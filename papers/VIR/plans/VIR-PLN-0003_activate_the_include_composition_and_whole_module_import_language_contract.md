---
id: "VIR-PLN-0003"
type: "PLAN"
domain: "VIR"
title: "Activate the include composition and whole-module import language contract"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
components:
  - "module-system"
  - "include"
  - "import"
  - "language-governance"
related:
  issues:
    - "VIR-ISS-0017"
  plans: []
  reports:
    - "VIR-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "module-composition"
  - "module-namespace"
  - "spec-activation"
---

# VIR-PLN-0003 — Activate the include composition and whole-module import language contract

## 1. Objective

Finalize the language-owned distinction between same-module implementation
composition through `include M` and independent module consumption through
`import M`, synchronize every active parent specification, and activate
`VIR-SPC-0021` without claiming compiler conformance.

## 2. Source Issues

- VIR-ISS-0017

The source issue already records the grammar decision and the compiler gap.
This plan owns only the normative language lifecycle needed to close that
decision record.

## 3. Scope

### In Scope

- audit repository use of include aliases and whole-module imports;
- revise `VIR-SPC-0006`, `0014`, `0017`, and `0018` for one consistent
  composition-versus-namespace contract;
- activate `VIR-SPC-0021` as the focused authority;
- preserve `VIRC-ISS-0065` as the separate compiler/LSP conformance owner;
- complete VPS report, registry, validation, and issue closure.

### Out of Scope

- compiler, resolver, parser, LSP, stdlib source, or test behavior changes;
- implementation of module namespace symbols or include-alias rejection;
- module initialization timing, ordering, failure, or cycle semantics;
- package acquisition and version solving.

## 4. Current Architecture

The grammar revision already makes `import M` the sole whole-module form and
rejects `import from M`. `VIR-SPC-0021` v0.3.0 is in REVIEW with the intended
semantic distinction, but active parent specs still describe include as a
namespace-producing directive and publish include aliases. The compiler still
accepts one compatibility fixture using multi-include aliases and still
source-splices whole-module imports; those implementation gaps are recorded by
`VIRC-ISS-0065`.

Repository audit found no include alias or whole-module import in production
`.vri` sources under `compiler/src`, `stdlib/vir`, or `tools`. The only include
alias source is the explicit compatibility fixture
`tests/modules/test_multi_include_alias_compat_positive.vri`.

## 5. Proposed Architecture

`VIR-SPC-0021` becomes the ACTIVE focused contract. Parent specs state:

- `include M` composes a fragment into the current logical module, contributes
  declarations to unqualified scope, creates no namespace, and accepts no
  alias;
- `import M [as A]` preserves an independent module/export boundary and binds
  a qualified namespace;
- `import X from M` creates selected unqualified bindings only for exported
  declarations;
- compiler implementation status is tracked separately and cannot delay or
  redefine an accepted language decision.

## 6. Design Decisions

### Decision 1 — Language activation is independent of implementation status

**Decision:** Activate the language contract after compatibility and parent
SPEC audits; track nonconforming compiler/LSP behavior exclusively through
`VIRC-ISS-0065`.

**Rationale:** A VIR issue decides language semantics. Making ACTIVE status
depend on prior compiler implementation would let current behavior define the
language and collapse the VIR/VIRC ownership boundary.

**Alternatives considered:** keep the focused SPEC in REVIEW until compiler
work is complete.

**Trade-offs:** the repository temporarily contains explicitly documented
nonconforming compatibility behavior until `VIRC-ISS-0065` is implemented.

### Decision 2 — Include alias is removed from canonical grammar

**Decision:** `include M as A` is invalid; aliases remain available only for
whole-module and selective import.

**Rationale:** include creates no namespace to rename. The repository has no
production `.vri` dependency on include aliases.

**Alternatives considered:** retain include alias as a compatibility form.

**Trade-offs:** the existing compatibility fixture becomes evidence of a known
compiler conformance gap rather than valid language syntax.

## 7. Implementation Plan

### Phase 1 — Compatibility and contradiction audit

- files/modules: production `.vri` sources, module fixtures, active module
  specifications;
- changes: record actual alias usage and every stale namespace claim;
- dependencies: `VIR-ISS-0017`, `VIRC-ISS-0065`;
- expected result: bounded migration surface and explicit conformance owner.

### Phase 2 — Normative synchronization

- files/modules: `VIR-SPC-0006`, `0014`, `0017`, `0018`, and `0021`;
- changes: remove include alias/namespace semantics, add focused references,
  document composition collisions and import boundaries, activate `0021`;
- dependencies: language-owner decision already recorded by the source issue;
- expected result: no contradiction among ACTIVE language papers.

### Phase 3 — Verification and closure

- files/modules: VPS issue, plan, report, and registry;
- changes: map every acceptance criterion to audit/spec evidence and validate;
- dependencies: synchronized normative papers;
- expected result: accepted report and closed `VIR-ISS-0017`.

## 8. Compatibility

- Source using `include M as A` must migrate to `include M` and unqualified
  composed declarations, or to `import M as A` for an independent namespace.
- No production repository `.vri` source currently requires that migration.
- No ABI, serialized format, LSP protocol, or stdlib runtime behavior changes
  are made by this language-only plan.
- Current compiler acceptance of include aliases and source-flattened imports
  remains a known nonconformance under `VIRC-ISS-0065`.

## 9. Migration

Replace:

```vir
include M as A
```

with `include M` when `M` is an implementation fragment, or `import M as A`
when `M` is an independent module API. Selective unqualified consumption uses
`import X from M`.

## 10. Validation Plan

- search all production `.vri` sources and fixtures for include aliases and
  whole-module imports;
- search all synchronized SPECs for stale include namespace/alias claims;
- verify focused and parent metadata, versions, and revision histories;
- run `./paper registry --check` and `./paper validate`;
- do not use compiler acceptance as evidence that invalid compatibility syntax
  is normative.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Parent specs retain a hidden contradiction | Medium | High | Search canonical forms and keyword/migration tables after editing |
| Language closure is mistaken for compiler completion | Medium | High | State `VIRC-ISS-0065` limitation in SPEC, ISSUE, and REPORT |
| Compatibility usage is missed | Low | Medium | Audit all production `.vri` roots and retain exact search evidence |

## 12. Rollback Strategy

Restore the five SPEC revisions and lifecycle metadata as one paper-only
change. No compiler artifact, source migration, or runtime state requires
rollback.

## 13. Exit Criteria

- [x] compatibility audit is recorded;
- [x] parent language specs are synchronized;
- [x] `VIR-SPC-0021` is ACTIVE;
- [x] `VIRC-ISS-0065` remains the explicit implementation owner;
- [x] report is accepted and `VIR-ISS-0017` is CLOSED;
- [x] VPS registry and validation gates pass.

## 14. Related Papers

- `VIR-ISS-0017` — source language decision record.
- `VIR-SPC-0021` — focused dependency contract.
- `VIRC-ISS-0065` — compiler and tooling conformance owner.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Completed after ACTIVE focused contract, synchronized parent specs, accepted report, and issue closure |
| 2026-10-10 | Plan created and activated after compatibility and parent-SPEC audit |
| 2026-10-10 | Linked VIR-RPT-0003 |
