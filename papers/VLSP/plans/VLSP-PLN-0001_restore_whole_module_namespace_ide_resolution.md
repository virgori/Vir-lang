---
id: "VLSP-PLN-0001"
type: "PLAN"
domain: "VLSP"
title: "Restore whole-module namespace IDE resolution"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VLSP-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "whole-module-import"
  - "namespace"
---

# VLSP-PLN-0001 — Restore whole-module namespace IDE resolution

## 1. Objective

Restore export-limited completion and provider navigation for whole-module
namespace calls while preserving existing compiler namespace semantics.

## 2. Source Issues

- VLSP-ISS-0002

The issue has a reproduced native protocol failure and a confirmed split
between compiler fact publication and LSP member consumption.

## 3. Scope

### In Scope

- expose bounded read-only iteration over the compiler module export registry;
- attach the resolved provider function symbol to module-qualified call facts;
- consume namespace/export facts in native completion;
- add native protocol regression coverage and rebuild `vir-lsp`.

### Out of Scope

- grammar or language-specification changes;
- workspace indexing;
- module-member rename support;
- changes to entity/UFCS resolution.

## 4. Current Architecture

`ideSessionAnalyze` already expands the provider with physical source markers,
registers module aliases/exports, and produces provider declaration facts.
`pass6_check_method_call` resolves module-qualified functions but omitted the
IDE resolver binding. `lspAppendCompilerMembers` only traverses an entity AST,
so a module namespace is not a completion receiver.

## 5. Proposed Architecture

The compiler remains authoritative. Typecheck publishes the resolved function
ID for the qualified call. The LSP detects a namespace through the compiler
alias table and enumerates only entries from the compiler export registry.
Existing occurrence/definition machinery then returns the provider location.

## 6. Design Decisions

### Decision 1 — Reuse compiler authority

**Decision:** Read module alias/export state produced by active compiler
analysis instead of reparsing `export` lines in the LSP.

**Rationale:** This preserves fail-closed visibility and avoids divergent
language logic in editor code.

**Alternatives considered:** scanning provider text in `vir-lsp`; rejected
because it duplicates grammar and visibility rules.

**Trade-offs:** completion remains compilation-unit scoped and does not claim
to be a workspace index.

## 7. Implementation Plan

### Phase 1 — Compiler fact bridge

- files/modules: `names/context.vri`, `typecheck/walk_method.vri`;
- changes: expose export iteration helpers and bind qualified call facts;
- dependencies: existing alias/export registry;
- expected result: complete provider-backed occurrence graph.

### Phase 2 — LSP behavior and regression

- files/modules: `tools/vir-lsp/src/main.vri`, `tools/vir-lsp-test/src/`;
- changes: export-only namespace completion, registry-backed native test, and
  strict include graph cleanup in the test harness;
- dependencies: Phase 1;
- expected result: completion and definition pass end to end.

### Phase 3 — Release and closure

- bump `vir-lsp` patch version under `VLSP-ISS-0002`;
- rebuild shipped server and native test runner;
- run focused and relevant full suites, then accept the report.

## 8. Compatibility

- Source, parser, ABI, stdlib and language behavior are unchanged.
- The LSP protocol shape is unchanged; completion and definition gain
  previously missing successful results.
- The server change is a compatible patch release.

## 9. Migration

No migration required.

## 10. Validation Plan

- native `import_alias` LSP suite;
- compiler module and UFCS groups;
- minimal compiler suite;
- compiler sync/version/fixed-point checks;
- `vir-lsp` version-policy and binary identity checks;
- VPS registry and paper validation.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Completion leaks private symbols | Low | High | Enumerate only compiler export registry entries |
| Definition binds same-spelling provider | Low | High | Publish the exact resolver symbol ID from typecheck |
| Harness fixture cannot resolve modules | Medium | Medium | Use repository module registry and open-document overlay |

## 12. Rollback Strategy

Revert the completion branch and IDE fact attachment together, rebuild the
previous server, and reopen `VLSP-ISS-0002`; no source migration is required.

## 13. Exit Criteria

- [x] implementation completed;
- [x] test suite passes;
- [x] acceptance criteria satisfied;
- [x] report generated;
- [x] linked issue closed through accepted report.

## 14. Related Papers

- `VLSP-ISS-0002`
- `VLSP-RPT-0001`
- `VIRC-ISS-0065`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Approved and activated the compiler-authoritative namespace IDE resolution plan |
| 2026-10-11 | Linked VLSP-RPT-0001 |
| 2026-10-11 | Completed after native LSP, compiler regression, fixed-point, and version-policy gates passed |
