---
id: "VIRC-PLN-0041"
type: "PLAN"
domain: "VIRC"
title: "Resolve directory alias self-load and nested registry resolution in native resolver"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
  - "tests"
components:
  - "module-resolution"
  - "module-registry"
  - "source-preprocessing"
  - "regression-suite"
related:
  issues:
    - "VIRC-ISS-0042"
  plans: []
  reports:
    - "VIRC-RPT-0058"
supersedes: null
superseded_by: null
tags:
  - "module-list"
  - "directory-alias"
  - "nested-registry"
  - "dedup"
  - "vps-plan"
---

# VIRC-PLN-0041 — Resolve directory alias self-load and nested registry resolution in native resolver

## 1. Objective

Triển khai giải quyết dứt điểm lỗi `VIRC-ISS-0042` theo nguyên tắc không hardcode,
không vá tạm:
1. Xóa bỏ hoàn toàn đoạn mã inline parser chắp vá trong `module_resolver.vri:366-493`
   vốn tự nạp lại cùng file registry khi gặp directory alias tự trỏ (`mod = .`),
   sinh duplicate module giả (E2121) cho `flat_shared`.
2. Thiết kế cơ chế nạp registry chuẩn xác, đệ quy, có quản lý stack các registry
   đang nạp (`active load stack`) và tập các registry đã duyệt (`visited set`)
   thông qua canonical realpath (`cliCanonicalPath`).
3. Chuẩn hóa ngữ nghĩa nested registry: một registry con trong thư mục alias
   `sub = path` chỉ đăng ký các module có namespace tiền tố `sub.<name>`, tuyệt
   đối không làm ô nhiễm (pollute) namespace top-level bằng bare keys.
4. Hội tụ danh tính chuẩn (`canonical identity convergence`): khi một module được
   truy xuất qua directory alias (ví dụ `mod.dep_shared`) mà physical path trùng
   với một exact registered module (ví dụ `flat_shared = dep_shared.vri`),
   resolver phải hội tụ về cùng một canonical ID (`project::flat_shared`) phục vụ
   deduplication và cycle detection.
5. Bổ sung test suite native hoàn chỉnh trong `tests/module/resolver_test.vri` và
   tích hợp năm positive fixtures trong `tests/modules/` vào `run_tests.sh 3`.

## 2. Source Issues

- `VIRC-ISS-0042` — Directory alias self-load causes duplicate module rejection
  in native resolver.

## 3. Scope

### In Scope

- `compiler/src/main/module_resolver.vri`: tái cấu trúc bộ nạp registry dự án,
  hỗ trợ load stack guard, tự trỏ (self-reference), đệ quy nhiều cấp, và hội tụ
  canonical ID giữa directory alias và exact entry.
- `compiler/src/main/path_util.vri`: bổ sung khai báo mảng trạng thái load stack
  và visited set cho registry transaction.
- `tests/module/resolver_test.vri`: cập nhật model resolver tương đương và bổ sung
  các test cases: tự trỏ (`mod = .`), nested registry con, đệ quy nhiều cấp,
  phát hiện duplicate xuyên file kèm source provenance.
- `run_tests.sh`: tích hợp năm positive module fixtures vào Nhóm 3.
- `compiler/generated/virc.vri` & `bin/virc`: đồng bộ hóa bundle và kiểm định
  bootstrap.

### Out of Scope

- Không thay đổi cú pháp hoặc định dạng của `stdlib/stdlib.vri`.
- Không thay đổi language grammar của `include` / `import` / `export`.

## 4. Current Architecture

Trong kiến trúc hiện tại:
- `virc_registry_load` tại `compiler/src/main/module_resolver.vri` mở top-level
  `module.list` và duyệt từng dòng tuần tự.
- Khi gặp một entry là directory alias (`is_dir == 1`, ví dụ `mod = .`), một khối
  mã lặp inline (dòng 366-493) kiểm tra sự tồn tại của `<mphys>/module.list`.
- Với `mod = .`, `<mphys>/module.list` trỏ về chính `module.list` top-level. Khối
  mã inline đọc lại toàn bộ nội dung file này.
- Khi đọc nội dung, khối inline chèn các key `skey` dưới dạng **bare key** vào
  `g_reg_names` (ví dụ `flat_shared`), đồng thời chèn `ns_key` (`mod.flat_shared`).
- Khi vòng lặp top-level tiếp tục đến dòng 3 `flat_shared = dep_shared.vri`, nó
  kiểm tra danh sách `g_reg_names` và thấy `flat_shared` đã có sẵn, do đó phát ra
  lỗi sai `[E2121] duplicate module in stdlib registry: 'flat_shared'`.
- Ngoài ra, việc resolve qua directory alias tại dòng 623 gán trực tiếp
  `g_inc_canonical_id = "project::" + nd` mà không kiểm tra xem physical target
  đã được đăng ký dưới một exact canonical module nào hay chưa.

## 5. Proposed Architecture

### 5.1. Bảng theo dõi nạp registry (Load Stack & Visited Registry Table)

- Sử dụng `cliCanonicalPath` để lấy đường dẫn thực tế tuyệt đối (realpath) của
  mỗi file `module.list` trước khi mở.
- Duy trì hai cấu trúc:
  - `g_reg_stack_paths`: ngăn xếp các registry đang trong quá trình duyệt.
  - `g_reg_visited_paths`: danh sách các registry đã hoàn tất phân tích trong phiên
    nạp hiện tại.
- Khi gặp một directory alias có `module.list`:
  - Lấy canonical path của file con.
  - Nếu canonical path trùng với đỉnh ngăn xếp: đây là **self-reference**
    (ví dụ `mod = .`). Trình phân giải nhận diện tự trỏ và bỏ qua bước nạp nested,
    giữ nguyên directory alias cho mục đích ánh xạ đường dẫn tail.
  - Nếu canonical path nằm sâu hơn trong ngăn xếp: phát hiện **cyclic registry
    recursion** và dừng phân tích để tránh vòng lặp vô hạn.
  - Nếu canonical path đã nằm trong tập `visited`: bỏ qua vì đã được nạp trước đó.

### 5.2. Hàm nạp đệ quy chuẩn hóa (`parse_project_registry_file`)

- Tách toàn bộ logic phân tích cú pháp registry dự án thành một hàm đệ quy thống nhất:
  ```vir
  func parse_project_registry_file(reg_path: int, base_dir: int, prefix: int) -> int
  ```
- Tham số `prefix`:
  - Với registry gốc: `prefix = 0`. Các entry đăng ký tên gốc (`mkey`).
  - Với registry con trong alias `sub`: `prefix = "sub"`. Mọi entry trong registry
    con bắt buộc phải đăng ký dưới tên tiền tố `join_dotted(prefix, mkey)`
    (ví dụ `sub.foo`). Tuyệt đối không chèn bare `foo` vào registry cha.
- Khi alias con tiếp tục trỏ tới một thư mục cháu có `module.list`:
  hàm tự gọi đệ quy với tiền tố mở rộng `join_dotted(prefix, mkey)`, hỗ trợ tự
  nhiên cấu trúc lồng nhau tùy ý không giới hạn số cấp.

### 5.3. Hội tụ danh tính chuẩn (Canonical ID Convergence)

- Trong `resolve_include_target`:
  Khi một module được định vị qua directory alias (ví dụ `mod.dep_shared` ->
  `tests/modules/dep_shared.vri`), resolver chuẩn hóa `target_path` và duyệt qua
  các exact module entry đã đăng ký (`g_reg_isdir == 0`):
  - Nếu `target_path` trùng physical path của một exact module (ví dụ `flat_shared`):
    gán `g_inc_canonical_id = "project::flat_shared"`.
  - Nếu không trùng exact module nào:
    gán `g_inc_canonical_id = "project::" + nd`.
- Đảm bảo tính bất biến: các dependency khác nhau trỏ tới cùng một đơn vị mã
  nguồn sẽ chia sẻ cùng một Canonical Module ID, cho phép bộ deduplication và
  cycle detector hoạt động chính xác theo `VIR-SPC-0006:75-78`.

## 6. Design Decisions

### Decision 1: Quản lý đệ quy bằng Canonical Realpath thay vì so sánh chuỗi tương đối
**Decision:** Dùng `cliCanonicalPath` để chuẩn hóa đường dẫn registry trước khi kiểm tra chu trình và tự trỏ.
**Rationale:** Tránh bỏ sót các trường hợp tự trỏ phức tạp như `mod = ./`, `mod = ../dir`, hoặc symlink.
**Alternatives considered:** Chỉ so sánh `rt_streq(mval, ".")`. Bị bác bỏ vì đây là "vá tạm", dễ vỡ khi đường dẫn được viết dưới dạng khác.

### Decision 2: Nested registry chỉ đăng ký tên có tiền tố
**Decision:** Entry trong child registry luôn có tiền tố namespace của alias cha.
**Rationale:** Phù hợp với nguyên tắc đóng gói module, không làm xung đột tên giữa các module con và module cha.
**Alternatives considered:** Đăng ký cả bare key và prefixed key. Bị bác bỏ vì gây ô nhiễm namespace toàn cục và sinh duplicate giả.

### Decision 3: Hội tụ Canonical ID cho directory alias target
**Decision:** Kiểm tra physical target của directory alias đối chiếu với exact entries.
**Rationale:** Đảm bảo `flat_shared` và `mod.dep_shared` hội tụ về cùng một identity duy nhất.

## 7. Implementation Plan

### Phase 1 — Native Regression Tests
- Cập nhật `tests/module/resolver_test.vri`:
  - Test 13: `mod = .` cùng exact file entry.
  - Test 14: Nested child registry với prefix namespace.
  - Test 15: Đệ quy đa cấp (multi-level recursion).
  - Test 16: Duplicate xuyên file kèm source provenance.
  - Test 17: Vòng lặp registry (cycle detection).

### Phase 2 — Compiler Resolver Implementation
- Cập nhật `compiler/src/main/path_util.vri` bổ sung mảng load stack và visited.
- Tái cấu trúc `compiler/src/main/module_resolver.vri` với `parse_project_registry_file` đệ quy.
- Triển khai canonical ID convergence trong `resolve_include_target`.

### Phase 3 — Test Parity & Test Suite Integration
- Bổ sung 5 positive fixtures (`tests/modules/test_*.vri`) vào `run_tests.sh 3`.
- Chạy toàn bộ `./run_tests.sh 3`.

### Phase 4 — Version Bump & Self-Hosting Bootstrap Verification
- Nâng phiên bản compiler theo `compiler/VERSIONING.md`.
- Đồng bộ `compiler/generated/virc.vri` bằng `tools/sync_virc.py`.
- Tự biên dịch `bin/virc` và kiểm chứng `./bin/virc --version`.

## 8. Compatibility

- Tương thích 100% với các dự án Vir hiện có.
- Giữ nguyên toàn bộ hành vi của `compiler/module.list` và stdlib.

## 9. Migration

Không yêu cầu migration dữ liệu hay mã nguồn.

## 10. Validation Plan

1. `./run_tests.sh 3`: 100% pass bao gồm `module-resolver-test` và 5 positive fixtures.
2. Biên dịch trực tiếp 5 file trong `tests/modules/` bằng `./bin/virc` với exit code 0.
3. Chạy `python3 tools/sync_virc.py --check` và `python3 tests/test_virc_version_policy.py`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tràn mảng registry khi đệ quy sâu | Thấp | Trung bình | Kiểm tra `count >= G_REG_MAX` fail-closed |
| Lỗi đường dẫn không tồn tại khi lấy realpath | Thấp | Thấp | Fallback sang `path_normalize_fat` nếu `cliCanonicalPath` trả 0 |

## 12. Rollback Strategy

Khôi phục working tree của `compiler/src/main/module_resolver.vri` về snapshot trước đó qua git.

## 13. Exit Criteria

- [x] Toàn bộ 5 positive fixtures trong `tests/modules/` biên dịch và thực thi exit 0.
- [x] `tests/module/resolver_test.vri` hoàn thành 17/17 tests thành công.
- [x] `run_tests.sh 3` pass toàn diện.
- [x] Trình biên dịch được bootstrap thành công và version policy regression pass.
- [x] Báo cáo nghiệm thu `VIRC-RPT-0058` được tạo và `./paper validate` pass.

## 14. Related Papers

- `VIRC-ISS-0042` — Issue nguồn.
- `VIR-SPC-0006` — Đặc tả kỹ thuật Module & Registry.
- `VIRC-RPT-0058` — Báo cáo nghiệm thu hoàn tất.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Approved initial plan for VIRC-ISS-0042 resolution |
| 2026-10-10 | Linked VIRC-RPT-0058 |
| 2026-10-10 | Completed implementation and verification; marked COMPLETED |
