---
module: panic
title: Panic
summary: Non-returning abort helpers — panic.*; not recoverable Error.
source:
  - name: error
    path: vir/error/error.vri
    notes: panic_msg / unreachable / unimplemented / todo migrate here
status: closed
notes: >-
  Namespace panic.* only — no new language keywords. Non-returning; no recovery
  / unwind contract. Distinct from Result and from process.abort. Docs only.
---

# Panic

Abort / invariant / development-failure helpers. **Not** recoverable
[`Error`](error.md) / [`Result`](result.md) payloads.

```text
Error / IoError     → recoverable values in Result.Err
panic.*             → non-returning abort
process.exit/abort  → process-level termination — [`process.md`](process.md)
```

## Boundary

| In `panic` | Not in `panic` |
|---|---|
| `fail` / `unreachable` / `unimplemented` / `todo` | Building `Error` values |
| Namespace `panic.*` | New language keywords |
| | `process.abort` overload |
| | Using panic for ordinary failure paths that should be `Result` |

## Public surface (closed)

```text
panic
├── fail
├── unreachable
├── unimplemented
└── todo
```

| API | Meaning |
|---|---|
| `panic.fail(msg)` | Terminate with message |
| `panic.unreachable()` | Branch that must never execute |
| `panic.unimplemented()` | Feature not implemented |
| `panic.todo()` | Intentionally unfinished (dev convenience) |

All four are **non-returning**. No recovery or unwinding contract in this
registry. `todo` is public for development — not a recoverable error.

## Migration map

| Current | Public | Action |
|---|---|---|
| `panic_msg` | `panic.fail` | **rename** |
| `unreachable` | `panic.unreachable` | **rename** / nest |
| `unimplemented` | `panic.unimplemented` | **rename** / nest |
| `todo` | `panic.todo` | **rename** / nest |
| `todo_error` | — | not panic · was Error ctor · out of this ns |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `panic.fail` | `panic.fail` | `panic.fail(msg: string) -> !` | proposed |
| `panic.unreachable` | `panic.unreachable` | `panic.unreachable() -> !` | proposed |
| `panic.unimplemented` | `panic.unimplemented` | `panic.unimplemented(feature: string) -> !` | proposed |
| `panic.todo` | `panic.todo` | `panic.todo(what: string) -> !` | proposed |

(`!` = non-returning; document in Vir terms when available.)

---

<a id="panic.fail"></a>
## `panic.fail`

```vir
panic.fail(msg: string)
```

### Status

`proposed` — **present** as `panic_msg`.

---

<a id="panic.unreachable"></a>
## `panic.unreachable` / `unimplemented` / `todo`

```vir
panic.unreachable()
panic.unimplemented(feature: string)
panic.todo(what: string)
```

### Status

`proposed`.

---

## Implementation readiness

1. Nest under `panic.*`; keep old names as migration wrappers briefly.
2. Keep out of [`error`](error.md) payload API.
3. Do not substitute for `Result` on normal failure paths.
