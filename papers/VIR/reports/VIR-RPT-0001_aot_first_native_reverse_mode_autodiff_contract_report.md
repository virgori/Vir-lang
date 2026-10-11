---
id: "VIR-RPT-0001"
type: "REPORT"
domain: "VIR"
title: "AOT-first native reverse-mode autodiff contract report"
status: "ACCEPTED"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "tensor"
  - "autodiff"
  - "hir"
  - "mir"
  - "memory-model"
related:
  issues:
    - "VIR-ISS-0014"
  plans:
    - "VIR-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "autodiff"
  - "ahead-of-time"
  - "contract"
---

# VIR-RPT-0001 — AOT-first native reverse-mode autodiff contract report

## 1. Executive Summary

VIR-ISS-0014 is resolved by VIR-SPC-0017/0018 v3.2.0 and
VIR-SPC-0001/0002/0003 v2.1.0. The active contract now requires typed-IR AOT
reverse transformation, forbids implicit runtime graph tracing, distinguishes
compiler-planned activation state from graph metadata, and defines fail-closed
behavior, gradient semantics, ownership/lifetime, and target capability.

## 2. Source Issues

- VIR-ISS-0014

## 3. Source Plans

- VIR-PLN-0001

## 4. Implementation Summary

- Defined the transformation boundary after type/shape/effect/ownership
  analysis and before target lowering.
- Defined branches, loops, calls, mutation, aliases, effects, recursion,
  extern/custom operations, and dynamic shapes as capability-gated; unsupported
  cases reject before artifact emission and never trigger an implicit tape.
- Defined root seeding, same-shape/dtype gradients, fan-out accumulation,
  replacement semantics for repeated backward, and public `.grad` availability.
- Applied ordinary ownership, arena, promotion, and cleanup rules to activation,
  execution-state, and gradient storage.
- Made checkpoint/recompute and buffer reuse semantics-preserving optimizations.
- Declared custom/stop gradients, higher-order AD, and runtime graph APIs
  explicit non-goals for v3.2.0.
- Removed fixed `~50%`, `~2–3×`, and tracing-speed claims.

## 5. Changes by Component

- VIR-SPC-0017/0018 define the paired English/Vietnamese language contract.
- VIR-SPC-0001/0002/0003 align the active compiler architecture contract.
- VIR-ISS-0014 records the decision and VIRC-ISS-0018 owns implementation.

## 6. Deviations from Plan

None. The contract was revised in the planned language and architecture papers
without adding runtime graph fallback or fixed performance promises.

## 7. Verification

The English and Vietnamese language specifications carry the same normative
rules. All three active architecture specifications now describe static reverse
dependency lowering and native gradient tensors rather than runtime tape nodes.
Stale tracing/tape claims were searched, the registry was regenerated, and VPS
validation completed after reciprocal links were added.

## 8. Acceptance Criteria

- [x] AOT-first execution model and no implicit tracing fallback.
- [x] Typed derivative-IR stage and forward/reverse coupling.
- [x] Differentiability, control-flow, call, mutation, alias, effect, recursion,
  and external-operation rules.
- [x] Static-shape and stable fail-closed diagnostics.
- [x] Activation ownership, lifetime, cleanup, reuse, and checkpoint policy.
- [x] Gradient shape/dtype, seed, fan-out, repeated-call, and observation rules.
- [x] Explicit custom/stop-gradient non-goal.
- [x] Target capability matrix rule and pre-artifact rejection.
- [x] Fixed memory/performance claims removed.
- [x] English/Vietnamese and architecture revisions linked.

## 9. Known Limitations

The contract does not standardize higher-order derivatives, custom-gradient or
stop-gradient syntax, or an opt-in runtime graph API. Individual compiler
capabilities may implement a strict subset only when unsupported cases reject
before artifact emission.

## 10. Remaining Work

No language-contract work remains for VIR-ISS-0014. Compiler capability beyond
the supported static subset is governed by VIRC-ISS-0018 and later focused
issues; it must continue to fail closed.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIR-ISS-0014
- VIR-PLN-0001
- VIRC-ISS-0018
- VIRC-PLN-0033
- VIRC-RPT-0050

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Accepted v3.2.0/v2.1.0 AOT autodiff contract and recommended VIR-ISS-0014 closure |
