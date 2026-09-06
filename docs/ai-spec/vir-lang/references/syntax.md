# Vir Syntax (AI Spec)

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
