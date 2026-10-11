---
id: "VIRC-PLN-0036"
type: "PLAN"
domain: "VIRC"
title: "Fix register hardware access, volatile width, field scope, and backend parity"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0053"
supersedes: null
superseded_by: null
tags:
  - "hardware-access"
  - "mmio"
  - "volatile"
  - "field-layout"
  - "cross-target"
---

# VIRC-PLN-0036 — Fix register hardware access, volatile width, field scope, and backend parity

## 1. Objective

Resolve critical defect [VIRC-ISS-0061](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md) (severity S0, priority P0) by correcting the hardware access contract across four connected layers:
1. Exact-width volatile memory access (8, 16, 32, and 64 bits) with memory barriers across ARM64 and x86-64 backends, eliminating silent memory overwrites.
2. Scoped register bit-field metadata keyed by owning register type, eliminating field collisions across distinct register types and between registers and ordinary entities.
3. Backend parity and fail-closed integrity for register bit extraction/insertion across ARM64, x86-64, RISC-V, and Wasm, eliminating invalid runtime unresolved stubs.
4. Accurate and comprehensive Group 16 test suite verifying volatile access widths, scoped register isolation, cross-target compilation, and optimization levels (-O0..-O3).

## 2. Source Issues

- [VIRC-ISS-0061](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md) — Register hardware access violates volatile width field scope and backend parity contracts.

## 3. Scope

### In Scope

- Compiler frontend builtin ID mappings for volatile builtins (`volatile_read8/16/32/64`, `volatile_write8/16/32/64`).
- LIR runtime stub definitions for 16-bit and 32-bit volatile reads and writes (`LIR_RT_VOLATILE_READ16/WRITE16/READ32/WRITE32`).
- ARM64 native machine code emission for halfword (`LDRH`/`STRH`) and word (`LDR`/`STR` 32-bit) with ordering barriers (`DMB ISHLD`/`DMB ISHST`).
- x86-64 native machine code emission for 8/16/32/64-bit volatile operations and register bit-field extraction/insertion.
- AST-to-MIR register field metadata scoped by `(register_type, field_name)` and scoping checks in `expr.vri` and `stmt.vri`.
- Fail-closed verification for RISC-V and Wasm targets when register intrinsics are requested.
- Conformance test fixtures and Group 16 harness updates in `run_tests.sh`.
- Self-hosted compiler bootstrap and fixed-point verification.

### Out of Scope

- RISC-V and Wasm full bit-manipulation ISA extensions (these remain explicit fail-closed compile-time errors per SPEC).
- Unrelated narrow cast mold rules covered under VIRC-ISS-0020 / VIRC-ISS-0023.

## 4. Current Architecture

1. **Volatile Width Collapse:**
   - In `compiler/src/lower/lir_codegen/types.vri:516-519` and `compiler/src/lower/lir_codegen_x86/types.vri:100-103`, `volatile_read16` and `volatile_write16` map to 8-bit stubs (`LIR_RT_VOLATILE_READ8`/`WRITE8`).
   - `volatile_read32` and `volatile_write32` map to 64-bit stubs (`LIR_RT_VOLATILE_READ`/`WRITE`).
   - ARM64 only provides 8-bit and 64-bit stubs in `rt_stubs_base.vri`.
   - Result: 32-bit writes perform 64-bit stores, corrupting adjacent 32-bit memory or hardware registers.
2. **Unscoped Register Metadata:**
   - In `compiler/src/lower/ast_to_mir/context.vri:999-1007`, register fields are inserted into `g_register_field_names` keyed only by unqualified field name. Duplicate names from subsequent registers are ignored.
   - In `field_layout.vri:485-495`, `is_register_field_scoped` completely ignores `base_type` and delegates to unqualified `is_register_field`.
   - In `expr.vri:498` and `stmt.vri:590`, any field access matching an entry in `g_register_field_names` triggers `MIR_INTR_BIT_EXTRACT` or `MIR_INTR_BIT_INSERT`, even if the object is an ordinary `entity`.
3. **Backend Asymmetry:**
   - ARM64 lowers `MIR_INTR_BIT_EXTRACT` / `INSERT` via `UBFX` / `BFI`.
   - x86-64 falls through to `LIR_RT_UNRESOLVED` and generates a binary that terminates with exit code 1 at runtime.
   - RISC-V and Wasm reject the intrinsic at compile-time with `E-RISCV-UNSUPPORTED` / `E-WASM-UNSUPPORTED`.
4. **Test Gap:**
   - Group 16 reports 22/22 PASS by invoking `tests/types/narrow_cast_test.vri`, which tests mold narrow casts but contains no `register` declarations or volatile width checks.

## 5. Proposed Architecture

```
                                  Source Code
                           (register Reg, volatile_*)
                                       │
                                       ▼
                       Pass 1..6 Semantic Analysis
                       (Typed registers, range checks)
                                       │
                                       ▼
                              AST-to-MIR Lowering
                   ┌────────────────────────────────────────┐
                   │ Scoped Register Table:                 │
                   │ key: TypeName.FieldName                │
                   │ (start_bit, width, base_width)         │
                   └────────────────────────────────────────┘
                                       │
               ┌───────────────────────┴───────────────────────┐
               ▼                                               ▼
       Ordinary Entity Field                         Register Bit-Field
       (Base is EntityDef)                           (Base is RegisterDef)
       -> Memory Load/Store                          -> MIR_INTR_BIT_EXTRACT/INSERT
               │                                               │
               └───────────────────────┬───────────────────────┘
                                       ▼
                                 LIR Lowering
            ┌─────────────────────────────────────────────────────┐
            │ Distinct Volatile Stubs:                            │
            │ LIR_RT_VOLATILE_READ8 / WRITE8   (1 byte)           │
            │ LIR_RT_VOLATILE_READ16 / WRITE16 (2 bytes)          │
            │ LIR_RT_VOLATILE_READ32 / WRITE32 (4 bytes)          │
            │ LIR_RT_VOLATILE_READ64 / WRITE64 (8 bytes)          │
            └─────────────────────────────────────────────────────┘
                                       │
             ┌─────────────────────────┼─────────────────────────┐
             ▼                         ▼                         ▼
        ARM64 Backend            x86-64 Backend            RISC-V / Wasm
    - LDRB/STRB (8b)          - movzx/mov (8b)           - Fail-closed
    - LDRH/STRH (16b)         - movzx/mov (16b)            compile-time
    - LDR/STR W (32b)         - mov/mov (32b)              diagnostics
    - LDR/STR X (64b)         - mov/mov (64b)              before output
    - DMB ISHLD/ISHST         - mfence / TSO
    - UBFX/BFI bitfields      - shift/mask bitfields
```

## 6. Design Decisions

### Decision 1: Dedicated LIR Runtime Stubs for 16-bit and 32-bit Volatile Access

- **Decision:** Introduce `LIR_RT_VOLATILE_READ16`, `LIR_RT_VOLATILE_WRITE16`, `LIR_RT_VOLATILE_READ32`, `LIR_RT_VOLATILE_WRITE32` alongside existing 8-bit and 64-bit stubs.
- **Rationale:** Preserves uniform runtime stub dispatch across native code emission, matches existing 8-bit/64-bit pattern, and guarantees hardware-level access width isolation with dedicated barrier sequences.
- **Trade-offs:** Adds 4 stub IDs to `lir.vri` (stub count increases from 117 to 121), but maintains clean separation and zero runtime branching.

### Decision 2: Scoped Keying for Register Fields: `RegisterName.FieldName`

- **Decision:** Store register bit layout keyed by `TypeName.FieldName` using `qualified_member_name(reg_name, field_name)` in dedicated hash tables. `expr.vri` and `stmt.vri` will inspect `get_expr_entity_type` (or variable type) and only lower as bit extraction/insertion if `is_register_field_scoped(base_type, field_name)` returns true.
- **Rationale:** Prevents distinct register types with homonymous fields from conflicting, and completely isolates ordinary entity field accesses from accidental register bitfield lowering.
- **Alternatives considered:** Keeping global field names with disambiguation heuristics (rejected: unsafe and prone to order-dependent bugs).

### Decision 3: Native x86-64 Bitfield Emission via Shift and Mask

- **Decision:** Implement `MIR_INTR_BIT_EXTRACT` and `MIR_INTR_BIT_INSERT` in `lir_codegen_x86/intrinsics.vri` using `shr_imm`/`and_rr` and `shl_imm`/`or_rr`.
- **Rationale:** x86-64 direct compilation should produce working executables for `register` constructs rather than crashing on `LIR_RT_UNRESOLVED`. For targets without bitfield codegen (RISC-V, Wasm), preserve fail-closed compile-time rejection before creating broken artifacts.

## 7. Implementation Plan

### Phase 1 — Volatile Access Width Separation
- Update `compiler/src/ir/lir/lir.vri`: define `LIR_RT_VOLATILE_READ16` (117), `LIR_RT_VOLATILE_WRITE16` (118), `LIR_RT_VOLATILE_READ32` (119), `LIR_RT_VOLATILE_WRITE32` (120), update `LIR_RT_STUB_COUNT` to 121, export symbols.
- Update `compiler/src/backend/codegen.vri`: implement `arm64_ldrh_uoff`, `arm64_strh_uoff`, `arm64_ldr_w_uoff`, `arm64_str_w_uoff` and export them.
- Update `compiler/src/lower/lir_codegen/rt_stubs_base.vri`: implement `emit_lir_rt_volatile_read16_stub`, `emit_lir_rt_volatile_write16_stub`, `emit_lir_rt_volatile_read32_stub`, `emit_lir_rt_volatile_write32_stub`.
- Update `compiler/src/lower/lir_codegen/types.vri`: map `bid == 58` to `LIR_RT_VOLATILE_READ16`, `bid == 59` to `LIR_RT_VOLATILE_WRITE16`, `bid == 60` to `LIR_RT_VOLATILE_READ32`, `bid == 61` to `LIR_RT_VOLATILE_WRITE32`.
- Update `compiler/src/lower/lir_codegen/rt_stubs_math/stub_emit.vri`: dispatch new stubs in ARM64 stub loop.
- Update `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri` and `lir_codegen_x86/types.vri`: implement 8/16/32/64-bit volatile read/write stubs for x86-64.

### Phase 2 — Scoped Register Field Metadata
- Update `compiler/src/lower/ast_to_mir/context.vri`:
  - Introduce `g_scoped_regfield_names`, `g_scoped_regfield_starts`, `g_scoped_regfield_widths`, `g_scoped_regfield_hash`, and `g_register_type_hash`.
  - In `set_global_prog_ast`, register register fields under qualified keys (`TypeName.FieldName`).
- Update `compiler/src/lower/ast_to_mir/layout/field_layout.vri`:
  - Implement genuine `is_register_field_scoped(base_type, field_name)`, `get_register_field_start_scoped`, `get_register_field_width_scoped`.
- Update `compiler/src/lower/ast_to_mir/expr.vri`:
  - Use `base_type` from `base_ast` and query `is_register_field_scoped(base_type, fname)`.
- Update `compiler/src/lower/ast_to_mir/stmt.vri`:
  - Use `base_type` of the assignment receiver and query `is_register_field_scoped(base_type, fld_name)`.

### Phase 3 — Backend Parity and Fail-Closed Verification
- In `compiler/src/lower/lir_codegen_x86/intrinsics.vri`:
  - Add native instruction emission for `MIR_INTR_BIT_EXTRACT` and `MIR_INTR_BIT_INSERT`.
- In `compiler/src/lower/lir_codegen_riscv.vri` and `compiler/src/lower/lir_codegen_wasm/rt_stubs.vri`:
  - Verify fail-closed compilation aborts before producing an executable or wasm artifact when register intrinsics are unhandled.

### Phase 4 — Test Suite and Group 16 Harness
- Create `tests/strict_v2/volatile_widths_e2e.vri`: canary address tests for 8/16/32/64-bit reads and writes proving exact byte boundaries.
- Create `tests/strict_v2/register_scoped_collision_e2e.vri`: multiple register definitions sharing field names.
- Create `tests/strict_v2/register_entity_isolation_e2e.vri`: entity and register sharing field name.
- Create `tests/strict_v2/register_x86_e2e.vri`: x86-64 execution / parity check.
- Update `run_tests.sh` Group 16:
  - Register new fixtures.
  - Update contract label and runner description to match actual executed register tests.
- Rebuild fixed-point stages (stage 1 and stage 2) and verify bit-for-bit identity.

## 8. Compatibility

- **Source Compatibility:** Fully backward compatible with canonical Vir `register` syntax (`VIR-SPC-0018` §16) and `embedded.mmio` APIs.
- **ABI Compatibility:** Exact-width volatile accesses now strictly comply with native C/hardware MMIO ABI boundaries (1, 2, 4, 8 bytes).
- **Target Parity:** ARM64 and x86-64 support register operations natively; RISC-V and Wasm fail closed safely.

## 9. Migration

No code migration required. Existing correct programs will benefit from hardware memory safety.

## 10. Validation Plan

1. Host execution of `volatile_widths_e2e.vri` demonstrating exact byte boundaries and no canary corruption.
2. Host execution of `register_scoped_collision_e2e.vri` demonstrating distinct bit ranges for identical field names.
3. Host execution of `register_entity_isolation_e2e.vri` demonstrating entity fields load/store correctly even when homonymous register fields exist.
4. Execution of all Group 16 tests in `run_tests.sh 16`.
5. Non-regression of Group 7 (59/59), Group 11 (62/62), Group 19 (25/25).
6. Multi-target compilation check across ARM64, x86-64, RISC-V, and Wasm.
7. Fixed-point bootstrap check (`cmp bin/virc.stage1 bin/virc.stage2`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Register receiver type inference returns empty string for chained expressions | Medium | Medium | Fallback to variable type lookup in `g_var_types` / `g_program_var_types` before rejecting register access. |
| Stub count expansion affects binary size or layout | Low | Low | Only 4 new stub slots added; fixed-point bootstrap verified cleanly. |
| x86-64 shift/mask register pressure | Low | Low | Use standard scratch registers (RAX/RCX/RDX) during intrinsic expansion. |

## 12. Rollback Strategy

Git revert of changes across affected compiler source files and generated compiler code, returning to clean baseline.

## 13. Exit Criteria

- [x] Exact 8/16/32/64-bit volatile memory reads and writes verified with canary tests;
- [x] Scoped register metadata implemented and verified with collision tests;
- [x] Entity vs register field isolation verified;
- [x] x86-64 register bitfield lowering implemented and verified;
- [x] Group 16 test suite updated and passing 100%;
- [x] Fixed-point bootstrap verified (`cmp bin/virc.stage1 bin/virc.stage2` == 0);
- [x] Verification report `VIRC-RPT-0053` generated and `VIRC-ISS-0061` moved to RESOLVED/CLOSED.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0061_register_hardware_access_violates_volatile_width_field_scope_and_backend_parity.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Initial plan to fix volatile width, scoped register metadata, backend parity, and Group 16 tests |
| 2026-10-09 | Linked VIRC-RPT-0053 |
| 2026-10-09 | Completed plan execution; verified all exit criteria and linked VIRC-RPT-0053 |
| 2026-10-09 | Reactivated to implement x86 volatile mfence barriers, full 64-bit write canary test, and Group 16 registered target/opt matrix |
| 2026-10-09 | Completed follow-up plan: verified x86 mfence ordering, multi-canary 64-bit preservation, registered Group 16 opt/target matrix, fixed ARM64 clobber hazard, and closed issue |
| 2026-10-09 | Completed follow-up plan: verified textual assembly (-S) parity in lir_to_mc, hardened Group 16 assembly oracles, and achieved bit-for-bit bootstrap |
