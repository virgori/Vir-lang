# Vir Compiler Release Notes — v3.8.0

**Release date:** 2026-09-28

**Compiler version:** `virc 3.8.0 (self-hosted)`

**Change range:** `e30b512e` (v3.6.0) through the v3.8.0 release commit

## Overview

Virc 3.8.0 consolidates every compiler fix and feature committed after v3.6.0. The release focuses on safe multi-target machine-code generation, SIMD/vector lowering, hardened arena allocation and promotion, strict Vir v2.0 declaration parsing, and regression coverage that fails closed instead of accepting incomplete output.

## Highlights

### Safe machine-code and symbol pipeline

- Replaced heuristic UFCS signature matching with canonical resolved-symbol identity.
- Added explicitly tagged MC symbol operands and trusted in-memory provenance tracking.
- Made MC verification fail closed across ARM64, x86-64, RISC-V, and Wasm paths.
- Removed unsafe filesystem/pointer probing and rejected unregistered symbols before dereference.
- Resolved Wasm calls and addresses from real LIR/FFI tables and hardened null-provider handling.
- Enforced assembly and artifact rejection when unresolved symbols or unsupported operations remain.

### SIMD, vector IR, and optimization

- Added explicit `flux<T, N>` vector semantics, swizzle reads/writes, deep-copy assignment, and strict lane/width validation.
- Added MIR/LIR vector operations and native 128-bit lowering for ARM64 NEON, x86 SSE2, and Wasm SIMD128, with a verified RISC-V scalar fallback.
- Added SLP and one-dimensional loop auto-vectorization, then removed the unsafe load-clobber transformation.
- Hardened induction-variable proofs, RVV opcode rejection, structural oracles, and benchmark gates.

### Arena and memory safety

- Added checked O(1) arena reserve, aligned allocation, and bulk zero/fill/copy operations.
- Added optimized copy/set/move paths with overlap-safe fallbacks and small-copy fast paths.
- Prevented integer overflow in arena and runtime allocation size/alignment arithmetic.
- Fixed multi-escape promotion slot aliasing, throw/revert promotion ordering, and X28 arena-reset corruption.
- Added SIMD promotion paths and deep-graph traversal for ARM64, x86-64, and Wasm.
- Fixed x86-64 spilled operands and destinations for arena mark/reset/drop/promote intrinsics.

### Parser and Vir v2.0 conformance

- Added grouped multi-line and semicolon-separated `var`, `let`, and `const` declarations.
- Added strict declaration lookahead so following statements are not swallowed.
- Preserved scope, immutability, type diagnostics, and MIR lowering across grouped declarations.
- Added precise rejection for comma separators, duplicates, shadowing, malformed declarations, use-before-declaration, and type mismatches.

### Cross-target diagnostics and regression coverage

- Added explicit unsupported-operation diagnostics for RISC-V instead of emitting broken ELF files.
- Hardened Wasm validation, throw trapping, string/import handling, and Node.js WASI test execution.
- Added semantic QEMU gates for x86-64 deep arena promotion in SIMD and non-SIMD modes.
- Added regression coverage for void-value lowering, unresolved UFCS receivers, module-order independence, fake symbol addresses, and zero-artifact failure behavior.

## Included commits after v3.6.0

- `ab3b802f` — v3.6.1 version bump and promoted compiler.
- `15e4d0cf`..`81de3430` — cross-backend parity, arena bulk operations, vector IR, native SIMD, and auto-vectorization.
- `52951e93`..`83637546` — SIMD/arena hardening, deep-graph promotion, QEMU gates, and x86 spill fixes.
- `7868e0e9`..`5d06785d` — regression locking and grouped declaration support.
- `cf6766eb`..`e0d52295` — void lowering coverage, canonical UFCS identity, tagged MC symbols, fail-closed verification, and in-memory symbol provenance.

## Compatibility

- Language target remains Vir Spec v2.0.
- Release targets remain macOS arm64, Linux arm64, Linux x86_64, Linux riscv64, and Wasm32/WASI where supported by the relevant backend.
- The release freeze is stored separately under `frozen/release/v3.8.0/` and records the exact Git commit in `MANIFEST.json`.

## Release verification

- Compiler bundle synchronization: PASS (`python3 tools/sync_virc.py --check`).
- Self-hosted fixed point: PASS (signed stage 2 and stage 3 are bit-for-bit identical).
- Promoted compiler SHA-256: `01c469355c3a3ec8065d2447eff0a952c21064a20863d64cfb69cf4e15560bf0`.
