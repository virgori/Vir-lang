---
id: "VIRC-ISS-0062"
type: "ISSUE"
domain: "VIRC"
title: "Compiler does not parse type check or lower explicit trailing default arguments"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "frontend-parser"
  - "ast"
  - "symbols"
  - "type-checker"
  - "call-resolution"
  - "ufcs"
  - "ast-to-mir"
  - "self-hosting"
related:
  issues:
    - "VIR-ISS-0015"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "default-arguments"
  - "functions"
  - "call-lowering"
  - "ufcs"
  - "self-hosted-compiler"
---

# VIRC-ISS-0062 — Compiler does not parse type check or lower explicit trailing default arguments

## 1. Summary

The self-hosted compiler cannot implement the explicit-declaration-only default
argument contract locked by `VIR-ISS-0015`. It rejects `= expression` in a
parameter list, stores no default expression on parameter AST nodes, records a
single exact `param_count`, and rejects calls whose supplied argument count is
not exactly that count.

The implementation must support omitted trailing arguments without introducing
function overloading or synthesizing defaults from parameter types.

## 2. Context

`VIR-ISS-0015` locks these semantic boundaries:

- a parameter has a default argument only when its declaration contains an
  explicit `= expression`;
- a parameter without that expression is required regardless of type;
- defaults are not derived from `int`, `bool`, pointer, string, entity, generic
  type, or any `Default` trait;
- omitted trailing arguments lower to one resolved callable's full argument
  list; they do not create another function identity.

Vec no longer consumes this feature: its canonical API now uses separate
`remove(index)` and `swapRemove(index)` methods. This compiler issue remains an
independent implementation of the language contract.

## 3. Expected Behavior

- Parser accepts the SPEC-approved explicit default-expression syntax on
  trailing parameters only.
- AST preserves each default expression and its source span on the owning
  parameter node.
- Declaration checking rejects a required parameter after a defaulted one and
  checks every default expression against the declared parameter type.
- Callee resolution determines the declaration before omitted arguments are
  materialized.
- A call may supply any arity from required-parameter count through full
  parameter count; all other arities fail with a stable diagnostic.
- Ordinary calls and UFCS calls normalize to the same full call. UFCS receiver
  insertion and default filling must not be counted twice or reordered.
- Explicit arguments override defaults. Defaults are never synthesized from a
  type and never trigger overload resolution.
- HIR/MIR/backend ABI sees one full-arity callable identity.

## 4. Actual Behavior

- `parse_func_def_mode` parses a parameter name and optional type annotation,
  then expects a separator or `)`; it does not consume an assignment token and
  default expression.
- `AstType.ParamDef` has no implemented default-expression contract.
- symbol registration records one exact `param_count`.
- semantic call checking reports `E3004` whenever supplied argument count does
  not exactly equal `param_count`.
- AST-to-MIR call lowering only receives arguments written at the call site and
  has no normalization step that clones/resolves declaration defaults.

## 5. Reproduction

```vir
func retry(count: int = 3):
    print(count)
end.

retry()
```

Run:

```sh
./bin/virc /private/tmp/vir_default_argument_probe.vri --check --json
```

Observed on 2026-10-09: compilation fails with `E1001`,
`expected ')' after parameters, found '='`, at the default expression marker.

After parser support, the following cases must also be tested:

```vir
func example(a: int, b: int = 10):
    # ...
end.

example(5)
example(5, 20)
example()  # missing required a
```

## 6. Evidence

- **OBSERVED:** the focused fixture fails with one `E1001` at line 1, column
  23 before semantic analysis.
- **CONFIRMED:**
  `compiler/src/frontend/parser/stmt_decl/func_def.vri` creates
  `AstType.ParamDef`/`RefParam` after parsing name and type but contains no
  parameter-default parse path.
- **CONFIRMED:**
  `compiler/src/frontend/parser/stmt_decl/type_expr.vri` stops a type expression
  at `TokType.Assign`, leaving the token for a caller that currently does not
  consume it.
- **CONFIRMED:** `compiler/src/frontend/parser/ast.vri` defines parameter node
  kinds but no implemented default-expression invariant.
- **CONFIRMED:** `compiler/src/semantic/typecheck/walk_stmt.vri` performs exact
  equality between `sym.param_count` and supplied `arg_count`, reporting
  `E3004` on mismatch.
- **CONFIRMED:** the active call/type paths enumerate parameter nodes in
  `compiler/src/semantic/typecheck/walk_stmt.vri`,
  `compiler/src/semantic/typecheck/walk_method.vri`, and
  `compiler/src/lower/ast_to_mir/calls.vri`; all require coordinated handling
  rather than a parser-only patch.
- **NOT_VERIFIED:** final SPEC decisions for default-expression lexical scope,
  evaluation order, function values, extern/FFI declarations, and parameter
  group syntax. Implementation must follow the approved VIR contract rather
  than decide these points in VIRC.

## 7. Scope

### Affected

- parameter parsing and AST cloning/specialization;
- symbol arity metadata and callable identity;
- default-expression type, ownership, effect, and error-flow checking;
- ordinary, method, callable-field, and free-function UFCS call resolution;
- AST-to-HIR/MIR call normalization;
- diagnostics, IDE/source spans, generated compiler bundle, and self-hosting;
- strict positive/negative conformance fixtures.

### Not affected / Unknown

- general function overloading is explicitly out of scope;
- automatic default values for types and a `Default` trait are out of scope;
- typed operation-selector resolution is a separate feature;
- backend calling conventions should remain full-arity after frontend
  normalization, but cross-target parity still requires verification.

## 8. Impact

Without this implementation, APIs cannot omit declared trailing arguments.
Adding overload-by-arity as a substitute would violate the locked language
decision and expand ambiguity beyond the requested feature.

## 9. Preliminary Analysis

- **CONFIRMED:** the first failure is parser-level, before type checking.
- **CONFIRMED:** exact arity is duplicated across symbol/typecheck/call-lowering
  paths, so changing only `param_count` would be incomplete.
- **HYPOTHESIS:** call normalization after callee resolution but before final
  borrow/effect checking and MIR emission provides one consistent full-arity
  boundary.
- **NOT_VERIFIED:** whether the existing generic AST clone path can safely copy
  default expressions without new ownership/source-span handling.

## 10. Acceptance Criteria

- [ ] Implement only the declaration forms and evaluation rules approved by
  `VIR-ISS-0015`; VIRC must not invent missing language semantics.
- [ ] Preserve explicit default expressions and source spans in modular AST and
  every clone/specialization path.
- [ ] Reject non-trailing defaults, required parameters after defaults, and
  default-expression type/ownership/effect failures with stable diagnostics.
- [ ] Represent required and full arity without creating overload sets or a
  second callable identity.
- [ ] Normalize ordinary, method, callable-field, generic, and UFCS calls once,
  with correct receiver and left-to-right argument evaluation.
- [ ] Prove that explicit arguments override defaults and missing required
  arguments fail; prove no primitive/pointer/entity/generic default is inferred.
- [ ] Keep extern/FFI/function-value behavior fail-closed unless explicitly
  authorized by the normative contract.
- [ ] Add focused strict fixtures for positive calls, arity boundaries,
  non-trailing declarations, type mismatch, side effects, ownership/error flow,
  generics, UFCS, and diagnostic source spans.
- [ ] Integrate the fixtures into the registered test runner and exercise all
  supported optimization levels and relevant native/Wasm targets.
- [ ] Synchronize modular compiler sources with
  `stdlib/vir/compiler/virc.vri`, rebuild successive self-host stages, and prove
  the repository's stage-2/stage-3 fixed point.
- [ ] Add an approved PLAN and an ACCEPTED verification REPORT before closure.

## 11. Related Papers

### Issues

- `VIR-ISS-0015` — locked language contract for explicit trailing defaults.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from the locked VIR default-argument contract and focused compiler reproduction |
| 2026-10-09 | Vec dependency withdrawn; issue retained as an independent language feature |
