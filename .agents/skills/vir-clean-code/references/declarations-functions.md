# Declarations and function interfaces

## Grouped declarations

Canonical multiline form:

```vir
let
    source = load_source(path)
    tokens = lex(source)

var
    index = 0
    errors = 0

const
    MAX_ERRORS = 32
    DEFAULT_CAPACITY = 4096
```

Same-line group members require `;`:

```vir
let width = 80; height = 24
var row = 0; column = 0
```

Avoid repetitive adjacent declarations:

```vir
# Avoid
var row = 0
var column = 0
var count = 0

# Prefer
var
    row = 0
    column = 0
    count = 0
```

Do not group bindings solely because their mutability matches. A binding used
much later or created under a narrower control-flow lifetime belongs near that
use.

## Parenthesized signatures

Use for a small interface. Pass-by-value has no `in` prefix.

```vir
func add(left: int, right: int) -> int:
    out left + right
end.

func increment(ref value: int):
    value = value + 1
end.
```

Never place an `in` section inside `()`.

## Parameter-group signatures

Use one keyword per semantic group, not one per parameter:

```vir
func transform:
    in
        source: string
        start: int
        length: int
    ref
        scratch: Buffer
        diagnostics: Diagnostics
    out
        consumed: int
        status: int

    # body
end.
```

Compact aligned form is valid for a short group:

```vir
func buffer_write:
    ref buffer: Buffer
    in  source: ptr
        length: int

    # body
end.
```

The group ends at the next group keyword or the function body. Empty groups and
orphan members are errors. Prefer the expanded form when comments, long types,
or more than a few members make alignment fragile.

## Calls and initializers

Do not confuse the grammars:

- Entity field initializer: `User(name: "A", age: 30)`.
- Named function argument: `connect(host = name; timeout = 30)`.
- Positional call to block-declared parameters remains positional unless a
  verified named-call form is used.

