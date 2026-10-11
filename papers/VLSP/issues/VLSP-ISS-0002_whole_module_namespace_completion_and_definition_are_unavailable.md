---
id: "VLSP-ISS-0002"
type: "ISSUE"
domain: "VLSP"
title: "Whole-module namespace completion and definition are unavailable"
status: "CLOSED"
severity: "S2"
priority: "P1"
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
    - "VIRC-ISS-0065"
  plans:
    - "VLSP-PLN-0001"
  reports:
    - "VIRC-RPT-0063"
    - "VLSP-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "whole-module-import"
  - "namespace"
  - "export-boundary"
---

# VLSP-ISS-0002 — Whole-module namespace completion and definition are unavailable

## 1. Summary

`vir-lsp` does not offer exported members after `moduleAlias.` and cannot
navigate a qualified whole-module call to its declaration, even when the
compiler accepts the call and retains provider source provenance.

## 2. Context

The closure audit for `VIRC-ISS-0065` found that its report claimed IDE
completion/navigation conformance without an executable LSP assertion. The
native `import_alias` suite was extended to exercise a real whole-module import
against the module registry and exposed both missing behaviors.

## 3. Expected Behavior

- Completion after a whole-module namespace MUST contain only the provider's
  explicit exports.
- Go-to-definition on an exported qualified call MUST return the physical
  provider URI and declaration range.
- The compiler semantic snapshot for the compilation unit MUST remain complete.

## 4. Actual Behavior

- Entity member completion handles runtime receiver types only; module
  namespaces return an empty item list.
- The module-qualified call has no resolver binding fact, so definition returns
  `null` despite the provider declaration existing in compiler facts.

## 5. Reproduction

```sh
./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite import_alias
```

Before remediation, the new whole-module assertions failed while the existing
selective-import hover, definition and rename assertions passed.

## 6. Evidence

- OBSERVED 2026-10-11: completion returned an empty item list for `fe.`.
- OBSERVED 2026-10-11: definition returned `null` for
  `fe.exported_kind_func()`.
- CONFIRMED: the compiler snapshot contained provider declarations and the
  physical `fixture_export_kinds.vri` URI, but no call occurrence bound to the
  exported function.

## 7. Scope

### Affected

- compiler IDE fact capture for module-qualified calls;
- native LSP module-member completion and definition;
- native `vir-lsp-test` regression coverage;
- independent `vir-lsp` patch release.

### Not affected / Unknown

- Vir grammar and language semantics;
- entity-member completion order;
- rename of module-qualified members;
- workspace-wide indexing beyond the analyzed compilation unit.

## 8. Impact

Users cannot discover a module's public surface through completion and cannot
navigate qualified calls, leaving the namespace contract incomplete in editors
even though compilation succeeds.

## 9. Preliminary Analysis

- CONFIRMED: the compiler export registry records the exact public member set
  and excludes private declarations.
- CONFIRMED: `pass6_check_method_call` resolves the provider function but did
  not publish that resolver ID through `ideFactResolve`.
- CONFIRMED: `lspAppendCompilerMembers` handled only named entity receivers.
- NOT_VERIFIED: third-party LSP clients beyond the native protocol harness.

## 10. Acceptance Criteria

- [x] Whole-module completion returns exported names and excludes private names.
- [x] A visible local receiver with the same name as a module alias retains
  normal entity-member completion.
- [x] Go-to-definition on a qualified exported call returns the provider URI
  and declaration range.
- [x] The whole-module compilation-unit semantic snapshot is complete.
- [x] Existing selective-import alias hover/definition/rename tests remain green.
- [x] `vir-lsp` receives one policy-compliant patch bump and rebuilt binary.

## 11. Related Papers

### Issues

- `VIRC-ISS-0065` — compiler/module conformance owner that exposed this gap.

### Plans

- `VLSP-PLN-0001` — implementation and verification plan.

### Reports

- `VLSP-RPT-0001` — implementation report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Opened from executable closure audit of VIRC-ISS-0065 and advanced to IMPLEMENTING after source-level cause confirmation |
| 2026-10-11 | Linked VLSP-PLN-0001 |
| 2026-10-11 | Linked VLSP-RPT-0001 |
| 2026-10-11 | Closed through accepted VLSP-RPT-0001 after export-only completion, local-shadow precedence, provider navigation, semantic snapshot, full protocol suite, and patch-release verification |
| 2026-10-11 | Linked VIRC-ISS-0065 |
| 2026-10-11 | Linked VIRC-RPT-0063 |
