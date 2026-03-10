# Vir – VIRGORI-CORE Engine

> **Natural Language Programming • Abstract Q-IR Core • Binary Self-Patching**

---

## Overview

**Vir** is an experimental programming language that allows writing code in **natural languages** (Vietnamese, 中文, 日本語, 한국어, English), compiling down to an abstract machine layer (Q-IR), with a runtime capable of **binary self-patching** based on actual CPU state.

### lib / sublib Architecture

Vir separates **lib** (English standard – single source of truth) and **sublib** (native language mapping layer):

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

Each sublib adapter maps native phrases → standard `TokenKind`, enabling Tokenizer + Parser to work uniformly regardless of input language.

### 4-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Multilingual Frontend                     │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ N-Gram       │→ │ Parser   │→ │ AST           │  │
│  │ Tokenizer    │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│          ↑                                           │
│    SubLibAdapter (vi / zh / ja / ko / en / …)        │
├─────────────────────────────────────────────────────┤
│  Layer 2: Virtual Machine (Q-IR)                    │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ IR Builder   │→ │Optimizer │→ │ QModule       │  │
│  │              │  │ (fold,   │  │ (SSA form)    │  │
│  │              │  │  DCE)    │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Virtual Registers: R₀, R₁, …, Rₙ (unlimited)      │
├─────────────────────────────────────────────────────┤
│  Layer 3: Self-Patching Backend                     │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ CodeGen      │→ │ Binary   │→ │ Jump Table    │  │
│  │ (x86_64 /   │  │ Patcher  │  │ Indirection   │  │
│  │  arm64)      │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Multi-versioning: Version A (Safe) / Version B (Fast) │
├─────────────────────────────────────────────────────┤
│  Layer 4: Runtime & Security                        │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ JIT Engine   │  │ Bridge   │  │ Internal      │  │
│  │ (Evolution   │  │ API      │  │ Signer        │  │
│  │  Loop)       │  │ (OS)     │  │ (HMAC-SHA256) │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  Register Pressure Monitor → Auto-patch when CPU idle │
└─────────────────────────────────────────────────────┘
```

---

## Installation

```bash
cd Vir
pip install -e ".[dev]"
```

## Usage

### Interactive REPL

```bash
python -m src.runtime.lifecycle.lifecycle --interactive --dump-ir --dump-asm
```

```
vir> If cpu idle, calculate sum of A and B using register.
[Compiled in 0.42ms]

── Tokens ──
<Token IF 'cpu idle' @4>
<Token OP_ADD 'calculate sum' @15>
<Token IDENTIFIER 'a' @26>
<Token IDENTIFIER 'b' @30>
<Token TARGET_REGISTER 'register' @38>

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

### Multilingual – Same program, different languages

```
🇻🇳  Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
🇨🇳  如果 机器空闲 加 A 和 B 用 寄存器
🇯🇵  もし CPU空き 足す A と B レジスタで
🇰🇷  만약 CPU여유 더하기 A 와 B 레지스터로
🇬🇧  if cpu_idle add A and B register
```
All compile to the same Q-IR → same machine code.

### Compile `.vir` files

```bash
python -m src.runtime.lifecycle.lifecycle examples/hello.vir --dump-ir
```

### Demo script

```bash
python examples/demo.py
```

---

## Project Structure

```
Vir/
├── src/
│   ├── lib/              # 🔑 Single Source of Truth (English)
│   │   └── keywords.py   # TokenKind enum, KeywordRegistry
│   ├── sublib/           # 🌍 Native Language Adapters
│   │   ├── base.py       # SubLibAdapter ABC, SubLibRegistry
│   │   ├── vi.py         # 🇻🇳 Vietnamese  (~100+ phrases)
│   │   ├── zh.py         # 🇨🇳 Chinese     (~90+ phrases)
│   │   ├── ja.py         # 🇯🇵 Japanese    (~90+ phrases)
│   │   ├── ko.py         # 🇰🇷 Korean      (~70+ phrases)
│   │   └── en.py         # 🇬🇧 English     (auto-generated)
│   ├── frontend/         # Layer 1: Tokens → AST
│   │   ├── tokenizer/    # N-Gram Tokenizer (uses SubLibAdapter)
│   │   ├── parser/       # Recursive-descent Parser (uses TokenKind)
│   │   └── sublib/       # [Legacy] Sublib Mapping loader
│   ├── ir/               # Layer 2: Q-IR Virtual Machine
│   │   ├── instructions/ # Opcode, QInstruction, IR Builder
│   │   ├── optimizer/    # Constant folding, DCE
│   │   └── registers/    # Virtual register allocator
│   ├── backend/          # Layer 3: Self-Patching Backend
│   │   ├── codegen/      # x86_64 / arm64 code generation
│   │   ├── patcher/      # Binary patching, JIT memory
│   │   └── monitor/      # Register pressure monitor
│   ├── runtime/          # Layer 4: Runtime lifecycle
│   │   ├── lifecycle/    # Orchestrator + CLI
│   │   ├── jit/          # JIT Engine (evolution loop)
│   │   └── bridge/       # OS Bridge API
│   └── security/         # Security
│       ├── signer/       # Internal HMAC signer
│       └── validator/    # Code integrity validator
├── core/                 # 🔧 C/ASM Native Core (libvir_core)
│   ├── src/              # C11 sources
│   ├── asm/              # ARM64 & x86_64 Assembly
│   ├── include/          # Public headers
│   └── lib/              # libvir_core.a / .dylib
├── config/
│   └── sublib_mapping.json   # [Legacy] JSON mapping table
├── tests/                # Unit & integration tests
├── examples/             # Example .vir + demo scripts
└── docs/                 # Architecture documentation
```

### Adding a new language

Create file `src/sublib/<lang>.py` extending `SubLibAdapter`:

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
            # ... add more phrases
        ]

    def _define_stop_words(self):
        return {"แล้ว", "ก็", "นะ", "ครับ", "ค่ะ"}
```

---

## Runtime Life-cycle

| Phase | Description |
|-------|-------------|
| **1. Authoring** | Coder writes native language → Frontend translates to Q-IR |
| **2. Preparation** | Backend creates binary + Q_PATCH_POINT |
| **3. Launching** | Program requests JIT permissions from OS |
| **4. Evolution** | AI Agent continuously monitors CPU → patches Assembly when CPU idle |

---

## OS Compatibility

| OS | JIT Mechanism |
|----|---------------|
| **macOS** | `MAP_JIT` + `pthread_jit_write_protect_np(0/1)` |
| **Linux** | `mmap(MAP_ANONYMOUS)` + `sys_mprotect` |
| **Windows** | `VirtualAlloc(PAGE_EXECUTE_READWRITE)` |

---

## Running tests

```bash
cd Vir
python -m pytest tests/ -v
```

---

## License

MIT
