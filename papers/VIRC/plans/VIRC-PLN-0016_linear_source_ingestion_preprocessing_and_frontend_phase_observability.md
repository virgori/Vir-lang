---
id: "VIRC-PLN-0016"
type: "PLAN"
domain: "VIRC"
title: "Linear source ingestion preprocessing and frontend phase observability"
status: "COMPLETED"
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
  - "cli-observability"
related:
  issues:
    - "VIRC-ISS-0029"
  plans: []
  reports:
    - "VIRC-RPT-0032"
supersedes: null
superseded_by: null
tags:
  - "performance"
  - "scalability"
  - "include"
  - "import"
  - "timings"
  - "source-manager"
---

# VIRC-PLN-0016 — Linear source ingestion preprocessing and frontend phase observability

## 1. Objective

Eliminate the superlinear $O(N^2 \cdot S)$ include/import preprocessing bottleneck in the self-hosted compiler frontend, establish linear single-pass streaming source expansion with canonical module caching, optimize source-map marker registration in `source_manager.vri`, and repair platform clock telemetry on Darwin in `cli_ui.vri` to achieve fine-grained, accurate phase observability across Reading, Preprocessing, Lexing, Parsing, and Semantic analysis.

## 2. Source Issues

- [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md): Source include and import preprocessing scales superlinearly during source ingestion (scaling from 30 ms at 16 includes to 1,579 ms at 256 includes; telemetry reporting `durationNs: null` and `unavailable`).

## 3. Scope

### In Scope

1. **Darwin Platform Clock Telemetry (`compiler/src/cli/cli_ui.vri`):**
   - Repair `cliClockReset()` and `cliClockNowNs()` on macOS ARM64 and x86-64 by calling BSD syscall `0x2000074` (`gettimeofday(buf, NULL)`) directly, deriving integer monotonic/epoch nanoseconds (`sec * 1_000_000_000 + usec * 1_000`).
   - Eliminate the failing string-based sysctl `0x2000112` ("hw.tbfrequency") call.
   - Ensure `durationNs` is non-null in JSON telemetry and the modern UI prints real elapsed times rather than `unavailable`.
   - Populate `g_phase_*_us` for classic `--timings` mode.

2. **Linear Include and Import Preprocessing (`compiler/src/main/include_expander.vri`, `import_expander.vri`):**
   - Replace full-buffer rescanning from offset 0 (`text_find_include`, `text_find_import`) and repeated full-buffer reallocation/byte-by-byte copying (`text_splice_at`) with forward cursor scanning and streaming append into a dynamically sized accumulator buffer.
   - Eliminate quadratic backwards rescanning from `inc_locate_marker_before` and `check_active_cycle` by tracking current source file/line numbers incrementally during forward scan and maintaining an explicit call stack array for active inclusion cycles.
   - Implement an in-memory canonical module content cache (`inc_key` -> pre-read, pre-sanitized text) to ensure identical physical modules are opened, read, and UTF-8 validated at most once per compilation session, completely eliminating redundant disk I/O in diamond and duplicate dependency graphs.

3. **Frontend Phase Separation and Deterministic Accounting (`compiler/src/main/driver/pipeline/step_frontend.vri`):**
   - Add discrete telemetry instrumentation separating physical file reading, UTF-8 validation, include/import expansion, and source-map construction.
   - Track deterministic operation counters: physical opens, bytes read, bytes scanned, bytes copied, buffer traversals, and source-map lookups.

4. **Source Manager Indexing (`compiler/src/frontend/source_manager.vri`):**
   - Optimize `sm_build_from_source` and `sm_register_file` with fast-path MRU cache / bucket lookup to prevent quadratic string scanning over registered files when processing bundles with hundreds of `# @vir_source` markers.

5. **Deterministic Performance Benchmarking and Verification (`tests/test_virc_issue_0029_include_scaling.py`):**
   - Commit deterministic benchmark test suite covering 16, 32, 64, 128, 256 includes, diamond/duplicate module graphs, and flat controls (256 KiB - 4 MiB).
   - Verify scaling factor $\le 2.5\times$ per doubling of unique modules (tighter linear target).
   - Ensure flat controls do not regress by $>20\%$.

6. **Self-Host Bootstrap and Paper Governance:**
   - Synchronize compiler sources via `python3 tools/sync_virc.py`.
   - Achieve 3-stage bootstrap fixed-point (`cmp bin/virc_stage2 bin/virc_stage3` returns 0).
   - Create verification report `VIRC-RPT-0032`, advance `VIRC-ISS-0029` to `RESOLVED`, update paper registry and validate papers.

### Out of Scope

- Modifying the Vir language specification, grammar, or syntax for `include` or `import`.
- Modifying AST, MIR, LIR, register allocation, or machine code generation backends.
- Changing `# @vir_source` or `# @vir_mod_*` marker formatting contracts expected by IDE or error reporters.

## 4. Current Architecture

1. **Clock Telemetry Failure:**
   - In `compiler/src/cli/cli_ui.vri:153-171`, `cliClockReset()` passes the string `"hw.tbfrequency"` to `syscall6(0x2000112, ...)`. In Darwin BSD, syscall 274 (`__sysctl`) requires an integer MIB array pointer (`[CTL_HW, HW_TBFRQ]`), not a C string. The syscall returns an error code, leaving `g_ui_clockFrequency = 0`.
   - In `cliClockNowNs()`, line 189 tests `if g_ui_clockFrequency <= 0 do out 0 - 1 end`. Consequently, Darwin systems always return `-1` (clock unavailable), forcing `durationNs: null` in JSON output and `unavailable` in the modern UI.
   - Classic `--timings` globals (`g_phase_read_us`, `g_phase_preprocess_us`, etc.) are initialized to 0 in `pipeline.vri` but are never assigned values by `step_frontend.vri`, causing `--timings` to print zeros for early phases.

2. **Quadratic Include/Import Preprocessing:**
   - In `compiler/src/main/include_expander.vri:889-972`, `expand_includes_text` runs a loop up to `G_PREPROCESS_MAX`:
     ```vir
     let at = text_find_include(source)
     ...
     source = text_splice_at(source, at, end_at, wrapped_body)
     ```
   - For every single directive:
     - `text_find_include` scans from byte 0 to the directive index `at`.
     - `inc_locate_marker_before` scans from byte 0 to `at` to find the enclosing file and line number.
     - `check_active_cycle` scans from byte 0 to `at` parsing all `# @vir_mod_start` and `# @vir_mod_end` markers to reconstruct the active inclusion stack.
     - `text_splice_at` allocates a new buffer of size `current_size + insertion_size` and performs three byte-by-byte loops copying prefix `[0..at]`, inserted body, and suffix `[end_at..current_size]`.
   - For $N$ modules of size $S$, cumulative work scales as $\sum_{i=1}^N i \cdot S = O(N^2 \cdot S)$. At $N=256$, over 165 MB of text is re-copied and scanned byte-by-byte, expanding preprocessing time from 30 ms (16 includes) to 1,579 ms (256 includes).
   - In `import_expander.vri:858-993`, `expand_imports_text` follows the identical quadratic pattern.

3. **Redundant Physical I/O on Duplicate/Diamond Modules:**
   - In `include_expander.vri:920`, `read_include_source(iname)` is called before checking whether `g_inc_has(inc_key)` is true. In diamond dependencies (module A includes C, module B includes C), module C is physically opened, read from disk, and UTF-8 validated again when processing B, only to be discarded in line 957 for `# [include duplicate: ...]`.

4. **Source Manager Registration:**
   - In `compiler/src/frontend/source_manager.vri:83-95`, `sm_register_file` performs a linear loop over all registered files for every `# @vir_source` marker encountered in `sm_build_from_source`.

## 5. Proposed Architecture

```
                       Source Ingestion & Preprocessing
                     
  [ Input Path ]
        │
        ▼ (Single open & read)
  ┌─────────────────────────────────────────────────────────────┐
  │ Physical File Read & UTF-8 Check (Phase 1: Reading)        │
  │ Telemetry: physical_opens += 1, bytes_read += src_len       │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼ (Phase 2: Preprocess)
  ┌─────────────────────────────────────────────────────────────┐
  │ Module Content Cache: canonical_id -> pre-sanitized text    │
  │ Diamond / Duplicate lookups return cached copy in O(1)      │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Linear Forward Scanner & Streaming Append Builder           │
  │ • Scan source forward with cursor pos: 0 -> len             │
  │ • Incremental file / line tracking (O(1) per line)          │
  │ • Active cycle stack array: [root, mod1, ...] (O(depth))    │
  │ • Append non-directive chunks + wrapped bodies to builder   │
  │ • Zero full-buffer rescanning; zero full-buffer resplicing  │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Source Manager Marker Registration                          │
  │ • sm_register_file with MRU cache / fast path lookup        │
  └─────────────────────────────────────────────────────────────┘
```

1. **Linear Append Builder:**
   - Preprocess text in a forward-scanning pass. Text prior to directives is appended directly to a growable builder.
   - When an `include` directive is encountered, the included file is recursively expanded directly into the builder, followed by resumption of the parent file from the directive end position.
   - Total bytes copied and scanned is $O(\text{final output size})$, achieving linear scaling $O(N \cdot S)$.

2. **In-Memory Canonical Module Cache:**
   - Keyed by `canonical_id`, caching the pre-read, pre-sanitized string.
   - Duplicate includes/imports consult this cache or `g_inc_has` to emit duplicate comments or shims immediately without disk I/O or redundant UTF-8 validation.

3. **Incremental Line/Marker & Cycle Tracking:**
   - Maintain `cur_file` and `cur_line` during forward scanning.
   - Maintain `cycle_stack` as an array of active module IDs (`vir_alloc(64 * 8)`), checking for cycles in $O(\text{depth})$ rather than rescanning the output text.

4. **Darwin Monotonic / Wall Clock via `gettimeofday`:**
   - In `cli_ui.vri`, invoke `syscall3(0x2000074, g_ui_clockBuffer, 0, 0)` on Darwin. Read 8-byte `tv_sec` and 8-byte `tv_usec`. Calculate total nanoseconds as `sec * 1_000_000_000 + (usec and 0xFFFFFFFF) * 1_000`.

## 6. Design Decisions

### Decision 1: Direct `gettimeofday` Syscall vs. Mach Ticks Sysctl on Darwin

- **Decision:** Use BSD syscall `0x2000074` (`gettimeofday`) passing the scratch buffer as the first parameter (`tp`) and `0, 0` for `tzp` and unused args.
- **Rationale:** `gettimeofday` is universally available across all Darwin kernel versions and architectures (ARM64 and x86-64) without requiring Mach port lookups or integer MIB sysctl arrays. Its microsecond precision ($\pm 1\,\mu\text{s}$) is more than sufficient for phase timing and telemetry.
- **Alternatives Considered:**
  - Calling `mach_absolute_time()`: Requires Mach trap or Libsystem binding not currently linked into pure-syscall compiler stubs.
  - Calling `__sysctl` with `[CTL_HW, HW_TBFRQ]`: Fragile across macOS virtual machines and containerized runners.
- **Trade-offs:** `gettimeofday` is wall-clock based, which can theoretically step if system clock changes during compilation, but for local compilations spanning milliseconds to seconds, elapsed difference is monotonic and accurate.

### Decision 2: Recursive Worklist Streaming vs. Multi-Pass Segment Splice

- **Decision:** Implement forward-scanning recursive stream expansion for includes and imports into a dynamically grown output builder.
- **Rationale:** An include tree is naturally depth-first. Streaming directly into an accumulator eliminates all intermediate string allocations and whole-buffer copies.
- **Alternatives Considered:**
  - Cursor-based in-place splice: Splicing into a single buffer still requires shifting trailing text rightward on each insert.
  - Token-level AST preprocessing: Parsing AST before include expansion would require AST-level module linking, which contradicts Vir's text-level `# @vir_source` and `# @vir_mod_*` specification contracts.
- **Trade-offs:** Recursion depth corresponds to include nesting depth. Since max include nesting is bounded by `G_PREPROCESS_MAX` and typical nesting is $< 20$ frames, recursion on the call stack is safe and minimal.

### Decision 3: Canonical Module Content Cache

- **Decision:** Introduce a per-session hash/lookup cache mapping `canonical_id` to cached pre-read module text.
- **Rationale:** Resolving module canonical identity is cheap; re-reading from disk and decoding UTF-8 on diamond dependencies is wasteful and violates acceptance criterion 4.
- **Alternatives Considered:**
  - Caching raw file descriptors: Unnecessary overhead; module bodies are already kept in memory for the duration of compilation.
- **Trade-offs:** Slightly higher peak memory for large unique module sets, but negligible since expanded text already retains all unique module bodies.

### Decision 4: MRU Fast-Path in `sm_register_file`

- **Decision:** Add a 1-entry most-recently-used (MRU) cache (`last_reg_path`, `last_reg_id`) and small secondary bucket in `source_manager.vri`.
- **Rationale:** Consecutive `# @vir_source` markers in generated bundles alternate heavily between the same module and the parent module. An MRU cache resolves over 90% of file lookups in $O(1)$ without any list traversal.

## 7. Implementation Plan

### Phase 1 — Telemetry Clock & Observability Repair
- **Files:** `compiler/src/cli/cli_ui.vri`, `compiler/src/main/driver/pipeline/step_frontend.vri`, `compiler/src/semantic/diagnostics/session.vri`
- **Changes:**
  - Update `cliClockReset()` and `cliClockNowNs()` on Darwin to use `syscall3(0x2000074, buf, 0, 0)`.
  - Ensure `durationNs` is non-null in JSON output and elapsed time renders in modern UI.
  - Populate `g_phase_*_us` in `step_frontend.vri` and `pipeline.vri` when `g_phase_timings == 1`.
  - Add deterministic counters and phase duration breakdown for Reading, UTF-8 check, Preprocessing, and Source-map construction.
- **Expected Result:** `./bin/virc --timings` prints real non-zero durations for Reading and Preprocessing; `--json` outputs integer `durationNs`.

### Phase 2 — Linear Forward Include Expansion & Module Caching
- **Files:** `compiler/src/main/include_expander.vri`, `compiler/src/main/module_resolver.vri`
- **Changes:**
  - Implement forward-scanning include expander with dynamic append builder.
  - Implement incremental line and marker tracking, replacing `inc_locate_marker_before`.
  - Maintain active cycle stack array, replacing `check_active_cycle`.
  - Add in-memory module cache in `module_resolver.vri` / `include_expander.vri`.
- **Expected Result:** 16 to 256 includes scale linearly; diamond/duplicate modules read disk at most once.

### Phase 3 — Linear Import Expansion & Source Manager Indexing
- **Files:** `compiler/src/main/import_expander.vri`, `compiler/src/frontend/source_manager.vri`
- **Changes:**
  - Mirror linear forward-scanning architecture in `import_expander.vri`.
  - Add MRU fast-path in `sm_register_file`.
- **Expected Result:** Import preprocessing scales linearly; source manager registration is fast.

### Phase 4 — Benchmarking, Contract Testing & Flat-Source Control
- **Files:** `tests/test_virc_issue_0029_include_scaling.py`, `tests/cli_contract/runner.py`
- **Changes:**
  - Add automated scaling test suite verifying $\le 2.5\times$ growth per doubling of includes (16, 32, 64, 128, 256).
  - Verify diamond and duplicate dependencies perform exactly 1 physical read.
  - Verify flat controls (256 KiB - 4 MiB) do not regress by $>20\%$.
  - Run all existing CLI and module contract suites.
- **Expected Result:** All tests pass green.

### Phase 5 — Compiler Synchronization, 3-Stage Bootstrap & Governance
- **Files:** `tools/sync_virc.py`, `papers/VIRC/plans/VIRC-PLN-0016_*.md`, `papers/VIRC/issues/VIRC-ISS-0029_*.md`, `papers/VIRC/reports/VIRC-RPT-0032_*.md`
- **Changes:**
  - Run `python3 tools/sync_virc.py`.
  - Compile stage1 -> stage2 -> stage3 with codesign.
  - Verify fixed-point `cmp bin/virc_stage2 bin/virc_stage3` returns 0.
  - Generate report `VIRC-RPT-0032`, advance statuses, validate papers with `./paper validate`.
- **Expected Result:** Clean fixed-point, clean paper validation.

## 8. Compatibility

- **Source Compatibility:** 100% compatible. No language syntax, keyword, or grammar changes.
- **Marker Compatibility:** `# @vir_source` and `# @vir_mod_*` marker strings, formats, and line-mappings remain bit-for-bit identical to current compiler expectations.
- **IDE Compatibility:** `ideCaptureResolvedModule` and `ide_register_include` / `ide_register_module` hooks remain fully intact and are invoked identically.
- **CLI/JSON Compatibility:** Output format maintains existing JSON schema version 1, now populating valid integers for `durationNs`.

## 9. Migration

No migration required. All source files, project configurations, and build scripts function without changes.

## 10. Validation Plan

1. **Clock Verification:**
   - Execute `./bin/virc <file> --check --timings` and `./bin/virc <file> --ui=modern --check`.
   - Verify `durationNs` is an integer $> 0$ and UI displays non-zero durations.
2. **Deterministic Scaling Verification:**
   - Run reproduction corpus (16, 32, 64, 128, 256 includes).
   - Assert preprocessing time and bytes copied grow $\le 2.5\times$ per doubling.
3. **Module Caching Verification:**
   - Run diamond dependency test (A -> C, B -> C).
   - Verify module C is physically opened and read exactly once.
4. **Flat-Source Regression Test:**
   - Compile flat source controls (256 KiB, 512 KiB, 1 MiB, 2 MiB, 4 MiB).
   - Verify compilation time does not regress by $> 20\%$.
5. **Contract & Regression Suite:**
   - Run `python3 tools/check_module_dependencies.py`.
   - Run `python3 tests/cli_contract/runner.py`.
   - Run `./run_tests.sh`.
6. **3-Stage Bootstrap Fixed-Point:**
   - Execute `tools/sync_virc.py`, build stages, verify `cmp bin/virc_stage2 bin/virc_stage3`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Include order or line mapping discrepancy in nested diamond includes | Low | Medium | Preserve depth-first traversal and `# @vir_source` emission rules; test with complex existing compiler bundle. |
| Memory usage growth in dynamic append builder | Low | Low | Geometric doubling buffer ensures at most $2\times$ memory overhead, far less than old repeated $N$-buffer allocations. |
| Incompatible `gettimeofday` return code on non-standard macOS sandbox | Low | Medium | Check return value; if non-zero, fall back to safe unavailable sentinel `-1`. |

## 12. Rollback Strategy

Revert changes to `compiler/src/cli/cli_ui.vri`, `compiler/src/main/include_expander.vri`, `compiler/src/main/import_expander.vri`, `compiler/src/frontend/source_manager.vri`, and `compiler/src/main/driver/pipeline/step_frontend.vri`, and re-run `python3 tools/sync_virc.py` to restore the previous compiler frontend ingestion behavior.

## 13. Exit Criteria

- [ ] Deterministic performance benchmark committed covering flat controls, 16..256 includes, and diamond/duplicate cases.
- [ ] Physical opens and reads occur at most once per canonical module per session.
- [ ] Preprocessing scaling factor $\le 2.5\times$ per doubling of unique modules.
- [ ] Darwin host emits non-null session and phase durations in JSON, and modern UI renders real durations.
- [ ] Flat controls (256 KiB - 4 MiB) do not regress by $>20\%$.
- [ ] 3-stage self-host bootstrap achieves bit-identical fixed-point (`cmp bin/virc_stage2 bin/virc_stage3`).
- [ ] Report `VIRC-RPT-0032` accepted and `./paper validate` passes.

## 14. Related Papers

### Issues

- [VIRC-ISS-0029](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0029_source_include_and_import_preprocessing_scales_superlinearly_during_source_inges.md)

### Plans

- None.

### Reports

- [VIRC-RPT-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0032_linear_source_ingestion_preprocessing_and_frontend_phase_observability_report.md)

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial plan created and drafted for VIRC-ISS-0029 |
| 2026-10-04 | Completed all implementation phases, verified with VIRC-RPT-0032 |
