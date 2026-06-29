#ifndef VIR_TARGET_H
#define VIR_TARGET_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "lir.h"
#include "mach_ir.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ENDIAN_LITTLE,
    ENDIAN_BIG
} target_endian_t;

// Forward declaration
struct target_info_t;

// Target hooks
typedef struct {
    // Instruction Selector: Lowers LIR block to MachIR block
    void (*select_instructions)(struct target_info_t *target, lir_block_t *lir_block, mach_block_t *mach_block);
    
    // Binary Encoder: Encodes a MachIR block to binary buffer
    // Returns number of bytes written, or -1 on error
    int (*encode_block)(struct target_info_t *target, mach_block_t *mach_block, uint8_t *buffer, size_t max_size);
} target_hooks_t;

typedef struct target_info_t {
    const char *name;
    uint8_t pointer_size; // in bytes (e.g. 8 for 64-bit)
    target_endian_t endianness;
    uint32_t stack_alignment; // in bytes (e.g. 16 for ARM64)
    
    target_hooks_t hooks;
} target_info_t;

// Returns the target info for the host architecture
const target_info_t* target_get_host(void);

#ifdef __cplusplus
}
#endif

#endif // VIR_TARGET_H
