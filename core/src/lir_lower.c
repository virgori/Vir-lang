#include "lir_lower.h"
#include <stdlib.h>

static lir_operand_t map_mir_opnd(mir_operand_t m) {
    lir_operand_t l = { LIR_OPND_NONE, {0} };
    switch (m.type) {
        case MIR_OPND_VREG:
            l.type = LIR_OPND_VREG_INT;
            l.as.vreg = m.as.vreg;
            break;
        case MIR_OPND_IMM:
            l.type = LIR_OPND_IMM;
            l.as.imm = m.as.imm;
            break;
        case MIR_OPND_BLOCK:
            l.type = LIR_OPND_LABEL;
            l.as.label_id = m.as.block_id;
            break;
        default:
            break;
    }
    return l;
}

static lir_op_t map_mir_op(mir_op_t m) {
    switch (m) {
        case MIR_MOVE:
        case MIR_LOAD:
        case MIR_STORE:
            return LIR_MOV;
        case MIR_LOAD_STRING:
            return LIR_LOAD_STRING;
        case MIR_ADD:
            return LIR_ADD;
        case MIR_SUB:
            return LIR_SUB;
        case MIR_MUL:
            return LIR_MUL;
        case MIR_DIV:
            return LIR_DIV;
        case MIR_CMP_GT:
            return LIR_CMP_GT;
        case MIR_CMP_LT:
            return LIR_CMP_LT;
        case MIR_CMP_EQ:
            return LIR_CMP_EQ;
        case MIR_CMP_GE:
            return LIR_CMP_GE;
        case MIR_CMP_LE:
            return LIR_CMP_LE;
        case MIR_CMP_NE:
            return LIR_CMP_NE;
        case MIR_ARG_COUNT:
            return LIR_ARG_COUNT;
        case MIR_GET_ARG:
            return LIR_GET_ARG;
        case MIR_LOAD_BYTE:
            return LIR_LOAD_BYTE;
        case MIR_STORE_BYTE:
            return LIR_STORE_BYTE;
        case MIR_LOAD_WORD:
            return LIR_LOAD_WORD;
        case MIR_STORE_WORD:
            return LIR_STORE_WORD;
        case MIR_CALL:
            return LIR_CALL;
        case MIR_JUMP:
            return LIR_JMP;
        case MIR_JUMP_IF:
            return LIR_JMP_COND;
        case MIR_RETURN:
            return LIR_RET;
        case MIR_PRINT:
            return LIR_PRINT;
        default:
            return LIR_NOP;
    }
}

lir_func_t *lower_mir_to_lir(const mir_func_t *mir) {
    if (!mir)
        return NULL;

    lir_func_t *func = lir_create_func(mir->id);

    for (mir_block_t *m_blk = mir->blocks; m_blk; m_blk = m_blk->next_block) {
        lir_block_t *l_blk = lir_create_block(func);
        l_blk->id = m_blk->id;

        for (mir_instr_t *m_inst = m_blk->head; m_inst; m_inst = m_inst->next) {
            lir_operand_t none = { LIR_OPND_NONE, {0} };
            lir_operand_t l_dst = map_mir_opnd(m_inst->dst);
            lir_operand_t l_src1 = map_mir_opnd(m_inst->src1);
            lir_operand_t l_src2 = map_mir_opnd(m_inst->src2);

            if (m_inst->op == MIR_JUMP_IF) {
                lir_operand_t cond = map_mir_opnd(m_inst->dst);
                lir_operand_t target = map_mir_opnd(m_inst->src1);
                lir_append_instr(l_blk, LIR_JMP_COND, none, target, cond);
                continue;
            }

            if (m_inst->op == MIR_JUMP) {
                lir_operand_t target = map_mir_opnd(m_inst->dst);
                lir_append_instr(l_blk, LIR_JMP, none, target, none);
                continue;
            }

            if (m_inst->op >= MIR_CMP_GT && m_inst->op <= MIR_CMP_NE) {
                lir_append_instr(l_blk, map_mir_op(m_inst->op), l_dst, l_src1,
                                 l_src2);
                continue;
            }

            lir_append_instr(l_blk, map_mir_op(m_inst->op), l_dst, l_src1, l_src2);
        }
    }

    return func;
}
