---
id: "VIRC-ISS-0012"
type: "ISSUE"
domain: "VIRC"
title: "Oversized compiler modules mix unrelated declaration groups"
status: "CLOSED"
severity: "S3"
priority: "P3"
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
  issues: []
  plans:
    - "VIRC-PLN-0009"
  reports:
    - "VIRC-RPT-0021"
supersedes: null
superseded_by: null
tags:
  - "modularization"
  - "oversized-modules"
---

# VIRC-ISS-0012 — Oversized compiler modules mix unrelated declaration groups

## 1. Summary

Five canonical compiler modules exceed 1,000 lines while bundling several unrelated declaration groups: `frontend/parser/expr.vri` (1,326), `frontend/parser/stmt_decl.vri` (1,207), `lower/lir_codegen/rt_stubs_math.vri` (1,175), `lower/lir_codegen_x86/rt_stubs_math.vri` (1,070) and `lower/ast_to_mir/layout.vri` (1,175).

## 2. Context

After `VIRC-ISS-0010` and `VIRC-ISS-0011`, these were the largest modules whose contents divide along existing function-group boundaries. Modules whose bulk is a single function (`parse_statement_impl`, `lower_stmt_control`, `lir_func_to_mc_riscv64`, `parse_primary`) cannot be split without semantic refactoring and are excluded.

## 3. Expected Behavior

Each listed module is an orchestrator over cohesive sub-modules (one declaration group each), registered in `compiler/module.list`, with unchanged generated compiler output.

## 4. Actual Behavior

Each module is a single file mixing groups, e.g. `rt_stubs_math.vri` mixes matmul, port/array, quantize/backward stubs, the emission driver and frame helpers.

## 5. Reproduction

```sh
wc -l compiler/src/frontend/parser/expr.vri compiler/src/frontend/parser/stmt_decl.vri \
  compiler/src/lower/lir_codegen/rt_stubs_math.vri compiler/src/lower/lir_codegen_x86/rt_stubs_math.vri \
  compiler/src/lower/ast_to_mir/layout.vri
```

## 6. Evidence

- CONFIRMED: none of the five files contains `import` or `export` statements, so splitting needs no export rewiring.
- CONFIRMED: `tools/sync_virc.py` strips `include` lines, so the bundle order is determined by markers and contiguous relocation preserves it.
- OBSERVED: top-level declaration lists show clear group boundaries (see PLAN).

## 7. Scope

### Affected
The five modules above, new sub-module directories beside them, `compiler/module.list`, `compiler/generated/virc.vri`.

### Not affected / Unknown
Language semantics, other modules, `stdlib/vir/`. `riscv64.vri`, `stmt_control.vri`, `stmt_dispatch.vri` are single-function modules and are unchanged.

## 8. Impact

Severity: S3 (maintainability). Priority: P3.

## 9. Preliminary Analysis

Pure contiguous relocation, validated by comparing non-comment bundle text and the self-hosted binary byte-for-byte.

## 10. Acceptance Criteria

- [x] The five modules are orchestrators over sub-modules grouped by declaration group.
- [x] Sub-modules are registered in `compiler/module.list` and bundled via markers.
- [x] Bundle code (excluding comments/blank lines) is unchanged.
- [x] 0 drift, 0 dependency violations, pass architecture passes.
- [x] Self-hosted compiler is byte-identical; CLI contract 43/43; `./run_tests.sh min` 409/413.
- [x] REPORT accepted and issue closed.

## 11. Related Papers

- `VIRC-ISS-0010`, `VIRC-ISS-0011`, `VIRC-PLN-0009`

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created from post-VIRC-ISS-0011 size audit |
| 2026-10-03 | Linked VIRC-RPT-0021 |
| 2026-10-03 | Verified all acceptance criteria via VIRC-RPT-0021 under VIRC-PLN-0009; closed issue |
