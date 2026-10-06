---
id: "VIRC-PLN-0025"
type: "PLAN"
domain: "VIRC"
title: "Complete bind FFI semantic and backend contracts"
status: "ACTIVE"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "parser"
  - "semantic-analysis"
  - "ffi"
  - "mir"
  - "lir"
  - "wasm"
  - "object-writers"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0004"
  plans: []
  reports:
    - "VIRC-RPT-0042"
supersedes: null
superseded_by: null
tags:
  - "bind"
  - "ffi"
  - "abi"
  - "wasm-import"
  - "no-opt"
  - "artifact-contract"
---

# VIRC-PLN-0025 — Complete bind FFI semantic and backend contracts

## 1. Objective

Complete the end-to-end `@bind(c|wasm|asm)` contract: reject invalid body
forms before codegen, route declaration-only bindings through the existing
target-neutral external registry, preserve asm no-opt identity, and replace
generic structural success with target-specific evidence.

## 2. Source Issues

- VIRC-ISS-0004


## 3. Scope

### In Scope

- semantic declaration/body/signature validation;
- C/WASM external classification and FFI registry registration;
- native/WASM call and import emission through the existing extern path;
- function-scoped asm optimization exclusion;
- strict structural/mutation oracles and artifact-absence checks.

### Out of Scope

- new assembly language syntax or inline-assembly parsing;
- variadic, aggregate-by-value, callback, or unsupported foreign ABIs;
- replacing the existing extern registry or object writers.

## 4. Current Architecture

The parser preserves a `BindAttr` target and wrapped `FuncDef`. Pass 6 checks
missing C/WASM parameter annotations only. Lowering unwraps the attribute and
lowers every wrapped `FuncDef` locally; only `ExternFunc` reaches
`ffi_import_register`. MIR and LIR optimization have no bind-scoped marker.
The Wasm writer can already emit used registry entries, but the active runner
does not inspect the import/type/call structure.

## 5. Proposed Architecture

Pass 6 is the single classification boundary. Empty-body C/WASM declarations
become `ExternFunc` nodes with explicit providers (`os` for C, `env` for Wasm);
non-empty bodies are rejected. Asm bindings remain local functions, require a
non-empty body, and are registered by canonical function name in a no-opt set
used by both MIR and LIR optimizer dispatch. Calls continue through the shared
FFI registry, so native relocation and Wasm import emission share one identity.

## 6. Design Decisions

### Decision 1 — Reuse `ExternFunc` and the FFI registry

**Decision:** Normalize valid C/WASM binds to the existing external-function
representation rather than adding a second backend path.

**Rationale:** Call lowering, symbol marking, relocations, and Wasm imports
already consume this registry.

**Alternatives considered:** Per-target bind tables and local zero stubs were
rejected because they duplicate symbol identity or silently produce wrong code.

**Trade-offs:** Provider defaults remain explicit compiler policy until richer
attribute arguments are specified.

## 7. Implementation Plan

### Phase 1 — Semantic classification

- files/modules: pass-6 bind walker and diagnostics;
- changes: stable body-form errors, explicit external/no-opt classification;
- dependencies: existing parser AST body block;
- expected result: FFI-001/002/004/005/006 reject correctly with no artifact.

### Phase 2 — Lowering and backend metadata

- files/modules: AST-to-MIR context/orchestrator and pipeline;
- changes: register C/WASM signatures/providers; skip optional MIR/LIR
  optimization only for asm-bound functions while retaining required CFG, SSA,
  verification, lowering, and register allocation;
- expected result: no local C/WASM body and stable asm instruction structure.

### Phase 3 — Strict oracles and bootstrap

- files/modules: FFI fixtures, gap-contract runner, generated compiler bundle;
- changes: parse Wasm imports/types/calls, compare asm across `-O0..-O3`, add
  mutation controls, synchronize and bootstrap;
- expected result: all FFI gates pass for intended reasons.

### Phase 4 — Native floating ABI completion

- files/modules: AST-to-MIR call classification, direct ARM64/x86 codegen,
  LIR-to-MC lowering/printer, target validation, and FFI runtime fixtures;
- changes: transport f64 arguments/results through D/XMM registers, assign
  mixed floating/integer arguments independent ABI indices, and fail closed
  for RISC-V f64 until RV64D foreign-call transport is implemented;
- verified result: macOS ARM64 runtime covers `fabs` and mixed `ldexp`, while
  Linux ARM64/x86-64 assembly proves the expected register classes.

## 8. Compatibility

- Existing valid declaration-only C/WASM and body-bearing asm sources remain
  source-compatible; previously accepted invalid forms are rejected.
- No parser grammar, serialized format, LSP protocol, or stdlib API changes.
- External calls use the established native ABI and object-writer contracts.

## 9. Migration

No migration required.

## 10. Validation Plan

- FFI-001..007 with target-specific structural checks;
- native external invocation with changing inputs and side effect;
- Wasm binary type/import/call inspection and host instantiation;
- asm `-O0..-O3` comparison with a normal-function control;
- extern regressions, dependency/sync gates, and byte-identical bootstrap.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AST mutation affects later passes | Medium | High | normalize once in pass 6 and retain function symbol identity |
| No-opt skips required lowering | Low | High | skip only optional optimizer hooks, never CFG/SSA/RA/codegen |
| Wasm signature encoding is incomplete | Medium | High | inspect exact type/import/call indices and reject unsupported types |

## 12. Rollback Strategy

Revert semantic normalization, no-opt registry checks, and strict runner
oracles together; do not restore local foreign stubs as a compatibility path.

## 13. Exit Criteria

- [x] invalid bind forms reject before artifact creation;
- [x] C/WASM bindings use the external registry and real backend imports;
- [x] asm functions bypass optional optimization at all supported levels;
- [x] strict FFI structural/mutation gates pass;
- [x] sync, focused regression, and self-host fixed-point gates pass;
- [ ] native floating-register and cross-target ABI matrix is complete
  (AAPCS64/SysV AMD64 f64 structure is verified; Linux x86-64 runtime and
  relocation/dependency execution plus RV64D float support remain);
- [ ] accepted closing report maps every issue criterion before closure.

## 14. Related Papers

- `VIRC-ISS-0004`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created, approved, and activated from the confirmed pass-6/lowering registry disconnect |
| 2026-10-05 | Verified 10/10 FFI contract, 7/7 Group 15, typed Wasm host import, asm O0..O3 no-opt, and byte-identical bootstrap; retained active for native floating/cross-target ABI evidence |
| 2026-10-05 | Implemented AAPCS64/SysV AMD64 f64 and mixed FP/GPR argument transport, expanded the strict contract to 12/12, and promoted fixed-point compiler hash `af63c79d2f984eb5c5859ed00a0ea769f8fd13b3922a28b89394d9bb6d04f2d5`; retained ACTIVE for remaining cross-runtime and broad-suite exit evidence |
| 2026-10-05 | Linked VIRC-RPT-0042 |
