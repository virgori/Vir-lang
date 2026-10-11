---
id: "VIRC-PLN-0043"
type: "PLAN"
domain: "VIRC"
title: "Enforce fail-closed private by default module export contract on selective import"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
  - "tooling"
components:
  - "module-resolution"
  - "import-expander"
  - "diagnostics"
  - "stdlib"
related:
  issues:
    - "VIRC-ISS-0008"
  plans: []
  reports:
    - "VIRC-RPT-0060"
supersedes: null
superseded_by: null
tags:
  - "modules"
  - "import"
  - "export"
  - "encapsulation"
  - "e2113"
---

# VIRC-PLN-0043 — Enforce fail-closed private by default module export contract on selective import

## 1. Objective

Triển khai quy tắc fail-closed private-by-default cho selective import (`import symbol from module`) theo đúng đặc tả `VIR-SPC-0014`: mọi khai báo trong module là private mặc định; việc selective import chỉ thành công khi symbol được liệt kê tường minh trong mệnh đề `export` của module đích. Module không có `export` được coi là có bề mặt public rỗng và mọi selective import vào module này phải bị từ chối với mã lỗi chuẩn `E2113`. Đồng thời chuẩn hoá diagnostic format hiển thị rõ ràng symbol được yêu cầu và module identity, bổ sung khai báo `export` đầy đủ cho các module nền tảng hiện hữu trong compiler và stdlib.

## 2. Source Issues

- **VIRC-ISS-0008**: Selective import imports non-exported declarations when module has no export declarations.

## 3. Scope

### In Scope

- Loại bỏ nhánh fallback tương thích cũ `if text_has_any_export(body) == 0 do out 1 end` trong `compiler/src/main/import_expander.vri`.
- Truy vết và lưu trữ symbol bị từ chối (`g_imp_failed_sym`), chuẩn hoá thông báo lỗi `E2113` hiển thị cả tên symbol và module identity (`imported symbol not exported: '<symbol>' from module '<mod>'`).
- Khắc phục lỗi ép kiểu con trỏ thô sang fat string slice tại các điểm phát sinh early error trong `compiler/src/main/import_expander.vri`.
- Bổ sung khai báo `export` tường minh cho tập hợp 45 module nền tảng trong `compiler/src/` và `stdlib/vir/` hiện chưa có `export`.
- Bổ sung test fixture và unit test kiểm tra toàn diện hợp đồng selective import: module không có export, module có export từng phần, preceding include không thể bypass export check.
- Tự biên dịch compiler qua fixed-point bootstrap và kiểm thử toàn bộ test suites.

### Out of Scope

- Cơ chế umbrella/wildcard import (`import from module` / `import * from module`) được quản lý riêng bởi `VIRC-ISS-0046`.
- Ngữ nghĩa namespace include (`include mod`) được quản lý bởi `VIRC-ISS-0007`.
- Lexical shadowing của biến cục bộ bên trong thân hàm.

## 4. Current Architecture

Trong kiến trúc tiền xử lý module hiện tại (`compiler/src/main/import_expander.vri`):
1. `text_has_export(body, fname)` kiểm tra xem symbol `fname` có được export trong module `body` hay không.
2. Tuy nhiên, ở đầu hàm có đoạn mã:
   ```vir
   func text_has_export(body: int, fname: int):
       if text_has_any_export(body) == 0 do
           out 1
       end
       ...
   ```
   Nếu module đích không chứa bất kỳ từ khoá `export` nào, hàm lập tức trả về `1` (cho phép import mọi thứ). Điều này phá vỡ tính đóng gói: bất kỳ hàm private nội bộ nào cũng có thể bị module khác selective import tự do nếu module đó chưa từng định nghĩa `export`.
3. Khi `text_build_import_body` phát hiện không có export (chỉ xảy ra khi module ĐÃ CÓ export nhưng không chứa symbol yêu cầu), nó gọi `inc_set_error(2113)` và báo lỗi qua `inc_report_early_error(2113, cur_file, cur_line, native_read_i64(g_imp_mod as i64, 0) as string)`.
   Đoạn gọi này truyền pointer cast sang string slice, gây lỗi toạ độ/chiều dài chuỗi và truyền module name thay vì symbol name.
4. Nhiều module nền tảng trong `stdlib/vir/` (như `core/option.vri`, `core/vec.vri`, `core/result.vri`) và `compiler/src/rt/` được viết từ giai đoạn bootstrap ban đầu trước khi có kiểm tra export, nên hiện tại đang thiếu câu lệnh `export`.

## 5. Proposed Architecture

### 5.1. Khắt khe hoá quy tắc Fail-Closed Private by Default

- Trong `compiler/src/main/import_expander.vri`:
  ```vir
  func text_has_export(body: int, fname: int):
      if text_has_any_export(body) == 0 do
          out 0
      end
      # Kiểm tra tiếp fname trong danh sách export hoặc enum variant...
  ```
  Nếu module không có khai báo `export`, `text_has_export` trả về `0`, khiến việc selective import bất kỳ symbol nào đều thất bại ngay lập tức với mã lỗi `E2113`.

### 5.2. Chuẩn hoá Định dạng Chẩn đoán E2113

- Khai báo biến toàn cục `var g_imp_failed_sym = 0`.
- Khi `text_has_export(mod_body, sym) == 0` hoặc symbol không tồn tại trong thân module, lưu vết symbol vi phạm: `g_imp_failed_sym = sym`.
- Khi phát sinh lỗi `E2113`, định dạng message hoàn chỉnh chứa cả symbol và canonical module name:
  `'<symbol>' from module '<module>'`.
- `msg_frontend.vri` render thành:
  `imported symbol not exported: '<symbol>' from module '<module>'`.
  Thông tin này xuất hiện nhất quán trên cả chế độ terminal classic và `--json`.

### 5.3. Bổ sung `export` cho các Module Nền tảng

- Thêm các dòng `export <symbols...>` tường minh ở cuối mỗi module trong danh sách 45 module nền tảng (cả compiler runtime lẫn standard library), công khai đúng các API hợp lệ mà các module khác phụ thuộc vào.

## 6. Design Decisions

### Decision 1: Chuyển text_has_any_export(body) == 0 sang return 0 (Fail-Closed)

**Decision:** Khi một module không có bất kỳ câu lệnh `export` nào, `text_has_export` trả về `0` (không export gì cả).

**Rationale:** Tuân thủ triệt để `VIR-SPC-0014` và triết lý ngôn ngữ Vir (mọi khai báo là private mặc định). Fallback "không có export thì export tất cả" là tàn tích bootstrap ban đầu, vi phạm nghiêm trọng tính đóng gói của module.

**Alternatives considered:** Tạo cờ `allow_implicit_export` hoặc cảnh báo warning. Bị bác bỏ vì tạo ra hành vi không xác định và đi ngược lại chỉ đạo "không hardcode, không vá tạm".

### Decision 2: Kết hợp Symbol Name và Module Identity trong Diagnostic Payload

**Decision:** Truyền chuỗi kết hợp `format_sym_and_mod(sym, mod)` cho `inc_report_early_error(2113, ...)`.

**Rationale:** Người dùng cần biết chính xác cả hai thông tin: symbol nào bị từ chối và nó thuộc module nào. Việc chỉ hiển thị một trong hai gây khó khăn cho việc sửa lỗi và không thoả mãn Acceptance Criterion 5.

**Alternatives considered:** Chỉ hiển thị symbol. Bị bác bỏ vì khi import nhiều module cùng lúc, người dùng không biết module nào thiếu export.

## 7. Implementation Plan

### Phase 1 — Bổ sung khai báo `export` cho các module nền tảng
- Cập nhật 13 module trong `compiler/src/` (`compiler/src/rt/`, `bootstrap/prelude/`, `frontend/`, `diagnostic/`, v.v.).
- Cập nhật 32 module trong `stdlib/vir/` (`core/`, `mem/`, `rt/`, `str/`, `math/`, `io/`, v.v.).
- Đảm bảo tất cả các symbol đang được import hợp lệ đều nằm trong danh sách export của module tương ứng.

### Phase 2 — Thực thi quy tắc Fail-Closed trong `import_expander.vri`
- Sửa `text_has_export` để trả về `0` khi `text_has_any_export(body) == 0`.
- Ghi nhận `g_imp_failed_sym` và truyền chuỗi chẩn đoán rõ ràng cho `inc_report_early_error(2113, ...)`.
- Cập nhật `msg_frontend.vri` và `actions.vri` nếu cần để đảm bảo định dạng chẩn đoán chuẩn mực.

### Phase 3 — Đồng bộ, Biên dịch Bootstrap và Kiểm thử
- Chạy `python3 tools/sync_virc.py`.
- Tự biên dịch compiler: `./bin/virc compiler/src/entry.vri -o bin/virc.tmp && codesign -s - -f bin/virc.tmp && mv bin/virc.tmp bin/virc`.
- Chạy `./bin/cli-contract-test --virc ./bin/virc`.
- Chạy `./bin/module-resolver-test`.
- Chạy `./run_tests.sh min`.

### Phase 4 — Kiểm chứng các Fixture Nghiệm thu và Lập Báo cáo
- Viết test fixture kiểm chứng:
  1. Module không có `export`: import hàm private -> Bị từ chối với `E2113`, chỉ rõ symbol và module.
  2. Module có `export` một phần: import hàm không export -> Bị từ chối với `E2113`.
  3. Preceding `include` không thể vượt qua export check.
  4. Module có `export`: import hàm được export -> Biên dịch thành công.
- Tạo report `VIRC-RPT-0060`, cập nhật trạng thái `VIRC-ISS-0008` và `VIRC-PLN-0043`.
- Xác thực paper bằng `./paper validate`.

## 8. Compatibility

- **Source compatibility:** Các chương trình Vir tuân thủ chuẩn `export` sẽ hoạt động hoàn toàn bình thường. Các chương trình dựa dẫm vào kẽ hở import hàm private từ module thiếu export sẽ bị từ chối chính xác theo đúng đặc tả.
- **Diagnostic output:** Cải thiện độ chi tiết của mã lỗi `E2113`, giữ nguyên mã lỗi chuẩn.
- **Tooling compatibility:** LSP/IDE sẽ nhận được thông tin chẩn đoán chính xác hơn về symbol không được export.

## 9. Migration

Các module hiện hữu trong codebase Vir chưa có mệnh đề `export` cần được bổ sung mệnh đề `export <public_symbols...>` ở cuối file để công khai các API mong muốn.

## 10. Validation Plan

- Kiểm thử đơn vị tập trung với fixture tái hiện lỗi của `VIRC-ISS-0008`.
- Chạy `./bin/cli-contract-test --virc ./bin/virc` kiểm tra 21 hợp đồng CLI.
- Chạy `./bin/module-resolver-test` kiểm tra 20 hợp đồng module resolution.
- Chạy `./run_tests.sh min` kiểm tra 505 ca kiểm thử trong 31 nhóm của compiler.
- Xác thực toàn bộ VPS papers qua `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Module trong stdlib hoặc test bị thiếu symbol trong danh sách export | Trung bình | Cao | Dùng script quét toàn diện mọi câu lệnh import trong repo để bảo đảm danh sách export đầy đủ trước khi kích hoạt fail-closed |
| Lỗi parse export dạng nhiều dòng | Thấp | Trung bình | `text_has_export` đã hỗ trợ dấu phẩy và xuống dòng liên tục cho đến dòng trống tiếp theo |

## 12. Rollback Strategy

Nếu phát sinh hồi quy nghiêm trọng, khôi phục lại fallback `if text_has_any_export(body) == 0 do out 1 end` trong `import_expander.vri`, đồng bộ lại mã nguồn và rebuild compiler.

## 13. Exit Criteria

- [ ] Selective import từ module không có `export` bị từ chối với mã `E2113` ở vị trí import.
- [ ] Selective import symbol đã được export thành công mà không cần `include` đi kèm.
- [ ] Selective import symbol không được export bị từ chối dù module có export các symbol khác.
- [ ] Preceding include, alias hoặc path spelling không thể bypass quy tắc export.
- [ ] Chẩn đoán xác định rõ symbol và canonical module identity trên cả text và JSON modes.
- [ ] Tất cả 45 module nền tảng trong compiler và stdlib có khai báo `export` tường minh.
- [ ] Compiler tự bootstrap thành công, vượt qua 100% test suites (`cli-contract-test`, `module-resolver-test`, `run_tests.sh min`).
- [ ] Báo cáo nghiệm thu `VIRC-RPT-0060` được chấp thuận và `VIRC-ISS-0008` được đóng.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0008_selective_import_imports_non_exported_declarations_when_module_has_no_export_decla.md`
- `papers/VIR/specs/VIR-SPC-0014_module_and_import_resolution.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created initial implementation plan for VIRC-ISS-0008 |
