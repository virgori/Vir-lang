---
id: "VIRC-PLN-0022"
type: "PLAN"
domain: "VIRC"
title: "Teardown sub-arena scope before tail jump in tail recursion"
status: "COMPLETED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "control-flow-analysis"
  - "ast-to-mir"
  - "lir-optimizer"
  - "arena-lowering"
  - "arm64"
  - "x86-64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0035"
  plans: []
  reports:
    - "VIRC-RPT-0039"
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tail-recursion"
  - "arena"
  - "cleanup"
  - "tco"
---

# VIRC-PLN-0022 — Teardown sub-arena scope before tail jump in tail recursion

## 1. Objective

Resolve VIRC-ISS-0035 by enabling clean, safe Tail-Call Optimization (TCO) across explicit `arena:` scopes:
1. Fix Control Flow Analysis (Pass 7) to recognize `AstType.ArenaBlock` as terminating when its enclosing body block terminates with `out`/`return`, eliminating false warning `W4001 Missing return statement on some code paths`.
2. Update AST-to-MIR statement lowering (`lower_stmt_return`) when lowering a direct self-tail-call inside an active arena scope to enforce the correct order:
   evaluate and stage arguments $\to$ promote escaping allocations if any $\to$ restore arena watermark (`MIR_MEM_RESET`) $\to$ set contiguous call arguments $\to$ emit self-Call and jump to return.
3. Permit functions with arena memory management (`MIR_MEM_MARK`, `MIR_MEM_RESET`, `MIR_MEM_PROMOTE`) in LIR Pass 11 TCO (`opt_backend_run_tco` / `lir_func_has_cleanup`), allowing tail positions whose arena reset has already completed before the call to transform into `LirOp.TailCall(0)` (`b LBB_<fid>_0`), while continuing to strictly reject calls with pending unexecuted cleanups (`ensure`, `revert`, `try`).
4. Implement `MIR_MEM_MARK` (71), `MIR_MEM_RESET` (72), and `MIR_MEM_PROMOTE` (73) in `compiler/src/lower/lir_to_mc/arm64.vri` (and `x86_64.vri`), ensuring the MCInst pipeline emits actual load/store instructions on the arena register (`X28` on ARM64, `R15` on x86-64).
5. Verify that deep recursion (10,000,000 iterations) executes in bounded $O(1)$ stack space and $O(1)$ memory without stack exhaustion or OOM, producing the exact oracle `660305`.

## 2. Source Issues

- VIRC-ISS-0035 — Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump

## 3. Scope

### In Scope

- `compiler/src/semantic/cfa/returns.vri`:
  - Handle `AstType.ArenaBlock` in `pass7_walk_block_check_return` so that terminating `ArenaBlock` nodes are recognized.
- `compiler/src/semantic/cfa/out_params.vri`:
  - Handle `AstType.ArenaBlock` in `pass7_check_stmt_outs` so that definite assignment analysis propagates through arena blocks.
- `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`:
  - Detect direct self-tail calls inside active arena scopes in `lower_stmt_return`.
  - Sequence argument staging, promotion, `MIR_MEM_RESET`, `SetArg`, and `Call`.
- `compiler/src/backend/opt_backend.vri`:
  - Remove `MIR_MEM_MARK` (71), `MIR_MEM_RESET` (72), and `MIR_MEM_PROMOTE` (73) from the whole-function blocking list in `lir_func_has_cleanup`.
  - Allow `MIR_MEM_RESET` (72) in `lir_is_pure_fail_block`.
- `compiler/src/lower/lir_to_mc/arm64.vri` and `compiler/src/lower/lir_to_mc/x86_64.vri`:
  - Add MCInst lowering for `MIR_MEM_MARK`, `MIR_MEM_RESET`, and `MIR_MEM_PROMOTE`.
- `compiler/src/ir/mc/mc_verify.vri`:
  - Register `rt_promote_graph` as a valid runtime symbol.
- Regression testing:
  - Add dedicated test case `test_10_arena_tco_stack_and_memory_bounded` in `tests/test_opt_tail_call.py`.
  - Verify against `/Users/gengyang/Desktop/Test/TCO.vri`.
  - Verify bootstrap fixed-point determinism (`cmp` / `shasum`).

### Out of Scope

- Mutual recursion or cross-function tail calls across arenas.
- Bypassing `ensure` blocks or `try/revert` clauses (these must remain linked calls).

## 4. Current Architecture

1. **CFG Analysis Gap**:
   In `compiler/src/semantic/cfa/returns.vri`, `pass7_walk_block_check_return` checks `AstType.Block`, `AstType.ReturnStmt`, `AstType.ThrowStmt`, and `AstType.IfStmt`, but completely omits `AstType.ArenaBlock`. As a result, functions ending in `arena:` fall through to returning 0, triggering warning `W4001 Missing return statement on some code paths`.

2. **Inverted Lowering Order**:
   In `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`, `lower_stmt_return` lowers the return expression first via `lower_expr(b_ret, ret_expr)`. When `ret_expr` is a recursive call, the `Call` instruction is emitted *before* `MIR_MEM_RESET`. If the call were transformed to a tail jump, the reset would be skipped; if it is not transformed, recursion recurses before resetting the arena watermark, exhausting the stack and leaking memory.

3. **Whole-Function TCO Cleanup Gate**:
   In `compiler/src/backend/opt_backend.vri`, `opt_backend_run_tco` checks `lir_func_has_cleanup(lf)`. That function returns 1 if *any* block contains `MIR_MEM_MARK` (71) or `MIR_MEM_RESET` (72). This conservative check disables TCO for the entire function, even when the arena reset has already completed prior to the tail call.

4. **Missing MCInst Emitter for Arena Intrinsics**:
   In `compiler/src/lower/lir_to_mc/arm64.vri` and `x86_64.vri`, intrinsic kinds `71` (`MIR_MEM_MARK`), `72` (`MIR_MEM_RESET`), and `73` (`MIR_MEM_PROMOTE`) were never implemented. The MC pipeline emits nothing for them, failing to restore the arena bump pointer `[X28, #0]` at runtime.

## 5. Proposed Architecture

```
[ AST ]
   │
   ├─► CFA (returns.vri & out_params.vri): recognize ArenaBlock as terminating
   │
   ▼
[ AST to MIR Lowering (jumps.vri) ]
   │
   ├─► Detect self-tail call inside active arena scope:
   │     1. Evaluate arguments -> staged_args VRegs
   │     2. Promote escaping container arguments
   │     3. Emit MIR_MEM_RESET (restores [X28, #0] before the call)
   │     4. Emit SetArg* from staged_args
   │     5. Emit Call -> pure return trampoline
   │
   ▼
[ Pre-RA LIR TCO (opt_backend.vri) ]
   │
   ├─► lir_func_has_cleanup: permit 71/72/73 (only reject ensure/revert/try)
   ├─► Pattern A matches Call followed by pure return
   └─► Rewrite Call to LirOp.TailCall(0), clear trampoline
   │
   ▼
[ MC Lowering (lir_to_mc/arm64.vri) ]
   │
   ├─► MIR_MEM_MARK   -> ldr x_dst, [x28, #0]
   ├─► MIR_MEM_RESET  -> str x_src, [x28, #0]
   ├─► MIR_MEM_PROMOTE-> bl rt_promote_graph
   └─► TailCall(0)    -> b LBB_<fid>_0
```

## 6. Design Decisions

### Decision 1: Pre-call teardown vs post-jump teardown
**Decision:** Teardown the sub-arena watermark *before* staging arguments and executing the tail jump.
**Rationale:** In tail recursion, the current iteration's local arena data is dead once the arguments for the next iteration are evaluated. Resetting the arena mark before the tail jump reclaims all sub-arena allocations immediately, keeping memory consumption $O(1)$.

### Decision 2: Refined cleanup gate vs block-level analysis
**Decision:** Remove arena intrinsics (71, 72, 73) from `lir_func_has_cleanup`'s disqualification list, relying on existing Pattern A/B pure-continuation checks.
**Rationale:** Pattern A and Pattern B already strictly verify that the instructions following the Call form a pure return (containing only Mov, Jmp, or Ret). If an unexecuted cleanup existed after the Call, Pattern A/B would reject it. Thus, removing arena intrinsics from the whole-function gate is safe and robust.

### Decision 3: MCInst parity for arena operations
**Decision:** Add `MIR_MEM_MARK`, `MIR_MEM_RESET`, and `MIR_MEM_PROMOTE` to `lir_to_mc/arm64.vri` and `lir_to_mc/x86_64.vri`.
**Rationale:** The MCInst pipeline is the canonical emitter for assembly and binary code in `virc 4.2.1`. Implementing these operations ensures that `ldr`/`str` on `X28`/`R15` are generated properly.

## 7. Implementation Plan

### Phase 1 — CFA Warning Resolution
- Update `compiler/src/semantic/cfa/returns.vri` to walk `AstType.ArenaBlock`.
- Update `compiler/src/semantic/cfa/out_params.vri` to walk `AstType.ArenaBlock`.

### Phase 2 — AST-to-MIR Arena Tail-Return Lowering
- In `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`, detect `is_arena_self_tail`.
- Sequence argument evaluation, promotion, `MIR_MEM_RESET`, and contiguous call setup.

### Phase 3 — LIR TCO Cleanup Gate
- In `compiler/src/backend/opt_backend.vri`, update `lir_func_has_cleanup` to allow 71, 72, 73.
- Allow `aux == 72` in `lir_is_pure_fail_block`.

### Phase 4 — MC Pipeline Arena Emitters
- In `compiler/src/lower/lir_to_mc/arm64.vri`, handle `MIR_MEM_MARK`, `MIR_MEM_RESET`, and `MIR_MEM_PROMOTE`.
- In `compiler/src/lower/lir_to_mc/x86_64.vri`, handle `MIR_MEM_MARK` and `MIR_MEM_RESET`.
- In `compiler/src/ir/mc/mc_verify.vri`, register `rt_promote_graph`.

### Phase 5 — Verification & Bootstrap
- Add `test_10_arena_tco_stack_and_memory_bounded` to `tests/test_opt_tail_call.py`.
- Run reproducer `/Users/gengyang/Desktop/Test/TCO.vri` and verify 10,000,000 iterations return `660305`.
- Synchronize bundle via `tools/sync_virc.py`.
- Execute multi-stage self-host bootstrap and verify bit-for-bit SHA-256 match.

## 8. Compatibility

- Fully preserves VIR-SPC-0005 (memory management) and VIR-SPC-0008 (execution model).
- Fully preserves all existing TCO semantics and negative cleanup gates (`ensure` / `try`).
- No syntax, parser, or ABI changes.

## 9. Migration

No migration required. Existing valid Vir code automatically benefits from TCO across arena scopes.

## 10. Validation Plan

- Verify `/Users/gengyang/Desktop/Test/TCO.vri` compiles without `W4001` and runs with exit code 0, output `660305`.
- Verify assembly contains `str ..., [x28]` followed by `b LBB_\d+_0` and 0 `bl` recursive calls.
- Run `tests/test_opt_tail_call.py` (all 10 tests PASS).
- Verify 3-stage self-host bootstrap fixed point.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Argument value allocated in arena escaping to next iteration | Low | Medium | Emit `MIR_MEM_PROMOTE` on escaping container argument VRegs before `MIR_MEM_RESET` |
| Negative cleanup tests regressing | Low | High | Strict preservation of `ensure`/`revert`/`try` gates in `lir_func_has_cleanup` |

## 12. Rollback Strategy

Revert changes to `jumps.vri`, `opt_backend.vri`, `returns.vri`, `out_params.vri`, and `lir_to_mc/arm64.vri`, then resynchronize `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] `W4001` eliminated for terminating returns inside arena blocks.
- [x] Direct self-tail-calls inside arena scopes emit `MIR_MEM_RESET` before `SetArg`/`Call`.
- [x] `opt_backend_run_tco` converts arena self-tail-calls to `LirOp.TailCall(0)`.
- [x] ARM64 assembly contains arena watermark restore and direct branch with 0 recursive calls.
- [x] Reproducer completes 10,000,000 steps with exit 0 and output `660305` in $O(1)$ stack.
- [x] Regression suite `tests/test_opt_tail_call.py` passes all 10 tests across `-O1`, `-O2`, `-O3`.
- [x] Fixed-point bootstrap verified bit-for-bit.
- [x] VIRC-RPT-0039 report accepted, closing VIRC-ISS-0035.

## 14. Related Papers

- VIRC-ISS-0035 — Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump
- VIRC-ISS-0024 — Production direct self-tail-call optimization (closed)
- VIRC-RPT-0030 — Current TCO implementation and its conservative cleanup gate
- VIRC-RPT-0039 — Teardown sub-arena scope before tail jump in tail recursion

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial plan created for VIRC-ISS-0035 implementation |
| 2026-10-05 | Implementation verified, all exit criteria satisfied, status advanced to COMPLETED |
