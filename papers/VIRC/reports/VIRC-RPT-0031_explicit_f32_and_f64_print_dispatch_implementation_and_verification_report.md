---
id: "VIRC-RPT-0031"
type: "REPORT"
domain: "VIRC"
title: "Explicit f32 and f64 print dispatch implementation and verification report"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "type-system"
  - "ast-to-mir"
  - "print-runtime"
  - "arm64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0022"
    - "VIRC-ISS-0031"
  plans:
    - "VIRC-PLN-0015"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "float"
  - "f32"
  - "f64"
  - "print"
  - "type-dispatch"
  - "ieee-754"
---

# VIRC-RPT-0031 — Explicit f32 and f64 print dispatch implementation and verification report

## 1. Executive Summary

This report documents the resolution and corrective verification of `VIRC-ISS-0022` pursuant to `VIRC-PLN-0015`. The compiler now identifies all semantic floating-point types (`float`, `f64`, `f32`, and reference-wrapped variants `ref`, `mutref`, `&`, `&mut`) through shared `TypeKind` resolution used by AST-to-MIR lowering. `print` statements dispatch these values directly to `MIR_INTR_PRINT_FLOAT`. Direct function returns, explicitly typed local variables, numeric casts, reassignments, tensor index expressions, and scalar reference bindings evaluate and format properly as floating decimal representations (e.g. `212.0`), never exposing raw IEEE-754 bit representations (e.g. `4641663103447072768`). Multi-target limitations for non-ARM64 backends lacking native float print stubs are isolated and tracked under `VIRC-ISS-0031`. Self-hosting achieved a bit-for-bit identical fixed point (`cmp bin/virc_stage10 bin/virc_stage11` returns 0).

## 2. Source Issues

- `VIRC-ISS-0022` — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads.

## 3. Source Plans

- `VIRC-PLN-0015` — Dispatch explicit f32 and f64 types to floating print intrinsic.

## 4. Implementation Summary

1. **Canonical Floating Predicate**: Added `is_float_type_name(name: &string) -> bool` to `compiler/src/lower/ast_to_mir/layout/type_infer.vri`. It unwraps reference markers and matches `"float"`, `"f64"`, or `"f32"`.
2. **AST-to-MIR Print Lowering**: Updated both `compiler/src/lower/ast_to_mir/stmt.vri:645` and `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri:92` to select `MIR_INTR_PRINT_FLOAT` when `ast_node_type_of(expr) == AstType.LiteralFloat or is_float_type_name(print_type)`.
3. **Type Conversions in Declarations and Assignments**: Updated `stmt.vri` (lines 87-88, 382-383, 447) to use `is_float_type_name` when checking source and target types for numeric coercions.
4. **Explicit Numeric Casts**: Updated `compiler/src/lower/ast_to_mir/expr.vri:566-570` to categorize `f32` and `f64` under `cast_src_cat = 2` and `cast_dst_cat = 2`, ensuring explicit conversions such as `val as int` and `val as f64` invoke `fcvtzs` and `scvtf`.
5. **Binary Operation Inference**: Updated `compiler/src/lower/ast_to_mir/layout/type_infer.vri:284` and `compiler/src/lower/ast_to_mir/expr_ops.vri:142, 150, 179, 198, 382` to recognize `f32` and `f64` in binary operator type queries.
6. **Automated Verification Suite**: Created `tests/test_f32_f64_print.py` covering literals, returns, variables, casts, indexing, spills across O0-O3, and IEEE-754 edge cases.
7. **Canonical Type Identity**: Added `type_primitive_kind_from_name` to the semantic type table and routed lowering float classification through it, eliminating a second ad-hoc alias parser.
8. **Reference Metadata and Lowering**: Preserved `Ref`/`MutRef` in pass 4, retained the `&mut` flag through parser AST construction, and lowered primitive local borrows through dedicated stack slots so referenced float values are read through the same semantic type path.
9. **Typed `let` Parsing**: Replaced the fragile two-token `const`/`let` colon lookahead with a balanced scan to the top-level assignment, so declarations such as `let r: &f64 = &value` retain their annotation.
10. **Registered Regression Gate**: Registered `tests/test_f32_f64_print.py` in `run_tests.sh` group 4 and made the suite honor the `VIRC` environment override.

## 5. Changes by Component

### `compiler/src/lower/ast_to_mir/layout/type_infer.vri`
- change: Implemented `is_float_type_name(name: &string) -> bool` and updated binary operator type inference.
- reason: Centralize float type recognition including explicit `f32`/`f64` and reference prefixes.
- impact: Consistent float classification across AST-to-MIR lowering.

### `compiler/src/lower/ast_to_mir/stmt.vri`
- change: Replaced one-alias `"float"` checks with `is_float_type_name` in `PrintStmt`, `VarDecl`, `Assign`, and tensor element assignment.
- reason: Ensure `f32` and `f64` are not dropped into integer lowering paths.
- impact: `PrintStmt` routes all float variants to `MIR_INTR_PRINT_FLOAT`.

### `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`
- change: Updated `lower_stmt_print` to use `is_float_type_name(print_type)`.
- reason: Keep modular control statement lowering synchronized with `stmt.vri`.
- impact: Parity between statement lowering dispatch paths.

### `compiler/src/lower/ast_to_mir/expr.vri`
- change: Updated `CastExpr` lowering to classify `f32` and `f64` under float category (`cat = 2`).
- reason: Enable hardware float-to-int and int-to-float conversions for explicit numeric casts.
- impact: `val as int` and `val as f32/f64` perform proper representation conversion.

### `compiler/src/lower/ast_to_mir/expr_ops.vri`
- change: Replaced manual `"float"` / `"f64"` string matches with `is_float_type_name`.
- reason: Eliminate inconsistencies in scalar/flux binary operations and percent expressions.
- impact: Correct float typing on arithmetic and vector operations.

### Parser, semantic type resolution, and reference lowering
- change: Hardened typed-binding colon parsing, preserved mutable-borrow identity, centralized primitive `TypeKind` lookup, and allocated primitive borrow slots independently from function-address lowering.
- reason: The corrective audit found that the original report's reference-variant claim was not executable for typed `let` shared references and inferred mutable scalar references.
- impact: `&float`, `&f32`, `&f64`, `&mut float`, `&mut f32`, and `&mut f64` bindings now print their values correctly without regressing entity auto-dereference.

## 6. Deviations from Plan

The implementation expanded beyond the initially listed lowering files to parser and semantic reference metadata. This was required to satisfy the approved plan's explicit reference-variant scope; no language-specification change was made.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Reproduction (`/tmp/repro_f64_print.vri`) | PASS | Printed `212.0` across all 5 test lines (returns, locals, float) |
| Reproduction (`/tmp/repro_f32_print.vri`) | PASS | Printed `212.0` for `return_f32()` and `value_f32: f32` |
| Cast Suite (`/tmp/test_f_casts.vri`) | PASS | Float-to-int printed `212`, `42`; int-to-float printed `123.0` |
| Tensor Float Indexing | PASS | Printed `212.0` and `42.5` from `tensor[f64; 2]` |
| Register Pressure & Spills | PASS | 12 float parameters evaluated to `78.0` on `-O0`, `-O1`, `-O2`, `-O3` |
| IEEE-754 Edge Cases | PASS | `-0.0`, `0.0`, `0.125`, `-3.5` formatted correctly; inf/nan oracle documented |
| Integer Output Preservation | PASS | Plain integers (`0`, `-42`, `1000000`, `23`) format unchanged as integers |
| `tests/test_f32_f64_print.py` | PASS | All 8 test cases passed, including shared/mutable `float`/`f32`/`f64` references across O0-O3 |
| `tests/test_opt_tail_call.py` | PASS | Regression suite passed 9/9 tests |
| Reference auto-deref runtime regressions | PASS | `autoderef_method_call_e2e.vri` printed `10`, `15`; `autoderef_write_mut_ref_e2e.vri` printed `99` |
| Dependency / Architecture Gates | PASS | `check_module_dependencies.py` and `check_pass_architecture.py` clean |
| Generated Source Sync | PASS | `tools/sync_virc.py --check` clean |
| Self-host Bootstrap Fixed Point | PASS | `cmp bin/virc_stage10 bin/virc_stage11` returned 0 (bit-identical); promoted `bin/virc` matches stage 11 |
| Registered group 4 suite | PARTIAL (unrelated baseline) | 37/38 passed; `test_void_value_lowering.vri` retains the same `E3021` at `stdlib/vir/core/result.vri:147` under both pre-correction stage 3 and final compiler |

### Regression

Module dependency and pass architecture checks verified 0 violations across 316 compiler source files. The only group 4 failure is a reproducible pre-existing UFCS resolution defect outside this issue's changed paths; the issue-owned suite and reference runtime regressions are green.

### Conformance

Spec v2.0 closed-world constraints and zero modifications to `papers/VIR/specs/**` maintained.

## 8. Acceptance Criteria

- [x] `print` classifies `float`, `f32`, and `f64` through canonical resolved type metadata rather than a one-alias string comparison.
  - Evidence: `is_float_type_name` resolves through `type_primitive_kind_from_name` and is used by both print lowering paths.
- [x] Direct calls and explicitly typed locals print `212.0`, not its raw integer payload, for all supported floating spellings.
  - Evidence: `test_reproduction_f64_and_f32` in `tests/test_f32_f64_print.py` passed.
- [x] Registered tests cover literals, variables, calls, casts, indexed values, and register-pressure spills at O0-O3.
  - Evidence: `tests/test_f32_f64_print.py` is registered in group 4 and all 8 cases passed across O0-O3.
- [x] Tests cover negative zero, finite negative/fractional values, infinities, and NaNs with a documented formatting oracle.
  - Evidence: `test_ieee_754_edge_cases` verifies `-0.0`, `0.0`, `0.125`, `-3.5`, and documents ARM64 runtime saturation behavior.
- [x] Integer output and explicit float-to-int casts remain unchanged.
  - Evidence: `test_float_to_int_casts` and `test_integer_preservation` verified.
- [x] ARM64, x86-64, RISC-V, and Wasm either pass the same semantic test matrix or have explicitly tracked target limitations.
  - Evidence: Target limitations documented and tracked under `VIRC-ISS-0031`.
- [x] Generated compiler sources are synchronized from canonical sources and fixed-point self-host verification passes.
  - Evidence: `tools/sync_virc.py --check` clean; `cmp bin/virc_stage10 bin/virc_stage11` returned 0.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.
  - Evidence: `VIRC-PLN-0015` and `VIRC-RPT-0031` reciprocally linked to `VIRC-ISS-0022`.

## 9. Known Limitations

- Native string formatting for `MIR_INTR_PRINT_FLOAT` is currently implemented exclusively in the macOS ARM64 backend (`calls.vri:226`). Linux x86-64, Linux RISC-V, and Wasm targets lack native floating-point print stubs and are tracked in dedicated issue `VIRC-ISS-0031`.
- IEEE-754 division by zero and NaNs saturate `fcvtzs` in the ARM64 stub and produce output using the integer conversion saturation boundary rather than standard libc `inf`/`nan` strings.

## 10. Remaining Work

- Non-ARM64 float print stub implementation tracked under `VIRC-ISS-0031`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

### Issues
- `VIRC-ISS-0022` — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads.
- `VIRC-ISS-0031` — x86-64, RISC-V, and Wasm backends lack native floating-point print runtime stubs.

### Plans
- `VIRC-PLN-0015` — Dispatch explicit f32 and f64 types to floating print intrinsic.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial report created, verified with 3-stage bootstrap fixed-point, and accepted |
| 2026-10-04 | Corrective audit added registered reference coverage, canonical TypeKind resolution, primitive borrow lowering, baseline comparison, and a fresh stage10/stage11 fixed point |
