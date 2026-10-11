---
id: "VIRC-PLN-0035"
type: "PLAN"
domain: "VIRC"
title: "Resolve and specialize generic receiver UFCS"
status: "COMPLETED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
components:
  - "semantic-analysis"
  - "type-checker"
  - "generics"
  - "ufcs"
  - "method-resolution"
  - "monomorphization"
  - "ast-to-mir"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0064"
    - "STLB-ISS-0032"
  plans: []
  reports:
    - "VIRC-RPT-0052"
supersedes: null
superseded_by: null
tags:
  - "generic-ufcs"
  - "generic-entities"
  - "receiver-resolution"
  - "monomorphization"
  - "self-hosted-compiler"
---

# VIRC-PLN-0035 — Resolve and specialize generic receiver UFCS

## 1. Objective

Implement generic receiver resolution and monomorphization across the self-hosted Vir compiler for instantiated generic entities (e.g. `Box of (T)`, `Vec of (T)`), resolving VIRC-ISS-0064 and unblocking STLB-ISS-0032:
1. Ensure semantic analysis in Pass 6 (`walk_method.vri`, `type_str.vri`, `eval.vri`) preserves instantiated receiver type arguments while looking up methods and fields against the base entity definition via `pass6_extract_base_name`.
2. Perform deterministic substitution of generic parameters with concrete type arguments across method parameter checking, callable fields, and method return type inference.
3. Infer type arguments for generic free-function UFCS candidates (Priority 3) when matching the receiver type against the first parameter of visible generic functions.
4. Bridge method calls to monomorphization in AST-to-MIR lowering: ensure `monomorphize_walk` specializes methods declared within generic entities, propagating specialized symbols into the lowering pipeline.
5. Provide strict regression tests covering single/multiple type arguments, method chaining, declaration order, and error diagnostics, without any type-specific or hardcoded name workarounds.
6. Verify self-hosting fixed point (`bin/virc.stage1` == `bin/virc.stage2`), update versioning, and document evidence in an accepted verification report.

## 2. Source Issues

- `VIRC-ISS-0064` — Generic receiver UFCS does not resolve or specialize for generic entities.
- `STLB-ISS-0032` — Vec canonical UFCS surface is blocked by compiler dispatch.

## 3. Scope

### In Scope

- Semantic analysis (Pass 6):
  - Base entity lookup using `pass6_extract_base_name` in `walk_method.vri`, `eval.vri`, `type_str.vri`.
  - Preservation of generic arguments from `EntityLiteral` initializers in `pass6_get_receiver_entity_name`.
  - Generic parameter substitution for method parameters and return types using `pass6_substitute_generic_type`.
  - Free-function generic inference for UFCS Priority 3.
  - Callable field type substitution for UFCS Priority 2.
- AST-to-MIR lowering & monomorphization:
  - Registration and specialization of scoped entity methods in `monomorphize_walk` and `calls.vri`.
  - Synthesis of specialized method names (`Entity.method__spec__...`).
  - Propagation of specialized symbols into method call lowering (`calls.vri`).
- Comprehensive regression testing under `tests/strict_v2/` and `tests/vri/`.
- Self-hosted compiler sync and fixed-point bootstrap verification.

### Out of Scope

- Type-receiver constructor lowering (e.g., `Vec of (T).with_capacity(...)` tracked in STLB-ISS-0032 / separate issue).
- Trailing default arguments (VIRC-ISS-0062).
- Contextual typed operation selectors (VIRC-ISS-0063).
- Vector implementation internals (memory growth, indexing logic).

## 4. Current Architecture

1. **Entity Registration**:
   Entities are defined as `AstType.EntityDef` and registered in the symbol table and `g_pass6_entity_buckets` under their base names (e.g., `"Box"`), with generic parameters stored in `builtin_id` (e.g., `"T"`).
2. **Receiver Entity Name Disconnect**:
   When an entity is instantiated (`var box: Box of (int)` or `var box = Box of (int)(...)`), its receiver type is represented as `"Box<int>"` or `"Box of (int)"`.
   `walk_method.vri` line 61 previously called `pass6_find_entity_ast(symbols, scopes, recv_ent_name)` directly with the parameterized string `"Box<int>"`. This lookup failed, causing Pass 6 to miss the entity method and fall through to report `E3021`.
   Similarly, `eval.vri` line 294 called `pass6_find_entity_ast` with `m_recv_ent` without stripping type parameters, failing return type inference.
3. **Monomorphization Scope**:
   In `compiler/src/lower/ast_to_mir/func.vri`, `monomorphize_walk` only inspects `AstType.Call`. Method calls (`AstType.MethodCall`) are not specialized prior to MIR lowering, and scoped methods registered as `"Entity.method"` in `g_scoped_method_names` did not receive generic parameter metadata from their parent `EntityDef`.

## 5. Proposed Architecture

1. **Instantiation-Aware Semantic Resolution**:
   - In `walk_method.vri`: extract the base entity name via `pass6_extract_base_name(recv_ent_name)` to locate `ent_ast`.
   - If `ent_ast.builtin_id != 0`, extract generic arguments using `typecheck_extract_generic_args_content(recv_ent_name)`.
   - Substitute generic parameters in method parameter types using `typecheck_substitute_generic_type(gen_params, gen_args, param_type)`.
   - In `eval.vri`: extract base entity name and perform generic substitution on method return types.
   - In `type_str.vri`: preserve type arguments on `EntityLiteral` initializers when resolving receiver entity names.
2. **Generic Free-Function UFCS (Priority 3)**:
   - When a free function is generic (`callee_node.builtin_id != 0`), match the receiver's concrete type against the function's first parameter type to infer concrete type arguments.
3. **Monomorphization of Scoped Entity Methods**:
   - In `ast_to_mir/context.vri`: when registering entity methods into `g_scoped_method_names`, propagate the parent `EntityDef` generic parameters (`child.builtin_id`) to the method `FuncDef` if the method does not declare its own.
   - In `ast_to_mir/func.vri`: extend `monomorphize_walk` to recognize `AstType.MethodCall`, resolving the scoped method name (`Entity.method`) and specializing it with concrete type arguments.
   - In `ast_to_mir/calls.vri`: ensure `get_scoped_method_name` and method call normalization resolve to the specialized method name.

## 6. Design Decisions

### Decision 1: Generic Compiler Infrastructure without Type Special Cases
- **Decision:** All generic receiver handling operates strictly via type string manipulation and parameter substitution functions (`extract_base_name`, `extract_generic_args_content`, `substitute_generic_type`). No branches checking `"Vec"` or `"Box"`.
- **Rationale:** Ensures all user and standard library generic entities behave uniformly according to VIR-SPC-0018.

### Decision 2: Preservation of Canonical Resolution Precedence
- **Decision:** Priority 1 (Entity Method) -> Priority 2 (Callable Field) -> Priority 3 (Free Function UFCS) -> Priority 3.5 (Module-qualified call).
- **Rationale:** Mandated by VIR-SPC-0018 §14 and VIRC-ISS-0064 Acceptance Criteria.

## 7. Implementation Plan

### Phase 1 — Semantic Receiver Resolution & Substitution
- files:
  - `compiler/src/semantic/typecheck/walk_method.vri`
  - `compiler/src/semantic/typecheck/type_str.vri`
  - `compiler/src/semantic/typecheck/eval.vri`
- changes:
  - Use `pass6_extract_base_name` on receiver entity names.
  - Extract generic arguments and perform substitution on parameter and return types.
  - Preserve generic arguments from `EntityLiteral` in `pass6_get_receiver_entity_name`.

### Phase 2 — AST-to-MIR Monomorphization Bridge
- files:
  - `compiler/src/lower/ast_to_mir/context.vri`
  - `compiler/src/lower/ast_to_mir/func.vri`
  - `compiler/src/lower/ast_to_mir/calls.vri`
  - `compiler/src/lower/ast_to_mir/layout/enum_names.vri`
- changes:
  - Inherit entity `builtin_id` onto scoped method `FuncDef` nodes.
  - Teach `monomorphize_walk` to inspect `AstType.MethodCall` and specialize scoped methods.
  - Ensure `calls.vri` lowers specialized method calls with receiver argument 0.

### Phase 3 — Validation & Regression Suite
- files:
  - `tests/strict_v2/generic_receiver_ufcs_e2e.vri`
  - `tests/strict_v2/generic_receiver_multi_arg_e2e.vri`
  - `tests/strict_v2/generic_free_ufcs_e2e.vri`
  - `tests/strict_v2/generic_receiver_type_mismatch_rejected.vri`
- changes:
  - Add comprehensive positive and negative test fixtures.
  - Run Group 7, Group 11, and exhaustive test suite.

### Phase 4 — Compiler Self-Hosting & Fixed Point
- files:
  - `compiler/version.json`
  - `stdlib/vir/compiler/virc.vri`
- changes:
  - Synchronize via `python3 tools/sync_virc.py`.
  - Bump compiler version via `python3 tools/bump_virc_version.py`.
  - Verify bit-for-bit stage1 == stage2 match.
  - Author `VIRC-RPT-0052`.

## 8. Compatibility

- Full backward compatibility with non-generic entity methods and existing UFCS calls.
- Preserves all error codes (`E3001`, `E3021`, `E3022`, `E3084`, `E3085`).

## 9. Migration

No user migration required; existing valid code continues to compile unchanged.

## 10. Validation Plan

- `./bin/virc <probe.vri> -o <out>` execution test.
- Strict test suite (`tests/strict_v2/`).
- Full test suite via `./run_tests.sh min` and `./run_tests.sh 11`.
- Self-host fixed-point check (`cmp bin/virc.stage1 bin/virc.stage2`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Name collision between specialized scoped methods | Low | Medium | Use canonical hash and mangled suffix `__spec__<hash>_N<len>_<type>` |
| Performance overhead during monomorphization | Low | Low | Hash-based deduplication in `g_func_ast_hash` |
| Regressions in non-generic UFCS | Low | High | Run full Group 11 suite before and after |

## 12. Rollback Strategy

Git revert of changes across the 5 affected compiler files, restoring previous commit.

## 13. Exit Criteria

- [x] Implementation completed across semantic and lowering subsystems;
- [x] Group 7, Group 11, and Group 19 test suites pass (Group 11: 62/62 PASS);
- [x] Acceptance criteria of VIRC-ISS-0064 fully satisfied;
- [x] Compiler fixed-point bootstrap verified;
- [x] Report VIRC-RPT-0052 accepted and VIRC-ISS-0064 marked RESOLVED/CLOSED.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0064_generic_receiver_ufcs_does_not_resolve_or_specialize_for_generic_entities.md`
- `papers/STLB/issues/STLB-ISS-0032_vec_canonical_ufcs_surface_is_blocked_by_compiler_dispatch.md`
- `papers/VIRC/reports/VIRC-RPT-0052_generic_receiver_ufcs_resolution_and_monomorphization_verification_report.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial plan for resolving generic receiver UFCS and monomorphization |
| 2026-10-09 | Linked VIRC-RPT-0052 |
| 2026-10-09 | Completed initial implementation and fixed point |
| 2026-10-09 | Reactivated for full multi-argument generic inference and acceptance test matrix |
| 2026-10-09 | Completed multi-argument generic inference implementation, full strict test suite, and fixed-point verification |
| 2026-10-09 | Reactivated following audit: method generic parameter specialization, pass 8 move invalidation, generic template monomorphization isolation, and Group 11 suite (62 fixtures) |
| 2026-10-09 | Completed plan after STLB-ISS-0007 closure unblocking all exit criteria; VIRC-RPT-0052 accepted |
