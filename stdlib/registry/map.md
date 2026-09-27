---
module: map
title: Map
summary: Hash map — map.*; explicit hash/eq; copy-limited get; no public entry pointers.
source:
  - name: map
    path: vir/collections/map.vri
  - name: hashmap
    path: vir/collections/hashmap.vri
    notes: merge / retire as duplicate public role
status: closed
notes: >-
  Design closed for CRUD/ctors/hash/eq/invalidation. get stable only for safely
  copyable V. No deep-free; no map.new() without hash/eq. keys/values/entries/
  getRef/iter planned. Full generic stable blocked on Copy check + owning
  destructor contract. Docs only.
---

# Map

Default **hash map**. No iteration-order guarantee.

```vir
let m = map.new(hash, eq)
map.insert(m, key, value)
let v = map.get(m, key)    # Option(V) copy — only for safely copyable V
```

Do **not** keep a second public module (`hashmap`) with the same role.

Shares hashing / equality with [`set`](set.md).

> **Ownership principle:** The map owns the **entries stored in its table**.
> It does **not** automatically own all memory that keys/values may point to.
> No deep-free promise until Vir has a matching resource-destruction contract.

**Design closed ≠ full generic collection stable.** Remaining gates: Copy
checking for `get`, owning key/value lifecycle / destructors, snapshot/iterator
semantics for owning types — must be **enforced**, not only documented.

## Boundary

| In `map` | Not in `map` |
|---|---|
| Explicit `new(hash, eq)` / `withCap` | Parameterless `map.new()` |
| CRUD + `len` / `isEmpty` / `clear` / `free` | Public raw entry pointers / stable borrows |
| `string` / `int` convenience ctors | Generic default hashing mechanism |
| Unordered hash map | Ordered / btree (later) |
| | Stable `get` for unique-ownership `V` |
| | Deep-free of pointed-to resources |

## Ownership (closed — option A, copy-limited `get`)

| Op | Contract |
|---|---|
| `get` | `Option(V)` — **copy** of value; does **not** transfer ownership out of the map. Stable only when `V` is **safely copyable**. |
| `insert` (new key) | **Move** key and value into the map. Returns `None`. |
| `insert` (existing key) | Keep **old key** in the table; replace value; return `Some(oldValue)`. Caller owns `oldValue`. |
| `remove` | Remove entry; **move out** value via `Option(V)`. |
| `getRef` | **planned** — not public |

### Replace / key parameter

On replace, the incoming key is used for **lookup** and is **not** retained in
the table. The parameter is consumed per normal calling convention; the map
does **not** deep-free underlying resources of a discarded key argument.

If keys own resources needing destructors, full support waits on the language
ownership/destructor contract — do not silently leak or double-free.

### Copy gate

Do **not** allow `get` to raw-copy a uniquely owned value. If the type system
cannot yet enforce Copy, generic `get` remains **limited** — not declared
stable for every `V`.

### `clear` / `free` / owning elements

Without a generic destructor contract, the near-term stable surface only
guarantees full lifecycle for keys/values managed safely by copy/move **without**
separate resource teardown. For owning values, the caller must reclaim resources
before `clear` / `free`. Owning keys need key-return or destructor support
before full support.

## Hash / equality (closed)

| ID | Decision |
|---|---|
| H1 | `map.new(hash, eq)` is the official constructor. No-arg `map.new()` **not** public. |
| H2 | `map.string()` / `map.int()` are **convenience** wrappers — not a new generic default-hashing system. |
| H3 | Hash/eq compatibility is a **required precondition**. Violation = caller logic error — **not** memory UB. |
| H4 | Hash must be stable while the key remains in the map. No cross-process / seed / entry-order promise. |

Mandatory:

```text
eq(a, b)  ⇒  hash(a) = hash(b)
```

Keys in the map must not change fields that participate in hash/equality.
Collisions are valid; implementation uses equality to distinguish keys.

`map.string()` hashes and compares by **string content**, not pointer identity.

## Invalidation (closed)

| ID | Decision |
|---|---|
| V1 | No public raw entry pointer or borrowed ref in the **stable** surface. |
| V2 | `keys` / `values` / `entries` stay in design as **planned** — new snapshot `Vec`. |
| V3 | Mutating the map while walking a **snapshot** is allowed. Snapshot ≠ live view. |

`insert` / `remove` / `clear` / rehash may move slots or free the old table.
Do not retain internal raw pointers across those ops.

Snapshots have their own element storage but do **not** imply deep-copy of
resources inside key/value. Owning-type snapshots need a copy/clone contract
before stable.

Streaming iterators remain **planned**. No commit to iterate-and-mutate on a
live iterator.

## Public surface (closed)

```text
map
├── new(hash, eq)
├── withCap(cap, hash, eq)
├── string          # convenience
├── int             # convenience
│
├── insert          # -> Option(V)
├── get             # -> Option(V) · copy-limited
├── contains
├── remove          # -> Option(V)
│
├── len
├── isEmpty
├── clear
└── free
```

### Planned

```text
map.getRef
map.keys / values / entries
map.iter
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `map_new(hash_fn, eq_fn)` | `map.new(hash, eq)` | **rename** |
| `map_with_cap` | `map.withCap(cap, hash, eq)` | **rename** |
| `string_map_new` | `map.string()` | **rename** |
| — | `map.int()` | **new** convenience |
| `map_insert` | `map.insert` | **rename** · `Option(V)` |
| `map_get` | `map.get` | **rename** · Copy gate |
| `map_contains` | `map.contains` | **rename** |
| `map_remove` | `map.remove` | **rename** |
| `map_len` | `map.len` | **rename** |
| `map_is_empty` | `map.isEmpty` | **rename** · public |
| `map_clear` | `map.clear` | **rename** · keep capacity |
| `map_free` | `map.free` | **rename** · public |
| `map_keys` / `values` / `pairs` | `keys` / `values` / `entries` | **planned** |
| `hm_*` (`hashmap.vri`) | → `map.*` | **merge** · one implementation |

Keep old symbols as compatibility wrappers until call-sites migrate. Do not
maintain two independent public hash-map implementations.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `map.new` | `map.new` | `map.new(hash, eq) -> Map` | proposed |
| `map.withCap` | `map.withCap` | `map.withCap(cap, hash, eq) -> Map` | proposed |
| `map.string` | `map.string` | `map.string() -> Map` | proposed |
| `map.int` | `map.int` | `map.int() -> Map` | proposed |
| `map.insert` | `map.insert` | `map.insert(m, key, value) -> Option(V)` | proposed |
| `map.get` | `map.get` | `map.get(m, key) -> Option(V)` | proposed |
| `map.contains` | `map.contains` | `map.contains(m, key) -> bool` | proposed |
| `map.remove` | `map.remove` | `map.remove(m, key) -> Option(V)` | proposed |
| `map.len` | `map.len` | `map.len(m) -> int` | proposed |
| `map.isEmpty` | `map.isEmpty` | `map.isEmpty(m) -> bool` | proposed |
| `map.clear` | `map.clear` | `map.clear(m)` | proposed |
| `map.free` | `map.free` | `map.free(m)` | proposed |

`clear` retains capacity. `free` ends container lifetime and releases the table
per allocator contract. Do not use after `free` (including a second `free`).
`free` does **not** deep-free resources pointed to by elements.

---

<a id="map.new"></a>
## `map.new` / `map.withCap`

```vir
map.new(hash, eq) -> Map
map.withCap(cap, hash, eq) -> Map
```

### Status

`proposed`.

---

<a id="map.string"></a>
## `map.string` / `map.int`

```vir
map.string() -> Map
map.int() -> Map
```

Wrappers over `map.new` with content hash/eq for `string` / `int` keys.

### Status

`proposed` — `string` present as `string_map_new`; `int` new.

---

<a id="map.insert"></a>
## `map.insert` / `get` / `remove`

```vir
map.insert(m, key, value) -> Option(V)
map.get(m, key) -> Option(V)
map.remove(m, key) -> Option(V)
```

### Status

`proposed`.

---

<a id="map.free"></a>
## `map.clear` / `map.free` / `isEmpty`

```vir
map.clear(m)
map.free(m)
map.isEmpty(m) -> bool
```

### Status

`proposed`.

---

## Implementation readiness

1. Single public `map.*`; fold `hashmap.*`.
2. Enforce Copy gate on `get` when the type system allows.
3. Document + eventually enforce hash/eq invariant (caller logic error).
4. Keep snapshots/iterators planned until owning copy/clone is real.
5. [`set.md`](set.md) / [`deque.md`](deque.md) share ownership style; Core
   Collections wave complete.
