# Vir Compiler 3.8.1

Vir Compiler 3.8.1 qualifies the self-contained Linux compiler binaries for
x86_64 and ARM64.

## Fixes

- Correct System V AMD64 stack-argument ordering for calls with more than six
  integer arguments.
- Detect Linux ARM64 at runtime so allocator and syscall lowering use Linux
  syscall numbers and flags instead of macOS values.
- Remove macOS-only diagnostic runtime dependencies from Linux compiler paths.
- Improve x86_64 spill handling and displacement encoding used by the
  self-hosted compiler.
- Include the canonical standard-library module registry required by clean
  checkouts and release CI.

## Verification

- Native macOS ARM64 compiler smoke: `30`, `90`.
- Vir `min` suite: 331/331 passed.
- Linux x86_64 QEMU: compiler version, self-compilation smoke, and generated
  executable all passed.
- Linux ARM64 QEMU: compiler version, self-compilation smoke, and generated
  executable all passed.

## Release assets

- `virc-v3.8.1-macos-arm64`
- `virc-v3.8.1-linux-x86_64`
- `virc-v3.8.1-linux-arm64`

The Linux binaries are static ELF executables and do not require a host C
compiler or dynamic runtime libraries.
