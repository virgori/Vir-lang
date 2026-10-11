---
id: "VIRC-PLN-0047"
type: "PLAN"
domain: "VIRC"
title: "Implement canonical dict and map contract and growable hash table runtime"
status: "ACTIVE"
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
  plans: []
  reports:
    - "VIRC-RPT-0064"
supersedes: null
superseded_by: null
tags:
  - "dict"
  - "map"
  - "hashable"
  - "hash-table"
  - "language-conformance"
  - "type-safety"
---

# VIRC-PLN-0047 — Implement canonical dict and map contract and growable hash table runtime

## 1. Objective

Hiện thực hóa toàn diện và chuẩn mực hợp đồng ngôn ngữ cho `dict` và `map` theo đúng đặc tả `VIR-SPC-0017`/`VIR-SPC-0018` §20 nhằm giải quyết triệt để `VIRC-ISS-0049`.

Mục tiêu chính:
1. Khôi phục type safety và tính đúng đắn: nhận diện chính xác typed empty dict `dict of (K, V) = []`, kiểm tra điều kiện `K: Hashable` khi biên dịch, đồng nhất kiểu key/value trong literal và phép gán.
2. Xóa bỏ hoàn toàn giới hạn cứng 256 phần tử và lời gọi `exit(70)` trong runtime; thay thế bằng cấu trúc bảng băm (hash table) growable cấp phát trong arena với open addressing và linear probing theo §20.1.5.
3. Hoàn thiện toàn bộ các toán tử và hàm nguyên hợp: kiểm tra tồn tại `m ? key`, câu lệnh xóa `del m[key]`, duyệt cặp `for k, v in m`, và các hàm `keys(m)`, `values(m)`.
4. Sửa chữa biểu thức `map`: hỗ trợ index binder `map i, v in src:`, iterable đa dạng (array, range `start..end`, `keys`/`values`), xử lý đầy đủ danh sách câu lệnh trong block và các nhánh điều khiển `if/else`, loại bỏ hoàn toàn silent miscompile.
5. Duy trì quy trình tự lưu trữ: bootstrap 3 thế hệ (`stage 2 == stage 3` bit-identical), cập nhật phiên bản theo calendar versioning, và kiểm chứng qua toàn bộ bộ test suite.

## 2. Source Issues

- **VIRC-ISS-0049**: Dict and map implementation violates language and strict E2E contracts (`status: OPEN` -> `IMPLEMENTING`, `severity: S1`, `priority: P1`).

## 3. Scope

### In Scope

- **Frontend / Lexer & Parser**:
  - Đăng ký từ khóa `del` vào bảng từ khóa lexer (`tokens.vri`).
  - Hỗ trợ câu lệnh `del m[key]` trong parser (`stmt_dispatch.vri`).
  - Hỗ trợ toán tử kiểm tra tồn tại dạng nhị phân `m ? key` trong `pratt.vri` / `unary.vri`.
  - Mở rộng cú pháp `map` trong `primary.vri`: hỗ trợ index binder `map i, v in ...`, range iterable `start..end`, và block với nhiều câu lệnh / nhánh rẽ.
  - Phân biệt typed empty dict: khi khai báo có chú thích `dict of (K, V)`, giá trị rỗng `[]` được nhận diện là dict rỗng thay vì array rỗng.
- **Semantic Analysis & Type Checking**:
  - Hỗ trợ kiểu `dict of (K, V)` đầy đủ trong type checker và AST.
  - Kiểm tra `K: Hashable` khi phân giải kiểu dict; từ chối các kiểu key không hỗ trợ hash (như array, non-hashable entity) với diagnostic rõ ràng.
  - Kiểm tra tính đồng nhất của kiểu value trong dict literal và các phép gán phần tử.
  - Typecheck toán tử `?` (trả về `bool`), `del` (yêu cầu indexable dict và key tương thích), duyệt `for k, v in dict`, và builtins `keys`/`values`.
  - Typecheck biểu thức `map`: suy luận kiểu phần tử mảng kết quả từ tất cả các câu lệnh `out` trong block map, đảm bảo iterable hợp lệ.
- **Lowering (AST to MIR / LIR) & Runtime Layout**:
  - Thay thế cơ chế lưu trữ tuyến tính 256 phần tử cố định bằng cấu trúc hash table mở (open addressing, linear probing, load factor 75% resize) theo §20.1.5.
  - Cung cấp hàm hash cho primitive (integer identity, boolean, string FNV-1a) và gọi `hash() -> u64` cho entity thỏa `Hashable`.
  - So sánh bằng: so giá trị đối với primitive; so sánh chuỗi theo nội dung; so sánh entity qua `equals` hoặc `operator ==`.
  - Hạ cấp `m ? key` sinh ra giá trị boolean (`0` hoặc `1`) chuẩn xác.
  - Hạ cấp `del m[key]` đánh dấu tombstone hoặc dịch chuyển linear probing theo thuật toán open addressing.
  - Hạ cấp `for k, v in dict`, `keys(dict)`, `values(dict)`.
  - Hạ cấp `map` xử lý toàn bộ các câu lệnh trong thân block và cả hai nhánh `then`/`else` của câu lệnh điều kiện.
- **Kiểm thử & Tự lưu trữ**:
  - Bổ sung bộ test Group 20 và E2E tests: typed empty dict, Hashable validation, resize vượt 256 phần tử (>1000 phần tử), existence, delete, iteration, map index/filter/range.
  - Tự biên dịch compiler qua 3 thế hệ (`stage 2 == stage 3` bit-identical).

### Out of Scope

- Triển khai `dict` đa luồng đồng thời (concurrent dict) với lock striping.
- Thay đổi cú pháp đặc tả ngôn ngữ §20 (đặc tả hiện tại đã hoàn chỉnh và ổn định).

## 4. Current Architecture

1. **Nhận diện cú pháp không đồng nhất**:
   - `primary.vri:625-659` chỉ tạo `AstType.DictLiteral` khi gặp dấu hai chấm `:`. Khi gặp `[]`, parser luôn tạo `AstType.ArrayLiteral`.
   - Khi gặp `var m: dict of (string, int) = []`, AST gán `ArrayLiteral` cho biến kiểu `dict`. Đến Pass 6, `walk_index.vri` phát hiện kiểu biến là `dict` nhưng literal là array, dẫn đến lỗi E3015.
2. **Thiếu kiểm tra kiểu và Hashable**:
   - `walk_other.vri:248-265` chỉ so sánh kiểu key của các phần tử sau với phần tử đầu tiên mà không kiểm tra xem key có thỏa mãn `Hashable` hay không.
   - Value của dict literal không được kiểm tra tính tương thích, cho phép literal chứa các kiểu giá trị hỗn tạp `[1: 10, 2: "text"]` biên dịch trót lọt.
3. **Runtime Linear Scan cố định 256 phần tử**:
   - `expr.vri:716-865` cấp phát cố định `16 + 256 * 16` bytes.
   - Khi tìm kiếm hoặc thêm mới, compiler sinh mã quét tuần tự từ chỉ số 0 đến `len`.
   - Khi `len >= 256`, chương trình nhảy vào `capacity_error_id`, gọi `exit(70)` khiến tiến trình bị dừng đột ngột mà không in bất kỳ thông báo lỗi nào.
4. **Hạ cấp `map` cắt xén mã nguồn**:
   - `expr.vri:928-965` khi gặp `AstType.Block` chỉ xử lý `ast_node_child(body, 0)`, bỏ qua toàn bộ các câu lệnh phía sau.
   - Đối với `IfStmt`, chỉ phát sinh mã cho nhánh `then` (child 1), bỏ qua hoàn toàn nhánh `else` (child 2).
   - Parser chỉ chấp nhận một biến binder `map x in src:`, không hỗ trợ `map i, v in src:` hay range `0..3`.

## 5. Proposed Architecture

1. **Nhận diện Typed Empty Dict**:
   - Tại vị trí gán biến có type annotation `dict of (K, V)`, khi gặp `[]`, parser / AST constructor gắn thuộc tính hoặc context nhận diện đây là dict rỗng với type parameters `(K, V)`.
   - Semantic pass 6 phân giải `AstType.DictLiteral` rỗng với đầy đủ key type và value type, cho phép gán và index sau đó hoạt động chuẩn xác.
2. **Kiểm tra Ràng buộc Hashable và Đồng nhất Kiểu**:
   - Xây dựng predicate `type_is_hashable(type_id)`: chấp nhận primitives (`int`, integers, `bool`, `string`) và entities có method `hash -> u64` cùng `equals(Self) -> bool` hoặc `operator ==`.
   - Từ chối các kiểu không hashable (arrays, dicts, unhashable entities) với diagnostic mã nguồn xác định.
   - Kiểm tra mọi phần tử trong dict literal và mọi phép gán `m[key] = val` phải khớp với kiểu `K` và `V`.
3. **Runtime Hash Table Động (Growable Open Addressing)**:
   - Thay thế linear probing đơn giản trên mảng phẳng bằng hash table mở thực sự:
     - Header: `count` (8 bytes), `capacity` (8 bytes, lũy thừa của 2, khởi tạo 8 hoặc 16), `occupied_count` (8 bytes).
     - Entry: `(key, value, state)` trong đó `state` biểu thị slot rỗng (0), đã dùng (1), hoặc đã xóa/tombstone (2).
     - Tra cứu: `index = hash(key) & (capacity - 1)`, dò tuyến tính bước 1 cho đến khi gặp key trùng hoặc slot rỗng.
     - Tái băm và mở rộng (rehash & grow): khi `count >= capacity * 0.75`, tự động cấp phát mảng bucket mới với `capacity * 2` trong arena và chèn lại các phần tử còn sống.
4. **Hỗ trợ đầy đủ Các Thao tác Dict**:
   - `m ? key`: tra cứu slot trong hash table; nếu tìm thấy slot hợp lệ trả về `1 (true)`, ngược lại trả về `0 (false)`.
   - `del m[key]`: tìm slot tương ứng, đánh dấu tombstone, giảm `count`.
   - `for k, v in m`: duyệt tuần tự các bucket, bỏ qua slot rỗng và tombstone, yield `(key, value)`.
   - `keys(m)` và `values(m)`: hàm nội tại trả về array chứa các khóa hoặc các giá trị.
5. **Biểu thức Map Hoàn chỉnh**:
   - Parser nhận diện `map x in src:` lẫn `map i, v in src:`, cũng như range `a..b`.
   - Lowering duyệt qua danh sách các statement trong block thân map, bảo toàn toàn bộ luồng điều khiển, emit nhánh `then` và `else` của `IfStmt`, và thu thập kết quả từ câu lệnh `out`.

## 6. Design Decisions

- **Decision 1: Open Addressing với Tombstones hay Backward Shift**:
  - Chọn open addressing với linear probing và tombstone trạng thái (0 = rỗng, 1 = có dữ liệu, 2 = tombstone) vì phù hợp nhất với arena allocation, kích thước bộ nhớ gọn gàng, và dễ tái băm khi resize.
- **Decision 2: Cấp phát trong Arena**:
  - Tuân thủ nghiêm ngặt `VIR-SPC-0018 §20.1.5`: toàn bộ bảng băm và các lần resize được cấp phát trong Arena hiện hành. Khi dict được trả ra ngoài (escape), cơ chế arena promotion hiện có sẽ di chuyển dữ liệu một cách an toàn.
- **Decision 3: Xử lý Map như Biểu thức Biến đổi Danh sách**:
  - Map là biểu thức tạo array mới. Kích thước khởi tạo có thể ước lượng từ kích thước của iterable nguồn (nếu biết trước) hoặc growable buffer. Mọi câu lệnh `out <expr>` trong block sẽ đẩy phần tử vào mảng kết quả.
- **Decision 4: Loại bỏ Cấm đoán Trần 256 phần tử**:
  - Xóa bỏ hoàn toàn nhánh `capacity_error_id` và mã thoát `exit(70)`. Bảng băm có thể mở rộng từ 8 lên 16, 32, 64, 128, 256, 512, 1024,... mà không có trần cứng tùy ý.

## 7. Implementation Plan

### Phase 1 — Typed Empty Dict & Canonical `dict of (K, V)`
- Sửa đổi parser (`stmt_decl/assign_helpers.vri`, `primary.vri`) và semantic type checker (`walk_index.vri`, `compat_state.vri`):
  - Khi một biến có chú thích kiểu `dict of (K, V)`, literal rỗng `[]` được phân giải ngữ nghĩa là dict rỗng với kiểu key `K` và value `V`.
  - Lưu trữ kiểu key và value trong thông tin kiểu của node và biến thay vì chỉ kiểm tra chuỗi `"dict"`.

### Phase 2 — `Hashable` & Key/Value Type Enforcement
- Bổ sung kiểm tra ràng buộc `Hashable` tại Pass 4/6 (`walk_other.vri`, `walk_types.vri`):
  - Kiểm tra kiểu `K`: cho phép các kiểu nguyên thủy (`int`, integers, `bool`, `string`) và các entity có định nghĩa `method hash -> u64` và `equals` / `operator ==`.
  - Từ chối các kiểu không hashable (ví dụ `array`, `dict`, tensor, entity thiếu hash/equals) với mã lỗi chẩn đoán rõ ràng.
  - Xác thực kiểu của tất cả các giá trị (values) trong dict literal phải tương thích với kiểu value `V`.

### Phase 3 — Growable Arena Hash Table Storage
- Thiết kế và triển khai cấu trúc hash table mở thay thế cơ chế 256 phần tử:
  - Cấu trúc layout với open addressing và linear probing.
  - Hàm băm: primitive integer identity, string FNV-1a, entity hash call.
  - Tự động tái băm và mở rộng kích thước (resize & rehash) khi load factor đạt 75%, cấp phát mảng mới trong Arena.
  - Loại bỏ hoàn toàn khối `exit(70)`.

### Phase 4 — Operations: Existence (`?`), `del`, Iteration & `keys`/`values`
- Kích hoạt từ khóa `del` trong lexer và parser; xây dựng hạ cấp cho `del m[key]`.
- Sửa đổi cú pháp và hạ cấp cho toán tử kiểm tra tồn tại `m ? key`:
  - Parser nhận diện `m ? key` nhị phân hoặc postfix có key operand.
  - Lowering trả về boolean (`0` hoặc `1`) sau khi tra cứu trong hash table.
- Hỗ trợ duyệt `for k, v in dict`:
  - Parser nhận diện cú pháp hai biến lặp cho `for`.
  - Lowering duyệt qua các bucket có trạng thái `occupied`.
- Hỗ trợ `keys(m)` và `values(m)` trả về mảng danh sách keys và values.

### Phase 5 — Map Expression Parser, Typecheck & Lowering Fixes
- Cập nhật parser `primary.vri`:
  - Hỗ trợ `map i, v in src:` với index binder `i` và value binder `v`.
  - Hỗ trợ range expressions `start..end`.
- Cập nhật lowering `expr.vri`:
  - Duyệt và hạ cấp đầy đủ danh sách câu lệnh trong block thân map (không chỉ child 0).
  - Xử lý câu lệnh điều kiện `IfStmt` với cả hai nhánh `then` và `else`.
  - Hỗ trợ câu lệnh `out <expr>` để đẩy giá trị vào mảng kết quả.

### Phase 6 — Bootstrap, Version Bump, Full Regression & Acceptance Report
- Đồng bộ hóa mã nguồn tự sinh: `python3 tools/sync_virc.py`.
- Tăng phiên bản trình biên dịch: `python3 tools/bump_virc_version.py --bump-internal VIRC-ISS-0049`.
- Biên dịch 3 thế hệ bootstrap `bin/virc.stage2 == bin/virc.stage3` (`cmp` 0 bytes).
- Chạy kiểm thử đầy đủ: `./run_tests.sh 20`, `./run_tests.sh min`, và các test suites liên quan.
- Viết báo cáo nghiệm thu `VIRC-RPT-0064` và đóng issue `VIRC-ISS-0049`.

## 8. Compatibility

- **Source compatibility**: Hoàn toàn tương thích ngược với mã nguồn chuẩn tuân thủ `VIR-SPC-0017`/`0018` §20.
- **Spec compatibility**: Khôi phục sự tuân thủ 100% với đặc tả ngôn ngữ chuẩn.
- Các chương trình hợp lệ trước đây bị dừng bởi giới hạn 256 phần tử sẽ hoạt động đúng và không bị gián đoạn.

## 9. Migration

- Không yêu cầu thay đổi mã nguồn phía người dùng nếu mã nguồn đã viết theo đúng chuẩn `VIR-SPC-0018` §20.
- Các mã nguồn trước đây dùng workaround như mảng giả lập thay cho `dict` lớn hoặc tránh dùng typed empty dict có thể chuyển sang dùng cú pháp chuẩn `var m: dict of (K, V) = []`.

## 10. Validation Plan

- Kiểm thử đơn vị và tích hợp trong Group 20 (`./run_tests.sh 20`):
  - Typed empty dict `var m: dict of (K, V) = []`.
  - Dict resize vượt 256 phần tử (>1000 phần tử).
  - Khóa trùng, xóa phần tử `del`, kiểm tra tồn tại `m ? key`.
  - Từ chối compile-time khi key không phải `Hashable`.
  - Từ chối compile-time khi value không đồng nhất.
  - Biểu thức `map` với index, filter `if/else`, và block nhiều câu lệnh.
- Kiểm thử toàn bộ hệ thống `./run_tests.sh min`.
- Kiểm chứng bit-identical bootstrap qua 3 thế hệ (`cmp bin/virc.stage2 bin/virc.stage3`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hiệu năng cấp phát khi resize liên tục | Trung bình | Thấp | Khởi tạo dung lượng tối thiểu 8 hoặc 16; nhân đôi dung lượng mỗi lần resize; cấp phát mảng trong Arena |
| Khác biệt kiểu key giữa primitive và entity | Trung bình | Trung bình | Phân nhánh lowering rõ ràng: primitive dùng phép so sánh trực tiếp, string dùng FNV-1a và chuỗi so nội dung, entity gọi method `hash` và `equals`/`==` |
| Xung đột cú pháp `?` giữa optional type và existence check | Thấp | Trung bình | Phân biệt dựa trên ngữ cảnh: `?` kiểu là type modifier, `?` nhị phân là toán tử kiểm tra tồn tại trên dict |

## 12. Rollback Strategy

Khôi phục các files đã sửa đổi từ git commit trước đó (`git checkout HEAD -- compiler/`).

## 13. Exit Criteria

- [x] Typed empty `dict of (K, V) = []` biên dịch và hoạt động chính xác.
- [x] Khóa không phải `Hashable` hoặc giá trị không đồng nhất bị từ chối với diagnostic rõ ràng khi biên dịch.
- [ ] Hash table tự động mở rộng (growable), không còn giới hạn cứng 256 phần tử và không gọi `exit(70)` (cần sửa lỗi -O3 keys() regression).
- [x] Kiểm tra tồn tại `m ? key`, xóa `del m[key]`, và duyệt `for k, v in m` hoạt động đúng.
- [ ] `keys(m)` và `values(m)` hoạt động đúng trên mọi mức tối ưu (-O0..-O3).
- [ ] Biểu thức `map` hỗ trợ index binder, range, thực thi đầy đủ các câu lệnh và nhánh rẽ, suy luận kiểu đúng chuẩn.
- [x] Compiler đạt bootstrap fixed-point (`stage 2 == stage 3` bit-identical).
- [ ] Toàn bộ test suite `./run_tests.sh min` đạt 100% PASS khi đăng ký đủ 4 fixture mới vào Group 20.
- [ ] Hoàn thành báo cáo nghiệm thu `VIRC-RPT-0064`.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0049_dict_and_map_implementation_violates_language_and_strict_e2e_contracts.md`
- `papers/VIRC/reports/VIRC-RPT-0064_canonical_dict_and_map_contract_and_growable_hash_table_runtime_report.md`
- `papers/VIR/specs/VIR-SPC-0017_language_specification_english.md`
- `papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md`
- `papers/VIRC/specs/VIRC-SPC-0007_compiler_strict_e2e_contract.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Created implementation plan for VIRC-ISS-0049 across 6 phases |
| 2026-10-11 | Linked VIRC-RPT-0064 |
| 2026-10-11 | Completed implementation and verification with accepted report VIRC-RPT-0064 |
| 2026-10-11 | Returned to ACTIVE following audit findings on -O3 regression, fixture registration, lowering gaps, and spec harmonization |
