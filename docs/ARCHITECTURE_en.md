# Vir – Architecture Specification (Vir v2.0)

> **Version:** 2.0 (Self-Hosted / Production)  
> **Updated:** 2026-09  
> **Language Standard:** Vir Language Specification v2.0 (§1.2, §26, §29, §30)  
> **Status:** Sovereign Systems Language — Zero Python, Zero C runtime shims, Zero libc, Zero External Linker.  
> **Canonical Pipeline:** `Source (.vri) → Lexer / Parser → AST → Semantic Analysis (10 Passes) → HIR/MIR (CFG + SSA) → MIR Opts → LIR → RegAlloc (Chaitin-Briggs + George-Appel IRC) → Direct Codegen → Mach-O / ELF / WASM`  
> **Vietnamese Version (Bản tiếng Việt):** [ARCHITECTURE_vi.md](ARCHITECTURE_vi.md)

---

## 0. High-Level Architecture & Core Design Principles

Vir is a sovereign, high-performance systems and AI-native programming language designed to compile directly to bare-metal machine code without depending on any external runtime libraries or third-party toolchains.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          VIR v2.0 SYSTEM ARCHITECTURE                         │
└───────────────────────────────────────────────────────────────────────────────┘
                                       │
    Source Code (.vri)                 │ [Strict English keywords, Spec v2.0]
    (UTF-8 Encoded)                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 1: FRONTEND                                                            │
 │   • Pure Vir UTF-8 Lexer (stdlib/vir/compiler/lexer.vri)                    │
 │   • Recursive Descent AST Parser (stdlib/vir/compiler/parser.vri)           │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    Abstract Syntax Tree               │ [Strongly typed AstNode hierarchy]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 2: SEMANTIC ANALYSIS — 10 DISCRETE PASSES (compiler/semantic.vri)      │
 │   • Module & Import   • Symbol Table    • Name Resolution   • Type Resolve  │
 │   • Type Inference    • Type Checking   • Control Flow CFA  • Borrow Check  │
 │   • Constant Folding  • Diagnostics Engine                                  │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    Semantically Validated AST         │ [ast_to_mir.vri / ast_to_hir.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 3: MID-LEVEL IR — MIR / SSA (compiler/mir*.vri)                        │
 │   • Control Flow Graph (CFG) & Dominator Trees (mir_cfg.vri)                │
 │   • Static Single Assignment (SSA) with Phi insertion & Renaming            │
 │   • Optimization Pipeline: Constant Fold, DCE, CSE, Inlining, Loop LICM     │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    Optimized SSA MIR                  │ [lir_lower.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 4: LOW-LEVEL IR & REGISTER ALLOCATION (compiler/lir*.vri)              │
 │   • Lowering to LIR virtual registers & explicit stack slots                │
 │   • Pre-RA Target Optimization Hook (opt_backend.vri)                       │
 │   • Liveness Analysis & Interference Graph (lir_liveness / interference)    │
 │   • Chaitin-Briggs Graph Coloring Register Allocator & Spill Manager        │
 │   • George-Appel Iterated Register Coalescing (IRC redundant Mov removal)   │
 │   • Post-RA Target Optimization Hook                                        │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    LIR with Physical Registers        │ [lir_codegen*.vri / lir_to_mc.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 5: DIRECT MACHINE CODEGEN & INTERNAL LINKER (compiler/codegen* / binary)│
 │   • Backend Codegen: ARM64 (NEON), x86_64 (AVX), WebAssembly, RISC-V 64     │
 │   • Internal Linker: Direct Mach-O 64-bit, Direct ELF 64-bit, WASM module   │
 │   • Zero `ld64`, Zero `ld.lld`, Zero `gcc/clang` dependency                 │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    Native Executable Binary           │ [Mach-O ARM64 / ELF x86_64 / WASM]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TIER 6: PURE NATIVE VIR RUNTIME (stdlib/vir/rt/)                            │
 │   • Syscall Layer (macOS BSD 0x2000000 / Linux POSIX) — Zero libc           │
 │   • Memory: Direct mmap page allocator, bump arena, free-list heap          │
 │   • String & Vector runtime, raw kernel I/O                                 │
 └─────────────────────────────────────────────────────────────────────────────┘
```

### 0.1. Core Architectural Pillars

1. **Language Sovereignty & Self-Hosting:**
   - The Vir compiler (`stdlib/vir/compiler/virc.vri`) is written 100% in Vir and compiles itself without external dependencies.
   - Early Python bootstrap prototypes (`src/*`) and C runtime shims (`core/*`) are completely superseded by native Vir modules.
   - Self-contained binary emission: The compiler emits executable binaries in native object formats (Mach-O on macOS, ELF on Linux, WebAssembly) directly from machine code buffers, eliminating external linkers.

2. **Single Canonical English Keyword Standard:**
   - **Specification Reality:** In accordance with Vir Language Specification v2.0 §1.2 & §29, Vir syntax is standardized strictly on a **single set of English keywords** (`func`, `var`, `let`, `const`, `if`, `when`, `for`, `loop`, `case`, `out`, `do`, `end`, `end.`, etc.).
   - All historical natural language adapters (`src/sublib/vi.py`, `zh.py`, `ja.py`, `ko.py`), multi-lingual N-gram tokenizers (`ngram_tokenizer.py`), and translation mappings (`config/sublib_mapping.json`) have been **completely removed**.
   - The Vir lexer processes UTF-8 character streams with single-pass greedy matching for standard Vir tokens, delivering deterministic parsing and microsecond-level lexical analysis.

3. **Strict Block Closing & Opener Law:**
   - **Definitions / Declarations** (`func`, `entity`, `enum`, `register`, `mold`, `method`, etc.) close with **`end.`**
   - **Control Flow / Statement Blocks** (`if`, `when`, `for`, `loop`, `case`, `try`, `arena`, etc.) close with **`end`**
   - **Openers:**
     - Expression before body → opened by **`do`** or **`loop`** (`if cond do`, `when cond loop`, `for i in 0..10 do`).
     - No expression before body → opened by colon **`:`** (`func main:`, `try:`, `arena:`).
     - Continuation clauses (`else`, `eif`, `ensure`, `revert`) do **not** take an opener colon `:`.

4. **First-Class AI / Machine Learning (Spec v2.0 §26):**
   - Built-in rank-N `tensor<T>[Dimensions...]` is a first-class language type.
   - Matrix multiplication `**` and fused multiply-add `><` are dedicated hardware-level language operators accelerated by SIMD (NEON on ARM64, AVX on x86_64).
   - Dedicated execution scopes: `infer:` for zero-overhead inference and `train:` for automatic computation graph tracking.
   - Native reverse-mode autodiff (`loss.backward()`) and multi-bit quantization (`quantize(t, bits)`).

---

## 1. Frontend: Pure Vir Lexer & AST Parser

The frontend reads UTF-8 `.vri` source files and generates a strongly-typed Abstract Syntax Tree (AST). It is implemented entirely in self-hosted Vir code within `stdlib/vir/compiler/`.

### 1.1. Lexer (`stdlib/vir/compiler/lexer.vri`)

The lexer performs a single-pass, greedy longest-match scan over UTF-8 bytes without backtracking or translation layers.

- **Data Structures:**
  - `Token`: Contains `type` (`TokType`), `start` offset, byte `length`, and `line` number.
  - `Lexer`: Cursor pointer, source string reference, and diagnostic line/column tracking state.
- **Canonical Token Set (`TokType` - 90+ kinds):**
  - **Core Keywords:** `func`, `var`, `let`, `const`, `if`, `eif`, `else`, `when`, `loop`, `for`, `in`, `case`, `out`, `skip`, `break`, `try`, `ensure`, `revert`, `arena`, `isolate`, `entity`, `enum`, `packed`, `register`, `mold`, `method`.
  - **AI / ML & Advanced Ops:** `tensor`, `infer`, `train`, `quantize`, MatMul `**`, FMA `><`, Power `^`, Remainder `mod`.
  - **Logic & Bitwise (Spec v2.0):** Logical AND `&`, Logical OR `||`, Logical NOT `!`; Bitwise AND `and`, Bitwise OR `or`, Bitwise XOR `xor`, bit shifts `shl`, `shr`, `>>`.
  - **Relational & Equality:** `==`, `!=`, `<`, `>`, `<=`, `>=`, Pattern match `:~`, Exact match `?=`, Assignment `=`.
  - **Separators & Literals:** Colon `:`, Dot `.`, Comma `,`, Semicolon `;`, Parentheses `()`, Brackets `[]`, Braces `{}`, Integer, Float, String, Boolean (`true`, `false`), Null (`none`).

### 1.2. Recursive Descent Parser (`stdlib/vir/compiler/parser.vri`)

The parser constructs a strongly typed `AstNode` tree from the token stream.

- **`AstNode` Structure:**
  - `type`: Enum `AstType` (Program, FuncDef, VarDecl, If, When, For, Loop, Case, Try, Return/Out, BinOp, UnaryOp, TensorDecl, InferBlock, TrainBlock, etc.).
  - `op`: Operator identifier for arithmetic, logic, and AI expressions.
  - `name`: Identifier string (function, variable, type, or field name).
  - `value`: Immediate integer/float/string payload for literal nodes.
  - `children`: Dynamic vector (`vec_rt`) of child nodes.
- **Operator Precedence Climbing (Spec v2.0 §30):**
  Expressions are parsed strictly following the 8-tier precedence hierarchy:
  1. Member Access (`.`), Safe Navigation (`?.`), Swizzle (`~`), Atomic (`!!`).
  2. Unary Prefix (`!`, `-`), Right-associative Power (`^`).
  3. Tensor MatMul (`**`), Tensor FMA (`><`), Multiplication/Division (`*`, `/`), Remainder (`mod`).
  4. Explicit Cast (`as`), Bit Shifts (`shl`, `shr`, `>>`), Addition/Subtraction (`+`, `-`).
  5. Relational Comparisons (`<`, `>`, `<=`, `>=`), Equality (`==`, `!=`, `?=`), Pattern Match (`:~`).
  6. Logical AND (`&`), Bitwise AND (`and`).
  7. Logical OR (`||`), Bitwise OR (`or`), Bitwise XOR (`xor`).
  8. Assignment (`=`, right-associative).

---

## 2. Semantic Analysis Engine (10 Discrete Passes)

Orchestrated by `semantic_run` in `stdlib/vir/compiler/semantic.vri`, the semantic analysis engine executes 10 discrete passes over the AST. If any pass records an error (`error_count > 0`), the pipeline terminates immediately with rich diagnostics before IR lowering.

```
       AST from Parser
             │
             ▼
    ┌──────────────────┐
    │  Pass 1: MODULES │ ─── Module discovery, DAG validation, `include` & `import` resolution
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 2: SYMBOLS │ ─── Register global functions, entities, enums, constants into SymbolTable
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 3: NAMES   │ ─── Lexical scope traversal, resolve variable references, detect shadows
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 4: TYPES   │ ─── Resolve type signatures, struct layouts, alignments, field offsets
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 5: INFER   │ ─── Contextual type inference for unannotated `var` and `let` bindings
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 6: CHK-TYP │ ─── Strict typechecking, operator compatibility, tensor shape validation
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 7: CFA     │ ─── Control Flow Analysis: Return path exhaustiveness, unreachable code
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 8: BORROW  │ ─── Ownership, immutable `&` vs mutable `&mut` borrows, lifetime verification
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 9: CONST   │ ─── Compile-time constant folding and expression simplification
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 10: DIAG   │ ─── Aggregate errors & warnings, format ANSI diagnostic messages
    └────────┬─────────┘
             │
             ▼
       Validated AST
```

| Pass | Source File | Responsibilities |
|------|-------------|------------------|
| **Pass 1: Modules** | `sem_pass1_modules.vri` | Scans module paths, handles `include` and `import ... from`, resolves the dependency DAG and prevents circular includes. |
| **Pass 2: Symbols** | `sem_pass2_symbols.vri` | Populates `SymbolTable`: registers global functions, entities, methods, enums, and module-level constants. |
| **Pass 3: Names** | `sem_pass3_names.vri` | Traverses `ScopeTree` to bind identifiers to symbol IDs; flags undeclared variables and invalid scopes. |
| **Pass 4: Types** | `sem_pass4_types.vri` | Computes struct memory layouts, alignments, size metrics, and validates non-recursive value types. |
| **Pass 5: Infer** | `sem_pass5_infer.vri` | Deduces types for unannotated variable declarations based on initializer expression return types. |
| **Pass 6: Typecheck** | `sem_pass6_typecheck.vri` | Enforces Vir v2.0 type rules: validates function signatures, implicit conversion bans, tensor rank/dimensions, and resolves UFCS method calls via 4-tier candidate matching. |
| **Pass 7: CFA** | `sem_pass7_cfa.vri` | Control Flow Analysis: verifies all execution paths terminate with `out` or throw; detects unreachable blocks. |
| **Pass 8: Borrow** | `sem_pass8_borrow.vri` | Memory safety checker: enforces the single-mutable (`&mut`) or multiple-immutable (`&`) borrow rule without a garbage collector. |
| **Pass 9: ConstFold** | `sem_pass9_constfold.vri` | Evaluates compile-time constant expressions (e.g., `32 * 1024` → `32768`) and folds dead branches. |
| **Pass 10: Diagnostics** | `sem_pass10_diagnostics.vri` | Collects all diagnostic records, cross-references source spans, and emits formatted compiler diagnostics. |

---

## 3. Intermediate Representation: HIR & MIR (SSA & CFG)

Per Vir Language Specification v2.0 §1.2, the compiler lowers the AST through a canonical IR chain: **AST → HIR → MIR → LIR**.

### 3.1. High-Level Intermediate Representation (HIR)
- Modules: `stdlib/vir/compiler/hir.vri`, `ast_to_hir.vri`, and `hir_to_mir.vri`.
- Retains high-level structured semantics, such as entity methods, typed pattern matching, structured `arena:` scopes, and high-level tensor blocks (`infer:` / `train:`).

### 3.2. Mid-Level Intermediate Representation (MIR)
- Module: `stdlib/vir/compiler/mir.vri`.
- **Architectural Characteristics:**
  - **Control Flow Graph (CFG):** Organized into `MirBlock` structures with explicit predecessor (`preds`) and successor (`successors`) edge lists.
  - **Static Single Assignment (SSA):** Every virtual register is assigned exactly once.
  - Lowered directly from AST via `ast_to_mir.vri` or through the canonical HIR pipeline.

- **Core MIR Instruction Set (`MirOp`):**

| Category | Opcodes |
|----------|---------|
| **Control Flow & Memory** | `Nop`, `Move`, `Load`, `Store`, `Jump`, `JumpIf`, `JumpIfNot`, `Return` |
| **Arithmetic & Bitwise** | `Add`, `Sub`, `Mul`, `Div`, `Mod`, `Pow`, `And`, `Or`, `Xor`, `Shl`, `Shr`, `Not` |
| **Comparison** | `CmpEq`, `CmpNe`, `CmpGt`, `CmpLt`, `CmpGe`, `CmpLe` |
| **Procedure Calls** | `SetArg`, `Call`, `Intrinsic` |
| **Native AI / Tensor** | `MatMul` (`**`), `Fma` (`><`) |

- **MIR Intrinsics (`MIR_INTR_*`):**
  Specialized system and memory primitives:
  - `MIR_INTR_STR_LIT`, `MIR_INTR_PRINT`, `MIR_INTR_INPUT`: String and console operations.
  - `MIR_INTR_ARRAY`, `MIR_INTR_TUPLE`, `MIR_INTR_ENTITY`: Object allocations.
  - `MIR_INTR_INDEX`, `MIR_INTR_INDEX_STORE`: Multi-dimensional tensor/array access.
  - `MIR_INTR_ARENA`: Arena memory region mark and sweep.
  - `MIR_INTR_THROW`, `MIR_INTR_ENSURE`, `MIR_INTR_REVERT`: Zero-cost error handling.

### 3.3. SSA Construction & CFG Dominance
- **CFG Dominators (`mir_cfg.vri`):**
  Computes the Dominator Tree and Dominance Frontiers across the basic blocks of each function using Lengauer-Tarjan or iterative bitvector algorithms.
- **$\phi$-Node Insertion (`mir_ssa.vri`):**
  Places $\phi$-functions at dominance frontiers for variables modified across converging branches.
- **SSA Renaming (`mir_ssa.vri`):**
  Renames all local variables into distinct SSA versioned registers ($v_0, v_1, v_2, \ldots$).

### 3.4. MIR Optimization Pipeline (`mir_opt_pipeline.vri`, `mir_opt.vri`)
Configurable from `-O0` (debug) to `-O3` (aggressive):
1. **Sparse Conditional Constant Propagation (SCCP):** Evaluates constants through $\phi$-nodes and propagates values across branches.
2. **Dead Code Elimination (DCE):** Traverses def-use chains and prunes instructions with unused results.
3. **Common Subexpression Elimination (CSE):** Eliminates redundant computations within dominator scopes.
4. **Function Inlining:** Inlines small functions and `@inline` procedures to eliminate call overhead.
5. **Loop Invariant Code Motion (LICM):** Hoists loop-invariant computations into pre-header blocks.
6. **Target-Specific MIR Optimizations (`opt_backend_run_mir_post`):** Applies architecture-specific transformations prior to LIR lowering.

---

## 4. Low-Level IR (LIR) & Register Allocation

Implemented in `stdlib/vir/compiler/lir*.vri`. LIR lowers SSA MIR into a flat, machine-adjacent instruction sequence with physical registers, abstract virtual registers, and explicit stack slots.

### 4.1. LIR Instruction Set & Operands (`lir.vri`)
- **Machine Types (`LirType`):** `Int8`, `Int16`, `Int32`, `Int64`, `F32`, `F64`, `Ptr`, `Vector`.
- **Operand Types (`LirOperandType`):**
  - `PhysReg`: Architecture-specific physical CPU register.
  - `VRegInt` / `VRegFloat`: Virtual integer/floating-point register pending allocation.
  - `StackMem`: Frame-pointer relative stack slot `[FP - offset]`.
  - `Imm`: 64-bit immediate constant.
  - `Label`: Branch target within the function.
- **LIR Opcodes (`LirOp`):**
  `Nop`, `Mov`, `Add`, `Sub`, `Mul`, `Div`, `Push`, `Pop`, `Call`, `Jmp`, `JmpCond`, `Cmp`, `Ret`, `Load`, `Store`, `Rem`, `SetArg`, `Intrinsic`, `And`, `Or`, `Xor`, `Shl`, `Shr`, `Not`, `Pow`, `MatMul`, `Fma`, `TailCall`.

### 4.2. LIR Lowering (`lir_lower.vri`)
- Converts MIR instructions into concrete LIR sequences.
- Deconstructs SSA form: Replaces $\phi$-functions with parallel register copies along predecessor edges.
- Sets up ABI call sequences by packing arguments into target ABI register conventions.

### 4.3. Graph Coloring Register Allocation & Coalescing

Vir employs a production-grade **Chaitin–Briggs Graph Coloring Allocator** coupled with **George–Appel Iterated Register Coalescing (IRC)** (`stdlib/vir/compiler/lir_regalloc_color.vri`):

```
       LIR with Virtual Registers
                   │
                   ▼
   ┌───────────────────────────────┐
   │ 1. LIR Normalization          │ ─── Eliminate no-op copies, normalize operands
   └───────────────┬───────────────┘
                   ▼
   ┌───────────────────────────────┐
   │ 2. Liveness Analysis          │ ─── Compute Live Intervals [start, end] per virtual register
   └───────────────┬───────────────┘
                   ▼
   ┌───────────────────────────────┐
   │ 3. Interference Graph Builder │ ─── Build adjacency conflict graph for concurrent variables
   └───────────────┬───────────────┘
                   ▼
   ┌───────────────────────────────┐
   │ 4. Chaitin-Briggs             │ ─── K-color simplification & register assignment;
   │    Coloring & Spill Manager   │     Compute loop-weighted spill costs & spill to StackMem
   └───────────────┬───────────────┘
                   ▼
   ┌───────────────────────────────┐
   │ 5. George-Appel IRC           │ ─── Iteratively coalesce Mov Rd, Rs copies without
   │    Coalescing Pass            │     increasing graph chromatic number
   └───────────────┬───────────────┘
                   ▼
       LIR with Physical Registers
```

1. **Liveness Analysis (`lir_liveness.vri`):** Computes live-in, live-out sets, and linear intervals for each virtual register across basic blocks.
2. **Interference Graph (`lir_interference.vri`):** Constructs an adjacency matrix/list connecting registers whose live ranges overlap.
3. **Graph Coloring:**
   - Evaluates node degree against $K$ (available physical registers for the target).
   - Simplifies nodes with degree $< K$ onto a selection stack.
   - When all remaining nodes have degree $\ge K$, selects spill candidates based on loop nesting depth and use frequency.
4. **Iterated Register Coalescing (IRC):**
   Applies Briggs/George conservative heuristics to merge copy-related nodes, eliminating redundant `Mov` instructions and yielding optimal register packing.

---

## 5. Direct Machine Code Generation & Internal Linker

All machine code generation and binary linking are performed natively by the Vir compiler without invoking external assemblers or linkers (`as`, `ld`, `ld64`, `lld`, `gcc`, `clang`).

### 5.1. Target Machine Code Generators

- **ARM64 / AArch64 (`stdlib/vir/compiler/lir_codegen.vri`):**
  - Fully compliant with the **AAPCS64** standard ABI ($X_0-X_7$ for arguments, $X_0/X_1$ for return values, 16-byte stack alignment).
  - Emits 32-bit machine instructions directly into `CodeBuf`:
    - ALU: `ADD`, `SUB`, `MUL`, `SDIV`, `UDIV`.
    - Memory & Immediate: `MOVZ`, `MOVK`, `LDR`, `STR`, `STP`, `LDP`.
    - Control Flow: `B`, `B.cond`, `BL`, `BLR`, `RET`.
    - Bitwise: `AND`, `ORR`, `EOR`, `LSL`, `LSR`.
  - **NEON SIMD Vectorization:** Direct encoding of vector instructions (`LD1`, `ST1`, `FADD.4S`, `FMUL.4S`, `FMLA.4S`) for tensor operations.

- **x86_64 (`stdlib/vir/compiler/lir_codegen_x86.vri`):**
  - Fully compliant with the **System V AMD64 ABI** (`RDI`, `RSI`, `RDX`, `RCX`, `R8`, `R9` for arguments, `RAX` for return).
  - Emits REX prefixes (REX.W), ModR/M bytes, SIB bytes, and immediate offsets:
    - ALU: `ADD`, `SUB`, `IMUL`, `IDIV`, `CQO`.
    - Control Flow: `JMP rel32`, `Jcc rel32`, `CALL rel32`, `RET`.
    - Memory: `MOV [rbp - off], reg`, `PUSH`, `POP`.
  - **AVX/SSE Vectorization:** VEX prefix encodings for 128-bit / 256-bit SIMD (`vaddps`, `vmulps`, `vfmadd213ps`).

- **WebAssembly (`stdlib/vir/compiler/lir_codegen_wasm.vri`):**
  - Emits structured WASM bytecode binaries (`.wasm`).
  - Generates standard WASM binary sections: Type, Import, Function, Table, Memory, Global, Export, Code.

- **RISC-V 64 (`stdlib/vir/compiler/lir_to_mc.vri`, `mc_printer.vri`):**
  - Targets RV64GC with standard LP64D calling conventions.
  - Implements an intermediate Machine Code (MC) layer and clean assembly generation.

### 5.2. Independent Binary Object Linkers

- **Mach-O 64-bit Writer (`stdlib/vir/compiler/macho.vri`):**
  - Directly constructs executable Mach-O binaries for macOS (Apple Silicon ARM64 and Intel x86_64).
  - Emits standard Mach-O load commands and headers:
    - `mach_header_64` (Magic `0xFEEDFACF`, cputype, filetype `MH_EXECUTE`).
    - `LC_SEGMENT_64 (__PAGEZERO)`: 4GB null-dereference guard segment.
    - `LC_SEGMENT_64 (__TEXT)`: Contains `__text` (executable code) and `__cstring` (string pool).
    - `LC_MAIN`: Configures the direct execution entry point pointing to `_start` / `main`.
    - `LC_LOAD_DYLINKER`: System dylinker or bare-metal configuration.

- **ELF 64-bit Writer (`stdlib/vir/compiler/binary.vri`, `stdlib/vir/rt/elf.vri`):**
  - Directly constructs executable ELF binaries for Linux.
  - Generates ELF64 headers and program headers:
    - `Elf64_Ehdr`: ELFCLASS64, ELFDATA2LSB, `ET_EXEC` / `ET_DYN`.
    - `Elf64_Phdr`: `PT_LOAD` segments with RX (code) and RW (data) permissions.
    - Section headers: `.text`, `.rodata`, `.data`, `.symtab`, `.strtab`.

---

## 6. Pure Native Runtime Layer (`stdlib/vir/rt/`)

In adherence to the **Zero Libc & Zero External Runtime** principle, all core system runtime primitives are implemented in pure Vir at `stdlib/vir/rt/`:

```
stdlib/vir/rt/
├── syscall.vri     # Direct kernel syscalls: macOS BSD 0x2000000 & Linux POSIX
├── alloc.vri       # Anonymous mmap page allocator, bump arena, free-list heap
├── vec_rt.vri      # Dynamic byte vector (bvec) & object vector runtime
├── string_rt.vri   # Fat-pointer UTF-8 strings & StringBuilder
├── io.vri          # Low-level console & file descriptor I/O
├── start.vri       # Execution entry point `_start` / `start`, argc/argv parser
├── macho.vri       # Mach-O runtime binary structures
└── elf.vri         # ELF runtime binary structures
```

### 6.1. Kernel Syscall Interface (`syscall.vri`)
Vir bypasses `libc.so` and `libSystem.dylib` entirely, issuing direct software interrupts to the OS kernel:
- **macOS (Darwin ARM64 / x86_64):**
  Uses Darwin BSD class 2 syscall offsets (`0x2000000`):
  - `sys_exit` = `0x2000001`
  - `sys_write` = `0x2000004`
  - `sys_open` = `0x2000005`
  - `sys_close` = `0x2000006`
  - `sys_mmap` = `0x20000c5` (197)
  - `sys_munmap` = `0x2000049` (73)
- **Linux (x86_64 / ARM64):**
  Uses standard Linux syscall numbers (e.g., `sys_write` = 1 on x86_64, 64 on AArch64) via `syscall` / `svc #0`.

### 6.2. Memory Subsystem (`alloc.vri`)
- **Page Allocation:** Maps virtual memory pages directly via `sys_mmap` (`PROT_READ | PROT_WRITE`, `MAP_ANONYMOUS | MAP_PRIVATE`).
- **Arena Scopes (`arena:` blocks):**
  Ultra-fast bump-pointer allocation for temporary objects within a scope. When execution exits the `end` of an `arena:` block, all memory is reclaimed instantly by resetting the arena pointer.
- **Heap Allocator (`vir_alloc`, `vir_free`, `vir_realloc`):**
  Thread-safe free-list allocator managing heap memory for long-lived objects.

### 6.3. Vector & String Runtime (`vec_rt.vri`, `string_rt.vri`)
- **`bvec` (Byte Vector):** Dynamically resizable byte buffer with low-level little-endian encoders (`bvec_push_u32_le`, `bvec_push_u64_le`). Serves as the binary backend for `CodeBuf`.
- **`vec_rt` (Object Vector):** Dynamically resizable pointer array supporting $O(1)$ indexed access.
- **Fat-Pointer Strings:** Strings in Vir consist of a raw data pointer and a byte length, eliminating buffer overruns and enabling zero-copy sub-string slicing.

---

## 7. Native AI / Machine Learning Subsystem (Spec v2.0 §26)

Unlike traditional languages that rely on external C++ or Python bindings, Vir natively integrates tensor mathematics into the language grammar, type system, and code generator:

```vir
var w: tensor<f32>[64, 128]
var x: tensor<f32>[128, 32]
train:
    var y = w ** x
    var loss = compute_loss(y)
    loss.backward()
end
```

### 7.1. First-Class Tensor Type (`tensor<T>[Dims...]`)
- Canonical Syntax: `tensor<Element_Type>[Dim_1, Dim_2, ...]`.
- Tensor ranks and dimensions are validated statically during Semantic Pass 6.
- Underlying memory is allocated in row-major contiguous or strided layout optimized for SIMD cache lines.

### 7.2. Hardware-Level AI Operators
- **Infix Matrix Multiplication (`**`):**
  The expression `a ** b` computes tensor dot products between dimension-compatible tensors ($[M, K] ** [K, N] ightarrow [M, N]$).
  - Not a library call; lowers to `MirOp.MatMul` → `LirOp.MatMul`.
  - Emits vectorized tiled GEMM loops using ARM NEON or x86 AVX instructions.
- **Fused Multiply-Add (`><`):**
  The expression `a >< b` maps directly to single-cycle hardware FMA instructions on CPU/NPU, maximizing throughput and numeric precision.

### 7.3. Execution Contexts: `infer:` and `train:`
- **`infer:` Block:**
  - Disables computation graph tracking for zero autodiff memory overhead.
  - Employs static activation buffer reuse to minimize RAM consumption.
- **`train:` Block:**
  - Automatically activates the dynamic computation tape.
  - Allocates `.grad` fields on parameter tensors to accumulate partial derivatives.

### 7.4. Reverse-Mode Tape Autodiff (`backward()`)
- During execution within `train:`, tensor mathematical operations record operation nodes and parent references onto an autodiff tape.
- Invoking `loss.backward()` initiates a reverse topological traversal across the tape, applying the calculus chain rule to compute gradients stored directly in `.grad`.

### 7.5. Multi-Bit Quantization (`quantize`)
- The built-in primitive `quantize(tensor, format)` enables precision conversions:
  - `INT8` (Symmetric / Asymmetric integer quantization).
  - `INT4` (Sub-byte packed weight quantization for large language models).
  - `FP16` / `BF16`.
- Implemented in `stdlib/vir/ai/quantize.vri`.

### 7.6. High-Level AI Standard Library (`stdlib/vir/ai/`)
- `model.vri`: Neural network layers (Linear, Conv2D, Multi-Head Attention, Transformer blocks).
- `train.vri`: Training loops and optimizers (SGD, Adam, AdamW).
- `infer.vri`: Batching and streaming inference execution engines.
- `onnx.vri`: Direct parser and runner for standard ONNX model graphs.
- `vision.vri`: Image preprocessing and computer vision pipelines.

---

## 8. Dynamic JIT & Runtime Self-Patching

Located in `stdlib/vir/jit/` and `core/src/jit_bridge.c`. Vir provides a JIT execution mode with hardware-adaptive dynamic self-patching.

```
                   Source / IR
                        │
                        ▼
          ┌───────────────────────────┐
          │ Dual-Emit Code Generator  │
          └─────────────┬─────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
  ┌─────────────┐               ┌─────────────┐
  │ Variant A:  │               │ Variant B:  │
  │ Safe (Stack)│               │ Fast (Reg)  │
  └──────┬──────┘               └──────┬──────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
           ┌─────────────────────────┐
           │  Jump Table Indirection │ ── JMP targets Variant A initially
           └────────────┬────────────┘
                        │
  Runtime Loop          │ (Execute & monitor CPU pressure)
  Evolution Loop        ▼
           ┌─────────────────────────┐
           │ Monitor: CPU Load < 80% │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
    [Sufficient Regs]         [Fault / Spill Detected]
           │                         │
           ▼                         ▼
  Overwrite JMP offset      Invoke Automatic Rollback
  switch to Fast Variant!   revert to Safe Variant
```

1. **Dual-Emit Architecture:**
   The code generator concurrently emits two machine code variants for dynamic hot-spots:
   - **Variant A (Safe):** Stack-based execution with zero register pressure risk.
   - **Variant B (Fast):** Register-direct execution with maximum throughput.
2. **Jump Table Patching:**
   Execution is routed through an indirect jump table. When CPU pressure monitoring detects available register headroom ($N_{free} > 	ext{threshold}$), the patcher overwrites the 4-byte relative offset in the `JMP` table, atomically redirecting execution to Variant B without process interruption.
3. **Rollback & Blacklisting:**
   If Variant B triggers a fault or register spilling, the engine invokes `jit_bridge_rollback()` to restore the jump table to Variant A. If a block faults repeatedly (default: 3 rollbacks), it is marked `PERMANENT_SAFE`.
4. **Memory Protection:**
   On macOS ARM64, JIT pages toggle between write and execute permissions using `pthread_jit_write_protect_np(0)` and `pthread_jit_write_protect_np(1)` combined with `sys_icache_invalidate()`. On Linux, `mprotect()` is used.

---

## 9. Self-Hosting Bootstrap & Verification

Vir achieves complete compiler self-sufficiency through a 3-stage fixed-point bootstrap verification cycle:

```
┌──────────────┐   Executed by C-VM    ┌─────────────────┐
│ Stage 0      │ ─────────────────────→│ Binary virc-s0  │
│ (virc.vri)   │                       │ (Initial Boot)  │
└──────────────┘                       └────────┬────────┘
                                                │
                                                ▼ Compiles itself
┌──────────────┐    Compiled by        ┌─────────────────┐
│ Stage 1      │ ─────────────────────→│ Binary virc-s1  │
│ (virc.vri)   │    virc-s0            │ (Self-Hosted)   │
└──────────────┘                       └────────┬────────┘
                                                │
                                                ▼ Compiles itself again
┌──────────────┐    Compiled by        ┌─────────────────┐
│ Stage 2      │ ─────────────────────→│ Binary virc-s2  │
│ (virc.vri)   │    virc-s1            │ (Final Verify)  │
└──────────────┘                       └─────────────────┘
                                                │
                          Verification: virc-s1 == virc-s2 (Bit-for-bit identical)
```

1. **Stage 0:** The pure Vir compiler driver (`stdlib/vir/compiler/virc.vri`) is bootstrapped via the minimal C-VM runtime, generating the first native compiler binary `virc-s0`.
2. **Stage 1:** `virc-s0` compiles its own source code (`stdlib/vir/compiler/virc.vri`), yielding the pure native compiler `virc-s1`.
3. **Stage 2 (Fixed-Point Verification):** `virc-s1` compiles `virc.vri` once more to produce `virc-s2`. When the cryptographic SHA-256 hashes of `virc-s1` and `virc-s2` match bit-for-bit, self-hosting is formally proven.

---

## 10. Canonical Vir v2.0 Example

The following program demonstrates canonical Vir v2.0 syntax, strict English keywords, tensor declarations, and native inference blocks:

```vir
# File: demo_ai.vri
# Canonical Vir v2.0 Specification — English Standard

module demo.ai

include vir.rt.io
import print_ln, print_int from vir.rt.io

func matrix_multiply_demo:
    # 1. Declare two 2x2 floating-point tensors
    var a: tensor<f32>[2, 2]
    var b: tensor<f32>[2, 2]

    # 2. Populate tensor elements
    a[0, 0] = 1.0; a[0, 1] = 2.0
    a[1, 0] = 3.0; a[1, 1] = 4.0

    b[0, 0] = 5.0; b[0, 1] = 6.0
    b[1, 0] = 7.0; b[1, 1] = 8.0

    # 3. Optimized inference scope (no autodiff overhead)
    infer:
        # Native matrix multiplication operator: a ** b
        var c = a ** b
        print_ln("Result c[0, 0] = ")
        print_int(c[0, 0] as int)
    end
end.

func main:
    print_ln("Vir v2.0 System Initialized...")
    matrix_multiply_demo()
    out 0
end.
```

---

## 11. Historical vs. Production Architecture Matrix

To maintain codebase transparency, the table below delineates obsolete early prototype components from the current self-hosted Vir v2.0 production architecture:

| Subsystem | Historical Prototype (Obsolete) | Production Architecture (Vir v2.0) | Canonical Implementation File |
|---|---|---|---|
| **Keyword Syntax** | Multi-lingual (`src/sublib/{vi,zh,ja,ko}.py`) | Single English Standard (Spec v2.0 §1.2 & §29) | `stdlib/vir/compiler/lexer.vri` |
| **Lexer** | N-Gram Greedy phrase match (`ngram_tokenizer.py`) | Direct UTF-8 character stream scanner | `stdlib/vir/compiler/lexer.vri` |
| **Vocabulary Map** | JSON file `config/sublib_mapping.json` | Strongly typed static `TokType` enum | `stdlib/vir/compiler/lexer.vri` |
| **Parser** | Python AST Parser (`src/frontend/parser/`) | Pure Vir Recursive Descent Parser | `stdlib/vir/compiler/parser.vri` |
| **Semantics** | Ad-hoc checks in legacy compiler | 10 Discrete Semantic Passes with diagnostics | `stdlib/vir/compiler/semantic.vri` |
| **IR Representation** | Flat linear Q-IR opcode stream | Canonical pipeline: AST → HIR → MIR (SSA) → LIR | `mir.vri`, `mir_ssa.vri`, `lir.vri` |
| **Register Allocator** | Basic Linear Scan | Chaitin–Briggs Graph Coloring + George–Appel IRC | `lir_regalloc_color.vri` |
| **Machine Codegen** | External Assembler or C runtime shims | Direct machine code byte emission (ARM64/x86/WASM) | `lir_codegen.vri`, `lir_codegen_x86.vri` |
| **Binary Linker** | External `gcc`, `clang`, `ld64`, `lld` | Internal Mach-O 64-bit and ELF 64-bit writer | `macho.vri`, `binary.vri`, `rt/elf.vri` |
| **System Runtime** | `libc.so`, `libSystem.dylib`, C runtime | Direct OS Syscalls (macOS BSD 0x2000000 / Linux) | `stdlib/vir/rt/syscall.vri` |
| **AI / ML Engine** | External library wrappers / test mocks | Native `tensor`, MatMul `**`, Autodiff `backward()` | `mir.vri`, `lir_codegen.vri`, `stdlib/vir/ai/` |
