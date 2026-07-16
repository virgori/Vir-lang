/*
 * parser.c – Vir Recursive-Descent Parser (v1.2)
 * ================================================
 * Produces ast_node_t trees from a token stream (vir_token_t[]).
 *
 * v1.2 Grammar (keyword-delimited blocks):
 *
 *   program     → (func_def | statement)* EOF
 *   func_def    → FUNC IDENT ':' [in_params] block END
 *   in_params   → IN '(' param (';' param)* ')'
 *   param       → IDENT [':' TYPE]
 *   params      → (IDENT (',' IDENT)*)?
 *   block       → statement*
 *   statement   → var_decl | const_decl | if_stmt | loop_stmt
 *               | while_stmt | return_stmt | print_stmt
 *               | assign_or_expr | NEWLINE
 *   var_decl    → VAR IDENT '=' expr
 *   const_decl  → CONST IDENT '=' expr
 *   if_stmt     → IF expr ':'|THEN block (EIF expr ':'|THEN block)* (ELSE
 * block)? END loop_stmt   → LOOP [expr] block END while_stmt  → WHILE expr THEN
 * block END (legacy) when_stmt   → WHEN expr LOOP block END (v1.2) return_stmt
 * → RETURN|OUT expr? print_stmt  → PRINT expr assign_or_expr → IDENT '=' expr
 * |  expr expr        → or_expr or_expr     → and_expr (OR and_expr)* and_expr
 * → compare (AND compare)* compare     → addition ((EQ|NE|GT|LT|GE|LE)
 * addition)? addition    → mult ((PLUS|MINUS) mult)* mult        → unary
 * ((STAR|SLASH|PERCENT) unary)* unary       → (MINUS|NOT) unary | call call →
 * primary ('(' args ')')? primary     → INT | FLOAT | STRING | TRUE | FALSE |
 * NONE | IDENT | '(' expr ')' | INPUT
 */

#include "parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "diagnostic.h"

extern diag_context_t g_parser_diag;

/* ═══════════════════════════════════════════════════════
 * Internal Helpers
 * ═══════════════════════════════════════════════════════ */

static void parse_error(vir_parser_t *p, const char *msg) {
  if (p->error[0] == '\0') { /* keep first error in the current statement */
    const vir_token_t *t =
        &p->tokens[p->pos < p->token_count ? p->pos : p->token_count - 1];
    snprintf(p->error, sizeof(p->error), "line %u: %s (got %s)", t->line, msg,
             lexer_token_name(t->type));
    p->error_line = t->line;
    
    diag_span_t span = diag_span_lc(p->file_id, t->line, t->col, 1);
    diag_entry_t *e = diag_error(&g_parser_diag, DCAT_SYNTAX, PHASE_PARSER, E1001, span, msg);
    diag_add_cause(&g_parser_diag, e, "Unexpected token in current context");
    diag_add_action(&g_parser_diag, e, "Check syntax and spelling");
  }
}

static void parser_sync(vir_parser_t *p) {
  p->error[0] = '\0'; /* Clear error to allow reporting next statement's error */
  while (p->pos < p->token_count) {
    vir_tok_t type = p->tokens[p->pos].type;
    if (type == TOK_EOF || type == TOK_NEWLINE || type == TOK_SEMICOLON ||
        type == TOK_FUNC || type == TOK_VAR || type == TOK_CONST ||
        type == TOK_IF || type == TOK_LOOP || type == TOK_FOR ||
        type == TOK_RETURN || type == TOK_CLASS || type == TOK_ENUM) {
      break;
    }
    p->pos++;
  }
}

static const vir_token_t *peek(const vir_parser_t *p) {
  uint32_t idx = p->pos < p->token_count ? p->pos : p->token_count - 1;
  return &p->tokens[idx];
}

static const vir_token_t *advance(vir_parser_t *p) {
  const vir_token_t *t = peek(p);
  if (p->pos < p->token_count)
    p->pos++;
  return t;
}

static int check(const vir_parser_t *p, vir_tok_t type) {
  return peek(p)->type == type;
}

static int match(vir_parser_t *p, vir_tok_t type) {
  if (check(p, type)) {
    advance(p);
    return 1;
  }
  return 0;
}

/* If the parser is positioned on a generic argument list `<T>` immediately
 * after a base type identifier, rewrite `node->name2` to the array-element
 * form `[T]`. This lets downstream element-type inference (e.g. vec_get_rt or
 * indexing into a `Vec<T>` field) recover the element type. Non-consuming:
 * the surrounding skip logic still consumes the `< ... >` tokens. */
static void capture_generic_elem_type(vir_parser_t *p, ast_node_t *node) {
  if (!node || !check(p, TOK_LT))
    return;
  if (p->pos + 1 < p->token_count &&
      p->tokens[p->pos + 1].type == TOK_IDENT) {
    snprintf(node->name2, AST_NAME_LEN, "[%s]", p->tokens[p->pos + 1].str.buf);
  }
}

static const vir_token_t *expect(vir_parser_t *p, vir_tok_t type,
                                 const char *msg) {
  if (check(p, type))
    return advance(p);
  parse_error(p, msg);
  return NULL;
}

/* Skip newlines (used between statements) */
static void skip_newlines(vir_parser_t *p) {
  while (check(p, TOK_NEWLINE))
    advance(p);
}

/* Check if token could start a statement */
static int is_stmt_start(vir_tok_t t) {
  return t == TOK_VAR || t == TOK_CONST || t == TOK_IF || t == TOK_LOOP ||
         t == TOK_WHILE || t == TOK_WHEN || t == TOK_FOR || t == TOK_RETURN ||
         t == TOK_OUT || t == TOK_PRINT || t == TOK_INPUT || t == TOK_IDENT ||
         t == TOK_INT || t == TOK_FLOAT || t == TOK_STRING || t == TOK_LPAREN ||
         t == TOK_MINUS || t == TOK_NOT || t == TOK_CHECK_CPU ||
         t == TOK_PATCH || t == TOK_FUNC || t == TOK_BREAK ||
         t == TOK_CONTINUE || t == TOK_SKIP || t == TOK_TRUE ||
         t == TOK_FALSE || t == TOK_LBRACKET || t == TOK_ENUM ||
         t == TOK_RECORD || t == TOK_ENTITY || t == TOK_IMPORT ||
         t == TOK_FROM || t == TOK_MODULE || t == TOK_EXPORT ||
         t == TOK_INCLUDE;
}

/* ═══════════════════════════════════════════════════════
 * v1.2 Block Opener: accept ':' or 'then'
 * ═══════════════════════════════════════════════════════ */

static int expect_block_open(vir_parser_t *p, const char *context) {
  if (match(p, TOK_COLON)) {
    if (match(p, TOK_THEN)) return 1;
    if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "do") == 0) {
      advance(p);
    }
    return 1;
  }
  if (match(p, TOK_THEN)) return 1;
  if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "do") == 0) {
    advance(p);
    return 1;
  }
  if (check(p, TOK_NEWLINE)) {
    return 1;
  }
  char msg[128];
  snprintf(msg, sizeof(msg), "expected ':', 'then', or 'do' after %s", context);
  parse_error(p, msg);
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Builtin Function Name → ID Mapping
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  const char *name;
  int id;
} builtin_map_t;

static const builtin_map_t builtins[] = {
    /* Vietnamese */
    {"dài", BUILTIN_LEN},
    {"đẩy", BUILTIN_PUSH},
    {"cấp", BUILTIN_ALLOC},
    {"giải", BUILTIN_FREE_MEM},
    {"đọc_byte", BUILTIN_READ8},
    {"ghi_byte", BUILTIN_WRITE8},
    {"đọc_số", BUILTIN_READ64},
    {"ghi_số", BUILTIN_WRITE64},
    {"dài_chuỗi", BUILTIN_STR_LEN},
    {"ký_tự", BUILTIN_STR_GET},
    {"nối", BUILTIN_STR_CAT},
    {"bằng_chuỗi", BUILTIN_STR_EQ},
    {"mở_tệp", BUILTIN_FILE_OPEN},
    {"đọc_tệp", BUILTIN_FILE_READ},
    {"ghi_tệp", BUILTIN_FILE_WRITE},
    {"đóng_tệp", BUILTIN_FILE_CLOSE},
    {"ghi_byte_tệp", BUILTIN_FILE_WRITE_BYTE},
    {"thoát_ct", BUILTIN_EXIT},
    {"số_sang_chuỗi", BUILTIN_I_TO_STR},
    {"chuỗi_sang_số", BUILTIN_STR_TO_I},
    {"mảng_mới", BUILTIN_ARR_NEW},
    /* English */
    {"len", BUILTIN_LEN},
    {"push", BUILTIN_PUSH},
    {"alloc", BUILTIN_ALLOC},
    {"dealloc", BUILTIN_FREE_MEM},
    {"read_byte", BUILTIN_READ8},
    {"native_read_u8", BUILTIN_READ8},
    {"write_byte", BUILTIN_WRITE8},
    {"native_write_u8", BUILTIN_WRITE8},
    {"read_word", BUILTIN_READ64},
    {"native_read_i64", BUILTIN_READ64},
    {"write_word", BUILTIN_WRITE64},
    {"native_write_i64", BUILTIN_WRITE64},
    {"native_str_byte_len", BUILTIN_STR_LEN},
    {"native_str_ptr", BUILTIN_CAST_PTR},
    {"str_get", BUILTIN_STR_GET},
    {"str_cat", BUILTIN_STR_CAT},
    {"str_eq", BUILTIN_STR_EQ},
    {"str_eq", BUILTIN_STR_EQ},
    {"file_open", BUILTIN_FILE_OPEN},
    {"file_read", BUILTIN_FILE_READ},
    {"file_write", BUILTIN_FILE_WRITE},
    {"file_close", BUILTIN_FILE_CLOSE},
    {"file_write_byte", BUILTIN_FILE_WRITE_BYTE},
    {"exit_prog", BUILTIN_EXIT},
    {"i_to_str", BUILTIN_I_TO_STR},
    {"int_to_str", BUILTIN_I_TO_STR},
    {"str_to_i", BUILTIN_STR_TO_I},
    {"str_to_int", BUILTIN_STR_TO_I},
    {"arr_new", BUILTIN_ARR_NEW},
    {"print_str", BUILTIN_PRINT_STR},
    {"viết_chuỗi", BUILTIN_PRINT_STR},
    {"get_arg", BUILTIN_GET_ARG},
    {"lấy_arg", BUILTIN_GET_ARG},
    {"arg_count", BUILTIN_ARG_COUNT},
    {"đếm_arg", BUILTIN_ARG_COUNT},
    {"volatile_read", BUILTIN_VOLATILE_READ},
    {"volatile_write", BUILTIN_VOLATILE_WRITE},
    {"đọc_volatile", BUILTIN_VOLATILE_READ},
    {"ghi_volatile", BUILTIN_VOLATILE_WRITE},
    /* §20 Dict builtins */
    {"hash", BUILTIN_HASH},
    {"băm", BUILTIN_HASH},
    {"keys", BUILTIN_KEYS},
    {"khóa", BUILTIN_KEYS},
    {"values", BUILTIN_VALUES},
    {"giá_trị", BUILTIN_VALUES},
    /* §26.5 quantize */
    {"quantize", BUILTIN_QUANTIZE},
    {"nén", BUILTIN_QUANTIZE},
    /* §24 flux / atomic builtins */
    {"flux", BUILTIN_FLUX_CTOR},
    {"flux_dot", BUILTIN_FLUX_DOT},
    {"flux_len", BUILTIN_FLUX_LEN},
    {"flux_norm", BUILTIN_FLUX_NORM},
    {"flux_splat", BUILTIN_FLUX_SPLAT},
    {"flux_load", BUILTIN_FLUX_LOAD},
    {"flux_store", BUILTIN_FLUX_STORE},
    {"tensor_sum", BUILTIN_TENSOR_SUM},
    {"atomic_cas", BUILTIN_ATOMIC_CAS},
    {"atomic_fence", BUILTIN_ATOMIC_FENCE},
    /* §19.4 array helpers */
    {"cap", BUILTIN_CAP},
    {"sức_chứa", BUILTIN_CAP},
    {"arr_compact", BUILTIN_ARR_COMPACT},
    {"nén_mảng", BUILTIN_ARR_COMPACT},
    /* §4.7 Arena allocator */
    {"arena_new", BUILTIN_ARENA_NEW},
    {"arena_alloc", BUILTIN_ARENA_ALLOC},
    {"arena_free", BUILTIN_ARENA_FREE},
    {"vùng_mới", BUILTIN_ARENA_NEW},
    {"vùng_cấp", BUILTIN_ARENA_ALLOC},
    {"vùng_giải", BUILTIN_ARENA_FREE},
    /* §22.5 Cooperative yield */
    {"yield", BUILTIN_YIELD},
    {"nhường", BUILTIN_YIELD},
    /* §Phase-9 Intrinsic Registry — Q_INTRINSIC table-driven dispatch */
    {"__syscall",     BUILTIN_SYSCALL},
    {"__memcpy",      BUILTIN_MEMCPY},
    {"__memset",      BUILTIN_MEMSET},
    {"__trap",        BUILTIN_TRAP},
    {"__unreachable", BUILTIN_UNREACHABLE},
    {"__clz",         BUILTIN_CLZ},
    {"__ctz",         BUILTIN_CTZ},
    {"__popcnt",      BUILTIN_POPCNT},
    {"__bswap",       BUILTIN_BSWAP},
    {"__atomic_load", BUILTIN_ATOMIC_LOAD},
    {"__atomic_store",BUILTIN_ATOMIC_STORE},
    {"__atomic_add",  BUILTIN_ATOMIC_ADD},
    {"__atomic_sub",  BUILTIN_ATOMIC_SUB},
    {NULL, 0}};

static int lookup_builtin(const char *name) {
  for (int i = 0; builtins[i].name; i++) {
    if (strcmp(builtins[i].name, name) == 0)
      return builtins[i].id;
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Forward Declarations
 * ═══════════════════════════════════════════════════════ */


static inline int is_name_token(vir_tok_t t) {
  if (t == TOK_IDENT) return 1;
  /* Exclude operators and delimiters explicitly */
  if (t >= TOK_PLUS && t <= TOK_MOD) return 0;
  if (t >= TOK_EQ && t <= TOK_SAFE_NE) return 0;
  if (t == TOK_ASSIGN) return 0;
  if (t >= TOK_AND && t <= TOK_NOT) return 0;
  if (t >= TOK_BIT_AND && t <= TOK_BIT_NOT) return 0;
  if (t >= TOK_SAFE_ACCESS && t <= TOK_HASH) return 0;
  if (t >= TOK_MATMUL && t <= TOK_ATOMIC_BANG && t != TOK_LOCK) return 0;
  if (t >= TOK_PLUS_ASSIGN && t <= TOK_SLASH_ASSIGN) return 0;
  if (t >= TOK_LPAREN && t <= TOK_ARROW) return 0;
  
  /* Everything else in the keyword range is acceptable as a name */
  return (t >= TOK_FUNC && t <= TOK_NONE_LIT);
}

static const vir_token_t *expect_name(vir_parser_t *p, const char *msg) {
  const vir_token_t *t = peek(p);
  if (is_name_token(t->type)) {
    return advance(p);
  }
  parse_error(p, msg);
  return NULL;
}

static const vir_token_t *expect_func_name(vir_parser_t *p) {
  const vir_token_t *t = peek(p);
  if (is_name_token(t->type)) {
    return advance(p);
  }
  parse_error(p, "expected function name");
  return NULL;
}
static ast_node_t *parse_expr(vir_parser_t *p);
static ast_node_t *parse_statement(vir_parser_t *p);
static ast_node_t *parse_block(vir_parser_t *p);
static ast_node_t *parse_unary(vir_parser_t *p);
static int expect_block_open(vir_parser_t *p, const char *ctx);

/* Forward - we need this for record literal parsing */
static int check_record_literal(vir_parser_t *p);

/* Check if current '{' starts a record literal (lookahead: '{' IDENT ':' or '{
 * ;' or '{ }') */
static int check_record_literal(vir_parser_t *p) {
  /* We're at '{', check if next tokens are IDENT ':' or '}' or ';' */
  uint32_t save = p->pos;
  if (p->pos < p->token_count && p->tokens[p->pos].type == TOK_LBRACE) {
    uint32_t next = save + 1;
    /* Empty record literal: Name { } */
    if (next < p->token_count && p->tokens[next].type == TOK_RBRACE)
      return 1;
    /* Record literal with fields on next line: Name { ; field: val ... } */
    if (next < p->token_count && (p->tokens[next].type == TOK_SEMICOLON ||
                                  p->tokens[next].type == TOK_NEWLINE))
      return 1;
    /* IDENT : or IDENT = pattern: Name { field: val ... } */
    if (next + 1 < p->token_count && p->tokens[next].type == TOK_IDENT &&
        (p->tokens[next + 1].type == TOK_COLON || p->tokens[next + 1].type == TOK_ASSIGN))
      return 1;
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Expression Parsing (precedence climbing)
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_primary(vir_parser_t *p) {
  const vir_token_t *t = peek(p);

  /* §17.1 precomp/comptime — prefix *modifier*, lowest precedence.
   * `precomp EXPR` / `comptime EXPR`: the modifier swallows the entire
   * expression that follows until end-of-line / separator / closing
   * delimiter. Use `precomp (EXPR)` to group compound expressions that
   * span parentheses-able boundaries.
   *   var a = precomp 2 + 3 * 5          →  precomp(2 + 3*5)
   *   var b = precomp (cfg() or true)    →  precomp(cfg() or true)
   * Spec §17.1 — modifier, not a block. */
  if (t->type == TOK_IDENT && (strcmp(t->str.buf, "precomp") == 0 ||
                               strcmp(t->str.buf, "comptime") == 0)) {
    const vir_token_t *t2 =
        (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
    /* Not a precomp expression if the next token is `func` (that's the
     * §17.2 function modifier, handled in parse_statement) or a `{`
     * record-literal brace that doesn't belong to us. */
    int is_modifier = (t2 && t2->type != TOK_FUNC);
    if (is_modifier) {
      advance(p); /* precomp / comptime */
      ast_node_t *inner = parse_expr(p);
      ast_node_t *n = ast_new(AST_PRECOMP);
      n->line = t->line;
      if (inner)
        ast_add_child(n, inner);
      return n;
    }
  }

  /* §23.3 `recv NAME` expression form — leaf port read */
  if (t->type == TOK_IDENT && strcmp(t->str.buf, "recv") == 0) {
    const vir_token_t *t2 =
        (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
    if (t2 && t2->type == TOK_IDENT) {
      advance(p); /* 'recv' */
      const vir_token_t *pn = advance(p);
      ast_node_t *r = ast_new(AST_RECV_EXPR);
      r->line = t->line;
      strncpy(r->name, pn->str.buf, AST_NAME_LEN - 1);
      return r;
    }
  }

  /* §22 `task FUNC_CALL` expression form — spawn async task */
  if (t->type == TOK_TASK) {
    advance(p); /* 'task' */
    ast_node_t *call_expr = parse_unary(p);
    if (!call_expr) {
      fprintf(stderr, "parse error: expected function call after 'task'\n");
      return NULL;
    }
    ast_node_t *task_node = ast_new(AST_TASK);
    task_node->line = t->line;
    task_node->int_val = 0; /* 0 = spawn */
    ast_add_child(task_node, call_expr);
    return task_node;
  }

  /* §22 `wait TASK_ID` expression form — wait for task completion */
  if (t->type == TOK_WAIT) {
    advance(p); /* 'wait' */
    ast_node_t *task_expr = parse_expr(p);
    if (!task_expr) {
      fprintf(stderr, "parse error: expected task expression after 'wait'\n");
      return NULL;
    }
    ast_node_t *wait_node = ast_new(AST_TASK);
    wait_node->line = t->line;
    wait_node->int_val = 1; /* 1 = wait */
    ast_add_child(wait_node, task_expr);
    return wait_node;
  }

  /* §20.2 Map expression: `map x [,idx] in iter: body end` */
  if (t->type == TOK_MAP_KW) {
    advance(p);
    const vir_token_t *v1 = expect_name(p, "expected map variable");
    if (!v1)
      return NULL;
    ast_node_t *m = ast_new(AST_MAP_EXPR);
    strncpy(m->name, v1->str.buf, AST_NAME_LEN - 1);
    m->line = t->line;
    if (match(p, TOK_COMMA)) {
      const vir_token_t *v2 =
          expect_name(p, "expected second map variable");
      if (v2)
        strncpy(m->name2, v2->str.buf, AST_NAME_LEN - 1);
    }
    if (!expect(p, TOK_IN, "expected 'in' in map expression"))
      return m;
    ast_node_t *iter = parse_expr(p);
    if (!iter)
      return m;
    ast_add_child(m, iter);
    expect_block_open(p, "map body");
    ast_node_t *body = parse_block(p);
    expect(p, TOK_END, "expected 'end' after map body");
    if (body && body->type == AST_BLOCK) {
      for (uint32_t i = 0; i < body->child_count; i++)
        ast_add_child(m, body->children[i]);
      body->child_count = 0;
      ast_free(body);
    } else if (body) {
      ast_add_child(m, body);
    }
    return m;
  }

  switch (t->type) {
  case TOK_INT: {
    advance(p);
    ast_node_t *n = ast_new(AST_LITERAL_INT);
    n->int_val = t->int_val;
    n->line = t->line;
    return n;
  }
  case TOK_FLOAT: {
    advance(p);
    ast_node_t *n = ast_new(AST_LITERAL_FLOAT);
    n->float_val = t->float_val;
    n->line = t->line;
    return n;
  }
  case TOK_STRING: {
    advance(p);
    ast_node_t *n = ast_new(AST_LITERAL_STR);
    strncpy(n->name, t->str.buf, AST_NAME_LEN - 1);
    n->line = t->line;
    return n;
  }
  case TOK_ERX: {
    advance(p);
    ast_node_t *n = ast_new(AST_ERX_READ);
    n->line = t->line;
    return n;
  }
  case TOK_TRUE: {
    advance(p);
    ast_node_t *n = ast_new(AST_LITERAL_INT);
    n->int_val = 1;
    n->line = t->line;
    return n;
  }
  case TOK_FALSE:
  case TOK_NONE_LIT: {
    advance(p);
    ast_node_t *n = ast_new(AST_LITERAL_INT);
    n->int_val = 0;
    n->line = t->line;
    return n;
  }
  case TOK_THIS: {
    advance(p);
    /* §12.4: `this` in entity method refers to the receiver instance.
     * Represent as AST_IDENTIFIER with special name "this" that
     * the lowerer resolves to the implicit receiver parameter. */
    ast_node_t *n = ast_new(AST_IDENTIFIER);
    strncpy(n->name, "this", AST_NAME_LEN - 1);
    n->line = t->line;
    return n;
  }
  case TOK_IDENT: {
    advance(p);
    /* §Phase-8: scoped-identifier chain `A::B::C` — fold into a
     * single AST_IDENTIFIER whose `name` holds the full path.
     * We mutate `t` to a local copy to extend the string. */
    if (check(p, TOK_COLON)) {
      const vir_token_t *nxt =
          (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
      if (nxt && nxt->type == TOK_COLON) {
        char full[AST_NAME_LEN];
        size_t pos = strlen(t->str.buf);
        if (pos >= AST_NAME_LEN)
          pos = AST_NAME_LEN - 1;
        memcpy(full, t->str.buf, pos);
        while (check(p, TOK_COLON)) {
          const vir_token_t *n2 =
              (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
          if (!n2 || n2->type != TOK_COLON)
            break;
          advance(p);
          advance(p);
          if (pos + 2 < AST_NAME_LEN) {
            full[pos++] = ':';
            full[pos++] = ':';
          }
          /* Allow identifiers and keywords as path segments */
          if (strlen(peek(p)->str.buf) == 0)
            break;
          const vir_token_t *seg = advance(p);
          size_t ns = strlen(seg->str.buf);
          if (pos + ns < AST_NAME_LEN) {
            memcpy(full + pos, seg->str.buf, ns);
            pos += ns;
          }
        }
        full[pos < AST_NAME_LEN ? pos : AST_NAME_LEN - 1] = '\0';
        ast_node_t *id = ast_new(AST_IDENTIFIER);
        strncpy(id->name, full, AST_NAME_LEN - 1);
        id->line = t->line;
        return id;
      }
    }

    /* Generic instantiation: f<T>(...) */
    if (check(p, TOK_LT)) {
      uint32_t save = p->pos;
      advance(p);
      int depth = 1;
      int ok = 1;
      while (depth > 0 && !check(p, TOK_EOF)) {
        if (check(p, TOK_LT)) depth++;
        else if (check(p, TOK_GT)) depth--;
        else if (check(p, TOK_CAST)) depth -= 2; /* >> counts as two > */
        else if (!is_name_token(peek(p)->type) && !check(p, TOK_COMMA)) {
          ok = 0;
          break;
        }
        advance(p);
      }
      if (ok && (check(p, TOK_LPAREN) || check(p, TOK_LBRACE))) {
        /* Valid generic instantiation, token is now at '(' or '{' */
      } else {
        /* Not a generic call, rewind to parse as operator later */
        p->pos = save;
      }
    }

    /* Check if it's a builtin function call or regular function call */
    if (check(p, TOK_LPAREN)) {
      int bid = lookup_builtin(t->str.buf);
      if (bid != 0) {
        /* Builtin function call */
        ast_node_t *call = ast_new(AST_BUILTIN_CALL);
        call->builtin_id = bid;
        strncpy(call->name, t->str.buf, AST_NAME_LEN - 1);
        call->line = t->line;
        advance(p); /* consume '(' */
        if (!check(p, TOK_RPAREN)) {
          ast_node_t *arg = parse_expr(p);
          if (arg)
            ast_add_child(call, arg);
          while (match(p, TOK_COMMA)) {
            arg = parse_expr(p);
            if (arg)
              ast_add_child(call, arg);
          }
        }
        expect(p, TOK_RPAREN, "expected ')' after builtin arguments");
        return call;
      }
      /* Regular function call */
      ast_node_t *call = ast_new(AST_CALL);
      strncpy(call->name, t->str.buf, AST_NAME_LEN - 1);
      call->line = t->line;
      advance(p); /* consume '(' */

      /* Parse arguments — accept positional, named (name=expr),
       * separators `,` or `;` (§6.4). */
      if (!check(p, TOK_RPAREN)) {
        for (;;) {
          ast_node_t *arg = NULL;
          /* Named arg: IDENT '=' expr  (but not ==).
           * Also accept IDENT ':' expr (record-literal style).
           * BUT: do NOT treat IDENT '::' as named arg — that is an
           * enum variant access like TokType::Int. */
          int next_is_double_colon =
              (p->tokens[p->pos + 1].type == TOK_COLON) &&
              (p->pos + 2 < p->token_count) &&
              (p->tokens[p->pos + 2].type == TOK_COLON);
          if (check(p, TOK_IDENT) && (p->pos + 1 < p->token_count) &&
              !next_is_double_colon &&
              (p->tokens[p->pos + 1].type == TOK_ASSIGN ||
               p->tokens[p->pos + 1].type == TOK_COLON)) {
            const vir_token_t *nm = advance(p);
            advance(p); /* '=' or ':' */
            ast_node_t *val = parse_expr(p);
            arg = ast_new(AST_NAMED_ARG);
            strncpy(arg->name, nm->str.buf, AST_NAME_LEN - 1);
            arg->line = nm->line;
            if (val)
              ast_add_child(arg, val);
          } else {
            arg = parse_expr(p);
          }
          if (arg)
            ast_add_child(call, arg);
          if (match(p, TOK_COMMA))
            continue;
          if (match(p, TOK_SEMICOLON))
            continue;
          break;
        }
      }
      expect(p, TOK_RPAREN, "expected ')' after arguments");
      return call;
    }
    /* Check for index access: IDENT '[' expr (, expr)* ']' */
    if (check(p, TOK_LBRACKET)) {
      advance(p); /* consume '[' */
      ast_node_t *idx = parse_expr(p);
      ast_node_t *access = ast_new(AST_INDEX_ACCESS);
      strncpy(access->name, t->str.buf, AST_NAME_LEN - 1);
      access->line = t->line;
      ast_add_child(access, idx);
      /* §26.1 tensor multi-index: collect additional comma-separated indices */
      while (check(p, TOK_COMMA)) {
        advance(p); /* consume ',' */
        ast_node_t *idx2 = parse_expr(p);
        ast_add_child(access, idx2);
      }
      expect(p, TOK_RBRACKET, "expected ']' after index");
      return access;
    }

    /* Check for record literal: IDENT '{' field: val, ... '}' */
    if (check(p, TOK_LBRACE) && check_record_literal(p)) {
      advance(p); /* consume '{' */
      skip_newlines(p);
      match(p, TOK_SEMICOLON); /* skip optional semicolon after '{' */
      skip_newlines(p);
      ast_node_t *rl = ast_new(AST_RECORD_LITERAL);
      strncpy(rl->name, t->str.buf, AST_NAME_LEN - 1);
      rl->line = t->line;
      while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
        /* Parse field_name : expr */
        const vir_token_t *fname = expect_name(p, "expected field name");
        if (!fname)
          break;
        if (check(p, TOK_COLON) || check(p, TOK_ASSIGN)) {
          advance(p);
        } else {
          parse_error(p, "expected ':' or '=' after field name");
        }
        ast_node_t *val = parse_expr(p);
        if (val) {
          /* Store field name in the value node's name2 */
          strncpy(val->name2, fname->str.buf, AST_NAME_LEN - 1);
          ast_add_child(rl, val);
        }
        /* Accept both ',' and ';' as field separator (v2.0 compat) */
        while (match(p, TOK_COMMA) || match(p, TOK_SEMICOLON) || match(p, TOK_NEWLINE)) {
          /* consume separator */
        }
      }
      /* Also allow trailing ';' before '}' */
      while (match(p, TOK_SEMICOLON) || match(p, TOK_COMMA) || match(p, TOK_NEWLINE)) {}
      expect(p, TOK_RBRACE, "expected '}' after record literal");
      return rl;
    }

    /* Plain identifier */
    ast_node_t *n = ast_new(AST_IDENTIFIER);
    strncpy(n->name, t->str.buf, AST_NAME_LEN - 1);
    n->line = t->line;
    return n;
  }
  case TOK_INPUT: {
    advance(p);
    ast_node_t *n = ast_new(AST_INPUT);
    n->line = t->line;
    return n;
  }
  case TOK_LPAREN: {
    advance(p);
    ast_node_t *inner = parse_expr(p);
    /* Check for tuple: (a, b, c) */
    if (check(p, TOK_COMMA)) {
      ast_node_t *tup = ast_new(AST_TUPLE_LITERAL);
      if (inner) ast_add_child(tup, inner);
      while (match(p, TOK_COMMA)) {
        if (check(p, TOK_RPAREN)) break; /* trailing comma */
        ast_node_t *elem = parse_expr(p);
        if (elem) ast_add_child(tup, elem);
      }
      expect(p, TOK_RPAREN, "expected ')' to close tuple");
      return tup;
    }
    expect(p, TOK_RPAREN, "expected ')'");
    return inner;
  }
  case TOK_LBRACKET: {
    /* Array literal: [expr, expr, ...]
     * Dict  literal: [key: val, key: val, ...]  (§20)
     * Empty []        → AST_ARRAY_LITERAL with 0 children.
     * Empty dict       → [:]
     */
    advance(p);
    /* [:] is an empty dict literal */
    if (check(p, TOK_COLON) && p->pos + 1 < p->token_count &&
        p->tokens[p->pos + 1].type == TOK_RBRACKET) {
      advance(p); /* ':' */
      advance(p); /* ']' */
      ast_node_t *dict = ast_new(AST_MAP_LITERAL);
      dict->line = t->line;
      return dict;
    }
    ast_node_t *arr = ast_new(AST_ARRAY_LITERAL);
    arr->line = t->line;
    if (!check(p, TOK_RBRACKET)) {
      ast_node_t *first = parse_expr(p);
      if (first)
        ast_add_child(arr, first);
      /* Dict literal: first item followed by ':' → re-interpret. */
      if (check(p, TOK_COLON)) {
        advance(p); /* consume ':' */
        arr->type = AST_MAP_LITERAL;
        ast_node_t *val = parse_expr(p);
        if (val)
          ast_add_child(arr, val);
        while (match(p, TOK_COMMA)) {
          if (check(p, TOK_RBRACKET))
            break;
          ast_node_t *k = parse_expr(p);
          if (k)
            ast_add_child(arr, k);
          expect(p, TOK_COLON, "expected ':' in dict literal");
          ast_node_t *v = parse_expr(p);
          if (v)
            ast_add_child(arr, v);
        }
      } else {
        while (match(p, TOK_COMMA)) {
          ast_node_t *elem = parse_expr(p);
          if (elem)
            ast_add_child(arr, elem);
        }
      }
    }
    expect(p, TOK_RBRACKET, "expected ']' after array/dict literal");
    return arr;
  }
  default:
    fprintf(stderr, "EXPECTED EXPR at line %d, token %s\n", peek(p)->line, peek(p)->str.buf); parse_error(p, "expected expression");
    return NULL;
  }
}

static ast_node_t *parse_unary(vir_parser_t *p) {
  /* §4.8: `&expr` (shared borrow) or `&mut expr` (mutable borrow).
   * `&` in prefix position = borrow; in infix position = logical AND.
   * parse_unary is only called at the start of an operand, so `&` here
   * is unambiguously a borrow. */
  if (check(p, TOK_AND)) {
    const vir_token_t *t = advance(p);
    int is_mut = 0;
    if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "mut") == 0) {
      advance(p);
      is_mut = 1;
    }
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;
    ast_node_t *n = ast_new(AST_BORROW);
    n->int_val = is_mut; /* 0 = shared, 1 = mutable */
    n->line = t->line;
    ast_add_child(n, operand);
    return n;
  }
  if (check(p, TOK_STAR)) {
    const vir_token_t *t = advance(p);
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;
    ast_node_t *n = ast_new(AST_ATOMIC_LOAD); // Use AST_ATOMIC_LOAD temporarily if DEREF is missing
    n->line = t->line;
    ast_add_child(n, operand);
    return n;
  }
  if (check(p, TOK_MINUS)) {
    const vir_token_t *t = advance(p);
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;

    /* -expr  →  0 - expr */
    ast_node_t *zero = ast_new(AST_LITERAL_INT);
    zero->int_val = 0;
    zero->line = t->line;

    ast_node_t *n = ast_new(AST_BINOP);
    n->op = OP_SUB;
    n->line = t->line;
    ast_add_child(n, zero);
    ast_add_child(n, operand);
    return n;
  }
  if (check(p, TOK_NOT)) {
    const vir_token_t *t = advance(p);
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;

    /*  NOT expr → (expr == 0) */
    ast_node_t *zero = ast_new(AST_LITERAL_INT);
    zero->int_val = 0;
    zero->line = t->line;

    ast_node_t *n = ast_new(AST_COMPARE);
    n->op = OP_EQ;
    n->line = t->line;
    ast_add_child(n, operand);
    ast_add_child(n, zero);
    return n;
  }
  /* §16: `~expr` bitwise NOT (prefix) — desugar to `expr xor -1`.
   * Postfix swizzle `v~xyz` is handled in the postfix loop after
   * parse_primary, so a leading `~` here is unambiguously prefix. */
  if (check(p, TOK_BIT_NOT)) {
    const vir_token_t *t = advance(p);
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;
    ast_node_t *all_ones = ast_new(AST_LITERAL_INT);
    all_ones->int_val = -1; /* 0xFFFFFFFFFFFFFFFF as int64 */
    all_ones->line = t->line;
    ast_node_t *n = ast_new(AST_BINOP);
    n->op = OP_XOR;
    n->line = t->line;
    ast_add_child(n, operand);
    ast_add_child(n, all_ones);
    return n;
  }
  /* §24.4: `lock expr` atomic read prefix */
  if (check(p, TOK_LOCK)) {
    const vir_token_t *t = advance(p);
    ast_node_t *operand = parse_unary(p);
    if (!operand)
      return NULL;
    ast_node_t *n = ast_new(AST_ATOMIC_LOAD);
    n->line = t->line;
    ast_add_child(n, operand);
    return n;
  }
  /* §5.2: Block expression `{ stmt...; out expr }` as value.
   * Distinguish from record literal by context: bare `{` at start of
   * operand position = block expression; `Type{` = record literal.
   * The block evaluates statements and returns the value of the
   * trailing `out` expression (or 0 if absent). */
  if (check(p, TOK_LBRACE)) {
    advance(p); /* consume '{' */
    ast_node_t *blk = ast_new(AST_BLOCK);
    blk->line = peek(p)->line;
    skip_newlines(p);
    while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
      ast_node_t *stmt = parse_statement(p);
      if (stmt)
        ast_add_child(blk, stmt);
      else if (p->error[0] != '\0')
        break;
      skip_newlines(p);
    }
    expect(p, TOK_RBRACE, "expected '}' to close block expression");
    return blk;
  }
  /* Postfix: field access via '.' on the result of primary */
  ast_node_t *left = parse_primary(p);
  if (!left)
    return NULL;
  while (check(p, TOK_DOT) || check(p, TOK_SAFE_ACCESS) ||
         check(p, TOK_EXIST) || check(p, TOK_ATOMIC_BANG) ||
         check(p, TOK_BIT_NOT) || check(p, TOK_LBRACKET)) {
    if (check(p, TOK_LBRACKET)) {
      const vir_token_t *lbr = advance(p);
      ast_node_t *idx = parse_expr(p);
      ast_node_t *access = ast_new(AST_INDEX_ACCESS);
      access->line = lbr->line;
      ast_add_child(access, left);
      ast_add_child(access, idx);
      while (check(p, TOK_COMMA)) {
        advance(p);
        ast_add_child(access, parse_expr(p));
      }
      expect(p, TOK_RBRACKET, "expected ']'");
      left = access;
      continue;
    }
    if (check(p, TOK_BIT_NOT)) {
      /* §24.2 swizzle: v~xyz / v~rgba.  Postfix only — bitwise NOT
       * is prefix-only.  Disambiguated by being in postfix position. */
      const vir_token_t *tilde = advance(p);
      const vir_token_t *chans = expect(
          p, TOK_IDENT, "expected channel name after '~' (e.g. xyz, rgba)");
      if (!chans)
        break;
      ast_node_t *sw = ast_new(AST_SWIZZLE);
      strncpy(sw->name, chans->str.buf, AST_NAME_LEN - 1);
      sw->line = tilde->line;
      ast_add_child(sw, left);
      left = sw;
      continue;
    }
    if (check(p, TOK_EXIST)) {
      const vir_token_t *q = advance(p);
      ast_node_t *ex = ast_new(AST_EXIST_CHECK);
      ex->line = q->line;
      ast_add_child(ex, left);
      /* §20 Dict existence: `m ? key` — parse an optional key expr
       * when it looks like a primary (string, int, or parenthesised). */
      if (check(p, TOK_STRING) || check(p, TOK_INT) || check(p, TOK_LPAREN)) {
        ast_node_t *key = parse_primary(p);
        if (key)
          ast_add_child(ex, key);
      }
      left = ex;
      continue;
    }
    if (check(p, TOK_ATOMIC_BANG)) {
      /* §24.4: expr!! atomic read postfix */
      const vir_token_t *q = advance(p);
      ast_node_t *al = ast_new(AST_ATOMIC_LOAD);
      al->line = q->line;
      ast_add_child(al, left);
      left = al;
      continue;
    }
    int is_safe = check(p, TOK_SAFE_ACCESS);
    advance(p); /* consume '.' or '?.' */
    
    if (check(p, TOK_INT)) {
      const vir_token_t *idx_tok = advance(p);
      ast_node_t *fa = ast_new(is_safe ? AST_SAFE_ACCESS : AST_FIELD_ACCESS);
      snprintf(fa->name, AST_NAME_LEN - 1, "%lld", (long long)idx_tok->int_val);
      fa->line = idx_tok->line;
      ast_add_child(fa, left);
      left = fa;
      continue;
    }
    
    const vir_token_t *field =
        expect_name(p, "expected field name after '.'");
    if (!field)
      break;
    ast_node_t *fa = ast_new(is_safe ? AST_SAFE_ACCESS : AST_FIELD_ACCESS);
    strncpy(fa->name, field->str.buf, AST_NAME_LEN - 1);
    fa->line = field->line;
    ast_add_child(fa, left);
    /* §11 UFCS: if a '(' follows a plain dot access, rewrite
     *   receiver.fn(args...)  →  AST_CALL fn(receiver, args...)
     * This covers §11.1 (UFCS), §11.3 (chaining), §11.4 (method on
     * entity).  Safe-access '?.' is left as pure field access. */
    if (!is_safe && check(p, TOK_LPAREN)) {
      advance(p); /* consume '(' */
      fa->type = AST_CALL;
      if (!check(p, TOK_RPAREN)) {
        ast_node_t *arg = parse_expr(p);
        if (arg)
          ast_add_child(fa, arg);
        while (match(p, TOK_COMMA)) {
          arg = parse_expr(p);
          if (arg)
            ast_add_child(fa, arg);
        }
      }
      expect(p, TOK_RPAREN, "expected ')' after UFCS arguments");
    }
    left = fa;
  }
  return left;
}

static ast_node_t *parse_power(vir_parser_t *p) {
  ast_node_t *left = parse_unary(p);
  if (!left)
    return NULL;

  /* Right-associative: 2 ^ 3 ^ 2 = 2 ^ (3 ^ 2) */
  if (check(p, TOK_POWER)) {
    const vir_token_t *op_tok = advance(p);
    ast_node_t *right = parse_power(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = OP_POW;
    bin->line = op_tok->line;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    return bin;
  }
  return left;
}

static ast_node_t *parse_matmul(vir_parser_t *p) {
  /* §26.2: ** matmul and >< FMA, level 22 (higher than *), left-assoc */
  ast_node_t *left = parse_power(p);
  if (!left)
    return NULL;

  while (check(p, TOK_MATMUL) || check(p, TOK_FMA)) {
    const vir_token_t *op_tok = advance(p);
    ast_op_t op = (op_tok->type == TOK_MATMUL) ? OP_MATMUL : OP_FMA;

    ast_node_t *right = parse_power(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = op;
    bin->line = op_tok->line;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_mult(vir_parser_t *p) {
  ast_node_t *left = parse_matmul(p);
  if (!left)
    return NULL;

  while (check(p, TOK_STAR) || check(p, TOK_SLASH) || check(p, TOK_PERCENT)) {
    const vir_token_t *op_tok = advance(p);
    ast_op_t op;
    switch (op_tok->type) {
    case TOK_STAR:
      op = OP_MUL;
      break;
    case TOK_SLASH:
      op = OP_DIV;
      break;
    case TOK_PERCENT:
      op = OP_MOD;
      break;
    default:
      op = OP_MUL;
      break;
    }

    ast_node_t *right = parse_matmul(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = op;
    bin->line = op_tok->line;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_addition(vir_parser_t *p) {
  ast_node_t *left = parse_mult(p);
  if (!left)
    return NULL;

  while (check(p, TOK_PLUS) || check(p, TOK_MINUS) || check(p, TOK_DOTDOT)) {
    const vir_token_t *op_tok = advance(p);
    ast_op_t op;
    if (op_tok->type == TOK_PLUS)
      op = OP_ADD;
    else if (op_tok->type == TOK_MINUS)
      op = OP_SUB;
    else
      op = OP_PATTERN; /* §9.2: range '..' — reuse PATTERN opcode */

    ast_node_t *right = parse_mult(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = op;
    bin->line = op_tok->line;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_bitwise(vir_parser_t *p) {
  ast_node_t *left = parse_addition(p);
  if (!left)
    return NULL;

  while (check(p, TOK_BIT_AND) || check(p, TOK_BIT_OR) ||
         check(p, TOK_BIT_XOR) || check(p, TOK_BIT_SHL) ||
         check(p, TOK_BIT_SHR)) {
    const vir_token_t *op_tok = advance(p);
    ast_op_t op;
    switch (op_tok->type) {
    case TOK_BIT_AND:
      op = OP_AND;
      break;
    case TOK_BIT_OR:
      op = OP_OR;
      break;
    case TOK_BIT_XOR:
      op = OP_XOR;
      break;
    case TOK_BIT_SHL:
      op = OP_SHL;
      break;
    case TOK_BIT_SHR:
      op = OP_SHR;
      break;
    default:
      op = OP_AND;
      break;
    }

    ast_node_t *right = parse_addition(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = op;
    bin->line = op_tok->line;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_cast(vir_parser_t *p) {
  ast_node_t *left = parse_bitwise(p);
  if (!left)
    return NULL;

  while (check(p, TOK_CAST) || check(p, TOK_AS) || check(p, TOK_PATTERN)) {
    const vir_token_t *op_tok = advance(p);
    if (op_tok->type == TOK_PATTERN) {
      /* §8.9 pattern match: expr :~ pattern
       *   - pattern is Ident: type-check (always 1 for now - placeholder)
       *   - pattern is literal int: equality test
       *   - pattern is literal string: equality test */
      ast_node_t *pattern = parse_bitwise(p);
      if (!pattern) {
        ast_free(left);
        return NULL;
      }
      ast_node_t *pm = ast_new(AST_PATTERN_MATCH);
      pm->line = op_tok->line;
      ast_add_child(pm, left);
      ast_add_child(pm, pattern);
      left = pm;
      continue;
    }
    const vir_token_t *type_tok =
        expect_name(p, "expected type name after cast");
    if (!type_tok) {
      ast_free(left);
      return NULL;
    }
    ast_node_t *cast = ast_new(AST_CAST);
    cast->line = op_tok->line;
    strncpy(cast->name, type_tok->str.buf, AST_NAME_LEN - 1);
    ast_add_child(cast, left);
    left = cast;
  }
  return left;
}

static ast_node_t *parse_compare(vir_parser_t *p) {
  ast_node_t *left = parse_cast(p);
  if (!left)
    return NULL;

  if (check(p, TOK_EQ) || check(p, TOK_NE) || check(p, TOK_GT) ||
      check(p, TOK_LT) || check(p, TOK_GE) || check(p, TOK_LE) ||
      check(p, TOK_SAFE_EQ) || check(p, TOK_SAFE_NE)) {
    const vir_token_t *op_tok = advance(p);
    ast_op_t op;
    switch (op_tok->type) {
    case TOK_EQ:
      op = OP_EQ;
      break;
    case TOK_NE:
      op = OP_NE;
      break;
    case TOK_GT:
      op = OP_GT;
      break;
    case TOK_LT:
      op = OP_LT;
      break;
    case TOK_GE:
      op = OP_GE;
      break;
    case TOK_LE:
      op = OP_LE;
      break;
    case TOK_SAFE_EQ:
      op = OP_SAFE_EQ;
      break;
    case TOK_SAFE_NE:
      op = OP_SAFE_NE;
      break;
    default:
      op = OP_EQ;
      break;
    }

    ast_node_t *right = parse_cast(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *cmp = ast_new(AST_COMPARE);
    cmp->op = op;
    cmp->line = op_tok->line;
    ast_add_child(cmp, left);
    ast_add_child(cmp, right);
    return cmp;
  }
  return left;
}

static ast_node_t *parse_and_expr(vir_parser_t *p) {
  ast_node_t *left = parse_compare(p);
  if (!left)
    return NULL;

  while (check(p, TOK_AND)) {
    advance(p);
    ast_node_t *right = parse_compare(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = OP_AND;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_or_expr(vir_parser_t *p) {
  ast_node_t *left = parse_and_expr(p);
  if (!left)
    return NULL;

  while (check(p, TOK_OR)) {
    advance(p);
    ast_node_t *right = parse_and_expr(p);
    if (!right) {
      ast_free(left);
      return NULL;
    }

    ast_node_t *bin = ast_new(AST_BINOP);
    bin->op = OP_OR;
    ast_add_child(bin, left);
    ast_add_child(bin, right);
    left = bin;
  }
  return left;
}

static ast_node_t *parse_expr(vir_parser_t *p) { return parse_or_expr(p); }

/* ═══════════════════════════════════════════════════════
 * Statement Parsing
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_block(vir_parser_t *p) {
  ast_node_t *block = ast_new(AST_BLOCK);

  skip_newlines(p);

  while (!check(p, TOK_END) && !check(p, TOK_ELSE) && !check(p, TOK_ELIF) &&
         !check(p, TOK_EIF) && !check(p, TOK_REVERT) && !check(p, TOK_ENSURE) &&
         !check(p, TOK_EOF)) {
    ast_node_t *stmt = parse_statement(p);
    if (stmt) {
      ast_add_child(block, stmt);
      /* Consume an optional trailing `;` that the statement
       * parser didn't eat (e.g. bare expression statement,
       * assignment, etc.). */
      while (check(p, TOK_SEMICOLON))
        advance(p);
    } else {
      /* Avoid infinite loop on unrecoverable error */
      if (p->error[0] != '\0')
        break;
      advance(p);
    }
    skip_newlines(p);
  }

  return block;
}

/* Parse a single `name [= expr]` clause of a var/let/const declaration.
 * Used by parse_var_decl both for the first clause and the additional
 * clauses chained after `;` in a §5.3 group. */
static ast_node_t *parse_var_decl_single(vir_parser_t *p, ast_type_t type) {
  if (match(p, TOK_LPAREN)) {
    ast_node_t *decl = ast_new(type);
    decl->int_val |= 0x4000; /* bit 14 = is_tuple_destruct */
    
    while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF)) {
      const vir_token_t *name_tok = expect_name(p, "expected tuple variable name");
      if (!name_tok) break;
      
      ast_node_t *ident = ast_new(AST_IDENTIFIER);
      strncpy(ident->name, name_tok->str.buf, AST_NAME_LEN - 1);
      ident->line = name_tok->line;
      ast_add_child(decl, ident);
      
      if (!match(p, TOK_COMMA)) break;
    }
    expect(p, TOK_RPAREN, "expected ')' to close tuple assignment");
    
    if (match(p, TOK_ASSIGN)) {
      ast_node_t *init = parse_expr(p);
      if (init) ast_add_child(decl, init);
    }
    return decl;
  }

  const vir_token_t *name_tok = expect_name(p, "expected variable name");
  if (!name_tok)
    return NULL;

  ast_node_t *decl = ast_new(type);
  strncpy(decl->name, name_tok->str.buf, AST_NAME_LEN - 1);
  decl->line = name_tok->line;

  /* Optional v2 §2.4/§16 type annotation: `var NAME: TYPE = expr`.
   * The bare identifier form is recorded in decl->name2 so later passes
   * (e.g. §16 register/mold lowering) can resolve it. */
  if (check(p, TOK_COLON)) {
    uint32_t save = p->pos;
    advance(p); /* consume ':' */
    if (check(p, TOK_IDENT)) {
      const vir_token_t *ty = peek(p);
      strncpy(decl->name2, ty->str.buf, AST_NAME_LEN - 1);
      advance(p);
      /* §26.1 tensor<T>[M, N]  — consume elem-type + shape, pack
       * dims into decl->int_val ((rows << 16) | cols) and set bit 12
       * to mark "is_tensor". */
      if (strcmp(ty->str.buf, "tensor") == 0 && match(p, TOK_LT)) {
        /* skip element-type IDENT until `>` */
        while (!check(p, TOK_GT) && !check(p, TOK_EOF))
          advance(p);
        match(p, TOK_GT);
        uint32_t rows = 0, cols = 0;
        if (match(p, TOK_LBRACKET)) {
          if (check(p, TOK_INT)) {
            rows = (uint32_t)peek(p)->int_val;
            advance(p);
          }
          if (match(p, TOK_COMMA)) {
            if (check(p, TOK_INT)) {
              cols = (uint32_t)peek(p)->int_val;
              advance(p);
            }
          }
          expect(p, TOK_RBRACKET, "expected ']' in tensor shape");
        }
        decl->int_val |= 0x8000; /* bit 15 = is_tensor */
        decl->int_val |= ((int64_t)rows & 0xFFFF) << 32;
        decl->int_val |= ((int64_t)cols & 0xFFFF) << 48;
      }
    } else if (match(p, TOK_LBRACKET)) {
      if (check(p, TOK_IDENT)) {
        snprintf(decl->name2, AST_NAME_LEN, "[%s]", peek(p)->str.buf);
        advance(p);
      }
      expect(p, TOK_RBRACKET, "expected ']' after array type");
      decl->int_val |= 0x10000; /* array type marker */
    } else {
      /* §Phase-8 colon-style init: `const NAME: EXPR;` is
       * accepted as sugar for `const NAME = EXPR;`.  Consume the
       * expression right here and return. */
      if (type == AST_CONST_DECL || type == AST_VAR_DECL) {
        ast_node_t *init = parse_expr(p);
        if (init)
          ast_add_child(decl, init);
        /* Swallow any trailing `;` so the outer statement loop
         * doesn't trip on a stray separator (group-syntax path
         * only kicks in when `=` was used). */
        match(p, TOK_SEMICOLON);
        return decl;
      }
      /* Not an identifier after ':' — rewind; caller may be parsing a
       * different construct (e.g. map literal). */
      p->pos = save;
    }
  }

  if (match(p, TOK_ASSIGN)) {
    ast_node_t *init = parse_expr(p);
    if (init)
      ast_add_child(decl, init);
  }
  return decl;
}

static ast_node_t *parse_var_decl(vir_parser_t *p, ast_type_t type) {
  /* §5.3 — Group syntax: `var a = 1; b = 2; c = 3` produces three
   * declarations. Separator is `;` followed by an IDENT that is NOT a
   * statement-starting keyword. A trailing `;` is allowed but not
   * required. Single-decl form (no `;`) stays identical to before. */
  ast_node_t *first = parse_var_decl_single(p, type);
  if (!first)
    return NULL;

  /* Peek past `;` — if the next token is an IDENT that is NOT the
   * start of another statement keyword, treat it as a continuation
   * of this var/let/const group. */
  if (!check(p, TOK_SEMICOLON))
    return first;

  /* Look ahead: is this a group, or an end-of-stmt trailing `;`?
   * Accept group iff `; IDENT` with IDENT followed by `:`, `=`, `;`,
   * NEWLINE, or END. Reject if IDENT is followed by `(` (function
   * call statement) or an operator. */
  uint32_t save = p->pos;
  advance(p); /* consume ';' */
  uint32_t after_semi = p->pos;
  skip_newlines(p);
  if (!check(p, TOK_IDENT)) {
    /* Trailing `;` — stay parked just after it so the outer
     * statement loop doesn't see a stray separator. */
    p->pos = after_semi;
    return first;
  }
  /* Look one token past the IDENT to validate. */
  uint32_t peek_pos = p->pos + 1;
  if (peek_pos < p->token_count) {
    vir_tok_t t2 = p->tokens[peek_pos].type;
    if (t2 != TOK_ASSIGN && t2 != TOK_COLON && t2 != TOK_SEMICOLON &&
        t2 != TOK_NEWLINE && t2 != TOK_END && t2 != TOK_EOF) {
      /* Not a var-group continuation. Rewind to just after `;`. */
      p->pos = after_semi;
      return first;
    }
  }

  /* It IS a group — build a synthetic AST_BLOCK holding all decls. */
  ast_node_t *group = ast_new(AST_BLOCK);
  group->line = first->line;
  ast_add_child(group, first);
  for (;;) {
    ast_node_t *nxt = parse_var_decl_single(p, type);
    if (!nxt)
      break;
    ast_add_child(group, nxt);
    if (!check(p, TOK_SEMICOLON))
      break;
    advance(p); /* consume ';' */
    uint32_t after_s2 = p->pos;
    skip_newlines(p);
    if (!check(p, TOK_IDENT)) {
      p->pos = after_s2;
      break;
    }
    uint32_t pp = p->pos + 1;
    if (pp < p->token_count) {
      vir_tok_t t2 = p->tokens[pp].type;
      if (t2 != TOK_ASSIGN && t2 != TOK_COLON && t2 != TOK_SEMICOLON &&
          t2 != TOK_NEWLINE && t2 != TOK_END && t2 != TOK_EOF) {
        p->pos = after_s2;
        break;
      }
    }
  }
  return group;
}

static ast_node_t *parse_if_stmt(vir_parser_t *p) {
  /* IF expr ':'|THEN block (EIF|ELIF expr ':'|THEN block)* (ELSE block)? END */
  uint32_t line = peek(p)->line;

  ast_node_t *cond = parse_expr(p);
  if (!cond)
    return NULL;

  expect_block_open(p, "if condition");

  ast_node_t *then_block = parse_block(p);

  ast_node_t *if_node = ast_new(AST_IF);
  if_node->line = line;
  ast_add_child(if_node, cond);
  ast_add_child(if_node, then_block);

  /* Handle ELIF/EIF as nested IF in else branch */
  if (check(p, TOK_ELIF) || check(p, TOK_EIF)) {
    advance(p);
    ast_node_t *elif_as_if = parse_if_stmt(p);
    /* Wrap in a block */
    ast_node_t *else_block = ast_new(AST_BLOCK);
    if (elif_as_if)
      ast_add_child(else_block, elif_as_if);
    ast_add_child(if_node, else_block);
    /* The nested if_stmt consumes its own END */
    return if_node;
  }

  /* Handle ELSE */
  if (match(p, TOK_ELSE)) {
    skip_newlines(p);
    /* Check if ELSE is followed by block opener (optional) */
    match(p, TOK_THEN);
    match(p, TOK_COLON);
    ast_node_t *else_block = parse_block(p);
    ast_add_child(if_node, else_block);
  }

  expect(p, TOK_END, "expected 'hết'/'end' after if block");
  return if_node;
}

static ast_node_t *parse_loop_stmt(vir_parser_t *p) {
  /* v1.2: LOOP block END  (infinite loop, no count)
   * legacy: LOOP expr THEN block END  (counted loop) */
  uint32_t line = peek(p)->line;

  /* Check if next token is block opener → infinite loop (v1.2) */
  if (check(p, TOK_NEWLINE) || check(p, TOK_COLON)) {
    /* Infinite loop: use a large count or special flag */
    match(p, TOK_COLON); /* optional ':' */
    skip_newlines(p);
    ast_node_t *body = parse_block(p);
    expect(p, TOK_END, "expected 'end' after loop block");
    /* Emit as while(true) */
    ast_node_t *cond = ast_new(AST_LITERAL_INT);
    cond->int_val = 1;
    cond->line = line;
    ast_node_t *n = ast_new(AST_WHILE);
    n->line = line;
    ast_add_child(n, cond);
    ast_add_child(n, body);
    return n;
  }

  /* Legacy: counted loop */
  ast_node_t *count = parse_expr(p);
  if (!count)
    return NULL;

  expect_block_open(p, "loop count");

  ast_node_t *body = parse_block(p);

  expect(p, TOK_END, "expected 'hết'/'end' after loop block");

  ast_node_t *n = ast_new(AST_LOOP);
  n->line = line;
  ast_add_child(n, count);
  ast_add_child(n, body);
  return n;
}

static ast_node_t *parse_while_stmt(vir_parser_t *p) {
  /* WHILE expr ':'|THEN block END (legacy, still supported) */
  uint32_t line = peek(p)->line;

  ast_node_t *cond = parse_expr(p);
  if (!cond)
    return NULL;

  expect_block_open(p, "while condition");

  ast_node_t *body = parse_block(p);

  expect(p, TOK_END, "expected 'hết'/'end' after while block");

  ast_node_t *n = ast_new(AST_WHILE);
  n->line = line;
  ast_add_child(n, cond);
  ast_add_child(n, body);
  return n;
}

/* ═══════════════════════════════════════════════════════
 * When-Loop (v1.2 conditional loop)
 * ═══════════════════════════════════════════════════════
 * Syntax:  when COND loop BLOCK end
 * Equivalent to: while COND then BLOCK end
 */

static ast_node_t *parse_when_loop_stmt(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  ast_node_t *cond = parse_expr(p);
  if (!cond)
    return NULL;

  expect(p, TOK_LOOP, "expected 'loop' after when condition");

  ast_node_t *body = parse_block(p);

  expect(p, TOK_END, "expected 'end' after when...loop block");

  /* Lower to AST_WHILE — same semantics */
  ast_node_t *n = ast_new(AST_WHILE);
  n->line = line;
  ast_add_child(n, cond);
  ast_add_child(n, body);
  return n;
}

static ast_node_t *parse_return_stmt(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  /* Idiom in stdlib: `out skip;` / `out break;` inside a `when … loop`
   * — desugars to BREAK (exit loop), not return. Every occurrence in
   * stdlib uses this to short-circuit the enclosing loop (read 0,
   * mismatch found, buffer full, newline reached, …). Continue-
   * semantics would loop forever in those cases. */
  if (check(p, TOK_SKIP) || check(p, TOK_BREAK) || check(p, TOK_CONTINUE)) {
    const vir_token_t *kw = advance(p);
    ast_type_t at = (kw->type == TOK_CONTINUE) ? AST_CONTINUE : AST_BREAK;
    ast_node_t *cf = ast_new(at);
    cf->line = line;
    match(p, TOK_SEMICOLON);
    return cf;
  }

  ast_node_t *n = ast_new(AST_RETURN);
  n->line = line;

  /* Optional return value */
  if (!check(p, TOK_NEWLINE) && !check(p, TOK_END) && !check(p, TOK_EOF) &&
      !check(p, TOK_ELSE) && !check(p, TOK_SEMICOLON)) {
    ast_node_t *val = parse_expr(p);
    if (val)
      ast_add_child(n, val);
  }
  match(p, TOK_SEMICOLON); /* optional ';' */
  return n;
}

static ast_node_t *parse_print_stmt(vir_parser_t *p) {
  uint32_t line = peek(p)->line;
  ast_node_t *n = ast_new(AST_PRINT);
  n->line = line;

  ast_node_t *val = parse_expr(p);
  if (val)
    ast_add_child(n, val);
  return n;
}

static ast_node_t *parse_func_def(vir_parser_t *p) {
  /* v2.0:   func IDENT ':' [in(...)] block end.
   *         func IDENT '(' params ')' [-> type] ':' block end.
   * Both inline `()` and body `in`/`ref`/`out` groups are valid (§6, §14). */
  const vir_token_t *name_tok = expect_func_name(p);
  if (!name_tok)
    return NULL;

  ast_node_t *fn = ast_new(AST_FUNC_DEF);
  strncpy(fn->name, name_tok->str.buf, AST_NAME_LEN - 1);
  fn->line = name_tok->line;

  /* §16: Optional generic clause `<T>` or `<T, U>` after function name.
   * C-core does not implement generics — we parse and discard the
   * clause so the surface syntax is accepted. */
  if (match(p, TOK_LT)) {
    int depth = 1;
    while (depth > 0 && !check(p, TOK_EOF)) {
      if (check(p, TOK_LT))
        depth++;
      else if (check(p, TOK_GT))
        depth--;
      advance(p);
      if (depth == 0)
        break;
    }
  }

  if (check(p, TOK_COLON)) {
    /* ─── v1.2 syntax: func name: [in(a:int; b:int)] block end ─── */
    advance(p); /* consume ':' */
    skip_newlines(p);

    /* Optional in(...) parameter block */
    if (check(p, TOK_IN)) {
      advance(p); /* consume 'in' */
      expect(p, TOK_LPAREN, "expected '(' after 'in'");

      /* §12.5 Leading orphan separator: `in(; a:int)` */
      if (check(p, TOK_SEMICOLON) || check(p, TOK_COMMA)) {
        fprintf(stderr,
                "warning W14: empty parameter group before first parameter at "
                "line %u\n",
                peek(p)->line);
        while (check(p, TOK_SEMICOLON) || check(p, TOK_COMMA))
          advance(p);
      }

      /* Parse params: [ref] name[:type] separated by ';' or ',' */
      if (!check(p, TOK_RPAREN)) {
        for (;;) {
          int is_ref_param = 0;
          if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "ref") == 0) {
            advance(p); /* consume 'ref' */
            is_ref_param = 1;
          }
          const vir_token_t *param_tok =
              expect_name(p, "expected parameter name");
          if (!param_tok)
            break;
          ast_node_t *param = ast_new(AST_IDENTIFIER);
          strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
          param->line = param_tok->line;
          if (is_ref_param)
            param->flags |= AST_FLAG_REF_PARAM;
          /* Optional type hint: ':' TYPE[<T>] */
          if (match(p, TOK_COLON)) {
            if (check(p, TOK_LBRACKET)) {
              advance(p);
              if (check(p, TOK_IDENT)) {
                snprintf(param->name2, AST_NAME_LEN, "[%s]", peek(p)->str.buf);
                advance(p);
              }
              expect(p, TOK_RBRACKET, "expected ']' in array type");
              param->int_val |= 0x10000;
            } else if (peek(p)->type != TOK_EOF && peek(p)->type != TOK_RPAREN && peek(p)->type != TOK_COMMA && peek(p)->type != TOK_SEMICOLON) {
              strncpy(param->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
              advance(p);
            }
            /* Skip generic type params: Vec<KeywordEntry>, etc. */
            capture_generic_elem_type(p, param);
            if (match(p, TOK_LT)) {
              int depth = 1;
              while (depth > 0 && !check(p, TOK_EOF)) {
                if (check(p, TOK_LT)) depth++;
                else if (check(p, TOK_GT)) depth--;
                else if (check(p, TOK_CAST)) depth -= 2;
                advance(p);
              }
            }
          }
          ast_add_child(fn, param);
          /* v1.2 uses ';' separator, also accept ',' */
          if (!match(p, TOK_SEMICOLON) && !match(p, TOK_COMMA))
            break;
          /* §12.5 After a separator: trailing `;)` or consecutive `;;` */
          if (check(p, TOK_RPAREN)) {
            fprintf(stderr,
                    "warning W14: trailing parameter separator before ')' at "
                    "line %u\n",
                    peek(p)->line);
            break;
          }
          if (check(p, TOK_SEMICOLON) || check(p, TOK_COMMA)) {
            fprintf(stderr, "warning W14: empty parameter group at line %u\n",
                    peek(p)->line);
            while (check(p, TOK_SEMICOLON) || check(p, TOK_COMMA))
              advance(p);
            if (check(p, TOK_RPAREN))
              break;
          }
        }
      }
      expect(p, TOK_RPAREN, "expected ')' after parameters");
      if (match(p, TOK_ARROW)) {
        if (check(p, TOK_IDENT)) {
          const vir_token_t *rt = advance(p);
          if (match(p, TOK_LT)) {
            int depth = 1;
            while (depth > 0 && !check(p, TOK_EOF)) {
              if (check(p, TOK_LT)) depth++;
              else if (check(p, TOK_GT)) depth--;
              else if (check(p, TOK_CAST)) depth -= 2;
              advance(p);
            }
          }
        }
      } else if (match(p, TOK_OUT)) {
        if (match(p, TOK_LPAREN)) {
            while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF)) advance(p);
            match(p, TOK_RPAREN);
        } else if (check(p, TOK_IDENT)) {
            advance(p);
        }
      }
      skip_newlines(p);
    }

    ast_node_t *body = parse_block(p);
    ast_add_child(fn, body);

    expect(p, TOK_END, "expected 'end' to close function");
    match(p, TOK_DOT); /* Vir v2.0: definition blocks close with end. */
    return fn;
  }

  /* Vir v2.0 inline params: func name(a, b): ... end. (§6, §14.1) */
  expect(p, TOK_LPAREN, "expected '(' after function name");

  /* Parse parameters → stored as IDENTIFIER children.
   * Each param: [ref] NAME [':' TYPE]. Separator: ',' or ';'. */
  if (!check(p, TOK_RPAREN)) {
    for (;;) {
      int is_ref_param = 0;
      if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "ref") == 0) {
        advance(p); /* consume 'ref' */
        is_ref_param = 1;
      }
      const vir_token_t *param_tok =
          expect_name(p, "expected parameter name");
      if (!param_tok)
        break;
      ast_node_t *param = ast_new(AST_IDENTIFIER);
      strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
      param->line = param_tok->line;
      if (is_ref_param)
        param->flags |= AST_FLAG_REF_PARAM;
      /* Optional type annotation: ':' TYPE  (skip composite types
       * like [i32], Vec<T> until separator) */
      if (match(p, TOK_COLON)) {
        if (check(p, TOK_LBRACKET)) {
          advance(p);
          if (check(p, TOK_IDENT)) {
            snprintf(param->name2, AST_NAME_LEN, "[%s]", peek(p)->str.buf);
            advance(p);
          }
          expect(p, TOK_RBRACKET, "expected ']' in array type");
          param->int_val |= 0x10000;
        } else if (check(p, TOK_IDENT)) {
          const vir_token_t *tt = advance(p);
          strncpy(param->name2, tt->str.buf, AST_NAME_LEN - 1);
          capture_generic_elem_type(p, param);
        }
        /* Consume any remaining type-decoration tokens until
         * separator/closing-paren, accounting for nested generic brackets `< >`. */
        int angle_depth = 0;
        while (!check(p, TOK_EOF)) {
          if (check(p, TOK_LT)) angle_depth++;
          else if (check(p, TOK_GT)) angle_depth--;
          
          if (angle_depth == 0 && (check(p, TOK_COMMA) || check(p, TOK_SEMICOLON) || check(p, TOK_RPAREN))) {
            break;
          }
          advance(p);
        }
      }
      ast_add_child(fn, param);
      if (!match(p, TOK_COMMA) && !match(p, TOK_SEMICOLON))
        break;
    }
  }

  expect(p, TOK_RPAREN, "expected ')' after parameters");
  /* Optional return type: '->' TYPE  (skip until block opener) */
  if (check(p, TOK_ARROW)) {
    advance(p);
    while (!check(p, TOK_COLON) && !check(p, TOK_THEN) &&
           !check(p, TOK_NEWLINE) && !check(p, TOK_EOF)) {
      advance(p);
    }
  }
  expect_block_open(p, "function signature");

  ast_node_t *body = parse_block(p);
  ast_add_child(fn, body); /* Last non-epilogue child = body block */

  /* Optional function-level §13 epilogue: revert + ensure blocks. */
  if (check(p, TOK_REVERT)) {
    advance(p);
    expect_block_open(p, "revert");
    ast_node_t *rb = ast_new(AST_REVERT_BLOCK);
    rb->line = peek(p)->line;
    ast_node_t *rbody = parse_block(p);
    ast_add_child(rb, rbody);
    ast_add_child(fn, rb);
  }
  if (check(p, TOK_ENSURE)) {
    advance(p);
    expect_block_open(p, "ensure");
    ast_node_t *eb = ast_new(AST_ENSURE_BLOCK);
    eb->line = peek(p)->line;
    ast_node_t *ebody = parse_block(p);
    ast_add_child(eb, ebody);
    ast_add_child(fn, eb);
  }

  expect(p, TOK_END, "expected 'hết'/'end' to close function");
  /* §12: `end.` — optional module/function sentinel period. */
  match(p, TOK_DOT);
  return fn;
}

/* ═══════════════════════════════════════════════════════
 * For-Range Statement
 * ═══════════════════════════════════════════════════════
 * Syntax:  for IDENT in START..END then block end
 *          với mỗi IDENT trong START..END thì block hết
 *
 * Children: [0]=start, [1]=end, [2]=body block
 * name = loop variable name
 */

static ast_node_t *parse_for_range_stmt(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  const vir_token_t *var_tok = expect_name(p, "expected loop variable");
  if (!var_tok)
    return NULL;

  /* §20.3: `for k, v in dict:` — dict iteration.  Desugars into a
   *   var __kv_keys__<line> = keys(dict)
   *   for __kv_i__ in 0..len(__kv_keys__):
   *       var k = __kv_keys__[__kv_i__]
   *       var v = dict[k]
   *       body
   * wrapped in AST_BLOCK. */
  if (check(p, TOK_COMMA)) {
    advance(p);
    const vir_token_t *v2_tok =
        expect_name(p, "expected value variable after ','");
    if (!v2_tok)
      return NULL;
    char kname[AST_NAME_LEN], vname[AST_NAME_LEN];
    strncpy(kname, var_tok->str.buf, AST_NAME_LEN - 1);
    kname[AST_NAME_LEN - 1] = '\0';
    strncpy(vname, v2_tok->str.buf, AST_NAME_LEN - 1);
    vname[AST_NAME_LEN - 1] = '\0';

    if (!expect(p, TOK_IN, "expected 'in' after 'for k,v'"))
      return NULL;

    ast_node_t *dict_expr = parse_expr(p);
    if (!dict_expr)
      return NULL;

    expect_block_open(p, "for dict iter");
    ast_node_t *body = parse_block(p);
    expect(p, TOK_END, "expected 'end' after for block");

    /* Require dict_expr to be a bare identifier for stable reuse
     * across iterations (avoids re-evaluating).  If not, still wrap:
     * we evaluate once and store in a temp var. */
    char dname[AST_NAME_LEN];
    ast_node_t *outer = ast_new(AST_BLOCK);
    outer->line = line;

    if (dict_expr->type == AST_IDENTIFIER) {
      strncpy(dname, dict_expr->name, AST_NAME_LEN - 1);
      dname[AST_NAME_LEN - 1] = '\0';
      ast_free(dict_expr);
    } else {
      snprintf(dname, AST_NAME_LEN, "__kv_d_%u", line);
      ast_node_t *d_decl = ast_new(AST_VAR_DECL);
      strncpy(d_decl->name, dname, AST_NAME_LEN - 1);
      d_decl->line = line;
      ast_add_child(d_decl, dict_expr);
      ast_add_child(outer, d_decl);
    }

    /* var __kv_keys_<line> = keys(<dict>) */
    char ks_name[AST_NAME_LEN];
    snprintf(ks_name, AST_NAME_LEN, "__kv_keys_%u", line);
    ast_node_t *ks_decl = ast_new(AST_VAR_DECL);
    strncpy(ks_decl->name, ks_name, AST_NAME_LEN - 1);
    ks_decl->line = line;
    ast_node_t *keys_call = ast_new(AST_BUILTIN_CALL);
    keys_call->builtin_id = BUILTIN_KEYS;
    ast_node_t *dict_id = ast_new(AST_IDENTIFIER);
    strncpy(dict_id->name, dname, AST_NAME_LEN - 1);
    ast_add_child(keys_call, dict_id);
    ast_add_child(ks_decl, keys_call);
    ast_add_child(outer, ks_decl);

    /* for __kv_i_<line> in 0..len(__kv_keys_<line>): body_with_kv end */
    ast_node_t *for_n = ast_new(AST_FOR_RANGE);
    char iname[AST_NAME_LEN];
    snprintf(iname, AST_NAME_LEN, "__kv_i_%u", line);
    strncpy(for_n->name, iname, AST_NAME_LEN - 1);
    for_n->line = line;
    ast_node_t *zero = ast_new(AST_LITERAL_INT);
    zero->int_val = 0;
    ast_add_child(for_n, zero);
    ast_node_t *len_call = ast_new(AST_BUILTIN_CALL);
    len_call->builtin_id = BUILTIN_LEN;
    ast_node_t *ks_id = ast_new(AST_IDENTIFIER);
    strncpy(ks_id->name, ks_name, AST_NAME_LEN - 1);
    ast_add_child(len_call, ks_id);
    ast_add_child(for_n, len_call);

    ast_node_t *inner = ast_new(AST_BLOCK);
    inner->line = line;
    /* var k = __kv_keys[__kv_i] */
    ast_node_t *k_decl = ast_new(AST_VAR_DECL);
    strncpy(k_decl->name, kname, AST_NAME_LEN - 1);
    ast_node_t *k_idx = ast_new(AST_INDEX_ACCESS);
    strncpy(k_idx->name, ks_name, AST_NAME_LEN - 1);
    ast_node_t *i_id = ast_new(AST_IDENTIFIER);
    strncpy(i_id->name, iname, AST_NAME_LEN - 1);
    ast_add_child(k_idx, i_id);
    ast_add_child(k_decl, k_idx);
    ast_add_child(inner, k_decl);
    /* var v = <dict>[k] */
    ast_node_t *v_decl = ast_new(AST_VAR_DECL);
    strncpy(v_decl->name, vname, AST_NAME_LEN - 1);
    ast_node_t *v_idx = ast_new(AST_INDEX_ACCESS);
    strncpy(v_idx->name, dname, AST_NAME_LEN - 1);
    ast_node_t *k_id = ast_new(AST_IDENTIFIER);
    strncpy(k_id->name, kname, AST_NAME_LEN - 1);
    ast_add_child(v_idx, k_id);
    ast_add_child(v_decl, v_idx);
    ast_add_child(inner, v_decl);
    /* user body statements */
    if (body && body->type == AST_BLOCK) {
      for (uint32_t i = 0; i < body->child_count; i++) {
        ast_add_child(inner, body->children[i]);
      }
      body->child_count = 0;
      ast_free(body);
    } else if (body) {
      ast_add_child(inner, body);
    }
    ast_add_child(for_n, inner);
    ast_add_child(outer, for_n);
    return outer;
  }

  if (!expect(p, TOK_IN, "expected 'in'/'trong' after for variable"))
    return NULL;

  /* Parse start expression */
  ast_node_t *start = parse_expr(p);
  if (!start)
    return NULL;

  ast_node_t *end_expr = NULL;

  if (start->type == AST_BINOP && start->op == OP_PATTERN) {
    /* 0..n was parsed as a single binary op by parse_expr! */
    ast_node_t *real_start = start->children[0];
    end_expr = start->children[1];
    start->child_count = 0; /* Unlink children so we can free the binary op node */
    ast_free(start);
    start = real_start;
  } else {
    if (!expect(p, TOK_DOTDOT, "expected '..' in range"))
      return NULL;

    /* Parse end expression */
    end_expr = parse_expr(p);
    if (!end_expr) {
      ast_free(start);
      return NULL;
    }
  }

  expect_block_open(p, "for range");

  ast_node_t *body = parse_block(p);

  expect(p, TOK_END, "expected 'hết'/'end' after for block");

  ast_node_t *n = ast_new(AST_FOR_RANGE);
  strncpy(n->name, var_tok->str.buf, AST_NAME_LEN - 1);
  n->line = line;
  ast_add_child(n, start);
  ast_add_child(n, end_expr);
  ast_add_child(n, body);
  return n;
}

/* ═══════════════════════════════════════════════════════
 * Enum Definition
 * ═══════════════════════════════════════════════════════
 * Syntax:  enum Name then
 *            VARIANT = value
 *            ...
 *          end
 *
 * name = enum type name
 * children: AST_LITERAL_INT nodes, each with name=variant, int_val=value
 */

static ast_node_t *parse_enum_def(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  const vir_token_t *name_tok = expect_name(p, "expected enum name");
  if (!name_tok)
    return NULL;

  /* §16: Optional generic clause `<T>` or `<T, U>` after enum name. */
  if (match(p, TOK_LT)) {
    int depth = 1;
    while (depth > 0 && !check(p, TOK_EOF)) {
      if (check(p, TOK_LT))
        depth++;
      else if (check(p, TOK_GT))
        depth--;
      advance(p);
      if (depth == 0)
        break;
    }
  }

  /* Accept ':' or 'then' */
  expect_block_open(p, "enum name");
  skip_newlines(p);

  ast_node_t *en = ast_new(AST_ENUM_DEF);
  strncpy(en->name, name_tok->str.buf, AST_NAME_LEN - 1);
  en->line = line;

  int64_t next_val = 0; /* auto-increment if no explicit value */

  while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
    const vir_token_t *vname =
        expect_name(p, "expected enum variant name");
    if (!vname)
      break;

    int64_t val = next_val;
    /* Tagged enum variant: `Ok(value)`, `Some(T)`. The C-core does
     * not yet model payloads — we accept and discard the parenthesized
     * type/payload so the surface syntax parses. The auto-incremented
     * tag is still assigned to the variant. */
    if (match(p, TOK_LPAREN)) {
      int depth = 1;
      while (depth > 0 && !check(p, TOK_EOF)) {
        if (check(p, TOK_LPAREN))
          depth++;
        else if (check(p, TOK_RPAREN))
          depth--;
        advance(p);
        if (depth == 0)
          break;
      }
    }
    if (match(p, TOK_ASSIGN)) {
      /* Explicit value */
      const vir_token_t *vt = expect(p, TOK_INT, "expected integer value");
      if (vt)
        val = vt->int_val;
    }
    next_val = val + 1;

    ast_node_t *variant = ast_new(AST_LITERAL_INT);
    strncpy(variant->name, vname->str.buf, AST_NAME_LEN - 1);
    variant->int_val = val;
    variant->line = vname->line;
    ast_add_child(en, variant);

    /* Accept trailing `,` or `;` between variants. */
    if (check(p, TOK_COMMA) || check(p, TOK_SEMICOLON))
      advance(p);
    skip_newlines(p);
  }

  expect(p, TOK_END, "expected 'hết'/'end' after enum definition");
  /* §12: `end.` — optional module/enum sentinel period. */
  match(p, TOK_DOT);
  return en;
}

/* ═══════════════════════════════════════════════════════
 * Record (Struct) Definition
 * ═══════════════════════════════════════════════════════
 * Syntax:  record Name then
 *            field_name: type_hint
 *            ...
 *          end
 *
 * name = record type name
 * children: AST_IDENTIFIER nodes, each with name=field_name
 * (type hints are stored in name2 but not used for codegen yet)
 */

static ast_node_t *parse_record_def(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  const vir_token_t *name_tok = expect_name(p, "expected record name");
  if (!name_tok)
    return NULL;

  /* §16: Optional generic clause `<T>` or `<T, U>` after record name. */
  if (match(p, TOK_LT)) {
    int depth = 1;
    while (depth > 0 && !check(p, TOK_EOF)) {
      if (check(p, TOK_LT))
        depth++;
      else if (check(p, TOK_GT))
        depth--;
      advance(p);
      if (depth == 0)
        break;
    }
  }

  /* Accept ':' or 'then' as block opener (optional for entity) */
  if (!match(p, TOK_COLON))
    match(p, TOK_THEN);
  skip_newlines(p);

  ast_node_t *rec = ast_new(AST_RECORD_DEF);
  strncpy(rec->name, name_tok->str.buf, AST_NAME_LEN - 1);
  rec->line = line;

  while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
    if (match(p, TOK_METHOD)) {
      /* §11.4: method name(params) block end */
      const vir_token_t *mname = expect_name(p, "expected method name");
      if (!mname)
        break;

      ast_node_t *fn = ast_new(AST_FUNC_DEF);
      strncpy(fn->name, mname->str.buf, AST_NAME_LEN - 1);
      fn->line = mname->line;

      /* Add implicit 'this' parameter as first child */
      ast_node_t *this_param = ast_new(AST_IDENTIFIER);
      strncpy(this_param->name, "this", AST_NAME_LEN - 1);
      this_param->line = mname->line;
      ast_add_child(fn, this_param);

      /* Optional parameters: `(n: int, ...)` */
      if (match(p, TOK_LPAREN)) {
        if (!check(p, TOK_RPAREN)) {
          do {
            const vir_token_t *pname =
                expect_name(p, "expected param name");
            if (!pname)
              break;
            ast_node_t *param = ast_new(AST_IDENTIFIER);
            strncpy(param->name, pname->str.buf, AST_NAME_LEN - 1);
            param->line = pname->line;
            /* Skip type hint */
            if (match(p, TOK_COLON)) {
              if (check(p, TOK_IDENT))
                advance(p);
            }
            ast_add_child(fn, param);
          } while (match(p, TOK_COMMA));
        }
        expect(p, TOK_RPAREN, "expected ')' after method params");
      }

      /* Optional return type: `: int` or `-> int` */
      if (check(p, TOK_ARROW)) {
        advance(p);
        if (check(p, TOK_IDENT))
          advance(p);
      } else if (check(p, TOK_COLON)) {
        /* Peek ahead: if it's IDENT then NEWLINE/COLON, it's a return type.
         * If it's just NEWLINE, it's a block opener. */
        if (p->pos + 1 < p->token_count &&
            p->tokens[p->pos + 1].type == TOK_IDENT) {
          advance(p); /* ':' */
          advance(p); /* type */
        }
      }

      expect_block_open(p, "method signature");

      ast_node_t *body = parse_block(p);
      ast_add_child(fn, body);
      expect(p, TOK_END, "expected 'end' after method body");
      match(p, TOK_DOT); /* optional '.' */

      ast_add_child(rec, fn);
      skip_newlines(p);
      continue;
    }

    const vir_token_t *fname = expect_name(p, "expected field name");
    if (!fname)
      break;

    ast_node_t *field = ast_new(AST_IDENTIFIER);
    strncpy(field->name, fname->str.buf, AST_NAME_LEN - 1);
    field->line = fname->line;

    /* Optional type hint: field_name: type
     * Skip complex types like [i32], Vec<T>, etc. until newline */
    if (match(p, TOK_COLON)) {
      if (check(p, TOK_LBRACKET)) {
        advance(p);
        if (check(p, TOK_IDENT)) {
          snprintf(field->name2, AST_NAME_LEN, "[%s]", peek(p)->str.buf);
          advance(p);
        }
        expect(p, TOK_RBRACKET, "expected ']' in array type");
        field->int_val |= 0x10000;
      } else if (check(p, TOK_IDENT)) {
        strncpy(field->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
        advance(p);
        capture_generic_elem_type(p, field);
      }
      while (!check(p, TOK_NEWLINE) && !check(p, TOK_END) &&
             !check(p, TOK_EOF)) {
        advance(p);
      }
    }

    ast_add_child(rec, field);
    skip_newlines(p);
  }

  expect(p, TOK_END, "expected 'hết'/'end' after record definition");
  /* §12: `end.` — optional module/record sentinel period. */
  match(p, TOK_DOT);
  return rec;
}

/* ═══════════════════════════════════════════════════════
 * §16 Register & Mold — bit-level type definitions
 * ═══════════════════════════════════════════════════════
 * Register:
 *     register UART_SR: u32
 *         PE: 0           # single-bit field at bit 0
 *         RXNE: 5         # single-bit field at bit 5
 *         MODE0: 0..1     # 2-bit field occupying bits 0 and 1
 *     end
 *
 * Mold:
 *     mold Pixel: u16
 *         r: 5, g: 6, b: 5        # sequential bit widths from LSB
 *     end
 *
 * Both lower to an AST node whose children are AST_IDENTIFIER field
 * descriptors; `int_val` encodes bit position: (width << 8) | lo.
 */

static int base_width_from_ident(const char *s) {
  if (!s)
    return 0;
  if (strcmp(s, "u8") == 0 || strcmp(s, "i8") == 0)
    return 8;
  if (strcmp(s, "u16") == 0 || strcmp(s, "i16") == 0)
    return 16;
  if (strcmp(s, "u32") == 0 || strcmp(s, "i32") == 0)
    return 32;
  if (strcmp(s, "u64") == 0 || strcmp(s, "i64") == 0 || strcmp(s, "int") == 0)
    return 64;
  return 0;
}

static ast_node_t *parse_register_def(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  const vir_token_t *name_tok = expect_name(p, "expected register name");
  if (!name_tok)
    return NULL;

  ast_node_t *reg = ast_new(AST_REGISTER_DEF);
  strncpy(reg->name, name_tok->str.buf, AST_NAME_LEN - 1);
  reg->line = line;

  /* Optional base-type annotation: `: u32` */
  if (match(p, TOK_COLON)) {
    if (check(p, TOK_IDENT)) {
      const vir_token_t *bt = peek(p);
      strncpy(reg->name2, bt->str.buf, AST_NAME_LEN - 1);
      reg->int_val = base_width_from_ident(bt->str.buf);
      advance(p);
    }
  }
  if (reg->int_val == 0)
    reg->int_val = 32; /* default */
  skip_newlines(p);

  while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
    const vir_token_t *fname = expect_name(p, "expected field name");
    if (!fname)
      break;
    ast_node_t *field = ast_new(AST_IDENTIFIER);
    strncpy(field->name, fname->str.buf, AST_NAME_LEN - 1);
    field->line = fname->line;
    if (!expect(p, TOK_COLON, "expected ':' after field name"))
      break;

    /* Bit position: `N` (single bit) or `LO..HI` (multi-bit range) */
    int64_t lo = 0, hi = -1;
    const vir_token_t *lo_tok = expect(p, TOK_INT, "expected bit position");
    if (!lo_tok)
      break;
    lo = lo_tok->int_val;
    if (match(p, TOK_DOTDOT)) {
      const vir_token_t *hi_tok = expect(p, TOK_INT, "expected high bit");
      if (!hi_tok)
        break;
      hi = hi_tok->int_val;
    }
    uint32_t width = (hi < 0) ? 1 : (uint32_t)(hi - lo + 1);
    if (width == 0 || width > 64 || lo < 0 || lo > 63) {
      parse_error(p, "invalid bit range in register field");
      break;
    }
    field->int_val = ((int64_t)width << 8) | (lo & 0xFF);
    ast_add_child(reg, field);

    /* Allow optional ',' or ';' separator (tolerant). */
    if (check(p, TOK_COMMA) || check(p, TOK_SEMICOLON))
      advance(p);
    skip_newlines(p);
  }

  expect(p, TOK_END, "expected 'end' after register definition");
  return reg;
}

static ast_node_t *parse_mold_def(vir_parser_t *p) {
  uint32_t line = peek(p)->line;

  const vir_token_t *name_tok = expect_name(p, "expected mold name");
  if (!name_tok)
    return NULL;

  ast_node_t *md = ast_new(AST_MOLD_DEF);
  strncpy(md->name, name_tok->str.buf, AST_NAME_LEN - 1);
  md->line = line;

  if (match(p, TOK_COLON)) {
    if (check(p, TOK_IDENT)) {
      const vir_token_t *bt = peek(p);
      strncpy(md->name2, bt->str.buf, AST_NAME_LEN - 1);
      md->int_val = base_width_from_ident(bt->str.buf);
      advance(p);
    }
  }
  if (md->int_val == 0)
    md->int_val = 32;
  skip_newlines(p);

  /* Mold fields are given as `name: width` comma-separated; bit positions
   * are assigned sequentially from LSB. */
  uint32_t next_lo = 0;
  while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
    const vir_token_t *fname = expect_name(p, "expected mold field name");
    if (!fname)
      break;
    ast_node_t *field = ast_new(AST_IDENTIFIER);
    strncpy(field->name, fname->str.buf, AST_NAME_LEN - 1);
    field->line = fname->line;
    if (!expect(p, TOK_COLON, "expected ':' after mold field"))
      break;
    const vir_token_t *w_tok = expect(p, TOK_INT, "expected bit width");
    if (!w_tok)
      break;
    int64_t width = w_tok->int_val;
    if (width <= 0 || width > 64 || next_lo + width > 64) {
      parse_error(p, "invalid mold field width");
      break;
    }
    field->int_val = ((int64_t)width << 8) | (next_lo & 0xFF);
    ast_add_child(md, field);
    next_lo += (uint32_t)width;
    if (check(p, TOK_COMMA) || check(p, TOK_SEMICOLON))
      advance(p);
    skip_newlines(p);
  }

  expect(p, TOK_END, "expected 'end' after mold definition");
  return md;
}

/* ═══════════════════════════════════════════════════════
 * TASK A1: Pattern Match (case expr :~ ... end)
 * ═══════════════════════════════════════════════════════
 *
 * Syntax:
 *   case EXPR :~
 *       PATTERN1: BODY1;
 *       PATTERN2: BODY2;
 *       _:        DEFAULT_BODY;
 *   end
 *
 * AST:
 *   AST_CASE
 *     children[0] = subject expr
 *     children[1..n] = AST_PATTERN_MATCH arms
 *       Each arm: name = pattern literal ("_" for wildcard)
 *                 int_val = pattern int value (if integer literal)
 *                 children[0] = body statement/block
 */
static ast_node_t *parse_case_stmt(vir_parser_t *p) {
  /* TOK_CASE already consumed.  Parse subject expression. */
  ast_node_t *subject = parse_expr(p);
  if (!subject) {
    parse_error(p, "expected expression after 'case'");
    return NULL;
  }

  /* Expect :~ token (optional in §21 simple form) or block opener */
  if (check(p, TOK_PATTERN)) {
    advance(p);
    if (check(p, TOK_COLON)) advance(p);
  } else {
    expect_block_open(p, "case subject");
  }

  ast_node_t *node = ast_new(AST_CASE);
  node->line = subject->line;
  ast_add_child(node, subject); /* children[0] = subject */

  skip_newlines(p);

  /* Parse arms until 'end' */
  while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
    ast_node_t *arm = ast_new(AST_PATTERN_MATCH);

    /* Vir v2.0 case arms start with `case` */
    match(p, TOK_CASE);

    const vir_token_t *pat = peek(p);

    if (pat->type == TOK_ELSE ||
        (pat->type == TOK_IDENT && strcmp(pat->str.buf, "_") == 0)) {
      /* Wildcard arm (else: or _:) */
      strncpy(arm->name, "_", AST_NAME_LEN - 1);
      arm->int_val = -1; /* sentinel: wildcard */
      advance(p);
    } else if (pat->type == TOK_INT) {
      /* Integer literal pattern */
      arm->int_val = pat->int_val;
      snprintf(arm->name, AST_NAME_LEN, "%lld", (long long)pat->int_val);
      advance(p);
    } else if (pat->type == TOK_STRING) {
      /* String literal pattern */
      strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
      arm->int_val = -2; /* sentinel: string pattern */
      advance(p);
    } else if (pat->type == TOK_IDENT) {
      /* Named pattern (enum variant or variable). Accept tagged
       * form `Variant(_)` or `Variant(name)` by skipping the
       * parenthesized payload binder; semantics are the same as
       * the bare named pattern at C-core level. */
      strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
      arm->int_val = -3; /* sentinel: named pattern */
      advance(p);
      if (match(p, TOK_LPAREN)) {
        /* Capture first binding identifier into name2, e.g. Some(v) -> name2="v" */
        if (peek(p)->type == TOK_IDENT) {
          const vir_token_t *bind = advance(p);
          strncpy(arm->name2, bind->str.buf, AST_NAME_LEN - 1);
          /* Skip any remaining tokens until matching ')' */
          while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF))
            advance(p);
          match(p, TOK_RPAREN);
        } else {
          /* No binding — just consume until ')' */
          int depth = 1;
          while (depth > 0 && !check(p, TOK_EOF)) {
            if (check(p, TOK_LPAREN))
              depth++;
            else if (check(p, TOK_RPAREN))
              depth--;
            advance(p);
            if (depth == 0)
              break;
          }
        }
      }
    } else {
      parse_error(p, "expected pattern in case arm");
      ast_free(arm);
      break;
    }

    arm->line = pat->line;

    /* Expect ':' separator */
    expect(p, TOK_COLON, "expected ':' after pattern");

    /* Parse body — one or more statements; terminators: newline
     * before next pattern or ';' before next pattern, or 'end'. */
    skip_newlines(p);
    while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
      /* Peek: if the next tokens look like a new pattern we stop.
       * Cheap heuristic: TOK_INT/TOK_STRING/TOK_ELSE or IDENT('_')
       * followed by ':' indicates another arm. */
      int starts_new_arm = 0;
      if (check(p, TOK_CASE) || check(p, TOK_ELSE))
        starts_new_arm = 1;
      else if ((check(p, TOK_INT) || check(p, TOK_STRING)) &&
               p->pos + 1 < p->token_count &&
               p->tokens[p->pos + 1].type == TOK_COLON) {
        starts_new_arm = 1;
      } else if (check(p, TOK_IDENT)) {
        if (p->pos + 1 < p->token_count && p->tokens[p->pos + 1].type == TOK_COLON) {
          starts_new_arm = 1;
        } else if (p->pos + 1 < p->token_count && p->tokens[p->pos + 1].type == TOK_LPAREN) {
          int nxt = p->pos + 2;
          int d = 1;
          while (nxt < p->token_count && d > 0) {
            if (p->tokens[nxt].type == TOK_LPAREN) d++;
            else if (p->tokens[nxt].type == TOK_RPAREN) d--;
            nxt++;
          }
          if (nxt < p->token_count && p->tokens[nxt].type == TOK_COLON) {
            starts_new_arm = 1;
          }
        }
      }
      if (starts_new_arm)
        break;
      ast_node_t *body = parse_statement(p);
      if (body) {
        ast_add_child(arm, body);
      } else {
        if (p->error[0] != '\0') break;
        if (!check(p, TOK_EOF)) advance(p);
      }
      /* Inter-stmt separators */
      while (check(p, TOK_SEMICOLON) || check(p, TOK_COMMA))
        advance(p);
      skip_newlines(p);
    }

    match(p, TOK_SEMICOLON); /* optional ';' */
    skip_newlines(p);

    ast_add_child(node, arm);
  }

  expect(p, TOK_END, "expected 'end'/'hết' after case block");
  return node;
}

static int parse_module_path(vir_parser_t *p, char *out_name) {
  size_t pos = 0;
  out_name[0] = '\0';
  while (is_name_token(peek(p)->type)) {
    const vir_token_t *seg = advance(p);
    size_t n_seg = strlen(seg->str.buf);
    if (pos + n_seg + 2 >= AST_NAME_LEN)
      break;
    memcpy(out_name + pos, seg->str.buf, n_seg);
    pos += n_seg;
    if (check(p, TOK_COLON)) {
      const vir_token_t *nxt =
          (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
      if (nxt && nxt->type == TOK_COLON) {
        advance(p);
        advance(p);
        out_name[pos++] = ':';
        out_name[pos++] = ':';
      } else {
        break;
      }
    } else if (check(p, TOK_DOT)) {
      advance(p);
      out_name[pos++] = '.';
    } else {
      break;
    }
  }
  out_name[pos] = '\0';
  return pos > 0;
}

static ast_node_t *parse_statement(vir_parser_t *p) {
  skip_newlines(p);
  const vir_token_t *t = peek(p);

  /* §18 `@entry func NAME:` — attribute consumed at statement level.
   * We rename the tagged function to "main" so the existing entry
   * lookup in vm picks it up. int_val bit 0x20000 marks it. */
  if (t->type == TOK_AT) {
    advance(p);
    const vir_token_t *at_name =
        expect_name(p, "expected attribute name after '@'");
    if (!at_name)
      return NULL;
    int is_entry = (strcmp(at_name->str.buf, "entry") == 0);
    /* consume optional `()` */
    if (match(p, TOK_LPAREN)) {
      while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF))
        advance(p);
      match(p, TOK_RPAREN);
    }
    skip_newlines(p);
    /* Parse the attributed statement (typically a func def) */
    ast_node_t *inner = parse_statement(p);
    if (inner && is_entry && inner->type == AST_FUNC_DEF) {
      inner->int_val |= 0x20000; /* entry marker */
      /* Rename to "main" so VM entry lookup picks it up.
       * If name is already "main", no change. */
      strncpy(inner->name, "main", AST_NAME_LEN - 1);
      inner->name[AST_NAME_LEN - 1] = '\0';
    }
    return inner;
  }

  /* ── §25/§26 Contextual statement keywords (soft keywords) ────────
   * These are IDENT tokens whose meaning depends on what follows.
   * Detected before the main switch so the generic TOK_IDENT path
   * (assignment / expression) still works for non-keyword names. */
  if (t->type == TOK_IDENT) {
    const vir_token_t *t2 =
        (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
    if (t2) {
      /* §22.5/§22.6 `await pass` — cooperative yield.
       * Desugared to the `yield()` builtin call (Q_TASK_YIELD). */
      if (strcmp(t->str.buf, "await") == 0 && t2->type == TOK_IDENT &&
          strcmp(t2->str.buf, "pass") == 0) {
        advance(p); /* await */
        advance(p); /* pass */
        ast_node_t *n = ast_new(AST_BUILTIN_CALL);
        n->builtin_id = BUILTIN_YIELD;
        strncpy(n->name, "yield", AST_NAME_LEN - 1);
        n->line = t->line;
        return n;
      }
      /* §22.1 `await EXPR` — wait for task completion, result in dest. */
      if (strcmp(t->str.buf, "await") == 0 && t2->type != TOK_COLON) {
        advance(p); /* await */
        ast_node_t *n = ast_new(AST_AWAIT_EXPR);
        n->line = t->line;
        ast_node_t *e = parse_expr(p);
        if (e)
          ast_add_child(n, e);
        return n;
      }
      /* §22.7 `cancel EXPR` — cancel a task. */
      if (strcmp(t->str.buf, "cancel") == 0 && t2->type != TOK_COLON &&
          t2->type != TOK_ASSIGN) {
        advance(p); /* cancel */
        ast_node_t *n = ast_new(AST_CANCEL_STMT);
        n->line = t->line;
        ast_node_t *e = parse_expr(p);
        if (e)
          ast_add_child(n, e);
        return n;
      }
      /* §22.9 `quiet EXPR` — fire-and-forget (no await). */
      if (strcmp(t->str.buf, "quiet") == 0 && t2->type != TOK_COLON &&
          t2->type != TOK_ASSIGN) {
        advance(p); /* quiet */
        ast_node_t *n = ast_new(AST_QUIET_STMT);
        n->line = t->line;
        ast_node_t *e = parse_expr(p);
        if (e)
          ast_add_child(n, e);
        return n;
      }
      /* §4.5 `arena NAME: body end` — scoped arena block.
       * Desugar to: NAME = arena_new(4096); body; arena_free(NAME). */
      if (strcmp(t->str.buf, "arena") == 0 && t2->type == TOK_IDENT) {
        const vir_token_t *t3 =
            (p->pos + 2 < p->token_count) ? &p->tokens[p->pos + 2] : NULL;
        if (t3 && t3->type == TOK_COLON) {
          advance(p);                         /* arena */
          const vir_token_t *nm = advance(p); /* NAME */
          advance(p);                         /* : */
          ast_node_t *n = ast_new(AST_ARENA_BLOCK);
          n->line = t->line;
          strncpy(n->name, nm->str.buf, AST_NAME_LEN - 1);
          ast_node_t *body = parse_block(p);
          if (body)
            ast_add_child(n, body);
          expect(p, TOK_END, "expected 'end' to close arena block");
          match(p, TOK_DOT);
          return n;
        }
      }
      /* §26.3 `infer: body end` / §26.4 `train: body end`
       * §25.5 `isolate: body end` (sandbox block) */
      if (t2->type == TOK_COLON) {
        if (strcmp(t->str.buf, "infer") == 0 ||
            strcmp(t->str.buf, "train") == 0 ||
            strcmp(t->str.buf, "isolate") == 0) {
          ast_type_t kind = AST_INFER_BLOCK;
          if (strcmp(t->str.buf, "train") == 0)
            kind = AST_TRAIN_BLOCK;
          if (strcmp(t->str.buf, "isolate") == 0)
            kind = AST_ISOLATE_BLOCK;
          ast_node_t *n = ast_new(kind);
          n->line = t->line;
          advance(p); /* name */
          advance(p); /* ':' */
          ast_node_t *body = parse_block(p);
          if (body)
            ast_add_child(n, body);
          expect(p, TOK_END, "expected 'end' to close block");
          return n;
        }
      }
      /* §25.1 `reactive var NAME [: TYPE] = expr` */
      if (strcmp(t->str.buf, "reactive") == 0 && t2->type == TOK_VAR) {
        advance(p);
        advance(p);
        ast_node_t *d = parse_var_decl(p, AST_VAR_DECL);
        if (d) {
          if (d->type == AST_BLOCK) {
            /* Group-syntax path: parse_var_decl() wrapped the VAR_DECL
             * nodes in a synthetic AST_BLOCK. Propagate the reactive
             * marker (0x2000) to every VAR_DECL child so the IR lowering
             * pass can set is_reactive on each symbol. */
            for (uint32_t i = 0; i < d->child_count; i++) {
              if (d->children[i])
                d->children[i]->int_val |= 0x2000;
            }
          } else {
            d->int_val |= 0x2000; /* reactive marker — single-decl path */
          }
        }
        return d;
      }
      /* §Phase-8 `extern func NAME(params) [-> TYPE] ;` — FFI shim
       * declaration with no body.  We record a function with
       * body_count=0 so VM syscall intrinsics (sys_write, …)
       * can intercept it by name. */
      if (strcmp(t->str.buf, "extern") == 0 && t2->type == TOK_FUNC) {
        advance(p); /* 'extern' */
        advance(p); /* 'func' */
        const vir_token_t *nm =
            expect_name(p, "expected name after 'extern func'");
        ast_node_t *f = ast_new(AST_FUNC_DEF);
        if (nm)
          strncpy(f->name, nm->str.buf, AST_NAME_LEN - 1);
        f->line = t->line;
        f->int_val |= 0x8000; /* extern marker — body-less shim */
        /* Optional `(param: type, …)` C-style signature: we just
         * skim past everything up to the terminating ';' so we
         * don't force the AST to carry FFI types the VM ignores. */
        if (check(p, TOK_LPAREN)) {
          int depth = 1;
          advance(p);
          while (!check(p, TOK_EOF) && depth > 0) {
            if (check(p, TOK_LPAREN))
              depth++;
            else if (check(p, TOK_RPAREN))
              depth--;
            if (depth > 0)
              advance(p);
            else
              advance(p); /* consume closing ')' */
          }
        }
        /* Skip `-> TYPE` if present. */
        if (check(p, TOK_ARROW)) {
          advance(p);
          if (check(p, TOK_IDENT))
            advance(p);
        }
        match(p, TOK_SEMICOLON);
        return f;
      }
      /* §25.4 `expose func NAME ... end` (also `expose async func`) */
      if (strcmp(t->str.buf, "expose") == 0 &&
          (t2->type == TOK_FUNC || t2->type == TOK_ASYNC)) {
        advance(p); /* 'expose' */
        if (check(p, TOK_ASYNC))
          advance(p); /* skip async marker */
        if (check(p, TOK_FUNC))
          advance(p);
        ast_node_t *f = parse_func_def(p);
        if (f)
          f->int_val |= 0x4000; /* exposed marker */
        return f;
      }
      /* §25.2 `morph NAME -> UI: bindings end` */
      if (strcmp(t->str.buf, "morph") == 0 && t2->type == TOK_IDENT) {
        advance(p);                          /* 'morph' */
        const vir_token_t *ent = advance(p); /* entity name */
        ast_node_t *m = ast_new(AST_MORPH_DEF);
        m->line = t->line;
        strncpy(m->name, ent->str.buf, AST_NAME_LEN - 1);
        if (match(p, TOK_ARROW)) {
          if (check(p, TOK_IDENT)) {
            strncpy(m->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
            advance(p);
          }
        }
        if (match(p, TOK_COLON)) {
          /* Consume body until matching 'end'; store bindings as
           * AST_ASSIGN nodes (field = expr). Lowering is a no-op. */
          while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
            skip_newlines(p);
            if (check(p, TOK_END) || check(p, TOK_EOF))
              break;
            uint32_t before = p->pos;
            ast_node_t *stmt = parse_statement(p);
            if (stmt)
              ast_add_child(m, stmt);
            else if (p->pos == before)
              advance(p);
          }
        }
        expect(p, TOK_END, "expected 'end' to close morph");
        return m;
      }
      /* §25.3 `bundle NAME: TYPE = embed "path"` */
      if (strcmp(t->str.buf, "bundle") == 0 && t2->type == TOK_IDENT) {
        advance(p); /* 'bundle' */
        const vir_token_t *nm = advance(p);
        ast_node_t *b = ast_new(AST_BUNDLE_DECL);
        b->line = t->line;
        strncpy(b->name, nm->str.buf, AST_NAME_LEN - 1);
        if (match(p, TOK_COLON)) {
          /* type annotation: IDENT (u8, string, etc.) optionally
           * followed by `[]`. Consume but don't require. */
          if (check(p, TOK_IDENT)) {
            strncpy(b->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
            advance(p);
            if (match(p, TOK_LBRACKET))
              expect(p, TOK_RBRACKET, "expected ']' in bundle type");
          }
        }
        expect(p, TOK_ASSIGN, "expected '=' in bundle decl");
        /* expect literal IDENT "embed" then STRING path */
        if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "embed") == 0) {
          advance(p);
        }
        const vir_token_t *path =
            expect(p, TOK_STRING, "expected path string after 'embed'");
        if (path) {
          /* Read file bytes at parse time. Path is resolved relative to
           * CWD; for simplicity we store it as AST_LITERAL_STR child. */
          FILE *fp = fopen(path->str.buf, "rb");
          ast_node_t *lit = ast_new(AST_LITERAL_STR);
          lit->line = path->line;
          if (fp) {
            fseek(fp, 0, SEEK_END);
            long sz = ftell(fp);
            fseek(fp, 0, SEEK_SET);
            if (sz < 0)
              sz = 0;
            if (sz > (long)(sizeof(lit->name) - 1))
              sz = sizeof(lit->name) - 1;
            size_t rd = fread(lit->name, 1, (size_t)sz, fp);
            lit->name[rd] = '\0';
            lit->int_val = (int64_t)rd;
            fclose(fp);
          } else {
            /* Missing file → empty bundle (diagnostic via line only). */
            lit->name[0] = '\0';
            lit->int_val = 0;
          }
          ast_add_child(b, lit);
        }
        return b;
      }
      /* §23.1 `port NAME: TYPE [(cap: N)]` declaration */
      if (strcmp(t->str.buf, "port") == 0 && t2->type == TOK_IDENT) {
        advance(p); /* 'port' */
        const vir_token_t *nm = advance(p);
        ast_node_t *pd = ast_new(AST_PORT_DECL);
        pd->line = t->line;
        strncpy(pd->name, nm->str.buf, AST_NAME_LEN - 1);
        pd->int_val = 16; /* default capacity */
        if (match(p, TOK_COLON)) {
          if (check(p, TOK_IDENT)) {
            strncpy(pd->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
            advance(p);
          }
        }
        /* §23.5 optional `(cap: N)` */
        if (match(p, TOK_LPAREN)) {
          while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF)) {
            const vir_token_t *k =
                expect_name(p, "expected option in port(...)");
            if (!k)
              break;
            if (!expect(p, TOK_COLON, "expected ':' after port option"))
              break;
            ast_node_t *v = parse_expr(p);
            if (v && v->type == AST_LITERAL_INT &&
                strcmp(k->str.buf, "cap") == 0) {
              pd->int_val = v->int_val;
            }
            if (v)
              ast_free(v);
            if (!match(p, TOK_COMMA) && !match(p, TOK_SEMICOLON))
              break;
          }
          expect(p, TOK_RPAREN, "expected ')' after port options");
        }
        return pd;
      }
      /* §23.2 `send NAME <- expr` */
      if (strcmp(t->str.buf, "send") == 0 && t2->type == TOK_IDENT) {
        /* Only bind as send if the token AFTER port name is '<-'. */
        const vir_token_t *t3 =
            (p->pos + 2 < p->token_count) ? &p->tokens[p->pos + 2] : NULL;
        if (t3 && t3->type == TOK_LARROW) {
          advance(p);                         /* 'send' */
          const vir_token_t *pn = advance(p); /* port name */
          advance(p);                         /* '<-' */
          ast_node_t *s = ast_new(AST_SEND_STMT);
          s->line = t->line;
          strncpy(s->name, pn->str.buf, AST_NAME_LEN - 1);
          ast_node_t *e = parse_expr(p);
          if (e)
            ast_add_child(s, e);
          return s;
        }
      }
      /* §23.4 `select: case recv X from P: body ... end` */
      if (strcmp(t->str.buf, "select") == 0 && t2->type == TOK_COLON) {
        advance(p);
        advance(p); /* 'select' ':' */
        ast_node_t *sb = ast_new(AST_SELECT_BLOCK);
        sb->line = t->line;
        while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
          skip_newlines(p);
          if (!is_name_token(peek(p)->type))
            break;
          /* case recv X from P: body */
          if (check(p, TOK_CASE))
            advance(p);
          /* expect IDENT "recv" */
          if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "recv") == 0) {
            advance(p);
          }
          const vir_token_t *bind =
              expect_name(p, "expected bind var in select case");
          if (!bind)
            break;
          /* 'from' keyword (tokenised as TOK_FROM by lexer) */
          if (check(p, TOK_FROM) ||
              (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "from") == 0)) {
            advance(p);
          }
          const vir_token_t *pn =
              expect_name(p, "expected port name in select case");
          if (!pn)
            break;
          expect(p, TOK_COLON, "expected ':' after select case header");
          ast_node_t *caseblk = ast_new(AST_BLOCK);
          caseblk->line = bind->line;
          strncpy(caseblk->name, bind->str.buf, AST_NAME_LEN - 1);
          strncpy(caseblk->name2, pn->str.buf, AST_NAME_LEN - 1);
          /* Parse statements until 'case' or 'end' */
          while (!check(p, TOK_END) && !check(p, TOK_EOF) &&
                 !check(p, TOK_CASE)) {
            skip_newlines(p);
            if (check(p, TOK_END) || check(p, TOK_EOF) || check(p, TOK_CASE))
              break;
            /* Don't misinterpret IDENT "recv" at start as new case */
            if (check(p, TOK_IDENT) && strcmp(peek(p)->str.buf, "recv") == 0) {
              const vir_token_t *t3 =
                  (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
              if (t3 && t3->type == TOK_IDENT) {
                const vir_token_t *t4 = (p->pos + 2 < p->token_count)
                                            ? &p->tokens[p->pos + 2]
                                            : NULL;
                if (t4 && t4->type == TOK_IDENT &&
                    strcmp(t4->str.buf, "from") == 0) {
                  break; /* implicit new case */
                }
              }
            }
            uint32_t before = p->pos;
            ast_node_t *st = parse_statement(p);
            if (st)
              ast_add_child(caseblk, st);
            else if (p->pos == before)
              advance(p);
          }
          ast_add_child(sb, caseblk);
        }
        expect(p, TOK_END, "expected 'end' to close select");
        return sb;
      }
      /* §17.2 `precomp func ...` / `comptime func ...` */
      if ((strcmp(t->str.buf, "precomp") == 0 ||
           strcmp(t->str.buf, "comptime") == 0) &&
          t2->type == TOK_FUNC) {
        advance(p); /* precomp/comptime */
        advance(p); /* func */
        ast_node_t *f = parse_func_def(p);
        if (f)
          f->int_val |= 0x40000; /* precomp marker */
        return f;
      }
      /* §24.3 `deck NAME: TYPE[SIZE]` — shared buffer, represented
       * in the VM as a zero-filled array of SIZE elements. */
      if (strcmp(t->str.buf, "deck") == 0 && t2->type == TOK_IDENT) {
        advance(p); /* 'deck' */
        const vir_token_t *nm = advance(p);
        expect(p, TOK_COLON, "expected ':' after deck name");
        /* type name: IDENT (may include `<...>` for flux<T,N>) */
        if (check(p, TOK_IDENT))
          advance(p);
        if (check(p, TOK_LT)) {
          /* skip generic args until '>' */
          int depth = 1;
          advance(p);
          while (depth > 0 && !check(p, TOK_EOF)) {
            if (check(p, TOK_LT))
              depth++;
            else if (check(p, TOK_GT))
              depth--;
            advance(p);
          }
        }
        int64_t size = 0;
        if (match(p, TOK_LBRACKET)) {
          ast_node_t *s = parse_expr(p);
          if (s && s->type == AST_LITERAL_INT)
            size = s->int_val;
          if (s)
            ast_free(s);
          expect(p, TOK_RBRACKET, "expected ']' after deck size");
        }
        /* Desugar to: var NAME = flux_splat(0, SIZE) */
        ast_node_t *decl = ast_new(AST_VAR_DECL);
        decl->line = t->line;
        strncpy(decl->name, nm->str.buf, AST_NAME_LEN - 1);
        ast_node_t *call = ast_new(AST_BUILTIN_CALL);
        call->builtin_id = BUILTIN_FLUX_SPLAT;
        call->line = t->line;
        ast_node_t *z = ast_new(AST_LITERAL_INT);
        z->int_val = 0;
        ast_node_t *sz = ast_new(AST_LITERAL_INT);
        sz->int_val = size > 0 ? size : 1;
        ast_add_child(call, z);
        ast_add_child(call, sz);
        ast_add_child(decl, call);
        return decl;
      }
    }
  }

  switch (t->type) {
  case TOK_ASYNC:
    /* §22 async func — mark function as async for IR lowering */
    advance(p);
    if (!expect(p, TOK_FUNC, "expected 'func' after 'async'"))
      return NULL;
    {
      ast_node_t *fn = parse_func_def(p);
      if (fn)
        fn->is_async = 1;
      return fn;
    }

  case TOK_FUNC:
    advance(p);
    return parse_func_def(p);

  case TOK_VAR:
    advance(p);
    return parse_var_decl(p, AST_VAR_DECL);

  case TOK_CONST:
    advance(p);
    return parse_var_decl(p, AST_CONST_DECL);

  case TOK_ATOMIC_KW: {
    /* atomic var x[: type] = expr — §13.7 retry-spanning var */
    advance(p);
    if (!expect(p, TOK_VAR, "expected 'var' after 'atomic'"))
      return NULL;
    ast_node_t *d = parse_var_decl(p, AST_VAR_DECL);
    if (d) {
      /* Mark via int_val bit to distinguish from ordinary var in later passes.
       * Re-used by lowering for W302 exemption. */
      d->int_val |= 0x1000;
    }
    return d;
  }

  case TOK_IF:
    advance(p);
    return parse_if_stmt(p);

  case TOK_LOOP:
    advance(p);
    return parse_loop_stmt(p);

  case TOK_WHILE:
    advance(p);
    return parse_while_stmt(p);

  case TOK_WHEN:
    advance(p);
    return parse_when_loop_stmt(p);

  case TOK_FOR:
    advance(p);
    return parse_for_range_stmt(p);

  case TOK_ENUM:
    advance(p);
    return parse_enum_def(p);

  case TOK_CASE:
    advance(p);
    return parse_case_stmt(p);

  case TOK_DEL: {
    /* §20: del IDENT[key] */
    const vir_token_t *dtok = advance(p);
    const vir_token_t *nm =
        expect_name(p, "expected dict name after 'del'");
    if (!nm)
      return NULL;
    if (!expect(p, TOK_LBRACKET, "expected '[' after dict name in 'del'"))
      return NULL;
    ast_node_t *key = parse_expr(p);
    expect(p, TOK_RBRACKET, "expected ']' after key in 'del'");
    ast_node_t *d = ast_new(AST_DEL_STMT);
    strncpy(d->name, nm->str.buf, AST_NAME_LEN - 1);
    d->line = dtok->line;
    if (key)
      ast_add_child(d, key);
    return d;
  }

  case TOK_RECORD:
  case TOK_ENTITY:
    advance(p);
    return parse_record_def(p);

  case TOK_PACKED: {
    advance(p);
    if (check(p, TOK_ENTITY) || check(p, TOK_RECORD)) {
      advance(p);
      ast_node_t *ed = parse_record_def(p);
      if (ed)
        ed->type = AST_PACKED_DEF;
      return ed;
    }
    return NULL;
  }

  case TOK_REGISTER:
    advance(p);
    return parse_register_def(p);

  case TOK_MOLD:
    advance(p);
    return parse_mold_def(p);

  case TOK_RETURN:
  case TOK_OUT:
    advance(p);
    return parse_return_stmt(p);

  case TOK_PRINT:
    advance(p);
    return parse_print_stmt(p);

  case TOK_LOCK: {
    /* §24.4: `lock IDENT = value` atomic store,
     *        `lock IDENT op= value` atomic RMW (op ∈ + - * /),
     *        `lock IDENT` alone = atomic load expression stmt */
    advance(p);
    const vir_token_t *id =
        expect_name(p, "expected variable after 'lock'");
    if (!id)
      return NULL;
    if (check(p, TOK_ASSIGN)) {
      advance(p); /* consume '=' */
      ast_node_t *st = ast_new(AST_ATOMIC_STORE);
      strncpy(st->name, id->str.buf, AST_NAME_LEN - 1);
      st->line = t->line;
      ast_node_t *val = parse_expr(p);
      if (val)
        ast_add_child(st, val);
      return st;
    }
    if (check(p, TOK_PLUS_ASSIGN) || check(p, TOK_MINUS_ASSIGN) ||
        check(p, TOK_STAR_ASSIGN) || check(p, TOK_SLASH_ASSIGN)) {
      const vir_token_t *op_tok = advance(p);
      ast_op_t op;
      switch (op_tok->type) {
      case TOK_PLUS_ASSIGN:
        op = OP_ADD;
        break;
      case TOK_MINUS_ASSIGN:
        op = OP_SUB;
        break;
      case TOK_STAR_ASSIGN:
        op = OP_MUL;
        break;
      default:
        op = OP_DIV;
        break; /* SLASH_ASSIGN */
      }
      ast_node_t *rhs = parse_expr(p);
      if (!rhs)
        return NULL;
      ast_node_t *idn = ast_new(AST_IDENTIFIER);
    if (t && t->str.buf && strcmp(t->str.buf, "prog") == 0) printf("\n*** FOUND prog IDENT AT LINE %u\n", t->line);
      strncpy(idn->name, id->str.buf, AST_NAME_LEN - 1);
      idn->line = id->line;
      ast_node_t *bin = ast_new(AST_BINOP);
      bin->op = op;
      bin->line = op_tok->line;
      ast_add_child(bin, idn);
      ast_add_child(bin, rhs);
      ast_node_t *st = ast_new(AST_ATOMIC_STORE);
      strncpy(st->name, id->str.buf, AST_NAME_LEN - 1);
      st->line = t->line;
      ast_add_child(st, bin);
      return st;
    }
    /* Bare `lock x` statement → atomic load (no-op as stmt; kept for
     * consistency with expression-form `lock x`) */
    ast_node_t *idn = ast_new(AST_IDENTIFIER);
    if (t && t->str.buf && strcmp(t->str.buf, "prog") == 0) printf("\n*** FOUND prog IDENT AT LINE %u\n", t->line);
    strncpy(idn->name, id->str.buf, AST_NAME_LEN - 1);
    idn->line = id->line;
    ast_node_t *al = ast_new(AST_ATOMIC_LOAD);
    al->line = t->line;
    ast_add_child(al, idn);
    return al;
  }

  case TOK_BREAK: {
    advance(p);
    ast_node_t *n = ast_new(AST_BREAK);
    n->line = t->line;
    match(p, TOK_SEMICOLON); /* optional ';' */
    return n;
  }
  case TOK_CONTINUE:
  case TOK_SKIP: {
    advance(p);
    ast_node_t *n = ast_new(AST_CONTINUE);
    n->line = t->line;
    match(p, TOK_SEMICOLON); /* optional ';' */
    return n;
  }

  case TOK_THROW: {
    /* throw <expr> */
    advance(p);
    ast_node_t *n = ast_new(AST_THROW);
    n->line = t->line;
    ast_node_t *code = parse_expr(p);
    if (code)
      ast_add_child(n, code);
    match(p, TOK_SEMICOLON);
    return n;
  }
  case TOK_RESUME: {
    /* resume retry | resume revert */
    advance(p);
    ast_node_t *n = ast_new(AST_RESUME);
    n->line = t->line;
    if (check(p, TOK_RETRY)) {
      advance(p);
      n->int_val = 0;
    } else if (check(p, TOK_REVERT)) {
      advance(p);
      n->int_val = 1;
    } else {
      snprintf(p->error, sizeof(p->error),
               "line %u: expected 'retry' or 'revert' after 'resume'", t->line);
      return NULL;
    }
    match(p, TOK_SEMICOLON);
    return n;
  }
  case TOK_EMIT: {
    /* emit LEVEL(arg, ...) — LEVEL is an identifier (LOG_INFO etc.) */
    advance(p);
    const vir_token_t *lvl =
        expect_name(p, "expected log level after 'emit'");
    if (!lvl)
      return NULL;
    ast_node_t *n = ast_new(AST_EMIT);
    n->line = t->line;
    strncpy(n->name, lvl->str.buf, AST_NAME_LEN - 1);
    if (match(p, TOK_LPAREN)) {
      if (!check(p, TOK_RPAREN)) {
        do {
          ast_node_t *arg = parse_expr(p);
          if (arg)
            ast_add_child(n, arg);
        } while (match(p, TOK_COMMA));
      }
      expect(p, TOK_RPAREN, "expected ')' after emit arguments");
    }
    match(p, TOK_SEMICOLON);
    return n;
  }
  case TOK_TRY: {
    /* try[(timeout: N; isolate: [a,b])]:  body  revert: handler  end */
    advance(p);
    ast_node_t *n = ast_new(AST_TRY_BLOCK);
    n->line = t->line;
    n->int_val = 0; /* opt flags */
    if (match(p, TOK_LPAREN)) {
      while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF)) {
        const vir_token_t *key = expect_name(p, "expected option name");
        if (!key)
          break;
        if (!expect(p, TOK_COLON, "expected ':' in try option"))
          break;
        if (strcmp(key->str.buf, "timeout") == 0) {
          ast_node_t *texpr = parse_expr(p);
          if (texpr) {
            if (texpr->type == AST_LITERAL_INT)
              n->int_val |= (int64_t)(texpr->int_val & 0xFFFF) << 16;
            ast_free(texpr);
          }
          n->int_val |= 1; /* bit 0 = has_timeout */
        } else if (strcmp(key->str.buf, "isolate") == 0) {
          /* [a, b, c] */
          if (!expect(p, TOK_LBRACKET, "expected '[' after 'isolate:'"))
            break;
          size_t off = 0;
          while (!check(p, TOK_RBRACKET) && !check(p, TOK_EOF)) {
            const vir_token_t *v = expect_name(p, "expected var name");
            if (!v)
              break;
            size_t ln = strlen(v->str.buf);
            if (off + ln + 2 < AST_NAME_LEN) {
              if (off > 0)
                n->name[off++] = ',';
              memcpy(n->name + off, v->str.buf, ln);
              off += ln;
              n->name[off] = '\0';
            }
            if (!match(p, TOK_COMMA))
              break;
          }
          expect(p, TOK_RBRACKET, "expected ']' to close isolate list");
          n->int_val |= 2; /* bit 1 = has_isolate */
        } else {
          /* unknown option — skip value */
          ast_node_t *skip_val = parse_expr(p);
          if (skip_val)
            ast_free(skip_val);
        }
        if (!match(p, TOK_SEMICOLON) && !match(p, TOK_COMMA))
          break;
      }
      expect(p, TOK_RPAREN, "expected ')' after try options");
    }
    expect_block_open(p, "try");
    ast_node_t *body = parse_block(p);
    ast_add_child(n, body);
    /* optional revert block */
    if (check(p, TOK_REVERT)) {
      advance(p);
      expect_block_open(p, "revert");
      ast_node_t *rb = ast_new(AST_REVERT_BLOCK);
      rb->line = peek(p)->line;
      ast_node_t *rbody = parse_block(p);
      ast_add_child(rb, rbody);
      ast_add_child(n, rb);
    }
    expect(p, TOK_END, "expected 'end' to close try block");
    return n;
  }

  case TOK_IMPORT: {
    /* import MODULE
     *   or   import MODULE as ALIAS
     *   or   import SYM1, SYM2, ... from MODULE ;     (§Phase-8)
     */
    advance(p);
    uint32_t line = peek(p)->line;
    char mod_name[AST_NAME_LEN];
    if (!parse_module_path(p, mod_name)) {
      parse_error(p, "expected module name after 'import'");
      return NULL;
    }
    ast_node_t *n = ast_new(AST_IMPORT);
    n->line = line;
    /* Detect `import SYM1 , … from MODULE` by peeking at next token. */
    if (check(p, TOK_COMMA) || check(p, TOK_FROM)) {
      /* Treat the first IDENT as a symbol name, collect more. */
      ast_node_t *s0 = ast_new(AST_IDENTIFIER);
      strncpy(s0->name, mod_name, AST_NAME_LEN - 1);
      s0->line = line;
      ast_add_child(n, s0);
      while (match(p, TOK_COMMA)) {
        skip_newlines(p);
        const vir_token_t *sym = expect_name(p, "expected symbol name");
        if (!sym)
          break;
        ast_node_t *s = ast_new(AST_IDENTIFIER);
        strncpy(s->name, sym->str.buf, AST_NAME_LEN - 1);
        s->line = sym->line;
        ast_add_child(n, s);
      }
      skip_newlines(p);
      if (match(p, TOK_FROM)) {
        char from_mod[AST_NAME_LEN];
        if (parse_module_path(p, from_mod))
          strncpy(n->name, from_mod, AST_NAME_LEN - 1);
        else
          parse_error(p, "expected module name after 'from'");
      }
      match(p, TOK_SEMICOLON);
      return n;
    }
    strncpy(n->name, mod_name, AST_NAME_LEN - 1);
    if (match(p, TOK_AS)) {
      const vir_token_t *alias =
          expect_name(p, "expected alias after 'as'");
      if (alias)
        strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
    }
    match(p, TOK_SEMICOLON);
    return n;
  }
  case TOK_FROM: {
    /* from MODULE import SYM1, SYM2, ... */
    advance(p);
    const vir_token_t *mod =
        expect_name(p, "expected module name after from");
    if (!mod)
      return NULL;
    if (!expect(p, TOK_IMPORT, "expected 'import' after module name"))
      return NULL;
    ast_node_t *n = ast_new(AST_IMPORT);
    strncpy(n->name, mod->str.buf, AST_NAME_LEN - 1);
    n->line = t->line;
    /* Parse imported symbols as children (AST_IDENTIFIER nodes) */
    do {
      skip_newlines(p);
      const vir_token_t *sym = expect_name(p, "expected symbol name");
      if (!sym)
        break;
      ast_node_t *s = ast_new(AST_IDENTIFIER);
      strncpy(s->name, sym->str.buf, AST_NAME_LEN - 1);
      s->line = sym->line;
      ast_add_child(n, s);
    } while (match(p, TOK_COMMA));
    match(p, TOK_SEMICOLON);
    return n;
  }
  case TOK_MODULE: {
    /* module NAME  (NAME may be dotted:  vir.rt.io  or  vir::rt::io) */
    advance(p);
    const vir_token_t *mod = expect_name(p, "expected module name");
    if (!mod)
      return NULL;
    ast_node_t *n = ast_new(AST_MODULE);
    size_t pos = 0;
    size_t n_seg = strlen(mod->str.buf);
    if (n_seg < AST_NAME_LEN) {
      memcpy(n->name, mod->str.buf, n_seg);
      pos = n_seg;
    }
    /* Accept `.NAME` or `::NAME` continuations. */
    while (1) {
      if (check(p, TOK_DOT)) {
        advance(p);
        if (pos + 1 < AST_NAME_LEN)
          n->name[pos++] = '.';
      } else if (check(p, TOK_COLON)) {
        const vir_token_t *nxt =
            (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
        if (!nxt || nxt->type != TOK_COLON)
          break;
        advance(p);
        advance(p);
        if (pos + 2 < AST_NAME_LEN) {
          n->name[pos++] = ':';
          n->name[pos++] = ':';
        }
      } else {
        break;
      }
      if (!check(p, TOK_IDENT))
        break;
      const vir_token_t *seg = advance(p);
      size_t ns = strlen(seg->str.buf);
      if (pos + ns < AST_NAME_LEN) {
        memcpy(n->name + pos, seg->str.buf, ns);
        pos += ns;
      }
    }
    n->name[pos] = '\0';
    match(p, TOK_SEMICOLON);
    n->line = t->line;
    return n;
  }
  case TOK_EXPORT: {
    advance(p);
    ast_node_t *block = ast_new(AST_BLOCK);
    while (1) {
      const vir_token_t *fn = expect_name(p, "expected function name after export");
      if (!fn) break;
      ast_node_t *n = ast_new(AST_EXPORT);
      strncpy(n->name, fn->str.buf, AST_NAME_LEN - 1);
      n->line = t->line;
      ast_add_child(block, n);
      if (!match(p, TOK_COMMA)) break;
    }
    match(p, TOK_SEMICOLON);
    return block;
  }
  case TOK_INCLUDE: {
    /* include "filename"  OR  include path::to::module; (§3.2) */
    advance(p);
    ast_node_t *n = ast_new(AST_INCLUDE);
    n->line = t->line;
    if (check(p, TOK_STRING)) {
      const vir_token_t *file = advance(p);
      strncpy(n->name, file->str.buf, AST_NAME_LEN - 1);
    } else if (is_name_token(peek(p)->type)) {
      /* dotted / namespaced path: A::B::C  or  a.b.c */
      size_t pos = 0;
      while (is_name_token(peek(p)->type)) {
        const vir_token_t *seg = advance(p);
        size_t n_seg = strlen(seg->str.buf);
        if (pos + n_seg + 2 >= AST_NAME_LEN)
          break;
        memcpy(n->name + pos, seg->str.buf, n_seg);
        pos += n_seg;
        /* Accept `::` (two COLONs) or `.` as separator. */
        if (check(p, TOK_COLON)) {
          const vir_token_t *nxt =
              (p->pos + 1 < p->token_count) ? &p->tokens[p->pos + 1] : NULL;
          if (nxt && nxt->type == TOK_COLON) {
            advance(p);
            advance(p);
            if (pos + 2 < AST_NAME_LEN) {
              n->name[pos++] = ':';
              n->name[pos++] = ':';
            }
            continue;
          }
        }
        if (check(p, TOK_DOT)) {
          advance(p);
          if (pos + 1 < AST_NAME_LEN)
            n->name[pos++] = '.';
          continue;
        }
        break;
      }
      n->name[pos] = '\0';
      match(p, TOK_SEMICOLON);
    } else {
      expect(p, TOK_STRING, "expected filename or path after include");
      return n;
    }
    /* `as alias` (already supported elsewhere) */
    if (check(p, TOK_AS)) {
      advance(p);
      const vir_token_t *alias =
          expect_name(p, "expected alias name after 'as'");
      if (alias) {
        strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
      }
    }
    match(p, TOK_SEMICOLON);
    return n;
  }

  case TOK_TYPE_KW: {
    /* type <name> ; */
    advance(p);
    const vir_token_t *name =
        expect_name(p, "expected type name after 'type'");
    if (!name)
      return NULL;
    ast_node_t *n = ast_new(AST_TYPE_DECL);
    strncpy(n->name, name->str.buf, AST_NAME_LEN - 1);
    n->line = t->line;
    match(p, TOK_SEMICOLON);
    return n;
  }

  case TOK_CHECK_CPU: {
    advance(p);
    ast_node_t *n = ast_new(AST_CHECK_CPU);
    n->line = t->line;
    return n;
  }
  case TOK_PATCH: {
    advance(p);
    ast_node_t *n = ast_new(AST_PATCH_POINT);
    n->line = t->line;
    return n;
  }

  case TOK_THIS:
  case TOK_IDENT: {
    /* Could be: assignment, index assign, field assign, or expression */
    const vir_token_t *t = advance(p);
    if (check(p, TOK_ASSIGN)) {
      advance(p); /* consume '=' */
      ast_node_t *assign = ast_new(AST_ASSIGN);
      strncpy(assign->name, t->str.buf, AST_NAME_LEN - 1);
      assign->line = t->line;
      ast_node_t *val = parse_expr(p);
      if (val)
        ast_add_child(assign, val);
      return assign;
    }
    /* Compound assignment: x op= value  →  x = x op value */
    if (check(p, TOK_PLUS_ASSIGN) || check(p, TOK_MINUS_ASSIGN) ||
        check(p, TOK_STAR_ASSIGN) || check(p, TOK_SLASH_ASSIGN)) {
      const vir_token_t *op_tok = advance(p);
      ast_op_t op;
      switch (op_tok->type) {
      case TOK_PLUS_ASSIGN:
        op = OP_ADD;
        break;
      case TOK_MINUS_ASSIGN:
        op = OP_SUB;
        break;
      case TOK_STAR_ASSIGN:
        op = OP_MUL;
        break;
      default:
        op = OP_DIV;
        break; /* SLASH_ASSIGN */
      }
      ast_node_t *rhs = parse_expr(p);
      if (!rhs)
        return NULL;
      ast_node_t *id = ast_new(AST_IDENTIFIER);
      strncpy(id->name, t->str.buf, AST_NAME_LEN - 1);
      id->line = t->line;
      ast_node_t *bin = ast_new(AST_BINOP);
      bin->op = op;
      bin->line = op_tok->line;
      ast_add_child(bin, id);
      ast_add_child(bin, rhs);
      ast_node_t *assign = ast_new(AST_ASSIGN);
      strncpy(assign->name, t->str.buf, AST_NAME_LEN - 1);
      assign->line = t->line;
      ast_add_child(assign, bin);
      return assign;
    }
    /* §24.4: x!! = value (atomic store postfix form) and x!! op= value (RMW) */
    if (check(p, TOK_ATOMIC_BANG)) {
      advance(p); /* consume '!!' */
      if (check(p, TOK_ASSIGN)) {
        advance(p); /* consume '=' */
        ast_node_t *st = ast_new(AST_ATOMIC_STORE);
        strncpy(st->name, t->str.buf, AST_NAME_LEN - 1);
        st->line = t->line;
        ast_node_t *val = parse_expr(p);
        if (val)
          ast_add_child(st, val);
        return st;
      }
      /* §24.4 RMW: x!! op= value  →  AST_ATOMIC_STORE(x, x op value) */
      if (check(p, TOK_PLUS_ASSIGN) || check(p, TOK_MINUS_ASSIGN) ||
          check(p, TOK_STAR_ASSIGN) || check(p, TOK_SLASH_ASSIGN)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op;
        switch (op_tok->type) {
        case TOK_PLUS_ASSIGN:
          op = OP_ADD;
          break;
        case TOK_MINUS_ASSIGN:
          op = OP_SUB;
          break;
        case TOK_STAR_ASSIGN:
          op = OP_MUL;
          break;
        default:
          op = OP_DIV;
          break;
        }
        ast_node_t *rhs = parse_expr(p);
        if (!rhs)
          return NULL;
        ast_node_t *id = ast_new(AST_IDENTIFIER);
        strncpy(id->name, t->str.buf, AST_NAME_LEN - 1);
        id->line = t->line;
        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = op;
        bin->line = op_tok->line;
        ast_add_child(bin, id);
        ast_add_child(bin, rhs);
        ast_node_t *st = ast_new(AST_ATOMIC_STORE);
        strncpy(st->name, t->str.buf, AST_NAME_LEN - 1);
        st->line = t->line;
        ast_add_child(st, bin);
        return st;
      }
      /* Bare `x!!` as expression statement → atomic load */
      ast_node_t *id = ast_new(AST_IDENTIFIER);
      strncpy(id->name, t->str.buf, AST_NAME_LEN - 1);
      id->line = t->line;
      ast_node_t *al = ast_new(AST_ATOMIC_LOAD);
      al->line = t->line;
      ast_add_child(al, id);
      return al;
    }
    /* §24.2 Swizzle write-mask: IDENT ~ CHANS = rhs */
    if (check(p, TOK_BIT_NOT)) {
      const vir_token_t *tilde = advance(p);
      const vir_token_t *chans =
          expect_name(p, "expected channel name after '~'");
      if (!chans)
        return NULL;
      if (check(p, TOK_ASSIGN)) {
        advance(p);
        ast_node_t *rhs = parse_expr(p);
        if (!rhs)
          return NULL;
        ast_node_t *sw = ast_new(AST_SWIZZLE_STORE);
        strncpy(sw->name, t->str.buf, AST_NAME_LEN - 1);
        strncpy(sw->name2, chans->str.buf, AST_NAME_LEN - 1);
        sw->line = tilde->line;
        ast_add_child(sw, rhs);
        return sw;
      }
      /* Not an assignment — fall through as read-swizzle expression stmt. */
      ast_node_t *id = ast_new(AST_IDENTIFIER);
      strncpy(id->name, t->str.buf, AST_NAME_LEN - 1);
      id->line = t->line;
      ast_node_t *sw = ast_new(AST_SWIZZLE);
      strncpy(sw->name, chans->str.buf, AST_NAME_LEN - 1);
      sw->line = tilde->line;
      ast_add_child(sw, id);
      return sw;
    }
    if (check(p, TOK_DOT)) {
      /* Field assign: IDENT '.' FIELD_NAME '=' expr */
      advance(p); /* consume '.' */
      const vir_token_t *field = expect_name(p, "expected field name");
      if (field && check(p, TOK_ASSIGN)) {
        advance(p); /* consume '=' */
        ast_node_t *val = parse_expr(p);
        ast_node_t *fa = ast_new(AST_FIELD_ASSIGN);
        strncpy(fa->name, t->str.buf, AST_NAME_LEN - 1);
        strncpy(fa->name2, field->str.buf, AST_NAME_LEN - 1);
        fa->line = t->line;
        if (val)
          ast_add_child(fa, val);
        return fa;
      }
      /* Not field assign - back up to before '.' and parse as expr */
      p->pos -= 3; /* back before 'c', '.', and 'inc' */
      ast_node_t *expr = parse_expr(p);
      return expr;
    }
    if (check(p, TOK_LBRACKET)) {
      /* Index assign: IDENT '[' expr ']' '=' expr */
      advance(p);
      ast_node_t *idx = parse_expr(p);
      expect(p, TOK_RBRACKET, "expected ']'");
      if (check(p, TOK_ASSIGN)) {
        advance(p);
        ast_node_t *val = parse_expr(p);
        ast_node_t *ia = ast_new(AST_INDEX_ASSIGN);
        strncpy(ia->name, t->str.buf, AST_NAME_LEN - 1);
        ia->line = t->line;
        if (idx)
          ast_add_child(ia, idx);
        if (val)
          ast_add_child(ia, val);
        return ia;
      }
      /* If not followed by '=', it's an index access expression statement */
      ast_node_t *acc = ast_new(AST_INDEX_ACCESS);
      strncpy(acc->name, t->str.buf, AST_NAME_LEN - 1);
      acc->line = t->line;
      if (idx)
        ast_add_child(acc, idx);
      return acc;
    }
    /* Back up and parse as expression */
    p->pos--;
    ast_node_t *expr = parse_expr(p);
    match(p, TOK_SEMICOLON);
    return expr;
  }

  case TOK_EOF:
  case TOK_END:
  case TOK_ELSE:
  case TOK_ELIF:
  case TOK_EIF:
    return NULL;

  default:
    /* Try as expression statement */
    {
      ast_node_t *expr = parse_expr(p);
      match(p, TOK_SEMICOLON);
      return expr;
    }
  }
}

/* ═══════════════════════════════════════════════════════
 * Top-level
 * ═══════════════════════════════════════════════════════ */

void parser_init(vir_parser_t *p, const vir_token_t *tokens, uint32_t count, uint32_t file_id) {
  memset(p, 0, sizeof(*p));
  p->tokens = tokens;
  p->token_count = count;
  p->file_id = file_id;
}

ast_node_t *parser_parse_program(vir_parser_t *p) {
  ast_node_t *prog = ast_new(AST_PROGRAM);

  skip_newlines(p);
  int count = 0;
  while (1) {
    uint32_t start_pos = p->pos;
    if (++count > 1000000) {
      printf("Hanging at token %d: %d\n", p->pos, peek(p)->type);
      exit(1);
    }
    skip_newlines(p);
    if (check(p, TOK_EOF))
      break;
    ast_node_t *stmt = parse_statement(p);
    if (stmt) {
      ast_add_child(prog, stmt);
    }
    
    if (p->error[0] != '\0') {
      /* Recover from error */
      parser_sync(p);
      if (check(p, TOK_SEMICOLON) || check(p, TOK_NEWLINE)) {
        advance(p);
      }
    } else {
      uint32_t before = p->pos;
      while (check(p, TOK_SEMICOLON))
        advance(p);
      skip_newlines(p);
      if (p->pos == before && p->pos == start_pos) {
          parse_error(p, "unexpected token at top level");
          parser_sync(p);
          if (p->pos == start_pos) p->pos++;
      }
    }
  }

  return prog;
}
