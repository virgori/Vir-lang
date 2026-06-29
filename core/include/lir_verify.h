#ifndef VIR_LIR_VERIFY_H
#define VIR_LIR_VERIFY_H

#include "lir.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Verifies that the LIR function is in a valid machine state.
// Asserts that no Virtual Registers remain, all Stack Offsets are valid,
// and physical registers are used correctly.
// Returns true if the function is valid, false otherwise.
bool lir_verify_machine_state(lir_func_t *func);

#ifdef __cplusplus
}
#endif

#endif // VIR_LIR_VERIFY_H
