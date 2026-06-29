#include "mir_pass.h"
#include "mir_cfg.h"
#include "mir_ssa.h"
#include <stdlib.h>
#include <stdio.h>

void mir_pm_init(mir_pass_manager_t* pm) {
    if (!pm) return;
    pm->passes = NULL;
    pm->tail = NULL;
    pm->valid_analyses = MIR_ANALYSIS_NONE;
}

void mir_pm_add_pass(mir_pass_manager_t* pm, const char* name, uint32_t requires, uint32_t preserves, void (*run)(mir_func_t*)) {
    if (!pm) return;
    mir_pass_t* pass = (mir_pass_t*)malloc(sizeof(mir_pass_t));
    pass->name = name;
    pass->requires = requires;
    pass->preserves = preserves;
    pass->run = run;
    pass->next = NULL;
    
    if (!pm->passes) {
        pm->passes = pass;
    } else {
        pm->tail->next = pass;
    }
    pm->tail = pass;
}

void mir_pass_cfg_run(mir_func_t* func) { mir_build_cfg(func); }
void mir_pass_dom_run(mir_func_t* func) { mir_compute_dominators(func); }
void mir_pass_ssa_run(mir_func_t* func) { mir_build_ssa(func); }

static void ensure_analysis(mir_pass_manager_t* pm, mir_func_t* func, uint32_t analysis_flag, void (*run)(mir_func_t*), const char* name) {
    if (!(pm->valid_analyses & analysis_flag)) {
        // printf("[PassManager] Running implicit %s\n", name);
        run(func);
        pm->valid_analyses |= analysis_flag;
    }
}

void mir_pm_run(mir_pass_manager_t* pm, mir_func_t* func) {
    if (!pm || !func) return;
    
    mir_pass_t* curr = pm->passes;
    while (curr) {
        // Ensure required analyses are met
        if (curr->requires & MIR_ANALYSIS_CFG) {
            ensure_analysis(pm, func, MIR_ANALYSIS_CFG, mir_pass_cfg_run, "CFGPass");
        }
        if (curr->requires & MIR_ANALYSIS_DOMINATORS) {
            // Dominators implicitly require CFG
            ensure_analysis(pm, func, MIR_ANALYSIS_CFG, mir_pass_cfg_run, "CFGPass");
            ensure_analysis(pm, func, MIR_ANALYSIS_DOMINATORS, mir_pass_dom_run, "DomPass");
        }
        if (curr->requires & MIR_ANALYSIS_SSA) {
            // SSA requires Dominators
            ensure_analysis(pm, func, MIR_ANALYSIS_CFG, mir_pass_cfg_run, "CFGPass");
            ensure_analysis(pm, func, MIR_ANALYSIS_DOMINATORS, mir_pass_dom_run, "DomPass");
            ensure_analysis(pm, func, MIR_ANALYSIS_SSA, mir_pass_ssa_run, "SSAPass");
        }
        
        // printf("[PassManager] Running %s\n", curr->name);
        if (curr->requires & MIR_ANALYSIS_DEF_USE) {
            ensure_analysis(pm, func, MIR_ANALYSIS_CFG, mir_pass_cfg_run, "CFGPass");
            ensure_analysis(pm, func, MIR_ANALYSIS_DEF_USE, mir_pass_def_use_run, "DefUsePass");
        }
        if (curr->run) {
            curr->run(func);
        }
        
        // Invalidate analyses not explicitly preserved
        pm->valid_analyses &= curr->preserves;
        
        // Verify IR invariants
        extern void mir_verify_run(mir_func_t* func, uint32_t current_analysis);
        mir_verify_run(func, pm->valid_analyses);
        
        curr = curr->next;
    }
}

void mir_pm_destroy(mir_pass_manager_t* pm) {
    if (!pm) return;
    mir_pass_t* curr = pm->passes;
    while (curr) {
        mir_pass_t* next = curr->next;
        free(curr);
        curr = next;
    }
    pm->passes = NULL;
    pm->tail = NULL;
    pm->valid_analyses = MIR_ANALYSIS_NONE;
}
