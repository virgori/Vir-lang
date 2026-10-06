---
id: "VIR-SPC-0012"
type: "SPEC"
domain: "VIR"
title: "Vir Errors (AI Spec)"
status: "ACTIVE"
version: "2.1.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-04"
owners:
  - "VIR"
components: []
aliases:
  - "docs/ai-spec/vir-lang/references/errors.md"
related:
  issues:
    - "VIR-ISS-0003"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0012 — Vir Errors (AI Spec)

**Spec:** Vir v2.1
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

The canonical terminal transfers from a local `revert` are standalone `retry` and `rethrow`:

```vir
try(isolate: [attempts]):
    perform_operation()
revert
    attempts -= 1
    if attempts > 0 do
        retry
    end
    rethrow
end
```

- `retry` is valid only in the local `revert` of an enclosing `try`; it restores documented `isolate` snapshots and restarts that exact `try`.
- `rethrow` is valid only while handling a current error; it preserves `erx` and propagates to the next outer compensation boundary.
- Both statements terminate their control-flow path; following statements on that path are unreachable.
- Through Vir 2.x, implementations may accept legacy `resume retry` and `resume revert` with a stable deprecation diagnostic. Formatters and generators emit only `retry` and `rethrow`; legacy removal is no earlier than Vir 3.0.

See human spec §13.7. Prefer copying a working pattern from the repo over inventing `catch` / `finally` keywords.

## Agent rules

1. Never invent `try/catch/finally` or `Result.unwrap()` unless that API exists in referenced stdlib.
2. Function cleanup → `ensure` / `revert`, not Rust `Drop` glosses.
3. Close the function with `end.` after ensure/revert sections.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-04 | 2.1.0 | Defined canonical local compensation transfers `retry` and `rethrow` with a Vir 2.x compatibility window |
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/errors.md` and assigned stable ID `VIR-SPC-0012` |
