---
id: "VIRC-ISS-0064"
type: "ISSUE"
domain: "VIRC"
title: "Generic receiver UFCS does not resolve or specialize for generic entities"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "semantic-analysis"
  - "type-checker"
  - "generics"
  - "ufcs"
  - "method-resolution"
  - "monomorphization"
  - "ast-to-mir"
  - "self-hosting"
related:
  issues:
    - "STLB-ISS-0032"
    - "VIRC-ISS-0065"
  plans:
    - "VIRC-PLN-0035"
  reports:
    - "VIRC-RPT-0052"
supersedes: null
superseded_by: null
tags:
  - "generic-ufcs"
  - "generic-entities"
  - "receiver-resolution"
  - "monomorphization"
  - "self-hosted-compiler"
---

# VIRC-ISS-0064 — Generic receiver UFCS does not resolve or specialize for generic entities

## 1. Summary

The self-hosted compiler does not resolve receiver calls whose receiver is an
instantiated generic entity. Calls such as `box.read()` on `Box of (int)` fail
semantic analysis with `E3021`, before AST-to-MIR can select and emit the
correct specialization.

Implementation must resolve entity methods and generic free-function UFCS from
the receiver's fully instantiated type, preserve one canonical callable
identity, and propagate the inferred concrete type arguments into
monomorphization. The fix must be generic compiler infrastructure, not a Vec
special case.

## 2. Context

The compiler already supports non-generic receiver UFCS and already contains a
monomorphization path for ordinary generic `AstType.Call` nodes. The missing
bridge is between method-call receiver resolution and generic substitution:
the receiver's base entity can be found, but its concrete generic arguments do
not produce a resolvable, specialized callable identity throughout semantic
analysis and lowering.

Vec is the first standard-library consumer blocked by this gap. The same defect
applies to every generic entity and every generic free function whose first
parameter is matched through UFCS.

## 3. Expected Behavior

- A value of type `Box of (int)` resolves `box.read()` to the `Box of (T)`
  method with `T = int`.
- A generic free function whose first parameter accepts `Vec of (T)` resolves
  `values.operation(...)` and infers `T` from the receiver.
- Existing resolution priority remains deterministic: entity method, then
  callable field, then visible free-function UFCS.
- Lookup observes canonical module identity, imports, and visibility.
- The resolved call carries the canonical method or free-function identity and
  the concrete generic arguments required by the monomorphizer.
- Receiver insertion preserves declared `ref`/`out`/move and ownership
  semantics.
- Resolution never erases an instantiated receiver to an unparameterized base
  entity and never relies on string matching or API-specific compiler branches.

## 4. Actual Behavior

- A receiver call on an instantiated generic entity fails with `E3021`.
- Entity-method lookup is driven by the base entity AST/name without completing
  generic substitution for the receiver and selected callable.
- AST-to-MIR can specialize an ordinary generic call from its explicit generic
  call metadata, but an unresolved generic `MethodCall` never reaches that path
  with an equivalent canonical identity and type-argument set.
- Consequently, generic Vec receiver syntax cannot expose its canonical UFCS
  API even when the underlying free functions exist.

## 5. Reproduction

```vir
entity Box of (T):
    value: T

    method read() -> T:
        out this.value
    end.
end.

func main:
    var box = Box of (int)(value: 42)
    print(box.read())
    out 0
end.
```

Run:

```sh
./bin/virc /private/tmp/vir_generic_receiver_ufcs_probe.vri --check --json
```

Observed on 2026-10-09: semantic analysis rejects `box.read()` with `E3021`
instead of resolving `read` with `T = int`.

## 6. Evidence

- **OBSERVED:** the focused `Box of (T)` fixture fails at `box.read()` with
  `E3021`.
- **CONFIRMED:**
  `compiler/src/semantic/typecheck/walk_method.vri` obtains a receiver entity
  name and attempts entity-method/callable-field/free-UFCS lookup, but the path
  does not establish a specialized callable identity from the receiver's
  concrete generic arguments.
- **CONFIRMED:**
  `compiler/src/semantic/typecheck/methods.vri` performs entity and method lookup
  primarily by entity/method name; it does not complete instantiation-aware
  substitution for generic receiver method resolution.
- **CONFIRMED:**
  `compiler/src/lower/ast_to_mir/calls.vri` normalizes resolved method/UFCS
  calls, but cannot repair an unresolved semantic method call.
- **CONFIRMED:**
  `compiler/src/lower/ast_to_mir/func.vri` can build specialized function names
  for ordinary generic calls when their generic arguments are present.
- **CONFIRMED:** strict UFCS coverage exists under `tests/strict_v2`, but it
  does not close this generic-receiver case.

## 7. Scope

### Affected

- instantiated generic receiver identity and type substitution;
- generic entity-method lookup;
- generic free-function UFCS lookup and type-argument inference from receiver;
- callable-field and free-UFCS fallback ordering around generic entities;
- canonical callable identity across AST, semantic facts, HIR/MIR, and
  monomorphization;
- receiver ownership/borrow mode and module visibility;
- diagnostics, strict fixtures, generated compiler bundle, and self-hosting.

### Not affected

- type-receiver constructor lowering remains separately tracked by
  `STLB-ISS-0032` and requires its own VIRC issue if implementation is opened;
- default arguments belong to `VIRC-ISS-0062`;
- typed operation selectors belong to `VIRC-ISS-0063`;
- three-level method groups are not authorized by the Vec API decision;
- Vec storage, growth, indexing, and removal algorithms are not part of this
  compiler issue.

## 8. Impact

Generic collections and user-defined generic entities cannot expose idiomatic
receiver APIs reliably. The failure blocks the approved Vec UFCS surface and
would force libraries to retain free-function-only spellings or add
type-specific compiler workarounds.

## 9. Preliminary Analysis

- **CONFIRMED:** failure occurs in semantic call resolution before backend
  lowering.
- **CONFIRMED:** generic ordinary-call specialization infrastructure exists,
  so the missing work is not a new backend ABI but a complete generic call
  identity from receiver resolution through lowering.
- **HYPOTHESIS:** method resolution should retain the receiver's full type
  application, derive a substitution environment, check the selected callable
  under that environment, and attach the resulting concrete generic arguments
  to the normalized call.
- **NOT_VERIFIED:** whether the current semantic fact representation can store
  the complete substitution without a new call-resolution record.

## 10. Acceptance Criteria

- [x] Preserve the receiver's complete generic type application during lookup;
  do not reduce `Entity of (Args...)` to an unparameterized entity identity.
- [x] Resolve generic entity methods with deterministic substitution of entity
  and method generic parameters.
- [x] Resolve visible generic free-function UFCS by inferring compatible type
  arguments from the receiver and remaining explicit arguments.
- [x] Preserve resolution priority among entity methods, callable fields, and
  free-function UFCS independent of declaration order.
- [x] Attach one canonical callable identity and complete concrete generic
  arguments for AST-to-MIR monomorphization.
- [x] Preserve receiver `ref`/`out`/move, mutability, lifetime, and ownership
  checks through normalization.
- [x] Emit stable diagnostics for no match, incompatible receiver, failed
  inference, inaccessible candidate, ambiguity, and specialization failure.
- [x] Add positive and negative strict fixtures for multiple instantiations,
  nested generics, receiver mismatch, module visibility, ambiguity, declaration
  order, and entity-method/callable-field/free-UFCS priority.
- [x] Compile the canonical one-level Vec receiver calls after the registered
  `collections.vec` module passes its independent checks (Proven in
  `tests/strict_v2/generic_receiver_vec_model_e2e.vri`; `collections.vec`
  clean compilation resolved with 0 diagnostics under `STLB-ISS-0007` / `STLB-RPT-0001`;
  consumer fixture `tests/strict_v2/collections_vec_consumer_e2e.vri` passing in Group 3).
- [x] Add no Vec-, Box-, method-name-, or source-spelling-specific branch.
- [x] Synchronize modular compiler sources with
  `stdlib/vir/compiler/virc.vri`, rebuild successive self-host stages, and prove
  the repository's stage-2/stage-3 fixed point.
- [x] Add an approved PLAN and an ACCEPTED verification REPORT before closure
  (`VIRC-PLN-0035` COMPLETED, `VIRC-RPT-0052` ACCEPTED with conclusion `READY_FOR_CLOSE`).

## 11. Related Papers

### Issues

- `STLB-ISS-0032` — Vec consumer issue and separate type-receiver constructor
  lowering gap.
- `VIRC-ISS-0065` — Include text splicing and module namespaces.

### Plans

- `VIRC-PLN-0035` — Resolve and specialize generic receiver UFCS.

### Reports

- `VIRC-RPT-0052` — Generic receiver UFCS resolution and monomorphization verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from the generic receiver failure isolated in STLB-ISS-0032 |
| 2026-10-09 | Linked VIRC-PLN-0035 |
| 2026-10-09 | Linked VIRC-ISS-0065 |
| 2026-10-09 | Linked VIRC-RPT-0052 |
| 2026-10-09 | Resolved and closed with verified fixed point and passing strict test suite |
| 2026-10-09 | Reopened following audit: multi-argument generic inference and missing acceptance test coverage |
| 2026-10-09 | Resolved multi-argument generic inference across receiver and all arguments, verified comprehensive strict test matrix (58/58 PASS), updated fixed-point metrics (18,435,343 bytes, SHA-256 04b52a18...), and closed |
| 2026-10-09 | Reopened following audit: method generic parameter specialization, pass 8 move invalidation, generic template monomorphization isolation, extended strict fixtures, and tracked dependency on STLB-ISS-0007 |
| 2026-10-09 | Corrected the ambiguity test to use two visible imported providers, implemented deterministic E3052 ambiguity rejection, added exact diagnostic-line oracles, and reconciled the report/closure acceptance state |
| 2026-10-09 | Closed after STLB-ISS-0007 closure satisfied Vec module acceptance criterion, VIRC-RPT-0052 accepted with conclusion READY_FOR_CLOSE, and fixed point verified |
