# Vir – VIRGORI-CORE Engine

> **Natural Language Programming • Abstract Q-IR Core • Binary Self-Patching • Virgex Pattern Engine**

🌐 **Language / Ngôn ngữ / 语言:**
[English](README_EN.md) | [Tiếng Việt](README_VI.md) | [简体中文](README_ZH_CN.md) | [繁體中文](README_ZH_TW.md)

| Metric | Giá trị |
|--------|---------|
| C/ASM native core | ~9,900 LOC · 27 nguồn + 27 header |
| Python compiler pipeline | 26,840 LOC · 152 modules |
| Standard Library | **233 modules** · 72,724 LOC `.vri` · 71 categories |
| Virgex engine | ~1,400 LOC (Python) + 708 LOC (.vri) |
| GPU backends | CUDA PTX + Apple Metal/MSL · 10 kernel templates |
| Tests | **700/700 pass ✅** |
| Self-hosting | 137 KB ARM64 Mach-O · fixed-point Stage 2 ≡ Stage 3 |
| Domains | Server · IoT · AI · Kernel/OS · Network · Crypto |

---

## Overview / Tổng quan

**Vir** là một ngôn ngữ lập trình thử nghiệm cho phép viết code bằng **ngôn ngữ tự nhiên** (Tiếng Việt, 中文, 日本語, 한국어, English), biên dịch xuống một tầng máy trừu tượng (Q-IR), và runtime có khả năng **tự vá mã nhị phân** (binary self-patching) dựa trên trạng thái CPU thực tế.

### Kiến trúc lib / sublib

Vir tách biệt **lib** (chuẩn Tiếng Anh – single source of truth) và **sublib** (lớp ánh xạ ngôn ngữ bản địa):

```
┌─────────────────────────────────────────────────────────┐
│  lib/keywords.py   (English Standard)                   │
│  TokenKind enum: FUNC_DEF, IF, ELSE, OP_ADD, PRINT, …  │
│  KeywordRegistry: by_kind(), by_english(), categories() │
└───────────────────────────┬─────────────────────────────┘
                            │ TokenKind
        ┌───────────┬───────┼───────┬───────────┐
        ↓           ↓       ↓       ↓           ↓
  ┌──────────┐ ┌─────────┐ ┌────┐ ┌──────┐ ┌─────────┐
  │ sublib/  │ │ sublib/ │ │sub │ │ sub  │ │ sublib/ │
  │ vi.py    │ │ zh.py   │ │lib/│ │ lib/ │ │ en.py   │
  │ 🇻🇳       │ │ 🇨🇳      │ │ja  │ │ ko   │ │ 🇬🇧      │
  └──────────┘ └─────────┘ └────┘ └──────┘ └─────────┘
  "nếu"→IF    "如果"→IF  "もし"→IF "만약"→IF  "if"→IF
```

Mỗi sublib adapter ánh xạ các cụm từ bản địa → `TokenKind` chuẩn, cho phép Tokenizer + Parser hoạt động thống nhất bất kể ngôn ngữ đầu vào.

### Kiến trúc 4 tầng

```
┌─────────────────────────────────────────────────────┐
│  Tầng 1: Multilingual Frontend                      │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ N-Gram       │→ │ Parser   │→ │ AST           │  │
│  │ Tokenizer    │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│          ↑                                           │
│    SubLibAdapter (vi / zh / ja / ko / en / …)        │
├─────────────────────────────────────────────────────┤
│  Tầng 2: Virtual Machine (Q-IR)                     │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ IR Builder   │→ │Optimizer │→ │ QModule       │  │
│  │              │  │ (fold,   │  │ (SSA form)    │  │
│  │              │  │  DCE)    │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Virtual Registers: R₀, R₁, …, Rₙ (unlimited)      │
├─────────────────────────────────────────────────────┤
│  Tầng 3: Self-Patching Backend                      │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ CodeGen      │→ │ Binary   │→ │ Jump Table    │  │
│  │ (x86_64 /   │  │ Patcher  │  │ Indirection   │  │
│  │  arm64)      │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Multi-versioning: Bản A (Safe) / Bản B (Fast)      │
├─────────────────────────────────────────────────────┤
│  Tầng 4: Runtime & Security                         │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ JIT Engine   │  │ Bridge   │  │ Internal      │  │
│  │ (Evolution   │  │ API      │  │ Signer        │  │
│  │  Loop)       │  │ (OS)     │  │ (HMAC-SHA256) │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Register Pressure Monitor → Auto-patch khi CPU rảnh │
└─────────────────────────────────────────────────────┘
```

---

## Cài đặt

```bash
cd Vir
pip install -e ".[dev]"
```

## Sử dụng

### REPL tương tác

```bash
python -m src.runtime.lifecycle.lifecycle --interactive --dump-ir --dump-asm
```

```
vir> Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
[Compiled in 0.42ms]

── Tokens ──
<Token IF 'máy rảnh' @4>
<Token OP_ADD 'tính tổng' @15>
<Token IDENTIFIER 'a' @26>
<Token IDENTIFIER 'b' @30>
<Token TARGET_REGISTER 'thanh ghi' @38>

── Q-IR ──
; module main
func @__main__():
  Q_PATCH_POINT ; CHECK_CPU → dynamic patch
  Q_ADD R2, R0, R1

── Machine Code ──
[PATCH_1]
  Safe: 5B 58 48 01 D8 50 90
  Fast: 48 01 D8 90
```

### Đa ngôn ngữ – Cùng một chương trình, nhiều ngôn ngữ

```
🇻🇳  Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
🇨🇳  如果 机器空闲 加 A 和 B 用 寄存器
🇯🇵  もし CPU空き 足す A と B レジスタで
🇰🇷  만약 CPU여유 더하기 A 와 B 레지스터로
🇬🇧  if cpu_idle add A and B register
```
Tất cả đều biên dịch ra cùng một Q-IR → cùng một mã máy.

### Biên dịch file `.vri`

```bash
python -m src.runtime.lifecycle.lifecycle examples/hello.vri --dump-ir
```

### Demo script

```bash
python examples/demo.py
```

---

## Cấu trúc dự án

```
Vir/
├── src/
│   ├── lib/              # 🔑 Single Source of Truth (English)
│   │   └── keywords.py   # TokenKind enum, KeywordRegistry
│   ├── sublib/           # 🌍 Native Language Adapters
│   │   ├── base.py       # SubLibAdapter ABC, SubLibRegistry
│   │   ├── vi.py         # 🇻🇳 Tiếng Việt  (~100+ phrases)
│   │   ├── zh.py         # 🇨🇳 中文         (~90+ phrases)
│   │   ├── ja.py         # 🇯🇵 日本語       (~90+ phrases)
│   │   ├── ko.py         # 🇰🇷 한국어       (~70+ phrases)
│   │   └── en.py         # 🇬🇧 English     (auto-generated)
│   ├── frontend/         # Tầng 1: Tokens → AST
│   │   ├── tokenizer/    # N-Gram Tokenizer (uses SubLibAdapter)
│   │   ├── parser/       # Recursive-descent Parser (uses TokenKind)
│   │   └── sublib/       # [Legacy] Sublib Mapping loader
│   ├── ir/               # Tầng 2: Q-IR Virtual Machine
│   │   ├── instructions/ # Opcode, QInstruction, IR Builder
│   │   ├── optimizer/    # Constant folding, DCE
│   │   └── registers/    # Virtual register allocator
│   ├── backend/          # Tầng 3: Self-Patching Backend
│   │   ├── codegen/      # x86_64 / arm64 code generation
│   │   ├── patcher/      # Binary patching, JIT memory
│   │   └── monitor/      # Register pressure monitor
│   ├── runtime/          # Tầng 4: Runtime lifecycle
│   │   ├── lifecycle/    # Orchestrator + CLI
│   │   ├── jit/          # JIT Engine (evolution loop)
│   │   └── bridge/       # OS Bridge API
│   └── security/         # Bảo mật
│       ├── signer/       # Internal HMAC signer
│       └── validator/    # Code integrity validator
├── core/                 # 🔧 C/ASM Native Core (libvir_core)
│   ├── src/              # C11 sources
│   ├── asm/              # ARM64 & x86_64 Assembly
│   ├── include/          # Public headers
│   └── lib/              # libvir_core.a / .dylib
├── config/
│   └── sublib_mapping.json   # [Legacy] Bảng ánh xạ JSON
├── tests/                # Unit & integration tests
├── examples/             # Ví dụ .vri + demo scripts
└── docs/                 # Tài liệu kiến trúc
```

### Thêm ngôn ngữ mới

Tạo file `src/sublib/<lang>.py` kế thừa `SubLibAdapter`:

```python
from src.sublib.base import SubLibAdapter, SubLibRegistry, PhraseEntry
from src.lib.keywords import TokenKind

@SubLibRegistry.register
class ThaiAdapter(SubLibAdapter):
    lang_code = "th"
    lang_name = "ภาษาไทย"

    def _define_phrases(self):
        return [
            PhraseEntry("ถ้า", TokenKind.IF, "control_flow"),
            PhraseEntry("ฟังก์ชัน", TokenKind.FUNC_DEF, "definition"),
            PhraseEntry("บวก", TokenKind.OP_ADD, "arithmetic"),
            # ... thêm phrases
        ]

    def _define_stop_words(self):
        return {"แล้ว", "ก็", "นะ", "ครับ", "ค่ะ"}
```

---

## Quy trình thực thi (Runtime Life-cycle)

| Giai đoạn | Mô tả |
|-----------|-------|
| **1. Soạn thảo** | Coder viết Tiếng Việt → Frontend dịch sang Q-IR |
| **2. Chuẩn bị** | Backend tạo file nhị phân + Q_PATCH_POINT |
| **3. Khởi chạy** | Chương trình xin quyền JIT từ OS |
| **4. Tiến hóa** | AI Agent liên tục kiểm tra chip → vá Assembly khi CPU rảnh |

---

## Virgex — Vir Pattern Syntax (VPS)

**Virgex** (**Vir** + re**gex**) là engine pattern matching của Vir, thay thế hoàn toàn regex truyền thống bằng cú pháp **literal-first** chỉ dùng **8 ký hiệu cốt lõi**. Triết lý: *"nhìn là hiểu, không cần decode"*.

### Kiến trúc Dual-Engine

```
VPS Pattern ──→ Lexer ──→ Tokens ──→ Parser ──→ AST ──┬──→ Compiler ──→ Python regex (default)
                                                       └──→ NFA Builder ──→ Thompson NFA (O(n×m), anti-ReDoS)
```

| Engine | Đặc điểm | Dùng khi |
|--------|----------|----------|
| **Regex backend** | Dựa trên `re` module (C-backed), nhanh cho pattern đơn giản | Mặc định |
| **Thompson NFA** | O(n×m) tuyến tính, không catastrophic backtracking | `engine='nfa'` · an toàn cho input không tin cậy |

### 8 Ký hiệu cốt lõi

| Ký hiệu | Vai trò | Ví dụ | Regex tương đương |
|----------|---------|-------|-------------------|
| `@` | Atom (lớp ký tự) | `@Az` · `@0` · `@Az0` | `[A-Za-z]` · `[0-9]` · `[A-Za-z0-9]` |
| `!` | Lượng từ (postfix) | `@0!3` · `@Az!2~5` · `@0!1~` | `[0-9]{3}` · `[A-Za-z]{2,5}` · `[0-9]+` |
| `~` | Tách phạm vi | Dùng trong `!` | `{min,max}` |
| `?` | Tùy chọn (prefix) | `?@Az` | `[A-Za-z]?` |
| `:(` `:)` | Nhóm | `:(A \| B:)` | `(?:A\|B)` |
| `\|` | Neo / hoặc | Đầu = `^`, cuối = `$`; trong nhóm = OR | `^` `$` `\|` |
| `$` | Thoát | `$-` · `$. block .$` | Literal `-` · literal block |
| `-` | Dấu cách | `-` | ` ` (space) |

### Bảng Atom chuẩn

| Atom | Ý nghĩa | Regex |
|------|---------|-------|
| `@Az` | Ký tự Latin (a-z, A-Z) | `[A-Za-z]` |
| `@AZ` | Viết hoa | `[A-Z]` |
| `@az` | Viết thường | `[a-z]` |
| `@0` | Chữ số (0-9) | `[0-9]` |
| `@Az0` | Chữ-số | `[A-Za-z0-9]` |
| `@06` | Phạm vi số | `[0-6]` |

### API

```python
import virgex

# Biên dịch pattern
pat = virgex.compile("| @Az!1~ $- @0!3 |")

# Match đầy đủ
m = virgex.fullmatch("| @Az!1~ $- @0!3 |", "Hello 123")
print(m.text)  # "Hello 123"

# Tìm kiếm
virgex.search("@0!3", "code 404 error")  # → "404"

# Tìm tất cả
virgex.findall("@0!1~", "a1 b23 c456")  # → ["1", "23", "456"]

# Chuyển sang regex truyền thống
virgex.to_regex("@Az!2~5 $- @0!3")
# → "[A-Za-z]{2,5}\\ [0-9]{3}"

# Engine NFA (không backtracking, an toàn ReDoS)
virgex.fullmatch("@Az!1~", "Hello", engine="nfa")
```

### Ví dụ thực tế

```python
# Số điện thoại VN: 09x hoặc 03x, 10 chữ số
virgex.fullmatch("| :( 09 | 03 :) @0!8 |", "0912345678")
# ✅ Match

# Email đơn giản
virgex.fullmatch("| @Az0!1~ $. @Az!2~ |", "user.name@domain.com")

# Mã bưu chính 5 số
virgex.fullmatch("| @0!5 |", "70000")
# ✅ Match

# Biển số xe VN: 2 số + chữ + 5 số
virgex.fullmatch("| @0!2 @AZ @0!5 |", "51A12345")
```

### Self-hosted Virgex (virgex.vri)

Virgex có triển khai bằng chính ngôn ngữ Vir tại `virgex/stdlib/virgex.vri` (708 LOC), bao gồm lexer và bảng atom. Viết hoàn toàn bằng **tiếng Việt**:

```vir
liệt_kê LoạiToken {
    LITERAL,        // Văn bản thường
    ATOM,           // @Az, @0, ...
    QUANTIFIER,     // !3, !2~5
    OPTIONAL,       // ?
    GROUP_OPEN,     // :(
    GROUP_CLOSE,    // :)
    ALTERNATION,    // | (trong nhóm)
    ANCHOR_START,   // | (đầu)
    ANCHOR_END,     // | (cuối)
}
```

### Cấu trúc

```
virgex/
├── README.md                 # Hướng dẫn sử dụng
├── spec/
│   └── VPS_SPEC_v1.md       # Đặc tả kỹ thuật đầy đủ (BNF grammar)
├── src/
│   ├── tokens.py             # 12 token types + quantifier
│   ├── lexer.py              # Greedy longest-match tokenizer
│   ├── ast_nodes.py          # 10 AST node types
│   ├── parser.py             # Recursive-descent parser
│   ├── compiler.py           # AST → Python regex
│   ├── matcher.py            # Virgex class + VPSMatch + API
│   ├── nfa.py                # Thompson NFA (O(n×m) guarantee)
│   └── errors.py             # VPSError hierarchy
├── stdlib/
│   └── virgex.vri            # Self-hosted VPS (708 LOC Vir)
└── tests/                    # 113 tests (lexer + parser + compiler + e2e)
```

---

## Native C Core (libvir_core)

Lõi native C11 biên dịch thành `libvir_core.dylib` + `.a`:

| Nhóm | File | LOC | Mô tả |
|------|------|-----|-------|
| **Compiler** | lexer.c · parser.c · ir_lower.c · q_ir.c · codegen.c | ~4,500 | Tokenizer → AST → Q-IR → machine code |
| **Runtime** | vm.c · patcher.c · jit_bridge.c · bridge.c · signer.c | ~2,000 | VM, JIT, binary self-patching, HMAC-SHA256 |
| **Scheduler** | task.c · task.h | ~600 | Green threads (M:N, `_setjmp/_longjmp`, 64KB mmap stacks) |
| **SIMD** | simd_dispatch.c · simd_index.c · intrinsics.c | ~1,500 | SVE2 > SVE > NEON · AVX-512 > AVX2 > SSE2 · simdjson-style |
| **GPU** | gpu_cuda.c · ptx_gen.c · gpu_metal.c | ~2,200 | CUDA FFI · Q-IR→PTX · Metal ObjC runtime |
| **Accelerator** | amx_accel.c | ~400 | Apple AMX matrix (M1-M4) / Intel AMX |
| **Memory** | slab_alloc.c · huge_alloc.c · numa_alloc.c | ~800 | Slab · huge page · NUMA-aware |
| **Cross-platform** | atomic.c · cpu_caps.c · micro_prober.c | ~600 | ARM64 LDXR/STXR · x86 LOCK · RISC-V LR/SC |

### GPU Kernel Library (data/gpu/)

5 PTX (CUDA sm_70+) + 5 MSL (Metal) prebuilt kernel templates:

| Kernel | PTX | MSL | Đặc điểm |
|--------|-----|-----|----------|
| **vadd** | vadd_f32.ptx | vadd_f32.metal | Vector addition, 1D grid-stride |
| **gemm** | gemm_f32.ptx | gemm_f32.metal | Tiled GEMM 32×32, shared memory |
| **relu** | relu_f32.ptx | relu_f32.metal | ReLU activation |
| **fused_relu_add** | fused_relu_add_f32.ptx | fused_relu_add_f32.metal | Fused kernel (zero intermediate buffer) |
| **softmax** | softmax_f32.ptx | softmax_f32.metal | Per-row softmax, parallel reduction |

Python-level: `codegen_gpu.py` — kernel fusion detection, Q-IR→PTX/MSL lowering, platform auto-detection.

---

## Stdlib (52 Modules)

```
stdlib/vir/
├── prelude.vri          # Auto-import: types, Option, Result, Vec, Map, I/O
├── core/                # Kiểu cơ bản: i8→i64, u8→u64, f32/f64, bool, bits
├── collections/         # Vec<T>, Map<K,V>, Set<T>, Deque, Heap, Ring
├── io/                  # stdio, file, buffered I/O, format traits
├── str/                 # UTF-8 string ops
├── math/                # basic, matrix, tensor, nn, attention, grad, optim
├── mem/                 # Arena, pool, allocator
├── async/               # EventLoop, Task, Waker, Poll<T>
├── net/                 # TCP/UDP/DNS (17 extern funcs)
├── http/                # HTTP client/server (built on net)
├── crypto/              # SHA-256 (native Vir, self-contained)
├── ffi/                 # dlopen/dlsym/dlclose
├── gpu/                 # GPU compute (inline PTX, @native calls)
├── json/                # JSON parse + serialize
├── csv/                 # CSV reader
├── regex/               # Virgex VPS integration
├── thread/              # Thread API (33 extern funcs)
├── test/                # Testing framework
├── iter/                # Iterator combinators
├── sort/                # Sorting algorithms
├── fmt/                 # Format template engine
├── log/                 # Structured logging
├── cli/                 # Argument parser
├── env/ path/ fs/       # OS interaction
├── rand/ uuid/ time/    # Utilities
├── serde/               # Serialization: binary + JSON
├── lsp/                 # Language Server Protocol (stub)
├── pkg/                 # Package manager (SemVer + manifest)
└── 20+ more modules…    # build, debug, profile, reflect, …
```

---

## Benchmark — So sánh hiệu năng đa ngôn ngữ

> Nền tảng: Apple M-series ARM64 · macOS · clang -O3 / rustc -O / go 1.26
>
> Source: `benchmarks/bench_comprehensive_*.{cpp,rs,go,py,mojo}` · prebuilt `bench_cpp` + `bench_rust`

### 1. Tốc độ tính toán (Computational Throughput)

| Task | C++ -O3 | Rust -O | Go | Python/numpy | Vir algo¹ | Python pure |
|------|--------:|--------:|---:|-----------:|----------:|------------:|
| **GEMM 512×512** (µs) | **18,054** | 31,596 | 74,009 | 890² | 91,190³ | 13,124³ |
| **GEMM 1024×1024** (µs) | **185,859** | 287,278 | 652,744 | 8,896² | — | — |
| **Softmax 100K** (µs) | **624** | 1,017 | 1,330 | 942² | 15,847 | 8,145 |
| **EW Fused** mul+add+relu 1M (µs) | **191** | 340 | 651 | 890² | 70,691 | 130,426 |
| **EW Unfused** 3-pass 1M (µs) | 699 | 1,273 | 1,881 | 1,130 | — | — |
| **Welford-Kahan** variance 1M (µs) | **5,276** | 5,764 | 334⁴ | 910² | 133,916 | 69,371 |
| **Kahan dot** 10M (µs) | 49,942 | **46,283** | **3,336**⁴ | 4,455² | — | — |
| **Winograd F(2,3)** 100K tiles (µs) | **88** | 188 | 1,727 | — | 23,960 | — |

> ¹ Vir algorithm sim — thuật toán Vir chạy trên Python interpreter; ARM64 codegen thực tế sẽ nhanh hơn đáng kể.
> ² numpy gọi BLAS (Apple Accelerate) — so sánh không trực tiếp với hand-written loops.
> ³ Đo trên 128×128 (Python quá chậm ở 512×512).
> ⁴ Go có GC overhead thấp hơn cho small-object workload nhưng GEMM chậm hơn C++ 4×.

### 2. Flash Attention — Bộ nhớ O(N) vs O(N²)

| seq_len | Standard O(N²) RAM | Vir Flash O(N) RAM | Tiết kiệm |
|--------:|-------------------:|-------------------:|----------:|
| 256 | 1.0 MB | 0.43 MB | 2× |
| 1,024 | 10.5 MB | 1.6 MB | **6×** |
| 4,096 | 142.6 MB | 6.3 MB | **23×** |
| 8,192 | 553.6 MB | 12.6 MB | **44×** |
| 16,384 | 2,181 MB | 25.2 MB | **87×** |

Flash Attention execution: C++ -O3 = **7.7 ms** (256×64) · numpy = 0.34 ms (BLAS) · Vir/flash algo = 619 ms (Python sim).

### 3. Vir JIT Pipeline — Tốc độ biên dịch

| Giai đoạn | Median | Mô tả |
|-----------|-------:|-------|
| Compile `a + b` | **82 µs** | Tokenize → Parse → IR → Codegen |
| Compile `func def` | **67 µs** | Khai báo hàm + body |
| Compile `loop` | **148 µs** | Vòng lặp + điều kiện |
| Compile `if/else` | **91 µs** | Phân nhánh |
| IR Optimization | **1.5 µs** | Constant fold + DCE |
| ARM64 Codegen | **19 µs** | Q-IR → ARM64 machine code |
| Virgex VPS match | **139 µs** | Pattern compile + match |

### 4. Scripting Engine — Vir vs Python vs Lua

| Task | Python 3.13 | Lua 5.4 | Tỉ lệ Py/Lua |
|------|------------:|--------:|-------------:|
| **fib(28)** recursive | 129.3 ms | **30.4 ms** | 4.3× |
| **fib_iter(10K)** | 0.88 ms | **0.20 ms** | 4.3× |
| **sum(1M)** | 49.1 ms | **7.3 ms** | 6.7× |
| **matrix 4×4** ×10K | 60.9 ms | **21.3 ms** | 2.9× |
| **sieve(1M)** | 101.8 ms | **73.9 ms** | 1.4× |
| **pattern match** ×1K | 92.0 ms | **82.3 ms** | 1.1× |

### 5. Memory Discipline — Allocation latency

| Kích thước | C++ (malloc) | Rust (Vec) | Go (make) |
|-----------:|-------------:|-----------:|----------:|
| 64 B | **31 ns** | 26 ns | 14 ns |
| 4 KB | **29 ns** | 80 ns | 594 ns |
| 1 MB | **738 ns** | 11,138 ns | 55,490 ns |

### 6. Scalability — Multi-thread sum 10M

| Threads | C++ (atomic) | Rust | Go (goroutine) | Python (numpy) |
|--------:|-------------:|-----:|-----------:|-----------:|
| 1 | 39,525 µs | **10,691 µs** | 3,461 µs | 2,140 µs² |
| 2 | 5,157 µs | 8,305 µs | 6,120 µs | 2,393 µs |
| 4 | 3,472 µs | 8,973 µs | 3,903 µs | 1,936 µs |
| 8 | **2,105 µs** | 6,846 µs | 3,295 µs | 2,069 µs |

> ² numpy BLAS tự quản lý thread pool nội bộ.

### 7. Compiler Intelligence — Q-IR Optimization

| Metric | Giá trị |
|--------|---------|
| IR nodes trước optimize | 288 |
| IR nodes sau optimize | 228 (giảm **20.8%**) |
| Auto-vectorized patterns | 3/5 (**60%**) |
| Optimization pass time | **393 µs** |
| Kernel fusion pass (12-layer Transformer) | < 500 µs |

### Chạy benchmark

```bash
# C++ (prebuilt)
./bench_cpp

# Rust (prebuilt)
./bench_rust

# Go
go run benchmarks/bench_comprehensive_go.go

# Python + Vir algorithms
python3 benchmarks/bench_comprehensive_python.py

# Cross-language full suite
python3 benchmarks/bench_cross_lang.py

# Vir JIT + Virgex
python3 benchmarks/bench_jit_comparison.py
```

---

## Phase 2 — Hoàn thành ✅

Tất cả 14 task Phase 2 đã hoàn thành (chi tiết: [PHASE2_ROADMAP_DETAILED.md](docs/PHASE2_ROADMAP_DETAILED.md)):

| Pillar | Tasks | Mô tả |
|--------|-------|-------|
| **A — Optimization** | A1 Pattern Matching · A2 Green Threads · A3 SIMD I/O · A4 AMX · A5 AVX-512 Fix | Ngôn ngữ + hiệu năng |
| **B — Meta** | B1 update_specs.sh · B2 Meta-compiler | Tự động hóa metadata |
| **C — Cross-platform** | C1 I-Cache Flush · C2 Atomics · C3 RISC-V Alignment | ARM64 + RISC-V |
| **D — GPU** | D1 CUDA FFI · D2 PTX Emitter · D3 Metal · D4 Kernel Library | GPU acceleration |

---

## Tương thích OS

| OS | Cơ chế JIT |
|----|-----------|
| **macOS** | `MAP_JIT` + `pthread_jit_write_protect_np(0/1)` |
| **Linux** | `mmap(MAP_ANONYMOUS)` + `sys_mprotect` |
| **Windows** | `VirtualAlloc(PAGE_EXECUTE_READWRITE)` |

---

## Chạy tests

```bash
cd Vir

# C native core (89 tests)
cd core && make test

# Python pipeline (656 tests)
python -m pytest tests/ -v

# Virgex pattern engine (113 tests)
python -m pytest virgex/tests/ -v
```

| Suite | Tests | Trạng thái |
|-------|-------|------------|
| C native | 89 | ✅ All pass |
| Python | 656 | ✅ All pass |
| Virgex | 113 | ✅ All pass |
| **Tổng** | **858** | **✅** |

---

## Roadmap

| Phase | Trạng thái | Focus |
|-------|------------|-------|
| Phase 1 | ✅ Done | Core language, Q-IR VM, self-hosting compiler |
| Phase 2 | ✅ Done | Optimization, GPU, cross-platform ([chi tiết](docs/PHASE2_ROADMAP_DETAILED.md)) |
| Phase 3 | 📋 Planned | Generics, LSP, stdlib native backing ([chi tiết](docs/PHASE3_ROADMAP_DETAILED.md)) |

---

## License

All rights reserved. No license granted for commercial use without explicit permission.  
