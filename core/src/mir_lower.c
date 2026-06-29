#include "mir_lower.h"
#include <stdlib.h>

// Helper to generate a new virtual register
static uint32_t alloc_vreg(mir_func_t* func) {
    return func->next_vreg++;
}

// Forward declaration
static mir_operand_t lower_hir_node_to_mir(mir_func_t* func, mir_block_t** current_block, mir_block_t* loop_hdr, mir_block_t* loop_end, const hir_node_t* hir);

static mir_operand_t lower_hir_node_to_mir(mir_func_t* func, mir_block_t** current_block, mir_block_t* loop_hdr, mir_block_t* loop_end, const hir_node_t* hir) {
    mir_operand_t none = { MIR_OPND_NONE, {0} };
    if (!hir || !*current_block) return none;

    switch (hir->kind) {
        case HIR_CONST: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
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
            mir_operand_t val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.store.value);
            mir_operand_t dst = { MIR_OPND_VREG, {hir->as.store.var_id} };
            mir_append_instr(*current_block, MIR_MOVE, dst, val, none);
            return val;
        }
        case HIR_VAR_DECL: {
            mir_operand_t val = none;
            if (hir->as.var_decl.init_value) {
                val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.var_decl.init_value);
            }
            mir_operand_t dst = { MIR_OPND_VREG, {hir->as.var_decl.var_id} };
            if (val.type != MIR_OPND_NONE) {
                mir_append_instr(*current_block, MIR_MOVE, dst, val, none);
            }
            return dst;
        }
        case HIR_BINOP: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_operand_t arg1 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.binop.left);
            mir_operand_t arg2 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.binop.right);
            // In a real compiler, map `hir->as.binop.op` to `MIR_ADD`, `MIR_SUB`, etc.
            mir_op_t op = MIR_ADD; // Simplification
            if (hir->as.binop.op == 1) op = MIR_SUB; // Assuming OP_SUB is 1
            else if (hir->as.binop.op == 2) op = MIR_MUL;
            else if (hir->as.binop.op == 3) op = MIR_DIV;
            mir_append_instr(*current_block, op, dst, arg1, arg2);
            return dst;
        }
        case HIR_INTRINSIC_CALL: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_operand_t arg1 = none;
            mir_operand_t arg2 = none;
            if (hir->as.intrinsic_call.argc > 0) {
                arg1 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.intrinsic_call.args[0]);
            }
            if (hir->as.intrinsic_call.argc > 1) {
                arg2 = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.intrinsic_call.args[1]);
            }
            mir_append_instr(*current_block, MIR_INTRINSIC, dst, arg1, arg2);
            return dst;
        }
        case HIR_CALL: {
            mir_operand_t dst = { MIR_OPND_VREG, {alloc_vreg(func)} };
            mir_operand_t callee = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.call.callee);
            // Ignore arguments mapping for this stub
            mir_append_instr(*current_block, MIR_CALL, dst, callee, none);
            return dst;
        }
        case HIR_RETURN: {
            mir_operand_t val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.ret.value);
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
            mir_operand_t cond = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.cond);
            
            mir_block_t* then_block = mir_create_block(func);
            mir_block_t* else_block = mir_create_block(func);
            mir_block_t* merge_block = mir_create_block(func);
            
            (*current_block)->succ_true = then_block;
            (*current_block)->succ_false = else_block;
            
            mir_operand_t then_opnd = { MIR_OPND_BLOCK, {then_block->id} };
            mir_append_instr(*current_block, MIR_JUMP_IF, cond, then_opnd, none);
            
            // Generate then
            *current_block = then_block;
            lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.then_block);
            mir_operand_t merge_opnd = { MIR_OPND_BLOCK, {merge_block->id} };
            mir_append_instr(*current_block, MIR_JUMP, merge_opnd, none, none);
            (*current_block)->succ_true = merge_block;
            
            // Generate else
            *current_block = else_block;
            if (hir->as.if_stmt.else_block) {
                lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.if_stmt.else_block);
            }
            mir_append_instr(*current_block, MIR_JUMP, merge_opnd, none, none);
            (*current_block)->succ_true = merge_block;
            
            *current_block = merge_block;
            return none;
        }
        case HIR_LOOP: {
            mir_block_t* new_loop_hdr = mir_create_block(func);
            mir_block_t* loop_body = mir_create_block(func);
            mir_block_t* new_loop_end = mir_create_block(func);
            
            mir_operand_t hdr_opnd = { MIR_OPND_BLOCK, {new_loop_hdr->id} };
            mir_append_instr(*current_block, MIR_JUMP, hdr_opnd, none, none);
            (*current_block)->succ_true = new_loop_hdr;
            
            *current_block = new_loop_hdr;
            // Unconditional loop logic for stub
            mir_operand_t body_opnd = { MIR_OPND_BLOCK, {loop_body->id} };
            mir_append_instr(*current_block, MIR_JUMP, body_opnd, none, none);
            (*current_block)->succ_true = loop_body;
            
            *current_block = loop_body;
            // Body is usually block
            if (hir->as.block.body) {
                for (uint32_t i = 0; i < hir->as.block.count; i++) {
                    lower_hir_node_to_mir(func, current_block, new_loop_hdr, new_loop_end, hir->as.block.body[i]);
                }
            }
            
            mir_append_instr(*current_block, MIR_JUMP, hdr_opnd, none, none);
            (*current_block)->succ_true = new_loop_hdr;
            
            *current_block = new_loop_end;
            return none;
        }
        case HIR_BLOCK: {
            mir_operand_t last_val = none;
            if (hir->as.block.body) {
                for (uint32_t i = 0; i < hir->as.block.count; i++) {
                    last_val = lower_hir_node_to_mir(func, current_block, loop_hdr, loop_end, hir->as.block.body[i]);
                }
            }
            return last_val;
        }
    }

    return none;
}

mir_func_t* lower_hir_to_mir(const hir_node_t* hir, uint32_t func_id) {
    if (!hir) return NULL;
    
    mir_func_t* func = mir_create_func(func_id);
    mir_block_t* current_block = func->entry_block;
    if (!current_block) {
        current_block = mir_create_block(func);
    }
    
    lower_hir_node_to_mir(func, &current_block, NULL, NULL, hir);
    
    return func;
}
