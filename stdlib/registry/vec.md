---
module: vec
title: Vec
summary: Owned growable typed collection Vec of (T) — constructors plus UFCS.
source:
  - name: collections.vec
    path: vir/collections/vec.vri
status: draft
notes: >-
  Canonical surface uses Vec constructors and receiver-style UFCS. The current
  implementation remains available through vec_* compatibility symbols while
  generic UFCS is completed in the compiler.
---

# Vec

Owned, growable **typed** collection `Vec of (T)`. Constructors live on `Vec`;
all operations use the receiver form `self.<op>`.

```text
string  → UTF-8 text
Buffer  → owned growable binary          (byte)
Slice   → borrowed binary view
Vec of (T)  → owned growable typed collection (element T)
```

```vir
let v = Vec.alloc of (int)(32)
v.push(1)
let x = v.get(0)
v.free()
```

Callables today remain `vec_*` compatibility functions. They map 1:1 to this
surface while compiler support for generic receiver dispatch is completed.
Safe lookup is the flat UFCS operation `self.try`. Removal exposes two explicit
methods: `self.remove(i)` preserves order, while
`self.swapRemove(i)` performs O(1) unordered removal. Neither default arguments,
overloading, nor typed operation selectors are part of this Vec contract.

## Boundary

| In `vec` | Not in `vec` |
|---|---|
| Typed element storage / grow by **element** | Byte builder → [`buffer`](buffer.md) |
| Panic `get` / Option `try` | Borrowed binary view → [`slice`](slice.md) |
| Owned range `copy` | Soft-bootstrap `compiler/vec_prelude` |
| Explicit `free` | Runtime `rt/vec_rt` (`*_rt`) |
| | Raw `as_ptr` / `from_slice(ptr)` — **internal** |
| | Higher-order `map`/`filter`/… — **uncurated** |
| | Compatibility `vec_*` symbols — **not canonical** |

`Vec of (u8)` is **not** `Buffer`. Even after element-width correctness lands,
`Vec of (u8)` remains a typed collection of `u8`; `Buffer` remains the binary
builder/storage abstraction.

## Generic reality (closed)

**Contract:**

```text
Vec of (T)
stride / grow unit = size_of(T)
```

**Implementation** (`vir/collections/vec.vri`): public Vec paths use
`size_of(T)` for allocation, offsets, and `mem_copy` / `mem_move`. Element
load/store uses `native_load` / `native_store`. Fixed `* 8` / `native_read_i64`
slot assumptions removed from the core surface.

| Layer | Meaning |
|---|---|
| Contract | `Vec of (T)`, stride = `size_of(T)` |
| Implementation | element-width addressing on core ops |
| Still out | compiler support for generic UFCS |

### Zero-sized types (closed)

If `size_of(T) == 0`, `Vec of (T)` is **currently unsupported** unless the
compiler/source later proves a defined representation. Do not assume pointer /
stride math works for ZST with today’s layout.

### Growth overflow (closed)

Capacity growth and sizing must guard integer overflow on at least:

```text
cap * 2
cap * size_of(T)
len + additional
```

Overflow must not produce an undersized allocation (memory corruption). Exact
failure mode (panic / abort / `Result`) follows runtime alloc policy — not silent
wrap.

## Contracts (closed)

### Mutation invalidation

Like [`buffer`](buffer.md): any operation that may **reallocate** invalidates
raw pointers and any view into the old storage.

May reallocate (non-exhaustive): `push`, `insert`, `extend`, `reserve`,
`compact`, and other paths that grow or relocate the backing store.

In-place ops that do not move storage (`set`, `swap`, `clear`, `truncate` that
only shrinks `len`, order-preserving `remove` shift within the same allocation)
keep the allocation address; content/length semantics still apply.

### `reserve(additional)`

```text
postcondition: capacity >= len + additional
```

`additional` is **extra element slots beyond current `len`**. It is **not** a
target absolute capacity and **not** a byte count. Implementations must not
reinterpret `reserve(n)` as “set capacity to `n`”.

### Removal operations

| Call form | Order | Complexity (relative) |
|---|---|---|
| `remove(i)` | **preserves** order of remaining elements | shifts the tail — O(n) |
| `swapRemove(i)` | **does not** preserve order | no full-tail shift — O(1) |

These are separate methods with separate callable identities. They do not
require function overloading, default arguments, or selector resolution.

### `extend` self-extension

```vir
v.extend(v)
```

**Supported.** Implementation must snapshot source length (and read from a
stable source view of the pre-extend prefix) before any reallocation that
appends; must not invoke UB if `other` aliases `v`. If an impl cannot support
this temporarily, it must **panic explicitly** — never corrupt.

### `clone` depth

```text
clone = deep w.r.t. Vec storage
       shallow w.r.t. T
```

Allocates new backing storage and copies each `T` by value (bitwise /
assignment copy as the language defines for `T`). Does **not** recursively
deep-clone resources that `T` points to.

## Decisions V1–V3 (locked)

| ID | Decision |
|---|---|
| V1 | Element Drop is a **language/implementation gate**. Missing destructor is **not** standardized “correct” behavior. |
| V2 | Canonical docs use `Vec.*` constructors plus receiver UFCS; source `vec_*` is a **compatibility layer**. |
| V3 | Lock move/copy; **no** public borrowed-element references until borrow contracts are enforced. |

### Ownership (locked)

Aligned with other locked collections:

| Op | Ownership |
|---|---|
| `push` / `insert` / `extend` | **Move** element(s) **into** the `Vec` |
| `pop` / `remove` / `swapRemove` | **Move** element **out** to the caller |
| `get` / `try` / `first` / `last` | **Copy** only when `T` is safely copyable |
| `clear` / `truncate` | End lifetime of removed elements |

Because Element Drop is incomplete (V1): ops that discard elements **without**
returning them are **not `stable`** for resource-owning `T` that need
destructors. Callers may move elements out before reclaiming storage — a
**temporary** limit, not a long-term contract.

Keep: **ZST unsupported**; **`Vec of (u8)` ≠ `Buffer`**.

### `clear` / `truncate` and element ownership

Today Vir has **no** general destructor / Drop semantics for arbitrary `T`.

| Op | Storage | Elements leaving the logical array |
|---|---|---|
| `clear` | `len = 0`; capacity retained | lifetimes end; destructors **not** run today (V1) |
| `truncate` | shrink `len` when `newLen < len` | same |

Do **not** document missing Drop as desired permanent semantics.

### Ownership / free

```vir
v.free()
```

| Op | Effect |
|---|---|
| `clear` | `len = 0`; capacity retained; no element destructors (today) |
| `truncate(newLen)` | if `newLen < len` → shrink `len`; if `newLen ≥ len` → **no-op** |
| `reserve(additional)` | `capacity >= len + additional` |
| `compact` | capacity → `len` (or free if empty); may relocate |
| `free` | release storage; do not use afterward |

Growth strategy today: double capacity (minimum 8 slots when growing from
`reserve`), subject to overflow guards above.

## CORE SPEC surface note

CORE SPEC minimal list is a **subset**. Extra ops already locked here
(`create`, `first`/`last`, `swapRemove`, `extend`, `clone`, `copy`, …)
remain part of this module’s closed surface. HOF stay **uncurated** / out of
this core wave. Ops not listed in either surface stay **out** unless marked
`planned` with a full entry.

## Public surface (closed)


```text
Vec
├── new
├── alloc
└── create

self
├── len
├── cap
├── isEmpty
│
├── get
├── try
├── set
├── first
├── last
│
├── push
├── pop
├── insert
├── remove
├── swapRemove
├── extend
│
├── contains
├── find
├── count
│
├── reverse
├── swap
├── clone
├── copy
├── equal
│
├── reserve
├── compact
├── truncate
├── clear
└── free
```

### Uncurated (not canonical)

Present in source; **not** part of this closed surface until callable/function
ABI is locked:

```text
forEach  map  filter  any  all  fold
zip  enumerate  flatten  dedup
Pair of (A,B)   # local helper for zip/enumerate
```

Status if mentioned elsewhere: `experimental` / uncurated — not teachable as
stable stdlib.

### Internal / raw

```text
vec_as_ptr
vec_as_slice              # byte Slice of representation — not public vec.bytes
vec_from_slice(ptr,count)
vec_extend_from_slice(ptr,count)
grow / realloc helpers inside reserve
```

## Public rename map

| Previous | Canonical |
|---|---|
| `vec.new` | `Vec.new` |
| `vec.withCap` | `Vec.alloc` |
| `vec.filled` | `Vec.create` |
| `vec.tryGet` | `self.try` |
| `vec.swapRemove` | `self.swapRemove` |
| `vec.copyRange` | `self.copy` |
| `vec.eq` | `self.equal` |
| `vec.shrinkToFit` | `self.compact` |

All other public leaf names are unchanged and move from `vec.<op>(self, …)`
to receiver form `self.<op>(…)`.

## Implementation compatibility map

| Current symbol | Canonical API | Impl note | Action |
|---|---|---|---|
| `vec_new` | `Vec.new` | empty, no alloc | **rename** |
| `vec_alloc` (`vec_with_cap` compat) | `Vec.alloc` | preallocated capacity | **mapped** |
| `vec_create` (`vec_filled` compat) | `Vec.create` | `n` copies of value | **mapped** |
| `vec_from_slice` | — | raw ptr | **internal** |
| `vec_len` | `self.len` | | **rename** |
| `vec_cap` | `self.cap` | | **rename** |
| `vec_is_empty` | `self.isEmpty` | | **rename** |
| `vec_get` | `self.get` | panic OOB | **rename** |
| `vec_try` (`vec_try_get` compat) | `self.try` | `Option` | **mapped** |
| `vec_set` | `self.set` | panic OOB | **rename** |
| `vec_first` | `self.first` | `Option` | **rename** |
| `vec_last` | `self.last` | `Option` | **rename** |
| `vec_push` | `self.push` | | **rename** |
| `vec_pop` | `self.pop` | `Option` | **rename** |
| `vec_insert` | `self.insert` | panic if `idx > len` | **rename** |
| `vec_remove` | `self.remove` | order-preserving; returns `T` | **mapped** |
| `vec_swap_remove` | `self.swapRemove` | unordered O(1) removal | **mapped** |
| `vec_extend` | `self.extend` | self-extend **supported** | **rename** + harden |
| `vec_extend_from_slice` | — | raw ptr | **internal** |
| `vec_contains` | `self.contains` | needs `T` `==` | **rename** |
| `vec_find` | `self.find` | `Option` of **index** | **rename** |
| `vec_count` | `self.count` | needs `T` `==` | **rename** |
| `vec_reverse` | `self.reverse` | in-place | **rename** |
| `vec_swap` | `self.swap` | exchange indices `a`,`b` | **present** |
| `vec_clone` | `self.clone` | deep storage / shallow `T` | **rename** |
| `vec_copy` (`vec_copy_range` / `vec_slice` compat) | `self.copy` | owned copy of `[from,to)` | **mapped** |
| `vec_equal` (`vec_eq` compat) | `self.equal` | content equality | **mapped** |
| `vec_reserve` | `self.reserve` | `cap >= len + additional` | **rename** |
| `vec_compact` (`vec_shrink_to_fit` compat) | `self.compact` | | **mapped** |
| `vec_truncate` | `self.truncate` | shrink-only | **rename** |
| `vec_clear` | `self.clear` | | **rename** |
| `vec_free` | `self.free` | explicit release | **rename** |
| `vec_as_ptr` / `vec_as_slice` | — | raw / byte view | **internal** |
| `vec_for_each` … `vec_dedup` | — | callback/`ptr` | **uncurated** |

## Equality / search constraint

`contains`, `find`, `count`, and `equal` use element `==` / `!=` as written in
source. Vir does **not** yet express this as a formal trait bound in the
registry — document as:

> Requires `T` to support the equality operators used by the implementation
> (`==` / `!=`). No invented trait constraint beyond what the compiler applies.

`find` returns **`Option` of index** (`Some(i)` / `None`), not the element value.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `vec.new` | `Vec.new` | `Vec.new() -> Vec of (T)` | proposed |
| `vec.withCap` | `Vec.alloc` | `Vec.alloc(cap: int) -> Vec of (T)` | proposed |
| `vec.filled` | `Vec.create` | `Vec.create(value: T, n: int) -> Vec of (T)` | proposed |
| `vec.len` | `self.len` | `self.len() -> int` | proposed |
| `vec.cap` | `self.cap` | `self.cap() -> int` | proposed |
| `vec.isEmpty` | `self.isEmpty` | `self.isEmpty() -> bool` | proposed |
| `vec.get` | `self.get` | `self.get(i: int) -> T` | proposed |
| `vec.tryGet` | `self.try` | `self.try(i: int) -> Option of (T)` | proposed |
| `vec.set` | `self.set` | `self.set(i: int, x: T) -> void` | proposed |
| `vec.first` | `self.first` | `self.first() -> Option of (T)` | proposed |
| `vec.last` | `self.last` | `self.last() -> Option of (T)` | proposed |
| `vec.push` | `self.push` | `self.push(x: T) -> …` | proposed |
| `vec.pop` | `self.pop` | `self.pop() -> Option of (T)` | proposed |
| `vec.insert` | `self.insert` | `self.insert(i: int, x: T) -> void` | proposed |
| `vec.remove` | `self.remove` | `self.remove(i: int) -> T` | proposed |
| `vec.swapRemove` | `self.swapRemove` | `self.swapRemove(i: int) -> T` | proposed |
| `vec.extend` | `self.extend` | `self.extend(other: Vec of (T)) -> void` | proposed |
| `vec.contains` | `self.contains` | `self.contains(x: T) -> bool` | proposed |
| `vec.find` | `self.find` | `self.find(x: T) -> Option of (int)` · index | proposed |
| `vec.count` | `self.count` | `self.count(x: T) -> int` | proposed |
| `vec.reverse` | `self.reverse` | `self.reverse() -> void` | proposed |
| `vec.swap` | `self.swap` | `self.swap(a: int, b: int) -> void` | proposed |
| `vec.clone` | `self.clone` | `self.clone() -> Vec of (T)` | proposed |
| `vec.copyRange` | `self.copy` | `self.copy(from: int, to: int) -> Vec of (T)` | proposed |
| `vec.eq` | `self.equal` | `self.equal(other: Vec of (T)) -> bool` | proposed |
| `vec.reserve` | `self.reserve` | `self.reserve(additional: int) -> void` | proposed |
| `vec.shrinkToFit` | `self.compact` | `self.compact() -> void` | proposed |
| `vec.truncate` | `self.truncate` | `self.truncate(newLen: int) -> void` | proposed |
| `vec.clear` | `self.clear` | `self.clear() -> void` | proposed |
| `vec.free` | `self.free` | `self.free() -> void` | proposed |

---

<a id="vec.new"></a>
## `Vec.new`

<!--
id: vec.new
api: Vec.new
previous: vec_new
-->

```vir
Vec.new() -> Vec of (T)
```

Empty vector; no allocation (`data = null`, `cap = 0` today).

### Parameters

None (type argument `T`).

### Returns

`Vec of (T)`

### Errors

None.

### Semantics

No public `vec.empty()` constructor — `new` is the empty constructor;
`isEmpty` is the predicate.

### Example

```vir
let v = Vec.new of (int)()
```

### Status

`proposed` — **present** as `vec_new`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_new`.

### See also

- `Vec.alloc`
- `Vec.create`

---

<a id="vec.withCap"></a>
## `Vec.alloc`

<!--
id: vec.withCap
api: Vec.alloc
previous: vec_with_cap
-->

```vir
Vec.alloc(cap: int) -> Vec of (T)
```

Empty vector with preallocated capacity for `cap` **elements**.

### Parameters

#### `cap: int`

Element slots to allocate (`len = 0`).

### Returns

`Vec of (T)`

### Errors

Alloc failure per runtime.

### Example

```vir
let v = Vec.alloc(32)
```

### Status

`proposed` — **present** as `vec_alloc`; `vec_with_cap` is compatibility-only.

### Implementation mapping

`vir/collections/vec.vri` → `vec_alloc`.

### See also

- `Vec.new`
- `self.reserve`

---

<a id="vec.filled"></a>
## `Vec.create`

<!--
id: vec.filled
api: Vec.create
previous: vec_filled
-->

```vir
Vec.create(value: T, n: int) -> Vec of (T)
```

Vector of `n` elements, each equal to `value`.

### Parameters

#### `value: T`

Element to repeat.

#### `n: int`

Element count.

### Returns

`Vec of (T)` with `len = n`.

### Errors

Alloc failure per runtime.

### Example

```vir
let v = Vec.create of (int)(0, 10)
```

### Status

`proposed` — **present** as `vec_create`; `vec_filled` is compatibility-only.

### Implementation mapping

`vir/collections/vec.vri` → `vec_create`.

### See also

- `Vec.alloc`

---

<a id="vec.len"></a>
## `self.len`

<!--
id: vec.len
api: self.len
previous: vec_len
-->

```vir
self.len() -> int
```

Number of elements (`len`), not capacity and not bytes.

### Example

```vir
let n = v.len()
```

### Status

`proposed`

### Implementation mapping

`vec_len`

### See also

- `self.cap`
- `self.isEmpty`

---

<a id="vec.cap"></a>
## `self.cap`

<!--
id: vec.cap
api: self.cap
previous: vec_cap
-->

```vir
self.cap() -> int
```

Allocated capacity in **elements**.

### Status

`proposed`

### Implementation mapping

`vec_cap`

### See also

- `self.len`
- `self.reserve`

---

<a id="vec.isEmpty"></a>
## `self.isEmpty`

<!--
id: vec.isEmpty
api: self.isEmpty
previous: vec_is_empty
-->

```vir
self.isEmpty() -> bool
```

`true` when `len == 0`.

### Status

`proposed`

### Implementation mapping

`vec_is_empty`

### See also

- `self.len`
- `Vec.new`

---

<a id="vec.get"></a>
## `self.get`

<!--
id: vec.get
api: self.get
previous: vec_get
-->

```vir
self.get(i: int) -> T
```

Element at index `i`. Panic on OOB. Hot-path primitive (like `slice.get`).

### Errors

`i >= len` → panic.

### Example

```vir
let x = v.get(0)
```

### Status

`proposed`

### Implementation mapping

`vec_get` — also subject to current 8-byte slot paths until fixed.

### See also

- `self.try`
- `self.set`

---

<a id="vec.tryGet"></a>
## `self.try`

<!--
id: vec.tryGet
api: self.try
previous: vec_try_get
-->

```vir
self.try(i: int) -> Option of (T)
```

Element at `i`, or `None` if out of bounds. Does not panic.

### Returns

`Option` of `T` — `Some(element)` / `None`.

### Status

`proposed`

### Implementation mapping

`vec_try` (`vec_try_get` compatibility alias)

### See also

- `self.get`
- `self.first`

---

<a id="vec.set"></a>
## `self.set`

<!--
id: vec.set
api: self.set
previous: vec_set
-->

```vir
self.set(i: int, x: T) -> void
```

Replace element at `i`. Panic on OOB. Does not extend length.

**Ownership (V3):** the new value `x` is **moved in**. The previous element at
`i` is **moved out of the logical slot** and its lifetime ends. Because Element
Drop is incomplete (V1), discarding that previous owning value without a
returned handle is **not `stable`** for resource-owning `T` — same gate as
`clear` / `truncate`. Do not silently leak as a long-term contract.

### Errors

`i >= len` → panic.

### Status

`proposed`

### Implementation mapping

`vec_set`

### See also

- `self.get`
- `self.push`

---

<a id="vec.first"></a>
## `self.first`

<!--
id: vec.first
api: self.first
previous: vec_first
-->

```vir
self.first() -> Option of (T)
```

First element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_first`

### See also

- `self.last`
- `self.try`

---

<a id="vec.last"></a>
## `self.last`

<!--
id: vec.last
api: self.last
previous: vec_last
-->

```vir
self.last() -> Option of (T)
```

Last element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_last`

### See also

- `self.first`
- `self.pop`

---

<a id="vec.push"></a>
## `self.push`

<!--
id: vec.push
api: self.push
previous: vec_push
-->

```vir
self.push(x: T) -> …
```

Append `x`, growing if needed. Today’s source returns the vector value; public
callers treat it as a mutating append (exact return shape may align to `void`
or `Vec` during implement — behavior is append-one-element).

### Semantics

May reallocate → invalidates prior raw pointers / views into old storage.
Growth is in **elements**.

### Status

`proposed`

### Implementation mapping

`vec_push`

### See also

- `self.pop`
- `self.extend`

---

<a id="vec.pop"></a>
## `self.pop`

<!--
id: vec.pop
api: self.pop
previous: vec_pop
-->

```vir
self.pop() -> Option of (T)
```

Remove and return the last element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_pop`

### See also

- `self.push`
- `self.last`

---

<a id="vec.insert"></a>
## `self.insert`

<!--
id: vec.insert
api: self.insert
previous: vec_insert
-->

```vir
self.insert(i: int, x: T) -> void
```

Insert `x` at `i`, shifting the tail right. Allows `i == len` (append-at-end).

### Errors

`i > len` → panic.

### Semantics

Uses `mem_move` for the shift today.

### Status

`proposed`

### Implementation mapping

`vec_insert`

### See also

- `self.remove`
- `self.push`

---

<a id="vec.remove"></a>
## `self.remove`

<!--
id: vec.remove
api: self.remove
previous: vec_remove
-->

```vir
self.remove(i: int) -> T
```

Removes and returns the element at `i`, shifts the tail left, and preserves the
relative order of the remaining elements. Relative complexity is **O(n)**.

### Errors

`i >= len` → panic.

### Semantics

Does not run element destructors on the removed value beyond returning it to
the caller (see element-ownership limitation). Same allocation unless a future
impl shrinks (today: no shrink).

### Status

`proposed` — implementation present; generic receiver UFCS remains compiler-gated.

### Implementation mapping

`vec_remove`

### See also

- `self.swapRemove`
- `self.swap`

---

<a id="vec.swapRemove"></a>
## `self.swapRemove`

<!--
id: vec.swapRemove
api: self.swapRemove
previous: vec_swap_remove
-->

```vir
self.swapRemove(i: int) -> T
```

Removes and returns the element at `i` in **O(1)** by replacing the removed slot
with the last element, then shrinking `len`. **Order is not preserved.**

### Errors

`i >= len` → panic.

### Status

`proposed` — implementation present; generic receiver UFCS remains compiler-gated.

### Implementation mapping

`vec_swap_remove`

### See also

- `self.remove`
- `self.swap`

---

<a id="vec.extend"></a>
## `self.extend`

<!--
id: vec.extend
api: self.extend
previous: vec_extend
-->

```vir
self.extend(other: Vec of (T)) -> void
```

Append all elements of `other` onto `v`.

### Semantics

Public bulk append from another `Vec`. Raw `extend_from_slice(ptr,…)` is
**internal**.

**Self-extension** `v.extend(v)` is **supported**: snapshot the source
length / prefix before reallocating to append; must not UB. May reallocate →
invalidates prior raw views into `v`.

### Status

`proposed` — self-alias snapshot before reserve (implemented).

### Implementation mapping

`vec_extend`


### See also

- `self.push`
- `self.clone`

---

<a id="vec.contains"></a>
## `self.contains`

<!--
id: vec.contains
api: self.contains
previous: vec_contains
-->

```vir
self.contains(x: T) -> bool
```

Whether any element equals `x` (`==`).

### Semantics

Requires `T` equality as used by the implementation — no invented trait bound.

### Status

`proposed`

### Implementation mapping

`vec_contains`

### See also

- `self.find`
- `self.count`

---

<a id="vec.find"></a>
## `self.find`

<!--
id: vec.find
api: self.find
previous: vec_find
-->

```vir
self.find(x: T) -> Option of (int)
```

First **index** where the element equals `x`, or `None`.

### Returns

`Option` of `int` — **index**, not the element value.

### Semantics

Requires `T` equality as used by the implementation.

### Example

```vir
let i = v.find(x)
# Some(index) or None
```

### Status

`proposed`

### Implementation mapping

`vec_find`

### See also

- `self.contains`
- `self.get`

---

<a id="vec.count"></a>
## `self.count`

<!--
id: vec.count
api: self.count
previous: vec_count
-->

```vir
self.count(x: T) -> int
```

Number of elements equal to `x`.

### Status

`proposed`

### Implementation mapping

`vec_count`

### See also

- `self.contains`

---

<a id="vec.reverse"></a>
## `self.reverse`

<!--
id: vec.reverse
api: self.reverse
previous: vec_reverse
-->

```vir
self.reverse() -> void
```

Reverse elements in place.

### Status

`proposed`

### Implementation mapping

`vec_reverse`

### See also

- `self.clone`

---

<a id="vec.swap"></a>
## `self.swap`

<!--
id: vec.swap
api: self.swap
-->

```vir
self.swap(a: int, b: int) -> void
```

Exchange elements at indices `a` and `b` in place.

### Parameters

#### `a: int` / `b: int`

Indices in `[0, len)`.

### Returns

None.

### Errors

Either index OOB → panic (target).

### Semantics

Does not reallocate. Useful for sort / shuffle / heap without a three-step
`get`/`set` dance. `a == b` is a no-op.

### Example

```vir
v.swap(i, j)
```

### Status

`proposed` — **present** as `vec_swap`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_swap`.

### See also

- `self.remove`
- `self.reverse`

---

<a id="vec.clone"></a>
## `self.clone`

<!--
id: vec.clone
api: self.clone
previous: vec_clone
-->

```vir
self.clone() -> Vec of (T)
```

Full-vector copy into new storage.

### Semantics

**Deep** with respect to `Vec` backing storage; **shallow** with respect to
`T` — each element is copied by value; pointed-to resources are not
deep-cloned. Distinct from `copy` (partial).

### Status

`proposed`

### Implementation mapping

`vec_clone`

### See also

- `self.copy`
- `self.equal`

---

<a id="vec.copyRange"></a>
## `self.copy`

<!--
id: vec.copyRange
api: self.copy
previous: vec_slice
-->

```vir
self.copy(from: int, to: int) -> Vec of (T)
```

New **owned** `Vec of (T)` containing a copy of the half-open range `[from, to)`.

### Parameters

#### `from: int` / `to: int`

Element indices; half-open.

### Returns

`Vec of (T)` — independent allocation.

### Errors

`from > to` or `to > len` → panic today.

### Semantics

**Not** a borrowed view — do not name this `vec.slice`. **Not** a full-vector
clone — that is `self.clone`. The range parameters keep `copy` distinct from
copying the whole collection.

Element copies are shallow w.r.t. `T` (same as `clone`).

### Example

```vir
let whole = v.clone()
let part = v.copy(2, 5)
# owned Vec of former elements [2,5)
```

### Status

`proposed` — **present** as `vec_copy`; `vec_copy_range` and `vec_slice` are
compatibility aliases.

### Implementation mapping

`vir/collections/vec.vri` → `vec_copy`.

### See also

- `self.clone`
- `slice.sub` *(borrowed binary — different type)*

---

<a id="vec.eq"></a>
## `self.equal`

<!--
id: vec.eq
api: self.equal
previous: vec_eq
-->

```vir
self.equal(other: Vec of (T)) -> bool
```

Content equality: same length and pairwise `==` elements.

### Semantics

Kept public (same rationale as `slice.eq`). Future language `==` on `Vec`
may lower to this. Requires element equality as used by the implementation.

### Status

`proposed`

### Implementation mapping

`vec_equal` (`vec_eq` compatibility alias)

### See also

- `self.clone`

---

<a id="vec.reserve"></a>
## `self.reserve`

<!--
id: vec.reserve
api: self.reserve
previous: vec_reserve
-->

```vir
self.reserve(additional: int) -> void
```

Ensure capacity for at least `len + additional` **elements**.

### Semantics

**Postcondition:** `capacity >= len + additional`.

`additional` is extra element slots beyond current `len` — **not**
“set capacity to `additional`” and **not** a byte size. May reallocate →
invalidates prior raw views. Growth arithmetic must guard overflow
(`len + additional`, `cap * 2`, `cap * size_of(T)`).

### Status

`proposed`

### Implementation mapping

`vec_reserve`

### See also

- `self.cap`
- `self.compact`

---

<a id="vec.shrinkToFit"></a>
## `self.compact`

<!--
id: vec.shrinkToFit
api: self.compact
previous: vec_shrink_to_fit
-->

```vir
self.compact() -> void
```

Shrink capacity to `len` (free storage if empty).

### Status

`proposed`

### Implementation mapping

`vec_compact` (`vec_shrink_to_fit` compatibility alias)

### See also

- `self.reserve`
- `self.clear`

---

<a id="vec.truncate"></a>
## `self.truncate`

<!--
id: vec.truncate
api: self.truncate
previous: vec_truncate
-->

```vir
self.truncate(newLen: int) -> void
```

If `newLen < len`, set `len = newLen`. Does **not** grow when `newLen ≥ len`
(current source: no-op).

### Semantics

Does not run destructors on discarded elements today (no general Drop). Does
not free capacity.

### Status

`proposed`

### Implementation mapping

`vec_truncate`

### See also

- `self.clear`

---

<a id="vec.clear"></a>
## `self.clear`

<!--
id: vec.clear
api: self.clear
previous: vec_clear
-->

```vir
self.clear() -> void
```

Set `len = 0`; capacity retained.

### Semantics

Does not destroy/release former elements under today’s language model. When
Move/resource destructors exist, revisit this contract.

### Status

`proposed`

### Implementation mapping

`vec_clear`

### See also

- `self.truncate`
- `self.free`

---

<a id="vec.free"></a>
## `self.free`

<!--
id: vec.free
api: self.free
previous: vec_free
-->

```vir
self.free() -> void
```

Release owned storage. Do not use `v` afterward.

### Semantics

Public while explicit ownership is required (same stance as `buffer.free`).

### Status

`proposed`

### Implementation mapping

`vec_free`

### See also

- `Vec.new`
- `buffer.free`

---

## Implementation readiness

**API naming is approved; dispatch remains draft.** Core operations exist under
the `vec_*` compatibility layer. Element Drop + borrow refs remain gates — do
not auto-`stable` for owning `T`. Higher-order map/filter remain uncurated.

| Item | Status |
|---|---|
| `size_of(T)` stride / alloc / move | **done** (source) |
| Overflow guards / ZST reject / self-extend / swap / copy | **done** (source) |
| `Vec.*` constructor dispatch | **blocked** — backend cannot lower type receivers yet (`STLB-ISS-0032`) |
| Generic receiver UFCS | **blocked** — generic entity/free-function UFCS is unresolved (`STLB-ISS-0032`) |
| Flat `self.try` naming | **decided** — avoids invalid three-level member paths (`STLB-ISS-0033`) |
| Separate `remove` / `swapRemove` identities | **decided** — no default argument or selector dependency |
| Element Drop on clear/truncate/remove | **gate** (V1) |
| Higher-order map/filter/… | **uncurated** |

Bootstrap `compiler/vec_prelude.vri` and `rt/vec_rt.vri` remain non-public.
