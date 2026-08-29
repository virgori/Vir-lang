# The Vir Programming Language

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Target](https://img.shields.io/badge/Targets-ARM64%20|%20x86__64%20|%20RISC--V%20|%20WASM-orange.svg)]()
[![Platform](https://img.shields.io/badge/OS-macOS%20|%20Linux%20|%20Windows-blueviolet.svg)]()
[![Stdlib](https://img.shields.io/badge/Stdlib-81%20Modules-success.svg)]()
[![Zero-Dependency](https://img.shields.io/badge/Dependencies-Zero%20(No%20Libc,%20No%20External%20Linker)-brightgreen.svg)]()

**Vir (Virgori)** is a modern, high-performance systems programming language designed for bare-metal performance, predictable memory safety, and seamless multilingual tooling.

Vir compiles directly to standalone native machine code (**macOS Mach-O 64-bit**, **Linux ELF 64-bit**, **Windows PE32+**, and **WebAssembly WASM32**) with **zero external dependencies** — no `libc`, no `clang`/`gcc`, and no external linker (`ld`/`lld`).

---

## Key Features

- ⚡ **Zero-Libc & Linkerless Direct Kernel Syscalls:** Direct supervisor call execution (`svc #0x80` / `svc #0`) and built-in binary format emitters.
- 🚀 **10-Pass Optimization Engine:** Chaitin-Briggs Graph Coloring Register Allocation, George-Appel Coalescing, SIMD Auto-Vectorization (NEON/AVX2), Tail-Call Optimization (TCO), and Closed-Form Symbolic Collapses.
- 🔍 **Linear-Time Pattern Matching (Virgex):** ReDoS-immune regular syntax executed via Thompson NFA multi-state simulation in deterministic $O(N \cdot M)$ time.
- 📦 **Rich Open-Source Standard Library (81 Modules):** Complete ecosystem covering cryptography (`sha256`, `aes`), networking (`http`, `socket`, `url`, `ip`), data structures (`hashmap`, `btree`, `lru`, `heap`, `deque`), concurrency (`atomic`, `channel`, `rwlock`), formats (`json`, `toml`, `yaml`, `csv`), and system I/O.
- 🛠️ **Unified Ergonomic Tooling:**
  - `vir`: Master CLI toolchain entrypoint.
  - `virc`: Native Self-Hosted AOT Compiler.
  - `viron`: Package Manager & Topological Sort Dependency DAG Resolver.
  - `vir-lsp`: Language Server Protocol daemon for VS Code and Antigravity IDE.

---

## Quick Start (One-Line Global Install)

Install the Vir toolchain on macOS or Linux with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/virgori/Vir-lang/main/install.sh | bash
```

Activate the environment:
```bash
source ~/.zshrc    # On macOS / Zsh
# or: source ~/.bashrc
```

---

## Language Tour & Examples

### 1. Hello World
```vir
func main:
    print_str("Hello from Vir!\n")
end.
```

### 2. Recursive Fibonacci with Tail-Call Optimization
```vir
func fib_tail(n, a, b):
    if n == 0 do out a end
    if n == 1 do out b end
    out fib_tail(n - 1, b, a + b)
end.

func main:
    let res = fib_tail(20, 0, 1)
    print_str("Fib(20) = ")
    print(res)
end.
```

### 3. Memory Arena & Dynamic Collections
```vir
func main:
    # 8-byte aligned bump arena allocator with O(1) reset
    let arena = alloc(4096)
    write_byte(arena, 0, 65) # 'A'
    write_byte(arena, 1, 66) # 'B'
    write_byte(arena, 2, 0)
    print_str(arena)
end.
```

---

## Toolchain Usage

### Master CLI (`vir`)

```bash
# Check version & toolchain info
vir --version
vir help

# Create a new project package
vir new my_project
cd my_project

# Compile and run
vir run

# Check syntax diagnostics
vir check main.vri
```

### Package Management (`viron`)

```bash
# Add package dependency with SemVer constraints
viron add std_http "^1.2.0"

# Inspect resolved dependency DAG (Topological Sort)
viron tree

# Run test suites
viron test
```

---

## Benchmarks & Performance

Benchmark results on Apple Silicon (M-series ARM64) comparing computation throughput and compilation speed:

| Metric / Benchmark | Vir (v2.0 Native) | C++ (Clang -O3) | Rust (rustc -O) | Go (gc) | Python (3.13) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Recursive Fib(40)** | **0.31s** | 0.32s | 0.31s | 0.48s | 14.82s |
| **Matrix DGEMM (GFLOPS)** | **124.5** | 126.2 | 121.8 | 48.2 | 2.1 |
| **Binary Startup Time** | **< 1ms** | 2ms | 2ms | 6ms | 35ms |
| **Binary Footprint** | **~67 KB** | ~120 KB | ~350 KB | ~2.1 MB | N/A |
| **Compilation Latency** | **Instant (Direct)** | 0.85s | 1.42s | 0.38s | N/A |

*Full comparative reports are available in [`docs/BENCHMARK_REPORT.md`](docs/BENCHMARK_REPORT.md).*

---

## Architecture & Algorithms Documentation

- 📖 [Language Specification v2.0](docs/vir_language_spec_v2.0_en.md)
- 🏛️ [System Architecture & Runtime](docs/ARCHITECTURE.md)
- 🧮 [Algorithms & Optimization Passes](docs/ALGORITHMS_AND_OPTIMIZATIONS.md)
- 📊 [Comprehensive Benchmark Report](docs/BENCHMARK_REPORT.md)
- 📁 [Binary Formats & Mach-O/ELF Layout](docs/FILE_FORMATS.md)
- 🔌 [Module & Include System](docs/MODULE_INCLUDE_SYSTEM.md)

---

## VS Code & Antigravity IDE Support

Install the extension from [`tools/vscode-vir/`](tools/vscode-vir/):
- Full syntax highlighting for `.vri`, `.sri`, `.sci`.
- Real-time diagnostics, completions, and hover documentation via `vir-lsp`.
- Smart Bar code folding and auto-closing block mechanics.

---

## License

The Vir Standard Library, documentation, ecosystem tools, benchmarks, and language specifications are licensed under the **Apache License, Version 2.0**.

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for full terms.
