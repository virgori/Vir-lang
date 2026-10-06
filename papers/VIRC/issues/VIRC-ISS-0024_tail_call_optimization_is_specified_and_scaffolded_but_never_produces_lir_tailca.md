---
id: "VIRC-ISS-0024"
type: "ISSUE"
domain: "VIRC"
title: "Tail-call optimization is specified and scaffolded but never produces LIR TailCall"
status: "CLOSED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "optimizer"
  - "mir-to-lir"
  - "lir"
  - "arm64"
  - "x86-64"
  - "riscv64"
  - "wasm"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0030"
  plans:
    - "VIRC-PLN-0014"
  reports:
    - "VIRC-RPT-0030"
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tail-recursion"
  - "tco"
  - "stack-space"
  - "optimizer"
  - "codegen"
  - "conformance"
---

# VIRC-ISS-0024 — Tail-call optimization is specified and scaffolded but never produces LIR TailCall

## 1. Summary

Vir specifies tail-call optimization (TCO) as conversion of direct recursive
tail calls to unconditional branches with O(1) stack use. The production
compiler defines `LirOp.TailCall`, and the ARM64 emitter contains a consumer
for that opcode, but no active pass creates it. Direct self-recursion in tail
position remains an ordinary `LirOp.Call` and emits `BL`, allocating a new
stack frame at every recursion level.

The registered fixture `tests/test_adv_023_tailcall.vri` therefore validates
only that 500 recursive calls happen to complete; it does not validate TCO.

## 2. Context

VIR-SPC-0017 section 1.2.1 and VIR-SPC-0018 section 1.2.1 list TCO as compiler
pass 11 with direct `B`/`JMP` emission. VIRC-SPC-0001 states that direct
recursive calls are transformed to immediate unconditional jumps, guaranteeing
O(1) stack space. VIRC-SPC-0004 also records TCO as implemented.

The behavior was inspected at commit
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` with installed self-hosted
`virc 4.1.0` on macOS ARM64. The existing tail-call fixture was compiled at
`-O0`, `-O1`, `-O2`, and `-O3`, and all four binaries retained a linked
self-call.

## 3. Expected Behavior

- At optimization levels where pass 11 is enabled, a direct self-call in tail
  position is converted to an argument update plus an unconditional branch or
  an equivalent loop form.
- The transformed function consumes O(1) call-stack space regardless of tail
  recursion depth.
- Non-tail calls and calls whose pending cleanup changes semantics are not
  transformed unsafely.
- Structural compiler tests prove that the production pipeline creates and
  consumes the tail-call representation; a small successful recursion alone
  is not a sufficient oracle.

## 4. Actual Behavior

- MIR-to-LIR lowering maps every `MirOp.Call` directly to `LirOp.Call`.
- The MIR optimization pipeline explicitly marks pass 11 as skipped.
- The backend dispatcher claims TCO marking occurs in `lir_codegen`, but the
  canonical source and generated bundle contain no producer of
  `LirOp.TailCall`.
- On ARM64, `countdown` emits a normal prologue and a recursive `BL`; every
  recursive step creates another frame.
- The only registered source fixture named for tail calls uses depth 500 and
  checks output `0`, so it passes without establishing constant stack use.

## 5. Reproduction

Use the existing registered fixture:

```vir
func countdown:
    in
        n: int
    if n <= 0 do
        out 0
    end
    out countdown(n - 1)
end.
```

Compile and run the default optimized path:

```sh
/Users/gengyang/Vir/bin/virc tests/test_adv_023_tailcall.vri \
  -O1 -o /tmp/vir_tailcall_probe
/tmp/vir_tailcall_probe
otool -tvV /tmp/vir_tailcall_probe
```

The program prints `0`, but the recursive function contains:

```text
0000000100000288  stp x29, x30, [sp, #-0x10]!
...
000000010000030c  bl  0x100000288
```

The same fixture was also compiled with `-O0`, `-O2`, and `-O3`; each binary
contained a linked branch back to the recursive function entry rather than an
unlinked tail branch.

## 6. Evidence

- CONFIRMED: `compiler/src/ir/mir/mir_opt_pipeline.vri:180-182` explicitly
  skips TCO at the MIR stage.
- CONFIRMED: `compiler/src/lower/lir_lower.vri:25-60` maps `MirOp.Call` to
  `LirOp.Call` and has no tail-position recognition or `TailCall` production.
- CONFIRMED: a repository-wide search of canonical compiler sources finds
  `LirOp.TailCall` only in its enum/name support, liveness termination handling,
  ARM64 emission, and instruction classification. No constructor, rewrite, or
  pass creates the opcode.
- CONFIRMED: the synchronized generated compiler bundle mirrors the same
  consumer-only state and the same skipped pass comment.
- CONFIRMED: ARM64 disassembly at `-O0`, `-O1`, `-O2`, and `-O3` contains a
  linked recursive branch (`BL`) after a frame-allocating prologue.
- CONFIRMED: `tests/test_adv_023_tailcall.vri` recurses only 500 levels and
  asserts output, not stack complexity or machine-code structure.
- CONFIRMED: `tests/bootstrap_codegen/cg_optimizer_tco.vri` manually rewrites a
  synthetic integer buffer and implements its million-step examples as loops;
  it does not exercise production MIR/LIR TCO.
- OBSERVED: the ARM64 emitter has a `LirOp.TailCall` branch, but it is
  unreachable from normal production lowering with the inspected sources.
- OBSERVED: no corresponding `LirOp.TailCall` consumer was found in the active
  x86-64, RISC-V, or Wasm emitters.

## 7. Scope

### Affected

- production tail-position analysis and call classification;
- MIR-to-LIR lowering and pre-register-allocation LIR optimization;
- direct self-recursive calls and their argument remapping;
- ARM64, x86-64, RISC-V, and Wasm backend support;
- optimizer tracing and registered structural/runtime conformance tests.

### Not affected / Unknown

- ordinary recursion is accepted and produces correct results at shallow depth;
- non-tail recursion is not eligible for constant-stack transformation;
- NOT_VERIFIED: mutual/sibling-call elimination as a normative language
  requirement;
- NOT_VERIFIED: the exact depth at which current binaries exhaust stack on each
  supported host;
- NOT_VERIFIED: tail calls crossing `ensure`, `revert`, arena cleanup, or other
  lifetime-sensitive boundaries.

## 8. Impact

Programs written in the documented tail-recursive style consume stack linearly
instead of the specified constant space and can fail with stack exhaustion at
inputs that should be safe under the compiler contract. The current tests and
VIRC-SPC-0004 status also report a capability that production binaries do not
have. This is classified S1 because it violates an explicit core compiler
resource guarantee and can turn otherwise valid deep computations into process
failure. P1 requests near-term correction without treating all recursion as
broken.

## 9. Preliminary Analysis

- CONFIRMED: the production pipeline has a defined tail-call opcode and partial
  backend scaffolding but no active producer.
- CONFIRMED: the existing tail-call fixture is a semantic recursion smoke test,
  not a TCO conformance test.
- CONFIRMED: optimization level does not change the recursive `BL` behavior in
  the inspected ARM64 output.
- HYPOTHESIS: a pre-register-allocation LIR pass can recognize a terminal
  `SetArg*`, self `Call`, result move, and `Ret` sequence and rewrite it safely
  after proving that no cleanup or exceptional edge remains pending.
- NOT_VERIFIED: whether canonical tail-position identity should instead be
  preserved earlier in typed MIR to avoid reconstructing it from LIR sequences.
- NOT_VERIFIED: cross-function sibling/mutual TCO and indirect tail calls.

## 10. Acceptance Criteria

- [x] The production pipeline recognizes direct self-calls in proven tail
  position at every optimization level where TCO is specified to run.
- [x] Structural MIR/LIR tests show a real production transformation to
  `LirOp.TailCall` or an explicitly documented equivalent loop form.
- [x] ARM64 disassembly uses an unlinked branch or loop backedge and does not
  allocate one additional frame per recursive step.
- [x] A registered runtime fixture executes at least 1,000,000 direct tail
  calls with bounded stack usage and the correct result.
- [x] Negative fixtures prove that non-tail recursion and calls with pending
  cleanup are not transformed unsafely.
- [x] Argument permutation, register spills, more than register-argument-count
  parameters, return values, and error propagation retain correct semantics.
- [x] ARM64, x86-64, RISC-V, and Wasm either pass the same structural/runtime
  contract or have explicit linked target-limitation ISSUEs.
- [x] Optimizer tracing reports pass 11 only when a real pass executes; stale
  comments and capability claims are corrected from implementation evidence.
- [x] Generated compiler sources are synchronized from canonical sources and
  fixed-point self-host verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0030

### Plans

- VIRC-PLN-0014

### Reports

- VIRC-RPT-0030

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from production source inspection and ARM64 disassembly at O0-O3 |
| 2026-10-04 | Linked VIRC-PLN-0014 |
| 2026-10-04 | Linked VIRC-RPT-0030 |
| 2026-10-04 | Verified full acceptance criteria across tests, fixed point, and closed as RESOLVED |
| 2026-10-04 | Registered the 9-test TCO contract suite in test runner group 6 and made its shared x86-64 fixture self-contained |
| 2026-10-04 | Closed after accepted verification report, clean registered regression suite, and explicit VIRC-ISS-0030 follow-up for RISC-V and Wasm limitations |
