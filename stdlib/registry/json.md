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
status: closed
notes: >-
  Design closed (D1–D5, Q3–Q4, CORE SPEC). Canonical parse/stringify (CORE SPEC).
  Ownership/float/error-map = gates. Duplicate json paths = gap. No .vri (Q5).
---

# Json

RFC 8259 JSON as an in-memory **`JsonValue`** tree under namespace **`json`**.

```vir
let r = json.parse(text)           # Result(JsonValue)
let s = json.stringify(val)      # compact string
let p = json.pretty(val)         # indent 2
json.set(obj, "port", json.number(8080))
```

Physical modules today: `vir/json.vri` and `vir/data/json.vri` (alias).
**Public docs use `json.*` only** — users never need `data.json` as a second API.

## Decisions D1–D5 (locked) · Q3–Q4 (locked)

## Naming (CORE SPEC)

| Previous / source | Canonical |
|---|---|
| `json.read` / `json_parse` | **`json.parse`** |
| `json.write` / `json_stringify` | **`json.stringify`** |
| `json.pretty` | keep |
| `asArray` / `asObject` | **`planned`** — add to surface; verify in source at implement time |

## Ownership gate

`JsonValue` ownership must be audited before APIs that return or copy values
are `stable`. No shallow-copy of dynamically owned payloads. Design may be
**closed** while this gate remains open.

Do **not** auto-promote `json` to `stable` while float, ownership, or related
gates remain open. **Q7:** finish this file before opening the **csv** wave;
TOML / YAML / XML later.

## Boundary

| In `json` | Not in `json` |
|---|---|
| Parse / stringify / tree ops | Streaming SAX / pull parsers |
| Object / array mutators on `JsonValue` | Schema validation language |
| Dual int + float numbers (float after gate) | Silent int→float coercion |
| | YAML / TOML / XML (separate namespaces) |
| | Distinct public semantics for `count` / `size` |

## Types (closed inventory)

```text
JsonType     # Null | Bool | Number | Str | Array | Object
JsonValue    # tagged tree node
```

`JsonParser` / `JsonBuf` are **implementation** — not public surface.

## Number model (locked — D3 · Q3 · Q4)

| Fact | Contract |
|---|---|
| Integer ctor | `json.number(n: int) -> JsonValue` |
| Float ctor | `json.numberFloat(f: float) -> JsonValue` — **planned** after float gate (Q4) |
| Unbox | `json.asInt` · `json.asFloat` (**planned** with float path) |
| Parse int in domain | → int-backed Number |
| Parse int **out of domain** | → `Err` `InvalidData` (**Q3**) — never silent float |
| Parse fractional / exp | → float path **only after** float gate; until then treat as gap / reject per impl policy documented as debt |
| Forbidden | Overloading `json.number`; silent int→float |

**Source today:** int-only storage — **implementation gap** vs dual contract.

RFC 8259 allows arbitrary precision; Vir’s locked model is **dual int + float**
with Q3/Q4. Exactness for integers outside domain = **reject**, not demote.

## Failure model (locked — D1)

```text
json.parse(s) -> Result(JsonValue)
```

`Err` uses [`Error`](error.md) with **`ErrorKind.InvalidData`**, plus **byte
offset**, **line**, **column**, and **reason** string. Do **not** invent a new
`ErrorKind`. Source may still use `vir.data.error` parse-error entities —
mapping onto `Error` + `InvalidData` is an **implementation gap**.

Trailing garbage after one value → error. Nesting depth limit **128** (present).

## Public surface (proposed)

```text
json
├── parse · stringify · pretty
│
├── null · bool · number · numberFloat · string · array · object
│
├── get · set · has
├── at · push
├── len                    # only canonical length (D5)
├── key · value
│
├── kind
├── asInt · asFloat · asString · asBool · isNull
├── asArray · asObject              # planned · verify at implement
│
├── getInt · getStr · getBool
└── fromInts · fromStrings · fromBools
```

## Naming (locked — D4 / D5)

| Current | Canonical | Action |
|---|---|---|
| `as_int` / `as_string` / `as_bool` / `is_null` | `asInt` / `asString` / `asBool` / `isNull` | **rename**; snake = alias → remove |
| — | `asFloat` | **new** with float path |
| — | `numberFloat` | **planned** (Q4) · no `number` overload |
| `count` / `size` | `len` | **aliases** during migrate → **remove** |
| `json_obj_key_at` / `val_at` | `json.key` / `json.value` | **rename** + ns |
| free `kind` / `len` / … | `json.*` only | drop free public aliases when map applied |

## Semantics notes (locked)

| Op | Contract |
|---|---|
| `get` | `Option(JsonValue)` — missing key → `None` |
| `has` | `bool` |
| `set` | upsert by key |
| `at` | `Option(JsonValue)` — `None` if wrong tag / OOB; `Some(null)` if JSON null (D2) |
| `push` | append to array |
| `len` | array length or object entry count; else `0` |
| `getInt` / `getStr` / `getBool` | typed get with **default** on missing / wrong type |
| `stringify` / `pretty` | compact / indent **2** |

## Migration map

| Current | Public | Action |
|---|---|---|
| `json_parse` | `json.parse` | keep ns · free → internal |
| `json_stringify` | `json.stringify` | keep |
| `json_stringify_pretty` | `json.pretty` | keep |
| `json_null` … `json_object` | `json.null` … | keep |
| `json_obj_get` / `set` | `json.get` / `set` | keep |
| `json_arr_get` | `json.at` → `Option(JsonValue)` | **behavior change** (D2) |
| `as_int` … | `asInt` … | **rename** + snake alias |
| `count` / `size` | `len` | **alias** → remove (D5) |
| `json_obj_key_at` / `val_at` | `json.key` / `json.value` | **rename** + ns |
| `data.json` include | `json` | **alias** only |
| float Number / `asFloat` / `numberFloat` | — | **planned** after float gate (Q4) |
| parse-error entity | `Error` + `InvalidData` | **map** (D1) |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `json.JsonType` | `JsonType` | enum | draft |
| `json.JsonValue` | `JsonValue` | entity | draft |
| `json.parse` | `json.parse` | `json.parse(s: string) -> Result(JsonValue)` | draft |
| `json.stringify` | `json.stringify` | `json.stringify(val: JsonValue) -> string` | draft |
| `json.pretty` | `json.pretty` | `json.pretty(val: JsonValue) -> string` | draft |
| `json.null` | `json.null` | `json.null() -> JsonValue` | draft |
| `json.bool` | `json.bool` | `json.bool(b: bool) -> JsonValue` | draft |
| `json.number` | `json.number` | `json.number(n: int) -> JsonValue` | draft |
| `json.numberFloat` | `json.numberFloat` | `json.numberFloat(f: float) -> JsonValue` | planned |
| `json.string` | `json.string` | `json.string(s: string) -> JsonValue` | draft |
| `json.array` | `json.array` | `json.array() -> JsonValue` | draft |
| `json.object` | `json.object` | `json.object() -> JsonValue` | draft |
| `json.get` | `json.get` | `json.get(obj: JsonValue, key: string) -> Option(JsonValue)` | draft |
| `json.set` | `json.set` | `json.set(obj: JsonValue, key: string, val: JsonValue)` | draft |
| `json.has` | `json.has` | `json.has(obj: JsonValue, key: string) -> bool` | draft |
| `json.at` | `json.at` | `json.at(arr: JsonValue, idx: int) -> Option(JsonValue)` | proposed |
| `json.push` | `json.push` | `json.push(arr: JsonValue, item: JsonValue)` | draft |
| `json.len` | `json.len` | `json.len(val: JsonValue) -> int` | draft |
| `json.key` | `json.key` | `json.key(obj: JsonValue, idx: int) -> string` | proposed |
| `json.value` | `json.value` | `json.value(obj: JsonValue, idx: int) -> JsonValue` | proposed |
| `json.kind` | `json.kind` | `json.kind(val: JsonValue) -> int` | draft |
| `json.asInt` | `json.asInt` | `json.asInt(val: JsonValue) -> int` | proposed |
| `json.asFloat` | `json.asFloat` | `json.asFloat(val: JsonValue) -> float` | planned |
| `json.asArray` | `json.asArray` | `json.asArray(val: JsonValue) -> …` · shape **verify at implement** | planned |
| `json.asObject` | `json.asObject` | `json.asObject(val: JsonValue) -> …` · shape **verify at implement** | planned |
| `json.asString` | `json.asString` | `json.asString(val: JsonValue) -> string` | proposed |
| `json.asBool` | `json.asBool` | `json.asBool(val: JsonValue) -> bool` | proposed |
| `json.isNull` | `json.isNull` | `json.isNull(val: JsonValue) -> bool` | proposed |
| `json.getInt` | `json.getInt` | `json.getInt(obj, key, default: int) -> int` | draft |
| `json.getStr` | `json.getStr` | `json.getStr(obj, key, default: string) -> string` | draft |
| `json.getBool` | `json.getBool` | `json.getBool(obj, key, default: bool) -> bool` | draft |
| `json.fromInts` | `json.fromInts` | `json.fromInts(values) -> JsonValue` | draft |
| `json.fromStrings` | `json.fromStrings` | `json.fromStrings(values) -> JsonValue` | draft |
| `json.fromBools` | `json.fromBools` | `json.fromBools(values) -> JsonValue` | draft |

---

<a id="json.parse"></a>
## `json.parse`

<!--
id: json.parse
api: json.parse
previous: json.read
-->

```vir
json.parse(s: string) -> Result(JsonValue)
```

Parse one JSON value from `s`. Trailing non-whitespace → error. Empty input →
error (present).

### Errors

`Err` → [`Error`](error.md) with `ErrorKind.InvalidData`, offset / line / col /
reason (D1). Source mapping = **implementation gap**.

### Status

`draft` — **present** as `json.parse` / `json_parse`.

### See also

- [`json.stringify`](#json.stringify)

---

<a id="json.stringify"></a>
## `json.stringify` / `json.pretty`

<!--
id: json.stringify
api: json.stringify
previous: json.write
-->

```vir
json.stringify(val: JsonValue) -> string
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
json.numberFloat(f: float) -> JsonValue   # planned · Q4 · float gate
json.string(s: string) -> JsonValue
json.array() -> JsonValue
json.object() -> JsonValue
```

**Q4:** no overload of `number`. Source today = int only (**gap**).

### Status

`draft` — **present** (`number`). `numberFloat` **planned**.

---

<a id="json.at"></a>
## Object / array ops

```vir
json.get(obj: JsonValue, key: string) -> Option(JsonValue)
json.set(obj: JsonValue, key: string, val: JsonValue)
json.has(obj: JsonValue, key: string) -> bool
json.at(arr: JsonValue, idx: int) -> Option(JsonValue)
json.push(arr: JsonValue, item: JsonValue)
json.len(val: JsonValue) -> int
json.key(obj: JsonValue, idx: int) -> string
json.value(obj: JsonValue, idx: int) -> JsonValue
```

`at` (D2): `None` if not an array or index out of range; `Some(v)` including
`Some(json.null())` for JSON null. **Source today** returns null-`JsonValue` on
OOB — **gap** vs contract. Ownership of returned `JsonValue` = **impl gate**
before `stable`.

### Status

`proposed` (`at` change) / `draft` (others).

---

<a id="json.asInt"></a>
## Tag / unbox / typed get

```vir
json.kind(val: JsonValue) -> int
json.asInt(val: JsonValue) -> int
json.asFloat(val: JsonValue) -> float    # planned · float gate
json.asString(val: JsonValue) -> string
json.asBool(val: JsonValue) -> bool
json.isNull(val: JsonValue) -> bool
json.getInt(obj: JsonValue, key: string, default: int) -> int
json.getStr(obj: JsonValue, key: string, default: string) -> string
json.getBool(obj: JsonValue, key: string, default: bool) -> bool
```

Wrong-tag unbox behavior = **audit**. Snake aliases during migration (D4).

### Status

`proposed` renames; `asFloat` **planned**; getters **present**.

---

<a id="json.fromInts"></a>
## Array bridges

```vir
json.fromInts(values) -> JsonValue
json.fromStrings(values) -> JsonValue
json.fromBools(values) -> JsonValue
```

### Status

`draft` — **present**. Exact `[T]` / `Vec(T)` parameter spelling follows source.

---

---

<a id="json.asArray"></a>
## `json.asArray` / `json.asObject`

<!--
id: json.asArray
api: json.asArray
-->

```vir
json.asArray(val: JsonValue) -> …     # shape verify at implement
json.asObject(val: JsonValue) -> …    # shape verify at implement
```

Typed views / casts for array and object `JsonValue`s. Return type
(`Option` / `Result` / bare) and ownership of nested values — **verify at
implement** against source; do not invent until audited.

### Status

`planned`.

### See also

- `json.kind`
- `json.at` / `json.get`

---

## Implementation gaps (keep visible)

Contract ≠ source. Do not mark `stable` until closed:

1. `Option` / `Result` may still be unparameterized in source enums  
2. Trait / I/O signatures may still say bare `Result` where payload exists  
3. `unicode.category` accessor missing  
4. `parse_float` stub → `0`  
5. `json.vri` / `data/json.vri` duplicate load paths  
6. Unicode tables ≠ any official UCD release (`pre-UCD`)

Json-specific gaps: D1 error mapping; D2 `at` → `Option`; D3 float Number;
`JsonValue` ownership / copy semantics.

## Implementation readiness

**Design status: closed** (CORE SPEC + D1–D5 + Q3–Q4). Not implementation-stable.

Gates before any `stable` claim:
1. Dedup `json.vri` / `data/json.vri`
2. Error mapping → `Error` + `InvalidData`
3. `at` → `Option(JsonValue)` behavior
4. `JsonValue` ownership audit
5. Float Number / `numberFloat` / `asFloat` after float gate
6. CamelCase renames; drop `count`/`size`

`asArray`/`asObject` are **planned** — verify shapes at implement. No `.vri` until Q5.
