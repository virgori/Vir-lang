/*
 * parser.h – Vir Recursive-Descent Parser
 * =========================================
 * Consumes a token stream from the lexer and builds an AST
 * (ast_node_t from ir_lower.h).
 *
 * Grammar uses keyword-based blocks: thì/then … hết/end
 */

#ifndef VIR_PARSER_H
#define VIR_PARSER_H

#include "lexer.h"
#include "ir_lower.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Parser State
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    const vir_token_t *tokens;
    uint32_t           token_count;
    uint32_t           pos;
    char               error[256];
    uint32_t           error_line;
    uint32_t           file_id;
    int                in_for_range_start;
} vir_parser_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialise parser with token array from lexer. */
void parser_init(vir_parser_t *p, const vir_token_t *tokens, uint32_t count, uint32_t file_id);

/* Parse full program → AST_PROGRAM node.
 * Returns NULL on fatal error (check p->error). */
ast_node_t *parser_parse_program(vir_parser_t *p);

#ifdef __cplusplus
}
#endif

#endif /* VIR_PARSER_H */
