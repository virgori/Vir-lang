# Vir – Architecture & System Runtime Specification

> **Version:** 2.0 | **Updated:** 2026-07-31  
> **Canonical Intermediate Representation:** `HIR → MIR → LIR`  
> **Language Specification:** `docs/vir_language_spec_v2.0_en.md`

---

## 1. Canonical Compiler Pipeline

Vir compiles source code through a 10-pass pipeline down to standalone machine binaries with zero external dependencies (no libc, no linker):

```text
Source Code (.vri)
  │
  ▼
[ Lexer & Parser ] ──────► Abstract Syntax Tree (AST)
  │
  ▼
[ High-Level IR (HIR) ] ───► Semantic verification & type inference
  │
  ▼
[ Mid-Level IR (MIR) ] ───► Control Flow Graph (CFG), SSA, Quadruple Ops (82 QOps)
  │                         Optimization Passes (TCO, CSE, LICM, IVSR, SIMD)
  ▼
[ Low-Level IR (LIR) ] ───► Virtual Register Allocation (Chaitin-Briggs Graph Coloring)
  │                         George-Appel Iterated Coalescing (IRC)
  ▼
[ Binary Emitter ] ──────► Machine Code (ARM64, x86_64, RISC-V, WASM)
  │                         Direct Mach-O 64 / ELF 64 / PE32+ / WASM32 generation
  ▼
Standalone Native Executable (Zero Libc / Direct Kernel Syscalls)
```

### IR Tiers Overview

| Tier | Role | Representation |
| :--- | :--- | :--- |
| **HIR** | Near-source semantic tree | Typed AST with uniform function call syntax (UFCS) resolution |
| **MIR** | Control Flow Graph & SSA optimizations | 82 Canonical QOps, dominance frontiers, basic blocks |
| **LIR** | Machine-near physical layout | Physical register constraints, stack frames, ABI calling conventions |

---

## 2. Multilingual Frontend & Tokenization

Vir provides built-in multilingual syntax adapters, enabling native-language keywords while compiling to canonical intermediate representation:

### 2.1. Keyword Token Mapping

- **`TokenKind` Enum:** 60+ canonical token types (`FUNC_DEF`, `VAR_DECL`, `IF`, `ELSE`, `EIF`, `LOOP`, `WHEN`, `FOR`, `BREAK`, `SKIP`, `OUT`, `OP_ADD`, `OP_SUB`, `OP_MUL`, `OP_DIV`, `CMP_EQ`, `CMP_NE`, `CMP_GT`, `CMP_LT`, `PRINT`, `INPUT`, types, system primitives).
- **`KeywordRegistry`:** Maps canonical language constructs across localized token dictionaries.

| Language Adapter | Region | Sample Mappings |
| :--- | :---: | :--- |
| **English** | 🇬🇧 | `if` → IF, `add` → OP_ADD, `print` → PRINT, `out` → OUT |
| **Vietnamese** | 🇻🇳 | `nếu` → IF, `cộng` → OP_ADD, `in ra` → PRINT, `xuất` → OUT |
| **Chinese** | 🇨🇳 | `如果` → IF, `加` → OP_ADD, `打印` → PRINT |
| **Japanese** | 🇯🇵 | `もし` → IF, `足す` → OP_ADD, `表示する` → PRINT |
| **Korean** | 🇰🇷 | `만약` → IF, `더하기` → OP_ADD, `출력` → PRINT |

### 2.2. Greedy Longest-Match N-Gram Tokenizer

1. **Normalization:** Convert input to canonical UTF-8, normalize casing, strip punctuation, compress consecutive whitespace.
2. **N-Gram Scanning:** Scan tokens left-to-right, attempting longest matching phrases first (`max_ngram` down to 1).
3. **Stop-Word Pruning:** Filter non-semantic grammatical connectors.
4. **Fallback Classifier:** Literals, identifiers, numerical tokens, and Unicode CJK identifier validation.

---

## 3. Quadruple Mid-Level IR (MIR) & Opcode Hierarchy

MIR represents computations as a quadruplet stream within basic blocks: `(Opcode, Dest, Src1, Src2)`.

### Core Opcode Families

- **Arithmetic & Logic:** `Q_ADD`, `Q_SUB`, `Q_MUL`, `Q_DIV`, `Q_MOD`, `Q_POW`, `Q_SHL`, `Q_SHR`, `Q_AND`, `Q_OR`, `Q_XOR`, `Q_NOT`.
- **Control Flow:** `Q_JUMP`, `Q_JUMP_IF`, `Q_JUMP_IF_NOT`, `Q_CALL`, `Q_RET`, `Q_TCO_CALL`.
- **Memory & Pointers:** `Q_ALLOC`, `Q_LOAD_BYTE`, `Q_STORE_BYTE`, `Q_LOAD_WORD`, `Q_STORE_WORD`, `Q_BOUNDS_CHECK`.
- **System & Concurrency:** `Q_SYSCALL`, `Q_ATOMIC_CAS`, `Q_ATOMIC_ADD`, `Q_BARRIER`, `Q_SPIN_LOCK`.

---

## 4. Register Allocation: Chaitin-Briggs Graph Coloring

Vir implements global register allocation using the **Chaitin-Briggs** graph-coloring formulation with **George-Appel Iterated Register Coalescing (IRC)**.

### 4.1. Algorithm Lifecycle

1. **Liveness Analysis:** Backwards dataflow analysis calculating `LiveIn` and `LiveOut` bitsets per basic block.
2. **Interference Graph:** Undirected graph $G = (V, E)$ where nodes represent virtual registers and edges connect concurrently live variables.
3. **Conservative Coalescing (George's Criterion):** Merges copy-related nodes without increasing the chromatic number.
4. **Simplification & Spilling:** Iteratively prunes nodes with degree $< K$ (where $K=31$ ARM64 general-purpose registers). Optimistically spills high-degree nodes.
5. **Coloring:** Reconstructs the graph and assigns physical hardware registers (`x0-x30`, `w0-w30`, `d0-d31`).

---

## 5. Optimization Pipeline (26 Production Passes)

### 5.1. Control Flow & Loop Optimizations
- **Tail-Call Optimization (TCO):** Transforms recursive calls in tail position (`Q_CALL + Q_RET`) into unconditional jumps (`Q_JUMP`), eliminating stack frame growth and enabling $O(1)$ space complexity.
- **Loop Invariant Code Motion (LICM):** Hoists loop-invariant computations out of loop bodies into preheaders.
- **Induction Variable Strength Reduction (IVSR):** Replaces multiplications inside loop bodies with linear accumulators.
- **Symbolic Closed-Form Collapse (Gauss Transform):** Detects closed-form linear progressions $\sum_{i=1}^N i$ and replaces loops with $O(1)$ analytical expressions.

### 5.2. Memory & Vectorization
- **Bounds Check Elimination (BCE):** Eliminates redundant bounds checks when memory accesses are proven strictly within allocation bounds.
- **Escape Analysis & Arena Promotion:** Promotes non-escaping heap buffers to fast bump arenas or execution stack frames.
- **SIMD Auto-Vectorization (NEON / AVX2):** Packs parallel arithmetic lanes into 128-bit vector instructions.

---

## 6. Direct Binary Generation (Linkerless AOT)

Vir generates native object and executable files directly without calling external assemblers or linkers (`as`, `ld`, `lld`):

- **macOS Mach-O 64-bit:** Generates `mach_header_64`, `LC_SEGMENT_64` (`__PAGEZERO`, `__TEXT`), and `LC_UNIXTHREAD` with initial execution state.
- **Linux ELF 64-bit:** Emits `Elf64_Ehdr`, `Elf64_Phdr` (`PT_LOAD`), and entry vector `_start`.
- **Windows PE32+:** Emits DOS header, COFF header, Optional Header 64-bit, and `.text` section aligned to 4096-byte page boundaries.
- **WebAssembly (WASM):** Generates WASM binary format (`\x00asm\x01\x00\x00\x00`) with LEB128 encoding for cross-platform browser runtime.
