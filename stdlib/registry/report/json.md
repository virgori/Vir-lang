# Report — `json`

Source: `stdlib/vir/json.vri` (sync `data/json.vri`)  
Registry: [`../json.md`](../json.md)

| API | Status | Notes |
|---|---|---|
| `json.parse` | done | previous: `read` (alias) |
| `json.stringify` | done | previous: `write` (alias) |
| `json.pretty` | done | |
| constructors (`null`…`object`) | done | |
| `json.get` / `set` / `has` / `push` / `len` | done | |
| `json.at` | done | → `Option(JsonValue)` |
| `json.asInt` / `asString` / `asBool` / `isNull` | done | snake aliases kept |
| `json.asArray` / `asObject` | done | `Option(JsonValue)` when tag matches |
| `json.numberFloat` / `asFloat` | planned | float gate |
| error → `Error` / ownership | blocked | design gates |
| dual `json.vri` / `data/json.vri` | partial | content synced; resolver dedup later |

**Tests touched:** `tests/std_json_test.vri`, `tests/test_json_extensions.vri`, `tests/test_backend_sample.vri`
