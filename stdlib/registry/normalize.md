---
module: normalize
title: Normalize
summary: Unicode NFC/NFD normalization — namespace normalize.*.
source:
  - name: normalize
    path: vir/str/normalize.vri
status: closed
notes: >-
  nfc/nfd + is/eq helpers. Full Unicode normalization algorithm promised for
  pinned version; partial tables = debt. No NFKC/NFKD this pass. Shared Unicode
  version pin (pre-UCD; see unicode.md). No .vri until map applied.
---

# Normalize

Unicode normalization forms **NFC** and **NFD** (UAX #15).

```vir
let t = normalize.nfc(s)
normalize.eqNfc(a, b)    # canonical-equivalence oriented via NFC
a == b                   # exact string equality — different op
```

Target:

> NFC/NFD conform to the Unicode normalization algorithm for the Unicode
> version declared by the stdlib.

Current partial decomposition/composition / CCC tables =
**non-conforming implementation debt**. Do **not** document the public API as
“NFC for our subset.”

Shares the **stdlib Unicode data version** with [`unicode`](unicode.md)
(pin: **`pre-UCD`**) / [`char`](char.md) / [`grapheme`](grapheme.md) /
[`collation`](collation.md).

## Boundary

| In `normalize` | Not in `normalize` |
|---|---|
| `nfc` / `nfd` | `nfkc` / `nfkd` — **out** this pass |
| `isNfc` / `isNfd` | Exact `==` (language) |
| `eqNfc` / `eqNfd` | Collation / locale compare → [`collation`](collation.md) |
| | Exposing internal CCC/decomp maps |

## Public surface (closed)

```text
normalize
├── nfc
├── nfd
├── isNfc
├── isNfd
├── eqNfc
└── eqNfd
```

## Equality (closed)

| Op | Meaning |
|---|---|
| `a == b` | Exact UTF-8 / string equality |
| `normalize.eqNfc(a, b)` | Compare under NFC-oriented canonical equivalence |
| `normalize.eqNfd(a, b)` | Same under NFD |

## Migration map

| Current | Public | Action |
|---|---|---|
| `nfc` | `normalize.nfc` | **rename** |
| `nfd` | `normalize.nfd` | **rename** |
| `is_nfc` | `normalize.isNfc` | **rename** |
| `is_nfd` | `normalize.isNfd` | **rename** |
| `str_eq_nfc` | `normalize.eqNfc` | **rename** |
| `str_eq_nfd` | `normalize.eqNfd` | **rename** |
| `_build_*` / `get_ccc` / … | — | **internal** |
| NFKC / NFKD | — | **out** until implemented |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `normalize.nfc` | `normalize.nfc` | `normalize.nfc(s: string) -> string` | proposed |
| `normalize.nfd` | `normalize.nfd` | `normalize.nfd(s: string) -> string` | proposed |
| `normalize.isNfc` | `normalize.isNfc` | `normalize.isNfc(s: string) -> bool` | proposed |
| `normalize.isNfd` | `normalize.isNfd` | `normalize.isNfd(s: string) -> bool` | proposed |
| `normalize.eqNfc` | `normalize.eqNfc` | `normalize.eqNfc(a: string, b: string) -> bool` | proposed |
| `normalize.eqNfd` | `normalize.eqNfd` | `normalize.eqNfd(a: string, b: string) -> bool` | proposed |

---

<a id="normalize.nfc"></a>
## `normalize.nfc` / `normalize.nfd`

```vir
normalize.nfc(s: string) -> string
normalize.nfd(s: string) -> string
```

### Status

`proposed` — **present**; table coverage = **debt**.

---

<a id="normalize.isNfc"></a>
## `normalize.isNfc` / `normalize.isNfd`

```vir
normalize.isNfc(s: string) -> bool
normalize.isNfd(s: string) -> bool
```

### Status

`proposed`.

---

<a id="normalize.eqNfc"></a>
## `normalize.eqNfc` / `normalize.eqNfd`

```vir
normalize.eqNfc(a: string, b: string) -> bool
normalize.eqNfd(a: string, b: string) -> bool
```

### Status

`proposed` — **present** as `str_eq_nfc` / `str_eq_nfd`.

---

## Implementation readiness

1. Namespace `normalize.*`.
2. Expand tables to conforming coverage for pinned Unicode version.
3. Keep NFKC/NFKD out until a dedicated pass.
