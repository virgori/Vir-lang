#include "mir_pass.h"
#include "mir_move_resolver.h"
#include <stdlib.h>

static mir_block_t* create_block_for_edge(mir_func_t* func, mir_block_t* pred, mir_block_t* succ) {
    mir_block_t* new_block = (mir_block_t*)malloc(sizeof(mir_block_t));
    new_block->id = ++func->next_block_id;
    new_block->head = NULL;
    new_block->tail = NULL;
    new_block->phis = NULL;
    new_block->succ_true = succ;
    new_block->succ_false = NULL;
    
    // Insert into func->blocks
    mir_block_t* curr = func->blocks;
    while (curr && curr->next_block) curr = curr->next_block;
    if (curr) curr->next_block = new_block;
    else func->blocks = new_block;
    new_block->next_block = NULL;
    
    // Create unconditional jump
    mir_instr_t* jmp = (mir_instr_t*)malloc(sizeof(mir_instr_t));
    jmp->op = MIR_JUMP;
    jmp->dst.type = MIR_OPND_BLOCK;
    jmp->dst.as.block_id = succ->id;
    jmp->src1.type = MIR_OPND_NONE;
    jmp->src2.type = MIR_OPND_NONE;
    jmp->next = NULL;
    
    
    new_block->head = jmp;
    new_block->tail = jmp;
    
    return new_block;
}

static void split_critical_edges(mir_func_t* func) {
    mir_block_t* block = func->blocks;
    while (block) {
        if (block->phis) {
            for (uint32_t i = 0; i < block->pred_count; i++) {
                mir_block_t* pred = block->preds[i];
                if (pred->succ_true && pred->succ_false) {
                    // Pred has multiple successors, block has multiple predecessors (since it has phis). Critical edge!
                    mir_block_t* edge_block = create_block_for_edge(func, pred, block);
                    
                    if (pred->succ_true == block) pred->succ_true = edge_block;
                    if (pred->succ_false == block) pred->succ_false = edge_block;
                    
                    // Update jump instructions in pred
                    mir_instr_t* tail = pred->tail;
                    if (tail && (tail->op == MIR_JUMP || tail->op == MIR_JUMP_IF)) {
                        if (tail->dst.type == MIR_OPND_BLOCK && tail->dst.as.block_id == block->id) {
                            tail->dst.as.block_id = edge_block->id;
                        }
                    }
                    
                    // Update phi blocks
                    mir_phi_t* phi = block->phis;
                    while (phi) {
                        for (uint32_t j = 0; j < phi->incoming_count; j++) {
                            if (phi->incoming_blocks[j] == pred) {
                                phi->incoming_blocks[j] = edge_block;
                            }
                        }
                        phi = phi->next;
                    }
                }
            }
        }
        block = block->next_block;
    }
}

void mir_pass_ssa_destruct_run(mir_func_t* func) {
    if (!func) return;
    
    // 1. Split critical edges
    split_critical_edges(func);
    
    // 2. Rebuild CFG to ensure preds are correct after splitting
    // Note: since we already updated incoming_blocks, we can rely on that for resolution.
    
    // 3. Resolve Phis into Moves using the Move Resolver to solve Parallel Copies!
    // Since phis in a block conceptually execute in parallel, the values from a specific predecessor
    // must be emitted as a set of parallel moves at the end of that predecessor block.
    
    // For each block, for each predecessor, build a set of moves
    mir_block_t* b = func->blocks;
    while (b) {
        if (b->phis) {
            for (uint32_t i = 0; i < b->pred_count; i++) {
                mir_block_t* pred = b->preds[i];
                
                mir_move_resolver_t resolver;
                mir_move_resolver_init(&resolver);
                
                mir_phi_t* phi = b->phis;
                while (phi) {
                    for (uint32_t j = 0; j < phi->incoming_count; j++) {
                        if (phi->incoming_blocks[j] == pred) {
                            mir_move_resolver_add(&resolver, phi->incoming_values[j], phi->dst_vreg);
                            break;
                        }
                    }
                    phi = phi->next;
                }
                
                mir_move_resolver_emit(&resolver, func, pred);
                mir_move_resolver_destroy(&resolver);
            }
        }
        b = b->next_block;
    }
    
    // 4. Delete all Phis
    b = func->blocks;
    while (b) {
        mir_phi_t* phi = b->phis;
        while (phi) {
            mir_phi_t* next = phi->next;
            if (phi->incoming_values) free(phi->incoming_values);
            if (phi->incoming_blocks) free(phi->incoming_blocks);
            free(phi);
            phi = next;
        }
        b->phis = NULL;
        b = b->next_block;
    }
}
