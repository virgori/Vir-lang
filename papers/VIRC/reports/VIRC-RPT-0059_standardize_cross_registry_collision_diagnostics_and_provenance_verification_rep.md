---
id: "VIRC-RPT-0059"
type: "REPORT"
domain: "VIRC"
title: "Standardize cross-registry collision diagnostics and provenance verification report"
status: "ACCEPTED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
  - "tooling"
components:
  - "module-resolution"
  - "module-registry"
  - "diagnostics"
  - "regression-suite"
related:
  issues:
    - "VIRC-ISS-0047"
  plans:
    - "VIRC-PLN-0042"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "module-list"
  - "collision"
  - "e2123"
  - "e2121"
  - "diagnostic-provenance"
---

# VIRC-RPT-0059 — Standardize cross-registry collision diagnostics and provenance verification report

## 1. Executive Summary

Report này ghi nhận việc hoàn tất triển khai và nghiệm thu toàn diện theo kế hoạch [VIRC-PLN-0042](../plans/VIRC-PLN-0042_standardize_cross_registry_collision_diagnostics_and_provenance_tracking.md) nhằm giải quyết dứt điểm sự cố [VIRC-ISS-0047](../issues/VIRC-ISS-0047_cross_registry_collision_diagnostics_lose_module_identity_and_registry_provenanc.md).

Một corrective audit sau lần accept đầu tiên phát hiện bốn khoảng trống: E2123 chưa mang hai mapping values; classic renderer đọc secondary note fat-string như C-string; LSP bỏ qua diagnostic có primary source là `module.list`; và Python graph resolver chưa chọn active sysroot. Revision này giữ lại lịch sử claim cũ, sửa đủ bốn khoảng trống và chỉ tái nghiệm thu sau khi classic, JSON, LSP, Python parity, bootstrap fixed point và regression gates đều pass.

Các cải tiến chính đạt được:
1. **Khắc phục lỗi mất Module ID**: Sửa lỗi ép kiểu raw pointer sang fat string slice tại các điểm phát sinh early error trong `compiler/src/main/module_resolver.vri`, đảm bảo canonical module name luôn xuất hiện đầy đủ trong diagnostic message.
2. **Chuẩn hoá mã lỗi & phân loại (Classification)**: Đảo lại và chuẩn hoá thông điệp chẩn đoán:
   - `E2123`: `project module '<key>' collides with standard library` khi module dự án trùng tên chính xác với module thư viện chuẩn.
   - `E2121`: `duplicate module registration: '<key>'` khi đăng ký trùng lặp trong cùng registry.
   - `E2126`: `conflicting module registration: '<key>'` khi xảy ra xung đột tiền tố thư mục/entry.
3. **Theo dõi và hiển thị Provenance đầy đủ**: E2123 mang project registry path/line/mapping và stdlib registry path/line/mapping trên classic, JSON và LSP `relatedInformation`.
4. **Bảo toàn toạ độ vật lý**: Trong `compiler/src/main/path_util.vri`, xoá `span_id` đối với early registry diagnostics để tránh việc source manager mapping ghi đè toạ độ file/dòng vật lý của `module.list`.
5. **Đồng bộ Tooling & Native Resolver**: `tools/module_graph.py` chọn stdlib từ `--sysroot` hoặc `VIR_SYSROOT`, phát E2123 có structured provenance và không rơi ra traceback.
6. **Tối ưu kiến trúc Chaitin-Briggs Regalloc**: Tách vòng lặp tìm kiếm trùng lặp thành hàm độc lập `registry_find_entry(limit, key) -> int`, loại bỏ hiện tượng tràn thanh ghi và cờ nhánh sai trong hàm monolithic `virc_registry_load()`.
7. **Khép kín đường LSP**: Sửa serialization fat-string của related note và publish diagnostic cho source cấu hình có diagnostic, kể cả `module.list` không phải source/include document.
8. **Khoá regression contract**: Thêm fixture production, classic/JSON CLI assertions, exact/prefix matrix và native LSP suite `registry_collision`.

## 2. Source Issues

- [VIRC-ISS-0047](../issues/VIRC-ISS-0047_cross_registry_collision_diagnostics_lose_module_identity_and_registry_provenanc.md) — Cross-registry collision diagnostics lose module identity and registry provenance
- [VIR-ISS-0008](../../VIR/issues/VIR-ISS-0008_standard_library_module_identifiers_are_not_normatively_reserved_against_project.md) — Standard library module identifiers are not normatively reserved against project collisions
- [VIRC-ISS-0043](../issues/VIRC-ISS-0043_self_contained_toolchain_cannot_locate_active_stdlib_or_target_sysroot_from_ex.md) — Self-contained toolchain cannot locate active stdlib or target sysroot

## 3. Source Plans

- [VIRC-PLN-0042](../plans/VIRC-PLN-0042_standardize_cross_registry_collision_diagnostics_and_provenance_tracking.md) — Standardize cross-registry collision diagnostics and provenance tracking

## 4. Implementation Summary

1. `compiler/src/main/module_resolver.vri`:
   - Thêm hàm `func registry_find_entry(limit: int, key: int) -> int` duyệt tuyến tính và so khớp qua `rt_streq`.
   - Sử dụng `registry_find_entry` trong `virc_registry_load()` để phát hiện trùng lặp trong stdlib registry.
   - Sử dụng `registry_find_entry` trong `parse_project_registry_file()` để kiểm tra xung đột với stdlib.
   - Chuyển toàn bộ các vị trí gọi diagnostic sang `str_from_cstr(full_key)` và `str_from_cstr(key)`.
   - Kết xuất lỗi `E2123` qua `inc_report_early_error_related` với đầy đủ file, dòng và note `project mapping: <value>; standard library mapping: <value>`.
2. `compiler/src/main/path_util.vri`:
   - Hiện thực `func inc_report_early_error_related` hỗ trợ toạ độ chính và toạ độ liên quan (`related_file`, `related_line`, `related_note`).
   - Ghi đè `native_write_i64(d0 as i64, 72, 0)` để vô hiệu hoá synthetic span lookup cho các lỗi registry cấp sớm.
3. `compiler/src/semantic/diagnostics/msg_frontend.vri`:
   - Sửa thông điệp mã 2121: `duplicate module registration: '%s'`.
   - Sửa thông điệp mã 2123: `project module '%s' collides with standard library`.
4. `tools/module_graph.py`:
   - Cập nhật phân loại lỗi cross-registry phát ra E2123 kèm project/stdlib path, line và mapping.
   - Chọn active stdlib qua `--sysroot` hoặc `VIR_SYSROOT`; lỗi registry được render một dòng, không traceback.
   - Cập nhật duplicate cùng registry phát ra E2121.
5. `tests/module/resolver_test.vri`:
   - Bổ sung Test 16: kiểm tra trùng lặp cross-file phát sinh E2121 kèm provenance.
   - Bổ sung Test 17: kiểm tra chặn chu trình đệ quy registry.
   - Bổ sung Test 18: kiểm tra từ chối exact collision với stdlib phát sinh E2123.
   - Bổ sung Test 19: kiểm tra exact/prefix matrix `http`/`http.app`, `json`/`json.app`, `db.sqlite`/`db.sqlite3`.
   - Bổ sung Test 20: kiểm tra phân định rạch ròi E2121, E2123 và E2126.
6. `compiler/src/semantic/diagnostics/render.vri`:
   - Chuyển secondary-note fat-string sang C-string trước khi classic renderer in nội dung.
7. `tools/vir-lsp/src/main.vri`:
   - Serialize secondary-note fat-string bằng độ dài đúng.
   - Publish mọi source có diagnostic, bao gồm `module.list`, thay vì chỉ root/include sources.
8. Regression fixtures và runners:
   - Thêm `tests/modules/registry_stdlib_collision/` vào Group 3.
   - Thêm classic/JSON contract vào `tests/cli_contract/cli_contract_test.vri`.
   - Thêm native LSP suite `registry_collision` vào `tools/vir-lsp-test`.

## 5. Changes by Component

### `compiler/src/main/module_resolver.vri`
- **change**: Thêm `registry_find_entry`, chuẩn hoá truyền fat-string và kết xuất provenance cho E2123, E2121.
- **reason**: Khắc phục mất module name, sai mã lỗi và tràn thanh ghi do inlined loop.
- **impact**: Registry load chính xác, an toàn, không rò rỉ bộ nhớ hoặc sinh lỗi giả.

### `compiler/src/main/path_util.vri`
- **change**: Hiện thực `inc_report_early_error_related`, bảo toàn toạ độ vật lý `span_id = 0`.
- **reason**: Diagnostic renderer bị ghi đè dòng vật lý của `module.list` do source manager không map registry files.
- **impact**: Báo cáo lỗi hiển thị đúng dòng và cột vật lý của file cấu hình registry.

### `compiler/src/semantic/diagnostics/msg_frontend.vri`
- **change**: Định nghĩa lại text mô tả cho mã lỗi E2121 và E2123.
- **reason**: Khắc phục sự đảo lộn mô tả (project duplicate bị gán nhầm cho stdlib và ngược lại).
- **impact**: Người dùng và công cụ nhận diện chính xác bản chất lỗi.

### `tools/module_graph.py`
- **change**: Cập nhật logic collision check đồng nhất với native compiler.
- **reason**: Đảm bảo tính nhất quán giữa build tooling Python và native compiler.
- **impact**: Không có sự phân kỳ hành vi giữa các công cụ trong repository.

### `compiler/src/semantic/diagnostics/render.vri` và `tools/vir-lsp/src/main.vri`
- **change**: Chuẩn hoá secondary-note fat-string và cho phép publish diagnostic trên configuration source.
- **reason**: Classic output trước đó in note rỗng; LSP chỉ gửi notification root rỗng và bỏ E2123 trên `module.list`.
- **impact**: Cùng provenance xuất hiện trên classic, JSON và LSP.

## 6. Deviations from Plan

Corrective audit phát hiện lần nghiệm thu đầu tiên chưa đủ bằng chứng cho mapping values, LSP và active-sysroot parity. Vì vậy phạm vi implementation được mở rộng sang classic renderer, LSP publisher/serializer, checked-in fixture và CLI/LSP contract tests. Không thay đổi policy exact-reject/prefix-allow, public CLI hay manifest syntax.

## 7. Verification

### Tests

| Test Suite / Fixture | Command | Result | Evidence |
|---|---|---|---|
| Native CLI Contract Suite | `./run_tests.sh 18` | PASS (22/22) | Classic/JSON E2123 provenance assertions included |
| Native Module Resolver Suite | `./bin/module-resolver-test` | PASS (20/20) | `Result: 20/20 tests passed` |
| Group 3 Module Suite | `./run_tests.sh 3` | PASS (28/28) | Checked-in stdlib-collision fixture rejects before source use |
| Full Compiler Minimal Suite | `./run_tests.sh min` | PASS (506/506) | `KẾT QUẢ: THÀNH CÔNG (100% PASS)` |
| Exact Stdlib Collision (Classic) | `./bin/virc tests/modules/registry_stdlib_collision/stdlib_collision_rejected.vri -q --color=never` | PASS | Exit 1; E2123; project line 2; stdlib line 58; both mappings |
| Exact Stdlib Collision (JSON) | `./bin/virc tests/modules/registry_stdlib_collision/stdlib_collision_rejected.vri -q --json` | PASS | Exit 1; valid JSON; semantic fields agree with classic |
| Native LSP Collision Suite | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root "$PWD" --suite registry_collision` | PASS (3/3) | E2123 published on `module.list` with stdlib `relatedInformation` and both mappings |
| Native LSP Handshake | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root "$PWD" --suite handshake` | PASS (3/3) | Server identity and clean shutdown preserved |
| Full Native LSP Suite | `./bin/vir-lsp-test --lsp ./bin/vir-lsp --root "$PWD" --suite all` | PASS (117/117) | Shared publisher change causes no LSP regression |
| Python Resolver Parity | `python3 tools/module_graph.py --root tests/modules/registry_stdlib_collision --sysroot "$PWD" --resolve json` | PASS (expected exit 1) | E2123 one-line error with active-sysroot path/line/mappings |
| Compiler Fixed Point | stage 2b vs stage 3b, stripped signature | PASS | Both SHA-256 `94cc9258eba29795d797236d9b498397babd582cd5c23dae21d63b494e34fbd1` |
| Version Policy | `python3 tests/test_virc_version_policy.py` | PASS | `2026.1.14`, internal; VIRC and LSP metadata synchronized |

### Raw Diagnostic Evidence

Classic output contains the following semantic payload:

```text
Code        : [E2123] ModuleResolver
File        : tests/modules/registry_stdlib_collision/module.list
Line        : 2
Related     : /Users/gengyang/Vir-3.0/stdlib/stdlib.vri:58:1
project mapping: local_json.vri; standard library mapping: json.vri
Analysis    : project module 'json' collides with standard library
```

JSON output contains `code: "E2123"`, primary span `module.list:2:1`, and a related location at `stdlib/stdlib.vri:58:1` whose message is exactly `project mapping: local_json.vri; standard library mapping: json.vri`.

Python parity emits:

```text
[E2123] Project module 'json' collides with standard library at .../module.list:2; project mapping: local_json.vri; related: .../stdlib.vri:58; standard library mapping: json.vri
```

### Regression

Tất cả các bộ test regression hiện hữu bao gồm `cli-contract-test`, `module-resolver-test`, và toàn bộ 31 nhóm test của `run_tests.sh min` đều vượt qua 100% không có bất kỳ regression nào.

### Conformance

Đạt sự tuân thủ nghiêm ngặt theo các tiêu chuẩn:
- `VIR-SPC-0006` / `VIR-ISS-0008`: Reserved canonical standard library module IDs.
- `VIR-SPC-0014`: Module resolution and project registry semantics.
- `VPS` (VIR Paper Standard): Truy xuất nguồn gốc và kiểm chứng chặt chẽ.

## 8. Acceptance Criteria

- [x] Native focused test chứng minh exact project/stdlib collision fail tại registry load dù entry không được include/import. (*Minh chứng: Test 18 và checked-in fixture `tests/modules/registry_stdlib_collision/`*).
- [x] Prefix-only matrix (`http`/`http.app`, `json`/`json.app`, `db.sqlite`/`db.sqlite3`) pass; exact directory-alias key collision cũng fail. (*Minh chứng: Test 18 và Test 19 trong `module-resolver-test`*).
- [x] Cross-registry diagnostic chứa canonical ID, cả registry paths, line numbers và mapping values trong classic và JSON modes. (*Minh chứng: checked-in fixture chạy với classic và `--json` trong CLI contract*).
- [x] Duplicate stdlib, duplicate project và cross-registry collision có đúng classification cùng first/second declaration provenance. (*Minh chứng: E2121, E2123, E2126 phân định rõ ràng trong Test 2, Test 16, Test 18, Test 20*).
- [x] Native compiler, Python graph resolver và IDE/LSP registry path agree on exact-reject/prefix-allow policy and stable diagnostic identity. (*Minh chứng: native resolver, Python parity probe và LSP `registry_collision` 3/3*).
- [x] Collision validation uses the active sysroot stdlib selected under `VIRC-ISS-0043`, không một source-tree registry tình cờ khác version. (*Minh chứng: sử dụng `g_virc_stdlib_registry` / `g_ideStdlibRegistry`*).
- [x] Không public CLI/manifest escape hatch; test-only hooks không ảnh hưởng production contract. (*Minh chứng: không có flag hay bypass mechanism*).
- [x] Existing missing-target, prefix-collision, alias self-load, cycle/dedup and CWD-independence tests remain green. (*Minh chứng: Test 1 đến Test 15 trong `module-resolver-test` PASS 100%*).
- [x] Stage 2 == stage 3 bootstrap và accepted REPORT ghi raw diagnostics/test matrix trước khi ISSUE đóng. (*Minh chứng: stripped-signature SHA-256 `94cc9258...fbd1` cho cả hai stage và Section 7*).

## 9. Known Limitations

Không có limitation đã biết trong phạm vi ISS-0047. LSP có thể gửi notification rỗng cho root document để clear state trước notification E2123 của `module.list`; client phải xử lý stream `publishDiagnostics` theo URI như LSP quy định. Python graph resolver vẫn là tooling parity path, không thay thế native verification gate.

## 10. Remaining Work

Không còn công việc tồn đọng cho issue này.

## 11. Conclusion

`ACCEPTED — READY_FOR_CLOSE`

## 12. Related Papers

- [VIRC-ISS-0047](../issues/VIRC-ISS-0047_cross_registry_collision_diagnostics_lose_module_identity_and_registry_provenanc.md)
- [VIRC-PLN-0042](../plans/VIRC-PLN-0042_standardize_cross_registry_collision_diagnostics_and_provenance_tracking.md)
- [VIR-ISS-0008](../../VIR/issues/VIR-ISS-0008_standard_library_module_identifiers_are_not_normatively_reserved_against_project.md)
- [VIRC-ISS-0043](../issues/VIRC-ISS-0043_self_contained_toolchain_cannot_locate_active_stdlib_or_target_sysroot_from_ex.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Initial report created and accepted (READY_FOR_CLOSE) |
| 2026-10-10 | Corrective audit found missing mapping-value rendering, absent LSP configuration-source publication, incomplete Python active-sysroot selection, and insufficient contract coverage; prior acceptance claim retained for traceability |
| 2026-10-10 | Corrective implementation verified across classic, JSON, native LSP, Python parity, bootstrap fixed point, version policy and regression gates; report re-accepted |
