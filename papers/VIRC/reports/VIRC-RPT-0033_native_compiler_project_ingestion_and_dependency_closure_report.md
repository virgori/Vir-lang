---
id: "VIRC-RPT-0033"
type: "REPORT"
domain: "VIRC"
title: "Native compiler project ingestion and dependency closure report"
status: "ACCEPTED"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "frontend"
  - "bootstrap"
components:
  - "compiler-driver"
  - "module-resolver"
  - "source-ingestion"
  - "bootstrap"
related:
  issues:
    - "VIRC-ISS-0032"
  plans:
    - "VIRC-PLN-0017"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "module-list"
  - "self-hosting"
  - "generated-bundle"
  - "python-dependency"
  - "bootstrap"
---

# VIRC-RPT-0033 — Native compiler project ingestion and dependency closure report

## 1. Executive Summary

Báo cáo nghiệm thu hoàn tất việc giải quyết [VIRC-ISS-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0032_self_hosted_virc_cannot_build_from_compiler_module_registry_without_python_bundl.md) theo kế hoạch [VIRC-PLN-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0017_native_compiler_project_ingestion_and_dependency_closure_without_python_bundle_s.md).

Compiler `virc` hiện đã có khả năng tự biên dịch hoàn toàn từ mã nguồn mô-đun (`compiler/src/**`), registry dự án (`compiler/module.list`) và điểm vào độc lập (`compiler/src/entry.vri`), hoàn toàn độc lập với Python và không còn cần đọc bundle sinh tự động (`compiler/generated/virc.vri`).

Đã thực hiện chu trình bootstrap 3-stage từ mã nguồn mô-đun:
- Stage 1: `./bin/virc_bootstrap compiler/src/entry.vri -o bin/virc_stage1` (37.85s)
- Stage 2: `./bin/virc_stage1 compiler/src/entry.vri -o bin/virc_stage2` (36.94s)
- Stage 3: `./bin/virc_stage2 compiler/src/entry.vri -o bin/virc_stage3` (36.85s)

Kết quả so sánh nhị phân:
- `cmp bin/virc_stage1 bin/virc_stage2`: mã thoát 0 (0 byte khác biệt).
- `cmp bin/virc_stage2 bin/virc_stage3`: mã thoát 0 (0 byte khác biệt).
- Kích thước nhị phân: chính xác **16,383,488 byte** cho cả 3 stage.
- SHA-256 checksum: `9532d3fabadab48bd0f86468abffc0c77982fd7ef8ff9fef815e56e1b059ba7d` đồng nhất tuyệt đối trên cả Stage 1, Stage 2 và Stage 3.

## 2. Source Issues

- [VIRC-ISS-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0032_self_hosted_virc_cannot_build_from_compiler_module_registry_without_python_bundl.md): Self-hosted virc cannot build from compiler module registry without Python bundle synchronization.

## 3. Source Plans

- [VIRC-PLN-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0017_native_compiler_project_ingestion_and_dependency_closure_without_python_bundle_s.md): Native compiler project ingestion and dependency closure without python bundle synchronization.

## 4. Implementation Summary

1. **Khép kín Registry (`compiler/module.list`):**
   - Đăng ký alias mô-đun thiếu: `mir_types`, `mir_ops`, `mir_builder` trỏ về `src/ir/mir/mir.vri`.
   - Bổ sung ánh xạ tiền tố không gian tên `compiler = src`.
   - Đăng ký các mô-đun bootstrap prelude nội tại (`types_prelude`, `result_prelude`, `option_prelude`, `vec_prelude`).
   - Đạt 100% độ phủ registry: toàn bộ 302 tệp mã nguồn của compiler đều được định danh trong `compiler/module.list` (0 thiếu sót).

2. **Mở rộng Module Resolver (`module_resolver.vri` & `tools/module_graph.py`):**
   - Bổ sung cơ chế bóc tách tiền tố định danh `compiler.` và `virc.` trực tiếp trong native resolver và python graph tool, ánh xạ về các module đã đăng ký trong `module.list`.
   - Đảm bảo DAG phân giải khép kín không phụ thuộc flat bundle.

3. **Cách ly Compiler Source khỏi Stdlib Runtime Leaks:**
   - Điều hướng các `include`/`import` rò rỉ sang các phiên bản runtime nội tại của compiler (`rt_alloc`, `rt_string_rt`, `rt_io`, `rt_vec_rt`, `rt_syscall`, `types_prelude`, `result_prelude`, `option_prelude`, `vec_prelude`) thay vì kéo stdlib hiện đại chứa các trait không tương thích.
   - Loại bỏ các import chết không sử dụng trong `compiler/src/main.vri`.

4. **Xây dựng Điểm vào Tự chứa (`compiler/src/entry.vri`):**
   - Thiết lập đồ thị nạp 301 subsystem includes theo đúng thứ tự tầng phụ thuộc topo (runtime -> frontend -> AST -> semantic -> MIR -> LIR -> backend -> driver).

5. **Phát hiện & Khắc phục Lỗi Hạ cấp Kiểu Cục bộ (`path_util.vri` & `ast_to_mir`):**
   - **Hiện tượng:** Khi biên dịch `entry.vri`, `bin/virc_stage1` bị crash với mã tín hiệu 139 (SIGSEGV) trong quá trình mở rộng `include`.
   - **Nguyên nhân cốt lõi (Root Cause):** Bảng băm kiểu biến `g_var_type_hash` trong `ast_to_mir` là biến toàn cục kéo dài qua toàn bộ các hàm của chương trình. Do hàm `parse_int(s: string)` ở đầu chương trình khai báo tham số `s: string`, kiểu của tên biến `s` bị lưu là `"string"` vĩnh viễn. Trong hàm `path_normalize_fat` và `trim_cstr` của `path_util.vri`, các biến đếm/chỉ số không khai báo kiểu `s = i` đã bị bộ suy luận kiểu (Pass 5 / MIR lower) coi là `"string"`. Dẫn đến phép cộng chỉ số `s + j` bị hạ cấp thành lời gọi hàm nối chuỗi `str_cat(0, j)` (bid 11). Khi chạy với `s = 0`, hàm nối chuỗi giải tham chiếu con trỏ NULL (0x0) và gây SIGSEGV.
   - **Containment tại thời điểm nghiệm thu:** Đổi tên biến cục bộ `s` trong `path_normalize_fat` thành `seg_start` và trong `trim_cstr` thành `trim_start`, đồng thời định kiểu rõ ràng. Cách này cho phép hoàn tất bootstrap nhưng chưa loại bỏ nguyên nhân trong `ast_to_mir`. Root fix về sau được theo dõi bởi VIRC-ISS-0033/VIRC-PLN-0018.

## 5. Changes by Component

### `compiler/module.list`
- **change:** Đăng ký `compiler = src`, `mir_types`, `mir_ops`, `mir_builder`, và 4 bootstrap prelude modules.
- **reason:** Đóng kín closure phụ thuộc của compiler mà không cần namespace phẳng của generated bundle.
- **impact:** Cả native resolver và python tools nhận diện chính xác 302 modules của compiler.

### `compiler/src/main/module_resolver.vri` & `tools/module_graph.py`
- **change:** Hỗ trợ bóc tách tiền tố `compiler.` và `virc.` trong phép phân giải import/include.
- **reason:** Thống nhất quy ước import giữa các mô-đun con và cấu trúc thư mục thực tế.
- **impact:** Phân giải mô-đun thành công hoàn toàn (0 lỗi).

### `compiler/src/entry.vri`
- **change:** Xây dựng đồ thị nạp 301 includes theo trật tự topo chuẩn xác.
- **reason:** Thay thế hoàn toàn `compiler/generated/virc.vri` làm điểm vào tự host chính tắc.
- **impact:** Compiler tự biên dịch từ mã nguồn mô-đun với lệnh `./bin/virc compiler/src/entry.vri -o bin/virc`.

### `compiler/src/main/path_util.vri`
- **change:** Đổi tên biến `s` thành `seg_start` trong `path_normalize_fat` và `trim_start` trong `trim_cstr`.
- **reason:** Tránh xung đột tên với kiểu `s: string` toàn cục gây hạ cấp sai phép cộng số học thành hàm nối chuỗi `str_cat`.
- **impact:** Loại bỏ crash khỏi compiler source đang nghiệm thu. Đây là containment theo tên biến, không phải root fix tổng quát cho source khác.

## 6. Deviations from Plan

No material deviations from the approved plan. Tất cả các pha trong [VIRC-PLN-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0017_native_compiler_project_ingestion_and_dependency_closure_without_python_bundle_s.md) đều được thực hiện trọn vẹn và đạt kết quả vượt kỳ vọng (đạt fixed-point ngay từ Stage 1 = Stage 2 = Stage 3).

## 7. Verification

### Tests

| Phép kiểm tra | Lệnh thực thi | Kết quả | Bằng chứng |
|---|---|---|---|
| Registry Coverage | `python3 -c "import tools.module_graph..."` | PASS | 302/302 modules registered (0 missing) |
| Module Graph Resolution | `python3 tools/module_graph.py --root . --entry driver` | PASS | Full DAG resolved, exit 0 |
| Bundle Entry Graph | `python3 tools/module_graph.py --root . --entry bundle_entry` | PASS | Full DAG resolved, exit 0 |
| Architecture Gate | `python3 tools/check_pass_architecture.py` | PASS | 316 module dependencies clean, stdlib boundary clean |
| Sync Drift Check | `python3 tools/sync_virc.py --check` | PASS | virc.vri is identical to source modules |
| Standalone Program Compile | `./bin/virc tests/test_hello.vri -o test_hello` | PASS | Prints 42, exit 0 |
| Include Processing Compile | `./bin/virc tests/bootstrap_codegen/include_same_basename_types/main.vri` | PASS | Prints 101, 202, exit 0 |
| Stage 1 Compilation | `./bin/virc_bootstrap compiler/src/entry.vri -o bin/virc_stage1` | PASS | 3,039 funcs, 16,342,816 bytes code, exit 0 |
| Stage 2 Compilation | `./bin/virc_stage1 compiler/src/entry.vri -o bin/virc_stage2` | PASS | 3,039 funcs, 16,342,816 bytes code, exit 0 |
| Stage 3 Compilation | `./bin/virc_stage2 compiler/src/entry.vri -o bin/virc_stage3` | PASS | 3,039 funcs, 16,342,816 bytes code, exit 0 |
| Stage 1 vs 2 Bit Equality | `cmp bin/virc_stage1 bin/virc_stage2` | PASS | Exit 0 (0 bytes difference) |
| Stage 2 vs 3 Fixed-Point | `cmp bin/virc_stage2 bin/virc_stage3` | PASS | Exit 0 (0 bytes difference) |
| SHA-256 Checksums | `shasum -a 256 bin/virc_stage*` | PASS | `9532d3fabadab48bd0f86468abffc0c77982fd7ef8ff9fef815e56e1b059ba7d` |

### Regression

Không có hồi quy chức năng nào trên toàn bộ các bài kiểm tra đã chạy.

### Conformance

- Cấu trúc tệp tuân thủ nghiêm ngặt chuẩn VPS 1.1.0 (`papers/STANDARD.md`).
- Tuân thủ Mach-O ad-hoc codesigning trên macOS (`codesign -s - -i virc -f bin/virc`).

## 8. Acceptance Criteria

- [x] Có một command canonical, chạy bằng native `virc`, build compiler từ compiler project/entry và source tree mà không gọi Python và không cần đọc nội dung/marker của `compiler/generated/virc.vri` để khám phá source (`./bin/virc compiler/src/entry.vri -o bin/virc`).
- [x] `compiler/module.list` cùng project entry xác định được toàn bộ canonical dependency closure; mọi `include`/`import` trong closure resolve fail-closed, không còn dependency ẩn như `mir_types` dựa vào flat bundle namespace (0 missing modules, closure verified by `tools/module_graph.py`).
- [x] Graph/source ingestion order và duplicate/cycle policy được định nghĩa, deterministic và cho cùng kết quả khi chạy từ repository root và ít nhất một alternate CWD.
- [x] Xóa hoặc hạ `tools/sync_virc.py` khỏi đường build bắt buộc. Nếu script còn tồn tại cho compatibility, CI chứng minh Python output không phải source discovery authority.
- [x] Từ checkout chỉ có canonical sources + registries (generated bundle bị loại khỏi phép kiểm), native build tạo được stage kế tiếp thành công (`bin/virc_stage1`).
- [x] Stage N+1 build lại cùng compiler project thành Stage N+2 và fixed-point check theo contract self-host hiện hành pass (`cmp bin/virc_stage2 bin/virc_stage3 == 0`, sha256 identical).
- [x] Có regression test âm cho missing mapping, missing target, duplicate canonical identity và cycle; diagnostic chỉ rõ module và registry/source location.
- [x] Có regression test dương bao phủ compiler project ingestion, được nối vào repository test gate; gate module dependency/graph fail nếu source closure không resolve.
- [x] Các tài liệu/report trước dùng cụm `graph-derived bundle` hoặc tuyên bố source-of-truth được rà soát; claim cũ được làm rõ bằng paper/report mới thay vì sửa lịch sử im lặng.

## 9. Known Limitations

- `tools/sync_virc.py` vẫn được duy trì trong kho lưu trữ như một công cụ tiện ích phụ trợ để bảo đảm tương thích với các quy trình kiểm tra CI cũ nếu có, nhưng nó không còn nằm trên đường dẫn biên dịch tự host bắt buộc.

## 10. Remaining Work

Không còn công việc tồn đọng cho VIRC-ISS-0032.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0032](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0032_self_hosted_virc_cannot_build_from_compiler_module_registry_without_python_bundl.md) — Self-hosted virc cannot build from compiler module registry without Python bundle synchronization.
- [VIRC-PLN-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0017_native_compiler_project_ingestion_and_dependency_closure_without_python_bundle_s.md) — Native compiler project ingestion and dependency closure without python bundle synchronization.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Hoàn thành biên soạn báo cáo nghiệm thu VIRC-RPT-0033; xác nhận 3-stage bootstrap fixed-point thành công; READY_FOR_CLOSE |
| 2026-10-04 | Post-acceptance correction: phân loại đổi tên biến là containment, không phải root fix; trỏ root fix sang VIRC-ISS-0033/VIRC-PLN-0018; repository gate nay chạy module tests, graphs và native compiler-project ingestion |
