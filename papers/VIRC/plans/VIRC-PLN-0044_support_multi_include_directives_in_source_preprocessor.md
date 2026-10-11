---
id: "VIRC-PLN-0044"
type: "PLAN"
domain: "VIRC"
title: "Support multi-include directives in source preprocessor"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-preprocessing"
  - "module-resolution"
  - "parser"
  - "diagnostics"
related:
  issues:
    - "VIRC-ISS-0044"
  plans: []
  reports:
    - "VIRC-RPT-0061"
supersedes: null
superseded_by: null
tags:
  - "include"
  - "multi-include"
  - "source-preprocessing"
  - "spec-conformance"
---

# VIRC-PLN-0044 — Support multi-include directives in source preprocessor

## 1. Objective

Hiện thực hóa việc hỗ trợ đầy đủ cú pháp multi-include directive (`include a, b, c`) trong tầng tiền xử lý mã nguồn (`compiler/src/main/include_expander.vri`) theo đúng đặc tả `VIR-SPC-0006 §5.3`, `VIR-SPC-0014`, `VIR-SPC-0018 §448-453`, và `VIR-SPC-0021`. Đảm bảo mỗi module trong danh sách phân tách bằng dấu phẩy được phân giải độc lập, kiểm tra chu trình (cycle check), khử trùng lặp (deduplication), đăng ký IDE facts và visibility metadata, và ghép mã nguồn tuần tự với source marker `@vir_source` chính xác; đồng thời từ chối cú pháp phi chuẩn include alias (`include m as a`) với diagnostic rõ ràng.

## 2. Source Issues

- **VIRC-ISS-0044**: Multi-include directives fail instead of loading every listed module (`status: IMPLEMENTING`, `severity: S2`, `priority: P1`).

## 3. Scope

### In Scope

- Cải tiến parser cú pháp `include` tại tầng tiền xử lý văn bản nguồn (`compiler/src/main/include_expander.vri`):
  - Phân tích danh sách module targets phân tách bằng dấu phẩy `,`.
  - Hỗ trợ đầy đủ định dạng unquoted identifiers/paths và quoted string literals `"path/to/mod.vri"`.
  - Xử lý linh hoạt khoảng trắng bao quanh dấu phẩy, dấu chấm phẩy `;` tùy chọn ở cuối câu lệnh, và comment `# ...`.
  - Phát hiện và từ chối cú pháp `include ... as ...` (include alias không được hỗ trợ theo `VIR-SPC-0021`) bằng mã lỗi `E2101`.
  - Phát hiện và từ chối dấu phẩy thừa ở đuôi hoặc danh sách rỗng (`include a,`).
- Cải tiến vòng lặp đệ quy mở rộng include (`expand_include_recurse`):
  - Lặp qua từng module target trong danh sách theo đúng thứ tự khai báo.
  - Phân giải canonical identity, phát hiện lỗi thiếu file `E2102` chính xác cho từng target (không gộp chuỗi).
  - Kiểm tra chu trình phụ thuộc `E2105` cho từng target.
  - Khử trùng lặp (`g_inc_has`) và chèn marker `# [include duplicate: ...]`.
  - Chèn source markers `# @vir_mod_start`, `# @vir_source`, `# @vir_mod_end`, và khôi phục source marker của file gọi `# @vir_source <parent> <line>` chính xác sau khi kết thúc chuỗi ghép.
  - Thu thập IDE facts (`ideCaptureResolvedModule`, `ide_register_include`) cho từng target.
- Cải tiến AST parser (`compiler/src/frontend/parser/stmt_module.vri`):
  - Từ chối `as alias` khi gặp token `TokType.As` trong câu lệnh `include`, phát sinh diagnostic `E2101` đồng bộ với spec.
- Thêm kiểm thử hồi quy và fixture native độc lập:
  - Multi-include với 2, 3 và nhiều target.
  - Multi-include kết hợp quoted path và dotted module IDs.
  - Multi-include với khoảng trắng và chấm phẩy.
  - Kiểm thử từ chối `as alias` và dấu phẩy đuôi.
  - Kiểm thử deduplication và cycle detection qua multi-include.
- Tự biên dịch compiler qua fixed-point bootstrap (`stage 2 == stage 3`) và chạy toàn bộ test suites.

### Out of Scope

- Selective symbol import (`import a, b from m`) và umbrella import (`import * from m`).
- Whole-module import namespace execution và symbol collision boundary giữa các module độc lập (thuộc phạm vi sở hữu của `VIRC-ISS-0065`).

## 4. Current Architecture

1. **Quá trình biên dịch**:
   - `expand_includes_text` chạy trước lexer và parser, quét toàn bộ mã nguồn để tìm dòng bắt đầu bằng `include ` (`text_find_include_at`).
2. **Hạn chế của `text_parse_include_name`**:
   - `text_parse_include_name(source, at)` chỉ đọc một tên duy nhất sau `include `. Nếu không có dấu ngoặc kép `"`, hàm đọc các ký tự cho đến khi gặp khoảng trắng (`32`), tab (`9`), chấm phẩy (`59`), hoặc ký tự xuống dòng (`10`, `13`).
   - Do đó, với `include a, b`, nó dừng ngay tại khoảng trắng sau `a,`, trả về chuỗi `a,` bao gồm cả dấu phẩy!
   - Resolver nhận chuỗi `a,` và tìm trong registry, dẫn đến thất bại `E2102: included source not found: 'a,'`.
3. **Mã nguồn AST parser (`stmt_module.vri`)**:
   - Trong `compiler/src/frontend/parser/stmt_module.vri:221-259`, AST parser đã có vòng lặp qua `TokType.Comma`, nhưng vòng lặp này chấp nhận cả `check(p2, TokType.As)` và gán vào `n.name2`, trái với tinh thần `VIR-SPC-0021` (include là file composition, không tạo namespace nên không có alias). Do preprocessor luôn chạy trước và nuốt sạch câu lệnh include, mã này trong parser chưa đồng bộ.

## 5. Proposed Architecture

### 5.1. Bộ phân tích câu lệnh Include tại tầng Preprocessor

Định nghĩa hàm phân tích câu lệnh toàn diện `text_parse_include_stmt(source: int, at: int)`:
- Quét qua từ khóa `include ` và bỏ qua khoảng trắng ngang.
- Vòng lặp thu thập các module target:
  - Nếu gặp `"`, đọc chuỗi ký tự bên trong dấu ngoặc kép cho tới dấu `"` đóng.
  - Nếu không có `"`, đọc các ký tự hợp lệ của định danh/đường dẫn module (dừng tại whitespace, comma, semicolon, newline, comment `#`, hoặc quote).
  - Lưu trữ target vào mảng tạm thời `items_buf`.
  - Bỏ qua khoảng trắng ngang tiếp theo.
  - Kiểm tra xem có token cấm `as` không: nếu có, thiết lập lỗi cú pháp `E2101` với thông điệp `"include alias 'as' is not supported; include does not create a namespace"`.
  - Kiểm tra ký tự phân tách:
    - Nếu là dấu phẩy `,`: bỏ qua dấu phẩy và khoảng trắng tiếp theo; kiểm tra xem có target hợp lệ tiếp theo không (nếu gặp newline, semicolon, `#`, hoặc EOF -> báo lỗi `E2101` do dấu phẩy ở đuôi).
    - Nếu không phải dấu phẩy: thoát vòng lặp target.
- Kiểm tra các ký tự còn lại trên dòng:
  - Cho phép dấu chấm phẩy `;` tùy chọn, comment `# ...`, và kết thúc bằng newline `\n` hoặc EOF.
  - Báo lỗi `E2101` nếu có token lạ không mong muốn.
- Trả về số lượng target `count`, mảng target `items`, vị trí kết thúc câu lệnh `end_at`, và mã trạng thái lỗi `err`.

### 5.2. Mở rộng đa Module trong `expand_include_recurse`

Trong `expand_include_recurse`:
- Gọi `text_parse_include_stmt(source, at)`.
- Nếu có lỗi cú pháp, báo `inc_report_early_error(2101, cur_file, cur_line, err_msg)`.
- Lưu trữ các biến `items_buf`, `items_count`, `end_at`, `resume_line` vào biến cục bộ của khung ngăn xếp hàm (stack frame), đảm bảo an toàn tuyệt đối khi hàm đệ quy được gọi bên trong thân của từng target.
- Lặp qua từng target `k = 0 .. items_count - 1`:
  - Lấy `iname = native_read_i64(items_buf, k * 8)`.
  - Phân giải target qua `read_include_source(iname)`.
  - Ghi nhận thông tin IDE facts qua `ideCaptureResolvedModule` và `ide_register_include`.
  - Nếu không tìm thấy module (`body == 0`): báo lỗi sớm `E2102` chỉ rõ đúng `iname` bị thiếu và dòng gọi.
  - Ghi nhận visibility metadata qua `import_visibility_register_include` và `import_visibility_register_module_identity`.
  - Kiểm tra chu trình `cycle_found`: báo lỗi `E2105` nếu phát hiện phụ thuộc vòng.
  - Khử trùng lặp qua `g_inc_has`:
    - Nếu đã include: ghi `# [include duplicate: <key>]\n`.
    - Nếu chưa include: đánh dấu `g_inc_mark`, thêm vào `g_cycle_stack`, chèn `# @vir_mod_start <key>\n# @vir_source <body_path> 1\n`, gọi đệ quy `expand_include_recurse(body, body_path, sb)`, xóa khỏi `g_cycle_stack`, và chèn `# @vir_mod_end <key>\n`.
- Sau khi kết thúc tất cả target của câu lệnh:
  - Nếu có ít nhất một target được mở rộng (không bị duplicate hoàn toàn), phát sinh source marker phục hồi vị trí của file cha:
    `# @vir_source <cur_file> <resume_line>\n`.
- Cập nhật `cur_line = resume_line` và `pos = end_at`.

### 5.3. Đồng bộ hóa AST Parser (`stmt_module.vri`)

- Khi gặp `TokType.As` trong mệnh đề `include`, parser gọi `parse_error_code_loc` với mã lỗi `2101` và thông báo `"include statement does not support alias 'as'"`.

## 6. Design Decisions

### Decision 1: Phân tách việc phân tích và mở rộng thành hai bước rõ ràng

- **Decision**: Phân tích toàn bộ danh sách target của câu lệnh `include` trên dòng trước khi tiến hành phân giải và nạp file đệ quy.
- **Rationale**: Tránh việc nạp dở dang một module rồi mới phát hiện cú pháp của các module phía sau bị sai hoặc có dấu phẩy đuôi. Phân tích trước đảm bảo fail-closed ngay lập tức tại vị trí cú pháp lỗi mà không làm thay đổi trạng thái global cache/cycle stack.
- **Alternatives considered**: Vừa đọc vừa phân giải từng token. Bị loại bỏ vì khó khôi phục trạng thái khi module thứ 2 có lỗi cú pháp.

### Decision 2: Lưu trữ danh sách target cục bộ trong stack frame của hàm đệ quy

- **Decision**: Cấp phát mảng con trỏ target qua `vir_alloc(count * 8)` và giữ địa chỉ mảng trong biến cục bộ `items_buf` của hàm `expand_include_recurse`.
- **Rationale**: Khi một module con chứa câu lệnh `include` khác, lời gọi đệ quy sẽ tự phân tích và cấp phát mảng riêng trên stack frame của nó. Khi lời gọi con kết thúc, biến `items_buf` của khung cha vẫn giữ nguyên vẹn để tiếp tục duyệt target tiếp theo trong danh sách.
- **Alternatives considered**: Dùng mảng toàn cục cố định. Bị loại bỏ vì đệ quy lồng nhau sẽ ghi đè dữ liệu của khung cha.

### Decision 3: Khôi phục `# @vir_source` của file cha sau khi kết thúc chuỗi ghép

- **Decision**: Đặt `# @vir_source <cur_file> <resume_line>` ở cuối câu lệnh multi-include khi có ít nhất một module được mở rộng.
- **Rationale**: Mỗi module con được kẹp giữa `# @vir_mod_start` và `# @vir_mod_end`. Đặt source marker khôi phục file cha ở cuối toàn bộ danh sách đảm bảo mã nguồn tiếp theo của file cha giữ nguyên toạ độ dòng chính xác mà không phát sinh marker thừa giữa các module con liền kề.

## 7. Implementation Plan

### Phase 1 — Cải tiến `compiler/src/main/include_expander.vri`

- Thêm `text_parse_include_stmt(source: int, at: int)` hỗ trợ danh sách dấu phẩy, quoted path, kiểm tra alias `as`, và dấu phẩy đuôi.
- Cập nhật `expand_include_recurse` để lặp qua danh sách target, phân giải, kiểm tra lỗi, khử trùng lặp và chèn source markers.
- Cập nhật `text_find_include` / `text_find_include_at` để chấp nhận tab sau `include`.

### Phase 2 — Đồng bộ hóa AST Parser trong `compiler/src/frontend/parser/stmt_module.vri`

- Từ chối `TokType.As` trong `stmt_module.vri` với mã lỗi `2101`.

### Phase 3 — Tạo test fixtures và kiểm thử độc lập

- Tạo fixture tái hiện `VIRC-ISS-0044` (`tests/modules/multi_include_positive/`): `include a, b` trả về 42.
- Tạo fixture kiểm thử cú pháp: `include a, "path/b.vri", c;`, khoảng trắng quanh dấu phẩy.
- Tạo fixture kiểm thử âm tính: `include a as A, b` -> E2101; `include a,` -> E2101.
- Tạo fixture kiểm thử lỗi thiếu file: `include a, non_existent` -> E2102 trỏ đúng `non_existent`.

### Phase 4 — Fixed-Point Bootstrap và Toàn bộ Test Suite

- Biên dịch `bin/virc` mới qua `sync_virc.py` và self-compilation.
- Kiểm tra bootstrap 3 giai đoạn: `bin/virc.stage2` == `bin/virc.stage3` (`cmp` == 0).
- Chạy `./bin/cli-contract-test --virc ./bin/virc`.
- Chạy `./bin/module-resolver-test` (với `BypassSandbox: true`).
- Chạy `./run_tests.sh min` (với `BypassSandbox: true`).

## 8. Compatibility

- **Source compatibility**: Hoàn toàn tương thích ngược với mọi câu lệnh single-include hiện hành (`include a`, `include "path"`). Không làm thay đổi hành vi của các file mã nguồn hiện tại.
- **Spec compatibility**: Khôi phục sự tuân thủ nghiêm ngặt với `VIR-SPC-0006 §5.3`, `VIR-SPC-0014`, `VIR-SPC-0018 §448-453`, và `VIR-SPC-0021`.

## 9. Migration

Không yêu cầu migration cho mã nguồn hợp lệ. Bất kỳ mã nguồn nào từng dựa vào cú pháp không chính thức `include m as a` (nếu có) sẽ nhận được diagnostic lỗi `E2101` rõ ràng hướng dẫn chuyển sang cú pháp chuẩn.

## 10. Validation Plan

- Kiểm thử đơn vị và tích hợp:
  - Fixture tái hiện `VIRC-ISS-0044`: `include a, b` trả về 42.
  - Multi-include 3 targets: `include a, b, c` trả về tổng của cả 3.
  - Quoted paths kết hợp unquoted identifiers trong cùng danh sách.
  - Khoảng trắng phức tạp và dấu chấm phẩy kết thúc.
  - Từ chối include alias: `include a as A` và `include a, b as B` phát sinh E2101.
  - Báo lỗi chính xác target bị thiếu: `include a, missing` phát sinh E2102 trỏ đúng `missing`.
  - Khử trùng lặp: `include a, b, a` không load lại `a` lần hai.
- Kiểm thử toàn hệ thống:
  - Bootstrap fixed-point `stage 2 == stage 3`.
  - 100% pass trên 506+ tests của `./run_tests.sh min`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lệch toạ độ dòng (source marker line shift) sau multi-include | Thấp | Trung bình | Tính toán chính xác `resume_line = cur_line + inc_count_newlines(source, at, end_at)` và chỉ phát sinh marker phục hồi ở cuối câu lệnh |
| Đệ quy lồng nhau ghi đè target list của câu lệnh cha | Thấp | Cao | Cấp phát vùng nhớ target bằng `vir_alloc` và lưu con trỏ trong biến cục bộ stack frame |
| Trùng lặp tên hàm giữa các include fragments | Trung bình | Thấp | Theo `VIR-SPC-0021`, include là same-scope composition; duplicate function redefinition được kiểm soát theo luật của compiler |

## 12. Rollback Strategy

Khôi phục lại file `compiler/src/main/include_expander.vri` và `compiler/src/frontend/parser/stmt_module.vri` từ git HEAD `git checkout HEAD -- compiler/src/`.

## 13. Exit Criteria

- [x] Fixture native `include a, b` biên dịch thành công và thực thi trả về mã 42.
- [x] Multi-include hỗ trợ 2, 3 và nhiều target, kết hợp quoted path và unquoted identifiers.
- [x] Cú pháp include alias `include a as A` bị từ chối với diagnostic E2101.
- [x] Dấu phẩy ở đuôi `include a,` bị từ chối với diagnostic E2101.
- [x] Module không tồn tại trong danh sách báo lỗi E2102 trỏ đúng tên module bị thiếu.
- [x] Deduplication và cycle detection hoạt động chính xác trên multi-include.
- [x] Self-hosting bootstrap đạt fixed-point: `stage 2 == stage 3` bit-for-bit identical.
- [x] Toàn bộ bộ test suites `./run_tests.sh min` đạt 100% pass.
- [x] Viết báo cáo nghiệm thu `VIRC-RPT-0061` và hoàn tất cập nhật registry/validate papers.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0044_multi_include_directives_fail_instead_of_loading_every_listed_module.md`
- `papers/VIR/specs/VIR-SPC-0006_module_include_system.md`
- `papers/VIR/specs/VIR-SPC-0014_modules_ai_spec.md`
- `papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md`
- `papers/VIR/specs/VIR-SPC-0021_include_and_whole_module_import_dependency_contract.md`
- `papers/VIRC/issues/VIRC-ISS-0065_include_text_splicing_does_not_provide_uniform_collision_free_dot_style_module_n.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created initial implementation plan for VIRC-ISS-0044 |
| 2026-10-10 | Linked VIRC-RPT-0061 |
| 2026-10-10 | Marked COMPLETED with verification report VIRC-RPT-0061 |
| 2026-10-10 | Corrected stale related-paper paths discovered during closure audit; implementation intent remains unchanged |
