---
id: "VIRC-RPT-0040"
type: "REPORT"
domain: "VIRC"
title: "Group 11 backend structural fixture module identity repair report"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners: [tests]
components: [strict-v2, group-11, module-registry, mcinst, verifier]
related:
  issues:
    - "VIRC-ISS-0039"
  plans:
    - "VIRC-PLN-0023"
  reports: []
supersedes: null
superseded_by: null
tags: [test-debt, module-identity, regression-suite]
---

# VIRC-RPT-0040 — Group 11 backend structural fixture module identity repair report

## 1. Executive Summary

The Group 11 backend structural fixture now uses canonical compiler module
identities and reaches its runtime verifier oracle. The focused executable
emits all fifteen expected malformed-symbol diagnostics followed by `1` and
exits zero. Both mutation controls fail as intended. Group 11 improved from
41/43 to 42/43; its only remaining failure is the independent Result/URL
semantic defect tracked by `VIRC-ISS-0037`.

## 2. Source Issues

- VIRC-ISS-0039

## 3. Source Plans

- VIRC-PLN-0023

## 4. Implementation Summary

- Replaced retired `compiler.mc` and `compiler.mc.verify` identities with
  registry keys `mc` and `mc_verify`.
- Replaced compatibility runtime aliases with `types_prelude`, `rt_string_rt`,
  and `rt_vec_rt`.
- Removed every redundant include/import pair from the fixture.
- Kept production registry, resolver, MC verifier, and backend code unchanged.

## 5. Changes by Component

### `tests/strict_v2/backend_unresolved_structural_e2e.vri`

- change: canonicalized five dependency declarations and retained one dependency
  form per module;
- reason: dotted and compatibility aliases were not registered identities;
- impact: the fixture now compiles, links, and executes the original MC
  verifier assertions without weakening the oracle.

## 6. Deviations from Plan

Import-only `mc_verify` passed semantic checking but failed native linking
because its internal `rt_io` implementation was not physically included. The
final implementation uses `include mc_verify` without a redundant import. This
preserves the one-form dependency rule and is verified by native execution.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Focused `--check --json` | PASS | zero diagnostics before native build |
| Focused native execution | PASS | fifteen expected verifier diagnostics, final `1`, exit 0 |
| False-accept mutation | PASS | forced malformed-symbol acceptance printed `101` and exited 1 |
| False-reject mutation | PASS | forced registered-symbol rejection printed `108` and exited 1 |
| Module graph from repository root | PASS | `mc` and `mc_verify` resolved to canonical source files |
| Module graph from `/private/tmp` | PASS | both identities resolved independently of CWD |
| Dependency discipline | PASS | all 316 compiler source files passed |
| Group 11 | PARTIAL | 42/43; repaired fixture PASS, sole remaining failure is VIRC-ISS-0037 |

### Regression

The embedded stdout oracle is unchanged. No production compiler source,
generated bundle, registry entry, or expected verifier behavior changed.

### Conformance

`VIR-SPC-0014` permits whole-module include and import-only access without a
preceding include. The fixture now uses existing identities from
`compiler/module.list` and no invented dotted path.

## 8. Acceptance Criteria

- [x] The fixture uses canonical `mc` and `mc_verify` keys and contains no
  redundant include/import pair.
- [x] Focused compilation and execution match the embedded stdout/exit oracle.
- [x] ARM64, x86-64, and RISC-V malformed/unresolved symbol cases execute.
- [x] Mutation controls catch false acceptance and false rejection.
- [x] Module graph resolution succeeds from repository root and `/private/tmp`.
- [x] Group 11 no longer reports this fixture as `FAIL-COMPILE`.
- [x] No production resolver alias was added.
- [x] Runtime aliases discovered in the same fixture were consolidated here;
  the independent compiler defect remains in `VIRC-ISS-0037`.
- [x] This accepted REPORT and completed PLAN provide closure evidence.

## 9. Known Limitations

Group 11 remains 42/43 until `VIRC-ISS-0037` is fixed. That failure is not
caused by this fixture and does not weaken the focused closure evidence.

## 10. Remaining Work

No remaining work exists within `VIRC-ISS-0039` scope.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIRC-ISS-0039`
- `VIRC-PLN-0023`
- `VIRC-ISS-0037` — independent remaining Group 11 semantic failure

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created and accepted with focused runtime, mutation, module-graph, dependency, and Group 11 evidence |
