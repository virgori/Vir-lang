---
id: "VIRC-ISS-0005"
type: "ISSUE"
domain: "VIRC"
title: "Quantized tensors lack format, shape, and storage metadata"
status: "CLOSED"
severity: "S2"
priority: "P1"
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
    - "VIRC-ISS-0003"
    - "VIRC-ISS-0019"
  plans:
    - "VIRC-PLN-0003"
  reports:
    - "VIRC-RPT-0001"
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

# VIRC-ISS-0005 — Quantized tensors lack format, shape, and storage metadata

## 1. Summary

Vir has a distinct `TypeKind.QuantizedTensor`, validates
`quantize(tensor, bits: N)`, and lowers it to compact runtime storage. That
type-state does not identify the quantization format, preserve the source
tensor's static shape in its type, describe physical blocks/strides, or carry
external-storage ownership and lifetime. The implemented `Q80TensorView` is
therefore an ordinary stdlib entity and Q8_0 GEMV/GEMM remain ordinary calls,
not first-class packed-tensor operations selected and verified by compiler IR.

## 2. Context

VIRC-ISS-0003 introduced a production 40-byte Q8_0 view and verified packed
kernels without changing language syntax. Its implementation report records
that the active IR metadata route remains absent. This ISSUE splits that
compiler/type-system concern from the completed stdlib storage and local kernel
slice so the existing implementation can be consumed now while first-class
packed-tensor semantics are designed independently.

This ISSUE does not assume that `Q8_0` becomes a legal element token in
`tensor[T; S...]`. The active language specification defines `T` as the logical
element type and the remainder as a static shape. Any new public syntax or
normative semantic change requires an explicitly authorized VIR SPEC revision;
an internal compiler descriptor and typed stdlib boundary may be sufficient.

## 3. Expected Behavior

- A quantized tensor descriptor retains logical element type, rank, dimensions,
  logical layout, quantization/codec identity, physical block size and byte
  strides, alignment, and mutability.
- Borrowed external storage additionally retains byte range, ownership and
  lifetime/invalidation facts needed to validate mmap-backed views.
- Semantic analysis and the active MIR/LIR path preserve this descriptor across
  variables, `infer:` boundaries, calls, optimization, and target lowering.
- Packed tensor operations select only kernels compatible with their codec,
  activation type, dimensions, layout, and target; incompatible combinations
  produce stable diagnostics instead of silently falling back to an untyped
  pointer loop.
- Existing dense `tensor[T; S...]` and generic `quantize(..., bits: N)` behavior
  remain source-compatible unless a separately approved SPEC says otherwise.

## 4. Actual Behavior

- `TypeKind.QuantizedTensor` is one undifferentiated compiler kind. Variables
  initialized by `quantize` are recorded as the string `QuantizedTensor`, so the
  resulting type identity does not contain source shape, logical dtype, codec,
  or storage layout.
- Semantic analysis temporarily recovers the input annotation through the AST
  to validate that `quantize` receives a floating-point tensor, but this is not
  a persistent typed descriptor passed into MIR/LIR.
- MIR lowering supplies only the bit count to `MIR_INTR_QUANTIZE`; the active
  runtime layout stores `numel`, `bits`, one scale, and packed bytes.
- The Q8_0 stdlib API exposes `Q80TensorView` plus `q80Gemv*`/`q80Gemm`, but the
  compiler does not classify that entity as `QuantizedTensor`, retain its
  40-byte block contract in IR, or select those kernels from tensor operators.
- Consequently, a typed `infer:` block can execute the stdlib calls, but that
  proves call/type checking only; it does not prove packed tensor metadata or
  compiler-directed Q8_0 dispatch.

## 5. Reproduction

```sh
rg -n "QuantizedTensor|QuantizeExpr|MIR_INTR_QUANTIZE|rt_quantize" \
  stdlib/vir/compiler --glob '!virc.vri'
sed -n '20,160p' stdlib/vir/compiler/type_table.vri
sed -n '1440,1505p' stdlib/vir/compiler/sem_pass6_typecheck.vri
sed -n '4435,4515p' stdlib/vir/compiler/sem_pass6_typecheck.vri
sed -n '3650,3735p' stdlib/vir/compiler/ast_to_mir.vri
sed -n '3455,3505p' stdlib/vir/compiler/lir_codegen.vri
rg -n "Q80TensorView|q80Gemv|q80Gemm" \
  stdlib/vir/math/tensor_q8_0.vri stdlib/stdlib.vri
rg -n "tensor\\[T; S|26\\.5|quantize" \
  papers/VIR/specs/VIR-SPC-0017_language_specification_english.md
```

The searches show the generic quantized type-state and runtime stub, but no
compiler descriptor or lowering path that names Q8_0, its 40-byte blocks,
external ownership/lifetime, or packed-kernel dispatch.

## 6. Evidence

- CONFIRMED: `stdlib/vir/compiler/type_table.vri` defines
  `TypeKind.QuantizedTensor`, while `TypeNode` tensor helpers model element type,
  rank, and shape only for `TypeKind.Tensor`; no quantization-format or physical
  storage fields exist.
- CONFIRMED: `sem_pass6_typecheck.vri` validates quantize input shape/type via
  `pass6_tensor_type_name`, then records the result as the undifferentiated
  `QuantizedTensor` type-state.
- CONFIRMED: `ast_to_mir.vri` lowers quantization as
  `MIR_INTR_QUANTIZE(input, bits)` without shape, codec, block, stride,
  ownership, or lifetime operands.
- CONFIRMED: ARM64 `lir_codegen.vri` documents the runtime result as
  `{numel, bits, scale, reserved, packed bytes}`; this is generic uniform
  quantization, not the stdlib Q8_0 block contract.
- CONFIRMED: `stdlib/vir/math/tensor_q8_0.vri` defines `Q80TensorView` and
  exported GEMV/GEMM functions; `stdlib/stdlib.vri` registers the module.
- CONFIRMED: VIR-SPC-0017 §26.1 defines `tensor[T; S...]` as logical element
  type plus static shape, and §26.5 defines `quantize(..., bits: N)` without a
  named Q8_0 packed format.
- OBSERVED: the focused Q8_0 contract executes scalar/SIMD/GEMM calls from a
  typed `infer:` block, while VIRC-RPT-0001 explicitly records that active IR
  retention of dtype/storage/shape is not implemented.
- NOT_VERIFIED: the appropriate public syntax, if any; the final internal IR
  schema; automatic operator dispatch policy; or compatibility with real
  Gemma-Vir model artifacts.

## 7. Scope

### Affected

- compiler quantized-tensor type representation and symbol propagation;
- semantic compatibility rules and stable diagnostics;
- MIR/LIR metadata, dumps, verification, optimization preservation, and target
  lowering;
- `infer:` packed operation dispatch and scalar/optimized fallback policy;
- external borrowed storage ownership, lifetime, bounds, alignment, layout,
  and invalidation integration;
- Q8_0 integration tests plus dense/generic-quantize regressions.

### Not affected / Unknown

- the existing 40-byte Q8_0 codec, `Q80TensorView`, and packed kernels;
- existing dense tensor syntax, layout, operators, and allocation;
- consumer migration and full-model benchmarks, which remain on
  VIRC-ISS-0003;
- public language syntax or normative SPEC changes until separately approved;
- additional quantization codecs beyond what an approved design explicitly
  includes.

## 8. Impact

Gemma-Vir can call the stdlib Q8_0 API explicitly, but the compiler cannot prove
that a packed value's format and shape match the selected kernel, preserve that
identity through the active IR, or optimize/diagnose packed tensor operations
as a coherent type. Integrators must manually pair bytes, descriptors, and
functions, leaving format mismatch and silent fallback risks. A validated
stdlib workaround exists, so the issue is S2/P1 rather than a broad compiler
correctness failure.

## 9. Preliminary Analysis

- CONFIRMED: Vir supports a generic quantized type-state; it does not yet
  support Q8_0 as a first-class packed tensor type/descriptor.
- CONFIRMED: logical tensor shape is recoverable from the input AST during one
  semantic check but is not represented by the resulting `QuantizedTensor`
  identity or quantize MIR instruction.
- CONFIRMED: the stdlib view already contains most runtime validation facts, so
  this issue should integrate or reference that contract rather than duplicate
  its codec and kernels.
- HYPOTHESIS: a target-neutral packed tensor descriptor associated with typed
  values can support Q8_0 without adding a new public tensor syntax.
- HYPOTHESIS: compiler-recognized typed stdlib operations may provide a safer
  incremental route than immediately overloading dense `**`.
- NOT_VERIFIED: whether generic `quantize(..., bits: 8)` should ever be
  assignment-compatible with the 40-byte Q8_0 format; they currently have
  different physical layouts and must not be treated as equivalent by default.

## 10. Acceptance Criteria

- [x] An approved design identifies whether packed metadata is internal-only or
  requires a separately authorized VIR SPEC revision; this ISSUE alone does not
  introduce public syntax.
- [x] The compiler represents logical dtype, rank/shape/layout and physical
  codec/block/byte-stride/alignment metadata for quantized values without
  collapsing all formats to the string `QuantizedTensor`.
- [x] Borrowed external packed values carry bounds, read-only state, ownership,
  lifetime/invalidation, and target-relevant alignment facts through semantic
  analysis and the active IR.
- [x] Deterministic semantic/MIR/LIR dump tests prove metadata survives variable
  binding, calls, `infer:`, optimization, and target lowering.
- [x] Q8_0 GEMV/GEMM dispatch accepts only compatible activation dtype, shape,
  codec, layout, and output bounds; each mismatch has a stable negative test.
- [x] Dispatch reaches the verified Q8_0 scalar/SIMD implementation or emits a
  stable unsupported-target diagnostic; it cannot silently erase metadata and
  take an unrelated untyped fallback.
- [x] Generic `quantize(..., bits: N)` and dense tensor contracts remain green,
  and tests prove generic 8-bit quantization is not implicitly reinterpreted as
  the 40-byte Q8_0 block format.
- [x] Modular/bundle sync and fixed-point self-host verification pass with the
  new metadata path.
- [x] A VPS PLAN and REPORT link this ISSUE before resolution or closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0003 — stdlib Q8_0 external view, packed kernels, and Gemma
  integration/measurement work from which this compiler gap was split.

### Plans

- VIRC-PLN-0003 — Implementation plan for first-class quantized tensor metadata and typed dispatch

### Reports

- VIRC-RPT-0001 — implementation evidence that identifies missing active IR
  retention of dtype/storage/shape.
- VIRC-RPT-0035 — Quantized tensor metadata and transparent inference implementation report

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from the VIRC-ISS-0003 implementation audit; scoped to first-class quantized metadata and typed dispatch without changing language syntax |
| 2026-10-02 | Linked VIRC-ISS-0003 |
| 2026-10-02 | Linked VIRC-RPT-0001 |
| 2026-10-02 | Linked VIRC-PLN-0003; advanced status to IMPLEMENTING |
| 2026-10-03 | Linked VIRC-ISS-0019 |
| 2026-10-04 | Linked VIRC-RPT-0035 |
| 2026-10-04 | Reopened to IMPLEMENTING following audit: resolving x86 quantized matmul stub, MIR/LIR metadata propagation, active dump inspection flags, floating-point dequantization inference, and dedicated Q8_0/negative contract test suites |
| 2026-10-04 | Completed all 6 audit items, verified 3-stage bootstrap fixed-point convergence, and marked CLOSED |
| 2026-10-05 | Addressed second-phase audit defects: isolated MIR bits from SSA memory epochs, implemented dedicated LIR metadata fields, corrected Q80-005 output buffer length testing, verified compiler dispatch and x86 execution in Docker, and re-closed with complete reproducible evidence |
| 2026-10-05 | Addressed third-phase audit findings: carried Q8_0 external-view metadata (codec=2, bits=8, size=40, align=8) into active IR, added variable type dump to --dump-semantic, unwrapped activation type in q80Gemv for negative testing (Q80-004), verified dynamic buffer length error propagation (Q80-005), added automated pytest regression suite, and verified bit-for-bit SHA-256 match across stages 1/2/3 |
| 2026-10-05 | Reopened after fourth audit found that bounds/ownership/lifetime were present only in semantic text, block bytes and row stride shared one legacy field, LIR did not consume the descriptor, and the regression count had no executable baseline gate |
| 2026-10-05 | Re-closed after adding the 16-field `MirQuantMeta` descriptor, distinct block/stride and external-view facts through MIR/LIR and post-RA verification, Q80-006..010 negative contracts, O0..O3 exact dump and Q8_0 SIMD fallback tests, a 121-entry status baseline gate, and a byte-identical v4.2.1 three-stage bootstrap |
