---
id: "VIRC-RPT-0062"
type: "REPORT"
domain: "VIRC"
title: "Entity method terminator and selective import boundary verification report"
status: "ACCEPTED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "language"
components:
  - "parser"
  - "entity"
  - "selective-import"
  - "source-preprocessing"
related:
  issues:
    - "VIR-ISS-0018"
    - "VIRC-ISS-0068"
  plans:
    - "VIRC-PLN-0045"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "method"
  - "terminator"
  - "import"
  - "bootstrap"
---

# VIRC-RPT-0062 — Entity method terminator and selective import boundary verification report

## 1. Executive Summary

`VIR-ISS-0018` and `VIRC-ISS-0068` are resolved. An entity member method is
now a nested block closed by `end`; only its owning entity closes with `end.`.
Module-scope `method` is rejected in favor of a free `func` with an explicit
receiver for UFCS. Selective import now retains complete exported ordinary,
generic, and packed entities containing methods, while ignoring `end.` decoys
inside strings and comments. The change is shipped in self-hosted compiler
`2026.1.17` and reached an exact unsigned bootstrap fixed point.

## 2. Source Issues

- VIR-ISS-0018
- VIRC-ISS-0068

## 3. Source Plans

- VIRC-PLN-0045

## 4. Implementation Summary

- Revised active English, Vietnamese, architecture, function, and AI syntax
  specifications to make method termination follow entity ownership.
- Added parser member mode plus focused `E3091` and `E3092` migration
  diagnostics for module-scope `method` and dotted entity-method terminators.
- Migrated checked-in entity and packed-entity method bodies from `end.` to
  `end` without changing their enclosing entity terminators.
- Replaced selective import's raw first-`end.` byte scan with a lexical-state
  aware declaration-end scan that skips strings, line comments, canonical
  block comments, and legacy block comments.
- Added registered-module, direct-path, include-control, generic, packed,
  export-negative, and parser-negative native fixtures.
- Synchronized generated compiler source and bumped the internal compiler
  version once to `2026.1.17`.

## 5. Changes by Component

### Language specification

- `VIR-SPC-0001`, `VIR-SPC-0002`, `VIR-SPC-0003`, `VIR-SPC-0013`,
  `VIR-SPC-0015`, `VIR-SPC-0017`, and `VIR-SPC-0018` now distinguish nested
  entity methods from top-level declarations.
- `method` is valid only as an entity member; standalone extension behavior is
  expressed by free-function UFCS.

### Frontend parser and diagnostics

- `parse_func_def_mode()` receives member context and rejects the legacy dot
  after a member's `end` while recovering deterministically.
- Entity parsing invokes member mode; top-level dispatch reports `E3091`.
- Diagnostic catalogs and actions provide stable JSON and text messages for
  `E3091` and `E3092`.

### Selective import

- `text_find_decl_end()` finds the first syntactic outer `end.` outside string
  and comment lexical states.
- Declaration selection recognizes ordinary, generic, and `packed entity`
  forms and preserves existing export checks.

### Tests and repository sources

- Added `tests/modules/import_entity_methods/` and two strict parser-negative
  fixtures; registered them in Group 3.
- Migrated active compiler, stdlib, and test method declarations to canonical
  nested `end` syntax.

## 6. Deviations from Plan

No material deviations from the approved plan. The final verification added
Groups 7 and 14 beyond the minimum plan because they directly exercise packed
entity methods and `ref`/`out` method parameters.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Module system, including all new fixtures | PASS | `./run_tests.sh 3`: 50/50 |
| Entity and packed entity | PASS | `./run_tests.sh 7`: 59/59 |
| Targets and source maps | PASS | `./run_tests.sh 11`: 68/68 |
| `in`/`ref`/`out`, including method cases | PASS | `./run_tests.sh 14`: 46/46 |
| Compiler source self-check | PASS | zero diagnostics, exit 0 |
| Compiler version policy | PASS | `2026.1.17`, internal |
| Generated bundle sync | PASS | modular source and `compiler/generated/virc.vri` identical |
| VPS registry validation | PASS | production papers validate after lifecycle closure |

### Regression

Registered Module ID import executes `42`, `50`, and `7` for ordinary and
generic entities. Direct-path packed-entity import executes `20`; include
control executes `42`. Unexported entity import remains rejected with `E2113`.
The two legacy syntax forms are rejected with focused `E3091` and `E3092`
machine diagnostics.

### Conformance

Self-hosting stage 3 and stage 4 unsigned binaries are byte-identical with
SHA-256 `d21acd5d95bb04c6de2b3498b561b2451472b28ddfc5c66e58a27712fbc86894`.
The promoted, ad-hoc-signed `bin/virc` reports `2026.1.17` and has SHA-256
`804fc53461949d2b68150f92da9240bf60202b6e179541f79f6afa4759629119`.

## 8. Acceptance Criteria

### `VIR-ISS-0018`

- [x] Active specifications define member `end` and owning entity `end.`.
- [x] Specifications reject module-scope `method` and retain free-function UFCS.
- [x] Canonical methods parse; dotted member terminators report `E3092`.
- [x] Module-scope methods report `E3091`.
- [x] Active stdlib and tests are migrated without behavioral regressions.
- [x] Registered and direct-path selective imports retain complete entities.
- [x] Self-check, native suites, generated sync, and bootstrap fixed point pass.

### `VIRC-ISS-0068`

- [x] Native fixtures construct and call selectively imported exported entities.
- [x] Multiple methods and nested statement blocks preserve the outer boundary.
- [x] Strings and comments containing `end.` do not terminate extraction.
- [x] Generic and packed entities are covered.
- [x] Missing/private export enforcement remains fail-closed.
- [x] Registered, direct-path, include-control, and JSON diagnostic gates pass.
- [x] Group 3, self-check, source sync, and fixed-point bootstrap pass.
- [x] No privacy, opacity, inheritance, or class-semantics decision was added.

## 9. Known Limitations

This is an intentional source migration. Legacy entity methods ending in
`end.` must remove the dot and receive `E3092` until migrated. Entity privacy
and class-like semantics remain explicitly undecided and outside this work.

## 10. Remaining Work

No in-scope work remains. Any future entity visibility or class-semantics
decision requires a separate VIR issue and specification change.

## 11. Conclusion

READY_FOR_CLOSE

The syntax, compiler, repository sources, regression coverage, generated
bundle, and self-hosted binary agree on the corrected ownership and
selective-import boundary contract.

## 12. Related Papers

- `VIR-ISS-0018` — entity method terminator and standalone-method contract.
- `VIRC-ISS-0068` — selective-import entity truncation defect.
- `VIRC-PLN-0045` — implementation and verification plan.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Accepted implementation, regression, source-sync, and fixed-point evidence |
