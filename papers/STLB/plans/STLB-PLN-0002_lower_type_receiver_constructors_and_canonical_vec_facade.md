---
id: "STLB-PLN-0002"
type: "PLAN"
domain: "STLB"
title: "Lower type receiver constructors and canonical Vec facade"
status: "COMPLETED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
  - "compiler"
components:
  - "collections"
  - "vec"
  - "generics"
  - "ufcs"
  - "parser"
  - "codegen"
related:
  issues:
    - "STLB-ISS-0032"
  plans: []
  reports:
    - "STLB-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "ufcs"
  - "constructors"
  - "codegen"
---

# STLB-PLN-0002 — Lower type receiver constructors and canonical Vec facade

## 1. Objective

Resolve `STLB-ISS-0032` by implementing compiler type-receiver constructor lowering (`Item.new(...)`, `Vec.alloc of (T)(cap)`, `Vec.new of (T)()`, `Vec.create of (T)(val, count)`), parsing dotted generic arguments (`recv.method of (TypeArgs)(args)`), monomorphizing type-receiver generic methods, and exposing the canonical Vec facade in `stdlib/vir/collections/vec.vri` with both constructors and UFCS receiver operations, while retaining complete backwards compatibility with `vec_*` symbols.

## 2. Source Issues

- `STLB-ISS-0032`: Vec constructors and generic receiver UFCS are blocked by compiler dispatch (S1/P0).

## 3. Scope

### In Scope

- Compiler Parser (`compiler/src/frontend/parser/expr/unary.vri`): Parse dotted generic method calls `recv.method of (TypeArgs)(args)` into `AstType.MethodCall` with generic argument metadata in `node.name2`.
- Compiler Parser (`compiler/src/frontend/parser/stmt_decl/aggregate_def.vri`): Skip leading blank lines before `method` declarations in entity bodies.
- Semantic Typecheck (`compiler/src/semantic/typecheck/walk_method.vri`): Identify type-receiver method calls, bind generic parameters to generic entities from explicit `node.name2` or inferred arguments, and reject calling instance methods requiring `this` on bare type receivers.
- AST-to-MIR Lowering (`compiler/src/lower/ast_to_mir/calls.vri`): Detect type-receiver calls (`recv` is an entity identifier without a runtime variable binding), prevent prepending `recv` into runtime call arguments, and suppress synthetic `this_param` in `sig_ast`.
- AST-to-MIR Lowering (`compiler/src/lower/ast_to_mir/func.vri`): Detect type-receiver methods (constructors/static methods lacking `this` declaration and `this` access), suppress synthetic `this` parameter generation in both `ast_lower_func` and `specialize_method_def`.
- Standard Library (`stdlib/vir/collections/vec.vri`): Expose canonical `Vec.new`, `Vec.alloc`, and `Vec.create` constructors on `entity Vec of (T)`, and expose the canonical 1-level receiver operations (`len`, `cap`, `isEmpty`, `get`, `try`, `set`, `first`, `last`, `push`, `pop`, `insert`, `remove`, `swapRemove`, `extend`, `contains`, `find`, `count`, `reverse`, `swap`, `clone`, `copy`, `equal`, `reserve`, `compact`, `truncate`, `clear`, `free`), while preserving all existing `vec_*` functions.
- Test Coverage: Add positive and negative fixtures for type-receiver constructors (non-generic and generic) and canonical Vec facade in `tests/strict_v2/`.

### Out of Scope

- Three-level dotted paths (`collections.vec.Vec.alloc`), tracked separately under `STLB-ISS-0033`.
- Removing `vec_*` compatibility symbols during this migration window.

## 4. Current Architecture

1. **Parser Limitation**: In `unary.vri`, following `TokType.Dot` and `field_tok`, the parser only checks `check(p4, TokType.LParen)`. For generic constructor invocations like `Vec.alloc of (int)(32)`, `peek(p4)` is `of`, causing the parser to treat `Vec.alloc` as a `FieldAccess` and leaving `of (int)(32)` unparsed.
2. **Lowering Defect**: In `calls.vri`, method calls unconditionally prepend `recv` as argument 0 of `call_expr`. For type-receiver calls like `Item.new(42)`, `Item` is an entity name rather than a value, triggering `virc: error: lowering unresolved identifier: Item`.
3. **Synthetic Parameter Inversion**: In `func.vri`, `ast_lower_func` and `specialize_method_def` assume every method without an explicit `this` parameter is an instance method and synthesize `this` at parameter index 0. This creates a signature mismatch when type-receiver constructors do not and cannot receive a runtime instance.
4. **Stdlib Vec Facade Gap**: `stdlib/vir/collections/vec.vri` only exposes `vec_*` free functions, preventing users from writing canonical `Vec.alloc of (int)(32)` or `v.push(1)` syntax.

## 5. Proposed Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │ Parser: unary.vri                            │
                       │ Detects `field_tok of (T)(args)`             │
                       │ Emits AstType.MethodCall (name2 = "T")       │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │ Pass 6 Typecheck: walk_method.vri            │
                       │ Identifies type receiver (is_type_receiver)  │
                       │ Binds entity generic args (Vec<int>)         │
                       │ Rejects instance methods on type receivers   │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │ Monomorphization: func.vri                   │
                       │ Specializes Vec.alloc for T=int              │
                       │ Does NOT synthesize `this` parameter         │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │ Lowering: calls.vri & func.vri               │
                       │ calls.vri: omits `recv` from call args       │
                       │ func.vri: omits synthetic `this` in func def │
                       └──────────────────────────────────────────────┘
```

## 6. Design Decisions

### Decision 1: Distinguish Type Receivers from Instance Receivers via Entity Name and Variable Scope

**Decision:** A receiver is classified as a type receiver when:
1. `recv.node_type == AstType.Identifier`;
2. `is_entity_name(recv.name) == 1` (or in Pass 6, `pass6_find_entity_ast(..., recv.name) != 0`);
3. The identifier does not shadow a local variable or parameter in the current scope (`get_var_vreg(b, recv.name) < 0`).

**Rationale:** Vir maintains separate namespaces for types (entities) and values (variables). An entity identifier without a local variable binding represents the type itself, allowing unambiguous dispatch to constructors and static methods.

### Decision 2: Pure Type-Receiver Methods Suppress Synthetic `this`

**Decision:** Methods declared on an entity that have no explicit `this` parameter (`has_this == 0`) and contain no accesses to `this` in their body (`ast_has_this_access == 0`) are identified as type-receiver/static methods (`is_type_receiver_method == 1`). For such methods, neither `ast_lower_func` nor `specialize_method_def` will synthesize `this` at parameter index 0.

**Rationale:** Constructors build instances from scratch and do not receive a pre-existing `this`. Synthesizing `this` for constructors causes parameter count and type mismatches.

### Decision 3: Expose Both Type-Receiver Constructors and Receiver UFCS on Vec

**Decision:**
- Place `method new() -> Vec of (T)`, `method alloc(cap: int) -> Vec of (T)`, and `method create(val: T, count: int) -> Vec of (T)` directly inside `entity Vec of (T)`.
- Expose the approved one-level operations as both entity methods and UFCS functions in `stdlib/vir/collections/vec.vri`.
- Retain all existing `vec_*` functions as compatibility wrappers.

**Rationale:** Fulfills `STLB-ISS-0032` acceptance criteria while ensuring existing code and compiler internal uses of `vec_*` remain fully functional without regression.

## 7. Implementation Plan

### Phase 1 — Parser Dotted Generics & Entity Whitespace

- files/modules: `compiler/src/frontend/parser/expr/unary.vri`, `compiler/src/frontend/parser/stmt_decl/aggregate_def.vri`
- changes:
  - In `unary.vri`, invoke `try_parse_generic_call_args(p4)` after `field_tok` on `TokType.Dot`. If generic arguments match, construct `AstType.MethodCall` with `mc.name2 = mgen_args`.
  - In `aggregate_def.vri`, skip newlines at the head of the entity member parsing loop.
- dependencies: none
- expected result: `Item.new(42)` and `Vec.alloc of (int)(32)` parse to valid `MethodCall` ASTs.

### Phase 2 — Semantic Typecheck for Type Receivers

- files/modules: `compiler/src/semantic/typecheck/walk_method.vri`
- changes:
  - In `pass6_check_method_call`, detect type receivers (`is_type_receiver`).
  - For generic entities with type receivers, bind explicit generic arguments from `node.name2` into `recv_ent_name` (`Vec<int>`).
  - Validate that instance methods with `has_this == 1` are not invoked on bare type receivers.
- dependencies: Phase 1
- expected result: Type-receiver method calls pass Pass 6 with fully resolved types.

### Phase 3 — Lowering & Monomorphization of Type Receivers

- files/modules: `compiler/src/lower/ast_to_mir/calls.vri`, `compiler/src/lower/ast_to_mir/func.vri`
- changes:
  - In `calls.vri`: When `is_type_recv` is true, do not prepend `recv` into `call_expr`, and do not synthesize `this_param` in `sig_ast`.
  - In `func.vri`: Add helper `ast_has_this_access(node)` and `is_type_receiver_method(ent_name, method_ast)`. When `is_type_receiver_method` is true, omit synthetic `this` parameter in `ast_lower_func` and `specialize_method_def`.
- dependencies: Phase 2
- expected result: Native executable compilation of `Item.new(42)` and `Vec.alloc of (int)(32)` succeeds and executes correctly.

### Phase 4 — Bootstrap Compiler Rebuild & Synchronization

- files/modules: `compiler/generated/`, `bin/virc*`
- changes:
  - Synchronize canonical sources to generated artifacts.
  - Rebuild 3-stage bootstrap compiler and verify fixed-point identity (`cmp bin/virc.stage1 bin/virc.stage2`).
- dependencies: Phase 3
- expected result: Fully synchronized bootstrap compiler.

### Phase 5 — Canonical Vec Facade in `collections.vec` & Test Fixtures

- files/modules: `stdlib/vir/collections/vec.vri`, `tests/strict_v2/`
- changes:
  - Expose constructors `Vec.new`, `Vec.alloc`, `Vec.create` on `entity Vec of (T)`.
  - Expose UFCS receiver operations on `Vec of (T)`.
  - Create positive and negative test fixtures for type-receiver constructors and Vec UFCS.
  - Register new tests in `run_tests.sh`.
- dependencies: Phase 4
- expected result: All tests pass cleanly.

## 8. Compatibility

- source compatibility: Retains 100% of existing `vec_*` functions.
- ABI: No changes to runtime or calling conventions.
- parser compatibility: Adds support for `recv.method of (T)(args)` conforming to `VIR-SPC-0018`.
- stdlib behavior: Consumers can use both canonical `Vec.alloc of (int)(32)` / `v.push(1)` and compatibility `vec_*` functions.

## 9. Migration

`vec_*` compatibility symbols remain in place for the full deprecation cycle documented in `stdlib/registry/vec.md`.

## 10. Validation Plan

- `./bin/virc scratch/probe_type_receiver.vri -o scratch/probe_type_receiver && ./scratch/probe_type_receiver`
- Focused test fixtures in `tests/strict_v2/` covering:
  - Non-generic type receiver: `Item.new(...)`;
  - Generic type receiver: `Vec.alloc of (int)(...)`, `Vec.new of (int)()`, `Vec.create of (int)(...)`;
  - Canonical Vec UFCS: `v.push(...)`, `v.len()`, `v.get(...)`, `v.free()`;
  - Negative test: calling instance method on type receiver rejected with appropriate error.
- Full test suites: `./run_tests.sh 3`, `./run_tests.sh 11`.
- `./paper registry --check && ./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ambiguity between type receiver and shadowed variable | Low | High | Explicitly check `get_var_vreg < 0` to prioritize variables if an identifier shadows an entity name |
| Regressions in existing instance method calls | Low | High | Only bypass `this` synthesis when `is_type_receiver_method` is true and `has_this_access == 0` |

## 12. Rollback Strategy

Git revert of changes to `compiler/src/`, `stdlib/vir/collections/vec.vri`, and tests.

## 13. Exit Criteria

- [x] Type-receiver constructors pass semantic checking and native lowering;
- [x] Generic Vec receiver calls resolve with correct specialization and preserve `ref`/move semantics;
- [x] Positive and negative test fixtures verified;
- [x] `collections.vec` exposes canonical facade while preserving compatibility symbols;
- [x] Verification report `STLB-RPT-0002` accepted and `STLB-ISS-0032` closed;
- [x] `./paper validate` clean.

## 14. Related Papers

- `STLB-ISS-0032`: Vec constructors and generic receiver UFCS are blocked by compiler dispatch
- `STLB-RPT-0002`: Lower type receiver constructors and canonical Vec facade report
- `STLB-ISS-0007`: The typed collections Vec module does not compile
- `VIRC-ISS-0064`: Generic receiver UFCS does not resolve or specialize for generic entities

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial plan for type-receiver constructor lowering and canonical Vec facade |
| 2026-10-09 | Completed implementation, verified tests, and linked STLB-RPT-0002 |
