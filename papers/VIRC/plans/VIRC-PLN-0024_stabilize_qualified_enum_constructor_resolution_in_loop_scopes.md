---
id: "VIRC-PLN-0024"
type: "PLAN"
domain: "VIRC"
title: "Stabilize qualified enum constructor resolution in loop scopes"
status: "COMPLETED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "semantic"
  - "name-resolution"
  - "enum"
  - "ufcs"
  - "stdlib-result"
  - "stdlib-url"
  - "strict-v2"
related:
  issues:
    - "VIRC-ISS-0037"
  plans: []
  reports:
    - "VIRC-RPT-0041"
supersedes: null
superseded_by: null
tags:
  - "enum-constructor"
  - "soft-abi"
  - "loop-scope"
  - "ufcs"
  - "regression"
---

# VIRC-PLN-0024 — Stabilize qualified enum constructor resolution in loop scopes

## 1. Objective

Ensure qualified `Enum.Variant(...)` expressions are classified as enum
constructors inside `for` scopes, including case-arm returns, without weakening
genuine unresolved method/UFCS diagnostics.

## 2. Source Issues

- `VIRC-ISS-0037` — valid `Result.Err(e)` inside `try_all` falls through to
  unresolved UFCS and blocks Result/URL consumers.

## 3. Scope

### In Scope

- pass-3 traversal of both range-form and iterable-form `for` bodies;
- loop-carried traversal state across recursive name-resolution calls;
- focused nested `for` + `case` + `out` enum-constructor regression;
- Result, URL, UFCS-negative, Group 11, source/bundle, and bootstrap evidence.

### Out of Scope

- changes to enum syntax or `E3021` meaning;
- source-span behavior already closed under `VIRC-ISS-0038`;
- URL parser runtime behavior unrelated to successful compilation;
- general compiler ABI redesign beyond this scalar identity boundary.

## 4. Current Architecture

The parser represents `Enum.Variant(args...)` as `MethodCall`. Pass 3 resolves
the receiver enum and rewrites the node to `EnumConstruct` before UFCS. Direct
and `when`-nested constructors pass, while a minimal constructor inside `for`
falls through to `E3021`. Instrumentation showed that the `ForRange` walker
visited its bounds but skipped its body: the straight-line `child_count` local
was caller-clobbered by recursive walks in native self-host output. The same AST
and enum rewrite are correct once the body is actually traversed.

## 5. Proposed Architecture

The `ForRange` walker treats every child except the last as a bound/iterable
expression and the last child as the loop body. `child_count` and the bound
index are declared loop-carried so recursive pass-3 calls preserve them under
the bootstrap compiler's soft ABI. The existing enum-first/UFCS-second rewrite
path remains unchanged.

## 6. Design Decisions

### Decision 1 — Stabilize the traversal boundary

**Decision:** Replace the fixed straight-line `ForRange` child checks with a
loop-carried walk over all non-body children, then walk the final body child in
the loop scope.

**Rationale:** It supports both `[start, end, body]` and `[iterable, body]`
shapes and prevents recursive calls from invalidating the child count used to
decide whether the body exists.

**Alternatives considered:** Special-casing `Result`, changing the enum rewrite,
or suppressing `E3021` were rejected because the resolver already works when it
reaches the expression. Parser changes were rejected because the parsed loop
shape is correct.

**Trade-offs:** The traversal now relies on the invariant that the body is the
last child, matching both parser forms and the lowering implementation.

## 7. Implementation Plan

### Phase 1 — Stabilize pass-3 loop traversal

- file: `compiler/src/semantic/names/walk.vri`;
- carry `child_count` and the bounds index through a loop;
- enter loop scope before walking the final body child;
- preserve the current enum rewrite and genuine UFCS fallback behavior.

### Phase 2 — Register exact regression

- add an executable fixture with `Enum.Variant` under `for` + `case` + `out`;
- register it in Group 11 min and full modes;
- retain unresolved UFCS negative coverage.

### Phase 3 — Synchronize and bootstrap

- synchronize `compiler/generated/virc.vri` from canonical modules;
- build successive compiler stages until bit-identical fixed point;
- run Result, URL, Group 11, dependency, sync, and paper gates.

## 8. Compatibility

- Valid source becomes accepted as required by existing enum syntax.
- No public ABI, parser grammar, serialized format, LSP protocol, or stdlib API
  changes are intended.
- The change is internal to pass-3 traversal and does not alter AST layout.

## 9. Migration

No source migration is required.

## 10. Validation Plan

- minimal direct, `when`, and `for` enum-constructor checks;
- `stdlib/vir/core/result.vri` and all registered URL consumers;
- focused runtime regression for loop/case/out;
- genuine `E3021` negative fixtures;
- Group 11, dependency discipline, generated-source sync, and self-host fixed point.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Iterable-form `for` body is skipped | Low | High | Cover both parser child layouts through last-child body traversal |
| Rewrite accepts genuine UFCS calls | Low | High | Keep existing E3021 negative fixtures green |
| Bootstrap stage diverges | Medium | High | Require consecutive bit-identical stages before closure |
| Concurrent include renames overlap pass-3 files | Medium | Medium | Preserve existing `rt_*` edits and inspect the targeted diff |

## 12. Rollback Strategy

Revert the `ForRange` traversal and registered fixture. Do not suppress
diagnostics or modify stdlib Result as a workaround.

## 13. Exit Criteria

- [x] pass 3 walks qualified enum constructors in loop bodies;
- [x] Result and URL consumers compile and execute;
- [x] genuine unresolved UFCS remains rejected with `E3021`;
- [x] Group 11, sync, and fixed-point gates pass;
- [x] accepted REPORT maps every ISSUE criterion before closure.

## 14. Related Papers

- `VIRC-ISS-0037`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created, approved, and activated after isolating the failure to qualified enum construction in `for` scopes |
| 2026-10-05 | Corrected root cause after tracing pass-3 visitation: recursive bound walks clobbered the straight-line child count and skipped the loop body |
| 2026-10-05 | Completed after 44/44 Group 11, source/bundle sync, dependency discipline, and byte-identical stage-2/stage-3 evidence |
| 2026-10-05 | Linked VIRC-RPT-0041 |
