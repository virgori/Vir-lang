# `json` — danh sách tên hàm

Source: `stdlib/vir/json.vri` (sync `data/json.vri`)  
Namespace: global `json` (`JsonNamespace`) · `include json`

## Canonical (trên `json`)

| Tên | Chữ ký (rút gọn) | Ghi chú |
|---|---|---|
| `json.parse` | `(s) -> Result of (JsonValue)` | |
| `json.stringify` | `(val) -> string` | compact |
| `json.pretty` | `(val) -> string` | indent 2 |
| `json.null` | `() -> JsonValue` | |
| `json.bool` | `(b) -> JsonValue` | |
| `json.number` | `(n) -> JsonValue` | int |
| `json.string` | `(s) -> JsonValue` | |
| `json.array` | `() -> JsonValue` | |
| `json.object` | `() -> JsonValue` | |
| `json.get` | `(obj, key) -> Option of (JsonValue)` | |
| `json.set` | `(obj, key, val)` | |
| `json.has` | `(obj, key) -> bool` | |
| `json.at` | `(arr, idx) -> Option of (JsonValue)` | |
| `json.push` | `(arr, item)` | |
| `json.len` | `(val) -> int` | |
| `json.kind` | `(val) -> int` | |
| `json.asInt` | `(val) -> int` | |
| `json.asString` | `(val) -> string` | |
| `json.asBool` | `(val) -> bool` | |
| `json.isNull` | `(val) -> bool` | |
| `json.asArray` | `(val) -> Option of (JsonValue)` | tag Array |
| `json.asObject` | `(val) -> Option of (JsonValue)` | tag Object |
| `json.key` | `(obj, idx) -> string` | |
| `json.value` | `(obj, idx) -> JsonValue` | |
| `json.getInt` | `(obj, key, default) -> int` | |
| `json.getStr` | `(obj, key, default) -> string` | |
| `json.getBool` | `(obj, key, default) -> bool` | |
| `json.fromInts` | `(values) -> JsonValue` | |
| `json.fromStrings` | `(values) -> JsonValue` | |
| `json.fromBools` | `(values) -> JsonValue` | |

## Alias (giữ migration)

| Tên | → Canonical |
|---|---|
| `json.read` | `json.parse` |
| `json.write` | `json.stringify` |
| `json.as_int` | `json.asInt` |
| `json.as_string` | `json.asString` |
| `json.as_bool` | `json.asBool` |
| `json.is_null` | `json.isNull` |
| `json.count` / `json.size` | `json.len` |

## Planned (chưa có trong source)

| Tên | Ghi chú |
|---|---|
| `json.numberFloat` | float gate |
| `json.asFloat` | float gate |

## Free exports (cùng tên, gọi không qua `json.`)

`kind`, `as_int`, `asInt`, `as_string`, `asString`, `as_bool`, `asBool`,
`is_null`, `isNull`, `asArray`, `asObject`, `len`, `count`, `size`, `at`,
`get`, `set`, `push`, `has`, `key`, `value`, `getInt`, `getStr`, `getBool`,
`fromInts`, `fromStrings`, `fromBools`
