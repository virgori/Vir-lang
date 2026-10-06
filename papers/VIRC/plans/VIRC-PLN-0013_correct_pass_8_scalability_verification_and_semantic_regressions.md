---
id: "VIRC-PLN-0013"
type: "PLAN"
domain: "VIRC"
title: "Correct Pass 8 scalability verification and semantic regressions"
status: "COMPLETED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow-analysis"
  - "non-lexical-lifetimes"
  - "compiler-performance"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0026"
    - "VIRC-ISS-0028"
  plans: []
  reports:
    - "VIRC-RPT-0029"
supersedes: null
superseded_by: null
tags:
  - "corrective-verification"
  - "borrow-checker"
  - "pass8"
  - "scalability"
---

# VIRC-PLN-0013 — Correct Pass 8 scalability verification and semantic regressions

## 1. Objective

Independently re-audit the implementation and evidence previously accepted in
`VIRC-RPT-0028`, repair semantic regressions, replace unsupported complexity
claims with deterministic operation-count evidence, and leave deeper
projection/loop optimization in a separately scoped ISSUE.

## 2. Source Issues

- `VIRC-ISS-0026` — Pass 8 borrow checker super-quadratic NLL and state scans.

## 3. Scope

### In Scope

- audit path/move and shadowing behavior introduced by the first optimization;
- repair maintained box indices and dynamically resize hash tables;
- add stable Pass 8 counters and strengthen the registered scaling gate;
- add semantic regression fixtures;
- run all optimization levels, compiler checks, and self-host fixed point;
- supersede inaccurate closure evidence and open the phase-2 ISSUE.

### Out of Scope

- changing Vir ownership semantics;
- fully optimizing projection overlap and loop dependency chains, tracked by
  `VIRC-ISS-0028`;
- unrelated dirty working-tree changes.

## 4. Current Architecture

Pass 8 keeps ordered vectors for deterministic traversal and auxiliary hash
maps for named lookup. Block NLL uses a reverse liveness table. The accepted
report incorrectly described fixed buckets as dynamic, treated wall-clock
growth as proof of strict linearity, and did not detect projection-move or
shadowed-name regressions.

## 5. Proposed Architecture

- Keep deterministic state vectors, with dynamically resized hash maps whose
  nodes carry the current vector index.
- Update indices on push, set, pop, truncate, and swap-remove.
- Count AST/NLL visits, hash work, overlap checks, rehash work, and release
  steps behind the internal `--borrow-stats` flag.
- Treat deterministic absolute Pass 8 operation growth as the asymptotic
  oracle; retain wall time as an independent regression ceiling.
- Preserve conservative overlap fallback for projections and track its next
  optimization phase in `VIRC-ISS-0028`.

## 6. Design Decisions

### Decision 1 — Deterministic counters over delta timing

**Decision:** Gate absolute Pass 8 operation growth and total borrow-workload
wall growth separately.

**Rationale:** Subtracting two small wall-clock measurements amplifies scheduler
noise and discrete rehash thresholds. Compiler-owned counters are repeatable
and directly measure implemented work.

**Alternatives considered:** A delta-time-only gate was rejected because it
both skipped unstable samples and could report false superlinearity.

**Trade-offs:** Counters must be maintained when Pass 8 algorithms change.

### Decision 2 — Correctness before projection micro-optimization

**Decision:** Remove the unsound exact moved-root shortcut, preserve the
projection fallback, and open `VIRC-ISS-0028` for root-partitioned phase 2.

**Rationale:** An owner must remain unusable after moving one of its fields;
an exact-root lookup cannot establish that fact.

**Trade-offs:** Projection-heavy code retains avoidable scans until phase 2.

## 7. Implementation Plan

### Phase 1 — Acceptance audit and regressions

- files/modules: `moves.vri`, `nll.vri`, memory fixtures and manifest;
- changes: reproduce projection-owner use and shadowed borrower liveness;
- expected result: both regressions become permanent contracts.

### Phase 2 — Dynamic indices and counters

- files/modules: `context.vri`, `paths.vri`, `loans.vri`,
  `sem_pass8_borrow.vri`, driver args;
- changes: resize maps, maintain vector indices, add hidden deterministic
  statistics output;
- expected result: no fixed-bucket degradation or release full scan on the
  independent corpus.

### Phase 3 — Stronger performance and semantic gates

- files/modules: performance runner, gap runner;
- changes: require repeatable counters, increase sizes through 1024, support
  semantic `check` fixtures, run `-O0` through `-O3`;
- expected result: correctness and `O(N log N)`-compatible work are enforced.

### Phase 4 — Self-host and paper correction

- synchronize the generated bundle;
- prove canonical-output self-host fixed point;
- supersede `VIRC-RPT-0028` with an evidence-correct report;
- create `VIRC-ISS-0028` for phase 2.

## 8. Compatibility

No syntax, ABI, serialization, LSP protocol, public API, or stdlib migration is
introduced. `--borrow-stats` is internal diagnostic instrumentation and does
not change normal compiler output.

## 9. Migration

No migration required.

## 10. Validation Plan

- full memory contracts at `-O0`, `-O1`, `-O2`, and `-O3`;
- CLI, module-dependency, pass-architecture, source-sync, and whitespace gates;
- deterministic performance corpus through `N=1024`;
- stage rebuild plus identical canonical-output compiler images;
- VPS registry and document validation.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| stale vector indices after swap-remove | Medium | High | update the swapped node and run all semantic contracts |
| counters perturb normal compilation | Low | Medium | emit only under hidden opt-in flag |
| timing noise masks regression | Medium | Medium | use counters as the primary asymptotic oracle |
| projection optimization overclaims | Medium | High | document fallback and split phase 2 into VIRC-ISS-0028 |

## 12. Rollback Strategy

Compiler changes are localized to Pass 8, its hidden driver flag, and test
infrastructure. Revert this scoped change set and regenerate the compiler
bundle; do not rewrite semantic fixtures to accommodate a regression.

## 13. Exit Criteria

- [x] semantic regressions reproduced and corrected;
- [x] dynamically resized indices and deterministic counters implemented;
- [x] memory contracts pass at all four optimization levels;
- [x] performance gate passes through `N=1024`;
- [x] canonical and generated sources synchronize;
- [x] corrective report generated and phase-2 ISSUE linked.

## 14. Related Papers

- `VIRC-ISS-0026` — source issue.
- `VIRC-ISS-0028` — phase-2 projection and loop scalability work.
- `VIRC-RPT-0028` — superseded initial report.
- `VIRC-RPT-0029` — corrective verification report.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created corrective plan and linked VIRC-RPT-0029 |
| 2026-10-04 | Completed audit, regression repair, deterministic gates, and phase-2 handoff |
