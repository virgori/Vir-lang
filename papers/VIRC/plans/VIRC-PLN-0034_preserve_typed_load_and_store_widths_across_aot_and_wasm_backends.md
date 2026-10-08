---
id: "VIRC-PLN-0034"
type: "PLAN"
domain: "VIRC"
title: "Preserve typed load and store widths across AOT and Wasm backends"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0051"
supersedes: null
superseded_by: null
tags:
  - "memory-safety"
  - "typed-load-store"
  - "width"
  - "unaligned-access"
  - "cross-target"
---

# VIRC-PLN-0034 — Preserve typed load and store widths across AOT and Wasm backends

## 1. Objective

Ensure that narrow and signed typed memory operations (`Load` and `Store`) with widths 1, 2, 4, and 8 bytes strictly preserve their byte widths and sign-extension semantics across all AOT (ARM64, x86-64, RISC-V 64) and WebAssembly backends, resolving out-of-bounds heap corruption and memory unsafety in packed entities reported in **VIRC-ISS-0060**.

## 2. Source Issues

- [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md)

## 3. Scope

### In Scope

- Establish a formal, backend-facing contract for `aux` metadata on MIR/LIR `Load` and `Store` instructions.
- Extend `MCOpcode` and `compiler/src/ir/mc/mc_printer.vri` to support width-specific and signed memory operations:
  - ARM64: `LDRB`, `LDRSB`, `LDRH`, `LDRSH`, `LDRW` (32-bit zero-extending), `LDRSW` (32-bit sign-extending), `STRB`, `STRH`, `STRW`.
  - x86-64: `MOVZX_LOAD8`, `MOVSX_LOAD8`, `MOVZX_LOAD16`, `MOVSX_LOAD16`, `MOV_LOAD32`, `MOVSXD_LOAD32`, `MOV_STORE8`, `MOV_STORE16`, `MOV_STORE32`.
  - RISC-V 64: `LB`, `LBU`, `LH`, `LHU`, `LW`, `LWU`, `SB`, `SH`, `SW`.
- Update LIR-to-MC lowering paths:
  - `compiler/src/lower/lir_to_mc/arm64.vri`: inspect `aux` and emit narrow/signed load and store opcodes.
  - `compiler/src/lower/lir_to_mc/x86_64.vri`: inspect `aux` and emit narrow/signed load and store opcodes.
  - `compiler/src/lower/lir_to_mc/riscv64/mov.vri`: inspect `aux` and emit narrow/signed load and store opcodes.
- Fix direct backend emitters:
  - `compiler/src/lower/lir_codegen_riscv.vri`: fix misuse of `aux` as offset; emit proper `rv_lbu`/`rv_lb`/`rv_lhu`/`rv_lh`/`rv_lwu`/`rv_lw`/`rv_ld` and `rv_sb`/`rv_sh`/`rv_sw`/`rv_sd` with zero displacement.
  - `compiler/src/lower/lir_codegen_x86/emit_func.vri`: fix signed load cases to emit `movsx`/`movsxd` instead of `movzx`.
  - `compiler/src/lower/lir_codegen_wasm.vri`: inspect `aux` and emit `i64.load8_u`/`s`, `i64.load16_u`/`s`, `i64.load32_u`/`s`, and `i64.store8`/`16`/`32` with safe alignment hint 0 ($2^0=1$ byte).
- Add verifier checks in `compiler/src/ir/mc/mc_verify.vri` validating operand shapes and register boundaries for new MCOpcodes.
- Verify cross-target assembly and execution via test suites and target emitters.

### Out of Scope

- Packed `f32` physical width or custom floating-point packed encodings (tracked separately).
- Changes to AST-to-MIR packed layout offset computation or struct field type checking.

## 4. Current Architecture

1. `emit_store_typed` and `emit_load_typed` in `compiler/src/lower/ast_to_mir/builder.vri` encode width in MIR `aux` (1, 2, 4, 8 for unsigned/store, -1, -2, -4 for signed loads).
2. `lir_lower.vri` propagates `aux` from MIR to LIR.
3. The macOS ARM64 direct backend (`compiler/src/lower/lir_codegen/emit_func.vri`) inspects `aux` and emits `ldrb`, `ldrsb`, `ldrh`, `ldrsh`, `ldr w`, `ldrsw`, `strb`, `strh`, `str w`.
4. However, the generic MCInst AOT pipeline (`lir_to_mc/arm64.vri`, `x86_64.vri`, `riscv64/mov.vri`) discards `aux` and emits hardcoded 64-bit `LDR`/`STR`, `MOV_LOAD`/`MOV_STORE`, `LD`/`SD`.
5. `compiler/src/lower/lir_codegen_riscv.vri` misinterprets `aux` as an address offset/displacement instead of width/signedness.
6. `compiler/src/lower/lir_codegen_wasm.vri` emits fixed `i64.load` (`0x29`) and `i64.store` (`0x37`) with 8-byte alignment hints.

## 5. Proposed Architecture

### Unified Typed Memory Metadata Contract

For any LIR `Load` or `Store` instruction:
- `aux == 1`: 1 byte unsigned load (`zero_extend`), or 1 byte store.
- `aux == -1`: 1 byte signed load (`sign_extend`), or 1 byte store.
- `aux == 2`: 2 bytes unsigned load (`zero_extend`), or 2 bytes store.
- `aux == -2`: 2 bytes signed load (`sign_extend`), or 2 bytes store.
- `aux == 4`: 4 bytes unsigned load (`zero_extend`), or 4 bytes store.
- `aux == -4`: 4 bytes signed load (`sign_extend`), or 4 bytes store.
- `aux == 8` or `aux == 0`: 8 bytes full 64-bit memory operation (default/legacy).
- Any other value: Invalid; verifier fails closed.

### Target Instruction Selection Matrix

| Operation | ARM64 MCInst | x86-64 MCInst | RISC-V 64 MCInst | RISC-V Direct | Wasm32 Direct |
|---|---|---|---|---|---|
| Load u8 (aux = 1) | `ldrb wN, [xM]` | `movzx rN, byte ptr [rM]` | `lbu aN, 0(aM)` | `rv_lbu` | `0x31` (`i64.load8_u`, align 0) |
| Load i8 (aux = -1) | `ldrsb xN, [xM]` | `movsx rN, byte ptr [rM]` | `lb aN, 0(aM)` | `rv_lb` | `0x30` (`i64.load8_s`, align 0) |
| Load u16 (aux = 2) | `ldrh wN, [xM]` | `movzx rN, word ptr [rM]` | `lhu aN, 0(aM)` | `rv_lhu` | `0x33` (`i64.load16_u`, align 0) |
| Load i16 (aux = -2) | `ldrsh xN, [xM]` | `movsx rN, word ptr [rM]` | `lh aN, 0(aM)` | `rv_lh` | `0x32` (`i64.load16_s`, align 0) |
| Load u32 (aux = 4) | `ldr wN, [xM]` | `mov rN32, dword ptr [rM]` | `lwu aN, 0(aM)` | `rv_lwu` | `0x35` (`i64.load32_u`, align 0) |
| Load i32 (aux = -4) | `ldrsw xN, [xM]` | `movsxd rN, dword ptr [rM]` | `lw aN, 0(aM)` | `rv_lw` | `0x34` (`i64.load32_s`, align 0) |
| Load 64 (aux = 0/8) | `ldr xN, [xM]` | `mov rN, qword ptr [rM]` | `ld aN, 0(aM)` | `rv_ld` | `0x29` (`i64.load`, align 0) |
| Store 8 (aux = 1/-1) | `strb wN, [xM]` | `mov byte ptr [rM], rN8` | `sb aN, 0(aM)` | `rv_sb` | `0x3c` (`i64.store8`, align 0) |
| Store 16 (aux = 2/-2) | `strh wN, [xM]` | `mov word ptr [rM], rN16` | `sh aN, 0(aM)` | `rv_sh` | `0x3d` (`i64.store16`, align 0) |
| Store 32 (aux = 4/-4) | `str wN, [xM]` | `mov dword ptr [rM], rN32` | `sw aN, 0(aM)` | `rv_sw` | `0x3e` (`i64.store32`, align 0) |
| Store 64 (aux = 0/8) | `str xN, [xM]` | `mov qword ptr [rM], rN` | `sd aN, 0(aM)` | `rv_sd` | `0x37` (`i64.store`, align 0) |

## 6. Design Decisions

### Decision 1: Dedicated MCOpcodes for Typed Memory Operations

**Decision:** Define explicit, strongly-typed MCOpcodes in `compiler/src/ir/mc/mc.vri` rather than overloading generic load/store opcodes with ad-hoc flag bits.

**Rationale:** The MCInst layer must produce verifiable machine instructions and faithful assembly output across multiple assembler dialects. Dedicated opcodes allow `mc_printer.vri` and `mc_verify.vri` to assert exact register widths and memory size directives unambiguously.

### Decision 2: 1-Byte Alignment Hint (`align=0`) in WebAssembly

**Decision:** In WebAssembly emitter (`lir_codegen_wasm.vri`), emit alignment hint `0` ($2^0 = 1$ byte) for all typed load/store operations on packed entities.

**Rationale:** Fields in a `packed entity` are aligned to 1 byte and may sit at arbitrary odd byte offsets. The Wasm specification guarantees that an alignment hint of 0 is valid for any memory address, preventing runtime alignment traps on strict Wasm runtimes while preserving correct memory read/write widths.

## 7. Implementation Plan

### Phase 1 — MCOpcode Extensions and Assembly Printing
- `compiler/src/ir/mc/mc.vri`:
  - Add ARM64 opcodes: `ARM64_LDRH_UOFF`, `ARM64_STRH_UOFF`, `ARM64_LDRW_UOFF`, `ARM64_STRW_UOFF`, `ARM64_LDRSB_UOFF`, `ARM64_LDRSH_UOFF`, `ARM64_LDRSW_UOFF`.
  - Add x86-64 opcodes: `X86_64_MOVZX_LOAD8`, `X86_64_MOVSX_LOAD8`, `X86_64_MOVZX_LOAD16`, `X86_64_MOVSX_LOAD16`, `X86_64_MOV_LOAD32`, `X86_64_MOVSXD_LOAD32`, `X86_64_MOV_STORE8`, `X86_64_MOV_STORE16`, `X86_64_MOV_STORE32`.
  - Add RISC-V opcodes: `RISCV_LB`, `RISCV_LH`, `RISCV_LHU`, `RISCV_LW`, `RISCV_LWU`, `RISCV_SH`, `RISCV_SW`.
- `compiler/src/ir/mc/mc_printer.vri`:
  - Implement textual assembly formatting for all new opcodes in ARM64 Darwin/GNU, x86-64 Intel syntax, and RISC-V GNU syntax.
- `compiler/src/ir/mc/mc_verify.vri`:
  - Update `mc_verify_inst` to validate register and memory operands for all new opcodes.

### Phase 2 — AOT MCInst Lowering
- `compiler/src/lower/lir_to_mc/arm64.vri`:
  - In `LirOp.Load` and `LirOp.Store`, read `aux = native_read_i64(ins as i64, 40)` and dispatch to narrow/signed opcodes.
- `compiler/src/lower/lir_to_mc/x86_64.vri`:
  - In `LirOp.Load` and `LirOp.Store`, read `aux = native_read_i64(ins as i64, 40)` and dispatch to narrow/signed opcodes.
- `compiler/src/lower/lir_to_mc/riscv64/mov.vri`:
  - Update `emit_riscv_load` and `emit_riscv_store` to accept `aux` and dispatch to narrow/signed opcodes. Update caller in `compiler/src/lower/lir_to_mc/riscv64.vri`.

### Phase 3 — Direct Backends (RISC-V, x86-64, Wasm)
- `compiler/src/lower/lir_codegen_riscv.vri`:
  - Fix displacement bug: pass displacement `0` and dispatch `rv_lbu`/`rv_lb`/`rv_lhu`/`rv_lh`/`rv_lwu`/`rv_lw`/`rv_ld` and `rv_sb`/`rv_sh`/`rv_sw`/`rv_sd` based on `aux`.
- `compiler/src/lower/lir_codegen_x86/emit_func.vri`:
  - In `LirOp.Load`, distinguish signed load (`ins_aux < 0`) to emit `x86_emit_movsx_reg_mem8`, `x86_emit_movsx_reg_mem16`, `x86_emit_movsxd_reg_mem32`.
- `compiler/src/lower/lir_codegen_wasm.vri`:
  - In `LirOp.Load` and `LirOp.Store`, read `aux = lir_instr_aux(ins)` and emit narrow Wasm memory opcodes (`0x30`-`0x35`, `0x3c`-`0x3e`) with alignment hint 0.

### Phase 4 — Verification and Self-Hosting
- Synchronize compiler bundle via `python3 tools/sync_virc.py`.
- Rebuild self-hosted compiler `bin/virc`.
- Verify assembly output for ARM64, x86-64, RISC-V 64, and Wasm on `packed_layout_mixed_width_e2e.vri`, `packed_unaligned_mutation_e2e.vri`, and `packed_signed_load_e2e.vri`.
- Run Group 7 test suite (`./run_tests.sh 7`) and type-safety contracts.
- Document evidence and compile REPORT paper.

## 8. Compatibility

- Fully preserves backward compatibility for ordinary (unpacked) 64-bit loads and stores (`aux == 0` or `aux == 8`).
- Preserves existing AST-to-MIR packed layout and sizeof contracts.

## 9. Migration

No source code migration required.

## 10. Validation Plan

- Verify ARM64 `-S` output contains `strb`, `strh`, `str w` and `ldrb`, `ldrh`, `ldr w` at byte offsets.
- Verify x86-64 `-S` output contains `mov byte ptr`, `mov word ptr`, `mov dword ptr` and `movzx`/`movsx`.
- Verify RISC-V `-S` output contains `sb`, `sh`, `sw` and `lbu`/`lb`, `lhu`/`lh`, `lwu`/`lw`.
- Verify Wasm output contains `i64.store8`/`16`/`32` and `i64.load8_u`/`16_u`/`32_u`/`s`.
- Run `./run_tests.sh 7` to ensure 100% PASS with zero regressions.
- Validate fixed-point compiler self-hosting build.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Register allocator clobber or operand type mismatch in MCInst | Low | High | Run `mc_verify_function` on all emitted functions; test with multiple optimization levels |
| Wasm validator rejection of alignment hints | Low | Medium | Use standard Wasm alignment hint 0 ($2^0=1$), valid for all memory instructions |
| Self-host bootstrap failure | Low | High | Validate compiler with multi-stage verification and backup binaries |

## 12. Rollback Strategy

Restore files in `compiler/src/` via git checkout and re-sync compiler bundle from previous commit.

## 13. Exit Criteria

- [x] Backend contract for typed `Load` and `Store` implemented across all AOT and Wasm emitters.
- [x] Narrow store widths 1, 2, 4 bytes preserved in ARM64, x86-64, RISC-V 64, and Wasm.
- [x] Unsigned zero extension and signed sign extension preserved across all targets.
- [x] RISC-V byte-wise reconstruction for unaligned multi-byte loads and stores implemented and verified.
- [x] Fail-closed typed-memory `aux` verification active across all backends.
- [x] Registered cross-target and optimization matrix assertions in regression suite passing.
- [x] Self-hosted compiler rebuild passes with byte-for-byte fixed-point stability.
- [x] Accompanying REPORT paper accepted and `VIRC-ISS-0060` moved to RESOLVED/CLOSED.

## 14. Related Papers

- [VIRC-ISS-0060](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0060_packed_entity_typed_load_and_store_widths_are_discarded_by_aot_and_wasm_backends.md)

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial plan created and moved to ACTIVE for VIRC-ISS-0060 |
| 2026-10-09 | Linked VIRC-RPT-0051 and moved to COMPLETED after verified implementation |
| 2026-10-09 | Reactivated to ACTIVE to address RISC-V unaligned access trap hazard, fail-closed invalid aux verifier, and cross-target test matrix |
| 2026-10-09 | Completed following implementation of RISC-V byte-wise reconstruction, fail-closed verifiers, registered test matrix, and bit-exact fixed point |
