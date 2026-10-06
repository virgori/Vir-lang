---
id: "VIR-ISS-0001"
type: "ISSUE"
domain: "VIR"
title: "Generic of syntax migration retains legacy string parsing and lacks closure gates"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
owners: [language, compiler]
components: [generics, parser, type-system, lowering, migration-tooling, tests]
related:
  issues: [VIR-ISS-0002]
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: [generic-syntax, of-syntax, type-identity, bootstrap, regression-gates]
---

# VIR-ISS-0001 — Generic of syntax migration retains legacy string parsing and lacks closure gates

## 1. Summary

The surface migration from generic `<...>` syntax to canonical `of (...)` is
partially implemented and passes its focused tests. Downstream type checking
and lowering still parse serialized generic types with mixed angle/parenthesis
byte scanners, and the complete legacy rejection matrix is not registered in
the normal runner. This issue covers only canonical type identity, removal of
legacy internal parsing, durable negative-test registration, and strict
self-host closure. Working parser and migration-tool behavior is not reopened.

## 2. Context

`docs/_legacy/plan/STRICT_VIR_OF_GENERIC_SYNTAX_MIGRATION_PROMPT.md` described a full
repository migration. The active tree audited on 2026-10-02 already contains
contextual `of (...)` parsing, dedicated legacy diagnostics, migrated active
Vir source, a transactional migration tool, and focused generic fixtures. This
ISSUE intentionally contains only the unfinished remainder.

## 3. Expected Behavior

- Canonical source and compiler-internal generic identity use one unambiguous
  `of (...)` representation or a structured type descriptor.
- Semantic and lowering passes do not retain compatibility parsing for
  `Name<Args>` serialized types.
- Every advertised legacy form is a registered compile-fail test with the
  canonical diagnostic and no artifact.
- Migration audit output classifies retained angle-bracket hits in a reviewable
  report, and a second run is a no-op.
- The strict compiler completes the active fixed-point bootstrap and runs final
  regression gates without promoting a bridge compiler.

## 4. Actual Behavior

- Parser paths accept `of (...)` and emit the required legacy syntax guidance.
- Focused generic behavior passes, and the migration tool proposes no remaining
  rewrite in its configured active roots.
- `type_table.vri`, `sem_pass6_typecheck.vri`, and `ast_to_mir.vri` still scan
  byte values 60/62 (`<`/`>`) alongside 40/41 (`(`/`)`) when extracting or
  serializing generic information.
- Eight `legacy_generic_*_negative.vri` fixtures reject correctly when invoked
  directly, but they are not referenced by `run_tests.sh` or a manifest.
- No current REPORT records bridge-to-final strict bootstrap and final
  fixed-point verification specifically closing this migration.

## 5. Reproduction

```sh
python3 tools/test_migrate_generic_of_syntax.py
python3 tools/migrate_generic_of_syntax.py --dry-run \
  --root stdlib/vir/compiler --root stdlib/vir --root tests
python3 tools/gap_contract_runner.py --filter '^GENERIC-' --verbose
rg -n "== 60|== 62|angle_depth" \
  stdlib/vir/compiler/type_table.vri \
  stdlib/vir/compiler/sem_pass6_typecheck.vri \
  stdlib/vir/compiler/ast_to_mir.vri
rg -n 'legacy_generic_' run_tests.sh tools tests --glob '!*.vri'
```

Direct compilation of each `tests/strict_v2/legacy_generic_*_negative.vri`
currently exits 1, emits canonical guidance, and leaves no artifact. The last
search demonstrates that success is not yet a durable suite gate.

## 6. Evidence

- CONFIRMED: migration-tool tests passed 10/10 on 2026-10-02, including
  transaction rollback and conflict protection.
- CONFIRMED: dry-run scanned 1,993 files, proposed 0 changes, retained 769
  classified angle-bracket hits, and reported 0 manual-review hits.
- CONFIRMED: `GENERIC-001..012` passed 12/12 with active `bin/virc` on macOS
  ARM64.
- CONFIRMED: all eight legacy generic fixtures failed with canonical guidance
  and no artifact when run directly.
- CONFIRMED: parser diagnostics at `parser.vri:1916`, `3273`, `3301`, `3356`,
  `3401`, and `3405` reject recognized legacy syntax.
- CONFIRMED: downstream angle parsing remains in `type_table.vri:398-449`,
  `sem_pass6_typecheck.vri:2292-2779`, and `ast_to_mir.vri:305-555`.
- CONFIRMED: `python3 tools/sync_virc.py --check` reports modular/generated
  compiler sources identical.
- NOT_VERIFIED: final strict self-host convergence and full regression closure
  dedicated to this migration.

## 7. Scope

### Affected

- canonical generic type identity after parsing;
- extraction, substitution, specialization, and mangling helpers;
- registration of the complete legacy rejection matrix;
- migration audit evidence and strict bootstrap closure.

### Not affected / Already complete

- contextual parsing of normal `of (...)` declarations and applications;
- current focused generic runtime/type-check behavior;
- direct diagnostic recognition of the eight audited legacy forms;
- transactional migration capabilities covered by the 10 passing tests;
- frozen release trees and language specification text.

## 8. Impact

Mixed internal syntax keeps multiple parsers for one semantic concept and can
reintroduce identity, nested-generic, substitution, or mangling bugs after the
surface migration appears complete. Unregistered negative fixtures can regress
without failing CI. Current focused tests reduce immediate impact, so this is
S2 rather than a claim of broad compiler failure.

## 9. Preliminary Analysis

- CONFIRMED: the parser migration is functional for the audited matrix.
- CONFIRMED: internal string scanners preserve angle-delimited compatibility.
- OBSERVED: the migration tool is idempotent on current active roots, while 769
  retained hits appear only as an aggregate in normal dry-run output.
- HYPOTHESIS: one structured descriptor or canonical serializer/parser will
  remove mixed-delimiter scans and make identity checks auditable.
- NOT_VERIFIED: persistent classification of every retained hit and final
  strict-bootstrap convergence.

## 10. Acceptance Criteria

- [ ] Semantic/lowering code no longer accepts `<...>` as a type encoding.
- [ ] Nested substitution, arity, specialization isolation, deterministic
  mangling, and distinct same-base identities remain green.
- [ ] All eight `legacy_generic_*` forms are registered and assert non-zero
  exit, canonical diagnostic location/guidance, and no artifact.
- [ ] Comparison, shift, FMA, port-send, foreign include, string, and comment
  controls remain unchanged and registered.
- [ ] Dry-run produces reviewable retained/manual classifications;
  apply/rollback/idempotence tests remain green.
- [ ] Modular/generated compiler sources synchronize without direct bundle
  edits.
- [ ] Strict bootstrap reaches the active fixed point and final tests run with
  the strict compiler, not a bridge.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIR-ISS-0002 — overlapping canonical type-identity debt.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from active source and executed-test audit; limited to unfinished migration closure |
