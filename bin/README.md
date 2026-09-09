# Vir Compiler Official Native Binaries (v2.8.5)

Precompiled self-hosted standalone binaries for the Vir Compiler toolchain (`v2.8.5`), featuring native support for **Spec §26 AI/ML Mathematical Operators**, postfix percent `%`, and strict **§4.4 / §7.3 `packed entity`**.

All binaries are pure native executables with zero external runtime dependencies.

## Target Matrix

| Target Architecture | Binary | File Size | Binary Format & ABI | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **macOS Apple Silicon** | `virc` (or `virc-macos-arm64`) | 2.0 MB | Mach-O 64-bit arm64 | `bd09638d33312a0c1f393df339601ec47478106350bb2c7ff59234be45300f87` |
| **Linux ARM64** | `virc-linux-arm64` | 2.0 MB | ELF 64-bit LSB aarch64 (static, stripped) | `7889429a720ab175c83f79b4ea93b5ae1f49bb9b81155aa08f7fde1f82308808` |
| **Linux x86_64** | `virc-linux-x86_64` | 1.4 MB | ELF 64-bit LSB x86-64 (static, stripped) | `ebe23a5ec45337fe2abf2a9c3f332a74e6a45d02e24300a7fa36692f0056676a` |
| **Linux RISC-V 64** | `virc-linux-riscv64` | 2.0 MB | ELF 64-bit LSB riscv64 (RVC, double-float ABI, static) | `84d84830d109ff0285a2ee602b7a9716c775dc99abd7807fc0d176df37661f4c` |
| **WebAssembly** | `virc-wasm32.wasm` | 754 B | WebAssembly binary module (MVP) | `e2dc2f81ec6acf51dd23d71ed7fe72e989a9f5f3a9c1a7eb1a73691fc2e21038` |

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
