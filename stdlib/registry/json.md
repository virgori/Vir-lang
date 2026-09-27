---
module: json
title: Json
summary: RFC 8259 JSON values — namespace json.*; JsonValue tree; read/write.
source:
  - name: json
    path: vir/json.vri
  - name: data.json
    path: vir/data/json.vri
    notes: duplicate / alias path — public namespace is json
status: draft
notes: >-
  Inventory from JsonNamespace + free helpers. Number payload is int today;
  JSON float numbers gated on format/parse float gate. camelCase renames proposed
  for as_*/is_null. No .vri until map accepted. Docs-only.
---

# Json

RFC 8259 JSON as an in-memory **`JsonValue`** tree under namespace **`json`**.

```vir
let r = json.read(text)          # Result(JsonValue)
let s = json.write(val)          # compact string
let p = json.pretty(val)         # indent 2
json.set(obj, "port", json.number(8080))
```

Physical modules today: `vir/json.vri` and `vir/data/json.vri` (alias).
**Public docs use `json.*` only** — users never need `data.json` as a second API.

## Boundary

| In `json` | Not in `json` |
|---|---|
| Parse / stringify / tree ops | Streaming SAX / pull parsers |
| Object / array mutators on `JsonValue` | Schema validation language |
| Integer JSON numbers (current) | Stable float JSON numbers before float gate |
| | YAML / TOML / XML (separate namespaces) |
| | Treating `count` / `size` as distinct semantics from `len` |

## Types (closed inventory)

```text
JsonType     # Null | Bool | Number | Str | Array | Object
JsonValue    # tagged tree node
```

`JsonParser` / `JsonBuf` are **implementation** — not public surface.

## Number model (locked for this draft)

| Fact | Contract |
|---|---|
| Constructor | `json.number(n: int) -> JsonValue` |
| Unbox | `json.asInt(v) -> int` (today `as_int`) |
| Parse | JSON numbers that fit signed 64-bit integers → `Number` |
| Float JSON | **Not stable** until [`float gate`](parse.md) (F1–F6). Do not invent `json.float` / `number(float)` in this pass. |
| Gap | Fractional / exponent JSON numbers vs int-only storage = **implementation gap** — document; do not silently claim full RFC number support as certified |

RFC 8259 allows arbitrary precision numbers; Vir’s public contract for this wave
is **int-backed `Number`** plus a future float path after the float gate. Exact
overflow / reject rules for out-of-int64 JSON numbers = **audit** against
`json_parse_num`.

## Failure model (closed)

```text
json.read(s) -> Result(JsonValue)
```

Errors use the existing parse-error payload from `vir.data.error` (position /
line / col / message). Map into [`Error`](error.md) /
domain kind **audit** — do not invent a second parallel error taxonomy in docs
until that mapping is closed. Trailing garbage after one value → error (present).

Nesting depth limit **128** (present) — keep as contract; do not raise in docs
without an explicit decision.

## Public surface (proposed)

```text
json
├── read · write · pretty
│
├── null · bool · number · string · array · object
│
├── get · set · has
├── at · push
├── len                    # count/size → aliases → merge
├── key · value            # indexed object walk (present as key_at / val_at)
│
├── kind
├── asInt · asString · asBool · isNull
│
├── getInt · getStr · getBool
└── fromInts · fromStrings · fromBools
```

## Naming (proposed)

| Current | Public | Action |
|---|---|---|
| `json.read` / `json_parse` | `json.read` | keep |
| `json.write` / `json_stringify` | `json.write` | keep |
| `json.pretty` / `json_stringify_pretty` | `json.pretty` | keep |
| `as_int` / `as_string` / `as_bool` / `is_null` | `asInt` / `asString` / `asBool` / `isNull` | **rename** |
| `count` / `size` | → `len` | **merge** (aliases optional during migrate) |
| `json_obj_key_at` / `json_obj_val_at` | `json.key` / `json.value` | **rename** · expose on namespace |
| free `kind` / `len` / … | `json.*` only | drop free public aliases when map applied |

## Semantics notes (locked)

| Op | Contract |
|---|---|
| `get` | `Option(JsonValue)` — missing key → `None` |
| `has` | `bool` |
| `set` | upsert by key |
| `at` | array index; out-of-range / wrong tag → **audit** (today returns `null` JsonValue — may be debt vs `Option`) |
| `push` | append to array |
| `len` | array length or object entry count; else `0` |
| `getInt` / `getStr` / `getBool` | typed get with **default** on missing / wrong type (no panic) |
| `write` | compact RFC stringify |
| `pretty` | indent **2** spaces (present) |

Malformed UTF-8 / escapes / isolated surrogates: follow RFC 8259 rejection
claimed by source — conformance suite is **implementation debt** until audited.

## Migration map

| Current | Public | Action |
|---|---|---|
| `json_parse` | `json.read` | keep ns · free → internal |
| `json_stringify` | `json.write` | keep |
| `json_stringify_pretty` | `json.pretty` | keep |
| `json_null` … `json_object` | `json.null` … | keep |
| `json_obj_get` / `set` | `json.get` / `set` | keep |
| `json_arr_get` / `push` | `json.at` / `push` | keep |
| `as_int` … | `asInt` … | **rename** |
| `count` / `size` | `len` | **merge** |
| `json_obj_key_at` / `val_at` | `json.key` / `json.value` | **rename** + ns |
| `data.json` include | `json` | **alias** only |
| float JSON number API | — | **planned** after float gate |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `json.JsonType` | `JsonType` | enum | draft |
| `json.JsonValue` | `JsonValue` | entity | draft |
| `json.read` | `json.read` | `json.read(s: string) -> Result(JsonValue)` | draft |
| `json.write` | `json.write` | `json.write(val: JsonValue) -> string` | draft |
| `json.pretty` | `json.pretty` | `json.pretty(val: JsonValue) -> string` | draft |
| `json.null` | `json.null` | `json.null() -> JsonValue` | draft |
| `json.bool` | `json.bool` | `json.bool(b: bool) -> JsonValue` | draft |
| `json.number` | `json.number` | `json.number(n: int) -> JsonValue` | draft |
| `json.string` | `json.string` | `json.string(s: string) -> JsonValue` | draft |
| `json.array` | `json.array` | `json.array() -> JsonValue` | draft |
| `json.object` | `json.object` | `json.object() -> JsonValue` | draft |
| `json.get` | `json.get` | `json.get(obj: JsonValue, key: string) -> Option(JsonValue)` | draft |
| `json.set` | `json.set` | `json.set(obj: JsonValue, key: string, val: JsonValue)` | draft |
| `json.has` | `json.has` | `json.has(obj: JsonValue, key: string) -> bool` | draft |
| `json.at` | `json.at` | `json.at(arr: JsonValue, idx: int) -> JsonValue` | draft |
| `json.push` | `json.push` | `json.push(arr: JsonValue, item: JsonValue)` | draft |
| `json.len` | `json.len` | `json.len(val: JsonValue) -> int` | draft |
| `json.key` | `json.key` | `json.key(obj: JsonValue, idx: int) -> string` | proposed |
| `json.value` | `json.value` | `json.value(obj: JsonValue, idx: int) -> JsonValue` | proposed |
| `json.kind` | `json.kind` | `json.kind(val: JsonValue) -> int` | draft |
| `json.asInt` | `json.asInt` | `json.asInt(val: JsonValue) -> int` | proposed |
| `json.asString` | `json.asString` | `json.asString(val: JsonValue) -> string` | proposed |
| `json.asBool` | `json.asBool` | `json.asBool(val: JsonValue) -> bool` | proposed |
| `json.isNull` | `json.isNull` | `json.isNull(val: JsonValue) -> bool` | proposed |
| `json.getInt` | `json.getInt` | `json.getInt(obj, key, default: int) -> int` | draft |
| `json.getStr` | `json.getStr` | `json.getStr(obj, key, default: string) -> string` | draft |
| `json.getBool` | `json.getBool` | `json.getBool(obj, key, default: bool) -> bool` | draft |
| `json.fromInts` | `json.fromInts` | `json.fromInts(values) -> JsonValue` | draft |
| `json.fromStrings` | `json.fromStrings` | `json.fromStrings(values) -> JsonValue` | draft |
| `json.fromBools` | `json.fromBools` | `json.fromBools(values) -> JsonValue` | draft |

`Result(JsonValue)` uses default [`Error`](error.md) once error mapping is
closed; until then source may return a dedicated parse-error value —
**implementation gap**.

---

<a id="json.read"></a>
## `json.read`

<!--
id: json.read
api: json.read
previous: json_parse
-->

```vir
json.read(s: string) -> Result(JsonValue)
```

Parse one JSON value from `s`. Trailing non-whitespace → error. Empty input →
error (present).

### Status

`draft` — **present** as `json.read` / `json_parse`.

### Errors

Parse failure (syntax, depth, trailing garbage). Exact `Error` mapping **audit**.

### See also

- [`json.write`](#json.write)

---

<a id="json.write"></a>
## `json.write` / `json.pretty`

<!--
id: json.write
api: json.write
previous: json_stringify
-->

```vir
json.write(val: JsonValue) -> string
json.pretty(val: JsonValue) -> string
```

Serialize. `pretty` uses indent width **2**.

### Status

`draft` — **present**.

---

<a id="json.number"></a>
## Constructors

```vir
json.null() -> JsonValue
json.bool(b: bool) -> JsonValue
json.number(n: int) -> JsonValue
json.string(s: string) -> JsonValue
json.array() -> JsonValue
json.object() -> JsonValue
```

### Status

`draft` — **present**. Float constructor **out** until float gate.

---

<a id="json.get"></a>
## Object / array ops

```vir
json.get(obj: JsonValue, key: string) -> Option(JsonValue)
json.set(obj: JsonValue, key: string, val: JsonValue)
json.has(obj: JsonValue, key: string) -> bool
json.at(arr: JsonValue, idx: int) -> JsonValue
json.push(arr: JsonValue, item: JsonValue)
json.len(val: JsonValue) -> int
json.key(obj: JsonValue, idx: int) -> string
json.value(obj: JsonValue, idx: int) -> JsonValue
```

### Status

`draft` / `proposed` (`key` / `value` rename). `at` out-of-range → null-value
behavior may be **debt** vs `Option(JsonValue)`.

---

<a id="json.asInt"></a>
## Tag / unbox / typed get

```vir
json.kind(val: JsonValue) -> int
json.asInt(val: JsonValue) -> int
json.asString(val: JsonValue) -> string
json.asBool(val: JsonValue) -> bool
json.isNull(val: JsonValue) -> bool
json.getInt(obj: JsonValue, key: string, default: int) -> int
json.getStr(obj: JsonValue, key: string, default: string) -> string
json.getBool(obj: JsonValue, key: string, default: bool) -> bool
```

Wrong-tag unbox behavior (e.g. `asInt` on non-Number) = **audit** — do not
document as panic without evidence.

### Status

`proposed` renames; getters **present**.

---

<a id="json.fromInts"></a>
## Array bridges

```vir
json.fromInts(values) -> JsonValue
json.fromStrings(values) -> JsonValue
json.fromBools(values) -> JsonValue
```

### Status

`draft` — **present**. Exact `[T]` / `Vec(T)` parameter spelling follows
language array form in source.

---

## Open questions

1. Map parse errors onto [`Error`](error.md) / `ErrorKind` without a parallel
   public error type?
2. `json.at` → `Option(JsonValue)` vs null-`JsonValue`?
3. Post–float-gate: store JSON numbers as `float`, decimal string, or dual?

## Implementation readiness

1. Deduplicate `json.vri` / `data/json.vri` under one public `json` load path.
2. Apply camelCase renames; merge `count`/`size` → `len`.
3. Audit RFC number edge cases vs int-only storage; keep float path gated.
4. Close error mapping to [`error`](error.md).
5. Do not mark `stable` until conformance suite + error mapping land.
