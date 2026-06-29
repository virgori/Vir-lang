#ifndef VIR_MACH_ISEL_H
#define VIR_MACH_ISEL_H

#include "lir.h"
#include "mach_ir.h"
#include "target.h"

#ifdef __cplusplus
extern "C" {
#endif

// Runs the Instruction Selector to lower a LIR function into a MachIR function
mach_func_t* mach_select_instructions(const target_info_t *target, lir_func_t *lir_func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MACH_ISEL_H
