---
id: "VIRC-RPT-0008"
type: "REPORT"
domain: "VIRC"
title: "Semantic pass 3 name resolution modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "semantic"
components:
  - "name-resolution"
  - "compiler-source-layout"
  - "module-resolution"
related:
  issues:
    - "VIRC-ISS-0006"
  plans:
    - "VIRC-PLN-0004"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "name-resolution"
  - "modularization"
  - "pass3"
  - "phase2"
---

# VIRC-RPT-0008 — Semantic pass 3 name resolution modularization report

## 1. Executive Summary

Semantic Pass 3 (`sem_pass3_names.vri`) has been modularized in accordance with `VIRC-PLN-0004` and `VIRC-ISS-0006`. The monolithic file was reduced from 1,066 lines to 56 lines (51 logical lines), achieving a 94.7% line reduction and comfortably meeting the mandatory architectural exit gate ($\le 300$ lines). The remaining file serves exclusively as a thin orchestrator initializing import alias collections, building the global symbol index, and executing the AST name resolution pass.

The domain logic was partitioned into 6 cohesive leaf submodules under `compiler/src/semantic/names/`:
1. `context.vri` (`names_context`): Global hash index configuration (`PASS3_GLOBAL_BUCKETS = 4096`), bucket hashing, import alias mappings, and intrinsic method / soft-call predicates.
2. `lookup.vri` (`names_lookup`): Bucket-based fast global symbol lookup (`pass3_lookup_global`), hierarchical scope chain resolution (`pass3_lookup_chain`), scope-exact lookups, and enclosing function scope navigation.
3. `register.vri` (`names_register`): Local variable and parameter registration, implicit assignment binding (`pass3_register_implicit_local`), and pattern match binder registration.
4. `rewrite.vri` (`names_rewrite`): Atomic AST rewrite of variant calls and identifiers into `AstType.EnumConstruct` nodes.
5. `walk_expr.vri` (`names_walk_expr`): Expression name resolution for identifiers, function calls, UFCS / enum constructor method calls, entity literals, field accesses, and enum accesses.
6. `walk_decl.vri` (`names_walk_decl`): Declaration name resolution for functions, variable declarations, groups, constants, and share/has declarations.
7. `walk.vri` (`names_walk`): Central traversal dispatcher coordinating statement, block, pattern match, and control flow traversal with delegation to `names_walk_expr` and `names_walk_decl`.

All submodules are registered with the `names_` prefix in `compiler/module.list` and synchronized to `compiler/generated/virc.vri` with zero drift. The full CLI contract suite (43/43 tests) and all paper validations pass cleanly.

## 2. Source Issues

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.

## 3. Source Plans

- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes.

## 4. Implementation Summary

1. **Orchestrator Reduction**:
   - Monolithic source `compiler/src/semantic/sem_pass3_names.vri`: 1,066 lines $\to$ 56 lines (-94.7%).
   - Retains only submodule includes, pass entry point `pass3_resolve_names`, and exports `pass3_resolve_names`, `pass3_lookup_chain`.
2. **Submodule Architecture**:
   - `compiler/src/semantic/names/context.vri` (117 lines, 102 logical lines): Hash table structures, import alias resolution (`pass3_resolve_import_alias`), and global indexing (`pass3_build_global_index`).
   - `compiler/src/semantic/names/lookup.vri` (166 lines, 152 logical lines): Multi-level symbol lookup (`pass3_lookup_global`, `pass3_lookup_chain`, `pass3_lookup_in_scope_exact`).
   - `compiler/src/semantic/names/register.vri` (127 lines, 115 logical lines): Local symbol allocation and pattern binder extraction (`pass3_register_pattern_binders`, `pass3_register_local`).
   - `compiler/src/semantic/names/rewrite.vri` (44 lines, 37 logical lines): Atomically rewritten variant construction (`pass3_rewrite_variant`).
   - `compiler/src/semantic/names/walk_expr.vri` (296 lines, 266 logical lines): Expression name resolution dispatching identifiers, calls, method calls, and variant construction.
   - `compiler/src/semantic/names/walk_decl.vri` (140 lines, 118 logical lines): Declaration resolution for functions, variable groups, and destructured constants.
   - `compiler/src/semantic/names/walk.vri` (260 lines, 229 logical lines): Traversal coordinator across statements, blocks, when/case matching, and loops.
3. **Module Registry**:
   - Registered 6 submodules in `compiler/module.list` (`names_context`, `names_lookup`, `names_register`, `names_rewrite`, `names_walk_expr`, `names_walk_decl`, `names_walk`).
   - Bundled and verified via `tools/sync_virc.py` with zero drift.

## 5. Changes by Component

### `compiler/src/semantic/sem_pass3_names.vri`

- change: Reduced monolithic source to 56 lines containing only `pass3_resolve_names` orchestrator and exports.
- reason: Satisfy `VIRC-PLN-0004` exit gate ($\le 300$ logical lines, thin orchestrator).
- impact: Line count reduced from 1,066 to 56 (-94.7%).

### `compiler/src/semantic/names/` (6 Submodules)

- change: Created submodules `context.vri`, `lookup.vri`, `register.vri`, `rewrite.vri`, `walk_expr.vri`, `walk_decl.vri`, and `walk.vri`.
- reason: Decouple global index, lookup chain, pattern binders, variant rewriting, expression resolution, and declaration dispatch.
- impact: Every submodule strictly $\le 300$ logical lines, highly cohesive, zero circular includes.

### `compiler/module.list`

- change: Registered entries `names_context`, `names_lookup`, `names_register`, `names_rewrite`, `names_walk_expr`, `names_walk_decl`, and `names_walk`.
- reason: Enable flat `include names_*` module resolution.
- impact: Standardized module resolution across compilation units.

## 6. Deviations from Plan

No deviations from `VIRC-PLN-0004`. All name resolution semantics, duplicate symbol errors (E1001), unresolved identifier errors (E2001), soft-call allowlists, IDE fact emissions (`ideFactResolve`, `ideFactType`, `ideFactResolvedType`, `ideFactScope`), and import alias behaviors remain strictly identical.

## 7. Verification

### Tests

| Test Suite / Command | Result | Evidence |
|---|---|---|
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 tests passing in 22.853s |
| `python3 tools/paper.py validate` | PASS | 59 production papers, 3 example papers valid |
| Line count verification (`wc -l`) | PASS | `sem_pass3_names.vri` = 56 lines ($\le 300$, orchestrator) |
| Logical line verification | PASS | Every submodule $\le 300$ logical lines (range: 37 - 266 lines) |
| Compiler self-compilation (`virc compiler/generated/virc.vri -o bin/virc`) | PASS | 26,115,664 bytes code generated, Mach-O codesigned |
| Bundle synchronization (`tools/sync_virc.py --check`) | PASS | Zero drift detected |
| Architecture check (`tools/check_pass_architecture.py`) | PASS | Verified 3 orchestrators, stdlib boundary clean |

### Regression

Zero regression across identifier resolution, call resolution, method call / UFCS lowering, pattern matching binders, loop binders, and CLI contract tests.

## 8. Acceptance Criteria

- [x] `sem_pass3_names.vri` is $\le 300$ logical lines and contains no inline rule implementation (`CONFIRMED`: 51 logical lines).
- [x] All 6 submodules registered in `compiler/module.list` with flat include names (`CONFIRMED`).
- [x] Every submodule under `names/` is $\le 300$ logical lines (`CONFIRMED`).
- [x] Self-hosted compiler builds successfully and passes codesign (`CONFIRMED`).
- [x] Full CLI contract runner passes 43/43 tests without degradation (`CONFIRMED`).
- [x] VPS paper validation passes completely (`CONFIRMED`).

## 9. Known Limitations

- Pass 10 (Diagnostics — 1,702 lines) remains the final oversized pass awaiting modularization.

## 10. Remaining Work

- Modularize Semantic Pass 10 (`sem_pass10_diagnostics.vri`) into leaf submodules under `compiler/src/semantic/diagnostics/`.

## 11. Conclusion

REQUIRES_FOLLOWUP

## 12. Related Papers

- `VIRC-ISS-0006` — Compiler sources coupled to stdlib and oversized pass files
- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial completion report for Pass 3 name resolution modularization |
