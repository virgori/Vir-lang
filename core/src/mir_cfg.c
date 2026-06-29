#include "mir_cfg.h"
#include <stdlib.h>
#include <string.h>

static void add_pred(mir_block_t* block, mir_block_t* pred) {
    if (!block) return;
    if (block->pred_count == block->pred_capacity) {
        block->pred_capacity = block->pred_capacity == 0 ? 4 : block->pred_capacity * 2;
        block->preds = (mir_block_t**)realloc(block->preds, block->pred_capacity * sizeof(mir_block_t*));
    }
    block->preds[block->pred_count++] = pred;
}

void mir_build_cfg(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    // Clear existing preds
    mir_block_t* curr = func->blocks;
    while (curr) {
        curr->pred_count = 0;
        curr = curr->next_block;
    }
    
    curr = func->blocks;
    while (curr) {
        if (curr->succ_true) add_pred(curr->succ_true, curr);
        if (curr->succ_false) add_pred(curr->succ_false, curr);
        curr = curr->next_block;
    }
}

// Simple bitset implementation for dominators
typedef struct {
    uint32_t* words;
    uint32_t word_count;
} bitset_t;

static void bitset_init(bitset_t* b, uint32_t size, int set_all) {
    b->word_count = (size + 31) / 32;
    b->words = (uint32_t*)malloc(b->word_count * sizeof(uint32_t));
    if (set_all) {
        memset(b->words, 0xFF, b->word_count * sizeof(uint32_t));
    } else {
        memset(b->words, 0, b->word_count * sizeof(uint32_t));
    }
}

static void bitset_free(bitset_t* b) {
    if (b->words) free(b->words);
}

static void bitset_set(bitset_t* b, uint32_t idx) {
    b->words[idx / 32] |= (1 << (idx % 32));
}

static int bitset_get(const bitset_t* b, uint32_t idx) {
    return (b->words[idx / 32] & (1 << (idx % 32))) != 0;
}

static int bitset_intersect(bitset_t* dst, const bitset_t* src) {
    int changed = 0;
    for (uint32_t i = 0; i < dst->word_count; i++) {
        uint32_t old = dst->words[i];
        dst->words[i] &= src->words[i];
        if (dst->words[i] != old) changed = 1;
    }
    return changed;
}

static void add_df(mir_block_t* block, mir_block_t* df_node) {
    for (uint32_t i = 0; i < block->df_count; i++) {
        if (block->df[i] == df_node) return; // Already exists
    }
    if (block->df_count == block->df_capacity) {
        block->df_capacity = block->df_capacity == 0 ? 4 : block->df_capacity * 2;
        block->df = (mir_block_t**)realloc(block->df, block->df_capacity * sizeof(mir_block_t*));
    }
    block->df[block->df_count++] = df_node;
}

static void add_dom_child(mir_block_t* parent, mir_block_t* child) {
    if (parent->dom_child_count == parent->dom_child_capacity) {
        parent->dom_child_capacity = parent->dom_child_capacity == 0 ? 4 : parent->dom_child_capacity * 2;
        parent->dom_children = (mir_block_t**)realloc(parent->dom_children, parent->dom_child_capacity * sizeof(mir_block_t*));
    }
    parent->dom_children[parent->dom_child_count++] = child;
}

void mir_compute_dominators(mir_func_t* func) {
    if (!func || !func->entry_block) return;
    
    // 1. Assign indices
    uint32_t block_count = 0;
    mir_block_t* curr = func->blocks;
    while (curr) {
        block_count++;
        curr = curr->next_block;
    }
    
    if (block_count == 0) return;
    
    mir_block_t** block_array = (mir_block_t**)malloc(block_count * sizeof(mir_block_t*));
    curr = func->blocks;
    uint32_t idx = 0;
    uint32_t entry_idx = 0;
    while (curr) {
        block_array[idx] = curr;
        if (curr == func->entry_block) entry_idx = idx;
        idx++;
        curr = curr->next_block;
    }
    
    // 2. Initialize Dom sets
    bitset_t* doms = (bitset_t*)malloc(block_count * sizeof(bitset_t));
    for (uint32_t i = 0; i < block_count; i++) {
        bitset_init(&doms[i], block_count, i != entry_idx);
    }
    bitset_set(&doms[entry_idx], entry_idx);
    
    // 3. Iterative solver for Dom
    int changed = 1;
    bitset_t temp;
    bitset_init(&temp, block_count, 0);
    
    while (changed) {
        changed = 0;
        for (uint32_t i = 0; i < block_count; i++) {
            if (i == entry_idx) continue;
            
            mir_block_t* b = block_array[i];
            if (b->pred_count == 0) continue;
            
            // Intersection of predecessors' doms
            memset(temp.words, 0xFF, temp.word_count * sizeof(uint32_t));
            for (uint32_t j = 0; j < b->pred_count; j++) {
                mir_block_t* p = b->preds[j];
                uint32_t p_idx = 0;
                for (uint32_t k = 0; k < block_count; k++) {
                    if (block_array[k] == p) { p_idx = k; break; }
                }
                bitset_intersect(&temp, &doms[p_idx]);
            }
            
            // Dom(n) = {n} U intersection
            bitset_set(&temp, i);
            
            // Check if changed
            for (uint32_t j = 0; j < temp.word_count; j++) {
                if (doms[i].words[j] != temp.words[j]) {
                    doms[i].words[j] = temp.words[j];
                    changed = 1;
                }
            }
        }
    }
    
    // 4. Compute IDom
    for (uint32_t i = 0; i < block_count; i++) {
        if (i == entry_idx) continue;
        mir_block_t* b = block_array[i];
        
        // Find strict dominators
        int idom_idx = -1;
        for (uint32_t d = 0; d < block_count; d++) {
            if (d == i) continue;
            if (bitset_get(&doms[i], d)) {
                // 'd' strictly dominates 'i'. Does 'd' dominate all other strict dominators?
                // Wait, IDom is the dominator that is dominated by all other strict dominators.
                int is_idom = 1;
                for (uint32_t other_d = 0; other_d < block_count; other_d++) {
                    if (other_d == i || other_d == d) continue;
                    if (bitset_get(&doms[i], other_d)) {
                        if (!bitset_get(&doms[d], other_d)) {
                            is_idom = 0;
                            break;
                        }
                    }
                }
                if (is_idom) {
                    idom_idx = (int)d;
                    break;
                }
            }
        }
        if (idom_idx != -1) {
            b->idom = block_array[idom_idx];
            add_dom_child(b->idom, b);
        }
    }
    
    // 5. Compute Dominance Frontiers
    for (uint32_t i = 0; i < block_count; i++) {
        mir_block_t* b = block_array[i];
        if (b->pred_count >= 2) {
            for (uint32_t j = 0; j < b->pred_count; j++) {
                mir_block_t* runner = b->preds[j];
                while (runner && runner != b->idom) {
                    add_df(runner, b);
                    runner = runner->idom;
                }
            }
        }
    }
    
    // Cleanup
    bitset_free(&temp);
    for (uint32_t i = 0; i < block_count; i++) {
        bitset_free(&doms[i]);
    }
    free(doms);
    free(block_array);
}
