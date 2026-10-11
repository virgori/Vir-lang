---
id: "VIRC-RPT-0056"
type: "REPORT"
domain: "VIRC"
title: "Complete VPS token consumption implementation and verification report"
status: "ACCEPTED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "virgex"
  - "vps-parser"
  - "conformance-tests"
related:
  issues:
    - "VIRC-ISS-0054"
  plans:
    - "VIRC-PLN-0039"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "vps"
  - "parser"
  - "fail-closed"
---

# VIRC-RPT-0056 — Complete VPS token consumption implementation and verification report

## 1. Executive Summary

The Virgex VPS compiler now rejects partial parses before IR compilation. The
implementation propagates malformed-expression state through the parser cursor
and requires the complete-pattern cursor to identify the sole EOF token after
legal leading and trailing anchors are handled. A dedicated native regression
rejects six malformed forms and preserves representative anchors, an escaped
pipe, and grouped alternation. Focused Group 28 verification passes 8/8.

## 2. Source Issues

- VIRC-ISS-0054

## 3. Source Plans

- VIRC-PLN-0039

## 4. Implementation Summary

- Mark genuinely unexpected expression tokens with a negative parser cursor,
  while retaining EOF, group close, and pipe as normal sequence terminators.
- Propagate malformed prefix-optionals and nested group parse failures.
- Require `_virgexCompile` to finish on exactly one EOF token after optional
  end-anchor consumption.
- Add a small native compile probe and a shell contract that verifies process
  rejection and diagnostic presence for malformed patterns, plus matching
  semantics for valid forms.
- Register the contract in repository test Group 28.

## 5. Changes by Component

### `stdlib/vir/virgex/virgex.vri`

- Change: added parser error-cursor propagation and the final EOF acceptance
  gate before `pattern_compile_ir`.
- Reason: the prior compiler accepted a valid prefix and ignored remaining
  top-level tokens.
- Impact: malformed VPS inputs now terminate through the existing panic-based
  compile-error path; valid syntax retains the same public API and semantics.

### `tests/strict_v2/vps_parser_compile_probe.vri`

- Change: added a native program that compiles an argument pattern and reports
  full-match semantics for an argument string.
- Reason: malformed compilation must be observed in a separate process because
  the current public compile contract is fail-fast rather than a typed result.
- Impact: provides a reusable executable boundary for rejection tests.

### `tests/test_vps_parser_full_consumption.sh` and `run_tests.sh`

- Change: added six negative and four positive cases and registered them as a
  Group 28 contract.
- Reason: existing parser tests covered tokenizer errors and valid syntax but
  did not assert complete top-level consumption.
- Impact: reintroducing partial compilation now fails the focused suite.

## 6. Deviations from Plan

No material deviations from the approved plan. During implementation, a
dedicated boolean parser field and a returned-node sentinel were evaluated but
were not retained because focused execution exposed instability in that state
path on valid unanchored inputs. The final design uses the already authoritative
parser cursor as the single error and consumption channel. Scope and public API
remain unchanged.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Pre-fix native reproduction | PASS | `./bin/vir-test --filter '@AZ \| @0' --manifest /private/tmp/vps_parser_missing_manifest.tsv ...` reached manifest loading with exit 1, proving the malformed filter was accepted before the fix |
| Focused fail-closed contract | PASS | `./tests/test_vps_parser_full_consumption.sh` exited 0; six malformed patterns were rejected with `Invalid VPS pattern:` diagnostics and four valid-form checks passed |
| Virgex/parser Group 28 | PASS | `./run_tests.sh 28` reported 8/8 PASS, including the new contract |
| Rebuilt native runner reproduction | PASS | temporary rebuild of `tools/vir-test/src/main.vri` rejected `@AZ \| @0` with `Invalid VPS pattern: unexpected top-level token`; valid anchor, `$\|`, and grouped-alternation filters advanced to manifest loading |
| VPS registry and validation | PASS | `./paper registry --check` reported synchronized; `./paper validate` passed 260 production and 3 example papers |

### Regression

The exact prior reproducer no longer returns a `Pattern`: the native runner
terminates before manifest loading with the parser diagnostic. Dangling
quantifiers, repeated quantifiers, dangling `?`, `?` before an end anchor, and
tokens after a would-be end anchor are also rejected.

### Conformance

The final cursor gate implements `VIR-SPC-0019` §18's full-token-consumption
requirement. Positive cases exercise the edge-anchor rule from §4 and enclosed
alternation rule from §9.

## 8. Acceptance Criteria

- [x] Interior top-level pipes, including `@AZ | @0`, are rejected before a
      partial `Pattern` can be returned.
- [x] Unexpected remaining tokens and dangling quantifier/optional forms are
      rejected through the existing compile diagnostic path.
- [x] Regression coverage asserts nonzero process termination and diagnostic
      presence, proving malformed patterns do not reach matching.
- [x] Leading/trailing anchors, escaped literal pipes, and grouped alternation
      retain successful compilation and matching semantics.
- [x] The focused contract and Group 28 pass; VPS registry and validation gates
      passed immediately before closure.

## 9. Known Limitations

- `virgex.compile` still uses the existing panic-based failure contract rather
  than returning a typed compile result. That API design is explicitly outside
  VIRC-ISS-0054 and is not defined by `VIR-SPC-0019`.
- Verification targets the current macOS ARM64 host. The change is parser-level
  Vir code, but no separate Linux or x86-64 runtime execution was performed.

## 10. Remaining Work

No remaining work is required for VIRC-ISS-0054. A future typed compile-error
API would require a separately scoped standard-library contract.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0054 — source issue.
- VIRC-PLN-0039 — implementation plan.
- VIR-SPC-0019 — normative VPS grammar and full-consumption requirement.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Accepted implementation and verification evidence with READY_FOR_CLOSE conclusion |
