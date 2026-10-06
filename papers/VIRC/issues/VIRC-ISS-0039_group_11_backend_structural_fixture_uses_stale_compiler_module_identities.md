---
id: "VIRC-ISS-0039"
type: "ISSUE"
domain: "VIRC"
title: "Group 11 backend structural fixture uses stale compiler module identities"
status: "CLOSED"
severity: "S3"
priority: "P1"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "tests"
components:
  - "strict-v2"
  - "group-11"
  - "module-registry"
  - "mcinst"
  - "verifier"
related:
  issues: []
  plans:
    - "VIRC-PLN-0023"
  reports:
    - "VIRC-RPT-0040"
supersedes: null
superseded_by: null
tags:
  - "test-debt"
  - "stale-fixture"
  - "module-identity"
  - "regression-suite"
---

# VIRC-ISS-0039 — Group 11 backend structural fixture uses stale compiler module identities

## 1. Summary

Group 11's `backend_unresolved_structural_e2e.vri` is a stale test fixture. It
imports the retired dotted identities `compiler.mc` and
`compiler.mc.verify`, while the active compiler registry exposes `mc` and
`mc_verify`. The test therefore fails in preprocessing with `E2125` and never
executes the MC verifier behavior it is meant to cover.

## 2. Context

Compiler module identity is closed by `compiler/module.list`; physical source
layout and a file's internal descriptive module name do not authorize tests to
invent alternate registry IDs. This issue is intentionally limited to Group 11
fixture maintenance. It must not be used to broaden the production resolver
with compatibility aliases for stale tests.

The audit was run on 2026-10-05 at Git HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` in a dirty worktree with concurrent
compiler work. No source or test file was changed during capture.

## 3. Expected Behavior

- The fixture imports MC definitions and verifier functions through canonical
  keys registered in `compiler/module.list`.
- It compiles, executes all malformed/unresolved symbol cases, emits the
  checked-in verifier output, and exits with the expected status.
- Group 11 reaches the backend structural runtime oracle instead of failing
  during include expansion.

## 4. Actual Behavior

- The fixture uses `include compiler.mc` and
  `include compiler.mc.verify`, with corresponding selective imports.
- `compiler/module.list` currently registers
  `mc = src/ir/mc/mc.vri` and
  `mc_verify = src/ir/mc/mc_verify.vri`.
- The compiler resolves `compiler.mc.verify` toward the nonexistent physical
  path `compiler/./src/mc/verify.vri` and emits `E2125` at line 1, column 1.
- None of the fixture's ARM64, x86-64, or RISC-V verifier assertions executes.

## 5. Reproduction

```sh
rg -n '^(mc|mc_verify)\s*=' compiler/module.list
rg -n 'compiler\.mc|mc_verify' \
  tests/strict_v2/backend_unresolved_structural_e2e.vri

bin/virc tests/strict_v2/backend_unresolved_structural_e2e.vri --check --json
./run_tests.sh 11
```

## 6. Evidence

- CONFIRMED: the focused compile returned `E2125 ModuleResolver`, reported
  missing target `compiler.mc.verify`, and named
  `compiler/./src/mc/verify.vri` as the unresolved path.
- CONFIRMED: `compiler/module.list` contains the canonical keys `mc` and
  `mc_verify`; the latter maps to the existing
  `compiler/src/ir/mc/mc_verify.vri`.
- CONFIRMED: the canonical source declares its internal descriptive identity
  as `vir.compiler.mc_verify` and exports the three verifier symbols used by
  the fixture.
- CONFIRMED: Group 11 reports this fixture as `FAIL-COMPILE`; the complete
  group result is 37/42 PASS.
- CONFIRMED: no production compiler failure must be fixed to resolve this
  particular module target mismatch; the fixture's dependency names disagree
  with the current registry.
- NOT_VERIFIED: the runtime oracle after replacing both stale identities,
  because this issue-capture turn intentionally did not edit tests while
  another process was modifying the worktree.

## 7. Scope

### Affected

- `tests/strict_v2/backend_unresolved_structural_e2e.vri`;
- Group 11's backend structural coverage and release-gate result;
- test dependency maintenance after compiler module-tree migration.

### Not affected / Unknown

- Production module resolution is not claimed defective by this reproduction.
- MC verifier implementation correctness is not established because the stale
  fixture does not reach runtime.
- The four remaining Group 11 failures are real compiler/diagnostic issues and
  are outside this test-only issue.

## 8. Impact

The stale fixture produces a false regression signal and removes executable
coverage for malformed MC symbol operands across three native architectures.
The defect is test-only but blocks a fully green Group 11 gate, so it is
classified S3/P1.

## 9. Preliminary Analysis

- CONFIRMED: the failure is caused by test dependency identities that are not
  present in the active registry.
- CONFIRMED: adding a compatibility alias in production would preserve stale
  coupling and is outside this issue's scope.
- HYPOTHESIS: the fixture was not migrated when MC sources moved under
  `compiler/src/ir/mc/` and registry keys were flattened.
- NOT_VERIFIED: whether its expected stdout needs any independent update after
  canonical imports allow it to run.

## 10. Acceptance Criteria

- [x] The fixture uses only canonical compiler module keys from
  `compiler/module.list`, including `mc` and `mc_verify`, with no redundant
  include/import pair beyond the active dependency contract.
- [x] The focused fixture compiles and executes to its checked-in exit and
  stdout oracle on the supported host.
- [x] All ARM64, x86-64, and RISC-V malformed/unresolved symbol checks in the
  fixture execute; mutation controls prove the oracle catches an accepted bad
  symbol and a rejected valid symbol.
- [x] `python3 tools/module_graph.py` resolves each fixture dependency from the
  repository root and a relevant alternate working directory.
- [x] Group 11 no longer reports this fixture as `FAIL-COMPILE`.
- [x] No production resolver alias is added solely to accept the retired
  `compiler.mc*` identities.
- [x] Any additional stale Group 11 test-only dependency/oracle discovered
  during the same audit is consolidated here rather than receiving a duplicate
  ISSUE; genuine compiler defects remain separate.
- [x] A VPS PLAN and accepted REPORT provide verification evidence before
  closure.

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
| 2026-10-05 | Created and triaged as the single test-maintenance issue from Group 11 reproduction and canonical module-registry inspection |
| 2026-10-05 | Linked VIRC-PLN-0023 and entered implementation in the user-requested 2→1→3 sequence |
| 2026-10-05 | Linked VIRC-PLN-0023 |
| 2026-10-05 | Linked VIRC-RPT-0040 |
| 2026-10-05 | Verified focused runtime, mutation controls, CWD-independent module resolution, dependency discipline, and Group 11; accepted VIRC-RPT-0040 and closed |
