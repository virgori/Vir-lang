---
id: "VIR-ISS-0019"
type: "ISSUE"
domain: "VIR"
title: "Entity method declaration and UFCS callable shadowing lack focused normative contracts and terminal regressions"
status: "CLOSED"
severity: "S3"
priority: "P1"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
  - "compiler"
components:
  - "entity"
  - "methods"
  - "ufcs"
  - "callable-fields"
  - "conformance-tests"
related:
  issues: []
  plans:
    - "VIR-PLN-0002"
  reports:
    - "VIR-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "entity"
  - "method"
  - "ufcs"
  - "shadowing"
  - "source-compatibility"
---

# VIR-ISS-0019 — Entity method declaration and UFCS callable shadowing lack focused normative contracts and terminal regressions

## 1. Summary

The active language specification contains the correct entity-method and UFCS
resolution behavior, but the two mechanisms are distributed across §§7.2,
11.4, and 11.5 instead of having focused normative contracts. Existing tests
prove successful priority selection, but do not directly prove that a selected
method or callable field with an invalid call signature terminates resolution
instead of falling back to a compatible free function of the same name.

## 2. Context

`VIR-SPC-0017` defines `method` as an entity member and rejects module-scope
`method`. For `receiver.member(args)`, it orders candidates as entity method,
typed callable field, then eligible free function through UFCS. Section 11.5
also deliberately permits a non-callable field and a free function to share a
name: `x.foo` reads data while `x.foo()` remains eligible for free UFCS.

The current compiler implements this candidate-kind model. Method and callable
field selection are terminal by name within their respective callable tiers;
a wrong arity or type reports an error. A non-callable field is not a callable
candidate and does not shadow free UFCS.

## 3. Expected Behavior

- Two focused ACTIVE specifications define entity/method declaration ownership
  and UFCS callable resolution without adding `extend` or top-level `method`.
- Entity methods close with `end`; their owning entity closes with `end.`.
- `receiver.member(args)` resolves entity method, callable field, then eligible
  free function UFCS, independently of source declaration order.
- Once a method or callable field is selected, argument-count or type failure
  is terminal and must not fall back to a lower-priority candidate.
- A non-callable field must not block free-function UFCS.
- The specifications document source-compatibility risks and direct-call syntax
  for callers that need to pin the free-function target.

## 4. Actual Behavior

- The complete rules exist only as sections of the broad language specs and a
  partial functions AI spec; there is no focused entity/method or UFCS paper.
- Positive tests cover method-over-free, callable-field-over-free,
  non-callable-field-plus-free, and declaration-order independence.
- Wrong-arity and wrong-type tests exist for methods and callable fields, but
  they do not place a compatible lower-priority free function at the same name;
  therefore terminal no-fallback behavior is not locked directly.
- The Vir syntax skill still classifies `method` as an independently dotted
  definition even though the active spec makes it a nested entity member.

## 5. Reproduction

Inspect and execute:

```sh
./bin/virc tests/strict_v2/ufcs_declaration_order_e2e.vri \
  -o /private/tmp/vir_iss_0019_priority
/private/tmp/vir_iss_0019_priority

./bin/virc tests/bootstrap_codegen/cg_ufcs_strict_resolution.vri \
  -o /private/tmp/vir_iss_0019_noncallable
/private/tmp/vir_iss_0019_noncallable
```

The first fixture distinguishes method and callable-field priority from free
UFCS. The second includes `label: int` plus `func label(this: HasLabel)` and
proves that `labeled.label()` reaches the free function.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0017` §§7.2 and 11.4–11.5 define the current behavior.
- CONFIRMED: `pass6_check_method_call()` in
  `compiler/src/semantic/typecheck/walk_method.vri` implements Priority 1
  method, Priority 2 callable field, and Priority 3 free function.
- CONFIRMED: each selected method/callable-field arity or type error returns
  before the free-function branch.
- OBSERVED: `ufcs_declaration_order_e2e.vri` prints `15`, `15`, `16`, `42`;
  the first result would be `915` if the colliding free `score` won.
- OBSERVED: `cg_ufcs_strict_resolution.vri` prints a final `47`, proving a
  non-callable field named `label` does not block free UFCS `label`.

## 7. Scope

### Affected

- focused language specification and cross-references;
- entity method declaration guidance;
- UFCS callable shadowing and compatibility guidance;
- strict regression coverage for terminal no-fallback behavior.

### Not affected / Unknown

- No parser, semantic, lowering, ABI, or runtime behavior change is intended.
- No top-level `method`, `extend`, class model, access modifier, inheritance, or
  strict shadowing by non-callable fields is introduced.
- Generic UFCS specialization remains governed by `VIRC-ISS-0064` and its
  accepted implementation report.

## 8. Impact

Without focused contracts, a future resolver refactor could accidentally
reinterpret all same-named fields as blockers or add overload-style fallback
after a selected method fails type checking. Either change would alter source
semantics. API authors also lack a normative warning that adding a method,
adding a callable field, or changing a field from data to a structural function
type can redirect existing dot-call syntax.

## 9. Preliminary Analysis

- CONFIRMED: current specification and compiler agree on the three callable
  tiers and on non-callable-field fallthrough.
- CONFIRMED: explicit `member(receiver, args)` bypasses dot-call priority and
  directly selects the visible free-function name.
- CONFIRMED: implementation changes are unnecessary if the new collision
  regressions pass unchanged.
- HYPOTHESIS: focused papers and terminal collision tests are sufficient to
  prevent future semantic drift without expanding language syntax.
- NOT_VERIFIED: downstream ecosystem reliance outside this repository; the
  compatibility note therefore treats candidate additions as potentially
  source-breaking.

## 10. Acceptance Criteria

- [x] An ACTIVE focused entity/method SPEC defines ownership, canonical
  declaration forms, `this`, block termination, and module-scope rejection.
- [x] An ACTIVE focused UFCS SPEC defines callable tiers, terminal selection,
  non-callable-field fallthrough, direct-call pinning, and API evolution risks.
- [x] `VIR-SPC-0017` and `VIR-SPC-0018` link the focused contracts and retain
  §11.5 behavior with English/Vietnamese normative parity.
- [x] Registered regressions prove method wrong arity and wrong type do not
  fall back to compatible free functions of the same name.
- [x] Registered regressions prove callable-field wrong arity and wrong type do
  not fall back to compatible free functions of the same name.
- [x] Registered regressions prove non-callable-field fallthrough and explicit
  direct free-function selection despite a same-named method.
- [x] The existing compiler passes all focused fixtures without source changes
  or a compiler version bump.
- [x] VPS registry and validation gates pass with an accepted report.

## 11. Related Papers

### Issues

- `VIR-ISS-0018` — established nested entity-method ownership and removed
  module-scope `method`.
- `VIR-ISS-0004` — typed callable-field contract and raw-`ptr` exclusion.

### Plans

- `VIR-PLN-0002` — focused specification and regression plan.

### Reports

- `VIR-RPT-0002` — accepted verification report; Group 11 passes 74/74 and
  compiler source/self-hosted generated-source checks pass unchanged.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Closed after VIR-RPT-0002 accepted all criteria and VPS validation passed |
| 2026-10-10 | Opened and moved to implementation after spec/compiler/test audit |
| 2026-10-10 | Linked VIR-PLN-0002 |
| 2026-10-10 | Linked VIR-RPT-0002 |
