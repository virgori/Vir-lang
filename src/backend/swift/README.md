# Vir → Swift Transpiler

Build native iOS/macOS apps from Vir source code.

## Architecture: Vỏ Vir - Nhân Native

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIR SOURCE CODE                              │
│                    (Clean syntax, 3-4x faster to write)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 1: VIR TRANSPILER                            │
│              vir → swift/kotlin translation                     │
│              (mapping.py, transpiler.py)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 2: NATIVE CORE (Optional)                    │
│              C/C++/Rust static libraries                        │
│              SIMD, GPU, heavy computation                       │
│              (bridge.py generates Swift FFI)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 3: NATIVE COMPILER                           │
│              swiftc / Xcode / kotlinc                           │
│              Fully optimized for Apple Silicon                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              FINAL: NATIVE BINARY                               │
│              .app bundle / executable                           │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Transpile Only (for debugging)

```bash
# Transpile .vir to .swift
vir transpile src/main.vir

# Output: .build/swift/main.swift
```

### 2. Full Build

```bash
# Build for macOS
vir build src/main.vir

# Build for iOS
vir build src/main.vir --target ios

# Release build (optimized)
vir build src/main.vir --release
```

### 3. With Native Libraries

```bash
# Link with C/Rust static library
vir build src/main.vir --native-lib libvir_math.a
```

## Syntax Mapping

| Vir | Swift | Notes |
|-----|-------|-------|
| `func foo() -> i32` | `func foo() -> Int32` | Types translated |
| `entity Point` | `struct Point` | Entity → Struct |
| `var x = 10` | `var x = 10` | Same |
| `const PI = 3.14` | `let PI = 3.14` | const → let |
| `if x > 0 then` | `if x > 0 {` | then → { |
| `end` | `}` | Block closing |
| `for i in 0..10` | `for i in 0..<10` | Range syntax |
| `out x` | `return x` | out → return |
| `and`, `or` | `&&`, `||` | Logical ops |
| `Vec<i32>` | `[Int32]` | Collections |
| `none` | `nil` | Null values |
| `EnumName::Value` | `EnumName.Value` | Enum access |

## Type Mapping

| Vir Type | Swift Type |
|----------|------------|
| `i8/i16/i32/i64` | `Int8/Int16/Int32/Int64` |
| `u8/u16/u32/u64` | `UInt8/UInt16/UInt32/UInt64` |
| `f32/f64` | `Float/Double` |
| `bool` | `Bool` |
| `str/String` | `String` |
| `Vec<T>` | `[T]` |
| `Dict<K,V>` | `[K: V]` |
| `Option<T>` | `T?` |

## Native Bridge

For performance-critical code, write in C/Rust and call from Vir:

**1. C Implementation (`libvir_math.c`)**:
```c
float vir_simd_dot_f32(const float* a, const float* b, int64_t len) {
    // SIMD-optimized dot product
    ...
}
```

**2. Vir Declaration**:
```vir
@native("vir_simd_dot_f32")
func native_dot(a: ptr, b: ptr, len: i64) -> f32

func dot(x: Vector, y: Vector) -> f32
    out native_dot(vec_ptr(x.data), vec_ptr(y.data), x.len)
end
```

**3. Build with library**:
```bash
# Compile C to static lib
clang -O3 -c libvir_math.c -o libvir_math.o
ar rcs libvir_math.a libvir_math.o

# Build Vir with native lib
vir build main.vir --native-lib libvir_math.a
```

## Project Structure

```
my_vir_app/
├── vir.json              # Project config
├── src/
│   ├── main.vir          # Entry point
│   ├── utils.vir         # Utilities
│   └── models/
│       └── user.vir
├── native/               # Optional native code
│   ├── vir_math.c
│   └── Makefile
└── .build/
    ├── swift/            # Generated Swift
    │   ├── main.swift
    │   └── utils.swift
    └── MyVirApp          # Final binary
```

## vir.json Configuration

```json
{
  "name": "MyVirApp",
  "version": "1.0.0",
  "target": "macos",
  "min_version": "14.0",
  "entry": "src/main.vir",
  "native_libs": [
    "native/libvir_math.a"
  ],
  "swift_flags": [
    "-O",
    "-whole-module-optimization"
  ]
}
```

## Why Transpile Instead of Direct Compilation?

1. **Leverage swiftc Optimization**: Apple's compiler is highly optimized for Apple Silicon (M1/M2/M3). We get this for free.

2. **Easy Debugging**: When something goes wrong, open the `.swift` file in Xcode and debug directly.

3. **Native Integration**: Call UIKit, SwiftUI, Foundation directly - no wrappers needed.

4. **Future-Proof**: As Swift evolves, we benefit automatically.

## Performance Numbers

| Operation | Pure Vir→Swift | With Native Core | Speedup |
|-----------|----------------|------------------|---------|
| Dot product (10k) | 45 µs | 3 µs | 15x |
| Matrix mul (1k×1k) | 2.1s | 0.08s | 26x |
| Softmax (10k) | 120 µs | 8 µs | 15x |

## Files

- `mapping.py` — Vir↔Swift syntax mapping table
- `transpiler.py` — Main transpiler (Vir AST → Swift code)
- `bridge.py` — Native FFI bridge generator
- `cli.py` — Command-line interface (`vir build`)

## License

Apache 2.0
