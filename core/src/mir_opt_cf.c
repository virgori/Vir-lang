#include "mir_opt.h"
#include <stdlib.h>
#include <string.h>

void mir_opt_cf_run(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    int changed = 1;
    uint32_t max_vreg = func->next_vreg;
    
    int* is_const = (int*)calloc(max_vreg + 1, sizeof(int));
    int64_t* const_val = (int64_t*)calloc(max_vreg + 1, sizeof(int64_t));
    
    while (changed) {
        changed = 0;
        
        mir_block_t* block = func->blocks;
        while (block) {
            
            // Note: Constant propagation through Phi nodes is possible but complex.
            // We focus on instructions first.
            
            mir_instr_t* instr = block->head;
            while (instr) {
                // 1. Propagate constants to operands
                if (instr->src1.type == MIR_OPND_VREG && is_const[instr->src1.as.vreg]) {
                    instr->src1.type = MIR_OPND_IMM;
                    instr->src1.as.imm = const_val[instr->src1.as.vreg];
                    changed = 1;
                }
                if (instr->src2.type == MIR_OPND_VREG && is_const[instr->src2.as.vreg]) {
                    instr->src2.type = MIR_OPND_IMM;
                    instr->src2.as.imm = const_val[instr->src2.as.vreg];
                    changed = 1;
                }
                
                // 2. Fold constants
                if (instr->op == MIR_MOVE && instr->src1.type == MIR_OPND_IMM) {
                    if (instr->dst.type == MIR_OPND_VREG && !is_const[instr->dst.as.vreg]) {
                        is_const[instr->dst.as.vreg] = 1;
                        const_val[instr->dst.as.vreg] = instr->src1.as.imm;
                        changed = 1;
                    }
                } else if (instr->src1.type == MIR_OPND_IMM && instr->src2.type == MIR_OPND_IMM) {
                    int folded = 0;
                    int64_t v1 = instr->src1.as.imm;
                    int64_t v2 = instr->src2.as.imm;
                    int64_t result = 0;
                    
                    switch (instr->op) {
                        case MIR_ADD: result = v1 + v2; folded = 1; break;
                        case MIR_SUB: result = v1 - v2; folded = 1; break;
                        case MIR_MUL: result = v1 * v2; folded = 1; break;
                        case MIR_DIV: 
                            if (v2 != 0) { result = v1 / v2; folded = 1; }
                            break;
                        default: break;
                    }
                    
                    if (folded) {
                        instr->op = MIR_MOVE;
                        instr->src1.type = MIR_OPND_IMM;
                        instr->src1.as.imm = result;
                        instr->src2.type = MIR_OPND_NONE;
                        changed = 1;
                        
                        if (instr->dst.type == MIR_OPND_VREG) {
                            is_const[instr->dst.as.vreg] = 1;
                            const_val[instr->dst.as.vreg] = result;
                        }
                    }
                }
                
                instr = instr->next;
            }
            
            block = block->next_block;
        }
    }
    
    free(is_const);
    free(const_val);
}
