---
id: "VIRC-RPT-0037"
type: "REPORT"
domain: "VIRC"
title: "Zero-extend unsigned narrow casts and truncate mold backing types"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "type-system"
  - "ast-to-mir"
  - "lir"
  - "arm64"
  - "x86-64"
  - "riscv64"
  - "wasm"
  - "mold"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0023"
  plans:
    - "VIRC-PLN-0020"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "cast"
  - "unsigned-integer"
  - "narrowing"
  - "zero-extension"
  - "sign-extension"
  - "mold"
  - "arm64"
---

# VIRC-RPT-0037 — Zero-extend unsigned narrow casts and truncate mold backing types

## 1. Executive Summary

This report documents the resolution of VIRC-ISS-0023 in accordance with VIRC-PLN-0020. The Vir compiler frontend (AST-to-MIR) now inspects and classifies canonical bit-width (8, 16, 32, 64) and signedness (signed vs. unsigned) for integer casts, resolving declared `mold` and `register` entities to their underlying backing types. The backend codegen layers across ARM64, x86-64, RISC-V, and WebAssembly now unconditionally narrow and zero-extend unsigned integer destinations and sign-extend signed integer destinations, preventing upper 64-bit register pollution even when register coalescing assigns source and destination operands to the same physical register (`dst == src`).

The deterministic reproducer from VIRC-ISS-0023 (`0x700000ab4e` through a `u16`-backed mold) now produces `43854` (previously `481036381006`). A post-acceptance audit found and corrected a remaining full-width-copy defect in the LIR-to-MC assembly path. Self-host fixed-point bootstrap has been re-established with identical Stage 2 and Stage 3 SHA-256 hashes (`830edb9446c32444af39fbc86f0d2858f535127886d6867fac056c99c38c5219`), test group 16 passes 22/22, and the 43 CLI contract tests pass.

## 2. Source Issues

- VIRC-ISS-0023 — Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64

## 3. Source Plans

- VIRC-PLN-0020 — Zero-extend unsigned narrow casts and truncate mold backing types

## 4. Implementation Summary

1. **AST-to-MIR Lowering & Mold Backing Resolution**:
   - In `compiler/src/lower/ast_to_mir/context.vri`, introduced `get_mold_or_register_backing_type(type_name: string)` which traverses `g_entity_nodes` to inspect if the named entity is an `AstType.RegisterDef`, returning its declared backing type (`ast_node_name2`).
   - In `compiler/src/lower/ast_to_mir/expr.vri`, updated `CastExpr` lowering to inspect the destination type (or its resolved mold backing type), recognizing `u8`, `u16`, `u32`, `u64`, `uint`, `i8`, `i16`, `i32`, `i64`, and `int`. Bit width (`cast_dst_bits`) is set to 8, 16, 32, or 64, and `cast_is_unsigned` is set to 1 for unsigned types.
   - Encoded `cast_dst_bits` (bits 24..31) and `cast_is_unsigned` (bits 32..39) into the 64-bit intrinsic kind value: `MIR_INTR_CAST | (src_cat << 8) | (dst_cat << 16) | (dst_bits << 24) | (is_unsigned << 32)`.

2. **Backend Native Codegen**:
   - **ARM64** (`compiler/src/lower/lir_codegen/intrinsics.vri`):
     - Unsigned casts emit `uxtb` (width 8), `uxth` (width 16), or 32-bit register move (`mov wD, wS` clearing upper 32 bits, opcode `0x2A0003E0`).
     - Signed casts emit `sxtb` (width 8), `sxth` (width 16), or `sxtw` (width 32).
     - Narrowing instructions are emitted unconditionally, guaranteeing clearing or sign-extending even when `cast_dst_reg == cast_src_reg`.
     - Intrinsic matching checks `(kind and 0xFF) == MIR_INTR_CAST`.
   - **x86-64** (`compiler/src/lower/lir_codegen_x86/intrinsics.vri`):
     - Emitted `MOVZX` for 8-bit and 16-bit unsigned, 32-bit register move for 32-bit unsigned zero-extension.
     - Emitted `MOVSX` and `MOVSXD` for 8-bit, 16-bit, and 32-bit signed integer extensions.
   - **RISC-V 64** (`compiler/src/lower/lir_codegen_riscv.vri`):
     - Emitted `andi` / bitwise `AND` masks for unsigned narrow casts.
     - Emitted `slli` + `srai` for signed narrow sign-extensions.
   - **WebAssembly** (`compiler/src/lower/lir_codegen_wasm.vri`):
     - Emitted `i64.const mask` + `i64.and` for unsigned narrow casts.
     - Emitted `i64.extend8_s` (0xC2), `i64.extend16_s` (0xC3), `i64.extend32_s` (0xC4) for signed narrow casts.
   - **MC Lowering** (`compiler/src/lower/lir_to_mc/arm64.vri`, `x86_64.vri`, `riscv64/intrinsics.vri`):
     - Decodes the cast source/destination category, destination width, and unsigned flag rather than treating every cast as a full-width copy.
     - ARM64 emits `UXTB`, `UXTH`, `UXTW`, `SXTB`, `SXTH`, or `SXTW` MC instructions.
     - x86-64 emits width-correct `MOVZX`, 32-bit `MOV`, `MOVSX`, or `MOVSXD` MC instructions.
     - RISC-V emits width-correct `SLLI` plus `SRLI`/`SRAI` sequences and verifies shift-immediate bounds.
     - Stack operands are loaded into a scratch register, narrowed, and only then stored to the destination spill slot.

3. **Bootstrap and Fixed Point**:
   - Synchronized bundle via `python3 tools/sync_virc.py`.
   - Built Stage 1 with new lowering, confirmed reproducer outputs `43854`.
   - Built Stage 2 with Stage 1, built Stage 3 with Stage 2, and confirmed bit-for-bit identity between Stage 2 and Stage 3 (`shasum -a 256` matching `830edb9446c32444af39fbc86f0d2858f535127886d6867fac056c99c38c5219`).
   - Promoted Stage 2 to `bin/virc` and `bin/virc_dev`.

## 5. Changes by Component

### `compiler/src/lower/ast_to_mir/context.vri`
- change: Added `get_mold_or_register_backing_type(type_name: string)` querying `g_entity_nodes`.
- reason: Mold definitions like `mold Packet: u16` must expose their backing integer type (`u16`) during cast lowering.
- impact: Enables accurate narrowing of mold-to-integer and integer-to-mold casts.

### `compiler/src/lower/ast_to_mir/expr.vri`
- change: Extended `CastExpr` lowering to inspect resolved destination types, set `cast_dst_bits` (8, 16, 32, 64) and `cast_is_unsigned` (1 for unsigned), and encode into `cast_kind`.
- reason: Preserves integer bit width and signedness across all sized numeric types.
- impact: Prevents narrow casts from defaulting to 64-bit integer moves.

### `compiler/src/lower/lir_codegen/intrinsics.vri`
- change: Hoisted `cast_bits` and implemented unconditional zero-extension (`uxtb`, `uxth`, `mov wD, wS`) and sign-extension (`sxtb`, `sxth`, `sxtw`) for integer-to-integer casts.
- reason: ARM64 regalloc coalescing previously bypassed cast operations when source and destination registers matched.
- impact: Eliminates upper-bit register leak on ARM64.

### `compiler/src/lower/lir_codegen_x86/intrinsics.vri`, `compiler/src/lower/lir_codegen_riscv.vri`, `compiler/src/lower/lir_codegen_wasm.vri`
- change: Added explicit zero-extension and sign-extension instruction emitters for integer narrowing.
- reason: Cross-backend semantic parity across all target architectures.
- impact: Guarantees narrow integer truncation semantics on x86-64, RISC-V, and Wasm.

### `tests/` and `run_tests.sh`
- change: Added `tests/test_mold_u16_cast.vri`, `tests/test_narrow_casts.vri`, `tests/test_narrow_cast_flow.vri`, and `tests/test_narrow_cast_contract.py`, registered into Group 16.
- reason: End-to-end regression verification and continuous test gate enforcement.
- impact: Group 16 now runs 22 tests with 100% pass rate. The contract runs call/register-pressure/branch behavior on the host and Wasm at O0-O3, and verifies target-specific MC narrowing for ARM64, x86-64, and RISC-V at O0-O3.

## 6. Deviations from Plan

The initial accepted report overstated MC-lowering and O0-O3 regression coverage. A post-acceptance audit reopened VIRC-ISS-0023, and the corrective work added the missing target-specific MC opcodes/lowering plus executable registered coverage. Linux x86-64 and RISC-V binaries were not executed on the ARM64 macOS host; their MC assembly is checked structurally at every optimization level, while ARM64 host binaries and Wasm run the semantic oracle at every optimization level.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `repro_mold_u16_cast.vri` | PASS | Output `43854` (was `481036381006`) |
| `tests/test_mold_u16_cast.vri` | PASS | Tested under `run_tests.sh 16` |
| `tests/test_narrow_casts.vri` | PASS | Tested under `run_tests.sh 16`: `300 as u8 -> 44`, `-5 as u8 -> 251`, `481036381006 as i16 -> -21682`, `481036381006 as u16 -> 43854`, `0x123456789abcdef0 as u32 -> 2596069104`, `0x123456789abcdef0 as i32 -> -1698898192` |
| `tests/test_narrow_cast_flow.vri` | PASS | Calls, register pressure/spills, branch consumption, and downstream arithmetic pass at O0-O3 |
| `tests/test_narrow_cast_contract.py` | PASS | 3 tests: host semantic O0-O3, ARM64/x86-64/RISC-V MC O0-O3, and Wasm WASI semantic O0-O3 |
| Group 16 Test Suite | PASS | 22/22 PASS |
| CLI Contract Suite | PASS | 43/43 PASS in 25.6s |

### Bootstrap & Fixed Point

- Stage 2 SHA-256: `830edb9446c32444af39fbc86f0d2858f535127886d6867fac056c99c38c5219`
- Stage 3 SHA-256: `830edb9446c32444af39fbc86f0d2858f535127886d6867fac056c99c38c5219`
- Status: Bit-for-bit identical fixed point confirmed.

## 8. Acceptance Criteria

Mapping 1:1 với VIRC-ISS-0023:

- [x] AST-to-MIR preserves canonical destination width and signedness for `i8/u8`, `i16/u16`, `i32/u32`, and 64-bit integer casts.
- [x] On ARM64, narrowing to `u8`, `u16`, and `u32` clears every bit above the destination width before the result reaches any consumer.
- [x] `mold as backing_type` returns only the declared backing-width payload; the reproduction prints `43854`.
- [x] Registered tests cover high-bit-set constants, variables, calls, spills, mold pack/unpack, and downstream arithmetic/branch consumers at O0-O3.
- [x] Signed narrow casts have explicit, tested truncation and sign-extension behavior distinct from unsigned zero-extension.
- [x] ARM64, x86-64, RISC-V, and Wasm either pass the same semantic matrix or have separately tracked target limitations.
- [x] MIR/LIR or disassembly assertions prove that the narrowing operation is present and cannot be optimized away before observable consumers.
- [x] Generated compiler sources are synchronized from canonical sources and fixed-point self-host verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 9. Known Limitations

- Direct bitfield member extraction (`mold.field`) uses separate bit-extraction intrinsics (`MIR_INTR_BIT_EXTRACT`), which were already functional and bounded. Whole-mold casts (`val as MoldType`) cast to the backing type's width.
- Dynamic SIMD vector casts continue to follow SIMD vector intrinsic lowering paths, which are unaffected by scalar integer narrow casts.
- Runtime execution of Linux x86-64 and RISC-V artifacts was not available on the ARM64 macOS verification host. Their target-specific MC assembly was verified across O0-O3; generated ARM64 and x86-64 assembly also assembled successfully with the available Clang, while the installed Clang lacks a working RISC-V assembler backend.

## 10. Remaining Work

None for this issue. The post-acceptance MC defect and regression-coverage gap
have been corrected and verified.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0023 — Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64
- VIRC-PLN-0020 — Zero-extend unsigned narrow casts and truncate mold backing types
- VIR-ISS-0002 — Broader canonical typed identity and typed MIR metadata hardening

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial implementation and verification report; status ACCEPTED, conclusion READY_FOR_CLOSE |
| 2026-10-05 | Post-acceptance audit invalidated the closure conclusion: MC assembly lowering and the claimed O0-O3 flow coverage remained incomplete; follow-up was required and VIRC-ISS-0023 reopened |
| 2026-10-05 | Corrective implementation completed: MC narrowing fixed on ARM64/x86-64/RISC-V, O0-O3 host/Wasm/MC regression matrix registered, fixed point re-established, conclusion restored to READY_FOR_CLOSE |
