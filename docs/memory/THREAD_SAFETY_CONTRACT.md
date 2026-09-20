# Vir Allocator Thread Safety Contract

## Status: Single-Threaded (Phase 2)

The Vir native allocator (`stdlib/vir/rt/alloc.vri`) is deliberately single-threaded as of Phase 2.

### Arena Allocator (bump/X28/s11)
- **Thread safe per thread**: the arena bump pointer (ARM64: X28, RISC-V: s11, Wasm: global 0) is a per-function register/global. If each thread uses its own stack frame and arena block, no sharing occurs.
- Arena `mark`/`reset`/`drop` operate on thread-local registers — safe without locking when used correctly.

### TLSF Heap (`heap_alloc`/`heap_free`)
- **NOT thread safe**: `g_tlsf_ctrl` is a shared global with no atomics or locks.
- Concurrent `heap_alloc`/`heap_free` from multiple threads causes undefined behavior.

### Recommended Patterns

| Use case | Safe approach |
|---|---|
| Single-threaded program | Use freely — no restrictions |
| Multi-threaded, arena only | Each thread uses its own `arena:` block — safe |
| Multi-threaded, heap | Wrap `heap_alloc`/`heap_free` with platform mutex |
| Actor model (`port`/`worker`) | Each worker has its own arena; heap sharing is guarded by message-passing |

### Future: Phase 3
- Lock-free TLSF using CAS on bin heads
- Per-thread slab cache with thread-local freelist
- Lock elision via per-thread segment ownership

## See Also
- `stdlib/vir/rt/alloc.vri` — `HEAP_THREAD_SAFE` constant and heap implementation
- `docs/MEMORY_MANAGEMENT.md` — overall memory architecture
