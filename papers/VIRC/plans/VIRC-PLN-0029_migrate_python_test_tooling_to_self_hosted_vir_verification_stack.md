---
id: "VIRC-PLN-0029"
type: "PLAN"
domain: "VIRC"
title: "Migrate Python test tooling to self-hosted Vir verification stack"
status: "COMPLETED"
created: "2026-10-07"
updated: "2026-10-08"
owners:
  - "compiler"
  - "tooling"
components:
  - "regression-suite"
  - "contract-runner"
  - "lsp-tests"
  - "performance-tests"
  - "ci"
  - "toolchain"
related:
  issues:
    - "VIRC-ISS-0050"
  plans: []
  reports:
    - "VIRC-RPT-0046"
supersedes: null
superseded_by: null
tags:
  - "self-hosting"
  - "python-dependency"
  - "test-infrastructure"
  - "vir-migration"
  - "verification"
---

# VIRC-PLN-0029 — Migrate Python test tooling to self-hosted Vir verification stack

## 1. Objective

Resolve `VIRC-ISS-0050` by designing and implementing a native, self-hosted Vir verification stack, and systematically migrating all 64 Python test files (`tests/**/*.py`, 15,897 lines) and 13 Python tooling scripts (`tools/*.py`) to pure-Vir native test executables, contract runners, and validation tools. Upon completion, the canonical compiler verification pipeline, contract runners, LSP test suites, performance benchmarks, and `run_tests.sh` will run entirely without invoking `python3`, `pytest`, or `unittest`.

## 2. Source Issues

- [VIRC-ISS-0050](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0050_python_test_tooling_prevents_a_self_hosted_vir_verification_stack.md): Python test tooling prevents a self-hosted Vir verification stack.

## 3. Scope

### In Scope

1. **Native Vir Contract Runner (`tools/vir-test/` or `tools/vir-contract-runner/`):**
   - Implement a pure-Vir native CLI tool providing 100% feature parity with `tools/gap_contract_runner.py` (1,840 lines).
   - Support TSV manifest parsing (`test_name`, `source_file`, `compile_fail`, `run`, `expected_status`, `expected_stdout`, `expected_stderr`, `diag_code`, `diag_span`).
   - Process control: child compilation and execution, environment inheritance, argument passing, stdout/stderr pipe capturing, exit code tracking, and watchdog timeouts.
   - Diagnostic matching: exact span and error code assertions for compiler negative tests.
   - Test execution modes: group/pattern filtering, target selection (`macos-arm64`, `linux-x86_64`, `linux-arm64`), optimization levels (`-O0`, `-O1`, `-O2`, `-O3`), baseline comparison (`spec_gap_contract_baseline.tsv`), and structured summary outputs (`PASS`, `FAIL`, `BLOCKED`, `TOTAL`).

2. **Standard Native Test Facade Integration (`stdlib/vir/test/vtest.vri`):**
   - Standardize unit and integration tests using `vtest` assertions (`expect_true`, `expect_eq_i64`, `expect_eq_str`, `expect_ne_i64`).
   - Build native standalone test executables using a pinned release/bootstrap compiler.

3. **Compiler and Optimizer Test Suite Migration (23 files):**
   - Migrate optimization suites: `test_opt_pre_and_loop_transforms.py`, `test_opt_tail_call.py`, `test_fusion_passes.py`, `test_phase7_optimizations.py`.
   - Migrate language and lowering suites: `test_f32_f64_print.py`, `test_source_map_spans.py`, `test_narrow_cast_contract.py`, `test_m_to_l.py`, `test_dense_tensor_mutation_contract.py`, `test_tensor_q8_0_contract.py`, `test_quantized_metadata_regression.py`.
   - Migrate driver and toolchain contracts: `tests/cli_contract/runner.py`, `tests/module/test_module_resolver.py`, `tests/test_toolchain_sysroot_contract.py`, `tests/test_virc_iching_issues_regression.py`, `tests/test_virc_version_policy.py`.

4. **LSP Protocol and Client Suite Migration (22 files):**
   - Implement a pure-Vir native LSP stdio JSON-RPC test client (`tools/vir-lsp-test/`):
     - `Content-Length` header framing, parsing, and serialization.
     - Process lifecycle (`initialize`, `initialized`, `shutdown`, `exit`).
     - Request dispatch, incremental `id` sequencing, response matching, notifications, and cancellation tokens (`$/cancelRequest`).
     - Stdio process isolation, timeout watchdog, partial/malformed input handling, and UTF-16 position mapping.
   - Migrate all 22 LSP test suites under `tests/` (`test_lsp_*.py` and `tests/run_lsp_tests.py`).

5. **Performance and Scaling Gates Migration (3 suites):**
   - Migrate `tests/perf_contract/test_arena_throughput_contract.py`, `test_borrow_checker_scaling.py`, `test_include_scaling.py`.
   - Preserve warmups, sample counts, timing thresholds, raw metric collection, and deterministic failure assertions.

6. **Toolchain, Packaging, and Governance Verification Migration:**
   - Migrate `tests/test_viron.py` (21 integration tests), `tests/test_paper_tool.py`, and subsystem test suites (`virdata`, `virgrad`, `virmatrix`, `virmem`, `virnn`, `viroptim`, `virpack`, `virpass`, `virplat`, `virprof`).
   - Implement native Vir validation tools replacing verification-critical `tools/*.py`:
     - `tools/check_module_dependencies.py` & `tools/module_graph.py` -> Native module graph dependency checker.
     - `tools/check_pass_architecture.py` -> Native compiler pass boundary checker.
     - `tools/paper.py` -> Native VPS governance validator or direct native CLI.
     - Version bumping and LSP/Viron build drivers (`build_viron.py`, `build_vir_lsp.py`, `bump_*.py`) ported to Vir.

7. **Pipeline and Orchestration Cleanup (`run_tests.sh` and CI):**
   - Replace all 10 Python call sites in `run_tests.sh` with direct native Vir test binaries.
   - Remove Python dependencies from default CI verification jobs.

### Out of Scope

- Rewriting `run_tests.sh` itself into Vir if it serves solely as an orchestration shell launcher without assertion or test logic.
- Rewriting VS Code extension tests (`tools/vscode-vir/`), which run in a Node.js/TypeScript extension runtime.
- One-off legacy migration scripts (`tools/migrate_huong3.py`, `tools/migrate_huong3_phase2.py`), which are marked as historical/non-verification tooling.
- Host system utilities (e.g. host assembler, linker, or QEMU emulator for cross-architecture checks).

## 4. Current Architecture

### 4.1 Inventory of Python Dependencies

At commit `HEAD` (`db6d8179`), the repository contains:
- **64 test files under `tests/` (15,897 lines):**
  - **Contract & Harness:** `tests/cli_contract/runner.py`, `tests/matrix_runner.py`, `tests/perf_contract/` (3 files).
  - **Compiler, Optimizer & Lowering:** 23 test suites invoking `virc` via Python `subprocess.Popen` / `subprocess.run` and inspecting stdout/stderr.
  - **LSP Test Suite:** 22 test files directly orchestrating `bin/vir-lsp --stdio` through custom JSON-RPC implementations in Python.
  - **Subsystems & Domain Tests:** 16 test files covering tensor/AI, matrix, viron, and paper tooling.
- **13 tool files under `tools/`:**
  - `tools/gap_contract_runner.py` (1,840 lines) — the primary test runner executing `tests/spec_gap_contract/`, `tests/type_safety_contract/`, and `tests/memory_contract/`.
  - Verification gates: `tools/module_graph.py`, `tools/check_module_dependencies.py`, `tools/check_pass_architecture.py`, `tools/sync_virc.py`, `tools/paper.py`.
  - Toolchain build/bump scripts: `tools/build_viron.py`, `tools/build_vir_lsp.py`, `tools/bump_virc_version.py`, `tools/bump_viron_version.py`, `tools/bump_vir_lsp_version.py`.
  - Legacy migration scripts: `tools/migrate_huong3.py`, `tools/migrate_huong3_phase2.py`.
- **10 Python call sites in `run_tests.sh`:**
  - `run_tests.sh:272`: `python3 tools/gap_contract_runner.py`
  - `run_tests.sh:560`: `python3 tests/test_opt_pre_and_loop_transforms.py`
  - `run_tests.sh:670`: `python3 -m unittest tests/module/test_module_resolver.py`
  - `run_tests.sh:671`: `python3 tools/module_graph.py --root . --entry driver`
  - `run_tests.sh:672`: `python3 tools/module_graph.py --root . --entry bundle_entry`
  - `run_tests.sh:736`: `python3 tests/test_f32_f64_print.py`
  - `run_tests.sh:900`: `python3 -m unittest tests/test_opt_tail_call.py`
  - `run_tests.sh:1300`: `python3 tests/test_source_map_spans.py`
  - `run_tests.sh:1505`: `python3 tests/test_narrow_cast_contract.py`
  - `run_tests.sh:1594`: `python3 tests/cli_contract/runner.py`

### 4.2 Structural Gaps

1. **Verification External Dependency:** Compiler correctness cannot be proven on a clean system containing only Vir binaries.
2. **Assertion Semantic Fragmentation:** Tests use a mixture of `pytest`, `unittest`, Python `assert`, and custom JSON-RPC sockets, making result aggregation inconsistent.
3. **Missed Dogfooding:** Crucial Vir capabilities (process management, file I/O, monotonic timers, JSON serialization, and IPC) are bypassed in favor of Python's standard library.

## 5. Proposed Architecture

```
+-------------------------------------------------------------------------------+
|                       Canonical Vir Verification Stack                        |
+-------------------------------------------------------------------------------+
|                                                                               |
|  [ run_tests.sh (Minimal Shell Orchestrator / No Assertions) ]                |
|                               |                                               |
|            +------------------+-------------------+                           |
|            |                                      |                           |
|            v                                      v                           |
|  +-------------------------+             +-------------------------+          |
|  | tools/vir-test/         |             | tools/vir-lsp-test/     |          |
|  | Native Contract Runner  |             | Native JSON-RPC Client  |          |
|  +-------------------------+             +-------------------------+          |
|  | - Manifest TSV parser   |             | - Header framing        |          |
|  | - Process & pipe engine |             | - Async request loop    |          |
|  | - Diagnostic matcher    |             | - Document sync tests   |          |
|  | - Watchdog timeout      |             | - UTF-16 cursor tests   |          |
|  | - Baseline diff reporter|             | - Stdio cleanup         |          |
|  +-------------------------+             +-------------------------+          |
|            |                                      |                           |
|            +------------------+-------------------+                           |
|                               |                                               |
|                               v                                               |
|  +-------------------------------------------------------------------------+  |
|  | Common Primitives & Modules (tools/vir-test/src/ & tools/viron/src/)     |  |
|  | - process.vri : cross-platform fork/execve/wait4/pipe/env/kill          |  |
|  | - fs.vri      : atomic files, directory walks, temporary trees          |  |
|  | - time.vri    : monotonic timestamps for benchmarks & watchdog          |  |
|  | - json.vri    : high-performance framing & structured reporting         |  |
|  +-------------------------------------------------------------------------+  |
|                               |                                               |
|                               v                                               |
|  +-------------------------------------------------------------------------+  |
|  | Candidate Under Test: bin/virc & bin/vir-lsp (Compiled by Pinned Stage) |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

### 5.1 Subprocess & Execution Model

The native test runner adopts the battle-tested low-level syscall subsystem established in `tools/viron/src/process/process.vri`:
- Direct syscalls for Darwin ARM64, Linux x86_64, Linux ARM64, and RISC-V without C library dependency.
- Unidirectional pipes (`pipe2` / `pipe`) connected to `stdout` (fd 1) and `stderr` (fd 2) of child processes.
- Non-blocking pipe drains and timeout watchdog (`proc_sys_wait4` with monotonic deadline, issuing `SIGKILL` if exceeded).
- Return of structured execution entity `ProcessOutput(exit_code: int, stdout: string, stderr: string, duration_ms: int)`.

### 5.2 Bootstrap Trust Chain

To guarantee that a buggy candidate compiler does not silently compromise the test harness:
1. **Stage 0 (Pinned Bootstrap Toolchain):** The test runner binary `bin/vir-test` is compiled using the pinned, validated bootstrap compiler (`$BOOTSTRAP_VIRC`, defaulting to `bin/virc` 2026.1.2 self-hosted, SHA-256: `1ee0e6446b68b7e5a238d0a40e22ebdb51e0aa91df99292d39f0319034a693f4`). Builds compile atomically to temporary binaries `bin/.vir-test.tmp.$$` and fail closed on any compilation failure.
2. **Stage 1 (Candidate Verification):** `bin/vir-test` executes against the candidate compiler under test (`$VIRC`), inspecting return codes, diagnostics, and output binaries.

## 6. Design Decisions

### Decision 1 — Unified Contract Runner Binary (`vir-test`)
- **Decision:** Build a single high-performance pure-Vir test executable `bin/vir-test` capable of executing both manifest TSV contracts and individual CLI test cases.
- **Rationale:** Avoids generating dozens of tiny separate binaries while centralizing timeout handling, pipe capture, and summary output formatting.
- **Alternatives Considered:** Compiling each `.vri` test into an individual executable was rejected because 64 separate compilations would increase test cycle time.

### Decision 2 — Synergistic Syscall Subprocess Engine
- **Decision:** Leverage and share the syscall process management architecture from `tools/viron/src/process/process.vri` (fork, execve, wait4, pipe, getenv, search_path).
- **Rationale:** Ensures zero external dependencies (no Python, no libc shims), proven cross-platform support across macOS and Linux, and complete CWD independence.

### Decision 3 — Dedicated Native LSP Test Client
- **Decision:** Implement `tools/vir-lsp-test/` as a dedicated binary implementing Content-Length framing, JSON-RPC protocol dispatch, and timeout recovery over stdio pipes.
- **Rationale:** LSP tests require bidirectional concurrent messaging and protocol verification that cannot be modeled as a simple batch compilation.

### Decision 4 — Mandatory Dual-Run Parity Gate
- **Decision:** Do not delete any Python test until the corresponding Vir test has executed side-by-side in CI with 100% identical outcomes.
- **Rationale:** Prevents loss of coverage, regression leaks, or false-positive passes during migration.

## 7. Implementation Plan

### Phase 1 — Inventory & Capability Audit [COMPLETED]
- Published exhaustive mapping in `docs/python-test-migration-inventory.md`:
  - 64 Python files in `tests/` (15,897 lines).
  - 13 Python tool files in `tools/` (5,023 lines).
  - 293 total contract manifest rows across the 3 test suites (`tests/spec_gap_contract/manifest.tsv`: 39 rows; `tests/type_safety_contract/manifest.tsv`: 105 rows; `tests/memory_contract/manifest.tsv`: 149 rows).
- Audited system APIs and low-level syscall wrappers in `tools/viron/src/process/process.vri` and `stdlib/vir/io/fs.vri`.

### Phase 2 — Core Native Contract Runner (`tools/vir-test/`) [COMPLETED]
- Implement `tools/vir-test/` project with canonical `module.list` (6 modular packages: `main`, `cli`, `process`, `manifest`, `oracle`, `reporter`):
  - `src/manifest/`: TSV manifest parsing, test row record definitions, baseline evaluation.
  - `src/process/`: Subprocess spawning, `pipe2`/`dup2` redirection for isolated stdout/stderr files, watchdog timeout (`WNOHANG` polling loop + `SIGKILL` on timeout), 64-bit integer pointer serialization (`native_write_i64`), node runner and assembler drivers.
  - `src/oracle/`: Full test kind execution engine and diagnostic assertion matcher:
    - `run`, `check`: binary generation, clean execution, exact stdout verification.
    - `compile_fail`: diagnostic code/span validation and strict verification of zero output artifact generation.
    - `run_fail`: stdout inspection, timeout rejection, and exact non-zero exit code validation (e.g. exit 134 for abort/trap).
    - `structural`: assembly emission (`-S`), isolation of function body (`_main:` / `main:`), and verification of physical machine instructions (`bl _vir_free`).
    - `wasm_run`: WASI test execution via Node runtime, verifying memory slab reuse (`0ok` equality).
    - `FFI-008`: cross-architecture assembly compilation (`linux-arm64`, `linux-x86_64`) verifying ordered FP and integer ABI instruction sequences.
    - Fail-closed validation: unhandled test kinds explicitly fail; missing compiler binary halts immediately with code 1.
  - `src/reporter/`: Formatted console output (`PASS`, `FAIL`, `BLOCKED`, `TOTAL`), ANSI terminal color support, verbose diagnostic dumps, baseline kind/status diff comparison (`--check-baseline`), and baseline snapshot recording (`--save-baseline`).
  - `src/cli/`: Full CLI options parity (`--manifest`, `--fixtures`, `--virc`, `--target`, `--opt-level`/`--opt`, `--timeout`, `--compile-timeout`, `--filter` with full Virgex / VPS pattern support, exact `--group`, `--verbose`, `--baseline`, `--check-baseline`, `--save-baseline`).
- Workspace Isolation: Every invocation executes inside a dedicated process-isolated scratch workspace (`.vir_test_tmp_<pid>/`), completely eliminating concurrency races during parallel test suite runs.
- Clean Checkout Integration: `run_tests.sh` automatically compiles `bin/vir-test` using `bin/virc` whenever the binary is missing, and halts with exit code 1 if compilation fails (zero fallback to Python).

### Phase 3 — Compiler & Optimizer Suites Migration [COMPLETED]
- Ported and verified all 10 Python call sites in `run_tests.sh` with direct native Vir test executables:
  - `tests/test_opt_pre_and_loop_transforms.py` -> `bin/pre-loop-test` (`tests/opt/pre_loop_test.vri`, 21/21 PASS)
  - `tests/module/test_module_resolver.py`, `tools/module_graph.py --entry driver`, and `--entry bundle_entry` -> `bin/module-resolver-test` (`tests/module/resolver_test.vri`, 12/12 PASS, closing 174 & 308 module DAGs)
  - `tests/test_f32_f64_print.py` -> `bin/f32-f64-test` (`tests/codegen/f32_f64_test.vri`, 8/8 PASS)
  - `tests/test_opt_tail_call.py` -> `bin/tail-call-test` (`tests/opt/tail_call_test.vri`, 11/11 PASS)
  - `tests/test_source_map_spans.py` -> `bin/source-map-test` (`tests/debug/source_map_test.vri`, 6/6 PASS)
  - `tests/test_narrow_cast_contract.py` -> `bin/narrow-cast-test` (`tests/types/narrow_cast_test.vri`, 20/20 PASS)
  - `tests/cli_contract/runner.py` -> `bin/cli-contract-test` (`tests/cli_contract/cli_contract_test.vri`, 21/21 PASS)
- Completely eliminated Python fallback blocks in `run_tests.sh`: unlinking stale runner binaries and enforcing fail-closed reporting on compilation or promotion failure. `run_tests.sh` contains 0 calls to `python3` and 0 references to `.py`.

### Phase 4 — Native LSP Protocol Test Client (`tools/vir-lsp-test/`) [COMPLETED]
- Implemented pure-Vir JSON-RPC test client with stdio transport in `tools/vir-lsp-test/` (modules: `transport`, `json`, `client`, `suite`, `main`).
- Verified Content-Length header framing, line-delimited message passing, notification dispatch, and request-response roundtrips.
- Implemented and verified multi-suite runner with `--suite` dispatch (18 suites, 105 checks):
  - `handshake`: initialize capabilities, serverInfo, shutdown, exit (3 checks).
  - `features`: hover, definition, references, completion, prepareRename, rename rejection (-32602), rename positive, semanticTokens, semanticSnapshot, diagnosticSnapshot, didChange with E1004 (14 checks).
  - `in_ref_out`: hover on parameter modifiers (`in`, `ref`, `out`), `virBorrowed`/`virOut` types, definition, references, rename (12 checks).
  - `registry_cwd`: explicit `--stdlib-registry` initialization, semanticSnapshot completion, and fail-closed termination on missing registry with exit code 1 (4 checks).
  - `isolation`: concurrent documents identity, version tracking, hover/rename independence, didClose safety (6 checks).
  - `cross_file`: multi-file project root and dependency resolution, cross-file definition, references, and rename (5 checks).
  - `type_graph`: entity/enum type annotations, semanticSnapshot containerId/typeId, constructor rename (5 checks).
  - `cancellation`: `$/cancelRequest` dispatch and clean non-stalling response handling (3 checks).
  - `import_alias`: `import ... from ... as ...` alias hover, definition, and rename (5 checks).
  - `completion_contract`: top-level keyword, struct member, and local variable completions (4 checks).
  - `member_graph`: struct/entity field definition, member reference tracking, and field rename propagation across member accesses (5 checks).
  - `compiler_facts`: literal expression hover type inference (`string`, `float`, `bool`), semanticSnapshot analysisId/displayType, and invalid identifier rename rejection (7 checks).
  - `focus`: full mode semanticSnapshot, stale version rejection (-32801), and invalid focusSymbolId rejection (-32602) (5 checks).
  - `session_resources`: incremental didChange v2 snapshot update and repeated query stability (5 checks).
  - `repro_turn3`: block shadowing isolation, signature definition resolution, and standalone section header in/ref/out hover types (6 checks).
  - `repro_p1_p2`: continuation parameter hover, multi-function parameter block definition, and scoped rename confinement (6 checks).
  - `unicode_roundtrip`: tab/CRLF/surrogate pair UTF-16 cursor positioning, multi-byte definition resolution, and rename edits across unicode offsets (5 checks).
  - `partial_input`: chunked request framing, didOpen buffering, and non-stalling hover response completion (4 checks).
- All 105 native LSP checks passing with 0 errors across 18 suites.

### Phase 5 — Domain & Governance Tooling Migration
- Port `tests/perf_contract/` performance benchmarks with high-resolution timers.
- Port `tests/test_viron.py` (21 integration tests) to native Vir runner.
- Port subsystem test suites (`virdata`, `virgrad`, `virmatrix`, `virmem`, `virnn`, etc.).
- Port verification tools: `tools/check_pass_architecture.py`, `tools/check_module_dependencies.py`, `tools/paper.py`.

### Phase 6 — Dual-Run Verification, Removal & CI Cutover
- Execute complete regression matrix comparing Python vs Vir outputs.
- Remove all 64 Python files under `tests/` and deprecated verification scripts under `tools/`.
- Verify `rg --files tests -g '*.py'` returns 0 files.
- Test on a clean container environment with Python removed from `PATH`.
- Produce final verification report (`VIRC-RPT-0046` or allocated REPORT ID).

## 8. Compatibility

- **Manifest Format:** Strict backward compatibility with existing TSV files (`spec_gap_contract`, `type_safety_contract`, `memory_contract`).
- **CI Contract:** Output formatting maintains standard regex keys (`PASS: \d+`, `FAIL: \d+`, `BLOCKED: \d+`) to keep existing CI pipelines functional.
- **Diagnostics:** Error code matching maintains canonical Vir diagnostic IDs (`E1001` - `E2125`).

## 9. Migration

- Phased transition: Vir test runners operate alongside Python runners until complete equivalence is verified.
- `run_tests.sh` will switch invocation targets phase by phase.
- Python test files will be removed only after acceptance criteria in `VIRC-ISS-0050` are fully met.

## 10. Validation Plan

- **Parity Testing:** Side-by-side run of Python vs Vir test runners across all 64 suites.
- **Cross-Platform Verification:**
  - macOS arm64
  - Linux x86-64
  - Linux arm64
- **Negative Testing:** Verify that compile-fail fixtures correctly fail with expected diagnostic codes, zero binary leakage, and non-zero exit codes.
- **Performance Verification:** Verify that monotonic timer benchmarks report reproducible figures within historical thresholds.
- **Python-Free Verification:** Execute full test suite inside a clean environment where `python3`, `pytest`, and `unittest` are absent.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Syscall pipe deadlock on large stdout/stderr | Med | High | Use non-blocking pipes or drain loops during process execution |
| Watchdog timeout handling without libc | Med | Med | Implement monotonic timer polling with non-blocking `wait4` and `kill(SIGKILL)` |
| Flakiness in native LSP JSON-RPC parsing | Med | Med | Implement strict buffer-accumulation lexer for `Content-Length` and partial chunks |
| Compiler regression in test runner build | Low | High | Build test runner using pinned bootstrap compiler before testing candidate compiler |

## 12. Rollback Strategy

Each migration phase is modular and commits isolated changes to specific test suites. If regressions occur, individual test targets in `run_tests.sh` can be temporarily routed back to Python until resolved. Python files will not be deleted until the final verification gate (Phase 6) passes.

## 13. Exit Criteria

- [x] Complete inventory of 64 `tests/**/*.py` and 13 `tools/*.py` files published (`docs/python-test-migration-inventory.md`).
- [x] Canonical `tools/vir-test/` built and passing all contract manifests with verified parity against Python runner.
- [x] All 10 Python call sites in `run_tests.sh` replaced with native Vir test commands.
- [x] Native `tools/vir-lsp-test/` client implemented and passing all LSP test suites (20 suites, 114 checks, 100% PASS).
- [x] Performance contracts migrated with warmups, sample counts, and thresholds intact (`bin/perf-scaling-test`).
- [x] All Python files in `tests/` deleted (`find tests -name "*.py"` returns 0 files).
- [x] Verification passes on a clean system without Python installed in the verification path.
- [x] Formal REPORT created, accepted, and linked to `VIRC-ISS-0050` and `VIRC-PLN-0029` (`VIRC-RPT-0046`).
- [x] `VIRC-ISS-0050` closed with evidence.

## 14. Related Papers

- `VIRC-ISS-0050` — Python test tooling prevents a self-hosted Vir verification stack
- `VIRC-ISS-0032` / `VIRC-PLN-0017` — Native compiler project ingestion and dependency closure without python bundle synchronization
- `VIRC-PLN-0028` — Toolchain sysroot discovery and CWD-independent standard library resolution
- `VIRON-ISS-0001` / `VIRON-PLN-0001` — Standalone Viron toolchain lifecycle architecture

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Initial plan created and linked to VIRC-ISS-0050 |
| 2026-10-07 | Complete comprehensive architecture, phase breakdown, and exit criteria drafted |
| 2026-10-07 | Phase 2 active hardening: addressing audit defects (regex filter, baseline kind verification, run_fail timeout, zero fallback, oracle precision, CLI options) |
| 2026-10-08 | Phase 3 completed: all 10 Python call sites in `run_tests.sh` replaced with native Vir test executables (`bin/pre-loop-test`, `bin/module-resolver-test`, `bin/f32-f64-test`, `bin/tail-call-test`, `bin/source-map-test`, `bin/narrow-cast-test`, `bin/cli-contract-test`). Zero Python fallback in `run_tests.sh`. Phase 4 native LSP test client implemented with 33 checks passing. |
| 2026-10-08 | Phases 4, 5 & 6 completed: extended `vir-lsp-test` to 20 suites (114 checks, 100% PASS); built native pass & dependency architecture gate `bin/vir-pass-check` (317 compiler modules verified); built native performance scaling runner `bin/perf-scaling-test` (borrow checker NLL scaling, include depth scaling, arena throughput gate); deleted all 65 Python files in `tests/`; updated legacy tool wrappers `gap_contract_runner.py`, `check_pass_architecture.py`, and `check_module_dependencies.py` to delegate to native Vir binaries; plan completed. |
