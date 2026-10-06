---
id: "VIRC-PLN-0015"
type: "PLAN"
domain: "VIRC"
title: "Dispatch explicit f32 and f64 types to floating print intrinsic"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0031"
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

# VIRC-PLN-0015 — Dispatch explicit f32 and f64 types to floating print intrinsic

## 1. Objective

Resolve `VIRC-ISS-0022` by ensuring that `print` statements, numeric declarations, assignments, casts, and binary operations consistently classify expressions having semantic floating types (`float`, `f32`, `f64`, and their reference variants) as floating-point operations rather than falling back to 64-bit integer intrinsics. When printed, floating values must format as floating decimal strings (e.g. `212.0`) rather than exposing raw IEEE-754 bit representations (e.g. `4641663103447072768`).

## 2. Source Issues

- `VIRC-ISS-0022` — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads.

## 3. Scope

### In Scope

- Introduce a canonical predicate `is_float_type_name(name: &string) -> bool` in AST-to-MIR type inference (`compiler/src/lower/ast_to_mir/layout/type_infer.vri`) recognizing `float`, `f64`, `f32`, and referenced forms (`ref`, `mutref`, `&`, `&mut`).
- Update AST-to-MIR `print` lowering in both `compiler/src/lower/ast_to_mir/stmt.vri` and `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri` to dispatch to `MIR_INTR_PRINT_FLOAT` whenever `is_float_type_name(print_type)` holds or the AST node is `AstType.LiteralFloat`.
- Update AST-to-MIR variable declarations (`VarDecl`/`ConstDecl`) and assignments (`Assign`) in `compiler/src/lower/ast_to_mir/stmt.vri` so that type coercions between int and float properly recognize `f32` and `f64`.
- Update AST-to-MIR `CastExpr` lowering in `compiler/src/lower/ast_to_mir/expr.vri` to classify `f32` and `f64` under float category (`cat = 2`) so that explicit casts (e.g. `val as int`, `val as f64`, `val as f32`) invoke appropriate float-to-int (`fcvtzs`) or int-to-float (`scvtf`) conversions.
- Update binary operations in `compiler/src/lower/ast_to_mir/expr_ops.vri` and `compiler/src/lower/ast_to_mir/layout/type_infer.vri` to recognize `f32` and `f64` in operand type queries.
- Create automated test suite `tests/test_f32_f64_print.py` verifying literals, variables, direct calls, casts, array/tensor indexing, spills, and edge cases (-0.0, 0.0, fractions, infinities, NaNs) across optimization levels O0-O3.
- Document target limitations and record `VIRC-ISS-0031` for non-ARM64 backends lacking native `MIR_INTR_PRINT_FLOAT` runtime stubs.
- Verify 3-stage bootstrap fixed-point (`cmp bin/virc_stage2 bin/virc_stage3`).

### Out of Scope

- Implementing native IEEE-754 string formatting stubs for x86-64, RISC-V, and Wasm (tracked under `VIRC-ISS-0031`).
- Changes to the Vir language specification under `papers/VIR/specs/**`.
- Modifying dense tensor multi-dimensional memory layout or kernel compute routines.

## 4. Current Architecture

Currently, AST-to-MIR lowering infers the expression type name via `infer_expr_type_name(expr)`. When a function is declared `func foo() -> f64:`, the return type is preserved as `"f64"`. When a variable is declared `let x: f32 = ...`, the variable type is `"f32"`.
However, `stmt.vri:645` and `stmt_control/jumps.vri:92` only test:
```vir
eif ast_node_type_of(expr) == AstType.LiteralFloat or fat_cstr_eq(print_type, "float") == 1 do
    b2 = emit_intrinsic(b2, MIR_INTR_PRINT_FLOAT, mir_opnd_none(), val_opnd)
else
    b2 = emit_intrinsic(b2, MIR_INTR_PRINT, mir_opnd_none(), val_opnd)
end
```
Because `"f64"` and `"f32"` fail `fat_cstr_eq(print_type, "float") == 1`, they fall into the `else` branch, emitting `MIR_INTR_PRINT` (the integer print intrinsic). On ARM64, `x0` transports the IEEE-754 bit pattern, which is then formatted by `rt_print_int` as an unsigned decimal integer.

Similarly, in `compiler/src/lower/ast_to_mir/expr.vri:566-570`, `CastExpr` lowering only checks `"float"` and `"f64"`, omitting `"f32"`:
```vir
if fat_cstr_eq(cast_src_name, "float") == 1 or fat_cstr_eq(cast_src_name, "f64") == 1 do cast_src_cat = 2 end
if fat_cstr_eq(cast_dst_name, "float") == 1 or fat_cstr_eq(cast_dst_name, "f64") == 1 do
    cast_dst_cat = 2
    cast_mir_type = MirType.F64 as i64
end
```
And in `stmt.vri:87-88, 382-383`, `f32` is omitted from declaration and assignment float checks.

## 5. Proposed Architecture

1. Define `is_float_type_name(name: &string) -> bool` in `compiler/src/lower/ast_to_mir/layout/type_infer.vri`. The predicate unwraps any reference prefix (`ref`, `mutref`, `&`, `&mut`) and returns true if the type name equals `"float"`, `"f64"`, or `"f32"`.
2. In `stmt.vri:645` and `stmt_control/jumps.vri:92`, replace the float check with:
   `eif ast_node_type_of(expr) == AstType.LiteralFloat or is_float_type_name(print_type) do`
3. In `stmt.vri:87-88, 382-383, 447`, use `is_float_type_name(...)` for float classification.
4. In `expr.vri:566-570`, use `is_float_type_name(cast_src_name)` and `is_float_type_name(cast_dst_name)` to categorize float sources and destinations.
5. In `layout/type_infer.vri:264` and `expr_ops.vri:142, 150, 179, 198`, use `is_float_type_name(...)` to unify binary operator type classification.

## 6. Design Decisions

### Decision 1: Shared Predicate vs Inline String Checks

**Decision:** Implement a canonical predicate `is_float_type_name(name: &string) -> bool` in `compiler/src/lower/ast_to_mir/layout/type_infer.vri`.
**Rationale:** Multiple lowering sites (`print`, `CastExpr`, `VarDecl`, `Assign`, `BinOp`) must classify floating types consistently. Centralizing the check eliminates subtle drift (such as checking `"f64"` in some places while omitting `"f32"`).
**Alternatives considered:** Inline `or fat_cstr_eq(..., "f64") == 1 or fat_cstr_eq(..., "f32") == 1` at each callsite. Rejected due to code bloat and risk of omission.

### Decision 2: Multi-Backend Capability Tracking

**Decision:** Formally document that ARM64 provides native `MIR_INTR_PRINT_FLOAT` execution via `emit_lir_rt_print_float_stub`, while x86-64, RISC-V, and Wasm lack runtime stub implementations for floating-point printing. File target limitation issue `VIRC-ISS-0031`.
**Rationale:** Satisfies Acceptance Criterion 6 without expanding scope into multi-target floating-point runtime stub engineering on non-ARM platforms.

## 7. Implementation Plan

### Phase 1 — Canonical Float Predicate & Print Lowering
- files/modules: `compiler/src/lower/ast_to_mir/layout/type_infer.vri`, `compiler/src/lower/ast_to_mir/stmt.vri`, `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`
- changes: Define `is_float_type_name`. Use it in `PrintStmt` lowering in both `stmt.vri` and `jumps.vri`.
- dependencies: None.
- expected result: `/tmp/repro_f64_print.vri` and `/tmp/repro_f32_print.vri` print `212.0`.

### Phase 2 — Casts, Declarations, and Binary Operations
- files/modules: `compiler/src/lower/ast_to_mir/expr.vri`, `compiler/src/lower/ast_to_mir/stmt.vri`, `compiler/src/lower/ast_to_mir/expr_ops.vri`, `compiler/src/lower/ast_to_mir/layout/type_infer.vri`
- changes: Update `CastExpr`, `VarDecl`, `Assign`, `BinOp` to use `is_float_type_name`.
- dependencies: Phase 1.
- expected result: `val as int` produces integers; `int as f64` produces floats.

### Phase 3 — Automated Test Suite
- files/modules: `tests/test_f32_f64_print.py`
- changes: Comprehensive test matrix covering literals, variables, returns, casts, indexing, register pressure spills at O0-O3, edge cases (-0.0, fractions, inf, nan), and integer cast verification.
- dependencies: Phase 2.
- expected result: All tests pass deterministically.

### Phase 4 — Synchronization, 3-Stage Bootstrap & Paper Governance
- files/modules: `compiler/src/virc.vri`, `bin/virc*`, papers.
- changes: Run `sync_virc.py`, rebuild stage1 -> stage2 -> stage3, verify fixed-point `cmp`, allocate `VIRC-ISS-0031`, create `VIRC-RPT-0031`, validate papers.
- dependencies: Phase 3.
- expected result: Bit-identical fixed point, green `./paper validate`.

## 8. Compatibility

- source compatibility: 100% compatible. Fixes incorrect presentation of explicit `f32`/`f64` types.
- ABI: No change to ABI. Scalar register transport remains intact.
- parser compatibility: Unaffected.
- serialized formats: Unaffected.
- LSP protocol: Unaffected.
- public API: Unaffected.
- stdlib behavior: Unaffected.

## 9. Migration

No migration required. Existing valid Vir programs with `float` continue working identically; programs with `f32`/`f64` will now display correct numeric output instead of raw integer bit payloads.

## 10. Validation Plan

- Deterministic reproduction tests with `/tmp/repro_f64_print.vri` and `/tmp/repro_f32_print.vri`.
- Automated test script `tests/test_f32_f64_print.py` run under Python 3 testing:
  - Direct float/f32/f64 return values.
  - Local variable bindings with and without type annotations.
  - Casts: float -> int, int -> float, float -> f64, float -> f32.
  - Floating binary operations and comparisons.
  - Register pressure spills across loops and deep calls at `-O0`, `-O1`, `-O2`, `-O3`.
  - IEEE-754 edge cases: `-0.0`, `0.0`, fractional values (`0.125`, `-3.5`), infinities, and NaNs.
- Verification that integer print statements and explicit float-to-int casts (`val as int`, `val as i64`) print as integer decimal.
- Synchronization check (`tools/sync_virc.py --check`).
- 3-stage self-host bootstrap (`cmp bin/virc_stage2 bin/virc_stage3`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unintended type classification in compound expressions | Low | Medium | Restrict `is_float_type_name` to unwrap only references and match exact scalar float names |
| Inconsistency between `stmt.vri` and `stmt_control/jumps.vri` | Low | High | Update both AST-to-MIR lowering entry points simultaneously |
| Stage2/Stage3 binary divergence | Low | High | Ensure all changes are deterministic and canonical sources are synchronized before building |

## 12. Rollback Strategy

Revert changes to `compiler/src/lower/ast_to_mir/` and re-run `tools/sync_virc.py` to restore previous compiler behavior.

## 13. Exit Criteria

- [x] `is_float_type_name` predicate implemented and integrated in AST-to-MIR lowering.
- [x] `print return_f64()` and `print return_f32()` produce `212.0`, not raw integer bit patterns.
- [x] `test_f32_f64_print.py` test suite passes across all cases and optimization levels.
- [x] Non-ARM64 backend limitations tracked in linked issue `VIRC-ISS-0031`.
- [x] `tools/sync_virc.py --check` passes cleanly.
- [x] 3-stage bootstrap fixed-point verified (`cmp bin/virc_stage2 bin/virc_stage3` returns 0).
- [x] `VIRC-RPT-0031` generated and accepted, `VIRC-ISS-0022` marked `RESOLVED`, `./paper validate` clean.

## 14. Related Papers

- `VIRC-ISS-0022` — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads.
- `VIRC-ISS-0031` — x86-64, RISC-V, and Wasm backends lack native floating-point print runtime stubs.
- `VIR-ISS-0002` — Canonical typed identity and typed MIR metadata hardening.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial plan created and moved to IMPLEMENTING |
| 2026-10-04 | Linked VIRC-RPT-0031 |
| 2026-10-04 | Completed implementation and verification; moved status to COMPLETED |
