#include "mir_lower.h"
#include "ir_lower.h"
#include <stdlib.h>
#include <string.h>

// Helper to generate a new virtual register
static uint32_t alloc_vreg(mir_func_t* func) {
    return func->next_vreg++;
}

// Forward declaration
static mir_operand_t lower_hir_node_to_mir(mir_func_t* func, mir_block_t** current_block, mir_block_t* loop_hdr, mir_block_t* loop_end, const hir_node_t* hir, lower_ctx_t *lctx);

static mir_operand_t lower_mir_call_by_name(
    mir_func_t *func, mir_block_t **current_block, mir_block_t *loop_hdr,
    mir_block_t *loop_end, lower_ctx_t *lctx, const char *name,
    struct hir_node **args, uint32_t argc) {
    mir_operand_t none = { MIR_OPND_NONE, {0} };
    if (!lctx || !name || !name[0])
        return none;

    int fidx = lower_find_func_index(lctx, name);
    if (fidx < 0)
        return none;

    /* Park every argument in a fresh vreg first: an argument may itself be a
     * call, which clobbers the ABI slots (vreg 0..n) and the R0 return slot. */
    uint32_t nargs = argc < Q_MAX_PARAMS ? argc : Q_MAX_PARAMS;
    mir_operand_t staged[Q_MAX_PARAMS];
    for (uint32_t i = 0; i < nargs; i++) {
        mir_operand_t arg = lower_hir_node_to_mir(
            func, current_block, loop_hdr, loop_end, args[i], lctx);
        if (arg.type == MIR_OPND_NONE)
            return none;
        mir_operand_t tmp = { MIR_OPND_VREG, {alloc_vreg(func)} };
        mir_append_instr(*current_block, MIR_MOVE, tmp, arg, none);
        staged[i] = tmp;
    }
    for (uint32_t i = 0; i < nargs; i++) {
        mir_operand_t slot = { MIR_OPND_VREG, {i} };
        mir_append_instr(*current_block, MIR_MOVE, slot, staged[i], none);
    }

    mir_operand_t fidx_op = { MIR_OPND_IMM, {(int64_t)fidx} };
    mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
    mir_append_instr(*current_block, MIR_CALL, none, fidx_op, none);
    mir_operand_t r0 = { MIR_OPND_VREG, {0} };
    mir_append_instr(*current_block, MIR_MOVE, dst, r0, none);
    return dst;
}

static mir_operand_t lower_hir_node_to_mir(mir_func_t* func, mir_block_t** current_block, mir_block_t* loop_hdr, mir_block_t* loop_end, const hir_node_t* hir, lower_ctx_t *lctx) {
    mir_operand_t none = { MIR_OPND_NONE, {0} };
    if (!hir || !*current_block) return none;

    switch (hir->kind) {
        case HIR_CONST: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            if (hir->as.constant.is_string && lctx) {
                uint32_t str_idx =
                    q_module_add_string(&lctx->module, hir->as.constant.str_value);
                mir_operand_t idx = { MIR_OPND_IMM, {(int64_t)str_idx} };
                mir_append_instr(*current_block, MIR_LOAD_STRING, dst, idx, none);
                return dst;
            }
            mir_operand_t imm = { MIR_OPND_IMM, {(int64_t)hir->as.constant.value} };
            mir_append_instr(*current_block, MIR_LOAD, dst, imm, none);
            return dst;
        }
        case HIR_LOAD: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_operand_t src = { MIR_OPND_VREG, {hir->as.load.var_id} };
            mir_append_instr(*current_block, MIR_MOVE, dst, src, none);
            return dst;
        }
        case HIR_STORE: {
            mir_operand_t val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.store.value, lctx);
            mir_operand_t dst = { MIR_OPND_VREG, {hir->as.store.var_id} };
            mir_append_instr(*current_block, MIR_MOVE, dst, val, none);
            return val;
        }
        case HIR_VAR_DECL: {
            mir_operand_t val = none;
            if (hir->as.var_decl.init_value) {
                val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.var_decl.init_value, lctx);
            }
            mir_operand_t dst = { MIR_OPND_VREG, {hir->as.var_decl.var_id} };
            if (val.type != MIR_OPND_NONE) {
                mir_append_instr(*current_block, MIR_MOVE, dst, val, none);
            }
            return dst;
        }
        case HIR_BINOP: {
            mir_operand_t arg1 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.binop.left, lctx);
            mir_operand_t arg2 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.binop.right, lctx);
            if (arg1.type == MIR_OPND_NONE || arg2.type == MIR_OPND_NONE)
                return none;
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_op_t op = MIR_ADD;
            switch (hir->as.binop.op) {
            case OP_ADD: op = MIR_ADD; break;
            case OP_SUB: op = MIR_SUB; break;
            case OP_MUL: op = MIR_MUL; break;
            case OP_DIV: op = MIR_DIV; break;
            case OP_MOD: op = MIR_MOD; break;
            case OP_PERCENT: {
              /* Spec §10.1: lower a % b as (a * b) / 100 */
              mir_operand_t prod = {MIR_OPND_VREG, {alloc_vreg(func)}};
              mir_append_instr(*current_block, MIR_MUL, prod, arg1, arg2);
              mir_operand_t c100 = {MIR_OPND_IMM, {.imm = 100}};
              mir_append_instr(*current_block, MIR_DIV, dst, prod, c100);
              return dst;
            }
            case OP_AND: op = MIR_AND; break;
            case OP_OR:  op = MIR_OR;  break;
            case OP_XOR: op = MIR_XOR; break;
            case OP_SHL: op = MIR_SHL; break;
            case OP_SHR: op = MIR_SHR; break;
            case OP_GT:  op = MIR_CMP_GT; break;
            case OP_LT:  op = MIR_CMP_LT; break;
            case OP_GE:  op = MIR_CMP_GE; break;
            case OP_LE:  op = MIR_CMP_LE; break;
            case OP_EQ:  op = MIR_CMP_EQ; break;
            case OP_NE:  op = MIR_CMP_NE; break;
            default: op = MIR_ADD; break;
            }
            mir_append_instr(*current_block, op, dst, arg1, arg2);
            return dst;
        }
        case HIR_INTRINSIC_CALL: {
            uint32_t bid = hir->as.intrinsic_call.intrinsic_id;
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            if (bid == BUILTIN_EXIT) {
                mir_operand_t arg = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    arg = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                    if (arg.type == MIR_OPND_NONE)
                        return none;
                }
                mir_append_instr(*current_block, MIR_EXIT, dst, arg, none);
                return dst;
            }
            if (bid == BUILTIN_ARG_COUNT) {
                mir_append_instr(*current_block, MIR_ARG_COUNT, dst, none, none);
                return dst;
            }
            if (bid == BUILTIN_GET_ARG) {
                mir_operand_t idx = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    idx = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                    if (idx.type == MIR_OPND_NONE)
                        return none;
                }
                mir_append_instr(*current_block, MIR_GET_ARG, dst, idx, none);
                return dst;
            }
            if (bid == BUILTIN_READ8) {
                mir_operand_t arg1 = none;
                mir_operand_t arg2 = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    arg1 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                }
                if (hir->as.intrinsic_call.argc > 1) {
                    arg2 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[1], lctx);
                }
                if (arg1.type == MIR_OPND_NONE || arg2.type == MIR_OPND_NONE)
                    return none;
                mir_append_instr(*current_block, MIR_LOAD_BYTE, dst, arg1, arg2);
                return dst;
            }
            if (bid == BUILTIN_WRITE8) {
                mir_operand_t arg1 = none;
                mir_operand_t arg2 = none;
                mir_operand_t arg3 = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    arg1 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                }
                if (hir->as.intrinsic_call.argc > 1) {
                    arg2 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[1], lctx);
                }
                if (hir->as.intrinsic_call.argc > 2) {
                    arg3 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[2], lctx);
                }
                if (arg1.type == MIR_OPND_NONE || arg2.type == MIR_OPND_NONE ||
                    arg3.type == MIR_OPND_NONE)
                    return none;
                mir_append_instr(*current_block, MIR_STORE_BYTE, arg3, arg1, arg2);
                mir_operand_t zero = { MIR_OPND_IMM, {0} };
                mir_append_instr(*current_block, MIR_MOVE, dst, zero, none);
                return dst;
            }
            if (bid == BUILTIN_READ64) {
                mir_operand_t arg1 = none;
                mir_operand_t arg2 = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    arg1 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                }
                if (hir->as.intrinsic_call.argc > 1) {
                    arg2 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[1], lctx);
                }
                if (arg1.type == MIR_OPND_NONE || arg2.type == MIR_OPND_NONE)
                    return none;
                mir_append_instr(*current_block, MIR_LOAD_WORD, dst, arg1, arg2);
                return dst;
            }
            if (bid == BUILTIN_WRITE64) {
                mir_operand_t arg1 = none;
                mir_operand_t arg2 = none;
                mir_operand_t arg3 = none;
                if (hir->as.intrinsic_call.argc > 0) {
                    arg1 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[0], lctx);
                }
                if (hir->as.intrinsic_call.argc > 1) {
                    arg2 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[1], lctx);
                }
                if (hir->as.intrinsic_call.argc > 2) {
                    arg3 = lower_hir_node_to_mir(
                        func, current_block, loop_hdr, loop_end,
                        hir->as.intrinsic_call.args[2], lctx);
                }
                if (arg1.type == MIR_OPND_NONE || arg2.type == MIR_OPND_NONE ||
                    arg3.type == MIR_OPND_NONE)
                    return none;
                mir_append_instr(*current_block, MIR_STORE_WORD, arg3, arg1, arg2);
                mir_operand_t zero = { MIR_OPND_IMM, {0} };
                mir_append_instr(*current_block, MIR_MOVE, dst, zero, none);
                return dst;
            }
            if (lctx && hir->as.intrinsic_call.callee_name[0]) {
                int fidx = lower_find_func_index(
                    lctx, hir->as.intrinsic_call.callee_name);
                if (fidx >= 0) {
                    return lower_mir_call_by_name(
                        func, current_block, loop_hdr, loop_end, lctx,
                        hir->as.intrinsic_call.callee_name,
                        hir->as.intrinsic_call.args,
                        hir->as.intrinsic_call.argc);
                }
            }
            return none;
        }
        case HIR_CALL: {
            int fidx = lctx ? lower_find_func_index(lctx, hir->as.call.callee_name)
                            : -1;
            if (fidx < 0)
                return none;

            /* Same ABI hazard as lower_mir_call_by_name: stage into fresh
             * vregs first, then fill slots 0..n-1 right before the call. */
            uint32_t nargs = hir->as.call.argc < Q_MAX_PARAMS
                                 ? hir->as.call.argc
                                 : Q_MAX_PARAMS;
            mir_operand_t staged[Q_MAX_PARAMS];
            for (uint32_t i = 0; i < nargs; i++) {
                mir_operand_t arg = lower_hir_node_to_mir(
                    func, current_block, loop_hdr, loop_end, hir->as.call.args[i],
                    lctx);
                mir_operand_t tmp = { MIR_OPND_VREG, {alloc_vreg(func)} };
                mir_append_instr(*current_block, MIR_MOVE, tmp, arg, none);
                staged[i] = tmp;
            }
            for (uint32_t i = 0; i < nargs; i++) {
                mir_operand_t slot = { MIR_OPND_VREG, {i} };
                mir_append_instr(*current_block, MIR_MOVE, slot, staged[i], none);
            }

            mir_operand_t fidx_op = { MIR_OPND_IMM, {(int64_t)fidx} };
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_append_instr(*current_block, MIR_CALL, none, fidx_op, none);
            mir_operand_t r0 = { MIR_OPND_VREG, {0} };
            mir_append_instr(*current_block, MIR_MOVE, dst, r0, none);
            return dst;
        }
        case HIR_PRINT: {
            mir_operand_t val =
                lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end,
                                      hir->as.print.value, lctx);
            mir_append_instr(*current_block, MIR_PRINT, none, val, none);
            return none;
        }
        case HIR_FIELD_LOAD: {
            mir_operand_t base = lower_hir_node_to_mir(
                func, current_block, loop_hdr, loop_end, hir->as.field_load.base,
                lctx);
            if (base.type == MIR_OPND_NONE)
                return none;
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_operand_t off = { MIR_OPND_IMM, {hir->as.field_load.offset} };
            mir_append_instr(*current_block, MIR_LOAD_WORD, dst, base, off);
            return dst;
        }
        case HIR_RETURN: {
            mir_operand_t val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.ret.value, lctx);
            mir_append_instr(*current_block, MIR_RETURN, val, none, none);
            return none;
        }
        case HIR_BREAK: {
            if (loop_end) {
                mir_operand_t end_opnd = { MIR_OPND_BLOCK, {loop_end->id} };
                mir_append_instr(*current_block, MIR_JUMP, end_opnd, none, none);
                (*current_block)->succ_true = loop_end;
                *current_block = mir_create_block(func); // Dead code block
            }
            return none;
        }
        case HIR_CONTINUE: {
            if (loop_hdr) {
                mir_operand_t hdr_opnd = { MIR_OPND_BLOCK, {loop_hdr->id} };
                mir_append_instr(*current_block, MIR_JUMP, hdr_opnd, none, none);
                (*current_block)->succ_true = loop_hdr;
                *current_block = mir_create_block(func); // Dead code block
            }
            return none;
        }
        case HIR_IF: {
            mir_operand_t cond = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.cond, lctx);
            
            mir_block_t* then_block = mir_create_block(func);
            mir_block_t* else_block = mir_create_block(func);
            mir_block_t* merge_block = mir_create_block(func);
            
            (*current_block)->succ_true = then_block;
            (*current_block)->succ_false = else_block;
            
            mir_operand_t then_opnd = { MIR_OPND_BLOCK, {then_block->id} };
            mir_operand_t else_opnd = { MIR_OPND_BLOCK, {else_block->id} };
            mir_append_instr(*current_block, MIR_JUMP_IF, cond, then_opnd, none);
            /* Fall-through after JUMP_IF reaches the next block in linear order
             * (then). Jump over it so the false path runs else instead. */
            mir_append_instr(*current_block, MIR_JUMP, else_opnd, none, none);
            (*current_block)->succ_false = else_block;

            // Generate then
            *current_block = then_block;
            lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.then_block, lctx);
            mir_operand_t merge_opnd = { MIR_OPND_BLOCK, {merge_block->id} };
            mir_append_instr(*current_block, MIR_JUMP, merge_opnd, none, none);
            (*current_block)->succ_true = merge_block;
            
            // Generate else
            *current_block = else_block;
            if (hir->as.if_stmt.else_block) {
                lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.else_block, lctx);
            }
            mir_append_instr(*current_block, MIR_JUMP, merge_opnd, none, none);
            (*current_block)->succ_true = merge_block;
            
            *current_block = merge_block;
            return none;
        }
        case HIR_LOOP: {
            mir_block_t *hdr = mir_create_block(func);
            mir_block_t *body_blk = mir_create_block(func);
            mir_block_t *end_blk = mir_create_block(func);

            mir_operand_t hdr_op = { MIR_OPND_BLOCK, {hdr->id} };
            mir_operand_t body_op = { MIR_OPND_BLOCK, {body_blk->id} };
            mir_operand_t end_op = { MIR_OPND_BLOCK, {end_blk->id} };

            mir_append_instr(*current_block, MIR_JUMP, hdr_op, none, none);
            (*current_block)->succ_true = hdr;

            *current_block = hdr;

            /* while desugar: loop { if cond { body } else { break } } */
            hir_node_t *inner = (hir->as.block.count == 1 && hir->as.block.body)
                                    ? hir->as.block.body[0]
                                    : NULL;
            int is_while = inner && inner->kind == HIR_IF &&
                           inner->as.if_stmt.else_block &&
                           inner->as.if_stmt.else_block->kind == HIR_BREAK;

            if (is_while) {
                mir_operand_t cond = lower_hir_node_to_mir(
                    func, current_block, hdr, end_blk, inner->as.if_stmt.cond, lctx);
                mir_append_instr(*current_block, MIR_JUMP_IF, cond, body_op, none);
                (*current_block)->succ_false = end_blk;
                mir_append_instr(*current_block, MIR_JUMP, end_op, none, none);
                (*current_block)->succ_true = end_blk;

                *current_block = body_blk;
                lower_hir_node_to_mir(func, current_block, hdr, end_blk,
                                      inner->as.if_stmt.then_block, lctx);
                mir_append_instr(*current_block, MIR_JUMP, hdr_op, none, none);
                (*current_block)->succ_true = hdr;

                *current_block = end_blk;
            } else {
                mir_append_instr(*current_block, MIR_JUMP, body_op, none, none);
                (*current_block)->succ_true = body_blk;
                *current_block = body_blk;
                if (hir->as.block.body) {
                    for (uint32_t i = 0; i < hir->as.block.count; i++) {
                        lower_hir_node_to_mir(func, current_block, hdr, end_blk,
                                              hir->as.block.body[i], lctx);
                    }
                }
                mir_append_instr(*current_block, MIR_JUMP, hdr_op, none, none);
                (*current_block)->succ_true = hdr;
                *current_block = end_blk;
            }
            return none;
        }
        case HIR_BLOCK: {
            mir_operand_t last_val = none;
            if (hir->as.block.body) {
                for (uint32_t i = 0; i < hir->as.block.count; i++) {
                    last_val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.block.body[i], lctx);
                }
            }
            return last_val;
        }
    }

    return none;
}

mir_func_t* lower_hir_to_mir(const hir_node_t* hir, uint32_t func_id, lower_ctx_t *lctx) {
    if (!hir) return NULL;
    
    mir_func_t* func = mir_create_func(func_id);
    if (lctx)
        func->next_vreg = lctx->vreg_alloc.next_index;
    else
        func->next_vreg = 16;
    mir_block_t* current_block = func->entry_block;
    if (!current_block) {
        current_block = mir_create_block(func);
    }
    
    lower_hir_node_to_mir(func, &current_block, NULL, NULL, hir, lctx);

    if (lctx && func->next_vreg > lctx->vreg_alloc.next_index)
        lctx->vreg_alloc.next_index = func->next_vreg;
    
    return func;
}
