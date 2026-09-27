---
module: collation
title: Collation
summary: Unicode collation compare + sort key — namespace collation.*.
source:
  - name: collation
    path: vir/str/collation.vri
status: closed
notes: >-
  Thin surface: compare + key → Buffer. Full UCA/data for pinned Unicode version
  promised; Latin subset = debt. No compareCi. Sort keys built with Buffer not
  StringBuilder. Locale tailoring later. Shared Unicode version pin (pre-UCD;
  see unicode.md). No .vri until map.
---

# Collation

Unicode collation (UTS #10 / UCA-oriented) for ordering strings.

```vir
collation.compare(a, b) -> int     # <0 / 0 / >0
collation.key(s) -> Buffer         # binary sort key
```

Target: conform to the collation algorithm and data for the **stdlib Unicode
version**. Current Latin/DUCET **subset** = **non-conforming implementation
debt** — do not lower the public contract to “Latin only.”

Locale-specific tailoring is **out** of this pass.

Shares the **stdlib Unicode data version** with [`unicode`](unicode.md)
(pin: **`pre-UCD`**) and sibling text modules.

## Boundary

| In `collation` | Not in `collation` |
|---|---|
| Default `compare` / `key` | `compareCi` / case-fold API (separate audit) |
| Binary sort keys as [`Buffer`](buffer.md) | Building keys with [`StringBuilder`](builder.md) |
| | User-managed table object as the only compare path |
| | Locale tailoring |
| | Exposing `compare_keys` as required public |

## Architecture correction (closed)

Sort keys are **arbitrary binary**, not UTF-8 text:

```text
StringBuilder → valid UTF-8 text construction
Buffer        → arbitrary binary / collation keys
```

Implementation must **not** use `sb_append_byte` / `StringBuilder` for key
material. That conflicts with the [`builder`](builder.md) UTF-8 invariant.

```vir
collation.key(s) -> Buffer
```

## Public surface (closed)

```text
collation
├── compare
└── key
```

Default table is internal. Users must **not** be forced to construct/manage a
`CollationTable` for ordinary compare. If an advanced table parameter exists
later, it is optional — not the canonical path.

`collation_compare_keys` stays **internal** (or becomes ordinary `Buffer`
byte-lex compare).

## `compareCi` — removed

Case-insensitive compare ≠ collation. Current `collation_compare_ci` (and its
byte-index bug) is **out** of the canonical surface. Future Unicode case
folding needs its own audit (`casefold` / similar) — not a `compareCi` alias.

## Migration map

| Current | Public | Action |
|---|---|---|
| `collation_compare` | `collation.compare` | **rename** · default table internal |
| `collation_sort_key` | `collation.key` | **rename** · return `Buffer` |
| `collation_compare_keys` | — | **internal** |
| `collation_compare_ci` | — | **remove** public |
| `collation_default_table` | — | **internal** |
| `CollationTable` / `CollationElement` | — | **internal** unless advanced API later |
| `StringBuilder` in key path | `Buffer` | **fix** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `collation.compare` | `collation.compare` | `collation.compare(a: string, b: string) -> int` | proposed |
| `collation.key` | `collation.key` | `collation.key(s: string) -> Buffer` | proposed |

---

<a id="collation.compare"></a>
## `collation.compare`

```vir
collation.compare(a: string, b: string) -> int
```

Ordering under default Unicode collation data: `<0` / `0` / `>0`.

Distinct from [`string.cmp`](string.md) (raw UTF-8 byte order).

### Status

`proposed` — **present** with explicit table arg — migrate to default-internal;
data coverage = **debt**.

### Implementation mapping

`vir/str/collation.vri` → `collation_compare`.

---

<a id="collation.key"></a>
## `collation.key`

```vir
collation.key(s: string) -> Buffer
```

Binary sort key for `s`. Suitable for storage / binary compare. Not a `string`.

### Status

`proposed` — **present** as `collation_sort_key` (likely `Vec` today) — migrate
to `Buffer`; stop using `StringBuilder`.

### Implementation mapping

`vir/str/collation.vri` → `collation_sort_key`.

### See also

- [`buffer`](buffer.md)
- [`builder`](builder.md) — text only

---

## Implementation readiness

1. Namespace `collation.*`; drop public `compareCi` / forced table.
2. `key` → `Buffer`; remove `StringBuilder` from key construction.
3. Expand collation data to conforming coverage for pinned Unicode version.
4. Locale tailoring = later pass.

**Next after unicode pack:** [`format`](format.md) + parse (`to_i64` / …)
audit — separate from this cluster.
