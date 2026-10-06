---
id: "VIRC-PLN-0008"
type: "PLAN"
domain: "VIRC"
title: "Modularize compiler driver and add canonical bundle entry module"
status: "COMPLETED"
created: "2026-10-03"
updated: "2026-10-03"
owners: []
components:
  - "compiler-driver"
  - "generated-compiler"
related:
  issues:
    - "VIRC-ISS-0011"
  plans: []
  reports:
    - "VIRC-RPT-0020"
supersedes: null
superseded_by: null
tags:
  - "driver"
  - "entry-module"
---

# VIRC-PLN-0008 — Modularize compiler driver and add canonical bundle entry module

## 1. Objective

Split `driver.vri` into cohesive modules, give the bundle header a canonical source, and remove self-referential pinned content from `compiler/generated/virc.vri`, with unchanged generated code.

## 2. Source Issues

- VIRC-ISS-0011

## 3. Scope

### In Scope
1. Extract nine contiguous ranges of `driver.vri` into `compiler/src/main/driver/{config,cli_output,ui,defaults,locate,args,pipeline,banner,main_entry}.vri`.
2. Keep `driver.vri` as orchestrator holding the `compiler.main`/`vec` imports and the `export` lines.
3. Add `compiler/src/entry.vri` (bundle header + `module vir.compiler.virc`).
4. Delete the 33 dead glue import sections from the bundle.
5. Harden `tools/sync_virc.py`: any self-referential marker in `compiler/generated/virc.vri` is an error.

### Out of Scope
- Splitting `virc_compile` internals, renaming symbols, changing behavior.

## 4. Current Architecture

`compiler/src/main/driver.vri` is one 1,432-line file; `compiler/generated/virc.vri` pins 77 lines of self-referential glue (header plus 33 import sections) that have no canonical source.

## 5. Proposed Architecture

`driver.vri` orchestrates nine modules under `compiler/src/main/driver/`; `compiler/src/entry.vri` owns the bundle header; the bundle has no self-referential markers.

## 6. Design Decisions

- Pure relocation of contiguous ranges preserves bundle order; no semantic edits.
- Glue imports are removed, not relocated: verified dead (byte-identical binary without them).
- Entry header lives in `compiler/src/entry.vri` (not `src/virc.vri`) to avoid clashing with the `virc = src` registry alias.

## 7. Implementation Plan

1. Phase 1 — `entry.vri` + remove glue + harden `sync_virc.py`; verify drift and bit-identical build.
2. Phase 2 — split `driver.vri`, register modules in `module.list`, re-sync bundle.
3. Phase 3 — full gates and 3-stage fixed point; report and closure.

## 8. Compatibility

No CLI, language or output change.

## 9. Migration

Internal source layout only; downstream users need no change.

## 10. Validation Plan

`check_module_dependencies.py`, `sync_virc.py --check`, `check_pass_architecture.py`, CLI contract (43), module fixtures (5), `./run_tests.sh min` (409/413), `cmp` stage3/stage4.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Relocation changes bundle text | Low | Med | Concatenated bundle text diff before/after must differ only in markers |
| Hidden dependence on glue imports | Low | High | Already disproved by byte-identical binary experiment |

## 12. Rollback Strategy

`git checkout` the touched files; restore `/tmp/virc_prev` if needed.

## 13. Exit Criteria

- [x] All ISS-0011 acceptance criteria met.
- [x] REPORT accepted and ISSUE closed.

## 14. Related Papers

- VIRC-ISS-0011, VIRC-ISS-0010, VIRC-PLN-0007

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial plan |
| 2026-10-03 | Implemented and verified; linked VIRC-RPT-0020; marked completed |
| 2026-10-03 | Linked VIRC-RPT-0020 |
