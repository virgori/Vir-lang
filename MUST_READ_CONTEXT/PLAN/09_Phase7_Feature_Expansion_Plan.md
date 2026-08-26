# Vir — Phase 7: Feature Expansion Master Plan

*Created: 2026-04-11 | Author: virc team | Status: PLANNING*
*Prerequisite: Phase 6 complete (47/47 tests, optimization passes, QOp reconciliation)*

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Trạng thái hiện tại](#trạng-thái-hiện-tại)
- [Giai đoạn 7A — Hoàn thiện tính năng đã parse](#giai-đoạn-7a--hoàn-thiện-tính-năng-đã-parse)
- [Giai đoạn 7B — Tính năng mới](#giai-đoạn-7b--tính-năng-mới)
- [Giai đoạn 7C — Hệ thống Module](#giai-đoạn-7c--hệ-thống-module)
- [Thứ tự triển khai](#thứ-tự-triển-khai)
- [Test Matrix](#test-matrix)
- [Rủi ro & Giải pháp](#rủi-ro--giải-pháp)

---

## Tổng quan

Phase 7 mở rộng Vir từ một ngôn ngữ biên dịch cơ bản (47 test, integer/string/array/entity/enum/HOF) thành một ngôn ngữ hệ thống đầy đủ với 13 tính năng mới, chia thành 3 giai đoạn:

| Giai đoạn | Tính năng | Số task | Ưu tiên |
|-----------|-----------|---------|---------|
| **7A** | Hoàn thiện 6 tính năng đã parse (UFCS, packed, ensure/revert, throw, interpolation) | 12 | **Cao** |
| **7B** | 5 tính năng mới (ref params, FFI @bind, register, compile-time exec, throw/error model) | 15 | **Cao** |
| **7C** | Hệ thống Module & kiểu dữ liệu (include/import/get, primitive types, @entry) | 10 | **Trung bình** |

**Tổng: ~37 task, ước lượng ~6 sprint (mỗi sprint = 1 session)**

---

## Trạng thái hiện tại

### Đã triển khai (Phase 6, verified ✅)

| Tính năng | Lexer | Parser | IR Lower | Codegen | Test | Kết quả |
|-----------|-------|--------|----------|---------|------|---------|
| UFCS (`x.func()`) | ✅ | ✅ AstType::MethodCall | ✅ rewrite→CallFunc | ✅ | test_ufcs.vri | ✅ **20, 15, 37** |
| UFCS + `this` keyword | ✅ | ✅ | ✅ | ✅ | test_this.vri | ⚠️ **21, 7, 0** (literal.method() trả 0 thay vì 10) |
| `packed entity` | ✅ PackedKw=161 | ✅ PackedDef=63 | ⚠️ treated as EntityDef | ⚠️ | test_packed.vri | ❌ **Hangs** (infinite loop in IR/codegen) |
| `ensure` block | ✅ EnsureKw=163 | ✅ EnsureBlock=59 | ⚠️ skipped in lower_stmt | ❌ | test_ensure.vri | ❌ **Chưa test** |
| `throw` statement | ✅ ThrowKw=165 | ✅ ThrowStmt=58 | ✅ →QOp::Trap | ✅ BRK #1 | test_throw.vri | ⚠️ **Chưa verify** |
| String interpolation | ✅ InterpStart/End | ✅ InterpExpr=61 | ✅ StrCat chain | ✅ | test_interp.vri | ⚠️ **Chưa verify** |
| `ref` parameters | — | ✅ RefParam=66 | ⚠️ parsed, stub | ❌ | — | ❌ Chưa triển khai |
| FFI `@bind(c)` | — | ✅ BindAttr | ⚠️ logs, skips | ❌ | — | ❌ Chưa triển khai |
| `revert` block | ✅ RevertKw=164 | ✅ RevertBlock=60 | ⚠️ | ❌ | — | ❌ Chưa triển khai |

### Bug đã phát hiện

1. **`15.clamp(0, 10)` → 0 thay vì 10**: Literal integer UFCS call (`15.clamp(...)`) không truyền đúng literal làm `this`. Parser có thể không nhận diện integer-literal dot-call.
2. **`packed entity` hangs**: Compiler bị loop vô hạn khi xử lý `packed entity`. IR lowering hoặc codegen đang lặp.
3. **`ensure` block bị skip**: `lower_stmt` ghi comment "handled in lower_func_def" nhưng `lower_func_def` có thể chưa thực sự emit epilogue code.

---

## Giai đoạn 7A — Hoàn thiện tính năng đã parse

### 7A.1 — UFCS hoàn chỉnh (`this` keyword)

**Mục tiêu:** `x.method(args)` ≡ `method(x, args)` cho mọi trường hợp.

**Cú pháp:**
```vir
// Bất kỳ hàm nào có tham số đầu tiên tên `this` đều callable qua UFCS
func scale(this, n):
    out this * n
end

var x = 7
var a = x.scale(3)         // → scale(7, 3) → 21 ✅
var b = 15.clamp(0, 10)    // → clamp(15, 0, 10) → 10 (hiện tại: ❌ 0)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| A1.1 | Fix literal UFCS | parser.vri | Khi gặp `<int_literal>.ident(`, parse thành MethodCall với receiver = LiteralInt |
| A1.2 | Fix entity UFCS | parser.vri + ir_optimizer.vri | `user.getName()` — phân biệt field access vs method call trên entity |
| A1.3 | Test UFCS chaining | test_ufcs_chain.vri | `x.double().add_n(3)` — chaining nhiều UFCS calls |
| A1.4 | Add to test suite | run_tests.sh | Thêm test_ufcs, test_this vào run_tests.sh |

**Lưu ý kỹ thuật:**
- Parser hiện tại: khi gặp `Ident "." Ident "("`, tạo `MethodCall { receiver, method, args }`.
- IR lowering: rewrite `MethodCall` → `CallFunc(method, [receiver] + args)`.
- Bug: `15.clamp(...)` — parser có thể đang parse `15` rồi gặp `.` và nghĩ đó là truy cập field thay vì method call trên literal.

---

### 7A.2 — `packed entity` (cấu trúc gọn)

**Mục tiêu:** `packed entity` đảm bảo các field được sắp xếp liên tiếp, không padding, phục vụ FFI và memory-mapped I/O.

**Cú pháp:**
```vir
packed entity Vec2:
    x: int
    y: int
end

// Nội bộ: sizeof(Vec2) = sizeof(int) * 2, không alignment padding
// Truy cập field: offset = field_index * field_size (thay vì arena-based)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| A2.1 | Fix packed hang | ir_optimizer.vri | Debug infinite loop khi lower PackedDef. Có thể là lower_stmt không có case cho PackedDef=63 → fallthrough loop |
| A2.2 | Implement packed layout | ir_optimizer.vri | PackedDef: tính toán flat offset cho mỗi field. `field_offset = Σ sizeof(prev_fields)`, không padding |
| A2.3 | Packed field codegen | codegen.vri | Truy cập field packed: `base_ptr + field_offset` thay vì arena-based slot access |
| A2.4 | Test packed | test_packed.vri | Verify: `u.x=3, u.y=4, dot=11`. Thêm vào run_tests.sh |

**Khác biệt packed vs entity thường:**

| | `entity` (hiện tại) | `packed entity` |
|-|------|------|
| Layout | Arena-allocated, field = slot index | Flat contiguous, field = byte offset |
| Alignment | Platform-dependent | None (1-byte aligned) |
| Use case | General OOP | FFI struct, hardware register, mmap |
| Sizeof | Runtime (arena header + slots) | Compile-time (`Σ field_sizes`) |

---

### 7A.3 — `ensure` và `revert` (Scope Guards)

**Mục tiêu:**
- `ensure` = code chạy **luôn luôn** khi thoát function (giống `defer`/`scope(exit)` trong D/Go)
- `revert` = code chạy **chỉ khi** function gặp lỗi/throw (giống `scope(failure)`)

**Cú pháp:**
```vir
func open_file(path):
    var fd = __syscall(5, path, 0, 0)    // open
ensure:
    __syscall(6, fd, 0, 0)                // close — luôn chạy
revert:
    print_str("Failed to process file\n") // chỉ chạy nếu throw
end

func work:
    print 42
ensure:
    print 99      // Expected output: 42 rồi 99
end
```

**Cơ chế nội bộ:**

```
lower_func_def("work"):
  1. Emit body code (print 42)
  2. Jump to ensure_label          ← normal exit
  3. [nếu có revert]:
       revert_label:
         emit revert code
         jump to ensure_label
  4. ensure_label:
       emit ensure code
  5. Emit function epilogue (RET)
  
  throw/panic handler:
    jump to revert_label (nếu có) hoặc ensure_label (nếu không có revert)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| A3.1 | Wire ensure in IR | ir_optimizer.vri | `lower_func_def`: sau khi emit body, emit ensure block trước RET. Lưu ensure/revert AST nodes khi parse FuncDef children |
| A3.2 | Wire revert in IR | ir_optimizer.vri | Emit revert block chỉ khi throw/trap xảy ra. Cần mechanism để jump từ throw → revert → ensure → RET |
| A3.3 | Throw → revert linkage | ir_optimizer.vri + codegen.vri | QOp::Trap hiện tại emit BRK #1 (crash). Thay bằng: jump to revert_label (nếu có) → ensure_label → RET |
| A3.4 | Test ensure + revert | test_ensure.vri, test_revert.vri | ensure: `42, 99`. revert: `42, error_msg, 99` (revert runs only on throw) |

**Lưu ý:** Ensure/revert chỉ áp dụng **trong cùng function**. Không phải exception propagation (chưa có stack unwinding ở Phase 7).

---

### 7A.4 — `throw` statement

**Mục tiêu:** `throw <expr>` dừng execution flow, jump đến revert/ensure nếu có, hoặc trap nếu không.

**Cú pháp:**
```vir
func safe_div(a, b):
    if b == 0:
        throw 1          // error code 1 = division by zero
    end
    out a / b
end

// Không có revert → throw = BRK #1 (process crash)
// Có revert      → throw = jump to revert block, set error register
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| A4.1 | Throw with error value | ir_optimizer.vri | `throw <expr>`: lower expr → store vào error register (dedicated vreg), jump to revert_label |
| A4.2 | Throw without revert | codegen.vri | Nếu function không có revert/ensure: emit `BRK #1` (hiện tại) |
| A4.3 | Throw with revert | codegen.vri | Nếu function có revert: emit `B revert_label` thay vì BRK |
| A4.4 | Test throw | test_throw.vri, test_throw_revert.vri | `safe_div(10,2)=5, safe_div(21,7)=3`. Throw+revert: error message printed |

---

### 7A.5 — Nội suy chuỗi (String Interpolation)

**Mục tiêu:** `"Hello $name"` tự động nối chuỗi.

**Cú pháp:**
```vir
var name = "World"
var age = 25

// Biến đơn
print_str("Hello $name")           // → "Hello World"

// Thuộc tính entity
print_str("User: $user.name")      // → "User: Geng"

// Biểu thức
print_str("VAT: $(price * 0.1)")   // → "VAT: 10.0"

// Escape
print_str("Price: $$100")          // → "Price: $100"
```

**Cơ chế nội bộ (đã triển khai phần lớn):**
```
Lexer:  "Hello $name!" → [InterpStart "Hello "] [Ident "name"] [InterpEnd "!"]
Parser: → InterpExpr { parts: [StrLit "Hello ", VarRef "name", StrLit "!"] }
IR:     → StrCat(StrCat("Hello ", i_to_str(name)), "!")    ← chain of StrCat
```

| Loại nội suy | Cú pháp | Lexer token | IR lowering |
|-------------|---------|-------------|-------------|
| Biến đơn | `$var` | `[InterpStart] [Ident] [InterpEnd]` | `StrCat(prefix, var_or_i_to_str(var))` |
| Thuộc tính | `$obj.prop` | `[InterpStart] [Ident.Ident] [InterpEnd]` | `StrCat(prefix, i_to_str(field_access))` |
| Biểu thức | `$(expr)` | `[InterpStart] [LParen...RParen] [InterpEnd]` | `StrCat(prefix, i_to_str(eval(expr)))` |
| Escape | `$$` | `[InterpStart "$"]` | `StrCat(prefix, "$")` |

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| A5.1 | Verify basic interp | test_interp.vri | Test: `"Hello $name"` → `Hello World` |
| A5.2 | Add property interp | lexer.vri + parser.vri | `$user.name` — lexer emit `Ident "user"` + `Dot` + `Ident "name"` inside interp context |
| A5.3 | Add expression interp | lexer.vri + parser.vri | `$(expr)` — khi gặp `$(`, parse full expression đến `)` |
| A5.4 | Add $$ escape | lexer.vri | `$$` → literal `$` character |
| A5.5 | Auto int→str in interp | ir_optimizer.vri | Nếu interp var là int, tự động wrap trong `i_to_str()` |
| A5.6 | Test full interp | test_interp_full.vri | Tất cả 4 loại: `$var`, `$obj.prop`, `$(expr)`, `$$` |

---

## Giai đoạn 7B — Tính năng mới

### 7B.1 — `ref` Parameters (Tham chiếu rõ ràng)

**Mục tiêu:** Phân biệt rõ pass-by-value vs pass-by-reference.

**Hiện tại:** Mọi tham số đều copy giá trị (integer = copy value, entity = copy pointer). Người dùng không biết họ đang sửa bản gốc hay bản sao.

**Cú pháp:**
```vir
// Pass by value (mặc định) — copy giá trị
func double(x):
    out x * 2
end

// Pass by reference — sửa trực tiếp bản gốc
func increment(in(ref x)):
    x = x + 1
end

func swap(in(ref a), in(ref b)):
    var tmp = a
    a = b
    b = tmp
end

func main:
    var n = 10
    increment(n)
    print n          // → 11 (bản gốc đã bị sửa)
    
    var x = 1
    var y = 2
    swap(x, y)
    print x          // → 2
    print y          // → 1
end
```

**Cơ chế nội bộ:**
```
// ref parameter: truyền địa chỉ stack slot thay vì giá trị
// caller: emit LoadAddr(x_slot) → pass addr as argument
// callee: dereference addr để đọc/ghi giá trị gốc

QOp::LoadAddr       vreg, slot    // LEA: load address of stack slot
QOp::DerefLoad      dst, src      // LDR [src] → dst (pointer dereference)
QOp::DerefStore     dst, src      // STR src → [dst] (pointer write-back)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| B1.1 | Parse `in(ref x)` | parser.vri | Nhận diện `in(ref ident)` → RefParam node với is_ref=true |
| B1.2 | Add QOps | ir_optimizer.vri | 3 QOp mới: LoadAddr, DerefLoad, DerefStore |
| B1.3 | IR lower ref params | ir_optimizer.vri | Caller: emit LoadAddr cho ref args. Callee: DerefLoad/DerefStore thay vì direct vreg access |
| B1.4 | ARM64 codegen | codegen.vri | LoadAddr→`ADD Xd, SP, #offset`. DerefLoad→`LDR Xd, [Xs]`. DerefStore→`STR Xs, [Xd]` |
| B1.5 | x86-64 codegen | codegen.vri | LoadAddr→`LEA rdi, [rsp+offset]`. DerefLoad→`MOV rdi, [rsi]`. DerefStore→`MOV [rdi], rsi` |
| B1.6 | Test ref params | test_ref.vri | `increment(n)` → n=11, `swap(x,y)` → x=2,y=1 |

---

### 7B.2 — FFI `@bind(c)` (Foreign Function Interface)

**Mục tiêu:** Gọi hàm C/thư viện ngoài từ Vir.

**Cú pháp:**
```vir
// Khai báo hàm C
@bind(c)
func puts(s: ptr): int

@bind(c)
func malloc(size: u64): ptr

@bind(c)
func free(p: ptr)

// Sử dụng
func main:
    var msg = "Hello from Vir via FFI!\n"
    puts(msg)
    
    var buf = malloc(1024)
    // ... use buf ...
    free(buf)
end
```

**Cơ chế nội bộ:**
```
// @bind(c) func → external symbol, không có body
// Linker:
//   Mach-O: thêm vào __DATA.__la_symbol_ptr + stub trong __TEXT.__stubs
//   ELF: thêm vào .dynsym + .plt
// Calling convention: SysV AMD64 ABI / AAPCS64
//   args: X0-X7 (ARM64), rdi/rsi/rdx/rcx/r8/r9 (x86-64)
//   return: X0 (ARM64), rax (x86-64)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| B2.1 | Parse @bind(c) | parser.vri | `@bind(c) func name(params): ret_type` → BindAttr + FuncDef (no body) |
| B2.2 | External symbol table | ir_optimizer.vri | Ghi nhận external symbols, không emit body code. Chỉ emit call-site linkage |
| B2.3 | Mach-O dynamic linking | macho.vri | Thêm LC_LOAD_DYLIB (/usr/lib/libSystem.B.dylib), __la_symbol_ptr, __stubs |
| B2.4 | ELF dynamic linking | elf.vri | Thêm .dynsym, .plt, .got, DT_NEEDED |
| B2.5 | Calling convention | codegen.vri | Map Vir args → C ABI registers. Handle return value |
| B2.6 | Test FFI | test_ffi_bind.vri | Gọi `puts()` từ libc → in chuỗi ra stdout |

**Lưu ý quan trọng:**
- FFI bắt buộc có type annotations vì C ABI cần biết kích thước tham số
- Hiện tại Vir binary là static (no libc). FFI sẽ require dynamic linking → thay đổi lớn trong macho.vri/elf.vri
- Phase đầu: chỉ hỗ trợ `@bind(c)` cho libc functions (puts, malloc, free, printf)
- Phase sau: hỗ trợ `@bind(c, "libcustom.so")` cho thư viện tùy chỉnh

---

### 7B.3 — `register` Keyword (Bit-level Hardware Struct)

**Mục tiêu:** Định nghĩa cấu trúc ánh xạ trực tiếp thanh ghi phần cứng, truy cập bit-level.

**Cú pháp:**
```vir
register UART_SR: u32
    PE:     0       // bit 0 — Parity Error
    FE:     1       // bit 1 — Framing Error
    NF:     2       // bit 2 — Noise Flag
    ORE:    3       // bit 3 — Overrun Error
    IDLE:   4       // bit 4 — IDLE line detected
    RXNE:   5       // bit 5 — Read Data Register Not Empty
    TC:     6       // bit 6 — Transmission Complete
    TXE:    7       // bit 7 — Transmit Data Register Empty
end

register GPIO_MODER: u32
    MODE0:  0..1    // bits 0-1 — Port 0 mode (2 bits)
    MODE1:  2..3    // bits 2-3 — Port 1 mode
    // ...
end

// Sử dụng
func uart_init:
    var sr = volatile_read(0x40011000) as UART_SR
    if sr.RXNE:
        var data = volatile_read(0x40011004)
        // process received byte
    end
    
    // Set bit
    sr.TXE = 1
    volatile_write(0x40011000, sr as u32)
end
```

**Cơ chế nội bộ:**
```
// register = packed bitmask struct
// Single bit field:  (value >> bit_pos) & 1          (read)
//                    (value & ~(1 << bit_pos)) | (new_val << bit_pos)  (write)
// Multi-bit field:   (value >> lo) & ((1 << (hi-lo+1)) - 1)           (read)
//                    (value & ~(mask << lo)) | ((new_val & mask) << lo) (write)
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| B3.1 | Add `register` keyword | lexer.vri | RegisterKw token |
| B3.2 | Parse register def | parser.vri | `register Name: type ... end` → RegisterDef { name, base_type, fields: [(name, bit_range)] } |
| B3.3 | IR lower register access | ir_optimizer.vri | `reg.FIELD` → `(reg >> lo) & mask`. `reg.FIELD = val` → `(reg & ~(mask << lo)) | (val << lo)` |
| B3.4 | ARM64 codegen | codegen.vri | UBFX/BFI instructions cho bit extract/insert (native ARM64 bitfield) |
| B3.5 | volatile_read/write intrinsics | ir_optimizer.vri + codegen.vri | `volatile_read(addr)` → LDR với memory barrier. `volatile_write(addr, val)` → STR với barrier |
| B3.6 | Test register | test_register.vri | Tạo register, set bit, read bit, verify bitmask |

---

### 7B.4 — Compile-time Execution (`comptime`)

**Mục tiêu:** Chạy code tại thời điểm biên dịch, kết quả được "inline" vào binary.

**Cú pháp:**
```vir
// Hằng số tính tại compile-time
const TABLE_SIZE = comptime { 1 << 16 }       // → 65536

// Hàm chạy tại compile-time
comptime func factorial(n):
    if n <= 1:
        out 1
    end
    out n * factorial(n - 1)
end

const FACT_10 = comptime { factorial(10) }     // → 3628800

// Compile-time assertion
comptime {
    if TABLE_SIZE > 1000000:
        throw "TABLE_SIZE too large!"           // compile error, not runtime
    end
}
```

**Cơ chế nội bộ:**
```
Compiler pipeline:
  1. Parse → AST (bình thường)
  2. Identify comptime blocks/functions
  3. Evaluate comptime expressions using IR interpreter (reuse VM logic)
  4. Replace comptime AST nodes with resulting LiteralInt/LiteralStr
  5. Continue normal IR lowering + codegen
```

**Interpreter cho comptime:**
- Tái sử dụng C VM interpreter cho phase đầu
- Chỉ hỗ trợ: integer arithmetic, if/else, function calls, recursion
- Không hỗ trợ: I/O, array, entity, string (Phase 7 giới hạn)
- Lỗi comptime → compile error (không phải runtime crash)

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| B4.1 | Add `comptime` keyword | lexer.vri | ComptimeKw token |
| B4.2 | Parse comptime block | parser.vri | `comptime { expr }` → ComptimeBlock { body } |
| B4.3 | Parse comptime func | parser.vri | `comptime func name(...): ... end` → ComptimeFunc |
| B4.4 | AST evaluator | ir_optimizer.vri | `eval_comptime(ast) → i64`: recursive AST interpreter cho arithmetic + control flow |
| B4.5 | Comptime const folding | ir_optimizer.vri | `const X = comptime { ... }` → replace X with literal everywhere |
| B4.6 | Comptime error | ir_optimizer.vri | `throw` inside comptime → compile error message |
| B4.7 | Test comptime | test_comptime.vri | `const F10 = comptime { factorial(10) }; print F10` → 3628800 |

---

### 7B.5 — Error Model hoàn chỉnh (throw + ensure + revert)

**Mục tiêu:** Kết hợp throw, ensure, revert thành error handling model thống nhất.

**Control flow diagram:**
```
func example:
    // ... body code ...
    throw 42                    // ─── jump to revert (if exists)
    // ... more body ...        //     │
ensure:                         //     │
    // always runs ◄────────────//─────┤── normal exit also jumps here
    cleanup()                   //     │     ensure always executes
revert:                         //     │
    // runs ONLY on throw ◄─────//─────┘
    handle_error()              //
end                             // ── function returns
```

**Execution order:**
1. **Normal exit** (no throw): body → ensure → RET
2. **Throw exit**: body → throw → revert (if exists) → ensure → RET (or BRK if no ensure)

**Dedicated registers:**
- `X19` (callee-saved) = error code register. 0 = no error, nonzero = thrown value.
- Trước khi enter function: `X19 = 0`
- `throw <expr>`: `X19 = expr; B revert_label`
- `revert` block can read `X19` để biết error code

**Task:** (đã liệt kê trong 7A.3 + 7A.4, task này là tích hợp)

| # | Task | File | Mô tả |
|---|------|------|--------|
| B5.1 | Unified error flow | ir_optimizer.vri | Implement control flow graph: Body → [throw?] → Revert → Ensure → RET |
| B5.2 | Error register protocol | codegen.vri | X19 = error code, save/restore across calls |
| B5.3 | Test full error model | test_error_model.vri | throw + revert + ensure combined |

---

## Giai đoạn 7C — Hệ thống Module & Kiểu dữ liệu

### 7C.1 — Module System (include / import / get)

**Mục tiêu:** Tổ chức mã nguồn theo cơ chế **Ánh xạ Thư mục**.

**Cú pháp:**

```vir
// A. Nạp tầng vật lý
include net.http;                    // → tìm net/http.vri, namespace = http
include net.http as web;             // → namespace = web

// B. Nhặt tài nguyên
import get from net.http;            // → gọi trực tiếp get() không cần prefix
import get from net.http as fetch;   // → gọi bằng fetch()
get MAX_RETRY from net.config;       // → dùng MAX_RETRY trực tiếp

// C. Sử dụng
func main:
    var resp = http.get("https://...")   // qualified call
    var resp2 = fetch("https://...")     // aliased import
    print MAX_RETRY                      // imported constant
end
```

**Dependency Graph protocol:**
```
1. Check Cache: module path đã load chưa?
2. Circular Check: nếu module đang Parsing → error "Circular Dependency"
3. Mapping: A.B.C → A/B/C.vri (tìm từ project root)
4. Registration: thêm exported symbols vào Symbol Table
```

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| C1.1 | include statement (virc) | parser.vri + ir_optimizer.vri | Parse `include path.to.file [as alias]`. Tìm + parse file target. Register namespace |
| C1.2 | import statement | parser.vri + ir_optimizer.vri | Parse `import func from path [as alias]`. Resolve function trong target module |
| C1.3 | get statement | parser.vri + ir_optimizer.vri | Parse `get var from path [as alias]`. Resolve variable/constant |
| C1.4 | Symbol table per module | ir_optimizer.vri | Mỗi module có riêng symbol table. Qualified access: `http.get()` → lookup "get" in module "http" |
| C1.5 | Circular dependency detection | ir_optimizer.vri | Module states: NotLoaded → Parsing → Parsed. Detect cycle |
| C1.6 | Test modules | test_module/ | Multi-file test: main.vri includes math.vri, calls math.add() |

---

### 7C.2 — Primitive Types

**Mục tiêu:** Hỗ trợ kiểu dữ liệu tường minh kích thước bit cho lập trình hệ thống.

| Nhóm | Kiểu | Kích thước | Mô tả |
|------|------|-----------|--------|
| Signed int | `i8`, `i16`, `i32`, `i64` | 1, 2, 4, 8 bytes | 2's complement |
| Unsigned int | `u8`, `u16`, `u32`, `u64` | 1, 2, 4, 8 bytes | Thanh ghi, bộ đếm |
| Flexible int | `int`, `uint` | Platform word size | 8 bytes trên 64-bit |
| Pointer | `ptr` | Platform word size | Raw pointer, FFI compatible |
| Boolean | `bool` | 1 byte | `true` / `false` |

**Hiện tại:** Mọi giá trị là 64-bit integer. Type annotations không ảnh hưởng codegen.

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| C2.1 | Type annotation parsing | parser.vri | `var x: i32 = 10`, `func add(a: i32, b: i32): i32` |
| C2.2 | Type table | ir_optimizer.vri | Lưu trữ type info cho mỗi variable/function. Dùng cho packed layout + FFI |
| C2.3 | Narrow codegen | codegen.vri | i8/u8 → LDRB/STRB, i16/u16 → LDRH/STRH, i32/u32 → LDR W-reg, i64/u64 → LDR X-reg |
| C2.4 | Type checking (basic) | ir_optimizer.vri | Warning khi assign i64 vào i8 (truncation). Error khi assign ptr vào int (safety) |

---

### 7C.3 — @entry Attribute

**Mục tiêu:** Cho phép tùy chọn entry point cho bare-metal/kernel development.

```vir
@entry
func kmain:
    // Kernel initialization code
    // No libc, no allocator, no strings — just raw hardware
end
```

**Cơ chế:** Compiler export symbol `@entry` func thành `_start` (hoặc tên tùy chỉnh).

**Task:**

| # | Task | File | Mô tả |
|---|------|------|--------|
| C3.1 | Parse @entry | parser.vri | Khi gặp `@entry` trước func def, đánh dấu function là entry point |
| C3.2 | Custom _start | main.vri | Nếu có @entry func, dùng nó thay vì tìm `main` |

---

## Thứ tự triển khai (Dependency-ordered)

```
Sprint 1 (7A — Fix & Verify):
  ├── A1.1  Fix literal UFCS bug (15.clamp → 10)
  ├── A2.1  Fix packed entity hang
  ├── A4.1  Verify throw works
  └── A5.1  Verify string interpolation works

Sprint 2 (7A — Ensure/Revert):
  ├── A3.1  Wire ensure in IR (emit before RET)
  ├── A3.2  Wire revert in IR 
  ├── A3.3  Throw → revert linkage
  ├── A4.2  Throw without revert → BRK
  └── A4.3  Throw with revert → jump

Sprint 3 (7B.1 — Ref params):
  ├── B1.1  Parse in(ref x)
  ├── B1.2  Add LoadAddr/DerefLoad/DerefStore QOps
  ├── B1.3  IR lower ref params
  ├── B1.4  ARM64 codegen
  └── B1.6  Test

Sprint 4 (7B.3 + 7B.4 — Register + Comptime):
  ├── B3.1  register keyword + parser
  ├── B3.3  Bitfield IR lowering
  ├── B4.1  comptime keyword + parser
  ├── B4.4  AST evaluator
  └── B4.7  Tests

Sprint 5 (7B.2 — FFI @bind):
  ├── B2.1  Parse @bind(c)
  ├── B2.2  External symbol table
  ├── B2.3  Mach-O dynamic linking (LC_LOAD_DYLIB, __stubs)
  ├── B2.5  C calling convention mapping
  └── B2.6  Test (puts from libc)

Sprint 6 (7C — Modules & Types):
  ├── C1.1  include statement
  ├── C1.2  import/get
  ├── C1.5  Circular dependency detection
  ├── C2.1  Type annotations
  └── C3.1  @entry attribute
```

**Phụ thuộc giữa các feature:**

```
                    ┌──────────────┐
                    │  7A.1 UFCS   │  (đã hoạt động, chỉ fix bug)
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌──────────┐   ┌──────────────┐
   │ 7A.3 ensure │  │ 7A.4     │   │ 7A.5 interp  │
   │ + revert    │◄─┤ throw    │   │ (string)     │
   └──────┬──────┘  └──────────┘   └──────────────┘
          │
          ▼
   ┌─────────────┐   ┌──────────────┐
   │ 7B.5 Error  │   │ 7A.2 packed  │
   │ Model       │   │ entity       │
   └─────────────┘   └──────┬───────┘
                             │
          ┌──────────────────┼───────────────────┐
          ▼                  ▼                   ▼
   ┌─────────────┐  ┌──────────────┐   ┌──────────────┐
   │ 7B.1 ref    │  │ 7B.3         │   │ 7B.2 FFI     │
   │ params      │  │ register     │   │ @bind(c)     │
   └─────────────┘  └──────────────┘   └──────┬───────┘
                                               │
                                        ┌──────┴───────┐
                                        │ 7C Modules   │
                                        │ Types @entry │
                                        └──────────────┘
```

---

## Test Matrix (Target: 47 existing + 15 new = 62 tests)

| # | Test file | Feature | Expected output | Sprint |
|---|-----------|---------|-----------------|--------|
| 48 | test_ufcs.vri | UFCS basic | 20, 15, 37 | 1 |
| 49 | test_this.vri | UFCS + this | 21, 7, **10** (fixed) | 1 |
| 50 | test_ufcs_chain.vri | UFCS chaining | `x.double().add_n(3)` = 23 | 1 |
| 51 | test_packed.vri | packed entity | 3, 4, 11 | 1 |
| 52 | test_throw.vri | throw (no revert) | 5, 3 | 1 |
| 53 | test_interp.vri | string interpolation | Hello World, Vir is great, Escaped $dollar | 1 |
| 54 | test_ensure.vri | ensure block | 42, 99 | 2 |
| 55 | test_revert.vri | revert block | revert on throw | 2 |
| 56 | test_error_model.vri | throw+ensure+revert | combined flow | 2 |
| 57 | test_ref.vri | ref parameters | 11, 2, 1 | 3 |
| 58 | test_register.vri | register bitfield | bit read/write | 4 |
| 59 | test_comptime.vri | compile-time exec | 3628800 | 4 |
| 60 | test_ffi_bind.vri | FFI @bind(c) | Hello from FFI | 5 |
| 61 | test_module/ | include/import | cross-file call | 6 |
| 62 | test_types.vri | type annotations | i32/u8/ptr | 6 |

---

## Rủi ro & Giải pháp

| Rủi ro | Xác suất | Tác động | Giải pháp |
|--------|----------|----------|-----------|
| FFI dynamic linking phá vỡ existing static binary | Cao | Cao | Giữ static là mặc định, `@bind(c)` trigger dynamic linking mode. 2 linker paths |
| Ensure/revert cần stack unwinding | Trung bình | Cao | Phase 7: chỉ function-local (no propagation). Phase 8: stack unwinding |
| Comptime evaluator phức tạp | Trung bình | Trung bình | Phase 7: chỉ integer + control flow. Phase 8: full evaluator |
| Module system circular import | Thấp | Cao | 3-state tracking (NotLoaded/Parsing/Parsed) + cycle error |
| Register bitfield trên big-endian | Thấp | Thấp | Phase 7: little-endian only (ARM64, x86-64). Document limitation |
| `packed entity` hang regression | Cao | Cao | Fix TRƯỚC Sprint 1. Root cause: missing IR lowering case → infinite fallthrough |

---

## Files cần chỉnh sửa

| File | LOC hiện tại | Tính năng liên quan |
|------|-------------|-------------------|
| `stdlib/vir/compiler/lexer.vri` | 955 | Tokens mới: RegisterKw, ComptimeKw, RefKw, InKw, AsKw, FromKw, GetKw |
| `stdlib/vir/compiler/parser.vri` | 1,623 | AST nodes mới: RegisterDef, ComptimeBlock, ComptimeFunc, RefParam enhanced, IncludeStmt, ImportStmt, GetStmt |
| `stdlib/vir/compiler/ir_optimizer.vri` | 2,281 | IR lowering: ref params, register bitfield, comptime eval, module resolution, ensure/revert CFG |
| `stdlib/vir/compiler/codegen.vri` | 1,852 | ARM64/x86: LoadAddr, DerefLoad, DerefStore, UBFX/BFI, dynamic linking stubs |
| `stdlib/vir/compiler/main.vri` | 1,953 | Entry point selection (@entry), linker changes (FFI) |
| `stdlib/vir/compiler/macho.vri` | ~800 | LC_LOAD_DYLIB, __stubs, __la_symbol_ptr |
| `stdlib/vir/compiler/elf.vri` | ~600 | .plt, .got, .dynsym, DT_NEEDED |
| `run_tests.sh` | ~200 | Add 15 new tests |

---

## Tham chiếu tài liệu

- Language Spec v1.2: `docs/vir_language_spec_v1.2.md`
- QIR Architecture (historical): `docs/archive/QIR_ARCHITECTURE.md` — superseded by HIR→MIR→LIR
- Self-Hosting Spec: `docs/SELF_HOSTING_SPEC.md`
- Module System: `docs/MODULE_INCLUDE_SYSTEM.md`
- Phase 6 Status: `MUST_READ_CONTEXT/CURRENT_STATUS_2026_03_30.md`
- Audit: `MUST_READ_CONTEXT/AUDIT_Docs_vs_Reality_2026_03_31.md`

---

*Plan created 2026-04-11. Next action: Sprint 1 — Fix bugs in UFCS literal, packed entity hang, verify throw + string interpolation.*
