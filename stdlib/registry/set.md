---
module: set
title: Set
summary: Hash set — set.*; same hash/eq as map; insert/remove return bool.
source:
  - name: set
    path: vir/collections/set.vri
status: closed
notes: >-
  Design closed with map ownership/hash/invalidation. Impl may stay Map of (T, bool).
  free/isEmpty/withCap public. Algebra/iter planned. Owning-element lifecycle
  gate same as map. Docs only.
---

# Set

Hash set. **Same hash / equality contract** as [`map`](map.md). May continue to
be implemented as `Map of (T, bool)`.

```vir
let s = set.new(hash, eq)
set.insert(s, value)     # true if newly inserted
set.contains(s, value)
```

> Same ownership principle as map: the set owns table entries, not necessarily
> all memory elements point to. No deep-free until destructor contract exists.

## Boundary

| In `set` | Not in `set` |
|---|---|
| Explicit `new(hash, eq)` / `withCap` | Separate hash story from `map` |
| insert/contains/remove + len/isEmpty/clear/free | Stable algebra before planned |
| | Public entry pointers |
| | Deep-free of element resources |

## Operations (closed)

| Op | Contract |
|---|---|
| `insert` | `bool` — `true` if newly added, `false` if already present |
| `contains` | `bool` |
| `remove` | `bool` — `true` if the element existed and was removed |
| `clear` | Empty contents; **keep** capacity |
| `free` | End lifetime; release table; do not use afterward (incl. double-`free`) |

Element move into the set on successful insert follows map key ownership rules.
`get`-style copy of elements is not on the core surface (membership only).

Owning elements: same gate as map — reclaim resources before `clear`/`free`
until destructors exist.

## Hash / equality

Identical to [`map`](map.md) H1–H4 and the invariant
`eq(a,b) ⇒ hash(a)=hash(b)`.

## Invalidation

Identical to map V1–V3: no public entry pointers; planned snapshots/iters;
mutate-after-snapshot OK for snapshots; no live-iterator mutate promise.

## Public surface (closed)

```text
set
├── new(hash, eq)
├── withCap(cap, hash, eq)
│
├── insert      # -> bool
├── contains
├── remove      # -> bool
│
├── len
├── isEmpty
├── clear
└── free
```

### Planned

```text
set.union
set.intersection
set.difference
set.iter
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `set_new` | `set.new(hash, eq)` | **rename** |
| `set_with_cap` | `set.withCap(cap, hash, eq)` | **rename** · public |
| `set_insert` | `set.insert` | **rename** · `bool` |
| `set_contains` | `set.contains` | **rename** |
| `set_remove` | `set.remove` | **rename** · `bool` |
| `set_len` | `set.len` | **rename** |
| `set_is_empty` | `set.isEmpty` | **rename** · public |
| `set_clear` | `set.clear` | **rename** |
| `set_free` | `set.free` | **rename** · public |
| `set_union` / … | — | **planned** |
| `set_to_vec` | — | **planned** / via iter |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `set.new` | `set.new` | `set.new(hash, eq) -> Set` | proposed |
| `set.withCap` | `set.withCap` | `set.withCap(cap, hash, eq) -> Set` | proposed |
| `set.insert` | `set.insert` | `set.insert(s, value) -> bool` | proposed |
| `set.contains` | `set.contains` | `set.contains(s, value) -> bool` | proposed |
| `set.remove` | `set.remove` | `set.remove(s, value) -> bool` | proposed |
| `set.len` | `set.len` | `set.len(s) -> int` | proposed |
| `set.isEmpty` | `set.isEmpty` | `set.isEmpty(s) -> bool` | proposed |
| `set.clear` | `set.clear` | `set.clear(s)` | proposed |
| `set.free` | `set.free` | `set.free(s)` | proposed |

---

<a id="set.new"></a>
## `set.new` / `set.withCap`

```vir
set.new(hash, eq) -> Set
set.withCap(cap, hash, eq) -> Set
```

### Status

`proposed`.

---

<a id="set.insert"></a>
## `set.insert` / `remove` / `contains`

```vir
set.insert(s, value) -> bool
set.remove(s, value) -> bool
set.contains(s, value) -> bool
```

### Status

`proposed`.

---

<a id="set.free"></a>
## `set.clear` / `set.free` / `isEmpty`

Same lifetime rules as [`map.clear`](map.md) / [`map.free`](map.md).

### Status

`proposed`.

---

## Next

[`deque.md`](deque.md) closed — Core Collections wave complete. Specialized
structures deferred (see README).
