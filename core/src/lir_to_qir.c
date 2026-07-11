#include "lir_to_qir.h"
#include "q_ir.h"
#include <stdlib.h>
#include <string.h>

static q_operand_t map_lir_opnd(const lir_operand_t *op) {
    switch (op->type) {
    case LIR_OPND_VREG_INT:
    case LIR_OPND_VREG_FLOAT:
        return q_vreg(op->as.vreg);
    case LIR_OPND_PHYS_REG:
        return q_vreg(op->as.phys_reg);
    case LIR_OPND_IMM:
        return q_imm(op->as.imm);
    case LIR_OPND_LABEL:
        return q_label((uint32_t)op->as.label_id);
    case LIR_OPND_STACK_MEM:
        return q_imm(op->as.stack_offset);
    default:
        return q_none();
    }
}

static q_opcode_t map_lir_op(lir_op_t op) {
    switch (op) {
    case LIR_MOV:
        return Q_MOVE;
    case LIR_ADD:
        return Q_ADD;
    case LIR_SUB:
        return Q_SUB;
    case LIR_MUL:
        return Q_MUL;
    case LIR_DIV:
        return Q_DIV;
    case LIR_CALL:
        return Q_CALL;
    case LIR_JMP:
        return Q_JUMP;
    case LIR_JMP_COND:
        return Q_JUMP_IF;
    case LIR_RET:
        return Q_RET;
    case LIR_LOAD:
        return Q_LOAD;
    case LIR_STORE:
        return Q_STORE;
    case LIR_CMP_GT:
        return Q_CMP_GT;
    case LIR_CMP_LT:
        return Q_CMP_LT;
    case LIR_CMP_GE:
        return Q_CMP_GE;
    case LIR_CMP_LE:
        return Q_CMP_LE;
    case LIR_CMP_EQ:
        return Q_CMP_EQ;
    case LIR_CMP_NE:
        return Q_CMP_EQ;
    default:
        return Q_NOP;
    }
}

int lir_to_qir_append(lower_ctx_t *ctx, const lir_func_t *lir) {
    if (!ctx || !ctx->current_func || !lir)
        return -1;

    q_function_t *fn = ctx->current_func;

    for (const lir_block_t *blk = lir->blocks; blk; blk = blk->next) {
        q_instruction_t bl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        bl.patch_id = blk->id;
        q_func_emit(fn, bl);

        for (const lir_instr_t *ins = blk->head; ins; ins = ins->next) {
            if (ins->op == LIR_PRINT) {
                q_instruction_t pin =
                    q_instr(Q_PRINT, q_none(), map_lir_opnd(&ins->src1), q_none());
                strncpy(pin.operand_type, "int", sizeof(pin.operand_type) - 1);
                q_func_emit(fn, pin);
                continue;
            }

            if (ins->op == LIR_LOAD_STRING) {
                q_instruction_t qload =
                    q_instr(Q_LOAD, map_lir_opnd(&ins->dst),
                            q_str((uint32_t)ins->src1.as.imm), q_none());
                q_func_emit(fn, qload);
                continue;
            }

            if (ins->op == LIR_CALL) {
                q_operand_t fidx = q_func_idx((uint32_t)ins->src1.as.imm);
                q_func_emit(fn, q_instr(Q_CALL_FUNC, q_none(), fidx, q_none()));
                if (ins->dst.type != LIR_OPND_NONE) {
                    q_func_emit(fn, q_instr(Q_MOVE, map_lir_opnd(&ins->dst),
                                            q_vreg(0), q_none()));
                }
                continue;
            }

            if (ins->op == LIR_JMP) {
                q_func_emit(fn, q_instr(Q_JUMP, q_none(), map_lir_opnd(&ins->src1),
                                        q_none()));
                continue;
            }

            if (ins->op == LIR_JMP_COND) {
                q_func_emit(fn, q_instr(Q_JUMP_IF, q_none(),
                                        map_lir_opnd(&ins->src2),
                                        map_lir_opnd(&ins->src1)));
                continue;
            }

            q_opcode_t qop = map_lir_op(ins->op);
            q_func_emit(fn, q_instr(qop, map_lir_opnd(&ins->dst),
                                    map_lir_opnd(&ins->src1),
                                    map_lir_opnd(&ins->src2)));
        }
    }

    return 0;
}
