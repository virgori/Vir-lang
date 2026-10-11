---
id: "VIRC-ISS-0018"
type: "ISSUE"
domain: "VIRC"
title: "AOT static-tensor autodiff is not graph general or storage safe"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-08"
owners:
  - "compiler"
  - "runtime"
components:
  - "infer"
  - "train"
  - "autodiff"
  - "tensor"
  - "mir"
  - "runtime-state"
  - "cleanup"
  - "tests"
related:
  issues:
    - "VIR-ISS-0014"
    - "VIRC-ISS-0057"
    - "VIRC-ISS-0059"
  plans:
    - "VIRC-PLN-0033"
  reports:
    - "VIRC-RPT-0050"
supersedes: null
superseded_by: null
tags:
  - "infer"
  - "train"
  - "autodiff"
  - "backward"
  - "lexical-scope"
  - "gradients"
---

# VIRC-ISS-0018 — AOT static-tensor autodiff is not graph general or storage safe

## 1. Summary

The original implementation used a runtime mode flag, one overwritten matmul
record, and a fixed 2×2 backward stub. Following VIR-ISS-0014, this issue is
re-scoped to the approved AOT-first contract: compiler-side static dependencies,
direct reverse kernels, native gradient tensors, and fail-closed capability
boundaries without an implicit runtime graph.

## 2. Context

VIR-SPC-0017/0018 v3.2.0 define `infer` as forward-only and `train` as a typed-IR
AOT reverse transformation. Semantic checks reject nesting, backward in
`infer`, backward outside `train`, and invalid receivers; this issue completes
the static dense-f32 matmul capability and rejects unsupported cases before
artifact emission.

## 3. Expected Behavior

- `infer:` and `train:` are lexical compiler scopes and require no persistent
  runtime graph-mode flag.
- `infer:` allocates no gradient tape or activation state and values created in
  it cannot later acquire gradient state implicitly.
- `train:` records supported operations only in compiler state and emits direct
  reverse calls with shape/dtype-aware operands and chain-rule accumulation.
- Backward supports declared ranks/shapes and multiple operations, uses separate
  native gradient tensors, and never repurposes primal tensor headers.
- Nested `infer`/`train` and invalid `.backward()` calls remain compile-time
  errors with stable diagnostics.

## 4. Actual Behavior

- AST-to-MIR emits `MIR_INTR_INFER` or `MIR_INTR_TRAIN` before lowering the
  block body but emits no matching restore operation at block exit.
- ARM64 and x86-64 intrinsics write one process/function runtime flag and clear
  two tape slots on entry.
- Matmul stores one `W`, one `X`, dimensions, one output, a count, and a float
  marker in fixed runtime offsets; later operations overwrite these slots.
- ARM64 backward allocates exactly two 48-byte gradient tensors, sets both to
  length four, and reads fixed offsets for a 2x2 matrix.
- `tests/strict_v2/test_autodiff_e2e.vri` now fails at its first gradient
  assertion after dense `f32` tensors became packed 4-byte payloads: backward
  still reads operands with fixed 8-byte loads and allocates 8-byte gradient
  slots, so even the single 2x2 case is no longer dtype-correct.

## 5. Reproduction

```sh
./bin/virc tests/strict_v2/test_autodiff_e2e.vri \
  -O1 -q -o /tmp/vir_autodiff_2x2
/tmp/vir_autodiff_2x2

./bin/virc tests/strict_v2/infer_backward_negative.vri --check --json -q
./bin/virc tests/strict_v2/infer_train_nested_negative.vri --check --json -q
./bin/virc tests/strict_v2/backward_outside_train_negative.vri --check --json -q

nl -ba compiler/src/lower/ast_to_mir/stmt.vri | sed -n '655,669p'
nl -ba compiler/src/lower/lir_codegen/intrinsics.vri | sed -n '77,104p'
nl -ba compiler/src/lower/lir_codegen/rt_stubs_math/quantize_backward.vri | \
  sed -n '268,368p'
```

## 6. Evidence

- CONFIRMED: VIR-SPC-0018:3654-3691 requires block-local inference mode and
  full-graph native autodiff.
- CONFIRMED: semantic negatives produce `E3009`, `E3016`, `E3017`, and `E3020`
  as applicable.
- CONFIRMED: `stmt.vri:655-669` emits only an entry intrinsic for each block.
- CONFIRMED: ARM64 backward at `quantize_backward.vri:268-368` is fixed to two
  2x2 gradient buffers and one stored matmul record.
- CONFIRMED: the current 2x2 autodiff fixture exits 10 on macOS ARM64, and the
  aggregate proof reaches the same defect at Stage 6 after its stale Stage 5
  oracle is corrected under `VIRC-ISS-0059`.
- NOT_VERIFIED: behavior after leaving a train block, multi-op gradients,
  rectangular/batched graphs, error unwinding, nested function calls, and
  parity across all native targets.

## 7. Scope

### Affected

- runtime mode save/restore and cleanup for `infer:` and `train:`;
- autodiff tape representation, lifetime, bounds, and arena interaction;
- multi-operation tensor graph recording and backward traversal;
- gradient shape/dtype semantics and cross-target runtime parity.

### Not affected / Unknown

- completed semantic prohibitions for nesting and invalid backward calls;
- optimizer update rules and public optimizer APIs;
- quantized codec metadata and transparent dequantization;
- tensor scalar/SIMD kernel performance except where tape metadata is required.

## 8. Impact

Accepted training programs beyond the one fixed 2x2 case can silently record
the wrong operation or compute invalid gradients, while mode leakage can cause
unexpected tape allocation outside the lexical block. This violates core
language semantics and is S1/P0.

## 9. Preliminary Analysis

- CONFIRMED: semantic gating is substantially implemented and must remain a
  regression baseline.
- CONFIRMED: the runtime tape is a fixed record, not a graph.
- CONFIRMED: no block-exit restore is present in the inspected lowering path.
- HYPOTHESIS: a scoped mode stack plus arena-owned append-only tape can satisfy
  lexical cleanup and graph requirements, subject to memory verification.
- NOT_VERIFIED: the public gradient observation/update contract beyond the
  existing raw test access and `.backward()` entry point.

## 10. Acceptance Criteria

- [x] Lexical mode lowering requires no runtime graph flag or tape restoration.
- [x] `infer:` proves zero gradient-tape/activation allocation for covered
  tensor operations through structural or allocation-counter evidence.
- [x] `train:` records a bounded, validated compiler graph for multiple supported
  operations and preserves dtype, shape, ownership, and lifetime metadata.
- [x] Backward computes correct chain-rule gradients for rectangular, chained,
  branched, and repeated-operation fixtures against an independent oracle.
- [x] Arena growth, unavailable state, repeated backward, and
  unsupported operations fail deterministically without memory corruption.
- [x] Semantic negatives for nesting and invalid backward remain green and
  produce no artifact.
- [x] O0-O3 and every affected backend pass identical semantic and gradient
  contracts; unsupported targets report stable diagnostics.
- [x] A public gradient observation/update contract is specified or explicitly
  linked before the blocked AI contract row is enabled.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- `VIR-ISS-0014` — approved AOT-first language contract.

### Plans

- `VIRC-PLN-0033` — AOT static-tensor reverse-mode implementation.

### Reports

- `VIRC-RPT-0050` — accepted implementation and verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Re-scoped to the approved AOT-first contract and closed after VIRC-PLN-0033/VIRC-RPT-0050 verification |
| 2026-10-03 | Created and triaged from semantic, lowering, runtime-stub, and focused test audit |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-08 | Linked VIR-ISS-0014 |
| 2026-10-08 | Replaced obsolete passing claim with current packed-f32 backward failure evidence and linked VIRC-ISS-0059 |
| 2026-10-08 | Linked VIRC-ISS-0059 |
