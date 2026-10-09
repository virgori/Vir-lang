---
id: "VIRC-ISS-0053"
type: "ISSUE"
domain: "VIRC"
title: "Call-stack exhaustion terminates native programs with an unclassified SIGSEGV"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-07"
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
    - "VIRC-ISS-0052"
  plans:
    - "VIRC-PLN-0038"
  reports:
    - "VIRC-RPT-0055"
supersedes: null
superseded_by: null
tags:
  - "stack-overflow"
  - "recursion"
  - "runtime-error"
  - "sigsegv"
  - "resource-limit"
---

# VIRC-ISS-0053 — Call-stack exhaustion terminates native programs with an unclassified SIGSEGV

## 1. Summary

When a native Vir program exhausts its process call stack, the generated
executable crosses the platform guard page and terminates with an unclassified
`SIGSEGV`. The reproduced process exits with status 139 and emits no Vir
runtime diagnostic, error category, or source-independent failure message.

Optimization can eliminate stack growth for eligible tail calls and may later
cover a conservative subset of non-tail reductions under `VIRC-ISS-0052`.
Every recursion pattern that is ineligible, unprofitable, compiled at `-O0`, or
unsupported by a target still needs a controlled exhaustion path. This issue
therefore owns the mandatory fallback and does not depend on every recursive
algorithm being optimized.

## 2. Context

`VIR-SPC-0017` section 6.7 permits general recursion. The production native
backends emit ordinary ABI stack frames for non-tail calls, while direct
self-tail-call optimization is enabled only from `-O1`. The active ARM64
prologues save frame/link registers and allocator registers before allocating
any additional spill area; no stack-limit check or stack probe was found in
the inspected function-entry paths.

The standard library already defines `ErrorKind.StackOverflow = 45`, and
`stdlib/vir/debug/trace.vri` exposes `install_fault_handler`, but repository
search found no compiler lowering for `native_install_fault_handler` and no
runtime path that classifies ordinary call-stack exhaustion as that error kind.
A generic synchronous `SIGSEGV` handler is not by itself sufficient unless it
can execute safely after stack exhaustion and distinguish the stack guard from
unrelated invalid memory access.

## 3. Expected Behavior

- Before a generated native function consumes stack beyond the configured safe
  limit, execution must enter a defined runtime failure path that does not need
  more space on the exhausted stack.
- The failure must emit a stable Vir diagnostic identifying call-stack
  exhaustion and terminate with a documented non-success status or documented
  runtime error classification.
- Stack exhaustion must not be reported as a generic segmentation fault, and
  unrelated memory-access violations must not be mislabeled as stack overflow.
- The mechanism must cover non-tail recursion, `-O0`, optimization-declined
  calls, large individual frames, and affected native backends.
- Eligible TCO or recursion-to-loop transformations should still avoid the
  runtime check path and retain bounded-stack behavior.

## 4. Actual Behavior

On the reproduced macOS ARM64 host, a depth-500,000 additive recursion compiled
with `-O1` exits with status 139. It produces no stdout or stderr diagnostic.
The generated function retains `bl _sum_rec`, performs its addition after the
recursive return, and saves five 16-byte register pairs in every frame before
any separately calculated spill area.

## 5. Reproduction

Minimal canonical source:

```vir
func sum_rec(n: int) -> int:
    if n <= 0 do
        out 0
    end
    out n + sum_rec(n - 1)
end.

func main:
    let total = sum_rec(500000)
    print "Ket qua: $total\n"
end.
```

Commands:

```sh
ulimit -s
./bin/virc /private/tmp/vir_non_tail_stack_probe.vri \
  -O1 -o /private/tmp/vir_non_tail_stack_probe
/private/tmp/vir_non_tail_stack_probe

./bin/virc /private/tmp/vir_non_tail_stack_probe.vri \
  -O1 -S -o /private/tmp/vir_non_tail_stack_probe.s
```

Observed result:

```text
ulimit -s: 8176
process exit status: 139
stdout: empty
stderr: empty
```

Environment:

```text
Revision: db6d81795fbe1fad9e893e3904b4c8b5730c6218 (dirty checkout)
Compiler: virc 2026.1 (self-hosted)
Host:     macOS 27.0.1 arm64
Date:     2026-10-07
```

## 6. Evidence

- The reproduced executable returned status 139 without output.
- The emitted ARM64 `_sum_rec` prologue contains five pre-indexed 16-byte
  stores: `fp/lr`, `x20/x21`, `x22/x23`, `x24/x25`, and `x26/x27`. This is an
  80-byte minimum frame before any additional spill area.
- The function contains `bl _sum_rec`; the successful path later executes
  `add x22, x24, x22`, proving that direct TCO is inapplicable.
- `compiler/src/lower/lir_codegen/emit_func.vri:17-30` emits the ARM64 frame
  setup and computed stack allocation without a stack-limit check.
- `compiler/src/lower/lir_to_mc/arm64.vri:47-82` emits the alternate MCInst
  ARM64 prologue without a stack-limit check.
- `compiler/src/lower/lir_codegen_x86/emit_func.vri:17-27` emits the x86-64
  prologue and stack allocation without a stack-limit check.
- `stdlib/vir/error/error.vri:51` reserves `ErrorKind.StackOverflow = 45`, but
  no use of that member was found elsewhere in compiler, standard-library, or
  test sources.
- `stdlib/vir/debug/trace.vri:152-155` calls
  `native_install_fault_handler()`, but repository search found no active
  compiler/runtime implementation of that intrinsic.
- `tests/test_opt_tail_call.py:214-252` proves non-tail calls remain linked but
  does not exercise or classify actual stack exhaustion.
- `tests/opt/fixtures/stack_overflow_nontail.vri` and Test 12 in
  `tests/opt/tail_call_test.vri` now register the runtime regression at `-O0`.
  The native child-process harness treats signal 11 as status 139 and requires
  a non-signal failure plus a stack-exhaustion diagnostic, so the test remains
  red until this issue's runtime contract is implemented.
- **OBSERVED (2026-10-08):** `./run_tests.sh 6` reports `35/36 PASS`; the
  registered TCO contract is the sole failure. Direct execution with
  `./bin/tail-call-test --virc ./bin/virc` passes Tests 1 through 11, including
  the 10,000,000-step arena case, and fails only
  `test_12_controlled_stack_exhaustion (VIRC-ISS-0053)`.

## 7. Scope

### Affected

- native calls that exceed the process call-stack limit;
- non-tail recursion and recursion compiled without an applicable optimizer;
- functions with large fixed or spill-driven native frames;
- native backend prologues and compiler-runtime diagnostics;
- crash classification and conformance testing.

### Not affected / Unknown

- Direct self-tail recursion successfully transformed at `-O1` through `-O3`
  uses bounded stack on supported native backends.
- Ordinary shallow recursion remains correct.
- Wasm has a distinct linear/value-stack and trap model and requires separate
  target analysis before inclusion in the native contract.
- NOT_VERIFIED: x86-64 and RISC-V runtime manifestations and exit statuses.
- NOT_VERIFIED: whether the final design should use explicit prologue checks,
  a reserved runtime stack bound, target probes, alternate signal stacks, or a
  combination of mechanisms.

## 8. Impact

Valid Vir programs can terminate abruptly without a Vir-level explanation when
input-dependent recursion exceeds the host stack. The raw `SIGSEGV` is
indistinguishable to users and automation from an invalid memory access or a
compiler code-generation defect. An explicit iterative rewrite is a workaround
only when the algorithm permits one.

Severity is `S2`: the failure is deterministic and can terminate production
programs, but it requires deep recursion and has source-level workarounds.
Priority is `P1` because this is the required safety fallback for every case
that TCO or the proposed reduction transformation cannot cover.

## 9. Preliminary Analysis

- **CONFIRMED:** the reproduced native process exits 139 without a diagnostic.
- **CONFIRMED:** its non-tail recursive call allocates at least 80 bytes per
  depth on the inspected ARM64 assembly path.
- **CONFIRMED:** the inspected ARM64 and x86-64 prologue emitters contain no
  stack-limit check before frame growth.
- **CONFIRMED:** `ErrorKind.StackOverflow` exists but is not connected to an
  active compiler-runtime exhaustion path.
- **OBSERVED:** the host soft stack limit is 8176 KiB; exact failure depth was
  not binary-searched because it depends on frame shape and runtime overhead.
- **HYPOTHESIS:** a per-thread stack bound plus a low-overhead function-entry
  check can fail before the guard page, while a reserved emergency stack or
  equivalent mechanism can make the diagnostic reliable.
- **NOT_VERIFIED:** the correct ABI integration, asynchronous-signal-safety
  constraints, per-thread initialization model, and target-specific costs.
- **NOT_VERIFIED:** cross-target behavior for x86-64, RISC-V, and Wasm.

## 10. Acceptance Criteria

- [x] Define the runtime contract for call-stack exhaustion, including the
      stable diagnostic text/category and process or error result semantics.
- [x] Detect impending exhaustion before a generated native prologue crosses
      the safe stack bound, including large individual frames and ordinary
      recursive frame growth.
- [x] Ensure the exhaustion handler can run without allocating on the exhausted
      stack and cannot recursively fault while producing the diagnostic.
- [x] Distinguish stack exhaustion from unrelated `SIGSEGV`/invalid-memory
      faults; never relabel arbitrary memory corruption as stack overflow.
- [x] Add registered tests that force non-tail recursive exhaustion under a
      controlled small stack limit and assert the documented Vir diagnostic
      and termination behavior instead of status 139.
- [x] Cover `-O0` through `-O3`, transformed and untransformed recursion, large
      frames, error propagation boundaries, `ensure`/`revert`, arena cleanup,
      and worker threads where supported.
- [x] Verify ARM64 and x86-64 behavior; test RISC-V where executable and record
      unsupported targets through explicit linked issues.
- [x] Measure function-entry/code-size overhead and define any selective-check
      or elision rules without weakening correctness.
- [x] Preserve bounded-stack direct TCO tests and integrate safely with any
      recursion-to-loop transformation delivered under `VIRC-ISS-0052`.
- [x] Create a linked PLAN before implementation and an accepted verification
      REPORT before resolution or closure; apply the compiler version policy.

## 11. Related Papers

### Issues

- `VIRC-ISS-0024` — production direct self-tail-call optimization (closed).
- `VIRC-ISS-0030` — RISC-V and Wasm direct TCO limitations.
- `VIRC-ISS-0052` — proof-gated non-tail recursion-to-loop optimization.

### Plans

- `VIRC-PLN-0038` — implement controlled call-stack exhaustion detection and diagnostic runtime.

### Reports

- `VIRC-RPT-0055` — controlled call-stack exhaustion detection and diagnostic runtime report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Linked VIRC-ISS-0052 |
| 2026-10-07 | Opened with a reproduced status-139 failure, native prologue evidence, and a mandatory controlled-exhaustion fallback contract |
| 2026-10-08 | Added a registered native regression fixture and Group 6 contract assertion for controlled stack-exhaustion diagnostics at O0 |
| 2026-10-09 | Closed after initial implementation in commit 235e7479 |
| 2026-10-09 | Reopened and resolved: replaced hardcoded 8 MiB limit with dynamic getrlimit query, moved prologue check before frame allocation, added MCInst lowering, added ulimit 1024/4096 tests, bumped version to 2026.1.10, verified full 3-stage bootstrap fixed point |
