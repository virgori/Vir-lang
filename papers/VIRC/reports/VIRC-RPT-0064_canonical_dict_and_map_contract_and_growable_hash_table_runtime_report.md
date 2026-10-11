---
id: "VIRC-RPT-0064"
type: "REPORT"
domain: "VIRC"
title: "Canonical dict and map contract and growable hash table runtime report"
status: "REVIEW"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "compiler"
components:
  - "frontend"
  - "semantic-analysis"
  - "ast-to-mir"
  - "runtime-layout"
  - "regression-suite"
related:
  issues:
    - "VIRC-ISS-0049"
  plans:
    - "VIRC-PLN-0047"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "dict"
  - "map"
  - "hashable"
  - "hash-table"
  - "runtime"
  - "bootstrap"
---

# VIRC-RPT-0064 — Canonical dict and map contract and growable hash table runtime report

## 1. Executive Summary

Report này ghi nhận hiện trạng triển khai `VIRC-ISS-0049` và kế hoạch `VIRC-PLN-0047`.
Các thành phần nền tảng chính đã đạt được gồm:
- Typed empty dict `var m: dict of (K, V) = []` được nhận diện chính xác, loại bỏ lỗi `E3015`.
- Kiểm tra compile-time cho `Hashable` key (diagnostic `E3093`) và giá trị không đồng nhất (diagnostic `E3094`, bảo toàn quy tắc nới rộng số).
- Loại bỏ hoàn toàn giới hạn cứng 256 phần tử và lời gọi `exit(70)`; thay bằng open-addressing hash table trong Arena với linear probing và resize khi đạt load factor 75%.
- Toán tử `m ? key` và câu lệnh `del m[key]` đã hoạt động.
- Biểu thức `map` hỗ trợ cú pháp `map i, v in src:`, `start..end`, và block câu lệnh / nhánh rẽ `if/else`.
- Compiler đạt 3-stage bootstrap bit-identical (`bin/virc.stage2 == bin/virc.stage3`) với version `2026.1.19`.

Tuy nhiên, đợt audit toàn diện đã xác định 7 vấn đề còn tồn đọng cần xử lý dứt điểm trước khi đóng issue:
1. Regression ở `-O3`: `test_dict_canonical_contract.vri` in `500,1,0,499,0` (sai ở `len(keys(m))`, trong khi `-O0` in `500,1,0,499,499`).
2. 4 fixture mới chưa được đăng ký trong `run_tests.sh` Group 20 (thực tế chạy 11/11 chứ chưa phải 16/16; fixture chèn 500 phần tử, không phải 1.000).
3. Entity `Hashable` mới chỉ được type check tại `compat_state.vri:458`, chưa được lower để gọi method `hash` và `equals` tại `expr.vri:723`.
4. Chuỗi dùng hàm băm DJB2 (`expr.vri:735`) thay vì chuẩn FNV-1a theo `VIR-SPC-0017`/`VIR-SPC-0018 §20.1.4`.
5. Map type inference chưa hoàn chỉnh: `infer/walk.vri:158` hardcode binder type thành `Int`; `walk_other.vri:477` chưa suy luận / hợp nhất kiểu các biểu thức `out`.
6. Xung đột đặc tả chưa giải quyết: `VIRC-SPC-0007 §4` vẫn quy định layout contiguous 16-byte entry, mâu thuẫn với layout 24-byte bucket hiện hành.
7. Thiếu bằng chứng thực thi native trực tiếp trên Linux x86-64 và Linux arm64.

Do đó, báo cáo chuyển sang trạng thái cần tiếp tục hoàn thiện và issue `VIRC-ISS-0049` chuyển sang trạng thái `REOPENED`.

## 2. Source Issues

- **VIRC-ISS-0049**: Dict and map implementation violates language and strict E2E contracts (`status: REOPENED`, `severity: S1`, `priority: P1`).

## 3. Source Plans

- **VIRC-PLN-0047**: Implement canonical dict and map contract and growable hash table runtime (`status: ACTIVE`).

## 4. Implementation Summary

- **Frontend / Lexer & Parser**:
  - `compiler/src/frontend/lexer/tokens.vri`: Thêm token `TokType.Del`.
  - `compiler/src/frontend/parser/stmt/stmt_dispatch.vri` & `ast.vri`: Hỗ trợ câu lệnh `del m[key]`.
  - `compiler/src/frontend/parser/expr/unary.vri`: Hỗ trợ toán tử nhị phân `m ? key`.
  - `compiler/src/frontend/parser/expr/primary.vri`: Hỗ trợ `map i, v in src:`, `start..end`, và block nhiều câu lệnh.
- **Semantic Analysis & Type Checking**:
  - `compiler/src/semantic/typecheck/walk_decl.vri`: Gán `AstType.DictLiteral` khi type annotation là `dict of (K, V)` và literal là `[]`.
  - `compiler/src/semantic/typecheck/walk_other.vri`: Kiểm tra `Hashable` (E3093) và value homogeneity (E3094).
  - `compiler/src/semantic/names/walk.vri` & `infer/walk.vri`: Đăng ký symbol cho binder map.
- **Lowering (AST to MIR / LIR) & Runtime Layout**:
  - `compiler/src/lower/ast_to_mir/expr.vri`: Triển khai bảng băm open-addressing linear probing trong Arena (header `count`, `capacity`, `occupied_count`, bucket `key, value, state`). Xóa bỏ hoàn toàn trần 256 phần tử và `exit(70)`.
  - `compiler/src/lower/ast_to_mir/stmt.vri`: Hạ cấp `del m[key]` đánh dấu tombstone (state = 2).
  - `compiler/src/lower/ast_to_mir/calls.vri`: Hạ cấp `keys(m)` và `values(m)` với cơ chế cách ly không làm ảnh hưởng hàm người dùng tên `values()`.

## 5. Changes by Component

### `compiler/src/frontend/lexer/tokens.vri`
- **change**: Thêm `TokType.Del` cho từ khóa `"del"`.
- **reason**: Cho phép câu lệnh `del` theo `VIR-SPC-0018 §20.1.3`.
- **impact**: Lexer nhận diện đúng từ khóa `del`.

### `compiler/src/frontend/parser/stmt/stmt_dispatch.vri` & `ast.vri`
- **change**: Parse `del m[key]` thành `AstType.DelStmt`.
- **reason**: Cung cấp node AST cho thao tác xóa phần tử.
- **impact**: AST chuyển tiếp chuẩn xác cho semantic và lowering.

### `compiler/src/frontend/parser/expr/unary.vri`
- **change**: Parse `m ? key` thành biểu thức kiểm tra tồn tại 2 toán hạng.
- **reason**: Khắc phục lỗi parser cũ chỉ nhận toán tử postfix một toán hạng `m`.
- **impact**: Cả dict và key đều đi vào cây cú pháp.

### `compiler/src/frontend/parser/expr/primary.vri`
- **change**: Hỗ trợ `map i, v in src:`, khoảng `start..end`, và block câu lệnh.
- **reason**: Đồng bộ cú pháp với `VIR-SPC-0018 §20.2`.
- **impact**: Chấp nhận đầy đủ các dạng biểu thức map theo đặc tả.

### `compiler/src/semantic/typecheck/walk_decl.vri` & `walk_other.vri`
- **change**: Nhận diện `[]` là typed empty dict khi biến có type annotation `dict of (K, V)`; phát sinh E3093 (unhashable key) và E3094 (heterogeneous value).
- **reason**: Khôi phục type safety tĩnh cho container dict.
- **impact**: Loại bỏ lỗi E3015 sai lệch; từ chối compile-time các literal không hợp lệ.

### `compiler/src/lower/ast_to_mir/expr.vri`
- **change**: Thay thế quét tuyến tính 256 phần tử bằng hash table mở tự mở rộng trong Arena; hạ cấp thân map thực thi toàn bộ block và cả hai nhánh `then`/`else`.
- **reason**: Loại bỏ giới hạn cứng compiler và giải quyết silent miscompile của map.
- **impact**: Dict co dãn động; map xử lý luồng điều khiển chuẩn xác. Cần sửa lỗi SSA vreg tại `lower_dict_extract` gây sai ở `-O3`.

### `compiler/src/lower/ast_to_mir/stmt.vri` & `calls.vri`
- **change**: Hạ cấp `del m[key]` tombstone; hạ cấp `keys(m)` và `values(m)`.
- **reason**: Hoàn thiện các thao tác container chuẩn.
- **impact**: Hoạt động ở `-O0`, cần xử lý regression `-O3`.

## 6. Deviations from Plan

Đợt kiểm tra độc lập phát hiện các độ lệch và thiếu sót so với `VIRC-PLN-0047`:
1. **`-O3` keys extraction defect**: Trong `lower_dict_extract` (`expr.vri:1394-1452`), các biến đếm vòng lặp dùng lệnh `emit_move` trực tiếp trên Virtual Register qua các basic block mà không đi qua bộ nhớ cell hoặc SSA Phi node. Ở mức `-O3`, các pass tối ưu SSA coi đây là bất biến hoặc biến chưa khởi tạo, dẫn đến `len(ks)` trả về `0` thay vì `499`.
2. **Missing harness registration**: File `run_tests.sh` chưa bổ sung 4 fixture mới vào Nhóm 20. Do đó Nhóm 20 thực tế chỉ chạy 11/11 tests ban đầu, chưa chạy các fixture mới trong min/full test runner.
3. **Entity lowering gap**: Pass 6 kiểm tra interface `Hashable` của entity, nhưng hạ cấp `lower_dict_hash` và `lower_dict_eq` chưa phát sinh lời gọi method `hash() -> u64` và `equals()` cho entity key.
4. **Non-spec hash function**: Sử dụng DJB2 thay vì thuật toán FNV-1a chuẩn được yêu cầu tại `VIR-SPC-0017`/`VIR-SPC-0018 §20.1.4`.
5. **Incomplete map inference**: `infer/walk.vri` giả định mặc định kiểu phần tử của binder là `Int`; chưa tổng hợp suy luận kiểu từ tập các câu lệnh `out` trong thân map.
6. **Spec conflict**: Tài liệu `VIRC-SPC-0007 §4` chưa được cập nhật để thay thế định dạng cũ (contiguous 16-byte entry) bằng định dạng mới (24-byte entry open-addressing).
7. **Linux verification**: Chưa có log chạy thực tế trên máy Linux x86-64 và Linux arm64.

## 7. Verification

### Tests

| Test Suite / Component | Result | Evidence |
|---|---|---|
| Group 20: Dict & Map (hiện tại trong runner) | PASS | `./run_tests.sh 20`: 11/11 PASS |
| Full Min Regression Suite (hiện tại) | PASS | `./run_tests.sh min`: 546/546 PASS (100%) |
| `test_dict_canonical_contract.vri` (-O0) | PASS | `scratch/dict_opt0` in: `500, 1, 0, 499, 499` |
| `test_dict_canonical_contract.vri` (-O3) | FAIL | `scratch/dict_opt3` in: `500, 1, 0, 499, 0` (lỗi keys()) |
| `test_map_canonical_contract.vri` | PASS | Exit 0 ở cả -O0 và -O3 |
| `dict_unhashable_key_negative.vri` | PASS | Bị từ chối với `E3093` lúc compile |
| `dict_heterogeneous_val_negative.vri` | PASS | Bị từ chối với `E3094` lúc compile |

### Conformance & Bootstrap

- 3-stage bootstrap: `bin/virc.stage2` == `bin/virc.stage3` (21.723.924 bytes bit-identical).
- Compiler version: `2026.1.19` (self-hosted).
- Sync source: `python3 tools/sync_virc.py --check` pass.

## 8. Acceptance Criteria

Mapping 1:1 against `VIRC-ISS-0049`:

- [ ] **Resolve the normative conflict between `VIR-SPC-0017`/`0018` §20.1.5 and `VIRC-SPC-0007` §4; approved paper changes leave exactly one canonical dict representation/behavior contract.**
  - *Status*: Chưa đạt. Cần cập nhật `VIRC-SPC-0007 §4`.
- [x] **Typed empty `dict of (K, V) = []` compiles, supports all dict operations and retains `K`/`V` through inference, assignment, function calls and imports.**
  - *Status*: Đã đạt.
- [x] **Semantic analysis rejects every non-`Hashable` key and heterogeneous or incompatible value at compile time with stable, source-located diagnostics.**
  - *Status*: Đã đạt (`E3093` và `E3094`).
- [ ] **Primitive and entity hash/equality behavior conforms to §20.1.4, including collision tests proving equal hash alone does not imply equal key.**
  - *Status*: Chưa đạt (entity methods chưa được gọi trong lowering; string dùng DJB2 thay vì FNV-1a).
- [x] **Dict uses the approved arena-backed hash-table design with linear probing and 75% resize, or an explicitly revised active SPEC; there is no hard-coded 256-entry termination path.**
  - *Status*: Đã đạt về mặt cấu trúc bảng băm và xóa bỏ `exit(70)`.
- [ ] **Set/get/update/duplicate-key/len/existence/delete semantics pass for empty, singleton, collision-heavy, deleted-slot, resize and large dictionaries.**
  - *Status*: Chưa đạt do lỗi `len(keys(m))` ở `-O3`.
- [ ] **`for k, v in dict`, `keys(dict)` and `values(dict)` compile and run with documented unordered iteration behavior.**
  - *Status*: Chưa đạt ở `-O3`.
- [x] **`map` supports one binder, index/value binders, array, range, `keys`/`values`, filter and nested map exactly as §20.2 specifies.**
  - *Status*: Cú pháp và execution cơ bản đã đạt.
- [x] **Map lowering executes every permitted body statement and every reachable control-flow branch; unsupported bodies fail before MIR instead of silently emitting incomplete output.**
  - *Status*: Đã đạt.
- [ ] **Result element type is inferred from all reachable `out` expressions and incompatible emissions produce a compile-time diagnostic.**
  - *Status*: Chưa đạt (type inference của map chưa suy luận từ các câu lệnh `out`).
- [ ] **Ownership regressions cover move-after-use, borrow conflicts, arena escape/promotion, resize and deletion at `-O0` through `-O3`.
  - *Status*: Chưa đạt do regression ở `-O3`.
- [ ] **Group 20 replaces false map coverage with direct language `map` expressions and adds negative contracts for every formerly accepted invalid case; `test_adv_093_map.vri` is not counted as map-expression coverage.**
  - *Status*: Chưa đạt vì 4 fixture mới chưa được đăng ký vào `run_tests.sh`.
- [ ] **Focused and full suites pass on every supported native target affected by shared lowering, with Linux x86-64 and Linux arm64 evidence recorded rather than inferred from macOS arm64.**
  - *Status*: Chưa đạt (chưa ghi nhận evidence Linux).
- [x] **Generated compiler source is synchronized from canonical sources, self-host stage 2 equals stage 3, and module dependency validation passes.**
  - *Status*: Đã đạt.
- [x] **Completion follows `compiler/VERSIONING.md` and bumps the compiler calendar patch exactly once for this issue.**
  - *Status*: Đã tăng phiên bản lên `2026.1.19`.
- [ ] **An accepted REPORT maps every criterion to commands/results and records any unsupported backend or ABI limitation; no criterion is closed solely by compilation success.**
  - *Status*: Chưa đạt vì còn các tiêu chí chưa vượt qua kiểm chứng.

## 9. Known Limitations

- Hạ cấp `lower_dict_extract` gặp lỗi ở `-O3`.
- Hạ cấp entity key chưa gọi `hash` và `equals`.
- Thuật toán hash chuỗi hiện là DJB2 thay vì FNV-1a.
- Biểu thức `map` chưa suy luận kiểu động đầy đủ cho binder và mảng kết quả.
- `VIRC-SPC-0007` chưa được cập nhật tương thích với layout hash table 24-byte.

## 10. Remaining Work

1. Sửa lỗi `-O3` trong `lower_dict_extract` bằng cách dùng memory cells / proper loop lowering thay vì mutate bare vregs.
2. Hoàn thiện hạ cấp entity hash/equality trong `expr.vri` gọi method `hash() -> u64` và `equals() -> bool`.
3. Chuyển hàm băm chuỗi sang FNV-1a chuẩn theo đặc tả §20.1.4.
4. Cập nhật `walk_other.vri` và `infer/walk.vri` để suy luận kiểu binder và hợp nhất kiểu các `out` trong `map`.
5. Đăng ký đầy đủ 4 fixture mới vào `run_tests.sh` Nhóm 20 và mở rộng fixture kiểm thử 1.000 phần tử.
6. Cập nhật `VIRC-SPC-0007 §4` để chuẩn hóa layout open-addressing mới.
7. Thu thập log kiểm thử trên các môi trường native target (bao gồm Linux).

## 11. Conclusion

REQUIRES_FOLLOWUP

Các acceptance criteria chủ chốt chưa thỏa mãn đầy đủ bằng chứng thực tế tại `-O3`, chưa hỗ trợ trọn vẹn hạ cấp entity `Hashable`, và chưa đồng bộ hoàn toàn với đặc tả ABI. Cần tiếp tục hoàn thiện theo danh mục Remaining Work.

## 12. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0049_dict_and_map_implementation_violates_language_and_strict_e2e_contracts.md`
- `papers/VIRC/plans/VIRC-PLN-0047_implement_canonical_dict_and_map_contract.md`
- `papers/VIR/specs/VIR-SPC-0017_language_specification_english.md`
- `papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md`
- `papers/VIRC/specs/VIRC-SPC-0007_compiler_strict_e2e_contract.md`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Initial report draft |
| 2026-10-11 | Initial completion report |
| 2026-10-11 | Transitioned to REVIEW with conclusion status updated following audit finding 7 concrete implementation and verification gaps |
