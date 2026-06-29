#include "lir_rewrite.h"
#include <stdlib.h>
#include <string.h>

static lir_phys_reg_t get_scratch_reg(int index) {
    int found = 0;
    for (int i = 0; i < LIR_REG_MAX; i++) {
        const lir_phys_reg_info_t *info = lir_get_phys_reg_info((lir_phys_reg_t)i);
        if (info && (info->roles & LIR_REG_ROLE_SCRATCH)) {
            if (found == index) return (lir_phys_reg_t)i;
            found++;
        }
    }
    // Fallback if not enough scratch regs
    return LIR_REG_R8; 
}

static void process_instruction_operands(lir_func_t *func, lir_block_t *block, lir_instr_t *instr, lir_interval_ctx_t *ctx) {
    // Check SRC1
    if (instr->src1.type == LIR_OPND_VREG_INT || instr->src1.type == LIR_OPND_VREG_FLOAT) {
        uint32_t vreg = instr->src1.as.vreg;
        lir_live_interval_t *interval = &ctx->intervals[vreg];
        if (interval->phys_reg != UINT32_MAX) { // NO_REG
            instr->src1.type = LIR_OPND_PHYS_REG;
            instr->src1.as.phys_reg = interval->phys_reg;
        } else {
            lir_phys_reg_t scratch = get_scratch_reg(0);
            instr->src1.type = LIR_OPND_PHYS_REG;
            instr->src1.as.phys_reg = scratch;
            
            lir_instr_t *load = malloc(sizeof(lir_instr_t));
            memset(load, 0, sizeof(lir_instr_t));
            load->op = LIR_LOAD;
            load->dst.type = LIR_OPND_PHYS_REG;
            load->dst.as.phys_reg = scratch;
            load->src1.type = LIR_OPND_STACK_MEM;
            load->src1.as.stack_offset = interval->stack_offset;
            
            if (block->head == instr) {
                load->next = instr;
                block->head = load;
            } else {
                lir_instr_t *prev = block->head;
                while (prev && prev->next != instr) prev = prev->next;
                if (prev) {
                    prev->next = load;
                    load->next = instr;
                }
            }
        }
    }
    
    // Check SRC2
    if (instr->src2.type == LIR_OPND_VREG_INT || instr->src2.type == LIR_OPND_VREG_FLOAT) {
        uint32_t vreg = instr->src2.as.vreg;
        lir_live_interval_t *interval = &ctx->intervals[vreg];
        if (interval->phys_reg != UINT32_MAX) {
            instr->src2.type = LIR_OPND_PHYS_REG;
            instr->src2.as.phys_reg = interval->phys_reg;
        } else {
            // Use second scratch reg if possible
            lir_phys_reg_t scratch = get_scratch_reg(1);
            instr->src2.type = LIR_OPND_PHYS_REG;
            instr->src2.as.phys_reg = scratch;
            
            lir_instr_t *load = malloc(sizeof(lir_instr_t));
            memset(load, 0, sizeof(lir_instr_t));
            load->op = LIR_LOAD;
            load->dst.type = LIR_OPND_PHYS_REG;
            load->dst.as.phys_reg = scratch;
            load->src1.type = LIR_OPND_STACK_MEM;
            load->src1.as.stack_offset = interval->stack_offset;
            
            if (block->head == instr) {
                load->next = instr;
                block->head = load;
            } else {
                lir_instr_t *prev = block->head;
                while (prev && prev->next != instr) prev = prev->next;
                if (prev) {
                    prev->next = load;
                    load->next = instr;
                }
            }
        }
    }
    
    // Check DST
    if (instr->dst.type == LIR_OPND_VREG_INT || instr->dst.type == LIR_OPND_VREG_FLOAT) {
        uint32_t vreg = instr->dst.as.vreg;
        lir_live_interval_t *interval = &ctx->intervals[vreg];
        if (interval->phys_reg != UINT32_MAX) {
            instr->dst.type = LIR_OPND_PHYS_REG;
            instr->dst.as.phys_reg = interval->phys_reg;
        } else {
            lir_phys_reg_t scratch = get_scratch_reg(0);
            instr->dst.type = LIR_OPND_PHYS_REG;
            instr->dst.as.phys_reg = scratch;
            
            lir_instr_t *store = malloc(sizeof(lir_instr_t));
            memset(store, 0, sizeof(lir_instr_t));
            store->op = LIR_STORE;
            store->dst.type = LIR_OPND_STACK_MEM;
            store->dst.as.stack_offset = interval->stack_offset;
            store->src1.type = LIR_OPND_PHYS_REG;
            store->src1.as.phys_reg = scratch;
            
            store->next = instr->next;
            instr->next = store;
            if (block->tail == instr) {
                block->tail = store;
            }
        }
    }
}

void lir_rewrite_operands(lir_func_t *func, lir_interval_ctx_t *ctx) {
    if (!func || !ctx) return;
    
    lir_block_t *b = func->blocks;
    while (b) {
        lir_instr_t *instr = b->head;
        while (instr) {
            lir_instr_t *next_instr = instr->next;
            process_instruction_operands(func, b, instr, ctx);
            instr = next_instr;
        }
        b = b->next;
    }
}
