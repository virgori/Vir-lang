---
id: "VIRC-PLN-0040"
type: "PLAN"
domain: "VIRC"
title: "Remove non-spec C and Rust syntax aliases"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
components:
  - "lexer"
  - "parser"
  - "stdlib"
  - "conformance-tests"
related:
  issues:
    - "VIRC-ISS-0048"
  plans: []
  reports:
    - "VIRC-RPT-0057"
supersedes: null
superseded_by: null
tags:
  - "syntax"
  - "legacy-alias"
  - "language-conformance"
---

# VIRC-PLN-0040 — Remove non-spec C and Rust syntax aliases

## 1. Objective

Remove the non-SPEC source spellings tracked by VIRC-ISS-0048, migrate active
Vir sources to canonical syntax, and make every retired spelling fail at the
lexer boundary with a stable replacement diagnostic while preserving `>>`
casts and postfix `~` swizzles.

## 2. Source Issues

- VIRC-ISS-0048

## 3. Scope

### In Scope

- Remove source acceptance for `return`, `while`, `&&`, infix `|`, prefix
  bitwise `~`, `<<`, `<<=`, and `>>=`.
- Remove the dead `TokType.While` parser compatibility path and obsolete
  symbolic-operator tokens that no longer have canonical source producers.
- Migrate active compiler, stdlib, examples, and positive tests to `out`,
  `when`, `&`, `or`, `bnot(...)`, `shl`, and `shr` as appropriate.
- Add focused classic/JSON diagnostic fixtures, canonical positive coverage,
  and a repository source-spelling conformance guard.
- Regenerate the self-hosted compiler bundle and verify bootstrap fixed point.

### Out of Scope

- Changing the active Vir specifications or introducing a compatibility mode.
- Renaming internal AST/IR/backend terminology such as return blocks, while
  nodes, or machine shift operations.
- Removing other observed legacy words (`continue`, `then`, `bit_shl`,
  `bit_shr`, `bit_and`, `bit_or`, `__not`) without a separate contract issue.
- Treating operator-like text inside comments, strings, Virgex patterns,
  embedded foreign source, or explicit negative fixtures as Vir syntax.

## 4. Current Architecture

`lexer/tokens.vri` maps `return` directly to `TokType.Out` and retains a
`TokType.While` value. `lexer.vri` emits tokens for `&&`, `<<`, `<<=`, and
`>>=`; the single-character table in `lexer/cursor.vri` maps `|` and `~` to
bitwise operators. Pratt and statement parsers consume these compatibility
tokens, including a distinct `while` branch even though `while` is no longer a
registered keyword. Active compiler and stdlib sources still contain the
retired symbolic spellings, so removing lexer support before migration would
break self-host compilation.

## 5. Proposed Architecture

The lexer is the single fail-closed boundary for retired spellings. It emits a
`TokType.Error` carrying the canonical replacement and exact offending span;
the frontend's existing early diagnostic path then produces the same message
in classic and JSON modes. Canonical tokens remain unchanged: `&`, `||`, word
bitwise operators, `>>` casts, and postfix swizzle `~`. The parser contains no
`while` compatibility dispatch and no prefix-bitwise-`~` interpretation.

A native conformance test scans only source-bearing regions of the maintained
Vir trees, excluding comments, string literals/foreign payloads, and dedicated
negative fixtures. This guards source migration independently from compiler
acceptance tests.

## 6. Design Decisions

### Decision 1 — Reject aliases in the lexer

**Decision:** Recognize retired words and symbols as explicit lexer errors with
replacement-oriented messages.

**Rationale:** This prevents an alias from producing a valid AST, avoids the
current `while` semantic E2001 fall-through, and gives stable spans before
parser recovery can change context.

**Alternatives considered:** Lex retired words as identifiers and special-case
them in statement dispatch; retain compatibility tokens and reject them in the
parser. Both keep unnecessary source grammar paths and give weaker diagnostics
outside statement-leading positions.

**Trade-offs:** The lexer needs context for `~`: postfix swizzle remains a
normal token, while prefix `~` is rejected by parser position. All other target
spellings can be rejected lexically.

### Decision 2 — Preserve internal operation kinds

**Decision:** Keep AST/IR operation kinds used by canonical word operators,
but remove only token/source compatibility that has no canonical producer.

**Rationale:** `shl`, `shr`, `or`, and `bnot(...)` still lower to shifts,
bitwise OR, and complement internally; source conformance does not require an
IR terminology rewrite.

**Alternatives considered:** Remove every `Bit*` token or `OpType` name. That
would break canonical operators and expand this issue into an IR redesign.

**Trade-offs:** Some internal names resemble the retired syntax but are not
accepted source spellings; the REPORT must distinguish those deliberately.

## 7. Implementation Plan

### Phase 1 — Source migration and inventory

- files/modules: maintained `.vri` sources under `compiler/src`, `stdlib`,
  examples, and positive test fixtures.
- changes: replace executable retired spellings with canonical equivalents;
  classify string/comment/foreign/negative occurrences as exclusions.
- dependencies: VIR-SPC-0015, VIR-SPC-0017 §§6.1, 9.2, 10.3–10.5 and §30,
  and the Vietnamese mirror VIR-SPC-0018.
- expected result: active sources no longer rely on compatibility acceptance.

### Phase 2 — Frontend fail-closed behavior

- files/modules: lexer token/keyword tables, scanner operator handling, Pratt
  unary/infix handling, statement dispatch/control helpers.
- changes: explicit diagnostics for each retired form; remove `TokType.While`
  and its parser path; preserve `>>` cast and postfix `~` swizzle.
- dependencies: Phase 1 migration.
- expected result: each spelling is rejected before it can form a valid AST.

### Phase 3 — Regression and repository guard

- files/modules: strict-v2 fixtures, `run_tests.sh`, and a native conformance
  test/tool owned by the repository suite.
- changes: classic and JSON assertions for messages/spans; positive canonical
  matrix; source scanner with explicit exclusions.
- dependencies: native verification workflow.
- expected result: aliases cannot silently return through code or fixtures.

### Phase 4 — Bootstrap, versioning, and closure

- files/modules: generated compiler bundle, compiler version metadata, ISSUE,
  PLAN, REPORT, and paper registry.
- changes: sync generated source, bump exactly once for VIRC-ISS-0048, rebuild,
  prove stage2 equals stage3, run focused/min/full tests, and record evidence.
- dependencies: Phases 1–3.
- expected result: accepted REPORT and closed ISSUE with reproducible evidence.

## 8. Compatibility

- Source compatibility intentionally narrows: non-SPEC aliases now fail with a
  canonical replacement message.
- Canonical source, ABI, serialized formats, and public stdlib APIs do not
  change.
- Parser compatibility paths for `while`, `&&`, symbolic bitwise OR, prefix
  `~`, and symbolic shifts are removed.
- LSP consumes the same frontend diagnostics; no protocol schema change.

## 9. Migration

Maintained sources are migrated before strict rejection. Users must replace
`return`/`while` and symbolic C/Rust operators with the canonical spellings
named by diagnostics. Strings, comments, and foreign payloads need no change.

## 10. Validation Plan

- Direct classic and `--json` compilation of one fixture per retired spelling,
  asserting nonzero status, replacement text, and exact line/column.
- Positive compile/run coverage for `&`, `||`, `and`, `or`, `xor`, `bnot`,
  `shl`, `shr`, `>>` cast, postfix swizzle, and canonical assignments.
- Native source-spelling guard with comments, strings, foreign source, and
  negative-fixture exclusions tested explicitly.
- Focused Groups 1 and 10, then `./run_tests.sh min` and `full`.
- `python3 tools/sync_virc.py --check`, compiler-version policy checks, rebuilt
  `bin/virc --version`, and stage2/stage3 fixed-point comparison.
- `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Broad text replacement changes strings or comments | Medium | High | Migrate only executable Vir tokens and inspect every changed hunk |
| Rejecting `~` breaks postfix swizzle | Medium | High | Keep the token and reject only prefix parse position; add read/write swizzle positives |
| Rejecting `>>=` accidentally changes `>>` cast | Low | High | Order the three-character diagnostic before the normative two-character cast and add cast coverage |
| Dirty worktree changes are overwritten | Medium | High | Apply narrow patches against current files and inspect per-file diffs |
| Generated bundle diverges from canonical source | Medium | High | Use sync workflow and require `--check` plus bootstrap fixed point |

## 12. Rollback Strategy

Revert the alias diagnostics, parser cleanup, source migrations, fixtures, and
generated sync as one compiler change, then reopen VIRC-ISS-0048. The change
does not migrate persistent data or serialized formats.

## 13. Exit Criteria

- [x] Active source inventory is clean or each retained match is classified.
- [x] Every retired spelling fails with stable classic/JSON diagnostics.
- [x] Canonical operators, cast, swizzle, and assignments pass.
- [x] Source guard, focused groups, min/full, sync, version, and fixed-point gates pass.
- [x] REPORT is accepted and VIRC-ISS-0048 is closed.

## 14. Related Papers

- VIRC-ISS-0048 — source issue and acceptance contract.
- VIR-SPC-0015 — forbidden substitutions and canonical syntax summary.
- VIR-SPC-0017 / VIR-SPC-0018 — normative English/Vietnamese language specifications.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created and activated from active lexer/parser/source audit |
| 2026-10-10 | Linked VIRC-RPT-0057 |
| 2026-10-10 | Completed after accepted report and full 953/953 verification |
