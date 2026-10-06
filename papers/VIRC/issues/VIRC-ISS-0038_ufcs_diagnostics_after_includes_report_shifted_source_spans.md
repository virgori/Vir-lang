---
id: "VIRC-ISS-0038"
type: "ISSUE"
domain: "VIRC"
title: "UFCS diagnostics after includes report shifted source spans"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "diagnostics"
  - "source-manager"
  - "preprocessing"
  - "semantic"
  - "ufcs"
  - "strict-v2"
related:
  issues:
    - "VIRC-ISS-0037"
  plans:
    - "VIRC-PLN-0021"
  reports:
    - "VIRC-RPT-0038"
supersedes: null
superseded_by: null
tags:
  - "diagnostics"
  - "source-map"
  - "include"
  - "ufcs"
  - "regression"
---

# VIRC-ISS-0038 — UFCS diagnostics after includes report shifted source spans

## 1. Summary

Semantic diagnostics for three Group 11 UFCS negative fixtures identify the
correct failure class but map the primary span to the following source line
after `include net.url` preprocessing. The checked-in line oracles point to the
actual offending dot-call and must not be moved to make the suite green.

## 2. Context

The compiler preprocesses included modules into one expanded source stream and
uses `SourceManager` segments/spans to recover physical file locations.
Diagnostics created from exact `span_id` values and diagnostics created from
legacy `node.line` values must both resolve to the user's original token.

The audit used the same dirty 2026-10-05 checkout and self-hosted 4.2.1 binary
recorded by VIRC-ISS-0037. Concurrent source changes were not modified during
this issue capture.

## 3. Expected Behavior

- `missingUrl.parse(raw_uri)` reports `E2001` on line 12 at the unresolved
  receiver/member expression, not on the following `print` statement.
- `url.parse(raw_uri)` with an incompatible entity receiver reports `E3001` on
  line 17.
- `p.parse(123)` with an incompatible explicit argument reports `E3001` on
  line 11.
- JSON and human diagnostics use the same original file, line, and token-level
  span after include/import expansion.

## 4. Actual Behavior

- `ufcs_unresolved_receiver_rejected.vri` emits `E2001` at line 13, column 15,
  although the unresolved call is on line 12.
- `ufcs_entity_receiver_type_mismatch_rejected.vri` contains the intended
  `E3001` as a secondary diagnostic at line 18, column 1, although the call is
  on line 17.
- `ufcs_free_arg_type_mismatch_rejected.vri` contains the intended `E3001` as
  a secondary diagnostic at line 12, column 1, although the call is on line 11.
- Group 11 reports all three as `FAIL-WRONG-DIAGNOSTIC`. A separate false
  `E3021` from `result.vri` currently precedes the two type-mismatch diagnostics
  and is not part of this source-span issue.

## 5. Reproduction

```sh
bin/virc tests/strict_v2/ufcs_unresolved_receiver_rejected.vri \
  --check --json
bin/virc tests/strict_v2/ufcs_entity_receiver_type_mismatch_rejected.vri \
  --check --json
bin/virc tests/strict_v2/ufcs_free_arg_type_mismatch_rejected.vri \
  --check --json

./run_tests.sh 11
```

Inspect every object in the JSON `diagnostics` array, not only the primary
diagnostic, until VIRC-ISS-0037 is resolved.

## 6. Evidence

- CONFIRMED: the unresolved-receiver command returned `E2001` at
  `13:15-25`; the source expression starts on line 12 and its checked-in oracle
  requires line 12, column 15.
- CONFIRMED: the entity-receiver command returned a secondary `E3001` at
  `18:1-2`; the incompatible call and checked-in oracle are on line 17.
- CONFIRMED: the free-argument command returned a secondary `E3001` at
  `12:1-2`; the incompatible call and checked-in oracle are on line 11.
- CONFIRMED: all three fixtures preprocess `include net.url`; the only strict
  fixtures that currently combine `EXPECT_DIAGNOSTIC_LINE` with an `include`
  are these three cases.
- OBSERVED: comparable no-include UFCS type-mismatch fixtures report the
  physical call line correctly.
- NOT_VERIFIED: whether the off-by-one originates in source-map segment
  construction, legacy line-only error creation, or both paths.

## 7. Scope

### Affected

- semantic diagnostic locations after include/import preprocessing;
- UFCS unresolved-receiver and type-mismatch diagnostics;
- structured JSON clients, CLI rendering, strict line/column oracles, and IDE
  navigation based on compiler spans.

### Not affected / Unknown

- The expected diagnostic codes remain `E2001` and `E3001`.
- The false `result.vri` `E3021` is a separate semantic defect.
- Whether non-UFCS diagnostics using the same source-map path are shifted has
  not been established by this focused reproduction.

## 8. Impact

The compiler rejects the invalid programs, but points tools and users to the
next statement instead of the offending call. This breaks precise regression
oracles and can make IDE navigation and automated fixes target the wrong line.
It is a scoped diagnostic correctness defect, classified S2/P1.

## 9. Preliminary Analysis

- CONFIRMED: updating the fixtures to expect the following line would encode
  incorrect user-facing locations and conceal the compiler defect.
- CONFIRMED: `MethodCall` nodes receive the member token's `span_id`, while
  several type-mismatch paths still have line-based fallbacks; both must obey
  one original-source coordinate contract.
- HYPOTHESIS: the include source-map segment boundary or a mixed expanded-line
  versus physical-line path adds one line before rendering the diagnostic.
- NOT_VERIFIED: the smallest non-UFCS reproducer and the complete set of
  affected diagnostic codes.

## 10. Acceptance Criteria

- [x] The three checked-in fixtures report their existing expected line and,
  where specified, column without changing those oracles.
- [x] E2001 highlights the unresolved receiver/member token and E3001
  highlights the incompatible UFCS call or argument rather than column 1 of
  the next statement.
- [x] Focused regression coverage exercises exact spans both with and without
  include/import expansion and at source-map segment boundaries.
- [x] JSON, classic UI, modern UI, and IDE semantic output resolve the same
  physical file and span.
- [x] A mutation or deliberately broken source-map case proves the regression
  oracle fails on a one-line shift.
- [x] Group 11 has no `FAIL-WRONG-DIAGNOSTIC` attributable to these three
  fixtures after the independent false-E3021 issue is removed.
- [x] A VPS PLAN and accepted REPORT provide verification evidence before
  closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0037 — false Result enum-constructor `E3021` that currently precedes
  two diagnostics audited here.

### Plans

- VIRC-PLN-0021 — Fix source map marker order after includes and imports

### Reports

- VIRC-RPT-0038 — Fix source map marker order after includes and imports

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created and triaged from exact JSON diagnostic arrays and Group 11 line-oracle failures |
| 2026-10-05 | Linked VIRC-ISS-0037 because its false primary E3021 currently masks two affected diagnostics |
| 2026-10-05 | Linked VIRC-ISS-0037 |
| 2026-10-05 | Linked VIRC-PLN-0021 |
| 2026-10-05 | Linked VIRC-RPT-0038 |
| 2026-10-05 | Closed upon verification, bootstrap determinism, and accepted VIRC-RPT-0038 |
| 2026-10-05 | Follow-up audit added a permanent Group 11 exact-span gate and a synthetic one-line-shift mutation proof; all VIRC-ISS-0038 cases pass |
