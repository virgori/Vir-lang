# VIR Q-IR Opcode Map — Bản đồ Gen của VIR

> **Mục đích:** Tài liệu hóa chi tiết TẤT CẢ Q-IR opcodes.
> **Ngày tạo:** 22/03/2026
> **Phiên bản:** 2.0 — Updated 2026-04-11
>
> ⚠️ **AUDIT CORRECTION (02/04/2026, updated 11/04/2026):**
> - Bản gốc claim "148 opcodes" — **SAI**. Thực tế C engine có **87 entries** trong `q_ir.h`.
> - Vir self-hosting compiler (virc) có **82 canonical QOp opcodes** (ir_optimizer.vri) + Store=200 alias (codegen.vri).
> - Nhiều opcodes trong tài liệu này (Float, Math, Network, Map) **CHƯA ĐƯỢC IMPLEMENT trong C engine** — nhưng một số đã có trong virc (FAdd–FCvtF2I).
> - Opcode numbering giữa C engine và Vir compiler **KHÔNG KHỚP** — đây là design (Vir compiler sinh ARM64 trực tiếp, không dùng C VM opcodes).
> - Xem `core/include/q_ir.h` (C) và `stdlib/vir/compiler/ir_optimizer.vri` QOp enum (Vir) cho opcodes thực tế.
>
> **VIRC CANONICAL QOp ENUM (82 opcodes, 2026-04-11):**
>
> | Range | Category | Opcodes |
> |-------|----------|---------|
> | 0–12 | Arithmetic/Logic | Nop, Load, Move, Add, Sub, Mul, Div, Mod, And, Or, Xor, Shl, Shr |
> | 20–25 | Comparison | CmpEq, CmpNe, CmpGt, CmpLt, CmpGe, CmpLe |
> | 30–37 | Control Flow | Jump, JumpIfNot, Label, Call, CallFunc, Ret, JumpIf, Halt |
> | 40–42 | I/O | Print, PrintStr, Input |
> | 50–55 | Memory | Alloc, Free, LoadByte, StoreByte, LoadWord, StoreWord |
> | 60–64 | Array | ArrNew, ArrPush, ArrGet, ArrSet, ArrLen |
> | 70–75 | String | StrLenOp, StrGet, StrCat, StrEq, IToStr, StrToI |
> | 80–84 | File I/O | FileOpen, FileRead, FileWrite, FileClose, FileWriteByte |
> | 90–98 | System | Exit, PatchPoint, LoadGlobal, StoreGlobal, GetArg, ArgCount, SetArg, LoadFuncAddr, LoadString |
> | 100–102 | Fused | FusedMulAdd, FusedBiasRelu, FusedBiasGelu |
> | 110–121 | SIMD | VLoad, VStore, VAdd, VSub, VMul, VFma, VDiv, VMin, VMax, VReduce, VSplat, VPerm |
> | 130–135 | Float | FAdd, FSub, FMul, FDiv, FCvtI2F, FCvtF2I |

---

## Mục lục

1. [Arithmetic Opcodes](#1-arithmetic-opcodes)
2. [Float Arithmetic](#2-float-arithmetic)
3. [Math Functions](#3-math-functions)
4. [Comparison Opcodes](#4-comparison-opcodes)
5. [Bitwise Opcodes](#5-bitwise-opcodes)
6. [Control Flow](#6-control-flow)
7. [Memory Operations](#7-memory-operations)
8. [String Operations](#8-string-operations)
9. [Array Operations](#9-array-operations)
10. [Map Operations](#10-map-operations)
11. [Entity/Struct Operations](#11-entitystruct-operations)
12. [File I/O](#12-file-io)
13. [Network Operations](#13-network-operations)
14. [SIMD/Vector Operations](#14-simdvector-operations)
15. [System Calls](#15-system-calls)
16. [Task/Process Operations](#16-taskprocess-operations)
17. [Exception Handling](#17-exception-handling)
18. [JIT/Patch Operations](#18-jitpatch-operations)
19. [Miscellaneous](#19-miscellaneous)

---

## 1. Arithmetic Opcodes

### Q_ADD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ADD dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 + src2` |
| **Side-effects** | None |
| **Flags** | None |
| **Register Usage** | dest = src1 + src2 (3-address) |
| **Notes** | Integer addition, wraps on overflow |

### Q_SUB
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SUB dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 - src2` |
| **Side-effects** | None |
| **Flags** | None |
| **Register Usage** | dest = src1 - src2 (3-address) |
| **Notes** | Integer subtraction |

### Q_MUL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MUL dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 * src2` |
| **Side-effects** | None |
| **Flags** | None |
| **Register Usage** | dest = src1 * src2 (3-address) |
| **Notes** | Signed multiplication, low 64 bits |

### Q_DIV
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_DIV dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 / src2` |
| **Side-effects** | None |
| **Flags** | None |
| **Register Usage** | dest = src1 / src2 (3-address) |
| **Notes** | Signed division, truncates toward zero. **TRAP** if src2 == 0 |

### Q_MOD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MOD dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 % src2` |
| **Side-effects** | None |
| **Flags** | None |
| **Register Usage** | dest = src1 % src2 (3-address) |
| **Notes** | Signed modulo, follows C semantics: `-17 % 5 = -2` |

### Q_PERCENT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PERCENT dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 % src2` |
| **Side-effects** | None |
| **Notes** | Alias for Q_MOD in some contexts |

### Q_NEG
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NEG dest, src` |
| **Input** | `src: i64` |
| **Output** | `dest: i64 = -src` |
| **Side-effects** | None |
| **Register Usage** | dest = -src (2-address) |
| **Notes** | Two's complement negation |

---

## 2. Float Arithmetic

### Q_FADD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FADD dest, src1, src2` |
| **Input** | `src1: f64`, `src2: f64` |
| **Output** | `dest: f64 = src1 + src2` |
| **Side-effects** | None |
| **Register Usage** | FP register (XMM on x86, D/Q on ARM) |
| **Notes** | IEEE 754 double-precision addition |

### Q_FSUB
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FSUB dest, src1, src2` |
| **Input** | `src1: f64`, `src2: f64` |
| **Output** | `dest: f64 = src1 - src2` |
| **Side-effects** | None |
| **Register Usage** | FP register |
| **Notes** | IEEE 754 double-precision subtraction |

### Q_FMUL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FMUL dest, src1, src2` |
| **Input** | `src1: f64`, `src2: f64` |
| **Output** | `dest: f64 = src1 * src2` |
| **Side-effects** | None |
| **Register Usage** | FP register |
| **Notes** | IEEE 754 double-precision multiplication |

### Q_FDIV
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FDIV dest, src1, src2` |
| **Input** | `src1: f64`, `src2: f64` |
| **Output** | `dest: f64 = src1 / src2` |
| **Side-effects** | None |
| **Register Usage** | FP register |
| **Notes** | IEEE 754 division, produces ±Inf or NaN on special cases |

---

## 3. Math Functions

### Q_SIN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SIN dest, src` |
| **Input** | `src: f64` (radians) |
| **Output** | `dest: f64 = sin(src)` |
| **Side-effects** | None |
| **Implementation** | Calls libm `sin()` or uses Taylor series |

### Q_COS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_COS dest, src` |
| **Input** | `src: f64` (radians) |
| **Output** | `dest: f64 = cos(src)` |
| **Side-effects** | None |
| **Implementation** | Calls libm `cos()` or uses Taylor series |

### Q_TAN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TAN dest, src` |
| **Input** | `src: f64` (radians) |
| **Output** | `dest: f64 = tan(src)` |
| **Side-effects** | None |
| **Implementation** | Calls libm `tan()` |

### Q_SQRT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SQRT dest, src` |
| **Input** | `src: f64` (non-negative) |
| **Output** | `dest: f64 = sqrt(src)` |
| **Side-effects** | None |
| **Implementation** | x86: `SQRTSD`, ARM64: `FSQRT` |
| **Notes** | Returns NaN if src < 0 |

### Q_ABS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ABS dest, src` |
| **Input** | `src: i64` |
| **Output** | `dest: i64 = abs(src)` |
| **Side-effects** | None |
| **Notes** | Integer absolute value |

### Q_POW
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_POW dest, base, exp` |
| **Input** | `base: f64`, `exp: f64` |
| **Output** | `dest: f64 = pow(base, exp)` |
| **Side-effects** | None |
| **Implementation** | Calls libm `pow()` |

---

## 4. Comparison Opcodes

### Q_CMP_EQ
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_EQ dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 == src2) ? 1 : 0` |
| **Side-effects** | None |
| **Notes** | Boolean comparison, result is 0 or 1 |

### Q_CMP_NE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_NE dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 != src2) ? 1 : 0` |

### Q_CMP_GT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_GT dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 > src2) ? 1 : 0` |
| **Notes** | Signed comparison |

### Q_CMP_LT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_LT dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 < src2) ? 1 : 0` |
| **Notes** | Signed comparison |

### Q_CMP_GE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_GE dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 >= src2) ? 1 : 0` |

### Q_CMP_LE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CMP_LE dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = (src1 <= src2) ? 1 : 0` |

---

## 5. Bitwise Opcodes

### Q_AND
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_AND dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 & src2` |
| **Notes** | Bitwise AND |

### Q_OR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_OR dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 | src2` |
| **Notes** | Bitwise OR |

### Q_XOR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_XOR dest, src1, src2` |
| **Input** | `src1: i64`, `src2: i64` |
| **Output** | `dest: i64 = src1 ^ src2` |
| **Notes** | Bitwise XOR |

### Q_NOT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NOT dest, src` |
| **Input** | `src: i64` |
| **Output** | `dest: i64 = ~src` |
| **Notes** | Bitwise NOT (one's complement) |

### Q_SHL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SHL dest, src, amount` |
| **Input** | `src: i64`, `amount: i64` |
| **Output** | `dest: i64 = src << amount` |
| **Notes** | Logical left shift |

### Q_SHR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SHR dest, src, amount` |
| **Input** | `src: i64`, `amount: i64` |
| **Output** | `dest: i64 = src >> amount` |
| **Notes** | Arithmetic right shift (sign-extended) |

---

## 6. Control Flow

### Q_NOP
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NOP` |
| **Input** | None |
| **Output** | None |
| **Side-effects** | None |
| **Notes** | No operation |

### Q_LABEL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_LABEL label_id` |
| **Input** | `label_id: u32` |
| **Output** | None |
| **Side-effects** | Defines jump target |
| **Notes** | Pseudo-instruction, resolved at assembly |

### Q_JUMP
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_JUMP label_id` |
| **Input** | `label_id: u32` |
| **Output** | None |
| **Side-effects** | Unconditional branch |
| **Implementation** | `JMP` (x86), `B` (ARM64) |

### Q_JUMP_IF
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_JUMP_IF cond, label_id` |
| **Input** | `cond: i64`, `label_id: u32` |
| **Output** | None |
| **Side-effects** | Jump if cond != 0 |
| **Implementation** | `TEST + JNZ` (x86), `CBNZ` (ARM64) |

### Q_JUMP_IF_NOT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_JUMP_IF_NOT cond, label_id` |
| **Input** | `cond: i64`, `label_id: u32` |
| **Output** | None |
| **Side-effects** | Jump if cond == 0 |
| **Implementation** | `TEST + JZ` (x86), `CBZ` (ARM64) |

### Q_CALL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CALL func_addr, arg_count` |
| **Input** | `func_addr: ptr`, `arg_count: u32` |
| **Output** | Return value in %rax (x86) or X0 (ARM64) |
| **Side-effects** | Pushes return address, transfers control |
| **Implementation** | `CALL` (x86), `BL` (ARM64) |

### Q_CALL_FUNC
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CALL_FUNC func_idx, arg_count` |
| **Input** | `func_idx: u32` (function table index) |
| **Output** | Return value |
| **Side-effects** | Indirect call through function table |

### Q_RET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_RET` or `Q_RET value` |
| **Input** | `value: i64` (optional) |
| **Output** | None |
| **Side-effects** | Returns to caller |
| **Implementation** | `RET` (x86), `RET` (ARM64) |

### Q_HALT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_HALT` |
| **Input** | None |
| **Output** | None |
| **Side-effects** | Terminates execution |

### Q_EXIT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_EXIT code` |
| **Input** | `code: i64` |
| **Output** | None |
| **Side-effects** | Exits process with code |
| **Implementation** | Calls `exit()` or `SYS_EXIT` |

---

## 7. Memory Operations

### Q_LOAD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_LOAD dest, src` |
| **Input** | `src: ptr` or immediate |
| **Output** | `dest: i64` |
| **Side-effects** | Memory read |
| **Implementation** | `MOV dest, [src]` |

### Q_STORE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STORE addr, value` |
| **Input** | `addr: ptr`, `value: i64` |
| **Output** | None |
| **Side-effects** | Memory write |
| **Implementation** | `MOV [addr], value` |

### Q_MOVE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MOVE dest, src` |
| **Input** | `src: i64` |
| **Output** | `dest: i64 = src` |
| **Side-effects** | None |
| **Notes** | Register-to-register copy |

### Q_LOAD_BYTE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_LOAD_BYTE dest, addr` |
| **Input** | `addr: ptr` |
| **Output** | `dest: i64` (zero-extended byte) |
| **Implementation** | `MOVZX dest, BYTE PTR [addr]` |

### Q_STORE_BYTE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STORE_BYTE addr, value` |
| **Input** | `addr: ptr`, `value: i64` (low byte used) |
| **Output** | None |
| **Implementation** | `MOV BYTE PTR [addr], value` |

### Q_LOAD_WORD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_LOAD_WORD dest, addr` |
| **Input** | `addr: ptr` |
| **Output** | `dest: i64` (zero-extended 16-bit) |

### Q_STORE_WORD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STORE_WORD addr, value` |
| **Input** | `addr: ptr`, `value: i64` |
| **Output** | None |

### Q_LOAD_GLOBAL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_LOAD_GLOBAL dest, global_idx` |
| **Input** | `global_idx: u32` |
| **Output** | `dest: i64` |
| **Notes** | Loads from global variable table |

### Q_STORE_GLOBAL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STORE_GLOBAL global_idx, value` |
| **Input** | `global_idx: u32`, `value: i64` |
| **Output** | None |
| **Notes** | Stores to global variable table |

### Q_ALLOC
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ALLOC dest, size` |
| **Input** | `size: i64` (bytes) |
| **Output** | `dest: ptr` |
| **Side-effects** | Heap allocation |
| **Implementation** | Calls `malloc()` or arena allocator |

### Q_FREE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FREE ptr` |
| **Input** | `ptr: ptr` |
| **Output** | None |
| **Side-effects** | Heap deallocation |
| **Implementation** | Calls `free()` or decrements RC |

### Q_MEM_LOAD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MEM_LOAD dest, addr` |
| **Input** | `addr: ptr` |
| **Output** | `dest: i64` |
| **Notes** | Direct memory load (64-bit) |

### Q_MEM_STORE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MEM_STORE addr, value` |
| **Input** | `addr: ptr`, `value: i64` |
| **Output** | None |
| **Notes** | Direct memory store (64-bit) |

### Q_MEM_LOAD8
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MEM_LOAD8 dest, addr` |
| **Input** | `addr: ptr` |
| **Output** | `dest: i64` (zero-extended) |
| **Notes** | Direct memory load (8-bit) |

### Q_MEM_STORE8
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MEM_STORE8 addr, value` |
| **Input** | `addr: ptr`, `value: i64` |
| **Output** | None |
| **Notes** | Direct memory store (8-bit) |

---

## 8. String Operations

### Q_STR_LEN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_LEN dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: i64` (length in bytes) |

### Q_STR_GET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_GET dest, str, idx` |
| **Input** | `str: String`, `idx: i64` |
| **Output** | `dest: i64` (char code) |
| **Notes** | Returns byte at index |

### Q_STR_CAT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_CAT dest, str1, str2` |
| **Input** | `str1: String`, `str2: String` |
| **Output** | `dest: String` (concatenated) |
| **Side-effects** | Allocates new string |

### Q_STR_EQ
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_EQ dest, str1, str2` |
| **Input** | `str1: String`, `str2: String` |
| **Output** | `dest: i64 = 1 if equal, 0 otherwise` |

### Q_STR_SLICE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_SLICE dest, str, start, end` |
| **Input** | `str: String`, `start: i64`, `end: i64` |
| **Output** | `dest: String` (substring) |
| **Side-effects** | Allocates new string |

### Q_STR_CONTAINS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_CONTAINS dest, haystack, needle` |
| **Input** | `haystack: String`, `needle: String` |
| **Output** | `dest: i64 = 1 if found, 0 otherwise` |

### Q_STR_STARTS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_STARTS dest, str, prefix` |
| **Input** | `str: String`, `prefix: String` |
| **Output** | `dest: i64 = 1 if starts with prefix` |

### Q_STR_FIND
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_FIND dest, haystack, needle` |
| **Input** | `haystack: String`, `needle: String` |
| **Output** | `dest: i64` (index or -1 if not found) |

### Q_STR_UPPER
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_UPPER dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: String` (uppercased) |

### Q_STR_LOWER
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_LOWER dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: String` (lowercased) |

### Q_STR_TRIM
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_TRIM dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: String` (whitespace trimmed) |

### Q_STR_REPLACE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_REPLACE dest, str, old, new` |
| **Input** | `str: String`, `old: String`, `new: String` |
| **Output** | `dest: String` (replaced) |

### Q_STR_SPLIT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_SPLIT dest, str, delim` |
| **Input** | `str: String`, `delim: String` |
| **Output** | `dest: Array[String]` |

### Q_STR_ALLOC
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_ALLOC dest, size` |
| **Input** | `size: i64` |
| **Output** | `dest: String` (allocated but empty) |

### Q_SPRINTF
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SPRINTF dest, format, ...args` |
| **Input** | `format: String`, variadic args |
| **Output** | `dest: String` (formatted) |

### Q_STR_TO_I
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_TO_I dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: i64` (parsed integer) |

### Q_STR_TO_F
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_STR_TO_F dest, str` |
| **Input** | `str: String` |
| **Output** | `dest: f64` (parsed float) |

### Q_I_TO_STR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_I_TO_STR dest, num` |
| **Input** | `num: i64` |
| **Output** | `dest: String` (decimal representation) |

### Q_F_TO_STR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_F_TO_STR dest, num` |
| **Input** | `num: f64` |
| **Output** | `dest: String` (decimal representation) |

---

## 9. Array Operations

### Q_ARR_NEW
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_NEW dest` |
| **Input** | None |
| **Output** | `dest: Array` (empty) |
| **Side-effects** | Allocates array header |

### Q_ARR_LEN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_LEN dest, arr` |
| **Input** | `arr: Array` |
| **Output** | `dest: i64` (length) |

### Q_ARR_GET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_GET dest, arr, idx` |
| **Input** | `arr: Array`, `idx: i64` |
| **Output** | `dest: Value` (element at index) |
| **Notes** | **TRAP** if idx out of bounds |

### Q_ARR_SET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_SET arr, idx, value` |
| **Input** | `arr: Array`, `idx: i64`, `value: Value` |
| **Output** | None |
| **Side-effects** | Modifies array |

### Q_ARR_PUSH
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_PUSH arr, value` |
| **Input** | `arr: Array`, `value: Value` |
| **Output** | None |
| **Side-effects** | Appends to array, may reallocate |

### Q_ARR_POP
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_POP dest, arr` |
| **Input** | `arr: Array` |
| **Output** | `dest: Value` (removed last element) |
| **Side-effects** | Modifies array |

### Q_ARR_SLICE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_SLICE dest, arr, start, end` |
| **Input** | `arr: Array`, `start: i64`, `end: i64` |
| **Output** | `dest: Array` (new subarray) |

### Q_ARR_INSERT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_INSERT arr, idx, value` |
| **Input** | `arr: Array`, `idx: i64`, `value: Value` |
| **Output** | None |
| **Side-effects** | Inserts at index, shifts elements |

### Q_ARR_REMOVE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARR_REMOVE dest, arr, idx` |
| **Input** | `arr: Array`, `idx: i64` |
| **Output** | `dest: Value` (removed element) |
| **Side-effects** | Removes at index, shifts elements |

---

## 10. Map Operations

### Q_MAP_NEW
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MAP_NEW dest` |
| **Input** | None |
| **Output** | `dest: Map` (empty) |

### Q_MAP_GET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MAP_GET dest, map, key` |
| **Input** | `map: Map`, `key: String` |
| **Output** | `dest: Value` (or default) |

### Q_MAP_SET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MAP_SET map, key, value` |
| **Input** | `map: Map`, `key: String`, `value: Value` |
| **Output** | None |
| **Side-effects** | Inserts or updates entry |

### Q_MAP_HAS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MAP_HAS dest, map, key` |
| **Input** | `map: Map`, `key: String` |
| **Output** | `dest: i64 = 1 if key exists` |

### Q_MAP_DEL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_MAP_DEL map, key` |
| **Input** | `map: Map`, `key: String` |
| **Output** | None |
| **Side-effects** | Removes entry |

---

## 11. Entity/Struct Operations

### Q_ENTITY_NEW
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ENTITY_NEW dest, type_idx, field_count` |
| **Input** | `type_idx: u32`, `field_count: u32` |
| **Output** | `dest: Entity` (allocated instance) |
| **Side-effects** | Allocates entity, initializes RC=1 |

### Q_GET_FIELD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_GET_FIELD dest, entity, field_idx` |
| **Input** | `entity: Entity`, `field_idx: u32` |
| **Output** | `dest: Value` (field value) |

### Q_SET_FIELD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SET_FIELD entity, field_idx, value` |
| **Input** | `entity: Entity`, `field_idx: u32`, `value: Value` |
| **Output** | None |
| **Side-effects** | Modifies entity field |

---

## 12. File I/O

### Q_FILE_OPEN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FILE_OPEN dest, path, mode` |
| **Input** | `path: String`, `mode: i64` |
| **Output** | `dest: i64` (file descriptor) |
| **Implementation** | `open()` syscall |

### Q_FILE_READ
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FILE_READ dest, fd, buf, count` |
| **Input** | `fd: i64`, `buf: ptr`, `count: i64` |
| **Output** | `dest: i64` (bytes read) |
| **Implementation** | `read()` syscall |

### Q_FILE_WRITE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FILE_WRITE dest, fd, buf, count` |
| **Input** | `fd: i64`, `buf: ptr`, `count: i64` |
| **Output** | `dest: i64` (bytes written) |
| **Implementation** | `write()` syscall |

### Q_FILE_WRITE_BYTE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FILE_WRITE_BYTE fd, byte` |
| **Input** | `fd: i64`, `byte: i64` |
| **Output** | None |

### Q_FILE_CLOSE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FILE_CLOSE fd` |
| **Input** | `fd: i64` |
| **Output** | None |
| **Implementation** | `close()` syscall |

### Q_FS_LIST
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FS_LIST dest, path` |
| **Input** | `path: String` |
| **Output** | `dest: Array[String]` (directory entries) |

### Q_FS_EXISTS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_FS_EXISTS dest, path` |
| **Input** | `path: String` |
| **Output** | `dest: i64 = 1 if exists` |

---

## 13. Network Operations

### Q_NET_LISTEN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_LISTEN dest, port` |
| **Input** | `port: i64` |
| **Output** | `dest: i64` (socket fd) |

### Q_NET_ACCEPT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_ACCEPT dest, server_fd` |
| **Input** | `server_fd: i64` |
| **Output** | `dest: i64` (client fd) |

### Q_NET_SEND_STR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_SEND_STR fd, str` |
| **Input** | `fd: i64`, `str: String` |
| **Output** | None |

### Q_NET_SEND_ALL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_SEND_ALL fd, buf, len` |
| **Input** | `fd: i64`, `buf: ptr`, `len: i64` |
| **Output** | None |

### Q_NET_RECV_STR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_RECV_STR dest, fd, max_len` |
| **Input** | `fd: i64`, `max_len: i64` |
| **Output** | `dest: String` |

### Q_NET_CLOSE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_CLOSE fd` |
| **Input** | `fd: i64` |
| **Output** | None |

### Q_NET_SET_NODELAY
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_NET_SET_NODELAY fd, enable` |
| **Input** | `fd: i64`, `enable: i64` |
| **Output** | None |
| **Notes** | Sets TCP_NODELAY option |

---

## 14. SIMD/Vector Operations

### Q_VLOAD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VLOAD dest, addr` |
| **Input** | `addr: ptr` (16-byte aligned) |
| **Output** | `dest: v128` (vector register) |
| **Implementation** | x86: `MOVDQA`, ARM64: `LD1` |

### Q_VSTORE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VSTORE addr, src` |
| **Input** | `addr: ptr`, `src: v128` |
| **Output** | None |
| **Implementation** | x86: `MOVDQA`, ARM64: `ST1` |

### Q_VADD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VADD dest, src1, src2, elem_type` |
| **Input** | `src1: v128`, `src2: v128`, `elem_type: i32` |
| **Output** | `dest: v128 = src1 + src2` (element-wise) |
| **Implementation** | x86: `PADDD/PADDQ`, ARM64: `ADD.4S` |

### Q_VSUB
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VSUB dest, src1, src2, elem_type` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128 = src1 - src2` |

### Q_VMUL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VMUL dest, src1, src2, elem_type` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128 = src1 * src2` |

### Q_VDIV
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VDIV dest, src1, src2, elem_type` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128 = src1 / src2` |

### Q_VFMA
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VFMA dest, a, b, c` |
| **Input** | `a: v128`, `b: v128`, `c: v128` |
| **Output** | `dest: v128 = a * b + c` (fused multiply-add) |
| **Implementation** | x86: `VFMADD`, ARM64: `FMLA` |

### Q_VMLA
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VMLA dest, a, b, c` |
| **Input** | Same as VFMA |
| **Output** | Same as VFMA |
| **Notes** | Alias for VFMA |

### Q_VMIN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VMIN dest, src1, src2` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128 = min(src1, src2)` (element-wise) |

### Q_VMAX
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VMAX dest, src1, src2` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128 = max(src1, src2)` (element-wise) |

### Q_VREDUCE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VREDUCE dest, src, op` |
| **Input** | `src: v128`, `op: ReduceOp` |
| **Output** | `dest: scalar` (reduced value) |
| **Notes** | Horizontal reduction (sum, max, min) |

### Q_VSPLAT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VSPLAT dest, scalar` |
| **Input** | `scalar: i64/f64` |
| **Output** | `dest: v128` (all lanes = scalar) |

### Q_VPERM
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VPERM dest, src, mask` |
| **Input** | `src: v128`, `mask: v128` |
| **Output** | `dest: v128` (permuted) |

### Q_VCMP_EQ
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VCMP_EQ dest, src1, src2` |
| **Input** | `src1: v128`, `src2: v128` |
| **Output** | `dest: v128` (comparison mask) |

### Q_VABS
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VABS dest, src` |
| **Input** | `src: v128` |
| **Output** | `dest: v128 = abs(src)` |

### Q_VSQRT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_VSQRT dest, src` |
| **Input** | `src: v128` |
| **Output** | `dest: v128 = sqrt(src)` (element-wise) |

---

## 15. System Calls

### Q_SYSCALL
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SYSCALL dest, num, args...` |
| **Input** | `num: i64`, up to 6 args |
| **Output** | `dest: i64` (syscall return value) |
| **Implementation** | Direct `syscall` instruction |
| **Notes** | Platform-specific syscall numbers |

### Q_ENV_GET
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ENV_GET dest, name` |
| **Input** | `name: String` |
| **Output** | `dest: String` (env value or empty) |
| **Implementation** | Calls `getenv()` |

### Q_TIME
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TIME dest` |
| **Input** | None |
| **Output** | `dest: i64` (Unix timestamp) |
| **Implementation** | `gettimeofday()` or `clock_gettime()` |

### Q_SLEEP
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SLEEP milliseconds` |
| **Input** | `milliseconds: i64` |
| **Output** | None |
| **Implementation** | `nanosleep()` |

---

## 16. Task/Process Operations

### Q_TASK_SPAWN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TASK_SPAWN dest, func, args` |
| **Input** | `func: FuncPtr`, `args: Array` |
| **Output** | `dest: TaskHandle` |
| **Side-effects** | Creates new task/coroutine |

### Q_TASK_YIELD
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TASK_YIELD` |
| **Input** | None |
| **Output** | None |
| **Side-effects** | Suspends current task |

### Q_TASK_WAIT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TASK_WAIT dest, handle` |
| **Input** | `handle: TaskHandle` |
| **Output** | `dest: Value` (task result) |
| **Side-effects** | Blocks until task completes |

### Q_PROCESS_FORK
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PROCESS_FORK dest` |
| **Input** | None |
| **Output** | `dest: i64` (0 in child, pid in parent) |
| **Implementation** | `fork()` syscall |

### Q_PIPE
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PIPE read_fd, write_fd` |
| **Input** | None |
| **Output** | `read_fd: i64`, `write_fd: i64` |
| **Implementation** | `pipe()` syscall |

### Q_EXEC
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_EXEC path, args, env` |
| **Input** | `path: String`, `args: Array`, `env: Array` |
| **Output** | None (replaces process) |
| **Implementation** | `execve()` syscall |

### Q_WAITPID
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_WAITPID dest, pid, options` |
| **Input** | `pid: i64`, `options: i64` |
| **Output** | `dest: i64` (status) |
| **Implementation** | `waitpid()` syscall |

### Q_DUP2
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_DUP2 dest, oldfd, newfd` |
| **Input** | `oldfd: i64`, `newfd: i64` |
| **Output** | `dest: i64` |
| **Implementation** | `dup2()` syscall |

---

## 17. Exception Handling

### Q_TRY_START
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TRY_START handler_label` |
| **Input** | `handler_label: u32` |
| **Output** | None |
| **Side-effects** | Pushes exception handler |

### Q_TRY_END
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_TRY_END` |
| **Input** | None |
| **Output** | None |
| **Side-effects** | Pops exception handler |

### Q_THROW
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_THROW error_value` |
| **Input** | `error_value: Value` |
| **Output** | None (control transfer) |
| **Side-effects** | Unwinds to nearest handler |

---

## 18. JIT/Patch Operations

### Q_PATCH_FUNC
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PATCH_FUNC func_idx, new_ptr` |
| **Input** | `func_idx: u32`, `new_ptr: ptr` |
| **Output** | None |
| **Side-effects** | Hot-patches function entry |
| **Notes** | Used by tiered JIT for upgrades |

### Q_PATCH_POINT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PATCH_POINT id` |
| **Input** | `id: u32` |
| **Output** | None |
| **Notes** | Marks location for dynamic patching |

### Q_REG_PIN
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_REG_PIN vreg, phys_reg` |
| **Input** | `vreg: u32`, `phys_reg: u32` |
| **Output** | None |
| **Notes** | Forces register allocation hint |

### Q_SIGN_VSIB
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_SIGN_VSIB base, idx, scale` |
| **Input** | Complex addressing mode |
| **Output** | None |
| **Notes** | x86 VSIB addressing for scatter/gather |

### Q_REFLECT_IR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_REFLECT_IR dest, func_idx` |
| **Input** | `func_idx: u32` |
| **Output** | `dest: IR_Module` |
| **Notes** | Runtime IR reflection |

---

## 19. Miscellaneous

### Q_PRINT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PRINT value` |
| **Input** | `value: Value` |
| **Output** | None |
| **Side-effects** | Writes to stdout |

### Q_PRINT_STR
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_PRINT_STR str` |
| **Input** | `str: String` |
| **Output** | None |

### Q_INPUT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_INPUT dest` |
| **Input** | None |
| **Output** | `dest: String` (line from stdin) |

### Q_CAST
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CAST dest, src, type` |
| **Input** | `src: Value`, `type: TypeId` |
| **Output** | `dest: Value` (casted) |

### Q_I_TO_F
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_I_TO_F dest, src` |
| **Input** | `src: i64` |
| **Output** | `dest: f64` |

### Q_F_TO_I
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_F_TO_I dest, src` |
| **Input** | `src: f64` |
| **Output** | `dest: i64` (truncated) |

### Q_GET_ARG
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_GET_ARG dest, idx` |
| **Input** | `idx: u32` |
| **Output** | `dest: Value` (function argument) |

### Q_ARG_COUNT
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_ARG_COUNT dest` |
| **Input** | None |
| **Output** | `dest: i64` (number of arguments) |

### Q_CHECK_CPU
| Field | Description |
|-------|-------------|
| **Syntax** | `Q_CHECK_CPU dest, feature` |
| **Input** | `feature: u32` (feature flag) |
| **Output** | `dest: i64 = 1 if supported` |
| **Notes** | Runtime CPU feature detection |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Arithmetic | 7 |
| Float | 4 |
| Math | 6 |
| Comparison | 6 |
| Bitwise | 6 |
| Control Flow | 11 |
| Memory | 16 |
| String | 21 |
| Array | 9 |
| Map | 5 |
| Entity | 3 |
| File I/O | 7 |
| Network | 7 |
| SIMD/Vector | 16 |
| System | 4 |
| Task/Process | 8 |
| Exception | 3 |
| JIT/Patch | 5 |
| Miscellaneous | 10 |
| **TOTAL** | **148** |

---

*Document generated for Stage 4 "Kill C" preparation — 22/03/2026*
