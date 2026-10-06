---
id: "VIRC-RPT-0034"
type: "REPORT"
domain: "VIRC"
title: "Function-scoped AST-to-MIR type state and virc 4.2.1 verification report"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "lowering"
  - "release"
components:
  - "ast-to-mir"
  - "hir"
  - "bootstrap"
  - "test-gates"
related:
  issues:
    - "VIRC-ISS-0033"
  plans:
    - "VIRC-PLN-0018"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "type-state"
  - "function-scope"
  - "self-host"
  - "4.2.1"
---

# VIRC-RPT-0034 — Function-scoped AST-to-MIR type state and virc 4.2.1 verification report

## 1. Executive Summary

Đã sửa lỗi type state cục bộ của AST-to-MIR tồn tại xuyên function boundary.
State local nay được tạo mới cho mỗi hàm, trong khi type facts cấp chương trình
được giữ trong baseline riêng và được seed lại có kiểm soát. Reproducer từng
crash nay in `3`.

Compiler đã được nâng lên `4.2.1`, bootstrap sạch ba stage, và đạt fixed point:
Stage 2, Stage 3 và `bin/virc` cùng SHA-256
`d7ce778c898cacb8e44ef5b9671d703f99bd92120fa165045728f868cc5d3199`.

## 2. Source Issues

- VIRC-ISS-0033

## 3. Source Plans

- VIRC-PLN-0018

## 4. Implementation Summary

1. Thêm `reset_var_type_scope()` và gọi ở đầu mỗi `ast_lower_func`.
2. Tách type facts field cấp chương trình sang `g_program_var_type_*`; mỗi local
   scope mới được seed từ baseline này thay vì tái sử dụng local facts của hàm
   trước.
3. Khai báo return type cho HIR constructors và AST-to-HIR entry points để
   compiler source không còn vô tình dựa vào stale type facts khi tự host.
4. Thêm regression `cg_function_type_scope_isolation.vri`, nối module tests,
   dependency graphs và native compiler-project ingestion vào group 3.
5. Nâng version/baselines lên 4.2.1, đồng bộ generated bundle, bootstrap ba
   stage và thay `bin/virc` bằng Stage 3 đã ký.

## 5. Changes by Component

### `compiler/src/lower/ast_to_mir/context.vri` và `func.vri`

- change: tách program baseline khỏi per-function maps và reset local maps tại
  function boundary.
- reason: lookup theo tên thuần không được phép thấy tham số/biến của hàm trước.
- impact: loại bỏ mislower số thành chuỗi mà vẫn giữ field layout facts.

### `compiler/src/ir/hir/hir.vri` và `compiler/src/lower/ast_to_hir.vri`

- change: bổ sung return type `HirNode`, `HirFunc` và `i64` cho constructors và
  lowering entry points.
- reason: làm type flow self-contained sau khi bỏ stale cross-function facts.
- impact: Stage 2 giữ đúng HIR behavior; typed và untyped controls đều in `3`.

### Tests, driver metadata và release artifacts

- change: thêm regression, mở rộng group 3, nâng version/baselines, sync bundle,
  build và ký `bin/virc_stage1..3` cùng `bin/virc`.
- reason: biến root fix và project ingestion thành repository gates tái lập.
- impact: binary phát hành báo `virc 4.2.1 (self-hosted)`.

## 6. Deviations from Plan

Bootstrap lần đầu sau khi chỉ reset local maps cho thấy Stage 1 chạy HIR control
đúng nhưng Stage 2 sai. Điều tra xác nhận hai dependency ẩn trước đó:

- field type facts cấp chương trình đang dùng chung storage với locals;
- HIR constructors/entry points thiếu return type và compiler source từng dựa
  vào stale facts để hạ field access.

Thực tế triển khai vì vậy bổ sung program baseline và explicit HIR return types.
Candidate lỗi không được phát hành; toàn bộ bootstrap và validation được chạy
lại sau sửa.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| AST function-scope reproducer | PASS | output `3`, exit 0 |
| HIR typed control | PASS | output `3`, exit 0 |
| HIR untyped reproducer | PASS | output `3`, exit 0 |
| `run_tests.sh 3` | PASS | 13/13, gồm native compiler project ingestion |
| `run_tests.sh 5` | PASS | 46/46 |
| CLI contract | PASS | 43/43 |
| Architecture/dependency checks | PASS | 3 orchestrators, 316 dependencies |
| Generated bundle sync check | PASS | source modules identical to bundle |
| Bootstrap Stage 2 vs Stage 3 | PASS | byte-identical, cùng SHA-256 |
| Binary version/signature | PASS | 4.2.1, strict codesign verify |
| Broader `run_tests.sh min` | FAIL | 390/424; 34 failures outside this issue's acceptance gates |

### Regression

Reproducer tối thiểu được chạy trên binary phát hành, không chỉ compiler trung
gian. Module group còn biên dịch `compiler/src/entry.vri` thành một compiler mới
và chạy `--version`, nên dependency closure và native ingestion là executable
gate.

Suite `min` toàn repository chưa xanh trên checkout hiện tại. Đối chiếu bằng
`bin/virc_bootstrap` 4.2.0 cho cùng 15/149 memory-contract failures và cùng các
lỗi đại diện `E3021` (`result.vri:147`) / `E3051` ở các nhóm khác. Report này
không quy 34 lỗi nền đó thành regression của type-scope fix, đồng thời không
tuyên bố đã giải quyết chúng.

### Conformance

- `tools/sync_virc.py --check`: PASS.
- `tools/check_pass_architecture.py`: PASS.
- `tools/check_module_dependencies.py --verbose`: PASS, 316 source files.
- `cmp bin/virc_stage2 bin/virc_stage3`: PASS.
- `codesign --verify --strict bin/virc`: PASS.

## 8. Acceptance Criteria

- [x] AST-to-MIR tạo type/dictionary state mới ở đầu mỗi hàm.
- [x] Reproducer tên biến trùng giữa hai hàm in `3`, không crash.
- [x] Regression fixture được nối vào `run_tests.sh`.
- [x] Compiler tự host đạt Stage 2 = Stage 3.
- [x] Binary phát hành báo phiên bản `4.2.1` và được ký hợp lệ.
- [x] REPORT xác minh được ACCEPTED trước khi đóng issue.

## 9. Known Limitations

HIR lowering chưa được chuyển sang reset map tại từng `hir_lower_func`; thay đổi
này bị giới hạn có chủ ý ở AST-to-MIR. Cả typed control và chính reproducer
untyped đều pass qua `--hir`, nên không có HIR defect đã xác nhận còn mở trong
phạm vi report này.

Full repository `min` gate còn 34 failures trên working tree rộng hiện tại;
nhóm lỗi gồm UFCS/result resolution, out-parameter CFA, AI runtime và borrow
negative contracts. Các lỗi đối chiếu đại diện cũng có trên binary bootstrap
4.2.0 và không thuộc acceptance criteria của VIRC-ISS-0033.

## 10. Remaining Work

Không còn công việc bắt buộc cho VIRC-ISS-0033.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0033 — AST-to-MIR variable type state leaks across functions and
  can mislower numeric operations.
- VIRC-PLN-0018 — Scope AST-to-MIR variable type state per function and add
  release regression gates.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Ghi nhận root fix, candidate rejection, bootstrap fixed point và final validation; ACCEPTED/READY_FOR_CLOSE |
| 2026-10-04 | Bổ sung kết quả suite `min` 390/424 và đối chiếu bootstrap cho các failure ngoài phạm vi |
