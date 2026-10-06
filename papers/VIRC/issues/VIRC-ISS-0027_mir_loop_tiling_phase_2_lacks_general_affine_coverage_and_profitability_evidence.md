---
id: "VIRC-ISS-0027"
type: "ISSUE"
domain: "VIRC"
title: "MIR loop tiling phase 2 lacks general affine coverage and profitability evidence"
status: "OPEN"
severity: "S3"
priority: "P2"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "mir"
  - "optimizer"
  - "cfg"
  - "ssa"
  - "loop-analysis"
  - "performance"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0001"
  plans: []
  reports:
    - "VIRC-RPT-0027"
supersedes: null
superseded_by: null
tags:
  - "optimizer"
  - "loop-transforms"
  - "loop-tiling"
  - "affine-analysis"
  - "profitability"
  - "phase-2"
---

# VIRC-ISS-0027 — MIR loop tiling phase 2 lacks general affine coverage and profitability evidence

## 1. Summary

The production MIR loop-tiling pass is correct for its currently documented
positive fixture, but its transform is an algebraic aggregation specialized to
one exact reduction shape. It requires a zero-based rectangular loop nest, a
compile-time outer bound divisible by 16, a six-instruction inner body, and the
specific carried recurrence represented by `sum = sum + i + j`.

Safe rejection is required for every shape outside that proof domain and fixed
the silent miscompilation tracked by `VIRC-ISS-0001`. It also means that VIRC
does not yet provide a general strip-mined CFG transformation, remainder/tail
handling, target-aware tile selection, or measured evidence that enabling the
pass improves representative workloads. This ISSUE tracks that second phase of
optimization work without weakening the correctness guards established by the
first phase.

## 2. Context

`VIRC-ISS-0001` and `VIRC-RPT-0027` established a production structural
harness, loop legality checks, post-pass verification, and one verified tiling
case. The final correction narrowed matching from an unsafe opcode-shape test
to an exact operand and Phi-chain proof. That correction is complete and must
remain intact.

The active implementation is
`compiler/src/ir/mir/opt/loops_advanced.vri:430-584`, registered as
`mir_opt_loops_advanced` in `compiler/module.list`. The current positive and
negative contracts are exercised by
`tests/test_opt_pre_and_loop_transforms.py`, including tests 09, 16, 19, and
21. `VIRC-SPC-0008` specifies general loop analysis and LICM but does not
currently define a normative loop-tiling algorithm or profitability contract.

## 3. Expected Behavior

- Loop tiling has an explicit, reviewable legality domain expressed in terms of
  loop structure, dependences, side effects, induction variables, and carried
  recurrences rather than exact instruction positions.
- Legal canonical affine nests can be strip-mined through real CFG/SSA
  transformation while preserving execution semantics, including supported
  non-zero lower bounds and trip counts that require a cleanup/tail path.
- The pass either preserves the original arithmetic evaluation order or proves
  that any reassociation is valid under the applicable Vir integer and
  floating-point semantics.
- Tile sizes and transform decisions use a documented profitability policy.
  Unsupported or unprofitable cases remain unchanged and report a precise skip
  reason.
- Structural tests, differential runtime tests, and reproducible benchmarks
  demonstrate both correctness and useful performance behavior. A trace label
  or transformed-looking source fixture is not sufficient evidence.

## 4. Actual Behavior

- The tile size is fixed at 16 and the aggregation constant is fixed at 120,
  the sum of the offsets `0..<16`.
- The outer bound must be an immediate divisible by 16, and both induction
  initial values must be the immediate value zero.
- The inner body must contain exactly six MIR instructions. The first three
  must form the exact `Add`/`Add`/`Move` dataflow and nested Phi recurrence
  recognized by the matcher.
- The rewrite scales the outer induction step and replaces sixteen executions
  with a closed-form aggregated addition. It does not construct a general
  four-level tiled/strip-mined CFG.
- The registered suite proves the one supported transform and safe rejection
  of several counterexamples. It does not contain a production loop-tiling
  performance benchmark, tile-size comparison, compile-time budget, or code-
  size regression gate.

## 5. Reproduction

From the repository root, inspect the active restrictions:

```sh
nl -ba compiler/src/ir/mir/opt/loops_advanced.vri | sed -n '430,584p'
rg -n "tile_size = 16|n_ib != 6|imm\(120\)|unsupported_loop_body" \
  compiler/src/ir/mir/opt/loops_advanced.vri
```

Run the current positive transform and expression/Phi-chain rejection cases:

```sh
python3 tests/test_opt_pre_and_loop_transforms.py --virc bin/virc \
  PreAndLoopTransformsTest.test_09_loop_tiling_positive_and_negative \
  PreAndLoopTransformsTest.test_21_loop_tiling_negative_expression_pattern
```

Observed result on 2026-10-04:

```text
Ran 2 tests in 1.280s
OK
```

Test 09 reports `changed = 1` for the exact `sum = sum + i + j` fixture. Test
21 reports `changed = 0`, `reason = "unsupported_loop_body"`, and O0/O2 parity
for `sum = sum + i + 7` and for a non-reduction overwrite. The latter result is
correct behavior today; it demonstrates the boundary of the supported domain,
not permission to relax matching without a new legality proof and rewrite.

## 6. Evidence

- CONFIRMED: `compiler/src/ir/mir/opt/loops_advanced.vri:433` fixes
  `tile_size = 16`.
- CONFIRMED: lines 452-462 accept only an immediate outer bound divisible by
  16 and zero immediate initial values for both loops.
- CONFIRMED: lines 472-541 require six inner-body instructions and an exact
  `Add`/`Add`/`Move` operand/Phi chain.
- CONFIRMED: lines 549-573 synthesize the closed-form arithmetic using the
  constants 16 and 120 and advance the outer induction by 16; they do not
  create a generic tiled CFG or cleanup loop.
- CONFIRMED: the focused production tests named in Reproduction pass with the
  installed `bin/virc` and preserve O0/O2 runtime parity.
- CONFIRMED: repository search finds tiling structural/bootstrap fixtures but
  no production benchmark suite that measures runtime speedup, compile-time
  cost, code size, or tile-size sensitivity for this pass.
- OBSERVED: the positive fixture is a scalar reduction with no memory-access
  locality workload, so it cannot establish the usual cache-blocking benefit
  associated with general loop tiling.
- NOT_VERIFIED: the best loop representation, dependence formulation, tail
  construction, cost model, default tile sizes, or target-specific thresholds
  for phase 2.

## 7. Scope

### Affected

- MIR loop discovery, legality and dependence analysis;
- CFG/SSA construction and verification for strip-mined loops and tails;
- loop-tiling diagnostics and optimization traces;
- optimization-level policy and target-aware profitability decisions;
- structural, differential, mutation, and benchmark coverage.

### Not affected / Unknown

- The current exact matcher and its negative correctness tests are not defects
  and must not be weakened merely to increase `changed = 1` counts.
- Loop fusion, loop interchange, PRE, and non-loop optimizer work are outside
  this ISSUE except where shared loop infrastructure is deliberately reused.
- Triangular, irregular, early-exit, exception-sensitive, atomic, volatile, or
  otherwise effectful loops are not automatically required to transform.
- Target-specific performance gains and cross-target behavior remain
  NOT_VERIFIED until the benchmark and target matrix are defined and run.

## 8. Impact

Correct programs continue to compile correctly because unsupported shapes are
left unchanged. The impact is missed optimization opportunity and an inability
to substantiate broader loop-tiling or cache-blocking claims. Hard-coded
specialization also makes future matcher expansion risky: increasing coverage
without a general legality model could reintroduce silent miscompilation.

This is classified S3 because no current correctness failure is known and a
safe fallback exists. Priority P2 records intentional follow-up after the
correctness closure of `VIRC-ISS-0001`.

## 9. Preliminary Analysis

- CONFIRMED: the current optimization is a specialized algebraic strip
  aggregation, not a general loop-nest tiling transformation.
- CONFIRMED: exact matching is necessary for the current rewrite; accepting a
  different expression while retaining the same formula is unsound.
- OBSERVED: existing loop legality helpers already expose induction, Phi,
  rectangular-domain, purity, barrier, and reduction checks that may be reused.
- HYPOTHESIS: representing canonical loops explicitly and applying CFG-level
  strip mining with a cleanup path can expand body and bound coverage while
  avoiding transform-specific closed-form arithmetic.
- HYPOTHESIS: profitability should be separated from legality so that a legal
  loop can still be skipped based on target, trip count, memory-access pattern,
  code-size cost, or profile information.
- NOT_VERIFIED: whether a polyhedral representation is necessary; a smaller
  affine loop model may be sufficient for the initial phase-2 domain.

## 10. Acceptance Criteria

- [ ] A PLAN defines the initial phase-2 legality domain, non-goals, loop/CFG
  representation, tail strategy, arithmetic-order policy, profitability model,
  target policy, rollout, and rollback.
- [ ] The production pass removes the exact six-instruction/position dependency
  for the newly supported domain and performs a real CFG/SSA strip-mining or
  equivalently general transformation whose correctness does not depend on the
  constants 16 and 120.
- [ ] Positive structural fixtures cover at least: a body with multiple pure
  operations, a supported non-zero lower bound, and a supported trip count with
  a non-empty tail. Before/after MIR proves actual loop restructuring.
- [ ] Negative fixtures cover loop-carried dependences, non-rectangular or
  unsupported domains, calls/barriers, unsupported steps, arithmetic-order
  hazards, and unprofitable cases, each with a stable skip reason.
- [ ] Differential execution compares O0 with every optimization level that
  enables tiling across deterministic boundary cases and generated legal input
  matrices; mutation controls demonstrate that the structural oracle detects
  identity and malformed CFG/SSA rewrites.
- [ ] A reproducible benchmark records hardware/target, compiler revision,
  warm-up, sample count, variance, runtime, compile time, and code size. At
  least one representative memory-locality workload shows a statistically
  reported benefit over the same compiler with loop tiling disabled, while a
  documented regression threshold gates default enablement.
- [ ] Tile-size selection is documented and tested for every enabled target;
  hard-coded defaults are permitted only when justified by benchmark evidence
  and retain a safe override or skip policy.
- [ ] Post-transform CFG/SSA and memory-contract verification passes; the full
  PRE/loop-transform suite, CLI contract suite, generated-source sync, and
  self-host fixed-point gates remain green.
- [ ] An ACCEPTED REPORT maps evidence to every criterion, states unsupported
  cases and performance limitations, and concludes whether the pass is ready
  for default production use.

## 11. Related Papers

### Issues

- `VIRC-ISS-0001` — established the safe production baseline and closed the
  first loop-transform acceptance cycle.

### Plans

- None yet. A dedicated phase-2 PLAN is required before implementation.

### Reports

- `VIRC-RPT-0027` — records the accepted first-phase implementation, exact
  matcher correction, structural evidence, and current limitations.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Opened phase-2 loop-tiling coverage and profitability issue from direct source, test, and accepted-report inspection |
| 2026-10-04 | Linked VIRC-ISS-0001 |
| 2026-10-04 | Linked VIRC-RPT-0027 |
