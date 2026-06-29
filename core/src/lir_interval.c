#include "lir_analysis.h"
#include <stdlib.h>
#include <string.h>

#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))

lir_interval_ctx_t* lir_analyze_intervals(lir_func_t *func, lir_liveness_t *liveness) {
    lir_interval_ctx_t *ctx = malloc(sizeof(lir_interval_ctx_t));
    ctx->func = func;
    ctx->liveness = liveness;
    
    // Find max_vreg
    uint32_t max_vreg = 0;
    lir_block_t *b = func->blocks;
    while (b) {
        lir_instr_t *instr = b->head;
        while (instr) {
            if (instr->dst.type == LIR_OPND_VREG_INT || instr->dst.type == LIR_OPND_VREG_FLOAT) {
                if (instr->dst.as.vreg > max_vreg) max_vreg = instr->dst.as.vreg;
            }
            if (instr->src1.type == LIR_OPND_VREG_INT || instr->src1.type == LIR_OPND_VREG_FLOAT) {
                if (instr->src1.as.vreg > max_vreg) max_vreg = instr->src1.as.vreg;
            }
            if (instr->src2.type == LIR_OPND_VREG_INT || instr->src2.type == LIR_OPND_VREG_FLOAT) {
                if (instr->src2.as.vreg > max_vreg) max_vreg = instr->src2.as.vreg;
            }
            instr = instr->next;
        }
        b = b->next;
    }
    
    ctx->max_vreg = max_vreg;
    ctx->intervals = malloc(sizeof(lir_live_interval_t) * (max_vreg + 1));
    for (uint32_t i = 0; i <= max_vreg; i++) {
        ctx->intervals[i].vreg = i;
        ctx->intervals[i].start_instr = UINT32_MAX;
        ctx->intervals[i].end_instr = 0;
        ctx->intervals[i].phys_reg = 0;
        ctx->intervals[i].is_live = false;
    }
    
    // Assign sequential IDs and build intervals
    uint32_t instr_id = 1;
    
    // First pass: Calculate total instructions to assign backwards IDs
    b = func->blocks;
    while (b) {
        lir_instr_t *instr = b->head;
        while (instr) {
            instr_id += 2; // leave gaps for spills
            instr = instr->next;
        }
        b = b->next;
    }
    
    uint32_t current_id = instr_id;
    
    // Traverse backwards
    lir_block_t **block_arr = malloc(sizeof(lir_block_t*) * liveness->block_count);
    b = func->blocks;
    for (int i = 0; i < (int)liveness->block_count; i++) {
        block_arr[i] = b;
        b = b->next;
    }
    
    for (int i = (int)liveness->block_count - 1; i >= 0; i--) {
        b = block_arr[i];
        lir_liveness_block_t *lb = &liveness->blocks[i];
        
        uint32_t block_end_id = current_id;
        
        // Build array of instructions in block
        uint32_t icount = 0;
        lir_instr_t *instr = b->head;
        while (instr) { icount++; instr = instr->next; }
        
        lir_instr_t **instr_arr = malloc(sizeof(lir_instr_t*) * icount);
        instr = b->head;
        for (int j = 0; j < (int)icount; j++) {
            instr_arr[j] = instr;
            instr = instr->next;
        }
        
        uint32_t block_start_id = block_end_id - (icount * 2);
        
        // Any variable in live_out has an interval ending at least at block_end_id
        for (uint32_t v = 0; v <= max_vreg; v++) {
            if (lir_bitset_test(&lb->live_out, v)) {
                if (!ctx->intervals[v].is_live) {
                    ctx->intervals[v].is_live = true;
                    ctx->intervals[v].end_instr = block_end_id;
                }
                ctx->intervals[v].start_instr = block_start_id; // Will be refined
            }
        }
        
        // Process instructions backwards
        for (int j = (int)icount - 1; j >= 0; j--) {
            instr = instr_arr[j];
            current_id -= 2;
            
            // Def ends liveness (going backwards)
            if (instr->dst.type == LIR_OPND_VREG_INT || instr->dst.type == LIR_OPND_VREG_FLOAT) {
                uint32_t vreg = instr->dst.as.vreg;
                ctx->intervals[vreg].is_live = true;
                ctx->intervals[vreg].start_instr = current_id;
            }
            
            // Uses start liveness (going backwards)
            if (instr->src1.type == LIR_OPND_VREG_INT || instr->src1.type == LIR_OPND_VREG_FLOAT) {
                uint32_t vreg = instr->src1.as.vreg;
                if (!ctx->intervals[vreg].is_live) {
                    ctx->intervals[vreg].is_live = true;
                    ctx->intervals[vreg].end_instr = current_id;
                }
                ctx->intervals[vreg].start_instr = block_start_id; // Will be refined
            }
            if (instr->src2.type == LIR_OPND_VREG_INT || instr->src2.type == LIR_OPND_VREG_FLOAT) {
                uint32_t vreg = instr->src2.as.vreg;
                if (!ctx->intervals[vreg].is_live) {
                    ctx->intervals[vreg].is_live = true;
                    ctx->intervals[vreg].end_instr = current_id;
                }
                ctx->intervals[vreg].start_instr = block_start_id; // Will be refined
            }
        }
        
        free(instr_arr);
    }
    
    free(block_arr);
    return ctx;
}

void lir_free_intervals(lir_interval_ctx_t *ctx) {
    if (!ctx) return;
    free(ctx->intervals);
    free(ctx);
}
