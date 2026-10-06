---
id: "VIRC-ISS-0026"
type: "ISSUE"
domain: "VIRC"
title: "Borrow checker NLL and state scans exhibit quadratic-to-cubic compile-time growth"
status: "REOPENED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-06"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow-analysis"
  - "non-lexical-lifetimes"
  - "dataflow"
  - "binding-state"
  - "ownership"
  - "move-semantics"
  - "compiler-performance"
  - "tests"
related:
  issues:
    - "VIR-ISS-0002"
    - "VIRC-ISS-0028"
  plans:
    - "VIRC-PLN-0012"
    - "VIRC-PLN-0013"
  reports:
    - "VIRC-RPT-0028"
    - "VIRC-RPT-0029"
supersedes: null
superseded_by: null
tags:
  - "borrow-checker"
  - "pass8"
  - "nll"
  - "complexity"
  - "performance"
  - "scalability"
  - "semantic-regression"
  - "use-after-move"
---

# VIRC-ISS-0026 — Borrow checker NLL and state scans exhibit quadratic-to-cubic compile-time growth

## 1. Summary

Semantic Pass 8 repeatedly scans future AST statements and linearly searches
borrow-state vectors. A source file whose size grows linearly with the number
of live named borrows exhibits super-quadratic compile-time growth; the
measured borrow-specific overhead grows by about 7.3x when the workload size
doubles from 32 to 64 and again from 64 to 128.

Static inspection establishes independent quadratic paths in boxed-state
lookup, loan release, state equality, and dataflow joins. The statement-level
NLL algorithm composes active-borrow iteration with repeated suffix-tree scans,
giving a cubic worst case for a block that keeps O(N) borrows live until its
end.

## 2. Context

`VIR-SPC-0005` section 2.2 identifies `sem_pass8_borrow.vri` as the production
borrow-analysis pass. `VIR-SPC-0017` and `VIR-SPC-0018` section 4.8 define the
ownership, move, shared-borrow, mutable-borrow, and lifetime behavior that this
pass must preserve.

Pass 8 was decomposed into `compiler/src/semantic/borrow/**` under
`VIRC-PLN-0004`; `VIRC-RPT-0003` verified that structural modularization and
semantic regression suites but did not claim or measure an asymptotic
complexity bound. `VIR-ISS-0002` separately tracks the broader language/type
system requirement for canonical binding identity and a registered complexity
gate. This ISSUE records the concrete VIRC implementation defect, reproducer,
and measured Pass 8 scaling evidence.

## 3. Expected Behavior

- Borrow analysis should scale linearly or O(N log N) for a linear-size block
  containing independent declarations and named borrows.
- Last-use/NLL decisions should not rescan the complete future statement suffix
  separately for every active loan at every statement boundary.
- Hot state lookup, insert, delete, equality, and union operations should use
  canonical binding identities and documented complexity bounds.
- Loop fixed-point processing may revisit changed states, but individual set
  comparisons and joins should not introduce avoidable quadratic membership
  scans.
- Performance corrections must preserve all ownership, lifetime, CFG, loop,
  await, shadowing, and projection diagnostics.

## 4. Actual Behavior

### Post-closure regression observed 2026-10-06

The current self-hosted `virc 4.2.1` accepts 15 registered negative ownership
contracts and emits artifacts where Pass 8 must reject use-after-move with
`E5001`. The failures cover direct entity moves, entity parameters, projection
moves, duplicate owned arguments, and move state across `loop`, `when`, `for`,
branches, `skip`, and nested loops:

```text
MEM-BOR-012
MEM-BOR-026
MEM-BOR-027
MEM-BOR-LOOP-001..007
MEM-BOR-LOOP-009..010
MEM-BOR-LOOP-012..013
MEM-BOR-EDGE-007
```

The focused 15-case corpus fails identically at `-O0`, `-O1`, `-O2`, and
`-O3`: 0 PASS / 15 FAIL. This invalidates the post-closure evidence that all
149 memory contracts pass at every supported optimization level.

- `pass8_walk_children_stmts` examines every active `bound_borrows` entry after
  each statement and calls `pass8_tree_uses_ident` across successive future
  AST subtrees until it finds a use. Keeping O(N) borrowers live to the end of
  an O(N)-statement block produces O(N^3) tree work.
- The await path performs another active-borrow-by-future-suffix scan when a
  statement contains `await`.
- `context.vri` documents a lazy name-to-item hash in boxed vectors, but
  `pass8_box_push`, `pass8_box_pop`, `pass8_box_set`, and
  `pass8_box_truncate_to` do not maintain that index, and `pass8_box_find`
  always scans the vector. The lazy-map helpers have no boxed-state caller.
- The only active Pass 8 hash use is the separate function index. Its bucket
  count is fixed at 256, so it also lacks an asymptotic constant-time guarantee
  without resizing.
- `pass8_release_borrower` restarts a full binding scan after each deletion and
  calls another linear scan to remove the corresponding owner loan.
- State equality and merge routines perform a linear membership query for each
  source item. `pass8_merge_bound_box` checks membership and then calls
  `pass8_claim_borrow`, which checks the same membership again. Loop
  fixed-point and case/branch joins repeat these costs.

## 5. Reproduction

### Post-closure regression reproduction — 2026-10-06

Run the focused registered negative corpus once for each optimization level:

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --virc bin/virc \
  --filter 'MEM-BOR-(012|026|027|LOOP-(001|002|003|004|005|006|007|009|010|012|013)|EDGE-007)$' \
  --opt-level=<O0|O1|O2|O3> \
  --compile-timeout 60
```

Each of `-O0`, `-O1`, `-O2`, and `-O3` reports 0 PASS / 15 FAIL. Every
negative fixture unexpectedly generates an artifact instead of producing the
required E5001 diagnostic.

### Original performance reproduction — 2026-10-04

The audit ran on 2026-10-04 on Darwin ARM64 from working tree base commit
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`. The five hotspot source files
listed in Evidence had no diff from that commit. The measured compiler was:

```text
bin/virc_stage2
virc 4.1.0 (self-hosted)
sha256 2e91ad5920d2e0f0b5bd10cf1e8d6fe67c35ee0cb6e0bcd30a53b81dc8cf76d1
```

For each N in `8, 16, 32, 64, 128`, generate one function with N independent
`Box` owners, N named borrows, and N later calls that use those borrowers:

```vir
entity Box:
    val: int
end.

func inspect(b: &Box):
    print b.val
end.

func main:
    var x0 = Box(val: 0)
    # Repeat owners through x(N-1).
    let b0 = &x0
    # Repeat named borrows through b(N-1).
    inspect(b0)
    # Repeat uses through b(N-1).
end.
```

The control has the same three groups and O(N) source size, replacing named
borrow declarations with integer padding declarations and using temporary
`inspect(&xI)` borrows. Warm each generated file once, then run five samples:

```sh
bin/virc_stage2 /private/tmp/borrow_N.vri \
  --check --timings --color=never
bin/virc_stage2 /private/tmp/control_N.vri \
  --check --timings --color=never
```

Median compiler-reported times were:

- N=32: borrow 46 ms; control 24 ms; borrow-specific delta 22 ms.
- N=64: borrow 212 ms; control 50 ms; borrow-specific delta 162 ms.
- N=128: borrow 1325 ms; control 154 ms; borrow-specific delta 1171 ms.

The borrow-specific delta grows by 7.36x and 7.23x across the two doublings,
consistent with the statically identified near-cubic path over this range.

The semantic regression check used:

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/memory_contract/manifest.tsv \
  --fixtures tests/memory_contract \
  --virc bin/virc_stage2 \
  --filter 'MEM-BOR' --opt-level=-O0
```

Result: 94 PASS, 0 FAIL, 0 BLOCKED.

## 6. Evidence

### Reopening evidence — 2026-10-06

- OBSERVED: repository HEAD was
  `e1fc2d54773b83a6be684ec6ab20f403faf0a215`; the dirty worktree was preserved.
- OBSERVED: tested `bin/virc` SHA-256 was
  `c18839d3d359dc771cea4e8a4191eb4fd2122900d43d316dc7327a0c1205e4a9`.
- CONFIRMED: the 15-case filter returns 0 PASS / 15 FAIL independently at
  `-O0`, `-O1`, `-O2`, and `-O3`; every failure says the compiler unexpectedly
  generated an artifact for a `compile_fail` contract.
- CONFIRMED: `VIR-SPC-0018` section 4.8 classifies `entity` as a Move type and
  requires the old owner to become invalid after a move. `VIR-SPC-0005`
  section 2.3 likewise requires the source binding to be invalid after move.
- CONFIRMED: `VIRC-RPT-0029` explicitly claimed `MEM-BOR-027` rejection and
  149/149 memory-contract success at all four optimization levels; the current
  evidence contradicts that closure gate.
- NOT_VERIFIED: the first regressing compiler revision and the precise Pass 8
  source change responsible for losing entity move state.

- CONFIRMED: `compiler/src/semantic/borrow/walk_stmts.vri:64-99` nests active
  borrower iteration, future-statement iteration, and recursive identifier-use
  inspection.
- CONFIRMED: `compiler/src/semantic/borrow/nll.vri:20-39` recursively visits an
  AST subtree for each `pass8_tree_uses_ident` call.
- CONFIRMED: `compiler/src/semantic/borrow/context.vri:132-150` defines a lazy
  per-box map, while lines 264-280 do not maintain it and lines 311-344 use
  vector scans. Repository-wide call inspection found no use of
  `pass8_box_ensure_map` outside its definition.
- CONFIRMED: `compiler/src/semantic/borrow/loans.vri:109-140` restarts loan
  scans after each deletion; `pass8_remove_one_borrow` is also linear.
- CONFIRMED: `compiler/src/semantic/borrow/state.vri:45-155` composes state
  iteration with linear membership lookup; loop fixed-point execution repeats
  equality and merge operations in
  `compiler/src/semantic/borrow/walk_loops.vri:43-115`.
- CONFIRMED: the controlled timing probe shows 46/212/1325 ms for 32/64/128
  named borrowers versus 24/50/154 ms for the corresponding controls.
- CONFIRMED (historical 2026-10-04 evidence): all 94 then-registered
  `MEM-BOR*` contracts passed at `-O0`; that result is superseded for current
  correctness by the reopening evidence above.
- OBSERVED: the measured growth is near cubic for this finite input range.
  Timings alone are not claimed as an exact asymptotic proof; the source-level
  nested traversal establishes the worst-case construction.
- NOT_VERIFIED: scaling above N=128, peak RSS, other hosts, other compiler
  binaries, O1-O3 timing, and per-function operation counters.

## 7. Scope

### Affected

- statement-list NLL and last-use processing;
- borrow-across-await liveness checking;
- boxed move, borrow, type, scope, and uninitialized state;
- loan release and branch/case/loop dataflow joins;
- self-host compile time for large functions with many live bindings;
- performance regression coverage.

### Not affected / Unknown

- The original 2026-10-04 audit found no semantic regression in its 94 executed
  `MEM-BOR*` contracts; the 2026-10-06 reopening evidence now demonstrates a
  15-case entity-move regression.
- Function-name lookup already uses a separate hash index, although its fixed
  bucket count does not provide a growing-input asymptotic guarantee.
- This ISSUE does not change language ownership or lifetime semantics.
- NOT_VERIFIED: whether parser, inference, typecheck, or lowering contain
  additional independent scaling bottlenecks on the same generated corpus.

## 8. Impact

Large generated functions, compiler sources, or application code with many
named borrows can spend super-quadratic time in semantic analysis even when
the source size grows linearly. At N=128 the borrow workload already takes
1.325 seconds versus 154 ms for the control. Extrapolation is not accepted as
evidence, but the cubic source construction makes substantially larger inputs
a credible compile-latency and CI-timeout risk.

The original performance defect was S2. The reopened issue is S1 because the
current compiler accepts programs that violate canonical entity move semantics
and emits executable artifacts instead of E5001 diagnostics. P1 requests
near-term correction because Pass 8 runs on every compilation and the failure
spans direct calls, projections, duplicate owned arguments, and loop dataflow.

## 9. Preliminary Analysis

- CONFIRMED: repeated future-use scans are the dominant constructed-path
  algorithmic defect and can be replaced by one reverse liveness/last-use
  analysis per lexical statement list.
- CONFIRMED: boxed-state indexing is incomplete rather than merely suffering
  poor hash distribution; the vector mutators and lookup never connect to the
  declared lazy map.
- CONFIRMED: path-overlap queries are not exact-name lookups. Any indexed
  replacement must preserve ancestor/descendant and dynamic-index alias rules,
  for example by grouping projection paths by canonical root before checking
  overlap.
- HYPOTHESIS: a reverse block-use index keyed by canonical binding ID, a
  borrower-to-loan multimap, and dynamically resized state maps can reduce the
  ordinary statement-list path to O(AST + uses + loans) expected time without
  changing diagnostics.
- HYPOTHESIS: worklist-based loop propagation with hash-set equality/union can
  make each monotone fact insertion bounded while avoiding full-state cloning
  and quadratic membership checks on unchanged rounds.
- NOT_VERIFIED: the best representation for deterministic diagnostics and IDE
  fact ordering, which currently depend on vector traversal order.

## 10. Acceptance Criteria

- [x] A committed Pass 8 performance corpus generates at least four increasing
  sizes, including 32, 64, 128, and 256 live named borrowers, plus a matched
  non-borrow control.
- [x] Stable operation counters or a documented low-noise benchmark gate prove
  O(N) expected or O(N log N) growth for the independent linear-size corpus;
  wall-clock thresholds alone are not the only oracle.
- [x] Statement-level NLL and borrow-across-await checking do not rescan the
  remaining AST separately for every active borrower.
- [x] Move, type, scope, uninitialized, borrower, and owner-loan state use
  canonical binding/path identities with maintained, dynamically sized indices
  for hot lookup, insert, and delete operations.
- [x] Path-overlap indexing preserves exact, ancestor/descendant, disjoint
  field, constant-index, and dynamic-index alias semantics.
- [ ] Bulk borrower release and state equality/union avoid quadratic full-set
  rescans, but a dedicated loop-convergence operation-count corpus is deferred
  to linked follow-up `VIRC-ISS-0028`.
- [ ] The full memory contract passes at every supported optimization level,
  including named borrow, shadowing, projection, CFG join, loop back-edge,
  early exit, await, arena reset, and positive/negative cases. This criterion
  was previously met by `VIRC-RPT-0029` but fails on the reopened evidence.
- [ ] All 15 reopened entity-move negative contracts reject with E5001 and
  produce no artifact at `-O0`, `-O1`, `-O2`, and `-O3`.
- [ ] A focused regression matrix proves direct entity moves, parameter
  forwarding, projection moves, duplicate owned arguments, and loop back-edge
  joins preserve invalidated ownership state.
- [x] Diagnostics and IDE loan/end facts remain deterministic and retain their
  required origin/end locations.
- [x] Canonical sources and generated compiler sources are synchronized, and
  fixed-point self-host verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure; the REPORT records
  benchmark data, semantic regressions, limitations, and any remaining
  target-specific gaps.

## 11. Related Papers

### Issues

- `VIR-ISS-0002` — broader canonical typed identity and complexity closure.
- `VIRC-ISS-0028` — second-phase projection overlap and loop dataflow scalability.

### Plans

- `VIRC-PLN-0012` — Eliminate Pass 8 borrow checker super-quadratic NLL and state scans.
- `VIRC-PLN-0013` — Correct Pass 8 scalability verification and semantic regressions.

### Reports

- `VIRC-RPT-0028` — Borrow checker NLL and state scans scalability optimization report.
- `VIRC-RPT-0029` — Corrective verification superseding VIRC-RPT-0028.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created from static Pass 8 complexity audit, controlled scaling benchmark, and 94/94 borrow-contract verification |
| 2026-10-04 | Linked VIR-ISS-0002 |
| 2026-10-04 | Linked VIRC-PLN-0012 |
| 2026-10-04 | Linked VIRC-RPT-0028 |
| 2026-10-04 | Resolved via VIRC-PLN-0012 and verified in VIRC-RPT-0028: linear O(N) scaling achieved, all 10 criteria met |
| 2026-10-04 | Linked VIRC-PLN-0013 |
| 2026-10-04 | Linked VIRC-RPT-0029 |
| 2026-10-04 | Corrective audit repaired two semantic regressions, replaced unsupported timing claims with deterministic counters, and moved loop/projection phase 2 to VIRC-ISS-0028 |
| 2026-10-04 | Closed with accepted corrective evidence in VIRC-RPT-0029 and explicit linked follow-up VIRC-ISS-0028 |
| 2026-10-04 | Post-closure compiler release promoted to virc 4.2.0 with a new canonical-output fixed point recorded in VIRC-RPT-0029 |
| 2026-10-06 | Reopened after 15 registered entity move/use-after-move negative contracts produced artifacts at O0, O1, O2, and O3, contradicting the 149/149 closure evidence |
