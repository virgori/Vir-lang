---
module: buffer
title: Buffer
summary: Owned growable binary storage — namespace-only buffer.*.
source:
  - name: buffer
    path: vir/mem/buffer.vri
status: stable
notes: >-
  Namespace-only like path. No receiver b.*. Integer push/set encode little-endian
  by default. write_bytes/grow/patch_u32 internal. Pair with slice.md; bridge is
  buffer.slice(b). No .vri changes until implementation against this map.
---

# Buffer

Owned, growable binary storage. Public API is **namespace-only**: `buffer.<op>(…)`.

```text
Buffer
  │ owns
  ▼
binary storage
  ▲
  │ borrows/views
Slice
```

Canonical borrow bridge:

```vir
buffer.slice(b) -> Slice
```

Not a public type named `bytes`. Not merged with [`slice.md`](slice.md).

```vir
let b = buffer.new(256)
buffer.pushU32(b, 0x12345678)
let view = buffer.slice(b)
# …
buffer.free(b)
```

## Boundary

| In `buffer` | Not in `buffer` |
|---|---|
| Own / grow / append / patch binary | Borrowed view ops → [`slice`](slice.md) |
| LE integer encode helpers | Text → `string` |
| Explicit `free` (current ownership) | `io.BufferedReader` / ring buffers |
| | Codegen `ByteBuffer` / `buf_*` |
| | Receiver API `b.push` — **not public** |
| | `buffer.bytes()` synonym — **not public** |
| | Raw `write_bytes(ptr)` — **internal** |

## Binary model

| Type | Role |
|---|---|
| `Buffer` | Owned growable storage (`data`, `len`, `cap`) |
| `Slice` | Borrowed `(ptr, len)` view — see [`slice.md`](slice.md) |
| `string` | Text (UTF-8) |

## Endianness (closed)

Integer encode/decode on `Buffer` is **little-endian** by default:

```text
pushU16 / pushU32 / pushU64
u32 / setU32
```

No `…LE` suffix while LE is the only public integer encoding. Big-endian is out
of this surface until a real need appears.

## Decision B1 (locked)

## CORE SPEC name map (reconcile — no invent)

| SPEC | Canonical in this registry |
|---|---|
| `buffer.withCap(cap)` | **`buffer.new(cap)`** — capacity constructor already locked |
| `buffer.empty()` | keep — distinct empty ctor |
| `buffer.get` | **canonical** byte read (previous public name `buffer.byte`) |
| `buffer.byte` | → **`buffer.get`** (SPEC: no public `byte` alias) |
| `buffer.copyTo` | **not a Buffer method** — use [`slice.copyTo`](slice.md) on `buffer.slice(b)` |
| Integer push/set | `pushU16`/`U32`/`U64`, `setU32`, … — LE locked |

Do **not** invent `buffer.withCap` as a second public name.

`Buffer` is owned, mutable, contiguous **binary** storage (no implicit UTF-8 decode). It owns storage under **move** semantics and must be **`buffer.free`**
explicitly under the current lifecycle. Do not assume automatic destruction the
language does not guarantee. Growing / restructuring that may relocate storage
invalidates outstanding [`Slice`](slice.md) views (see borrow rules below).

Little-endian integer helpers remain locked. `copyTo` on slices is overlap-safe
(see [`slice`](slice.md)).

## Ownership and borrow invalidation (closed)

`Buffer` is a **Move** type today. Mutating APIs take `ref b: Buffer`.

```vir
buffer.free(b)
```

is **public** while the memory model requires explicit release. Docs do **not**
assume automatic destruction that the compiler does not yet guarantee.

Rules:

1. `free` releases the buffer; the value must not be used afterward.
2. A `Slice` from `buffer.slice(b)` is valid only while the underlying storage
   remains at the same address and covers that range.
3. Operations that may **reallocate** (including `reserve`, `push*`, `write`,
   and internal grow) **invalidate** outstanding slices borrowed from that
   buffer.

```vir
let view = buffer.slice(b)
buffer.reserve(b, 4096)   # may realloc → view may be dangling
```

Also invalidated by `free`, and by any future impl that moves the backing store.

## Public surface (closed)

```text
buffer
├── new
├── empty
│
├── push
├── pushU16
├── pushU32
├── pushU64
├── write
│
├── get          # was byte (SPEC)
├── u32
├── set
├── setU32
│
├── slice
│
├── len
├── cap
├── isEmpty
│
├── clear
├── truncate
├── reserve
└── free
```

Collision accepted:

```vir
buffer.empty()      # construct empty Buffer
buffer.isEmpty(b)   # predicate
```

No public `buffer.default`. No public `buffer.bytes()`.

## Migration map

| Current | Public | Impl note | Action |
|---|---|---|---|
| `buffer_new` | `buffer.new` | capacity arg; `≤0` → initial cap 256 | **rename** |
| `buffer_default` | `buffer.empty` | `buffer_new(256)` today | **rename** |
| `buffer_push` | `buffer.push` | one byte | **rename** |
| `buffer_push_u16` | `buffer.pushU16` | LE uint16 | **rename** |
| `buffer_push_u32` | `buffer.pushU32` | LE uint32 | **rename** |
| `buffer_push_u64` | `buffer.pushU64` | LE uint64 | **rename** |
| `buffer_write` | `buffer.write` | append `Slice` | **rename** |
| `buffer_write_bytes` | — | raw `ptr` + count | **internal** |
| `buffer_read_u8` / `buffer.get` | `buffer.get` | byte at offset | **rename** · SPEC canonical `get` |
| `buffer_read_u32` | `buffer.u32` | LE u32 at offset | **rename** |
| `buffer_write_at` | `buffer.set` | byte at offset | **rename** |
| `buffer_write_u32_at` | `buffer.setU32` | LE u32 at offset | **rename** |
| `buffer_patch_u32` | `buffer.setU32` | alias of write_u32_at | **merge** / remove public |
| `buffer_as_slice` | `buffer.slice` | → `Slice` of `[0, len)` | **rename** |
| `buffer_len` | `buffer.len` | | **rename** |
| `buffer_cap` | `buffer.cap` | | **rename** |
| `buffer_is_empty` | `buffer.isEmpty` | not `empty` (ctor) | **rename** |
| `buffer_clear` | `buffer.clear` | `len = 0`, keep cap | **rename** |
| `buffer_truncate` | `buffer.truncate` | shrink `len` only if smaller | **rename** |
| `buffer_reserve` | `buffer.reserve` | grow for `additional` bytes | **rename** |
| `buffer_free` | `buffer.free` | explicit release | **rename** |
| `buffer_grow` | — | capacity helper | **internal** |
| `BUFFER_INITIAL_CAP` | — | const 256 | **internal** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `buffer.new` | `buffer.new` | `buffer.new(cap: int) -> Buffer` | proposed |
| `buffer.empty` | `buffer.empty` | `buffer.empty() -> Buffer` | proposed |
| `buffer.push` | `buffer.push` | `buffer.push(b: Buffer, byte: int) -> void` | proposed |
| `buffer.pushU16` | `buffer.pushU16` | `buffer.pushU16(b: Buffer, value: int) -> void` | proposed |
| `buffer.pushU32` | `buffer.pushU32` | `buffer.pushU32(b: Buffer, value: int) -> void` | proposed |
| `buffer.pushU64` | `buffer.pushU64` | `buffer.pushU64(b: Buffer, value: int) -> void` | proposed |
| `buffer.write` | `buffer.write` | `buffer.write(b: Buffer, data: Slice) -> void` | proposed |
| `buffer.get` | `buffer.get` | `buffer.get(b: Buffer, offset: int) -> int` | proposed |
| `buffer.u32` | `buffer.u32` | `buffer.u32(b: Buffer, offset: int) -> int` | proposed |
| `buffer.set` | `buffer.set` | `buffer.set(b: Buffer, offset: int, value: int) -> void` | proposed |
| `buffer.setU32` | `buffer.setU32` | `buffer.setU32(b: Buffer, offset: int, value: int) -> void` | proposed |
| `buffer.slice` | `buffer.slice` | `buffer.slice(b: Buffer) -> Slice` | proposed |
| `buffer.len` | `buffer.len` | `buffer.len(b: Buffer) -> int` | proposed |
| `buffer.cap` | `buffer.cap` | `buffer.cap(b: Buffer) -> int` | proposed |
| `buffer.isEmpty` | `buffer.isEmpty` | `buffer.isEmpty(b: Buffer) -> bool` | proposed |
| `buffer.clear` | `buffer.clear` | `buffer.clear(b: Buffer) -> void` | proposed |
| `buffer.truncate` | `buffer.truncate` | `buffer.truncate(b: Buffer, new_len: int) -> void` | proposed |
| `buffer.reserve` | `buffer.reserve` | `buffer.reserve(b: Buffer, additional: int) -> void` | proposed |
| `buffer.free` | `buffer.free` | `buffer.free(b: Buffer) -> void` | proposed |

Signatures use `b: Buffer` in docs; mutating calls take `ref` in source today.

---

<a id="buffer.new"></a>
## `buffer.new`

<!--
id: buffer.new
api: buffer.new
previous: buffer_new
-->

```vir
buffer.new(cap: int) -> Buffer
```

Allocates an owned buffer with at least `cap` bytes of capacity (`len = 0`).

### Parameters

#### `cap: int`

Requested capacity. If `cap ≤ 0`, implementation uses initial capacity **256**
(`BUFFER_INITIAL_CAP`).

### Returns

`Buffer` — empty (`len = 0`), ready to append.

### Errors

Allocation failure follows host/runtime alloc behavior (today: no `Result`).

### Semantics

Does not touch the filesystem. Does not zero-fill beyond allocator behavior.

### Example

```vir
let b = buffer.new(256)
```

### Status

`proposed` — **present** as `buffer_new`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_new`.

### See also

- `buffer.empty`
- `buffer.free`

---

<a id="buffer.empty"></a>
## `buffer.empty`

<!--
id: buffer.empty
api: buffer.empty
previous: buffer_default
-->

```vir
buffer.empty() -> Buffer
```

Constructs an empty buffer with the default initial capacity.

### Parameters

None.

### Returns

`Buffer` — same as `buffer.new` with default capacity (256 today).

### Errors

Same as `buffer.new`.

### Semantics

Not `buffer.default`. Distinct from predicate `buffer.isEmpty`.

### Example

```vir
let b = buffer.empty()
```

### Status

`proposed` — **present** as `buffer_default`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_default`.

### See also

- `buffer.new`
- `buffer.isEmpty`

---

<a id="buffer.push"></a>
## `buffer.push`

<!--
id: buffer.push
api: buffer.push
previous: buffer_push
-->

```vir
buffer.push(b: Buffer, byte: int) -> void
```

Appends one byte (low 8 bits of `byte` as written by impl).

### Parameters

#### `b: Buffer`

Target buffer (`ref` in source).

#### `byte: int`

Byte value to append.

### Returns

None.

### Errors

May panic / abort on alloc failure during grow (current style).

### Semantics

May reallocate → invalidates outstanding `Slice` views.

### Example

```vir
buffer.push(b, 0x0A)
```

### Status

`proposed` — **present** as `buffer_push`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_push`.

### See also

- `buffer.write`
- `buffer.pushU32`

---

<a id="buffer.pushU16"></a>
## `buffer.pushU16`

<!--
id: buffer.pushU16
api: buffer.pushU16
previous: buffer_push_u16
-->

```vir
buffer.pushU16(b: Buffer, value: int) -> void
```

Appends a **little-endian** unsigned 16-bit value (2 bytes).

### Parameters

#### `b: Buffer`

Target buffer.

#### `value: int`

Value; low 16 bits encoded LE.

### Returns

None.

### Errors

Grow / alloc as `push`.

### Semantics

Default integer encoding for `Buffer` is LE. May reallocate.

### Example

```vir
buffer.pushU16(b, 0x1234)
```

### Status

`proposed` — **present** as `buffer_push_u16`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_push_u16`.

### See also

- `buffer.pushU32`
- `buffer.pushU64`

---

<a id="buffer.pushU32"></a>
## `buffer.pushU32`

<!--
id: buffer.pushU32
api: buffer.pushU32
previous: buffer_push_u32
-->

```vir
buffer.pushU32(b: Buffer, value: int) -> void
```

Appends a **little-endian** unsigned 32-bit value (4 bytes).

### Parameters

#### `b: Buffer`

Target buffer.

#### `value: int`

Value; low 32 bits encoded LE.

### Returns

None.

### Errors

Grow / alloc as `push`.

### Semantics

May reallocate. Prefer this over building a temporary `Slice` for one integer.

### Example

```vir
buffer.pushU32(b, 0x12345678)
```

### Status

`proposed` — **present** as `buffer_push_u32`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_push_u32`.

### See also

- `buffer.setU32`
- `buffer.u32`

---

<a id="buffer.pushU64"></a>
## `buffer.pushU64`

<!--
id: buffer.pushU64
api: buffer.pushU64
previous: buffer_push_u64
-->

```vir
buffer.pushU64(b: Buffer, value: int) -> void
```

Appends a **little-endian** unsigned 64-bit value (8 bytes), using the host
integer representation available to the current impl.

### Parameters

#### `b: Buffer`

Target buffer.

#### `value: int`

Value encoded LE across 8 bytes (current loop write).

### Returns

None.

### Errors

Grow / alloc as `push`.

### Semantics

May reallocate.

### Example

```vir
buffer.pushU64(b, n)
```

### Status

`proposed` — **present** as `buffer_push_u64`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_push_u64`.

### See also

- `buffer.pushU32`

---

<a id="buffer.write"></a>
## `buffer.write`

<!--
id: buffer.write
api: buffer.write
previous: buffer_write
-->

```vir
buffer.write(b: Buffer, data: Slice) -> void
```

Appends all bytes of `data` onto `b`. Sole **public** bulk-append API.

### Parameters

#### `b: Buffer`

Target buffer.

#### `data: Slice`

Borrowed source bytes (see [`slice.md`](slice.md)).

### Returns

None.

### Errors

Grow / alloc as `push`.

### Semantics

Raw `buffer_write_bytes(ptr, count)` is **internal** — not part of the public
layering `Buffer ← Slice ← memory`. May reallocate.

### Example

```vir
buffer.write(b, data)
```

### Status

`proposed` — **present** as `buffer_write`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_write`; keep `buffer_write_bytes` internal.

### See also

- `buffer.slice`
- `buffer.push`

---

<a id="buffer.get"></a>
## `buffer.get`

<!--
id: buffer.get
api: buffer.get
previous: buffer.byte
previous: buffer_read_u8
-->

```vir
buffer.get(b: Buffer, offset: int) -> int
```

Reads one byte at `offset` (`0 ≤ offset < len`).

### Parameters

#### `b: Buffer`

Source buffer.

#### `offset: int`

Byte index from start of buffer contents.

### Returns

`int` — byte value `0…255`.

### Errors

Out of bounds → panic today (`buffer read out of bounds`).

### Semantics

Pairs with `buffer.set`. Does not grow.

### Example

```vir
let x = buffer.get(b, 0)
```

### Status

`proposed` — **present** as `buffer_read_u8`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_read_u8`.

### See also

- `buffer.set`
- `buffer.u32`

---

<a id="buffer.u32"></a>
## `buffer.u32`

<!--
id: buffer.u32
api: buffer.u32
previous: buffer_read_u32
-->

```vir
buffer.u32(b: Buffer, offset: int) -> int
```

Reads a **little-endian** u32 at `offset` (needs 4 bytes in range).

### Parameters

#### `b: Buffer`

Source buffer.

#### `offset: int`

Start byte index.

### Returns

`int` — decoded LE value.

### Errors

`offset + 4 > len` → panic today.

### Semantics

Pairs with `buffer.setU32`.

### Example

```vir
let n = buffer.u32(b, 0)
```

### Status

`proposed` — **present** as `buffer_read_u32`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_read_u32`.

### See also

- `buffer.setU32`
- `buffer.pushU32`

---

<a id="buffer.set"></a>
## `buffer.set`

<!--
id: buffer.set
api: buffer.set
previous: buffer_write_at
-->

```vir
buffer.set(b: Buffer, offset: int, value: int) -> void
```

Writes one byte at `offset` (in-bounds patch; does not extend `len`).

### Parameters

#### `b: Buffer`

Target buffer.

#### `offset: int`

Existing index (`offset < len`).

#### `value: int`

Byte to store.

### Returns

None.

### Errors

Out of bounds → panic today.

### Semantics

Does not append. Does not change `len`. No separate public `writeAt`.

### Example

```vir
buffer.set(b, 0, 0xFF)
```

### Status

`proposed` — **present** as `buffer_write_at`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_write_at`.

### See also

- `buffer.get`
- `buffer.setU32`

---

<a id="buffer.setU32"></a>
## `buffer.setU32`

<!--
id: buffer.setU32
api: buffer.setU32
previous: buffer_write_u32_at, buffer_patch_u32
-->

```vir
buffer.setU32(b: Buffer, offset: int, value: int) -> void
```

Writes a **little-endian** u32 at `offset` (in-bounds; does not extend `len`).

### Parameters

#### `b: Buffer`

Target buffer.

#### `offset: int`

Start index; requires four in-range bytes.

#### `value: int`

Value encoded LE.

### Returns

None.

### Errors

Out of bounds → panic today.

### Semantics

Merges `buffer_write_u32_at` and `buffer_patch_u32` into one public name.
Binary patching for codegen/emit use cases.

### Example

```vir
buffer.setU32(b, 4, 0x12345678)
```

### Status

`proposed` — **present** under two names; public is `setU32` only.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_write_u32_at`; drop public `buffer_patch_u32`.

### See also

- `buffer.u32`
- `buffer.set`

---

<a id="buffer.slice"></a>
## `buffer.slice`

<!--
id: buffer.slice
api: buffer.slice
previous: buffer_as_slice
-->

```vir
buffer.slice(b: Buffer) -> Slice
```

Borrowed view of the buffer’s current contents `[0, len)` — **not** capacity.

### Parameters

#### `b: Buffer`

Owner buffer.

### Returns

`Slice` — `(data, len)` pointing into `b`’s storage.

### Errors

None.

### Semantics

Canonical bridge used by I/O / `fs` contracts. Call as `buffer.slice(b)`, not
receiver `b.slice()`. Outstanding views are invalidated by reallocate / `free`
(see Ownership section).

No public synonym `buffer.bytes()`.

### Example

```vir
let view = buffer.slice(b)
fs.write(path, view)
```

### Status

`proposed` — **present** as `buffer_as_slice`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_as_slice`.

### See also

- [`slice.md`](slice.md)
- `buffer.write`

---

<a id="buffer.len"></a>
## `buffer.len`

<!--
id: buffer.len
api: buffer.len
previous: buffer_len
-->

```vir
buffer.len(b: Buffer) -> int
```

Number of **used** bytes (`len`), not capacity.

### Parameters

#### `b: Buffer`

Buffer to query.

### Returns

`int` — `≥ 0`.

### Errors

None.

### Example

```vir
let n = buffer.len(b)
```

### Status

`proposed` — **present** as `buffer_len`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_len`.

### See also

- `buffer.cap`
- `buffer.isEmpty`

---

<a id="buffer.cap"></a>
## `buffer.cap`

<!--
id: buffer.cap
api: buffer.cap
previous: buffer_cap
-->

```vir
buffer.cap(b: Buffer) -> int
```

Allocated capacity in bytes.

### Parameters

#### `b: Buffer`

Buffer to query.

### Returns

`int` — `≥ len`.

### Errors

None.

### Example

```vir
let c = buffer.cap(b)
```

### Status

`proposed` — **present** as `buffer_cap`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_cap`.

### See also

- `buffer.reserve`
- `buffer.len`

---

<a id="buffer.isEmpty"></a>
## `buffer.isEmpty`

<!--
id: buffer.isEmpty
api: buffer.isEmpty
previous: buffer_is_empty
-->

```vir
buffer.isEmpty(b: Buffer) -> bool
```

`true` when `len == 0`.

### Parameters

#### `b: Buffer`

Buffer to query.

### Returns

`bool`

### Errors

None.

### Semantics

Predicate — not the constructor `buffer.empty()`.

### Example

```vir
if buffer.isEmpty(b) do
    io.println("empty")
end
```

### Status

`proposed` — **present** as `buffer_is_empty`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_is_empty`.

### See also

- `buffer.empty`
- `buffer.len`

---

<a id="buffer.clear"></a>
## `buffer.clear`

<!--
id: buffer.clear
api: buffer.clear
previous: buffer_clear
-->

```vir
buffer.clear(b: Buffer) -> void
```

Sets `len = 0` without freeing capacity.

### Parameters

#### `b: Buffer`

Target buffer.

### Returns

None.

### Errors

None.

### Semantics

Does not `free`. Content past the new `len` is unspecified for reads.
Slices that covered old contents are logically obsolete (length shrink).

### Example

```vir
buffer.clear(b)
```

### Status

`proposed` — **present** as `buffer_clear`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_clear`.

### See also

- `buffer.truncate`
- `buffer.free`

---

<a id="buffer.truncate"></a>
## `buffer.truncate`

<!--
id: buffer.truncate
api: buffer.truncate
previous: buffer_truncate
-->

```vir
buffer.truncate(b: Buffer, new_len: int) -> void
```

If `new_len < len`, sets `len = new_len`. Does not grow.

### Parameters

#### `b: Buffer`

Target buffer.

#### `new_len: int`

Desired length.

### Returns

None.

### Errors

None (current impl ignores `new_len ≥ len`).

### Semantics

Current source only shrinks; it does not extend or panic when `new_len > len`.

### Example

```vir
buffer.truncate(b, 4)
```

### Status

`proposed` — **present** as `buffer_truncate`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_truncate`.

### See also

- `buffer.clear`
- `buffer.len`

---

<a id="buffer.reserve"></a>
## `buffer.reserve`

<!--
id: buffer.reserve
api: buffer.reserve
previous: buffer_reserve
-->

```vir
buffer.reserve(b: Buffer, additional: int) -> void
```

Ensures capacity for at least `len + additional` bytes (may reallocate).

### Parameters

#### `b: Buffer`

Target buffer.

#### `additional: int`

Extra bytes needed beyond current `len`.

### Returns

None.

### Errors

Alloc failure per runtime.

### Semantics

**May invalidate** all `Slice` views previously returned by `buffer.slice(b)`.

### Example

```vir
buffer.reserve(b, 4096)
```

### Status

`proposed` — **present** as `buffer_reserve`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_reserve` / internal `buffer_grow`.

### See also

- `buffer.cap`
- `buffer.slice`

---

<a id="buffer.free"></a>
## `buffer.free`

<!--
id: buffer.free
api: buffer.free
previous: buffer_free
-->

```vir
buffer.free(b: Buffer) -> void
```

Releases owned storage. Buffer must not be used afterward.

### Parameters

#### `b: Buffer`

Buffer to release (`ref` in source; zeroes `data`/`len`/`cap` today).

### Returns

None.

### Errors

None.

### Semantics

Public while explicit ownership is required. Invalidates all borrowed slices.
Do not design around a future automatic destructor in this registry pass.

### Example

```vir
buffer.free(b)
```

### Status

`proposed` — **present** as `buffer_free`.

### Implementation mapping

`vir/mem/buffer.vri` → `buffer_free`.

### See also

- `buffer.new`
- `buffer.slice`

---

## Implementation readiness

**Design status: closed** (B1). Explicit `free` + move/invalidate rules locked.
No `.vri` until authorized (Q5).
