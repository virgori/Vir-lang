---
id: "STLB-ISS-0001"
type: "ISSUE"
domain: "STLB"
title: "The public math tensor module fails semantic and ownership checks"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-03"
owners: [stdlib]
components: [math-tensor, module-registry, typecheck, ownership, public-api, tests]
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: [stdlib, tensor, ownership, move, compile-failure, public-api]
---

# STLB-ISS-0001 — The public math tensor module fails semantic and ownership checks

## 1. Summary

The registered public standard-library module `math.tensor` does not pass the
current compiler's semantic and ownership checks. A direct check reports 220
errors, so callers cannot treat the dense tensor library surface as a usable,
release-qualified stdlib module even though lower-level language tensor
intrinsics and the separate `math.tensor_q8_0` module exist.

## 2. Context

`stdlib/stdlib.vri` registers `math.tensor = math/tensor.vri` as a public module.
The Vir stdlib contract requires registered modules and exported symbols to be
validated with the active compiler and representative callers. The audit was
performed against the current dirty working tree and current `./bin/virc`
without modifying owner source.

## 3. Expected Behavior

- `math.tensor` compiles cleanly under the active compiler and its public
  exports resolve through the canonical stdlib registry.
- Public APIs obey current Vir ownership, move, borrow, type, and error rules.
- Dense tensor construction, views, indexing, reductions, matmul, and external
  storage operations have focused positive and negative module-level tests.
- Callers do not need private compiler intrinsics or raw memory access to use
  the documented library API.

## 4. Actual Behavior

- `./bin/virc stdlib/vir/math/tensor.vri --check --json -q` exits nonzero with
  `error_count: 220`.
- Diagnostics are dominated by `E5001` move-after-move findings and also
  include `E3007` type mismatches.
- The separately registered `math.tensor_q8_0` module passes the same semantic
  check with zero diagnostics, so the failure is scoped to the dense module.
- Existing low-level tensor operator fixtures do not establish that users can
  import and call the public `math.tensor` API.

## 5. Reproduction

```sh
rg -n '^math\.tensor' stdlib/stdlib.vri

./bin/virc stdlib/vir/math/tensor.vri --check --json -q
./bin/virc stdlib/vir/math/tensor_q8_0.vri --check --json -q

rg -n '^export ' stdlib/vir/math/tensor.vri
```

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri:245` maps `math.tensor` to
  `math/tensor.vri`; line 246 maps the separate Q8_0 module.
- CONFIRMED: the dense module check reported 220 errors on 2026-10-03.
- OBSERVED: serialized diagnostics contain 208 `E5001` occurrences and 13
  `E3007` occurrences; occurrence totals may include duplicated diagnostic
  serialization and are not substituted for the compiler's `error_count`.
- CONFIRMED: `math.tensor_q8_0` reported success with `error_count: 0`.
- NOT_VERIFIED: which dense public functions are reachable after the earliest
  failures, whether all errors have independent root causes, and compatibility
  with previously built compiler stages.

## 7. Scope

### Affected

- public `math.tensor` exports and their module-level callers;
- ownership and type-correctness of dense tensor data/view operations;
- public error and lifetime contracts for external storage;
- stdlib registration and release verification for the module.

### Not affected / Unknown

- compiler-native `tensor[T; S...]` syntax and operator lowering;
- the separately compiling `math.tensor_q8_0` module;
- new language syntax or semantic changes;
- performance optimization until the public module is correct and buildable.

## 8. Impact

A canonical public stdlib module is unusable under the current compiler, which
blocks library consumers and invalidates any release claim that relies on its
API. Because the module is broadly broken rather than one optional function,
the issue is S1/P0.

## 9. Preliminary Analysis

- CONFIRMED: the module registry entry exists and the mapped source fails
  semantic checking.
- CONFIRMED: the failure includes ownership and type diagnostics.
- HYPOTHESIS: groups of `E5001` errors may share a small number of API ownership
  design mismatches and should be clustered before mechanical edits.
- NOT_VERIFIED: whether the desired API should preserve every current export or
  deprecate unsafe/redundant surfaces under an approved compatibility plan.

## 10. Acceptance Criteria

- [ ] Every public export is inventoried with signature, ownership, lifetime,
  error behavior, and at least one intended caller.
- [ ] `math.tensor` passes `--check` with zero errors using a newly built active
  compiler; fixes do not suppress legitimate move or type diagnostics.
- [ ] Focused executable tests cover construction, indexing, views, reductions,
  dense matmul, external storage bounds/lifetime, and failure paths.
- [ ] Module identity and exports resolve through `stdlib/stdlib.vri` from a
  consumer outside the module's source directory.
- [ ] Ownership tests include moved values, shared/mutable borrows, escaping
  views, and invalid use after owner/storage lifetime ends.
- [ ] Existing Q8_0 and compiler-native tensor contracts remain green.
- [ ] Supported targets and optimization levels are tested or explicitly
  reported as unsupported; compilation alone is not closure evidence.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None yet.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged after direct semantic check of the registered public module |
