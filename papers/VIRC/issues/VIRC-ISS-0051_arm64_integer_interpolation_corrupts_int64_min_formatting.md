---
id: "VIRC-ISS-0051"
type: "ISSUE"
domain: "VIRC"
title: "ARM64 integer interpolation corrupts INT64_MIN formatting"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "compiler"
  - "runtime"
components:
  - "arm64-backend"
  - "compiler-runtime"
  - "string-interpolation"
  - "stdlib-format"
  - "conformance-tests"
related:
  issues: []
  plans:
    - "VIRC-PLN-0030"
  reports:
    - "VIRC-RPT-0047"
supersedes: null
superseded_by: null
tags:
  - "integer-formatting"
  - "int64-min"
  - "backend-parity"
  - "boundary-value"
---

# VIRC-ISS-0051 — ARM64 integer interpolation corrupts INT64_MIN formatting

## 1. Summary

On macOS ARM64, the native executable path formats the signed 64-bit minimum
value incorrectly when an integer is converted for string interpolation. A
direct integer `print` renders `-9223372036854775808`, while interpolation of
the same runtime value emits non-decimal punctuation and digits.

The active ARM64 direct machine-code emitter negates a negative operand and then
uses signed division in `rt_int_to_str`. Negating `INT64_MIN` wraps back to the
same bit pattern; signed division therefore produces negative remainders that
are converted into bytes outside `0` through `9`. The textual ARM64 assembly
stub instead uses unsigned division and does not have the same instruction
sequence, exposing drift between backend paths.

## 2. Context

Vir represents signed integer types using two's complement. The current
compiler and `tests/vri/test_int64_overflow_wrapping.vri` implement ordinary
`int` addition as wrapping on the tested 64-bit native path, so
`9223372036854775807 + 1` produces `-9223372036854775808`.

`VIR-SPC-0017` section 12.5 specifies that integer interpolation is lowered
through `i_to_str()`. The minimum signed value is a valid `int` value and must
therefore be rendered correctly regardless of whether it came from wrapping
arithmetic, parsing, a constant, or another computation.

The active language specification explicitly assigns wrapping overflow to
integer power but does not state a complete overflow policy for ordinary `+`,
`-`, and `*`. This specification gap is distinct from the formatter defect:
both wrapping and checked arithmetic still require any valid `INT64_MIN` value
to be printable and formattable correctly.

## 3. Expected Behavior

Given a runtime `int` value equal to `INT64_MIN`:

```text
direct=-9223372036854775808
interpolated=-9223372036854775808
```

All integer-to-string paths must support the complete signed 64-bit domain
without evaluating an unrepresentable positive signed magnitude. Supported
backend paths must agree on exact decimal output.

## 4. Actual Behavior

With `virc 2026.1 (self-hosted)` on macOS ARM64, direct integer printing is
correct but interpolation is corrupted:

```text
-9223372036854775808
interpolated=-'..--).0-*(+,))+(0(
```

A separate focused call to the public `format.int(INT64_MIN)` surface also
produced an incorrect result (`481036370336`) in the current checkout. Its
source negates negative values before digit extraction, so the standard-library
surface requires the same boundary audit rather than being assumed correct
after the compiler runtime stub is fixed.

## 5. Reproduction

Minimal source:

```vir
func main:
    let
        maximum = 9223372036854775807
        minimum = maximum + 1

    print minimum
    print "interpolated=$minimum\n"
end.
```

Run from the repository root:

```sh
./bin/virc /private/tmp/virc_int64_min_interpolation.vri \
  -o /private/tmp/virc_int64_min_interpolation
/private/tmp/virc_int64_min_interpolation

./bin/virc /private/tmp/virc_int64_min_interpolation.vri \
  -S -o /private/tmp/virc_int64_min_interpolation.s
```

Environment used for confirmation:

```text
Compiler: virc 2026.1 (self-hosted)
Host:     macOS arm64
Date:     2026-10-07
```

## 6. Evidence

- `tests/vri/test_int64_overflow_wrapping.vri` confirms the current executable
  behavior expected for wrapping addition, but checks only sign and nearby
  values; it does not interpolate or stringify `INT64_MIN`.
- `papers/VIR/specs/VIR-SPC-0017_language_specification_english.md` section
  12.5 states that integer interpolation is lowered through `i_to_str()`.
- `compiler/src/lower/lir_codegen/rt_stubs_base.vri:483-495` negates a negative
  value and then emits `arm64_sdiv_rrr` for decimal digit extraction.
- Disassembly of the reproduced native executable contains `sdiv x13, x9,
  x15` in the runtime integer-to-string stub after the wrapping negation.
- `compiler/src/ir/mc/mc_printer/stubs_arm64.vri:204-217`, used by the textual
  assembly path, performs the same negation but uses `udiv` and therefore does
  not match the direct emitter.
- `compiler/src/lower/lir_codegen_x86/rt_stubs_base.vri:65-79` uses unsigned
  `div` after negation. This path was inspected but not executed on an x86-64
  host during this report.
- `compiler/src/ir/mc/mc_printer/stubs_riscv.vri:231-244` uses signed `rem` and
  `div` after negation. The likely `INT64_MIN` failure on RISC-V is a
  source-based hypothesis until executed on that target.
- `stdlib/vir/io/format.vri:41-50` computes `val = -val` and passes it to a
  positive-only digit loop. A focused native execution of
  `format.int(INT64_MIN)` returned the incorrect text `481036370336`.

## 7. Scope

### Affected

- macOS ARM64 executables emitted by the direct native machine-code path.
- Integer string interpolation lowered through the compiler runtime
  `i_to_str`/`rt_int_to_str` path.
- The public `format.int` boundary at `INT64_MIN` in the reproduced checkout.
- Potentially other radix-formatting methods that share `_formatIntRadix` or
  `_formatPrefixedRadix`.

### Not affected / Unknown

- Direct integer `print` on the reproduced macOS ARM64 path renders
  `INT64_MIN` correctly.
- The emitted ARM64 textual assembly stub uses unsigned division and has the
  correct magnitude strategy by source inspection.
- The x86-64 direct emitter uses unsigned division by source inspection, but
  runtime behavior is NOT_VERIFIED in this issue.
- RISC-V runtime behavior is NOT_VERIFIED; its signed `rem`/`div` sequence is
  suspicious and must be tested.
- WebAssembly behavior is NOT_VERIFIED.
- General overflow policy for ordinary signed `+`, `-`, and `*` is not fully
  stated by the active language specification and requires an explicit
  normative decision or clarification.

## 8. Impact

Programs can emit corrupted user-visible text for a valid boundary integer.
The defect affects logging, diagnostics, serialization built on interpolation,
and any output protocol that relies on the compiler's integer-to-string
runtime helper. Backend drift also allows `-S` inspection to appear correct
while the directly emitted executable remains wrong.

Severity is `S2`: the defect is deterministic and violates core formatting
correctness, but it is limited to a boundary value and direct integer printing
provides a temporary workaround. Priority is `P1` because the failure crosses
compiler/runtime and public formatting boundaries and currently lacks a
regression gate.

## 9. Preliminary Analysis

- **CONFIRMED:** `INT64_MIN` interpolation is corrupted on the reproduced
  macOS ARM64 native executable.
- **CONFIRMED:** direct integer printing of the same value is correct.
- **CONFIRMED:** the direct ARM64 runtime stub uses signed division after
  wrapping negation; the textual assembly stub uses unsigned division.
- **CONFIRMED:** the existing wrapping regression does not exercise
  interpolation or integer-to-string conversion of `INT64_MIN`.
- **OBSERVED:** the public `format.int` path also returns incorrect output for
  `INT64_MIN` in the current checkout.
- **HYPOTHESIS:** RISC-V has the same magnitude-conversion defect because its
  assembly stub uses signed remainder/division after `neg`.
- **NOT_VERIFIED:** x86-64 and WebAssembly runtime behavior, optimization-level
  parity, and whether every public radix formatter fails identically.
- **NOT_VERIFIED:** whether Vir's normative policy for ordinary signed
  arithmetic will remain wrapping or become checked; current tests establish
  implementation behavior, not a complete general language rule.

## 10. Acceptance Criteria

- [x] Add a committed regression fixture covering decimal conversion of `0`,
      `1`, `-1`, `INT64_MAX`, and `INT64_MIN` through direct print,
      interpolation, the builtin integer-to-string path, and `format.int`.
- [x] The macOS ARM64 direct executable renders `INT64_MIN` exactly as
      `-9223372036854775808` for every supported decimal conversion surface.
- [x] Integer magnitude conversion never requires a representable positive
      signed form of `INT64_MIN`; digit extraction uses an unsigned magnitude
      or an equivalent negative-domain algorithm.
- [x] ARM64 direct emission and textual assembly emission use semantically
      equivalent integer-formatting algorithms, with a structural regression
      preventing `sdiv` in the unsigned-magnitude digit loop.
- [x] Execute the boundary matrix on every supported native backend. Record
      unsupported x86-64, RISC-V, or WebAssembly paths explicitly instead of
      inferring parity from ARM64.
- [x] Audit `format.intRadix`, `format.hex`, `format.bin`, and `format.oct` at
      `INT64_MIN`; fix or track every independently failing surface.
- [x] Establish or link the canonical overflow policy for ordinary signed
      `+`, `-`, and `*`. If wrapping remains normative, preserve
      `INT64_MAX + 1 == INT64_MIN`; if checked arithmetic is adopted, add the
      required diagnostic/runtime-trap tests separately from formatter tests.
- [x] Rebuild the canonical/generated compiler artifacts, bump the compiler
      version according to `compiler/VERSIONING.md`, and pass version-policy
      regression tests.
- [x] Create a linked PLAN before implementation and a verification REPORT
      before resolving or closing this ISSUE.

## 11. Related Papers

### Issues

- None.

### Plans

- [VIRC-PLN-0030](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0030_fix_integer_interpolation_and_radix_formatting_at_int64_min_boundary_across_comp.md)

### Reports

- [VIRC-RPT-0047](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0047_arm64_integer_interpolation_and_int64_min_formatting_fix_verification_report.md)

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Opened with a deterministic macOS ARM64 reproduction, backend instruction evidence, stdlib boundary observation, and measurable acceptance criteria |
| 2026-10-07 | Linked VIRC-PLN-0030 and transitioned to IMPLEMENTING |
| 2026-10-07 | Linked VIRC-RPT-0047 |
| 2026-10-07 | Resolved and closed: all acceptance criteria verified in VIRC-RPT-0047 |
