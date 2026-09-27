---
module: deque
title: Deque
summary: Double-ended queue (ring buffer) — deque.*; last Core Collections module.
source:
  - name: deque
    path: vir/collections/deque.vri
status: closed
notes: >-
  Design closed D1–D7. push move-in; pop move-out None if empty; front/back
  copy-limited. clear keeps cap; free ends lifetime; no deep-free; no public
  slot pointers. get/toVec/iter planned. Docs only.
---

# Deque

Double-ended queue as a **ring buffer**. Last module of the **Core Collections**
design wave (`vec` · `map` · `set` · `deque`).

```vir
let d = deque.new()
deque.pushBack(d, x)
deque.pushFront(d, y)
let a = deque.popFront(d)   # Option(T) · move out
let peek = deque.front(d)   # Option(T) · copy-limited
```

> Same ownership principle as [`map`](map.md) / [`vec`](vec.md): the deque owns
> **slots in its storage**, not necessarily all memory elements point to. No
> deep-free until a destructor contract exists.

**Design closed ≠ implementation certified stable.**

## Boundary

| In `deque` | Not in `deque` |
|---|---|
| Ends: push/pop/peek front & back | Core `get(i)` this wave |
| `new` / `withCap` / `len` / `isEmpty` / `clear` / `free` | Public raw slot pointers |
| Logical order front → back | Stable addresses across grow/push/pop |
| | Deep-free of element resources |
| | Specialized collections (heap, lru, …) |

## Ownership (closed — D5 / D1 / D3)

| Op | Contract |
|---|---|
| `pushFront` / `pushBack` | **Move** element into the deque |
| `popFront` / `popBack` | **Move** element out to caller; empty → **`None`** (no panic) |
| `front` / `back` | Read + **copy**; deque unchanged. Stable only for safely **copyable** `T` |

Do not raw-copy uniquely owned types via `front`/`back` (same Copy gate as
[`map.get`](map.md)).

## `clear` / `free` (closed — D4)

| Op | Contract |
|---|---|
| `clear` | `len = 0`; **keep** capacity |
| `free` | Release storage; end container lifetime |

Do not use after `free` (including a second `free`).

Owning elements: caller must reclaim resources before `clear`/`free` (e.g. pop
all and dispose) until destructors exist — no automatic deep-free.

## Invalidation (closed — D6)

No public raw entry / slot pointers in the stable API.

Grow may relocate the entire buffer. Push/pop / head movement change logical
positions. Addresses are **not** stable.

When `getRef` or a live iterator is designed later, lock borrowing/invalidation
separately.

## Indexing / snapshots (planned — D2 / D7)

Logical order is always **front → back**. If `get(i)` is added later, index `0`
is the front element regardless of physical ring layout.

| Planned | Notes |
|---|---|
| `get(i)` | Not in this core surface |
| `getRef` | Later + invalidation lock |
| `toVec` | Snapshot `Vec` front→back; own storage; **not** deep-copy of pointed-to data |
| `iter` | Later |

Mutating the deque after `toVec` does not change that `Vec`’s structure.

## Public surface (closed)

```text
deque
├── new
├── withCap
│
├── pushFront
├── pushBack
├── popFront
├── popBack
├── front
├── back
│
├── len
├── isEmpty
├── clear
└── free
```

### Planned

```text
deque.get
deque.getRef
deque.toVec
deque.iter
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `deque_new` | `deque.new` | **rename** |
| `deque_with_cap` | `deque.withCap` | **rename** |
| `deque_push_back` | `deque.pushBack` | **rename** |
| `deque_push_front` | `deque.pushFront` | **rename** |
| `deque_pop_back` | `deque.popBack` | **rename** · `None` if empty |
| `deque_pop_front` | `deque.popFront` | **rename** · `None` if empty |
| `deque_front` / `back` | `deque.front` / `back` | **rename** · Copy-limited |
| `deque_len` | `deque.len` | **rename** |
| `deque_is_empty` | `deque.isEmpty` | **rename** |
| `deque_clear` | `deque.clear` | **rename** |
| `deque_free` | `deque.free` | **rename** |
| `deque_get` | `deque.get` | **planned** |
| `deque_to_vec` | `deque.toVec` | **planned** |

Keep old names as compatibility wrappers until migration finishes. Do not open
a second deque implementation solely for the new API.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `deque.new` | `deque.new` | `deque.new() -> Deque` | proposed |
| `deque.withCap` | `deque.withCap` | `deque.withCap(cap: int) -> Deque` | proposed |
| `deque.pushFront` | `deque.pushFront` | `deque.pushFront(d, value)` | proposed |
| `deque.pushBack` | `deque.pushBack` | `deque.pushBack(d, value)` | proposed |
| `deque.popFront` | `deque.popFront` | `deque.popFront(d) -> Option(T)` | proposed |
| `deque.popBack` | `deque.popBack` | `deque.popBack(d) -> Option(T)` | proposed |
| `deque.front` | `deque.front` | `deque.front(d) -> Option(T)` | proposed |
| `deque.back` | `deque.back` | `deque.back(d) -> Option(T)` | proposed |
| `deque.len` | `deque.len` | `deque.len(d) -> int` | proposed |
| `deque.isEmpty` | `deque.isEmpty` | `deque.isEmpty(d) -> bool` | proposed |
| `deque.clear` | `deque.clear` | `deque.clear(d)` | proposed |
| `deque.free` | `deque.free` | `deque.free(d)` | proposed |

---

<a id="deque.new"></a>
## `deque.new` / `deque.withCap`

```vir
deque.new() -> Deque
deque.withCap(cap: int) -> Deque
```

### Status

`proposed`.

---

<a id="deque.pushBack"></a>
## Push / pop / peek

```vir
deque.pushFront(d, value)
deque.pushBack(d, value)
deque.popFront(d) -> Option(T)
deque.popBack(d) -> Option(T)
deque.front(d) -> Option(T)
deque.back(d) -> Option(T)
```

### Status

`proposed`.

---

<a id="deque.free"></a>
## `deque.clear` / `deque.free` / `isEmpty`

Same lifetime pattern as [`vec`](vec.md) / [`map`](map.md).

### Status

`proposed`.

---

## Core Collections wave

| Module | Design |
|---|---|
| [`vec`](vec.md) | closed |
| [`map`](map.md) | closed |
| [`set`](set.md) | closed |
| [`deque`](deque.md) | closed |

No further API expansion in this wave. Next work for collections is
**implementation audit** against these contracts — not more public surface.
Specialized structures → Deferred (see README).
