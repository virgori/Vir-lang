---
module: encode
title: Encode
summary: Encoding bridges UTF-8 ↔ UTF-16LE / UTF-32LE — namespace encode.*.
source:
  - name: encode
    path: vir/str/encode.vri
    notes: stdlib name str.encode
status: closed
notes: >-
  Bridges only; UTF-8 codec stays in unicode. Public Slice in / Buffer out.
  Wire form UTF-16LE and UTF-32LE explicit; no silent host endian; no auto BOM.
  Strict default; asciiLossy explicitly named. Err → ErrorKind.InvalidData.
  No .vri until map applied.
---

# Encode

Conversion **between** UTF-8 and other Unicode encoding forms.

UTF-8 scalar codec stays in [`unicode`](unicode.md). This module is the
**bridge** layer.

```text
encode ── encoding bridges ── Buffer / Slice
```

```vir
let b = encode.utf8ToUtf16(slice)   # Result → Ok(Buffer) UTF-16LE
let u = encode.utf16ToUtf8(slice)   # Result → Ok(Buffer) UTF-8 bytes
```

Physical module today: `str/encode.vri` (`str.encode` in `stdlib.vri`). Public
namespace is **`encode`**. Distinct from any other `encode/*` package modules.

## Boundary

| In `encode` | Not in `encode` |
|---|---|
| UTF-8 ↔ UTF-16LE / UTF-32LE | UTF-8 scalar codec → [`unicode`](unicode.md) |
| Explicitly named `asciiLossy` | Silent lossy `ascii()` |
| `Slice` in / `Buffer` out | Public raw `ptr` / `Utf16Result` pointer bags |
| Strict malformed → `Result` | Auto BOM detect/emit |
| | Host-endian dependent UTF-16/32 |

## Endianness (closed)

Public UTF-16 and UTF-32 **wire bytes** are **little-endian**:

| Form | Public meaning |
|---|---|
| UTF-16 | **UTF-16LE** code units in a `Buffer` / `Slice` of bytes |
| UTF-32 | **UTF-32LE** code units in a `Buffer` / `Slice` of bytes |

Names stay `utf8ToUtf16` / … (as locked); registry contract states LE. No
silent dependence on host endian. Big-endian variants = future separate APIs
if needed.

## BOM (closed)

No automatic BOM sniffing or emission unless a future API says so explicitly.
Callers that need BOM prepend/strip do it themselves.

## Errors (closed)

Malformed input → `Result` Err with [`ErrorKind.InvalidData`](error.md).
Do **not** invent `InvalidEncoding` in this pass.

## Public surface (closed)

```text
encode
├── utf8ToUtf16
├── utf16ToUtf8
├── utf8ToUtf32
├── utf32ToUtf8
└── asciiLossy
```

## I/O types (closed)

| Direction | Type |
|---|---|
| UTF-8 text input | `string` **or** `Slice` of UTF-8 bytes (implementer picks per op; prefer `Slice` for symmetric bridges) |
| UTF-8 output | `Buffer` (UTF-8 bytes) or `string` when validating into text — prefer **`Buffer`** for bridge symmetry unless converting to text |
| UTF-16/32 input | `Slice` (LE bytes) |
| UTF-16/32 output | `Buffer` (LE bytes) |

Drop public `Utf16Result` / `Utf8Result` / `Utf32Result` as pointer wrappers.
Allocation lives in `Buffer`.

Canonical signatures (closed intent):

```vir
encode.utf8ToUtf16(s: Slice) -> Result    # Ok(Buffer) UTF-16LE
encode.utf16ToUtf8(s: Slice) -> Result    # Ok(Buffer) UTF-8
encode.utf8ToUtf32(s: Slice) -> Result    # Ok(Buffer) UTF-32LE
encode.utf32ToUtf8(s: Slice) -> Result    # Ok(Buffer) UTF-8
encode.asciiLossy(s: Slice) -> Buffer     # non-ASCII → '?'
```

`asciiLossy` is intentionally lossy; name must stay explicit. No
`encode.ascii` that silently replaces.

## Migration map

| Current | Public | Action |
|---|---|---|
| `utf8_to_utf16` | `encode.utf8ToUtf16` | **rename** · `Slice`→`Result(Buffer)` · UTF-16LE |
| `utf16_to_utf8` | `encode.utf16ToUtf8` | **rename** |
| `utf8_to_utf32` | `encode.utf8ToUtf32` | **rename** · add `Result` if missing |
| `utf32_to_utf8` | `encode.utf32ToUtf8` | **rename** |
| `utf8_to_ascii_lossy` | `encode.asciiLossy` | **rename** · keep lossy |
| `is_ascii_string` | — or `char`/`unicode` helper | **audit** · not required on encode surface |
| `Utf16Result` / `Utf8Result` / `Utf32Result` | — | **remove** public · use `Buffer` |
| raw `ptr` + lengths | `Slice` / `Buffer` | **migrate** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `encode.utf8ToUtf16` | `encode.utf8ToUtf16` | `encode.utf8ToUtf16(s: Slice) -> Result(Buffer)` | proposed |
| `encode.utf16ToUtf8` | `encode.utf16ToUtf8` | `encode.utf16ToUtf8(s: Slice) -> Result(Buffer)` | proposed |
| `encode.utf8ToUtf32` | `encode.utf8ToUtf32` | `encode.utf8ToUtf32(s: Slice) -> Result(Buffer)` | proposed |
| `encode.utf32ToUtf8` | `encode.utf32ToUtf8` | `encode.utf32ToUtf8(s: Slice) -> Result(Buffer)` | proposed |
| `encode.asciiLossy` | `encode.asciiLossy` | `encode.asciiLossy(s: Slice) -> Buffer` | proposed |

---

<a id="encode.utf8ToUtf16"></a>
## `encode.utf8ToUtf16`

```vir
encode.utf8ToUtf16(s: Slice) -> Result(Buffer)
```

Decode UTF-8 via [`unicode`](unicode.md) SSOT; emit **UTF-16LE** into
`Ok(Buffer)`. Invalid UTF-8 / scalar → `Err(… InvalidData …)`.

### Status

`proposed` — **present** on `ptr`; LE today.

---

<a id="encode.utf16ToUtf8"></a>
## `encode.utf16ToUtf8`

```vir
encode.utf16ToUtf8(s: Slice) -> Result(Buffer)
```

Interpret `s` as **UTF-16LE** bytes; emit UTF-8 `Buffer`. Truncated/invalid
surrogate pairs → `Err(InvalidData)`.

### Status

`proposed`.

---

<a id="encode.utf8ToUtf32"></a>
## `encode.utf8ToUtf32`

```vir
encode.utf8ToUtf32(s: Slice) -> Result(Buffer)
```

Emit **UTF-32LE** code units into `Buffer`.

### Status

`proposed` — today may return bare struct; unify on `Result` + `Buffer`.

---

<a id="encode.utf32ToUtf8"></a>
## `encode.utf32ToUtf8`

```vir
encode.utf32ToUtf8(s: Slice) -> Result(Buffer)
```

Interpret `s` as **UTF-32LE**; emit UTF-8. Invalid scalar → `Err(InvalidData)`.

### Status

`proposed`.

---

<a id="encode.asciiLossy"></a>
## `encode.asciiLossy`

```vir
encode.asciiLossy(s: Slice) -> Buffer
```

Replace non-ASCII codepoints with `'?'`. Explicitly lossy — never the default
strict path.

### Status

`proposed` — **present** as `utf8_to_ascii_lossy`.

---

## Implementation readiness

1. `Slice`/`Buffer` public ABI; drop pointer result entities.
2. Document and test LE-only wire; no BOM auto.
3. Decode through `unicode` SSOT; errors → `InvalidData`.
4. Keep `asciiLossy` named; no silent ascii.
