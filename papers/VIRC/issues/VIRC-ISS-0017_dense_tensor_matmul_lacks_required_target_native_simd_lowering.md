---
id: "VIRC-ISS-0017"
type: "ISSUE"
domain: "VIRC"
title: "Dense tensor matmul lacks required target native SIMD lowering"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-03"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "tensor"
  - "simd"
  - "mir"
  - "lir"
  - "arm64"
  - "x86-64"
  - "wasm"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0036"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "matmul"
  - "simd"
  - "neon"
  - "avx512"
  - "wasm-simd"
  - "performance"
---

# VIRC-ISS-0017 — Dense tensor matmul lacks required target native SIMD lowering

## 1. Summary

Dense tensor `**` and `><` lower to scalar triple-loop runtime stubs rather than
the target-native SIMD/tensor operations required by the active language
specification. General `flux` SIMD infrastructure exists, but it is not used by
the production dense matmul path and does not prove tensor operator compliance.

## 2. Context

VIR-SPC-0018 section 26.2 states that `**` maps to ARM NEON FMMLA, x86 AVX-512
DPBF16, or Wasm simd128 dot-product operations. This ISSUE is limited to dense
tensor operators. Packed Q8_0 kernels and compiler-directed quantized dispatch
remain under their existing issues.

## 3. Expected Behavior

- Dense tensor matmul selects a verified kernel compatible with dtype, shape,
  alignment, target ISA, and enabled feature set.
- Supported native targets use vector accumulation and documented scalar tails;
  unsupported combinations take a correct scalar fallback or emit a stable
  unsupported-target diagnostic according to an approved support matrix.
- `--no-simd` disables vector kernels without changing numeric results.
- Disassembly and mutation tests prove the intended hot loop rather than merely
  proving that unrelated vector instructions exist in the artifact.

## 4. Actual Behavior

- ARM64 integer matmul uses scalar `madd`; floating matmul uses scalar
  `fmadd d...` inside a three-level loop.
- x86-64 integer matmul uses scalar `imul`; floating matmul uses scalar
  `mulsd` followed by `addsd`.
- An O3 macOS ARM64 dense matmul artifact contains no FMMLA, FMLA, SDOT, UDOT,
  or vector f32/f64 multiply-add instruction in the tensor kernels.
- An O3 Linux x86-64 ELF artifact contains scalar matmul instructions and no
  DPBF16 or vector FMA in the tensor kernels.
- The Wasm target rejects the rectangular matmul fixture with
  `E-WASM-UNSUPPORTED` for LIR op 25.

## 5. Reproduction

```sh
./bin/virc tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri \
  -O3 -q -o /tmp/vir_tensor_arm64
otool -tvV /tmp/vir_tensor_arm64

./bin/virc tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri \
  -O3 --target linux-x86_64 --format elf -q \
  -o /tmp/vir_tensor_x86.elf
llvm-objdump -d /tmp/vir_tensor_x86.elf

./bin/virc tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri \
  -O3 --target wasm32-wasi-p1 --format wasm -q \
  -o /tmp/vir_tensor.wasm

nl -ba compiler/src/lower/lir_codegen/rt_stubs_math/matmul.vri | \
  sed -n '84,177p;241,327p'
nl -ba compiler/src/lower/lir_codegen_x86/rt_stubs_math/tensor.vri | \
  sed -n '79,155p;222,309p'
```

## 6. Evidence

- CONFIRMED: VIR-SPC-0018:3633-3652 specifies target-native SIMD mapping.
- CONFIRMED: the ARM64 runtime source implements scalar index calculation,
  scalar element loads, and scalar accumulation.
- CONFIRMED: the x86-64 runtime source implements scalar element loads and
  scalar integer or SSE2-double accumulation.
- CONFIRMED: ARM64 O3 disassembly contained scalar `madd x...` and `fmadd d...`
  but none of the required vector hot-loop operations.
- CONFIRMED: x86-64 ELF disassembly contained `mulsd`/`addsd` and no DPBF16 or
  vector matmul instruction in the tensor path.
- CONFIRMED: the current Wasm backend could not lower the tested dense matmul.
- NOT_VERIFIED: target hardware throughput, cache behavior, vector tail safety,
  and instruction availability on all CPU generations.

## 7. Scope

### Affected

- dense `**` and `><` kernel selection and target lowering;
- dtype/shape-aware SIMD dispatch, scalar tails, and feature gating;
- ARM64, x86-64, and Wasm structural and runtime evidence;
- optimizer preservation of tensor kernel metadata.

### Not affected / Unknown

- dense scalar numerical correctness, tracked separately;
- general-purpose `flux` SIMD operations unrelated to tensor matmul;
- Q8_0 byte decode, packed storage, Gemma integration, and quantized metadata;
- GPU/NPU backends not present in the current supported target list.

## 8. Impact

The compiler does not deliver a normative AI/ML performance contract and Wasm
cannot currently emit the tested tensor operation. Scalar native fallback can
serve as a correctness path once corrected, so this is S2/P1 rather than a
standalone correctness blocker.

## 9. Preliminary Analysis

- CONFIRMED: production dense matmul bypasses the existing general vector
  lowering and calls scalar runtime stubs.
- CONFIRMED: source and disassembly disagree with the active SIMD claim.
- HYPOTHESIS: a target-neutral tensor-kernel selection layer can reuse MIR
  vector metadata while keeping scalar reference kernels.
- NOT_VERIFIED: the appropriate tiling, packing, and ISA baseline for each
  dtype and target.

## 10. Acceptance Criteria

- [ ] An approved target/dtype capability matrix defines vector kernels,
  feature checks, scalar tails, fallbacks, and stable diagnostics.
- [ ] ARM64 dense matmul emits and executes the approved NEON hot loop with
  scalar tail coverage and exact/tolerance parity against a scalar oracle.
- [ ] x86-64 dense matmul emits the approved AVX/AVX-512 hot loop only when CPU
  features permit it and otherwise selects a verified fallback.
- [ ] Wasm dense matmul either emits the specified simd128 path or reports the
  approved unsupported capability before artifact emission.
- [ ] `--no-simd` artifacts omit vector tensor instructions while producing the
  same numeric results.
- [ ] Disassembly gates are scoped to the tensor kernel and mutation controls
  fail for scalar-only, wrong-width, missing-tail, or wrong-dispatch variants.
- [ ] Benchmarks record shapes, dtypes, hardware, warmup, repetitions, and
  scalar-versus-vector throughput without replacing correctness gates.
- [ ] O0-O3, module/bundle sync, and fixed-point self-host regressions pass.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None yet.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged from source and O3 disassembly audit of dense tensor matmul |
| 2026-10-04 | Linked VIRC-ISS-0036 |
