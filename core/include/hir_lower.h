#ifndef VIR_HIR_LOWER_H
#define VIR_HIR_LOWER_H

#include "ir_lower.h" // For ast_node_t
#include "hir.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Lower an AST node (usually a statement, expression, or function body)
 * into a HIR node. This is the first pass of the modern compiler backend.
 */
hir_node_t* lower_ast_to_hir(const ast_node_t* ast, lower_ctx_t *lctx);

#ifdef __cplusplus
}
#endif

#endif // VIR_HIR_LOWER_H
