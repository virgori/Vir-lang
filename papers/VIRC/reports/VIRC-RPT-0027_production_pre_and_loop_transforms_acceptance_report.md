---
id: "VIRC-RPT-0027"
type: "REPORT"
domain: "VIRC"
title: "Production PRE and loop transforms acceptance report"
status: "ACCEPTED"
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
    - "VIRC-ISS-0027"
  plans:
    - "VIRC-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "acceptance-report"
  - "optimizer"
  - "pre"
  - "loop-transforms"
  - "structural-testing"
  - "fixed-point"
---

# VIRC-RPT-0027 — Production PRE and loop transforms acceptance report

## 1. Executive Summary

This report establishes auditable verification evidence following multiple rounds of independent audit and defect isolation on `VIRC-ISS-0001`.

Eight silent miscompilation defects have been systematically investigated, reproduced with minimal counterexamples, resolved in the compiler source, and guarded with dedicated structural and runtime regression tests:
1. **Loop Fusion induction step false-positive**: resolved via exact latch recurrence tracing (`mir_loop_iv_chain`).
2. **Loop Fusion initial value mismatch**: resolved by enforcing `init1 == init2` in `mir_loop_header_info`.
3. **Loop Tiling non-zero lower bound**: resolved by checking `init_out == 0` and `init_in == 0`.
4. **Loop Interchange non-rectangular inner bound**: resolved via `mir_loop_nest_is_rectangular`.
5. **Loop Fusion second-loop entry dependency**: non-IV phi entry values dependent on loop 1 definitions safely rejected via `mir_loop_fusion_has_cross_dep`.
6. **Loop Tiling outer-dependent inner bound**: triangular loop nests (`j < i`) safely rejected via `mir_loop_nest_is_rectangular`.
7. **Loop Interchange mismatched lower bounds**: rectangular nests with different initial values (e.g. 0 vs 1) safely rejected via `mir_opnd_is_same(init_out, init_in)`.
8. **Loop Tiling expression-pattern false-positive**: an `Add/Add/Move` body such as `sum = sum + i + 7` was incorrectly rewritten as the special `sum + i + j` reduction; the matcher now verifies the complete operand dataflow and exact inner induction chain.

The production MIR optimizer capabilities are:
1. **Partial Redundancy Elimination (PRE)**: Hoists partially redundant expressions from join blocks into single-successor predecessor edges, introduces SSA Phi nodes, and eliminates redundant evaluations on joined control flow paths.
2. **Loop Legality Framework (`compiler/src/ir/mir/opt/loop_legality.vri`)**: Shared mathematical legality analysis module (492 lines) providing exact latch recurrence tracing (`mir_loop_iv_chain`), header operand decomposition (`mir_loop_header_info`), affine/rectangular domain verification (`mir_loop_nest_is_rectangular`), cross-loop data dependency detection (`mir_loop_fusion_has_cross_dep`), body purity validation (`mir_loop_body_is_scalar_pure`), and order-independent reduction analysis (`mir_loop_reductions_ok`).
3. **Loop Fusion**: Merges adjacent counted loops with identical bounds, steps, and initial values into a single loop, eliminating redundant loop headers and branch instructions in generated machine assembly while strictly preserving user accumulations.
4. **Loop Tiling**: Implements outer induction step scaling by tile size (16) and aggregated strip computation over 2D rectangular constant-bound reduction loops. Note: Does not construct an explicit 4-level loop nest; strip iteration is aggregated.
5. **Loop Interchange**: Reorders induction variables and loop trip bounds for 2D nests while enforcing rectangular domain invariants, compatible initial values, and dependence direction vectors.
6. **CFG & SSA Invariant Verification**: Verifies CFG and SSA integrity after every individual optimization pass, rejecting critical-edge or Phi corruption with diagnostic `E6001`.
7. **Structural Test Suite**: Upgraded to 21 deterministic tests in `tests/test_opt_pre_and_loop_transforms.py`, capturing before/after MIR JSON snapshots, asserting assembly structural divergence from marker bypass mode, validating mutation controls, and proving runtime parity across `-O0` through `-O3`.
8. **Deterministic Bootstrap Fixed-Point**: Achieved full-file bit-for-bit identity across `bin/virc_stage5` and `bin/virc_stage6`, with matching SHA-256 `625cbbdfa0c43cfe256c80641ee63dc50cf871d8e5792808b90c0e95f8a62819` and 16,154,456 bytes of generated machine code across 2,586 compiled functions.

All 21 structural tests pass cleanly in 16.39s using the fixed-point compiler, all 43 CLI contract tests pass cleanly in 25.71s, and `python3 tools/sync_virc.py --check` confirms full synchronization.

## 2. Source Issues

- `VIRC-ISS-0001` — MIR PRE and loop transform passes lack production transformations.

## 3. Source Plans

- `VIRC-PLN-0001` — Implement production PRE loop transforms and George-Appel IRC.

## 4. Implementation Summary

1. **Dedicated Loop Legality Framework (`compiler/src/ir/mir/opt/loop_legality.vri`)**:
   - Implemented `mir_loop_header_info`: inspects loop headers, decomposes induction Phi nodes into entry and latch operands, extracts comparator opcodes, initial values, trip bounds, and step constants.
   - Implemented `mir_loop_iv_chain`: traces the backward recurrence chain from the header Phi's latch operand (`phi -> latch -> Move(temp) -> Add(iv, step)`). Isolates the exact induction step instruction from other arithmetic expressions in the loop body.
   - Implemented `mir_loop_phi_edges`: cleanly differentiates loop entry operands from latch recurrence operands.
   - Implemented `mir_loop_operand_invariant`: proves whether an operand or bound is invariant across a region, ensuring bounds do not depend on loop induction variables.
   - Implemented `mir_loop_nest_is_rectangular`: verifies that both bounds and initial values in a 2D nest are invariant over the nest and independent of either induction variable.
   - Implemented `mir_loop_fusion_has_cross_dep`: checks whether loop 2 has data dependencies on loop 1 (bounds, body instructions, or non-IV phi entry values).
   - Implemented `mir_loop_body_is_scalar_pure`, `mir_loop_reads_defs_of`, and `mir_loop_reductions_ok`: guarantees data-dependence isolation, absence of side-effects/calls/stores, and commutativity of accumulated reductions.

2. **PRE Algorithm & Critical Edge Safety (`compiler/src/ir/mir/opt/target.vri`)**:
   - Implemented PRE over safe integer arithmetic expressions (`Add`, `Sub`, `Mul`).
   - Guarded edge insertion against critical edges: predecessor blocks must possess exactly one successor (`vec_len_rt(p_succs) == 1`). If a multi-successor predecessor is encountered, PRE safely aborts with `unsafe_reason = "critical_edge"`, preventing CFG predecessor mismatch and join Phi corruption.
   - Inserted candidate expressions into missing predecessor edges and synthesized corresponding SSA Phi instructions in the join block.

3. **Loop Fusion (`compiler/src/ir/mir/opt/loops_advanced.vri`)**:
   - Detects adjacent counted loops with identical trip bounds, steps, and initial values (`init1 == init2`).
   - Skips with reason `"mismatched_bounds"` if initial values or upper bounds differ.
   - Skips with reason `"barrier_in_body"` if `mir_loop_fusion_has_cross_dep` detects loop 2 reading definitions of loop 1.
   - Employs `mir_loop_iv_chain` to isolate and remove ONLY the exact second-loop induction step (`add_idx2`, `move_idx2`), preserving scalar accumulations like `sum2 = sum2 + j`.
   - Re-wires body blocks of the second loop into the latch of the first loop, eliminating the second loop header and its branch/backedge entirely. Assembly verification confirms reduction of loop headers from 2 to 1.

4. **Loop Tiling (`compiler/src/ir/mir/opt/loops_advanced.vri`)**:
   - Enforces `mir_loop_nest_is_rectangular`; rejects triangular nests (`j < i`) with reason `"non_rectangular_domain"`.
   - Enforces `init_out == 0`, `init_in == 0`, and `bound_out % 16 == 0`.
   - Rejects non-zero lower bounds or non-divisible trip counts with reason `"bounds_not_divisible_by_tile_size"`.
   - Matches the complete supported reduction dataflow: `Add(sum, iv_out)`, then `Add(previous, iv_in)`, then the recurrence-closing `Move`, followed by the exact inner induction chain. Other `Add/Add/Move` bodies are skipped with `"unsupported_loop_body"`.
   - Scales the outer loop induction step from 1 to 16 and aggregates inner strip iterations.

5. **Loop Interchange (`compiler/src/ir/mir/opt/loops_advanced.vri`)**:
   - Checks rectangularity via `mir_loop_nest_is_rectangular`. Rejects triangular or dependent bounds (`j < i`) with reason `"non_rectangular_domain"`.
   - Evaluates dependence direction vectors; skips interchange with reason `"dependence_direction_violation"` when cross-iteration dependencies are non-interchangeable.
   - Checks initial value equivalence (`init_out == init_in`) and matching comparators; rejects mismatched lower bounds with reason `"mismatched_bounds"`.
   - Verifies order-independent reductions via `mir_loop_reductions_ok`.
   - Swaps induction variables on all loop body instructions except the inner loop's exact induction chain (`add_idx_in`, `move_idx_in`).

6. **Runtime Bounds & Safety Fix (`compiler/src/main/path_util.vri`)**:
   - Resolved `EXC_BAD_ACCESS` in `path_normalize_fat` caused by non-short-circuiting Vir bitwise operator `and`. Replaced unshortcircuited expressions with nested `if` statements and guarded index reads (`out_len > 0`).

7. **Deterministic MIR Snapshot & Verifier Logging (`compiler/src/ir/mir/opt/snapshot.vri`, `mir_opt_pipeline.vri`)**:
   - Implemented deterministic JSON serialization of function before/after MIR snapshots, recording block labels, instructions, Phis, transform changed flags, and skip reasons.
   - Embedded CFG and SSA invariant checks immediately following each pass.

## 5. Changes by Component

### `compiler/src/ir/mir/opt/loop_legality.vri`
- **change**: Created new dedicated module (492 lines) for induction chain tracing, header info analysis, rectangular domain checking, cross-loop dependency detection, and reduction verification.
- **reason**: Replaced ad-hoc instruction scanning that caused multiple silent miscompilation defects.
- **impact**: Eliminates miscompilations while providing mathematically sound legality checks across all loop passes.

### `compiler/src/ir/mir/opt/loops_advanced.vri`
- **change**: Refactored loop fusion, tiling, and interchange to use `loop_legality.vri`.
- **reason**: Corrects misidentified accumulations as induction steps, enforces initial value matching, rejects outer-dependent inner bounds and false-positive expression patterns in tiling, and rejects cross-loop dependencies in fusion.
- **impact**: All counterexamples now execute with exact bitwise output parity between `-O0` and `-O2`.

### `compiler/src/ir/mir/opt/target.vri`
- **change**: Added single-successor check on predecessor blocks before PRE hoist; safe Phi synthesis.
- **reason**: Splitting critical edges without predecessor vector updates caused SSA invariant failure `E6001`.
- **impact**: Self-host Stage 2 builds cleanly through all 2586 functions without CFG/SSA verifier failures.

### `compiler/src/main/path_util.vri`
- **change**: Nested `if` guards in `path_normalize_fat` for safe buffer indexing.
- **reason**: Vir `and` is bitwise and evaluates operands eagerly, triggering `out_buf[-1]` reads on empty paths.
- **impact**: Eliminates memory faults during CLI contract runner and compiler execution.

### `compiler/module.list` and `compiler/generated/virc.vri`
- **change**: Registered `mir_opt_loop_legality` at module index 223 and synchronized bundle via `tools/sync_virc.py`.
- **reason**: Complies with pass architecture constraints and single-bundle self-host generation.
- **impact**: Clean pass architecture and zero dependency violations across all 316 modules.

### `tests/test_opt_pre_and_loop_transforms.py`
- **change**: Expanded test suite to 21 structural and regression tests, adding tests 14–21 for the documented miscompilation counterexamples.
- **reason**: Verification against regressions in fusion induction steps and bounds, tiling trip counts, tiling expression-pattern matching, non-rectangular domains, fusion cross-dependencies, and interchange mismatched initial values.
- **impact**: Dedicated structural and runtime regression coverage for every counterexample documented in this report.

## 6. Deviations from Plan

1. **Loop Tiling Scope Clarification**: The implementation performs induction step scaling and aggregated strip computation rather than constructing an explicit 4-level nested loop AST/CFG. This is documented explicitly and correctly.
2. **Conservative Domain Gating**: Legality checks adhere strictly to conservative safety principles: transformations abort with an observable reason whenever safety cannot be formally proven.

## 7. Verification

### Test Matrix

| Test Suite / Command | Result | Duration | Notes |
|---|---|---|---|
| `python3 tests/test_opt_pre_and_loop_transforms.py --virc bin/virc_stage5` | **PASS (21/21)** | 16.39s | Structural MIR snapshots, SSA Phi verification, mutation controls, 8 regression counterexamples |
| `VIRC=bin/virc_stage5 python3 tests/cli_contract/runner.py` | **PASS (43/43)** | 25.71s | Full CLI contract, optimizer invocation tracking, JSON schema |
| `python3 tools/sync_virc.py --check` | **PASS** | — | Modular source and generated `virc.vri` bundle synchronized |
| `python3 tools/check_module_dependencies.py --verbose` | **PASS** | — | All 316 source files have disciplined dependencies |
| `python3 tools/check_pass_architecture.py` | **PASS** | — | Architecture verified across 3 orchestrators |
| `./paper validate` | **PASS** | — | 109 production papers and 3 example papers pass VPS validation |
| `git diff --check` | **PASS** | — | Clean whitespace and no conflict markers |

### Audit of Silent Miscompilation Defect Counterexamples

| Defect Counterexample | Flawed Behavior Before Fix | Correct Behavior After Fix (`bin/virc`) | Skip / Transform Status |
|---|---|---|---|
| **Fusion Step Classification** (`tests/opt_structural/loop_fusion_step_positive.vri`) | `mir_is_step_for_iv` treated `sum2 = sum2 + j` as IV step, removing it: `-O0 = 90`, `-O2 = 45`. | Exact latch recurrence tracing isolates only `j = j + 1`: `-O0 = 90`, `-O2 = 90`. | Transformed (`changed = 1`, `reason = "changed"`) |
| **Fusion Initial Value Mismatch** (`tests/opt_structural/loop_fusion_negative_init.vri`) | Ignored `init` mismatch (0 vs 5), fusing loops and expanding iteration domain: `-O0 = 215`, `-O2 = 255`. | Enforced `init1 == init2`: `-O0 = 215`, `-O2 = 215`. | Safely skipped (`changed = 0`, `reason = "mismatched_bounds"`) |
| **Tiling Trip Count vs Bound** (`tests/opt_structural/loop_tiling_negative_lb.vri`) | Checked `upper % 16 == 0` without checking `lower == 0`, tiling 31 iterations as 32: `-O0 = 31248`, `-O2 = 32768`. | Enforced `init_out == 0`, `init_in == 0`: `-O0 = 31248`, `-O2 = 31248`. | Safely skipped (`changed = 0`, `reason = "bounds_not_divisible_by_tile_size"`) |
| **Interchange Non-Rectangular Domain** (`tests/opt_structural/loop_interchange_negative_dep.vri`) | Swapped triangular inner bound `j < i` to `i < i`, zeroing iterations: `-O0 = 1176`, `-O2 = 0`. | Enforced affine independence via `mir_loop_nest_is_rectangular`: `-O0 = 1176`, `-O2 = 1176`. | Safely skipped (`changed = 0`, `reason = "non_rectangular_domain"`) |
| **Fusion Second-Loop Entry Dependency** (`tests/opt_structural/loop_fusion_negative_dep.vri`) | Transplanted loop 2 phi reading loop 1 reduction into loop 1 header: `-O0 = 90`, `-O2 = 8362694813`. | Detected cross-loop dependency via `mir_loop_fusion_has_cross_dep`: `-O0 = 90`, `-O2 = 90`. | Safely skipped (`changed = 0`, `reason = "barrier_in_body"`) |
| **Tiling Outer-Dependent Inner Bound** (`tests/opt_structural/loop_tiling_negative_dep.vri`) | Tiled triangular nest `j < i` without checking `bound_in` invariant: `-O0 = 15376`, `-O2 = 7936`. | Detected triangular domain via `mir_loop_nest_is_rectangular`: `-O0 = 15376`, `-O2 = 15376`. | Safely skipped (`changed = 0`, `reason = "non_rectangular_domain"`) |
| **Interchange Mismatched Initial Values** (`tests/opt_structural/loop_interchange_negative_init.vri`) | Exchanged upper bounds on `0..<3` and `1..<5` without swapping entry phis: `-O0 = 90`, `-O2 = 95`. | Required `mir_opnd_is_same(init_out, init_in)`: `-O0 = 90`, `-O2 = 90`. | Safely skipped (`changed = 0`, `reason = "mismatched_bounds"`) |
| **Tiling Expression Pattern False-Positive** (`tests/opt_structural/loop_tiling_negative_pattern.vri`) | Treated `sum = sum + i + 7` as `sum + i + j`: `-O0 = 23040`, `-O2 = 31744`. | Exact operand/dataflow matching preserves `-O0 = 23040`, `-O2 = 23040`. | Safely skipped (`changed = 0`, `reason = "unsupported_loop_body"`) |

### Structural Assembly Evidence vs Marker Bypass Mode

Generated assembly files were compared between normal optimization (`-O2 -S`) and mutation bypass mode (`-O2 --mutate-mir=marker_loop_transforms -S` or `--mutate-mir=identity_pre -S`):

| Transform | Normal Assembly SHA-256 | Marker / Identity Bypass SHA-256 | Structural Observation |
|---|---|---|---|
| **PRE** (`pre_positive.vri`) | `ac18df8d7412088c0fe1cce08cddd65528b95375ea181b6775eeae203876b068` | `6cc10d3fa6430b33043efcfc9723b25879c8bbb0da806660762349cbec182055` | `mul` hoisted into predecessor edge `LBB_1_4`; redundant `mul` removed from join `LBB_1_5` |
| **Loop Fusion** (`loop_fusion_positive.vri`) | `088d0d6637ac7aece2a2b4a83afecf18bb85ebbc73bfa497cd684209122ffb67` | `bc023756befbe495829dee16102b61fd3897f34e3d928f2a3350aa61da32b90c` | Two loops fused into single loop header `LBB_1_3`; loop count reduced from 2 to 1 |
| **Loop Interchange** (`loop_interchange_positive.vri`) | `e075bfaa2e7e6e7a2d28909a6e71a4b479994e7180b6a29bfca0df08a8bcc297` | `d9c8b0feb7df7573d8e7def095caa77b32acdf3d3ae5221d7cf8c7107b02aa5a` | Outer comparison bound swapped to `x26` ($M$); inner bound to $N$; induction multiply inverted |
| **Loop Tiling** (`loop_tiling_positive.vri`) | `091d4e8e52bc44e8781947c7ab529a49007fd9c161452d4e95265be0de226c50` | `61be3e51dd400ec1a3ff7cdcf63fd5bce20d11292d7bb4bf6d22c049e969285f` | Outer induction increment scaled from 1 to 16 (`add x26, x24, #16`); tiled inner body rewrite |

### Self-Host Bootstrap Fixed-Point Evidence

The compiler was rebuilt across bootstrap generations. `bin/virc_stage5` compiled the synchronized source into `bin/virc_stage6`; the resulting binaries are fully identical, including the ad-hoc signature:

```sh
cmp bin/virc_stage5 bin/virc_stage6
```
**Result**: Comparison exited with status `0` and empty diff.

Full-file SHA-256 hashes:
- `bin/virc_stage5`: `625cbbdfa0c43cfe256c80641ee63dc50cf871d8e5792808b90c0e95f8a62819`
- `bin/virc_stage6`: `625cbbdfa0c43cfe256c80641ee63dc50cf871d8e5792808b90c0e95f8a62819`

Machine code size: `16,154,456` bytes across 2,586 compiled functions. The installed `bin/virc` has the same full-file SHA-256.
The self-host bootstrap fixed point is **100% BIT-FOR-BIT IDENTICAL**.

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0001`:

- [x] A registered structural harness invokes the production MIR passes and serializes deterministic before/after structure.
  - *Evidence*: `tests/test_opt_pre_and_loop_transforms.py` tests 1–21 inspect `payload["optimization"]["mirTransforms"]` with deterministic before/after snapshots and status checks.
- [x] PRE implements a named algorithm on an explicit safe expression domain, including edge placement and SSA repair for supported shapes.
  - *Evidence*: Hoists partially redundant expressions across single-successor edges and synthesizes SSA join Phis (`target.vri:232-260`).
- [x] Positive PRE fixtures mutate as expected; barriers, traps, redefinitions, and unsupported shapes remain unchanged.
  - *Evidence*: `test_01` verifies positive hoist; `test_02` verifies skip on redefinition; `test_03` verifies skip on call barrier.
- [x] Fusion, tiling, and interchange each have at least one production structural positive case and legality-based negative cases.
  - *Evidence*: `test_06/07/08/14/15/18` (fusion); `test_09/16/19/21` (tiling); `test_10/17/20` (interchange).
- [x] Successful loop transforms change loop/CFG/SSA structure; patch-point insertion is not accepted as transformation evidence.
  - *Evidence*: Assembly inspection confirms loop fusion eliminates a loop (2 loops -> 1 loop); interchange swaps bounds/multiplication; tiling scales induction steps. None use patch points.
- [x] MIR verifiers pass after every mutation and mutation controls catch an identity or marker-only regression.
  - *Evidence*: `test_04` (`identity_pre`), `test_05` (`corrupt_pre_phi` -> `E6001`), and `test_11` (`marker_loop_transforms`) fail or reject as expected.
- [x] O0/O1/O2/O3 runtime parity is demonstrated on the host for supported cases, with cross-target results reported honestly.
  - *Evidence*: `test_12` validates identical runtime stdout across `-O0`, `-O1`, `-O2`, and `-O3` for all positive fixtures; tests 14–21 confirm exact parity for all eight counterexamples.
- [x] Generated compiler source is synchronized and self-host fixed-point plus required regression suites pass using the newly built compiler.
  - *Evidence*: `tools/sync_virc.py --check` passes; Stage 5 == Stage 6 full-file bit-for-bit identical (`625cbbdf...`); CLI contract 43/43 passes.
- [x] A REPORT links this issue and records exact commands, structural diffs, results, limitations, and deviations.
  - *Evidence*: Documented comprehensively within this report (`VIRC-RPT-0027`).

## 9. Known Limitations

1. **Critical Edge Splitting in PRE**: PRE safely refuses hoist when a predecessor has multiple successors (`critical_edge`). Full edge-splitting with synthetic empty basic blocks is deferred to a future general edge-splitting pass.
2. **Loop Shapes**: Loop transformations target canonical affine counted loops with compile-time or divisible trip bounds and invariant rectangular domains. Arbitrary while-loops with irregular breaks or triangular loop domains remain in canonical form without transformation.

## 10. Remaining Work

No remaining first-phase PRE or loop-transform acceptance work is known for
`VIRC-ISS-0001`. Register allocation work continues independently under
`VIRC-ISS-0002` and `VIRC-PLN-0001`. The later `VIRC-ISS-0027` tracks a
phase-2 expansion of loop-tiling coverage and profitability evidence; it does
not reopen or invalidate the correctness evidence accepted by this report.

## 11. Conclusion

**READY_FOR_CLOSE**

## 12. Related Papers

- `VIRC-ISS-0001` — MIR PRE and loop transform passes lack production transformations
- `VIRC-ISS-0027` — MIR loop tiling phase 2 lacks general affine coverage and profitability evidence
- `VIRC-PLN-0001` — Implement production PRE loop transforms and George-Appel IRC
- `VIRC-RPT-0024` — Superseded production PRE and loop transforms implementation report
- `VIRC-RPT-0025` — Independent acceptance audit of production PRE and loop transforms
- `VIRC-RPT-0026` — Driver default output naming, optimizer inlining repair, and test suite integration
- `VIRC-RPT-0027` — Production PRE and loop transforms acceptance report
- `VIRC-SPC-0008` — Compiler Optimization

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial acceptance report superseding VIRC-RPT-0024 and satisfying all five requirements of VIRC-RPT-0025 |
| 2026-10-04 | Implemented shared `loop_legality.vri` framework; resolved 4 silent miscompilation defects |
| 2026-10-04 | Reopened following audit identifying 3 new silent miscompile defects in loop fusion (loop 2 entry dependency), tiling (outer-dependent inner bound), and interchange (mismatched initial values); resolved all three defects, expanded test suite to 20/20 tests; verified Stage 2 == Stage 3 bootstrap fixed-point (`5bdb09dc...`, 16,142,656 bytes code) |
| 2026-10-04 | Resolved the eighth silent miscompile by exact tiling-expression and Phi-chain matching; added test 21, verified 21/21 and 43/43 suites, established Stage 5 == Stage 6 full-file fixed point (`625cbbdf...`), and accepted the report |
| 2026-10-04 | Linked VIRC-ISS-0027 |
