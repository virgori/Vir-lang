---
id: "VIRC-ISS-0016"
type: "ISSUE"
domain: "VIRC"
title: "Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
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
    - "VIR-ISS-0002"
    - "VIRC-ISS-0022"
  plans:
    - "VIRC-PLN-0026"
  reports:
    - "VIRC-RPT-0043"
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

# VIRC-ISS-0016 — Dense tensor lowering loses declared element dtype and miscomputes matmul and FMA

## 1. Summary

The compiler accepts the normative dense tensor element types, but AST-to-MIR
lowering rewrites literal-initialized declarations according to the literal
kind instead of preserving the declared element type. The current runtime then
miscomputes rectangular `**` and both integer and floating-point `><` fixtures.
This is a dense tensor correctness defect, not a request for new syntax.

## 2. Context

VIR-SPC-0018 section 26.1 requires `tensor[T; S...]` to retain parsed
`element_type`, rank, and shape and requires lowering to branch on that parsed
element type. Section 26.2 defines shape-correct matrix multiplication for
`**` and fused accumulation for `><`. The 2026-10-03 audit used the current
dirty working tree at HEAD `e1fc2d54773b83a6be684ec6ab20f403faf0a215` and the
current `./bin/virc`; owner changes were not reset.

## 3. Expected Behavior

- A declared `tensor[f32; ...]`, `tensor[f16; ...]`, `tensor[f64; ...]`,
  `tensor[i8; ...]`, `tensor[u8; ...]`, or `tensor[i32; ...]` retains that
  logical type and physical element width through semantic analysis, MIR, LIR,
  allocation, indexing, operators, and target lowering.
- Literal initialization converts each element to the declared tensor element
  type; it does not change the tensor type.
- Rank-2 `**` and `><` produce the specified row-major result for all supported
  compatible shapes and reject incompatible dtype or shape combinations before
  artifact emission.
- Runtime headers, payload alignment, indexing strides, and autodiff metadata
  agree on the same element representation.

## 4. Actual Behavior

- `compiler/src/lower/ast_to_mir/stmt.vri` replaces a declared tensor type with
  `tensor[f64; ...]` for a floating literal and `tensor[int; ...]` for an
  integer literal.
- The nominal `tensor[f32; 2, 2]` identity-matmul fixture succeeds only while
  reading 8-byte f64 bit patterns at 8-byte strides, demonstrating that the
  declared f32 representation was not retained.
- `tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri` compiles and
  exits successfully but prints four zero values instead of `58`, `64`, `139`,
  and `154`.
- `tests/strict_v2/fma_tensor_e2e.vri` exits with code `12`; the floating
  rectangular FMA fixture exits with code `1`.

## 5. Reproduction

From repository root:

```sh
./bin/virc tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri \
  -O3 -q -o /tmp/vir_tensor_rect
/tmp/vir_tensor_rect

./bin/virc tests/strict_v2/fma_tensor_e2e.vri \
  -O3 -q -o /tmp/vir_tensor_fma_i32
/tmp/vir_tensor_fma_i32

./bin/virc tests/strict_v2/fma_float_rectangular_e2e.vri \
  -O3 -q -o /tmp/vir_tensor_fma_f32
/tmp/vir_tensor_fma_f32

nl -ba compiler/src/lower/ast_to_mir/stmt.vri | sed -n '121,147p'
```

## 6. Evidence

- CONFIRMED: VIR-SPC-0018:3598-3652 defines structured element metadata and
  exact matmul/FMA semantics.
- CONFIRMED: `stmt.vri:121-147` constructs a replacement type from the first
  literal kind and overwrites the declared tensor type used by lowering.
- CONFIRMED: the rectangular `**` artifact printed `0.000000000`, `0.0`,
  `0.000000000`, `0.0` on macOS ARM64 at `-O3`.
- CONFIRMED: integer and floating `><` fixtures returned nonzero failure codes
  `12` and `1` respectively.
- OBSERVED: semantic shape mismatch checks produce `E3014`; the defect is after
  successful frontend validation.
- NOT_VERIFIED: the first wrong MIR instruction, behavior for every supported
  dtype/shape, and parity on Windows, Linux ARM64, RISC-V, or Wasm.

## 7. Scope

### Affected

- dense tensor literal conversion and physical layout;
- AST-to-MIR tensor type propagation and operator result metadata;
- dense `**` and `><` runtime correctness on native targets;
- indexing, alignment, and optimization-level parity for affected element
  widths.

### Not affected / Unknown

- public tensor syntax and the currently working shape diagnostics;
- canonical structural type identity architecture, tracked independently by
  VIR-ISS-0002;
- quantized codecs and packed Q8_0 dispatch;
- native SIMD performance, which is separable from scalar correctness;
- the public `math.tensor` module build failure.

## 8. Impact

This is a core numerical miscompile: accepted programs can produce incorrect
tensor values without a runtime error. It also makes the declared dtype
unreliable for memory sizing and ABI reasoning. The issue is S1/P0 because
correctness must be restored before performance or release claims are trusted.

## 9. Preliminary Analysis

- CONFIRMED: literal-kind rewriting violates the normative requirement to use
  the parsed tensor element type.
- CONFIRMED: rectangular matmul and both FMA fixtures fail their numeric
  oracles with the current compiler.
- HYPOTHESIS: dtype erasure and inconsistent element-width flags contribute to
  the rectangular operator failures; this requires MIR/LIR dumps to prove.
- NOT_VERIFIED: whether one correction can safely fix all operator, indexing,
  and autodiff consumers without a representation migration.

## 10. Acceptance Criteria

- [x] Literal initialization preserves the declared tensor element type and
  performs an explicit checked element conversion where required.
- [x] MIR/LIR carry element type, rank, shape, element width, and layout without
  reconstructing them from literal kind or scanning a serialized type name.
- [x] Registered positive tests cover all six normative element types and prove
  payload width, 64-byte alignment, row-major indexing, and result metadata.
- [x] Rectangular and square `**` and `><` pass exact or tolerance-based numeric
  oracles at O0-O3 on each supported backend.
- [x] Dtype and shape mismatches fail before artifact emission with stable
  diagnostics.
- [x] Mutation controls catch dtype erasure, swapped dimensions, wrong strides,
  scalar width changes, and zero-result regressions.
- [x] Compiler module/bundle synchronization and fixed-point self-host checks
  pass with a newly built compiler.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIR-ISS-0002 — broader canonical typed identity and MIR metadata hardening.
- VIRC-ISS-0022 — Explicit f32 and f64 print dispatch.

### Plans

- VIRC-PLN-0026 — Dense tensor element dtype preservation and matmul FMA lowering repair.

### Reports

- VIRC-RPT-0043 — Dense tensor element dtype preservation and matmul FMA lowering repair report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged from direct dense tensor lowering and runtime audit |
| 2026-10-03 | Linked VIR-ISS-0002 |
| 2026-10-04 | Linked VIRC-ISS-0022 |
| 2026-10-05 | Linked VIRC-PLN-0026 |
| 2026-10-05 | Linked VIRC-RPT-0043 |
| 2026-10-05 | Reopened: audit revealed x86 f32 layout, signed i8 zero-extension, type string scanning, and incomplete fixtures |
| 2026-10-05 | Reopened: audit revealed f16 lowering/matmul defects, false positive fixture, remaining type string scans, x86 runtime oracle requirement, and mutation controls |
| 2026-10-05 | Reopened: independent audit found x86 f16 matmul kernel stride failure (P0), non-IEEE-754 half conversion losing signed zero and subnormals (P1), 28 AST->MIR serialized type scanning sites (P1), and dead TensorTypeMeta residual (P2) |
| 2026-10-05 | Implemented dedicated x86 f16 2-byte loop, full software IEEE-754 half precision conversion, structured tdesc store, removed dead TensorTypeMeta, added f16 rectangular and boundary fixtures, 11/11 mutation controls |
| 2026-10-06 | Reopened: audit identified 8 residual tdesc_from_annotation call sites in AST->MIR lowering; refactored Pass 4 and Pass 6 to attach descriptors to AST nodes, eliminating all string decoding in lowering; criterion 2 left unchecked pending independent audit sign-off |
| 2026-10-06 | Verified and closed: explicit annotations decode once in Pass 4, Pass 6 only fills inferred or missing descriptors, lowering has zero serialized tensor-type scans, the 12-test mutation/propagation suite passes on ARM64 and Linux x86-64, and fixed-point stage2 equals stage3 |
