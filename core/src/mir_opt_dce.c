#include "mir_opt.h"
#include <stdlib.h>

void mir_opt_dce_run(mir_func_t* func) {
    if (!func || !func->blocks) return;
    
    int changed = 1;
    while (changed) {
        changed = 0;
        
        mir_block_t* block = func->blocks;
        while (block) {
            // Eliminate dead Phis
            mir_phi_t* phi = block->phis;
            mir_phi_t* prev_phi = NULL;
            while (phi) {
                if (func->def_uses[phi->dst_vreg] == NULL) {
                    mir_remove_phi_def_use(func, phi);
                    
                    mir_phi_t* next = phi->next;
                    if (prev_phi) prev_phi->next = next;
                    else block->phis = next;
                    
                    if (phi->incoming_values) free(phi->incoming_values);
                    if (phi->incoming_blocks) free(phi->incoming_blocks);
                    free(phi);
                    
                    phi = next;
                    changed = 1;
                } else {
                    prev_phi = phi;
                    phi = phi->next;
                }
            }
            
            // Eliminate dead Instructions
            mir_instr_t* instr = block->head;
            mir_instr_t* prev_instr = NULL;
            while (instr) {
                mir_instr_t* next = instr->next;
                
                if (instr->dst.type == MIR_OPND_VREG && func->def_uses[instr->dst.as.vreg] == NULL) {
                    mir_opcode_info_t info = mir_get_opcode_info(instr->op);
                    
                    if (!info.has_side_effect) {
                        mir_remove_instr_def_use(func, instr);
                        
                        if (prev_instr) prev_instr->next = next;
                        else block->head = next;
                        
                        if (!next) block->tail = prev_instr;
                        
                        free(instr);
                        changed = 1;
                        instr = next;
                        continue;
                    }
                }
                prev_instr = instr;
                instr = next;
            }
            
            block = block->next_block;
        }
    }
}
