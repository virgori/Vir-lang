#include "mir_ssa.h"
#include <stdlib.h>
#include <string.h>

// Helper to find max var id
static uint32_t find_max_vreg(mir_func_t* func) {
    uint32_t max_vreg = 0;
    mir_block_t* block = func->blocks;
    while (block) {
        mir_instr_t* instr = block->head;
        while (instr) {
            if (instr->dst.type == MIR_OPND_VREG && instr->dst.as.vreg > max_vreg) max_vreg = instr->dst.as.vreg;
            if (instr->src1.type == MIR_OPND_VREG && instr->src1.as.vreg > max_vreg) max_vreg = instr->src1.as.vreg;
            if (instr->src2.type == MIR_OPND_VREG && instr->src2.as.vreg > max_vreg) max_vreg = instr->src2.as.vreg;
            instr = instr->next;
        }
        block = block->next_block;
    }
    return max_vreg;
}

void mir_insert_phi_nodes(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    uint32_t max_vreg = find_max_vreg(func);
    if (max_vreg == 0) return;
    
    uint32_t block_count = 0;
    mir_block_t* curr = func->blocks;
    while (curr) { block_count++; curr = curr->next_block; }
    
    mir_block_t** blocks = (mir_block_t**)malloc(block_count * sizeof(mir_block_t*));
    curr = func->blocks;
    for (uint32_t i = 0; i < block_count; i++) { blocks[i] = curr; curr = curr->next_block; }
    
    int* def_blocks = (int*)malloc(block_count * sizeof(int));
    int* has_phi = (int*)malloc(block_count * sizeof(int));
    int* worklist = (int*)malloc(block_count * sizeof(int));
    
    for (uint32_t v = 1; v <= max_vreg; v++) {
        memset(def_blocks, 0, block_count * sizeof(int));
        memset(has_phi, 0, block_count * sizeof(int));
        
        int head = 0, tail = 0;
        
        // Find defining blocks
        for (uint32_t i = 0; i < block_count; i++) {
            mir_block_t* b = blocks[i];
            int defined = 0;
            mir_instr_t* instr = b->head;
            while (instr) {
                if (instr->dst.type == MIR_OPND_VREG && instr->dst.as.vreg == v) {
                    defined = 1;
                    break;
                }
                instr = instr->next;
            }
            if (defined) {
                def_blocks[i] = 1;
                worklist[tail++] = i;
            }
        }
        
        // Compute IDF
        while (head < tail) {
            int x = worklist[head++];
            mir_block_t* b = blocks[x];
            for (uint32_t j = 0; j < b->df_count; j++) {
                mir_block_t* y = b->df[j];
                // Find index of y
                int y_idx = 0;
                for (uint32_t k = 0; k < block_count; k++) {
                    if (blocks[k] == y) { y_idx = k; break; }
                }
                
                if (!has_phi[y_idx]) {
                    // Insert Phi
                    mir_phi_t* phi = (mir_phi_t*)malloc(sizeof(mir_phi_t));
                    phi->orig_vreg = v;
                    phi->dst_vreg = v; // Will be renamed later
                    phi->incoming_count = y->pred_count;
                    phi->incoming_values = (mir_operand_t*)malloc(y->pred_count * sizeof(mir_operand_t));
                    phi->incoming_blocks = (mir_block_t**)malloc(y->pred_count * sizeof(mir_block_t*));
                    for (uint32_t k = 0; k < y->pred_count; k++) {
                        phi->incoming_values[k].type = MIR_OPND_NONE;
                        phi->incoming_blocks[k] = y->preds[k];
                    }
                    phi->next = y->phis;
                    y->phis = phi;
                    
                    has_phi[y_idx] = 1;
                    
                    if (!def_blocks[y_idx]) {
                        def_blocks[y_idx] = 1;
                        worklist[tail++] = y_idx;
                    }
                }
            }
        }
    }
    
    free(def_blocks);
    free(has_phi);
    free(worklist);
    free(blocks);
}

typedef struct version_node {
    uint32_t vreg;
    struct version_node* next;
} version_node_t;

static uint32_t top_version(version_node_t** stacks, uint32_t orig_vreg) {
    if (stacks[orig_vreg]) return stacks[orig_vreg]->vreg;
    return orig_vreg; // Uninitialized use
}

static void push_version(version_node_t** stacks, uint32_t orig_vreg, uint32_t new_vreg) {
    version_node_t* node = (version_node_t*)malloc(sizeof(version_node_t));
    node->vreg = new_vreg;
    node->next = stacks[orig_vreg];
    stacks[orig_vreg] = node;
}

static void pop_version(version_node_t** stacks, uint32_t orig_vreg) {
    if (stacks[orig_vreg]) {
        version_node_t* node = stacks[orig_vreg];
        stacks[orig_vreg] = node->next;
        free(node);
    }
}

static void rename_block(mir_func_t* func, mir_block_t* block, version_node_t** stacks, int* pop_counts, uint32_t max_orig_vreg) {
    if (!block) return;
    
    int pushes = 0;
    
    // Rename Phi dst
    mir_phi_t* phi = block->phis;
    while (phi) {
        uint32_t orig = phi->orig_vreg;
        uint32_t new_vreg = ++func->next_vreg;
        phi->dst_vreg = new_vreg;
        push_version(stacks, orig, new_vreg);
        pop_counts[orig]++;
        phi = phi->next;
    }
    
    // Rename normal instructions
    mir_instr_t* instr = block->head;
    while (instr) {
        if (instr->src1.type == MIR_OPND_VREG) {
            instr->src1.as.vreg = top_version(stacks, instr->src1.as.vreg);
        }
        if (instr->src2.type == MIR_OPND_VREG) {
            instr->src2.as.vreg = top_version(stacks, instr->src2.as.vreg);
        }
        if (instr->dst.type == MIR_OPND_VREG) {
            uint32_t orig = instr->dst.as.vreg;
            uint32_t new_vreg = ++func->next_vreg;
            instr->dst.as.vreg = new_vreg;
            push_version(stacks, orig, new_vreg);
            pop_counts[orig]++;
        }
        instr = instr->next;
    }
    
    // Populate successor phis
    if (block->succ_true) {
        mir_phi_t* p = block->succ_true->phis;
        while (p) {
            for (uint32_t i = 0; i < p->incoming_count; i++) {
                if (p->incoming_blocks[i] == block) {
                    p->incoming_values[i].type = MIR_OPND_VREG;
                    p->incoming_values[i].as.vreg = top_version(stacks, p->orig_vreg);
                }
            }
            p = p->next;
        }
    }
    if (block->succ_false) {
        mir_phi_t* p = block->succ_false->phis;
        while (p) {
            for (uint32_t i = 0; i < p->incoming_count; i++) {
                if (p->incoming_blocks[i] == block) {
                    p->incoming_values[i].type = MIR_OPND_VREG;
                    p->incoming_values[i].as.vreg = top_version(stacks, p->orig_vreg);
                }
            }
            p = p->next;
        }
    }
    
    // Recurse into dom children
    for (uint32_t i = 0; i < block->dom_child_count; i++) {
        int* child_pops = (int*)calloc(max_orig_vreg + 1, sizeof(int));
        rename_block(func, block->dom_children[i], stacks, child_pops, max_orig_vreg);
        free(child_pops);
    }
    
    // Pop versions created in this block
    for (uint32_t v = 0; v <= max_orig_vreg; v++) { // Wait, pop_counts is sized to max_orig_vreg
        while (pop_counts[v] > 0) {
            pop_version(stacks, v);
            pop_counts[v]--;
        }
    }
}

void mir_rename_variables(mir_func_t* func) {
    if (!func || !func->entry_block) return;
    
    uint32_t max_orig_vreg = find_max_vreg(func);
    // Ensure func->next_vreg is at least max_orig_vreg
    if (func->next_vreg <= max_orig_vreg) {
        func->next_vreg = max_orig_vreg;
    }
    
    version_node_t** stacks = (version_node_t**)calloc(max_orig_vreg + 1, sizeof(version_node_t*));
    int* pop_counts = (int*)calloc(max_orig_vreg + 1, sizeof(int));
    
    rename_block(func, func->entry_block, stacks, pop_counts, max_orig_vreg);
    
    // Cleanup stacks (should be empty if rename_block popped correctly, but just in case)
    for (uint32_t i = 0; i <= max_orig_vreg; i++) {
        while (stacks[i]) {
            pop_version(stacks, i);
        }
    }
    
    free(stacks);
    free(pop_counts);
}

void mir_build_ssa(mir_func_t* func) {
    if (!func) return;
    mir_insert_phi_nodes(func);
    mir_rename_variables(func);
}
