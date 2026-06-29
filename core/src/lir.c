#include "lir.h"
#include <stdlib.h>
#include <string.h>

lir_func_t* lir_create_func(uint32_t id) {
    lir_func_t* func = (lir_func_t*)malloc(sizeof(lir_func_t));
    if (func) {
        memset(func, 0, sizeof(lir_func_t));
        func->id = id;
        func->next_block_id = 1;
    }
    return func;
}

lir_block_t* lir_create_block(lir_func_t* func) {
    if (!func) return NULL;
    
    lir_block_t* block = (lir_block_t*)malloc(sizeof(lir_block_t));
    if (block) {
        memset(block, 0, sizeof(lir_block_t));
        block->id = func->next_block_id++;
        
        if (!func->blocks) {
            func->blocks = block;
        } else {
            lir_block_t* curr = func->blocks;
            while (curr->next) {
                curr = curr->next;
            }
            curr->next = block;
        }
    }
    return block;
}

void lir_append_instr(lir_block_t* block, lir_op_t op, lir_operand_t dst, lir_operand_t src1, lir_operand_t src2) {
    if (!block) return;
    
    lir_instr_t* instr = (lir_instr_t*)malloc(sizeof(lir_instr_t));
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

void lir_free_func(lir_func_t* func) {
    if (!func) return;
    
    lir_block_t* block = func->blocks;
    while (block) {
        lir_instr_t* instr = block->head;
        while (instr) {
            lir_instr_t* next_instr = instr->next;
            free(instr);
            instr = next_instr;
        }
        
        lir_block_t* next_block = block->next;
        free(block);
        block = next_block;
    }
    
    free(func);
}

static const lir_phys_reg_info_t reg_info_table[] = {
    [LIR_REG_R0] = { "r0", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLER_SAVED | LIR_REG_ROLE_RETURN },
    [LIR_REG_R1] = { "r1", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLER_SAVED | LIR_REG_ROLE_ARGUMENT },
    [LIR_REG_R2] = { "r2", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLER_SAVED | LIR_REG_ROLE_ARGUMENT },
    [LIR_REG_R3] = { "r3", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLER_SAVED | LIR_REG_ROLE_ARGUMENT },
    [LIR_REG_R4] = { "r4", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLER_SAVED | LIR_REG_ROLE_ARGUMENT },
    [LIR_REG_R5] = { "r5", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLEE_SAVED },
    [LIR_REG_R6] = { "r6", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLEE_SAVED },
    [LIR_REG_R7] = { "r7", LIR_REG_CLASS_INT, LIR_REG_ROLE_CALLEE_SAVED },
    [LIR_REG_R8] = { "r8", LIR_REG_CLASS_INT, LIR_REG_ROLE_SCRATCH },
    [LIR_REG_R9] = { "r9", LIR_REG_CLASS_INT, LIR_REG_ROLE_SCRATCH },
    [LIR_REG_SP] = { "sp", LIR_REG_CLASS_SPECIAL, LIR_REG_ROLE_RESERVED },
    [LIR_REG_FP] = { "fp", LIR_REG_CLASS_SPECIAL, LIR_REG_ROLE_RESERVED }
};

const lir_phys_reg_info_t* lir_get_phys_reg_info(lir_phys_reg_t reg) {
    if (reg >= LIR_REG_MAX) return NULL;
    return &reg_info_table[reg];
}
