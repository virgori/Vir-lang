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
#include "ir_lower.h"
#include <stdlib.h>
#include <string.h>

int pipeline_enabled(void) {
  return 1;
}

static int lower_hir_tree(lower_ctx_t *ctx, hir_node_t *hir, uint32_t func_id) {
  if (!hir)
    return 0;

  mir_func_t *mir = lower_hir_to_mir(hir, func_id, ctx);
  if (!mir) {
    strncpy(ctx->last_error, "MIR lowering failed", sizeof(ctx->last_error) - 1);
    return -1;
  }

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

static int pipeline_lower_stmt(lower_ctx_t *ctx, const ast_node_t *stmt,
                               uint32_t func_id) {
  if (!stmt)
    return 0;

  hir_node_t *hir = lower_ast_to_hir(stmt, ctx);
  if (hir) {
    int rc = lower_hir_tree(ctx, hir, func_id);
    hir_free_node(hir);
    return rc;
  }
  return lower_stmt(ctx, stmt);
}

static int pipeline_lower_block(lower_ctx_t *ctx, const ast_node_t *block,
                                uint32_t func_id) {
  if (!block)
    return 0;
  if (block->type != AST_BLOCK)
    return pipeline_lower_stmt(ctx, block, func_id);

  for (uint32_t i = 0; i < block->child_count; i++) {
    if (pipeline_lower_stmt(ctx, block->children[i], func_id) != 0)
      return -1;
  }
  return 0;
}

int pipeline_lower_func_body(lower_ctx_t *ctx, const ast_node_t *body_ast,
                             uint32_t func_id) {
  if (!ctx || !body_ast || !ctx->current_func)
    return -1;

  return pipeline_lower_block(ctx, body_ast, func_id);
}
