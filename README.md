# Vir – VIRGORI-CORE Engine

> **Natural Language Programming • Abstract Q-IR Core • Binary Self-Patching**

🌐 **Language / Ngôn ngữ / 语言:**
[English](README_EN.md) | [Tiếng Việt](README_VI.md) | [简体中文](README_ZH_CN.md) | [繁體中文](README_ZH_TW.md)

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
python -m pytest tests/ -v
```

---

## License

MIT
