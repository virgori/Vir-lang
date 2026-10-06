# Arena and ownership patterns

## Explicit sub-arena

Use the parser-supported canonical header and close it as a statement block:

```vir
arena:
    let request = parse_request(input)
    handle(request)
end

arena(capacity: 65536):
    let buffer = build_buffer()
    consume(buffer)
end
```

Nested arenas are valid. Each child defines a narrower allocation lifetime;
only non-escaping allocations are reclaimed at its `end`.

## Lexical scopes and loop sub-arenas

Treat bodies of `if ... do`, `when ... loop`, `loop`, and `for ... do` as
lexical lifetime boundaries. A local borrow may not escape one of these scopes.

Loop bodies with local dynamic allocations may receive an implicit per-iteration
arena mark/reset when values do not escape across iterations. A loop-carried
owned value assigned to an outer binding must remain live, so the compiler
preserves/promotes it instead of resetting its storage.

```vir
var result = [0]
var index = 0
when index < 10 loop
    let local = [index, index + 1]
    result = local
    index = index + 1
end
```

Do not promise an implicit watermark for every control block or backend without
inspecting lowering and tests. When deterministic bounded scratch reclamation
is part of the program design, write an explicit `arena:` block.

## Owned escape versus borrow escape

Valid owned transfer:

```vir
func build() -> [int]:
    arena:
        let local = [5, 8, 13]
        out local
    end
end.
```

The owned graph moves outward and the source is invalid. Promotion must include
all reachable backing storage.

Invalid borrowed transfer:

```vir
func invalid:
    arena:
        let local = [5, 8]
        let borrowed = &local
        out borrowed
    end
end.
```

The borrow would outlive its owner. Casting it to `ptr` does not make it safe.

## Early exits and resources

Arena state must unwind correctly on normal exit, `break`, `skip`, `out`, and
error flow. Arena cleanup still does not close external resources:

```vir
func process(path: string):
    let fd = open_file(path)
    arena:
        consume(read_request(fd))
    end
ensure
    close_file(fd)
end.
```

Verify the actual `open_file`/`close_file` names before using this schematic
pattern in production code.

## Low-level arenas

Manual `arena_reset(handle)` or destroy/free operations do not perform compiler
promotion. Before calling them, prove that no live owned value, borrow, or raw
pointer refers to the region. Check allocation failure, capacity, alignment,
and the exact API name/signature in the selected module.

