---
module: format
title: Format
summary: Value → string primitives (int/bool/pad); float planned — not stream I/O.
source:
  - name: format
    path: vir/io/format.vri
status: closed
notes: >-
  Stable: int/intRadix/hex/bin/oct/bool + padLeft/Right/Center. No auto-prefix on
  int/intRadix; hex/bin/oct keep prefixes. Float planned until native meets tests.
  fmt.* and builder.writeInt* = later passes. Parse is parse.md. APFS: this file
  may appear as FORMAT.md. No .vri until map applied.
---

# Format

**Value → text** primitives. Public namespace **`format`**, not `io` (disk path
`vir/io/format.vri` is accidental).

```vir
format.int(255)           # "255"
format.intRadix(255, 16)  # "ff"
format.hex(255)           # "0xff"
format.bool(true)         # "true"
format.padLeft(s, 8, 0x20)
```

Opposite direction → [`parse`](parse.md). Templates / `printf` → **`fmt`**
(later). Direct numeric append on builder → later (`builder.write` +
`format.int` for now).

## Boundary

| In `format` | Not in `format` |
|---|---|
| Int / bool → `string` | [`parse`](parse.md) |
| Padding by **codepoint** width | [`fmt`](fmt.md) templates / printf |
| Prefixed `hex` / `bin` / `oct` | Stream I/O → [`io`](io.md) |
| | Stable `format.float` until tests pass |
| | `builder.writeInt` — later pass |

## Stable surface (closed)

```text
format
├── int
├── intRadix
├── hex
├── bin
├── oct
├── bool
│
├── padLeft
├── padRight
└── padCenter
```

## Integer formatting (closed)

| API | Output |
|---|---|
| `format.int(n)` | Decimal, no prefix |
| `format.intRadix(n, base)` | Digits only for `base` ∈ {2,8,10,16}; **no** prefix |
| `format.hex(n)` | `"0x"` + lowercase hex digits |
| `format.bin(n)` | `"0b"` + binary digits |
| `format.oct(n)` | `"0o"` + octal digits |

Negative: sign before prefix where applicable:

```text
format.hex(-255) → "-0xff"
```

Hex alphabet: **lowercase** (`a`–`f`). Unsupported `base` on `intRadix` =
parameter contract failure (not a parse error).

Domain: signed 64-bit integer of the current implementation (same as
[`parse`](parse.md)).

### Contract examples (target — not a claim that today’s impl already passes)

| Expression | Result |
|---|---|
| `format.int(255)` | `"255"` |
| `format.intRadix(255, 16)` | `"ff"` |
| `format.hex(255)` | `"0xff"` |
| `format.bin(5)` | `"0b101"` |
| `format.oct(8)` | `"0o10"` |
| `format.hex(-255)` | `"-0xff"` |

Today’s `format_int(n, base)` auto-prefixes for non-10 — **debt**; split into
`int` / `intRadix` / `hex`/`bin`/`oct` as above.

## Boolean (closed)

```vir
format.bool(value) -> string   # "true" / "false"
```

## Padding (closed)

```vir
format.padLeft(s, width, fill)
format.padRight(s, width, fill)
format.padCenter(s, width, fill)
```

| Rule | Contract |
|---|---|
| Width unit | Unicode **codepoints** ([`string.len`](string.md)) |
| `fill` | One valid Unicode **scalar** (`int`), not an arbitrary string |
| `width ≤ string.len(s)` | Return `s` unchanged |
| `padCenter` odd pad | Extra fill codepoint on the **right** |

Not terminal display width; not grapheme-cluster width.

## Float gate (closed — design criteria)

Shared with [`parse.float`](parse.md). See that file for F1–F6. Do **not**
auto-promote to `stable`. This module’s half:

| Item | Contract |
|---|---|
| `format.float(value)` | **Shortest round-trip** string for binary64 (F1a) — Q2 |
| `format.floatFixed(value, prec)` | Digits **after** decimal `prec` in `0…17`, ties-to-even (F1b) — Q2 |
| Overloading | **Out** — two distinct names; no overload / default-arg dual API |
| Decimal separator | `.` (locale-independent) |
| NaN / ±∞ | Emit **`nan`** / **`inf`** / **`-inf`** only (F2 — lowercase) |
| Negative zero | Preserve sign |

Stub / untested `native_f64_to_str` must **not** become public contract.
[`fmt.float`](fmt.md) / [`builder.writeFloat`](builder.md) wait on this gate.

## Planned — not stable (`format.float` / `format.floatFixed`)

```text
format.float(value)                 # shortest round-trip (Q2)
format.floatFixed(value, prec)      # fixed precision (Q2)
```

Not stable until the float gate (F1–F6) passes.

## Compatibility

| Current | Public | Action |
|---|---|---|
| `format_int` | `format.int` + `format.intRadix` (+ fix prefixes) | **split** / migrate |
| `format_hex` / `bin` / `oct` | `format.hex` / `bin` / `oct` | **rename** · keep prefixes |
| `format_bool` | `format.bool` | **rename** |
| `format_pad_left` | `format.padLeft` | **rename** |
| `format_pad_right` | `format.padRight` | **rename** |
| `format_center` | `format.padCenter` | **rename** |
| `format_float` | `format.float` + `format.floatFixed` | **planned** · split (Q2) |
| `i64_to_str` | → `format.int` | temp wrapper → deprecate |
| `f64_to_str` | → `format.float` (shortest) | planned / deprecate with float |
| `fmt.*` | — | **later** pass · own registry |
| `sb_append_i64` / … | — | **later** · use `builder.write` + `format.int` for now |

## Migration map

| Current | Canonical | Action |
|---|---|---|
| `format_int(n, 10)` style | `format.int(n)` | **rename** |
| `format_int(n, base)` bare digits | `format.intRadix(n, base)` | **new** / split |
| `format_int` auto `0x`/`0b`/`0o` | `format.hex` / `bin` / `oct` only | **remove** from generic int |
| `format_hex` | `format.hex` | **rename** |
| `format_bin` | `format.bin` | **rename** |
| `format_oct` | `format.oct` | **rename** |
| `format_bool` | `format.bool` | **rename** |
| `format_pad_left` | `format.padLeft` | **rename** |
| `format_pad_right` | `format.padRight` | **rename** |
| `format_center` | `format.padCenter` | **rename** |
| `format_float` | `format.float` / `format.floatFixed` | **planned** · split (Q2) |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `format.int` | `format.int` | `format.int(n: int) -> string` | proposed |
| `format.intRadix` | `format.intRadix` | `format.intRadix(n: int, base: int) -> string` | proposed |
| `format.hex` | `format.hex` | `format.hex(n: int) -> string` | proposed |
| `format.bin` | `format.bin` | `format.bin(n: int) -> string` | proposed |
| `format.oct` | `format.oct` | `format.oct(n: int) -> string` | proposed |
| `format.bool` | `format.bool` | `format.bool(value: bool) -> string` | proposed |
| `format.padLeft` | `format.padLeft` | `format.padLeft(s, width: int, fill: int) -> string` | proposed |
| `format.padRight` | `format.padRight` | `format.padRight(s, width: int, fill: int) -> string` | proposed |
| `format.padCenter` | `format.padCenter` | `format.padCenter(s, width: int, fill: int) -> string` | proposed |
| `format.float` | `format.float` | `format.float(value: float) -> string` | planned |
| `format.floatFixed` | `format.floatFixed` | `format.floatFixed(value: float, prec: int) -> string` | planned |

---

<a id="format.int"></a>
## `format.int`

<!-- id: format.int previous: format_int -->

```vir
format.int(n: int) -> string
```

Decimal rendering. No prefix.

### Example

```vir
format.int(255)  # "255"
```

### Status

`proposed` — split from `format_int`.

### Implementation mapping

`vir/io/format.vri` → part of `format_int` (base 10, no prefix).

---

<a id="format.intRadix"></a>
## `format.intRadix`

<!-- id: format.intRadix -->

```vir
format.intRadix(n: int, base: int) -> string
```

Digits only for `base` ∈ {2, 8, 10, 16}. **No** `0x`/`0b`/`0o`. Hex lowercase.
Unsupported `base` → parameter contract failure.

### Example

```vir
format.intRadix(255, 16)  # "ff"
```

### Status

`proposed`.

---

<a id="format.hex"></a>
## `format.hex` / `format.bin` / `format.oct`

```vir
format.hex(n: int) -> string   # "-"? + "0x" + hex
format.bin(n: int) -> string   # "-"? + "0b" + bits
format.oct(n: int) -> string   # "-"? + "0o" + octal
```

### Status

`proposed` — **present** as `format_hex` / `bin` / `oct`.

### Implementation mapping

`vir/io/format.vri`.

---

<a id="format.bool"></a>
## `format.bool`

```vir
format.bool(value: bool) -> string
```

`"true"` / `"false"`.

### Status

`proposed` — **present** as `format_bool`.

---

<a id="format.padLeft"></a>
## Padding

```vir
format.padLeft(s: string, width: int, fill: int) -> string
format.padRight(s: string, width: int, fill: int) -> string
format.padCenter(s: string, width: int, fill: int) -> string
```

See padding rules above. `fill` must be a valid Unicode scalar
([`unicode.valid`](unicode.md)).

### Status

`proposed` — **present** as `format_pad_*` / `format_center` → `padCenter`.

---

<a id="format.float"></a>
## `format.float` / `format.floatFixed` *(planned)*

```vir
format.float(value: float) -> string
format.floatFixed(value: float, prec: int) -> string
```

| Symbol | Role |
|---|---|
| `format.float` | Shortest round-trip (F1a) |
| `format.floatFixed` | Fixed digits-after-decimal `prec` 0…17, ties-to-even (F1b) |

**Q2 locked:** two names — **no** function overloading. Not stable until F1–F6
([`parse.md`](parse.md)) pass. Must not ship stub behavior as contract.

### Status

`planned`.

### See also

- [`parse.float`](parse.md) *(planned)*

---

## Later passes (out)

```text
fmt.format / fmt.printf / fmt.printfln
builder.writeInt / writeFloat / writeBool
```

Until then:

```vir
builder.write(sb, format.int(n))
```

## Implementation readiness

1. Split int vs intRadix vs prefixed hex/bin/oct.
2. Rename pads; `center` → `padCenter`; codepoint width + scalar fill.
3. Keep float planned; wrappers deprecate toward this surface.
4. Parse SSOT: [`parse.md`](parse.md).
