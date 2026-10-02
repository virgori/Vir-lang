---
id: "VIRC-RPT-0001"
type: "REPORT"
domain: "VIRC"
title: "Q8_0 external tensor view and packed kernel implementation"
status: "DRAFT"
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
    - "VIRC-ISS-0005"
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

# VIRC-RPT-0001 — Q8_0 external tensor view and packed kernel implementation

## 1. Executive Summary

The first production slice is implemented and verified: an additive typed,
borrowed Q8_0 tensor view; one authoritative 40-byte block codec; scalar GEMV;
two-lane ARM64 SIMD GEMV; batched GEMM; generation-based mapping invalidation;
and bit-preserving f64 external loads/stores in ARM64/x86 compiler backends.

The focused self-host build and structural contract pass. The source ISSUE
remains open because compiler `infer:` metadata dispatch, a migrated Gemma-Vir
consumer, Gemma-shaped/model parity, RSS, throughput, unsupported-target
coverage, and fixed-point bootstrap evidence are not yet complete.

## 2. Source Issues

- VIRC-ISS-0003
- VIRC-ISS-0005 — follow-up issue split from the verified active-IR limitation.

## 3. Source Plans

- VIRC-PLN-0002

## 4. Implementation Summary

- Registered `math.tensor_q8_0` without changing dense `Tensor` or language
  syntax.
- Defined f64-le scale plus signed int8[32] as the only accepted Q8_0 block.
- Added a non-owning view with range, shape, stride, alignment, read-only,
  ownership-kind, and caller-owned generation validation.
- Added scalar GEMV, a `flux of (float, 2)` SIMD path, target lowering fallback,
  and batched GEMM without whole-matrix unpacking.
- Mapped typed `native_read_f64`/`native_write_f64` extern calls to the existing
  bit-preserving 64-bit runtime stubs on ARM64 and x86-64.
- Added independent Python codec/negative tests plus an executable structural
  Vir contract.

## 5. Changes by Component

### `stdlib/vir/math/tensor_q8_0.vri`

- change: typed borrowed external view, validation, codec access, scalar/SIMD
  GEMV and batched GEMM;
- reason: replace consumer-local ambiguous layouts and scalar-only loops;
- impact: callers can consume mmap bytes in place under an explicit lifetime
  token and stable validation codes.

### `stdlib/vir/compiler/lir_codegen*.vri`

- change: resolve typed f64 external loads/stores to the existing raw 64-bit
  stubs in ARM64 and x86-64 backends;
- reason: generic `native_load/native_store` calls were not link-resolved by the
  active backend;
- impact: packed scale and dense activation bits cross the external-memory ABI
  without numerical casts.

### `tests/`

- change: independent f64-le codec fixture, validation matrix, semantic API
  fixture, executable GEMV/GEMM fixture, and opcode/fallback runner gate;
- reason: numerical output alone cannot prove vector lowering or safe views;
- impact: one focused command checks output, generation invalidation,
  `fmul.2d`/`fadd.2d`, and `--no-simd` equivalence.

## 6. Deviations from Plan

Phase 1 and the local Phase 2 kernel contract were implemented. Phase 3 was not
attempted: the active compiler reports that legacy Q-IR is bypassed, so adding
an unverified metadata route would not be production evidence. The SIMD path
uses two f64 lanes and scalar byte decode; it does not claim ARM dot-product
instructions. GEMM currently batches the verified GEMV kernel rather than
introducing a separately packed microkernel.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `python3 -m pytest -q tests/test_tensor_q8_0_contract.py` | PASS | 5 passed |
| `python3 tools/gap_contract_runner.py --virc /private/tmp/virc_q80_v2 --filter '^Q80-001$' --verbose` | PASS | exact scalar/SIMD/typed-`infer:`/GEMM output; invalidation code 3; ARM64 `fmul.2d`/`fadd.2d`; x86-64 `mulpd`/`addpd`; `--no-simd` artifacts omit vector math |
| `python3 tools/gap_contract_runner.py --virc /private/tmp/virc_q80_v2 --filter '^AI-006$' --verbose` | PASS | dense rectangular matmul output unchanged |
| `./bin/virc stdlib/vir/compiler/virc.vri --check` | PASS | 0 diagnostics over 592,783 tokens |
| `./bin/virc stdlib/vir/compiler/virc.vri -O1 -o /private/tmp/virc_q80_v2` | PASS | new 27,670,892-byte self-hosted compiler built |
| `python3 tools/sync_virc.py --check` | PASS | modular sources and bundle identical |
| `bash tests/test_stdlib_modules.sh` | BASELINE FAIL | 9 pass; pre-existing `stdlib/vir/error/error.vri` has 5 semantic errors |

### Regression

The first-class dense tensor contract `AI-006` passed with the newly built
compiler. The broader stdlib smoke suite retained its checkpointed unrelated
failure in `error.vri`; no new failure was observed in its nine passing modules.

### Conformance

The public Q8 API semantic fixture passes `virc --check`. The executable fixture
uses the same 40-byte bytes as the independent Python codec and produces
`32/-64` for scalar, SIMD, and typed `infer:` GEMV, `32/-64/64/-128` for
batched GEMM, then returns stable error code `3` after generation invalidation.

## 8. Acceptance Criteria

- [x] One authoritative 40-byte f64-le plus int8[32] layout has an independent
  fixture and malformed descriptor negatives.
- [x] External view validates range/overflow, shape, stride, alignment,
  read-only, borrowed ownership, and generation lifetime.
- [ ] Scalar GEMV/GEMM passes small exact oracles; Gemma-shaped inputs remain
  unverified.
- [ ] macOS ARM64 typed dispatch and vector hot-loop evidence pass locally;
  migrated production Gemma prefill dispatch remains unverified.
- [x] Typed stdlib dispatch from `infer:` is executable and validated. Active
  IR retention of dtype/storage/shape is not implemented and is tracked by
  VIRC-ISS-0005.
- [ ] macOS and x86-64 SIMD/`--no-simd` structures are verified; execution on
  unsupported architectures remains unverified.
- [ ] End-to-end Gemma parity, RSS, throughput, and token evidence are absent.
- [ ] Dense contract and source/bundle sync pass; broader stdlib has a baseline
  failure and fixed-point bootstrap was not run.
- [x] PLAN and REPORT are linked to the ISSUE.

## 9. Known Limitations

- Q8_0 is intentionally only the active 40-byte Gemma-Vir format; legacy
  34-byte f16-scale data is rejected rather than auto-detected.
- Byte decode is scalar. The proven vector operations are f64 lane multiply and
  accumulation, not `sdot`/`udot`.
- The generation cell detects stale mappings only if the loader increments it
  before unmap as required by the API contract.
- No consumer migration or real model artifact was performed in this repo.
- The newly built compiler is retained as temporary verification evidence and
  was not copied over the user's already-modified tracked `bin/virc`.

## 10. Remaining Work

Remaining consumer and release evidence stays on the still-open VIRC-ISS-0003:
Gemma-Vir migration, Gemma-shaped/model measurements, cross-target coverage,
and fixed-point bootstrap. First-class quantized format/shape/storage metadata
and compiler-directed packed dispatch are split into VIRC-ISS-0005 so they can
be designed without blocking use of the explicit stdlib Q8_0 API.

## 11. Conclusion

PARTIALLY_RESOLVED

## 12. Related Papers

- VIRC-ISS-0003
- VIRC-ISS-0005
- VIRC-PLN-0002

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Recorded verified Phase 1 and local Phase 2 implementation; concluded PARTIALLY_RESOLVED |
| 2026-10-02 | Linked VIRC-ISS-0005 |
| 2026-10-02 | Split the active-IR quantized metadata limitation into VIRC-ISS-0005 |
