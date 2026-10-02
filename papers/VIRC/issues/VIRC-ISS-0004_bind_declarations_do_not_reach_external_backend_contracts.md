---
id: "VIRC-ISS-0004"
type: "ISSUE"
domain: "VIRC"
title: "Bind declarations do not reach external backend contracts"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-02"
updated: "2026-10-02"
owners: [compiler]
components: [parser, semantic-analysis, ffi, mir, abi, wasm, object-writers, tests]
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: [bind, ffi, abi, wasm-import, no-opt, artifact-contract]
---

# VIRC-ISS-0004 — Bind declarations do not reach external backend contracts

## 1. Summary

`@bind` parsing and parameter-annotation checks are partially implemented, but
binding identity is discarded before lowering. `@bind(c)` and `@bind(wasm)` are
still treated as local `FuncDef` bodies, `@bind(asm)` body requirements are not
enforced, and the two structural gates have generic success fallbacks rather
than real WASM-import/no-opt oracles. This issue tracks only the missing
semantic, metadata, ABI, backend, and test path; working attribute parsing and
missing-annotation diagnostics are excluded.

## 2. Context

`docs/plan/STRICT_BIND_FFI_BACKEND_END_TO_END_PROMPT.md` recorded a valid C
binding returning zero instead of calling the external symbol. The 2026-10-02
audit reran the active `FFI-001..007` contract and inspected modular compiler
sources. The existing `extern func` registry and object-writer machinery are
working architectural inputs, not proof that `@bind` reaches them.

## 3. Expected Behavior

- `@bind(c)` and `@bind(wasm)` are declaration-only external functions with
  typed ABI signatures and no local MIR body or missing-return warning.
- Calls register and mark the external symbol through one target-neutral FFI
  registry, then produce correct native linkage or WASM imports.
- `@bind(asm)` requires a body and retains a function-scoped no-opt contract
  across supported optimization levels without disabling required lowering.
- Invalid target, placement, body form, signature, provider, or symbol conflict
  fails before codegen and leaves no artifact.
- Each target/bind pair is verified with an appropriate runtime or structural
  oracle; a generic exit-zero fallback cannot pass the gate.

## 4. Actual Behavior

- The parser constructs `AstType.BindAttr` with the target and wrapped
  declaration, and Pass 6 rejects missing C/WASM parameter annotations.
- Passes 2, 3, and 6 unwrap/walk the child as a normal function. They do not
  classify C/WASM as declaration-only or require an asm body.
- `ast_lower_program` strips `BindAttr`, sees the child `FuncDef`, and sends it
  to `ast_lower_func`. Only `AstType.ExternFunc` calls `ffi_import_register`.
- The active FFI contract reports failures for C/WASM-with-body rejection and
  asm-without-body rejection.
- FFI-003 and FFI-007 report PASS only because the generic structural fallback
  exits zero; they do not prove asm optimizer bypass or a WASM import section.
- Existing `tests/test_bind.vri` and `tests/vri/test_bind.vri` do not invoke the
  declared C/WASM functions, so their stdout cannot detect a local zero stub.

## 5. Reproduction

```sh
python3 tools/gap_contract_runner.py --filter '^FFI-' --verbose
sed -n '5070,5165p' stdlib/vir/compiler/sem_pass6_typecheck.vri
sed -n '7135,7200p' stdlib/vir/compiler/ast_to_mir.vri
sed -n '1,180p' tests/test_bind.vri
sed -n '77,83p' tests/spec_gap_contract/manifest.tsv
```

Current result: 4 PASS / 3 FAIL / 0 BLOCKED. FFI-001, FFI-002, and FFI-006
fail because the compiler emits artifacts for invalid declarations. The two
structural PASS results state only `Structural check executed (exit=0)`.

## 6. Evidence

- CONFIRMED: `parser.vri:5382-5418` preserves bind target and child declaration.
- CONFIRMED: `sem_pass6_typecheck.vri:5093-5130` checks missing parameter types
  for C/WASM but performs no body-kind contract enforcement.
- CONFIRMED: `ast_to_mir.vri:7158-7186` unwraps `BindAttr`; only the subsequent
  `ExternFunc` branch registers an FFI import, while wrapped `FuncDef` lowers
  locally.
- CONFIRMED: active `FFI-001..007` execution produced 4 PASS and 3 FAIL on
  2026-10-02; FFI-001/002/006 emitted forbidden artifacts.
- CONFIRMED: the runner's generic structural path does not inspect asm no-opt or
  WASM type/import/call sections for FFI-003/007.
- CONFIRMED: declaration smoke tests never call `add_c` or `wasm_stub`.
- OBSERVED: `ffi_imports.vri`, Mach-O, and WASM writer code already provide an
  extern path that bind can intentionally share.
- NOT_VERIFIED: ABI correctness beyond the existing extern path, cross-target
  native linking, WASM host instantiation, and asm no-opt preservation.

## 7. Scope

### Affected

- one-time bind classification and typed metadata preservation;
- C/WASM declaration-only and asm body/no-opt semantic contracts;
- target-neutral FFI registry integration, symbol identity/conflict handling;
- native ABI/object linking and WASM import/type/call lowering;
- invocation, structural, mutation, artifact-absence, target, and bootstrap
  evidence.

### Not affected / Already complete

- attribute parsing and target text preservation;
- current missing-parameter-type checks represented by FFI-004/005;
- existing `extern func` behavior except regression preservation;
- language-spec changes, new assembly syntax, unsupported aggregate/variadic/
  callback FFI, or consumer runtime substitutions.

## 8. Impact

A valid external declaration can compile as a local function and return an
incorrect value without a link failure. Invalid bind forms also produce
artifacts, and green structural labels overstate coverage. This is a core
correctness failure with silent wrong-code potential, so it is S1/P0.

## 9. Preliminary Analysis

- CONFIRMED: the root disconnect is between `BindAttr` and the existing
  `ExternFunc`/FFI registry path.
- CONFIRMED: semantic checks cover parameter annotations only, not declaration
  form or asm body requirements.
- OBSERVED: sharing the target-neutral registry is architecturally preferable
  to introducing per-emitter bind tables.
- HYPOTHESIS: bind kind should be classified before symbol registration and
  lowered into an explicit external/local-no-opt function descriptor retained
  through MIR/LIR.
- NOT_VERIFIED: complete per-target ABI coverage and the exact function-scoped
  no-opt invariant supported by every active optimizer stage.

## 10. Acceptance Criteria

- [ ] C/WASM body and asm missing-body negatives fail semantically with stable
  diagnostics and no artifact; FFI-001/002/006 pass for the intended reason.
- [ ] `@bind(c)` invocation reaches a real external symbol with changing inputs
  and observable side effects; no local stub or spurious missing-return warning
  remains.
- [ ] Binding kind, signature, provider/symbol, and no-opt metadata survive
  symbol, MIR, LIR, clone/specialization, and writer boundaries.
- [ ] Supported native ABIs validate integer/floating/pointer/void, mixed and
  stack arguments, returns, alignment, clobbers, relocation, and dependencies;
  unsupported signatures fail before codegen.
- [ ] WASM oracle inspects type/import/function/call indices and instantiates
  with a host function; missing or mismatched imports fail.
- [ ] Asm oracle proves function-scoped optimizer exclusion at each supported
  optimization level and includes a normal-function control.
- [ ] Runner mutation controls reject local stubs, missing imports, wrong
  signatures, and lost no-opt; generic structural fallback cannot yield PASS.
- [ ] Existing extern, ownership/lifetime, module identity, min/full, sync, and
  self-host fixed-point gates remain green with a newly built compiler.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from 3/7 failing bind contract plus production source audit; excluded completed parser and annotation validation work |
