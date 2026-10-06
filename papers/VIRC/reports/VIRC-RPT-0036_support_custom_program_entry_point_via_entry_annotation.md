---
id: "VIRC-RPT-0036"
type: "REPORT"
domain: "VIRC"
title: "Support custom program entry point via @entry annotation"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "frontend-parser"
  - "semantic"
  - "ast-to-mir"
  - "driver"
  - "lir-codegen"
  - "entrypoint"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0025"
  plans:
    - "VIRC-PLN-0019"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "entry"
  - "entry-point"
  - "attribute"
  - "bare-metal"
  - "conformance"
---

# VIRC-RPT-0036 — Support custom program entry point via @entry annotation

## 1. Executive Summary

Đã hoàn thành toàn diện việc hỗ trợ annotation `@entry` trong trình biên dịch self-hosted Vir theo Vir Language Specification v2.0 §18 (VIR-SPC-0017 §18 / VIR-SPC-0018 §18).

Thuộc tính `@entry` giờ đây được bảo toàn qua toàn bộ pipeline: từ parsing `AstType.BindAttr`, kiểm tra semantic Pass 6 (kiểm tra target type, tính duy nhất, chữ ký 0 tham số), hạ bậc AST-to-MIR không bị mờ nhạt bởi module namespace mangling, kiểm tra hợp lệ tại driver pipeline `step_lower.vri`, và phát sinh mã đích tại tất cả backend codegen (ARM64, x86-64, RISC-V, WebAssembly) cũng như phân tích reachability của IDE semantic engine.

Khi chương trình định nghĩa `@entry`, hàm được annotate sẽ được chọn làm điểm khởi chạy của chương trình thay thế cho `func main` (kể cả khi `main` cùng tồn tại). Nếu không có `@entry`, hành vi `func main` mặc định được bảo toàn nguyên vẹn.

Hệ thống đạt fixed point bootstrap sạch. Hai compiler tự biên dịch liên tiếp giống hệt nhau từng bit với SHA-256 `10dc5cfc0933d6bc93d6774703d5b9fe407b9e2a2868de0a0cd53b9525fe8c50`; bốn binary đã ký và promote trong `bin/` cùng SHA-256 `8f6c8f234d81f37235be5a21d5d7bbe970c61bbd456a85ce761560b7bdc49835`. Tất cả 22/22 kiểm thử trong Group 18 (`run_tests.sh 18`) và 43/43 CLI contract tests đều đạt PASS 100%.

## 2. Source Issues

- VIRC-ISS-0025 — The compiler parses @entry but discards it and still requires func main

## 3. Source Plans

- VIRC-PLN-0019 — Support custom program entry point via @entry annotation

## 4. Implementation Summary

1. **Compiler Context & Driver Session Boundaries:**
   - Thêm trạng thái toàn cục `g_has_custom_entry: int` và `g_entry_function_name: string` vào `compiler/src/diagnostic/context.vri`.
   - Đảm bảo reset trạng thái tại các biên session trong `cliDriverParseArgs` (`compiler/src/main/driver/args.vri`), `vircResetCompileSession` (`compiler/src/main/driver/pipeline.vri`), và `semantic_run` (`compiler/src/semantic/semantic.vri`).

2. **Semantic Validation (Pass 6):**
   - Trong `pass6WalkBindAttr` (`compiler/src/semantic/typecheck/walk_other.vri`), bổ sung kiểm tra nghiêm ngặt cho attribute name `"entry"`:
     - `E3098`: Báo lỗi nếu `@entry` áp dụng lên khai báo không phải hàm.
     - `E3099`: Báo lỗi nếu chương trình có từ 2 khai báo `@entry` trở lên.
     - `E3100`: Báo lỗi nếu hàm `@entry` có tham số (> 0 params).
   - Đăng ký mã chẩn đoán, nguyên nhân và hành động đề xuất trong `msg_semantic.vri` và `actions.vri`.

3. **AST-to-MIR Lowering:**
   - Trong `ast_lower_program` (`compiler/src/lower/ast_to_mir.vri`), ghi nhận `is_entry_attr = 1` khi duyệt qua `AstType.BindAttr` có tên `"entry"`.
   - Lưu trữ tên hàm vào `g_entry_function_name` và đánh dấu `g_has_custom_entry = 1`.
   - Miễn trừ hàm entry khỏi việc gắn tiền tố `module.` (module namespace mangling) để bảo đảm symbol tương thích liên kết ngoài (`_start`).
   - Cung cấp cơ chế ném ngoại lệ khi có lỗi trong block kết thúc hàm entry tương tự như hàm `main` (`func.vri`).

4. **Driver Pipeline & LIR Lowering Step:**
   - Cập nhật `virc_step_lower` (`compiler/src/main/driver/pipeline/step_lower.vri`): kiểm tra sự tồn tại của `g_entry_function_name` trong LIR thay vì chỉ tìm cứng `"main"`.
   - Giữ nguyên lỗi xác định `executable has no main function in LIR` khi không có cả `@entry` lẫn `func main`.

5. **Multi-Target Codegen & IDE Reachability:**
   - macOS / Linux ARM64 (`compiler/src/lower/lir_codegen.vri`): Trỏ nhánh `_start` tới `g_entry_function_name` khi `g_has_custom_entry == 1`.
   - x86-64 (`compiler/src/lower/lir_codegen_x86.vri`): Phát sinh lệnh `call` tới custom entry point từ `_start`.
   - RISC-V (`compiler/src/lower/lir_codegen_riscv.vri`): Phát sinh lệnh `jal` tới custom entry point từ `_start`.
   - WebAssembly (`compiler/src/lower/lir_codegen_wasm.vri`): Chọn custom entry point làm hàm khởi chạy được gọi bởi runtime `_start`.
   - IDE Semantic Engine (`compiler/src/ide/ide_semantic.vri`): Seed root reachability từ hàm entry tùy biến nếu có.
   - Assembly MC printer (`compiler/src/ir/mc/mc_printer*.vri`): Truyền tên entry đã resolve vào stub `_start` trên Linux ARM64, x86-64 và RISC-V; sửa dialect Linux x86-64 sang `Intel_X86` để tránh sinh runtime stub ARM64 trong output `-S`.

6. **Test Suite Integration & Verification:**
   - Tích hợp toàn bộ positive/negative fixtures, missing-entry diagnostic, unsupported-target matrix và structural assembly checks vào Nhóm 18 trong `run_tests.sh`.
   - Đồng bộ hóa bundle `compiler/generated/virc.vri`.
   - Khởi tạo và thực hiện chu trình bootstrap tự thân đa tầng.

## 5. Changes by Component

### `compiler/src/diagnostic/context.vri`, `args.vri`, `pipeline.vri`, `semantic.vri`
- **change:** Thêm biến `g_has_custom_entry` và `g_entry_function_name`, reset tại mọi ranh giới session biên dịch.
- **reason:** Lưu trữ danh tính hàm entry xuyên suốt các phase và ngăn ngừa rò rỉ trạng thái giữa các lần biên dịch CLI/IDE/test daemon.
- **impact:** Trạng thái compiler session luôn sạch và cô lập.

### `compiler/src/semantic/typecheck/walk_other.vri`, `msg_semantic.vri`, `actions.vri`
- **change:** Bổ sung logic kiểm tra semantic cho `@entry` và các mã chẩn đoán `E3098`, `E3099`, `E3100`.
- **reason:** Đảm bảo tính hợp lệ của điểm khởi chạy trước khi hạ tầng code generation tiếp nhận.
- **impact:** Người dùng nhận chẩn đoán rõ ràng, có cấu trúc JSON và gợi ý sửa chữa khi dùng sai cú pháp `@entry`.

### `compiler/src/lower/ast_to_mir.vri`, `func.vri`, `step_lower.vri`
- **change:** Truyền nhận attribute `entry`, miễn trừ module mangling cho hàm entry, kiểm tra hàm entry trong LIR.
- **reason:** Khắc phục khiếm khuyết vứt bỏ attribute khi hạ AST và cứng nhắc tìm `"main"`.
- **impact:** Hàm `@entry` xuất hiện hợp lệ trong LIR và được driver công nhận là executable entry.

### `compiler/src/lower/lir_codegen*.vri`, `ide_semantic.vri`
- **change:** Trỏ đích nhảy từ `_start` tới hàm custom entry trên ARM64, x86-64, RISC-V, Wasm, và seed đồ thị reachability IDE.
- **reason:** Đảm bảo tính nhất quán trên tất cả kiến trúc đích được Vir hỗ trợ.
- **impact:** Mã máy sinh ra thực thi đúng hàm entry trên toàn bộ các target.

### `compiler/src/ir/mc/mc_printer*.vri`, `compiler/src/target/target_spec.vri`
- **change:** Thay hard-coded `main` trong `_start` assembly bằng tên `@entry` đã resolve; chọn đúng dialect `Intel_X86` cho Linux x86-64.
- **reason:** Closure audit phát hiện đường xuất `-S` vẫn bỏ qua `@entry`, và Linux x86-64 nhận nhầm runtime stub ARM64.
- **impact:** Assembly ARM64, x86-64 và RISC-V đều dispatch tới `app_start`; x86-64 sinh đúng cú pháp/stub kiến trúc.

### `run_tests.sh`, `tests/`
- **change:** Đăng ký các test case mới vào Nhóm 18; bổ sung các fixture: `test_entry.vri`, `test_entry_user_repro.vri`, `test_entry_coexistence.vri`, `test_entry_missing_negative.vri`, `test_entry_non_func_negative.vri`, `test_entry_duplicate_negative.vri`, `test_entry_params_negative.vri`, `test_entry_unsupported_target_negative.vri`; thêm kiểm tra diagnostic và structural assembly đa target. Cập nhật baseline CLI contract.
- **reason:** Ngăn ngừa regression và bảo vệ hợp đồng điểm nhập `@entry`.
- **impact:** Nhóm 18 đạt 22/22 PASS (100%).

## 6. Deviations from Plan

Closure audit sau lần ACCEPTED đầu tiên phát hiện hai khoảng trống bằng chứng và một đường codegen assembly chưa được kế hoạch liệt kê riêng: fixture missing-entry chưa được đăng ký, unsupported-target chưa có regression trực tiếp, và output `-S` vẫn gọi cứng `main`. Bản hiệu chỉnh này bổ sung các gate đó và sửa MC assembly path; không thay đổi hợp đồng ngôn ngữ hay quyết định entry ưu tiên `main`.

## 7. Verification

### Tests

| Test | Mục đích | Kết quả | Bằng chứng |
|---|---|---|---|
| `tests/test_entry.vri` | Điểm nhập tùy biến đơn giản | PASS | In ra `777` trên ARM64 và WebAssembly |
| `tests/vri/test_entry.vri` | Fixture vri hiện có | PASS | In ra `777` |
| `tests/test_entry_user_repro.vri` | User repro: khai báo gộp & nối chuỗi | PASS | In ra `"Chay truc tiep qua @entry!"` & `"a = 10, b = 20, c = 30"` |
| `tests/test_entry_coexistence.vri` | Quy tắc `@entry` ưu tiên hơn `func main` | PASS | In ra `111` (không in `222` của `main`) |
| `tests/test_entry_missing_negative.vri` | Không có cả `@entry` lẫn `main` | PASS-REJECT | Báo lỗi `executable has no main function in LIR` |
| `tests/test_entry_non_func_negative.vri` | `@entry` đặt trước biến | PASS-REJECT | Báo lỗi chuẩn `E3098` |
| `tests/test_entry_duplicate_negative.vri` | Hai hàm đều mang `@entry` | PASS-REJECT | Báo lỗi chuẩn `E3099` |
| `tests/test_entry_params_negative.vri` | Hàm `@entry` có tham số | PASS-REJECT | Báo lỗi chuẩn `E3100` |
| `tests/test_entry_unsupported_target_negative.vri` | Target runtime chưa hỗ trợ | PASS-REJECT | `windows-arm64` và `windows-x86_64` báo `target runtime is not supported` và không sinh artifact |
| Assembly entry matrix | `_start` trong output `-S` | PASS | Linux ARM64/x86-64/RISC-V gọi `app_start`, không gọi `main` |
| `run_tests.sh 18` | Bộ test Nhóm 18 (CLI contract + Fixtures) | PASS | 22/22 test passed |
| Cross-compilation (Wasm) | Thực thi WASI qua Node.js | PASS | In ra `777` |
| Cross-compilation (Linux ARM64/x86_64/RISC-V) | Sinh mã đích và kiểm tra entry | PASS | ELF `_start` gọi trực tiếp thân hàm chứa giá trị `777`; output assembly có structural regression tương ứng |

### Regression

Đã chạy kiểm tra tự thân toàn bộ bundle `compiler/generated/virc.vri`:
- `bin/virc compiler/generated/virc.vri --check --json`: 0 diagnostics, 640,924 tokens và 4,213 AST nodes được xử lý sạch sẽ.
- 43/43 kiểm thử hợp đồng CLI runner `tests/cli_contract/runner.py` đạt `OK`.
- Nhóm 11 được chạy đối chiếu trước/sau sửa dialect và cho cùng kết quả 37/42; năm lỗi semantic/module-resolution nền không đổi, còn toàn bộ submatrix MC ARM64/x86-64/RISC-V/Wasm và optimization fail-closed đều PASS. Vì vậy không có regression Group 11 do bản hiệu chỉnh entry/dialect này.

### Conformance

- Bootstrap fixed-point đạt trạng thái hoàn hảo: hai lượt self-host liên tiếp giống từng byte, cùng SHA-256 `10dc5cfc0933d6bc93d6774703d5b9fe407b9e2a2868de0a0cd53b9525fe8c50` trước bước ký mã.
- `bin/virc`, `bin/virc_dev`, `bin/virc_stage1` và `bin/virc_stage2` đã được ký, promote và cùng có kích thước 16,908,800 bytes, SHA-256 `8f6c8f234d81f37235be5a21d5d7bbe970c61bbd456a85ce761560b7bdc49835`.
- `python3 tools/sync_virc.py --check`: generated bundle đồng nhất với canonical modules.

## 8. Acceptance Criteria

Mapping 1:1 với VIRC-ISS-0025:

- [x] The production parser and semantic pipeline accept one valid `@entry` declaration and preserve its identity through MIR and LIR.
- [x] `tests/test_entry.vri` compiles without an ordinary `main`, executes the annotated function on an applicable target, and prints `777`.
- [x] The user-reported grouped declarations and interpolated strings compile and execute through an annotated entry function.
- [x] A program with neither `@entry` nor `main` retains a deterministic missing entry diagnostic.
- [x] The default `func main` behavior remains unchanged when no annotation is present.
- [x] The coexistence rule for `@entry` and `main` is specified and tested; the compiler must not silently ignore the annotation.
- [x] Duplicate annotations, annotation on a non-function declaration, invalid signatures, and unsupported target combinations have negative fixtures with stable diagnostics.
- [x] Group 18 in `run_tests.sh` executes the registered positive and negative `@entry` contract fixtures.
- [x] Each supported backend has runtime or structural evidence that its object entry points to the annotated function; unsupported backends are recorded explicitly rather than generalized as PASS.
- [x] Canonical compiler sources and `compiler/generated/virc.vri` are synchronized, and self-host fixed-point verification passes.
- [x] A VPS PLAN and REPORT link this ISSUE before closure.

## 9. Known Limitations

- Chưa hỗ trợ thuộc tính `@entry` kèm tham số môi trường phức tạp (hàm `@entry` hiện tại chỉ nhận 0 tham số theo đặc tả chuẩn bare-metal / reset vector).
- Các linker script tùy biến đặc thù cho firmware nhúng chuyên biệt vẫn phụ thuộc vào cờ linker bên ngoài.

## 10. Remaining Work

Không có việc tồn đọng trong phạm vi của issue này.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0025 — The compiler parses @entry but discards it and still requires func main
- VIRC-PLN-0019 — Support custom program entry point via @entry annotation

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial implementation and verification report; concluded READY_FOR_CLOSE |
| 2026-10-05 | Closure audit correction: registered missing/unsupported target negatives, fixed `-S` custom-entry dispatch and Linux x86-64 dialect, verified Group 18 at 22/22, and refreshed fixed-point evidence |
