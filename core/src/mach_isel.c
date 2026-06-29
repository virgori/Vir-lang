#include "mach_isel.h"
#include <stdlib.h>
#include <stdio.h>

static void convert_operand(lir_operand_t *lir_opnd, mach_opnd_t *mach_opnd) {
    switch (lir_opnd->type) {
        case LIR_OPND_PHYS_REG:
            mach_opnd->type = MACH_OPND_REG;
            mach_opnd->as.reg = lir_opnd->as.phys_reg;
            break;
        case LIR_OPND_IMM:
            mach_opnd->type = MACH_OPND_IMM;
            mach_opnd->as.imm = lir_opnd->as.imm;
            break;
        case LIR_OPND_STACK_MEM:
            mach_opnd->type = MACH_OPND_IMM;
            mach_opnd->as.imm = lir_opnd->as.stack_offset;
            break;
        case LIR_OPND_NONE:
            mach_opnd->type = MACH_OPND_NONE;
            break;
        case LIR_OPND_LABEL:
            mach_opnd->type = MACH_OPND_LABEL;
            mach_opnd->as.label_id = lir_opnd->as.label_id;
            break;
        default:
            fprintf(stderr, "[ISel Error] Unsupported operand type for ISel: %d\n", lir_opnd->type);
            mach_opnd->type = MACH_OPND_NONE;
            break;
    }
}

// ARM64 Instruction Selector
void arm64_select_instructions(struct target_info_t *target, lir_block_t *lir_block, mach_block_t *mach_block) {
    (void)target;
    lir_instr_t *instr = lir_block->head;
    while (instr) {
        mach_instr_t *mach_instr = NULL;
        switch (instr->op) {
            case LIR_ADD:
                mach_instr = mach_append_instr(mach_block, MACH_OP_ADD);
                mach_instr->opnd_count = 3;
                convert_operand(&instr->dst, &mach_instr->opnds[0]);
                convert_operand(&instr->src1, &mach_instr->opnds[1]);
                convert_operand(&instr->src2, &mach_instr->opnds[2]);
                break;
            case LIR_SUB:
                mach_instr = mach_append_instr(mach_block, MACH_OP_SUB);
                mach_instr->opnd_count = 3;
                convert_operand(&instr->dst, &mach_instr->opnds[0]);
                convert_operand(&instr->src1, &mach_instr->opnds[1]);
                convert_operand(&instr->src2, &mach_instr->opnds[2]);
                break;
            case LIR_MOV:
                mach_instr = mach_append_instr(mach_block, MACH_OP_MOV);
                mach_instr->opnd_count = 2;
                convert_operand(&instr->dst, &mach_instr->opnds[0]);
                convert_operand(&instr->src1, &mach_instr->opnds[1]);
                break;
            case LIR_LOAD: // LOAD dst, stack_offset
                mach_instr = mach_append_instr(mach_block, MACH_OP_LDR);
                mach_instr->opnd_count = 3;
                convert_operand(&instr->dst, &mach_instr->opnds[0]);
                
                // For ARM64 LDR Rd, [FP, #imm], we assume SP/FP is handled by encoder
                // We'll pass FP (register 29) as the base.
                mach_instr->opnds[1].type = MACH_OPND_REG;
                mach_instr->opnds[1].as.reg = LIR_REG_FP; // We need FP
                
                convert_operand(&instr->src1, &mach_instr->opnds[2]); // the offset
                break;
            case LIR_STORE: // STORE stack_offset, src1
                mach_instr = mach_append_instr(mach_block, MACH_OP_STR);
                mach_instr->opnd_count = 3;
                convert_operand(&instr->src1, &mach_instr->opnds[0]); // Rt
                
                mach_instr->opnds[1].type = MACH_OPND_REG;
                mach_instr->opnds[1].as.reg = LIR_REG_FP;
                
                convert_operand(&instr->dst, &mach_instr->opnds[2]); // the offset
                break;
            case LIR_RET:
                mach_instr = mach_append_instr(mach_block, MACH_OP_RET);
                mach_instr->opnd_count = 0;
                break;
            default:
                // Fallback for NOP or unhandled
                mach_instr = mach_append_instr(mach_block, MACH_OP_NOP);
                mach_instr->opnd_count = 0;
                break;
        }
        instr = instr->next;
    }
}

mach_func_t* mach_select_instructions(const target_info_t *target, lir_func_t *lir_func) {
    if (!target || !lir_func) return NULL;
    
    mach_func_t *mach_func = mach_create_func(lir_func->id);
    
    lir_block_t *lir_b = lir_func->blocks;
    while (lir_b) {
        mach_block_t *mach_b = mach_create_block(mach_func);
        target->hooks.select_instructions((struct target_info_t *)target, lir_b, mach_b);
        lir_b = lir_b->next;
    }
    
    return mach_func;
}
