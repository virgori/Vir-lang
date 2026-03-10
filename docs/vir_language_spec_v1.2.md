# Vir Language Core Syntax Specification v1.2

## Overview

Vir v1.2 is a structured, block-scoped language with explicit delimiters.
All blocks close with `end`. The colon `:` opens a block. Statements terminate with `;`.

---

## 1. Comments

```vir
# single-line comment

##
  block comment
  spanning multiple lines
##
```

---

## 2. Module Structure

Modules follow a strict ordering:

```
include → const → var → entity → func → export → share
```

### 2.1 Include

```vir
include math;
include io;
```

### 2.2 Constants

```vir
const PI: 3.14159;
const MAX_SIZE: 1024;
```

### 2.3 Module State (var block)

Pascal-style variable declarations for module-level state:

```vir
var
    counter:int;
    mode:string;
```

### 2.4 Export / Share

```vir
export add, subtract;      # export functions
share counter, mode;        # share module state
```

### 2.5 Import

```vir
import add, subtract, get counter, mode from math;
```

- `import func1, func2` — import functions
- `get state1, state2` — import shared state
- `from module` — source module

---

## 3. Functions

### 3.1 Basic Function

```vir
func add:
    in(a:int; b:int; result:int)
    result = a + b;
    out result;
end
```

- `func <name>:` — function definition, `:` opens block
- `in(params)` — parameter declaration, `;` separates params
- `out <expr>;` — return value (replaces `return`)
- `end` — closes function

### 3.2 Async Function

```vir
async func fetchData:
    in(url:string)
    # ... async operations ...
    out data;
end
```

### 3.3 Forward Declaration

```vir
has processData;    # declare before defining
```

### 3.4 Named Arguments

```vir
sum(a=5; b=10);     # call with named args, ; separator
```

---

## 4. Entity (Struct)

```vir
entity User:
    name:string;
    age:int;
end
```

### 4.1 Method

```vir
method User.print:
    out name;
end
```

### 4.2 Class (Entity + Method bundle)

```vir
class Account
    entity Account:
        balance:int;
    end
    method Account.deposit:
        in(amount:int)
        balance = balance + amount;
    end
end
```

---

## 5. Control Flow

### 5.1 If / Eif / Else

```vir
if x > 10:
    print x;
eif x > 5:
    print "medium";
else
    print "small";
end
```

- `eif` replaces `elif` (else-if)
- `else` has no colon
- `end` closes the entire if block

### 5.2 Loop (Infinite)

```vir
loop
    # body
    if done:
        break;
    end
end
```

### 5.3 When Loop (Conditional)

```vir
when x > 0 loop
    x = x - 1;
end
```

- `when <condition> loop` replaces `while`
- `skip;` replaces `continue`

### 5.4 Break / Skip

```vir
break;      # exit loop
skip;       # continue to next iteration (replaces 'continue')
```

---

## 6. Case Expression

```vir
case color
    "red": print "stop";
    "green": print "go";
    "yellow": print "caution";
else
    print "unknown";
end
```

---

## 7. Map

```vir
map
    "name": "Alice";
    "age": 30;
end
```

---

## 8. Error Handling

```vir
out action try fallback error ErrorName end
```

Example:
```vir
out divide(a, b) try 0 error DivisionError end
```

---

## 9. Task / Async

```vir
task fetchResult wait fetchData;
```

---

## 10. Operators

### 10.1 Arithmetic

| Operator | Description   | Precedence |
|----------|---------------|------------|
| `^`      | Power         | 30         |
| `*`      | Multiply      | 20         |
| `/`      | Divide        | 20         |
| `%`      | Percent       | 18         |
| `mod`    | Remainder     | 18         |
| `+`      | Add           | 10         |
| `-`      | Subtract      | 10         |

### 10.2 Comparison

| Operator | Description      | Precedence |
|----------|------------------|------------|
| `==`     | Equal            | 5          |
| `!=`     | Not equal        | 5          |
| `?=`     | Safe equal       | 5          |
| `?=/=`   | Safe not-equal   | 5          |
| `>`      | Greater than     | 6          |
| `<`      | Less than        | 6          |
| `>=`     | Greater or equal | 6          |
| `<=`     | Less or equal    | 6          |

### 10.3 Logical

| Operator | Description | Precedence |
|----------|-------------|------------|
| `&`      | AND         | 3          |
| `||`     | OR          | 2          |
| `!`      | NOT         | 28 (unary) |

### 10.4 Bitwise (keyword operators)

| Keyword | Description    | Precedence |
|---------|----------------|------------|
| `xor`   | Bitwise XOR    | 2          |
| `shl`   | Shift left     | 12         |
| `shr`   | Shift right    | 12         |

### 10.5 Special Operators

| Operator | Description         | Precedence |
|----------|---------------------|------------|
| `.`      | Member access       | 40         |
| `?.`     | Safe member access  | 40         |
| `?`      | Existence check     | —          |
| `:~`     | Pattern match       | 8          |
| `>>`     | Type cast           | 12         |

### 10.6 Precedence Table (high → low)

```
() → ?. . → ! - → ^ → * / → % mod → + -
→ >> shl shr → :~ → > < >= <=
→ == != ?= ?=/= → & → xor → || → =
```

---

## 11. Types

| Type     | Description |
|----------|-------------|
| `int`    | Integer     |
| `float`  | Float       |
| `string` | String      |
| `bool`   | Boolean     |
| `array`  | Array       |
| `map`    | Map/Dict    |

---

## 12. Literals

```vir
42              # int
3.14            # float
"hello"         # string
true / false    # boolean
none            # null
```

---

## 13. Changes from v1.1

| Old (v1.1)      | New (v1.2)    | Notes                     |
|------------------|---------------|---------------------------|
| `return <expr>`  | `out <expr>;` | Return keyword            |
| `continue`       | `skip;`       | Continue keyword          |
| `elif`           | `eif`         | Else-if keyword           |
| `while <cond>`   | `when <cond> loop` | Conditional loop     |
| `**`             | `^`           | Power operator            |
| `%` (modulo)     | `mod`         | Remainder is now keyword  |
| `%` (unused)     | `%` (percent) | Percent operator          |
| `&&` (AND)       | `&`           | Logical AND               |
| `^` (XOR)        | `xor`         | XOR is now keyword        |
| `>>` (shift)     | `shr`/`>>`    | `>>` is cast, `shr` is shift |
| `struct`/`record`| `entity`      | Struct-like type          |
| —                | `method`      | Method on entity          |
| —                | `has`         | Forward declaration       |
| —                | `share`       | State sharing             |
| —                | `task`/`wait` | Async task                |
| —                | `case`        | Switch/match expression   |
| —                | `map`         | Map literal               |
| —                | `try`/`error` | Error handling            |
| —                | `include`     | Module include            |
| —                | `## ... ##`   | Block comments            |

---

## 14. Multilingual Support

Vir supports programming in multiple natural languages through the SubLib adapter system:

- **Vietnamese (vi)**: `nếu`, `hàm`, `trả về` → `out`, `còn nếu` → `eif`
- **Chinese (zh)**: `如果`, `函数`, `返回` → `out`, `否则如果` → `eif`
- **Japanese (ja)**: `もし`, `関数`, `返す` → `out`, `それ以外もし` → `eif`
- **Korean (ko)**: `만약`, `함수`, `반환` → `out`, `아니면 만약` → `eif`
- **English (en)**: Direct keyword mapping (identity adapter)

All natural language phrases are mapped through the KeywordRegistry to canonical TokenKind values.
