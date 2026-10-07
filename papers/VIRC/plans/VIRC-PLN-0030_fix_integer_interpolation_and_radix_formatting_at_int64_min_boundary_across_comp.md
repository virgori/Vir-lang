---
id: "VIRC-PLN-0030"
type: "PLAN"
domain: "VIRC"
title: "Fix integer interpolation and radix formatting at INT64_MIN boundary across compiler backends and stdlib"
status: "COMPLETED"
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
  issues:
    - "VIRC-ISS-0051"
  plans: []
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

# VIRC-PLN-0030 — Fix integer interpolation and radix formatting at INT64_MIN boundary across compiler backends and stdlib

## 1. Objective

Resolve `VIRC-ISS-0051` by fixing the boundary-value formatting defect for `INT64_MIN` (`-9223372036854775808`) across all Vir compiler runtime stubs and standard library formatting surfaces. This ensures that integer interpolation, builtin `i_to_str`, direct `print`, and standard library `format.*` functions accurately and consistently format the entire signed 64-bit integer domain without wrapping corruption or missing digits.

## 2. Source Issues

- [VIRC-ISS-0051](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0051_arm64_integer_interpolation_corrupts_int64_min_formatting.md): ARM64 integer interpolation corrupts INT64_MIN formatting.

## 3. Scope

### In Scope

1. **Direct ARM64 Machine-Code Runtime Stub:**
   - Fix `emit_lir_rt_int_to_str_stub` in `compiler/src/lower/lir_codegen/rt_stubs_base.vri` to use unsigned division (`arm64_udiv_rrr`) instead of signed division (`arm64_sdiv_rrr`) in the digit extraction loop.
   - Eliminate instruction sequence drift between direct machine-code generation and textual assembly generation.

2. **Cross-Backend Stubs Audit and Alignment:**
   - Audit and fix `compiler/src/ir/mc/mc_printer/stubs_riscv.vri`: replace signed `rem` and `div` with unsigned `remu` and `divu`.
   - Audit and fix `compiler/src/lower/lir_codegen_wasm/rt_stubs.vri`: replace signed `W_I64_REM_S` and `W_I64_DIV_S` with unsigned `W_I64_REM_U` and `W_I64_DIV_U`.
   - Verify x86-64 direct emitter (`compiler/src/lower/lir_codegen_x86/rt_stubs_base.vri`) and assembly printer (`compiler/src/ir/mc/mc_printer/stubs_x86.vri`) which already utilize unsigned `div r10`.

3. **Standard Library Format Surface Audit and Fix:**
   - Fix `stdlib/vir/io/format.vri` (`_formatIntRadix`, `_formatPrefixedRadix`, `_formatUnsignedDigits`): adopt a negative-domain digit extraction algorithm so that `INT64_MIN` does not overflow upon negation or result in empty/corrupted digit buffers.
   - Verify all radix variants (`format.int`, `format.intRadix`, `format.hex`, `format.bin`, `format.oct`) render `INT64_MIN` correctly.

4. **Comprehensive Regression Testing:**
   - Add committed regression fixtures testing `0`, `1`, `-1`, `INT64_MAX`, and `INT64_MIN` across direct `print`, string interpolation `"$n"`, builtin `i_to_str(n)`, and `format.*`.
   - Add structural checks ensuring `sdiv` is never used in the ARM64 integer-to-string digit loop.

5. **Compiler Governance and Versioning:**
   - Synchronize compiler generated bundle via `tools/sync_virc.py`.
   - Bump internal compiler version for `VIRC-ISS-0051` via `tools/bump_virc_version.py --bump-internal VIRC-ISS-0051`.
   - Rebuild self-hosted binary `bin/virc` from `compiler/src/entry.vri` and pass version policy test `tests/test_virc_version_policy.py`.

### Out of Scope

- Redesigning the general language overflow trap model for arbitrary arithmetic expressions (`+`, `-`, `*`). Vir preserves wrapping two's complement semantics (`INT64_MAX + 1 == INT64_MIN`) as specified in existing tests (`tests/vri/test_int64_overflow_wrapping.vri`).
- Overhauling floating-point formatters (`format.float`, `format.floatFixed`).

## 4. Current Architecture

### Compiler Runtime Stubs

When Vir lowers integer string interpolation (`"$n"`) or the builtin `i_to_str(n)`, the call is routed to the runtime helper `rt_int_to_str`:

- In the direct ARM64 machine-code backend (`compiler/src/lower/lir_codegen/rt_stubs_base.vri:469-512`):
  ```vir
  # if n < 0: sign=1, n = 0 - n
  ...
  cb = arm64_sdiv_rrr(cb, 13, 9, 15)
  cb = arm64_msub_rrrr(cb, 14, 13, 15, 9)
  ```
  On `INT64_MIN` (`0x8000000000000000`), `0 - n` wraps back to `0x8000000000000000`. Using signed division (`arm64_sdiv_rrr`) computes a negative quotient and negative remainder (`-8`), resulting in ASCII values like `48 + (-8) = 40` (`'('`), which corrupts the formatted output into punctuation characters (`-'..--).0-*(+,))+(0(`).

- In the textual assembly emitter (`compiler/src/ir/mc/mc_printer/stubs_arm64.vri:204-217`):
  ```assembly
  neg x9, x9
  udiv x13, x9, x15
  msub x14, x13, x15, x9
  ```
  Unsigned division (`udiv`) is used. Since the bit pattern `0x8000000000000000` corresponds to unsigned `9223372036854775808`, `udiv` extracts the correct positive digits. This caused silent divergence between `-S` compilation and direct binary emission.

- In RISC-V text assembly (`compiler/src/ir/mc/mc_printer/stubs_riscv.vri:239-240`):
  Signed `rem` and `div` are currently used, suffering from the same signed remainder failure.

- In WebAssembly (`compiler/src/lower/lir_codegen_wasm/rt_stubs.vri:284-286`):
  Signed `W_I64_REM_S` and `W_I64_DIV_S` are currently emitted.

### Standard Library `format.vri`

In `stdlib/vir/io/format.vri:41-66`:
```vir
func _formatIntRadix(n: int, base: int) -> string:
    if n == 0 do out str_new("0") end
    negative = false
    val = n
    if val < 0 do
        negative = true
        val = -val
    end
    body = _formatUnsignedDigits(val, base)
...
```
`val = -val` on `INT64_MIN` wraps to `INT64_MIN` (still negative). Then `_formatUnsignedDigits` checks `when v > 0 loop`. Because `v < 0`, the loop terminates immediately without emitting digits, producing `"-"` or pointer address conversions.

## 5. Proposed Architecture

### 1. Direct ARM64 Emission Parity with Assembly

In `emit_lir_rt_int_to_str_stub`:
Replace `arm64_sdiv_rrr` with `arm64_udiv_rrr`. Both direct emission and assembly printers will now emit unsigned 64-bit division. Under two's complement, negating `INT64_MIN` yields unsigned magnitude `2^63` (`0x8000000000000000`), which is within the 64-bit unsigned domain `[0, 2^64 - 1]`. Unsigned division by `10` extracts each digit without overflow.

### 2. Multi-Target Parity

- **RISC-V (`stubs_riscv.vri`):** Replace `rem` and `div` with unsigned `remu` and `divu`.
- **WebAssembly (`rt_stubs.vri`):** Replace `W_I64_REM_S` (0x81) and `W_I64_DIV_S` (0x7F) with `W_I64_REM_U` (0x82) and `W_I64_DIV_U` (0x80).
- **x86-64 (`stubs_x86.vri`, `rt_stubs_base.vri`):** Verified using unsigned `div r10`.

### 3. Negative-Domain Digit Extraction in `stdlib/vir/io/format.vri`

Adopt the negative-domain algorithm used by `stdlib/vir/str/string.vri:435-457` (`i64_to_str`):
- Avoid `val = -val` on signed integers.
- Record `negative = n < 0`.
- In `_formatUnsignedDigits(val: int, base: int)`:
  - If `val > 0`, negate to negative `v = 0 - val`.
  - While `v != 0`:
    - `quotient = v / base`
    - `rem = v - quotient * base`
    - `digit = 0 - rem`
    - `buffer_push(digits, ...)`
    - `v = quotient`
  - Reverse the collected digits.
- In two's complement, all values in `[-2^63, 0]` are representable as signed 64-bit integers. Working entirely in the negative domain guarantees zero overflow for `INT64_MIN` across any radix (`base = 2, 8, 10, 16`).

## 6. Design Decisions

### Decision 1: Unsigned Division for Machine Code vs Negative Domain Algorithm

**Decision:** Use unsigned division (`udiv`) in low-level machine-code stubs (ARM64, x86-64, RISC-V, Wasm), and negative-domain signed arithmetic in high-level Vir code (`stdlib/vir/io/format.vri`).

**Rationale:**
- In machine code (ARM64 `udiv`, x86-64 `div`, RISC-V `divu`/`remu`, Wasm `i64.div_u`/`rem_u`), unsigned division instructions are single-cycle/native hardware instructions that treat the 64-bit register as an unsigned value `[0, 2^64 - 1]`. Since `|INT64_MIN| = 2^63 < 2^64`, `neg` followed by unsigned division is the canonical, most compact, and fastest machine-code sequence.
- In high-level Vir code, where all integer variables have signed `int` semantics, negative-domain extraction avoids depending on unsigned type availability or bitwise cast gymnastics.

### Decision 2: Structural Verification of Machine-Code Emitter

**Decision:** Add an automated verification check that scans emitted direct machine code and assembly stubs to ensure no signed division opcode (`sdiv`, `rem`, `div`) appears in the `rt_int_to_str` loop.

## 7. Implementation Plan

### Phase 1 — Compiler Backend Direct Emitters and Assembly Stubs
- **Files:**
  - `compiler/src/lower/lir_codegen/rt_stubs_base.vri`
  - `compiler/src/ir/mc/mc_printer/stubs_riscv.vri`
  - `compiler/src/lower/lir_codegen_wasm/rt_stubs.vri`
- **Changes:**
  - In `rt_stubs_base.vri:494`, change `arm64_sdiv_rrr` to `arm64_udiv_rrr`.
  - In `stubs_riscv.vri:239-240`, change `rem`/`div` to `remu`/`divu`.
  - In `lir_codegen_wasm/rt_stubs.vri`, define `W_I64_DIV_U = 0x80` and `W_I64_REM_U = 0x82`, update `w_itoa_code`.
- **Expected Result:**
  - ARM64 direct emitter and RISC-V/Wasm assembly emit unsigned division for integer string conversion.

### Phase 2 — Standard Library Format Surface
- **Files:**
  - `stdlib/vir/io/format.vri`
- **Changes:**
  - Refactor `_formatUnsignedDigits` to use negative-domain digit extraction.
  - Refactor `_formatIntRadix` and `_formatPrefixedRadix` to pass original `n` without overflowing `val = -val`.
- **Expected Result:**
  - `format.int`, `format.intRadix`, `format.hex`, `format.bin`, and `format.oct` produce exact decimal, hex, binary, and octal representations for `INT64_MIN`.

### Phase 3 — Test Suites and Structural Regressions
- **Files:**
  - `tests/vri/test_int64_min_formatting.vri`
  - `tests/test_int64_min_boundary_contract.py`
- **Changes:**
  - Add end-to-end Vir tests exercising the boundary values (`0`, `1`, `-1`, `INT64_MAX`, `INT64_MIN`) across direct print, string interpolation, builtin `i_to_str`, and all `format.*` methods.
  - Add backend parity and structural disassembly checks.

### Phase 4 — Versioning, Synchronization, and Compiler Rebuild
- **Commands:**
  - `python3 tools/sync_virc.py`
  - `python3 tools/bump_virc_version.py --bump-internal VIRC-ISS-0051`
  - `./bin/virc compiler/src/entry.vri -o bin/virc`
  - `python3 tests/test_virc_version_policy.py`

## 8. Compatibility

- **Source compatibility:** 100% backward compatible; fixes corrupted output on previously broken boundary values.
- **ABI & Runtime:** Preserves identical function signature and memory allocation layout for `rt_int_to_str`.
- **Target Parity:** Aligns macOS ARM64 direct emitter with `-S` textual assembly, x86-64, RISC-V, and Wasm.

## 9. Migration

No migration required. Bug fix for existing APIs.

## 10. Validation Plan

1. Compile and execute `tests/vri/test_int64_min_formatting.vri` with `./bin/virc`:
   - Verify `INT64_MIN` direct print = `-9223372036854775808`.
   - Verify `INT64_MIN` interpolation = `-9223372036854775808`.
   - Verify `i_to_str(INT64_MIN)` = `-9223372036854775808`.
   - Verify `format.int(INT64_MIN)` = `-9223372036854775808`.
   - Verify `format.hex(INT64_MIN)` = `"-0x8000000000000000"`.
   - Verify `format.bin(INT64_MIN)` = `"-0b1000000000000000000000000000000000000000000000000000000000000000"`.
   - Verify `format.oct(INT64_MIN)` = `"-0o1000000000000000000000"`.
2. Inspect assembly output from `-S --target <target>`:
   - `macos-arm64`: contains `udiv`, no `sdiv`.
   - `linux-riscv64`: contains `remu` and `divu`.
   - `linux-x86_64`: contains unsigned `div`.
3. Run version policy check `python3 tests/test_virc_version_policy.py`.
4. Run `paper validate` to verify VPS conformance.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Regressing positive integer formatting | Low | High | Exhaustive tests covering 0, 1, -1, INT64_MAX, and general random integers |
| Performance overhead of negative domain in `format.vri` | Low | Low | Digit extraction remains a single loop with identical division count |
| Rebuilding self-hosted compiler introduces boot anomalies | Low | High | Pinned stage rebuild verified via `--version` and version-policy runner |

## 12. Rollback Strategy

Changes are isolated to `rt_stubs_base.vri`, `stubs_riscv.vri`, `rt_stubs.vri`, and `format.vri`. If any regression occurs, revert git commits cleanly.

## 13. Exit Criteria

- [ ] Implementation completed across all identified compiler stubs and stdlib formatters.
- [ ] End-to-end regression fixture committed and passing with 100% correct outputs.
- [ ] Direct machine-code emitter verified to use `arm64_udiv_rrr`.
- [ ] RISC-V and Wasm stubs verified to use unsigned division.
- [ ] Compiler version bumped according to `compiler/VERSIONING.md` and rebuilt.
- [ ] Verification REPORT created and linked to `VIRC-ISS-0051` and `VIRC-PLN-0030`.
- [ ] `./paper validate` passes cleanly.

## 14. Related Papers

- [VIRC-ISS-0051](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0051_arm64_integer_interpolation_corrupts_int64_min_formatting.md)

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Created technical implementation plan for VIRC-ISS-0051 |
| 2026-10-07 | Completed implementation and verification; advanced to COMPLETED |
| 2026-10-07 | Linked VIRC-RPT-0047 |
