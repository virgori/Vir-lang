---
id: "VIR-SPC-0015"
type: "SPEC"
domain: "VIR"
title: "Vir Syntax (AI Spec)"
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
  - "docs/ai-spec/vir-lang/references/syntax.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0015 — Vir Syntax (AI Spec)

**Extension:** `.vri`  
**Spec:** Vir v2.0

## Comments

```vir
# line comment

#*#
  block comment
#*#

## legacy block still accepted ##
```

## Separators

One rule for statement / declaration groups:

```text
separator := ";" | NEWLINE
```

- Same line → `;` required between items: `print(1); print(2)`
- Newlines alone are enough
- Trailing `;` before newline is OK

`,` is for flat lists only (call args, list elements) — not the block separator.

## Block openers

| Situation | Opener |
|---|---|
| Expression then body | `do` or `loop` |
| No expression before body | `:` |

```vir
if cond do … end
when cond loop … end
for i in 0..n do … end
func name: … end.
try: … end
entity Foo: … end.
```

## Block closers (law)

| Construct | Close with |
|---|---|
| Definitions: `func`, `async func`, `entity`, `method`, `enum`, `register`, `mold`, … | `end.` |
| Control / statement blocks: `if`, `when`, `for`, `loop`, `case`, `try`, `arena`, … | `end` |

Continuations (`else`, `eif`, `ensure`, `revert`) — **no** `:` opener.

## Keywords agents confuse (forbidden → Vir)

| Invented | Correct Vir |
|---|---|
| `fn` / `function` / braces | `func name:` … `end.` |
| `elif` / `else if` | `eif` |
| `while` | `when cond loop` |
| `continue` | `skip` |
| `return` | `out` |
| `.vir` | `.vri` |
| `{ }` blocks | `do` / `loop` / `:` + `end` / `end.` |

## Minimal program

```vir
func main:
    print("Hello")
    out 0
end.
```

## Identifiers & literals

```vir
42
3.14
"hello"
"Hello $name"      # interpolation
true / false
none
[1, 2, 3]          # list
["a": 1, "b": 2]   # dict (elements contain :)
```

## Operators (high-signal)

- Arithmetic: `+` `-` `*` `/` `^` ; remainder is **`mod`** (not `%` — `%` is percent)
- Power `^` is right-associative. With integer operands, a non-negative
  exponent returns `int`; a negative exponent is valid and returns the
  binary64 reciprocal as `float` (`2^-3 == 0.125`).
- Compare: `==` `!=` `>` `<` `>=` `<=` ; nil-safe `?=` `?=/=`
- Logic: `&` `||` `!`
- Bitwise keywords: `and` `or` `xor` `shl` `shr`
- Member: `.` `?.`

## Variables

```vir
var x = 42
var y: i32 = 42
const PI = 3.14
```

## Generics

Vir's canonical generic syntax is `of (...)` in declarations, type applications, constructors, and explicit generic calls.

```vir
entity Box of (T):
    value: T
end.

func wrap of (T)(value: T) -> Box of (T):
    out Box of (T)(value: value)
end.

var boxed = wrap of (int)(42)
var nested: dict of (string, Box of (int))
```

- `of` is contextual, not a general infix operator.
- `(...)` following `of (...)` contains runtime call/constructor arguments.
- Tensor is not an ordinary generic: write `tensor[T; S...]`, never `tensor of (T)[S...]` or `tensor(T)[S...]`.
- `[...]` remains list/dict literal, indexing, or dimension syntax.
- Do not generate `Box<T>`; angle-bracket generics are legacy compatibility syntax only.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/syntax.md` and assigned stable ID `VIR-SPC-0015` |
