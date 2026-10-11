---
id: "VIRC-PLN-0032"
type: "PLAN"
domain: "VIRC"
title: "Implement generic tensor quantization storage and transparent inference contracts"
status: "COMPLETED"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "runtime"
components:
  - "tensor"
  - "quantization"
  - "infer"
  - "mir"
  - "lir"
  - "runtime-stubs"
  - "arm64"
  - "x86-64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0019"
  plans: []
  reports:
    - "VIRC-RPT-0049"
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "quantize"
  - "int4"
  - "int8"
  - "f16"
  - "f32"
  - "dequantize"
  - "infer"
---

# VIRC-PLN-0032 — Implement generic tensor quantization storage and transparent inference contracts

## 1. Objective

Deliver a comprehensive implementation of generic tensor quantization storage and transparent inference contracts specified in VIR-SPC-0018 §26.5 and required by VIRC-ISS-0019. This includes:
1. Correctly supporting `f16` (2-byte), `f32` (4-byte), and `f64` (8-byte) input tensors in runtime quantize stubs on both ARM64 and x86-64, eliminating source-stride misinterpretation.
2. Supporting all four specified quantization bit widths: 4 (`INT4`), 8 (`i8`), 16 (`f16`), and 32 (`f32`) with accurate storage representation and scale/zero-point computation.
3. Enabling transparent inference (`infer:` block) dequantization and matmul kernel execution for 2-byte (`f16`), 4-byte (`f32`), and 8-byte (`f64`) activations across INT4, INT8, and floating bit-widths.
4. Restoring full test passage on `tests/strict_v2/test_quantize_e2e.vri` (Group 26) and spec gap contracts `AI-001` (`quantize_transparent_infer.vri`) and `AI-003` (`quantize_odd_int4_edge.vri`).

## 2. Source Issues

- VIRC-ISS-0019

## 3. Scope

### In Scope

- Propagation of input tensor element type/size through MIR and LIR for `MIR_INTR_QUANTIZE` / `LIR_RT_QUANTIZE`.
- ARM64 runtime stub (`emit_lir_rt_quantize_stub`) update: support 2-byte `f16`, 4-byte `f32`, and 8-byte `f64` source elements with matching loads and conversions.
- ARM64 runtime stub (`emit_lir_rt_matmul_quantized_stub`) update: support 2-byte `f16`, 4-byte `f32`, and 8-byte `f64` activation loads.
- x86-64 intrinsic lowering and runtime stubs in the executable
  `compiler/src/lower/lir_codegen_x86/` backend.
- Correct handling of INT4 packing (low nibble first, high nibble second, odd tensor lengths zero-padded).
- Verification of test suites: Group 26 (`test_quantize_e2e.vri`), Spec Gap Contracts `AI-001` and `AI-003`, and regression test baseline.

### Out of Scope

- Q8_0 40-byte blocked codec (governed separately by VIRC-ISS-0005 / VIRC-PLN-0003).
- NPU-specific hardware INT4 vector acceleration instructions.

## 4. Current Architecture

The initial baseline had lost the source element width before runtime lowering,
hardcoded 8-byte ARM64 loads, and routed the first x86 implementation into the
legacy `lir_codegen_x86` backend.

The current checkout has advanced beyond that baseline:

1. `expr_ops.vri` lowers `quantize(w, bits: N)` to `MIR_INTR_QUANTIZE` and maps
   the inferred source element descriptor to `MirType.F16`, `MirType.F32`, or
   `MirType.F64`. Quantized matmul also encodes the activation width in MIR
   metadata.
2. The ARM64 lowering passes source element size 2, 4, or 8 in `X2` and the
   reachable ARM64 runtime stubs select the matching load/conversion path.
   Quantized matmul preserves its width code in a 16-byte aligned stack slot
   rather than the platform-reserved `X18` register.
3. Executable target `linux-x86_64` is routed by `step_backend.vri` to
   `emit_lir_module_x86_64` in `compiler/src/lower/lir_codegen_x86.vri`.
   This byte emitter owns the reachable intrinsic fixups and runtime stubs.
   The similarly named MCInst lowering is used by the assembly-emission path
   and is not the executable backend used by the O0-O3 ELF tests.
4. The reachable x86 runtime now includes float printing, source-width-aware
   quantization, and quantized matmul for activation widths f16/f32/f64.

## 5. Proposed Architecture

1. **Shared type and operation metadata**:
   - Preserve the existing MIR/LIR propagation for `f16`, `f32`, and `f64`
     source widths and quantized-matmul dimensions/width codes.
   - Make the executable x86 intrinsic lowering consume the same LIR operand,
     type, and `SetArg` information as ARM64 lowering.
2. **Reachable x86 executable runtime surface**:
   - Add explicit raw-backend lowering/fixups for `MIR_INTR_PRINT_FLOAT`,
     `MIR_INTR_QUANTIZE`, and quantized `LirOp.MatMul`.
   - Pass their arguments using the verified System V x86-64 ABI and preserve
     compiler-assigned live registers across calls according to the existing
     raw-backend call contract.
   - Emit the corresponding runtime entry points through the reachable
     `compiler/src/lower/lir_codegen_x86/` stub table.
3. **Quantization and transparent matmul behavior**:
   - Select 2-, 4-, or 8-byte source loads from the propagated element type.
   - Preserve valid f16/f32 storage for bits 16/32; implement signed INT8 and
     low-nibble-first packed INT4 storage for bits 8/4, including odd lengths.
   - Unpack each supported width in quantized matmul and feed float printing
     through the reachable x86 float runtime so numeric stdout is observable.
4. **Fail-closed backend behavior**:
   - Treat an unsupported required intrinsic as a compilation error instead of
     silently omitting it. This prevents a zero-exit executable from being
     accepted when quantization or float printing was never emitted.

## 6. Design Decisions

### Decision 1: Preserve element byte size at each active target boundary

**Decision:** Preserve source element size 2, 4, or 8 from the LIR type. The
ARM64 runtime call receives it in `X2`. The active x86 lowering reads the same
LIR type and places the size in the third System V integer argument
register, `RDX`, when calling its reachable quantize runtime entry point.

**Rationale:** The existing `QuantizedTensor` representation has header `numel`, `capacity` which does not encode element size. Passing the element size in the standard 3rd argument register preserves existing tensor headers without requiring runtime layout changes.

**Alternatives considered:** Modifying the input tensor header to store an element descriptor. Rejected because it would break existing dense tensor layouts across the entire compiler runtime.

**Trade-offs:** Each active target lowering must materialize the third argument
before its runtime call and tests must verify that the propagated type, not a
legacy backend side channel, determines the value.

## 7. Implementation Plan

### Phase 1 — Type and Aux Propagation
- `compiler/src/lower/ast_to_mir/expr_ops.vri`:
  - Preserve `MirType.F16`, `MirType.F32`, or `MirType.F64` on quantize.
  - Preserve f16/f32/f64 activation width metadata on quantized matmul.
- `compiler/src/lower/lir_codegen/intrinsics.vri`:
  - Keep the completed ARM64 propagation of element size 2, 4, or 8 in `X2`.
- `compiler/src/lower/lir_codegen_x86/intrinsics.vri`:
  - Read the propagated LIR type and pass element size in `RDX` through the
    production executable backend.

### Phase 2 — ARM64 Quantize and MatMul Runtime Stubs
- `compiler/src/lower/lir_codegen/rt_stubs_math/quantize_backward.vri`:
  - Implement 2-byte half-float reading and promotion when element size is 2.
  - Implement 4-byte float reading in scale calculation and packing loops when element size is 4.
  - Implement 8-byte double reading when element size is 8.
- `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`:
  - Save `width_code` in a 16-byte aligned stack frame slot (`[sp, 0]`); strictly avoid platform-reserved register `X18`.
  - Branch activation loads among 2-byte `ldr h` + promotion, 4-byte `ldr s` + promotion, and 8-byte `ldr d`.

### Phase 3 — x86-64 Executable Intrinsic Lowering and Runtime Parity
- `compiler/src/lower/lir_codegen_x86/intrinsics.vri` and `emit_func.vri`:
  - Lower `MIR_INTR_PRINT_FLOAT`, `MIR_INTR_QUANTIZE`, and quantized
    `LirOp.MatMul` through reachable runtime fixups.
- `compiler/src/lower/lir_codegen_x86/calls.vri` and `rt_stubs_math/`:
  - Emit reachable float formatting, quantize packing loops, and transparent
    dequantization matmul.
- Make missing required x86 intrinsics fail compilation rather than being
  silently ignored.

### Phase 4 — Verification and Compiler Self-Hosting
- Synchronize compiler sources via `python3 tools/sync_virc.py`.
- Rebuild self-hosted compiler `bin/virc`.
- Verify `tests/strict_v2/test_quantize_e2e.vri` exits 0.
- Verify `tests/spec_gap_contract/quantize_transparent_infer.vri` (`AI-001`) and `quantize_odd_int4_edge.vri` (`AI-003`) pass.
- Compile the focused quantization fixtures for `linux-x86_64` at O0-O3 and
  execute them through the available QEMU/binfmt environment.
- Require exact numeric stdout and byte-layout oracles and inspect emitted
  assembly for the expected intrinsic-specific calls/runtime symbols.
- Run test groups and validate zero regressions.

## 8. Compatibility

- Preserves backward compatibility with existing dense tensor representations.
- Preserves Q8_0 blocked tensor view contracts.
- Completion targets conformance with the storage widths and transparent
  dequantization requirements currently stated in VIR-SPC-0018 §26.5.
  VIR-SPC-0018 v3.1.2 now defines the exact numerical edge policy, including
  NaN/Inf, signed zero, integer-domain guards, and malformed-input boundaries.

## 9. Migration

No migration required.

## 10. Validation Plan

- Verify `tests/strict_v2/test_quantize_e2e.vri` passes (Group 26).
- Verify `tests/spec_gap_contract/quantize_transparent_infer.vri` (`AI-001`) matches `3.0\n7.0`.
- Verify `tests/spec_gap_contract/quantize_odd_int4_edge.vri` (`AI-003`) matches `6.0\n15.0`.
- For every optimization level O0-O3, compile
  `test_quantize_f16_input.vri`, `test_quantize_f16_infer.vri`, and
  `test_quantize_e2e.vri` for `linux-x86_64` and execute the resulting ELF
  binaries under QEMU/binfmt.
- Require exact x86 stdout for inference (`3.0\n7.0`) and exact byte-level
  storage assertions for bits 4, 8, 16, and 32; exit code 0 alone is not a
  passing oracle.
- Execute exact-output x86 oracles so an artifact that silently omits
  quantize, quantized matmul, or float printing cannot pass on exit code alone.
- Run full Group 26 suite and Group 4 suite.
- Verify signed-zero and IEEE NaN/Infinity storage for bits 16/32, plus status
  133 rejection of non-finite inputs for bits 4/8, on ARM64 and x86-64 O0-O3.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Register clobbering in runtime stubs | Low | High | Audit caller-saved register usage in ARM64 and x86 stubs |
| Compiler self-hosting divergence | Low | High | Rebuild compiler via multi-stage verification |

## 12. Rollback Strategy

Revert code changes in `compiler/src/` via git checkout and restore previous compiler binary from stage backup.

## 13. Exit Criteria

- [x] `tests/strict_v2/test_quantize_e2e.vri` passes (Group 26).
- [x] Contract cases `AI-001` and `AI-003` pass with correct numeric outputs (`3.0`, `7.0` and `6.0`, `15.0`).
- [x] Direct acceptance tests for f16 tensor source input on ARM64 and 16/32-bit layout pass.
- [x] x86-64 runtime quantize and quantized matmul parity implemented and verified.
- [x] Platform register X18 eliminated from ARM64 quantized matmul stub.
- [x] `./paper validate` succeeds.
- [x] Implementation report updated with ARM64/x86 evidence and remaining
  normative closure gate.

## 14. Related Papers

- VIRC-ISS-0005 — Quantized tensors lack format, shape, and storage metadata
- VIRC-RPT-0035 — Quantized tensor metadata and transparent inference implementation report

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Completed authorized VIR-SPC-0018 v3.1.2 edge policy and cross-target regression matrix; no remaining plan work |
| 2026-10-08 | Corrected executable backend ownership to lir_codegen_x86, repaired float-write length calculation, added all-width infer and exact-output Docker amd64 O0-O3 regression gates, and completed the implementation plan |
| 2026-10-08 | Replaced stale baseline architecture with the current ARM64/MCInst state, added reachable x86 runtime design and fail-closed lowering, scoped the SPEC conformance claim, and added O0-O3 QEMU stdout/layout/assembly gates |
| 2026-10-08 | Revised Phase 3 to target active MCInst backend lir_to_mc/x86_64.vri; removed X18 reference in favor of aligned stack slot [sp, 0] |
| 2026-10-08 | Reactivated to ACTIVE: audit identified active linux-x86_64 target uses lir_to_mc/x86_64 lacking PRINT_FLOAT/QUANTIZE/MATMUL_QUANTIZED lowering, and QEMU x86 verification failed |
| 2026-10-08 | Initial comprehensive plan created for VIRC-ISS-0019 |
| 2026-10-08 | Linked VIRC-RPT-0049 |
| 2026-10-08 | Implementation completed, verified against Group 26 and spec contracts, plan marked COMPLETED |
| 2026-10-08 | Reactivated: adding phases for ARM64 f16 source input, X18 removal, and full x86-64 runtime parity |
| 2026-10-08 | All phases and exit criteria completed and verified; plan moved to COMPLETED |
| 2026-10-08 | Reactivated to ACTIVE: addressing x86 f16 truncation rounding fix, x86 float print stub for transparent infer oracle, and Group 26 test registration |
