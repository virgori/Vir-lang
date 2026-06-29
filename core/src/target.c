#include "target.h"
#include <stddef.h>

// Forward declarations of ARM64 hooks (to be implemented in mach_isel.c / mach_encode.c)
extern void arm64_select_instructions(struct target_info_t *target, lir_block_t *lir_block, mach_block_t *mach_block);
extern int arm64_encode_block(struct target_info_t *target, mach_block_t *mach_block, uint8_t *buffer, size_t max_size);

static target_info_t target_arm64 = {
    .name = "arm64-apple-darwin",
    .pointer_size = 8,
    .endianness = ENDIAN_LITTLE,
    .stack_alignment = 16,
    .hooks = {
        .select_instructions = arm64_select_instructions,
        .encode_block = arm64_encode_block
    }
};

const target_info_t* target_get_host(void) {
    // We assume the host is ARM64 (Apple Silicon) for Phase 10 prototyping.
    return &target_arm64;
}
