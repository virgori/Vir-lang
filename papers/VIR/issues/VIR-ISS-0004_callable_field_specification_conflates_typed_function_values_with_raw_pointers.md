---
id: "VIR-ISS-0004"
type: "ISSUE"
domain: "VIR"
title: "Callable-field specification conflates typed function values with raw pointers"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "language"
  - "compiler"
components:
  - "type-system"
  - "functions"
  - "ufcs"
  - "ffi"
  - "semantic-analysis"
  - "ast-to-mir"
  - "diagnostics"
  - "tests"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "callable-field"
  - "function-type"
  - "raw-pointer"
  - "ufcs"
  - "soundness"
  - "spec-conformance"
---

# VIR-ISS-0004 — Callable-field specification conflates typed function values with raw pointers

## 1. Summary

Before Vir 2.1, the active English and Vietnamese Vir language specifications
described a raw `ptr` entity field as a function-pointer field and stated that
`x.field()` calls it through UFCS resolution step 2. The current semantic checker instead treats
only a typed `func(...)` field as callable and correctly rejects invocation of
a raw `ptr` with E3021.

The specification therefore conflates two distinct types: an opaque,
FFI-compatible address with no callable signature, and a typed function value
whose parameters and result can be checked. AST-to-MIR also retains a fallback
that classifies both forms as callable, leaving the implementation internally
inconsistent even though semantic analysis currently prevents the raw-pointer
path from being reached.

## 2. Context

VIR-SPC-0017 and VIR-SPC-0018 section 11.4 define entity call resolution as:
entity method, callable field, free-function UFCS, then error. That resolution
order is useful and is not disputed by this ISSUE. The defect is the type used
to demonstrate and define the callable-field branch before the Vir 2.1
revision.

Before Vir 2.1, both active SPECs declared `Button.on_click` as `ptr`, labeled
it a function pointer, initialized it with a function, and claimed
`btn.on_click()` performs an
indirect call. Elsewhere VIR-SPC-0017 defines `ptr` as a raw, platform-word,
FFI-compatible pointer. Current strict fixtures use structural function types
such as `func(int) -> int` for successful callable-field dispatch and explicitly
expect E3021 for a `ptr` field invocation.

## 3. Expected Behavior

- A field is callable through `x.field(args)` only when its declared type is a
  typed function value such as `func(A, B) -> R` or `func(A)`.
- A raw `ptr` is never implicitly callable. It carries no parameter types,
  result type, calling convention, ABI, provenance, or lifetime guarantee from
  which a safe indirect call can be generated.
- Assignment to a typed callable field and every indirect call through it are
  checked against the declared parameter and result types.
- Callable-field invocation passes only the arguments written at the call site;
  unlike an entity method, it does not inject the receiver implicitly.
- If Vir later supports converting an FFI address to a callable value, that
  conversion must be explicit, unsafe, signature-bearing, ABI-aware, and
  specified separately. No implicit `ptr`-to-`func` conversion is permitted.
- The English and Vietnamese active SPECs must express the same rule and use
  typed callable examples.

## 4. Actual Behavior

The following records the baseline at triage, before the Vir 2.1 normative
resolution:

- At triage, VIR-SPC-0017 section 11.4 declared `on_click: ptr`, called it a
  function pointer, and stated that `btn.on_click()` invokes it.
- At triage, VIR-SPC-0018 contained the equivalent Vietnamese declaration and claim.
- Semantic UFCS resolution recognizes a callable field only when the serialized
  declared type begins with `func`; a `ptr` field falls through to E3021.
- The existing strict negative fixture requires E3021 for calling a `ptr`
  field, while the typed callable-field fixture compiles and runs.
- `scoped_field_is_callable` in AST-to-MIR nevertheless returns true for both a
  `func...` field and an exact `ptr` field. The second branch is currently
  blocked by semantic failure but contradicts the fail-closed type boundary.

## 5. Reproduction

The reported reproducer declares this field and later invokes it:

```vir
entity TaskRunner:
    id: i64
    multiplier: i64
    op: ptr
end.

func add_boost(runner: TaskRunner, value: i64) -> i64:
    out value + runner.multiplier
end.

func main:
    var runner = TaskRunner(id: 1, multiplier: 5, op: add_boost)
    print(runner.op(runner, 2))
    out 0
end.
```

The equivalent source currently stored in `.pytest_cache/test/test.vri` can be
reproduced with:

```sh
./bin/virc .pytest_cache/test/test.vri \
  -o /private/tmp/vir_iss_0004_raw_ptr_repro

./bin/virc tests/strict_v2/ufcs_pointer_field_rejected.vri \
  -o /private/tmp/vir_ufcs_raw_ptr_negative

./bin/virc tests/strict_v2/ufcs_declaration_order_e2e.vri \
  -o /private/tmp/vir_ufcs_typed_positive
/private/tmp/vir_ufcs_typed_positive
```

On 2026-10-04, the first command failed with E3021 at the indirect call. The
registered raw-pointer negative also included E3021. The typed positive
compiled and printed `15`, `15`, `16`, and `42`.

## 6. Evidence

- CONFIRMED at triage: VIR-SPC-0017:1683-1705 and VIR-SPC-0018:1714-1736
  defined UFCS callable-field resolution but used `ptr` in the normative
  example.
- CONFIRMED: VIR-SPC-0017 identifies `ptr` as a raw, platform-word,
  FFI-compatible pointer in its type table.
- CONFIRMED: `compiler/src/semantic/typecheck/walk_method.vri:133-165`
  classifies only declared field types beginning with `func` as callable and
  validates their arity and argument types.
- CONFIRMED: `compiler/src/lower/ast_to_mir/calls.vri:542-610` lowers a
  semantically resolved callable field as an ordinary indirect function call
  and passes only explicit arguments.
- CONFIRMED: `compiler/src/lower/ast_to_mir/layout/enum_names.vri:153-159`
  additionally classifies an exact `ptr` field as callable, contrary to the
  semantic checker.
- CONFIRMED: `tests/strict_v2/ufcs_pointer_field_rejected.vri` expects E3021
  for a raw-pointer field call.
- CONFIRMED: `tests/strict_v2/ufcs_declaration_order_e2e.vri` uses
  `func(...) -> ...` fields and passed with its expected output.
- OBSERVED: the exact TaskRunner reproducer failed with one E3021 at line 38,
  column 36 using repository `bin/virc`, which reports version 4.0.0, on
  checkout HEAD `e1fc2d5` with the current working tree.

## 7. Scope

### Affected

- callable-field and indirect-call type semantics;
- UFCS resolution step 2 in VIR-SPC-0017 and VIR-SPC-0018;
- examples and glossary text that use “function pointer” ambiguously;
- semantic callable classification and AST-to-MIR fallback classification;
- diagnostics and positive/negative conformance fixtures;
- any future raw-address-to-callable FFI conversion contract.

### Not affected / Unknown

- entity method precedence and free-function UFCS fallback order;
- ordinary raw-pointer data access and FFI data-pointer use;
- direct calls to statically known functions;
- existing typed callable-field behavior represented by strict positive tests;
- NOT_VERIFIED: whether any supported foreign ABI currently exposes a defined,
  explicit raw-address-to-typed-callable conversion;
- NOT_VERIFIED: ecosystem source counts that rely on implicit raw-pointer calls.

## 8. Impact

The pre-2.1 language contract instructed users to write a form the compiler
rejects and described an opaque address as safely callable. If implemented
literally, that rule would permit calls without checked parameters, result
type, ABI, or calling convention, risking wrong-register argument passing,
stack corruption, invalid control flow, crashes, and undefined behavior.

The current semantic rejection is fail-closed and a typed-field workaround is
available, so this is scoped as S2. P1 reflects that active normative documents
must not encourage an unsafe representation and that the lowering fallback
should be closed before future refactoring can bypass semantic protection.

## 9. Preliminary Analysis

- CONFIRMED: callable-field support is implemented; this is not a total absence
  of UFCS step 2. The supported representation is a structural `func` type.
- CONFIRMED: E3021 for `runner.op(...)` when `op: ptr` is consistent with the
  strict negative test and the safer current semantic behavior.
- CONFIRMED: changing the declaration to
  `op: func(TaskRunner, i64) -> i64` supplies the signature required by the
  reported explicit call `runner.op(runner, i)`.
- OBSERVED: specification terminology uses “function pointer” for both typed
  function values and raw pointers, obscuring the safety boundary.
- HYPOTHESIS: removing the raw-`ptr` lowering fallback after aligning both
  SPECs is sufficient to make callable classification fail closed at all
  currently identified stages.
- NOT_VERIFIED: the complete FFI design needed for explicitly importing a
  foreign code address as a typed callable value.

## 10. Normative Resolution (2026-10-04)

Vir 2.1 defines callable fields as typed structural function values
`func(P...) -> R` or the no-result form `func(P...)`. Calling a field passes
only the arguments written at the call site and never injects the entity as an
implicit receiver. Assignment and invocation are checked against the declared
signature.

Raw `ptr` remains an opaque, non-callable address with no implicit conversion
to a function type. Vir 2.1 defines no raw-address-to-callable operation. Any
future FFI conversion must be explicit and unsafe and must specify the full
signature, ABI/calling convention, provenance, and lifetime constraints.

This resolution changes only the VIR specification papers. Removing the exact
`ptr` callable fallback in lowering, aligning all compiler predicates, and
expanding conformance/bootstrap evidence are VIRC implementation work and are
intentionally not performed here. The ISSUE therefore remains `TRIAGED`.

## 11. Acceptance Criteria

- [x] VIR-SPC-0017 and VIR-SPC-0018 define a callable field as a declared
  structural function type `func(P...) -> R` or its no-result form, not `ptr`.
- [x] Both section 11.4 examples use a typed callable field and explain that
  only explicit arguments are passed; no receiver is injected for field calls.
- [x] Both SPECs define `ptr` as non-callable and forbid implicit
  `ptr`-to-`func` conversion.
- [x] Any supported raw-address-to-callable FFI operation has explicit unsafe
  syntax, a complete function signature, ABI/calling-convention requirements,
  provenance/lifetime constraints, diagnostics, and dedicated tests; otherwise
  the SPECs state that no such operation is currently supported.
- [ ] Semantic analysis and every lowering/codegen fallback use the same typed
  callable predicate; no exact-`ptr` exception remains.
- [ ] Assignment to and invocation of callable fields validate parameter count,
  parameter types, result type, and supported ABI metadata without falling back
  to integer or opaque-pointer behavior.
- [ ] Registered positive tests cover typed callable assignment, runtime
  replacement, explicit argument passing, and indirect invocation.
- [ ] Registered negative tests cover raw `ptr` invocation, wrong arity, wrong
  argument types, incompatible assignment, and artifact suppression on error.
- [ ] English/Vietnamese parity, supported native targets, O0-O3 behavior, and
  self-host/bootstrap convergence are recorded in a VPS REPORT before closure.

## 12. Related Papers

### Issues

- VIR-ISS-0002 — broader canonical typed identity, callable metadata, and
  fail-closed compatibility work; no formal reciprocal link has yet been added.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Resolved the normative VIR portion in v2.1 around typed callable values and non-callable raw `ptr`; retained TRIAGED status for deferred VIRC implementation and verification |
| 2026-10-04 | Created and triaged from the active SPEC mismatch, exact TaskRunner reproduction, strict fixtures, and semantic/lowering source audit |
