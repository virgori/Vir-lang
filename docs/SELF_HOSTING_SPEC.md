# Vir Self-Hosting Specification

> **Goal:** The entire Vir compiler is written in Vir itself.
> No `cc`, no C runtime. The `vir` binary compiles itself.
>
> **Last updated:** 9/3/2026

---

## Progress Overview (9/3/2026)

```
Phase 0 (Baseline)        ████████████████████  DONE — C compiler + VM + JIT
Phase 1 (Type Extension)  ████████████████████  DONE → 100%
  └─ compiler.vri         ████████████████████  ~1,900 LOC, self-compiles ARM64 ✅
  └─ array + globals      ████████████████████  codegen_emit_full2 ✅ DONE
  └─ struct/record        ████████████████████  parser + IR lower + VM ✅ DONE (10 E2E tests)
  └─ enum                 ████████████████████  parser + IR lower + VM ✅ DONE (compile-time const)
  └─ byte buffer          ████████████████████  stdlib buffer ✅, VM opcodes ✅ DONE
  └─ for-range loop       ████████████████████  `for i in 0..N` — lexer/parser/IR ✅ DONE
Phase 2 (Program Struct)  ████████████████████  DONE — Module/Import System ✅
  └─ import statement     ████████████████████  `import module` + `from module import sym` ✅
  └─ module statement     ████████████████████  `module name` declaration ✅
  └─ export statement     ████████████████████  `export func_name` ✅
  └─ qualified names      ████████████████████  `module.func()` syntax ✅
  └─ module resolution    ████████████████████  stdlib/module.vri lookup ✅
Phase 3 (System Layer)    ████████████████████  DONE — Native Syscalls ✅
  └─ syscall primitive    ████████████████████  `syscall(num, arg0, arg1, ...)` ✅
  └─ macOS ARM64 ABI      ████████████████████  x16=num, x0-x5=args, svc #0x80 ✅
  └─ BSD offset           ████████████████████  0x2000000 for syscall numbers ✅
Phase 4 (Vir-in-Vir)     ████████████████████  DONE — "The Purest Build" (9/3/2026) ✅
  └─ lexer.vri            ████████████████████  905 LOC ← lexer.c (807 LOC) ✅
  └─ parser.vri           ████████████████████  1,319 LOC ← parser.c (1,164 LOC) ✅
  └─ ir_optimizer.vri     ████████████████████  1,448 LOC ← ir_lower.c (1,804 LOC) ✅
  └─ codegen.vri          ████████████████████  1,663 LOC ← codegen.c (3,408 LOC) ✅
  └─ stdlib English conv  ████████████████████  16,036 changes across 82 files ✅
  └─ 0 Vietnamese kw      ████████████████████  grep verified: ZERO remaining ✅
Phase 5 (Bootstrap)       ████████████████████  DONE — Self-Hosting Binary (9/3/2026) ✅
  └─ compiler.vri         ████████████████████  ~3,170 LOC monolithic ARM64 compiler ✅
  └─ C VM compilation     ████████████████████  C vir → runs compiler.vri → 19,967 lines .s ✅
  └─ native binary        ████████████████████  137KB standalone Mach-O ARM64 executable ✅
  └─ self-compilation     ████████████████████  native compiler compiles itself ✅
  └─ fixed-point          ████████████████████  Stage 2 == Stage 3 (bit-identical) ✅
  └─ hello.vri test       ████████████████████  native → assemble → link → run → 42 ✅
  └─ fib(10) test         ████████████████████  recursive Fibonacci → 55 ✅
Phase 6 (Polish)          ░░░░░░░░░░░░░░░░░░░░  NOT STARTED

Phase 5 — Bootstrap "Tự Sinh" (9/3/2026):
  ✅ Monolithic compiler: core/bootstrap/compiler.vri (~3,170 LOC)
     - Tokenizer (50+ token types, keyword table, string/char escaping)
     - Recursive descent parser (AST with 30+ node types)
     - Constant-fold evaluator (compile-time arithmetic, shr, xor, etc.)
     - ARM64 code generator (functions, locals, globals, arrays, strings)
     - Inline runtime (print_int, str_cat, str_eq, malloc/mmap, file I/O)
  ✅ Build pipeline: compiler.vri → ARM64 .s → as → .o → ld → native binary
  ✅ Self-compilation: 19,967 lines ARM64 assembly, 137KB native binary
  ✅ Fixed-point achieved: Stage 2 (native compiles itself) == Stage 3 (identical)
  ✅ No Python dependency — standalone ARM64 Mach-O executable
  ✅ Bugs fixed during bootstrap:
     - `^` → `xor` keyword, `>>` → `shr` keyword (C lexer operator mapping)
     - `var mod` → `var mod_name` (keyword conflict with C lexer `mod` token)
     - Large stack offsets (>255 bytes) — indirect addressing via x9 register
     - Duplicate symbol collision (_char_to_str) — user function guard
     - Data section alignment (.p2align 3 before .quad entries)
     - Dynamic token allocation (heap-based lexer for large source files)
     - shr/xor keyword support in bootstrap tokenizer (for self-compilation)

Previous milestones:
  ✅ Phase 2: Module/Import system — import, from, module, export keywords
  ✅ Phase 3: Native syscall — syscall(4, 1, msg, len) = write to stdout
  ✅ compiler.vri: ~13,425 lines ARM64 assembly (self-hosting verified)
  ✅ Bootstrap stdlib: string.vri, math.vri, io.vri, array.vri, sys.vri
  ✅ Virgex (VPS) engine — 113/113 tests
  ✅ Standard library — 85 files .vri (82 original + 3 codegen)
  ✅ codegen_emit_full2 — all Q-IR opcodes (bitwise, memory, globals,
     strings, file I/O, arrays, system)
  ✅ 17 intrinsic functions
  ✅ 77/77 native tests pass (67 Phase 1A + 10 Phase 1B)
```

### Blockers ĐÃ GIẢI QUYẾT (Phase 1-3):

| Blocker | Trạng thái | Giải pháp |
|---------|-----------|-----------|
| Q_LOAD_GLOBAL / Q_STORE_GLOBAL | ✅ DONE | `codegen_emit_full2` — x86_64 + ARM64 |
| Array runtime intrinsics | ✅ DONE | `vir_builtin_arr_*` in `intrinsics.c` |
| Builtin string ops | ✅ DONE | `vir_builtin_str_*`, `file_*` in `intrinsics.c` |
| Q_JUMP / Q_CALL codegen | ✅ DONE (trước đó) | `codegen_emit_full` đã có |
| Bitwise ops (AND/OR/XOR/SHL/SHR) | ✅ DONE | Native x86_64 + ARM64 instructions |
| Q_CALL_FUNC | ✅ DONE | Label fixup trong `codegen_emit_full2` |
| Memory ops (LOAD/STORE BYTE/WORD) | ✅ DONE | Native load/store instructions |
| Import/Module system | ✅ DONE | Tokens: T_IMPORT, T_MODULE, T_EXPORT, T_FROM, T_AS |
| Native syscalls | ✅ DONE | syscall() built-in, macOS ARM64 ABI via svc #0x80 |

### Phase 2 — Module System (8/3/2026):

| Feature | Trạng thái | Chi tiết |
|---------|-----------|----------|
| `import mod` | ✅ DONE | Import entire module, resolved from stdlib/ |
| `from mod import sym` | ✅ DONE | Import specific symbols |
| `module name` | ✅ DONE | Declare current module name |
| `export func` | ✅ DONE | Mark function for export |
| `mod.func()` | ✅ DONE | Qualified name call via `_module_func` mangling |
| Module resolution | ✅ DONE | Searches stdlib/mod.vri and stdlib/vir/mod/mod.vri |

### Phase 3 — Native Syscalls (8/3/2026):

| Feature | Trạng thái | Chi tiết |
|---------|-----------|----------|
| `syscall(num, args...)` | ✅ DONE | Built-in expression returning syscall result |
| macOS ARM64 ABI | ✅ DONE | x16=syscall number, x0-x5=args, svc #0x80 |
| BSD syscall offset | ✅ DONE | Adds 0x2000000 to syscall number |
| sys.vri stdlib | ✅ DONE | sys_write, sys_read, sys_open, sys_close, sys_exit, mem_alloc |

### Phase 1B — Hoàn thành (9/3/2026):

| Feature | Trạng thái | Chi tiết |
|---------|-----------|----------|
| For-range loops | ✅ DONE | `for i in 0..N then` — lexer `..` token, parser, IR desugar to while |
| Enum definitions | ✅ DONE | `enum Name then VARIANT = val end` — compile-time integer constants |
| Record/struct | ✅ DONE | `record Name then field: type end` — heap-alloc Q_ALLOC + Q_STORE_WORD |
| Field access | ✅ DONE | `var.field` → Q_LOAD_WORD at field offset |
| Field assignment | ✅ DONE | `var.field = val` → Q_STORE_WORD at field offset |
| Record literals | ✅ DONE | `Type { field: val, ... }` syntax |
| E2E tests (Phase 1B) | ✅ 10/10 | for-range, enum, record — all passing |

### Blockers còn lại (Phase 4+):

| Blocker | Chi tiết | Cần làm |
|---------|----------|--------|
| Replace C runtime | Dùng syscall thay cho printf, malloc | Viết lại runtime.c bằng Vir |
| Native memory allocator | mem_alloc uses mmap but no free | Implement proper allocator |
| Remove -lSystem dependency | Eliminate all system library calls | Pure syscall-based I/O |

---

## 0. Hiện trạng (Baseline)

### 0.1. Kiến trúc hiện tại

```
┌─────────────────────────────────────────────────────────────────┐
│                    .vri source (UTF-8)                          │
│                  Vietnamese / English / Mixed                    │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐
│ C Lexer  │→│ C Parser │→│ ir_lower │→│   VM    │  │  JIT   │
│ lexer.c  │  │ parser.c │  │ir_lower.c│  │  vm.c   │  │codegen │
│  659 LOC │  │  662 LOC │  │  775 LOC │  │ 361 LOC │  │1230 LOC│
└──────────┘  └──────────┘  └──────────┘  └─────────┘  └────────┘
                                                ▲           ▲
                                                │           │
                                          ┌─────┴─────┬─────┴──────┐
                                          │ bridge.c  │jit_bridge.c│
                                          │  479 LOC  │  491 LOC   │
                                          └───────────┴────────────┘
```

### 0.2. Inventory – Các module C cần thay thế

| # | Module | File | LOC | Độ khó | Phụ thuộc C |
|---|--------|------|-----|--------|-------------|
| 1 | Q-IR types & builder | q_ir.c + q_ir.h | 423 | ★★☆ | malloc, memcpy |
| 2 | VM interpreter | vm.c + vm.h | 466 | ★★☆ | printf, scanf |
| 3 | Lexer | lexer.c + lexer.h | 816 | ★★★ | UTF-8, strcmp |
| 4 | Parser | parser.c + parser.h | 709 | ★★★ | AST alloc, recursion |
| 5 | IR Lowering | ir_lower.c + ir_lower.h | 982 | ★★★★ | symbol table, regalloc |
| 6 | Codegen (x86+ARM) | codegen.c + codegen.h | 1406 | ★★★★★ | machine code emit, backpatch |
| 7 | Bridge (OS layer) | bridge.c + bridge.h | 606 | ★★★★★ | mmap, mprotect, pthread |
| 8 | JIT Bridge | jit_bridge.c + jit_bridge.h | 743 | ★★★★ | exe memory, icache flush |
| 9 | Patcher | patcher.c + patcher.h | 410 | ★★★ | binary patching |
| 10 | Signer (HMAC) | signer.c + signer.h | 443 | ★★★ | SHA-256, crypto |
| 11 | Constraints | constraints.c + constraints.h | 238 | ★★☆ | type system |
| 12 | Intrinsics | intrinsics.c + intrinsics.h | 291 | ★★☆ | function pointers |
| 13 | CLI driver | main.c | 369 | ★★☆ | file I/O, argv |
| 14 | ASM (ARM64) | vir_arm64.S | 337 | ★★★★★ | platform ABI |
| 15 | ASM (x86_64) | vir_x86_64.S | 319 | ★★★★★ | platform ABI |
| | **TỔNG** | | **~8,600** | | |

### 0.3. Tính năng ngôn ngữ Vir hiện có

| Feature | Trạng thái |
|---------|-----------|
| int64, float64, string literals | ✅ |
| Biến (var), hằng (const) | ✅ |
| Hàm (func) với tham số | ✅ |
| if / elif / else / end | ✅ |
| while / loop / end | ✅ |
| Toán tử +−×/%, so sánh, logic | ✅ |
| print, input, return | ✅ |
| Gọi hàm (function call) | ✅ |
| TCO (tail-call optimization) | ✅ |
| JIT compilation (ARM64+x86) | ✅ |
| **Mảng (array)** | ✅ (VM + parser + IR) |
| **Struct / bản ghi (record)** | ✅ (parser + IR + VM) |
| **Con trỏ / tham chiếu** | ❌ |
| **Chuỗi mutable + thao tác** | ❌ |
| **File I/O** | ❌ |
| **Import / module system** | ❌ |
| **Cấp phát bộ nhớ (alloc/free)** | ❌ |
| **For loop** | ✅ (for-range: `for i in 0..N`) |
| **Byte / uint8 type** | ❌ |
| **Bitwise operators** | ✅ (parser + IR + VM + codegen) |
| **Platform syscall** | ❌ |
| **Inline ASM** | ❌ |
| **Generic / template** | ❌ |
| **Error handling** | ❌ |

### 0.4. Khoảng cách (Gap Analysis)

Để Vir tự viết compiler cho chính nó, cần **~15 tính năng mới** chia thành 3 nhóm:

```
┌─────────────────────────────────────────────────────────┐
│ NHÓM A: Hệ thống kiểu dữ liệu (Type System)           │
│   - Mảng (array) cơ bản                                │
│   - Struct / bản ghi (record type)                      │
│   - Enum (kiểu liệt kê)                                │
│   - Union / tagged union                                │
│   - Byte/u8/u32/u64 types                              │
│   - Con trỏ cơ bản (pointer-as-integer)                │
├─────────────────────────────────────────────────────────┤
│ NHÓM B: Cấu trúc chương trình (Program Structure)      │
│   - For loop                                            │
│   - Import / module / file                              │
│   - Error handling (try/catch hoặc result type)         │
│   - Chuỗi mutable + concat + slice + length            │
│   - Bitwise operators (and, or, xor, shift)            │
├─────────────────────────────────────────────────────────┤
│ NHÓM C: Hệ thống runtime (System Layer)                │
│   - malloc / free (cấp phát heap)                      │
│   - File I/O (open, read, write, close)                │
│   - Syscall interface (mmap, mprotect)                  │
│   - Inline ASM / raw byte emit                         │
│   - Platform detection (#nếu ARM64 / x86_64)           │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Chiến lược tổng thể (Overall Strategy)

### 1.1. Phương pháp: **Bootstrapping dần (Incremental Bootstrap)**

```
        Phase 0           Phase 1           Phase 2           Phase 3
       (hiện tại)      (mở rộng Vir)    (Vir viết Vir)    (tự biên dịch)
    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │  C compiler │    │  C compiler │    │  C compiler │    │ Vir binary │
    │  biên dịch  │    │  biên dịch  │    │  biên dịch  │    │  biên dịch │
    │  Vir engine │    │  Vir engine │    │ Vir engine  │    │ Vir engine │
    │ (thuần C)   │    │ (C + tính   │    │ + Vir-Vir   │    │ (thuần Vir)│
    │             │    │  năng mới)  │    │  compiler   │    │            │
    └──────┬─────┘    └──────┬─────┘    └──────┬─────┘    └──────┬─────┘
           │                 │                 │                 │
           ▼                 ▼                 ▼                 ▼
     vir run/jit       vir run/jit        vir₁ biên dịch    vir₂ == vir₁
     hello.vri         complex.vri        vir₁ compiler     (fixed point)
```

**Nguyên tắc:**
1. **Không bao giờ phá vỡ cái đang chạy** – C core luôn build được
2. **Mỗi phase thêm feature** – test regression 50+ tests vẫn pass
3. **Song song 2 đường** – C binary cũ validate output của Vir binary mới
4. **Fixed-point test** – Phase cuối: `vir₂(vir_source) == vir₁(vir_source)` byte-for-byte

### 1.2. Ngôn ngữ đích cho Self-Hosting

Vir sẽ **không cần toàn bộ tính năng C**. Thay vào đó, thiết kế tập con tối thiểu:

| C feature | Vir tương đương | Lý do |
|-----------|----------------|-------|
| `struct` | `bản ghi` (record) | Cây AST, Q-IR instruction |
| `enum` | `liệt kê` (enum) | Token types, opcodes |
| `int64_t` | `số` (int64, mặc định) | Registers, counters |
| `uint8_t*` | `mảng byte` | Machine code buffer |
| `malloc/free` | `cấp/giải` | Heap allocation |
| `char*` string | `chuỗi` (immutable) + `đệm` (buffer) | Source code, names |
| `array[N]` | `mảng` (dynamic) | Token list, instructions |
| `FILE*` | `tệp` (file handle) | Source input, binary output |
| `switch/case` | `chọn/trường_hợp` | Opcode dispatch |
| `#if ARCH` | `@nếu ARM64` | Platform conditional |

---

## 2. Các Phase Chi tiết

---

### Phase 1: Mở rộng Hệ thống Kiểu (Type System Extension)
**Mục tiêu:** Vir có đủ kiểu dữ liệu để biểu diễn AST, Q-IR, token list
**Thời gian ước tính:** 2-3 tuần
**Prerequisite:** None (standalone)

#### 1A. Mảng (Array)

**Cú pháp:**
```
biến danh_sách = [1, 2, 3, 4, 5]
biến phần_tử = danh_sách[2]        # → 3
danh_sách[0] = 99
biến dài = dài(danh_sách)           # → 5
```

**Implementation:**
- Lexer: thêm `TOK_LBRACKET`, `TOK_RBRACKET` (đã có)
- Parser: `AST_ARRAY_LITERAL`, `AST_INDEX_ACCESS`, `AST_INDEX_ASSIGN`
- IR Lower: mảng → contiguous heap allocation, index → `Q_LOAD addr + offset`
- VM: `Q_LOAD_INDEXED`, `Q_STORE_INDEXED` opcodes mới
- Runtime: `vir_array_new(cap)`, `vir_array_get(arr, idx)`, `vir_array_set(arr, idx, val)`

**Tests:**
```
hàm kiểm_tra() thì
  biến a = [10, 20, 30]
  trả về a[0] + a[1] + a[2]    # → 60
hết
```

#### 1B. Bản ghi (Struct / Record)

**Cú pháp:**
```
bản_ghi Token thì
  loại: số
  dòng: số
  cột: số
  giá_trị: chuỗi
hết

biến t = Token { loại: 1, dòng: 5, cột: 10, giá_trị: "hello" }
in ra t.loại         # → 1
t.dòng = 6
```

**Implementation:**
- Lexer: `TOK_RECORD` (keyword `bản_ghi`), `TOK_DOT` (`.`)
- Parser: `AST_RECORD_DEF`, `AST_RECORD_LITERAL`, `AST_FIELD_ACCESS`, `AST_FIELD_ASSIGN`
- IR Lower: record → heap-allocated block, field → fixed offset load/store
- Type system: record type table mapping field names → offsets
- Codegen: field access → base_ptr + field_offset

**Tests:**
```
bản_ghi Điểm thì
  x: số
  y: số
hết

hàm khoảng_cách(p: Điểm) thì
  trả về p.x * p.x + p.y * p.y
hết
```

#### 1C. Liệt kê (Enum)

**Cú pháp:**
```
liệt_kê Opcode thì
  NOP = 0
  LOAD = 1
  ADD = 16
  RET = 68
hết

biến op = Opcode.ADD
nếu op == Opcode.LOAD thì ...
```

**Implementation:**
- Lexer: `TOK_ENUM` (keyword `liệt_kê`)
- Parser: `AST_ENUM_DEF`, `AST_ENUM_ACCESS`
- IR Lower: enum → compile-time integer constants (zero-cost abstraction)

#### 1D. Byte Array / Buffer

**Cú pháp:**
```
biến đệm = đệm_mới(4096)         # Buffer 4096 bytes
đệm_ghi_byte(đệm, 0, 0x90)       # Write NOP at offset 0
biến b = đệm_đọc_byte(đệm, 0)    # Read byte at offset 0
đệm_ghi_u32(đệm, 4, 0xD503201F)  # Write ARM64 NOP
```

**Implementation:**
- Intrinsics: `vir_buffer_new`, `vir_buffer_read_u8/u32/u64`, `vir_buffer_write_u8/u32/u64`
- IR: buffer is an opaque handle (pointer-as-int64)
- Codegen: direct memory access via intrinsic calls

**Deliverables Phase 1:**
- [ ] Array: parse `[...]`, index `a[i]`, `dài(a)`, dynamic resize
- [ ] Record: parse `bản_ghi`, field access `r.field`, record literal `R{...}`
- [ ] Enum: parse `liệt_kê`, `E.variant` → compile-time int
- [ ] Buffer: byte-level read/write intrinsics
- [ ] 20+ new tests, all 70+ tests pass
- [ ] Update ARCHITECTURE.md §12

---

### Phase 2: Cấu trúc Chương trình Mở rộng (Program Structure)
**Mục tiêu:** Vir có đủ cấu trúc điều khiển và module system
**Thời gian ước tính:** 2 tuần
**Prerequisite:** Phase 1

#### 2A. For Loop

**Cú pháp:**
```
với mỗi i trong 0..10 thì
  in ra i
hết

với mỗi phần_tử trong danh_sách thì
  in ra phần_tử
hết
```

**Implementation:**
- Parser: `AST_FOR_RANGE`, `AST_FOR_EACH`
- IR Lower: desugar to WHILE + counter/iterator

#### 2B. Switch / Match (Chọn)

**Cú pháp:**
```
chọn opcode thì
  trường_hợp Opcode.NOP thì
    # ...
  trường_hợp Opcode.LOAD thì
    # ...
  mặc_định thì
    # ...
hết
```

**Implementation:**
- Lexer: `TOK_SWITCH` (`chọn`), `TOK_CASE` (`trường_hợp`), `TOK_DEFAULT` (`mặc_định`)
- Parser: `AST_SWITCH`
- IR Lower: chain of `CMP_EQ + JUMP_IF_NOT` (later: jump table optimization)

#### 2C. Import / Module System

**Cú pháp:**
```
# File: q_ir.vri
nhập "lexer" dùng Token, TokenType
nhập "vm" dùng hết
```

**Implementation:**
- Lexer: `TOK_IMPORT` (`nhập`), `TOK_USE` (`dùng`)
- Module resolver: path-based lookup (`nhập "foo"` → `foo.vri`)
- Compilation unit: parse each module → lower independently → link Q-IR modules
- Symbol export/import table

#### 2D. Chuỗi Mutable (String Operations)

**Cú pháp:**
```
biến s = "hello"
biến t = s + " world"          # Concatenation
biến n = dài(s)                 # Length → 5
biến c = s[0]                   # Char access → 104 ('h')
biến sub = cắt(s, 1, 3)        # Slice → "ell"
```

**Implementation:**
- String intrinsics: `vir_str_concat`, `vir_str_len`, `vir_str_char_at`, `vir_str_slice`
- Strings are heap-allocated, reference-counted or GC-managed

#### 2E. Bitwise Operators (Parser Integration)

**Cú pháp:**
```
biến x = a & b          # AND
biến y = a | b          # OR
biến z = a ^ b          # XOR
biến w = a << 4         # Shift left
biến v = a >> 8         # Shift right
```

**Implementation:**
- Parser: thêm bitwise precedence level giữa comparison và logical
- Q-IR opcodes Q_AND/Q_OR/Q_XOR/Q_SHL/Q_SHR **đã có** sẵn
- Chỉ cần kết nối parser → ir_lower

**Deliverables Phase 2:**
- [ ] For loop (range + each)
- [ ] Switch / match statement
- [ ] Import / module system (single-file → multi-file)
- [ ] String operations (concat, len, index, slice)
- [ ] Bitwise operators connected to parser
- [ ] 30+ new tests, all 100+ tests pass

---

### Phase 3: Hệ thống Runtime (System Layer)
**Mục tiêu:** Vir có thể gọi OS, đọc/ghi file, cấp phát bộ nhớ
**Thời gian ước tính:** 2-3 tuần
**Prerequisite:** Phase 1 + 2

#### 3A. Cấp phát Bộ nhớ (Memory Allocation)

**Cú pháp:**
```
biến vùng = cấp(1024)          # malloc(1024)
ghi_byte(vùng, 0, 0x90)
biến b = đọc_byte(vùng, 0)
giải(vùng)                      # free()
```

**Implementation:**
- Intrinsics: `vir_alloc(size)` → returns int64 (address-as-integer)
- `vir_free(addr)`, `vir_read8/16/32/64(addr, offset)`, `vir_write8/16/32/64(addr, offset, val)`
- Intrinsic IDs đã có sẵn trong `intrinsics.h` (ALLOC=6, FREE=7)

#### 3B. File I/O

**Cú pháp:**
```
biến f = mở_tệp("input.vri", "r")
biến nội_dung = đọc_tệp(f)
đóng_tệp(f)

biến g = mở_tệp("output.bin", "w")
ghi_tệp(g, dữ_liệu)
đóng_tệp(g)
```

**Implementation:**
- New intrinsics: `vir_file_open`, `vir_file_read`, `vir_file_write`, `vir_file_close`
- File handle = integer (fd or FILE* cast to int64)

#### 3C. Syscall Interface

**Cú pháp:**
```
# Cấp thấp – gọi syscall trực tiếp
biến vùng = gọi_hệ_thống(SYS_MMAP, 0, 4096, 3, 34, -1, 0)
gọi_hệ_thống(SYS_MPROTECT, vùng, 4096, 5)
```

**Implementation:**
- Intrinsic: `vir_syscall(number, arg0..arg5)` → int64
- VM: dispatch to actual `syscall()` or platform wrapper
- Codegen: emit SVC (ARM64) or SYSCALL (x86_64)

#### 3D. Inline Byte Emit

**Cú pháp:**
```
# Emit raw bytes vào code buffer
biến cb = đệm_mã_mới(4096)
phát_byte(cb, 0xD5)          # Raw byte
phát_u32(cb, 0xD503201F)     # ARM64 NOP
phát_u64(cb, địa_chỉ)        # 64-bit address
```

**Implementation:**
- Intrinsics wrapping `codebuf_emit_byte`, `codebuf_emit_u32`
- Cho phép Vir code trực tiếp emit machine code

#### 3E. Platform Detection

**Cú pháp:**
```
@nếu ARM64 thì
  phát_u32(cb, 0xD503201F)    # ARM64 NOP
@hoặc_nếu X86_64 thì
  phát_byte(cb, 0x90)         # x86 NOP
@hết
```

**Implementation:**
- Compile-time conditional (`@nếu` = preprocessor directive)
- Lexer: `TOK_DIRECTIVE_IF`, `TOK_DIRECTIVE_ELIF`, `TOK_DIRECTIVE_END`
- Parser: evaluate platform flag → include/exclude AST subtree

**Deliverables Phase 3:**
- [ ] Memory alloc/free + raw read/write
- [ ] File I/O (open, read, write, close)
- [ ] Syscall interface
- [ ] Raw byte emit intrinsics
- [ ] Platform conditional compilation
- [ ] 20+ new tests, all 120+ tests pass

---

### Phase 4: Viết lại Compiler bằng Vir (Vir-in-Vir Compiler)
**Mục tiêu:** Toàn bộ pipeline Lexer → Parser → IR Lower → Codegen viết bằng Vir
**Thời gian ước tính:** 4-6 tuần
**Prerequisite:** Phase 1 + 2 + 3

#### 4A. Tự viết Lexer (vir_lexer.vri)

**Thay thế:** `lexer.c` (659 LOC) → `vir_lexer.vri` (~800 LOC)

```
nhập "q_ir_types" dùng hết

liệt_kê TokenType thì
  EOF = 0
  INT = 1
  FLOAT = 2
  STRING = 3
  IDENT = 4
  FUNC = 5
  # ... 55 loại
hết

bản_ghi Token thì
  loại: số
  dòng: số
  cột: số
  giá_trị_số: số
  giá_trị_chuỗi: chuỗi
hết

hàm tokenize(nguồn: chuỗi) thì
  biến tokens = []
  biến vị_trí = 0
  trong khi vị_trí < dài(nguồn) thì
    biến ký_tự = nguồn[vị_trí]
    chọn ký_tự thì
      trường_hợp ' ' thì
        vị_trí = vị_trí + 1
      trường_hợp '+' thì
        tokens = thêm(tokens, Token { loại: TokenType.PLUS, ... })
      # ...
    hết
  hết
  trả về tokens
hết
```

#### 4B. Tự viết Parser (vir_parser.vri)

**Thay thế:** `parser.c` (662 LOC) → `vir_parser.vri` (~900 LOC)

```
nhập "vir_lexer" dùng Token, TokenType
nhập "ast" dùng ASTNode, ASTType

hàm parse_expression(tokens, vị_trí) thì
  trả về parse_or(tokens, vị_trí)
hết

hàm parse_or(tokens, vị_trí) thì
  biến trái = parse_and(tokens, vị_trí)
  trong khi current_token(tokens, vị_trí).loại == TokenType.OR thì
    vị_trí = vị_trí + 1
    biến phải = parse_and(tokens, vị_trí)
    trái = ASTNode { loại: ASTType.BINOP, op: OP_OR, ... }
  hết
  trả về trái
hết
```

#### 4C. Tự viết IR Lowering (vir_lower.vri)

**Thay thế:** `ir_lower.c` (775 LOC) → `vir_lower.vri` (~1000 LOC)

#### 4D. Tự viết Codegen (vir_codegen.vri)

**Thay thế:** `codegen.c` (1230 LOC) → `vir_codegen.vri` (~1500 LOC)

Đây là module phức tạp nhất vì emit machine code trực tiếp:

```
nhập "buffer" dùng đệm_mới, phát_byte, phát_u32

@nếu ARM64 thì
hàm emit_add(cb, rd, rn, rm) thì
  # ADD Xd, Xn, Xm → 0x8B000000 | rm<<16 | rn<<5 | rd
  biến instr = 0x8B000000 | (rm << 16) | (rn << 5) | rd
  phát_u32(cb, instr)
hết
@hết

@nếu X86_64 thì
hàm emit_add(cb, dst, src) thì
  # REX.W prefix + ADD r/m64, r64
  phát_byte(cb, 0x48 | ((src >> 3) << 2) | (dst >> 3))
  phát_byte(cb, 0x01)
  phát_byte(cb, 0xC0 | ((src & 7) << 3) | (dst & 7))
hết
@hết
```

#### 4E. Tự viết VM (vir_vm.vri)

**Thay thế:** `vm.c` (361 LOC) → `vir_vm.vri` (~500 LOC)

#### 4F. Tự viết Bridge + JIT Bridge

**Thay thế:** `bridge.c` + `jit_bridge.c` (970 LOC) → sử dụng syscall interface

**Deliverables Phase 4:**
- [ ] vir_lexer.vri – Lexer viết bằng Vir
- [ ] vir_parser.vri – Parser viết bằng Vir
- [ ] vir_lower.vri – IR Lowering viết bằng Vir
- [ ] vir_codegen.vri – Codegen viết bằng Vir
- [ ] vir_vm.vri – VM viết bằng Vir
- [ ] vir_bridge.vri – OS Bridge viết bằng Vir
- [ ] vir_main.vri – CLI driver viết bằng Vir
- [ ] Cross-validation: C binary và Vir binary cho cùng output
- [ ] All 120+ tests pass trên cả hai

---

### Phase 5: Bootstrap & Validation (Fixed-Point)
**Mục tiêu:** `vir₂ = vir₁(vir_source)` = `vir₂(vir_source)` — binary giống nhau
**Thời gian ước tính:** 2 tuần
**Prerequisite:** Phase 4

#### 5A. Three-Stage Bootstrap

```
Stage 0:  cc biên dịch vir₀ (C code)              → binary vir₀
Stage 1:  vir₀ biên dịch vir_compiler.vri          → binary vir₁
Stage 2:  vir₁ biên dịch vir_compiler.vri          → binary vir₂
Kiểm tra: sha256(vir₁) == sha256(vir₂)            → FIXED POINT ✓
```

#### 5B. Validation Suite

| Test | Mô tả |
|------|-------|
| Byte-identical | sha256(vir₁ output) == sha256(vir₂ output) |
| Cross-compile | vir₁ biên dịch test suite, vir₂ biên dịch test suite → cùng kết quả |
| Regression | Tất cả 120+ tests pass trên vir₁ và vir₂ |
| Fuzzing | Random Vir source → cả hai compiler cho cùng output hoặc cùng error |
| Performance | vir₂ không chậm hơn vir₁ quá 20% |

#### 5C. Loại bỏ C Dependency

```
TRƯỚC:
  Makefile → cc src/*.c → libvir_core.a → build/vir (C binary)

SAU:
  Stage 0: (chỉ lần đầu, hoặc lưu vir₀ binary pre-built)
  cc → vir₀

  Phát triển bình thường:
  vir₀ → biên dịch vir_compiler.vri → vir₁ (production binary)
```

**Deliverables Phase 5:**
- [ ] Three-stage bootstrap script
- [ ] Fixed-point validation (sha256 match)
- [ ] Fuzzing cross-check
- [ ] Remove C from build path (keep as historical reference)
- [ ] Pre-built vir₀ binary cho mỗi platform (macOS ARM64, Linux x86_64)

---

### Phase 6: Tinh chỉnh & Tối ưu (Polish)
**Mục tiêu:** Compiler tự viết hoàn chỉnh, production-ready
**Thời gian ước tính:** 2-4 tuần
**Prerequisite:** Phase 5

#### 6A. Tối ưu Compiler

- [ ] Constant folding (đã có phần nào trong TCO)
- [ ] Dead code elimination
- [ ] Inlining nhỏ (functions < 10 instructions)
- [ ] Loop-invariant code motion
- [ ] Register allocation cải tiến (graph coloring thay linear scan)

#### 6B. Error Messages bằng Tiếng Việt

```
LỖI [dòng 5, cột 12]: Biến 'x' chưa được khai báo
GỢI Ý: Bạn muốn dùng 'biến x = ...' ?

LỖI [dòng 10]: Thiếu 'hết' để đóng khối 'nếu' bắt đầu ở dòng 3
```

#### 6C. Standard Library (stdlib.vri)

```
# stdlib/io.vri     – File I/O, console
# stdlib/chuỗi.vri  – String utilities
# stdlib/mảng.vri   – Array utilities
# stdlib/toán.vri   – Math functions
# stdlib/hệ.vri     – OS, process, env
```

#### 6D. Documentation Generator

- Viết bằng Vir, tạo HTML/Markdown từ doc comments trong source

---

## 3. Timeline Tổng hợp

```
Tháng    1         2         3         4         5         6
      ├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
      │ Phase 1 │ Phase 2 │ Phase 3 │    Phase 4          │ Ph5+6  │
      │ Types   │ Struct  │ System  │    Vir-in-Vir       │ Boot   │
      │ Array   │ Import  │ File IO │    Compiler          │ Polish │
      │ Record  │ Switch  │ Syscall │    Rewrite           │ Fixed  │
      │ Enum    │ String  │ Inline  │    Validate          │ Point  │
      ├─────────┼─────────┼─────────┼─────────────────────┼────────┤
      │~70 tests│~100 test│~120 test│ ~150 tests          │~180 tst│
      └─────────┴─────────┴─────────┴─────────────────────┴────────┘

Milestone checkpoints:
  M1 (end Phase 1): Vir có array + struct + enum → có thể biểu diễn AST
  M2 (end Phase 2): Vir có import + switch → có thể viết compiler logic
  M3 (end Phase 3): Vir có file I/O + syscall → có thể đọc source, ghi binary
  M4 (end Phase 4): Compiler Vir-in-Vir output == C compiler output
  M5 (end Phase 5): vir₁ == vir₂ (fixed point, C removed from build)
  M6 (end Phase 6): Production-ready, optimized, documented
```

---

## 4. Rủi ro & Giải pháp

| Rủi ro | Xác suất | Giải pháp |
|--------|----------|-----------|
| Codegen quá phức tạp viết bằng Vir | Cao | Giữ ASM files làm "escape hatch", Vir gọi qua FFI |
| Performance regression | Trung bình | Benchmark suite, profiling, keep C fallback |
| Bootstrap cycle break | Thấp | Lưu pre-built binary, git tag mỗi milestone |
| Platform divergence (ARM vs x86) | Trung bình | `@nếu` directive + shared Q-IR layer |
| Compiler bug loop (vir biên dịch sai chính nó) | Trung bình | Always cross-validate with C binary until M5 |

---

## 5. Thứ tự Ưu tiên Module Thay thế

Dựa trên dependency graph và độ khó:

```
Đợt 1 (ít phụ thuộc, thuần logic):
  ① q_ir.vri        – Types & builder (423 LOC) ★★☆
  ② constraints.vri  – Type checking   (238 LOC) ★★☆
  ③ signer.vri       – SHA-256, HMAC   (443 LOC) ★★★

Đợt 2 (frontend, text processing):
  ④ lexer.vri        – Tokenizer       (816 LOC) ★★★
  ⑤ parser.vri       – Recursive desc  (709 LOC) ★★★

Đợt 3 (middle-end, semantic):
  ⑥ ir_lower.vri     – AST→Q-IR       (982 LOC) ★★★★
  ⑦ vm.vri           – Interpreter     (466 LOC) ★★☆

Đợt 4 (backend, machine code):
  ⑧ codegen.vri      – ARM64+x86 emit (1406 LOC) ★★★★★
  ⑨ patcher.vri      – Binary patching (410 LOC) ★★★
  ⑩ intrinsics.vri   – Builtins        (291 LOC) ★★☆

Đợt 5 (OS layer, most platform-dependent):
  ⑪ bridge.vri       – OS syscalls     (606 LOC) ★★★★★
  ⑫ jit_bridge.vri   – JIT memory      (743 LOC) ★★★★
  ⑬ main.vri         – CLI driver      (369 LOC) ★★☆
```

---

## 6. Metrrics Thành công

| Metric | Target |
|--------|--------|
| **Test pass rate** | 100% (regression + new) |
| **Fixed-point** | sha256(vir₁ output) == sha256(vir₂ output) |
| **Build time** | vir biên dịch chính nó < 5 giây |
| **Binary size** | vir binary < 500 KB |
| **Performance** | JIT throughput ≥ 80% so với C version |
| **C dependency** | 0 (chỉ pre-built vir₀ cho bootstrap) |
| **LOC Vir** | ~10,000 (tương đương ~8,600 LOC C) |
| **Platform** | macOS ARM64 + Linux x86_64 |
