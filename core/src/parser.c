/*
 * parser.c – Vir Recursive-Descent Parser
 * =========================================
 * Produces ast_node_t trees from a token stream (vir_token_t[]).
 *
 * Grammar (keyword-delimited blocks):
 *
 *   program     → (func_def | statement)* EOF
 *   func_def    → FUNC IDENT '(' params ')' THEN block END
 *   params      → (IDENT (',' IDENT)*)?
 *   block       → statement*
 *   statement   → var_decl | const_decl | if_stmt | loop_stmt
 *               | while_stmt | return_stmt | print_stmt
 *               | assign_or_expr | NEWLINE
 *   var_decl    → VAR IDENT '=' expr
 *   const_decl  → CONST IDENT '=' expr
 *   if_stmt     → IF expr THEN block (ELIF expr THEN block)* (ELSE block)? END
 *   loop_stmt   → LOOP expr THEN block END
 *   while_stmt  → WHILE expr THEN block END
 *   return_stmt → RETURN expr?
 *   print_stmt  → PRINT expr
 *   assign_or_expr → IDENT '=' expr  |  expr
 *   expr        → or_expr
 *   or_expr     → and_expr (OR and_expr)*
 *   and_expr    → compare (AND compare)*
 *   compare     → addition ((EQ|NE|GT|LT|GE|LE) addition)?
 *   addition    → mult ((PLUS|MINUS) mult)*
 *   mult        → unary ((STAR|SLASH|PERCENT) unary)*
 *   unary       → (MINUS|NOT) unary | call
 *   call        → primary ('(' args ')')?
 *   primary     → INT | FLOAT | STRING | TRUE | FALSE | NONE
 *               | IDENT | '(' expr ')' | INPUT
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

/* Check if token could start a statement */
static int is_stmt_start(vir_tok_t t)
{
    return t == TOK_VAR || t == TOK_CONST || t == TOK_IF ||
           t == TOK_LOOP || t == TOK_WHILE || t == TOK_FOR ||
           t == TOK_RETURN || t == TOK_OUT || t == TOK_PRINT || t == TOK_INPUT ||
           t == TOK_IDENT || t == TOK_INT || t == TOK_FLOAT ||
           t == TOK_STRING || t == TOK_LPAREN || t == TOK_MINUS ||
           t == TOK_NOT || t == TOK_CHECK_CPU || t == TOK_PATCH ||
           t == TOK_FUNC || t == TOK_BREAK || t == TOK_CONTINUE ||
           t == TOK_TRUE || t == TOK_FALSE || t == TOK_LBRACKET ||
           t == TOK_ENUM || t == TOK_RECORD || t == TOK_ENTITY ||
           t == TOK_IMPORT || t == TOK_FROM || t == TOK_MODULE ||
           t == TOK_EXPORT || t == TOK_INCLUDE;
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

/* Forward - we need this for record literal parsing */
static int check_record_literal(vir_parser_t *p);

/* Check if current '{' starts a record literal (lookahead: '{' IDENT ':') */
static int check_record_literal(vir_parser_t *p)
{
    /* We're at '{', check if next tokens are IDENT ':' or '}' */
    uint32_t save = p->pos;
    if (p->pos < p->token_count && p->tokens[p->pos].type == TOK_LBRACE) {
        uint32_t next = save + 1;
        /* Empty record literal */
        if (next < p->token_count && p->tokens[next].type == TOK_RBRACE)
            return 1;
        /* IDENT : pattern */
        if (next + 1 < p->token_count &&
            p->tokens[next].type == TOK_IDENT &&
            p->tokens[next + 1].type == TOK_COLON)
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
    case TOK_IDENT: {
        advance(p);
        /* Check for record literal: IDENT '{' field: val, ... '}' */
        if (check(p, TOK_LBRACE) && check_record_literal(p)) {
            advance(p);  /* consume '{' */
            ast_node_t *rl = ast_new(AST_RECORD_LITERAL);
            strncpy(rl->name, t->str.buf, AST_NAME_LEN - 1);
            rl->line = t->line;
            while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
                /* Parse field_name : expr */
                const vir_token_t *fname = expect(p, TOK_IDENT, "expected field name");
                if (!fname) break;
                expect(p, TOK_COLON, "expected ':' after field name");
                ast_node_t *val = parse_expr(p);
                if (val) {
                    /* Store field name in the value node's name2 */
                    strncpy(val->name2, fname->str.buf, AST_NAME_LEN - 1);
                    ast_add_child(rl, val);
                }
                match(p, TOK_COMMA);
                skip_newlines(p);
            }
            expect(p, TOK_RBRACE, "expected '}' after record literal");
            return rl;
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
            strncpy(call->name, t->str.buf, AST_NAME_LEN - 1);
            call->line = t->line;
            advance(p);  /* consume '(' */

            /* Parse arguments */
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
        /* Check for index access: IDENT '[' expr ']' */
        if (check(p, TOK_LBRACKET)) {
            advance(p);  /* consume '[' */
            ast_node_t *idx = parse_expr(p);
            expect(p, TOK_RBRACKET, "expected ']' after index");
            ast_node_t *access = ast_new(AST_INDEX_ACCESS);
            strncpy(access->name, t->str.buf, AST_NAME_LEN - 1);
            access->line = t->line;
            ast_add_child(access, idx);
            return access;
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
    default:
        parse_error(p, "expected expression");
        return NULL;
    }
}

static ast_node_t *parse_unary(vir_parser_t *p)
{
    if (check(p, TOK_MINUS)) {
        const vir_token_t *t = advance(p);
        ast_node_t *operand = parse_unary(p);
        if (!operand) return NULL;

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
        if (!operand) return NULL;

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
    /* Postfix: field access via '.' on the result of primary */
    ast_node_t *left = parse_primary(p);
    if (!left) return NULL;
    while (check(p, TOK_DOT)) {
        advance(p);  /* consume '.' */
        const vir_token_t *field = expect(p, TOK_IDENT, "expected field name after '.'");
        if (!field) break;
        ast_node_t *fa = ast_new(AST_FIELD_ACCESS);
        strncpy(fa->name, field->str.buf, AST_NAME_LEN - 1);
        fa->line = field->line;
        ast_add_child(fa, left);
        left = fa;
    }
    return left;
}

static ast_node_t *parse_mult(vir_parser_t *p)
{
    ast_node_t *left = parse_unary(p);
    if (!left) return NULL;

    while (check(p, TOK_STAR) || check(p, TOK_SLASH) || check(p, TOK_PERCENT)) {
        const vir_token_t *op_tok = advance(p);
        ast_op_t op;
        switch (op_tok->type) {
        case TOK_STAR:    op = OP_MUL; break;
        case TOK_SLASH:   op = OP_DIV; break;
        case TOK_PERCENT: op = OP_MOD; break;
        default:          op = OP_MUL; break;
        }

        ast_node_t *right = parse_unary(p);
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

static ast_node_t *parse_compare(vir_parser_t *p)
{
    ast_node_t *left = parse_bitwise(p);
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

        ast_node_t *right = parse_addition(p);
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
           !check(p, TOK_ELIF) && !check(p, TOK_EIF) && !check(p, TOK_EOF)) {
        ast_node_t *stmt = parse_statement(p);
        if (stmt) {
            ast_add_child(block, stmt);
        } else {
            /* Avoid infinite loop on unrecoverable error */
            if (p->error[0] != '\0') break;
            advance(p);
        }
        skip_newlines(p);
    }

    return block;
}

static ast_node_t *parse_var_decl(vir_parser_t *p, ast_type_t type)
{
    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected variable name");
    if (!name_tok) return NULL;

    ast_node_t *decl = ast_new(type);
    strncpy(decl->name, name_tok->str.buf, AST_NAME_LEN - 1);
    decl->line = name_tok->line;

    if (match(p, TOK_ASSIGN)) {
        ast_node_t *init = parse_expr(p);
        if (init) ast_add_child(decl, init);
    }
    return decl;
}

static ast_node_t *parse_if_stmt(vir_parser_t *p)
{
    /* IF expr THEN block (ELIF expr THEN block)* (ELSE block)? END */
    uint32_t line = peek(p)->line;

    ast_node_t *cond = parse_expr(p);
    if (!cond) return NULL;

    expect(p, TOK_THEN, "expected 'thì'/'then' after condition");

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
        if (elif_as_if) ast_add_child(else_block, elif_as_if);
        ast_add_child(if_node, else_block);
        /* The nested if_stmt consumes its own END */
        return if_node;
    }

    /* Handle ELSE */
    if (match(p, TOK_ELSE)) {
        skip_newlines(p);
        /* Check if ELSE is followed by THEN (optional) */
        match(p, TOK_THEN);
        ast_node_t *else_block = parse_block(p);
        ast_add_child(if_node, else_block);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after if block");
    return if_node;
}

static ast_node_t *parse_loop_stmt(vir_parser_t *p)
{
    /* LOOP expr THEN block END */
    uint32_t line = peek(p)->line;

    ast_node_t *count = parse_expr(p);
    if (!count) return NULL;

    expect(p, TOK_THEN, "expected 'thì'/'then' after loop count");

    ast_node_t *body = parse_block(p);

    expect(p, TOK_END, "expected 'hết'/'end' after loop block");

    ast_node_t *n = ast_new(AST_LOOP);
    n->line = line;
    ast_add_child(n, count);
    ast_add_child(n, body);
    return n;
}

static ast_node_t *parse_while_stmt(vir_parser_t *p)
{
    /* WHILE expr THEN block END */
    uint32_t line = peek(p)->line;

    ast_node_t *cond = parse_expr(p);
    if (!cond) return NULL;

    expect(p, TOK_THEN, "expected 'thì'/'then' after while condition");

    ast_node_t *body = parse_block(p);

    expect(p, TOK_END, "expected 'hết'/'end' after while block");

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

    /* Optional return value */
    if (!check(p, TOK_NEWLINE) && !check(p, TOK_END) &&
        !check(p, TOK_EOF) && !check(p, TOK_ELSE)) {
        ast_node_t *val = parse_expr(p);
        if (val) ast_add_child(n, val);
    }
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

static ast_node_t *parse_func_def(vir_parser_t *p)
{
    /* FUNC IDENT '(' params ')' THEN block END */
    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected function name");
    if (!name_tok) return NULL;

    ast_node_t *fn = ast_new(AST_FUNC_DEF);
    strncpy(fn->name, name_tok->str.buf, AST_NAME_LEN - 1);
    fn->line = name_tok->line;

    expect(p, TOK_LPAREN, "expected '(' after function name");

    /* Parse parameters → stored as IDENTIFIER children */
    if (!check(p, TOK_RPAREN)) {
        const vir_token_t *param_tok = expect(p, TOK_IDENT, "expected parameter name");
        if (param_tok) {
            ast_node_t *param = ast_new(AST_IDENTIFIER);
            strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
            ast_add_child(fn, param);
        }
        while (match(p, TOK_COMMA)) {
            param_tok = expect(p, TOK_IDENT, "expected parameter name");
            if (param_tok) {
                ast_node_t *param = ast_new(AST_IDENTIFIER);
                strncpy(param->name, param_tok->str.buf, AST_NAME_LEN - 1);
                ast_add_child(fn, param);
            }
        }
    }

    expect(p, TOK_RPAREN, "expected ')' after parameters");
    expect(p, TOK_THEN, "expected 'thì'/'then' after function signature");

    ast_node_t *body = parse_block(p);
    ast_add_child(fn, body);  /* Last child = body block */

    expect(p, TOK_END, "expected 'hết'/'end' to close function");
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

static ast_node_t *parse_for_range_stmt(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *var_tok = expect(p, TOK_IDENT, "expected loop variable");
    if (!var_tok) return NULL;

    if (!expect(p, TOK_IN, "expected 'in'/'trong' after for variable"))
        return NULL;

    /* Parse start expression */
    ast_node_t *start = parse_expr(p);
    if (!start) return NULL;

    if (!expect(p, TOK_DOTDOT, "expected '..' in range"))
        return NULL;

    /* Parse end expression */
    ast_node_t *end_expr = parse_expr(p);
    if (!end_expr) { ast_free(start); return NULL; }

    expect(p, TOK_THEN, "expected 'thì'/'then' after for range");

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

static ast_node_t *parse_enum_def(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected enum name");
    if (!name_tok) return NULL;

    expect(p, TOK_THEN, "expected 'thì'/'then' after enum name");
    skip_newlines(p);

    ast_node_t *en = ast_new(AST_ENUM_DEF);
    strncpy(en->name, name_tok->str.buf, AST_NAME_LEN - 1);
    en->line = line;

    int64_t next_val = 0;  /* auto-increment if no explicit value */

    while (!check(p, TOK_END) && !check(p, TOK_EOF)) {
        const vir_token_t *vname = expect(p, TOK_IDENT, "expected enum variant name");
        if (!vname) break;

        int64_t val = next_val;
        if (match(p, TOK_ASSIGN)) {
            /* Explicit value */
            const vir_token_t *vt = expect(p, TOK_INT, "expected integer value");
            if (vt) val = vt->int_val;
        }
        next_val = val + 1;

        ast_node_t *variant = ast_new(AST_LITERAL_INT);
        strncpy(variant->name, vname->str.buf, AST_NAME_LEN - 1);
        variant->int_val = val;
        variant->line = vname->line;
        ast_add_child(en, variant);

        skip_newlines(p);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after enum definition");
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

static ast_node_t *parse_record_def(vir_parser_t *p)
{
    uint32_t line = peek(p)->line;

    const vir_token_t *name_tok = expect(p, TOK_IDENT, "expected record name");
    if (!name_tok) return NULL;

    /* 'then' is optional — required for 'record', omitted for 'entity' */
    match(p, TOK_THEN);
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

        /* Optional type hint: field_name: type
         * Skip complex types like [i32], Vec<Token>, etc. until newline */
        if (match(p, TOK_COLON)) {
            while (!check(p, TOK_NEWLINE) && !check(p, TOK_END) &&
                   !check(p, TOK_EOF)) {
                advance(p);
            }
        }

        ast_add_child(rec, field);
        skip_newlines(p);
    }

    expect(p, TOK_END, "expected 'hết'/'end' after record definition");
    return rec;
}

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

    case TOK_FOR:
        advance(p);
        return parse_for_range_stmt(p);

    case TOK_ENUM:
        advance(p);
        return parse_enum_def(p);

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
        return n;
    }
    case TOK_CONTINUE: {
        advance(p);
        ast_node_t *n = ast_new(AST_CONTINUE);
        n->line = t->line;
        return n;
    }

    case TOK_IMPORT: {
        /* import MODULE   or   import MODULE as ALIAS */
        advance(p);
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name after import");
        if (!mod) return NULL;
        ast_node_t *n = ast_new(AST_IMPORT);
        strncpy(n->name, mod->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        if (match(p, TOK_AS)) {
            const vir_token_t *alias = expect(p, TOK_IDENT, "expected alias after 'as'");
            if (alias) strncpy(n->name2, alias->str.buf, AST_NAME_LEN - 1);
        }
        return n;
    }
    case TOK_FROM: {
        /* from MODULE import SYM1, SYM2, ... */
        advance(p);
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name after from");
        if (!mod) return NULL;
        if (!expect(p, TOK_IMPORT, "expected 'import' after module name"))
            return NULL;
        ast_node_t *n = ast_new(AST_IMPORT);
        strncpy(n->name, mod->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        /* Parse imported symbols as children (AST_IDENTIFIER nodes) */
        do {
            const vir_token_t *sym = expect(p, TOK_IDENT, "expected symbol name");
            if (!sym) break;
            ast_node_t *s = ast_new(AST_IDENTIFIER);
            strncpy(s->name, sym->str.buf, AST_NAME_LEN - 1);
            s->line = sym->line;
            ast_add_child(n, s);
        } while (match(p, TOK_COMMA));
        return n;
    }
    case TOK_MODULE: {
        /* module NAME */
        advance(p);
        const vir_token_t *mod = expect(p, TOK_IDENT, "expected module name");
        if (!mod) return NULL;
        ast_node_t *n = ast_new(AST_MODULE);
        strncpy(n->name, mod->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        return n;
    }
    case TOK_EXPORT: {
        /* export FUNC_NAME */
        advance(p);
        const vir_token_t *fn = expect(p, TOK_IDENT, "expected function name after export");
        if (!fn) return NULL;
        ast_node_t *n = ast_new(AST_EXPORT);
        strncpy(n->name, fn->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
        return n;
    }
    case TOK_INCLUDE: {
        /* include "filename" */
        advance(p);
        const vir_token_t *file = expect(p, TOK_STRING, "expected filename after include");
        if (!file) return NULL;
        ast_node_t *n = ast_new(AST_INCLUDE);
        strncpy(n->name, file->str.buf, AST_NAME_LEN - 1);
        n->line = t->line;
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

    case TOK_IDENT: {
        /* Could be: assignment, index assign, field assign, or expression */
        advance(p);
        if (check(p, TOK_ASSIGN)) {
            advance(p);  /* consume '=' */
            ast_node_t *assign = ast_new(AST_ASSIGN);
            strncpy(assign->name, t->str.buf, AST_NAME_LEN - 1);
            assign->line = t->line;
            ast_node_t *val = parse_expr(p);
            if (val) ast_add_child(assign, val);
            return assign;
        }
        if (check(p, TOK_DOT)) {
            /* Field assign: IDENT '.' FIELD_NAME '=' expr */
            advance(p);  /* consume '.' */
            const vir_token_t *field = expect(p, TOK_IDENT, "expected field name");
            if (field && check(p, TOK_ASSIGN)) {
                advance(p);  /* consume '=' */
                ast_node_t *val = parse_expr(p);
                ast_node_t *fa = ast_new(AST_FIELD_ASSIGN);
                strncpy(fa->name, t->str.buf, AST_NAME_LEN - 1);
                strncpy(fa->name2, field->str.buf, AST_NAME_LEN - 1);
                fa->line = t->line;
                if (val) ast_add_child(fa, val);
                return fa;
            }
            /* Not field assign - back up to before '.' and parse as expr */
            p->pos -= 2;  /* back before field and dot */
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
                if (idx) ast_add_child(ia, idx);
                if (val) ast_add_child(ia, val);
                return ia;
            }
            /* If not followed by '=', it's an index access expression statement */
            ast_node_t *acc = ast_new(AST_INDEX_ACCESS);
            strncpy(acc->name, t->str.buf, AST_NAME_LEN - 1);
            acc->line = t->line;
            if (idx) ast_add_child(acc, idx);
            return acc;
        }
        /* Back up and parse as expression */
        p->pos--;
        ast_node_t *expr = parse_expr(p);
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
        return parse_expr(p);
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
            /* Avoid infinite loop on unrecoverable error */
            if (p->error[0] != '\0') break;
            advance(p);
        }
        skip_newlines(p);
    }

    return prog;
}
