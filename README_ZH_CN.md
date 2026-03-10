# Vir – VIRGORI-CORE 引擎

> **自然语言编程 • Q-IR 抽象机核心 • 二进制自修补**

---

## 概述

**Vir** 是一种实验性编程语言，允许使用**自然语言**（越南语、中文、日语、韩语、英语）编写代码，编译到抽象机层（Q-IR），运行时能够根据实际 CPU 状态进行**二进制自修补**。

### lib / sublib 架构

Vir 将 **lib**（英语标准 – 唯一真实来源）和 **sublib**（本地语言映射层）分离：

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

每个 sublib 适配器将本地短语映射到标准 `TokenKind`，使 Tokenizer + Parser 能够统一工作，无论输入语言是什么。

### 四层架构

```
┌─────────────────────────────────────────────────────┐
│  第一层：多语言前端                                   │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ N-Gram       │→ │ Parser   │→ │ AST           │  │
│  │ Tokenizer    │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│          ↑                                           │
│    SubLibAdapter (vi / zh / ja / ko / en / …)        │
├─────────────────────────────────────────────────────┤
│  第二层：虚拟机 (Q-IR)                               │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ IR Builder   │→ │Optimizer │→ │ QModule       │  │
│  │              │  │ (fold,   │  │ (SSA form)    │  │
│  │              │  │  DCE)    │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  虚拟寄存器：R₀, R₁, …, Rₙ（无限制）                  │
├─────────────────────────────────────────────────────┤
│  第三层：自修补后端                                   │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ CodeGen      │→ │ Binary   │→ │ Jump Table    │  │
│  │ (x86_64 /   │  │ Patcher  │  │ Indirection   │  │
│  │  arm64)      │  │          │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  多版本：版本 A（安全）/ 版本 B（快速）                │
├─────────────────────────────────────────────────────┤
│  第四层：运行时 & 安全                               │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ JIT Engine   │  │ Bridge   │  │ Internal      │  │
│  │ (Evolution   │  │ API      │  │ Signer        │  │
│  │  Loop)       │  │ (OS)     │  │ (HMAC-SHA256) │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
│  寄存器压力监控 → CPU 空闲时自动修补                   │
└─────────────────────────────────────────────────────┘
```

---

## 安装

```bash
cd Vir
pip install -e ".[dev]"
```

## 使用

### 交互式 REPL

```bash
python -m src.runtime.lifecycle.lifecycle --interactive --dump-ir --dump-asm
```

```
vir> 如果 机器空闲 加 A 和 B 用 寄存器
[Compiled in 0.42ms]

── Tokens ──
<Token IF '机器空闲' @4>
<Token OP_ADD '加' @15>
<Token IDENTIFIER 'a' @26>
<Token IDENTIFIER 'b' @30>
<Token TARGET_REGISTER '寄存器' @38>

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

### 多语言 – 同一程序，不同语言

```
🇻🇳  Nếu máy rảnh, tính tổng A và B bằng thanh ghi.
🇨🇳  如果 机器空闲 加 A 和 B 用 寄存器
🇯🇵  もし CPU空き 足す A と B レジスタで
🇰🇷  만약 CPU여유 더하기 A 와 B 레지스터로
🇬🇧  if cpu_idle add A and B register
```
全部编译为相同的 Q-IR → 相同的机器码。

### 编译 `.vri` 文件

```bash
python -m src.runtime.lifecycle.lifecycle examples/hello.vri --dump-ir
```

### 演示脚本

```bash
python examples/demo.py
```

---

## 项目结构

```
Vir/
├── src/
│   ├── lib/              # 🔑 唯一真实来源（英语）
│   │   └── keywords.py   # TokenKind enum, KeywordRegistry
│   ├── sublib/           # 🌍 本地语言适配器
│   │   ├── base.py       # SubLibAdapter ABC, SubLibRegistry
│   │   ├── vi.py         # 🇻🇳 越南语   (~100+ 短语)
│   │   ├── zh.py         # 🇨🇳 中文     (~90+ 短语)
│   │   ├── ja.py         # 🇯🇵 日语     (~90+ 短语)
│   │   ├── ko.py         # 🇰🇷 韩语     (~70+ 短语)
│   │   └── en.py         # 🇬🇧 英语     (自动生成)
│   ├── frontend/         # 第一层：Tokens → AST
│   │   ├── tokenizer/    # N-Gram Tokenizer (使用 SubLibAdapter)
│   │   ├── parser/       # 递归下降解析器 (使用 TokenKind)
│   │   └── sublib/       # [遗留] Sublib 映射加载器
│   ├── ir/               # 第二层：Q-IR 虚拟机
│   │   ├── instructions/ # Opcode, QInstruction, IR Builder
│   │   ├── optimizer/    # 常量折叠, DCE
│   │   └── registers/    # 虚拟寄存器分配器
│   ├── backend/          # 第三层：自修补后端
│   │   ├── codegen/      # x86_64 / arm64 代码生成
│   │   ├── patcher/      # 二进制修补, JIT 内存
│   │   └── monitor/      # 寄存器压力监控
│   ├── runtime/          # 第四层：运行时生命周期
│   │   ├── lifecycle/    # 编排器 + CLI
│   │   ├── jit/          # JIT 引擎 (进化循环)
│   │   └── bridge/       # OS Bridge API
│   └── security/         # 安全
│       ├── signer/       # 内部 HMAC 签名器
│       └── validator/    # 代码完整性验证器
├── core/                 # 🔧 C/ASM 原生核心 (libvir_core)
│   ├── src/              # C11 源代码
│   ├── asm/              # ARM64 & x86_64 汇编
│   ├── include/          # 公共头文件
│   └── lib/              # libvir_core.a / .dylib
├── config/
│   └── sublib_mapping.json   # [遗留] JSON 映射表
├── tests/                # 单元测试 & 集成测试
├── examples/             # 示例 .vri + 演示脚本
└── docs/                 # 架构文档
```

### 添加新语言

创建文件 `src/sublib/<lang>.py` 继承 `SubLibAdapter`：

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
            # ... 添加更多短语
        ]

    def _define_stop_words(self):
        return {"แล้ว", "ก็", "นะ", "ครับ", "ค่ะ"}
```

---

## 运行时生命周期

| 阶段 | 描述 |
|------|------|
| **1. 编写** | 程序员使用自然语言编写 → 前端翻译为 Q-IR |
| **2. 准备** | 后端创建二进制文件 + Q_PATCH_POINT |
| **3. 启动** | 程序向 OS 请求 JIT 权限 |
| **4. 进化** | AI Agent 持续监控 CPU → CPU 空闲时修补汇编 |

---

## 操作系统兼容性

| OS | JIT 机制 |
|----|----------|
| **macOS** | `MAP_JIT` + `pthread_jit_write_protect_np(0/1)` |
| **Linux** | `mmap(MAP_ANONYMOUS)` + `sys_mprotect` |
| **Windows** | `VirtualAlloc(PAGE_EXECUTE_READWRITE)` |

---

## 运行测试

```bash
cd Vir
python -m pytest tests/ -v
```

---

## 许可证

MIT
