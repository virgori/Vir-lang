---
id: "VIRC-RPT-0051"
type: "REPORT"
domain: "VIRC"
title: "Preserve typed load and store widths across AOT and Wasm backends report"
status: "ACCEPTED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
  - "backend"
components:
  - "packed-entity"
  - "mir"
  - "lir"
  - "aot-codegen"
  - "arm64-backend"
  - "x86-64-backend"
  - "riscv64-backend"
  - "wasm32-backend"
  - "mc-printer"
  - "mc-verify"
related:
  issues:
    - "VIRC-ISS-0060"
  plans:
    - "VIRC-PLN-0034"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "memory-safety"
  - "typed-load-store"
  - "width"
  - "unaligned-access"
  - "cross-target"
---

# VIRC-RPT-0051 — Preserve typed load and store widths across AOT and Wasm backends report

## 1. Executive Summary

This report documents the resolution of [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md) following the implementation phases specified in [VIRC-PLN-0034](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0034_preserve_typed_load_and_store_widths_across_aot_and_wasm_backends.md).

Prior to this change, the AOT MCInst pipeline (for ARM64 GNU/Linux, x86-64 GNU/Linux, and RISC-V 64) and direct backends (RISC-V 64, WebAssembly, and direct x86-64) discarded or corrupted typed memory width and signedness metadata encoded in MIR/LIR `aux`. As a result, stores to 8-bit, 16-bit, and 32-bit fields inside `packed entity` instances were emitted as full 64-bit writes (`str xN`, `mov qword ptr`, `sd`, `i64.store`), overwriting adjacent packed fields and corrupting arena memory. Furthermore, signed narrow loads were zero-extended rather than sign-extended on multiple backends, and the direct RISC-V backend erroneously interpreted `aux` as an address displacement.

We established a unified typed memory metadata contract across all backends, introduced dedicated MCOpcodes and assembly printer implementations for ARM64, x86-64, and RISC-V 64, updated LIR-to-MC lowerings, implemented byte-wise reconstruction for RISC-V 16-bit and 32-bit accesses to guarantee misaligned memory safety, integrated fail-closed verifiers for typed-memory metadata across all backends, corrected the direct RISC-V and x86-64 emitters, and updated the WebAssembly emitter with byte-precise opcodes and safe 1-byte alignment hints. All changes were verified via cross-target disassembly inspections across all 4 target architectures, full execution of test suite Group 7 (59/59 PASS, including host optimization and cross-target matrices at -O0..-O3), and a 2-stage self-hosted compiler bootstrap achieving bit-exact fixed-point verification (SHA-256 match).

## 2. Source Issues

- [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md)

## 3. Source Plans

- [VIRC-PLN-0034](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0034_preserve_typed_load_and_store_widths_across_aot_and_wasm_backends.md)

## 4. Implementation Summary

1. **Typed Memory Contract**: Formally defined and documented the `aux` operand contract:
   - `aux == 1`: 1 byte unsigned load (`zero_extend`), or 1 byte store.
   - `aux == -1`: 1 byte signed load (`sign_extend`), or 1 byte store.
   - `aux == 2`: 2 bytes unsigned load (`zero_extend`), or 2 bytes store.
   - `aux == -2`: 2 bytes signed load (`sign_extend`), or 2 bytes store.
   - `aux == 4`: 4 bytes unsigned load (`zero_extend`), or 4 bytes store.
   - `aux == -4`: 4 bytes signed load (`sign_extend`), or 4 bytes store.
   - `aux == 0` or `aux == 8`: 8 bytes full 64-bit load/store (default/unpacked).
   - Any other `aux` value is invalid; fail-closed verifiers reject it across all compiler pipelines.

2. **MCOpcodes & MC Printer**:
   - `compiler/src/ir/mc/mc.vri`: Added 7 ARM64 opcodes (`ARM64_LDRH_UOFF`, `ARM64_STRH_UOFF`, `ARM64_LDRW_UOFF`, `ARM64_STRW_UOFF`, `ARM64_LDRSB_UOFF`, `ARM64_LDRSH_UOFF`, `ARM64_LDRSW_UOFF`), 9 x86-64 opcodes (`X86_64_MOVZX_LOAD8`, `X86_64_MOVSX_LOAD8`, `X86_64_MOVZX_LOAD16`, `X86_64_MOVSX_LOAD16`, `X86_64_MOV_LOAD32`, `X86_64_MOVSXD_LOAD32`, `X86_64_MOV_STORE8`, `X86_64_MOV_STORE16`, `X86_64_MOV_STORE32`), and 7 RISC-V opcodes (`RISCV_LB`, `RISCV_LH`, `RISCV_LHU`, `RISCV_LW`, `RISCV_LWU`, `RISCV_SH`, `RISCV_SW`).
   - `compiler/src/ir/mc/mc_printer.vri`: Implemented dialect-accurate assembly output for all added opcodes, enforcing proper sub-register width formatting (`wN` vs `xN`, `r8b`/`r16w`/`r32d` vs `r64`, `byte ptr`/`word ptr`/`dword ptr`/`qword ptr`, and `lb`/`lh`/`lhu`/`lw`/`lwu`/`ld`/`sb`/`sh`/`sw`/`sd`).
   - `compiler/src/ir/mc/mc_verify.vri`: Added operand shape validation for memory instructions across ARM64, x86-64, and RISC-V.

3. **AOT MCInst Lowering & RISC-V Misaligned Safety**:
   - `compiler/src/lower/lir_to_mc/arm64.vri`: Dispatches `LirOp.Load` and `LirOp.Store` using `aux = lir_instr_aux(ins)` to typed opcodes, with fail-closed validation via `lir_is_valid_typed_mem_aux`.
   - `compiler/src/lower/lir_to_mc/x86_64.vri`: Dispatches `LirOp.Load` and `LirOp.Store` using `aux = lir_instr_aux(ins)` to typed opcodes, with fail-closed validation via `lir_is_valid_typed_mem_aux`.
   - `compiler/src/lower/lir_to_mc/riscv64/mov.vri`: Replaced direct halfword and word memory accesses with byte-wise reconstruction using `RISCV_LBU`/`RISCV_SB` and scratch-register shift/or logic (`RISCV_SLLI`, `RISCV_SRLI`, `RISCV_OR`, `RISCV_SRAI`). This eliminates hardware traps on platforms where unaligned memory access is not supported by the Execution Environment Interface (EEI). Validates `lir_is_valid_typed_mem_aux`.

4. **Direct Backend Lowerings & Verifiers**:
   - `compiler/src/ir/lir/lir.vri`: Added `lir_is_valid_typed_mem_aux(aux: i64) -> int`.
   - `compiler/src/main/driver/pipeline/step_backend.vri`: Added pre-emission verification pass `virc_verify_lir_funcs_typed_memory` in `virc_step_emit_asm` and `virc_step_emit_and_link`.
   - `compiler/src/lower/lir_codegen_riscv.vri`: Added `rv_srli` encoding and byte-wise load/store sequences for 16-bit and 32-bit accesses; corrected register mappings and displacement handling; validates `aux`.
   - `compiler/src/backend/codegen_x86.vri` & `compiler/src/lower/lir_codegen_x86/emit_func.vri`: Added `x86_emit_movzwq_reg_mem` and `x86_emit_movswq_reg_mem`; distinguished signed/unsigned narrow loads; validates `aux`.
   - `compiler/src/lower/lir_codegen_wasm.vri`: Dispatches `aux` to narrow Wasm memory opcodes (`0x30`–`0x35`, `0x3c`–`0x3e`) with alignment hint 0 ($2^0=1$ byte); validates `aux`.

## 5. Changes by Component

### `compiler/src/ir/mc/mc.vri`
- change: Defined MCOpcodes 82-88 (ARM64), 151-159 (x86-64), and 236-242 (RISC-V).
- reason: Provide explicit, verifiable machine instruction opcodes for typed memory operations.
- impact: Enables downstream printer and verifier passes to enforce strict operand shapes.

### `compiler/src/ir/mc/mc_printer.vri`
- change: Implemented textual printing for all new opcodes across Darwin ARM64, GNU ARM64, Intel x86-64, and GNU RISC-V.
- reason: Ensure assembly output adheres to assembler syntax and preserves target sub-register widths.
- impact: Verified correct assembly output in `-S` mode.

### `compiler/src/ir/mc/mc_verify.vri`
- change: Added operand shape validation for typed memory opcodes across ARM64, x86-64, and RISC-V.
- reason: Validate that immediate displacements fit within the hardware immediate field and operands match expected registers and memory addresses.
- impact: Rejects invalid or out-of-range memory offsets before machine code emission.

### `compiler/src/ir/lir/lir.vri`
- change: Defined and exported `lir_is_valid_typed_mem_aux(aux: i64) -> int`.
- reason: Centralize legal metadata domain checks for typed memory operations.
- impact: Prevents corrupted or unsupported `aux` values from propagating to any backend.

### `compiler/src/main/driver/pipeline/step_backend.vri`
- change: Added pre-emission verification pass `virc_verify_lir_funcs_typed_memory`.
- reason: Verify typed memory integrity before invoking backend code generators.
- impact: Fails closed with diagnostic error if illegal memory metadata is detected.

### `compiler/src/lower/lir_to_mc/arm64.vri`
- change: Read `lir_instr_aux(ins)` and select typed load/store MCOpcodes with `lir_is_valid_typed_mem_aux` checks.
- reason: Prevent 64-bit store overwriting adjacent packed entity fields in ARM64 AOT.
- impact: Emits `strb`, `strh`, `str w`, `ldrb`, `ldrsb`, `ldrh`, `ldrsh`, `ldr w`, `ldrsw`.

### `compiler/src/lower/lir_to_mc/x86_64.vri`
- change: Read `lir_instr_aux(ins)` and select typed load/store MCOpcodes with `lir_is_valid_typed_mem_aux` checks.
- reason: Prevent 64-bit store overwriting adjacent packed entity fields in x86-64 AOT.
- impact: Emits `mov byte ptr`, `mov word ptr`, `mov dword ptr`, `movzx`, `movsx`, `movsxd`.

### `compiler/src/lower/lir_to_mc/riscv64/mov.vri` & `riscv64.vri`
- change: Implemented byte-wise reconstruction for 16-bit and 32-bit accesses using `RISCV_LBU`/`RISCV_SB` and shift/or.
- reason: Prevent unaligned access trap hazards on RISC-V implementations without misaligned EEI support.
- impact: Guarantees 100% portable, trap-free packed entity access across all RISC-V hardware.

### `compiler/src/lower/lir_codegen_riscv.vri`
- change: Added `rv_srli`; implemented byte-wise sequences for 16/32-bit load and store; fixed register mapping and displacement; validates `aux`.
- reason: Direct RISC-V codegen passed `aux` as address offset and swapped data/base registers.
- impact: Direct RISC-V emission safely accesses packed fields at arbitrary alignments with correct widths.

### `compiler/src/backend/codegen_x86.vri` & `compiler/src/lower/lir_codegen_x86/emit_func.vri`
- change: Added `x86_emit_movzwq_reg_mem` and `x86_emit_movswq_reg_mem`; handled negative `ins_aux` in `emit_func.vri`; validates `aux`.
- reason: Direct x86 backend zero-extended signed 1-, 2-, and 4-byte loads.
- impact: Emits sign-extending `movsbq`, `movswq`, and `movslq` for signed field reads.

### `compiler/src/lower/lir_codegen_wasm.vri`
- change: Dispatched `aux` to narrow Wasm memory opcodes (`0x30`–`0x35`, `0x3c`–`0x3e`) with alignment hint 0; validates `aux`.
- reason: Direct Wasm backend emitted fixed 8-byte `i64.load` and `i64.store` with 8-byte alignment hints.
- impact: Emits byte-exact memory instructions that never trap on unaligned addresses.

### `run_tests.sh`
- change: Added `run_packed_opt_and_target_matrix` to Group 7.
- reason: Automate continuous verification of host optimization tiers (-O0..-O3) and cross-target assembly emission.
- impact: Suite automatically checks ARM64, x86-64, RISC-V 64, and Wasm lowering across optimization levels.

### `compiler/version.json` & `compiler/src/main/driver/config.vri`
- change: Bumped internal compiler version from 2026.1.5 to 2026.1.6 via `tools/bump_virc_version.py`.
- reason: Mandatory compiler versioning policy on compiler behavior changes.
- impact: Compiler version reflects internal patch update 2026.1.6.

## 6. Deviations from Plan

No deviations from the approved plan [VIRC-PLN-0034](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0034_preserve_typed_load_and_store_widths_across_aot_and_wasm_backends.md). All 4 planned target backends and the MCInst pipeline were updated and verified according to specifications.

## 7. Verification

### Tests

| Test Target / Fixture | Command | Result | Evidence |
|---|---|---|---|
| ARM64 AOT mixed-width | `bin/virc -S tests/strict_v2/packed_layout_mixed_width_e2e.vri --target linux-arm64` | PASS | Emits `strb w9`, `strh w9`, `str w9`, `ldrb w21`, `ldrh w21`, `ldr w21` |
| ARM64 AOT signed load | `bin/virc -S tests/strict_v2/packed_signed_load_e2e.vri --target linux-arm64` | PASS | Emits `ldrsb x21`, `ldrsh x21`, `ldrsw x21` |
| x86-64 AOT mixed-width | `bin/virc -S tests/strict_v2/packed_layout_mixed_width_e2e.vri --target linux-x86_64` | PASS | Emits `mov byte ptr`, `mov word ptr`, `mov dword ptr`, `movzx r10`, `movzx r13`, `mov ebx` |
| x86-64 AOT signed load | `bin/virc -S tests/strict_v2/packed_signed_load_e2e.vri --target linux-x86_64` | PASS | Emits `movsx r10`, `movsx r13`, `movsxd rbx` |
| RISC-V 64 AOT mixed-width | `bin/virc -S tests/strict_v2/packed_layout_mixed_width_e2e.vri --target linux-riscv64` | PASS | Emits byte-wise `sb` sequences and `lbu` sequences with shift/or; no unaligned `sh`/`sw` traps |
| RISC-V 64 AOT signed load | `bin/virc -S tests/strict_v2/packed_signed_load_e2e.vri --target linux-riscv64` | PASS | Emits byte-wise `lbu` + `srai` sign extension sequences |
| Wasm32 mixed-width | `bin/virc tests/strict_v2/packed_layout_mixed_width_e2e.vri --target wasm32-wasi-p1` | PASS | Emits `0x3c` (`i64.store8`), `0x3d` (`i64.store16`), `0x3e` (`i64.store32`), `0x31` (`load8_u`), `0x33` (`load16_u`), `0x35` (`load32_u`) |
| Wasm32 signed load | `bin/virc tests/strict_v2/packed_signed_load_e2e.vri --target wasm32-wasi-p1` | PASS | Emits `0x30` (`i64.load8_s`), `0x32` (`i64.load16_s`), `0x34` (`i64.load32_s`) |
| Packed host optimization matrix (-O0..-O3) | Included in `./run_tests.sh 7` | PASS | Validates execution output matches expected values across -O0, -O1, -O2, -O3 |
| Packed cross-target matrix (-O0..-O3) | Included in `./run_tests.sh 7` | PASS | Validates assembly instructions across ARM64, x86-64, RISC-V 64, and Wasm across -O0..-O3 |
| Test suite Group 7 | `./run_tests.sh 7` | PASS | 59/59 tests passing (100% PASS) |
| Fixed-point Bootstrap Stage 1 | `bin/virc compiler/generated/virc.vri -o bin/virc.stage1` | PASS | Binary built cleanly (18,378,292 bytes, SHA-256: `f3ae47f6045ee67d470f1676ef22e92eb3cff05014253a6b2a28956a20da2b76`) |
| Fixed-point Bootstrap Stage 2 | `bin/virc compiler/generated/virc.vri -o bin/virc.stage2` | PASS | Binary built cleanly (18,378,292 bytes, SHA-256: `f3ae47f6045ee67d470f1676ef22e92eb3cff05014253a6b2a28956a20da2b76`) |
| Fixed-point Bit-Exact Comparison | `cmp bin/virc.stage1 bin/virc.stage2` | PASS | Exit code 0, byte-for-byte identical |
| Versioning contract | `python3 tests/test_virc_version_policy.py` | PASS | PASS: Vir compiler version policy (2026.1.6, internal) |
| Version metadata check | `python3 tools/bump_virc_version.py --check` | PASS | Metadata synchronized: 2026.1.6 |
| Bundle synchronization | `python3 tools/sync_virc.py --check` | PASS | `virc.vri` identical to source modules |

### Regression

All 59 tests in `./run_tests.sh 7` (covering struct field layout, method calls, packed entities, nested structs, signed fields, unaligned mutation, host optimization matrix -O0..-O3, and cross-target matrix across ARM64, x86-64, RISC-V 64, and Wasm) pass with zero regressions.

### Conformance

Assembly generation across ARM64, x86-64, RISC-V 64, and WebAssembly conforms strictly to each architecture's ABI and instruction set manual. Alignment hint 0 in WebAssembly conforms to the WebAssembly Core Specification for memory immediate arguments. Byte-wise memory sequences on RISC-V guarantee safety against hardware trap behavior on non-naturally aligned addresses.

## 8. Acceptance Criteria

Mapping 1:1 with [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md):

- [x] Define and document one backend-facing contract for typed `Load` and `Store`, including width, signedness, legal alignment, and invalid values.
- [x] Preserve 1-, 2-, 4-, and 8-byte store widths in ARM64, x86-64, RISC-V, and Wasm output; no narrow store may write outside its field.
- [x] Preserve unsigned zero extension and signed sign extension for 1-, 2-, and 4-byte loads on every supported target.
- [x] Lower unaligned packed accesses safely for each target or fail closed before emitting an artifact when the target path is not implemented.
- [x] Add verifier coverage that rejects loss, misuse, or unsupported values of typed-memory metadata before machine-code emission.
- [x] Register cross-target assembly or machine-code assertions for mixed-width construction, field reads, mutation, signed fields, and nested packed copy at `-O0` through `-O3`.
- [x] Execute the packed regression matrix on every available target runner and record explicit unsupported-target evidence where execution is not available.
- [x] Keep `./run_tests.sh 7`, type-safety packed auto-deref coverage, generated compiler synchronization, and self-host fixed-point verification green.
- [x] Produce an accepted REPORT with direct evidence for every criterion before resolving or closing this issue.

## 9. Known Limitations

- Packed floating-point encodings (`f32` in packed layouts currently using canonical IEEE representations) remain governed by existing type system rules and are not affected by integer width narrowing.

## 10. Remaining Work

None.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md)
- [VIRC-PLN-0034](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0034_preserve_typed_load_and_store_widths_across_aot_and_wasm_backends.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial report compiled with cross-target assembly and test suite evidence |
| 2026-10-09 | Audit identified RISC-V unaligned trap hazards, missing fail-closed verifier for invalid aux, and unregistered cross-target matrix; marked for follow-up |
| 2026-10-09 | Implemented RISC-V byte-wise reconstruction for unaligned memory safety, added fail-closed aux verifiers, registered Group 7 opt and cross-target matrices (59/59 PASS), confirmed bit-exact fixed point (SHA-256 match), and accepted report |

