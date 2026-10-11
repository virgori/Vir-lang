---
id: "VIR-PLN-0001"
type: "PLAN"
domain: "VIR"
title: "Define the AOT-first native reverse-mode autodiff contract"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIR-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "autodiff"
  - "ahead-of-time"
  - "language-contract"
---

# VIR-PLN-0001 — Define the AOT-first native reverse-mode autodiff contract

## 1. Objective

Replace the ambiguous runtime-tracing language in the active Vir
specifications with one normative AOT-first reverse-mode contract and provide
the implementation gate needed by VIRC-ISS-0018.

## 2. Source Issues

- VIR-ISS-0014

## 3. Scope

In scope: transformation boundary, differentiability and control-flow rules,
shape/target failure policy, gradient observation and accumulation, activation
lifetime/cleanup, checkpointing, and English/Vietnamese parity.

Out of scope: higher-order derivatives, custom-gradient syntax, stop-gradient
syntax, and an opt-in runtime graph API.

## 4. Current Architecture

The active contract mixed a native tensor surface with language that implied
runtime graph tracing, a dynamic tape, and fixed memory/performance ratios. It
did not define the derivative transformation boundary, fail-closed behavior,
or the ownership of activation and gradient storage.

## 5. Proposed Architecture

Vir uses a typed-IR AOT reverse transformation after type, shape, effect, and
ownership analysis and before target lowering. Compiler-planned activation or
execution-state storage is permitted, but implicit runtime operator graphs,
parent links, reverse dispatch, and graph traversal are not.

## 6. Design Decisions

1. Reverse-mode differentiation is a typed HIR/MIR/SSA transformation before
   target lowering, not raw-AST rewriting and not runtime graph tracing.
2. Runtime activation or compact execution-state storage is permitted, but
   operator nodes, parent links, and runtime reverse dispatch are not implicit.
3. Unsupported shapes, operations, effects, control flow, or targets fail
   before artifact emission with stable diagnostics.
4. Root gradients are one-seeded; fan-out contributions sum within one call;
   each repeated `.backward()` replaces the reachable gradient set.
5. `.grad` is a public tensor projection only after successful backward for a
   reachable train value.
6. No fixed RAM or speed multiplier is normative.

## 7. Implementation Plan

- [x] Revise VIR-SPC-0017 §26.3–26.4 in English.
- [x] Revise VIR-SPC-0018 §26.3–26.4 in Vietnamese.
- [x] Align VIR-SPC-0001/0002/0003 architecture §7.3–7.4.
- [x] Link VIR-ISS-0014, this plan, and VIR-RPT-0001 reciprocally.
- [x] Re-scope VIRC-ISS-0018 to the approved AOT contract.
- [x] Validate the paper registry and close only after an accepted report.

## 8. Compatibility

The source surface (`train`, `.backward()`, and `.grad`) remains native. The
revision narrows previously ambiguous behavior: implementations that relied on
implicit runtime graph tracing must migrate to AOT lowering or reject the
unsupported capability before artifact emission.

## 9. Migration

Revise the English and Vietnamese language contracts together, align the three
active architecture specifications, then re-scope VIRC-ISS-0018 and its
implementation plan to the approved static capability set.

## 10. Validation Plan

- Search active specifications for stale implicit tracing/tape and fixed
  `~50%`/`~2–3×` claims.
- Run `./paper registry --write` and `./paper validate`.
- Confirm the implementation issue links the approved contract.

## 11. Risks

- Calling all runtime storage a "tape" could accidentally reintroduce graph
  semantics; the specifications distinguish activation state from graph nodes.
- A backend may silently accept an unsupported case; the contract therefore
  requires stable pre-artifact rejection.
- English/Vietnamese drift is prevented by a shared acceptance matrix.

## 12. Rollback Strategy

If the contract cannot be implemented safely, keep the affected capability
unsupported and fail closed. Reverting to an implicit runtime graph is not a
permitted compatibility fallback.

## 13. Exit Criteria

- [x] Active English/Vietnamese language specifications are semantically equal.
- [x] Active architecture specifications no longer prescribe a dynamic tape.
- [x] All VIR-ISS-0014 acceptance criteria are addressed.
- [x] VIR-RPT-0001 concludes `READY_FOR_CLOSE`.

## 14. Related Papers

- VIR-ISS-0014
- VIR-RPT-0001
- VIRC-ISS-0018
- VIRC-PLN-0033
- VIRC-RPT-0050

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Plan created and completed with the v3.2.0 language and v2.1.0 architecture revisions |
