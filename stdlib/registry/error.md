---
module: error
title: Error
summary: ErrorKind + Error + IoError — single kind taxonomy; recoverable Result payloads.
source:
  - name: error
    path: vir/error/error.vri
  - name: compiler.file
    path: vir/compiler/file.vri
    notes: bootstrap IoError shape must conform (today diverges)
status: closed
notes: >-
  Architecture closed: sole ErrorKind; no public IoErrorKind; IoError.kind:
  ErrorKind; thin error.*; fromErrno SSOT; panic out. .vri not yet migrated.
---

# Error

Recoverable error **values** used as `Result` error payloads (`Err(E)`).

```text
Error / IoError   → recoverable values in Result.Err
panic / todo / …  → abort / invariant  (separate API — not error.*)
```

```text
                 ErrorKind   (one taxonomy)
                     │
              ┌──────┴──────┐
              │             │
            Error         IoError
                            │
                          errno
```

## Boundary

| In `error` | Not in `error` |
|---|---|
| `ErrorKind`, `Error`, `IoError` | Public `IoErrorKind` — **removed** |
| Construct / access / display / errno bridge | `panic_msg` / `unreachable` / `todo` / `unimplemented` |
| `fromErrno` / `toError` | One convenience ctor per kind |
| Optional cause chain (semantic) | Promising `source: Option of (ptr)` as public ABI |
| | `data.error` / `compiler.errors` — other domains |

Aligns with locked I/O:

```text
Reader.exact / atleast premature EOF  → Err(… UnexpectedEof …)
fs.text invalid UTF-8                 → Err(… InvalidData …)
```

`Result` algebra stays in [`result.md`](result.md). This file defines **`E`**.
Parse failures use `ParseIntError` / `ParseFloatError` — see [`parse.md`](parse.md).

## Architecture (closed)

### One `ErrorKind`

**Remove** public `IoErrorKind`. It is only a subset of `ErrorKind` with
intentionally overlapping discriminants — it adds conversion noise, not
information.

Evidence of today’s divergence:

```text
error/error.vri      IoError.kind: ErrorKind
compiler/file.vri    IoError.kind: IoErrorKind
```

Canonical:

```text
IoError.kind: ErrorKind
```

Constraint (documentation / convention, not a second enum):

> `IoError.kind` uses the **I/O-relevant** variants of `ErrorKind`.

### Keep two value types

Do **not** merge `Error` and `IoError`.

| Type | Fields (semantic) |
|---|---|
| `Error` | `kind: ErrorKind`, `message: string`, optional **source/cause** |
| `IoError` | `kind: ErrorKind`, `message: string`, `errno: int` |

`IoError` exists to retain native OS `errno` at the syscall/filesystem boundary.

Conversion:

```text
IoError  →  Error    via error.toError
```

### Compiler must conform

`compiler/file.vri` (and any bootstrap duplicate) may keep a physical copy for
bootstrap, but the **semantic model** must match:

```text
IoError.kind: ErrorKind
errno mapping: single SSOT (error.fromErrno)
```

Duplicate implementation OK; duplicate error model **not** OK.

## `ErrorKind` taxonomy (closed)

Preserve **exact variant names and numeric discriminants** from
`vir/error/error.vri` unless a dedicated ABI audit says otherwise. Grouping is
documentation structure only:

```text
ErrorKind

I/O
├── NotFound           = 1
├── PermissionDenied   = 2
├── AlreadyExists      = 3
├── BrokenPipe         = 4
├── WouldBlock         = 5
├── TimedOut           = 6
├── ConnectionRefused  = 7
├── ConnectionReset    = 8
├── Interrupted        = 9
├── UnexpectedEof      = 10
│
Input / parse
├── InvalidInput       = 20
├── InvalidData        = 21
├── InvalidEncoding    = 22
├── ParseIntError      = 23
├── ParseFloatError    = 24
├── SyntaxError        = 25
│
Runtime / resource
├── OutOfMemory        = 40
├── Overflow           = 41
├── DivisionByZero     = 42
├── IndexOutOfBounds   = 43
├── NullPointer        = 44
├── StackOverflow      = 45
│
Program / logic
├── Unimplemented      = 60
├── Unreachable        = 61
├── AssertionFailed    = 62
│
└── Other              = 99
```

I/O-relevant kinds commonly used on `IoError` include the I/O group plus
`InvalidInput` / `InvalidData` / `InvalidEncoding` / `Other` (and others when
the OS path warrants).

### Contract examples (shared language with `io` / `fs`)

```text
Reader.exact / atleast → premature EOF
  Err(IoError { kind: ErrorKind.UnexpectedEof, … })

fs.text → invalid UTF-8
  Err(IoError { kind: ErrorKind.InvalidData, … })
```

## Public surface (closed)

```text
error
├── new
├── withSource
├── kind
├── message
├── source
├── string
├── chain
├── kindName
├── fromErrno
└── toError
```

```vir
error.new(ErrorKind.NotFound, msg)
error.fromErrno(errno)
error.toError(ioErr)
```

No public:

```text
IoErrorKind
io_error                    # footgun: named io_*, kind was NotFound
make_parse_error / overflow_error / index_error / null_error / todo_error
panic_msg / unreachable / unimplemented / todo
```

Convenience kind constructors are **not** required: callers use
`error.new(ErrorKind.…, message)`. Existing helpers may remain internal until
audited; they are not canonical.

## Cause / source chain (closed)

Public operations:

```text
error.withSource
error.source
error.chain
```

**Semantic contract:**

> An `Error` may retain an optional source/cause error.

Implementation today may box via `Option of (ptr)` / `native_box`. That storage is
an **implementation detail**. Registry does **not** freeze public ABI as
`Option of (ptr)`. Target may become `Option` of `Error` (or equivalent) when the
language representation is clean.

## errno SSOT (closed)

```vir
error.fromErrno(errno) -> IoError
```

(Optional message parameter only if implementation already supports / later
adds it — today maps errno → kind + stock message.)

```text
OS errno
   ↓
error.fromErrno
   ↓
IoError
   ↓
Err(IoError)
```

**Single mapping table** in the error module. `compiler/file`, `fs`, and `io`
must not each invent divergent errno → kind tables.

```vir
error.toError(io: IoError) -> Error
```

| Field | Mapping |
|---|---|
| `kind` | preserved |
| `message` | preserved |
| `errno` | not folded into `kind`; display may mention it |

## Migration map

| Current | Public | Action |
|---|---|---|
| `ErrorKind` | `ErrorKind` | **keep** (sole kind enum) |
| `IoErrorKind` | — | **remove** public; migrate uses → `ErrorKind` |
| `Error` | `Error` | **keep** |
| `IoError` | `IoError` | **keep**; `kind: ErrorKind` |
| `error_new` | `error.new` | **rename** |
| `error_with_source` | `error.withSource` | **rename** |
| `error_kind` | `error.kind` | **rename** |
| `error_message` | `error.message` | **rename** |
| `error_source` | `error.source` | **rename**; hide ptr ABI |
| `error_to_string` | `error.string` | **rename** |
| `error_chain` | `error.chain` | **rename** |
| `error_kind_name` | `error.kindName` | **rename** |
| `io_error_from_errno` | `error.fromErrno` | **rename**; SSOT errno map |
| `io_error_to_error` | `error.toError` | **rename** |
| `io_error` | — | **remove** public |
| `make_parse_error` … `todo_error` | — | **internal** / not canonical |
| `panic_msg` / `unreachable` / `unimplemented` / `todo` | — | **out** of error payload API |
| `compiler/file` `IoErrorKind` | `ErrorKind` | **conform** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `error.ErrorKind` | `ErrorKind` | enum (taxonomy above) | proposed |
| `error.Error` | `Error` | type | proposed |
| `error.IoError` | `IoError` | type · `kind: ErrorKind` | proposed |
| `error.new` | `error.new` | `error.new(kind: ErrorKind, msg: string) -> Error` | proposed |
| `error.withSource` | `error.withSource` | `error.withSource(kind, msg, source: Error) -> Error` | proposed |
| `error.kind` | `error.kind` | `error.kind(e: Error) -> ErrorKind` | proposed |
| `error.message` | `error.message` | `error.message(e: Error) -> string` | proposed |
| `error.source` | `error.source` | `error.source(e: Error) -> Option of (Error)` · cause | proposed |
| `error.string` | `error.string` | `error.string(e: Error) -> string` | proposed |
| `error.chain` | `error.chain` | `error.chain(e: Error) -> string` | proposed |
| `error.kindName` | `error.kindName` | `error.kindName(kind: ErrorKind) -> string` | proposed |
| `error.fromErrno` | `error.fromErrno` | `error.fromErrno(errno: int) -> IoError` | proposed |
| `error.toError` | `error.toError` | `error.toError(e: IoError) -> Error` | proposed |

Accessors may also apply to `IoError` for `kind` / `message` where useful;
primary construct path for I/O remains `fromErrno` + fields. Document
`IoError` field access in implementer notes if methods are shared or duplicated.

---

<a id="error.new"></a>
## `error.new`

<!--
id: error.new
api: error.new
previous: error_new
-->

```vir
error.new(kind: ErrorKind, msg: string) -> Error
```

Construct an `Error` with no cause.

### Example

```vir
error.new(ErrorKind.NotFound, "config missing")
```

### Status

`proposed` — **present** as `error_new`.

### Implementation mapping

`vir/error/error.vri` → `error_new`.

### See also

- `error.withSource`
- `error.fromErrno`

---

<a id="error.withSource"></a>
## `error.withSource`

<!--
id: error.withSource
api: error.withSource
previous: error_with_source
-->

```vir
error.withSource(kind: ErrorKind, msg: string, source: Error) -> Error
```

Construct an `Error` that retains `source` as cause.

### Semantics

Public cause chain. Storage (box/ptr) is implementation detail.

### Status

`proposed` — **present** as `error_with_source`.

### Implementation mapping

`vir/error/error.vri` → `error_with_source`.

### See also

- `error.source`
- `error.chain`

---

<a id="error.kind"></a>
## `error.kind`

<!--
id: error.kind
api: error.kind
previous: error_kind
-->

```vir
error.kind(e: Error) -> ErrorKind
```

### Status

`proposed` — **present** as `error_kind`.

### Implementation mapping

`vir/error/error.vri` → `error_kind`.

---

<a id="error.message"></a>
## `error.message`

<!--
id: error.message
api: error.message
previous: error_message
-->

```vir
error.message(e: Error) -> string
```

### Status

`proposed` — **present** as `error_message`.

### Implementation mapping

`vir/error/error.vri` → `error_message`.

---

<a id="error.source"></a>
## `error.source`

<!--
id: error.source
api: error.source
previous: error_source
-->

```vir
error.source(e: Error) -> Option of (Error)
```

Optional cause. Success payload is an `Error` (semantic); not a public `ptr`.

### Status

`proposed` — **present**; tighten representation away from leaked `ptr`.

### Implementation mapping

`vir/error/error.vri` → `error_source`.

### See also

- `error.withSource`
- `error.chain`

---

<a id="error.string"></a>
## `error.string`

<!--
id: error.string
api: error.string
previous: error_to_string
-->

```vir
error.string(e: Error) -> string
```

Single-line display (`kindName: message` today).

### Status

`proposed` — **present** as `error_to_string`.

### Implementation mapping

`vir/error/error.vri` → `error_to_string`.

### See also

- `error.chain`
- `error.kindName`

---

<a id="error.chain"></a>
## `error.chain`

<!--
id: error.chain
api: error.chain
previous: error_chain
-->

```vir
error.chain(e: Error) -> string
```

Multi-line display including causes.

### Status

`proposed` — **present** as `error_chain`.

### Implementation mapping

`vir/error/error.vri` → `error_chain`.

---

<a id="error.kindName"></a>
## `error.kindName`

<!--
id: error.kindName
api: error.kindName
previous: error_kind_name
-->

```vir
error.kindName(kind: ErrorKind) -> string
```

Stable short name for a kind (display / logging).

### Notes

Today’s implementation does not name every variant (falls through to
`"Error"`). Completing coverage is an implementation follow-up; discriminants
stay fixed.

### Status

`proposed` — **present** as `error_kind_name`.

### Implementation mapping

`vir/error/error.vri` → `error_kind_name`.

---

<a id="error.fromErrno"></a>
## `error.fromErrno`

<!--
id: error.fromErrno
api: error.fromErrno
previous: io_error_from_errno
-->

```vir
error.fromErrno(errno: int) -> IoError
```

Map a POSIX/`errno` code to `IoError` (`kind` + message + `errno` field).

### Semantics

**SSOT** for errno → `ErrorKind`. Expand table as platforms require; do not
fork maps in `fs` / `io` / compiler file.

### Status

`proposed` — **present** as `io_error_from_errno` (partial table today).

### Implementation mapping

`vir/error/error.vri` → `io_error_from_errno`; compiler/file local map must
delegate or match.

### See also

- `error.toError`
- [`fs.md`](fs.md) / [`io.md`](io.md)

---

<a id="error.toError"></a>
## `error.toError`

<!--
id: error.toError
api: error.toError
previous: io_error_to_error
-->

```vir
error.toError(e: IoError) -> Error
```

Lift `IoError` into generic `Error` (kind + message preserved).

### Status

`proposed` — **present** as `io_error_to_error`.

### Implementation mapping

`vir/error/error.vri` → `io_error_to_error`.

### See also

- `error.fromErrno`
- `error.new`

---

## Abort APIs (out of this module)

See [`panic.md`](panic.md):

```text
panic.fail / unreachable / unimplemented / todo
```

Do not overload `error.*` to both build an `Error` and abort.

---

## Implementation readiness

Public error architecture is closed for this refactor:

1. Delete / stop exporting public `IoErrorKind`.
2. Unify `IoError.kind` on `ErrorKind` everywhere (including compiler file).
3. Centralize errno mapping in `error.fromErrno`.
4. Expose namespace `error.*`; drop public `io_error` footgun.
5. Keep cause chain; hide `ptr` from the public contract.

Implementation may proceed against this registry. Cross-check `io.md` / `fs.md`
Err examples against `ErrorKind.UnexpectedEof` / `InvalidData`.
