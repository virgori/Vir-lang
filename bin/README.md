# Vir Compiler Official Native Binaries (v2.8.5)

Precompiled self-hosted standalone binaries for the Vir Compiler toolchain (`v2.8.5`), featuring native support for **Spec §26 AI/ML Mathematical Operators**, postfix percent `%`, and strict **§4.4 / §7.3 `packed entity`**.

All binaries are pure native executables with zero external runtime dependencies.

## Target Matrix

| Target Architecture | Binary | File Size | Binary Format & ABI | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **macOS Apple Silicon** | `virc` (or `virc-macos-arm64`) | 2.0 MB | Mach-O 64-bit arm64 | `34f769132b10d357049112825717a02a583f0204032d00043d536a5be6852d19` |
| **Linux ARM64** | `virc-linux-arm64` | 2.0 MB | ELF 64-bit LSB aarch64 (static, stripped) | `32fed169a00ac062614e99b41b9ec26448a93ad6883f56b2f8bcf481b0b903bd` |
| **Linux x86_64** | `virc-linux-x86_64` | 1.4 MB | ELF 64-bit LSB x86-64 (static, stripped) | `2a3ddc4dcb37d818239e6b13194c697b651ee5234d43611c2ec75f38f8eaad08` |
| **Linux RISC-V 64** | `virc-linux-riscv64` | 2.0 MB | ELF 64-bit LSB riscv64 (RVC, double-float ABI, static) | `52f095953209f166eb417ca476f570b45a42ccf7f896ac68726231c0f3822b45` |
| **WebAssembly** | `virc-wasm32.wasm` | 754 B | WebAssembly binary module (MVP) | `eae339254dd270ff1dafc4fb194ded5cc1c03f7afaa5d01693525fd3989bbb03` |

## Usage

```bash
# macOS Apple Silicon
./bin/virc main.vri -o app && ./app

# Linux ARM64
./bin/virc-linux-arm64 main.vri -o app && ./app

# Linux x86_64
./bin/virc-linux-x86_64 main.vri -o app && ./app

# Linux RISC-V 64
./bin/virc-linux-riscv64 main.vri -S -o app.s

# WebAssembly
wasmtime ./bin/virc-wasm32.wasm
```
