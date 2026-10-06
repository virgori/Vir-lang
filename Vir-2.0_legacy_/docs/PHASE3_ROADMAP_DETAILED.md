# PHASE 3 — Kế hoạch phát triển chi tiết
## Vir Programming Language

> **Chủ đề: "Make It Real"**
> Phase 2 xây hạ tầng (GPU, SIMD, cross-platform). Phase 3 biến mọi thứ thành **thực sự hoạt động**.

*Ngày lập: 11/03/2026*
*Dựa trên: Phase 2 hoàn thành 14/14 tasks, 858 tests passing*

---

## MỤC LỤC

- [Tổng quan](#tổng-quan)
- [Pillar E — Type System & Generics](#pillar-e--type-system--generics)
  - [E1. Hệ thống Generics](#e1-hệ-thống-generics)
  - [E2. Trait / Interface System](#e2-trait--interface-system)
  - [E3. Pattern Matching Pipeline (`:~` → Virgex)](#e3-pattern-matching-pipeline)
  - [E4. Error Handling (`try`/`?` propagation)](#e4-error-handling)
- [Pillar F — Tooling & Developer Experience](#pillar-f--tooling--developer-experience)
  - [F1. LSP Server](#f1-lsp-server)
  - [F2. Code Formatter (`vir fmt`)](#f2-code-formatter)
  - [F3. Package Manager (`vir pkg`)](#f3-package-manager)
  - [F4. Debugger / Source Map](#f4-debugger--source-map)
- [Pillar G — Stdlib Native Backing](#pillar-g--stdlib-native-backing)
  - [G1. Network Runtime (net/async/http)](#g1-network-runtime)
  - [G2. Thread Runtime (thread/tls)](#g2-thread-runtime)
  - [G3. FFI Runtime (ffi/ffi.vri → dlopen)](#g3-ffi-runtime)
  - [G4. GPU Pipeline Integration](#g4-gpu-pipeline-integration)
- [Pillar H — Bootstrap Compiler Evolution](#pillar-h--bootstrap-compiler-evolution)
  - [H1. Optimizer Pass (const fold, DCE, inlining)](#h1-optimizer-pass)
  - [H2. Memory Management (free / Arena reuse)](#h2-memory-management)
  - [H3. x86_64 Backend cho Bootstrap](#h3-x86_64-backend)
  - [H4. Virgex Self-Hosted Completion](#h4-virgex-self-hosted-completion)
- [Pillar I — Spec Alignment & Polish](#pillar-i--spec-alignment--polish)
  - [I1. Syntax Reconciliation (entity/record, eif/elif)](#i1-syntax-reconciliation)
  - [I2. Closures / Lambdas](#i2-closures--lambdas)
  - [I3. Safe Operators (`?.`, `?=`)](#i3-safe-operators)
  - [I4. Vietnamese Error Messages](#i4-vietnamese-error-messages)
- [Bảng tổng hợp](#bảng-tổng-hợp)
- [Thứ tự thực hiện](#thứ-tự-thực-hiện)

---

## TỔNG QUAN

### Trạng thái trước Phase 3

| Component | Trạng thái |
|-----------|------------|
| Q-IR VM (60+ opcodes, SSA) | ✅ Hoạt động |
| Self-hosting ARM64 compiler (137KB) | ✅ Fixed-point |
| Self-patching JIT (HMAC-SHA256) | ✅ Hoạt động |
| Virgex pattern engine (dual-engine) | ✅ 113/113 tests |
| GPU backends (CUDA + Metal) | ✅ C code + templates |
| SIMD dispatch (NEON/AVX2/AVX-512/SVE) | ✅ Hoạt động |
| Green threads (M:N scheduler) | ✅ Hoạt động |
| Stdlib (52 modules) | ⚠️ Phase A/B hoạt động, Phase C/D là API shells |
| Generics (`Vec<T>`, `Map<K,V>`) | ❌ Chưa có trong compiler |
| LSP Server | ❌ Stub 204 LOC |
| Package Manager | ❌ `Err("not implemented")` |
| Memory management | ❌ Chỉ `alloc`, không `free` |

### Mục tiêu Phase 3

1. **Type system** hoàn chỉnh: generics, traits, error handling thực sự
2. **Tooling** chuyên nghiệp: LSP, formatter, package manager
3. **Stdlib chạy thật**: network, thread, FFI có native backing trong `core/src/`
4. **Bootstrap compiler** mạnh hơn: optimizer, memory management, multi-arch

---

## PILLAR E — TYPE SYSTEM & GENERICS

### E1. Hệ thống Generics

**Vấn đề**: Stdlib sử dụng `Vec<T>`, `Map<K,V>`, `Result<T,E>` khắp nơi, nhưng compiler không hiểu generics.

**Mục tiêu**: Monomorphization-based generics (giống Rust/C++, không giống Java type erasure).

#### Thiết kế

```vir
// Khai báo entity generic
entity Vec<T> {
    data: ptr<T>,
    len: u64,
    cap: u64,
}

// Khai báo hàm generic
hàm vec_push<T>(v: &Vec<T>, item: T) {
    // ...
}

// Sử dụng (compiler tự suy luận T)
biến xs = vec_new<i64>()
vec_push(xs, 42)  // T = i64, suy luận từ context
```

#### Chiến lược monomorphization

```
Source                          Q-IR output
──────                          ───────────
vec_push<i64>(xs, 42)    →     call @vec_push__i64
vec_push<f32>(ys, 3.14)  →     call @vec_push__f32
```

Mỗi tổ hợp `<T>` cụ thể sinh ra hàm riêng. Tránh runtime overhead.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| E1.1 | `src/frontend/parser/` | Parse `<T>` trong entity và func declarations | ~200 |
| E1.2 | `src/ir/instructions/q_ir.py` | Thêm generic param vào `QFunction`, `QModule` | ~50 |
| E1.3 | `src/ir/` (mới: `monomorph.py`) | Monomorphization pass: duyệt call graph, instantiate mỗi `<T>` cụ thể | ~400 |
| E1.4 | `core/src/parser.c` | Parse generics trong C parser (cho bootstrap) | ~150 |
| E1.5 | Tests | Test instantiation, recursive generics, inference | ~200 |

**Tổng: ~1,000 LOC**

**Tiêu chí hoàn thành**: `Vec<i64>`, `Vec<f32>`, `Map<str, i64>`, `Result<i64, str>` đều compile và chạy đúng.

---

### E2. Trait / Interface System

**Vấn đề**: Stdlib cần polymorphism — `Iterator`, `Display`, `Add` — nhưng chưa có cơ chế trait.

**Mục tiêu**: Static dispatch traits (vtable-free khi có thể, vtable cho `dyn Trait`).

#### Thiết kế

```vir
trait Display {
    hàm to_string(self) → str
}

trait Iterator<T> {
    hàm next(self) → Option<T>
}

// Implement cho entity cụ thể
impl Display cho Vec<i64> {
    hàm to_string(self) → str {
        // ...
    }
}

// Hàm nhận trait bound
hàm print_item<T: Display>(item: T) {
    println(item.to_string())
}
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| E2.1 | `src/frontend/parser/` | Parse `trait`, `impl ... cho ...`, trait bounds `<T: Trait>` | ~250 |
| E2.2 | AST + IR | `AST_TRAIT_DEF`, `AST_IMPL_BLOCK` node types | ~100 |
| E2.3 | `src/ir/` (mới: `trait_resolve.py`) | Trait resolution: tìm impl phù hợp tại compile time | ~300 |
| E2.4 | `src/ir/monomorph.py` | Mở rộng monomorphization cho trait bounds | ~150 |
| E2.5 | Tests | Trait impl, trait bounds, orphan rule check | ~200 |

**Tổng: ~1,000 LOC**

**Tiêu chí**: `impl Display cho Vec<i64>` hoạt động, trait bounds trong generics, compiler báo lỗi khi thiếu impl.

---

### E3. Pattern Matching Pipeline (`:~` → Virgex)

**Vấn đề**: Token `:~` có trong lexer, parser.c có `parse_case_stmt()`, ir_lower.c handle `AST_PATTERN_MATCH` — nhưng pipeline end-to-end chưa nối.

**Mục tiêu**: Pattern matching expressions sử dụng Virgex VPS.

#### Thiết kế

```vir
biến input = "0912345678"

khớp input :~
    "| 09 @0!8 |"   → println("Viettel")
    "| 03 @0!8 |"   → println("Mobifone")
    _                → println("Không xác định")
hết

// Biên dịch thành:
//   1. Mỗi nhánh: virgex.compile(pattern)
//   2. Test input against patterns tuần tự
//   3. Jump vào nhánh match đầu tiên
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| E3.1 | `core/src/parser.c` | Hoàn thiện `parse_case_stmt()` cho `:~` với VPS patterns | ~100 |
| E3.2 | `core/src/ir_lower.c` | Lower `AST_PATTERN_MATCH` → chuỗi Q_CALL virgex_match + Q_JUMP_IF | ~150 |
| E3.3 | `src/frontend/parser/` | Python parser: `:~` → match expression node | ~100 |
| E3.4 | `src/ir/` | Python IR builder: emit virgex match calls | ~100 |
| E3.5 | Runtime glue | Virgex <=> Q-IR interop (load pattern, match, branch) | ~100 |
| E3.6 | Tests | Phone number matching, format validation, exhaustive case | ~150 |

**Tổng: ~700 LOC**

**Tiêu chí**: `khớp x :~ pattern → action hết` compiles và chạy, Virgex patterns trong match arms.

---

### E4. Error Handling (`try` / `?` propagation)

**Vấn đề**: Stdlib dùng `Result<T,E>` nhưng compiler không hỗ trợ `try` expression hay `?` operator.

**Mục tiêu**: Ergonomic error handling — `?` propagation + `try`/`error` blocks.

#### Thiết kế

```vir
// Option 1: Rust-style ? propagation
hàm read_config() → Result<Config, Error> {
    biến content = fs_read("config.json")?   // ? = unwrap hoặc return Err
    biến config = json_parse(content)?
    Ok(config)
}

// Option 2: Spec-compatible try/error block
out action
    try
        biến f = file_open("data.txt")
        biến data = file_read(f)
    fallback
        println("Lỗi đọc file")
    error FileNotFound
        println("Không tìm thấy file")
end
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| E4.1 | Parser | Parse `?` postfix operator trên expression | ~80 |
| E4.2 | Parser | Parse `try/fallback/error` blocks (theo spec v1.2) | ~120 |
| E4.3 | IR Lower | `?` → extract Ok value hoặc early return Err | ~100 |
| E4.4 | IR Lower | `try/error` → Q_JUMP_IF chain với error type matching | ~150 |
| E4.5 | Tests | Propagation chains, nested try, custom error types | ~150 |

**Tổng: ~600 LOC**

---

## PILLAR F — TOOLING & DEVELOPER EXPERIENCE

### F1. LSP Server

**Vấn đề**: VS Code extension "Virgori Core" v3.1.2 có LSP client framework, nhưng không có server. Hiện tại chỉ có syntax highlighting + basic completion.

**Mục tiêu**: LSP server viết bằng Python, cung cấp real-time diagnostics, go-to-definition, completion.

#### Tính năng

| Feature | LSP Method | Mô tả |
|---------|-----------|-------|
| Diagnostics | `textDocument/publishDiagnostics` | Parse errors, type errors, undefined variables |
| Go-to-definition | `textDocument/definition` | Jump đến function/entity definition |
| Completion | `textDocument/completion` | Keyword + symbol completion từ scope hiện tại |
| Hover | `textDocument/hover` | Hiển thị type signature + doc comment |
| Document symbols | `textDocument/documentSymbol` | Outline: functions, entities, imports |
| Rename | `textDocument/rename` | Rename symbol across file |

#### Architecture

```
VS Code Extension (TypeScript)
       │ JSON-RPC / stdio
       ▼
vir-lsp-server (Python)
       ├── protocol.py     # LSP message parsing/serialization
       ├── server.py        # Main loop, dispatch
       ├── analysis.py      # Parse .vri → AST, extract symbols
       ├── diagnostics.py   # Real-time error detection
       ├── completion.py    # Context-aware completion
       └── workspace.py     # Multi-file project indexing
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| F1.1 | `tools/vir-lsp/protocol.py` | LSP JSON-RPC protocol handler (initialize, shutdown, textDocument/*) | ~300 |
| F1.2 | `tools/vir-lsp/server.py` | Main server loop, stdio transport, request dispatch | ~200 |
| F1.3 | `tools/vir-lsp/analysis.py` | Reuse `src/frontend/` parser → symbol table extraction | ~250 |
| F1.4 | `tools/vir-lsp/diagnostics.py` | Parse + type error collection → diagnostic messages | ~200 |
| F1.5 | `tools/vir-lsp/completion.py` | Keyword + scope-aware symbol completion | ~150 |
| F1.6 | `tools/vscode-vir/` update | Point extension to vir-lsp-server, add configuration | ~50 |
| F1.7 | Tests | Protocol compliance, diagnostic accuracy | ~200 |

**Tổng: ~1,350 LOC**

**Tiêu chí**: Mở file `.vri` trong VS Code → thấy lỗi syntax real-time, Ctrl+Click jump to definition, autocomplete keywords + symbols.

---

### F2. Code Formatter (`vir fmt`)

**Vấn đề**: Không có cách format code `.vri` tự động. Mỗi file viết style khác nhau.

**Mục tiêu**: `vir fmt file.vri` — deterministic formatting, indent 4 spaces, consistent style.

#### Rules

| Rule | Mô tả |
|------|-------|
| Indent | 4 spaces, +1 level per block (`hàm`, `nếu`, `lặp`, `entity`, `impl`) |
| Blank lines | 1 blank line giữa top-level declarations, 0 trong block |
| Trailing whitespace | Strip |
| Line length | Soft limit 100, hard limit 120 |
| Keyword spacing | Luôn 1 space sau keyword (`nếu `, `biến `, `trả_về `) |
| Operator spacing | `a + b`, `a == b`, `a → b` |
| Entity fields | Aligned colons |

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| F2.1 | `tools/vir-fmt/formatter.py` | AST → formatted source (pretty printer) | ~400 |
| F2.2 | `tools/vir-fmt/rules.py` | Configurable formatting rules | ~100 |
| F2.3 | `tools/vir-fmt/cli.py` | CLI: `vir fmt [--check] [files...]` | ~80 |
| F2.4 | Tests | Idempotency, edge cases, multilingual keywords | ~200 |

**Tổng: ~780 LOC**

---

### F3. Package Manager (`vir pkg`)

**Vấn đề**: `stdlib/vir/pkg/pkg.vri` define `SemVer` + `Manifest` nhưng `pkg_install()` return `Err("not implemented")`.

**Mục tiêu**: Local-first package manager — file-based registry, lock files, dependency resolution.

#### Thiết kế

```
vir.toml (project manifest)
├── [package]
│   ├── name = "my-project"
│   ├── version = "0.1.0"
│   └── vir = ">=0.3.0"
├── [dependencies]
│   ├── virgex = "1.0"
│   └── json-vir = { path = "../json-vir" }
└── [dev-dependencies]
    └── test-kit = "0.2"

vir.lock (generated, deterministic)
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| F3.1 | `tools/vir-pkg/manifest.py` | Parse vir.toml (TOML format), validate | ~200 |
| F3.2 | `tools/vir-pkg/resolver.py` | Dependency resolution (SAT-based, topological sort) | ~300 |
| F3.3 | `tools/vir-pkg/lockfile.py` | Generate/read vir.lock | ~150 |
| F3.4 | `tools/vir-pkg/registry.py` | Local file registry + git-based remote | ~200 |
| F3.5 | `tools/vir-pkg/cli.py` | CLI: `vir pkg init/add/install/update/publish` | ~150 |
| F3.6 | Tests | Resolution, circular dep detection, lock determinism | ~200 |

**Tổng: ~1,200 LOC**

---

### F4. Debugger / Source Map

**Vấn đề**: Không có debugger. Khi crash, chỉ thấy instruction pointer — không biết dòng source nào.

**Mục tiêu**: Source map linking Q-IR instructions → source lines. Stack trace có tên file + dòng.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| F4.1 | `src/ir/instructions/q_ir.py` | Thêm `source_loc: (file, line, col)` vào `QInstruction` | ~30 |
| F4.2 | `src/ir/` (mới: `source_map.py`) | Compact binary source map: instruction_offset → (file_id, line) | ~200 |
| F4.3 | `src/runtime/` | Stack trace formatter: khi crash → print source locations | ~150 |
| F4.4 | `core/src/q_ir.c` | Lưu line info trong C Q-IR | ~50 |
| F4.5 | Tests | Crash → correct source location, nested calls | ~100 |

**Tổng: ~530 LOC**

---

## PILLAR G — STDLIB NATIVE BACKING

### G1. Network Runtime (net / async / http)

**Vấn đề**: `net.vri` khai báo 17 extern funcs (TCP/UDP/DNS). `async.vri` khai báo 4 extern funcs (epoll/kqueue). Tất cả chưa có C implementation.

**Mục tiêu**: Implement native backing trong `core/src/` — async I/O loop trên kqueue (macOS) / epoll (Linux).

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| G1.1 | `core/src/vir_net.c` | TCP/UDP socket ops: create, bind, listen, accept, connect, send, recv, close | ~500 |
| G1.2 | `core/src/vir_net.c` | DNS resolver: `getaddrinfo` wrapper | ~100 |
| G1.3 | `core/src/vir_async.c` | Event loop: kqueue (macOS) / epoll (Linux), timer, signal handling | ~600 |
| G1.4 | `core/include/vir_net.h` | Public API headers | ~80 |
| G1.5 | `core/include/vir_async.h` | Public API headers | ~60 |
| G1.6 | Tests | TCP echo server, HTTP GET, async timer | ~300 |

**Tổng: ~1,640 LOC**

**Tiêu chí**: `net.vri` → compile → chạy được TCP echo server. `http.vri` → compile → fetch URL thật.

---

### G2. Thread Runtime (thread / tls)

**Vấn đề**: `thread.vri` khai báo 33 extern funcs. `tls.vri` khai báo 15 extern funcs. Chưa có native backing.

**Mục tiêu**: pthread wrapper trong `core/src/`.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| G2.1 | `core/src/vir_thread.c` | pthread_create/join/detach, mutex, rwlock, condvar, barrier | ~400 |
| G2.2 | `core/src/vir_thread.c` | Thread pool: work-stealing queue, fixed thread count | ~300 |
| G2.3 | `core/include/vir_thread.h` | Public API headers | ~80 |
| G2.4 | Tests | Spawn + join, mutex contention, thread pool throughput | ~200 |

**Tổng: ~980 LOC**

---

### G3. FFI Runtime (ffi/ffi.vri → dlopen)

**Vấn đề**: `ffi.vri` define 6 extern funcs cho dlopen/dlsym/dlclose. Cần C wrapper.

**Mục tiêu**: Dynamic library loading từ Vir code.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| G3.1 | `core/src/vir_ffi.c` | dlopen/dlsym/dlclose/dlerror wrapper, type conversion | ~250 |
| G3.2 | `core/src/vir_ffi.c` | Call convention bridge: Vir stack → C ABI | ~200 |
| G3.3 | `core/include/vir_ffi.h` | Public API | ~40 |
| G3.4 | Tests | Load libm → call sin(), load custom .dylib | ~150 |

**Tổng: ~640 LOC**

---

### G4. GPU Pipeline Integration

**Vấn đề**: `gpu_cuda.c`, `ptx_gen.c`, `gpu_metal.c` tồn tại (2,200 LOC) + `codegen_gpu.py` + 10 kernel templates. Nhưng chưa nối vào compilation pipeline.

**Mục tiêu**: Viết code Vir → compile → kernel chạy trên GPU thật.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| G4.1 | `src/backend/codegen/codegen.py` | Thêm `TargetArch.CUDA` + `TargetArch.METAL`, dispatch tới `codegen_gpu.py` | ~100 |
| G4.2 | `src/runtime/` | GPU runtime manager: init → compile kernel → dispatch → sync → cleanup | ~300 |
| G4.3 | `core/src/gpu_cuda.c` | Integration tests qua Metal (macOS) hoặc CUDA stub | ~100 |
| G4.4 | `stdlib/vir/gpu/gpu.vri` | Update stdlib GPU module với API matching `core/include/gpu_*.h` | ~150 |
| G4.5 | Tests | VADD trên GPU thật (Metal), verify correctness | ~200 |

**Tổng: ~850 LOC**

---

## PILLAR H — BOOTSTRAP COMPILER EVOLUTION

### H1. Optimizer Pass (const fold, DCE, inlining)

**Vấn đề**: Bootstrap compiler (compiler.vri, 3,254 LOC) không có optimizer. Code-gen thẳng AST → ARM64.

**Mục tiêu**: 3 optimization passes cơ bản, viết bằng Vir.

#### Passes

| Pass | Mô tả | Tác động |
|------|-------|---------|
| **Constant folding** | `3 + 4` → `7` tại compile time | Giảm instruction count |
| **Dead code elimination** | Remove unreachable blocks, unused assignments | Giảm binary size |
| **Function inlining** | Inline small functions (≤5 instructions) | Giảm call overhead |

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| H1.1 | `core/bootstrap/opt_fold.vri` | Constant folding pass (walk AST, evaluate ops) | ~200 |
| H1.2 | `core/bootstrap/opt_dce.vri` | Dead code elimination (mark-sweep on IR) | ~200 |
| H1.3 | `core/bootstrap/opt_inline.vri` | Function inlining (threshold-based) | ~250 |
| H1.4 | `core/bootstrap/compiler.vri` | Wire optimizer vào pipeline: parse → optimize → codegen | ~50 |
| H1.5 | Tests | Verify fixed-point vẫn giữ sau optimization | ~100 |

**Tổng: ~800 LOC**

**Tiêu chí**: Stage 2 binary nhỏ hơn 5-10% sau optimization. Fixed-point vẫn giữ.

---

### H2. Memory Management (free / Arena reuse)

**Vấn đề**: Bootstrap compiler `mem_alloc` dùng mmap nhưng **không bao giờ free**. Compile lớn → leak hết memory.

**Mục tiêu**: Arena allocator với reset() — memory tái sử dụng giữa các compilation phases.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| H2.1 | `core/bootstrap/stdlib/arena.vri` | Mở rộng arena: `arena_reset()`, region markers, nested arenas | ~150 |
| H2.2 | `core/bootstrap/compiler.vri` | Dùng separate arenas cho lexer/parser/codegen, reset giữa phases | ~80 |
| H2.3 | Tests | Compile large file (1000+ lines) → verify memory bounded | ~50 |

**Tổng: ~280 LOC**

---

### H3. x86_64 Backend cho Bootstrap

**Vấn đề**: Bootstrap compiler chỉ target ARM64. Không thể self-host trên x86_64 Linux/macOS.

**Mục tiêu**: Thêm x86_64 codegen vào compiler.vri.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| H3.1 | `core/bootstrap/codegen_x86.vri` | x86_64 instruction encoding (REX prefix, ModR/M, SIB) | ~500 |
| H3.2 | `core/bootstrap/codegen_x86.vri` | ELF64 emitter (thay vì Mach-O) | ~300 |
| H3.3 | `core/bootstrap/compiler.vri` | `-arch x86_64` flag, dispatch to correct backend | ~50 |
| H3.4 | Tests | Cross-compile trên ARM64, verify trên x86_64 (CI) | ~100 |

**Tổng: ~950 LOC**

---

### H4. Virgex Self-Hosted Completion

**Vấn đề**: `virgex.vri` (708 LOC) có lexer + atom table nhưng thiếu compiler (AST→regex) và matcher.

**Mục tiêu**: Virgex tự compile VPS patterns bằng chính ngôn ngữ Vir — hoàn chỉnh pipeline.

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| H4.1 | `virgex/stdlib/virgex.vri` | Parser: tokens → AST tree (recursive descent) | ~200 |
| H4.2 | `virgex/stdlib/virgex.vri` | Compiler: AST → regex string | ~150 |
| H4.3 | `virgex/stdlib/virgex.vri` | NFA builder: Thompson construction in Vir | ~250 |
| H4.4 | `virgex/stdlib/virgex.vri` | Matcher: NFA simulation, match/search/findall | ~200 |
| H4.5 | Tests `.vri` | Self-test: virgex patterns test cases in Vir | ~100 |

**Tổng: ~900 LOC**

**Tiêu chí**: `virgex.vri` tự biên dịch pattern VPS → match text, không cần Python reference impl.

---

## PILLAR I — SPEC ALIGNMENT & POLISH

### I1. Syntax Reconciliation

**Vấn đề**: Spec v1.2 nói `entity` nhưng bootstrap dùng `record`. Spec nói `eif` nhưng stdlib dùng `elif`. Spec nói `out` nhưng code dùng `return/trả_về`.

**Mục tiêu**: Một cú pháp thống nhất — spec, compiler, stdlib đều khớp.

#### Quyết định đề xuất

| Spec v1.2 | Bootstrap | Stdlib | **Quyết định** |
|-----------|-----------|--------|----------------|
| `entity` | `record` | `entity` | → **`entity`** (spec wins, update bootstrap) |
| `eif` | `elif` | cả hai | → **`eif`** (spec wins, thêm `elif` alias) |
| `when...loop` | `while` | `while` | → **`lặp khi`** (Viet) / **`while`** (En), spec update |
| `out` | `return` | `trả_về` | → **`trả_về`** (Viet) / **`return`** (En), spec update |
| `skip` | `continue` | `tiếp_tục` | → **`tiếp_tục`** / **`skip`**, spec keeps |

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| I1.1 | `core/bootstrap/compiler.vri` | `record` → accept `entity` (alias) | ~30 |
| I1.2 | `src/sublib/vi.py` | Ensure `entity`, `eif`, `trả_về`, `tiếp_tục` all map correctly | ~20 |
| I1.3 | `docs/vir_language_spec_v1.2.md` | Update spec cho reconciled syntax | ~50 |
| I1.4 | Stdlib `.vri` files | Search-replace inconsistencies | ~100 |

**Tổng: ~200 LOC**

---

### I2. Closures / Lambdas

**Vấn đề**: Không có closures. Stdlib iter/func modules cần HOF (higher-order functions).

**Mục tiêu**: Anonymous functions với captured environment.

#### Thiết kế

```vir
// Lambda syntax
biến double = |x: i64| → x * 2

// Closure — captures biến ngoài
biến offset = 10
biến add_offset = |x: i64| → x + offset

// Sử dụng trong iter
xs.map(|x| → x * 2).filter(|x| → x > 5)
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| I2.1 | Parser | Parse `\|params\| → body` lambda syntax | ~100 |
| I2.2 | IR Lower | Capture analysis: xác định biến ngoài cần capture | ~150 |
| I2.3 | IR Lower | Generate closure struct (function pointer + captured env) | ~150 |
| I2.4 | Codegen | Closure calling convention | ~100 |
| I2.5 | Tests | Capture by value/ref, nested closures | ~100 |

**Tổng: ~600 LOC**

---

### I3. Safe Operators (`?.`, `?=`)

**Vấn đề**: Spec v1.2 define safe operators nhưng chưa implement.

```vir
// ?. — optional chaining (như Swift/Kotlin)
biến name = user?.profile?.name    // None nếu bất kỳ link nào null

// ?= — default assignment
biến x ?= 42    // giữ giá trị cũ nếu đã có, gán 42 nếu None
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| I3.1 | Parser | Parse `?.` và `?=` | ~60 |
| I3.2 | IR Lower | `?.` → Q_JUMP_IF_NOT (check None) + Q_LOAD field | ~80 |
| I3.3 | IR Lower | `?=` → Q_CMP_EQ None + conditional Q_STORE | ~50 |
| I3.4 | Tests | Chaining, nested optional, default assignment | ~80 |

**Tổng: ~270 LOC**

---

### I4. Vietnamese Error Messages

**Vấn đề**: Compiler errors bằng tiếng Anh. Vir là ngôn ngữ multilingual — errors cũng nên multilingual.

**Mục tiêu**: Error messages bằng ngôn ngữ đầu vào.

```
// Nếu code viết tiếng Việt:
Lỗi [E0001] tại hàm_test.vri:15:8
  │ biến x = 10 / 0
  │              ^^^
  └── Chia cho không (division by zero)

// Nếu code viết tiếng Anh:
Error [E0001] at func_test.vri:15:8
  │ var x = 10 / 0
  │            ^^^
  └── Division by zero
```

#### Implementation steps

| Step | File | Mô tả | LOC |
|------|------|-------|-----|
| I4.1 | `src/` (mới: `errors/messages.py`) | Error message catalog: EN + VI + ZH + JA + KO | ~300 |
| I4.2 | `src/frontend/`, `src/ir/` | Replace hardcoded strings → catalog lookup | ~100 |
| I4.3 | `core/src/` | C error messages: detect locale → select message | ~100 |
| I4.4 | Tests | Verify messages in each language | ~100 |

**Tổng: ~600 LOC**

---

## BẢNG TỔNG HỢP

| # | Task | Pillar | Domain | LOC ước tính | Ưu tiên |
|---|------|--------|--------|-------------|---------|
| E1 | Generics (monomorphization) | Type System | Compiler | ~1,000 | 🔥 Cao |
| E2 | Trait / Interface System | Type System | Compiler | ~1,000 | 🔥 Cao |
| E3 | Pattern Matching (`:~` → Virgex) | Type System | Language | ~700 | 🔥 Cao |
| E4 | Error Handling (`try`/`?`) | Type System | Language | ~600 | ⚡ Quan trọng |
| F1 | LSP Server | Tooling | DX | ~1,350 | 🔥 Cao |
| F2 | Code Formatter (`vir fmt`) | Tooling | DX | ~780 | ⚡ Quan trọng |
| F3 | Package Manager (`vir pkg`) | Tooling | Ecosystem | ~1,200 | ⚡ Quan trọng |
| F4 | Debugger / Source Map | Tooling | DX | ~530 | 🧊 Trung bình |
| G1 | Network Runtime (net/async/http) | Native Backing | Stdlib | ~1,640 | 🔥 Cao |
| G2 | Thread Runtime (thread/tls) | Native Backing | Stdlib | ~980 | ⚡ Quan trọng |
| G3 | FFI Runtime (dlopen) | Native Backing | Stdlib | ~640 | ⚡ Quan trọng |
| G4 | GPU Pipeline Integration | Native Backing | GPU | ~850 | 🧊 Trung bình |
| H1 | Bootstrap Optimizer | Bootstrap | Compiler | ~800 | ⚡ Quan trọng |
| H2 | Memory Management (Arena) | Bootstrap | Compiler | ~280 | ⚡ Quan trọng |
| H3 | x86_64 Bootstrap Backend | Bootstrap | Cross-platform | ~950 | 🧊 Trung bình |
| H4 | Virgex Self-Hosted Completion | Bootstrap | Virgex | ~900 | ⚡ Quan trọng |
| I1 | Syntax Reconciliation | Polish | Spec | ~200 | 🔥 Cao |
| I2 | Closures / Lambdas | Polish | Language | ~600 | ⚡ Quan trọng |
| I3 | Safe Operators (`?.`, `?=`) | Polish | Language | ~270 | 🧊 Trung bình |
| I4 | Vietnamese Error Messages | Polish | DX | ~600 | 🧊 Trung bình |
| | | | **TỔNG** | | **~14,870 LOC** |

---

## THỨ TỰ THỰC HIỆN ĐỀ XUẤT

```
Sprint 1 — Foundation (Unlock generics → stdlib thực sự dùng được):
  I1 → E1 → E2 → E4
  (Reconcile syntax → Generics → Traits → Error handling)
  → Tiêu chí: Vec<i64>, Result<T,E>, impl Display cho Vec hoạt động

Sprint 2 — Language Completeness (Pattern match + closures):
  E3 → I2 → I3
  (Pattern matching with Virgex → Closures → Safe operators)
  → Tiêu chí: khớp x :~ pattern, |x| → x*2, user?.name hoạt động

Sprint 3 — Make Stdlib Real (Native backing):
  G3 → G2 → G1 → G4
  (FFI → Threads → Network → GPU)
  → Tiêu chí: TCP echo server chạy thật, GPU vadd trên Metal

Sprint 4 — Tooling (Developer experience):
  F1 → F2 → F4 → F3
  (LSP → Formatter → Source map → Package manager)
  → Tiêu chí: VS Code real-time diagnostics, vir fmt, stack traces

Sprint 5 — Bootstrap Evolution (Self-hosting mạnh hơn):
  H2 → H1 → H4 → H3
  (Memory → Optimizer → Virgex self-host → x86_64)
  → Tiêu chí: Bootstrap compiler optimized, Virgex.vri tự match, cross-arch

Sprint 6 — Polish:
  I4
  (Vietnamese error messages)
  → Tiêu chí: Lỗi compiler hiển thị bằng tiếng Việt khi code viết tiếng Việt
```

### Dependency Graph

```
I1 (syntax) ──────┐
                   ▼
          E1 (generics) ──→ E2 (traits)
                   │              │
                   ▼              ▼
          E4 (error handling)    G1/G2/G3 (stdlib native)
                   │
                   ▼
          E3 (pattern match) ←── H4 (virgex self-host)
                   │
          I2 (closures) ──→ I3 (safe ops)

          F1 (LSP) ──→ F2 (formatter) ──→ F4 (debugger)
                                           │
                                           ▼
                                    F3 (package manager)

          H2 (memory) ──→ H1 (optimizer) ──→ H3 (x86_64)
```

---

*Tài liệu kỹ thuật Phase 3 — Vir Codebase, 11/03/2026*
*Tổng: 20 tasks · 5 pillars · ~14,870 LOC dự kiến*
