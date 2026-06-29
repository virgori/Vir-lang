#include "mir_pass.h"
#include <stdlib.h>

static void add_use(mir_func_t* func, uint32_t vreg, mir_instr_t* instr, mir_phi_t* phi, uint8_t opnd_idx) {
    if (vreg > func->next_vreg) return;
    mir_use_t* use = (mir_use_t*)malloc(sizeof(mir_use_t));
    use->instr = instr;
    use->phi = phi;
    use->opnd_idx = opnd_idx;
    use->next = func->def_uses[vreg];
    func->def_uses[vreg] = use;
}

void mir_pass_def_use_run(mir_func_t* func) {
    if (!func) return;
    
    // Cleanup old uses
    if (func->def_uses) {
        for (uint32_t i = 0; i <= func->next_vreg; i++) {
            mir_use_t* use = func->def_uses[i];
            while (use) {
                mir_use_t* next = use->next;
                free(use);
                use = next;
            }
        }
        free(func->def_uses);
    }
    
    func->def_uses = (mir_use_t**)calloc(func->next_vreg + 1, sizeof(mir_use_t*));
    
    mir_block_t* block = func->blocks;
    while (block) {
        // Phis
        mir_phi_t* phi = block->phis;
        while (phi) {
            for (uint32_t i = 0; i < phi->incoming_count; i++) {
                if (phi->incoming_values[i].type == MIR_OPND_VREG) {
                    add_use(func, phi->incoming_values[i].as.vreg, NULL, phi, i);
                }
            }
            phi = phi->next;
        }
        
        // Instrs
        mir_instr_t* instr = block->head;
        while (instr) {
            if (instr->src1.type == MIR_OPND_VREG) add_use(func, instr->src1.as.vreg, instr, NULL, 1);
            if (instr->src2.type == MIR_OPND_VREG) add_use(func, instr->src2.as.vreg, instr, NULL, 2);
            instr = instr->next;
        }
        
        block = block->next_block;
    }
}

void mir_replace_all_uses(mir_func_t* func, uint32_t old_vreg, uint32_t new_vreg) {
    if (!func || old_vreg > func->next_vreg || new_vreg > func->next_vreg) return;
    if (old_vreg == new_vreg) return;
    
    mir_use_t* use = func->def_uses[old_vreg];
    if (!use) return;
    
    // Find the end of the list and update the instructions
    mir_use_t* tail = use;
    while (tail) {
        if (tail->instr) {
            if (tail->opnd_idx == 1) tail->instr->src1.as.vreg = new_vreg;
            else if (tail->opnd_idx == 2) tail->instr->src2.as.vreg = new_vreg;
        } else if (tail->phi) {
            tail->phi->incoming_values[tail->opnd_idx].as.vreg = new_vreg;
        }
        if (!tail->next) break;
        tail = tail->next;
    }
    
    // Append to new_vreg's list
    tail->next = func->def_uses[new_vreg];
    func->def_uses[new_vreg] = use;
    func->def_uses[old_vreg] = NULL;
}

void mir_remove_use(mir_func_t* func, uint32_t vreg, mir_instr_t* instr, mir_phi_t* phi) {
    if (!func || vreg > func->next_vreg) return;
    
    mir_use_t* use = func->def_uses[vreg];
    mir_use_t* prev = NULL;
    
    while (use) {
        if ((instr && use->instr == instr) || (phi && use->phi == phi)) {
            if (prev) prev->next = use->next;
            else func->def_uses[vreg] = use->next;
            
            free(use);
            return; // Assume one use per instr/phi per vreg (or we'd continue)
        }
        prev = use;
        use = use->next;
    }
}

void mir_remove_instr_def_use(mir_func_t* func, mir_instr_t* instr) {
    if (!func || !instr) return;
    if (instr->src1.type == MIR_OPND_VREG) mir_remove_use(func, instr->src1.as.vreg, instr, NULL);
    if (instr->src2.type == MIR_OPND_VREG) mir_remove_use(func, instr->src2.as.vreg, instr, NULL);
}

void mir_remove_phi_def_use(mir_func_t* func, mir_phi_t* phi) {
    if (!func || !phi) return;
    for (uint32_t i = 0; i < phi->incoming_count; i++) {
        if (phi->incoming_values[i].type == MIR_OPND_VREG) {
            mir_remove_use(func, phi->incoming_values[i].as.vreg, NULL, phi);
        }
    }
}
