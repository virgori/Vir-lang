# Vir Codegen & Backend Emitter — Handover Documentation
# ======================================================
# Last updated: 9 March 2026
# Author: AI (GitHub Copilot)

## Overview
This document explains the Vir backend emitter, codegen, and self-hosting linker modules. It is intended for new maintainers or contributors to continue development, extend targets, or debug the system.

### Directory Structure
- `stdlib/vir/codegen/arm64.vri` — ARM64 backend (NEON SIMD, macOS ABI)
- `stdlib/vir/codegen/x86_64.vri` — x86-64 backend (SSE2/AVX2, System V ABI)
- `stdlib/vir/codegen/emitter.vri` — Emitter framework (pattern selection, QIR-L orchestration)
- `stdlib/vir/codegen/binary.vri` — Mach-O/ELF object file emitter
- `stdlib/vir/codegen/linker.vri` — Self-hosting linker (symbol resolution, relocation, executable generation)

## Key Concepts
- **QIR-L nodes**: Lowered intermediate representation for backend codegen.
- **Grade S/A/B**: Rule-based ranking for kernel patterns (S = optimal, A = good, B = fallback).
- **Micro-kernels**: Small, highly optimized routines (GEMM, elementwise, ReLU) for vector hardware.
- **Mach-O/ELF emission**: Direct binary object file generation, bypassing external assembler/linker.
- **Self-hosting linker**: Vir can link its own binaries, resolving symbols and applying relocations.

## Emitter Framework (`emitter.vri`)
- Orchestrates codegen from QIR-L nodes to platform assembly.
- Uses pattern registry and rule-based selection.
- Supports multiple targets (ARM64, x86_64, future WASM).
- Entry point: `emit_vir_kernel_module(name: String)`

## ARM64 Backend (`arm64.vri`)
- Defines register classes, instruction emitters (mov, add, sub, mul, ldr, str, bl, ret).
- NEON SIMD: fadd.4s, fmul.4s, fmla.4s, fmax.4s, ld1, st1.
- Micro-kernels: `emit_micro_gemm_4x4`, `emit_ew_add_neon`, `emit_relu_neon`.
- MacOS ABI helpers: header, global function, data section, float constant.

## x86-64 Backend (`x86_64.vri`)
- Register model: GPR64, XMM (SSE2), YMM (AVX2).
- SSE2: 4-wide float ops (addps, mulps, movaps).
- AVX2: 8-wide float ops (vaddps, vmulps, vfmadd231ps).
- Micro-kernels: `x86_emit_micro_gemm_8x8`, `x86_emit_ew_add_avx`, `x86_emit_relu_avx`.
- System V ABI helpers: prologue, epilogue, global function.

## Binary Format Emitter (`binary.vri`)
- Mach-O 64-bit object file emission: header, segments, sections, symtab, relocations.
- ELF 64-bit support (Linux): header, section headers, .text, .data, .symtab, .strtab.
- High-level API: `emit_object_file`, `emit_kernel_object`.

## Self-Hosting Linker (`linker.vri`)
- Symbol resolution, relocation patching (ARM64, x86-64), section merging.
- Produces final executable Mach-O binary (no external `ld`).
- High-level API: `link_objects`, `link_single_kernel`.

## Maintenance & Extension
- To add new backend: create `target.vri` (e.g., `wasm.vri`), implement register/instruction model, micro-kernels, ABI helpers.
- To extend binary formats: update `binary.vri` for new object/executable formats.
- To debug: use test suite (`tests/`), check kernel pattern registry, verify symbol resolution and relocation.
- To optimize: tune micro-kernels, add new Grade S/A patterns, improve vectorization.

## Contact & Further Reading
- See `docs/virgori_library_design_plan.md` for roadmap and design rationale.
- For questions, contact previous maintainers or refer to commit history.

---
**All codegen modules are fully documented and ready for handover.**
