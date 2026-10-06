---
id: "VIRC-RPT-0029"
type: "REPORT"
domain: "VIRC"
title: "Corrective verification of Pass 8 scalability and semantic regressions"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
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
  output path.

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
  --virc bin/virc --repeats 3 --assert-scaling \
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
