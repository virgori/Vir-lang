#ifndef VIR_COMPILER_PIPELINE_H
#define VIR_COMPILER_PIPELINE_H

#include "ir_lower.h"
#include "borrow_check.h"

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

/*
 * §4.8: Run Q-IR borrow checker (NLL + IPA) on the module after lowering.
 * On success, inserts drop points (Q_FREE). Returns 0 if clean, -1 on errors.
 * Set VIR_NO_BORROW_CHECK=1 to skip (bootstrap escape hatch).
 */
int pipeline_borrow_check(lower_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif /* VIR_COMPILER_PIPELINE_H */
