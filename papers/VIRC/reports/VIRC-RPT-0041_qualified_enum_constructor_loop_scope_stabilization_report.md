---
id: "VIRC-RPT-0041"
type: "REPORT"
domain: "VIRC"
title: "Qualified enum constructor loop-scope stabilization report"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners: [compiler]
components: [semantic, name-resolution, enum, ufcs, stdlib-result, stdlib-url, strict-v2]
related:
  issues:
    - "VIRC-ISS-0037"
  plans:
    - "VIRC-PLN-0024"
  reports: []
supersedes: null
superseded_by: null
tags: [enum-constructor, soft-abi, loop-scope, regression, fixed-point]
---

# VIRC-RPT-0041 — Qualified enum constructor loop-scope stabilization report

## 1. Executive Summary

`VIRC-ISS-0037` is resolved. Pass 3 now visits the body of both range-form and
iterable-form `for` nodes reliably under the native self-host ABI. The valid
qualified `Result.Err(...)` constructor in `result.try_all` is rewritten before
UFCS fallback, Result and URL consumers pass, genuine unresolved UFCS remains
rejected, and two consecutive self-host generations are byte-identical.

## 2. Source Issues

- VIRC-ISS-0037

## 3. Source Plans

- VIRC-PLN-0024

## 4. Implementation Summary

- Replaced straight-line `ForRange` child-count checks with loop-carried
  traversal of every non-body child followed by the final body child.
- Added a focused executable `for` + `case` + `out` qualified enum-constructor
  regression and registered it in Group 11 min/full modes.
- Synchronized the generated compiler bundle and promoted the fixed-point
  self-host binary.

## 5. Changes by Component

### `compiler/src/semantic/names/walk.vri`

- change: walk all bound/iterable children through loop-carried state, then
  resolve the last child inside the loop scope;
- reason: recursive bound walks clobbered the straight-line `child_count` local
  in native self-host output and caused the body to be skipped;
- impact: qualified enum constructors and all other names in `for` bodies now
  reach pass 3 for both supported loop AST shapes.

### `tests/strict_v2/enum_constructor_for_case_out_e2e.vri`

- change: added a runtime oracle for `LoopResult.Err(7)` inside nested
  `for` + `case` + `out` control flow;
- reason: reproduce the exact missing traversal without depending on stdlib
  preprocessing;
- impact: future regressions fail Group 11 with an exact output mismatch.

### `run_tests.sh` and `compiler/generated/virc.vri`

- change: registered the regression in both Group 11 modes and regenerated the
  canonical compiler bundle;
- reason: make the fix durable in normal CI and keep source/bundle parity;
- impact: Group 11 now contains 44 checks and passes 44/44.

## 6. Deviations from Plan

The initial hypothesis proposed scalarizing import-alias identity. Direct
instrumentation instead proved that pass 3 never visited the loop body. The
plan was corrected before closure and no alias or enum-rewrite ABI was changed.
This reduced the implementation surface while preserving the intended
acceptance and compatibility contract.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Focused loop/case/out regression | PASS | prints exactly `7`, exit 0 |
| Result semantic check | PASS | JSON success, zero errors |
| URL namespace smoke | PASS | compile and runtime exit 0 |
| URL matrix | PASS | compile and runtime exit 0 |
| Group 11 | PASS | 44/44, including all genuine UFCS rejects |
| Module dependency discipline | PASS | all 316 compiler source files |
| Generated-source synchronization | PASS | `sync_virc.py --check` identical |
| Self-host fixed point | PASS | stage 2 = stage 3, SHA-256 `f5ebbfb599172f5a744dbc30b6c787410f79790372fc8bbdce0fdcd73dd1b29f` |

### Regression

The new fixture independently demonstrates that a qualified payload constructor
inside a `for` body reaches enum semantics, survives a `case` payload bind, and
can be returned through another qualified constructor. Group 11 also executes
the original URL positive case and retains all `E3021` rejection fixtures.

### Conformance

No public syntax, AST layout, diagnostic code, module API, or serialized format
changed. Canonical modular sources and the generated bundle are synchronized.

## 8. Acceptance Criteria

Mapping 1:1 với ISSUE:

- [x] `result.vri` checks successfully with zero errors.
- [x] Focused nested `for` + `case` + `out` constructors execute correctly.
- [x] URL smoke, matrix, and registered positive consumer pass.
- [x] Genuine unresolved UFCS fixtures still emit `E3021` and Group 11 passes.
- [x] Group 11 has no `result.vri:147` failure (44/44 PASS).
- [x] Generated source is synchronized and self-host stages reach fixed point.
- [x] The PLAN and this accepted REPORT provide closure evidence.

## 9. Known Limitations

The fix assumes the parser/lowering invariant that a `ForRange` node stores its
body as the final child. That invariant already covers both supported forms:
`[start, end, body]` and `[iterable, body]`.

## 10. Remaining Work

None for this issue.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIRC-ISS-0037`
- `VIRC-PLN-0024`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Accepted with focused runtime, Group 11, sync, dependency, and byte-identical bootstrap evidence |
