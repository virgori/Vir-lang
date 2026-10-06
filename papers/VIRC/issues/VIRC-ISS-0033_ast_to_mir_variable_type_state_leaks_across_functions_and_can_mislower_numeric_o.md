---
id: "VIRC-ISS-0033"
type: "ISSUE"
domain: "VIRC"
title: "AST-to-MIR variable type state leaks across functions and can mislower numeric operations"
status: "CLOSED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "lowering"
components:
  - "ast-to-mir"
  - "type-lowering"
  - "bootstrap"
related:
  issues: []
  plans:
    - "VIRC-PLN-0018"
  reports:
    - "VIRC-RPT-0034"
supersedes: null
superseded_by: null
tags:
  - "type-state"
  - "function-scope"
  - "miscompilation"
  - "release-gate"
---

# VIRC-ISS-0033 — AST-to-MIR variable type state leaks across functions and can mislower numeric operations

## 1. Summary

`ast_to_mir` lưu kiểu biến cục bộ trong các bảng toàn cục dùng chung cho mọi
hàm. Một tham số có kiểu ở hàm trước có thể làm biến trùng tên ở hàm sau bị hạ
kiểu sai, kể cả biến số bị hạ thành chuỗi và gây crash ở runtime.

## 2. Context

Các bảng `g_var_type_names`, `g_var_type_values`, `g_var_type_hash`,
`g_dict_var_names` và `g_dict_var_hash` được tạo một lần khi gắn AST chương
trình. `ast_lower_func` không mở scope mới trước khi ghi kiểu tham số và biến
cục bộ của từng hàm.

## 3. Expected Behavior

Thông tin kiểu của tham số và biến cục bộ chỉ có hiệu lực trong hàm đang hạ.
Tên `s` ở hai hàm độc lập không được chia sẻ kiểu.

## 4. Actual Behavior

Sau khi hạ `seed_type_name(s: string)`, phép gán `s = 1` trong `main` vẫn tra
được kiểu `string`. Phép cộng `s + 2` bị chọn đường nối chuỗi; chương trình được
biên dịch thành công nhưng binary thoát bằng tín hiệu 139/`EXC_BAD_ACCESS`.

## 5. Reproduction

Fixture tối thiểu nay nằm tại
`tests/bootstrap_codegen/cg_function_type_scope_isolation.vri`:

1. Khai báo hàm đầu có tham số `s: string`.
2. Trong `main`, gán `s = 1` rồi `print s + 2`.
3. Biên dịch và chạy bằng compiler trước bản sửa.

Kỳ vọng là `3`; hành vi lỗi là crash runtime. Đổi tên biến trong `main` chỉ né
lỗi và không sửa nguyên nhân.

## 6. Evidence

- Reproducer tối thiểu biên dịch thành công nhưng binary cũ thoát 139.
- Control không có hàm `seed_type_name` in `3`, cô lập ảnh hưởng theo tên.
- Code audit xác nhận `g_var_type_hash` chỉ được khởi tạo ở cấp chương trình và
  được `ast_lower_func` tái sử dụng giữa các hàm.
- Sau bản sửa, fixture in `3`; bootstrap Stage 2 và Stage 3 có SHA-256 giống
  nhau.

## 7. Scope

### Affected

- AST-to-MIR local variable/parameter type lookup.
- Dictionary-variable marks cùng dùng tên cục bộ và cần được scope đồng bộ.
- Bootstrap compiler và mọi chương trình có tên biến lặp giữa các hàm.

### Not affected / Unknown

- Global declarations and function signatures are not moved into this local
  scope.
- HIR lowering is intentionally unchanged: the current AST-to-HIR form does
  not yet preserve every local type fact needed to rebuild this table per HIR
  function.

## 8. Impact

Đây là lỗi đúng đắn lõi: source hợp lệ có thể được compiler chấp nhận nhưng
sinh mã gọi sai runtime operation và crash. Workaround đổi tên biến không thể
bảo vệ source người dùng nói chung, vì vậy issue được xếp S1/P1.

## 9. Preliminary Analysis

- **CONFIRMED:** bảng kiểu local của AST-to-MIR tồn tại xuyên hàm và lookup theo
  tên thuần, không theo function identity.
- **CONFIRMED:** reset các bảng local trước mỗi `ast_lower_func` làm reproducer
  in `3` và không phá bootstrap fixed point.
- **OBSERVED:** lỗi trước sửa biểu hiện bằng `str_cat` trên giá trị số và
  `EXC_BAD_ACCESS`.
- **NOT_VERIFIED:** HIR có thể chuyển sang cùng mô hình reset chỉ sau khi IR đó
  giữ đủ type facts; thay đổi đó nằm ngoài issue này.

## 10. Acceptance Criteria

- [x] AST-to-MIR tạo type/dictionary state mới ở đầu mỗi hàm.
- [x] Reproducer tên biến trùng giữa hai hàm in `3`, không crash.
- [x] Regression fixture được nối vào `run_tests.sh`.
- [x] Compiler tự host đạt Stage 2 = Stage 3.
- [x] Binary phát hành báo phiên bản `4.2.1` và được ký hợp lệ.
- [x] REPORT xác minh được ACCEPTED trước khi đóng issue.

## 11. Related Papers

### Issues

- None.

### Plans

- VIRC-PLN-0018 — Scope AST-to-MIR variable type state per function and add
  release regression gates.

### Reports

- VIRC-RPT-0034 — Function-scoped AST-to-MIR type state and virc 4.2.1
  verification report (ACCEPTED/READY_FOR_CLOSE).

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Ghi nhận reproducer, root cause, phạm vi và acceptance criteria; chuyển VERIFYING |
| 2026-10-04 | Linked VIRC-PLN-0018 |
| 2026-10-04 | Đóng issue sau khi VIRC-RPT-0034 được ACCEPTED với READY_FOR_CLOSE |
| 2026-10-04 | Linked VIRC-RPT-0034 |
