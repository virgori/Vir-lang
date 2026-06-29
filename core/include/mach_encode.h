#ifndef VIR_MACH_ENCODE_H
#define VIR_MACH_ENCODE_H

#include <stdint.h>
#include <stddef.h>
#include "mach_ir.h"
#include "target.h"

#ifdef __cplusplus
extern "C" {
#endif

// Runs the Binary Encoder on a MachIR function.
// Writes the encoded bytes into the provided buffer.
// Returns the number of bytes written, or -1 on error.
int mach_encode_func(const target_info_t *target, mach_func_t *mach_func, uint8_t *buffer, size_t max_size);

#ifdef __cplusplus
}
#endif

#endif // VIR_MACH_ENCODE_H
