/*
 * parser.c – Vir Recursive-Descent Parser (v2-compatible)
 * ========================================================
 * Produces ast_node_t trees from a token stream (vir_token_t[]).
 *
 * Supports both v1.2 and v2 syntax:
 *   - const NAME: value; / const NAME = value;
 *   - var NAME: TYPE = value; / var NAME = expr;
 *   - var (x, y) = expr;  (tuple destructuring)
 *   - extern func name(param: Type, ...) -> RetType;
 *   - import SYM1, SYM2, ... from MODULE;
 *   - func name<T>(param: Type, ...) -> RetType: body end
 *   - entity Name<T>: fields end
 *   - enum Name: Variant(payload); ... end
 *   - case EXPR; case PAT body; ... end
 *   - Enum::Variant (namespace access)
 *   - expr >> Type (cast)
 *   - if-expressions
 *   - Optional block opener for if
 */

#include "parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Internal Helpers
 * ═══════════════════════════════════════════════════════ */

static void parse_error(vir_parser_t *p, const char *msg)
{
    if (p->error[0] == '\0') {  /* keep first error */
        const vir_token_t *t = &p->tokens[p->pos < p->token_count ? p->pos : p->token_count - 1];
        snprintf(p->error, sizeof(p->error),
                 "line %u: %s (got %s)", t->line, msg, lexer_token_name(t->type));
        p->error_line = t->line;
    }
}

static const vir_token_t *peek(const vir_parser_t *p)
{
    uint32_t idx = p->pos < p->token_count ? p->pos : p->token_count - 1;
    return &p->tokens[idx];
}

static const vir_token_t *peek_at(const vir_parser_t *p, uint32_t offset)
{
    uint32_t idx = p->pos + offset;
    if (idx >= p->token_count) idx = p->token_count - 1;
    return &p->tokens[idx];
}

static const vir_token_t *advance(vir_parser_t *p)
{
    const vir_token_t *t = peek(p);
    if (p->pos < p->token_count) p->pos++;
    return t;
}

static int check(const vir_parser_t *p, vir_tok_t type)
{
    return peek(p)->type == type;
}

static int match(vir_parser_t *p, vir_tok_t type)
{
    if (check(p, type)) { advance(p); return 1; }
    return 0;
}

static const vir_token_t *expect(vir_parser_t *p, vir_tok_t type, const char *msg)
{
    if (check(p, type)) return advance(p);
    parse_error(p, msg);
    return NULL;
}

/* Skip newlines (used between statements) */
static void skip_newlines(vir_parser_t *p)
{
    while (check(p, TOK_NEWLINE)) advance(p);
}

/* Skip newlines and semicolons */
static void skip_terminators(vir_parser_t *p)
{
    while (check(p, TOK_NEWLINE) || check(p, TOK_SEMICOLON)) advance(p);
}

/* Check if token could start a statement */
static int is_stmt_start(vir_tok_t t)
{
    return t == TOK_VAR || t == TOK_CONST || t == TOK_IF ||
           t == TOK_LOOP || t == TOK_WHILE || t == TOK_WHEN ||
           t == TOK_FOR ||
           t == TOK_RETURN || t == TOK_OUT || t == TOK_PRINT || t == TOK_INPUT ||
           t == TOK_IDENT || t == TOK_INT || t == TOK_FLOAT ||
           t == TOK_STRING || t == TOK_LPAREN || t == TOK_MINUS ||
           t == TOK_NOT || t == TOK_CHECK_CPU || t == TOK_PATCH ||
           t == TOK_FUNC || t == TOK_BREAK || t == TOK_CONTINUE ||
           t == TOK_SKIP ||
           t == TOK_TRUE || t == TOK_FALSE || t == TOK_LBRACKET ||
           t == TOK_ENUM || t == TOK_RECORD || t == TOK_ENTITY ||
           t == TOK_IMPORT || t == TOK_FROM || t == TOK_MODULE ||
           t == TOK_EXPORT || t == TOK_INCLUDE ||
           t == TOK_EXTERN || t == TOK_CASE ||
           t == TOK_NONE_LIT;
}

/* ═══════════════════════════════════════════════════════
 * v1.2/v2 Block Opener: accept ':' or 'then' (optional)
 * ═══════════════════════════════════════════════════════ */

static int expect_block_open(vir_parser_t *p, const char *context)
{
    if (match(p, TOK_COLON)) return 1;
    if (match(p, TOK_THEN))  return 1;
    /* v2: Block opener optional — if next token starts statement, proceed */
    if (is_stmt_start(peek(p)->type)) return 1;
    if (check(p, TOK_NEWLINE)) { skip_newlines(p); return 1; }
    char msg[128];
    snprintf(msg, sizeof(msg), "expected ':' or 'then' after %s", context);
    parse_error(p, msg);
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Generics Helpers: <T>, <T, U>, etc.
 * ═══════════════════════════════════════════════════════ */

/* Check if current '<' starts generic params (lookahead).
 * Heuristic: <IDENT[,IDENT]*> followed by ( { : ; = NL */
static int check_is_generics(const vir_parser_t *p)
{
    if (peek(p)->type != TOK_LT) return 0;

    uint32_t i = p->pos + 1;
    int depth = 1;

    while (i < p->token_count && depth > 0) {
        vir_tok_t t = p->tokens[i].type;
        if (t == TOK_LT) depth++;
        else if (t == TOK_GT) {
            depth--;
            if (depth == 0) {
                i++;
                if (i < p->token_count) {
                    vir_tok_t after = p->tokens[i].type;
                    return after == TOK_LPAREN || after == TOK_LBRACE ||
                           after == TOK_COLON || after == TOK_SEMICOLON ||
                           after == TOK_NEWLINE || after == TOK_EOF ||
                           after == TOK_COMMA || after == TOK_ASSIGN ||
                           after == TOK_RPAREN;
                }
                return 1;
            }
        } else if (t != TOK_IDENT && t != TOK_COMMA && t != TOK_STAR &&
                   t != TOK_FUNC && t != TOK_ARROW && t != TOK_LPAREN &&
                   t != TOK_RPAREN) {
            return 0;  /* Not a generic param list */
        }
        i++;
    }
    return 0;
}

/* Skip generic params: <T>, <T, U>, etc. */
static void skip_generics(vir_parser_t *p)
{
    if (!check(p, TOK_LT) || !check_is_generics(p)) return;
    advance(p);  /* consume < */
    int depth = 1;
    while (!check(p, TOK_EOF) && depth > 0) {
        if (check(p, TOK_LT)) depth++;
        else if (check(p, TOK_GT)) depth--;
        advance(p);
    }
}

/* Skip a type annotation until we hit = ; NL ) } , or EOF
 * Handles: int, Vec<Token>, [i32], func(T) -> U, ptr, etc. */
static void skip_type_annotation(vir_parser_t *p)
{
    int depth = 0;
    while (!check(p, TOK_EOF)) {
        if (depth == 0) {
            vir_tok_t t = peek(p)->type;
            if (t == TOK_ASSIGN || t == TOK_SEMICOLON ||
                t == TOK_NEWLINE || t == TOK_LBRACE ||
                t == TOK_COMMA)
                return;
            if (t == TOK_RPAREN) return;
        }
        vir_tok_t t = peek(p)->type;
        if (t == TOK_LT || t == TOK_LBRACKET || t == TOK_LPAREN) depth++;
        if (t == TOK_GT || t == TOK_RBRACKET || t == TOK_RPAREN) {
            if (depth > 0) depth--;
            else return;
        }
        advance(p);
    }
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
    {"dài",           BUILTIN_LEN},
    {"đẩy",           BUILTIN_PUSH},
    {"cấp",           BUILTIN_ALLOC},
    {"giải",          BUILTIN_FREE_MEM},
    {"đọc_byte",      BUILTIN_READ8},
    {"ghi_byte",      BUILTIN_WRITE8},
    {"đọc_số",        BUILTIN_READ64},
    {"ghi_số",        BUILTIN_WRITE64},
    {"dài_chuỗi",     BUILTIN_STR_LEN},
    {"ký_tự",         BUILTIN_STR_GET},
    {"nối",           BUILTIN_STR_CAT},
    {"bằng_chuỗi",    BUILTIN_STR_EQ},
    {"mở_tệp",       BUILTIN_FILE_OPEN},
    {"đọc_tệp",      BUILTIN_FILE_READ},
    {"ghi_tệp",      BUILTIN_FILE_WRITE},
    {"đóng_tệp",     BUILTIN_FILE_CLOSE},
    {"ghi_byte_tệp",  BUILTIN_FILE_WRITE_BYTE},
    {"thoát_ct",      BUILTIN_EXIT},
    {"số_sang_chuỗi", BUILTIN_I_TO_STR},
    {"chuỗi_sang_số", BUILTIN_STR_TO_I},
    {"mảng_mới",      BUILTIN_ARR_NEW},
    /* English */
    {"len",           BUILTIN_LEN},
    {"push",          BUILTIN_PUSH},
    {"alloc",         BUILTIN_ALLOC},
    {"dealloc",       BUILTIN_FREE_MEM},
    {"read_byte",     BUILTIN_READ8},
    {"write_byte",    BUILTIN_WRITE8},
    {"read_word",     BUILTIN_READ64},
    {"write_word",    BUILTIN_WRITE64},
    {"str_len",       BUILTIN_STR_LEN},
    {"str_get",       BUILTIN_STR_GET},
    {"str_cat",       BUILTIN_STR_CAT},
    {"str_eq",        BUILTIN_STR_EQ},
    {"file_open",     BUILTIN_FILE_OPEN},
    {"file_read",     BUILTIN_FILE_READ},
    {"file_write",    BUILTIN_FILE_WRITE},
    {"file_close",    BUILTIN_FILE_CLOSE},
    {"file_write_byte", BUILTIN_FILE_WRITE_BYTE},
    {"exit_prog",     BUILTIN_EXIT},
    {"i_to_str",      BUILTIN_I_TO_STR},
    {"int_to_str",    BUILTIN_I_TO_STR},
    {"str_to_i",      BUILTIN_STR_TO_I},
    {"str_to_int",    BUILTIN_STR_TO_I},
    {"arr_new",       BUILTIN_ARR_NEW},
    {"print_str",     BUILTIN_PRINT_STR},
    {"viết_chuỗi",    BUILTIN_PRINT_STR},
    {"get_arg",       BUILTIN_GET_ARG},
    {"lấy_arg",       BUILTIN_GET_ARG},
    {"arg_count",     BUILTIN_ARG_COUNT},
    {"đếm_arg",       BUILTIN_ARG_COUNT},
    {NULL, 0}
};

static int lookup_builtin(const char *name)
{
    for (int i = 0; builtins[i].name; i++) {
        if (strcmp(builtins[i].name, name) == 0)
            return builtins[i].id;
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Forward Declarations
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_expr(vir_parser_t *p);
static ast_node_t *parse_statement(vir_parser_t *p);

/* Check if current '{' starts a record literal.
 * Lookahead: '{' IDENT ':' or '{' IDENT '=' or '{' '}' or '{' ';' */
static int check_record_literal(vir_parser_t *p)
{
    if (p->pos >= p->token_count || p->tokens[p->pos].type != TOK_LBRACE)
        return 0;

    uint32_t next = p->pos + 1;

    /* Empty record literal */
    if (next < p->token_count && p->tokens[next].type == TOK_RBRACE)
        return 1;

    /* {; multiline record literal */
    if (next < p->token_count && p->tokens[next].type == TOK_SEMICOLON)
        return 1;

    /* { NEWLINE — multiline */
    if (next < p->token_count && p->tokens[next].type == TOK_NEWLINE)
        return 1;

    if (next + 1 < p->token_count && p->tokens[next].type == TOK_IDENT) {
        vir_tok_t after = p->tokens[next + 1].type;
        /* IDENT ':' or IDENT '=' pattern */
        if (after == TOK_COLON || after == TOK_ASSIGN)
            return 1;
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Expression Parsing (precedence climbing)
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_primary(vir_parser_t *p)
{
    const vir_token_t *t = peek(p);

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

    case TOK_IF: {
        /* If-expression: if COND THEN_EXPR else ELSE_EXPR end */
        advance(p);
        uint32_t line = t->line;
        ast_node_t *cond = parse_expr(p);
        if (!cond) return NULL;

        /* Body might or might not have block opener */
        int has_block = match(p, TOK_COLON) || match(p, TOK_THEN);

        if (has_block) {
            /* Block-style if-expression — parse as full if, return last value */
            ast_node_t *then_block = ast_new(AST_BLOCK);
            skip_newlines(p);
            while (!check(p, TOK_ELSE) && !check(p, TOK_END) &&
                   !check(p, TOK_EIF) && !check(p, TOK_ELIF) && !check(p, TOK_EOF)) {
                ast_node_t *stmt = parse_statement(p);
                if (stmt) ast_add_child(then_block, stmt);
                else if (p->error[0] != '\0') break;
                else advance(p);
                skip_newlines(p);
            }

            ast_node_t *if_node = ast_new(AST_IF);
            if_node->line = line;
            ast_add_child(if_node, cond);
            ast_add_child(if_node, then_block);

            if (match(p, TOK_ELSE)) {
                skip_newlines(p);
                match(p, TOK_COLON);
                match(p, TOK_THEN);
                ast_node_t *else_block = ast_new(AST_BLOCK);
                while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
                    ast_node_t *stmt = parse_statement(p);
                    if (stmt) ast_add_child(else_block, stmt);
                    else if (p->error[0] != '\0') break;
                    else advance(p);
                    skip_newlines(p);
                }
                ast_add_child(if_node, else_block);
            }
            match(p, TOK_END);
            match(p, TOK_COLON);  /* optional trailing ':' after end */
            return if_node;
        }

        /* Single-line if-expression: if COND THEN_EXPR else ELSE_EXPR end */
        ast_node_t *then_val = parse_expr(p);
        ast_node_t *if_node = ast_new(AST_IF);
        if_node->line = line;
        ast_add_child(if_node, cond);

        /* Wrap then-value as return in block */
        ast_node_t *then_block = ast_new(AST_BLOCK);
        if (then_val) {
            ast_node_t *out1 = ast_new(AST_RETURN);
            out1->line = line;
            ast_add_child(out1, then_val);
            ast_add_child(then_block, out1);
        }
        ast_add_child(if_node, then_block);

        if (match(p, TOK_ELSE)) {
            ast_node_t *else_val = parse_expr(p);
            ast_node_t *else_block = ast_new(AST_BLOCK);
            if (else_val) {
                ast_node_t *out2 = ast_new(AST_RETURN);
                out2->line = line;
                ast_add_child(out2, else_val);
                ast_add_child(else_block, out2);
            }
            ast_add_child(if_node, else_block);
        }

        match(p, TOK_END);
        match(p, TOK_COLON);  /* optional trailing ':' */
        return if_node;
    }

    case TOK_IDENT: {
        advance(p);
        const char *ident_name = t->str.buf;
        uint32_t ident_line = t->line;

        /* ── Enum::Variant namespace access ──────────────── */
        if (check(p, TOK_COLONCOLON)) {
            advance(p);  /* consume :: */
            const vir_token_t *variant = expect(p, TOK_IDENT, "expected variant name after '::'");
            if (variant) {
                ast_node_t *ea = ast_new(AST_ENUM_ACCESS);
                strncpy(ea->name, ident_name, AST_NAME_LEN - 1);
                strncpy(ea->name2, variant->str.buf, AST_NAME_LEN - 1);
                ea->line = ident_line;
                return ea;
            }
        }

        /* ── Skip generics <T> on identifier if present ──── */
        if (check_is_generics(p)) {
            skip_generics(p);
        }

        /* ── Record literal: IDENT '{' field: val, ... '}' ─ */
        if (check(p, TOK_LBRACE) && check_record_literal(p)) {
            advance(p);  /* consume '{' */
            /* Skip semicolons/newlines after { */
            skip_terminators(p);

            ast_node_t *rl = ast_new(AST_RECORD_LITERAL);
            strncpy(rl->name, ident_name, AST_NAME_LEN - 1);
            rl->line = ident_line;

            while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
                skip_terminators(p);
                if (check(p, TOK_RBRACE)) break;

                const vir_token_t *fname = expect(p, TOK_IDENT, "expected field name");
                if (!fname) break;

                /* Accept ':' or '=' after field name */
                if (!match(p, TOK_COLON) && !match(p, TOK_ASSIGN)) {
                    parse_error(p, "expected ':' or '=' after field name");
                    break;
                }

                ast_node_t *val = parse_expr(p);
                if (val) {
                    strncpy(val->name2, fname->str.buf, AST_NAME_LEN - 1);
                    ast_add_child(rl, val);
                }
                match(p, TOK_COMMA);
                skip_terminators(p);
            }
            expect(p, TOK_RBRACE, "expected '}' after record literal");
            /* Optional trailing semicolons */
            match(p, TOK_SEMICOLON);
            return rl;
        }

        /* ── Function call: IDENT '(' args ')' ──────────── */
        if (check(p, TOK_LPAREN)) {
            int bid = lookup_builtin(ident_name);
            if (bid != 0) {
                /* Builtin function call */
                ast_node_t *call = ast_new(AST_BUILTIN_CALL);
                call->builtin_id = bid;
                strncpy(call->name, ident_name, AST_NAME_LEN - 1);
                call->line = ident_line;
                advance(p);  /* consume '(' */
                if (!check(p, TOK_RPAREN)) {
                    ast_node_t *arg = parse_expr(p);
                    if (arg) ast_add_child(call, arg);
                    while (match(p, TOK_COMMA)) {
                        arg = parse_expr(p);
                        if (arg) ast_add_child(call, arg);
                    }
                }
                expect(p, TOK_RPAREN, "expected ')' after builtin arguments");
                return call;
            }

            /* Regular function call */
            ast_node_t *call = ast_new(AST_CALL);
            strncpy(call->name, ident_name, AST_NAME_LEN - 1);
            call->line = ident_line;
            advance(p);  /* consume '(' */
            if (!check(p, TOK_RPAREN)) {
                ast_node_t *arg = parse_expr(p);
                if (arg) ast_add_child(call, arg);
                while (match(p, TOK_COMMA)) {
                    arg = parse_expr(p);
                    if (arg) ast_add_child(call, arg);
                }
            }
            expect(p, TOK_RPAREN, "expected ')' after arguments");
            return call;
        }

        /* ── Index access: IDENT '[' expr ']' ───────────── */
        if (check(p, TOK_LBRACKET)) {
            advance(p);
            ast_node_t *idx = parse_expr(p);
            expect(p, TOK_RBRACKET, "expected ']' after index");
            ast_node_t *access = ast_new(AST_INDEX_ACCESS);
            strncpy(access->name, ident_name, AST_NAME_LEN - 1);
            access->line = ident_line;
            ast_add_child(access, idx);
            return access;
        }

        /* ── Plain identifier ────────────────────────────── */
        ast_node_t *n = ast_new(AST_IDENTIFIER);
        strncpy(n->name, ident_name, AST_NAME_LEN - 1);
        n->line = ident_line;
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
        expect(p, TOK_RPAREN, "expected ')'");
        return inner;
    }
    case TOK_LBRACKET: {
        /* Array literal: [expr, expr, ...] */
        advance(p);
        ast_node_t *arr = ast_new(AST_ARRAY_LITERAL);
        arr->line = t->line;
        if (!check(p, TOK_RBRACKET)) {
            ast_node_t *elem = parse_expr(p);
            if (elem) ast_add_child(arr, elem);
            while (match(p, TOK_COMMA)) {
                elem = parse_expr(p);
                if (elem) ast_add_child(arr, elem);
            }
        }
        expect(p, TOK_RBRACKET, "expected ']' after array literal");
        return arr;
    }
    case TOK_AND: {
        /* & as address-of — treat as unary producing the identifier */
        advance(p);
        ast_node_t *inner = parse_primary(p);
        /* For now, just pass through — address-of is identity in VM */
        return inner;
    }
    default:
        parse_error(p, "expected expression");
        return NULL;
    }
}

/* Postfix: field access, safe access, call chains */
static ast_node_t *parse_postfix(vir_parser_t *p, ast_node_t *left)
{
    while (left) {
        if (check(p, TOK_DOT)) {
            advance(p);
            const vir_token_t *field = expect(p, TOK_IDENT, "expected field name after '.'");
            if (!field) break;

            /* Check if field is followed by '(' — method-like call */
            if (check(p, TOK_LPAREN)) {
                /* Method call: obj.method(args) → call method(obj, args) */
                advance(p);  /* consume '(' */
                ast_node_t *call = ast_new(AST_CALL);
                strncpy(call->name, field->str.buf, AST_NAME_LEN - 1);
                call->line = field->line;
                ast_add_child(call, left);  /* self/receiver as first arg */
                if (!check(p, TOK_RPAREN)) {
                    ast_node_t *arg = parse_expr(p);
                    if (arg) ast_add_child(call, arg);
                    while (match(p, TOK_COMMA)) {
                        arg = parse_expr(p);
                        if (arg) ast_add_child(call, arg);
                    }
                }
                expect(p, TOK_RPAREN, "expected ')' after method arguments");
                left = call;
                continue;
            }

            /* Check if field has generics <T> */
            if (check_is_generics(p)) skip_generics(p);

            /* Check for index on field: expr.field[idx] */
            if (check(p, TOK_LBRACKET)) {
                /* First create field access, then index */
                ast_node_t *fa = ast_new(AST_FIELD_ACCESS);
                strncpy(fa->name, field->str.buf, AST_NAME_LEN - 1);
                fa->line = field->line;
                ast_add_child(fa, left);

                advance(p);  /* consume '[' */
                ast_node_t *idx = parse_expr(p);
                expect(p, TOK_RBRACKET, "expected ']'");

                ast_node_t *ia = ast_new(AST_INDEX_ACCESS);
                /* Store field access as child */
                ia->line = field->line;
                ast_add_child(ia, fa);
                if (idx) ast_add_child(ia, idx);
                left = ia;
                continue;
            }

            ast_node_t *fa = ast_new(AST_FIELD_ACCESS);
            strncpy(fa->name, field->str.buf, AST_NAME_LEN - 1);
            fa->line = field->line;
            ast_add_child(fa, left);
            left = fa;
            continue;
        }

        if (check(p, TOK_SAFE_ACCESS)) {
            advance(p);  /* consume ?. */
            const vir_token_t *field = expect(p, TOK_IDENT, "expected field name after '?.'");
            if (!field) break;
            ast_node_t *sa = ast_new(AST_SAFE_ACCESS);
            strncpy(sa->name, field->str.buf, AST_NAME_LEN - 1);
            sa->line = field->line;
            ast_add_child(sa, left);
            left = sa;
            continue;
        }

        if (check(p, TOK_EXIST)) {
            advance(p);  /* consume ? */
            ast_node_t *ex = ast_new(AST_EXIST_CHECK);
            ex->line = left->line;
            ast_add_child(ex, left);
            left = ex;
            continue;
        }

        break;
    }
    return left;
}

static ast_node_t *parse_unary(vir_parser_t *p)
{
    if (check(p, TOK_MINUS)) {
        const vir_token_t *t = advance(p);
        ast_node_t *operand = parse_unary(p);
        if (!operand) return NULL;

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
        if (!operand) return NULL;

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
    if (check(p, TOK_BIT_NOT)) {
        /* Bitwise NOT: ~expr */
        const vir_token_t *t = advance(p);
        ast_node_t *operand = parse_unary(p);
        if (!operand) return NULL;

        /* ~x → x XOR -1 */
        ast_node_t *neg1 = ast_new(AST_LITERAL_INT);
        neg1->int_val = -1;
        neg1->line = t->line;

        ast_node_t *n = ast_new(AST_BINOP);
        n->op = OP_XOR;
        n->line = t->line;
        ast_add_child(n, operand);
        ast_add_child(n, neg1);
        return n;
    }

    ast_node_t *left = parse_primary(p);
    if (!left) return NULL;
    return parse_postfix(p, left);
}

static ast_node_t *parse_power(vir_parser_t *p)
{
    ast_node_t *left = parse_unary(p);
    if (!left) return NULL;

    while (check(p, TOK_POWER)) {
        const vir_token_t *op_tok = advance(p);
        ast_node_t *right = parse_unary(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = OP_POW;
        bin->line = op_tok->line;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

static ast_node_t *parse_mult(vir_parser_t *p)
{
    ast_node_t *left = parse_power(p);
    if (!left) return NULL;

    while (check(p, TOK_STAR) || check(p, TOK_SLASH) ||
           check(p, TOK_PERCENT) || check(p, TOK_MOD)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op;
        switch (op_tok->type) {
        case TOK_STAR:    op = OP_MUL; break;
        case TOK_SLASH:   op = OP_DIV; break;
        case TOK_PERCENT: op = OP_MOD; break;
        case TOK_MOD:     op = OP_MOD; break;
        default:          op = OP_MUL; break;
        }

        ast_node_t *right = parse_power(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = op;
        bin->line = op_tok->line;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

static ast_node_t *parse_addition(vir_parser_t *p)
{
    ast_node_t *left = parse_mult(p);
    if (!left) return NULL;

    while (check(p, TOK_PLUS) || check(p, TOK_MINUS)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op = (op_tok->type == TOK_PLUS) ? OP_ADD : OP_SUB;

        ast_node_t *right = parse_mult(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = op;
        bin->line = op_tok->line;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

static ast_node_t *parse_bitwise(vir_parser_t *p)
{
    ast_node_t *left = parse_addition(p);
    if (!left) return NULL;

    while (check(p, TOK_BIT_AND) || check(p, TOK_BIT_OR) ||
           check(p, TOK_BIT_XOR) || check(p, TOK_BIT_SHL) ||
           check(p, TOK_BIT_SHR)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op;
        switch (op_tok->type) {
        case TOK_BIT_AND: op = OP_AND; break;
        case TOK_BIT_OR:  op = OP_OR;  break;
        case TOK_BIT_XOR: op = OP_XOR; break;
        case TOK_BIT_SHL: op = OP_SHL; break;
        case TOK_BIT_SHR: op = OP_SHR; break;
        default:          op = OP_AND; break;
        }

        ast_node_t *right = parse_addition(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = op;
        bin->line = op_tok->line;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

/* ── Cast: expr >> Type ────────────────────────────────── */
static ast_node_t *parse_cast(vir_parser_t *p)
{
    ast_node_t *left = parse_bitwise(p);
    if (!left) return NULL;

    while (check(p, TOK_CAST)) {
        const vir_token_t *op_tok = advance(p);  /* consume >> */
        /* Type name after cast */
        const vir_token_t *type_tok = expect(p, TOK_IDENT, "expected type name after '>>'");
        if (!type_tok) return left;

        ast_node_t *cast = ast_new(AST_CAST);
        strncpy(cast->name, type_tok->str.buf, AST_NAME_LEN - 1);
        cast->line = op_tok->line;
        ast_add_child(cast, left);
        left = cast;
    }
    return left;
}

static ast_node_t *parse_compare(vir_parser_t *p)
{
    ast_node_t *left = parse_cast(p);
    if (!left) return NULL;

    if (check(p, TOK_EQ) || check(p, TOK_NE) || check(p, TOK_GT) ||
        check(p, TOK_LT) || check(p, TOK_GE) || check(p, TOK_LE)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op;
        switch (op_tok->type) {
        case TOK_EQ: op = OP_EQ; break;
        case TOK_NE: op = OP_NE; break;
        case TOK_GT: op = OP_GT; break;
        case TOK_LT: op = OP_LT; break;
        case TOK_GE: op = OP_GE; break;
        case TOK_LE: op = OP_LE; break;
        default:     op = OP_EQ; break;
        }

        ast_node_t *right = parse_cast(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *cmp = ast_new(AST_COMPARE);
        cmp->op = op;
        cmp->line = op_tok->line;
        ast_add_child(cmp, left);
        ast_add_child(cmp, right);
        return cmp;
    }
    return left;
}

static ast_node_t *parse_and_expr(vir_parser_t *p)
{
    ast_node_t *left = parse_compare(p);
    if (!left) return NULL;

    while (check(p, TOK_AND)) {
        advance(p);
        ast_node_t *right = parse_compare(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = OP_AND;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

static ast_node_t *parse_or_expr(vir_parser_t *p)
{
    ast_node_t *left = parse_and_expr(p);
    if (!left) return NULL;

    while (check(p, TOK_OR)) {
        advance(p);
        ast_node_t *right = parse_and_expr(p);
        if (!right) { ast_free(left); return NULL; }

        ast_node_t *bin = ast_new(AST_BINOP);
        bin->op = OP_OR;
        ast_add_child(bin, left);
        ast_add_child(bin, right);
        left = bin;
    }
    return left;
}

static ast_node_t *parse_expr(vir_parser_t *p)
{
    return parse_or_expr(p);
}

/* ═══════════════════════════════════════════════════════
 * Statement Parsing
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_block(vir_parser_t *p)
{
    ast_node_t *block = ast_new(AST_BLOCK);

    skip_newlines(p);

    while (!check(p, TOK_END) && !check(p, TOK_ELSE) &&
           !check(p, TOK_ELIF) && !check(p, TOK_EIF) &&
           !check(p, TOK_CASE) && !check(p, TOK_EOF)) {
        ast_node_t *stmt = parse_statement(p);
        if (stmt) {
            ast_add_child(block, stmt);
        } else {
            if (p->error[0] != '\0') break;
            advance(p);
        }
        skip_newlines(p);
    }

    return block;
}

/* Block that stops at END/ELSE/ELIF but NOT at CASE (for top-level case) */
static ast_node_t *parse_block_no_case_stop(vir_parser_t *p)
{
    ast_node_t *block = ast_new(AST_BLOCK);
    skip_newlines(p);
    while (!check(p, TOK_END) && !check(p, TOK_ELSE) &&
           !check(p, TOK_ELIF) && !check(p, TOK_EIF) && !check(p, TOK_EOF)) {
        ast_node_t *stmt = parse_statement(p);
        if (stmt) {
            ast_add_child(block, stmt);
        } else {
            if (p->error[0] != '\0') break;
            advance(p);
        }
        skip_newlines(p);
    }
    return block;
}

/* ═══════════════════════════════════════════════════════
 * Variable / Constant Declaration (v2)
 * ═══════════════════════════════════════════════════════
 * Supports:
 *   var NAME = expr
 *   var NAME: TYPE = expr
 *   var NAME: TYPE;
 *   const NAME: value;
 *   const NAME = expr;
 *   var (x, y) = expr;  (tuple destructuring)
 */

static ast_node_t *parse_var_decl(vir_parser_t *p, ast_type_t type)
{
    /* ── Tuple destructuring: var (x, y) = expr ─────────── */
    if (check(p, TOK_LPAREN)) {
        advance(p);  /* consume '(' */

        char names[16][AST_NAME_LEN];
        int name_count = 0;
        memset(names, 0, sizeof(names));

        while (!check(p, TOK_RPAREN) && !check(p, TOK_EOF)) {
            const vir_token_t *n = peek(p);
            if (n->type == TOK_IDENT) {
                advance(p);
                if (name_count < 16) {
                    strncpy(names[name_count], n->str.buf, AST_NAME_LEN - 1);
                    name_count++;
                }
            } else {
                /* Might be '_' wildcard — skip */
                advance(p);
                if (name_count < 16) {
                    strncpy(names[name_count], "_", AST_NAME_LEN - 1);
                    name_count++;
                }
            }
            if (!match(p, TOK_COMMA)) break;
        }
        expect(p, TOK_RPAREN, "expected ')' after tuple names");

        ast_node_t *decl = ast_new(type);
        if (name_count > 0) {
            strncpy(decl->name, names[0], AST_NAME_LEN - 1);
        }
        decl->line = peek(p)->line;

        if (match(p, TOK_ASSIGN)) {
            ast_node_t *init = parse_expr(p);
            if (init) ast_add_child(decl, init);
        }
        match(p, TOK_SEMICOLON);
        return decl;
    }

    /* ── Regular: var/const NAME ... ────────────────────── */
    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected variable name");
    if (!name_tok) return NULL;

    ast_node_t *decl = ast_new(type);
    strncpy(decl->name, name_tok->str.buf, AST_NAME_LEN - 1);
    decl->line = name_tok->line;

    if (match(p, TOK_COLON)) {
        if (type == AST_CONST_DECL) {
            /* const NAME: value — colon is assignment */
            ast_node_t *init = parse_expr(p);
            if (init) ast_add_child(decl, init);
        } else {
            /* var NAME: TYPE [= value] — colon is type annotation */
            skip_type_annotation(p);
            if (match(p, TOK_ASSIGN)) {
                ast_node_t *init = parse_expr(p);
                if (init) ast_add_child(decl, init);
            }
        }
    } else if (match(p, TOK_ASSIGN)) {
        ast_node_t *init = parse_expr(p);
        if (init) ast_add_child(decl, init);
    }

    match(p, TOK_SEMICOLON);
    return decl;
}

static ast_node_t *parse_if_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    ast_node_t *cond = parse_expr(p);
    if (!cond) return NULL;

    /* Block opener is optional in v2 */
    int has_opener = match(p, TOK_COLON) || match(p, TOK_THEN);
    (void)has_opener;

    ast_node_t *then_block = parse_block_no_case_stop(p);

    ast_node_t *if_node = ast_new(AST_IF);
    if_node->line = line;
    ast_add_child(if_node, cond);
    ast_add_child(if_node, then_block);

    /* Handle ELIF/EIF as nested IF in else branch */
    if (check(p, TOK_ELIF) || check(p, TOK_EIF)) {
        advance(p);
        ast_node_t *elif_as_if = parse_if_stmt(p);
        ast_node_t *else_block = ast_new(AST_BLOCK);
        if (elif_as_if) ast_add_child(else_block, elif_as_if);
        ast_add_child(if_node, else_block);
        return if_node;
    }

    if (match(p, TOK_ELSE)) {
        skip_newlines(p);
        match(p, TOK_THEN);
        match(p, TOK_COLON);
        ast_node_t *else_block = parse_block_no_case_stop(p);
        ast_add_child(if_node, else_block);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after if block");
    /* Optional trailing ':' after end (v2 style) */
    match(p, TOK_COLON);
    return if_node;
}

static ast_node_t *parse_loop_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    /* Check for infinite loop: LOOP ':' or LOOP NEWLINE */
    if (check(p, TOK_NEWLINE) || check(p, TOK_COLON)) {
        match(p, TOK_COLON);
        skip_newlines(p);
        ast_node_t *body = parse_block_no_case_stop(p);
        expect(p, TOK_END, "expected 'end' after loop block");
        match(p, TOK_COLON);

        ast_node_t *cond = ast_new(AST_LITERAL_INT);
        cond->int_val = 1;
        cond->line = line;
        ast_node_t *n = ast_new(AST_WHILE);
        n->line = line;
        ast_add_child(n, cond);
        ast_add_child(n, body);
        return n;
    }

    /* Counted loop */
    ast_node_t *count = parse_expr(p);
    if (!count) return NULL;

    expect_block_open(p, "loop count");
    ast_node_t *body = parse_block_no_case_stop(p);
    expect(p, TOK_END, "expected 'hết'/'end' after loop block");
    match(p, TOK_COLON);

    ast_node_t *n = ast_new(AST_LOOP);
    n->line = line;
    ast_add_child(n, count);
    ast_add_child(n, body);
    return n;
}

static ast_node_t *parse_while_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    ast_node_t *cond = parse_expr(p);
    if (!cond) return NULL;

    expect_block_open(p, "while condition");
    ast_node_t *body = parse_block_no_case_stop(p);
    expect(p, TOK_END, "expected 'hết'/'end' after while block");
    match(p, TOK_COLON);

    ast_node_t *n = ast_new(AST_WHILE);
    n->line = line;
    ast_add_child(n, cond);
    ast_add_child(n, body);
    return n;
}

static ast_node_t *parse_when_loop_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    ast_node_t *cond = parse_expr(p);
    if (!cond) return NULL;

    expect(p, TOK_LOOP, "expected 'loop' after when condition");
    ast_node_t *body = parse_block_no_case_stop(p);
    expect(p, TOK_END, "expected 'end' after when...loop block");
    match(p, TOK_COLON);

    ast_node_t *n = ast_new(AST_WHILE);
    n->line = line;
    ast_add_child(n, cond);
    ast_add_child(n, body);
    return n;
}

static ast_node_t *parse_return_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;
    ast_node_t *n = ast_new(AST_RETURN);
    n->line = line;

    if (!check(p, TOK_NEWLINE) && !check(p, TOK_END) &&
        !check(p, TOK_EOF) && !check(p, TOK_ELSE) &&
        !check(p, TOK_SEMICOLON) && !check(p, TOK_CASE)) {
        ast_node_t *val = parse_expr(p);
        if (val) ast_add_child(n, val);
    }
    match(p, TOK_SEMICOLON);
    return n;
}

static ast_node_t *parse_print_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;
    ast_node_t *n = ast_new(AST_PRINT);
    n->line = line;

    ast_node_t *val = parse_expr(p);
    if (val) ast_add_child(n, val);
    return n;
}

/* ═══════════════════════════════════════════════════════
 * Function Definition (v2)
 * ═══════════════════════════════════════════════════════
 * Supports:
 *   func name:  in(params)  body  end
 *   func name(params) then body end      (legacy)
 *   func name<T>(param: Type, ...) -> RetType: body end  (v2 paren)
 *   func name<T>: in(params) body end    (v2 colon)
 */

static ast_node_t *parse_func_def(vir_parser_t *p)
{
    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected function name");
    if (!name_tok) return NULL;

    ast_node_t *fn = ast_new(AST_FUNC_DEF);
    strncpy(fn->name, name_tok->str.buf, AST_NAME_LEN - 1);
    fn->line = name_tok->line;

    /* Skip generics <T> or <T, U> after name */
    if (check_is_generics(p)) skip_generics(p);

    if (check(p, TOK_COLON)) {
        /* ─── v1.2/v2 colon-style: func name[<T>]: [in(params)] block end ─── */
        advance(p);  /* consume ':' */
        skip_newlines(p);

        /* Optional in(...) parameter block */
        if (check(p, TOK_IN)) {
            advance(p);
            expect(p, TOK_LPAREN, "expected '(' after 'in'");

            if (!check(p, TOK_RPAREN)) {
                for (;;) {
                    const vir_token_t *param_tok = expect(p, TOK_IDENT, "expected parameter name");
                    if (!param_tok) break;
                    ast_node_t *param = ast_new(AST_IDENTIFIER);
                    strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
                    param->line = param_tok->line;
                    /* Optional type hint: ':' TYPE */
                    if (match(p, TOK_COLON)) {
                        skip_type_annotation(p);
                    }
                    ast_add_child(fn, param);
                    if (!match(p, TOK_SEMICOLON) && !match(p, TOK_COMMA)) break;
                }
            }
            expect(p, TOK_RPAREN, "expected ')' after parameters");
            skip_newlines(p);
        }

        ast_node_t *body = parse_block_no_case_stop(p);
        ast_add_child(fn, body);

        expect(p, TOK_END, "expected 'end' to close function");
        match(p, TOK_COLON);
        return fn;
    }

    if (check(p, TOK_LPAREN)) {
        /* ─── Paren-style: func name[<T>](params) [-> RetType] [:] block end ─── */
        advance(p);  /* consume '(' */

        if (!check(p, TOK_RPAREN)) {
            for (;;) {
                const vir_token_t *param_tok = expect(p, TOK_IDENT, "expected parameter name");
                if (!param_tok) break;
                ast_node_t *param = ast_new(AST_IDENTIFIER);
                strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
                param->line = param_tok->line;
                /* Optional type: ':' TYPE */
                if (match(p, TOK_COLON)) {
                    skip_type_annotation(p);
                }
                ast_add_child(fn, param);
                if (!match(p, TOK_COMMA) && !match(p, TOK_SEMICOLON)) break;
            }
        }

        expect(p, TOK_RPAREN, "expected ')' after parameters");

        /* Optional return type: -> Type */
        if (match(p, TOK_ARROW)) {
            skip_type_annotation(p);
        }

        /* Block opener (optional in v2 for paren-style) */
        if (!match(p, TOK_COLON) && !match(p, TOK_THEN)) {
            skip_newlines(p);
        }
        skip_newlines(p);

        ast_node_t *body = parse_block_no_case_stop(p);
        ast_add_child(fn, body);

        expect(p, TOK_END, "expected 'end' to close function");
        match(p, TOK_COLON);
        return fn;
    }

    /* If neither : nor (, try as colon-style without params */
    expect_block_open(p, "function signature");
    ast_node_t *body = parse_block_no_case_stop(p);
    ast_add_child(fn, body);
    expect(p, TOK_END, "expected 'end' to close function");
    match(p, TOK_COLON);
    return fn;
}

/* ═══════════════════════════════════════════════════════
 * Extern Function Declaration (v2)
 * ═══════════════════════════════════════════════════════
 * Syntax: extern func name(param: Type, ...) -> RetType;
 * Creates AST_HAS_DECL (forward declaration)
 */

static ast_node_t *parse_extern_func_decl(vir_parser_t *p)
{
    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected function name after extern func");
    if (!name_tok) return NULL;

    ast_node_t *decl = ast_new(AST_HAS_DECL);
    strncpy(decl->name, name_tok->str.buf, AST_NAME_LEN - 1);
    decl->line = name_tok->line;

    /* Skip generics */
    if (check_is_generics(p)) skip_generics(p);

    /* Parse parameter list (for param count) */
    if (match(p, TOK_LPAREN)) {
        if (!check(p, TOK_RPAREN)) {
            for (;;) {
                const vir_token_t *param_tok = expect(p, TOK_IDENT, "expected parameter name");
                if (!param_tok) break;
                ast_node_t *param = ast_new(AST_IDENTIFIER);
                strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
                param->line = param_tok->line;
                if (match(p, TOK_COLON)) {
                    skip_type_annotation(p);
                }
                ast_add_child(decl, param);
                if (!match(p, TOK_COMMA) && !match(p, TOK_SEMICOLON)) break;
            }
        }
        expect(p, TOK_RPAREN, "expected ')' after extern parameters");
    }

    /* Skip return type */
    if (match(p, TOK_ARROW)) {
        skip_type_annotation(p);
    }

    match(p, TOK_SEMICOLON);
    return decl;
}

/* ═══════════════════════════════════════════════════════
 * For-Range Statement
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_for_range_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *var_tok = expect(p, TOK_IDENT, "expected loop variable");
    if (!var_tok) return NULL;

    if (!expect(p, TOK_IN, "expected 'in'/'trong' after for variable"))
        return NULL;

    ast_node_t *start = parse_expr(p);
    if (!start) return NULL;

    if (!expect(p, TOK_DOTDOT, "expected '..' in range"))
        return NULL;

    ast_node_t *end_expr = parse_expr(p);
    if (!end_expr) { ast_free(start); return NULL; }

    expect_block_open(p, "for range");

    ast_node_t *body = parse_block_no_case_stop(p);
    expect(p, TOK_END, "expected 'hết'/'end' after for block");
    match(p, TOK_COLON);

    ast_node_t *n = ast_new(AST_FOR_RANGE);
    strncpy(n->name, var_tok->str.buf, AST_NAME_LEN - 1);
    n->line = line;
    ast_add_child(n, start);
    ast_add_child(n, end_expr);
    ast_add_child(n, body);
    return n;
}

/* ═══════════════════════════════════════════════════════
 * Enum Definition (v2)
 * ═══════════════════════════════════════════════════════
 * Supports:
 *   enum Name:
 *     Variant = value;
 *     Some(payload)
 *     None
 *   end
 */

static ast_node_t *parse_enum_def(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected enum name");
    if (!name_tok) return NULL;

    expect_block_open(p, "enum name");
    skip_newlines(p);

    ast_node_t *en = ast_new(AST_ENUM_DEF);
    strncpy(en->name, name_tok->str.buf, AST_NAME_LEN - 1);
    en->line = line;

    int64_t next_val = 0;

    while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
        const vir_token_t *vname = expect(p, TOK_IDENT, "expected enum variant name");
        if (!vname) break;

        int64_t val = next_val;

        /* ADT variant: Name(payload) — skip the payload */
        if (match(p, TOK_LPAREN)) {
            int depth = 1;
            while (!check(p, TOK_EOF) && depth > 0) {
                if (check(p, TOK_LPAREN)) depth++;
                if (check(p, TOK_RPAREN)) depth--;
                if (depth > 0) advance(p);
            }
            match(p, TOK_RPAREN);
        }

        /* Explicit value: = INT */
        if (match(p, TOK_ASSIGN)) {
            const vir_token_t *vt = peek(p);
            if (vt->type == TOK_INT) {
                val = vt->int_val;
                advance(p);
            } else {
                /* Could be a more complex expression — parse it */
                ast_node_t *vexpr = parse_expr(p);
                if (vexpr && vexpr->type == AST_LITERAL_INT) {
                    val = vexpr->int_val;
                }
                ast_free(vexpr);
            }
        }
        next_val = val + 1;

        ast_node_t *variant = ast_new(AST_LITERAL_INT);
        strncpy(variant->name, vname->str.buf, AST_NAME_LEN - 1);
        variant->int_val = val;
        variant->line = vname->line;
        ast_add_child(en, variant);

        /* Skip trailing semicolon */
        match(p, TOK_SEMICOLON);
        skip_newlines(p);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after enum definition");
    match(p, TOK_COLON);
    return en;
}

/* ═══════════════════════════════════════════════════════
 * Record / Entity Definition (v2)
 * ═══════════════════════════════════════════════════════
 * Supports:
 *   entity Name<T>:
 *     field: Type;
 *     field2: Type;
 *   end
 */

static ast_node_t *parse_record_def(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected record/entity name");
    if (!name_tok) return NULL;

    /* Skip generics <T> */
    if (check_is_generics(p)) skip_generics(p);

    /* Accept ':' or 'then' as block opener (optional for entity) */
    if (!match(p, TOK_COLON)) match(p, TOK_THEN);
    skip_newlines(p);

    ast_node_t *rec = ast_new(AST_RECORD_DEF);
    strncpy(rec->name, name_tok->str.buf, AST_NAME_LEN - 1);
    rec->line = line;

    while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
        const vir_token_t *fname = expect(p, TOK_IDENT, "expected field name");
        if (!fname) break;

        ast_node_t *field = ast_new(AST_IDENTIFIER);
        strncpy(field->name, fname->str.buf, AST_NAME_LEN - 1);
        field->line = fname->line;

        /* Optional type: field_name: type */
        if (match(p, TOK_COLON)) {
            /* Skip type tokens until newline, semicolon, or end */
            while (!check(p, TOK_NEWLINE) && !check(p, TOK_END) &&
                   !check(p, TOK_SEMICOLON) && !check(p, TOK_EOF)) {
                advance(p);
            }
        }

        ast_add_child(rec, field);
        match(p, TOK_SEMICOLON);
        skip_newlines(p);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after record/entity definition");
    match(p, TOK_COLON);
    return rec;
}

/* ═══════════════════════════════════════════════════════
 * Case Statement (v2)
 * ═══════════════════════════════════════════════════════
 * v1.2:  case EXPR :~  PAT: BODY; ... end
 * v2:    case EXPR;  case PAT BODY; ... end
 */

static ast_node_t *parse_case_stmt(vir_parser_t *p)
{
    ast_node_t *subject = parse_expr(p);
    if (!subject) { parse_error(p, "expected expression after 'case'"); return NULL; }

    ast_node_t *node = ast_new(AST_CASE);
    node->line = subject->line;
    ast_add_child(node, subject);  /* children[0] = subject */

    if (match(p, TOK_PATTERN)) {
        /* ─── v1.2 syntax: case EXPR :~ PAT: BODY; ... end ─── */
        skip_newlines(p);

        while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
            ast_node_t *arm = ast_new(AST_PATTERN_MATCH);
            const vir_token_t *pat = peek(p);

            if (pat->type == TOK_IDENT && strcmp(pat->str.buf, "_") == 0) {
                strncpy(arm->name, "_", AST_NAME_LEN - 1);
                arm->int_val = -1;
                advance(p);
            } else if (pat->type == TOK_INT) {
                arm->int_val = pat->int_val;
                snprintf(arm->name, AST_NAME_LEN, "%lld", (long long)pat->int_val);
                advance(p);
            } else if (pat->type == TOK_STRING) {
                strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
                arm->int_val = -2;
                advance(p);
            } else if (pat->type == TOK_IDENT) {
                strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
                arm->int_val = -3;
                advance(p);
            } else {
                parse_error(p, "expected pattern in case arm");
                ast_free(arm);
                break;
            }

            arm->line = pat->line;
            expect(p, TOK_COLON, "expected ':' after pattern");

            ast_node_t *body = parse_statement(p);
            if (body) ast_add_child(arm, body);

            match(p, TOK_SEMICOLON);
            skip_newlines(p);
            ast_add_child(node, arm);
        }

        expect(p, TOK_END, "expected 'end'/'hết' after case block");
        match(p, TOK_COLON);
        return node;
    }

    /* ─── v2 syntax: arms are separated by ';', statements inside one arm by ',' ─── */
    match(p, TOK_SEMICOLON);
    skip_newlines(p);

    while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
        skip_newlines(p);
        if (check(p, TOK_END) || check(p, TOK_EOF)) break;

        ast_node_t *arm = ast_new(AST_PATTERN_MATCH);

        /* Legacy-prefixed arm: `case PAT ...` */
        if (check(p, TOK_CASE)) advance(p);

        const vir_token_t *pat = peek(p);

        if (pat->type == TOK_ELSE ||
            (pat->type == TOK_IDENT && strcmp(pat->str.buf, "default") == 0) ||
            (pat->type == TOK_IDENT && strcmp(pat->str.buf, "_") == 0)) {
            strncpy(arm->name, "_", AST_NAME_LEN - 1);
            arm->int_val = -1;
            advance(p);
        } else if (pat->type == TOK_INT) {
            arm->int_val = pat->int_val;
            snprintf(arm->name, AST_NAME_LEN, "%lld", (long long)pat->int_val);
            advance(p);
        } else if (pat->type == TOK_STRING) {
            strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
            arm->int_val = -2;
            advance(p);
        } else if (pat->type == TOK_NONE_LIT) {
            strncpy(arm->name, "None", AST_NAME_LEN - 1);
            arm->int_val = 0;
            advance(p);
        } else if (pat->type == TOK_IDENT) {
            strncpy(arm->name, pat->str.buf, AST_NAME_LEN - 1);
            arm->int_val = -3;
            advance(p);
            if (match(p, TOK_DOT) || match(p, TOK_COLONCOLON)) {
                const vir_token_t *variant = peek(p);
                if (is_ident_like_tok(variant->type)) {
                    char tmp[AST_NAME_LEN];
                    snprintf(tmp, AST_NAME_LEN, "%s.%s", arm->name, variant->str.buf);
                    strncpy(arm->name, tmp, AST_NAME_LEN - 1);
                    advance(p);
                }
            }
            if (match(p, TOK_LPAREN)) {
                if (check(p, TOK_IDENT)) {
                    strncpy(arm->name2, peek(p)->str.buf, AST_NAME_LEN - 1);
                }
                int depth = 1;
                while (!check(p, TOK_EOF) && depth > 0) {
                    if (check(p, TOK_LPAREN)) depth++;
                    if (check(p, TOK_RPAREN)) depth--;
                    if (depth > 0) advance(p);
                }
                match(p, TOK_RPAREN);
            }
        } else {
            parse_error(p, "expected pattern in case arm");
            ast_free(arm);
            break;
        }

        arm->line = pat->line;
        match(p, TOK_COLON);

        /* Parse body: statements in one arm are separated by ',' */
        ast_node_t *body = ast_new(AST_BLOCK);
        skip_newlines(p);

        while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
            ast_node_t *stmt = parse_statement(p);
            if (stmt) {
                ast_add_child(body, stmt);
            } else {
                if (p->error[0] != '\0') break;
                advance(p);
            }
            if (match(p, TOK_COMMA)) {
                skip_newlines(p);
                continue;
            }
            break;
        }

        int has_arm_end = match(p, TOK_SEMICOLON);
        skip_newlines(p);
        int arm_terminated = has_arm_end;
        if (!arm_terminated && p->pos > 0) {
            vir_tok_t prev = p->tokens[p->pos - 1].type;
            if (prev == TOK_SEMICOLON) {
                arm_terminated = 1;
            } else if (prev == TOK_NEWLINE && p->pos > 1 && p->tokens[p->pos - 2].type == TOK_SEMICOLON) {
                arm_terminated = 1;
            }
        }
        if (!arm_terminated && !check(p, TOK_END) && !check(p, TOK_EOF)) {
            parse_error(p, "expected ';' after case arm or ',' between statements");
            ast_free(body);
            ast_free(arm);
            break;
        }

        /* If body has exactly 1 child, unwrap it */
        if (body->child_count == 1) {
            ast_add_child(arm, body->children[0]);
            body->child_count = 0;
            ast_free(body);
        } else if (body->child_count > 0) {
            ast_add_child(arm, body);
        } else {
            ast_free(body);
        }

        ast_add_child(node, arm);
        skip_newlines(p);
    }

    expect(p, TOK_END, "expected 'end' after case block");
    match(p, TOK_COLON);
    return node;
}

/* ═══════════════════════════════════════════════════════
 * Statement Dispatch
 * ═══════════════════════════════════════════════════════ */

static ast_node_t *parse_statement(vir_parser_t *p)
{
    skip_newlines(p);
    const vir_token_t *t = peek(p);

    switch (t->type) {
    case TOK_FUNC:
        advance(p);
        return parse_func_def(p);

    case TOK_VAR:
        advance(p);
        return parse_var_decl(p, AST_VAR_DECL);

    case TOK_CONST:
        advance(p);
        return parse_var_decl(p, AST_CONST_DECL);

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

    case TOK_RECORD:
    case TOK_ENTITY:
        advance(p);
        return parse_record_def(p);

    case TOK_RETURN:
    case TOK_OUT:
        advance(p);
        return parse_return_stmt(p);

    case TOK_PRINT:
        advance(p);
        return parse_print_stmt(p);

    case TOK_BREAK: {
        advance(p);
        ast_node_t *n = ast_new(AST_BREAK);
        n->line = t->line;
        match(p, TOK_SEMICOLON);
        return n;
    }
    case TOK_CONTINUE:
    case TOK_SKIP: {
        advance(p);
        ast_node_t *n = ast_new(AST_CONTINUE);
        n->line = t->line;
        match(p, TOK_SEMICOLON);
        return n;
    }

    /* ── extern func ──────────────────────────────────── */
    case TOK_EXTERN: {
        advance(p);
        if (match(p, TOK_FUNC)) {
            return parse_extern_func_decl(p);
        }
        /* Unknown extern usage — skip to next line */
        while (!check(p, TOK_NEWLINE) && !check(p, TOK_SEMICOLON) &&
               !check(p, TOK_EOF))
            advance(p);
        match(p, TOK_SEMICOLON);
        return NULL;
    }

    /* ── import (canonical v2 syntax) ─────────────────── */
    case TOK_IMPORT: {
        advance(p);
        ast_node_t *n = ast_new(AST_IMPORT);
        n->line = t->line;

        if (match(p, TOK_FROM)) {
            skip_newlines(p);
            char mod_name[AST_NAME_LEN] = {0};
            const vir_token_t *seg = expect(p, TOK_IDENT, "expected module name after 'from'");
            if (!seg) return n;
            strncpy(mod_name, seg->str.buf, AST_NAME_LEN - 1);
            while (match(p, TOK_DOT)) {
                const vir_token_t *part = expect(p, TOK_IDENT, "expected path segment after '.'");
                if (!part) break;
                strncat(mod_name, ".", AST_NAME_LEN - strlen(mod_name) - 1);
                strncat(mod_name, part->str.buf, AST_NAME_LEN - strlen(mod_name) - 1);
            }
            strncpy(n->name, mod_name, AST_NAME_LEN - 1);
            if (match(p, TOK_AS)) {
                const vir_token_t *alias = expect(p, TOK_IDENT, "expected alias after 'as'");
                if (alias) strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
            }
            match(p, TOK_SEMICOLON);
            return n;
        }

        do {
            skip_newlines(p);
            const vir_token_t *sym = expect(p, TOK_IDENT, "expected symbol name after import");
            if (!sym) break;
            ast_node_t *s = ast_new(AST_IDENTIFIER);
            strncpy(s->name, sym->str.buf, AST_NAME_LEN - 1);
            s->line = sym->line;
            ast_add_child(n, s);
        } while (match(p, TOK_COMMA));

        skip_newlines(p);
        if (!expect(p, TOK_FROM, "expected 'from' after import list")) {
            match(p, TOK_SEMICOLON);
            return n;
        }

        char mod_name[AST_NAME_LEN] = {0};
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name after 'from'");
        if (mod) {
            strncpy(mod_name, mod->str.buf, AST_NAME_LEN - 1);
            while (match(p, TOK_DOT)) {
                const vir_token_t *part = expect(p, TOK_IDENT, "expected path segment after '.'");
                if (!part) break;
                strncat(mod_name, ".", AST_NAME_LEN - strlen(mod_name) - 1);
                strncat(mod_name, part->str.buf, AST_NAME_LEN - strlen(mod_name) - 1);
            }
            strncpy(n->name, mod_name, AST_NAME_LEN - 1);
        }

        if (match(p, TOK_AS)) {
            const vir_token_t *alias = expect(p, TOK_IDENT, "expected alias after 'as'");
            if (alias) strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
        }
        match(p, TOK_SEMICOLON);
        return n;
    }

    case TOK_FROM: {
        /* Legacy compatibility only: from MODULE import SYM1, SYM2, ... */
        advance(p);
        char mod_name[AST_NAME_LEN] = {0};
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name after from");
        if (!mod) return NULL;
        strncpy(mod_name, mod->str.buf, AST_NAME_LEN - 1);
        while (match(p, TOK_DOT)) {
            const vir_token_t *part = expect(p, TOK_IDENT, "expected path segment after '.'");
            if (!part) break;
            strncat(mod_name, ".", AST_NAME_LEN - strlen(mod_name) - 1);
            strncat(mod_name, part->str.buf, AST_NAME_LEN - strlen(mod_name) - 1);
        }
        if (!expect(p, TOK_IMPORT, "expected 'import' after module name"))
            return NULL;
        ast_node_t *n = ast_new(AST_IMPORT);
        strncpy(n->name, mod_name, AST_NAME_LEN - 1);
        n->line = t->line;
        do {
            const vir_token_t *sym = expect(p, TOK_IDENT, "expected symbol name");
            if (!sym) break;
            ast_node_t *s = ast_new(AST_IDENTIFIER);
            strncpy(s->name, sym->str.buf, AST_NAME_LEN - 1);
            s->line = sym->line;
            ast_add_child(n, s);
        } while (match(p, TOK_COMMA));
        match(p, TOK_SEMICOLON);
        return n;
    }

    case TOK_MODULE: {
        advance(p);
        char mod_name[AST_NAME_LEN] = {0};
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name");
        if (!mod) return NULL;
        strncpy(mod_name, mod->str.buf, AST_NAME_LEN - 1);
        while (match(p, TOK_DOT)) {
            const vir_token_t *part = expect(p, TOK_IDENT, "expected path segment after '.'");
            if (!part) break;
            strncat(mod_name, ".", AST_NAME_LEN - strlen(mod_name) - 1);
            strncat(mod_name, part->str.buf, AST_NAME_LEN - strlen(mod_name) - 1);
        }
        ast_node_t *n = ast_new(AST_MODULE);
        strncpy(n->name, mod_name, AST_NAME_LEN - 1);
        n->line = t->line;
        match(p, TOK_SEMICOLON);
        return n;
    }
    case TOK_EXPORT: {
        advance(p);
        const vir_token_t *fn = expect(p, TOK_IDENT, "expected symbol name after export");
        if (!fn) return NULL;
        ast_node_t *n = ast_new(AST_EXPORT);
        strncpy(n->name, fn->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        while (match(p, TOK_COMMA)) {
            const vir_token_t *extra = expect(p, TOK_IDENT, "expected symbol name after ','");
            if (!extra) break;
            ast_node_t *s = ast_new(AST_IDENTIFIER);
            strncpy(s->name, extra->str.buf, AST_NAME_LEN - 1);
            s->line = extra->line;
            ast_add_child(n, s);
        }
        match(p, TOK_SEMICOLON);
        return n;
    }
    case TOK_INCLUDE: {
        advance(p);
        ast_node_t *n = ast_new(AST_INCLUDE);
        n->line = t->line;

        if (check(p, TOK_STRING)) {
            const vir_token_t *file = expect(p, TOK_STRING, "expected filename after include");
            if (!file) return NULL;
            strncpy(n->name, file->str.buf, AST_NAME_LEN - 1);
        } else if (is_ident_like(p)) {
            char path[AST_NAME_LEN] = {0};
            size_t pos = 0;
            const vir_token_t *id = expect_ident(p, "expected module path after include");
            if (!id) return NULL;
            pos += snprintf(path + pos, sizeof(path) - pos, "%s", id->str.buf);
            while (match(p, TOK_DOT)) {
                const vir_token_t *part = expect_ident(p, "expected path segment after '.'");
                if (!part) break;
                pos += snprintf(path + pos, sizeof(path) - pos, "/%s", part->str.buf);
            }
            snprintf(path + pos, sizeof(path) - pos, ".vri");
            strncpy(n->name, path, AST_NAME_LEN - 1);
        } else {
            parse_error(p, "expected filename or module path after include");
            ast_free(n);
            return NULL;
        }

        if (match(p, TOK_AS)) {
            const vir_token_t *alias = expect(p, TOK_IDENT, "expected alias after include path");
            if (alias) strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
        }
        match(p, TOK_SEMICOLON);
        return n;
    }

    case TOK_TYPE_KW: {
        /* type name; — or type name: ... end */
        advance(p);
        const vir_token_t *name = expect(p, TOK_IDENT, "expected type name after 'type'");
        if (!name) return NULL;
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

    case TOK_HAS: {
        /* has funcName — forward declaration */
        advance(p);
        const vir_token_t *fn = expect(p, TOK_IDENT, "expected function name after 'has'");
        if (!fn) return NULL;
        ast_node_t *n = ast_new(AST_HAS_DECL);
        strncpy(n->name, fn->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        match(p, TOK_SEMICOLON);
        return n;
    }

    case TOK_IDENT: {
        /* Could be: assignment, index assign, field assign, or expression */
        advance(p);

        /* Check for :: enum access in statement position */
        if (check(p, TOK_COLONCOLON)) {
            /* Back up and parse as expression */
            p->pos--;
            ast_node_t *expr = parse_expr(p);
            match(p, TOK_SEMICOLON);
            return expr;
        }

        if (check(p, TOK_ASSIGN)) {
            advance(p);
            ast_node_t *assign = ast_new(AST_ASSIGN);
            strncpy(assign->name, t->str.buf, AST_NAME_LEN - 1);
            assign->line = t->line;
            ast_node_t *val = parse_expr(p);
            if (val) ast_add_child(assign, val);
            match(p, TOK_SEMICOLON);
            return assign;
        }
        if (check(p, TOK_DOT)) {
            advance(p);
            const vir_token_t *field = expect(p, TOK_IDENT, "expected field name");
            if (field && check(p, TOK_ASSIGN)) {
                advance(p);
                ast_node_t *val = parse_expr(p);
                ast_node_t *fa = ast_new(AST_FIELD_ASSIGN);
                strncpy(fa->name, t->str.buf, AST_NAME_LEN - 1);
                strncpy(fa->name2, field->str.buf, AST_NAME_LEN - 1);
                fa->line = t->line;
                if (val) ast_add_child(fa, val);
                match(p, TOK_SEMICOLON);
                return fa;
            }
            /* Not field assign — back up and parse as expr */
            p->pos -= 2;
            ast_node_t *expr = parse_expr(p);
            match(p, TOK_SEMICOLON);
            return expr;
        }
        if (check(p, TOK_LBRACKET)) {
            advance(p);
            ast_node_t *idx = parse_expr(p);
            expect(p, TOK_RBRACKET, "expected ']'");
            if (check(p, TOK_ASSIGN)) {
                advance(p);
                ast_node_t *val = parse_expr(p);
                ast_node_t *ia = ast_new(AST_INDEX_ASSIGN);
                strncpy(ia->name, t->str.buf, AST_NAME_LEN - 1);
                ia->line = t->line;
                if (idx) ast_add_child(ia, idx);
                if (val) ast_add_child(ia, val);
                match(p, TOK_SEMICOLON);
                return ia;
            }
            ast_node_t *acc = ast_new(AST_INDEX_ACCESS);
            strncpy(acc->name, t->str.buf, AST_NAME_LEN - 1);
            acc->line = t->line;
            if (idx) ast_add_child(acc, idx);
            match(p, TOK_SEMICOLON);
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

    case TOK_SEMICOLON:
        advance(p);
        return NULL;

    default: {
        /* Try as expression statement */
        ast_node_t *expr = parse_expr(p);
        match(p, TOK_SEMICOLON);
        return expr;
    }
    }
}

/* ═══════════════════════════════════════════════════════
 * Top-level
 * ═══════════════════════════════════════════════════════ */

void parser_init(vir_parser_t *p, const vir_token_t *tokens, uint32_t count)
{
    memset(p, 0, sizeof(*p));
    p->tokens      = tokens;
    p->token_count = count;
}

ast_node_t *parser_parse_program(vir_parser_t *p)
{
    ast_node_t *prog = ast_new(AST_PROGRAM);

    skip_newlines(p);

    while (!check(p, TOK_EOF)) {
        ast_node_t *stmt = parse_statement(p);
        if (stmt) {
            ast_add_child(prog, stmt);
        } else if (!check(p, TOK_EOF)) {
            if (p->error[0] != '\0') break;
            advance(p);
        }
        skip_newlines(p);
    }

    return prog;
}
