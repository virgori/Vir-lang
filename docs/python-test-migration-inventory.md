# Python Test Tooling Migration Inventory

This document defines the complete, authoritative migration inventory required by
**VIRC-ISS-0050** (Acceptance Criterion 1) and **VIRC-PLN-0029** (Phase 1).

Every Python file currently residing under `tests/` (64 files, 15,897 lines) and
`tools/` (13 files, 5,023 lines) is classified below with its active verification role,
dependencies, and mapped Vir replacement module or non-test classification.

---

## 1. Summary Metrics

| Category | File Count | Line Count | Target Vir Architecture |
|---|---|---|---|
| Contract & Harness Runners | 6 | 2,695 | `tools/vir-test/` native binary |
| Compiler, Optimizer & Codegen Tests | 20 | 7,849 | Native Vir regression suites (`tests/**/*.vri`) |
| LSP Protocol & Client Tests | 21 | 2,677 | `tools/vir-lsp-test/` JSON-RPC stdio client |
| Subsystem & Domain Tests | 17 | 2,676 | Domain native tests (`stdlib/vir/test/vtest.vri`) |
| **Total `tests/`** | **64** | **15,897** | **All migrated to Vir / 0 Python remaining** |
| Verification Gate Tools | 6 | 3,564 | Native Vir toolchain validation binaries |
| Toolchain Build & Bumping Helpers | 5 | 814 | Vir-native build/bump commands (`viron` or CLI) |
| Non-Verification / Historical Scripts | 2 | 645 | Historical archive (excluded from verification path) |
| **Total `tools/`** | **13** | **5,023** | **6 replaced, 5 unified, 2 archived** |

---

## 2. Inventory of Test Suites (`tests/**/*.py`)

### 2.1 Contract & Harness Runners (6 files, 2,695 lines)

| Path | Lines | Frameworks & Patterns | Verification Role | Vir Replacement Target |
|---|---|---|---|---|
| `tests/cli_contract/runner.py` | 1,094 | `unittest`, `subprocess`, `json` | Compiler CLI argument matrix & flags | `tools/vir-test/src/cli/` |
| `tests/matrix_runner.py` | 486 | `subprocess`, `json` | Multi-target compilation matrix | `tools/vir-test/src/matrix/` |
| `tests/perf_contract/test_arena_throughput_contract.py` | 582 | `subprocess`, `json` | Memory arena allocation throughput | `tests/perf_contract/arena_throughput.vri` |
| `tests/perf_contract/test_borrow_checker_scaling.py` | 221 | `subprocess` | Borrow checker NLL polynomial scaling | `tests/perf_contract/borrow_checker_scaling.vri` |
| `tests/perf_contract/test_include_scaling.py` | 262 | `subprocess`, `json` | Preprocessor include depth scaling | `tests/perf_contract/include_scaling.vri` |
| `tests/run_lsp_tests.py` | 50 | `subprocess` | Orchestrator for LSP test suite | `tools/vir-lsp-test/src/main.vri` |

---

### 2.2 Compiler, Optimizer, Lowering & Toolchain (20 files, 7,849 lines)

| Path | Lines | Frameworks & Patterns | Verification Role | Vir Replacement Target |
|---|---|---|---|---|
| `tests/module/test_module_resolver.py` | 208 | `unittest` | CWD-independent module resolution | `tests/module/test_module_resolver.vri` |
| `tests/test_cost_model.py` | 361 | `pytest`, `json` | LIR instruction cost model | `tests/optimizer/test_cost_model.vri` |
| `tests/test_dense_tensor_mutation_contract.py` | 232 | `pytest`, `subprocess` | Tensor element mutation lowering | `tests/tensor/test_dense_tensor_mutation.vri` |
| `tests/test_f32_f64_print.py` | 271 | `subprocess` | Floating-point formatting intrinsic | `tests/codegen/test_f32_f64_print.vri` |
| `tests/test_fusion_passes.py` | 195 | Direct assertions | Kernel and loop fusion passes | `tests/optimizer/test_fusion_passes.vri` |
| `tests/test_m_to_l.py` | 209 | Direct assertions | MIR-to-LIR lowering pass | `tests/lowering/test_m_to_l.vri` |
| `tests/test_narrow_cast_contract.py` | 187 | `unittest`, `subprocess` | Zero-extension unsigned narrow casts | `tests/types/test_narrow_cast.vri` |
| `tests/test_neon_kernels.py` | 238 | Direct assertions | ARM64 NEON vector intrinsics | `tests/backend/test_neon_kernels.vri` |
| `tests/test_opt_pre_and_loop_transforms.py` | 516 | `unittest`, `subprocess` | Pre-loop and George-Appel IRC passes | `tests/optimizer/test_opt_pre_loop.vri` |
| `tests/test_opt_tail_call.py` | 530 | `unittest`, `subprocess` | Tail call optimization in LIR | `tests/optimizer/test_opt_tail_call.vri` |
| `tests/test_phase3.py` | 628 | `pytest`, `json` | Semantic analysis Phase 3 | `tests/compiler/test_phase3.vri` |
| `tests/test_phase7_optimizations.py` | 534 | `pytest` | Optimization pipeline Phase 7 | `tests/optimizer/test_phase7.vri` |
| `tests/test_phase_h.py` | 673 | `pytest`, `json` | High-level WIR lowering Phase H | `tests/lowering/test_phase_h.vri` |
| `tests/test_phase_i.py` | 494 | `pytest` | Mid-level WIR lowering Phase I | `tests/lowering/test_phase_i.vri` |
| `tests/test_phase_j.py` | 734 | `pytest` | Low-level WIR backend Phase J | `tests/backend/test_phase_j.vri` |
| `tests/test_quantized_metadata_regression.py` | 231 | `pytest`, `subprocess` | Q8_0 shape & storage metadata | `tests/tensor/test_quantized_metadata.vri` |
| `tests/test_source_map_spans.py` | 130 | `unittest`, `subprocess` | Source map marker order & spans | `tests/debug/test_source_map_spans.vri` |
| `tests/test_tensor_q8_0_contract.py` | 260 | `subprocess` | Q8_0 packed kernels & dot product | `tests/tensor/test_tensor_q8_0.vri` |
| `tests/test_toolchain_sysroot_contract.py` | 1,105 | `subprocess`, `json` | Sysroot discovery, CWD isolation | `tests/toolchain/test_sysroot_contract.vri` |
| `tests/test_virc_iching_issues_regression.py` | 113 | `subprocess`, `json` | Regression gate for I-Ching issues | `tests/regression/test_virc_iching.vri` |

---

### 2.3 Language Server Protocol (LSP) Tests (21 files, 2,677 lines)

All LSP test files communicate with `bin/vir-lsp --stdio` over JSON-RPC. They are mapped to tests executed by the pure-Vir `tools/vir-lsp-test/` runner:

| Path | Lines | Target LSP Verification Domain | Vir Replacement Target |
|---|---|---|---|
| `tests/test_lsp_initialize.py` | 146 | Lifecycle (`initialize`, `initialized`, capabilities) | `tools/vir-lsp-test/src/suites/initialize.vri` |
| `tests/test_lsp_cancellation.py` | 45 | Request cancellation (`$/cancelRequest`) | `tools/vir-lsp-test/src/suites/cancellation.vri` |
| `tests/test_lsp_checker_equivalence.py` | 87 | Compiler diagnostics vs LSP diagnostics | `tools/vir-lsp-test/src/suites/checker_equiv.vri` |
| `tests/test_lsp_compiler_facts.py` | 217 | Compiler symbol facts & semantic tokens | `tools/vir-lsp-test/src/suites/compiler_facts.vri` |
| `tests/test_lsp_completion_rename_contract.py` | 165 | Code completion & symbol renaming | `tools/vir-lsp-test/src/suites/completion_rename.vri` |
| `tests/test_lsp_cross_file.py` | 57 | Cross-file navigation & definition jump | `tools/vir-lsp-test/src/suites/cross_file.vri` |
| `tests/test_lsp_diagnostic_mapping.py` | 136 | Position mapping and error codes | `tools/vir-lsp-test/src/suites/diagnostics.vri` |
| `tests/test_lsp_document_isolation.py` | 62 | Multi-document state isolation | `tools/vir-lsp-test/src/suites/document_isolation.vri` |
| `tests/test_lsp_features.py` | 383 | Hover, definition, references | `tools/vir-lsp-test/src/suites/features.vri` |
| `tests/test_lsp_focus.py` | 45 | Focused file parsing and telemetry | `tools/vir-lsp-test/src/suites/focus.vri` |
| `tests/test_lsp_import_alias.py` | 54 | Module alias and include hover | `tools/vir-lsp-test/src/suites/import_alias.vri` |
| `tests/test_lsp_in_ref_out.py` | 474 | In/ref/out signature diagnostics | `tools/vir-lsp-test/src/suites/in_ref_out.vri` |
| `tests/test_lsp_member_graph.py` | 61 | Struct/entity member graph | `tools/vir-lsp-test/src/suites/member_graph.vri` |
| `tests/test_lsp_partial_input.py` | 37 | Fragmented / streaming stdin chunks | `tools/vir-lsp-test/src/suites/partial_input.vri` |
| `tests/test_lsp_registry_cwd.py` | 26 | Registry discovery with differing CWD | `tools/vir-lsp-test/src/suites/registry_cwd.vri` |
| `tests/test_lsp_repro_p1_p2.py` | 201 | P1/P2 issue regression scenarios | `tools/vir-lsp-test/src/suites/repro_p1_p2.vri` |
| `tests/test_lsp_repro_turn3.py` | 160 | Complex editing turn regression | `tools/vir-lsp-test/src/suites/repro_turn3.vri` |
| `tests/test_lsp_session_resources.py` | 86 | Memory and fd leak checks per session | `tools/vir-lsp-test/src/suites/resources.vri` |
| `tests/test_lsp_timeout.py` | 36 | Request watchdog and client timeout | `tools/vir-lsp-test/src/suites/timeout.vri` |
| `tests/test_lsp_type_graph.py` | 127 | Type hierarchy and interface navigation | `tools/vir-lsp-test/src/suites/type_graph.vri` |
| `tests/test_lsp_unicode_roundtrip.py` | 72 | UTF-16 code units vs UTF-8 offsets | `tools/vir-lsp-test/src/suites/unicode.vri` |

---

### 2.4 Subsystem, Toolchain & Governance Tests (17 files, 2,676 lines)

| Path | Lines | Frameworks & Patterns | Verification Role | Vir Replacement Target |
|---|---|---|---|---|
| `tests/test_lib_sublib.py` | 396 | `pytest` | Nested module tree resolution | `tests/module/test_lib_sublib.vri` |
| `tests/test_grad_rules_extended.py` | 191 | Direct assertions | Reverse-mode automatic differentiation | `tests/autodiff/test_grad_rules.vri` |
| `tests/test_qir_pipeline.py` | 152 | Direct assertions | Quantum IR pipeline verification | `tests/quantum/test_qir_pipeline.vri` |
| `tests/test_qir_schema.py` | 87 | Direct assertions | Quantum schema token validation | `tests/quantum/test_qir_schema.vri` |
| `tests/test_paper_tool.py` | 125 | `unittest`, `subprocess` | Paper standard schema validation | `tests/governance/test_paper_tool.vri` |
| `tests/test_virc_version_policy.py` | 43 | `subprocess`, `json` | Semantic version CLI format | `tests/toolchain/test_version_policy.vri` |
| `tests/test_virdata.py` | 79 | Direct assertions | Data serialization & buffers | `tests/stdlib/test_virdata.vri` |
| `tests/test_virgrad.py` | 108 | Direct assertions | Autodiff core ops | `tests/stdlib/test_virgrad.vri` |
| `tests/test_virmatrix_kernels.py` | 107 | Direct assertions | Matrix math intrinsics | `tests/stdlib/test_virmatrix.vri` |
| `tests/test_virmem.py` | 53 | Direct assertions | Memory allocators and copy ops | `tests/stdlib/test_virmem.vri` |
| `tests/test_virnn_mlp.py` | 238 | Direct assertions | Neural network MLP training loop | `tests/stdlib/test_virnn_mlp.vri` |
| `tests/test_viron.py` | 662 | `unittest`, `subprocess` | Standalone Viron CLI & packages | `tools/viron/tests/test_viron.vri` |
| `tests/test_viroptim.py` | 61 | Direct assertions | Optimizer algorithms (SGD, Adam) | `tests/stdlib/test_viroptim.vri` |
| `tests/test_virpack.py` | 136 | Direct assertions | Binary packing & unpacking | `tests/stdlib/test_virpack.vri` |
| `tests/test_virpass.py` | 59 | Direct assertions | Compiler pass registration | `tests/stdlib/test_virpass.vri` |
| `tests/test_virplat.py` | 28 | Direct assertions | Platform detection intrinsics | `tests/stdlib/test_virplat.vri` |
| `tests/test_virprof.py` | 151 | Direct assertions | Profiler sampling & call stack | `tests/stdlib/test_virprof.vri` |

---

## 3. Inventory of Verification and Tool Scripts (`tools/*.py`)

| Path | Lines | Role Classification | Description | Vir Replacement / Action |
|---|---|---|---|---|
| `tools/gap_contract_runner.py` | 1,840 | **Verification Gate** | Contract runner executing 293 TSV manifest test rows across 3 suites | Replaced by `tools/vir-test/` |
| `tools/check_module_dependencies.py` | 150 | **Verification Gate** | Enforces module hierarchy and import DAG rules | Replaced by `tools/vir-module-graph/` |
| `tools/check_pass_architecture.py` | 122 | **Verification Gate** | Enforces pass boundary constraints in compiler | Replaced by `tools/vir-pass-check/` |
| `tools/module_graph.py` | 315 | **Verification Gate** | Ingests `module.list` and calculates closure | Replaced by `tools/vir-module-graph/` |
| `tools/paper.py` | 988 | **Verification Gate** | VPS governance CLI (`validate`, `new`, `registry`) | Replaced by native Vir `./paper` CLI |
| `tools/sync_virc.py` | 149 | **Tooling / Deprecated** | Syncs modular compiler sources to generated bundle | Secondary per PLN-0017; port to Vir CLI |
| `tools/build_vir_lsp.py` | 122 | **Toolchain Builder** | Builds `bin/vir-lsp` binary with `virc` | Direct build command or `viron` task |
| `tools/build_viron.py` | 129 | **Toolchain Builder** | Builds `bin/viron` binary with `virc` | Direct build command or `viron` task |
| `tools/bump_vir_lsp_version.py` | 149 | **Version Helper** | Updates version in `vir-lsp` sources | Replaced by native Vir version utility |
| `tools/bump_virc_version.py` | 199 | **Version Helper** | Updates version in compiler sources | Replaced by native Vir version utility |
| `tools/bump_viron_version.py` | 215 | **Version Helper** | Updates version in Viron toolchain | Replaced by native Vir version utility |
| `tools/migrate_huong3.py` | 243 | **Non-Verification Archive** | One-time AST transform script (Historical) | Excluded from verification path / archive |
| `tools/migrate_huong3_phase2.py` | 402 | **Non-Verification Archive** | One-time syntax migration script (Historical) | Excluded from verification path / archive |

---

## 4. Contract Manifests Covered

The native `tools/vir-test/` runner replaces `tools/gap_contract_runner.py` for all three active manifests:

1. `tests/spec_gap_contract/manifest.tsv` (39 tests: generics, precompute, FFI, SIMD, AI, Q8_0)
2. `tests/type_safety_contract/manifest.tsv` (105 tests: borrow, autoderef, entities, tuples, generics)
3. `tests/memory_contract/manifest.tsv` (149 tests: arena allocation, borrow checker scopes, heap, loops)

**Total manifest test rows:** 293 active rows.

---

## 5. Verification Call Sites in `run_tests.sh`

The 10 call sites in `run_tests.sh` to be replaced with native binaries:

1. Line 272: `tools/gap_contract_runner.py` -> `tools/vir-test/vir-test --manifest ...`
2. Line 560: `tests/test_opt_pre_and_loop_transforms.py` -> `tests/optimizer/test_opt_pre_loop`
3. Line 670: `tests/module/test_module_resolver.py` -> `tests/module/test_module_resolver`
4. Line 671: `tools/module_graph.py --root . --entry driver` -> `tools/vir-module-graph/`
5. Line 672: `tools/module_graph.py --root . --entry bundle_entry` -> `tools/vir-module-graph/`
6. Line 736: `tests/test_f32_f64_print.py` -> `tests/codegen/test_f32_f64_print`
7. Line 900: `tests/test_opt_tail_call.py` -> `tests/optimizer/test_opt_tail_call`
8. Line 1300: `tests/test_source_map_spans.py` -> `tests/debug/test_source_map_spans`
9. Line 1505: `tests/test_narrow_cast_contract.py` -> `tests/types/test_narrow_cast`
10. Line 1594: `tests/cli_contract/runner.py` -> `tools/vir-test/vir-test --mode cli`
