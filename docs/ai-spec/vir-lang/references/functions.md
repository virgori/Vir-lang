# Vir Functions (AI Spec)

**Spec:** Vir v2.0

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
