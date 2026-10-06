---
id: "VIR-SPC-0013"
type: "SPEC"
domain: "VIR"
title: "Vir Functions (AI Spec)"
status: "ACTIVE"
version: "3.0.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-06"
owners:
  - "VIR"
components: []
aliases:
  - "docs/ai-spec/vir-lang/references/functions.md"
related:
  issues:
    - "VIR-ISS-0004"
    - "VIR-ISS-0005"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0013 — Vir Functions (AI Spec)

**Spec:** Vir v3.0

## Declaration

```vir
func name:
    # body
end.

func add(a: i32, b: i32) -> i32:
    out a + b
end.
```

- Opens with `:` (no expression before body)
- Closes with **`end.`**
- Entry programs typically define `func main:`

Function definitions in one source unit are collected independently of source
order. A call may therefore refer to a function defined later; no untyped
forward declaration is part of Vir 3.0. A bodyless foreign declaration must use
the typed `extern func`/`extern from ... func` or binding contract from the FFI
specification.

## `out` (not `return`)

`out` emits a result from the current context (function result). One keyword, context-dependent destination.

```vir
func main:
    out 0
end.
```

Never write `return`.

## Calls

```vir
print("hi")
print "hi"           # call forms used in codebase
var z = add(1, 2)
```

Named args use `=` in call position (distinct from entity field init `name: expr`):

```vir
# Prefer patterns from nearby .vri files when unsure
```

## Parameters — `in` / `ref` / `out`

Two documented styles (see human spec §14):

### Parentheses

```vir
func foo(a: int, b: int) -> int:
    out a + b
end.
```

### Section blocks

```vir
func transfer:
    in from: Account
       to: Account
       amount: int
    # body …
    out ok
end.
```

| Section | Meaning |
|---|---|
| `in` | Inputs |
| `ref` | By-reference / shared mutable access |
| `out` | Output section / result wiring |

Do not invent Python/`*`/`**` or Rust lifetime syntax.

## Methods & UFCS

Methods inside `entity` use implicit `this`; close methods with `end.`.

```vir
entity Account:
    balance: int

    method deposit(amount: int):
        this.balance = this.balance + amount
    end.
end.
```

UFCS: a free function whose first param is `this` may be called with `.`:

```vir
func display(this: User):
    print("User: $this.name")
end.

u.display()    # ≈ display(u)
```

### Callable fields

A callable field must have a structural function type, never raw `ptr`:

```vir
entity Button:
    label: string
    on_click: func()
end.

func handle_click:
    print("clicked!")
end.

var btn = Button(label: "OK", on_click: handle_click)
btn.on_click()
```

Calling `x.field(args)` invokes the typed function value and passes only the explicit `args`; unlike a method call, it does not inject `x` as an implicit receiver. Assignment and invocation are checked against the field's declared parameters and result. Raw `ptr` is not callable and is not implicitly convertible to a function type. Vir 2.1 defines no raw-address-to-callable conversion; any future FFI conversion must be explicit, unsafe, signature-bearing, ABI-aware, and specify provenance and lifetime constraints.

## Async

```vir
async func fetch:
    # …
end.
```

Only use `async` when the surrounding project already does; do not invent schedulers.

## Agent rules

1. Always `end.` for function / method / entity / enum definitions.
2. Prefer `out` for results; never `return`.
3. Match `in`/`ref`/`out` style of the nearest file in the repo.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-06 | 3.0.0 | Made function lookup declaration-order independent and removed the untyped forward-declaration form from the Vir 3.0 contract |
| 2026-10-04 | 2.1.0 | Defined callable fields as typed structural function values and excluded implicit raw-`ptr` calls |
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/functions.md` and assigned stable ID `VIR-SPC-0013` |
