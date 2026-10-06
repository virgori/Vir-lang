---
id: "VIRC-ISS-0031"
type: "ISSUE"
domain: "VIRC"
title: "x86-64, RISC-V, and Wasm backends lack native floating-point print runtime stubs"
status: "TRIAGED"
severity: "S2"
priority: "P2"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "backend"
  - "codegen"
components:
  - "lir-codegen"
  - "x86_64"
  - "riscv64"
  - "wasm32"
related:
  issues:
    - "VIRC-ISS-0022"
  plans:
    - "VIRC-PLN-0015"
  reports:
    - "VIRC-RPT-0031"
supersedes: null
superseded_by: null
tags:
  - "float"
  - "print"
  - "runtime-stub"
  - "x86_64"
  - "riscv"
  - "wasm"
  - "backend"
---

# VIRC-ISS-0031 — x86-64, RISC-V, and Wasm backends lack native floating-point print runtime stubs

## 1. Summary

The compiler lowers floating-point print expressions (`LiteralFloat`, `float`, `f32`, `f64`) to `MIR_INTR_PRINT_FLOAT` (LIR runtime stub 112). While ARM64 implements `emit_lir_rt_print_float_stub` to format floating-point numbers into decimal strings, the x86-64, RISC-V, and Wasm backends lack implementation of this runtime stub.

## 2. Context

During verification of `VIRC-ISS-0022` (dispatching explicit `f32` and `f64` types to `MIR_INTR_PRINT_FLOAT`), cross-target compilation was evaluated across all four supported backends (macOS ARM64, Linux x86-64, Linux RISC-V 64, and Wasm32).

## 3. Expected Behavior

All backends should either emit native formatting code for `MIR_INTR_PRINT_FLOAT` or delegate to a standard C runtime library / environment function (such as `printf("%g", ...)` or WASI fd_write).

## 4. Actual Behavior

- **macOS ARM64**: Fully supported via native `emit_lir_rt_print_float_stub`.
- **Linux x86-64**: `compiler/src/lower/lir_codegen_x86/intrinsics.vri` does not handle `MIR_INTR_PRINT_FLOAT`. The stub emitted at index 112 in `stub_emit.vri` is an empty `retq`, so no output is produced.
- **Linux RISC-V 64**: `compiler/src/lower/lir_codegen_riscv.vri` throws `error [E-RISCV-UNSUPPORTED]: linux-riscv64 backend cannot lower LIR op 17 (detail 69)`.
- **Wasm32**: `compiler/src/lower/lir_codegen_wasm.vri` throws `error [E-WASM-UNSUPPORTED]: wasm32-wasi-p1 backend cannot lower LIR op 17 (detail 69)`.

## 5. Reproduction

Compile a program containing `print 212.0` with `--target linux-riscv64` or `--target wasm32`:

```sh
/Users/gengyang/Vir-3.0/bin/virc /tmp/repro_f64_print.vri --target linux-riscv64 -o /tmp/repro_riscv
/Users/gengyang/Vir-3.0/bin/virc /tmp/repro_f64_print.vri --target wasm32 -o /tmp/repro_wasm
```

## 6. Evidence

- CONFIRMED: `compiler/src/lower/lir_codegen/calls.vri:226` defines `emit_lir_rt_print_float_stub` exclusively for ARM64 machine code buffers.
- CONFIRMED: `compiler/src/lower/lir_codegen_x86/intrinsics.vri:304-315` only checks `MIR_INTR_PRINT` and `MIR_INTR_PRINT_STR`.
- CONFIRMED: `compiler/src/lower/lir_codegen_riscv.vri:642` only handles `MIR_INTR_PRINT`.
- CONFIRMED: `compiler/src/lower/lir_codegen_wasm.vri:98` excludes `MIR_INTR_PRINT_FLOAT` from `supported` opcode set.

## 7. Scope

### Affected

- Target backends: `linux-x86_64`, `linux-riscv64`, `wasm32`.
- Execution of programs printing floating-point values on these non-ARM64 platforms.

### Not affected / Unknown

- macOS ARM64 (fully functional).
- Integer and string print intrinsics across all targets.
- Floating-point calculations, arithmetic, and calling conventions on non-ARM64 targets.

## 8. Impact

Cross-compiling Vir code that contains `print <float>` fails at compile time for RISC-V and Wasm, and produces silent no-op printing on x86-64.

## 9. Preliminary Analysis

- CONFIRMED: Non-ARM64 backends need corresponding runtime stub implementations or standard library / libc bridge calls for IEEE-754 decimal string conversion.

## 10. Acceptance Criteria

- [ ] `MIR_INTR_PRINT_FLOAT` is implemented for `linux-x86_64` (either native SSE2 stub or libc printf).
- [ ] `MIR_INTR_PRINT_FLOAT` is supported in `linux-riscv64` lowering.
- [ ] `MIR_INTR_PRINT_FLOAT` is supported in `wasm32` lowering.
- [ ] Cross-target test suite verifies identical output across all four backends.

## 11. Related Papers

### Issues

- `VIRC-ISS-0022` — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads.

### Plans

- `VIRC-PLN-0015` — Dispatch explicit f32 and f64 types to floating print intrinsic.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Initial issue created and triaged to track non-ARM64 float print limitations |
| 2026-10-04 | Linked VIRC-ISS-0022 |
| 2026-10-04 | Linked VIRC-PLN-0015 |
| 2026-10-04 | Linked VIRC-RPT-0031 |
