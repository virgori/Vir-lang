#include "compiler_pipeline.h"
#include "hir_lower.h"
#include "mir_lower.h"
#include "mir_pass.h"
#include "mir_opt.h"
#include "lir_lower.h"
#include "lir_to_qir.h"
#include "lir_analysis.h"
#include "lir_regalloc.h"
#include "hir.h"
#include <stdlib.h>
#include <string.h>

int pipeline_enabled(void) {
  return 1;
}

static void run_mir_passes(mir_func_t *func) {
  mir_pass_manager_t pm;
  mir_pm_init(&pm);
  mir_pm_add_pass(&pm, "CFG", MIR_ANALYSIS_NONE, MIR_ANALYSIS_CFG,
                  mir_pass_cfg_run);
  mir_pm_add_pass(&pm, "Dominators", MIR_ANALYSIS_CFG, MIR_ANALYSIS_DOMINATORS,
                  mir_pass_dom_run);
  mir_pm_add_pass(&pm, "SSA", MIR_ANALYSIS_DOMINATORS, MIR_ANALYSIS_SSA,
                  mir_pass_ssa_run);
  mir_pm_add_pass(&pm, "ConstantFold", MIR_ANALYSIS_SSA, MIR_ANALYSIS_SSA,
                  mir_opt_cf_run);
  mir_pm_add_pass(&pm, "CopyProp", MIR_ANALYSIS_SSA, MIR_ANALYSIS_SSA,
                  mir_opt_cp_run);
  mir_pm_add_pass(&pm, "DCE", MIR_ANALYSIS_SSA, MIR_ANALYSIS_SSA,
                  mir_opt_dce_run);
  mir_pm_add_pass(&pm, "CFGCleanup", MIR_ANALYSIS_SSA, MIR_ANALYSIS_NONE,
                  mir_opt_cfg_cleanup_run);
  mir_pm_run(&pm, func);
  mir_pm_destroy(&pm);
}

int pipeline_lower_func_body(lower_ctx_t *ctx, const ast_node_t *body_ast,
                             uint32_t func_id) {
  if (!ctx || !body_ast || !ctx->current_func)
    return -1;

  hir_node_t *hir = lower_ast_to_hir(body_ast);
  if (!hir) {
    strncpy(ctx->last_error, "HIR lowering failed", sizeof(ctx->last_error) - 1);
    return -1;
  }

  mir_func_t *mir = lower_hir_to_mir(hir, func_id, ctx);
  hir_free_node(hir);
  if (!mir) {
    strncpy(ctx->last_error, "MIR lowering failed", sizeof(ctx->last_error) - 1);
    return -1;
  }

  /* MIR optimization passes */
  mir_pass_cfg_run(mir);

  lir_func_t *lir = lower_mir_to_lir(mir);
  mir_free_func(mir);
  if (!lir) {
    strncpy(ctx->last_error, "LIR lowering failed", sizeof(ctx->last_error) - 1);
    return -1;
  }

  int rc = lir_to_qir_append(ctx, lir);
  lir_free_func(lir);

  if (rc != 0) {
    strncpy(ctx->last_error, "LIR to Q-IR conversion failed",
            sizeof(ctx->last_error) - 1);
  }
  return rc;
}
