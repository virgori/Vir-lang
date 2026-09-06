# Trình Theo Dõi & Checklist Lỗi Trình Biên Dịch Vir (`virc`)

Tài liệu này ghi nhận và theo dõi tiến độ xử lý toàn diện mọi lỗi (bugs), chẩn đoán (diagnostics), hạn chế thiết kế (limitations) và quá trình nâng cấp bootstrap độc lập cho trình biên dịch Vir (`virc`).

---

## 1. Nhóm I: Báo Cáo Kỹ Thuật InterVir (Bugs & Limitations - Categories A - I)

| STT | Mã / Hạng mục | Mô tả lỗi & Triệu chứng | Phân loại | Tình trạng | Regression Test & Ghi chú |
|:---:|:---|:---|:---|:---:|:---|
| 1 | **Bug 1 (Cat A)** | Struct Field Offset Collision: Bảng offset phẳng toàn cục không phân vùng theo kiểu struct (`TypeName::FieldName`) gây đọc sai offset trường trùng tên. | Compiler Bug (Critical) | **[x] ĐÃ FIX** | `test_struct_field_offset_scoped_by_type.vri`<br>`test_struct_field_same_name_diff_offset.vri`<br>`test_struct_field_three_entities.vri`<br>`test_struct_field_boundary_read_write.vri`<br>*(4/4 PASS)* |
| 2 | **Bug 2 (Cat B)** | Aggregate Return ABI: Hàm trả về struct chứa `string` làm hỏng con trỏ chuỗi hoặc crash runtime do quản lý indirect return buffer (`x8`) và stack callee. | ABI Bug (Critical) | **[x] ĐÃ FIX** | `test_aggregate_return_string_field_preserved.vri`<br>`test_aggregate_return_string_int_combos.vri`<br>`test_aggregate_return_large_entity.vri`<br>*(3/3 PASS)* |
| 3 | **Bug 3 (Cat C)** | Struct Natural Alignment: Cộng dồn offset tuần tự thiếu căn chỉnh 8-byte padding tự nhiên khi xen kẽ `string` và kiểu số nguyên thủy. | Layout Bug (High) | **[x] ĐÃ FIX** | `test_struct_layout_string_int_alignment.vri`<br>`test_struct_layout_alternating_fields.vri`<br>*(2/2 PASS)* |
| 4 | **Bug 4 (Cat D/E)** | Parser không chặn từ khóa dành riêng `port` ở vị trí identifier (tham số, biến, hàm) mà thả trôi xuống codegen gây lỗi/crash. | Parser / Diagnostic | **[x] ĐÃ FIX** | `test_reserved_keyword_port_rejected_as_parameter.vri`<br>`test_reserved_keyword_port_rejected_as_local_var.vri`<br>`test_reserved_keyword_port_rejected_as_function_name.vri`<br>`test_reserved_keywords_rejected_as_identifiers.vri`<br>`test_parameter_same_name_as_entity_field_allowed.vri`<br>*(5/5 PASS)* |
| 5 | **Limitation 1 (Cat F)** | Ngữ nghĩa Value Copy khi index mảng struct: Gán hoặc index struct thực hiện copy giá trị, mutate trên bản copy không ảnh hưởng mảng gốc. | Semantic / Design | **[x] ĐÃ XÁC NHẬN** | `test_value_copy_struct_indexing.vri`<br>*(1/1 PASS - Đúng đặc tả)* |
| 6 | **Limitation 2 (Cat G)** | Số học nguyên 64-bit tràn số bọc vòng theo chuẩn bù 2 (Two's complement wrapping) không sinh exception. | Semantic / Runtime | **[x] ĐÃ XÁC NHẬN** | `test_int64_overflow_wrapping.vri`<br>*(1/1 PASS - Đúng đặc tả)* |
| 7 | **Limitation 5** | Binary Mach-O sinh ra trên macOS ARM64 thiếu ad-hoc signature dẫn đến kernel gửi `SIGKILL 9`. | Toolchain / Packaging | **[x] ĐÃ FIX** | Tích hợp tự động ký mã qua `virc_sign` / `codesign -s -`. |
| 8 | **Limitation 7 (Cat H)** | Parser chưa hỗ trợ truy xuất thuộc tính đa cấp (`a.b.c`). | Grammar Limitation | **[x] ĐÃ FIX** | `test_member_access_chain.vri`<br>*(1/1 PASS)* |
| 9 | **Limitation 8 (Cat I)** | Lexer xử lý ranh giới literal số nguyên `INT64_MAX` (0x7FFFFFFFFFFFFFFF). | Lexer Boundary | **[x] ĐÃ FIX** | `test_int_literal_boundary.vri`<br>*(1/1 PASS)* |

---

## 2. Nhóm II: Lỗi Test Suite (`./run_tests.sh`)

| STT | Tên Test / Thành phần | Nguyên nhân gốc rễ (Root Cause) | Tình trạng | Chi tiết xử lý |
|:---:|:---|:---|:---:|:---|
| 1 | `test_adv_046_entity_mutate.vri`<br>`test_entity_full.vri`<br>`test_entity_advanced.vri`<br>`test_entity_paren.vri` | Bộ tối ưu MIR (`mir_opt.vri`) coi `MirOp.Load` là biểu thức thuần không có side-effect trong GVN và LICM, dẫn đến di chuyển hoặc triệt tiêu lệnh đọc bộ nhớ khi đối tượng bị mutate giữa chừng. | **[x] ĐÃ FIX** | Loại bỏ `MirOp.Load` khỏi GVN và LICM trong `mir_opt.vri`. |
| 2 | `test_bind.vri` | (1) Biến `child_count` bị conflict giữa số param và số stmts.<br>(2) Bảng shadow name `ast_to_mir.vri` kiểm tra `if old_v > 0` thay vì `if old_v >= 0`, khiến biến ở slot 0 bị coi là không tồn tại và gán nhầm id. | **[x] ĐÃ FIX** | Sửa định danh `stmt_count` và sửa guard `if old_v >= 0 do`. |
| 3 | `test_adv_005_shift.vri`<br>`test_adv_007_bitops_edge.vri` | (1) Cú pháp test case chứa token sai quy cách.<br>(2) Đếm bit leading zero kỳ vọng toán học 1 bit cao nhất. | **[x] ĐÃ FIX** | Chuẩn hóa cú pháp test và cập nhật kỳ vọng trong runner. |
| 4 | `test_method.vri` | Lỗi phân giải và hạ mã phương thức bên trong `EntityDef` (`method name -> type:`) dẫn đến crash Segmentation Fault: 11 khi biên dịch. | **[ ] ĐANG XỬ LÝ** | Cần hoàn thiện cú pháp và hạ mã AST cho method inline trong entity. |

---

## 3. Nhóm III: Sửa Lỗi Native Include/Bootstrap & virc 2.3.0 (Bỏ Phụ Thuộc Python)

> **Mục tiêu:** Loại bỏ hoàn toàn sự phụ thuộc vào script Python (`virc-expanded.vri`, build script) trong chuỗi tự dựng trình biên dịch. Đạt điểm bất động (fixed point): Seed → G1 → G2 → G3, với `cmp G2 G3` trùng khớp 100% từng byte.

### Phạm vi & Kỷ luật nghiêm ngặt:
- [x] Tạo thư mục thử nghiệm duy nhất: `frozen/experimental/v2.3.0-bootstrap/` sao chép từ `frozen/release/v2.2.0/`.
- [x] Tuyệt đối không sửa `frozen/release/v2.2.0/` gốc.
- [x] Chỉ thao tác và chạy trong thư mục thử nghiệm.
- [x] Tuyệt đối không dùng script Python để preprocess, build hay kiểm chứng.
- [x] Không nghiệm thu dựa trên exit 0 đơn thuần; bắt buộc kiểm tra `cmp` nhị phân.

### Danh mục Bằng chứng lỗi & Hạng mục sửa chữa:

| Bằng chứng | Mô tả kỹ thuật | Trạng thái xác minh | Trạng thái sửa chữa | Ghi chú kỹ thuật |
|:---:|:---|:---:|:---:|:---|
| **E1** | Build trực tiếp `stdlib/vir/compiler/virc.vri` bằng `bin/virc` tạo được G1, nhưng G1 tự build tiếp thì `SIGSEGV`. | [ ] Chưa xác minh | [ ] Chưa sửa | Thử nghiệm trên bản copy `frozen/experimental/v2.3.0-bootstrap/`. |
| **E2** | Syscall macOS ARM64 (`svc #0x80`) báo lỗi qua **cờ Carry (C flag)** thay vì trả số âm. `emit_lir_rt_syscall_stub` trả thẳng kết quả `x0`, còn `file_open_read` chỉ kiểm tra `fd < 0`, nên nhận nhầm `x0 = 2` (ENOENT) là file descriptor hợp lệ. | [ ] Chưa xác minh | [ ] Chưa sửa | Sửa stub syscall trên macOS kiểm tra cờ carry (`b.cc 1f; neg x0, x0; 1:` hoặc `cset`), giữ nguyên hành vi Linux. |
| **E3** | `file_open_read` khi mở file thất bại vẫn cấp phát chuỗi rỗng và trả về thành công; module resolver đánh dấu file là đã include. | [ ] Chưa xác minh | [ ] Chưa sửa | Trả về mã lỗi rõ ràng, không coi chuỗi rỗng là thành công, không đánh dấu đã include khi thất bại. |
| **E4** | `codegen.vri` không được nạp dẫn đến mất toàn bộ định nghĩa bên trong (ví dụ `TargetArch`). | [ ] Chưa xác minh | [ ] Chưa sửa | Module resolver phải fallback đúng đường dẫn `stdlib/vir/...` và báo lỗi dừng biên dịch nếu thiếu. |
| **E5** | Chuỗi build dùng `virc-expanded.vri` che giấu lỗi include do đã dùng Python gộp sẵn file từ trước. | [ ] Chưa xác minh | [ ] Chưa sửa | Xóa bỏ `virc-expanded.vri` trong đường build, bắt buộc build trực tiếp từ `stdlib/vir/compiler/virc.vri`. |
| **E6** | Khi enum/symbol không tìm thấy trong hằng số/bảng symbol, compiler sinh mã null dereference (`mov x20, #0; ldr x19, [x20]`) thay vì báo lỗi biên dịch dừng lại. | [ ] Chưa xác minh | [ ] Chưa sửa | Bắt buộc kiểm tra symbol resolution; từ chối và báo lỗi có vị trí dòng/cột cụ thể nếu không giải quyết được enum/symbol. Cấm vá cứng riêng cho `TargetArch`. |

### Chuỗi Nghiệm Thu Chuẩn (Verification Pipeline):
1. **Bootstrap Chain:** Seed (`bin/virc`) → G1 → G2 → G3.
2. **Byte-by-Byte Match:** `cmp bin/virc-g2 bin/virc-g3` (hoặc so sánh SHA256 trước khi ký mã).
3. **Test Suite:** Binary G3 biên dịch và chạy thành công test suite mà không có lỗi hồi quy.
