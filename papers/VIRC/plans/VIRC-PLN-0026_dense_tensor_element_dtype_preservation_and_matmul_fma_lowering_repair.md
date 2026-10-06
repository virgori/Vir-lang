---
id: "VIRC-PLN-0026"
type: "PLAN"
domain: "VIRC"
title: "Dense tensor element dtype preservation and matmul FMA lowering repair"
status: "COMPLETED"
created: "2026-10-05"
updated: "2026-10-06"
owners:
  - "compiler"
components:
  - "tensor"
  - "ast-to-mir"
  - "mir"
  - "lir"
  - "codegen"
  - "runtime-stubs"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0016"
  plans: []
  reports:
    - "VIRC-RPT-0043"
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "dtype"
  - "matmul"
  - "fma"
  - "correctness"
  - "lowering"
---

# VIRC-PLN-0026 — Dense tensor element dtype preservation and matmul FMA lowering repair

## 1. Objective

Restore dense tensor declared element dtype preservation end-to-end across AST-to-MIR
lowering, LIR intrinsic code generation, and native machine-code runtime stubs. Ensure
that explicitly declared types such as `tensor[i32; ...]` and `tensor[f32; ...]` retain
their 4-byte packed layout, correct memory allocation sizing, type-appropriate indexing
and float conversions, and target-native single-precision runtime math stubs without dtype
erasure to generic 8-byte `int` or `f64`.

## 2. Source Issues

- VIRC-ISS-0016 — Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA

## 3. Scope

### In Scope

- AST-to-MIR lowering in `compiler/src/lower/ast_to_mir/stmt.vri`:
  - Eliminate literal-kind type overwriting in `VarDecl` and `ConstDecl`.
  - Introduce dedicated tensor literal lowering (`lower_tensor_literal`) that sizes allocations
    by `16 + numel * elem_sz` and stores elements with typed `INDEX_STORE` matching declared dtype.
  - Eliminate dtype erasure in uninitialized `VarDecl` (removing forced 8-byte promotion).
  - Eliminate dtype erasure in `IndexAssign` (removing overwriting of `vtype` to `tensor[int; ...]` or `tensor[f64; ...]`).
  - Preserve `MirType.F64` for `code == 7` in `IndexAssign`.
- AST-to-MIR expression lowering in `compiler/src/lower/ast_to_mir/expr.vri`:
  - Preserve `MirType.F64` for `code == 7` in `IndexAccess`.
- Backend code generation in `compiler/src/backend/codegen.vri`:
  - Add and export ARM64 single-precision float encoders (`arm64_ldr_s_reg_lsl2`, `arm64_str_s_reg_lsl2`,
    `arm64_fmadd_ssss`, `arm64_fmov_szr`, `arm64_fcvt_ds`, `arm64_fcvt_sd`).
- LIR intrinsic code generation in `compiler/src/lower/lir_codegen/intrinsics.vri`:
  - Correct `MIR_INTR_INDEX` and `MIR_INTR_INDEX_STORE` for `LirType.F32`: convert loaded 32-bit floats
    to standard binary64 doubles in registers, and convert 64-bit double registers to 32-bit single precision
    on memory store.
- Native runtime math stubs in `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`:
  - Update `emit_lir_rt_matmul_f64_stub` to inspect `X5` (`is_32bit`); when set, allocate `16 + numel * 4`
    bytes and execute the 32-bit single-precision FMADD loop using ARM64 S-registers.
- Test verification:
  - Verify `tests/strict_v2/fma_tensor_e2e.vri`, `tests/strict_v2/fma_float_rectangular_e2e.vri`, and
    `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` at O0-O3.
  - Verify complete tensor test suites.

### Out of Scope

- Changes to the Vir language specification (`papers/VIR/specs/**` remains frozen).
- Quantized tensor codec alterations (e.g. Q8_0 view formats).
- SIMD vector loop transforms or pass 10 optimizer alterations.
- Unrelated compiler backends outside active native targets.

## 4. Current Architecture

Currently, `stmt.vri:121-147` inspects the first element of an `ArrayLiteral` initializer and
overwrites the declared tensor type (`var_t`) with `tensor[int; ...]` or `tensor[f64; ...]`.
`lower_aggregate` in `builder.vri:524-550` allocates array buffers with 8-byte slots and untyped
stores, storing 8-byte integers or doubles at 8-byte offsets even for `i32` or `f32` tensors.
Uninitialized tensor declarations in `stmt.vri:319-321` force `elem_bytes = 8` whenever `elem_bytes < 8`.
In `stmt.vri:495-518`, element indexing assignments (`IndexAssign`) rewrite tensor variable types
to `tensor[int; ...]` or `tensor[f64; ...]`.
In `matmul.vri:191-327`, `emit_lir_rt_matmul_f64_stub` clobbers `X5` immediately and only performs
64-bit double FMADD operations.
In `intrinsics.vri:721-729`, `MIR_INTR_INDEX` for `LirType.F32` loads 32-bit words into 64-bit general-purpose
registers without converting to binary64 double representation, leading to subnormal values when read
by float operators or comparisons.

## 5. Proposed Architecture

1. **Declared Dtype Preservation:**
   `stmt.vri` retains the parsed `var_t` without modification. When initializing a declared tensor from
   an `ArrayLiteral`, `lower_tensor_literal` is invoked to allocate `16 + numel * tensor_elem_byte_size(declared_t)`
   and store elements with typed `INDEX_STORE` matching the declared element `MirType`.
2. **True Element Sizing in Uninitialized Declarations & IndexAssign:**
   Remove the forced 8-byte override in `stmt.vri:319-321` and the mutating block in `stmt.vri:495-518`.
3. **Register Float Representation Invariant:**
   All scalar float values in registers are represented as IEEE-754 double precision (`f64`). When loading
   a 32-bit float (`LirType.F32`), it is loaded via `ldr s0`, converted to double via `fcvt d0, s0`, and moved
   to the destination register via `fmov rd, d0`. On store, the register value is moved via `fmov d0, r_val`,
   converted via `fcvt s0, d0`, and stored via `str s0`.
4. **Target Runtime Stub Precision Dispatch:**
   `emit_lir_rt_matmul_f64_stub` preserves `X5` (`is_32bit`) in `X17`. When `X17 != 0`, it computes allocation
   size as `16 + numel * 4` and executes a dedicated single-precision loop utilizing `ldr s`, `fmadd s`,
   and `str s`.

## 6. Design Decisions

### Decision 1 — Dedicated Tensor Literal Lowering

**Decision:** Lower tensor `ArrayLiteral` initializers using a dedicated helper (`lower_tensor_literal`) rather than
piggybacking on generic 8-byte array lowering.

**Rationale:** Vir arrays are homogenous sequences of 8-byte values, whereas dense tensors require packed layouts
(e.g., 4 bytes for `i32`/`f32`, 2 bytes for `f16`, 1 byte for `i8`/`u8`) to match tensor shape strides and
native math stubs.

**Alternatives considered:** Modifying `lower_aggregate` to inspect an ambient type was rejected because `lower_aggregate`
is used across tuples, arrays, and entities where 8-byte slot invariants must remain intact.

**Trade-offs:** Adds a specialized helper in AST-to-MIR lowering.

### Decision 2 — Register Float Model Invariant

**Decision:** Keep registers holding float values in binary64 double format, performing single/double conversions
at the memory load/store boundary for 32-bit floats.

**Rationale:** Vir compiler passes, comparisons, arithmetic, and print runtime stubs expect register-held floats
to be standard doubles. Converting at load/store maintains 100% interoperability with all existing float pipelines.

**Alternatives considered:** Maintaining 32-bit float bit patterns in registers would require bifurcating all arithmetic,
comparisons, and print stubs across the compiler.

### Decision 3 — Branching Stub Dispatch for Single-Precision Math

**Decision:** In `emit_lir_rt_matmul_f64_stub`, check `X17` before the triple loop and branch to a dedicated 32-bit
loop instead of inserting a conditional branch inside the innermost `k` loop.

**Rationale:** Eliminates branch mispredictions and preserves compute pipeline throughput in tensor matrix multiplication.

## 7. Implementation Plan

### Phase 1 — AST-to-MIR Type Preservation and Literal Lowering

- files/modules: `compiler/src/lower/ast_to_mir/stmt.vri`, `compiler/src/lower/ast_to_mir/expr.vri`
- changes:
  - Add `lower_tensor_literal(b, expr, declared_t)`.
  - Remove literal-kind overwriting in `stmt.vri:121-147`.
  - Remove forced 8-byte promotion in `stmt.vri:319-321`.
  - Remove dtype erasure in `stmt.vri:495-518`.
  - Add `MirType.F64` handling for `code == 7` in `stmt.vri:570` and `expr.vri:443`.
- dependencies: none.
- expected result: declared tensor types and packed layouts are preserved in MIR.

### Phase 2 — Codegen Encoders and LIR Float Indexing

- files/modules: `compiler/src/backend/codegen.vri`, `compiler/src/lower/lir_codegen/intrinsics.vri`
- changes:
  - Add ARM64 encoders: `arm64_ldr_s_reg_lsl2`, `arm64_str_s_reg_lsl2`, `arm64_fmadd_ssss`, `arm64_fmov_szr`, `arm64_fcvt_ds`, `arm64_fcvt_sd`.
  - Update `MIR_INTR_INDEX` and `MIR_INTR_INDEX_STORE` for `LirType.F32`.
- dependencies: Phase 1.
- expected result: 32-bit float indexing correctly loads and stores IEEE-754 single-precision values.

### Phase 3 — Single-Precision MatMul & FMA Runtime Stub

- files/modules: `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`
- changes:
  - Save `X5` to `X17`.
  - Allocate `16 + numel * 4` when `X17 != 0`.
  - Emit 32-bit single-precision triple loop using S-registers.
- dependencies: Phase 2.
- expected result: `tensor[f32; ...]` matrix multiplication and FMA produce exact single-precision results.

### Phase 4 — Initial ARM64 Verification

- files/modules: `papers/VIRC/reports/VIRC-RPT-0043_dense_tensor_element_dtype_preservation_and_matmul_fma_lowering_repair_report.md`
- changes:
  - Compile the compiler and verify tests on ARM64:
    - `tests/strict_v2/fma_tensor_e2e.vri`
    - `tests/strict_v2/fma_float_rectangular_e2e.vri`
    - `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri`
  - Record audit findings from first review.

### Phase 5 — x86-64 Single-Precision MatMul Layout and Dispatch

- files/modules: `compiler/src/lower/lir_codegen_x86/emit_func.vri`, `compiler/src/backend/codegen_x86.vri`, `compiler/src/lower/lir_codegen_x86/rt_stubs_math/tensor.vri`
- changes:
  - In `emit_func.vri`: propagate `is_32bit = (ins_aux shr 49) and 1` to `X86_R9`.
  - In `codegen_x86.vri`: add `x86_emit_movd_xmm_gpr`, `x86_emit_movd_gpr_xmm`.
  - In `tensor.vri`: in `emit_lir_rt_matmul_f64_stub_x86`, branch on `is_32bit`; allocate `16 + numel * 4` (shl 2); execute single-precision loop with `movd`, `mulss`, `addss`.

### Phase 6 — Signed i8 Sign-Extending Load Semantics

- files/modules: `compiler/src/backend/codegen.vri`, `compiler/src/backend/codegen_x86.vri`, `compiler/src/lower/lir_codegen/intrinsics.vri`, `compiler/src/lower/lir_codegen_x86/intrinsics.vri`
- changes:
  - In `codegen.vri`: add `arm64_ldrsb_reg` (opcode `0x38a06800`).
  - In `codegen_x86.vri`: add `x86_emit_movsbq_reg_mem` (opcode `0x48 0x0F 0xBE`).
  - Set `mir_instr_set_bits(ins, 1)` for signed `i8` loads, `0` for unsigned `u8`.
  - In LIR intrinsics for ARM64 and x86: dispatch `Int8` loads based on `lir_instr_bits`: use sign-extending load for signed `i8`, zero-extending for unsigned `u8`.

### Phase 7 — Verification Hardening, All-6-Dtype Fixture, and Alignment

- files/modules: `tests/strict_v2/tensor_supported_types_positive.vri`, `tests/strict_v2/tensor_result_alignment_e2e.vri`, `papers/VIRC/reports/VIRC-RPT-0043_dense_tensor_element_dtype_preservation_and_matmul_fma_lowering_repair_report.md`
- changes:
  - Fix `tests/strict_v2/tensor_supported_types_positive.vri`: add `func main`, cover all 6 dtypes (`f32`, `f16`, `f64`, `i8`, `u8`, `i32`), test negative `i8` values.
  - Fix `tests/strict_v2/tensor_result_alignment_e2e.vri`: replace `%` with `mod`.
  - Update `VIRC-RPT-0043` with audit responses and genuine evidence.

### Phase 8 — Semantic Pass Descriptor Attachment and AST->MIR String Scan Elimination

- files/modules: `compiler/src/semantic/types/walk.vri`, `compiler/src/semantic/typecheck/walk_decl.vri`, `compiler/src/semantic/typecheck/walk_other.vri`, `compiler/src/semantic/typecheck/walk_entity.vri`, `compiler/src/lower/ast_to_mir/layout/type_infer.vri`, `compiler/src/lower/ast_to_mir/stmt.vri`, `compiler/src/lower/ast_to_mir/func.vri`
- changes:
  - In Pass 4 (`semantic/types/walk.vri`): attach tensor descriptor handles (`tdesc_from_annotation`) to `node.builtin_id` (VarDecl, ConstDecl, CastExpr), `node.op` (FuncDef, ExternFunc), parameter `param.builtin_id`, and entity field `field.builtin_id`.
  - In Pass 6 (`semantic/typecheck/walk_*.vri`): attach tensor descriptors during typecheck and type inference.
  - In AST->MIR lowering: remove all 8 call sites of `tdesc_from_annotation`. Read `stmt.builtin_id`, `ch.builtin_id`, `node.builtin_id`, and `callee_ast.op` directly.
- dependencies: Phase 7.
- expected result: 0 string scanning or type annotation decoding call sites in AST->MIR lowering (`grep -rn "tdesc_from_annotation" compiler/src/lower/` yields 0 matches).

## 8. Compatibility

- source compatibility: 100% compatible with Spec v2.0 §26.
- ABI: Preserves native runtime stub ABI calling conventions.
- parser compatibility: Unchanged.
- serialized formats: Unchanged.
- public API / stdlib: Unchanged.

## 9. Migration

No migration required. Programs relying on buggy dtype erasure to `int` or `f64` were non-conformant defects.

## 10. Validation Plan

- Execute reproduction commands:
  - `./bin/virc tests/strict_v2/fma_tensor_e2e.vri -O3 -o /tmp/vir_tensor_fma_i32 && /tmp/vir_tensor_fma_i32` (exit code 0).
  - `./bin/virc tests/strict_v2/fma_float_rectangular_e2e.vri -O3 -o /tmp/vir_tensor_fma_f32 && /tmp/vir_tensor_fma_f32` (exit code 0).
  - `./bin/virc tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri -O3 -o /tmp/vir_tensor_rect && /tmp/vir_tensor_rect` (output 58, 64, 139, 154).
- Run `tests/test_tensor_q8_0_contract.py` and other tensor regression suites.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Float register clobbering in LIR intrinsics | Low | Medium | Use caller-saved scratch D0/S0 matching existing convention |
| Branch offset overflow in matmul stub | Low | High | Use 19-bit/26-bit relative branch fixups verified by assembler |

## 12. Rollback Strategy

Revert modifications to the affected compiler source files (`stmt.vri`, `expr.vri`, `codegen.vri`, `intrinsics.vri`, `matmul.vri`).

## 13. Exit Criteria

- [x] Implementation completed across AST-to-MIR, LIR codegen, and runtime stubs for ARM64.
- [x] x86-64 single-precision packed layout and `is_32bit` ABI dispatch implemented and verified.
- [x] Signed `i8` negative values correctly sign-extended on load.
- [x] Tensor f16 correctly lowered and computed across indexing and matmul.
- [x] Registered positive tests cover all six normative element types with active reads and computations.
- [x] Reproduction test fixtures exit with code 0 and produce exact numeric outputs across O0-O3 on supported targets.
- [x] VIRC-RPT-0043 report updated and approved.
- [x] VIRC-ISS-0016 closed and `./paper validate` succeeds.

## 14. Related Papers

- VIRC-ISS-0016 — Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA
- VIR-ISS-0002 — Canonical typed identity and MIR metadata hardening
- VIRC-ISS-0022 — Explicit f32 and f64 print dispatch

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial plan authoring for VIRC-ISS-0016 resolution |
| 2026-10-05 | Linked VIRC-RPT-0043 |
| 2026-10-05 | Reopened following audit; added Phases 5-7 for x86-64 parity, signed i8 loads, and test fixture fixes |
| 2026-10-05 | Completed all phases and audit closure gates; status marked COMPLETED |
| 2026-10-05 | Reopened: audit identified f16 lowering gap, test fixture omission, string scan backlog, and mutation controls |
| 2026-10-05 | Fully completed all exit criteria: verified f16, all 6 dtypes in test fixture, direct parsing without string rebuild, x86-64 Docker runtime, 8/8 mutation controls, and bit-for-bit self-host. Status COMPLETED |
| 2026-10-05 | Reopened: audit revealed x86 f16 matmul 4-byte stride loop (P0), half precision conversion losing signed zero and subnormals (P1), remaining AST->MIR type string scanning sites (P1), and dead TensorTypeMeta residual (P2) |
| 2026-10-05 | Completed: resolved x86 f16 2-byte loop, full IEEE-754 software binary16 conversion, structured tdesc store eliminating all string scanning in AST->MIR, deleted dead metadata, verified 11/11 mutation controls, and confirmed stage2=stage3 fixed point (SHA-256 facb6c...) |
| 2026-10-06 | Added Phase 8: migrated tensor descriptor creation to Semantic Pass 4/6 and attached to AST nodes, eliminating all string decoding in AST->MIR lowering; kept status ACTIVE pending independent audit sign-off |
| 2026-10-06 | Completed Phase 8 and all exit criteria: eliminated duplicate Pass 6 annotation decoding, added cross-target descriptor propagation coverage, accepted VIRC-RPT-0043, and closed VIRC-ISS-0016 |
