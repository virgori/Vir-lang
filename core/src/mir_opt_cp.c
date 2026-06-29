#include "mir_opt.h"
#include <stdlib.h>

void mir_opt_cp_run(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    int changed = 1;
    while (changed) {
        changed = 0;
        mir_block_t* block = func->blocks;
        while (block) {
            mir_instr_t* instr = block->head;
            while (instr) {
                if (instr->op == MIR_MOVE && 
                    instr->dst.type == MIR_OPND_VREG && 
                    instr->src1.type == MIR_OPND_VREG) {
                    
                    uint32_t dst_vreg = instr->dst.as.vreg;
                    uint32_t src_vreg = instr->src1.as.vreg;
                    
                    if (dst_vreg != src_vreg && func->def_uses[dst_vreg]) {
                        mir_replace_all_uses(func, dst_vreg, src_vreg);
                        changed = 1;
                    }
                }
                instr = instr->next;
            }
            block = block->next_block;
        }
    }
}
