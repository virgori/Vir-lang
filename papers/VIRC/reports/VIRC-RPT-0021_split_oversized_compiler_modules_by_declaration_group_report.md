---
id: "VIRC-RPT-0021"
type: "REPORT"
domain: "VIRC"
title: "Split oversized compiler modules by declaration group report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0009"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "modularization"
  - "oversized-modules"
---

# VIRC-RPT-0021 — Split oversized compiler modules by declaration group report

## 1. Executive Summary

Five compiler modules that exceeded 1,000 lines were converted into orchestrators over 19 cohesive sub-modules (283 compiler source files in total, up from 263). The self-hosted compiler rebuilt from the new sources is byte-identical to the previous one (19,797,871 bytes).

## 2. Source Issues

- VIRC-ISS-0012

## 3. Source Plans

- VIRC-PLN-0009

## 4. Implementation Summary

A mechanical splitter relocated contiguous top-level ranges into sub-modules, registered them in `compiler/module.list`, and replaced each bundle marker by a marker per part. The bundle was re-synchronized and compared against its pre-split text.

## 5. Changes by Component

| Module | Sub-modules (lines) |
|---|---|
| `frontend/parser/expr` | `expr/primary` 683, `postfix_generics` 142, `pratt` 169, `unary` 314 |
| `frontend/parser/stmt_decl` | `stmt_decl/type_expr` 258, `func_def` 482, `aggregate_def` 410, `assign_helpers` 42 |
| `lower/lir_codegen/rt_stubs_math` | `matmul` 321, `port_array` 124, `quantize_backward` 355, `stub_emit` 187, `frame` 173 |
| `lower/lir_codegen_x86/rt_stubs_math` | `tensor` 297, `backward_quantize` 472, `stub_emit` 275, `frame` 12 |
| `lower/ast_to_mir/layout` | `enum_names` 279, `type_infer` 416, `field_layout` 468 |

Each original file keeps its doc header and includes, and includes every sub-module. Registry names are `<module_alias>_<part>` (e.g. `parser_expr_primary`).

## 6. Deviations from Plan

None material. The x86 `frame` part is only 12 lines (callee save/restore); it was kept as its own module to mirror the ARM64 layout.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Bundle diff vs pre-split | PASS | only module doc comments and 4 trailing blank lines differ; zero code lines changed |
| `python3 tools/sync_virc.py --check` | PASS | 0 drift |
| `python3 tools/check_module_dependencies.py` | PASS | 283 files, 0 violations |
| `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, 283 modules clean |
| `python3 tools/paper.py validate` | PASS | 84 production papers |
| Self-host | PASS | stage2 and stage3 built from the new bundle are `cmp`-identical to the prior `bin/virc` |
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 |
| `tests/modules/test_*.vri` | PASS | 5/5 exit 0 |
| `./run_tests.sh min` | PASS (baseline) | 409/413, same 4 known failures |

### Regression

Zero regression against the 409/413 baseline.

### Conformance

No language, CLI or `stdlib/vir/` change.

## 8. Acceptance Criteria

- [x] Five modules are orchestrators over sub-modules grouped by declaration group.
- [x] Sub-modules registered in `compiler/module.list` and bundled via markers.
- [x] Bundle code unchanged.
- [x] 0 drift, 0 dependency violations, pass architecture passes.
- [x] Self-hosted compiler byte-identical; CLI contract 43/43; min suite 409/413.
- [x] REPORT accepted, issue closed.

## 9. Known Limitations

- Modules dominated by one function remain large: `parse_statement_impl` (`stmt_dispatch`, ~1,165 lines), `lower_stmt_control` (~1,000), `lir_func_to_mc_riscv64` (~1,030), `parse_primary` (683). Splitting them needs semantic refactoring.
- `alloc.vri` and `alloc_prelude.vri` (runtime copies) were not split.
- Sub-modules rely on the flat bundle namespace for cross-part references (notably mutually recursive parser functions).

## 10. Remaining Work

None under VIRC-ISS-0012. Function-level decomposition of the large single functions can be tracked as a separate issue.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0012, VIRC-PLN-0009, VIRC-ISS-0011, VIRC-RPT-0020

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0012 / VIRC-PLN-0009 |
