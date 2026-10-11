---
id: "VLSP-RPT-0001"
type: "REPORT"
domain: "VLSP"
title: "Whole-module namespace IDE resolution report"
status: "ACCEPTED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "lsp"
  - "compiler-ide"
components:
  - "completion"
  - "definition"
  - "compiler-facts"
related:
  issues:
    - "VLSP-ISS-0002"
  plans:
    - "VLSP-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "whole-module-import"
  - "namespace"
  - "export-boundary"
---

# VLSP-RPT-0001 — Whole-module namespace IDE resolution report

## 1. Executive Summary

Whole-module namespace completion and provider navigation are implemented and
verified. The compiler now publishes the exact resolved provider binding for a
qualified call. `vir-lsp` reads the compiler-owned alias/export registry, so
completion returns explicit exports only and definition reuses the binding to
return the physical provider location. `vir-lsp` was released as `1.3.1`.

## 2. Source Issues

- VLSP-ISS-0002

## 3. Source Plans

- VLSP-PLN-0001

## 4. Implementation Summary

- Added bounded export-registry iteration helpers to the compiler semantic
  context.
- Attached the provider function symbol ID to module-qualified call IDE facts.
- Added compiler-authoritative module namespace completion in `vir-lsp`.
- Added registry-backed native LSP checks for snapshot completeness,
  export-only completion, local receiver shadowing, and provider navigation.
- Removed duplicate includes/extern declarations from the native test harness
  so it conforms to strict include composition.
- Exported the four `driver_sysroot` entry points consumed by `vir-lsp`, so a
  canonical rebuild also passes the compiler's fail-closed selective-import
  boundary.

## 5. Changes by Component

### `compiler/src/semantic/names/context.vri`

- change: exposed bounded read-only accessors for registered module exports;
- reason: let IDE consumers reuse the same fail-closed visibility authority;
- impact: completion cannot infer or leak unexported provider declarations.

### `compiler/src/semantic/typecheck/walk_method.vri`

- change: module-qualified calls publish the resolved declaration symbol ID;
- reason: the provider was known to typecheck but absent from IDE occurrences;
- impact: go-to-definition returns the provider URI/range and semantic snapshots
  become complete.

### `tools/vir-lsp/src/main.vri`

- change: module namespace receivers enumerate compiler export entries before
  the existing entity-member path;
- reason: entity AST traversal cannot represent a module namespace;
- impact: `alias.` completion exposes the public surface only.

### `tools/vir-lsp-test/src/`

- change: normalized the textual include graph and added whole-module checks to
  the native `import_alias` suite using the real repository module registry;
- reason: the earlier VIRC report relied only on source inspection;
- impact: closure now has executable protocol evidence.

### `compiler/src/main/driver/sysroot.vri`

- change: explicitly exported the sysroot resolver, registry validator, parent
  path helper, and active stdlib registry consumed by `vir-lsp`;
- reason: the canonical strict compiler correctly rejected the previous
  unexported selective import with `E2113`;
- impact: `vir-lsp` rebuilds from source under the same export rules it serves.

## 6. Deviations from Plan

No material deviations from the approved plan. During fixture development, a
temporary `/tmp` module was replaced with a repository registry-backed overlay
because module resolution correctly refuses unregistered project module IDs.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Native focused LSP suite | PASS (9/9) | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite import_alias` |
| Native full LSP suite | PASS (121/121) | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite all` |
| Compiler module group | PASS (62/62) | `./run_tests.sh 3` |
| Compiler UFCS group | PASS (74/74) | `./run_tests.sh 11` |
| Full minimal compiler suite | PASS (546/546) | `./run_tests.sh min` |
| Compiler fixed point | PASS | `cmp -s bin/virc.stage2 bin/virc.stage3`; both SHA-256 `ccad645538f4c7e045bd8ef057626507eab4a58011ab614ecef1d4a8ac68543c` |
| LSP version policy | PASS | `python3 tools/bump_vir_lsp_version.py --check`; public version `1.3.1` |

### Regression

No regression occurred across the compiler module/UFCS suites, the 31-group
minimal suite, or 121 native LSP protocol checks.

### Conformance

The change preserves `VIR-SPC-0021` visibility: completion uses the same module
alias and explicit export registries as compiler typecheck. No protocol schema
or language syntax changed, so the LSP release is a compatible patch.

## 8. Acceptance Criteria

- [x] Whole-module completion returns `exported_kind_func` and excludes
  `hidden_kind_func`.
- [x] Local entity receiver `fe` shadows the same-spelling module alias for
  completion and does not receive module-export candidates.
- [x] Go-to-definition returns `fixture_export_kinds.vri` and its declaration
  range.
- [x] The whole-module semantic snapshot reports `complete:true`.
- [x] Existing selective alias hover, definition and rename checks remain green.
- [x] `vir-lsp` was bumped once under `VLSP-ISS-0002`, rebuilt, and reports
  version `1.3.1`.

## 9. Known Limitations

- Completion is scoped to the current analyzed compilation unit; it is not a
  workspace-wide index.
- Module-member rename remains outside this issue.

## 10. Remaining Work

None for `VLSP-ISS-0002`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VLSP-ISS-0002`
- `VLSP-PLN-0001`
- `VIRC-ISS-0065`
- `VIRC-RPT-0063`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Accepted after compiler fixed-point, 9/9 focused LSP, 121/121 full LSP, 62/62 module, 74/74 UFCS, and 546/546 minimal-suite verification |
