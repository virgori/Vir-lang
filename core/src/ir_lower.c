/*
 * ir_lower.c – AST → Q-IR Lowering + Linear-Scan Register Allocator
 * ====================================================================
 * Pure C implementation.  Transforms the AST produced by the parser
 * into well-formed Q-IR instructions inside a q_module_t.
 *
 * After lowering, the linear-scan register allocator assigns physical
 * registers to virtual registers based on live intervals.
 */

#include "ir_lower.h"
#include "compiler_pipeline.h"
#include "lexer.h"
#include "parser.h"
#include "vm.h"    /* VIR_INTR_* intrinsic IDs for Q_INTRINSIC emission */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>


/* ═══════════════════════════════════════════════════════
 * AST Utilities
 * ═══════════════════════════════════════════════════════ */

ast_node_t *ast_new(ast_type_t type) {
  ast_node_t *n = (ast_node_t *)calloc(1, sizeof(ast_node_t));
  if (n)
    n->type = type;
  return n;
}

int ast_add_child(ast_node_t *parent, ast_node_t *child) {
  if (!parent || !child)
    return -1;
  if (parent->child_count >= AST_MAX_CHILDREN) {
    fprintf(stderr, "WARNING: AST_MAX_CHILDREN (%d) exceeded, parent type=%d, child type=%d name=%s\n",
            AST_MAX_CHILDREN, parent->type, child->type, child->name ? child->name : "");
    return -1;
  }
  parent->children[parent->child_count++] = child;
  return 0;
}

void ast_free(ast_node_t *node) {
  if (!node)
    return;
  for (uint32_t i = 0; i < node->child_count; i++)
    ast_free(node->children[i]);
  free(node);
}

/* ═══════════════════════════════════════════════════════
 * Symbol Table
 * ═══════════════════════════════════════════════════════ */

void sym_init(symbol_table_t *st) { memset(st, 0, sizeof(*st)); }

int sym_define(symbol_table_t *st, const char *name, uint32_t vreg,
               vir_type_t type) {
  if (st->count >= SYM_MAX)
    return -1;
  /* Overwrite if exists */
  for (uint32_t i = 0; i < st->count; i++) {
    if (strcmp(st->entries[i].name, name) == 0) {
      st->entries[i].vreg = vreg;
      st->entries[i].type = type;
      st->entries[i].type_name[0] = '\0';
      return 0;
    }
  }
  strncpy(st->entries[st->count].name, name, AST_NAME_LEN - 1);
  st->entries[st->count].vreg = vreg;
  st->entries[st->count].type = type;
  st->entries[st->count].type_name[0] = '\0';
  st->count++;
  return 0;
}

int sym_lookup(const symbol_table_t *st, const char *name, uint32_t *vreg) {
  for (uint32_t i = 0; i < st->count; i++) {
    if (strcmp(st->entries[i].name, name) == 0) {
      if (vreg)
        *vreg = st->entries[i].vreg;
      return 0;
    }
  }
  return -1; /* not found */
}

/* ═══════════════════════════════════════════════════════
 * Lowering Context
 * ═══════════════════════════════════════════════════════ */

void lower_init(lower_ctx_t *ctx, const char *module_name) {
  memset(ctx, 0, sizeof(*ctx));
  q_module_init(&ctx->module, module_name);
  q_vreg_alloc_init(&ctx->vreg_alloc);
  sym_init(&ctx->symbols);
  sym_init(&ctx->global_symbols);
}

#include "diagnostic.h"
extern diag_context_t g_parser_diag;
extern int g_diag_initialized;

static diag_entry_t *lower_error(lower_ctx_t *ctx, const ast_node_t *node, const char *msg) {
  if (node) {
      snprintf(ctx->last_error, sizeof(ctx->last_error), "[Line %u] %s", node->line, msg);
  } else {
      snprintf(ctx->last_error, sizeof(ctx->last_error), "%s", msg);
  }
  ctx->error_count++;

  if (!g_diag_initialized) {
    diag_init(&g_parser_diag, STAGE_0_C_CORE, DIAG_FMT_TERMINAL);
    g_diag_initialized = 1;
  }

  uint32_t code = E3001; // default to unsupported
  diag_phase_t phase = PHASE_IR_LOWER;
  diag_category_t cat = DCAT_LOWERING;

  if (strstr(msg, "undefined variable") != NULL || strstr(msg, "undefined:") != NULL || strstr(msg, "undefined port") != NULL) {
    code = E2001;
    phase = PHASE_SEMA;
    cat = DCAT_SEMANTIC;
  } else if (strstr(msg, "undefined function") != NULL) {
    code = E2002;
    phase = PHASE_SEMA;
    cat = DCAT_SEMANTIC;
  } else if (strstr(msg, "type mismatch") != NULL || strstr(msg, "needs ") != NULL || strstr(msg, "requires ") != NULL || strstr(msg, "without ") != NULL) {
    code = E2003;
    phase = PHASE_SEMA;
    cat = DCAT_SEMANTIC;
  } else if (strstr(msg, "invalid call") != NULL) {
    code = E3003;
    phase = PHASE_IR_LOWER;
    cat = DCAT_LOWERING;
  } else if (strstr(msg, "invalid lowering target") != NULL) {
    code = E3002;
    phase = PHASE_IR_LOWER;
    cat = DCAT_LOWERING;
  } else if (strstr(msg, "of moved value") != NULL) {
    code = E8001;
    phase = PHASE_BORROW;
    cat = DCAT_OWNERSHIP;
  } else if (strstr(msg, "cannot borrow") != NULL) {
    code = E8002;
    phase = PHASE_BORROW;
    cat = DCAT_OWNERSHIP;
  } else if (strstr(msg, "module not found") != NULL) {
    code = E7001;
    phase = PHASE_SEMA;
    cat = DCAT_MODULE;
  } else if (strstr(msg, "invariant violation") != NULL || strstr(msg, "out of memory") != NULL) {
    code = E9001;
    phase = PHASE_IR_LOWER;
    cat = DCAT_INTERNAL;
  } else if (strstr(msg, "unsupported") != NULL) {
    code = E3001;
    phase = PHASE_IR_LOWER;
    cat = DCAT_LOWERING;
  }

  diag_span_t span = DIAG_SPAN_EMPTY;
  if (node) {
    span = diag_span_lc(DIAG_NO_FILE, node->line, 1, 1);
  }

  if (code == E9001) {
    diag_ice_phase(&g_parser_diag, phase, code, ctx->last_error);
  } else {
    diag_entry_t *e = diag_error(&g_parser_diag, cat, phase, code, span, ctx->last_error);
    if (getenv("VIR_DEBUG_COMPILER")) {
      fprintf(stderr, "DEBUG_ERROR: node type=%d name=%s line=%u\n", node ? (int)node->type : -1, node && node->name ? node->name : "null", node ? node->line : 0);
    }
    
    if (e && (code == E2001 || code == E2002)) {
      if (code == E2002) {
        diag_set_analysis(&g_parser_diag, e, diag_str_ptr(&g_parser_diag, diag_intern_fmt(&g_parser_diag, "The compiler could not resolve the function `%s` in the current scope.", node && node->name ? node->name : "unknown")));
      } else {
        diag_set_analysis(&g_parser_diag, e, diag_str_ptr(&g_parser_diag, diag_intern_fmt(&g_parser_diag, "The compiler could not resolve the variable `%s` in the current scope.", node && node->name ? node->name : "unknown")));
      }
      diag_add_cause(&g_parser_diag, e, "Function or variable was not declared");
      diag_add_cause(&g_parser_diag, e, "Module was not imported");
      diag_add_cause(&g_parser_diag, e, "Symbol name contains a typo");
      diag_add_action(&g_parser_diag, e, "Check function and variable declarations");
      diag_add_action(&g_parser_diag, e, "Check imports");
      diag_add_action(&g_parser_diag, e, "Check symbol spelling");
    } else if (e && code == E2003) {
      diag_add_cause(&g_parser_diag, e, "Expression was not provided with expected operands or arguments");
      diag_add_action(&g_parser_diag, e, "Provide the correct number of arguments or operands");
    } else if (e && code == E3001) {
      diag_add_cause(&g_parser_diag, e, "The compiler IR lowering phase does not yet support this language feature");
      diag_add_action(&g_parser_diag, e, "Avoid using this syntax until it is fully supported by the compiler backend");
    } else if (e && code == E8001) {
      diag_set_analysis(&g_parser_diag, e, diag_str_ptr(&g_parser_diag, diag_intern_fmt(&g_parser_diag, "The value `%s` was used after it had already been moved.", node && node->name ? node->name : "unknown")));
      diag_add_cause(&g_parser_diag, e, "Value was assigned to another variable without cloning");
      diag_add_cause(&g_parser_diag, e, "Value was passed to a function that consumes it");
      diag_add_action(&g_parser_diag, e, "Pass by reference (borrow) instead of moving");
      diag_add_action(&g_parser_diag, e, "Clone the value if you need multiple owned copies");
    } else if (e && code == E8002) {
      diag_set_analysis(&g_parser_diag, e, diag_str_ptr(&g_parser_diag, diag_intern_fmt(&g_parser_diag, "Conflicting borrows detected for `%s`.", node && node->name ? node->name : "unknown")));
      diag_add_cause(&g_parser_diag, e, "Multiple mutable borrows of the same value in scope");
      diag_add_cause(&g_parser_diag, e, "Mutable borrow while shared borrows exist");
      diag_add_action(&g_parser_diag, e, "Ensure previous borrows end before creating a new one");
    }
    return e;
  }
  return NULL;
}

static int is_soft_value_name(const char *name) {
  if (!name || !name[0])
    return 1;
  if (strcmp(name, "null") == 0 || strcmp(name, "void") == 0 ||
      strcmp(name, "None") == 0 || strcmp(name, "Some") == 0 ||
      strcmp(name, "Ok") == 0 || strcmp(name, "Err") == 0 ||
      strcmp(name, "out") == 0 || strcmp(name, "end") == 0 ||
      strcmp(name, "e") == 0 || strcmp(name, "func") == 0 ||
      strcmp(name, "IoErrorKind") == 0 || strcmp(name, "default") == 0 ||
      strcmp(name, "count") == 0)
    return 1;
  return 0;
}

static int lookup_soft_const_value(const char *name, int64_t *out) {
  if (!name || !out)
    return 0;
  if (strcmp(name, "CODEBUF_INIT_CAP") == 0) {
    *out = 4096;
    return 1;
  }
  if (strcmp(name, "CG_MAX_LABELS") == 0) {
    *out = 1024;
    return 1;
  }
  if (strcmp(name, "CG_MAX_FIXUPS") == 0) {
    *out = 4096;
    return 1;
  }
  return 0;
}

static uint32_t fresh_vreg(lower_ctx_t *ctx);
static void emit(lower_ctx_t *ctx, q_instruction_t instr);

static int is_soft_call_name(const char *name) {
  if (!name || !name[0])
    return 0;
  if (strncmp(name, "native_", 7) == 0)
    return 1;
  if (strcmp(name, "panic") == 0 || strcmp(name, "free") == 0 ||
      strcmp(name, "realloc") == 0 || strcmp(name, "size_of") == 0 ||
      strcmp(name, "alloc") == 0 || strcmp(name, "min") == 0 ||
      strcmp(name, "max") == 0 || strcmp(name, "f") == 0 ||
      strcmp(name, "predicate") == 0 || strcmp(name, "ParseError") == 0 ||
      strcmp(name, "Ok") == 0 || strcmp(name, "Err") == 0 ||
      strcmp(name, "Some") == 0 || strcmp(name, "to_string") == 0 ||
      strcmp(name, "utf8_decode_char") == 0 || strcmp(name, "pred") == 0 ||
      strcmp(name, "eq") == 0 || strcmp(name, "char_to_str") == 0 ||
      strcmp(name, "out") == 0 || strcmp(name, "vec_set_at") == 0 ||
      strcmp(name, "str_from_i64") == 0 ||
      strcmp(name, "codebuf_get_data") == 0 ||
      strcmp(name, "read_u32") == 0 || strcmp(name, "patch_u32") == 0 ||
      strcmp(name, "patch_i32") == 0 || strcmp(name, "eprintln") == 0 ||
      strcmp(name, "read") == 0 || strcmp(name, "write") == 0 ||
      strcmp(name, "_next_pow2") == 0 ||
      strcmp(name, "alloc_zeroed") == 0 ||
      strcmp(name, "float_to_bits") == 0 ||
      strcmp(name, "wf_emit_sleb128") == 0 ||
      strcmp(name, "map_set") == 0 ||
      strcmp(name, "write_bytes_to_file") == 0)
    return 1;
  return 0;
}

static int lowering_strict_ownership(void) {
  return getenv("VIR_STRICT_OWNERSHIP") != NULL;
}

static int lowering_strict_fields(void) {
  return getenv("VIR_STRICT_FIELDS") != NULL;
}

static int emit_soft_zero(lower_ctx_t *ctx) {
  uint32_t rd = fresh_vreg(ctx);
  emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
  return (int)rd;
}

static int lookup_soft_qop_value(const char *name, int64_t *out) {
  struct qop_name_value {
    const char *name;
    int64_t value;
  };
  static const struct qop_name_value qops[] = {
      {"Nop", 0},          {"Load", 1},          {"Store", 2},
      {"Move", 3},         {"Add", 4},           {"Sub", 5},
      {"Mul", 6},          {"Div", 7},           {"Mod", 8},
      {"CmpEq", 9},        {"CmpGt", 10},        {"CmpLt", 11},
      {"CmpGe", 12},       {"CmpLe", 13},        {"And", 14},
      {"Or", 15},          {"Xor", 16},          {"Shl", 17},
      {"Shr", 18},         {"Label", 19},        {"Jump", 20},
      {"JumpIf", 21},      {"JumpIfNot", 22},    {"Call", 23},
      {"CallFunc", 24},    {"Ret", 25},          {"Halt", 26},
      {"Print", 27},       {"Input", 28},        {"PrintStr", 29},
      {"Alloc", 30},       {"Free", 31},         {"LoadByte", 32},
      {"StoreByte", 33},   {"LoadWord", 34},     {"StoreWord", 35},
      {"StrLen", 36},      {"StrGet", 37},       {"StrCat", 38},
      {"StrEq", 39},       {"IToStr", 40},       {"StrToI", 41},
      {"FileOpen", 42},    {"FileRead", 43},     {"FileWrite", 44},
      {"FileClose", 45},   {"FileWriteByte", 46},{"ArrNew", 47},
      {"ArrLen", 48},      {"ArrGet", 49},       {"ArrSet", 50},
      {"ArrPush", 51},     {"Exit", 52},         {"LoadGlobal", 53},
      {"StoreGlobal", 54}, {"GetArg", 55},       {"ArgCount", 56},
      {"PatchPoint", 57},  {"VLoad", 58},        {"VStore", 59},
      {"VAdd", 60},        {"VSub", 61},         {"VMul", 62},
      {"VFma", 63},        {"VDiv", 64},         {"VMin", 65},
      {"VMax", 66},        {"VReduce", 67},      {"VSplat", 68},
      {"VPerm", 69},       {"ArenaNew", 133},    {"ArenaAlloc", 134},
      {"ArenaFree", 135},  {"ArrCap", 149},      {"ArrCompact", 150},
      {"CallFFI", 200},    {"Syscall", 201},     {"SetArg", 202},
      {"LoadFuncAddr", 203},{"DictNew", 230},    {"DictSet", 231},
      {"DictGet", 232},    {"DictHas", 233},     {"DictDel", 234},
      {"DictSize", 235},   {"PortNew", 236},     {"PortSend", 237},
      {"PortRecv", 238},   {"PortLen", 239},     {"PortClose", 240},
      {"TaskWait", 244},   {"TaskCancel", 245},  {"Yield", 246},
      {"TensorNew", 247},  {"TensorGet1D", 248}, {"TensorSet1D", 249},
      {"TensorGet2D", 250},{"TensorSet2D", 251}, {"TensorMatmul", 252},
      {"TensorHadamard", 253},{"TensorQuantize", 254},
  };
  if (!name || !out)
    return 0;
  for (uint32_t i = 0; i < sizeof(qops) / sizeof(qops[0]); i++) {
    if (strcmp(qops[i].name, name) == 0) {
      *out = qops[i].value;
      return 1;
    }
  }
  return 0;
}

/* Allocate a fresh virtual register */
static uint32_t fresh_vreg(lower_ctx_t *ctx) {
  return q_vreg_alloc_next(&ctx->vreg_alloc);
}

/* Lookup in local then global scope
 * Returns: 0 = found local, 1 = found global, -1 = not found
 * If found, *idx contains vreg (local) or global_index (global) */
static int sym_lookup_both(lower_ctx_t *ctx, const char *name, uint32_t *idx) {
  if (sym_lookup(&ctx->symbols, name, idx) == 0)
    return 0; /* local */
  if (ctx->current_func) {
    for (uint32_t i = 0; i < ctx->current_func->param_count; i++) {
      if (strcmp(ctx->current_func->param_names[i], name) == 0) {
        if (idx)
          *idx = ctx->current_func->param_vregs[i];
        return 0;
      }
    }
  }
  if (sym_lookup(&ctx->global_symbols, name, idx) == 0)
    return 1; /* global */
  return -1;  /* not found */
}

/* Encode a ref-argument binding for VM write-back:
 *   0          = no binding
 *   vreg + 1   = caller local vreg
 *  -(gidx + 1) = caller global slot */
static int64_t lower_ref_binding(lower_ctx_t *ctx, const ast_node_t *arg) {
  if (!arg)
    return 0;
  if (arg->type == AST_NAMED_ARG) {
    arg = (arg->child_count > 0) ? arg->children[0] : NULL;
  }
  if (!arg || arg->type != AST_IDENTIFIER)
    return 0;

  uint32_t idx = 0;
  int scope = sym_lookup_both(ctx, arg->name, &idx);
  if (scope == 0)
    return (int64_t)idx + 1;
  if (scope == 1)
    return -((int64_t)idx + 1);
  return 0;
}

/* §4.8: same as sym_lookup_both but also returns the symbol entry so we
 * can read/modify ownership flags (is_moved, is_move_type, borrow counts).
 * Returns scope (0 local, 1 global) or -1 if not found. */
static int sym_lookup_entry_both(lower_ctx_t *ctx, const char *name,
                                 symbol_entry_t **out_entry,
                                 uint32_t *out_idx) {
  for (uint32_t i = 0; i < ctx->symbols.count; i++) {
    if (strcmp(ctx->symbols.entries[i].name, name) == 0) {
      if (out_entry)
        *out_entry = &ctx->symbols.entries[i];
      if (out_idx)
        *out_idx = ctx->symbols.entries[i].vreg;
      return 0;
    }
  }
  for (uint32_t i = 0; i < ctx->global_symbols.count; i++) {
    if (strcmp(ctx->global_symbols.entries[i].name, name) == 0) {
      if (out_entry)
        *out_entry = &ctx->global_symbols.entries[i];
      if (out_idx)
        *out_idx = ctx->global_symbols.entries[i].vreg;
      return 0; /* treat as "found"; scope=1 unavailable here */
    }
  }
  if (out_entry)
    *out_entry = NULL;
  return -1;
}

/* §4.8: classify AST node as producing a move-typed value (heap-ish).
 * Conservative: array literal, string literal, alloc() builtin, record
 * literal. Returns 1 if the value should be treated as move-type. */
static int ast_produces_move_type(const ast_node_t *n) {
  if (!n)
    return 0;
  switch (n->type) {
  case AST_ARRAY_LITERAL:
  case AST_LITERAL_STR:
  case AST_RECORD_LITERAL:
    return 1;
  case AST_BUILTIN_CALL:
    if (n->builtin_id == BUILTIN_ALLOC || n->builtin_id == BUILTIN_ARR_NEW ||
        n->builtin_id == BUILTIN_STR_CAT || n->builtin_id == BUILTIN_I_TO_STR)
      return 1;
    return 0;
  default:
    return 0;
  }
}

/* §4.8: unwrap AST_BORROW to look at what's being borrowed. */
static const ast_node_t *ast_unwrap_borrow(const ast_node_t *n) {
  while (n && n->type == AST_BORROW && n->child_count >= 1)
    n = n->children[0];
  return n;
}

/* §4.8 NLL: release any active borrow held by `ent`. If ent.borrow_kind
 * is non-zero, look up ent.borrow_of_name in symbol tables and decrement
 * that target's shared/mut counter. Clears ent's borrow state. */
static void ownership_release_borrow(lower_ctx_t *ctx, symbol_entry_t *ent) {
  if (!ent || ent->borrow_kind == 0)
    return;
  symbol_entry_t *target = NULL;
  if (sym_lookup_entry_both(ctx, ent->borrow_of_name, &target, NULL) == 0 &&
      target) {
    if (ent->borrow_kind == 1 && target->borrow_shared_count > 0)
      target->borrow_shared_count--;
    else if (ent->borrow_kind == 2 && target->borrow_mut_count > 0)
      target->borrow_mut_count--;
  }
  ent->borrow_kind = 0;
  ent->borrow_of_name[0] = '\0';
}

/* §4.8 NLL: release all active borrows in both tables (called at func exit). */
static void ownership_release_all_borrows(lower_ctx_t *ctx) {
  for (uint32_t i = 0; i < ctx->symbols.count; i++) {
    ownership_release_borrow(ctx, &ctx->symbols.entries[i]);
  }
  for (uint32_t i = 0; i < ctx->global_symbols.count; i++) {
    ownership_release_borrow(ctx, &ctx->global_symbols.entries[i]);
  }
}

/* §4.8 NLL: a binder (var_decl / assign) with an AST_BORROW as RHS
 * claims the most recent unclaimed stmt_borrow. This transfers the
 * counter increment from the transient statement scope to the
 * borrower's persistent cross-stmt back-link. */
static void ownership_claim_stmt_borrow(lower_ctx_t *ctx,
                                        symbol_entry_t *borrower,
                                        const ast_node_t *rhs) {
  if (!borrower || !rhs || rhs->type != AST_BORROW)
    return;
  if (rhs->child_count < 1)
    return;
  const ast_node_t *tgt = rhs->children[0];
  if (!tgt || tgt->type != AST_IDENTIFIER)
    return;
  uint8_t kind = (rhs->int_val != 0) ? 2 : 1;
  /* Find most recent unclaimed matching entry. */
  for (int i = (int)ctx->stmt_borrow_count - 1; i >= 0; i--) {
    if (ctx->stmt_borrows[i].claimed)
      continue;
    if (ctx->stmt_borrows[i].kind != kind)
      continue;
    if (strcmp(ctx->stmt_borrows[i].target, tgt->name) != 0)
      continue;
    ctx->stmt_borrows[i].claimed = 1;
    /* AST_BORROW already incremented target's counter and the
     * borrower persistently takes ownership of that increment;
     * record the back-link but do NOT increment again. */
    borrower->borrow_kind = kind;
    strncpy(borrower->borrow_of_name, tgt->name, AST_NAME_LEN - 1);
    borrower->borrow_of_name[AST_NAME_LEN - 1] = '\0';
    return;
  }
}

/* §4.8 NLL: at the end of a statement, decrement counters for any
 * borrow that was NOT claimed by a binder (e.g. function arguments). */
static void ownership_release_unclaimed_stmt_borrows(lower_ctx_t *ctx) {
  for (uint32_t i = 0; i < ctx->stmt_borrow_count; i++) {
    if (ctx->stmt_borrows[i].claimed)
      continue;
    symbol_entry_t *target = NULL;
    if (sym_lookup_entry_both(ctx, ctx->stmt_borrows[i].target, &target,
                              NULL) == 0 &&
        target) {
      if (ctx->stmt_borrows[i].kind == 1 && target->borrow_shared_count > 0)
        target->borrow_shared_count--;
      else if (ctx->stmt_borrows[i].kind == 2 && target->borrow_mut_count > 0)
        target->borrow_mut_count--;
    }
  }
  ctx->stmt_borrow_count = 0;
}

/* §4.8: if `src` is a bare identifier referring to a move-typed symbol,
 * mark that symbol as moved. `var y = x` / `y = x` consumes x. A borrow
 * (`&x`) does NOT consume — callers strip AST_BORROW before calling this. */
static void ownership_mark_moved_if_id(lower_ctx_t *ctx,
                                       const ast_node_t *src) {
  const ast_node_t *u = ast_unwrap_borrow(src);
  if (!u || u->type != AST_IDENTIFIER)
    return;
  /* If the original src was wrapped in an AST_BORROW, don't move. */
  if (src && src->type == AST_BORROW)
    return;
  symbol_entry_t *ent = NULL;
  if (sym_lookup_entry_both(ctx, u->name, &ent, NULL) < 0 || !ent)
    return;
  if (ent->is_move_type) {
    ent->is_moved = 1;
    ent->moved_at_line = src->line;
  }
}

/* Allocate a fresh label id */
static uint32_t fresh_label(lower_ctx_t *ctx) { return ctx->label_counter++; }

/* Find function index by name (returns -1 if not found) */
int lower_find_func_index(lower_ctx_t *ctx, const char *name) {
  for (uint32_t i = 0; i < ctx->module.func_count; i++) {
    if (strcmp(ctx->module.functions[i].name, name) == 0)
      return (int)i;
  }
  return -1;
}

int lower_lookup_vreg(lower_ctx_t *ctx, const char *name, uint32_t *vreg) {
  if (!ctx || !name)
    return -1;
  return sym_lookup_both(ctx, name, vreg);
}

int lower_lookup_local_vreg(lower_ctx_t *ctx, const char *name, uint32_t *vreg) {
  if (!ctx || !name)
    return -1;
  if (sym_lookup(&ctx->symbols, name, vreg) == 0)
    return 0;
  if (ctx->current_func) {
    for (uint32_t i = 0; i < ctx->current_func->param_count; i++) {
      if (strcmp(ctx->current_func->param_names[i], name) == 0) {
        if (vreg)
          *vreg = ctx->current_func->param_vregs[i];
        return 0;
      }
    }
  }
  return -1;
}

int lower_declare_var(lower_ctx_t *ctx, const char *name, uint32_t *vreg) {
  if (!ctx || !name || !vreg)
    return -1;
  uint32_t v = fresh_vreg(ctx);
  if (sym_define(&ctx->symbols, name, v, VIR_TYPE_I64) != 0)
    return -1;
  *vreg = v;
  return 0;
}

static int find_func_index(lower_ctx_t *ctx, const char *name) {
  return lower_find_func_index(ctx, name);
}

/* Emit instruction into current function */
static void emit(lower_ctx_t *ctx, q_instruction_t instr) {
  if (ctx->current_func)
    q_func_emit(ctx->current_func, instr);
}

/* ═══════════════════════════════════════════════════════
 * Enum / Record Type Lookup Helpers
 * ═══════════════════════════════════════════════════════ */

static enum_type_t *find_enum_type(lower_ctx_t *ctx, const char *name) {
  for (uint32_t i = 0; i < ctx->enum_type_count; i++) {
    if (strcmp(ctx->enum_types[i].name, name) == 0)
      return &ctx->enum_types[i];
  }
  return NULL;
}

static int64_t enum_lookup_variant(const enum_type_t *et, const char *variant) {
  if (!et || !variant || et->variant_count > ENUM_MAX_VARIANTS)
    return -1;
  for (uint32_t i = 0; i < et->variant_count; i++) {
    if (strcmp(et->variants[i].name, variant) == 0)
      return et->variants[i].value;
  }
  return -1;
}

static record_type_t *find_record_type(lower_ctx_t *ctx, const char *name) {
  for (uint32_t i = 0; i < ctx->record_type_count; i++) {
    if (strcmp(ctx->record_types[i].name, name) == 0)
      return &ctx->record_types[i];
  }
  if (name[0] == '\0') {
    /* Create a synthetic record type for tuples! */
    if (ctx->record_type_count < RECORD_MAX_TYPES) {
      record_type_t *rt = &ctx->record_types[ctx->record_type_count++];
      rt->name[0] = '\0';
      rt->field_count = 32;
      for (uint32_t f = 0; f < 32; f++) {
        snprintf(rt->fields[f].name, AST_NAME_LEN, "%u", f);
        rt->fields[f].type_name[0] = '\0';
        rt->fields[f].offset = f * 8;
      }
      return rt;
    }
  }
  return NULL;
}

static int record_field_offset(const record_type_t *rt, const char *field) {
  for (uint32_t i = 0; i < rt->field_count; i++) {
    if (strcmp(rt->fields[i].name, field) == 0)
      return (int)rt->fields[i].offset;
  }
  return -1;
}

static const char *find_func_return_type(lower_ctx_t *ctx, const char *name) {
  if (!ctx || !name || !name[0])
    return NULL;
  for (uint32_t i = 0; i < ctx->func_return_type_count; i++) {
    if (strcmp(ctx->func_return_types[i].name, name) == 0 &&
        ctx->func_return_types[i].type_name[0])
      return ctx->func_return_types[i].type_name;
  }
  return NULL;
}

static void register_func_return_type(lower_ctx_t *ctx, const char *name,
                                      const char *type_name) {
  if (!ctx || !name || !name[0] || !type_name || !type_name[0])
    return;
  if (!find_record_type(ctx, type_name))
    return;
  for (uint32_t i = 0; i < ctx->func_return_type_count; i++) {
    if (strcmp(ctx->func_return_types[i].name, name) == 0) {
      strncpy(ctx->func_return_types[i].type_name, type_name,
              AST_NAME_LEN - 1);
      ctx->func_return_types[i].type_name[AST_NAME_LEN - 1] = '\0';
      return;
    }
  }
  if (ctx->func_return_type_count >= FUNC_RETURN_TYPE_MAX)
    return;
  uint32_t idx = ctx->func_return_type_count++;
  strncpy(ctx->func_return_types[idx].name, name, AST_NAME_LEN - 1);
  ctx->func_return_types[idx].name[AST_NAME_LEN - 1] = '\0';
  strncpy(ctx->func_return_types[idx].type_name, type_name, AST_NAME_LEN - 1);
  ctx->func_return_types[idx].type_name[AST_NAME_LEN - 1] = '\0';
}

static const record_field_t *record_field_info(const record_type_t *rt,
                                               const char *field) {
  if (!rt || !field)
    return NULL;
  for (uint32_t i = 0; i < rt->field_count; i++) {
    if (strcmp(rt->fields[i].name, field) == 0)
      return &rt->fields[i];
  }
  return NULL;
}

static int copy_array_element_type_name(const char *type_name, char *out,
                                        size_t out_sz) {
  if (!type_name || !out || out_sz == 0)
    return 0;
  out[0] = '\0';
  if (type_name[0] != '[')
    return 0;
  const char *end = strchr(type_name + 1, ']');
  if (!end || end == type_name + 1)
    return 0;
  size_t n = (size_t)(end - (type_name + 1));
  if (n >= out_sz)
    n = out_sz - 1;
  memcpy(out, type_name + 1, n);
  out[n] = '\0';
  return out[0] != '\0';
}

static int copy_symbol_type_name(lower_ctx_t *ctx, const char *name, char *out,
                                 size_t out_sz) {
  if (!ctx || !name || !name[0] || !out || out_sz == 0)
    return 0;
  out[0] = '\0';
  symbol_entry_t *ent = NULL;
  if (sym_lookup_entry_both(ctx, name, &ent, NULL) < 0 || !ent ||
      !ent->type_name[0])
    return 0;
  strncpy(out, ent->type_name, out_sz - 1);
  out[out_sz - 1] = '\0';
  return 1;
}

static int copy_expr_type_name(lower_ctx_t *ctx, const ast_node_t *expr,
                               char *out, size_t out_sz) {
  if (!ctx || !expr || !out || out_sz == 0)
    return 0;
  out[0] = '\0';

  if (expr->type == AST_IDENTIFIER)
    return copy_symbol_type_name(ctx, expr->name, out, out_sz);

  if ((expr->type == AST_CALL || expr->type == AST_RECORD_LITERAL) &&
      expr->name[0] && find_record_type(ctx, expr->name)) {
    strncpy(out, expr->name, out_sz - 1);
    out[out_sz - 1] = '\0';
    return 1;
  }

  /* Element accessors over a generic container `Vec<T>` (stored as `[T]`):
   * infer the element type from the container argument. This is what makes
   * `f = vec_get_rt(mod.functions, i); f.body` resolve to the right offset. */
  if (expr->type == AST_CALL && expr->name[0] && expr->child_count >= 1 &&
      (strcmp(expr->name, "vec_get_rt") == 0 ||
       strcmp(expr->name, "vec_get") == 0)) {
    char cont_type[AST_NAME_LEN];
    if (copy_expr_type_name(ctx, expr->children[0], cont_type,
                            sizeof(cont_type)) &&
        copy_array_element_type_name(cont_type, out, out_sz))
      return 1;
  }

  if (expr->type == AST_CALL && expr->name[0]) {
    const char *ret_type = find_func_return_type(ctx, expr->name);
    if (ret_type && ret_type[0]) {
      strncpy(out, ret_type, out_sz - 1);
      out[out_sz - 1] = '\0';
      return 1;
    }
  }

  if ((expr->type == AST_FIELD_ACCESS || expr->type == AST_SAFE_ACCESS) &&
      expr->child_count >= 1) {
    char base_type[AST_NAME_LEN];
    if (!copy_expr_type_name(ctx, expr->children[0], base_type,
                             sizeof(base_type)))
      return 0;
    record_type_t *rt = find_record_type(ctx, base_type);
    const record_field_t *rf = record_field_info(rt, expr->name);
    if (!rf || !rf->type_name[0])
      return 0;
    strncpy(out, rf->type_name, out_sz - 1);
    out[out_sz - 1] = '\0';
    return 1;
  }

  if (expr->type == AST_INDEX_ACCESS) {
    char base_type[AST_NAME_LEN];
    if (expr->name[0]) {
      if (!copy_symbol_type_name(ctx, expr->name, base_type,
                                 sizeof(base_type)))
        return 0;
    } else if (expr->child_count >= 1) {
      if (!copy_expr_type_name(ctx, expr->children[0], base_type,
                               sizeof(base_type)))
        return 0;
    } else {
      return 0;
    }
    return copy_array_element_type_name(base_type, out, out_sz);
  }

  return 0;
}

static record_type_t *record_type_for_symbol(lower_ctx_t *ctx,
                                             const char *name,
                                             const char **out_type_name) {
  if (out_type_name)
    *out_type_name = NULL;
  if (!ctx || !name || !name[0])
    return NULL;

  symbol_entry_t *ent = NULL;
  if (sym_lookup_entry_both(ctx, name, &ent, NULL) >= 0 && ent &&
      ent->type_name[0]) {
    record_type_t *rt = find_record_type(ctx, ent->type_name);
    if (rt) {
      if (out_type_name)
        *out_type_name = ent->type_name;
      return rt;
    }
  }
  return NULL;
}

static record_type_t *record_type_for_expr(lower_ctx_t *ctx,
                                           const ast_node_t *expr,
                                           const char **out_type_name) {
  if (out_type_name)
    *out_type_name = NULL;
  if (!ctx || !expr)
    return NULL;

  char type_name[AST_NAME_LEN];
  if (copy_expr_type_name(ctx, expr, type_name, sizeof(type_name))) {
    record_type_t *rt = find_record_type(ctx, type_name);
    if (rt) {
      if (out_type_name)
        *out_type_name = rt->name;
      return rt;
    }
  }

  return NULL;
}

static void symbol_infer_record_type_from_expr(lower_ctx_t *ctx,
                                               symbol_entry_t *ent,
                                               const ast_node_t *expr) {
  if (!ent || ent->type_name[0])
    return;
  const char *type_name = NULL;
  if (record_type_for_expr(ctx, expr, &type_name) && type_name && type_name[0]) {
    strncpy(ent->type_name, type_name, AST_NAME_LEN - 1);
    ent->type_name[AST_NAME_LEN - 1] = '\0';
  }
}

/* Exported for the HIR pipeline: record the (record/array) type of a local
 * variable so later field-offset resolution can find the right offset. Mirrors
 * the annotation/inference logic in the legacy lower_stmt VAR_DECL path — the
 * HIR var-decl lowering otherwise never assigns a record type to the symbol,
 * which forced entity field reads onto the ambiguous scan-all fallback. */
void lower_infer_symbol_type(lower_ctx_t *ctx, const char *name,
                             const char *annot, const ast_node_t *init) {
  if (!ctx || !name || !name[0])
    return;
  symbol_entry_t *ent = NULL;
  if (sym_lookup_entry_both(ctx, name, &ent, NULL) < 0 || !ent)
    return;
  if (ent->type_name[0])
    return;
  if (annot && annot[0]) {
    strncpy(ent->type_name, annot, AST_NAME_LEN - 1);
    ent->type_name[AST_NAME_LEN - 1] = '\0';
    return;
  }
  symbol_infer_record_type_from_expr(ctx, ent, init);
}

static int infer_return_type_from_stmt(lower_ctx_t *ctx, const ast_node_t *stmt,
                                       char *out, size_t out_sz) {
  if (!ctx || !stmt || !out || out_sz == 0)
    return 0;

  if (stmt->type == AST_RETURN && stmt->child_count > 0 &&
      stmt->children[0]) {
    return copy_expr_type_name(ctx, stmt->children[0], out, out_sz);
  }

  if (stmt->type == AST_FUNC_DEF)
    return 0;

  for (uint32_t i = 0; i < stmt->child_count; i++) {
    if (infer_return_type_from_stmt(ctx, stmt->children[i], out, out_sz))
      return 1;
  }
  return 0;
}

static void infer_func_return_type(lower_ctx_t *ctx,
                                   const ast_node_t *func_def) {
  if (!ctx || !func_def || func_def->type != AST_FUNC_DEF)
    return;

  char type_name[AST_NAME_LEN];
  type_name[0] = '\0';
  for (uint32_t i = 0; i < func_def->child_count; i++) {
    const ast_node_t *child = func_def->children[i];
    if (!child || child->type == AST_IDENTIFIER)
      continue;
    if (infer_return_type_from_stmt(ctx, child, type_name,
                                    sizeof(type_name))) {
      register_func_return_type(ctx, func_def->name, type_name);
      return;
    }
  }
}

static int record_field_offset_for_expr(lower_ctx_t *ctx,
                                        const ast_node_t *base_expr,
                                        const char *field,
                                        const record_type_t **out_rt) {
  if (out_rt)
    *out_rt = NULL;
  if (!field || !field[0])
    return -1;
  if (field[0] >= '0' && field[0] <= '9')
    return atoi(field) * 8;

  record_type_t *typed_rt = record_type_for_expr(ctx, base_expr, NULL);
  if (typed_rt) {
    int off = record_field_offset(typed_rt, field);
    if (off >= 0) {
      if (out_rt)
        *out_rt = typed_rt;
      return off;
    }
  }

  for (uint32_t i = 0; i < ctx->record_type_count; i++) {
    int off = record_field_offset(&ctx->record_types[i], field);
    if (off >= 0) {
      if (out_rt)
        *out_rt = &ctx->record_types[i];
      return off;
    }
  }
  /* Soft layout for string-like runtime blobs (str_from_cstr): */
  if (strcmp(field, "data") == 0)
    return 0;
  if (strcmp(field, "byte_len") == 0 || strcmp(field, "len") == 0)
    return 8;
  if (strcmp(field, "char_len") == 0 || strcmp(field, "cap") == 0)
    return 16;
  return -1;
}

int lower_record_field_offset(lower_ctx_t *ctx, const ast_node_t *base_expr,
                              const char *field_name) {
  if (!ctx || !base_expr || !field_name)
    return -1;
  return record_field_offset_for_expr(ctx, base_expr, field_name, NULL);
}

static int record_field_offset_for_symbol(lower_ctx_t *ctx,
                                          const char *symbol_name,
                                          const char *field,
                                          const record_type_t **out_rt) {
  if (out_rt)
    *out_rt = NULL;
  if (!field || !field[0])
    return -1;
  if (field[0] >= '0' && field[0] <= '9')
    return atoi(field) * 8;

  record_type_t *typed_rt = record_type_for_symbol(ctx, symbol_name, NULL);
  if (typed_rt) {
    int off = record_field_offset(typed_rt, field);
    if (off >= 0) {
      if (out_rt)
        *out_rt = typed_rt;
      return off;
    }
  }

  for (uint32_t i = 0; i < ctx->record_type_count; i++) {
    int off = record_field_offset(&ctx->record_types[i], field);
    if (off >= 0) {
      if (out_rt)
        *out_rt = &ctx->record_types[i];
      return off;
    }
  }
  if (strcmp(field, "data") == 0)
    return 0;
  if (strcmp(field, "byte_len") == 0 || strcmp(field, "len") == 0)
    return 8;
  if (strcmp(field, "char_len") == 0 || strcmp(field, "cap") == 0)
    return 16;
  return -1;
}

/* §16 Register / Mold — lookup helpers + bit extract/insert emission. */
static bit_type_t *find_bit_type(lower_ctx_t *ctx, const char *name) {
  if (!name || !*name)
    return NULL;
  for (uint32_t i = 0; i < ctx->bit_type_count; i++) {
    if (strcmp(ctx->bit_types[i].name, name) == 0)
      return &ctx->bit_types[i];
  }
  return NULL;
}

static const bit_field_t *find_bit_field(const bit_type_t *bt,
                                         const char *field) {
  if (!bt)
    return NULL;
  for (uint32_t i = 0; i < bt->field_count; i++) {
    if (strcmp(bt->fields[i].name, field) == 0)
      return &bt->fields[i];
  }
  return NULL;
}

/* Compute a (1 << width) - 1 style mask immediate (width capped at 63 to
 * avoid UB when width == 64; base types in §16 never exceed 64 bits). */
static uint64_t bit_mask_u64(uint8_t width) {
  if (width == 0)
    return 0;
  if (width >= 64)
    return ~(uint64_t)0;
  return ((uint64_t)1 << width) - 1;
}

/* Emit `dest = (src >> lo) & mask` for reading a bit-field. */
static uint32_t emit_bit_extract(lower_ctx_t *ctx, uint32_t src, uint8_t lo,
                                 uint8_t width) {
  uint32_t shifted = src;
  if (lo > 0) {
    uint32_t sh = fresh_vreg(ctx);
    uint32_t lo_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(lo_r), q_imm((int64_t)lo), q_none()));
    emit(ctx, q_instr(Q_SHR, q_vreg(sh), q_vreg(src), q_vreg(lo_r)));
    shifted = sh;
  }
  uint32_t mask_r = fresh_vreg(ctx);
  uint32_t rd = fresh_vreg(ctx);
  emit(ctx, q_instr(Q_LOAD, q_vreg(mask_r), q_imm((int64_t)bit_mask_u64(width)),
                    q_none()));
  emit(ctx, q_instr(Q_AND, q_vreg(rd), q_vreg(shifted), q_vreg(mask_r)));
  return rd;
}

/* Emit `dest = (old & ~(mask << lo)) | ((val & mask) << lo)` for writing. */
static uint32_t emit_bit_insert(lower_ctx_t *ctx, uint32_t old_val,
                                uint32_t new_val, uint8_t lo, uint8_t width) {
  uint64_t mask = bit_mask_u64(width);
  uint64_t clear_mask = ~(mask << lo);

  /* cleared = old & clear_mask */
  uint32_t cm_r = fresh_vreg(ctx);
  uint32_t cleared = fresh_vreg(ctx);
  emit(ctx,
       q_instr(Q_LOAD, q_vreg(cm_r), q_imm((int64_t)clear_mask), q_none()));
  emit(ctx, q_instr(Q_AND, q_vreg(cleared), q_vreg(old_val), q_vreg(cm_r)));

  /* masked = (new_val & mask) */
  uint32_t m_r = fresh_vreg(ctx);
  uint32_t masked = fresh_vreg(ctx);
  emit(ctx, q_instr(Q_LOAD, q_vreg(m_r), q_imm((int64_t)mask), q_none()));
  emit(ctx, q_instr(Q_AND, q_vreg(masked), q_vreg(new_val), q_vreg(m_r)));

  /* shifted = masked << lo */
  uint32_t shifted = masked;
  if (lo > 0) {
    uint32_t lo_r = fresh_vreg(ctx);
    uint32_t sh = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(lo_r), q_imm((int64_t)lo), q_none()));
    emit(ctx, q_instr(Q_SHL, q_vreg(sh), q_vreg(masked), q_vreg(lo_r)));
    shifted = sh;
  }

  /* result = cleared | shifted */
  uint32_t rd = fresh_vreg(ctx);
  emit(ctx, q_instr(Q_OR, q_vreg(rd), q_vreg(cleared), q_vreg(shifted)));
  return rd;
}

/* ═══════════════════════════════════════════════════════
 * Expression Lowering
 * ═══════════════════════════════════════════════════════
 *
 * Each expression returns a vreg holding the result.
 */

/* §17 precomp: recursive constant folder over a literal-only subtree.
 * Supports: LITERAL_INT, BINOP (arithmetic/bitwise/shift) with constant
 * children, and unary minus (AST_BINOP with OP_SUB against literal 0 as
 * produced by parser). Returns 1 on success, 0 if any non-constant
 * subtree is encountered. */
static int precomp_fold(const ast_node_t *e, int64_t *out) {
  if (!e || !out)
    return 0;
  switch (e->type) {
  case AST_LITERAL_INT:
    *out = e->int_val;
    return 1;
  case AST_BINOP: {
    if (e->child_count != 2)
      return 0;
    int64_t a, b;
    if (!precomp_fold(e->children[0], &a))
      return 0;
    if (!precomp_fold(e->children[1], &b))
      return 0;
    int64_t r = 0;
    int ov = 0;
    switch (e->op) {
    case OP_ADD:
      ov = __builtin_add_overflow(a, b, &r);
      *out = r;
      break;
    case OP_SUB:
      ov = __builtin_sub_overflow(a, b, &r);
      *out = r;
      break;
    case OP_MUL:
      ov = __builtin_mul_overflow(a, b, &r);
      *out = r;
      break;
    case OP_DIV:
      if (b == 0) {
        fprintf(stderr, "warning W152: precomp division by zero\n");
        return 0;
      }
      *out = a / b;
      return 1;
    case OP_MOD:
      if (b == 0) {
        fprintf(stderr, "warning W152: precomp mod by zero\n");
        return 0;
      }
      *out = a % b;
      return 1;
    case OP_SHL:
      *out = (int64_t)((uint64_t)a << (b & 63));
      return 1;
    case OP_SHR:
      *out = a >> (b & 63);
      return 1;
    case OP_AND:
      *out = a & b;
      return 1;
    case OP_OR:
      *out = a | b;
      return 1;
    case OP_XOR:
      *out = a ^ b;
      return 1;
    default:
      return 0;
    }
    if (ov) {
      fprintf(stderr, "warning W152: precomp i64 overflow at line %u\n",
              e->line);
    }
    return 1;
  }
  case AST_COMPARE: {
    if (e->child_count != 2)
      return 0;
    int64_t a, b;
    if (!precomp_fold(e->children[0], &a))
      return 0;
    if (!precomp_fold(e->children[1], &b))
      return 0;
    switch (e->op) {
    case OP_EQ:
      *out = (a == b);
      return 1;
    case OP_NE:
      *out = (a != b);
      return 1;
    case OP_GT:
      *out = (a > b);
      return 1;
    case OP_LT:
      *out = (a < b);
      return 1;
    case OP_GE:
      *out = (a >= b);
      return 1;
    case OP_LE:
      *out = (a <= b);
      return 1;
    default:
      return 0;
    }
  }
  case AST_PRECOMP:
    /* Nested precomp: fold its child directly. */
    if (e->child_count > 0)
      return precomp_fold(e->children[0], out);
    return 0;
  default:
    return 0;
  }
}

int lower_expr(lower_ctx_t *ctx, const ast_node_t *expr) {
  if (!expr) {
    lower_error(ctx, expr, "null expr");
    return -1;
  }

  switch (expr->type) {

  case AST_LITERAL_INT: {
    uint32_t r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(expr->int_val), q_none()));
    return (int)r;
  }

  /* §17.1 precomp EXPR / comptime EXPR — prefix modifier.
   * Recursively constant-fold literal-only subtree. Falls back to runtime
   * evaluation if anything non-constant is encountered. */
  case AST_PRECOMP: {
    int64_t folded = 0;
    int ok = 0;
    if (expr->child_count > 0) {
      ok = precomp_fold(expr->children[0], &folded);
    }
    uint32_t r = fresh_vreg(ctx);
    if (ok) {
      emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(folded), q_none()));
    } else if (expr->child_count > 0) {
      /* §17 fallback: runtime evaluation (parser kept the expr). */
      int v = lower_expr(ctx, expr->children[0]);
      if (v < 0)
        return -1;
      emit(ctx, q_instr(Q_MOVE, q_vreg(r), q_vreg((uint32_t)v), q_none()));
    } else {
      emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(0), q_none()));
    }
    return (int)r;
  }

  /* §23.3 recv PORT — pop front (-1 if empty) */
  case AST_RECV_EXPR: {
    uint32_t pidx;
    int scope = sym_lookup_both(ctx, expr->name, &pidx);
    if (scope < 0) {
      lower_error(ctx, expr, "undefined port");
      return -1;
    }
    uint32_t pv;
    if (scope == 1) {
      pv = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(pv), q_imm(pidx), q_none()));
    } else {
      pv = pidx;
    }
    uint32_t r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_PORT_RECV, q_vreg(r), q_vreg(pv), q_none()));
    return (int)r;
  }

  case AST_ERX_READ: {
    /* §13.5 — read error register */
    uint32_t r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_ERX_LOAD, q_vreg(r), q_none(), q_none()));
    return (int)r;
  }


  case AST_IDENTIFIER: {
    uint32_t idx;
    int scope = sym_lookup_both(ctx, expr->name, &idx);

    if (scope < 0) {
      /* §Phase-8 scoped identifier `A::B` — fold as enum access. */
      const char *sep = strstr(expr->name, "::");
      if (sep && sep != expr->name) {
        char enum_name[128];
        size_t n = (size_t)(sep - expr->name);
        if (n >= sizeof(enum_name))
          n = sizeof(enum_name) - 1;
        memcpy(enum_name, expr->name, n);
        enum_name[n] = '\0';
        const char *variant = sep + 2;
        enum_type_t *et = find_enum_type(ctx, enum_name);
        if (et) {
          int64_t val = enum_lookup_variant(et, variant);
          if (val >= 0) {
            uint32_t rd = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(val), q_none()));
            return (int)rd;
          }
        }
      }
      /* §6.6 / §11.4 bước 2: identifier may refer to a function.
       * Materialise the function index as an i64 so it can be stored
       * in a field / passed as argument / later called indirectly. */
      int fidx = find_func_index(ctx, expr->name);
      if (fidx >= 0) {
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm((int64_t)fidx), q_none()));
        return (int)rd;
      }
      int64_t const_val = 0;
      if (lookup_soft_const_value(expr->name, &const_val)) {
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(const_val), q_none()));
        return (int)rd;
      }
      if (is_soft_value_name(expr->name)) {
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      char buf[128];
      snprintf(buf, sizeof(buf), "undefined variable: %s", expr->name);
      lower_error(ctx, expr, buf);
      return -1;
    }
    /* §4.8: reject read of a moved value. */
    {
      symbol_entry_t *ent = NULL;
      sym_lookup_entry_both(ctx, expr->name, &ent, NULL);
      if (lowering_strict_ownership() && ent && ent->is_moved) {
        char buf[128];
        snprintf(buf, sizeof(buf), "use of moved value: '%s'", expr->name);
        diag_entry_t *e = lower_error(ctx, expr, buf);
        if (e && ent->moved_at_line > 0) {
          diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->moved_at_line, 1, 1), "value was moved here");
        }
        return -1;
      }
    }
    if (scope == 1) {
      /* Global variable - emit Q_LOAD_GLOBAL */
      uint32_t rd = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(rd), q_imm(idx), q_none()));
      return (int)rd;
    }
    /* Local variable - vreg is in idx */
    return (int)idx;
  }

  case AST_BINOP: {
    if (expr->child_count < 2) {
      lower_error(ctx, expr, "binop needs 2 operands");
      return -1;
    }
    int lhs = lower_expr(ctx, expr->children[0]);
    int rhs = lower_expr(ctx, expr->children[1]);
    if (lhs < 0 || rhs < 0)
      return -1;

    /* OP_POW (8.2): synthesize via repeated multiplication loop
     *     rd = 1; i = 0
     * loop:
     *     if i >= rhs goto end
     *     rd = rd * lhs
     *     i = i + 1
     *     goto loop
     * end:
     */
    if (expr->op == OP_POW) {
      uint32_t rd = fresh_vreg(ctx);
      uint32_t one = fresh_vreg(ctx);
      uint32_t ic = fresh_vreg(ctx);
      uint32_t cond = fresh_vreg(ctx);
      uint32_t loop_label = fresh_label(ctx);
      uint32_t end_label = fresh_label(ctx);

      emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(1), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(ic), q_imm(0), q_none()));

      q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
      lbl.patch_id = loop_label;
      emit(ctx, lbl);

      emit(ctx,
           q_instr(Q_CMP_LT, q_vreg(cond), q_vreg(ic), q_vreg((uint32_t)rhs)));
      emit(ctx,
           q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(cond), q_label(end_label)));
      emit(ctx, q_instr(Q_MUL, q_vreg(rd), q_vreg(rd), q_vreg((uint32_t)lhs)));
      emit(ctx, q_instr(Q_ADD, q_vreg(ic), q_vreg(ic), q_vreg(one)));
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(loop_label), q_none()));

      lbl.patch_id = end_label;
      emit(ctx, lbl);
      return (int)rd;
    }

    uint32_t rd = fresh_vreg(ctx);
    q_opcode_t op;

    /* Check if this is string concatenation (OP_ADD with string operands) */
    if (expr->op == OP_ADD && expr->child_count >= 2) {
      const ast_node_t *left = expr->children[0];
      const ast_node_t *right = expr->children[1];
      int is_string_concat = 0;

      /* Check if either operand is a string */
      if (left->type == AST_LITERAL_STR || right->type == AST_LITERAL_STR) {
        is_string_concat = 1;
      } else {
        /* Check if variables are strings */
        if (left->type == AST_IDENTIFIER) {
          symbol_entry_t *ent = NULL;
          if (sym_lookup_entry_both(ctx, left->name, &ent, NULL) >= 0 && ent) {
            if (ent->type == VIR_TYPE_PTR) {
              is_string_concat = 1;
            }
          }
        }
        if (!is_string_concat && right->type == AST_IDENTIFIER) {
          symbol_entry_t *ent = NULL;
          if (sym_lookup_entry_both(ctx, right->name, &ent, NULL) >= 0 && ent) {
            if (ent->type == VIR_TYPE_PTR) {
              is_string_concat = 1;
            }
          }
        }
      }

      if (is_string_concat) {
        /* Emit Q_STR_CAT for string concatenation */
        emit(ctx, q_instr(Q_STR_CAT, q_vreg(rd), q_vreg((uint32_t)lhs),
                          q_vreg((uint32_t)rhs)));
        return (int)rd;
      }
    }

    switch (expr->op) {
    case OP_ADD:
      op = Q_ADD;
      break;
    case OP_SUB:
      op = Q_SUB;
      break;
    case OP_MUL:
      op = Q_MUL;
      break;
    case OP_DIV:
      op = Q_DIV;
      break;
    case OP_MOD:
      op = Q_MOD;
      break;
    case OP_AND:
      op = Q_AND;
      break;
    case OP_OR:
      op = Q_OR;
      break;
    case OP_XOR:
      op = Q_XOR;
      break;
    case OP_SHL:
      op = Q_SHL;
      break;
    case OP_SHR:
      op = Q_SHR;
      break;
    /* §26.2 AI operators: runtime-dispatched via Q_TENSOR_MUL/FMA.
     * If both operands are array handles → element-wise loop in VM;
     * else → scalar multiply fallback. */
    case OP_MATMUL:
      op = Q_TENSOR_MUL;
      break; /* a ** b */
    case OP_FMA:
      op = Q_TENSOR_FMA;
      break; /* a >< b */
    default:
      lower_error(ctx, expr, "unsupported binop");
      return -1;
    }
    emit(ctx,
         q_instr(op, q_vreg(rd), q_vreg((uint32_t)lhs), q_vreg((uint32_t)rhs)));
    return (int)rd;
  }

  case AST_COMPARE: {
    if (expr->child_count < 2) {
      lower_error(ctx, expr, "compare needs 2 operands");
      return -1;
    }
    int lhs = lower_expr(ctx, expr->children[0]);
    int rhs = lower_expr(ctx, expr->children[1]);
    if (lhs < 0 || rhs < 0)
      return -1;

    uint32_t rd = fresh_vreg(ctx);
    q_opcode_t op;
    switch (expr->op) {
    case OP_EQ:
      op = Q_CMP_EQ;
      break;
    case OP_NE: {
      uint32_t eq = fresh_vreg(ctx);
      uint32_t one = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                        q_vreg((uint32_t)rhs)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
      emit(ctx, q_instr(Q_XOR, q_vreg(rd), q_vreg(eq), q_vreg(one)));
      return (int)rd;
    }
    case OP_GT:
      op = Q_CMP_GT;
      break;
    case OP_LT:
      op = Q_CMP_LT;
      break;
    case OP_GE:
      op = Q_CMP_GE;
      break;
    case OP_LE:
      op = Q_CMP_LE;
      break;
    /* 8.4 Safe equality: both operands must be non-nil (truthy) AND equal */
    case OP_SAFE_EQ: {
      uint32_t eq = fresh_vreg(ctx);
      uint32_t zero = fresh_vreg(ctx);
      uint32_t la = fresh_vreg(ctx);
      uint32_t lb = fresh_vreg(ctx);
      uint32_t t1 = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                        q_vreg((uint32_t)rhs)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
      emit(ctx,
           q_instr(Q_CMP_GT, q_vreg(la), q_vreg((uint32_t)lhs), q_vreg(zero)));
      emit(ctx,
           q_instr(Q_CMP_GT, q_vreg(lb), q_vreg((uint32_t)rhs), q_vreg(zero)));
      emit(ctx, q_instr(Q_AND, q_vreg(t1), q_vreg(la), q_vreg(lb)));
      emit(ctx, q_instr(Q_AND, q_vreg(rd), q_vreg(t1), q_vreg(eq)));
      return (int)rd;
    }
    case OP_SAFE_NE: {
      uint32_t eq = fresh_vreg(ctx);
      uint32_t zero = fresh_vreg(ctx);
      uint32_t la = fresh_vreg(ctx);
      uint32_t lb = fresh_vreg(ctx);
      uint32_t one = fresh_vreg(ctx);
      uint32_t neq = fresh_vreg(ctx);
      uint32_t t1 = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                        q_vreg((uint32_t)rhs)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
      emit(ctx, q_instr(Q_XOR, q_vreg(neq), q_vreg(eq), q_vreg(one)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
      emit(ctx,
           q_instr(Q_CMP_GT, q_vreg(la), q_vreg((uint32_t)lhs), q_vreg(zero)));
      emit(ctx,
           q_instr(Q_CMP_GT, q_vreg(lb), q_vreg((uint32_t)rhs), q_vreg(zero)));
      emit(ctx, q_instr(Q_AND, q_vreg(t1), q_vreg(la), q_vreg(lb)));
      emit(ctx, q_instr(Q_AND, q_vreg(rd), q_vreg(t1), q_vreg(neq)));
      return (int)rd;
    }
    default:
      lower_error(ctx, expr, "unsupported comparison");
      return -1;
    }
    emit(ctx,
         q_instr(op, q_vreg(rd), q_vreg((uint32_t)lhs), q_vreg((uint32_t)rhs)));
    return (int)rd;
  }

  case AST_CALL: {
    /* Function call: evaluate args, put in R0..Rn, call, result in R0 */
    int fidx = find_func_index(ctx, expr->name);
    /* Empty extern stubs (body_count==0) for soft/native_* names must not
     * become Q_CALL_FUNC no-ops — e.g. native_file_open would leave R0
     * unchanged instead of emitting Q_FILE_OPEN. Prefer the soft handlers. */
    if (fidx >= 0 && ctx->module.functions[fidx].body_count == 0 &&
        is_soft_call_name(expr->name))
      fidx = -1;
    if (fidx < 0) {
      /* §11.4 bước 2 — Callable field fallback.
       * UFCS rewrite produced AST_CALL with children[0] = receiver.
       * If no free function `name` exists but some record type has a
       * field named `name`, treat this as `receiver.name(args)` where
       * `receiver.name` holds a function index (callable field). */
      if (expr->child_count >= 1) {
        int field_off =
            record_field_offset_for_expr(ctx, expr->children[0], expr->name,
                                         NULL);
        if (field_off >= 0) {
          /* Lower receiver and load function index from field. */
          int base = lower_expr(ctx, expr->children[0]);
          if (base < 0)
            return -1;
          uint32_t off_r = fresh_vreg(ctx);
          uint32_t fn_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)field_off),
                            q_none()));
          emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(fn_r), q_vreg((uint32_t)base),
                            q_vreg(off_r)));

          /* Args are children[1..n] (receiver is NOT passed). */
          uint32_t nargs = expr->child_count - 1;
          int arg_vregs[Q_MAX_PARAMS] = {0};
          for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
            int av = lower_expr(ctx, expr->children[i + 1]);
            if (av < 0)
              return -1;
            arg_vregs[i] = av;
          }
          for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
            emit(ctx, q_instr(Q_MOVE, q_vreg(i), q_vreg((uint32_t)arg_vregs[i]),
                              q_none()));
          }
          emit(ctx, q_instr(Q_CALL_INDIRECT, q_none(), q_vreg(fn_r), q_none()));
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_MOVE, q_vreg(rd), q_vreg(0), q_none()));
          return (int)rd;
        }
      }
      /* §7: Record/entity construction via parens —
       * `TypeName(field: val, ...)` desugars to record literal. */
      {
        record_type_t *rt = find_record_type(ctx, expr->name);
        if (rt) {
          /* Enum variant records (Ok/Err/Some/None…): layout is
           *   [0]=tag discriminant, [8]=payload
           * so `Ok(x)` stores tag then x — matching case-arm binding. */
          int64_t variant_tag = -1;
          for (uint32_t ei = 0; ei < ctx->enum_type_count; ei++) {
            int64_t v = enum_lookup_variant(&ctx->enum_types[ei], expr->name);
            if (v >= 0) {
              variant_tag = v;
              break;
            }
          }
          if (variant_tag >= 0 && rt->field_count >= 2 &&
              strcmp(rt->fields[0].name, "tag") == 0) {
            uint32_t sz_r = fresh_vreg(ctx);
            uint32_t ptr_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(sz_r), q_imm(16), q_none()));
            emit(ctx, q_instr(Q_ALLOC, q_vreg(ptr_r), q_vreg(sz_r), q_none()));
            uint32_t tag_r = fresh_vreg(ctx);
            uint32_t off0 = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(tag_r), q_imm(variant_tag),
                              q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(off0), q_imm(0), q_none()));
            emit(ctx, q_instr(Q_STORE_WORD, q_vreg(tag_r), q_vreg(ptr_r),
                              q_vreg(off0)));
            if (expr->child_count > 0) {
              const ast_node_t *payload = expr->children[0];
              if (payload && payload->type == AST_NAMED_ARG &&
                  payload->child_count > 0)
                payload = payload->children[0];
              if (payload) {
                int val = lower_expr(ctx, payload);
                if (val >= 0) {
                  uint32_t off8 = fresh_vreg(ctx);
                  emit(ctx, q_instr(Q_LOAD, q_vreg(off8), q_imm(8), q_none()));
                  emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                                    q_vreg(ptr_r), q_vreg(off8)));
                }
              }
            }
            return (int)ptr_r;
          }
          /* Allocate field_count * 8 bytes */
          uint32_t sz_r = fresh_vreg(ctx);
          uint32_t ptr_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(sz_r),
                            q_imm((int64_t)rt->field_count * 8), q_none()));
          emit(ctx, q_instr(Q_ALLOC, q_vreg(ptr_r), q_vreg(sz_r), q_none()));
          /* Store each child:
           *   AST_NAMED_ARG → use name → field offset
           *   positional    → use index as field index */
          for (uint32_t i = 0; i < expr->child_count; i++) {
            const ast_node_t *child = expr->children[i];
            if (!child)
              continue;
            int field_off = -1;
            const ast_node_t *value_node = child;
            if (child->type == AST_NAMED_ARG) {
              field_off = record_field_offset(rt, child->name);
              if (field_off < 0) {
                if (lowering_strict_fields()) {
                  char buf[128];
                  snprintf(buf, sizeof(buf), "unknown field: %s.%s",
                           expr->name, child->name);
                  lower_error(ctx, expr, buf);
                }
                continue;
              }
              value_node = (child->child_count > 0) ? child->children[0] : NULL;
            } else {
              if (i < rt->field_count)
                field_off = (int)(i * 8);
            }
            if (!value_node || field_off < 0)
              continue;
            int val = lower_expr(ctx, value_node);
            if (val < 0)
              continue;
            uint32_t off_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)field_off),
                              q_none()));
            emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                              q_vreg(ptr_r), q_vreg(off_r)));
          }
          return (int)ptr_r;
        }
      }
      if (is_soft_call_name(expr->name)) {
        if (strcmp(expr->name, "native_str_byte_len") == 0 && expr->child_count >= 1) {
          int a0 = lower_expr(ctx, expr->children[0]);
          if (a0 < 0) return -1;
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_STR_LEN, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_str_ptr") == 0 && expr->child_count >= 1) {
          return lower_expr(ctx, expr->children[0]);
        }
        if ((strcmp(expr->name, "native_memcpy") == 0 ||
             strcmp(expr->name, "native_memmove") == 0 ||
             strcmp(expr->name, "native_mem_copy") == 0) &&
            expr->child_count >= 3) {
          int dst = lower_expr(ctx, expr->children[0]);
          int src = lower_expr(ctx, expr->children[1]);
          int len = lower_expr(ctx, expr->children[2]);
          if (dst < 0 || src < 0 || len < 0) return -1;
          emit(ctx, q_instr(Q_MEM_COPY, q_vreg((uint32_t)dst),
                            q_vreg((uint32_t)src), q_vreg((uint32_t)len)));
          return dst;
        }
        if (strcmp(expr->name, "native_memset") == 0 && expr->child_count >= 3) {
          int dst = lower_expr(ctx, expr->children[0]);
          int val = lower_expr(ctx, expr->children[1]);
          int len = lower_expr(ctx, expr->children[2]);
          if (dst < 0 || val < 0 || len < 0) return -1;
          emit(ctx, q_instr(Q_MEM_SET, q_vreg((uint32_t)dst),
                            q_vreg((uint32_t)val), q_vreg((uint32_t)len)));
          return dst;
        }
        if ((strcmp(expr->name, "native_malloc") == 0 ||
             strcmp(expr->name, "alloc_zeroed") == 0) &&
            expr->child_count >= 1) {
          int size = lower_expr(ctx, expr->children[0]);
          if (size < 0) return -1;
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_ALLOC, q_vreg(rd), q_vreg((uint32_t)size), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_calloc") == 0 && expr->child_count >= 2) {
          int count = lower_expr(ctx, expr->children[0]);
          int size = lower_expr(ctx, expr->children[1]);
          if (count < 0 || size < 0) return -1;
          uint32_t bytes = fresh_vreg(ctx);
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_MUL, q_vreg(bytes), q_vreg((uint32_t)count),
                            q_vreg((uint32_t)size)));
          emit(ctx, q_instr(Q_ALLOC, q_vreg(rd), q_vreg(bytes), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_free") == 0 ||
            strcmp(expr->name, "free") == 0) {
          if (expr->child_count >= 1) {
            int ptr = lower_expr(ctx, expr->children[0]);
            if (ptr < 0) return -1;
            emit(ctx, q_instr(Q_FREE, q_none(), q_vreg((uint32_t)ptr), q_none()));
          }
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_load_u8") == 0 && expr->child_count >= 2) {
          int base = lower_expr(ctx, expr->children[0]);
          int off = lower_expr(ctx, expr->children[1]);
          if (base < 0 || off < 0) return -1;
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD_BYTE, q_vreg(rd), q_vreg((uint32_t)base),
                            q_vreg((uint32_t)off)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_store_u8") == 0 && expr->child_count >= 3) {
          int base = lower_expr(ctx, expr->children[0]);
          int off = lower_expr(ctx, expr->children[1]);
          int val = lower_expr(ctx, expr->children[2]);
          if (base < 0 || off < 0 || val < 0) return -1;
          emit(ctx, q_instr(Q_STORE_BYTE, q_vreg((uint32_t)val),
                            q_vreg((uint32_t)base), q_vreg((uint32_t)off)));
          return val;
        }
        /* stdlib file.vri: native_file_open(data, len, FileMode) → Q_FILE_OPEN.
         * Path bytes are treated as a C string (callers pass null-terminated
         * data from get_arg / str_from_cstr). FileMode ints are accepted by VM. */
        if (strcmp(expr->name, "native_file_open") == 0 &&
            expr->child_count >= 2) {
          int data = lower_expr(ctx, expr->children[0]);
          int mode = -1;
          if (expr->child_count >= 3)
            mode = lower_expr(ctx, expr->children[2]);
          else
            mode = lower_expr(ctx, expr->children[1]);
          if (data < 0 || mode < 0)
            return -1;
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_FILE_OPEN, q_vreg(rd), q_vreg((uint32_t)data),
                            q_vreg((uint32_t)mode)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_file_close") == 0 &&
            expr->child_count >= 1) {
          int fd = lower_expr(ctx, expr->children[0]);
          if (fd < 0)
            return -1;
          emit(ctx,
               q_instr(Q_FILE_CLOSE, q_none(), q_vreg((uint32_t)fd), q_none()));
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_file_read") == 0 &&
            expr->child_count >= 3) {
          /* fread into caller buffer; return byte count via intrinsic-style
           * soft path: reuse Q_FILE_READ only for whole-file reads. For the
           * buffered API, emit a host call through sys_read when fd is int,
           * else fopen FILE* via a small inline sequence is not available —
           * map FILE* read to fread through Q_INTRINSIC sys_read is wrong.
           * Use soft: allocate result via FILE_READ when buf is ignored… */
          int fd = lower_expr(ctx, expr->children[0]);
          int buf = lower_expr(ctx, expr->children[1]);
          int len = lower_expr(ctx, expr->children[2]);
          if (fd < 0 || buf < 0 || len < 0)
            return -1;
          /* Move args into R0..R2 and dispatch VIR_INTR_SYS_READ-like host
           * fread via intrinsic ID — registered as native_file_read name
           * table entry; emit Q_INTRINSIC with id matching table slot 32. */
          emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)fd), q_none()));
          emit(ctx, q_instr(Q_MOVE, q_vreg(1), q_vreg((uint32_t)buf), q_none()));
          emit(ctx, q_instr(Q_MOVE, q_vreg(2), q_vreg((uint32_t)len), q_none()));
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd), q_imm(33), q_imm(3)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_file_write") == 0 &&
            expr->child_count >= 3) {
          int fd = lower_expr(ctx, expr->children[0]);
          int buf = lower_expr(ctx, expr->children[1]);
          int len = lower_expr(ctx, expr->children[2]);
          if (fd < 0 || buf < 0 || len < 0)
            return -1;
          emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)fd), q_none()));
          emit(ctx, q_instr(Q_MOVE, q_vreg(1), q_vreg((uint32_t)buf), q_none()));
          emit(ctx, q_instr(Q_MOVE, q_vreg(2), q_vreg((uint32_t)len), q_none()));
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd), q_imm(34), q_imm(3)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_errno") == 0) {
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd), q_imm(35), q_imm(0)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_load") == 0 && expr->child_count >= 2) {
          int base = lower_expr(ctx, expr->children[0]);
          int off = lower_expr(ctx, expr->children[1]);
          if (base < 0 || off < 0) return -1;
          uint32_t byte_off = fresh_vreg(ctx);
          uint32_t word_size = fresh_vreg(ctx);
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(word_size), q_imm(8), q_none()));
          emit(ctx, q_instr(Q_MUL, q_vreg(byte_off), q_vreg((uint32_t)off),
                            q_vreg(word_size)));
          emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)base),
                            q_vreg(byte_off)));
          return (int)rd;
        }
        if (strcmp(expr->name, "native_store") == 0 && expr->child_count >= 3) {
          int base = lower_expr(ctx, expr->children[0]);
          int off = lower_expr(ctx, expr->children[1]);
          int val = lower_expr(ctx, expr->children[2]);
          if (base < 0 || off < 0 || val < 0) return -1;
          uint32_t byte_off = fresh_vreg(ctx);
          uint32_t word_size = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(word_size), q_imm(8), q_none()));
          emit(ctx, q_instr(Q_MUL, q_vreg(byte_off), q_vreg((uint32_t)off),
                            q_vreg(word_size)));
          emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                            q_vreg((uint32_t)base), q_vreg(byte_off)));
          return val;
        }
        if ((strcmp(expr->name, "_next_pow2") == 0 ||
             strcmp(expr->name, "float_to_bits") == 0) &&
            expr->child_count >= 1) {
          return lower_expr(ctx, expr->children[0]);
        }
        if ((strcmp(expr->name, "str_from_i64") == 0 ||
             strcmp(expr->name, "to_string") == 0) &&
            expr->child_count >= 1) {
          int val = lower_expr(ctx, expr->children[0]);
          if (val < 0) return -1;
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_I_TO_STR, q_vreg(rd), q_vreg((uint32_t)val), q_none()));
          return (int)rd;
        }
        if (strcmp(expr->name, "size_of") == 0) {
          uint32_t rd = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(8), q_none()));
          return (int)rd;
        }
        for (uint32_t i = 0; i < expr->child_count; i++)
          (void)lower_expr(ctx, expr->children[i]);
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      /* Truly undefined. */
      char buf[128];
      snprintf(buf, sizeof(buf), "undefined function: %s", expr->name);
      lower_error(ctx, expr, buf);
      uint32_t rd = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      return (int)rd;
    }

    /* Evaluate arguments and move to R0..Rn */
    uint32_t nargs = expr->child_count;
    int arg_vregs[Q_MAX_PARAMS] = {0};
    const ast_node_t *arg_nodes[Q_MAX_PARAMS] = {0};
    /* §6.4 Named args: if any child is AST_NAMED_ARG, reorder by
     * matching against the target function's parameter names. */
    int has_named = 0;
    for (uint32_t i = 0; i < nargs; i++) {
      if (expr->children[i] && expr->children[i]->type == AST_NAMED_ARG) {
        has_named = 1;
        break;
      }
    }
    if (has_named) {
      q_function_t *tgt = &ctx->module.functions[fidx];
      int slot_filled[Q_MAX_PARAMS] = {0};
      int named_started = 0;
      uint32_t positional = 0;
      for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
        const ast_node_t *child = expr->children[i];
        if (child && child->type == AST_NAMED_ARG) {
          named_started = 1;
          /* Value expression is children[0]. */
          int av = (child->child_count > 0)
                       ? lower_expr(ctx, child->children[0])
                       : -1;
          if (av < 0)
            return -1;
          /* Find matching parameter. */
          int slot = -1;
          for (uint32_t p = 0; p < tgt->param_count; p++) {
            if (strcmp(tgt->param_names[p], child->name) == 0) {
              slot = (int)p;
              break;
            }
          }
          if (slot < 0 || slot_filled[slot]) {
            char buf[128];
            snprintf(buf, sizeof(buf), "unknown or duplicate named arg '%s'",
                     child->name);
            lower_error(ctx, expr, buf);
            slot = (int)i;
          }
          arg_vregs[slot] = av;
          arg_nodes[slot] = child->children[0];
          slot_filled[slot] = 1;
        } else {
          if (named_started) {
            lower_error(ctx, expr, "positional arg after named arg is not allowed");
          }
          int av = lower_expr(ctx, child);
          if (av < 0)
            return -1;
          arg_vregs[positional] = av;
          arg_nodes[positional] = child;
          slot_filled[positional] = 1;
          positional++;
        }
      }
      /* Fill unfilled slots with 0 (no default values yet). */
      for (uint32_t p = 0; p < tgt->param_count && p < Q_MAX_PARAMS; p++) {
        if (!slot_filled[p]) {
          uint32_t z = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(z), q_imm(0), q_none()));
          arg_vregs[p] = (int)z;
          arg_nodes[p] = NULL;
        }
      }
      nargs = tgt->param_count;
    } else {
      q_function_t *tgt = &ctx->module.functions[fidx];
      for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
        int av = lower_expr(ctx, expr->children[i]);
        if (av < 0)
          return -1;
        arg_vregs[i] = av;
        arg_nodes[i] = expr->children[i];
      }
    }
    /* §4.8: pass-by-value of a bare move-type identifier consumes it.
     * Borrowed args (`&x`, `&mut x`) do NOT consume. */
    for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
      q_function_t *tgt = &ctx->module.functions[fidx];
      if (i < tgt->param_count && tgt->param_is_ref[i])
        continue;
      ownership_mark_moved_if_id(ctx, arg_nodes[i]);
    }
    /* Move to R0..R(n-1) */
    for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
      emit(ctx, q_instr(Q_MOVE, q_vreg(i), q_vreg((uint32_t)arg_vregs[i]),
                        q_none()));
    }
    /* Explicit ref-binding ABI: clear staged bindings, then publish one
     * binding per `ref` parameter for the VM to consume at call time. */
    {
      q_function_t *tgt = &ctx->module.functions[fidx];
      int has_ref = 0;
      for (uint32_t i = 0; i < tgt->param_count && i < Q_MAX_PARAMS; i++) {
        if (tgt->param_is_ref[i]) {
          has_ref = 1;
          break;
        }
      }
      if (has_ref) {
        emit(ctx, q_instr(Q_REF_BIND_CLEAR, q_none(), q_none(), q_none()));
      }
      for (uint32_t i = 0; i < tgt->param_count && i < Q_MAX_PARAMS; i++) {
        if (!tgt->param_is_ref[i])
          continue;
        int64_t binding = lower_ref_binding(ctx, arg_nodes[i]);
        if (binding == 0) {
          char buf[160];
          snprintf(buf, sizeof(buf),
                   "ref arg for param '%s' must be a variable",
                   tgt->param_names[i]);
          lower_error(ctx, expr, buf);
        }
        emit(ctx, q_instr(Q_REF_BIND_SET, q_imm((int64_t)i), q_imm(binding),
                          q_none()));
      }
    }

    /* Emit call */
    emit(ctx,
         q_instr(Q_CALL_FUNC, q_none(), q_func_idx((uint32_t)fidx), q_none()));

    /* Result is in R0, copy to fresh vreg */
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_MOVE, q_vreg(rd), q_vreg(0), q_none()));
    return (int)rd;
  }

  case AST_INPUT: {
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_INPUT, q_vreg(rd), q_none(), q_none()));
    return (int)rd;
  }

  case AST_LITERAL_STR: {
    /* Check if string contains interpolation markers (\x01...\x02) */
    const char *str = expr->name;
    int has_interpolation = 0;
    for (const char *p = str; *p; p++) {
      if (*p == '\x01') {
        has_interpolation = 1;
        break;
      }
    }

    if (!has_interpolation) {
      /* Simple string literal - no interpolation */
      uint32_t str_idx = q_module_add_string(&ctx->module, expr->name);
      uint32_t r = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_str(str_idx), q_none()));
      return (int)r;
    }

    /* String with interpolation - expand into concatenation */
    uint32_t result_r = 0;
    int first_part = 1;
    const char *p = str;
    char buf[TOK_STR_MAX];
    int buf_len = 0;

    while (*p) {
      if (*p == '\x01') {
        /* Start of interpolation */
        /* First, emit the literal part before interpolation (if any) */
        if (buf_len > 0) {
          buf[buf_len] = '\0';
          uint32_t lit_idx = q_module_add_string(&ctx->module, buf);
          uint32_t lit_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(lit_r), q_str(lit_idx), q_none()));

          if (first_part) {
            result_r = lit_r;
            first_part = 0;
          } else {
            uint32_t new_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_STR_CAT, q_vreg(new_r), q_vreg(result_r),
                              q_vreg(lit_r)));
            result_r = new_r;
          }
          buf_len = 0;
        }

        /* Extract variable name */
        p++; /* skip \x01 */
        char var_name[TOK_STR_MAX];
        int var_len = 0;
        while (*p && *p != '\x02' && var_len < TOK_STR_MAX - 1) {
          var_name[var_len++] = *p++;
        }
        var_name[var_len] = '\0';

        if (*p == '\x02')
          p++; /* skip \x02 */

        /* Look up the variable */
        symbol_entry_t *ent = NULL;
        int scope = sym_lookup_entry_both(ctx, var_name, &ent, NULL);
        if (scope < 0 || !ent) {
          lower_error(ctx, expr, "undefined variable in string interpolation");
          return -1;
        }

        uint32_t var_r = ent->vreg;

        /* Concatenate with result */
        if (first_part) {
          result_r = var_r;
          first_part = 0;
        } else {
          uint32_t new_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_STR_CAT, q_vreg(new_r), q_vreg(result_r),
                            q_vreg(var_r)));
          result_r = new_r;
        }
      } else {
        /* Regular character */
        if (buf_len < TOK_STR_MAX - 1) {
          buf[buf_len++] = *p;
        }
        p++;
      }
    }

    /* Emit any remaining literal part */
    if (buf_len > 0) {
      buf[buf_len] = '\0';
      uint32_t lit_idx = q_module_add_string(&ctx->module, buf);
      uint32_t lit_r = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD, q_vreg(lit_r), q_str(lit_idx), q_none()));

      if (first_part) {
        result_r = lit_r;
      } else {
        uint32_t new_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_STR_CAT, q_vreg(new_r), q_vreg(result_r),
                          q_vreg(lit_r)));
        result_r = new_r;
      }
    }

    return (int)result_r;
  }

  case AST_LITERAL_FLOAT: {
    /* Store as int64 bit pattern for now */
    uint32_t r = fresh_vreg(ctx);
    emit(ctx,
         q_instr(Q_LOAD, q_vreg(r), q_imm((int64_t)expr->float_val), q_none()));
    return (int)r;
  }

  
  case AST_TUPLE_LITERAL: {
    uint32_t cap_r = fresh_vreg(ctx);
    uint32_t arr_r = fresh_vreg(ctx);
    int64_t n = (int64_t)expr->child_count;
    int64_t cap = n < 16 ? 16 : n;
    emit(ctx, q_instr(Q_LOAD, q_vreg(cap_r), q_imm(cap), q_none()));
    emit(ctx, q_instr(Q_ARR_NEW, q_vreg(arr_r), q_vreg(cap_r), q_none()));
    for (uint32_t i = 0; i < expr->child_count; i++) {
      int elem = lower_expr(ctx, expr->children[i]);
      if (elem >= 0) {
        emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg(arr_r),
                          q_vreg((uint32_t)elem)));
      }
    }
    return (int)arr_r;
  }

  case AST_ARRAY_LITERAL: {
    uint32_t cap_r = fresh_vreg(ctx);
    uint32_t arr_r = fresh_vreg(ctx);
    int64_t n = (int64_t)expr->child_count;
    int64_t cap = n < 16 ? 16 : n;
    emit(ctx, q_instr(Q_LOAD, q_vreg(cap_r), q_imm(cap), q_none()));
    emit(ctx, q_instr(Q_ARR_NEW, q_vreg(arr_r), q_vreg(cap_r), q_none()));
    for (uint32_t i = 0; i < expr->child_count; i++) {
      int elem = lower_expr(ctx, expr->children[i]);
      if (elem >= 0) {
        emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg(arr_r),
                          q_vreg((uint32_t)elem)));
      }
    }
    return (int)arr_r;
  }

  case AST_MAP_LITERAL: {
    /* §20 Dict literal: [k:v, k:v, ...] — children come in alternating
     * key/value order.  Determine key kind from the first key (string
     * literal => Q_DICT_SET_S, otherwise Q_DICT_SET_I).  The symbol
     * table marker is set by the VAR_DECL site. */
    uint32_t dict_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_DICT_NEW, q_vreg(dict_r), q_none(), q_none()));
    int key_is_str = 0;
    if (expr->child_count >= 2 && expr->children[0] &&
        expr->children[0]->type == AST_LITERAL_STR) {
      key_is_str = 1;
    }
    for (uint32_t i = 0; i + 1 < expr->child_count; i += 2) {
      int kr = lower_expr(ctx, expr->children[i]);
      int vr = lower_expr(ctx, expr->children[i + 1]);
      if (kr < 0 || vr < 0)
        continue;
      emit(ctx,
           q_instr(key_is_str ? Q_DICT_SET_S : Q_DICT_SET_I,
                   q_vreg((uint32_t)vr), q_vreg(dict_r), q_vreg((uint32_t)kr)));
    }
    /* Stash the key kind on the ctx for the VAR_DECL post-hook via a
     * side-channel: piggyback on the expr itself by setting int_val.
     * (Caller inspects ast_node->type == AST_MAP_LITERAL and reads
     *  int_val to mark symbol.)  Safe: int_val otherwise unused here. */
    ((ast_node_t *)expr)->int_val = key_is_str ? 1 : 0;
    return (int)dict_r;
  }

  case AST_MAP_EXPR: {
    /* §20.2: map x [,idx] in iter: ... out expr ... end
     * Desugared to a runtime loop over the iterable array.  Produces
     * a new array.  Body statements are lowered in order; any
     * AST_RETURN (parser output of `out expr`) is retargeted to
     * Q_ARR_PUSH via ctx->in_map_expr. */
    if (expr->child_count < 1)
      return -1;
    /* Evaluate iterable into vreg. */
    int src = lower_expr(ctx, expr->children[0]);
    if (src < 0)
      return -1;

    /* Allocate result array. */
    uint32_t cap_r = fresh_vreg(ctx);
    uint32_t dst_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(cap_r), q_imm(16), q_none()));
    emit(ctx, q_instr(Q_ARR_NEW, q_vreg(dst_r), q_vreg(cap_r), q_none()));

    /* Length of source array. */
    uint32_t len_r = fresh_vreg(ctx);
    emit(ctx,
         q_instr(Q_ARR_LEN, q_vreg(len_r), q_vreg((uint32_t)src), q_none()));

    /* Loop counter init. */
    uint32_t i_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(i_r), q_imm(0), q_none()));

    uint32_t top_l = fresh_label(ctx);
    uint32_t end_l = fresh_label(ctx);

    q_instruction_t top_lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    top_lbl.patch_id = top_l;
    emit(ctx, top_lbl);

    /* if !(i < len) goto end */
    uint32_t cond_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_CMP_LT, q_vreg(cond_r), q_vreg(i_r), q_vreg(len_r)));
    emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(cond_r), q_label(end_l)));

    /* Scope: define element var (and optional idx/val). */
    symbol_table_t *saved = malloc(sizeof(*saved));
    if (!saved) {
      lower_error(ctx, expr, "out of memory saving map scope");
      return -1;
    }
    *saved = ctx->symbols;
    uint32_t elem_r = fresh_vreg(ctx);
    if (expr->name2[0]) {
      /* `map i, v in arr` — first name is index, second is value. */
      sym_define(&ctx->symbols, expr->name, i_r, VIR_TYPE_I64);
      sym_define(&ctx->symbols, expr->name2, elem_r, VIR_TYPE_I64);
    } else {
      sym_define(&ctx->symbols, expr->name, elem_r, VIR_TYPE_I64);
    }
    emit(ctx, q_instr(Q_ARR_GET, q_vreg(elem_r), q_vreg((uint32_t)src),
                      q_vreg(i_r)));

    /* Lower body with map context active. */
    uint32_t saved_arr = ctx->map_arr_vreg;
    uint8_t saved_in = ctx->in_map_expr;
    ctx->map_arr_vreg = dst_r;
    ctx->in_map_expr = 1;
    for (uint32_t bi = 1; bi < expr->child_count; bi++) {
      if (expr->children[bi])
        lower_stmt(ctx, expr->children[bi]);
    }
    ctx->map_arr_vreg = saved_arr;
    ctx->in_map_expr = saved_in;

    /* Restore scope */
    ctx->symbols = *saved;
    free(saved);

    /* i = i + 1 ; goto top */
    uint32_t one_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(one_r), q_imm(1), q_none()));
    emit(ctx, q_instr(Q_ADD, q_vreg(i_r), q_vreg(i_r), q_vreg(one_r)));
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(top_l), q_none()));

    q_instruction_t end_lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    end_lbl.patch_id = end_l;
    emit(ctx, end_lbl);

    return (int)dst_r;
  }

  case AST_INDEX_ACCESS: {
    uint32_t arr_vreg;
    uint32_t idx_child = 0;
    symbol_entry_t *ent = NULL;
    if (expr->name[0] == '\0') {
      if (expr->child_count < 2) {
        lower_error(ctx, expr, "index needs base and expr");
        return -1;
      }
      int base = lower_expr(ctx, expr->children[0]);
      if (base < 0)
        return -1;
      arr_vreg = (uint32_t)base;
      idx_child = 1;
    } else {
      uint32_t arr_idx;
      int arr_scope = sym_lookup_both(ctx, expr->name, &arr_idx);
      if (arr_scope < 0) {
        lower_error(ctx, expr, "undefined variable for index");
        return -1;
      }
      /* §4.8: use-after-move check */
      if (lowering_strict_ownership() &&
          sym_lookup_entry_both(ctx, expr->name, &ent, NULL) == 0 && ent &&
          ent->is_moved) {
        char buf[128];
        snprintf(buf, sizeof(buf), "use of moved value: '%s'", expr->name);
        diag_entry_t *e = lower_error(ctx, expr, buf);
        if (e && ent->moved_at_line > 0) {
          diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->moved_at_line, 1, 1), "value was moved here");
        }
        return -1;
      }
      if (arr_scope == 1) {
        /* Global array - load into vreg first */
        arr_vreg = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(arr_vreg), q_imm(arr_idx),
                          q_none()));
      } else {
        arr_vreg = arr_idx;
      }
    }
    if (expr->child_count <= idx_child) {
      lower_error(ctx, expr, "index needs expr");
      return -1;
    }
    int idx = lower_expr(ctx, expr->children[idx_child]);
    if (idx < 0)
      return -1;
    /* §26.1 tensor multi-index: t[i, j] → flat index i*cols + j */
    if (expr->child_count >= 2) {
      symbol_entry_t *tent = NULL;
      sym_lookup_entry_both(ctx, expr->name, &tent, NULL);
      if (tent && tent->is_tensor && tent->tensor_cols > 0) {
        /* flat = i * cols + j */
        int j = lower_expr(ctx, expr->children[1]);
        if (j < 0)
          return -1;
        uint32_t cols_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(cols_r),
                          q_imm((int64_t)tent->tensor_cols), q_none()));
        uint32_t row_off = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_MUL, q_vreg(row_off), q_vreg((uint32_t)idx),
                          q_vreg(cols_r)));
        uint32_t flat = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_ADD, q_vreg(flat), q_vreg(row_off),
                          q_vreg((uint32_t)j)));
        idx = (int)flat;
      }
    }
    uint32_t rd = fresh_vreg(ctx);
    /* §20 Dict get — dispatch on is_dict flag. */
    {
      symbol_entry_t *ent = NULL;
      if (expr->name[0] != '\0' &&
          sym_lookup_entry_both(ctx, expr->name, &ent, NULL) == 0 && ent &&
          ent->is_dict) {
        emit(ctx, q_instr(ent->dict_key_is_str ? Q_DICT_GET_S : Q_DICT_GET_I,
                          q_vreg(rd), q_vreg(arr_vreg), q_vreg((uint32_t)idx)));
        return (int)rd;
      }
    }
    emit(ctx, q_instr(Q_ARR_GET, q_vreg(rd), q_vreg(arr_vreg),
                      q_vreg((uint32_t)idx)));
    return (int)rd;
  }

  case AST_BUILTIN_CALL: {
    int bid = expr->builtin_id;
    uint32_t rd = fresh_vreg(ctx);
    int a0 = -1, a1 = -1, a2 = -1;
    if (expr->child_count > 0)
      a0 = lower_expr(ctx, expr->children[0]);
    if (expr->child_count > 1)
      a1 = lower_expr(ctx, expr->children[1]);
    if (expr->child_count > 2)
      a2 = lower_expr(ctx, expr->children[2]);
    switch (bid) {
    case BUILTIN_LEN:
      if (a0 >= 0) {
        /* §20 Dict length when arg is a dict symbol. */
        int is_dict_arg = 0;
        if (expr->child_count > 0 && expr->children[0] &&
            expr->children[0]->type == AST_IDENTIFIER) {
          symbol_entry_t *ent = NULL;
          if (sym_lookup_entry_both(ctx, expr->children[0]->name, &ent, NULL) ==
                  0 &&
              ent && ent->is_dict) {
            is_dict_arg = 1;
          }
        }
        emit(ctx, q_instr(is_dict_arg ? Q_DICT_LEN : Q_ARR_LEN, q_vreg(rd),
                          q_vreg((uint32_t)a0), q_none()));
      }
      break;
    case BUILTIN_PUSH:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_ALLOC:
      if (a0 >= 0)
        emit(ctx, q_instr(Q_ALLOC, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_FREE_MEM:
      if (a0 >= 0)
        emit(ctx, q_instr(Q_FREE, q_none(), q_vreg((uint32_t)a0), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_READ8:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_LOAD_BYTE, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_WRITE8:
      if (a0 >= 0 && a1 >= 0 && a2 >= 0)
        emit(ctx, q_instr(Q_STORE_BYTE, q_vreg((uint32_t)a2),
                          q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_READ64:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_WRITE64:
      if (a0 >= 0 && a1 >= 0 && a2 >= 0)
        emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)a2),
                          q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_STR_LEN:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_STR_LEN, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_STR_GET:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_STR_GET, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_STR_CAT:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_STR_CAT, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_STR_EQ:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_STR_EQ, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_FILE_OPEN:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FILE_OPEN, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_FILE_READ:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_FILE_READ, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_FILE_WRITE:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FILE_WRITE, q_none(), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_FILE_CLOSE:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_FILE_CLOSE, q_none(), q_vreg((uint32_t)a0), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_FILE_WRITE_BYTE:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FILE_WRITE_BYTE, q_none(), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_EXIT:
      if (a0 >= 0)
        emit(ctx, q_instr(Q_EXIT, q_none(), q_vreg((uint32_t)a0), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_I_TO_STR:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_I_TO_STR, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_STR_TO_I:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_STR_TO_I, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_ARR_NEW:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_ARR_NEW, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      else {
        uint32_t def = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(def), q_imm(16), q_none()));
        emit(ctx, q_instr(Q_ARR_NEW, q_vreg(rd), q_vreg(def), q_none()));
      }
      break;
    case BUILTIN_PRINT_STR:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_PRINT_STR, q_none(), q_vreg((uint32_t)a0), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_GET_ARG:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_GET_ARG, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_ARG_COUNT:
      emit(ctx, q_instr(Q_ARG_COUNT, q_vreg(rd), q_none(), q_none()));
      break;
    case BUILTIN_VOLATILE_READ:
      /* §16.3: volatile_read(addr) — unreordered MMIO/raw load. */
      if (a0 >= 0) {
        emit(ctx,
             q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)a0), q_imm(0)));
      } else {
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      }
      break;
    case BUILTIN_VOLATILE_WRITE:
      /* §16.3: volatile_write(addr, val) — unreordered MMIO/raw store. */
      if (a0 >= 0 && a1 >= 0) {
        emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)a1),
                          q_vreg((uint32_t)a0), q_imm(0)));
      }
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_HASH:
      /* §20.4: hash(v) — FNV-1a if string literal, splitmix64 otherwise. */
      if (a0 >= 0) {
        int is_str = (expr->child_count > 0 && expr->children[0] &&
                      expr->children[0]->type == AST_LITERAL_STR);
        emit(ctx, q_instr(is_str ? Q_HASH_S : Q_HASH_I, q_vreg(rd),
                          q_vreg((uint32_t)a0), q_none()));
      }
      break;
    case BUILTIN_KEYS:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_DICT_KEYS, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_VALUES:
      if (a0 >= 0)
        emit(ctx, q_instr(Q_DICT_VALUES, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_none()));
      break;
    case BUILTIN_QUANTIZE:
      /* §26.5: quantize(tensor, bits) — clip each element to signed int_N. */
      if (a0 >= 0) {
        int has_bits = (a1 >= 0);
        emit(ctx, q_instr(Q_QUANTIZE, q_vreg(rd), q_vreg((uint32_t)a0),
                          has_bits ? q_vreg((uint32_t)a1) : q_imm(8)));
      }
      break;
    /* §24.1 flux constructor — `flux(a, b, c, ...)` returns array. */
    case BUILTIN_FLUX_CTOR: {
      uint32_t n = expr->child_count;
      uint32_t cap_r = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD, q_vreg(cap_r), q_imm((int64_t)(n > 0 ? n : 1)),
                        q_none()));
      emit(ctx, q_instr(Q_ARR_NEW, q_vreg(rd), q_vreg(cap_r), q_none()));
      for (uint32_t i = 0; i < n; i++) {
        int v = lower_expr(ctx, expr->children[i]);
        if (v < 0)
          continue;
        emit(ctx,
             q_instr(Q_ARR_PUSH, q_none(), q_vreg(rd), q_vreg((uint32_t)v)));
      }
      break;
    }
    case BUILTIN_FLUX_DOT:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FLUX_DOT, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_FLUX_LEN:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_FLUX_LEN, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_FLUX_NORM:
      /* §24.1 flux_norm returns the Euclidean norm |v| (integer sqrt
       * of sum of squares). Uses Q_FLUX_NORM opcode which computes
       * isqrt(Σ v[i]²) — distinct from Q_FLUX_LEN (element count). */
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_FLUX_NORM, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_FLUX_SPLAT:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FLUX_SPLAT, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_FLUX_LOAD:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FLUX_LOAD, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_FLUX_STORE:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_FLUX_STORE, q_none(), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_TENSOR_SUM:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_TENSOR_SUM, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_ATOMIC_FENCE:
      emit(ctx, q_instr(Q_ATOMIC_FENCE, q_none(), q_none(), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_CAP:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_ARR_CAP, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_ARR_COMPACT:
      if (a0 >= 0)
        emit(ctx, q_instr(Q_ARR_COMPACT, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_none()));
      break;
    case BUILTIN_ARENA_NEW:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_ARENA_NEW, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_ARENA_ALLOC:
      if (a0 >= 0 && a1 >= 0)
        emit(ctx, q_instr(Q_ARENA_ALLOC, q_vreg(rd), q_vreg((uint32_t)a0),
                          q_vreg((uint32_t)a1)));
      break;
    case BUILTIN_ARENA_FREE:
      if (a0 >= 0)
        emit(ctx,
             q_instr(Q_ARENA_FREE, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
      break;
    case BUILTIN_YIELD:
      emit(ctx, q_instr(Q_TASK_YIELD, q_none(), q_none(), q_none()));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    case BUILTIN_ATOMIC_CAS: {
      /* atomic_cas(slot, old, new) — single-threaded VM: synthesise
       * via Q_ATOMIC_LOAD_GLOBAL + compare + conditional store.
       * Returns the previous value. First arg must reduce to an
       * imm global slot; fall back to treating it as a vreg when
       * not. */
      if (a0 < 0 || a1 < 0 || a2 < 0)
        break;
      /* Load current value from globals[slot]. */
      uint32_t cur = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_ATOMIC_LOAD_GLOBAL, q_vreg(cur), q_vreg((uint32_t)a0),
                        q_none()));
      /* dest = cur (we return previous value regardless of swap). */
      emit(ctx, q_instr(Q_MOVE, q_vreg(rd), q_vreg(cur), q_none()));
      /* Compare cur == old, conditional store. */
      uint32_t cmp = fresh_vreg(ctx);
      emit(ctx,
           q_instr(Q_CMP_EQ, q_vreg(cmp), q_vreg(cur), q_vreg((uint32_t)a1)));
      uint32_t skip = fresh_label(ctx);
      emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(cmp), q_label(skip)));
      emit(ctx, q_instr(Q_ATOMIC_STORE_GLOBAL, q_none(), q_vreg((uint32_t)a0),
                        q_vreg((uint32_t)a2)));
      q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
      lbl.patch_id = skip;
      emit(ctx, lbl);
      break;
    }
    /* ── §Phase-9 Intrinsic Registry cases ─────────────────
     * These emit Q_INTRINSIC(dest=rd, src1=INTR_ID, src2=argc).
     * Q_INTRINSIC reads args from vm->regs[0..argc-1], so we MOVE
     * each already-lowered arg vreg into R0..Rn before dispatch.
     * ────────────────────────────────────────────────────── */
    case BUILTIN_SYSCALL: {
      /* __syscall(num, a1..a6) — variadic up to 7 args.
       * a0/a1/a2 already lowered above; lower extra children[3..6]. */
      uint32_t argc = 0;
      int av_arr[7] = {a0, a1, a2, -1, -1, -1, -1};
      for (uint32_t ci = 3; ci < expr->child_count && ci < 7; ci++)
        av_arr[ci] = lower_expr(ctx, expr->children[ci]);
      for (uint32_t ci = 0; ci < expr->child_count && ci < 7; ci++) {
        if (av_arr[ci] >= 0) {
          emit(ctx, q_instr(Q_MOVE, q_vreg((int64_t)argc),
                            q_vreg((uint32_t)av_arr[ci]), q_none()));
          argc++;
        }
      }
      emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                        q_imm(VIR_INTR_SYSCALL), q_imm((int64_t)argc)));
      break;
    }
    case BUILTIN_MEMCPY: {
      if (a0 >= 0 && a1 >= 0 && a2 >= 0) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)a0), q_none()));
        emit(ctx, q_instr(Q_MOVE, q_vreg(1), q_vreg((uint32_t)a1), q_none()));
        emit(ctx, q_instr(Q_MOVE, q_vreg(2), q_vreg((uint32_t)a2), q_none()));
        emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                          q_imm(VIR_INTR_MEMCPY), q_imm(3)));
      } else {
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      }
      break;
    }
    case BUILTIN_MEMSET: {
      if (a0 >= 0 && a1 >= 0 && a2 >= 0) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)a0), q_none()));
        emit(ctx, q_instr(Q_MOVE, q_vreg(1), q_vreg((uint32_t)a1), q_none()));
        emit(ctx, q_instr(Q_MOVE, q_vreg(2), q_vreg((uint32_t)a2), q_none()));
        emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                          q_imm(VIR_INTR_MEMSET), q_imm(3)));
      } else {
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      }
      break;
    }
    case BUILTIN_TRAP:
    case BUILTIN_UNREACHABLE: {
      /* __trap() / __unreachable() — never returns; emit trap then
       * a fallthrough load so rd is defined for dead-code paths. */
      emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                        q_imm(VIR_INTR_TRAP), q_imm(0)));
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    }
    case BUILTIN_CLZ:
    case BUILTIN_CTZ:
    case BUILTIN_POPCNT:
    case BUILTIN_BSWAP:
    case BUILTIN_ATOMIC_LOAD: {
      if (a0 >= 0) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)a0), q_none()));
        int intr_id = VIR_INTR_CLZ;
        if (expr->builtin_id == BUILTIN_CTZ) intr_id = VIR_INTR_CTZ;
        else if (expr->builtin_id == BUILTIN_POPCNT) intr_id = VIR_INTR_POPCNT;
        else if (expr->builtin_id == BUILTIN_BSWAP) intr_id = VIR_INTR_BSWAP;
        else if (expr->builtin_id == BUILTIN_ATOMIC_LOAD) intr_id = VIR_INTR_ATOMIC_LOAD;
        emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                          q_imm(intr_id), q_imm(1)));
      } else {
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      }
      break;
    }
    case BUILTIN_ATOMIC_STORE:
    case BUILTIN_ATOMIC_ADD:
    case BUILTIN_ATOMIC_SUB: {
      if (a0 >= 0 && a1 >= 0) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(0), q_vreg((uint32_t)a0), q_none()));
        emit(ctx, q_instr(Q_MOVE, q_vreg(1), q_vreg((uint32_t)a1), q_none()));
        int intr_id = VIR_INTR_ATOMIC_STORE;
        if (expr->builtin_id == BUILTIN_ATOMIC_ADD) intr_id = VIR_INTR_ATOMIC_ADD;
        else if (expr->builtin_id == BUILTIN_ATOMIC_SUB) intr_id = VIR_INTR_ATOMIC_SUB;
        emit(ctx, q_instr(Q_INTRINSIC, q_vreg(rd),
                          q_imm(intr_id), q_imm(2)));
      } else {
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      }
      break;
    }
    default:
      emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
      break;
    }
    return (int)rd;
  }


  case AST_ENUM_ACCESS: {
    /* Compile-time constant lookup: EnumName.VARIANT → integer */
    enum_type_t *et = find_enum_type(ctx, expr->name);
    if (!et) {
      char buf[128];
      snprintf(buf, sizeof(buf), "undefined enum: %s", expr->name);
      lower_error(ctx, expr, buf);
      return -1;
    }
    int64_t val = enum_lookup_variant(et, expr->name2);
    if (val < 0) {
      char buf[128];
      snprintf(buf, sizeof(buf), "undefined enum variant: %s.%s", expr->name,
               expr->name2);
      lower_error(ctx, expr, buf);
      return -1;
    }
    uint32_t r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(val), q_none()));
    return (int)r;
  }

  case AST_RECORD_LITERAL: {
    /* Allocate heap block, store fields at offsets.
     * Each field is stored as an int64_t word.
     * name = record type name, children = field values
     * children[i]->name2 = field name */
    record_type_t *rt = find_record_type(ctx, expr->name); if (strcmp(expr->name, "VirFile") == 0) { printf("AST_RECORD_LITERAL VirFile: child_count=%d, rt->field_count=%d\n", expr->child_count, rt ? rt->field_count : -1); }
    if (!rt) {
      if (expr->name[0] == '\0') {
        uint32_t sz_r = fresh_vreg(ctx);
        uint32_t ptr_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(sz_r),
                          q_imm((int64_t)expr->child_count * 8), q_none()));
        emit(ctx, q_instr(Q_ALLOC, q_vreg(ptr_r), q_vreg(sz_r), q_none()));
        for (uint32_t i = 0; i < expr->child_count; i++) {
          const ast_node_t *child = expr->children[i];
          if (!child)
            continue;
          int val = lower_expr(ctx, child);
          if (val < 0)
            continue;
          uint32_t off_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)i * 8),
                            q_none()));
          emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                            q_vreg(ptr_r), q_vreg(off_r)));
        }
        return (int)ptr_r;
      }
      if (strcmp(expr->name, "string") == 0) {
        for (uint32_t i = 0; i < expr->child_count; i++)
          (void)lower_expr(ctx, expr->children[i]);
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      char buf[128];
      snprintf(buf, sizeof(buf), "undefined record: %s", expr->name);
      lower_error(ctx, expr, buf);
      return -1;
    }
    /* Allocate: size = field_count * 8 */
    uint32_t sz_r = fresh_vreg(ctx);
    uint32_t ptr_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(sz_r), q_imm((int64_t)rt->field_count * 8),
                      q_none()));
    emit(ctx, q_instr(Q_ALLOC, q_vreg(ptr_r), q_vreg(sz_r), q_none()));
    /* Store each field value at its offset */
    for (uint32_t i = 0; i < expr->child_count; i++) {
      const ast_node_t *child = expr->children[i];
      if (!child)
        continue;
      int field_off = record_field_offset(rt, child->name2);
      if (field_off < 0) {
        if (lowering_strict_fields()) {
          char buf[128];
          snprintf(buf, sizeof(buf), "unknown field: %s", child->name2);
          lower_error(ctx, expr, buf);
        }
        continue;
      }
      int val = lower_expr(ctx, child);
      if (val < 0)
        continue;
      uint32_t off_r = fresh_vreg(ctx);
      emit(ctx,
           q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)field_off), q_none()));
      emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val), q_vreg(ptr_r),
                        q_vreg(off_r)));
    }
    return (int)ptr_r;
  }

  case AST_FIELD_ACCESS: {
    /* children[0] = base expression, name = field/variant name.
     * Could be either: (a) enum access: EnumType.VARIANT
     *                  (b) record field access: var.field */
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "field access without target");
      return -1;
    }
    /* Check for enum access: child is an identifier matching an enum type */
    const ast_node_t *base_node = expr->children[0];
    if (base_node && base_node->type == AST_IDENTIFIER) {
      if (strcmp(base_node->name, "QOp") == 0) {
        int64_t val = 0;
        if (lookup_soft_qop_value(expr->name, &val)) {
          uint32_t r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(val), q_none()));
          return (int)r;
        }
      }
      enum_type_t *et = find_enum_type(ctx, base_node->name);
      if (et) {
        int64_t val = enum_lookup_variant(et, expr->name);
        if (val >= 0) {
          uint32_t r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(val), q_none()));
          return (int)r;
        }
        if (lowering_strict_fields()) {
          char buf[128];
          snprintf(buf, sizeof(buf), "unknown variant: %s.%s",
                   base_node->name, expr->name);
          lower_error(ctx, expr, buf);
          return -1;
        }
        return emit_soft_zero(ctx);
      }
      /* §16 register/mold field read: `var.field` → shift+mask. */
      symbol_entry_t *bent = NULL;
      if (sym_lookup_entry_both(ctx, base_node->name, &bent, NULL) >= 0 &&
          bent && bent->bit_type_name[0]) {
        bit_type_t *bt = find_bit_type(ctx, bent->bit_type_name);
        const bit_field_t *bf = find_bit_field(bt, expr->name);
        if (bt && bf) {
          int src = lower_expr(ctx, base_node);
          if (src < 0)
            return -1;
          return (int)emit_bit_extract(ctx, (uint32_t)src, bf->lo, bf->width);
        }
      }
    }
    /* Record field access */
    int base = lower_expr(ctx, expr->children[0]);
    if (base < 0)
      return -1;

    const record_type_t *resolved_rt = NULL;
    int offset =
        record_field_offset_for_expr(ctx, expr->children[0], expr->name,
                                     &resolved_rt);
    if (offset < 0) {
      if (lowering_strict_fields()) {
        char buf[128];
        if (resolved_rt)
          snprintf(buf, sizeof(buf), "unknown field: %s.%s",
                   resolved_rt->name, expr->name);
        else
          snprintf(buf, sizeof(buf), "unknown field: %s", expr->name);
        lower_error(ctx, expr, buf);
        return -1;
      }
      return emit_soft_zero(ctx);
    }
    uint32_t off_r = fresh_vreg(ctx);
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
    emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)base),
                      q_vreg(off_r)));
    return (int)rd;
  }

  /* 8.7 Safe access: base?.field → if base==0 then 0 else base.field */
  case AST_SAFE_ACCESS: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "safe access without target");
      return -1;
    }
    int base = lower_expr(ctx, expr->children[0]);
    if (base < 0)
      return -1;

    const record_type_t *resolved_rt = NULL;
    int offset =
        record_field_offset_for_expr(ctx, expr->children[0], expr->name,
                                     &resolved_rt);
    if (offset < 0) {
      if (lowering_strict_fields()) {
        char buf[128];
        if (resolved_rt)
          snprintf(buf, sizeof(buf), "unknown field: %s.%s",
                   resolved_rt->name, expr->name);
        else
          snprintf(buf, sizeof(buf), "unknown field: %s", expr->name);
        lower_error(ctx, expr, buf);
        return -1;
      }
      return emit_soft_zero(ctx);
    }

    uint32_t rd = fresh_vreg(ctx);
    uint32_t zero = fresh_vreg(ctx);
    uint32_t cond = fresh_vreg(ctx);
    uint32_t off_r = fresh_vreg(ctx);
    uint32_t nil_l = fresh_label(ctx);
    uint32_t end_l = fresh_label(ctx);

    emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
    emit(ctx,
         q_instr(Q_CMP_EQ, q_vreg(cond), q_vreg((uint32_t)base), q_vreg(zero)));
    emit(ctx, q_instr(Q_JUMP_IF, q_none(), q_vreg(cond), q_label(nil_l)));

    emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
    emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)base),
                      q_vreg(off_r)));
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_l), q_none()));

    q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    lbl.patch_id = nil_l;
    emit(ctx, lbl);
    emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));

    lbl.patch_id = end_l;
    emit(ctx, lbl);
    return (int)rd;
  }

  /* 8.8 Existence: expr? → 1 if expr != 0 else 0
   * §20:  dict ? key   → 1 if key exists in dict. */
  case AST_EXIST_CHECK: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "exist check without target");
      return -1;
    }
    /* Two-argument form: dict ? key. */
    if (expr->child_count >= 2 && expr->children[0] &&
        expr->children[0]->type == AST_IDENTIFIER) {
      symbol_entry_t *ent = NULL;
      if (sym_lookup_entry_both(ctx, expr->children[0]->name, &ent, NULL) ==
              0 &&
          ent && ent->is_dict) {
        int dr = lower_expr(ctx, expr->children[0]);
        int kr = lower_expr(ctx, expr->children[1]);
        if (dr < 0 || kr < 0)
          return -1;
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx,
             q_instr(ent->dict_key_is_str ? Q_DICT_HAS_S : Q_DICT_HAS_I,
                     q_vreg(rd), q_vreg((uint32_t)dr), q_vreg((uint32_t)kr)));
        return (int)rd;
      }
    }
    int v = lower_expr(ctx, expr->children[0]);
    if (v < 0)
      return -1;
    uint32_t zero = fresh_vreg(ctx);
    uint32_t eq = fresh_vreg(ctx);
    uint32_t one = fresh_vreg(ctx);
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
    emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)v), q_vreg(zero)));
    emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
    emit(ctx, q_instr(Q_XOR, q_vreg(rd), q_vreg(eq), q_vreg(one)));
    return (int)rd;
  }

  /* 8.10/8.11 Cast: for now pass through unchanged (int/float same repr) */
  case AST_CAST: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "cast without operand");
      return -1;
    }
    return lower_expr(ctx, expr->children[0]);
  }

  /* §8.9 Pattern match: expr :~ pattern
   *   - pattern is Ident matching a known type name: compile-time check
   *     against the LHS AST shape (literal int/float/str/array/record).
   *   - pattern is Ident matching a declared record/enum type name:
   *     evaluates to 1 if LHS is that record/enum, 0 otherwise (best
   *     effort, compile-time).
   *   - pattern is Ident referring to a variable: equality test on the
   *     identifier's value.
   *   - pattern is literal int/float/str: equality test.
   *   - otherwise: equality test on evaluated expression.
   */
  case AST_PATTERN_MATCH: {
    if (expr->child_count < 2) {
      lower_error(ctx, expr, "pattern match needs value and pattern");
      return -1;
    }
    const ast_node_t *lhs_ast = expr->children[0];
    const ast_node_t *pat = expr->children[1];
    if (pat && pat->type == AST_IDENTIFIER) {
      const char *tn = pat->name;
      /* First: if the identifier is a declared variable, treat this as
       * value equality rather than type check.  Variables shadow type
       * names (spec §10.5). */
      uint32_t dummy;
      int is_var = (sym_lookup_both(ctx, tn, &dummy) >= 0);
      if (!is_var) {
        /* Type-name pattern: compile-time check based on LHS shape. */
        int match = -1; /* -1 = unknown, 0/1 = determined */
        int lhs_kind = lhs_ast ? (int)lhs_ast->type : -1;

        /* Recognised primitive type names */
        int is_int_t = (strcmp(tn, "int") == 0 || strcmp(tn, "i8") == 0 ||
                        strcmp(tn, "i16") == 0 || strcmp(tn, "i32") == 0 ||
                        strcmp(tn, "i64") == 0 || strcmp(tn, "u8") == 0 ||
                        strcmp(tn, "u16") == 0 || strcmp(tn, "u32") == 0 ||
                        strcmp(tn, "u64") == 0);
        int is_float_t = (strcmp(tn, "float") == 0 || strcmp(tn, "f32") == 0 ||
                          strcmp(tn, "f64") == 0);
        int is_str_t = (strcmp(tn, "string") == 0 || strcmp(tn, "str") == 0);
        int is_bool_t = (strcmp(tn, "bool") == 0);
        int is_array_t = (strcmp(tn, "array") == 0);

        if (lhs_kind == AST_LITERAL_INT) {
          match = (is_int_t || is_bool_t) ? 1 : 0;
        } else if (lhs_kind == AST_LITERAL_FLOAT) {
          match = is_float_t ? 1 : 0;
        } else if (lhs_kind == AST_LITERAL_STR) {
          match = is_str_t ? 1 : 0;
        } else if (lhs_kind == AST_ARRAY_LITERAL) {
          match = is_array_t ? 1 : 0;
        } else if (lhs_kind == AST_RECORD_LITERAL && lhs_ast) {
          match = (strcmp(lhs_ast->name, tn) == 0) ? 1 : 0;
        } else if (is_int_t || is_float_t || is_str_t || is_bool_t ||
                   is_array_t) {
          /* Recognised primitive but LHS shape unknown: we can't
           * prove — stay conservative and return 0. */
          match = 0;
        }

        /* Still lower LHS for side effects (e.g. call expressions). */
        (void)lower_expr(ctx, lhs_ast);
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx,
             q_instr(Q_LOAD, q_vreg(rd), q_imm(match > 0 ? 1 : 0), q_none()));
        return (int)rd;
      }
      /* Fall through: identifier is a variable → value equality. */
    }
    int lhs = lower_expr(ctx, expr->children[0]);
    int rhs = lower_expr(ctx, expr->children[1]);
    if (lhs < 0 || rhs < 0)
      return -1;
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_CMP_EQ, q_vreg(rd), q_vreg((uint32_t)lhs),
                      q_vreg((uint32_t)rhs)));
    return (int)rd;
  }

  /* §24.4 Atomic load (lock expr / expr!!): real seq_cst load via
   * Q_ATOMIC_LOAD_GLOBAL when operand is a global identifier.
   * Otherwise fall through to regular expression evaluation. */
  case AST_ATOMIC_LOAD: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "atomic load without operand");
      return -1;
    }
    const ast_node_t *inner = expr->children[0];
    if (inner && inner->type == AST_IDENTIFIER) {
      uint32_t idx;
      int scope = sym_lookup_both(ctx, inner->name, &idx);
      if (scope == 1) {
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx,
             q_instr(Q_ATOMIC_LOAD_GLOBAL, q_vreg(rd), q_imm(idx), q_none()));
        return (int)rd;
      }
    }
    return lower_expr(ctx, inner);
  }

  /* §24.2 Swizzle (v~xyz / v~rgba): emit Q_SWIZZLE with channel string
   * in string table.  VM dispatches at runtime: array → reordered array,
   * scalar → passthrough. */
  case AST_SWIZZLE: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "swizzle without operand");
      return -1;
    }
    int v = lower_expr(ctx, expr->children[0]);
    if (v < 0)
      return -1;
    uint32_t chans_idx = q_module_add_string(&ctx->module, expr->name);
    uint32_t rd = fresh_vreg(ctx);
    q_operand_t chans_op;
    chans_op.type = OPERAND_STR;
    chans_op.str_idx = chans_idx;
    emit(ctx, q_instr(Q_SWIZZLE, q_vreg(rd), q_vreg((uint32_t)v), chans_op));
    return (int)rd;
  }

  /* §4.8 (2.10): shared/mutable borrow — &x / &mut x.
   *   – No runtime codegen effect: borrow is a static view of the value.
   *   – Purpose at lower time: run borrow-conflict check, and SUPPRESS
   *     the "use of moved value" check on the underlying identifier
   *     (borrowing does not consume).
   *   – Shared + mutable borrows on the same symbol within the same
   *     statement-level expression are rejected.
   *   – Multiple &mut on the same symbol are rejected.
   *   – The borrow counters live on the symbol entry and are reset
   *     between statements by lower_stmt (see below). */
  case AST_BORROW: {
    if (expr->child_count < 1) {
      lower_error(ctx, expr, "borrow without operand");
      return -1;
    }
    int is_mut = (expr->int_val != 0);
    const ast_node_t *tgt = expr->children[0];
    /* Borrow of an identifier — the common case. */
    if (tgt->type == AST_IDENTIFIER) {
      symbol_entry_t *ent = NULL;
      uint32_t idx = 0;
      int found = sym_lookup_entry_both(ctx, tgt->name, &ent, &idx);
      if (found < 0 || !ent) {
        char buf[128];
        snprintf(buf, sizeof(buf), "borrow of undefined: %s", tgt->name);
        lower_error(ctx, expr, buf);
        return -1;
      }
      if (ent->is_moved) {
        char buf[128];
        snprintf(buf, sizeof(buf), "borrow of moved value: '%s'", tgt->name);
        diag_entry_t *e = lower_error(ctx, expr, buf);
        if (e && ent->moved_at_line > 0) {
          diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->moved_at_line, 1, 1), "value was moved here");
        }
        return -1;
      }
      if (is_mut) {
        if (ent->borrow_shared_count > 0) {
          char buf[160];
          snprintf(buf, sizeof(buf),
                   "cannot borrow '%s' as mutable: already "
                   "borrowed as shared",
                   tgt->name);
          diag_entry_t *e = lower_error(ctx, expr, buf);
          if (e && ent->borrowed_at_line > 0) {
            diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->borrowed_at_line, 1, 1), "first borrow occurs here");
          }
          return -1;
        }
        if (ent->borrow_mut_count > 0) {
          char buf[160];
          snprintf(buf, sizeof(buf),
                   "cannot borrow '%s' as mutable more than once", tgt->name);
          diag_entry_t *e = lower_error(ctx, expr, buf);
          if (e && ent->borrowed_at_line > 0) {
            diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->borrowed_at_line, 1, 1), "first mutable borrow occurs here");
          }
          return -1;
        }
        ent->borrow_mut_count++;
        ent->borrowed_at_line = tgt->line;
      } else {
        if (ent->borrow_mut_count > 0) {
          char buf[160];
          snprintf(buf, sizeof(buf),
                   "cannot borrow '%s' as shared: already "
                   "borrowed as mutable",
                   tgt->name);
          diag_entry_t *e = lower_error(ctx, expr, buf);
          if (e && ent->borrowed_at_line > 0) {
            diag_add_related_span(&g_parser_diag, e, diag_span_lc(DIAG_NO_FILE, ent->borrowed_at_line, 1, 1), "first mutable borrow occurs here");
          }
          return -1;
        }
        ent->borrow_shared_count++;
        ent->borrowed_at_line = tgt->line;
      }
      /* §4.8 NLL: record the transient increment so it can either
       * be claimed by a binder (var_decl / assign) or released at
       * end of the enclosing statement. */
      if (ctx->stmt_borrow_count < STMT_BORROW_MAX) {
        uint32_t i = ctx->stmt_borrow_count++;
        strncpy(ctx->stmt_borrows[i].target, tgt->name, AST_NAME_LEN - 1);
        ctx->stmt_borrows[i].target[AST_NAME_LEN - 1] = '\0';
        ctx->stmt_borrows[i].kind = is_mut ? 2 : 1;
        ctx->stmt_borrows[i].claimed = 0;
      }
      /* Materialise the value like a plain read (no Q_ opcode change).
       * Scope 1 (global) → emit LOAD_GLOBAL; else → vreg passthrough. */
      uint32_t dummy;
      int scope = sym_lookup_both(ctx, tgt->name, &dummy);
      if (scope == 1) {
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(rd), q_imm(idx), q_none()));
        return (int)rd;
      }
      return (int)idx;
    }
    /* Borrow of a non-identifier (e.g. &obj.field, &arr[i]) — just
     * pass the value through for now. No aliasing tracking. */
    return lower_expr(ctx, tgt);
  }

  /* §22 `task FUNC_CALL` — spawn async task, returns task ID
   * §22 `wait TASK_ID` — wait for task completion, returns result */
  case AST_TASK: {
    if (expr->int_val == 0) {
      /* Spawn: task FUNC_CALL — children[0] is the call expression */
      if (expr->child_count < 1) {
        lower_error(ctx, expr, "task spawn requires a function call");
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      const ast_node_t *call = expr->children[0];
      if (!call || call->type != AST_CALL) {
        lower_error(ctx, expr, "task spawn requires a function call expression");
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      /* Find function index */
      int fidx = find_func_index(ctx, call->name);
      if (fidx < 0) {
        char buf[128];
        snprintf(buf, sizeof(buf), "undefined async function: %s", call->name);
        lower_error(ctx, expr, buf);
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      {
        q_function_t *tgt = &ctx->module.functions[fidx];
        for (uint32_t i = 0; i < tgt->param_count && i < Q_MAX_PARAMS; i++) {
          if (tgt->param_is_ref[i]) {
            lower_error(ctx, expr, "async/task call does not support ref parameters");
            uint32_t rd = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            return (int)rd;
          }
        }
      }
      /* Evaluate arguments and move to R0..R(n-1) */
      uint32_t nargs = call->child_count;
      int arg_vregs[16] = {0};
      for (uint32_t i = 0; i < nargs && i < 16; i++) {
        int av = lower_expr(ctx, call->children[i]);
        if (av < 0)
          return -1;
        arg_vregs[i] = av;
      }
      for (uint32_t i = 0; i < nargs && i < 16; i++) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(i), q_vreg((uint32_t)arg_vregs[i]),
                          q_none()));
      }
      /* Emit Q_TASK_SPAWN with function index */
      uint32_t rd = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_TASK_SPAWN, q_vreg(rd), q_func_idx((uint32_t)fidx),
                        q_none()));
      return (int)rd;
    } else {
      /* Wait: wait TASK_ID — children[0] is the task ID expression */
      if (expr->child_count < 1) {
        lower_error(ctx, expr, "wait requires a task expression");
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
        return (int)rd;
      }
      int tid = lower_expr(ctx, expr->children[0]);
      if (tid < 0)
        return -1;
      /* Emit Q_TASK_WAIT — result goes to dest vreg */
      uint32_t rd = fresh_vreg(ctx);
      emit(ctx,
           q_instr(Q_TASK_WAIT, q_vreg(rd), q_vreg((uint32_t)tid), q_none()));
      return (int)rd;
    }
  }

  case AST_BLOCK: {
    for (uint32_t i = 0; i < expr->child_count; i++) {
      if (expr->children[i])
        lower_stmt(ctx, expr->children[i]);
    }
    return emit_soft_zero(ctx);
  }

  case AST_NAMED_ARG:
    if (expr->child_count > 0 && expr->children[0])
      return lower_expr(ctx, expr->children[0]);
    return emit_soft_zero(ctx);

  case AST_IF:
  case AST_LOOP:
  case AST_WHILE:
  case AST_FOR_RANGE:
    lower_stmt(ctx, expr);
    return emit_soft_zero(ctx);

  case AST_MODULE:
  case AST_IMPORT:
  case AST_EXPORT:
  case AST_INCLUDE:
  case AST_TYPE_DECL:
  case AST_ENUM_DEF:
  case AST_RECORD_DEF:
  case AST_MOLD_DEF:
  case AST_REGISTER_DEF:
  case AST_FUNC_DEF: {
    return emit_soft_zero(ctx);
  }

  default: {
    char buf[96];
    snprintf(buf, sizeof(buf), "unsupported expression type: %d", expr->type);
    lower_error(ctx, expr, buf);
    return -1;
  }
  }
}

/* ═══════════════════════════════════════════════════════
 * §11.12 W302 – try-body dirty-state static check
 * ═══════════════════════════════════════════════════════
 * Walk the try body AST collecting outer-scope variable names that are
 * mutated (AST_ASSIGN / AST_FIELD_ASSIGN / AST_INDEX_ASSIGN / atomic
 * stores / RMWs). Any such name that is NOT in the try(isolate:…) list
 * and whose symbol is NOT marked `atomic` emits W302.
 *
 * The walker also learns local shadowing: any AST_VAR_DECL inside the
 * body introduces a name that is local and therefore exempt.
 */

static int w302_name_in_csv(const char *csv, const char *name) {
  if (!csv || !*csv || !name)
    return 0;
  const char *s = csv;
  size_t nl = strlen(name);
  while (*s) {
    const char *e = s;
    while (*e && *e != ',')
      e++;
    size_t L = (size_t)(e - s);
    if (L == nl && strncmp(s, name, nl) == 0)
      return 1;
    s = *e ? e + 1 : e;
  }
  return 0;
}

typedef struct {
  char names[32][AST_NAME_LEN];
  uint32_t count;
} w302_name_set_t;

static int w302_set_has(const w302_name_set_t *s, const char *name) {
  for (uint32_t i = 0; i < s->count; i++)
    if (strcmp(s->names[i], name) == 0)
      return 1;
  return 0;
}

static void w302_set_add(w302_name_set_t *s, const char *name) {
  if (w302_set_has(s, name))
    return;
  if (s->count >= sizeof(s->names) / sizeof(s->names[0]))
    return;
  strncpy(s->names[s->count], name, AST_NAME_LEN - 1);
  s->names[s->count][AST_NAME_LEN - 1] = '\0';
  s->count++;
}

static void w302_walk(const ast_node_t *node, w302_name_set_t *locals,
                      w302_name_set_t *mutated) {
  if (!node)
    return;

  switch (node->type) {
  case AST_VAR_DECL:
  case AST_CONST_DECL:
    /* Local shadowing: declarations inside the try body do not count
     * as outer-scope mutations. */
    w302_set_add(locals, node->name);
    for (uint32_t i = 0; i < node->child_count; i++)
      w302_walk(node->children[i], locals, mutated);
    return;

  case AST_ASSIGN:
  case AST_ATOMIC_STORE:
  case AST_ATOMIC_RMW:
    if (!w302_set_has(locals, node->name))
      w302_set_add(mutated, node->name);
    for (uint32_t i = 0; i < node->child_count; i++)
      w302_walk(node->children[i], locals, mutated);
    return;

  case AST_INDEX_ASSIGN:
  case AST_FIELD_ASSIGN: {
    /* Target is children[0] — look for root identifier. */
    const ast_node_t *root = node->child_count > 0 ? node->children[0] : NULL;
    while (root &&
           (root->type == AST_FIELD_ACCESS || root->type == AST_INDEX_ACCESS ||
            root->type == AST_SAFE_ACCESS)) {
      root = root->child_count > 0 ? root->children[0] : NULL;
    }
    if (root && root->type == AST_IDENTIFIER &&
        !w302_set_has(locals, root->name)) {
      w302_set_add(mutated, root->name);
    }
    for (uint32_t i = 0; i < node->child_count; i++)
      w302_walk(node->children[i], locals, mutated);
    return;
  }

  case AST_TRY_BLOCK:
    /* Nested try — do not descend; the inner try runs its own W302
     * pass when lowered. */
    return;

  default:
    for (uint32_t i = 0; i < node->child_count; i++)
      w302_walk(node->children[i], locals, mutated);
    return;
  }
}

static void w302_walk_try_body(lower_ctx_t *ctx, const ast_node_t *body,
                               const char *isolate_csv, int has_isolate,
                               uint32_t try_line) {
  (void)has_isolate;
  w302_name_set_t locals = {.count = 0};
  w302_name_set_t mutated = {.count = 0};
  w302_walk(body, &locals, &mutated);

  for (uint32_t i = 0; i < mutated.count; i++) {
    const char *nm = mutated.names[i];
    if (w302_name_in_csv(isolate_csv, nm))
      continue;
    symbol_entry_t *ent = NULL;
    if (sym_lookup_entry_both(ctx, nm, &ent, NULL) >= 0 && ent &&
        ent->is_atomic)
      continue;
    fprintf(stderr,
            "warning W302: variable '%s' mutated in try-body at line %u "
            "without isolate or atomic declaration\n",
            nm, try_line);
  }
}

/* ═══════════════════════════════════════════════════════
 * Statement Lowering
 * ═══════════════════════════════════════════════════════ */

static void emit_sized_narrowing(lower_ctx_t *ctx, uint32_t r,
                                 const char *type_name) {
  if (!type_name || !type_name[0])
    return;

  if (strcmp(type_name, "bool") == 0) {
    /* bool: val & 1 (as per test_sized_types.vri expectation) */
    uint32_t mr = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(mr), q_imm(1), q_none()));
    emit(ctx, q_instr(Q_AND, q_vreg(r), q_vreg(r), q_vreg(mr)));
    return;
  }

  int64_t mask = 0;
  int is_signed = 0;
  int bits = 0;

  if (strcmp(type_name, "u8") == 0) {
    mask = 0xFF;
    bits = 8;
  } else if (strcmp(type_name, "i8") == 0) {
    mask = 0xFF;
    bits = 8;
    is_signed = 1;
  } else if (strcmp(type_name, "u16") == 0) {
    mask = 0xFFFF;
    bits = 16;
  } else if (strcmp(type_name, "i16") == 0) {
    mask = 0xFFFF;
    bits = 16;
    is_signed = 1;
  } else if (strcmp(type_name, "u32") == 0) {
    mask = 0xFFFFFFFFLL;
    bits = 32;
  } else if (strcmp(type_name, "i32") == 0) {
    mask = 0xFFFFFFFFLL;
    bits = 32;
    is_signed = 1;
  }

  if (mask) {
    uint32_t mr = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(mr), q_imm(mask), q_none()));
    emit(ctx, q_instr(Q_AND, q_vreg(r), q_vreg(r), q_vreg(mr)));

    if (is_signed) {
      /* Sign extend: (x << (64 - bits)) >> (64 - bits) */
      uint32_t sr = fresh_vreg(ctx);
      emit(ctx,
           q_instr(Q_LOAD, q_vreg(sr), q_imm((int64_t)(64 - bits)), q_none()));
      emit(ctx, q_instr(Q_SHL, q_vreg(r), q_vreg(r), q_vreg(sr)));
      emit(ctx, q_instr(Q_SHR, q_vreg(r), q_vreg(r), q_vreg(sr)));
    }
  }
}

int lower_stmt(lower_ctx_t *ctx, const ast_node_t *stmt) {
  if (!stmt)
    return 0;
  /* §4.8 NLL: release any transient (unclaimed) borrows created by
   * the previous statement's expressions (e.g. function call args).
   * Claimed borrows persist via the borrower's back-link and are
   * only released when the borrower is reassigned or at func exit. */
  ownership_release_unclaimed_stmt_borrows(ctx);

  switch (stmt->type) {

  case AST_VAR_DECL:
  case AST_CONST_DECL: {
    if (stmt->int_val & 0x4000) {
      /* Tuple destructuring: var (a, b) = expr */
      int expr_vreg = -1;
      if (stmt->child_count > 0) {
        ast_node_t *init = stmt->children[stmt->child_count - 1];
        if (init->type != AST_IDENTIFIER) { /* ensure it's the RHS */
            expr_vreg = lower_expr(ctx, init);
        } else {
            /* If the last child is an identifier, it could be either RHS or part of tuple */
            /* If child_count > number of tuple names, the last is RHS. */
            /* Actually, in parser.c we added the init expression as the last child if match(TOK_ASSIGN). */
            expr_vreg = lower_expr(ctx, init);
        }
      }
      for (uint32_t i = 0; i < stmt->child_count - 1; i++) {
        ast_node_t *ident = stmt->children[i];
        if (strcmp(ident->name, "_") == 0) continue;
        
        uint32_t r = fresh_vreg(ctx);
        sym_define(&ctx->symbols, ident->name, r, VIR_TYPE_I64);
        
        if (expr_vreg >= 0) {
          uint32_t idx_r = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(idx_r), q_imm(i), q_none()));
          emit(ctx, q_instr(Q_ARR_GET, q_vreg(r), q_vreg((uint32_t)expr_vreg), q_vreg(idx_r)));
        }
      }
      return 0;
    }

    uint32_t r = 0;
    uint32_t existing_idx = 0;
    int existing_scope = sym_lookup_both(ctx, stmt->name, &existing_idx);
    int reuse_existing_local = (existing_scope == 0);
    if (reuse_existing_local) {
      r = existing_idx;
    } else {
      r = fresh_vreg(ctx);
    }

    /* Infer type from initializer if present */
    vir_type_t var_type = VIR_TYPE_I64; /* default */
    if (stmt->child_count > 0) {
      const ast_node_t *init = stmt->children[0];
      if (init->type == AST_LITERAL_STR) {
        var_type = VIR_TYPE_PTR; /* string pointer */
      } else if (init->type == AST_LITERAL_FLOAT) {
        var_type = VIR_TYPE_F64;
      } else if (init->type == AST_BUILTIN_CALL) {
        /* Check if builtin returns a string */
        if (init->builtin_id == BUILTIN_STR_CAT ||
            init->builtin_id == BUILTIN_I_TO_STR) {
          var_type = VIR_TYPE_PTR;
        }
      } else if (init->type == AST_IDENTIFIER) {
        /* Look up the type of the source variable */
        symbol_entry_t *src_ent = NULL;
        if (sym_lookup_entry_both(ctx, init->name, &src_ent, NULL) >= 0 &&
            src_ent) {
          var_type = src_ent->type;
        }
      }
    }

    if (!reuse_existing_local) {
      sym_define(&ctx->symbols, stmt->name, r, var_type);
    }
    /* §4.8: locate the just-defined entry and classify its type. */
    symbol_entry_t *new_ent = NULL;
    sym_lookup_entry_both(ctx, stmt->name, &new_ent, NULL);
    if (new_ent && stmt->name2[0]) {
      strncpy(new_ent->type_name, stmt->name2, AST_NAME_LEN - 1);
      new_ent->type_name[AST_NAME_LEN - 1] = '\0';
    }
    /* §13.7 atomic-var marker: parser sets bit 12 (0x1000) in int_val
     * for `atomic var ...`. Record on the symbol so try(isolate:) can
     * skip snapshots and W302 can suppress warnings. */
    if (new_ent && (stmt->int_val & 0x1000)) {
      new_ent->is_atomic = 1;
    }
    /* §25.1 reactive-var marker (bit 13, 0x2000) */
    if (new_ent && (stmt->int_val & 0x2000)) {
      new_ent->is_reactive = 1;
    }
    /* §26.1 tensor shape marker (bit 15, 0x8000); rows in bits 32..47,
     * cols in 48..63 of the parser's int_val field. */
    if (new_ent && (stmt->int_val & 0x8000)) {
      new_ent->is_tensor = 1;
      new_ent->tensor_rows = (uint32_t)((stmt->int_val >> 32) & 0xFFFF);
      new_ent->tensor_cols = (uint32_t)((stmt->int_val >> 48) & 0xFFFF);
    }
    /* §16 register/mold type binding: if the `var x: TYPE` annotation
     * names a known bit-type, record it so field access lowers to
     * shift+mask operations. */
    if (new_ent && stmt->name2[0] && find_bit_type(ctx, stmt->name2)) {
      strncpy(new_ent->bit_type_name, stmt->name2, AST_NAME_LEN - 1);
    }
    /* If there is an initialiser expression, lower it */
    if (stmt->child_count > 0) {
      const ast_node_t *init = stmt->children[0];
      symbol_infer_record_type_from_expr(ctx, new_ent, init);
      int val = lower_expr(ctx, init);
      if (val >= 0 && (uint32_t)val != r) {
        emit(ctx, q_instr(Q_MOVE, q_vreg(r), q_vreg((uint32_t)val), q_none()));
      }
      /* §4.1 Sized-type narrowing */
      emit_sized_narrowing(ctx, r, stmt->name2);
      /* §20: mark dict symbols. */
      if (new_ent && init && init->type == AST_MAP_LITERAL) {
        new_ent->is_dict = 1;
        new_ent->dict_key_is_str = (uint8_t)(init->int_val & 1);
        new_ent->is_move_type = 1;
      }
      /* §4.8: classify move-type and possibly consume the source. */
      if (new_ent) {
        const ast_node_t *u = ast_unwrap_borrow(init);
        if (ast_produces_move_type(init)) {
          new_ent->is_move_type = 1;
        } else if (init->type != AST_BORROW && u && u->type == AST_IDENTIFIER) {
          /* Initialising from another identifier. Inherit the
           * move-type flag from the source; if so, consume. */
          symbol_entry_t *src_ent = NULL;
          sym_lookup_entry_both(ctx, u->name, &src_ent, NULL);
          if (src_ent && src_ent->is_move_type) {
            new_ent->is_move_type = 1;
            src_ent->is_moved = 1;
            src_ent->moved_at_line = init->line;
          }
        }
        /* §4.8 NLL: if RHS is &expr or &mut expr, claim the
         * stmt_borrow entry so the increment persists on this
         * new binder across statements. */
        if (init->type == AST_BORROW) {
          ownership_claim_stmt_borrow(ctx, new_ent, init);
        }
      }
    } else {
      emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(0), q_none()));
    }
    /* §26.1 tensor: after init, stamp shape onto the array handle so
     * Q_TENSOR_MUL can pick the matmul path. */
    if (new_ent && new_ent->is_tensor &&
        (new_ent->tensor_rows || new_ent->tensor_cols)) {
      emit(ctx, q_instr(Q_TENSOR_SHAPE, q_vreg(r),
                        q_imm((int64_t)new_ent->tensor_rows),
                        q_imm((int64_t)new_ent->tensor_cols)));
    }
    /* §25.1 reactive init: emit notification on initial binding. */
    if (new_ent && new_ent->is_reactive) {
      uint32_t sidx = q_module_add_string(&ctx->module, stmt->name);
      emit(ctx, q_instr(Q_REACTIVE_NOTIFY, q_none(), q_str(sidx), q_vreg(r)));
    }
    return 0;
  }

  case AST_ASSIGN: {
    if (stmt->child_count < 1)
      return -1;
    uint32_t idx;
    int scope = sym_lookup_both(ctx, stmt->name, &idx);
    if (scope < 0) {
      /* Implicitly declare local variable! */
      uint32_t r = fresh_vreg(ctx);
      sym_define(&ctx->symbols, stmt->name, r, VIR_TYPE_I64);
      scope = 0; /* now local scope */
      idx = r;
    }
    const ast_node_t *rhs = stmt->children[0];
    int val = lower_expr(ctx, rhs);
    if (val < 0)
      return -1;

    symbol_entry_t *ent = NULL;
    sym_lookup_entry_both(ctx, stmt->name, &ent, NULL);
    symbol_infer_record_type_from_expr(ctx, ent, rhs);

    if (scope == 1) {
      /* Global variable - emit Q_STORE_GLOBAL */
      uint32_t r = (uint32_t)val;
      if (ent && ent->type_name[0]) {
        /* Truncate/narrow before storing to global */
        r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_MOVE, q_vreg(r), q_vreg((uint32_t)val), q_none()));
        emit_sized_narrowing(ctx, r, ent->type_name);
      }
      emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(), q_imm(idx), q_vreg(r)));
    } else {
      /* Local variable */
      if ((uint32_t)val != idx) {
        emit(ctx,
             q_instr(Q_MOVE, q_vreg(idx), q_vreg((uint32_t)val), q_none()));
      }
      if (ent && ent->type_name[0]) {
        emit_sized_narrowing(ctx, idx, ent->type_name);
      }
    }
    /* §25.1 reactive-var write notification. */
    {
      symbol_entry_t *re = NULL;
      sym_lookup_entry_both(ctx, stmt->name, &re, NULL);
      if (re && re->is_reactive) {
        uint32_t sidx = q_module_add_string(&ctx->module, stmt->name);
        emit(ctx, q_instr(Q_REACTIVE_NOTIFY, q_none(), q_str(sidx),
                          q_vreg((uint32_t)val)));
      }
    }
    /* §4.8: if RHS is a bare identifier of a move-type var, consume it.
     * Also: reassigning the LHS resurrects it (no longer moved). */
    {
      symbol_entry_t *lhs_ent = NULL;
      sym_lookup_entry_both(ctx, stmt->name, &lhs_ent, NULL);
      /* §4.8 NLL: reassigning the LHS releases any borrow it
       * previously held (from `var b = &a` etc.). */
      if (lhs_ent)
        ownership_release_borrow(ctx, lhs_ent);
      const ast_node_t *u = ast_unwrap_borrow(rhs);
      if (rhs->type != AST_BORROW && u && u->type == AST_IDENTIFIER) {
        symbol_entry_t *src_ent = NULL;
        sym_lookup_entry_both(ctx, u->name, &src_ent, NULL);
        if (src_ent && src_ent->is_move_type) {
          src_ent->is_moved = 1;
          src_ent->moved_at_line = rhs->line;
          if (lhs_ent)
            lhs_ent->is_move_type = 1;
        }
      } else if (ast_produces_move_type(rhs) && lhs_ent) {
        lhs_ent->is_move_type = 1;
      }
      /* §4.8 NLL: if RHS is &expr, LHS claims that borrow. */
      if (rhs->type == AST_BORROW && lhs_ent) {
        ownership_claim_stmt_borrow(ctx, lhs_ent, rhs);
      }
      if (lhs_ent)
        lhs_ent->is_moved = 0;
    }
    return 0;
  }

  /* §24.4 Atomic store (lock x = v / x!! = v): real seq_cst store on
   * globals via Q_ATOMIC_STORE_GLOBAL.  Locals have no cross-thread
   * aliasing so regular move is safe.
   *
   * Peephole for RMW (lock x += v → AST_ATOMIC_STORE(x, x OP_ADD v)):
   *   - If child is BINOP with self-reference on left, emit atomic
   *     fetch_add/sub for real atomicity on globals. */
  case AST_ATOMIC_STORE: {
    if (stmt->child_count < 1)
      return -1;
    uint32_t idx;
    int scope = sym_lookup_both(ctx, stmt->name, &idx);
    if (scope < 0) {
      char buf[128];
      snprintf(buf, sizeof(buf), "atomic store to undefined: %s", stmt->name);
      lower_error(ctx, stmt, buf);
      return -1;
    }
    /* Detect RMW pattern: child = BINOP(OP_ADD/SUB, IDENT(name), rhs) */
    const ast_node_t *child = stmt->children[0];
    if (scope == 1 && child && child->type == AST_BINOP &&
        child->child_count >= 2 &&
        (child->op == OP_ADD || child->op == OP_SUB)) {
      const ast_node_t *lhs = child->children[0];
      if (lhs && lhs->type == AST_IDENTIFIER &&
          strcmp(lhs->name, stmt->name) == 0) {
        int rhs_v = lower_expr(ctx, child->children[1]);
        if (rhs_v < 0)
          return -1;
        uint32_t rd = fresh_vreg(ctx);
        q_opcode_t aop =
            (child->op == OP_ADD) ? Q_ATOMIC_ADD_GLOBAL : Q_ATOMIC_SUB_GLOBAL;
        emit(ctx,
             q_instr(aop, q_vreg(rd), q_imm(idx), q_vreg((uint32_t)rhs_v)));
        return 0;
      }
    }
    int val = lower_expr(ctx, stmt->children[0]);
    if (val < 0)
      return -1;
    if (scope == 1) {
      emit(ctx, q_instr(Q_ATOMIC_STORE_GLOBAL, q_none(), q_imm(idx),
                        q_vreg((uint32_t)val)));
    } else {
      if ((uint32_t)val != idx) {
        emit(ctx,
             q_instr(Q_MOVE, q_vreg(idx), q_vreg((uint32_t)val), q_none()));
      }
    }
    return 0;
  }

  /* §24.2 Swizzle write-mask: v~xy = rhs */
  case AST_SWIZZLE_STORE: {
    if (stmt->child_count < 1)
      return -1;
    uint32_t vidx;
    int scope = sym_lookup_both(ctx, stmt->name, &vidx);
    if (scope < 0) {
      char buf[128];
      snprintf(buf, sizeof(buf), "swizzle store to undefined: %s", stmt->name);
      lower_error(ctx, stmt, buf);
      return -1;
    }
    /* Load target array handle */
    uint32_t dst_v = fresh_vreg(ctx);
    if (scope == 1) {
      emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(dst_v), q_imm(vidx), q_none()));
    } else {
      emit(ctx, q_instr(Q_MOVE, q_vreg(dst_v), q_vreg(vidx), q_none()));
    }
    int rhs = lower_expr(ctx, stmt->children[0]);
    if (rhs < 0)
      return -1;
    uint32_t chans_idx = q_module_add_string(&ctx->module, stmt->name2);
    q_operand_t chans_op;
    chans_op.type = OPERAND_STR;
    chans_op.str_idx = chans_idx;
    emit(ctx, q_instr(Q_SWIZZLE_STORE, q_vreg(dst_v), q_vreg((uint32_t)rhs),
                      chans_op));
    return 0;
  }

  case AST_INDEX_ASSIGN: {
    /* arr[idx] = val */
    if (stmt->child_count < 2)
      return -1;
    uint32_t arr_vreg;
    uint32_t idx_child = 0;
    uint32_t val_child = 1;
    symbol_entry_t *ent = NULL;
    if (stmt->name[0] == '\0') {
      if (stmt->child_count < 3)
        return -1;
      int base = lower_expr(ctx, stmt->children[0]);
      if (base < 0)
        return -1;
      arr_vreg = (uint32_t)base;
      idx_child = 1;
      val_child = 2;
    } else {
      uint32_t arr_idx;
      int arr_scope = sym_lookup_both(ctx, stmt->name, &arr_idx);
      if (arr_scope < 0) {
        lower_error(ctx, stmt, "index assign to undefined variable");
        return -1;
      }
      if (arr_scope == 1) {
        /* Global - load into vreg first */
        arr_vreg = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(arr_vreg), q_imm(arr_idx),
                          q_none()));
      } else {
        arr_vreg = arr_idx;
      }
      sym_lookup_entry_both(ctx, stmt->name, &ent, NULL);
    }
    int idx = lower_expr(ctx, stmt->children[idx_child]);
    int val = lower_expr(ctx, stmt->children[val_child]);
    if (idx < 0 || val < 0)
      return -1;
    /* §20 Dict set when symbol is a dict. */
    {
      if (stmt->name[0] != '\0' && ent &&
          ent->is_dict) {
        emit(ctx, q_instr(ent->dict_key_is_str ? Q_DICT_SET_S : Q_DICT_SET_I,
                          q_vreg((uint32_t)val), q_vreg(arr_vreg),
                          q_vreg((uint32_t)idx)));
        return 0;
      }
    }
    emit(ctx, q_instr(Q_ARR_SET, q_vreg((uint32_t)val), q_vreg(arr_vreg),
                      q_vreg((uint32_t)idx)));
    return 0;
  }

  case AST_DEL_STMT: {
    /* §20: del m[key] */
    if (stmt->child_count < 1)
      return -1;
    uint32_t d_idx;
    int scope = sym_lookup_both(ctx, stmt->name, &d_idx);
    if (scope < 0) {
      lower_error(ctx, stmt, "del on undefined variable");
      return -1;
    }
    uint32_t d_vreg;
    if (scope == 1) {
      d_vreg = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(d_vreg), q_imm(d_idx), q_none()));
    } else {
      d_vreg = d_idx;
    }
    int kr = lower_expr(ctx, stmt->children[0]);
    if (kr < 0)
      return -1;
    symbol_entry_t *ent = NULL;
    sym_lookup_entry_both(ctx, stmt->name, &ent, NULL);
    int is_str = (ent && ent->is_dict && ent->dict_key_is_str);
    emit(ctx, q_instr(is_str ? Q_DICT_DEL_S : Q_DICT_DEL_I, q_none(),
                      q_vreg(d_vreg), q_vreg((uint32_t)kr)));
    return 0;
  }

  case AST_PRINT: {
    if (stmt->child_count < 1)
      return -1;
    int val = lower_expr(ctx, stmt->children[0]);
    if (val < 0)
      return -1;

    /* Infer the type of the expression to annotate Q_PRINT */
    const char *type_str = "int"; /* default */
    const ast_node_t *expr = stmt->children[0];

    /* Helper function to infer type recursively */
    vir_type_t inferred_type = VIR_TYPE_I64;

    if (expr->type == AST_LITERAL_STR) {
      inferred_type = VIR_TYPE_PTR;
    } else if (expr->type == AST_LITERAL_FLOAT) {
      inferred_type = VIR_TYPE_F64;
    } else if (expr->type == AST_IDENTIFIER) {
      symbol_entry_t *ent = NULL;
      if (sym_lookup_entry_both(ctx, expr->name, &ent, NULL) >= 0 && ent) {
        inferred_type = ent->type;
      }
    } else if (expr->type == AST_BUILTIN_CALL) {
      if (expr->builtin_id == BUILTIN_STR_CAT ||
          expr->builtin_id == BUILTIN_I_TO_STR) {
        inferred_type = VIR_TYPE_PTR;
      }
    } else if (expr->type == AST_BINOP && expr->op == OP_ADD) {
      /* Check if either operand is a string - string concatenation */
      if (expr->child_count >= 2) {
        const ast_node_t *left = expr->children[0];
        const ast_node_t *right = expr->children[1];

        /* Check left operand */
        if (left->type == AST_LITERAL_STR) {
          inferred_type = VIR_TYPE_PTR;
        } else if (left->type == AST_IDENTIFIER) {
          symbol_entry_t *ent = NULL;
          if (sym_lookup_entry_both(ctx, left->name, &ent, NULL) >= 0 && ent) {
            if (ent->type == VIR_TYPE_PTR) {
              inferred_type = VIR_TYPE_PTR;
            }
          }
        }

        /* Check right operand if left wasn't a string */
        if (inferred_type != VIR_TYPE_PTR) {
          if (right->type == AST_LITERAL_STR) {
            inferred_type = VIR_TYPE_PTR;
          } else if (right->type == AST_IDENTIFIER) {
            symbol_entry_t *ent = NULL;
            if (sym_lookup_entry_both(ctx, right->name, &ent, NULL) >= 0 &&
                ent) {
              if (ent->type == VIR_TYPE_PTR) {
                inferred_type = VIR_TYPE_PTR;
              }
            }
          }
        }
      }
    }

    /* Convert vir_type_t to string */
    if (inferred_type == VIR_TYPE_PTR) {
      type_str = "string";
    } else if (inferred_type == VIR_TYPE_F32 || inferred_type == VIR_TYPE_F64) {
      type_str = "float";
    } else if (inferred_type == VIR_TYPE_I8) {
      type_str = "bool";
    }

    q_instruction_t instr =
        q_instr(Q_PRINT, q_none(), q_vreg((uint32_t)val), q_none());
    strncpy(instr.operand_type, type_str, sizeof(instr.operand_type) - 1);
    instr.operand_type[sizeof(instr.operand_type) - 1] = '\0';
    emit(ctx, instr);
    return 0;
  }

  case AST_RETURN: {
    if (stmt->child_count > 0) {
      int val = lower_expr(ctx, stmt->children[0]);
      if (val < 0)
        return -1;
      /* §20.2: inside `map ... end`, `out expr` appends to array. */
      if (ctx->in_map_expr) {
        emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg(ctx->map_arr_vreg),
                          q_vreg((uint32_t)val)));
        return 0;
      }
      emit(ctx, q_instr(Q_RET, q_none(), q_vreg((uint32_t)val), q_none()));
    } else {
      emit(ctx, q_instr(Q_RET, q_none(), q_none(), q_none()));
    }
    return 0;
  }

  case AST_IF: {
    /* children[0] = condition
     * children[1] = then-block
     * children[2] = else-block (optional) */
    if (stmt->child_count < 2)
      return -1;

    int cond = lower_expr(ctx, stmt->children[0]);
    if (cond < 0)
      return -1;

    uint32_t else_label = fresh_label(ctx);
    uint32_t end_label = fresh_label(ctx);

    emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg((uint32_t)cond),
                      q_label(else_label)));

    /* Then block */
    lower_stmt(ctx, stmt->children[1]);

    if (stmt->child_count > 2 && stmt->children[2]) {
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_label), q_none()));
    }

    /* Else label */
    q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    lbl.patch_id = else_label;
    emit(ctx, lbl);

    /* Else block */
    if (stmt->child_count > 2 && stmt->children[2]) {
      lower_stmt(ctx, stmt->children[2]);
      lbl.patch_id = end_label;
      emit(ctx, lbl);
    }
    return 0;
  }

  case AST_LOOP: {
    /* children[0] = count expression
     * children[1] = body block */
    if (stmt->child_count < 2)
      return -1;

    /* Counter variable */
    uint32_t counter = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(counter), q_imm(0), q_none()));

    int limit = lower_expr(ctx, stmt->children[0]);
    if (limit < 0)
      return -1;

    uint32_t loop_label = fresh_label(ctx);
    uint32_t cont_label = fresh_label(ctx);
    uint32_t end_label = fresh_label(ctx);

    /* Loop header */
    q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    lbl.patch_id = loop_label;
    emit(ctx, lbl);

    /* Check counter < limit */
    uint32_t cmp_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_CMP_LT, q_vreg(cmp_r), q_vreg(counter),
                      q_vreg((uint32_t)limit)));
    emit(ctx,
         q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(cmp_r), q_label(end_label)));

    /* Push loop labels: continue → increment, break → end */
    ctx->loop_start_labels[ctx->loop_depth] = cont_label;
    ctx->loop_end_labels[ctx->loop_depth] = end_label;
    ctx->loop_depth++;

    /* Body */
    lower_stmt(ctx, stmt->children[1]);

    ctx->loop_depth--;

    /* Continue target: increment counter */
    lbl.patch_id = cont_label;
    emit(ctx, lbl);
    uint32_t one = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
    emit(ctx, q_instr(Q_ADD, q_vreg(counter), q_vreg(counter), q_vreg(one)));

    /* Loop back */
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(loop_label), q_none()));

    /* End label */
    lbl.patch_id = end_label;
    emit(ctx, lbl);
    return 0;
  }

  case AST_WHILE: {
    /* children[0] = condition
     * children[1] = body block */
    if (stmt->child_count < 2)
      return -1;

    uint32_t loop_label = fresh_label(ctx);
    uint32_t end_label = fresh_label(ctx);

    q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    lbl.patch_id = loop_label;
    emit(ctx, lbl);

    int cond = lower_expr(ctx, stmt->children[0]);
    if (cond < 0)
      return -1;

    emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg((uint32_t)cond),
                      q_label(end_label)));

    /* Push loop labels for break/continue */
    ctx->loop_start_labels[ctx->loop_depth] = loop_label;
    ctx->loop_end_labels[ctx->loop_depth] = end_label;
    ctx->loop_depth++;

    lower_stmt(ctx, stmt->children[1]);

    ctx->loop_depth--;

    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(loop_label), q_none()));

    lbl.patch_id = end_label;
    emit(ctx, lbl);
    return 0;
  }

  case AST_CHECK_CPU: {
    q_instruction_t pp = q_instr(Q_PATCH_POINT, q_none(), q_none(), q_none());
    pp.patch_id = ++ctx->patch_counter;
    emit(ctx, pp);
    return 0;
  }

  case AST_PATCH_POINT: {
    q_instruction_t pp = q_instr(Q_PATCH_POINT, q_none(), q_none(), q_none());
    pp.patch_id = ++ctx->patch_counter;
    emit(ctx, pp);
    return 0;
  }

  case AST_BLOCK: {
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      lower_stmt(ctx, stmt->children[i]);
    }
    return 0;
  }

  /* ── §25/§26 Annotation blocks: body lowers transparently. ─── */
  case AST_INFER_BLOCK:
  case AST_TRAIN_BLOCK:
  case AST_ISOLATE_BLOCK: {
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      lower_stmt(ctx, stmt->children[i]);
    }
    return 0;
  }

  /* §25.2 morph Entity -> UI — compile-time metadata only. */
  case AST_MORPH_DEF:
    return 0;

  /* §25.3 bundle NAME: TYPE = embed "path" — at this point the parser
   * has already stored the file bytes into child[0].name. Emit as a
   * string-valued var or byte-array depending on the type annotation. */
  case AST_BUNDLE_DECL: {
    uint32_t r = fresh_vreg(ctx);
    sym_define(&ctx->symbols, stmt->name, r, VIR_TYPE_I64);
    const ast_node_t *payload =
        (stmt->child_count > 0) ? stmt->children[0] : NULL;
    if (payload) {
      int is_bytes = (strcmp(stmt->name2, "u8") == 0);
      if (is_bytes) {
        /* Build array of byte values. */
        emit(ctx, q_instr(Q_ARR_NEW, q_vreg(r),
                          q_imm((int64_t)payload->int_val), q_none()));
        for (int64_t i = 0; i < payload->int_val; i++) {
          uint32_t tmp = fresh_vreg(ctx);
          emit(ctx, q_instr(Q_LOAD, q_vreg(tmp),
                            q_imm((uint8_t)payload->name[i]), q_none()));
          emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg(r), q_vreg(tmp)));
        }
      } else {
        /* Treat as string. */
        uint32_t sidx = q_module_add_string(&ctx->module, payload->name);
        emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_str(sidx), q_none()));
      }
    } else {
      emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(0), q_none()));
    }
    return 0;
  }

  /* §23.1 port NAME: TYPE [(cap: N)] — allocate channel handle */
  case AST_PORT_DECL: {
    uint32_t r = fresh_vreg(ctx);
    if (sym_define(&ctx->symbols, stmt->name, r, VIR_TYPE_I64) >= 0) {
      symbol_entry_t *ent = NULL;
      if (sym_lookup_entry_both(ctx, stmt->name, &ent, NULL) >= 0 && ent)
        ent->is_port = 1;
    }
    int64_t cap = stmt->int_val > 0 ? stmt->int_val : 16;
    emit(ctx, q_instr(Q_PORT_NEW, q_vreg(r), q_imm(cap), q_none()));
    return 0;
  }
  /* §23.2 send NAME <- expr */
  case AST_SEND_STMT: {
    uint32_t pidx;
    int scope = sym_lookup_both(ctx, stmt->name, &pidx);
    if (scope < 0)
      return -1;
    uint32_t pv;
    if (scope == 1) {
      pv = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(pv), q_imm(pidx), q_none()));
    } else {
      pv = pidx;
    }
    if (stmt->child_count < 1)
      return -1;
    int vv = lower_expr(ctx, stmt->children[0]);
    if (vv < 0)
      return -1;
    emit(ctx, q_instr(Q_PORT_SEND, q_vreg(pv), q_vreg((uint32_t)vv), q_none()));
    return 0;
  }
  /* §23.4 select: case recv X from P: body ... end
   * Semantics: poll each case's port in order; first non-empty wins.
   * Uses Q_PORT_LEN → if >0 then Q_PORT_RECV into bind var → lower body →
   * break. */
  case AST_SELECT_BLOCK: {
    uint32_t end_lbl = fresh_label(ctx);
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      ast_node_t *cs = stmt->children[i];
      if (!cs)
        continue;
      uint32_t pidx;
      int scope = sym_lookup_both(ctx, cs->name2, &pidx);
      if (scope < 0)
        continue;
      uint32_t pv;
      if (scope == 1) {
        pv = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(pv), q_imm(pidx), q_none()));
      } else {
        pv = pidx;
      }
      uint32_t len_r = fresh_vreg(ctx);
      emit(ctx, q_instr(Q_PORT_LEN, q_vreg(len_r), q_vreg(pv), q_none()));
      uint32_t next_lbl = fresh_label(ctx);
      emit(ctx,
           q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(len_r), q_label(next_lbl)));
      /* Recv into bind var */
      uint32_t bind_r = fresh_vreg(ctx);
      sym_define(&ctx->symbols, cs->name, bind_r, VIR_TYPE_I64);
      emit(ctx, q_instr(Q_PORT_RECV, q_vreg(bind_r), q_vreg(pv), q_none()));
      for (uint32_t j = 0; j < cs->child_count; j++)
        lower_stmt(ctx, cs->children[j]);
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_lbl), q_none()));
      q_instruction_t nxt = q_instr(Q_LABEL, q_none(), q_none(), q_none());
      nxt.patch_id = next_lbl;
      emit(ctx, nxt);
    }
    q_instruction_t e = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    e.patch_id = end_lbl;
    emit(ctx, e);
    return 0;
  }
  case AST_AWAIT_EXPR: {
    /* §22.1 `await EXPR` — resolve EXPR to a task id, block until it
     * completes, then load its result into the statement result reg. */
    if (stmt->child_count < 1)
      return -1;
    int tid = lower_expr(ctx, stmt->children[0]);
    if (tid < 0)
      return -1;
    emit(ctx, q_instr(Q_TASK_WAIT, q_none(), q_vreg((uint32_t)tid), q_none()));
    /* Result is not directly surfaced here (VM task_wait is
     * synchronous and result retrieval happens via Q_LOAD of the
     * task's global slot elsewhere). Emit a dummy dest = 0. */
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
    return (int)rd;
  }
  case AST_CANCEL_STMT: {
    /* §22.7 `cancel EXPR` — cancel task whose id is EXPR. */
    if (stmt->child_count < 1)
      return -1;
    int tid = lower_expr(ctx, stmt->children[0]);
    if (tid < 0)
      return -1;
    uint32_t rd = fresh_vreg(ctx);
    emit(ctx,
         q_instr(Q_TASK_CANCEL, q_vreg(rd), q_vreg((uint32_t)tid), q_none()));
    return 0;
  }
  case AST_QUIET_STMT: {
    /* §22.9 `quiet EXPR` — fire-and-forget. Currently: simply
     * evaluate EXPR for side effects and discard its result. The
     * scheduler already runs any spawned tasks to completion on
     * vm_exec_module exit, so no additional book-keeping needed. */
    if (stmt->child_count < 1)
      return 0;
    (void)lower_expr(ctx, stmt->children[0]);
    return 0;
  }
  case AST_ARENA_BLOCK: {
    /* §4.5 `arena NAME: body end` — scoped arena.
     * entry: NAME = arena_new(4096)
     * body:  block
     * exit:  arena_free(NAME) */
    uint32_t size_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(size_r), q_imm(4096), q_none()));
    uint32_t aid_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_ARENA_NEW, q_vreg(aid_r), q_vreg(size_r), q_none()));
    sym_define(&ctx->symbols, stmt->name, aid_r, VIR_TYPE_I64);
    if (stmt->child_count >= 1 && stmt->children[0]) {
      lower_stmt(ctx, stmt->children[0]);
    }
    uint32_t dummy = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_ARENA_FREE, q_vreg(dummy), q_vreg(aid_r), q_none()));
    return 0;
  }
  case AST_FOR_RANGE: {
    /* for VAR in START..END then BODY end
     * children[0] = start, children[1] = end, children[2] = body
     * name = loop variable name
     * Desugar: var = start; while var < end: body; var = var + 1 */
    if (stmt->child_count < 3)
      return -1;

    int start_val = lower_expr(ctx, stmt->children[0]);
    if (start_val < 0)
      return -1;

    int end_val = lower_expr(ctx, stmt->children[1]);
    if (end_val < 0)
      return -1;

    /* Create loop variable */
    uint32_t loop_var = fresh_vreg(ctx);
    sym_define(&ctx->symbols, stmt->name, loop_var, VIR_TYPE_I64);
    emit(ctx, q_instr(Q_MOVE, q_vreg(loop_var), q_vreg((uint32_t)start_val),
                      q_none()));

    uint32_t loop_label = fresh_label(ctx);
    uint32_t end_label = fresh_label(ctx);

    /* Loop header */
    q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    lbl.patch_id = loop_label;
    emit(ctx, lbl);

    /* Check loop_var < end */
    uint32_t cmp_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_CMP_LT, q_vreg(cmp_r), q_vreg(loop_var),
                      q_vreg((uint32_t)end_val)));
    emit(ctx,
         q_instr(Q_JUMP_IF_NOT, q_none(), q_vreg(cmp_r), q_label(end_label)));

    uint32_t cont_label = fresh_label(ctx);

    /* Push loop labels: continue → increment, break → end */
    ctx->loop_start_labels[ctx->loop_depth] = cont_label;
    ctx->loop_end_labels[ctx->loop_depth] = end_label;
    ctx->loop_depth++;

    /* Body */
    lower_stmt(ctx, stmt->children[2]);

    ctx->loop_depth--;

    /* Continue target: increment loop variable */
    lbl.patch_id = cont_label;
    emit(ctx, lbl);
    uint32_t one = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
    emit(ctx, q_instr(Q_ADD, q_vreg(loop_var), q_vreg(loop_var), q_vreg(one)));

    /* Loop back */
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(loop_label), q_none()));

    /* End label */
    lbl.patch_id = end_label;
    emit(ctx, lbl);
    return 0;
  }

  case AST_ENUM_DEF: {
    /* Register enum type — no code emitted (compile-time only) */
    if (ctx->enum_type_count >= ENUM_MAX_TYPES) {
      lower_error(ctx, stmt, "too many enum types");
      return -1;
    }
    enum_type_t *et = &ctx->enum_types[ctx->enum_type_count++];
    strncpy(et->name, stmt->name, AST_NAME_LEN - 1);
    et->name[AST_NAME_LEN - 1] = '\0';
    et->variant_count = 0;
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      const ast_node_t *v = stmt->children[i];
      if (!v || et->variant_count >= ENUM_MAX_VARIANTS)
        continue;
      enum_variant_t *ev = &et->variants[et->variant_count++];
      strncpy(ev->name, v->name, AST_NAME_LEN - 1);
      ev->name[AST_NAME_LEN - 1] = '\0';
      ev->value = v->int_val;

      /* Automatically register this variant as a RECORD type with tag+payload.
       * Layout: [0]=discriminant (variant value), [8]=payload. */
      if (ctx->record_type_count < RECORD_MAX_TYPES) {
        record_type_t *rt = &ctx->record_types[ctx->record_type_count++];
        strncpy(rt->name, v->name, AST_NAME_LEN - 1);
        rt->field_count = 2;
        strncpy(rt->fields[0].name, "tag", AST_NAME_LEN - 1);
        rt->fields[0].type_name[0] = '\0';
        rt->fields[0].offset = 0;
        strncpy(rt->fields[1].name, "value", AST_NAME_LEN - 1);
        rt->fields[1].type_name[0] = '\0';
        rt->fields[1].offset = 8;
      }
    }
    return 0;
  }

  case AST_RECORD_DEF: {
    /* Register record type with field offsets (compile-time only) */
    if (ctx->record_type_count >= RECORD_MAX_TYPES) {
      lower_error(ctx, stmt, "too many record types");
      return -1;
    }
    record_type_t *rt = &ctx->record_types[ctx->record_type_count++];
    strncpy(rt->name, stmt->name, AST_NAME_LEN - 1);
    rt->field_count = 0;
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      const ast_node_t *f = stmt->children[i];
      if (!f || rt->field_count >= RECORD_MAX_FIELDS)
        continue;
      record_field_t *rf = &rt->fields[rt->field_count];
      strncpy(rf->name, f->name, AST_NAME_LEN - 1);
      rf->name[AST_NAME_LEN - 1] = '\0';
      if (f->name2[0]) {
        strncpy(rf->type_name, f->name2, AST_NAME_LEN - 1);
        rf->type_name[AST_NAME_LEN - 1] = '\0';
      } else {
        rf->type_name[0] = '\0';
      }
      rf->offset = rt->field_count * 8; /* offset in bytes */
      rt->field_count++;
    }
    return 0;
  }

  case AST_REGISTER_DEF:
  case AST_MOLD_DEF: {
    /* §16 Register / Mold — compile-time bit-type registration. */
    if (ctx->bit_type_count >= BIT_TYPE_MAX) {
      lower_error(ctx, stmt, "too many register/mold types");
      return -1;
    }
    bit_type_t *bt = &ctx->bit_types[ctx->bit_type_count++];
    strncpy(bt->name, stmt->name, AST_NAME_LEN - 1);
    bt->kind = (stmt->type == AST_MOLD_DEF) ? 1 : 0;
    bt->base_width = (uint8_t)(stmt->int_val > 0 ? stmt->int_val : 32);
    bt->field_count = 0;
    for (uint32_t i = 0; i < stmt->child_count; i++) {
      const ast_node_t *f = stmt->children[i];
      if (!f || bt->field_count >= BIT_TYPE_MAX_FIELDS)
        continue;
      bit_field_t *bf = &bt->fields[bt->field_count++];
      strncpy(bf->name, f->name, AST_NAME_LEN - 1);
      bf->lo = (uint8_t)(f->int_val & 0xFF);
      bf->width = (uint8_t)((f->int_val >> 8) & 0xFF);
    }
    return 0;
  }

  case AST_FIELD_ASSIGN: {
    /* name = variable name, name2 = field name, children[0] = value */
    if (stmt->child_count < 1)
      return -1;

    /* §16 register/mold field write: RMW on the variable's vreg. */
    {
      symbol_entry_t *bent = NULL;
      int bscope = sym_lookup_entry_both(ctx, stmt->name, &bent, NULL);
      if (bscope >= 0 && bent && bent->bit_type_name[0]) {
        bit_type_t *bt = find_bit_type(ctx, bent->bit_type_name);
        const bit_field_t *bf = find_bit_field(bt, stmt->name2);
        if (bt && bf) {
          int val = lower_expr(ctx, stmt->children[0]);
          if (val < 0)
            return -1;
          /* Load current value */
          uint32_t old_r;
          if (bscope == 1) {
            old_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(old_r), q_imm(bent->vreg),
                              q_none()));
          } else {
            old_r = bent->vreg;
          }
          uint32_t merged =
              emit_bit_insert(ctx, old_r, (uint32_t)val, bf->lo, bf->width);
          if (bscope == 1) {
            emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(), q_imm(bent->vreg),
                              q_vreg(merged)));
          } else {
            emit(ctx,
                 q_instr(Q_MOVE, q_vreg(bent->vreg), q_vreg(merged), q_none()));
          }
          return 0;
        }
      }
    }

    /* Load the record pointer */
    uint32_t idx;
    int scope = sym_lookup_both(ctx, stmt->name, &idx);
    if (scope < 0) {
      char buf[128];
      snprintf(buf, sizeof(buf), "field assign to undefined: %s", stmt->name);
      lower_error(ctx, stmt, buf);
      return -1;
    }
    uint32_t base_vreg;
    if (scope == 1) {
      base_vreg = fresh_vreg(ctx);
      emit(ctx,
           q_instr(Q_LOAD_GLOBAL, q_vreg(base_vreg), q_imm(idx), q_none()));
    } else {
      base_vreg = idx;
    }

    const record_type_t *resolved_rt = NULL;
    int offset = record_field_offset_for_symbol(ctx, stmt->name, stmt->name2,
                                                &resolved_rt);
    if (offset < 0) {
      if (lowering_strict_fields()) {
        char buf[128];
        if (resolved_rt)
          snprintf(buf, sizeof(buf), "unknown field: %s.%s",
                   resolved_rt->name, stmt->name2);
        else
          snprintf(buf, sizeof(buf), "unknown field: %s", stmt->name2);
        lower_error(ctx, stmt, buf);
        return -1;
      }
      return 0;
    }

    int val = lower_expr(ctx, stmt->children[0]);
    if (val < 0)
      return -1;

    uint32_t off_r = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
    emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val), q_vreg(base_vreg),
                      q_vreg(off_r)));
    return 0;
  }

  case AST_THROW: {
    /* §13.1 throw <expr> — set erx and jump to innermost revert */
    if (stmt->child_count == 0) {
      lower_error(ctx, stmt, "throw needs code");
      return -1;
    }
    int code = lower_expr(ctx, stmt->children[0]);
    if (code < 0)
      return -1;
    emit(ctx, q_instr(Q_THROW, q_none(), q_vreg((uint32_t)code), q_none()));
    return 0;
  }

  case AST_RESUME: {
    /* §13.7 resume retry | resume revert — only valid inside revert block.
     * VM halts with erx as exit if no active try frame. */
    if (stmt->int_val == 0) {
      emit(ctx, q_instr(Q_RESUME_RETRY, q_none(), q_none(), q_none()));
    } else {
      emit(ctx, q_instr(Q_RESUME_REVERT, q_none(), q_none(), q_none()));
    }
    return 0;
  }

  case AST_EMIT: {
    /* §13.7 emit LEVEL(args) — format a log line string at lower-time
     * and emit a runtime print. */
    char buf[512];
    size_t off = (size_t)snprintf(buf, sizeof(buf), "[%s]", stmt->name);
    for (uint32_t i = 0; i < stmt->child_count && off + 2 < sizeof(buf); i++) {
      const ast_node_t *a = stmt->children[i];
      buf[off++] = ' ';
      if (a->type == AST_LITERAL_STR) {
        size_t ln = strlen(a->name);
        if (off + ln >= sizeof(buf))
          ln = sizeof(buf) - off - 1;
        memcpy(buf + off, a->name, ln);
        off += ln;
      } else if (a->type == AST_LITERAL_INT) {
        off += (size_t)snprintf(buf + off, sizeof(buf) - off, "%lld",
                                (long long)a->int_val);
      } else if (a->type == AST_ERX_READ) {
        if (off + 4 < sizeof(buf)) {
          memcpy(buf + off, "$erx", 4);
          off += 4;
        }
      } else if (a->type == AST_IDENTIFIER) {
        size_t ln = strlen(a->name);
        if (off + ln + 1 < sizeof(buf)) {
          buf[off++] = '$';
          memcpy(buf + off, a->name, ln);
          off += ln;
        }
      }
    }
    buf[off] = '\0';
    uint32_t sidx = q_module_add_string(&ctx->module, buf);
    emit(ctx, q_instr(Q_EMIT_LOG, q_none(), q_imm((int64_t)sidx), q_none()));
    return 0;
  }

  case AST_TRY_BLOCK: {
    /* §13.7 local try block.
     *   children[0] = body block
     *   children[1] = optional AST_REVERT_BLOCK (child[0] = body)
     *   int_val bit0=has_timeout (ignored at runtime), bit1=has_isolate
     *   name = comma-joined isolate var list (if any)
     */
    uint32_t revert_L = fresh_label(ctx);
    uint32_t end_L = fresh_label(ctx);

    q_instruction_t begin = q_instr(Q_TRY_BEGIN, q_label(revert_L),
                                    q_imm((int64_t)stmt->int_val), q_none());
    emit(ctx, begin);

    /* isolate: snapshot listed vars (Copy scalars). */
    if (stmt->int_val & 2) {
      const char *s = stmt->name;
      while (*s) {
        char nm[AST_NAME_LEN];
        size_t n = 0;
        while (*s && *s != ',' && n + 1 < sizeof(nm))
          nm[n++] = *s++;
        nm[n] = '\0';
        if (*s == ',')
          s++;
        if (n == 0)
          continue;
        uint32_t vi;
        symbol_entry_t *ient = NULL;
        int sc = sym_lookup_entry_both(ctx, nm, &ient, &vi);
        if (sc >= 0 && ient) {
          /* §13.7 atomic vars are exempt from isolate: keep their
           * final mutation across resume retry / revert. */
          if (ient->is_atomic) {
            fprintf(stderr,
                    "note: variable '%s' is 'atomic' — skipped from "
                    "try(isolate:) snapshot (line %u)\n",
                    nm, stmt->line);
            continue;
          }
          emit(ctx, q_instr(Q_ISOLATE_SAVE, q_vreg(vi), q_imm(0), q_none()));
        }
      }
    }

    /* §11.12 W302 static check: any var mutated in the try body that
     * is neither in the isolate list nor marked `atomic` is flagged. */
    if (stmt->child_count > 0 && stmt->children[0]) {
      w302_walk_try_body(ctx, stmt->children[0], stmt->name,
                         (stmt->int_val & 2) != 0, stmt->line);
    }

    if (stmt->child_count > 0 && stmt->children[0])
      lower_stmt(ctx, stmt->children[0]);

    /* Normal exit path: pop frame, skip revert handler. */
    emit(ctx, q_instr(Q_TRY_END, q_none(), q_none(), q_none()));
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_L), q_none()));

    q_instruction_t rlbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    rlbl.patch_id = revert_L;
    emit(ctx, rlbl);

    if (stmt->child_count > 1 && stmt->children[1] &&
        stmt->children[1]->type == AST_REVERT_BLOCK &&
        stmt->children[1]->child_count > 0) {
      lower_stmt(ctx, stmt->children[1]->children[0]);
    }

    /* Fall-through from revert block → pop frame. */
    emit(ctx, q_instr(Q_TRY_END, q_none(), q_none(), q_none()));

    q_instruction_t elbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    elbl.patch_id = end_L;
    emit(ctx, elbl);
    return 0;
  }

  case AST_ENSURE_BLOCK:
  case AST_REVERT_BLOCK:
    /* Function-level epilogue blocks are consumed in lower_func_def;
     * if reached here they were misplaced. Treat as no-op. */
    return 0;

  case AST_BREAK: {
    if (ctx->loop_depth == 0) {
      lower_error(ctx, stmt, "break outside of loop");
      return -1;
    }
    uint32_t end = ctx->loop_end_labels[ctx->loop_depth - 1];
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end), q_none()));
    return 0;
  }
  case AST_CONTINUE:
  case AST_SKIP: {
    if (ctx->loop_depth == 0) {
      lower_error(ctx, stmt, "continue outside of loop");
      return -1;
    }
    uint32_t start = ctx->loop_start_labels[ctx->loop_depth - 1];
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(start), q_none()));
    return 0;
  }

  /* Module system — compile-time metadata, no runtime effect */
  case AST_IMPORT:
  case AST_MODULE:
  case AST_EXPORT:
  case AST_INCLUDE:
  case AST_TYPE_DECL:
    return 0;

  /* ═══════════════════════════════════════════════════
   * TASK A1: Pattern Match Decision Tree
   * ═══════════════════════════════════════════════════
   *
   * AST_CASE children[0] = subject expression
   * AST_CASE children[1..n] = AST_PATTERN_MATCH arms
   *   arm->name = pattern literal ("_" for wildcard)
   *   arm->int_val: -1 = wildcard, -2 = string, -3 = named, else integer
   *   arm->children[0] = body statement
   *
   * Strategy: Linear decision chain (CMP_EQ + JUMP_IF for each arm).
   * Wildcard arm "_" → unconditional jump (default case).
   */
  case AST_CASE: {
    if (stmt->child_count < 2)
      return -1;

    /* Lower subject expression once into a vreg */
    int subject = lower_expr(ctx, stmt->children[0]);
    if (subject < 0)
      return -1;

    uint32_t end_label = fresh_label(ctx);

    /* Allocate arm labels */
    uint32_t arm_count = stmt->child_count - 1;
    uint32_t small_arm_labels[64];
    uint32_t *arm_labels = small_arm_labels;
    if (arm_count > 64) {
      arm_labels = malloc(arm_count * sizeof(uint32_t));
      if (!arm_labels) {
        lower_error(ctx, stmt, "out of memory allocating case labels");
        return -1;
      }
    }
    for (uint32_t i = 0; i < arm_count; i++)
      arm_labels[i] = fresh_label(ctx);

    /* Phase 1: Emit comparison chain */
    int has_wildcard = 0;
    uint32_t wildcard_arm_idx = 0;

    for (uint32_t i = 0; i < arm_count; i++) {
      const ast_node_t *arm = stmt->children[i + 1];
      if (!arm)
        continue;

      if (strcmp(arm->name, "_") == 0) {
        /* Wildcard — unconditional jump (emit last) */
        has_wildcard = 1;
        wildcard_arm_idx = i;
        continue;
      }

      /* §21 Pattern kind dispatch.
       *   -1 = wildcard (handled above)
       *   -2 = string literal (compare via Q_STR_EQ)
       *   -3 = named pattern: try enum lookup first,
       *        else fall back to variable-compare. */
      uint32_t cmp_r = fresh_vreg(ctx);
      if (arm->int_val == -2) {
        /* String pattern: load string literal, compare. */
        uint32_t sidx = q_module_add_string(&ctx->module, (char *)arm->name);
        uint32_t pat_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(pat_r), q_str(sidx), q_none()));
        emit(ctx, q_instr(Q_STR_EQ, q_vreg(cmp_r), q_vreg((uint32_t)subject),
                          q_vreg(pat_r)));
      } else {
        int64_t pat_val = arm->int_val;
        if (arm->int_val == -3) {
          int found_val = -1;
          for (uint32_t ei = 0; ei < ctx->enum_type_count; ei++) {
            int64_t v = enum_lookup_variant(&ctx->enum_types[ei], arm->name);
            if (v >= 0) {
              found_val = (int)v;
              break;
            }
          }
          if (found_val >= 0) {
            /* Tagged union: compare discriminant at offset 0. */
            uint32_t off_r = fresh_vreg(ctx);
            uint32_t tag_r = fresh_vreg(ctx);
            uint32_t pat_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm(0), q_none()));
            emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(tag_r),
                              q_vreg((uint32_t)subject), q_vreg(off_r)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(pat_r), q_imm(found_val),
                              q_none()));
            emit(ctx, q_instr(Q_CMP_EQ, q_vreg(cmp_r), q_vreg(tag_r),
                              q_vreg(pat_r)));
            emit(ctx, q_instr(Q_JUMP_IF, q_none(), q_vreg(cmp_r),
                              q_label(arm_labels[i])));
            continue;
          } else {
            uint32_t idx;
            if (sym_lookup_both(ctx, arm->name, &idx) >= 0) {
              emit(ctx, q_instr(Q_CMP_EQ, q_vreg(cmp_r),
                                q_vreg((uint32_t)subject), q_vreg(idx)));
              emit(ctx, q_instr(Q_JUMP_IF, q_none(), q_vreg(cmp_r),
                                q_label(arm_labels[i])));
              continue;
            }
          }
        }
        uint32_t pat_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(pat_r), q_imm(pat_val), q_none()));
        emit(ctx, q_instr(Q_CMP_EQ, q_vreg(cmp_r), q_vreg((uint32_t)subject),
                          q_vreg(pat_r)));
      }
      emit(ctx,
           q_instr(Q_JUMP_IF, q_none(), q_vreg(cmp_r), q_label(arm_labels[i])));
    }

    /* Jump to wildcard arm if present, otherwise to end */
    if (has_wildcard) {
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(arm_labels[wildcard_arm_idx]),
                        q_none()));
    } else {
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_label), q_none()));
    }

    /* Phase 2: Emit arm bodies */
    for (uint32_t i = 0; i < arm_count; i++) {
      const ast_node_t *arm = stmt->children[i + 1];
      if (!arm)
        continue;

      /* Label for this arm */
      q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
      lbl.patch_id = arm_labels[i];
      emit(ctx, lbl);

      /* Save symbols table to support arm-local bindings */
      symbol_table_t *saved_syms = malloc(sizeof(*saved_syms));
      if (!saved_syms) {
        lower_error(ctx, stmt, "out of memory saving case scope");
        if (arm_labels != small_arm_labels) free(arm_labels);
        return -1;
      }
      *saved_syms = ctx->symbols;

      if (arm->name2[0] != '\0') {
        /* Bind payload variable: load value field at offset 8 from tagged
         * union (layout [tag|value]). Fallback: alias subject for bare ints. */
        uint32_t off_r = fresh_vreg(ctx);
        uint32_t payload_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm(8), q_none()));
        emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(payload_r),
                          q_vreg((uint32_t)subject), q_vreg(off_r)));
        sym_define(&ctx->symbols, arm->name2, payload_r, VIR_TYPE_I64);
      }

      /* Lower body — support multi-statement arms. */
      for (uint32_t bi = 0; bi < arm->child_count; bi++) {
        if (arm->children[bi])
          lower_stmt(ctx, arm->children[bi]);
      }

      /* Restore symbols table */
      ctx->symbols = *saved_syms;
      free(saved_syms);

      /* Jump to end after arm body */
      emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_label), q_none()));
    }

    /* End label */
    q_instruction_t end_lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    end_lbl.patch_id = end_label;
    emit(ctx, end_lbl);

    if (arm_labels != small_arm_labels) free(arm_labels);
    return 0;
  }

  default: {
    /* Try as expression statement */
    int result = lower_expr(ctx, stmt);
    (void)result;
    return 0;
  }
  }
}

/* ═══════════════════════════════════════════════════════
 * Function Lowering
 * ═══════════════════════════════════════════════════════ */

int lower_func_def(lower_ctx_t *ctx, const ast_node_t *func_def) {
  if (!func_def || func_def->type != AST_FUNC_DEF)
    return -1;


  q_function_t *func = q_module_add_func(&ctx->module, func_def->name);
  if (!func)
    return -1;
  if ((func_def->int_val & 0x8000) != 0) {
    return 0;
  }
  if (func->body_count > 0 || func->param_count > 0) {
    if (strcmp(func_def->name, "main") != 0) {
      return 0;
    }
    q_func_free(func);
    if (q_func_init(func, func_def->name) != 0)
      return -1;
  }

  ctx->current_func = func;

  /* Save parent symbols, create local scope */
  symbol_table_t *saved_syms = malloc(sizeof(*saved_syms));
  if (!saved_syms) {
    lower_error(ctx, func_def, "out of memory saving function scope");
    return -1;
  }
  *saved_syms = ctx->symbols;
  sym_init(&ctx->symbols);

  /* Save and reset vreg allocator - each function gets fresh vregs
   * BUT start after the global vreg range to avoid conflicts */
  q_vreg_alloc_t saved_vreg_alloc = ctx->vreg_alloc;
  uint32_t saved_label_counter = ctx->label_counter;
  
  /* Reset allocator per function so vregs don't grow indefinitely across functions.
   *
   * Critical: ensure param_vregs do NOT alias R0..R(Q_MAX_PARAMS-1).
   * Those low registers are used as the call-arg ABI slots — if a
   * parameter shares the same vreg, the caller's `Q_MOVE Ri, arg`
   * during a recursive (or any) call destroys that parameter, and
   * after the callee returns the VM only restores R0..R(nregs-1)
   * to their *call-time* values, not the caller's pre-arg-marshal
   * values, then overwrites R0 with the return value — corrupting
   * the parameter. Bumping the allocator past Q_MAX_PARAMS gives
   * the VM's `param_vregs[i] = R i` copy a real (distinct) target. */
  ctx->vreg_alloc.next_index = Q_MAX_PARAMS;
  ctx->label_counter = 0;

  /* Register parameters as vregs.
   * Convention: first N children are parameter names,
   * body + optional AST_REVERT_BLOCK + optional AST_ENSURE_BLOCK follow. */
  const ast_node_t *revert_node = NULL;
  const ast_node_t *ensure_node = NULL;
  uint32_t trailing = 0;
  for (uint32_t k = 0; k < func_def->child_count; k++) {
    uint32_t idx = func_def->child_count - 1 - k;
    ast_type_t ct = func_def->children[idx]->type;
    if (ct == AST_ENSURE_BLOCK) {
      ensure_node = func_def->children[idx];
      trailing++;
    } else if (ct == AST_REVERT_BLOCK) {
      revert_node = func_def->children[idx];
      trailing++;
    } else {
      break;
    }
  }
  uint32_t body_idx = func_def->child_count - 1 - trailing;
  for (uint32_t i = 0; i < body_idx && i < Q_MAX_PARAMS; i++) {
    const ast_node_t *param = func_def->children[i];
    if (param && param->type == AST_IDENTIFIER) {
      uint32_t pr = fresh_vreg(ctx);
      func->param_vregs[func->param_count] = pr;
      strncpy(func->param_names[func->param_count], param->name,
              Q_MAX_FUNC_NAME - 1);
      func->param_names[func->param_count][Q_MAX_FUNC_NAME - 1] = '\0';
      func->param_is_ref[func->param_count] =
          ((param->flags & AST_FLAG_REF_PARAM) != 0);
      func->param_count++;
      if (sym_define(&ctx->symbols, param->name, pr, VIR_TYPE_I64) >= 0 &&
          param->name2[0]) {
        symbol_entry_t *ent = NULL;
        if (sym_lookup_entry_both(ctx, param->name, &ent, NULL) < 0 || !ent)
          continue;
        strncpy(ent->type_name, param->name2, AST_NAME_LEN - 1);
        ent->type_name[AST_NAME_LEN - 1] = '\0';
        if (find_bit_type(ctx, param->name2)) {
          strncpy(ent->bit_type_name, param->name2, AST_NAME_LEN - 1);
          ent->bit_type_name[AST_NAME_LEN - 1] = '\0';
        }
      }
    }
  }

  int has_epilogue = (ensure_node || revert_node);
  uint32_t rev_L = 0, ens_L = 0;
  if (has_epilogue) {
    rev_L = fresh_label(ctx);
    ens_L = fresh_label(ctx);
    emit(ctx, q_instr(Q_TRY_BEGIN, q_label(rev_L), q_imm(0), q_none()));
  }

  /* Emit a start label (0) for tail-call optimization */
  q_instruction_t start_lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
  start_lbl.patch_id = 0;
  emit(ctx, start_lbl);

  ctx->pipeline_label_base = 0;

  /* Lower the body — HIR pipeline when VIR_PIPELINE=1, else classic. */
  if (func_def->child_count > body_idx) {
    const ast_node_t *body = func_def->children[body_idx];
    if (pipeline_enabled()) {
      uint32_t func_id =
          ctx->module.func_count > 0 ? ctx->module.func_count - 1 : 0;
      if (pipeline_lower_func_body(ctx, body, func_id) != 0) {
        lower_error(ctx, func_def, ctx->last_error[0] ? ctx->last_error
                                                      : "pipeline lowering failed");
        ctx->symbols = *saved_syms;
        free(saved_syms);
        ctx->current_func = NULL;
        ctx->vreg_alloc = saved_vreg_alloc;
        ctx->label_counter = saved_label_counter;
        return -1;
      }
    } else if (lower_stmt(ctx, body) != 0) {
      ctx->symbols = *saved_syms;
      free(saved_syms);
      ctx->current_func = NULL;
      ctx->vreg_alloc = saved_vreg_alloc;
      ctx->label_counter = saved_label_counter;
      return -1;
    }
  }

  if (has_epilogue) {
    /* Normal exit path: pop frame, jump to ensure block. */
    emit(ctx, q_instr(Q_TRY_END, q_none(), q_none(), q_none()));
    emit(ctx, q_instr(Q_JUMP, q_none(), q_label(ens_L), q_none()));

    /* Error path (revert_L): run revert body, then ensure body, then
     * rethrow to outer try (or halt with erx). */
    q_instruction_t rlbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    rlbl.patch_id = rev_L;
    emit(ctx, rlbl);
    if (revert_node && revert_node->child_count > 0) {
      lower_stmt(ctx, revert_node->children[0]);
    }
    if (ensure_node && ensure_node->child_count > 0) {
      lower_stmt(ctx, ensure_node->children[0]);
    }
    emit(ctx, q_instr(Q_RESUME_REVERT, q_none(), q_none(), q_none()));

    /* Normal ensure label. */
    q_instruction_t elbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
    elbl.patch_id = ens_L;
    emit(ctx, elbl);
    if (ensure_node && ensure_node->child_count > 0) {
      lower_stmt(ctx, ensure_node->children[0]);
    }
  }

  /* §4.8 NLL: release all transient and persistent borrows before
   * scope teardown so counters are consistent when the caller's
   * symbol table is restored. */
  ownership_release_unclaimed_stmt_borrows(ctx);
  ownership_release_all_borrows(ctx);

  /* §4.8 (2.11): auto-drop — emit Q_FREE for every local that owns a
   * move-type value and has NOT been moved out (consumed by assignment
   * to another owner). Parameters and non-move-type locals are skipped.
   * Q_FREE is a no-op on non-heap addresses, so this is safe even for
   * values the allocator did not hand out via Q_ALLOC. */
  for (uint32_t i = 0; i < ctx->symbols.count; i++) {
    const symbol_entry_t *e = &ctx->symbols.entries[i];
    if (e->is_move_type && !e->is_moved) {
      /* Skip entries that alias a parameter vreg (0..param_count-1). */
      int is_param = 0;
      for (uint32_t p = 0; p < func->param_count; p++) {
        if (func->param_vregs[p] == e->vreg) {
          is_param = 1;
          break;
        }
      }
      if (is_param)
        continue;
      emit(ctx, q_instr(Q_FREE, q_none(), q_vreg(e->vreg), q_none()));
    }
  }

  /* Restore parent scope */
  ctx->symbols = *saved_syms;
  free(saved_syms);
  ctx->current_func = NULL;
  
  /* Restore the parent function's vreg space so it continues where it left off!
   * This prevents vreg_alloc.next_index from growing forever and causing
   * huge vm->reg_count in the C-Core VM, which leads to massive overhead
   * during Q_CALL saving/restoring of registers. */
  ctx->vreg_alloc = saved_vreg_alloc;
  ctx->label_counter = saved_label_counter;
  
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Program Lowering
 * ═══════════════════════════════════════════════════════ */

/* Helper: lower a global var decl (registers in global_symbols) */
static int lower_global_var(lower_ctx_t *ctx, const ast_node_t *stmt) {
  if (!stmt)
    return 0;
  if (stmt->type != AST_VAR_DECL && stmt->type != AST_CONST_DECL)
    return 0;

  /* Assign next global index */

  /* Assign next global index */
  uint32_t gidx = ctx->global_index_counter++;
  sym_define(&ctx->global_symbols, stmt->name, gidx, VIR_TYPE_I64);

  symbol_entry_t *gent = NULL;
  sym_lookup_entry_both(ctx, stmt->name, &gent, NULL);
  if (gent && stmt->name2[0]) {
    strncpy(gent->type_name, stmt->name2, AST_NAME_LEN - 1);
    gent->type_name[AST_NAME_LEN - 1] = '\0';
  }
  if (gent && stmt->child_count > 0)
    symbol_infer_record_type_from_expr(ctx, gent, stmt->children[0]);

  /* If there is an initialiser expression, lower it */
  if (stmt->child_count > 0) {
    int val = lower_expr(ctx, stmt->children[0]);
    if (val >= 0) {
      emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(), q_imm(gidx),
                        q_vreg((uint32_t)val)));
    }
  } else {
    /* Store 0 to global */
    uint32_t zero = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
    emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(), q_imm(gidx), q_vreg(zero)));
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Metadata Classification
 * ═══════════════════════════════════════════════════════ */

int ast_is_metadata(ast_type_t type) {
  switch (type) {
  case AST_ENUM_DEF:
  case AST_RECORD_DEF:
  case AST_REGISTER_DEF:
  case AST_MOLD_DEF:
  case AST_MODULE:
  case AST_IMPORT:
  case AST_EXPORT:
  case AST_INCLUDE:
  case AST_TYPE_DECL:
  case AST_MORPH_DEF:
    return 1;
  default:
    return 0;
  }
}

/* ═══════════════════════════════════════════════════════
 * Include Resolution
 * ═══════════════════════════════════════════════════════
 *
 * Walk AST_INCLUDE nodes, load the referenced file, lex+parse
 * the content, and splice the resulting sub-AST children into
 * the parent program node (replacing the AST_INCLUDE node).
 */

int lower_resolve_includes(lower_ctx_t *ctx, ast_node_t *program) {
  if (!program || program->type != AST_PROGRAM)
    return -1;
  if (!ctx->include_reader)
    return 0; /* No reader → skip */

  /* Flatten top-level AST_BLOCK nodes */
  for (uint32_t i = 0; i < program->child_count; i++) {
    ast_node_t *child = program->children[i];
    if (child && child->type == AST_BLOCK) {
      uint32_t n_b = child->child_count;
      if (n_b == 0) {
        ast_free(child);
        for (uint32_t j = i; j + 1 < program->child_count; j++)
          program->children[j] = program->children[j + 1];
        program->child_count--;
        i--;
        continue;
      }
      program->children[i] = child->children[0];
      if (n_b > 1) {
        for (int32_t j = (int32_t)program->child_count - 1; j > (int32_t)i; j--) {
          if (j + n_b - 1 < AST_MAX_CHILDREN) {
            program->children[j + n_b - 1] = program->children[j];
          }
        }
        for (uint32_t k = 1; k < n_b; k++) {
          if (i + k < AST_MAX_CHILDREN) {
            program->children[i + k] = child->children[k];
          }
        }
        program->child_count += (n_b - 1);
      }
      free(child);
      i--;
    }
  }

  for (uint32_t i = 0; i < program->child_count; i++) {
    ast_node_t *child = program->children[i];
    if (!child || child->type != AST_INCLUDE)
      continue;

    const char *filename = child->name;

    /* Guard against double-include */
    int already = 0;
    for (uint32_t j = 0; j < ctx->included_file_count; j++) {
      if (strcmp(ctx->included_files[j], filename) == 0) {
        already = 1;
        break;
      }
    }
    if (already) {
      /* Remove the include node, shift remaining children */
      ast_free(child);
      for (uint32_t j = i; j + 1 < program->child_count; j++)
        program->children[j] = program->children[j + 1];
      program->child_count--;
      i--; /* Re-check this index */
      continue;
    }

    /* Mark as included */
    if (ctx->included_file_count < INCLUDE_MAX) {
      strncpy(ctx->included_files[ctx->included_file_count], filename, 255);
      ctx->included_files[ctx->included_file_count][255] = '\0';
      ctx->included_file_count++;
    }

    /* Read file contents via callback */
    size_t src_len = 0;
    char *src = ctx->include_reader(filename, &src_len, ctx->include_user_data);
    if (!src) {
      char buf[320];
      snprintf(buf, sizeof(buf), "include: cannot read '%s'", filename);
      lower_error(ctx, NULL, buf);
      return -1;
    }
    int dbg = (getenv("VIR_INCLUDE_DEBUG") != NULL);
    if (dbg)
      fprintf(stderr, "[resolve] read '%s' (%zu bytes)\n", filename, src_len);

    /* Lex + parse the included source */
    vir_lexer_t *lex = malloc(sizeof(vir_lexer_t));
    if (!lex) {
      free(src);
      return -1;
    }
    lexer_init(lex, src, src_len);
    if (lexer_tokenize(lex) != 0) {
      char buf[320];
      snprintf(buf, sizeof(buf), "include '%s': %s", filename, lex->error);
      lower_error(ctx, NULL, buf);
      lexer_free(lex);
      free(lex);
      free(src);
      return -1;
    }

    vir_parser_t parser;
    uint32_t file_id = DIAG_NO_FILE;
    if (g_diag_initialized) {
        file_id = diag_register_source(&g_parser_diag, filename, src, src_len);
    } else {
        diag_init(&g_parser_diag, STAGE_0_C_CORE, DIAG_FMT_TERMINAL);
        g_diag_initialized = 1;
        file_id = diag_register_source(&g_parser_diag, filename, src, src_len);
    }
    parser_init(&parser, lex->tokens, lex->token_count, file_id);
    ast_node_t *sub = parser_parse_program(&parser);
    if (!sub) {
      char buf[320];
      snprintf(buf, sizeof(buf), "include '%s' line %u: %s", filename,
               parser.error_line, parser.error);
      lower_error(ctx, NULL, buf);
      if (dbg)
        fprintf(stderr, "[resolve] parse FAIL %s\n", buf);
      lexer_free(lex);
      free(lex);
      free(src);
      return -1;
    }
    if (dbg)
      fprintf(stderr, "[resolve] parsed '%s' → %u children\n", filename,
              sub->child_count);
    if (dbg) {
      for (uint32_t ci = 0; ci < sub->child_count && ci < 32; ci++) {
        ast_node_t *c = sub->children[ci];
        fprintf(stderr, "[resolve]   child[%u] type=%d name='%s'\n", ci,
                c ? (int)c->type : -1, c && c->name ? c->name : "");
      }
      if (parser.error[0]) {
        fprintf(stderr, "[resolve]   parse_error line %u: %s\n",
                parser.error_line, parser.error);
      }
    }

    /* ── O(n) splice using memmove (one shift per include) ── */
    uint32_t n_new = sub->child_count;
    if (n_new == 0) {
      /* Empty file — just remove the include node */
      ast_free(child);
      if (i + 1 < program->child_count)
        memmove(&program->children[i], &program->children[i + 1],
                (program->child_count - i - 1) * sizeof(ast_node_t *));
      program->child_count--;
      i--;
    } else {
      uint32_t needed = program->child_count + n_new - 1;
      if (needed > AST_MAX_CHILDREN) {
        lower_error(ctx, NULL, "include: too many top-level nodes");
        ast_free(sub);
        lexer_free(lex);
        free(lex);
        free(src);
        return -1;
      }

      /* Single memmove to open space for n_new children at position i */
      if (n_new > 1 && i + 1 < program->child_count) {
        memmove(&program->children[i + n_new],
                &program->children[i + 1],
                (program->child_count - i - 1) * sizeof(ast_node_t *));
      }

      /* Place included children */
      for (uint32_t k = 0; k < n_new; k++) {
        program->children[i + k] = sub->children[k];
        sub->children[k] = NULL;
      }
      program->child_count = needed;

      /* Free original include node */
      ast_free(child);

      /* Re-process position i (first spliced child may itself be an include) */
      i--;
    }

    /* Clean up: free the sub-program shell + lex + src */
    sub->child_count = 0;
    ast_free(sub);
    lexer_free(lex);
    free(lex);
    free(src);
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Import / Module Processing
 * ═══════════════════════════════════════════════════════
 *
 * Walk the AST and populate:
 *   - module_aliases[]    from `import X` or `import X as Y`
 *   - imported_syms[]     from `from X import sym1, sym2`
 *   - ctx->module.name    from `module NAME`
 */

static int is_module_known(const ast_node_t *program, const char *module_name) {
  if (module_name && access(module_name, F_OK) == 0) {
    return 1;
  }
  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *c = program->children[i];
    if (c && c->type == AST_MODULE && strcmp(c->name, module_name) == 0) {
      return 1;
    }
  }
  for (uint32_t i = 0; i < g_parser_diag.file_count; i++) {
    if (!g_parser_diag.files[i].active) continue;
    const char *fn = g_parser_diag.files[i].filename;
    if (!fn) continue;
    const char *last_slash = strrchr(fn, '/');
    const char *base = last_slash ? (last_slash + 1) : fn;
    size_t name_len = strlen(module_name);
    if (strncmp(base, module_name, name_len) == 0) {
      if (base[name_len] == '\0' || strcmp(base + name_len, ".vri") == 0) {
        return 1;
      }
    }
  }
  return 0;
}

int lower_process_imports(lower_ctx_t *ctx, const ast_node_t *program) {
  if (!program || program->type != AST_PROGRAM)
    return -1;

  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (!child)
      continue;

    if (child->type == AST_MODULE) {
      /* Set the module name */
      strncpy(ctx->module.name, child->name, sizeof(ctx->module.name) - 1);
    } else if (child->type == AST_IMPORT && child->child_count == 0) {
      /* `import X` or `import X as Y` */
      if (!is_module_known(program, child->name)) {
        char buf[128];
        snprintf(buf, sizeof(buf), "module not found: '%s'", child->name);
        diag_entry_t *e = lower_error(ctx, child, buf);
        if (e) {
          diag_add_cause(&g_parser_diag, e, "Module file is missing or not included");
          diag_add_action(&g_parser_diag, e, "Ensure the module is in VIR_STDLIB or the correct path");
          diag_add_action(&g_parser_diag, e, "Check for typos in the module name");
        }
        return -1;
      }
      if (ctx->module_alias_count < MODULE_ALIAS_MAX) {
        uint32_t idx = ctx->module_alias_count++;
        strncpy(ctx->module_aliases[idx].original, child->name,
                AST_NAME_LEN - 1);
        if (child->name2[0] != '\0') {
          strncpy(ctx->module_aliases[idx].alias, child->name2,
                  AST_NAME_LEN - 1);
        } else {
          strncpy(ctx->module_aliases[idx].alias, child->name,
                  AST_NAME_LEN - 1);
        }
      }
    } else if (child->type == AST_IMPORT && child->child_count > 0) {
      /* `from X import sym1, sym2, ...` */
      if (!is_module_known(program, child->name)) {
        char buf[128];
        snprintf(buf, sizeof(buf), "module not found: '%s'", child->name);
        diag_entry_t *e = lower_error(ctx, child, buf);
        if (e) {
          diag_add_cause(&g_parser_diag, e, "Module file is missing or not included");
          diag_add_action(&g_parser_diag, e, "Ensure the module is in VIR_STDLIB or the correct path");
          diag_add_action(&g_parser_diag, e, "Check for typos in the module name");
        }
        return -1;
      }
      for (uint32_t j = 0; j < child->child_count; j++) {
        const ast_node_t *sym = child->children[j];
        if (!sym || sym->type != AST_IDENTIFIER)
          continue;
        if (ctx->imported_sym_count < IMPORTED_SYM_MAX) {
          uint32_t idx = ctx->imported_sym_count++;
          strncpy(ctx->imported_syms[idx].module, child->name,
                  AST_NAME_LEN - 1);
          strncpy(ctx->imported_syms[idx].symbol, sym->name, AST_NAME_LEN - 1);
        }
      }
    }
    /* AST_EXPORT is recorded but not processed further for now;
     * it marks which functions are publicly visible for linking. */
  }
  return 0;
}

int lower_program(lower_ctx_t *ctx, const ast_node_t *program) {
  if (!program || program->type != AST_PROGRAM)
    return -1;

  /* Process module metadata (import/export/module declarations) */
  if (lower_process_imports(ctx, program) < 0) {
    return -1;
  }

  int has_main_func = 0;
  int has_top_stmt = 0;

  /* Pass 0: register all enum/record type definitions first */
  /* Pass 0: register all enum/record type definitions first */
  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (!child)
      continue;
    if (child->type == AST_ENUM_DEF || child->type == AST_RECORD_DEF ||
        child->type == AST_REGISTER_DEF || child->type == AST_MOLD_DEF)
      lower_stmt(ctx, child);
  }

  /* Pass 0b: infer record return types for helper functions before locals are
   * initialised from calls such as `let ctx = lower_ctx_new(...)`. */
  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (!child)
      continue;
    /* if (strcmp(child->name, "vec_push") == 0) printf("[DEBUG] FOUND VEC_PUSH IN AST!\n"); */

    if (child->type == AST_FUNC_DEF) {
      infer_func_return_type(ctx, child);
    } else if (child->type == AST_RECORD_DEF) {
      for (uint32_t j = 0; j < child->child_count; j++) {
        if (child->children[j] && child->children[j]->type == AST_FUNC_DEF)
          infer_func_return_type(ctx, child->children[j]);
      }
    }
  }

  /* First pass: register all function names and enums */
  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (!child) continue;
    if (child->type == AST_ENUM_DEF || child->type == AST_RECORD_DEF) {
      lower_stmt(ctx, child); /* Registers the enum type */
    }
  }

  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (!child)
      continue;
    /* if (strcmp(child->name, "vec_push") == 0) printf("[DEBUG] FOUND VEC_PUSH IN AST!\n"); */

    if (child->type == AST_FUNC_DEF) {
      q_module_add_func(&ctx->module, child->name);
      if (strcmp(child->name, "main") == 0)
        has_main_func = 1;
    } else if (child->type == AST_RECORD_DEF) {
      /* Register methods */
      for (uint32_t j = 0; j < child->child_count; j++) {
        if (child->children[j]->type == AST_FUNC_DEF) {
          q_module_add_func(&ctx->module, child->children[j]->name);
        }
      }
    } else if (!ast_is_metadata(child->type)) {
      has_top_stmt = 1;
    }
  }

  /* Always create __vir_init__ if there are top-level statements,
   * so that global variables get correctly lowered and registered. */
  if (has_top_stmt) {
    q_function_t *init_fn = q_module_add_func(&ctx->module, "__vir_init__");
    if (!init_fn)
      return -1;
    ctx->current_func = init_fn;

  /* Lower all top-level var decls as globals */
  for (uint32_t i = 0; i < program->child_count; i++) {
    const ast_node_t *child = program->children[i];
    if (child &&
        (child->type == AST_VAR_DECL || child->type == AST_CONST_DECL)) {
      lower_global_var(ctx, child);
    }
      else if (child && child->type == AST_PORT_DECL) {
        /* §23.1 top-level port → global slot holding the handle */
        uint32_t gidx = ctx->global_index_counter++;
        if (sym_define(&ctx->global_symbols, child->name, gidx,
                       VIR_TYPE_I64) >= 0) {
          symbol_entry_t *ent = NULL;
          if (sym_lookup_entry_both(ctx, child->name, &ent, NULL) >= 0 && ent)
            ent->is_port = 1;
        }
        uint32_t r = fresh_vreg(ctx);
        int64_t cap = child->int_val > 0 ? child->int_val : 16;
        emit(ctx, q_instr(Q_PORT_NEW, q_vreg(r), q_imm(cap), q_none()));
        emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(), q_imm(gidx), q_vreg(r)));
      }
    }

    /* Return 0 from init */
    uint32_t rz = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(rz), q_imm(0), q_none()));
    emit(ctx, q_instr(Q_RET, q_none(), q_vreg(rz), q_none()));
    ctx->current_func = NULL;

    /* Second pass: lower all func def bodies */
    for (uint32_t i = 0; i < program->child_count; i++) {
      const ast_node_t *child = program->children[i];
      if (child && child->type == AST_FUNC_DEF)
        lower_func_def(ctx, child);
      else if (child && child->type == AST_RECORD_DEF) {
        for (uint32_t j = 0; j < child->child_count; j++) {
          if (child->children[j]->type == AST_FUNC_DEF)
            lower_func_def(ctx, child->children[j]);
        }
      }
    }
  } else if (has_main_func) {
    /* Only functions, no top-level statements */
    /* Second pass: lower bodies */
    for (uint32_t i = 0; i < program->child_count; i++) {
      const ast_node_t *child = program->children[i];
      if (child && child->type == AST_FUNC_DEF)
        lower_func_def(ctx, child);
      else if (child && child->type == AST_RECORD_DEF) {
        for (uint32_t j = 0; j < child->child_count; j++) {
          if (child->children[j]->type == AST_FUNC_DEF)
            lower_func_def(ctx, child->children[j]);
        }
      }
    }
  } else {
    /* No user main - wrap everything in __main__ */
    q_function_t *main_fn = q_module_add_func(&ctx->module, "__main__");
    if (!main_fn)
      return -1;
    ctx->current_func = main_fn;

    for (uint32_t i = 0; i < program->child_count; i++) {
      const ast_node_t *child = program->children[i];
      if (child && child->type != AST_FUNC_DEF && child->type != AST_RECORD_DEF)
        lower_stmt(ctx, child);
      else if (child && child->type == AST_RECORD_DEF) {
        /* Lower the record definition itself (fields/offsets) */
        lower_stmt(ctx, child);
        /* Note: methods are lowered in the second pass below */
      }
    }

    /* Implicit return 0 */
    uint32_t rz = fresh_vreg(ctx);
    emit(ctx, q_instr(Q_LOAD, q_vreg(rz), q_imm(0), q_none()));
    emit(ctx, q_instr(Q_RET, q_none(), q_vreg(rz), q_none()));
    ctx->current_func = NULL;

    /* Second pass: lower remaining func defs */
    for (uint32_t i = 0; i < program->child_count; i++) {
      const ast_node_t *child = program->children[i];
      if (child && child->type == AST_FUNC_DEF)
        lower_func_def(ctx, child);
      else if (child && child->type == AST_RECORD_DEF) {
        for (uint32_t j = 0; j < child->child_count; j++) {
          if (child->children[j]->type == AST_FUNC_DEF)
            lower_func_def(ctx, child->children[j]);
        }
      }
    }
  }

  return ctx->error_count > 0 ? -1 : 0;
}

/* ═══════════════════════════════════════════════════════
 * Liveness Analysis
 * ═══════════════════════════════════════════════════════
 *
 * Linear scan over the instruction array:
 *   - Definitions (dest) set the interval start.
 *   - Uses (src1, src2) extend the interval end.
 */

static live_interval_t *find_or_create_interval(lower_ctx_t *ctx,
                                                uint32_t vreg) {
  /* Search existing */
  for (uint32_t i = 0; i < ctx->interval_count; i++) {
    if (ctx->intervals[i].vreg == vreg)
      return &ctx->intervals[i];
  }
  /* Create new */
  if (ctx->interval_count >= LOWER_MAX_INTERVALS)
    return NULL;
  live_interval_t *iv = &ctx->intervals[ctx->interval_count++];
  iv->vreg = vreg;
  iv->start = UINT32_MAX;
  iv->end = 0;
  iv->phys_reg = -1;
  iv->spill_slot = -1;
  return iv;
}

static void update_interval(lower_ctx_t *ctx, const q_operand_t *op,
                            uint32_t instr_idx, int is_def) {
  if (op->type != OPERAND_VREG)
    return;

  live_interval_t *iv = find_or_create_interval(ctx, op->vreg);
  if (!iv)
    return;

  if (is_def && instr_idx < iv->start)
    iv->start = instr_idx;
  if (instr_idx > iv->end)
    iv->end = instr_idx;
  if (!is_def && instr_idx < iv->start)
    iv->start = instr_idx;
}

int lower_compute_liveness(lower_ctx_t *ctx, const q_function_t *func) {
  ctx->interval_count = 0;

  for (uint32_t i = 0; i < func->body_count; i++) {
    const q_instruction_t *instr = &func->body[i];
    update_interval(ctx, &instr->dest, i, 1); /* definition */
    update_interval(ctx, &instr->src1, i, 0); /* use        */
    update_interval(ctx, &instr->src2, i, 0); /* use        */
  }

  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Linear-Scan Register Allocation
 * ═══════════════════════════════════════════════════════
 *
 * Classic linear-scan algorithm:
 *   1. Sort intervals by start point
 *   2. Maintain an "active" list of intervals using physical regs
 *   3. When starting a new interval:
 *      a. Expire old intervals whose end < current start
 *      b. If a free register is available, assign it
 *      c. Otherwise, spill the interval with the furthest end
 *
 * Physical register pool = caller-saved registers from the ABI
 * (not RSP, RBP, etc.)
 */

/* Compare by start position */
static int cmp_interval_start(const void *a, const void *b) {
  const live_interval_t *ia = (const live_interval_t *)a;
  const live_interval_t *ib = (const live_interval_t *)b;
  if (ia->start != ib->start)
    return (ia->start < ib->start) ? -1 : 1;
  return 0;
}

int lower_regalloc_linear_scan(lower_ctx_t *ctx, uint32_t num_phys_regs) {
  if (num_phys_regs == 0 || ctx->interval_count == 0)
    return 0;

  /* Sort by start */
  qsort(ctx->intervals, ctx->interval_count, sizeof(live_interval_t),
        cmp_interval_start);

  /* Free register pool (bit-set) */
  uint32_t max_regs = (num_phys_regs > 32) ? 32 : num_phys_regs;
  uint32_t free_mask = (max_regs == 32) ? 0xFFFFFFFF : (1u << max_regs) - 1;

  /* Active list: indices into intervals[], sorted by end */
  uint32_t active[32];
  uint32_t active_count = 0;
  int next_spill = 0;

  for (uint32_t i = 0; i < ctx->interval_count; i++) {
    live_interval_t *cur = &ctx->intervals[i];

    /* Expire finished intervals */
    uint32_t new_active = 0;
    for (uint32_t a = 0; a < active_count; a++) {
      live_interval_t *act = &ctx->intervals[active[a]];
      if (act->end < cur->start) {
        /* Release physical register */
        if (act->phys_reg >= 0)
          free_mask |= (1u << (uint32_t)act->phys_reg);
      } else {
        active[new_active++] = active[a];
      }
    }
    active_count = new_active;

    /* Try to allocate a free register */
    if (free_mask != 0) {
      /* Find lowest set bit */
      uint32_t bit = 0;
      uint32_t tmp = free_mask;
      while ((tmp & 1) == 0) {
        bit++;
        tmp >>= 1;
      }

      cur->phys_reg = (int)bit;
      free_mask &= ~(1u << bit);

      /* Insert into active (sorted by end) */
      uint32_t pos = active_count;
      for (uint32_t a = 0; a < active_count; a++) {
        if (ctx->intervals[active[a]].end > cur->end) {
          pos = a;
          break;
        }
      }
      /* Shift right */
      for (uint32_t a = active_count; a > pos; a--)
        active[a] = active[a - 1];
      active[pos] = i;
      active_count++;
    } else {
      /* Spill: either this interval or the one with furthest end */
      if (active_count > 0) {
        uint32_t last = active[active_count - 1];
        live_interval_t *spill_cand = &ctx->intervals[last];
        if (spill_cand->end > cur->end) {
          /* Spill the active interval, give its reg to current */
          cur->phys_reg = spill_cand->phys_reg;
          spill_cand->phys_reg = -1;
          spill_cand->spill_slot = next_spill++;
          active_count--;

          /* Insert current into active */
          uint32_t pos = active_count;
          for (uint32_t a = 0; a < active_count; a++) {
            if (ctx->intervals[active[a]].end > cur->end) {
              pos = a;
              break;
            }
          }
          for (uint32_t a = active_count; a > pos; a--)
            active[a] = active[a - 1];
          active[pos] = i;
          active_count++;
        } else {
          /* Spill current */
          cur->phys_reg = -1;
          cur->spill_slot = next_spill++;
        }
      } else {
        cur->phys_reg = -1;
        cur->spill_slot = next_spill++;
      }
    }
  }

  return 0;
}

int lower_get_phys_reg(const lower_ctx_t *ctx, uint32_t vreg) {
  for (uint32_t i = 0; i < ctx->interval_count; i++) {
    if (ctx->intervals[i].vreg == vreg)
      return ctx->intervals[i].phys_reg;
  }
  return -1;
}

/* ═══════════════════════════════════════════════════════
 * Tail-Call Optimization
 * ═══════════════════════════════════════════════════════
 *
 * Post-lowering pass that scans the instruction body for the
 * pattern:   Q_CALL label  ;  Q_RET  [val]
 * and replaces it with:   Q_JUMP label
 *
 * This eliminates a stack frame for tail-position calls,
 * turning recursion into a loop.
 *
 * Also detects the self-recursive pattern:
 *   Q_CALL @self  ;  Q_RET
 * and converts it into:
 *   Q_JUMP @func_entry  (i.e. label 0 of the function)
 *
 * Returns the number of tail calls optimised.
 */

int lower_tco_pass(q_function_t *func, uint32_t func_idx) {
  if (!func || func->body_count < 2)
    return 0;

  int tco_count = 0;

  for (uint32_t i = 0; i + 1 < func->body_count; i++) {
    q_instruction_t *cur = &func->body[i];
    q_instruction_t *next = &func->body[i + 1];

    /* Pattern 1: call followed by return. Q_CALL is legacy label-based IR;
     * Q_CALL_FUNC is the newer function-index form. */
    if ((cur->opcode == Q_CALL_FUNC || cur->opcode == Q_CALL) &&
        next->opcode == Q_RET) {
      if (cur->opcode == Q_CALL_FUNC) {
        if (cur->src1.type != OPERAND_FUNC_IDX ||
            cur->src1.func_idx != func_idx)
          continue;
        cur->opcode = Q_TAILCALL_FUNC;
        cur->dest = q_none();
        cur->src2 = q_none();
      } else {
        cur->opcode = Q_JUMP;
        cur->dest = q_none();
        cur->src2 = q_none();
      }
      next->opcode = Q_NOP;
      tco_count++;
      i++;
      continue;
    }

    /* Pattern 2: Q_CALL_FUNC followed by Q_MOVE R0->rd, then Q_RET rd */
    if (i + 2 < func->body_count) {
      q_instruction_t *move = &func->body[i + 1];
      q_instruction_t *ret = &func->body[i + 2];

      if ((cur->opcode == Q_CALL_FUNC || cur->opcode == Q_CALL) &&
          move->opcode == Q_MOVE &&
          move->src1.type == OPERAND_VREG && move->src1.vreg == 0 &&
          move->dest.type == OPERAND_VREG && ret->opcode == Q_RET &&
          ret->src1.type == OPERAND_VREG && ret->src1.vreg == move->dest.vreg) {

        if (cur->opcode == Q_CALL_FUNC) {
          if (cur->src1.type != OPERAND_FUNC_IDX ||
              cur->src1.func_idx != func_idx)
            continue;
          cur->opcode = Q_TAILCALL_FUNC;
          cur->dest = q_none();
          cur->src2 = q_none();
        } else {
          cur->opcode = Q_JUMP;
          cur->dest = q_none();
          cur->src2 = q_none();
        }
        move->opcode = Q_NOP;
        ret->opcode = Q_NOP;
        tco_count++;
        i += 2;
        continue;
      }
    }
  }

  return tco_count;
}

/* ═══════════════════════════════════════════════════════
 * Module Access & Cleanup
 * ═══════════════════════════════════════════════════════ */

q_module_t *lower_get_module(lower_ctx_t *ctx) { return &ctx->module; }

/* ═══════════════════════════════════════════════════════
 * Spill Code Insertion
 * ═══════════════════════════════════════════════════════
 *
 * After register allocation, some virtual registers may have
 * phys_reg == -1 and a valid spill_slot.  This pass rewrites
 * the instruction stream so that:
 *
 *   - Before each USE of a spilled vreg, insert:
 *       Q_LOAD_WORD  spill_temp_reg, SP, spill_slot
 *     and rewrite the operand to reference spill_temp_reg.
 *
 *   - After each DEF of a spilled vreg, insert:
 *       Q_STORE_WORD spill_temp_reg, SP, spill_slot
 *
 * `spill_temp_reg` is a reserved physical register index used
 * as a scratch register for spill traffic (e.g., X16 on ARM64,
 * R11 on x86_64).
 *
 * Returns number of spill operations inserted.
 */

/* Helper: get spill slot for a vreg, or -1 if not spilled */
static int get_spill_slot(const lower_ctx_t *ctx, uint32_t vreg) {
  for (uint32_t i = 0; i < ctx->interval_count; i++) {
    if (ctx->intervals[i].vreg == vreg)
      return ctx->intervals[i].spill_slot;
  }
  return -1;
}

int lower_insert_spill_code(lower_ctx_t *ctx, q_function_t *func,
                            uint32_t spill_temp_reg) {
  if (!ctx || !func || func->body_count == 0)
    return 0;

  /* We'll build a new instruction buffer with spill loads/stores
   * inserted.  Worst case: 3x original size (load before each
   * src + store after each dest). */
  uint32_t max_new = func->body_count * 4 + 16;
  q_instruction_t *new_body =
      (q_instruction_t *)calloc(max_new, sizeof(q_instruction_t));
  if (!new_body)
    return -1;

  uint32_t out = 0;
  int spill_count = 0;

  for (uint32_t i = 0; i < func->body_count; i++) {
    q_instruction_t instr = func->body[i];
    int dest_spill = -1;

    /* Check src1: if spilled, insert LOAD before */
    if (instr.src1.type == OPERAND_VREG) {
      int slot = get_spill_slot(ctx, instr.src1.vreg);
      if (slot >= 0) {
        /* LOAD spill_temp_reg from stack slot */
        q_instruction_t load = q_instr(Q_LOAD_WORD, q_vreg(spill_temp_reg),
                                       q_vreg(29), /* frame pointer (x29/rbp) */
                                       q_imm((int64_t)(-(slot + 1) * 8)));
        if (out < max_new)
          new_body[out++] = load;
        /* Rewrite src1 to use spill_temp_reg */
        instr.src1.vreg = spill_temp_reg;
        spill_count++;
      }
    }

    /* Check src2: if spilled, insert LOAD before
     * (use spill_temp_reg + 1 to avoid conflict with src1) */
    if (instr.src2.type == OPERAND_VREG) {
      int slot = get_spill_slot(ctx, instr.src2.vreg);
      if (slot >= 0) {
        uint32_t temp2 = spill_temp_reg + 1;
        q_instruction_t load = q_instr(Q_LOAD_WORD, q_vreg(temp2), q_vreg(29),
                                       q_imm((int64_t)(-(slot + 1) * 8)));
        if (out < max_new)
          new_body[out++] = load;
        instr.src2.vreg = temp2;
        spill_count++;
      }
    }

    /* Check dest: record for post-instruction STORE */
    if (instr.dest.type == OPERAND_VREG) {
      dest_spill = get_spill_slot(ctx, instr.dest.vreg);
      if (dest_spill >= 0) {
        /* Rewrite dest to spill_temp_reg; we'll store after */
        instr.dest.vreg = spill_temp_reg;
      }
    }

    /* Emit the (possibly rewritten) instruction */
    if (out < max_new)
      new_body[out++] = instr;

    /* If dest was spilled, insert STORE after */
    if (dest_spill >= 0) {
      q_instruction_t store =
          q_instr(Q_STORE_WORD, q_vreg(spill_temp_reg), q_vreg(29),
                  q_imm((int64_t)(-(dest_spill + 1) * 8)));
      if (out < max_new)
        new_body[out++] = store;
      spill_count++;
    }
  }

  /* Replace the function body with the new one */
  free(func->body);
  func->body = new_body;
  func->body_count = out;
  func->body_capacity = max_new;

  return spill_count;
}

void lower_destroy(lower_ctx_t *ctx) {
  q_module_free(&ctx->module);
  memset(ctx, 0, sizeof(*ctx));
}
