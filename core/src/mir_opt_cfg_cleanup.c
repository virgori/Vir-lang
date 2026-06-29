#include "mir_opt.h"
#include <stdlib.h>

static void mark_reachable(mir_block_t* block, int* visited, mir_block_t** blocks, uint32_t count) {
    if (!block) return;
    
    int idx = -1;
    for (uint32_t i = 0; i < count; i++) {
        if (blocks[i] == block) { idx = i; break; }
    }
    if (idx == -1 || visited[idx]) return;
    
    visited[idx] = 1;
    mark_reachable(block->succ_true, visited, blocks, count);
    mark_reachable(block->succ_false, visited, blocks, count);
}

void mir_opt_cfg_cleanup_run(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    uint32_t block_count = 0;
    mir_block_t* curr = func->blocks;
    while (curr) { block_count++; curr = curr->next_block; }
    
    mir_block_t** blocks = (mir_block_t**)malloc(block_count * sizeof(mir_block_t*));
    curr = func->blocks;
    for (uint32_t i = 0; i < block_count; i++) { blocks[i] = curr; curr = curr->next_block; }
    
    int* visited = (int*)calloc(block_count, sizeof(int));
    
    mark_reachable(func->entry_block, visited, blocks, block_count);
    
    mir_block_t* prev = NULL;
    curr = func->blocks;
    int idx = 0;
    while (curr) {
        if (!visited[idx]) {
            // Remove block
            mir_block_t* next = curr->next_block;
            if (prev) prev->next_block = next;
            else func->blocks = next;
            
            // Free instructions
            mir_instr_t* instr = curr->head;
            while (instr) {
                mir_instr_t* ni = instr->next;
                free(instr);
                instr = ni;
            }
            
            // Free phis
            mir_phi_t* phi = curr->phis;
            while (phi) {
                mir_phi_t* np = phi->next;
                if (phi->incoming_values) free(phi->incoming_values);
                if (phi->incoming_blocks) free(phi->incoming_blocks);
                free(phi);
                phi = np;
            }
            
            if (curr->preds) free(curr->preds);
            if (curr->dom_children) free(curr->dom_children);
            if (curr->df) free(curr->df);
            
            free(curr);
            curr = next;
        } else {
            prev = curr;
            curr = curr->next_block;
        }
        idx++;
    }
    
    free(blocks);
    free(visited);
}
