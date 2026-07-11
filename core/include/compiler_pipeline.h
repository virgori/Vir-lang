#ifndef VIR_COMPILER_PIPELINE_H
#define VIR_COMPILER_PIPELINE_H

#include "ir_lower.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Returns 1 when the HIR/MIR/LIR pipeline should be used (default). */
int pipeline_enabled(void);

/*
 * Lower a function body AST through HIR -> MIR -> MIR opts -> LIR -> regalloc
 * -> Q-IR, appending to ctx->current_func.
 * Returns 0 on success, -1 on failure.
 */
int pipeline_lower_func_body(lower_ctx_t *ctx, const ast_node_t *body_ast,
                             uint32_t func_id);

#ifdef __cplusplus
}
#endif

#endif /* VIR_COMPILER_PIPELINE_H */
