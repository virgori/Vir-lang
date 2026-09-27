---
module: slice
title: Slice
summary: Borrowed binary view (ptr, len) — namespace-only slice.*.
source:
  - name: slice
    path: vir/mem/slice.vri
status: draft
notes: >-
  Separate from buffer.md — Slice does not own storage. Namespace-only like
  buffer/path. Indexing is get/set (not byte — avoids Reader.byte confusion).
  copyTo target = overlap-safe (mem_move). Keep eq for content compare / future ==.
  No .vri changes until implementation against this map.
---

# Slice

Borrowed binary view `(ptr, len)`. Does **not** allocate or free. Public API is
**namespace-only**: `slice.<op>(…)`.

```text
Buffer
  │ owns
  ▼
binary storage
  ▲
  │ borrows/views
Slice
```

Canonical bridge from an owner:

```vir
let view = buffer.slice(b)   # -> Slice
```

Not merged into a `bytes` namespace. Pair with [`buffer.md`](buffer.md).

```vir
let s = slice.sub(view, 0, 4)
slice.copyTo(s, dst)
```

## Boundary

| In `slice` | Not in `slice` |
|---|---|
| Borrowed view over existing memory | Owned growable storage → `buffer` |
| Index / subview / fill / copy between slices | Text → `string` |
| Content equality / find byte | `buffer.push*` / `buffer.free` |
| | Receiver `s.get` — **not public** |
| | Lifetime extension beyond owner — **impossible** |

## Borrow lifetime (closed)

A `Slice` is valid only while:

1. the backing memory remains allocated at the same address;
2. the referenced byte range remains defined by the owner.

When the owner is a `Buffer`:

| Owner event | Effect on outstanding `Slice` |
|---|---|
| `buffer.reserve` / `push*` / `write` (realloc) | **Invalid** |
| `buffer.free` | **Invalid** |
| `buffer.clear` / `truncate` (shrink `len`) | Views past new `len` are **invalid** to read |
| `buffer.set` / `setU32` (in-place) | Address stable; content may change |

`slice.sub` does **not** extend lifetime — it returns another borrow into the
same storage.

Registry does not invent a borrow checker here; it documents the rule callers
must respect until the language enforces it.

## Indexing (closed)

Random access is **`get` / `set`**, not `byte`:

```vir
slice.get(s, i)
slice.set(s, i, value)
```

`Slice` is a borrowed binary array view (`[u8]`). `get`/`set` match indexed
access. Public name `byte` is reserved against confusion with stream APIs such
as `reader.byte()` (sequential consume).

If the Vir compiler exposes index syntax later, map:

```text
s[i]  →  slice.get(s, i)
```

(and a corresponding store form to `slice.set` if assignment indexing lands).
Until then, call `slice.get` / `slice.set` explicitly. Namespace style remains
`slice.get(s, i)` — not receiver `s.get(i)`.

## Public surface (closed)

```text
slice
├── new
├── empty
│
├── get
├── set
├── sub
│
├── len
├── eq
├── find
│
├── copyTo
└── fill
```

```vir
slice.new(data, len)
slice.empty()
slice.get(s, i)
slice.set(s, i, value)
slice.sub(s, from, to)
slice.len(s)
slice.eq(a, b)
slice.find(s, byte)
slice.copyTo(src, dst)
slice.fill(s, value)
```

## Migration map

| Current | Public | Impl note | Action |
|---|---|---|---|
| `slice_new` | `slice.new` | `(ptr, len)` view | **rename** |
| `slice_empty` | `slice.empty` | null + `len = 0` | **rename** |
| `slice_get` | `slice.get` | indexed byte read | **rename** |
| `slice_set` | `slice.set` | indexed byte write | **rename** |
| `slice_sub` | `slice.sub` | half-open `[from, to)` · OOB **panic** | **rename** |
| — | `slice.len` | today field `s.len` | **expose** ns accessor *(planned)* |
| `slice_eq` | `slice.eq` | content equality (`len` + `mem_cmp`) | **rename** · **keep** |
| `slice_find_byte` | `slice.find` | first byte value | **rename** |
| `slice_copy_to` | `slice.copyTo` | today `mem_copy` → target **`mem_move`** | **rename** + **change** |
| `slice_fill` | `slice.fill` | fill all bytes | **rename** |

### Why keep `eq`

`slice.eq` is **required** public API:

- Content compare after `a.len == b.len` then `mem_cmp` — not pointer identity.
- Without it, callers invent loops or wrongly compare `a.data == b.data`.
- Future: compiler may lower `a == b` on `Slice` to this content equality.

Distinct from removing public `string.eq` (language `==` on `string`).

## Sub boundary (closed)

```vir
slice.sub(s, from, to) -> Slice
```

Half-open byte range **`[from, to)`**.

OOB (`from > to` or `to > s.len`) → **panic** immediately. No `Result`.
Slicing is a hot-path primitive; wrapping every `sub` in `Result` would fight
loop optimization (aligned with Go / Rust / Zig panic-on-bad-slice style).

Result points at `s.data + from` with length `to - from`. No copy. No ownership
transfer. Does not extend borrow lifetime.

## Copy semantics (closed)

```vir
slice.copyTo(src, dst) -> void
```

Copies `n = min(src.len, dst.len)` bytes from `src` into `dst`. Does not grow
`dst`.

**Overlap:** public `copyTo` must be **overlap-safe**. Target implementation
uses `mem_move` (already in `vir/mem/copy.vri`), not `mem_copy` / memcpy-style
UB on overlapping ranges.

| Today | Target |
|---|---|
| `slice_copy_to` → `mem_copy` | `slice.copyTo` → **`mem_move`** |

Do **not** ship a footgun public name that requires non-overlapping regions
unless a separate unchecked/internal helper is added later. Default public API
stays the safe name `copyTo`.

```vir
slice.fill(s, value) -> void
```

Sets every byte in `s` to `value` (via `mem_set` today).

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `slice.new` | `slice.new` | `slice.new(data: ptr, len: int) -> Slice` | proposed |
| `slice.empty` | `slice.empty` | `slice.empty() -> Slice` | proposed |
| `slice.get` | `slice.get` | `slice.get(s: Slice, i: int) -> int` | proposed |
| `slice.set` | `slice.set` | `slice.set(s: Slice, i: int, value: int) -> void` | proposed |
| `slice.sub` | `slice.sub` | `slice.sub(s: Slice, from: int, to: int) -> Slice` | proposed |
| `slice.len` | `slice.len` | `slice.len(s: Slice) -> int` | planned |
| `slice.eq` | `slice.eq` | `slice.eq(a: Slice, b: Slice) -> bool` | proposed |
| `slice.find` | `slice.find` | `slice.find(s: Slice, byte: int) -> Option(int)` | proposed |
| `slice.copyTo` | `slice.copyTo` | `slice.copyTo(src: Slice, dst: Slice) -> void` | proposed |
| `slice.fill` | `slice.fill` | `slice.fill(s: Slice, value: int) -> void` | proposed |

---

<a id="slice.new"></a>
## `slice.new`

<!--
id: slice.new
api: slice.new
previous: slice_new
-->

```vir
slice.new(data: ptr, len: int) -> Slice
```

Constructs a borrowed view over `len` bytes at `data`.

### Parameters

#### `data: ptr`

Start of existing memory (caller-owned / buffer-owned).

#### `len: int`

Byte length of the view.

### Returns

`Slice`

### Errors

None at construction; invalid `data`/`len` is undefined later.

### Semantics

Low-level constructor. Prefer `buffer.slice(b)` when the owner is a `Buffer`.

### Example

```vir
# prefer: let s = buffer.slice(b)
let s = slice.new(p, n)
```

### Status

`proposed` — **present** as `slice_new`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_new`.

### See also

- `slice.empty`
- `buffer.slice`

---

<a id="slice.empty"></a>
## `slice.empty`

<!--
id: slice.empty
api: slice.empty
previous: slice_empty
-->

```vir
slice.empty() -> Slice
```

Empty view (`null` data, `len = 0` today).

### Parameters

None.

### Returns

`Slice` with zero length.

### Errors

None.

### Example

```vir
let s = slice.empty()
```

### Status

`proposed` — **present** as `slice_empty`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_empty`.

### See also

- `slice.new`
- `slice.len`

---

<a id="slice.get"></a>
## `slice.get`

<!--
id: slice.get
api: slice.get
previous: slice_get
-->

```vir
slice.get(s: Slice, i: int) -> int
```

Reads the byte at index `i` (random access into the borrowed array view).

### Parameters

#### `s: Slice`

View to read.

#### `i: int`

Index (`0 ≤ i < len`).

### Returns

`int` — byte `0…255`.

### Errors

Out of bounds → panic today.

### Semantics

Indexed get — not stream `reader.byte()`. Future `s[i]` should lower to this
API if the language adds index operators.

### Example

```vir
let x = slice.get(s, 0)
```

### Status

`proposed` — **present** as `slice_get`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_get`.

### See also

- `slice.set`
- `buffer.byte` *(offset read on owned buffer — different owner API)*

---

<a id="slice.set"></a>
## `slice.set`

<!--
id: slice.set
api: slice.set
previous: slice_set
-->

```vir
slice.set(s: Slice, i: int, value: int) -> void
```

Writes one byte at index `i` into the underlying memory.

### Parameters

#### `s: Slice`

View (mutable underlying storage).

#### `i: int`

Index in range.

#### `value: int`

Byte to store.

### Returns

None.

### Errors

Out of bounds → panic today.

### Semantics

Does not grow. Requires the backing memory to be writable.

### Example

```vir
slice.set(s, 0, 0x00)
```

### Status

`proposed` — **present** as `slice_set`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_set`.

### See also

- `slice.get`
- `buffer.set`

---

<a id="slice.sub"></a>
## `slice.sub`

<!--
id: slice.sub
api: slice.sub
previous: slice_sub
-->

```vir
slice.sub(s: Slice, from: int, to: int) -> Slice
```

Subview `[from, to)` — half-open byte range.

### Parameters

#### `s: Slice`

Parent view.

#### `from: int`

Start offset (inclusive).

#### `to: int`

End offset (exclusive).

### Returns

`Slice` — shorter borrow into the same storage.

### Errors

`from > to` or `to > s.len` → **panic** (not `Result`).

### Semantics

No allocation. Hot-path primitive — panic on bad bounds. Lifetime tied to the
same backing memory as `s`. Empty subview when `from == to` and both in range.

### Example

```vir
let head = slice.sub(s, 0, 4)
```

### Status

`proposed` — **present** as `slice_sub`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_sub`.

### See also

- `slice.get`
- `buffer.slice`

---

<a id="slice.len"></a>
## `slice.len`

<!--
id: slice.len
api: slice.len
-->

```vir
slice.len(s: Slice) -> int
```

Byte length of the view.

### Parameters

#### `s: Slice`

View to query.

### Returns

`int` — `≥ 0`.

### Errors

None.

### Semantics

Today length is the entity field `s.len`. Public contract prefers
`slice.len(s)` so callers need not treat fields as API. Implementation may
thin-wrap the field.

### Example

```vir
let n = slice.len(s)
```

### Status

`planned` — field present; namespace accessor to align with `buffer.len`.

### Implementation mapping

New wrapper over `s.len`, or document field until wrapper lands.

### See also

- `buffer.len`
- `slice.empty`

---

<a id="slice.eq"></a>
## `slice.eq`

<!--
id: slice.eq
api: slice.eq
previous: slice_eq
-->

```vir
slice.eq(a: Slice, b: Slice) -> bool
```

Content equality: same length and equal bytes.

### Parameters

#### `a: Slice` / `b: Slice`

Views to compare.

### Returns

`bool`

### Errors

None.

### Semantics

Content compare: length check then `mem_cmp`. **Not** pointer identity
(`a.data == b.data`). Required public API — without it callers invent loops or
compare pointers wrongly. Future compiler may lower `a == b` on `Slice` values
to this function.

### Example

```vir
if slice.eq(a, b) do
    io.println("same")
end
```

### Status

`proposed` — **present** as `slice_eq`; **keep**.

### Implementation mapping

`vir/mem/slice.vri` → `slice_eq`.

### See also

- `slice.copyTo`

---

<a id="slice.find"></a>
## `slice.find`

<!--
id: slice.find
api: slice.find
previous: slice_find_byte
-->

```vir
slice.find(s: Slice, byte: int) -> Option(int)
```

First index of `byte`, or `None`.

### Parameters

#### `s: Slice`

Haystack view.

#### `byte: int`

Byte value to search for.

### Returns

`Option` of `int` — `Some(index)` or `None`.

### Errors

None.

### Semantics

Byte search only (not UTF-8 / string find). Index is a **byte** offset into `s`.

### Example

```vir
let i = slice.find(s, 0x0A)
```

### Status

`proposed` — **present** as `slice_find_byte`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_find_byte`.

### See also

- `slice.get`
- [`string.find`](string.md) *(codepoint index)* / `string.byteFind` *(byte index)*

---

<a id="slice.copyTo"></a>
## `slice.copyTo`

<!--
id: slice.copyTo
api: slice.copyTo
previous: slice_copy_to
-->

```vir
slice.copyTo(src: Slice, dst: Slice) -> void
```

Copies `min(src.len, dst.len)` bytes from `src` into `dst`.

### Parameters

#### `src: Slice`

Source bytes.

#### `dst: Slice`

Destination view (must be writable; not grown).

### Returns

None.

### Errors

None at API level.

### Semantics

Does not allocate. Truncates copy to the shorter length. Does not report a
count today.

**Overlap-safe by contract:** target uses `mem_move` so overlapping `src`/`dst`
(same backing buffer, overlapping ranges) is defined. Today’s
`slice_copy_to` calls `mem_copy` — **change** on implement. Do not rename the
public API to `copyToNonoverlapping` / `…Unchecked`; keep `copyTo` as the safe
default. An unchecked non-overlap helper may be internal later if profiling
demands it.

### Example

```vir
slice.copyTo(src, dst)
```

### Status

`proposed` — **present** with unsafe-on-overlap impl → target `mem_move`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_copy_to`; switch to `mem_move` from
`vir/mem/copy.vri`.

### See also

- `slice.fill`
- `buffer.write`

---

<a id="slice.fill"></a>
## `slice.fill`

<!--
id: slice.fill
api: slice.fill
previous: slice_fill
-->

```vir
slice.fill(s: Slice, value: int) -> void
```

Sets every byte in `s` to `value`.

### Parameters

#### `s: Slice`

Writable view.

#### `value: int`

Fill byte.

### Returns

None.

### Errors

None.

### Semantics

Uses `mem_set` today over `s.len` bytes.

### Example

```vir
slice.fill(s, 0)
```

### Status

`proposed` — **present** as `slice_fill`.

### Implementation mapping

`vir/mem/slice.vri` → `slice_fill`.

### See also

- `slice.copyTo`
- `slice.set`

---

## Implementation readiness

Public slice API map is closed for this refactor.
Implementation may proceed against this registry.
Binary model (`Buffer` + `Slice` + `string`) is closed with [`buffer.md`](buffer.md).
