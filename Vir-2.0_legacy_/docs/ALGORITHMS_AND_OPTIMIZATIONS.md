# Vir Compiler & Runtime Algorithms Specification

This document provides a comprehensive technical overview of the key algorithms, optimization passes, memory architectures, and formal computational models employed in the **Vir Programming Language (v2.0)** ecosystem.

---

## 1. Register Allocation: Chaitin-Briggs Graph Coloring & Iterated Coalescing

Vir uses a native graph-coloring register allocator based on the **Chaitin-Briggs** formulation augmented with **George-Appel Iterated Register Coalescing (IRC)**.

### 1.1. Interference Graph Construction
1. **Liveness Analysis:** Computes Live-In and Live-Out bitsets for each basic block using backwards dataflow equations:
   $$\text{LiveIn}(B) = \text{Use}(B) \cup (\text{LiveOut}(B) \setminus \text{Def}(B))$$
   $$\text{LiveOut}(B) = \bigcup_{S \in \text{Succ}(B)} \text{LiveIn}(S)$$
2. **Interference Graph:** An undirected graph $G = (V, E)$ where vertices $V$ represent virtual registers and edges $E$ connect variables that are concurrently live.

### 1.2. Graph Simplification & George-Appel Coalescing
- **Degree $< K$ (Simplify):** Removes non-interfering nodes with degree $< K$ (where $K=31$ general-purpose ARM64 registers, reserving frame pointer and link register).
- **Conservative Coalescing (George's Criterion):** Merges virtual registers $u$ and $v$ if every neighbor $t$ of $u$ either already interferes with $v$ or has low degree ($\text{deg}(t) < K$).
- **Optimistic Spilling (Briggs):** When no node has degree $< K$, marks the lowest-cost candidate for potential spill, pushes it onto the color stack, and attempts coloring during graph rebuild.

```
       [ Live Range Analysis ]
                 │
                 ▼
     [ Interference Graph G(V,E) ] ◄──────────────┐
                 │                                │
                 ▼                                │ (Spill Insertion)
     [ George-Appel Coalescing ]                  │
                 │                                │
                 ▼                                │
     [ Briggs Color Assignment ] ──────► [ Actual Spills? ] ──► [ Machine Code ]
```

---

## 2. Multi-Pass IR Optimizer Pipeline (26 Core Optimization Passes)

The Vir optimizer operates over High-Level IR (HIR), Quadruple Mid-Level IR (MIR with 82 canonical QOps), and Low-Level IR (LIR).

### Tier 1: Local & Algebraic Optimizations
1. **Constant Folding & Propagation:** Evaluates static arithmetic, bitwise shifts, and boolean expressions at compile time.
2. **Strength Reduction:** Replaces expensive operations (multiplication/division by power of 2) with hardware bit shifts (`x * 8 -> x << 3`).
3. **Common Subexpression Elimination (CSE):** Eliminates redundant expressions within basic blocks using value hashing.
4. **Dead Code Elimination (DCE):** Iteratively removes unused assignments and unreached blocks via post-dominator liveness sweeps.

### Tier 2: Loop & Polyhedral Optimizations
5. **Loop Invariant Code Motion (LICM):** Hoists loop-invariant calculations into preheaders.
6. **Induction Variable Strength Reduction (IVSR):** Converts `i * Stride` multiplications in loop bodies to linear additions `acc += Stride`.
7. **Loop Unrolling Engine:** 2-way and 4-way unrolling with scalar epilogues for residual iterations.
8. **Symbolic Closed-Form Collapse (Gauss Transform):** Detects arithmetic progression loops $\sum_{i=1}^N i$ and collapses them into $O(1)$ analytical closed-form:
   $$S = \frac{N(N + 1)}{2}$$
9. **Polyhedral Loop Tiling:** Blocks nested 2D/3D matrix traversals to fit within L1 (32KB) and L2 (128KB) hardware cache lines.

### Tier 3: Memory, Vectorization & Concurrency
10. **SIMD Auto-Vectorization (NEON 128-bit & AVX2 256-bit):** Emits 4x32-bit and 16x8-bit parallel lane operations with vector reductions.
11. **Tail-Call Optimization (TCO):** Transforms direct recursive calls into immediate unconditional jumps (`B / JMP`), guaranteeing $O(1)$ stack space.
12. **Bounds Check Elimination (BCE):** Eliminates redundant `Q_BOUNDS_CHECK` when iteration bounds are proven within allocation limits.
13. **Escape Analysis & Stack/Arena Promotion:** Promotes non-escaping heap allocations to stack frames or linear memory arenas.
14. **Bacon-Rajan Cycle Collection:** 3-color trial deletion algorithm detecting cyclic references in automatic reference-counted objects.

### Tier 4-6: Interprocedural, SSA & Link-Time Optimizations (LTO)
15. **Inter-procedural Function Inlining (IPA):** Inlines leaf functions ($\le 6$ instructions) directly at call sites.
16. **Global Value Numbering (GVN):** Assigns canonical value numbers over the Dominator Tree with algebraic commutativity normalization ($VN(a + b) == VN(b + a)$).
17. **Partial Redundancy Elimination (PRE / Lazy Code Motion):** Eliminates partially redundant computations via Knoop-Ruthing-Steffen equations.
18. **Superword-Level Parallelism (SLP):** Packs isomorphic adjacent scalar statements into 128-bit SIMD instructions.
19. **Shrink-Wrapping:** Moves callee-saved register push/pop instructions away from fast early-exit paths into compute-heavy branches.
20. **Sparse Conditional Constant Propagation (SCCP):** Simultaneously propagates lattice constants and discovers executable CFG edges (Wegman & Zadeck algorithm).
21. **Scalar Replacement of Aggregates (SROA):** Deconstructs small structs into independent virtual registers, eliminating all memory traffic.
22. **CHA Devirtualization:** Resolves monomorphic vtable calls into direct `BL` branches.

---

## 3. Pattern Matching Engine: Virgex (VPS) & Thompson NFA

Vir replaces standard regex engines with **Virgex (Vir Pattern Syntax - VPS)**, executing patterns in deterministic linear time $O(N \cdot M)$.

### 3.1. Thompson NFA Multi-State Simulation
- Converts pattern AST into a non-deterministic finite automaton (NFA).
- Tracks active states using twin sparse sets (`curr_states` and `next_states`), eliminating backtracking vulnerabilities (ReDoS immunity).
- Supported operations:
  * Character classes and range sets (`[0-9]`, `[a-zA-Z]`, `\d`, `\w`)
  * Repetition quantifiers (`*`, `+`, `?`, `{m,n}`)
  * Concatenation and Alternation (`|`)
  * Word boundary and anchor assertions (`^`, `$`, `\b`)

---

## 4. Package Dependency Management: Topological Sort DAG Resolver

The **Viron Package Manager** models package dependencies as a Directed Acyclic Graph (DAG) $G = (V, E)$, where vertices $V$ represent packages and directed edges $E = (u, v)$ denote that package $u$ depends on $v$.

### 4.1. Depth-First Search (DFS) Topological Sort
- **3-Color Node Marking:**
  * `0 (White / Unvisited)`: Unexplored package.
  * `1 (Gray / Visiting)`: Currently in active recursion stack; if encountered again, **a dependency cycle is detected**.
  * `2 (Black / Resolved)`: Fully resolved; appended to deterministic build order.
- **Complexity:** Time $O(|V| + |E|)$, Space $O(|V|)$.

---

## 5. Machine Code Generation & Linkerless Emission

Vir directly generates native machine code and executable headers without invoking external linkers (`ld`, `lld`, `gold`):

1. **macOS Mach-O 64-bit (`macho.vri`):**
   - Directly constructs `mach_header_64` (`MH_MAGIC_64`), `LC_SEGMENT_64` (`__PAGEZERO`, `__TEXT`), `LC_UNIXTHREAD` with initial ARM64 register state (`PC = _start`, `SP = aligned_stack`).
2. **Linux ELF 64-bit (`elf.vri`):**
   - Constructs `Elf64_Ehdr`, `Elf64_Phdr` (`PT_LOAD` segments with `PF_R | PF_X` permissions), and sets entry virtual address `0x400000`.
3. **Windows PE32+ (`codegen_windows.vri`):**
   - Constructs DOS Header, PE Signature, COFF Header, Optional Header 64-bit, and `.text` section adhering to Microsoft x64 Calling Convention and 32-byte shadow space.
4. **WebAssembly MVP Binary Module (`codegen_wasm.vri`):**
   - Emits WASM binary format (`\x00asm\x01\x00\x00\x00`), Type Section, Function Section, Export Section, and Code Section with LEB128 variable-length integer encoding.
