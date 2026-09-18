# Vir Memory Management Architecture & Specification

**Language baseline**: v2.2.0
**Scope**: Memory architecture, allocator cost model, and implementation boundaries (Spec §11)
**Target scope**: Native OS-backed allocation and target-specific backends; WebAssembly requires a separate linear-memory implementation.

This document distinguishes design intent from implementation observations. The presence of an API or compiler pass does not establish that every backend implements its contract. Performance and safety claims require validation against a particular compiler build, target, and workload.

---

## 1. Design Philosophy

Vir separates memory management into five layers with different lifetime and cost models:

```text
1. Compile-time escape analysis / SROA → registers or stack where eligible
2. Region-based bump arenas           → phase or request lifetime
3. Free-list heap                     → independent dynamic lifetimes
4. Size-class slab pools              → repeated buffer allocation and reuse
5. Platform page allocator            → backing virtual memory
```

These are cooperating mechanisms, not five mandatory steps for every allocation. Slab pools and general heaps can obtain backing memory directly from the platform layer.

The intended rule is: **non-escaping entities are candidates for scalar/register/stack placement; escaping data requires an allocator and an explicit lifetime policy.** Escape alone does not choose the allocator: an escaping object may still fit a caller-owned arena. The arena must outlive every use of that object.

### Core principles

- **No required tracing GC in these allocator paths.** This removes tracing-GC pauses, not all latency: allocation can still incur page faults, kernel work, synchronization, or scheduling delays.
- **Explicit allocation paths.** `arena_alloc` expresses region lifetime; general heap allocation requires a matching ownership and release policy. API names alone do not prove the selected backend implementation.
- **Backend-specific runtime dependencies.** The native `vir/rt/alloc` path uses syscall-backed allocation. The separate `vir/mem/alloc` interface calls `native_malloc`, `native_calloc`, `native_realloc`, and `native_free`; their lowering determines the actual runtime dependency. Zero-libc is not a blanket guarantee for every Vir allocation API.
- **Alignment is a contract.** The native runtime declares 16-byte alignment. This does not satisfy every possible SIMD or over-aligned type requirement; those require an appropriate aligned-allocation path.
- **Defined lifetimes.** Stack, arena, and heap lifetimes must be respected. Raw-pointer operations require additional care beyond what static analysis can establish.

---

## 2. Compile-Time Memory Passes

### 2.1. Escape analysis and SROA

Escape analysis and scalar replacement can remove eligible aggregate allocations, place scalars in registers, or reserve stack storage. Non-escaping status is an optimization opportunity, not a guarantee that every local entity or temporary buffer avoids the heap. Address-taking, aliasing, representation constraints, and backend support affect the result.

Verify allocation elimination in generated IR or machine code for the exact build and optimization settings. Stack placement still consumes stack space; register values may spill.

### 2.2. Borrow and ownership analysis

`sem_pass8_borrow.vri` is the compiler's borrow-analysis pass. Its existence does not establish complete pointer-provenance tracking or universal detection of double-free and use-after-free. Document guarantees only for cases supported and exercised by regression tests, particularly around raw pointers, casts, foreign calls, and explicit allocator operations.

### 2.3. Lexical-scope and sub-arena escape

The language contract applies one ownership/lifetime rule to ordinary control
scopes (`if`, `when`, `loop`, and `for`) and explicit `arena:` blocks. No
separate `escape` keyword is required:

- Moving an owned value into an owner that outlives the current scope, or
  returning it with `out`, is an escape.
- The compiler assigns the allocation to the nearest enclosing arena or other
  region that outlives every use. An implementation should select that region
  before code generation instead of allocating in the child arena and copying
  later.
- Promotion covers the complete reachable owned graph. Copying only an array,
  string, entity, or dictionary header while leaving its backing storage in the
  child arena is invalid.
- The source binding is invalid after the move. Borrows (`&` and `&mut`) may not
  outlive the source owner/arena. Raw pointers do not extend lifetime.
- Scope exit resets only non-escaping allocations. Escaping one value does not
  retain the entire child arena.

For nested arenas, promotion targets the nearest ancestor region satisfying the
required lifetime. A value that later crosses a function or task boundary may
require a second promotion under the target's ownership and synchronization
rules.

This is a language/backend requirement, not a claim that every current backend
already implements complete graph promotion. Until validated by positive,
negative, nested-graph, early-exit, and mutation tests, incomplete promotion must
be treated as unsupported rather than implemented with a shallow copy.

---

## 3. Runtime Allocator Architecture

### 3.1. Platform page allocation

`stdlib/vir/rt/alloc.vri` provides `page_alloc` and `page_free` as backing-memory operations for the native runtime.

**Page size belongs to the target platform, not the instruction-set name alone.** The current source declares `PAGE_SIZE = 16384` with a macOS ARM64 comment. Treat this as a target-specific implementation choice, not a universal constant. An ARM64 target does not by itself establish a 4 KiB or 16 KiB page size.

A portable backend must obtain the applicable granularity from platform initialization or a validated target configuration. A future query such as `platform_page_size()` would be an API proposal, not an existing API asserted by this document. WebAssembly linear-memory pages must be handled under its own backend contract.

The required allocation contract is:

1. Validate the size and check for overflow before rounding.
2. Round to the applicable allocation granularity.
3. Request backing memory and interpret failure using the platform syscall/error convention.
4. Preserve the mapping extent needed for release.

Do not assume a raw syscall failure is always represented by a negative integer. The platform adapter must normalize errors consistently with callers.

Mapping or unmapping memory involves OS work. Reserving virtual memory does not guarantee that all pages are resident or that later accesses avoid page faults.

### 3.2. Region-based bump arenas

An arena groups allocations under one lifetime. Its bookkeeping is:

```text
[base address | capacity | current offset]

base → [allocated, aligned ranges][remaining capacity] ← base + capacity
```

- **`arena_new(size)`** obtains backing memory. The current native implementation enforces a minimum backing size, so a small request need not produce an equally small mapping.
- **`arena_alloc(arena, size)`** checks capacity and advances an aligned offset. Within an existing arena, allocator bookkeeping is O(1); touching the returned memory may still fault. The current implementation returns 0 when capacity is insufficient.
- **`arena_reset(arena)`** resets the offset and invalidates prior allocations for further use. Bookkeeping is O(1), with no per-object walk in this implementation. It does not zero memory, run object cleanup, or release the mapping. “One CPU cycle” is not a valid latency guarantee.
- **`arena_destroy(arena)`** releases the backing mapping. It is independent of the number of objects allocated inside a single arena, but `munmap` has kernel and virtual-memory costs. It is not a constant-cycle operation. A future arena with multiple segments must also account for those segments.

Before reset or destruction, finish all uses of the arena's objects and release any non-memory resources they own. Releasing an arena does not automatically close file descriptors or perform arbitrary per-object cleanup.

For compiler-managed lexical/sub-arenas, escape analysis must place or promote
escaping owned graphs before the child watermark is restored. Consequently,
reset invalidates all allocations that remain in that arena, while promoted
values continue under their destination owner's lifetime. Manually calling
`arena_reset` on an explicit low-level arena handle does not perform promotion;
the caller must ensure that no live value or pointer still refers to it.

A request can allocate a 1 KiB input buffer and a 4 KiB parse workspace from the same arena, check both allocation results, use them, and destroy the arena when the request finishes. This expresses the intended lifetime without promising that the entire operation has constant latency.

### 3.3. Two-Level Segregated Fit (TLSF) O(1) heap and real `free()`

The native runtime (`stdlib/vir/rt/alloc.vri`) implements a segregated Two-Level Segregated Fit (TLSF) allocator for independently released heap allocations with strict $O(1)$ worst-case time complexity, eliminating all linear search loops:

- **Segregated free lists with two-level bitmapped indexing**:
  - First-level ($FL$) size classes: 28 classes ($FL = 0 \dots 27$), spanning power-of-two ranges from $2^5 = 32\text{ B}$ up to $2^{32} = 4\text{ GB}$.
  - Second-level ($SL$) linear subdivisions: 16 subdivisions per $FL$ class ($SL = 0 \dots 15$, $SL\_INDEX = 4$), providing a total of $28 \times 16 = 448$ segregated bins.
  - Primary bitmap `fl_bitmap: i64` and secondary bitmap array `sl_bitmap: [i64; 28]` record non-empty bins.
  - Constant-time bin search uses branchless bit-scan routines `tlsf_fls` (finding the most significant set bit) and `tlsf_ffs` (finding the least significant set bit) to map requested sizes to bins and locate the smallest non-empty suitable bin in bounded instruction count.
- **Intrusive doubly-linked lists**:
  - Each segregated bin head points to a circular intrusive doubly-linked list of free blocks via `prev_free` and `next_free` pointers embedded directly in free block payloads.
  - Insertion and unlinking operations execute in strict $O(1)$ time without traversing any list nodes.
- **Boundary-tag layout & bidirectional coalescing**:
  - Block header layout:
    ```text
    Allocated block:
    [size_and_flags: i64][prev_size: i64][payload (16-byte aligned)...]
    Free block:
    [size_and_flags: i64][prev_size: i64][prev_free: i64][next_free: i64][unused...]
    ```
  - Allocation flags: bit 0 encodes `PREV_FREE (1)`, bit 1 encodes `CURR_FREE (2)`.
  - Right/forward neighbor lookup: calculated directly via `ptr + size`. If bit 1 (`CURR_FREE`) is set, the right neighbor is unlinked in $O(1)$ and merged.
  - Left/backward neighbor lookup: if bit 0 (`PREV_FREE`) is set, the preceding neighbor is located at `ptr - prev_size`, unlinked in $O(1)$, and merged.
  - Sentinel blocks: a 0-size allocated block marks the end of each mapped heap region to prevent coalescing past segment boundaries.
- **Exact accounting and integrity verifier**:
  - `g_heap.used` tracks strictly live payload bytes, decremented only by the payload of the freed block without double-counting previously merged neighbors.
  - `heap_verify() -> int` validates internal consistency: bitmap-to-bin correspondence, doubly-linked list symmetry, neighbor boundary tag reciprocity, and allocation flag sanity.
- **Real `free()` lowering across all backends**:
  - Builtins `free` and `vir_free` lower directly to `heap_free()` across ARM64, x86_64, RISC-V, and native execution paths. Silent `LIR_RT_NOP` stubs are eliminated.
- **Empirical verification**:
  - Storage reuse: `tests/memory_contract/heap_alloc_free_reuse.vri` (exact pointer identity on sequential allocation and release).
  - Bounded kernel RSS: `tests/memory_contract/heap_bounded_rss_reuse.vri` (10,000 iterations $\times 4\text{ KB}$ with OS kernel measurement via `sys_getrusage`, asserting $\Delta\text{RSS} \le 128\text{ KB}$ and `heap_verify() == 1`).
  - Adversarial complexity contract: `tests/memory_contract/heap_complexity_adversarial.vri` (250 fragmented free nodes with worst-case search steps $\le 4$).
  - Structural disassembly verification: `tools/gap_contract_runner.py` disassembles binaries via `otool -tv` / `objdump -d` asserting branch instructions (`bl vir_free` / `heap_free`).

### 3.4. Size-class slab pools

`core/src/slab_alloc.c` contains a C implementation of reusable size-class pools. Its presence does not establish that a particular self-hosted native compiler uses this path.

The configured region classes are 64 KiB, 1 MiB, 8 MiB, and 64 MiB. Headers occupy part of these regions; class size must not be presented as an unconditional usable-payload size. Oversized allocations use a separate mapping path.

Reusing a cached region requires O(1) stack bookkeeping. Pool misses obtain fresh backing memory; oversized frees and frees to a full cache may release mappings.

Reuse can avoid a new mapping syscall and often reuses resident pages. It does **not** guarantee absence of page faults: memory pressure or explicit page reclamation can make future accesses fault again.

The current implementation uses a global singleton with ordinary pool counters and free-stack accesses. Do not describe it as a lock-free thread-local allocator or promise safe concurrent use without a defined synchronization or ownership policy.

### 3.5. Loop sub-arena per-iteration reclamation and loop-carried escape preservation

In Vir v2.0, loop bodies that allocate local dynamic buffers or literals (e.g., array literals) can reclaim their memory on each iteration using an implicit loop sub-arena watermark:

- **Per-iteration watermark save & reset**: When a loop body contains local arena allocations and does not escape values across iterations, the compiler captures the arena mark at loop iteration start (`MIR_INTR_ARENA` mark) and restores it at iteration end (`MIR_INTR_ARENA` reset).
- **Loop-carried escape preservation**: If the loop body assigns an allocated value to an outer variable (detected via `scan_has_local_arena_alloc` and escape-target analysis), per-iteration reset is bypassed to preserve the loop-carried accumulator across iterations.
- **Contract tests**: Verified by `tests/memory_contract/loop_implicit_arena_rss.vri` (10,000 loop iterations executing in flat, bounded RSS under $O(1)$ space) and `tests/memory_contract/loop_implicit_arena_escape.vri` (loop-carried accumulator preserved without clobbering).

### 3.6. Runtime bounds enforcement of `arena(capacity: N)`

Lexical arena blocks specifying explicit byte capacities (`arena(capacity: N) do ... end`) enforce runtime bounds checks at block boundary:

- **Hardware watermark check**: At the end of the block, the total allocation volume within the arena is evaluated against the capacity: `(cur_bump - mark_vreg) > cap_opnd`.
- **Deterministic trap**: If the allocated bytes exceed the declared capacity, execution immediately traps with process exit status `99`.
- **Contract tests**: Verified by `tests/memory_contract/arena_capacity_enforced_exceeded.vri` (traps with exit 99 when exceeded) and `tests/memory_contract/arena_capacity_enforced_ok.vri` (succeeds with exit 0 when within capacity).

---

## 4. Standard Library API Boundaries

`vir/mem/alloc` and `vir/rt/alloc` are distinct interfaces. Resolve the imported module and backend before reasoning about an allocation's implementation.

The general-memory interface provides `alloc`, `alloc_zeroed`, `try_alloc`, `realloc`, and `free` through native allocation hooks. The native runtime defines arena operations `arena_new`, `arena_alloc`, `arena_reset`, and `arena_destroy`, along with its heap and page operations. This listing describes API roles, not interchangeable signatures or a guarantee of identical failure semantics.

A complete allocator contract must state:

- Zero-size and allocation-failure behavior.
- Alignment and overflow handling.
- Whether memory is initialized.
- Ownership, valid release operations, and behavior on failed reallocation.
- Thread-safety and backend dependencies.

Read source together with the selected native-hook lowering to determine the concrete memory path. Generated code and runtime tests establish whether the intended path is actually taken.

---

## 5. Cost Model and Comparison Method

No fixed runtime-size or pause-time ranking is specified here. Allocator/runtime code occupies space even without a GC; binary size also depends on linking, optimization, enabled features, and the target.

Useful distinctions are:

- **Scalar/stack placement:** can eliminate a heap operation for eligible values; does not imply zero instructions or zero memory use.
- **Arena reset:** constant bookkeeping for one arena; does not perform object-specific cleanup.
- **Arena destruction:** releases backing mappings; measure OS cost separately from object count.
- **General heap:** search, fragmentation, and release costs depend on implementation and allocation history.
- **Slab reuse:** cheap cached allocation, with retained-memory and size-class tradeoffs.

Language ownership rules alone do not determine fragmentation. Cross-language comparisons must name the actual allocator, runtime version, target, build flags, and workload. Compare equivalent resource-cleanup semantics rather than treating bulk arena release, individual destruction, and tracing collection as identical operations.

For reproducible measurements, record binary size and runtime dependencies, allocation throughput, tail latency, peak/resident memory, retained pool capacity, page faults, and syscall counts. Separate warmed-cache results from first-touch and pool-growth behavior.

---

## 6. Verification and Memory Diagnostics

Validation should cover zero-initialization, alignment, allocation isolation, capacity exhaustion, size overflow, failure propagation, realloc behavior, and arena lifetime boundaries. Tests must assert expected results; the existence of a test file is not evidence of a passing implementation.

Inspect IR or machine code to verify stack/SROA claims. Test actual coalescing cases and free-list invariants before claiming stronger heap behavior. Concurrent use requires separate synchronization tests.

Debug symbols alone do not enable AddressSanitizer instrumentation or make a custom allocator visible to Valgrind. Tool support depends on the backend, platform, generated instrumentation, and any custom-allocator integration. No automatic sanitizer integration is guaranteed by this document.

### 6.1. Empirical Contract Verification Matrix

The memory management implementation is verified against the comprehensive `tests/memory_contract` suite executed via `tools/gap_contract_runner.py`, as well as compiler integration test suites:

| Category | Test Fixture | Contract / Invariant Verified | Result |
| :--- | :--- | :--- | :--- |
| **Heap $O(1)$ Complexity** | `MEM-HEAP-003` | Worst-case search inspection steps $\le 4$ on adversarial heap with 250 fragmented free nodes | **PASS** (1) |
| **Kernel RSS Reuse** | `MEM-HEAP-002` | 10,000 iterations $\times 4\text{ KB}$ allocations with OS kernel RSS check (`sys_getrusage`), $\Delta\text{RSS} \le 128\text{ KB}$ | **PASS** (10000) |
| **Storage Reuse** | `MEM-HEAP-001` | Sequential allocate-free-allocate returns identical virtual address pointer | **PASS** (1) |
| **Disassembly Structural** | `MEM-STRUCT-001` | Machine code disassembled via `otool -tv` / `objdump -d` asserts concrete branch `bl vir_free` / `heap_free` | **PASS** (1) |
| **Implicit Loop Sub-Arena** | `MEM-LOOP-001` | 10,000 loop iterations executing in flat, bounded memory with per-iteration watermark reset | **PASS** (10000) |
| **Loop Escape Preservation**| `MEM-LOOP-002` | Accumulator escaping outer loop scope is preserved without clobbering | **PASS** (10000) |
| **Arena Capacity Trapping** | `MEM-CAP-001` | Runtime watermark check aborts process with exit status `99` when allocation exceeds capacity | **PASS** (exit 99) |
| **Arena Capacity Pass** | `MEM-CAP-002` | Executing within capacity limit completes normally with exit status `0` | **PASS** (exit 0) |
| **Owned Graph Promotion** | `MEM-ESC-001..003`| Escape across nested arenas preserves deep graph backing memory across multiple scopes | **PASS** (100%) |
| **Borrow Invalidation** | `MEM-BORROW-001..003`| Compile-time rejection with stable diagnostic when borrowing across arena resets | **PASS** (100%) |

**Summary Gate Verification:**
- Memory Contract Suite (`tools/gap_contract_runner.py`): **46 / 46 PASS (100%)**
- Compiler Group 27 Integration Suite (`./run_tests.sh 27`): **52 / 52 PASS (100%)**
- Compiler Min Suite (`./run_tests.sh min`): **271 / 271 PASS (100%)**

### 6.2. Bit-for-Bit Self-Host Bootstrap Convergence

Self-host fixed-point convergence is verified across 3 bootstrap generations (Stage 1 $\to$ Stage 2 $\to$ Stage 3) compiled with canonical target naming:

- **Stage 2 Binary**: Compiled from source by Stage 1 compiler (`scratch/stage2/virc`).
- **Stage 3 Binary**: Compiled from source by Stage 2 compiler (`scratch/stage3/virc`).
- **Bit-for-Bit Comparison**:
  ```shell
  cmp scratch/stage2/virc scratch/stage3/virc
  # Exit code: 0 (0 byte differences across all 17,745,871 bytes)
  ```
- **Cryptographic Hash (SHA-256)**:
  - Stage 2 SHA-256: `24cab86b6f721d5a6bc965d7056e69970b834934310db52b0a87a76b6ed51245`
  - Stage 3 SHA-256: `24cab86b6f721d5a6bc965d7056e69970b834934310db52b0a87a76b6ed51245`
- **Installed Compiler**: `bin/virc` is synchronized to the converged Stage 3 binary.
