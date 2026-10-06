---
id: "VIRC-RPT-0003"
type: "REPORT"
domain: "VIRC"
title: "Semantic pass 8 borrow analysis modularization report"
status: "ACCEPTED"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow"
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
  - "borrow"
  - "modularization"
  - "pass8"
  - "phase8"
---

# VIRC-RPT-0003 — Semantic pass 8 borrow analysis modularization report

## 1. Executive Summary

Semantic Pass 8 (`sem_pass8_borrow.vri`) has been completely modularized in accordance with Phase 8 and Section 5.6 of `VIRC-PLN-0004`. The monolithic file was reduced from 3,138 lines to 213 logical lines, significantly outperforming the mandatory requirement ($\le 300$ lines). The remaining file serves exclusively as a thin orchestrator providing pass initialization (`pass8_analyze_borrow`), high-level AST walk dispatch (`pass8_walk`), and pass exports, with zero inline ownership/borrow rule logic.

All specific ownership rule families, lexical scope trackers, address-of and loan management, finite-lattice dataflow joins, move analysis, Arena region escape checks, and statement/loop walkers were partitioned into 22 cohesive submodules under `compiler/src/semantic/borrow/`. Every submodule is explicitly registered with a flat identifier in `compiler/module.list` pursuant to Policy Direction 3. The entire compiler CLI contract suite (43/43 tests) and all paper validations pass cleanly.

## 2. Source Issues

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.

## 3. Source Plans

- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes (Phase 8).

## 4. Implementation Summary

1. **Orchestrator Reduction**:
   - Monolithic source `compiler/src/semantic/sem_pass8_borrow.vri`: 3,138 lines $\to$ 213 lines.
   - Reduction: -2,925 lines (-93.2%).
   - Contains only submodule includes, initialization context setup, and the high-level AST walk dispatch table.
2. **Submodule Architecture**:
   - Partitioned into 22 dedicated submodules under `compiler/src/semantic/borrow/`:
     - Core Infrastructure: `context.vri`, `binding.vri`, `paths.vri`, `scopes.vri`, `diagnostics.vri`, `funcs.vri`, `nll.vri`.
     - Dataflow State & Lattice: `state.vri`, `moves.vri`, `loans.vri`, `loops.vri`, `branches.vri`.
     - Specialized Lifetimes: `arena.vri`, `async.vri`.
     - AST Walkers: `walk_access.vri`, `walk_assign.vri`, `walk_decl.vri`, `walk_call.vri`, `walk_return.vri`, `walk_stmts.vri`, `walk_func.vri`, `walk_block.vri`, `walk_branches.vri`, `walk_loops.vri`.
3. **Module Registry**:
   - Registered all 22 submodules in `compiler/module.list` with prefix `borrow_`.
   - Maintained strict topological ordering in `compiler/generated/virc.vri`.

## 5. Changes by Component

### `compiler/src/semantic/sem_pass8_borrow.vri`

- change: Reduced monolithic implementation to 213 lines containing `pass8_analyze_borrow` orchestrator and high-level `pass8_walk` dispatch table.
- reason: Satisfy `VIRC-PLN-0004` Phase 8 exit gate ($\le 300$ logical lines, thin orchestrator).
- impact: Line count reduced from 3,138 to 213.

### `compiler/src/semantic/borrow/` (22 Submodules)

- change: Created cohesive submodules:
  - Infrastructure: `context`, `binding`, `paths`, `scopes`, `diagnostics`, `funcs`, `nll`.
  - State & dataflow: `state`, `moves`, `loans`, `loops`, `branches`.
  - Lifetimes: `arena`, `async`.
  - Walk dispatchers: `walk_access`, `walk_assign`, `walk_decl`, `walk_call`, `walk_return`, `walk_stmts`, `walk_func`, `walk_block`, `walk_branches`, `walk_loops`.
- reason: Enforce single-responsibility principle across affine ownership and borrow analysis.
- impact: Clean boundaries; loan tracking, moves, loop lattices, and AST walking are isolated and independently maintainable.

### `compiler/module.list`

- change: Registered 22 entries matching `borrow_* = src/semantic/borrow/*.vri`.
- reason: Enable flat `include borrow_*` resolution across all compilation units.
- impact: Elimination of relative path coupling in source files.

## 6. Deviations from Plan

No deviations from `VIRC-PLN-0004` Phase 8. All ownership rules, diagnostic codes (E5001–E5013), and loop lattice fixed-point behaviors remain strictly preserved.

## 7. Verification

### Tests

| Test Suite / Command | Result | Evidence |
|---|---|---|
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 tests passing in 27.140s |
| `python3 tools/paper.py validate` | PASS | 54 production papers, 3 example papers valid |
| Line count verification (`wc -l`) | PASS | `sem_pass8_borrow.vri` = 213 lines ($\le 300$) |
| Compiler self-compilation (`virc compiler/generated/virc.vri -o bin/virc`) | PASS | 26,301,176 bytes code generated, Mach-O codesigned |

### Regression

Zero regression across compiler contract tests, parser metadata, CFG liveness intervals, GVN equivalence, and IDE mode facts.

## 8. Acceptance Criteria

- [x] `sem_pass8_borrow.vri` is $\le 300$ logical lines and contains no inline rule implementation (`CONFIRMED`: 213 lines).
- [x] All 22 submodules registered in `compiler/module.list` with flat include names (`CONFIRMED`).
- [x] Self-hosted compiler builds successfully and passes codesign (`CONFIRMED`).
- [x] Full CLI contract runner passes 43/43 tests without degradation (`CONFIRMED`).
- [x] VPS paper validation passes completely (`CONFIRMED`).

## 9. Known Limitations

- Submodules under `compiler/src/semantic/borrow/` still use module-level globals (`g_pass8_*`) defined in `context.vri`.
- Pass 7 (`sem_pass7_cfa.vri`, 594 lines), Pass 2 (`sem_pass2_symbols.vri`, 686 lines), Pass 3 (`sem_pass3_names.vri`, 1,065 lines), and Pass 10 (`sem_pass10_diagnostics.vri`, 1,702 lines) remain to be modularized in subsequent phases.

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
| 2026-10-02 | Initial completion report for Phase 8 (Pass 8 borrow analysis modularization) |
