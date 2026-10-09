---
id: "VIRC-PLN-0037"
type: "PLAN"
domain: "VIRC"
title: "Allow entity fields and methods to share identifier per member resolution contract"
status: "COMPLETED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "semantic"
  - "symbols"
  - "member-resolution"
  - "entities"
related:
  issues:
    - "VIRC-ISS-0066"
  plans: []
  reports:
    - "VIRC-RPT-0054"
supersedes: null
superseded_by: null
tags:
  - "field"
  - "method"
  - "name-resolution"
  - "spec-conformance"
---

# VIRC-PLN-0037 — Allow entity fields and methods to share identifier per member resolution contract

## 1. Objective

Resolve `VIRC-ISS-0066` by permitting entity fields (`Variable`) and inherent methods (`Method`) to share an identifier within entity scope, conforming to `VIR-SPC-0017` and `VIR-SPC-0018` sections 11.4 and 11.5. This ensures `x.foo` resolves to the field, `x.foo(args)` resolves to the method before any callable field or UFCS candidate, and duplicate fields or duplicate methods remain rejected.

## 2. Source Issues

- `VIRC-ISS-0066`: Entity fields and methods cannot share a name despite member-resolution contract (S2/P0).

## 3. Scope

### In Scope

- Compiler Semantic Pass 2 (`compiler/src/semantic/symbols/context.vri`): Introduce `pass2_register_member` which permits co-existing `Variable` and `Method` symbols in the same entity scope while enforcing duplicate field and duplicate method rejection.
- Compiler Semantic Pass 2 (`compiler/src/semantic/symbols/walk_types.vri`): Use `pass2_register_member` when registering entity fields and methods.
- Compiler Bootstrap: Rebuild self-hosting compiler through stage 1 and stage 2, verifying fixed-point identity.
- Test Coverage: Add positive fixtures verifying field/method co-existence for both non-generic and generic entities, update legacy rejection test into positive priority test, and add negative tests verifying duplicate fields and duplicate methods remain rejected.
- Test Registry: Register all new fixtures in `run_tests.sh` Group 11.

### Out of Scope

- Modifying parser grammar (parser already preserves fields and methods as distinct AST nodes).
- General function overloading.

## 4. Current Architecture

Currently, `pass2_register` in `compiler/src/semantic/symbols/context.vri` performs a collision check within the current scope via `pass2_lookup_name_in_scope`. When a method has the same identifier as a field (or vice versa), `pass2_register` treats it as a duplicate definition and emits a redefinition error (`E1001`/`E2004`). In `walk_types.vri`, both entity fields (`AstType.VarDecl`/`AstType.Identifier`) and methods (`AstType.FuncDef`) are registered via `pass2_register` in the same `ScopeKind.Entity` scope.

## 5. Proposed Architecture

1. In Pass 2 symbol registration:
   - Introduce `pass2_register_member(symbols, scopes, diag, name, kind, line)` in `context.vri`.
   - If an existing symbol with the same identifier is found in the entity scope:
     - If the existing symbol is a field (`Variable`) and the new symbol is a method (`Method`) or vice versa, allocate a new `SymbolNode`, add it to the scope, and index it.
     - If both symbols are `Variable` (duplicate fields) or both are `Method` (duplicate methods), delegate to `pass2_register` to report redefinition.
2. In Pass 6 typechecking:
   - Field accesses `x.foo` query `pass6_find_entity_field` which inspects only field definitions.
   - Dotted calls `x.foo(...)` query `pass6_check_method_call` which checks entity methods first (Priority 1), then callable fields (Priority 2), then free-function UFCS (Priority 3).

## 6. Design Decisions

### Decision 1: Single Scope with Disambiguated Member Kinds
- **Decision:** Maintain a single lexical entity scope but permit distinct `Variable` and `Method` symbols with the same identifier.
- **Rationale:** Minimizes structural changes to the symbol table while matching the language specification (§11.5) that parentheses distinguish field access from method invocation.

### Decision 2: Fail-Closed on Same-Kind Duplicates
- **Decision:** Duplicate fields and duplicate methods remain strictly rejected with diagnostic errors.
- **Rationale:** Preserves semantic integrity against accidental field or method redeclarations.

## 7. Implementation Plan

### Phase 1 — Semantic Symbol Registration
- files: `compiler/src/semantic/symbols/context.vri`, `compiler/src/semantic/symbols/walk_types.vri`
- changes: Implement `pass2_register_member` and use it in `walk_types.vri` for entity fields and methods.

### Phase 2 — Compiler Synchronization and Bootstrap Rebuild
- files: `compiler/generated/virc.vri`, `bin/virc.stage1`, `bin/virc.stage2`, `bin/virc`
- changes: Run `python3 tools/sync_virc.py`, build stage 1 and stage 2, verify bit-for-bit identity, and promote compiler.

### Phase 3 — Test Fixtures and Verification
- files: `tests/strict_v2/`, `run_tests.sh`
- changes: Add positive fixtures for non-generic and generic same-name members, convert `ufcs_method_field_same_name_rejected.vri` to positive priority test, add duplicate field/method negative tests, run Group 11 suite.

## 8. Compatibility

- Completely backwards compatible with all existing valid code.
- Conforms to active specifications `VIR-SPC-0017` and `VIR-SPC-0018` §11.4 and §11.5.

## 9. Migration

No migration required for existing programs. Programs previously rejected by this compiler defect will now compile cleanly.

## 10. Validation Plan

- `./bin/virc scratch/probe_same_name.vri -o scratch/probe_same_name && ./scratch/probe_same_name`
- `./bin/virc scratch/probe_generic_same_name.vri -o scratch/probe_generic_same_name && ./scratch/probe_generic_same_name`
- `./run_tests.sh 11`
- `./paper registry --check && ./paper validate`

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unintended symbol shadowing in entity scope | Low | Medium | Strict kind checking: only (Variable, Method) pairs are accepted |
| Monomorphization collision | Low | Low | Methods and fields have distinct AST node types and code paths |

## 12. Rollback Strategy

Revert changes in `compiler/src/semantic/symbols/context.vri` and `compiler/src/semantic/symbols/walk_types.vri` and re-synchronize generated compiler.

## 13. Exit Criteria

- [x] Same-name field and method accepted on non-generic entities.
- [x] Same-name field and method accepted on generic entities.
- [x] Duplicate fields remain rejected.
- [x] Duplicate methods remain rejected.
- [x] Group 11 test suite passes 100%.
- [x] Bootstrap fixed point verified.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0066_entity_fields_and_methods_cannot_share_a_name_despite_member_resolution_contract.md`
- `papers/STLB/issues/STLB-ISS-0032_vec_canonical_ufcs_surface_is_blocked_by_compiler_dispatch.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Created initial plan for VIRC-ISS-0066 |
| 2026-10-09 | Linked VIRC-RPT-0054 |
| 2026-10-09 | Completed and verified in VIRC-RPT-0054 |
