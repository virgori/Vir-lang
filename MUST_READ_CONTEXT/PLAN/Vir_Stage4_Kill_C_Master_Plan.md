# VIR — Stage 4: "Giết C" — Kế hoạch Chiến lược Thống lĩnh

> **Mục tiêu:** Biến Vir thành ngôn ngữ lập trình **tự chủ hoàn toàn**, thống lĩnh cả bậc thấp (systems) lẫn bậc cao (applications), với hiệu suất vượt trội — trở thành **hiện tượng kỳ lạ** trong giới ngôn ngữ lập trình.
> **Ngày:** 22/03/2026 (updated 11/04/2026)
> **Trạng thái hiện tại:** Stage 4 ĐÃ HOÀN TẤT ✅ — 47/47 tests, Phase 6 optimization passes done
>
> ⚠️ **CẬP NHẬT 2026-04-11:**
> - Stage 4 ("Giết C") đã hoàn thành: 47/47 tests PASS, self-hosting compiler virc.vri hoạt động hoàn chỉnh
> - **Phase 5:** Python removed, build hardened, heap-overflow fixed
> - **Phase 6:** 3 optimization passes (fusion, BCE, autovec), 82 canonical QOp opcodes, ARM64 SIMD handlers
> - **Tiếp theo:** Stage 5 (Bootstrap: virc biên dịch virc → native binary, x86_64 backend)

---

## MỤC LỤC

1. [Tầm nhìn Chiến lược](#1-tầm-nhìn-chiến-lược)
2. [Phân tích Hiện trạng](#2-phân-tích-hiện-trạng)
3. [Stage 4: Giết C](#3-stage-4-giết-c)
4. [Stage 5: Siêu năng lực](#4-stage-5-siêu-năng-lực)
5. [Stage 6: Thống lĩnh](#5-stage-6-thống-lĩnh)
6. [Adaptive JIT: Chìa khóa Hiệu suất](#6-adaptive-jit-chìa-khóa-hiệu-suất)
7. [Lộ trình Thực hiện](#7-lộ-trình-thực-hiện)
8. [Metrics Thành công](#8-metrics-thành-công)

---

## 1. Tầm nhìn Chiến lược

### 1.1 Định vị

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VIR POSITIONING                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   HIGH-LEVEL                                                        │
│   (Productivity)     Python ─────────────── JavaScript              │
│        │                    \               /                        │
│        │                     \    VIR     /                          │
│        │                      \  ═════  /                            │
│        │                       \       /                             │
│        │              Java ─────◆─────── Go                          │
│        │                       /       \                             │
│        │                      /         \                            │
│        ▼                     /           \                           │
│   LOW-LEVEL          Rust ─────────────── C/C++                     │
│   (Performance)                                                      │
│                                                                      │
│   VIR = Unique position: Systems + Applications + AI                │
│         with Self-Hosting + Adaptive JIT + Zero Dependencies        │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Tại sao Vir Đặc biệt?

| Ngôn ngữ | Điểm mạnh | Điểm yếu | Vir giải quyết |
|----------|-----------|----------|----------------|
| **C/C++** | Hiệu suất, bậc thấp | Unsafe, complex | Borrow Checker + Clean syntax |
| **Rust** | Memory safety | Steep learning curve | Simpler ownership model |
| **Go** | Concurrency | No generics (until 1.18), GC | Vir có cả hai + no GC |
| **Python** | Productivity | Slow | Vir compiler ~1900x faster |
| **JavaScript** | Ecosystem | Single-threaded | True parallelism |
| **Mojo** | AI/ML perf | Proprietary, new | Open source, proven |

### 1.3 Công thức Thành công

```
Vir = Rust's Safety + Go's Concurrency + C's Performance + Python's Readability
    + Self-Hosting + Adaptive JIT + Zero External Dependencies
```

---

## 2. Phân tích Hiện trạng

### 2.1 Codebase Metrics (Corrected 02/04/2026)

| Component | Language | LOC | Status |
|-----------|----------|-----|--------|
| **C Engine** | C11 | **26,393** (22,173 src + 4,220 headers) | ✅ Production (CẦN THAY THẾ) |
| **Vir Compiler** | Vir | **9,107** (7 core files) / **13,124** (+ rt + stdlib) | ✅ Self-hosted, 46 tests |
| **Vir Stdlib** | Vir | ~93,901 | ✅ 292 modules |
| **JIT Infrastructure** | Vir | ~1,000 | ⚠️ Stub/skeleton — cần verify |
| **Bootstrap** | Vir | ~3,000 | ⚠️ Pipeline works but not self-compiled yet |

### 2.2 Những gì Đã Có

```
✅ HOÀN TẤT:
├── Spec v1.2 Compliance (11 opcodes, 10 parser features)
├── Self-hosting Compiler (lexer → parser → IR → codegen → Mach-O)
├── 3-Pass Lowerer (Enum/Entity → FuncReg → FuncLower)
├── Memory Management (Arena + RC + Pool)
├── vtest Framework (29 files, ~910 test functions)
├── Python Elimination (100% độc lập)
└── Phase C.4+: virc.vri → ARM64 binary (46 tests pass, 02/04/2026)
    └── Phase C.4 codegen debugged (03/04/2026): test_arithmetic.vri
        compiles to 380-byte Mach-O, outputs 30/90/75/15/5, exit 0
        14 bugs fixed: print_int encoding, register clobbering, MSUB,
        frame pointer, field collision, QOp align, eif depth limit
    └── Phase 4.2 FULL WORKING BINARY (08/04/2026): `print 42` →
        34KB Mach-O ARM64 → "42" EXIT=0. 6 more bugs fixed:
        const decl parsing, codebuf_emit_byte, bvec word index,
        codebuf_get_data intrinsic, include reorder, write_file_bytes.
        409 globals initialized, 617 functions compiled, debug cleaned.

✅ ĐÃ VERIFY / COMPLETE (Phase 4.1C):
├── Stack Spilling — vreg ≥18 spills to SP+offset, SUB/ADD SP in prologue/epilogue
├── Higher-Order Calls — LoadFuncAddr (ADR), CallIndirect (BLR X16), let f = func_name; f(x) ✅
├── Chained arithmetic (a + b + c + ... parser loop fixed) ✅
└── expr_op clobbering in recursive BinOp lowering fixed ✅

⚠️ CHƯA VERIFY / PARTIAL:
├── 12-Pass Optimizer — KHÔNG TỒN TẠI trong Vir compiler (chỉ 3 passes)
├── SIMD Vectorization — C engine only (12 opcodes), Vir compiler: 0
├── JIT Bridge / Tiered / PGO — Stdlib files exist, chưa verify hoạt động
└── Escape Analysis / Deterministic Free — CHƯA IMPLEMENT
```

### 2.3 C Engine — Actual File Metrics (verified `wc -l`)

| File | LOC | Chức năng | Thay thế bằng |
|------|-----|-----------|---------------|
| `codegen.c` | 3,510 | x86_64/ARM64 emit | `codegen.vri` (đã có) |
| `ir_lower.c` | 2,102 | AST → Q-IR | `ir_optimizer.vri` (✅ đã có) |
| `parser.c` | 1,738 | Recursive descent | `parser.vri` (đã có) |
| `vm.c` | 1,559 | VM Interpreter | `vm.vri` (đã có) |
| `borrow_check.c` | 1,154 | Borrow checker | ❌ Chưa port |
| `micro_prober.c` | 1,056 | CPU probing | (platform-specific) |
| `lexer.c` | 854 | Tokenizer | `lexer.vri` (đã có) |
| `mem_manager.c` | 271 | Arena/RC/Pool | `alloc.vri` (đã có) |
| `bridge_native.c` | 362 | FFI bridge | Q_SYSCALL wrappers |
| **Total src** | **22,173** | | |
| **Headers** | **4,220** | | |

---

## 3. Stage 4: Giết C

### 3.1 Chiến lược Tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 4: KILL C                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Phase 4.1: Complete IR Lowering in Vir           ✅ DONE     │
│       └── C engine ir_lower.c: 601 funcs, 33K Q-IR, 0 errors   │
│                                                                  │
│   Phase 4.1B: VM Execution Verification            ✅ DONE     │
│       └── virc.vri runs on C VM → compiles 46 test programs   │
│       └── All 46 ARM64 binaries execute correctly (02/04/2026)│
│       └── 18+ bugs fixed (parser/entity/calling convention)  │
│       └── Strings, arrays, entities, enums, globals working  │
│       └── Plan: COMPLETE/06_Phase3_VM_Execution.md              │
│                                                                  │
│   Phase 4.1C: Stack Spilling + Higher-Order Calls  ✅ DONE     │
│       └── Codegen stack spill: vreg overflow → STR/LDR [SP]   │
│       └── Q_CALL_INDIRECT opcode + vm.c handler               │
│       └── Parser: fn as parameter type syntax                  │
│       └── Prerequisite for Phase 4.2/4.3 (self-hosting)       │
│                                                                  │
│   Phase 4.2: Native Codegen Verification                        │
│       └── codegen.vri emits identical binaries to codegen.c     │
│                                                                  │
│   Phase 4.3: Bootstrap Chain                                    │
│       └── virc.vri compiles itself → native binary              │
│       └── That binary compiles virc.vri → identical binary      │
│                                                                  │
│   Phase 4.4: Syscall Wrappers                                   │
│       └── Replace bridge_native.c with Q_SYSCALL + inline asm   │
│                                                                  │
│   Phase 4.5: Final Cutover                                      │
│       └── Delete core/src/*.c                                   │
│       └── Vir compiles itself without any C                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Phase 4.1: IR Lowering — ✅ HOÀN TẤT (24/03/2026)

**Kết quả:** C engine `ir_lower.c` (2,102 LOC) xử lý thành công toàn bộ `virc.vri` (~9,107 LOC Vir):
- **601 hàm** lowered, **33,187 lệnh Q-IR** sinh ra
- **0 lỗi**, 0 crash, ASAN verified
- 15 fix áp dụng: 12 expr/stmt + 3 crash + 3 zero-error

**Vir-side `ir_optimizer.vri`** (~1,995 LOC, 3-Pass Lowerer) đã sẵn sàng.

**Cần bổ sung cho Phase 4.5 (Kill C):**

| AST Node | Q-IR Pattern | Độ phức tạp |
|----------|--------------|-------------|
| `AST_TRY` | Q_TRY_START/END/THROW | Medium |
| `AST_ASYNC_FUNC` | Q_TASK_SPAWN | Medium |
| `AST_MATCH` | Jump table + Q_CMP | High |
| `AST_GENERIC` | Type instantiation | High |
| **Total** | ~500 LOC mới |

**Test:** `ir_lower_vtest.vri` — Verify output matches C `ir_lower.c`

### 3.2.1 Phase 4.1C: Stack Spilling + Higher-Order Calls — ✅ DONE

> **Thêm ngày:** 02/04/2026  
> **Lý do:** Cả hai là prerequisite cho Phase 4.2 (codegen verification) và Phase 4.3 (bootstrap chain). Không có stack spilling → chương trình lớn (>18 vreg ARM64 / >14 vreg x86) bị silent data corruption. Không có HOF → `f(x)` với f là local var → trả về 0 thay vì gọi hàm.

#### A. Stack Spilling (~200 LOC)

**Vấn đề hiện tại:**
- `codegen.vri` dùng trivial mapping: `vreg_to_arm()` map vreg 0-9 → X19-X28, vreg 10-17 → X0-X7
- **vreg ≥ 18 (ARM64) / ≥ 14 (x86) → silently map to X0/RAX** → data corruption
- IR layer (`ir_lower.c` / `ir_optimizer.vri`) có Linear-Scan RegAlloc + spill slot computation nhưng **codegen KHÔNG consume spill info**
- Hiện tại dùng workaround: vreg recycling (save/restore `next_vreg` per statement)

**Giải pháp:**

```
┌──────────────────────────────────────────────────────────────────┐
│ STACK SPILLING IMPLEMENTATION                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ 1. codegen.vri: vreg_to_arm() khi vreg ≥ 18:                    │
│    - Compute spill offset: (vreg - 18) * 8                      │
│    - Emit STR Xtemp, [SP, #offset] sau mỗi DEF                  │
│    - Emit LDR Xtemp, [SP, #offset] trước mỗi USE                │
│    - Dùng X16 làm scratch register (caller-saved, convention)   │
│                                                                   │
│ 2. Function prologue/epilogue:                                   │
│    - SUB SP, SP, #(num_spill_slots * 8) tại prologue            │
│    - ADD SP, SP, #(num_spill_slots * 8) tại epilogue            │
│                                                                   │
│ 3. Track max vreg dùng trong function → tính spill frame size   │
│                                                                   │
│ 4. x86: tương tự với [RBP - offset], dùng R11 scratch           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Files cần sửa:**

| File | Thay đổi | LOC |
|------|---------|-----|
| `codegen.vri` | `vreg_to_arm()` + `vreg_to_x86()`: emit spill STR/LDR | +80 |
| `codegen.vri` | Function prologue/epilogue: SP adjustment | +40 |
| `codegen.vri` | Track `max_vreg` per function | +20 |
| `main.vri` | Pass spill info from IR to codegen | +10 |
| `test_spill.vri` | Test: >18 local vars trên ARM64 | +50 |
| **TỔNG** | | **~200** |

**Test verification:**
```vir
# test_spill.vri — 20+ local variables, forces stack spilling
func main:
    let a=1; let b=2; let c=3; let d=4; let e=5;
    let f=6; let g=7; let h=8; let i=9; let j=10;
    let k=11; let l=12; let m=13; let n=14; let o=15;
    let p=16; let q=17; let r=18; let s=19; let t=20;
    print(a+b+c+d+e+f+g+h+i+j+k+l+m+n+o+p+q+r+s+t); # expect 210
end
```

#### B. Higher-Order Calls (~250 LOC)

**Vấn đề hiện tại:**
- Khi gặp `f(x)` với `f` là local variable (không phải tên hàm đã biết), IR lowerer emit `Q_LOAD rd, 0` → dummy
- Q_CALL_INDIRECT **chưa tồn tại** trong `q_ir.h` enum
- VM (`vm.c`) không có handler cho indirect call
- Parser **không hỗ trợ** `fn` as parameter type (`fn(int) -> int`)
- Closure/lambda **chưa có** (future — Phase 5)

**Giải pháp (3 bước):**

```
┌──────────────────────────────────────────────────────────────────┐
│ HIGHER-ORDER CALLS IMPLEMENTATION                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Bước 1: Q_CALL_INDIRECT opcode (~50 LOC)                        │
│   - Thêm Q_CALL_INDIRECT vào q_opcode_t enum (q_ir.h)          │
│   - Format: Q_CALL_INDIRECT rd, vreg_func_idx, [args...]       │
│   - vreg chứa function index (int) → lookup function table     │
│                                                                   │
│ Bước 2: IR Lowering support (~80 LOC)                            │
│   - ir_lower.c AST_CALL: nếu callee là local var →             │
│     emit Q_CALL_INDIRECT thay vì Q_CALL                         │
│   - ir_optimizer.vri: tương tự cho Vir-side lowerer            │
│                                                                   │
│ Bước 3: VM handler (~50 LOC)                                     │
│   - vm.c: case Q_CALL_INDIRECT:                                  │
│     - Read func_idx from vreg                                    │
│     - Lookup vm->functions[func_idx]                             │
│     - Push call frame, dispatch                                  │
│                                                                   │
│ Bước 4: Parser fn-type syntax (~70 LOC)                          │
│   - parser.vri: parse `fn(Type,...) -> RetType` as type ann     │
│   - Cho phép: `func apply(f: fn(int)->int, x: int) -> int`     │
│   - Chưa cần closure capture (Phase 5)                          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Files cần sửa:**

| File | Thay đổi | LOC |
|------|---------|-----|
| `core/include/q_ir.h` | Thêm `Q_CALL_INDIRECT` vào enum | +5 |
| `core/src/ir_lower.c` | AST_CALL: emit indirect khi callee là var | +40 |
| `core/src/vm.c` | `case Q_CALL_INDIRECT:` handler | +50 |
| `ir_optimizer.vri` | Vir-side: emit indirect call | +40 |
| `parser.vri` | Parse `fn(T,...)->T` type syntax | +70 |
| `codegen.vri` | Emit BLR Xn (indirect branch) thay vì BL label | +20 |
| `test_hof.vri` | Test: pass function as argument, call it | +30 |
| **TỔNG** | | **~255** |

**Test verification:**
```vir
# test_hof.vri — higher-order function call
func apply(f: fn(int)->int, x: int) -> int:
    out f(x);
end

func double(n: int) -> int:
    out n * 2;
end

func main:
    let result = apply(double, 21);
    print(result);  # expect 42
end
```

**Dependency:** HOF là prerequisite cho closures (Phase 5), callback patterns trong stdlib, và event loop async runtime.

---

### 3.3 Phase 4.2: Codegen Verification

> **[AUDIT-FIX S-05 — 2026-04-02]** Back-patch loop trong `main.vri` đã được vá: nếu label không tìm thấy, compiler bây giờ in `[codegen ERROR] unresolved label N — branch left unpatched` thay vì để branch sai im lặng. Điều này loại bỏ một class lỗi silent wrong control flow quan trọng trước khi bắt đầu Codegen Verification.

**Mục tiêu:** `codegen.vri` emit identical machine code to `codegen.c`

```vir
# Test strategy:
func verify_codegen(source: str) -> bool:
    # Compile with C engine
    let c_binary = shell("./build/vir compile " + source)
    
    # Compile with Vir compiler
    let vir_binary = virc_compile(source)
    
    # Compare disassembly
    let c_asm = shell("objdump -d " + c_binary)
    let vir_asm = shell("objdump -d " + vir_binary)
    
    return c_asm == vir_asm
end
```

**Checklist:**

- [ ] x86_64: REX prefixes, ModR/M encoding
- [ ] ARM64: Fixed-width 32-bit instructions
- [ ] Relocations: GOT, PLT entries
- [ ] Mach-O headers: LC_SEGMENT_64, LC_SYMTAB
- [ ] ELF headers: PT_LOAD, SHT_SYMTAB

### 3.4 Phase 4.3: Bootstrap Chain Hoàn chỉnh

> **[AUDIT-FIX S-02 — 2026-04-02]** Parser `stdlib/vir/compiler/parser.vri` đã được vá: thêm field `p_errors: Vec<string>` để tích lũy **tất cả** lỗi parse thay vì chỉ ghi nhận lỗi đầu tiên. Khi bootstrap chain thất bại, error messages bây giờ hiển thị toàn bộ danh sách lỗi, giúp chẩn đoán nhanh hơn.

```
┌─────────────────────────────────────────────────────────────────┐
│                    BOOTSTRAP CHAIN                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Stage 0: virc.vri (source)                                    │
│       ↓ compiled by C engine                                    │
│   Stage 1: virc_stage1 (binary)                                 │
│       ↓ compiles virc.vri                                       │
│   Stage 2: virc_stage2 (binary)                                 │
│       ↓ compiles virc.vri                                       │
│   Stage 3: virc_stage3 (binary)                                 │
│                                                                  │
│   FIXED-POINT: diff stage2 stage3 = IDENTICAL                   │
│                                                                  │
│   SUCCESS: Stage 2+ are pure Vir, no C involved                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Verification:**
```bash
# Stage 1: C engine compiles Vir compiler
./build/vir compile stdlib/vir/compiler/virc.vri -o virc_stage1

# Stage 2: Vir compiler compiles itself
./virc_stage1 stdlib/vir/compiler/virc.vri -o virc_stage2

# Stage 3: Self-compiled compiler compiles itself
./virc_stage2 stdlib/vir/compiler/virc.vri -o virc_stage3

# Verify fixed-point
diff virc_stage2 virc_stage3  # Must be identical
```

### 3.5 Phase 4.4: Syscall Wrappers

**Thay thế `bridge_native.c` bằng Q_SYSCALL + inline assembly:**

```vir
# stdlib/vir/os/syscall.vri

# Linux syscall numbers
const SYS_READ = 0
const SYS_WRITE = 1
const SYS_OPEN = 2
const SYS_CLOSE = 3
const SYS_MMAP = 9
const SYS_MPROTECT = 10
const SYS_FORK = 57
const SYS_EXECVE = 59
const SYS_PIPE = 22
const SYS_DUP2 = 33

# Direct syscall wrapper
func syscall6(num: i64; a1: i64; a2: i64; a3: i64; a4: i64; a5: i64; a6: i64) -> i64:
    # Uses Q_SYSCALL with register window
    return __syscall__(num, a1, a2, a3, a4, a5, a6)
end

# High-level wrappers
func write(fd: i32; buf: ptr; len: i64) -> i64:
    return syscall6(SYS_WRITE, fd, buf >> i64, len, 0, 0, 0)
end

func mmap(addr: ptr; len: i64; prot: i32; flags: i32; fd: i32; off: i64) -> ptr:
    return syscall6(SYS_MMAP, addr >> i64, len, prot, flags, fd, off) >> ptr
end
```

**IoT Wrappers (Linux-specific):**
```vir
# stdlib/vir/hw/gpio_linux.vri

const GPIO_V2_GET_LINE = 0xC250B407  # ioctl magic

func gpio_set(chip: i32; line: i32; value: i32) -> i32:
    let req = GpioLineRequest {
        lines: [line],
        config: GpioLineConfig { flags: GPIO_V2_LINE_FLAG_OUTPUT },
    }
    return ioctl(chip, GPIO_V2_GET_LINE, req >> ptr)
end
```

### 3.6 Phase 4.5: Final Cutover

**Bước cuối cùng — Xóa C hoàn toàn:**

```bash
# 1. Verify Vir compiler works standalone
./virc_stage2 test.vri -o test && ./test

# 2. Archive C source (không xóa vĩnh viễn)
mv core/src core/src_c_archive

# 3. Create new entry point
cat > core/main.vri << 'EOF'
include "stdlib/vir/compiler/virc.vri"

func main(args: [str]) -> i32:
    return virc_main(args)
end
EOF

# 4. Build native Vir binary from Stage 2 compiler
./virc_stage2 core/main.vri -o vir

# 5. Verify
./vir compile test.vri -o test && ./test
echo "C HAS BEEN KILLED"
```

---

## 4. Stage 5: Siêu năng lực

### 4.1 Borrow Checker — An toàn Bộ nhớ

**Mục tiêu:** Memory safety như Rust nhưng KHÔNG cần GC, và cú pháp đơn giản hơn.

#### 4.1.1 Ownership Model

```vir
# Ownership annotation (đơn giản hơn Rust)
func process(data: own [i32]) -> own [i32]:
    # 'own' = exclusive ownership, auto-dropped at scope end
    return data.map(|x| x * 2)
end

func borrow_read(data: &[i32]) -> i32:
    # '&' = shared borrow, read-only
    return data.sum()
end

func borrow_mut(data: &mut [i32]):
    # '&mut' = exclusive mutable borrow
    data[0] = 100
end

# Usage:
let arr: own [i32] = [1, 2, 3]
let sum = borrow_read(&arr)      # OK: shared borrow
borrow_mut(&mut arr)             # OK: exclusive borrow
let arr2 = process(arr)          # arr moved, can't use arr anymore
```

#### 4.1.2 Borrow Checker Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│                    BORROW CHECKER PASS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. Build Lifetime Graph                                       │
│      - Track variable creation (birth)                          │
│      - Track last use (death)                                   │
│      - Track borrows (edges)                                    │
│                                                                  │
│   2. Check Rules                                                │
│      - At any point: 1 mutable borrow XOR N shared borrows     │
│      - Borrowed data cannot be moved                            │
│      - Borrows cannot outlive owner                             │
│                                                                  │
│   3. Insert Drops                                               │
│      - At scope end: drop owned values                          │
│      - Early drop: if value moved                               │
│                                                                  │
│   4. Error Messages (Rust-like quality)                         │
│      - "cannot borrow `x` as mutable because..."               │
│      - Visual spans showing conflict                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.1.3 Implementation Plan

| # | Task | LOC | Priority |
|---|------|-----|----------|
| 1 | Lifetime annotations parser | ~200 | P0 |
| 2 | Ownership type system | ~500 | P0 |
| 3 | Borrow graph builder | ~400 | P0 |
| 4 | Conflict detection | ~300 | P0 |
| 5 | Drop insertion pass | ~200 | P0 |
| 6 | Error message formatter | ~300 | P1 |
| **Total** | | **~1,900** |

### 4.2 Event Loop — Async Runtime

**Mục tiêu:** Cạnh tranh trực tiếp với Go/Node.js cho server-side.

#### 4.2.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIR EVENT LOOP                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │   Timer     │     │   I/O       │     │   Signal    │      │
│   │   Queue     │     │   Poller    │     │   Handler   │      │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘      │
│          │                   │                   │              │
│          └───────────────────┼───────────────────┘              │
│                              ▼                                  │
│                     ┌─────────────────┐                         │
│                     │   Event Queue   │                         │
│                     │   (Lock-free)   │                         │
│                     └────────┬────────┘                         │
│                              │                                  │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │   Worker 0  │     │   Worker 1  │     │   Worker N  │      │
│   │   (Thread)  │     │   (Thread)  │     │   (Thread)  │      │
│   └─────────────┘     └─────────────┘     └─────────────┘      │
│                                                                  │
│   Platform: kqueue (macOS) / epoll (Linux) / io_uring (Linux)  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.2.2 API Design

```vir
# async/await syntax (đã có parser support)
async func fetch_data(url: str) -> Result[str; Error]:
    let conn = await TcpStream.connect(url)
    let response = await conn.read_all()
    return Ok(response)
end

# Spawn tasks
func main():
    let runtime = Runtime.new(workers: 4)
    
    # Spawn thousands of concurrent tasks
    for i in 0..10000:
        runtime.spawn(fetch_data("http://example.com"))
    end
    
    # Wait for all
    runtime.block_on_all()
end

# Channels (Go-style)
func producer(tx: Sender[i32]):
    for i in 0..100:
        tx.send(i)
    end
end

func consumer(rx: Receiver[i32]):
    while let Some(val) = rx.recv():
        print(val)
    end
end
```

#### 4.2.3 I/O Poller Implementation

```vir
# stdlib/vir/async/poller.vri

entity Poller:
    fd: i32          # kqueue/epoll fd
    events: [Event]  # registered events
end

method Poller.new() -> Poller:
    #[cfg(target_os = "macos")]
    let fd = syscall(SYS_KQUEUE)
    
    #[cfg(target_os = "linux")]
    let fd = syscall(SYS_EPOLL_CREATE1, 0)
    
    return Poller { fd: fd, events: [] }
end

method Poller.register(p: &mut Poller; fd: i32; interest: Interest):
    #[cfg(target_os = "macos")]
    let kev = kevent { ident: fd, filter: EVFILT_READ, flags: EV_ADD }
    syscall(SYS_KEVENT, p.fd, &kev, 1, null, 0, null)
    
    #[cfg(target_os = "linux")]
    let ev = epoll_event { events: EPOLLIN, data: fd }
    syscall(SYS_EPOLL_CTL, p.fd, EPOLL_CTL_ADD, fd, &ev)
end

method Poller.poll(p: &mut Poller; timeout_ms: i32) -> [Event]:
    #[cfg(target_os = "macos")]
    let ts = timespec { tv_sec: timeout_ms / 1000, tv_nsec: (timeout_ms % 1000) * 1_000_000 }
    let n = syscall(SYS_KEVENT, p.fd, null, 0, p.events.ptr, p.events.cap, &ts)
    
    return p.events[0..n]
end
```

#### 4.2.4 Implementation Plan

| # | Task | LOC | Priority |
|---|------|-----|----------|
| 1 | Event Queue (lock-free) | ~400 | P0 |
| 2 | Poller (kqueue/epoll) | ~500 | P0 |
| 3 | Worker Pool | ~300 | P0 |
| 4 | Task Scheduler | ~400 | P0 |
| 5 | Future/Promise impl | ~300 | P0 |
| 6 | Channel (mpsc/mpmc) | ~400 | P1 |
| 7 | Timer wheel | ~200 | P1 |
| 8 | io_uring backend | ~300 | P2 |
| **Total** | | **~2,800** |

### 4.3 Package Manager — `vpm`

**Mục tiêu:** Xây dựng cộng đồng và ecosystem.

#### 4.3.1 Design Principles

```
┌─────────────────────────────────────────────────────────────────┐
│                    VPM DESIGN                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. FAST                                                       │
│      - Content-addressable storage (like Nix)                   │
│      - Parallel downloads                                       │
│      - Lockfile for reproducibility                             │
│                                                                  │
│   2. SECURE                                                     │
│      - Package signing (Ed25519)                                │
│      - Checksum verification                                    │
│      - Audit dependencies                                       │
│                                                                  │
│   3. SIMPLE                                                     │
│      - Single manifest file (vir.pkg)                           │
│      - No complex config options                                │
│      - Sensible defaults                                        │
│                                                                  │
│   4. DECENTRALIZED                                              │
│      - Multiple registries supported                            │
│      - Git dependencies                                         │
│      - Local path dependencies                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.3.2 Manifest Format

```vir
# vir.pkg

[package]
name = "my-web-app"
version = "1.0.0"
authors = ["developer@example.com"]
license = "MIT"

[dependencies]
http = "^2.0"              # Registry dependency
json = { git = "https://github.com/vir/json.git", tag = "v1.0" }
local-lib = { path = "../local-lib" }

[dev-dependencies]
vtest = "^1.0"

[build]
target = "native"          # or "wasm"
optimize = "release"       # "debug" | "release" | "size"

[features]
default = ["http/tls"]
full = ["http/tls", "http/http2", "json/simd"]
```

#### 4.3.3 Command Interface

```bash
# Initialize new project
vpm init my-project

# Add dependency
vpm add http@^2.0

# Install all dependencies
vpm install

# Build project
vpm build --release

# Run tests
vpm test

# Publish to registry
vpm publish

# Audit security
vpm audit
```

#### 4.3.4 Registry Server

```vir
# vpm-registry/server.vri

entity RegistryServer:
    db: Database
    storage: ObjectStore  # S3-compatible
    cache: RedisClient
end

# API endpoints
route GET "/api/v1/packages/:name" -> handler_get_package
route GET "/api/v1/packages/:name/:version" -> handler_get_version
route POST "/api/v1/packages" -> handler_publish
route GET "/api/v1/search" -> handler_search

method handler_publish(req: Request) -> Response:
    let pkg = req.json() >> Package
    
    # Verify signature
    if not verify_signature(pkg.signature, pkg.author_key):
        return Response.forbidden("Invalid signature")
    end
    
    # Store tarball
    let tarball_sha = storage.put(pkg.tarball)
    
    # Update database
    db.insert("packages", {
        name: pkg.name,
        version: pkg.version,
        tarball_sha: tarball_sha,
        dependencies: pkg.dependencies,
        created_at: now(),
    })
    
    # Invalidate cache
    cache.delete("pkg:" + pkg.name)
    
    return Response.ok({ success: true })
end
```

#### 4.3.5 Implementation Plan

| # | Task | LOC | Priority |
|---|------|-----|----------|
| 1 | Manifest parser | ~300 | P0 |
| 2 | Dependency resolver | ~600 | P0 |
| 3 | Registry client | ~400 | P0 |
| 4 | Download/unpack | ~300 | P0 |
| 5 | Lockfile | ~200 | P0 |
| 6 | Build integration | ~300 | P1 |
| 7 | Registry server | ~800 | P1 |
| 8 | Security audit | ~400 | P2 |
| **Total** | | **~3,300** |

---

## 5. Stage 6: Thống lĩnh

### 5.1 Hệ sinh thái Cốt lõi

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIR ECOSYSTEM                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   TIER 1 — Core (Must have)                                     │
│   ├── vir          Compiler + Runtime                           │
│   ├── vpm          Package Manager                              │
│   ├── vtest        Testing Framework                            │
│   └── vfmt         Code Formatter                               │
│                                                                  │
│   TIER 2 — Tooling                                              │
│   ├── vir-lsp      Language Server Protocol                     │
│   ├── vir-debug    Debugger (DAP)                               │
│   ├── vir-doc      Documentation Generator                      │
│   └── vir-bench    Benchmarking Suite                           │
│                                                                  │
│   TIER 3 — Libraries                                            │
│   ├── http         HTTP client/server                           │
│   ├── json         JSON parsing/serialization                   │
│   ├── sql          Database drivers                             │
│   ├── crypto       Cryptography primitives                      │
│   ├── ml           Machine Learning (Tensor, Neural Nets)       │
│   └── ui           Cross-platform GUI                           │
│                                                                  │
│   TIER 4 — Applications                                         │
│   ├── vir-shell    Interactive REPL                             │
│   ├── vir-play     Online Playground                            │
│   └── vir-hub      Package Registry                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Target Markets

| Market | Use Case | Competitive Advantage |
|--------|----------|----------------------|
| **Systems** | OS, drivers, embedded | C performance + memory safety |
| **Backend** | Web servers, microservices | Go concurrency + Rust safety |
| **AI/ML** | Neural networks, data processing | Python ease + C performance |
| **WebAssembly** | Browser apps, edge computing | Native WASM codegen |
| **Mobile** | iOS/Android native | Single codebase |
| **Desktop** | Cross-platform GUI | Native performance |

### 5.3 Community Building

```
YEAR 1: Foundation
├── Release vir 1.0 stable
├── Launch vpm registry
├── VSCode extension (full LSP)
├── 100+ stdlib packages
└── First 1,000 GitHub stars

YEAR 2: Growth
├── First major company adoption
├── VirConf conference
├── 10+ core contributors
├── 10,000+ stars
└── First book published

YEAR 3: Maturity
├── Fortune 500 adoption
├── University curricula
├── 100+ contributors
├── 50,000+ stars
└── Industry recognition
```

---

## 6. Adaptive JIT: Chìa khóa Hiệu suất

### 6.1 Safe/Fast Variant Switching

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE JIT                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Function Entry                                                │
│       │                                                         │
│       ▼                                                         │
│   ┌──────────────┐                                              │
│   │ Call Counter │ < 100 ──────────────────────┐               │
│   └──────┬───────┘                             │               │
│          │ >= 100                              ▼               │
│          ▼                              ┌─────────────┐        │
│   ┌─────────────────┐                   │ Interpreter │        │
│   │ Tier 1 Compile  │                   │   (Safe)    │        │
│   │ (Safe Variant)  │                   └─────────────┘        │
│   └──────┬──────────┘                                          │
│          │                                                      │
│          ▼                                                      │
│   ┌──────────────┐                                              │
│   │ Call Counter │ < 10000 ─────────────────────┐              │
│   └──────┬───────┘                              │              │
│          │ >= 10000                             ▼              │
│          ▼                                ┌─────────────┐      │
│   ┌─────────────────┐                     │   Tier 1    │      │
│   │ Tier 2 Compile  │                     │   (JIT)     │      │
│   │ (Fast Variant)  │                     └─────────────┘      │
│   └──────┬──────────┘                                          │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────┐     Exception?     ┌─────────────┐       │
│   │    Tier 2       │ ─────────────────► │  Blacklist  │       │
│   │    (Fast)       │     Deopt          │ Fallback    │       │
│   └─────────────────┘                    │ to Tier 1   │       │
│                                          └─────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Safe Variant

```vir
# Generates bounds checks, null checks, overflow checks
func safe_array_sum(arr: [i32]) -> i32:
    let sum = 0
    for i in 0..arr.len:
        # Bounds check: if i >= arr.len then panic
        Q_BOUNDS_CHECK(i, arr.len)
        sum = sum + arr[i]
    end
    return sum
end

# Emitted Q-IR:
# L0: LOAD_ARR_LEN %len, %arr
# L1: CMP_LT %i, %len
# L2: JUMP_IF_NOT L_panic
# L3: ARR_GET %tmp, %arr, %i
# ...
```

### 6.3 Fast Variant

```vir
# No checks, maximum speed
func fast_array_sum(arr: [i32]) -> i32:
    let sum = 0
    let len = arr.len
    let ptr = arr.data
    
    # SIMD vectorization if len >= 4
    while len >= 4:
        let v = SIMD.load_i32x4(ptr)
        sum = sum + SIMD.hsum(v)
        ptr = ptr + 16
        len = len - 4
    end
    
    # Scalar epilog
    while len > 0:
        sum = sum + *ptr
        ptr = ptr + 4
        len = len - 1
    end
    
    return sum
end

# Emitted native (ARM64):
# LDP Q0, Q1, [X0], #32
# ADDV S2, V0.4S
# ADDV S3, V1.4S
# FADD S0, S2, S3
# ...
```

### 6.4 Blacklist Mechanism

```vir
# stdlib/vir/jit/blacklist.vri

share _blacklist: Map[FuncId; BlacklistEntry]

entity BlacklistEntry:
    func_id: FuncId
    fail_count: i32
    last_fail: Timestamp
    reason: str
end

func should_use_fast(func_id: FuncId) -> bool:
    if _blacklist.has(func_id):
        let entry = _blacklist.get(func_id)
        
        # Try again after cooldown (exponential backoff)
        if now() - entry.last_fail > 2 ^ entry.fail_count * 1000:
            return true  # Retry fast variant
        end
        
        return false  # Use safe variant
    end
    return true
end

func report_fast_failure(func_id: FuncId; reason: str):
    if _blacklist.has(func_id):
        let entry = _blacklist.get(func_id)
        entry.fail_count = entry.fail_count + 1
        entry.last_fail = now()
        entry.reason = reason
    else:
        _blacklist.set(func_id, BlacklistEntry {
            func_id: func_id,
            fail_count: 1,
            last_fail: now(),
            reason: reason,
        })
    end
    
    # Patch call site to use safe variant
    patch_call_site(func_id, get_safe_variant(func_id))
end
```

### 6.5 PGO Integration

```vir
# stdlib/vir/jit/pgo.vri

entity ProfileData:
    call_counts: Map[FuncId; i64]
    branch_taken: Map[BranchId; i64]
    branch_not_taken: Map[BranchId; i64]
    type_feedback: Map[CallSite; [TypeTag]]
end

func optimize_with_profile(func: QFunction; profile: ProfileData) -> QFunction:
    let opt = func.clone()
    
    # 1. Inline hot callees
    for (callee, count) in profile.call_counts:
        if count > 10000 and callee.size < 50:
            opt = inline_function(opt, callee)
        end
    end
    
    # 2. Reorder branches by probability
    for (branch_id, taken) in profile.branch_taken:
        let not_taken = profile.branch_not_taken.get(branch_id)
        if taken > not_taken * 10:
            opt = mark_likely(opt, branch_id, true)
        elif not_taken > taken * 10:
            opt = mark_likely(opt, branch_id, false)
        end
    end
    
    # 3. Specialize by observed types
    for (site, types) in profile.type_feedback:
        if types.len == 1:
            opt = specialize_call(opt, site, types[0])
        end
    end
    
    return opt
end
```

---

## 7. Lộ trình Thực hiện

### 7.1 Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION TIMELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Q2 2026 (Apr-Jun): STAGE 4 — Kill C                           │
│   ├── Week 1-2: Complete ir_lower.vri                           │
│   ├── Week 3-4: Verify codegen.vri                              │
│   ├── Week 5-6: Bootstrap chain                                 │
│   ├── Week 7-8: Syscall wrappers                                │
│   └── Week 9-10: Final cutover + validation                     │
│                                                                  │
│   Q3 2026 (Jul-Sep): STAGE 5a — Borrow Checker                  │
│   ├── Month 1: Ownership type system                            │
│   ├── Month 2: Borrow graph + conflict detection                │
│   └── Month 3: Drop insertion + error messages                  │
│                                                                  │
│   Q4 2026 (Oct-Dec): STAGE 5b — Event Loop                      │
│   ├── Month 1: Poller (kqueue/epoll)                            │
│   ├── Month 2: Task scheduler + workers                         │
│   └── Month 3: async/await runtime                              │
│                                                                  │
│   Q1 2027 (Jan-Mar): STAGE 5c — Package Manager                 │
│   ├── Month 1: vpm CLI + manifest                               │
│   ├── Month 2: Registry server                                  │
│   └── Month 3: Launch vir-hub.org                               │
│                                                                  │
│   Q2 2027: STAGE 6 — Launch                                     │
│   ├── Vir 1.0 stable release                                    │
│   ├── Documentation + tutorials                                 │
│   └── Community outreach                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 LOC Estimates

| Stage | Component | LOC | Cumulative |
|-------|-----------|-----|------------|
| **4** | Kill C | ~2,000 | 2,000 |
| **5a** | Borrow Checker | ~1,900 | 3,900 |
| **5b** | Event Loop | ~2,800 | 6,700 |
| **5c** | Package Manager | ~3,300 | 10,000 |
| **6** | Ecosystem | ~5,000 | 15,000 |
| **Total** | | **~15,000 LOC** |

### 7.3 Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY GRAPH                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Stage 4 ────────────────────────────────────────────┐         │
│   (Kill C)                                            │         │
│       │                                               │         │
│       ▼                                               ▼         │
│   Stage 5a                                        Stage 5c      │
│   (Borrow Checker)                               (vpm)         │
│       │                                               │         │
│       ▼                                               │         │
│   Stage 5b ◄──────────────────────────────────────────┘         │
│   (Event Loop)                                                  │
│       │                                                         │
│       ▼                                                         │
│   Stage 6                                                       │
│   (Launch)                                                      │
│                                                                  │
│   Note: 5a and 5c can proceed in parallel after Stage 4        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Metrics Thành công

### 8.1 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Bootstrap** | Stage 3 = Stage 4 | Binary diff |
| **Performance** | Within 5% of C | Benchmark suite |
| **Memory Safety** | 0 unsafe escapes | Static analysis |
| **Test Coverage** | > 80% | Line coverage |
| **Build Time** | < 10s for stdlib | CI measurement |

### 8.2 Community Metrics

| Metric | Year 1 | Year 2 | Year 3 |
|--------|--------|--------|--------|
| **GitHub Stars** | 1,000 | 10,000 | 50,000 |
| **Contributors** | 10 | 50 | 200 |
| **Packages** | 100 | 1,000 | 5,000 |
| **Downloads** | 10K | 100K | 1M |
| **Companies** | 5 | 50 | 500 |

### 8.3 Competitive Benchmarks

```
Target: Vir should rank in TOP 3 for each category

SYSTEMS PROGRAMMING:
├── Compile Time: Faster than Rust
├── Runtime: Within 5% of C
├── Memory Safety: Equal to Rust
└── Binary Size: Smaller than Go

SERVER-SIDE:
├── Throughput: Higher than Go
├── Latency: Lower than Node.js
├── Concurrency: 1M+ connections
└── Memory Usage: Lower than Java

AI/ML:
├── Training Speed: Faster than PyTorch
├── Inference: Faster than TensorFlow
├── Model Size: Smaller than ONNX
└── Ease of Use: Equal to Keras
```

---

## Kết luận

Vir đang ở ngưỡng cửa của **cuộc cách mạng**:

1. **Python đã chết** — Testing và development không còn phụ thuộc Python
2. **C sắp chết** — Bootstrap chain đã hoạt động, chỉ cần 2,000 LOC để hoàn tất
3. **Adaptive JIT** — Chìa khóa để đạt hiệu suất vượt trội trong khi vẫn an toàn
4. **Borrow Checker + Event Loop + vpm** — Tam giác vàng để thống lĩnh

**Công thức cuối cùng:**

```
VIR = 
    Rust's Memory Safety (Borrow Checker)
  + Go's Concurrency (Event Loop + Goroutines)
  + C's Performance (Zero-cost Abstractions)
  + Python's Ecosystem (vpm + 5000+ packages)
  + Self-Hosting (Zero External Dependencies)
  + Adaptive JIT (Safe/Fast Switching)
  ────────────────────────────────────────
  = HIỆN TƯỢNG KỲ LẠ trong Giới Ngôn ngữ Lập trình
```

**Vir không phải là "ngôn ngữ mới nữa". Vir là TƯƠNG LAI.**

---

*Kế hoạch chiến lược — 22/03/2026*
*Version 1.0 — "Kill C" Master Plan*
