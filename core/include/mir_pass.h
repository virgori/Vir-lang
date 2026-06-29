#ifndef VIR_MIR_PASS_H
#define VIR_MIR_PASS_H

#include "mir.h"

#ifdef __cplusplus
extern "C" {
#endif

// Analysis bitmasks
#define MIR_ANALYSIS_NONE       0
#define MIR_ANALYSIS_CFG        (1 << 0)
#define MIR_ANALYSIS_DOMINATORS (1 << 1)
#define MIR_ANALYSIS_SSA        (1 << 2)
#define MIR_ANALYSIS_DEF_USE    (1 << 3)

typedef struct mir_pass {
    const char* name;
    
    // Required analyses before running this pass
    uint32_t requires;
    
    // Analyses preserved (not invalidated) by this pass
    uint32_t preserves;
    
    // The actual pass function
    void (*run)(mir_func_t* func);
    
    struct mir_pass* next;
} mir_pass_t;

typedef struct {
    mir_pass_t* passes;
    mir_pass_t* tail;
    
    // Currently valid analyses
    uint32_t valid_analyses;
} mir_pass_manager_t;

/* Manager API */
void mir_pm_init(mir_pass_manager_t* pm);
void mir_pm_add_pass(mir_pass_manager_t* pm, const char* name, uint32_t requires, uint32_t preserves, void (*run)(mir_func_t*));
void mir_pm_run(mir_pass_manager_t* pm, mir_func_t* func);
void mir_pm_destroy(mir_pass_manager_t* pm);

/* Built-in Passes */
void mir_pass_cfg_run(mir_func_t* func);
void mir_pass_dom_run(mir_func_t* func);
void mir_pass_ssa_run(mir_func_t* func);
void mir_pass_def_use_run(mir_func_t* func);

void mir_replace_all_uses(mir_func_t* func, uint32_t old_vreg, uint32_t new_vreg);
void mir_remove_instr_def_use(mir_func_t* func, mir_instr_t* instr);
void mir_remove_phi_def_use(mir_func_t* func, mir_phi_t* phi);

void mir_verify_run(mir_func_t* func, uint32_t current_analysis);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_PASS_H
