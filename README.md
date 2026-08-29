# The Vir Programming Language

[![Version](https://img.shields.io/badge/Release-v2.1.0-brightgreen.svg)](https://github.com/virgori/Vir-lang/releases/tag/v2.1.0)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Target](https://img.shields.io/badge/Targets-ARM64%20|%20x86__64%20|%20RISC--V%20|%20WASM-orange.svg)]()
[![Platform](https://img.shields.io/badge/OS-macOS%20|%20Linux%20|%20Windows-blueviolet.svg)]()
[![Stdlib](https://img.shields.io/badge/Stdlib-85%20Modules-success.svg)]()
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(No%20Libc,%20Linkerless%20AOT)-blue.svg)]()

**Vir (Virgori)** is a modern, high-performance systems programming language designed for bare-metal execution speed, predictable memory safety, and seamless multilingual developer ergonomics.

Vir compiles directly to standalone native machine code (**macOS Mach-O 64-bit**, **Linux ELF 64-bit**, and **WebAssembly WASM32**) with **zero external dependencies** — no `libc`, no `clang`/`gcc`, and no external linker (`ld`/`lld`).

---

## ⚡ Key Highlights (v2.1.0 Release)

- 🚀 **Official Self-Hosted Modular Soft Compiler (`virc`):**
  - **10 Semantic Analysis Passes:** Multi-pass symbol resolution, bidirectional type inference, CFA, and lexical borrow tracking.
  - **HIR → MIR (CFG/SSA) → LIR Pipeline:** True multi-tier compiler architecture with complete intermediate representations.
  - **26 Optimization Passes (-O0 .. -O3):** Tail-Call Optimization (TCO), Dead Code Elimination (DCE), Common Subexpression Elimination (CSE), Loop-Invariant Code Motion (LICM), Global Value Numbering (GVN), Sparse Conditional Constant Propagation (SCCP), Devirtualization, Function Inlining, SROA, Escape Arena Allocations, Partial Redundancy Elimination (PRE), SLP Vectorization, Jump Threading, Loop Tiling, Hot/Cold Splitting, and Zero-Cost ABI transforms.
  - **Chaitin-Briggs Graph Coloring RegAlloc (IRC):** Optimal register allocation with George-Appel Iterated Register Coalescing across all 31 hardware general-purpose registers.
- ⚡ **Zero-Libc & Linkerless Direct Kernel Syscalls:** Direct kernel supervisor calls (`svc #0x80` on macOS Darwin, `svc #0` on Linux) with built-in native Mach-O and ELF container builders.
- 🔍 **Linear-Time Pattern Matching (Virgex):** ReDoS-immune regular syntax executed via Thompson NFA multi-state simulation in deterministic $O(N \cdot M)$ time.
- 📦 **Standard Library (85 Modules):** Complete ecosystem covering cryptography (`sha256`, `aes`), networking (`http`, `socket`, `url`, `ip`), data structures (`hashmap`, `btree`, `lru`, `heap`, `deque`), concurrency (`atomic`, `channel`, `rwlock`), formats (`json`, `toml`, `yaml`, `csv`), and direct system I/O.
- 🛠️ **Unified Ergonomic Toolchain:**
  - `vir`: Master CLI toolchain entrypoint (`vir compile`, `vir run`, `vir new`, `vir build`, `vir test`, `vir check`, `vir lsp`).
  - `virc`: Official Self-Hosted Soft Modular AOT Compiler.
  - `viron`: Package Manager & Topological Sort Dependency DAG Resolver (SemVer 2.0).
  - `vir-lsp`: Language Server Protocol JSON-RPC 2.0 daemon for VS Code and Antigravity IDE.
  - `vir-todo`: Showcase standalone CLI task manager application in 100% pure Vir.

---

## 🚀 Quick Start (One-Line Global Install)

### Option 1: Automatic Installer (macOS & Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/virgori/Vir-lang/main/install.sh | bash
```

Activate the environment in your shell:
```bash
echo 'export PATH="$HOME/.vir/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
# Or for bash: echo 'export PATH="$HOME/.vir/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### Option 2: Homebrew Tap (macOS)

```bash
brew tap virgori/tap
brew install virgori/tap/vir
```

---

## 💻 Language Tour & Examples

### 1. Hello World
```vir
func main:
    print_str("Hello from Vir v2.1.0!\n")
end.
```

### 2. Recursive Fibonacci with Tail-Call Optimization (TCO)
```vir
func fib_tail(n, a, b):
    if n == 0 do out a end
    if n == 1 do out b end
    out fib_tail(n - 1, b, a + b)
end.

func main:
    let res = fib_tail(40, 0, 1)
    print_str("Fib(40) = ")
    print_int(res)
    print_newline()
end.
```

### 3. Native Buffer Allocation & Direct Syscalls
```vir
func main:
    # 8-byte aligned bump arena allocator with O(1) reset
    let arena = alloc(4096)
    write_byte(arena, 0, 86) # 'V'
    write_byte(arena, 1, 105) # 'i'
    write_byte(arena, 2, 114) # 'r'
    write_byte(arena, 3, 0)
    print_str(arena)
end.
```

---

## 🛠️ Toolchain Usage

### Master CLI (`vir`)

```bash
# Check installed toolchain suite
vir --version

# Create a new Vir package
vir new my_project
cd my_project

# Compile and execute application
vir run

# Static syntax & block analysis
vir check main.vri
```

### Soft Full Modular Compiler (`virc`)

```bash
# Display full compiler pipeline and optimization passes
virc --version

# Compile Vir source directly to standalone Mach-O / ELF binary
virc main.vri -o bin/my_app

# Compile with target and format flags
virc main.vri -o bin/my_app_linux --target=x86_64 --format=elf
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

### Standalone Showcase App (`vir-todo`)

```bash
vir-todo add "Build Native Web Framework in Vir"
vir-todo add "Benchmark Chaitin-Briggs IRC Allocator"
vir-todo list
vir-todo done 1
```

---

## 📊 Benchmarks & Performance

Benchmark results on Apple Silicon (M-series ARM64) comparing computation throughput, compilation latency, and binary size:

| Metric / Benchmark | Vir (v2.1.0 Native) | C++ (Clang -O3) | Rust (rustc -O) | Go (gc) | Python (3.13) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Recursive Fib(40)** | **0.31s** | 0.32s | 0.31s | 0.48s | 14.82s |
| **Matrix DGEMM (GFLOPS)** | **124.5** | 126.2 | 121.8 | 48.2 | 2.1 |
| **Binary Startup Time** | **< 1ms** | 2ms | 2ms | 6ms | 35ms |
| **Binary Footprint** | **~50 KB** | ~120 KB | ~350 KB | ~2.1 MB | N/A |
| **Compilation Latency** | **Instant (< 0.05s)** | 0.85s | 1.42s | 0.38s | N/A |

*Full comparative reports are available in [`docs/BENCHMARK_REPORT.md`](docs/BENCHMARK_REPORT.md).*

---

## 🏛️ Architecture & Documentation

- 📖 [Language Specification v2.0](docs/vir_language_spec_v2.0_en.md)
- 🏛️ [System Architecture & Runtime](docs/ARCHITECTURE.md)
- 🧮 [Algorithms & 26 Optimization Passes](docs/ALGORITHMS_AND_OPTIMIZATIONS.md)
- 📊 [Comprehensive Benchmark Report](docs/BENCHMARK_REPORT.md)
- 📁 [Binary Formats & Mach-O/ELF Layout](docs/FILE_FORMATS.md)
- 🔌 [Module & Include System](docs/MODULE_INCLUDE_SYSTEM.md)
- ⚙️ [InterVir Runtime Architecture](docs/INTERVIR_ARCHITECTURE.md)

---

## 🔌 VS Code & Antigravity IDE Support

Install the extension from [`tools/vscode-vir/`](tools/vscode-vir/):
- Full syntax highlighting for `.vri`, `.sri`, `.sci`.
- Real-time diagnostics, completions, and hover documentation via `vir-lsp`.
- Smart Bar code folding and auto-closing block mechanics.

---

## 📜 License

The Vir Standard Library, documentation, ecosystem tools, benchmarks, and language specifications are licensed under the **Apache License, Version 2.0**.

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for full terms.
