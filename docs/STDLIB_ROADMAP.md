# Vir Standard Library — Lộ trình & Đặc tả Toàn diện

> **Ngày tạo:** 7/3/2026  
> **Cập nhật:** 8/3/2026  
> **Dựa trên:** C23 Standard Library + Python 3.14 Standard Library  
> **Mục tiêu:** Xây dựng stdlib tối thiểu → đầy đủ → hệ sinh thái cho ngôn ngữ Vir

---

## ✅ TRẠNG THÁI HOÀN THÀNH

| Phase | Trạng thái | Số module | Ghi chú |
|-------|-----------|-----------|---------|
| **A — Bootstrap** | ✅ HOÀN TẤT | ~20 files / 12 modules | core, mem, str, io, path, math, time, env, collections, error, cli, debug |
| **B — Usable** | ✅ HOÀN TẤT | ~10 files / 10 modules | map, set, sort, rand, fs, process, fmt, test, json, regex |
| **C — Production** | ✅ HOÀN TẤT | ~10 files / 10 modules | thread, async, net, http, crypto, archive, config, serde, tls, sql |
| **D — Ecosystem** | ✅ HOÀN TẤT | ~12 files / 12 modules | ast, token, parser_kit, ffi, reflect, pkg, doc, bench, build, lsp, profile, doctest |
| **Prelude** | ✅ HOÀN TẤT | 1 file | vir/prelude.vri — auto-imported |
| **E — Virgex** | ✅ HOÀN TẤT (8/3/2026) | 1 module + Python ref | Vir Pattern Syntax — thay thế regex truyền thống |

**Tổng cộng: ~66 files `.vri` trong 42+ module directories dưới `stdlib/vir/` + `virgex/`**

### Module mới: Virgex (VPS) — 8/3/2026

```
virgex/
├── spec/VPS_SPEC_v1.md         # Đặc tả kỹ thuật v1.0 đầy đủ
├── src/                         # Python reference implementation
│   ├── __init__.py              # Public API
│   ├── tokens.py                # Token types & Quantifier
│   ├── lexer.py                 # VPS tokenizer
│   ├── ast_nodes.py             # AST node definitions
│   ├── parser.py                # Recursive-descent parser
│   ├── compiler.py              # AST → Python regex compiler
│   ├── matcher.py               # High-level matching API (Virgex class)
│   └── errors.py                # Error hierarchy
├── tests/                       # 113/113 tests pass
│   ├── test_lexer.py
│   ├── test_parser.py
│   ├── test_compiler.py
│   └── test_e2e.py
├── stdlib/virgex.vri            # Vir-native implementation (lexer + compiler)
└── README.md
```

**VPS ký hiệu:** `@` atom · `!` quantifier · `~` range · `?` optional · `:(` `:)` group · `|` anchor/OR · `$` escape · `-` space

### Danh sách đầy đủ files đã tạo:

```
stdlib/vir/
├── prelude.vri                          # Std prelude (auto-import)
├── core/
│   ├── types.vri                        # Primitives, limits, constants
│   ├── option.vri                       # Option<T> = Some(T) | None
│   ├── result.vri                       # Result<T, E> = Ok(T) | Err(E)
│   ├── ops.vri                          # Checked arithmetic
│   └── bits.vri                         # Bit manipulation, popcount, clz
├── mem/
│   ├── alloc.vri                        # Allocator (malloc/free/realloc)
│   ├── slice.vri                        # Slice<T> view
│   ├── buffer.vri                       # Buffer (growable byte array)
│   ├── arena.vri                        # Arena allocator
│   └── copy.vri                         # Deep/shallow copy
├── str/
│   ├── string.vri                       # Immutable UTF-8 String
│   ├── builder.vri                      # Mutable StringBuilder
│   ├── char.vri                         # Char classification
│   ├── unicode.vri                      # UTF-8 encode/decode
│   └── encode.vri                       # UTF-8↔UTF-16↔UTF-32
├── io/
│   ├── traits.vri                       # Reader/Writer traits
│   ├── stdio.vri                        # stdin/stdout/stderr
│   ├── file.vri                         # File I/O
│   ├── format.vri                       # Format strings
│   └── buffered.vri                     # BufferedReader/Writer
├── path/
│   └── path.vri                         # Path abstraction
├── math/
│   └── basic.vri                        # Math functions (trig, exp, etc.)
├── time/
│   └── time.vri                         # Instant, Duration, clock
├── env/
│   └── env.vri                          # OS detection, env vars, signals
├── collections/
│   ├── vec.vri                          # Vec<T> dynamic array
│   ├── deque.vri                        # Deque<T>
│   ├── heap.vri                         # MinHeap<T> priority queue
│   ├── ring.vri                         # RingBuffer<T>
│   ├── map.vri                          # HashMap<K, V> (FNV-1a, open addressing)
│   └── set.vri                          # HashSet<T>
├── error/
│   └── error.vri                        # Error type, error chains
├── cli/
│   ├── args.vri                         # Argument parser
│   └── shlex.vri                        # Shell lexer
├── debug/
│   ├── assert.vri                       # assert, assert_eq, assert_ne
│   └── trace.vri                        # Stack trace
├── sort/
│   └── sort.vri                         # Introsort + binary_search
├── rand/
│   └── rand.vri                         # xoshiro256** PRNG
├── fs/
│   └── fs.vri                           # Filesystem operations
├── process/
│   └── process.vri                      # Subprocess Command builder
├── fmt/
│   └── fmt.vri                          # Format template engine
├── test/
│   └── test.vri                         # Test framework
├── json/
│   └── json.vri                         # RFC 8259 JSON parser/serializer
├── regex/
│   └── regex.vri                        # NFA regex (Thompson's construction)
├── thread/
│   └── thread.vri                       # Thread, Mutex, RwLock, Channel
├── async/
│   └── async.vri                        # EventLoop, Task, Future
├── net/
│   └── net.vri                          # TCP/UDP sockets
├── http/
│   └── http.vri                         # HTTP/1.1 client
├── crypto/
│   └── crypto.vri                       # SHA-256, HMAC, secure random
├── archive/
│   └── archive.vri                      # Deflate/Gzip/Tar
├── config/
│   └── config.vri                       # INI parser, env override
├── serde/
│   └── serde.vri                        # Binary serialization
├── tls/
│   └── tls.vri                          # TLS/SSL wrapper
├── sql/
│   └── sql.vri                          # SQLite binding
├── ast/
│   └── ast.vri                          # Complete Vir AST nodes
├── token/
│   └── token.vri                        # Vir lexer / tokenizer
├── parser_kit/
│   └── parser_kit.vri                   # Recursive descent parser
├── ffi/
│   └── ffi.vri                          # Dynamic library + C FFI
├── reflect/
│   └── reflect.vri                      # Runtime reflection
├── pkg/
│   └── pkg.vri                          # Package manager / SemVer
├── doc/
│   └── doc.vri                          # Doc generator
├── bench/
│   └── bench.vri                        # Benchmarking framework
├── build/
│   └── build.vri                        # Build system driver
├── lsp/
│   └── lsp.vri                          # Language Server Protocol
├── profile/
│   └── profile.vri                      # Runtime profiler
└── doctest/
    └── doctest.vri                      # Doc-test runner
```

---

## 0. Nguyên tắc Thiết kế

| # | Nguyên tắc | Học từ |
|---|-----------|--------|
| 1 | **Nhỏ, sát máy, rõ chi phí** — mỗi API phải rõ cost (có allocate không? O(n) hay O(1)?) | C23 |
| 2 | **Thực dụng, API nhất quán** — module tổ chức theo domain, tên hàm đọc là hiểu | Python |
| 3 | **Zero-cost khi không dùng** — import module nào chỉ link module đó | C23 |
| 4 | **Option/Result thay vì exception** — error handling tường minh, không panic ngầm | Rust-inspired |
| 5 | **Unicode-first** — string mặc định là UTF-8, không dùng null-terminated byte string | Vượt C |
| 6 | **Đa ngôn ngữ tự nhiên** — API tiếng Anh là chuẩn, sublib ánh xạ tên tiếng Việt/中文/日本語/한국어 | Vir riêng |
| 7 | **Self-hosting first** — ưu tiên những gì compiler cần để tự biên dịch chính nó | Vir SELF_HOSTING_SPEC |

---

## 1. Tổng quan 4 Phase

```
Phase A: Bootstrap        Phase B: Usable           Phase C: Production       Phase D: Ecosystem
(ngôn ngữ sống được)     (viết app thật được)      (deploy được)            (hệ sinh thái đầy đủ)
                                                    
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ vir/core         │    │ vir/vec          │    │ vir/thread       │    │ vir/ast          │
│ vir/mem          │    │ vir/map          │    │ vir/atomic       │    │ vir/token         │
│ vir/str          │    │ vir/set          │    │ vir/async        │    │ vir/parser_kit    │
│ vir/io           │    │ vir/json         │    │ vir/net          │    │ vir/ffi           │
│ vir/path         │    │ vir/regex        │    │ vir/http         │    │ vir/reflect       │
│ vir/math         │    │ vir/fs           │    │ vir/crypto       │    │ vir/pkg           │
│ vir/time         │    │ vir/process      │    │ vir/archive      │    │ vir/doc           │
│ vir/env          │    │ vir/log          │    │ vir/config       │    │ vir/bench         │
│ vir/collections  │    │ vir/test         │    │ vir/sql          │    │ vir/lsp           │
│ vir/error        │    │ vir/fmt          │    │ vir/serde        │    │ vir/build         │
│ vir/cli          │    │ vir/sort         │    │ vir/tls          │    │ vir/profile       │
│ vir/debug        │    │ vir/rand         │    │ vir/compress     │    │ vir/doctest       │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
     ~12 modules             ~12 modules             ~12 modules             ~12 modules
     Compiler tự dùng        App viết được            Hệ thống thật           Tooling đầy đủ
```

---

## 2. Mapping: C23 Headers → Python Modules → Vir Stdlib

### 2.1. Core / Runtime / Utility

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<assert.h>` | `assert` statement | **vir/debug** | Debug assertions, panic | A |
| `<errno.h>` | `errno` module | **vir/error** | Error codes, Result type | A |
| `<stdlib.h>` | builtins + `sys` | **vir/core** | Primitives, exit, conversion | A |
| `<stddef.h>` | builtins | **vir/core** | size, offset, base types | A |
| `<stdint.h>` | — (Python has bigint) | **vir/core** | i8/i16/i32/i64/u8/u16/u32/u64 | A |
| `<inttypes.h>` | — | **vir/fmt** | Integer format macros | B |
| `<limits.h>` | `sys.maxsize` | **vir/core** | Type limits: I64_MAX, etc. | A |
| `<float.h>` | `sys.float_info` | **vir/core** | Float limits: F64_MAX, etc. | A |

### 2.2. String / Memory / Character

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<string.h>` | `str` type + methods | **vir/str** | String ops, bytes, buffer | A |
| `<ctype.h>` | `str.isdigit()` etc. | **vir/str** | Character classification | A |
| `<wchar.h>` | — (Python str is Unicode) | **vir/str** | UTF-8/UTF-16/UTF-32 | A |
| `<wctype.h>` | `unicodedata` | **vir/str** | Unicode category | A |
| `<uchar.h>` | `codecs` | **vir/str** | Encoding conversion | A |
| — | `re` | **vir/regex** | Regular expressions | B |
| — | `textwrap` | **vir/str** | Text wrapping | B |
| — | `difflib` | **vir/str** | Text diff | B |

### 2.3. Memory Management

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<stdlib.h>` (malloc/free) | `gc`, `tracemalloc` | **vir/mem** | Allocator, slices, arena | A |

### 2.4. I/O / File / Format

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<stdio.h>` | `io`, `print()`, `open()` | **vir/io** | Reader/Writer, stdin/stdout | A |
| — | `pathlib`, `os.path` | **vir/path** | Path abstraction | A |
| — | `os`, `shutil`, `glob`, `tempfile` | **vir/fs** | Filesystem operations | B |
| — | `json` | **vir/json** | JSON encode/decode | B |
| — | `csv`, `configparser`, `tomllib` | **vir/config** | Config file formats | C |
| — | `pickle`, `marshal` | **vir/serde** | Serialization framework | C |
| — | `sqlite3` | **vir/sql** | Embedded DB | C |

### 2.5. Math / Numeric

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<math.h>` | `math` | **vir/math** | Basic math functions | A |
| `<complex.h>` | `cmath` | **vir/math** | Complex numbers (later) | C |
| `<tgmath.h>` | — | **vir/math** | Generic math dispatch | A |
| `<fenv.h>` | — | **vir/math** | Float environment | C |
| `<stdbit.h>` (C23 new) | — | **vir/math** | Bit manipulation, byte order | A |
| `<stdckdint.h>` (C23 new) | — | **vir/math** | Checked integer arithmetic | A |
| — | `decimal` | **vir/math** | Arbitrary precision (later) | C |
| — | `fractions` | **vir/math** | Rational numbers (later) | C |
| — | `statistics` | **vir/math** | Basic statistics | C |
| — | `random` | **vir/rand** | Random number generation | B |

### 2.6. Time / Calendar / Locale

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<time.h>` | `time`, `datetime` | **vir/time** | Timestamp, duration, clock | A |
| — | `calendar` | **vir/time** | Calendar helpers | C |
| — | `zoneinfo` | **vir/time** | Timezone | C |
| `<locale.h>` | `locale`, `gettext` | — | Locale (defer) | D |

### 2.7. OS / Process / Signal

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<signal.h>` | `signal` | **vir/env** | Signal handling | A |
| `<setjmp.h>` | — | **vir/error** | Non-local jump (panic) | A |
| — | `os` | **vir/env** | Environment variables | A |
| — | `subprocess` | **vir/process** | Process spawning | B |
| — | `platform`, `sys` | **vir/env** | Platform detection | A |

### 2.8. Concurrency

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| `<threads.h>` | `threading` | **vir/thread** | Threads, mutex, condvar | C |
| `<stdatomic.h>` | — | **vir/atomic** | Atomic operations | C |
| — | `asyncio` | **vir/async** | Async event loop, futures | C |
| — | `concurrent.futures` | **vir/async** | Task pool | C |
| — | `queue` | **vir/collections** | Thread-safe queue | C |
| — | `multiprocessing` | **vir/process** | Multi-process (later) | D |

### 2.9. Data Structures

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `list` builtin | **vir/collections** | Vec (dynamic array) | A |
| — | `dict` builtin | **vir/map** | HashMap | B |
| — | `set` builtin | **vir/set** | HashSet | B |
| — | `collections.deque` | **vir/collections** | Deque | A |
| — | `heapq` | **vir/collections** | Priority queue | A |
| — | `bisect` | **vir/sort** | Binary search | B |
| — | `array` | **vir/collections** | Typed array | A |
| — | `enum` | **vir/core** | Enum type | A |
| — | `dataclasses` | **vir/core** | Record/struct helper | A |
| — | `graphlib` | **vir/collections** | Topological sort | B |
| — | `copy` | **vir/mem** | Deep/shallow copy | A |
| — | `types` | **vir/core** | Type metadata | A |

### 2.10. Security / Crypto / Hash

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `hashlib` | **vir/crypto** | Hash functions (SHA, etc.) | C |
| — | `hmac` | **vir/crypto** | HMAC | C |
| — | `secrets` | **vir/crypto** | Secure random | C |
| — | `ssl` | **vir/tls** | TLS binding | C |

### 2.11. Compression / Archive

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `gzip`, `bz2`, `lzma` | **vir/compress** | Stream compression | C |
| — | `zipfile`, `tarfile` | **vir/archive** | Archive read/write | C |

### 2.12. Networking

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `socket` | **vir/net** | Socket layer | C |
| — | `http` | **vir/http** | HTTP client/server | C |
| — | `urllib` | **vir/http** | URL parser | C |
| — | `email` | — | Email (defer to ecosystem) | — |

### 2.13. Testing / Debugging / Profiling

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `unittest`, `doctest` | **vir/test** | Test framework | B |
| — | `logging` | **vir/log** | Logger | B |
| — | `traceback` | **vir/debug** | Stack trace | A |
| — | `cProfile` | **vir/profile** | Profiler | D |
| — | `pdb` | **vir/debug** | Debugger hooks | A |
| — | `faulthandler` | **vir/debug** | Crash handler | A |

### 2.14. Language Tooling

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `ast` | **vir/ast** | AST node library | D |
| — | `tokenize`, `token` | **vir/token** | Tokenizer support | D |
| — | `keyword` | **vir/token** | Keyword list | D |
| — | `symtable` | **vir/ast** | Symbol table | D |
| — | `importlib` | **vir/pkg** | Module/package system | D |
| — | `inspect` | **vir/reflect** | Reflection API | D |
| — | `dis` | **vir/reflect** | Bytecode/IR inspection | D |

### 2.15. CLI / Terminal

| C23 Header | Python Module | Vir Module | Chức năng | Phase |
|-----------|--------------|------------|-----------|-------|
| — | `argparse` | **vir/cli** | Argument parser | A |
| — | `shlex` | **vir/cli** | Shell lexer | A |
| — | `readline` | **vir/cli** | Line editor | B |
| — | `curses` | — | TUI (defer to ecosystem) | — |
| `<stdarg.h>` | — | **vir/core** | Variadic functions | A |

---

## 3. Chi tiết từng Module — Phase A (Bootstrap)

> Mục tiêu: Vir có đủ stdlib để compiler tự biên dịch chính nó

### 3.1. `vir/core` — Kiểu nguyên thủy & nền tảng

**Học từ C23:** `<stddef.h>`, `<stdint.h>`, `<limits.h>`, `<float.h>`, `<stdbool.h>`, `<stdarg.h>`  
**Học từ Python:** builtins (`int`, `float`, `bool`, `None`, `type`), `enum`, `dataclasses`

```
vir/core/
├── types.vri          # i8, i16, i32, i64, u8, u16, u32, u64, f32, f64, bool, byte
├── limits.vri         # I8_MIN, I8_MAX, I64_MAX, U64_MAX, F64_EPSILON, F64_MAX
├── option.vri         # Option<T> = Some(T) | None
├── result.vri         # Result<T, E> = Ok(T) | Err(E)
├── enum.vri           # Enum support macros / helpers
├── record.vri         # Record/struct helper (like dataclasses)
├── convert.vri        # to_i64(), to_f64(), to_str(), parse_int(), parse_float()
├── ops.vri            # Checked arithmetic: add_checked(), mul_checked() (C23 stdckdint.h)
└── bits.vri           # Bit ops: count_ones(), leading_zeros(), byte_swap() (C23 stdbit.h)
```

**API tối thiểu:**
```
# types.vri
kiểu i8    # -128 .. 127
kiểu i16   # -32768 .. 32767
kiểu i32   # -2^31 .. 2^31-1
kiểu i64   # -2^63 .. 2^63-1 (mặc định "số")
kiểu u8    # 0 .. 255
kiểu u16   # 0 .. 65535
kiểu u32   # 0 .. 2^32-1
kiểu u64   # 0 .. 2^64-1
kiểu f32   # IEEE 754 single
kiểu f64   # IEEE 754 double (mặc định "thực")
kiểu bool  # đúng / sai
kiểu byte  # alias cho u8

# option.vri
liệt_kê Option thì
  Some(giá_trị)
  None
hết

hàm is_some(opt: Option) → bool
hàm is_none(opt: Option) → bool
hàm unwrap(opt: Option) → giá_trị  # panic nếu None
hàm unwrap_or(opt: Option, mặc_định) → giá_trị

# result.vri
liệt_kê Result thì
  Ok(giá_trị)
  Err(lỗi)
hết

hàm is_ok(r: Result) → bool
hàm is_err(r: Result) → bool
hàm unwrap(r: Result) → giá_trị  # panic nếu Err
hàm map(r: Result, f: hàm) → Result

# ops.vri (từ C23 <stdckdint.h>)
hàm add_checked(a: i64, b: i64) → Result<i64, OverflowError>
hàm sub_checked(a: i64, b: i64) → Result<i64, OverflowError>
hàm mul_checked(a: i64, b: i64) → Result<i64, OverflowError>

# bits.vri (từ C23 <stdbit.h>)
hàm count_ones(x: u64) → u32       # popcount
hàm count_zeros(x: u64) → u32
hàm leading_zeros(x: u64) → u32    # clz
hàm trailing_zeros(x: u64) → u32   # ctz
hàm rotate_left(x: u64, n: u32) → u64
hàm rotate_right(x: u64, n: u32) → u64
hàm byte_swap(x: u64) → u64        # endian swap
hàm bit_width(x: u64) → u32        # floor(log2(x)) + 1
```

**Tự dùng cho compiler:** enum TokenKind, struct Token, Result cho parser errors.

---

### 3.2. `vir/mem` — Quản lý bộ nhớ

**Học từ C23:** `<stdlib.h>` (malloc/free/realloc), `<string.h>` (memcpy/memset/memmove)  
**Học từ Python:** `gc`, `tracemalloc`, `copy`

```
vir/mem/
├── alloc.vri          # Allocator interface, global alloc, free
├── slice.vri          # Slice<T> = (ptr, len) — borrowed view
├── buffer.vri         # Buffer = growable byte array (owned)
├── arena.vri          # Arena allocator (bump allocator)
└── copy.vri           # memcpy, memset, memmove, deep_copy
```

**API tối thiểu:**
```
# alloc.vri
hàm alloc(size: u64) → ptr           # malloc
hàm alloc_zeroed(size: u64) → ptr    # calloc
hàm realloc(p: ptr, new_size: u64) → ptr
hàm free(p: ptr)
hàm size_of<T>() → u64

# slice.vri
bản_ghi Slice thì
  data: ptr
  len: u64
hết
hàm slice_get(s: Slice, i: u64) → byte
hàm slice_set(s: Slice, i: u64, val: byte)
hàm slice_sub(s: Slice, from: u64, to: u64) → Slice

# buffer.vri
bản_ghi Buffer thì
  data: ptr
  len: u64
  cap: u64
hết
hàm buffer_new(cap: u64) → Buffer
hàm buffer_push(b: Buffer, byte: u8)
hàm buffer_write(b: Buffer, data: Slice)
hàm buffer_as_slice(b: Buffer) → Slice
hàm buffer_free(b: Buffer)

# arena.vri
bản_ghi Arena thì
  base: ptr
  offset: u64
  cap: u64
hết
hàm arena_new(size: u64) → Arena
hàm arena_alloc(a: Arena, size: u64) → ptr   # bump pointer, O(1)
hàm arena_reset(a: Arena)                      # free tất cả cùng lúc
hàm arena_free(a: Arena)

# copy.vri
hàm mem_copy(dst: ptr, src: ptr, n: u64)
hàm mem_set(dst: ptr, val: u8, n: u64)
hàm mem_move(dst: ptr, src: ptr, n: u64)
hàm mem_cmp(a: ptr, b: ptr, n: u64) → i32
```

**Tự dùng cho compiler:** Arena cho AST nodes, Buffer cho machine code emit.

---

### 3.3. `vir/str` — Chuỗi & Unicode

**Học từ C23:** `<string.h>`, `<ctype.h>`, `<wchar.h>`, `<uchar.h>`  
**Học từ Python:** `str` type, `unicodedata`, `codecs`

```
vir/str/
├── string.vri         # String type (UTF-8 immutable), basic ops
├── builder.vri        # StringBuilder (mutable append builder)
├── char.vri           # Character classification (isdigit, isalpha, ...)
├── unicode.vri        # Unicode normalization, categories
├── encode.vri         # UTF-8 / UTF-16 / UTF-32 encode/decode
└── search.vri         # find, contains, starts_with, ends_with, split, join
```

**API tối thiểu:**
```
# string.vri
bản_ghi String thì
  data: ptr          # UTF-8 bytes
  byte_len: u64      # byte length
  char_len: u64      # codepoint count (cached)
hết

hàm str_new(literal: chuỗi) → String
hàm str_len(s: String) → u64                     # codepoint count
hàm str_byte_len(s: String) → u64                # byte count
hàm str_char_at(s: String, i: u64) → u32         # codepoint
hàm str_slice(s: String, from: u64, to: u64) → String
hàm str_concat(a: String, b: String) → String
hàm str_eq(a: String, b: String) → bool
hàm str_cmp(a: String, b: String) → i32          # lexicographic
hàm str_contains(haystack: String, needle: String) → bool
hàm str_starts_with(s: String, prefix: String) → bool
hàm str_ends_with(s: String, suffix: String) → bool
hàm str_find(s: String, needle: String) → Option<u64>
hàm str_split(s: String, delim: String) → Vec<String>
hàm str_join(parts: Vec<String>, sep: String) → String
hàm str_trim(s: String) → String
hàm str_to_upper(s: String) → String
hàm str_to_lower(s: String) → String
hàm str_replace(s: String, old: String, new: String) → String

# builder.vri
bản_ghi StringBuilder thì
  buf: Buffer
hết
hàm sb_new() → StringBuilder
hàm sb_append(sb: StringBuilder, s: String)
hàm sb_append_char(sb: StringBuilder, c: u32)
hàm sb_append_i64(sb: StringBuilder, n: i64)
hàm sb_build(sb: StringBuilder) → String
hàm sb_free(sb: StringBuilder)

# char.vri
hàm is_digit(c: u32) → bool
hàm is_alpha(c: u32) → bool
hàm is_alnum(c: u32) → bool
hàm is_space(c: u32) → bool
hàm is_upper(c: u32) → bool
hàm is_lower(c: u32) → bool
hàm to_upper(c: u32) → u32
hàm to_lower(c: u32) → u32
hàm is_ascii(c: u32) → bool
```

**Tự dùng cho compiler:** Lexer cần string ops, StringBuilder cho error messages.

---

### 3.4. `vir/io` — Nhập xuất

**Học từ C23:** `<stdio.h>`  
**Học từ Python:** `io` module, `print()`, `open()`, `sys.stdin/stdout/stderr`

```
vir/io/
├── traits.vri         # Reader, Writer, Seeker interfaces
├── stdio.vri          # stdin, stdout, stderr
├── file.vri           # File open/read/write/close
├── buffered.vri       # BufferedReader, BufferedWriter
└── format.vri         # format(), print(), println()
```

**API tối thiểu:**
```
# traits.vri
giao_diện Reader thì
  hàm read(buf: Slice) → Result<u64, IoError>
hết

giao_diện Writer thì
  hàm write(data: Slice) → Result<u64, IoError>
  hàm flush() → Result<(), IoError>
hết

# stdio.vri
hàm print(s: String)                      # write to stdout, no newline
hàm println(s: String)                    # write to stdout + newline
hàm eprint(s: String)                     # write to stderr
hàm eprintln(s: String)                   # write to stderr + newline
hàm read_line() → Result<String, IoError> # read line from stdin

# file.vri
bản_ghi File thì
  fd: i64
  path: String
  mode: FileMode
hết

liệt_kê FileMode thì
  Read = 1
  Write = 2
  Append = 4
  ReadWrite = 3
hết

hàm file_open(path: String, mode: FileMode) → Result<File, IoError>
hàm file_read(f: File, buf: Slice) → Result<u64, IoError>
hàm file_read_all(f: File) → Result<String, IoError>
hàm file_write(f: File, data: Slice) → Result<u64, IoError>
hàm file_write_str(f: File, s: String) → Result<u64, IoError>
hàm file_close(f: File) → Result<(), IoError>
hàm file_seek(f: File, offset: i64, whence: SeekFrom) → Result<u64, IoError>
hàm file_size(f: File) → Result<u64, IoError>

# format.vri
hàm format(template: String, args: ...) → String
hàm format_int(n: i64, base: u32) → String    # base = 2, 8, 10, 16
hàm format_float(f: f64, precision: u32) → String
hàm format_hex(n: u64) → String
```

**Tự dùng cho compiler:** Đọc source file, ghi binary output, in error messages.

---

### 3.5. `vir/path` — Đường dẫn

**Học từ Python:** `pathlib`

```
vir/path/
└── path.vri           # Path manipulation
```

**API tối thiểu:**
```
bản_ghi Path thì
  raw: String
hết

hàm path_new(s: String) → Path
hàm path_join(base: Path, child: String) → Path
hàm path_parent(p: Path) → Option<Path>
hàm path_filename(p: Path) → Option<String>
hàm path_stem(p: Path) → Option<String>        # filename without extension
hàm path_extension(p: Path) → Option<String>
hàm path_is_absolute(p: Path) → bool
hàm path_normalize(p: Path) → Path
hàm path_exists(p: Path) → bool
hàm path_is_file(p: Path) → bool
hàm path_is_dir(p: Path) → bool
hàm path_to_string(p: Path) → String
```

**Tự dùng cho compiler:** Module resolver, source file lookup.

---

### 3.6. `vir/math` — Toán học

**Học từ C23:** `<math.h>`, `<tgmath.h>`, `<stdbit.h>`, `<stdckdint.h>`  
**Học từ Python:** `math`

```
vir/math/
├── basic.vri          # abs, min, max, clamp
├── float.vri          # sin, cos, tan, sqrt, pow, log, exp, ceil, floor, round
├── integer.vri        # gcd, lcm, factorial, checked arithmetic
└── const.vri          # PI, E, TAU, INF, NAN
```

**API tối thiểu:**
```
# const.vri
hằng PI  = 3.14159265358979323846
hằng E   = 2.71828182845904523536
hằng TAU = 6.28318530717958647692
hằng INF = +∞
hằng NAN = NaN

# basic.vri
hàm abs(x: i64) → i64
hàm abs_f(x: f64) → f64
hàm min(a: i64, b: i64) → i64
hàm max(a: i64, b: i64) → i64
hàm clamp(x: i64, lo: i64, hi: i64) → i64

# float.vri
hàm sqrt(x: f64) → f64
hàm pow(base: f64, exp: f64) → f64
hàm sin(x: f64) → f64
hàm cos(x: f64) → f64
hàm tan(x: f64) → f64
hàm asin(x: f64) → f64
hàm acos(x: f64) → f64
hàm atan(x: f64) → f64
hàm atan2(y: f64, x: f64) → f64
hàm exp(x: f64) → f64
hàm log(x: f64) → f64
hàm log2(x: f64) → f64
hàm log10(x: f64) → f64
hàm ceil(x: f64) → f64
hàm floor(x: f64) → f64
hàm round(x: f64) → f64
hàm is_nan(x: f64) → bool
hàm is_inf(x: f64) → bool

# integer.vri
hàm gcd(a: i64, b: i64) → i64
hàm lcm(a: i64, b: i64) → i64
hàm pow_int(base: i64, exp: u32) → i64
```

**Tự dùng cho compiler:** Ít dùng trực tiếp nhưng cần cho standard library foundation.

---

### 3.7. `vir/time` — Thời gian

**Học từ C23:** `<time.h>`  
**Học từ Python:** `time`, `datetime`

```
vir/time/
├── instant.vri        # Instant (monotonic clock)
├── duration.vri       # Duration (nanosecond-precision)
├── datetime.vri       # Date, Time, DateTime
└── clock.vri          # now(), elapsed(), sleep()
```

**API tối thiểu:**
```
# instant.vri
bản_ghi Instant thì
  nanos: u64    # nanoseconds since epoch (monotonic)
hết
hàm now() → Instant
hàm elapsed(start: Instant) → Duration

# duration.vri
bản_ghi Duration thì
  secs: u64
  nanos: u32
hết
hàm duration_from_secs(s: u64) → Duration
hàm duration_from_millis(ms: u64) → Duration
hàm duration_from_nanos(ns: u64) → Duration
hàm duration_to_millis(d: Duration) → u64
hàm duration_add(a: Duration, b: Duration) → Duration

# clock.vri
hàm sleep(d: Duration)
hàm sleep_ms(ms: u64)
```

**Tự dùng cho compiler:** Benchmark compile time, JIT timing.

---

### 3.8. `vir/env` — Môi trường & nền tảng

**Học từ C23:** `<signal.h>`, `<stdlib.h>` (getenv, exit)  
**Học từ Python:** `os`, `sys`, `platform`, `signal`

```
vir/env/
├── vars.vri           # Environment variables
├── platform.vri       # OS, arch detection
├── signal.vri         # Signal handling
└── exit.vri           # Process exit, panic
```

**API tối thiểu:**
```
# vars.vri
hàm get_env(key: String) → Option<String>
hàm set_env(key: String, val: String)
hàm env_vars() → Vec<(String, String)>

# platform.vri
liệt_kê OS thì
  MacOS
  Linux
  Windows
  Unknown
hết

liệt_kê Arch thì
  ARM64
  X86_64
  Unknown
hết

hàm current_os() → OS
hàm current_arch() → Arch

# exit.vri
hàm exit(code: i32)            # terminate process
hàm panic(msg: String)         # print + abort
hàm abort()                     # immediate abort
```

**Tự dùng cho compiler:** Platform detection cho codegen, env vars cho config.

---

### 3.9. `vir/collections` — Cấu trúc dữ liệu cơ bản

**Học từ C23:** — (C23 không có collections)  
**Học từ Python:** `list`, `collections.deque`, `heapq`, `array`

```
vir/collections/
├── vec.vri            # Vec<T> — dynamic array
├── deque.vri          # Deque<T> — double-ended queue
├── heap.vri           # MinHeap<T> — priority queue
└── ring.vri           # RingBuffer<T> — fixed-size ring
```

**API tối thiểu (Vec):**
```
bản_ghi Vec thì
  data: ptr
  len: u64
  cap: u64
  elem_size: u64
hết

hàm vec_new() → Vec
hàm vec_with_cap(cap: u64) → Vec
hàm vec_push(v: Vec, item)
hàm vec_pop(v: Vec) → Option
hàm vec_get(v: Vec, i: u64) → Option
hàm vec_set(v: Vec, i: u64, item)
hàm vec_len(v: Vec) → u64
hàm vec_cap(v: Vec) → u64
hàm vec_is_empty(v: Vec) → bool
hàm vec_clear(v: Vec)
hàm vec_insert(v: Vec, i: u64, item)
hàm vec_remove(v: Vec, i: u64) → Option
hàm vec_contains(v: Vec, item) → bool
hàm vec_reverse(v: Vec)
hàm vec_sort(v: Vec, cmp: hàm)
hàm vec_iter(v: Vec) → Iterator
hàm vec_free(v: Vec)
```

**Tự dùng cho compiler:** Token list, instruction list, symbol table.

---

### 3.10. `vir/error` — Xử lý lỗi

**Học từ C23:** `<errno.h>`, `<setjmp.h>`  
**Học từ Python:** `Exception` hierarchy, `traceback`

```
vir/error/
├── error.vri          # Error trait, common error types
├── result.vri         # Result type (re-export từ core)
└── panic.vri          # Panic handler, stack unwind
```

**API tối thiểu:**
```
giao_diện Error thì
  hàm message() → String
  hàm code() → i32
hết

bản_ghi IoError thực_hiện Error thì
  kind: IoErrorKind
  msg: String
hết

liệt_kê IoErrorKind thì
  NotFound = 1
  PermissionDenied = 2
  AlreadyExists = 3
  InvalidInput = 4
  TimedOut = 5
  Other = 99
hết

bản_ghi ParseError thực_hiện Error thì
  line: u64
  col: u64
  msg: String
hết

bản_ghi OverflowError thực_hiện Error thì
  msg: String
hết
```

**Tự dùng cho compiler:** Parse errors, file I/O errors, codegen errors.

---

### 3.11. `vir/cli` — Command Line

**Học từ Python:** `argparse`, `shlex`

```
vir/cli/
├── args.vri           # Argument parser
└── shlex.vri          # Shell-safe string splitting
```

**API tối thiểu:**
```
bản_ghi ArgParser thì
  name: String
  description: String
  args: Vec<ArgDef>
hết

bản_ghi ArgDef thì
  name: String
  short: String          # "-v"
  long: String           # "--verbose"
  help: String
  required: bool
  default: Option<String>
hết

bản_ghi ParsedArgs thì
  positional: Vec<String>
  flags: Map<String, String>
hết

hàm arg_parser_new(name: String, desc: String) → ArgParser
hàm arg_add(p: ArgParser, def: ArgDef)
hàm arg_parse(p: ArgParser, argv: Vec<String>) → Result<ParsedArgs, String>
hàm arg_get(parsed: ParsedArgs, name: String) → Option<String>
hàm arg_has(parsed: ParsedArgs, name: String) → bool

# shlex
hàm shlex_split(s: String) → Vec<String>
hàm shlex_quote(s: String) → String
```

**Tự dùng cho compiler:** `vir` CLI (`vir run file.vri --dump-ir --dump-asm`).

---

### 3.12. `vir/debug` — Debug & Diagnostics

**Học từ C23:** `<assert.h>`  
**Học từ Python:** `traceback`, `faulthandler`, `pdb`

```
vir/debug/
├── assert.vri         # assert(), assert_eq(), assert_ne()
├── trace.vri          # Stack trace capture
└── fault.vri          # Fault handler (SIGSEGV, etc.)
```

**API tối thiểu:**
```
# assert.vri
hàm assert(cond: bool, msg: String)
hàm assert_eq(a, b, msg: String)
hàm assert_ne(a, b, msg: String)
hàm debug_assert(cond: bool, msg: String)    # chỉ active khi debug build
hàm unreachable(msg: String)                  # always panic

# trace.vri
bản_ghi StackFrame thì
  func_name: String
  file: String
  line: u64
hết

hàm capture_trace() → Vec<StackFrame>
hàm print_trace()
```

**Tự dùng cho compiler:** Assert invariants, capture trace khi codegen fails.

---

## 4. Chi tiết Module — Phase B (Usable)

### 4.1. `vir/map` — HashMap

```
bản_ghi Map thì ... hết

hàm map_new() → Map
hàm map_insert(m: Map, key, value) → Option        # trả về old value
hàm map_get(m: Map, key) → Option
hàm map_remove(m: Map, key) → Option
hàm map_contains(m: Map, key) → bool
hàm map_len(m: Map) → u64
hàm map_keys(m: Map) → Vec
hàm map_values(m: Map) → Vec
hàm map_entries(m: Map) → Vec<(key, value)>
hàm map_iter(m: Map) → Iterator
hàm map_free(m: Map)
```

### 4.2. `vir/set` — HashSet

```
hàm set_new() → Set
hàm set_insert(s: Set, item) → bool
hàm set_remove(s: Set, item) → bool
hàm set_contains(s: Set, item) → bool
hàm set_union(a: Set, b: Set) → Set
hàm set_intersection(a: Set, b: Set) → Set
hàm set_difference(a: Set, b: Set) → Set
```

### 4.3. `vir/json` — JSON

```
liệt_kê JsonValue thì
  Null
  Bool(bool)
  Number(f64)
  Str(String)
  Array(Vec<JsonValue>)
  Object(Map<String, JsonValue>)
hết

hàm json_parse(s: String) → Result<JsonValue, ParseError>
hàm json_stringify(v: JsonValue) → String
hàm json_stringify_pretty(v: JsonValue, indent: u32) → String
```

### 4.4. `vir/regex` — Regular Expressions

```
bản_ghi Regex thì ... hết
bản_ghi Match thì start: u64; end: u64; text: String hết

hàm regex_new(pattern: String) → Result<Regex, ParseError>
hàm regex_is_match(r: Regex, text: String) → bool
hàm regex_find(r: Regex, text: String) → Option<Match>
hàm regex_find_all(r: Regex, text: String) → Vec<Match>
hàm regex_replace(r: Regex, text: String, repl: String) → String
hàm regex_split(r: Regex, text: String) → Vec<String>
```

### 4.5. `vir/fs` — Filesystem

```
hàm fs_read(path: Path) → Result<String, IoError>
hàm fs_read_bytes(path: Path) → Result<Buffer, IoError>
hàm fs_write(path: Path, content: String) → Result<(), IoError>
hàm fs_write_bytes(path: Path, data: Slice) → Result<(), IoError>
hàm fs_append(path: Path, content: String) → Result<(), IoError>
hàm fs_remove(path: Path) → Result<(), IoError>
hàm fs_rename(old: Path, new: Path) → Result<(), IoError>
hàm fs_copy(src: Path, dst: Path) → Result<(), IoError>
hàm fs_create_dir(path: Path) → Result<(), IoError>
hàm fs_create_dir_all(path: Path) → Result<(), IoError>
hàm fs_remove_dir(path: Path) → Result<(), IoError>
hàm fs_list_dir(path: Path) → Result<Vec<DirEntry>, IoError>
hàm fs_metadata(path: Path) → Result<Metadata, IoError>
hàm fs_temp_file() → Result<File, IoError>
hàm fs_temp_dir() → Path
hàm fs_glob(pattern: String) → Vec<Path>
```

### 4.6. `vir/process` — Process Control

```
bản_ghi Command thì
  program: String
  args: Vec<String>
  env: Map<String, String>
  cwd: Option<Path>
hết

bản_ghi Output thì
  status: i32
  stdout: String
  stderr: String
hết

hàm cmd_new(program: String) → Command
hàm cmd_arg(c: Command, arg: String) → Command
hàm cmd_env(c: Command, key: String, val: String) → Command
hàm cmd_cwd(c: Command, dir: Path) → Command
hàm cmd_run(c: Command) → Result<Output, IoError>
hàm cmd_spawn(c: Command) → Result<Process, IoError>
hàm process_wait(p: Process) → Result<i32, IoError>
hàm process_kill(p: Process) → Result<(), IoError>
hàm current_pid() → u64
```

### 4.7. `vir/log` — Logging

```
liệt_kê LogLevel thì
  Trace = 0
  Debug = 1
  Info = 2
  Warn = 3
  Error = 4
hết

hàm log_init(level: LogLevel)
hàm log_trace(msg: String)
hàm log_debug(msg: String)
hàm log_info(msg: String)
hàm log_warn(msg: String)
hàm log_error(msg: String)
```

### 4.8. `vir/test` — Testing Framework

```
hàm test_assert(cond: bool, msg: String)
hàm test_assert_eq(a, b)
hàm test_assert_ne(a, b)
hàm test_assert_err(r: Result)
hàm test_assert_ok(r: Result)
hàm test_fail(msg: String)
hàm test_skip(reason: String)

# Test runner
hàm test_run_all() → TestResult
```

### 4.9. `vir/fmt` — Formatting

```
hàm fmt(template: String, args: ...) → String     # "Hello {0}, you are {1}" 
hàm fmt_pad_left(s: String, width: u64, fill: u32) → String
hàm fmt_pad_right(s: String, width: u64, fill: u32) → String
hàm fmt_hex(n: u64) → String
hàm fmt_bin(n: u64) → String
hàm fmt_oct(n: u64) → String
```

### 4.10. `vir/sort` — Sorting & Searching

```
hàm sort(v: Vec, cmp: hàm)              # in-place, stable sort
hàm sort_by_key(v: Vec, key: hàm)
hàm binary_search(v: Vec, target) → Option<u64>
hàm binary_search_by(v: Vec, cmp: hàm) → Option<u64>
hàm is_sorted(v: Vec, cmp: hàm) → bool
```

### 4.11. `vir/rand` — Random

```
bản_ghi Rng thì seed: u64 hết

hàm rng_new() → Rng                          # seeded from OS
hàm rng_seed(seed: u64) → Rng
hàm rand_u64(rng: Rng) → u64
hàm rand_i64(rng: Rng, lo: i64, hi: i64) → i64
hàm rand_f64(rng: Rng) → f64                 # [0.0, 1.0)
hàm rand_bool(rng: Rng) → bool
hàm rand_shuffle(rng: Rng, v: Vec)
hàm rand_choice(rng: Rng, v: Vec) → Option
```

---

## 5. Phase C — Production (API Skeleton)

| Module | Core Types | Key Functions |
|--------|-----------|---------------|
| **vir/thread** | Thread, Mutex, CondVar, RwLock | thread_spawn, mutex_lock/unlock, condvar_wait/signal |
| **vir/atomic** | AtomicI64, AtomicBool, AtomicPtr | load, store, compare_exchange, fetch_add |
| **vir/async** | Future, Task, EventLoop, Channel | spawn, await, select, channel_send/recv |
| **vir/net** | TcpSocket, UdpSocket, IpAddr | bind, listen, accept, connect, send, recv |
| **vir/http** | Request, Response, Server, Client | http_get, http_post, serve |
| **vir/crypto** | Hash, Hmac, Cipher | sha256, hmac_sign/verify, aes_encrypt/decrypt |
| **vir/tls** | TlsConfig, TlsStream | tls_connect, tls_accept |
| **vir/archive** | ZipReader, ZipWriter, TarReader | zip_open, zip_extract, tar_create |
| **vir/compress** | GzipEncoder, GzipDecoder | gzip_compress, gzip_decompress |
| **vir/config** | Config, TomlParser, IniParser | config_load, config_get, toml_parse |
| **vir/sql** | Database, Statement, Row | db_open, db_execute, db_query |
| **vir/serde** | Serializer, Deserializer | serialize, deserialize, to_bytes, from_bytes |

---

## 6. Phase D — Ecosystem (API Skeleton)

| Module | Core Types | Key Functions |
|--------|-----------|---------------|
| **vir/ast** | ASTNode, ASTVisitor, SourceSpan | ast_parse, ast_walk, ast_transform |
| **vir/token** | TokenKind, Token, TokenStream | tokenize, token_name, keyword_list |
| **vir/parser_kit** | Grammar, Rule, ParseResult | parser_new, parse, expect, many, choice |
| **vir/ffi** | ForeignFunc, DynLib, CType | dlopen, dlsym, call_c, struct_layout |
| **vir/reflect** | TypeInfo, FieldInfo, FuncInfo | type_of, fields_of, methods_of |
| **vir/pkg** | Package, Module, Dependency | pkg_load, pkg_resolve, import |
| **vir/doc** | DocComment, DocPage | doc_extract, doc_render_html, doc_render_md |
| **vir/bench** | Benchmark, BenchResult | bench_run, bench_compare, bench_report |
| **vir/lsp** | LspServer, Diagnostic, Completion | lsp_start, lsp_complete, lsp_diagnose |
| **vir/build** | BuildConfig, Target, Artifact | build, build_release, build_test |
| **vir/profile** | Profiler, Sample, CallGraph | profile_start, profile_stop, profile_report |
| **vir/doctest** | DocTest, DocTestResult | doctest_extract, doctest_run |

---

## 7. Dependency Graph

```
Phase A (mũi tên = phụ thuộc):

vir/core ──────────────────────────────────────────────────┐
   │                                                        │
   ├── vir/error (dùng Option, Result từ core)              │
   │      │                                                 │
   ├── vir/mem (dùng core types + error)                    │
   │      │                                                 │
   ├── vir/str (dùng core + mem + error)                    │
   │      │                                                 │
   ├── vir/io (dùng core + mem + str + error)               │
   │      │                                                 │
   ├── vir/path (dùng core + str)                           │
   │      │                                                 │
   ├── vir/math (dùng core)                                 │
   │                                                        │
   ├── vir/time (dùng core)                                 │
   │                                                        │
   ├── vir/env (dùng core + str + error)                    │
   │                                                        │
   ├── vir/collections (dùng core + mem + error)            │
   │                                                        │
   ├── vir/cli (dùng core + str + collections + error)      │
   │                                                        │
   └── vir/debug (dùng core + str + io)                     │
                                                            │
Phase B:                                                    │
   vir/map (dùng core + mem + collections)                  │
   vir/set (dùng core + mem + map)                          │
   vir/json (dùng core + str + map + collections + error)   │
   vir/regex (dùng core + str + mem + error)                │
   vir/fs (dùng core + path + io + error)                   │
   vir/process (dùng core + str + io + env + error)         │
   vir/log (dùng core + str + io + time)                    │
   vir/test (dùng core + str + io + debug + error)          │
   vir/fmt (dùng core + str + mem)                          │
   vir/sort (dùng core + collections)                       │
   vir/rand (dùng core)                                     │
```

---

## 8. Build Order (lần lượt implement)

### Phase A — thứ tự build:

```
 ①  vir/core/types       → kiểu cơ bản, limits
 ②  vir/core/option      → Option<T>
 ③  vir/core/result      → Result<T,E>
 ④  vir/core/ops         → checked arithmetic
 ⑤  vir/core/bits        → bit manipulation
 ⑥  vir/error            → Error trait + common errors
 ⑦  vir/mem/alloc        → malloc/free wrapper
 ⑧  vir/mem/slice        → borrowed view
 ⑨  vir/mem/buffer       → growable byte buffer
 ⑩  vir/mem/copy         → memcpy/memset
 ⑪  vir/str/string       → immutable UTF-8 string
 ⑫  vir/str/char         → character classification
 ⑬  vir/str/builder      → mutable string builder  
 ⑭  vir/str/search       → find, contains, split
 ⑮  vir/collections/vec  → dynamic array
 ⑯  vir/io/traits        → Reader/Writer interfaces
 ⑰  vir/io/stdio         → print/println/read_line
 ⑱  vir/io/file          → file open/read/write/close
 ⑲  vir/io/format        → format strings
 ⑳  vir/path             → path manipulation
 ㉑  vir/math             → basic + float + integer math
 ㉒  vir/time             → instant, duration, sleep
 ㉓  vir/env              → env vars, platform, exit
 ㉔  vir/debug            → assert, stack trace
 ㉕  vir/cli              → argument parser
```

---

## 9. Thống kê ước tính

| Phase | Modules | LOC ước tính | Thời gian |
|-------|---------|-------------|-----------|
| A — Bootstrap | 12 modules, ~25 files | ~4,000–5,000 | 4-6 tuần |
| B — Usable | 12 modules, ~15 files | ~3,000–4,000 | 3-4 tuần |
| C — Production | 12 modules, ~20 files | ~5,000–7,000 | 6-8 tuần |
| D — Ecosystem | 12 modules, ~20 files | ~5,000–8,000 | 8-12 tuần |
| **Tổng** | **~48 modules, ~80 files** | **~17,000–24,000** | **~21-30 tuần** |

---

## 10. Tiêu chí Hoàn thành mỗi Module

Mỗi module phải đạt:

- [ ] **API spec** — file `.vri` với đầy đủ function signatures
- [ ] **Implementation** — code hoạt động
- [ ] **Tests** — ≥80% branch coverage
- [ ] **Docs** — doc comment cho mỗi public function
- [ ] **Examples** — ≥1 example sử dụng
- [ ] **Self-hosting check** — nếu compiler cần module này, phải verify
- [ ] **Cross-platform** — macOS ARM64 + Linux x86_64 đều pass

---

## 11. So sánh với Ngôn ngữ Tương đương

| Feature | Vir (target) | Rust (stdlib) | Go (stdlib) | Zig (stdlib) |
|---------|-------------|---------------|-------------|-------------|
| String | UTF-8, immutable | UTF-8, owned/borrowed | UTF-8, slice | UTF-8, slice |
| Error | Result<T,E> | Result<T,E> | error interface | error union |
| Memory | Manual + arena | Ownership + borrow | GC | Allocator param |
| Collections | Vec, Map, Set | Vec, HashMap, etc. | slice, map | ArrayList, HashMap |
| Async | Future + EventLoop | async/await (tokio) | goroutines | async/await |
| Networking | vir/net + vir/http | (ecosystem) | net/http (builtin) | (ecosystem) |
| Testing | vir/test | #[test] | testing pkg | test runner |
| Package | vir/pkg | cargo | go modules | build.zig |

---

## Phụ lục A: Tên tiếng Việt cho API

Vir hỗ trợ đa ngôn ngữ tự nhiên. Mỗi stdlib function có alias tiếng Việt:

| English (chuẩn) | Tiếng Việt | Module |
|-----------------|-----------|--------|
| `vec_new()` | `tạo_mảng()` | collections |
| `vec_push()` | `thêm()` | collections |
| `vec_pop()` | `lấy_cuối()` | collections |
| `str_len()` | `độ_dài()` | str |
| `str_find()` | `tìm()` | str |
| `file_open()` | `mở_tệp()` | io |
| `file_read()` | `đọc_tệp()` | io |
| `file_write()` | `ghi_tệp()` | io |
| `print()` | `in_ra()` | io |
| `println()` | `in_dòng()` | io |
| `assert()` | `kiểm_tra()` | debug |
| `panic()` | `hoảng()` | env |
| `exit()` | `thoát()` | env |
| `now()` | `bây_giờ()` | time |
| `sleep()` | `ngủ()` | time |
| `path_join()` | `nối_đường()` | path |
| `map_insert()` | `thêm_cặp()` | map |
| `sort()` | `sắp_xếp()` | sort |
| `format()` | `định_dạng()` | fmt |
| `alloc()` | `cấp()` | mem |
| `free()` | `giải()` | mem |

---

## Phụ lục B: Liên kết Self-Hosting

Bảng mapping stdlib modules sang compiler components cần dùng:

| Compiler Module | Stdlib Dependencies |
|----------------|-------------------|
| Lexer (lexer.vri) | core, str, mem, collections/vec, error |
| Parser (parser.vri) | core, str, mem, collections/vec, error, debug |
| IR Lower (ir_lower.vri) | core, str, mem, collections/vec+map, error |
| Codegen (codegen.vri) | core, mem/buffer, io, env/platform, error, math/bits |
| VM (vm.vri) | core, mem, io, collections/vec, error |
| Bridge (bridge.vri) | core, mem, env, error |
| Patcher (patcher.vri) | core, mem/buffer, error |
| Signer (signer.vri) | core, mem, str, crypto.hash (Phase C) |
| CLI (main.vri) | core, str, io, cli, env, path, error |

**Kết luận:** Phase A stdlib đủ để viết lại 80% compiler. Chỉ Signer cần chờ Phase C (crypto).
