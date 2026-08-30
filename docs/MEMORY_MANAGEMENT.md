# Vir Memory Management Architecture & Specification

**Language Version**: v2.1.0  
**Target Architectures**: Apple Silicon ARM64, Linux x86_64, WebAssembly WASM32  
**Specification Level**: Master Technical Reference (Spec §11)

---

## 1. Executive Summary & Design Philosophy

The Vir programming language is engineered for systems-level execution where memory safety, deterministic latency, and maximum hardware throughput are critical. Unlike managed languages (Java, Go, C#) that rely on a runtime Garbage Collector (GC), and unlike pure manual languages (C) that lack compile-time lifecycle guarantees, **Vir employs a Multi-Tier Deterministic Memory Architecture**:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VIR HYBRID MEMORY ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Compile-Time Escape & Borrow Analysis (Zero-Cost Stack / SROA)          │
│  2. Region-Based Bump Arena Allocator (O(1) Sequential + Batch Reset)       │
│  3. Free-List Coalescing Heap Allocator (General Dynamic Lifetime)          │
│  4. Size-Class Slab Allocator (High-Throughput IO / Tensor Buffers)         │
│  5. Direct Kernel Page Allocator (mmap / munmap / madvise / mbind)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Tenets:
1. **Zero Garbage Collection (0 ms GC Pause):** No background tracing, no Stop-The-World (STW) pauses, and zero runtime thread stalls.
2. **Zero-Libc Kernel Discipline:** Memory allocation directly interfaces with OS kernel supervisor calls (`mmap` / `munmap` on macOS Darwin and Linux), completely bypassing C runtime `malloc`/`free`.
3. **Hardware-Aligned Coalescing:** All heap allocations enforce **16-byte alignment** for SIMD (ARM64 NEON / x86 AVX2) instructions.
4. **Predictable Deallocation:** Every memory region has a strictly defined lifecycle bound to lexical scopes, arenas, or explicit ownership transfers.

---

## 2. Compile-Time Memory Passes

Vir's self-hosted modular compiler (`virc`) eliminates runtime allocation overhead through static optimization passes:

### 2.1. Escape Analysis & SROA (Scalar Replacement of Aggregates)
- The compiler analyzes whether an `entity` or temporary buffer escapes the local function frame.
- **Non-escaping entities** are flattened into scalar CPU registers or placed on the call stack frame (`[SP, #offset]`), reducing heap allocation rate to zero for local variables.

### 2.2. Lexical Borrow & Ownership Tracking (`sem_pass8_borrow.vri`)
- Tracks pointer provenance and lifetimes across lexical blocks.
- Flags double-free and use-after-free conditions statically before machine code emission.

---

## 3. Runtime Allocator Architecture (`stdlib/vir/rt/alloc.vri`)

The Vir runtime provides three built-in allocation mechanisms:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            KERNEL VIRTUAL MEMORY                            │
│                      (sys_mmap / sys_munmap / PROT_RW)                      │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
                       ▼                               ▼
       ┌───────────────────────────────┐ ┌───────────────────────────┐
       │   Arena Allocator (Bump)      │ │  Heap Allocator (Free-List│
       │   [Base | Capacity | Offset]  │ │  [Header | Coalescing]    │
       └───────────────┬───────────────┘ └─────────────┬─────────────┘
                       │                               │
                       ▼                               ▼
            O(1) Compiler Phases,              General Dynamic
            Request Lifecycles, AST            Data Structures
```

---

### 3.1. Direct Page Allocator (Kernel Layer)

The foundation of all memory in Vir is the low-level page allocator:

```vir
# Low-level mmap/munmap interface (Pure Vir, Zero Libc)
const PAGE_SIZE:      16384;      # 16KB on Apple Silicon ARM64, 4KB on x86_64
const MIN_ARENA_SIZE: 1048576;    # 1MB minimum backing segment

func page_alloc(size: int):
    let pages = (size + PAGE_SIZE - 1) / PAGE_SIZE
    let actual = pages * PAGE_SIZE
    let ptr = sys_mmap(0, actual, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
    if ptr < 0 do out 0 end
    out ptr
end.

func page_free(ptr: int, size: int):
    let pages = (size + PAGE_SIZE - 1) / PAGE_SIZE
    let actual = pages * PAGE_SIZE
    sys_munmap(ptr, actual)
end.
```

---

### 3.2. Region-Based Bump Arena Allocator

The **Arena Allocator** is the fastest memory pattern in Vir ($O(1)$ allocation, $O(1)$ batch reset). It is used extensively across the compiler (AST nodes, token buffers, IR quads) and in high-throughput network handlers.

#### Memory Layout:
```text
┌───────────────────────────────────┬────────────────────────────────────────┐
│ Allocated Objects (16-byte align) │ Free Capacity (offset -> capacity)     │
└───────────────────────────────────┴────────────────────────────────────────┘
▲                                   ▲                                        ▲
base                                offset                                capacity
```

#### Operations:
- **`arena_new(size)`**: Obtains memory directly from `sys_mmap`.
- **`arena_alloc(arena, size)`**: Advances `offset` forward by 16-byte aligned `size`. Zero search cost ($O(1)$).
- **`arena_reset(arena)`**: Sets `offset = 0` in a single CPU cycle ($O(1)$), reusing the entire block without OS kernel context switches.
- **`arena_destroy(arena)`**: Releases the backing virtual memory pages via `sys_munmap`.

---

### 3.3. Free-List Coalescing Heap Allocator

For long-lived, dynamically resized objects with heterogeneous lifetimes, Vir provides a **First-Fit Free-List Heap Allocator** with automatic block coalescing.

#### Block Layout:
```text
┌──────────────────┬──────────────────┬──────────────────────────────────────┐
│  size: i64       │  flags: i64      │  User Payload (16-byte aligned)      │
│  (Total bytes)   │  (FREE or USED)  │  (returned pointer)                  │
└──────────────────┴──────────────────┴──────────────────────────────────────┘
▲                                     ▲
block_ptr                             user_ptr (block_ptr + 16)
```

#### Coalescing & Splitting Algorithm:
1. **Allocation (`heap_alloc`)**:
   - Traverses the singly-linked free list (`free_head`).
   - If a free block of `size >= needed` is found:
     * If `remainder >= 32 bytes`: **Splits** the block into `USED` block and a new `FREE` block.
     * Otherwise: Marks the entire block as `USED`.
2. **Deallocation (`heap_free`)**:
   - Marks block as `BLOCK_FREE`.
   - **Bidirectional Coalescing**: Inspects adjacent physical neighbors; merges consecutive free blocks into a single large continuous chunk to eliminate external memory fragmentation.

---

### 3.4. Size-Class Slab Allocator (High-Throughput IO)

For high-concurrency network servers and tensor computations, Vir includes a dedicated **Slab Allocator** (`core/src/slab_alloc.c`):

| Size Class | Buffer Size | Target Workload |
| :--- | :---: | :--- |
| **Class 0** | 64 KB | Network packet buffers, JSON parse chunks |
| **Class 1** | 1 MB | Standard file slurp buffers, AST tables |
| **Class 2** | 8 MB | Matrix / Tensor intermediate buffers |
| **Class 3** | 64 MB | Large audio/video buffers, batch neural layers |

- **Allocation Speed:** $O(1)$ pop from lock-free thread-local free-stacks.
- **Zero Kernel Overhead:** Reuses pre-allocated virtual memory slabs without triggering page faults.

---

## 4. Standard Library Memory API (`vir/mem/alloc`)

### 4.1. Core Functions

```vir
# General Heap Allocation
func alloc(size: int) -> ptr
func alloc_zeroed(size: int) -> ptr
func try_alloc(size: int) -> Result[ptr, AllocError]
func realloc(p: ptr, new_size: int) -> ptr
func free(p: ptr)

# Region Arena Management
func arena_new(size: int) -> Arena
func arena_alloc(arena: Arena, size: int) -> ptr
func arena_reset(arena: Arena) -> Arena
func arena_destroy(arena: Arena)
```

### 4.2. Concrete Usage Example

```vir
func process_request:
    # 1. Create a 64KB local request arena
    let arena = arena_new(65536)

    # 2. Fast sequential allocation (O(1))
    let req_buf = arena_alloc(arena, 1024)
    let json_tree = arena_alloc(arena, 4096)

    # 3. Use buffers...
    write_byte(req_buf, 0, 123)

    # 4. Instant O(1) cleanup — frees all allocations simultaneously
    arena_destroy(arena)
end.
```

---

## 5. Comparative Memory Matrix

| Metric | Vir (v2.1.0) | C (malloc/free) | Rust (Ownership/Borrow) | Go (GC) |
| :--- | :---: | :---: | :---: | :---: |
| **Garbage Collector** | **None (Zero-GC)** | None | None | Tracing Concurrent GC |
| **Pause Time (STW)** | **0.0 ms** | 0.0 ms | 0.0 ms | 0.5 – 5.0 ms |
| **Runtime Overhead** | **0 KB** | ~8 KB (`libc`) | ~30 KB (`libstd`) | ~1.2 MB (GC runtime) |
| **Syscall Interface** | **Direct Kernel (`mmap`)** | `brk` / `mmap` via libc | Allocator API via libc | Direct Syscalls |
| **Bulk Free Complexity** | **$O(1)$ (Arena)** | $O(N)$ individual free | $O(N)$ Drop traversal | $O(N)$ Mark-and-Sweep |
| **Memory Fragmentation** | **Low (Arena + Slab)** | High (Classic heap) | Low to Medium | Low (Compacting/Slab) |

---

## 6. Verification & Memory Diagnostics

Vir provides built-in memory isolation testing:
- **`cg_mem_alloc_zero.vri`**: Verifies zero-initialization semantics.
- **`cg_mem_alloc_isolation.vri`**: Verifies 16-byte alignment and boundary isolation between consecutive memory blocks.
- **Valgrind / AddressSanitizer Compatibility**: Memory maps are tracked with native ASan annotations when compiling with debugging symbols.
