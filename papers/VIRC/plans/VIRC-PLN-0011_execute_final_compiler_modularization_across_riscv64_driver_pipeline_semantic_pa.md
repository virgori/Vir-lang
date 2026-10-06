---
id: "VIRC-PLN-0011"
type: "PLAN"
domain: "VIRC"
title: "Execute final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator"
status: "COMPLETED"
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
  issues:
    - "VIRC-ISS-0021"
  plans: []
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

# VIRC-PLN-0011 — Execute final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator

## 1. Objective

Decompose the final four oversized monolithic components in `compiler/src/` into cohesive, single-responsibility submodules and clean orchestrators, completing compiler modularization and establishing 100% fine-grained source module architecture across all compiler domains.

## 2. Source Issues

- [VIRC-ISS-0021](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0021_final_compiler_modularization_across_riscv64_driver_pipeline_semantic_pass_4_and.md) — Final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator.

## 3. Scope

### In Scope

- **Area 1 — RISC-V 64 LIR to MC Lowering:** Decompose `compiler/src/lower/lir_to_mc/riscv64.vri` (1,102 lines) into `compiler/src/lower/lir_to_mc/riscv64/` (`helpers.vri`, `mov.vri`, `alu.vri`, `branch.vri`, `call.vri`, `intrinsics.vri`).
- **Area 2 — Compiler Driver Pipeline:** Decompose `compiler/src/main/driver/pipeline.vri` (606 lines) into `compiler/src/main/driver/pipeline/` (`step_frontend.vri`, `step_semantic.vri`, `step_lower.vri`, `step_backend.vri`).
- **Area 3 — Semantic Pass 4 & Type Table:** Decompose `compiler/src/semantic/type_table.vri` (796 lines) and `sem_pass4_types.vri` (262 lines) into `compiler/src/semantic/types/` (`table.vri`, `tensor.vri`, `quantized.vri`, `resolve.vri`, `walk.vri`).
- **Area 4 — Runtime Allocator:** Decompose `compiler/src/rt/alloc.vri` (1,379 lines) into `compiler/src/rt/alloc/` (`mmap_core.vri`, `tlsf_core.vri`, `slab.vri`, `verify.vri`, `promote.vri`).
- Registration of all 20 new submodules in `compiler/module.list`.
- Synchronization of `compiler/generated/virc.vri` with zero bundle drift.
- Verification across all repository quality gates and bit-identical 3-stage self-hosting fixed point.

### Out of Scope

- Standard library modifications (`stdlib/vir/**`).
- Language grammar or syntax changes.
- AST/MIR/LIR instruction schema modifications.

## 4. Current Architecture

Prior to this plan, four areas remained monolithic in `compiler/src/`:
- `compiler/src/lower/lir_to_mc/riscv64.vri`: 1,102 lines implementing RISC-V register saving, stack management, ALU emission, matmul FMA, branching, jumps, calls, and intrinsics.
- `compiler/src/main/driver/pipeline.vri`: 606 lines implementing source ingestion, frontend expansion, parsing, semantic pass sequence, AST-to-MIR-to-LIR lowering, and native code emission/linking.
- `compiler/src/semantic/type_table.vri` and `sem_pass4_types.vri`: 1,058 lines combining scalar types, tensor shape/stride calculation, quantized codecs, symbol type resolution, and AST walking.
- `compiler/src/rt/alloc.vri`: 1,379 lines implementing kernel mmap, page allocation, bump Arena, TLSF bitwise scanning, segment registry, hash table, free list bins, coalescing, verification, and graph promotion.

## 5. Proposed Architecture

Each area is decomposed into dedicated submodules:
1. `compiler/src/lower/lir_to_mc/riscv64/`:
   - `helpers.vri`: Stack adjustment and helper routines.
   - `mov.vri`: Move, load, and store operations.
   - `alu.vri`: Arithmetic, logical, and matmul FMA operations.
   - `branch.vri`: Compare, jump, conditional jump, return, and epilogue.
   - `call.vri`: Call and argument lowering.
   - `intrinsics.vri`: Target intrinsics.
   - `riscv64.vri`: Orchestrator (142 lines).
2. `compiler/src/main/driver/pipeline/`:
   - `step_frontend.vri`: Source reading, encoding validation, include/import expansion, lexing, parsing.
   - `step_semantic.vri`: Semantic passes 1..10 execution.
   - `step_lower.vri`: Target selection and AST->MIR->LIR lowering.
   - `step_backend.vri`: Assembly emission, object generation, and linking.
   - `pipeline.vri`: Orchestrator (72 lines).
3. `compiler/src/semantic/types/`:
   - `table.vri`: Core TypeKind, TypeNode, TypeTable, alloc, query predicates.
   - `tensor.vri`: Dense tensor types, rank, shape, stride, numel, flux swizzles.
   - `quantized.vri`: Quantized formats, Q8_0 codec, uniform quantization.
   - `resolve.vri`: Pass 4 type name resolution.
   - `walk.vri`: AST type walk and symbol annotation.
   - `type_table.vri`: Composer (12 lines).
   - `sem_pass4_types.vri`: Pass orchestrator (25 lines).
4. `compiler/src/rt/alloc/`:
   - `mmap_core.vri`: Virtual memory and page allocation (`vm_alloc`, `page_alloc`, bump `Arena`).
   - `tlsf_core.vri`: Data structures (`FreeNode`, `Heap`), bitwise scans (`tlsf_fls`, `tlsf_ffs`), segments, hash table.
   - `slab.vri`: TLSF bins, block insert/remove, `heap_init`, `heap_alloc`, `heap_free`, `heap_realloc`.
   - `verify.vri`: Heap verification and destruction (`heap_verify`, `heap_destroy`).
   - `promote.vri`: Deep graph promotion runtime (`rt_promote_graph`).
   - `alloc.vri`: Orchestrator (72 lines).

## 6. Design Decisions

### Decision 1: Pure Delegation Orchestrators
Each decomposed parent module (`riscv64.vri`, `pipeline.vri`, `type_table.vri`, `sem_pass4_types.vri`, `alloc.vri`) acts as a pure orchestrator or composer. It includes and re-exports symbols, ensuring 100% backward compatibility for existing callers.

### Decision 2: Strict Topological Ordering in Generated Bundle
All submodules are bundled into `compiler/generated/virc.vri` in topological order preceding their orchestrators, ensuring that all types, entities, and constants are defined before use in single-pass compilation.

### Decision 3: Zero Redundant Module Dependencies
Every submodule adheres strictly to `tools/check_module_dependencies.py`, avoiding simultaneous `include M` and `import ... from M` declarations.

## 7. Implementation Plan

### Phase 1 — RISC-V 64 LIR to MC Lowering Decomposition
- Extract `helpers.vri`, `mov.vri`, `alu.vri`, `branch.vri`, `call.vri`, `intrinsics.vri`.
- Reduce `riscv64.vri` to orchestrator (142 lines).
- Register in `compiler/module.list`.

### Phase 2 — Compiler Driver Pipeline Decomposition
- Extract `step_frontend.vri`, `step_semantic.vri`, `step_lower.vri`, `step_backend.vri`.
- Reduce `pipeline.vri` to orchestrator (72 lines).
- Register in `compiler/module.list`.

### Phase 3 — Semantic Pass 4 & Type Table Decomposition
- Extract `table.vri`, `tensor.vri`, `quantized.vri`, `resolve.vri`, `walk.vri`.
- Reduce `type_table.vri` to composer (12 lines) and `sem_pass4_types.vri` to orchestrator (25 lines).
- Register in `compiler/module.list`.

### Phase 4 — Runtime Allocator Decomposition
- Extract `mmap_core.vri`, `tlsf_core.vri`, `slab.vri`, `verify.vri`, `promote.vri`.
- Reduce `alloc.vri` to orchestrator (72 lines).
- Register in `compiler/module.list`.

### Phase 5 — Quality Gate Verification & 3-Stage Self-Hosting
- Verify 0 bundle drift (`python3 tools/sync_virc.py --check`).
- Verify 0 dependency violations (`python3 tools/check_module_dependencies.py`).
- Verify pass architecture (`python3 tools/check_pass_architecture.py`).
- Verify CLI contract suite (43/43).
- Verify module fixtures (10/10).
- Verify min test suite (409/413 historical baseline).
- Complete 3-stage self-hosting fixed point build (`cmp bin/virc_stage3 bin/virc_stage4`).

## 8. Compatibility

- **Source compatibility:** 100% preserved. All public symbols re-exported.
- **ABI compatibility:** No change to data layouts or calling conventions.
- **Runtime memory safety:** Preserved identical TLSF boundary tag coalescing, pointer validation, and double-free detection.

## 9. Migration

No migration required. Submodule breakdown is an internal compiler refactoring.

## 10. Validation Plan

- `python3 tools/check_module_dependencies.py`
- `python3 tools/sync_virc.py --check`
- `python3 tools/check_pass_architecture.py`
- `python3 tests/cli_contract/runner.py`
- `python3 tests/module/test_module_resolver.py`
- `./run_tests.sh min`
- `cmp bin/virc_stage3 bin/virc_stage4`

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Circular dependency between allocator submodules | Low | Medium | Strict layering: `mmap_core` -> `tlsf_core` -> `slab` -> `verify` -> `alloc` orchestrator |
| Runtime memory allocator regression | Low | High | Bit-identical self-host verification and comprehensive min test suite |

## 12. Rollback Strategy

Restore files via Git and revert to prior checkpoint compiler binary.

## 13. Exit Criteria

- [x] Area 1: `riscv64.vri` refactored into orchestrator + 6 submodules.
- [x] Area 2: `pipeline.vri` refactored into orchestrator + 4 step submodules.
- [x] Area 3: `type_table.vri` and `sem_pass4_types.vri` refactored into orchestrators + 5 submodules.
- [x] Area 4: `alloc.vri` refactored into orchestrator + 5 submodules.
- [x] All 20 new submodules registered in `compiler/module.list`.
- [x] All 7 gates pass cleanly.
- [x] 3-stage self-hosting fixed point verified bit-identical.
- [x] `VIRC-RPT-0023` accepted and `VIRC-ISS-0021` resolved.

## 14. Related Papers

- `VIRC-ISS-0021` — Final compiler modularization across riscv64, driver pipeline, semantic pass 4, and memory allocator.
- `VIRC-RPT-0023` — Final compiler modularization completion report.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial plan creation |
| 2026-10-03 | Implementation completed across all 4 phases, quality gates verified, marked COMPLETED |
