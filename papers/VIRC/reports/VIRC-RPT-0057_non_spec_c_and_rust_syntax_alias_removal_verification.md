---
id: "VIRC-RPT-0057"
type: "REPORT"
domain: "VIRC"
title: "Non-spec C and Rust syntax alias removal verification"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0040"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "syntax"
  - "legacy-alias"
  - "language-conformance"
  - "self-hosting"
---

# VIRC-RPT-0057 — Non-spec C and Rust syntax alias removal verification

## 1. Executive Summary

The compiler now rejects every non-SPEC source spelling tracked by
VIRC-ISS-0048: `return`, `while`, `&&`, infix `|`, prefix bitwise `~`, `<<`,
`<<=`, and `>>=`. Each rejected spelling has a focused classic and JSON
diagnostic with a canonical replacement and stable source position. Active
compiler, stdlib, tool, and positive-test sources were migrated before the
compatibility paths were removed.

Canonical `out`, `when ... loop`, `&`, `||`, `and`, `or`, `xor`, `bnot`,
`shl`, `shr`, `>>` cast, postfix swizzle `~`, and canonical compound
assignments remain operational. The final self-hosted compiler is version
2026.1.12, its stage-2 and stage-3 binaries are byte-identical, the minimum
suite passes 494/494, and the full suite passes 953/953.

## 2. Source Issues

- VIRC-ISS-0048

## 3. Source Plans

- VIRC-PLN-0040

## 4. Implementation Summary

- Removed obsolete source-token and parser paths for `return`, `while`,
  `&&`, symbolic bitwise OR, symbolic shifts, and shift assignments.
- Kept `~` as a postfix swizzle token and added a position-aware parser error
  for its retired prefix bitwise meaning.
- Registered canonical `bnot(...)` as the public spelling for bitwise
  complement while retaining the existing internal operation ID.
- Migrated executable aliases throughout maintained compiler, stdlib, tools,
  and positive fixtures; retained only classified text in comments, strings,
  foreign source, and explicit negative fixtures.
- Added eight negative diagnostic fixtures, two positive canonical fixtures,
  a classic/JSON contract, and a 1,935-file repository source guard.
- Synchronized the generated compiler, performed the required internal version
  bump, rebuilt `bin/virc`, and proved self-host fixed point.

## 5. Changes by Component

### `compiler/src/frontend/lexer` and `compiler/src/frontend/parser`

- Change: removed `TokType.While`, `LogicalAnd`, standalone `BitOr`, prefix
  `BitNot`, `BitShlAssign`, and `BitShrAssign` source compatibility; added
  targeted lexer errors and the prefix-`~` parser diagnostic.
- Reason: these spellings are not part of the active Vir grammar and could
  previously form valid AST nodes or misleading semantic errors.
- Impact: invalid aliases fail before semantic lowering; `>>`, `||`, `|=`,
  postfix swizzle, and canonical word operators remain distinguishable.

### `compiler/src/frontend/parser/builtins.vri` and MIR lowering

- Change: registered `bnot` against the existing bitwise-not builtin ID and
  routed canonical calls through the existing MIR operation.
- Reason: source migration requires the normative spelling to be executable,
  not merely documented.
- Impact: no IR, ABI, or backend operation-kind change.

### Maintained `.vri` source trees

- Change: migrated executable `&&`, infix `|`, prefix `~`, symbolic left/right
  shifts, and `return` occurrences under compiler, stdlib, tools, and positive
  tests to canonical spellings. Multi-line byte-swap expressions and logging
  pattern alternatives caught by the source guard were also normalized.
- Reason: strict frontend rejection cannot be enabled while the repository
  itself depends on retired aliases.
- Impact: the self-hosted bundle and all active suites compile under the same
  grammar exposed to users.

### Tests and repository source guard

- Change: added one negative fixture per retired spelling, positive canonical
  operator/swizzle matrices, classic and JSON assertions, and a lexical source
  guard that ignores comments and strings.
- Reason: test both compiler behavior and repository hygiene independently.
- Impact: reintroducing an alias, changing its replacement diagnostic/span, or
  breaking a preserved canonical form fails Group 10.

## 6. Deviations from Plan

The plan proposed a native source-spelling scanner. The implemented guard is a
small Perl lexical scanner invoked by the established shell test harness. It
does not participate in compiler behavior or build/release orchestration and
adds no Python dependency. This deviation kept the guard independent from the
lexer being tested while preserving the planned source-region exclusions and
fail-closed result. All compiler validation itself uses the self-hosted native
binary and native repository test runners.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Focused diagnostic/source contract | PASS | `VIRC=./bin/virc tests/test_noncanonical_syntax_contract.sh`; all eight spellings failed in classic and JSON modes with exact line/column, and 1,935 maintained `.vri` files passed the lexical guard |
| Group 1 | PASS | `./run_tests.sh 1` reported 54/54 |
| Group 9 | PASS | `./run_tests.sh 9` reported 35/35 |
| Group 10 | PASS | `./run_tests.sh 10` reported 61/61, including the new contract and canonical positives |
| Minimum suite | PASS | `./run_tests.sh min` reported 494/494 |
| Full suite | PASS | `./run_tests.sh full` reported 953/953 |
| Generated-source synchronization | PASS | `python3 tools/sync_virc.py --check` reported the bundle identical to source modules |
| Version policy | PASS | bump for `VIRC-ISS-0048` produced 2026.1.12; `bump_virc_version.py --check`, `test_virc_version_policy.py`, and rebuilt `bin/virc --version` passed |
| Bootstrap fixed point | PASS | versioned stage 2 and stage 3 both hashed `c339bbb66f8948cc5aeafefd22050b7f8c09f88e9e09a83e9d9cb2b3df862068`; `cmp` returned success |

### Regression

The full 953-test run covers the migrated archived/positive operator fixtures,
stdlib consumers, native memory contracts, multi-target assembly checks, and
Wasm contracts. There were no failures or blocked tests.

### Conformance

The removed-source inventory was derived from VIR-SPC-0015 and the operator,
control-flow, function, and cast sections of VIR-SPC-0017/VIR-SPC-0018:

- removed: `return`, `while`, `&&`, infix `|`, prefix bitwise `~`, `<<`,
  `<<=`, and `>>=`;
- preserved canonical source: `out`, `when ... loop`, `&`, `||`, `and`, `or`,
  `xor`, `bnot(...)`, `shl`, `shr`, `>>` cast, postfix swizzle `~`, `|=`, and
  other canonical compound assignments;
- retained but not source compatibility: internal AST/IR/backend return,
  while, and shift terminology plus the internal `__not` bootstrap spelling;
- excluded data: comments, string/Virgex payloads, explicit negative fixtures,
  and `stdlib/vir/gpu/kernels.vri` embedded foreign source.

## 8. Acceptance Criteria

- [x] Compared active lexer/parser tables with VIR-SPC-0015, VIR-SPC-0017,
      and VIR-SPC-0018; the complete removed/preserved inventory is recorded
      in this report.
- [x] Migrated active compiler, stdlib, tools, and positive tests before
      removing frontend support.
- [x] Removed `return -> TokType.Out`; the focused fixture rejects at line 5,
      column 5 and points to `out`.
- [x] Removed `TokType.While`, statement dispatch, and compatibility parsing;
      the fixture now rejects in the lexer and points to `when condition loop`.
- [x] Removed acceptance of `&&`, infix `|`, prefix bitwise `~`, `<<`, `<<=`,
      and `>>=` with one focused negative fixture each.
- [x] Preserved and executed `&`, `||`, `and`, `or`, `xor`, `bnot`, `shl`,
      `shr`, postfix swizzle, and canonical compound assignments.
- [x] Preserved `65 >> int` as a cast in the positive operator matrix.
- [x] Verified every retired spelling in classic and JSON modes with stable
      source positions and canonical replacement text.
- [x] Added a repository guard with comment, string, embedded-foreign-source,
      and explicit-negative-fixture exclusions.
- [x] Passed sync, focused, minimum/full, version, and fixed-point gates.
- [x] This accepted report maps all issue criteria to raw commands and results.

## 9. Known Limitations

- The repository source guard intentionally excludes the embedded GPU kernel
  payload and explicit negative fixtures. Compiler tests, rather than the
  source guard, own those negative spellings.
- Diagnostics use the existing generic structured `action` field; the
  canonical replacement is carried in the stable diagnostic message in both
  classic and JSON output.

## 10. Remaining Work

No remaining work is required for VIRC-ISS-0048. Other legacy spellings listed
as out of scope in the issue remain separate language-contract decisions.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0048 — source issue.
- VIRC-PLN-0040 — implementation plan.
- VIR-SPC-0015 — forbidden substitution inventory.
- VIR-SPC-0017 / VIR-SPC-0018 — normative operator and control-flow grammar.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Accepted implementation evidence and READY_FOR_CLOSE conclusion |
