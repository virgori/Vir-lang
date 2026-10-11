---
id: "VIRC-RPT-0050"
type: "REPORT"
domain: "VIRC"
title: "AOT static-tensor reverse-mode autodiff implementation report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0033"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "autodiff"
  - "ahead-of-time"
  - "reverse-mode"
---

# VIRC-RPT-0050 — AOT static-tensor reverse-mode autodiff implementation report

## 1. Executive Summary

VIRC-ISS-0018 is resolved for the compiler's declared static capability set.
The fixed 2×2 runtime record was replaced by compiler-side AOT dependency and
gradient maps plus direct rectangular f32 reverse kernels. No active matmul path
records runtime graph nodes, and gradient tensors no longer overwrite dense
tensor header storage.

## 2. Source Issues

- VIR-ISS-0014
- VIRC-ISS-0018

## 3. Source Plans

- VIR-PLN-0001
- VIRC-PLN-0033

## 4. Implementation Summary

- `ast_to_mir/context.vri`, `stmt.vri`, `expr_ops.vri`, and `calls.vri` record
  static matmul nodes, canonical aliases, and SSA gradient values; backward
  emits direct reverse calls in compile-time order.
- `expr.vri` and type/semantic lowering expose `.grad` as a native tensor and
  reject unavailable projections.
- ARM64 and x86-64 intrinsic lowering stage five static derivative arguments.
- Both runtime kernels implement rectangular `dA = G × Bᵀ` and
  `dB = Aᵀ × G`, root-one seeding, prior-gradient fan-out accumulation, and
  ordinary packed-f32 gradient tensors.
- The root seed is materialized as its own ordinary all-ones tensor, so
  `root.grad` follows the same public storage and repeated-backward replacement
  rules as every other reachable train value.
- Train/infer intrinsics are structural markers only; active forward matmul
  stubs contain no AD graph recording.
- E3105–E3109 reject unsupported roots, dtypes, dynamic control flow, targets,
  and invalid gradient observation before artifact emission.

## 5. Changes by Component

An intermediate implementation reused tensor header offset 8 as a gradient
pointer. O2 correctly exposed that this was not a stable storage contract. The
final implementation uses separate SSA gradient tensors, preserving both
`len` and `capacity` and remaining correct under O0–O3. The x86 derivative
allocator also honors arena growth instead of overrunning the initial chunk.

## 6. Deviations from Plan

The first implementation attempted to store a gradient pointer in the tensor
header. O2 exposed that as invalid, so the final implementation moved all
gradient identity to compiler SSA and separate tensor values. This correction
preserves the plan's public behavior and strengthens its storage guarantee.

## 7. Verification

- ARM64 O0–O3: `test_autodiff_e2e.vri`,
  `test_autodiff_aot_graph.vri`, and `test_spec26_ai_huge_proof.vri` pass.
- Linux x86-64 Docker/amd64 O0–O3: single, rectangular chain, fan-out, and
  repeated backward pass with exact fixture output.
- Negative contracts reject dynamic control flow, unsupported f64 AD, invalid
  `.grad` timing, backward outside train/in infer, and unsupported targets.
- Group 4 passes 38/38 and Group 26 passes 47/47 after registration of the new
  positive and negative fixtures.
- Generated compiler synchronization and the 2026.1.5 internal version check
  pass. Production-default O1 self-host stages 10 and 11 are byte-identical at
  SHA-256 `8ac8a2559cf980581dc4bd38941603c619f03d460ad8b5b5e7a4531255a520ef`.
- Task-scoped `git diff --check` and `./paper validate` pass.

## 8. Acceptance Criteria

- [x] Lexical train/infer state does not depend on a runtime mode flag or tape.
- [x] `infer` emits no derivative graph/runtime graph state.
- [x] Static graph preserves shape/dtype/ownership metadata in compiler state.
- [x] Rectangular chain, fan-out, and repeated backward are correct.
- [x] Tensor header/storage remains unmodified by gradient projection.
- [x] Semantic and capability negatives produce no artifact.
- [x] ARM64/Linux-x86_64 O0–O3 parity is verified; other targets fail closed.
- [x] Public `.grad` contract links VIR-SPC-0017/0018 v3.2.0.
- [x] PLAN and REPORT are reciprocal and accepted.

## 9. Known Limitations

The shipped capability is static straight-line dense f32 matmul AD. Dynamic
reverse CFGs and additional differentiable operators/dtypes remain future
capabilities and are rejected rather than traced at runtime. This is conformant
with the v3.2.0 fail-closed contract.

## 10. Remaining Work

None for VIRC-ISS-0018's declared capability and closure criteria.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0018
- VIRC-PLN-0033
- VIR-ISS-0014
- VIR-PLN-0001
- VIR-RPT-0001

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Accepted AOT static-tensor autodiff implementation and cross-target verification |
