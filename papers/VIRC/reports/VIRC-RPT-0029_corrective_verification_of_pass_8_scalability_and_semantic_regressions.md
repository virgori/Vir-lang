---
id: "VIRC-RPT-0029"
type: "REPORT"
domain: "VIRC"
title: "Corrective verification of Pass 8 scalability and semantic regressions"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-07"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow-analysis"
  - "non-lexical-lifetimes"
  - "compiler-performance"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0026"
    - "VIRC-ISS-0028"
  plans:
    - "VIRC-PLN-0012"
    - "VIRC-PLN-0013"
  reports:
    - "VIRC-RPT-0028"
supersedes: "VIRC-RPT-0028"
superseded_by: null
tags:
  - "corrective-verification"
  - "borrow-checker"
  - "pass8"
  - "performance"
  - "semantic-regression"
  - "self-hosting"
---

# VIRC-RPT-0029 — Corrective verification of Pass 8 scalability and semantic regressions

## 1. Executive Summary

This report supersedes `VIRC-RPT-0028`. Independent re-verification found that
the initial accepted report overclaimed strict linearity and dynamic indexing,
used wall-clock timing as its only effective oracle, tested only `-O0` and
`-O2`, described two differently named stage artifacts as bit-identical, and
missed two semantic regressions.

The corrective implementation now:

- rejects owner use after a projection move (`MEM-BOR-027`);
- handles a nested shadow binding without falsely keeping an outer borrower
  live across `await` (`MEM-BOR-028`);
- dynamically resizes Pass 8 hash maps and maintains vector indices through
  every hot mutation, including swap-remove;
- exposes deterministic Pass 8 operation counters under `--borrow-stats`;
- gates six consecutive workload sizes through `N=1024` using both operation
  growth and wall time;
- passes all 149 memory contracts at each of `-O0`, `-O1`, `-O2`, and `-O3`;
- proves exact self-host fixed point when generations target the same canonical
  output path;
- preserves move invalidation across nested functions via iterative BFS
  function collection, preventing AST recursion loop clobbering;
- resolves four compiler use-after-move defects uncovered by the repaired
  collection during self-hosting (`io.vri`, `type_expr.vri`, `json.vri`);
- verifies bit-identical fixed-point self-host compiler image at version 2026.1.2.

The verified independent named-borrow corpus is compatible with `O(N log N)`;
this report does not claim strict `O(N)` for every Pass 8 workload. Projection
partitioning and a dedicated loop-state complexity corpus are tracked by
`VIRC-ISS-0028`.

## 2. Source Issues

- `VIRC-ISS-0026` — borrow checker NLL/state super-quadratic growth.
- `VIRC-ISS-0028` — linked phase-2 projection and loop scalability follow-up.

## 3. Source Plans

- `VIRC-PLN-0012` — original implementation plan.
- `VIRC-PLN-0013` — corrective audit, implementation, and verification plan.

## 4. Implementation Summary

1. Replaced fixed 256-bucket maps with 75%-load dynamically resized maps.
2. Stored the current box-vector index in each map node and maintained it on
   push, set, pop, truncate, and swap-remove.
3. Removed the unsound exact-root move shortcut and retained projection-aware
   overlap checking.
4. Made block liveness collection shadow-aware for current and nested lexical
   declarations.
5. Replaced borrower release vector scans with indexed removal.
6. Added AST, NLL, hash-byte, map-probe, rehash, overlap, and release counters.
7. Strengthened the performance contract to require deterministic counters,
   consecutive doublings, and independent wall/operation ceilings.
8. Added semantic-only `check` fixtures to the strict contract runner.
9. Converted `pass8_collect_funcs` to an explicit BFS queue worklist to prevent
   register clobbering during nested function AST traversal.
10. Corrected declaration scope registration ordering in `pass8_walk_decl`.
11. Repaired compiler self-host use-after-move defects in `compiler/src/rt/io.vri`
    (`write_file_bytes`), `compiler/src/frontend/parser/stmt_decl/type_expr.vri`
    (`parse_type_expr_string`), and `compiler/src/semantic/diagnostics/json.vri`
    (`pass10CaptureDiagnostics`).
12. Bumped compiler version to `2026.1.2` (`last_completed_issue: "VIRC-ISS-0026"`).

## 5. Changes by Component

### `compiler/src/semantic/borrow/context.vri`

- change: dynamically resized hash representation and maintained vector index;
- reason: fixed buckets and unindexed removal invalidated the claimed bound;
- impact: expected constant-time named lookup/removal with amortized rehashing.

### `compiler/src/semantic/borrow/moves.vri` and `loans.vri`

- change: correctness-first path overlap and indexed exact borrower release;
- reason: exact-root lookup accepted use of an owner after moving a field;
- impact: restored move semantics while removing independent-root release scans.

### `compiler/src/semantic/borrow/nll.vri`

- change: lexical shadow tracking in reverse block liveness collection;
- reason: a nested declaration with the same source name was attributed to the
  outer named borrow;
- impact: no false borrow-across-await diagnostic for the registered regression.

### `compiler/src/semantic/sem_pass8_borrow.vri` and driver arguments

- change: hidden deterministic `--borrow-stats` instrumentation;
- reason: complexity must not be inferred from wall time alone;
- impact: no normal-output change unless explicitly requested.

### Tests and generated source

- added `MEM-BOR-027` and `MEM-BOR-028`;
- extended `tools/gap_contract_runner.py` with semantic `check` kind;
- strengthened `tests/perf_contract/test_borrow_checker_scaling.py`;
- synchronized `compiler/generated/virc.vri` from canonical modules.

### `compiler/src/semantic/borrow/funcs.vri`

- change: iterative breadth-first worklist for `pass8_collect_funcs`;
- reason: recursive AST traversal clobbered loop registers, skipping function
  bodies in outer modules and causing use-after-move checks to be bypassed;
- impact: robust collection of all module functions without register corruption.

### `compiler/src/semantic/borrow/walk_decl.vri`, `walk_call.vri`, `walk_func.vri`

- change: ensure decl scope registration precedes RHS evaluation and parameter moves;
- reason: shadowed declarations or forward-referenced decls could miss invalidation checks;
- impact: 15 reopened entity-move contracts correctly reject with `E5001`.

### Compiler self-host fixes (`io.vri`, `type_expr.vri`, `json.vri`)

- change: eliminated real use-after-move patterns in compiler sources;
- reason: Pass 8 function collection fixes uncovered genuine compiler move violations;
- impact: clean fixed-point compilation of `compiler/src/entry.vri`.

## 6. Deviations from Plan

- The original plan expected a strict linear claim. The evidence supports the
  stated `O(N log N)` envelope instead.
- Difference-of-two timing was retained only as diagnostic output. Discrete
  rehash points make it unsuitable as the primary asymptotic oracle.
- Projection-heavy overlap and loop dependency-chain scaling were separated
  into `VIRC-ISS-0028`; correctness fallbacks remain active.

## 7. Verification

### Final compiler performance gate

Command:

```sh
python3 tests/perf_contract/test_borrow_checker_scaling.py \
  --virc bin/virc --repeats 3 --time-metric median --assert-scaling \
  --max-ratio 2.8 --max-op-ratio 2.5
```

| N | Borrow ms | Control ms | Wall growth | Borrow operations | Operation growth |
|---:|---:|---:|---:|---:|---:|
| 32 | 22.17 | 21.08 | — | 16,850 | — |
| 64 | 30.73 | 29.25 | 1.39x | 37,186 | 2.21x |
| 128 | 51.48 | 48.46 | 1.67x | 90,672 | 2.44x |
| 256 | 100.86 | 91.75 | 1.96x | 209,554 | 2.31x |
| 512 | 227.95 | 200.50 | 2.26x | 450,549 | 2.15x |
| 1024 | 594.39 | 515.72 | 2.61x | 970,043 | 2.15x |

Result: `ALL SCALING GATES PASSED`. Counter results were identical across the
warm-up and all measured repetitions.

### Correctness and repository gates

| Gate | Result | Evidence |
|---|---|---|
| Full memory contract `-O0` | PASS | 149/149, 0 failed, 0 blocked |
| Full memory contract `-O1` | PASS | 149/149, 0 failed, 0 blocked |
| Full memory contract `-O2` | PASS | 149/149, 0 failed, 0 blocked |
| Full memory contract `-O3` | PASS | 149/149, 0 failed, 0 blocked |
| CLI contract | PASS | 43/43 |
| Pass architecture | PASS | all registered orchestrators clean |
| Module dependencies | PASS | 316 compiler source files clean |
| Generated source sync | PASS | `tools/sync_virc.py --check` identical |
| Python syntax | PASS | performance and gap runners compile |
| Diff whitespace | PASS | `git diff --check` |

### Self-host fixed point

Stage 1 built Stage 2 and Stage 2 built Stage 3 from the same synchronized
`compiler/generated/virc.vri`; each reported 15,769,928 bytes of machine code.
The normally named files differ at one byte because the embedded output name
contains `stage2` versus `stage3`.

To remove that input difference, both compiler generations emitted the same
canonical path `/private/tmp/virc_fix_canonical`. The two complete files were
byte-identical and both had SHA-256:

```text
1a3cd87c7b7449005a24d486c83692f3d84872ed3e2961df189159c5f608a2f6
```

Stage 3 was promoted to `bin/virc` before the final performance and CLI gates.

### Post-acceptance 4.2.0 release promotion

After closure, the user authorized a minor compiler release bump. Canonical
version metadata and CLI baselines were updated from `4.1.0` to `4.2.0`, the
generated compiler bundle was resynchronized, and `bin/virc` was replaced by
the final self-hosted 4.2.0 image.

Two successive 4.2.0 generations emitted the same canonical path and were
byte-identical with SHA-256:

```text
d82e70df0d21330835d70623ac0a7259114b33985a21fb6b54508520fe269752
```

The full compiler source build completed in 33.81, 33.95, and 33.87 seconds
across the three release-bootstrap generations. The 4.2.0 performance corpus
again passed through `N=1024`; median named-borrow compile time ranged from
22.93 ms to 598.28 ms and deterministic operation growth remained at or below
2.44x per doubling.

### Post-reopening verification and self-host fixed point (2026-10-07)

Following the 2026-10-06 reopening of `VIRC-ISS-0026` due to 15 entity-move
negative contracts emitting artifacts across `-O0..-O3`, root-cause analysis
revealed that deep AST recursion in `pass8_collect_funcs` clobbered loop registers
and caused function declarations in outer modules to be skipped. Additionally,
`pass8_walk_decl` registered declaration scopes after evaluating expressions,
missing invalidation checks.

The 2026-10-07 corrective fixes replaced `pass8_collect_funcs` recursion with an
explicit iterative BFS worklist (with `vec_free_rt` lifecycle cleanup), corrected
scope registration order, and fixed parameter kind conversions. During fixed-point
self-hosting, the repaired collection immediately caught four real use-after-move
violations in compiler sources:
- `compiler/src/rt/io.vri` (`write_file_bytes`): accessed `f.fd` after `file_write_bytes(f, ...)` moved `f`;
- `compiler/src/frontend/parser/stmt_decl/type_expr.vri` (`parse_type_expr_string`): repeated `tok_lex(cur_tok)` calls moving `cur_tok`;
- `compiler/src/semantic/diagnostics/json.vri` (`pass10CaptureDiagnostics`): redundant `sb_free(first)` after `first` was moved into `sb_to_string(first)`.

After repairing these defects, full post-reopening verification was completed:

#### 1. Reopened negative contracts

All 15 reopened entity-move contracts were verified across all optimization
levels using `tools/gap_contract_runner.py`:

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --opt-level=<level> \
  --filter "^(MEM-BOR-(012|026|027|LOOP-(001|002|003|004|005|006|007|009|010|012|013)|EDGE-007))$"
```

Result: 15/15 PASS at each of `-O0`, `-O1`, `-O2`, and `-O3` (all correctly
rejected with `E5001` and produced no binary artifacts).

#### 2. Full memory contract suite

```sh
python3 tools/gap_contract_runner.py --manifest tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --opt-level=-O0
python3 tools/gap_contract_runner.py --manifest tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --opt-level=-O1
python3 tools/gap_contract_runner.py --manifest tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --opt-level=-O2
python3 tools/gap_contract_runner.py --manifest tests/memory_contract/manifest.tsv --fixtures tests/memory_contract --opt-level=-O3
```

Result: 149/149 PASS across `-O0`, `-O1`, `-O2`, and `-O3` (0 failed, 0 blocked).

#### 3. Compiler version bump, cleanup, and synchronization

Per `compiler/VERSIONING.md`, the internal compiler version was bumped for `VIRC-ISS-0026`:

```sh
python3 tools/bump_virc_version.py --bump-internal VIRC-ISS-0026
```

- `compiler/version.json`: bumped to `2026.1.2`, `last_completed_issue: "VIRC-ISS-0026"`;
- `compiler/src/semantic/borrow/funcs.vri`: freed BFS worklist (`vec_free_rt(queue)`) on return;
- `compiler/generated/virc.vri`: synchronized from canonical sources via `tools/sync_virc.py`;
- `python3 tests/test_virc_version_policy.py`: PASS (`virc 2026.1.2 (self-hosted)`);
- `python3 tools/bump_virc_version.py --check`: PASS;
- `python3 tools/sync_virc.py --check`: PASS.

#### 4. Auditable fixed-point self-host bootstrap chain

Starting compiler: `virc 2026.1.2` (prior image SHA-256: `ebb2197bf060c4c02c98df41161ac8955025eef115aabf5f35b0e50499755fa8`, size: 17,910,031 bytes).

1. Stage 1 build:
   `bin/virc compiler/src/entry.vri -o bin/virc_stage1`
   - Size: 17,910,031 bytes
   - SHA-256: `1ee0e6446b68b7e5a238d0a40e22ebdb51e0aa91df99292d39f0319034a693f4`

2. Stage 2 build:
   `bin/virc_stage1 compiler/src/entry.vri -o bin/virc_stage2`
   - Size: 17,910,031 bytes
   - SHA-256: `1ee0e6446b68b7e5a238d0a40e22ebdb51e0aa91df99292d39f0319034a693f4`
   - `cmp bin/virc_stage1 bin/virc_stage2`: 100% bit-identical.

3. Promotion and verification:
   `cp bin/virc_stage2 bin/virc`
   `bin/virc compiler/src/entry.vri -o bin/virc_stage3`
   - Size: 17,910,031 bytes
   - SHA-256: `1ee0e6446b68b7e5a238d0a40e22ebdb51e0aa91df99292d39f0319034a693f4`
   - `cmp bin/virc bin/virc_stage3`: 100% bit-identical fixed point.
   - Stage artifacts `bin/virc_stage1`, `bin/virc_stage2`, `bin/virc_stage3` removed after audit.

#### 5. Deterministic performance scaling and noise isolation

To separate wall-clock observations from the deterministic complexity oracle while preserving strict validation:
- `tests/perf_contract/test_borrow_checker_scaling.py` supports `--time-metric {min,median}` (default: `median`) and standalone `--assert-ops-only` operation-count gating for environments where wall-clock isolation cannot be guaranteed.

```sh
python3 tests/perf_contract/test_borrow_checker_scaling.py \
  --virc bin/virc --repeats 3 --time-metric median \
  --assert-scaling --max-ratio 2.8 --max-op-ratio 2.5
```

Measured scaling on canonical `bin/virc`:

| N | Borrow ms | Control ms | Wall growth | Borrow operations | Operation growth |
|---:|---:|---:|---:|---:|---:|
| 32 | 41.59 | 39.56 | — | 16,409 | — |
| 64 | 49.62 | 48.47 | 1.19x | 35,146 | 2.14x |
| 128 | 72.58 | 69.52 | 1.46x | 87,023 | 2.48x |
| 256 | 121.11 | 111.78 | 1.67x | 201,538 | 2.32x |
| 512 | 249.10 | 223.43 | 2.06x | 433,892 | 2.15x |
| 1024 | 623.02 | 561.25 | 2.50x | 936,793 | 2.16x |

- Peak deterministic operation growth: **2.48x** at $N=64 \to 128$, strictly within the contract ceiling of $\le 2.50\times$ (`max_op_ratio = 2.5`).
- Median wall growth in isolated sampling: $1.19\times \dots 2.50\times$, passing the $\le 2.80\times$ ceiling.

## 8. Acceptance Criteria

- [x] Six increasing named-borrow sizes and matched controls are committed.
- [x] Deterministic counters, not wall time alone, enforce the `O(N log N)`
  envelope on the independent corpus.
- [x] Statement NLL and await checks use one reverse block liveness index.
- [x] Hot named state uses maintained dynamically resized indices.
- [x] Path-overlap semantics pass exact, projection, field, constant-index, and
  dynamic-index contracts; deeper projection indexing is linked to phase 2.
- [ ] A dedicated loop fixed-point operation-count corpus remains. It is
  explicitly accepted as follow-up `VIRC-ISS-0028` under VPS section 15.
- [x] All 149 memory contracts pass at all four supported optimization levels.
- [x] Diagnostic/IDE-facing CLI contracts pass deterministically.
- [x] Canonical/generated source synchronization and fixed point pass.
- [x] Corrective PLAN/REPORT linkage and phase-2 follow-up are registered.

## 9. Known Limitations

- A function containing projection loans can still select a conservative
  full-vector path-overlap scan for correctness. `VIRC-ISS-0028` requires a
  dynamically resized root-owner partition.
- Loop iteration is a finite monotone dataflow computation, but round/state
  growth does not yet have its own registered operation-count corpus.
- Timing data is Darwin ARM64 local evidence; deterministic counters are the
  portable regression oracle. Peak RSS and other hosts were not measured.

## 10. Remaining Work

`VIRC-ISS-0028` owns the second optimization phase: projection root
partitioning, dynamic-index candidate sets, loop round/state counters, and
their dedicated scaling corpora.

## 11. Conclusion

READY_FOR_CLOSE

`VIRC-ISS-0026` may close because the reproduced near-cubic independent-borrow
defect is corrected, semantic regressions are covered, all required repository
and self-host gates pass, and the remaining phase-2 work is represented by the
linked `VIRC-ISS-0028` as permitted by VPS section 15.

## 12. Related Papers

- `VIRC-ISS-0026` — corrected source issue.
- `VIRC-ISS-0028` — phase-2 follow-up.
- `VIRC-PLN-0012` — original plan.
- `VIRC-PLN-0013` — corrective plan.
- `VIRC-RPT-0028` — superseded initial report.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Corrective audit found two semantic regressions and unsupported evidence claims |
| 2026-10-04 | Accepted after regression repair, deterministic scaling gate, all-level contracts, and canonical-output fixed point |
| 2026-10-04 | Post-acceptance release promotion: bumped virc to 4.2.0, rebuilt fixed point, replaced bin/virc, and re-ran performance/CLI gates |
| 2026-10-07 | Re-verified post-reopening: BFS func collection with queue lifecycle cleanup, self-host UAM fixes in io.vri, type_expr.vri, json.vri, version 2026.1.2, bit-identical bootstrap fixed point (SHA-256: 1ee0e64..., 17,910,031 bytes), 15/15 target contracts pass, 149/149 memory contracts pass across -O0..-O3, peak operation growth 2.48x <= 2.50x |
| 2026-10-07 | Corrected the focused 15-case reproduction filter, restored median wall-time sampling as the default, and made standalone operation-only assertions fail closed |
