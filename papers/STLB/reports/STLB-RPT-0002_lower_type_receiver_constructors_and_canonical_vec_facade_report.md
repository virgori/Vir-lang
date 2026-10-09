---
id: "STLB-RPT-0002"
type: "REPORT"
domain: "STLB"
title: "Lower type receiver constructors and canonical Vec facade report"
status: "ACCEPTED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
  - "compiler"
components:
  - "collections"
  - "vec"
  - "generics"
  - "ufcs"
  - "constructors"
  - "codegen"
related:
  issues:
    - "STLB-ISS-0032"
  plans:
    - "STLB-PLN-0002"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "ufcs"
  - "constructors"
  - "verification"
---

# STLB-RPT-0002 — Lower type receiver constructors and canonical Vec facade report

## 1. Executive Summary

This report verifies the resolution of `STLB-ISS-0032` ("Vec constructors and generic receiver UFCS are blocked by compiler dispatch") and the execution of `STLB-PLN-0002`.
The active Vir compiler now parses dotted generic invocations `recv.method of (TypeArgs)(args)`, lowers type-receiver constructors (`Item.new(...)`, `Vec.alloc of (int)(4)`, `Vec.new of (int)()`, `Vec.create of (int)(val, count)`), lowers intrinsic generic memory stores and loads (`native_store of (T)`, `native_load of (T)`), and resolves generic receiver UFCS calls (`v.push(x)`, `v.get(i)`, `v.len()`, `v.isEmpty()`, `v.free()`).
The standard library module `collections.vec` (`stdlib/vir/collections/vec.vri`) exposes the approved canonical `Vec` facade while preserving 100% backwards compatibility with existing `vec_*` symbols.
All test suites pass without regression: Group 3 (`16/16 PASS`), Group 11 (`68/68 PASS`), 3-stage bootstrap fixed point is bit-for-bit identical, and VPS paper validation passes with 0 errors.

## 2. Source Issues

- `STLB-ISS-0032`: Vec constructors and generic receiver UFCS are blocked by compiler dispatch (S1/P0).

## 3. Source Plans

- `STLB-PLN-0002`: Lower type receiver constructors and canonical Vec facade.

## 4. Implementation Summary

1. **Parser Dotted Generic Call Support**:
   - In `compiler/src/frontend/parser/expr/unary.vri`, extended method parsing following `.` and `field_tok` to recognize `of (TypeArgs)(args)` and emit `AstType.MethodCall` with generic argument metadata packed into `name2`.
   - In `compiler/src/frontend/parser/stmt_decl/aggregate_def.vri`, skipped leading empty lines in entity bodies to allow whitespace-separated method declarations.
2. **Semantic Typecheck & Type-Receiver Identification**:
   - In `compiler/src/semantic/typecheck/walk_method.vri`, identified type-receiver method calls where the receiver is an entity identifier without local variable binding.
   - Bound generic entity parameters (`Vec<int>`) from explicit generic arguments or inferred method arguments.
   - Enforced fail-closed rejection for instance methods requiring `this` invoked on type receivers (`E3021`), and missing generic arguments on generic type receivers (`E3001`).
3. **AST-to-MIR Lowering & Monomorphization**:
   - In `compiler/src/lower/ast_to_mir/calls.vri`, detected type-receiver method calls (`is_type_receiver`), preventing prepending `recv` as a runtime argument and omitting synthetic `this` parameter generation.
   - Implemented `lower_native_store` and `lower_native_load` in `calls.vri` to lower `native_store of (T)` and `native_load of (T)` to direct typed memory instructions (`emit_store_typed` / `emit_load_typed`), enabling generic vector element indexing and stores across all primitive widths without external runtime stubs.
   - In `compiler/src/lower/ast_to_mir/func.vri`, detected type-receiver methods (`is_type_receiver_method`) and suppressed synthetic `this` parameter synthesis in both `ast_lower_func` and `specialize_method_def`.
4. **Standard Library Canonical Vec Facade**:
   - In `stdlib/vir/collections/vec.vri`, added methods `new`, `alloc`, `create`, `len`, `cap`, `isEmpty`, `is_empty`, `get`, `try`, `set`, `first`, `last`, `push`, `pop`, `insert`, `remove`, `swapRemove`, `swap_remove`, `extend`, `contains`, `find`, `count`, `reverse`, `swap`, `clone`, `copy`, `equal`, `reserve`, `compact`, `truncate`, `clear`, and `free` to `entity Vec of (T)`.
   - Annotated return types on `vec_new`, `vec_alloc`, `vec_with_cap`, `vec_from_slice`, `vec_create`, and `vec_filled` to ensure correct field offset inference on constructed entities.
   - Retained all existing `vec_*` functions for backwards compatibility during the migration cycle.
5. **Regression & E2E Verification**:
   - Created `tests/strict_v2/canonical_vec_facade_e2e.vri` covering `Vec.new`, `Vec.create`, `Vec.alloc`, `v.push`, `v.len`, `v.get`, `v.set`, `v.contains`, `v.count`, `v.swap`, `v.reverse`, and `v.free`.
   - Created `tests/strict_v2/type_receiver_instance_method_rejected.vri` (`E3021`) and `tests/strict_v2/type_receiver_generic_missing_args_rejected.vri` (`E3001`).
   - Integrated fixtures into `run_tests.sh` Groups 3 and 11.

## 5. Changes by Component

### `compiler/src/frontend/parser/`

- change: Parsed dotted generic method invocations `recv.method of (TypeArgs)(args)` and allowed leading whitespace before entity method blocks.
- reason: Enable `Vec.alloc of (int)(4)` and generic method syntax per `VIR-SPC-0018`.
- impact: Parser emits complete `MethodCall` AST with generic metadata.

### `compiler/src/semantic/typecheck/`

- change: Detected type receivers, bound generic entity types, and rejected instance methods on type receivers.
- reason: Validate constructor calls and prevent invalid invocations on uninstantiated types.
- impact: Safe compile-time type checking with descriptive diagnostics.

### `compiler/src/lower/ast_to_mir/`

- change: Lowered type-receiver calls without synthetic `this` arguments, and implemented direct lowering for generic `native_store` and `native_load`.
- reason: Eliminate lowering unresolved identifier errors and linker failures for generic element load/store operations.
- impact: Monomorphized constructors and generic collections compile and execute natively.

### `stdlib/vir/collections/vec.vri`

- change: Exposed canonical type-receiver constructors and receiver methods on `Vec of (T)` while preserving all `vec_*` functions and adding return type annotations to constructors.
- reason: Provide the canonical public surface described in `stdlib/registry/vec.md`.
- impact: Consumers can write idiomatic `Vec.alloc of (int)(16)` and `v.push(42)` syntax.

### `tests/strict_v2/` & `run_tests.sh`

- change: Added `canonical_vec_facade_e2e.vri`, `type_receiver_instance_method_rejected.vri`, and `type_receiver_generic_missing_args_rejected.vri` into Groups 3 and 11.
- reason: Ensure continuous regression protection across both positive execution and negative rejection paths.
- impact: Test harness reliably verifies canonical Vec operations and type receiver semantics.

## 6. Deviations from Plan

No deviations from the implementation plan in `STLB-PLN-0002`.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `tests/strict_v2/canonical_vec_facade_e2e.vri` | PASS | E2E execution matches expected outputs for `Vec.new`, `Vec.create`, `Vec.alloc`, `push`, `get`, `set`, `swap`, `reverse`, `free` |
| `tests/strict_v2/type_receiver_instance_method_rejected.vri` | PASS | Rejected with `E3021` |
| `tests/strict_v2/type_receiver_generic_missing_args_rejected.vri` | PASS | Rejected with `E3001` |
| `./run_tests.sh 3` (Hệ thống Module) | PASS | 16/16 PASS (100%) |
| `./run_tests.sh 11` (UFCS & Generics) | PASS | 68/68 PASS (100%) |
| Bootstrap Fixed-Point | PASS | `bin/virc`, `bin/virc.stage1`, `bin/virc.stage2` identical (19,600,879 bytes, SHA-256 `ab6b6f783c1c1655d8cfc067d64d233ad6743037ff9944a0a0aba0da255c8110`) |
| `./paper validate` | PASS | 255 production papers, 0 errors |

### Regression

- Group 3 (16/16 PASS) confirms all module export, include, and collections tests pass.
- Group 11 (68/68 PASS) confirms all UFCS, member resolution, and generic receiver specialization tests pass without regressions.

## 8. Acceptance Criteria

- [x] Type-receiver constructors pass semantic checking and native lowering (`Vec.new`, `Vec.alloc`, `Vec.create`).
- [x] Generic Vec receiver calls resolve with the correct specialization and preserve `ref`/move semantics (`v.push`, `v.get`, `v.len`, `v.isEmpty`, etc.).
- [x] `Vec.new`, `Vec.alloc`, `Vec.create`, and all one-level receiver calls have focused positive and negative tests (`canonical_vec_facade_e2e.vri`, `type_receiver_instance_method_rejected.vri`, `type_receiver_generic_missing_args_rejected.vri`).
- [x] `collections.vec` exposes the canonical facade without removing the old compatibility symbols before a documented migration window.
- [x] `STLB-ISS-0007` is independently closed by making the typed module pass its complete semantic and ownership check (closed in `STLB-RPT-0001`).

## 9. Known Limitations

- Three-level dotted operations (`collections.vec.Vec.alloc`) are tracked under `STLB-ISS-0033`.

## 10. Remaining Work

- Resolution of three-level member/UFCS paths tracked in `STLB-ISS-0033`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `STLB-ISS-0032`: Vec constructors and generic receiver UFCS are blocked by compiler dispatch
- `STLB-PLN-0002`: Lower type receiver constructors and canonical Vec facade
- `STLB-ISS-0007`: The typed collections Vec module does not compile
- `STLB-RPT-0001`: Typed collections Vec module verification report
- `STLB-ISS-0033`: Three-level Vec UFCS paths conflict with member access semantics
- `VIRC-ISS-0064`: Generic receiver UFCS does not resolve or specialize for generic entities

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial verification report confirming type-receiver constructors, native load/store lowering, canonical Vec facade, and test suite execution |
