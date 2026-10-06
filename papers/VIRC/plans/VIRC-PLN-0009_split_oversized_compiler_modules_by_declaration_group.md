---
id: "VIRC-PLN-0009"
type: "PLAN"
domain: "VIRC"
title: "Split oversized compiler modules by declaration group"
status: "COMPLETED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "compiler-source-layout"
  - "parser"
  - "lowering"
  - "codegen-runtime-stubs"
related:
  issues:
    - "VIRC-ISS-0012"
  plans: []
  reports:
    - "VIRC-RPT-0021"
supersedes: null
superseded_by: null
tags:
  - "modularization"
  - "oversized-modules"
---

# VIRC-PLN-0009 — Split oversized compiler modules by declaration group

## 1. Objective

Convert five 1,000+ line compiler modules into orchestrators over cohesive sub-modules without changing generated output.

## 2. Source Issues

- VIRC-ISS-0012

## 3. Scope

### In Scope
| Module | Parts (lines) |
|---|---|
| `frontend/parser/expr` | primary 683, postfix_generics 142, pratt 169, unary 314 |
| `frontend/parser/stmt_decl` | type_expr 258, func_def 482, aggregate_def 410, assign_helpers 42 |
| `lower/lir_codegen/rt_stubs_math` | matmul 321, port_array 124, quantize_backward 355, stub_emit 187, frame 173 |
| `lower/lir_codegen_x86/rt_stubs_math` | tensor 297, backward_quantize 472, stub_emit 275, frame 12 |
| `lower/ast_to_mir/layout` | enum_names 279, type_infer 416, field_layout 468 |

### Out of Scope
Single-function modules (`stmt_dispatch`, `stmt_control`, `riscv64`), runtime copies (`alloc`), any semantic refactor.

## 4. Current Architecture

Each module is one file with its includes and all declarations.

## 5. Proposed Architecture

The original file keeps its doc header and includes and additionally includes each sub-module; each sub-module repeats the original include list and holds one contiguous declaration group, registered as `<module_alias>_<part>` in `compiler/module.list`.

## 6. Design Decisions

- Contiguous relocation preserves bundle order and generated code.
- Sub-modules use the flat namespace for mutually recursive parser functions rather than cyclic includes.
- No `export`/`import` exist in these files, so public surface is unchanged.

## 7. Implementation Plan

1. Split with a mechanical script that rewrites sources, `module.list` and bundle markers.
2. Re-sync the bundle; diff non-comment bundle text.
3. Run gates, build the self-hosted compiler, compare bytes, run suites.

## 8. Compatibility

No behavior change.

## 9. Migration

Internal layout only.

## 10. Validation Plan

`sync_virc --check`, `check_module_dependencies`, `check_pass_architecture`, `cmp` of rebuilt compiler, CLI contract, `./run_tests.sh min`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Relocation changes bundle code | Low | High | Non-comment bundle diff must be empty; binary `cmp` |

## 12. Rollback Strategy

`git checkout` the touched files and re-sync.

## 13. Exit Criteria

- [x] All ISS-0012 acceptance criteria met; REPORT accepted.

## 14. Related Papers

- VIRC-ISS-0012, VIRC-ISS-0011, VIRC-PLN-0008

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial plan |
| 2026-10-03 | Linked VIRC-RPT-0021 |
| 2026-10-03 | Implemented and verified; linked VIRC-RPT-0021; marked completed |
