---
module: unicode
title: Unicode
summary: SSOT for Unicode scalar facts + UTF-8 codec — namespace unicode.*.
source:
  - name: unicode
    path: vir/str/unicode.vri
status: closed
unicode_version: pre-UCD
notes: >-
  Sole public UTF-8 codec and scalar validity/category. Script predicates → char.
  next_codepoint / duplicate string&grapheme decoders → internal one impl.
  Full Unicode conformance promised; subset tables = debt.
  unicode_version pin: pre-UCD until first UCD import (see Version pin).
  No .vri until map applied.
---

# Unicode

**Single source of truth** for:

1. Unicode **scalar** validity / BMP / surrogate / supplementary  
2. **`UnicodeCategory`** + `unicode.category`  
3. **UTF-8 codec** used by the rest of the stdlib  

```text
                    unicode
             ┌──── UTF-8 codec ────┐
             │   scalar/category   │
             ▼                     ▼
          string                 builder
             │
      grapheme / normalize / collation / encode
```

```text
string utf8_*  +  grapheme utf8_decode  +  unicode utf8_*
        ↓
   ONE implementation · ONE malformed-input policy
```

[`builder.push`](builder.md) must use the same scalar rule as `unicode.valid`.

Shares the **stdlib Unicode data version** with sibling text modules
(see **Version pin** below).

## Version pin (closed)

### Audit

| Finding | Evidence |
|---|---|
| No UCD import / table generator | No UCD tooling or generated data under `stdlib/vir/str/` |
| No version string in sources | `unicode.vri`, `char.vri`, `normalize.vri`, `grapheme.vri`, `collation.vri` |
| Current data | Hand ranges, enum stubs, Latin/subset algorithms |

**Cannot honestly pin `Unicode X.Y.Z` today.** Inventing a release number would
claim UCD provenance that does not exist.

### Policy (locked)

1. **SSOT:** this file declares the stdlib Unicode data version
   (`unicode_version` in front matter). Siblings only reference it.
2. **Current value:** `pre-UCD` (unset). Subset / hand-written tables =
   **implementation debt**, not a conformance claim for any Unicode release.
   **Do not publish Unicode conformance** until official UCD tables are imported
   **and** tested. When a generator exists, pin **one** UCD version for all
   dependent modules.
3. **First UCD import:** the commit that lands UCD-derived tables **must** set
   `unicode_version: X.Y.Z` here and in [`README.md`](README.md) to the exact
   UCD release used to generate those tables. No silent upgrades.
4. **Shared:** `char` · `grapheme` · `normalize` · `collation` · `encode` ·
   Unicode-aware [`string`](string.md) case mapping use the same pin.
5. **Conformance:** public APIs remain full-algorithm contracts for the pinned
   version once set; until then do **not** document “Unicode N.M subset” as if
   it were the pin.
6. **Do not invent** a version number ahead of generated tables.

## Boundary

| In `unicode` | Not in `unicode` |
|---|---|
| Scalar validity + category | Script predicates → [`char`](char.md) |
| UTF-8 encode/decode/validate/count | Encoding bridges UTF-16/32 → [`encode`](encode.md) |
| | Public `next_codepoint` iteration helper |
| | Duplicate public decoders in `string` / `grapheme` |
| | Normalization / grapheme / collation algorithms |

## Public surface (closed)

```text
unicode
├── valid
├── surrogate
├── bmp
├── supplementary
├── category
│
├── utf8Len
├── encodeUtf8
├── decodeUtf8
├── validUtf8
└── countUtf8
```

Plus types:

```text
UnicodeCategory   # Lu, Ll, … — public with unicode.category
Utf8Decoded       # codepoint + nbytes — decodeUtf8 Ok payload (Q1)
```

## Scalar rules (closed)

```vir
unicode.valid(cp) -> bool
```

Reject: surrogates, `> U+10FFFF`, negative / invalid representation.

```text
unicode.surrogate(cp)
unicode.bmp(cp)
unicode.supplementary(cp)
```

`builder.push` / trusted encoders call the same `valid` rule — never silently
corrupt UTF-8.

## UTF-8 codec (closed)

Public binary views use [`Slice`](slice.md) / [`Buffer`](buffer.md), not raw
`ptr`.

| Op | Role |
|---|---|
| `utf8Len(cp)` | Bytes needed to encode scalar (`0` if invalid) |
| `encodeUtf8(cp, …)` | Write UTF-8 for one scalar (invalid → panic or no-write; never bad sequence) |
| `decodeUtf8(s, offset)` | One scalar from `Slice` at byte offset → recoverable on malformed |
| `validUtf8(s)` | Whole-sequence validation |
| `countUtf8(s)` | Codepoint count of valid sequence |

Malformed UTF-8 on decode/validate paths that return errors → `Result` with
[`ErrorKind.InvalidData`](error.md). **Do not invent `InvalidEncoding`** in
this pass.

`unicode.decodeUtf8` must **not** silently emit `U+FFFD` as success for bad
input on the public path (today’s decoder replacement behavior is debt if
exposed). Replacement policy, if any, belongs in an explicitly named API later.

## Category (closed)

```vir
unicode.category(cp) -> UnicodeCategory
```

Target: Unicode Character Database for the pinned stdlib Unicode version.
Enum without accessor is not enough — **add** `category` even if missing today.

## Migration map

| Current | Public | Action |
|---|---|---|
| `is_valid_codepoint` | `unicode.valid` | **rename** |
| `is_surrogate` | `unicode.surrogate` | **rename** |
| `is_bmp` | `unicode.bmp` | **rename** |
| `is_supplementary` | `unicode.supplementary` | **rename** |
| `UnicodeCategory` | `UnicodeCategory` | **keep** |
| — | `unicode.category` | **new** · UCD-backed |
| `utf8_encode_len` | `unicode.utf8Len` | **rename** |
| `utf8_encode` | `unicode.encodeUtf8` | **rename** · no public raw `ptr` ABI |
| `utf8_decode` | `unicode.decodeUtf8` | **rename** · `Slice` + `Result` policy |
| `utf8_is_valid` | `unicode.validUtf8` | **rename** · `Slice` |
| `utf8_codepoint_count` | `unicode.countUtf8` | **rename** |
| `utf8_next_codepoint` | — | **internal** |
| `is_cjk_*` / hangul / kana / emoji / vietnamese | → [`char`](char.md) or out | **move** / **drop** |
| `string.vri` `utf8_*` | — | **dedupe** → call unicode |
| `grapheme` `utf8_decode` | — | **internal** → unicode SSOT |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `unicode.UnicodeCategory` | `UnicodeCategory` | enum | proposed |
| `unicode.valid` | `unicode.valid` | `unicode.valid(cp: int) -> bool` | proposed |
| `unicode.surrogate` | `unicode.surrogate` | `unicode.surrogate(cp: int) -> bool` | proposed |
| `unicode.bmp` | `unicode.bmp` | `unicode.bmp(cp: int) -> bool` | proposed |
| `unicode.supplementary` | `unicode.supplementary` | `unicode.supplementary(cp: int) -> bool` | proposed |
| `unicode.category` | `unicode.category` | `unicode.category(cp: int) -> UnicodeCategory` | proposed |
| `unicode.utf8Len` | `unicode.utf8Len` | `unicode.utf8Len(cp: int) -> int` | proposed |
| `unicode.encodeUtf8` | `unicode.encodeUtf8` | encode one scalar into buffer/bytes | proposed |
| `unicode.Utf8Decoded` | `Utf8Decoded` | entity · `codepoint: int`, `nbytes: int` | proposed |
| `unicode.decodeUtf8` | `unicode.decodeUtf8` | `decodeUtf8(s: Slice, offset: int) -> Result of (Utf8Decoded)` | proposed |
| `unicode.validUtf8` | `unicode.validUtf8` | `unicode.validUtf8(s: Slice) -> bool` | proposed |
| `unicode.countUtf8` | `unicode.countUtf8` | `unicode.countUtf8(s: Slice) -> int` | proposed |

`encodeUtf8` buffer shape follows implementer choice (`Buffer` append vs scratch)
without public `ptr` + `out_len`. **`decodeUtf8` Ok type is locked (Q1):**
`Utf8Decoded` — not an unverified tuple form.

---

<a id="unicode.valid"></a>
## Scalar queries

```vir
unicode.valid(cp: int) -> bool
unicode.surrogate(cp: int) -> bool
unicode.bmp(cp: int) -> bool
unicode.supplementary(cp: int) -> bool
```

### Status

`proposed` — **present** under `is_*` names.

### See also

- [`builder.push`](builder.md)

---

<a id="unicode.category"></a>
## `unicode.category`

```vir
unicode.category(cp: int) -> UnicodeCategory
```

UCD General Category for the pinned Unicode version.

### Status

`proposed` — **missing** accessor; enum exists — **debt** until UCD-backed.

---

<a id="unicode.utf8Len"></a>
## UTF-8 codec

```vir
unicode.utf8Len(cp: int) -> int
unicode.encodeUtf8(...)
unicode.utf8Len(cp: int) -> int
unicode.encodeUtf8(...)
unicode.decodeUtf8(s: Slice, offset: int) -> Result of (Utf8Decoded)
unicode.validUtf8(s: Slice) -> bool
unicode.countUtf8(s: Slice) -> int
```

### `Utf8Decoded` (Q1 — locked)

```text
entity Utf8Decoded:
    codepoint: int    # decoded Unicode scalar
    nbytes: int       # bytes consumed from the Slice
```

`decodeUtf8` returns `Result of (Utf8Decoded)`. Malformed → `Err` with
[`ErrorKind.InvalidData`](error.md); no silent `U+FFFD` success. Do **not**
depend on tuple syntax for this public ABI.

### Status

`proposed` — **present** on `ptr`; migrate types; unify callers; fix public
malformed policy.

### See also

- [`string.fromBytes`](string.md)
- [`encode`](encode.md)

---

## Implementation readiness

1. Make this module the only UTF-8 decoder/encoder implementation.
2. Add `category`; move script predicates to `char`.
3. `Slice`/`Buffer` public ABI; `InvalidData` on malformed decode errors.
4. **Version pin policy closed** (`pre-UCD`). First UCD import sets `X.Y.Z`;
   then expand tables to conforming coverage for that pin.
