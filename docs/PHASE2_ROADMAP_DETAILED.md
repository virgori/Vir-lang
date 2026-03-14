# VIR PHASE 2 — LỘ TRÌNH KỸ THUẬT CHI TIẾT

> **Ngày**: 10/03/2026  
> **Mục đích**: Dev guide đủ chi tiết để thực thi ngay — thuật toán, data source, file cần sửa, pseudocode.  
> **Cấu trúc**: 3 trụ cột × 14 task × mỗi task có [Hiện trạng → Thuật toán → File → Steps]

---

## MỤC LỤC

**Trụ cột A — Tối ưu kiến trúc (Optimization)**
- [A1. Pattern Matching (:~) với Decision Tree](#a1-pattern-matching--với-decision-tree)
- [A2. Async/Task Semantics — Green Threads](#a2-asynctask-semantics--green-threads)
- [A3. Vectorized I/O — simdjson-style](#a3-vectorized-io--simdjson-style)
- [A4. AMX Backend (Apple Matrix Extensions)](#a4-amx-backend-apple-matrix-extensions)
- [A5. AVX-512 Stable JIT — ZMM Register Fix](#a5-avx-512-stable-jit--zmm-register-fix)

**Trụ cột B — Metadata-Driven Codegen (Scalability)**
- [B1. Script tự động cập nhật Metadata](#b1-script-tự-động-cập-nhật-metadata)
- [B2. Meta-Compiler: Metadata → generated_codegen.c](#b2-meta-compiler-metadata--generated_codegenc)

**Trụ cột C — Tương thích đa nền tảng (Compatibility)**
- [C1. I-Cache Flush cho ARM64 Self-Patching](#c1-i-cache-flush-cho-arm64-self-patching)
- [C2. Atomic Abstraction Layer (x86 LOCK → ARM LR/SC → RISC-V)](#c2-atomic-abstraction-layer)
- [C3. Alignment Audit cho RISC-V](#c3-alignment-audit-cho-risc-v)

**Trụ cột D — GPU & CUDA (Zero-Dependency)**
- [D1. CUDA Driver FFI Bridge](#d1-cuda-driver-ffi-bridge)
- [D2. PTX Emitter (Q-IR → PTX)](#d2-ptx-emitter-q-ir--ptx)
- [D3. Apple Metal/AIR Backend](#d3-apple-metalair-backend)
- [D4. GPU Kernel Library (GEMM, Fusion, Coalesced Access)](#d4-gpu-kernel-library)

---

## Trụ cột A — Tối ưu kiến trúc

---

### A1. Pattern Matching (`:~`) với Decision Tree

#### Hiện trạng
- `TOK_PATTERN_MATCH` token đã khai báo trong `core/include/lexer.h`
- Parser (`core/src/parser.c`) **chưa có** `parse_pattern_match()` handler
- IR lower (`core/src/ir_lower.c`) **chưa có** AST node cho pattern match
- Virgex engine (`virgex/`) cung cấp pattern matching string nhưng **chưa kết nối** với `:~`

#### Thuật toán: Decision Tree Compilation

Thay vì chuỗi `if-else` tuần tự O(n), compile pattern match thành **Decision Tree** O(log n):

```
THUẬT TOÁN: Compile Pattern Match → Decision Tree

Input: patterns[] = [(pattern₁, action₁), (pattern₂, action₂), ...]
Output: Q-IR instructions (tree of CMP + JUMP)

1. PHÂN TÍCH PATTERN
   Mỗi pattern được phân tách thành:
   - Literal match:  x :~ 42        → CMP_EQ(x, 42)
   - Range match:    x :~ 1..10     → CMP_GE(x, 1) AND CMP_LE(x, 10)
   - Type guard:     x :~ int       → TYPE_CHECK(x, INT)
   - Wildcard:       x :~ _         → (always true, default branch)
   - Destructor:     (a, b) :~ pair → LOAD_FIELD(pair, 0) → a, LOAD_FIELD(pair, 1) → b

2. XÂY DỰNG DECISION TREE (Greedy Column Selection)
   function build_tree(patterns, column=0):
     if all patterns matched → emit action
     if no patterns left → emit ERROR("no match")
     
     # Chọn cột (column) có ít giá trị distinct nhất → split tốt nhất
     best_col = argmin(col, count_distinct(patterns[col]))
     
     # Partition patterns theo giá trị tại best_col
     for each unique value v in patterns[best_col]:
       subset = filter(patterns, row[best_col] == v)
       children[v] = build_tree(subset, next_column)
     
     return DecisionNode(test=best_col, children)

3. EMIT Q-IR
   function emit_decision(node, target_vreg):
     if node.is_leaf:
       emit Q_JUMP → action_label
     else:
       for each (value, child) in node.children:
         emit Q_CMP_EQ target_vreg, value → tmp
         emit Q_JUMP_IF tmp → child_label
       emit Q_JUMP → default_label  # wildcard / error
```

**Ví dụ biến đổi:**
```vir
# Source (Vir v1.2)
case color :~
    "red":   out 1;
    "green": out 2;
    "blue":  out 3;
    _:       out 0;
end

# Q-IR output (Decision Tree)
  CMP_EQ R0, "red"    → T1
  JUMP_IF T1 → .L_red
  CMP_EQ R0, "green"  → T2
  JUMP_IF T2 → .L_green
  CMP_EQ R0, "blue"   → T3
  JUMP_IF T3 → .L_blue
  JUMP → .L_default
.L_red:    LOAD R_out, 1; RET
.L_green:  LOAD R_out, 2; RET
.L_blue:   LOAD R_out, 3; RET
.L_default: LOAD R_out, 0; RET
```

#### File cần sửa

| File | Thay đổi |
|------|----------|
| `core/include/lexer.h` | Xác nhận `TOK_PATTERN_MATCH` (`:~`) đã có |
| `core/src/lexer.c` | Thêm emit `TOK_PATTERN_MATCH` khi gặp chuỗi `:~` |
| `core/include/ir_lower.h` | Thêm `AST_MATCH`, `AST_MATCH_ARM`, `AST_MATCH_WILDCARD` |
| `core/src/parser.c` | Thêm `parse_match_expr()`: parse `case EXPR :~ ARM₁ ARM₂ ... end` |
| `core/src/ir_lower.c` | Thêm `lower_match()`: build decision tree → emit CMP/JUMP chain |
| `src/qir/opcodes.py` | Thêm `QIR_H.MATCH` opcode (lowered to CMP/JUMP at M level) |
| `core/bootstrap/vir_parser.vri` | Thêm handler `TK_CASE` kết hợp `:~` trong parse_statement |

#### Steps chi tiết

1. **Lexer**: Trong `lexer.c`, thêm check 2-char lookahead cho `:` + `~` → emit `TOK_PATTERN_MATCH`
2. **Parser**: Sau `parse_expr()`, nếu peek == `TOK_PATTERN_MATCH`:
   ```c
   static ASTNode* parse_match_expr(Parser* p) {
       ASTNode* subject = current_expr;  // đã parse
       expect(TOK_PATTERN_MATCH);        // consume :~
       ASTNode* match = ast_new(AST_MATCH);
       match->match.subject = subject;
       while (peek() != TOK_END) {
           ASTNode* arm = parse_match_arm(p);  // pattern : body
           ast_add_child(match, arm);
           skip_newlines();
       }
       expect(TOK_END);
       return match;
   }
   ```
3. **IR Lower**: `lower_match()` — iterate arms, emit `Q_CMP_EQ` + `Q_JUMP_IF` per arm, wildcard `_` → default jump
4. **Optimization (nâng cao)**: Nếu tất cả patterns là integer liên tục (0,1,2,3...) → emit **jump table** thay vì decision tree:
   ```c
   // Jump table: O(1) thay vì O(n)
   emit Q_CMP_GE subject, min_val → T1
   emit Q_CMP_LE subject, max_val → T2
   emit Q_AND T1, T2 → T3
   emit Q_JUMP_IF_NOT T3 → default
   emit Q_JUMP_TABLE subject, [label_0, label_1, ..., label_n]
   ```

---

### A2. Async/Task Semantics — Green Threads

#### Hiện trạng
- **Parser**: `async func`, `task`, `wait` đã được parse (`src/frontend/parser/parser.py:786`)
- **Stdlib**: `stdlib/vir/async/async.vri` có `EventLoop`, `Task`, `Poll<T>`, `Waker` (~200 LOC, 60% impl)
- **THIẾU**: Không có context switching thực sự, không có green thread stack, `yield_now()` là stub

#### Thuật toán: Stackful Green Threads via setjmp/longjmp

```
THUẬT TOÁN: Cooperative Green Thread Scheduler

Cấu trúc dữ liệu:
  TaskControlBlock (TCB):
    - id: uint32
    - state: READY | RUNNING | WAITING | COMPLETED
    - stack_base: void*       // mmap'd stack (64KB mỗi task)
    - stack_size: uint64      // 65536 default
    - context: jmp_buf        // setjmp/longjmp save area
    - entry_fn: void*         // task function pointer
    - result: int64           // return value

  Scheduler:
    - ready_queue: Deque<TCB*>
    - current: TCB*
    - main_context: jmp_buf   // scheduler's own context

KHỞI TẠO TASK:
  function task_create(fn, arg):
    tcb = alloc(sizeof(TCB))
    tcb.stack_base = mmap(NULL, 65536, PROT_READ|PROT_WRITE,
                          MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)
    tcb.state = READY
    tcb.entry_fn = fn
    # Setup initial context: SP points to top of stack
    # Trampoline: khi longjmp vào lần đầu, chạy task_trampoline()
    getcontext(&tcb.context)
    tcb.context.uc_stack.ss_sp = tcb.stack_base
    tcb.context.uc_stack.ss_size = 65536
    makecontext(&tcb.context, task_trampoline, 1, tcb)
    ready_queue.push_back(tcb)

SCHEDULER LOOP:
  function scheduler_run():
    while ready_queue not empty:
      tcb = ready_queue.pop_front()
      tcb.state = RUNNING
      current = tcb
      if setjmp(main_context) == 0:
        longjmp(tcb.context, 1)   // resume task
      # Khi task yield hoặc complete, control returns here
      if tcb.state == COMPLETED:
        munmap(tcb.stack_base, tcb.stack_size)
        free(tcb)

YIELD (từ trong task):
  function yield_now():
    if setjmp(current.context) == 0:
      current.state = READY
      ready_queue.push_back(current)
      longjmp(main_context, 1)    // return to scheduler
    # Khi scheduler longjmp back, execution continues here

WAIT (chờ task khác complete):
  function task_wait(target_id):
    current.state = WAITING
    current.wait_for = target_id
    yield_now()
    # Scheduler sẽ không re-queue WAITING tasks
    # Khi target complete → wake_task(current.id) → push to ready_queue
```

**Lựa chọn implementation:**

| Approach | Ưu điểm | Nhược điểm | Đề xuất |
|----------|---------|------------|---------|
| `setjmp/longjmp` | Portable, đơn giản | Không save FP/SIMD regs | ✅ Phase 1 |
| `ucontext_t` (makecontext) | Full register save, POSIX | Deprecated trên macOS | ⚠️ Linux only |
| Hand-written asm | Fastest, full control | Per-arch maintenance | Phase 2 |
| `_setjmp/_longjmp` | Faster (no signal mask save) | BSD-specific | macOS preferred |

#### File cần tạo/sửa

| File | Thay đổi |
|------|----------|
| `core/src/task.c` (MỚI) | ~400 LOC: TCB, scheduler loop, yield, wait, task_create |
| `core/src/task.h` (MỚI) | Struct definitions, API declarations |
| `core/src/vm.c` | Thêm opcodes: `Q_TASK_SPAWN`, `Q_TASK_YIELD`, `Q_TASK_WAIT` |
| `core/include/q_ir.h` | Khai báo 3 opcodes mới |
| `core/src/ir_lower.c` | Lower `AST_ASYNC_FUNC` → wrap body trong task_create() call |
| `stdlib/vir/async/async.vri` | Wire `yield_now()` và `sleep_async()` vào native task.c |

#### Steps

1. **core/src/task.c**: Implement TCB + deque + scheduler loop dùng `_setjmp/_longjmp` (macOS) hoặc `setjmp/longjmp` (Linux)
2. **Stack allocation**: `mmap(NULL, 65536, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)` — 64KB per task
3. **Context init**: Dùng inline assembly để set RSP (x86) hoặc SP (ARM64) vào top of mmap'd stack, push trampoline address
4. **VM integration**: Khi VM gặp `Q_TASK_SPAWN`, gọi `task_create(fn_ptr, arg)`. Khi gặp `Q_TASK_YIELD`, gọi `yield_now()`
5. **Trampoline**:
   ```c
   static void task_trampoline(TCB* tcb) {
       tcb->result = ((task_fn_t)tcb->entry_fn)(tcb->arg);
       tcb->state = TASK_COMPLETED;
       // Wake any tasks waiting on this one
       scheduler_wake_waiters(tcb->id);
       longjmp(scheduler.main_context, 1);
   }
   ```

---

### A3. Vectorized I/O — simdjson-style

#### Hiện trạng
- `cpu_caps.c:242-264` detect YMM/ZMM nhưng **không dùng cho I/O**
- JSON parser (`stdlib/vir/json/json.vri`) là scalar byte-by-byte
- Không có SIMD parsing nào trong codebase

#### Thuật toán: SIMD Structural Character Classification

Kỹ thuật core của simdjson (Lemire et al. 2019):

```
THUẬT TOÁN: SIMD JSON Structural Index

Mục tiêu: Tìm vị trí tất cả structural characters ({}[],:"\n) 
          trong buffer 64 bytes chỉ bằng 3-5 SIMD instructions.

BƯỚC 1: LOAD 64 bytes vào 2 thanh ghi YMM (AVX2) hoặc 1 ZMM (AVX-512)
  __m256i chunk0 = _mm256_loadu_si256(buf);       // bytes 0-31
  __m256i chunk1 = _mm256_loadu_si256(buf + 32);  // bytes 32-63

BƯỚC 2: SO SÁNH SONG SONG — Tạo bitmask cho mỗi loại ký tự
  // Tìm tất cả dấu '"' (0x22)
  __m256i quote  = _mm256_set1_epi8('"');
  uint32_t qm0 = _mm256_movemask_epi8(_mm256_cmpeq_epi8(chunk0, quote));
  uint32_t qm1 = _mm256_movemask_epi8(_mm256_cmpeq_epi8(chunk1, quote));
  uint64_t quote_mask = ((uint64_t)qm1 << 32) | qm0;

  // Tìm tất cả ':' (0x3A)
  __m256i colon  = _mm256_set1_epi8(':');
  // ... tương tự cho {, }, [, ], ',', '\n'

BƯỚC 3: STRING MASKING — Loại bỏ characters bên trong string literals
  // prefix-xor trick: toggle bit ON tại mỗi quote → bits ON = inside string
  uint64_t string_mask = prefix_xor(quote_mask);
  // Loại bỏ structural chars bên trong strings:
  uint64_t structural = (colon_mask | brace_mask | bracket_mask) & ~string_mask;

BƯỚC 4: EXTRACT POSITIONS
  while (structural) {
      int pos = __builtin_ctzll(structural);  // Count trailing zeros
      index_array[idx++] = offset + pos;       // Global position
      structural &= structural - 1;            // Clear lowest bit
  }

prefix_xor(bitmask):
  // Cumulative XOR — O(1) via carry-less multiply
  // clmul(bitmask, 0xFFFFFFFFFFFFFFFF) trên x86
  // Hoặc: iterative XOR cascade trên ARM NEON
  x = bitmask
  x ^= x << 1;  x ^= x << 2;  x ^= x << 4;
  x ^= x << 8;  x ^= x << 16; x ^= x << 32;
  return x;
```

**Throughput ước tính:**
- Scalar JSON parse: ~300 MB/s
- SIMD (AVX2): ~2.5 GB/s  
- SIMD (AVX-512): ~4.0 GB/s

#### File cần tạo/sửa

| File | Thay đổi |
|------|----------|
| `core/src/simd_io.c` (MỚI) | ~500 LOC: SIMD structural indexer cho JSON/CSV |
| `core/src/simd_io.h` (MỚI) | API declarations |
| `stdlib/vir/json/json.vri` | Wire `native_simd_index()` trước khi parse |
| `core/src/intrinsics.c` | Register `simd_json_index` intrinsic |

#### Steps

1. **Detect capability** tại runtime: `cpu_caps.has_avx2` → dùng YMM path, `cpu_caps.has_avx512bw` → dùng ZMM path, fallback scalar
2. **Implement 3 functions**:
   - `simd_find_structural_avx2(buf, len, out_positions)` — xử lý 64 bytes/iteration
   - `simd_find_structural_neon(buf, len, out_positions)` — ARM64 NEON, 32 bytes/iteration
   - `simd_find_structural_scalar(buf, len, out_positions)` — fallback
3. **Tích hợp**: JSON parser gọi `simd_find_structural()` → nhận mảng positions → parse theo index thay vì scan tuần tự
4. **Mở rộng cho CSV, Vir tokenizer**: Cùng kỹ thuật, thay character set (`\n`, `,`, `"` cho CSV)

---

### A4. AMX Backend (Apple Matrix Extensions)

#### Hiện trạng
- `data/arch/arm64_config.json` đã khai báo 9 AMX opcodes (AMX_LDX, AMX_LDY, AMX_STZ, AMX_FMA32, AMX_FMA64, AMX_FMA16, AMX_MAC16, AMX_SET, AMX_CLR)
- `core/src/codegen.c` **không có** AMX instruction emission
- `cpu_caps.c` detect AMX capability trên Apple Silicon
- Current GEMM: ~10 GFLOP/s (NEON micro-kernel 8×8). AMX target: ~200 GFLOP/s

#### Thuật toán: AMX Tiled GEMM

```
THUẬT TOÁN: AMX-accelerated GEMM (C = A × B)

KIẾN TRÚC AMX (Apple M1-M4):
  - 2 matrix registers: X (input), Y (input), Z (accumulator)
  - Mỗi register: 32 rows × 16 columns = 512 bytes (1KB total)
  - FP32: 16×16 tiles, FP64: 8×8 tiles, FP16: 32×32 tiles
  - AMX_FMA32: Z += X × Y (16×16 FP32 in 1 cycle)

THUẬT TOÁN:
  // Chia ma trận C[M×N] = A[M×K] × B[K×N] thành tiles 16×16
  for tile_i = 0..M step 16:
    for tile_j = 0..N step 16:
      AMX_SET Z = 0                        // Clear accumulator
      for tile_k = 0..K step 16:
        AMX_LDX X, &A[tile_i][tile_k]     // Load 16×16 tile from A
        AMX_LDY Y, &B[tile_k][tile_j]     // Load 16×16 tile from B
        AMX_FMA32                          // Z += X × Y (16×16 FMA)
      end
      AMX_STZ &C[tile_i][tile_j], Z       // Store result tile
    end
  end

AMX INSTRUCTION ENCODING (Apple Silicon, undocumented but reverse-engineered):
  // Nguồn: github.com/corsix/amx
  // AMX instructions are encoded as system register writes:
  //   MSR, S3_4_C15_C<Cn>_<Op2>, Xd
  
  AMX_SET:    msr s3_4_c15_c0_0, x0   // Enable AMX coprocessor
  AMX_CLR:    msr s3_4_c15_c0_1, x0   // Clear/disable
  AMX_LDX:    msr s3_4_c15_c1_0, xN   // Load row to X register
  AMX_LDY:    msr s3_4_c15_c1_1, xN   // Load row to Y register
  AMX_STZ:    msr s3_4_c15_c1_2, xN   // Store Z register to memory
  AMX_FMA32:  msr s3_4_c15_c6_0, xN   // Z += X * Y (FP32, 16×16)
  AMX_FMA64:  msr s3_4_c15_c7_0, xN   // Z += X * Y (FP64, 8×8)
  AMX_FMA16:  msr s3_4_c15_c6_1, xN   // Z += X * Y (FP16, 32×32)
  
  // xN encodes: row index (bits 0-5), offset (bits 6-55), flags
```

#### Nguồn dữ liệu

| Nguồn | URL/Path | Nội dung |
|-------|----------|---------|
| corsix/amx | `github.com/corsix/amx` | Reverse-engineered AMX opcodes, encoding tables |
| dougallj/apple-silicon-instructions | `github.com/dougallj/applesiliconinstructions` | Latency/throughput đo thực tế |
| Vir config | `data/arch/arm64_config.json` | 9 AMX opcodes đã khai báo |

#### File cần sửa

| File | Thay đổi |
|------|----------|
| `core/src/codegen.c` | Thêm `arm64_emit_amx_*()` — 9 functions, mỗi function emit 1 MSR instruction (4 bytes) |
| `src/virmatrix/kernels/amx/` (MỚI) | GEMM kernel gọi AMX intrinsics |
| `src/backend/codegen/codegen.py` | Thêm AMX path trong `_emit_matmul()` khi `cap.has_amx == True` |
| `core/src/cpu_caps.c` | Xác nhận detect `hw.optional.amx_version` trên macOS |

#### Steps

1. **Verify AMX detection**: `sysctl hw.optional.amx_version` → nếu ≥ 1, AMX available
2. **Emit MSR instructions** trong `codegen.c`:
   ```c
   static void arm64_emit_amx_ldx(CodeBuf* cb, uint8_t reg) {
       // MSR S3_4_C15_C1_0, Xreg → encoding: 0xD503_4F20 | (reg & 0x1F)
       uint32_t insn = 0xD5034F20 | (reg & 0x1F);
       codebuf_emit_u32(cb, insn);
   }
   ```
3. **GEMM kernel**: Wrap AMX instructions trong C function:
   ```c
   void amx_gemm_16x16(float* A, float* B, float* C, int K) {
       arm64_emit_amx_set();
       for (int k = 0; k < K; k += 16) {
           arm64_emit_amx_ldx(A + k * 16);
           arm64_emit_amx_ldy(B + k * 16);
           arm64_emit_amx_fma32();
       }
       arm64_emit_amx_stz(C);
       arm64_emit_amx_clr();
   }
   ```
4. **Fallback**: Nếu không có AMX → dùng NEON micro-kernel hiện tại (8×8)

---

### A5. AVX-512 Stable JIT — ZMM Register Fix

#### Hiện trạng
- `cpu_caps.c` detect `AVX512F/BW` → `capability_profile.py` set `VectorBackend.AVX512`
- `data/arch/x86_64_config.json` có 8 AVX-512 opcodes + 6 Intel AMX opcodes
- **BUG**: Register allocator (`src/ir/registers/linear_scan.py`) cố định 8 XMM registers. ZMM cần 64 bytes/spill nhưng spill slot chỉ 8 bytes → **stack overflow khi spill ZMM**
- `codegen.c` hardcode XMM (128-bit), không có YMM/ZMM emission path

#### Root Cause & Fix

```
BUG: ZMM Register Spill Stack Overflow

Register Allocator state:
  ARM64: 8 VEC registers (V0-V7, 128-bit NEON) → spill = 16 bytes
  x86_64: 8 VEC registers (XMM0-XMM7, 128-bit) → spill = 16 bytes

Khi AVX-512 enabled:
  32 ZMM registers available (ZMM0-ZMM31, 512-bit)
  Nhưng allocator vẫn alloc 8 slots → spill 24 registers
  Spill slot size = 8 bytes (designed for GP int64) ← BUG
  ZMM cần 64 bytes per spill → viết 64 bytes vào slot 8 bytes → TRÀN STACK

FIX:
1. Mở rộng VEC register pool từ 8 → 32 khi AVX-512 detected
2. Spill slot size = max(8, register_width_bytes)
   - GP: 8 bytes
   - XMM: 16 bytes  
   - YMM: 32 bytes
   - ZMM: 64 bytes
3. Stack frame alignment: 64-byte aligned khi dùng ZMM (AVX-512 yêu cầu)
```

#### Thuật toán: Tiered Vector Register Allocation

```
THUẬT TOÁN: Architecture-Aware Vec Register Allocation

function allocate_vec_registers(instructions, arch_profile):
  if arch_profile.has_avx512:
    vec_pool = [ZMM0..ZMM31]     // 32 registers, 512-bit
    spill_size = 64
    alignment = 64
  elif arch_profile.has_avx2:
    vec_pool = [YMM0..YMM15]     // 16 registers, 256-bit
    spill_size = 32
    alignment = 32
  else:  // SSE2 / NEON
    vec_pool = [XMM0..XMM7]      // 8 registers, 128-bit
    spill_size = 16
    alignment = 16
  
  // Adjust stack frame
  stack_frame.vec_spill_area_align = alignment
  stack_frame.vec_spill_slot_size = spill_size
  
  // Standard linear scan with adjusted parameters
  linear_scan(instructions, vec_pool, spill_size)

EMIT SPILL (x86_64):
  XMM:  MOVAPS [rsp + offset], xmm_n      // 16-byte aligned
  YMM:  VMOVAPS [rsp + offset], ymm_n     // 32-byte aligned
  ZMM:  VMOVAPS [rsp + offset], zmm_n     // 64-byte aligned (EVEX prefix)

EMIT RELOAD:
  XMM:  MOVAPS xmm_n, [rsp + offset]
  YMM:  VMOVAPS ymm_n, [rsp + offset]
  ZMM:  VMOVAPS zmm_n, [rsp + offset]      // EVEX prefix required
```

#### File cần sửa

| File | Thay đổi |
|------|----------|
| `src/ir/registers/linear_scan.py` | `vec_pool` size = 32 khi AVX-512, spill_size = 64 |
| `core/src/codegen.c` | Thêm EVEX prefix emitters cho ZMM: `x86_emit_vmovaps_zmm()`, `x86_emit_vaddps_zmm()` |
| `core/src/ir_lower.c` | Stack frame calculation: align to 64 bytes khi AVX-512 |
| `data/arch/x86_64_config.json` | Thêm spill cost cho ZMM: `{"spill_store": 2, "spill_load": 6}` |
| `src/backend/codegen/codegen.py` | LoopVectorizer width = 16 (512 / 32-bit) khi AVX-512 |

#### Steps

1. **linear_scan.py**: Thêm `get_vec_pool(profile)` trả về 8/16/32 registers tùy backend
2. **codegen.c — EVEX prefix**: AVX-512 dùng EVEX (4 bytes) thay vì VEX (2-3 bytes):
   ```c
   // EVEX prefix: 62h [R'XBR'] [W_vvvv_1pp] [z_L'L_b_V'_aaa]
   static void x86_emit_evex(CodeBuf* cb, uint8_t mm, uint8_t pp, 
                              uint8_t W, uint8_t vvvv, uint8_t LL) {
       codebuf_emit(cb, 0x62);
       codebuf_emit(cb, 0xF1 | (mm & 3));         // R=1, X=1, B=1, R'=1
       codebuf_emit(cb, (W << 7) | (~vvvv << 3) | 0x04 | (pp & 3));
       codebuf_emit(cb, (LL << 5));                 // LL=10 for 512-bit
   }
   ```
3. **Stack alignment**: Trong `ir_lower.c`, khi setting up stack frame:
   ```c
   if (cpu_has_avx512) {
       frame->alignment = 64;
       frame->vec_spill_size = 64;
   }
   ```
4. **Test**: Viết benchmark `bench_avx512.vri` — vector add 1M floats, verify kết quả

---

## Trụ cột B — Metadata-Driven Codegen

---

### B1. Script tự động cập nhật Metadata

#### Nguồn dữ liệu chính thức

| Kiến trúc | Nguồn | Format | URL/Repo |
|-----------|-------|--------|----------|
| **x86_64 Intrinsics** | Intel Intrinsics Guide | XML | `software.intel.com/sites/landingpage/IntrinsicsGuide/files/data-latest.xml` |
| **x86_64 µops** | uops.info | JSON | `uops.info/instructions.json` (Andreas Abel, Saarland University) |
| **ARM64 ISA** | ARM Exploration Tools | XML | `developer.arm.com/architectures/instruction-sets/intrinsics/` |
| **Apple Silicon** | dougallj reverse-eng | CSV/JSON | `github.com/dougallj/applesiliconinstructions` |
| **RISC-V opcodes** | riscv/riscv-opcodes | CSV/Python | `github.com/riscv/riscv-opcodes` |
| **RISC-V V ext** | riscv/riscv-v-spec | AsciiDoc tables | `github.com/riscv/riscv-v-spec` |

#### Script: `scripts/update_specs.sh`

```bash
#!/bin/bash
# update_specs.sh — Tự động tải metadata tập lệnh từ nguồn chính thức
set -euo pipefail

SPEC_DIR="data/arch/specs"
mkdir -p "$SPEC_DIR"

echo "=== [1/5] x86_64: Intel Intrinsics Guide ==="
curl -sSL "https://www.intel.com/content/dam/develop/public/us/en/include/intrinsics-guide/data-latest.xml" \
  -o "$SPEC_DIR/intel_intrinsics.xml"

echo "=== [2/5] x86_64: uops.info ==="
curl -sSL "https://uops.info/instructions.json" \
  -o "$SPEC_DIR/uops_info.json"

echo "=== [3/5] ARM64: Apple Silicon (dougallj) ==="
if [ -d "$SPEC_DIR/apple-silicon-instructions" ]; then
  git -C "$SPEC_DIR/apple-silicon-instructions" pull --quiet
else
  git clone --depth 1 "https://github.com/dougallj/applesiliconinstructions.git" \
    "$SPEC_DIR/apple-silicon-instructions"
fi

echo "=== [4/5] RISC-V: Opcodes ==="
if [ -d "$SPEC_DIR/riscv-opcodes" ]; then
  git -C "$SPEC_DIR/riscv-opcodes" pull --quiet
else
  git clone --depth 1 "https://github.com/riscv/riscv-opcodes.git" \
    "$SPEC_DIR/riscv-opcodes"
fi

echo "=== [5/5] RISC-V: Vector Spec ==="
if [ -d "$SPEC_DIR/riscv-v-spec" ]; then
  git -C "$SPEC_DIR/riscv-v-spec" pull --quiet
else
  git clone --depth 1 "https://github.com/riscv/riscv-v-spec.git" \
    "$SPEC_DIR/riscv-v-spec"
fi

echo "✅ All specs updated in $SPEC_DIR"
ls -la "$SPEC_DIR"
```

---

### B2. Meta-Compiler: Metadata → generated_codegen.c

#### Thuật toán: Metadata → Instruction Table → C Code

```
THUẬT TOÁN: Meta-Compiler Pipeline

INPUT:
  - intel_intrinsics.xml (12,000+ intrinsics)
  - uops_info.json (latency/throughput per µarch)
  - riscv-opcodes/*.csv (500+ opcodes)

OUTPUT:
  - generated_codegen_x86.c    (emit functions for x86_64)
  - generated_codegen_arm64.c  (emit functions for ARM64)
  - generated_codegen_riscv.c  (emit functions for RISC-V)
  - generated_cost_model.json  (updated cost model per arch)

BƯỚC 1: PARSE METADATA
  function parse_intel_xml(path):
    for each <intrinsic> in xml:
      name = intrinsic.name           // e.g. "_mm256_add_ps"
      tech = intrinsic.tech           // e.g. "AVX"
      cpuid = intrinsic.CPUID         // e.g. "AVX"
      instruction = intrinsic.instruction  // e.g. "VADDPS ymm, ymm, ymm"
      description = intrinsic.description
      params = [p.type + " " + p.varname for p in intrinsic.parameters]
      rettype = intrinsic.rettype
      → InstructionSpec(name, opcode, encoding, params, rettype, tech)

  function parse_uops_json(path):
    for each instruction in json:
      name = instruction.name         // e.g. "VADDPS (YMM, YMM, YMM)"
      for each µarch in instruction.measurements:
        latency = µarch.latency
        throughput = µarch.throughput_reciprocal
        ports = µarch.ports
        → CostEntry(name, µarch_name, latency, throughput, ports)

  function parse_riscv_opcodes(dir):
    // File format: mnemonic  arg1 arg2 ... encoding
    // e.g.: "vadd.vv     vd vs2 vs1 vm  0b000000_._....._....._000_....._1010111"
    for each line in opcodes-rv64v:
      mnemonic, *args, encoding = split(line)
      → RiscvSpec(mnemonic, args, parse_binary(encoding))

BƯỚC 2: GENERATE C EMIT FUNCTIONS
  function generate_emitter(spec):
    // Template per architecture:
    if spec.arch == "x86_64":
      → emit C function using REX/VEX/EVEX prefix + opcode + ModRM
    if spec.arch == "arm64":
      → emit C function using fixed 32-bit encoding
    if spec.arch == "riscv64":
      → emit C function using R/I/S/B/U/J format encoding

  // Example output for VADDPS YMM:
  // static void x86_emit_vaddps_ymm(CodeBuf* cb, uint8_t dst, uint8_t s1, uint8_t s2) {
  //     x86_emit_vex3(cb, /*pp=*/0, /*mm=*/1, /*W=*/0, /*L=*/1, s1);
  //     codebuf_emit(cb, 0x58);  // ADDPS opcode
  //     x86_emit_modrm(cb, 0xC0, dst, s2);
  // }

BƯỚC 3: GENERATE COST MODEL
  function generate_cost_json(cost_entries):
    output = {}
    for each entry in cost_entries:
      output[entry.name] = {
        "latency": entry.latency,
        "throughput": entry.throughput,
        "ports": entry.ports,
        "uops": entry.uops
      }
    write_json("data/arch/{arch}_config.json", output)
```

#### File cần tạo

| File | Mô tả | LOC ước tính |
|------|--------|-------------|
| `scripts/update_specs.sh` | Download metadata | ~40 |
| `scripts/meta_compiler.py` | Parse XML/JSON/CSV → generate C | ~800 |
| `scripts/meta_compiler_riscv.py` | RISC-V specific (khác format) | ~300 |
| `core/src/generated_codegen_x86.c` (GENERATED) | Auto-generated emit functions | ~5,000 |
| `core/src/generated_codegen_arm64.c` (GENERATED) | Auto-generated emit functions | ~3,000 |
| `core/src/generated_codegen_riscv.c` (GENERATED) | Auto-generated emit functions | ~2,000 |

#### Steps

1. **Tạo `scripts/update_specs.sh`** — chạy 1 lần để populate `data/arch/specs/`
2. **Viết `scripts/meta_compiler.py`**:
   - Class `IntelXMLParser` — parse `data-latest.xml`
   - Class `UopsParser` — parse `instructions.json`
   - Class `CEmitter` — template engine cho C emit functions
   - Function `main()` — orchestrate: parse → filter (chỉ lấy SSE2/AVX/AVX-512) → generate
3. **Filter strategy**: Không generate tất cả 12,000 intrinsics. Chỉ generate:
   - Arithmetic: ADD/SUB/MUL/DIV/FMA (scalar + packed, all widths)
   - Compare: CMP (all predicates)
   - Load/Store: MOV aligned/unaligned, broadcast, gather/scatter
   - Shuffle: PERM, SHUF, BLEND
   - Conversion: CVT (int↔float, width changes)
   - Total: ~200-400 instructions per arch (đủ cho compiler, không quá tải)
4. **Makefile integration**: `make generated` chạy meta_compiler, `make` includes generated files

---

## Trụ cột C — Tương thích đa nền tảng

---

### C1. I-Cache Flush cho ARM64 Self-Patching

#### Hiện trạng
- `core/src/bridge.c:187-233` **đã có** I-Cache flush:
  - macOS: `sys_icache_invalidate(addr, size)`
  - Linux: `__asm__ volatile("dsb ish; isb")`
- `core/src/patcher.c:20` extern `vir_asm_flush_icache()`
- **THIẾU**: Bypass D-cache clean (chỉ invalidate I-cache, chưa clean D-cache trước)

#### Thuật toán chính xác: D-Cache Clean + I-Cache Invalidate + Barriers

```
THUẬT TOÁN: ARM64 Cache Coherency cho Self-Patching

PROBLEM:
  CPU viết code mới vào RAM (data write → D-cache)
  Nhưng I-cache vẫn chứa code cũ
  → CPU thực thi code cũ → crash hoặc sai logic

GIẢI PHÁP (3 bước bắt buộc):

BƯỚC 1: CLEAN D-CACHE TO POINT OF UNIFICATION (PoU)
  // Đẩy data mới từ D-cache → shared cache/RAM
  // Cần clean từng cache line (64 bytes trên Apple Silicon)
  for addr = patch_start; addr < patch_end; addr += 64:
    asm volatile("dc cvau, %0" :: "r"(addr));
  asm volatile("dsb ish");  // Wait for all clean ops to complete

BƯỚC 2: INVALIDATE I-CACHE
  // Buộc I-cache xóa entries cho vùng đã patch
  for addr = patch_start; addr < patch_end; addr += 64:
    asm volatile("ic ivau, %0" :: "r"(addr));
  asm volatile("dsb ish");  // Wait for all invalidate ops to complete

BƯỚC 3: INSTRUCTION SYNCHRONIZATION BARRIER
  asm volatile("isb");
  // Flush pipeline — CPU phải fetch lại từ I-cache (đã invalidated)
  // Mọi instruction sau ISB đều sẽ được fetch lại

COMPLETE C IMPLEMENTATION:
  void flush_code_region(void* addr, size_t size) {
    #if defined(__aarch64__)
      uintptr_t start = (uintptr_t)addr & ~63ULL;  // Align to cache line
      uintptr_t end = ((uintptr_t)addr + size + 63) & ~63ULL;
      
      // Step 1: Clean D-cache
      for (uintptr_t p = start; p < end; p += 64)
          __asm__ volatile("dc cvau, %0" :: "r"(p) : "memory");
      __asm__ volatile("dsb ish" ::: "memory");
      
      // Step 2: Invalidate I-cache
      for (uintptr_t p = start; p < end; p += 64)
          __asm__ volatile("ic ivau, %0" :: "r"(p) : "memory");
      __asm__ volatile("dsb ish" ::: "memory");
      
      // Step 3: Sync pipeline  
      __asm__ volatile("isb" ::: "memory");
    #elif defined(__APPLE__) && defined(__aarch64__)
      sys_icache_invalidate(addr, size);  // macOS API (does all 3 steps)
    #elif defined(__x86_64__)
      // x86_64: No explicit flush needed
      // Intel guarantees I-cache coherency on store-to-code
      __asm__ volatile("mfence" ::: "memory");
    #endif
  }
```

#### File cần sửa

| File | Thay đổi |
|------|----------|
| `core/src/bridge.c` | Thay thế hiện tại bằng full 3-step flush (dc cvau + ic ivau + isb) cho Linux ARM64 |
| `core/src/patcher.c` | Gọi `flush_code_region()` sau mỗi binary patch |

---

### C2. Atomic Abstraction Layer

#### Thuật toán: Cross-Architecture Atomic Primitives

```
THUẬT TOÁN: Portable Atomic Operations

TARGET: Cung cấp API thống nhất cho 3 kiến trúc:
  - x86_64: LOCK prefix (LOCK CMPXCHG, LOCK XADD, LOCK BTS)
  - ARM64: Load-Linked / Store-Conditional (LDXR/STXR) hoặc LSE (LDADD, CAS, SWP)
  - RISC-V: LR/SC (Load Reserved / Store Conditional)

API:
  vir_atomic_cas(ptr, expected, desired) → old_value
  vir_atomic_add(ptr, value) → old_value
  vir_atomic_load(ptr) → value       // with acquire semantics
  vir_atomic_store(ptr, value)        // with release semantics

IMPLEMENTATION PER ARCH:

// Compare-And-Swap
x86_64:
  mov rax, [expected]
  lock cmpxchg [ptr], desired    // if *ptr == rax: *ptr = desired, ZF=1
                                 // else: rax = *ptr, ZF=0

ARM64 (LSE, ARMv8.1+):
  cas x_old, x_new, [ptr]       // Atomic CAS, single instruction

ARM64 (pre-LSE):
  1: ldxr x_old, [ptr]          // Load-exclusive
     cmp x_old, x_expected
     b.ne 2f
     stxr w_tmp, x_desired, [ptr]  // Store-exclusive (w_tmp = 0 if success)
     cbnz w_tmp, 1b              // Retry if store failed
  2: // x_old = result

RISC-V:
  1: lr.d x_old, (ptr)          // Load-reserved
     bne x_old, x_expected, 2f
     sc.d x_tmp, x_desired, (ptr)  // Store-conditional
     bnez x_tmp, 1b              // Retry if reservation lost
  2: // x_old = result

// Atomic Add
x86_64: lock xadd [ptr], value
ARM64:  ldadd value, old, [ptr]   // LSE
RISC-V: amoadd.d old, value, (ptr)
```

#### File cần tạo

| File | Mô tả | LOC |
|------|--------|-----|
| `core/src/atomic.c` (MỚI) | Portable atomic implementations | ~200 |
| `core/include/atomic.h` (MỚI) | API + inline asm macros per arch | ~150 |

---

### C3. Alignment Audit cho RISC-V

#### Thuật toán: Static Alignment Checker

```
THUẬT TOÁN: Struct Alignment Audit

PROBLEM:
  x86_64 cho phép unaligned access (chậm nhưng không crash)
  RISC-V crash (SIGBUS/trap) khi access unaligned address
  ARM64: phụ thuộc SCTLR.A flag

AUDIT PROCEDURE:
  1. Tìm tất cả struct/entity trong codebase:
     grep -rn "typedef struct\|struct {" core/include/ core/src/
  
  2. Cho mỗi struct, kiểm tra:
     - Có field nào kích thước < alignment của field sau không?
     - Có explicit alignment attribute không?
     - Struct tổng size có là bội số của alignment lớn nhất không?
  
  3. FIX: Thêm padding hoặc attribute

VÍ DỤ BUG:
  struct bad_layout {
      uint8_t  type;       // offset 0, size 1
      uint64_t value;      // offset 1 ← UNALIGNED! Cần offset 8
  };
  // Trên RISC-V: access value gây trap
  // Fix: __attribute__((aligned(8))) hoặc sắp xếp lại fields

FIX SYSTEMIC:
  // Trong tất cả headers, thêm:
  #if defined(__riscv)
  #define VIR_ALIGNED(n) __attribute__((aligned(n)))
  #else
  #define VIR_ALIGNED(n) // x86 cho phép unaligned
  #endif

  struct fixed_layout {
      uint64_t value VIR_ALIGNED(8);  // offset 0
      uint32_t count VIR_ALIGNED(4);  // offset 8
      uint8_t  type;                  // offset 12
      uint8_t  _pad[3];              // padding to 16 bytes
  } VIR_ALIGNED(8);
```

#### Script audit tự động: `scripts/alignment_audit.py`

```python
# Pseudocode cho alignment checker
import re, sys

def audit_struct(header_path):
    structs = parse_structs(header_path)  # regex extract struct definitions
    for s in structs:
        offset = 0
        max_align = 1
        for field in s.fields:
            align = natural_alignment(field.type)  # uint8=1, uint16=2, uint32=4, uint64=8, void*=8
            max_align = max(max_align, align)
            if offset % align != 0:
                print(f"⚠️  {s.name}.{field.name}: offset {offset} misaligned for {field.type} (need {align})")
                offset = (offset + align - 1) & ~(align - 1)  # auto-pad
            offset += sizeof(field.type)
        if offset % max_align != 0:
            print(f"⚠️  {s.name}: total size {offset} not aligned to {max_align}")
```

#### File cần audit

| File | Structs quan trọng |
|------|-------------------|
| `core/include/q_ir.h` | `QIR_Instruction`, `QIR_Module`, `QIR_Function` |
| `core/include/vm.h` | `VM_State`, `VM_Array` |
| `core/include/lexer.h` | `vir_token_t` |
| `core/include/parser.h` | `ASTNode`, `Parser` |
| `core/include/codegen.h` | `CodeBuf`, `CodeBlock` |
| `core/include/jit_bridge.h` | `JIT_Bridge`, `JIT_Block` |

---

## Trụ cột D — GPU & CUDA (Zero-Dependency)

---

### D1. CUDA Driver FFI Bridge

#### Thuật toán: Dynamic Loading CUDA Driver API

```
THUẬT TOÁN: Zero-Dependency CUDA Bridge

NGUYÊN TẮC:
  - KHÔNG link libcuda.so tại compile time
  - KHÔNG yêu cầu CUDA Toolkit installed
  - Load libcuda.so/nvcuda.dll tại RUNTIME bằng dlopen/dlsym
  - Nếu không có GPU → graceful fallback to CPU

BƯỚC 1: DYNAMIC LOAD
  void* libcuda = dlopen("libcuda.so.1", RTLD_LAZY);  // Linux
  // hoặc: LoadLibrary("nvcuda.dll");                   // Windows
  if (!libcuda) return VIR_NO_GPU;
  
  // Resolve function pointers
  typedef CUresult (*cuInit_t)(unsigned int);
  typedef CUresult (*cuCtxCreate_t)(CUcontext*, unsigned int, CUdevice);
  typedef CUresult (*cuModuleLoadData_t)(CUmodule*, const void*);
  typedef CUresult (*cuLaunchKernel_t)(CUfunction, ...);
  
  cuInit_t       f_cuInit       = dlsym(libcuda, "cuInit");
  cuCtxCreate_t  f_cuCtxCreate  = dlsym(libcuda, "cuCtxCreate_v2");
  // ... 15-20 functions total

BƯỚC 2: GPU INITIALIZATION
  f_cuInit(0);
  CUdevice device;
  f_cuDeviceGet(&device, 0);
  CUcontext ctx;
  f_cuCtxCreate(&ctx, 0, device);

BƯỚC 3: LOAD PTX MODULE
  // PTX source compiled by Vir (see D2)
  const char* ptx_source = "..generated PTX..";
  CUmodule module;
  f_cuModuleLoadData(&module, ptx_source);  // JIT compile PTX → SASS
  CUfunction kernel;
  f_cuModuleGetFunction(&kernel, module, "vir_kernel_add");

BƯỚC 4: MEMORY MANAGEMENT (Unified Memory)
  void* d_buf;
  f_cuMemAllocManaged(&d_buf, size, CU_MEM_ATTACH_GLOBAL);
  // CPU và GPU dùng chung con trỏ — không cần memcpy
  memcpy(d_buf, host_data, size);  // CPU writes
  // Launch kernel — GPU reads same pointer

BƯỚC 5: LAUNCH KERNEL
  void* args[] = { &d_A, &d_B, &d_C, &N };
  f_cuLaunchKernel(kernel,
      grid_x, grid_y, grid_z,       // Grid dimensions
      block_x, block_y, block_z,    // Block dimensions
      shared_mem_bytes, stream,
      args, NULL);
  f_cuCtxSynchronize();  // Wait for completion
```

#### CUDA Driver API Functions cần wrap (tối thiểu)

| Function | Mục đích |
|----------|---------|
| `cuInit` | Khởi tạo driver |
| `cuDeviceGet` | Lấy device handle |
| `cuDeviceGetAttribute` | Query compute capability, SM count |
| `cuCtxCreate_v2` | Tạo CUDA context |
| `cuCtxDestroy_v2` | Hủy context |
| `cuModuleLoadData` | Load PTX → JIT compile thành SASS |
| `cuModuleGetFunction` | Lấy kernel function handle |
| `cuLaunchKernel` | Launch kernel trên GPU |
| `cuMemAllocManaged` | Unified Memory allocation |
| `cuMemFree_v2` | Free GPU memory |
| `cuCtxSynchronize` | Đợi GPU hoàn thành |
| `cuStreamCreate` | Tạo async stream |
| `cuStreamSynchronize` | Sync stream |
| `cuDeviceGetName` | GPU name (diagnostic) |
| `cuDeviceTotalMem_v2` | VRAM size |

#### File cần tạo

| File | Mô tả | LOC |
|------|--------|-----|
| `core/src/gpu_cuda.c` (MỚI) | CUDA Driver API bridge, dlopen/dlsym | ~500 |
| `core/include/gpu_cuda.h` (MỚI) | Function pointer typedefs, API | ~100 |
| `core/src/gpu_common.h` (MỚI) | Abstract GPU interface (CUDA/Metal/Vulkan) | ~80 |

---

### D2. PTX Emitter (Q-IR → PTX)

#### Thuật toán: Q-IR → PTX Assembly Translation

```
THUẬT TOÁN: Q-IR to PTX Compilation

PTX (Parallel Thread Execution):
  - NVIDIA virtual ISA
  - Text format (assembly-like)
  - GPU driver JIT compiles PTX → SASS (native, per-GPU)
  
MAPPING Q-IR → PTX:

Q-IR Opcode      → PTX Instruction     Width
─────────────────────────────────────────────
Q_ADD (int)      → add.s64             64-bit
Q_ADD (float)    → add.f32             32-bit
Q_SUB            → sub.f32 / sub.s64
Q_MUL            → mul.lo.s64 / mul.f32
Q_DIV            → div.rn.f32          (round-to-nearest)
Q_FMA            → fma.rn.f32          (fused multiply-add)
Q_LOAD           → ld.global.f32
Q_STORE          → st.global.f32
Q_CMP_EQ         → setp.eq.f32 + selp
Q_JUMP_IF        → @p bra label
VADD             → add.f32 (per-thread, implicit SIMT)
VMATMUL          → wmma.mma.sync.aligned.m16n16k16.f32 (Tensor Core)

PTX TEMPLATE cho một kernel:

  .version 7.8
  .target sm_86           // Ampere hoặc mới hơn
  .address_size 64
  
  .visible .entry vir_kernel_add(
      .param .u64 param_A,
      .param .u64 param_B,
      .param .u64 param_C,
      .param .u32 param_N
  ) {
      .reg .u32 %tid, %n;
      .reg .u64 %addr_a, %addr_b, %addr_c;
      .reg .f32 %a, %b, %c;
      
      // Thread index = blockIdx.x * blockDim.x + threadIdx.x
      mov.u32     %tid, %ctaid.x;
      mad.lo.u32  %tid, %tid, %ntid.x, %tid.x;
      
      // Bounds check
      ld.param.u32 %n, [param_N];
      setp.ge.u32 %p, %tid, %n;
      @%p bra $L_exit;
      
      // Load A[tid] and B[tid]
      ld.param.u64 %addr_a, [param_A];
      ld.param.u64 %addr_b, [param_B];
      cvt.u64.u32  %off, %tid;
      shl.b64      %off, %off, 2;        // ×4 bytes per float
      add.u64      %addr_a, %addr_a, %off;
      add.u64      %addr_b, %addr_b, %off;
      ld.global.f32 %a, [%addr_a];
      ld.global.f32 %b, [%addr_b];
      
      // C[tid] = A[tid] + B[tid]
      add.f32      %c, %a, %b;
      
      // Store result
      ld.param.u64 %addr_c, [param_C];
      add.u64      %addr_c, %addr_c, %off;
      st.global.f32 [%addr_c], %c;
      
  $L_exit:
      ret;
  }

TENSOR CORE GEMM (wmma):
  // Warp-level Matrix Multiply-Accumulate (16×16×16)
  wmma.load.a.sync.aligned.m16n16k16.global.row.f16  {%ra0..%ra7}, [addr_A];
  wmma.load.b.sync.aligned.m16n16k16.global.col.f16  {%rb0..%rb7}, [addr_B];
  wmma.mma.sync.aligned.m16n16k16.f32.f16.f16
      {%rc0..%rc7}, {%ra0..%ra7}, {%rb0..%rb7}, {%rc0..%rc7};
  wmma.store.d.sync.aligned.m16n16k16.global.row.f32  [addr_C], {%rc0..%rc7};
```

#### Steps

1. **PTX text generator** (`core/src/ptx_gen.c`): String builder that emits PTX assembly text
2. **Q-IR → PTX lowering** trong `src/backend/codegen/codegen_gpu.py`:
   - Iterate Q-IR-L instructions
   - Map each opcode → PTX instruction string
   - Handle thread indexing: `%ctaid.x * %ntid.x + %tid.x`
   - Handle memory: `.global` space for arrays, `.shared` for tile buffers
3. **Module load**: Pass PTX string to `cuModuleLoadData()` — NVIDIA driver JIT compiles
4. **Vir syntax**: Hàm đánh dấu `async task(gpu)`:
   ```vir
   async task(gpu) func vector_add:
       in(a:array; b:array; c:array; n:int)
       # Compiler detects task(gpu) → emit PTX instead of Q-IR
       var i = thread_id()
       if i < n:
           c[i] = a[i] + b[i]
       end
   end
   ```

#### File cần tạo

| File | Mô tả | LOC |
|------|--------|-----|
| `core/src/ptx_gen.c` (MỚI) | PTX text emitter | ~400 |
| `core/include/ptx_gen.h` (MỚI) | API declarations | ~50 |
| `src/backend/codegen/codegen_gpu.py` (MỚI) | Q-IR → PTX lowering | ~600 |
| `data/gpu/ptx_templates/` (MỚI) | Pre-built PTX kernels (vadd, gemm, relu) | ~500 |

---

### D3. Apple Metal/AIR Backend

#### Thuật toán: Q-IR → Metal Shading Language (MSL)

```
THUẬT TOÁN: Generate Metal Compute Shader

KHÁC BIỆT vs CUDA:
  - Apple GPU dùng Unified Memory (CPU/GPU chung RAM) → KHÔNG cần memcpy
  - Shader language: MSL (C++-like) thay vì PTX
  - Dispatch: MTLComputeCommandEncoder thay vì cuLaunchKernel
  - API: Metal framework (load bằng dlopen trên macOS)

MSL TEMPLATE cho vector add:

  #include <metal_stdlib>
  using namespace metal;
  
  kernel void vir_kernel_add(
      device const float* A [[buffer(0)]],
      device const float* B [[buffer(1)]],
      device float* C       [[buffer(2)]],
      constant uint& N      [[buffer(3)]],
      uint tid              [[thread_position_in_grid]]
  ) {
      if (tid < N) {
          C[tid] = A[tid] + B[tid];
      }
  }

MSL GEMM (simdgroup_matrix):
  // Apple GPU threadgroup matrix operations (M1+)
  kernel void vir_gemm(
      device const float* A [[buffer(0)]],
      device const float* B [[buffer(1)]],
      device float* C       [[buffer(2)]],
      constant uint& M      [[buffer(3)]],
      constant uint& N      [[buffer(4)]],
      constant uint& K      [[buffer(5)]],
      uint2 gid             [[threadgroup_position_in_grid]],
      uint2 lid             [[thread_position_in_threadgroup]]
  ) {
      simdgroup_float8x8 a, b, c;
      simdgroup_load(c, C + ..., N);  // Load accumulator
      for (uint k = 0; k < K; k += 8) {
          simdgroup_load(a, A + ..., K);
          simdgroup_load(b, B + ..., N);
          simdgroup_multiply_accumulate(c, a, b, c);
      }
      simdgroup_store(c, C + ..., N);
  }

METAL API LOADING (dlopen):
  void* metal = dlopen("/System/Library/Frameworks/Metal.framework/Metal", RTLD_LAZY);
  // Resolve Objective-C selectors via objc_msgSend
  // MTLCreateSystemDefaultDevice() → id<MTLDevice>
  // [device newBufferWithBytesNoCopy:...] → Unified Memory (zero-copy!)
  // [device newLibraryWithSource:...] → Compile MSL at runtime
```

#### File cần tạo

| File | Mô tả | LOC |
|------|--------|-----|
| `core/src/gpu_metal.m` (MỚI) | Metal API bridge (Objective-C) | ~400 |
| `core/include/gpu_metal.h` (MỚI) | API declarations | ~60 |
| `src/backend/codegen/codegen_metal.py` (MỚI) | Q-IR → MSL lowering | ~500 |
| `data/gpu/msl_templates/` (MỚI) | Pre-built MSL kernels | ~400 |

---

### D4. GPU Kernel Library (GEMM, Fusion, Coalesced Access)

#### 3 kỹ thuật GPU hardcore

##### Kỹ thuật 1: Kernel Fusion

```
THUẬT TOÁN: GPU Kernel Fusion

PROBLEM: Mỗi kernel launch = overhead (~5-10µs) + VRAM roundtrip
  Kernel1: C = A + B → write C to VRAM
  Kernel2: D = ReLU(C) → read C from VRAM, write D
  Kernel3: E = D * W → read D from VRAM, write E
  = 3 kernel launches + 3 VRAM reads + 3 VRAM writes

SOLUTION: Gộp thành 1 kernel
  FusedKernel: E = (ReLU(A + B)) * W
  = 1 kernel launch + 1 VRAM read + 1 VRAM write

IMPLEMENTATION:
  function fuse_kernels(graph):
    // Reuse auto_fusion.py algorithm nhưng cho PTX/MSL:
    chains = find_fuseable_chains(graph)  // ADD→RELU→MUL
    for chain in chains:
      ptx = emit_fused_ptx(chain)
      // Tất cả intermediate values ở registers, KHÔNG đi qua VRAM
```

##### Kỹ thuật 2: Tiled GEMM cho GPU

```
THUẬT TOÁN: Tiled GPU GEMM

GPU Memory Hierarchy:
  VRAM (Global):  ~1TB/s bandwidth, 400+ cycle latency
  Shared Memory:  ~19 TB/s, ~20 cycle latency  (48-164 KB per SM)
  Registers:      ~80 TB/s, 0 cycle latency     (256 KB per SM)

STRATEGY: Load tiles from VRAM → Shared Memory → Registers

  TILE_M = 128, TILE_N = 128, TILE_K = 32  // Per threadblock
  
  for tile_k = 0..K step TILE_K:
    // Cooperative load: mỗi thread load vài elements
    __shared__ float As[TILE_M][TILE_K];
    __shared__ float Bs[TILE_K][TILE_N];
    As[thread_row][thread_col] = A[global_row][tile_k + thread_col];
    Bs[thread_row][thread_col] = B[tile_k + thread_row][global_col];
    __syncthreads();
    
    // Compute: TILE_K iterations, all from shared memory
    for k = 0..TILE_K:
      c_reg += As[local_row][k] * Bs[k][local_col];
    __syncthreads();
  
  // Write back
  C[global_row][global_col] = c_reg;
```

##### Kỹ thuật 3: Coalesced Memory Access

```
THUẬT TOÁN: Coalesced vs Non-Coalesced

COALESCED (tốt — 1 transaction cho 32 threads):
  Thread 0 đọc address 0x1000
  Thread 1 đọc address 0x1004
  Thread 2 đọc address 0x1008
  ...
  Thread 31 đọc address 0x107C
  → GPU gộp thành 1 memory transaction (128 bytes)

NON-COALESCED (xấu — 32 transactions):
  Thread 0 đọc address 0x1000
  Thread 1 đọc address 0x2000  // gap!
  Thread 2 đọc address 0x3000  // gap!
  → GPU phải phát 32 transactions riêng lẻ

RULE: Đảm bảo threads trong cùng warp (32 threads) 
      truy cập addresses liên tiếp nhau.

IMPLEMENTATION trong PTX emitter:
  // Khi emit array access A[tid]:
  // Good: offset = tid * sizeof(float)  → coalesced
  // Bad:  offset = tid * stride         → non-coalesced nếu stride > 1
  
  // Cho matrix access A[row][col] với row-major layout:
  // Thread lặp theo col (inner dimension) → coalesced
  // Thread lặp theo row → non-coalesced → cần transpose
```

---

## BẢNG TỔNG HỢP — LỖ HỔNG & ƯU TIÊN

| # | Task | Kiến trúc | Trạng thái | File chính | LOC |
|---|------|-----------|------------|------------|-----|
| A1 | Pattern Matching (`:~`) | General | ✅ DONE | parser.c, ir_lower.c | ~500 |
| A2 | Async Green Threads | General | ✅ DONE | task.c, task.h | ~600 |
| A3 | Vectorized I/O | x86_64 + ARM64 | ✅ DONE | simd_dispatch.c, simd_index.c | ~500 |
| A4 | AMX Backend | Apple M1-M4 | ✅ DONE | amx_accel.c | ~400 |
| A5 | AVX-512 JIT Fix | Intel/AMD | ✅ DONE | linear_scan.py (tiered ZMM/YMM/XMM) | ~300 |
| B1 | Metadata Download | All | ✅ DONE | scripts/update_specs.sh | ~40 |
| B2 | Meta-Compiler | All | ✅ DONE | scripts/meta_compiler.py | ~300 |
| C1 | I-Cache Flush Fix | ARM64 | ✅ DONE | bridge.c (dc cvau + ic ivau + isb) | ~50 |
| C2 | Atomic Abstraction | ARM64 + RISC-V | ✅ DONE | atomic.c, atomic.h | ~350 |
| C3 | Alignment Audit | RISC-V | ✅ DONE | vir_platform.h, alignment_audit.py | ~200 |
| D1 | CUDA Driver Bridge | NVIDIA GPU | ✅ DONE | gpu_cuda.c | ~500 |
| D2 | PTX Emitter | NVIDIA GPU | ✅ DONE | ptx_gen.c | ~1,050 |
| D3 | Metal/AIR Backend | Apple GPU | ✅ DONE | gpu_metal.c | ~960 |
| D4 | GPU Kernel Library | All GPU | ✅ DONE | codegen_gpu.py, data/gpu/ | ~800 |
| | | | **14/14 HOÀN THÀNH** | | **~6,550** |

---

## THỨ TỰ THỰC HIỆN ĐỀ XUẤT

```
Sprint 1 (Cao nhất — Unlock core language features):
  C1 → A5 → A1 → A2
  (Bug fix cache → Fix reg allocator → Pattern match → Async)

Sprint 2 (Performance — Thu hẹp gap với C):
  A4 → A3 → B1 → B2
  (AMX GEMM → SIMD I/O → Metadata specs → Meta-compiler)

Sprint 3 (GPU — Mở rộng sang accelerator):
  D1 → D2 → D4 → D3
  (CUDA bridge → PTX emitter → Kernel lib → Metal)

Sprint 4 (Cross-platform — RISC-V readiness):
  C2 → C3
  (Atomics → Alignment)
```

---

*Tài liệu kỹ thuật Phase 2 — Vir Codebase, 10/03/2026*
*Cập nhật lần cuối: 11/03/2026 — **ALL 14 TASKS COMPLETED** ✅*

### Test Results (11/03/2026)
- C native: **89/89** passed
- Python: **656/656** passed
- Virgex: **113/113** passed
- Build: libvir_core.dylib + libvir_core.a + vir CLI ✅

---

### → Tiếp theo: [PHASE3_ROADMAP_DETAILED.md](PHASE3_ROADMAP_DETAILED.md)

Phase 3 "Make It Real" — 20 tasks · 5 pillars · ~14,870 LOC:
- **Pillar E**: Generics, Traits, Pattern Matching, Error Handling
- **Pillar F**: LSP Server, Formatter, Package Manager, Debugger
- **Pillar G**: Network/Thread/FFI/GPU native backing
- **Pillar H**: Bootstrap optimizer, memory management, x86_64, Virgex self-host
- **Pillar I**: Syntax reconciliation, Closures, Safe operators, Vietnamese errors
