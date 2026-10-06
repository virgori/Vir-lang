---
name: vir-memory-management
description: >-
  Design, write, audit, and verify Vir ownership, moves, borrows, escape
  analysis, lexical lifetimes, explicit and implicit sub-arenas, promotion,
  cleanup, and allocator/backend behavior.
---

# Vir memory, ownership, and arenas

Use after `vir-lang`. Read
[`references/arena-ownership.md`](references/arena-ownership.md) for source-level
work and [`references/verification.md`](references/verification.md) for compiler,
runtime, or backend claims.

## Governing contract

Read `VIR-SPC-0005`, the memory sections of `VIR-SPC-0017` / `0018`, and the
relevant current fixture under `tests/memory_contract/`. For allocator APIs,
inspect the exact imported module and implementation; `vir/mem/alloc` and
`vir/rt/alloc` are not interchangeable.

## Core rules

- Copy values may be copied. Move values transfer ownership and invalidate the
  source binding.
- `&` is a shared borrow; `&mut` is exclusive. A borrow cannot outlive its
  owner or arena and cannot cross a reset.
- An owned graph may escape a child scope by move or `out`. The compiler must
  place/promote the complete reachable graph into the nearest region with a
  sufficient lifetime. Do not shallow-copy only a header.
- A raw pointer does not extend lifetime.
- Reset/release reclaims memory only. Use `ensure`/`revert` or explicit APIs for
  file descriptors, sockets, locks, and other external resources.

## Important correction to the old skill

Do not apply the obsolete blanket rule “a value created in `arena:` can never
escape.” Current contract tests permit owned moves and `out` with graph
promotion. Escape diagnostics apply to invalid borrows/references and unsafe
lifetime paths, not every owned transfer.

## Completion gate

For memory-sensitive changes, test positive and negative ownership paths,
nested arenas, every early exit (`break`, `skip`, `out`, `throw`), cleanup,
optimization levels, and each affected backend. Report unsupported backends
separately instead of generalizing one native result.

