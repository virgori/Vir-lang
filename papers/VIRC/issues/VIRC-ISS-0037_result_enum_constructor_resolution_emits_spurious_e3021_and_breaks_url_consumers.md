---
id: "VIRC-ISS-0037"
type: "ISSUE"
domain: "VIRC"
title: "Result enum constructor resolution emits spurious E3021 and breaks URL consumers"
status: "CLOSED"
severity: "S1"
priority: "P1"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "semantic"
  - "name-resolution"
  - "typecheck"
  - "enum"
  - "stdlib-result"
  - "stdlib-url"
  - "strict-v2"
related:
  issues:
    - "VIRC-ISS-0038"
  plans:
    - "VIRC-PLN-0024"
  reports:
    - "VIRC-RPT-0041"
supersedes: null
superseded_by: null
tags:
  - "enum-constructor"
  - "false-positive"
  - "e3021"
  - "result"
  - "url"
  - "regression"
---

# VIRC-ISS-0037 — Result enum constructor resolution emits spurious E3021 and breaks URL consumers

## 1. Summary

The self-hosted compiler emits a false `E3021` UFCS error while checking the
valid `Result.Err(e)` constructor in `stdlib/vir/core/result.vri::try_all`.
The same diagnostic prevents the public `url` module, its own smoke and matrix
tests, and Group 11's positive URL fixture from compiling.

## 2. Context

Vir resolves `Enum.Variant(args...)` before ordinary method/callable-field/UFCS
resolution. The active language specification defines that qualified enum
constructor form, and `compiler/src/semantic/names/walk_expr.vri` contains the
rewrite from the parser's initial `MethodCall` node to `EnumConstruct`.

The audit was run on 2026-10-05 at Git HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` with a dirty working tree owned by
concurrent work. The tested `bin/virc` identified itself as self-hosted 4.2.1
and had SHA-256
`8f6c8f234d81f37235be5a21d5d7bbe970c61bbd456a85ce761560b7bdc49835`.

## 3. Expected Behavior

- Every valid `Result.Ok(...)` and `Result.Err(...)` expression is resolved as
  an enum constructor, including inside nested `for`, `case`, and `out` forms.
- `stdlib/vir/core/result.vri` passes semantic checking.
- Public `url` consumers and the registered URL smoke/matrix fixtures compile
  without a UFCS diagnostic originating in `result.vri`.
- Genuine unresolved method/UFCS calls continue to fail with `E3021`.

## 4. Actual Behavior

- Checking `stdlib/vir/core/result.vri` fails with `E3021` at reported location
  `stdlib/vir/core/result.vri:147:39-42`.
- Line 147 contains `Result.Err(e): out Result.Err(e)` inside
  `try_all`; `Err` is declared as a variant of `Result` at line 22.
- Checking `stdlib/vir/test/url_ns_smoke.vri`,
  `stdlib/vir/test/url_matrix_vtest.vri`, and
  `tests/strict_v2/ufcs_url_parse_positive_e2e.vri` fails with the same primary
  diagnostic and location.
- The Group 11 runner therefore records the positive URL case as
  `FAIL-COMPILE` before its runtime oracle can execute.

## 5. Reproduction

From the repository root:

```sh
bin/virc --version
shasum -a 256 bin/virc

bin/virc stdlib/vir/core/result.vri --check --json
bin/virc stdlib/vir/test/url_ns_smoke.vri --check --json
bin/virc stdlib/vir/test/url_matrix_vtest.vri --check --json
bin/virc tests/strict_v2/ufcs_url_parse_positive_e2e.vri --check --json

./run_tests.sh 11
```

## 6. Evidence

- CONFIRMED: each of the four focused compiler commands above returned failure
  with primary code `E3021`, message `Unresolved UFCS member`, and the same
  reported `result.vri:147:39-42` span.
- CONFIRMED: `result.vri` declares `enum Result` with `Ok` and `Err` variants;
  multiple earlier qualified `Result.Err(...)` occurrences do not themselves
  receive the reported diagnostic before the occurrence in `try_all`.
- CONFIRMED: the active English and Vietnamese language specifications define
  qualified enum construction and separately reserve dot-call UFCS fallback
  for calls not resolved as methods, callable fields, or free functions.
- CONFIRMED: Group 11 produced 37/42 PASS; one of its five failures is the
  positive URL fixture blocked by this diagnostic.
- OBSERVED: `walk_expr.vri` rewrites enum constructor candidates before UFCS,
  while `walk_method.vri` emits `E3021` only after method, callable-field,
  free-function, and module-qualified resolution fail.
- NOT_VERIFIED: the exact AST corruption or rewrite condition that leaves this
  occurrence on the UFCS path, and whether all nested enum-constructor shapes
  are affected.

## 7. Scope

### Affected

- enum-constructor name resolution and the pass-3-to-pass-6 AST contract;
- public `result` and legacy/public `url` module consumers;
- stdlib URL smoke/matrix tests and the Group 11 positive URL fixture;
- any module that preprocesses the failing `result.try_all` body.

### Not affected / Unknown

- The issue does not claim that genuine unresolved UFCS calls are accepted.
- Runtime URL parsing correctness is unknown because compilation stops first.
- Diagnostic source-span drift in the three negative Group 11 fixtures is
  independent and tracked separately.

## 8. Impact

This is a core semantic false positive in a foundational stdlib module. It
prevents otherwise valid URL programs and registered stdlib tests from
compiling, contaminates unrelated negative-test diagnostic ordering, and can
block any consumer that includes the same Result implementation. The behavior
is therefore classified S1/P1 rather than test-only debt.

## 9. Preliminary Analysis

- CONFIRMED: the diagnostic is emitted on the compiler's unresolved
  method/UFCS path even though the source expression names an existing enum and
  variant.
- CONFIRMED: changing the Group 11 URL oracle cannot make the public stdlib
  smoke and matrix programs compile, so this is not a stale-test failure.
- HYPOTHESIS: enum-constructor rewriting loses or fails to recognize the nested
  `out Result.Err(e)` node under the final `case` arm of a `for` loop.
- HYPOTHESIS: the same AST preservation workaround that keeps the parser's
  synthetic receiver child may interact with nested traversal or symbol state.
- NOT_VERIFIED: whether the defect originates in pass 3 traversal, AST
  mutation, symbol lookup, source preprocessing, or a later pass consuming a
  partially rewritten node.

## 10. Acceptance Criteria

- [x] `bin/virc stdlib/vir/core/result.vri --check --json` succeeds with zero
  errors.
- [x] A focused regression containing qualified `Ok`/`Err` constructors inside
  nested `for` + `case` + `out` paths proves every constructor reaches
  `EnumConstruct` semantics and no false `E3021` is emitted.
- [x] `url_ns_smoke.vri`, `url_matrix_vtest.vri`, and
  `ufcs_url_parse_positive_e2e.vri` compile and pass their runtime oracles.
- [x] Existing unresolved method/UFCS negative fixtures still emit `E3021`.
- [x] Group 11 has no failure attributable to the `result.vri:147` diagnostic;
  independent issues are reported separately rather than hidden.
- [x] Canonical compiler sources and `compiler/generated/virc.vri` are
  synchronized through the approved generator, and consecutive self-hosted
  generations reach a fixed point.
- [x] A VPS PLAN and accepted REPORT provide focused and regression evidence
  before closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0038 — include-expanded UFCS diagnostics report shifted source
  spans independently of this false primary diagnostic.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created and triaged from direct Result/URL semantic checks and Group 11 reproduction |
| 2026-10-05 | Linked the independent source-span defect VIRC-ISS-0038 |
| 2026-10-05 | Linked VIRC-ISS-0038 |
| 2026-10-05 | Linked VIRC-PLN-0024 and entered implementation after a minimal direct/when/for differential isolated the loop-scope failure |
| 2026-10-05 | Linked VIRC-PLN-0024 |
| 2026-10-05 | Linked VIRC-RPT-0041 |
| 2026-10-05 | Closed after accepted VIRC-RPT-0041: Result/URL pass, Group 11 is 44/44, generated source is synchronized, and self-host stages are byte-identical |
