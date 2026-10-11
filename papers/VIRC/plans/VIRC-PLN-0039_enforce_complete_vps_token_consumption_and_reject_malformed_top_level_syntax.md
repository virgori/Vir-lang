---
id: "VIRC-PLN-0039"
type: "PLAN"
domain: "VIRC"
title: "Enforce complete VPS token consumption and reject malformed top-level syntax"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0056"
supersedes: null
superseded_by: null
tags:
  - "vps"
  - "parser"
  - "fail-closed"
---

# VIRC-PLN-0039 — Enforce complete VPS token consumption and reject malformed top-level syntax

## 1. Objective

Make the active Virgex VPS compiler reject any token stream that is not fully
consumed by the grammar, while preserving valid edge anchors, escaped literal
pipes, and alternatives enclosed by `:(` and `:)`.

## 2. Source Issues

- VIRC-ISS-0054

## 3. Scope

### In Scope

- Validate the parser cursor after the optional trailing end anchor.
- Reject top-level pipes that are not the first or last token.
- Reject dangling quantifiers, prefix optionals without an expression, and
  other unexpected trailing tokens instead of compiling a prefix.
- Add focused fail-closed tests plus positive anchor, escape, and grouped
  alternation coverage.

### Out of Scope

- Changing `VIR-SPC-0019` or the VPS grammar.
- Redesigning the public `virgex.compile` return type or panic contract.
- Changing the regex frontend or pattern-engine matching semantics.

## 4. Current Architecture

`vps_tokenize` produces a `Vec of (VpsToken)` terminated by `VpsTok.Eof`.
`VpsParser.parse_sequence` deliberately stops on EOF, group close, or pipe so
that grouped alternation can consume separators. `_virgexCompile` separately
recognizes a leading pipe as a start anchor and a pipe immediately followed by
EOF as an end anchor. It then compiles the parsed body without requiring the
final cursor to point at EOF. Consequently, an interior top-level pipe leaves
tokens unconsumed and the valid prefix is compiled.

The current compile-error convention is unchanged: tokenizer failures are
converted to `panic` by `_vps_tokens_or_panic`. The parser currently has no
separate public error value.

## 5. Proposed Architecture

Keep sequence parsing reusable for groups, but make `_virgexCompile` own the
complete-pattern acceptance gate. After parsing the body and consuming at most
one legal trailing anchor, the cursor must identify the sole EOF token. Any
other token or any token following that EOF is rejected before IR compilation.

## 6. Design Decisions

### Decision 1 — Validate at the complete-pattern boundary

**Decision:** Add the full-consumption check in `_virgexCompile`, after legal
anchor handling and before `pattern_compile_ir`.

**Rationale:** `parse_sequence` must continue stopping at pipes and group-close
tokens for grouped alternatives. Only the outer compiler knows whether a pipe
is a legal final anchor and whether EOF is expected.

**Alternatives considered:** Reject every pipe in `parse_sequence`. This would
break valid group alternation and conflate sequence parsing with outer-pattern
anchor classification.

**Trade-offs:** The public API continues to reject malformed patterns through
the existing panic-based compile contract; a typed compile result remains
outside this issue.

## 7. Implementation Plan

### Phase 1 — Parser acceptance gate

- files/modules: `stdlib/vir/virgex/virgex.vri` (`virgex` in
  `stdlib/stdlib.vri`).
- changes: require the final parser cursor to point at the single EOF token;
  reject unexpected or trailing tokens before IR compilation.
- dependencies: active grammar in `VIR-SPC-0019` §§4, 9, and 18.
- expected result: `@AZ | @0`, dangling quantifiers, and dangling `?` fail
  closed; valid anchors, escapes, and grouped alternatives still compile.

### Phase 2 — Focused regression coverage

- files/modules: a dedicated strict-v2 fixture plus Group 28 registration in
  `run_tests.sh`, or an existing focused native regression runner when it can
  assert child-process failure without weakening current tests.
- changes: exercise invalid patterns in separate processes and retain positive
  semantic assertions.
- dependencies: self-hosted `virc` and the native repository test runner.
- expected result: the prior fail-open behavior becomes a deterministic test
  failure if reintroduced.

### Phase 3 — Verification and lifecycle closure

- files/modules: `VIRC-ISS-0054`, this PLAN, a new REPORT, and
  `papers/REGISTRY.yaml`.
- changes: record actual diff, map evidence to each acceptance criterion, and
  close only after the focused suite and VPS validators pass.
- dependencies: `./run_tests.sh 28`, `./paper registry --check`, and
  `./paper validate`.
- expected result: accepted verification evidence and reciprocal traceability.

## 8. Compatibility

- Source compatibility: valid VPS syntax is preserved; invalid partial parses
  are intentionally rejected.
- ABI and serialized formats: unchanged.
- Parser compatibility: stricter acceptance at the complete-pattern boundary.
- LSP protocol: unchanged.
- Public API: signature unchanged; malformed inputs use the existing compile
  failure path.
- Stdlib behavior: only invalid patterns change from partial compilation to
  rejection.

## 9. Migration

No migration is required for conforming patterns. Callers relying on malformed
top-level pipes or trailing syntax must correct those patterns.

## 10. Validation Plan

- Reproduce the pre-fix fail-open behavior using the native `vir-test` filter
  path.
- Add negative cases for an interior top-level pipe, dangling quantifiers,
  dangling optional markers, and tokens following a legal end anchor.
- Add or retain positive cases for leading/trailing anchors, `$|`, and grouped
  alternatives.
- Run `./run_tests.sh 28` and the focused malformed-pattern regression.
- Run `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A cursor check rejects a legal edge anchor | Low | High | Check after optional end-anchor consumption and require EOF |
| Group alternation is rejected as top-level syntax | Low | High | Keep group pipe consumption inside `VpsParser.parse_expr` and cover grouped alternatives |
| Existing owner edits in the same stdlib file are overwritten | Medium | High | Apply a narrow additive patch and inspect the final diff against the current worktree |
| Panic-based rejection yields a different process status than a future typed API | Medium | Low | Preserve the current compile contract and scope typed errors to separate API work |

## 12. Rollback Strategy

Revert the full-consumption guard and its dedicated regression fixture. No data
or format migration is involved. Reopen VIRC-ISS-0054 if verification later
shows a valid VPS construct is rejected.

## 13. Exit Criteria

- [x] `_virgexCompile` rejects every non-EOF token remaining after legal anchor handling.
- [x] Invalid patterns cannot return or match a prefix `Pattern`.
- [x] Valid edge anchors, escaped pipes, and grouped alternatives retain their semantics.
- [x] Focused malformed-pattern regression and Group 28 pass.
- [x] VIRC-RPT-0056 is accepted with `READY_FOR_CLOSE`.

## 14. Related Papers

- VIRC-ISS-0054 — source issue.
- VIR-SPC-0019 — active VPS grammar and full-consumption requirement.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Created and activated the implementation plan from current source and executable reproduction evidence |
| 2026-10-09 | Linked VIRC-RPT-0056 |
| 2026-10-09 | Completed after focused regression and Group 28 passed and VIRC-RPT-0056 was accepted |
