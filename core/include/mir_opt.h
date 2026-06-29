#ifndef VIR_MIR_OPT_H
#define VIR_MIR_OPT_H

#include "mir.h"
#include "mir_pass.h"


// CFG Cleanup
void mir_opt_cfg_cleanup_run(mir_func_t* func);

// SSA Destruction
void mir_pass_ssa_destruct_run(mir_func_t* func);

#ifdef __cplusplus
extern "C" {
#endif

// Constant Folding & Propagation
void mir_opt_cf_run(mir_func_t* func);

// Copy Propagation
void mir_opt_cp_run(mir_func_t* func);

// Dead Code Elimination
void mir_opt_dce_run(mir_func_t* func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_OPT_H
