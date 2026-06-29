#ifndef VIR_LIR_LOWER_H
#define VIR_LIR_LOWER_H

#include "mir.h"
#include "lir.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Lower a MIR function into a LIR function.
 * This is an initial draft which directly maps MIR virtual registers
 * to LIR virtual registers or stack slots. 
 */
lir_func_t* lower_mir_to_lir(const mir_func_t* mir);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_LOWER_H
