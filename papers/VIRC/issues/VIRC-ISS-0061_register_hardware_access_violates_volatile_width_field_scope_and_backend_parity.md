---
id: "VIRC-ISS-0061"
type: "ISSUE"
domain: "VIRC"
title: "Register hardware access violates volatile width field scope and backend parity contracts"
status: "CLOSED"
severity: "S0"
priority: "P0"
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
  issues: []
  plans:
    - "VIRC-PLN-0036"
  reports:
    - "VIRC-RPT-0053"
supersedes: null
superseded_by: null
tags:
  - "hardware-access"
  - "mmio"
  - "volatile"
  - "silent-miscompile"
  - "field-layout"
  - "cross-target"
---

# VIRC-ISS-0061 — Register hardware access violates volatile width field scope and backend parity contracts

## 1. Summary

The implemented `register` hardware-access surface violates one compiler
contract at four connected layers: volatile builtins select the wrong access
width, register bit-field metadata is keyed only by field name instead of
owning register type, non-ARM64 targets do not implement or reject bit-field
lowering consistently, and the registered test group reports cross-target
coverage without exercising these paths.

On the host ARM64 path, `volatile_read16` performs an 8-bit read,
`volatile_read32` performs a 64-bit read, `volatile_write16` performs an 8-bit
write, and `volatile_write32` performs a 64-bit write. The 32-bit write can
therefore overwrite an adjacent hardware register or memory-mapped value.
Separately, two register types that reuse the same field name silently share
the first registered bit range; an ordinary entity field with that name can
also be lowered as a register bit field.

This single issue tracks the end-to-end correctness boundary promised by
`register`: typed bit layout, exact-width volatile access, target lowering, and
tests that prove those properties. It does not split the symptoms into
backend-specific issues because they expose the same hardware-access contract
and require one target matrix to close safely.

## 2. Context

`VIR-SPC-0018` section 16 defines `register` as the language construct for
hardware bit-field mappings and requires reads and writes to lower to bit
extraction/insertion while volatile access and ordering are preserved. The
ARM64 direct AOT path contains `UBFX`/`BFI` lowering, and semantic analysis
rejects invalid field ranges and non-constant register field values. The
standard library exports the volatile width variants and bit helpers through
`embedded.mmio`.

The audited compiler was self-hosted `virc 2026.1.6` at revision
`930d21eef3e63b8bae7b748a35e6e8c00f72215b` in a dirty checkout. All temporary
reproduction fixtures and artifacts were removed after the audit.

## 3. Expected Behavior

- `volatile_read8/16/32/64` must read exactly 1, 2, 4, or 8 bytes,
  respectively, with the documented ordering barriers.
- `volatile_write8/16/32/64` must write exactly 1, 2, 4, or 8 bytes and must
  not modify adjacent bytes.
- A register field lookup must be scoped by both the owning register type and
  field name. Reusing a field name in another register or ordinary entity must
  not change its layout or lowering.
- Register field reads and writes must preserve the declared bit start and
  width on every supported backend and optimization level.
- A target without implemented register lowering must reject compilation
  before producing an executable or module; it must not emit a callable
  unresolved stub or a semantically incomplete artifact.
- Direct binary and `-S`/machine-code paths for the same target must implement
  the same register semantics.
- Registered tests must exercise the claimed volatile-width, register-layout,
  optimization-level, and target matrix.

## 4. Actual Behavior

- Builtin IDs for unqualified/32-bit/64-bit volatile reads and writes all map
  to the 64-bit runtime stubs. The 16-bit variants map to the 8-bit stubs.
- The ARM64 runtime-stub layer only implements 8-bit and 64-bit volatile
  operations, so the wrong mapping is observable at runtime.
- Register layout is stored in three global vectors keyed only by field name.
  Duplicate names across register definitions are suppressed, and the
  allegedly scoped lookup functions ignore `base_type`.
- Register field reads and writes use that unscoped metadata. Reusing a name
  silently applies the first encountered start/width to later types, including
  an ordinary entity field with the same name.
- The ARM64 direct AOT path emits working `UBFX`/`BFI` operations, but the
  inspected `-S` path does not preserve equivalent register bit operations.
- Linux x86-64 direct compilation produces an executable whose register-bit
  intrinsic reaches `LIR_RT_UNRESOLVED` and exits rather than implementing the
  operation.
- Linux RISC-V and `wasm32-wasi-p1` compilation reject the register bit
  intrinsic as unsupported. This fail-closed result is safer than the x86-64
  artifact but still demonstrates an incomplete advertised target matrix.
- `./run_tests.sh 16` reports 22/22 PASS. Its test labelled “Register narrow
  cast contract across -O0..-O3 and multi-target” invokes narrow-cast fixtures
  that contain no `register` declaration, and the group does not cover the
  volatile widths or field-name collisions above.

## 5. Reproduction

### 5.1 Volatile access widths

Allocate or otherwise provide an eight-byte writable address, initialize it
to `0x1122334455667788`, and invoke the exported volatile width variants:

```vir
print(volatile_read8(addr))
print(volatile_read16(addr))
print(volatile_read32(addr))
print(volatile_read64(addr))

volatile_write16(addr, 4660)
print(volatile_read64(addr))
```

Observed decimal output from the focused host fixture:

```text
136
136
1234605616436508552
1234605616436508552
52
```

Expected read results are `136`, `30600`, `1432778632`, and
`1234605616436508552`. After `volatile_write16(addr, 4660)`, the low 16 bits
must be `4660`; the observed low value is `52`, proving an 8-bit write. A
separate 32-bit canary fixture observed a 64-bit readback of `1432778632` after
`volatile_write32`, rather than `1234605616436508552`, proving that the upper
32-bit canary was overwritten.

### 5.2 Register field-name collision

Compile and run a focused fixture containing two register types whose field
name is the same but whose bit starts differ:

```vir
register FlagsLow:
    FLAG: 0..0
end.

register FlagsHigh:
    FLAG: 4..4
end.
```

Assign `1` to both fields and print the raw register values. The observed
output is `1,1`; the expected output is `1,16`. In a second fixture, an
ordinary `entity Box` with `value: int` returns `0` instead of `8` when a
register field named `value` is present, showing that the collision crosses
the register/entity boundary.

### 5.3 Target matrix and registered gate

Run the existing host checks and compile the register fixture for each target:

```sh
./run_tests.sh 16
./bin/virc tests/test_register.vri -O0 -q -o /private/tmp/register-o0
./bin/virc tests/test_register.vri -O1 -q -o /private/tmp/register-o1
./bin/virc tests/test_register.vri -O2 -q -o /private/tmp/register-o2
./bin/virc tests/test_register.vri -O3 -q -o /private/tmp/register-o3
./bin/virc tests/test_register.vri --target linux-arm64 -q -o /private/tmp/register-arm64
./bin/virc tests/test_register.vri --target linux-x86_64 -q -o /private/tmp/register-x86
./bin/virc tests/test_register.vri --target linux-riscv64 -q -o /private/tmp/register-riscv
./bin/virc tests/test_register.vri --target wasm32-wasi-p1 -q -o /private/tmp/register.wasm
```

The host executions print `1`, `1`, `3` at `-O0` through `-O3`. The ARM64
direct artifact contains `BFI` and `UBFX`. The x86-64 artifact is produced but
reaches the unresolved runtime stub on the first register insert. RISC-V and
Wasm reject the intrinsic with `E-RISCV-UNSUPPORTED` and
`E-WASM-UNSUPPORTED`, respectively, for LIR op `17`, detail `65602`.

## 6. Evidence

- **CONFIRMED:** `compiler/src/frontend/lexer/tokens.vri:358` recognizes the
  canonical `register` keyword, and
  `compiler/src/frontend/parser/stmt_dispatch/declarations.vri:162` constructs
  a `RegisterDef`.
- **CONFIRMED:** `compiler/src/semantic/typecheck/walk_entity.vri:205` enforces
  register field range diagnostics `E3077`/`E3078`, and
  `compiler/src/semantic/typecheck/walk_field.vri:137` enforces constant field
  values with `E3079`.
- **CONFIRMED:** `compiler/src/lower/lir_codegen/types.vri:516-519` maps
  volatile 16-bit builtins to 8-bit stubs and 32-bit builtins to 64-bit stubs.
- **CONFIRMED:** `compiler/src/lower/lir_codegen/rt_stubs_base.vri:296-321`
  implements only 64-bit and 8-bit volatile load/store stubs in the inspected
  ARM64 direct path.
- **CONFIRMED:** `compiler/src/lower/ast_to_mir/context.vri:219-221` stores
  register starts and widths in global field-name vectors, while
  `compiler/src/lower/ast_to_mir/context.vri:984-991` drops later entries with
  a duplicate field name.
- **CONFIRMED:**
  `compiler/src/lower/ast_to_mir/layout/field_layout.vri:469-478` accepts
  `base_type` in the scoped APIs but ignores it and delegates to unscoped
  field-name lookup.
- **CONFIRMED:** register reads and writes consume the unscoped lookup in
  `compiler/src/lower/ast_to_mir/expr.vri:498-505` and
  `compiler/src/lower/ast_to_mir/stmt.vri:578-588`.
- **CONFIRMED:** `compiler/src/lower/lir_codegen/intrinsics.vri:49` contains
  the ARM64 direct register-bit lowering used by the passing host fixture.
- **CONFIRMED:** `compiler/src/lower/lir_codegen_x86/intrinsics.vri:707-712`
  falls through to `LIR_RT_UNRESOLVED` when the intrinsic kind has no valid
  runtime stub.
- **CONFIRMED:** `compiler/src/lower/lir_codegen_wasm.vri:100-106` does not
  admit the register bit intrinsic in its supported intrinsic set.
- **CONFIRMED:** `stdlib/stdlib.vri:292` registers `embedded.mmio`, and
  `stdlib/vir/embedded/mmio.vri:8` onward exports the affected width variants
  and bit helpers.
- **OBSERVED:** `./run_tests.sh 16` passed 22/22 on 2026-10-09 despite the
  focused failures. `run_tests.sh:1667-1688` derives its cross-target register
  claim from `tests/types/narrow_cast_test.vri`; the invoked fixtures do not
  contain the `register` keyword.
- **OBSERVED:** `tests/test_volatile.vri` prints `12345` successfully at
  `-O0` through `-O3` and its ARM64 disassembly contains ordering barriers,
  but the fixture exercises only the generic/full-width operation and does not
  cover 8/16/32/64-bit width separation.

## 7. Scope

### Affected

- Self-hosted compiler lowering for `register` field reads and writes;
- ARM64 volatile 16-bit and 32-bit reads/writes and any target reusing the same
  builtin-to-runtime-stub mapping;
- x86-64 register bit-field direct artifacts;
- RISC-V and Wasm register feature availability and target diagnostics;
- direct versus `-S`/machine-code parity for register bit operations;
- `embedded.mmio` APIs that expose the affected compiler builtins;
- group 16 and cross-target conformance claims.

### Not affected / Unknown

- Lexer/parser recognition and the inspected semantic range/constant checks
  behave as designed for the existing fixtures.
- The ARM64 direct AOT bit extraction/insertion path works for
  `tests/test_register.vri` at `-O0` through `-O3`.
- Generic/full-width volatile access and ARM64 barriers work in the existing
  `tests/test_volatile.vri` fixture; this does not establish narrow-width
  correctness.
- `VIRC-ISS-0023` concerns upper-bit preservation for mold/unsigned narrow
  casts and is not a duplicate of this hardware-access issue.
- `VIRC-RPT-0051` verifies typed packed-entity load/store width fixes; it does
  not cover volatile builtins or register field identity and is not a closure
  record for this issue.
- **NOT_VERIFIED:** runtime execution of the generated Linux ARM64 artifact on
  Linux; its `BFI`/`UBFX` instructions were inspected statically.
- **NOT_VERIFIED:** ordering requirements beyond the existing ARM64 barrier
  checks on non-ARM64 targets.

## 8. Impact

A valid program can silently access the wrong number of bytes at a
memory-mapped hardware address. In particular, a 32-bit write currently uses a
64-bit store on the inspected host path and can modify the adjacent register,
which may acknowledge interrupts, change device state, or corrupt unrelated
memory. Field-name collisions are also silent miscompilations: source types
declare distinct layouts, but generated code uses whichever homonymous field
was registered first.

Severity is `S0` because the compiler can emit a successful artifact that
performs an unintended hardware write outside the declared width. Priority is
`P0` because affected APIs are exported through the standard library and the
current green test result gives no warning; unsupported target paths must fail
closed until they are correct.

## 9. Preliminary Analysis

- **CONFIRMED:** the volatile defect is caused by width-collapsing builtin ID
  mapping plus the absence of 16-bit and 32-bit ARM64 runtime stubs.
- **CONFIRMED:** the field collision is caused by global field-name identity;
  the existing “scoped” API does not use its type argument.
- **CONFIRMED:** ARM64 direct lowering and the generic `-S`/machine-code path do
  not currently establish the same register behavior.
- **CONFIRMED:** target behavior is inconsistent: ARM64 implements the bit
  intrinsic, x86-64 emits a failing artifact, and RISC-V/Wasm reject it.
- **CONFIRMED:** the registered group 16 label overstates the exercised
  register and target coverage.
- **HYPOTHESIS:** register metadata keyed by canonical type identity plus field
  identity can remove both register/register and register/entity collisions.
- **HYPOTHESIS:** a width-parametric volatile lowering contract shared by
  native backends can prevent future builtin-ID aliasing.
- **NOT_VERIFIED:** whether 16/32-bit volatile operations should use dedicated
  runtime stub IDs or lower directly at each call site.
- **NOT_VERIFIED:** whether RISC-V/Wasm `register` support is required for the
  current release or should remain an explicit compile-time capability error.

## 10. Acceptance Criteria

- [x] A focused ARM64/runtime test proves that volatile reads return exactly
      the low 8, 16, 32, and 64 bits of a canary value.
- [x] Canary tests prove that volatile writes modify exactly 1, 2, 4, or 8
      bytes and preserve every byte outside the requested width.
- [x] Each exported volatile width variant maps to a width-correct lowering;
      no 16-bit operation aliases an 8-bit stub and no 32-bit operation aliases
      a 64-bit stub.
- [x] Barrier instructions and ordering semantics remain present for every
      implemented width.
- [x] Register field metadata is keyed by owning type and field identity, and
      two register types may reuse a field name with different starts/widths.
- [x] An ordinary entity field with the same name as a register field retains
      ordinary entity load/store semantics.
- [x] ARM64, x86-64, RISC-V, and Wasm either implement correct register bit
      extraction/insertion in every artifact path or reject the feature before
      emitting an artifact with a target-specific diagnostic.
- [x] For every supported target, direct binary/object and `-S`/machine-code
      paths have equivalent register semantics.
- [x] Registered tests cover field reads/writes, duplicate field names,
      entity/register name isolation, volatile 8/16/32/64 widths, and
      `-O0` through `-O3`.
- [x] Group 16 descriptions match the fixtures they execute; no narrow-cast
      fixture without `register` is reported as proof of register target
      coverage.
- [x] `tests/test_register.vri`, `tests/test_volatile.vri`, the focused
      regressions, and the full registered suite pass on every available target
      runner, with explicit fail-closed expectations for unavailable features.

## 11. Related Papers

### Issues

- `VIRC-ISS-0023` — adjacent mold/narrow-cast upper-bit preservation issue;
  audited and rejected as a duplicate.

### Plans

- `VIRC-PLN-0036` — Fix register hardware access, volatile width, field scope, and backend parity.

### Reports

- `VIRC-RPT-0051` — packed typed load/store width verification; relevant
  precedent, but it does not cover the contracts tracked here.
- `VIRC-RPT-0053` — Register hardware access volatile width, field scope, and
  backend parity verification report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened one consolidated issue from the `register` hardware-access audit |
| 2026-10-09 | Linked VIRC-PLN-0036 |
| 2026-10-09 | Linked VIRC-RPT-0053 |
| 2026-10-09 | Resolved and closed; verified by VIRC-RPT-0053 with full test coverage and bootstrap parity |
| 2026-10-09 | Reopened: audit revealed missing x86 mfence in volatile stubs, untested 64-bit write canary preservation, and missing registered target/opt matrix for register fixtures in Group 16 |
| 2026-10-09 | Reopened: audit revealed -S assembly pipeline omitted volatile barriers/instructions, fail-open test oracles, and incomplete optimization matrix |
| 2026-10-09 | Resolved and closed: verified by VIRC-RPT-0053 with -S assembly parity on ARM64/x86-64, hardened Group 16 assembly test oracles, all 6 register/volatile fixtures across -O0..-O3, and bit-for-bit bootstrap (19,404,080 bytes) |
