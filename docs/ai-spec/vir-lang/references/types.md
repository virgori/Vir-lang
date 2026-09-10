# Vir Types (AI Spec)

**Spec:** Vir v2.0

## Primitives

| Group | Types |
|---|---|
| Signed | `i8` `i16` `i32` `i64` |
| Unsigned | `u8` `u16` `u32` `u64` |
| Platform int | `int` `uint` |
| Float | `float` (IEEE 754, 8 bytes in spec) |
| Bool | `bool` (`true` / `false`) |
| String | `string` (immutable, arena) |
| Pointer | `ptr` (FFI / raw) |

Annotations optional for locals (inference); required for FFI and packed-entity fields.

```vir
var x = 42
var y: i32 = 42
func add(a: i32, b: i32) -> i32:
    out a + b
end.
```

## Compound

| Kind | Notes | Semantics |
|---|---|---|
| `entity` | Named record | Move |
| `packed entity` | No padding (FFI/mmap) | Move |
| `enum` (fieldless) | Named ints from 0 | Copy |
| `enum` (with payload) | Tagged union (arena-allocated) | Move / Arena |
| `register` / `mold` | Bit layouts | Copy |
| `array` / list `[…]` | Dynamic | Move |
| `dict` `["k": v]` | Key-value | Move |
| `flux<T,N>` | Fixed SIMD vector | Copy |
| `deck` | Shared CPU-GPU buffer handle | Move |

```vir
entity User:
    name: string
    age: int
end.

# Fieldless enum (immediate integer)
enum Color:
    Red
    Green
    Blue
end.

# Tagged union / Payload enum (generic or non-generic)
enum Option<T>:
    Some(value: T)
    None
end.

enum Shape:
    Circle(radius: float)
    Rect(w: int, h: int)
    Point
end.
```

Construction / access:

```vir
var u = User(name: "Alice", age: 30)
var c = Color.Red # fieldless immediate integer
var opt = Option.Some(42) # qualified with dot
var opt2 = Option::Some(42) # qualified with double-colon
var opt3 = Some(42) # unqualified when unique in scope
```

### Tagged Union ABI & Memory Layout

When an `enum` contains any variant with payload, instances are allocated via the runtime arena allocator (`rt_alloc(8 + max_payload_slots * 8)`):

| Byte Offset | Size | Field | Description |
|---|---|---|---|
| `0` | 4 bytes | `tag` (`u32`) | Variant index / tag ID (0, 1, 2, ...). |
| `4` | 4 bytes | `padding` | Zero padding for 8-byte alignment. |
| `8 + i * 8` | 8 bytes | `slot[i]` | 64-bit payload word for parameter `i` (pointer, int, or float). |

- **Fieldless variants** inside a tagged union (e.g., `Option.None`) also allocate an 8-byte cell with `tag = 1` and 0 payload slots, or use 0-length payload.
- **Pure fieldless enums** (having zero payload variants, like `Color`) are unboxed immediate 64-bit integers with zero heap allocation overhead (`Copy` semantics).

### Tagged Union Pattern Matching & Diagnostics

Pattern matching on enums is performed using `case`:

```vir
case opt
    Option.Some(val):
        print(val)
    Option.None:
        print(0)
end
```

- Qualified syntax `Enum.Variant` and `Enum::Variant` are both supported.
- Unqualified `Variant` is supported when unambiguous across all enums in scope.
- **Diagnostics**:
  - `E3031`: Constructor arity mismatch.
  - `E3032`: Non-exhaustive `case` (missing variant and no `else`).
  - `E3033`: Unknown variant name.
  - `E3034`: Wrong enum qualifier.
  - `E3035`: Duplicate variant arm in `case`.
  - `E3036`: Unreachable arm after `else`.
  - `E3037`: Wrong pattern binder count.
  - `E3038`: Ambiguous unqualified variant name.
  - `E3039`: Duplicate explicit tag.
  - `E3040`: Invalid tag range (must fit in `u32`).
  - `E3041`: Duplicate binder variable name in pattern.
  - `E3042`: Generic type argument mismatch.
  - `E3043`: Direct equality comparison `==` on payload enum (must use `case` pattern matching).

## Ownership (summary)

Do not invent Rust-looking syntax unless it matches Vir:

```vir
# owned param — caller moves in
func process(data: [i32]) -> [i32]:
    out data
end.

# shared borrow
func sum_all(data: &[i32]) -> int:
    out 0
end.

# mutable borrow
func clear_first(data: &mut [i32]):
    data[0] = 0
end.
```

- Copy types remain valid after assign
- Move types invalidate the source after move
- Shared + mutable borrow must not overlap

## Arena (Memory Management & Sub-arena Blocks)

Vir uses an **Arena-scoped bump allocator** for all dynamic allocations (`string`, `entity`, `array`, `dict`) without runtime GC or RC overhead:

- **Khối `arena:` (Sub-arena Block)**:
  Tạo sub-arena tạm thời, tự động thu hồi toàn bộ bộ nhớ cấp phát bên trong khi thoát khối hoặc sau mỗi lần lặp. Đóng bằng **`end`** (khối điều khiển).

```vir
when is_running loop
    arena:
        var req = read_request()
        var resp = process(req)
        send_response(resp)
    end   # Toàn bộ bộ nhớ của request được giải phóng tức thì tại đây
end
```

- **Tùy chỉnh dung lượng (`capacity`)**:

```vir
arena(capacity: 256KB):
    var big_buffer = process_large_data()
end
```

- **Quy tắc an toàn (Escape Prevention Rule)**:
  Đối tượng được cấp phát bên trong `arena:` không được phép thoát (escape) hoặc gán cho các biến có thời gian sống (lifetime) vượt ra ngoài khối `arena:`.

- **API Arena cấp thấp (Low-level Arena APIs)**:
  - `arena_alloc(size)`: Cấp phát từ arena hiện tại.
  - `arena_reset()`: Tua lại bump pointer của arena.
  - `arena_new(capacity)`: Tạo một arena handle độc lập.
  - `arena_alloc_from(arena, size)`: Cấp phát từ arena chỉ định.
  - `arena_free(arena)`: Thu hồi arena handle.

## Agent rules

1. Prefer `int` / `string` / `bool` for simple examples unless FFI needs fixed width.
2. Do not invent generic syntax beyond documented forms (`array`, `Option`, `Result`, `flux<T,N>`, …).
3. If unsure whether a type exists in the current toolchain, say so and point to `stdlib/vir/`.
