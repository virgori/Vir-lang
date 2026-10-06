---
id: "VIRC-PLN-0020"
type: "PLAN"
domain: "VIRC"
title: "Zero-extend unsigned narrow casts and truncate mold backing types"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0037"
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

# VIRC-PLN-0020 — Zero-extend unsigned narrow casts and truncate mold backing types

## 1. Objective

Resolve VIRC-ISS-0023 by implementing rigorous integer narrowing in the Vir self-hosting compiler:
1. Ensure AST-to-MIR preserves canonical destination bit width (8, 16, 32, 64) and signedness (signed vs. unsigned) for all integer casts (`i8/u8`, `i16/u16`, `i32/u32`, `i64/u64`, `int/uint`), including `mold` and `register` types resolved to their backing types.
2. In target code generation (ARM64, x86-64, RISC-V, WebAssembly), emit narrowing instructions that clear all bits above the destination width for unsigned types (zero-extension: `UXTB`, `UXTH`, 32-bit register move), and sign-extend for signed types (`SXTB`, `SXTH`, `SXTW`), even when source and destination registers are coalesced by the register allocator.
3. Verify that `mold as backing_type` and `val as mold` strictly truncate/mask values to their declared bit-width contract, fixing the reproducer (`0x700000ab4e` through `u16`-backed mold prints `43854` rather than `481036381006`).

## 2. Source Issues

- VIRC-ISS-0023 — Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64

## 3. Scope

### In Scope

- AST-to-MIR lowering of `CastExpr` in `compiler/src/lower/ast_to_mir/expr.vri`:
  - Recognize `u8`, `u16`, `u32`, `u64`, `uint`, `i8`, `i16`, `i32`, `i64`, `int`.
  - Resolve mold/register type names (`AstType.RegisterDef`) to their declared backing type.
  - Encode bit width (`cast_dst_bits`: 8, 16, 32, 64) and signedness flag (`cast_is_unsigned`: 0 for signed, 1 for unsigned) into the 64-bit `cast_kind` intrinsic payload.
- ARM64 native codegen in `compiler/src/lower/lir_codegen/intrinsics.vri`:
  - Unsigned: emit `uxtb` (8-bit), `uxth` (16-bit), 32-bit `mov` (32-bit zero-extension).
  - Signed: emit `sxtb` (8-bit), `sxth` (16-bit), `sxtw` (32-bit sign-extension).
  - Execute narrowing unconditionally (even when `dst_reg == src_reg`) so upper register bits are guaranteed to be cleared/extended.
- Cross-backend narrowing and MC lowering consistency:
  - x86-64 (`compiler/src/lower/lir_codegen_x86/intrinsics.vri` and `compiler/src/backend/codegen_x86.vri`).
  - RISC-V 64 (`compiler/src/lower/lir_to_mc/riscv64/intrinsics.vri`).
  - WebAssembly (`compiler/src/lower/lir_codegen_wasm.vri`).
  - MC instruction lowering (`lir_to_mc/arm64.vri`, `x86_64.vri`, `riscv64/intrinsics.vri`): match `(kind and 0xFF) == MIR_INTR_CAST`.
- Test suites:
  - Create positive fixtures for unsigned casts, signed casts, mold casts, and arithmetic/branch consumers at O0-O3.
  - Add to `run_tests.sh`.

### Out of Scope

- Floating point casts (`f32`, `f64`), which already have dedicated conversion paths.
- Changing `mold` grammar or syntax in the language specification.

## 4. Current Architecture

- `compiler/src/lower/ast_to_mir/expr.vri` only checks `i8`, `i16`, `i32` by string equality against `cast_dst_name`. `u8`, `u16`, `u32` are unhandled, defaulting `cast_dst_bits` to `64`.
- Mold type names like `Packet` are not resolved to their backing type, leaving `cast_dst_bits = 64`.
- In `compiler/src/lower/lir_codegen/intrinsics.vri`, integer-to-integer casts (`cast_src_cat == 1 and cast_dst_cat == 1`) only execute `arm64_mov_rr` if `dst != src`. If `dst == src` (or after register coalescing), no instructions are emitted, and no masking or sign-extension occurs.

## 5. Proposed Architecture

- Define helper `get_type_cast_spec(type_name: string)`:
  - Check if `type_name` is an entity that is a `RegisterDef` (mold/register); if so, substitute `backing_type = ast_node_name2(entity_node)`.
  - Classify `(bits, is_unsigned, mir_type)`:
    - `u8`: bits=8, is_unsigned=1, mir_type=MirType.Int8
    - `u16`: bits=16, is_unsigned=1, mir_type=MirType.Int16
    - `u32`: bits=32, is_unsigned=1, mir_type=MirType.Int32
    - `u64`, `uint`: bits=64, is_unsigned=1, mir_type=MirType.Int64
    - `i8`: bits=8, is_unsigned=0, mir_type=MirType.Int8
    - `i16`: bits=16, is_unsigned=0, mir_type=MirType.Int16
    - `i32`: bits=32, is_unsigned=0, mir_type=MirType.Int32
    - `i64`, `int`: bits=64, is_unsigned=0, mir_type=MirType.Int64
- Encode in `cast_kind`:
  - `MIR_INTR_CAST | (src_cat << 8) | (dst_cat << 16) | (dst_bits << 24) | (is_unsigned << 32)`.
- Backend codegen:
  - On integer-to-integer cast:
    - If `is_unsigned == 1`:
      - 8-bit: `uxtb w_dst, w_src` (`0x53001C00 | (src << 5) | dst`)
      - 16-bit: `uxth w_dst, w_src` (`0x53003C00 | (src << 5) | dst`)
      - 32-bit: `mov w_dst, w_src` (`0x2A0003E0 | (src << 16) | dst`)
      - 64-bit: `mov x_dst, x_src` (only if `dst != src`)
    - If `is_unsigned == 0`:
      - 8-bit: `sxtb x_dst, w_src` (`0x93401C00 | (src << 5) | dst`)
      - 16-bit: `sxth x_dst, w_src` (`0x93403C00 | (src << 5) | dst`)
      - 32-bit: `sxtw x_dst, w_src` (`0x93407C00 | (src << 5) | dst`)
      - 64-bit: `mov x_dst, x_src` (only if `dst != src`)

## 6. Design Decisions

### Decision 1: Explicit bit encoding for signedness and width in `cast_kind`
**Decision:** Use bits 24..31 for destination bit width (8, 16, 32, 64) and bits 32..39 for destination signedness flag (`is_unsigned`).
**Rationale:** Fits cleanly into 64-bit integer representation of LIR intrinsic kind without allocating new IR opcodes or modifying IR data structures.

### Decision 2: Mold / Register backing type lookup in AST-to-MIR
**Decision:** When `cast_dst_name` is an aggregate defined via `RegisterDef` (mold or register), inspect its recorded `ast_node_name2` (backing type) to determine narrowing dimensions.
**Rationale:** Mold and register types represent packed bitfields whose machine representation is their backing integer. Casting to a mold or casting a mold to integer must enforce the backing type's boundaries.

## 7. Implementation Plan

### Phase 1 — AST-to-MIR Cast Classification & Mold Type Resolution
- File: `compiler/src/lower/ast_to_mir/expr.vri`
- Implement type classification helper that handles unsigned, signed, and mold backing types.
- Set `cast_dst_bits`, `cast_is_unsigned`, and `cast_mir_type`.

### Phase 2 — Target Code Generation for Narrowing
- File: `compiler/src/lower/lir_codegen/intrinsics.vri`
- Unconditionally narrow integer registers on ARM64 for 8, 16, 32 bits (zero-extend for unsigned, sign-extend for signed).
- Update x86-64, RISC-V 64, and Wasm backends.
- Fix `(kind and 0xFF) == MIR_INTR_CAST` in `lir_to_mc/` passes.

### Phase 3 — Verification & Conformance Tests
- Add fixtures:
  - `tests/test_mold_u16_cast.vri` (reproduces VIRC-ISS-0023, asserts `43854`).
  - `tests/test_narrow_casts.vri` (validates `u8`, `u16`, `u32`, `i8`, `i16`, `i32` with high bits set).
  - Register in `run_tests.sh`.

### Phase 4 — Fixed-Point Bootstrap & Governance
- Sync `compiler/generated/virc.vri`.
- Self-check, stage1, and stage2 build to confirm bit-for-bit fixed point.
- Generate `VIRC-RPT-0037` report, mark `VIRC-ISS-0023` CLOSED, update registry.

## 8. Compatibility

- Fully backward-compatible: standard 64-bit integer behavior is unchanged.
- Fixes broken contract where values outside declared type range leaked into computations.

## 9. Migration

No migration required. Existing programs with narrow casts will now produce correct, truncated values according to the language specification.

## 10. Validation Plan

- Verify `pkt as u16` prints `43854`.
- Verify `300 as u8` prints `44`.
- Verify `0xfe as i8` prints `-2`.
- Verify all tests at O0, O1, O2, O3.
- Run complete test suites (`run_tests.sh`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing code inadvertently relying on unmasked high bits | Low | Low | Spec mandates mold/narrow cast truncation; bug fix restores spec conformance |
| Regalloc assigning dst == src causes skipped truncation | Low | High | Narrowing instructions emitted unconditionally for bits < 64 |

## 12. Rollback Strategy

Revert changes in `compiler/src/` and regenerate `compiler/generated/virc.vri`.

## 13. Exit Criteria

- [x] AST-to-MIR preserves canonical destination width and signedness for `i8/u8`, `i16/u16`, `i32/u32`, and 64-bit integer casts.
- [x] On ARM64, narrowing to `u8`, `u16`, and `u32` clears every bit above destination width.
- [x] `mold as backing_type` prints `43854`.
- [x] Signed narrow casts correctly sign-extend.
- [x] Multi-target backends handle cast narrowing.
- [x] Full test suites pass and fixed-point bootstrap succeeds.
- [x] VIRC-RPT report created and VIRC-ISS-0023 closed.

## 14. Related Papers

- VIRC-ISS-0023 — Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64
- VIRC-RPT-0037 — Zero-extend unsigned narrow casts and truncate mold backing types

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Created plan for VIRC-ISS-0023 implementation |
| 2026-10-05 | Linked VIRC-RPT-0037 |
| 2026-10-05 | Implementation complete; status COMPLETED |
