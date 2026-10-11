---
id: "VIRC-RPT-0046"
type: "REPORT"
domain: "VIRC"
title: "Self-hosted Vir test runner migration and parity verification report"
status: "ACCEPTED"
created: "2026-10-07"
updated: "2026-10-08"
owners:
  - "toolchain"
  - "compiler"
components:
  - "test-runner"
  - "vir-test"
  - "verification"
  - "process-isolation"
related:
  issues:
    - "VIRC-ISS-0050"
  plans:
    - "VIRC-PLN-0029"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "self-hosting"
  - "vir-test"
  - "contract-runner"
  - "zero-fallback"
  - "virgex-filter"
  - "concurrency"
---

# VIRC-RPT-0046 — Self-hosted Vir test runner migration and parity verification report

## 1. Executive Summary

This report documents the verification, audit remediation, and empirical validation of `VIRC-ISS-0050` pursuant to `VIRC-PLN-0029` Phase 2.
The self-hosted native test runner `bin/vir-test` written in Vir v2.0 (`tools/vir-test/src/`) has been systematically tested and hardened against the legacy Python reference runner (`tools/gap_contract_runner.py`), resolving both initial audit findings and verification defects:

1. **Atomic Fail-Closed Rebuild & Staleness Fix**: Fixed the source dependency glob in `run_tests.sh` to track `tools/vir-test/module.list` and core stdlib dependencies (`stdlib/vir/virgex/virgex.vri`, `stdlib/vir/core/vec.vri`). Rebuilding compiles to an isolated temporary binary (`bin/.vir-test.tmp.$$`) and verifies both `chmod +x` and `mv -f` operations. On compilation, permissions, or promotion failure, the temporary artifact is unlinked, execution of stale binaries is strictly prohibited, and the runner fails closed.
2. **Pinned Bootstrap Toolchain Decoupling**: Decoupled the candidate compiler-under-test from the bootstrap runner compiler via `BOOTSTRAP_VIRC="${BOOTSTRAP_VIRC:-$VIRC}"` in `run_tests.sh`. Pinned reference toolchain: `virc` 2026.1.2 self-hosted (SHA-256: `1ee0e6446b68b7e5a238d0a40e22ebdb51e0aa91df99292d39f0319034a693f4`).
3. **Strict Timeout Argument Parsing**: Malformed `--timeout` values (such as `--timeout nope` or trailing non-numeric tokens) are strictly rejected with exit code 2 and Python argparse-identical diagnostics (`gap_contract_runner: error: argument --timeout: invalid float value: 'nope'`), eliminating accidental silent defaults. The subprocess watchdog enforces deadlines using 10ms polling ticks.
4. **Baseline Column Toleration & Duplicate Enforcement**: Baseline verification parses columns 1 (`test_id`), 2 (`kind`), and 3 (`status` delimited by tab), ignoring incidental 4th+ columns in accordance with the Python reference runner (`fields[:3]`), while strictly enforcing duplicate ID rejection.
5. **Official Virgex / VPS Pattern Filter & Zero Custom Regex**: Completely removed the custom hand-rolled regex engine from `tools/vir-test/src/cli/cli.vri`. Integrated canonical stdlib `virgex` (`include virgex`) with pattern compilation performed exactly once before test execution via `virgex.compile`, matching via verified `virgex.isMatch(pat, test_id)`. Resolved borrow/move root causes in `stdlib/vir/core/vec.vri` (restored `ref v: Vec`) and `stdlib/vir/virgex/virgex.vri` (updated matching methods to accept `ref pat: Pattern`), eliminating all E5001 borrow errors. Explicitly updated the CLI contract: `--filter` accepts official Vir Pattern Syntax (VPS) rather than Python `re`. Malformed pattern inputs fail closed with exit code 2.
6. **Empirical Parity with Current Compiler Metrics**: Verified exact ID-for-ID and status-for-status execution across all 293 contract tests matching current compiler 2026.1.2 (284 PASS / 4 FAIL / 5 BLOCKED).

## 2. Source Issues

- **VIRC-ISS-0050** — `Python test tooling prevents a self-hosted Vir verification stack`

## 3. Source Plans

- **VIRC-PLN-0029** — `Migrate Python test tooling to self-hosted Vir verification stack`

## 4. Implementation Summary

The self-hosted test runner was implemented and hardened across 6 native Vir modules and the root test driver:
1. `tools/vir-test/src/cli/cli.vri`: CLI argument parsing, strict fractional timeout conversion to milliseconds (`cli_parse_timeout_ms`), unknown option rejection with exit code 2, official Virgex pattern integration (`include virgex`), fail-closed pattern validation (`vps_tokenize`), and group/filter precedence.
2. `tools/vir-test/src/process/process.vri`: POSIX subprocess harness (`fork`, `execve`, piped file descriptors, PID retrieval) and millisecond watchdog timeouts via `wait4` with 10ms ticks.
3. `tools/vir-test/src/manifest/manifest.vri`: Tab-separated manifest parser, move-free pointer table, and fixture directive extractor.
4. `tools/vir-test/src/oracle/oracle.vri`: Function body isolation (`_main` boundary detection distinguishing `LBB_*` basic block labels), token sequence validation for multi-target ABI conventions (`FFI-008`), and exit code checking.
5. `tools/vir-test/src/reporter/reporter.vri`: Console formatter and two-pass baseline comparator ignoring extra trailing columns while rejecting duplicate IDs and verifying kind and status equality.
6. `tools/vir-test/src/main.vri`: Orchestration loop, move-free unpacked configuration locals, single-compilation Virgex pattern lifecycle (`var filter_pat = virgex.compile(...)`), PID workspace lifecycle, and unconditional per-test artifact cleanup.
7. `run_tests.sh`: Native runner integration with source-staleness auto-rebuild, atomic fail-closed compilation and promotion verification, pinned bootstrap support, and zero Python fallback.

## 5. Changes by Component

### 5.1. CLI Driver (`tools/vir-test/src/cli/cli.vri`)
- Implemented `cli_parse_timeout_ms` with strict decimal validation: parses digits and single decimal dot into integer milliseconds; returns `-1` on any malformed character, multiple dots, or empty digit input.
- Emits argparse-compatible diagnostic `gap_contract_runner: error: argument --<flag>: invalid float value: '<val>'` and exits with code 2 on invalid timeout.
- Removed all 260 lines of hand-rolled regex parsing and matching (`cli_regex_search`, `cli_match_here`, `cli_atom_matches_char`, `cli_match_char_class`, `cli_str_concat_slices`).
- Integrated official `include virgex`; pattern strings are validated using `vps_tokenize(filter as string)` during argument parsing. Any invalid syntax fails closed with `gap_contract_runner: error: argument --filter: invalid Virgex pattern: '<pattern>'` and exits with code 2. Missing arguments exit with code 2.
- Updated `--help` / `-h` description to explicitly declare VPS syntax: `--filter FILTER Virgex pattern filter by test ID (VPS syntax)`.
- Restructured `cli_filter_matches` to accept `ref pat: Pattern`, allowing matching without entity moves or allocations.

### 5.2. Process Subsystem (`tools/vir-test/src/process/process.vri`)
- All string parameters and buffer pointers typed as primitive `int` to ensure zero moves in Vir Pass 8 borrow checking.
- Updated `proc_wait_timeout` to operate on `timeout_ms: int` with 10ms ticks (`max_ticks = timeout_ms / 10`), accurately enforcing sub-second deadlines.
- Captured stdout/stderr streams cleanly unlinked after each test iteration.

### 5.3. Oracles and Verification (`tools/vir-test/src/oracle/oracle.vri`)
- `oracle_check_structural_free`: Distinguishes internal basic block labels (`LBB_*`) from function boundaries (`.globl`, `//`, `_`), properly isolating `_main`.
- `oracle_check_ffi008_arm` and `oracle_check_ffi008_x86`: Enforces ordered register instruction sequences across architectures.
- `oracle_check_exit_code`: Rejects timeout `-999` from passing generic non-zero exit requirements.

### 5.4. Baseline Verification Engine (`tools/vir-test/src/reporter/reporter.vri`)
- Two-pass baseline verification:
  - Pass 1 parses all rows, validates at least 3 fields per row, extracts `b_status` up to the next tab (`\t`) while ignoring trailing 4th+ columns, and tracks seen IDs to reject duplicates with `duplicate baseline id at row <line>: <id>`.
  - Pass 2 verifies missing current results, new results absent from baseline, and exact match on both `kind` and `status`.

### 5.5. Main Loop and Workspace Lifecycle (`tools/vir-test/src/main.vri`)
- Compiles the Virgex filter pattern exactly once before iterating over tests: `var filter_pat = virgex.compile("")`; if `has_filter == 1`, `filter_pat = virgex.compile(filter as string)`.
- Passes `filter_pat` by reference (`ref pat: Pattern`) to `cli_filter_matches`.
- Unpacks `cfg` and `tbl` into local primitive integer variables at the start of `main()`, avoiding entity moves during loop iterations.
- Unconditional per-iteration artifact cleanup unlinking `.bin`, `.stdout`, `.stderr`, `.s`, and `.wasm` before moving to the next test.
- Cleanup on wasm compilation failure explicitly unlinks `wasm_bin`, `test_stdout`, and `test_stderr`.
- Clean directory removal via `proc_rmdir(tmp_dir)` at program completion.

### 5.6. Stdlib Borrow/Move Fixes
- `stdlib/vir/core/vec.vri`: Restored `ref v: Vec` across `vec_reserve`, `vec_push`, `vec_len`, `vec_get`, `vec_set`, and `VecNamespace` methods, eliminating 22 compiler E5001 borrow errors.
- `stdlib/vir/virgex/virgex.vri`: Updated `VirgexNamespace` methods (`isMatch`, `fullMatch`, `search`, etc.) to take `ref pat: Pattern`, allowing pattern reuse across repetitive iterations without consuming the pattern entity. Added token validation in `vps_tokenize` for unrecognized `@` atoms.

### 5.7. Suite Integration (`run_tests.sh`)
- Added source-staleness check comparing timestamps of `tools/vir-test/src/*.vri`, `tools/vir-test/src/*/*.vri`, `tools/vir-test/module.list`, `stdlib/vir/virgex/virgex.vri`, and `stdlib/vir/core/vec.vri` against `bin/vir-test`.
- Atomic compilation to temporary binary `bin/.vir-test.tmp.$$` with fail-closed return: on compilation failure, `chmod` failure, or `mv -f` promotion failure, temporary artifacts are unlinked, old binaries are never executed, and the build aborts immediately.
- Decoupled `BOOTSTRAP_VIRC` from candidate compiler `$VIRC`.
- Zero Python fallback across all test paths.

## 6. Deviations from Plan

The test runner contract for `--filter` was explicitly transitioned from legacy Python `re` syntax to canonical Vir Pattern Syntax (VPS / Virgex), avoiding custom non-standard regex parsers while dogfooding the native standard library.
The native runner relies strictly on:
- `bin/virc` (stage-0 bootstrap compiler)
- POSIX kernel and libc syscalls (fork, execve, wait4, dup2, open, close, unlink, mkdir, rmdir)
- `Node.js` (specifically for WASI Preview 1 tests via `proc_find_node()`; if Node.js is not present on the host system, Wasm tests are accurately reported as `BLOCKED`).

## 7. Verification

### 7.1. Contract Suite Execution
The native test runner was executed across all three official contract manifests under compiler 2026.1.2:
- `tests/spec_gap_contract/manifest.tsv`: 31 PASS / 3 FAIL / 5 BLOCKED (TOTAL 39). Exit 1.
- `tests/type_safety_contract/manifest.tsv`: 104 PASS / 1 FAIL / 0 BLOCKED (TOTAL 105). Exit 1 (matching Python reference runner).
- `tests/memory_contract/manifest.tsv`: 149 PASS / 0 FAIL / 0 BLOCKED (TOTAL 149). Exit 0.
- Total executed: 293 tests (284 PASS, 4 FAIL, 5 BLOCKED).

### 7.2. Audit Finding Remediation and Edge Cases
1. **Atomic Runner Rebuild & Fail-Closed Promotion**:
   Compiled to `bin/.vir-test.tmp.$$` and atomically replaced `bin/vir-test`. Verified that simulated compiler failure or promotion failure (`chmod` / `mv`) unlinks the artifact and aborts immediately with code 1, never running stale binaries. Verified that modifying `tools/vir-test/module.list` or stdlib dependencies triggers automatic rebuild.
2. **Dual CWD Compilation**:
   Successfully compiled `bin/vir-test` from workspace root and from an alternate directory (`tools/`) with 0 errors and 0 warnings.
3. **Pinned Bootstrap Toolchain Decoupling**:
   `run_tests.sh` respects `BOOTSTRAP_VIRC`. Rebuilding using pinned `virc` 2026.1.2 completed cleanly with 0 errors and 0 warnings.
4. **Strict Timeout Rejection**:
   `./bin/vir-test --timeout nope` emitted `gap_contract_runner: error: argument --timeout: invalid float value: 'nope'` and exited with code 2.
5. **Fractional Timeout Execution**:
   `./bin/vir-test ... --timeout 0.2` on a hanging loop fixture terminated in 0.264s total, enforcing sub-second deadlines.
6. **Baseline Extra Column Handling**:
   Baselines containing extra metadata columns evaluated successfully with `Baseline check: PASS`. Duplicate IDs were strictly rejected with exit code 1.
7. **Virgex / VPS Filter Regressions & Fail-Closed Validation**:
   Executed automated regression suite `tests/test_vir_test_filter_regression.sh`:
   - Anchor: `'| MEM $- BOR $- @0!3 |'` matched exactly 28 tests.
   - Alternation: `'| MEM $- :( WASM | STRUCT :) $- @0!3 |'` matched exactly 3 tests.
   - Group repetition: `'| :( MEM $- :)!1 @AZ!3 $- @0!3 |'` matched 43 tests.
   - Literal escape: `'MEM $- HEAP'` matched exactly 8 tests.
   - Alphanumeric atoms: `'| @AZ!3 $- @AZ!3 $- @0!3 |'` matched 43 tests.
   - Fail-closed validation: Malformed patterns (`:( unclosed`, `:) unmatched`, `@unknown_atom`, `!2~1`, `@90`) and missing `--filter` arguments all failed closed with exit code 2.
8. **CLI Help Parity**:
   `./bin/vir-test --help` and `./bin/vir-test -h` print argument usage and options description and exit with code 0.
9. **Workspace Leak Prevention**:
   Executing failing wasm tests unlinked all temporary output files, leaving `.vir_test_tmp_<pid>/` empty for clean removal.
10. **Group 27 Integration**:
    `./run_tests.sh 27` completed with 155/155 PASS (149 native contract tests + 6 unit tests).

## 8. Acceptance Criteria

- [x] Native runner compiles without errors via `bin/virc tools/vir-test/src/main.vri` (0 errors, 0 warnings).
- [x] Complete 6-module architecture registered in `tools/vir-test/module.list`.
- [x] Parity achieved across all 293 contract tests in `tests/*/manifest.tsv` (284 PASS / 4 FAIL / 5 BLOCKED).
- [x] Zero Python fallback on clean checkout or build failure.
- [x] Atomic fail-closed rebuild preventing stale binary execution (verifying compilation, chmod, and mv success).
- [x] Decoupled, pinned bootstrap compiler workflow via `BOOTSTRAP_VIRC`.
- [x] Strict fractional timeout parsing with exit code 2 on malformed input.
- [x] Dual-field baseline check with duplicate ID rejection and extra column tolerance.
- [x] Official Virgex / VPS pattern filter (`virgex.compile`, `virgex.isMatch`) replacing custom regex engine, with fail-closed exit code 2 on invalid patterns.
- [x] CLI `--help` / `-h` parity with exit code 0.
- [x] PID-isolated execution with leak-free cleanup across all failure paths.
- [x] Documented external Node.js dependency for Wasm test harness.

## 9. Known Limitations

- Compilation of `tools/vir-test`, `tools/vir-lsp-test`, `tools/vir-pass-check`, and `tests/perf_contract/scaling_test.vri` requires an existing bootstrap `virc` binary (`BOOTSTRAP_VIRC`).
- Node.js remains documented as the host runtime for executing Wasm Preview 1 linear memory tests.

## 10. Remaining Work

None. All 6 implementation and verification phases specified in `VIRC-PLN-0029` are fully verified and completed.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIRC-ISS-0050` — Source issue
- `VIRC-PLN-0029` — Implementation plan
- `VIRC-SPC-0001` — Vir compiler specification
- `VIR-SPC-0019` — Vir Pattern Syntax (VPS)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Initial verification report documenting Phase 2 audit remediation and parity results. |
| 2026-10-07 | Added remediation and verification for runner staleness, fractional timeouts, duplicate baseline IDs, workspace cleanup, and group/filter precedence. |
| 2026-10-07 | Implemented move-free architecture eliminating 321 E5001 borrow errors; added atomic fail-closed rebuild, pinned bootstrap toolchain, strict timeout arg error (exit 2), baseline 4th column tolerance, and updated metrics. |
| 2026-10-07 | Migrated `--filter` to official Virgex (VPS syntax) using `virgex.compile` and `virgex.isMatch`; resolved stdlib `vec.vri` and `virgex.vri` borrow signatures; implemented fail-closed pattern rejection (exit 2); verified chmod/mv fail-closed rebuild; added 6 filter regressions; verified dual CWD compilation and 284/4/5 contract results. |
| 2026-10-07 | Linked the dedicated VPS syntax specification migrated as `VIR-SPC-0019`. |
| 2026-10-08 | Phase 3 verified: migrated all 10 Python call sites in `run_tests.sh` to native Vir binaries (`pre-loop-test`, `module-resolver-test`, `f32-f64-test`, `tail-call-test`, `source-map-test`, `narrow-cast-test`, `cli-contract-test`). Zero Python fallback in `run_tests.sh`. Phase 4 native LSP test client (`vir-lsp-test`) implemented and passing 105 checks across 18 suites (`handshake`, `features`, `in_ref_out`, `registry_cwd`, `isolation`, `cross_file`, `type_graph`, `cancellation`, `import_alias`, `completion_contract`, `member_graph`, `compiler_facts`, `focus`, `session_resources`, `repro_turn3`, `repro_p1_p2`, `unicode_roundtrip`, `partial_input`). |
| 2026-10-08 | Phases 4, 5 & 6 verified: added `checker_equivalence` and `diagnostic_mapping` LSP suites (20 suites, 114 checks total, 100% PASS); built native pass & dependency architecture gate `bin/vir-pass-check` (317 compiler modules verified); built native performance scaling runner `bin/perf-scaling-test` (borrow checker NLL scaling, include depth scaling, arena throughput gate); decommissioned and deleted all 65 Python files under `tests/` (`find tests -name "*.py"` returns 0); updated legacy tool wrappers `gap_contract_runner.py`, `check_pass_architecture.py`, and `check_module_dependencies.py` to delegate to native Vir binaries; report status advanced to ACCEPTED. |
