#ifndef VIR_LIR_TO_QIR_H
#define VIR_LIR_TO_QIR_H

#include "ir_lower.h"
#include "lir.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Append LIR instructions from a lowered function into the current
 * Q-IR function on ctx. Used as the final stage of the HIR/MIR/LIR pipeline.
 */
int lir_to_qir_append(lower_ctx_t *ctx, const lir_func_t *lir);

#ifdef __cplusplus
}
#endif

#endif /* VIR_LIR_TO_QIR_H */
