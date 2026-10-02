---
id: "VIRC-ISS-0003"
type: "ISSUE"
domain: "VIRC"
title: "Gemma Q8_0 tensor path lacks production storage and optimized kernels"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "compiler"
  - "stdlib"
components:
  - "tensor"
  - "quantization"
  - "qir"
  - "arm64"
  - "simd"
  - "memory-mapping"
  - "tests"
related:
  issues: []
  plans:
    - "VIRC-PLN-0002"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "gemma"
  - "q8-0"
  - "tensor-view"
  - "gemv"
  - "gemm"
  - "neon"
---

# VIRC-ISS-0003 — Gemma Q8_0 tensor path lacks production storage and optimized kernels

## 1. Summary

Vir already has dense tensor storage, first-class dense matmul checks, a tiled
standard-library matmul, and general SIMD infrastructure. The Gemma consumer
also has mmap-backed `TensorView` and scalar Q8_0 routines. The remaining gap is
a production Vir Q8_0 storage/view contract and optimized Q8_0 GEMV/GEMM path
that consumes mapped model bytes, participates in `infer:`/Q-IR, and is proven
on Gemma shapes. This ISSUE excludes completed dense tensor work and records
only that missing path.

## 2. Context

`docs/plan/STRICT_V2_GEMMA_VIR_Q8_0_TENSOR_MATMUL_PROMPT.md` was written after
Gemma-Vir paused on packed projections. Audit on 2026-10-02 covered the active
Vir tree and the consumer at `/Users/gengyang/Desktop/Repo/Gemma-Vir`. The
consumer is evidence of integration needs, not a substitute for a compiler or
stdlib implementation.

## 3. Expected Behavior

- A typed external-storage tensor/view carries base pointer, byte length,
  element/storage kind, shape, strides, alignment, ownership, and lifetime.
- Q8_0 block layout has one authoritative byte-level contract and rejects
  malformed dimensions, offsets, lengths, and alignment.
- Decode dispatches Q8_0 weight × dense activation to an optimized macOS ARM64
  GEMV; prefill has an optimized GEMM/batched path, both with scalar oracles.
- `infer:` operations lower through typed tensor/Q-IR dispatch rather than a
  consumer-only scalar pointer loop.
- Model bytes remain mmap-backed without full-model unpack/repack, and mapping
  lifetime outlives every view.

## 4. Actual Behavior

- `stdlib/vir/math/tensor.vri` provides owned dense `Tensor`, external
  `tensor_from_data`, naive matmul, and a tiled scalar matmul over f64 loads.
- Compiler tensor intrinsics cover allocation/get/set and first-class shape/type
  checks, but no production Q8_0 storage descriptor or Q8 GEMV/GEMM intrinsic
  was found in active Vir source.
- Gemma-Vir defines its own `TensorView`, quant enum, mmap loader, and Q8 loops.
- The consumer file named `neon_gemv.vri` implements Q8 arithmetic with scalar
  byte loads and scalar accumulators; no NEON vector operations are present in
  the audited Q8 loops.
- That consumer contains two incompatible Q8 layouts: a 40-byte block with f64
  scale in `gemvQ80BlockDot`/`gemvQ80MatrixVectorTiled4`, and a 34-byte f16-scale
  block in `gemvQ80Row`, while `Q8_0_BYTE_SIZE` is 34.
- No registered Vir contract/benchmark links an official Q8 descriptor through
  Q-IR to disassembled vector code and Gemma parity.

## 5. Reproduction

```sh
rg -n "Q8_0|Q80|q8_0|gemv|gemm|TensorView" \
  stdlib/vir core tests tools \
  --glob '!stdlib/vir/compiler/virc.vri' --glob '!frozen/**'
sed -n '307,430p' stdlib/vir/math/tensor.vri
sed -n '1280,1395p' stdlib/vir/math/tensor.vri
sed -n '1,290p' \
  /Users/gengyang/Desktop/Repo/Gemma-Vir/src/kernel/arm64/neon_gemv.vri
rg -n "Q8_0|Q80|TensorView|gemv|gemm|infer:" \
  /Users/gengyang/Desktop/Repo/Gemma-Vir/src --glob '*.vri'
```

The first search finds dense tensor/SIMD infrastructure but no production Vir
Q8 tensor kernel. Consumer source shows scalar byte loops and the conflicting
34/40-byte block assumptions.

## 6. Evidence

- CONFIRMED: `stdlib/vir/math/tensor.vri:307` defines dense `Tensor`, line 380
  wraps external data, and lines 1280-1395 implement naive/tiled dense matmul.
- CONFIRMED: MIR exposes tensor alloc/get/set intrinsics, not a Q8 storage/GEMV/
  GEMM contract.
- CONFIRMED: Gemma-Vir `src/tensor/tensor.vri` defines consumer-local
  `TensorView`; `src/model/loader.vri` binds it to mmap offsets.
- CONFIRMED: Gemma-Vir `src/kernel/arm64/neon_gemv.vri:42-214` uses scalar
  `read_byte`/`loadF64` loops and assumes 40-byte blocks for the active tiled
  routine.
- CONFIRMED: the same file at `:216-257` assumes 34-byte f16-scale blocks, and
  `src/quant/block.vri:7-8` declares 34 bytes.
- OBSERVED: generic NEON/SIMD and dense matmul tests exist in Vir, but none are
  Q8 Gemma projection evidence.
- NOT_VERIFIED: numerical parity on the production model, optimized assembly,
  throughput/RSS claims, prefill batching, or cross-target fallbacks.

## 7. Scope

### Affected

- external-storage tensor/view ABI and lifetime validation needed by mmap;
- authoritative Q8_0 codec/storage descriptor and typed dispatch;
- scalar reference plus optimized ARM64 GEMV/GEMM;
- `infer:`/Q-IR integration, feature gating, parity, mutation, and benchmark
  evidence on Gemma dimensions.

### Not affected / Already complete

- dense owned tensor allocation/indexing and basic shape checks;
- existing dense naive/tiled matmul functionality;
- general-purpose SIMD infrastructure unrelated to Q8 projection;
- consumer-local mmap loader, view facade, and scalar prototypes;
- new public syntax or language-spec changes, which are out of scope unless
  separately authorized.

## 8. Impact

Gemma-Vir cannot rely on a release-qualified, compiler/stdlib-owned packed
projection path and instead carries contradictory scalar kernels. This blocks
the intended zero-copy performance path and makes byte-layout mistakes capable
of silent numerical corruption. A scalar consumer workaround exists, so this
is classified S2/P1 rather than a broad compiler correctness failure.

## 9. Preliminary Analysis

- CONFIRMED: dense tensor/matmul foundations are implemented and should be
  preserved rather than re-planned.
- CONFIRMED: the consumer's “neon” Q8 path is tiled scalar code and cannot serve
  as vectorization evidence.
- CONFIRMED: block-size disagreement must be resolved from the model/packer
  authority before implementing the production codec.
- HYPOTHESIS: a target-neutral typed storage descriptor plus Q8 operation in
  Q-IR can share validation/scalar reference while dispatching native kernels.
- NOT_VERIFIED: whether the best prefill implementation should reuse a GEMV
  microkernel or introduce a distinct packed GEMM layout.

## 10. Acceptance Criteria

- [ ] One authoritative Q8_0 byte layout is documented from actual model and
  packer bytes, with independent codec fixtures and malformed-input negatives.
- [ ] External storage/view validates byte length, offset overflow, shape,
  stride, alignment, read-only state, ownership, and mmap lifetime.
- [ ] Scalar Q8_0 GEMV/GEMM references pass exact/tolerance oracles on small and
  Gemma-shaped inputs without unpacking the full model.
- [ ] macOS ARM64 optimized GEMV and prefill GEMM are invoked through production
  typed dispatch; disassembly and mutation controls prove vector hot loops.
- [ ] `infer:`/Q-IR retains dtype/storage/shape metadata and cannot bypass into
  an untyped scalar fallback silently.
- [ ] Feature-disabled and unsupported targets use verified scalar fallback or
  stable diagnostics according to the support matrix.
- [ ] End-to-end Gemma layer/logit/token parity, RSS, throughput, and artifact
  evidence is recorded using a newly built self-hosted compiler.
- [ ] Dense tensor regressions, modular/bundle sync, and fixed-point bootstrap
  remain green.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from Vir plus Gemma-Vir audit; excluded completed dense tensor and consumer prototype work |
| 2026-10-02 | Linked VIRC-PLN-0002 |
