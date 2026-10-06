---
id: "STLB-SPC-0002"
type: "SPEC"
domain: "STLB"
title: "Vir Allocator Thread Safety Contract"
status: "ACTIVE"
version: "1.0.0"
language: "en"
spec_class: "CONTRACT"
created: "2026-09-20"
updated: "2026-10-02"
owners:
  - "STLB"
  - "VIRC"
components: []
aliases:
  - "docs/memory/THREAD_SAFETY_CONTRACT.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# STLB-SPC-0002 — Vir Allocator Thread Safety Contract

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
- `VIR-SPC-0005` — overall memory architecture

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/memory/THREAD_SAFETY_CONTRACT.md` and assigned stable ID `STLB-SPC-0002` |
