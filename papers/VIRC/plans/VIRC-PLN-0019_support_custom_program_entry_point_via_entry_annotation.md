---
id: "VIRC-PLN-0019"
type: "PLAN"
domain: "VIRC"
title: "Support custom program entry point via @entry annotation"
status: "COMPLETED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "frontend-parser"
  - "semantic"
  - "ast-to-mir"
  - "driver"
  - "lir-codegen"
  - "entrypoint"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0025"
  plans: []
  reports:
    - "VIRC-RPT-0036"
supersedes: null
superseded_by: null
tags:
  - "entry"
  - "entry-point"
  - "attribute"
  - "bare-metal"
  - "conformance"
---

# VIRC-PLN-0019 — Support custom program entry point via @entry annotation

## 1. Objective

Implement full compiler support for custom program entry points declared with
the `@entry` annotation (Vir Spec §18 / VIR-SPC-0017 §18 / VIR-SPC-0018 §18).
Ensure that annotated functions are validated during semantic analysis, preserved
through AST-to-MIR and MIR-to-LIR lowering, and dispatched as the executable's
entry point across all target code generators (ARM64, x86-64, RISC-V, and Wasm)
without requiring a function named `main`.

## 2. Source Issues

- VIRC-ISS-0025 — The compiler parses @entry but discards it and still requires func main

## 3. Scope

### In Scope

- Retain `@entry` attribute metadata across semantic analysis, AST-to-MIR, and
  MIR-to-LIR lowering.
- Validate `@entry` in semantic analysis Pass 6:
  - Reject annotations on non-function declarations (E3098).
  - Reject multiple/duplicate `@entry` declarations (E3099).
  - Reject `@entry` functions with parameters (E3100).
- Update executable driver (`step_lower.vri`) to accept the designated `@entry`
  function in place of `main`.
- Update all backend code generators (`lir_codegen.vri`, `lir_codegen_x86.vri`,
  `lir_codegen_riscv.vri`, `lir_codegen_wasm.vri`) to branch to the resolved
  entry function from `_start`.
- Update reachability analysis in IDE semantic mode (`ide_semantic.vri`).
- Coexistence: If both `@entry func foo` and `func main` exist, `@entry`
  overrides `main` as the program entry point.
- Register positive and negative fixtures into test suites (including Group 18).

### Out of Scope

- Changing language syntax or VIR Spec v2.0 grammar.
- Custom linker script generation (linker script symbols remain a linker concern).
- ABI changes to ordinary hosted `func main`.

## 4. Current Architecture

- The parser wraps declarations following `@entry` in `AstType.BindAttr` with
  attribute name `"entry"`.
- Semantic analysis passes traverse the wrapper without recording an entry
  function identity or checking signature/multiplicity rules.
- `ast_to_mir.vri` un緻nwrap every `BindAttr` and discards the attribute name.
- `step_lower.vri` hard-codes a lookup for a LIR function named `"main"` and
  fails if absent with `virc: error: executable has no main function in LIR`.
- Backend code generators hard-code `"main"` (or `"__main__"`) as the branch
  target from `_start`.

## 5. Proposed Architecture

- Define centralized compiler entry tracking in `compiler/src/diagnostic/context.vri`:
  `g_has_custom_entry` and `g_entry_function_name`.
- In semantic Pass 6 (`walk_other.vri`): validate declaration kind, single-entry
  invariant, and 0-parameter signature.
- In `ast_to_mir.vri`: preserve `@entry` identity when lowering functions; do not
  prefix user module name onto the designated entry symbol.
- In `step_lower.vri`: verify that the resolved entry function exists in LIR.
- In backend codegen: resolve `_start` jump target to `g_entry_function_name`
  when a custom entry is active, otherwise falling back to default `main`.
- Reset entry state at driver session boundaries (`args.vri`, `semantic.vri`).

## 6. Design Decisions

### Decision 1: Priority of `@entry` over `main`

**Decision:** If a program defines both `@entry func custom_start` and
`func main`, `custom_start` is selected as the program entry point.

**Rationale:** Vir Spec §18 specifies `@entry` as an explicit override for
bare-metal/custom execution environments. Silently favoring `main` breaks
bare-metal execution.

**Alternatives considered:** Compile-time error when both exist. Rejected
because modular libraries or test fixtures may define helper `main` routines
while the entry module explicitly designates `@entry`.

### Decision 2: Zero-parameter constraint on `@entry`

**Decision:** `@entry` functions must have 0 parameters (E3100).

**Rationale:** Program entry points executed directly by bare-metal reset vectors
or raw OS `_start` stubs receive no Vir arguments from caller stack frames.

## 7. Implementation Plan

### Phase 1 — Compiler State & Semantic Validation

- Files: `compiler/src/diagnostic/context.vri`, `compiler/src/semantic/typecheck/walk_other.vri`,
  `compiler/src/semantic/diagnostics/msg_semantic.vri`, `compiler/src/semantic/diagnostics/actions.vri`,
  `compiler/src/main/driver/args.vri`, `compiler/src/semantic/semantic.vri`.
- Add `g_has_custom_entry`, `g_entry_function_name`, and session resets.
- Implement validation rules in Pass 6 (E3098, E3099, E3100).

### Phase 2 — Lowering & Driver Integration

- Files: `compiler/src/lower/ast_to_mir.vri`, `compiler/src/lower/ast_to_mir/func.vri`,
  `compiler/src/main/driver/pipeline/step_lower.vri`.
- Track `@entry` during AST-to-MIR lowering, exempt entry from module prefixing.
- Allow resolved entry in `step_lower.vri`.

### Phase 3 — Backend Codegen & IDE Reachability

- Files: `compiler/src/lower/lir_codegen.vri`, `compiler/src/lower/lir_codegen_x86.vri`,
  `compiler/src/lower/lir_codegen_riscv.vri`, `compiler/src/lower/lir_codegen_wasm.vri`,
  `compiler/src/ide/ide_semantic.vri`.
- Target entry branch target in ARM64, x86-64, RISC-V, and Wasm.
- Seed reachability in IDE semantic graph with custom entry.

### Phase 4 — Test Fixtures, Group 18, and Self-Host Bootstrap

- Files: `tests/test_entry.vri`, `tests/vri/test_entry.vri`, negative test fixtures,
  `run_tests.sh`.
- Sync modular sources to `compiler/generated/virc.vri`.
- Verify compilation, execution, and fixed-point bootstrap.

## 8. Compatibility

- Full backward compatibility for standard programs containing `func main`.
- Conformance with Vir Language Specification v2.0 §18.

## 9. Migration

No migration required for existing code.

## 10. Validation Plan

- Positive: `tests/test_entry.vri` prints `777`.
- User reproduction: grouped declarations and string interpolation inside `@entry`.
- Coexistence: `@entry` prints `111` while `main` prints `222`.
- Negatives: non-function `@entry` (E3098), duplicate `@entry` (E3099), `@entry` with args (E3100).
- Regression: Group 18 test suite and full compiler self-check.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Leaking entry state across compiler driver runs | Low | Medium | Explicit resets in `args.vri` and `semantic.vri` |
| Module mangling breaks entry symbol | Low | High | Explicit exemption in `ast_to_mir.vri` |

## 12. Rollback Strategy

Revert changes in `compiler/src/` and regenerate `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] All Acceptance Criteria of VIRC-ISS-0025 pass.
- [x] Group 18 executes positive and negative entry tests.
- [x] Compiler self-host fixed-point bootstrap succeeds.
- [x] VIRC-RPT report document created and approved.

## 14. Related Papers

- VIRC-ISS-0025
- VIRC-RPT-0036

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created plan for VIRC-ISS-0025 implementation |
| 2026-10-05 | Linked VIRC-RPT-0036 |
| 2026-10-05 | Completed implementation, verified fixed point, and marked COMPLETED |
