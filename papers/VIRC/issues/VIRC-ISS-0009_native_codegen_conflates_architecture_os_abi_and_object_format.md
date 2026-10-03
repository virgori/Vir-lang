---
id: "VIRC-ISS-0009"
type: "ISSUE"
domain: "VIRC"
title: "Native codegen conflates architecture OS ABI and object format"
status: "TRIAGED"
severity: "S1"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "native-codegen"
  - "target-model"
  - "runtime-abi"
  - "object-writers"
  - "generated-compiler"
  - "modularization"
related:
  issues: []
  plans: []
  reports:
    - "VIRC-RPT-0013"
    - "VIRC-RPT-0015"
supersedes: null
superseded_by: null
tags:
  - "arm64"
  - "x86-64"
  - "elf"
  - "mach-o"
  - "pe-coff"
  - "mcinst"
  - "cross-target"
---

# VIRC-ISS-0009 — Native codegen conflates architecture OS ABI and object format

## 1. Summary

Native executable generation currently selects instruction encoding mostly by
architecture, runtime/startup behavior through an `is_linux` boolean or an
architecture-specific hard-coded implementation, and the executable container
through a separate object-format branch. These choices are not validated as one
coherent `TargetSpec` capability.

Consequently, the active compiler accepts target combinations for which it has
no matching ABI/runtime implementation and returns success after placing Linux
or Darwin machine code inside PE or Mach-O containers. The modular source tree
also has no live ELF source module: the generated compiler retains an embedded
ELF writer behind a dangling source marker, while the multi-target CLI and final
dispatch remain hand-owned by the generated bundle rather than by a canonical
module under `compiler/src/`.

This is both a correctness defect and an architecture-boundary defect. A valid
container header is not evidence that the contained startup sequence, calling
convention, syscalls, relocations, or runtime provider match the declared
target.

## 2. Context

This audit was performed at repository revision
`c2fc28035432b00265adb278983c259676a52aa9` on 2026-10-02 while
`VIRC-PLN-0004` is moving the compiler into `compiler/src/` and splitting large
passes.

The governing active architecture specification is `VIR-SPC-0009`. Its core
requirements include:

- target selection is the orthogonal product of architecture, OS, ABI, and
  object format;
- emitted startup/runtime behavior is determined from target information, not
  the host;
- native binary and assembly paths consume the same MCInst/relocation model;
- object writers own Mach-O/ELF/PE container and relocation details;
- portable runtime code does not own native syscall numbers or OS flags.

This audit inspected ARM64 and x86-64 deeply and followed the shared dispatch
far enough to identify effects on RISC-V, Windows, Wasm, and format overrides.
It did not claim runtime correctness for every instruction or every target.

## 3. Expected Behavior

- A target is selected once as a validated `TargetSpec`; architecture, OS, ABI,
  runtime provider, object format, assembly dialect, page policy, and supported
  features cannot drift independently.
- Native lowering produces target-machine instructions without embedding an OS
  container decision.
- Runtime/startup emission is selected by OS + ABI + runtime provider, not by
  an `is_linux` boolean and not by architecture alone.
- Binary encoding and assembly printing consume the same legalized MCInst
  stream and relocation records.
- ELF, Mach-O, and PE/COFF are independent canonical object-writer modules with
  explicit supported-architecture matrices.
- Unsupported target or `--target`/`--format` combinations fail before codegen
  and leave no artifact.
- Generated `virc.vri` is reproducible from existing canonical source modules;
  no production CLI/backend logic is owned only by the generated file.
- Target matrix verification distinguishes structural container validity from
  executable ABI/runtime validity.

## 4. Actual Behavior

### 4.1 Architecture and OS/runtime are fused in lowering

- `compiler/src/lower/lir_codegen.vri` is a 5,686-line ARM64 module containing
  instruction lowering, function/call fixups, runtime stubs, entry construction,
  Linux and Darwin syscall numbers, `mmap` flags, arena layout, FFI thunks, and
  virtual-address assumptions.
- `emit_lir_module_arm64(lir_funcs, is_linux)` selects only Linux versus
  non-Linux. The non-Linux branch emits Darwin entry and raw syscall behavior;
  there is no Windows ARM64 branch despite `windows-arm64` being advertised as
  a canonical target.
- `compiler/src/lower/lir_codegen_x86.vri` is a 3,487-line System V/Linux
  backend with no OS/ABI parameter. Its module entry emits Linux `mmap`, Linux
  process entry stack handling, Linux `exit`, and fixed ELF virtual addresses.
  The same function is dispatched for Linux x86-64, Windows x86-64, and the
  accepted `macos-x86_64` alias.

### 4.2 Container selection is independent from runtime selection

The generated driver computes `is_linux` as:

```text
target_spec_is_linux(target_spec) OR out_fmt == ELF
```

It then dispatches machine code only by `TargetArch`, and later selects a writer
using a separate chain of `final_fmt == target format OR out_fmt == override`.
No compatibility gate rejects impossible or unimplemented products.

Observed examples compiled with exit status 0:

- `windows-x86_64`: PE32+ x86-64 containing Linux `syscall` instructions and
  Linux x86-64 startup/runtime code;
- `windows-arm64`: PE32+ ARM64 containing Darwin `svc #0x80` paths;
- `macos-x86_64`: Mach-O x86-64 containing Linux syscall numbers, ELF virtual
  address assumptions, and Linux initial-stack handling;
- `linux-arm64 --format macho`: Mach-O ARM64 wrapping Linux startup/syscalls;
- `macos-arm64 --format elf`: the format override sets Linux codegen behavior,
  while the earlier Mach-O writer branch still wins because the target's native
  format is Mach-O.

### 4.3 ELF and the active driver have no canonical modular source

- `compiler/module.list` registers `macho` and `pe`, but no `elf` module.
- `compiler/src/misc/elf.vri` is a symlink to `../rt/elf.vri`; the target path
  `compiler/src/rt/elf.vri` does not exist. Other compatibility symlinks in
  `compiler/src/misc/` have the same broken relative-root shape.
- `compiler/generated/virc.vri` nevertheless embeds a full ELF implementation
  under marker `compiler/src/misc/elf.vri` and imports it as `rt.elf`.
- `tools/sync_virc.py` silently retains content when a marker source does not
  exist and also preserves every section whose marker path ends in `virc.vri`.
  It therefore cannot detect either the orphaned ELF implementation or the
  generated-only driver.
- `CompilerConfig`, CLI target/format parsing, multi-target codegen dispatch,
  and final object-writer dispatch are in a self-owned tail of
  `compiler/generated/virc.vri`; no equivalent source module exists under
  `compiler/src/`.

### 4.4 The binary path bypasses the specified MCInst boundary

- `-S` lowers LIR to MCInst, verifies MCInst, and prints assembly.
- Executable generation directly invokes `emit_lir_module_arm64`,
  `emit_lir_module_x86_64`, or `emit_lir_module_riscv64` and hands raw bytes to
  a container writer.
- `compiler/src/backend/binary.vri` declares Mach-O and ELF intent but implements
  only Mach-O object building; `emit_object_file` always constructs Mach-O.
- `compiler/src/ir/mc/mc_printer.vri` combines ARM64, x86-64, RISC-V, dialect,
  runtime-stub, and string-pool printing in one 2,484-line module. There is no
  corresponding modular binary encoder consuming `MCInst` and `RelocKind`.

### 4.5 Target identity is duplicated across layers

- `TargetArch` is declared separately in `backend/codegen.vri` and `ir/mc/mc.vri`.
- `backend/binary.vri` introduces a third `Arch` enum with different numeric
  values, while CLI code manually translates target architecture into
  `container_arch` integers.
- The active `VIR-SPC-0009` example assigns ARM64 and x86-64 values differently
  from the implementation. This audit treats the active code values as current
  implementation evidence and records the spec/code conflict; it does not
  silently normalize either side.

## 5. Reproduction

From repository root at the audited revision:

```sh
readlink compiler/src/misc/elf.vri
test -e compiler/src/misc/elf.vri
rg -n 'elf =|macho =|pe =' compiler/module.list
python3 tools/sync_virc.py --check

./bin/virc tests/test_hello.vri --target windows-arm64 -q \
  -o /tmp/windows-arm64.exe
./bin/virc tests/test_hello.vri --target windows-x86_64 -q \
  -o /tmp/windows-x86.exe
./bin/virc tests/test_hello.vri --target macos-x86_64 -q \
  -o /tmp/macos-x86
./bin/virc tests/test_hello.vri --target linux-arm64 --format macho -q \
  -o /tmp/linux-arm64-macho
./bin/virc tests/test_hello.vri --target macos-arm64 --format elf -q \
  -o /tmp/macos-arm64-elf

file /tmp/windows-arm64.exe /tmp/windows-x86.exe /tmp/macos-x86 \
  /tmp/linux-arm64-macho /tmp/macos-arm64-elf
objdump -d /tmp/windows-arm64.exe
objdump -d /tmp/windows-x86.exe
objdump -d /tmp/macos-x86
```

Audit artifacts were written under
`/private/tmp/vir_codegen_audit.nfAKZ5/`; they are temporary evidence and are
not part of the repository.

## 6. Evidence

- CONFIRMED: all five reproduction compiles returned exit status 0 using
  `bin/virc` v4.0.0.
- CONFIRMED: `file` identified the requested PE/Mach-O containers, proving the
  issue is not merely a wrong filename extension.
- CONFIRMED: `objdump -d` found repeated x86 `syscall` instructions in the
  Windows x86-64 PE and repeated ARM64 `svc #0x80` instructions in the Windows
  ARM64 PE.
- CONFIRMED: disassembly of `macos-x86_64` contains Linux syscall number 60
  followed by `syscall` in a Mach-O binary.
- CONFIRMED: `lower/lir_codegen.vri:5408-5541` owns both Linux and Darwin ARM64
  entry/syscall selection through `is_linux`.
- CONFIRMED: `lower/lir_codegen_x86.vri:3307-3446` owns Linux-only startup,
  `mmap`, initial-stack, and exit behavior without an OS or ABI argument.
- CONFIRMED: generated driver lines 80285-80311 dispatch executable codegen
  directly from LIR; lines 80368-80398 independently dispatch object writers.
- CONFIRMED: `compiler/src/misc/elf.vri` is dangling, while generated bundle
  lines 4804 onward retain its previous contents.
- CONFIRMED: `tools/sync_virc.py:100-107` explicitly preserves self-owned or
  missing-source sections. `python3 tools/sync_virc.py --check` reported only
  the user's current borrow-module drift and did not report the missing ELF
  source or generated-only driver.
- CONFIRMED: `tests/matrix_runner.py` validates PE headers and only executes
  Windows x86-64 when Wine is available; Windows ARM64 is otherwise
  `BLOCKED_NO_RUNNER`. Structural validation does not inspect ABI, imports,
  syscalls, or runtime-provider compatibility.
- CONFIRMED: focused matrix runs for both `windows-arm64` and
  `windows-x86_64` classified the structurally valid artifacts as
  `BLOCKED_NO_RUNNER`, with zero PASS and zero FAIL. The current gate therefore
  does not reject the statically proven non-Windows runtime payload.
- OBSERVED: `compiler/module.list` is flat for backend/lowering modules and has
  no explicit OS, ABI, object-writer, or binary-encoder ownership groups.
- NOT_VERIFIED: execution on a real Windows ARM64/x86-64 host; static
  disassembly already proves that the emitted runtime ABI is not Windows.
- NOT_VERIFIED: full correctness of native Linux ARM64/x86-64 execution and
  Darwin ARM64 beyond the focused compile/disassembly audit.
- NOT_VERIFIED: RISC-V runtime correctness; its dispatch is affected by the
  same generated-only driver and object-writer architecture, but this issue
  does not claim a reproduced RISC-V miscompile.

## 7. Scope

### Affected

- ARM64 and x86-64 direct binary lowering;
- Linux, Darwin/macOS, and Windows runtime/startup ABI selection;
- Mach-O, ELF, and PE/COFF executable writers;
- target/format CLI validation;
- generated compiler ownership and synchronization;
- MCInst binary/assembly convergence;
- cross-target verification.

### Not affected / Unknown

- Vir source syntax and type semantics are not changed by this issue.
- Parser, semantic passes, and MIR optimization algorithms are outside the
  direct audit scope except where they feed target selection.
- Wasm has a dedicated writer/lowering path; its complete correctness was not
  audited here.
- Dynamic ELF FFI is already rejected explicitly and is not claimed as a new
  defect here.

## 8. Impact

The compiler can report success and produce an artifact with a plausible target
header that cannot obey the selected platform's startup contract, calling
convention, syscall ABI, or runtime-provider contract. This can mislead release
automation and structural target-matrix tests into treating unsupported targets
as implemented.

Severity is S1 because the failure is a target-wide correctness problem with
false-success artifacts, not a cosmetic modularity concern. Priority is P1
because continued backend extraction on top of the current boolean/manual
dispatch would freeze ambiguous boundaries into more modules and increase the
cost of later correction.

## 9. Preliminary Analysis

- CONFIRMED: `TargetSpec` already represents the necessary dimensions, but the
  binary codegen APIs consume only architecture or `is_linux`, so the model is
  not carried through the pipeline.
- CONFIRMED: the current physical split is mostly by historical file or
  architecture, not by the boundaries architecture → ABI/runtime → encoder →
  object writer.
- CONFIRMED: generated-source ownership is incomplete; moving ELF into a real
  compiler module and moving the driver tail into canonical source are
  prerequisites for a reliable module graph.
- HYPOTHESIS: the smallest safe migration is capability-first: make unsupported
  target products fail closed, then introduce typed backend capabilities and
  extract architecture/ABI/writer modules without changing supported output.
- HYPOTHESIS: a shared MCInst binary encoder will remove most divergence between
  `-S` and executable paths, but runtime stubs and container relocations still
  need explicit OS/ABI/object-writer owners.
- NOT_VERIFIED: whether the current `macos-x86_64` alias is intended to become a
  supported target or should be rejected until a Darwin x86-64 runtime exists.
- NOT_VERIFIED: whether Windows targets are roadmap placeholders or release
  claims; current CLI/help and matrix runner present them as canonical targets.

## 10. Acceptance Criteria

- [ ] One canonical target model defines architecture, OS, ABI, runtime
  provider, object format, dialect, page policy, and supported emit kinds; no
  duplicated numeric target translation remains in driver/backend code.
- [ ] The compiler has an explicit capability matrix and rejects unsupported
  target/emission products before lowering, with no output artifact.
- [ ] `--format` cannot create a container/runtime mismatch. Either format is
  derived from `--target`, or each override is validated against an explicitly
  supported target product.
- [ ] ARM64 instruction encoding, AAPCS64 lowering, Darwin runtime/startup,
  Linux runtime/startup, and Windows runtime/startup have separate owners and
  typed interfaces; no `is_linux` boolean crosses the backend API.
- [ ] x86-64 instruction encoding, SysV AMD64, Windows x64, Linux runtime, and
  Darwin runtime have separate owners; unsupported combinations fail closed.
- [ ] ELF, Mach-O, and PE/COFF exist as canonical modules under compiler-owned
  source paths and declare supported architectures independently.
- [ ] No dangling compatibility symlink or missing source marker contributes
  code to `compiler/generated/virc.vri`.
- [ ] The CLI/configuration and final backend dispatch live in canonical source
  modules under `compiler/src/`; the generated bundle contains no hand-owned
  production section.
- [ ] Bundle generation fails on a missing source marker and is reproducible
  from one entry module plus the validated module graph.
- [ ] Both executable and `-S` paths consume the same legalized MCInst stream
  and relocation model, or any temporary divergence is explicitly bounded by a
  linked plan with equivalence tests.
- [ ] Windows targets either execute correctly under Windows/Wine with verified
  Windows ABI/import behavior or are reported as unsupported; a valid PE header
  alone is insufficient.
- [ ] Linux ARM64 and x86-64, Darwin ARM64, every claimed additional target, and
  invalid target/format pairs have positive, negative, structural, disassembly,
  and runtime checks appropriate to the platform.
- [ ] Self-host stage-2/stage-3 fixed-point, generated-source drift, module graph,
  and full relevant regression gates pass before closure.
- [ ] A linked PLAN defines reviewable migration phases, rollback boundaries,
  and compatibility policy; an accepted REPORT maps evidence to every criterion.

## 11. Related Papers

### Issues

- `VIRC-ISS-0006` — compiler tree separation and large-pass modularization;
  this issue narrows the backend boundary and correctness problem discovered
  during that migration.

### Plans

- `VIRC-PLN-0004` — contextual modularization plan. It mentions later codegen
  extraction but does not yet define the OS/ABI/object-writer capability
  boundaries or this issue's false-success gates; it is not linked as an
  implementation plan for this issue yet.

### Reports

- None. No implementation was performed in this audit.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged from ARM64/x86-64 codegen, target-dispatch, object-writer, generated-source, and focused artifact audit |
| 2026-10-02 | Added focused Windows matrix evidence showing structurally valid artifacts remain BLOCKED_NO_RUNNER rather than failing ABI/runtime validation |
| 2026-10-03 | Linked VIRC-RPT-0013 |
| 2026-10-03 | Linked VIRC-RPT-0015 |
