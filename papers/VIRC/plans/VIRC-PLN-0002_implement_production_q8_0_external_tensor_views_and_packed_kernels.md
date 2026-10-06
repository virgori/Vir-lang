---
id: "VIRC-PLN-0002"
type: "PLAN"
domain: "VIRC"
title: "Implement production Q8_0 external tensor views and packed kernels"
status: "ACTIVE"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "compiler"
  - "stdlib"
components:
  - "tensor"
  - "quantization"
  - "arm64"
  - "simd"
  - "external-storage"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0003"
  plans: []
  reports:
    - "VIRC-RPT-0001"
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

# VIRC-PLN-0002 — Implement production Q8_0 external tensor views and packed kernels

## 1. Objective

Deliver an auditable Q8_0 path for the 40-byte packed format used by the active
Gemma-Vir packer: typed external-storage views, strict validation, scalar
reference kernels, SIMD-dispatched GEMV/GEMM, and structural ARM64 evidence.
Mapped model bytes remain in place and are never unpacked as a whole.

## 2. Source Issues

- VIRC-ISS-0003 — Gemma Q8_0 tensor path lacks production storage and
  optimized kernels.

## 3. Scope

### In Scope

- canonical 40-byte blocks: little-endian f64 scale plus 32 signed int8 values;
- non-owning, read-only external storage metadata with bounds, shape, byte
  strides, alignment, storage kind, and a generation token;
- scalar GEMV/GEMM reference implementations;
- ARM64 SIMD dispatch through the verified Vir `flux` surface, with scalar
  fallback on unsupported or feature-disabled targets;
- stdlib registry integration, executable fixtures, and disassembly evidence.

### Out of Scope

- language syntax or language-specification changes;
- modifying Gemma-Vir or its `.vwm` serialization in this repository;
- Q4/K-quants, activation quantization, or whole-model repacking;
- claiming `sdot`/`udot` before a native int8 dot-product lowering is proven;
- ISSUE closure without real Gemma parity, RSS, throughput, and self-host
  fixed-point evidence.

## 4. Current Architecture

CONFIRMED on 2026-10-02:

- `math.tensor` owns dense f64 tensors and copies external input in
  `tensor_from_data`; it has no packed-storage descriptor.
- `ai.quantize` stores flat int8 values and separate scales, not Gemma blocks.
- the production compiler pipeline reports that legacy Q-IR is bypassed, so no
  packed Q8 metadata currently reaches a kernel dispatcher.
- Gemma-Vir's active `pack_gemma_q8.py` writes f64 scale plus int8[32], while a
  legacy packer writes an incompatible 34-byte f16-scale form.
- `flux of (float, 2)` has existing ARM64 NEON and `--no-simd` contracts.

## 5. Proposed Architecture

Add a registered `math.tensor_q8_0` module. `Q80TensorView` is a non-owning
descriptor over an external byte range. A caller-owned generation cell makes
mapping invalidation observable; every public kernel validates it before
dereferencing. The scalar path is the numerical oracle. The SIMD path uses two
f64 lanes per operation and GEMM batches GEMV without materializing weights.

## 6. Design Decisions

### Decision 1 — One explicit format

**Decision:** Q8_0 means a 40-byte block with f64 scale and int8[32].

**Rationale:** This is the active production model/packer format.

**Alternatives considered:** automatic 34/40-byte detection and f16 scale.

**Trade-offs:** legacy 34-byte data requires a separately named converter.

### Decision 2 — Explicit lifetime token

**Decision:** Each view captures a caller-owned generation cell and value.

**Rationale:** Raw pointers neither own nor extend mmap lifetimes.

**Alternatives considered:** raw pointers, a global mapping table, or copies.

**Trade-offs:** loaders must retain the token and increment it before unmap.

### Decision 3 — Verified `flux` surface

**Decision:** Use two-lane f64 `flux` accumulation on NEON and scalar fallback.

**Rationale:** It is an active, tested compiler surface matching f64 activations.

**Alternatives considered:** consumer unrolling or an unimplemented native ABI.

**Trade-offs:** byte decode remains scalar; no int8-dot claim is made.

## 7. Implementation Plan

### Phase 1 — View contract and scalar oracle

- files/modules: `stdlib/vir/math/tensor_q8_0.vri`, `stdlib/stdlib.vri`, tests;
- changes: typed descriptor, generation/bounds/alignment checks, signed decode,
  scalar GEMV and batched GEMM;
- dependencies: active 40-byte packer and native byte/f64 loads;
- expected result: exact fixtures and malformed descriptors pass without
  unpacking the weight matrix.

### Phase 2 — SIMD dispatch and structural evidence

- files/modules: Q8 module, fixture, structural runner;
- changes: NEON-selected `flux` accumulation, scalar fallback, disassembly and
  mutation controls;
- dependencies: current target/SIMD lowering;
- expected result: scalar/SIMD parity and vector arithmetic in ARM64 code.

### Phase 3 — Compiler metadata and real Gemma evidence

- files/modules: active MIR/LIR pipeline and Gemma-Vir consumer;
- changes: retain packed dtype/storage/shape through typed compiler dispatch,
  migrate the loader/session, and run real model parity/RSS/throughput;
- dependencies: a verified production IR extension point;
- expected result: remaining ISSUE acceptance criteria have direct evidence.

## 8. Compatibility

- no parser, language-spec, or dense `Tensor` ABI change;
- additive public module `math.tensor_q8_0`;
- accepts only the 40-byte format and rejects ambiguous descriptors;
- borrowed, read-only storage remains owned by the caller;
- scalar fallback is the portability contract.

## 9. Migration

Gemma-Vir should replace local 40-byte loops with this module, retain one
generation cell per mapping, and increment it before `munmap`. Its 34-byte
helper must be renamed or converted explicitly; the new API will not guess.

## 10. Validation Plan

- exact signed-codec, scalar GEMV, SIMD parity, and batched GEMM fixtures;
- null, shape, short range, overflow, stride, alignment, writable, wrong-kind,
  and dead-generation negatives;
- ARM64 disassembly plus `--no-simd` output/structure comparison;
- dense tensor, stdlib registry, modular/bundle sync, and paper validation;
- defer closure until real Gemma and self-host evidence exists.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 34/40-byte ambiguity | High | High | One exact format and negative fixture |
| mapping dies before view | Medium | High | Required generation token checked at entry |
| SIMD present but unused | Medium | High | Dispatch, parity, disassembly and mutation checks |
| scalar decode limits speedup | High | Medium | Report precisely; reserve `sdot` for follow-up |

## 12. Rollback Strategy

Remove the additive module, registry entry, and fixtures. Dense tensors,
serialized files, and language behavior remain unchanged.

## 13. Exit Criteria

- [ ] Phase 1 positive and negative contracts pass;
- [ ] Phase 2 parity and structural gates pass;
- [ ] dense tensor and registry regressions pass;
- [ ] REPORT maps every ISSUE criterion and records Phase 3 gaps;
- [ ] ISSUE advances only when its lifecycle gates pass.

## 14. Related Papers

- VIRC-ISS-0003

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Activated from audited Vir and Gemma-Vir sources |
| 2026-10-02 | Linked VIRC-RPT-0001 |
