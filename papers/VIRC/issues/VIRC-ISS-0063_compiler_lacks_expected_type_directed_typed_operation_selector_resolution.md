---
id: "VIRC-ISS-0063"
type: "ISSUE"
domain: "VIRC"
title: "Compiler lacks expected type directed typed operation selector resolution"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "frontend-parser"
  - "semantic-analysis"
  - "name-resolution"
  - "type-checker"
  - "call-resolution"
  - "ufcs"
  - "ast-to-mir"
  - "diagnostics"
  - "self-hosting"
related:
  issues:
    - "VIR-ISS-0016"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "typed-selectors"
  - "contextual-resolution"
  - "name-resolution"
  - "ufcs"
  - "self-hosted-compiler"
---

# VIRC-ISS-0063 — Compiler lacks expected type directed typed operation selector resolution

## 1. Summary

The self-hosted compiler has no representation or resolver path for the typed
operation selectors locked by `VIR-ISS-0016`. A bare argument such as `swap` is
handled only as an ordinary identifier and fails with `E2001` when no lexical
binding exists. The compiler cannot use the resolved callee's expected
parameter type to find an explicitly declared selector member.

Implementation must add contextual typed lookup without reserving selector
spellings globally, importing implicit constants, adding overload resolution,
or special-casing a library.

## 2. Context

`VIR-ISS-0016` locks the resolution order:

1. resolve the callee and parameter list;
2. obtain the expected selector type for the argument position;
3. preserve ordinary lexical identifier lookup and shadowing;
4. only when ordinary lookup has no binding, find an explicitly declared
   selector member in the expected selector type;
5. require exactly one visible match and lower it as a typed value.

Vec no longer consumes typed selectors: its canonical API now uses separate
`remove` and `swapRemove` methods. The same selector spelling must nevertheless
remain available for ordinary variables, fields, methods, and selectors
belonging to other types.

## 3. Expected Behavior

- Selector members are created only by the SPEC-approved explicit declaration
  form and carry a nominal typed identity and visibility.
- Parser keeps selector spellings identifier-shaped; it does not add `swap`,
  `preserve`, or user-defined selectors to the keyword set.
- Call resolution determines a unique callee and expected parameter type before
  contextual selector lookup.
- A visible ordinary lexical binding keeps normal identifier semantics and
  shadows selector fallback lookup.
- With no ordinary binding, one visible selector member of the expected type
  resolves successfully; zero or multiple matches fail deterministically.
- The resolved AST/HIR/MIR node carries a typed selector value, not a string,
  magic integer, function overload discriminator, or library-specific flag.
- Module/import boundaries and a SPEC-approved qualified escape form provide
  deterministic visibility and disambiguation.

## 4. Actual Behavior

- Bare `swap` enters ordinary identifier lookup only.
- No selector type/member registry exists in the inspected semantic resolver.
- Expected call-argument types are used for compatibility checking after
  argument expressions have already been resolved; they do not drive fallback
  name resolution.
- Existing enum resolution supports qualified enum identities and constructors
  but does not implement bare expected-type-directed selector lookup.
- No dedicated diagnostics distinguish missing expected type, unknown selector,
  ambiguous selector, or lexical shadowing from an ordinary undefined variable.

## 5. Reproduction

Current ordinary-name behavior can be observed with:

```vir
func removeMode(index: int, operation: int):
    print(index + operation)
end.

removeMode(0, swap)
```

Run:

```sh
./bin/virc /private/tmp/vir_typed_selector_probe.vri --check --json
```

Observed on 2026-10-09: compilation fails with `E2001`, `Undefined variable in
current scope`, at `swap`.

The final positive fixture must use the selector declaration/type syntax
approved by `VIR-ISS-0016`, not the temporary `int` parameter above.

## 6. Evidence

- **OBSERVED:** the focused bare-identifier fixture fails with one `E2001` at
  line 5, column 15.
- **CONFIRMED:** `compiler/src/frontend/parser/ast.vri` has identifier, enum
  access, and enum-construction nodes but no typed-selector node or invariant.
- **CONFIRMED:** `compiler/src/semantic/typecheck/walk_stmt.vri` and
  `compiler/src/semantic/typecheck/walk_method.vri` infer/check argument types
  against resolved parameters but expose no expected-type selector fallback.
- **CONFIRMED:** `compiler/src/semantic/typecheck/enums.vri` performs enum AST
  lookup and constructor validation; it does not resolve unqualified members
  from a call parameter's expected type.
- **CONFIRMED:** active parser/semantic keyword and name-resolution paths do not
  reserve or recognize `swap` as a global language word.
- **NOT_VERIFIED:** final selector declaration and qualification syntax and
  runtime/ABI representation. VIRC must follow the approved VIR revision rather
  than choose these language-level details itself.

## 7. Scope

### Affected

- selector declaration representation and symbol registration;
- lexical, module, visibility, and expected-type name resolution;
- ordinary/method/callable-field/free-UFCS argument checking;
- generic substitution and delayed expected types;
- AST/HIR/MIR typed-value lowering and constant representation;
- ambiguity/shadowing/source-span diagnostics and IDE facts;
- generated compiler bundle, strict fixtures, and self-hosting.

### Not affected / Unknown

- selector spellings must not enter the global keyword set;
- general function overloading is out of scope;
- default-argument parsing/lowering belongs to `VIRC-ISS-0062`;
- enum behavior may provide reusable infrastructure, but typed selectors must
  not silently change existing enum lookup semantics;
- serialization, pattern matching, FFI, and runtime representation remain
  gated by the normative VIR contract.

## 8. Impact

Without contextual typed lookup, APIs that choose selector-style operations
must expose additional names, use qualified enum values, booleans/magic
integers, or rely on global constants. The compiler must implement the locked
language decision without assuming any one stdlib consumer.

## 9. Preliminary Analysis

- **CONFIRMED:** current failure is ordinary undefined-name resolution, not a
  missing backend intrinsic.
- **CONFIRMED:** expected parameter types already exist during call type
  checking, but resolution order must be restructured so they can guide a
  controlled fallback without overriding lexical bindings.
- **HYPOTHESIS:** a nominal selector-member registry parallel to scoped enum
  metadata can reuse visibility/type identity infrastructure while keeping
  lookup semantics separate.
- **NOT_VERIFIED:** interaction with unresolved generic expected types and the
  exact point where selector values should be materialized in HIR/MIR.

## 10. Acceptance Criteria

- [ ] Implement only selector declaration, qualification, and representation
  forms approved by `VIR-ISS-0016`; VIRC must not invent syntax.
- [ ] Keep selector spellings out of global keyword/implicit-global tables.
- [ ] Register selector members with nominal type identity, module provenance,
  visibility, source span, and deterministic duplicate diagnostics.
- [ ] Resolve callee and expected parameter type before selector fallback;
  preserve ordinary lexical binding semantics and shadowing.
- [ ] Emit stable diagnostics for missing expected type, unknown member,
  inaccessible member, ambiguous member, and incompatible ordinary binding.
- [ ] Support ordinary, method, callable-field, generic, and free-function UFCS
  calls without adding overload resolution or library-specific branches.
- [ ] Lower selectors as typed values through AST/HIR/MIR and every supported
  backend; no string matching or magic call-site flag may survive lowering.
- [ ] Add positive/negative fixtures for same-spelling members across selector
  types, lexical shadowing, module visibility, qualification, absent/ambiguous
  expected types, generics, UFCS, and ordinary fields/methods named `swap`.
- [ ] Integrate tests into the registered runner across supported optimization
  levels and relevant native/Wasm targets.
- [ ] Synchronize modular compiler sources with
  `stdlib/vir/compiler/virc.vri`, rebuild successive self-host stages, and prove
  the repository's stage-2/stage-3 fixed point.
- [ ] Add an approved PLAN and an ACCEPTED verification REPORT before closure.

## 11. Related Papers

### Issues

- `VIR-ISS-0016` — locked contextual typed-selector language contract.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from the locked VIR typed-selector contract and focused compiler reproduction |
| 2026-10-09 | Vec dependency withdrawn; issue retained as an independent language feature |
