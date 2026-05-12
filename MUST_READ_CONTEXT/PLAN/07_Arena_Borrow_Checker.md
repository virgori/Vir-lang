# Kế hoạch: Quản lý Bộ nhớ Arena + Borrow Checker (Thay thế RC)

> **Ngày lập:** 24/03/2026  
> **Trạng thái hiện tại:** RC (Reference Counting) — không cycle detection, O(n) cleanup  
> **Mục tiêu:** Arena-first allocation + compile-time Borrow Checker thay RC runtime overhead  
> **Scope:** C engine (`core/src/`) + Vir stdlib (`stdlib/vir/`) + Vir compiler self-hosted

---

## MỤC LỤC

1. [Phân tích Hiện trạng](#1-phân-tích-hiện-trạng)
2. [Kiến trúc Mới: Arena + Borrow](#2-kiến-trúc-mới-arena--borrow)
3. [Phase A: Arena Allocator Thống nhất](#3-phase-a-arena-allocator-thống-nhất)
4. [Phase B: Borrow Checker Pass](#4-phase-b-borrow-checker-pass)  
5. [Phase C: Drop Insertion + Codegen](#5-phase-c-drop-insertion--codegen)
6. [Phase D: Loại bỏ RC](#6-phase-d-loại-bỏ-rc)
7. [Lộ trình Thực hiện](#7-lộ-trình-thực-hiện)
8. [Test & Verification](#8-test--verification)

---

## 1. Phân tích Hiện trạng

### 1.1 Hệ thống RC hiện tại (`mem_manager.c` — 267 LOC)

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIỆN TRẠNG: 3 ALLOCATOR                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Arena (64KB)         RC (header + refcount)      Pool (slab)  │
│   ┌──────────┐        ┌──────────────────┐        ┌──────────┐ │
│   │ bump ptr │        │ magic: 0xABCD1234│        │ free-list│ │
│   │ 8B align │        │ refcount: i32    │        │ intrusive│ │
│   │ no free  │        │ size: size_t     │        │ fixed-sz │ │
│   │ reset all│        │ [user data]      │        │ O(1)     │ │
│   └──────────┘        └──────────────────┘        └──────────┘ │
│                                                                  │
│   VAND: slab_alloc.c + numa_alloc.c + huge_alloc.c (800 LOC)   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Nhược điểm RC

| Vấn đề | Mức độ | Chi tiết |
|--------|--------|----------|
| **Không cycle detection** | 🔴 CRITICAL | Cycle → memory leak vĩnh viễn |
| **Runtime overhead** | 🟡 MEDIUM | Mỗi assign = retain + release (2 atomic ops) |
| **Cache-unfriendly** | 🟡 MEDIUM | Mỗi object = 1 malloc → phân tán heap |
| **Thread-unsafe** | 🔴 CRITICAL | `refcount++/--` không atomic |
| **16 bytes overhead/object** | 🟡 MEDIUM | magic + refcount + size header |

### 1.3 Nền tảng đã có

| Module | Vị trí | Trạng thái |
|--------|--------|-----------|
| Arena allocator (C) | `mem_manager.c` L31-89 | ✅ Sẵn sàng (64KB, 8B align) |
| Arena allocator (Vir) | `stdlib/vir/rt/alloc.vri` L72-113 | ✅ Sẵn sàng (1MB mmap, 16B align) |
| Heap free-list (Vir) | `stdlib/vir/rt/alloc.vri` L120-240 | ✅ First-fit + split |
| Escape Analysis pass | `ir_optimizer.vri` | ❌ **CHƯA IMPLEMENT** (ir_optimizer.vri chỉ có ~1,995 LOC, L2481 không tồn tại) |
| Deterministic Free pass | `ir_optimizer.vri` | ❌ **CHƯA IMPLEMENT** (không có `QOp::Free` trong QOp enum) |
| Pool allocator (C) | `mem_manager.c` L191-267 | ✅ Intrusive free-list |

**Kết luận:** ~40% infrastructure đã có (Arena allocator C + Vir, Pool allocator). Cần: (1) implement Escape Analysis, (2) implement Deterministic Free, (3) borrow checker MỚI, (4) drop insertion chính xác.

---

## 2. Kiến trúc Mới: Arena + Borrow

### 2.1 Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                    KIẾN TRÚC MỚI                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   COMPILE-TIME (Borrow Checker)         RUNTIME (Arena)         │
│   ┌──────────────────────────┐         ┌──────────────────────┐ │
│   │ 1. Ownership tracking    │         │ 1. Scoped arenas     │ │
│   │ 2. Borrow validation     │────────▶│ 2. Function arenas   │ │
│   │ 3. Lifetime inference    │         │ 3. Module arena      │ │
│   │ 4. Drop point insertion  │         │ 4. Global heap       │ │
│   └──────────────────────────┘         │    (for escapes)     │ │
│                                         └──────────────────────┘ │
│                                                                  │
│   ❌ LOẠI BỎ:                                                    │
│   - vir_rc_alloc / vir_rc_retain / vir_rc_release               │
│   - vir_rc_header_t (16 byte overhead)                          │
│   - g_mem_stats.current_objects tracking                        │
│                                                                  │
│   ✅ GIỮ LẠI:                                                    │
│   - vir_arena_* (nâng cấp)                                      │
│   - vir_pool_* (cho fixed-size objects)                         │
│   - slab_alloc (cho media/tensor)                               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Memory Hierarchy

```
                    ┌───────────────────────┐
                    │   Global Heap         │ ← escapes, long-lived
                    │   (free-list, mmap)   │
                    └───────────┬───────────┘
                                │ fallback
                    ┌───────────┴───────────┐
                    │   Module Arena        │ ← module-scoped data
                    │   (4MB, one per file) │   (string constants,
                    │                       │    type tables, etc.)
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Function Arena  │ │ Function Arena  │ │ Function Arena  │
    │ (64KB, reset    │ │ (64KB, reset    │ │ (64KB, reset    │
    │  on return)     │ │  on return)     │ │  on return)     │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Scope Arena     │ │ Scope Arena     │ │ Scope Arena     │
    │ (watermark      │ │ (watermark      │ │ (watermark      │
    │  save/restore)  │ │  save/restore)  │ │  save/restore)  │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.3 So sánh RC vs Arena+Borrow

| Tiêu chí | RC (hiện tại) | Arena + Borrow (mới) |
|----------|:---:|:---:|
| Cycle safety | ❌ Leak | ✅ Không có cycle vấn đề |
| Runtime overhead | 🟡 2 atomic ops/assign | ✅ 0 (bump pointer) |
| Memory locality | ❌ Phân tán | ✅ Sequential, cache-friendly |
| Per-object overhead | 16 bytes | 0 bytes |
| Thread safety | ❌ Non-atomic | ✅ Arena per-thread |
| Compile-time cost | 0 | 🟡 Borrow check pass |
| Deallocation | Individual release | Bulk reset (arena) |
| Long-lived objects | ✅ | ✅ (escape to heap) |

---

## 3. Phase A: Arena Allocator Thống nhất

### 3.1 Nâng cấp Arena (C engine)

**File:** `core/src/mem_manager.c`  
**Delta:** ~150 LOC mới, ~50 LOC sửa

```c
/* ═══════════════════════════════════════════════════════
 * Arena v2 — Hierarchical + Watermark
 * ═══════════════════════════════════════════════════════ */

typedef struct vir_arena_v2 {
    uint8_t     *base;
    size_t       capacity;
    size_t       offset;
    int          id;
    int          parent_id;      /* NEW: parent arena (-1 = root) */
    size_t       watermarks[32]; /* NEW: save/restore stack */
    int          watermark_top;  /* NEW: watermark stack pointer */
} vir_arena_v2_t;

/* Watermark save/restore — for scope-based allocation */
size_t vir_arena_save(int arena_id);
void   vir_arena_restore(int arena_id, size_t watermark);

/* Overflow: chain to new page instead of failing */
void  *vir_arena_alloc_v2(int arena_id, size_t size);
```

**Watermark Pattern:**
```c
// Enter scope
size_t mark = vir_arena_save(func_arena);

// Allocate freely inside scope
void *tmp1 = vir_arena_alloc(func_arena, 256);
void *tmp2 = vir_arena_alloc(func_arena, 128);

// Exit scope — everything since save is freed
vir_arena_restore(func_arena, mark);
```

### 3.2 Arena Overflow Chain

Hiện tại: arena hết → return NULL.  
Mới: arena hết → chain new page.

```c
typedef struct arena_page {
    uint8_t *base;
    size_t   capacity;
    size_t   offset;
    struct arena_page *next;  /* linked list of pages */
} arena_page_t;

typedef struct vir_arena_v2 {
    arena_page_t *current;    /* current active page */
    arena_page_t *pages;      /* all pages (for destroy) */
    size_t        page_size;  /* default: 64KB */
    int           id;
} vir_arena_v2_t;
```

### 3.3 VM Arena Integration

**File:** `core/src/vm.c`  
**Mục tiêu:** Thay `malloc` per-array/per-map bằng arena

```c
// TRƯỚC (hiện tại):
case Q_ARR_NEW:
    arr = calloc(1, sizeof(vm_array_t));    // ← malloc mỗi array
    arr->data = calloc(cap, sizeof(v_value_t));  // ← malloc data

// SAU:
case Q_ARR_NEW:
    arr = vir_arena_alloc(vm->func_arena, sizeof(vm_array_t));
    arr->data = vir_arena_alloc(vm->func_arena, cap * sizeof(v_value_t));
    // Arena reset khi function return → tự giải phóng
```

### 3.4 Deliverables Phase A

| # | Task | File | LOC |
|---|------|------|-----|
| A1 | Arena v2 with watermark + overflow chain | `mem_manager.c` | +150 |
| A2 | VM function arena (thay malloc per-array) | `vm.c` | +80 |
| A3 | IR lowering arena (thay scattered malloc) | `ir_lower.c` | +40 |
| A4 | Module arena for string constants | `q_ir.c` | +30 |
| A5 | Tests: arena watermark, overflow, bulk free | `core/tests/` | +100 |
| | **TỔNG** | | **~400** |

---

## 4. Phase B: Borrow Checker Pass

### 4.1 Tổng quan

Borrow Checker là **compiler pass** chạy sau IR lowering, trước codegen. Nó phân tích Q-IR để:
1. Xác định ownership của mỗi value
2. Validate borrows (không overlap mutable)
3. Tính toán drop points
4. Emit lỗi compile-time nếu vi phạm

```
Pipeline mới:

  AST → ir_lower → Q-IR → TCO pass → ★ Borrow Check ★ → Optimizer → Codegen
                                       │
                                       ├── Ownership inference
                                       ├── Borrow validation  
                                       ├── Lifetime analysis
                                       └── Drop point insertion
```

### 4.2 Ownership Model cho Vir

#### Nguyên tắc (đơn giản hơn Rust):

```
┌────────────────────────────────────────────────────────────────┐
│ OWNERSHIP RULES (SỐ HÓA)                                       │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Rule 1: Mỗi value có ĐÚNG MỘT owner tại mọi thời điểm        │
│                                                                 │
│ Rule 2: Khi owner ra khỏi scope → value bị DROP tự động        │
│                                                                 │
│ Rule 3: Value có thể được BORROW:                               │
│          & = shared (read-only, many)                           │
│          &mut = exclusive (read-write, one)                     │
│                                                                 │
│ Rule 4: Shared borrows và mutable borrow KHÔNG đồng thời       │
│                                                                 │
│ Rule 5: Borrow KHÔNG sống lâu hơn owner                        │
│                                                                 │
│ Rule 6: MOVE = transfer ownership (owner cũ invalid)            │
│                                                                 │
│ EXCEPTION (đơn giản hóa so với Rust):                           │
│ - int/float/bool: COPY implicit (không cần borrow)             │
│ - string literal: static lifetime (không cần borrow)           │
│ - Arena-allocated: scope-determined (không cần explicit drop)   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### Cú pháp Vir:

```vir
# Ownership (mặc định = own)
func process(data: [i32]) -> [i32]:     # data is owned, moved in
    out data;                             # ownership transferred out
end

# Shared borrow
func read_only(data: &[i32]) -> i32:    # read-only reference
    out data[0];
end

# Mutable borrow
func modify(data: &mut [i32]):          # exclusive mutable reference
    data[0] = 42;
end

# Copy types — không cần borrow
let x = 10;
let y = x;    # OK: int is Copy, x vẫn valid

# Move semantics — array/entity/string
let arr = [1, 2, 3];
let arr2 = arr;    # arr MOVED → arr2
# print(arr);      # COMPILE ERROR: use after move

# Borrow then use
let arr = [1, 2, 3];
let sum = read_only(&arr);    # borrow, arr vẫn valid
modify(&mut arr);             # exclusive borrow
print(arr[0]);                # arr vẫn valid, borrow đã end
```

### 4.3 Implementation: Q-IR Borrow Checker

**File mới:** `core/src/borrow_check.c` (~800 LOC)

#### 4.3.1 Data Types

```c
/* ═══ Ownership State ═══ */
typedef enum {
    OWN_OWNED,        /* value is owned by this variable */
    OWN_MOVED,        /* ownership transferred away */
    OWN_BORROWED,     /* currently borrowed (shared) */
    OWN_MUT_BORROWED, /* currently borrowed (exclusive) */
    OWN_COPY,         /* Copy type: int, float, bool */
    OWN_STATIC,       /* static lifetime: string literals */
} ownership_state_t;

/* ═══ Borrow Record ═══ */
typedef struct {
    uint32_t borrower_vreg;  /* who is borrowing */
    uint32_t owner_vreg;     /* who is being borrowed */
    uint32_t start_ip;       /* borrow starts at instruction # */
    uint32_t end_ip;         /* borrow ends at last use of borrower */
    bool     is_mutable;     /* &mut vs & */
} borrow_record_t;

/* ═══ Variable Info ═══ */
typedef struct {
    uint32_t         vreg;
    ownership_state_t state;
    uint32_t         birth_ip;    /* where this value was created */
    uint32_t         death_ip;    /* last use (for liveness) */
    uint32_t         moved_at;    /* IP where moved (if MOVED) */
    uint32_t         borrow_count;
    bool             is_copy_type;
} var_info_t;

/* ═══ Borrow Checker Context ═══ */
typedef struct {
    var_info_t      vars[4096];
    uint32_t        var_count;
    borrow_record_t borrows[1024];
    uint32_t        borrow_count;
    uint32_t        drop_points[4096]; /* IP where to insert Q_FREE */
    uint32_t        drop_count;
    /* Error reporting */
    char             errors[64][256];
    int              error_count;
} borrow_ctx_t;
```

#### 4.3.2 Main Algorithm

```c
int borrow_check_function(borrow_ctx_t *ctx, const q_function_t *func) {
    /* Pass 1: Scan — build variable table + liveness */
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        const q_instruction_t *instr = &func->body[ip];
        scan_instruction(ctx, instr, ip);
    }
    
    /* Pass 2: Infer ownership — determine which vars own heap data */
    for (uint32_t i = 0; i < ctx->var_count; i++) {
        infer_ownership(ctx, &ctx->vars[i], func);
    }
    
    /* Pass 3: Check borrows — validate no conflicts */
    for (uint32_t i = 0; i < ctx->borrow_count; i++) {
        check_borrow_rules(ctx, &ctx->borrows[i]);
    }
    
    /* Pass 4: Check use-after-move */
    for (uint32_t ip = 0; ip < func->body_count; ip++) {
        check_use_after_move(ctx, &func->body[ip], ip);
    }
    
    /* Pass 5: Compute drop points */
    compute_drop_points(ctx, func);
    
    return ctx->error_count;
}
```

#### 4.3.3 Type Classification

```c
static bool is_copy_type(const char *type_name) {
    /* Primitive types → Copy (no borrow needed) */
    if (strcmp(type_name, "int") == 0) return true;
    if (strcmp(type_name, "i32") == 0) return true;
    if (strcmp(type_name, "i64") == 0) return true;
    if (strcmp(type_name, "float") == 0) return true;
    if (strcmp(type_name, "f32") == 0) return true;
    if (strcmp(type_name, "f64") == 0) return true;
    if (strcmp(type_name, "bool") == 0) return true;
    return false;
}
/* Non-copy types: string, array, entity, map → MOVE semantics */
```

#### 4.3.4 Borrow Conflict Detection

```c
static int check_borrow_rules(borrow_ctx_t *ctx, const borrow_record_t *br) {
    /* Rule: At any IP, for a given owner:
     *   - 0 or more shared borrows (&), OR
     *   - exactly 1 mutable borrow (&mut), but NOT both */
    
    for (uint32_t i = 0; i < ctx->borrow_count; i++) {
        const borrow_record_t *other = &ctx->borrows[i];
        if (other == br) continue;
        if (other->owner_vreg != br->owner_vreg) continue;
        
        /* Check overlap: [start, end] ranges intersect? */
        if (br->start_ip > other->end_ip) continue;
        if (br->end_ip < other->start_ip) continue;
        
        /* Overlapping borrows on same owner */
        if (br->is_mutable || other->is_mutable) {
            /* CONFLICT: mutable + anything = error */
            snprintf(ctx->errors[ctx->error_count++], 256,
                "error: cannot borrow R%u as %s because it is "
                "already borrowed as %s (at IP %u-%u vs %u-%u)",
                br->owner_vreg,
                br->is_mutable ? "&mut" : "&",
                other->is_mutable ? "&mut" : "&",
                br->start_ip, br->end_ip,
                other->start_ip, other->end_ip);
            return -1;
        }
    }
    return 0;
}
```

### 4.4 Deliverables Phase B

| # | Task | File | LOC |
|---|------|------|-----|
| B1 | Borrow checker core (ctx, scan, infer) | `borrow_check.c` | +350 |
| B2 | Conflict detection + use-after-move | `borrow_check.c` | +200 |
| B3 | Drop point computation | `borrow_check.c` | +150 |
| B4 | Error messages (Rust-quality) | `borrow_check.c` | +100 |
| B5 | Header file + integration hooks | `borrow_check.h` | +50 |
| B6 | Tests: borrow conflicts, moves, drops | `core/tests/` | +200 |
| | **TỔNG** | | **~1,050** |

---

## 5. Phase C: Drop Insertion + Codegen

### 5.1 Q-IR Drop Instructions

Borrow checker xác định drop points → emit `Q_FREE` instruction tại đúng vị trí:

```
TRƯỚC (RC):
  Q_CALL_FUNC  <some_func>    # may retain/release internally
  Q_RET        R0              # hope refcount reaches 0

SAU (Arena + Borrow):
  Q_CALL_FUNC  <some_func>
  Q_FREE       R3              # ← borrow checker inserted: R3 dies here  
  Q_FREE       R7              # ← R7 dies here
  Q_RET        R0              # R0 ownership transferred to caller
```

### 5.2 IR Optimizer Integration

Nâng cấp 2 pass đã có:

| Pass | Tên | Hiện tại | Nâng cấp |
|------|-----|---------|----------|
| Pass 8 | Escape Analysis | Marks promotable allocs | + Arena promotion decision |
| Pass 9 | Deterministic Free | Inserts Free before Ret | + Use borrow checker drop points |

```vir
# ir_optimizer.vri — nâng cấp pass 9
func opt_deterministic_free_v2:
    in(func: QFunction, drop_points: vec<DropPoint>)
    # Thay vì chỉ insert Free trước Ret,
    # insert tại ĐÚNG vị trí borrow checker chỉ định
    for dp in drop_points:
        insert_free_at(func, dp.ip, dp.vreg);
    end
    out func;
end
```

### 5.3 Codegen: Arena vs Heap

```c
/* codegen.c — allocation strategy decision */
static void emit_alloc(codebuf_t *cb, target_arch_t arch,
                       uint32_t dest_vreg, uint32_t size,
                       alloc_strategy_t strategy) {
    switch (strategy) {
    case ALLOC_ARENA:
        /* Fast path: bump pointer */
        // arena->offset += aligned_size;
        // return arena->base + old_offset;
        break;
    case ALLOC_HEAP:
        /* Slow path: for escaping allocations */
        // call malloc
        break;
    case ALLOC_STACK:
        /* Fastest: promoted by escape analysis */
        // sub sp, sp, #size
        break;
    }
}
```

### 5.4 Deliverables Phase C

| # | Task | File | LOC |
|---|------|------|-----|
| C1 | Drop insertion engine | `borrow_check.c` | +100 |
| C2 | ir_optimizer.vri pass 9 upgrade | `ir_optimizer.vri` | +80 |
| C3 | Codegen arena/heap/stack strategy | `codegen.c` | +120 |
| C4 | main.c pipeline hook (after TCO) | `main.c` | +20 |
| | **TỔNG** | | **~320** |

---

## 6. Phase D: Loại bỏ RC

### 6.1 Migration Plan

```
Step 1: Thêm Arena + Borrow (Phase A-C) — song song với RC
Step 2: Báo lỗi khi dùng RC pattern (warning → error)
Step 3: Update tất cả callsite:
        vir_rc_alloc()   → vir_arena_alloc() hoặc heap_alloc()
        vir_rc_retain()  → (xóa — không cần)
        vir_rc_release() → (xóa — borrow checker handles drops)
Step 4: Xóa RC code (~60 LOC)
Step 5: Xóa g_mem_stats RC tracking
```

### 6.2 Files cần thay đổi

| File | Thay đổi | Est. |
|------|---------|------|
| `mem_manager.c` | Xóa RC section (L108-168), giữ Arena + Pool | -60 LOC |
| `mem_manager.h` | Xóa `vir_rc_*` prototypes | -10 LOC |
| `vm.c` | Strings → arena intern, Arrays → arena | +50 LOC |
| `ir_lower.c` | Module arena for string pool | +20 LOC |
| Bất kỳ caller nào dùng `vir_rc_*` | Migrate | ~30 LOC |

### 6.3 Deliverables Phase D

| # | Task | LOC |
|---|------|-----|
| D1 | Remove RC section from mem_manager | -60 |
| D2 | Update all callsites | ~30 |
| D3 | Verify 0 `vir_rc_` references in codebase | 0 |
| D4 | ASAN verification | 0 |
| | **NET** | **~-30** |

---

## 7. Lộ trình Thực hiện

```
┌──────────────────────────────────────────────────────────────────┐
│                       TIMELINE                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Phase A: Arena Thống nhất                          ~400 LOC      │
│ ├── A1: Arena v2 (watermark + overflow)                          │
│ ├── A2: VM arena integration                                    │
│ ├── A3: IR lowering arena                                       │
│ ├── A4: Module arena                                            │
│ └── A5: Tests                                                   │
│                                                                   │
│ Phase B: Borrow Checker                            ~1,050 LOC   │
│ ├── B1: Core scanner + ownership inference                      │
│ ├── B2: Conflict detection + use-after-move                     │
│ ├── B3: Drop point computation                                  │
│ ├── B4: Error messages                                          │
│ ├── B5: Header + integration                                    │
│ └── B6: Tests                                                   │
│                                                                   │
│ Phase C: Drop Insertion + Codegen                  ~320 LOC     │
│ ├── C1: Drop insertion engine                                   │
│ ├── C2: Optimizer pass 9 upgrade                                │
│ ├── C3: Codegen allocation strategy                             │
│ └── C4: Pipeline hook                                           │
│                                                                   │
│ Phase D: RC Removal                                ~-30 LOC     │
│ ├── D1: Remove RC code                                          │
│ ├── D2: Migrate callsites                                       │
│ └── D3-D4: Verify + ASAN                                        │
│                                                                   │
│ TỔNG NET DELTA: ~1,740 LOC (thêm) - 70 LOC (xóa) = ~1,670 LOC │
└──────────────────────────────────────────────────────────────────┘
```

### Dependency Graph

```
Phase A (Arena) ──────────────────────┐
                                       ├──▶ Phase D (RC Removal)
Phase B (Borrow Checker) ─────┐       │
                                ├──▶ Phase C (Drop + Codegen) ──┘
Phase B không phụ thuộc A     │
Phase C phụ thuộc B           │
Phase D phụ thuộc A + C       │
```

**Có thể làm song song:** Phase A và Phase B độc lập — 2 người/2 session.

---

## 8. Test & Verification

### 8.1 Test Cases cho Borrow Checker

```vir
# TEST 1: Use-after-move → COMPILE ERROR
func test_use_after_move():
    let arr = [1, 2, 3];
    let arr2 = arr;       # move
    print(arr[0]);        # ERROR: use of moved value 'arr'
end

# TEST 2: Mutable + shared borrow conflict → COMPILE ERROR
func test_borrow_conflict():
    let arr = [1, 2, 3];
    let r1 = &arr;        # shared borrow
    modify(&mut arr);     # ERROR: cannot borrow as &mut while & exists
    print(r1[0]);         # r1 still alive → conflict
end

# TEST 3: Sequential borrows → OK
func test_sequential_borrows():
    let arr = [1, 2, 3];
    let sum = read_only(&arr);   # OK: shared borrow, ends before next line
    modify(&mut arr);            # OK: previous borrow ended
end

# TEST 4: Copy types → no borrow needed
func test_copy():
    let x = 10;
    let y = x;      # COPY, not move
    print(x + y);   # OK: both valid
end

# TEST 5: Arena scope → auto-drop
func test_arena_scope():
    let arr = [1, 2, 3];     # allocated in function arena
    if true:
        let tmp = [4, 5, 6]; # allocated in scope arena  
        print(tmp[0]);
    end                        # tmp auto-dropped (arena watermark restore)
    print(arr[0]);             # arr still valid
end                            # arr auto-dropped (function arena reset)

# TEST 6: Escape to caller → heap allocation
func test_escape() -> [i32]:
    let arr = [1, 2, 3];     # escape analysis detects return
    out arr;                   # moved to heap, caller owns
end
```

### 8.2 Regression Tests

| Suite | Count | Phải pass |
|-------|-------|-----------|
| virc E2E tests (`run_tests.sh`) | 46 | ✅ 100% |
| vtest framework (`~796 funcs`) | ~796 | ✅ 100% |
| virc.vri dump (0 lỗi) | 1 | ✅ 0 errors |
| Arena watermark tests | 5 | ✅ |
| Borrow checker tests | 10+ | ✅ |
| ASAN (DEBUG=1) | 1 | ✅ 0 memory errors |

### 8.3 Performance Benchmarks

| Metric | RC (baseline) | Arena+Borrow (target) |
|--------|:---:|:---:|
| Alloc throughput | ~50M ops/s | ~500M ops/s (bump) |
| Per-alloc overhead | 16 bytes header | 0 bytes |
| Dealloc cost | O(1) per object | O(1) bulk (arena reset) |
| Compile time | 0 (no check) | +5-10% (borrow pass) |
| Cache hit rate | Low (scattered) | High (sequential) |

---

## Tổng kết

| Phase | LOC | Files | Mục tiêu |
|-------|-----|-------|----------|
| **A** Arena | +400 | `mem_manager.c`, `vm.c`, `ir_lower.c` | Arena thống nhất, watermark |
| **B** Borrow | +1,050 | `borrow_check.c/h` (MỚI) | Compile-time safety |
| **C** Codegen | +320 | `borrow_check.c`, `ir_optimizer.vri`, `codegen.c` | Drop insertion |
| **D** RC Remove | -30 | `mem_manager.c/h` | Xóa RC overhead |
| **TỔNG** | **~1,740** | **8 files** | **Zero-RC, Arena-first, Borrow-safe** |

---

*Tài liệu này thay thế phần RC trong `mem_manager.c` (267 LOC).*  
*Tham chiếu: `Vir_Stage4_Kill_C_Master_Plan.md` §4.1 Borrow Checker.*  
*Nền tảng cần xây: Escape Analysis pass + Deterministic Free pass (CHƯA có trong `ir_optimizer.vri`).*
