---
module: string
title: String
summary: Immutable UTF-8 text — thin namespace string.*; two-lane char/byte indexing.
source:
  - name: string
    path: vir/str/string.vri
status: stable
notes: >-
  Namespace-only string.*. No public str_* aliases. No string.eq (use ==).
  find = codepoint index; byteFind = byte. fromBytes strict UTF-8 → Result of (string).
  lower/upper/trim Unicode-aware (ASCII-only impl = debt). Parse/format → parse.md / format.md.
  Builder / unicode pack = separate registries. No .vri until map applied.
---

# String

Immutable UTF-8 **text**. Public API is namespace-only: `string.<op>(…)`.

```text
Slice   = borrowed binary view
Buffer  = owned binary storage
string  = text (UTF-8)
```

No public type named `bytes`. Binary I/O stays on [`buffer`](buffer.md) /
[`slice`](slice.md) / [`fs`](fs.md); text is this module plus explicit
`fs.text` / `reader.line` convenience layers.

```vir
let n = string.len(s)          # codepoints
let b = string.bytes(s)        # UTF-8 bytes
let i = string.find(s, "→")    # Option of (int)  # codepoint index
let t = string.slice(s, 0, i)  # codepoint range → new string
```

`str_*` free names are implementation / migration only — not long-lived public
aliases.

## Boundary

| In `string` | Not in `string` |
|---|---|
| Immutable UTF-8 text ops | Public `str_*` aliases |
| Two-lane indexing: codepoint vs byte | Grapheme count / clusters → [`grapheme`](grapheme.md) *(later)* |
| Strict `fromBytes` → `Result of (string)` | Minting invalid UTF-8 |
| Search / slice / case / trim / split-join | `string.eq` — use language `==` |
| Explicit `free` (current ownership) | Parse/format → [`parse`](parse.md) / [`format`](format.md) |
| | Mutable build → [`builder`](builder.md) |
| | NFC/NFD / collation / encode bridges — separate registries |
| | Public `asSlice` until backing lifetime is locked |
| | `string.fromBuffer` — use `buffer.slice` → `fromBytes` |

## Binary ↔ text (closed)

```text
Slice  ──validate+copy──→ string     via string.fromBytes
Buffer ──slice──────────→ Slice ──→ string
```

Canonical binary→text entry:

```vir
string.fromBytes(slice) -> Result of (string)
```

No public `string.fromBuffer`.

Text→binary:

| Bridge | Status |
|---|---|
| `string.asSlice(s) -> Slice` | **not public** until UTF-8 storage lifetime is defined |
| `string.toBuffer(s) -> Buffer` | optional later; owned copy — not required for symmetry |

Unchecked “bytes already valid” constructors may exist **internal only**.

## Indexing model (closed)

Two lanes. Names stay short and paired:

| Lane | Count | Element | Range |
|---|---|---|---|
| Codepoint | `string.len` | `string.char` | `string.slice` |
| Byte | `string.bytes` | `string.byte` | `string.byteSlice` |

```text
string.len(s)           # Unicode codepoint count — NOT grapheme count
string.bytes(s)         # UTF-8 byte count

string.char(s, i)       # codepoint at codepoint index i
string.byte(s, i)       # byte at byte index i

string.slice(s, a, b)       # codepoint half-open [a, b) → string
string.byteSlice(s, a, b)   # byte half-open [a, b) → string
```

Grapheme is a **separate** abstraction (`grapheme.md`).

### Bounds / panic (closed)

Out-of-range codepoint or byte indexes, and invalid `slice` / `byteSlice`
ranges (`from > to` or `to > len`), follow the same **panic** style as
[`slice.sub`](slice.md) — not `Result`.

### `byteSlice` UTF-8 boundary invariant (closed)

`string.byteSlice` takes **byte** offsets, but `start` and `end` **must** lie
on UTF-8 codepoint boundaries.

Cutting mid-codepoint must **not** produce an invalid `string`. Treat as
bounds-style failure (**panic**), same family as OOB index.

Valid `string` values always remain well-formed UTF-8.

## Search (closed)

```text
string.find(s, needle)      → Option of (int)  # codepoint index
string.byteFind(s, needle)  → Option of (int)  # byte index
```

Current `str_find` returning a **byte** index is **implementation debt**.
Contract does **not** follow that bug.

Engine may stay Two-Way on bytes:

```text
byteFind → byte offset directly
find     → byteFind then byte offset → codepoint offset
```

Empty needle → `Some(0)` (both lanes), matching today’s empty-match behavior
unless a later audit changes it deliberately.

`string.contains` is true iff `find` is `Some`.

## Case and trim (closed)

```text
string.lower / string.upper   → Unicode-aware case conversion
string.trim / trimStart / trimEnd → Unicode whitespace (stdlib Unicode data/version)
```

ASCII-only behavior in current `string.vri` is **non-conforming
implementation debt**, not the public contract. Fast ASCII helpers may remain
internal.

## Equality (closed)

User-facing equality is language-level:

```vir
a == b
```

`str_eq` may back the compiler/runtime. **No** public `string.eq`.
(`Slice` keeps `slice.eq` because it is not a language-level value type.)

`string.cmp` stays for ordering (`-1` / `0` / `1`).

## Ownership (closed)

`string` is immutable; transforming ops allocate a new `string`.

`string.free` remains public while ownership still requires explicit free
(aligned with `buffer.free` / current model). Refinement of language ownership
may retire it later — out of this map’s rename scope.

Heavy incremental construction → [`builder`](builder.md), not `string.*`.

## Parse / format (out of this pass)

Not in the closed core surface:

```text
str_to_i64 / str_to_f64 / i64_to_str / f64_to_str
```

Audit later as conversion/parse API (`Option` vs `Result`, error kind, radix,
formatting). Presence in `string.vri` today is not a reason to lock them here.

## Unicode pack (separate registries)

Do **not** fold into core `string`:

```text
builder.md      ← **closed**
char.md … collation.md ← **closed** (unicode pack)
```

Physical modules may remain `str.unicode`, …; public namespaces are the
registry names above.

## Public surface (closed)

```text
string
├── empty
├── fromBytes
│
├── len
├── bytes
├── isEmpty
│
├── char
├── byte
├── slice
├── byteSlice
│
├── cmp
│
├── concat
├── contains
├── find
├── byteFind
├── startsWith
├── endsWith
│
├── trim
├── trimStart
├── trimEnd
├── lower
├── upper
├── replace
├── repeat
│
├── split
├── join
└── free
```

## Migration map

| Current | Public | Action |
|---|---|---|
| `str_empty` | `string.empty` | **rename** |
| `str_new` | — / language literal | **internal** or language path; not required on thin surface |
| `str_from_bytes` | `string.fromBytes` | **rename** + **strict UTF-8** → `Result of (string)` |
| `str_len` | `string.len` | **rename** |
| `str_byte_len` | `string.bytes` | **rename** |
| `str_is_empty` | `string.isEmpty` | **rename** |
| `str_char_at` | `string.char` | **rename** |
| `str_byte_at` | `string.byte` | **rename** |
| `str_cmp` | `string.cmp` | **rename** |
| `str_eq` | — | **internal** / `==` backing |
| `str_slice` | `string.slice` | **rename** |
| `str_slice_bytes` | `string.byteSlice` | **rename** + UTF-8 boundary check |
| `str_concat` | `string.concat` | **rename** |
| `str_contains` | `string.contains` | **rename** |
| `str_find` | `string.find` + `string.byteFind` | **split** · find = codepoint |
| `str_starts_with` | `string.startsWith` | **rename** |
| `str_ends_with` | `string.endsWith` | **rename** |
| `str_to_lower` | `string.lower` | **rename** · Unicode contract |
| `str_to_upper` | `string.upper` | **rename** · Unicode contract |
| `str_trim` | `string.trim` | **rename** · Unicode whitespace |
| `str_trim_start` | `string.trimStart` | **rename** |
| `str_trim_end` | `string.trimEnd` | **rename** |
| `str_replace` | `string.replace` | **rename** · replace native stub |
| `str_repeat` | `string.repeat` | **rename** |
| `str_split` | `string.split` | **rename** · replace native stub |
| `str_join` | `string.join` | **rename** · replace native stub |
| `str_free` | `string.free` | **rename** |
| `str_to_i64` / `str_to_f64` / `i64_to_str` / `f64_to_str` | — | **out** this pass |
| `utf8_*` / `is_ascii_whitespace` | — | **internal** |
| public `str_*` aliases | — | **remove** long-term |

### Implementation debt (must fix for conforming)

1. **`find` / `byteFind`** — split lanes; `find` returns codepoint index.
2. **`fromBytes`** — validate UTF-8; never mint invalid `string`.
3. **`byteSlice`** — reject mid-codepoint cuts (panic).
4. **`lower` / `upper` / `trim*`** — Unicode semantics (ASCII-only = debt).
5. **`replace` / `split` / `join`** — real Vir impl; not conforming while `native_*` stubs.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `string.empty` | `string.empty` | `string.empty() -> string` | proposed |
| `string.fromBytes` | `string.fromBytes` | `string.fromBytes(s: Slice) -> Result of (string)` | proposed |
| `string.len` | `string.len` | `string.len(s: string) -> int` | proposed |
| `string.bytes` | `string.bytes` | `string.bytes(s: string) -> int` | proposed |
| `string.isEmpty` | `string.isEmpty` | `string.isEmpty(s: string) -> bool` | proposed |
| `string.char` | `string.char` | `string.char(s: string, i: int) -> int` | proposed |
| `string.byte` | `string.byte` | `string.byte(s: string, i: int) -> int` | proposed |
| `string.slice` | `string.slice` | `string.slice(s, from, to: int) -> string` | proposed |
| `string.byteSlice` | `string.byteSlice` | `string.byteSlice(s, from, to: int) -> string` | proposed |
| `string.cmp` | `string.cmp` | `string.cmp(a: string, b: string) -> int` | proposed |
| `string.concat` | `string.concat` | `string.concat(a: string, b: string) -> string` | proposed |
| `string.contains` | `string.contains` | `string.contains(s, needle: string) -> bool` | proposed |
| `string.find` | `string.find` | `string.find(s, needle: string) -> Option of (int)` | proposed |
| `string.byteFind` | `string.byteFind` | `string.byteFind(s, needle: string) -> Option of (int)` | proposed |
| `string.startsWith` | `string.startsWith` | `string.startsWith(s, prefix: string) -> bool` | proposed |
| `string.endsWith` | `string.endsWith` | `string.endsWith(s, suffix: string) -> bool` | proposed |
| `string.trim` | `string.trim` | `string.trim(s: string) -> string` | proposed |
| `string.trimStart` | `string.trimStart` | `string.trimStart(s: string) -> string` | proposed |
| `string.trimEnd` | `string.trimEnd` | `string.trimEnd(s: string) -> string` | proposed |
| `string.lower` | `string.lower` | `string.lower(s: string) -> string` | proposed |
| `string.upper` | `string.upper` | `string.upper(s: string) -> string` | proposed |
| `string.replace` | `string.replace` | `string.replace(s, old, new: string) -> string` | proposed |
| `string.repeat` | `string.repeat` | `string.repeat(s: string, n: int) -> string` | proposed |
| `string.split` | `string.split` | `string.split(s, delim: string) -> Vec` | proposed |
| `string.join` | `string.join` | `string.join(parts: Vec, sep: string) -> string` | proposed |
| `string.free` | `string.free` | `string.free(s: string)` | proposed |

`Result` / `Option` / `Vec` payload types follow language forms; error on
`fromBytes` uses I/O-relevant / data kind — prefer
`ErrorKind.InvalidData` (see [`error.md`](error.md)). Exact `Err` payload type
(`Error` vs dedicated decode error) follows source when implemented — must be
recoverable.

---

<a id="string.empty"></a>
## `string.empty`

<!--
id: string.empty
api: string.empty
previous: str_empty
-->

```vir
string.empty() -> string
```

Empty UTF-8 string.

### Status

`proposed` — **present** as `str_empty`.

### Implementation mapping

`vir/str/string.vri` → `str_empty`.

---

<a id="string.fromBytes"></a>
## `string.fromBytes`

<!--
id: string.fromBytes
api: string.fromBytes
previous: str_from_bytes
-->

```vir
string.fromBytes(s: Slice) -> Result of (string)
```

Validate `s` as UTF-8, copy into a new `string`.

### Returns

`Ok(string)` if valid; `Err(…)` with `ErrorKind.InvalidData` (or equivalent
recoverable payload) if not.

### Semantics

Never returns an invalid `string`. Unchecked path = **internal only**.

```text
Slice ──validate+copy──→ string
```

### Status

`proposed` — **present** as trusting `str_from_bytes`; must gain validation +
`Result`.

### Implementation mapping

`vir/str/string.vri` → `str_from_bytes` (behavior change).

### See also

- [`error.md`](error.md) — `InvalidData`
- [`slice.md`](slice.md) / [`buffer.md`](buffer.md)
- `fs.text`

---

<a id="string.len"></a>
## `string.len`

<!--
id: string.len
api: string.len
previous: str_len
-->

```vir
string.len(s: string) -> int
```

Unicode **codepoint** count. Not grapheme count; not byte count.

### Status

`proposed` — **present** as `str_len`.

### Implementation mapping

`vir/str/string.vri` → `str_len`.

### See also

- `string.bytes`
- grapheme count → `grapheme` registry

---

<a id="string.bytes"></a>
## `string.bytes`

<!--
id: string.bytes
api: string.bytes
previous: str_byte_len
-->

```vir
string.bytes(s: string) -> int
```

UTF-8 **byte** length.

### Status

`proposed` — **present** as `str_byte_len`.

### Implementation mapping

`vir/str/string.vri` → `str_byte_len`.

---

<a id="string.isEmpty"></a>
## `string.isEmpty`

<!--
id: string.isEmpty
api: string.isEmpty
previous: str_is_empty
-->

```vir
string.isEmpty(s: string) -> bool
```

True when byte length is `0`.

### Status

`proposed` — **present** as `str_is_empty`.

### Implementation mapping

`vir/str/string.vri` → `str_is_empty`.

---

<a id="string.char"></a>
## `string.char`

<!--
id: string.char
api: string.char
previous: str_char_at
-->

```vir
string.char(s: string, i: int) -> int
```

Codepoint at **codepoint** index `i`. OOB → panic.

### Status

`proposed` — **present** as `str_char_at`.

### Implementation mapping

`vir/str/string.vri` → `str_char_at`.

### See also

- `string.byte`

---

<a id="string.byte"></a>
## `string.byte`

<!--
id: string.byte
api: string.byte
previous: str_byte_at
-->

```vir
string.byte(s: string, i: int) -> int
```

Byte at **byte** index `i` (`0…255`). OOB → panic.

### Status

`proposed` — **present** as `str_byte_at`.

### Implementation mapping

`vir/str/string.vri` → `str_byte_at`.

---

<a id="string.slice"></a>
## `string.slice`

<!--
id: string.slice
api: string.slice
previous: str_slice
-->

```vir
string.slice(s: string, from: int, to: int) -> string
```

New string for codepoint range half-open `[from, to)`. Invalid range → panic.

### Status

`proposed` — **present** as `str_slice`.

### Implementation mapping

`vir/str/string.vri` → `str_slice`.

### See also

- `string.byteSlice`

---

<a id="string.byteSlice"></a>
## `string.byteSlice`

<!--
id: string.byteSlice
api: string.byteSlice
previous: str_slice_bytes
-->

```vir
string.byteSlice(s: string, from: int, to: int) -> string
```

New string for **byte** range half-open `[from, to)`.

### Semantics

`from` and `to` must be UTF-8 boundaries. Mid-codepoint cut → panic.
OOB / `from > to` → panic. Result is always valid UTF-8.

### Status

`proposed` — **present** as `str_slice_bytes` without boundary check — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_slice_bytes`.

---

<a id="string.cmp"></a>
## `string.cmp`

<!--
id: string.cmp
api: string.cmp
previous: str_cmp
-->

```vir
string.cmp(a: string, b: string) -> int
```

Lexicographic compare on UTF-8 bytes: `<0` / `0` / `>0`.

Not collation (see `collation` registry). Equality for users: `a == b`.

### Status

`proposed` — **present** as `str_cmp`.

### Implementation mapping

`vir/str/string.vri` → `str_cmp`.

---

<a id="string.concat"></a>
## `string.concat`

<!--
id: string.concat
api: string.concat
previous: str_concat
-->

```vir
string.concat(a: string, b: string) -> string
```

Allocate concatenation `a ‖ b`.

### Status

`proposed` — **present** as `str_concat`.

### Implementation mapping

`vir/str/string.vri` → `str_concat`.

### See also

- [`builder`](builder.md) for many appends

---

<a id="string.contains"></a>
## `string.contains`

<!--
id: string.contains
api: string.contains
previous: str_contains
-->

```vir
string.contains(s: string, needle: string) -> bool
```

True iff `string.find(s, needle)` is `Some`.

### Status

`proposed` — **present** as `str_contains`.

### Implementation mapping

`vir/str/string.vri` → `str_contains`.

---

<a id="string.find"></a>
## `string.find`

<!--
id: string.find
api: string.find
previous: str_find
-->

```vir
string.find(s: string, needle: string) -> Option of (int)
```

First occurrence of `needle` as **codepoint** index, or `None`.

### Semantics

Must not return a raw byte offset. Impl may `byteFind` then convert.

### Status

`proposed` — **present** but **wrong lane** (byte index) — must fix.

### Implementation mapping

`vir/str/string.vri` → part of `str_find` split.

### See also

- `string.byteFind`
- [`slice.find`](slice.md) — byte search on binary views

---

<a id="string.byteFind"></a>
## `string.byteFind`

<!--
id: string.byteFind
api: string.byteFind
previous: str_find
-->

```vir
string.byteFind(s: string, needle: string) -> Option of (int)
```

First occurrence as **byte** index, or `None`.

### Status

`proposed` — new public split from today’s `str_find` engine.

### Implementation mapping

`vir/str/string.vri` → Two-Way path of `str_find`.

---

<a id="string.startsWith"></a>
## `string.startsWith`

<!--
id: string.startsWith
api: string.startsWith
previous: str_starts_with
-->

```vir
string.startsWith(s: string, prefix: string) -> bool
```

### Status

`proposed` — **present** as `str_starts_with`.

### Implementation mapping

`vir/str/string.vri` → `str_starts_with`.

---

<a id="string.endsWith"></a>
## `string.endsWith`

<!--
id: string.endsWith
api: string.endsWith
previous: str_ends_with
-->

```vir
string.endsWith(s: string, suffix: string) -> bool
```

### Status

`proposed` — **present** as `str_ends_with`.

### Implementation mapping

`vir/str/string.vri` → `str_ends_with`.

---

<a id="string.trim"></a>
## `string.trim`

<!--
id: string.trim
api: string.trim
previous: str_trim
-->

```vir
string.trim(s: string) -> string
```

Strip leading and trailing **Unicode** whitespace.

### Status

`proposed` — **present** ASCII-only — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_trim`.

---

<a id="string.trimStart"></a>
## `string.trimStart`

<!--
id: string.trimStart
api: string.trimStart
previous: str_trim_start
-->

```vir
string.trimStart(s: string) -> string
```

### Status

`proposed` — ASCII-only today — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_trim_start`.

---

<a id="string.trimEnd"></a>
## `string.trimEnd`

<!--
id: string.trimEnd
api: string.trimEnd
previous: str_trim_end
-->

```vir
string.trimEnd(s: string) -> string
```

### Status

`proposed` — ASCII-only today — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_trim_end`.

---

<a id="string.lower"></a>
## `string.lower`

<!--
id: string.lower
api: string.lower
previous: str_to_lower
-->

```vir
string.lower(s: string) -> string
```

Unicode-aware lowercase mapping → new `string`.

### Status

`proposed` — ASCII-only today — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_to_lower`.

---

<a id="string.upper"></a>
## `string.upper`

<!--
id: string.upper
api: string.upper
previous: str_to_upper
-->

```vir
string.upper(s: string) -> string
```

Unicode-aware uppercase mapping → new `string`.

### Status

`proposed` — ASCII-only today — **debt**.

### Implementation mapping

`vir/str/string.vri` → `str_to_upper`.

---

<a id="string.replace"></a>
## `string.replace`

<!--
id: string.replace
api: string.replace
previous: str_replace
-->

```vir
string.replace(s: string, old: string, new: string) -> string
```

Replace all non-overlapping occurrences of `old` with `new`.

### Status

`proposed` — **present** via `native_str_replace` stub — not conforming until
real impl.

### Implementation mapping

`vir/str/string.vri` → `str_replace`.

---

<a id="string.repeat"></a>
## `string.repeat`

<!--
id: string.repeat
api: string.repeat
previous: str_repeat
-->

```vir
string.repeat(s: string, n: int) -> string
```

Concatenate `s` repeated `n` times (`n == 0` → empty).

### Status

`proposed` — **present** as `str_repeat`.

### Implementation mapping

`vir/str/string.vri` → `str_repeat`.

---

<a id="string.split"></a>
## `string.split`

<!--
id: string.split
api: string.split
previous: str_split
-->

```vir
string.split(s: string, delim: string) -> Vec
```

Split on delimiter → `Vec` of `string`. Exact empty-delim / trailing-empty
rules follow implementation audit when stub is replaced; document then without
inventing foreign semantics here.

### Status

`proposed` — `native_str_split` stub — not conforming until real impl.

### Implementation mapping

`vir/str/string.vri` → `str_split`.

---

<a id="string.join"></a>
## `string.join`

<!--
id: string.join
api: string.join
previous: str_join
-->

```vir
string.join(parts: Vec, sep: string) -> string
```

Join string parts with `sep`.

### Status

`proposed` — `native_str_join` stub — not conforming until real impl.

### Implementation mapping

`vir/str/string.vri` → `str_join`.

---

<a id="string.free"></a>
## `string.free`

<!--
id: string.free
api: string.free
previous: str_free
-->

```vir
string.free(s: string)
```

Release owned UTF-8 storage under the current ownership model.

### Status

`proposed` — **present** as `str_free`.

### Implementation mapping

`vir/str/string.vri` → `str_free`.

---

## Implementation readiness

Core `string` map is closed for this refactor:

1. Expose namespace `string.*`; drop long-term public `str_*`.
2. Split `find` / `byteFind`; fix codepoint lane.
3. Strict `fromBytes`; boundary-safe `byteSlice`.
4. Unicode `lower` / `upper` / `trim*`.
5. Replace `replace` / `split` / `join` stubs.

Builder: [`builder.md`](builder.md). Unicode pack closed. Format/parse:
[`format`](format.md) / [`parse`](parse.md). Next: `fmt` + `builder.writeInt*`.
