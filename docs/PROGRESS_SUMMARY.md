# Vir Language - Progress Summary

*Last updated: July 16, 2025*

## Overview

Vir is a minimalist programming language with a self-hosting bootstrap compiler targeting ARM64 macOS.

---

## Phase 1: Bootstrap Compiler ✅ COMPLETE

### 1.1 Core Language
- **Lexer**: Tokenizes Vir source (keywords, operators, strings, numbers, identifiers)
- **Parser**: Recursive descent parser producing AST
- **Code Generation**: Direct ARM64 assembly output
- **Runtime**: C runtime (`runtime.c`) providing builtins

### 1.2 Syntax
```vir
# Variables and expressions
var x = 10
var s = "hello"

# Functions
func add(a, b) then
    return a + b
end

# Control flow
if x > 0 then
    # ...
else
    # ...
end

while x > 0 then
    x = x - 1
end

# Arrays
var arr = []
push(arr, 1)
```

### 1.3 Self-Hosting Achievement
- **Stage 0**: C-based reference compiler (`build/vir`)
- **Stage 1**: `compiler.vri` compiled by Stage 0 → produces ARM64 binary
- **Stage 2**: `compiler.vri` compiled by Stage 1 → **identical to Stage 1**
- **Compiler size**: ~13,425 lines of ARM64 assembly
- **Source**: ~1,900 lines of Vir code

---

## Phase 2: Production Features ✅ COMPLETE

### 2.1 Constant Folding
- Compile-time evaluation of constant expressions
- `2 + 3` → `mov x0, #5` (single instruction)
- Supported: `+`, `-`, `*`, `/`, `%`

### 2.2 Error Reporting
- Line and column tracking during lexing
- Error messages include source location:
  ```
  Error at line 42, col 15: Expected 'then' after if condition
  ```

### 2.3 Include System
- `include "path/to/file.vri"` directive
- Tokens from included files appended to token stream
- Duplicate include prevention
- Relative path resolution from source directory

### 2.4 Module/Import System ✅ NEW
- `import module_name` - Import entire module
- `from module import func1, func2` - Import specific symbols
- `module name` - Declare module name
- `export func_name` - Export function
- `module.func(args)` - Qualified name calls (mangled to `_module_func`)
- Module resolution: searches `stdlib/mod.vri` and `stdlib/vir/mod/mod.vri`

---

## Phase 3: Native Syscalls ✅ COMPLETE

### 3.1 Syscall Primitive
```vir
# Direct syscall invocation
var result = syscall(4, 1, "Hello\n", 6)  # write to stdout
syscall(1, 0)                               # exit(0)
```

### 3.2 macOS ARM64 ABI
- x16: syscall number (with 0x2000000 BSD offset)
- x0-x5: arguments
- svc #0x80: invoke kernel
- x0: return value

### 3.3 sys.vri Standard Library
| Function | Description |
|----------|-------------|
| `sys_exit(code)` | Exit program |
| `sys_write(fd, buf, count)` | Write to file descriptor |
| `sys_read(fd, buf, count)` | Read from file descriptor |
| `sys_open(path, flags, mode)` | Open file |
| `sys_close(fd)` | Close file descriptor |
| `mem_alloc(size)` | Allocate memory via mmap |
| `sys_print(s)` | Print string to stdout |

---

## Phase 4: Standard Library ✅ COMPLETE

Location: `bootstrap/stdlib/`

### 4.1 string.vri (~5KB)
String manipulation functions. Names prefixed to avoid C library conflicts.

| Function | Description |
|----------|-------------|
| `strLen(s)` | Get string length |
| `strCmp(s1, s2)` | Compare strings (-1, 0, 1) |
| `strEq(s1, s2)` | Check equality (0 or 1) |
| `strCopy(s)` | Copy string |
| `strConcat(s1, s2)` | Concatenate strings |
| `charAt(s, idx)` | Get character at index |
| `startsWith(s, prefix)` | Check prefix |
| `endsWith(s, suffix)` | Check suffix |
| `substring(s, start, end)` | Extract substring |
| `indexOf(s, ch)` | Find character |
| `charIsDigit(c)` | Check if digit |
| `charIsAlpha(c)` | Check if letter |
| `charIsSpace(c)` | Check if whitespace |
| `charToUpper(c)` | Convert to uppercase |
| `charToLower(c)` | Convert to lowercase |
| `intToStr(n)` | Integer to string |
| `trim(s)` | Remove whitespace |

### 4.2 math.vri (~5KB)
Mathematical functions.

| Function | Description |
|----------|-------------|
| `abs(n)` | Absolute value |
| `min(a, b)` | Minimum |
| `max(a, b)` | Maximum |
| `clamp(v, lo, hi)` | Clamp to range |
| `sign(n)` | Sign (-1, 0, 1) |
| `pow(base, exp)` | Integer power |
| `fastPow(base, exp)` | Binary exponentiation |
| `sqrt(n)` | Integer square root |
| `gcd(a, b)` | Greatest common divisor |
| `lcm(a, b)` | Least common multiple |
| `isEven(n)` / `isOdd(n)` | Parity check |
| `isPrime(n)` | Primality test |
| `factorial(n)` | Factorial |
| `fib(n)` | Fibonacci number |
| `isPowerOf2(n)` | Power of 2 check |
| `log2(n)` | Log base 2 (floor) |
| `popcount(n)` | Count set bits |

### 4.3 io.vri (~4KB)
Input/output functions.

| Function | Description |
|----------|-------------|
| `print(s)` | Print string |
| `println(s)` | Print with newline |
| `printInt(n)` | Print integer |
| `printlnInt(n)` | Print int + newline |
| `newline()` | Print newline |
| `printChar(c)` | Print character |
| `printSpaces(n)` | Print n spaces |
| `printPadded(n, w)` | Right-aligned number |
| `printZeroPadded(n, w)` | Zero-padded number |
| `printHex(n)` | Print hexadecimal |
| `printBin(n)` | Print binary |
| `readFile(path)` | Read file contents |
| `writeFile(path, s)` | Write to file |
| `fileExists(path)` | Check file exists |

### 4.4 array.vri (~6KB)
Array manipulation functions.

| Function | Description |
|----------|-------------|
| `newArray()` | Create empty array |
| `append(arr, val)` | Append element |
| `first(arr)` | First element |
| `last(arr, len)` | Last element |
| `contains(arr, val, len)` | Check membership |
| `find(arr, val, len)` | Find index |
| `count(arr, val, len)` | Count occurrences |
| `sum(arr, len)` | Sum of elements |
| `product(arr, len)` | Product of elements |
| `minArr(arr, len)` | Minimum element |
| `maxArr(arr, len)` | Maximum element |
| `reverse(arr, len)` | Reverse in-place |
| `bubbleSort(arr, len)` | Sort array |
| `binarySearch(arr, len, val)` | Binary search |
| `isSorted(arr, len)` | Check sorted |

---

## Build System

### Compile a Vir program
```bash
cd Vir/core
build/vir run bootstrap/compiler.vri myprogram.vri > output.s
as -o output.o output.s
ld -o myprogram output.o /tmp/runtime.o -lSystem \
   -syslibroot $(xcrun --show-sdk-path) -arch arm64
./myprogram
```

### Self-host the compiler
```bash
# Compile compiler with itself
build/vir run bootstrap/compiler.vri bootstrap/compiler.vri > /tmp/stage1.s
as -o /tmp/stage1.o /tmp/stage1.s
ld -o /tmp/stage1 /tmp/stage1.o /tmp/runtime.o -lSystem \
   -syslibroot $(xcrun --show-sdk-path) -arch arm64

# Stage 2 (stage1 compiling compiler.vri)
/tmp/stage1 bootstrap/compiler.vri > /tmp/stage2.s
diff /tmp/stage1.s /tmp/stage2.s  # Should be identical!
```

---

## Phase I: Advanced Optimizations ✅ COMPLETE

### I.1 Common Subexpression Elimination (CSE)
- Hash-based value numbering with commutative awareness (ADD, MUL)
- Key: `(opcode, operand_key1, operand_key2)` → cached destination VReg
- Duplicate expressions replaced with `Q_MOVE` (register copy)
- Cache invalidation at control-flow boundaries and VReg redefinitions
- Commutative ops: sorted operand keys so `ADD v1, v2` == `ADD v2, v1`

### I.2 Loop Unrolling
- Pattern-based detection: `Q_LABEL → body → backward_jump`
- Configurable unroll factor via `cost_model._unroll_factor` (default 4)
- MAX_LOOP_BODY = 32 instructions (large loops skipped)
- Reduces branch overhead by duplicating loop body N times

### I.3 Linear Scan Register Allocator
- Poletto & Sarkar 1999 algorithm replacing trivial sequential allocation
- Separate general-purpose and vector register pools
- ARM64: 16 GP (X0-X15) + 8 VEC (V0-V7) = 24 physical registers
- x86_64: 14 GP (RAX-R15) + 8 VEC (XMM0-XMM7) = 22 physical registers
- Spill strategy: evict the interval ending furthest
- Automatic spill/reload code insertion via `rewrite()`

### I.4 Optimizer Pipeline
```
copy_propagate → constant_fold → CSE → strength_reduce → loop_unroll → vectorize → dead_code_eliminate
```

**Tests:** 25 new tests (323 Python total + 89 C native = 412 total)

---

## Phase J: Core Improvements ✅ COMPLETE

### J.1 Arena Allocator
- Region-based bump allocator replacing per-object GC need
- Pure Vir implementation (`core/bootstrap/stdlib/arena.vri`)
- `arena_create(capacity)` → mmap-backed page-aligned allocation (16KB pages)
- `arena_alloc(arena, size)` → 8-byte aligned bump allocation, O(1)
- `arena_reset(arena)` → free all allocations by resetting pointer, O(1)
- `arena_destroy(arena)` → munmap back to OS
- 32-byte header: base, ptr, end_ptr, capacity

### J.2 Floating-Point Support
- 12 new FP scalar opcodes: FLOAD, FSTORE, FMOVE, FADD, FSUB, FMUL, FDIV, FCMP_EQ/LT/GT, FCVT_I2F, FCVT_F2I
- ARM64: D-register (double) helpers using NEON encoding (D0-D7)
- x86_64: SSE2 scalar-double helpers (XMM0-XMM7)
- FP scalars share vector register pool (ARM64 D-regs overlap V-regs)
- Full codegen support in all 4 paths (safe/fast × ARM64/x86_64)

### J.3 Separate Compilation
- `MachOEmitter` class producing valid Mach-O 64-bit relocatable objects (.o)
- Complete structure: MH_MAGIC_64 header, LC_SEGMENT_64, LC_SYMTAB, LC_DYSYMTAB
- Symbol table with nlist entries, string table, relocation records
- Supports both ARM64 and x86_64 CPU types
- `compile_module_to_object()` convenience: QModule → .o file

### J.4 Live Range Splitting
- **Next-use-distance spill heuristic**: replaces "furthest end" with "furthest next use"
- `LiveInterval.use_positions` tracks all def/use positions per VReg
- `next_use_after(pos)` method for O(n) next-use queries
- **Cached-reload optimization** in `rewrite()`: tracks recently-loaded spilled VRegs, skips redundant Q_LOAD instructions
- Conservative cache flush at control-flow boundaries

### J.5 Epilogue Loop
- Loop unrolling now emits a **remainder loop** after the unrolled body
- Pattern: `[unrolled body × factor] + [epilogue loop for N%factor]`
- Epilogue has unique label (`_epi_<loop>_<id>`) and its own back-edge
- `_retarget_label()` helper for re-pointing jump targets

### J.6 Function Inlining (IPO)
- Inter-procedural optimization: inline small callees at call sites
- Threshold: body ≤ 20 instructions, non-recursive
- VReg remapping with per-site offset to avoid register clashes
- Label renaming with `_inl<tag>` suffix
- Q_RET → Q_MOVE mapping for return values

### J.7 LICM (Loop-Invariant Code Motion)
- Hoists pure instructions whose operands are all defined outside the loop
- Moves to preheader position (before the loop label)
- Handles FP opcodes (FADD, FSUB, FMUL, FDIV) in addition to integer ops
- Iterative hoisting: hoisted defs removed from loop_defs set enabling further hoists

### J.8 Optional Static Typing
- Gradual typing: annotations optional, checked when present
- Type system: `int`, `float`, `str`, `bool` with implicit int→float promotion
- AST extensions: `VarDeclNode.type_ann`, `FuncDefNode.param_types`, `FuncDefNode.return_type`
- `TypeChecker` class: single-pass checker with scope tracking
- Detects: type mismatches, unknown types, argument type errors, string op violations

### J.9 Optimizer Pipeline (updated)
```
copy_propagate → constant_fold → CSE → inline_functions → strength_reduce → LICM → loop_unroll → vectorize → dead_code_eliminate
```

**Tests:** 36 new tests (359 Python total + 89 C native = 448 total)

---

## Phase 7: Core Optimizations & File Format Ecosystem ✅ COMPLETE

### 7.1 Bounds Check Elimination (BCE)
- Range Analysis on loop induction variables
- Proves array accesses within bounds → eliminates Q_BOUNDS_CHECK
- `BoundsCheckEliminator` in `src/ir/optimizer/bounds_check_elim.py`
- Supports counted loops with `[0, limit)` range inference
- Performance: **~1 µs** per function analysis

### 7.2 Escape Analysis + Stack Promotion
- 3-state escape lattice: `NoEscape`, `ArgEscape`, `GlobalEscape`
- Tracks Q_ALLOC sites and their uses through Q_STORE, Q_CALL, Q_RET
- Promotes `NoEscape` allocations to Q_STACK_ALLOC (zero-cost stack alloc)
- `EscapeAnalyzer` in `src/ir/optimizer/escape_analysis.py`
- Performance: **~2.5 µs per allocation site**

### 7.3 Deterministic Free
- Automatic Q_FREE insertion at scope exits
- Computes allocation lifetimes (first use → last use)
- Inserts frees before Q_RET and at function endings
- `DeterministicFree` in `src/ir/optimizer/deterministic_free.py`
- Eliminates need for GC in most programs

### 7.4 New Q-IR Opcodes
- `Q_BOUNDS_CHECK` — runtime bounds validation (eliminated by BCE)
- `Q_ALLOC` / `Q_FREE` — explicit heap allocation/deallocation
- `Q_STACK_ALLOC` — stack allocation (promoted from Q_ALLOC by escape analysis)

### 7.5 File Extension Ecosystem
- `.vri` — Vir source files (Vir Intermediate) — renamed from `.vir`
- `.sri` — Serialized Runtime Image (compiled binary)
- `.vsib` — Vir Static/Import Binary (library package)

### 7.6 SRI Binary Format
- Magic: `SRI\x01`, little-endian, supports ARM64 & x86_64
- Sections: header (88 bytes) + code + data + symbol table + string table + relocation table
- Flags: debug info, PIC, BCE metadata, escape info
- `SRIBinary` class in `src/backend/formats.py` with read/write serialization

### 7.7 VSIB Library Format
- Magic: `VSIB`, contains multiple SRI modules + export table + metadata
- Supports auto-export of all function symbols per module
- Metadata: build timestamp, compiler version, target arch, optimization level
- `VSIBLibrary` class in `src/backend/formats.py`

### 7.8 Codegen Integration
- `CodeGenerator.emit_sri()` — generates SRI binary from QModule
- `compile_module_to_sri()` — one-call compilation pipeline
- CLI: `--emit-sri PATH` and `--emit-vsib PATH` flags

### 7.9 Optimizer Pipeline (11 passes)
```
copy_propagate → constant_fold → CSE → inline_functions → strength_reduce →
LICM → loop_unroll → vectorize → dead_code_eliminate →
bounds_check_elim → escape_analysis → deterministic_free
```

### 7.10 Performance Benchmarks (Phase 7)
| Benchmark | Mean | Median | Min |
|-----------|------|--------|-----|
| BCE Range Analysis | 1.07 µs | 1.04 µs | 1.00 µs |
| Escape Analysis (100 allocs) | 248.74 µs | 217.44 µs | 205.12 µs |
| Deterministic Free (100 allocs) | 221.34 µs | 185.35 µs | 177.42 µs |
| Full Optimizer (11 passes, 10×200) | 447.48 µs | 411.69 µs | 380.58 µs |
| Codegen + SIMD Vectorizer | 70.82 µs | 69.52 µs | 66.21 µs |
| SRI Binary Emission | 59.06 µs | 54.25 µs | 46.46 µs |

**Tests:** 42 new Phase 7 tests (656 total)

---

## Known Limitations

1. ~~No garbage collection~~ → Arena allocator + Deterministic Free available
2. ~~Integer only~~ → Floating-point support added (J.2)
3. ~~Single-file compilation~~ → Mach-O .o emitter + SRI binary format available
4. **C runtime dependency**: Requires `runtime.c` for builtins
5. ~~No escape analysis~~ → Escape Analysis + Stack Promotion (Phase 7)

---

## Future Work

- [ ] Pattern matching
- [ ] Closures / first-class functions
- [ ] Cross-platform support (x86_64, Linux)
- [ ] REPL / interpreter mode
- [ ] Package manager
- [ ] Link-time optimization (LTO with .o files)
- [x] ~~Escape analysis for stack allocation~~ → Phase 7 complete
- [ ] VSIB library linker (link multiple .vsib → executable)
- [ ] Stdlib build system (compile .vri → .sri → .vsib)

---

## Statistics

| Metric | Value |
|--------|-------|
| Compiler source | ~1,800 lines |
| Generated assembly | ~11,094 lines |
| stdlib total | ~20KB |
| Runtime (C) | ~500 lines |
| Self-hosting | ✅ stage1 = stage2 |
| Optimizer passes | 11 (copy prop, const fold, CSE, inlining, strength reduce, LICM, loop unroll, SIMD vectorize, DCE, BCE, escape analysis, det. free) |
| Register allocator | Linear Scan + next-use heuristic (ARM64: 24 regs, x86_64: 22 regs) |
| File formats | .vri (source), .sri (binary), .vsib (library) |
| Python tests | 567 |
| C native tests | 89 |
| Total tests | 656 |
