---
id: "VIRC-ISS-0030"
type: "ISSUE"
domain: "VIRC"
title: "RISC-V and Wasm backends lack full tail-call optimization support"
status: "TRIAGED"
severity: "S2"
priority: "P2"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "lir"
  - "codegen"
  - "riscv64"
  - "wasm"
related:
  issues:
    - "VIRC-ISS-0024"
  plans:
    - "VIRC-PLN-0014"
  reports:
    - "VIRC-RPT-0030"
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tco"
  - "riscv64"
  - "wasm"
  - "target-limitation"
---

# VIRC-ISS-0030 — RISC-V and Wasm backends lack full tail-call optimization support

## 1. Summary

The RISC-V (`linux-riscv64`) and WebAssembly (`wasm32-wasi`) backend code generators lack production
support for low-level LIR tail-call optimization (`LirOp.TailCall`) and corresponding control-flow
lowering. While ARM64 and x86-64 support full tail-recursion elimination in $O(1)$ stack space,
targeting RISC-V or Wasm fails during machine code generation or drops stack arguments.

## 2. Context

During the resolution of `VIRC-ISS-0024` and implementation of `VIRC-PLN-0014`, acceptance criteria
specified:
"ARM64, x86-64, RISC-V, and Wasm either pass the same structural/runtime contract or have explicit
linked target-limitation ISSUEs."

Source inspection and target compilation probes reveal:
1. `compiler/src/lower/lir_codegen_riscv.vri:318-328` only implements argument assignment for up to
   8 register parameters (`RV_A0..RV_A7`) and drops arguments with index $\ge 8$. Furthermore, the
   RISC-V backend fails with `[E-RISCV-UNSUPPORTED]: linux-riscv64 backend cannot lower LIR op 11 (detail 5)`
   when compiling standard relational comparisons (`<=`).
2. `compiler/src/lower/lir_codegen_wasm.vri:23-40` (`wasm_lir_validate_supported`) excludes `LirOp.TailCall`.
   Additionally, WebAssembly requires structured control flow (`loop`/`block`/`br`) or the WebAssembly
   Tail Calls proposal (`return_call`/`return_call_indirect`), failing compilation with
   `[E-WASM-UNSUPPORTED]: wasm32-wasi-p1 backend cannot lower LIR op 10`.

## 3. Expected Behavior

- Programs targeting `linux-riscv64` and `wasm32-wasi` with tail-recursive functions should either:
  1. Transform tail calls into $O(1)$ stack space branches/calls matching the target's ABI.
  2. Or, if tail call optimization is not yet implemented for that backend, emit a clean diagnostic
     or fall back safely to linked calls without unhandled opcode panics.

## 4. Actual Behavior

- `bin/virc tests/test_adv_023_tailcall.vri --target linux-riscv64` aborts with
  `virc: error [E-RISCV-UNSUPPORTED]: linux-riscv64 backend cannot lower LIR op 11 (detail 5)`.
- `bin/virc tests/test_adv_023_tailcall.vri --target wasm32-wasi` aborts with
  `virc: error [E-WASM-UNSUPPORTED]: wasm32-wasi-p1 backend cannot lower LIR op 10`.
- Functions with $>8$ arguments on RISC-V silently drop stack argument updates in `SetArg`.

## 5. Reproduction

Compile the standard tail call fixture for each target:

```sh
bin/virc tests/test_adv_023_tailcall.vri --target linux-riscv64 -o /tmp/test_riscv.o
bin/virc tests/test_adv_023_tailcall.vri --target wasm32-wasi -o /tmp/test_wasm.wasm
```

Both commands fail during backend code generation.

## 6. Evidence

- `compiler/src/lower/lir_codegen_riscv.vri:318`: `if arg_idx >= 0 and arg_idx < 8 do` has no `else`
  branch to handle stack arguments (`>8` parameters).
- `compiler/src/lower/lir_codegen_wasm.vri:33`: `wasm_lir_validate_supported` checks supported opcodes
  and does not include `LirOp.TailCall`.
- Command outputs confirm `E-RISCV-UNSUPPORTED` and `E-WASM-UNSUPPORTED`.

## 7. Scope

### Affected

- `compiler/src/lower/lir_codegen_riscv.vri` (RISC-V argument passing and comparison lowering).
- `compiler/src/lower/lir_codegen_wasm.vri` (Wasm LIR validation and structured tail call lowering).

### Not affected / Unknown

- Native ARM64 and x86-64 backends are fully supported and verified.
- Semantic analysis, AST lowering, and MIR passes are target-agnostic and unaffected.

## 8. Impact

Cross-compilation of tail-recursive Vir programs to RISC-V or WebAssembly fails at the codegen stage.

## 9. Preliminary Analysis

- CONFIRMED: RISC-V and Wasm backends have incomplete LIR lowering for conditional branches,
  comparisons, and tail calls.
- HYPOTHESIS: RISC-V requires extending `SetArg` to write to `[s0 + stack_offset]` and completing
  comparison emission.
- HYPOTHESIS: Wasm requires wrapping the function body in a `loop` block with `br 0` or emitting
  Wasm `return_call`.

## 10. Acceptance Criteria

- [ ] RISC-V backend supports $>8$ arguments on stack in `SetArg` and `TailCall`.
- [ ] RISC-V backend completes lowering for relational comparisons and `TailCall`.
- [ ] Wasm backend lowers `TailCall` either via WebAssembly `return_call` or structured `loop`/`br`.
- [ ] Automated regression tests pass for RISC-V and Wasm targets.

## 11. Related Papers

### Issues

- `papers/VIRC/issues/VIRC-ISS-0024_tail_call_optimization_is_specified_and_scaffolded_but_never_produces_lir_tailca.md`

### Plans

- `papers/VIRC/plans/VIRC-PLN-0014_implement_production_tail_call_optimization_in_lir.md`

### Reports

- `papers/VIRC/reports/VIRC-RPT-0030_production_tail_call_optimization_implementation_and_verification_report.md`

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created target-limitation issue tracking RISC-V and Wasm backend gaps for TCO |
