---
id: "VIRC-PLN-0014"
type: "PLAN"
domain: "VIRC"
title: "Implement production tail-call optimization in LIR"
status: "COMPLETED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "optimizer"
  - "lir"
  - "arm64"
  - "x86-64"
  - "riscv64"
  - "wasm"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0024"
    - "VIRC-ISS-0030"
  plans: []
  reports:
    - "VIRC-RPT-0030"
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tail-recursion"
  - "tco"
  - "lir"
  - "codegen"
  - "optimizer"
---

# VIRC-PLN-0014 — Implement production tail-call optimization in LIR

## 1. Objective

Implement production-grade tail-call optimization (TCO, Pass 11) for direct self-recursive
functions in the Vir compiler pipeline. Ensure that recursive tail calls are transformed to
O(1) constant stack space jumps, backend machine code and assembly emit direct branches
(`B` / `JMP`), optimizer tracing records Pass 11 accurately, and deep recursions
(>= 1,000,000 calls) complete without stack overflow.

## 2. Source Issues

- **VIRC-ISS-0024**: Tail-call optimization is specified and scaffolded but never produces LIR TailCall.

## 3. Scope

### In Scope

- Direct self-recursion calls in proven tail position across `-O1`, `-O2`, and `-O3`.
- Pre-RA LIR pass recognizing tail position, preserving argument updates (`SetArg`), and emitting `LirOp.TailCall(0)`.
- Liveness and CFG updates reflecting back-edges to block 0.
- Machine code codegen and assembly emission on ARM64, x86-64, RISC-V branching directly to block 0.
- Argument permutation, register spills, and > 8 parameter handling in tail recursion.
- Conservation gates: strict rejection of non-tail recursion and calls with pending cleanups (`ensure`, `revert`, `try`, arena reset).
- Optimizer tracing recording Pass 11 (`OptPassTCO`) upon transformation.
- Production test suite verifying structural transformation, deep runtime execution (1,000,000 calls), and negative tests.

### Out of Scope

- Cross-function sibling-call or mutual-recursion TCO (tracked for future VPS issue if needed).
- Indirect function pointer tail calls.

## 4. Current Architecture

- `compiler/src/ir/lir/lir.vri` defines `LirOp.TailCall = 27`.
- `compiler/src/backend/opt_pass.vri` registers `OptPassTCO: 11` under `OptStageLIR`, but `opt_pass_min_level(11)` defaults to 2 rather than 1.
- `compiler/src/ir/mir/mir_opt_pipeline.vri` explicitly skips Pass 11 with `# 11 TCO — OptStageLIR (skipped)`.
- `compiler/src/backend/opt_backend.vri` defines `optBackendRunLirPreLevel`, but `opt_backend_run_lir_pre` only returns `lf` unchanged without inspecting instructions.
- `compiler/src/lower/lir_codegen/emit_func.vri` lines 612-629 contains unreachable scaffolding that redundantly unwinds and reallocates the stack.
- `compiler/src/lower/lir_to_mc/arm64.vri` lacks a handler for `LirOp.TailCall`.
- Consequently, all tail calls remain `LirOp.Call` and emit `BL`, exhausting stack at depth (crashing with SIGSEGV at 1,000,000 calls).

## 5. Proposed Architecture

```
[ AST ]
   │
   ▼
[ MIR Lowering ] ──> Contiguous call sequences: SetArg*, Call, ERX-check, JumpIfNot
   │
   ▼
[ Shared MIR Opts ] ──> SSA PRE, DCE, Loop Transforms
   │
   ▼
[ LIR Lowering ] ──> Destroys SSA into virtual registers and blocks
   │
   ▼
[ Pre-RA LIR Hook: optBackendRunLirPreLevel ]
   │
   ├──> opt_backend_run_tco (Pass 11)
   │     ├── Safety Gate: reject functions with ensure/revert/try/arena cleanups
   │     ├── Pattern Match: terminal self-Call with pure return / error re-propagation
   │     └── Rewrite: preserve SetArg*, replace Call with LirOp.TailCall(0), clear dead exits
   │
   ▼
[ Liveness & Regalloc ] ──> Liveness tracks backedge from TailCall to Block 0
   │
   ▼
[ Backend Codegen / MC ]
   ├── ARM64: emit direct branch (B LBB_fid_0), write pending stack args (>8 args) to [FP+16+si*8]
   ├── x86-64: emit direct branch (JMP LBB_fid_0)
   ├── RISC-V: emit direct jump (JAL zero, LBB_fid_0)
   └── Wasm: explicit limitation tracking if structured loop requires separate block
```

## 6. Design Decisions

### Decision 1: Perform TCO at Pre-RA LIR Stage (Pass 11)

**Decision:** Implement TCO in `compiler/src/backend/opt_backend.vri` within `optBackendRunLirPreLevel`, running before register allocation.

**Rationale:** Aligns with VIR-SPC-0017 §1.2.1 and `opt_pass.vri` which designate Pass 11 as `OptStageLIR`. At LIR level, SSA has been destructed into virtual registers, avoiding CFG complications of introducing phi nodes into entry block 0. Virtual registers in the Vir allocator map to callee-saved registers `X20..X27`, while argument registers `X0..X7` are updated by `SetArg`, ensuring argument evaluation does not clobber inputs.

**Alternatives considered:** Performing TCO at AST or MIR level by converting to while-loops. Rejected because AST/MIR loop lowering creates additional synthetic basic blocks and complicates ownership tracking, whereas LIR already has `LirOp.TailCall`.

### Decision 2: Conservative Tail-Position and Cleanup Invariant

**Decision:** A call is proven tail position if and only if:
1. Callee name matches current function name.
2. Function has no pending `MIR_INTR_ENSURE`, `MIR_INTR_REVERT`, `MIR_INTR_TRY`, `MIR_INTR_ARENA`, `MIR_MEM_RESET`, `MIR_MEM_DROP`.
3. The call is either directly followed by `Ret`/`Jmp` to return, or followed by the standard ERX check where the success block performs only `Mov ret, call_dst` and jumps to return, and the failure block only re-propagates the error.

**Rationale:** Prevents any behavioral deviation where deferred handlers, cleanups, or subsequent expressions would be bypassed.

### Decision 3: Direct In-Frame Branching in Backend Codegen

**Decision:** Self-recursive tail calls reuse the caller's stack frame in-place without adjusting `FP` or allocating/freeing stack frames. For functions with more than 8 arguments, arguments 8..N are written into `[FP + 16 + (si * 8)]` before branching.

**Rationale:** Guarantees true O(1) stack space complexity and avoids unnecessary stack pointer arithmetic on every loop backedge.

## 7. Implementation Plan

### Phase 1 — Specification & Pipeline Configuration

- Update `compiler/src/backend/opt_pass.vri` so `opt_pass_min_level(OptPassTCO)` returns 1.
- Update `compiler/src/ir/mir/mir_opt_pipeline.vri` comment for Pass 11.
- Update `compiler/src/ir/lir/lir_liveness.vri` to record block 0 as a successor target for `LirOp.TailCall`.

### Phase 2 — Pre-RA LIR TCO Optimization Pass

- In `compiler/src/backend/opt_backend.vri`, implement `opt_backend_run_tco(lf: i64, level: int) -> i64`.
- Detect cleanup barriers, match terminal self-calls, rewrite to `LirOp.TailCall(0)`, clean up dead blocks, and trace via `optTraceNote(OptPassTCO)`.
- Connect into `optBackendRunLirPreLevel`.

### Phase 3 — Backend Codegen and MC Emitter

- In `compiler/src/lower/lir_codegen/emit_func.vri`: simplify `LirOp.TailCall` to branch directly to block 0 (`arm64_b_imm26(cb, 0)` with fixup to block 0), handling stack arguments when `n_stk > 0`.
- In `compiler/src/lower/lir_to_mc/arm64.vri`: add `LirOp.TailCall` handler emitting `mc_inst_new(MCOpcode.ARM64_B, mc_opnd_imm(fid * 10000 + 0), ...)`.
- In x86-64 and RISC-V emitters: add corresponding direct jumps to block 0.

### Phase 4 — Synchronization & Bootstrap Rebuild

- Run `python3 tools/sync_virc.py` to synchronize `compiler/generated/virc.vri`.
- Rebuild stage 1 compiler, codesign, and verify 3-stage self-host bootstrap (`cmp bin/virc_stage2 bin/virc_stage3`).

### Phase 5 — Verification & Governance

- Create automated test suite `tests/test_opt_tail_call.py` exercising 1,000,000 calls, structural assembly checks, argument permutation, > 8 arguments, and negative cases (`ensure`, `revert`, non-tail).
- Validate all acceptance criteria of `VIRC-ISS-0024`.
- Generate `VIRC-RPT-0030`, update `VIRC-ISS-0024` to RESOLVED, and validate VPS registry.

## 8. Compatibility

- **Source compatibility:** 100% backward compatible. All valid Vir code compiles with identical results.
- **ABI compatibility:** Unchanged calling convention (`X0..X7`, stack arguments at `[FP + 16]`).
- **Target compatibility:** Native ARM64, x86-64, and RISC-V backend support.

## 9. Migration

No user code migration required. Tail-recursive functions automatically benefit from constant stack space.

## 10. Validation Plan

- **Disassembly check:** Verify `otool -tvV` and `-S` contain `b` instead of `bl` for recursive calls.
- **Deep recursion runtime:** Run countdown with depth 1,000,000; verify exit code 0 and output 0.
- **Argument permutation runtime:** Verify `gcd(a, b)` and accumulator tail calls.
- **Stack argument runtime:** Verify tail calls with 10 arguments.
- **Negative tests:** Verify non-tail calls, `ensure`, and `revert` blocks retain `bl`.
- **Optimizer tracing:** Verify `--json` outputs `passInvocations` with id 11.
- **3-stage bootstrap:** Verify stage 2 and stage 3 compiler binaries match bit-for-bit.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Register clobber during argument update | Low | High | Vir regalloc uses callee-saved X20..X27 for virtual registers; SetArg uses X0..X7. All arguments are evaluated before SetArg writes. |
| Incomplete error propagation | Low | Medium | Direct self-calls retain function-level error return paths for exceptions occurring in subsequent iterations. |
| Unsafe optimization of functions with cleanup | Low | High | Conservative gate rejects any function with ensure, revert, try, or arena reset. |

## 12. Rollback Strategy

Revert changes in `compiler/src/backend/opt_backend.vri`, `compiler/src/lower/lir_codegen/emit_func.vri`, and `compiler/src/lower/lir_to_mc/arm64.vri`, run `python3 tools/sync_virc.py`, and recompile `bin/virc`.

## 13. Exit Criteria

- [x] Production pipeline recognizes direct self-calls in proven tail position at `-O1`, `-O2`, `-O3`.
- [x] Structural tests show transformation to `LirOp.TailCall` and assembly `B`.
- [x] ARM64 disassembly contains unlinked branch and no extra stack frames.
- [x] Registered runtime test runs 1,000,000 direct tail calls with O(1) stack space.
- [x] Negative fixtures confirm non-tail recursion and cleanup blocks are safely preserved.
- [x] Argument permutation and > 8 arguments preserve correct semantics.
- [x] Target emitters updated or documented.
- [x] Optimizer tracing records Pass 11 (`OptPassTCO`).
- [x] Synchronized compiler bundle and 3-stage self-host fixed point verified.
- [x] VPS PLAN and REPORT linked, and `./paper validate` passes.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0024_tail_call_optimization_is_specified_and_scaffolded_but_never_produces_lir_tailca.md`
- `papers/VIRC/issues/VIRC-ISS-0030_risc_v_and_wasm_backends_lack_full_tail_call_optimization_support.md`
- `papers/VIR/specs/VIR-SPC-0017_language_specification_english.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial accepted plan for VIRC-ISS-0024 TCO implementation |
| 2026-10-04 | Linked VIRC-RPT-0030 |
| 2026-10-04 | Completed all implementation phases, verified 3-stage bootstrap, and closed plan |
