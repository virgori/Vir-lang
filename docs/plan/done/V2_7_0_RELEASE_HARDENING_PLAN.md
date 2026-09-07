# Vir v2.7.0 Compiler Hardening & Strict RA Architecture Plan

**Status:** Proposed Roadmap & Execution Contract
**Target Version:** `virc 2.7.0`
**Dependencies:**
- `REGISTER_ALLOCATION_STRICT_SPEC.md`
- `REGISTER_ALLOCATION_OPTIMIZATION_AND_BLOCK_ARENA_PLAN.md`
- `FFI_EXTERN_IMPORT_REPORT.md`
- `compiler_hardening_plan.md`

---

## 1. Principles & Mandatory Rules

1. **Strict Claims:** Every bugfix, transformation, and compiler pass enhancement MUST provide a concrete, verifiable claim (with test case reproducing failure or verifying invariant). Changes without verified claims are not admitted.
2. **Scope-Block Arena Semantics:** The Vir `arena:` construct operates as a lexical scope block (`ScopeKind.Block`). The borrow checker analyzes lifetime and escape strictly within lexical scope boundaries (no inter-procedural escape tracking).
3. **Memory Optimization via Arena Blocks:** Temporary analysis/optimization data structures that are created, used, and discarded entirely within a single function pass or scope MUST use an arena block or scratch block to eliminate heap fragmentation and memory leaks.
4. **Target Descriptors & ABI Separation:** Machine architectures (ARM64, x86-64) must not be configured via magic constants or ad-hoc ranges (`19 + color`). Target descriptors define allocatable registers, leaf/non-leaf palettes, caller-saved clobbers, callee-saved registers, reserved registers, scratch registers, and stack alignment rules.
5. **CFG Fixed-Point Liveness & Def-vs-Live-Out Interference:** Register interference must be derived from backward fixed-point dataflow liveness (`live_out[B] = union(live_in[S])`, `live_in[B] = use[B] union (live_out[B] - def[B])`), creating interference edges between `def(d)` and `live_out(d)`. Coarse whole-function interval overlap is forbidden as the strict contract.
6. **Mandatory Post-RA Verifier:** Before machine code emission, a strict invariant verifier checks that no unallocated vreg remains, no interfering vregs share a physical register, caller-saved registers never cross calls without stack spilling, and stack alignments/offsets are legal.
7. **Zero Test Regressions:** `./run_tests.sh` must maintain a 100% pass rate across the entire suite (187+ tests) after every milestone.

---

## 2. Phase 1 — SSA Correctness & Optimization Hardening

### Task 1.1 — Sentinel Initialization in `mir_rename_variables`
- **File:** `stdlib/vir/compiler/mir_ssa.vri`
- **Issue:** Seeding the variable rename stack with pre-SSA virtual register index caused undefined variables on dominator paths to fall back to pre-SSA indices, blurring pre-SSA and post-SSA namespaces.
- **Strict Claim:** Sentinel `-1` is pushed on initialization. Uninitialized reads fall back cleanly to slot index until a definition is pushed on the dominator path.
- **Verification:** Tests `tests/vri/test_arithmetic.vri`, `tests/vri/test_register.vri`, byte-for-byte exact compilation.

### Task 1.2 — Dead Phi Sweep Post-Simplification
- **File:** `stdlib/vir/compiler/mir_opt.vri`
- **Issue:** Phi nodes whose incoming value list became empty during simplification remained in `block.phis`, occupying virtual registers and creating dead graph nodes.
- **Strict Claim:** `mir_opt_sweep_dead_phis` removes any phi with `vec_len(incoming_values) == 0`.
- **Verification:** After optimization, no block contains an empty phi node.

### Task 1.3 — In-Place Instruction Mutation & Arena in Def-Counts Optimizers
- **File:** `stdlib/vir/compiler/mir_opt.vri`
- **Issue:** `mir_opt_copy_propagation` and `mir_opt_constant_propagation` construct `def_counts` vector and allocate new instructions for modifications, retaining temporary allocation pressure.
- **Strict Claim:** Instructions are modified in-place (`native_write_i64` on operand fields), and `def_counts` is contained within an arena block or freed upon pass exit.
- **Verification:** Passes complete with identical MIR semantics and zero escaping heap allocations for def-count analysis.

---

## 3. Phase 2 — Borrow Checker Correctness & Scope-Block Arena

### Task 2.1 — Move-on-Call Enforcement
- **File:** `stdlib/vir/compiler/sem_pass8_borrow.vri`
- **Issue:** Passing move-type arguments (arrays, resources) by value into function calls did not mark the source variable moved.
- **Strict Claim:** Passing a move-type identifier by value to a function marks it moved in the current scope. Subsequent use in the same scope triggers `[E5001] Use of moved value`.
- **Verification Test:** `tests/test_borrow_move_on_call.vri` (compile-fail `[E5001]`).

### Task 2.2 — Arena Escape Prevention via Bound Borrows
- **File:** `stdlib/vir/compiler/sem_pass8_borrow.vri`
- **Issue:** Returning or assigning an identifier that holds a borrow binding to an arena-allocated variable was not detected if the return was via identifier instead of direct `&x`.
- **Strict Claim:** If `bb = lookup(name, bound_borrows)` and `target(bb) in arena_locals`, returning or assigning outside the arena triggers `[E5005] Cannot escape arena-allocated reference`.
- **Verification Test:** `tests/test_borrow_arena_escape.vri` (compile-fail `[E5005]`).

### Task 2.3 — Conservative Move Join on Conditional Branches
- **File:** `stdlib/vir/compiler/sem_pass8_borrow.vri`
- **Issue:** Sequential evaluation of `then` and `else` branches without join semantics allowed values moved in only one branch to be treated as live or improperly dropped.
- **Strict Claim:** Any variable moved in either the `then` or `else` branch is treated as moved at the join point.
- **Verification Test:** `tests/test_borrow_if_move.vri` (compile-fail `[E5001]`).

### Task 2.4 — Rebind Conflict Detection Order in Assignment
- **File:** `stdlib/vir/compiler/sem_pass8_borrow.vri`
- **Issue:** Releasing the old borrower before evaluating the RHS of an assignment allowed conflicting borrows (e.g. `let r = &x; r = &mut x;`) to pass undetected.
- **Strict Claim:** Evaluating RHS before releasing previous borrower detects conflicting borrows and raises `[E5002] Cannot mutably borrow while shared borrow is active`.
- **Verification Test:** `tests/test_borrow_rebind_conflict.vri` (compile-fail `[E5002]`).

---

## 4. Phase 3 — Strict Register Allocation Architecture

### Task 3.1 — Target Register Descriptors (`lir_target_desc.vri`)
- **Strict Claim:** Formal descriptor entity `TargetDesc` providing:
  - Allocatable register palette (separate Leaf and Non-Leaf).
  - Reserved registers (SP, FP, X16, X17, X18, X28 on ARM64; RSP, RBP, R15 on x86-64).
  - Caller-saved call clobbers (X0..X15 on ARM64; RAX, RCX, RDX, RSI, RDI, R8..R11 on x86-64).
  - Callee-saved preserved registers (X19..X27 on ARM64; RBX, R12..R14 on x86-64).
  - Target-agnostic mapping from logical color index to physical register.

### Task 3.2 — CFG Fixed-Point Backward Liveness (`lir_liveness.vri`)
- **Strict Claim:** Backward dataflow iteration:
  24595live\_out[B] = igcup_{S \in succ[B]} live\_in[S]24595
  24595live\_in[B] = use[B] \cup (live\_out[B] - def[B])24595
  Iterated to convergence with RPO worklist.
  Per-instruction liveness marks any variable crossing a `Call` or `Intrinsic` instruction as requiring a callee-saved physical register or stack spill.

### Task 3.3 — Def-vs-Live-Out Interference Graph (`lir_interference.vri`)
- **Strict Claim:** For each instruction $ defining $, add undirected interference edge between $ and every  \in live\_out[i]$ (except when $ is a copy  \leftarrow v$).
- Dual representation: bit-matrix for  \le 512$ plus adjacency lists.

### Task 3.4 — Block-Arena Scratch Allocator for RA (`lir_ra_arena.vri`)
- **Strict Claim:** Ephemeral RA data structures (live bitsets, worklists, adjacency chunks) allocate from bump-allocated scratch blocks freed at the end of each function compilation. No pointer escapes to `LirFunc` or code emission.

### Task 3.5 — Mandatory Post-RA Verifier (`lir_verifier.vri`)
- **Strict Claim:** Pre-emission verifier rejects invalid allocations with deterministic diagnostics:
  1. Unallocated virtual registers in instruction operands.
  2. Conflicting physical registers between interfering virtual registers.
  3. Caller-saved registers live across calls without save/restore.
  4. Allocation of target-reserved registers.
  5. Illegal stack frame offset overlap or misalignment.

---

## 5. Phase 4 — FFI Extern Import Verification (Mach-O ARM64)

- **Status:** Target-neutral syntax and dyld dynamic linking resolved.
- **Strict Claim:** Mach-O binaries linking against OS dynamic libraries (e.g. `libSystem.B.dylib`) execute end-to-end under macOS dyld without stub offset collisions or address mismatch.
- **Verification Test:** `tests/test_extern_from_os.vri` added to `run_tests.sh` as Category M, verifying `getpid()` dynamically resolves and outputs deterministic pass confirmation.

---

## 6. Phase 5 — Version Promotion & Release Freeze `v2.7.0`

1. Update `VERSION` in `stdlib/vir/compiler/virc.vri` to `"virc 2.7.0 (self-hosted)"`.
2. Full self-hosting compiler bootstrap:
   `./bin/virc stdlib/vir/compiler/virc.vri -o dist/virc-2.7.0 && codesign -s - -f dist/virc-2.7.0 && cp dist/virc-2.7.0 bin/virc`
3. Freeze tree:
   `bash tools/freeze_std_tree.sh release v2.7.0`
4. Test suite certification:
   Run `./run_tests.sh` -> 100% PASS (187/187 tests).
