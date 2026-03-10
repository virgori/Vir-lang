# Vir – VIRGORI-CORE 引擎

> **自然語言程式設計 • Q-IR 抽象機核心 • 二進位自修補**

---

## 概述

**Vir** 是一種實驗性程式語言，允許使用**自然語言**（越南語、中文、日語、韓語、英語）編寫程式碼，編譯到抽象機層（Q-IR），執行時期能夠根據實際 CPU 狀態進行**二進位自修補**。

### lib / sublib 架構

Vir 將 **lib**（英語標準 – 唯一真實來源）和 **sublib**（本地語言映射層）分離：

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

每個 sublib 適配器將本地短語映射到標準 `TokenKind`，使 Tokenizer + Parser 能夠統一工作，無論輸入語言是什麼。

### 四層架構

```
┌─────────────────────────────────────────────────────┐
│  第一層：多語言前端                                   │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ N-Gram       │→ │ Parser   │→ │ AST           │  │
│  │ Tokenizer    │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│          ↑                                           │
│    SubLibAdapter (vi / zh / ja / ko / en / …)        │
├─────────────────────────────────────────────────────┤
│  第二層：虛擬機 (Q-IR)                               │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ IR Builder   │→ │Optimizer │→ │ QModule       │  │
│  │              │  │ (fold,   │  │ (SSA form)    │  │
│  │              │  │  DCE)    │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  虛擬暫存器：R₀, R₁, …, Rₙ（無限制）                  │
├─────────────────────────────────────────────────────┤
│  第三層：自修補後端                                   │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ CodeGen      │→ │ Binary   │→ │ Jump Table    │  │
│  │ (x86_64 /   │  │ Patcher  │  │ Indirection   │  │
│  │  arm64)      │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  多版本：版本 A（安全）/ 版本 B（快速）                │
├─────────────────────────────────────────────────────┤
│  第四層：執行時期 & 安全                             │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ JIT Engine   │  │ Bridge   │  │ Internal      │  │
│  │ (Evolution   │  │ API      │  │ Signer        │  │
│  │  Loop)       │  │ (OS)     │  │ (HMAC-SHA256) │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  暫存器壓力監控 → CPU 閒置時自動修補                   │
└─────────────────────────────────────────────────────┘
```

---

## 安裝

```bash
cd Vir
pip install -e ".[dev]"
```

## 使用

### 互動式 REPL

```bash
python -m src.runtime.lifecycle.lifecycle --interactive --dump-ir --dump-asm
```

```
vir> 如果 機器空閒 加 A 和 B 用 暫存器
[Compiled in 0.42ms]

── Tokens ──
<Token IF '機器空閒' @4>
<Token OP_ADD '加' @15>
<Token IDENTIFIER 'a' @26>
<Token IDENTIFIER 'b' @30>
<Token TARGET_REGISTER '暫存器' @38>

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

### 多語言 – 同一程式，不同語言

```
🇻🇳  Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
🇨🇳  如果 机器空闲 加 A 和 B 用 寄存器
🇯🇵  もし CPU空き 足す A と B レジスタで
🇰🇷  만약 CPU여유 더하기 A 와 B 레지스터로
🇬🇧  if cpu_idle add A and B register
```
全部編譯為相同的 Q-IR → 相同的機器碼。

### 編譯 `.vri` 檔案

```bash
python -m src.runtime.lifecycle.lifecycle examples/hello.vri --dump-ir
```

### 示範腳本

```bash
python examples/demo.py
```

---

## 專案結構

```
Vir/
├── src/
│   ├── lib/              # 🔑 唯一真實來源（英語）
│   │   └── keywords.py   # TokenKind enum, KeywordRegistry
│   ├── sublib/           # 🌍 本地語言適配器
│   │   ├── base.py       # SubLibAdapter ABC, SubLibRegistry
│   │   ├── vi.py         # 🇻🇳 越南語   (~100+ 短語)
│   │   ├── zh.py         # 🇨🇳 中文     (~90+ 短語)
│   │   ├── ja.py         # 🇯🇵 日語     (~90+ 短語)
│   │   ├── ko.py         # 🇰🇷 韓語     (~70+ 短語)
│   │   └── en.py         # 🇬🇧 英語     (自動產生)
│   ├── frontend/         # 第一層：Tokens → AST
│   │   ├── tokenizer/    # N-Gram Tokenizer (使用 SubLibAdapter)
│   │   ├── parser/       # 遞迴下降解析器 (使用 TokenKind)
│   │   └── sublib/       # [遺留] Sublib 映射載入器
│   ├── ir/               # 第二層：Q-IR 虛擬機
│   │   ├── instructions/ # Opcode, QInstruction, IR Builder
│   │   ├── optimizer/    # 常數摺疊, DCE
│   │   └── registers/    # 虛擬暫存器分配器
│   ├── backend/          # 第三層：自修補後端
│   │   ├── codegen/      # x86_64 / arm64 程式碼產生
│   │   ├── patcher/      # 二進位修補, JIT 記憶體
│   │   └── monitor/      # 暫存器壓力監控
│   ├── runtime/          # 第四層：執行時期生命週期
│   │   ├── lifecycle/    # 編排器 + CLI
│   │   ├── jit/          # JIT 引擎 (進化迴圈)
│   │   └── bridge/       # OS Bridge API
│   └── security/         # 安全
│       ├── signer/       # 內部 HMAC 簽章器
│       └── validator/    # 程式碼完整性驗證器
├── core/                 # 🔧 C/ASM 原生核心 (libvir_core)
│   ├── src/              # C11 原始碼
│   ├── asm/              # ARM64 & x86_64 組合語言
│   ├── include/          # 公開標頭檔
│   └── lib/              # libvir_core.a / .dylib
├── config/
│   └── sublib_mapping.json   # [遺留] JSON 映射表
├── tests/                # 單元測試 & 整合測試
├── examples/             # 範例 .vri + 示範腳本
└── docs/                 # 架構文件
```

### 新增語言

建立檔案 `src/sublib/<lang>.py` 繼承 `SubLibAdapter`：

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
            # ... 新增更多短語
        ]

    def _define_stop_words(self):
        return {"แล้ว", "ก็", "นะ", "ครับ", "ค่ะ"}
```

---

## 執行時期生命週期

| 階段 | 說明 |
|------|------|
| **1. 撰寫** | 程式設計師使用自然語言撰寫 → 前端翻譯為 Q-IR |
| **2. 準備** | 後端建立二進位檔案 + Q_PATCH_POINT |
| **3. 啟動** | 程式向 OS 請求 JIT 權限 |
| **4. 進化** | AI Agent 持續監控 CPU → CPU 閒置時修補組合語言 |

---

## 作業系統相容性

| OS | JIT 機制 |
|----|----------|
| **macOS** | `MAP_JIT` + `pthread_jit_write_protect_np(0/1)` |
| **Linux** | `mmap(MAP_ANONYMOUS)` + `sys_mprotect` |
| **Windows** | `VirtualAlloc(PAGE_EXECUTE_READWRITE)` |

---

## 執行測試

```bash
cd Vir
python -m pytest tests/ -v
```

---

## 授權

MIT
