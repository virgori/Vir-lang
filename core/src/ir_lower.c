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
#include "lexer.h"
#include "parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * AST Utilities
 * ═══════════════════════════════════════════════════════ */

ast_node_t *ast_new(ast_type_t type)
{
    ast_node_t *n = (ast_node_t *)calloc(1, sizeof(ast_node_t));
    if (n) n->type = type;
    return n;
}

int ast_add_child(ast_node_t *parent, ast_node_t *child)
{
    if (!parent || !child) return -1;
    if (parent->child_count >= AST_MAX_CHILDREN) {
        fprintf(stderr, "WARNING: AST_MAX_CHILDREN (%d) exceeded, dropping child\n",
                AST_MAX_CHILDREN);
        return -1;
    }
    parent->children[parent->child_count++] = child;
    return 0;
}

void ast_free(ast_node_t *node)
{
    if (!node) return;
    for (uint32_t i = 0; i < node->child_count; i++)
        ast_free(node->children[i]);
    free(node);
}

/* ═══════════════════════════════════════════════════════
 * Symbol Table
 * ═══════════════════════════════════════════════════════ */

void sym_init(symbol_table_t *st)
{
    memset(st, 0, sizeof(*st));
}

int sym_define(symbol_table_t *st, const char *name,
               uint32_t vreg, vir_type_t type)
{
    if (st->count >= SYM_MAX) return -1;
    /* Overwrite if exists */
    for (uint32_t i = 0; i < st->count; i++) {
        if (strcmp(st->entries[i].name, name) == 0) {
            st->entries[i].vreg = vreg;
            st->entries[i].type = type;
            return 0;
        }
    }
    strncpy(st->entries[st->count].name, name, AST_NAME_LEN - 1);
    st->entries[st->count].vreg = vreg;
    st->entries[st->count].type = type;
    st->count++;
    return 0;
}

int sym_lookup(const symbol_table_t *st, const char *name,
               uint32_t *vreg)
{
    for (uint32_t i = 0; i < st->count; i++) {
        if (strcmp(st->entries[i].name, name) == 0) {
            if (vreg) *vreg = st->entries[i].vreg;
            return 0;
        }
    }
    return -1;  /* not found */
}

/* ═══════════════════════════════════════════════════════
 * Lowering Context
 * ═══════════════════════════════════════════════════════ */

void lower_init(lower_ctx_t *ctx, const char *module_name)
{
    memset(ctx, 0, sizeof(*ctx));
    q_module_init(&ctx->module, module_name);
    q_vreg_alloc_init(&ctx->vreg_alloc);
    sym_init(&ctx->symbols);
    sym_init(&ctx->global_symbols);
}

static void lower_error(lower_ctx_t *ctx, const char *msg)
{
    snprintf(ctx->last_error, sizeof(ctx->last_error), "%s", msg);
    ctx->error_count++;
}

/* Allocate a fresh virtual register */
static uint32_t fresh_vreg(lower_ctx_t *ctx)
{
    return q_vreg_alloc_next(&ctx->vreg_alloc);
}

/* Lookup in local then global scope
 * Returns: 0 = found local, 1 = found global, -1 = not found
 * If found, *idx contains vreg (local) or global_index (global) */
static int sym_lookup_both(lower_ctx_t *ctx, const char *name, uint32_t *idx)
{
    if (sym_lookup(&ctx->symbols, name, idx) == 0)
        return 0;  /* local */
    if (sym_lookup(&ctx->global_symbols, name, idx) == 0)
        return 1;  /* global */
    return -1;     /* not found */
}

/* Allocate a fresh label id */
static uint32_t fresh_label(lower_ctx_t *ctx)
{
    return ctx->label_counter++;
}

/* Find function index by name (returns -1 if not found) */
static int find_func_index(lower_ctx_t *ctx, const char *name)
{
    for (uint32_t i = 0; i < ctx->module.func_count; i++) {
        if (strcmp(ctx->module.functions[i].name, name) == 0)
            return (int)i;
    }
    return -1;
}

/* Emit instruction into current function */
static void emit(lower_ctx_t *ctx, q_instruction_t instr)
{
    if (ctx->current_func)
        q_func_emit(ctx->current_func, instr);
}

/* ═══════════════════════════════════════════════════════
 * Enum / Record Type Lookup Helpers
 * ═══════════════════════════════════════════════════════ */

static enum_type_t *find_enum_type(lower_ctx_t *ctx, const char *name)
{
    for (uint32_t i = 0; i < ctx->enum_type_count; i++) {
        if (strcmp(ctx->enum_types[i].name, name) == 0)
            return &ctx->enum_types[i];
    }
    return NULL;
}

static int64_t enum_lookup_variant(const enum_type_t *et, const char *variant)
{
    for (uint32_t i = 0; i < et->variant_count; i++) {
        if (strcmp(et->variants[i].name, variant) == 0)
            return et->variants[i].value;
    }
    return -1;
}

static record_type_t *find_record_type(lower_ctx_t *ctx, const char *name)
{
    for (uint32_t i = 0; i < ctx->record_type_count; i++) {
        if (strcmp(ctx->record_types[i].name, name) == 0)
            return &ctx->record_types[i];
    }
    return NULL;
}

static int record_field_offset(const record_type_t *rt, const char *field)
{
    for (uint32_t i = 0; i < rt->field_count; i++) {
        if (strcmp(rt->fields[i].name, field) == 0)
            return (int)rt->fields[i].offset;
    }
    return -1;
}

/* ═══════════════════════════════════════════════════════
 * Expression Lowering
 * ═══════════════════════════════════════════════════════
 *
 * Each expression returns a vreg holding the result.
 */

int lower_expr(lower_ctx_t *ctx, const ast_node_t *expr)
{
    if (!expr) { lower_error(ctx, "null expr"); return -1; }

    switch (expr->type) {

    case AST_LITERAL_INT: {
        uint32_t r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(expr->int_val), q_none()));
        return (int)r;
    }

    case AST_IDENTIFIER: {
        uint32_t idx;
        int scope = sym_lookup_both(ctx, expr->name, &idx);
        if (scope < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "undefined variable: %s", expr->name);
            lower_error(ctx, buf);
            return -1;
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
            lower_error(ctx, "binop needs 2 operands");
            return -1;
        }
        int lhs = lower_expr(ctx, expr->children[0]);
        int rhs = lower_expr(ctx, expr->children[1]);
        if (lhs < 0 || rhs < 0) return -1;

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
            uint32_t rd   = fresh_vreg(ctx);
            uint32_t one  = fresh_vreg(ctx);
            uint32_t ic   = fresh_vreg(ctx);
            uint32_t cond = fresh_vreg(ctx);
            uint32_t loop_label = fresh_label(ctx);
            uint32_t end_label  = fresh_label(ctx);

            emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd),  q_imm(1), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(ic),  q_imm(0), q_none()));

            q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
            lbl.patch_id = loop_label;
            emit(ctx, lbl);

            emit(ctx, q_instr(Q_CMP_LT, q_vreg(cond), q_vreg(ic),
                              q_vreg((uint32_t)rhs)));
            emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(),
                              q_vreg(cond), q_label(end_label)));
            emit(ctx, q_instr(Q_MUL, q_vreg(rd), q_vreg(rd),
                              q_vreg((uint32_t)lhs)));
            emit(ctx, q_instr(Q_ADD, q_vreg(ic), q_vreg(ic), q_vreg(one)));
            emit(ctx, q_instr(Q_JUMP, q_none(), q_label(loop_label), q_none()));

            lbl.patch_id = end_label;
            emit(ctx, lbl);
            return (int)rd;
        }

        uint32_t rd = fresh_vreg(ctx);
        q_opcode_t op;
        switch (expr->op) {
        case OP_ADD: op = Q_ADD; break;
        case OP_SUB: op = Q_SUB; break;
        case OP_MUL: op = Q_MUL; break;
        case OP_DIV: op = Q_DIV; break;
        case OP_MOD: op = Q_MOD; break;
        case OP_AND: op = Q_AND; break;
        case OP_OR:  op = Q_OR;  break;
        case OP_XOR: op = Q_XOR; break;
        case OP_SHL: op = Q_SHL; break;
        case OP_SHR: op = Q_SHR; break;
        /* §26.2 AI operators: scalar fallback.
         * Future: detect tensor operands and emit VMUL/VFMA for SIMD. */
        case OP_MATMUL: op = Q_MUL; break;  /* a ** b → a * b for scalars */
        case OP_FMA:    op = Q_MUL; break;  /* a >< b → a * b for scalars */
        default:
            lower_error(ctx, "unsupported binop");
            return -1;
        }
        emit(ctx, q_instr(op, q_vreg(rd), q_vreg((uint32_t)lhs),
                          q_vreg((uint32_t)rhs)));
        return (int)rd;
    }

    case AST_COMPARE: {
        if (expr->child_count < 2) {
            lower_error(ctx, "compare needs 2 operands");
            return -1;
        }
        int lhs = lower_expr(ctx, expr->children[0]);
        int rhs = lower_expr(ctx, expr->children[1]);
        if (lhs < 0 || rhs < 0) return -1;

        uint32_t rd = fresh_vreg(ctx);
        q_opcode_t op;
        switch (expr->op) {
        case OP_EQ: op = Q_CMP_EQ; break;
        case OP_NE: {
            uint32_t eq = fresh_vreg(ctx);
            uint32_t one = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                              q_vreg((uint32_t)rhs)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
            emit(ctx, q_instr(Q_XOR, q_vreg(rd), q_vreg(eq), q_vreg(one)));
            return (int)rd;
        }
        case OP_GT: op = Q_CMP_GT; break;
        case OP_LT: op = Q_CMP_LT; break;
        case OP_GE: op = Q_CMP_GE; break;
        case OP_LE: op = Q_CMP_LE; break;
        /* 8.4 Safe equality: both operands must be non-nil (truthy) AND equal */
        case OP_SAFE_EQ: {
            uint32_t eq  = fresh_vreg(ctx);
            uint32_t zero = fresh_vreg(ctx);
            uint32_t la  = fresh_vreg(ctx);
            uint32_t lb  = fresh_vreg(ctx);
            uint32_t t1  = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                              q_vreg((uint32_t)rhs)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
            emit(ctx, q_instr(Q_CMP_GT, q_vreg(la), q_vreg((uint32_t)lhs), q_vreg(zero)));
            emit(ctx, q_instr(Q_CMP_GT, q_vreg(lb), q_vreg((uint32_t)rhs), q_vreg(zero)));
            emit(ctx, q_instr(Q_AND, q_vreg(t1), q_vreg(la), q_vreg(lb)));
            emit(ctx, q_instr(Q_AND, q_vreg(rd), q_vreg(t1), q_vreg(eq)));
            return (int)rd;
        }
        case OP_SAFE_NE: {
            uint32_t eq  = fresh_vreg(ctx);
            uint32_t zero = fresh_vreg(ctx);
            uint32_t la  = fresh_vreg(ctx);
            uint32_t lb  = fresh_vreg(ctx);
            uint32_t one = fresh_vreg(ctx);
            uint32_t neq = fresh_vreg(ctx);
            uint32_t t1  = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)lhs),
                              q_vreg((uint32_t)rhs)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
            emit(ctx, q_instr(Q_XOR, q_vreg(neq), q_vreg(eq), q_vreg(one)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
            emit(ctx, q_instr(Q_CMP_GT, q_vreg(la), q_vreg((uint32_t)lhs), q_vreg(zero)));
            emit(ctx, q_instr(Q_CMP_GT, q_vreg(lb), q_vreg((uint32_t)rhs), q_vreg(zero)));
            emit(ctx, q_instr(Q_AND, q_vreg(t1), q_vreg(la), q_vreg(lb)));
            emit(ctx, q_instr(Q_AND, q_vreg(rd), q_vreg(t1), q_vreg(neq)));
            return (int)rd;
        }
        default:
            lower_error(ctx, "unsupported comparison");
            return -1;
        }
        emit(ctx, q_instr(op, q_vreg(rd), q_vreg((uint32_t)lhs),
                          q_vreg((uint32_t)rhs)));
        return (int)rd;
    }

    case AST_CALL: {
        /* Function call: evaluate args, put in R0..Rn, call, result in R0 */
        int fidx = find_func_index(ctx, expr->name);
        if (fidx < 0) {
            /* Function not yet defined - will be forward declared */
            /* For now, record a placeholder; we'll fix up later or error */
            char buf[128];
            snprintf(buf, sizeof(buf), "undefined function: %s", expr->name);
            lower_error(ctx, buf);
            uint32_t rd = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            return (int)rd;
        }
        
        /* Evaluate arguments and move to R0..Rn */
        uint32_t nargs = expr->child_count;
        int arg_vregs[Q_MAX_PARAMS] = {0};
        for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
            int av = lower_expr(ctx, expr->children[i]);
            if (av < 0) return -1;
            arg_vregs[i] = av;
        }
        /* Move to R0..R(n-1) */
        for (uint32_t i = 0; i < nargs && i < Q_MAX_PARAMS; i++) {
            emit(ctx, q_instr(Q_MOVE, q_vreg(i), q_vreg((uint32_t)arg_vregs[i]), q_none()));
        }
        
        /* Emit call */
        emit(ctx, q_instr(Q_CALL_FUNC, q_none(), q_func_idx((uint32_t)fidx), q_none()));
        
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
        uint32_t str_idx = q_module_add_string(&ctx->module, expr->name);
        uint32_t r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_str(str_idx), q_none()));
        return (int)r;
    }

    case AST_LITERAL_FLOAT: {
        /* Store as int64 bit pattern for now */
        uint32_t r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm((int64_t)expr->float_val), q_none()));
        return (int)r;
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

    case AST_INDEX_ACCESS: {
        uint32_t arr_idx;
        int arr_scope = sym_lookup_both(ctx, expr->name, &arr_idx);
        if (arr_scope < 0) {
            lower_error(ctx, "undefined variable for index");
            return -1;
        }
        uint32_t arr_vreg;
        if (arr_scope == 1) {
            /* Global array - load into vreg first */
            arr_vreg = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(arr_vreg), q_imm(arr_idx), q_none()));
        } else {
            arr_vreg = arr_idx;
        }
        if (expr->child_count < 1) { lower_error(ctx, "index needs expr"); return -1; }
        int idx = lower_expr(ctx, expr->children[0]);
        if (idx < 0) return -1;
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_ARR_GET, q_vreg(rd), q_vreg(arr_vreg), q_vreg((uint32_t)idx)));
        return (int)rd;
    }

    case AST_BUILTIN_CALL: {
        int bid = expr->builtin_id;
        uint32_t rd = fresh_vreg(ctx);
        int a0 = -1, a1 = -1, a2 = -1;
        if (expr->child_count > 0) a0 = lower_expr(ctx, expr->children[0]);
        if (expr->child_count > 1) a1 = lower_expr(ctx, expr->children[1]);
        if (expr->child_count > 2) a2 = lower_expr(ctx, expr->children[2]);
        switch (bid) {
        case BUILTIN_LEN:
            if (a0 >= 0) emit(ctx, q_instr(Q_ARR_LEN, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_PUSH:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_ARR_PUSH, q_none(), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_ALLOC:
            if (a0 >= 0) emit(ctx, q_instr(Q_ALLOC, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_FREE_MEM:
            if (a0 >= 0) emit(ctx, q_instr(Q_FREE, q_none(), q_vreg((uint32_t)a0), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_READ8:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_LOAD_BYTE, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_WRITE8:
            if (a0 >= 0 && a1 >= 0 && a2 >= 0)
                emit(ctx, q_instr(Q_STORE_BYTE, q_vreg((uint32_t)a2), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_READ64:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_WRITE64:
            if (a0 >= 0 && a1 >= 0 && a2 >= 0)
                emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)a2), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_STR_LEN:
            if (a0 >= 0) emit(ctx, q_instr(Q_STR_LEN, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_STR_GET:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_STR_GET, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_STR_CAT:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_STR_CAT, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_STR_EQ:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_STR_EQ, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_FILE_OPEN:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_FILE_OPEN, q_vreg(rd), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            break;
        case BUILTIN_FILE_READ:
            if (a0 >= 0) emit(ctx, q_instr(Q_FILE_READ, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_FILE_WRITE:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_FILE_WRITE, q_none(), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_FILE_CLOSE:
            if (a0 >= 0) emit(ctx, q_instr(Q_FILE_CLOSE, q_none(), q_vreg((uint32_t)a0), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_FILE_WRITE_BYTE:
            if (a0 >= 0 && a1 >= 0)
                emit(ctx, q_instr(Q_FILE_WRITE_BYTE, q_none(), q_vreg((uint32_t)a0), q_vreg((uint32_t)a1)));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_EXIT:
            if (a0 >= 0) emit(ctx, q_instr(Q_EXIT, q_none(), q_vreg((uint32_t)a0), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_I_TO_STR:
            if (a0 >= 0) emit(ctx, q_instr(Q_I_TO_STR, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_STR_TO_I:
            if (a0 >= 0) emit(ctx, q_instr(Q_STR_TO_I, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_ARR_NEW:
            if (a0 >= 0) emit(ctx, q_instr(Q_ARR_NEW, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            else {
                uint32_t def = fresh_vreg(ctx);
                emit(ctx, q_instr(Q_LOAD, q_vreg(def), q_imm(16), q_none()));
                emit(ctx, q_instr(Q_ARR_NEW, q_vreg(rd), q_vreg(def), q_none()));
            }
            break;
        case BUILTIN_PRINT_STR:
            if (a0 >= 0) emit(ctx, q_instr(Q_PRINT_STR, q_none(), q_vreg((uint32_t)a0), q_none()));
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));
            break;
        case BUILTIN_GET_ARG:
            if (a0 >= 0) emit(ctx, q_instr(Q_GET_ARG, q_vreg(rd), q_vreg((uint32_t)a0), q_none()));
            break;
        case BUILTIN_ARG_COUNT:
            emit(ctx, q_instr(Q_ARG_COUNT, q_vreg(rd), q_none(), q_none()));
            break;
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
            lower_error(ctx, buf);
            return -1;
        }
        int64_t val = enum_lookup_variant(et, expr->name2);
        if (val < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "undefined enum variant: %s.%s",
                     expr->name, expr->name2);
            lower_error(ctx, buf);
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
        record_type_t *rt = find_record_type(ctx, expr->name);
        if (!rt) {
            char buf[128];
            snprintf(buf, sizeof(buf), "undefined record: %s", expr->name);
            lower_error(ctx, buf);
            return -1;
        }
        /* Allocate: size = field_count * 8 */
        uint32_t sz_r = fresh_vreg(ctx);
        uint32_t ptr_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(sz_r),
                          q_imm((int64_t)rt->field_count * 8), q_none()));
        emit(ctx, q_instr(Q_ALLOC, q_vreg(ptr_r), q_vreg(sz_r), q_none()));
        /* Store each field value at its offset */
        for (uint32_t i = 0; i < expr->child_count; i++) {
            const ast_node_t *child = expr->children[i];
            if (!child) continue;
            int field_off = record_field_offset(rt, child->name2);
            if (field_off < 0) {
                char buf[128];
                snprintf(buf, sizeof(buf), "unknown field: %s", child->name2);
                lower_error(ctx, buf);
                continue;
            }
            int val = lower_expr(ctx, child);
            if (val < 0) continue;
            uint32_t off_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(off_r),
                              q_imm((int64_t)field_off), q_none()));
            emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                              q_vreg(ptr_r), q_vreg(off_r)));
        }
        return (int)ptr_r;
    }

    case AST_FIELD_ACCESS: {
        /* children[0] = base expression, name = field/variant name.
         * Could be either: (a) enum access: EnumType.VARIANT
         *                  (b) record field access: var.field */
        if (expr->child_count < 1) {
            lower_error(ctx, "field access without target");
            return -1;
        }
        /* Check for enum access: child is an identifier matching an enum type */
        const ast_node_t *base_node = expr->children[0];
        if (base_node && base_node->type == AST_IDENTIFIER) {
            enum_type_t *et = find_enum_type(ctx, base_node->name);
            if (et) {
                int64_t val = enum_lookup_variant(et, expr->name);
                if (val >= 0) {
                    uint32_t r = fresh_vreg(ctx);
                    emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(val), q_none()));
                    return (int)r;
                }
                char buf[128];
                snprintf(buf, sizeof(buf), "unknown variant: %s.%s",
                         base_node->name, expr->name);
                lower_error(ctx, buf);
                return -1;
            }
        }
        /* Record field access */
        int base = lower_expr(ctx, expr->children[0]);
        if (base < 0) return -1;

        /* Search all record types for this field */
        int offset = -1;
        for (uint32_t i = 0; i < ctx->record_type_count && offset < 0; i++) {
            offset = record_field_offset(&ctx->record_types[i], expr->name);
        }
        if (offset < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "unknown field: %s", expr->name);
            lower_error(ctx, buf);
            return -1;
        }
        uint32_t off_r = fresh_vreg(ctx);
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
        emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd),
                          q_vreg((uint32_t)base), q_vreg(off_r)));
        return (int)rd;
    }

    /* 8.7 Safe access: base?.field → if base==0 then 0 else base.field */
    case AST_SAFE_ACCESS: {
        if (expr->child_count < 1) {
            lower_error(ctx, "safe access without target");
            return -1;
        }
        int base = lower_expr(ctx, expr->children[0]);
        if (base < 0) return -1;

        int offset = -1;
        for (uint32_t i = 0; i < ctx->record_type_count && offset < 0; i++) {
            offset = record_field_offset(&ctx->record_types[i], expr->name);
        }
        if (offset < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "unknown field: %s", expr->name);
            lower_error(ctx, buf);
            return -1;
        }

        uint32_t rd     = fresh_vreg(ctx);
        uint32_t zero   = fresh_vreg(ctx);
        uint32_t cond   = fresh_vreg(ctx);
        uint32_t off_r  = fresh_vreg(ctx);
        uint32_t nil_l  = fresh_label(ctx);
        uint32_t end_l  = fresh_label(ctx);

        emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
        emit(ctx, q_instr(Q_CMP_EQ, q_vreg(cond), q_vreg((uint32_t)base), q_vreg(zero)));
        emit(ctx, q_instr(Q_JUMP_IF, q_none(), q_vreg(cond), q_label(nil_l)));

        emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
        emit(ctx, q_instr(Q_LOAD_WORD, q_vreg(rd),
                          q_vreg((uint32_t)base), q_vreg(off_r)));
        emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end_l), q_none()));

        q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        lbl.patch_id = nil_l;
        emit(ctx, lbl);
        emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(0), q_none()));

        lbl.patch_id = end_l;
        emit(ctx, lbl);
        return (int)rd;
    }

    /* 8.8 Existence: expr? → 1 if expr != 0 else 0 */
    case AST_EXIST_CHECK: {
        if (expr->child_count < 1) {
            lower_error(ctx, "exist check without target");
            return -1;
        }
        int v = lower_expr(ctx, expr->children[0]);
        if (v < 0) return -1;
        uint32_t zero = fresh_vreg(ctx);
        uint32_t eq   = fresh_vreg(ctx);
        uint32_t one  = fresh_vreg(ctx);
        uint32_t rd   = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(zero), q_imm(0), q_none()));
        emit(ctx, q_instr(Q_CMP_EQ, q_vreg(eq), q_vreg((uint32_t)v), q_vreg(zero)));
        emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
        emit(ctx, q_instr(Q_XOR, q_vreg(rd), q_vreg(eq), q_vreg(one)));
        return (int)rd;
    }

    /* 8.10/8.11 Cast: for now pass through unchanged (int/float same repr) */
    case AST_CAST: {
        if (expr->child_count < 1) {
            lower_error(ctx, "cast without operand");
            return -1;
        }
        return lower_expr(ctx, expr->children[0]);
    }

    /* §8.9 Pattern match: expr :~ pattern
     *   - pattern is Ident (type name): currently always true (placeholder
     *     until runtime type tags exist)
     *   - pattern is literal int/str: equality test
     *   - otherwise: equality test on evaluated expression
     */
    case AST_PATTERN_MATCH: {
        if (expr->child_count < 2) {
            lower_error(ctx, "pattern match needs value and pattern");
            return -1;
        }
        const ast_node_t *pat = expr->children[1];
        if (pat && pat->type == AST_IDENTIFIER) {
            /* Type name pattern (e.g. `x :~ int`): placeholder → always 1.
             * A real implementation would check a runtime type tag. */
            uint32_t rd = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(rd), q_imm(1), q_none()));
            return (int)rd;
        }
        int lhs = lower_expr(ctx, expr->children[0]);
        int rhs = lower_expr(ctx, expr->children[1]);
        if (lhs < 0 || rhs < 0) return -1;
        uint32_t rd = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_CMP_EQ, q_vreg(rd), q_vreg((uint32_t)lhs),
                          q_vreg((uint32_t)rhs)));
        return (int)rd;
    }

    /* §24.4 Atomic load (lock expr / expr!!): passthrough for now.
     * Real implementation would emit LDAR (ARM64) / MOV+mfence (x86). */
    case AST_ATOMIC_LOAD: {
        if (expr->child_count < 1) {
            lower_error(ctx, "atomic load without operand");
            return -1;
        }
        return lower_expr(ctx, expr->children[0]);
    }

    default: {
        lower_error(ctx, "unsupported expression type");
        return -1;
    }
    }
}

/* ═══════════════════════════════════════════════════════
 * Statement Lowering
 * ═══════════════════════════════════════════════════════ */

int lower_stmt(lower_ctx_t *ctx, const ast_node_t *stmt)
{
    if (!stmt) return 0;

    switch (stmt->type) {

    case AST_VAR_DECL:
    case AST_CONST_DECL: {
        uint32_t r = fresh_vreg(ctx);
        sym_define(&ctx->symbols, stmt->name, r, VIR_TYPE_I64);
        /* If there is an initialiser expression, lower it */
        if (stmt->child_count > 0) {
            int val = lower_expr(ctx, stmt->children[0]);
            if (val >= 0 && (uint32_t)val != r) {
                emit(ctx, q_instr(Q_MOVE, q_vreg(r),
                                  q_vreg((uint32_t)val), q_none()));
            }
        } else {
            emit(ctx, q_instr(Q_LOAD, q_vreg(r), q_imm(0), q_none()));
        }
        return 0;
    }

    case AST_ASSIGN: {
        if (stmt->child_count < 1) return -1;
        uint32_t idx;
        int scope = sym_lookup_both(ctx, stmt->name, &idx);
        if (scope < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "assign to undefined: %s", stmt->name);
            lower_error(ctx, buf);
            return -1;
        }
        int val = lower_expr(ctx, stmt->children[0]);
        if (val < 0) return -1;
        if (scope == 1) {
            /* Global variable - emit Q_STORE_GLOBAL */
            emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(),
                              q_imm(idx), q_vreg((uint32_t)val)));
        } else {
            /* Local variable */
            if ((uint32_t)val != idx) {
                emit(ctx, q_instr(Q_MOVE, q_vreg(idx),
                                  q_vreg((uint32_t)val), q_none()));
            }
        }
        return 0;
    }

    case AST_INDEX_ASSIGN: {
        /* arr[idx] = val */
        if (stmt->child_count < 2) return -1;
        uint32_t arr_idx;
        int arr_scope = sym_lookup_both(ctx, stmt->name, &arr_idx);
        if (arr_scope < 0) {
            lower_error(ctx, "index assign to undefined variable");
            return -1;
        }
        uint32_t arr_vreg;
        if (arr_scope == 1) {
            /* Global - load into vreg first */
            arr_vreg = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(arr_vreg), q_imm(arr_idx), q_none()));
        } else {
            arr_vreg = arr_idx;
        }
        int idx = lower_expr(ctx, stmt->children[0]);
        int val = lower_expr(ctx, stmt->children[1]);
        if (idx < 0 || val < 0) return -1;
        emit(ctx, q_instr(Q_ARR_SET, q_vreg((uint32_t)val),
                          q_vreg(arr_vreg), q_vreg((uint32_t)idx)));
        return 0;
    }

    case AST_PRINT: {
        if (stmt->child_count < 1) return -1;
        int val = lower_expr(ctx, stmt->children[0]);
        if (val < 0) return -1;
        emit(ctx, q_instr(Q_PRINT, q_none(), q_vreg((uint32_t)val), q_none()));
        return 0;
    }

    case AST_RETURN: {
        if (stmt->child_count > 0) {
            int val = lower_expr(ctx, stmt->children[0]);
            if (val < 0) return -1;
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
        if (stmt->child_count < 2) return -1;

        int cond = lower_expr(ctx, stmt->children[0]);
        if (cond < 0) return -1;

        uint32_t else_label = fresh_label(ctx);
        uint32_t end_label  = fresh_label(ctx);

        emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(),
                          q_vreg((uint32_t)cond), q_label(else_label)));

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
        if (stmt->child_count < 2) return -1;

        /* Counter variable */
        uint32_t counter = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(counter), q_imm(0), q_none()));

        int limit = lower_expr(ctx, stmt->children[0]);
        if (limit < 0) return -1;

        uint32_t loop_label = fresh_label(ctx);
        uint32_t cont_label = fresh_label(ctx);
        uint32_t end_label  = fresh_label(ctx);

        /* Loop header */
        q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        lbl.patch_id = loop_label;
        emit(ctx, lbl);

        /* Check counter < limit */
        uint32_t cmp_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_CMP_LT, q_vreg(cmp_r),
                          q_vreg(counter), q_vreg((uint32_t)limit)));
        emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(),
                          q_vreg(cmp_r), q_label(end_label)));

        /* Push loop labels: continue → increment, break → end */
        ctx->loop_start_labels[ctx->loop_depth] = cont_label;
        ctx->loop_end_labels[ctx->loop_depth]   = end_label;
        ctx->loop_depth++;

        /* Body */
        lower_stmt(ctx, stmt->children[1]);

        ctx->loop_depth--;

        /* Continue target: increment counter */
        lbl.patch_id = cont_label;
        emit(ctx, lbl);
        uint32_t one = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
        emit(ctx, q_instr(Q_ADD, q_vreg(counter),
                          q_vreg(counter), q_vreg(one)));

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
        if (stmt->child_count < 2) return -1;

        uint32_t loop_label = fresh_label(ctx);
        uint32_t end_label  = fresh_label(ctx);

        q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        lbl.patch_id = loop_label;
        emit(ctx, lbl);

        int cond = lower_expr(ctx, stmt->children[0]);
        if (cond < 0) return -1;

        emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(),
                          q_vreg((uint32_t)cond), q_label(end_label)));

        /* Push loop labels for break/continue */
        ctx->loop_start_labels[ctx->loop_depth] = loop_label;
        ctx->loop_end_labels[ctx->loop_depth]   = end_label;
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

    case AST_FOR_RANGE: {
        /* for VAR in START..END then BODY end
         * children[0] = start, children[1] = end, children[2] = body
         * name = loop variable name
         * Desugar: var = start; while var < end: body; var = var + 1 */
        if (stmt->child_count < 3) return -1;

        int start_val = lower_expr(ctx, stmt->children[0]);
        if (start_val < 0) return -1;

        int end_val = lower_expr(ctx, stmt->children[1]);
        if (end_val < 0) return -1;

        /* Create loop variable */
        uint32_t loop_var = fresh_vreg(ctx);
        sym_define(&ctx->symbols, stmt->name, loop_var, VIR_TYPE_I64);
        emit(ctx, q_instr(Q_MOVE, q_vreg(loop_var),
                          q_vreg((uint32_t)start_val), q_none()));

        uint32_t loop_label = fresh_label(ctx);
        uint32_t end_label  = fresh_label(ctx);

        /* Loop header */
        q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        lbl.patch_id = loop_label;
        emit(ctx, lbl);

        /* Check loop_var < end */
        uint32_t cmp_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_CMP_LT, q_vreg(cmp_r),
                          q_vreg(loop_var), q_vreg((uint32_t)end_val)));
        emit(ctx, q_instr(Q_JUMP_IF_NOT, q_none(),
                          q_vreg(cmp_r), q_label(end_label)));

        uint32_t cont_label = fresh_label(ctx);

        /* Push loop labels: continue → increment, break → end */
        ctx->loop_start_labels[ctx->loop_depth] = cont_label;
        ctx->loop_end_labels[ctx->loop_depth]   = end_label;
        ctx->loop_depth++;

        /* Body */
        lower_stmt(ctx, stmt->children[2]);

        ctx->loop_depth--;

        /* Continue target: increment loop variable */
        lbl.patch_id = cont_label;
        emit(ctx, lbl);
        uint32_t one = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(one), q_imm(1), q_none()));
        emit(ctx, q_instr(Q_ADD, q_vreg(loop_var),
                          q_vreg(loop_var), q_vreg(one)));

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
            lower_error(ctx, "too many enum types");
            return -1;
        }
        enum_type_t *et = &ctx->enum_types[ctx->enum_type_count++];
        strncpy(et->name, stmt->name, AST_NAME_LEN - 1);
        et->variant_count = 0;
        for (uint32_t i = 0; i < stmt->child_count; i++) {
            const ast_node_t *v = stmt->children[i];
            if (!v || et->variant_count >= ENUM_MAX_VARIANTS) continue;
            enum_variant_t *ev = &et->variants[et->variant_count++];
            strncpy(ev->name, v->name, AST_NAME_LEN - 1);
            ev->value = v->int_val;
        }
        return 0;
    }

    case AST_RECORD_DEF: {
        /* Register record type with field offsets (compile-time only) */
        if (ctx->record_type_count >= RECORD_MAX_TYPES) {
            lower_error(ctx, "too many record types");
            return -1;
        }
        record_type_t *rt = &ctx->record_types[ctx->record_type_count++];
        strncpy(rt->name, stmt->name, AST_NAME_LEN - 1);
        rt->field_count = 0;
        for (uint32_t i = 0; i < stmt->child_count; i++) {
            const ast_node_t *f = stmt->children[i];
            if (!f || rt->field_count >= RECORD_MAX_FIELDS) continue;
            record_field_t *rf = &rt->fields[rt->field_count];
            strncpy(rf->name, f->name, AST_NAME_LEN - 1);
            rf->offset = rt->field_count;  /* offset in int64 units */
            rt->field_count++;
        }
        return 0;
    }

    case AST_FIELD_ASSIGN: {
        /* name = variable name, name2 = field name, children[0] = value */
        if (stmt->child_count < 1) return -1;

        /* Load the record pointer */
        uint32_t idx;
        int scope = sym_lookup_both(ctx, stmt->name, &idx);
        if (scope < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "field assign to undefined: %s", stmt->name);
            lower_error(ctx, buf);
            return -1;
        }
        uint32_t base_vreg;
        if (scope == 1) {
            base_vreg = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD_GLOBAL, q_vreg(base_vreg), q_imm(idx), q_none()));
        } else {
            base_vreg = idx;
        }

        /* Find field offset */
        int offset = -1;
        for (uint32_t i = 0; i < ctx->record_type_count && offset < 0; i++) {
            offset = record_field_offset(&ctx->record_types[i], stmt->name2);
        }
        if (offset < 0) {
            char buf[128];
            snprintf(buf, sizeof(buf), "unknown field: %s", stmt->name2);
            lower_error(ctx, buf);
            return -1;
        }

        int val = lower_expr(ctx, stmt->children[0]);
        if (val < 0) return -1;

        uint32_t off_r = fresh_vreg(ctx);
        emit(ctx, q_instr(Q_LOAD, q_vreg(off_r), q_imm((int64_t)offset), q_none()));
        emit(ctx, q_instr(Q_STORE_WORD, q_vreg((uint32_t)val),
                          q_vreg(base_vreg), q_vreg(off_r)));
        return 0;
    }

    case AST_BREAK: {
        if (ctx->loop_depth == 0) {
            lower_error(ctx, "break outside of loop");
            return -1;
        }
        uint32_t end = ctx->loop_end_labels[ctx->loop_depth - 1];
        emit(ctx, q_instr(Q_JUMP, q_none(), q_label(end), q_none()));
        return 0;
    }
    case AST_CONTINUE: {
        if (ctx->loop_depth == 0) {
            lower_error(ctx, "continue outside of loop");
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
        if (stmt->child_count < 2) return -1;

        /* Lower subject expression once into a vreg */
        int subject = lower_expr(ctx, stmt->children[0]);
        if (subject < 0) return -1;

        uint32_t end_label = fresh_label(ctx);

        /* Allocate arm labels */
        uint32_t arm_count = stmt->child_count - 1;
        uint32_t arm_labels[AST_MAX_CHILDREN];
        for (uint32_t i = 0; i < arm_count; i++)
            arm_labels[i] = fresh_label(ctx);

        /* Phase 1: Emit comparison chain */
        int has_wildcard = 0;
        uint32_t wildcard_arm_idx = 0;

        for (uint32_t i = 0; i < arm_count; i++) {
            const ast_node_t *arm = stmt->children[i + 1];
            if (!arm) continue;

            if (strcmp(arm->name, "_") == 0) {
                /* Wildcard — unconditional jump (emit last) */
                has_wildcard = 1;
                wildcard_arm_idx = i;
                continue;
            }

            /* Emit: CMP_EQ subject, pattern_val → tmp */
            uint32_t pat_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_LOAD, q_vreg(pat_r),
                              q_imm(arm->int_val), q_none()));
            uint32_t cmp_r = fresh_vreg(ctx);
            emit(ctx, q_instr(Q_CMP_EQ, q_vreg(cmp_r),
                              q_vreg((uint32_t)subject), q_vreg(pat_r)));
            emit(ctx, q_instr(Q_JUMP_IF, q_none(),
                              q_vreg(cmp_r), q_label(arm_labels[i])));
        }

        /* Jump to wildcard arm if present, otherwise to end */
        if (has_wildcard) {
            emit(ctx, q_instr(Q_JUMP, q_none(),
                              q_label(arm_labels[wildcard_arm_idx]), q_none()));
        } else {
            emit(ctx, q_instr(Q_JUMP, q_none(),
                              q_label(end_label), q_none()));
        }

        /* Phase 2: Emit arm bodies */
        for (uint32_t i = 0; i < arm_count; i++) {
            const ast_node_t *arm = stmt->children[i + 1];
            if (!arm) continue;

            /* Label for this arm */
            q_instruction_t lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
            lbl.patch_id = arm_labels[i];
            emit(ctx, lbl);

            /* Lower body */
            if (arm->child_count > 0) {
                lower_stmt(ctx, arm->children[0]);
            }

            /* Jump to end after arm body */
            emit(ctx, q_instr(Q_JUMP, q_none(),
                              q_label(end_label), q_none()));
        }

        /* End label */
        q_instruction_t end_lbl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        end_lbl.patch_id = end_label;
        emit(ctx, end_lbl);

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

int lower_func_def(lower_ctx_t *ctx, const ast_node_t *func_def)
{
    if (!func_def || func_def->type != AST_FUNC_DEF) return -1;

    q_function_t *func = q_module_add_func(&ctx->module, func_def->name);
    if (!func) return -1;

    ctx->current_func = func;

    /* Save parent symbols, create local scope */
    symbol_table_t saved_syms = ctx->symbols;
    sym_init(&ctx->symbols);
    
    /* Save and reset vreg allocator - each function gets fresh vregs
     * BUT start after the global vreg range to avoid conflicts */
    q_vreg_alloc_t saved_vreg_alloc = ctx->vreg_alloc;
    /* Don't reset - keep incrementing so vregs don't overlap across functions
     * This way globals get low vregs, each function gets a fresh range */

    /* Register parameters as vregs.
     * Convention: first N children are parameter names,
     * last child is the body block. */
    uint32_t body_idx = func_def->child_count - 1;
    for (uint32_t i = 0; i < body_idx && i < Q_MAX_PARAMS; i++) {
        const ast_node_t *param = func_def->children[i];
        if (param && param->type == AST_IDENTIFIER) {
            uint32_t pr = fresh_vreg(ctx);
            func->param_vregs[func->param_count] = pr;
            func->param_count++;
            sym_define(&ctx->symbols, param->name, pr, VIR_TYPE_I64);
        }
    }

    /* Lower the body */
    if (func_def->child_count > 0) {
        lower_stmt(ctx, func_def->children[body_idx]);
    }

    /* Restore parent scope */
    ctx->symbols = saved_syms;
    ctx->current_func = NULL;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Program Lowering
 * ═══════════════════════════════════════════════════════ */

/* Helper: lower a global var decl (registers in global_symbols) */
static int lower_global_var(lower_ctx_t *ctx, const ast_node_t *stmt)
{
    if (!stmt) return 0;
    if (stmt->type != AST_VAR_DECL && stmt->type != AST_CONST_DECL) return 0;

    /* Assign next global index */
    uint32_t gidx = ctx->global_index_counter++;
    sym_define(&ctx->global_symbols, stmt->name, gidx, VIR_TYPE_I64);
    
    /* If there is an initialiser expression, lower it */
    if (stmt->child_count > 0) {
        int val = lower_expr(ctx, stmt->children[0]);
        if (val >= 0) {
            emit(ctx, q_instr(Q_STORE_GLOBAL, q_none(),
                              q_imm(gidx), q_vreg((uint32_t)val)));
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

int ast_is_metadata(ast_type_t type)
{
    switch (type) {
    case AST_ENUM_DEF:
    case AST_RECORD_DEF:
    case AST_MODULE:
    case AST_IMPORT:
    case AST_EXPORT:
    case AST_INCLUDE:
    case AST_TYPE_DECL:
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

int lower_resolve_includes(lower_ctx_t *ctx, ast_node_t *program)
{
    if (!program || program->type != AST_PROGRAM) return -1;
    if (!ctx->include_reader) return 0;  /* No reader → skip */

    for (uint32_t i = 0; i < program->child_count; i++) {
        ast_node_t *child = program->children[i];
        if (!child || child->type != AST_INCLUDE) continue;

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
            i--;  /* Re-check this index */
            continue;
        }

        /* Mark as included */
        if (ctx->included_file_count < INCLUDE_MAX) {
            strncpy(ctx->included_files[ctx->included_file_count],
                    filename, 255);
            ctx->included_files[ctx->included_file_count][255] = '\0';
            ctx->included_file_count++;
        }

        /* Read file contents via callback */
        size_t src_len = 0;
        char *src = ctx->include_reader(filename, &src_len,
                                         ctx->include_user_data);
        if (!src) {
            char buf[320];
            snprintf(buf, sizeof(buf), "include: cannot read '%s'", filename);
            lower_error(ctx, buf);
            return -1;
        }

        /* Lex + parse the included source */
        vir_lexer_t *lex = malloc(sizeof(vir_lexer_t));
        if (!lex) { free(src); return -1; }
        lexer_init(lex, src, src_len);
        if (lexer_tokenize(lex) != 0) {
            char buf[320];
            snprintf(buf, sizeof(buf), "include '%s': %s",
                     filename, lex->error);
            lower_error(ctx, buf);
            lexer_free(lex);
            free(lex);
            free(src);
            return -1;
        }

        vir_parser_t parser;
        parser_init(&parser, lex->tokens, lex->token_count);
        ast_node_t *sub = parser_parse_program(&parser);
        if (!sub) {
            char buf[320];
            snprintf(buf, sizeof(buf), "include '%s' line %u: %s",
                     filename, parser.error_line, parser.error);
            lower_error(ctx, buf);
            lexer_free(lex);
            free(lex);
            free(src);
            return -1;
        }

        /* Splice: replace AST_INCLUDE node with sub-program's children.
         * We need to make room: inserting (sub->child_count - 1) extra
         * nodes at position i. */
        uint32_t n_new = sub->child_count;
        if (n_new == 0) {
            /* Empty file — just remove the include node */
            ast_free(child);
            for (uint32_t j = i; j + 1 < program->child_count; j++)
                program->children[j] = program->children[j + 1];
            program->child_count--;
            i--;
        } else {
            /* Check capacity */
            uint32_t needed = program->child_count + n_new - 1;
            if (needed > AST_MAX_CHILDREN) {
                lower_error(ctx, "include: too many top-level nodes");
                ast_free(sub);
                lexer_free(lex);
                free(lex);
                free(src);
                return -1;
            }

            /* Shift existing children right by (n_new - 1) */
            if (n_new > 1) {
                for (uint32_t j = program->child_count - 1; j > i; j--)
                    program->children[j + n_new - 1] = program->children[j];
            }

            /* Place included children, clear their parent refs */
            for (uint32_t k = 0; k < n_new; k++) {
                program->children[i + k] = sub->children[k];
                sub->children[k] = NULL;  /* Prevent double-free */
            }
            program->child_count = needed;

            /* Free the original include node (not the spliced children) */
            ast_free(child);

            /* Recursively resolve includes in spliced content */
            /* (skip current: inner includes will be picked up naturally
             *  since we'll re-iterate at index i) */
            i--;  /* Re-process from this position */
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

int lower_process_imports(lower_ctx_t *ctx, const ast_node_t *program)
{
    if (!program || program->type != AST_PROGRAM) return -1;

    for (uint32_t i = 0; i < program->child_count; i++) {
        const ast_node_t *child = program->children[i];
        if (!child) continue;

        if (child->type == AST_MODULE) {
            /* Set the module name */
            strncpy(ctx->module.name, child->name,
                    sizeof(ctx->module.name) - 1);
        } else if (child->type == AST_IMPORT && child->child_count == 0) {
            /* `import X` or `import X as Y` */
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
            for (uint32_t j = 0; j < child->child_count; j++) {
                const ast_node_t *sym = child->children[j];
                if (!sym || sym->type != AST_IDENTIFIER) continue;
                if (ctx->imported_sym_count < IMPORTED_SYM_MAX) {
                    uint32_t idx = ctx->imported_sym_count++;
                    strncpy(ctx->imported_syms[idx].module, child->name,
                            AST_NAME_LEN - 1);
                    strncpy(ctx->imported_syms[idx].symbol, sym->name,
                            AST_NAME_LEN - 1);
                }
            }
        }
        /* AST_EXPORT is recorded but not processed further for now;
         * it marks which functions are publicly visible for linking. */
    }
    return 0;
}

int lower_program(lower_ctx_t *ctx, const ast_node_t *program)
{
    if (!program || program->type != AST_PROGRAM) return -1;

    /* Process module metadata (import/export/module declarations) */
    lower_process_imports(ctx, program);

    int has_main_func = 0;
    int has_top_stmt = 0;

    /* Pass 0: register all enum/record type definitions first */
    for (uint32_t i = 0; i < program->child_count; i++) {
        const ast_node_t *child = program->children[i];
        if (!child) continue;
        if (child->type == AST_ENUM_DEF || child->type == AST_RECORD_DEF)
            lower_stmt(ctx, child);
    }

    /* First pass: register all function names */
    for (uint32_t i = 0; i < program->child_count; i++) {
        const ast_node_t *child = program->children[i];
        if (!child) continue;
        if (child->type == AST_FUNC_DEF) {
            q_module_add_func(&ctx->module, child->name);
            if (strcmp(child->name, "main") == 0)
                has_main_func = 1;
        } else if (!ast_is_metadata(child->type)) {
            has_top_stmt = 1;
        }
    }

    /* If there are top-level statements AND a user main,
     * we need to lower globals in __vir_init__ first */
    /* If there are top-level statements AND a user main,
     * we need to lower globals in __vir_init__ first */
    if (has_top_stmt && has_main_func) {
        q_function_t *init_fn = q_module_add_func(&ctx->module, "__vir_init__");
        if (!init_fn) return -1;
        ctx->current_func = init_fn;

        /* Lower all top-level var decls as globals */
        for (uint32_t i = 0; i < program->child_count; i++) {
            const ast_node_t *child = program->children[i];
            if (child && (child->type == AST_VAR_DECL || child->type == AST_CONST_DECL))
                lower_global_var(ctx, child);
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
        }
    } else if (has_main_func) {
        /* Only functions, no top-level statements */
        /* Second pass: lower bodies */
        for (uint32_t i = 0; i < program->child_count; i++) {
            const ast_node_t *child = program->children[i];
            if (child && child->type == AST_FUNC_DEF)
                lower_func_def(ctx, child);
        }
    } else {
        /* No user main - wrap everything in __main__ */
        q_function_t *main_fn = q_module_add_func(&ctx->module, "__main__");
        if (!main_fn) return -1;
        ctx->current_func = main_fn;

        for (uint32_t i = 0; i < program->child_count; i++) {
            const ast_node_t *child = program->children[i];
            if (child && child->type != AST_FUNC_DEF)
                lower_stmt(ctx, child);
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
                                                 uint32_t vreg)
{
    /* Search existing */
    for (uint32_t i = 0; i < ctx->interval_count; i++) {
        if (ctx->intervals[i].vreg == vreg)
            return &ctx->intervals[i];
    }
    /* Create new */
    if (ctx->interval_count >= LOWER_MAX_INTERVALS) return NULL;
    live_interval_t *iv = &ctx->intervals[ctx->interval_count++];
    iv->vreg       = vreg;
    iv->start      = UINT32_MAX;
    iv->end        = 0;
    iv->phys_reg   = -1;
    iv->spill_slot = -1;
    return iv;
}

static void update_interval(lower_ctx_t *ctx, const q_operand_t *op,
                             uint32_t instr_idx, int is_def)
{
    if (op->type != OPERAND_VREG) return;

    live_interval_t *iv = find_or_create_interval(ctx, op->vreg);
    if (!iv) return;

    if (is_def && instr_idx < iv->start) iv->start = instr_idx;
    if (instr_idx > iv->end) iv->end = instr_idx;
    if (!is_def && instr_idx < iv->start) iv->start = instr_idx;
}

int lower_compute_liveness(lower_ctx_t *ctx, const q_function_t *func)
{
    ctx->interval_count = 0;

    for (uint32_t i = 0; i < func->body_count; i++) {
        const q_instruction_t *instr = &func->body[i];
        update_interval(ctx, &instr->dest, i, 1);  /* definition */
        update_interval(ctx, &instr->src1, i, 0);  /* use        */
        update_interval(ctx, &instr->src2, i, 0);  /* use        */
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
static int cmp_interval_start(const void *a, const void *b)
{
    const live_interval_t *ia = (const live_interval_t *)a;
    const live_interval_t *ib = (const live_interval_t *)b;
    if (ia->start != ib->start)
        return (ia->start < ib->start) ? -1 : 1;
    return 0;
}

int lower_regalloc_linear_scan(lower_ctx_t *ctx, uint32_t num_phys_regs)
{
    if (num_phys_regs == 0 || ctx->interval_count == 0) return 0;

    /* Sort by start */
    qsort(ctx->intervals, ctx->interval_count,
          sizeof(live_interval_t), cmp_interval_start);

    /* Free register pool (bit-set) */
    uint32_t max_regs = (num_phys_regs > 32) ? 32 : num_phys_regs;
    uint32_t free_mask = (max_regs == 32) ? 0xFFFFFFFF
                         : (1u << max_regs) - 1;

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
            while ((tmp & 1) == 0) { bit++; tmp >>= 1; }

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
                            pos = a; break;
                        }
                    }
                    for (uint32_t a = active_count; a > pos; a--)
                        active[a] = active[a - 1];
                    active[pos] = i;
                    active_count++;
                } else {
                    /* Spill current */
                    cur->phys_reg   = -1;
                    cur->spill_slot = next_spill++;
                }
            } else {
                cur->phys_reg   = -1;
                cur->spill_slot = next_spill++;
            }
        }
    }

    return 0;
}

int lower_get_phys_reg(const lower_ctx_t *ctx, uint32_t vreg)
{
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

int lower_tco_pass(q_function_t *func)
{
    if (!func || func->body_count < 2) return 0;

    int tco_count = 0;

    for (uint32_t i = 0; i + 1 < func->body_count; i++) {
        q_instruction_t *cur  = &func->body[i];
        q_instruction_t *next = &func->body[i + 1];

        /* Pattern: Q_CALL ... followed by Q_RET */
        if (cur->opcode == Q_CALL && next->opcode == Q_RET) {
            /*
             * Convert:
             *   Q_CALL  target
             *   Q_RET   [retval]
             * Into:
             *   Q_JUMP  target
             *   Q_NOP
             *
             * The jump target comes from the call's src1
             * (label or function reference).
             */
            cur->opcode = Q_JUMP;
            /* Keep src1 as the jump target (label) */
            cur->dest = q_none();
            cur->src2 = q_none();

            /* NOP out the RET */
            next->opcode = Q_NOP;
            next->dest   = q_none();
            next->src1   = q_none();
            next->src2   = q_none();

            tco_count++;
            i++;  /* skip the NOP'd RET */
        }
    }

    return tco_count;
}

/* ═══════════════════════════════════════════════════════
 * Module Access & Cleanup
 * ═══════════════════════════════════════════════════════ */

q_module_t *lower_get_module(lower_ctx_t *ctx)
{
    return &ctx->module;
}

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
static int get_spill_slot(const lower_ctx_t *ctx, uint32_t vreg)
{
    for (uint32_t i = 0; i < ctx->interval_count; i++) {
        if (ctx->intervals[i].vreg == vreg)
            return ctx->intervals[i].spill_slot;
    }
    return -1;
}

int lower_insert_spill_code(lower_ctx_t *ctx, q_function_t *func,
                            uint32_t spill_temp_reg)
{
    if (!ctx || !func || func->body_count == 0) return 0;

    /* We'll build a new instruction buffer with spill loads/stores
     * inserted.  Worst case: 3x original size (load before each
     * src + store after each dest). */
    uint32_t max_new = func->body_count * 4 + 16;
    q_instruction_t *new_body = (q_instruction_t *)calloc(
        max_new, sizeof(q_instruction_t));
    if (!new_body) return -1;

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
                q_instruction_t load = q_instr(
                    Q_LOAD_WORD,
                    q_vreg(spill_temp_reg),
                    q_vreg(29),  /* frame pointer (x29/rbp) */
                    q_imm((int64_t)(-(slot + 1) * 8)));
                if (out < max_new) new_body[out++] = load;
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
                q_instruction_t load = q_instr(
                    Q_LOAD_WORD,
                    q_vreg(temp2),
                    q_vreg(29),
                    q_imm((int64_t)(-(slot + 1) * 8)));
                if (out < max_new) new_body[out++] = load;
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
        if (out < max_new) new_body[out++] = instr;

        /* If dest was spilled, insert STORE after */
        if (dest_spill >= 0) {
            q_instruction_t store = q_instr(
                Q_STORE_WORD,
                q_vreg(spill_temp_reg),
                q_vreg(29),
                q_imm((int64_t)(-(dest_spill + 1) * 8)));
            if (out < max_new) new_body[out++] = store;
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

void lower_destroy(lower_ctx_t *ctx)
{
    q_module_free(&ctx->module);
    memset(ctx, 0, sizeof(*ctx));
}
