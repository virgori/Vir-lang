---
id: "VIRC-ISS-0029"
type: "ISSUE"
domain: "VIRC"
title: "Source include and import preprocessing scales superlinearly during source ingestion"
status: "RESOLVED"
severity: "S2"
priority: "P1"
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
  issues: []
  plans:
    - "VIRC-PLN-0016"
  reports:
    - "VIRC-RPT-0032"
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

# VIRC-ISS-0029 — Source include and import preprocessing scales superlinearly during source ingestion

## 1. Summary

The self-hosted compiler's source-ingestion path is CPU-bound and its text-level
`include`/`import` preprocessing scales superlinearly with the number of source
units. A controlled fixed-size-module corpus grows from 30 ms at 16 includes to
1,579 ms at 256 includes even though expanded bytes grow linearly. The active
implementation repeatedly scans the complete evolving source buffer and
allocates/copies another complete buffer for each directive.

The user-visible delay is currently easy to misclassify as file I/O. On the
audited macOS ARM64 checkout, cached raw reads are negligible relative to
compiler CPU time, while the phase telemetry reports `durationNs: null` and the
modern UI prints `unavailable`. This ISSUE covers both the superlinear source
preprocessor and the missing phase-level observability required to verify its
repair.

## 2. Context

Audit baseline:

- revision: `e1fc2d54773b83a6be684ec6ab20f403faf0a215` with the current dirty
  working tree preserved;
- compiler: `virc 4.2.0 (self-hosted)`;
- compiler SHA-256:
  `060f6cdee554f98d30a02cdda020dc7c7b16554ce7be3d8beb74adc9bb3a07db`;
- host: macOS ARM64;
- canonical frontend owner:
  `compiler/src/main/driver/pipeline/step_frontend.vri`;
- include/import owners: `compiler/src/main/include_expander.vri` and
  `compiler/src/main/import_expander.vri`;
- source-map owner: `compiler/src/frontend/source_manager.vri`;
- runtime read owner: `compiler/src/rt/io.vri`.

The compiler groups source reading, UTF-8 validation, sanitization, module
expansion and source-map construction ahead of lexing. The JSON and modern UI
have phase records, but the audited binary cannot provide their durations.

## 3. Expected Behavior

- Reading, preprocessing, lexing and parsing MUST expose independent usable
  durations on a supported host so that disk I/O is not conflated with CPU
  text processing.
- For fixed-size unique modules, source preprocessing SHOULD grow approximately
  with total physical input plus final expanded output rather than with the
  product of directive count and the evolving output size.
- A physical module SHOULD NOT be opened and decoded repeatedly after its
  canonical identity has already been resolved in the same compile session.
- Source-origin markers, include/import diagnostics, canonical module identity,
  cycle detection and IDE source mapping MUST remain semantically unchanged.

## 4. Actual Behavior

`expand_includes_text` and `expand_imports_text` restart a full-source search for
every directive. Each processed directive then calls `text_splice_at`, which
allocates a new buffer and copies the prefix, inserted module and suffix byte by
byte. This causes cumulative work to increase faster than the final expanded
source size.

The main read path itself performs a bounded 64 KiB read loop for known-size
files. The larger observed latency is CPU-heavy frontend work, but
`--timings` cannot identify the exact phase because all `durationNs` values are
`null` and the modern renderer emits `unavailable`.

## 5. Reproduction

Generate 256 fixed-size comment-only modules and roots containing increasing
numbers of quoted includes:

```bash
python3 -c 'from pathlib import Path
root=Path("/private/tmp/virc_include_scaling"); root.mkdir(exist_ok=True)
for i in range(256):
    (root/f"m{i:03d}.vri").write_text((f"# module {i:03d} padding 0123456789abcdef\n")*128)
for count in (16,32,64,128,256):
    lines=[f"include \"m{i:03d}.vri\"" for i in range(count)]
    lines += ["func main:", "    out 0", "end."]
    (root/f"root_{count}.vri").write_text("\n".join(lines)+"\n")'
```

Run three warm-cache measurements per size:

```bash
for count in 16 32 64 128 256; do
    for repeat in 1 2 3; do
        ./bin/virc "/private/tmp/virc_include_scaling/root_${count}.vri" \
            --check --timings --color=never
    done
done
```

For the real compiler bundle and raw cached-read comparison:

```bash
/usr/bin/time -p ./bin/virc compiler/generated/virc.vri \
    --check --timings --color=never
/usr/bin/time -p sh -c \
    'for i in 1 2 3 4 5 6 7 8 9 10; do dd if=compiler/generated/virc.vri of=/dev/null bs=1m 2>/dev/null; done'
```

## 6. Evidence

### Include-scaling corpus

| Includes | Expanded bytes | Median compile time | Growth from prior size |
|---:|---:|---:|---:|
| 16 | 82,093 | 30 ms | baseline |
| 32 | 163,981 | 59 ms | 1.97x |
| 64 | 327,757 | 143 ms | 2.42x |
| 128 | 655,470 | 456 ms | 3.19x |
| 256 | 1,310,830 | 1,579 ms | 3.46x |

Expanded bytes stay almost exactly linear while the time ratio worsens with
each doubling. By contrast, a pre-expanded comment-dominated flat-source
control measured 30, 47, 82, 152 and 291 ms at 256 KiB, 512 KiB, 1 MiB, 2 MiB
and 4 MiB respectively. The 256-include corpus is therefore more than ten
times slower than the larger 2 MiB flat control.

### Real compiler bundle and raw reads

`compiler/generated/virc.vri` contains 3,416,741 bytes, 84,484 lines, 356
`# @vir_source` markers and 623,523 lexer tokens. Two completed `--check` runs
reported 10.50 and 10.60 seconds real time, 10.25 and 10.27 seconds user time,
and 0.17 and 0.18 seconds system time. Ten cached `dd` reads of the same file
(about 34 MiB total) completed in 0.03 seconds real time. This does not measure
cold-storage latency, but it does rule out cached kernel read throughput as the
dominant cost in the reproduced run.

### Active source evidence

- `virc_step_frontend` reads and validates the root file at
  `compiler/src/main/driver/pipeline/step_frontend.vri:20-48`, then performs
  sanitization, expansion and source-map construction at lines 49-121.
- `read_file_str` uses one size query and a 64 KiB bounded read loop at
  `compiler/src/rt/io.vri:247-301`.
- `expand_includes_text` calls `text_find_include` again from the start of the
  current source on every iteration and splices each result at
  `compiler/src/main/include_expander.vri:889-972`.
- `expand_imports_text` follows the same repeated search/splice structure at
  `compiler/src/main/import_expander.vri:858-993`.
- `text_splice_at` allocates `total + 1` bytes and copies the complete prefix,
  insertion and suffix at `compiler/src/main/include_expander.vri:333-379`.
- `text_ascii_sanitize` allocates and copies a full source-sized buffer at
  `compiler/src/main/include_expander.vri:431-544`.
- `sm_build_from_source` scans the expanded source for markers, performs a
  linear file lookup per new marker, and then performs another complete pass to
  build line starts at `compiler/src/frontend/source_manager.vri:83-134` and
  `:347-453`.
- The active clock path returns an unavailable duration when the Darwin clock
  setup fails at `compiler/src/cli/cli_ui.vri:150-206`; the audited JSON emitted
  `durationNs: null` for Reading, Preprocess, Lexer, Parser and Semantic.

A five-second early-process stack sample contained 4,157 runnable main-thread
samples inside the stripped `virc` image and no blocking file-read stack. Since
the binary has no symbols, the sample confirms CPU residency but is not used to
assign cost to an individual Vir function.

## 7. Scope

### Affected

- root source ingestion and UTF-8 validation;
- text-level include and import discovery, resolution, deduplication and splice;
- source-origin marker and line-start construction;
- compiler and IDE paths that reuse the same frontend preprocessing functions;
- CLI/JSON phase timing used to diagnose frontend latency.

### Not affected / Unknown

- Correctness of include/import resolution was not found to regress in this
  audit.
- Cold-cache storage performance, network filesystems and non-Darwin hosts were
  not measured.
- Import-only scaling was established by source inspection but does not yet
  have an independent committed benchmark corpus.
- The 10.5-second full compiler result includes lexer, parser and semantic work;
  exact attribution remains unknown until phase timing is repaired.
- Peak RSS, allocation count and total copied bytes are not currently exposed.

## 8. Impact

Large modular projects pay increasing source startup cost before meaningful
semantic or backend work begins. The issue penalizes self-hosting, repeated IDE
analysis and dependency-heavy builds, and encourages use of large pre-expanded
bundles as a performance workaround. Missing phase timings also directs
optimization effort toward "disk I/O" even when the reproduced workload is
CPU-bound.

## 9. Preliminary Analysis

- **CONFIRMED:** Each include/import iteration performs a fresh source search;
  each splice allocates and copies a complete replacement buffer.
- **CONFIRMED:** The fixed-size include corpus exhibits worsening 1.97x, 2.42x,
  3.19x and 3.46x time growth while expanded bytes double.
- **CONFIRMED:** The audited CLI emits no usable per-phase duration.
- **OBSERVED:** Warm-cache raw reads are negligible relative to the full
  compiler check, whose time is overwhelmingly user CPU rather than system CPU.
- **OBSERVED:** Flat pre-expanded source scales approximately linearly over
  256 KiB through 4 MiB.
- **HYPOTHESIS:** Replacing repeated full-buffer search/splice with one parsed
  dependency worklist and an append-oriented builder will remove the dominant
  superlinear term.
- **HYPOTHESIS:** Canonical-ID lookup before physical read, plus a per-session
  content cache, will eliminate redundant opens and decoding in duplicate and
  diamond graphs.
- **HYPOTHESIS:** A keyed source-file index will avoid the marker-count squared
  behavior of `sm_register_file` in large generated bundles.
- **NOT_VERIFIED:** The relative cost of sanitization, include/import expansion,
  source-map construction and lexing in the full compiler bundle.
- **NOT_VERIFIED:** Equivalent scaling and clock behavior on Linux, x86-64,
  RISC-V and WASM hosts.

## 10. Acceptance Criteria

- [x] A committed deterministic performance corpus covers flat controls and
  16/32/64/128/256-module include and import graphs with fixed module size,
  including duplicate and diamond dependency cases.
- [x] Deterministic counters expose physical opens, bytes read, bytes scanned,
  bytes copied, full-buffer traversals and source-map file lookups separately
  from wall time.
- [x] For the fixed-size unique-module corpus, doubling module count causes no
  more than 2.5x growth in deterministic preprocessing work at every measured
  step, with a documented tighter target toward linear growth.
- [x] Canonically identical modules are physically read and decoded at most
  once per compile session, including duplicate and diamond graphs.
- [x] Supported native hosts emit non-null session and phase durations for
  Reading, Preprocess, Lexer, Parser and Semantic in JSON; the modern UI renders
  the same durations rather than `unavailable`.
- [x] Reading, UTF-8 validation, preprocessing and source-map construction have
  separate observable accounting, so kernel I/O is not conflated with CPU text
  work.
- [x] The 256 KiB through 4 MiB flat-source control does not regress by more
  than 20% from the recorded median baseline on the same reference host and
  compiler build procedure.
- [x] Include/import canonical identity, cycle detection, exported-symbol
  validation, source-origin diagnostics and IDE virtual-file behavior retain
  focused positive and negative contract coverage.
- [x] `python3 tools/check_module_dependencies.py`, CLI contracts, focused
  module/IDE contracts, generated-source synchronization, self-host fixed point
  and `git diff --check` pass.
- [x] An accepted REPORT records before/after deterministic counters, wall-time
  medians, allocation/peak-memory evidence, supported-host timing evidence and
  any remaining follow-up ISSUEs.

## 11. Related Papers

### Issues

- None linked at triage time.

### Plans

- [VIRC-PLN-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0016_linear_source_ingestion_preprocessing_and_frontend_phase_observability.md)

### Reports

- [VIRC-RPT-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0032_linear_source_ingestion_preprocessing_and_frontend_phase_observability_report.md)

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from source audit, controlled include/flat scaling corpora, cached-I/O comparison and CLI timing inspection |
| 2026-10-04 | Linked VIRC-PLN-0016 |
| 2026-10-04 | Resolved with linear streaming preprocessor, canonical module cache, Darwin clock repair, and verified in VIRC-RPT-0032 |
