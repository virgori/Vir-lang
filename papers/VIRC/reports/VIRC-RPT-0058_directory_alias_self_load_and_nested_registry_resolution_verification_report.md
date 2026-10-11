---
id: "VIRC-RPT-0058"
type: "REPORT"
domain: "VIRC"
title: "Directory alias self-load and nested registry resolution verification report"
status: "ACCEPTED"
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
  plans:
    - "VIRC-PLN-0041"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "module-list"
  - "directory-alias"
  - "nested-registry"
  - "dedup"
  - "self-hosting"
---

# VIRC-RPT-0058 — Directory alias self-load and nested registry resolution verification report

## 1. Executive Summary

Báo cáo nghiệm thu, bao gồm một vòng audit sửa sai độc lập, xác nhận việc giải
quyết `VIRC-ISS-0042` trên chính resolver production thay vì chỉ dựa vào mô
hình resolver độc lập.

Vấn đề cốt lõi là false duplicate error `[E2121]` khi `module.list` chứa
directory alias tự trỏ (`mod = .`), do đoạn mã inline parser chắp vá đọc lại
cùng một file registry và xả bare keys un-prefixed vào namespace toàn cục.
Đồng thời, cấu trúc diamond dependency không thể tự bung đệ quy do thiếu recursive
import expansion và parser từ chối contextual token `mod`.

Toàn bộ các mục tiêu theo `VIRC-PLN-0041` đã hoàn thành và kiểm chứng:
1. Xóa bỏ hoàn toàn inline parser; thay thế bằng `parse_project_registry_file`
   đệ quy, đa cấp, quản lý `active load stack` và `visited set` qua realpath
   chuẩn tắc (`get_canonical_path_cstr`).
2. Tự trỏ (`mod = .`, `mod = ./`, `mod = ../dir`) được phát hiện và bảo vệ an toàn
   bằng stack guard, không sinh duplicate giả.
3. Nested registry con tuân thủ nghiêm ngặt namespace prefixing (`prefix.entry`),
   không làm ô nhiễm namespace cha.
4. Hội tụ danh tính chuẩn (Canonical Module ID convergence): các module được
   truy xuất qua directory alias (như `mod.dep_shared`) mà physical path trùng
   với exact registered module (`flat_shared = dep_shared.vri`) đều hội tụ về
   cùng Canonical ID `project::flat_shared`.
5. Resolver production từ chối duplicate chính xác bằng E2121, prefix collision
   bằng E2126, malformed registry bằng E2120 và target khai báo nhưng không tồn
   tại bằng E2124; duplicate/collision kèm related source provenance.
6. Suite mô hình native `tests/module/resolver_test.vri` đạt 17/17 PASS, còn
   Group 3 chạy các fixture production đạt 27/27 PASS.
7. Toàn bộ 5 positive fixtures cũ và fixture nested registry đa cấp đều compile
   và chạy thành công; năm negative fixtures mới fail-closed đúng diagnostic.
8. `./run_tests.sh min` bằng artifact đã cài đạt 505/505 PASS; Group 8 riêng đạt
   32/32 PASS.
9. Trình biên dịch được nâng đúng một lần lên `2026.1.13` (internal). Stage 2 và
   stage 3 self-host byte-identical với SHA-256
   `2edd3bcc27a38815d04d6821ff2ea7253d10026ea30b5a4666493ceb2269dd13`.

## 2. Source Issues

- `VIRC-ISS-0042` — Directory alias self-load causes duplicate module rejection in native resolver.

## 3. Source Plans

- `VIRC-PLN-0041` — Resolve directory alias self-load and nested registry resolution in native resolver.

## 4. Implementation Summary

- **Xóa bỏ inline parser & tái cấu trúc `parse_project_registry_file`**:
  Thay thế toàn bộ đoạn mã đọc registry inline bằng hàm đệ quy thống nhất
  `parse_project_registry_file(reg_path, base_dir, prefix)`.
- **Active Load Stack & Visited Realpath Set**:
  Thêm `g_reg_stack_paths` (độ sâu tối đa 64) và `g_reg_visited_paths` (tối đa 4096),
  sử dụng `cliCanonicalPath` để chuẩn hóa đường dẫn registry. Khi đường dẫn con
  trùng đỉnh stack, nhận diện tự trỏ (self-reference) và bỏ qua đệ quy mà không
  sinh lỗi. Khi trùng sâu hơn trong stack, phát hiện và cắt đứt chu trình (cycle).
- **Namespace Prefixing cho Child Registry**:
  Các entry trong child registry luôn mang tiền tố của alias cha (`join_dotted_cstr`).
  Top-level namespace không bị ô nhiễm bởi bare keys con.
- **Canonical Module ID Convergence**:
  Trong `resolve_include_target`, khi một physical path được tìm thấy qua
  directory alias hoặc relative fallback, resolver quét đối chiếu với các exact
  module entries đã đăng ký (`g_reg_isdir == 0`). Nếu trùng physical path,
  gán Canonical ID của exact module đó, đảm bảo dedup và DAG closure đồng nhất.
- **Production collision validation**:
  `parse_project_registry_file` kiểm tra exact duplicate trước prefix collision,
  so sánh cả hai chiều giữa directory alias và dotted module ID, canonicalize
  target trước khi ghi registry, và fail-closed nếu target không tồn tại.
- **Cross-file diagnostic provenance**:
  Registry lưu file/line nguồn cho mỗi entry. E2121, E2123 và E2126 đi qua
  related-diagnostic transport; E2121 và E2126 được fixture production xác minh
  file/dòng declaration trước ở human output và JSON payload. Cross-registry
  classification/mapping parity của E2123 vẫn thuộc `VIRC-ISS-0047`.
- **Bảo vệ Register Allocator & Bộ nhớ Registry**:
  Khởi tạo zero toàn bộ `g_reg_names` và sử dụng `g_reg_count` toàn cục thay vì
  biến cục bộ lồng trong hàm dài, loại bỏ triệt để hiện tượng clobber thanh ghi
  khi dùng cờ `-q` (im lặng).
- **Mở rộng Preprocessor Import Recursion**:
  Cập nhật `import_expander.vri` nhận diện `piece` là full body (`fat_str_eq(piece, body) == 1`)
  khi module chứa includes/imports, kích hoạt đệ quy `expand_import_recurse`.
- **Hỗ trợ Contextual Keyword `mod`**:
  Cập nhật `is_name_token` trong `compiler/src/frontend/parser/state.vri` chấp nhận
  `TokType.Mod` như identifier hợp lệ trong ngữ cảnh đường dẫn module (`mod.dep_shared`).
- **Bảo vệ Tính Bất Biến của Enum Variant Ambiguity**:
  Trong `compiler/src/semantic/symbols/walk_types.vri`, chỉ đánh dấu ambiguous (-2)
  khi variant xuất hiện ở hai enum khác nhau (`old_parent != enum_id`), đảm bảo
  tính lũy biến (idempotent) khi cùng một enum được nạp lại qua nhiều đường dẫn include.

## 5. Changes by Component

### `compiler/src/main/path_util.vri`

- Change: Bổ sung `join_dotted_cstr`, `path_dirname_cstr`, `get_canonical_path_cstr`
  cùng các mảng trạng thái toàn cục `g_reg_stack_paths`, `g_reg_visited_paths`,
  `g_reg_regfiles`, và helper early diagnostic có related location.
- Reason: Cung cấp hạ tầng chuẩn hóa đường dẫn thực tế (realpath) và quản lý
  trạng thái ngăn xếp nạp cho resolver; giữ chính xác provenance vật lý của
  `module.list` thay vì ánh xạ nó như source line đã expand.
- Impact: Transaction state bị giới hạn theo compiler session và diagnostic có
  primary/related file-line machine-readable.

### `compiler/src/main/module_resolver.vri`

- Change: Thay thế 130 dòng lặp inline bằng hàm đệ quy `parse_project_registry_file`;
  zero-init mảng `g_reg_names`; triển khai Canonical Module ID convergence,
  exact-duplicate precedence, prefix collision hai chiều và target
  canonicalization.
- Reason: Loại bỏ false E2121 trên `mod = .`, chuẩn hóa nạp nested registry,
  hội tụ định danh giữa alias và exact entry.
- Impact: Loại bỏ E2121 giả, không làm yếu duplicate thật, hỗ trợ diamond
  dependency và nested registry tới giới hạn fail-closed đã công bố.

### `compiler/src/diagnostic/error_codes.vri` and semantic diagnostics

- Change: Đăng ký E2120–E2126, thêm message E2126, render related file/note và
  giữ JSON related location nhất quán.
- Reason: Production collision validation phải có code riêng và chỉ rõ cả hai
  declaration xung đột.
- Impact: Human/JSON diagnostics cùng báo E2121/E2126 với provenance kiểm thử
  được; báo cáo này không tuyên bố đóng các acceptance criteria của E2123.

### `compiler/src/main/import_expander.vri`

- Change: Nhận diện full body piece trong `text_build_import_body` và cho phép
  bước đệ quy `expand_import_recurse` tiếp tục bung các nested import.
- Reason: Hỗ trợ diamond import và module lồng nhau không có include header.
- Impact: `test_diamond_dedup.vri` mở rộng trơn tru, không sót import directive trong AST.

### `compiler/src/frontend/parser/state.vri`

- Change: Thêm `TokType.Mod` vào `is_name_token`.
- Reason: Từ khóa `mod` là contextual identifier hợp lệ cho tên module / namespace.
- Impact: Cú pháp `mod.xxx` được parse thành công mà không ảnh hưởng tới toán tử modulo.

### `compiler/src/semantic/symbols/walk_types.vri`

- Change: Chỉ gán `-2` (ambiguous) khi `old_parent != enum_id`.
- Reason: Cùng một enum Option khi xuất hiện nhiều lần qua multi-include không được coi là ambiguous với chính nó.
- Impact: Tránh false E3038 khi sử dụng enum chuẩn trong các module consumer.

### `tests/module/resolver_test.vri`

- Change: Bổ sung Tests 13–17:
  - Test 13: `mod = .` self-reference and exact entry canonical ID convergence.
  - Test 14: Distinct child registry with namespace prefixing (`sub.child_item`).
  - Test 15: Multi-level nested registry recursion (`mid.leaf.item`).
  - Test 16: Cross-file duplicate key rejection with provenance (`E2121`).
  - Test 17: Cyclic registry reference termination guard.
- Reason: Mô hình độc lập kiểm định thuật toán và dependency DAG; nó là bằng
  chứng bổ trợ, không thay thế fixture chạy qua compiler production.
- Impact: 17/17 tests pass 100%, gồm E2126 prefix collision và provenance E2121.

### `run_tests.sh`

- Change: Tích hợp 5 positive fixtures (`test_flat_include.vri`, `test_include_only.vri`,
  `test_import_only.vri`, `test_diamond_dedup.vri`, `test_flat_diamond.vri`),
  fixture nested positive và năm negative production vào Nhóm 3. Runner đọc
  thêm `EXPECT_RELATED_FILE` và `EXPECT_RELATED_LINE`.
- Reason: Tự động hóa kiểm thử hồi quy hệ thống module trong CI/CD.
- Impact: Nhóm 3 đầy đủ đạt 27/27 PASS.

## 6. Deviations from Plan

- Phạm vi implementation thực tế rộng hơn resolver: `import_expander.vri`,
  parser contextual-name handling và enum symbol registration cũng thay đổi để
  các fixture module hiện hữu đi hết pipeline. Đây là thay đổi được kiểm tra bởi
  Group 3, Group 8 và suite `min`, không được mô tả là “không deviation”.
- Nested `module.list` recursion là hành vi tương thích của compiler hiện tại.
  `VIR-SPC-0006` không chuẩn hóa cơ chế registry lồng này; báo cáo không đưa ra
  normative language claim và không sửa language specification.
- Gate Python `tests/module/test_module_resolver.py` được nêu trong ISSUE ban đầu
  đã bị loại bỏ có chủ đích trong migration `VIRC-ISS-0050`. Closure gate được
  thay bằng `tests/module/resolver_test.vri`, production fixtures trong Group 3,
  dependency checks và alternate-CWD compile.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Native resolver model | PASS | Rebuilt `tests/module/resolver_test.vri`; 17/17, including E2126 and cross-file E2121 provenance |
| Production positives | PASS | Five original module fixtures plus multi-level nested registry fixture compile/run |
| Production negatives | PASS | E2120 malformed, E2121 same/cross-file duplicate, E2124 missing target, E2126 prefix collision |
| Group 3 | PASS | `./run_tests.sh 3` (27/27, 100%) |
| Group 8 | PASS | `./run_tests.sh 8` (32/32, 100%) |
| Minimum suite | PASS | `./run_tests.sh min` using installed `bin/virc` (505/505, 100%) |
| Architecture gate | PASS | `./bin/vir-pass-check`: 3 orchestrators and 317 dependencies clean |
| Alternate CWD | PASS | From `/private/tmp`, real `test_flat_diamond.vri --check` succeeds with explicit sysroot |
| Version Policy | PASS | `python3 tests/test_virc_version_policy.py` (2026.1.13 internal) |
| Bundle Sync | PASS | `python3 tools/sync_virc.py --check` reports identical |
| Self-host Bootstrap | PASS | Signed stage 2 and stage 3 are byte-identical; SHA-256 `2edd3bcc27a38815d04d6821ff2ea7253d10026ea30b5a4666493ceb2269dd13` |

## 8. Acceptance Criteria

- [x] A focused native regression test reproduces `mod = .` plus an exact file entry and fails before the fix.
- [x] Native resolver does not parse the same normalized `module.list` twice in one registry load or otherwise handles self-reference without a false E2121.
- [x] All five positive fixtures compile and execute with exit code 0.
- [x] `flat_shared` and `mod.dep_shared` resolve to the intended physical source and converge under the documented canonical/dedup policy.
- [x] Genuine duplicate key, missing target, malformed entry and prefix-collision negative tests continue to emit their expected diagnostics.
- [x] Nested registry tests cover a distinct child registry, self-reference, multi-level recursion and a real cross-file duplicate with source provenance.
- [x] Group 3 invokes the native positive fixtures so this regression cannot be hidden by Python-only resolver tests.
- [x] Native resolver-model tests, production Group 3 fixtures, dependency checks,
  compiler project ingestion and alternate-CWD resolution remain green.
- [x] A REPORT records before/after commands, versions, fixture exits and diagnostic evidence before closure.

## 9. Known Limitations

- Độ sâu stack nạp registry tối đa là 64 cấp (`G_REG_STACK_MAX`), fail-closed nếu vượt quá.
- Sức chứa registry tối đa là 4096 entries (`G_REG_MAX`), báo lỗi rõ ràng nếu vượt quá.
- Nested project registries là compiler compatibility behavior, chưa phải cú
  pháp hay semantics chuẩn hóa bởi `VIR-SPC-0006`.

## 10. Remaining Work

Không còn công việc tồn đọng cho `VIRC-ISS-0042`. Diagnostic parity đầy đủ cho
cross-registry E2123 vẫn được theo dõi độc lập bởi `VIRC-ISS-0047`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIRC-ISS-0042` — source issue.
- `VIRC-ISS-0047` — remaining cross-registry E2123 diagnostic parity work.
- `VIRC-PLN-0041` — implementation plan.
- `VIR-SPC-0006` — module and registry specification.
- `VIR-SPC-0014` — compiler modular architecture specification.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Accepted implementation evidence and READY_FOR_CLOSE conclusion |
| 2026-10-10 | Corrective independent audit replaced the retired Python gate, added production negative fixtures and related provenance, recorded implementation deviations, verified Group 3 27/27, Group 8 32/32, min 505/505, alternate CWD, version 2026.1.13, bundle sync, and byte-identical stage2/stage3 SHA-256 `2edd3bcc...dd13` |
