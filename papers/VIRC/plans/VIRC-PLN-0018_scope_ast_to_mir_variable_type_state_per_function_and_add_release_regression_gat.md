---
id: "VIRC-PLN-0018"
type: "PLAN"
domain: "VIRC"
title: "Scope AST-to-MIR variable type state per function and add release regression gates"
status: "COMPLETED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "lowering"
  - "release"
components:
  - "ast-to-mir"
  - "bootstrap"
  - "test-gates"
related:
  issues:
    - "VIRC-ISS-0033"
  plans: []
  reports:
    - "VIRC-RPT-0034"
supersedes: null
superseded_by: null
tags:
  - "type-state"
  - "function-scope"
  - "self-host"
---

# VIRC-PLN-0018 — Scope AST-to-MIR variable type state per function and add release regression gates

## 1. Objective

Loại bỏ rò rỉ type state giữa các hàm ở AST-to-MIR, khóa lỗi bằng regression
test, xác minh bootstrap fixed point, và phát hành native compiler 4.2.1.

## 2. Source Issues

- VIRC-ISS-0033 — AST-to-MIR variable type state leaks across functions and
  can mislower numeric operations.

Không tạo PLAN không có lý do kỹ thuật rõ ràng.

## 3. Scope

### In Scope

- Tạo lại các bảng type và dictionary-local ở đầu mỗi `ast_lower_func`.
- Thêm reproducer nhỏ vào bootstrap-codegen gate.
- Nối kiểm tra registry/module graph và compiler-project ingestion vào test gate.
- Đồng bộ generated bundle, bootstrap 3 stage, ký và nâng binary lên 4.2.1.

### Out of Scope

- Không thay đổi syntax hoặc language specification.
- Không tái kiến trúc HIR type transport trong thay đổi này.
- Không xóa compatibility bundle hay Python tooling.

## 4. Current Architecture

`set_global_prog_ast` tạo các bảng kiểu một lần. `ast_lower_func` sau đó ghi
tham số/biến của từng hàm vào cùng state. Lookup chỉ dùng tên biến, nên cùng tên
ở hàm sau thừa hưởng kiểu hàm trước. HIR lowering cũng đọc type tables nhưng
AST-to-HIR chưa mang đủ metadata để có thể reset độc lập an toàn.

## 5. Proposed Architecture

`set_global_prog_ast` vẫn tạo state hợp lệ cho một lần compile, nhưng mỗi
`ast_lower_func` bắt đầu bằng `reset_var_type_scope()`. Type facts local không
thoát khỏi function boundary; global program state khác không đổi.

## 6. Design Decisions

### Decision 1 — Reset local lowering state at the function boundary

**Decision:** gom việc tạo mới năm bảng local vào `reset_var_type_scope()` và
gọi ở đầu AST-to-MIR lowering của từng hàm.

**Rationale:** function boundary là lifetime thực của type facts; sửa tại đây
bao phủ mọi tên biến thay vì duy trì danh sách workaround đổi tên.

**Alternatives considered:** key theo `(function, name)` và xóa từng entry khi
kết thúc hàm. Cả hai phức tạp hơn mà không đem lại lợi ích cho state local.

**Trade-offs:** cấp phát vài cấu trúc nhỏ mỗi hàm; đổi lại lookup đơn giản và
không còn stale state.

### Decision 2 — Do not reset HIR type state in this patch

**Decision:** giới hạn reset ở `ast_lower_func`.

**Rationale:** thử nghiệm kiểm soát cho thấy reset ở `hir_lower_func` làm mất
type fact mà HIR hiện chưa serialize đầy đủ. Giữ hành vi HIR hiện tại tránh tạo
hồi quy ngoài phạm vi.

**Trade-offs:** HIR type transport cần một issue riêng nếu muốn áp dụng cùng
mô hình trong tương lai.

## 7. Implementation Plan

### Phase 1 — Root fix

- files/modules: `compiler/src/lower/ast_to_mir/context.vri`,
  `compiler/src/lower/ast_to_mir/func.vri`.
- changes: thêm helper reset và gọi trước khi hạ mỗi hàm.
- dependencies: existing runtime vector/hash constructors.
- expected result: biến trùng tên giữa các hàm không chia sẻ type state.

### Phase 2 — Regression and project gates

- files/modules: `tests/bootstrap_codegen/`, `run_tests.sh`.
- changes: fixture tái hiện, module resolver/graph gate và native project build.
- expected result: lỗi type leak hoặc dependency-closure drift làm test thất bại.

### Phase 3 — Release bootstrap

- files/modules: driver config, CLI contract baselines, generated bundle,
  `bin/virc*`.
- changes: nâng version 4.2.1, sync, build Stage 1→3, ký binary và so fixed point.
- expected result: `bin/virc --version` là 4.2.1 và Stage 2 = Stage 3.

## 8. Compatibility

- Source/parser compatibility: không đổi.
- ABI và serialized formats: không đổi có chủ ý.
- LSP, public API và stdlib behavior: không đổi.
- Compiler behavior: sửa codegen cho source từng bị hạ sai.

## 9. Migration

Không cần migration source. Thay binary compiler bằng bản 4.2.1.

## 10. Validation Plan

- Chạy module resolver unittest và hai dependency graphs.
- Chạy group 3 để biên dịch native compiler project từ canonical entry.
- Chạy group 5 với fixture function type-scope isolation.
- Chạy CLI contract, sync drift, architecture và dependency checks.
- Build ba stage, so byte equality Stage 2/3, kiểm tra version và codesign.
- Chạy HIR control để xác nhận phạm vi sửa không làm mất typed HIR behavior.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Reset nhầm HIR state | Medium | High | Giữ reset ở AST-to-MIR; chạy typed HIR control |
| Generated bundle lệch source | Medium | High | `sync_virc.py --check` trong validation |
| Bootstrap không hội tụ | Low | High | 3-stage build và `cmp` Stage 2/3 |
| Binary macOS không chạy do signature | Medium | High | ad-hoc codesign và strict verify |

## 12. Rollback Strategy

Khôi phục lời gọi reset ở `ast_lower_func`, regression fixture, version metadata
và các binary 4.2.1 như một thay đổi nguyên tử. Không cần migration dữ liệu.

## 13. Exit Criteria

- [x] implementation completed;
- [x] scoped regression/release gates pass trên binary cuối;
- [x] acceptance criteria satisfied;
- [x] report generated;
- [x] linked issue closed sau accepted verification.

## 14. Related Papers

- VIRC-ISS-0033.
- VIRC-RPT-0034.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Ghi nhận kiến trúc, quyết định phạm vi, ba phase và validation plan; chuyển ACTIVE |
| 2026-10-04 | Hoàn tất triển khai, bootstrap, validation và accepted report; chuyển COMPLETED |
| 2026-10-04 | Linked VIRC-RPT-0034 |
