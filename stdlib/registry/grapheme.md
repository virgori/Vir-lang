---
module: grapheme
title: Grapheme
summary: Extended grapheme clusters (UAX #29) — namespace grapheme.*.
source:
  - name: grapheme
    path: vir/str/grapheme.vri
status: closed
notes: >-
  Thin surface: count/at/clusters/reverse. Full UAX #29 conformance promised;
  simplified impl = debt. Index unit = grapheme. Decode via unicode SSOT.
  Shared Unicode version pin (pre-UCD; see unicode.md). No .vri until map applied.
---

# Grapheme

User-perceived character segmentation — **extended grapheme clusters** per
Unicode Standard Annex #29.

```text
string.len(s)       → codepoints
grapheme.count(s)   → extended grapheme clusters
string.bytes(s)     → UTF-8 bytes
```

```vir
let n = grapheme.count(s)
let g = grapheme.at(s, 0)       # Option · grapheme index
let rev = grapheme.reverse(s)
```

**Not** “simplified UAX #29” as the public contract. Target is conforming
grapheme segmentation for the **stdlib Unicode data version**. Current
simplified tables/rules = **non-conforming implementation debt**.

## Boundary

| In `grapheme` | Not in `grapheme` |
|---|---|
| Cluster count / index / list / reverse | Codepoint count → [`string.len`](string.md) |
| Grapheme **index** lane | Public UTF-8 decode (use [`unicode`](unicode.md)) |
| | Word/sentence breaks (other UAX #29 products) |

## Public surface (closed)

```text
grapheme
├── count
├── at
├── clusters
└── reverse
```

## Types (from source)

```text
GraphemeCluster
├── start: int     # byte offset in source (today)
├── length: int    # byte length (today)
└── text: string   # cluster contents
```

`grapheme.clusters(s) -> Vec` of `GraphemeCluster`.  
`grapheme.at(s, idx) -> Option of (GraphemeCluster)`.

Registry does not invent a different collection type. Field meanings follow
implementation; any byte-vs-codepoint bugs in today’s `clusters` builder are
**debt** to fix under the UAX #29 + UTF-8 SSOT work.

## Indexing (closed)

`grapheme.at` / logical positions use **grapheme index** `0 .. count`, not
byte or codepoint index.

OOB → `None` for `at` (today). Do not conflate with `string.char` panic style
unless a later audit unifies — keep `Option` while source does.

## Migration map

| Current | Public | Action |
|---|---|---|
| `grapheme_count` | `grapheme.count` | **rename** |
| `grapheme_at` | `grapheme.at` | **rename** |
| `grapheme_clusters` | `grapheme.clusters` | **rename** |
| `grapheme_reverse` | `grapheme.reverse` | **rename** |
| `utf8_decode` (local) | — | **internal** · call [`unicode`](unicode.md) |
| `grapheme_break_property` | — | **internal** |
| `GraphemeCluster` | `GraphemeCluster` | **keep** public payload type |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `grapheme.GraphemeCluster` | `GraphemeCluster` | type | proposed |
| `grapheme.count` | `grapheme.count` | `grapheme.count(s: string) -> int` | proposed |
| `grapheme.at` | `grapheme.at` | `grapheme.at(s: string, i: int) -> Option of (GraphemeCluster)` | proposed |
| `grapheme.clusters` | `grapheme.clusters` | `grapheme.clusters(s: string) -> Vec of (GraphemeCluster)` | proposed |
| `grapheme.reverse` | `grapheme.reverse` | `grapheme.reverse(s: string) -> string` | proposed |

---

<a id="grapheme.count"></a>
## `grapheme.count`

```vir
grapheme.count(s: string) -> int
```

Number of extended grapheme clusters.

### Status

`proposed` — **present**; algorithm coverage = **debt**.

---

<a id="grapheme.at"></a>
## `grapheme.at`

```vir
grapheme.at(s: string, i: int) -> Option of (GraphemeCluster)
```

Cluster at grapheme index `i`, or `None`.

### Status

`proposed`.

---

<a id="grapheme.clusters"></a>
## `grapheme.clusters`

```vir
grapheme.clusters(s: string) -> Vec
```

All clusters as `GraphemeCluster` values.

### Status

`proposed` — fix offset/`string.slice` misuse and UAX coverage as debt.

---

<a id="grapheme.reverse"></a>
## `grapheme.reverse`

```vir
grapheme.reverse(s: string) -> string
```

Concatenate clusters in reverse order (grapheme-aware reverse).

### Status

`proposed` — uses [`builder`](builder.md); keep UTF-8 invariant.

---

## Implementation readiness

1. Namespace `grapheme.*`; decode only via `unicode` SSOT.
2. Expand to conforming UAX #29 for pinned Unicode version.
3. Fix cluster offset / slice bugs under that work.
