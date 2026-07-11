#ifndef VIR_MIR_LOWER_H
#define VIR_MIR_LOWER_H

#include "hir.h"
#include "mir.h"
#include "ir_lower.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Lower a HIR node (usually representing a function body) into a MIR function.
 * This flattens control flow into basic blocks.
 */
mir_func_t* lower_hir_to_mir(const hir_node_t* hir, uint32_t func_id, lower_ctx_t *lctx);

#ifdef __cplusplus
}
#endif

#endif // VIR_MIR_LOWER_H
