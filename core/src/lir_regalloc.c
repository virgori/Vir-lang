#include "lir_regalloc.h"
#include <stdlib.h>
#include <string.h>

#define NUM_PHYS_REGS 5 // R0 to R4
#define NO_REG UINT32_MAX

typedef struct {
    lir_live_interval_t *interval;
} active_item_t;

static int compare_start(const void *a, const void *b) {
    lir_live_interval_t *ia = *(lir_live_interval_t **)a;
    lir_live_interval_t *ib = *(lir_live_interval_t **)b;
    if (ia->start_instr < ib->start_instr) return -1;
    if (ia->start_instr > ib->start_instr) return 1;
    return 0;
}

static int compare_end(const void *a, const void *b) {
    active_item_t *ia = (active_item_t *)a;
    active_item_t *ib = (active_item_t *)b;
    if (ia->interval->end_instr < ib->interval->end_instr) return -1;
    if (ia->interval->end_instr > ib->interval->end_instr) return 1;
    return 0;
}

static void expire_old_intervals(lir_live_interval_t *i, active_item_t *active, uint32_t *active_count, bool *free_regs) {
    // Sort active by end_instr
    qsort(active, *active_count, sizeof(active_item_t), compare_end);
    
    for (uint32_t j = 0; j < *active_count; ) {
        if (active[j].interval->end_instr >= i->start_instr) {
            return;
        }
        
        free_regs[active[j].interval->phys_reg] = true;
        
        // Remove from active list
        for (uint32_t k = j; k < *active_count - 1; k++) {
            active[k] = active[k + 1];
        }
        (*active_count)--;
    }
}

static void spill_at_interval(lir_live_interval_t *i, active_item_t *active, uint32_t *active_count, lir_func_t *func) {
    active_item_t *spill_cand = &active[*active_count - 1];
    
    if (spill_cand->interval->end_instr > i->end_instr) {
        // Evict candidate
        i->phys_reg = spill_cand->interval->phys_reg;
        
        spill_cand->interval->phys_reg = NO_REG;
        func->stack_size += 8;
        spill_cand->interval->stack_offset = -(int32_t)func->stack_size;
        
        // Replace in active list
        spill_cand->interval = i;
        qsort(active, *active_count, sizeof(active_item_t), compare_end);
    } else {
        // Spill i
        i->phys_reg = NO_REG;
        func->stack_size += 8;
        i->stack_offset = -(int32_t)func->stack_size;
    }
}

bool lir_allocate_registers(lir_func_t *func, lir_interval_ctx_t *ctx) {
    if (!func || !ctx) return false;
    
    uint32_t live_count = 0;
    for (uint32_t i = 0; i <= ctx->max_vreg; i++) {
        if (ctx->intervals[i].is_live) live_count++;
    }
    
    if (live_count == 0) return true;
    
    lir_live_interval_t **sorted = malloc(sizeof(lir_live_interval_t *) * live_count);
    uint32_t idx = 0;
    for (uint32_t i = 0; i <= ctx->max_vreg; i++) {
        if (ctx->intervals[i].is_live) {
            sorted[idx++] = &ctx->intervals[i];
        }
    }
    
    qsort(sorted, live_count, sizeof(lir_live_interval_t *), compare_start);
    
    // We only allocate registers that are not reserved and not scratch.
    // Let's count them.
    uint32_t allocatable_regs = 0;
    for (int i = 0; i < LIR_REG_MAX; i++) {
        const lir_phys_reg_info_t *info = lir_get_phys_reg_info(i);
        if (info && !(info->roles & LIR_REG_ROLE_RESERVED) && !(info->roles & LIR_REG_ROLE_SCRATCH)) {
            allocatable_regs++;
        }
    }
    
    active_item_t *active = malloc(sizeof(active_item_t) * allocatable_regs);
    uint32_t active_count = 0;
    
    bool free_regs[LIR_REG_MAX];
    for (int i = 0; i < LIR_REG_MAX; i++) {
        const lir_phys_reg_info_t *info = lir_get_phys_reg_info(i);
        if (info && !(info->roles & LIR_REG_ROLE_RESERVED) && !(info->roles & LIR_REG_ROLE_SCRATCH)) {
            free_regs[i] = true;
        } else {
            free_regs[i] = false;
        }
    }
    
    for (uint32_t i = 0; i < live_count; i++) {
        lir_live_interval_t *interval = sorted[i];
        
        expire_old_intervals(interval, active, &active_count, free_regs);
        
        int reg = -1;
        for (int r = 0; r < LIR_REG_MAX; r++) {
            if (free_regs[r]) {
                reg = r;
                break;
            }
        }
        
        if (reg == -1) {
            spill_at_interval(interval, active, &active_count, func);
        } else {
            interval->phys_reg = reg;
            free_regs[reg] = false;
            
            active[active_count].interval = interval;
            active_count++;
            qsort(active, active_count, sizeof(active_item_t), compare_end);
        }
    }
    
    free(active);
    free(sorted);
    
    // Note: We no longer rewrite operands here!
    // The Rewrite pass (`lir_rewrite.c`) will consume `ctx->intervals`.
    return true;
}
