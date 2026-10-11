---
id: "VIRC-PLN-0045"
type: "PLAN"
domain: "VIRC"
title: "Preserve nested entity declaration boundaries during selective import"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
components:
  - "source-preprocessing"
  - "selective-import"
  - "declaration-extraction"
related:
  issues:
    - "VIR-ISS-0018"
    - "VIRC-ISS-0068"
  plans: []
  reports:
    - "VIRC-RPT-0062"
supersedes: null
superseded_by: null
tags:
  - "import"
  - "entity"
  - "method"
  - "regression"
---

# VIRC-PLN-0045 — Preserve nested entity declaration boundaries during selective import

## 1. Objective

Resolve `VIRC-ISS-0068` and implement the syntax correction recorded by
`VIR-ISS-0018`: entity member methods close with nested-block `end`, the entity
alone owns the outer `end.`, and `method` is invalid at module scope. Preserve
the existing fail-closed export contract and source provenance.

## 2. Source Issues

- VIR-ISS-0018
- VIRC-ISS-0068

The issue is a confirmed compiler defect: `text_extract_func()` currently ends
an entity chunk at the first nested method terminator.

## 3. Scope

### In Scope

- Revise the active language specifications so nested entity methods close
  with `end`, and reserve `end.` for the containing declaration.
- Reject module-scope `method`; retain free-function UFCS as the external
  extension mechanism.
- Enforce the context-specific terminator in the parser and migrate active
  entity/packed-entity method sources.
- Keep declaration extraction lexical-state-aware so `end.` decoys in strings
  and comments cannot terminate an imported declaration.
- Verify registered Module ID and direct-path selective imports.
- Preserve private-by-default export rejection and source-marker behavior.
- Synchronize the generated compiler source, bump the internal compiler
  version once, and prove self-hosting fixed-point convergence.

### Out of Scope

- Entity privacy, opacity, inheritance, or class semantics.
- Whole-module namespace execution behavior tracked by `VIRC-ISS-0065`.

## 4. Current Architecture

The active specifications describe methods only as entity members, while their
global terminator table still classifies methods like top-level declarations.
The parser compounds this mismatch by accepting both `end` and `end.` for a
method and by retaining a module-scope `method` branch. `text_build_import_body()`
then asks `text_extract_func()` to copy a requested entity through the first
`end.`, which is currently allowed to belong to a nested method.

## 5. Proposed Architecture

Make source structure express ownership directly. An entity member method is a
nested block and closes with `end`; only the entity closes with `end.`. The
general parser rejects `method` at module scope, and the entity parser invokes
the function-body parser in a member mode that rejects a trailing dot. The
import expander scans outside strings/comments to the first syntactic `end.`,
which is then necessarily the entity's outer boundary for valid source.

## 6. Design Decisions

### Decision 1 — Terminator follows ownership scope

**Decision:** A method owned by an entity closes with `end`; the entity closes
with `end.`.

**Rationale:** The punctuation now distinguishes the nested member block from
its top-level declaration owner and removes the ambiguous source boundary.

**Alternatives considered:** Keeping dotted method terminators and balancing
nested declarations inside the textual import expander was rejected because it
duplicates syntax structure in a preprocessor.

**Trade-offs:** Existing method declarations require a mechanical one-character
migration and receive an explicit parser diagnostic until updated.

### Decision 2 — Entity semantics remain unchanged

**Decision:** Treat nested methods solely as declaration boundaries; do not add
access modifiers or class semantics.

**Rationale:** `VIR-SPC-0018` already permits methods inside entities and
selective import of exported types. The defect is loss of source text, not a
missing language-design decision.

**Alternatives considered:** Restricting import to data-only entities would
contradict the active specification and the include control.

**Trade-offs:** Future entity visibility design remains an independent paper.

### Decision 3 — No standalone `method`

**Decision:** Reject `method` at module scope; use `func` with an explicit first
receiver parameter for UFCS.

**Rationale:** Active specifications define `method` through entity ownership,
while UFCS already supplies the standalone extension form.

**Alternatives considered:** Retaining module-scope `method` as an alias of
`func` was rejected because it has no entity owner and duplicates UFCS.

**Trade-offs:** The dormant parser compatibility branch is removed.

## 7. Implementation Plan

### Phase 1 — Specification and parser contract

- files/modules: active VIR specifications and frontend parser declaration
  dispatch/function parsing.
- changes: specify and enforce nested `end`, reject top-level `method`, and add
  focused migration diagnostics.
- expected result: a single unambiguous dotted boundary for each entity.

### Phase 2 — Source migration and import extraction

- files/modules: entity method declarations in active stdlib/tests and
  `compiler/src/main/import_expander.vri`.
- changes: mechanically remove the method terminator dot and retain lexical
  protection for string/comment decoys.
- expected result: repository sources use canonical syntax and selective import
  retains the complete entity.

### Phase 3 — Native regression fixtures

- files/modules: isolated fixtures under `tests/modules/` and Group 3 in
  `run_tests.sh`.
- changes: add registered and direct-path positive cases plus unexported entity
  rejection.
- expected result: runtime behavior and fail-closed visibility are both locked.

### Phase 4 — Bootstrap and lifecycle closure

- files/modules: compiler version metadata, generated source, VPS plan/report.
- changes: bump once, synchronize, bootstrap to a binary fixed point, record
  evidence, and close the issue.
- expected result: released native compiler and papers agree with canonical
  modular source.

## 8. Compatibility

- This is an intentional source migration: nested `end.` becomes `end` for
  entity methods, while the surrounding entity keeps `end.`.
- Module-scope `method` is removed; equivalent extension behavior uses `func`
  and UFCS.
- No ABI, serialized-format, LSP protocol, public API, or stdlib behavior
  changes are intended.
- Existing unexported and missing-symbol imports remain rejected.

## 9. Migration

For each inherent method, change only its own final `end.` to `end`. Do not
change the enclosing entity's `end.`. Replace module-scope `method` with `func`
and an explicit first receiver parameter when UFCS behavior is intended.

## 10. Validation Plan

- Parser-positive fixture for nested method `end` and parser-negative fixtures
  for nested `end.` and module-scope `method`.
- Focused registered-module runtime fixture with multiple methods, a nested
  statement block, and lexical `end.` decoys.
- Direct-path compatibility fixture.
- Negative unexported entity fixture with machine-JSON diagnostic assertion.
- Provider and include controls.
- Group 3 module tests and compiler source self-check.
- Generated-source sync check, version-policy test, and multi-stage bootstrap
  fixed-point comparison.
- `./paper validate` after report and lifecycle transitions.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scanner mistakes `end.` inside strings/comments for syntax | Medium | High | Track lexical state and add decoy fixtures |
| Mechanical migration changes an enclosing entity terminator | Medium | High | Use structure-aware rewrite and compile every touched source set |
| Legacy method spelling receives a secondary parser error | Low | Med | Add context-specific diagnostic and recovery |
| Export enforcement regresses | Low | High | Retain the existing validation path and add an entity-specific negative test |
| Generated compiler diverges from modular source | Low | High | Sync check plus fixed-point bootstrap |

## 12. Rollback Strategy

Revert the parser/spec correction and source migration together, restore the
prior generated bundle/version metadata, and reopen both source issues. No
persisted data rollback is required.

## 13. Exit Criteria

- [x] `VIR-ISS-0018` specification and parser contract implemented;
- [x] active repository method sources migrated to nested `end`;
- [x] registered, direct-path, include-control, and export-negative regressions pass;
- [x] Group 3 and compiler source self-check pass;
- [x] generated-source sync and bootstrap fixed point pass;
- [x] report accepted and `VIRC-ISS-0068` closed.

## 14. Related Papers

- `VIR-ISS-0018` — method ownership and terminator contract.
- `VIRC-ISS-0068` — selective-import compiler defect.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Plan created and activated for implementation |
| 2026-10-10 | Linked VIR-ISS-0018 |
| 2026-10-10 | Revised implementation around nested method `end` and top-level `method` rejection |
| 2026-10-10 | Linked VIRC-RPT-0062 |
| 2026-10-10 | Completed after accepted report VIRC-RPT-0062 and closure of both source issues |
