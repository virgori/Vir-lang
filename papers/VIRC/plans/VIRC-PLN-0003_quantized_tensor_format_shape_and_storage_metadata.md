---
id: "VIRC-PLN-0003"
type: "PLAN"
domain: "VIRC"
title: "Quantized tensor format shape and storage metadata"
status: "COMPLETED"
created: "2026-10-02"
updated: "2026-10-05"
owners:
  - "compiler"
  - "stdlib"
components:
  - "type-system"
  - "semantic-analysis"
  - "mir"
  - "lir"
  - "tensor"
  - "quantization"
  - "infer"
  - "external-storage"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0005"
  plans: []
  reports:
    - "VIRC-RPT-0035"
supersedes: null
superseded_by: null
tags:
  - "quantized-tensor"
  - "q8-0"
  - "packed-storage"
  - "dtype"
  - "shape"
  - "typed-dispatch"
---

# VIRC-PLN-0003 — Quantized tensor format shape and storage metadata

## 1. Objective

Deliver internal first-class quantized tensor metadata (format/codec, logical element type,
rank, shape, physical block elements/bytes, row byte strides, alignment, mutability, and
borrowed external storage facts) across semantic analysis, MIR, and LIR; enable
compiler-directed Q8_0 and uniform quantized operation verification/dispatch inside `infer:`;
and preserve dense tensor and generic `quantize(..., bits: N)` contracts without modifying
language syntax.

## 2. Source Issues

- VIRC-ISS-0005 — Quantized tensors lack format, shape, and storage metadata.

## 3. Scope

### In Scope

- Target-neutral internal quantized tensor descriptor and structured type string in
  `stdlib/vir/compiler/type_table.vri`:
  - Codec classification: `GenericUniform` (bits 4, 8, 16, 32) vs `Q8_0` (canonical 40-byte block: f64-le scale + int8[32]);
  - Logical element type (`f32`, `f64`), rank, static shape dimensions;
  - Physical block elements (32 for Q8_0, 1 for uniform), physical block bytes (40 for Q8_0), row byte stride, and byte alignment (8 for Q8_0);
  - Mutability (`readOnly: true`), ownership kind (`OWNERSHIP_BORROWED`), and generation lifetime cell.
- Semantic analysis (`stdlib/vir/compiler/sem_pass6_typecheck.vri`):
  - Propagate input tensor shape, dtype, and bit width on `quantize(tensor, bits: N)` instead of collapsing to flat `"QuantizedTensor"`;
  - Recognize `Q80TensorView` entity as carrying canonical Q8_0 packed metadata;
  - Enforce typed dispatch and validation on Q8_0 GEMV/GEMM operations: check activation dtype, shape compatibility (activationLength == columns, outputLength >= rows), and layout;
  - Reject implicit conversion between generic 8-bit uniform quantization and 40-byte Q8_0 format;
  - Permit and type-check uniform quantized matmul (`compact ** input`) within `infer:`.
- MIR lowering & preservation (`stdlib/vir/compiler/ast_to_mir.vri`):
  - Retain quantized metadata across variable bindings, assignments, and calls;
  - Annotate `MIR_INTR_QUANTIZE`, `MirOp.MatMul`, and packed calls with complete codec, shape, and block aux metadata;
  - Ensure MIR optimization passes preserve packed metadata without loss.
- LIR lowering & codegen (`stdlib/vir/compiler/lir_lower.vri`, `stdlib/vir/compiler/lir_codegen.vri`, `stdlib/vir/compiler/lir_codegen_x86.vri`):
  - Lower uniform quantized matmul in `infer:` to exact scaled numerical output, resolving the AI-001 and AI-003 baseline failures;
  - Direct Q8_0 dispatch to verified scalar/SIMD kernels without untyped fallback, and emit stable diagnostic on unsupported targets (e.g. Wasm);
  - Add deterministic semantic, MIR, and LIR dump inspection (`--dump-semantic`, `--dump-mir`, `--dump-lir`) proving metadata survival across stages.
- Verification and test suite:
  - Stable negative tests for activation dtype, shape mismatch, output length mismatch, and format reinterpretation;
  - Contract tests: AI-001, AI-003, AI-006, Q80-001 all green;
  - Modular compiler source synchronization and self-host compiler build.

### Out of Scope

- Changing canonical Vir language syntax or modifying `papers/VIR/specs/**` (Spec Freeze invariant);
- Introducing unapproved public syntax for quantized tensor types;
- Additional quantization schemes beyond Generic Uniform and 40-byte Q8_0;
- Modification of Gemma-Vir serialization formats.

## 4. Current Architecture

CONFIRMED on 2026-10-02:

- `TypeKind.QuantizedTensor = 22` is an undifferentiated compiler kind in `type_table.vri`.
- `sem_pass6_typecheck.vri` temporarily inspects the input AST node during `quantize` validation, but records the variable type as the flat string `"QuantizedTensor"`.
- `ast_to_mir.vri` sets variable types to `"QuantizedTensor"`, discarding shape, rank, element type, and physical storage parameters.
- `compact ** input` fails semantic analysis ([E3002], [E3014]) because `QuantizedTensor` is not recognized as having rank-2 matrix dimensions, causing baseline failures in AI-001 and AI-003.
- `stdlib/vir/math/tensor_q8_0.vri` defines `Q80TensorView` with full runtime validation fields (base, byteLength, byteOffset, viewByteLength, storageKind, rank, rows, columns, rowStrideBytes, alignment, readOnly, ownershipKind, generationCell, generation), but compiler IR treats `Q80TensorView` as a generic user entity with no compiler-directed packed dispatch.

## 5. Proposed Architecture

### 5.1 Internal Quantized Type Representation

In `stdlib/vir/compiler/type_table.vri`:
- Define `QuantizedCodec`:
  - `Q_CODEC_NONE = 0`
  - `Q_CODEC_UNIFORM = 1`
  - `Q_CODEC_Q8_0 = 2`
- Define structured type string format:
  - Uniform: `"quantized[uniform; elem=f32; bits=8; 2, 2]"`
  - Q8_0: `"quantized[q8_0; elem=f64; shape=2, 32; block=40; stride=40; align=8; bytes=80; offset=0; view=80; ro=1; own=0; life=1; generation=1]"`
- Add helper functions:
  - `is_quantized_type_str(s: int) -> bool`
  - `parse_quantized_codec(s: int) -> int`
  - `parse_quantized_elem_type(s: int) -> TypeKind`
  - `parse_quantized_bits(s: int) -> int`
  - `parse_quantized_shape(s: int) -> int` (returns vec_rt of dimensions)
  - `parse_quantized_rank(s: int) -> int`
  - `parse_quantized_block_elements(s: int) -> int`
  - `parse_quantized_block_bytes(s: int) -> int`
  - `parse_quantized_stride_bytes(s: int) -> int`
  - `parse_quantized_alignment(s: int) -> int`
  - `parse_quantized_read_only(s: int) -> bool`
  - `parse_quantized_ownership_kind(s: int) -> int`
  - `parse_quantized_has_lifetime(s: int) -> bool`
  - `format_quantized_uniform_type(...) -> string`
  - `format_quantized_q80_type(...) -> string`

### 5.2 Semantic Validation and Dispatch

In `stdlib/vir/compiler/sem_pass6_typecheck.vri`:
- In `pass6_walk` on `AstType.QuantizeExpr`:
  - Capture input tensor type name `q_tensor_name` and shape `shape_vec`.
  - Record the resulting expression type as `format_quantized_uniform_type(elem_type, bits, shape_vec)`.
- When initializing a variable from `QuantizeExpr`:
  - Propagate this structured type name to `pass6_set_var_type`.
- When initializing or typing `Q80TensorView`:
  - Associate with `format_quantized_q80_type(rows, cols, stride, align, ...)`.
- On `MatMulOp` (`compact ** input`):
  - If `left` is `is_quantized_type_str`:
    - Ensure inside `infer:` (`g_pass6_ai_mode == 1`). If outside, report [E3023].
    - Extract shape from quantized type string; check dimension compatibility `K_a == K_b`.
    - Allow uniform quantized matmul.
- On `q80Gemv` / `q80Gemm` calls:
  - Validate activation buffer type (must be float pointer/array/tensor).
  - Validate activationLength equals view.columns, and outputLength >= view.rows.
  - Reject mismatch with stable compile diagnostics.
  - Reject passing generic uniform quantized tensor to Q8_0 functions.

### 5.3 MIR & LIR Lowering

In `stdlib/vir/compiler/ast_to_mir.vri`:
- `infer_expr_type_name` and `set_var_type` handle structured quantized type strings.
- `MatMulOp` with quantized left operand encodes `is_quantized = 1` in `ins.aux` alongside M, K, N, and bits.
- `MIR_INTR_QUANTIZE` retains shape and element type in aux metadata.

In `stdlib/vir/compiler/lir_lower.vri` & `stdlib/vir/compiler/lir_codegen.vri`:
- Propagate `is_quantized` flag in `ins.aux` to `LirOp.MatMul`.
- In `lir_codegen.vri`:
  - When `is_quantized == 1`, dispatch to `emit_lir_rt_matmul_quantized_stub` on ARM64 and x86-64.
  - The stub computes dequantized dot products using the scale at offset 16 and packed int8/int4 values at offset 32, producing exact outputs matching dense tensors.
  - On unsupported targets (e.g. Wasm if unsupported), produce a clean compile diagnostic instead of silent fallback.

### 5.4 Deterministic Dump Support

Add CLI flags `--dump-semantic`, `--dump-mir`, `--dump-lir` in `virc.vri`:
- `--dump-semantic`: prints function variables and their full type strings.
- `--dump-mir`: prints MIR blocks and instructions with operand types, aux annotations, and shapes.
- `--dump-lir`: prints LIR blocks and instructions with physical registers, aux attributes, and target opcodes.

## 6. Design Decisions

### Decision 1 — Internal-only metadata schema without new public syntax

**Decision:** Retain Spec v2.0 syntax (`quantize(tensor, bits: N)` and stdlib `Q80TensorView`) and represent rich metadata internally via structured compiler type strings and descriptors.

**Rationale:** The user has not requested a language specification amendment. Internal representation fulfills all compiler correctness and optimization goals without violating the Spec Freeze rule.

**Alternatives considered:** Introducing `tensor[q8_0; M, K]` syntax. Rejected because it violates Spec Freeze.

### Decision 2 — Codec-distinct type identities

**Decision:** Treat `uniform` and `q8_0` as mutually incompatible codecs.

**Rationale:** Generic 8-bit uniform quantization stores `{numel, bits, scale, zero_point, flat bytes}`, while Q8_0 stores 40-byte blocks `{scale: f64-le, int8[32]}` with row strides and alignment. Reinterpreting one as the other causes memory corruption.

### Decision 3 — In-pipeline quantized matmul lowering

**Decision:** Lower uniform quantized `**` directly into a verified runtime stub that reads the uniform layout and scale, returning a standard dense float tensor.

**Rationale:** Resolves long-standing gaps in AI-001 and AI-003 while maintaining full source compatibility.

## 7. Implementation Plan

### Phase 1 — Type Table and String Helpers

- files/modules: `stdlib/vir/compiler/type_table.vri`
- changes: Add quantized codec constants, structured string formatters, and parsing helpers (`is_quantized_type_str`, `parse_quantized_shape`, `parse_quantized_codec`, etc.).
- dependencies: Existing string runtime and vec_rt.
- expected result: Independent helper tests pass; type table exports new functions.

### Phase 2 — Semantic Analysis Hardening

- files/modules: `stdlib/vir/compiler/sem_pass6_typecheck.vri`
- changes:
  - Propagate rich type strings in `QuantizeExpr`.
  - Validate and associate `Q80TensorView` with Q8_0 descriptor.
  - Enable quantized matmul checking in `infer:` when shapes align.
  - Validate Q8_0 kernel call arguments and emit stable diagnostics on mismatch.
- dependencies: Phase 1 type helpers.
- expected result: Type checker validates shapes, catches mismatches, and preserves metadata across bindings.

### Phase 3 — MIR, LIR, and Runtime Lowering

- files/modules: `stdlib/vir/compiler/ast_to_mir.vri`, `stdlib/vir/compiler/lir_lower.vri`, `stdlib/vir/compiler/lir_codegen.vri`, `stdlib/vir/compiler/lir_codegen_x86.vri`
- changes:
  - Pass quantized shape and codec in `ins.aux`.
  - Implement `emit_lir_rt_matmul_quantized_stub` for ARM64 and x86-64.
  - Add `--dump-semantic`, `--dump-mir`, `--dump-lir` flags in `virc.vri`.
- dependencies: Phase 2 semantic types.
- expected result: AI-001 and AI-003 execute successfully; dump flags output deterministic metadata.

### Phase 4 — Verification, Bootstrap, and Paper Lifecycle

- files/modules: `tests/`, `papers/`
- changes:
  - Add negative test fixtures for shape mismatch, wrong activation type, and codec reinterpretation.
  - Add dump verification fixture.
  - Re-run full test suite and verify AI-001, AI-003, AI-006, Q80-001.
  - Sync `virc.vri` and rebuild self-hosted compiler.
  - Create REPORT and update ISSUE lifecycle.
- dependencies: Phases 1–3.
- expected result: Clean test runner output, synchronized compiler bundle, and valid VPS papers.

## 8. Compatibility

- **Source compatibility:** 100% source-compatible with existing Vir code; no keywords or grammar added.
- **ABI:** Runtime layouts of `Tensor`, `QuantizedTensor`, and `Q80TensorView` remain strictly preserved.
- **Stdlib:** `math.tensor_q8_0` remains the single SSOT for the 40-byte view and kernels.

## 9. Migration

No user migration required; existing programs continue to work without change.

## 10. Validation Plan

- Unit tests for type string parsing and formatters;
- Negative semantic tests for Q8_0 argument mismatch and invalid shapes;
- Execution of `AI-001`, `AI-003`, `AI-006`, and `Q80-001`;
- Regression test runner across full contract suite;
- `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Quantized type string confuses existing string/type checks | Low | Medium | Use distinct prefix `quantized[` and guard checks with `is_quantized_type_str` |
| Rounding discrepancies in 4-bit uniform matmul | Low | Low | Match exact integer dequantization oracle specified in AI-003 |
| Self-host bootstrap failure during bundle sync | Low | High | Run modular sync and test Stage 1/Stage 2 bootstrap in isolation |

## 12. Rollback Strategy

Revert changes to `type_table.vri`, `sem_pass6_typecheck.vri`, `ast_to_mir.vri`, and `lir_codegen.vri`. Run `tools/sync_virc.py` to restore monolithic compiler.

## 13. Exit Criteria

- [x] Internal quantized metadata captures codec, element type, shape, and physical layout without flat string collapsing;
- [x] AI-001 and AI-003 pass in gap contract runner;
- [x] Q80-001 and AI-006 pass with verified dispatch;
- [x] Negative tests verify rejection of mismatched shapes, activation types, and codec reinterpretation;
- [x] Deterministic dump tests prove metadata preservation across compiler passes;
- [x] Modular compiler sources and `virc.vri` are synchronized and self-host compiles cleanly;
- [x] VIRC-RPT-0035 implementation report links VIRC-ISS-0005 and VIRC-PLN-0003;
- [x] `./paper validate` passes with zero errors.

## 14. Related Papers

- VIRC-ISS-0005 — Source issue
- VIRC-ISS-0003 — Q8_0 stdlib and kernels
- VIRC-PLN-0002 — Q8_0 implementation plan
- VIRC-RPT-0001 — Q8_0 implementation report
- VIRC-RPT-0035 — Implementation report

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Activated PLAN for VIRC-ISS-0005 implementation |
| 2026-10-04 | Completed implementation and verification; linked VIRC-RPT-0035 |
| 2026-10-04 | Reverted to ACTIVE to complete x86 stub, true dequantization float inference, real dump flags, and Q8_0 contract verification |
| 2026-10-04 | Completed all remaining work: x86 quantized stub, MIR/LIR metadata, active dump flags, float dequantization, and Q8_0 suite; advanced to COMPLETED |
| 2026-10-05 | Completed follow-up audit items: isolated MIR bits from SSA memory epochs, implemented and propagated dedicated LIR metadata fields, corrected Q80-005 output bounds contract, proved compiler dispatch in Q80-001, verified x86 execution in Docker, and confirmed bit-for-bit 3-stage bootstrap |
| 2026-10-05 | Completed third-phase audit resolution: integrated Q8_0 external-view metadata in active IR, added variable type dump to --dump-semantic, unwrapped activation type for Q8_0 negative test (Q80-004), verified dynamic output length error propagation (Q80-005), added automated pytest regression suite, and validated zero regression across 116-test suite |
| 2026-10-05 | Completed fourth-phase descriptor hardening: separated block bytes from row stride; propagated byte range, read-only, ownership, lifetime, and generation through semantic/MIR/LIR; added mandatory LIR descriptor verification; added Q80-006..010, O0..O3 dump regressions, and Q8_0 SIMD-vs-`--no-simd` opcode checks; and activated the checked 121-status baseline |
