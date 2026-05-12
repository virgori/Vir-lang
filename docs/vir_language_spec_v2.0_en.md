# Vir Language Specification v2.0

*Version: 2.0 | Date: April 11, 2026 | Status: Living Document*
*Supersedes: v1.2 (March 2026)*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Comments](#2-comments)
3. [Module System](#3-module-system)
4. [Types](#4-types)
5. [Variables & Constants](#5-variables--constants)
6. [Functions](#6-functions)
7. [Entity & Packed Entity](#7-entity--packed-entity)
8. [Enum](#8-enum)
9. [Control Flow](#9-control-flow)
10. [Operators](#10-operators)
11. [UFCS — Uniform Function Call Syntax](#11-ufcs--uniform-function-call-syntax)
12. [String Interpolation](#12-string-interpolation)
13. [Error Handling — throw / ensure / revert](#13-error-handling--throw--ensure--revert)
14. [Parameter Blocks — in / ref / out](#14-parameter-blocks--in--ref--out)
15. [FFI — @bind](#15-ffi--bind)
16. [Register & Mold — Bit-level Structs](#16-register--mold--bit-level-structs)
17. [Compile-time Execution — precomp](#17-compile-time-execution--precomp)
18. [Entry Point — @entry](#18-entry-point--entry)
19. [Arrays](#19-arrays)
20. [Dict & Map](#20-dict--map)
21. [Case Expression](#21-case-expression)
22. [Async / Task](#22-async--task)
23. [Port — Inter-worker Signal Coordination](#23-port--inter-worker-signal-coordination)
24. [GPU, SIMD & Atomic Primitives](#24-gpu-simd--atomic-primitives)
25. [System Intrinsics](#25-system-intrinsics)
26. [Multilingual Support](#26-multilingual-support)
27. [Keyword Reference](#27-keyword-reference)
28. [Operator Precedence Table](#28-operator-precedence-table)
29. [Changes from v1.2](#29-changes-from-v12)

---

## 1. Overview

Vir is a compiled, structured, block-scoped systems programming language. It compiles to native ARM64 (Mach-O), x86-64 (ELF), and WebAssembly — with zero external dependencies (no libc, no linker).

**Core principles:**
- Definition blocks (`func`, `entity`, `method`, `enum`, `register`, `mold`) open with `:` and close with `end.`
- Control-flow blocks (`if` / `eif`) open with `do` and close with `end`
- Colon `:` is also used for type annotation and key-value mapping (dict, case, map)
- Semicolons are permitted but optional (newline is a valid terminator)
- `out` replaces `return`, `eif` replaces `elif`, `skip` replaces `continue`
- `when ... loop` replaces `while`

```vir
func main:
    var name = "Vir"
    print("Hello from $name!")
end.
```

---

## 2. Comments

```vir
# single-line comment

##
  block comment
  spanning multiple lines
##
```

---

## 3. Module System

Vir manages source code using **Directory Mapping**. The compiler uses the dot `.` separator to traverse directory trees and builds a Dependency Graph to prevent circular imports.

### 3.1 Module Ordering

Modules follow a strict declaration order:

```
include → import/get → const → var → entity → func → export → share
```

### 3.2 Include — Physical File Loading

Declares the presence of a source file and establishes a namespace.

```vir
include math;                    # loads math.vri, namespace = math
include net.http;                # loads net/http.vri, namespace = http
include net.http as web;         # loads net/http.vri, namespace = web
```

**Resolution:** `A.B.C` → searches for `A/B/C.vri` from project root.

### 3.3 Import — Bring Functions into Scope

```vir
import add from math;            # call add() directly
import get from net.http as fetch;  # call fetch() instead of get()
```

### 3.4 Get — Bring Variables/Constants into Scope

```vir
get MAX_RETRY from net.config;   # use MAX_RETRY directly
get PI from math as TAU;         # alias
```

### 3.5 Export / Share / Port

```vir
export add, subtract;            # export functions to other modules
share counter, mode;             # share module-level state (raw data, same process)
port signals, commands;          # expose named signal ports (inter-worker coordination)
```

**`share` vs `port`:**

| | `share` / `ref` | `port` |
|---|---|---|
| Purpose | Pass raw data between modules in the same process | Coordinate signals between workers / tasks |
| Access model | Direct memory read/write | Send/receive message (queue-backed) |
| Ownership | Borrow (`&`) or move | Message copy — sender retains no handle |
| Typical use | Framebuffer, audio buffers, lookup tables | Gateway ↔ Satellite, producer ↔ consumer pipelines |
| Blocking | No | `recv` blocks until a message arrives (or timeout) |

### 3.6 Combined Import

```vir
import add, subtract, get counter, mode from math;
```

### 3.7 Usage

```vir
func main:
    var resp = http.get("/api")     # qualified call via namespace
    var resp2 = fetch("/api")       # aliased import
    print MAX_RETRY                 # imported constant
end.
```

### 3.8 Dependency Graph

Each time the compiler encounters `include`, `import`, or `get`, it performs these steps:

1. **Cache check:** Is module path `A.B.C` already loaded?
2. **Circular check:** If module status is `Parsing`, emit error `"Circular Dependency detected: A.B.C"`
3. **Mapping:** Resolve `A.B.C` → `A/B/C.vri`, load and parse source file
4. **Registration:** Add identifiers to the current module's Symbol Table

Module states: `NotLoaded` → `Parsing` → `Parsed`

---

## 4. Types

### 4.1 Primitive Types

| Group | Type | Size | Description |
|-------|------|------|-------------|
| **Signed integer** | `i8`, `i16`, `i32`, `i64` | 1, 2, 4, 8 bytes | Two's complement |
| **Unsigned integer** | `u8`, `u16`, `u32`, `u64` | 1, 2, 4, 8 bytes | Registers, counters, raw data |
| **Flexible integer** | `int`, `uint` | Platform word | 8 bytes on 64-bit CPUs |
| **Floating point** | `float` | 8 bytes | IEEE 754 double precision |
| **Boolean** | `bool` | 1 byte | `true` or `false` |
| **String** | `string` | Pointer + length | Immutable, Arena-allocated |
| **Pointer** | `ptr` | Platform word | Raw pointer, FFI-compatible |

### 4.2 String Memory Model

Strings in Vir are **immutable, length-prefixed byte sequences** stored in an arena allocator.

```
┌──────────┬──────────────────────────┐
│ len (u64)│  UTF-8 bytes (no NUL)    │
└──────────┴──────────────────────────┘
      ↑
   string variable points here
```

**Key properties:**

| Property | Detail |
|----------|--------|
| **Encoding** | UTF-8 |
| **Mutability** | Immutable — concatenation creates a new string |
| **Allocation** | Arena-allocated (bump allocator, freed at scope exit or program end) |
| **Terminator** | No NUL terminator (length-prefixed). FFI functions use explicit `ptr` + length |
| **Comparison** | Byte-by-byte (`==` compares content, not pointer) |
| **Interpolation** | `"$var"` / `"$(expr)"` creates a new string via `StrCat` chain |

**String operations:**

```vir
var s = "Hello"
var t = s :~ " World"       # concatenation → new string "Hello World"
print len(s)                 # → 5  (byte length)
print s[0]                   # → 72 (ASCII 'H', returns u8)
```

**FFI interop:**

```vir
@bind(c)
func puts(s: ptr) -> int:
end.

func main:
    var msg = "Hello\n"
    puts(msg as ptr)         # cast to raw pointer — caller must ensure NUL or use length
end.
```

**Ownership:** Strings are never freed individually. The arena allocator reclaims all string memory in bulk when the enclosing scope (function or module) exits. This eliminates use-after-free and double-free bugs without a garbage collector.

### 4.2 Compound Types

| Type | Description | Semantics |
|------|-------------|----------|
| `entity` | Struct-like named record | **Move** |
| `packed entity` | Contiguous layout, no padding (FFI/mmap) | **Move** |
| `enum` | Named integer constants | **Copy** |
| `register` | Bit-level hardware register mapping | **Copy** |
| `mold` | General-purpose bit-field (data packing) | **Copy** |
| `array` | Dynamic growable array | **Move** |
| `dict` | Key-value dictionary | **Move** |
| `map` | Transformation expression | expression |
| `flux<T,N>` | Fixed-width SIMD vector — N elements of type T | **Copy** |
| `deck` | Shared CPU-GPU buffer (typed, fixed-size) | **Move** (handle) |

### 4.3 Literals

```vir
42                # int
3.14              # float
"hello"           # string
"Hello $name"     # interpolated string
true / false      # boolean
none              # null
[1, 2, 3]         # array literal
```

### 4.4 Type Annotations

Type annotations are optional for local variables (inferred) but required for FFI and packed entity fields.

```vir
var x = 42               # inferred as int
var y: i32 = 42           # explicit i32
func add(a: i32, b: i32) -> i32:
    out a + b
end.
```

### 4.5 Memory Architecture

Vir uses three memory regions with no garbage collector:

| Region | Allocation | Deallocation | Used for |
|--------|-----------|-------------|----------|
| **Stack** | Automatic (push/pop) | On function exit | Local variables, parameters, temporaries |
| **Arena** | Bump allocator | Entire arena freed when scope ends | Entity, dynamic strings, arrays, dicts |
| **Static** | Compile-time | Never | `const`, string literals, `precomp` |

**Arena allocator:**
- Allocates via bump pointer — O(1), no fragmentation
- No per-object deallocation — the entire arena is freed at once
- Each `main` function (or large scope) creates a default arena
- No GC, no reference counting

**String:**
- Immutable — all concatenation/interpolation creates a new string
- Internal representation: `{ ptr: *u8, len: u64 }`
- String literals → Static region (zero-cost, no runtime allocation)
- Interpolated / concatenated strings → allocated in Arena

**No ownership/borrow:**
Vir does not have Rust-style ownership or borrow checking. Instead, it relies on **arena-scoped lifetime** — all objects live until the arena that owns them is freed. This eliminates use-after-free and double-free without runtime overhead.

### 4.6 Sub-arena Block — `arena:`

Long-running loops (servers, event loops, stream processors) would exhaust the default arena because the bump pointer never rewinds. The `arena:` block creates a **temporary sub-arena** that is destroyed automatically on every iteration or block exit.

```vir
func serve_forever:
    loop
        var conn = accept()

        arena:
            # All allocations here (strings, entities, arrays)
            # live in a fresh sub-arena
            var req = parse_request(conn)
            var resp = build_response(req)
            send(conn, resp)
        end
        # Sub-arena freed here — all request-scoped memory reclaimed
    end
end.
```

**Semantics:**

| Property | Behavior |
|----------|----------|
| Scope | Block-scoped — freed when `end` is reached |
| Nesting | `arena:` blocks can nest; each has its own bump pointer |
| Default capacity | Compiler-chosen (e.g. 64KB); resizable via `arena(capacity: 256KB):` |
| Interaction with `try` | `arena:` inside `try:` is freed before local `revert` runs |
| Stack variables | Unaffected — only heap-allocated objects (entity, string, array, dict) use the sub-arena |

**With explicit capacity:**

```vir
arena(capacity: 1MB):
    var big_buf = arr_new(100000)
    process(big_buf)
end
```

**Rule:** Any object allocated inside `arena:` must not escape the block. The compiler emits a diagnostic if a reference to an arena-local object is stored in a variable whose lifetime exceeds the block.

### 4.7 Allocator API

```vir
# Default arena — created automatically by the compiler for `main`
var buf = arena_alloc(1024)           # allocate 1024 bytes from current arena
arena_reset()                          # free all arena allocations at once

# Custom arena for subsystems
var scratch = arena_new(64 * 1024)     # 64KB arena
var ptr = arena_alloc_from(scratch, 512)
arena_free(scratch)                    # free entire arena
```

| Function | Description |
|----------|-------------|
| `arena_alloc(size)` | Allocate from default arena (bump pointer) |
| `arena_reset()` | Reset default arena (free all at once) |
| `arena_new(capacity)` | Create a new arena with given capacity |
| `arena_alloc_from(arena, size)` | Allocate from a specific arena |
| `arena_free(arena)` | Destroy an arena and all its allocations |

For FFI or bare-metal scenarios requiring manual management, use `ptr` + `malloc`/`free` via `@bind(c)`.

### 4.8 Ownership, Borrow Checker, and Move Semantics

Vir has a **compile-time borrow checker** that enforces memory safety without garbage collection or reference counting. The borrow checker runs as a compiler pass after IR lowering, before codegen.

#### Ownership Rules

```
Rule 1:  Each value has exactly ONE owner at any point in time.
Rule 2:  When the owner leaves scope → value is dropped automatically.
Rule 3:  Values can be BORROWED:
             &     = shared borrow    (read-only, many simultaneous)
             &mut  = exclusive borrow (read-write, one at a time)
Rule 4:  Shared borrows (&) and mutable borrows (&mut) cannot coexist.
Rule 5:  A borrow cannot outlive its owner.
Rule 6:  MOVE transfers ownership — the old owner becomes invalid.
```

**Type categories:**

| Category | Types | Semantics |
|----------|-------|-----------|
| **Copy** | `int`, `i8`–`i64`, `u8`–`u64`, `float`, `bool` | Implicit copy — no borrow needed |
| **Static** | String literals | Static lifetime — no borrow/move |
| **Move** | `string`, `array`, `entity`, `dict` | Move on assignment; borrow with `&`/`&mut` |

#### Ownership Syntax

```vir
# Owned parameter — caller moves value in
func process(data: [i32]) -> [i32]:
    out data                        # ownership transferred to caller
end.

# Shared borrow — read-only, does not consume
func sum_all(data: &[i32]) -> int:
    var total = 0
    for x in data:
        total = total + x
    end
    out total
end.

# Mutable borrow — exclusive write access
func zero_first(data: &mut [i32]):
    data[0] = 0
end.
```

#### Move semantics

```vir
# Copy types — assignment is a copy, original stays valid
let x = 10
let y = x           # COPY — x still valid
print(x + y)        # OK

# Move types — assignment transfers ownership
let arr = [1, 2, 3]
let arr2 = arr      # MOVE — arr is now invalid
# print(arr[0])     # COMPILE ERROR: use of moved value 'arr'

# To keep original, borrow instead
let s = sum_all(&arr2)   # shared borrow — arr2 still valid after
```

#### Borrow conflicts

```vir
let arr = [1, 2, 3]

# OK — multiple shared borrows
let s1 = sum_all(&arr)
let s2 = sum_all(&arr)   # &arr + &arr → OK

# ERROR — shared + mutable borrow overlap
let r = &arr             # shared borrow begins
zero_first(&mut arr)     # COMPILE ERROR: cannot borrow as &mut
                         # while shared borrow is live
print(r[0])              # r is still in scope here → conflict
```

#### Auto-drop and arena scoping

Arena-allocated objects (`array`, `entity`, `string`, `dict`) are dropped automatically when their owner leaves scope. The borrow checker inserts `Q_FREE` drop instructions at the computed death point — no `free()` calls needed.

```vir
func example:
    let arr = [1, 2, 3]     # allocated in function arena
    if condition do
        let tmp = [4, 5]    # allocated in scope arena (watermark)
        process(tmp)
    end                      # tmp dropped here (watermark restore)
    print(arr[0])            # arr still alive
end.                          # arr dropped here (function arena reset)
```

Objects that **escape** to the caller (via `out` or move-return) are promoted to the heap by escape analysis — the caller owns them and they are dropped when the caller's scope ends.

#### Borrow checker pipeline position

```
AST → ir_lower → Q-IR → TCO pass → ★ Borrow Check ★ → Optimizer → Codegen
                                         │
                                         ├── Ownership inference
                                         ├── Borrow conflict validation
                                         ├── Lifetime analysis
                                         └── Drop point insertion (Q_FREE)
```

**Compile-time cost:** +5–10% compile time for the borrow check pass. Zero runtime overhead — all checks are resolved at compile time.

---

## 5. Variables & Constants

### 5.1 Variable Declaration

```vir
var counter = 0           # mutable, inferred type
var name: string = "Vir"  # mutable, explicit type
let result = compute()    # immutable binding
```

- `var` — mutable variable
- `let` — immutable binding (cannot reassign after initialization)

**Grouped declaration** — use `var` once, then indent multiple variables:

```vir
var x = 10;
    y = 20;
    z = 30            # no ';' ends the group
```

This avoids repeating `var` for each variable. The grouping follows the same `;` convention as parameter blocks (see [§14](#14-parameter-blocks--in--ref--out)).

### 5.2 Constants

```vir
const PI: 3.14159;
const MAX_SIZE: 1024;
const BANNER: "Hello Vir";
```

Constants are evaluated at compile time and cannot be reassigned.

### 5.3 Module-level State

```vir
var
    counter: int;
    mode: string;
```

Module-level variables are accessible by all functions within the module. Use `share` to expose them to other modules.

### 5.4 Reassignment

```vir
var x = 5
x = x + 1         # reassign
x = compute(x)    # reassign with function result
```

---

## 6. Functions

### 6.1 Basic Function

```vir
func add(a, b):
    out a + b
end.
```

- `func <name>(<params>):` — defines a function
- `out <expr>` — returns a value (replaces `return`)
- `end` — closes the function body

### 6.2 Typed Parameters

```vir
func add(a: int, b: int) -> int:
    out a + b
end.
```

### 6.3 Multi-parameter

```vir
func clamp(value, lo, hi):
    if value < lo do
        out lo
    end
    if value > hi do
        out hi
    end
    out value
end.
```

### 6.4 Named Arguments

```vir
sum(a=5; b=10);     # call with named args, ; separator
```

### 6.5 Forward Declaration

```vir
has processData;     # declare before defining
```

### 6.6 Higher-Order Functions

Functions can be passed as values:

```vir
func double(x):
    out x * 2
end.

func apply(f, value):
    out f(value)
end.

func main:
    var f = double        # function pointer
    print f(5)            # → 10
    print apply(double, 7) # → 14
end.
```

### 6.7 Recursion

```vir
func factorial(n):
    if n <= 1 do
        out 1
    end
    out n * factorial(n - 1)
end.
```

### 6.8 Scope Guards (ensure / revert)

See [§13 Error Handling](#13-error-handling--throw--ensure--revert).

---

## 7. Entity & Packed Entity

### 7.1 Entity (struct)

```vir
entity User:
    name: string
    age: int
end.
```

**Creating an instance:**

```vir
var u = User(name: "Alice", age: 30)
print u.name          # field access
u.age = 31            # field assignment
```

**Internal layout:** Arena-allocated, fields addressed by slot index.

### 7.2 Method

Vir has a `method` keyword for defining functions bound to an entity. Methods receive the entity instance as an implicit `this`:

```vir
entity User:
    name: string
    age: int

    method greet:
        print("Hello, $this.name")
    end.

    method birthday:
        this.age = this.age + 1
    end.
end.

var u = User(name: "Alice", age: 30)
u.greet()              # calls method — prints "Hello, Alice"
u.birthday()           # mutates u.age → 31
```

**Additionally**, standalone functions can be called as methods via UFCS (see [§11 UFCS](#11-ufcs--uniform-function-call-syntax)). When the compiler sees `x.foo()`:
1. If `x` is an entity and `foo` is a field → field access
2. If `foo` is a `method` of entity type → method call (implicit `this`)
3. If `foo(x, ...)` exists as a standalone function → UFCS call
4. Otherwise → compile error

### 7.3 Packed Entity

A `packed entity` guarantees contiguous memory layout with no padding, suitable for FFI interop, memory-mapped I/O, and binary protocols.

```vir
packed entity Vec2:
    x: int
    y: int
end.

packed entity TCPHeader:
    src_port: u16
    dst_port: u16
    seq_num: u32
    ack_num: u32
    flags: u16
end.
```

| Property | `entity` | `packed entity` |
|----------|----------|-----------------|
| Memory layout | Arena slots | Contiguous, no padding |
| Field access | Slot index | Byte offset |
| Alignment | Platform-dependent | 1-byte aligned |
| Use case | General purpose | FFI, mmap, hardware |
| `sizeof` | Runtime | Compile-time (`Σ field_sizes`) |

**Usage is identical to regular entity:**

```vir
var v = Vec2(x: 3, y: 4)
print v.x                 # → 3
```

---

## 8. Enum

```vir
enum Color:
    Red
    Green
    Blue
end.

enum Priority:
    Low
    Medium
    High
end.
```

**Access:**

```vir
var c = Color.Red
if c == Color.Green do
    print("Go!")
end
```

Enum values are integer constants starting from 0.

---

## 9. Control Flow

### 9.1 If / Eif / Else

```vir
if x > 10 do
    print x
eif x > 5 do
    print("medium")
else
    print("small")
end
```

- `eif` replaces `elif`/`else if`
- `else` has no colon
- `end` closes the entire block

### 9.2 When Loop (while)

```vir
when x > 0 loop
    x = x - 1
end
```

### 9.3 For Range

```vir
for i in 0..10:
    print i         # prints 0 through 9
end
```

### 9.4 Loop (infinite)

```vir
loop
    if done do
        break
    end
end
```

### 9.5 Loop N (counted)

```vir
loop 5:
    print 7         # prints 7 five times
end
```

### 9.6 Break / Skip

```vir
break        # exit the innermost loop
skip         # skip to next iteration (replaces 'continue')
```

---

## 10. Operators

### 10.1 Arithmetic

| Operator | Description | Precedence |
|----------|-------------|------------|
| `^` | Power | 30 |
| `*` | Multiply | 20 |
| `/` | Divide | 20 |
| `%` | Percent | 18 |
| `mod` | Remainder (modulo) | 18 |
| `+` | Add | 10 |
| `-` | Subtract | 10 |

### 10.2 Comparison

| Operator | Description | Precedence |
|----------|-------------|------------|
| `==` | Equal | 5 |
| `!=` | Not equal | 5 |
| `?=` | Safe equal (nil-safe) | 5 |
| `?=/=` | Safe not-equal | 5 |
| `>` | Greater than | 6 |
| `<` | Less than | 6 |
| `>=` | Greater or equal | 6 |
| `<=` | Less or equal | 6 |

### 10.3 Logical

| Operator | Description | Precedence |
|----------|-------------|------------|
| `&` | Logical AND | 3 |
| `\|\|` | Logical OR | 2 |
| `!` | Logical NOT (unary) | 28 |

### 10.4 Bitwise

| Keyword | Description | Precedence |
|---------|-------------|------------|
| `and` | Bitwise AND | 3 |
| `or` | Bitwise OR | 2 |
| `xor` | Bitwise XOR | 2 |
| `shl` | Shift left | 12 |
| `shr` | Shift right | 12 |

### 10.5 Special

| Operator | Description | Precedence |
|----------|-------------|------------|
| `.` | Member access / UFCS call | 40 |
| `?.` | Safe member access | 40 |
| `?` | Existence check | — |
| `:~` | Pattern match | 8 |
| `>>` | Type cast | 12 |
| `as` | Type conversion | 12 |

### 10.6 Assignment

```vir
x = 10               # simple assignment
x = x + 1            # compound (no += syntax — explicit is better)
```

---

## 11. UFCS — Uniform Function Call Syntax

Any function can be called using dot-syntax on its first argument. This enables method-like calls without a class system.

### 11.1 Basic UFCS

```vir
func double(val):
    out val * 2
end.

func add_n(val, n):
    out val + n
end.

var x = 10
var a = x.double()           # → double(10) → 20
var b = x.add_n(5)           # → add_n(10, 5) → 15
```

### 11.2 The `this` Keyword

When a function's first parameter is named `this`, it signals the function is designed for UFCS usage:

```vir
func scale(this, n):
    out this * n
end.

func clamp(this, lo, hi):
    if this < lo do out lo end
    if this > hi do out hi end
    out this
end.

var x = 7
print x.scale(3)             # → 21
print x.clamp(0, 10)         # → 7
print 15.clamp(0, 10)        # → 10 (works on literals too)
```

### 11.3 UFCS Chaining

```vir
var result = x.double().add_n(3).clamp(0, 100)
# equivalent to: clamp(add_n(double(x), 3), 0, 100)
```

### 11.4 UFCS on Entity

```vir
entity User:
    name: string
    age: int
end.

func display(this: User):
    print("User: $this.name, age: $this.age")
end.

var u = User(name: "Alice", age: 30)
u.display()                  # → display(u)
```

**Resolution rule:**

| Syntax | Meaning |
|--------|--------|
| `x.foo` | Always **field access** — never calls a function |
| `x.foo()` | Function call — resolved in the order below |
| `x.foo(a, b)` | Function call with args — same resolution |

When the compiler sees `x.foo(args)`:
1. If `foo` is a `method` of the entity type → method call (implicit `this`)
2. If `foo` is a **callable field** (field of function-pointer type) → indirect call via field value
3. If `foo(x, args)` exists as a standalone function → UFCS call
4. Otherwise → compile error

Step 2 enables event-driven patterns where entity fields store callbacks:

```vir
entity Button:
    label: string
    on_click: ptr           # function pointer field
end.

func handle_click:
    print("clicked!")
end.

var btn = Button(label: "OK", on_click: handle_click)
btn.on_click()              # step 2 → indirect call via field value
```

> **Note:** `btn.on_click` (no parens) is still a field access — it reads the function pointer. `btn.on_click()` (with parens) **calls** the function pointer because step 2 detects that the field holds a callable type.

### 11.5 Field vs Function — No Ambiguity

Parentheses are the **sole** disambiguator between field access and function calls:

```vir
entity User:
    name: string
end.

func name(this: User) -> string:
    out "display: $this.name"
end.

var u = User(name: "Alice")
print u.name               # → "Alice"              (field access — no parens)
print u.name()             # → "display: Alice"     (UFCS call  — has parens)
```

This means a field and a function can share the same identifier without conflict. The compiler **never** guesses — `x.foo` is always a field, `x.foo()` is always a call.

---

## 12. String Interpolation

Vir supports inline string interpolation using the `$` prefix inside double-quoted strings.

### 12.1 Variable Interpolation

```vir
var name = "World"
print("Hello $name")             # → Hello World
```

### 12.2 Property Interpolation

```vir
var user = User(name: "Alice", age: 30)
print("Name: $user.name")        # → Name: Alice
```

### 12.3 Expression Interpolation

```vir
var price = 100
print("VAT: $(price * 10 / 100)")       # → VAT: 10
```

### 12.4 Escape Dollar Sign

```vir
print("Price: $$100")            # → Price: $100
```

### 12.5 Summary

| Type | Syntax | Example | Output |
|------|--------|---------|--------|
| Variable | `$var` | `"Hello $name"` | `Hello World` |
| Property | `$obj.prop` | `"User: $user.id"` | `User: 42` |
| Expression | `$(expr)` | `"Sum: $(a + b)"` | `Sum: 15` |
| Escape | `$$` | `"Price: $$100"` | `Price: $100` |

**Internal mechanism:** The lexer splits interpolated strings into `InterpStart`/`InterpEnd` tokens around identifier/expression tokens. The IR lowers them to a chain of `StrCat` operations, auto-wrapping integer values with `i_to_str()`.

### 12.6 Lexer Boundary Rules

The `$` interpolation is **not** greedy. The lexer consumes only what the grammar defines:

| Pattern | Lexer consumes | Example | Result |
|---------|---------------|---------|--------|
| `$ident` | One identifier (letters, digits, `_`) | `"val: $x"` | value of `x` |
| `$ident.ident` | Identifier + `.` + identifier (one dot-chain) | `"name: $user.name"` | field access |
| `$ident.ident.ident` | Up to N dot-chains | `"$a.b.c"` | nested field |
| `$(expr)` | Everything inside `()` as an expression | `"$(list[0])"` | element access |
| `$ident[...]` | **NOT consumed** — `[` stops the lexer | `"val: $list[0]"` | ❌ literal `[0]"` |

**Rule:** The `$` short form stops at the **first non-identifier, non-dot** character. Square brackets `[`, operators, and spaces are **not** consumed. For array indexing, dict access, or complex expressions, use the `$(...)` form:

```vir
var list = [10, 20, 30]
print("Bad:  $list[0]")          # → prints list value + literal "[0]"
print("Good: $(list[0])")        # → prints "10"

var m = dict[string, int] "a": 1 end
print("Bad:  $m[a]")             # → prints m value + literal "[a]"
print("Good: $(m[\"a\"])")       # → prints "1"
```

**Summary:** `$ident` and `$ident.prop` are convenience shortcuts. For **anything more complex** (indexing, arithmetic, method calls), use `$(expr)`.

---

## 13. Error Handling — throw / ensure / revert

Vir uses a function-local error model with three keywords:

| Keyword | Role | Analogous to |
|---------|------|-------------|
| `throw` | Raise an error, abort normal flow | `throw` (Java), `panic!` (Rust) |
| `ensure` | Code that **always** runs when leaving a function | `defer` (Go), `scope(exit)` (D) |
| `revert` | Code that runs **only** when `throw` occurs | `catch` (Java), `scope(failure)` (D) |

### 13.1 throw

```vir
func safe_div(a, b):
    if b == 0 do
        throw 1               # error code 1 = division by zero
    end
    out a / b
end.
```

Without `revert`/`ensure` in the function, `throw` terminates the process (emits ARM64 `BRK #1`).

### 13.2 ensure — Always Execute on Exit

```vir
func process_file(path):
    var fd = open(path)
    # ... work with file ...
    print 42
ensure
    close(fd)                  # always runs, even after throw
end.
```

**Output:** `42` then `close(fd)` executes.

`ensure` is the last block before `end`. It runs on both normal exits and thrown errors.

### 13.3 revert — Execute Only on Error

```vir
func transfer(from, to, amount):
    withdraw(from, amount)
    deposit(to, amount)
ensure
    log("transfer completed or rolled back")
revert
    refund(from, amount)       # only runs if throw occurred
end.
```

### 13.4 Combined Flow

```vir
func example:
    # body code runs here
    if bad_condition do
        throw 42
    end
    print("success")
ensure
    print("cleanup")           # always runs
revert
    print("error handler")     # runs only on throw
end.
```

**Execution order:**

| Scenario | Flow |
|----------|------|
| Normal exit (no throw) | body → ensure → return |
| Throw exit | body → throw → revert → ensure → return |

### 13.5 Error Value — `erx`

The thrown value is stored in the `erx` error register. The `revert` block can read it:

```vir
func compute(x):
    if x < 0 do
        throw 1        # negative input
    end
    if x > 1000 do
        throw 2        # overflow
    end
    out x * x
revert
    # erx contains 1 or 2
    print("Error occurred: $erx")
end.
```

### 13.6 Error Types and Convention

`throw` transmits a single integer value (stored in a dedicated register: ARM64 X19, x86-64 r12). Vir does not have exception objects — errors are **numeric codes**.

**Pattern 1: Error codes only (bare-metal safe)**

```vir
const ERR_NONE      = 0
const ERR_DIV_ZERO  = 1
const ERR_OVERFLOW  = 2
const ERR_NOT_FOUND = 100
const ERR_IO        = 101

func safe_div(a, b):
    if b == 0 do
        throw ERR_DIV_ZERO
    end
    out a / b
revert
    # error register == ERR_DIV_ZERO
    print("division error")
end.
```

**Pattern 2: Error entity + out parameter (rich errors)**

For functions that need to carry a message or context alongside the code:

```vir
entity Error:
    code: int
    message: string
end.

func parse_config(path: string):
    out result: Config;
        err: Error

    if !file_exists(path) do
        err = Error(code: ERR_NOT_FOUND, message: "file not found: $path")
        throw ERR_NOT_FOUND
    end
    # ... parse ...
end.
```

**Pattern 3: Module-level error (shared state)**

```vir
var last_error: Error

func safe_div(a, b):
    if b == 0 do
        last_error = Error(code: 1, message: "division by zero")
        throw 1
    end
    out a / b
end.
```

**Why integer only?** — Keeps `throw`/`revert` simple and zero-cost on bare-metal. The error code occupies a single register. Additional context is passed via `out` parameters or module-level variables — no heap allocation required for error handling.

| Code range | Convention |
|-----------|-----------|
| 0 | No error |
| 1–99 | Application logic errors |
| 100–199 | I/O errors |
| 200–255 | System/hardware errors |

### 13.7 try / revert — Local Error Handling with Compensation

`try:` creates a **local error boundary** inside a function body. Each `try` block has its own `revert` section for local compensation. Additional features: **timeout**, **isolate**, **resume retry**, **resume revert**, and **emit** for structured logging.

**Basic structure:**

```vir
try:
    # risky operations
revert
    # local compensation / recovery
end
```

**With `timeout` — automatic abort after duration:**

```vir
try(timeout: 5s):
    download_large_file()
revert
    emit LOG_ERROR("Download timed out or failed: $erx")
    resume revert
end
```

The `timeout` parameter is optional. If the operation exceeds the specified duration, the try block is aborted and the local `revert` runs with a timeout error code in `erx`.

**`resume retry` — restart the current try block:**

If the local `revert` determines the error is recoverable, `resume retry` restarts the `try` block from the top. Use a counter to prevent infinite loops.

**⚠ Dirty state warning:** Vir has no transactional memory. Variables modified before the `throw` inside `try:` **retain their mutated values** when `resume retry` restarts the block. The developer **must** reset any dirty state inside the local `revert` before calling `resume retry`. Failure to do so means the retry runs on corrupted/partial data.

```vir
var retry_limit = 3

try(timeout: 5s):
    connect_to_server()
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry           # restart this try block
    end
    resume revert              # give up — propagate to function revert
end
```

**Best practice — clean up before retry:**

```vir
var retry_limit = 3;
    partial_result = 0

try:
    partial_result = step_one()   # modifies partial_result
    step_two(partial_result)      # may throw
revert
    partial_result = 0            # ← MUST reset dirty state before retry
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry
    end
    resume revert
end
```

The compiler emits a **warning** if `resume retry` is used and the `revert` block does not reassign any variable that was modified inside the `try` body. This is a best-effort heuristic, not a guarantee — complex control flow may require manual auditing.

**`isolate` — automatic snapshot & restore:**

`isolate` is a `try` parameter that declares a list of external variables the compiler automatically **snapshots onto the stack** on `try` entry and **restores** before each `resume retry`. This eliminates the need to manually reset dirty state in `revert`.

```vir
try(isolate: [retry_limit, partial_result]):
    partial_result = step_one()
    step_two(partial_result)
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry       # partial_result auto-restored to its pre-try value
    end
    resume revert
end
```

Can be combined with `timeout`:

```vir
try(timeout: 5s, isolate: [retry_limit]):
    connect_to_server()
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry
    end
    resume revert
end
```

**Semantics:**
- **On `try` entry:** snapshot values of all `isolate`-listed variables are pushed to the enclosing stack frame (copy semantics; for Move types only the header/pointer is copied — heap contents are *not* rolled back).
- **On `resume retry`:** listed variables are **restored** from snapshot before the `try` body restarts. The snapshot is kept for subsequent retries.
- **On normal exit or `resume revert`:** snapshot is discarded.
- Variables **not** in the `isolate` list are unaffected — their mutations remain live.

**Compile-time dirty state detection (W302):**

If the compiler detects that a variable is:
1. Declared **outside** the `try` block
2. **Mutated** inside the `try` body (assigned, `+=`, `-=`, etc.)
3. In a block that uses `resume retry`
4. **Not** listed in `isolate`
5. And **not** reassigned in the `revert` block

→ The compiler emits a **W302 warning**:

```
Warning W302: Variable 'retry_limit' is mutated before retry.
  State may be dirty. Use isolate: [retry_limit] or reset manually in revert.
```

**`resume revert` — propagate to function-level revert:**

`resume revert` inside a local `revert` block escalates the error to the function-level `revert`. This implements the **Saga compensation pattern** — each level cleans up locally, then propagates upward.

**`emit` — structured event logging:**

`emit` sends a structured event/log. The argument is an event constructor with a message string. Events are compile-time typed; the runtime decides routing (console, file, telemetry).

```vir
emit LOG_INFO("message")
emit LOG_ERROR("error: $erx")
emit LOG_CRITICAL("system failure")
```

**Comprehensive example — leveled try blocks (Saga pattern):**

```vir
func sync_satellite_data:
    var retry_limit = 3;
        connection = none;
        data_buffer = none

    # Level 1: Connect
    try(timeout: 5s):
        emit LOG_INFO("Connecting to satellite...")
        connection = open_satellite_link()
    revert
        emit LOG_ERROR("Connection failed (error $erx)")
        retry_limit -= 1
        if retry_limit > 0 do
            resume retry
        end
        resume revert
    end

    # Level 2: Fetch data
    try(timeout: 10s):
        emit LOG_INFO("Fetching telemetry data...")
        data_buffer = fetch_telemetry(connection)
    revert
        emit LOG_ERROR("Fetch failed (error $erx)")
        close_satellite_link(connection)
        resume revert
    end

    # Level 3: Write to storage
    try:
        emit LOG_INFO("Writing data to storage...")
        write_storage(data_buffer)
    revert
        emit LOG_ERROR("Write failed (error $erx)")
        resume revert
    end

    emit LOG_INFO("Sync complete.")

revert
    emit LOG_CRITICAL("sync_satellite_data failed, rolling back...")
    rollback_all_changes()

ensure
    if connection != none do
        close_satellite_link(connection)
    end
    if data_buffer != none do
        free_buffer(data_buffer)
    end
    emit LOG_INFO("Resources released.")
end.
```

**`erx` — Error Register:**

The `erx` keyword reads the current error code (the value passed to `throw`). Available inside `revert` and `ensure` blocks (both local and function-level).

**Semantics summary:**

| Construct | Where | Behavior |
|-----------|-------|----------|
| `try: ... revert ... end` | Inside function body | Error boundary with local compensation |
| `try(timeout: T): ...` | Inside function body | Error boundary with automatic timeout |
| `try(isolate: [x, y]): ...` | Inside function body | Auto-snapshot vars on entry; restore on `resume retry` |
| `resume retry` | Inside local `revert` | Restart the current try block |
| `resume revert` | Inside local `revert` | Propagate error to function-level revert |
| `revert` | End of function | Runs only when error propagates via `resume revert` or `throw` |
| `ensure` | End of function | Always runs on function exit |
| `emit` | Anywhere | Structured event/log emission |
| `erx` | revert / ensure | Reads the thrown error code |

**Execution flow:**

| Scenario | Flow |
|----------|------|
| try succeeds | try body → code after try end → ensure → return |
| try throws + resume retry | try body → throw → local revert → resume retry → try body (restart) |
| try throws + resume retry (isolate) | try body → throw → local revert → resume retry → **restore snapshots** → try body (restart) |
| try throws + resume revert | try body → throw → local revert → resume revert → function revert → ensure → return |
| try timeout | timeout fires → local revert (erx = timeout code) |
| throw outside try | body → throw → function revert → ensure → return |

---

## 14. Parameter Blocks — in / ref / out

Vir uses **grouped parameter blocks** with the keywords `in`, `ref`, and `out` to declare function parameters. Each keyword starts a group; multiple parameters in the same group are indented below, separated by `;`. A parameter without `;` ends the group.

### 14.1 Syntax

```vir
func process_data:
    in  path: String;
        timeout: Int;
        retry: Bool          # no ';' → ends the 'in' group
    ref buffer: Array        # single param, no ';' → ends 'ref' group
    out status: Bool;
        error: String        # no ';' → ends 'out' group

    # function body here
end.
```

**Rules:**
- `in` — input parameters (read-only inside function, default)
- `ref` — reference parameters (callee can read AND write, changes affect caller)
- `out` — output parameters (callee writes, caller receives results)
- Within a group, parameters are separated by `;` — the last parameter has **no** `;` to signal end of group
- A single parameter in a group has no `;`

**Compiler safety — semicolon mismatch detection:**

Because the `;` continuation character carries semantic weight (it determines group membership), accidental insertion or deletion can silently shift parameter groups. The compiler applies these checks to catch mistakes:

| Check | Condition | Diagnostic |
|-------|-----------|------------|
| **Orphan parameter** | A bare identifier line follows a group-ending line (no `;`) but has no `in`/`ref`/`out` keyword | **Error:** "parameter `X` has no group — did you forget `;` on the previous line?" |
| **Empty group** | `in`/`ref`/`out` keyword with no parameters before next group keyword or function body | **Error:** "empty parameter group `ref`" |
| **Type mismatch hint** | A parameter is used as `ref` (address taken) but declared under `in` | **Warning:** "parameter `X` is passed by value but modified — consider `ref`" |
| **Indentation guide** | Continuation lines (after `;`) must be indented deeper than the group keyword | **Warning:** "continuation line should be indented under its group keyword" |

### 14.2 Simple Functions (no block needed)

For simple functions with only input parameters, the traditional parenthesis syntax remains valid:

```vir
func add(a, b):
    out a + b
end.

func clamp(value: int, lo: int, hi: int) -> int:
    if value < lo do out lo end
    if value > hi do out hi end
    out value
end.
```

### 14.3 Reference Parameters

```vir
func increment:
    ref x: Int

    x = x + 1
end.

func swap:
    ref a: Int;
        b: Int

    var tmp = a
    a = b
    b = tmp
end.

func main:
    var n = 10
    increment(n)
    print n              # → 11 (original was modified)

    var x = 1
    var y = 2
    swap(x, y)
    print x              # → 2
    print y              # → 1
end.
```

### 14.4 Mixed in / ref / out Example

```vir
func read_sensor:
    in  sensor_id: Int;
        channel: Int
    ref calibration: Float
    out value: Int;
        timestamp: Int

    # read from sensor, adjust calibration, write outputs
end.
```

### 14.5 Semantics

| Parameter style | Caller passes | Callee sees | Callee writes affect original? |
|----------------|---------------|-------------|-------------------------------|
| `in x` | Copy of value | Local copy | No |
| `ref x` | Address of variable | Dereferenced original | **Yes** |
| `out x` | Address of variable | Uninitialized slot | **Yes** (caller receives value) |

**Internal:** `ref` and `out` parameters emit `LoadAddr` (address of stack slot) at call site, `DerefLoad`/`DerefStore` at callee access points.

---

## 15. FFI — @bind

The `@bind(target)` attribute enables Vir to interface with external code via FFI (Foreign Function Interface). Three targets are supported: `c`, `asm`, `wasm`.

### 15.1 @bind(c) — External C Function

Declare an external C function for dynamic linking.

```vir
@bind(c)
func puts(s: ptr) -> int:
end.

@bind(c)
func malloc(size: u64) -> ptr:
end.

@bind(c)
func free(p: ptr):
end.
```

- `@bind(c)` functions have **no body** — they are external symbols
- Type annotations are **required** (the C ABI needs exact parameter sizes)
- Return type uses `-> type` after the parameter list
- Terminated with `end`

**Usage:**

```vir
func main:
    var msg = "Hello from Vir via FFI!\n"
    puts(msg)

    var buf = malloc(1024)
    # ... use buf ...
    free(buf)
end.
```

### 15.2 @bind(asm) — Inline Assembly Function

Declare a function containing target-architecture assembly.

```vir
@bind(asm)
func halt:
    # body contains assembly instructions or Vir logic
    # compiled directly to machine code
    print 0
end.
```

- `@bind(asm)` functions **have a body** — containing logic compiled directly to machine code
- Use for hot paths, trap handlers, or special CPU instructions
- The compiler does **not** optimize `@bind(asm)` function bodies — emits as-is

### 15.3 @bind(wasm) — External WebAssembly Function

Declare a function imported from the WebAssembly host environment.

```vir
@bind(wasm)
func console_log(msg: ptr):
end.

@bind(wasm)
func wasm_alloc(size: u32) -> ptr:
end.
```

- `@bind(wasm)` functions have **no body** — they are host-imported symbols
- Similar to `@bind(c)` but linked via the WASM import table
- Parameter types map to WASM value types (`i32`, `i64`, `f32`, `f64`)

### 15.4 Calling Convention

| Architecture | Parameter registers | Return register |
|-------------|-------------------|-----------------|
| ARM64 (AAPCS64) | X0–X7 | X0 |
| x86-64 (SysV) | rdi, rsi, rdx, rcx, r8, r9 | rax |
| WASM | Stack machine (no registers) | Stack top |

### 15.5 Linking

- **Mach-O (macOS):** Generates `__stubs` + `__la_symbol_ptr`, links `/usr/lib/libSystem.B.dylib`
- **ELF (Linux):** Generates `.plt` + `.got`, links via `DT_NEEDED`
- **WASM:** Generates `import` section, host provides functions at instantiation
- `@bind(c)` and `@bind(wasm)` trigger dynamic linking mode; pure Vir programs remain fully static
- `@bind(asm)` does not change linking mode — code is embedded directly

---

## 16. Register — Bit-level Hardware Struct

The `register` keyword defines a bit-mapped hardware register structure for systems programming and embedded development.

### 16.1 Single-bit Fields

```vir
register UART_SR: u32
    PE:     0          # bit 0 — Parity Error
    FE:     1          # bit 1 — Framing Error
    NF:     2          # bit 2 — Noise Flag
    ORE:    3          # bit 3 — Overrun Error
    IDLE:   4          # bit 4 — IDLE line detected
    RXNE:   5          # bit 5 — Read Data Register Not Empty
    TC:     6          # bit 6 — Transmission Complete
    TXE:    7          # bit 7 — Transmit Data Register Empty
end.
```

### 16.2 Multi-bit Fields

```vir
register GPIO_MODER: u32
    MODE0:  0..1       # bits 0-1 (2 bits)
    MODE1:  2..3       # bits 2-3
    MODE2:  4..5       # bits 4-5
end.
```

### 16.3 Usage

```vir
func uart_init:
    var sr = volatile_read(0x40011000) as UART_SR

    if sr.RXNE do # read bit 5
        var data = volatile_read(0x40011004)
    end

    sr.TXE = 1                            # set bit 7
    volatile_write(0x40011000, sr as u32)  # write back
end.
```

### 16.4 Internal Mechanism

| Operation | Generated code |
|-----------|---------------|
| **Read single bit** `reg.FIELD` | `(value >> bit_pos) & 1` |
| **Write single bit** `reg.FIELD = v` | `(value & ~(1 << bit_pos)) \| (v << bit_pos)` |
| **Read multi-bit** `reg.FIELD` | `(value >> lo) & ((1 << (hi-lo+1)) - 1)` |
| **Write multi-bit** `reg.FIELD = v` | `(value & ~(mask << lo)) \| ((v & mask) << lo)` |

On ARM64, the compiler emits native `UBFX` (extract) and `BFI` (insert) instructions.

### 16.5 Volatile Intrinsics

```vir
volatile_read(addr: ptr): int    # load with memory barrier
volatile_write(addr: ptr, val)   # store with memory barrier
```

These prevent the compiler from reordering or eliding memory accesses to hardware registers.

### 16.6 Mold — General-purpose Bit-field

While `register` is designed for hardware register mapping (volatile, memory-mapped I/O), `mold` defines **general-purpose bit-fields** for data packing — pixel formats, protocol headers, compact flags, etc.

```vir
mold Pixel: u16
    r: 5, g: 6, b: 5
end.

mold TCPFlags: u8
    FIN: 1, SYN: 1, RST: 1, PSH: 1, ACK: 1, URG: 1
end.
```

**Syntax:** `mold Name: <backing_type>` followed by comma-separated `field: width` pairs, closed by `end`.

**Usage:**

```vir
var p = Pixel(r: 31, g: 0, b: 0)    # pure red
print p.r                             # 31
p.g = 63                              # set green to max
var raw = p as u16                    # pack to u16
```

**Difference from `register`:**

| Aspect | `register` | `mold` |
|--------|-----------|--------|
| Purpose | Hardware register I/O | Data packing / bit protocol |
| Access | Via `volatile_read`/`volatile_write` | Normal variable |
| Volatile | Yes — compiler preserves all accesses | No — compiler may optimize |
| Use case | UART, GPIO, DMA | Pixel, network header, flags |
| Semantics | **Copy** | **Copy** |

**Internal mechanism:** Same bit-extraction/insertion as `register` (§16.4) — `UBFX`/`BFI` on ARM64, shift-and-mask elsewhere.

---

## 17. Compile-time Execution — precomp

The `precomp` keyword is a **modifier** that marks a declaration or expression to be evaluated during compilation. The result is inlined into the binary as a constant. Unlike a block construct, `precomp` is placed directly before the expression or function it applies to — no braces needed.

### 17.1 Compile-time Constants

```vir
const TABLE_SIZE = precomp 1 shl 16          # → 65536
const MASK       = precomp 0xFF and 0x0F      # → 0x0F
```

### 17.2 Compile-time Functions

```vir
precomp func factorial(n):
    if n <= 1 do
        out 1
    end
    out n * factorial(n - 1)
end.

const FACT_10 = precomp factorial(10)         # → 3628800

func main:
    print FACT_10             # prints 3628800 (computed at compile time)
end.
```

### 17.3 Compile-time Assertions

```vir
precomp if TABLE_SIZE > 1000000 do
    throw "TABLE_SIZE too large!"             # compile error, not runtime
end
```

### 17.4 Limitations

| Supported in precomp | Not supported |
|----------------------|---------------|
| Integer arithmetic | I/O (`print`) |
| `if`/`eif`/`else` | Arrays, entities |
| Function calls, recursion | String operations |
| `throw` (becomes compile error) | System calls |
| Comparison operators | Allocation |

---

## 18. Entry Point — @entry

By default, the compiler looks for `func main` as the program entry point. In bare-metal/kernel environments, use `@entry` to designate a custom entry.

```vir
@entry
func kmain:
    # Kernel initialization — no libc, no allocator
    # Direct hardware access only
end.
```

The `@entry` function is exported as `_start` (or a custom symbol name via linker script).

---

## 19. Arrays

### 19.1 Array Literal

```vir
var nums = [10, 20, 30, 40, 50]
print nums[0]            # → 10
print len(nums)          # → 5
```

### 19.2 Dynamic Array

```vir
var list = arr_new(64)   # create with initial capacity
push(list, 42)           # append element
push(list, 99)
print list[0]            # → 42
print len(list)          # → 2
list[0] = 100            # assign by index
```

### 19.3 Array in Loops

```vir
var sum = 0
for i in 0..len(nums):
    sum = sum + nums[i]
end
print sum                # → 150
```

### 19.4 Resize and Arena Dead Space

When a dynamic array exceeds its capacity, it allocates a new, larger block (2× growth) and copies elements over. Because Vir uses a bump allocator, the **old block becomes unreclaimable dead space** until the entire arena is freed.

**Impact:** An array that resizes repeatedly (e.g. in a loop that pushes millions of items) can consume arena memory much faster than the live data size suggests.

**Mitigation strategies:**

| Strategy | When to use |
|----------|------------|
| Pre-size with `arr_new(N)` | When the maximum size is known or estimable |
| Use `arena:` block (§4.6) | When arrays are loop-scoped — dead space is reclaimed each iteration |
| Use `arr_compact(list)` | Explicitly reclaim dead space by reallocating to exact fit |

```vir
# Pre-size to avoid resize
var data = arr_new(10000)

# Or compact after bulk inserts
for i in 0..10000:
    push(data, compute(i))
end
arr_compact(data)          # reallocate to exact length, old block becomes dead space (one-time)
```

| Function | Description |
|----------|-------------|
| `arr_new(capacity)` | Create array with pre-allocated capacity |
| `arr_compact(arr)` | Reallocate to exact-fit size (shrinks arena waste) |
| `len(arr)` | Current number of elements |
| `cap(arr)` | Current allocated capacity |

---

## 20. Dict & Map

### 20.1 Dict — Key-value Data

Dict is a key-value data structure (hash table).

#### 20.1.1 Declaration

```vir
var ages = dict[string, int]
    "Alice": 30;
    "Bob": 25
end
```

- `dict[K, V]` — `K` is the key type, `V` is the value type
- If `[K, V]` is omitted, the compiler infers types from the first element
- Built-in key types: `int`, `string`, `bool`, `ptr`
- Entity keys require a `hash` method (see §20.1.4)

#### 20.1.2 Operations

```vir
var m = dict[string, int] end      # empty dict

m["Alice"] = 30                    # set
print m["Alice"]                   # get → 30

var exists = m ? "Alice"           # existence check → true
del m["Bob"]                       # delete
print len(m)                       # element count
```

#### 20.1.3 Iteration

```vir
for k, v in ages:
    print("$k: $v")
end

for k in keys(ages):
    print k
end

for v in values(ages):
    print v
end
```

Iteration order is **not guaranteed** (hash table does not preserve insertion order).

#### 20.1.4 Hash Function

Vir uses built-in hashes for primitive types. Entity keys must define a `hash` method:

| Key type | Hash |
|----------|------|
| `int`, `i32`, `u64`, ... | Identity hash (mod bucket count) |
| `string` | FNV-1a |
| `bool` | 0 or 1 |
| Entity with `method hash -> int` | User-defined |

```vir
entity Point:
    x: int
    y: int

    method hash -> int:
        out this.x * 31 + this.y
    end.
end.

var grid = dict[Point, string]
    Point(x: 0, y: 0): "origin"
end
```

#### 20.1.5 Internals

| Property | Detail |
|----------|--------|
| **Collision** | Open addressing, linear probing |
| **Load factor** | Resize at 75% |
| **Allocation** | Arena-allocated bucket array |
| **Equality** | Primitive: value comparison. Entity: field-by-field comparison |

### 20.2 Map — Transformation Expression

`map` transforms each element of an iterable, producing a new array.

```vir
var doubled = map x in numbers:
    out x * 2
end

var names = map u in users:
    out u.name
end
```

**Syntax:**

```
map <var> in <iterable>:
    out <expression>
end
```

- `<var>` — loop variable bound to each element
- `<iterable>` — any iterable (array, range, keys/values of a dict)
- `out <expression>` — the transformed value for the output array
- Result type is `array` whose element type is inferred from `<expression>`

**With index:**

```vir
var labeled = map i, v in items:
    out "$i: $v"
end
```

**Chaining with filter:**

```vir
var evens = map x in numbers:
    if x % 2 == 0 do
        out x
    end
end
```

**Nested map:**

```vir
var flat = map row in matrix:
    out map col in row:
        out col * 2
    end
end
```

---

## 21. Case Expression

```vir
case color
    "red": print("stop")
    "green": print("go")
    "yellow": print("caution")
else
    print("unknown")
end
```

---

## 22. Async / Task

Vir supports asynchronous programming via **stackless coroutines** — each `async` function is transformed by the compiler into a state machine.

### 22.1 Async Functions

```vir
async func fetch_data(url: string):
    var conn = await connect(url)
    var data = await read(conn)
    out data
end.
```

- `async func` declares an asynchronous function
- `await` suspends the function, yielding control to the scheduler
- The compiler generates a state machine — each `await` is a suspension point

### 22.2 Task — Spawn Work

```vir
var t = task fetch_data("https://api.example.com")
# t is a handle; fetch_data has not completed yet
```

`task` creates an async task and places it on the scheduler queue. Returns a task handle.

### 22.3 Wait — Await Result

```vir
var result = wait t               # blocks until t completes
```

### 22.4 Multiple Tasks

```vir
var t1 = task fetch_data("/api/a")
var t2 = task fetch_data("/api/b")

var r1 = wait t1
var r2 = wait t2
```

Tasks run concurrently — not in parallel unless the runtime supports a thread pool.

### 22.5 Scheduler Model

| Property | Value |
|----------|-------|
| Type | Cooperative (stackless coroutine) |
| Context switch | At each `await` or `await pass` |
| Event loop | Polling-based, single-threaded by default |
| Thread pool | Optional — available for OS targets |
| Overhead | Minimal — state machine, no per-task stack allocation |

The default scheduler is a single-threaded polling loop. On OS targets, it can be extended to a thread pool. On bare-metal, the scheduler integrates into the main loop.

### 22.6 Explicit Yielding — `await pass`

In the cooperative model, a long-running synchronous loop inside an `async func` will block the scheduler. `await pass` inserts an **explicit yield point** — the current task suspends for one scheduler tick, allowing other ready tasks to run.

```vir
async func process_big_list(items: array):
    var i = 0
    loop:
        if i >= items.len do
            stop
        end
        do_heavy_work(items[i])
        i += 1
        if i mod 100 == 0 do
            await pass           # yield every 100 iterations
        end
    end
end.
```

- `await pass` is only valid inside `async func`
- Cost: one scheduler round-trip (no I/O, just yield and re-queue)
- Use it in CPU-intensive loops to prevent task starvation

### 22.7 Task Cancellation — `cancel`

`cancel` requests graceful termination of a running task. The cancelled task's next `await` (including `await pass`) raises an internal error that routes to its `revert` block.

```vir
var t = task long_running_job()

# ... later, if conditions change:
cancel t

# the task's revert block (if any) runs for cleanup
```

**Semantics:**

| Aspect | Behavior |
|--------|----------|
| Immediate? | No — cancellation is **cooperative**. Delivery happens at the next `await` |
| Task in `await` | Woken immediately with cancel error code |
| Task running (no await) | Cancel flag set; delivered at next `await` or `await pass` |
| Cancelled task's `revert` | Runs normally — `erx` contains the cancel error code |
| Cancel already-finished | No-op |
| Cancel from non-async | Allowed — `cancel` does not require `async func` |

### 22.8 Event Multiplexing — `select`

`select` waits on **multiple task handles** simultaneously and returns when the **first** one completes. The result is a `(index, value)` pair indicating which task completed.

```vir
async func race_fetch:
    var t1 = task fetch_data("/api/primary")
    var t2 = task fetch_data("/api/mirror")

    select:
        on t1 as result:
            print "Primary responded: $result"
        end
        on t2 as result:
            print "Mirror responded: $result"
            cancel t1
        end
    end
end.
```

**With timeout:**

```vir
select(timeout: 10s):
    on t1 as result:
        process(result)
    end
    on timeout:
        cancel t1
        emit LOG_ERROR("All tasks timed out")
    end
end
```

**Rules:**
- `select` is only valid inside `async func`
- Each `on <handle> as <binding>:` branch runs when that task completes first
- Only **one** branch executes — the first to complete wins
- Remaining tasks are **not** auto-cancelled — use `cancel` explicitly if needed
- `on timeout:` is the fallback if no task completes within the duration
- Nested `select` is allowed

### 22.9 Detached Task — `quiet`

`quiet` spawns a **fire-and-forget** task that is detached from the caller. The caller receives no handle — the task runs independently until completion or error. Its `revert`/`ensure` blocks execute normally; errors are logged via `emit` but do not propagate.

```vir
quiet send_analytics(event_data)
quiet flush_cache()
```

**Semantics:**

| Aspect | Behavior |
|--------|----------|
| Return value | None — `quiet` discards the result |
| Handle | None — cannot `wait`, `cancel`, or `select` a quiet task |
| Error handling | Task's own `revert`/`ensure` runs; error logged via `emit`, not propagated |
| Lifetime | Until task completes or scheduler shuts down |
| Use case | Telemetry, logging, cache warming, background cleanup |

**⚠ Warning:** Because `quiet` tasks are detached, resource leaks are possible if the task opens resources without `ensure`. Always use `ensure` blocks for cleanup in quiet tasks.

### 22.10 Limitations

- `await` / `await pass` / `select` are only valid inside `async func`
- `cancel` is cooperative — a task stuck in non-async C FFI cannot be cancelled until control returns to Vir
- For raw data buffers shared between modules without messaging overhead, use `share` variables or `ref` parameters instead of `port`

### 22.11 Port — Inter-worker Signal Coordination

See **§23 Port** for the full specification.

---

## 23. Port — Inter-worker Signal Coordination

`port` is Vir's primitive for **message-based coordination between async workers**. It is distinct from `share`/`ref`, which provide direct memory access to raw data buffers (e.g., a Framebuffer). A `port` carries **typed signals** through an internal queue; the sender does not block, and the receiver awaits the next signal.

**When to use `port` vs `share`/`ref`:**

| Scenario | Use |
|----------|---------|
| Framebuffer, audio buffer, lookup table | `share` or `deck` — direct memory, no copy |
| Gateway receiving telemetry from Satellite nodes | `port` — typed signals, queue-backed, safe across tasks |
| Passing a large array into a function for in-place work | `ref` parameter |
| Sending a command or event from producer to consumer | `port` |

### 23.1 Declaration

```vir
port signals: SatSignal          # typed signal port (MPSC — many-producer, single-consumer)
port commands: GatewayCmd        # another port on the same module
```

Ports are declared at module level with `port name: MessageType`. The declared module **owns** the port (consumer end). Any other module that imports the port can send to it.

### 23.2 Sending a Signal

```vir
send signals <- SatSignal(id: 7, lat: 21.03, lon: 105.8)
send commands <- GatewayCmd.Ping
```

`send <port> <- <value>` enqueues a message. This is **non-blocking** — the sender continues immediately.

### 23.3 Receiving a Signal

```vir
async func gateway_loop:
    loop:
        var msg = recv signals        # suspend until a message arrives
        process(msg)
    end
end.
```

`recv <port>` suspends the current `async func` until a message is available, then returns the value. It is a suspension point (like `await`).

**With timeout:**

```vir
async func gateway_loop:
    loop:
        var msg = recv(signals, timeout: 500ms)
        case msg:
            SatSignal as s: handle_signal(s)
            timeout:        emit LOG_WARN("No signal in 500 ms")
        end
    end
end.
```

### 23.4 Port with `select`

Multiple ports can be multiplexed using `select`:

```vir
async func gateway_loop:
    loop:
        select:
            on recv(signals) as s:
                process_signal(s)
            end
            on recv(commands) as cmd:
                process_command(cmd)
            end
            on timeout(1s):
                emit LOG_WARN("Idle timeout")
            end
        end
    end
end.
```

### 23.5 Exporting a Port

A module exposes its port by listing the port name in `port`:

```vir
# gateway.vri
port signals: SatSignal          # owns the consumer end
port commands: GatewayCmd
```

A satellite module sends to it:

```vir
# satellite.vri
include gateway;

func report_position(lat: f32, lon: f32):
    send gateway.signals <- SatSignal(id: NODE_ID, lat: lat, lon: lon)
end.
```

### 23.6 Semantics

| Property | Behaviour |
|----------|-----------|
| Queue model | MPSC — many producers, single consumer |
| Message ownership | **Copy** on send (Move types are moved into queue; old binding invalid) |
| Blocking | `send` never blocks; `recv` suspends until message or timeout |
| Buffer capacity | Unbounded by default; bounded variant: `port(cap: N) name: T` |
| Bounded full behaviour | Sender blocks until slot available (cooperative yield) |
| Type safety | Compile-time — type mismatch on `send` or `recv` is a type error |
| Thread safety | Safe across async tasks; not safe across OS threads without `lock` |

### 23.7 Comparison with `share` and `deck`

```vir
# Raw data path — no copy, direct memory
share framebuf: Pixel[SCREEN_W * SCREEN_H]   # modules read/write directly

# GPU shared buffer — mapped region
deck render_target: Pixel[1920 * 1080]        # CPU-GPU mapped, lock for atomic write

# Signal coordination — typed queue
port frame_done: FrameEvent                  # renderer notifies compositor
port user_input: InputEvent                  # input module notifies UI
```

---

## 24. GPU, SIMD & Atomic Primitives

Vir provides first-class keywords for SIMD vectors, GPU shared buffers, swizzle operations, and atomic memory access — enabling graphics and high-performance computing without external libraries.

### 24.1 SIMD Vector — `flux`

`flux<T, N>` declares a fixed-width SIMD vector of `N` elements of type `T`. The compiler maps operations to native SIMD instructions (ARM NEON, x86 SSE/AVX, WASM SIMD).

```vir
var pos: flux<f32, 4> = flux(1.0, 2.0, 3.0, 1.0)
var vel: flux<f32, 4> = flux(0.1, 0.0, -0.5, 0.0)

var next_pos = pos + vel          # element-wise add — single SIMD instruction
```

**Supported element types:** `f32`, `f64`, `i8`–`i64`, `u8`–`u64`
**Common widths:** 2, 4, 8, 16 (must be power of 2)

| Operation | Syntax | Generated |
|-----------|--------|-----------|
| Element-wise arithmetic | `a + b`, `a * b`, `a - b` | SIMD `FADD`/`FMUL`/`FSUB` |
| Scalar broadcast | `flux(s, s, s, s)` or `flux.splat(s)` | `DUP` / broadcast |
| Dot product | `flux.dot(a, b)` | fused multiply-add chain |
| Length / normalize | `flux.len(v)`, `flux.norm(v)` | `SQRT` + reciprocal |
| Load from memory | `flux.load(ptr)` | aligned SIMD load |
| Store to memory | `flux.store(ptr, v)` | aligned SIMD store |

**Semantics:** `flux` is a **Copy** type (fixed-size, register-width). No heap allocation.

### 24.2 Swizzle — `~`

The swizzle operator `~` reorders or replicates vector channels by name. Channel names follow the `xyzw` convention (positions) or `rgba` (colors).

```vir
var v: flux<f32, 4> = flux(1.0, 2.0, 3.0, 4.0)

var xyz  = v~xyz              # flux<f32, 3> — drop w
var zyx  = v~zyx              # flux<f32, 3> — reverse xyz
var xxxx = v~xxxx             # flux<f32, 4> — broadcast x
var rg   = v~rg               # flux<f32, 2> — synonymous with xy
```

**Rules:**
- Channel letters: `x`=0, `y`=1, `z`=2, `w`=3 (equivalently `r`, `g`, `b`, `a`)
- Result width equals the number of letters: `v~xy` → `flux<T, 2>`
- Channels may repeat: `v~xxyy` → `flux<T, 4>`
- Swizzle is compile-time — no runtime cost (maps to shuffle instruction or is folded)

**Pipeline integration:**

```vir
v~xyz |> project |> draw      # swizzle, then pipe through functions
```

### 24.3 Shared Buffer — `deck`

`deck` declares a **shared data buffer** for CPU-GPU communication or multi-stage rendering pipelines. A deck is a typed, fixed-size memory region that can be mapped for read/write by both CPU and GPU.

```vir
deck screen: Pixel[1920 * 1080]

func clear_screen:
    for i in 0..screen.len:
        screen[i] = Pixel(r: 0, g: 0, b: 0)
    end
end.
```

**Declaration:** `deck name: Type[size]`

| Property | Description |
|----------|-------------|
| Type | Any Copy type (`mold`, sized ints, `flux`) |
| Access | Indexed like array: `deck[i]` |
| Memory | Allocated in shared/mapped region (platform-dependent) |
| Lifetime | Module-level — lives for program duration |
| Semantics | **Move** (buffer handle); elements are **Copy** |
| Use case | Framebuffer, vertex buffer, compute staging area |

**Atomic write to deck — see §24.4.**

### 24.4 Atomic — `lock` / `!!`

`lock` provides **atomic read-modify-write** access to a memory location. This prevents data races when multiple tasks or hardware units access the same address.

**Prefix form — `lock`:**

```vir
lock screen[coord] = p           # atomic store
lock counter += 1                 # atomic increment
var val = lock shared_flag        # atomic load
```

**Postfix form — `!!`:**

```vir
screen[coord]!! = p              # atomic store
counter!! += 1                    # atomic increment
var val = shared_flag!!           # atomic load
```

Both forms are equivalent. `lock` reads left-to-right ("lock this, then operate"). `!!` reads right-to-left as a postfix warning ("this is sensitive!").

**Semantics:**

| Operation | `lock` form | `!!` form | Generated |
|-----------|------------|-----------|-----------|
| Atomic store | `lock x = v` | `x!! = v` | `STLR` (ARM64) / `XCHG` (x86) |
| Atomic load | `var v = lock x` | `var v = x!!` | `LDAR` (ARM64) / `MOV` + fence (x86) |
| Atomic RMW | `lock x += 1` | `x!! += 1` | `LDAXR`/`STLXR` loop (ARM64) / `LOCK ADD` (x86) |
| Compare-and-swap | `lock.cas(x, old, new)` | — | `CAS` / `CMPXCHG` |

**Memory ordering:** All `lock`/`!!` operations use **sequentially consistent** ordering by default. For relaxed ordering in performance-critical paths, use intrinsics `__atomic_load_relaxed` / `__atomic_store_relaxed`.

**⚠ Warning:** `lock`/`!!` protects a **single operation**. For multi-step critical sections, combine with `try`/`revert` or a mutex protocol.

### 24.5 Combined Example

```vir
mold Pixel: u16
    r: 5, g: 6, b: 5
end.

deck screen: Pixel[1920 * 1080]

func render:
    var p = Pixel(r: 31, g: 0, b: 0)
    var v: flux<f32, 4> = get_pos()

    # Swizzle + pipeline
    v~xyz |> project |> draw

    # Atomic write to shared buffer
    lock screen[coord] = p
end.
```

---

## 24. System Intrinsics

Vir provides low-level intrinsics for systems programming (available without `@bind(c)`):

| Intrinsic | Description |
|-----------|-------------|
| `__syscall(num, a0, a1, a2)` | Raw system call |
| `__memcpy(dst, src, n)` | Memory copy |
| `__memset(dst, val, n)` | Memory fill |
| `__clz(x)` | Count leading zeros |
| `__ctz(x)` | Count trailing zeros |
| `__popcnt(x)` | Population count |
| `__bswap(x)` | Byte swap |
| `__neg(x)` | Negate |
| `__not(x)` | Bitwise NOT |
| `__fence()` | Memory fence (barrier) |
| `__trap()` | Trigger hardware trap |
| `volatile_read(addr)` | Volatile load + barrier |
| `volatile_write(addr, val)` | Volatile store + barrier |

---

## 25. Multilingual Support

Vir supports programming in multiple natural languages through the SubLib adapter system:

| Language | `if` | `func` | `out` | `eif` |
|----------|------|--------|-------|-------|
| English | `if` | `func` | `out` | `eif` |
| Vietnamese | `nếu` | `hàm` | `trả về` | `còn nếu` |
| Chinese | `如果` | `函数` | `返回` | `否则如果` |
| Japanese | `もし` | `関数` | `返す` | `それ以外もし` |
| Korean | `만약` | `함수` | `반환` | `아니면 만약` |

All natural language phrases are mapped through the KeywordRegistry to canonical token values.

---

## 26. Keyword Reference

### Core

| Keyword | Purpose |
|---------|---------|
| `func` | Define a function |
| `end` | Close any block |
| `out` | Return a value from function |
| `var` | Mutable variable declaration |
| `let` | Immutable variable binding |
| `const` | Compile-time constant |
| `arena` | Sub-arena block — scoped memory region (§4.6) |

### Control Flow

| Keyword | Purpose |
|---------|---------|
| `if` | Conditional branch |
| `eif` | Else-if branch |
| `else` | Default branch |
| `when ... loop` | While loop |
| `for ... in` | Range-based for loop |
| `loop` | Infinite or counted loop |
| `break` | Exit loop |
| `skip` | Continue to next iteration |
| `case` | Switch/match expression |

### Data Types

| Keyword | Purpose |
|---------|---------|
| `entity` | Define a struct-like type |
| `packed` | Modifier for contiguous-layout entity |
| `enum` | Define named integer constants |
| `register` | Define bit-mapped hardware register |
| `mold` | Define general-purpose bit-field (data packing) |
| `method` | Define a function bound to an entity |
| `dict` | Declare key-value dictionary |
| `map` | Transformation expression (functional map) |

### Hardware & SIMD

| Keyword / Operator | Purpose |
|-------------------|---------|
| `mold` | Declare general-purpose bit-field — compact data packing, not hardware-volatile (§16.6) |
| `flux<T, N>` | SIMD vector type — N elements of type T; maps to ARM NEON / x86 SSE-AVX / WASM SIMD (§24.1) |
| `deck` | Shared buffer — typed, fixed-size region for CPU-GPU or multi-stage pipelines (§24.3) |
| `~` | Swizzle postfix — reorder or replicate `flux` channels: `v~xyz`, `v~rgba` (§24.2) |
| `lock` | Atomic read-modify-write prefix — sequentially consistent (§24.4) |
| `!!` | Atomic postfix — equivalent to `lock`; marks a location as sensitive (§24.4) |

### Module System

| Keyword | Purpose |
|---------|---------|
| `include` | Load a file and create namespace |
| `import` | Bring a function into local scope |
| `get` | Bring a variable/constant into local scope |
| `from` | Specify source module |
| `as` | Alias for namespace, import, or type cast |
| `export` | Export functions to other modules |
| `share` | Share module-level state |

### Ownership & Borrowing

| Keyword / Syntax | Purpose |
|---------|----------|
| `&expr` | Shared borrow — read-only reference, non-consuming |
| `&mut expr` | Mutable borrow — exclusive write reference |
| `let` | Immutable binding; move semantics for non-copy types |
| `var` | Mutable binding; move semantics for non-copy types |

> Copy types (`int`, `float`, `bool`, sized integers) are implicitly copied on assignment. Move types (`string`, `array`, `entity`, `dict`) transfer ownership — borrow with `&` to avoid moving.

### Error Handling

| Keyword | Purpose |
|---------|---------|
| `throw` | Raise an error (abort normal flow) |
| `ensure` | Scope guard — always runs on function exit |
| `revert` | Scope guard — runs only on error/throw (function-level and local try-level) |
| `try` | Open local error boundary block |
| `erx` | Read the thrown error code (error register) |
| `emit` | Structured event/log emission |
| `timeout` | Parameter for `try` — automatic abort after duration |
| `isolate` | Parameter for `try` — declare variables for auto-snapshot & restore on retry |
| `resume retry` | Inside local `revert` — restart current try block |
| `resume revert` | Inside local `revert` — propagate to function-level revert |

### Parameters

| Keyword | Purpose |
|---------|---------|
| `in` | Input parameter group (read-only, default) |
| `ref` | Reference parameter group (read-write, affects caller) |
| `out` | Output parameter group (callee writes, caller receives) |
| `this` | Implicit self in entity methods; UFCS convention for first param |

### FFI & System

| Keyword | Purpose |
|---------|---------|
| `@bind(c)` | Declare external C function |
| `@bind(asm)` | Inline assembly function |
| `@bind(wasm)` | Declare external WASM function |
| `@entry` | Mark kernel/bare-metal entry point |
| `ptr` | Raw pointer type |
| `precomp` | Compile-time evaluation modifier (keyword, not block) |

### Async

| Keyword | Purpose |
|---------|---------|
| `async` | Declare async function |
| `await` | Suspend function and wait for async operation to complete |
| `await pass` | Explicit yield — suspend for one scheduler tick to prevent CPU hogging (§22.6) |
| `task` | Spawn async task; returns a task handle |
| `wait` | Await task completion — block caller until task finishes |
| `cancel` | Request cooperative cancellation of a running task (§22.7) |
| `select` | Event multiplexing — wait on first-completed among multiple tasks (§22.8) |
| `quiet` | Spawn detached fire-and-forget task — no handle, no error propagation (§22.9) |
| `port` | Declare a typed MPSC signal port for inter-worker coordination (§23) |
| `send` | Enqueue a message to a port: `send port <- value` (non-blocking) (§23.2) |
| `recv` | Dequeue from a port: suspends until message arrives or timeout (§23.3) |

### Other

| Keyword | Purpose |
|---------|---------|
| `has` | Forward declaration |
| `none` | Null value |
| `true` / `false` | Boolean literals |
| `mod` | Modulo operator |
| `xor` / `shl` / `shr` | Bitwise operators |
| `and` / `or` | Bitwise AND / OR |

---

## 27. Operator Precedence Table

From highest to lowest:

| Precedence | Operators | Associativity |
|-----------|-----------|---------------|
| 40 | `.` `?.` | Left |
| 39 | `~` (swizzle postfix) | Left |
| 38 | `!!` (atomic postfix) | Left |
| 28 | `!` `-` (unary) | Right |
| 30 | `^` | Right |
| 20 | `*` `/` | Left |
| 18 | `%` `mod` | Left |
| 12 | `>>` `shl` `shr` `as` | Left |
| 10 | `+` `-` | Left |
| 8 | `:~` | Left |
| 6 | `>` `<` `>=` `<=` | Left |
| 5 | `==` `!=` `?=` `?=/=` | Left |
| 3 | `&` `and` | Left |
| 2 | `\|\|` `or` `xor` | Left |
| 1 | `=` | Right |

---

## 28. Changes from v1.2

| Feature | v1.2 | v2.0 |
|---------|------|------|
| UFCS | — | `x.func()` ≡ `func(x)` with `this` keyword |
| Entity method | — | `method` keyword inside entity for bound functions |
| Packed entity | — | `packed entity` with contiguous layout |
| String interpolation | — | `"Hello $name"`, `"$(expr)"`, `"$$"` |
| throw | — | `throw <expr>` with error codes |
| ensure | — | `ensure` scope guard (always runs) |
| revert | — | `revert` scope guard (on error only) |
| ref parameters | — | `in`/`ref`/`out` grouped parameter blocks |
| FFI | — | `@bind(c)` for C interop, `@bind(asm)` for assembly, `@bind(wasm)` for WASM |
| Register | — | `register Name: u32 ... end` for bit fields |
| precomp | — | `precomp` keyword modifier for compile-time evaluation |
| @entry | — | Custom bare-metal entry point |
| try / revert | — | `try: ... revert ... end` local error boundary with Saga compensation |
| emit | — | `emit LOG_INFO(...)` structured event/log emission |
| timeout | — | `try(timeout: 5s):` automatic abort after duration |
| resume | — | `resume retry` / `resume revert` — flow control inside local revert |
| erx | — | Error register — reads thrown error code |
| Return type arrow | `func f(): int` | `func f() -> int:` |
| dict (was map) | `map[K,V]` | `dict[K,V]` — key-value dictionary |
| Map expression | — | `map x in list: out expr end` — transformation |
| Sized types | `int`, `float`, `string`, `bool` | + `i8`–`i64`, `u8`–`u64`, `ptr` |
| Include paths | `include math;` | + `include net.http;` (dot-path directory mapping) |
| Include alias | — | `include net.http as web;` |
| Import alias | — | `import get from net.http as fetch;` |
| Get | — | `get PI from math;` (import variable/constant) |
| Borrow checker | — | Compile-time ownership, borrow, move safety — zero runtime overhead (§4.8) |
| `&` / `&mut` | — | Shared / mutable borrow syntax — no move, validated by borrow checker |
| Move semantics | — | Non-copy types move on assignment; old binding invalidated (§4.8) |
| arena block | — | `arena: ... end` scoped sub-arena for loop memory reclamation (§4.6) |
| arr_compact | — | `arr_compact(arr)` — reclaim array resize dead space (§19.4) |
| Callable field | — | UFCS step 2: `x.callback()` calls function-pointer field (§11) |
| Interpolation boundary | — | `$ident` stops at non-identifier chars; use `$(expr)` for `[]` access (§12.6) |
| Semicolon safety | — | Compiler detects orphan parameters from missing/extra `;` (§14.1) |
| isolate | — | `try(isolate: [x, y]):` auto-snapshot & restore on retry; W302 warning for unprotected mutations (§13.7) |
| resume retry safety | — | Compiler emits W302 if variable mutated in try body, block uses `resume retry`, and variable not in `isolate` list or reset in `revert` (§13.7) |
| `await pass` | — | Explicit yield point — prevents CPU hogging in cooperative async loops (§22.6) |
| `cancel` | — | Cooperative task cancellation — delivered at next `await` (§22.7) |
| `select` | — | Event multiplexing — `select: on t1 as r: ... end` races multiple tasks (§22.8) |
| `quiet` | — | Detached fire-and-forget task — no handle, errors logged not propagated (§22.9) |
| `mold` | `register` (data packing use) | `mold Name: u16 r:5, g:6, b:5 end` — general-purpose bit-field (§16.6) |
| `flux` | — | `flux<T, N>` — SIMD vector type, mapped to NEON/SSE-AVX/WASM SIMD (§24.1) |
| Swizzle `~` | — | `v~xyz` — postfix channel reorder/replicate for `flux` (§24.2) |
| `deck` | — | `deck name: Type[size]` — shared CPU-GPU buffer (§24.3) |
| `lock` / `!!` | — | Atomic read-modify-write: `lock x += 1` or `x!! += 1` (§24.4) |
| `port` | — | `port name: T` — typed MPSC signal port for inter-worker coordination (§23) |
| `send` / `recv` | — | `send port <- v` (non-blocking); `recv port` (async-suspending) (§23.2–23.3) |

---

*Vir Language Specification v2.0 — Systems programming language with zero-dependency native compilation.*
*Targets: ARM64 (Mach-O), x86-64 (ELF), WebAssembly.*
*Self-hosting compiler: virc.vri (written entirely in Vir).*
