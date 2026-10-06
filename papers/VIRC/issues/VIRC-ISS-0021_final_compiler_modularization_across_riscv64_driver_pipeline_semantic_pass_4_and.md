---
id: "VIRC-ISS-0021"
type: "ISSUE"
domain: "VIRC"
title: "Final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator"
status: "CLOSED"
severity: "S3"
priority: "P3"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "riscv64-lowering"
  - "driver-pipeline"
  - "semantic-pass4"
  - "runtime-allocator"
related:
  issues: []
  plans:
    - "VIRC-PLN-0011"
  reports:
    - "VIRC-RPT-0023"
supersedes: null
superseded_by: null
tags:
  - "modularization"
  - "riscv64"
  - "pipeline"
  - "pass4"
  - "allocator"
---

# VIRC-ISS-0021 — Final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator

## 1. Summary

Four remaining oversized areas across the compiler source tree (`compiler/src/lower/lir_to_mc/riscv64.vri` at 1,102 lines, `compiler/src/main/driver/pipeline.vri` at 606 lines, Semantic Pass 4 in `compiler/src/semantic/type_table.vri` + `sem_pass4_types.vri` at 1,058 lines, and `compiler/src/rt/alloc.vri` at 1,379 lines) each mix separate domain logic and violate the single-responsibility decomposition target.

## 2. Context

Following the modularization of the AST-to-MIR lowering, parser dispatch, compiler driver, and MC printer under VIRC-PLN-0004 through VIRC-PLN-0010, an architectural audit identified four remaining monolithic components in `compiler/src/`:
1. RISC-V 64 LIR to MC lowering (`compiler/src/lower/lir_to_mc/riscv64.vri`): 1,102 lines combining helpers, moves, ALU/FMA, branching/calls, and target-specific intrinsics.
2. Compiler driver pipeline (`compiler/src/main/driver/pipeline.vri`): 606 lines combining frontend expansion/parsing, semantic passes, AST-to-LIR lowering, and backend assembly emission/linking.
3. Semantic Pass 4 (`compiler/src/semantic/type_table.vri` 796 lines and `sem_pass4_types.vri` 262 lines): combining basic type management, dense tensor shape/layout calculations, quantized tensor codecs, symbol type resolution, and AST walking.
4. Pure Vir low-level runtime allocator (`compiler/src/rt/alloc.vri`): 1,379 lines mixing mmap page allocation, bump arena, TLSF bitmaps/structures, heap allocation/coalescing/realloc, heap verification, and deep graph promotion.

## 3. Expected Behavior

Each oversized component is decomposed into cohesive domain-specific submodules located in dedicated subdirectories, with concise orchestrators under 300 logical lines. All submodules are registered in `compiler/module.list` and bundled into `compiler/generated/virc.vri` with zero bundle drift, zero dependency violations, and clean pass architecture checks.

## 4. Actual Behavior

The four areas were monolithic single-file implementations exceeding maintainability guidelines and making domain-level review and testing difficult.

## 5. Reproduction

Audit line counts in `compiler/src/`:
```sh
wc -l compiler/src/lower/lir_to_mc/riscv64.vri \
      compiler/src/main/driver/pipeline.vri \
      compiler/src/semantic/type_table.vri \
      compiler/src/semantic/sem_pass4_types.vri \
      compiler/src/rt/alloc.vri
```

## 6. Evidence

- `compiler/src/lower/lir_to_mc/riscv64.vri`: 1,102 lines (monolithic opcode dispatch).
- `compiler/src/main/driver/pipeline.vri`: 606 lines (monolithic compilation pipeline).
- `compiler/src/semantic/type_table.vri`: 796 lines + `sem_pass4_types.vri`: 262 lines (monolithic type checking and layout tables).
- `compiler/src/rt/alloc.vri`: 1,379 lines (monolithic TLSF allocator and runtime memory manager).

## 7. Scope

### Affected

- `compiler/src/lower/lir_to_mc/riscv64.vri` and `compiler/src/lower/lir_to_mc/riscv64/`
- `compiler/src/main/driver/pipeline.vri` and `compiler/src/main/driver/pipeline/`
- `compiler/src/semantic/type_table.vri`, `sem_pass4_types.vri`, and `compiler/src/semantic/types/`
- `compiler/src/rt/alloc.vri` and `compiler/src/rt/alloc/`
- `compiler/module.list`
- `compiler/generated/virc.vri`

### Not affected / Unknown

- `stdlib/vir/**` (stdlib untouched).
- Compiler AST/MIR/LIR data structure definitions.
- Language syntax and semantics.

## 8. Impact

Eliminates all remaining monolithic pass/runtime files in `compiler/src/`, establishing fine-grained modularity, improved build performance, reduced function complexity, and complete test suite reproducibility.

## 9. Preliminary Analysis

- CONFIRMED: `riscv64.vri` can be cleanly partitioned into 6 submodules: `helpers.vri`, `mov.vri`, `alu.vri`, `branch.vri`, `call.vri`, and `intrinsics.vri`.
- CONFIRMED: `pipeline.vri` can be partitioned into 4 pipeline steps: `step_frontend.vri`, `step_semantic.vri`, `step_lower.vri`, and `step_backend.vri`.
- CONFIRMED: Semantic Pass 4 can be partitioned into 5 submodules: `table.vri`, `tensor.vri`, `quantized.vri`, `resolve.vri`, and `walk.vri`.
- CONFIRMED: `rt/alloc.vri` can be partitioned into 5 submodules: `mmap_core.vri`, `tlsf_core.vri`, `slab.vri`, `verify.vri`, and `promote.vri`.

## 10. Acceptance Criteria

- [x] Area 1: `compiler/src/lower/lir_to_mc/riscv64.vri` decomposed into 6 submodules under `compiler/src/lower/lir_to_mc/riscv64/` (orchestrator reduced from 1,102 to 142 lines).
- [x] Area 2: `compiler/src/main/driver/pipeline.vri` decomposed into 4 step submodules under `compiler/src/main/driver/pipeline/` (orchestrator reduced from 606 to 72 lines).
- [x] Area 3: Semantic Pass 4 (`sem_pass4_types.vri` and `type_table.vri`) decomposed into 5 submodules under `compiler/src/semantic/types/` (`type_table.vri` reduced to 12 lines, `sem_pass4_types.vri` reduced to 25 lines).
- [x] Area 4: `compiler/src/rt/alloc.vri` decomposed into 5 submodules under `compiler/src/rt/alloc/` (orchestrator reduced from 1,379 to 72 lines).
- [x] All 20 new submodules registered in `compiler/module.list` (total compiler source modules expanded from 294 to 314).
- [x] Generated bundle `compiler/generated/virc.vri` synchronized with zero drift (`python3 tools/sync_virc.py --check`).
- [x] Module dependencies gate passes with zero violations (`python3 tools/check_module_dependencies.py`).
- [x] Pass architecture verification passes (`python3 tools/check_pass_architecture.py`).
- [x] CLI contract suite passes (43/43).
- [x] Module fixtures pass (10/10).
- [x] Historical test baseline maintained (409/413 in `./run_tests.sh min`).
- [x] Bit-identical 3-stage self-hosting fixed point verified (`bin/virc_stage3` == `bin/virc_stage4`).

## 11. Related Papers

### Issues

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.
- `VIRC-ISS-0010` — Eliminate compiler legacy dead code and establish canonical runtime tree.
- `VIRC-ISS-0012` — Oversized compiler modules mix unrelated declaration groups.
- `VIRC-ISS-0015` — Oversized parser and lowering functions are single monolithic dispatch chains.

### Plans

- `VIRC-PLN-0011` — Execute final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator.

### Reports

- `VIRC-RPT-0023` — Final compiler modularization completion report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial issue creation for final compiler modularization |
| 2026-10-03 | All four areas decomposed, quality gates verified, marked RESOLVED |
| 2026-10-03 | Full verification: CLI contract 43/43, min tests 409/413, bit-identical fixed point; marked CLOSED |
