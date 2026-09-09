# Vir Compiler v2.8.5 Release Report — AI/ML Hardening, Postfix Percent & Strict Packed Entity

- **Release Version**: `virc v2.8.5 (self-hosted)`
- **Release Date**: September 10, 2026
- **Status**: Production-Ready / General Availability (100% PASS)
- **Frozen Release Tree**: `frozen/release/v2.8.5` (491 files: 401 stdlib, 90 compiler source files, native signed binary, verified SHA-256)

---

## 1. Release Highlights

Vir Compiler **v2.8.5** delivers critical stability hardening and complete specification compliance according to **Vir Language Specification v2.0**:

### 1.1 Robust Tensor Mutation & Coercion (Spec §26)
- **Zero-Allocation Shape Safeguards**: Fixed zero-element buffer allocations when initializing empty float tensors, guaranteeing minimum 8-byte memory slots per element.
- **Automatic Element Coercion**: Automatically coerces integer literal values when mutating multi-dimensional float tensors (`tensor<f32>[M, N]`), ensuring clean dispatch between integer matrix multiplication (`LIR_RT_MATMUL`) and floating-point SIMD kernels (`LIR_RT_MATMUL_F64`).

### 1.2 Postfix Percent Operator `%` (Spec §10 & §30)
- Full support for postfix percent operator (`value%`), evaluating to `value / 100`.
- Native support across both integers and IEEE 754 floating-point numbers.
- Integrated into operator precedence hierarchy and reinforced with strict semantic validation (rejecting prefix usage and non-numeric types).

### 1.3 Strict `packed entity` Layout & Diagnostics (Spec §4.4 & §7.3)
- **Canonical Syntax Enforcement**: Mandates `packed entity Name: ... end.`, rejecting deprecated shorthand `packed Name:`.
- **Exact Sequential Byte Alignment**: Field offsets are packed strictly according to primitive byte widths with alignment 1 byte (zero padding, no rounding up to 8-byte boundaries).
- **Compile-Time `sizeof(Type)` Operator**: Native `sizeof(Type)` expression evaluating to the precise physical byte length of packed data structures.
- **Typed Memory Instructions on ARM64**: Direct generation of width-specific load/store instructions (`LDRB`/`LDRSB`, `LDRH`/`LDRSH`, `LDR W`/`LDRSW`, `LDR X`, `STRB`, `STRH`, `STR W`, `STR X`), preventing clobbering of neighboring unaligned fields.
- **Exhaustive Diagnostic Codes (E3025–E3030)**: Complete reporting for missing type annotations, dynamic types, recursive layout cycles, heap entity embeddings, missing/duplicate constructor fields, and integer bounds overflow.

### 1.4 Production Freeze (`frozen/release/v2.8.5`)
- Standalone snapshot frozen at `frozen/release/v2.8.5`, verified against `SHA256SUMS` (491/491 files OK).

---

## 2. Official 5-Target Release Binary Matrix (`bin/`)

All binaries are self-contained, standalone executables compiled directly from clean self-hosted compiler source:

| Target Architecture | Binary | File Size | Binary Format & ABI | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **macOS Apple Silicon** | `bin/virc-macos-arm64` (and `virc`) | 2.0 MB | Mach-O 64-bit arm64 | `bd09638d33312a0c1f393df339601ec47478106350bb2c7ff59234be45300f87` |
| **Linux ARM64** | `bin/virc-linux-arm64` | 2.0 MB | ELF 64-bit LSB aarch64 (static, stripped) | `7889429a720ab175c83f79b4ea93b5ae1f49bb9b81155aa08f7fde1f82308808` |
| **Linux x86_64** | `bin/virc-linux-x86_64` | 1.4 MB | ELF 64-bit LSB x86-64 (static, stripped) | `ebe23a5ec45337fe2abf2a9c3f332a74e6a45d02e24300a7fa36692f0056676a` |
| **Linux RISC-V 64** | `bin/virc-linux-riscv64` | 2.0 MB | ELF 64-bit LSB riscv64 (RVC, double-float ABI, static) | `84d84830d109ff0285a2ee602b7a9716c775dc99abd7807fc0d176df37661f4c` |
| **WebAssembly** | `bin/virc-wasm32.wasm` | 754 B | WebAssembly binary module (MVP) | `e2dc2f81ec6acf51dd23d71ed7fe72e989a9f5f3a9c1a7eb1a73691fc2e21038` |

---

## 3. Verification & Test Suite Results

- **Group 7 (Entity & Packed Entity)**: `55/55 PASS (100%)` across all struct, member method, chained access, and strict packed tests.
- **Specification Conformance (`run_tests.sh min`)**: `97/97 PASS (100%)` across all 31 specification chapters.
- **Self-Hosting Bootstrap**: Perfect convergence with native Mach-O ARM64 code execution verified (`30 90`).
