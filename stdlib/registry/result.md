---
module: result
title: Result
summary: Result of (T, E) — Ok(T) or Err(E); namespace result.*; language-level constructors.
source:
  - name: result
    path: vir/core/result.vri
  - name: compiler.result.def
    path: vir/compiler/result.vri
status: closed
notes: >-
  Design closed (R1–R3). Callable HOF → planned. result.all fail-fast + ownership;
  planned until reclaim-on-error proven. A unchanged. No .vri (Q5).
---

# Result

`Result of (T, E)` is either a successful value of type `T` or an error value of
type `E`.

```text
Result of (T, E)
├── Ok(T)
└── Err(E)
```

```text
Result  ≠  throw
Result  ≠  panic
```

`Err(E)` is a **recoverable, value-level** error channel. `panic` / `throw`
remain for invariant violation, bounds failure, and explicit abort — as locked
for `io` / `fs`.

Constructors are **language-level** enum variants:

```vir
Ok(value)
Err(error)
# Result.Ok / Result.Err when qualified
```

No `result.ok(…)` / `result.err(…)` constructors.

Operations use namespace **`result.*`**:

```vir
result.isOk(r)
result.mapErr(r, f)
result.recover(r, f)
```

Free names (`is_ok`, `unwrap`, …) are implementation / prelude only.

## Boundary

| In `result` | Not in `result` |
|---|---|
| Ok/Err algebra + convert to Option | Constructors `result.ok` / `result.err` |
| `mapErr` / `recover` / `error` | `Error` / `IoError` types → **error** registry *(next)* |
| `all` over `Vec` of results | `andThen` alias |
| | `inspect` / `flatten` / `transpose` — **out** (no source; do not inflate) |
| | Free `is_ok` / `unwrap` as public aliases |
| | Replacing I/O failures with `throw` |

Bridge with Option (already locked):

```text
option.toResult(opt, error)   Option → Result
result.toOption(r)            Result → Option  (success side)
result.error(r)               Result → Option  (error side)
```

Primary consumers: `fs.*`, `File.*`, `Reader` / `Writer`, and other fallible
stdlib APIs returning `Result`.

## Generic contract (closed)

**Semantic contract:** `Result of (T, E)` with success type `T` and error type `E`.
When the error type is the stdlib default [`Error`](error.md), write **`Result of (T)`**.

Bare source `enum Result:` with erased payloads is an **implementation
mechanism**. Registry does not invent unsupported generic syntax in examples;
meaning remains parameterized `Result`.


## Naming (CORE SPEC)

| Source / previous | Canonical |
|---|---|
| `unwrap_or` / was `result.or` | **`result.unwrapOr`** |
| `unwrap_or_else` | **`result.orWith`** · planned (callable) |
| `or_else` | **`result.recover`** |

## Decisions R1–R3 (locked)

| ID | Decision |
|---|---|
| R1 | HOF needing callable ABI (`map` / `mapErr` / `flatMap` / `recover` / `orWith`) → **`planned`**. Stay in target design; not `stable` until ABI confirmed. Align with option O2. |
| R2 | Keep `result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)` in target surface; impl depends on `vec` + error ownership. |
| R3 | Keep `Result of (T)`, `Result of (T, E)`, and bare `Result` for void success. **Do not reopen A.** |

### `result.all` semantics (locked)

Fail-fast in element order:

1. All `Ok` → `Ok` of collected success payloads (moved, not owning-copied).
2. First `Err(e)` → return that `e`; do not continue.

If the implementation cannot reclaim already-processed success payloads when a
later element fails, `result.all` remains **`planned`**. Do not mark `stable` by
ignoring retained resources.

## Public surface (closed)


```text
result
├── isOk · isErr
├── unwrap · unwrapErr · expect · unwrapOr
├── toOption · error
│
├── orWith · map · mapErr · flatMap · recover   # planned · callable ABI (R1)
└── all                                          # planned · reclaim gate (R2)
```

### Semantic families

| Family | Shape |
|---|---|
| `unwrapOr` / `orWith` | `Result` → success `T` |
| `map` / `mapErr` / `flatMap` / `recover` | `Result` → `Result` |
| `toOption` / `error` | `Result` → `Option` |
| `all` | `Vec` of `Result` → `Result` of `Vec` |

### Extract / fallback (vs Option)

```text
result.unwrapOr(r, default)     Ok(v) → v; Err(_) → default
result.orWith(r, f)       Ok(v) → v; Err(e) → f(e)
```

**Contract difference from Option:**

```text
option.orWith : () → T      (no payload on None)
result.orWith : E → T       (callback receives the error)
```

### Recovery (not value fallback)

```text
result.recover(r, f)      Ok(v) → Ok(v); Err(e) → f(e)
```

`f(e)` returns **`Result`**. Do not name this `orElse` — avoids clash with
value-level `or` / `orWith`.

Three non-overlapping operations:

```text
result.unwrapOr(r, value)       Result → T
result.orWith(r, f)       Result → T
result.recover(r, f)      Result → Result
```

### Map pair

```text
result.map(r, f)          Ok(v) → Ok(f(v)); Err(e) → Err(e)
result.mapErr(r, f)       Ok(v) → Ok(v);    Err(e) → Err(f(e))
```

`mapErr` is **core** (domain remapping of I/O / low-level errors).

### FlatMap

```text
result.flatMap(r, f)      Ok(v) → f(v); Err(e) → Err(e)
```

`and_then` is **not** a separate public name — merge into `flatMap` (same as
`option.flatMap` vocabulary).

## Migration map

| Current | Public | Returns | Action |
|---|---|---|---|
| `Ok` / `Err` | `Ok` / `Err` | constructors | **keep** language-level |
| `is_ok` | `result.isOk` | `bool` | **rename** |
| `is_err` | `result.isErr` | `bool` | **rename** |
| `unwrap` | `result.unwrap` | `T` or panic | **rename** |
| `unwrap_err` | `result.unwrapErr` | `E` or panic | **rename** |
| `expect` | `result.expect` | `T` or panic | **rename** |
| `unwrap_or` | `result.unwrapOr` | `T` | **rename** |
| `unwrap_or_else` | `result.orWith` | `T` (`f(e)`) | **rename** |
| `map` | `result.map` | `Result` | **rename** |
| `map_err` | `result.mapErr` | `Result` | **rename** · **core** |
| `flat_map` | `result.flatMap` | `Result` | **rename** |
| `and_then` | `result.flatMap` | `Result` | **merge** / remove alias |
| `or_else` | `result.recover` | `Result` | **rename** |
| `result_to_option` / `ok` | `result.toOption` | `Option` | **merge** → one name |
| `err` | `result.error` | `Option` of `E` | **rename** |
| `try_all` | `result.all` | `Result` of `Vec` | **rename** |

## Not in this surface

```text
andThen
ok          (as public name — use toOption)
orElse
inspect / inspectErr / flatten / transpose
```

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `result.isOk` | `result.isOk` | `result.isOk(r: Result) -> bool` | proposed |
| `result.isErr` | `result.isErr` | `result.isErr(r: Result) -> bool` | proposed |
| `result.unwrap` | `result.unwrap` | `result.unwrap(r: Result) -> T` | proposed |
| `result.unwrapErr` | `result.unwrapErr` | `result.unwrapErr(r: Result) -> E` | proposed |
| `result.expect` | `result.expect` | `result.expect(r: Result, msg: string) -> T` | proposed |
| `result.unwrapOr` | `result.unwrapOr` | `result.unwrapOr(r: Result, default: T) -> T` | proposed |
| `result.orWith` | `result.orWith` | `result.orWith(r: Result, f: E -> T) -> T` | planned |
| `result.map` | `result.map` | `result.map(r: Result of (T, E), f: …) -> Result of (…)` | planned |
| `result.mapErr` | `result.mapErr` | `result.mapErr(r: Result of (T, E), f: …) -> Result of (…)` | planned |
| `result.flatMap` | `result.flatMap` | `result.flatMap(r: Result of (T, E), f: …) -> Result of (…)` | planned |
| `result.recover` | `result.recover` | `result.recover(r: Result of (T, E), f: …) -> Result of (…)` | planned |
| `result.toOption` | `result.toOption` | `result.toOption(r: Result of (T, E)) -> Option of (T)` | proposed |
| `result.error` | `result.error` | `result.error(r: Result of (T, E)) -> Option of (E)` | proposed |
| `result.all` | `result.all` | `result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)` | planned |

---

<a id="result.isOk"></a>
## `result.isOk`

<!--
id: result.isOk
api: result.isOk
previous: is_ok
-->

```vir
result.isOk(r: Result) -> bool
```

`true` iff `r` is `Ok(_)`.

### Status

`proposed` — **present** as `is_ok`.

### Implementation mapping

`vir/core/result.vri` → `is_ok`.

### See also

- `result.isErr`

---

<a id="result.isErr"></a>
## `result.isErr`

<!--
id: result.isErr
api: result.isErr
previous: is_err
-->

```vir
result.isErr(r: Result) -> bool
```

`true` iff `r` is `Err(_)`.

### Status

`proposed` — **present** as `is_err`.

### Implementation mapping

`vir/core/result.vri` → `is_err`.

### See also

- `result.isOk`

---

<a id="result.unwrap"></a>
## `result.unwrap`

<!--
id: result.unwrap
api: result.unwrap
previous: unwrap
-->

```vir
result.unwrap(r: Result) -> T
```

| Case | Result |
|---|---|
| `Ok(v)` | `v` |
| `Err(_)` | **panic** |

Valid primitive; not preferred normal flow when errors are expected — prefer
`or` / `orWith` / `recover` / `case`.

### Status

`proposed` — **present** as free `unwrap`.

### Implementation mapping

`vir/core/result.vri` → `unwrap`.

### See also

- `result.expect`
- `result.unwrapErr`

---

<a id="result.unwrapErr"></a>
## `result.unwrapErr`

<!--
id: result.unwrapErr
api: result.unwrapErr
previous: unwrap_err
-->

```vir
result.unwrapErr(r: Result) -> E
```

| Case | Result |
|---|---|
| `Err(e)` | `e` |
| `Ok(_)` | **panic** |

### Status

`proposed` — **present** as `unwrap_err`.

### Implementation mapping

`vir/core/result.vri` → `unwrap_err`.

### See also

- `result.error`
- `result.unwrap`

---

<a id="result.expect"></a>
## `result.expect`

<!--
id: result.expect
api: result.expect
previous: expect
-->

```vir
result.expect(r: Result, msg: string) -> T
```

Same as `unwrap` with custom panic message.

### Status

`proposed` — **present** as `expect`.

### Implementation mapping

`vir/core/result.vri` → `expect`.

### See also

- `result.unwrap`

---

<a id="result.unwrapOr"></a>
## `result.unwrapOr`

<!--
id: result.unwrapOr
api: result.unwrapOr
previous: unwrap_or
-->

```vir
result.unwrapOr(r: Result, default: T) -> T
```

| Case | Result |
|---|---|
| `Ok(v)` | `v` |
| `Err(_)` | `default` |

### Status

`proposed` — **present** as `unwrap_or`.

### Implementation mapping

`vir/core/result.vri` → `unwrap_or`.

### See also

- `result.orWith`
- `result.recover`

---

<a id="result.orWith"></a>
## `result.orWith`

<!--
id: result.orWith
api: result.orWith
previous: unwrap_or_else
-->

```vir
result.orWith(r: Result, f: …) -> T
```

| Case | Result |
|---|---|
| `Ok(v)` | `v` |
| `Err(e)` | `f(e)` |

### Semantics

Returns **`T`**. Callback receives **`E`** — unlike `option.orWith` which takes
no absence payload.

### Status

`proposed` — **present** as `unwrap_or_else`.

### Implementation mapping

`vir/core/result.vri` → `unwrap_or_else`.

### See also

- `result.unwrapOr`
- `result.recover`

---

<a id="result.map"></a>
## `result.map`

<!--
id: result.map
api: result.map
previous: map
-->

```vir
result.map(r: Result of (T, E), f: (T) -> U) -> Result of (U, E)
```

| Case | Result |
|---|---|
| `Ok(v)` | `Ok(f(v))` |
| `Err(e)` | `Err(e)` |

### Status

`proposed` — **present** as `map`.

### Implementation mapping

`vir/core/result.vri` → `map`.

### See also

- `result.mapErr`
- `result.flatMap`

---

<a id="result.mapErr"></a>
## `result.mapErr`

<!--
id: result.mapErr
api: result.mapErr
previous: map_err
-->

```vir
result.mapErr(r: Result of (T, E), f: (E) -> F) -> Result of (T, F)
```

| Case | Result |
|---|---|
| `Ok(v)` | `Ok(v)` |
| `Err(e)` | `Err(f(e))` |

### Semantics

**Core.** Remap low-level / I/O errors into domain errors without touching
success values.

### Status

`proposed` — **present** as `map_err`.

### Implementation mapping

`vir/core/result.vri` → `map_err`.

### See also

- `result.map`
- `result.recover`

---

<a id="result.flatMap"></a>
## `result.flatMap`

<!--
id: result.flatMap
api: result.flatMap
previous: flat_map, and_then
-->

```vir
result.flatMap(r: Result of (T, E), f: (T) -> Result of (U, E)) -> Result of (U, E)
```

| Case | Result |
|---|---|
| `Ok(v)` | `f(v)` (`f` returns `Result`) |
| `Err(e)` | `Err(e)` |

### Semantics

Sole public name for this operation. `and_then` is not canonical.

### Status

`proposed` — **present** as `flat_map` (+ alias `and_then` → remove public).

### Implementation mapping

`vir/core/result.vri` → `flat_map`.

### See also

- `result.map`
- `option.flatMap`

---

<a id="result.recover"></a>
## `result.recover`

<!--
id: result.recover
api: result.recover
previous: or_else
-->

```vir
result.recover(r: Result of (T, E), f: (E) -> Result of (T, E)) -> Result of (T, E)
```

| Case | Result |
|---|---|
| `Ok(v)` | `Ok(v)` |
| `Err(e)` | `f(e)` (`f` returns `Result`) |

### Semantics

Stay in Result algebra while handling the error channel. Not value fallback
(`or` / `orWith`).

### Status

`proposed` — **present** as `or_else`.

### Implementation mapping

`vir/core/result.vri` → `or_else`.

### See also

- `result.orWith`
- `result.mapErr`

---

<a id="result.toOption"></a>
## `result.toOption`

<!--
id: result.toOption
api: result.toOption
previous: result_to_option, ok
-->

```vir
result.toOption(r: Result of (T, E)) -> Option of (T)
```

| Case | Result |
|---|---|
| `Ok(v)` | `Some(v)` |
| `Err(_)` | `None` |

### Semantics

Success-side conversion. Not named `result.ok` (reads like predicate /
constructor). Merges `result_to_option` and free `ok`.

### Status

`proposed` — **present** under two names.

### Implementation mapping

`vir/core/result.vri` → `result_to_option` / `ok`.

### See also

- `result.error`
- `option.toResult`

---

<a id="result.error"></a>
## `result.error`

<!--
id: result.error
api: result.error
previous: err
-->

```vir
result.error(r: Result of (T, E)) -> Option of (E)
```

| Case | Result |
|---|---|
| `Ok(_)` | `None` |
| `Err(e)` | `Some(e)` |

### Semantics

Error-side conversion → `Option` of `E`. Pair with `toOption`:

```text
result.toOption(r)  → Option of T
result.error(r)     → Option of E
```

### Status

`proposed` — **present** as `err`.

### Implementation mapping

`vir/core/result.vri` → `err`.

### See also

- `result.toOption`
- `result.unwrapErr`

---

<a id="result.all"></a>
## `result.all`

<!--
id: result.all
api: result.all
previous: try_all
-->

```vir
result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)
```

Aggregate a vector of results.

| Input | Output |
|---|---|
| all `Ok` | `Ok` of `Vec` of success values (order preserved) |
| any `Err` | **first** `Err` (short-circuit) |

### Semantics

Conceptual shape: collection of `Result` → `Result` of collection.
**First error wins.** Depends on locked `Vec` core — not a reason to defer.

Do not invent unsupported generic syntax in call sites; document meaning only.

### Status

`proposed` — **present** as `try_all`.

### Implementation mapping

`vir/core/result.vri` → `try_all` (may need alignment with `vec.get` /
namespace after Vec rename pass).

### See also

- `result.flatMap`
- [`vec.md`](vec.md)

---

## Implementation readiness

**Design status: closed** (R1–R3). Error payloads: [`error.md`](error.md).
Callable HOF and `all` stay `planned` until ABI / reclaim gates clear.
No `.vri` until authorized (Q5).
