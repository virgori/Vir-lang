#ifndef VIR_LIR_REGALLOC_H
#define VIR_LIR_REGALLOC_H

#include "lir.h"
#include "lir_analysis.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Allocates physical registers for all virtual registers in the function.
// Rewrites the LIR instructions to use physical registers or stack slots (for spills).
// Returns true on success, false if an unrecoverable error occurred.
bool lir_allocate_registers(lir_func_t *func, lir_interval_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_REGALLOC_H
