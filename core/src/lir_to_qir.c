#include "lir_to_qir.h"
#include "q_ir.h"
#include <stdlib.h>
#include <string.h>

static q_operand_t map_lir_opnd(const lir_operand_t *op, uint32_t label_offset) {
    switch (op->type) {
    case LIR_OPND_VREG_INT:
    case LIR_OPND_VREG_FLOAT:
        return q_vreg(op->as.vreg);
    case LIR_OPND_PHYS_REG:
        return q_vreg(op->as.phys_reg);
    case LIR_OPND_IMM:
        return q_imm(op->as.imm);
    case LIR_OPND_LABEL:
        return q_label((uint32_t)(op->as.label_id + label_offset));
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
    case LIR_EXIT:
        return Q_EXIT;
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
        return Q_CMP_NE;
    case LIR_MOD:
        return Q_MOD;
    case LIR_AND:
        return Q_AND;
    case LIR_OR:
        return Q_OR;
    case LIR_XOR:
        return Q_XOR;
    case LIR_SHL:
        return Q_SHL;
    case LIR_SHR:
        return Q_SHR;
    default:
        return Q_NOP;
    }
}

int lir_to_qir_append(lower_ctx_t *ctx, const lir_func_t *lir) {
    if (!ctx || !ctx->current_func || !lir)
        return -1;

    q_function_t *fn = ctx->current_func;
    /* Allocate pipeline block labels from the shared label counter so they
     * can never collide with legacy fresh_label() ids emitted by lower_stmt
     * fallbacks within the same function. */
    uint32_t label_offset = ctx->pipeline_label_base;
    if (ctx->label_counter > label_offset)
        label_offset = ctx->label_counter;
    uint32_t max_block_id = 0;

    for (const lir_block_t *blk = lir->blocks; blk; blk = blk->next)
        if (blk->id > max_block_id)
            max_block_id = blk->id;

    /* Label placed after the whole chunk. Open blocks (no LIR_JMP/LIR_RET
     * terminator, e.g. a loop's empty exit block or an if's merge block)
     * must jump here explicitly: their layout position can be followed by
     * unrelated nested blocks, so plain fallthrough would re-enter the
     * middle of a loop or branch body. */
    uint32_t chunk_end_label = label_offset + max_block_id + 1;

    for (const lir_block_t *blk = lir->blocks; blk; blk = blk->next) {
        q_instruction_t bl = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        bl.patch_id = blk->id + label_offset;
        q_func_emit(fn, bl);

        const lir_instr_t *last = NULL;
        for (const lir_instr_t *ins = blk->head; ins; ins = ins->next)
            last = ins;
        int has_terminator = last && (last->op == LIR_JMP || last->op == LIR_RET);

        for (const lir_instr_t *ins = blk->head; ins; ins = ins->next) {
            if (ins->op == LIR_PRINT) {
                q_instruction_t pin =
                    q_instr(Q_PRINT, q_none(), map_lir_opnd(&ins->src1, label_offset), q_none());
                strncpy(pin.operand_type, "int", sizeof(pin.operand_type) - 1);
                q_func_emit(fn, pin);
                continue;
            }

            if (ins->op == LIR_LOAD_STRING) {
                q_instruction_t qload =
                    q_instr(Q_LOAD, map_lir_opnd(&ins->dst, label_offset),
                            q_str((uint32_t)ins->src1.as.imm), q_none());
                q_func_emit(fn, qload);
                continue;
            }

            if (ins->op == LIR_ARG_COUNT) {
                q_func_emit(fn, q_instr(Q_ARG_COUNT,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        q_none(), q_none()));
                continue;
            }

            if (ins->op == LIR_GET_ARG) {
                q_func_emit(fn, q_instr(Q_GET_ARG,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        q_none()));
                continue;
            }

            if (ins->op == LIR_LOAD_BYTE) {
                q_func_emit(fn, q_instr(Q_LOAD_BYTE,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        map_lir_opnd(&ins->src2, label_offset)));
                continue;
            }

            if (ins->op == LIR_STORE_BYTE) {
                q_func_emit(fn, q_instr(Q_STORE_BYTE,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        map_lir_opnd(&ins->src2, label_offset)));
                continue;
            }

            if (ins->op == LIR_LOAD_WORD) {
                q_func_emit(fn, q_instr(Q_LOAD_WORD,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        map_lir_opnd(&ins->src2, label_offset)));
                continue;
            }

            if (ins->op == LIR_STORE_WORD) {
                q_func_emit(fn, q_instr(Q_STORE_WORD,
                                        map_lir_opnd(&ins->dst, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        map_lir_opnd(&ins->src2, label_offset)));
                continue;
            }

            if (ins->op == LIR_RET) {
                q_func_emit(fn, q_instr(Q_RET, q_none(),
                                        map_lir_opnd(&ins->dst, label_offset), q_none()));
                continue;
            }

            if (ins->op == LIR_CALL) {
                q_operand_t fidx = q_func_idx((uint32_t)ins->src1.as.imm);
                q_func_emit(fn, q_instr(Q_CALL_FUNC, q_none(), fidx, q_none()));
                if (ins->dst.type != LIR_OPND_NONE) {
                    q_func_emit(fn, q_instr(Q_MOVE, map_lir_opnd(&ins->dst, label_offset),
                                            q_vreg(0), q_none()));
                }
                continue;
            }

            if (ins->op == LIR_JMP) {
                q_func_emit(fn, q_instr(Q_JUMP, q_none(),
                                        map_lir_opnd(&ins->src1, label_offset),
                                        q_none()));
                continue;
            }

            if (ins->op == LIR_JMP_COND) {
                q_func_emit(fn, q_instr(Q_JUMP_IF, q_none(),
                                        map_lir_opnd(&ins->src2, label_offset),
                                        map_lir_opnd(&ins->src1, label_offset)));
                continue;
            }

            q_opcode_t qop = map_lir_op(ins->op);
            q_func_emit(fn, q_instr(qop, map_lir_opnd(&ins->dst, label_offset),
                                    map_lir_opnd(&ins->src1, label_offset),
                                    map_lir_opnd(&ins->src2, label_offset)));
        }

        if (!has_terminator)
            q_func_emit(fn, q_instr(Q_JUMP, q_none(),
                                    q_label(chunk_end_label), q_none()));
    }

    {
        q_instruction_t el = q_instr(Q_LABEL, q_none(), q_none(), q_none());
        el.patch_id = chunk_end_label;
        q_func_emit(fn, el);
    }

    /* Next chunk starts past every label used here (blocks + chunk end),
     * otherwise its block 0 collides with this chunk's labels and jumps
     * resolve to the wrong instruction. */
    ctx->pipeline_label_base = chunk_end_label + 1;
    if (ctx->label_counter < ctx->pipeline_label_base)
        ctx->label_counter = ctx->pipeline_label_base;
    return 0;
}
