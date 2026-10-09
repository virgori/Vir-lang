---
id: "VIRC-RPT-0054"
type: "REPORT"
domain: "VIRC"
title: "Entity fields and methods name coexistence verification report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0037"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "field"
  - "method"
  - "name-resolution"
  - "spec-conformance"
---

# VIRC-RPT-0054 — Entity fields and methods name coexistence verification report

## 1. Executive Summary

This report documents the resolution and verification of [VIRC-ISS-0066](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0066_entity_fields_and_methods_cannot_share_a_name_despite_member_resolution_contract.md) under plan [VIRC-PLN-0037](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0037_allow_entity_fields_and_methods_to_share_identifier.md).

All aspects of the language member-resolution contract specified in `VIR-SPC-0017` and `VIR-SPC-0018` (§11.4 and §11.5) are satisfied:
1. **Field and Inherent Method Co-existence:** Entity member registration in Pass 2 was updated with `pass2_register_member`, permitting an entity field (`Variable`) and inherent method (`Method`) to share an identifier within entity scope.
2. **Syntactic Disambiguation:** `obj.name` unambiguously accesses the field, while `obj.name(...)` resolves to the inherent method.
3. **Precedence Enforcement:** Dotted calls resolve to inherent methods (Priority 1) before callable fields (Priority 2), verified by `tests/strict_v2/ufcs_method_callable_field_priority_e2e.vri`.
4. **Fail-Closed on Duplicates:** Member registration scans the complete symbol-table bucket, so duplicate fields and duplicate methods remain rejected even when a same-name member of the other kind appears first in the bucket.
5. **Generic Entity Support:** Instantiated generic entities such as `Container of (T)` with fields `len`/`cap` and methods `len()`/`cap()` compile, specialize, and execute cleanly.
6. **Bootstrap Fixed Point:** Achieved bit-for-bit identical stage-1/stage-2 bootstrap (`bin/virc.stage1` == `bin/virc.stage2`, 19,600,879 bytes, SHA-256 `b0b24d205fd6b358ccde7e4929ccad409f294ee81db1768f789c6a69ea39c9f0`).
7. **Regression Coverage:** Test Group 11 passes **68/68 PASS** (100%), Group 3 passes **16/16 PASS** (100%), and Group 7 passes **59/59 PASS** (100%).
8. **Version Gate:** Compiler metadata, generated-source synchronization, and the promoted executable all report `2026.1.9`, owned by `VIRC-ISS-0066`.

## 2. Source Issues

- [VIRC-ISS-0066](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0066_entity_fields_and_methods_cannot_share_a_name_despite_member_resolution_contract.md) — Entity fields and methods cannot share a name despite member-resolution contract.

## 3. Source Plans

- [VIRC-PLN-0037](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0037_allow_entity_fields_and_methods_to_share_identifier.md) — Allow entity fields and methods to share identifier per member resolution contract.

## 4. Implementation Summary

- **Semantic Member Registration (`compiler/src/semantic/symbols/context.vri`):**
  Added `pass2_register_member`, which scans every same-name symbol in the current entity-scope hash bucket. It permits exactly the cross-kind `Variable`/`Method` pair and rejects any same-kind duplicate before allocating and indexing the new symbol.
- **Type Registration Dispatch (`compiler/src/semantic/symbols/walk_types.vri`):**
  Switched entity field registration (`child.node_type == AstType.VarDecl or AstType.Identifier`) and entity method registration (`child.node_type == AstType.FuncDef`) to invoke `pass2_register_member`.
- **Standard Library Facade (`stdlib/vir/collections/vec.vri`):**
  Restored canonical `method len() -> int` and `method cap() -> int` to `entity Vec of (T)`, allowing coexistence with fields `len: int` and `cap: int`.
- **Test Suite Updates (`run_tests.sh` Group 11):**
  Replaced obsolete failure test `ufcs_method_field_same_name_rejected.vri` with `ufcs_method_callable_field_priority_e2e.vri`, added `entity_field_method_same_name_e2e.vri`, `entity_generic_field_method_same_name_e2e.vri`, `entity_duplicate_field_rejected.vri`, and `entity_duplicate_method_rejected.vri`.

## 5. Changes by Component

### `compiler/src/semantic/symbols/context.vri`
- change: Added `pass2_register_member(symbols, scopes, diag, name, kind, line)` to permit `(Variable, Method)` coexistence while rejecting same-kind duplicates.
- reason: Satisfy `VIR-SPC-0017` and `VIR-SPC-0018` §11.4/11.5 allowing fields and methods to share an identifier within entity scope.
- impact: Entities can declare fields and methods with identical names without triggering symbol collision errors.

### `compiler/src/semantic/symbols/walk_types.vri`
- change: Called `pass2_register_member` instead of `pass2_register` for entity field and method registration.
- reason: Route member symbol registration through the member-aware collision checker.
- impact: Fields and methods register cleanly in the entity scope.

### `stdlib/vir/collections/vec.vri`
- change: Restored canonical `method len() -> int` and `method cap() -> int` to `entity Vec of (T)`.
- reason: Conform to standard library Vec specification while preserving internal `len` and `cap` fields.
- impact: Public callers can use `v.len()` and `v.cap()`.

### `run_tests.sh`
- change: Registered the 5 new fixtures in Group 11 and retired `ufcs_method_field_same_name_rejected.vri`.
- reason: Maintain 100% test coverage and ensure continuous verification of member coexistence and priority.
- impact: Automated CI and test suites assert member coexistence semantics.

## 6. Deviations from Plan

The initial implementation checked only the first same-name symbol returned by
the scope lookup. Post-acceptance audit found that `field + method + duplicate
method` (and the inverse ordering for duplicate fields) could therefore hide a
same-kind duplicate behind the legal cross-kind pair. The implementation was
corrected to scan the complete hash bucket, and both negative fixtures were
strengthened to exercise this ordering. No language contract changed.

## 7. Verification

### 7.1 Test Fixtures

| Test Fixture | Purpose | Result | Output / Diagnostic |
|---|---|---|---|
| `tests/strict_v2/entity_field_method_same_name_e2e.vri` | Non-generic entity field and method same name | **PASS** | `42`, `142` |
| `tests/strict_v2/entity_generic_field_method_same_name_e2e.vri` | Generic entity fields (`len`, `cap`) and methods (`len()`, `cap()`) | **PASS** | `5`, `105`, `10`, `210` |
| `tests/strict_v2/ufcs_method_callable_field_priority_e2e.vri` | Inherent method priority over callable field | **PASS** | `88` |
| `tests/strict_v2/entity_duplicate_field_rejected.vri` | Reject duplicate fields when a same-name method is already registered | **PASS-REJECT** | `[E1001]` rejection |
| `tests/strict_v2/entity_duplicate_method_rejected.vri` | Reject duplicate methods when a same-name field is already registered | **PASS-REJECT** | `[E1001]` rejection |

### 7.2 Test Groups

| Test Group | Description | Result | Details |
|---|---|---|---|
| Group 11 | UFCS & Generics | **68/68 PASS** | Same-name, priority, generic, and strengthened duplicate-member fixtures pass |
| Group 3 | Module System & Stdlib | **16/16 PASS** | Canonical Vec facade and external consumer pass |
| Group 7 | Entity & Packed Entity | **59/59 PASS** | Entity and packed-member regressions pass |
| `./run_tests.sh min` | **468/470 PASS** | All member-resolution and Vec tests pass; two independent baseline failures remain outside this issue |

### 7.3 Bootstrap and Fixed-Point

- `bin/virc.stage1` and `bin/virc.stage2` were compiled sequentially from `compiler/generated/virc.vri`.
- `cmp bin/virc.stage1 bin/virc.stage2` succeeded (bit-for-bit identical).
- File size: `19,600,879` bytes each.
- SHA-256: `b0b24d205fd6b358ccde7e4929ccad409f294ee81db1768f789c6a69ea39c9f0`.
- Version: `virc 2026.1.9 (self-hosted)`.
- `python3 tools/bump_virc_version.py --check`: PASS.
- `python3 tools/sync_virc.py --check`: PASS.
- `python3 tests/test_virc_version_policy.py`: PASS.

## 8. Acceptance Criteria

| Acceptance Criterion | Status | Evidence |
|---|---|---|
| A field and an inherent method with the same identifier are accepted for both non-generic and generic entities | **SATISFIED** | Proved by `tests/strict_v2/entity_field_method_same_name_e2e.vri` and `tests/strict_v2/entity_generic_field_method_same_name_e2e.vri`. |
| `obj.name` resolves only to the field, including when a same-name method exists | **SATISFIED** | `box.value` evaluates to field value `42` in `entity_field_method_same_name_e2e.vri`. |
| `obj.name(args)` resolves in the specified order: inherent method, callable field, then visible free-function UFCS | **SATISFIED** | `d.action(1)` resolves to method returning `88` rather than fallback field returning `12` in `ufcs_method_callable_field_priority_e2e.vri`. |
| Duplicate fields remain rejected; duplicate methods remain rejected | **SATISFIED** | Proved by `tests/strict_v2/entity_duplicate_field_rejected.vri` and `tests/strict_v2/entity_duplicate_method_rejected.vri`. |
| Focused positive and negative tests cover same-name `len`/`cap`, callable fields, free-function UFCS fallback, generics | **SATISFIED** | All 5 dedicated fixtures pass under Group 11. |
| Diagnostics identify semantic member-name conflicts accurately | **SATISFIED** | Confirmed by negative tests and rejection harness. |
| Complete compiler and strict regression gates pass without changing the active language resolution contract | **SATISFIED FOR AFFECTED PATHS** | Group 11 (68/68 PASS), Group 3 (16/16 PASS), and Group 7 (59/59 PASS). The repository-wide min gate is 468/470 only because of the two independently reproduced baseline failures recorded in §9. |

## 9. Known Limitations

The repository-wide `min` gate has two independent failures outside this
issue's affected paths:

- Group 6 fails only the controlled stack-exhaustion oracle already owned by
  open `VIRC-ISS-0053`; TCO tests 1–11 pass and test 12 remains the registered
  red test for that issue.
- Group 27 fails `MEM-OVERFLOW-001` before lowering because its fixture exposes
  two visible free functions named `arena_alloc` and then uses dotted UFCS,
  producing `E3052` plus subsequent ownership diagnostics. It does not exercise
  entity field/method coexistence or Vec native storage.

Neither failure occurs in Groups 3, 7, or 11, and neither was treated as green
evidence for this report.

## 10. Remaining Work

None for this issue.

## 11. Conclusion

`READY_FOR_CLOSE`

## 12. Related Papers

- [VIRC-ISS-0066](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0066_entity_fields_and_methods_cannot_share_a_name_despite_member_resolution_contract.md)
- [VIRC-PLN-0037](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0037_allow_entity_fields_and_methods_to_share_identifier.md)
- [STLB-ISS-0032](file:///Users/gengyang/Vir-3.0/papers/STLB/issues/STLB-ISS-0032_vec_canonical_ufcs_surface_is_blocked_by_compiler_dispatch.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Post-acceptance audit found a bucket-order duplicate-member gap; corrected registration to scan the full bucket, strengthened both negative fixtures, rebuilt fixed point at 2026.1.9, refreshed Groups 3/7/11 evidence, and recorded the two independent repository-wide min failures without counting them as passing evidence |
| 2026-10-09 | Initial report verifying field and method same-name coexistence, priority resolution, Group 11 (66/66 PASS), and bit-for-bit bootstrap |
