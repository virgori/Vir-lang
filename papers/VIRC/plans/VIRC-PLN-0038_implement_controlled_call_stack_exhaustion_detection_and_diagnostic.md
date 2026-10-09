---
id: "VIRC-PLN-0038"
type: "PLAN"
domain: "VIRC"
title: "Implement controlled call-stack exhaustion detection and diagnostic runtime"
status: "COMPLETED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
  - "runtime"
components:
  - "compiler-runtime"
  - "stack-frame"
  - "codegen"
  - "diagnostics"
  - "arm64-backend"
  - "x86-64-backend"
  - "conformance-tests"
related:
  issues:
    - "VIRC-ISS-0053"
  plans: []
  reports:
    - "VIRC-RPT-0055"
supersedes: null
superseded_by: null
tags:
  - "stack-overflow"
  - "recursion"
  - "runtime-error"
  - "resource-limit"
  - "prologue-check"
---

# VIRC-PLN-0038 — Implement controlled call-stack exhaustion detection and diagnostic runtime

## 1. Objective

Resolve `VIRC-ISS-0053` by implementing a low-overhead, fail-safe call-stack exhaustion check in native function prologues and a standalone, non-allocating runtime trap stub. This ensures that native Vir programs exceeding safe stack limits emit a standardized Vir diagnostic message (`call-stack exhaustion (stack overflow)`) to stderr and terminate with exit status 1 instead of unclassified `SIGSEGV` (exit status 139), satisfying Group 6 Test 12 in `tests/opt/tail_call_test.vri`.

## 2. Source Issues

- `VIRC-ISS-0053`: Call-stack exhaustion terminates native programs with an unclassified SIGSEGV (S2/P1).

## 3. Scope

### In Scope

- **Runtime Stack Boundary Setup (`_start`)**:
  - In `compiler/src/lower/lir_codegen.vri` (ARM64) and `compiler/src/lower/lir_codegen_x86.vri` (x86-64), capture initial `SP` at program entry.
  - Determine safe stack limit (querying `getrlimit(RLIMIT_STACK)` with fallback to standard 8 MiB soft limit, leaving 256 KiB safety headroom before the OS guard page).
  - Store computed `stack_limit` into runtime header slot `*(X28 + 32760)` (and `*(R15 + 32760)` on x86-64).
- **Runtime Trap Stub (`__vir_stack_overflow`)**:
  - Define `LIR_RT_STACK_OVERFLOW = 121` in `compiler/src/ir/lir/lir.vri` and bump `LIR_RT_STUB_COUNT = 122`.
  - In `compiler/src/lower/lir_codegen/rt_stubs_base.vri` (and x86-64 stub emitter), implement `emit_lir_rt_stack_overflow_stub`.
  - The stub executes without stack allocation, references the static diagnostic string PC-relatively, issues `sys_write` to stderr (fd 2), and terminates via `sys_exit(1)`.
- **Function Prologue Stack Check**:
  - In `compiler/src/lower/lir_codegen/emit_func.vri` (direct ARM64 binary emitter) and `compiler/src/lower/lir_to_mc/arm64.vri` (MCInst assembly emitter):
    Emit prologue comparison `cmp sp, x9` against `*(x28 + 32760)` and branch over trap call to `LIR_RT_STACK_OVERFLOW`.
  - In `compiler/src/lower/lir_codegen_x86/emit_func.vri` and `compiler/src/lower/lir_to_mc/x86_64.vri`:
    Emit matching x86-64 prologue check `cmp rsp, qword ptr [r15 + 32760]` and call to runtime stub.
- **Verification**:
  - Verify Test 12 in `tests/opt/tail_call_test.vri` passes (`[PASS] test_12_controlled_stack_exhaustion`).
  - Verify Group 6 test suite reaches 36/36 PASS (100%).
  - Verify 3-stage bootstrap fixed-point identity.

### Out of Scope

- RISC-V and Wasm stack checks (recorded under separate target issues).
- Dynamic stack expansion / split stacks (Vir uses contiguous ABI stacks with TCO and bounded arena lifecycles).

## 4. Current Architecture

Currently, function prologues allocate stack frames without inspecting the remaining stack distance to the platform guard page:
- On ARM64, `compiler/src/lower/lir_codegen/emit_func.vri` pushes callee-save registers and subtracts `frame_size` from `SP`.
- When non-tail recursion exceeds the soft stack limit (~8 MiB), the next store into `[sp, #-16]!` touches the guard page and raises an unhandled kernel `SIGSEGV` (signal 11, process exit status 139) with empty stdout and stderr.
- `tests/opt/tail_call_test.vri` Test 12 registers this defect as a failure.

## 5. Proposed Architecture

### 5.1 Stack Limit Storage in Runtime Heap Header

The global arena base register (`X28` on ARM64, `R15` on x86-64) points to a 32 KiB reserved runtime header before the bump-allocated heap area (`X28 + 32768`). User global variables are indexed at `32 + slot * 8`.
We assign the dedicated slot at offset `32760` (`0x7FF8`, the exact maximum 64-bit load immediate in ARM64) to hold `g_stack_limit`.

At `_start`:
```text
initial_sp = SP (or FP after prologue setup)
stack_size = 8,372,224 (8176 KiB soft limit from getrlimit / fallback)
safety_headroom = 262,144 (256 KiB safety headroom before guard page)
stack_limit = initial_sp - (stack_size - safety_headroom)
*(X28 + 32760) = stack_limit
```

### 5.2 Low-Overhead Function Prologue Check

In every compiled function, at function entry before prologue frame allocation or stores:
```arm64
ldr x9, [x28, #32760]      ; load stack limit
add x9, x9, #total_frame   ; add required frame growth (16 + callee_saves + ssz)
cmp sp, x9                 ; compare current un-decremented SP against required bound
b.hi L_stack_ok            ; if sp > limit + total_frame, stack is safe (predicted taken)
bl __vir_stack_overflow    ; trap to non-allocating runtime stub (never returns)
L_stack_ok:
stp fp, lr, [sp, #-16]!    ; frame allocation proceeds only after check passes
...
```
On x86-64:
```x86
mov r11, qword ptr [r15 + 32760] ; load stack limit
mov rax, total_frame             ; total frame bytes (32 + ssz)
add r11, rax                     ; required bound
cmp rsp, r11                     ; compare un-decremented RSP
ja .L_stack_ok                   ; branch over trap call
call __vir_stack_overflow        ; trap to runtime stub
.L_stack_ok:
push rbp                         ; frame allocation proceeds only after check passes
...
```

### 5.3 Non-Allocating Stack Overflow Trap Stub

When `bl __vir_stack_overflow` is invoked:
- The stub does NOT touch `SP` or allocate stack.
- The diagnostic message `"virc: runtime error: call-stack exhaustion (stack overflow)\n"` is embedded adjacent to the code and referenced via PC-relative addressing (`adr x1, L_msg` / `lea rsi, [rip + L_msg]`).
- Syscall `write(2, msg, 58)` outputs to stderr.
- Syscall `exit(1)` terminates the process with clean status 1.

## 6. Design Decisions

### Decision 1: Dedicated Slot at Header Boundary `32760`
- **Decision:** Place `stack_limit` at `X28 + 32760` (`R15 + 32760`).
- **Rationale:** `32760` is `0xFFF * 8`, which fits into a single 12-bit unsigned immediate for 64-bit ARM64 `ldr x9, [x28, #32760]`. It sits at the very end of the 32 KiB header area, completely isolated from user global slots (`32 + slot * 8`), requiring zero additional runtime memory or register dedication.

### Decision 2: 256 KiB Redzone Headroom
- **Decision:** Reserve 256 KiB headroom between `stack_limit` and the OS guard page.
- **Rationale:** Ensures that when `sp <= stack_limit` triggers, the process is still comfortably inside valid, writable stack pages. This guarantees that diagnostic execution and syscall trap code cannot trigger a secondary fault.

### Decision 3: Zero-Stack-Allocation Trap Stub
- **Decision:** Implement `__vir_stack_overflow` without saving registers on the stack.
- **Rationale:** When stack exhaustion occurs, writing to the stack is hazardous. Using PC-relative `adr` and direct syscalls with registers ensures 100% signal-safe, deterministic termination.

## 7. Implementation Plan

### Phase 1 — IR and Runtime Stub Definition
- files: `compiler/src/ir/lir/lir.vri`, `compiler/src/lower/lir_codegen/rt_stubs_math/stub_emit.vri`, `compiler/src/lower/lir_codegen/rt_stubs_base.vri`
- changes: Define `LIR_RT_STACK_OVERFLOW`, implement non-allocating trap stub emitting diagnostic and clean exit.

### Phase 2 — Startup Stack Boundary Initialization
- files: `compiler/src/lower/lir_codegen.vri`, `compiler/src/lower/lir_codegen_x86.vri`
- changes: In `_start`, record initial stack pointer, compute safe stack limit, and store into `*(X28 + 32760)` / `*(R15 + 32760)`.

### Phase 3 — Backend Prologue Check
- files: `compiler/src/lower/lir_codegen/emit_func.vri`, `compiler/src/lower/lir_to_mc/arm64.vri`, `compiler/src/lower/lir_codegen_x86/emit_func.vri`, `compiler/src/lower/lir_to_mc/x86_64.vri`
- changes: Emit `cmp sp/rsp, stack_limit` and branch over trap call to `LIR_RT_STACK_OVERFLOW`.

### Phase 4 — Compiler Synchronization and Bootstrap Verification
- files: `compiler/generated/virc.vri`, `bin/virc`
- changes: Sync compiler bundle, rebuild stage 1 and stage 2, verify bit-exact fixed-point, promote compiler.

### Phase 5 — Test Verification
- files: `tests/opt/tail_call_test.vri`, `run_tests.sh`
- changes: Run `./bin/tail-call-test --virc ./bin/virc` and `./run_tests.sh 6` to confirm all 36 tests pass.

## 8. Compatibility

- Preserves 100% backwards compatibility for all standard programs with normal call stacks.
- Preserves bounded-stack behavior for direct tail-call optimization (`-O1..-O3`), where `SP` does not grow.
- Converts unexpected hard crashes (status 139) on non-tail stack exhaustion into informative diagnostics and status 1.

## 9. Migration

No migration required for existing Vir source code. Programs exceeding the stack limit will now provide clear, actionable diagnostics instead of silent SIGSEGV.

## 10. Validation Plan

- Execute `./bin/tail-call-test --virc ./bin/virc` to verify Test 12 passes (`[PASS] test_12_controlled_stack_exhaustion`).
- Execute `./run_tests.sh 6` to verify 36/36 PASS.
- Execute `./run_tests.sh 3` (16/16) and `./run_tests.sh 11` (68/68) to verify zero regression.
- Validate papers via `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Prologue code size growth | Low | Low | Only 16 bytes per function on ARM64; in-order branch prediction minimizes latency |
| False positive on unusual stack layouts | Very Low | High | Fallback limit is 8 MiB with 256 KiB headroom; `cmp sp, 0` does nothing if limit is 0 |
| Secondary fault during diagnostic print | Very Low | High | Trap stub does zero stack allocation and uses PC-relative data addressing |

## 12. Rollback Strategy

Revert changes in `emit_func.vri`, `_start` in `lir_codegen.vri`, and `rt_stubs_base.vri`, and re-synchronize compiler bundle.

## 13. Exit Criteria

- [x] `LIR_RT_STACK_OVERFLOW` stub implemented and linked.
- [x] `_start` initializes stack limit in runtime header.
- [x] ARM64 and x86-64 prologues check stack limit.
- [x] `tests/opt/fixtures/stack_overflow_nontail.vri` exits with status 1 and diagnostic string.
- [x] `./run_tests.sh 6` passes 36/36 (100%).
- [x] 3-stage bootstrap fixed-point verified.
- [x] `./paper validate` reports 0 errors.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0053_call_stack_exhaustion_terminates_native_programs_with_an_unclassified_sigsegv.md`
- `papers/VIRC/issues/VIRC-ISS-0024_production_direct_self_tail_call_optimization.md`
- `papers/VIRC/issues/VIRC-ISS-0052_eligible_non_tail_self_recursive_reductions_are_not_converted_to_bounded_stack_l.md`
- `papers/VIRC/reports/VIRC-RPT-0055_controlled_call_stack_exhaustion_detection_and_diagnostic_report.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial plan drafted for VIRC-ISS-0053 |
| 2026-10-09 | Completed controlled call-stack exhaustion implementation, bootstrap, and report VIRC-RPT-0055 |
| 2026-10-09 | Updated following review: dynamic getrlimit query at _start, early prologue check before frame growth, and MCInst lowering |
