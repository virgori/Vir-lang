---
id: VIRC-ISS-0000
type: ISSUE
domain: VIRC
title: Example optimizer validation failure
status: RESOLVED
severity: S2
priority: P2
created: 2026-10-02
updated: 2026-10-02
owners: [compiler-team]
components: [optimizer]
related:
  issues: []
  plans: [VIRC-PLN-0000]
  reports: [VIRC-RPT-0000]
supersedes: null
superseded_by: null
tags: [example, validation]
---

# VIRC-ISS-0000 — Example optimizer validation failure

## 1. Summary

An example issue showing how a failing optimizer invariant is recorded.

## 2. Context

This fixture is not a production defect and exists only to exercise VPS.

## 3. Expected Behavior

The optimizer verifier rejects malformed control-flow metadata.

## 4. Actual Behavior

The example precondition assumes the verifier accepted that malformed input.

## 5. Reproduction

Run the fixture-specific regression case described by the linked example plan.

## 6. Evidence

- OBSERVED: the hypothetical regression test fails before the example change.
- NOT_VERIFIED: no production compiler behavior is claimed by this fixture.

## 7. Scope

### Affected

- Example optimizer validation path.

### Not affected / Unknown

- All production code and releases.

## 8. Impact

This fixture demonstrates traceability only.

## 9. Preliminary Analysis

- CONFIRMED: the paper chain and metadata are validator fixtures.
- OBSERVED: the example describes a missing invariant check.
- HYPOTHESIS: an early verifier check would produce a clearer failure.
- NOT_VERIFIED: whether such a defect exists in production.

## 10. Acceptance Criteria

- [x] The example plan links this issue.
- [x] The example report records verification and a conclusion.

## 11. Related Papers

- VIRC-PLN-0000
- VIRC-RPT-0000

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Initial example issue |
