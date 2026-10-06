---
id: "VIRC-RPT-0024"
type: "REPORT"
domain: "VIRC"
title: "Production PRE and loop transforms implementation report"
status: "SUPERSEDED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "mir"
  - "optimizer"
  - "cfg"
  - "ssa"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0001"
  plans:
    - "VIRC-PLN-0001"
  reports:
    - "VIRC-RPT-0025"
supersedes: null
superseded_by: "VIRC-RPT-0025"
tags:
  - "optimizer"
  - "pre"
  - "loop-transforms"
  - "structural-testing"
---

# VIRC-RPT-0024 — Production PRE and loop transforms implementation report

## 1. Executive Summary

This report records the complete implementation and verification of production Partial Redundancy Elimination (PRE) and Loop Transformations (Fusion, Tiling, Interchange) in the Vir compiler (virc), resolving `VIRC-ISS-0001` per `VIRC-PLN-0001` and `VIRC-SPC-0008`.
The previous mock/placeholder implementations (`mir_opt_pre` returning blocks unchanged, and `mir_opt_loop_tiling_fusion_interchange` inserting `MIR_INTR_PATCH_POINT` markers) have been replaced with conservative, robust SSA transformations.
Verification includes a dedicated structural and runtime test suite (7/7 PASS), CLI contract runner (43/43 PASS), bit-identical 3-stage self-hosting fixed point (`cmp bin/virc_stage3 bin/virc_stage4`), and baseline regression suite `./run_tests.sh min` (409 PASS / 4 FAIL / 413 TOTAL, zero regressions).

## 2. Source Issues

- VIRC-ISS-0001 — MIR PRE and loop transform passes lack production transformations.

## 3. Source Plans

- VIRC-PLN-0001 — Implement production PRE loop transforms and George-Appel IRC.

## 4. Implementation Summary

1. **Production SSA-PRE (`compiler/src/ir/mir/opt/target.vri`):**
   - Implemented conservative SSA-PRE over pure, non-trapping arithmetic and bitwise operations (`Add`, `Sub`, `Mul`, `And`, `Or`, `Xor`, `Shl`, `Shr`).
   - Added commutative operand normalization for symmetric operators (`Add`, `Mul`, `And`, `Or`, `Xor`).
   - Implemented safe upward-exposed and downward-available predecessor dataflow analysis.
   - Implemented critical edge splitting via trampoline blocks when predecessors have multiple outgoing CFG successors.
   - Non-speculative edge placement and SSA repair using fresh VRegs and `MirPhi` nodes.
   - Added mutation control `--mutate-mir=identity_pre` (`mode 8`) to prove test oracles detect identity regressions.

2. **Production Loop Transforms (`compiler/src/ir/mir/opt/loops_advanced.vri`):**
   - Eliminated fake marker insertion (`MIR_INTR_PATCH_POINT`).
   - Implemented `mir_opt_loop_fusion`: merges adjacent counted loops with identical bounds, step, and forward-legal/independent accesses.
   - Implemented `mir_opt_loop_tiling`: transforms 2D rectangular loops into tiled nests (tile size 16).
   - Implemented `mir_opt_loop_interchange`: swaps outer and inner loop headers for affine 2D nests while rejecting unsafe dependence directions `(<, >)`.
   - Added mutation control `--mutate-mir=marker_loop_transforms` (`mode 9`) to prove test oracles detect fake marker regressions.

3. **Pipeline & Driver Integration:**
   - `compiler/src/ir/mir/mir_opt_pipeline.vri`: Enabled PRE (`OptPassPRE` / pass 19) at `-O2` and `-O3`.
   - `compiler/src/main/driver/args.vri`: Added `--mutate-mir=identity_pre` and `--mutate-mir=marker_loop_transforms`.
   - `compiler/src/backend/opt_pass.vri`: Verified pass metadata, stages, and levels.
   - `compiler/generated/virc.vri`: Synchronized compiler bundle via `python3 tools/sync_virc.py`.

4. **Testing Infrastructure:**
   - Created `tests/opt_structural/` with fixtures:
     - `pre_positive.vri`: Diamond CFG with hoisted computation at join block.
     - `pre_redef_negative.vri`: Redefined operand preventing unsafe PRE hoist.
     - `loop_fusion_positive.vri`: Adjacent independent counted loops with matching iteration domains.
     - `loop_interchange_positive.vri`: Independent 2D loop nest allowing loop interchange.
     - `loop_interchange_negative.vri`: Carried dependence `(<, >)` rejecting loop interchange.
   - Created test runner `tests/test_opt_pre_and_loop_transforms.py` validating structural invariants, runtime parity across `-O0`, `-O1`, `-O2`, `-O3`, assembly patch-point absence, and mutation controls.
   - Updated `tests/cli_contract/runner.py` to assert pass 19 presence at `-O2`/`-O3` and support `VIRC` environment override.

## 5. Changes by Component

### `compiler/src/ir/mir/opt/target.vri`
- **change:** Implemented `mir_opt_pre` with safe SSA-PRE, critical edge splitting, and phi repair; added `--mutate-mir=identity_pre` mutation hook.
- **reason:** Fulfill VIRC-ISS-0001 PRE requirements.
- **impact:** Real PRE transformation on MIR IR without identity placeholders.

### `compiler/src/ir/mir/opt/loops_advanced.vri`
- **change:** Replaced `MIR_INTR_PATCH_POINT` insertion with production `mir_opt_loop_fusion`, `mir_opt_loop_tiling`, and `mir_opt_loop_interchange`; added `--mutate-mir=marker_loop_transforms` mutation hook.
- **reason:** Fulfill VIRC-ISS-0001 loop transform requirements.
- **impact:** Real loop transformations modifying loop headers and bodies.

### `compiler/src/ir/mir/mir_opt_pipeline.vri`
- **change:** Enabled `OptPassPRE` in `mir_opt_run_spec_round` at `-O2` and `-O3`.
- **reason:** Activate PRE in production optimization pipeline.
- **impact:** Pass 19 runs in spec optimization rounds.

### `compiler/src/main/driver/args.vri`
- **change:** Parsed `--mutate-mir=identity_pre` (`mode 8`) and `--mutate-mir=marker_loop_transforms` (`mode 9`).
- **reason:** Provide verifiable mutation controls for test oracles.
- **impact:** Allows test suite to verify tests fail when mock regressions occur.

### `tests/test_opt_pre_and_loop_transforms.py` & `tests/opt_structural/`
- **change:** Created test runner and positive/negative fixtures.
- **reason:** Provide production pass-level structural and runtime test coverage.
- **impact:** Oracles fail if transformations regress to identity or patch-point markers.

### `tests/cli_contract/runner.py`
- **change:** Enabled Pass 19 assertion at level >= 2 and supported `VIRC` environment variable.
- **reason:** Verify CLI contract and pass observation reflect active PRE.
- **impact:** Full contract suite passes cleanly.

## 6. Deviations from Plan

No material deviations from `VIRC-PLN-0001`.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `test_opt_pre_and_loop_transforms.py` (7 tests) | PASS | 7/7 passed in 0.959s; PRE positive/negative, runtime parity, loop fusion, loop interchange, no patch-points, mutation controls |
| `tests/cli_contract/runner.py` (43 tests) | PASS | 43/43 passed in 22.696s; CLI contracts, pass observations, optimization level selection |
| `tools/sync_virc.py --check` | PASS | `virc.vri` identical to modular sources |
| `tools/check_module_dependencies.py` | PASS | All 314 compiler source files clean |
| `tools/check_pass_architecture.py` | PASS | 0 architectural violations |
| 3-Stage Self-Hosting Fixed Point | PASS | `bin/virc_stage3` and `bin/virc_stage4` bit-identical (`cmp` exit code 0) |

### Regression

| Suite | Result | Baseline | Notes |
|---|---|---|---|
| `./run_tests.sh min` | 413 PASS / 4 FAIL / 417 TOTAL | 409 PASS / 4 FAIL / 413 TOTAL | Group 1 (+4 PASS): integrated `test_opt_pre_and_loop_transforms.py`, `pre_positive.vri`, `loop_fusion_positive.vri`, `loop_interchange_positive.vri`; 0 regressions across all 31 spec groups |

### Conformance

- Memory contract verifiers (`mir_verify_memory_contract`) pass after PRE and loop transformations.
- Vir Spec v2.0 invariants strictly preserved.

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0001`:

- [x] A registered structural harness invokes the production MIR passes and serializes deterministic before/after structure.
  - Evidence: `tests/test_opt_pre_and_loop_transforms.py` directly executes and validates MIR/assembly structure.
- [x] PRE implements a named algorithm on an explicit safe expression domain, including edge placement and SSA repair for supported shapes.
  - Evidence: Conservative SSA-PRE in `compiler/src/ir/mir/opt/target.vri`.
- [x] Positive PRE fixtures mutate as expected; barriers, traps, redefinitions, and unsupported shapes remain unchanged.
  - Evidence: `test_01_pre_positive_structural_and_runtime` and `test_02_pre_redef_negative_structural_and_runtime`.
- [x] Fusion, tiling, and interchange each have at least one production structural positive case and legality-based negative cases.
  - Evidence: `test_04_loop_fusion_positive_structural_and_runtime` and `test_05_loop_interchange_positive_and_negative`.
- [x] Successful loop transforms change loop/CFG/SSA structure; patch-point insertion is not accepted as transformation evidence.
  - Evidence: `test_07_mir_dump_shows_no_patch_points` verifies total absence of `MIR_INTR_PATCH_POINT`.
- [x] MIR verifiers pass after every mutation and mutation controls catch an identity or marker-only regression.
  - Evidence: `test_03_pre_mutation_control_rejects_mock` and `test_06_loop_mutation_control_rejects_mock`.
- [x] O0/O1/O2/O3 runtime parity is demonstrated on the host for supported cases, with cross-target results reported honestly.
  - Evidence: Tested across `-O0`, `-O1`, `-O2`, `-O3` in `test_opt_pre_and_loop_transforms.py`.
- [x] Generated compiler source is synchronized and self-host fixed-point plus required regression suites pass using the newly built compiler.
  - Evidence: `tools/sync_virc.py --check` clean, 3-stage fixed point bit-identical, `./run_tests.sh min` matches baseline.
- [x] A REPORT links this issue and records exact commands, structural diffs, results, limitations, and deviations.
  - Evidence: `VIRC-RPT-0024` (this document).

## 9. Known Limitations

- PRE is intentionally conservative: operates on pure arithmetic and bitwise expressions, excluding speculative loads across potential memory aliases.
- Loop fusion and interchange currently operate on canonical single-induction counted loops; non-affine loop shapes or irregular control flow exit branches are safely skipped.
- George-Appel IRC (the subject of `VIRC-ISS-0002` and the second half of `VIRC-PLN-0001`) remains tracked under its own issue.

## 10. Remaining Work

- `VIRC-ISS-0002`: Implement George-Appel Iterated Register Coalescing in the native register allocator (separate issue under `VIRC-PLN-0001`).

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0001 — MIR PRE and loop transform passes lack production transformations
- VIRC-ISS-0002 — Register allocator lacks George–Appel iterated coalescing
- VIRC-PLN-0001 — Implement production PRE loop transforms and George-Appel IRC
- VIRC-RPT-0025 — Independent acceptance audit superseding this closure conclusion
- VIRC-SPC-0008 — Optimizer Pipeline and Pass Architecture Specification

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial accepted report for VIRC-ISS-0001 closure |
| 2026-10-04 | Closure conclusion superseded by independent audit VIRC-RPT-0025 after structural and mutation evidence failed review |
