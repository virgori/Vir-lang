---
id: "STLB-RPT-0001"
type: "REPORT"
domain: "STLB"
title: "Typed collections Vec module verification report"
status: "ACCEPTED"
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
  plans:
    - "STLB-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "verification"
  - "ownership"
---

# STLB-RPT-0001 — Typed collections Vec module verification report

## 1. Executive Summary

This report verifies the resolution of `STLB-ISS-0007` ("The typed collections Vec module does not compile").
The registered standard library module `collections.vec` (`stdlib/vir/collections/vec.vri`) now compiles cleanly under `./bin/virc --check --json` with zero diagnostics (reduced from 70 initial diagnostics).
All `Vec of (T)` query functions and mutating functions have been updated to use canonical `ref v: Vec of (T)` borrow parameter semantics, preventing destructive ownership moves on reads.
A new external consumer regression fixture `tests/strict_v2/collections_vec_consumer_e2e.vri` verifies public export resolution through `stdlib/stdlib.vri` and repeated `ref` queries.
The post-acceptance continuation also removes the unresolved direct
`native_store`/`native_load` calls from specialized Vec code by lowering the
typed intrinsics directly to MIR memory operations. The canonical facade now
executes `Vec<int>`, `Vec<u8>`, and `Vec<i16>` allocation, growth, stores, and
loads. The final test harness (Group 3: 16/16 PASS, Group 7: 59/59 PASS, Group
11: 68/68 PASS) and compiler fixed point remain green.

## 2. Source Issues

- `STLB-ISS-0007`: The typed collections Vec module does not compile (S1/P0).

## 3. Source Plans

- `STLB-PLN-0001`: Fix typed collections Vec module compilation and ownership.

## 4. Implementation Summary

1. **Entity Instantiation Syntax**:
   - Replaced obsolete `=` with canonical `:` in entity literals (`Vec of (T)(data: null, len: 0, cap: 0)`).
2. **Built-in Element Sizing**:
   - Replaced undefined `size_of of (T)()` function calls with the Vir language built-in operator `sizeof(T)`.
3. **Borrow and Ownership Semantics**:
   - Updated query functions (`vec_len`, `vec_cap`, `vec_is_empty`, `vec_get`, `vec_try`, `vec_clone`, `vec_equal`, `vec_for_each`, `vec_map`, `vec_filter`, `vec_any`, `vec_all`, `vec_fold`, `vec_zip`, `vec_enumerate`, `vec_dedup`, `vec_as_ptr`, `vec_as_slice`) to take `ref v: Vec of (T)`, eliminating use-after-move errors (`E5001`).
   - Updated mutating functions (`vec_reserve`, `vec_compact`, `vec_shrink_to_fit`, `vec_push`, `vec_pop`, `vec_insert`, `vec_remove`, `vec_swap_remove`, `vec_clear`, `vec_truncate`, `vec_extend`, `vec_extend_from_slice`, `vec_swap`, `vec_reverse`, `vec_free`) to take `ref v: Vec of (T)`.
   - Callers pass `v` directly into `ref` parameters instead of temporary references (`&v`).
4. **Clean Grammar & Typing**:
   - Removed trailing comma in `Pair of (A, B)`.
   - Initialized variable `var n = a.len` in `vec_zip`.
   - Fixed `vec_flatten` signature from `nested: ptr` to `nested: Vec of (Vec of (T))`.
5. **Consumer Regression Coverage**:
   - Added `tests/strict_v2/collections_vec_consumer_e2e.vri` importing `Vec, vec_new, vec_len, vec_cap, vec_is_empty from collections.vec`.
   - Registered fixture in Group 3 of `run_tests.sh`.
6. **Generic Native Load/Store Completion**:
   - Added typed MIR lowering for `native_store of (T)` and `native_load of
     (T)`, including element-size address scaling, signed narrow loads, and the
     aggregate byte-copy path.
   - Added concrete generic return inference for `native_load of (T)`.
   - Added the canonical Vec facade regression and exercised 8-, 1-, and 2-byte
     element widths (`int`, `u8`, and `i16`).

## 5. Changes by Component

### `stdlib/vir/collections/vec.vri`

- change: Converted entity literals to `data: null`, `size_of of (T)()` to `sizeof(T)`, added `ref v: Vec of (T)` parameter semantics across all operations, and removed temporary `&` call-site passes.
- reason: Satisfy Vir language specification and borrow checker rules.
- impact: Module compiles with 0 diagnostics under `--check` and can be consumed safely without destructive moves.

### `tests/strict_v2/collections_vec_consumer_e2e.vri`

- change: Created end-to-end regression test importing from `collections.vec` and performing multiple query operations on a `ref` parameter.
- reason: Verify external export resolution via `stdlib/stdlib.vri` and borrow preservation.
- impact: Prevents regression in module visibility and parameter passing.

### `run_tests.sh`

- change: Added `tests/strict_v2/collections_vec_consumer_e2e.vri` to Group 3 (`Hệ thống Module`).
- reason: Integrate new fixture into continuous test runner.
- impact: Group 3 now validates module export and consumer integration.

### `compiler/src/lower/ast_to_mir/calls.vri`

- change: Lowered typed `native_store` and `native_load` calls directly to MIR
  typed memory operations instead of emitting unresolved direct function calls.
- reason: Specialized `vec_store`/`vec_load` must preserve `sizeof(T)` addressing
  and link without runtime symbols named `native_store` or `native_load`.
- impact: Canonical Vec mutation and retrieval execute for narrow and word-size
  element types.

### `compiler/src/semantic/typecheck/eval.vri` and `inference.vri`

- change: Resolved the concrete generic return kind of `native_load of (T)` and
  retained a builtin fallback for unresolved contexts.
- reason: Vec getters need the specialized element type to propagate through
  semantic analysis and lowering.
- impact: `Vec.get()` returns the expected specialized scalar type.

### `tests/strict_v2/canonical_vec_facade_e2e.vri`

- change: Added end-to-end coverage for constructors, same-name `len()`/`cap()`
  methods, mutations, queries, and `int`/`u8`/`i16` memory paths.
- reason: Verify the public facade and generic native memory path together.
- impact: Prevents recurrence of the unresolved `native_store` linker failure
  and incorrect fixed-width element strides.

## 6. Deviations from Plan

The original plan restored module compilation but deliberately deferred direct
generic `native_load`/`native_store` lowering. That deferred path subsequently
blocked executable use of the canonical Vec facade. The issue was therefore
continued under its existing scope, with compiler lowering and a facade E2E
fixture added; no language-syntax or public API contract changed.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `./bin/virc stdlib/vir/collections/vec.vri --check --json` | PASS | `diagnostics: []`, `error_count: 0`, `success: true` |
| `./run_tests.sh 3` (Hệ thống Module) | PASS | 16/16 PASS, including `collections_vec_consumer_e2e.vri` and `canonical_vec_facade_e2e.vri` |
| `./run_tests.sh 7` (Entity & Packed Entity) | PASS | 59/59 PASS |
| `./run_tests.sh 11` (UFCS & Generics) | PASS | 68/68 PASS |
| Canonical Vec facade | PASS | `int`, `u8`, and `i16` stores/loads produce the declared expected output |
| Bootstrap Fixed-Point | PASS | `bin/virc.stage1` and `bin/virc.stage2` identical: 19,600,879 bytes, SHA-256 `b0b24d205fd6b358ccde7e4929ccad409f294ee81db1768f789c6a69ea39c9f0` |
| Compiler version gates | PASS | promoted `virc 2026.1.9`; version metadata, generated sync, and version-policy checks pass |
| `./run_tests.sh min` | 468/470 PASS | Vec/module/member paths pass; failures are the open `VIRC-ISS-0053` stack-exhaustion oracle and the independent `MEM-OVERFLOW-001` Arena fixture ambiguity |

### Regression

- All existing module tests in Group 3 pass without regression.
- Generic receiver UFCS tests in Group 11 pass 100%.

## 8. Acceptance Criteria

- [x] The registered module passes `./bin/virc stdlib/vir/collections/vec.vri --check --json` with zero diagnostics on a newly built active compiler.
- [x] Public exports resolve from a consumer outside the module source directory through `stdlib/stdlib.vri`.
- [x] A focused regression test fails before the repair and passes afterward, including the relevant error or ownership path (`collections_vec_consumer_e2e.vri`).
- [x] The repair uses current Vir syntax and explicitly exported dependency names; it does not rely on selective-import fail-open behavior.
- [x] Existing module/resolver and relevant stdlib test groups remain green (Group 3: 16/16, Group 7: 59/59, Group 11: 68/68).
- [x] Any API contract change is linked to the applicable API specification issue (`STLB-ISS-0032`).
- [x] A VPS PLAN (`STLB-PLN-0001`) and verification REPORT (`STLB-RPT-0001`) link this ISSUE before closure.

## 9. Known Limitations

No remaining limitation from the reported generic native load/store link failure
is known for the scalar widths exercised by the canonical Vec regression.

The repository-wide `min` gate is not wholly green: Group 6 retains the known
`VIRC-ISS-0053` stack-exhaustion red test, and Group 27's
`MEM-OVERFLOW-001` fixture fails semantic analysis because two visible
`arena_alloc` providers make its dotted UFCS calls ambiguous. Neither failure
uses `collections.vec` or the generic native load/store path.

## 10. Remaining Work

None for `STLB-ISS-0007`; the canonical facade lifecycle is recorded separately
under `STLB-ISS-0032`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `STLB-ISS-0007`: The typed collections Vec module does not compile
- `STLB-PLN-0001`: Fix typed collections Vec module compilation and ownership
- `STLB-ISS-0032`: Vec canonical UFCS surface is blocked by compiler dispatch

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Continued the accepted report with direct generic native load/store lowering, canonical Vec int/u8/i16 execution, compiler 2026.1.9 fixed point, and refreshed Groups 3/7/11 evidence |
| 2026-10-09 | Initial report verifying clean compilation, ownership fixes, and consumer test execution |
