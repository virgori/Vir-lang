---
id: "VIRC-PLN-0001"
type: "PLAN"
domain: "VIRC"
title: "Implement production PRE loop transforms and George-Appel IRC"
status: "ACTIVE"
created: "2026-10-02"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "mir"
  - "lir"
  - "optimizer"
  - "cfg"
  - "ssa"
  - "register-allocation"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0001"
    - "VIRC-ISS-0002"
  plans: []
  reports:
    - "VIRC-RPT-0024"
    - "VIRC-RPT-0025"
    - "VIRC-RPT-0026"
    - "VIRC-RPT-0027"
supersedes: null
superseded_by: null
tags:
  - "optimizer"
  - "pre"
  - "loop-transforms"
  - "george-appel"
  - "irc"
---

# VIRC-PLN-0001 — Implement production PRE loop transforms and George-Appel IRC

## 1. Objective

Replace three overstated or missing production capabilities with conservative,
structurally testable implementations:

1. a named PRE formulation over an explicit safe expression domain;
2. real loop fusion, tiling, and interchange over documented legal loop shapes;
3. George–Appel Iterated Register Coalescing in the production native allocator.

Correctness, verifier coverage, deterministic self-hosting, and truthful
capability reporting take precedence over optimization rate or benchmark wins.

## 2. Source Issues

- VIRC-ISS-0001 — MIR PRE and loop transform passes lack production
  transformations.
- VIRC-ISS-0002 — register allocator lacks George–Appel iterated coalescing.

Implementation detail and strict gates are preserved in
`docs/_legacy/plan/STRICT_PRE_LOOP_TRANSFORMS_AND_GEORGE_APPEL_IRC_PROMPT.md`. This VPS
PLAN governs lifecycle and traceability; the legacy prompt remains design input
and MUST NOT be treated as a completion report.

## 3. Scope

### In Scope

- production MIR PRE, loop analysis/canonicalization, dependence legality,
  fusion, tiling, interchange, cleanup, and pass observations;
- production LIR liveness/interference correctness needed by IRC;
- George/Briggs coalescing, worklist transitions, aliasing, coloring, spill
  rewrite, bounded reruns, target constraints, and final copy cleanup;
- deterministic pass-level structural harnesses invoking production code;
- verifier, mutation, runtime parity, target, self-host, generated-source, and
  regression gates;
- correction of active capability documentation after implementation evidence
  exists.

### Out of Scope

- changes to the Vir language specification;
- speculative load PRE without a verified memory-version/alias model;
- arbitrary irreducible loops, non-affine loop transformation, or unsupported
  effectful shapes in the first implementation;
- public optimizer APIs or a new general-purpose IR CLI unless the test harness
  proves they are necessary;
- unrelated optimizer, backend, ABI, parser, LSP, or standard-library cleanup;
- release, freeze, default binary promotion, commit, or push.

## 4. Current Architecture

CONFIRMED from active modular source on 2026-10-02:

- `mir_opt_pre` is an identity function and its pipeline call is disabled.
- `mir_opt_loop_tiling_fusion_interchange` reasons from block-vector adjacency,
  inserts `MIR_INTR_PATCH_POINT`, and increments the optimizer change counter;
  it does not mutate loop/CFG/SSA structure.
- code generation treats the patch point as marker/no-op behavior.
- PRE and loop fixtures under `tests/bootstrap_codegen/` encode expected ideas
  in source but do not call the production passes.
- `lir_allocate_registers_color` builds an interval interference graph,
  simplifies/colors once, uses move affinity as a color preference, assigns
  direct stack slots to uncolorable nodes, and removes same-location moves
  during rewriting.
- the allocator has no production IRC move/node worklists or alias union. The
  bootstrap IRC fixture implements a separate local graph/coalescer.
- `build_interference_graph_def_live_out` exists and is imported, but the
  allocator calls `build_interference_graph(intervals)`; neither name nor import
  is accepted as proof of move-aware graph correctness.
- `stdlib/vir/compiler/virc.vri` is generated from modular sources. The baseline
  `python3 tools/sync_virc.py --check` passed on the audited dirty tree.

## 5. Proposed Architecture

### Structural observation layer

Introduce a test-only production-pass interface capable of constructing or
loading minimal MIR/LIR, invoking the actual pass/allocator, serializing stable
before/after facts, and running the corresponding verifier. It must expose
transform status (`changed`, `skipped`, reason) separately from pass invocation.

### MIR analysis and mutation layer

- Define a conservative pure-expression/effect model for PRE.
- Implement a named Knoop–Rüthing–Steffen Lazy Code Motion or documented
  SSA-PRE equivalent, including fixed-point dataflow, edge placement, critical
  edge splitting where required, fresh values, phis, and cleanup.
- Build a canonical natural-loop forest from CFG/dominators/backedges with
  preheaders, latches, exits, induction/trip facts, live values, and effects.
- Build conservative affine memory-access/dependence summaries. Legality and
  profitability are separate decisions with distinct skip reasons.
- Implement fusion, tiling, and interchange as real CFG/SSA mutations only for
  the initial proven subset.

### LIR allocation layer

- Verify fixed-point liveness and move-aware def-vs-live-out graph semantics,
  including phi/parallel copies, precolored/fixed registers, register classes,
  and call clobbers.
- Implement explicit IRC node and move sets, adjacency/degree state, move lists,
  aliases, and colors.
- Interleave simplify, George/Briggs coalesce, freeze, and deterministic spill
  selection until worklists are empty.
- Assign colors through aliases. If nodes spill, rewrite with typed/aligned
  frame slots and fresh vregs, recompute analyses, and rerun with a convergence
  budget.
- Keep same-location `Mov` deletion as final canonical cleanup, not as the
  coalescing algorithm.

## 6. Design Decisions

### Decision 1 — Build the structural harness first

**Decision:** Land production-pass structural observation and mutation controls
before enabling or claiming any new optimization.

**Rationale:** Existing hand-authored fixtures remain green when production
passes are absent, so they cannot guard the implementation.

**Alternatives considered:** Extend only runtime fixtures or inspect assembly.

**Trade-offs:** Initial work does not improve generated code, but creates a
reliable oracle for every later phase.

### Decision 2 — Use named algorithms and conservative initial domains

**Decision:** PRE must identify its formulation; IRC must implement the
George–Appel state machine; loop transforms must use CFG/dependence legality.
Unsupported cases skip rather than fall back to a heuristic bearing the same
name.

**Rationale:** Algorithm names imply invariants that marker insertion,
move-biased coloring, and post-color cleanup do not satisfy.

**Alternatives considered:** Rename the current heuristics or preserve them as
partial implementations.

**Trade-offs:** The first supported domain will be narrower, but capability
claims and tests remain auditable.

### Decision 3 — Preserve canonical source ownership

**Decision:** Modify modular compiler sources first, regenerate
`stdlib/vir/compiler/virc.vri` through the verified sync workflow, and do not
edit frozen/release/spec trees.

**Rationale:** Prevents generated-source drift and protects unrelated owner
changes in the dirty worktree.

**Alternatives considered:** Patch the generated bundle directly.

**Trade-offs:** Every phase requires an additional sync/provenance gate.

### Decision 4 — Gate phases independently

**Decision:** PRE, loop transforms, and IRC have separate structural/verifier
gates even though they share one delivery plan.

**Rationale:** A green result in one subsystem must not hide an incomplete or
unsafe sibling workstream.

**Alternatives considered:** Enable all capabilities in one pipeline change.

**Trade-offs:** More intermediate checkpoints and potentially multiple REPORTs,
but failures and rollback remain localized.

## 7. Implementation Plan

### Phase 0 — Baseline and production structural harness

- files/modules: active MIR/LIR constructors and verifiers, optimizer/allocator
  test registration, `run_tests.sh`, and existing test tooling;
- changes: record source/compiler hashes and dirty state; create deterministic
  before/after facts; add mutation controls for identity PRE, marker-only loop
  behavior, move-biased-only allocation, forced legality, and omitted verifier;
- dependencies: exact active test-runner and self-host workflows must be
  re-audited before implementation;
- expected result: the new suite fails against the current implementation for
  the intended positive cases and passes for explicit negative controls.

### Phase 1 — PRE

- files/modules: `mir_opt.vri`, CFG/SSA/dominator utilities, pipeline/pass trace,
  MIR verifier, and production PRE fixtures;
- changes: expression/effect domain, fixed-point analysis, edge placement,
  critical-edge handling, fresh vregs/phis, replacement and cleanup;
- dependencies: stable CFG mutation and metadata/origin preservation helpers;
- expected result: supported diamonds and nested/control-edge cases transform
  structurally, barriers and unsafe cases skip, and only then is PRE enabled at
  the verified optimization level.

### Phase 2 — Loop canonicalization and transforms

- files/modules: MIR CFG/SSA/dominator/loop analysis, `mir_opt.vri`, pipeline,
  verifier, and production loop fixtures;
- changes: canonical natural-loop model, affine access/dependence summaries,
  legality/profitability reasons, real fusion, perfect-2D tiling with tails,
  perfect-2D interchange, and deterministic cleanup/budgets;
- dependencies: Phase 0 harness; reusable edge/block clone/remap/phi utilities;
- expected result: each transform changes the required loop structure for a
  positive fixture and leaves illegal/unsupported shapes unchanged. The
  marker-only implementation is removed as transformation evidence.

### Phase 3 — Interference graph and George–Appel IRC

- files/modules: `lir_liveness.vri`, `lir_interference.vri`,
  `lir_regalloc_color.vri`, target descriptor, verifier, phi/parallel-copy and
  frame/spill handling, production allocator fixtures;
- changes: graph correctness gate; complete node/move worklists and aliasing;
  George/Briggs decisions; simplify/coalesce/freeze/spill iteration; alias color
  propagation; typed spill rewrite and bounded allocation reruns;
- dependencies: target register policy and call-clobber rules from active source;
- expected result: safe copies merge before coloring, constrained copies remain,
  spills are rewritten legally, and allocator structural facts are deterministic.

### Phase 4 — Integration, self-host, documentation and REPORT

- files/modules: generated compiler bundle, registered test runners, active
  architecture/capability docs, and VPS REPORT paper(s);
- changes: synchronize generated source; build and compare self-host stages;
  run contract and regression matrices with the newly built compiler; correct
  overstated active documentation only after evidence exists;
- dependencies: all prior phase gates;
- expected result: modular/generated sources agree, fixed-point and required
  suites pass, limitations remain explicit, and REPORT evidence maps to both
  source ISSUEs.

## 8. Compatibility

- Source language and parser compatibility: no intended change.
- Public standard-library API: no intended change.
- Native ABI: no intended change; frame/spill and fixed-register behavior must
  nevertheless be verified per target.
- Internal MIR/LIR shape and debug/trace output may change and must remain
  deterministic or be versioned if consumed externally.
- Generated code may change at optimization levels that enable the pass, but
  observable program behavior must match O0 for supported inputs.
- Wasm and any backend not using native register allocation must be marked not
  applicable rather than reported as IRC-verified.

## 9. Migration

No source-code migration is required for VIR users. Internal generated compiler
artifacts must be regenerated through `tools/sync_virc.py`. Any test or active
documentation that currently treats hand-authored fixtures as production
evidence must be updated after replacement structural coverage is operational;
historical reports must retain provenance and receive explicit correction or
supersession rather than silent rewriting.

## 10. Validation Plan

- Before each phase, capture Git ref/dirty state, compiler path/hash/version,
  host/target, optimization level, command, stdout/stderr, exit code, and
  artifact hash where applicable.
- Run the new registered production structural contract suite; record its exact
  command in the REPORT.
- Require MIR verifier success after each CFG/SSA mutation and LIR verifier
  success after allocation/spill rewrite.
- Require positive structural changes and negative legality no-change cases for
  every supported PRE/loop/IRC path.
- Run mutation controls proving that identity, marker-only, biased-color-only,
  always-legal, and verifier-disabled implementations fail.
- Run runtime parity between O0 and enabled optimization levels on multiple
  branch/loop/register-pressure inputs.
- Run applicable host and cross-target compile/structure checks; report missing
  runtime infrastructure as UNVERIFIED, never PASS.
- Verify generated source and allocator regressions with:

```sh
python3 tools/sync_virc.py --check
python3 tools/test_opt_mov.py <new-compiler-path>
VIRC=<new-compiler-path> ./run_tests.sh min
VIRC=<new-compiler-path> ./run_tests.sh full
```

- Execute the repository's verified self-host stage/fixed-point workflow with
  the new compiler; do not substitute the pre-change `bin/virc`.
- Benchmark only after correctness gates; report compile time, code size,
  moves, spills, frame size, runtime, warmup/sample count, and noise.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PRE speculates trapping/effectful work | Medium | High | Narrow effect domain, edge placement, negative barriers, verifier/runtime parity |
| Loop rewrite corrupts CFG/SSA/phis or cleanup edges | High | High | Canonical loop model, shared mutation utilities, verifier after each mutation |
| Dependence analysis accepts an unsafe transform | Medium | High | Conservative unknown handling, separate legality/profitability, negative direction cases |
| IRC graph/coalescing introduces interference collision | Medium | High | Move-aware graph oracle, George/Briggs accept/reject tests, post-allocation verifier |
| Spill rewrite creates illegal operands or fails to converge | Medium | High | Typed slots, fresh vregs, recomputation, bounded rounds and explicit failure |
| Self-host result becomes nondeterministic | Medium | High | Stable ordering/tie-breaking, budgets, stage hash/structural comparison |
| Broad work hides incomplete sub-capability | High | Medium | Independent phase gates and REPORT evidence per source ISSUE |

## 12. Rollback Strategy

- Keep PRE disabled until its full phase gate passes.
- Disable an individual loop transform through verified pass policy if its
  structural or semantic gate fails; do not restore marker insertion as a
  substitute.
- Retain the pre-change allocator as a recoverable implementation until IRC,
  spill rewrite, verifier, and target gates pass; do not promote a new default
  binary during this plan without separate authorization.
- Revert only task-owned modular changes, regenerate derived source from the
  restored modules, and preserve failing fixtures/evidence in the REPORT.
- Do not reset unrelated dirty-tree changes or edit frozen releases.

## 13. Exit Criteria

- [x] VIRC-ISS-0001 acceptance criteria are satisfied with production
  structural and runtime evidence.
- [ ] VIRC-ISS-0002 acceptance criteria are satisfied with production allocator
  structural and verifier evidence.
- [x] Every named capability has a documented supported domain and observable
  skip reason outside it.
- [x] No patch point or hand-authored transformed fixture is used as the sole
  proof of PRE/fusion/tiling/interchange.
- [ ] Production IRC contains the full required worklist/alias iteration and
  legal spill rewrite/rerun; post-color copy deletion is only cleanup.
- [x] Mutation controls fail for every identified placeholder/fake-oracle mode.
- [x] Modular source and generated bundle are synchronized.
- [x] Self-host fixed-point, registered contract suites, min/full regression,
  and applicable target gates pass with the new compiler.
- [x] One or more REPORT papers record actual diffs, exact commands/results,
  deviations, limitations, hashes, target applicability, and conclusions.
- [x] Linked issues move to VERIFYING/RESOLVED only after their own evidence
  gates pass; neither issue is closed by compilation alone.

## 14. Related Papers

- VIRC-ISS-0001
- VIRC-ISS-0002
- VIRC-RPT-0024 — Production PRE and loop transforms implementation report
- VIRC-RPT-0025 — Independent acceptance audit of PRE and loop transforms
- VIRC-RPT-0026 — Driver default output naming, optimizer inlining repair, and test suite integration
- VIRC-RPT-0027 — Production PRE and loop transforms acceptance report
- Legacy design/provenance:
  `docs/_legacy/plan/STRICT_PRE_LOOP_TRANSFORMS_AND_GEORGE_APPEL_IRC_PROMPT.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Initial plan derived from verified production-source/test audit and linked source issues |
| 2026-10-04 | Linked VIRC-RPT-0024; VIRC-ISS-0001 verified and closed |
| 2026-10-04 | Independent audit VIRC-RPT-0025 invalidated premature completion checks; VIRC-ISS-0001 returned to IMPLEMENTING |
| 2026-10-04 | Linked VIRC-RPT-0025 |
| 2026-10-04 | Linked VIRC-RPT-0026 |
| 2026-10-04 | Linked VIRC-RPT-0027 |
