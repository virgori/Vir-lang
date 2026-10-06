---
id: "VIRC-ISS-0018"
type: "ISSUE"
domain: "VIRC"
title: "Infer and train runtime modes and autodiff are not block scoped or graph general"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-03"
owners: [compiler, runtime]
components: [infer, train, autodiff, tensor, mir, runtime-state, cleanup, tests]
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: [infer, train, autodiff, backward, lexical-scope, gradients]
---

# VIRC-ISS-0018 — Infer and train runtime modes and autodiff are not block scoped or graph general

## 1. Summary

The compiler recognizes `infer:` and `train:` and enforces several semantic
restrictions, but runtime mode changes are emitted only at block entry and the
backward runtime is hard-coded for one 2x2 matmul record. The implementation
therefore does not provide lexical block restoration or the general traced
autodiff graph required by the language contract.

## 2. Context

VIR-SPC-0018 sections 26.3 and 26.4 define `infer` as disabling gradient
tracking for the block and `train` as tracing tensor operations so
`.backward()` differentiates the complete computation graph. Semantic checks
already reject nesting, backward in `infer`, backward outside `train`, and
invalid receivers; this ISSUE preserves those completed checks and tracks the
runtime gap only.

## 3. Expected Behavior

- Entering and leaving `infer:` or `train:` saves and restores the previous
  runtime mode on normal completion and every supported early/error exit.
- `infer:` allocates no gradient tape or activation state and values created in
  it cannot later acquire gradient state implicitly.
- `train:` records every supported tensor operation in an ordered graph with
  shape/dtype-aware operands and computes gradients by chain rule.
- Backward supports documented ranks/shapes and multiple operations, detects
  stale or invalid tape state, and does not overwrite unrelated arena data.
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
- `tests/strict_v2/test_autodiff_e2e.vri` passes, but it exercises exactly that
  single 2x2 matmul shape and cannot prove a general graph.

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
- CONFIRMED: the current 2x2 autodiff fixture passes on macOS ARM64.
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

- [ ] Runtime mode is saved and restored for normal exit, `break`, `skip`,
  `out`, and propagated error paths without leaking tape or activation state.
- [ ] `infer:` proves zero gradient-tape/activation allocation for covered
  tensor operations through structural or allocation-counter evidence.
- [ ] `train:` records a bounded, validated graph for multiple supported
  operations and preserves dtype, shape, ownership, and lifetime metadata.
- [ ] Backward computes correct chain-rule gradients for rectangular, chained,
  branched, and repeated-operation fixtures against an independent oracle.
- [ ] Tape bounds, allocation failure, stale state, repeated backward, and
  unsupported operations fail deterministically without memory corruption.
- [ ] Semantic negatives for nesting and invalid backward remain green and
  produce no artifact.
- [ ] O0-O3 and every affected backend pass identical semantic and gradient
  contracts; unsupported targets report stable diagnostics.
- [ ] A public gradient observation/update contract is specified or explicitly
  linked before the blocked AI contract row is enabled.
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
| 2026-10-03 | Created and triaged from semantic, lowering, runtime-stub, and focused test audit |
