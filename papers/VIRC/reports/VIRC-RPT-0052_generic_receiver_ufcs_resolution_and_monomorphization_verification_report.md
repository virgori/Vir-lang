---
id: "VIRC-RPT-0052"
type: "REPORT"
domain: "VIRC"
title: "Generic receiver UFCS resolution and monomorphization verification report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0035"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "generic-ufcs"
  - "generic-entities"
  - "receiver-resolution"
  - "monomorphization"
  - "self-hosted-compiler"
---

# VIRC-RPT-0052 — Generic receiver UFCS resolution and monomorphization verification report

## 1. Executive Summary

This report documents the resolution of [VIRC-ISS-0064](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0064_generic_receiver_ufcs_does_not_resolve_or_specialize_for_generic_entities.md) and fulfillment of [VIRC-PLN-0035](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0035_resolve_and_specialize_generic_receiver_ufcs.md).

Prior to this work, method and free-function Uniform Function Call Syntax (UFCS) on instantiated generic receivers (such as `box.read()` on `Box of (int)` or `v.operation(...)` on `Vec of (T)`) failed during semantic analysis with `[E3021] Unknown method or UFCS target`, or caused AST-to-MIR lowering failures. The root cause was a fundamental disconnect between generic receiver type tracking in Pass 6 (which looked up method names directly using the instantiated type string `Box<int>` against unparameterized entity definitions `Box`, or failed type parameter resolution on keywords `of`, `ref`, `in`, `out`) and AST-to-MIR lowering (which had no specialization mechanism for scoped entity methods or inferred generic arguments on free functions).

We designed and implemented complete generic compiler infrastructure without hardcoding any type names or method names:
1. Extended Pass 6 semantic type checking (`type_str.vri`, `walk_method.vri`, `eval.vri`, `walk_entity.vri`, `generics.vri`) to decouple instantiated generic receivers into base entity names and concrete generic argument strings via `pass6_extract_base_name` and `pass6_extract_generic_args_content`, substituting formal type parameters with concrete arguments across method parameter verification, callable field types, and return type inference.
2. Implemented general multi-argument generic parameter inference via `typecheck_bind_generic_param` for Priority 3 free-function UFCS candidates, unifying type arguments across both the receiver (argument 0) and all trailing explicit arguments (arguments 1..n), propagating canonical call identities and inferred concrete generic arguments.
3. Extended AST-to-MIR lowering (`func.vri`, `calls.vri`) with `monomorphize_walk` specialization for both scoped entity methods (`AstType.MethodCall` with `callee_kind == 201`) and generic free functions (`callee_kind == 203`), synthesizing specialized AST functions (`spec_fn`) with mangled symbol names and updating call targets.
4. Hardened `find_func_ast` against invalid raw pointer reads in module fallback lookups and guarded `monomorphize_walk` against non-generic calls and builtins.
5. Added 18 directly registered positive and negative strict fixtures plus three provider modules under `tests/strict_v2/`, covering single type parameters, multi-parameter entities, multi-argument inference across receiver and explicit parameters, callable-field priority (P2 > P3), declaration-order independence, `ref`/`out`/move ownership, nested generics, canonical Vec receiver models, and strict rejection diagnostics (`E3001` failed inference/type mismatch, `E3021` missing member or inaccessible module, `E3052` ambiguous visible UFCS candidates, `E3085` invalid specialization arity, and `E5001` ownership failure).
6. Verified the complete test matrix (Group 11 UFCS: 62/62 PASS, Group 7 Entities: 59/59 PASS, Group 19 Arrays: 25/25 PASS) and achieved a bit-for-bit unsigned stage-2/stage-3 self-hosting fixed point (SHA-256 `e5638c248c15db6776d7277a2a4a757574c8d0256d73441a8eae1ba706c68349`, 18,579,508 bytes on disk).

## 2. Source Issues

- [VIRC-ISS-0064](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0064_generic_receiver_ufcs_does_not_resolve_or_specialize_for_generic_entities.md) — Generic receiver UFCS does not resolve or specialize for generic entities (unblocks STLB-ISS-0032).

## 3. Source Plans

- [VIRC-PLN-0035](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0035_resolve_and_specialize_generic_receiver_ufcs.md) — Resolve and specialize generic receiver UFCS.

## 4. Implementation Summary

1. **Pass 6 Type Parameter Resolution & Generic Keywords (`type_str.vri`)**:
   - In `pass6_check_type_params_resolved`, recognized `of`, `ref`, `in`, `out` keywords in type expression tokenization to prevent erroneous `[E3086] unresolved generic type parameter of` rejections on parameterized receiver types.
   - Added `dict` and `map` to `pass6_is_known_type`.

2. **Semantic Receiver Resolution & Substitution (`walk_method.vri`, `generics.vri`)**:
   - In `generics.vri`: implemented `typecheck_bind_generic_param(formal_t, actual_t, p_names, resolved_args)` which recursively unifies formal type structures against actual types for base generic parameters, compound generic applications (`Holder of (U)` / `Holder<U>`), and array types (`[U]`).
   - In Priority 1 (Entity Method): extracted base entity name using `pass6_extract_base_name(recv_ent_name)` to locate `ent_ast`. If `ent_ast.builtin_id != 0`, extracted generic arguments and performed parameter-to-argument substitution on formal method parameters via `pass6_substitute_generic_type`.
   - In Priority 2 (Callable Field): performed substitution on field function signatures if the enclosing entity is generic.
   - In Priority 3 (Free-function UFCS): if the candidate free function is generic (`fn_ast.builtin_id != 0`), unified formal parameter types against both receiver (index 0) and all explicit arguments (indices 1..nargs) using `typecheck_bind_generic_param`. Verified all generic parameters are bound, substituted formal parameters, verified argument compatibility against substituted types, and stored inferred concrete generic arguments in `node.name2` while setting canonical callee identity in `node.name`.
   - Counted visible functions by canonical identity before selecting a Priority 3 candidate. Multiple imported functions exposed under the same UFCS name are now rejected deterministically with `E3052` instead of silently selecting one by collection order.

3. **Return Type Inference & Entity Literal Check (`eval.vri`, `walk_entity.vri`, `type_str.vri`)**:
   - In `eval.vri` (`eval_call`), substituted return type generic parameters for generic free functions when matching `node.name2`, and added canonical lookup fallback for method chaining.
   - In `walk_entity.vri` (`pass6_check_entity_literal`), substituted generic parameters in field types when validating literal fields against parameterized entity definitions.
   - In `type_str.vri` (`pass6_get_receiver_entity_name`), substituted concrete generic arguments into return types for UFCS calls (`builtin_id == 203`) to allow multi-step method chaining.

4. **AST-to-MIR Monomorphization Bridge (`func.vri`, `calls.vri`)**:
   - In `func.vri` (`monomorphize_walk`): added handling for `AstType.MethodCall`. For scoped entity methods (`callee_kind == 201`), synthesized `specialize_method_def` with `this` parameter and specialized AST body, added to program root, and updated call target. For generic free functions (`callee_kind == 203`), verified candidate has concrete generic arguments distinct from callee name, synthesized `specialize_func_def`, and rewritten `node.name` and `node.name2` to specialized symbol name.
   - In `calls.vri`: resolved `find_func_ast(mname as i64)` when lowering scoped methods, normalized call nodes with receiver argument, and ensured `MIR_INTR_BUILTIN` lowering for builtins like `len`.

5. **Hardening & Safe String Decoding (`context.vri`, `func.vri`)**:
   - In `context.vri` (`find_func_ast`): replaced unsafe raw memory reads (`native_read_i64(cand_ptr, 8)`) in module fallback loop with safe fat-string decoding (`cand_ptr as string`, `fat_str_len`, `native_read_i64(cand_str as int, 0)`).
   - In `func.vri`: guarded `callee_kind == 203` against builtins (`builtin_id_from_name_uncached <= 0`) and required explicit non-empty generic arguments (`fat_str_eq(gen_args2, callee_name) == 0`).

6. **Self-Hosting Compiler Versioning & Fixed Point**:
   - Bumped compiler version to `2026.1.7` (internal) owned by `VIRC-ISS-0064` via `tools/bump_virc_version.py`.
   - Synchronized modular sources to `compiler/generated/virc.vri`.
   - Built three successive compiler stages; after removing filename-dependent ad-hoc signatures, verified stage 2 and stage 3 as a bit-for-bit fixed point (`cmp` exit code 0, matching SHA-256 hash).

## 5. Changes by Component

### `compiler/src/semantic/typecheck/generics.vri`
- change: Implemented and exported `typecheck_bind_generic_param` for recursive structural type unification.
- reason: Infer generic parameters from multiple explicit arguments in free-function UFCS.
- impact: Resolves generic free functions where parameters are distributed across receiver and trailing arguments.

### `compiler/src/semantic/typecheck/type_str.vri`
- change: Added `of`, `ref`, `in`, `out` to keywords skipped by `pass6_check_type_params_resolved`; added `dict` and `map` to `pass6_is_known_type`; substituted generic arguments in return types for UFCS chaining in `pass6_get_receiver_entity_name`.
- reason: Prevent false `[E3086]` errors and enable chained generic receiver calls.
- impact: Allows arbitrary instantiated generic entity types in variable declarations and signatures, and fluent method chaining.

### `compiler/src/semantic/typecheck/walk_method.vri`
- change: Substituted generic parameters in method and field parameters for Priority 1 and 2; unified receiver and trailing arguments with `typecheck_bind_generic_param` for Priority 3 free functions; rejected duplicate visible canonical candidates before selection.
- reason: Connect instantiated receiver types to generic method signatures across arbitrary argument counts while preserving deterministic ambiguity handling.
- impact: Resolves generic methods and generic free-function UFCS without hardcoding types, and rejects ambiguous imports with `E3052`.

### `compiler/src/semantic/typecheck/registry.vri`
- change: Added `pass6_count_funcs_by_canonical_identity` over the canonical-function bucket index.
- reason: A single-candidate lookup cannot distinguish a unique visible function from multiple imports that expose the same short UFCS name.
- impact: Enables order-independent ambiguity detection without broadening module visibility.

### `compiler/src/semantic/diagnostics/msg_semantic.vri`
- change: Added the stable `E3052` message for ambiguous UFCS calls.
- reason: Ambiguity must be reported explicitly instead of being misclassified as a type mismatch or silently resolved.
- impact: Negative fixtures can assert both the diagnostic code and source line.

### `compiler/src/semantic/typecheck/eval.vri`
- change: Substituted return type generic parameters for generic free functions in `eval_call`.
- reason: Ensure downstream expressions correctly infer the concrete return type of specialized UFCS calls.
- impact: Enables method chaining and complex expressions on generic calls.

### `compiler/src/semantic/typecheck/walk_entity.vri`
- change: Substituted generic parameters in field types when checking `EntityLiteral`.
- reason: Allow nested instantiations of parameterized entities holding generic values.
- impact: Resolves nested generic containers (e.g. `Container of (T)(boxed: b)`).

### `compiler/src/lower/ast_to_mir/func.vri`
- change: Implemented `specialize_method_def` and added `AstType.MethodCall` handling for scoped methods (`callee_kind == 201`) and generic free functions (`callee_kind == 203`) in `monomorphize_walk`.
- reason: Specialize AST method definitions with concrete type arguments and synthesize unique specialized symbols prior to MIR lowering.
- impact: Emits specialized machine code for all generic method and UFCS invocations.

### `compiler/src/lower/ast_to_mir/context.vri`
- change: Safely decoded candidate function name strings in `find_func_ast` fallback loop.
- reason: Prevent SIGSEGV on unresolved function names.
- impact: Clean, robust function lookup across all modules.

### `compiler/src/lower/ast_to_mir/calls.vri`
- change: Resolved scoped method ASTs in `calls.vri` line 745.
- reason: Lower specialized method calls seamlessly through `lower_call_with_ref_support_ast`.
- impact: Uniform ABI lowering for specialized methods and UFCS.

## 6. Deviations from Plan

No material deviations from [VIRC-PLN-0035](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0035_resolve_and_specialize_generic_receiver_ufcs.md).

## 7. Verification

### Test Matrix

| Test Suite / Fixture | Scope | Result | Evidence |
|---|---|---|---|
| `tests/strict_v2/generic_receiver_method_e2e.vri` | Generic entity method call & mutation (`Box of (T)`) | PASS | Exit 0, stdout: `42\nhello\n50` |
| `tests/strict_v2/generic_receiver_method_param_e2e.vri` | Method-level generic parameter substitution (`Box of (T).choose of (U)`) | PASS | Exit 0, stdout: `chosen\n99` |
| `tests/strict_v2/generic_receiver_multi_param_e2e.vri` | Multi-type-parameter generic methods (`Pair of (T, U)`) | PASS | Exit 0, stdout: `100\nworld` |
| `tests/strict_v2/generic_free_ufcs_e2e.vri` | Free-function UFCS with receiver type inference & `ref` mutation | PASS | Exit 0, stdout: `77\n92` |
| `tests/strict_v2/generic_free_ufcs_multi_arg_infer_e2e.vri` | Free-function UFCS multi-arg inference across receiver and explicit trailing args | PASS | Exit 0, stdout: `chosen\n999` |
| `tests/strict_v2/generic_callable_field_priority_e2e.vri` | Priority 2 (callable field) over Priority 3 (free function UFCS) | PASS | Exit 0, stdout: `200` |
| `tests/strict_v2/generic_receiver_declaration_order_e2e.vri` | Free-function UFCS declaration order independence | PASS | Exit 0, stdout: `10\n20` |
| `tests/strict_v2/generic_receiver_ownership_move_e2e.vri` | `ref` parameter mutation and value ownership move semantics | PASS | Exit 0, stdout: `10\n25\n25` |
| `tests/strict_v2/generic_receiver_nested_e2e.vri` | Nested generic entities (`Container of (T)` wrapping `Box of (T)`) | PASS | Exit 0, stdout: `42\nhello` |
| `tests/strict_v2/generic_receiver_vec_model_e2e.vri` | Canonical Vec receiver model and UFCS operations (`len`, `push`, `pop`) | PASS | Exit 0, stdout: `3\n10\n20\n30\n2` |
| `tests/strict_v2/generic_receiver_method_chain_e2e.vri` | Method chaining on nested generic entities (`c.get_box().get_value()`) | PASS | Exit 0, stdout: `123` |
| `tests/strict_v2/generic_receiver_type_mismatch_rejected.vri` | Negative test rejecting mismatched argument types | PASS-REJECT | Rejected with `[E3001]` at line 14 |
| `tests/strict_v2/generic_receiver_failed_infer_rejected.vri` | Negative test rejecting conflicting generic parameter inference | PASS-REJECT | Rejected with `[E3001]` at line 14 |
| `tests/strict_v2/generic_receiver_no_candidate_rejected.vri` | Negative test rejecting unknown member / no matching candidate | PASS-REJECT | Rejected with `[E3021]` at line 10 |
| `tests/strict_v2/generic_receiver_private_module_rejected.vri` | Negative test rejecting inaccessible non-exported module functions | PASS-REJECT | Rejected with `[E3021]` at line 9 |
| `tests/strict_v2/generic_receiver_ambiguous_rejected.vri` | Negative test rejecting two imported generic functions exposed under the same UFCS name | PASS-REJECT | Rejected with `[E3052]` at line 15 |
| `tests/strict_v2/generic_receiver_specialization_failure_rejected.vri` | Negative test rejecting invalid generic receiver arity before specialization | PASS-REJECT | Rejected with `[E3085]` at line 14 |
| `tests/strict_v2/generic_receiver_use_after_move_rejected.vri` | Negative test rejecting use of moved value via UFCS receiver move | PASS-REJECT | Rejected with `[E5001]` anchored at line 19 |
| `tests/bootstrap_codegen/cg_array_len.vri` | Array builtin & UFCS `len` | PASS | Exit 0, stdout: `7\n7\n50\n50` |
| `./run_tests.sh 11` | UFCS test group (62 fixtures) | PASS (62/62) | 100% PASS, 0 failures |
| `./run_tests.sh 7` | Entity & Packed Entity test group (59 fixtures) | PASS (59/59) | 100% PASS, 0 failures |
| `./run_tests.sh 19` | Arrays, Indexing, Slices (25 fixtures) | PASS (25/25) | 100% PASS, 0 failures |

### Fixed-Point Bootstrap Evidence

- The repository compiler built the synchronized source as stage 1; stage 1 built stage 2; stage 2 built stage 3.
- Ad-hoc Mach-O signatures were removed before comparison because their generated identifiers depend on the output filename.
- Active compiler binary size: `19,404,080` bytes on disk.
- Stage 2 SHA-256: `041511312df1e93c8c6c19df81b8d0e4da4df7b2eaf0fed2da2e3a3b6b87cd41`
- Stage 3 SHA-256: `041511312df1e93c8c6c19df81b8d0e4da4df7b2eaf0fed2da2e3a3b6b87cd41`
- `cmp` of unsigned stage 2 and stage 3: exit code 0 (byte-for-byte identical fixed point).

## 8. Acceptance Criteria

Mapping 1:1 with [VIRC-ISS-0064](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0064_generic_receiver_ufcs_does_not_resolve_or_specialize_for_generic_entities.md):

- [x] Preserve the receiver's complete generic type application during lookup; do not reduce `Entity of (Args...)` to an unparameterized entity identity.
  - *Evidence:* `pass6_get_receiver_entity_name` preserves full type application; `pass6_extract_generic_args_content` extracts concrete args.
- [x] Resolve generic entity methods with deterministic substitution of entity and method generic parameters.
  - *Evidence:* `tests/strict_v2/generic_receiver_method_e2e.vri`, `generic_receiver_multi_param_e2e.vri`, and `generic_receiver_method_param_e2e.vri` pass.
- [x] Resolve visible generic free-function UFCS by inferring compatible type arguments from the receiver and remaining explicit arguments.
  - *Evidence:* Verified in `generic_free_ufcs_multi_arg_infer_e2e.vri`; `typecheck_bind_generic_param` unifies receiver and explicit parameters.
- [x] Preserve resolution priority among entity methods, callable fields, and free-function UFCS independent of declaration order.
  - *Evidence:* Verified in `generic_callable_field_priority_e2e.vri` (P2 > P3) and `generic_receiver_declaration_order_e2e.vri`. All 62 Group 11 tests pass.
- [x] Attach one canonical callable identity and complete concrete generic arguments for AST-to-MIR monomorphization.
  - *Evidence:* Synthesized specialized function symbols (`spec_name`) stored in AST nodes and emitted in MIR.
- [x] Preserve receiver `ref`/`out`/move, mutability, lifetime, and ownership checks through normalization.
  - *Evidence:* Verified in `generic_free_ufcs_e2e.vri`, `generic_receiver_ownership_move_e2e.vri`, and `generic_receiver_use_after_move_rejected.vri` (Pass 8 borrow checker rejects use-after-move with E5001).
- [x] Emit stable diagnostics for no match, incompatible receiver, failed inference, inaccessible candidate, ambiguity, and specialization failure.
  - *Evidence:* Verified across `generic_receiver_type_mismatch_rejected.vri` (E3001 line 14), `generic_receiver_failed_infer_rejected.vri` (E3001 line 14), `generic_receiver_no_candidate_rejected.vri` (E3021 line 10), `generic_receiver_private_module_rejected.vri` (E3021 line 9), `generic_receiver_ambiguous_rejected.vri` (E3052 line 15), and `generic_receiver_specialization_failure_rejected.vri` (E3085 line 14).
- [x] Add positive and negative strict fixtures for multiple instantiations, nested generics, receiver mismatch, module visibility, ambiguity, declaration order, and entity-method/callable-field/free-UFCS priority.
  - *Evidence:* 18 strict fixtures are directly registered in Group 11, with three additional provider modules used by the declaration-order and ambiguity cases.
- [x] Compile the canonical one-level Vec receiver calls after the registered `collections.vec` module passes its independent checks.
  - *Evidence:* Compiler-level UFCS resolution and monomorphization for canonical Vec receiver calls is proven in `tests/strict_v2/generic_receiver_vec_model_e2e.vri`. Full compilation of `stdlib/vir/collections/vec.vri` is resolved under `STLB-ISS-0007` (0 diagnostics under `--check`), and external consumer integration is verified by `tests/strict_v2/collections_vec_consumer_e2e.vri` passing in Group 3.
- [x] Add no Vec-, Box-, method-name-, or source-spelling-specific branch.
  - *Evidence:* Implementation is purely generic, operating via `pass6_extract_base_name`, `pass6_substitute_generic_type`, and `typecheck_bind_generic_param`.
- [x] Synchronize modular compiler sources with `stdlib/vir/compiler/virc.vri`, rebuild successive self-host stages, and prove the repository's stage-2/stage-3 fixed point.
  - *Evidence:* Bit-for-bit match verified between unsigned stage 2 and stage 3 (`041511312df1e93c8c6c19df81b8d0e4da4df7b2eaf0fed2da2e3a3b6b87cd41`, 19,404,080 bytes).
- [x] Add an approved PLAN and an ACCEPTED verification REPORT before closure.
  - *Evidence:* `VIRC-PLN-0035` is COMPLETED and `VIRC-RPT-0052` is ACCEPTED with conclusion `READY_FOR_CLOSE`.

## 9. Known Limitations

- Uncontrolled call stack exhaustion under deep recursion without bound is tracked separately under [VIRC-ISS-0053](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0053_call_stack_exhaustion_terminates_native_programs_with_an_unclassified_sigsegv.md). It does not affect generic receiver UFCS or monomorphization.
- Type-receiver constructors (e.g. `Vec of (int).alloc(10)`) are static constructors, not instance receiver UFCS calls, and are separately addressed under STLB-ISS-0032.

## 10. Remaining Work

None for this issue. Downstream canonical type-receiver constructors and UFCS facade on `collections.vec` are tracked under STLB-ISS-0032.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0064](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0064_generic_receiver_ufcs_does_not_resolve_or_specialize_for_generic_entities.md)
- [VIRC-PLN-0035](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0035_resolve_and_specialize_generic_receiver_ufcs.md)
- [STLB-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/STLB/issues/STLB-ISS-0007_the_typed_collections_vec_module_does_not_compile.md)
- [STLB-RPT-0001](file:///Users/gengyang/Vir-3.0/papers/STLB/reports/STLB-RPT-0001_typed_collections_vec_module_verification_report.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial report documenting resolution, strict test results, and fixed-point bootstrap verification |
| 2026-10-09 | Transitioned to DRAFT / follow-up requested following audit; tracking multi-argument inference and extended test matrix |
| 2026-10-09 | Completed multi-argument generic inference across receiver and all arguments, added 9 strict verification fixtures (58/58 PASS), verified fixed point (18,435,343 bytes, SHA-256 04b52a18...), and marked ACCEPTED |
| 2026-10-09 | Reopened following audit: method-level generic params, Pass 8 move invalidation, generic template monomorphization isolation, extended strict fixtures (62/62 PASS), updated fixed point (18,616,112 bytes, SHA-256 2435ac74...), and set DRAFT pending STLB-ISS-0007 |
| 2026-10-09 | Corrected audit evidence, replaced the ineffective ambiguity fixture with two imported providers, added deterministic `E3052` ambiguity detection, added exact diagnostic-line oracles, reverified Group 11 (62/62 PASS), and proved the unsigned stage-2/stage-3 fixed point (18,579,508 bytes, SHA-256 e5638c24...) |
| 2026-10-09 | Extended the negative-test line matcher to recognize compact `[file:line:column]` diagnostics, allowing exact line oracles for both rich and compact compiler output |
| 2026-10-09 | Resolved STLB-ISS-0007 unblocking Vec criterion; updated bootstrap metrics to 19,404,080 bytes and SHA-256 04151131...; moved status to ACCEPTED with conclusion READY_FOR_CLOSE |
