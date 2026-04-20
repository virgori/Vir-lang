# Checklist Tính Năng — Vir v2.0

*Đối chiếu: `docs/vir_language_spec_v2.0_vi.md` (2938 dòng, 101KB — bản 12/04/2026) ↔ codebase thực tế*
*Phạm vi: Self-hosting compiler (`stdlib/vir/compiler/`) — lexer.vri, parser.vri, ir_optimizer.vri, codegen.vri, codegen_wasm.vri, main.vri*
*Cập nhật lần cuối: 18/04/2026 UTC+7*

## Snapshot xác minh 18/04/2026

- ✅ Self-host pipeline hiện đã đi hết các bước lớn: tokenize → parse → lower → optimize → ARM64 codegen → Mach-O link → write output.
- ✅ Binary do self-host compiler sinh ra giờ là Mach-O ARM64 thật; trên macOS arm64 có thể launch được sau `chmod +x` và ad-hoc `codesign -f -s -`.
- ⚠️ Blocker còn lại không còn nằm ở Mach-O/launch path mà nằm ở parser/bootstrap semantics của nhánh tự-host.
- ⚠️ Vì vậy trạng thái đúng hiện nay là: **bootstrap gần xong nhưng CHƯA thể đóng Stage 4** cho tới khi binary self-host in đúng output mẫu mà không phụ thuộc C-side execution.

### Rerun key suite — 18/04/2026 (fresh verification)

- Lệnh xác minh: `bash ./run_tests.sh`
- Kết quả thực tế hiện tại: **0/162 PASS, 162 FAIL** trong đường tự-host key suite.
- Repro tối thiểu: chạy `./core/build/vir run stdlib/vir/compiler/virc.vri test_42.vri` hiện in cảnh báo parse `line 18: expected expression (got COLONCOLON)` và **không sinh `a.out`**.
- Điều này cho thấy blocker đang nằm ở **module / namespace path parsing trong self-host entry path**, không phải riêng từng test đơn lẻ.

### Nhóm hàm / tính năng hiện CHƯA xử lý xong hoặc CHƯA re-verify được trong self-host path

- `module` / `include` / namespace path dạng `A::B::C` trong compiler entry và import graph
- `case` syntax end-to-end trong self-host compiler (dù C-core path đã chạy được test mới `test_case_real.vri`)
- string interpolation runtime path (`test_interp.vri`)
- UFCS / `this` / method dispatch (`test_ufcs.vri`, `test_this.vri`)
- `throw` / `ensure` (`test_throw.vri`, `test_ensure.vri`)
- `packed entity` (`test_packed.vri`)
- `@bind` / FFI bridge (`test_bind.vri`)
- module system integration (`test_module_system.vri`)

> Ghi chú: các hàng trạng thái chi tiết bên dưới phản ánh mức triển khai feature-by-feature; tuy nhiên **đường tự-host e2e hiện đang bị chặn bởi regression parser/module path**, nên chưa thể xem các feature này là “đã xác minh lại” cho bootstrap native.

---

## Quy ước

| Ký hiệu | Ý nghĩa |
|----------|---------|
| ✅ | Đã triển khai (lexer + parser + IR/codegen hoạt động) |
| ⚠️ | Triển khai một phần (có token/AST nhưng codegen/semantic chưa đầy đủ) |
| ❌ | Chưa triển khai (không tìm thấy hoặc chỉ có stub) |

---

## 0. Cú Pháp Block — Quy Tắc Đóng-Mở (§1)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|----------|
| 0.1 | `do` mở khối `if`/`eif` | §1 | ✅ | **MỚI 13/04** — Token `TOK_DO` (C), `DO` (Py), `Do=43` (virc). Parser cả 3 layer chấp nhận `do` sau điều kiện if/eif |
| 0.2 | `end.` đóng khối định nghĩa | §1 | ✅ | **MỚI 13/04** — `expect_def_close()` (C), `_skip_end_dot()` (Py), `match_tok(Dot)` (virc). Áp dụng cho func/entity/enum/method/class/trait/impl |
| 0.3 | Backward compatible (`:` và `end` vẫn hoạt động) | §1 | ✅ | Cú pháp cũ vẫn được chấp nhận — `do`/`end.` là tuỳ chọn |
| 0.4 | `>>` context-sensitive (shift vs cast) | §10.1/§10.5 | ✅ | **MỚI 13/04** — C core lexer peek-ahead: `>> digit/(/−` → `TOK_BIT_SHR`, otherwise → `TOK_CAST` |

*Test suite 15/04 (lần cuối): **155/160 passed** (5 fail). Tất cả file compiler `stdlib/vir/compiler/*.vri` đã chuyển `end` → `end.` (v2.0).*

### Thay đổi 14/04 (Session 2+3):
- **ARM64 frame layout (U6)**: Sửa lỗi collision callee-saved ↔ FP/LR khi spill_extra > 0. `SUB SP, frame_size` rồi STP tại offsets cố định.
- **const/let immutability**: `ir_optimizer.vri` — `const_names` + `is_const_name()`. Assignment vào const/let bị chặn.
- **Block handler**: Di chuyển lên vị trí thứ 3 trong `lower_stmt` dispatch chain.
- **codegen.vri**: Thêm `arm64_stp_off()`, `arm64_ldp_off()` + export.
- **Compiler source v2.0**: Tất cả 14 file `stdlib/vir/compiler/*.vri` chuyển `end` → `end.` cho definition blocks (453 replacements). Interpreter hỗ trợ `end.`.
- **Nhiều bug fix** (session external): entity_enum fix, string handling, bitwise ops, hanoi, exit_code, v.v. → **+14 tests** từ 137 → 151.

### Phân loại 5 test FAIL:
| Nhóm | Tests | Nguyên nhân |
|------|-------|-------------|
| Compile fail (2) | 022_switch_case, packed | `case` IR chưa xong; `packed entity` chỉ có parser |
| Entity/Array (3) | entity_enum_array, if_dot, 042_arr_entity | Entity field access trên array element lỗi; if_dot segfault (exit=139) |
| ~~Bitwise edge~~ | ~~007_bitops_edge~~ | **15/04 FIXED** — PopCnt dùng X16 thay X8 tránh clobber spilled src |
| ~~Func ptr~~ | ~~057_func_ptr_arr~~ | **15/04 FIXED** — Spill post-store nằm ngoài `if handled==0`, clobber return value |
| 64-bit overflow (1) | 080_hash | Hash `h*33+c` tràn 64-bit: expected 99162322, actual 210714636441 |
| ~~Comparison~~ | ~~089_minmax~~ | **15/04 FIXED** — IfStmt vreg recycling giảm register pressure |

---

## 1. Hệ thống Module (§3)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 1.1 | `include path;` | §3.2 | ⚠️ | Parser có hỗ trợ đường dẫn module, nhưng **key suite 18/04** cho thấy self-host entry path vẫn còn regression với namespace/module path dạng `A::B::C` nên chưa thể coi là re-verified e2e |
| 1.2 | `include ... as alias;` | §3.2 | ✅ | **14/04** — Parser check `as` sau include path, lưu alias vào `n.name2` |
| 1.3 | `import sym from module;` | §3.3 | ✅ | Parser hỗ trợ `import X from MOD` và `from MOD import X` |
| 1.4 | `import MOD as alias;` | §3.3 | ✅ | Parser xử lý `match_tok(As)` → `n.name2 = alias.str_val` |
| 1.5 | `get VAR from module;` | §3.4 | ✅ | **Đã có** — Parser tại L1845 parse `get NAME from MODULE;` → `ImportStmt` (trước đánh sai ⚠️) |
| 1.6 | `export name;` | §3.5 | ✅ | Parser có ExportStmt |
| 1.7 | `share var;` | §3.5 | ✅ | **14/04** — Parser handler cho `TokType::Share` → `ShareStmt` AST, hỗ trợ `share a, b, c;` |
| 1.8 | `port signals: Type;` | §3.5/§23 | ✅ | **14/04** — Lexer `PortKw = 172`, parser → `PortStmt` AST với `name` + `name2` (type). IR skip (compile-time) |
| 1.9 | Import kết hợp (func + var từ cùng module) | §3.6 | ✅ | `import X, Y from MOD` — parser parse danh sách tên |
| 1.10 | Dependency Graph + phát hiện vòng | §3.8 | ✅ | **14/04** — IR `dep_modules: Vec<string>` trong `LowerCtx`, track include/lazy include, skip duplicate |
| 1.11 | `lazy include` (type-only import) | §3.8 | ✅ | **14/04** — Lexer `LazyKw = 173`, parser → `LazyInclude` AST, hỗ trợ cả string và path syntax |

---

## 2. Kiểu Dữ Liệu (§4)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 2.1 | `int`, `float`, `bool`, `string` | §4.1 | ✅ | Lexer nhận int/float/string/bool |
| 2.2 | Kiểu có kích thước: `i8`–`i64`, `u8`–`u64` | §4.1 | ⚠️ | **16/04** — Lexer tokens TypeI8–TypeU64 (180–187). Parser lưu type vào `decl.name2`. Chưa có semantic enforcement |
| 2.3 | `ptr` (con trỏ thô) | §4.1 | ⚠️ | **16/04** — Lexer `TypePtr = 189`. Parser lưu vào AST. Chưa có semantic thực sự |
| 2.4 | Type annotations (suy luận kiểu) | §4.4 | ✅ | **16/04** — Parser lưu type annotation vào `name2` cho var/let/const declarations, func params, và return types. Hỗ trợ cả keyword types (i8–string) và entity types |
| 2.5 | Arena allocator (`arena: ... end` block) | §4.5–4.6 | ⚠️ | **16/04** — Parser `ArenaBlock(91)` AST. IR transparent pass-through. Chưa có allocator runtime |
| 2.6 | Arena API (`arena_alloc`, `arena_new`, `arena_free`) | §4.7 | ❌ | Không có builtin allocator API |
| 2.7 | Float arithmetic | §4.1 | ✅ | ~~Trước đánh ⚠️~~ → **Đã sửa**: IR có `FAdd/FSub/FMul/FDiv`, codegen emit ARM64 `FADD/FSUB/FMUL/FDIV` (scalar double D16/D17). NEON 4S float ops cũng có |
| 2.8 | Ownership / Borrow Checker | §4.8 | ❌ | Spec mô tả ownership/borrow/move semantic + `&`/`&mut`. Chưa triển khai |
| 2.9 | Move semantics (non-Copy types) | §4.8 | ❌ | Không có move/copy distinction |
| 2.10 | `&` / `&mut` borrow syntax | §4.8 | ❌ | Không có borrow syntax trong parser |
| 2.11 | Auto-drop (`Q_FREE`) | §4.8 | ❌ | Không có auto-drop tại scope exit |

---

## 3. Biến & Hằng (§5)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 3.1 | `var` | §5.1 | ✅ | Hoàn chỉnh |
| 3.2 | `let` (immutable binding) | §5.1 | ✅ | **14/04** — Parser tạo ConstDecl cho `let`. IR `is_const_name()` chặn assignment (giữ giá trị gốc). `var x=42; x=99; print x` → 99. `let x=42; x=99; print x` → 42 |
| 3.3 | `const` | §5.2 | ✅ | **14/04** — Giờ enforce immutability: `const x=42; x=99; print x` → 42 (assignment bị chặn). Trước đó chỉ là alias cho VarDecl |
| 3.4 | Biến cấp module (multi-line `var` block) | §5.3 | ✅ | Parser nhận diện module-level var |
| 3.5 | Quy tắc nhóm bằng `;` cho `var` block | §5.3 | ⚠️ | Hoạt động một phần, parser dựa vào `;` nhưng không enforce nghiêm ngặt |

---

## 4. Hàm (§6)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 4.1 | `func`, `out`, `end`/`end.` | §6.1 | ⚠️ | Source parser đã hỗ trợ cú pháp này, nhưng bootstrap artifact hiện tại vẫn còn regression với các hàm đơn giản dạng `func main:` — body có thể bị parse rỗng khi tự-host (xác minh 18/04) |
| 4.2 | Tham số có kiểu (`a: int`) | §6.2 | ✅ | **16/04** — Parser lưu param type vào `param.name2` cho `this`, first param, và subsequent params. Hỗ trợ keyword types + entity types |
| 4.3 | Kiểu trả về `-> int` | §6.2 | ✅ | **16/04** — Parser lưu return type vào `fn_node.name2`. Hỗ trợ `-> type` và `: type` syntax |
| 4.4 | Đối số có tên (`f(a=5; b=10)`) | §6.4 | ⚠️ | ~~Trước đánh ❌~~ → **Parser đã triển khai** named args: `call.int_val = 1` flag, parse `ident = expr` kèm `;` separator. Nhưng IR **không** reorder theo tên — chỉ truyền theo thứ tự |
| 4.5 | `has` (forward declaration) | §6.5 | ✅ | ~~Trước đánh ⚠️~~ → Parser parse `HasDecl` + IR `lower_func_def` xử lý (dòng 2055) |
| 4.6 | Higher-order functions (function pointer) | §6.6 | ✅ | LoadFuncAddr + indirect CallFunc |
| 4.7 | Đệ quy | §6.7 | ✅ | Hoàn chỉnh |
| 4.8 | `extern func` | §6 | ✅ | Parser parse `extern func name(...)` → ExternFunc AST |

---

## 5. Entity & Packed Entity (§7)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 5.1 | `entity ... end`/`end.` | §7.1 | ✅ | Hoàn chỉnh. **13/04**: `end.` closer hoạt động (xem §0.2) |
| 5.2 | Entity field access (`u.name`) | §7.1 | ✅ | `FieldAccess` hoạt động |
| 5.3 | Entity field mutation (`u.age = 31`) | §7.1 | ✅ | Hoạt động |
| 5.4 | Entity paren syntax `Point(x: 10, y: 20)` | §7.1 | ✅ | `check_entity_literal_paren()` + EntityLiteral lowering |
| 5.5 | `method` trong entity (implicit `this`) | §7.2 | ✅ | **15/04** — Parser parse `method` block bên trong entity, tự thêm `this` param. IR đăng ký + lower method như func. `test_method.vri` PASS (11,16,16) |
| 5.6 | `packed entity` (no-padding layout) | §7.3 | ⚠️ | Lexer `PackedKw = 161`, parser tạo `PackedDef`, nhưng không có logic packed layout riêng |
| 5.7 | Callable field (`btn.on_click()`) | §11.4 | ✅ | **21/04** — Q_CALL_INDIRECT + AST_CALL callable-field fallback (commit 09b66f7) |

---

## 6. Enum (§8)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 6.1 | `enum ... end`/`end.` | §8 | ✅ | Hoàn chỉnh. **13/04**: `end.` closer hoạt động (xem §0.2) |
| 6.2 | `Color.Red` / `Color::Red` syntax | §8 | ✅ | EnumAccess hoạt động |

---

## 7. Luồng Điều Khiển (§9)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 7.1 | `if / eif / else / end` | §9.1 | ✅ | Hoàn chỉnh. **13/04**: `do` opener hoạt động — `if x > 5 do ... end` (xem §0.1) |
| 7.2 | `when ... loop` | §9.2 | ✅ | Hoàn chỉnh |
| 7.3 | `for i in 0..10:` | §9.3 | ✅ | Hoàn chỉnh |
| 7.4 | `loop` (vô hạn) | §9.4 | ✅ | Hoàn chỉnh |
| 7.5 | `loop N:` (đếm) | §9.5 | ✅ | Hoàn chỉnh |
| 7.6 | `break` | §9.6 | ✅ | Hoàn chỉnh |
| 7.7 | `skip` (continue) | §9.6 | ✅ | Hoàn chỉnh |
| 7.8 | Block-local shadowing | §5/§9 | ✅ | **14/04** — `ir_optimizer.vri` dùng symbol stack + pop khi rời block; `test_adv_059_shadowing.vri` giờ PASS (`10,42,10`) |

---

## 8. Toán Tử (§10)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 8.1 | Số học: `+`, `-`, `*`, `/`, `%`, `mod` | §10.1 | ✅ | Hoàn chỉnh |
| 8.2 | Luỹ thừa `^` | §10.1 | ✅ | ~~Trước đánh ⚠️~~ → **13/04**: virc có `parse_power()` + `PowOp = 25` + IR `Pow` QOp. `test_adv_053_power.vri` PASS |
| 8.3 | So sánh: `==`, `!=`, `>`, `<`, `>=`, `<=` | §10.2 | ✅ | Hoàn chỉnh |
| 8.4 | So sánh an toàn: `?=`, `?=/=` (nil-safe) | §10.2 | ✅ | **20/04** — C core parser + IR lower emit nil-safe compare (commit a423f80) |
| 8.5 | Logic: `and`/`&`, `or`/`||`, `not`/`!` | §10.3 | ✅ | Hoàn chỉnh |
| 8.6 | Bit: `and`, `or`, `xor`, `shl`, `shr` | §10.4 | ✅ | **14/04 update** — right-shift alias `shrrr` được map về `shr`; `test_adv_005_shift.vri` và `test_adv_097_bit_manip.vri` PASS |
| 8.7 | Truy cập an toàn `?.` | §10.5 | ✅ | **20/04** — AST_SAFE_ACCESS lower hoàn chỉnh (commit a423f80). Không rewrite thành AST_CALL ngay cả khi có `()` theo sau |
| 8.8 | Kiểm tra tồn tại `?` | §10.5 | ✅ | **20/04** — AST_EXIST_CHECK: `expr == 0 XOR 1` (commit a423f80) |
| 8.9 | So khớp mẫu `:~` | §10.5 | ✅ | **21/04** — Compile-time LHS-shape check: literal int/float/string/array/record vs type name → 0/1 tại thời điểm lower (commit 09b66f7). Identifier biến vẫn fall-through Q_CMP_EQ |
| 8.10 | Ép kiểu `>>` | §10.5 | ✅ | `Cast = 87` trong parser. **13/04**: C core lexer giờ context-sensitive — `>> digit/(/-` → SHR, otherwise → Cast |
| 8.11 | Chuyển đổi kiểu `as` | §10.5 | ✅ | **20/04** — Passthrough lower (int/float cùng VM repr) (commit a423f80) |
| 8.12 | Matmul `**` | §26.2 | ✅ | **20/04** — Q_TENSOR_MUL runtime dispatch: array operands → element-wise mul, scalar → `a*b` (commit ea98aa0). Verified: `[2,3,4,5]**[10,20,30,40] = [20,60,120,200]` |
| 8.13 | FMA `><` | §26.2 | ✅ | **20/04** — Q_TENSOR_FMA cùng semantics (commit ea98aa0) |
| 8.14 | Swizzle `~` | §24.2 | ✅ | **20/04** — Q_SWIZZLE với channel string trong module string table; array → reorder theo `xyzw`/`rgba`; scalar → passthrough (commit ea98aa0). Verified: `[10,20,30,40]~zyx = [30,20,10]` |
| 8.15 | Atomic `lock` / `!!` | §24.4 | ✅ | **20/04** — Q_ATOMIC_LOAD/STORE/ADD/SUB_GLOBAL qua `vir_atomic_*_i64` seq_cst (commit ea98aa0). `lock x += v` peephole thành một Q_ATOMIC_ADD_GLOBAL đơn (không phải load+store rời) |

---

## 9. UFCS (§11)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 9.1 | `x.func()` → `func(x)` | §11.1 | ✅ | **20/04 C core** — `parse_unary` postfix loop: sau khi build AST_FIELD_ACCESS, nếu `(` tiếp theo thì retype thành AST_CALL với receiver = children[0]. Verified: `21.double() = 42`, `5.add(3) = 8` |
| 9.2 | `this` keyword | §11.2 | ✅ | `this` là plain identifier trong parser. Verified: `func square: in(this:int) out this*this end; print 7.square() → 49` |
| 9.3 | UFCS chaining `a.b().c()` | §11.3 | ✅ | **20/04 C core** — Postfix loop + AST_CALL retype cho phép chaining liên tục. Verified: `10.inc().double().inc() = 23`, `4.square().incr(1) = 17`. Lexer fix kèm theo: `lex_number` không nuốt `.` khi ký tự tiếp theo là letter/`_` để `10.inc()` lex đúng thành INT DOT IDENT |
| 9.4 | UFCS trên Entity | §11.4 | ✅ | Hoạt động với `this: SomeType` param (miễn là entity literal syntax đã có; §5.4 hoàn chỉnh) |
| 9.5 | Callable field (field con trỏ hàm) | §11.4 bước 2 | ✅ | **21/04** — Q_CALL_INDIRECT = 0xF4 opcode; AST_IDENTIFIER fallback → Q_LOAD imm=fidx; AST_CALL fallback dò record field → load fn addr + Q_CALL_INDIRECT (không ngầm truyền `this`) (commit 09b66f7) |
| 9.6 | Field vs Function resolution (4 bước) | §11.4 | ✅ | **21/04** — Đủ 4 bước: (1) method via UFCS, (2) callable field via Q_CALL_INDIRECT, (3) free function via UFCS, (4) field access fallback (commit 09b66f7) |

---

## 10. Nội Suy Chuỗi (§12)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 10.1 | `"Hello $name"` | §12.1 | ✅ | Lexer `InterpStart/InterpEnd`, sub-lexing |
| 10.2 | `"$obj.prop"` | §12.2 | ✅ | Lexer kiểm tra Dot sau Ident, emit FieldAccess |
| 10.3 | `"$(expr)"` | §12.3 | ✅ | Lexer xử lý `$(` → balanced paren → sub-lex. `InterpExprMark = 172`. Parser wraps in `InterpSubExpr` AST |
| 10.4 | `"$$"` thoát ký hiệu | §12.4 | ✅ | Lexer xử lý double `$` → single `$` literal |
| 10.5 | Quy tắc biên lexer (`$ident` dừng tại `[`) | §12.6 | ✅ | Lexer tuân thủ: `$` chỉ lex ident/field, `[` dừng |

---

## 11. Xử Lý Lỗi (§13)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 11.1 | `throw <expr>` | §13.1 | ✅ | Lexer `ThrowKw = 165`, parser `ThrowStmt`, IR emit Trap |
| 11.2 | `ensure` (cleanup on exit) | §13.2 | ✅ | Lexer `EnsureKw = 163`, parser `EnsureBlock`, IR lower ở cuối `lower_func_def` |
| 11.3 | `revert` (cleanup on throw) | §13.3 | ⚠️ | Lexer `RevertKw = 164`, parser `RevertBlock`. IR handler có nhưng semantic throw→revert chưa đầy đủ  |
| 11.4 | `erx` (thanh ghi lỗi) | §13.5 | ❌ | Không có `erx` keyword. Throw chỉ emit Trap, không lưu mã lỗi  |
| 11.5 | Kiểu lỗi int (mã 0–255) | §13.6 | ❌ | Không có error code convention |
| 11.6 | `try: ... revert ... end` (local) | §13.7 | ⚠️ | Lexer có `Try = 150`, parser **không** parse `try` block dạng local. Chỉ có ensure/revert cấp hàm |
| 11.7 | `try(timeout: 5s):` | §13.7 | ❌ | Không có timeout parameter |
| 11.8 | `try(isolate: [x, y]):` snapshot | §13.7 | ❌ | Không có isolate snapshot |
| 11.9 | `resume retry` | §13.7 | ❌ | Không có resume keyword |
| 11.10 | `resume revert` (Saga pattern) | §13.7 | ❌ | Không có resume keyword |
| 11.11 | `emit LOG_INFO(...)` (structured logging) | §13.7 | ❌ | Không có emit keyword |
| 11.12 | Cảnh báo W302 (dirty state detection) | §13.7 | ❌ | Không có compiler warning system |
| 11.13 | `atomic var` (mutation xuyên retry) | §13.7 | ❌ | **MỚI** — Spec thêm `atomic var` để tắt W302 và giữ giá trị qua retry. Không có `atomic` keyword |

---

## 12. Tham Số Nhóm — in / ref / out (§14)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 12.1 | `ref` parameter (pass-by-reference) | §14.1 | ⚠️ | Lexer `RefKw = 166`, parser tạo `RefParam`. Nhưng không có LoadAddr/DerefLoad semantic thực sự |
| 12.2 | `in` parameter group | §14.2 | ✅ | `in(...)` block syntax hoạt động |
| 12.3 | `out` return | §14.2 | ✅ | `out expr` hoạt động |
| 12.4 | Cú pháp nhóm multi-line (`;` continuation) | §14.2 | ⚠️ | `;`-separated params hoạt động nhưng không enforce |
| 12.5 | Phát hiện lệch nhóm (compiler safety) | §14.2 | ❌ | Không có diagnostics cho tham số mồ côi/nhóm rỗng |

---

## 13. FFI — @bind (§15)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 13.1 | `@bind(c)` | §15.1 | ✅ | Parser generic `@attr(arg)` → `BindAttr{name, name2}` |
| 13.2 | `@bind(asm)` | §15.2 | ✅ | Parsed qua cùng generic mechanism |
| 13.3 | `@bind(wasm)` | §15.3 | ✅ | Parsed qua generic mechanism |
| 13.4 | WebAssembly target | §15.3 | ⚠️ | codegen_wasm.vri có WASM binary encoder nhưng chưa tích hợp vào build pipeline e2e |
| 13.5 | Liên kết Mach-O (`__stubs`, `__la_symbol_ptr`) | §15.5 | ✅ | codegen.vri có Mach-O linker |
| 13.6 | Liên kết ELF (`.plt`, `.got`) | §15.5 | ✅ | codegen.vri có ELF linker |
| 13.7 | WASM import section | §15.5 | ⚠️ | codegen_wasm.vri có import section nhưng chưa e2e |

---

## 14. Register & Mold (§16)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 14.1 | `register NAME: u32 ... end` | §16.1 | ⚠️ | Lexer `RegisterKw = 167`, parser tạo `RegisterDef`. Nhưng không có bit-level access codegen |
| 14.2 | Field bit access (single/multi-bit) | §16.3 | ❌ | Không có `UBFX`/`BFI` codegen |
| 14.3 | `volatile_read`/`volatile_write` | §16.5 | ❌ | Không có intrinsic riêng |
| 14.4 | `mold Name: u16 r:5, g:6, b:5 end` | §16.6 | ❌ | Không có `MoldKw` token, parser/IR không xử lý |

---

## 15. Precomp / Comptime (§17)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 15.1 | `precomp { expr }` / `comptime { expr }` | §17.1 | ⚠️ | Lexer `ComptimeKw = 162` map cả `"precomp"` và `"comptime"`. Parser/IR không xử lý — chỉ có token |
| 15.2 | `precomp func` | §17.2 | ❌ | Không có |
| 15.3 | Compile-time validation | §17.3 | ❌ | Không có |

---

## 16. @entry (§18)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 16.1 | `@entry` attribute | §18 | ⚠️ | Generic `@attr` mechanism parse `@entry func main:` nhưng compiler hard-code tìm `func main` |

---

## 17. Mảng (§19)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 17.1 | Array literal `[1, 2, 3]` | §19.1 | ✅ | `ArrayLiteral` AST |
| 17.2 | `arr_new()`, `push()`, `len()` | §19.2 | ✅ | Builtin intrinsics |
| 17.3 | Array index access `a[i]` | §19.1 | ✅ | `IndexAccess` AST |
| 17.4 | Array set `a[i] = v` | §19.2 | ✅ | `IndexAssign` AST → `ArrSet` QOp |
| 17.5 | `arr_compact(arr)` | §19.4 | ❌ | Không có arr_compact builtin |
| 17.6 | `cap(arr)` (capacity) | §19.4 | ❌ | Không có cap() builtin |

---

## 18. Dict & Map (§20)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 18.1 | `dict[K, V] ... end` | §20.1 | ❌ | Không có parser/IR cho dict type |
| 18.2 | Dict operations (`m["key"]`, `del`, `len`) | §20.1.2 | ❌ | Không có |
| 18.3 | Dict iteration (`for k, v in dict:`) | §20.1.3 | ❌ | `for` chỉ hỗ trợ range (`0..n`) |
| 18.4 | Hash function support (FNV-1a, entity `method hash`) | §20.1.4 | ❌ | Không có |
| 18.5 | `map x in list: out expr end` (transformation) | §20.2 | ⚠️ | Lexer `MapKw = 152`, parser không xử lý map expression |

---

## 19. Case Expression (§21)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 19.1 | `case expr ... else ... end` | §21 | ⚠️ | Đã có parser/lowering path và **test mới `test_case_real.vri` chạy đúng trên C-core path** (18/04). Tuy nhiên self-host key suite vẫn chưa re-verify được end-to-end vì compiler entry đang bị chặn sớm bởi regression parser/module path |

---

## 20. Async / Task (§22)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 20.1 | `async func` | §22.1 | ✅ | **16/04** — Lexer `Async=19`, `AwaitKw=200`. Parser `AsyncFuncDef(80)`. IR normalize → FuncDef + CallFunc (sync stub). `test_async_basic.vri` PASS |
| 20.2 | `await` | §22.1 | ⚠️ | **16/04** — Lexer `AwaitKw=200`. Parser → Call node (bypass AwaitExpr). IR lower trực tiếp. `await expr` hoạt động, `await pass` bị hang (C VM bug) |
| 20.3 | `await pass` (cooperative yield) | §22.6 | ❌ | C VM interaction bug — hang khi gặp `await pass`. Deferred (no-op trong sync mode) |
| 20.4 | `task` expression | §22.2 | ✅ | **16/04** — Parser `TaskExpr(82)`. IR lower → SetArg chain + CallFunc (sync stub). `test_async_basic.vri` PASS |
| 20.5 | `wait` expression | §22.3 | ✅ | **16/04** — Parser `WaitExpr(83)`. IR lower → pass-through (sync stub). Task result = call return value |
| 20.6 | `cancel` task | §22.7 | ⚠️ | **16/04** — Lexer `CancelKw=201`. Parser `CancelStmt(84)`. IR evaluate for side effects (no-op stub) |
| 20.7 | `select` multiplex | §22.8 | ⚠️ | **16/04** — Lexer `SelectKw=202`. Parser `SelectStmt(85)` + `SelectBranch(86)`. IR sequential execution stub |
| 20.8 | `quiet` fire-and-forget | §22.9 | ⚠️ | **16/04** — Lexer `QuietKw=203`. Parser `QuietStmt(87)`. IR fire-and-forget stub |
| 20.9 | Scheduler / Event loop | §22.5 | ❌ | Không tích hợp vào compiler |

---

## 21. Port — Tín Hiệu Giữa Workers (§23)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 21.1 | `port NAME: Type` (khai báo) | §23.1 | ⚠️ | **14/04** — Lexer `PortKw = 172`, parser → `PortStmt` AST (name + type). Nhưng chưa có runtime send/recv |
| 21.2 | `send port <- value` | §23.2 | ⚠️ | **16/04** — Lexer `SendKw=204` (C VM enum FAIL). Parser `SendStmt(88)` parse `<-` syntax. IR no-op stub |
| 21.3 | `recv port` | §23.3 | ⚠️ | **16/04** — Lexer `RecvKw=205` (C VM enum FAIL). Parser `RecvExpr(89)`. IR Load 0 stub |
| 21.4 | Port + `select` | §23.4 | ❌ | Không có |
| 21.5 | Port capacity (`port(cap: N)`) | §23.6 | ❌ | Không có |

---

## 22. GPU, SIMD & Atomic (§24)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 22.1 | `flux<T, N>` (SIMD vector) | §24.1 | ❌ | Không có token/parser. *Lưu ý: codegen.vri có NEON helper `neon_fadd_4s/fmul_4s/fdiv_4s/fmla_4s` nhưng chưa wire vào language level* |
| 22.2 | Swizzle `~` read (`v~xyz`) | §24.2 | ❌ | Không có |
| 22.3 | Swizzle `~` write-mask (`v~xy = ...`) | §24.2 | ❌ | **MỚI** — Spec thêm write-masking. Không triển khai |
| 22.4 | `deck Name: Type[size]` (shared buffer) | §24.3 | ❌ | Không có token/parser |
| 22.5 | `lock x = v` (atomic write) | §24.4 | ❌ | Không có token/parser |
| 22.6 | `x!! = v` (postfix atomic) | §24.4 | ❌ | Không có token/parser |
| 22.7 | `lock.cas(x, old, new)` (CAS) | §24.4 | ❌ | Không có |
| 22.8 | `flux.dot`, `flux.len`, `flux.norm` | §24.1 | ❌ | Không có |
| 22.9 | `flux.load(ptr)`, `flux.store(ptr, v)` | §24.1 | ❌ | Không có |

---

## 23. UI / Reactive (§25)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 23.1 | `reactive var` | §25.1 | ❌ | Không có token/parser |
| 23.2 | `morph Entity -> UI:` | §25.2 | ❌ | Không có |
| 23.3 | `bundle name: type = embed "path"` | §25.3 | ❌ | Không có |
| 23.4 | `expose func` (API endpoint) | §25.4 | ❌ | Không có |
| 23.5 | `isolate: ... end` (security sandbox) | §25.5 | ❌ | Không có |

---

## 24. AI / Học Máy (§26)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 24.1 | `tensor<T>[S...]` | §26.1 | ❌ | Không có token/parser |
| 24.2 | Matmul `**` | §26.2 | ❌ | Không có |
| 24.3 | FMA `><` | §26.2 | ❌ | Không có |
| 24.4 | `infer: ... end` block | §26.3 | ❌ | Không có |
| 24.5 | `train: ... end` block | §26.4 | ❌ | Không có |
| 24.6 | `quantize(model, bits: 8)` | §26.5 | ❌ | Không có |

---

## 25. Intrinsics Hệ Thống (§27)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 25.1 | `__syscall(num, a0, a1, a2)` | §27 | ✅ | BuiltinId::Syscall → QOp::Syscall → ARM64 SVC |
| 25.2 | `__memcpy`, `__memset` | §27 | ✅ | QOp::MemCopy/MemSet. 3-arg lowering |
| 25.3 | `__clz`, `__ctz`, `__popcnt`, `__bswap` | §27 | ✅ | ARM64 CLZ/RBIT/REV |
| 25.4 | `__neg`, `__not` | §27 | ✅ | ARM64 NEG/MVN |
| 25.5 | `__fence`, `__trap` | §27 | ✅ | DMB, BRK |
| 25.6 | `volatile_read`/`volatile_write` | §27 | ❌ | Không có intrinsic riêng |
| 25.7 | Atomic: `__atomic_load/_store/_cas/_add/_sub` | §27 | ✅ | ARM64 LDAR/STLR/LDXR/STXR. Codegen hoàn chỉnh |

---

## 26. Hỗ Trợ Đa Ngôn Ngữ (§28)

| # | Tính năng | Spec | Trạng thái | Ghi chú |
|---|-----------|------|-----------|---------|
| 26.1 | Tiếng Việt: `nếu`, `hàm`, etc. | §28 | ⚠️ | C core lexer có keyword map tiếng Việt. Self-hosting lexer chỉ có English |
| 26.2 | 中文, 日本語, 한국어 | §28 | ❌ | Chỉ có Vietnamese (C core) và English |
| 26.3 | SubLib adapter / KeywordRegistry | §28 | ❌ | Không có dynamic keyword system |

---

## Tóm Tắt Thống Kê

| Trạng thái | Số lượng | Tỷ lệ |
|-----------|---------|--------|
| ✅ Đã triển khai | 83 | 57% |
| ⚠️ Một phần | 22 | 15% |
| ❌ Chưa triển khai | 41 | 28% |
| **Tổng** | **146** | **100%** |

*Cập nhật 20/04/2026: §8.4, §8.7, §8.8, §8.11, §8.12, §8.13, §8.14, §8.15 chuyển từ ⚠️/❌ → ✅ (commit `a423f80` + `ea98aa0` triển khai toàn bộ §10/§24/§26.2 operators trong C core). §9 UFCS đã xác minh hoạt động (§9.1/9.3 hiện là real UFCS rewrite, không phải stub).*

*Cập nhật 21/04/2026: §5.7, §9.5, §9.6 chuyển ❌/⚠️ → ✅ (callable field qua Q_CALL_INDIRECT=0xF4). §8.9 `:~` chuyển ⚠️ → ✅ (compile-time LHS-shape type check). Commit 09b66f7. Stats: ✅ 79→83 (+4), ⚠️ 24→22 (-2), ❌ 43→41 (-2).*

---

## Sửa Lỗi So Với Checklist Trước (v2)

| Mục | Trước (v1) | Sau (v2) | Lý do |
|-----|------------|----------|-------|
| 2.7 Float arithmetic | ⚠️ | ✅ | IR có `FAdd/FSub/FMul/FDiv` QOp + codegen emit ARM64 `FADD/FSUB/FMUL/FDIV` (scalar double D16/D17). NEON `fadd_4s/fmul_4s/fdiv_4s/fmla_4s` cũng có |
| 4.4 Named arguments | ❌ | ⚠️ | Parser **đã triển khai** named args parsing (`call.int_val = 1` flag, `ident = expr ; ident = expr`). Nhưng IR không reorder — args chỉ truyền theo thứ tự parse |
| 4.5 `has` forward decl | ⚠️ | ✅ | Parser parse `HasDecl` (dòng 1625-1650) + IR xử lý trong `lower_func_def` (dòng 2055) |
| 8.9 `:~` pattern / case | ⚠️ | ⚠️ | virc có `parse_case_stmt` + `CaseExpr=67` nhưng IR/codegen chưa hoàn chỉnh (`test_adv_022` FAIL compile) |
| 19.1 `case ... end` | ⚠️ | ⚠️ | Đồng bộ với 8.9 |

### Tính năng MỚI từ spec update (2847 → 2934 dòng)

| Mục | Spec | Trạng thái | Ghi chú |
|-----|------|-----------|---------|
| 1.11 `lazy include` | §3.8 | ✅ | **14/04** — `lazy include X;` cho phụ thuộc vòng kiểu. Lexer `LazyKw`, parser → `LazyInclude` AST |
| 11.13 `atomic var` | §13.7 | ❌ | Bổ ngữ biến cho retry — giữ giá trị qua `resume retry`, tắt W302 |
| 22.3 Swizzle write-mask | §24.2 | ❌ | `v~xy = flux(a, b)` — ghi chọn lọc kênh, sinh `INS`/`BLENDPS` |
### Cập nhật 13/04/2026 — Block Syntax v1.2 + Parser improvements

| Mục | Trước (v2) | Sau (v3) | Lý do |
|-----|------------|----------|--------|
| 0.1–0.3 Block syntax `do`/`end.` | N/A | ✅ | **MỚI** — `do` opener cho if/eif, `end.` closer cho definition blocks. Triển khai cả 3 layer: C core (`TOK_DO`, `expect_block_open`, `expect_def_close`), Python (`DO`, `_skip_end_dot`), virc (`Do=43`, `match_tok(Dot)`) |
| 0.4 `>>` context-sensitive | N/A | ✅ | **MỚI** — C core lexer peek-ahead phân biệt shift (`>> 8`) vs cast (`>> int`) |
| 8.2 Luỹ thừa `^` | ⚠️ | ✅ | virc có `parse_power()` + `PowOp=25` + IR `Pow` QOp. `test_adv_053_power.vri` PASS |
| 8.9 Pattern `:~` | ⚠️ | ⚠️ | Parser có `parse_case_stmt` nhưng dùng value comparison, chưa có `:~` semantic |
| 8.10 `>>` cast | ✅ | ✅ | Cải tiến: context-sensitive lexing (shift vs cast) |
| 19.1 `case` expr | ⚠️ | ⚠️ | virc giờ có `parse_case_stmt` + `CaseExpr=67`. Nhưng IR/codegen chưa hoàn chỉnh — test FAIL (compile) |

### Cập nhật 14/04 Session 3 — v2.0 compliance + bug fixes (+14 tests)

| Mục | Trước (v3) | Sau (v4) | Lý do |
|-----|------------|----------|--------|
| 5.5 `method` trong entity | ✅ | ⚠️ | Đánh sai ✅ — parser chỉ có UFCS dot-call, CHƯA parse `method` block bên trong entity. `test_method.vri` FAIL (compile timeout) |
| Compiler source v2.0 | N/A | ✅ | Tất cả 14 file `stdlib/vir/compiler/*.vri` chuyển `end` → `end.` (453 replacements) |
| String handling | ⚠️ (4 FAIL) | ✅ | test_034, 037, 055, interp giờ đều PASS |
| Memory/byte | ⚠️ (2 FAIL) | ✅ | test_012_byte_rw, 016_memset giờ PASS |
| Logic bugs | ⚠️ (3 FAIL) | ✅ | test_058, 071, 088 giờ PASS |
| Entity/enum | ⚠️ (2 FAIL) | ✅ (1/2) | test_047, 091 PASS. test_entity_enum_array vẫn FAIL (partial output) |
| Bitwise | ⚠️ (2 FAIL) | ⚠️ (1/1) | test_004 PASS, test_007 vẫn FAIL (__popcnt spill) |
| Complex | ⚠️ (2 FAIL) | ✅ | virc_all, 100 giờ PASS |
| eif classify | ⚠️ | ✅ | test_082 PASS |
| entity_paren | FAIL | ✅ | test_entity_paren PASS |
| ufcs | FAIL | ✅ | test_ufcs PASS |

**Test suite**: 137/160 → **151/160** (+14 tests, 9 remaining failures)

**Test suite 14/04/2026 (final)**: 151/160 passed, 9 failed. Tất cả compiler source files `end` → `end.` (v2.0). Không có regression.

### Cập nhật 15/04/2026 — Method in Entity + Bug Fixes (+4 tests)

| Mục | Trước | Sau | Lý do |
|-----|-------|-----|-------|
| 5.5 `method` trong entity | ⚠️ | ✅ | Parser parse `method` block bên trong entity, tự thêm `this` param. IR đăng ký + lower method như func. `test_method.vri` PASS |
| test_007_bitops_edge | FAIL | ✅ | PopCnt handler dùng X16 thay X8 tránh clobber khi src/dst cùng spilled |
| test_057_func_ptr_arr | FAIL | ✅ | Di chuyển spill post-store vào trong `if handled==0` block — tránh clobber return value với d_reg chưa init |
| test_089_minmax | FAIL | ✅ | IfStmt handler recycle vreg sau mỗi branch, giảm register pressure |
| MethodCall in lower_stmt | N/A | ✅ | Thêm explicit MethodCall handler để tránh entity corruption qua C VM |

**Test suite 15/04/2026**: 155/160 passed, 5 failed. (+4 tests từ 151)

### Cập nhật 16/04/2026 — Data Types + Async/Task System

| Mục | Trước | Sau | Lý do |
|-----|-------|-----|-------|
| 2.2 Sized types | ❌ | ⚠️ | Lexer tokens TypeI8–TypeU64 (180–187). Parser lưu type vào `decl.name2`. Chưa có semantic enforcement |
| 2.3 `ptr` | ❌ | ⚠️ | Lexer `TypePtr=189`. Parser lưu vào AST |
| 2.4 Type annotations | ⚠️ | ✅ | Parser lưu type cho var/let/const decl (`name2`), func params (`param.name2`), return types (`fn_node.name2`) |
| 2.5 Arena block | ❌ | ⚠️ | Parser `ArenaBlock(91)`. IR transparent pass-through |
| 4.2 Param types | ⚠️ | ✅ | Parser lưu `param.name2` cho this, first, subsequent params |
| 4.3 Return type | ⚠️ | ✅ | Parser lưu `fn_node.name2` — `-> type` và `: type` syntax |
| 20.1 `async func` | ⚠️ | ✅ | Parser `AsyncFuncDef(80)` → IR normalize → FuncDef + CallFunc sync stub |
| 20.2 `await` | ❌ | ⚠️ | Parser → Call node. `await expr` works, `await pass` hangs (C VM bug) |
| 20.4 `task` | ⚠️ | ✅ | Parser `TaskExpr(82)` → IR SetArg + CallFunc sync stub |
| 20.5 `wait` | ⚠️ | ✅ | Parser `WaitExpr(83)` → IR pass-through sync stub |
| 20.6 `cancel` | ❌ | ⚠️ | Parser `CancelStmt(84)`. IR no-op stub |
| 20.7 `select` | ❌ | ⚠️ | Parser `SelectStmt(85)` + `SelectBranch(86)`. IR sequential stub |
| 20.8 `quiet` | ❌ | ⚠️ | Parser `QuietStmt(87)`. IR fire-and-forget stub |
| 21.2 `send` | ❌ | ⚠️ | Lexer `SendKw=204`, parser `SendStmt(88)`. IR no-op stub |
| 21.3 `recv` | ❌ | ⚠️ | Lexer `RecvKw=205`, parser `RecvExpr(89)`. IR Load 0 stub |

**New tokens (lexer.vri)**: TypeI8(180)–TypeString(193), DictKw(194), ArenaKw(195), AwaitKw(200)–RecvKw(205) — 22 tokens total.
**New AST types (parser.vri)**: AsyncFuncDef(80)–ArenaBlock(91) — 12 AST types total.
**New QOps (ir_optimizer.vri)**: TaskCreate(170)–RecvOp(176) — defined but NOT emitted (C VM can't handle in codegen dispatch). Sync stubs use existing CallFunc QOp.

**New tests**: `test_typed_vars.vri` ✅ (42,100,3,hello), `test_async_basic.vri` ✅ (10,20,30), `test_await.vri` ✅ (42,0)

**Known issues**:
- `await pass` causes C VM hang during lowering — deferred (no-op in sync mode)
- TokType::SendKw(204)/RecvKw(205) exceed C VM enum resolution limit — cosmetic warning only
- Stats: ✅ 65→71 (+6), ⚠️ 25→28 (+3), ❌ 56→47 (−9)

---

## Các Khu Vực Ưu Tiên Cao

### Nhóm 1 — Nền tảng ngôn ngữ (blocking nhiều tính năng khác)
1. ~~**Hệ thống kiểu thực sự**~~ — ✅ **16/04 DONE** — Parser lưu type annotations vào AST (`name2`). Cần semantic enforcement cho next step
2. ~~**Sized types** (`i8`–`i64`, `u8`–`u64`, `ptr`)~~ — ⚠️ **16/04 PARTIAL** — Lexer tokens + parser lưu. Cần codegen emit size-specific instructions
3. **`case` expression** — parser có `parse_case_stmt` + `CaseExpr` AST nhưng IR/codegen chưa hoàn chỉnh. Test FAIL (compile). Cần cho pattern matching
4. ~~**`method` trong entity**~~ — ✅ **15/04 DONE** — Parser + IR hoàn chỉnh, `test_method.vri` PASS
5. **Ownership/Borrow checker** — spec mô tả đầy đủ, cần compiler pass

### Nhóm 2 — Tính năng ngôn ngữ cốt lõi
6. **Named argument reordering** — parser parse nhưng IR chỉ truyền theo thứ tự
7. **`ref` semantic thực sự** — có token/AST nhưng chưa có pass-by-reference (LoadAddr/DerefLoad)
8. **`erx` error register** + error propagation — throw chỉ Trap, chưa có error handling model
9. **`try: ... revert ... end`** (local error boundary) — chỉ có ensure/revert cấp hàm
10. **`ref` semantic thực sự** — có token/AST nhưng chưa có pass-by-reference (LoadAddr/DerefLoad)

### Nhóm 3 — Cấu trúc dữ liệu
11. **Dict** — hoàn toàn chưa triển khai, cần hash table runtime
12. **Map expression** — phụ thuộc iteration protocol

### Nhóm 4 — Hệ thống nâng cao
13. ~~**Async/Task/Await**~~ — ⚠️ **16/04 PARTIAL** — Parser + IR sync stubs hoàn chỉnh. `async func`, `task`, `wait` ✅. `await expr` ⚠️. Cần scheduler cho true async
14. **Port** (MPSC message queue) — ⚠️ **16/04 PARTIAL** — send/recv có parser + IR stubs. Cần runtime
15. **Precomp/Comptime** — chỉ có token, cần compile-time evaluator
16. **Register bit-field + `mold`** — cần cho embedded/OS dev
17. **WASM pipeline e2e** — codegen_wasm.vri exists nhưng chưa wire vào build
18. **Arena block + Allocator API** — cần cho memory management model

### Nhóm 5 — Tầm nhìn xa (frontier)
19. **GPU/SIMD** (`flux`, `deck`, swizzle, `lock`) — cần SIMD codegen backend. NEON helpers đã tồn tại ở mức codegen
20. **UI/Reactive** (`reactive`, `morph`, `bundle`, `expose`) — cần UI runtime
21. **AI/ML** (`tensor`, matmul `**`, autodiff, `quantize`) — cần tensor runtime + SIMD

---

*Tài liệu này đối chiếu spec `docs/vir_language_spec_v2.0_vi.md` (2934 dòng, 101KB — bản 12/04/2026) với self-hosting compiler tại `stdlib/vir/compiler/` (10,461 dòng tổng 5 file chính).*
*Spec có §1–§31 (28 mục tính năng + 3 mục tham chiếu). Tổng: 146 tính năng kiểm tra (142 gốc + 4 block syntax mới).*
*Compiler source: Tất cả 14 file `.vri` đã tuân thủ v2.0 (`end.` cho definition blocks). Interpreter (`./core/build/vir`) hỗ trợ `end.`.*
