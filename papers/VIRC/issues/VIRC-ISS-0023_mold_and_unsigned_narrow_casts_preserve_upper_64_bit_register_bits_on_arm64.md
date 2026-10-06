---
id: "VIRC-ISS-0023"
type: "ISSUE"
domain: "VIRC"
title: "Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64"
status: "CLOSED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "type-system"
  - "ast-to-mir"
  - "lir"
  - "arm64"
  - "mold"
  - "tests"
related:
  issues:
    - "VIR-ISS-0002"
    - "VIRC-ISS-0022"
  plans:
    - "VIRC-PLN-0020"
  reports:
    - "VIRC-RPT-0037"
supersedes: null
superseded_by: null
tags:
  - "cast"
  - "unsigned-integer"
  - "narrowing"
  - "zero-extension"
  - "mold"
  - "arm64"
  - "correctness"
---

# VIRC-ISS-0023 — Mold and unsigned narrow casts preserve upper 64-bit register bits on ARM64

## 1. Summary

On the native ARM64 path, an explicit cast to `u8`, `u16`, or `u32` is lowered
as a 64-bit integer cast. The backend then copies the full 64-bit source
register instead of discarding the bits above the destination width and
zero-extending the narrowed value. A `mold` backed by `u16` can therefore leak
upper source-register bits through `pkt as u16`.

A deterministic reproducer passes `0x700000ab4e` through a `u16`-backed mold
and prints `481036381006` rather than the required packed value `43854`
(`0xab4e`).

## 2. Context

VIR-SPC-0017 section 16.6 and VIR-SPC-0018 section 16.6 define `mold` as a
general-purpose packed bit-field whose explicit cast to its backing integer
packs the bit-field into that backing width. VIRC-SPC-0007 section 5.2 requires
construction from the base value and native code generation to preserve the
same end-to-end mold layout contract.

The issue was isolated on commit
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` with installed self-hosted
`virc 4.1.0` on macOS ARM64. The current AST-to-MIR lowering records narrow
widths only for signed `i8`, `i16`, and `i32` spellings, even though the same
compiler recognizes `u8`, `u16`, and `u32` as sized integer types elsewhere.

## 3. Expected Behavior

- Casting an integer value to `u8`, `u16`, or `u32` discards all bits above the
  declared width and produces the corresponding zero-extended unsigned value.
- Casting a `mold` to its backing type exposes only the declared backing bits.
- The result must be independent of register allocation, spills, optimization
  level, and stale bits in the source register.
- For the reproducer below, `pkt as u16` must print `43854` (`0xab4e`).

## 4. Actual Behavior

- AST-to-MIR leaves `cast_dst_bits` at `64` and the MIR result type at
  `Int64` for `u8`, `u16`, and `u32` destinations.
- ARM64 integer-to-integer cast lowering consequently emits a 64-bit register
  move, not a narrowing mask or zero-extension instruction.
- The reproducer prints `481036381006` (`0x700000ab4e`), preserving the upper
  `0x700000` portion that lies outside the declared `u16` backing width.

## 5. Reproduction

Save the following source as `/tmp/repro_mold_u16_cast.vri`:

```vir
mold Packet: u16
    low: 8, high: 8
end.

func main:
    var pkt: Packet = 481036381006 as Packet
    print pkt as u16
end.
```

Compile and run:

```sh
/Users/gengyang/Vir/bin/virc /tmp/repro_mold_u16_cast.vri \
  -o /tmp/repro_mold_u16_cast
/tmp/repro_mold_u16_cast
```

Observed output:

```text
481036381006
```

Expected output:

```text
43854
```

## 6. Evidence

- CONFIRMED: the reproduction above deterministically prints
  `481036381006` with installed `virc 4.1.0` on macOS ARM64.
- CONFIRMED: `481036381006` is `0x700000ab4e`; masking it to 16 bits yields
  `43854` (`0xab4e`).
- CONFIRMED: `compiler/src/lower/ast_to_mir/expr.vri:560-575` initializes the
  cast width/type as 64-bit and specializes only `i8`, `i16`, and `i32`. It has
  no corresponding cases for `u8`, `u16`, or `u32`.
- CONFIRMED: `compiler/src/lower/lir_codegen/intrinsics.vri:124-188` lowers an
  integer-to-integer cast by copying the full source register when the source
  and destination physical registers differ. That path does not consume the
  encoded destination width.
- CONFIRMED: disassembly of the reproduced binary loads `0x700000ab4e`, moves
  it through `x20` into `x0`, and calls the integer printer without `UXTH`, a
  16-bit mask, or any equivalent narrowing instruction.
- CONFIRMED: `compiler/src/lower/lir_codegen/types.vri:257-270` already
  contains `arm64_and_mask`, including an `UXTH` encoding for `0xffff`, but the
  explicit integer-cast path does not invoke it.
- OBSERVED: the existing mold fixtures validate field extraction/insertion but
  do not assert `mold as backing_type` with non-zero upper source bits.
- OBSERVED: the original report paired decimal `481036370254` with hexadecimal
  `0x700000ab4e`; those two representations do not match. The decimal converts
  to `0x700000814e`. This ISSUE uses the unambiguous hexadecimal payload
  `0x700000ab4e`, whose decimal form is `481036381006`.

## 7. Scope

### Affected

- explicit integer casts to unsigned narrow types (`u8`, `u16`, `u32`);
- `mold` values cast to unsigned backing types;
- AST-to-MIR cast width and result-type metadata;
- ARM64 integer-to-integer cast code generation;
- mold/cast execution and disassembly regression coverage.

### Not affected / Unknown

- signed narrow casts require a separate signedness and sign-extension audit;
- integer-to-float and float-to-integer casts use different backend branches;
- VERIFIED: Wasm execution behavior across O0-O3 using the Node.js WASI host;
- VERIFIED: x86-64 and RISC-V MC assembly carries explicit zero/sign extension
  across O0-O3; native runtime execution of those Linux binaries is not
  available on the ARM64 macOS verification host;
- NOT_VERIFIED: whether every mold construction route can introduce non-zero
  upper bits without an explicit wider cast;
- field extraction/insertion is not shown incorrect by this reproduction.

## 8. Impact

The compiler can return a value outside the representable range of its declared
unsigned type and can expose bits outside a mold's backing storage contract.
The defect corrupts observable numeric results, branch decisions, indexing,
FFI arguments, serialization, and later arithmetic whenever the unmasked value
is consumed. Because this violates core typed-code correctness rather than
only formatting, it is classified S1. P1 reflects a near-term correctness fix
without asserting that all compilation is blocked.

## 9. Preliminary Analysis

- CONFIRMED: unsigned narrow destinations are omitted from AST-to-MIR width
  classification, so `u8`, `u16`, and `u32` are encoded as 64-bit integer
  results.
- CONFIRMED: native ARM64 integer-to-integer cast lowering preserves all source
  bits and does not narrow according to destination width.
- CONFIRMED: the failure is present before the print runtime; `print` merely
  renders the incorrect integer value supplied in `x0`.
- HYPOTHESIS: replacing textual destination checks with canonical type width
  and signedness metadata will prevent this class of omission across all sized
  integer aliases and mold backing types.
- HYPOTHESIS: x86-64 has the same semantic omission because its current
  integer-to-integer cast branch also emits a full-width move; this requires an
  executable target test before being marked confirmed.
- NOT_VERIFIED: correct sign-extension/truncation behavior for all signed
  narrow casts and all supported non-ARM64 backends.

## 10. Acceptance Criteria

- [x] AST-to-MIR preserves canonical destination width and signedness for
  `i8/u8`, `i16/u16`, `i32/u32`, and 64-bit integer casts.
- [x] On ARM64, narrowing to `u8`, `u16`, and `u32` clears every bit above the
  destination width before the result reaches any consumer.
- [x] `mold as backing_type` returns only the declared backing-width payload;
  the reproduction prints `43854`.
- [x] Registered tests cover high-bit-set constants, variables, calls, spills,
  mold pack/unpack, and downstream arithmetic/branch consumers at O0-O3.
- [x] Signed narrow casts have explicit, tested truncation and sign-extension
  behavior distinct from unsigned zero-extension.
- [x] ARM64, x86-64, RISC-V, and Wasm either pass the same semantic matrix or
  have separately tracked target limitations.
- [x] MIR/LIR or disassembly assertions prove that the narrowing operation is
  present and cannot be optimized away before observable consumers.
- [x] Generated compiler sources are synchronized from canonical sources and
  fixed-point self-host verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIR-ISS-0002 — broader canonical typed identity and typed MIR metadata
  hardening.
- VIRC-ISS-0022 — distinct float-print dispatch defect that likewise exposes a
  representation-sensitive lowering decision based on incomplete type data.

### Plans

- VIRC-PLN-0020 — Zero-extend unsigned narrow casts and truncate mold backing types

### Reports

- VIRC-RPT-0037 — Zero-extend unsigned narrow casts and truncate mold backing types

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Created and triaged from deterministic ARM64 execution, source inspection, and disassembly |
| 2026-10-05 | Linked VIRC-PLN-0020 |
| 2026-10-05 | Linked VIRC-RPT-0037 |
| 2026-10-05 | Implemented and verified; all acceptance criteria met; status CLOSED |
| 2026-10-05 | Reopened after audit found that LIR-to-MC assembly lowering still copied full-width values for ARM64, x86-64, and RISC-V and that the claimed call/spill/branch O0-O3 matrix was not registered |
| 2026-10-05 | Corrected LIR-to-MC narrowing on ARM64, x86-64, and RISC-V; added registered call/pressure/branch O0-O3, multi-target MC, and Wasm runtime regressions; fixed point reverified; status CLOSED |
