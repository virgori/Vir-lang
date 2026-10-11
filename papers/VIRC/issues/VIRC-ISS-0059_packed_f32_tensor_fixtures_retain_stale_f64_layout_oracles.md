---
id: "VIRC-ISS-0059"
type: "ISSUE"
domain: "VIRC"
title: "Packed f32 tensor fixtures retain stale f64 layout oracles"
status: "CLOSED"
severity: "S2"
priority: "P0"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
components:
  - "tests"
  - "tensor"
  - "matmul"
  - "arm64"
  - "x86-64"
related:
  issues:
    - "VIRC-ISS-0016"
    - "VIRC-ISS-0018"
  plans:
    - "VIRC-PLN-0031"
  reports:
    - "VIRC-RPT-0048"
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "f32"
  - "layout"
  - "test-oracle"
  - "regression"
---

# VIRC-ISS-0059 — Packed f32 tensor fixtures retain stale f64 layout oracles

## 1. Summary

Several strict tensor fixtures still interpret `tensor[f32]` payloads as
8-byte IEEE-754 `f64` values after `VIRC-ISS-0016` changed dense `f32` storage
to the required packed 4-byte representation. The stale oracles make correct
matmul output fail the test suite and can hide separate runtime defects behind
the first obsolete assertion.

## 2. Context

VIR-SPC-0018 section 26.1 defines `tensor[T; S...]` as carrying a structured
element type and row-major aligned storage. `VIRC-ISS-0016` closed after dense
tensor lowering and native matmul were changed to preserve the physical width
of `f32`, `f16`, and `f64` rather than widening every floating payload to
`f64`.

The current ARM64 and x86-64 paths encode `f32` as a 4-byte element. Some
fixtures created before that repair still call `native_read_i64` at 8-byte
strides and compare the result with `f64` bit patterns.

## 3. Expected Behavior

- Semantic tensor tests observe results through typed indexing and remain
  independent of private payload width.
- Physical-layout tests read `f32` payloads as 32-bit values at offsets
  `16 + index * 4` and compare them with binary32 bit patterns.
- Tests do not read beyond the logical payload.
- Autodiff tests that expose an actual width-unaware backward runtime remain
  failing evidence for `VIRC-ISS-0018`; their oracles are not weakened merely
  to make the group green.

## 4. Actual Behavior

- `tests/strict_v2/test_float_matmul_e2e.vri` reads four `f32` results with
  `native_read_i64` at offsets 16, 24, 32, and 40 and expects four `f64`
  bit-pattern integers.
- Stage 5 of `tests/strict_v2/test_spec26_ai_huge_proof.vri` repeats the same
  stale reads, so the aggregate proof exits before reaching the independently
  broken backward stage.
- The current packed result contains four binary32 values at offsets 16, 20,
  24, and 28. A 64-bit read at offset 16 therefore combines `1.0f` and `2.0f`;
  reads at 32 and 40 are outside the logical payload.

## 5. Reproduction

At revision `930d21eef3e63b8bae7b748a35e6e8c00f72215b` on macOS ARM64:

```sh
./bin/virc tests/strict_v2/test_float_matmul_e2e.vri \
  -O3 -q -o /private/tmp/virc_iss_0059_repro
/private/tmp/virc_iss_0059_repro

./run_tests.sh 26
```

The focused fixture prints:

```text
4611686019492741120
4647714816524288000
0
0
```

Group 26 reports 28/37 passing and includes an output mismatch for this
fixture.

## 6. Evidence

- CONFIRMED: `raw_tensor_elem_byte_size` maps the `f32` descriptor code to 4
  bytes in `compiler/src/semantic/types/tensor.vri`.
- CONFIRMED: tensor literal lowering allocates `16 + n * elem_sz` and emits
  typed element stores in `compiler/src/lower/ast_to_mir/builder.vri`.
- CONFIRMED: ARM64 and x86-64 matmul pass a 32-bit width code, allocate 4 bytes
  per result element, and use single-precision load/compute/store operations.
- CONFIRMED: `4611686019492741120` is `0x400000003f800000`, the little-endian
  concatenation of binary32 `1.0f` and `2.0f`; `4647714816524288000` is
  `0x4080000040400000`, the concatenation of `3.0f` and `4.0f`.
- CONFIRMED: `tests/strict_v2/tensor_supported_types_positive.vri` passes at
  O0, O1, O2, and O3 with the current compiler.
- OBSERVED: `test_autodiff_e2e.vri` also fails, but inspection shows that the
  backward runtime itself still allocates 8-byte gradient slots and reads
  `f32` operands with 8-byte loads. That is real compiler behavior tracked by
  `VIRC-ISS-0018`, not a stale-oracle-only failure.

## 7. Scope

### Affected

- direct raw-layout assertions for dense `f32` tensor results;
- Stage 5 of the aggregate section 26 proof;
- Group 26 signal quality and regression triage.

### Not affected / Unknown

- dense `f32` literal and matmul storage, which currently uses 4-byte payloads;
- `test_autodiff_e2e.vri` and Stage 6 backward assertions, which expose the
  separate `VIRC-ISS-0018` runtime defect;
- quantized tensor failures and unrelated float-print fixtures;
- Windows, RISC-V, and Wasm execution, not verified in this audit.

## 8. Impact

Correct `f32` matmul behavior is reported as a regression, Group 26 remains
red for the wrong first cause, and later real failures are masked by early
returns. The defect affects verification reliability rather than emitted
tensor code, so it is S2/P0.

## 9. Preliminary Analysis

- CONFIRMED: the main matmul fixture must keep a raw physical-layout oracle but
  change to 32-bit reads at 4-byte strides.
- CONFIRMED: the aggregate infer-stage fixture should use typed tensor indexing
  because its purpose is zero-tape execution, not ABI layout.
- CONFIRMED: changing backward gradient expectations would mask a compiler
  defect and is outside this issue.
- NOT_VERIFIED: whether additional fixtures outside Group 26 contain the same
  stale raw-layout assumption.

## 10. Acceptance Criteria

- [x] The focused `f32` identity-matmul fixture validates binary32 payload bits
  at offsets 16, 20, 24, and 28 and passes at O0-O3.
- [x] Stage 5 of the section 26 aggregate proof validates the same numeric
  result through typed indexing and advances to Stage 6.
- [x] No changed fixture reads beyond the logical four-element `f32` payload.
- [x] Backward/autodiff failures remain attributable to `VIRC-ISS-0018` and are
  not converted into passing oracles.
- [x] Group 26 is rerun and its remaining failures are reported without
  claiming unrelated defects are resolved.
- [x] VPS registry and paper validation pass with linked PLAN and REPORT
  evidence before closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0016 — Dense tensor dtype and physical-width preservation repair.
- VIRC-ISS-0018 — Remaining width-unaware and graph-incomplete autodiff
  runtime behavior.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Created and triaged from deterministic packed-f32 fixture failures and source audit |
| 2026-10-08 | Linked VIRC-ISS-0016 |
| 2026-10-08 | Linked VIRC-ISS-0018 |
| 2026-10-08 | Activated VIRC-PLN-0031 and started scoped fixture correction |
| 2026-10-08 | Verified all criteria, accepted VIRC-RPT-0048, and closed after clean VPS validation |
| 2026-10-08 | Linked VIRC-PLN-0031 |
| 2026-10-08 | Linked VIRC-RPT-0048 |
