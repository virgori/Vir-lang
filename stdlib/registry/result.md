---
module: result
title: Result
summary: Result of (T, E) — Success(T) or Failure(E); receiver UFCS plus Result.all.
source:
  - name: result
    path: vir/core/result.vri
  - name: compiler.result.def
    path: vir/compiler/result.vri
status: closed
notes: >-
  Design closed (R1–R3). Callable HOF → planned. Result.all fail-fast + ownership;
  planned until reclaim-on-error proven. Canonical implementation symbols are
  present; receiver and type dispatch still depend on compiler UFCS support.
---

# Result

`Result of (T, E)` is either a successful value of type `T` or an error value of
type `E`.

```text
Result of (T, E)
├── Success(T)
└── Failure(E)
```

```text
Result  ≠  throw
Result  ≠  panic
```

`Failure(E)` is a **recoverable, value-level** error channel. `panic` / `throw`
remain for invariant violation, bounds failure, and explicit abort — as locked
for `io` / `fs`.

Constructors are **language-level** enum variants:

```vir
Result.Success(value)
Result.Failure(error)
```

No `result.ok(…)` / `result.err(…)` constructors.

Operations use receiver UFCS; aggregation is a type operation:

```vir
self.isSuccess()
self.mapFailure(f)
self.recover(f)
Result.all(results)
```

The free functions in `vir/core/result.vri` are the implementation targets for
UFCS; they are not a second public spelling.

## Boundary

| In `result` | Not in `result` |
|---|---|
| Success/Failure algebra + convert to Option | Constructors `result.ok` / `result.err` |
| `mapFailure` / `recover` / `error` | `Error` / `IoError` types → **error** registry *(next)* |
| `all` over `Vec` of results | `andThen` alias |
| | `inspect` / `flatten` / `transpose` — **out** (no source; do not inflate) |
| | Free `is_ok` / `unwrap` as public aliases |
| | Replacing I/O failures with `throw` |

Bridge with Option (already locked):

```text
option.toResult(opt, error)  Option → Result
self.toOption()              Result → Option  (success side)
self.error()                 Result → Option  (error side)
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
| `unwrap_or` / was `result.or` | **`self.unwrapOr`** |
| `unwrap_or_else` | **`self.orWith`** · planned (callable) |
| `or_else` | **`self.recover`** |

## Decisions R1–R3 (locked)

| ID | Decision |
|---|---|
| R1 | HOF needing callable ABI (`map` / `mapFailure` / `flatMap` / `recover` / `orWith`) → **`planned`**. Stay in target design; not `stable` until ABI confirmed. Align with option O2. |
| R2 | Keep `Result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)` in target surface; impl depends on `vec` + error ownership. |
| R3 | Keep `Result of (T)`, `Result of (T, E)`, and bare `Result` for void success. **Do not reopen A.** |

### `Result.all` semantics (locked)

Fail-fast in element order:

1. All `Success` → `Success` of collected success payloads (moved, not owning-copied).
2. First `Failure(e)` → return that `e`; do not continue.

If the implementation cannot reclaim already-processed success payloads when a
later element fails, `Result.all` remains **`planned`**. Do not mark `stable` by
ignoring retained resources.

## Public surface (closed)


```text
Result
├── Success · Failure
└── all                                      # planned · reclaim gate (R2)

self
├── isSuccess · isFailure
├── unwrap · unwrapFailure · expect · unwrapOr
├── toOption · error
└── orWith · map · mapFailure · flatMap · recover   # callable ABI (R1)
```

### Semantic families

| Family | Shape |
|---|---|
| `unwrapOr` / `orWith` | `Result` → success `T` |
| `map` / `mapFailure` / `flatMap` / `recover` | `Result` → `Result` |
| `toOption` / `error` | `Result` → `Option` |
| `all` | `Vec` of `Result` → `Result` of `Vec` |

### Extract / fallback (vs Option)

```text
self.unwrapOr(default)  Success(v) → v; Failure(_) → default
self.orWith(f)          Success(v) → v; Failure(e) → f(e)
```

**Contract difference from Option:**

```text
option.orWith : () → T      (no payload on None)
self.orWith : E → T       (callback receives the error)
```

### Recovery (not value fallback)

```text
self.recover(f)         Success(v) → Success(v); Failure(e) → f(e)
```

`f(e)` returns **`Result`**. Do not name this `orElse` — avoids clash with
value-level `or` / `orWith`.

Three non-overlapping operations:

```text
self.unwrapOr(value)    Result → T
self.orWith(f)          Result → T
self.recover(f)         Result → Result
```

### Map pair

```text
self.map(f)             Success(v) → Success(f(v)); Failure(e) → Failure(e)
self.mapFailure(f)      Success(v) → Success(v);    Failure(e) → Failure(f(e))
```

`mapFailure` is **core** (domain remapping of I/O / low-level errors).

### FlatMap

```text
self.flatMap(f)         Success(v) → f(v); Failure(e) → Failure(e)
```

`and_then` is **not** a separate public name — merge into `flatMap` (same as
`option.flatMap` vocabulary).

## Migration map

| Current | Public | Returns | Action |
|---|---|---|---|
| `Ok` / `Err` | `Result.Success` / `Result.Failure` | enum variants | **breaking rename** |
| `is_ok` | `self.isSuccess` | `bool` | **rename** |
| `is_err` | `self.isFailure` | `bool` | **rename** |
| `unwrap` | `self.unwrap` | `T` or panic | **rename** |
| `unwrap_err` | `self.unwrapFailure` | `E` or panic | **rename** |
| `expect` | `self.expect` | `T` or panic | **rename** |
| `unwrap_or` | `self.unwrapOr` | `T` | **rename** |
| `unwrap_or_else` | `self.orWith` | `T` (`f(e)`) | **rename** |
| `map` | `self.map` | `Result` | **rename** |
| `map_err` | `self.mapFailure` | `Result` | **rename** · **core** |
| `flat_map` | `self.flatMap` | `Result` | **rename** |
| `and_then` | `self.flatMap` | `Result` | **merge** / remove alias |
| `or_else` | `self.recover` | `Result` | **rename** |
| `result_to_option` / `ok` | `self.toOption` | `Option` | **merge** → one name |
| `err` | `self.error` | `Option` of `E` | **rename** |
| `try_all` | `Result.all` | `Result` of `Vec` | **rename** |

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
| `result.isSuccess` | `self.isSuccess` | `self.isSuccess() -> bool` | proposed |
| `result.isFailure` | `self.isFailure` | `self.isFailure() -> bool` | proposed |
| `result.unwrap` | `self.unwrap` | `self.unwrap() -> T` | proposed |
| `result.unwrapFailure` | `self.unwrapFailure` | `self.unwrapFailure() -> E` | proposed |
| `result.expect` | `self.expect` | `self.expect(msg: string) -> T` | proposed |
| `result.unwrapOr` | `self.unwrapOr` | `self.unwrapOr(default: T) -> T` | proposed |
| `result.orWith` | `self.orWith` | `self.orWith(f: E -> T) -> T` | planned |
| `result.map` | `self.map` | `self.map(f: …) -> Result of (…)` | planned |
| `result.mapFailure` | `self.mapFailure` | `self.mapFailure(f: …) -> Result of (…)` | planned |
| `result.flatMap` | `self.flatMap` | `self.flatMap(f: …) -> Result of (…)` | planned |
| `result.recover` | `self.recover` | `self.recover(f: …) -> Result of (…)` | planned |
| `result.toOption` | `self.toOption` | `self.toOption() -> Option of (T)` | proposed |
| `result.error` | `self.error` | `self.error() -> Option of (E)` | proposed |
| `result.all` | `Result.all` | `Result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)` | planned |

---

<a id="result.isSuccess"></a>
## `self.isSuccess`

<!--
id: result.isSuccess
api: self.isSuccess
previous: is_ok
-->

```vir
self.isSuccess() -> bool
```

`true` iff `r` is `Success(_)`.

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `isSuccess`.

### See also

- `self.isFailure`

---

<a id="result.isFailure"></a>
## `self.isFailure`

<!--
id: result.isFailure
api: self.isFailure
previous: is_err
-->

```vir
self.isFailure() -> bool
```

`true` iff `r` is `Failure(_)`.

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `isFailure`.

### See also

- `self.isSuccess`

---

<a id="result.unwrap"></a>
## `self.unwrap`

<!--
id: result.unwrap
api: self.unwrap
previous: unwrap
-->

```vir
self.unwrap() -> T
```

| Case | Result |
|---|---|
| `Success(v)` | `v` |
| `Failure(_)` | **panic** |

Valid primitive; not preferred normal flow when errors are expected — prefer
`or` / `orWith` / `recover` / `case`.

### Status

`proposed` — **present** as free `unwrap`.

### Implementation mapping

`vir/core/result.vri` → `unwrap`.

### See also

- `self.expect`
- `self.unwrapFailure`

---

<a id="result.unwrapFailure"></a>
## `self.unwrapFailure`

<!--
id: result.unwrapFailure
api: self.unwrapFailure
previous: unwrap_err
-->

```vir
self.unwrapFailure() -> E
```

| Case | Result |
|---|---|
| `Failure(e)` | `e` |
| `Success(_)` | **panic** |

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `unwrapFailure`.

### See also

- `self.error`
- `self.unwrap`

---

<a id="result.expect"></a>
## `self.expect`

<!--
id: result.expect
api: self.expect
previous: expect
-->

```vir
self.expect(msg: string) -> T
```

Same as `unwrap` with custom panic message.

### Status

`proposed` — **present** as `expect`.

### Implementation mapping

`vir/core/result.vri` → `expect`.

### See also

- `self.unwrap`

---

<a id="result.unwrapOr"></a>
## `self.unwrapOr`

<!--
id: result.unwrapOr
api: self.unwrapOr
previous: unwrap_or
-->

```vir
self.unwrapOr(default: T) -> T
```

| Case | Result |
|---|---|
| `Success(v)` | `v` |
| `Failure(_)` | `default` |

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `unwrapOr`.

### See also

- `self.orWith`
- `self.recover`

---

<a id="result.orWith"></a>
## `self.orWith`

<!--
id: result.orWith
api: self.orWith
previous: unwrap_or_else
-->

```vir
self.orWith(f: …) -> T
```

| Case | Result |
|---|---|
| `Success(v)` | `v` |
| `Failure(e)` | `f(e)` |

### Semantics

Returns **`T`**. Callback receives **`E`** — unlike `option.orWith` which takes
no absence payload.

### Status

`proposed` — implementation present; callable ABI remains the general gate.

### Implementation mapping

`vir/core/result.vri` → `orWith`.

### See also

- `self.unwrapOr`
- `self.recover`

---

<a id="result.map"></a>
## `self.map`

<!--
id: result.map
api: self.map
previous: map
-->

```vir
self.map(f: (T) -> U) -> Result of (U, E)
```

| Case | Result |
|---|---|
| `Success(v)` | `Success(f(v))` |
| `Failure(e)` | `Failure(e)` |

### Status

`proposed` — **present** as `map`.

### Implementation mapping

`vir/core/result.vri` → `map`.

### See also

- `self.mapFailure`
- `self.flatMap`

---

<a id="result.mapFailure"></a>
## `self.mapFailure`

<!--
id: result.mapFailure
api: self.mapFailure
previous: map_err
-->

```vir
self.mapFailure(f: (E) -> F) -> Result of (T, F)
```

| Case | Result |
|---|---|
| `Success(v)` | `Success(v)` |
| `Failure(e)` | `Failure(f(e))` |

### Semantics

**Core.** Remap low-level / I/O errors into domain errors without touching
success values.

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `mapFailure`.

### See also

- `self.map`
- `self.recover`

---

<a id="result.flatMap"></a>
## `self.flatMap`

<!--
id: result.flatMap
api: self.flatMap
previous: flat_map, and_then
-->

```vir
self.flatMap(f: (T) -> Result of (U, E)) -> Result of (U, E)
```

| Case | Result |
|---|---|
| `Success(v)` | `f(v)` (`f` returns `Result`) |
| `Failure(e)` | `Failure(e)` |

### Semantics

Sole public name for this operation. `and_then` is not canonical.

### Status

`proposed` — implementation present; the old `and_then` alias is removed.

### Implementation mapping

`vir/core/result.vri` → `flatMap`.

### See also

- `self.map`
- `option.flatMap`

---

<a id="result.recover"></a>
## `self.recover`

<!--
id: result.recover
api: self.recover
previous: or_else
-->

```vir
self.recover(f: (E) -> Result of (T, E)) -> Result of (T, E)
```

| Case | Result |
|---|---|
| `Success(v)` | `Success(v)` |
| `Failure(e)` | `f(e)` (`f` returns `Result`) |

### Semantics

Stay in Result algebra while handling the error channel. Not value fallback
(`or` / `orWith`).

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `recover`.

### See also

- `self.orWith`
- `self.mapFailure`

---

<a id="result.toOption"></a>
## `self.toOption`

<!--
id: result.toOption
api: self.toOption
previous: result_to_option, ok
-->

```vir
self.toOption() -> Option of (T)
```

| Case | Result |
|---|---|
| `Success(v)` | `Some(v)` |
| `Failure(_)` | `None` |

### Semantics

Success-side conversion. Not named `result.ok` (reads like predicate /
constructor). Merges `result_to_option` and free `ok`.

### Status

`proposed` — implementation present under the canonical name only.

### Implementation mapping

`vir/core/result.vri` → `toOption`.

### See also

- `self.error`
- `option.toResult`

---

<a id="result.error"></a>
## `self.error`

<!--
id: result.error
api: self.error
previous: err
-->

```vir
self.error() -> Option of (E)
```

| Case | Result |
|---|---|
| `Success(_)` | `None` |
| `Failure(e)` | `Some(e)` |

### Semantics

Error-side conversion → `Option` of `E`. Pair with `toOption`:

```text
self.toOption()  → Option of T
self.error()     → Option of E
```

### Status

`proposed` — implementation present.

### Implementation mapping

`vir/core/result.vri` → `error`.

### See also

- `self.toOption`
- `self.unwrapFailure`

---

<a id="result.all"></a>
## `Result.all`

<!--
id: result.all
api: Result.all
previous: try_all
-->

```vir
Result.all(results: Vec of (Result of (T, E))) -> Result of (Vec of (T), E)
```

Aggregate a vector of results.

| Input | Output |
|---|---|
| all `Success` | `Success` of `Vec` of success values (order preserved) |
| any `Failure` | **first** `Failure` (short-circuit) |

### Semantics

Conceptual shape: collection of `Result` → `Result` of collection.
**First error wins.** Depends on locked `Vec` core — not a reason to defer.

Do not invent unsupported generic syntax in call sites; document meaning only.

### Status

`proposed` — implementation present; type-receiver dispatch remains compiler-gated.

### Implementation mapping

`vir/core/result.vri` → `all`.

### See also

- `self.flatMap`
- [`vec.md`](vec.md)

---

## Implementation readiness

**Design status: closed** (R1–R3). Error payloads: [`error.md`](error.md).
Callable HOF and `all` stay `planned` until ABI / reclaim gates clear. The
canonical implementation symbols are present in `vir/core/result.vri`.
