#ifndef VIR_MIR_CFG_H
#define VIR_MIR_CFG_H

#include "mir.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Build Control Flow Graph (resolve predecessors) */
void mir_build_cfg(mir_func_t* func);

/* Compute Dominator Tree and Dominance Frontiers */
void mir_compute_dominators(mir_func_t* func);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_CFG_H
