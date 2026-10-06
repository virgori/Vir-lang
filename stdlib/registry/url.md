---
module: url
title: Url
summary: RFC 3986 URL parse, stringify, and encoding — namespace url.*
source:
  - name: url
    path: vir/url.vri
  - name: url.impl
    path: vir/net/url.vri
    notes: implementation
status: stable
---

# Url

Public contract: **`include url`** → namespace **`url.*`**. Types use qualified
names in docs: **`url.Url`**.

```vir
let r = url.parse("https://example.com/path?q=1")
```

## Migration map

| Legacy (remove from public export) | Public | Action |
|---|---|---|
| `url_parse` | `url.parse` | **internal** impl name only |
| `url_stringify` | `url.stringify` | **internal** |
| `url_encode` / `url_decode` | `url.encode` / `url.decode` | **internal** |
| `url_decode_form` | `url.decodeForm` | **internal** |
| `url_query_get` | `url.queryGet` | **internal** |
| `url_get_*` | accessors TBD | **planned** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `url.Url` | `Url` | entity | draft |
| `url.parse` | `url.parse` | `url.parse(raw: string) -> Result of (Url)` | draft |
| `url.stringify` | `url.stringify` | `url.stringify(u: Url) -> string` | draft |
| `url.encode` | `url.encode` | `url.encode(raw: string) -> string` | draft |
| `url.decode` | `url.decode` | `url.decode(raw: string) -> Result of (string)` | draft |
| `url.decodeForm` | `url.decodeForm` | `url.decodeForm(raw: string) -> Result of (string)` | draft |
| `url.queryGet` | `url.queryGet` | `url.queryGet(u: Url, key: string) -> Option of (string)` | draft |
| `url.queryParam` | `url.queryParam` | `url.queryParam(query: string, key: string) -> Option of (string)` | draft |

## Implementation notes

`url.parse` is implemented by internal `url_parse` in `vir/net/url.vri`. That
name must not appear in user-facing API tables or examples.
