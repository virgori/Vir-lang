---
module: option
title: Option
summary: Option(T) — Some(T) or None; namespace option.* for helpers; language-level constructors.
source:
  - name: option
    path: vir/core/option.vri
  - name: compiler.option.def
    path: vir/compiler/option.vri
status: closed
notes: >-
  Design closed (O1–O4). zip deferred until Pair(T,U). Callable HOF → planned.
  and planned. Ownership: payload only; move vs copy rules. No .vri (Q5).
---

# Option

`Option(T)` is either one value of type `T` or the absence of a value.

```text
Option(T)
├── Some(T)
└── None
```

Constructors are **language-level enum variants**, not namespace helpers:

```vir
Some(value)
None
# Option.Some(value) / Option.None when qualified form is in scope
```

Operations use namespace **`option.*`**:

```vir
option.isSome(opt)
option.unwrapOr(opt, default)
option.map(opt, f)
```

Free names (`is_some`, `unwrap`, …) are implementation / prelude compatibility
only — not canonical public API.

## Boundary

| In `option` | Not in `option` |
|---|---|
| Query / extract / combinators on `Option` | Constructors `option.some` / `option.none` |
| `toResult` conversion | Full `Result` algebra → [`result`](result.md) *(next)* |
| Small HOF set (`map` / `flatMap` / `filter` / `zip`) | Collection HOF surface (see `vec` — separate) |
| | Free `is_some` / `unwrap` as public aliases |
| | Treating `Option` as a functional programming kit |

Primary consumers already locked elsewhere:

```text
vec.tryGet / first / last / pop / find
path.parent / name / stem / ext
env.get / int / bool   (target)
slice.find
```

`unwrap` is a valid primitive but **not** the preferred normal-flow pattern in
docs when absence is expected — callers should branch or use `or` / `orWith`.

## Generic contract (closed)

**Semantic contract:** `Option(T)` with payload type `T`.

Source may currently write an unparameterized `enum Option` with a generic
payload slot. That is an **implementation mechanism**, not a reason to document
an untyped public contract.

Document public contracts as `Option(T)` using Vir `()` generics.
If a given compiler stage only accepts unparameterized `Option` in
examples, note that as an **implementation gap** — do not fall back to `<>`.

## Public surface (closed)

```text
option
├── isSome · isNone          # proposed / present
├── unwrap · expect · unwrapOr
├── otherwise · toResult     # proposed / present
│
├── unwrapOrElse · map · flatMap · filter   # planned · callable ABI (O2)
├── and                                 # planned (O3)
│
# zip — deferred from public core until Pair(T, U) (O1)
```

### Semantic families

| Family | Shape |
|---|---|
| `unwrapOr` / `unwrapOrElse` | `Option` → contained `T` (or default) |
| `otherwise` / `and` / `filter` | `Option` → `Option` |
| `map` | `Option` → `Option` (transformed payload) |
| `flatMap` | `Option` → `Option` via `T → Option` |
| `toResult` | `Option` → `Result` |

### Critical naming (collision avoided)

Source today has **two different** APIs:

| Current | Returns | Canonical |
|---|---|---|
| `unwrap_or(default)` | `T` | **`option.unwrapOr`** |
| `unwrap_or_else(f)` | `T` (lazy) | **`option.unwrapOrElse`** |
| `or_else(alt)` | **`Option`** | `option.otherwise` |

Do **not** map both `unwrap_or_else` and `or_else` to `orElse`.

```vir
option.unwrapOr(opt, value)        # → T
option.unwrapOrElse(opt, f)        # → T, lazy · planned
option.otherwise(opt, alt)         # → Option
```

## Migration map

| Current | Public | Returns | Action |
|---|---|---|---|
| `Some` / `None` | `Some` / `None` | constructors | **keep** language-level |
| `is_some` | `option.isSome` | `bool` | **rename**; remove free public |
| `is_none` | `option.isNone` | `bool` | **rename**; remove free public |
| `unwrap` | `option.unwrap` | `T` or panic | **rename**; remove free public |
| `expect` | `option.expect` | `T` or panic | **rename**; remove free public |
| `unwrap_or` | `option.unwrapOr` | `T` | **rename** |
| `unwrap_or_else` | `option.unwrapOrElse` | `T` | **rename**; **planned** (O2) |
| `or_else` | `option.otherwise` | `Option` | **rename** |
| — | `option.and` | `Option` | **planned** (trivial) |
| `map` | `option.map` | `Option` | **rename**; **planned** until callable ABI (O2) |
| `flat_map` | `option.flatMap` | `Option` | **rename**; **planned** (O2) |
| `filter` | `option.filter` | `Option` | **rename**; **planned** (O2) |
| `zip` | — | — | **defer** until `Pair(T, U)` (O1) |
| `option_to_result` | `option.toResult` | `Result` | **move** into `core/option.vri` |

Prelude (`compiler/option_prelude.vri`) may keep minimal free helpers for
bootstrap; not the user-facing contract.

## Decisions O1–O4 (locked)

| ID | Decision |
|---|---|
| O1 | **`zip` deferred** from public core until standardized `Pair(T, U)`. Do not invent a pair type only for `option`. |
| O2 | HOF needing callable ABI (`map` / `flatMap` / `filter` / `orWith`) → **`planned`**. Target surface + semantics remain in docs; not `stable` until ABI confirmed. |
| O3 | `option.and` stays **`planned`**; not required present to close design. |
| O4 | Typo `Option(U)` → `Option(U)` fixed. |

Ops without callbacks (`isSome` / `isNone` / `unwrap` / `expect` / `or` / `otherwise` / `toResult`) keep their own statuses.


## Naming (CORE SPEC)

Canonical public names follow the CORE SPEC. Source/snake names migrate later.

| Source / previous | Canonical |
|---|---|
| `unwrap_or` / was `option.or` | **`option.unwrapOr`** |
| `unwrap_or_else` / was `option.orWith` | **`option.unwrapOrElse`** · planned (callable ABI) |
| `or_else` | **`option.otherwise`** |

Do not keep parallel `or` / `orWith` as second public names.

## Ownership (locked)

`Option(T)` owns **no** resources beyond the payload `T`.

| Access | Rule |
|---|---|
| Move payload out | Old `Option` must not be used as if it still holds the payload |
| Copy payload | Only when `T` is **safely copyable** |
| Forbidden | Shallow-copy of unique ownership |

## Callable HOF (O2)

`map` / `flatMap` / `filter` / `orWith` remain in the **target** surface as
**`planned`** until callable ABI is confirmed. Do not silently drop them from
design; do not mark them `stable` early.

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `option.isSome` | `option.isSome` | `option.isSome(opt: Option(T)) -> bool` | proposed |
| `option.isNone` | `option.isNone` | `option.isNone(opt: Option(T)) -> bool` | proposed |
| `option.unwrap` | `option.unwrap` | `option.unwrap(opt: Option(T)) -> T` | proposed |
| `option.expect` | `option.expect` | `option.expect(opt: Option(T), msg: string) -> T` | proposed |
| `option.unwrapOr` | `option.unwrapOr` | `option.unwrapOr(opt: Option(T), default: T) -> T` | proposed |
| `option.unwrapOrElse` | `option.unwrapOrElse` | `option.unwrapOrElse(opt: Option(T), f: …) -> T` | planned |
| `option.otherwise` | `option.otherwise` | `option.otherwise(opt: Option(T), alt: Option(T)) -> Option(T)` | proposed |
| `option.and` | `option.and` | `option.and(opt: Option(T), next: Option(U)) -> Option(U)` | planned |
| `option.map` | `option.map` | `option.map(opt: Option(T), f: …) -> Option(U)` | planned |
| `option.flatMap` | `option.flatMap` | `option.flatMap(opt: Option(T), f: …) -> Option(U)` | planned |
| `option.filter` | `option.filter` | `option.filter(opt: Option(T), predicate: …) -> Option(T)` | planned |
| `option.zip` | — | deferred until `Pair(T, U)` (O1) | deferred |
| `option.toResult` | `option.toResult` | `option.toResult(opt: Option(T), error: E) -> Result(T, E)` | proposed |

---

<a id="option.isSome"></a>
## `option.isSome`

<!--
id: option.isSome
api: option.isSome
previous: is_some
-->

```vir
option.isSome(opt: Option(T)) -> bool
```

`true` iff `opt` is `Some(_)`.

### Example

```vir
if option.isSome(opt) do
    # …
end
```

### Status

`proposed` — **present** as `is_some`.

### Implementation mapping

`vir/core/option.vri` → `is_some`.

### See also

- `option.isNone`

---

<a id="option.isNone"></a>
## `option.isNone`

<!--
id: option.isNone
api: option.isNone
previous: is_none
-->

```vir
option.isNone(opt: Option(T)) -> bool
```

`true` iff `opt` is `None`.

### Status

`proposed` — **present** as `is_none`.

### Implementation mapping

`vir/core/option.vri` → `is_none`.

### See also

- `option.isSome`

---

<a id="option.unwrap"></a>
## `option.unwrap`

<!--
id: option.unwrap
api: option.unwrap
previous: unwrap
-->

```vir
option.unwrap(opt: Option(T)) -> T
```

| Case | Result |
|---|---|
| `Some(v)` | `v` |
| `None` | **panic** |

### Semantics

Valid primitive; **not** preferred normal flow when absence is expected
(prefer `or` / `orWith` / `case` / `isSome`).

### Status

`proposed` — **present** as free `unwrap`.

### Implementation mapping

`vir/core/option.vri` → `unwrap`.

### See also

- `option.expect`
- `option.unwrapOr`

---

<a id="option.expect"></a>
## `option.expect`

<!--
id: option.expect
api: option.expect
previous: expect
-->

```vir
option.expect(opt: Option(T), msg: string) -> T
```

Same as `unwrap`, with custom panic message.

### Example

```vir
option.expect(opt, "configuration required")
```

### Status

`proposed` — **present** as `expect`.

### Implementation mapping

`vir/core/option.vri` → `expect`.

### See also

- `option.unwrap`

---

<a id="option.unwrapOr"></a>
## `option.unwrapOr`

<!--
id: option.unwrapOr
api: option.unwrapOr
previous: unwrap_or
-->

```vir
option.unwrapOr(opt: Option(T), default: T) -> T
```

| Case | Result |
|---|---|
| `Some(v)` | `v` |
| `None` | `default` |

### Semantics

Eager default. Not `option.otherwise` (that returns `Option`).

### Example

```vir
let v = option.unwrapOr(opt, 0)
```

### Status

`proposed` — **present** as `unwrap_or`.

### Implementation mapping

`vir/core/option.vri` → `unwrap_or`.

### See also

- `option.unwrapOrElse`
- `option.otherwise`

---

<a id="option.unwrapOrElse"></a>
## `option.unwrapOrElse`

<!--
id: option.unwrapOrElse
api: option.unwrapOrElse
previous: unwrap_or_else
-->

```vir
option.unwrapOrElse(opt: Option(T), f: …) -> T
```

| Case | Result |
|---|---|
| `Some(v)` | `v` |
| `None` | `f()` |

### Semantics

Lazy default producing a **`T`**. Distinct from `option.otherwise` (Option
fallback) and from former name collision with `or_else`.

### Status

`proposed` — **present** as `unwrap_or_else`.

### Implementation mapping

`vir/core/option.vri` → `unwrap_or_else`.

### See also

- `option.unwrapOr`
- `option.otherwise`

---

<a id="option.otherwise"></a>
## `option.otherwise`

<!--
id: option.otherwise
api: option.otherwise
previous: or_else
-->

```vir
option.otherwise(opt: Option(T), alt: Option(T)) -> Option(T)
```

| Case | Result |
|---|---|
| `Some(_)` | `opt` (unchanged) |
| `None` | `alt` |

### Semantics

Returns **`Option`**, not `T`. Former `or_else` — must not be named `orElse`
alongside `orWith`.

### Status

`proposed` — **present** as `or_else`.

### Implementation mapping

`vir/core/option.vri` → `or_else`.

### See also

- `option.and`
- `option.unwrapOr`

---

<a id="option.and"></a>
## `option.and`

<!--
id: option.and
api: option.and
-->

```vir
option.and(opt: Option(T), next: Option(U)) -> Option(U)
```

| Case | Result |
|---|---|
| `Some(_)` | `next` |
| `None` | `None` |

### Semantics

Sequence / short-circuit on absence. Complements `otherwise`.

### Status

`planned` — **missing**; trivial to add.

### Implementation mapping

New in `vir/core/option.vri`.

### See also

- `option.otherwise`
- `option.flatMap`

---

<a id="option.map"></a>
## `option.map`

<!--
id: option.map
api: option.map
previous: map
-->

```vir
option.map(opt: Option(T), f: …) -> Option(U)
```

| Case | Result |
|---|---|
| `Some(v)` | `Some(f(v))` |
| `None` | `None` |

### Semantics

Target algebra. Status **`planned`** until callable ABI confirmed (O2).

### Status

`proposed` — **present** as `map`.

### Implementation mapping

`vir/core/option.vri` → `map`.

### See also

- `option.flatMap`
- `option.filter`

---

<a id="option.flatMap"></a>
## `option.flatMap`

<!--
id: option.flatMap
api: option.flatMap
previous: flat_map
-->

```vir
option.flatMap(opt: Option(T), f: …) -> Option(U)
```

| Case | Result |
|---|---|
| `Some(v)` | `f(v)` (`f` returns `Option`) |
| `None` | `None` |

### Status

`proposed` — **present** as `flat_map`.

### Implementation mapping

`vir/core/option.vri` → `flat_map`.

### See also

- `option.map`
- `option.and`

---

<a id="option.filter"></a>
## `option.filter`

<!--
id: option.filter
api: option.filter
previous: filter
-->

```vir
option.filter(opt: Option(T), predicate: …) -> Option(T)
```

| Case | Result |
|---|---|
| `Some(v)` + predicate true | `Some(v)` |
| `Some(v)` + predicate false | `None` |
| `None` | `None` |

### Status

`proposed` — **present** as `filter`.

### Implementation mapping

`vir/core/option.vri` → `filter`.

### See also

- `option.map`

---

<a id="option.zip"></a>
## `option.zip` *(deferred — O1)*

<!--
id: option.zip
api: option.zip
previous: zip
-->

```vir
option.zip(a: Option(T), b: Option(U)) -> Option
```

| Case | Result |
|---|---|
| both `Some` | `Some(pair)` |
| otherwise | `None` |

### Semantics

Pair / tuple payload follows **current implementation** representation
(source uses `(unwrap(a), unwrap(b))`). Not a license to invent a public
tuple type name ahead of the language.

### Status

`deferred` — **out of public core** until `Pair(T, U)` (O1). Source may still have `zip`; not canonical.

### Implementation mapping

`vir/core/option.vri` → `zip`.

### See also

- `option.and`
- `option.map`

---

<a id="option.toResult"></a>
## `option.toResult`

<!--
id: option.toResult
api: option.toResult
previous: option_to_result
-->

```vir
option.toResult(opt: Option(T), error: E) -> Result(T, E)
```

| Case | Result |
|---|---|
| `Some(v)` | `Ok(v)` |
| `None` | `Err(error)` |

### Semantics

Conversion starts from `Option` → lives on `option`, not `result`. Move
implementation from `compiler/option.vri` into user-facing `core/option.vri`.
Error payload type follows current `Result` / `Err` conventions.

### Status

`proposed` — **present** only under compiler module today.

### Implementation mapping

`vir/compiler/option.vri` → `option_to_result`; target `vir/core/option.vri`.

### See also

- `option.unwrapOr`
- Result registry *(next)*

---

## Implementation readiness

**Design status: closed** (O1–O4 + ownership). Q8 surface / ownership / error /
lifecycle / semantics reflected. Implementation may proceed against this map
(Q5: no `.vri` until authorized).

1. Namespace renames (`unwrapOr` / `unwrapOrElse` / `otherwise`).
2. Add `and` when convenient; not a design blocker.
3. Callable HOF remain `planned` until ABI confirmed — then may become proposed/stable.
4. Do **not** reintroduce public `zip` before `Pair(T, U)`.
5. Keep constructors language-level (`Some` / `None`).
