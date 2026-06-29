#include "lir_analysis.h"
#include <stdlib.h>
#include <string.h>

void lir_bitset_set(lir_bitset_t *bs, uint32_t vreg) {
    if (vreg < LIR_MAX_VREGS) {
        bs->bits[vreg / 32] |= (1U << (vreg % 32));
    }
}

void lir_bitset_clear(lir_bitset_t *bs, uint32_t vreg) {
    if (vreg < LIR_MAX_VREGS) {
        bs->bits[vreg / 32] &= ~(1U << (vreg % 32));
    }
}

bool lir_bitset_test(const lir_bitset_t *bs, uint32_t vreg) {
    if (vreg < LIR_MAX_VREGS) {
        return (bs->bits[vreg / 32] & (1U << (vreg % 32))) != 0;
    }
    return false;
}

bool lir_bitset_union(lir_bitset_t *dst, const lir_bitset_t *src) {
    bool changed = false;
    for (int i = 0; i < LIR_BITSET_WORDS; i++) {
        uint32_t old = dst->bits[i];
        dst->bits[i] |= src->bits[i];
        if (dst->bits[i] != old) {
            changed = true;
        }
    }
    return changed;
}

void lir_bitset_clear_all(lir_bitset_t *bs) {
    memset(bs->bits, 0, sizeof(bs->bits));
}

// Internal helper
static void analyze_block_local(lir_liveness_block_t *lb, lir_block_t *block) {
    lir_bitset_clear_all(&lb->use);
    lir_bitset_clear_all(&lb->def);
    
    lir_instr_t *instr = block->head;
    while (instr) {
        // Source 1 use
        if (instr->src1.type == LIR_OPND_VREG_INT || instr->src1.type == LIR_OPND_VREG_FLOAT) {
            uint32_t vreg = instr->src1.as.vreg;
            if (!lir_bitset_test(&lb->def, vreg)) {
                lir_bitset_set(&lb->use, vreg);
            }
        }
        // Source 2 use
        if (instr->src2.type == LIR_OPND_VREG_INT || instr->src2.type == LIR_OPND_VREG_FLOAT) {
            uint32_t vreg = instr->src2.as.vreg;
            if (!lir_bitset_test(&lb->def, vreg)) {
                lir_bitset_set(&lb->use, vreg);
            }
        }
        
        // Dest def
        if (instr->dst.type == LIR_OPND_VREG_INT || instr->dst.type == LIR_OPND_VREG_FLOAT) {
            lir_bitset_set(&lb->def, instr->dst.as.vreg);
        }
        
        instr = instr->next;
    }
}

lir_liveness_t* lir_analyze_liveness(lir_func_t *func) {
    lir_liveness_t *liveness = malloc(sizeof(lir_liveness_t));
    liveness->func = func;
    
    // Count blocks
    uint32_t bcount = 0;
    lir_block_t *b = func->blocks;
    while (b) { bcount++; b = b->next; }
    
    liveness->block_count = bcount;
    liveness->blocks = malloc(sizeof(lir_liveness_block_t) * bcount);
    
    // Init blocks and calculate local Def/Use
    uint32_t i = 0;
    b = func->blocks;
    while (b) {
        lir_liveness_block_t *lb = &liveness->blocks[i];
        lb->block_id = b->id;
        lir_bitset_clear_all(&lb->live_in);
        lir_bitset_clear_all(&lb->live_out);
        analyze_block_local(lb, b);
        i++;
        b = b->next;
    }
    
    // Iterative dataflow analysis
    bool changed = true;
    while (changed) {
        changed = false;
        
        // Traverse backwards (bottom-up is faster for backwards analysis like liveness)
        for (int idx = (int)bcount - 1; idx >= 0; idx--) {
            lir_liveness_block_t *lb = &liveness->blocks[idx];
            b = func->blocks;
            for (int k = 0; k < idx; k++) b = b->next; // find lir_block_t
            
            // Calculate LiveOut = Union(LiveIn of successors)
            lir_bitset_t new_out;
            lir_bitset_clear_all(&new_out);
            
            // Successor 1: Fallthrough (if not unconditional jump/ret)
            lir_instr_t *tail = b->tail;
            bool has_fallthrough = true;
            if (tail && (tail->op == LIR_JMP || tail->op == LIR_RET)) {
                has_fallthrough = false;
            }
            if (has_fallthrough && idx + 1 < (int)bcount) {
                lir_bitset_union(&new_out, &liveness->blocks[idx + 1].live_in);
            }
            
            // Successor 2: Jump target
            if (tail && (tail->op == LIR_JMP || tail->op == LIR_JMP_COND)) {
                if (tail->dst.type == LIR_OPND_LABEL) {
                    uint32_t target_id = tail->dst.as.label_id;
                    // Find target block
                    for (int t = 0; t < (int)bcount; t++) {
                        if (liveness->blocks[t].block_id == target_id) {
                            lir_bitset_union(&new_out, &liveness->blocks[t].live_in);
                            break;
                        }
                    }
                }
            }
            
            lb->live_out = new_out;
            
            // Calculate LiveIn = Use U (LiveOut - Def)
            lir_bitset_t new_in = lb->use;
            for (int w = 0; w < LIR_BITSET_WORDS; w++) {
                new_in.bits[w] |= (lb->live_out.bits[w] & ~lb->def.bits[w]);
            }
            
            // Check if LiveIn changed
            for (int w = 0; w < LIR_BITSET_WORDS; w++) {
                if (lb->live_in.bits[w] != new_in.bits[w]) {
                    lb->live_in = new_in;
                    changed = true;
                }
            }
        }
    }
    
    return liveness;
}

void lir_free_liveness(lir_liveness_t *liveness) {
    if (!liveness) return;
    free(liveness->blocks);
    free(liveness);
}
