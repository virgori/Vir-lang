---
id: "VIR-ISS-0003"
type: "ISSUE"
domain: "VIR"
title: "Saga control transfer uses redundant resume retry and resume revert forms"
status: "TRIAGED"
severity: "S3"
priority: "P2"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "language"
  - "compiler"
components:
  - "syntax"
  - "error-handling"
  - "saga-compensation"
  - "parser"
  - "semantic-analysis"
  - "ast-to-mir"
  - "diagnostics"
  - "tests"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "saga"
  - "retry"
  - "rethrow"
  - "revert"
  - "language-design"
  - "migration"
---

# VIR-ISS-0003 — Saga control transfer uses redundant resume retry and resume revert forms

## 1. Summary

Before Vir 2.1, Vir expressed the two terminal control transfers available
inside a local `revert` clause as `resume retry` and `resume revert`. The shared
`resume` prefix adds no independent behavior, while `resume retry` can be read
as continuing an already-running retry even though it restarts the complete
enclosing `try` block. This ISSUE evaluated replacing those forms with the
standalone, symmetric control statements `retry` and `rethrow`.

This paper does not make `saga` a keyword. Its normative language-design part
was resolved in Vir 2.1; compiler and tooling migration remains deferred.

## 2. Context

Before their Vir 2.1 revision, VIR-SPC-0017 and VIR-SPC-0018 section 13.7
defined local compensation through `try: ... revert ... end`. Within the local
`revert`, `resume retry` restarted the current `try`, while `resume revert`
propagated the current error to the
next enclosing or function-level `revert`. The latter propagation chain is the
documented Saga compensation pattern.

The lexer reserves `resume` and `retry` separately. The parser represents both
forms as one `ResumeStmt` with a textual target, and AST-to-MIR lowering then
branches on that target. There is currently no standalone `retry` statement or
`rethrow` keyword.

## 3. Expected Behavior

- The canonical syntax should state the two terminal decisions directly:
  `retry` restarts the current `try`, and `rethrow` propagates the unchanged
  current error to the outer compensation boundary.
- `revert` should remain exclusively recognizable as a compensation clause;
  it should not also be used as a bare propagation statement.
- The words used by the syntax should describe actual control flow: retrying a
  block and rethrowing an error, not resuming execution at the failure point.
- Any transition must define source compatibility, diagnostics, formatter/LSP
  behavior, test migration, and a removal gate for legacy spellings.

## 4. Actual Behavior

The following records the baseline at triage, before the Vir 2.1 normative
resolution:

- Only `resume retry` and `resume revert` are accepted in a local `revert`.
- `resume` has no standalone semantic mode; the following token is mandatory.
- `resume retry` jumps to the start of the current `try`, not to the original
  failure instruction.
- `resume revert` propagates the existing error; it does not execute a second
  local `revert` clause.
- The current grammar therefore uses two tokens where each operation can be
  expressed unambiguously by one terminal statement.

## 5. Reproduction

Verify the two current forms:

```sh
./bin/virc tests/vri/test_try_isolate_retry.vri \
  -q -o /tmp/vir_saga_retry_current
/tmp/vir_saga_retry_current

./bin/virc tests/strict_v2/error_resume_revert_saga_e2e.vri \
  -q -o /tmp/vir_saga_revert_current
/tmp/vir_saga_revert_current

sed -n '157,174p' \
  compiler/src/frontend/parser/stmt_dispatch/concurrency.vri
```

The first artifact prints `3` and `777`; the second prints `11`, `22`, `9`,
`33`, and `0`. These executions establish current behavior, not approval of
the proposed replacement syntax.

## 6. Evidence

- CONFIRMED at triage: both active language SPECs defined `resume retry` and
  `resume revert` in section 13.7.
- CONFIRMED: `compiler/src/frontend/lexer/tokens.vri` reserves both `resume`
  and `retry` as keywords, but has no `rethrow` token.
- CONFIRMED: `parseResumeStatement` accepts exactly `retry` or `revert` after
  `resume` and reports E3062 otherwise.
- CONFIRMED: `lower_stmt_resume` lowers the `retry` target to the current retry
  block and the `revert` target to the outer error/compensation block.
- CONFIRMED: the two focused current-syntax fixtures compiled and executed with
  their expected outputs on 2026-10-04 using the current repository compiler.
- OBSERVED: 97 references to the current forms or their implementation tokens
  exist across the two SPECs, compiler source, and tests under the focused
  search scope; migration is therefore broader than a parser-only rename.

## 7. Scope

### Affected

- normative English and Vietnamese language specifications;
- lexer tokens, parser AST, semantic context checks, diagnostics, and
  AST-to-MIR control-flow lowering;
- formatter, syntax highlighting, LSP completion/diagnostics, and source tools;
- positive, negative, bootstrap, strict-v2, and memory-contract fixtures using
  the current forms;
- compatibility policy for existing Vir source.

### Not affected / Unknown

- the `try: ... revert ... end` compensation structure itself;
- `throw`, `ensure`, `erx`, `timeout`, `isolate`, `atomic`, and `emit`
  semantics except where tests contain the migrated control statements;
- the decision that `saga` remains a design-pattern name rather than a keyword;
- NOT_VERIFIED: preferred deprecation duration and whether an automatic source
  fixer is required before removal of legacy forms.

## 8. Impact

The current syntax is functional but unnecessarily verbose and semantically
misleading. It increases the vocabulary needed to read compensation code and
makes the difference between a `revert` clause and error propagation harder to
explain. The impact is language ergonomics and long-term clarity rather than a
runtime correctness defect, so the ISSUE is S3/P2.

## 9. Preliminary Analysis

- CONFIRMED: `resume` does not encode a third operation; it is only a required
  prefix for the two existing targets.
- CONFIRMED: using bare `revert` as the propagation statement would overload a
  keyword that already introduces local and function-level clauses.
- OBSERVED: `retry` is already reserved, so accepting it as a standalone
  statement does not consume a previously available identifier.
- HYPOTHESIS: `retry` and `rethrow` provide the clearest one-word pair because
  each names the actual terminal control transfer and preserves `revert` for
  compensation clauses.
- HYPOTHESIS: a compatibility interval accepting the old spellings with a
  stable deprecation diagnostic can avoid an immediate ecosystem break.
- NOT_VERIFIED: whether the compatibility interval belongs in the next minor
  language revision or requires a major-version transition policy.

## 10. Normative Resolution (2026-10-04)

Vir 2.1 selects the standalone, symmetric terminal statements `retry` and
`rethrow`. The active English and Vietnamese specifications now define the
same grammar, placement, isolate restoration, `erx` propagation, and
unreachable-code semantics. `revert` remains a clause keyword and `saga`
remains a design-pattern term rather than a keyword.

For source compatibility, Vir 2.x implementations may accept `resume retry`
and `resume revert` as deprecated input. Acceptance requires a stable
deprecation diagnostic and identical semantics; formatters and generators
emit only `retry` and `rethrow`, providing the automatic source rewrite path.
Legacy removal is allowed no earlier than Vir 3.0.

This resolution changes only the VIR specification papers. Lexer, parser,
semantic analysis, MIR lowering, formatter/LSP behavior, compiler diagnostics,
fixtures, bootstrap, and self-host work belong to VIRC implementation and are
intentionally not performed here. The ISSUE therefore remains `TRIAGED`.

## 11. Acceptance Criteria

- [ ] An approved VIR PLAN selects or rejects `retry`/`rethrow` after comparing
  at least: current syntax, bare `retry` plus `throw erx`, and
  `retry`/`rethrow`.
- [x] If selected, both active language SPECs define identical grammar,
  placement, state restoration, propagation, and unreachable-code semantics.
- [x] `retry` is valid only inside the local `revert` of an enclosing `try` and
  restarts that exact `try` after the documented isolate restoration.
- [x] `rethrow` is valid only where a current error exists and preserves `erx`
  while propagating to the outer compensation boundary.
- [x] `revert` remains a clause keyword and `saga` remains non-keyword
  terminology.
- [x] A documented compatibility window either rejects legacy forms at a
  declared major boundary or accepts them temporarily with stable deprecation
  diagnostics and an automated fix path.
- [ ] Parser, semantic, MIR, LSP, formatter, bootstrap, O0-O3, and self-host
  tests cover the new syntax and reject invalid contexts.
- [ ] A VPS REPORT records implementation, migration counts, fixed-point
  self-host evidence, and the final closure decision.

## 12. Related Papers

### Issues

- None yet.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Resolved the normative VIR portion in v2.1 as `retry`/`rethrow`; retained TRIAGED status for deferred VIRC implementation and verification |
| 2026-10-04 | Created and triaged from the current Saga syntax, parser, lowering, and focused runtime fixtures |
