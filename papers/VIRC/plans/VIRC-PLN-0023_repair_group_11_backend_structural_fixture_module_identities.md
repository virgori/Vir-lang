---
id: "VIRC-PLN-0023"
type: "PLAN"
domain: "VIRC"
title: "Repair Group 11 backend structural fixture module identities"
status: "COMPLETED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "tests"
components:
  - "strict-v2"
  - "group-11"
  - "module-registry"
  - "mcinst"
  - "verifier"
related:
  issues:
    - "VIRC-ISS-0039"
  plans: []
  reports:
    - "VIRC-RPT-0040"
supersedes: null
superseded_by: null
tags:
  - "test-debt"
  - "module-identity"
  - "regression-suite"
---

# VIRC-PLN-0023 — Repair Group 11 backend structural fixture module identities

## 1. Objective

Restore Group 11's backend structural oracle by replacing retired module
aliases with the canonical identities in `compiler/module.list`, without
adding resolver compatibility aliases or changing production MC behavior.

## 2. Source Issues

- `VIRC-ISS-0039` — the fixture stops in preprocessing and never exercises
  malformed and unresolved MC symbol verification.

## 3. Scope

### In Scope

- `tests/strict_v2/backend_unresolved_structural_e2e.vri` dependency forms;
- canonical compiler registry identities for MC and runtime helpers;
- focused execution, module-graph resolution, and Group 11 regression gates;
- mutation checks for one rejected malformed symbol and one accepted registered
  symbol.

### Out of Scope

- production module aliases or resolver behavior;
- MC verifier semantics, backend encoders, or expected output changes;
- the independent URL semantic failure tracked by `VIRC-ISS-0037`.

## 4. Current Architecture

`compiler/module.list` registers `mc`, `mc_verify`, `rt_string_rt`, and
`rt_vec_rt`. The fixture uses retired dotted `compiler.mc*` identities and
legacy runtime aliases, and combines `include` with selective `import` for the
same dependency. The first unresolved dotted target raises `E2125`, so no MC
verifier assertion executes.

## 5. Proposed Architecture

The fixture declares direct whole-module dependencies with canonical registry
keys when the module has no export surface, and uses import-only access for the
explicitly exported `mc_verify` functions. Production registry and resolver
behavior remain unchanged.

## 6. Design Decisions

### Decision 1 — Fix the consumer, not the resolver

**Decision:** Replace stale fixture identities and redundant dependency pairs;
do not add aliases to `compiler/module.list` or resolver fallback code.

**Rationale:** The registry is the closed-world identity authority, and the
failure is isolated to a consumer whose declared names do not exist.

**Alternatives considered:** Compatibility aliases were rejected because they
would preserve stale coupling in production. Editing source module declarations
was rejected because their canonical registry keys already resolve.

**Trade-offs:** The fixture becomes coupled to current canonical keys by design;
future registry migrations must update it in the same change.

## 7. Implementation Plan

### Phase 1 — Canonicalize dependencies

- file: `tests/strict_v2/backend_unresolved_structural_e2e.vri`;
- replace retired and compatibility identities with registry keys;
- use one dependency form per module;
- expected result: preprocessing and semantic analysis reach the runtime oracle.

### Phase 2 — Verify behavior and close lifecycle

- run the focused compiled program and compare its checked-in stdout/exit oracle;
- run module graph resolution and Group 11;
- apply positive and negative mutation controls without retaining mutations;
- record evidence in a REPORT and close only if every ISSUE criterion is met.

## 8. Compatibility

- No production source, ABI, parser, serialized format, LSP, or public API
  compatibility change is intended.
- Only the stale test dependency declarations change.

## 9. Migration

No production migration is required. The fixture itself is the migration unit.

## 10. Validation Plan

- resolve `mc` and `mc_verify` from the repository and an alternate CWD;
- compile and execute the focused fixture against its embedded oracle;
- mutate one invalid symbol into an accepted registered symbol and one valid
  symbol into an unregistered symbol, requiring each mutation to fail the oracle;
- run `./run_tests.sh 11`;
- run paper registry, validation, and fixed-point gates applicable to a test-only
  dependency change.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Canonical imports reveal an independent verifier failure | Medium | Medium | Preserve runtime output and diagnose separately instead of weakening the oracle |
| Redundant dependencies mask transitive visibility | Low | Medium | Declare direct `mc` and `mc_verify` dependencies explicitly |
| Concurrent worktree changes overlap the fixture | Low | High | Inspect status and patch only the dependency block |

## 12. Rollback Strategy

Revert only the fixture dependency block and lifecycle papers. No production
binary, registry alias, or source module is modified.

## 13. Exit Criteria

- [x] canonical dependency declarations compile and execute;
- [x] embedded output and exit oracle passes;
- [x] mutation controls detect both false acceptance and false rejection;
- [x] module graph and Group 11 gates pass for this fixture;
- [x] accepted REPORT maps all ISSUE criteria;
- [x] ISSUE moves through VERIFYING and RESOLVED before closure.

## 14. Related Papers

- `VIRC-ISS-0039`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created, approved, and activated for the user-requested 2→1→3 implementation sequence |
| 2026-10-05 | Linked VIRC-RPT-0040 |
| 2026-10-05 | Completed after focused execution, mutation, module-graph, dependency, and Group 11 verification |
