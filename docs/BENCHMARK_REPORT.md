# Vir Performance & Systems Benchmark Methodology

**Architecture**: Apple Silicon ARM64 / Linux x86_64  
**Compilers & Baseline**: Clang (C++ -O3), Rust (`rustc -O`), Go (`gc`), Vir Native AOT (`virc`)

---

## 1. Overview & Measurement Methodology

This document outlines the performance characteristics, architectural efficiency, and benchmarking methodology of the **Vir Programming Language (v2.1.0 Native Toolchain)**.

In systems programming, compiler efficiency is evaluated along multiple concrete axes:
1. **Binary Footprint**: Executable size in bytes without external runtime bloat.
2. **Cold Startup Latency**: Process execution time from kernel launch (`execve`) to entrypoint.
3. **Compilation Overhead**: Compiler wall-clock time from source parsing to binary emission.
4. **Memory Management Overhead**: Allocator latency and absence of non-deterministic Stop-The-World GC pauses.
5. **Syscall Discipline**: Direct kernel supervisor interface (`svc #0x80` on Darwin, `svc #0` on Linux) vs C standard library indirection.

---

## 2. Systems & Runtime Comparison

| Dimension / Characteristic | Vir (v2.1.0 Native) | C++ (Clang) | Rust (Cargo) | Go (gc) |
| :--- | :---: | :---: | :---: | :---: |
| **Execution Model** | **Pure Native AOT** | Native AOT | Native AOT | Native AOT |
| **Runtime Dependency** | **Zero (No Libc)** | `libc++`, `libc` | `libstd`, `libc` | Go runtime |
| **Linker Requirement** | **Linkerless (Direct Binary Emitter)** | `ld64` / `lld` / `mold` | `lld` / `cc` | Internal / External Linker |
| **Syscall Interface** | **Direct Kernel Supervisor (`svc`)** | Via `libc` wrapper | Via `libc` wrapper | Direct Syscall |
| **Typical CLI Binary Size** | **~50 KB** | ~120 KB+ | ~350 KB+ | ~2.1 MB+ |
| **Cold Startup Overhead** | **< 1 ms (Instant)** | ~2 ms | ~2 ms | ~6 ms |
| **Memory Management** | **Arena / Explicit Linear** | RAII / Manual | Ownership / Borrowing | Tracing Garbage Collector |
| **GC Pause Latency** | **0 ms (Zero-GC)** | 0 ms | 0 ms | Non-zero STW pauses |

---

## 3. Compiler Pipeline & Optimization Architecture

The Vir Self-Hosted Modular Compiler (`virc`) employs a 5-tier intermediate representation pipeline:

```text
Source Code (.vri)
   │
   ▼ [10 Semantic Analysis Passes]
Typed AST
   │
   ▼ [Lowering]
High-Level Intermediate Representation (HIR)
   │
   ▼ [SSA & CFG Construction]
Mid-Level Intermediate Representation (MIR)
   │
   ▼ [26 Optimization Passes: TCO, DCE, CSE, LICM, GVN, SCCP, Devirt, DAE, Inlining, SROA, PRE, SLP]
Optimized MIR
   │
   ▼ [Chaitin-Briggs Graph Coloring + George-Appel Iterated Coalescing (31 Registers)]
Low-Level Intermediate Representation (LIR)
   │
   ▼ [Direct Linkerless Mach-O / ELF Container Emitter]
Native Standalone Binary (Zero-Libc)
```

---

## 4. Reproducing Benchmarks

All benchmark harnesses and test programs are located in the `benchmarks/` directory.

To run the native verification suite:
```bash
# Verify standalone binary generation
virc benchmarks/bench_amx.vri -o bin/bench_amx
./bin/bench_amx

# Run package performance suites via Viron
viron test
```
