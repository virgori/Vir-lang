---
id: "VIRC-ISS-0060"
type: "ISSUE"
domain: "VIRC"
title: "Packed entity typed load and store widths are discarded by AOT and Wasm backends"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-08"
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
  - "conformance-tests"
related:
  issues: []
  plans:
    - "VIRC-PLN-0034"
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

# VIRC-ISS-0060 — Packed entity typed load and store widths are discarded by AOT and Wasm backends

## 1. Summary

The compiler records packed-field byte widths in the `aux` metadata of MIR and
LIR `Load` and `Store` instructions, but the generic native AOT lowering paths
and the Wasm emitter discard that meaning and emit 8-byte memory operations.
For a seven-byte `packed entity` containing `u8`, `u16`, and `u32` fields, the
generated ARM64, x86-64, and RISC-V assembly allocates seven bytes and performs
8-byte stores at byte offsets 0, 1, and 3. The final store therefore reaches
four bytes beyond the allocation.

The host macOS ARM64 executable path interprets the width metadata and passes
the current runtime fixture, so the registered host-only regression suite does
not expose the cross-target corruption.

## 2. Context

`VIR-SPC-0018` section 7.3 requires a `packed entity` to use contiguous
byte-offset layout without padding, with one-byte alignment and compile-time
`sizeof` equal to the sum of its field sizes. AST-to-MIR lowering computes
packed field offsets and calls `emit_load_typed` / `emit_store_typed`; these
helpers encode widths 1, 2, 4, or 8 in instruction `aux`, with a negative load
width representing signed extension.

The direct ARM64 code generator selects byte, halfword, word, or doubleword
instructions from this metadata. The inspected LIR-to-MC ARM64, x86-64, and
RISC-V paths instead lower every ordinary `Load` and `Store` as a full 64-bit
operation. The Wasm backend likewise emits fixed `i64.load` and `i64.store`
opcodes and never reads the instruction width.

## 3. Expected Behavior

- Every backend must preserve the MIR/LIR typed-memory contract: 1-, 2-, 4-,
  and 8-byte stores write exactly that many bytes.
- Typed loads must read exactly the declared width and apply zero extension or
  sign extension according to the encoded signedness.
- Unaligned packed fields must be lowered safely on each supported target,
  including targets whose native aligned load/store instructions cannot be
  used at arbitrary byte offsets.
- A packed value must never read or write outside `sizeof(Entity)` merely
  because the selected target uses a different code-generation path.
- Cross-target conformance must be registered rather than inferred from the
  host backend result.

## 4. Actual Behavior

- `emit_store_typed` stores the requested byte width in MIR `aux`, and
  `lir_lower` propagates `aux` to LIR.
- The generic ARM64 LIR-to-MC path emits `ARM64_LDR_UOFF` / `ARM64_STR_UOFF`
  without examining `aux`.
- The generic x86-64 LIR-to-MC path emits `X86_64_MOV_LOAD` /
  `X86_64_MOV_STORE` without examining `aux`.
- Both inspected RISC-V lowering paths emit `ld` / `sd`; one path incorrectly
  uses `aux` as a memory displacement rather than a width/signedness encoding.
- The Wasm emitter always emits `i64.load` (`0x29`) and `i64.store` (`0x37`)
  with an eight-byte alignment hint.
- `./run_tests.sh 7` reports 57/57 PASS on the macOS ARM64 host because it runs
  the direct host backend, not the affected target matrix.

## 5. Reproduction

Use the registered mixed-width fixture:

```vir
extern func native_read_u8(addr: int, offset: int) -> int

packed entity Wire:
    a: u8
    b: u16
    c: u32
end.

func main:
    var wire: Wire = Wire(a: 17, b: 8755, c: 1146447479)
    print(wire.a)
    print(wire.b)
    print(wire.c)
    out 0
end.
```

Generate target assembly:

```sh
./bin/virc tests/strict_v2/packed_layout_mixed_width_e2e.vri \
  --target linux-arm64 -S -q -o /private/tmp/packed_layout_arm64.s
./bin/virc tests/strict_v2/packed_layout_mixed_width_e2e.vri \
  --target linux-x86_64 -S -q -o /private/tmp/packed_layout_x86_64.s
./bin/virc tests/strict_v2/packed_layout_mixed_width_e2e.vri \
  --target linux-riscv64 -S -q -o /private/tmp/packed_layout_riscv64.s
./bin/virc tests/strict_v2/packed_layout_mixed_width_e2e.vri \
  --target wasm32-wasi-p1 -q -o /private/tmp/packed_layout.wasm
```

Observed ARM64 body excerpt:

```asm
movz x0, #7
bl rt_alloc
str x9, [x20]
add x23, x20, #1
str x9, [x23]
add x22, x20, #3
str x9, [x22]
```

Observed x86-64 and RISC-V instructions at the same field offsets include:

```asm
mov qword ptr [r14], r10
mov qword ptr [r13], r10
mov qword ptr [rbx], r10

sd t0, 0(s2)
sd t0, 0(s5)
sd t0, 0(s4)
```

## 6. Evidence

- **CONFIRMED:** `compiler/src/lower/ast_to_mir/builder.vri:483-498`
  encodes typed store width and typed load width/signedness in MIR `aux`.
- **CONFIRMED:** `compiler/src/lower/lir_lower.vri:81` propagates MIR `aux` for
  `Load` and `Store` into LIR.
- **CONFIRMED:** `compiler/src/lower/ast_to_mir/builder.vri:615-656` allocates
  exactly the computed packed size and uses typed stores at field byte offsets.
- **CONFIRMED:** `compiler/src/lower/lir_to_mc/arm64.vri:296-342` emits only
  64-bit load/store MC opcodes and does not inspect instruction `aux`.
- **CONFIRMED:** `compiler/src/lower/lir_to_mc/x86_64.vri:415-459` emits only
  the generic 64-bit memory opcodes and does not inspect instruction `aux`.
- **CONFIRMED:** `compiler/src/lower/lir_to_mc/riscv64/mov.vri:57-113` emits
  only `RISCV_LD` / `RISCV_SD` for ordinary LIR memory operations.
- **CONFIRMED:** `compiler/src/lower/lir_codegen_riscv.vri:735-760` emits
  `rv_ld` / `rv_sd` and passes `aux` as the displacement.
- **CONFIRMED:** `compiler/src/lower/lir_codegen_wasm.vri:242-255` emits fixed
  `i64.load` and `i64.store` instructions without reading `lir_instr_aux`.
- **CONFIRMED:** target assembly generated from the registered fixture allocates
  seven bytes and performs 8-byte stores at offsets 0, 1, and 3.
- **CONFIRMED:** `./run_tests.sh 7` passed 57/57 on 2026-10-08, demonstrating
  that the existing host regression gate does not cover the affected paths.
- **OBSERVED:** the audit used revision
  `930d21eef3e63b8bae7b748a35e6e8c00f72215b` in a dirty checkout and
  self-hosted `virc 2026.1.4` on macOS ARM64.

## 7. Scope

### Affected

- AOT assembly/object generation through generic ARM64, x86-64, and RISC-V
  LIR-to-MC lowering;
- Wasm32 packed-field reads, initialization, mutation, and nested packed copy;
- RISC-V direct LIR code generation;
- every narrow typed memory operation that reaches these generic paths, even
  when introduced by a feature other than `packed entity`;
- cross-target conformance and memory-safety tests.

### Not affected / Unknown

- The current macOS ARM64 direct executable path preserves typed widths for the
  tested unsigned and signed packed fields.
- Parser recognition, packed-definition validation, field offset calculation,
  named initialization, and nested packed layout are not the cause of this
  reproduction.
- Packed `f32` physical width, zero-field packed size, one-byte type alignment,
  lowercase-name Move classification, and missing `u64` literal bounds are
  independent audit findings and are outside this issue.
- NOT_VERIFIED: runtime execution of the produced Linux and Wasm artifacts on
  their native/emulated targets; the emitted instruction widths already
  establish the out-of-bounds access statically.
- NOT_VERIFIED: whether non-packed users of typed narrow memory operations can
  currently reach every affected backend path.

## 8. Impact

Supported cross-target compilation can produce executables that overwrite
adjacent arena memory during ordinary construction or mutation of a valid
packed value. Loads can consume bytes from following objects, and signed narrow
fields lose their required extension semantics. This violates the language's
FFI/mmap/binary-protocol contract and can corrupt unrelated program state.

Severity is `S1` because this is a core correctness and memory-safety failure in
supported compiler targets. Priority is `P0` because the compiler currently
emits the unsafe artifacts successfully instead of rejecting an unsupported
operation.

## 9. Preliminary Analysis

- **CONFIRMED:** width and signedness survive AST-to-MIR and MIR-to-LIR; the
  metadata is discarded or misinterpreted during backend lowering.
- **CONFIRMED:** the affected native AOT output uses 8-byte operations even
  when the packed field width is 1, 2, or 4 bytes.
- **CONFIRMED:** this is not a stale expected-output oracle; the generated code
  writes beyond the allocation described by its own preceding `rt_alloc(7)`.
- **HYPOTHESIS:** a shared typed-memory lowering contract plus verifier checks
  can prevent backend-specific fallback to untyped 64-bit memory operations.
- **HYPOTHESIS:** RISC-V packed accesses may need byte-wise reconstruction or
  explicit target capability handling for offsets that do not satisfy natural
  alignment.
- **NOT_VERIFIED:** the preferred representation of width/signedness in MCInst
  and whether one shared lowering helper can serve all native backends.

## 10. Acceptance Criteria

- [x] Define and document one backend-facing contract for typed `Load` and
      `Store`, including width, signedness, legal alignment, and invalid values.
- [x] Preserve 1-, 2-, 4-, and 8-byte store widths in ARM64, x86-64, RISC-V,
      and Wasm output; no narrow store may write outside its field.
- [x] Preserve unsigned zero extension and signed sign extension for 1-, 2-,
      and 4-byte loads on every supported target.
- [x] Lower unaligned packed accesses safely for each target or fail closed
      before emitting an artifact when the target path is not implemented.
- [x] Add verifier coverage that rejects loss, misuse, or unsupported values of
      typed-memory metadata before machine-code emission.
- [x] Register cross-target assembly or machine-code assertions for mixed-width
      construction, field reads, mutation, signed fields, and nested packed
      copy at `-O0` through `-O3`.
- [x] Execute the packed regression matrix on every available target runner and
      record explicit unsupported-target evidence where execution is not
      available.
- [x] Keep `./run_tests.sh 7`, type-safety packed auto-deref coverage, generated
      compiler synchronization, and self-host fixed-point verification green.
- [x] Produce an accepted REPORT with direct evidence for every criterion
      before resolving or closing this issue.

## 11. Related Papers

### Issues

- None.

### Plans

- VIRC-PLN-0034 — Preserve typed load and store widths across AOT and Wasm backends.

### Reports

- VIRC-RPT-0051 — Preserve typed load and store widths across AOT and Wasm backends report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened from the packed-keyword audit with cross-target assembly and source evidence. |
| 2026-10-09 | Linked VIRC-PLN-0034 |
| 2026-10-09 | Linked VIRC-RPT-0051 |
| 2026-10-09 | Closed following verified implementation in VIRC-PLN-0034 and accepted report VIRC-RPT-0051 |
| 2026-10-09 | Reopened: audit revealed unaligned RISC-V access can trap, backend lowering lacks fail-closed verifier for invalid aux, and cross-target -O0..-O3 matrix is unregistered |
| 2026-10-09 | Closed after verifying byte-wise RISC-V lowering, fail-closed metadata verifier, Group 7 test matrix (59/59 PASS), and bit-exact self-host fixed-point in VIRC-RPT-0051 |
