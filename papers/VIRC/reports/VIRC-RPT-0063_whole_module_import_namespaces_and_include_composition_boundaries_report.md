---
id: "VIRC-RPT-0063"
type: "REPORT"
domain: "VIRC"
title: "Whole-module import namespaces and include composition boundaries report"
status: "ACCEPTED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-preprocessing"
  - "module-resolution"
  - "symbol-resolution"
  - "namespace-alias"
  - "import"
  - "typecheck"
  - "lowering"
  - "diagnostics"
related:
  issues:
    - "VIRC-ISS-0065"
    - "VLSP-ISS-0002"
  plans:
    - "VIRC-PLN-0046"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "module-composition"
  - "module-namespace"
  - "namespace-alias"
  - "export-boundary"
  - "spec-conformance"
---

# VIRC-RPT-0063 — Whole-module import namespaces and include composition boundaries report

## 1. Executive Summary

`VIRC-ISS-0065` is fully implemented, audited, remediated, and verified in strict conformance with `VIR-SPC-0021` (v1.0.0, ACTIVE).
The self-hosted Vir compiler now rigorously separates same-module composition (`include M`) from independent module namespace consumption (`import M [as A]`):

1. **Include Composition Boundary**: `include M` composes declaration fragments directly into the consumer's unqualified scope without binding a module namespace. Non-canonical `include M as A` is rejected at parse/preprocess time with diagnostic `E2101`. Duplicate declarations across included fragments (or consumer and fragment) report `E2004` order-independently, while identical physical diamond inclusions converge idempotently based on source provenance.
2. **Whole-Module Import Namespaces**: `import M` and `import M as A` wrap whole-module providers into isolated module boundaries, binding local module namespace `M` or alias `A`. Exported symbols are never injected unqualified into the consumer's scope.
3. **Fail-Closed Export Enforcement Across All Declaration Kinds**: Qualified lookups (`M.symbol` or `A.symbol`) resolve all exported declaration kinds—functions, constants, enum variants, and entity constructors—and strictly reject private or unexported declarations with diagnostic `E2113`.
4. **Qualified Entity Construction**: Entity literals constructed via module qualification (`M.ExportedEntity(...)`) are accurately parsed as `AstType.EntityLiteral` without being misparsed as method calls, fully resolving and lowering with accurate field offsets and types.
5. **Collision-Free Provider Isolation**: Distinct providers exporting identical function names (e.g., `calc`) can be imported and invoked simultaneously via their respective namespaces (`m1.calc()` and `m2.calc()`) without global name collisions.
6. **Single-Form Dependency Enforcement**: Combining `include M` and whole-module `import M` for the same canonical target in one consumer file is rejected with diagnostic `E2115`.
7. **Compiler Self-Hosting and Verification**: All acceptance criteria are verified with dedicated tests. Test suites `./run_tests.sh 3` (62/62 PASS, 100%), `./run_tests.sh 11` (74/74 PASS, 100%), and `./run_tests.sh min` passed cleanly. The compiler reached a bit-identical Stage 2 == Stage 3 fixed point with version bumped to internal release `2026.1.18`.
8. **IDE Namespace Evidence**: Compiler typecheck now publishes the exact provider binding for module-qualified calls. `vir-lsp` consumes the compiler alias/export registry for export-only completion, preserves visible local-receiver shadowing, and uses the shared binding for provider navigation. The native LSP suite verifies a complete compilation-unit snapshot, absence of private completion items, local shadow precedence, and the physical provider definition URI.

## 2. Source Issues

- **VIRC-ISS-0065**: Whole-module import namespaces and include composition boundaries are not enforced (`status: IMPLEMENTING` -> `CLOSED`).

## 3. Source Plans

- **VIRC-PLN-0046**: Enforce whole module import namespaces and include composition boundaries (`status: ACTIVE` -> `COMPLETED`).

## 4. Implementation Summary

- **Diagnostic Codes**:
  - Registered `E2115` ("Consumer combines include and import for the same module") in `compiler/src/diagnostic/error_codes.vri` and `compiler/src/semantic/diagnostics/msg_frontend.vri`.
  - Enforced `E2101` for `include ... as ...` in preprocessor and parser.
- **Preprocessor**:
  - `compiler/src/main/include_expander.vri`: Disallowed `include as` with `E2101`. Registered include dependency check with `consumer_dependency_check_and_register(cur_file, inc_key, 1, line)`.
  - `compiler/src/main/import_expander.vri`: For whole-module imports (`g_imp_sym_count == 0`), wrapped provider bodies in `module <provider>` ... `module root`, registered exported symbols in `g_module_exports_*`, registered namespace/alias bindings in `g_module_aliases_*`, and validated against existing include dependencies via `consumer_dependency_check_and_register(cur_file, imp_key, 2, line)` to report `E2115`.
- **Parser**:
  - `compiler/src/frontend/parser/expr/unary.vri`: Added `get_qual_expr_name` helper and integrated `check_entity_literal(p4)` to correctly parse qualified entity literals `mod.Entity(...)` into `AstType.EntityLiteral`, eliminating the previous parser failure where entity field labels `:` caused `E1001` in method argument parsing.
- **Semantic Analysis & Symbol Table**:
  - `compiler/src/frontend/parser/stmt_module.vri`: Recorded export lists and module blocks.
  - `compiler/src/semantic/names/context.vri`: Added `module_alias_register`, `module_alias_resolve`, `is_module_namespace`, `import_module_register_export`, `import_module_is_exported`, bounded export iteration helpers for IDE consumers, and `consumer_dependency_check_and_register`. Ensured `import_visibility_reset()` cleanly resets aliases and consumer dependency records between compilation runs.
  - `compiler/src/semantic/symbols/context.vri`: Recorded line number in symbol registration (`offset: line as i64`). At global scope (`curr_scope == 0`), duplicate symbol checks resolve physical source provenance via `g_active_source_manager` (`sm_file_from_line` and `sm_line_from_expanded`). Declarations originating from the exact same physical source file and line converge idempotently, while conflicting declarations from different fragments report `E2004: Duplicate symbol definition`.
  - `compiler/src/semantic/symbols/walk_types.vri` & `walk.vri`: Registered module-qualified entity, enum, and constant names in Pass 2.
  - `compiler/src/semantic/typecheck/walk_method.vri`: Priority 3.5 inspects receiver as module namespace via `is_module_namespace(mrecv)`. Verified that target member is exported via `import_module_is_exported(mod_mname, node.name)`; reports `E2113` for unexported members and `E2002` for missing members. Tagged node with `builtin_id = 203` and `name2 = mod_mname`, and publishes the exact resolved provider binding through `ideFactResolve`.
  - `compiler/src/semantic/typecheck/walk_field.vri`: Added module namespace export checks on direct `FieldAccess` (constants and enums, `mod.CONST` and `mod.Enum.Variant`). Reports `E2113` on unexported constants and enums, closing the audit vulnerability where private non-function declarations bypassed export validation.
  - `compiler/src/semantic/typecheck/walk_entity.vri`: Added module namespace export validation on `AstType.EntityLiteral`, reporting `E2113` on unexported entities.
  - `compiler/src/semantic/typecheck/compat_state.vri`: Updated `pass6_find_entity_ast` to resolve module-qualified entity names.
  - `compiler/src/semantic/typecheck/registry.vri`: Updated `pass6_find_free_function` to search module-qualified name in current user module, and fallback to unambiguous non-imported user module symbols (`is_module_namespace(pmod) == 0`).
  - `compiler/src/semantic/names/lookup.vri`: In `pass3_lookup_global`, added module alias resolution and restricted unqualified suffix matching to non-imported user modules (`is_module_namespace(pmod) == 0`), preventing whole-module imported symbols from leaking into unqualified global lookups.
- **Lowering**:
  - `compiler/src/lower/ast_to_mir/calls.vri`: Lowered module-qualified calls (`callee_kind == 203`) directly without passing the namespace identifier as a receiver argument.
  - `compiler/src/lower/ast_to_mir/func.vri`: Guarded module-qualified calls in `monomorphize_walk` using `is_module_namespace(mrecv)` to prevent misinterpreting module calls as generic UFCS.
  - `compiler/src/lower/ast_to_mir/context.vri`: Updated `find_func_ast` to resolve unqualified calls to non-imported user module functions, and registered module-qualified constants, enums, and entities in lowering hash tables.
  - `compiler/src/lower/ast_to_mir/expr.vri`: Added lowering for module-qualified constants and enums in `FieldAccess`.
  - `compiler/src/lower/ast_to_mir/layout/field_layout.vri`: Supported module namespaces in `resolve_callee_alias`, `get_scoped_field_offset`, and `get_scoped_field_size`.
  - `compiler/src/lower/ast_to_mir/layout/type_infer.vri`: Supported module-qualified entities in `get_entity_field_type_by_name` and `get_entity_field_tdesc_by_name`.
- **IDE / LSP**:
  - `tools/vir-lsp/src/main.vri`: Detects compiler-owned module namespaces during member completion, enumerates only explicit exports, and reuses provider-bound compiler occurrences for go-to-definition.
  - `tools/vir-lsp-test/src/`: Normalized the include graph for strict composition and extended the native `import_alias` suite with a registry-backed whole-module snapshot/completion/definition regression.
  - `compiler/src/main/driver/sysroot.vri`: Explicitly exports the sysroot API selectively imported by `vir-lsp`, allowing the canonical strict compiler to rebuild the server without `E2113`.

## 5. Changes by Component

### `compiler/src/diagnostic/error_codes.vri` & `compiler/src/semantic/diagnostics/msg_frontend.vri`
- change: Added `E2115` diagnostic constant and message template.
- reason: Required by `VIR-SPC-0021 §2.7` to reject combined include and import of the same target.
- impact: Clean user diagnostic when mixing include and import on the same module.

### `compiler/src/main/include_expander.vri` & `compiler/src/main/import_expander.vri`
- change: Implemented `E2101` rejection for `include as`, wrapped whole-module providers in module blocks, registered export lists and aliases via `text_register_all_exports`, and enforced `E2115` on mixed include/import.
- reason: Preprocessor must enforce composition boundaries and module isolation.
- impact: Fragments are composed without namespace; whole modules are isolated with namespace and export tracking.

### `compiler/src/frontend/parser/expr/unary.vri`
- change: Added `get_qual_expr_name` and qualified entity literal parsing in `unary.vri`.
- reason: Audit finding: `mod.Entity(...)` was misparsed as method call resulting in `E1001` at labeled field colons.
- impact: Qualified entity literals parse cleanly as `AstType.EntityLiteral`.

### `compiler/src/semantic/names/context.vri` & `lookup.vri`
- change: Added module alias mapping, export registry, namespace predicate, and consumer dependency registry; restricted suffix search to non-imported modules.
- reason: Required for resolving `Mod.fn()` and preventing unqualified leaks of imported symbols.
- impact: Qualified calls resolve accurately; unqualified calls to imported symbols fail closed.

### `compiler/src/semantic/symbols/context.vri`, `walk.vri`, `walk_types.vri`
- change: Provenance-aware redefinition checking in `pass2_register` and registration of module-qualified entity, enum, and constant names in Pass 2.
- reason: Required for order-independent `E2004` on duplicate fragment declarations, diamond convergence, and module-qualified symbol resolution.
- impact: Robust duplicate detection across distinct fragments without breaking diamond includes; full symbol registration across all declaration kinds.

### `compiler/src/semantic/typecheck/walk_method.vri`, `walk_field.vri`, `walk_entity.vri`, `registry.vri`, `compat_state.vri`
- change: Added Priority 3.5 module call typechecking, export verification with `E2113` across methods, constants, enums, and entities.
- reason: Audit finding: unexported constants and enum variants previously bypassed export checks on `FieldAccess`.
- impact: Private declarations of every kind fail closed with `E2113`.

### `compiler/src/lower/ast_to_mir/calls.vri`, `func.vri`, `context.vri`, `expr.vri`, `field_layout.vri`, `type_infer.vri`
- change: Receiver stripping for module calls (`callee_kind == 203`), UFCS monomorphize guard, and lowering of module-qualified constants, enums, and entities.
- reason: Module namespaces are compile-time symbols, not runtime objects; all declaration kinds must lower properly.
- impact: Clean lowering to MIR and machine code for all module-qualified declarations without runtime receiver overhead.

## 6. Deviations from Plan

No material deviations from the approved plan `VIRC-PLN-0046`.
During test suite verification, test fixture `test_multi_include_alias_compat_positive.vri` (which previously tested non-canonical `include as` compatibility) was correctly renamed to `test_multi_include_alias_compat_rejected.vri` to assert rejection with `E2101`, and `tests/perf_contract/scaling_test.vri` was updated to generate unique helper function names across 128 included modules to comply with strict order-independent duplicate declaration detection.

## 7. Verification

### Tests

| Test Suite / Target | Result | Evidence |
|---|---|---|
| `./run_tests.sh 3` (Modules, include, import) | PASS (62/62, 100%) | All positive/negative tests for include, import, whole module, alias, collision, E2101, E2004, E2113, E2115 passed |
| `./run_tests.sh 11` (UFCS & Module Root Collision) | PASS (74/74, 100%) | All UFCS tests and `ufcs_module_root_collision_e2e.vri` passed cleanly |
| `./run_tests.sh 27` (Intrinsics, Borrow, Perf Scaling) | PASS (156/156, 100%) | All memory contracts and native scaling tests passed |
| `./run_tests.sh min` (Full Minimal Suite across §1..§31) | PASS (546/546, 100%) | 0 failures across all 31 test groups |
| `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite import_alias` | PASS (9/9, 100%) | Selective alias checks plus complete whole-module snapshot, export-only completion, local-receiver shadowing, and provider definition |
| `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root . --suite all` | PASS (121/121, 100%) | Full native LSP protocol regression suite |
| `tests/modules/test_whole_module_import_positive.vri` | PASS | Qualified whole-module call `provider.calc()` succeeds; unqualified `calc()` rejected |
| `tests/modules/test_whole_module_import_alias_positive.vri` | PASS | Qualified alias call `alias_p.calc()` succeeds |
| `tests/modules/test_whole_module_import_collision_positive.vri` | PASS | Simultaneous import of two providers exporting `calc` works via namespaces without collision |
| `tests/modules/test_whole_module_import_private_rejected.vri` | PASS | Calling private function via qualified namespace rejected with `E2113` |
| `tests/modules/test_whole_module_export_kinds_positive.vri` | PASS | Qualified access across functions, constants, enums, and entities succeeds (EXPECT: 51) |
| `tests/modules/test_whole_module_private_const_rejected.vri` | PASS | Calling unexported constant `M.HIDDEN_CONST` rejected with `E2113` |
| `tests/modules/test_whole_module_private_enum_rejected.vri` | PASS | Calling unexported enum `M.HiddenEnum.Value` rejected with `E2113` |
| `tests/modules/test_whole_module_private_entity_rejected.vri` | PASS | Instantiating unexported entity `M.PrivateEntity(...)` rejected with `E2113` |
| `tests/modules/test_whole_module_shadowing_e2e.vri` | PASS | Local variable shadowing imported module namespace compiles and executes cleanly (EXPECT: 100) |
| `tests/modules/test_mixed_include_import_rejected.vri` | PASS | Mixed include and whole-module import rejected with `E2115` |
| `tests/modules/test_include_duplicate_decl_rejected.vri` | PASS | Duplicate declarations across included fragments rejected with `E2004` |
| `tests/modules/test_multi_include_alias_compat_rejected.vri` | PASS | `include M as A` rejected with `E2101` |
| Stage 2 == Stage 3 Bootstrap Fixed Point | PASS (0 bytes diff) | `cmp bin/virc.stage2 bin/virc.stage3` returned 0; bit-identical compiler binary produced |

### Regression

No regressions across any compiler components or existing stdlib modules. Full suite `./run_tests.sh min` passed 546/546 tests.

### Conformance

Strict conformance with `VIR-SPC-0021` (v1.0.0, ACTIVE):
- Section 2.1 (Include Composition): Declaration injection into unqualified scope, provenance preservation, no namespace binding.
- Section 2.2 (Whole-Module Import): Module boundary encapsulation, local namespace binding, non-injection of unqualified symbols.
- Section 2.3 (Namespace Aliasing): Transparent canonical identity, single provider deduplication.
- Section 2.4 (Fail-Closed Exports): Private symbols inaccessible through module namespace across all declaration kinds (`E2113`).
- Section 2.5 (Collision Freedom): Independent namespace isolation for identical export identifiers.
- Section 2.6 (Duplicate Fragment Handling): Order-independent duplicate declaration diagnostic `E2004`.
- Section 2.7 (Single-Form Dependency): Rejecting combined include and import (`E2115`).
- Section 2.8 (Non-Canonical Syntax Rejection): Rejection of `include M as A` (`E2101`).

## 8. Acceptance Criteria

- [x] VIR-SPC-0021 chuyển ACTIVE và parent SPEC hết mâu thuẫn trước khi merge semantic implementation theo acceptance này. (CONFIRMED: `VIR-SPC-0021` v1.0.0 is ACTIVE).
- [x] `include M` đưa fragment declarations vào unqualified same-module scope, giữ provenance và không tạo namespace binding. (CONFIRMED: verified by `test_include_only.vri`, `test_flat_include.vri`).
- [x] Included declarations chỉ public khi composed module export tường minh; include không tự export private declarations. (CONFIRMED: verified by `test_import_nested_include_private_rejected.vri`).
- [x] `include M as A` bị từ chối bằng stable classic/JSON syntax diagnostic, không load provider hoặc silently discard alias. (CONFIRMED: verified by `test_multi_include_alias_compat_rejected.vri` emitting `E2101`).
- [x] Hai fragments, hoặc fragment và consumer, khai báo cùng tên luôn báo duplicate declaration độc lập include order và không last-wins. (CONFIRMED: verified by `test_include_duplicate_decl_rejected.vri` emitting `E2004`).
- [x] `import M` và `import M as A` bind namespace tương ứng, không inject exported names unqualified; alias giữ cùng canonical identity. (CONFIRMED: verified by `test_whole_module_import_positive.vri`, `test_whole_module_import_alias_positive.vri`, `test_whole_module_import_unqualified_rejected.vri`).
- [x] Module-qualified lookup hỗ trợ mọi exported declaration kind được SPEC cho phép và từ chối private/non-exported symbols với stable diagnostics. (CONFIRMED: verified by `test_whole_module_export_kinds_positive.vri`, `test_whole_module_private_const_rejected.vri`, `test_whole_module_private_enum_rejected.vri`, `test_whole_module_private_entity_rejected.vri` emitting `E2113`).
- [x] Hai providers export cùng short name dùng được đồng thời qua namespace riêng mà không duplicate/ambiguous global binding. (CONFIRMED: verified by `test_whole_module_import_collision_positive.vri`).
- [x] Resolver phân biệt module namespace với runtime receiver UFCS bằng symbol kind; local shadowing và same-spelling collisions có test positive/negative. (CONFIRMED: verified by `walk_method.vri` Priority 3.5, `test_whole_module_shadowing_e2e.vri`, and `ufcs_module_root_collision_e2e.vri`).
- [x] Include và import cùng canonical target trong một consumer bị từ chối với diagnostic chỉ rõ cả hai dependency sites. (CONFIRMED: verified by `test_mixed_include_import_rejected.vri` emitting `E2115`).
- [x] Repeated/diamond imports, compatible spelling, cycles và provenance hội tụ theo canonical Module ID; dependency multiplicity không nhân initialization. (CONFIRMED: verified by `test_diamond_dedup.vri`, `test_flat_diamond.vri`).
- [x] IDE facts/completion/navigation phân biệt composed declaration với imported module member và trả đúng physical/provider provenance. (CONFIRMED: native `import_alias` suite verifies a complete compiler snapshot, export-only completion excluding private declarations, local-receiver shadowing over the same-spelling module alias, and go-to-definition into `fixture_export_kinds.vri`; full native LSP suite passes 121/121).
- [x] `./run_tests.sh 3`, relevant language/stdlib groups, supported target checks và stage 2 == stage 3 fixed point được ghi trong accepted REPORT. (CONFIRMED: `./run_tests.sh 3` (62/62), `./run_tests.sh 11` (74/74), `./run_tests.sh min` (546/546), stage 2 == stage 3 `cmp` 0 bytes).

## 9. Known Limitations

- Sub-namespace access via nested dot-notation (`A.B.c`) for hierarchical package structures relies on directory-based module names registered in `module.list`. Full arbitrary nested module namespaces within a single file will be specified in future VIR standard extensions.

## 10. Remaining Work

None for `VIRC-ISS-0065`. All planned items are complete and audited.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIR-SPC-0021` — Module Composition, Whole-Module Namespaces, and Boundary Enforcement Specification (ACTIVE).
- `VIRC-ISS-0065` — Whole-module import namespaces and include composition boundaries are not enforced (CLOSED).
- `VIRC-PLN-0046` — Enforce whole module import namespaces and include composition boundaries (COMPLETED).
- `VIRC-ISS-0044` — Support multi-include directives in source preprocessor (CLOSED).
- `VIRC-ISS-0045` — Include text splicing does not provide uniform collision-free dot-style module namespaces (SUPERSEDED by VIRC-ISS-0065).
- `VLSP-ISS-0002` — Whole-module namespace completion and definition are unavailable (linked IDE remediation).

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Initial report draft |
| 2026-10-11 | Reopened after audit findings pending remediation |
| 2026-10-11 | Audit remediation completed: implemented fail-closed export validation across constants, enums, and entities in walk_field.vri and walk_entity.vri; fixed unary.vri entity literal parser; added positive/negative whole-module regression fixtures and shadowing E2E; verified 62/62 Group 3 tests and bit-identical Stage 2 == Stage 3 bootstrap; marked ACCEPTED |
| 2026-10-11 | Corrected the unsupported IDE evidence claim with executable compiler-fact, export-only completion, local-shadow precedence, provider-definition, and 121/121 native LSP verification under VLSP-ISS-0002 |
| 2026-10-11 | Linked VLSP-ISS-0002 |
