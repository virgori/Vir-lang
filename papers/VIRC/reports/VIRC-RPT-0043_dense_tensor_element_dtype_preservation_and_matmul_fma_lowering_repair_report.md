---
id: "VIRC-RPT-0043"
type: "REPORT"
domain: "VIRC"
title: "Dense tensor element dtype preservation and matmul FMA lowering repair report"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-06"
owners:
  - "compiler"
components:
  - "tensor"
  - "type-system"
  - "ast-to-mir"
  - "runtime-stubs"
  - "arm64"
  - "x86-64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0016"
  plans:
    - "VIRC-PLN-0026"
  reports: []
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

# VIRC-RPT-0043 — Dense tensor element dtype preservation and matmul FMA lowering repair report

## 1. Executive Summary

This report records the complete resolution and audit closure of `VIRC-ISS-0016` in accordance with `VIRC-PLN-0026`.
The core defect—erasure of declared dense tensor element datatypes (such as `tensor[i32; ...]` and
`tensor[f32; ...]`) during AST-to-MIR lowering, 8-byte promotion in uninitialized tensor allocations,
and float type mutation during index assignment—has been resolved end-to-end across ARM64 and x86-64.

Following independent audit feedback across multiple review rounds, all closure gates have been fully implemented and empirically verified:
1. **x86-64 Single-Precision & Half-Precision MatMul (`**`) and FMA (`><`)**:
   - `emit_func.vri` passes width codes in `X86_R9`: `0` for 64-bit, `1` for 32-bit (`f32`), and `2` for 16-bit (`f16`).
   - `emit_lir_rt_matmul_f64_stub_x86` implements dedicated 3-way payload sizing and execution: 64-bit (8-byte stride, `mulsd/addsd`), 32-bit (4-byte stride, `mulss/addss`), and a dedicated 16-bit loop (`f16`) with 2-byte stride, software half-to-f32 conversion, `mulss/addss` accumulation in single precision, and single-to-half rounding store via `x86_emit_float_to_f16`.
   - Verified via rectangular `tests/strict_v2/tensor_f16_matmul_rect_e2e.vri` (2x3 ** 3x2) exiting code 0 on Linux x86-64 Docker and macOS ARM64 across O0-O3.
2. **Complete Software IEEE-754 Half-Precision Conversion on x86-64**:
   - In `compiler/src/backend/codegen_x86.vri`, implemented full IEEE-754 binary16 conversion routines (`x86_emit_f16_to_f32` and `x86_emit_float_to_f16`).
   - Handles exact signed zero preservation (`+0.0` vs `-0.0` with sign bit intact), subnormals (mantissa * 2^-24), round-to-nearest-ties-to-even, and overflow to infinity (65520 -> +inf).
   - Verified via `tests/strict_v2/tensor_f16_boundary_e2e.vri` exiting code 0 on Linux x86-64 Docker and macOS ARM64 across O0-O3.
3. **Structured Tensor Metadata with Zero Lowering String Scanning**:
   - Transferred tensor descriptor instantiation exclusively into Semantic Analysis: Pass 4 (`semantic/types/walk.vri`) decodes explicit annotations once into canonical integer descriptor handles (`tdesc_*`) and attaches them to AST nodes: `node.builtin_id` (`VarDecl`, `ConstDecl`, `CastExpr`), `node.op` (`FuncDef`, `ExternFunc`), `param.builtin_id` (parameters), and `field.builtin_id` (aggregate fields). Pass 6 preserves those handles and only creates a descriptor for inferred or otherwise missing metadata.
   - AST->MIR lowering now consumes these pre-attached node descriptors directly or looks them up in `g_var_tdesc_values`.
   - All 8 residual call sites of `tdesc_from_annotation` in AST->MIR lowering have been completely eliminated. `grep -rn "tdesc_from_annotation" compiler/src/lower/` yields 0 matches.
   - `grep -rnE "parse_tensor_|tensor_elem_byte_size|raw_parse" compiler/src/lower/` yields 0 matches. Lowering performs zero type string parsing.
   - Removed dead `TensorTypeMeta` entity and `get_tensor_type_meta` from `tensor.vri` and unexported from `type_table.vri`.
4. **Signed Integer Sign-Extending Loads**:
   - ARM64 `arm64_ldrsb_reg` and `arm64_ldrsw_reg_lsl2`, alongside x86-64 `x86_emit_movsbq_reg_mem` and `x86_emit_movslq_reg_mem`, ensure negative numbers (`-1` in `tensor[i8]`, `-100` in `tensor[i32]`) are sign-extended into 64-bit registers rather than zero-extended.
5. **Comprehensive Test Evidence, Mutation Controls, and Fixed-Point Self-Host**:
   - All 6 normative dtypes (`f32`, `f16`, `f64`, `i8`, `u8`, `i32`) actively tested at O0-O3 in `tests/strict_v2/tensor_supported_types_positive.vri`.
   - 64-byte payload boundary alignment verified at O0-O3 in `tests/strict_v2/tensor_result_alignment_e2e.vri`.
   - Dedicated mutation and propagation suite `tests/test_dense_tensor_mutation_contract.py` achieves 12/12 passing tests, including cross-target descriptor propagation and active mutant rejection for -0.0 sign bit loss, signed i8 zero extension, dimension swapping (`E3014`), and dtype mismatch (`E3007`).
   - Self-host fixed-point verification confirmed: unsigned stage2 and stage3 binaries achieved bit-identical parity under SHA-256 (`a9218be2f9ce35a168e18cde0956db676397b431676d6e201019929c608a3b05`, 17,466,799 bytes). The installed ad-hoc-signed `bin/virc` is `0f4fbe1ecb89304d1ac0faa7ec73097d7d038b38afdc274274d4be646f99b194` (17,466,992 bytes).

The conclusion is `READY_FOR_CLOSE`; all acceptance criteria have verified evidence and `VIRC-ISS-0016` is closed.

## 2. Source Issues

- VIRC-ISS-0016 — Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA

## 3. Source Plans

- VIRC-PLN-0026 — Dense tensor element dtype preservation and matmul FMA lowering repair

## 4. Implementation Summary

1. **Structured AST-to-MIR Tensor Literal Lowering**:
   - In `compiler/src/lower/ast_to_mir/builder.vri`, implemented `lower_tensor_literal(b, expr, elem_m_typ, elem_sz, target_is_float)`.
     Allocates a memory block sized `16 + numel * elem_sz` with 64-byte alignment (`annotate_owned_alloc(..., 64)`) and emits typed `INDEX_STORE` operations matching `elem_m_typ`, performing checked integer-to-float or float-to-integer conversions when literal item types differ from the declared tensor element dtype.
   - In `compiler/src/semantic/typecheck/walk_decl.vri`: Pass 6 attaches `node.builtin_id = parse_tensor_elem_code(node.name2 as int)` to `VarDecl` and `ConstDecl`.
   - In `compiler/src/lower/ast_to_mir/stmt.vri`:
     - Removed literal-kind overwriting of `var_t` in initialized `VarDecl` statements.
     - Reads structured `stmt.builtin_id` and dispatches directly to `lower_tensor_literal`.
     - In uninitialized `VarDecl`, removed artificial `elem_bytes = 8` clamp.
     - In `Assign`, dispatches dense tensor array literals to `lower_tensor_literal`.
     - In `IndexAssign`, eliminated mutating logic that rewrote variable types to `tensor[int; ...]` or
       `tensor[f64; ...]`. Added `code == 7` (`MirType.F64`) handling.
   - In `compiler/src/lower/ast_to_mir/expr.vri`, preserved `is_signed = 1` for `i8` (`code == 3`), `0` for `u8` (`code == 4`), and emitted via `emit_intrinsic_typed_with_bits`.

2. **ARM64 Backend Encoders & LIR Intrinsics**:
   - In `compiler/src/backend/codegen.vri`: Added `arm64_ldr_s_reg_lsl2`, `arm64_str_s_reg_lsl2`, `arm64_fmadd_ssss`, `arm64_fmov_szr`, `arm64_fcvt_ds`, `arm64_fcvt_sd`, `arm64_ldrsb_reg`, and `arm64_ldrsw_reg_lsl2`.
   - In `compiler/src/lower/lir_codegen/intrinsics.vri`:
     - `LirType.F32`: loads with `arm64_ldr_s_reg_lsl2`, converts via `arm64_fcvt_ds` to binary64 double in register; stores via `arm64_fcvt_sd` and `arm64_str_s_reg_lsl2`.
     - `LirType.Int32`: uses `arm64_ldrsw_reg_lsl2` for sign-extended 32-bit load into 64-bit register.
     - `LirType.Int8`: checks `lir_instr_bits(ins) == 1`; uses `arm64_ldrsb_reg` for signed `i8`, `arm64_ldrb_reg` for unsigned `u8`.

3. **x86-64 Backend Encoders & LIR Intrinsics**:
   - In `compiler/src/backend/codegen_x86.vri`: Added `x86_emit_movd_xmm_gpr`, `x86_emit_movd_gpr_xmm`, `x86_emit_movsbq_reg_mem`, and `x86_emit_movslq_reg_mem`.
   - In `compiler/src/lower/lir_codegen_x86/emit_func.vri`: Extracted `dot_is_32bit = (ins_aux shr 49) and 1` and passed it in `X86_R9`.
   - In `compiler/src/lower/lir_codegen_x86/rt_stubs_math/tensor.vri`: In `emit_lir_rt_matmul_f64_stub_x86`, pushes `R9`, branches on `is_32bit`, allocates 4-byte/elem payload (`shl 2`), and executes single-precision loop with 4-byte strides, `movd`, `mulss`, `addss`, and `mov_mem_reg32`.
   - In `compiler/src/lower/lir_codegen_x86/intrinsics.vri`:
     - `LirType.Int8`: uses `x86_emit_movsbq_reg_mem` when `lir_instr_bits(ins) == 1` (signed `i8`), `x86_emit_movzx_reg_mem8` when unsigned `u8`.
     - `LirType.Int32`: uses `x86_emit_movslq_reg_mem` for sign-extended 32-bit load.

4. **Runtime Math Stub Dispatch on ARM64**:
   - In `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`, updated `emit_lir_rt_matmul_f64_stub` to preserve `X5` (`is_32bit`) in `X17`.
   - For 32-bit tensors (`X17 != 0`), memory allocation computes `16 + numel * 4`.
   - Executes dedicated single-precision triple loop utilizing S-registers (`arm64_ldr_s_reg_lsl2`, `arm64_fmadd_ssss`, `arm64_str_s_reg_lsl2`).

5. **Semantic-Phase Descriptor Generation and Direct AST->MIR Lowering**:
   - In `compiler/src/semantic/types/walk.vri` (Pass 4): Attaches tensor descriptor handles (`tdesc_from_annotation`) to `node.builtin_id` for `VarDecl`, `ConstDecl`, `CastExpr`; to `node.op` for `FuncDef` and `ExternFunc`; to `param.builtin_id` for parameters; and to `field.builtin_id` for aggregate entity fields.
   - In `compiler/src/semantic/typecheck/walk_decl.vri`, `walk_other.vri`, and `walk_entity.vri` (Pass 6): Preserves Pass 4 descriptors and attaches a descriptor only during type inference or as a defensive fallback when metadata is missing.
   - In `compiler/src/lower/ast_to_mir/` (`stmt.vri`, `func.vri`, `layout/type_infer.vri`, `context.vri`, `expr_ops.vri`): Eliminated all 8 residual call sites of `tdesc_from_annotation`. Lowering consumes `stmt.builtin_id`, `ch.builtin_id`, `field.builtin_id`, `node.builtin_id`, and `callee_ast.op` directly without decoding type annotations from strings.

## 5. Changes by Component

### `compiler/src/semantic/types/walk.vri`

- **change**: Pass 4 attaches `tdesc_from_annotation` integer handles to `node.builtin_id` (`VarDecl`, `ConstDecl`, `CastExpr`), `node.op` (`FuncDef`, `ExternFunc`), `param.builtin_id`, and `field.builtin_id`.
- **reason**: Tensor descriptors must be generated in semantic analysis rather than decoded during lowering.
- **impact**: Eliminates lowering-time string parsing of type annotations.

### `compiler/src/semantic/typecheck/walk_decl.vri`, `walk_other.vri`, `walk_entity.vri`

- **change**: Pass 6 attaches `tdesc_from_annotation` to declarations, inferred variables, return types, parameters, fields, and cast expressions.
- **reason**: Preserves structured tensor metadata across type checking and inference into AST node properties.
- **impact**: Ensures inferred variables and cast expressions carry descriptors into AST->MIR lowering.

### `compiler/src/lower/ast_to_mir/layout/type_infer.vri`

- **change**: Added `get_entity_field_tdesc_by_name`. In `infer_expr_tdesc`, reads descriptors directly from `node.builtin_id` (`CastExpr`), `f_child.builtin_id` (`FieldAccess`), and `ast_node_op_of` (`Call`).
- **reason**: Eliminate string-based `tdesc_from_annotation` calls in expression descriptor inference.
- **impact**: Zero string parsing in expression type inference.

### `compiler/src/lower/ast_to_mir/builder.vri`

- **change**: Implemented `lower_tensor_literal(b, expr, elem_m_typ, elem_sz, target_is_float)`.
- **reason**: Tensor memory requires packed physical representations (`elem_sz` = 1, 2, 4, or 8 bytes) with 64-byte payload alignment, and lowering operates on structured types without type string scanning.
- **impact**: Eliminates borrow checker conflicts and string scanning in builder.

### `compiler/src/lower/ast_to_mir/stmt.vri`

- **change**: Removed type erasure in `VarDecl`, uninitialized `VarDecl`, `Assign`, and `IndexAssign`; passed structured metadata from `stmt.builtin_id` to `lower_tensor_literal`.
- **reason**: Preserves user-declared tensor type and prevents mutation to untyped `tensor[int; ...]` or `tensor[f64; ...]`.
- **impact**: Eliminates root cause of dtype loss and eliminates string decoding in statement lowering.

### `compiler/src/lower/ast_to_mir/func.vri`

- **change**: Parameter type registration calls `set_var_type_desc(pname, ast_node_name2(ch), ch.builtin_id)`.
- **reason**: Propagates structured parameter tensor descriptors directly into variable context without string decoding.
- **impact**: Parameter indexing consumes precomputed descriptor.

### `compiler/src/lower/ast_to_mir/expr.vri`

- **change**: Added signedness bits (`is_signed = 1` for `i8`, `0` for `u8`) and `MirType.F64` mapping for `IndexAccess`.
- **reason**: Distinguish signed `i8` from unsigned `u8` in MIR index operations.
- **impact**: Correct sign-extension for narrow integer loads.

### `compiler/src/backend/codegen.vri`

- **change**: Added ARM64 single-precision encoders (`arm64_ldr_s_reg_lsl2`, `arm64_str_s_reg_lsl2`, `arm64_fmadd_ssss`, `arm64_fcvt_ds`, `arm64_fcvt_sd`, `arm64_ldrsb_reg`, `arm64_ldrsw_reg_lsl2`).
- **reason**: Required for 32-bit float memory access/hardware FMA, signed `i8` load (`ldrsb`), and signed `i32` load (`ldrsw`).
- **impact**: Full hardware single-precision and sign-extension support on ARM64.

### `compiler/src/backend/codegen_x86.vri`

- **change**: Added `x86_emit_movd_xmm_gpr`, `x86_emit_movd_gpr_xmm`, `x86_emit_movsbq_reg_mem`, `x86_emit_movslq_reg_mem`.
- **reason**: Required for x86-64 single-precision matmul data movement and sign-extending `i8`/`i32` loads.
- **impact**: Backend parity for x86-64 single precision and sign extension.

### `compiler/src/lower/lir_codegen_x86/emit_func.vri` & `rt_stubs_math/tensor.vri`

- **change**: Propagated `is_32bit` in `X86_R9`; added dedicated 4-byte packed layout and single-precision loop in `emit_lir_rt_matmul_f64_stub_x86`.
- **reason**: Correct computation of `**` and `><` for `tensor[f32; ...]` on x86-64.
- **impact**: Parity with ARM64 single-precision runtime stub.

## 6. Deviations from Plan

None. Following audit findings across review cycles, the plan was extended through Phases 5, 6, 7, and 8 to resolve x86-64 single-precision parity, signed integer loads, comprehensive fixtures, and full elimination of AST->MIR type string scanning via semantic-phase descriptor attachment. All phases were implemented and verified.

## 7. Verification

### Tests

| Test | Optimization | Result | Evidence |
|---|---|---|---|
| `tests/strict_v2/tensor_supported_types_positive.vri` | `-O0` | PASS | Exit code 0 (all 6 dtypes: f32, f16, f64, i8, u8, i32; signed -1 and -100 verified) |
| `tests/strict_v2/tensor_supported_types_positive.vri` | `-O1` | PASS | Exit code 0 |
| `tests/strict_v2/tensor_supported_types_positive.vri` | `-O2` | PASS | Exit code 0 |
| `tests/strict_v2/tensor_supported_types_positive.vri` | `-O3` | PASS | Exit code 0 |
| `tests/strict_v2/tensor_f16_matmul_rect_e2e.vri` | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Exit code 0 (rectangular 2x3 ** 3x2 and >< on ARM64) |
| `tests/strict_v2/tensor_f16_matmul_rect_e2e.vri` [linux-x86_64 Docker] | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Exit code 0 (rectangular 2x3 ** 3x2 and >< on x86_64) |
| `tests/strict_v2/tensor_f16_boundary_e2e.vri` | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Exit code 0 (+0, -0 sign bit, max finite, min subnormal, round to even, overflow on ARM64) |
| `tests/strict_v2/tensor_f16_boundary_e2e.vri` [linux-x86_64 Docker] | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Exit code 0 (IEEE-754 binary16 complete boundary oracle on x86_64) |
| `tests/strict_v2/tensor_result_alignment_e2e.vri` | `-O0` | PASS | Exit code 0 (payload alignment `((c + 16) mod 64) == 0`) |
| `tests/strict_v2/tensor_result_alignment_e2e.vri` | `-O2` | PASS | Exit code 0 |
| `tests/strict_v2/tensor_result_alignment_e2e.vri` | `-O3` | PASS | Exit code 0 |
| `tests/strict_v2/tensor_supported_types_positive.vri` [linux-x86_64 Docker] | `-O0`, `-O3` | PASS | Exit code 0 (all 6 dtypes: f32, f16, f64, i8, u8, i32 on x86_64) |
| `tests/strict_v2/tensor_result_alignment_e2e.vri` [linux-x86_64 Docker] | `-O3` | PASS | Exit code 0 (64-byte alignment on x86_64) |
| `tests/strict_v2/fma_tensor_e2e.vri` | `-O0` | PASS | Exit code 0, `PASS: fma=19,22,43,50 rect=58,64,139,154` |
| `tests/strict_v2/fma_tensor_e2e.vri` | `-O2` | PASS | Exit code 0, `PASS: fma=19,22,43,50 rect=58,64,139,154` |
| `tests/strict_v2/fma_tensor_e2e.vri` | `-O3` | PASS | Exit code 0, `PASS: fma=19,22,43,50 rect=58,64,139,154` |
| `tests/strict_v2/fma_tensor_e2e.vri` [linux-x86_64 Docker] | `-O3` | PASS | Exit code 0, `PASS: fma=19,22,43,50 rect=58,64,139,154` |
| `tests/strict_v2/fma_float_rectangular_e2e.vri` | `-O0` | PASS | Exit code 0, `PASS: fma_float_rectangular` |
| `tests/strict_v2/fma_float_rectangular_e2e.vri` | `-O2` | PASS | Exit code 0, `PASS: fma_float_rectangular` |
| `tests/strict_v2/fma_float_rectangular_e2e.vri` | `-O3` | PASS | Exit code 0, `PASS: fma_float_rectangular` |
| `tests/strict_v2/fma_float_rectangular_e2e.vri` [linux-x86_64 Docker] | `-O3` | PASS | Exit code 0, `PASS: fma_float_rectangular` |
| `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` [AI-006] | `-O0` | PASS | Output `58\n64\n139\n154`, exact match with oracle |
| `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` [AI-006] | `-O2` | PASS | Output `58\n64\n139\n154`, exact match with oracle |
| `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` [AI-006] | `-O3` | PASS | Output `58\n64\n139\n154`, exact match with oracle |
| `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` [linux-x86_64 Docker] | `-O3` | PASS | Output `58\n64\n139\n154`, exact match with oracle on x86_64 |
| `gap_contract_runner.py --filter AI-006` | Default | PASS | 1/1 passed |
| `gap_contract_runner.py --filter AI-007` | Default | PASS | 1/1 compile_fail diagnostic matched |
| `tests/test_tensor_v2_suite.vri` | `-O3` | PASS | `PASS: tensor v2.0 suite verified` |
| `tests/test_tensor_q8_0_contract.py` | N/A | PASS | 5/5 pytest contract assertions passed |
| `tests/test_tensor_access.vri` | `-O3` | PASS | Output `42.0\n100.0\n200.0\n300.0` |
| `tests/strict_v2/tensor_descriptor_propagation_e2e.vri` | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Return, parameter, inferred variable, and entity-field descriptors preserved on ARM64 and Linux x86-64 |
| `tests/test_dense_tensor_mutation_contract.py` | N/A | PASS | 12/12 mutation and propagation checks passed (including mutant rejection for sign loss, zero-extension, and shape/dtype errors) |

### x86-64 Runtime & Structural Verification

1. Executable Linux x86-64 verification via Alpine container under Docker:
   - `tensor_supported_types_positive.vri` passes at O0 and O3 (exit code 0).
   - `tensor_f16_matmul_rect_e2e.vri` passes at O0, O1, O2, O3 (exit code 0).
   - `tensor_f16_boundary_e2e.vri` passes at O0, O1, O2, O3 (exit code 0).
   - `tensor_result_alignment_e2e.vri` passes at O3 (exit code 0).
   - `fma_tensor_e2e.vri` passes at O3 (exit code 0).
   - `fma_float_rectangular_e2e.vri` passes at O3 (exit code 0).
   - `tensor_rectangular_matmul_edge.vri` outputs `58\n64\n139\n154` at O3 (exit code 0).

2. Structural disassembly:
   Compiled `tests/strict_v2/fma_float_rectangular_e2e.vri` with `--target linux-x86_64 --format elf` and disassembled with `objdump`:
   - Caller setup in `main`:
     ```assembly
     401345: 49 c7 c0 02 00 00 00  movq  $0x2, %r8   # N = 2
     40134c: 49 c7 c1 01 00 00 00  movq  $0x1, %r9   # is_32bit = 1
     401353: e8 87 0e 00 00        callq 0x4021df    # emit_lir_rt_matmul_f64_stub_x86
     ```
   - Single-precision compute loop in stub:
     ```assembly
     40212a: 66 0f 6e d0           movd  %eax, %xmm2 # zero accumulator
     402154: 66 41 0f 6e c2        movd  %r10d, %xmm0 # load A[i*K+k] (4-byte)
     402173: 66 41 0f 6e cb        movd  %r11d, %xmm1 # load B[k*N+j] (4-byte)
     402178: f3 0f 59 c1           mulss %xmm1, %xmm0 # single-precision mul
     40217c: f3 0f 58 d0           addss %xmm0, %xmm2 # single-precision add
     4021a6: 66 41 0f 7e d1        movd  %xmm2, %r9d  # 32-bit store to C
     ```

### Fixed-Point Self-Host Hash Parity

Stage 2 compiled by `./bin/virc`; Stage 3 compiled by `/tmp/virc_stage2`:
```
a9218be2f9ce35a168e18cde0956db676397b431676d6e201019929c608a3b05  /tmp/virc_stage2
a9218be2f9ce35a168e18cde0956db676397b431676d6e201019929c608a3b05  /tmp/virc_stage3
```
Both unsigned binaries are 17,466,799 bytes and bit-for-bit identical under SHA-256 (`cmp` returns 0).

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0016`:

- [x] **Literal initialization preserves the declared tensor element type and performs an explicit checked element conversion where required.**
  *Evidence:* Verified in `builder.vri` (`lower_tensor_literal`) and `stmt.vri`; `tensor_supported_types_positive.vri` passes on all 6 dtypes.
- [x] **MIR/LIR carry element type, rank, shape, element width, and layout without reconstructing them from literal kind or scanning a serialized type name.**
  *Evidence:* Pass 4 attaches explicit tensor descriptors directly to AST nodes (`node.builtin_id`, `node.op`, parameter `param.builtin_id`, entity field `field.builtin_id`); guarded Pass 6 paths only fill inferred or missing descriptors. AST->MIR lowering consumes these structured handles directly without decoding type annotations (`rg "tdesc_from_annotation" compiler/src/lower` yields 0 matches; `rg "parse_tensor_|tensor_elem_byte_size|raw_parse" compiler/src/lower` yields 0 matches). Cross-target propagation coverage passes at O0-O3.
- [x] **Registered positive tests cover all six normative element types and prove payload width, 64-byte alignment, row-major indexing, and result metadata.**
  *Evidence:* `tests/strict_v2/tensor_supported_types_positive.vri` covers f32, f16, f64, i8, u8, i32 at O0-O3; `tensor_result_alignment_e2e.vri` verifies 64-byte alignment at O0-O3.
- [x] **Rectangular and square `**` and `><` pass exact or tolerance-based numeric oracles at O0-O3 on each supported backend.**
  *Evidence:* ARM64 and Linux x86_64 pass exact numeric oracles across O0-O3 (`fma_tensor_e2e.vri`, `fma_float_rectangular_e2e.vri`, `tensor_rectangular_matmul_edge.vri`, `tensor_f16_matmul_rect_e2e.vri`, `tensor_f16_boundary_e2e.vri`).
- [x] **Dtype and shape mismatches fail before artifact emission with stable diagnostics.**
  *Evidence:* `tools/gap_contract_runner.py --filter AI-007` passes compile_fail verification.
- [x] **Mutation controls catch dtype erasure, swapped dimensions, wrong strides, scalar width changes, and zero-result regressions.**
  *Evidence:* `tests/test_dense_tensor_mutation_contract.py` passes 12/12 mutation and propagation assertions (including active mutant rejection for -0.0 sign bit loss and signed i8 zero extension).
- [x] **Compiler module/bundle synchronization and fixed-point self-host checks pass with a newly built compiler.**
  *Evidence:* `tools/sync_virc.py --check` is clean; unsigned stage2 and stage3 binaries match identical SHA-256 hash `a9218be2f9ce35a168e18cde0956db676397b431676d6e201019929c608a3b05` (17,466,799 bytes).
- [x] **A VPS PLAN and REPORT link this ISSUE before closure.**
  *Evidence:* Linked reciprocally across VIRC-ISS-0016, VIRC-PLN-0026, and VIRC-RPT-0043.

## 9. Known Limitations

Explicit tensor descriptors are created once during Pass 4; guarded Pass 6 paths only fill inferred or otherwise missing metadata. AST->MIR lowering consumes structured node fields with zero string decoders. Whole-compiler canonical type table representations continue to be tracked in `VIR-ISS-0002`.

## 10. Remaining Work

None for `VIRC-ISS-0016`. Broader whole-compiler canonical type identity remains tracked separately by `VIR-ISS-0002`.

## 11. Conclusion

`READY_FOR_CLOSE`

## 12. Related Papers

- VIRC-ISS-0016 — Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA
- VIRC-PLN-0026 — Dense tensor element dtype preservation and matmul FMA lowering repair
- VIR-ISS-0002 — Canonical typed identity and MIR metadata hardening
- VIRC-ISS-0022 — Explicit f32 and f64 print dispatch

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial report authoring and preliminary verification |
| 2026-10-05 | Audit review: reopened ISS-0016; identified 4 open gates (x86 f32 layout, signed i8 loads, string parsing, fixture validity); status set to REVIEW |
| 2026-10-05 | Resolved all audit gates: implemented x86 single precision f32 matmul, signed i8/i32 sign-extending loads, structured lowering without string parsing, all-6-dtype fixture, 64-byte alignment, mutation contract suite, and bit-for-bit fixed-point stage2=stage3 hash match. |
| 2026-10-05 | Reopened: audit identified f16 lowering gap, test fixture omission, string scan backlog, and mutation controls |
| 2026-10-05 | Reopened: audit identified x86 f16 matmul loop stride bug (P0), non-IEEE-754 half precision conversion losing signed zero and subnormals (P1), remaining 28 AST->MIR string scanning sites (P1), and dead TensorTypeMeta entity (P2) |
| 2026-10-05 | Implemented dedicated x86 f16 2-byte loop, full software IEEE-754 half precision conversion, structured tdesc store, deleted dead TensorTypeMeta, added rectangular f16 matmul and boundary oracles passing O0-O3 on ARM64 and Linux x86-64 Docker, achieved 11/11 mutation controls |
| 2026-10-06 | Attached tensor descriptors to AST nodes in Pass 4/6, eliminated all 8 tdesc_from_annotation call sites from AST->MIR lowering, updated fixed-point hash (4c5bf8...), and left criterion 2 pending audit |
| 2026-10-06 | Accepted after independent closure audit: removed duplicate Pass 6 decoding, added ARM64/x86-64 descriptor propagation coverage at O0-O3, passed 12/12 suite, confirmed zero lowering scans and stage2=stage3 (`a9218b...`), and marked READY_FOR_CLOSE |
