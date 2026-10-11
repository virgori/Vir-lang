---
id: "VIRC-ISS-0054"
type: "ISSUE"
domain: "VIRC"
title: "VPS parser silently accepts unconsumed top-level syntax"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "virgex"
  - "vps-parser"
  - "stdlib-boundary"
  - "conformance-tests"
related:
  issues: []
  plans:
    - "VIRC-PLN-0039"
  reports:
    - "VIRC-RPT-0056"
supersedes: null
superseded_by: null
tags:
  - "vps"
  - "parser"
  - "fail-open"
  - "invalid-syntax"
---

# VIRC-ISS-0054 — VPS parser silently accepts unconsumed top-level syntax

## 1. Summary

The VPS parser can compile a valid prefix while silently ignoring invalid,
unconsumed top-level syntax. For example, `@AZ | @0` is invalid under active
`VIR-SPC-0019` §9 and §18, but the compiled pattern behaves as `@AZ`.

## 2. Context

VPS parsing is implemented by the Virgex frontend in
`stdlib/vir/virgex/virgex.vri`. The active syntax SPEC requires a parser to
consume the complete token stream or reject the pattern. This ISSUE is owned
in VIRC because the defect is parser acceptance/conformance; the public API
contract and exact failure representation remain the standard-library
contract's responsibility.

## 3. Expected Behavior

- Invalid syntax, including an interior top-level pipe or any trailing token
  that is not a legal end anchor, must not produce a compiled partial pattern.
- The parser must either consume the complete token stream or reject the
  pattern through the library's documented compile-error contract.
- Valid leading/trailing anchors and `|` alternatives inside groups must
  continue to compile and retain their specified meaning.

## 4. Actual Behavior

`virgex.compile("@AZ | @0")` returns a `Pattern` instead of rejecting the
pattern. A compiled pattern matches the prefix `A`, ignoring the interior pipe
and the trailing `@0` tokens.

## 5. Reproduction

The following standalone source was compiled with the current self-hosted
compiler (`virc 2026.1.2`, repository revision
`930d21eef3e63b8bae7b748a35e6e8c00f72215b`):

```vir
include virgex

func main:
    var pat = virgex.compile("@AZ | @0")
    if virgex.fullMatch(pat, "A") do
        print("ACCEPTED_PREFIX")
    else
        print("REJECTED")
    end
end.
```

Commands:

```sh
./bin/virc /private/tmp/vps_parser_fail_open_probe.vri \
  -o /private/tmp/vps_parser_fail_open_probe
/private/tmp/vps_parser_fail_open_probe
```

Observed output:

```text
ACCEPTED_PREFIX
exit status: 0
```

## 6. Evidence

Evidence:

- `CONFIRMED`: the reproduction compiled successfully and printed
  `ACCEPTED_PREFIX` with exit status 0.
- `CONFIRMED`: `VIR-SPC-0019` §9 says top-level pipes are not alternatives;
  §18 requires full token-stream consumption or rejection.
- `CONFIRMED`: `parse_sequence` stops at `Pipe` in
  `stdlib/vir/virgex/virgex.vri:542-563`. `_virgexCompile` recognizes a pipe
  as an end anchor only if it is followed by EOF, but does not verify EOF
  consumption before compiling the partial body (`:566-608`).
- `OBSERVED`: existing strict VPS tests exercise valid anchors and grouped
  alternatives, but do not cover this invalid top-level-pipe acceptance.

## 7. Scope

### Affected

- VPS tokenization/parsing and compilation in `stdlib/vir/virgex/virgex.vri`.
- Any caller relying on VPS compile to reject malformed patterns.

### Not affected / Unknown

- Traditional `regex` frontend: not implicated by this reproduction.
- Exact library-level compile error type/diagnostic: not specified by
  `VIR-SPC-0019`; leave it to the separate standard-library API contract.

## 8. Impact

Malformed VPS patterns may be accepted as a different, shorter pattern. This
can silently change validation or search results and make a caller believe
the complete expression was checked when only its prefix was compiled. The
reproduction is scoped to VPS; no evidence implicates the traditional regex
frontend.

## 9. Preliminary Analysis

- **CONFIRMED:** the sequence parser stops at a top-level pipe and
  `_virgexCompile` does not require its final cursor to reach EOF.
- **OBSERVED:** the executable reproducer accepts `@AZ | @0` as a pattern
  matching `A`.
- **HYPOTHESIS:** the same missing full-consumption guard may accept other
  malformed trailing-token cases, such as a quantifier with no base
  expression; those cases were not executed in this investigation.
- **NOT_VERIFIED:** the complete set of malformed patterns accepted, and the
  appropriate public error representation for `virgex.compile`.

Resolution evidence (2026-10-09):

- `CONFIRMED`: `_virgexCompile` now requires its final cursor to point to the
  sole EOF token after legal edge-anchor handling.
- `CONFIRMED`: a negative parser cursor propagates dangling expressions and
  unexpected expression tokens without changing normal EOF, group-close, or
  pipe sequence termination.
- `CONFIRMED`: the dedicated native contract rejects the original reproducer,
  dangling and repeated quantifiers, dangling optionals, and tokens after a
  would-be end anchor with an `Invalid VPS pattern:` diagnostic.
- `CONFIRMED`: `./run_tests.sh 28` passes 8/8, including valid anchors, escaped
  pipes, and grouped alternation.

## 10. Acceptance Criteria

- [x] Reject `@AZ | @0` and other top-level pipes that are neither a leading
      nor trailing anchor; never return a pattern compiled from only a prefix.
- [x] Reject any remaining unexpected token after parsing, including dangling
      quantifiers and trailing tokens, according to the documented library
      compile-error contract.
- [x] Add regression tests that assert malformed patterns fail and prove that
      no partial pattern is returned or matched.
- [x] Preserve acceptance and semantics for valid leading/trailing anchors,
      escaped literal pipes, and alternation pipes inside groups.
- [x] Run the focused Virgex lexer/parser and end-to-end suites, then
      `./paper registry --check` and `./paper validate`.

## 11. Related Papers

### Issues

- None.

### Plans

- VIRC-PLN-0039 — Enforce complete VPS token consumption and reject malformed
  top-level syntax.

### Reports

- VIRC-RPT-0056 — Complete VPS token consumption implementation and
  verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Opened with an executable reproducer and source-level parser evidence; linked to active VPS syntax requirements |
| 2026-10-09 | Triaged and moved through PLANNED to IMPLEMENTING under VIRC-PLN-0039; reproduced fail-open behavior on the current tree while Group 28 remained 7/7 passing |
| 2026-10-09 | Linked VIRC-PLN-0039 |
| 2026-10-09 | Linked VIRC-RPT-0056 |
| 2026-10-09 | Marked RESOLVED after the focused contract and Group 28 passed and VIRC-RPT-0056 was accepted |
| 2026-10-09 | Closed after synchronized-registry and VPS validation gates passed for 260 production papers |
