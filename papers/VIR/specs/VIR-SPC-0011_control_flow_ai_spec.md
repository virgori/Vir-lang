---
id: "VIR-SPC-0011"
type: "SPEC"
domain: "VIR"
title: "Vir Control Flow (AI Spec)"
status: "ACTIVE"
version: "2.0.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-02"
owners:
  - "VIR"
components: []
aliases:
  - "docs/ai-spec/vir-lang/references/control-flow.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0011 — Vir Control Flow (AI Spec)

**Spec:** Vir v2.0  
Control constructs close with **`end`** (not `end.`).

## if / eif / else

```vir
if x > 10 do
    print(x)
eif x > 5 do
    print("mid")
else
    print("small")
end
```

- **`eif`**, never `elif` / `else if`
- `else` has no `:`
- One `end` closes the whole chain

## when … loop (while)

```vir
when x > 0 loop
    x = x - 1
end
```

Never invent `while`.

## for range

```vir
for i in 0..10 do
    print(i)    # 0 .. 9
end
```

`in` here is the for-loop keyword, not the param section.

## loop forms

| Form | Meaning |
|---|---|
| `loop` … `end` | Infinite until `break` |
| `when cond loop` … `end` | While-style |
| `loop N:` … `end` | Repeat N times |

```vir
loop
    if done do
        break
    end
end

loop 5:
    print(7)
end
```

## break / skip

```vir
break    # leave nearest loop
skip     # next iteration (not continue)
```

## case

Use Vir `case` patterns from human spec §21 / nearby tests. Close with `end`. Do not invent Rust `match` / C `switch` syntax.

```vir
# Prefer copying a real case from tests/ or stdlib/vir/
```

## arena (scoped sub-arena)

`arena:` / `arena(capacity: N):` opens a scoped memory reclamation block $\rightarrow$ closes with **`end`**.

```vir
when active loop
    arena:
        var msg = receive()
        handle(msg)
    end
end
```

`arena:` uses the same escape rules as ordinary control scopes. Moving an owned
value into a longer-lived owner, or returning it with `out`, makes the compiler
promote its complete owned graph to the nearest region with sufficient lifetime.
The source binding is invalid after the move. Borrows (`&`/`&mut`) may not
escape, and a raw pointer does not extend lifetime. At `end`, only non-escaping
allocations are reclaimed; there is no separate `escape` keyword.

## Agent checklist

- [ ] No `while` / `elif` / `continue` / braces
- [ ] `do` or `loop` after expressions
- [ ] Control (`if`, `when`, `for`, `loop`, `case`, `try`, `arena`) → `end`; definitions → `end.`

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/control-flow.md` and assigned stable ID `VIR-SPC-0011` |
