---
id: "VIRC-PLN-0033"
type: "PLAN"
domain: "VIRC"
title: "Implement AOT static-tensor reverse-mode autodiff"
status: "COMPLETED"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "runtime"
components:
  - "autodiff"
  - "tensor"
  - "mir"
  - "lir"
  - "arm64"
  - "x86-64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0018"
    - "VIR-ISS-0014"
  plans: []
  reports:
    - "VIRC-RPT-0050"
supersedes: null
superseded_by: null
tags:
  - "autodiff"
  - "ahead-of-time"
  - "reverse-mode"
---

# VIRC-PLN-0033 — Implement AOT static-tensor reverse-mode autodiff

## 1. Objective

Replace the fixed runtime tape/backward stub with compiler-owned AOT graph
lowering for the supported dense `tensor[f32]` matmul subset, public `.grad`,
and ARM64/Linux-x86_64 parity under VIR-SPC-0017/0018 v3.2.0.

## 2. Source Issues

- VIRC-ISS-0018
- VIR-ISS-0014

## 3. Scope

In scope: static rectangular matmul chains, fan-out accumulation, repeated
backward replacement, compiler-side alias/gradient maps, native gradient tensor
storage, inference with no AD graph state, target diagnostics, O0–O3, ARM64 and
Linux x86-64.

Out of scope for this implementation slice: dynamic reverse CFGs, non-f32 AD,
custom/stop gradients, recursion, and unsupported targets. These fail closed.

## 4. Current Architecture

The previous implementation recorded a fixed 2×2 matmul entry in runtime arena
memory, reused tensor header storage for gradient discovery, and dispatched one
hard-coded backward stub. It could not represent rectangular chains, fan-out,
or stable optimizer-visible gradient storage.

## 5. Proposed Architecture

1. AST-to-MIR lowering records typed/static matmul dependencies only while
   lowering a lexical `train` block.
2. `.backward()` emits two direct derivative kernel calls per reachable node in
   reverse dependency order. Compiler SSA maps carry upstream, prior, and final
   gradient tensor values.
3. Runtime derivative kernels receive primal tensors, optional upstream/prior
   gradient tensors, and packed static dimensions. They compute one rectangular
   derivative and return an ordinary tensor; they own no graph state.
4. `.grad` resolves to the compiler-managed gradient vreg. Tensor headers retain
   their normal `len` and `capacity` fields.
5. Unsupported dtype, control flow, root, projection order, or target terminates
   compilation with E3105–E3109 before artifact emission.

## 6. Design Decisions

- Keep dependency and gradient identity in compiler state, never in tensor
  headers or runtime graph objects.
- Emit one direct rectangular derivative call per operand and graph node.
- Seed roots with ones, accumulate fan-out explicitly, and replace reachable
  gradients on repeated backward.
- Restrict the first capability to straight-line dense f32 matmul and reject
  unsupported dtype, control flow, root, projection timing, and target.

## 7. Implementation Plan

- [x] Add compiler-side AOT node, alias, and gradient maps.
- [x] Emit reverse-order derivative MIR and public `.grad` projection.
- [x] Implement rectangular f32 ARM64 derivative kernel.
- [x] Implement Linux x86-64 derivative kernel and arena growth.
- [x] Remove active matmul runtime tape recording.
- [x] Add chain, fan-out, repeated-backward, negative, and cross-target tests.
- [x] Synchronize generated compiler, bump the internal version, and verify
  self-host fixed point plus paper lifecycle.

## 8. Compatibility

Existing supported `train`, `.backward()`, and `.grad` programs retain their
surface syntax. Invalid or previously accidental fixed-tape behavior now
receives E3105–E3109 before artifact emission.

## 9. Migration

Synchronize the modular compiler and generated bundle, bump the internal
compiler version, replace active tape recording with AOT MIR emission, and
retain no implicit runtime fallback.

## 10. Validation Plan

- ARM64 O0–O3 for the single, rectangular chain, fan-out, repeated-backward,
  and existing Spec 26 fixtures.
- Linux x86-64 O0–O3 execution under Docker amd64.
- Negative diagnostics for dynamic control, f64, invalid `.grad`, and targets.
- Group 4, Group 26, self-host fixed point, version/sync checks, diff check,
  and VPS validation.

## 11. Risks

- Optimizer assumptions may expose tensor-header aliasing bugs.
- Gradient allocation may exceed the initial arena on x86-64.
- Compiler-side graph state may leak between functions or lexical modes.

These are gated by O0–O3 tests, separate gradient tensors, arena growth, and
per-function/per-mode state reset.

## 12. Rollback Strategy

Revert the AOT lowering and keep the capability rejected. Do not reactivate the
fixed runtime tape or tensor-header gradient pointer as a fallback.

## 13. Exit Criteria

- [x] Single, rectangular chained, fan-out, and repeated backward fixtures pass.
- [x] Primal tensor storage remains intact; gradients are separate native tensors.
- [x] ARM64 and Linux x86-64 O0–O3 produce identical results.
- [x] Unsupported capabilities fail before artifact emission.
- [x] Group 4/26, self-host, module sync, version, and paper validation pass.
- [x] VIRC-RPT-0050 concludes `READY_FOR_CLOSE`.

## 14. Related Papers

- VIRC-ISS-0018
- VIR-ISS-0014
- VIR-PLN-0001
- VIR-RPT-0001
- VIRC-RPT-0050

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Created and completed AOT static-tensor autodiff implementation plan |
