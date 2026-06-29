#include "lir_verify.h"
#include <stdio.h>

static bool verify_operand(lir_operand_t *opnd) {
    if (opnd->type == LIR_OPND_VREG_INT || opnd->type == LIR_OPND_VREG_FLOAT) {
        fprintf(stderr, "[Machine Verifier Error] Virtual Register found in machine-level LIR: v%u\n", opnd->as.vreg);
        return false;
    }
    
    if (opnd->type == LIR_OPND_PHYS_REG) {
        if (opnd->as.phys_reg >= LIR_REG_MAX) {
            fprintf(stderr, "[Machine Verifier Error] Invalid Physical Register ID: %u\n", opnd->as.phys_reg);
            return false;
        }
    }
    
    return true;
}

bool lir_verify_machine_state(lir_func_t *func) {
    if (!func) return false;
    
    bool ok = true;
    
    lir_block_t *b = func->blocks;
    while (b) {
        lir_instr_t *instr = b->head;
        while (instr) {
            if (!verify_operand(&instr->dst)) ok = false;
            if (!verify_operand(&instr->src1)) ok = false;
            if (!verify_operand(&instr->src2)) ok = false;
            
            instr = instr->next;
        }
        b = b->next;
    }
    
    return ok;
}
