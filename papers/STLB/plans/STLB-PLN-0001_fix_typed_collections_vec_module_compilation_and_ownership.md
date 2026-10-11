---
id: "STLB-PLN-0001"
type: "PLAN"
domain: "STLB"
title: "Fix typed collections Vec module compilation and ownership"
status: "COMPLETED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "collections"
  - "vec"
  - "generics"
  - "module-identity"
  - "ownership"
related:
  issues:
    - "STLB-ISS-0007"
  plans: []
  reports:
    - "STLB-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "compilation"
  - "ownership"
---

# STLB-PLN-0001 — Fix typed collections Vec module compilation and ownership

## 1. Objective

Repair `stdlib/vir/collections/vec.vri` (registered as `collections.vec` in `stdlib/stdlib.vri:210`) so that it compiles cleanly with zero diagnostics under `./bin/virc --check --json`, preserves `Vec of (T)` ownership invariants across query and mutation functions using canonical `ref` parameter semantics, and successfully resolves from external standard library consumers.

## 2. Source Issues

- `STLB-ISS-0007`: The typed collections Vec module does not compile (S1/P0).

## 3. Scope

### In Scope

- Fix entity instantiation syntax: change field assignments from `=` to `:` (`Vec of (T)(data: null, len: 0, cap: 0)`).
- Fix `Pair of (A, B)` entity declaration: eliminate trailing comma.
- Replace undefined `size_of of (T)()` calls with canonical built-in `sizeof(T)` expression.
- Fix parameter ownership: update query and mutating functions to accept `ref v: Vec of (T)` rather than by-value, preventing destructive ownership transfer on read operations.
- Correct `ref` argument passing at call sites: pass `v` instead of invalid temporary `&v`.
- Fix `vec_zip` variable initialization: ensure `n` is definitely initialized before use.
- Fix `vec_flatten` type signature and inner vector loading: use `Vec of (Vec of (T))` instead of raw `ptr`.
- Add focused consumer regression fixture `tests/strict_v2/collections_vec_consumer_e2e.vri` and register it in `run_tests.sh` Group 3.

### Out of Scope

- Type-receiver constructor syntax (`Vec of (T).alloc(...)`) and UFCS method dispatch facades, tracked separately under `STLB-ISS-0032`.
- Bootstrap runtime vector implementation in `rt/vec_rt.vri`.

## 4. Current Architecture

The `collections.vec` module was mapped to `stdlib/vir/collections/vec.vri` in `stdlib/stdlib.vri:210`. The source file contained legacy syntax and ownership anti-patterns that failed the active compiler's semantic passes:
- Instantiations used obsolete `=` syntax (`data = null`).
- Element stride calculations called undefined `size_of of (T)()`.
- Query functions took `v` by value, triggering `E5001` (use-after-move) in callers.
- Internal call sites attempted to pass `&var` into `ref` parameters, causing `E3048` temporary reference errors.

## 5. Proposed Architecture

- **Canonical Syntax**: All entity literals conform to `EntityName(field: val, ...)`.
- **Built-in Sizing**: Element sizing uses `sizeof(T)` expression directly.
- **Strict Borrow Semantics**: All non-consuming functions accept `ref v: Vec of (T)`. In Vir, callers pass `v` directly, and the caller retains ownership after the call.
- **Export Resolution**: External consumers import `Vec` and associated operations via `import ... from collections.vec` through `stdlib/stdlib.vri`.

## 6. Design Decisions

### Decision 1: Use `ref v: Vec of (T)` for Query Functions

**Decision:** Declare `vec_len`, `vec_cap`, `vec_is_empty`, `vec_get`, `vec_try`, `vec_clone`, `vec_equal`, and iteration functions with `ref v: Vec of (T)`.

**Rationale:** Vir moves entities by default when passed by value. If `vec_len(v)` took `v` by value, the caller would forfeit `v` on the first query. Passing by `ref` enables repeated queries while maintaining memory safety.

**Alternatives considered:** Using raw pointers or copying the entity record. Both forfeit type-safety and lifecycle tracking.

### Decision 2: Call-site Argument Passing without `&`

**Decision:** Pass `v` directly into `ref` parameters (`vec_push(v, item)`), avoiding `&v`.

**Rationale:** Vir language semantics specify that `ref` parameters receive the variable binding itself; `&v` creates a reference-to-reference temporary rejected with `E3048`.

## 7. Implementation Plan

### Phase 1 — Syntax and Parameter Signatures in `collections/vec.vri`

- files/modules: `stdlib/vir/collections/vec.vri`
- changes:
  - Fix entity literals, `sizeof(T)`, trailing commas, and `var n` initialization.
  - Update all query and mutating functions to take `ref v: Vec of (T)`.
  - Clean call-site parameter invocations.
- dependencies: none
- expected result: `./bin/virc stdlib/vir/collections/vec.vri --check --json` passes with 0 diagnostics.

### Phase 2 — Consumer Integration and Test Harness

- files/modules: `tests/strict_v2/collections_vec_consumer_e2e.vri`, `run_tests.sh`
- changes:
  - Create external consumer fixture validating `Vec` import and non-destructive `ref` queries.
  - Register fixture in Group 3 of `run_tests.sh`.
- dependencies: Phase 1
- expected result: Group 3 passes 15/15.

## 8. Compatibility

- source compatibility: Restores documented `collections.vec` API surface; does not alter bootstrap `vec` (`rt/vec_rt.vri`).
- ABI: No ABI changes.
- parser compatibility: Fully compliant with current Vir grammar.
- stdlib behavior: Consumers can now import and use `collections.vec`.

## 9. Migration

No migration required.

## 10. Validation Plan

- `./bin/virc stdlib/vir/collections/vec.vri --check --json` must return 0 diagnostics.
- `./run_tests.sh 3` must pass 15/15 including `collections_vec_consumer_e2e.vri`.
- `./paper validate` must pass.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Collision with bootstrap `vec` | Low | Low | `collections.vec` is distinctly namespaced in `stdlib.vri` |
| Regressions in UFCS resolution | Low | Med | Verified by Group 11 passing 62/62 |

## 12. Rollback Strategy

Revert changes in `stdlib/vir/collections/vec.vri` and `run_tests.sh` via git.

## 13. Exit Criteria

- [x] implementation completed;
- [x] test suite passes (Group 3: 15/15, Group 11: 62/62);
- [x] acceptance criteria satisfied;
- [x] report generated (`STLB-RPT-0001`);
- [x] linked issue moved to CLOSED.

## 14. Related Papers

- `STLB-ISS-0007`: The typed collections Vec module does not compile
- `STLB-ISS-0032`: Vec canonical UFCS surface is blocked by compiler dispatch
- `STLB-RPT-0001`: Typed collections Vec module verification report

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Completed plan after syntax, ownership, and consumer verification |
| 2026-10-09 | Initial draft allocated |
