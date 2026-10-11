---
id: "VIRC-RPT-0053"
type: "REPORT"
domain: "VIRC"
title: "Register hardware access volatile width field scope and backend parity verification report"
status: "ACCEPTED"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "compiler"
  - "backend"
components:
  - "register"
  - "embedded-mmio"
  - "ast-to-mir"
  - "lir"
  - "arm64-backend"
  - "x86-64-backend"
  - "riscv64-backend"
  - "wasm32-backend"
  - "conformance-tests"
related:
  issues:
    - "VIRC-ISS-0061"
  plans:
    - "VIRC-PLN-0036"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "hardware-access"
  - "mmio"
  - "volatile"
  - "field-layout"
  - "cross-target"
---

# VIRC-RPT-0053 — Register hardware access volatile width field scope and backend parity verification report

## 1. Executive Summary

This report documents the complete resolution and verification of [VIRC-ISS-0061](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md) under plan [VIRC-PLN-0036](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0036_fix_register_hardware_access_volatile_width_field_scope_and_backend_parity.md).

All defective layers have been addressed and verified:
1. **Volatile Access Width Separation and Ordering:** Dedicated LIR runtime stubs (`LIR_RT_VOLATILE_READ16`, `LIR_RT_VOLATILE_WRITE16`, `LIR_RT_VOLATILE_READ32`, `LIR_RT_VOLATILE_WRITE32`) implemented across ARM64 (`ldrh`/`strh`, `ldr_w`/`str_w` with `dmb ishld`/`dmb ishst` barriers) and x86-64 (`movzwq`/`mov_mem16`, `mov_reg_mem32`/`mov_mem_reg32`, with `mfence` barriers before and after every load and store). Full 8/16/32/64-bit read and write isolation verified with multi-canary tests; narrow writes and 64-bit writes modify only declared byte widths and preserve surrounding canary words intact.
2. **Scoped Register Metadata and Collision Isolation:** Register fields are keyed by `(entity_name, field_name)` via `g_scoped_regfield_hash`. Homonymous field names across distinct register types resolve to their exact respective bit offsets. Ordinary entities with matching field names are fully isolated from register bitfield lowering. Furthermore, register clobber hazards during bit insertion (`r_val == target_rd`) are protected via safe scratch preservation across all optimization levels (`-O0..-O3`).
3. **Backend Parity and Fail-Closed Verification:** Native bit-field extraction (`shr`/`and`) and insertion (`shl`/`and`/`or`) implemented in x86-64 backend. RISC-V and Wasm targets fail closed with compile-time capability diagnostics (`E-RISCV-UNSUPPORTED`, `E-WASM-UNSUPPORTED`) before emitting broken artifacts.
4. **Textual Assembly (-S) Pipeline Parity:** Machine-code emission (`lir_to_mc`) updated for ARM64 and x86-64 to lower volatile reads/writes with correct widths and barriers (`dmb`, `mfence`), and register bitfield operations (`ubfx`, `bfi` on ARM64; `shr`, `shl`, `and`, `or` on x86-64). RISC-V and Wasm fail closed in `-S` mode with explicit diagnostics.
5. **Registered Group 16 Matrix & Hardened Oracles:** `run_tests.sh` Group 16 contains dedicated contract runner `run_register_opt_and_target_matrix` testing `-O0..-O3` host execution across all 6 fixtures, ARM64 and x86-64 multi-target backend parity (inspecting exact assembly mnemonics `ubfx`, `bfi`, `dmb`, `ldrh`, `strh`, `shr`, `shl`, `and`, `or`, `mfence`, `movzx`), and RISC-V/Wasm fail-closed capability verification. All 29/29 tests in Group 16 pass 100%.

Self-hosted bootstrap achieved bit-for-bit identity across `bin/virc`, `bin/virc.stage1`, and `bin/virc.stage2` (19,404,080 bytes, SHA-256 `041511312df1e93c8c6c19df81b8d0e4da4df7b2eaf0fed2da2e3a3b6b87cd41`).

## 2. Source Issues

- [VIRC-ISS-0061](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md) — Register hardware access violates volatile width field scope and backend parity contracts.

## 3. Source Plans

- [VIRC-PLN-0036](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0036_fix_register_hardware_access_volatile_width_field_scope_and_backend_parity.md) — Fix register hardware access, volatile width, field scope, and backend parity.

## 4. Implementation Summary

- **LIR runtime definitions:** Added `LIR_RT_VOLATILE_READ16` (117), `LIR_RT_VOLATILE_WRITE16` (118), `LIR_RT_VOLATILE_READ32` (119), `LIR_RT_VOLATILE_WRITE32` (120) to `compiler/src/ir/lir/lir.vri`; updated `LIR_RT_STUB_COUNT` to 121.
- **ARM64 machine code generation:** Added `arm64_strh_uoff`, `arm64_ldrh_uoff`, `arm64_str_w_uoff`, `arm64_ldr_w_uoff` in `compiler/src/backend/codegen.vri`.
- **ARM64 runtime stubs:** Added `emit_lir_rt_volatile_read16_stub`, `emit_lir_rt_volatile_write16_stub`, `emit_lir_rt_volatile_read32_stub`, `emit_lir_rt_volatile_write32_stub` with `dmb` barriers in `compiler/src/lower/lir_codegen/rt_stubs_base.vri` and wired dispatch in `stub_emit.vri`.
- **Builtin-to-stub mapping:** Fixed `compiler/src/lower/lir_codegen/types.vri` and `compiler/src/lower/lir_codegen_x86/types.vri` to map builtin IDs 56..63 to exact 8/16/32/64-bit LIR stubs without collapsing widths.
- **x86-64 machine code & stubs:** Added 8/16/32/64-bit volatile memory stubs and `mfence` barriers in `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri`. Exported `x86_emit_movzwq_reg_mem` and `x86_emit_movswq_reg_mem` in `codegen_x86.vri`.
- **x86-64 register intrinsics:** Implemented `MIR_INTR_BIT_EXTRACT` and `MIR_INTR_BIT_INSERT` in `compiler/src/lower/lir_codegen_x86/intrinsics.vri` using shift and bitwise mask logic.
- **Textual assembly (-S) parity in MC & LIR-to-MC:**
  - Added MC opcodes `ARM64_UBFX`, `ARM64_BFI`, `ARM64_DMB_ISHLD`, `ARM64_DMB_ISHST`, `ARM64_DMB_ISH`, `ARM64_DSB_ISH`, `ARM64_ISB`, `X86_64_SHR_IMM`, `X86_64_SHL_IMM`, `X86_64_MFENCE` in `compiler/src/ir/mc/mc.vri` and instruction printers in `compiler/src/ir/mc/mc_printer.vri`.
  - Implemented volatile builtins (54..66) and bitfield operations (`MIR_INTR_BIT_EXTRACT`, `MIR_INTR_BIT_INSERT`) with argument protection in `compiler/src/lower/lir_to_mc/arm64.vri` and `compiler/src/lower/lir_to_mc/x86_64.vri`.
  - Implemented fail-closed rejection for RISC-V bit operations in `compiler/src/lower/lir_to_mc/riscv64/intrinsics.vri`.
- **Scoped register metadata:** Added `g_register_names`, `g_register_hash`, `g_scoped_regfield_names`, `g_scoped_regfield_starts`, `g_scoped_regfield_widths`, and `g_scoped_regfield_hash` in `compiler/src/lower/ast_to_mir/context.vri`. Keyed register bit layout by `qualified_member_name(entity_name, field_name)`.
- **Scoped layout queries:** Implemented `is_register_type`, `is_register_field_scoped`, `get_register_field_start_scoped`, `get_register_field_width_scoped` in `compiler/src/lower/ast_to_mir/layout/field_layout.vri`.
- **AST-to-MIR lowering checks:** Updated `compiler/src/lower/ast_to_mir/expr.vri` and `stmt.vri` to resolve receiver `base_type` before querying scoped register bitfields, preventing ordinary entity fields from being lowered as register bit-manipulations.
- **Test suite updates:** Updated `run_tests.sh` Group 16 to execute real register and volatile fixtures across `-O0..-O3`, multi-target direct binary and `-S` assembly checks with concrete mnemonic verification, and fail-closed checks for RISC-V/Wasm.
- **Version bump:** Incremented calendar version to `2026.1.8` for `VIRC-ISS-0061` per `compiler/VERSIONING.md`.

## 5. Changes by Component

### `compiler/src/ir/lir/lir.vri`
- Added `LIR_RT_VOLATILE_READ16` (117), `LIR_RT_VOLATILE_WRITE16` (118), `LIR_RT_VOLATILE_READ32` (119), `LIR_RT_VOLATILE_WRITE32` (120).
- Bumped `LIR_RT_STUB_COUNT` to 121 and exported new constants.

### `compiler/src/ir/mc/mc.vri` & `mc_printer.vri`
- Added and formatted MC opcodes for ARM64 (`UBFX`, `BFI`, `DMB`, `DSB`, `ISB`) and x86-64 (`SHR_IMM`, `SHL_IMM`, `MFENCE`).

### `compiler/src/lower/lir_to_mc/arm64.vri`
- Lowered volatile builtins to `dmb`/`ldr`/`str` sequences and intrinsics `MIR_INTR_BIT_EXTRACT` (`ubfx`), `MIR_INTR_BIT_INSERT` (`bfi` with `x0` clobber protection).

### `compiler/src/lower/lir_to_mc/x86_64.vri`
- Lowered volatile builtins with `mfence` barriers and intrinsics `MIR_INTR_BIT_EXTRACT`/`INSERT` via shifts and bitwise masking.

### `compiler/src/lower/lir_to_mc/riscv64/intrinsics.vri`
- Enforced compile-time fail-closed rejection with `E-RISCV-UNSUPPORTED`.

### `compiler/src/backend/codegen.vri`
- Implemented `arm64_strh_uoff`, `arm64_ldrh_uoff`, `arm64_str_w_uoff`, `arm64_ldr_w_uoff` and exported them.

### `compiler/src/backend/codegen_x86.vri`
- Exported `x86_emit_movzwq_reg_mem` and `x86_emit_movswq_reg_mem`.

### `compiler/src/lower/lir_codegen/rt_stubs_base.vri` & `rt_stubs_math/stub_emit.vri`
- Implemented ARM64 16-bit and 32-bit volatile load/store stubs with ordering barriers (`DMB ISHLD` / `DMB ISHST`) and added dispatch cases.

### `compiler/src/lower/lir_codegen/types.vri` & `lir_codegen_x86/types.vri`
- Mapped builtin IDs 58 (`volatile_read16`) -> `LIR_RT_VOLATILE_READ16`, 59 (`volatile_write16`) -> `LIR_RT_VOLATILE_WRITE16`, 60 (`volatile_read32`) -> `LIR_RT_VOLATILE_READ32`, 61 (`volatile_write32`) -> `LIR_RT_VOLATILE_WRITE32`.
- Retained 56/57 for 8-bit and 54/55/62/63 for 64-bit.

### `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri`
- Implemented 8/16/32/64-bit volatile memory load and store stubs and `mfence` barriers.

### `compiler/src/lower/lir_codegen_x86/intrinsics.vri`
- Lowered `MIR_INTR_BIT_EXTRACT` and `MIR_INTR_BIT_INSERT` via shift and bitwise mask operations.

### `compiler/src/lower/ast_to_mir/context.vri`
- Introduced `g_scoped_regfield_*` tables and `g_register_names`/`g_register_hash`. Populated entries during AST walk keyed by `TypeName.FieldName`.

### `compiler/src/lower/ast_to_mir/layout/field_layout.vri`
- Implemented `is_register_type`, `is_register_field_scoped`, `get_register_field_start_scoped`, `get_register_field_width_scoped`.

### `compiler/src/lower/ast_to_mir/expr.vri` & `stmt.vri`
- Resolved `base_type` before checking register fields, verifying type match before lowering bit extraction/insertion.

### `run_tests.sh`
- Updated Group 16 with all 6 register/volatile fixtures in optimization matrix (-O0..-O3); hardened assembly checks for concrete instruction mnemonics.

## 6. Deviations from Plan

No material deviations. Implementation followed all four phases of `VIRC-PLN-0036`.

## 7. Verification

### 7.1 Test Fixtures

| Test Fixture | Purpose | Result | Evidence |
|---|---|---|---|
| `tests/strict_v2/volatile_widths_e2e.vri` | Exact 8/16/32/64-bit reads and writes with adjacent multi-canary check | PASS | Reads return `136`, `30600`, `1432778632`, `1234605616436508552`; narrow and 64-bit writes modify only declared byte widths; canaries remain `123456789` and `987654321` |
| `tests/strict_v2/register_scoped_collision_e2e.vri` | Multiple register types sharing field name `ENABLE` and `MODE` | PASS | `dev_a` bit 0 yields 1, `dev_b` bit 4 yields 16; no cross-register collision across `-O0..-O3` |
| `tests/strict_v2/register_entity_isolation_e2e.vri` | Entity and register sharing field name `val` | PASS | Entity `e.val` loads/stores normally (`42`, `100`, `999`); register `r.val` extracts bitfield (`15`) |
| `tests/strict_v2/register_x86_e2e.vri` | Multi-width bitfield ranges across low, mid, high bits | PASS | Returns `7`, `255`, `65535`, `7`, `0`, `65535` identically |
| `tests/test_register.vri` | Canonical register basic test across optimization levels | PASS | Passes at `-O0`, `-O1`, `-O2`, `-O3` |
| `tests/test_volatile.vri` | Canonical volatile full-width test | PASS | Passes at `-O0`, `-O1`, `-O2`, `-O3` |

### 7.2 Test Groups

| Test Group | Description | Result | Details |
|---|---|---|---|
| Group 16 | Register & Mold | **29/29 PASS** | 25 fixtures, narrow cast contract, registered opt matrix (-O0..-O3), multi-target parity (mfence), fail-closed |
| Group 7 | Entity & Packed Entity | **59/59 PASS** | No regression in struct/entity/packed lowering |
| Group 11 | UFCS & Generics | **62/62 PASS** | No regression in generic dispatch and resolution |
| Group 19 | Arrays & Slices | **25/25 PASS** | No regression in indexing or memory stubs |

### 7.3 Multi-Target and Optimization Matrix

- **Optimization Levels:** All 6 register/volatile fixtures verified passing under `-O0`, `-O1`, `-O2`, `-O3`. In particular, register bit insertion preserves `r_val` against clobbering when `r_val == target_rd`.
- **Target `macos-arm64`:** Direct binary compilation produces Mach-O executable with native `UBFX`, `BFI`, and `DMB` barriers (`dmb ishld`, `dmb ishst`). Textual assembly (`-S`) emits identical `ubfx`, `bfi`, and `dmb` instructions.
- **Target `linux-x86_64`:** Direct binary compilation produces ELF executable with native `shr`, `shl`, `and`, `or`, and volatile stubs with `mfence` barriers before and after every load and store. Textual assembly (`-S`) emits identical `shr`, `shl`, `and`, `or`, and `mfence` instructions.
- **Target `linux-riscv64`:** Fails closed at compile time in both binary and `-S` modes with `virc: error [E-RISCV-UNSUPPORTED]`.
- **Target `wasm32-wasi-p1`:** Fails closed at compile time in both binary and `-S` modes with `virc: error [E-WASM-UNSUPPORTED]`.

### 7.4 Bootstrap and Fixed-Point

- `bin/virc.stage1` and `bin/virc.stage2` were compiled sequentially from `compiler/generated/virc.vri`.
- `cmp bin/virc bin/virc.stage1 && cmp bin/virc bin/virc.stage2` returned exit code 0 (bit-for-bit identical).
- Size: `19,404,080` bytes.
- SHA-256: `041511312df1e93c8c6c19df81b8d0e4da4df7b2eaf0fed2da2e3a3b6b87cd41`.
- Version: `virc 2026.1.8 (self-hosted)`.

## 8. Acceptance Criteria

| Acceptance Criterion | Status | Evidence |
|---|---|---|
| A focused ARM64/runtime test proves that volatile reads return exactly the low 8, 16, 32, and 64 bits of a canary value | **SATISFIED** | `tests/strict_v2/volatile_widths_e2e.vri` returns `136`, `30600`, `1432778632`, `1234605616436508552`. |
| Canary tests prove that volatile writes modify exactly 1, 2, 4, or 8 bytes and preserve every byte outside the requested width | **SATISFIED** | `tests/strict_v2/volatile_widths_e2e.vri` proves canaries remain `123456789` and `987654321` across 8, 16, 32, and 64-bit writes. |
| Each exported volatile width variant maps to a width-correct lowering; no 16-bit operation aliases an 8-bit stub and no 32-bit operation aliases a 64-bit stub | **SATISFIED** | Distinct LIR runtime stubs 117 (`READ16`), 118 (`WRITE16`), 119 (`READ32`), 120 (`WRITE32`) implemented and mapped in `types.vri`. |
| Barrier instructions and ordering semantics remain present for every implemented width | **SATISFIED** | `DMB ISHLD` and `DMB ISHST` barriers present in ARM64 16/32-bit stubs; `mfence` implemented before and after all volatile reads/writes on x86-64 in binary and `-S` modes. |
| Register field metadata is keyed by owning type and field identity, and two register types may reuse a field name with different starts/widths | **SATISFIED** | `g_scoped_regfield_hash` keys fields by `TypeName.FieldName`; `tests/strict_v2/register_scoped_collision_e2e.vri` verified across `-O0..-O3`. |
| An ordinary entity field with the same name as a register field retains ordinary entity load/store semantics | **SATISFIED** | `tests/strict_v2/register_entity_isolation_e2e.vri` proves entity `val` field loads/stores without register bitfield hijacking. |
| ARM64, x86-64, RISC-V, and Wasm either implement correct register bit extraction/insertion in every artifact path or reject the feature before emitting an artifact with a target-specific diagnostic | **SATISFIED** | ARM64 and x86-64 compile native instructions in both binary and `-S` paths; RISC-V rejects with `E-RISCV-UNSUPPORTED`; Wasm rejects with `E-WASM-UNSUPPORTED`. |
| For every supported target, direct binary/object and -S/machine-code paths have equivalent register semantics | **SATISFIED** | Both ARM64 and x86-64 machine code generation paths emit equivalent bit extraction/insertion and volatile memory accesses. |
| Registered tests cover field reads/writes, duplicate field names, entity/register name isolation, volatile 8/16/32/64 widths, and -O0 through -O3 | **SATISFIED** | All 6 fixtures registered in `run_tests.sh` Group 16 and pass in `run_register_opt_and_target_matrix` across `-O0..-O3`. |
| Group 16 descriptions match the fixtures they execute; no narrow-cast fixture without register is reported as proof of register target coverage | **SATISFIED** | `run_tests.sh` Group 16 contract runner labelled `Mold narrow cast contract...`; genuine register opt/target matrix runner added. |
| `tests/test_register.vri`, `tests/test_volatile.vri`, the focused regressions, and the full registered suite pass on every available target runner, with explicit fail-closed expectations for unavailable features | **SATISFIED** | All fixtures pass on host and x86-64 target; fail closed on RISC-V/Wasm. |

## 9. Known Limitations

- RISC-V and Wasm targets do not support `register` bit extraction/insertion in this release; per specification and acceptance criteria, they fail closed at compile time with explicit diagnostics (`E-RISCV-UNSUPPORTED`, `E-WASM-UNSUPPORTED`).

## 10. Remaining Work

None. All planned implementation and verification items are complete.

## 11. Conclusion

`READY_FOR_CLOSE`

## 12. Related Papers

- [VIRC-ISS-0061](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md)
- [VIRC-PLN-0036](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0036_fix_register_hardware_access_volatile_width_field_scope_and_backend_parity.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial report verifying volatile width separation, scoped register metadata, x86-64 bit extraction/insertion, Group 16 test suite, and fixed-point bootstrap |
| 2026-10-09 | Follow-up audit verification: added x86 mfence barriers, full 64-bit write multi-canary preservation, registered Group 16 opt/target matrix, fixed ARM64 BIT_INSERT register clobber hazard, and achieved fixed-point bootstrap |
| 2026-10-09 | Final acceptance: implemented textual assembly (-S) parity in lir_to_mc on ARM64/x86-64, hardened Group 16 assembly oracles, expanded optimization matrix to all 6 fixtures, verified fail-closed RISC-V/Wasm, and achieved bit-for-bit bootstrap (19,404,080 bytes) |
