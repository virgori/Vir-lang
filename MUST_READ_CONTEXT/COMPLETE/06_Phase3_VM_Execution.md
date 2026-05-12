# Phase 3: VM Execution — Kế hoạch Chi tiết

> **Ngày lập:** 26/03/2026  
> **Cập nhật:** 11/04/2026  
> **Tiên quyết:** Phase 2 IR Lowering ✅ (601 hàm, 33,187 Q-IR, 0 lỗi)  
> **Mục tiêu:** Chạy Q-IR của virc.vri qua VM interpreter → verify correctness → tiến tới JIT  
> **Tham chiếu:** `Vir_Stage4_Kill_C_Master_Plan.md` → Phase 4.2-4.3  
> **TRẠNG THÁI:** 🟢 Phase 3A+ → Phase 6 HOÀN TẤT — virc.vri chạy trên C VM, compile **47 test programs** thành ARM64 binary hoạt động đúng. Optimization passes (fusion, BCE, autovec) done. 82 canonical QOp opcodes.

### ✅ ĐÃ ĐẠT ĐƯỢC (cập nhật 11/04/2026)
- **virc.vri chạy trên C VM** → compile source → ARM64 Mach-O binary
- **47/47 test programs pass**: hello world, arithmetic (5 ops), if-true/false/else/nested/eif, while, nested while, for-range, break, skip (continue), loop-N, func call, multi-func, recursion, fibonacci, mutual recursion, strings (var/concat/len/print_str_var), arrays (literal/get/set/push/len), entities (create/field access/field assign), enums, globals, combined patterns, stack spilling (20+ vars), higher-order functions (function pointers)
- **Phase 5 (2026-04-10):** Python removed, build hardened, heap-overflow fix
- **Phase 6 (2026-04-11):** 3 optimization passes (fusion, BCE, autovec), 82 canonical QOp opcodes, ARM64 SIMD handlers (12 NEON ops), fused op handlers (FusedMulAdd/BiasRelu/BiasGelu), float op handlers (FAdd–FCvtF2I)
- **20+ bugs fixed** (Fixes 1-20f documented in CURRENT_STATUS)
- **Backpatch system working**: labels, forward jumps, conditional branches, while loop back-edges
- **Cross-function calls working**: proper ABI via X0-X7 args, BL patching, callee-saved preservation
- **Recursion working**: factorial(10)=3628800, fib(10)=55, mutual recursion
- **Blocker #4 (Field Access) RESOLVED**: Entity field access/assign via inline field lookup + element index
- Xem chi tiết: `CURRENT_STATUS_2026_03_30.md`

---

## MỤC LỤC

1. [Tổng quan Pipeline](#1-tổng-quan-pipeline)
2. [Phân tích Blocker](#2-phân-tích-blocker)
3. [Kế hoạch thực thi 5 bước](#3-kế-hoạch-thực-thi-5-bước)
4. [Chi tiết kỹ thuật](#4-chi-tiết-kỹ-thuật)
5. [Test & Verification](#5-test--verification)
6. [Risk Matrix](#6-risk-matrix)
7. [Metrics thành công](#7-metrics-thành-công)

---

## 1. Tổng quan Pipeline

```
                        PHASE 2 (DONE)              PHASE 3 (THIS)
                        ─────────────               ─────────────
virc.vri (~9,107 LOC core)
    │
    ▼
┌─────────────┐     ┌────────────────┐     ┌────────────────┐
│  frontend()  │────▶│ lower_program()│────▶│ lower_tco_pass │
│  Lex+Parse   │     │   601 funcs    │     │   Tail Call Opt│
└─────────────┘     └────────────────┘     └───────┬────────┘
                                                    │
                     ┌──────────────────────────────┤
                     ▼                              ▼
              ┌─────────────┐              ┌─────────────────┐
              │  cmd_dump   │              │    cmd_run       │◀── Phase 3A
              │  (text out) │ ✅ DONE      │  VM Interpreter  │
              └─────────────┘              └────────┬────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │    cmd_jit       │◀── Phase 3B
                                           │  ARM64/x86 JIT  │
                                           └────────┬────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │  Self-compile    │◀── Phase 3C
                                           │  virc compiles   │
                                           │  virc.vri        │
                                           └─────────────────┘
```

### Lệnh hiện tại

```bash
# Phase 2 done:
cd Vir && core/build/vir dump stdlib/vir/compiler/virc.vri    # ✅ 0 lỗi

# Phase 3 target:
cd Vir && core/build/vir run stdlib/vir/compiler/virc.vri test.vri   # ← MỤC TIÊU
cd Vir && core/build/vir jit stdlib/vir/compiler/virc.vri            # ← NÂNG CAO
```

---

## 2. Phân tích Blocker

### 2.1 Blocker #1: 38+ Extern Stub Functions (CRITICAL)

Phase 2 auto-registered ~38 functions as extern stubs (có `func_idx` nhưng `body_count == 0`).  
Khi VM gọi `Q_CALL_FUNC` → `vm->current_func = callee` → `vm->ip = 0` → **đọc instr[0] không tồn tại → crash/UB**.

**Danh sách extern stubs (xác định từ Phase 2 log):**

| # | Tên | Nguồn gốc | Cần implement |
|---|-----|-----------|---------------|
| 1 | `panic` | runtime | ✅ VM intrinsic (print + exit) |
| 2 | `size_of` | runtime | ✅ Return sizeof(i64) = 8 |
| 3 | `native_load` | runtime | ✅ Memory read |
| 4 | `native_store` | runtime | ✅ Memory write |
| 5 | `native_alloc` | alloc.vri | ✅ Map to Q_ARR_NEW or malloc |
| 6 | `native_dealloc` | alloc.vri | ✅ Free |
| 7 | `Some` | option type | ✅ Return value as-is (tagged 1) |
| 8 | `None` | option type | ✅ Return 0 (tagged 0) |
| 9 | `Ok` | result type | ✅ Return value (tagged 1) |
| 10 | `Err` | result type | ✅ Return error (tagged 2) |
| 11 | `unwrap` | option/result | ✅ Extract value or panic |
| 12 | `is_some` / `is_ok` | option/result | ✅ Check tag |
| 13-20 | String ops | string_rt.vri | Map to Q_STR_* |
| 21-30 | Vec ops | vec_rt.vri | Map to Q_ARR_* |
| 31-38 | I/O, math, misc | io.vri, etc. | Map to existing VM ops |

**Giải pháp:** Thêm **intrinsic dispatch** trong `vm.c` `Q_CALL_FUNC` handler:

```c
case Q_CALL_FUNC: {
    // ... existing code ...
    const q_function_t *callee = &vm->module->functions[fidx];
    
    // NEW: Handle extern stubs (body_count == 0)
    if (callee->body_count == 0) {
        return vm_call_intrinsic(vm, callee->name, instr);
    }
    // ... existing switch to callee ...
}
```

### 2.2 Blocker #2: Missing Q-IR Opcodes (MEDIUM)

`codegen_wasm.vri` references opcodes không có trong `q_opcode_t`:

| Opcode | Dùng trong | Giải pháp |
|--------|-----------|-----------|
| `QOp.LoadString` | codegen_wasm.vri | Thêm `Q_LOAD_STRING` vào enum |
| `QOp.FCvtI2F` | codegen_wasm.vri | Thêm `Q_FCVT_I2F` (map to `Q_I_TO_F`) |
| `QOp.FCvtF2I` | codegen_wasm.vri | Thêm `Q_FCVT_F2I` (map to `Q_F_TO_I`) |

**Lưu ý:** Trong Phase 2, chúng ta đã tolerance-skip các trường hợp này. Trong Phase 3, phải thêm opcodes thật vào enum hoặc alias chúng.

### 2.3 Blocker #3: Higher-Order Function Calls (MEDIUM)

Phase 2 tolerance: `f(x)`, `pred(x)`, `emit_fn(...)` — local function variables called as functions.  
Lowered thành `Q_LOAD rd, 0` (dummy).  
Khi VM execute, kết quả sẽ sai (always 0 thay vì call thật).

**Giải pháp:** Implement `Q_CALL_INDIRECT` — call qua vreg chứa func pointer/index.

```c
case Q_CALL_INDIRECT: {
    uint32_t fidx = vm->regs[instr->src1.vreg].as_int;
    // ... same as Q_CALL_FUNC nhưng dynamic fidx ...
}
```

### 2.4 Blocker #4: Record/Entity Field Access (LOW) — ✅ RESOLVED

Phase 2 tolerance: unknown fields → offset 0. VM sẽ đọc sai field.

**GIẢI QUYẾT (02/04/2026):** Entity field access/assign hoạt động qua inline field lookup + LoadWord/StoreWord element index. 4 entity tests + combined test pass. Xem CURRENT_STATUS Fixes 18b-18h.

### 2.5 Priority Matrix

```
┌────────────────────────────────────────────────────────┐
│ Priority │ Blocker                   │ Impact │ Effort │
├──────────┤───────────────────────────┤────────┤────────┤
│ P0       │ Extern stub intrinsics    │ CRASH  │ ~300L  │
│ P1       │ Higher-order calls        │ WRONG  │ ~150L  │
│ P2       │ Missing opcodes           │ WRONG  │ ~50L   │
│ P3       │ Field offset accuracy     │ WRONG  │ ~200L  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Kế hoạch thực thi 5 bước

### Bước 1: VM Intrinsic Dispatch (~300 LOC)

**File:** `core/src/vm.c`  
**Mục tiêu:** Xử lý 38+ extern stubs không crash

```
1.1  Thêm vm_call_intrinsic(vm, name, instr) → vm_status_t
1.2  Dispatch theo tên:
     - "panic"         → fprintf(stderr, msg) + return VM_HALT
     - "size_of"       → regs[0] = 8; return VM_OK
     - "native_load"   → regs[0] = *(int64_t*)regs[0].as_ptr
     - "native_store"  → *(int64_t*)regs[0].as_ptr = regs[1].as_int
     - "native_alloc"  → regs[0].as_ptr = malloc(regs[0].as_int)
     - "native_dealloc"→ free(regs[0].as_ptr)
     - "Some/Ok"       → regs[0] = {tag:1, value:regs[0]}
     - "None"          → regs[0] = {tag:0, value:0}
     - "Err"           → regs[0] = {tag:2, value:regs[0]}
     - Fallback        → fprintf(stderr, "unimplemented intrinsic: %s\n", name)
1.3  Hook into Q_CALL_FUNC: nếu body_count == 0 → vm_call_intrinsic
1.4  Test: chạy simple program calling Some/panic/size_of
```

**Verification:**
```bash
core/build/vir run tests/e2e/test_intrinsics.vri    # phải pass
core/build/vir run stdlib/vir/compiler/virc.vri -v   # không crash
```

### Bước 2: Q_CALL_INDIRECT (~150 LOC)

**Files:** `core/include/q_ir.h`, `core/src/ir_lower.c`, `core/src/vm.c`  
**Mục tiêu:** Higher-order call `f(x)` → dynamic dispatch

```
2.1  Thêm Q_CALL_INDIRECT vào q_opcode_t enum
2.2  ir_lower.c AST_CALL: nếu sym_lookup tìm thấy local var → emit Q_CALL_INDIRECT rd, vreg
2.3  vm.c: case Q_CALL_INDIRECT → read func_idx from vreg → dispatch
2.4  Test: callback pattern
```

```c
// ir_lower.c — thay thế tolerance path hiện tại
if (sym) {
    // e.g., "f" is a local variable holding func index
    emit(ctx, Q_CALL_INDIRECT, dst, sym->vreg, 0);
}
```

### Bước 3: Missing Opcodes & Aliases (~50 LOC)

**Files:** `core/include/q_ir.h`, `core/src/vm.c`

```
3.1  Thêm vào q_opcode_t:
     Q_LOAD_STRING  = 0xC0  # Load string constant
     Q_FCVT_I2F     = 0xC1  # Alias cho Q_I_TO_F
     Q_FCVT_F2I     = 0xC2  # Alias cho Q_F_TO_I
3.2  vm.c handlers:
     case Q_LOAD_STRING: → Q_STR_ALLOC path
     case Q_FCVT_I2F:    → same as Q_I_TO_F
     case Q_FCVT_F2I:    → same as Q_F_TO_I
3.3  ir_lower.c: update field_access cho QOp enum → emit đúng opcode
```

### Bước 4: Record Field Registry Accuracy (~200 LOC)

**File:** `core/src/ir_lower.c`  
**Mục tiêu:** Correct field offsets thay vì offset 0 tolerance

```
4.1  Record type registry: khi gặp AST_RECORD_DEF, ghi lại field {name, offset, type}
4.2  AST_FIELD_ACCESS: lookup field → emit Q_GET_FIELD rd, base, correct_offset
4.3  AST_RECORD_LITERAL: emit Q_ENTITY_NEW + Q_SET_FIELD cho mỗi field
4.4  Test: struct tạo/truy cập các field
```

### Bước 5: Integration Test — VM Execute virc.vri (~100 LOC test)

```
5.1  Chạy: core/build/vir run stdlib/vir/compiler/virc.vri test_simple.vri
     - virc.vri đọc test_simple.vri → lex → parse → lower → codegen
     - Output: assembly hoặc binary
5.2  Verify output khớp với self-hosted virc output
5.3  Nếu pass → Phase 3 COMPLETE
5.4  Benchmark: instruction count, wall time
```

---

## 4. Chi tiết kỹ thuật

### 4.1 VM Intrinsic Dispatch Architecture

```c
/* vm.c — new function */
static vm_status_t vm_call_intrinsic(vm_state_t *vm, const char *name,
                                      const q_instruction_t *instr) {
    /* String comparison dispatch — ordered by frequency */
    if (strcmp(name, "Some") == 0 || strcmp(name, "Ok") == 0) {
        /* Tag value: {tag=1, value=R0} — just keep R0 as-is */
        return VM_OK;
    }
    if (strcmp(name, "None") == 0) {
        vm->regs[0] = (v_value_t){VAL_INT, {.as_int = 0}};
        return VM_OK;
    }
    if (strcmp(name, "Err") == 0) {
        /* For now: Err wraps the error value in R0 */
        return VM_OK;
    }
    if (strcmp(name, "panic") == 0) {
        if (vm->regs[0].type == VAL_STR)
            fprintf(stderr, "panic: %s\n", (char *)vm->regs[0].as_ptr);
        else
            fprintf(stderr, "panic: %lld\n", (long long)vm->regs[0].as_int);
        return VM_HALT;
    }
    if (strcmp(name, "size_of") == 0) {
        vm->regs[0] = (v_value_t){VAL_INT, {.as_int = 8}};
        return VM_OK;
    }
    if (strcmp(name, "native_alloc") == 0) {
        size_t sz = (size_t)vm->regs[0].as_int;
        vm->regs[0] = (v_value_t){VAL_PTR, {.as_ptr = calloc(1, sz)}};
        return VM_OK;
    }
    if (strcmp(name, "native_dealloc") == 0) {
        if (vm->regs[0].as_ptr) free(vm->regs[0].as_ptr);
        return VM_OK;
    }
    if (strcmp(name, "native_load") == 0) {
        int64_t *p = (int64_t *)vm->regs[0].as_ptr;
        vm->regs[0] = (v_value_t){VAL_INT, {.as_int = p ? *p : 0}};
        return VM_OK;
    }
    if (strcmp(name, "native_store") == 0) {
        int64_t *p = (int64_t *)vm->regs[0].as_ptr;
        if (p) *p = vm->regs[1].as_int;
        return VM_OK;
    }
    /* ... more intrinsics ... */
    
    fprintf(stderr, "[vm] warning: unimplemented intrinsic '%s'\n", name);
    vm->regs[0] = (v_value_t){VAL_INT, {.as_int = 0}};
    return VM_OK;
}
```

### 4.2 Q_CALL_INDIRECT Protocol

```
Instruction:  Q_CALL_INDIRECT  rd, vreg_func_idx
Semantics:    rd = call(functions[regs[vreg_func_idx]], R0..R(n-1))

Flow:
  1. Read func_idx = regs[vreg_func_idx].as_int
  2. Lookup callee = module->functions[func_idx]
  3. If body_count == 0 → vm_call_intrinsic
  4. Else → standard Q_CALL_FUNC path (save context, switch)
```

### 4.3 Pipeline hiện tại vs Cần thay đổi

| Component | Hiện tại | Cần thay đổi |
|-----------|---------|--------------|
| `ir_lower.c` | 2,144 LOC | +~100 LOC (indirect calls, correct field offsets) |
| `vm.c` | ~2,000 LOC | +~300 LOC (intrinsic dispatch, Q_CALL_INDIRECT) |
| `q_ir.h` | ~130 opcodes | +3 opcodes |
| `codegen.c` | 3,500+ LOC | Không đổi (Phase 3B mới dùng) |
| `main.c` | ~600 LOC | Không đổi |

---

## 5. Test & Verification

### 5.1 Progression Test Matrix

| Test | Command | Kỳ vọng | Phase | Trạng thái |
|------|---------|---------|-------|-----------|
| Existing E2E | `make test` | 89/89 pass (regression) | 3.0 | ✅ |
| Intrinsic basic | `vir run test_intrinsics.vri` | Some/None/panic work | 3.1 | ✅ (handled in Fix 1-9) |
| virc.vri compile hello | `vir run virc.vri test_hello.vri && ./a.out` | "hello world" | 3.5 | ✅ |
| virc.vri compile arithmetic | `vir run virc.vri test_arithmetic.vri && ./a.out` | 30,90,75,15,5 | 3.5 | ✅ |
| virc.vri compile if/else | `vir run virc.vri test_if_*.vri && ./a.out` | Correct branches | 3.5 | ✅ (3 tests) |
| virc.vri compile while | `vir run virc.vri test_while.vri && ./a.out` | 0,1,2,3,4 | 3.5 | ✅ |
| virc.vri compile reassign | `vir run virc.vri test_reassign.vri && ./a.out` | 6 | 3.5 | ✅ |
| Nested if/else | `vir run virc.vri test_nested_if.vri && ./a.out` | 2 | 3.6 | ✅ |
| For-range loops | `vir run virc.vri test_for_range.vri && ./a.out` | 0,1,2,3,4 | 3.6 | ✅ |
| Break/continue | `vir run virc.vri test_break/skip.vri && ./a.out` | Correct control | 3.6 | ✅ (2 tests) |
| Multi-function calls | `vir run virc.vri test_func_call.vri && ./a.out` | 10, 25 | 3.7 | ✅ (2 tests) |
| Recursion | `vir run virc.vri test_recursion.vri && ./a.out` | 120, 3628800 | 3.7 | ✅ |
| Fibonacci | `vir run virc.vri test_fib.vri && ./a.out` | 0, 1, 5, 55 | 3.7 | ✅ |
| Mutual recursion | `vir run virc.vri test_mutual_recursion.vri && ./a.out` | 1, 1, 0, 0 | 3.7 | ✅ |
| Loop N, eif, for accum | Multiple tests | Correct | 3.6 | ✅ (3 tests) |
| **Self-compile** | `vir run virc.vri -- compile virc.vri` | **Fixed-point** | 3.C | ⬜ |
| **Full Mach-O** (Phase 4.2) | `vir run virc.vri -- test_42.vri && ./a.out` | `42`, exit 0 | 4.2 | ✅ (08/04/2026) |

### 5.2 ASAN Verification

```bash
cd Vir/core && make cli DEBUG=1 && cd .. && core/build/vir run stdlib/vir/compiler/virc.vri test.vri
```

Mỗi bước phải pass ASAN (0 memory errors) trước khi tiến bước tiếp.

### 5.3 Performance Baseline

| Metric | Phase 2 (dump) | Phase 3 Target (run) |
|--------|----------------|---------------------|
| Lower time | <1s | <1s |
| Q-IR instrs | 33,187 | 33,187 |
| VM instrs executed | N/A | TBD (estimated ~1M for tokenize) |
| Wall time | <1s | <5s (tokenize simple file) |

---

## 6. Risk Matrix

| Risk | Xác suất | Tác động | Mitigation |
|------|----------|----------|------------|
| VM stack overflow (601 funcs recursive) | Cao | Crash | Tăng VM_MAX_CALL_DEPTH, tối ưu TCO |
| Sai field offset → wrong data | Trung bình | Wrong output | Step 4 registry fix |
| Intrinsic semantics mismatch | Trung bình | Wrong output | Test against self-hosted output |
| Chậm (VM interpret 33K instrs) | Thấp | Slow | Acceptable cho verification |
| Missing intrinsic → silent wrong result | Cao | Wrong output | Warn + track unimplemented calls |

---

## 7. Metrics thành công

### Phase 3A: VM Execution ✓

- [ ] `vir run virc.vri -- tokens test.vri` → output khớp self-hosted
- [ ] `vir run virc.vri -- dump test.vri` → Q-IR output hợp lệ
- [ ] 0 crash, 0 ASAN errors
- [ ] Tất cả 89 E2E tests regression pass

### Phase 3B: JIT Execution (tùy chọn)

- [ ] `vir jit virc.vri` → compile via `codegen_emit_full2`
- [ ] Cần hook `codegen_emit_full2` thay vì `codegen_emit_full` trong `cmd_jit`
- [ ] Cần register tất cả intrinsic addresses via `codegen_rt_init`

### Phase 3C: Self-Compile (ultimate goal)

- [ ] C engine chạy virc.vri → compile virc.vri → stage1 binary
- [ ] stage1 compile virc.vri → stage2 binary
- [ ] `diff stage1 stage2` = identical (fixed-point)
- [ ] **Khi đạt fixed-point → Stage 4 Kill C hoàn tất**

---

## Tổng kết LOC thay đổi dự kiến

| File | Thêm | Sửa | Tổng delta |
|------|------|-----|-----------|
| `vm.c` | ~300 | ~20 | +320 |
| `ir_lower.c` | ~100 | ~50 | +150 |
| `q_ir.h` | ~10 | 0 | +10 |
| Tests (mới) | ~100 | 0 | +100 |
| **Tổng** | | | **~580 LOC** |

---

*Tài liệu này là kế hoạch Phase 3 của Vir C engine bootstrap.*  
*Phase 2 report: `docs/PHASE2_IR_LOWERING_REPORT.md`*  
*Master plan: `MUST_READ_CONTEXT/Vir_Stage4_Kill_C_Master_Plan.md`*
