---
id: "VIRC-ISS-0066"
type: "ISSUE"
domain: "VIRC"
title: "Entity fields and methods cannot share a name despite member-resolution contract"
status: "CLOSED"
severity: "S2"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "semantic"
  - "symbols"
  - "member-resolution"
  - "entities"
related:
  issues:
    - "STLB-ISS-0007"
    - "STLB-ISS-0032"
  plans:
    - "VIRC-PLN-0037"
  reports:
    - "VIRC-RPT-0054"
supersedes: null
superseded_by: null
tags:
  - "field"
  - "method"
  - "name-resolution"
  - "spec-conformance"
---

# VIRC-ISS-0066 — Entity fields and methods cannot share a name despite member-resolution contract

## 1. Summary

The compiler rejects an entity that declares a field and a method with the same
identifier. Active language specifications distinguish field access from calls
by syntax and resolve `x.foo(args)` to an entity method before a callable field
or free-function UFCS candidate. The rejection is therefore a compiler
conformance defect, not a missing language-design decision.

## 2. Context

`VIR-SPC-0017` and `VIR-SPC-0018`, sections 11.4 and 11.5, define:

- `x.foo` as field access;
- `x.foo(args)` as a call;
- call resolution order as entity method, callable field, then free-function
  UFCS; and
- fields and functions as permitted to share an identifier.

This contract is needed by the canonical `Vec` facade tracked by
`STLB-ISS-0032`, where storage fields `len` and `cap` must remain accessible
while public methods use `len()` and `cap()`.

## 3. Expected Behavior

Given an entity with a field `value` and a method `value()`:

- `box.value` reads the field;
- `box.value()` calls the inherent method;
- the declarations coexist in distinct member namespaces; and
- duplicate fields or duplicate methods that are not valid overloads remain
  rejected independently.

## 4. Actual Behavior

`virc --check` emits `E1001` at the method declaration and rejects the program.
The JSON diagnostic reports `phase: Parser`, but its session data shows parsing
succeeded and semantic analysis failed.

Renaming the method while leaving the field unchanged makes the same probe pass.

## 5. Reproduction

Save and check this minimal source:

```vir
entity Box:
    value: int

    method value() -> int:
        out this.value
    end.
end.

func main:
    var box = Box(value: 42)
    print(box.value)
    print(box.value())
    out 0
end.
```

Command:

```sh
./bin/virc /private/tmp/vir_field_method_same_name.vri --check
```

Observed result on compiler `2026.1.8`: `success: false`, `code: E1001`, at
the `method value` declaration. A control probe using `method read()` succeeds.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0017` section 11.4 resolves `x.foo(args)` in the order
  method, callable field, free-function UFCS; section 11.5 says parentheses are
  the sole field-access/call disambiguator and permits a shared identifier.
- CONFIRMED: `VIR-SPC-0018` sections 11.4 and 11.5 specify the same contract in
  Vietnamese.
- CONFIRMED: the same-name probe above fails with `E1001`; the distinct-name
  control probe passes with no diagnostics.
- CONFIRMED: `compiler/src/frontend/parser/stmt_decl/aggregate_def.vri` stores
  entity fields and methods as distinct AST node kinds.
- CONFIRMED: `compiler/src/semantic/symbols/walk_types.vri` registers both kinds
  in one entity scope through `pass2_register`; that registration service
  rejects any existing same-name local symbol without considering the
  field-versus-method kind pair.
- OBSERVED: the emitted diagnostic classifies the failure as a parser error even
  though the session reports semantic failure.

## 7. Scope

### Affected

- entity member symbol registration;
- field access and inherent-method dispatch when identifiers coincide;
- canonical `Vec.len()` and `Vec.cap()` facade exposure;
- diagnostic phase/message accuracy for this rejection.

### Not affected / Unknown

- The parser already preserves fields and methods as separate AST node kinds.
- Generic `native_store`/`native_load` specialization and linking remain an
  independent `STLB-ISS-0007` concern.
- Method references without a call and future overload policy are not defined
  or expanded by this issue.
- Backend correctness after successful same-name semantic resolution is not yet
  verified.

## 8. Impact

Valid Vir source is rejected, forcing public APIs to rename storage or methods
despite an unambiguous language contract. The immediate impact is the blocked
`Vec.len()`/`Vec.cap()` facade, while the general impact applies to every entity
that needs a property and an operation with the same domain name.

## 9. Preliminary Analysis

- CONFIRMED: this is not a parser grammar limitation; parsing completes before
  the semantic symbol-registration failure.
- CONFIRMED: fields and methods currently share a single collision rule in the
  entity scope even though later type-checking has separate lookup functions
  for entity methods and fields.
- HYPOTHESIS: member registration can preserve one lexical entity scope while
  admitting a field/method pair as separate symbol kinds, provided every lookup
  path selects by syntactic context and kind.
- NOT_VERIFIED: lowering, IDE facts, rename/completion, and all generic receiver
  paths after relaxing registration.

## 10. Acceptance Criteria

- [x] A field and an inherent method with the same identifier are accepted for
  both non-generic and generic entities.
- [x] `obj.name` resolves only to the field, including when a same-name method
  exists.
- [x] `obj.name(args)` resolves in the specified order: inherent method,
  callable field, then visible free-function UFCS, independent of declaration
  and import order.
- [x] Duplicate fields remain rejected; duplicate methods that violate the
  approved signature/overload policy remain rejected.
- [x] Focused positive and negative tests cover same-name `len`/`cap`, callable
  fields, free-function UFCS fallback, generics, and ambiguity diagnostics.
- [x] Diagnostics identify semantic member-name conflicts accurately and do not
  misclassify this valid coexistence case as `E1001` parser syntax failure.
- [x] The complete compiler and strict regression gates pass without changing
  the active language resolution contract.

## 11. Related Papers

### Issues

- `STLB-ISS-0032` — Vec constructors and generic receiver UFCS are blocked by
  compiler dispatch.
- `STLB-ISS-0007` — the typed collections Vec module does not compile; its
  generic native load/store defect remains independent.

### Plans

- `VIRC-PLN-0037` — Allow entity fields and methods to share identifier per member resolution contract.

### Reports

- `VIRC-RPT-0054` — Entity fields and methods name coexistence verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from active SPEC review and focused same-name/control probes |
| 2026-10-09 | Linked STLB-ISS-0032 |
| 2026-10-09 | Linked STLB-ISS-0007 |
| 2026-10-09 | Linked VIRC-RPT-0054 |
| 2026-10-09 | Closed via VIRC-PLN-0037 and verified in VIRC-RPT-0054 |
| 2026-10-09 | Reopened during post-closure audit after a legal cross-kind pair was found to hide a later same-kind duplicate in the same symbol bucket |
| 2026-10-09 | Reclosed after full-bucket duplicate detection, strengthened negative fixtures, compiler version 2026.1.9 fixed point, and refreshed Groups 3/7/11 verification |
