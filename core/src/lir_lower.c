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
        case MIR_OPND_NONE:
        default:
            break;
    }
    return l;
}

static lir_op_t map_mir_op(mir_op_t m) {
    switch (m) {
        case MIR_MOVE:
        case MIR_LOAD:
        case MIR_STORE: return LIR_MOV;
        case MIR_ADD: return LIR_ADD;
        case MIR_SUB: return LIR_SUB;
        case MIR_MUL: return LIR_MUL;
        case MIR_DIV: return LIR_DIV;
        case MIR_CALL: 
        case MIR_INTRINSIC: return LIR_CALL;
        case MIR_JUMP: return LIR_JMP;
        case MIR_JUMP_IF: return LIR_JMP_COND;
        case MIR_RETURN: return LIR_RET;
        case MIR_NOP:
        default: return LIR_NOP;
    }
}

lir_func_t* lower_mir_to_lir(const mir_func_t* mir) {
    if (!mir) return NULL;
    
    lir_func_t* func = lir_create_func(mir->id);
    
    // Map blocks
    mir_block_t* m_blk = mir->blocks;
    while (m_blk) {
        lir_block_t* l_blk = lir_create_block(func);
        l_blk->id = m_blk->id; // Keep block IDs synchronized
        
        mir_instr_t* m_inst = m_blk->head;
        while (m_inst) {
            lir_op_t l_op = map_mir_op(m_inst->op);
            lir_operand_t l_dst = map_mir_opnd(m_inst->dst);
            lir_operand_t l_src1 = map_mir_opnd(m_inst->src1);
            lir_operand_t l_src2 = map_mir_opnd(m_inst->src2);
            
            // For jump-if, LIR usually separates CMP and JMP.
            if (m_inst->op == MIR_JUMP_IF) {
                // Draft simplification: assume src1 is truthy value check
                lir_operand_t none = { LIR_OPND_NONE, {0} };
                lir_operand_t imm0 = { LIR_OPND_IMM, {0} };
                lir_append_instr(l_blk, LIR_CMP, l_src1, imm0, none);
            }
            
            lir_append_instr(l_blk, l_op, l_dst, l_src1, l_src2);
            
            m_inst = m_inst->next;
        }
        
        m_blk = m_blk->next_block;
    }
    
    return func;
}
