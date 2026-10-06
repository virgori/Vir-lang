---
id: "VIRC-ISS-0028"
type: "ISSUE"
domain: "VIRC"
title: "Pass 8 projection overlap and loop dataflow need second-phase scalability optimization"
status: "TRIAGED"
severity: "S3"
priority: "P2"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow-analysis"
  - "path-overlap"
  - "loop-dataflow"
  - "compiler-performance"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0026"
  plans:
    - "VIRC-PLN-0013"
  reports:
    - "VIRC-RPT-0029"
supersedes: null
superseded_by: null
tags:
  - "borrow-checker"
  - "pass8"
  - "phase-2"
  - "projection"
  - "dataflow"
  - "scalability"
---

# VIRC-ISS-0028 — Pass 8 projection overlap and loop dataflow need second-phase scalability optimization

## 1. Summary

The first Pass 8 scalability correction removes repeated statement-suffix
NLL scans, adds dynamically resized hash indices, and makes the independent
root-owner corpus scale within its deterministic operation-count gate.
Projection-bearing functions and loop fixed-point workloads still need a
separate optimization phase and dedicated complexity corpus.

## 2. Context

`VIRC-ISS-0026` addressed the reproduced near-cubic named-borrow workload and
restored semantic regressions found during acceptance review. Its corrective
report deliberately does not claim that every projection or loop workload is
linear. This ISSUE preserves that remaining optimization scope rather than
hiding it inside a closed report.

## 3. Expected Behavior

- Exact, ancestor, descendant, disjoint-field, constant-index, and
  dynamic-index queries use a root-owner partition before path comparison.
- One projection loan does not force unrelated root-owner queries to scan all
  active loans or moved paths.
- Loop fixed-point joins expose deterministic round and state-operation counts
  and have a registered increasing-size corpus.
- Semantic diagnostics remain identical across `-O0` through `-O3`.

## 4. Actual Behavior

- `g_pass8_has_proj_loans` is function-wide. Once nonzero, loan conflict/count
  queries retain correctness by falling back to full-vector overlap scans,
  including entries with unrelated root owners.
- Moved-path overlap queries likewise retain a conservative vector fallback
  for projections.
- `pass8_walk_loop` uses a finite monotone lattice iteration, but the current
  performance contract exercises the independent sequential-borrow corpus,
  not growing loop-state dependency chains.

## 5. Reproduction

1. Generate `N` independent owners and at least one projection loan.
2. Query loans or moved paths for each owner while requesting
   `--borrow-stats`.
3. Observe `overlap_checks` grow with unrelated live state because projection
   presence selects the conservative fallback.
4. Separately generate loop bodies whose back-edge state grows with `N` and
   record fixed-point rounds and state operations.

The committed phase-2 corpus is an acceptance deliverable; timing alone is
not sufficient evidence.

## 6. Evidence

- CONFIRMED: `compiler/src/semantic/borrow/loans.vri` selects exact hash lookup
  only when `g_pass8_has_proj_loans == 0` and otherwise evaluates path overlap
  across active loan vectors.
- CONFIRMED: `compiler/src/semantic/borrow/moves.vri` preserves projection
  correctness through overlap scans rather than a root-partitioned index.
- CONFIRMED: `compiler/src/semantic/borrow/walk_loops.vri` iterates until full
  ownership state equality but has no dedicated scaling corpus.
- CONFIRMED: `VIRC-RPT-0029` records deterministic counters and correctness
  coverage for the completed first-phase workload.
- NOT_VERIFIED: the phase-2 asymptotic bound, peak RSS, and cross-host timing.

## 7. Scope

### Affected

- projection-bearing loan and moved-path lookup;
- root-owner partition maintenance during insert, delete, and swap-remove;
- loop fixed-point round/state instrumentation;
- projection and loop scalability regression tests.

### Not affected / Unknown

- No change to language ownership or alias semantics is requested.
- The registered semantic contracts remain the correctness oracle.
- Parser, type inference, MIR, and backend performance are out of scope.

## 8. Impact

Large generated functions with projections can retain avoidable linear scans
per query, and loop dataflow lacks a deterministic complexity gate. This is an
S3 follow-up because the reproduced first-phase cubic path and identified
semantic regressions are corrected; the remaining defect is bounded to deeper
performance coverage without a demonstrated miscompile.

## 9. Preliminary Analysis

- CONFIRMED: root equality is a necessary condition for path overlap, so a
  dynamically resized root-owner partition can reject unrelated entries
  before exact projection comparison.
- CONFIRMED: the current vector remains useful for deterministic iteration;
  an auxiliary root index can preserve ordering and diagnostics.
- HYPOTHESIS: per-root buckets plus round/change counters will reduce the
  projection corpus to expected `O(N)` or `O(N log N)` work.
- NOT_VERIFIED: the best representation for dynamic-index aliases.

## 10. Acceptance Criteria

- [ ] Add dynamically resized root-owner indices for loan and moved-path
  overlap candidates, maintained by every mutator.
- [ ] Preserve exact, ancestor/descendant, disjoint-field, constant-index, and
  dynamic-index alias semantics with positive and negative fixtures.
- [ ] Add a projection-heavy increasing-size corpus with deterministic
  operation-count assertions and matched controls.
- [ ] Add loop fixed-point round/state counters and an increasing dependency
  chain corpus with a documented finite bound.
- [ ] Pass the full memory contract at `-O0`, `-O1`, `-O2`, and `-O3` with
  deterministic diagnostics and IDE facts.
- [ ] Synchronize generated compiler sources and verify self-host fixed point.
- [ ] Link an approved PLAN and ACCEPTED REPORT before resolution.

## 11. Related Papers

### Issues

- `VIRC-ISS-0026` — first-phase Pass 8 NLL/state scalability correction.

### Plans

- None yet.

### Reports

- `VIRC-RPT-0029` — corrective first-phase verification and handoff.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial triaged phase-2 issue with explicit projection and loop scalability gates |
| 2026-10-04 | Linked VIRC-PLN-0013 |
