# VIR IR Lowering Specification — AST → Q-IR Translation

> **Mục đích:** Tài liệu hóa cách mỗi AST node được dịch sang Q-IR instructions
> **Ngày tạo:** 22/03/2026
> **Phiên bản:** 1.0 — Stage 4 Preparation
> **Source:** `core/src/ir_lower.c`, `core/src/parser.c`

---

## Mục lục

1. [Overview](#1-overview)
2. [Literals](#2-literals)
3. [Declarations](#3-declarations)
4. [Expressions](#4-expressions)
5. [Control Flow](#5-control-flow)
6. [Functions](#6-functions)
7. [Entities & Types](#7-entities--types)
8. [Error Handling](#8-error-handling)
9. [Async/Tasks](#9-asynctasks)
10. [Modules & Imports](#10-modules--imports)

---

## 1. Overview

### Lowering Pipeline

```
Source Code (.vri)
       │
       ▼
┌──────────────────┐
│     Lexer        │  → Tokens
└──────────────────┘
       │
       ▼
┌──────────────────┐
│     Parser       │  → AST (Abstract Syntax Tree)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│   IR Lowering    │  → Q-IR (Quadruple IR)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│    Codegen       │  → Native Code (x86_64/ARM64)
└──────────────────┘
```

### AST Node Structure

```c
typedef struct AST_Node {
    AST_Type type;           // Node type (AST_BINOP, AST_IF, etc.)
    SourceLoc loc;           // Source location
    union {
        // Literal data
        int64_t int_val;
        double float_val;
        char* str_val;
        
        // Structural data
        struct { AST_Node* left; AST_Node* right; Op op; } binop;
        struct { AST_Node* cond; AST_Node* then_; AST_Node* else_; } if_stmt;
        // ... more variants
    } data;
} AST_Node;
```

---

## 2. Literals

### AST_LITERAL_INT
**Description:** Integer literal (123, -42, 0xFF)

| Input | Output Q-IR |
|-------|-------------|
| `42` | `Q_LOAD dest, #42` |

**Lowering:**
```c
case AST_LITERAL_INT:
    emit(Q_LOAD, alloc_vreg(), node->data.int_val);
    return vreg;
```

---

### AST_LITERAL_FLOAT
**Description:** Float literal (3.14, 2.5e-10)

| Input | Output Q-IR |
|-------|-------------|
| `3.14` | `Q_LOAD dest, const_pool[3.14]` |

**Lowering:**
```c
case AST_LITERAL_FLOAT:
    int idx = add_const_pool(node->data.float_val);
    emit(Q_LOAD, alloc_vreg(), CONST_REF(idx));
    return vreg;
```

---

### AST_LITERAL_STRING
**Description:** String literal ("hello", "unicode: ñ")

| Input | Output Q-IR |
|-------|-------------|
| `"hello"` | `Q_STR_ALLOC dest, 5` + `Q_MEM_STORE dest[0], 'h'` ... |

**Lowering (interned):**
```c
case AST_LITERAL_STRING:
    int str_idx = intern_string(node->data.str_val);
    emit(Q_LOAD, alloc_vreg(), STR_REF(str_idx));
    return vreg;
```

---

### AST_LITERAL_BOOL
**Description:** Boolean literal (true, false)

| Input | Output Q-IR |
|-------|-------------|
| `true` | `Q_LOAD dest, #1` |
| `false` | `Q_LOAD dest, #0` |

---

### AST_LITERAL_NULL
**Description:** Null literal

| Input | Output Q-IR |
|-------|-------------|
| `null` | `Q_LOAD dest, #0` |

---

## 3. Declarations

### AST_VAR_DECL
**Description:** Variable declaration

```vir
let x = 42
let y: Int = 100
```

| Input | Output Q-IR |
|-------|-------------|
| `let x = 42` | `Q_LOAD t1, #42` + `Q_MOVE x, t1` |
| `let x: Int` | `Q_LOAD x, #0` (default init) |

**Lowering:**
```c
case AST_VAR_DECL:
    vreg x = allocate_local(node->data.var_decl.name);
    if (node->data.var_decl.init) {
        vreg init_val = lower(node->data.var_decl.init);
        emit(Q_MOVE, x, init_val);
    } else {
        emit(Q_LOAD, x, default_for_type(node->data.var_decl.type));
    }
```

---

### AST_CONST_DECL
**Description:** Constant declaration (immutable)

```vir
const PI = 3.14159
```

| Input | Output Q-IR |
|-------|-------------|
| `const PI = 3.14` | `Q_LOAD PI, const_pool[3.14]` |

**Notes:** Constants are marked immutable in symbol table, emit error on reassignment.

---

### AST_ASSIGN
**Description:** Assignment statement

```vir
x = 42
arr[i] = value
entity.field = value
```

| Input | Output Q-IR |
|-------|-------------|
| `x = 42` | `Q_LOAD t1, #42` + `Q_MOVE x, t1` |
| `arr[i] = v` | `Q_ARR_SET arr, i, v` |
| `e.f = v` | `Q_SET_FIELD e, f_idx, v` |

---

## 4. Expressions

### AST_BINOP
**Description:** Binary operations (+, -, *, /, %, etc.)

| Operator | AST | Q-IR |
|----------|-----|------|
| `+` | `BINOP_ADD` | `Q_ADD dest, lhs, rhs` |
| `-` | `BINOP_SUB` | `Q_SUB dest, lhs, rhs` |
| `*` | `BINOP_MUL` | `Q_MUL dest, lhs, rhs` |
| `/` | `BINOP_DIV` | `Q_DIV dest, lhs, rhs` |
| `%` | `BINOP_MOD` | `Q_MOD dest, lhs, rhs` |
| `&` | `BINOP_AND` | `Q_AND dest, lhs, rhs` |
| `\|` | `BINOP_OR` | `Q_OR dest, lhs, rhs` |
| `^` | `BINOP_XOR` | `Q_XOR dest, lhs, rhs` |
| `<<` | `BINOP_SHL` | `Q_SHL dest, lhs, rhs` |
| `>>` | `BINOP_SHR` | `Q_SHR dest, lhs, rhs` |

**Float variant detection:**
```c
case AST_BINOP:
    vreg lhs = lower(node->data.binop.left);
    vreg rhs = lower(node->data.binop.right);
    
    if (is_float_type(get_type(lhs)) || is_float_type(get_type(rhs))) {
        // Use float opcodes
        switch (node->data.binop.op) {
            case BINOP_ADD: emit(Q_FADD, dest, lhs, rhs); break;
            case BINOP_SUB: emit(Q_FSUB, dest, lhs, rhs); break;
            // ...
        }
    } else {
        // Use integer opcodes
        switch (node->data.binop.op) {
            case BINOP_ADD: emit(Q_ADD, dest, lhs, rhs); break;
            // ...
        }
    }
```

---

### AST_COMPARE
**Description:** Comparison operations (==, !=, <, >, <=, >=)

| Operator | Q-IR |
|----------|------|
| `==` | `Q_CMP_EQ dest, lhs, rhs` |
| `!=` | `Q_CMP_NE dest, lhs, rhs` |
| `<` | `Q_CMP_LT dest, lhs, rhs` |
| `>` | `Q_CMP_GT dest, lhs, rhs` |
| `<=` | `Q_CMP_LE dest, lhs, rhs` |
| `>=` | `Q_CMP_GE dest, lhs, rhs` |

---

### AST_UNARY
**Description:** Unary operations (-, !, ~)

| Operator | Q-IR |
|----------|------|
| `-x` | `Q_NEG dest, x` |
| `!x` | `Q_CMP_EQ dest, x, #0` (logical not) |
| `~x` | `Q_NOT dest, x` |

---

### AST_CALL
**Description:** Function call

```vir
foo(a, b, c)
obj.method(arg)
```

**Lowering:**
```c
case AST_CALL:
    // Evaluate arguments left-to-right
    for (int i = 0; i < arg_count; i++) {
        vreg arg_val = lower(args[i]);
        emit(Q_MOVE, ARG_REG(i), arg_val);
    }
    
    // Emit call
    if (is_direct_call(node)) {
        emit(Q_CALL, func_addr, arg_count);
    } else {
        emit(Q_CALL_FUNC, func_idx, arg_count);
    }
    
    // Get return value
    emit(Q_MOVE, dest, RET_REG);
```

---

### AST_INDEX_ACCESS
**Description:** Array/map indexing

```vir
arr[0]
map["key"]
```

| Input | Output Q-IR |
|-------|-------------|
| `arr[i]` | `Q_ARR_GET dest, arr, i` |
| `map[k]` | `Q_MAP_GET dest, map, k` |

---

### AST_FIELD_ACCESS
**Description:** Field access on entities

```vir
person.name
point.x
```

| Input | Output Q-IR |
|-------|-------------|
| `e.f` | `Q_GET_FIELD dest, e, f_idx` |

---

### AST_SAFE_ACCESS ⚠️ SPECIAL
**Description:** Null-safe field access (`?.`)

```vir
person?.address?.city
```

**Lowering expansion:**
```c
case AST_SAFE_ACCESS:
    // person?.address?.city becomes:
    //   if person == null: return null
    //   t1 = person.address
    //   if t1 == null: return null
    //   return t1.city
    
    vreg obj = lower(node->data.safe_access.obj);
    int null_label = alloc_label();
    int end_label = alloc_label();
    
    // Null check
    emit(Q_CMP_EQ, t1, obj, NULL_VAL);
    emit(Q_JUMP_IF, t1, null_label);
    
    // Access field
    vreg field = emit(Q_GET_FIELD, obj, field_idx);
    emit(Q_MOVE, dest, field);
    emit(Q_JUMP, end_label);
    
    // Null path
    emit(Q_LABEL, null_label);
    emit(Q_LOAD, dest, NULL_VAL);
    
    emit(Q_LABEL, end_label);
```

**Critical Test Case:**
```vir
entity User { name: String, profile: Profile? }
entity Profile { bio: String }

fn test_safe_access(u: User?) -> String? {
    return u?.profile?.bio  // Must NOT crash if u or profile is null
}
```

---

## 5. Control Flow

### AST_IF
**Description:** Conditional statement

```vir
if condition {
    // then
} else {
    // else
}
```

**Lowering:**
```c
case AST_IF:
    vreg cond = lower(node->data.if_stmt.cond);
    int else_label = alloc_label();
    int end_label = alloc_label();
    
    emit(Q_JUMP_IF_NOT, cond, else_label);
    lower(node->data.if_stmt.then_);
    emit(Q_JUMP, end_label);
    
    emit(Q_LABEL, else_label);
    if (node->data.if_stmt.else_) {
        lower(node->data.if_stmt.else_);
    }
    
    emit(Q_LABEL, end_label);
```

---

### AST_WHILE
**Description:** While loop

```vir
while condition {
    // body
}
```

**Lowering:**
```c
case AST_WHILE:
    int loop_start = alloc_label();
    int loop_end = alloc_label();
    
    push_loop_context(loop_start, loop_end);  // For break/continue
    
    emit(Q_LABEL, loop_start);
    vreg cond = lower(node->data.while_stmt.cond);
    emit(Q_JUMP_IF_NOT, cond, loop_end);
    
    lower(node->data.while_stmt.body);
    emit(Q_JUMP, loop_start);
    
    emit(Q_LABEL, loop_end);
    pop_loop_context();
```

---

### AST_FOR_RANGE
**Description:** Range-based for loop

```vir
for i in 0..10 {
    print(i)
}
```

**Lowering:**
```c
case AST_FOR_RANGE:
    vreg i = allocate_local("i");
    vreg end_val = lower(node->data.for_range.end);
    
    int loop_start = alloc_label();
    int loop_end = alloc_label();
    
    // Initialize
    emit(Q_LOAD, i, lower(node->data.for_range.start));
    
    emit(Q_LABEL, loop_start);
    // Check condition
    emit(Q_CMP_LT, t1, i, end_val);
    emit(Q_JUMP_IF_NOT, t1, loop_end);
    
    // Body
    lower(node->data.for_range.body);
    
    // Increment
    emit(Q_ADD, i, i, #1);
    emit(Q_JUMP, loop_start);
    
    emit(Q_LABEL, loop_end);
```

---

### AST_LOOP
**Description:** Infinite loop (break to exit)

```vir
loop {
    if done { break }
}
```

**Lowering:**
```c
case AST_LOOP:
    int loop_start = alloc_label();
    int loop_end = alloc_label();
    
    push_loop_context(loop_start, loop_end);
    
    emit(Q_LABEL, loop_start);
    lower(node->data.loop.body);
    emit(Q_JUMP, loop_start);
    
    emit(Q_LABEL, loop_end);
    pop_loop_context();
```

---

### AST_BREAK
**Description:** Break from loop

| Input | Output Q-IR |
|-------|-------------|
| `break` | `Q_JUMP loop_end_label` |

---

### AST_CONTINUE
**Description:** Continue to next iteration

| Input | Output Q-IR |
|-------|-------------|
| `continue` | `Q_JUMP loop_start_label` |

---

### AST_PATTERN_MATCH
**Description:** Pattern matching (match/case)

```vir
match value {
    case 1 -> "one"
    case 2 -> "two"
    case _ -> "other"
}
```

**Lowering:**
```c
case AST_PATTERN_MATCH:
    vreg scrutinee = lower(node->data.match.value);
    int end_label = alloc_label();
    
    for each (case in cases) {
        int next_case = alloc_label();
        
        // Check pattern
        vreg pattern_matches = emit_pattern_check(scrutinee, case.pattern);
        emit(Q_JUMP_IF_NOT, pattern_matches, next_case);
        
        // Execute arm
        lower(case.body);
        emit(Q_JUMP, end_label);
        
        emit(Q_LABEL, next_case);
    }
    
    // Default case or error
    emit(Q_LABEL, end_label);
```

---

## 6. Functions

### AST_FUNC_DEF
**Description:** Function definition

```vir
fn add(a: Int, b: Int) -> Int {
    return a + b
}
```

**Lowering:**
```c
case AST_FUNC_DEF:
    // Create function entry in function table
    int func_idx = alloc_function(node->data.func.name);
    
    // Prologue
    emit(Q_LABEL, func_idx);
    
    // Bind parameters
    for (int i = 0; i < param_count; i++) {
        vreg param = allocate_local(params[i].name);
        emit(Q_GET_ARG, param, i);
    }
    
    // Body
    lower(node->data.func.body);
    
    // Epilogue (implicit return if not explicit)
    emit(Q_LOAD, RET_REG, #0);
    emit(Q_RET);
```

---

### AST_RETURN
**Description:** Return statement

```vir
return value
```

| Input | Output Q-IR |
|-------|-------------|
| `return x` | `Q_MOVE ret_reg, x` + `Q_RET` |
| `return` | `Q_RET` |

---

### AST_BUILTIN_CALL
**Description:** Built-in function calls (len, type, etc.)

| Builtin | Q-IR |
|---------|------|
| `len(arr)` | `Q_ARR_LEN dest, arr` |
| `len(str)` | `Q_STR_LEN dest, str` |
| `len(map)` | `Q_MAP_LEN dest, map` |
| `sin(x)` | `Q_SIN dest, x` |
| `cos(x)` | `Q_COS dest, x` |
| `sqrt(x)` | `Q_SQRT dest, x` |
| `abs(x)` | `Q_ABS dest, x` |

---

## 7. Entities & Types

### AST_CLASS_DEF / AST_RECORD_DEF
**Description:** Entity/struct definition

```vir
entity Point {
    x: Float
    y: Float
    
    fn distance() -> Float {
        return sqrt(self.x * self.x + self.y * self.y)
    }
}
```

**Lowering:**
```c
case AST_CLASS_DEF:
    // Register type
    int type_idx = register_type(node->data.class.name);
    
    // Calculate field layout
    for each (field in fields) {
        add_field(type_idx, field.name, field.type, offset);
        offset += sizeof_type(field.type);
    }
    
    // Lower methods
    for each (method in methods) {
        lower_method(type_idx, method);
    }
```

---

### AST_ENTITY_NEW
**Description:** Entity instantiation

```vir
let p = Point { x: 1.0, y: 2.0 }
```

**Lowering:**
```c
case AST_ENTITY_NEW:
    int type_idx = lookup_type(node->data.entity_new.type_name);
    int field_count = get_field_count(type_idx);
    
    emit(Q_ENTITY_NEW, dest, type_idx, field_count);
    
    // Initialize fields
    for each (init in initializers) {
        vreg val = lower(init.value);
        int field_idx = lookup_field(type_idx, init.name);
        emit(Q_SET_FIELD, dest, field_idx, val);
    }
```

---

### AST_ENUM_DEF
**Description:** Enumeration definition

```vir
enum Color {
    Red,
    Green,
    Blue
}
```

**Lowering:**
```c
case AST_ENUM_DEF:
    // Each variant gets an integer tag
    for (int i = 0; i < variant_count; i++) {
        register_const(enum_name ++ "." ++ variant[i].name, i);
    }
```

---

### AST_ENUM_ACCESS
**Description:** Enum variant access

```vir
let c = Color.Red
```

| Input | Output Q-IR |
|-------|-------------|
| `Color.Red` | `Q_LOAD dest, #0` (variant index) |

---

## 8. Error Handling

### AST_TRY_ERROR ⚠️ SPECIAL
**Description:** Try-catch error handling

```vir
try {
    risky_operation()
} catch e {
    handle_error(e)
}
```

**Lowering:**
```c
case AST_TRY_ERROR:
    int handler_label = alloc_label();
    int end_label = alloc_label();
    
    // Register exception handler
    emit(Q_TRY_START, handler_label);
    
    // Try block
    lower(node->data.try_error.try_block);
    
    emit(Q_TRY_END);
    emit(Q_JUMP, end_label);
    
    // Handler block
    emit(Q_LABEL, handler_label);
    vreg error_var = allocate_local(node->data.try_error.error_var);
    emit(Q_MOVE, error_var, EXCEPTION_REG);
    lower(node->data.try_error.catch_block);
    
    emit(Q_LABEL, end_label);
```

**Exception propagation:**
```c
// When Q_THROW is emitted:
emit(Q_THROW, error_value);
// This unwinds the stack to the nearest Q_TRY_START handler
```

---

## 9. Async/Tasks

### AST_ASYNC_FUNC ⚠️ SPECIAL
**Description:** Async function definition

```vir
async fn fetch_data(url: String) -> String {
    let response = await http_get(url)
    return response.body
}
```

**Lowering (coroutine transformation):**
```c
case AST_ASYNC_FUNC:
    // Transform async function into state machine
    // Each 'await' point becomes a yield/resume state
    
    int state_idx = 0;
    for each (await_point in find_awaits(body)) {
        mark_state(await_point, state_idx++);
    }
    
    // Generate state machine dispatcher
    emit(Q_LABEL, func_entry);
    emit(Q_LOAD, t1, STATE_FIELD);
    
    for (int i = 0; i < state_count; i++) {
        emit(Q_CMP_EQ, t2, t1, #i);
        emit(Q_JUMP_IF, t2, state_labels[i]);
    }
```

---

### AST_TASK
**Description:** Task spawning

```vir
task my_task {
    // concurrent work
}
```

| Input | Output Q-IR |
|-------|-------------|
| `task { body }` | `Q_TASK_SPAWN dest, closure_ptr, args` |

---

## 10. Modules & Imports

### AST_IMPORT
**Description:** Module import

```vir
import "std/io"
import { read, write } from "std/fs"
```

**Lowering:**
```c
case AST_IMPORT:
    // Resolved at compile time, no runtime code
    // Symbols from module are added to current scope
    Module* mod = load_module(node->data.import.path);
    for each (symbol in mod->exports) {
        add_to_scope(current_scope, symbol);
    }
```

---

### AST_EXPORT
**Description:** Export declaration

```vir
export fn public_api() { }
```

**Lowering:**
```c
case AST_EXPORT:
    // Mark symbol as exported in module table
    lower(node->data.export.decl);
    mark_exported(get_symbol_name(node->data.export.decl));
```

---

## Special Cases & Edge Cases

### 1. Array Literals
```vir
let arr = [1, 2, 3]
```

**Lowering:**
```c
emit(Q_ARR_NEW, arr);
for (int i = 0; i < elements.length; i++) {
    vreg elem = lower(elements[i]);
    emit(Q_ARR_PUSH, arr, elem);
}
```

### 2. Map Literals
```vir
let map = {"a": 1, "b": 2}
```

**Lowering:**
```c
emit(Q_MAP_NEW, map);
for each (kv in pairs) {
    vreg k = lower(kv.key);
    vreg v = lower(kv.value);
    emit(Q_MAP_SET, map, k, v);
}
```

### 3. String Interpolation
```vir
let msg = "Hello, ${name}!"
```

**Lowering:**
```c
// "Hello, ${name}!" → "Hello, " + str(name) + "!"
emit(Q_STR_CAT, t1, "Hello, ", name_str);
emit(Q_STR_CAT, dest, t1, "!");
```

### 4. Method Calls on Primitives
```vir
let upper = "hello".upper()
```

**Lowering:**
```c
emit(Q_STR_UPPER, dest, "hello");
```

---

## Summary: AST → Q-IR Quick Reference

| AST Node | Primary Q-IR |
|----------|--------------|
| `AST_LITERAL_INT` | `Q_LOAD` |
| `AST_LITERAL_FLOAT` | `Q_LOAD` (const pool) |
| `AST_LITERAL_STRING` | `Q_LOAD` (string table) |
| `AST_VAR_DECL` | `Q_LOAD` + `Q_MOVE` |
| `AST_ASSIGN` | `Q_MOVE` or `Q_SET_FIELD` |
| `AST_BINOP` | `Q_ADD/SUB/MUL/DIV/...` |
| `AST_COMPARE` | `Q_CMP_*` |
| `AST_CALL` | `Q_CALL` |
| `AST_IF` | `Q_JUMP_IF_NOT` + labels |
| `AST_WHILE` | `Q_JUMP_IF_NOT` + `Q_JUMP` |
| `AST_FOR_RANGE` | Loop with `Q_CMP_LT` + `Q_ADD` |
| `AST_FUNC_DEF` | `Q_LABEL` + body + `Q_RET` |
| `AST_RETURN` | `Q_RET` |
| `AST_ENTITY_NEW` | `Q_ENTITY_NEW` + `Q_SET_FIELD` |
| `AST_SAFE_ACCESS` | `Q_CMP_EQ` + `Q_JUMP_IF` |
| `AST_TRY_ERROR` | `Q_TRY_START` + `Q_TRY_END` |
| `AST_TASK` | `Q_TASK_SPAWN` |

---

## Critical Lowering Invariants (MUST PRESERVE)

1. **Evaluation Order:** Always left-to-right for binary ops and arguments
2. **Stack Discipline:** Every `Q_TRY_START` must have matching `Q_TRY_END`
3. **Loop Context:** Break/Continue must have valid loop context on stack
4. **Null Safety:** `AST_SAFE_ACCESS` must check null before dereferencing
5. **Register Discipline:** Caller-saved registers preserved across calls
6. **Type Consistency:** Float ops use `Q_F*`, int ops use `Q_*`

---

*Document generated for Stage 4 "Kill C" preparation — 22/03/2026*
