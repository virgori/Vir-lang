---
id: "VIR-PLN-0002"
type: "PLAN"
domain: "VIR"
title: "Specify entity methods and UFCS callable shadowing with terminal regression coverage"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
  - "compiler"
components:
  - "entity"
  - "methods"
  - "ufcs"
  - "conformance-tests"
related:
  issues:
    - "VIR-ISS-0019"
  plans: []
  reports:
    - "VIR-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "entity"
  - "method"
  - "ufcs"
  - "shadowing"
---

# VIR-PLN-0002 — Specify entity methods and UFCS callable shadowing with terminal regression coverage

## 1. Objective

Create focused normative specifications for entity method declarations and
UFCS callable shadowing, synchronize the broad language specs and agent syntax
guidance, and add terminal collision regressions without changing compiler
behavior.

## 2. Source Issues

- VIR-ISS-0019

The source issue records a verified documentation and regression-coverage gap;
the resolver implementation itself already conforms to the intended design.

## 3. Scope

### In Scope

- `VIR-SPC-0022`: entity and method declaration ownership and syntax;
- `VIR-SPC-0023`: UFCS resolution and callable-shadowing contract;
- English/Vietnamese language-spec cross-references and normative note;
- syntax skill alignment;
- six focused Group 11 fixtures covering terminal collisions, non-callable
  fallthrough, and direct-call pinning.

### Out of Scope

- compiler resolver or lowering changes unless a regression disproves audit;
- top-level `method`, `extend`, class semantics, access modifiers, inheritance;
- strict shadowing by non-callable fields;
- overload ranking or signature-based fallback among callable tiers.

## 4. Current Architecture

`VIR-SPC-0017`/`0018` distribute the rules across entity and UFCS sections.
Pass 6 implements name-priority tiers in `walk_method.vri`: method selection is
terminal, callable structural fields are terminal, and free UFCS is attempted
only afterward. A same-named non-callable field is skipped. Existing fixtures
cover successful priority and field/function disambiguation, but terminal
wrong-signature collisions lack an eligible free fallback oracle.

## 5. Proposed Architecture

Keep the compiler unchanged and establish two narrow ACTIVE specifications.
The broad language specs point to them and preserve their concise overview.
Group 11 contains direct executable/negative evidence for every priority edge
and terminal failure rule.

## 6. Design Decisions

### Decision 1 — Method ownership remains lexical

**Decision:** `method` exists only inside `entity` (or as a bodyless interface
member signature), closes with `end`, and has no module-scope form.

**Rationale:** Entity ownership supplies implicit `this`; free `func` already
provides external operations through UFCS.

**Alternatives considered:** top-level `method` and an `extend` block.

**Trade-offs:** external operations use explicit receiver functions rather than
a second declaration mechanism.

### Decision 2 — Callable namespace, not all-member shadowing

**Decision:** Only entity methods and structural callable fields shadow free
UFCS. A non-callable field of the same name does not block call resolution.

**Rationale:** `x.foo` is data access while `x.foo()` is callable lookup; this
preserves §11.5 and avoids making ordinary field additions break UFCS calls.

**Alternatives considered:** strict shadowing by every same-named field.

**Trade-offs:** field access and callable lookup intentionally use distinct
candidate sets.

### Decision 3 — Selected callable failure is terminal

**Decision:** Once a method or callable field is selected by name, arity and
type errors do not trigger lower-priority fallback.

**Rationale:** Signature-based fallback would make call targets unstable under
small signature changes and turn type errors into implicit dispatch changes.

**Alternatives considered:** overload-style viable-candidate search across all
three tiers.

**Trade-offs:** callers must use direct function syntax to force a colliding
free function.

## 7. Implementation Plan

### Phase 1 — Focused specifications

- files/modules: `VIR-SPC-0022`, `VIR-SPC-0023`.
- changes: define complete normative contracts and compatibility rules.
- dependencies: audited behavior in `VIR-SPC-0017` §§7.2, 11.4–11.5.
- expected result: stable focused authority for both mechanisms.

### Phase 2 — Broad-spec and guidance synchronization

- files/modules: `VIR-SPC-0017`, `VIR-SPC-0018`, Vir syntax skill.
- changes: add focused references, source-compatibility note, and correct the
  stale dotted-method quick rule.
- expected result: no active or agent-facing contradiction.

### Phase 3 — Native conformance fixtures

- files/modules: `tests/strict_v2/`, Group 11 in `run_tests.sh`.
- changes: add four negative no-fallback collisions and two positive selection
  fixtures.
- expected result: every normative priority edge is executable evidence.

### Phase 4 — Verification and lifecycle closure

- files/modules: Group 11, compiler self-check, VPS registry/report.
- changes: verify no compiler change is needed, accept report, close issue.
- expected result: specification-only completion with no version bump.

## 8. Compatibility

- No current source, ABI, parser, serialized-format, LSP, or stdlib behavior
  changes are introduced.
- Adding an entity method or callable field can redirect an existing dot call.
- Changing a non-callable field into a structural function field can redirect
  an existing dot call and is potentially source-breaking.
- Direct `member(receiver, args)` with qualification when needed pins the free
  target against callable-tier additions.

## 9. Migration

No migration is required because compiler behavior is unchanged. API authors
should use direct calls where free-function target stability is required.

## 10. Validation Plan

- compile/run both positive selection fixtures;
- assert E3022 for method/callable-field wrong arity with compatible free
  fallback present;
- assert E3001 for corresponding wrong-type collisions;
- run `./run_tests.sh 11`;
- run compiler source self-check and generated-source sync check to prove no
  compiler changes are present;
- run `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tests accidentally pass through the free function | Medium | High | Give method/field and free candidates observably different results and assert diagnostics |
| Focused specs drift from English/Vietnamese language specs | Low | High | Cross-reference both and validate parallel normative wording |
| Clarification is mistaken for new compiler semantics | Medium | Medium | State unchanged behavior and require existing compiler to pass without rebuild/version bump |

## 12. Rollback Strategy

Revert the two focused specs, language-spec references, guidance correction,
and six isolated fixtures together. No binary or persisted-data rollback is
required.

## 13. Exit Criteria

- [x] both focused SPECs are ACTIVE;
- [x] English/Vietnamese and skill guidance are synchronized;
- [x] all six focused regressions and Group 11 pass;
- [x] no compiler source or version change is introduced by this issue;
- [x] report is accepted and `VIR-ISS-0019` is closed.

## 14. Related Papers

- `VIR-ISS-0019` — source issue.
- `VIR-SPC-0017` / `VIR-SPC-0018` — broad language specifications.
- `VIR-SPC-0022` — focused entity/method declaration specification.
- `VIR-SPC-0023` — focused UFCS callable-shadowing specification.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Completed after focused specs, six regressions, Group 11 verification, accepted report, and issue closure |
| 2026-10-10 | Plan created and activated after design decision and implementation audit |
| 2026-10-10 | Linked VIR-RPT-0002 |
