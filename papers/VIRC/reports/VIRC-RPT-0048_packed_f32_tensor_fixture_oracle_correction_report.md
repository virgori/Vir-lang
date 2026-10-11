---
id: "VIRC-RPT-0048"
type: "REPORT"
domain: "VIRC"
title: "Packed f32 tensor fixture oracle correction report"
status: "ACCEPTED"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
components:
  - "tests"
  - "tensor"
  - "matmul"
related:
  issues:
    - "VIRC-ISS-0059"
  plans:
    - "VIRC-PLN-0031"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "f32"
  - "test-oracle"
  - "verification"
---

# VIRC-RPT-0048 — Packed f32 tensor fixture oracle correction report

## 1. Executive Summary

The two confirmed stale `f32` matmul assertions were corrected without changing
compiler behavior. The focused layout fixture now reconstructs each binary32
word from exactly four payload bytes at offsets 16, 20, 24, and 28. Stage 5 of
the aggregate section 26 proof now checks the result through typed indexing.

The focused fixture passes at O0-O3 on macOS ARM64 and compiles to a static
Linux x86-64 ELF artifact. The aggregate proof passes Stage 5 at O0-O3 and then
fails consistently in Stage 6 with exit code 92, preserving evidence for the
separate width-unaware backward runtime tracked by `VIRC-ISS-0018`. Group 26
improves from 28/37 to 29/37; its eight remaining failures are outside this
report's scope.

## 2. Source Issues

- VIRC-ISS-0059

## 3. Source Plans

- VIRC-PLN-0031

## 4. Implementation Summary

1. Replaced four 8-byte `native_read_i64` payload reads and binary64 expected
   values with four bounded binary32 word reads.
2. Added a local `read_u32_le` helper built from the supported
   `native_read_u8` runtime primitive.
3. Replaced Stage 5 raw payload checks in the aggregate proof with typed
   two-dimensional indexing.
4. Left all backward/gradient assertions unchanged and updated
   `VIRC-ISS-0018` with the newly exposed current failure evidence.

## 5. Changes by Component

### `tests/strict_v2/test_float_matmul_e2e.vri`

- change: read four binary32 words at offsets 16, 20, 24, and 28 using four
  byte reads per word; update expected output to binary32 bit patterns;
- reason: preserve direct physical-width coverage without reading outside the
  packed 16-byte payload;
- impact: the test passes on the current correct packed representation and
  will reject widening or stride regressions.

### `tests/strict_v2/test_spec26_ai_huge_proof.vri`

- change: Stage 5 validates `yi[0, 0]` through `yi[1, 1]` numerically;
- reason: the stage proves infer-mode execution, not payload ABI details;
- impact: Stage 5 passes and Stage 6 now exposes the independent backward
  defect instead of being masked by a stale assertion.

### VPS papers

- change: created and linked `VIRC-ISS-0059`, `VIRC-PLN-0031`, and this report;
  linked the historical dtype repair and active autodiff issue;
- reason: preserve audit evidence and lifecycle traceability;
- impact: the test-only repair has an explicit scope and closure record.

## 6. Deviations from Plan

The plan proposed calling `native_read_i32` directly. Compilation succeeded,
but the executable failed at load time because macOS provides no
`_native_read_i32` symbol for that declaration. The implementation instead
uses the verified `native_read_u8` primitive to reconstruct each little-endian
32-bit word. This still reads exactly four bytes per element, preserves the
intended layout assertion, and compiles for both tested native backends.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Focused layout fixture, O0-O3, macOS ARM64 | PASS | Prints `1065353216`, `1073741824`, `1077936128`, `1082130432` at every level |
| Aggregate proof, O0-O3, macOS ARM64 | EXPECTED BOUNDARY | Stages 1-5 pass; Stage 6 exits 92 from return code 604 |
| Focused layout fixture, Linux x86-64 O3 | COMPILE PASS | Produces a static ELF64 x86-64 executable |
| Group 26 | PARTIAL | 29/37 pass; focused layout fixture changed from FAIL to PASS |

### Regression

The corrected layout test reads no byte beyond offset 31. The unchanged
autodiff fixture still fails at its first gradient check, and the aggregate
proof now reaches the equivalent Stage 6 failure. No compiler source or
generated compiler artifact changed.

### Conformance

The fixtures now agree with VIR-SPC-0018 section 26.1 and the closed
`VIRC-ISS-0016` contract: `tensor[f32]` retains a 4-byte physical element width
through matmul. No normative specification change was required.

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0059`:

- [x] The focused fixture validates binary32 payload words at offsets 16, 20,
  24, and 28 and passes at O0-O3.
- [x] Stage 5 validates the matmul result through typed indexing and advances
  to Stage 6 at O0-O3.
- [x] No changed fixture reads beyond the logical four-element payload.
- [x] Backward/autodiff failures remain unchanged and attributable to
  `VIRC-ISS-0018`.
- [x] Group 26 was rerun; the result is 29/37 and all remaining failures are
  reported as unresolved and out of scope.
- [x] VPS registry and paper validation passed before acceptance and issue
  closure.

## 9. Known Limitations

- Runtime execution was performed on macOS ARM64 only. Linux x86-64 received a
  compile/artifact-format check but was not executed in this run.
- The raw word helper is explicitly little-endian, matching the two current
  native targets covered by the implementation; portable typed semantics are
  covered separately by Stage 5.
- Group 26 remains red because of eight independent compiler and fixture
  failures.

## 10. Remaining Work

`VIRC-ISS-0018` continues to own the width-aware, shape-aware, graph-general
autodiff runtime repair. Quantization and unrelated print/first-class tensor
failures were not classified by this report.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0059 — Packed f32 tensor fixtures retain stale f64 layout oracles.
- VIRC-PLN-0031 — Correct packed f32 tensor test oracles without masking
  autodiff defects.
- VIRC-ISS-0016 — Dense tensor dtype and physical-width preservation repair.
- VIRC-ISS-0018 — Active infer/train/autodiff runtime gaps.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Recorded implementation, O0-O3 evidence, Group 26 boundary, and native-read deviation for review |
| 2026-10-08 | Accepted after synchronized registry and clean VPS validation |
