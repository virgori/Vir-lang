# Vir – VIRGORI-CORE Engine

> **Lập trình bằng ngôn ngữ tự nhiên • Lõi máy trừu tượng Q-IR • Tự vá mã máy**

---

## Tổng quan

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
│  Tầng 1: Giao diện Đa ngôn ngữ (Frontend)           │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ N-Gram       │→ │ Parser   │→ │ AST           │  │
│  │ Tokenizer    │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│          ↑                                           │
│    SubLibAdapter (vi / zh / ja / ko / en / …)        │
├─────────────────────────────────────────────────────┤
│  Tầng 2: Máy ảo (Q-IR)                              │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ IR Builder   │→ │Optimizer │→ │ QModule       │  │
│  │              │  │ (fold,   │  │ (SSA form)    │  │
│  │              │  │  DCE)    │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Thanh ghi ảo: R₀, R₁, …, Rₙ (không giới hạn)       │
├─────────────────────────────────────────────────────┤
│  Tầng 3: Backend Tự-vá mã                           │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ CodeGen      │→ │ Binary   │→ │ Jump Table    │  │
│  │ (x86_64 /   │  │ Patcher  │  │ Indirection   │  │
│  │  arm64)      │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Multi-versioning: Bản A (An toàn) / Bản B (Nhanh)  │
├─────────────────────────────────────────────────────┤
│  Tầng 4: Runtime & Bảo mật                          │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ JIT Engine   │  │ Bridge   │  │ Internal      │  │
│  │ (Evolution   │  │ API      │  │ Signer        │  │
│  │  Loop)       │  │ (OS)     │  │ (HMAC-SHA256) │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Monitor áp lực thanh ghi → Tự vá khi CPU rảnh      │
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
│   ├── lib/              # 🔑 Nguồn chuẩn duy nhất (Tiếng Anh)
│   │   └── keywords.py   # TokenKind enum, KeywordRegistry
│   ├── sublib/           # 🌍 Adapter Ngôn ngữ Bản địa
│   │   ├── base.py       # SubLibAdapter ABC, SubLibRegistry
│   │   ├── vi.py         # 🇻🇳 Tiếng Việt  (~100+ cụm từ)
│   │   ├── zh.py         # 🇨🇳 中文         (~90+ cụm từ)
│   │   ├── ja.py         # 🇯🇵 日本語       (~90+ cụm từ)
│   │   ├── ko.py         # 🇰🇷 한국어       (~70+ cụm từ)
│   │   └── en.py         # 🇬🇧 English     (tự sinh)
│   ├── frontend/         # Tầng 1: Tokens → AST
│   │   ├── tokenizer/    # N-Gram Tokenizer (dùng SubLibAdapter)
│   │   ├── parser/       # Recursive-descent Parser (dùng TokenKind)
│   │   └── sublib/       # [Di sản] Sublib Mapping loader
│   ├── ir/               # Tầng 2: Máy ảo Q-IR
│   │   ├── instructions/ # Opcode, QInstruction, IR Builder
│   │   ├── optimizer/    # Constant folding, DCE
│   │   └── registers/    # Bộ cấp phát thanh ghi ảo
│   ├── backend/          # Tầng 3: Backend Tự-vá mã
│   │   ├── codegen/      # Sinh mã x86_64 / arm64
│   │   ├── patcher/      # Vá nhị phân, bộ nhớ JIT
│   │   └── monitor/      # Monitor áp lực thanh ghi
│   ├── runtime/          # Tầng 4: Vòng đời Runtime
│   │   ├── lifecycle/    # Orchestrator + CLI
│   │   ├── jit/          # JIT Engine (vòng tiến hóa)
│   │   └── bridge/       # OS Bridge API
│   └── security/         # Bảo mật
│       ├── signer/       # Bộ ký HMAC nội bộ
│       └── validator/    # Bộ xác thực tính toàn vẹn mã
├── core/                 # 🔧 Lõi Native C/ASM (libvir_core)
│   ├── src/              # Mã nguồn C11
│   ├── asm/              # Assembly ARM64 & x86_64
│   ├── include/          # Header công khai
│   └── lib/              # libvir_core.a / .dylib
├── config/
│   └── sublib_mapping.json   # [Di sản] Bảng ánh xạ JSON
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
            # ... thêm các cụm từ khác
        ]

    def _define_stop_words(self):
        return {"แล้ว", "ก็", "นะ", "ครับ", "ค่ะ"}
```

---

## Quy trình thực thi (Runtime Life-cycle)

| Giai đoạn | Mô tả |
|-----------|-------|
| **1. Soạn thảo** | Lập trình viên viết ngôn ngữ tự nhiên → Frontend dịch sang Q-IR |
| **2. Chuẩn bị** | Backend tạo file nhị phân + Q_PATCH_POINT |
| **3. Khởi chạy** | Chương trình xin quyền JIT từ OS |
| **4. Tiến hóa** | AI Agent liên tục theo dõi CPU → vá Assembly khi CPU rảnh |

---

## Tương thích hệ điều hành

| OS | Cơ chế JIT |
|----|------------|
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

## Giấy phép

MIT
