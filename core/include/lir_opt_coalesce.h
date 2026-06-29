#ifndef VIR_LIR_OPT_COALESCE_H
#define VIR_LIR_OPT_COALESCE_H

#include "lir.h"

#ifdef __cplusplus
extern "C" {
#endif

// Performs move coalescing and peephole optimizations on LIR after register allocation
// and rewriting. Eliminates redundant MOVs (e.g., MOV R1, R1).
void lir_opt_coalesce(lir_func_t *func);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_OPT_COALESCE_H
