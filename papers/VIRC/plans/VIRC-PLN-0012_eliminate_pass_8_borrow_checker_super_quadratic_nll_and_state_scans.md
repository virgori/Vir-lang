---
id: "VIRC-PLN-0012"
type: "PLAN"
domain: "VIRC"
title: "Eliminate Pass 8 borrow checker super-quadratic NLL and state scans"
status: "COMPLETED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "semantic"
components:
  - "borrow-analysis"
  - "non-lexical-lifetimes"
  - "dataflow"
  - "binding-state"
  - "compiler-performance"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0026"
  plans: []
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
---

# VIRC-PLN-0012 — Eliminate Pass 8 borrow checker super-quadratic NLL and state scans

## 1. Objective

Eliminate super-quadratic and cubic algorithmic bottlenecks in Semantic Pass 8 (`compiler/src/semantic/borrow/**`), achieving linear $O(N)$ or $O(N \log N)$ compile-time scaling for blocks with live named borrows while preserving the registered memory contracts, IDE loan/end facts (`ideFactBorrowEnd`), and deterministic diagnostics.

## 2. Source Issues

- [VIRC-ISS-0026](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0026_borrow_checker_nll_and_state_scans_exhibit_quadratic_to_cubic_compile_time_growt.md) — Borrow checker NLL and state scans exhibit quadratic-to-cubic compile-time growth.

## 3. Scope

### In Scope

- **Statement-Level NLL & Suffix Scans (`walk_stmts.vri`, `nll.vri`):** Replace repeated $O(B \times K \times S)$ AST suffix scans after each statement with a single block-level last-use table or reverse liveness analysis computed once per sequential statement list ($O(K \times S)$).
- **Borrow Across Await Checking (`walk_stmts.vri`, `async.vri`):** Eliminate active-borrower $\times$ future-statement suffix scans when inspecting statements containing `await`.
- **Borrower & Loan Release Operations (`loans.vri`):** Replace restart-on-delete quadratic loops in `pass8_release_borrower` and `pass8_remove_one_borrow` with single-pass compaction and indexed lookup.
- **Boxed State Hash Index Maintenance (`context.vri`):** Wire active hash indexing into `pass8_box_push`, `pass8_box_pop`, `pass8_box_set`, `pass8_box_truncate_to`, and `pass8_box_find` so state lookups run in $O(1)$ expected time instead of $O(N)$ linear scans.
- **Path-Overlap Indexing (`paths.vri`, `loans.vri`, `moves.vri`):** Exploit the invariant that paths overlap only if they share identical root owners ($pass8\_root\_owner(p_1) == pass8\_root\_owner(p_2)$), partitioning conflict queries by root owner to avoid full vector comparisons.
- **Dataflow State Merges & Loop Convergence (`state.vri`, `walk_loops.vri`):** Eliminate redundant repeated membership queries in `pass8_merge_bound_box`, `pass8_merge_borrows_box`, `pass8_merge_moved_box`, and `pass8_borrow_state_equal`.
- **Performance Corpus & Contract:** Add an automated scaling benchmark suite (`tests/perf_contract/test_borrow_checker_scaling.py`) evaluating $N \in \{32, 64, 128, 256\}$ with operation/timing metrics and regression assertions.
- **Verification & Self-Hosting:** Verify the full memory contract at every supported optimization level, the CLI contract suite, compiler module checks, and a canonical-output self-hosting fixed point without error or divergence.

### Out of Scope

- Changes to Vir language syntax, grammar, or type system semantics.
- Changes to ownership rules, borrow exclusivity, or lifetime definitions specified in `VIR-SPC-0017` / `VIR-SPC-0018`.
- Optimization passes outside Semantic Pass 8 (e.g. MIR or LIR optimizations).

## 4. Current Architecture

Semantic Pass 8 analyzes ownership and borrows across AST blocks:
1. `walk_stmts.vri:64-100`: After statement $i$ in a block of $K$ statements, the walker loops over every active borrower in `bound_borrows`. For each borrower, it iterates over statements $j = i+1 \dots K-1$ and recursively traverses AST nodes via `pass8_tree_uses_ident` searching for identifier mentions. When a borrower is released, it restarts the outer loop (`nll_again = 1`). For $N$ statements keeping $N$ borrows live, this evaluates to $O(N^3)$ node inspections.
2. `walk_stmts.vri:31-53`: If statement $i$ contains `await`, it repeats the active borrower $\times$ remaining statement suffix search.
3. `context.vri:132-248`: Allocates 16-byte box structs `[0]=vec, [8]=map` but mutators (`pass8_box_push`, `pass8_box_set`, etc.) leave the map unused or disconnected, causing `pass8_box_find` to fall back to linear vector search `when i < n loop`.
4. `loans.vri:109-140`: `pass8_release_borrower` runs nested loops with `release_again = 1` restarting from 0 whenever a binding is removed, and calls `pass8_remove_one_borrow` which also scans linearly.
5. `state.vri:45-155`: `pass8_merge_bound_box` and `pass8_borrow_state_equal` execute nested membership queries calling `pass8_borrow_binding_present`, taking $O(N^2)$ time during branch joins and loop lattice iterations.

## 5. Proposed Architecture

1. **Block-Level Last-Use Index (`pass8_block_liveness`):**
   - Before executing statements in `pass8_walk_children_stmts`, build a block-scoped last-use table `last_use_stmt_map` mapping identifier names to the highest statement index where they are referenced.
   - A single AST pass over all statements in the block records `last_use_stmt_map[ident] = max(stmt_index)` in $O(\text{block\_size})$ time.
   - At statement $i$, checking whether borrower `nll_name` is used later reduces to $O(1)$: `last_use_idx > i`.
   - For `await` at statement $i$, checking whether borrower `b_name` is live across `await` reduces to $O(1)$: `last_use_idx >= i`.
   - Single-pass borrower release: iterate active borrowers once; release all eligible borrowers without resetting the iteration index.

2. **Maintained Box Hash Index (`context.vri`):**
   - Maintain the hash table in `pass8_box_push`, `pass8_box_set`, `pass8_box_pop`, and `pass8_box_truncate_to`.
   - `pass8_box_find(b, name)` queries the hash table in $O(1)$ expected time, with fallback to vector only when the box has no map.
   - Dynamic resizing or bucket capacity adequate for typical symbol counts.

3. **Root-Owner Partitioned Loan & Move Tracking (`loans.vri`, `moves.vri`, `paths.vri`):**
   - Since `pass8_paths_overlap(p1, p2) == 1` requires `pass8_root_owner(p1) == pass8_root_owner(p2)`, store and query loans and moves partitioned by root owner.
   - `pass8_conflicting_borrow_line`, `pass8_borrow_count`, and `pass8_is_moved` inspect only entries sharing the target's root owner.

4. **Linear Loan Release & Bound Merge (`loans.vri`, `state.vri`):**
   - `pass8_release_borrower` performs in-place compaction: scan `bound_borrows` once from end to beginning or with two-pointer compaction, removing matching bindings and unlinking loans from `shared_borrows`/`mut_borrows` without restarting.
   - `pass8_merge_bound_box` and `pass8_borrow_state_equal` utilize hash-accelerated binding queries.

## 6. Design Decisions

### Decision 1: Block-scoped last-use table vs full CFG liveness
**Decision:** Implement a block-scoped last-use table for sequential statement lists rather than full inter-procedural CFG SSA liveness.
**Rationale:** In Vir's AST structure, statements inside blocks are executed sequentially. NLL within `walk_stmts.vri` specifically decides whether a block-local named borrow can be released before subsequent sibling statements. A block-scoped index gives exact equivalence to the existing `pass8_tree_uses_ident` suffix scans while dropping time complexity from $O(N^3)$ to $O(N)$.
**Alternatives considered:** Global CFG liveness analysis over MIR. While MIR has CFG liveness, Pass 8 runs on AST before MIR lowering to enforce source-level lexical ownership diagnostics and IDE facts (`ideFactBorrowEnd`).

### Decision 2: Root-owner partitioned indexing for path overlap
**Decision:** Group loan records by canonical root owner.
**Rationale:** The path overlapping rule in `paths.vri` states that two paths can only overlap if their root owners are identical. In independent variable declarations ($x_0, x_1, \dots, x_N$), each root owner is unique. Grouping or filtering by root owner makes conflict checking $O(1)$ per variable instead of $O(N)$.

### Decision 3: Single-pass backward compaction for loan release
**Decision:** Replace `release_again = 1` restart loops with backward iteration or linear in-place compaction.
**Rationale:** Avoids quadratic iteration restarts when multiple borrowers expire at the same statement boundary.

## 7. Implementation Plan

### Phase 1 — Performance Corpus & Benchmark Gate
- **Files:** `tests/perf_contract/test_borrow_checker_scaling.py`
- **Changes:** Create benchmark generator testing $N \in \{32, 64, 128, 256\}$ with named borrowers and controls. Measure compile times and scaling factors.
- **Exit:** Corpus runs and documents current super-quadratic scaling baseline (7.3x growth per doubling).

### Phase 2 — Block-Level Last-Use Index for NLL & Await
- **Files:** `compiler/src/semantic/borrow/nll.vri`, `compiler/src/semantic/borrow/walk_stmts.vri`
- **Changes:**
  - Implement `pass8_build_block_last_use_map(node)` in `nll.vri` to precompute the last statement index of each identifier in the statement list in a single $O(\text{block\_size})$ pass.
  - In `walk_stmts.vri`, replace the inner loop `when nll_future < child_count` with an $O(1)$ lookup in the last-use map.
  - In `walk_stmts.vri`, replace the await inner loop `when j < child_count` with an $O(1)$ lookup.
  - Eliminate `nll_again = 1` restarts in `walk_stmts.vri`.
- **Exit:** Benchmark shows immediate reduction from cubic to low-degree polynomial.

### Phase 3 — Linear Loan Compaction & Release
- **Files:** `compiler/src/semantic/borrow/loans.vri`
- **Changes:**
  - Rewrite `pass8_release_borrower` to scan and compact without `release_again = 1` loop restarts.
  - Optimize `pass8_remove_one_borrow` to avoid repeated full-vector scans.
- **Exit:** Zero redundant restarts during borrower release.

### Phase 4 — Box Hash Maintenance & Accelerated Joins
- **Files:** `compiler/src/semantic/borrow/context.vri`, `compiler/src/semantic/borrow/state.vri`
- **Changes:**
  - Maintain the hash table in `pass8_box_push`, `pass8_box_set`, `pass8_box_pop`, and `pass8_box_truncate_to`.
  - Accelerate `pass8_box_find`, `pass8_merge_bound_box`, and `pass8_borrow_state_equal`.
- **Exit:** Box lookups run in $O(1)$ expected time.

### Phase 5 — Full Verification, Sync & Self-Host Fixed Point
- **Files:** `compiler/generated/virc.vri`, `bin/virc`
- **Changes:**
  - Run `python3 tools/sync_virc.py` and verify zero drift.
  - Run `tools/check_module_dependencies.py` and `tools/check_pass_architecture.py`.
  - Run the full `tools/gap_contract_runner.py` memory manifest at `-O0` through `-O3`.
  - Run `tests/perf_contract/test_borrow_checker_scaling.py` verifying $O(N)$ / $O(N \log N)$ scaling.
  - Rebuild Stage 1, Stage 2, Stage 3 compilers and prove byte-identical output when generations use the same canonical output path.

## 8. Compatibility

- **Language Conformance:** 100% compliant with Vir Spec v2.0 ownership and borrow semantics.
- **Diagnostics:** Exact diagnostic IDs, error codes, and source line numbers preserved.
- **IDE Facts:** Deterministic emission of `ideFactBorrowEnd` and loan facts preserved.

## 9. Migration

No user-facing migration required. Internal compiler performance optimization.

## 10. Validation Plan

1. **Performance Validation:** `tests/perf_contract/test_borrow_checker_scaling.py` asserting deterministic Pass 8 operation growth $\le 2.5\times$ and wall growth $\le 2.8\times$ per input doubling across $N \in \{32, 64, 128, 256, 512, 1024\}$.
2. **Contract Validation:** Run all 149 memory contracts at `-O0`, `-O1`, `-O2`, and `-O3`.
3. **CLI Contract:** `python3 tests/cli_contract/runner.py --virc bin/virc` (43/43 PASS).
4. **Transform Tests:** `python3 tests/test_opt_pre_and_loop_transforms.py --virc bin/virc` (20/20 PASS).
5. **Self-Host Fixed Point:** Successive generations produce the same SHA-256 when targeting the same canonical output path.
6. **Paper Validation:** `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Missed identifier use in complex AST subtrees | Low | Medium | Re-use existing recursive visitor logic when indexing block identifiers. |
| Invalidation of box hash during deep recursion | Low | High | Ensure every box mutator updates or invalidates the hash synchronously. |
| Shadowing or rebinding in sub-blocks | Low | Medium | Last-use map only tracks names for lexical block scope; outer borrowers are already excluded by depth check. |

## 12. Rollback Strategy

Changes are isolated to `compiler/src/semantic/borrow/**` and new tests under `tests/perf_contract/`. In case of unexpected regression, revert the git working tree commit and regenerate `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] Committed Pass 8 scaling benchmark suite in `tests/perf_contract/test_borrow_checker_scaling.py`.
- [x] Deterministic operation growth through $N=1024$ demonstrates an $O(N \log N)$-compatible envelope (ratio $\le 2.5\times$); wall growth remains $\le 2.8\times$.
- [x] Statement-level NLL and await checks do not rescan future AST subtrees for each borrower.
- [x] Box hash lookups and root-owner loan queries operate in $O(1)$ expected time.
- [x] All 149 memory contracts pass at `-O0`, `-O1`, `-O2`, and `-O3`.
- [x] IDE facts (`ideFactBorrowEnd`) and diagnostics remain deterministic.
- [x] `compiler/generated/virc.vri` synchronized with zero drift.
- [x] Successive self-host generations achieve a byte-identical canonical-output fixed point.
- [x] VPS validation passed and REPORT created.

## 14. Related Papers

- `VIRC-ISS-0026` — Borrow checker NLL and state scans exhibit quadratic-to-cubic compile-time growth.
- `VIRC-RPT-0028` — Borrow checker NLL and state scans scalability optimization report.
- `VIR-ISS-0002` — Type system hardening lacks canonical typed identity and complexity closure.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial detailed plan addressing all 10 acceptance criteria of VIRC-ISS-0026 |
| 2026-10-04 | Linked VIRC-RPT-0028 |
| 2026-10-04 | Completed all phases; verified linear scaling, 94/94 MEM-BOR, 43/43 CLI, and 3-stage fixed point in VIRC-RPT-0028 |
| 2026-10-04 | Linked VIRC-RPT-0029 |
| 2026-10-04 | Corrected verification claims per VIRC-RPT-0029: deterministic O(N log N) envelope, 149 contracts at four optimization levels, and canonical-output fixed point |
