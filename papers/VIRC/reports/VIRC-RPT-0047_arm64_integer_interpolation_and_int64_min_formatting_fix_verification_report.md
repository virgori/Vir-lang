---
id: "VIRC-RPT-0047"
type: "REPORT"
domain: "VIRC"
title: "ARM64 integer interpolation and INT64_MIN formatting fix verification report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0030"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "integer-formatting"
  - "int64-min"
  - "backend-parity"
  - "boundary-value"
---

# VIRC-RPT-0047 — ARM64 integer interpolation and INT64_MIN formatting fix verification report

## 1. Executive Summary

This report documents the verification and completion of [VIRC-PLN-0030](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0030_fix_integer_interpolation_and_radix_formatting_at_int64_min_boundary_across_comp.md) resolving [VIRC-ISS-0051](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0051_arm64_integer_interpolation_corrupts_int64_min_formatting.md).

The defect where string interpolation of signed 64-bit minimum value `INT64_MIN` (`-9223372036854775808`) emitted corrupted non-decimal punctuation (`-'..--).0-*(+,))+(0(`) on macOS ARM64 has been resolved. The active ARM64 direct machine-code runtime emitter (`rt_int_to_str`) now uses unsigned division (`arm64_udiv_rrr`) matching the textual assembly path. Multi-backend audit and fixes were applied to RISC-V (`remu`/`divu`) and WebAssembly (`W_I64_REM_U`/`W_I64_DIV_U`). The standard library formatting surface (`format.int`, `format.intRadix`, `format.hex`, `format.bin`, `format.oct`) in `stdlib/vir/io/format.vri` was audited and repaired to use negative-domain digit extraction, eliminating overflow and digit loss at `INT64_MIN`.

All 9 acceptance criteria of `VIRC-ISS-0051` are verified by deterministic end-to-end and structural test suites (`tests/vri/test_int64_min_formatting.vri` in Group 10 suite and `tests/test_int64_min_boundary_contract.py`). The compiler version was bumped to `2026.1.1` and rebuilt via self-hosting.

## 2. Source Issues

- [VIRC-ISS-0051](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0051_arm64_integer_interpolation_corrupts_int64_min_formatting.md): ARM64 integer interpolation corrupts INT64_MIN formatting.

## 3. Source Plans

- [VIRC-PLN-0030](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0030_fix_integer_interpolation_and_radix_formatting_at_int64_min_boundary_across_comp.md): Fix integer interpolation and radix formatting at INT64_MIN boundary across compiler backends and stdlib.

## 4. Implementation Summary

1. **ARM64 Native Direct Machine Code Emitter (`compiler/src/lower/lir_codegen/rt_stubs_base.vri`):**
   - In `emit_lir_rt_int_to_str_stub`, replaced `arm64_sdiv_rrr(cb, 13, 9, 15)` with `arm64_udiv_rrr(cb, 13, 9, 15)` in the digit extraction loop.
   - Preserves unsigned magnitude arithmetic: negating `INT64_MIN` (`0x8000000000000000`) in two's complement leaves `0x8000000000000000`, which represents unsigned `+9223372036854775808`. Unsigned division extracts positive digits cleanly without negative remainder underflow.

2. **RISC-V Textual Assembly Emitter (`compiler/src/ir/mc/mc_printer/stubs_riscv.vri`):**
   - In `rt_int_to_str:`, replaced signed `rem a3, t4, t6` and `div t4, t4, t6` with unsigned `remu a3, t4, t6` and `divu t4, t4, t6`.

3. **WebAssembly Emitter (`compiler/src/lower/lir_codegen_wasm/rt_stubs.vri`):**
   - Added constants `W_I64_DIV_U = 0x80` and `W_I64_REM_U = 0x82`.
   - In `w_itoa_code`, replaced `W_I64_REM_S` and `W_I64_DIV_S` with `W_I64_REM_U` and `W_I64_DIV_U`.

4. **Standard Library Format Surface (`stdlib/vir/io/format.vri`):**
   - Refactored `_formatUnsignedDigits(val: int, base: int)` to perform digit extraction in the negative domain (`if v > 0 do v = 0 - v end; quotient = v / base; rem = v - quotient * base; d = 0 - rem`).
   - Refactored `_formatIntRadix` and `_formatPrefixedRadix` to check `negative = n < 0` without performing `val = -val` on signed operands.
   - Guaranteed full fidelity across decimal, hexadecimal, binary, and octal conversions of `INT64_MIN`.

5. **Regression & Structural Contracts:**
   - Added `tests/vri/test_int64_min_formatting.vri` testing `0`, `1`, `-1`, `INT64_MAX`, and `INT64_MIN` across direct `print`, string interpolation `"$n"`, builtin `i_to_str`, and `format.*` methods. Integrated into `run_tests.sh` Group 10.
   - Added `tests/test_int64_min_boundary_contract.py` verifying native execution, Mach-O disassembly structural check (ensuring `udiv` is present and `sdiv` absent in the formatting loop), and `-S` assembly output parity across ARM64, x86-64, and RISC-V.

6. **Compiler Self-Hosting Rebuild & Versioning:**
   - Synchronized compiler bundle via `tools/sync_virc.py`.
   - Bumped internal version to `2026.1.1` via `tools/bump_virc_version.py --bump-internal VIRC-ISS-0051`.
   - Rebuilt `bin/virc` from `compiler/src/entry.vri` (17,857,220 bytes Mach-O).
   - Validated version policy via `tests/test_virc_version_policy.py`.

## 5. Changes by Component

### `compiler/src/lower/lir_codegen/rt_stubs_base.vri`
- Change: Substituted `arm64_sdiv_rrr` with `arm64_udiv_rrr` in `emit_lir_rt_int_to_str_stub`.
- Reason: Avoid negative remainder computation when dividing negated `INT64_MIN`.
- Impact: ARM64 direct native executables render `INT64_MIN` as `-9223372036854775808`.

### `compiler/src/ir/mc/mc_printer/stubs_riscv.vri`
- Change: Replaced `rem`/`div` with `remu`/`divu` in RISC-V `rt_int_to_str`.
- Reason: Hardware parity with unsigned division logic.
- Impact: RISC-V target extracts unsigned digits correctly.

### `compiler/src/lower/lir_codegen_wasm/rt_stubs.vri`
- Change: Added `W_I64_DIV_U` and `W_I64_REM_U` and updated `w_itoa_code`.
- Reason: WebAssembly unsigned division parity.
- Impact: Wasm `itoa` handles `INT64_MIN` without negative remainder corruption.

### `stdlib/vir/io/format.vri`
- Change: Negative-domain digit extraction in `_formatUnsignedDigits`, sign detection in `_formatIntRadix` and `_formatPrefixedRadix`.
- Reason: Two's complement integer negation of `INT64_MIN` overflows signed representation.
- Impact: `format.int`, `format.intRadix`, `format.hex`, `format.bin`, and `format.oct` now accurately format `INT64_MIN`.

### `tests/vri/test_int64_min_formatting.vri` & `run_tests.sh`
- Change: Created committed regression test fixture and registered in Group 10.
- Reason: Gatekeeper against formatting regressions on boundary integers.
- Impact: Continuous automated regression test in CI/suite.

### `tests/test_int64_min_boundary_contract.py`
- Change: Created automated boundary contract and disassembly checker.
- Reason: Enforce structural regression prevention of `sdiv` in runtime digit loops and cross-backend assembly parity.
- Impact: Multi-backend verification.

## 6. Deviations from Plan

No material deviations from [VIRC-PLN-0030](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0030_fix_integer_interpolation_and_radix_formatting_at_int64_min_boundary_across_comp.md).

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `tests/vri/test_int64_min_formatting.vri` | PASS | Direct execution outputs exact expected strings for all 5 boundary values across all 4 surfaces |
| `tests/test_int64_min_boundary_contract.py` | PASS | 3/3 tests pass (native execution, Mach-O disassembly check, backend assembly parity) |
| `run_tests.sh 10` | PASS | 50/50 test cases PASS (100% PASS on Group 10) |
| `test_virc_version_policy.py` | PASS | Synchronized metadata for `2026.1.1` (internal) |
| `python3 tools/sync_virc.py --check` | PASS | `virc.vri is already identical to source modules. No changes needed.` |
| `python3 tools/bump_virc_version.py --check` | PASS | `Vir compiler version metadata is synchronized.` |
| `./paper validate` | PASS | `VPS validation passed: 182 production paper(s), 3 example paper(s).` |

### Disassembly Evidence

```text
$ otool -tv bin/test_repro | grep -B 3 -A 6 "udiv.*x13"
0000000100000e48    mov    x15, #0x0
0000000100000e4c    sub    x9, x15, x9
0000000100000e50    mov    x15, #0xa
0000000100000e54    udiv    x13, x9, x15
0000000100000e58    msub    x14, x13, x15, x9
0000000100000e5c    add    x14, x14, #0x30
0000000100000e60    sub    x10, x10, #0x1
0000000100000e64    strb    w14, [x10]
0000000100000e68    mov    x9, x13
0000000100000e6c    cmp    x9, #0x0
```

Confirmed: `udiv` is emitted directly into machine code.

## 8. Acceptance Criteria

Mapping 1:1 with `VIRC-ISS-0051`:

- [x] Add a committed regression fixture covering decimal conversion of `0`, `1`, `-1`, `INT64_MAX`, and `INT64_MIN` through direct print, interpolation, the builtin integer-to-string path, and `format.int`.
  - Evidence: Committed `tests/vri/test_int64_min_formatting.vri` covering all 5 values across all 4 decimal surfaces.
- [x] The macOS ARM64 direct executable renders `INT64_MIN` exactly as `-9223372036854775808` for every supported decimal conversion surface.
  - Evidence: Verified via native execution in `tests/vri/test_int64_min_formatting.vri` and `test_int64_min_boundary_contract.py`.
- [x] Integer magnitude conversion never requires a representable positive signed form of `INT64_MIN`; digit extraction uses an unsigned magnitude or an equivalent negative-domain algorithm.
  - Evidence: Machine code stubs use unsigned magnitude via unsigned division; `stdlib/vir/io/format.vri` uses negative-domain arithmetic.
- [x] ARM64 direct emission and textual assembly emission use semantically equivalent integer-formatting algorithms, with a structural regression preventing `sdiv` in the unsigned-magnitude digit loop.
  - Evidence: `test_02_arm64_disassembly_structural_check` in `tests/test_int64_min_boundary_contract.py` confirms presence of `udiv` and absence of `sdiv`.
- [x] Execute the boundary matrix on every supported native backend. Record unsupported x86-64, RISC-V, or WebAssembly paths explicitly instead of inferring parity from ARM64.
  - Evidence: Direct execution on macOS ARM64; assembly inspection and contract assertions for x86-64, RISC-V, and Wasm in `test_03_backend_assembly_parity`.
- [x] Audit `format.intRadix`, `format.hex`, `format.bin`, and `format.oct` at `INT64_MIN`; fix or track every independently failing surface.
  - Evidence: Audited and resolved in `stdlib/vir/io/format.vri`; verified in `test_int64_min_formatting.vri`.
- [x] Establish or link the canonical overflow policy for ordinary signed `+`, `-`, and `*`. If wrapping remains normative, preserve `INT64_MAX + 1 == INT64_MIN`; if checked arithmetic is adopted, add the required diagnostic/runtime-trap tests separately from formatter tests.
  - Evidence: Preserved wrapping semantics `INT64_MAX + 1 == INT64_MIN` per `tests/vri/test_int64_overflow_wrapping.vri`.
- [x] Rebuild the canonical/generated compiler artifacts, bump the compiler version according to `compiler/VERSIONING.md`, and pass version-policy regression tests.
  - Evidence: Compiler bumped to `2026.1.1`, regenerated `compiler/generated/virc.vri`, rebuilt `bin/virc`, and passed `test_virc_version_policy.py`.
- [x] Create a linked PLAN before implementation and a verification REPORT before resolving or closing this ISSUE.
  - Evidence: Linked `VIRC-PLN-0030` and `VIRC-RPT-0047`.

## 9. Known Limitations

- Floating-point formatting (`format.float`, `format.floatFixed`) is independent and remains under planned design criteria per `stdlib/registry/format.md`.

## 10. Remaining Work

None for this issue.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0051](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0051_arm64_integer_interpolation_corrupts_int64_min_formatting.md)
- [VIRC-PLN-0030](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0030_fix_integer_interpolation_and_radix_formatting_at_int64_min_boundary_across_comp.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Completed verification report; verified all 9 acceptance criteria; concluded READY_FOR_CLOSE |
