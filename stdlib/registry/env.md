---
module: env
title: Env
summary: Environment variables, argv, and path helpers — namespace-only; no exit/abort.
source:
  - name: env
    path: vir/env.vri
  - name: env.env
    path: vir/env/env.vri
status: closed
notes: >-
  Dot-style only via global `env`. exit/abort moved to process.* (see process.md).
  Free-function aliases removed from public API. Typed helpers target Option.
---

# Env

Environment **variables** plus light process-adjacent helpers (`args`, cwd/home/temp).
Public API is **namespace-only**: `env.<op>(…)`.

Lifecycle / subprocess / `exit` / `abort` → [`process`](process.md).
Streams → [`io`](io.md). Non-recoverable logic failure → [`panic`](panic.md).

## Boundary

| In `env` | Out |
|---|---|
| get / or / has / set / remove | Free-function aliases → **remove public** |
| int / bool / require | `env.str` → **remove** (duplicate of `get`) |
| args / name / cwd / home / temp | `exit` / `abort` → [`process`](process.md) |
| | spawn / wait / kill / Command → [`process`](process.md) |
| | Interactive CLI → `cli` |
| | Formatting → `format` |

`args` / `cwd` stay here as environment/context queries for the **current**
process; they are not a subprocess API.

## Public surface (closed)

```text
env
├── get
├── or
├── has
├── set
├── remove
│
├── int
├── bool
├── require
│
├── args
├── name
├── cwd
├── home
└── temp
```

```vir
env.get("HOME")
env.or("APP_MODE", "dev")
env.has("CI")

env.set("APP_MODE", "prod")
env.remove("APP_MODE")

env.args()
env.name()
env.cwd()
env.home()
env.temp()

env.int("PORT")
env.bool("DEBUG")
env.require("SECRET")

process.exit(0)    # not env.exit
```
## Migration map

| Current | Public | Impl note | Action |
|---|---|---|---|
| `get` / `env.get` | `env.get` | present | **remove** free alias |
| `get_or` / `env.get_or` | `env.or` | present | **rename** + remove free alias |
| `has` / `env.has` | `env.has` | present | keep ns; remove free alias |
| `set` / `env.set` | `env.set` | present → `Result` | keep ns; remove free alias |
| `remove` / `env.remove` | `env.remove` | present → `Result` | keep ns; remove free alias |
| `args` | `env.args` | present (free; not on entity today) | expose on `env`; remove free public |
| `program_name` | `env.name` | present | **rename** |
| `cwd` | `env.cwd` | present | keep; remove free public |
| `home_dir` | `env.home` | present | **rename** |
| `temp_dir` | `env.temp` | present | **rename** |
| `int(key, default)` | `env.int(key)` → `Option` | present with **default** | **change** semantics |
| `str` / `env.str` / `string` | — | alias of get-or-default | **remove** public |
| `bool(key, default)` | `env.bool(key)` → `Option` | present with **default** | **change** semantics |
| `require` | `env.require` | present → `Result` | keep ns |
| `exit` | `process.exit` | present | **move** — [`process.md`](process.md) |
| `abort` | `process.abort` | present | **move** |
| `keys` / `values` / `count` / `clear` / `vars` | — | present | **internal** or later inventory (not in closed surface) |
| `panic` / signals / `current_os`… | — | present | **out** (`panic` / other) |
| `env_int` free helper | — | present | **internal** |

## Typed helpers (target semantics)

| API | Return | Notes |
|---|---|---|
| `env.get(key)` | `Option` of `string` | missing → `None` |
| `env.or(key, fallback)` | `string` | value or fallback; never `Option` |
| `env.int(key)` | `Option` of `int` | parse fail / missing → `None` *(today uses default — change)* |
| `env.bool(key)` | `Option` of `bool` | parse fail / missing → `None` *(today uses default — change)* |
| `env.require(key)` | `Result` · `Ok(string)` / `Err(…)` | explicit failure when missing |

No public `env.str` — identical to `env.get` with no extra meaning.

Bool accepted tokens (keep current spirit of `env_bool`): case-insensitive
`true`/`1`/`yes`/`on` vs `false`/`0`/`no`/`off`; other → `None` under Option
semantics (today falls back to default).

## API

| ID | Symbol | Signature | Status | Impl |
|---|---|---|---|---|
| `env.get` | `env.get` | `env.get(key: string) -> Option(string)` | proposed | rename surface (drop free `get`) |
| `env.or` | `env.or` | `env.or(key: string, fallback: string) -> string` | proposed | rename from `get_or` |
| `env.has` | `env.has` | `env.has(key: string) -> bool` | proposed | present |
| `env.set` | `env.set` | `env.set(key: string, value: string) -> Result` | proposed | void success · form pending audit |
| `env.remove` | `env.remove` | `env.remove(key: string) -> Result` | proposed | void success · form pending audit |
| `env.int` | `env.int` | `env.int(key: string) -> Option(int)` | proposed | change from default-arg |
| `env.bool` | `env.bool` | `env.bool(key: string) -> Option(bool)` | proposed | change from default-arg |
| `env.require` | `env.require` | `env.require(key: string) -> Result(string)` | proposed | present |
| `env.args` | `env.args` | `env.args() -> Vec(string)` | proposed | present free → ns method |
| `env.name` | `env.name` | `env.name() -> string` | proposed | rename `program_name` |
| `env.cwd` | `env.cwd` | `env.cwd() -> string` | proposed | present |
| `env.home` | `env.home` | `env.home() -> string` | proposed | rename `home_dir` |
| `env.temp` | `env.temp` | `env.temp() -> string` | proposed | rename `temp_dir` |

---

<a id="env.get"></a>
## `env.get`

<!--
id: env.get
api: env.get
previous: get
-->

```vir
env.get(key: string) -> Option(string)
```

Look up environment variable `key`.

### Parameters

#### `key: string`

Variable name.

### Returns

`Option` — `Some(string)` if present; `None` if missing.

### Errors

None as `Result`; absence is `None`.

### Example

```vir
let opt = env.get("HOME")
```

### See also

- `env.or`
- `env.require`

---

<a id="env.or"></a>
## `env.or`

<!--
id: env.or
api: env.or
previous: get_or
-->

```vir
env.or(key: string, fallback: string) -> string
```

Environment value **or** fallback. Clearer than `get_or` under namespace `env`.

### Parameters

#### `key: string`

Variable name.

#### `fallback: string`

Returned when missing; not written into the environment.

### Returns

`string` — existing value or `fallback`.

### Errors

None.

### Example

```vir
let mode = env.or("APP_MODE", "dev")
```

### See also

- `env.get`

---

<a id="env.has"></a>
## `env.has`

<!--
id: env.has
api: env.has
previous: has
-->

```vir
env.has(key: string) -> bool
```

Whether `key` is present (including empty value).

### Parameters

#### `key: string`

Variable name.

### Returns

`bool`

### Errors

None.

### Example

```vir
if env.has("CI") do
    io.println("ci")
end
```

---

<a id="env.set"></a>
## `env.set`

<!--
id: env.set
api: env.set
previous: set
-->

```vir
env.set(key: string, value: string) -> Result
```

Define or update `key`.

### Parameters

#### `key: string`

Non-empty; must not contain `=` or NUL (current validation).

#### `value: string`

New value; must not contain NUL.

### Returns

`Result` — `Ok` / `Err` with validation or set failure.

### Errors

Empty name; illegal characters; implementation failure.

### Example

```vir
env.set("APP_MODE", "prod")
```

---

<a id="env.remove"></a>
## `env.remove`

<!--
id: env.remove
api: env.remove
previous: remove
-->

```vir
env.remove(key: string) -> Result
```

Unset `key`.

### Parameters

#### `key: string`

Name to remove.

### Returns

`Result`

### Errors

Implementation-defined unset failure.

### Example

```vir
env.remove("TMP_FLAG")
```

---

<a id="env.int"></a>
## `env.int`

<!--
id: env.int
api: env.int
previous: int
-->

```vir
env.int(key: string) -> Option(int)
```

Parse `key` as integer.

### Parameters

#### `key: string`

Variable name.

### Returns

`Option` — `Some(int)` if present and parseable; `None` if missing or invalid.

### Errors

None as `Result`; soft failure is `None`.

### Example

```vir
let port = env.int("PORT")
```

### Notes

**Semantics change:** today `int(key, default) -> int`. Target drops default;
use `env.or` + parse, or unwrap `Option`, for fallbacks.

---

<a id="env.bool"></a>
## `env.bool`

<!--
id: env.bool
api: env.bool
previous: bool
-->

```vir
env.bool(key: string) -> Option(bool)
```

Parse `key` as boolean (accepted tokens above).

### Parameters

#### `key: string`

Variable name.

### Returns

`Option` — `Some(bool)` or `None` if missing / unrecognized.

### Errors

None as `Result`.

### Example

```vir
let dbg = env.bool("DEBUG")
```

### Notes

**Semantics change:** today `bool(key, default) -> bool`.

---

<a id="env.require"></a>
## `env.require`

<!--
id: env.require
api: env.require
previous: require
-->

```vir
env.require(key: string) -> Result(string)
```

Require `key` to be present; fail explicitly otherwise.

### Parameters

#### `key: string`

Variable name.

### Returns

`Result` — `Ok(string)` or `Err(…)` when missing (message today mentions the key).

### Errors

Missing variable.

### Example

```vir
let secret = env.require("SECRET")
```

---

<a id="env.args"></a>
## `env.args`

<!--
id: env.args
api: env.args
previous: args
-->

```vir
env.args() -> Vec
```

Process argument list. Index `0` is the program name when the host provides it.

### Parameters

None.

### Returns

`Vec` of `string` (exact vec type as implemented).

### Errors

None typical; may be empty.

### Example

```vir
let a = env.args()
```

### See also

- `env.name`
- [`process.exit`](process.md)

---

<a id="env.name"></a>
## `env.name`

<!--
id: env.name
api: env.name
previous: program_name
-->

```vir
env.name() -> string
```

Program name (`argv[0]`), or empty string if unavailable.

### Parameters

None.

### Returns

`string`

### Errors

None.

### Example

```vir
io.println(env.name())
```

---

<a id="env.cwd"></a>
## `env.cwd`

<!--
id: env.cwd
api: env.cwd
previous: cwd
-->

```vir
env.cwd() -> string
```

Current working directory path.

### Parameters

None.

### Returns

`string` — absolute path text as returned by the host.

### Errors

Today best-effort syscall; target may surface `Result` later — not closed here.

### Example

```vir
let dir = env.cwd()
```

---

<a id="env.home"></a>
## `env.home`

<!--
id: env.home
api: env.home
previous: home_dir
-->

```vir
env.home() -> string
```

User home directory (today via `HOME`, else `""`).

### Parameters

None.

### Returns

`string`

### Errors

None as `Result` today.

### Example

```vir
let h = env.home()
```

---

<a id="env.temp"></a>
## `env.temp`

<!--
id: env.temp
api: env.temp
previous: temp_dir
-->

```vir
env.temp() -> string
```

Temp directory (`TMPDIR` or platform default such as `/tmp`).

### Parameters

None.

### Returns

`string`

### Errors

None as `Result` today.

### Example

```vir
let t = env.temp()
```

---

<a id="env.exit"></a>
## `env.exit` — **removed from env**

<!--
id: env.exit
api: env.exit
previous: exit
status: removed
-->

Use [`process.exit`](process.md) / [`process.abort`](process.md).

```vir
process.exit(code: int)
```

Terminate the process with OS exit status `code`. Does not return.
**(Migrated out of `env`.)**
`0` = success by Unix convention.

### Parameters

#### `code: int`

Exit status (low bits may be all the parent sees).

### Returns

Does not return.

### Errors

None.

### Example

```vir
process.exit(0)
```

### Notes

Removed from `env` public surface — see [`process.md`](process.md).

## Open questions

1. Whether `env.cwd` should become `Result` when syscall fails.
2. Exact `Vec` element type documentation for `args` once collections public names settle.
3. `exit`/`abort` → [`process`](process.md) (done in design). `args`/`cwd` remain.
4. Public fate of `keys` / `values` / `count` / `clear` (useful but not in the closed minimal surface).

## Notes

- No free-function public aliases.
- No `.vri` renames until this map is accepted.
- `env.str` is **not** public.
