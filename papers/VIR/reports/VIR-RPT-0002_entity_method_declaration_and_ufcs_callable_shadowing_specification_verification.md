---
id: "VIR-RPT-0002"
type: "REPORT"
domain: "VIR"
title: "Entity method declaration and UFCS callable shadowing specification verification report"
status: "ACCEPTED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
  - "compiler"
components:
  - "entity"
  - "methods"
  - "ufcs"
  - "conformance-tests"
related:
  issues:
    - "VIR-ISS-0019"
  plans:
    - "VIR-PLN-0002"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "entity"
  - "method"
  - "ufcs"
  - "shadowing"
---

# VIR-RPT-0002 — Entity method declaration and UFCS callable shadowing specification verification report

## 1. Executive Summary

VIR-ISS-0019 is resolved without a compiler behavior change. Two focused
ACTIVE specifications now define entity-owned methods and callable-tier UFCS
resolution. The English and Vietnamese language specifications retain §11.5,
explicitly define callable-only shadowing and terminal no-fallback selection,
and document direct free-function selection and source-compatibility risks.
Six registered regressions pass, the full UFCS group passes 74/74, and the
self-hosted compiler source check succeeds.

## 2. Source Issues

- VIR-ISS-0019

## 3. Source Plans

- VIR-PLN-0002

## 4. Implementation Summary

- Added `VIR-SPC-0022` for entity and method declaration ownership, implicit
  `this`, nested `end`, owning `end.`, and module-scope rejection.
- Added `VIR-SPC-0023` for method > callable field > free UFCS resolution,
  terminal selection, non-callable-field fallthrough, and direct-call pinning.
- Updated `VIR-SPC-0017` and `VIR-SPC-0018` to v3.5.0 with normative parity.
- Corrected the Vir syntax skill's block law so nested entity methods close
  with `end`, not `end.`.
- Added and registered four negative collision tests and two positive
  selection tests in Group 11.
- Made no resolver, parser, lowering, backend, ABI, or compiler-version change
  for this issue.

## 5. Changes by Component

### `papers/VIR/specs/`

- change: added two focused specs and synchronized the broad language specs;
- reason: make the audited behavior independently normative and discoverable;
- impact: specification clarity only; existing valid programs keep the same
  resolution behavior.

### `.agents/skills/vir-syntax/SKILL.md`

- change: moved nested entity `method` from the dotted top-level block rule to
  the undotted nested block rule;
- reason: align agent-facing syntax guidance with Vir 3.5;
- impact: generated/reviewed Vir code now uses the normative terminator.

### `tests/strict_v2/` and `run_tests.sh`

- change: added six focused fixtures to both Group 11 modes;
- reason: lock terminal no-fallback, non-callable fallthrough, and direct-call
  behavior with executable evidence;
- impact: future resolver drift fails the native regression suite.

## 6. Deviations from Plan

No material deviations from the approved plan.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Method wrong arity, compatible free fallback | PASS-REJECT | `E3022`; no fallback |
| Method wrong type, compatible free fallback | PASS-REJECT | `E3001`; no fallback |
| Callable-field wrong arity, compatible free fallback | PASS-REJECT | `E3022`; no fallback |
| Callable-field wrong type, compatible free fallback | PASS-REJECT | `E3001`; no fallback |
| Non-callable field plus free UFCS | PASS | output `40`, `47` |
| Direct free call despite same-named method | PASS | dot output `15`, direct output `915` |
| `./run_tests.sh 11` | PASS | 74/74 |
| `./bin/virc compiler/src/entry.vri --check --json --color=never` | PASS | zero errors and warnings |
| `python3 tools/sync_virc.py --check` | PASS | generated `virc.vri` identical to source modules |

### Regression

The four rejection fixtures deliberately place a compatible free function
behind the selected higher-priority candidate. Their expected `E3022`/`E3001`
diagnostics therefore prove that signature failure does not reopen resolution.
The two positive fixtures distinguish field access from callable lookup and
dot-call priority from explicit free-function selection by observable output.

### Conformance

Compiler `2026.1.17` passes all new fixtures unchanged. This confirms the work
is a specification and coverage completion, not a language-design or compiler
implementation change.

## 8. Acceptance Criteria

- [x] `VIR-SPC-0022` is ACTIVE and defines entity/method ownership and syntax.
- [x] `VIR-SPC-0023` is ACTIVE and defines callable-tier UFCS resolution.
- [x] `VIR-SPC-0017`/`0018` retain §11.5 with English/Vietnamese parity.
- [x] Method wrong-arity and wrong-type collision regressions pass.
- [x] Callable-field wrong-arity and wrong-type collision regressions pass.
- [x] Non-callable-field fallthrough and direct free-call regressions pass.
- [x] Existing compiler passes without a change or version bump for this issue.
- [x] Registry and VPS validation gates pass after report registration.

## 9. Known Limitations

- Generic UFCS specialization remains owned by `VIRC-ISS-0064`; this report
  does not broaden that contract.
- The API-compatibility warning is conservative because downstream ecosystem
  usage outside this repository was not audited.

## 10. Remaining Work

None for VIR-ISS-0019.

## 11. Conclusion

ACCEPTED — READY_FOR_CLOSE

## 12. Related Papers

- `VIR-ISS-0019` — source issue.
- `VIR-PLN-0002` — implementation and verification plan.
- `VIR-SPC-0017` / `VIR-SPC-0018` — broad language specifications v3.5.0.
- `VIR-SPC-0022` — entity and method declaration specification.
- `VIR-SPC-0023` — UFCS resolution and callable shadowing specification.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Accepted after six focused regressions, Group 11 at 74/74, compiler self-check, generated-source sync, and VPS validation |
