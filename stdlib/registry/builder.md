---
module: builder
title: StringBuilder
summary: Mutable UTF-8 text construction — namespace builder.*; always-valid UTF-8 invariant.
source:
  - name: builder
    path: vir/str/builder.vri
status: closed
notes: >-
  Namespace-only builder.*. Always-valid UTF-8 invariant; string() is snapshot via
  trusted internal path (not public fromBytes). write/push/insert codepoint-first;
  len=codepoints, bytes=bytes. Raw byte/cstr/newline/numeric appends out of public
  core. Compiler StringBuilder bootstrap out of registry ABI. No .vri until map applied.
---

# StringBuilder

Mutable **UTF-8 text** construction. Public API is namespace-only:
`builder.<op>(…)`.

> **A valid `StringBuilder` always contains a valid UTF-8 sequence. Every
> public mutation must preserve this invariant.**

```text
Buffer
  arbitrary bytes
       │
       │ UTF-8 construction
       ▼
StringBuilder ── builder.string ──→ string
 valid UTF-8                       valid UTF-8
```

Because the invariant holds end-to-end, `builder.string` does **not** need
public re-validation as a safety net. It uses an **internal trusted** string
construction path — never the public unchecked misuse of
[`string.fromBytes`](string.md).

```vir
let sb = builder.new()
builder.write(sb, "hello")
builder.push(sb, 0x20AC)          # €
let s = builder.string(sb)        # snapshot; sb still usable
builder.write(sb, "!")
```

Not nested under `string.builder.*`. `StringBuilder` is its own owned mutable
abstraction (like [`Buffer`](buffer.md)), not a method group on immutable
`string`.

## Boundary

| In `builder` | Not in `builder` |
|---|---|
| Always-valid UTF-8 construction | Public raw byte append (`sb_append_byte`) |
| `write` / `push` / `insert` / `repeat` | Public `append_cstr` / `newline` |
| Snapshot `string` | Consuming zero-copy `finish` *(not this pass)* |
| `len` (codepoints) / `bytes` / `isEmpty` | Treating `len` as `Buffer.len` |
| `clear` / `free` | Stable `writeInt*` — **planned** (see below) |
| | `string.builder.*` nesting |
| | Documenting compiler `virc` / `string_rt` representation |
| | Public `byteInsert` *(optional later)* |

## UTF-8 invariant (closed)

Every public mutation leaves the builder holding a well-formed UTF-8 sequence
(possibly empty).

| Op | Why safe |
|---|---|
| `write` / `repeat` / `insert` | Source is valid `string` |
| `push` | Encodes one valid Unicode scalar → UTF-8 |
| `clear` | Empty is valid UTF-8 |
| `string` | Trusted copy of invariant contents |

Public **must not** expose arbitrary byte injection. Internal encoder helpers
may write bytes only after the sequence is known valid.

Invalid Unicode scalar for `push` (surrogate / out of range): reject per
`is_valid_codepoint` (and related `unicode` helpers) when wired; otherwise
**panic** — never silently corrupt the builder. Do not invent a new soft-error
type in this pass.

## Capacity (closed)

```vir
builder.new()
builder.withCap(1024)
```

Capacity is **UTF-8 storage bytes** (backing [`Buffer`](buffer.md)), not
codepoints.

Aligned with [`vec`](vec.md) construction style (`new` / `withCap`) — **not**
`buffer.empty` / `builder.empty`.

Default capacity for `new` follows current `sb_new` (64 bytes today).

## Finish: snapshot (closed)

```vir
let s = builder.string(sb)
```

Creates a new immutable `string` from current contents. The builder **remains
usable** afterward:

```text
builder = "abc"
s1 = builder.string()     # "abc"
builder.write("def")
s1                        # "abc"
builder contents          # "abcdef"
```

```text
sb_build + sb_to_string  →  builder.string   (one name)
```

No consuming / zero-copy finish in this pass. A future `builder.finish` may be
designed separately.

```text
public Slice          → string.fromBytes   (validate)
StringBuilder         → builder.string     (trusted internal)
```

## Indexing (closed)

Text core is **codepoint-first**, matching [`string`](string.md):

| | `string` | `builder` |
|---|---|---|
| Codepoints | `len` | `len` |
| Bytes | `bytes` | `bytes` |
| Empty | `isEmpty` | `isEmpty` |

```vir
builder.len(sb)       # codepoint count
builder.bytes(sb)     # UTF-8 byte count (= Buffer len)
builder.isEmpty(sb)
```

Today’s `sb_len` returns byte length → migrates to **`builder.bytes`**.
`builder.len` is **new** (may cache codepoint count later; do not weaken
semantics for today’s byte-only convenience).

### `insert` (closed)

```vir
builder.insert(sb, index, s)
```

`index` is a **codepoint** index (not byte offset). Implementation finds the
byte boundary, then shifts/copies.

```text
"A你B"   codepoints 0 1 2
insert(2, "好") → "A你好B"
```

OOB index / invalid range → **panic** (same family as `string.slice` /
`string.char`). Optional later: `builder.byteInsert` for low-level byte ops —
**not** in this surface.

## Ownership (closed)

`StringBuilder` is a **Move** type. Mutating APIs take `ref sb` in source today.

```vir
builder.clear(sb)   # content empty; capacity retained; still valid
builder.free(sb)    # release Buffer; do not use until reinitialized
```

Same ownership story as `Buffer`: explicit `free` while the memory model
requires it.

## Numeric writers (planned)

Target — direct append, **no** intermediate `string`:

```text
builder.writeInt(sb, n)
builder.writeIntRadix(sb, n, base)   # base ∈ {2,8,10,16}; digits only, no prefix
builder.writeBool(sb, value)
builder.writeFloat(sb, value, prec)  # after format.float stable
```

No separate `writeHex` / `writeBin` / `writeOct` — use `writeIntRadix`.
Errors / allocator behavior follow `builder.write`. Until implemented:

```vir
builder.write(sb, format.int(n))
builder.write(sb, format.bool(value))
```

Legacy `sb_append_i64` / `f64` / `bool` → migrate to these writers.

## Compiler bootstrap (closed)

Registry SSOT:

```text
vir/str/builder.vri  →  builder.md
```

Compiler / `string_rt` `StringBuilder` is bootstrap implementation. Registry
does **not** document its `buf/len/cap` layout or force ABI-identical
representation.

**Observable semantics** of equivalent operations should conform. Unlike
[`IoError`](error.md) (public error payload), bootstrap builder need not match
stdlib field layout.

## Public surface (closed)

```text
builder
├── new
├── withCap
│
├── write
├── push
├── insert
├── repeat
│
├── string
│
├── len
├── bytes
├── isEmpty
│
├── clear
└── free
```

Internal / non-canonical:

```text
sb_append_cstr
sb_append_byte
sb_append_newline
sb_append_i64 / sb_append_f64 / sb_append_bool   # format audit
sb_to_string                                      # merge into string
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `sb_new` | `builder.new` | **rename** |
| `sb_with_cap` | `builder.withCap` | **rename** · cap = bytes |
| `sb_append` | `builder.write` | **rename** |
| `sb_append_cstr` | — | **internal** |
| `sb_append_char` | `builder.push` | **rename** · reject invalid scalar |
| `sb_append_byte` | — | **internal** |
| `sb_append_newline` | — | **internal**; public uses `write("\n")` |
| `sb_append_repeat` | `builder.repeat` | **rename** · repeat `string` |
| `sb_insert` (byte pos) | `builder.insert` | **rename** · **codepoint** index |
| `sb_build` | `builder.string` | **rename** · trusted snapshot |
| `sb_to_string` | `builder.string` | **merge** |
| `sb_len` | `builder.bytes` | **rename** (was byte len) |
| — | `builder.len` | **new** · codepoints |
| — | `builder.isEmpty` | **new** |
| `sb_clear` | `builder.clear` | **rename** |
| `sb_free` | `builder.free` | **rename** |
| `sb_append_i64` / `f64` / `bool` | — | **out** · format audit |
| public `sb_*` aliases | — | **remove** long-term |

### Implementation debt

1. **`len` / `isEmpty`** — add codepoint count (cache optional).
2. **`insert`** — switch public index to codepoints; panic OOB.
3. **`push`** — reject invalid scalars (no corrupt UTF-8).
4. **`string`** — trusted internal construct; stop relying on public
   validating/non-validating `fromBytes` as the user path.
5. Drop public exposure of byte/cstr/newline appends.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `builder.new` | `builder.new` | `builder.new() -> StringBuilder` | proposed |
| `builder.withCap` | `builder.withCap` | `builder.withCap(cap: int) -> StringBuilder` | proposed |
| `builder.write` | `builder.write` | `builder.write(sb, s: string)` | proposed |
| `builder.push` | `builder.push` | `builder.push(sb, cp: int)` | proposed |
| `builder.insert` | `builder.insert` | `builder.insert(sb, index: int, s: string)` | proposed |
| `builder.repeat` | `builder.repeat` | `builder.repeat(sb, s: string, count: int)` | proposed |
| `builder.string` | `builder.string` | `builder.string(sb) -> string` | proposed |
| `builder.len` | `builder.len` | `builder.len(sb) -> int` | proposed |
| `builder.bytes` | `builder.bytes` | `builder.bytes(sb) -> int` | proposed |
| `builder.isEmpty` | `builder.isEmpty` | `builder.isEmpty(sb) -> bool` | proposed |
| `builder.clear` | `builder.clear` | `builder.clear(sb)` | proposed |
| `builder.free` | `builder.free` | `builder.free(sb)` | proposed |

Mutating calls take `ref` in source; docs show `sb: StringBuilder`.

---

<a id="builder.new"></a>
## `builder.new`

<!--
id: builder.new
api: builder.new
previous: sb_new
-->

```vir
builder.new() -> StringBuilder
```

Empty builder with default byte capacity (64 today).

### Status

`proposed` — **present** as `sb_new`.

### Implementation mapping

`vir/str/builder.vri` → `sb_new`.

### See also

- `builder.withCap`

---

<a id="builder.withCap"></a>
## `builder.withCap`

<!--
id: builder.withCap
api: builder.withCap
previous: sb_with_cap
-->

```vir
builder.withCap(cap: int) -> StringBuilder
```

Empty builder; `cap` is initial **byte** capacity of the backing `Buffer`.

### Status

`proposed` — **present** as `sb_with_cap`.

### Implementation mapping

`vir/str/builder.vri` → `sb_with_cap`.

---

<a id="builder.write"></a>
## `builder.write`

<!--
id: builder.write
api: builder.write
previous: sb_append
-->

```vir
builder.write(sb: StringBuilder, s: string)
```

Append UTF-8 bytes of `s`. Preserves invariant.

### Status

`proposed` — **present** as `sb_append`.

### Implementation mapping

`vir/str/builder.vri` → `sb_append`.

### See also

- `builder.push`
- `builder.repeat`

---

<a id="builder.push"></a>
## `builder.push`

<!--
id: builder.push
api: builder.push
previous: sb_append_char
-->

```vir
builder.push(sb: StringBuilder, cp: int)
```

UTF-8-encode Unicode scalar `cp` and append.

### Semantics

Unit is a **codepoint/scalar**, not a raw byte (`buffer.push` remains one
byte on binary buffers). Invalid scalar → reject/panic; never corrupt.

### Status

`proposed` — **present** as `sb_append_char`; tighten invalid-scalar handling.

### Implementation mapping

`vir/str/builder.vri` → `sb_append_char`.

---

<a id="builder.insert"></a>
## `builder.insert`

<!--
id: builder.insert
api: builder.insert
previous: sb_insert
-->

```vir
builder.insert(sb: StringBuilder, index: int, s: string)
```

Insert `s` at **codepoint** index `index`. OOB → panic.

### Status

`proposed` — **present** with **byte** `pos` — must migrate to codepoints.

### Implementation mapping

`vir/str/builder.vri` → `sb_insert` (behavior change).

### See also

- `string.slice` / `string.char` — codepoint-first text lane

---

<a id="builder.repeat"></a>
## `builder.repeat`

<!--
id: builder.repeat
api: builder.repeat
previous: sb_append_repeat
-->

```vir
builder.repeat(sb: StringBuilder, s: string, count: int)
```

Append `s` repeated `count` times (`count == 0` → no-op). Source is valid
`string` → invariant preserved.

### Status

`proposed` — **present** as `sb_append_repeat` (repeat string, not a bare char).

### Implementation mapping

`vir/str/builder.vri` → `sb_append_repeat`.

---

<a id="builder.string"></a>
## `builder.string`

<!--
id: builder.string
api: builder.string
previous: sb_build
-->

```vir
builder.string(sb: StringBuilder) -> string
```

Snapshot current contents to a new `string`. Builder remains usable.

### Semantics

Trusted internal construction from invariant UTF-8. Not
`string.fromBytes` on an arbitrary public `Slice`.

### Status

`proposed` — **present** as `sb_build` / `sb_to_string` → one name.

### Implementation mapping

`vir/str/builder.vri` → `sb_build`; drop public `sb_to_string`.

### See also

- [`string.fromBytes`](string.md)

---

<a id="builder.len"></a>
## `builder.len`

<!--
id: builder.len
api: builder.len
-->

```vir
builder.len(sb: StringBuilder) -> int
```

Unicode **codepoint** count of current contents. Not byte length.

### Status

`proposed` — **missing**; today’s `sb_len` is bytes → `builder.bytes`.

### Implementation mapping

New; may scan or cache.

### See also

- `builder.bytes`
- [`string.len`](string.md)

---

<a id="builder.bytes"></a>
## `builder.bytes`

<!--
id: builder.bytes
api: builder.bytes
previous: sb_len
-->

```vir
builder.bytes(sb: StringBuilder) -> int
```

UTF-8 **byte** length of current contents.

### Status

`proposed` — **present** as `sb_len` (byte semantics kept under new name).

### Implementation mapping

`vir/str/builder.vri` → `sb_len`.

---

<a id="builder.isEmpty"></a>
## `builder.isEmpty`

<!--
id: builder.isEmpty
api: builder.isEmpty
-->

```vir
builder.isEmpty(sb: StringBuilder) -> bool
```

True when there is no content (`bytes == 0`).

### Status

`proposed` — **missing**.

### Implementation mapping

New (or `builder.bytes(sb) == 0`).

---

<a id="builder.clear"></a>
## `builder.clear`

<!--
id: builder.clear
api: builder.clear
previous: sb_clear
-->

```vir
builder.clear(sb: StringBuilder)
```

Set content empty; retain capacity; builder remains valid.

### Status

`proposed` — **present** as `sb_clear`.

### Implementation mapping

`vir/str/builder.vri` → `sb_clear`.

---

<a id="builder.free"></a>
## `builder.free`

<!--
id: builder.free
api: builder.free
previous: sb_free
-->

```vir
builder.free(sb: StringBuilder)
```

Release owned `Buffer`. Do not use afterward until reinitialized.

### Status

`proposed` — **present** as `sb_free`.

### Implementation mapping

`vir/str/builder.vri` → `sb_free`.

---

## Implementation readiness

Builder map is closed for this refactor:

1. Namespace `builder.*`; drop long-term public `sb_*`.
2. Preserve always-valid UTF-8; no public byte injection.
3. `insert` + `len` codepoint-first; `bytes` for byte length.
4. `string` = trusted snapshot; merge `to_string`.
5. Defer numeric appends to format audit.

See [`fmt`](fmt.md), [`format`](format.md), [`parse`](parse.md).
`writeInt*` planned above. `builder.push` uses [`unicode.valid`](unicode.md).
