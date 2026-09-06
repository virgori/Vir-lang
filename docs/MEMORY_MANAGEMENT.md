# Vir Memory Management Architecture & Specification

**Language baseline**: v2.1.0
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

A request can allocate a 1 KiB input buffer and a 4 KiB parse workspace from the same arena, check both allocation results, use them, and destroy the arena when the request finishes. This expresses the intended lifetime without promising that the entire operation has constant latency.

### 3.3. Free-list heap

The native runtime implements a first-fit free list for independently released allocations.

The current 16-byte header has a size word and a second word used as free-list linkage when the block is free. It must not be described as a complete boundary-tag layout:

```text
[size: total block bytes][next free pointer when free][payload]
          8 bytes                 8 bytes             starts at +16
```

Allocation searches free blocks and may split a sufficiently large block. First-fit search is O(F) in the number of free-list entries examined, not unconditionally O(1).

**Current coalescing limitation:** `heap_free` merges with the immediately following physical block only when that block equals `g_heap.free_head`; otherwise it pushes the released block onto the list. This is not general bidirectional coalescing.

A bidirectional design needs a way to identify the preceding physical block: for example, boundary tags, `prev_size`, an address-ordered search, or external metadata. The two-word layout above alone does not provide O(1) backward-neighbor lookup. Any proposed metadata must also specify region boundaries and split/merge updates.

Coalescing can reduce external fragmentation; it does not eliminate it. Alignment, minimum block size, and splitting policy also introduce internal fragmentation. Workload measurements are needed to quantify both.

### 3.4. Size-class slab pools

`core/src/slab_alloc.c` contains a C implementation of reusable size-class pools. Its presence does not establish that a particular self-hosted native compiler uses this path.

The configured region classes are 64 KiB, 1 MiB, 8 MiB, and 64 MiB. Headers occupy part of these regions; class size must not be presented as an unconditional usable-payload size. Oversized allocations use a separate mapping path.

Reusing a cached region requires O(1) stack bookkeeping. Pool misses obtain fresh backing memory; oversized frees and frees to a full cache may release mappings.

Reuse can avoid a new mapping syscall and often reuses resident pages. It does **not** guarantee absence of page faults: memory pressure or explicit page reclamation can make future accesses fault again.

The current implementation uses a global singleton with ordinary pool counters and free-stack accesses. Do not describe it as a lock-free thread-local allocator or promise safe concurrent use without a defined synchronization or ownership policy.

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
