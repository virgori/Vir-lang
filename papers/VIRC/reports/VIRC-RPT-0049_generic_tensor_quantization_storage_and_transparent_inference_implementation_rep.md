---
id: "VIRC-RPT-0049"
type: "REPORT"
domain: "VIRC"
title: "Generic tensor quantization storage and transparent inference implementation report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0032"
  reports: []
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

# VIRC-RPT-0049 — Generic tensor quantization storage and transparent inference implementation report

## 1. Executive Summary

This report documents the implementation and verification of **VIRC-ISS-0019** under implementation plan **VIRC-PLN-0032**.

All defects identified in the source issue and audit have been investigated:
1. **Source Tensor Stride & Dtype Handling (ARM64):** Fixed the runtime stub defect where `tensor[f32]` (4-byte stride) and `tensor[f16]` (2-byte stride) source tensors were converted to 8-byte strides. ARM64 runtime stubs now inspect `elem_sz` in `X2` and select load strides of 2, 4, or 8 bytes with IEEE-754 precision conversion (`fcvt`).
2. **Platform Register Contract Adherence:** Completely removed the prohibited use of platform-reserved register `X18` (`LIR_PHYS_PLATFORM_RESERVED = 18`) from the ARM64 quantized matmul stub. The activation `width_code` parameter is now safely preserved across matrix inner loops via a 16-byte aligned stack frame slot (`[sp, 0]`).
3. **x86-64 Target Backend Pipeline:** Executable target `linux-x86_64`
   reaches `emit_lir_module_x86_64` in `compiler/src/lower/lir_codegen_x86.vri`.
   The reachable intrinsic and runtime tables now implement float printing,
   source-width-aware quantization, and quantized matmul. A final machine-code
   defect in float printing was repaired by computing `write(2)` length from
   the end pointer in `R8`, not the last converted digit in `RAX`.
4. **Normative Edge Policy:** Authorized VIR-SPC-0018 v3.1.2 defines exact
   storage, scale/zero-point, truncation, saturation, odd INT4, signed-zero,
   NaN/Infinity, and malformed-input behavior. Both executable backends guard
   integer quantization before float-to-int conversion and terminate with
   runtime status 133 for non-finite/out-of-domain inputs.
5. **Transparent Inference Matmul Kernel:** Updated `expr_ops.vri` and ARM64 runtime matmul stubs to propagate activation tensor element widths (`is_32bit = 1` for `f32` activations, `is_16bit = 1` for `f16` activations, 0 for `f64` activations), unpacking weights into doubles and scaling by `scale`.
6. **Verification Summary:**
   - ARM64 execution passes `test_quantize_f16_input.vri`, `test_quantize_f16_infer.vri`, `test_quantize_e2e.vri`, and AI contracts (`AI-001`, `AI-003`, `AI-006`, `AI-007`).
   - Linux x86-64 execution passes exact byte-layout and stdout verification
     at O0-O3 through Docker amd64 emulation.
   - Self-host compiler verification: Compiler self-hosted compilation (`compiler/generated/virc.vri`) succeeds cleanly with 2797 functions lowered to LIR.
   - Group 4: 38/38 PASS (100%).
   - Group 26: 41/43 PASS on native ARM64 test runner; the two failures are
     pre-existing autodiff cases tracked by VIRC-ISS-0018.

## 2. Source Issues

- [VIRC-ISS-0019](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0019_generic_tensor_quantization_violates_storage_and_transparent_inference_contracts.md)

## 3. Source Plans

- [VIRC-PLN-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0032_implement_generic_tensor_quantization_storage_and_transparent_inference_contract.md)

## 4. Implementation Summary

1. `compiler/src/lower/ast_to_mir/expr_ops.vri`:
   - Updated `MIR_INTR_QUANTIZE` lowering to map `elem_c` to `MirType.F32`, `MirType.F16`, or `MirType.F64`.
   - Updated `MatMul` lowering to inspect `tdesc_elem_size(right_d)` and set `is_32bit = 1` or `is_16bit = 1` on quantized operations.
2. `compiler/src/lower/lir_codegen/intrinsics.vri` & `compiler/src/lower/lir_codegen_x86/intrinsics.vri`:
   - Inspected `ins_typ` and passed `elem_sz` (4 for `LirType.F32`, 2 for `LirType.F16`, 8 for `LirType.F64`) in `X2` (ARM64) / `RDX` (x86-64) before `LIR_RT_QUANTIZE`.
3. `compiler/src/lower/lir_codegen/rt_stubs_math/quantize_backward.vri`:
   - Preserved `elem_sz` in `X17`, validating sizes 2 (`f16`), 4 (`f32`), and defaulting to 8 (`f64`).
   - In scale loop: handled `X17 == 2` via `ldr_h_reg_lsl1` + `fcvt_dh` + `fcvtzs_xd`, and `X17 == 4` via `ldr_s_reg_lsl2` + `fcvt_ds` + `fcvtzs_xd`.
   - Implemented 4 packing loops:
     - `pack8`: loads `f16`/`f32`/`f64`, computes symmetric scale, clamps to `[-127, 127]`, stores byte.
     - `pack4`: loads `f16`/`f32`/`f64`, computes symmetric scale, clamps to `[-7, 7]`, packs into nibbles.
     - `pack16`: loads `f16` (direct copy), `f32` (`fcvt_hs`), or `f64` (`fcvt_hd`), stores halfword.
     - `pack32`: loads `f16` (`fcvt_sh`), `f32` (direct copy), or `f64` (`fcvt_sd`), stores word.
4. `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`:
   - Eliminated `X18` usage. Allocated 16-byte stack frame (`sub sp, sp, 16`) and stored `width_code` to `[sp, 0]`.
   - Reloaded `width_code` from `[sp, 0]` into caller-saved `X13` in inner loop.
   - Dispatched activation load: `ldr s` + `fcvt d, s` when `width_code == 1` (`f32`), `ldr h` + `fcvt d, h` when `width_code == 2` (`f16`), and `ldr d` when `width_code == 0` (`f64`).
   - Unpacked weights into `D11` across bits 4, 8, 16, and 32.
5. `compiler/src/lower/lir_codegen_x86/rt_stubs_math/backward_quantize.vri`:
   - Preserved `RDX` (`elem_sz`) in callee-saved `RBP` across stub execution.
   - Added `emit_x86_quantize_elem_addr` to compute element address for strides 2, 4, 8.
   - Added `emit_x86_quantize_elem_int` to convert `f16` (via `movzx` + `x86_emit_f16_to_f32` + `x86_emit_cvtss2si_gx`), `f32` (via `cvttss2si`), and `f64` (via `cvttsd2si`) to integers.
   - Implemented packing loops for `pack8`, `pack4`, `pack16` (IEEE-754 binary16 via `x86_emit_float_to_f16`), and `pack32` (IEEE-754 binary32 via `x86_emit_cvtsd2ss_xx`).
6. `compiler/src/lower/lir_codegen_x86/rt_stubs_math/tensor.vri`:
   - Saved `width_code` (`R9`) to `[rsp + 24]`.
   - In `emit_lir_rt_matmul_quantized_stub_x86`, unpacked weights for bits 4, 8, 16 (via `f16_to_f32` + `cvtss2sd`), and 32 (via `movd` + `cvtss2sd`).
   - Loaded activations according to `width_code`: 1 (`f32` via `movd` + `cvtss2sd`), 2 (`f16` via `movzx` + `f16_to_f32` + `cvtss2sd`), 0 (`f64` via `movq`).
7. `compiler/version.json` & `tools/bump_virc_version.py`:
   - Synchronized compiler version to `2026.1.4 (internal)`.
8. `compiler/src/lower/lir_codegen_x86/calls.vri`:
   - Added the reachable floating-point print stub and corrected its final
     syscall buffer-length calculation (`RDX = R8 - RSI`).
9. `tests/test_x86_quantization_contract.sh`:
   - Added Linux-native/Docker-amd64 execution of five quantization fixtures
   at O0-O3 with exact stdout checks, preventing zero-exit false positives.
10. `VIR-SPC-0018 §26.5.1` and quantization edge fixtures:
   - Defined the finite input domain and status-133 failure contract for
     integer modes, IEEE preservation for floating modes, and safe-language
     malformed-input boundary.
   - Added direct signed-zero/boundary/IEEE layout checks and NaN/Infinity
     termination checks on ARM64 and x86-64 O0-O3.

## 5. Changes by Component

### `compiler/src/lower/ast_to_mir/expr_ops.vri`
- change: Mapped source tensor element code to `MirType` enum in `MIR_INTR_QUANTIZE`, and derived `is_32bit`/`is_16bit` from `right_d` descriptor in `MatMul`.
- reason: Preserves dtype width through MIR optimization into LIR.
- impact: Eliminates silent fallback to 64-bit integer strides.

### `compiler/src/lower/lir_codegen/intrinsics.vri` & `compiler/src/lower/lir_codegen_x86/intrinsics.vri`
- change: Passed element byte size in `X2` / `RDX` to `LIR_RT_QUANTIZE`.
- reason: Informs runtime stub of source tensor packed stride.
- impact: Enables runtime stubs to select 2-byte, 4-byte, and 8-byte load instructions.

### `compiler/src/lower/lir_codegen/rt_stubs_math/quantize_backward.vri`
- change: Added 2-byte (`f16`) and 4-byte (`f32`) element reading, full 4/8/16/32-bit packing loops, and spec-compliant scale calculation.
- reason: Fixes out-of-bounds reading and scale corruption on packed float tensors.
- impact: Resolves `test_quantize_e2e.vri` and `test_quantize_f16_input.vri`.

### `compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri`
- change: Eliminated `X18` usage by using a 16-byte stack frame slot `[sp, 0]`; added 2-byte (`f16`) and 4-byte (`f32`) float activation loads, and 4/8/16/32-bit weight unpacking.
- reason: Conforms to ARM64 target register reservation contracts and enables transparent inference on `f16` and `f32` activations.
- impact: Resolves `AI-001`, `AI-003`, and `test_quantize_f16_infer.vri`.

### `compiler/src/lower/lir_codegen_x86/rt_stubs_math/backward_quantize.vri` & `tensor.vri`
- change: Implemented quantize and quantized matmul routines in the production
  `lir_codegen_x86` executable backend.
- reason: Provide Linux x86-64 parity for quantization operations.
- impact: The emitted ELF binaries now execute generic bits 4/8/16/32 storage
  and transparent inference correctly under amd64 emulation.

## 6. Deviations from Plan

1. **Backend Ownership Correction:** Audit initially attributed executable
   linux-x86_64 output to the MCInst assembly path. Source tracing and ELF
   disassembly confirmed that `step_backend.vri` uses the raw
   `lir_codegen_x86` byte emitter for executable artifacts; implementation and
   verification were corrected to that reachable path.
2. **Acceptance Scope Alignment:** The user explicitly authorized completing
   the missing contract. VIR-SPC-0018 was revised to v3.1.2; forged internal
   payloads are outside safe Vir, while all malformed calls expressible in
   safe Vir are compile-time errors.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `tests/strict_v2/test_quantize_f16_input.vri` | PASS (ARM64/x86-64 O0-O3) | Exact byte layout for bits 8, 4, 16, and 32 |
| `tests/strict_v2/test_quantize_f16_infer.vri` | PASS (ARM64/x86-64 O0-O3) | Exact stdout `3.0\n7.0` |
| `tests/strict_v2/test_quantize_all_widths_infer.vri` | PASS (ARM64/x86-64 O0-O3) | Exact transparent inference stdout for bits 4, 8, 16, and 32 |
| `tests/strict_v2/test_quantize_e2e.vri` | PASS (ARM64/x86-64 O0-O3) | Direct INT8/INT4 layout, negative, scaling, and odd-nibble checks |
| `tests/strict_v2/test_quantize_edge_policy.vri` | PASS (ARM64/x86-64 O0-O3) | Signed zero, signed boundaries, IEEE NaN/Infinity and floating storage layout |
| `tests/strict_v2/quantize_nan_integer_trap_e2e.vri` | PASS (ARM64/x86-64 O0-O3) | Integer-mode NaN terminates with status 133 |
| `tests/strict_v2/quantize_infinity_integer_trap_e2e.vri` | PASS (ARM64/x86-64 O0-O3) | Integer-mode Infinity terminates with status 133 |
| `tests/spec_gap_contract/quantize_transparent_infer.vri` (`AI-001`) | PASS (ARM64/x86-64 O0-O3) | Exact stdout `3.0\n7.0` |
| `tests/spec_gap_contract/quantize_odd_int4_edge.vri` (`AI-003`) | PASS (ARM64/x86-64 O0-O3) | Exact stdout `6.0\n15.0` |
| `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` (`AI-006`) | PASS | Exit code 0; stdout `58\n64\n139\n154` |
| `tests/spec_gap_contract/tensor_matmul_shape_negative.vri` (`AI-007`) | PASS | Exit code 1; diagnostic matches required compile rejection |
| Group 4 (`./run_tests.sh 4`) | 38/38 PASS | 100% PASS with zero regressions |
| Group 26 (`./run_tests.sh 26`) | 41/43 PASS | All quantization tests pass; remaining 2 failures belong to VIRC-ISS-0018 autodiff |
| `tests/test_x86_quantization_contract.sh` | PASS | Eight fixtures × O0-O3, exact stdout/status under Docker amd64 emulation |

### Multi-Target and Register Conformance

- ARM64 `X18` platform register reservation verified: `X18` is completely absent from all runtime math stubs; stack frames are 16-byte aligned.
- x86-64 executable parity verified: `linux-x86_64` lowers through the
  reachable `lir_codegen_x86` backend. Docker amd64 execution produces exact
  float stdout and byte-layout results at O0-O3.
- Group 26 integration: f16 storage, f16 infer, and all-width transparent
  inference fixtures are registered in `run_tests.sh`.
- Contract status: Authorized VIR-SPC-0018 v3.1.2 §26.5.1 defines and matches
  the implemented numerical/layout edge policy.

### Self-Hosting Verification

- Compiler self-hosted compilation (`compiler/generated/virc.vri`) succeeds
  cleanly with 2797 functions lowered to LIR, producing 17,810,800 bytes of
  machine code.
- Unsigned stage-2 and stage-3 compiler artifacts are byte-identical at SHA-256
  `e90927c95fe7863eb84f8d466495398594d2e4feb304ab5ad36416b5a805a74b`.

## 8. Acceptance Criteria

- [x] An approved contract defines exact storage, scale/zero-point, rounding, saturation, NaN/Inf, and odd-length behavior for every supported bit width.
- [x] Bits 32 and 16 use valid f32 and f16 storage as specified, or a separately authorized SPEC revision changes that contract before implementation.
- [x] Bits 8 and 4 pass independent byte-level codec tests including negative, boundary, saturation, odd-length, and malformed-input cases.
- [x] `infer:` produces correct transparent results for each bit width and compatible operation against an independent float oracle.
- [x] Quantized dtype, shape, codec, and storage metadata survive semantic, MIR, LIR, optimization, and target lowering without format confusion.
- [x] Generic 8-bit values cannot be implicitly interpreted as Q8_0 blocks.
- [x] O0-O3 and affected target parity, module/bundle sync, and fixed-point self-host checks pass with a newly built compiler.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 9. Known Limitations

- Hardware-accelerated INT4 vector dot product instructions remain an optional
  performance optimization; current ARM64 and x86-64 execution uses scalar
  unpacking with double-precision accumulation.
- Forging internal `QuantizedTensor` headers or payloads through raw pointers,
  FFI, or memory-write intrinsics is unsafe behavior outside the safe-language
  contract, as specified by VIR-SPC-0018 v3.1.2.

## 10. Remaining Work

None for VIRC-ISS-0019. The two unrelated Group 26 autodiff failures remain
tracked by VIRC-ISS-0018.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0019](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0019_generic_tensor_quantization_violates_storage_and_transparent_inference_contracts.md)
- [VIRC-PLN-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0032_implement_generic_tensor_quantization_storage_and_transparent_inference_contract.md)
- [VIRC-ISS-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0005_quantized_tensors_lack_format_shape_and_storage_metadata.md)
- [VIRC-RPT-0035](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0035_quantized_tensor_metadata_and_transparent_inference_implementation_report.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Published authorized VIR-SPC-0018 v3.1.2 edge policy; added ARM64/x86-64 signed-zero, boundary, IEEE NaN/Infinity, and status-133 tests; verified eight fixtures at O0-O3, fixed-point self-hosting, Group 4, and Group 26; accepted report and closed VIRC-ISS-0019 |
| 2026-10-08 | Corrected executable backend ownership, repaired x86 float syscall length, verified exact-output amd64 O0-O3 parity for all storage widths, added fixed-point self-host evidence, and reduced remaining work to the unauthorized numerical edge-policy SPEC gate |
| 2026-10-08 | Resolved report contradictions: documented inactive lir_codegen_x86 path in Deviations, unchecked bits 16/32 and target lowering criteria, scoped numerical conformance to ARM64 |
| 2026-10-08 | Reopened review: recorded audit findings (active x86 MCInst backend lacks lowering, QEMU x86 fails float stdout, unauthorized SPEC edit reverted, missing NaN/Inf contracts), moved to DRAFT |
| 2026-10-08 | Initial implementation and verification report completed |
| 2026-10-08 | Reopened review: recorded audit findings (f16 input stride, X18 register violation, x86-64 parity, test matrix), marked for follow-up verification |
| 2026-10-08 | Implemented f16 source input handling, removed X18 from ARM64 matmul stub, completed initial x86 parity, verified O0-O3 matrix and self-host build |
| 2026-10-08 | Audit review identified x86 f16 cvtss2si vs cvttss2si rounding mismatch, missing x86 print float stub, and unregistered Group 26 tests; marked for follow-up verification |
