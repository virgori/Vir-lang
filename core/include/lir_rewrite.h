#ifndef VIR_LIR_REWRITE_H
#define VIR_LIR_REWRITE_H

#include "lir.h"
#include "lir_analysis.h"

#ifdef __cplusplus
extern "C" {
#endif

// Rewrites LIR operands using the allocation map in lir_interval_ctx_t.
// Automatically inserts Spill/Reload instructions using the scratch pool.
void lir_rewrite_operands(lir_func_t *func, lir_interval_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_REWRITE_H
