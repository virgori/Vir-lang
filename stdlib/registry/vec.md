---
module: vec
title: Vec
summary: Owned growable typed collection Vec of (T) — namespace-only vec.*.
source:
  - name: collections.vec
    path: vir/collections/vec.vri
status: closed
notes: >-
  Implemented in collections/vec.vri. Callables today are vec_* (no generic entity
  methods yet); registry names remain vec.*. Stride = size_of(T); ZST unsupported.
  Self-extend, overflow guards, vec_swap, vec_copy_range landed.
---

# Vec

Owned, growable **typed** collection `Vec of (T)`. Public API is **namespace-only**:
`vec.<op>(…)`.

```text
string  → UTF-8 text
Buffer  → owned growable binary          (byte)
Slice   → borrowed binary view
Vec of (T)  → owned growable typed collection (element T)
```

```vir
let v = vec.withCap(32)
vec.push(v, 1)
let x = vec.get(v, 0)
vec.free(v)
```

Callables today are `vec_*` free functions (Vir has no generic entity methods yet
for a `vec` namespace object). Registry / docs use canonical `vec.*` names; map
1:1 onto `vec_*` / `vec_copy_range` / `vec_swap` until a namespace facade can land.

## Boundary

| In `vec` | Not in `vec` |
|---|---|
| Typed element storage / grow by **element** | Byte builder → [`buffer`](buffer.md) |
| Panic `get` / Option `tryGet` | Borrowed binary view → [`slice`](slice.md) |
| Owned range `copyRange` | Soft-bootstrap `compiler/vec_prelude` |
| Explicit `free` | Runtime `rt/vec_rt` (`*_rt`) |
| | Raw `as_ptr` / `from_slice(ptr)` — **internal** |
| | Higher-order `map`/`filter`/… — **uncurated** |
| | Receiver `v.push` — **not public** |

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
| Still out | generic `vec` namespace object (no generic methods yet) |

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
`shrinkToFit`, and other paths that grow or relocate the backing store.

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

### `remove` vs `swapRemove`

| API | Order | Complexity (relative) |
|---|---|---|
| `remove` | **preserves** order of remaining elements | shifts the tail — O(n) |
| `swapRemove` | **does not** preserve order | no full-tail shift — O(1) |

### `extend` self-extension

```vir
vec.extend(v, v)
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
| V2 | Canonical docs use `vec.*`; source `vec_*` is a **migration gap**. |
| V3 | Lock move/copy; **no** public borrowed-element references until borrow contracts are enforced. |

### Ownership (locked)

Aligned with other locked collections:

| Op | Ownership |
|---|---|
| `push` / `insert` / `extend` | **Move** element(s) **into** the `Vec` |
| `pop` / `remove` / `swapRemove` | **Move** element **out** to the caller |
| `get` / `tryGet` / `first` / `last` | **Copy** only when `T` is safely copyable |
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
vec.free(v)
```

| Op | Effect |
|---|---|
| `clear` | `len = 0`; capacity retained; no element destructors (today) |
| `truncate(newLen)` | if `newLen < len` → shrink `len`; if `newLen ≥ len` → **no-op** |
| `reserve(additional)` | `capacity >= len + additional` |
| `shrinkToFit` | capacity → `len` (or free if empty); may relocate |
| `free` | release storage; do not use afterward |

Growth strategy today: double capacity (minimum 8 slots when growing from
`reserve`), subject to overflow guards above.

## CORE SPEC surface note

CORE SPEC minimal list is a **subset**. Extra ops already locked here
(`filled`, `first`/`last`, `swapRemove`, `extend`, `clone`, `copyRange`, …)
remain part of this module’s closed surface. HOF stay **uncurated** / out of
this core wave. Ops not listed in either surface stay **out** unless marked
`planned` with a full entry.

## Public surface (closed)


```text
vec
├── new
├── withCap
├── filled
│
├── len
├── cap
├── isEmpty
│
├── get
├── tryGet
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
├── copyRange
├── eq
│
├── reserve
├── shrinkToFit
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

## Migration map

| Current | Public | Impl note | Action |
|---|---|---|---|
| `vec_new` | `vec.new` | empty, no alloc | **rename** |
| `vec_with_cap` | `vec.withCap` | preallocated capacity | **rename** |
| `vec_filled` | `vec.filled` | `n` copies of value | **rename** |
| `vec_from_slice` | — | raw ptr | **internal** |
| `vec_len` | `vec.len` | | **rename** |
| `vec_cap` | `vec.cap` | | **rename** |
| `vec_is_empty` | `vec.isEmpty` | | **rename** |
| `vec_get` | `vec.get` | panic OOB | **rename** |
| `vec_try_get` | `vec.tryGet` | `Option` | **rename** |
| `vec_set` | `vec.set` | panic OOB | **rename** |
| `vec_first` | `vec.first` | `Option` | **rename** |
| `vec_last` | `vec.last` | `Option` | **rename** |
| `vec_push` | `vec.push` | | **rename** |
| `vec_pop` | `vec.pop` | `Option` | **rename** |
| `vec_insert` | `vec.insert` | panic if `idx > len` | **rename** |
| `vec_remove` | `vec.remove` | order-preserving; O(n) shift; returns `T` | **rename** |
| `vec_swap_remove` | `vec.swapRemove` | O(1); order not preserved | **rename** |
| `vec_extend` | `vec.extend` | self-extend **supported** | **rename** + harden |
| `vec_extend_from_slice` | — | raw ptr | **internal** |
| `vec_contains` | `vec.contains` | needs `T` `==` | **rename** |
| `vec_find` | `vec.find` | `Option` of **index** | **rename** |
| `vec_count` | `vec.count` | needs `T` `==` | **rename** |
| `vec_reverse` | `vec.reverse` | in-place | **rename** |
| `vec_swap` | `vec.swap` | exchange indices `a`,`b` | **present** |
| `vec_clone` | `vec.clone` | deep storage / shallow `T` | **rename** |
| `vec_copy_range` / `vec_slice` | `vec.copyRange` | owned copy of `[from,to)` | **present** (`vec_slice` compat alias) |
| `vec_eq` | `vec.eq` | content equality | **rename** |
| `vec_reserve` | `vec.reserve` | `cap >= len + additional` | **rename** |
| `vec_shrink_to_fit` | `vec.shrinkToFit` | | **rename** |
| `vec_truncate` | `vec.truncate` | shrink-only | **rename** |
| `vec_clear` | `vec.clear` | | **rename** |
| `vec_free` | `vec.free` | explicit release | **rename** |
| `vec_as_ptr` / `vec_as_slice` | — | raw / byte view | **internal** |
| `vec_for_each` … `vec_dedup` | — | callback/`ptr` | **uncurated** |

## Equality / search constraint

`contains`, `find`, `count`, and `eq` use element `==` / `!=` as written in
source. Vir does **not** yet express this as a formal trait bound in the
registry — document as:

> Requires `T` to support the equality operators used by the implementation
> (`==` / `!=`). No invented trait constraint beyond what the compiler applies.

`find` returns **`Option` of index** (`Some(i)` / `None`), not the element value.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `vec.new` | `vec.new` | `vec.new() -> Vec of (T)` | proposed |
| `vec.withCap` | `vec.withCap` | `vec.withCap(cap: int) -> Vec of (T)` | proposed |
| `vec.filled` | `vec.filled` | `vec.filled(value: T, n: int) -> Vec of (T)` | proposed |
| `vec.len` | `vec.len` | `vec.len(v: Vec of (T)) -> int` | proposed |
| `vec.cap` | `vec.cap` | `vec.cap(v: Vec of (T)) -> int` | proposed |
| `vec.isEmpty` | `vec.isEmpty` | `vec.isEmpty(v: Vec of (T)) -> bool` | proposed |
| `vec.get` | `vec.get` | `vec.get(v: Vec of (T), i: int) -> T` | proposed |
| `vec.tryGet` | `vec.tryGet` | `vec.tryGet(v: Vec of (T), i: int) -> Option of (T)` | proposed |
| `vec.set` | `vec.set` | `vec.set(v: Vec of (T), i: int, x: T) -> void` | proposed |
| `vec.first` | `vec.first` | `vec.first(v: Vec of (T)) -> Option of (T)` | proposed |
| `vec.last` | `vec.last` | `vec.last(v: Vec of (T)) -> Option of (T)` | proposed |
| `vec.push` | `vec.push` | `vec.push(v: Vec of (T), x: T) -> …` | proposed |
| `vec.pop` | `vec.pop` | `vec.pop(v: Vec of (T)) -> Option of (T)` | proposed |
| `vec.insert` | `vec.insert` | `vec.insert(v: Vec of (T), i: int, x: T) -> void` | proposed |
| `vec.remove` | `vec.remove` | `vec.remove(v: Vec of (T), i: int) -> T` | proposed |
| `vec.swapRemove` | `vec.swapRemove` | `vec.swapRemove(v: Vec of (T), i: int) -> T` | proposed |
| `vec.extend` | `vec.extend` | `vec.extend(v: Vec of (T), other: Vec of (T)) -> void` | proposed |
| `vec.contains` | `vec.contains` | `vec.contains(v: Vec of (T), x: T) -> bool` | proposed |
| `vec.find` | `vec.find` | `vec.find(v: Vec of (T), x: T) -> Option of (int)` · index | proposed |
| `vec.count` | `vec.count` | `vec.count(v: Vec of (T), x: T) -> int` | proposed |
| `vec.reverse` | `vec.reverse` | `vec.reverse(v: Vec of (T)) -> void` | proposed |
| `vec.swap` | `vec.swap` | `vec.swap(v: Vec of (T), a: int, b: int) -> void` | proposed |
| `vec.clone` | `vec.clone` | `vec.clone(v: Vec of (T)) -> Vec of (T)` | proposed |
| `vec.copyRange` | `vec.copyRange` | `vec.copyRange(v: Vec of (T), from: int, to: int) -> Vec of (T)` | proposed |
| `vec.eq` | `vec.eq` | `vec.eq(a: Vec of (T), b: Vec of (T)) -> bool` | proposed |
| `vec.reserve` | `vec.reserve` | `vec.reserve(v: Vec of (T), additional: int) -> void` | proposed |
| `vec.shrinkToFit` | `vec.shrinkToFit` | `vec.shrinkToFit(v: Vec of (T)) -> void` | proposed |
| `vec.truncate` | `vec.truncate` | `vec.truncate(v: Vec of (T), newLen: int) -> void` | proposed |
| `vec.clear` | `vec.clear` | `vec.clear(v: Vec of (T)) -> void` | proposed |
| `vec.free` | `vec.free` | `vec.free(v: Vec of (T)) -> void` | proposed |

---

<a id="vec.new"></a>
## `vec.new`

<!--
id: vec.new
api: vec.new
previous: vec_new
-->

```vir
vec.new() -> Vec of (T)
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
let v = vec.new of (int)()
```

### Status

`proposed` — **present** as `vec_new`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_new`.

### See also

- `vec.withCap`
- `vec.filled`

---

<a id="vec.withCap"></a>
## `vec.withCap`

<!--
id: vec.withCap
api: vec.withCap
previous: vec_with_cap
-->

```vir
vec.withCap(cap: int) -> Vec of (T)
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
let v = vec.withCap(32)
```

### Status

`proposed` — **present** as `vec_with_cap`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_with_cap`.

### See also

- `vec.new`
- `vec.reserve`

---

<a id="vec.filled"></a>
## `vec.filled`

<!--
id: vec.filled
api: vec.filled
previous: vec_filled
-->

```vir
vec.filled(value: T, n: int) -> Vec of (T)
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
let v = vec.filled of (int)(0, 10)
```

### Status

`proposed` — **present** as `vec_filled`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_filled`.

### See also

- `vec.withCap`

---

<a id="vec.len"></a>
## `vec.len`

<!--
id: vec.len
api: vec.len
previous: vec_len
-->

```vir
vec.len(v: Vec of (T)) -> int
```

Number of elements (`len`), not capacity and not bytes.

### Example

```vir
let n = vec.len(v)
```

### Status

`proposed`

### Implementation mapping

`vec_len`

### See also

- `vec.cap`
- `vec.isEmpty`

---

<a id="vec.cap"></a>
## `vec.cap`

<!--
id: vec.cap
api: vec.cap
previous: vec_cap
-->

```vir
vec.cap(v: Vec of (T)) -> int
```

Allocated capacity in **elements**.

### Status

`proposed`

### Implementation mapping

`vec_cap`

### See also

- `vec.len`
- `vec.reserve`

---

<a id="vec.isEmpty"></a>
## `vec.isEmpty`

<!--
id: vec.isEmpty
api: vec.isEmpty
previous: vec_is_empty
-->

```vir
vec.isEmpty(v: Vec of (T)) -> bool
```

`true` when `len == 0`.

### Status

`proposed`

### Implementation mapping

`vec_is_empty`

### See also

- `vec.len`
- `vec.new`

---

<a id="vec.get"></a>
## `vec.get`

<!--
id: vec.get
api: vec.get
previous: vec_get
-->

```vir
vec.get(v: Vec of (T), i: int) -> T
```

Element at index `i`. Panic on OOB. Hot-path primitive (like `slice.get`).

### Errors

`i >= len` → panic.

### Example

```vir
let x = vec.get(v, 0)
```

### Status

`proposed`

### Implementation mapping

`vec_get` — also subject to current 8-byte slot paths until fixed.

### See also

- `vec.tryGet`
- `vec.set`

---

<a id="vec.tryGet"></a>
## `vec.tryGet`

<!--
id: vec.tryGet
api: vec.tryGet
previous: vec_try_get
-->

```vir
vec.tryGet(v: Vec of (T), i: int) -> Option of (T)
```

Element at `i`, or `None` if out of bounds. Does not panic.

### Returns

`Option` of `T` — `Some(element)` / `None`.

### Status

`proposed`

### Implementation mapping

`vec_try_get`

### See also

- `vec.get`
- `vec.first`

---

<a id="vec.set"></a>
## `vec.set`

<!--
id: vec.set
api: vec.set
previous: vec_set
-->

```vir
vec.set(v: Vec of (T), i: int, x: T) -> void
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

- `vec.get`
- `vec.push`

---

<a id="vec.first"></a>
## `vec.first`

<!--
id: vec.first
api: vec.first
previous: vec_first
-->

```vir
vec.first(v: Vec of (T)) -> Option of (T)
```

First element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_first`

### See also

- `vec.last`
- `vec.tryGet`

---

<a id="vec.last"></a>
## `vec.last`

<!--
id: vec.last
api: vec.last
previous: vec_last
-->

```vir
vec.last(v: Vec of (T)) -> Option of (T)
```

Last element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_last`

### See also

- `vec.first`
- `vec.pop`

---

<a id="vec.push"></a>
## `vec.push`

<!--
id: vec.push
api: vec.push
previous: vec_push
-->

```vir
vec.push(v: Vec of (T), x: T) -> …
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

- `vec.pop`
- `vec.extend`

---

<a id="vec.pop"></a>
## `vec.pop`

<!--
id: vec.pop
api: vec.pop
previous: vec_pop
-->

```vir
vec.pop(v: Vec of (T)) -> Option of (T)
```

Remove and return the last element, or `None` if empty.

### Status

`proposed`

### Implementation mapping

`vec_pop`

### See also

- `vec.push`
- `vec.last`

---

<a id="vec.insert"></a>
## `vec.insert`

<!--
id: vec.insert
api: vec.insert
previous: vec_insert
-->

```vir
vec.insert(v: Vec of (T), i: int, x: T) -> void
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

- `vec.remove`
- `vec.push`

---

<a id="vec.remove"></a>
## `vec.remove`

<!--
id: vec.remove
api: vec.remove
previous: vec_remove
-->

```vir
vec.remove(v: Vec of (T), i: int) -> T
```

Remove element at `i`, **preserving order** of the remaining elements. Returns
the removed value. Shifts the tail — relative complexity **O(n)**.

### Errors

`i >= len` → panic.

### Semantics

Does not run element destructors on the removed value beyond returning it to
the caller (see element-ownership limitation). Same allocation unless a future
impl shrinks (today: no shrink).

### Status

`proposed`

### Implementation mapping

`vec_remove`

### See also

- `vec.swapRemove`

---

<a id="vec.swapRemove"></a>
## `vec.swapRemove`

<!--
id: vec.swapRemove
api: vec.swapRemove
previous: vec_swap_remove
-->

```vir
vec.swapRemove(v: Vec of (T), i: int) -> T
```

Remove element at `i` in **O(1)** by swapping with the last element, then
shrinking `len`. **Order is not preserved.** Does **not** shift the whole
tail.

### Errors

`i >= len` → panic.

### Semantics

Systems-programming escape hatch vs order-preserving `remove`.

### Status

`proposed`

### Implementation mapping

`vec_swap_remove`

### See also

- `vec.remove`
- `vec.swap`

---

<a id="vec.extend"></a>
## `vec.extend`

<!--
id: vec.extend
api: vec.extend
previous: vec_extend
-->

```vir
vec.extend(v: Vec of (T), other: Vec of (T)) -> void
```

Append all elements of `other` onto `v`.

### Semantics

Public bulk append from another `Vec`. Raw `extend_from_slice(ptr,…)` is
**internal**.

**Self-extension** `vec.extend(v, v)` is **supported**: snapshot the source
length / prefix before reallocating to append; must not UB. May reallocate →
invalidates prior raw views into `v`.

### Status

`proposed` — self-alias snapshot before reserve (implemented).

### Implementation mapping

`vec_extend`


### See also

- `vec.push`
- `vec.clone`

---

<a id="vec.contains"></a>
## `vec.contains`

<!--
id: vec.contains
api: vec.contains
previous: vec_contains
-->

```vir
vec.contains(v: Vec of (T), x: T) -> bool
```

Whether any element equals `x` (`==`).

### Semantics

Requires `T` equality as used by the implementation — no invented trait bound.

### Status

`proposed`

### Implementation mapping

`vec_contains`

### See also

- `vec.find`
- `vec.count`

---

<a id="vec.find"></a>
## `vec.find`

<!--
id: vec.find
api: vec.find
previous: vec_find
-->

```vir
vec.find(v: Vec of (T), x: T) -> Option of (int)
```

First **index** where the element equals `x`, or `None`.

### Returns

`Option` of `int` — **index**, not the element value.

### Semantics

Requires `T` equality as used by the implementation.

### Example

```vir
let i = vec.find(v, x)
# Some(index) or None
```

### Status

`proposed`

### Implementation mapping

`vec_find`

### See also

- `vec.contains`
- `vec.get`

---

<a id="vec.count"></a>
## `vec.count`

<!--
id: vec.count
api: vec.count
previous: vec_count
-->

```vir
vec.count(v: Vec of (T), x: T) -> int
```

Number of elements equal to `x`.

### Status

`proposed`

### Implementation mapping

`vec_count`

### See also

- `vec.contains`

---

<a id="vec.reverse"></a>
## `vec.reverse`

<!--
id: vec.reverse
api: vec.reverse
previous: vec_reverse
-->

```vir
vec.reverse(v: Vec of (T)) -> void
```

Reverse elements in place.

### Status

`proposed`

### Implementation mapping

`vec_reverse`

### See also

- `vec.clone`

---

<a id="vec.swap"></a>
## `vec.swap`

<!--
id: vec.swap
api: vec.swap
-->

```vir
vec.swap(v: Vec of (T), a: int, b: int) -> void
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
vec.swap(v, i, j)
```

### Status

`proposed` — **present** as `vec_swap`.

### Implementation mapping

`vir/collections/vec.vri` → `vec_swap`.

### See also

- `vec.swapRemove`
- `vec.reverse`

---

<a id="vec.clone"></a>
## `vec.clone`

<!--
id: vec.clone
api: vec.clone
previous: vec_clone
-->

```vir
vec.clone(v: Vec of (T)) -> Vec of (T)
```

Full-vector copy into new storage.

### Semantics

**Deep** with respect to `Vec` backing storage; **shallow** with respect to
`T` — each element is copied by value; pointed-to resources are not
deep-cloned. Distinct from `copyRange` (partial).

### Status

`proposed`

### Implementation mapping

`vec_clone`

### See also

- `vec.copyRange`
- `vec.eq`

---

<a id="vec.copyRange"></a>
## `vec.copyRange`

<!--
id: vec.copyRange
api: vec.copyRange
previous: vec_slice
-->

```vir
vec.copyRange(v: Vec of (T), from: int, to: int) -> Vec of (T)
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
clone — that is `vec.clone`. Naming `copyRange` avoids reading as “clone the
whole collection.”

Element copies are shallow w.r.t. `T` (same as `clone`).

### Example

```vir
let whole = vec.clone(v)
let part = vec.copyRange(v, 2, 5)
# owned Vec of former elements [2,5)
```

### Status

`proposed` — **present** as `vec_copy_range`; `vec_slice` kept as compat alias.

### Implementation mapping

`vir/collections/vec.vri` → `vec_copy_range`.

### See also

- `vec.clone`
- `slice.sub` *(borrowed binary — different type)*

---

<a id="vec.eq"></a>
## `vec.eq`

<!--
id: vec.eq
api: vec.eq
previous: vec_eq
-->

```vir
vec.eq(a: Vec of (T), b: Vec of (T)) -> bool
```

Content equality: same length and pairwise `==` elements.

### Semantics

Kept public (same rationale as `slice.eq`). Future language `==` on `Vec`
may lower to this. Requires element equality as used by the implementation.

### Status

`proposed`

### Implementation mapping

`vec_eq`

### See also

- `vec.clone`

---

<a id="vec.reserve"></a>
## `vec.reserve`

<!--
id: vec.reserve
api: vec.reserve
previous: vec_reserve
-->

```vir
vec.reserve(v: Vec of (T), additional: int) -> void
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

- `vec.cap`
- `vec.shrinkToFit`

---

<a id="vec.shrinkToFit"></a>
## `vec.shrinkToFit`

<!--
id: vec.shrinkToFit
api: vec.shrinkToFit
previous: vec_shrink_to_fit
-->

```vir
vec.shrinkToFit(v: Vec of (T)) -> void
```

Shrink capacity to `len` (free storage if empty).

### Status

`proposed`

### Implementation mapping

`vec_shrink_to_fit`

### See also

- `vec.reserve`
- `vec.clear`

---

<a id="vec.truncate"></a>
## `vec.truncate`

<!--
id: vec.truncate
api: vec.truncate
previous: vec_truncate
-->

```vir
vec.truncate(v: Vec of (T), newLen: int) -> void
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

- `vec.clear`

---

<a id="vec.clear"></a>
## `vec.clear`

<!--
id: vec.clear
api: vec.clear
previous: vec_clear
-->

```vir
vec.clear(v: Vec of (T)) -> void
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

- `vec.truncate`
- `vec.free`

---

<a id="vec.free"></a>
## `vec.free`

<!--
id: vec.free
api: vec.free
previous: vec_free
-->

```vir
vec.free(v: Vec of (T)) -> void
```

Release owned storage. Do not use `v` afterward.

### Semantics

Public while explicit ownership is required (same stance as `buffer.free`).

### Status

`proposed`

### Implementation mapping

`vec_free`

### See also

- `vec.new`
- `buffer.free`

---

## Implementation readiness

**Design status: closed** (V1–V3). Core ops exist under `vec_*` (migration gap V2).
Element Drop + borrow refs = gates — do not auto-`stable` for owning `T`.
No `.vri` redesign until authorized (Q5). Higher-order map/filter remain uncurated.

| Item | Status |
|---|---|
| `size_of(T)` stride / alloc / move | **done** (source) |
| Overflow guards / ZST reject / self-extend / swap / copyRange | **done** (source) |
| `vec.*` namespace object | **blocked** — use `vec_*` until generic methods |
| Element Drop on clear/truncate/remove | **gate** (V1) |
| Higher-order map/filter/… | **uncurated** |

Bootstrap `compiler/vec_prelude.vri` and `rt/vec_rt.vri` remain non-public.