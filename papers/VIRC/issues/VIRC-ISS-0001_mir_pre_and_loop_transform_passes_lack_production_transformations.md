---
id: "VIRC-ISS-0001"
type: "ISSUE"
domain: "VIRC"
title: "MIR PRE and loop transform passes lack production transformations"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
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
    - "VIRC-ISS-0002"
  plans:
    - "VIRC-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "optimizer"
  - "pre"
  - "loop-transforms"
  - "structural-testing"
---

# VIRC-ISS-0001 — MIR PRE and loop transform passes lack production transformations

## 1. Summary

The production MIR optimizer does not implement PRE, and the active pass named
loop tiling/fusion/interchange only inserts a patch-point marker rather than
changing loop, CFG, or SSA structure. Existing bootstrap fixtures do not invoke
the production passes and therefore cannot detect these gaps.

## 2. Context

VIRC exposes pass IDs for PRE and loop tiling and orders them in the optimizer
pipeline. The implementation and tests were audited against the active modular
compiler source on 2026-10-02. The working tree was dirty, so this issue records
the inspected state without resetting or rewriting owner changes.

Detailed implementation requirements already exist in
`docs/_legacy/plan/STRICT_PRE_LOOP_TRANSFORMS_AND_GEORGE_APPEL_IRC_PROMPT.md`. That
legacy plan is provenance and design input, not evidence that the capability is
implemented.

## 3. Expected Behavior

- A pass named PRE performs a defined PRE formulation on a documented safe
  expression domain, repairs CFG/SSA as required, and is enabled only after
  structural and semantic validation.
- Loop fusion, tiling, and interchange change the production loop forest and
  CFG/SSA for legal positive cases and leave rejected cases unchanged with an
  observable reason.
- A successful transform changes the relevant structure; inserting a no-op
  marker MUST NOT count as the transform.
- Tests invoke the production pass and fail if it becomes identity or
  marker-only.

## 4. Actual Behavior

- `mir_opt_pre` returns its `blocks` argument unchanged. The current pipeline
  explicitly disables invocation because the function is an identity
  placeholder.
- `mir_opt_loop_tiling_fusion_interchange` scans three adjacent vector entries,
  compares two `CmpLe` instructions, inserts `MIR_INTR_PATCH_POINT`, and calls
  `mir_opt_note_change`; it does not construct or transform a loop.
- MIR lowering/code generation recognizes the patch point as a marker/no-op.
- PRE and loop bootstrap tests encode transformed source or simulate a small
  formula; they do not run and inspect the production pass.

## 5. Reproduction

From repository root:

```sh
nl -ba stdlib/vir/compiler/mir_opt.vri | sed -n '2560,2568p;4125,4157p'
nl -ba stdlib/vir/compiler/mir_opt_pipeline.vri | sed -n '107,145p'
rg -n "MIR_INTR_PATCH_POINT" stdlib/vir/compiler/lir_lower.vri \
  stdlib/vir/compiler/lir_codegen*.vri
rg -n "mir_opt_pre|mir_opt_loop_tiling_fusion_interchange" \
  tests/bootstrap_codegen
sed -n '1,100p' tests/bootstrap_codegen/cg_optimizer_pre.vri
sed -n '1,100p' tests/bootstrap_codegen/cg_optimizer_loop_tiling_fusion.vri
```

The first two commands expose the identity and marker-only implementations.
The searches show no fixture call into either production pass.

## 6. Evidence

- CONFIRMED: `stdlib/vir/compiler/mir_opt.vri:2563-2567` implements
  `mir_opt_pre` as `out blocks` only.
- CONFIRMED: `stdlib/vir/compiler/mir_opt_pipeline.vri:139-141` does not invoke
  PRE and describes it as an identity placeholder.
- CONFIRMED: `stdlib/vir/compiler/mir_opt.vri:4128-4157` performs no loop/CFG/SSA
  rewrite and inserts `MIR_INTR_PATCH_POINT` at lines 4146-4149.
- CONFIRMED: `stdlib/vir/compiler/lir_codegen.vri:462`,
  `lir_codegen_x86.vri:89`, and `lir_codegen_riscv.vri:609` classify patch
  points with marker/no-op handling.
- CONFIRMED: `tests/bootstrap_codegen/cg_optimizer_pre.vri` starts from a
  manually transformed function and a standalone bitset equation.
- CONFIRMED: `tests/bootstrap_codegen/cg_optimizer_loop_tiling_fusion.vri`
  manually writes a fused loop, calculates tile counts, and returns an
  interchange decision without observing MIR.
- OBSERVED: `python3 tools/sync_virc.py --check` reported the generated compiler
  bundle identical to the current modular sources.
- NOT_VERIFIED: performance loss, generated-code delta, or a user-visible
  correctness failure caused by these missing transforms.

## 7. Scope

### Affected

- MIR optimizer capability and pass/change reporting;
- PRE placement, loop analysis, legality and CFG/SSA mutation infrastructure;
- production pass-level test coverage;
- documentation or release claims that treat these transforms as complete.

### Not affected / Unknown

- O0 semantics are not shown to be incorrect by this audit.
- Other optimizer passes were not comprehensively audited by this issue.
- Target-specific performance impact remains NOT_VERIFIED.

## 8. Impact

The compiler silently lacks advertised optimization capabilities. The active
loop pass can record a change without performing the named transformation,
making traces and coverage misleading. Existing green fixtures cannot prevent
regression because they do not exercise production code. No direct semantic
miscompile has been established, so this is classified S2 rather than S1.

## 9. Preliminary Analysis

- CONFIRMED: PRE is deliberately disabled because safe cross-predecessor
  insertion is absent.
- CONFIRMED: loop transformation requires CFG/SSA/loop/dependence machinery
  that is not present in the inspected function.
- OBSERVED: current tests validate hand-authored examples rather than pass
  mutations.
- HYPOTHESIS: a shared canonical loop model and structural harness should be
  implemented before individual transforms to prevent local heuristics from
  being mislabeled again.
- NOT_VERIFIED: which PRE formulation and loop subset produce the best
  compile-time/performance trade-off for VIRC.

## 10. Acceptance Criteria

- [ ] A registered structural harness invokes the production MIR passes and
  serializes deterministic before/after structure.
- [ ] PRE implements a named algorithm on an explicit safe expression domain,
  including edge placement and SSA repair for supported shapes.
- [ ] Positive PRE fixtures mutate as expected; barriers, traps, redefinitions,
  and unsupported shapes remain unchanged.
- [ ] Fusion, tiling, and interchange each have at least one production
  structural positive case and legality-based negative cases.
- [ ] Successful loop transforms change loop/CFG/SSA structure; patch-point
  insertion is not accepted as transformation evidence.
- [ ] MIR verifiers pass after every mutation and mutation controls catch an
  identity or marker-only regression.
- [ ] O0/O1/O2/O3 runtime parity is demonstrated on the host for supported
  cases, with cross-target results reported honestly.
- [ ] Generated compiler source is synchronized and self-host fixed-point plus
  required regression suites pass using the newly built compiler.
- [ ] A REPORT links this issue and records exact commands, structural diffs,
  results, limitations, and deviations.

## 11. Related Papers

### Issues

- VIRC-ISS-0002 — related production optimizer/backend algorithm gap.

### Plans

- VIRC-PLN-0001 — implementation and verification plan.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from direct production-source/test audit; linked VIRC-PLN-0001 |
| 2026-10-02 | Linked VIRC-ISS-0002 |
