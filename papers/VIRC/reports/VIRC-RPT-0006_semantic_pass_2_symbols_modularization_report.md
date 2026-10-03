---
id: "VIRC-RPT-0006"
type: "REPORT"
domain: "VIRC"
title: "Semantic pass 2 symbol registration modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "semantic"
components:
  - "symbol-table"
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
  - "symbol-table"
  - "modularization"
  - "pass2"
  - "phase2"
---

# VIRC-RPT-0006 — Semantic pass 2 symbol registration modularization report

## 1. Executive Summary

Semantic Pass 2 (`sem_pass2_symbols.vri`) has been modularized in accordance with `VIRC-PLN-0004` and `VIRC-ISS-0006`. The monolithic file was reduced from 687 lines to 34 logical lines, achieving a 95.1% line reduction and comfortably meeting the mandatory architectural exit gate ($\le 300$ lines). The remaining file serves exclusively as a thin orchestrator coordinating type name extraction, builtin initialization, and AST declaration traversal.

The domain logic was partitioned into 4 cohesive leaf submodules under `compiler/src/semantic/symbols/`:
1. `context.vri` (`symbols_context`): Pass 2 per-scope hash buckets (`PASS2_BUCKETS = 256`), user module detection (`is_user_module`), type name collection, scope lookups, and symbol creation/redefinition validation.
2. `builtins.vri` (`symbols_builtins`): Registration of intrinsic runtime functions, memory primitives, syscall helpers, atomic operations, and system barriers into global scope 0.
3. `walk_types.vri` (`symbols_walk_types`): Symbol registration for entities, packed structs, registers, classes, type aliases, and enums/variants.
4. `walk.vri` (`symbols_walk`): Top-level AST traversal for functions, variables, constants, modules, attributes, and nested extern declarations.

All submodules are registered with the `symbols_` prefix in `compiler/module.list` and synchronized to `compiler/generated/virc.vri` with zero drift. The full CLI contract suite (43/43 tests) and all paper validations pass cleanly.

## 2. Source Issues

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.

## 3. Source Plans

- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes.

## 4. Implementation Summary

1. **Orchestrator Reduction**:
   - Monolithic source `compiler/src/semantic/sem_pass2_symbols.vri`: 687 lines $\to$ 34 lines (-95.1%).
   - Retains only submodule includes, pass entry point `pass2_register_symbols`, and export `pass2_register_symbols`.
2. **Submodule Architecture**:
   - `compiler/src/semantic/symbols/context.vri` (181 lines): Hash maps per scope (`pass2_hash_name`, `pass2_index_symbol`, `pass2_lookup_name_in_scope`), user module detection, and redefinition checking (`pass2_register`).
   - `compiler/src/semantic/symbols/builtins.vri` (148 lines): Deterministic builtin function table registration (`pass2_register_builtins`, `pass2_register_builtin_one`).
   - `compiler/src/semantic/symbols/walk_types.vri` (150 lines): Type declaration walker `pass2_walk_type_def` handling entities, packed/register structs, type aliases, and enums.
   - `compiler/src/semantic/symbols/walk.vri` (244 lines): AST declaration walker `pass2_walk_node` and nested extern collector `pass2_collect_nested_extern`.
3. **Module Registry**:
   - Registered 4 submodules in `compiler/module.list` (`symbols_context`, `symbols_builtins`, `symbols_walk_types`, `symbols_walk`).
   - Bundled and verified via `tools/sync_virc.py` with zero drift.

## 5. Changes by Component

### `compiler/src/semantic/sem_pass2_symbols.vri`

- change: Reduced monolithic source to 34 lines containing only `pass2_register_symbols` orchestrator and exports.
- reason: Satisfy `VIRC-PLN-0004` exit gate ($\le 300$ logical lines, thin orchestrator).
- impact: Line count reduced from 687 to 34 (-95.1%).

### `compiler/src/semantic/symbols/` (4 Submodules)

- change: Created submodules `context.vri`, `builtins.vri`, `walk_types.vri`, and `walk.vri`.
- reason: Decouple scope indexing/lookups, builtin registration, type declarations, and AST declaration dispatch.
- impact: Isolated submodules with clear, bounded responsibility and maintainable structure.

### `compiler/module.list`

- change: Registered entries `symbols_context`, `symbols_builtins`, `symbols_walk_types`, and `symbols_walk`.
- reason: Enable flat `include symbols_*` module resolution.
- impact: Standardized module resolution across compilation units.

## 6. Deviations from Plan

No deviations from `VIRC-PLN-0004`. All symbol registration semantics, error reporting (E1001 duplicate symbol), IDE fact emission (`ideFactResolve`, `ideFactType`, `ideFactResolvedType`), and qualified variant naming rules remain strictly identical.

## 7. Verification

### Tests

| Test Suite / Command | Result | Evidence |
|---|---|---|
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 tests passing in 24.922s |
| `python3 tools/paper.py validate` | PASS | 57 production papers, 3 example papers valid |
| Line count verification (`wc -l`) | PASS | `sem_pass2_symbols.vri` = 34 lines ($\le 300$) |
| Compiler self-compilation (`virc compiler/generated/virc.vri -o bin/virc`) | PASS | 26,272,128 bytes code generated, Mach-O codesigned |
| Bundle synchronization (`tools/sync_virc.py --check`) | PASS | Zero drift detected |
| Architecture check (`tools/check_pass_architecture.py`) | PASS | Verified 3 orchestrators, stdlib boundary clean |

### Regression

Zero regression across compiler contract tests, error and warning codes, builtin intrinsics, module-qualified function names, and entity field/method resolution.

## 8. Acceptance Criteria

- [x] `sem_pass2_symbols.vri` is $\le 300$ logical lines and contains no inline rule implementation (`CONFIRMED`: 34 lines).
- [x] All 4 submodules registered in `compiler/module.list` with flat include names (`CONFIRMED`).
- [x] Self-hosted compiler builds successfully and passes codesign (`CONFIRMED`).
- [x] Full CLI contract runner passes 43/43 tests without degradation (`CONFIRMED`).
- [x] VPS paper validation passes completely (`CONFIRMED`).

## 9. Known Limitations

- Submodules under `compiler/src/semantic/symbols/` still use module-level globals (`g_pass2_*`) defined in `context.vri`.
- Remaining oversized compiler passes (Pass 3, Pass 9, Pass 10) await modularization in upcoming phases.

## 10. Remaining Work

- Proceed to modularize the next oversized compiler pass pursuant to `VIRC-PLN-0004`.

## 11. Conclusion

REQUIRES_FOLLOWUP

## 12. Related Papers

- `VIRC-ISS-0006` — Compiler sources coupled to stdlib and oversized pass files
- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial completion report for Pass 2 symbol registration modularization |
