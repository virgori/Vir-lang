#include "mir.h"
#include <stdlib.h>
#include <string.h>

mir_func_t* mir_create_func(uint32_t id) {
    mir_func_t* func = (mir_func_t*)malloc(sizeof(mir_func_t));
    if (func) {
        memset(func, 0, sizeof(mir_func_t));
        func->id = id;
        func->next_vreg = 1;
        func->next_block_id = 1;
    }
    return func;
}

mir_block_t* mir_create_block(mir_func_t* func) {
    if (!func) return NULL;
    
    mir_block_t* block = (mir_block_t*)malloc(sizeof(mir_block_t));
    if (block) {
        memset(block, 0, sizeof(mir_block_t));
        block->id = func->next_block_id++;
        
        // Append to func block list
        if (!func->blocks) {
            func->blocks = block;
            func->entry_block = block;
        } else {
            mir_block_t* curr = func->blocks;
            while (curr->next_block) {
                curr = curr->next_block;
            }
            curr->next_block = block;
        }
    }
    return block;
}

void mir_append_instr(mir_block_t* block, mir_op_t op, mir_operand_t dst, mir_operand_t src1, mir_operand_t src2) {
    if (!block) return;
    
    mir_instr_t* instr = (mir_instr_t*)malloc(sizeof(mir_instr_t));
    if (instr) {
        instr->op = op;
        instr->dst = dst;
        instr->src1 = src1;
        instr->src2 = src2;
        instr->next = NULL;
        
        if (!block->head) {
            block->head = instr;
            block->tail = instr;
        } else {
            block->tail->next = instr;
            block->tail = instr;
        }
    }
}

void mir_free_func(mir_func_t* func) {
    if (!func) return;
    
    mir_block_t* block = func->blocks;
    while (block) {
        mir_instr_t* instr = block->head;
        while (instr) {
            mir_instr_t* next_instr = instr->next;
            free(instr);
            instr = next_instr;
        }
        
        mir_phi_t* phi = block->phis;
        while (phi) {
            mir_phi_t* next_phi = phi->next;
            if (phi->incoming_values) free(phi->incoming_values);
            if (phi->incoming_blocks) free(phi->incoming_blocks);
            free(phi);
            phi = next_phi;
        }
        
        if (block->preds) free(block->preds);
        if (block->dom_children) free(block->dom_children);
        if (block->df) free(block->df);
        
        mir_block_t* next_block = block->next_block;
        free(block);
        block = next_block;
    }
    
    
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

    free(func);
}

mir_opcode_info_t mir_get_opcode_info(mir_op_t op) {
    mir_opcode_info_t info = {0, 0, 0, 0};
    switch (op) {
        case MIR_CALL:
            info.has_side_effect = 1;
            info.may_read_memory = 1;
            info.may_write_memory = 1;
            break;
        case MIR_STORE:
            info.has_side_effect = 1;
            info.may_write_memory = 1;
            break;
        case MIR_LOAD:
            info.may_read_memory = 1;
            break;
        case MIR_JUMP:
        case MIR_JUMP_IF:
        case MIR_RETURN:
            info.is_terminator = 1;
            info.has_side_effect = 1;
            break;
        case MIR_INTRINSIC:
            info.has_side_effect = 1;
            info.may_read_memory = 1;
            info.may_write_memory = 1;
            break;
        default:
            // Pure arithmetic, MOVE, CMP, NOP
            break;
    }
    return info;
}
