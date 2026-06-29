#include "lir_opt_coalesce.h"
#include <stdlib.h>

void lir_opt_coalesce(lir_func_t *func) {
    if (!func) return;
    
    lir_block_t *b = func->blocks;
    while (b) {
        lir_instr_t *instr = b->head;
        while (instr) {
            lir_instr_t *next = instr->next;
            
            // Coalesce MOV PReg, PReg where destination and source are the same
            if (instr->op == LIR_MOV) {
                if (instr->dst.type == LIR_OPND_PHYS_REG && instr->src1.type == LIR_OPND_PHYS_REG) {
                    if (instr->dst.as.phys_reg == instr->src1.as.phys_reg) {
                        // Redundant MOV! Unlink it.
                        if (instr->prev) instr->prev->next = instr->next;
                        else b->head = instr->next;
                        
                        if (instr->next) instr->next->prev = instr->prev;
                        else b->tail = instr->prev;
                        
                        free(instr);
                    }
                }
            }
            
            instr = next;
        }
        b = b->next;
    }
}
