#include "mir_pass.h"
#include <stdio.h>
#include <stdlib.h>

static void verify_cfg(mir_func_t* func) {
    mir_block_t* block = func->blocks;
    while (block) {
        // 1. Check terminator
        if (!block->tail) {
            fprintf(stderr, "VERIFY ERROR: Block %u has no instructions\n", block->id);
            exit(1);
        }
        mir_opcode_info_t info = mir_get_opcode_info(block->tail->op);
        if (!info.is_terminator) {
            fprintf(stderr, "VERIFY ERROR: Block %u does not end with a terminator\n", block->id);
            exit(1);
        }
        
        // 2. Check symmetry of preds/succs (only if CFG is built)
        // This is complex because we just have succ_true/succ_false.
        if (block->succ_true) {
            int found = 0;
            for (uint32_t i = 0; i < block->succ_true->pred_count; i++) {
                if (block->succ_true->preds[i] == block) found = 1;
            }
            if (!found) {
                fprintf(stderr, "VERIFY ERROR: Block %u is missing from preds of Block %u\n", block->id, block->succ_true->id);
                exit(1);
            }
        }
        if (block->succ_false) {
            int found = 0;
            for (uint32_t i = 0; i < block->succ_false->pred_count; i++) {
                if (block->succ_false->preds[i] == block) found = 1;
            }
            if (!found) {
                fprintf(stderr, "VERIFY ERROR: Block %u is missing from preds of Block %u\n", block->id, block->succ_false->id);
                exit(1);
            }
        }
        
        block = block->next_block;
    }
}

static void verify_ssa(mir_func_t* func) {
    // 1. Check single assignment
    uint8_t* assigned = (uint8_t*)calloc(func->next_vreg + 1, 1);
    
    mir_block_t* block = func->blocks;
    while (block) {
        mir_phi_t* phi = block->phis;
        while (phi) {
            if (assigned[phi->dst_vreg]) {
                fprintf(stderr, "VERIFY ERROR: SSA violation, vreg %u assigned multiple times\n", phi->dst_vreg);
                exit(1);
            }
            assigned[phi->dst_vreg] = 1;
            phi = phi->next;
        }
        
        mir_instr_t* instr = block->head;
        while (instr) {
            if (instr->dst.type == MIR_OPND_VREG) {
                if (assigned[instr->dst.as.vreg]) {
                    fprintf(stderr, "VERIFY ERROR: SSA violation, vreg %u assigned multiple times\n", instr->dst.as.vreg);
                    exit(1);
                }
                assigned[instr->dst.as.vreg] = 1;
            }
            instr = instr->next;
        }
        block = block->next_block;
    }
    
    free(assigned);
}

void mir_verify_run(mir_func_t* func, uint32_t current_analysis) {
    if (!func) return;
    
    if (current_analysis & MIR_ANALYSIS_CFG) {
        verify_cfg(func);
    }
    
    if (current_analysis & MIR_ANALYSIS_SSA) {
        verify_ssa(func);
    }
}
