# Vir Errors (AI Spec)

**Spec:** Vir v2.0  
Model: local function error flow — **not** Java-style exception objects.

| Keyword | Role | Analog (informational only) |
|---|---|---|
| `throw` | Abort normal path | throw / panic |
| `ensure` | Always runs on function exit | defer / scope(exit) |
| `revert` | Runs only after `throw` | catch / scope(failure) |

## throw

```vir
func safe_div(a, b):
    if b == 0 do
        throw 1
    end
    out a / b
end.
```

Thrown values are integers (`int`). Without `revert`/`ensure`, uncaught `throw` may abort (e.g. `BRK`).

## ensure / revert on functions

Continuations — **no** `:`.

```vir
func process_file(path):
    var fd = open(path)
    print(42)
ensure
    close(fd)
end.
```

```vir
func transfer(from, to, amount):
    withdraw(from, amount)
    deposit(to, amount)
ensure
    log("done or rolled back")
revert
    refund(from, amount)
end.
```

### Exit order

| Scenario | Order |
|---|---|
| Normal | body → ensure → return |
| Throw | body → throw → revert → ensure → return |

## erx

In `revert`, `erx` holds the thrown integer:

```vir
func compute(x):
    if x < 0 do
        throw 1
    end
    out x * x
revert
    print("error: $erx")
end.
```

## Conventional code ranges (convention, not enforced)

| Range | Meaning |
|---|---|
| 0 | No error |
| 1–99 | App logic |
| 100–199 | I/O |
| 200–255 | System |

Extra context may use an `Error` entity + side storage — do not invent exception classes.

## try / revert (local)

See human spec §13.7. Prefer copying a working pattern from the repo over inventing `catch` / `finally` keywords.

## Agent rules

1. Never invent `try/catch/finally` or `Result.unwrap()` unless that API exists in referenced stdlib.
2. Function cleanup → `ensure` / `revert`, not Rust `Drop` glosses.
3. Close the function with `end.` after ensure/revert sections.
