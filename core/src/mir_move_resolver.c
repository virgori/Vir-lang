#include "mir_move_resolver.h"
#include <stdlib.h>
#include <string.h>

void mir_move_resolver_init(mir_move_resolver_t* resolver) {
    if (!resolver) return;
    resolver->count = 0;
    resolver->capacity = 16;
    resolver->moves = (mir_move_intent_t*)malloc(sizeof(mir_move_intent_t) * resolver->capacity);
    resolver->status = NULL;
}

void mir_move_resolver_add(mir_move_resolver_t* resolver, mir_operand_t src, uint32_t dst_vreg) {
    if (!resolver) return;
    
    // Ignore self-moves (e.g. v1 -> v1)
    if (src.type == MIR_OPND_VREG && src.as.vreg == dst_vreg) return;
    
    if (resolver->count >= resolver->capacity) {
        resolver->capacity *= 2;
        resolver->moves = (mir_move_intent_t*)realloc(resolver->moves, sizeof(mir_move_intent_t) * resolver->capacity);
    }
    resolver->moves[resolver->count].src = src;
    resolver->moves[resolver->count].dst_vreg = dst_vreg;
    resolver->count++;
}

// Emits a single move instruction just before the terminator
static void emit_move(mir_func_t* func, mir_block_t* block, mir_operand_t src, uint32_t dst_vreg) {
    mir_instr_t* instr = (mir_instr_t*)malloc(sizeof(mir_instr_t));
    memset(instr, 0, sizeof(mir_instr_t));
    instr->op = MIR_MOVE;
    instr->src1 = src;
    instr->dst.type = MIR_OPND_VREG;
    instr->dst.as.vreg = dst_vreg;
    
    // Insert before terminator, or at end if no terminator
    if (!block->head) {
        block->head = instr;
        block->tail = instr;
    } else {
        mir_opcode_info_t info = mir_get_opcode_info(block->tail->op);
        if (info.is_terminator) {
            // Insert before tail
            mir_instr_t* prev = NULL;
            mir_instr_t* curr = block->head;
            while (curr != block->tail) {
                prev = curr;
                curr = curr->next;
            }
            if (prev) {
                prev->next = instr;
                instr->next = block->tail;
            } else {
                instr->next = block->head;
                block->head = instr;
            }
        } else {
            // Append
            block->tail->next = instr;
            block->tail = instr;
        }
    }
}

// DFS to resolve cycles
static void resolve_dfs(mir_move_resolver_t* resolver, uint32_t i, mir_func_t* func, mir_block_t* block) {
    resolver->status[i] = 1; // visiting
    
    mir_move_intent_t* move = &resolver->moves[i];
    
    // Dependency: Move i writes to `dst_vreg`. If Move j reads from `dst_vreg`,
    // Move j must execute before Move i.
    // So i depends on j.
    for (uint32_t j = 0; j < resolver->count; j++) {
        if (i == j) continue;
        
        mir_move_intent_t* dep = &resolver->moves[j];
        if (dep->src.type == MIR_OPND_VREG && dep->src.as.vreg == move->dst_vreg) {
            if (resolver->status[j] == 0) { // unvisited
                resolve_dfs(resolver, j, func, block);
            } else if (resolver->status[j] == 1) { // visiting -> cycle detected!
                // Break cycle: Move j reads from `dep->src`.
                // We copy `dep->src` to a new TMP, and Move j will read from TMP instead.
                uint32_t tmp_vreg = ++func->next_vreg;
                emit_move(func, block, dep->src, tmp_vreg);
                dep->src.as.vreg = tmp_vreg;
            }
        }
    }
    
    // Now safe to emit move i
    emit_move(func, block, move->src, move->dst_vreg);
    
    resolver->status[i] = 2; // visited
}

void mir_move_resolver_emit(mir_move_resolver_t* resolver, mir_func_t* func, mir_block_t* block) {
    if (!resolver || !func || !block || resolver->count == 0) return;
    
    resolver->status = (uint8_t*)calloc(resolver->count, sizeof(uint8_t));
    
    for (uint32_t i = 0; i < resolver->count; i++) {
        if (resolver->status[i] == 0) {
            resolve_dfs(resolver, i, func, block);
        }
    }
    
    free(resolver->status);
    resolver->status = NULL;
}

void mir_move_resolver_destroy(mir_move_resolver_t* resolver) {
    if (!resolver) return;
    free(resolver->moves);
    if (resolver->status) free(resolver->status);
    resolver->moves = NULL;
    resolver->capacity = 0;
    resolver->count = 0;
}
