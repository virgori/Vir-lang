# Canonical Vir syntax quick reference

Use this reference for code generation and review. The canonical detailed
sources are `VIR-SPC-0017` / `VIR-SPC-0018`; this file is a decision aid, not a
replacement specification.

## Separators and blocks

One list separator rule applies to statements and declaration/parameter groups:
newline or `;`. Multiple items on the same line require `;`. A comma remains a
flat-list separator for constructs whose grammar defines it.

```vir
func classify(value: int) -> int:
    if value < 0 do
        out -1
    eif value == 0 do
        out 0
    else
        out 1
    end
end.
```

```vir
when active loop
    process()
end

for item in items do
    consume(item)
end

loop
    if done do break end
end
```

Use `skip` for the next iteration. `case`, `try:`, `arena:`, `select:`, and
`isolate:` are statement blocks and close with `end`.

## Distinctive forms

- Null: `none`.
- Interpolation: `"$name"`, `"$object.field"`, `"$(expression)"`, `"$$"` for
  a literal dollar sign.
- Ordinary generics: `Vec of (int)`, `func identity of (T)(value: T) -> T:`.
- Tensor type: `tensor[i32; 2, 3]`; tensor matmul: `a ** b`; tensor FMA:
  `a >< b`.
- Power: `^` and right-associative. Remainder: `mod`.
- Boolean: `left & right`, `left || right`, `!value`.
- Bitwise: `and`, `or`, `xor`, `shl`, `shr`.
- Shared and mutable borrow: `&value`, `&mut value`.
- Safe member access: `?.`; comparisons include `?=` and `?=/=`.
- Function result: `out value`.

## Entities, enums, and pattern matching

```vir
entity User:
    name: string
    age: int

    method birthday:
        this.age = this.age + 1
    end
end.

enum Option of (T):
    Some(value: T)
    None
end.

let result = Option.Some(42)
case result
    Option.Some(value):
        print(value)
    Option.None:
        print(0)
    else print(-1)
end
```

Use `Enum.Variant`, never `Enum::Variant`. Payload enums are destructured with
`case`; do not compare them directly with `==`. Entity construction uses field
initializers such as `User(name: "A", age: 30)`.

An entity member `method` is a nested block and closes with `end`; the owning
entity closes with `end.`. `method` is invalid at module scope. Use a free
`func` with an explicit first receiver parameter for standalone UFCS behavior.

Do not translate class/extension syntax from another language. These are the
two canonical declaration shapes:

```vir
entity Counter:
    value: int

    method add(delta: int) -> int:
        out this.value + delta
    end
end.

func reset(this: Counter):
    this.value = 0
end.
```

Never emit either of these forms:

```vir
# Invalid: a nested method does not own a dotted declaration boundary.
entity Counter:
    method read() -> int:
        out this.value
    end.
end.

# Invalid: module scope has no method declaration.
method reset(this: Counter):
    this.value = 0
end.
```

## UFCS and callable shadowing

Treat field access and callable resolution as separate operations:

```vir
entity HasLabel:
    label: int
end.

func label(this: HasLabel) -> int:
    out this.label + 7
end.

let value = HasLabel(label: 40)
print(value.label)      # data-field access: 40
print(value.label())    # free-function UFCS: 47
```

For `receiver.member(args)`, use this fixed order:

1. same-named entity method;
2. same-named field only when its declared type is structural `func(...)`;
3. eligible visible free function with the receiver inserted as argument zero;
4. compile error.

Method and callable-field selection are terminal by name. If the selected
candidate has the wrong arity or argument type, report that error and do not
fall back. A non-callable field is skipped rather than treated as a shadowing
candidate. Raw `ptr` is not a callable field.

Direct syntax pins the free function when a callable member has the same name:

```vir
score.compute(5)       # method/callable-member priority applies
compute(score, 5)      # explicitly selects the free function
```

Adding a method/callable field, or changing a data field to structural
function type, may redirect existing dotted calls and is potentially
source-breaking. Adding a non-callable field does not by itself block free
UFCS.

`packed entity`, `register`, `mold`, `flux`, `deck`, `map`, `reactive`,
`bundle`, `expose`, `infer`, `train`, and `quantize` are Vir constructs, but
their recognition is not permission to invent semantics. Read the exact SPEC
and a current positive test before emitting one.

## FFI declarations

FFI signatures require exact types and close as definitions:

```vir
@bind(c)
func native_call(value: i64) -> i64:
end.
```

Declaration-only `extern from ... func ...` also exists on supported native
paths. Verify the provider, target ABI, symbol, and active linker/backend before
using it. Do not infer Linux behavior from ARM64 or macOS behavior from the ISA
name alone.

## Errors and cleanup

`throw` carries the supported Vir error value. Function-level `ensure` runs on
every exit; `revert` handles propagated failure. Local compensation uses
`try:` / `revert` and may use `resume retry` or `resume revert` only under the
documented state rules. There is no `catch`, `finally`, or `saga` keyword.

```vir
func work:
    try:
        perform()
    revert
        compensate()
        resume revert
    end
ensure
    release_external_resource()
end.
```

## Async

Use `async func`; suspension forms belong inside it. `task call()` returns a
handle, `await operation` suspends, `await pass` yields cooperatively, `wait`
joins, and `cancel` requests cancellation. `quiet call()` is detached work and
requires an explicit cleanup/error policy. Do not invent promises or a global
scheduler.
