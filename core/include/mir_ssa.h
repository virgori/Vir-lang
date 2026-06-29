#ifndef VIR_MIR_SSA_H
#define VIR_MIR_SSA_H

#include "mir.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Insert Phi nodes at dominance frontiers */
void mir_insert_phi_nodes(mir_func_t* func);

/* Rename variables to ensure Static Single Assignment form */
void mir_rename_variables(mir_func_t* func);

/* Wrapper to run all SSA passes */
void mir_build_ssa(mir_func_t* func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_SSA_H
