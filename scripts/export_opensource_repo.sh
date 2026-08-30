#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════
# Vir Open-Source Release Repository Generator (Apache-2.0)
# ═════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")/.."

OUT_DIR="vir-community"
echo "=== Generating Vir Open-Source Release Repository in '${OUT_DIR}' ==="

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

# 1. Create LICENSE (Apache-2.0) and NOTICE
echo "1. Writing Apache-2.0 LICENSE & NOTICE..."
cat << 'EOF' > "${OUT_DIR}/LICENSE"
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to use, reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or exemplary damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS
EOF

cat << 'EOF' > "${OUT_DIR}/NOTICE"
Vir Programming Language & Toolchain
Copyright 2026 The Virgori Authors and Contributors.

This product includes software developed at
The Vir Programming Language Project (https://dev.virgori.com).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
EOF

# 2. Copy Open-Source Documentation
echo "2. Copying open-source specifications, architecture, algorithms, and benchmark docs..."
mkdir -p "${OUT_DIR}/docs"
cp docs/vir_language_spec_v2.0_en.md "${OUT_DIR}/docs/vir_language_spec_v2.0_en.md"
cp docs/ARCHITECTURE.md "${OUT_DIR}/docs/ARCHITECTURE.md"
cp docs/ALGORITHMS_AND_OPTIMIZATIONS.md "${OUT_DIR}/docs/ALGORITHMS_AND_OPTIMIZATIONS.md"
cp docs/VIR_CODEBASE_ARCHITECTURE.md "${OUT_DIR}/docs/VIR_CODEBASE_ARCHITECTURE.md" 2>/dev/null || true
cp docs/INTERVIR_ARCHITECTURE.md "${OUT_DIR}/docs/INTERVIR_ARCHITECTURE.md" 2>/dev/null || true
cp docs/FILE_FORMATS.md "${OUT_DIR}/docs/FILE_FORMATS.md" 2>/dev/null || true
cp docs/MODULE_INCLUDE_SYSTEM.md "${OUT_DIR}/docs/MODULE_INCLUDE_SYSTEM.md" 2>/dev/null || true
cp docs/BENCHMARK_REPORT.md "${OUT_DIR}/docs/BENCHMARK_REPORT.md"
cp docs/BENCHMARK_REPORT_v2.md "${OUT_DIR}/docs/BENCHMARK_REPORT_v2.md" 2>/dev/null || true
cp docs/BENCHMARK_REPORT_v3.md "${OUT_DIR}/docs/BENCHMARK_REPORT_v3.md" 2>/dev/null || true

# 3. Copy Standard Library (EXCLUDING compiler source)
echo "3. Copying standard library (81 open-source modules)..."
mkdir -p "${OUT_DIR}/stdlib/vir"
cp -R stdlib/vir/* "${OUT_DIR}/stdlib/vir/"
# CRITICAL: Strip internal compiler sources from public repo
rm -rf "${OUT_DIR}/stdlib/vir/compiler"
echo "   ✓ Removed compiler source from public stdlib (compiler is proprietary AOT binary distribution)"

# 4. Copy Apps and Ecosystem Tools
echo "4. Copying ecosystem CLI apps (vir, viron, vir-lsp)..."
mkdir -p "${OUT_DIR}/apps"
cp -R apps/vir "${OUT_DIR}/apps/" 2>/dev/null || true
cp -R apps/viron "${OUT_DIR}/apps/" 2>/dev/null || true
cp -R apps/vir-lsp "${OUT_DIR}/apps/" 2>/dev/null || true
cp -R apps/todo "${OUT_DIR}/apps/" 2>/dev/null || true

# 5. Copy Tools (VS Code extension & helper scripts)
echo "5. Copying VS Code / Antigravity IDE extension and tools..."
mkdir -p "${OUT_DIR}/tools"
cp -R tools/vscode-vir "${OUT_DIR}/tools/"
cp -R tools/vir-pkg "${OUT_DIR}/tools/" 2>/dev/null || true

# 6. Copy Benchmarks and Examples
echo "6. Copying benchmarks and examples..."
mkdir -p "${OUT_DIR}/benchmarks" "${OUT_DIR}/examples"
cp -R benchmarks/* "${OUT_DIR}/benchmarks/" 2>/dev/null || true
cp -R examples/* "${OUT_DIR}/examples/" 2>/dev/null || true
cp hello.vri "${OUT_DIR}/hello.vri"

# 7. Copy Pre-Compiled Standalone Native Binaries
echo "7. Copying standalone native binaries (bin/)..."
mkdir -p "${OUT_DIR}/bin"
cp bin/vir "${OUT_DIR}/bin/vir"
cp bin/virc "${OUT_DIR}/bin/virc"
cp bin/viron "${OUT_DIR}/bin/viron"
cp bin/vir-lsp "${OUT_DIR}/bin/vir-lsp"
chmod +x "${OUT_DIR}/bin/"*

# 8. Copy Build & Installer scripts
echo "8. Copying scripts and global installer..."
mkdir -p "${OUT_DIR}/scripts"
cp scripts/build_tools.sh "${OUT_DIR}/scripts/"
cp install.sh "${OUT_DIR}/install.sh"
chmod +x "${OUT_DIR}/install.sh" "${OUT_DIR}/scripts/"*.sh

# 9. Generate Master Open-Source README.md
echo "9. Generating official open-source README.md..."
cat << 'EOF' > "${OUT_DIR}/README.md"
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
curl -fsSL https://raw.githubusercontent.com/virgori/vir/main/install.sh | bash
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
EOF

echo ""
echo ">>> Vir Open-Source Community Repository generated successfully in '${OUT_DIR}/'! <<<"

