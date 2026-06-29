#ifndef VIR_MIR_MOVE_RESOLVER_H
#define VIR_MIR_MOVE_RESOLVER_H

#include "mir.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Represents a single logical move: src -> dst
typedef struct {
    mir_operand_t src;
    uint32_t dst_vreg;
} mir_move_intent_t;

// A context for resolving parallel moves into sequential moves
typedef struct {
    mir_move_intent_t* moves;
    uint32_t count;
    uint32_t capacity;
    
    // Internal states for cycle detection
    uint8_t* status; // 0=unvisited, 1=visiting, 2=visited
} mir_move_resolver_t;

void mir_move_resolver_init(mir_move_resolver_t* resolver);
void mir_move_resolver_add(mir_move_resolver_t* resolver, mir_operand_t src, uint32_t dst_vreg);

// Resolves the added moves and appends sequential MIR instructions to the specified block.
// The instructions are inserted at the end of the block, but BEFORE the block's terminator.
void mir_move_resolver_emit(mir_move_resolver_t* resolver, mir_func_t* func, mir_block_t* block);

void mir_move_resolver_destroy(mir_move_resolver_t* resolver);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_MOVE_RESOLVER_H
