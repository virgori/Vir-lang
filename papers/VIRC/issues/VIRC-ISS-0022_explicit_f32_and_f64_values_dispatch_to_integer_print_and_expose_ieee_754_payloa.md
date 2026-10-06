---
id: "VIRC-ISS-0022"
type: "ISSUE"
domain: "VIRC"
title: "Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
components:
  - "type-system"
  - "ast-to-mir"
  - "print-runtime"
  - "arm64"
  - "tests"
related:
  issues:
    - "VIR-ISS-0002"
    - "VIRC-ISS-0016"
    - "VIRC-ISS-0023"
    - "VIRC-ISS-0031"
  plans:
    - "VIRC-PLN-0015"
  reports:
    - "VIRC-RPT-0031"
supersedes: null
superseded_by: null
tags:
  - "float"
  - "f32"
  - "f64"
  - "print"
  - "type-dispatch"
  - "ieee-754"
  - "correctness"
---

# VIRC-ISS-0022 — Explicit f32 and f64 values dispatch to integer print and expose IEEE-754 payloads

## 1. Summary

The compiler preserves the IEEE-754 payload of explicit `f32` and `f64`
values, but `print` lowers those values through the integer print intrinsic.
For example, a function returning `212.0` as `f64` prints
`4641663103447072768`, the unsigned decimal representation of the binary64
payload `0x406a800000000000`. The canonical `float` spelling prints correctly.

## 2. Context

The defect was isolated while investigating an apparent numerical failure in a
tensor-derived `f64` result. The exact bit pattern proved that the computed
value and return transport were intact, while presentation selected the wrong
runtime path. The audit used installed `virc 4.1.0`, the backed-up 4.0.0
compiler, and the current repository compiler at commit
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` on macOS ARM64.

VIR-SPC-0016 classifies `float` as an IEEE-754 8-byte primitive, while active
compiler and tensor paths also admit explicit `f32` and `f64` spellings. Once a
value has resolved to a floating type, output lowering must preserve that
semantic category rather than branch on one textual alias.

## 3. Expected Behavior

- `print` dispatches `float`, `f32`, and `f64` expressions to floating-point
  formatting according to their resolved semantic type.
- Direct literals, variables, casts, call results, indexed values, and spilled
  values produce the same numeric output for the same floating value.
- Internal raw-bit transport remains an implementation detail and is never
  exposed as integer output unless the source explicitly converts or reinterprets
  the value as an integer.

## 4. Actual Behavior

- `print 212.0` and values declared as `float` print `212.0`.
- A direct result from `func return_f64() -> f64`, and the same result assigned
  to `let value: f64`, print `4641663103447072768`.
- AST-to-MIR lowering recognizes a literal float or the exact inferred type
  name `"float"`, but omits `"f32"` and `"f64"`; the fallback is the integer
  print intrinsic.
- The behavior is identical in the tested 4.0.0 and 4.1.0 compilers, so current
  evidence establishes a pre-existing uncovered defect rather than a 4.1-only
  regression.

## 5. Reproduction

Save the following source as `/tmp/repro_f64_print.vri`:

```vir
func return_f64() -> f64:
    out 212.0
end.

func return_float() -> float:
    out 212.0
end.

func main:
    print 212.0
    print return_f64()
    let value_f64: f64 = return_f64()
    print value_f64
    print return_float()
    let value_float: float = return_float()
    print value_float
end.
```

Compile and run:

```sh
/Users/gengyang/Vir/bin/virc /tmp/repro_f64_print.vri \
  -o /tmp/repro_f64_print
/tmp/repro_f64_print
```

Observed output:

```text
212.0
4641663103447072768
4641663103447072768
212.0
212.0
```

## 6. Evidence

- CONFIRMED: `4641663103447072768` is hexadecimal
  `0x406a800000000000`, the IEEE-754 binary64 encoding of `212.0`.
- CONFIRMED: `compiler/src/lower/ast_to_mir/layout/type_infer.vri:178-182`
  returns the declared callable result spelling, including `f64`.
- CONFIRMED: both active print-lowering paths in
  `compiler/src/lower/ast_to_mir/stmt.vri:640-648` and
  `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri:87-95` select
  `MIR_INTR_PRINT_FLOAT` only for literal floats or the exact name `float`.
- CONFIRMED: `compiler/src/lower/lir_codegen/intrinsics.vri:607-613` passes
  the scalar payload through `x0` to the float print stub, and
  `compiler/src/lower/lir_codegen/calls.vri:250-251` explicitly transfers those
  bits into `d0`. Therefore `x0` transport is intentional in the current
  internal ABI and is not itself evidence of a caller/callee register mismatch.
- CONFIRMED: installed 4.1.0, backed-up 4.0.0, and current repository binaries
  produced the same five-line output above.
- OBSERVED: no registered regression fixture directly prints an explicit
  `f32` or `f64` call result and checks its numeric text.

## 7. Scope

### Affected

- AST-to-MIR dispatch for `print` statements;
- explicit `f32` and `f64` variables and callable results;
- any target/backend consuming the incorrectly selected generic integer print
  intrinsic;
- regression coverage for floating aliases, calls, spills, and optimization
  levels.

### Not affected / Unknown

- arithmetic and function-return payload transport in the demonstrated case;
- dense tensor storage, indexing, matmul, and FMA correctness, independently
  tracked by VIRC-ISS-0016;
- explicit casts to integer, which are expected to print integer values;
- NOT_VERIFIED: every supported target, special IEEE-754 values, and all
  formatting/rounding edge cases.

## 8. Impact

Accepted programs can display a numerically correct floating value as an
unrelated large integer. This can falsely implicate arithmetic, tensors, or the
calling convention and makes CLI output unsuitable as a correctness oracle for
explicit `f32`/`f64` values. The defect is scoped and has a `float`-spelling
workaround, so it is classified S2/P1 rather than a release-wide S1 failure.

## 9. Preliminary Analysis

- CONFIRMED: type recovery preserves the exact callable return spelling, but
  print lowering compares only against the textual alias `float`.
- CONFIRMED: both duplicated native AST-to-MIR print paths contain the same
  omission, and the generated compiler bundle contains the same conditions.
- CONFIRMED: adding `: f64` to the local variable does not work around the
  defect because the explicit spelling remains `f64`.
- HYPOTHESIS: dispatching on canonical semantic type identity rather than raw
  strings will prevent the same alias omission in print and other
  representation-sensitive consumers.
- NOT_VERIFIED: whether `f32` formatting requires a distinct conversion path
  before the existing binary64-oriented formatter.

## 10. Acceptance Criteria

- [x] `print` classifies `float`, `f32`, and `f64` through canonical resolved
  type metadata rather than a one-alias string comparison.
- [x] Direct calls and explicitly typed locals print `212.0`, not its raw
  integer payload, for all supported floating spellings.
- [x] Registered tests cover literals, variables, calls, casts, indexed
  values, and register-pressure spills at O0-O3.
- [x] Tests cover negative zero, finite negative/fractional values, infinities,
  and NaNs with a documented formatting oracle.
- [x] Integer output and explicit float-to-int casts remain unchanged.
- [x] ARM64, x86-64, RISC-V, and Wasm either pass the same semantic test matrix
  or have explicitly tracked target limitations.
- [x] Generated compiler sources are synchronized from canonical sources and
  fixed-point self-host verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIR-ISS-0002 — canonical typed identity and typed MIR metadata hardening.
- VIRC-ISS-0016 — separate dense-tensor dtype/layout correctness issue exposed
  during the same investigation; it does not own this print defect.
- VIRC-ISS-0031 — x86-64, RISC-V, and Wasm backends lack native floating-point print runtime stubs.

### Plans

- VIRC-PLN-0015 — Dispatch explicit f32 and f64 types to floating print intrinsic.

### Reports

- VIRC-RPT-0031 — Explicit f32 and f64 print dispatch implementation and verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from deterministic f64 print reproduction and source inspection |
| 2026-10-04 | Linked VIR-ISS-0002 |
| 2026-10-04 | Linked VIRC-ISS-0016 |
| 2026-10-04 | Linked VIRC-ISS-0023 |
| 2026-10-04 | Linked VIRC-PLN-0015 |
| 2026-10-04 | Linked VIRC-ISS-0031 |
| 2026-10-04 | Linked VIRC-RPT-0031 |
| 2026-10-04 | Completed implementation and verification; marked RESOLVED |
| 2026-10-04 | Corrective audit verified registered 8-case coverage including reference variants, confirmed bootstrap fixed point, and marked CLOSED |
