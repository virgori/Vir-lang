# Báo Cáo Tình Trạng Dự Án Vir v2.0
**Ngày:** 2026-07-26 20:40 (GMT+7)
**Branch hiện tại:** `recovered_stash`

---

## Mốc đạt được: Stage-1 sinh binary chạy được

`virc_stage1.vri` giờ là compiler thật, không còn stub. Nó tự lex → parse → codegen →
link Mach-O, và binary nó tạo ra chạy đúng.

| Stage | Status |
|-------|--------|
| Stage-0 → `dist/virc-stage1` | **PASS** — Mach-O arm64 hợp lệ |
| Stage-1 → `dist/from_s1` | **PASS** — exit 0, ghi file mode 0755 |
| `./dist/from_s1` | **PASS** — in `42` |
| `tests/bootstrap_codegen/` (17 file) | **17/17** — thêm `cg_when`, `cg_when_assign` |

```bash
./tools/s1_try.sh
# → S1_EXIT:0
# → 42
# → OUT_EXIT:0
```

`tools/s1_try.sh` build Stage-1 bằng Stage-0, ký, chạy trên
`tests/bootstrap_codegen/cg_call.vri`, rồi chạy binary kết quả. Có watchdog 8 giây
nên vòng lặp vô hạn hiện ra thành `S1_TIMEOUT` thay vì treo terminal.

Ghi chú: `cg_global` không in gì. Đây là lỗi **có sẵn từ trước** (đã kiểm chứng bằng
`git stash` bản Stage-0 cũ), không phải hồi quy của đợt sửa này.

---

## Sáu lỗi codegen Stage-0

Đây là phần quan trọng nhất của tài liệu này. Sáu lỗi xếp chồng lên nhau, mỗi lỗi
che lỗi kế tiếp, nên chúng chỉ lộ ra lần lượt. Ai chạm vào codegen Stage-0 nên đọc
hết mục này trước.

Lỗi 1–4 và **6 đã sửa gốc**. Lỗi 5 (`when`/`while` lower) **đã sửa** — xem mục 5
bên dưới. Stage-1 vẫn nên ưu tiên st-slot trong thân `when` (store `let` trên C-VM
vẫn mỏng), nhưng vòng `when` đơn giản với `n = n + 1` giờ lower và chạy đúng.

### 1. Hàm không được đóng khi có `out` giữa thân — `virc_boot.vri:19567`, `:22226`

Vòng emit dùng cờ `did_ret` để bỏ epilogue cuối hàm. Nhưng cờ đó chỉ nói "đã emit
*một* lệnh `Ret` nào đó", không phải "lệnh cuối cùng là `Ret`". Hàm có `out` sớm
ở giữa thân (như `next_tok`) bị bỏ ngỏ phần đuôi, và **rơi thẳng vào prologue của
hàm kế tiếp** trong buffer code.

Triệu chứng: `next_tok` rơi vào `classify_kw`, hàm này nhận `st` = giá trị rác còn
sót trong `x0` (đúng bằng ký tự vừa lex), rồi SEGV ở `str x2, [x0, x1]`.

Cách sửa: luôn emit epilogue cuối hàm. Epilogue thừa sau một `ret` thật chỉ là code
chết, vô hại.

**Chẩn đoán:** `did_ret` là cờ per-function nhưng ngữ nghĩa cần là per-instruction.
Nếu sau này tối ưu lại, điều kiện đúng là "op cuối cùng của thân hàm có phải `Ret`
không", chứ không phải "có `Ret` nào không".

### 2. Hằng số bị cắt còn 16 bit — `virc_boot.vri:18066`, `:19309`, `:21967`

`boot_cg_movz0` chỉ phát một lệnh `MOVZ`, và cả hai vòng emit còn chủ động mask
`immv bit_and 65535` trước khi gọi. Mọi hằng số lớn hơn `0xFFFF` mất phần cao.

Triệu chứng: Stage-1 phát `0xFEEDFACF` thành `0xFACF` (header Mach-O hỏng) và mọi
word lệnh ARM64 nó sinh ra (`0xA9B07BFD`, …) đều sai.

Cách sửa: bỏ mask, cho `boot_cg_movz0` phát `MOVZ` + một `MOVK` cho mỗi halfword
khác 0.

**Cạm bẫy:** `boot_cg_movz0` **phải giữ nguyên dạng chỉ-dùng-global**. Bản đầu tiên
tôi viết dùng `let rd0 = …; let imm0 = …` thì C-VM nuốt mất các lệnh gán
`g_emit_word`, làm mọi `MOVZ` biến mất và hỏng entry stub (`_start` mất `mov x0,#0`,
`mov x2,#3`, … chỉ còn lệnh trước đó lặp lại ba lần). Scratch cho việc tách halfword
nằm ở `g_cg_immw` / `g_cg_rdw` / `g_cg_hw` (khai báo cạnh `g_cg_imm`).

### 3. `_rt_write` bị clobber, `write_bytes` nhảy sang `print` — `virc_boot.vri:16154`

`g_rt_write_off` bị clobber về 0 trước khi caller copy nó vào name-cell offset 472.
Offset 0 trỏ đúng vào đầu vùng runtime, tức `print_int`.

Triệu chứng: chương trình in ra một con số dài (con trỏ path, đổi mỗi lần chạy vì
ASLR) rồi exit 0 mà không tạo file nào.

Cách sửa: ghi sticky ngay trong `emit_runtime_arm64`, đúng cách `_rt_alloc` vẫn làm
với cell 496. Hai chỗ ghi cell 472 ở ngoài giờ chỉ điền khi cell còn 0.

**Chẩn đoán:** khi một offset runtime "biến mất", so sánh địa chỉ đích của `bl` với
bảng địa chỉ các hàm runtime. Nhảy vào đúng đầu vùng runtime nghĩa là offset = 0.

### 4. Mode file 0644 — `virc_boot.vri:16165`

`_rt_write` mở file với mode `0x1A4` (0644), nên binary sinh ra không chạy được.
Đã đổi sang `0x1ED` (0755).

### 5. `let` trong thân `when` / lower vòng lặp (một phần)

Hai nguyên nhân đã xử lý, cộng một lỗi sâu hơn vẫn mở:

1. **`g_boot_var_name` còn gắn tên LHS lúc lower init** — `let p2 = st_get(st, 2)`
   giải `st` thành chính `p2` (vreg mới, chưa ghi) → đọc "stale self". Đã
   `boot_set_var_name(0)` ngay sau khi bind tên trong `VarDecl` (cùng fix với lỗi 6).
2. **`fresh_label` dùng `ctx.label_counter`** — entity field không tin cậy trên
   C-VM (cùng anti-pattern với `fresh_vreg` cũ). Đã chuyển sang `g_boot_label_cell`,
   reset trong `boot_reset_vregs`.
3. **`parse_block` lồng nhau clobber `g_boot_blk_*`** — đã thêm
   `boot_blk_push_scope` / `pop_scope` + `g_boot_fin_*` để `boot_func_blk_snap_at`
   vẫn thấy đúng thân FuncDef sau khi pop.

**Đã sửa (2026-07-26 tối):** hai lỗi xếp chồng khi lower `when`/`while`:

1. **`LowerCtx.loop_start_labels` / `loop_end_labels` / `loop_depth`** — entity
   field offset trên C-VM trả về con trỏ vec rác → `vec_push_rt` SEGV ngay khi
   vào thân `WhileStmt`. Cùng anti-pattern với `next_vreg` / `label_counter`.
   Đã chuyển sang `boot_loop_push` / `pop` / `cur_start` / `cur_end` (native
   heap + `g_boot_loop_depth`), reset trong `boot_reset_vregs`. `break`/`continue`
   dùng API này.
2. **`Assign` trong thân vòng** — `Token.str_val` / `AstNode.name` bị clobber
   trước khi vào `boot_blk_*`, nên `sym_lookup` fail và `n = n + 1` không ghi
   → vòng vô hạn. Fix: lookahead `IDENT '='` chụp `peek(p).str_val` trước
   `advance`/`parse_expr`; đặt `name` sau `ast_add_child`; lower fallback
   `boot_vmap_get` khi SymTable miss (cùng đường `PrintStmt`).

Regression: `cg_when.vri` → `3`, `cg_when_assign.vri` → `7`.

### 6. `let x = call(st, …)` mở đầu hàm giải sai tham số — **ĐÃ SỬA GỐC**

`lower_expr` Identifier **ghi đè vô điều kiện** `expr.name` bằng
`boot_get_var_name()` (tên LHS của câu `let` đang lower). Khi lower
`let site = st_get(st, 9)`, argument `st` bị đổi thành `"site"` → đọc đúng slot
của local mới (rác) thay vì param.

Cách sửa: chỉ fallback sang `boot_get_var_name()` khi `sym_lookup_both(expr.name)`
**đã thất bại**; và clear `var_name` trước khi lower init của `VarDecl`.

Regression: `tests/bootstrap_codegen/cg_let_call_arg.vri` → `42`.
Stage-1 đã bỏ workaround st-slot ở `emit_bl` / `emit_bl_later` / `emit_entry`
(`let site = st_get(st, 9)` chạy đúng; `ldr` từ `[x29,#0x10]`).

**Lưu ý còn lại:** `let d = (target - site) / 4` (BinOp lồng trong init) vẫn bị
parse-time vconst fold thành `0` → `bl #0` treo. `emit_bl` dùng biểu thức inline
một tầng thay vì `let d` trung gian.

---

## Layout Mach-O tối thiểu mà codesign chấp nhận — `virc_stage1.vri:777`

Bản `write_macho` đầu của Stage-1 chỉ phát 4 load command. Kết quả: `file` nhận ra
Mach-O nhưng `codesign` từ chối với *"main executable failed strict validation"*, và
kernel giết tiến trình (exit 137) vì trên Apple Silicon mọi binary đều phải được ký.

Hai điều kiện bắt buộc:

- **`sizeofcmds` phải khớp chính xác** tổng `cmdsize` của các load command. Sai 8 byte
  là `otool -l` báo *"Inconsistent sizeofcmds"*.
- **Phải có segment `__LINKEDIT`**, vì codesign nối chữ ký vào đó. Không có nó thì
  không ký được, mà không ký thì không chạy được.

Layout đang dùng, sao chép từ `macho_emit` của Stage-0 — 10 load command, 552 byte,
cộng 32 byte đệm để codesign chèn `LC_CODE_SIGNATURE`, nên code bắt đầu ở offset 616:

| Offset | Load command | cmdsize |
|--------|--------------|---------|
| 32  | `__PAGEZERO` | 72 |
| 104 | `__TEXT` + section `__text` | 152 |
| 256 | `__LINKEDIT` | 72 |
| 328 | `LC_DYLD_CHAINED_FIXUPS` | 16 |
| 344 | `LC_SYMTAB` | 24 |
| 368 | `LC_DYSYMTAB` | 80 |
| 448 | `LC_LOAD_DYLINKER` | 32 |
| 480 | `LC_UUID` | 24 |
| 504 | `LC_MAIN` | 24 |
| 528 | `LC_LOAD_DYLIB` | 56 |

Payload `__LINKEDIT` là 52 byte: header dyld chained fixups rỗng (48) + string table
rỗng (4).

---

## Chẩn đoán: cách lần ra lỗi trong binary Stage-1

Binary Stage-1 không có symbol nên `bt` của lldb vô dụng. Quy trình đã dùng:

1. **Dựng bảng hàm**: mọi hàm người dùng bắt đầu bằng `sub sp, sp, #0x4, lsl #12`
   (frame 16KB). Lọc `otool -tV` theo pattern đó rồi ghép theo thứ tự khai báo
   trong source.
2. **Unwind thủ công**: prologue là `stp x29, x30, [sp]; mov x29, sp`, nên `[fp]` là
   fp của caller và `[fp+8]` là địa chỉ trả về. Lặp theo chuỗi đó dựng lại stack.
   Script mẫu: `/tmp/unwind.py` trong phiên debug.
3. **Bisect bằng `exit_prog(N)`**: chèn `exit_prog` với mã khác nhau để định vị dòng
   crash. Hữu ích hơn `print` vì `print` có thể clobber state. Có thể mã hoá dữ liệu
   vào mã thoát (ví dụ `exit_prog(st_get(st, 2))` để lấy vị trí con trỏ nguồn).
4. **Bẫy không-tiến**: với vòng lặp treo, lưu con trỏ ở đầu thân vòng và so sánh ở
   cuối; nếu bằng nhau thì thoát kèm token hiện tại. Mẫu ở `virc_stage1.vri:717`.

---

## Việc còn lại

1. Parse-time vconst fold nuốt BinOp lồng (`let d = (a - b) / 4` → 0).
2. `cg_global` không in gì — lỗi có sẵn, chưa điều tra.
3. `let` store trong thân `when` trên C-VM vẫn mỏng — Stage-1 nên giữ st-slot
   cho vòng lex phức tạp dù Assign đơn giản đã chạy.
4. Mở rộng `parse_expr_to`: hiện chỉ đủ cho `cg_call` (số, gọi hàm một đối số, biến
   local, chuỗi `+`). Local được giả định luôn nằm ở `fp+16`.
5. `write_macho` của Stage-1 cố định `text_seg = 16384`; cần page-align theo
   `code_size` khi input lớn hơn.
6. Stage-1 tự biên dịch chính nó (Stage-2).
