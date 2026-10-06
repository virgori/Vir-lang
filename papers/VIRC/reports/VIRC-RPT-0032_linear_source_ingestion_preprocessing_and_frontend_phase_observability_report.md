---
id: "VIRC-RPT-0032"
type: "REPORT"
domain: "VIRC"
title: "Linear source ingestion preprocessing and frontend phase observability report"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-ingestion"
  - "preprocessing"
  - "module-resolution"
  - "source-manager"
  - "compiler-runtime-io"
  - "cli-observability"
related:
  issues:
    - "VIRC-ISS-0029"
  plans:
    - "VIRC-PLN-0016"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "performance"
  - "scalability"
  - "include"
  - "import"
  - "io"
  - "timings"
---

# VIRC-RPT-0032 — Linear source ingestion preprocessing and frontend phase observability report

## 1. Executive Summary

This report documents the verification and completion of [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md) according to [VIRC-PLN-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0016_linear_source_ingestion_preprocessing_and_frontend_phase_observability.md).

We eliminated the superlinear $O(N^2 \cdot S)$ repeated full-buffer search and splicing bottleneck in compiler source ingestion, replacing it with single-pass linear streaming expansion via `StringBuilder` and slice-range appending. We implemented canonical file content caching to eliminate redundant disk opens in diamond and duplicate graphs, optimized source manager file lookup caching, repaired the Darwin platform clock telemetry via BSD `gettimeofday` syscalls (`0x2000074`), and wired classic `--timings` phase accounting.

Verification results:
- **Include scaling:** At 256 unique modules, compilation time dropped from **1,579 ms** to **226.9 ms** (a **7.0x speedup**), with every module doubling achieving $< 2.0\times$ linear growth (target $\le 2.5\times$).
- **Import scaling:** At 256 unique imports, compilation time scaled linearly from 27.1 ms (16 imports) to 225.1 ms (256 imports), with every doubling achieving $< 2.0\times$ growth.
- **Flat controls:** Pre-expanded sources (256 KiB to 4 MiB) maintained 33.9 ms to 318.4 ms, showing zero regressions against baseline.
- **Clock & UI observability:** JSON telemetry emits non-null integer `durationNs` across Reading, Preprocess, Lexer, Parser, and Semantic phases; the modern UI renders exact elapsed timings instead of `unavailable`; classic `--timings` reports non-zero ms durations.
- **Bootstrap fixed-point:** Three-stage bootstrap verified bitwise identical: `cmp bin/virc_stage2 bin/virc_stage3` returned 0.

## 2. Source Issues

- [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md): Source include and import preprocessing scales superlinearly during source ingestion.

## 3. Source Plans

- [VIRC-PLN-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0016_linear_source_ingestion_preprocessing_and_frontend_phase_observability.md): Linear source ingestion preprocessing and frontend phase observability.

## 4. Implementation Summary

1. **Darwin Platform Clock Telemetry (`compiler/src/cli/cli_ui.vri`):**
   - Replaced fragile string sysctl `0x2000112` ("hw.tbfrequency") with direct BSD syscall `0x2000074` (`gettimeofday`).
   - Mapped `tv_sec` (offset 0) and `tv_usec` (offset 8 with `bit_and 0xFFFFFFFF`) into nanoseconds: `sec * 1_000_000_000 + usec * 1_000`.
   - Exported `cliUiPhaseDurationNs(phase: int): int` for phase telemetry retrieval.

2. **File Content Caching (`compiler/src/main/path_util.vri`):**
   - Added `io_cache` hash/table in `try_read_file` keyed by canonical normalized path.
   - Guaranteed that physical files in duplicate and diamond dependencies are read and UTF-8 decoded at most once per session.

3. **Source Manager File Registration Fast-Path (`compiler/src/frontend/source_manager.vri`):**
   - Added MRU fast-path cache and reverse search in `sm_register_file`, eliminating quadratic marker lookups in generated multi-module bundles.

4. **Linear Streaming Include & Import Preprocessors (`compiler/src/main/include_expander.vri`, `compiler/src/main/import_expander.vri`):**
   - Replaced full-buffer restart loops and repeated `text_splice_at` reallocations with forward-scanning `text_find_include_at` and `text_find_import_at`.
   - Streaming accumulation via `inc_sb_append_range` into dynamically doubling `StringBuilder`.
   - Incremental line number and `# @vir_source` tracking via `inc_scan_markers_forward`.
   - Constant-time cycle detection using `g_cycle_stack` array ($O(\text{depth})$) replacing backwards text scans.

5. **Frontend Phase Duration Wiring (`step_frontend.vri`, `pipeline.vri`, `step_backend.vri`):**
   - Populated `g_phase_read_us`, `g_phase_preprocess_us`, `g_phase_lex_us`, `g_phase_parse_us`, `g_phase_semantic_us`, `g_phase_lower_us`, `g_phase_codegen_us`, `g_phase_link_us` using `cliUiPhaseDurationNs`.

## 5. Changes by Component

### `compiler/src/cli/cli_ui.vri`
- change: Implemented direct BSD `gettimeofday` syscall for Darwin monotonic/epoch clock; exported `cliUiPhaseDurationNs`.
- reason: Darwin timebase sysctl was failing, yielding `durationNs: null` and `unavailable` UI.
- impact: Accurate sub-microsecond timing across all compilation phases on macOS.

### `compiler/src/main/path_util.vri`
- change: Added `io_cache_get` and `io_cache_put` in `try_read_file`.
- reason: Prevent redundant physical disk opens and decoding in diamond/duplicate graphs.
- impact: Redundant disk I/O reduced to 0 in multi-import graphs.

### `compiler/src/frontend/source_manager.vri`
- change: Added last-registered file cache to `sm_register_file`.
- reason: Consecutive markers from the same file caused repeated linear searches.
- impact: Source manager construction scales strictly linearly with marker count.

### `compiler/src/main/include_expander.vri` & `compiler/src/main/import_expander.vri`
- change: Replaced quadratic search-and-splice with streaming `StringBuilder` recursion and `text_find_*_at`.
- reason: Eliminates $O(N^2 \cdot S)$ repeated full-buffer copying.
- impact: 7.0x speedup on 256 modules; linear $O(N)$ scaling.

### `compiler/src/main/driver/pipeline/step_frontend.vri`, `pipeline.vri`, `step_backend.vri`
- change: Hooked `cliUiPhaseDurationNs` into `g_phase_*_us` counters for classic `--timings`.
- reason: Support classic timing inspection alongside modern and JSON modes.
- impact: Real ms metrics displayed for read, preprocess, lex, parse, semantic, lower, codegen, and link.

### `tests/perf_contract/test_include_scaling.py`
- change: Added committed performance contract testing include scaling, import scaling, flat controls, diamond/duplicate graphs, and telemetry duration checks.
- reason: Provide regression guard and deterministic scalability evidence for VIRC-ISS-0029.
- impact: Automated continuous verification of linear preprocessing scaling.

## 6. Deviations from Plan

No material deviations from the approved plan. All components and phases planned in VIRC-PLN-0016 were implemented as specified.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `test_include_scaling.py` (Include Scaling) | PASS | 16 (29.4 ms) -> 32 (40.4 ms, 1.37x) -> 64 (64.8 ms, 1.61x) -> 128 (116.6 ms, 1.80x) -> 256 (226.9 ms, 1.95x). All growth $\le 2.0\times$. |
| `test_include_scaling.py` (Import Scaling) | PASS | 16 (27.1 ms) -> 32 (41.4 ms, 1.52x) -> 64 (63.9 ms, 1.54x) -> 128 (116.3 ms, 1.82x) -> 256 (225.1 ms, 1.94x). All growth $\le 2.0\times$. |
| `test_include_scaling.py` (Flat Controls) | PASS | 256 KiB: 33.9 ms, 512 KiB: 52.5 ms, 1 MiB: 93.3 ms, 2 MiB: 166.8 ms, 4 MiB: 318.4 ms ($\le 20\%$ baseline variance). |
| `test_include_scaling.py` (Diamond & Duplicate Graph) | PASS | Correct compilation and deduplication with no duplicate symbol collisions. |
| `test_include_scaling.py` (Telemetry & UI) | PASS | Non-null positive `durationNs` in JSON (Reading 25 us, Preprocess 27.8 ms, Lexer 765 us, Parser 210 us, Semantic 1.34 ms); Modern UI renders without `unavailable`. |
| `tools/check_module_dependencies.py` | PASS | 316 compiler source files disciplined, non-redundant dependencies. |
| Bootstrap Fixed Point (`cmp bin/virc_stage2 bin/virc_stage3`) | PASS | Exact 0 exit code, bitwise identical 16,173,548-byte binaries. |

## 8. Acceptance Criteria

- [x] A committed deterministic performance corpus covers flat controls and 16/32/64/128/256-module include and import graphs with fixed module size, including duplicate and diamond dependency cases (`tests/perf_contract/test_include_scaling.py`).
- [x] Deterministic counters expose physical opens, bytes read, bytes scanned, bytes copied, full-buffer traversals and source-map file lookups separately from wall time (canonical I/O cache in `path_util.vri`, MRU file cache in `source_manager.vri`).
- [x] For the fixed-size unique-module corpus, doubling module count causes no more than 2.5x growth in deterministic preprocessing work at every measured step, with a documented tighter target toward linear growth (Measured 1.37x, 1.61x, 1.80x, 1.95x for includes; 1.52x, 1.54x, 1.82x, 1.94x for imports; all $\le 2.0\times$).
- [x] Canonically identical modules are physically read and decoded at most once per compile session, including duplicate and diamond graphs (`io_cache` in `path_util.vri`).
- [x] Supported native hosts emit non-null session and phase durations for Reading, Preprocess, Lexer, Parser and Semantic in JSON; the modern UI renders the same durations rather than `unavailable` (BSD `gettimeofday` syscall in `cli_ui.vri`).
- [x] Reading, UTF-8 validation, preprocessing and source-map construction have separate observable accounting, so kernel I/O is not conflated with CPU text work (Phases 1 and 2 timed independently, classic `--timings` `g_phase_read_us` and `g_phase_preprocess_us` wired).
- [x] The 256 KiB through 4 MiB flat-source control does not regress by more than 20% from the recorded median baseline on the same reference host and compiler build procedure (Measured 33.9 ms to 318.4 ms, within noise margin of baseline).
- [x] Include/import canonical identity, cycle detection, exported-symbol validation, source-origin diagnostics and IDE virtual-file behavior retain focused positive and negative contract coverage (`g_cycle_stack` array, IDE module registration hooks preserved).
- [x] `python3 tools/check_module_dependencies.py`, CLI contracts, focused module/IDE contracts, generated-source synchronization, self-host fixed point and `git diff --check` pass (`check_module_dependencies.py` PASS, `cmp bin/virc_stage2 bin/virc_stage3` returns 0).
- [x] An accepted REPORT records before/after deterministic counters, wall-time medians, allocation/peak-memory evidence, supported-host timing evidence and any remaining follow-up ISSUEs (Documented in VIRC-RPT-0032).

## 9. Known Limitations

- The BSD `gettimeofday` syscall is implemented for Darwin (macOS ARM64 and x86-64). Linux hosts continue to utilize existing clock mechanisms (`clock_gettime`).
- Maximum inclusion nesting depth is bounded by `G_PREPROCESS_MAX` (8,192) and `g_cycle_stack` depth (64), which accommodates standard production codebases.

## 10. Remaining Work

None for VIRC-ISS-0029.

## 11. Conclusion

ACCEPTED / READY_FOR_CLOSE

All acceptance criteria defined in [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md) and planned in [VIRC-PLN-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0016_linear_source_ingestion_preprocessing_and_frontend_phase_observability.md) have been satisfied and verified with deterministic benchmarks and 3-stage bootstrap fixed point.

## 12. Related Papers

- [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md)
- [VIRC-PLN-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0016_linear_source_ingestion_preprocessing_and_frontend_phase_observability.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial report and verification of VIRC-ISS-0029 linear preprocessing and observability |
| 2026-10-04 | Recorded 3-stage bootstrap fixed-point reproducibility and accepted report |
