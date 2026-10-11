---
id: "VIRC-PLN-0046"
type: "PLAN"
domain: "VIRC"
title: "Enforce whole module import namespaces and include composition boundaries"
status: "COMPLETED"
created: "2026-10-10"
updated: "2026-10-11"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-preprocessing"
  - "module-resolution"
  - "symbol-resolution"
  - "namespace-alias"
  - "import"
  - "typecheck"
  - "lowering"
  - "diagnostics"
related:
  issues:
    - "VIRC-ISS-0065"
  plans: []
  reports:
    - "VIRC-RPT-0063"
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "module-composition"
  - "module-namespace"
  - "namespace-alias"
  - "export-boundary"
  - "spec-conformance"
---

# VIRC-PLN-0046 — Enforce whole module import namespaces and include composition boundaries

## 1. Objective

Hiện thực hóa việc thực thi toàn diện ranh giới ngữ nghĩa giữa `include M` (same-module implementation composition) và whole-module `import M [as A]` (independent module namespace consumption) theo đúng đặc tả chuẩn `VIR-SPC-0021` (v1.0.0, ACTIVE) nhằm giải quyết dứt điểm `VIRC-ISS-0065`.

Cụ thể:
1. **Whole-module import namespace**: `import M` và `import M as A` phải bảo tồn module độc lập, ràng buộc namespace cục bộ `M` (hoặc alias `A`), và chỉ cho phép truy cập các khai báo được export tường minh qua cú pháp định danh có tiền tố (`M.symbol` hoặc `A.symbol`). Tuyệt đối không đưa các khai báo của module được import vào unqualified local scope của consumer.
2. **Fail-closed export boundary**: Các hàm/khai báo private trong provider không được phép truy cập qua qualified lookup và phải bị từ chối bằng diagnostic `E2113` rõ ràng.
3. **Độc lập và không xung đột giữa các providers**: Hai providers khác nhau cùng export một tên hàm ngắn (ví dụ `calc`) phải có thể import và sử dụng đồng thời trong cùng một consumer qua hai namespace riêng (`m1.calc()` và `m2.calc()`) mà không gây xung đột trùng tên toàn cục.
4. **Phân biệt module namespace và UFCS**: Bộ giải nghĩa tên phải phân biệt rạch ròi giữa module namespace (`SymbolKind.Module`) và biến cục bộ runtime receiver (`SymbolKind.Variable`) theo thứ tự ưu tiên và shadowing chuẩn.
5. **Từ chối kết hợp cả include và import trên cùng target (`E2115`)**: Thực thi quy tắc Single-Form Dependency của `VIR-SPC-0021 §2.7`. Consumer không được phép vừa `include M` vừa `import M` (hoặc `import ... from M`) cho cùng một canonical Module ID.
6. **Từ chối include alias (`E2101`)**: Phát hiện và từ chối cú pháp `include M as A` tại tầng preprocessor và parser với mã lỗi `E2101`.
7. **Phát hiện trùng lặp khai báo giữa các fragments (`E2004`)**: Hai fragments được `include` (hoặc fragment và consumer) khai báo trùng tên hàm trong cùng unqualified scope phải bị báo lỗi `E2004: Duplicate symbol definition` độc lập với thứ tự include (không silent coalescing hay last-wins).

## 2. Source Issues

- **VIRC-ISS-0065**: Whole-module import namespaces and include composition boundaries are not enforced (`status: IMPLEMENTING`, `severity: S2`, `priority: P1`).

## 3. Scope

### In Scope

- **Preprocessor (`include_expander.vri` & `import_expander.vri`)**:
  - Từ chối `include ... as ...` bằng diagnostic `E2101` thay vì âm thầm nuốt alias.
  - Theo dõi danh sách canonical module IDs đã `include` và `import` cho từng file; phát hiện và phát sinh lỗi `E2115` khi một consumer kết hợp cả include và import cho cùng một target.
  - Xử lý whole-module import `import M [as A]`: bao bọc nội dung module với chỉ thị chuyển đổi namespace `module <canonical_mod>` và hoàn trả `module root` (hoặc module của consumer); đăng ký thông tin namespace alias (`A -> canonical_mod`) và danh sách export của provider.
- **AST Parser & Module Collection (`stmt_module.vri` & `sem_pass1_modules.vri`)**:
  - Đăng ký `SymbolKind.Module` cho namespace gốc `M` và alias `A`.
  - Lưu bảng ánh xạ namespace alias trong ngữ cảnh ngữ nghĩa.
- **Symbol Registration (`symbols/context.vri` & `symbols/walk.vri`)**:
  - Đăng ký các hàm trong `module M` dưới tên chuẩn `M.func_name`.
  - Loại bỏ hành vi âm thầm bỏ qua trùng tên hàm tại scope 0 trong `pass2_register`; báo lỗi `E2004` khi phát hiện hai định nghĩa hàm khác nhau cùng tồn tại trong cùng unqualified scope.
- **Name Resolution & Type Checking (`names/walk_expr.vri` & `typecheck/walk_method.vri`)**:
  - Hỗ trợ gọi hàm qua module namespace hoặc module alias (`A.func(...)` -> phân giải alias thành `M.func(...)`).
  - Kiểm tra điều kiện export: chỉ các hàm nằm trong danh sách export của `M` mới được phép gọi; các hàm private bị từ chối với lỗi `E2113`.
  - Phân biệt giữa module namespace và runtime receiver UFCS.
- **Lowering (`ast_to_mir/calls.vri` & `ast_to_mir/context.vri`)**:
  - Nhận diện `is_module_call` chính xác kể cả khi gọi qua alias `A`, đảm bảo không truyền `recv` làm đối số thứ nhất vào hàm được gọi.
- **Kiểm thử & Tự lưu trữ**:
  - Bộ fixtures kiểm thử đầy đủ: positive whole-module import, module alias, không inject unqualified, hai provider trùng short name, từ chối private member `E2113`, từ chối include alias `E2101`, từ chối mixed include+import `E2115`, phát hiện trùng lặp khai báo `E2004`.
  - Tự biên dịch compiler qua 3 thế hệ (`stage 2 == stage 3` bit-for-bit identical) và vượt qua toàn bộ test suites.

### Out of Scope

- Cơ chế khởi tạo runtime module initialization order/cycles (cần đặc tả ngôn ngữ độc lập theo `VIR-SPC-0021 §2.9`).
- Tái cấu trúc các `*Namespace` facade hiện có trong thư viện chuẩn stdlib.
- Cú pháp umbrella import (đã bị loại bỏ khỏi chuẩn).

## 4. Current Architecture

1. **Preprocessor Flattening**:
   - Khi gặp whole-module `import M [as A]`, `import_expander.vri` chỉ đơn giản trả về nguyên văn `mod_body` của provider và xóa câu lệnh `import`.
   - Các hàm trong `mod_body` bị dán thẳng vào unqualified scope của consumer file.
   - Tên module `M` hoặc alias `A` hoàn toàn không tồn tại trong AST hoặc bảng ký hiệu; lời gọi `M.func()` hoặc `A.func()` thất bại với `E2001: Undefined variable in current scope`.
   - Ngược lại, lời gọi không định danh `func()` lại chạy được vì hàm bị inject bừa bãi vào root scope.
2. **Nuốt include alias**:
   - `include_expander.vri:487-503` quét qua `as <alias>` nhưng không báo lỗi mà chỉ bỏ qua, vi phạm nghiêm trọng `VIR-SPC-0021`.
3. **Silent Coalescing tại Scope 0**:
   - `compiler/src/semantic/symbols/context.vri:158` có đoạn mã `if curr_scope == 0 and old_kind == SymbolKind.Func and kind == SymbolKind.Func do out found end`, âm thầm hợp nhất hai khai báo hàm trùng tên mà không báo lỗi `E2004`.
4. **Hạ tầng Module Namespace có sẵn**:
   - Compiler đã có sẵn hỗ trợ gọi hàm module `mod.func(...)` tại `walk_method.vri:620` và `ast_to_mir/calls.vri:982` nếu hàm mang tên chuẩn `mod.func` và `node.builtin_id = 203`. Chỉ cần kết nối đúng preprocessor và symbol table để kích hoạt cơ chế này một cách chuẩn mực.

## 5. Proposed Architecture

### 5.1. Tiền xử lý Whole-Module Import & Đóng gói Namespace

Trong `compiler/src/main/import_expander.vri`:
- Khi `g_imp_sym_count == 0` (câu lệnh `import M [as A]`):
  - Phân giải target `M` lấy `provider_path` và `canonical_mod = g_inc_canonical_id` (nếu không có thì dùng `g_imp_mod`).
  - Ghi nhận `canonical_mod` và alias `A` (nếu có `g_imp_alias`) vào bảng namespace của compiler.
  - Kiểm tra xem provider có export nào không: nếu không có export, đánh dấu export surface rỗng.
  - Bao bọc nội dung module provider:
    ```vir
    module <canonical_mod>
    # @vir_source <provider_path> 1
    <mod_body>
    # @vir_source <cur_file> <resume_line>
    module root
    ```
  - Thay vì dán thô, cấu trúc này đưa toàn bộ định nghĩa trong provider vào scope của `module <canonical_mod>`, ngăn không cho bất kỳ hàm nào rò rỉ vào unqualified scope của consumer.
  - Tạo hoặc lưu trữ câu lệnh AST `ImportStmt` biểu diễn việc import `canonical_mod` với alias `A` vào consumer scope.

### 5.2. Đăng ký Ký hiệu & Ánh xạ Alias

- Trong `sem_pass1_modules.vri`:
  - Cho `ImportStmt` whole-module: đăng ký `SymbolKind.Module` cho `M` và nếu có alias `A`, đăng ký cả `A`.
  - Lưu bảng ánh xạ alias: `g_module_aliases[A] = M`.
- Trong `symbols/walk.vri`:
  - Khi `g_pass2_cur_module == M`, các hàm được đăng ký dưới dạng `M.func_name`.
- Trong `symbols/context.vri` (`pass2_register`):
  - Loại bỏ việc bỏ qua lỗi trùng tên hàm tại scope 0. Nếu `found != -1` và `old_kind == SymbolKind.Func` và `kind == SymbolKind.Func`:
    - Nếu hai hàm đến từ hai AST node khác nhau thuộc cùng một logical module (không phải từ deduplication file giống hệt), phát sinh diagnostic `E2004: Duplicate symbol definition in current scope`.

### 5.3. Định danh có Tiền tố & Kiểm tra Export

- Trong `names/context.vri`:
  - Lưu trữ danh sách exported symbols của từng canonical module: `import_module_register_exports(canonical_mod, exported_syms)`.
  - Cung cấp hàm tra cứu `import_module_is_exported(canonical_mod, symbol_name)`.
- Trong `names/walk_expr.vri` và `typecheck/walk_method.vri`:
  - Khi gặp `recv.member(...)`:
    - Kiểm tra nếu `recv` là `SymbolKind.Module`:
      - Lấy canonical module `mod_name = resolve_module_alias(recv.name)`.
      - Kiểm tra `import_module_is_exported(mod_name, member)`. Nếu không được export:
        - Báo lỗi `E2113: imported symbol not exported: '<member>' from '<mod_name>'`.
      - Tra cứu hàm `mod_name.member` qua `pass6_find_func_by_canonical_identity`.
      - Đánh dấu `node.builtin_id = 203`, `node.name2 = mod_name + "." + member`.

### 5.4. Chuẩn hóa Hạ tầng Lowering

- Trong `ast_to_mir/calls.vri`:
  - Khi `callee_kind == 203`, kiểm tra `is_module_call`:
    - Tra cứu `mod_name = resolve_module_alias(recv.name)`.
    - Nếu `resolved_name` có tiền tố `mod_name + "."`:
      - Đặt `is_module_call = true`.
      - Khi tạo `call_expr`, KHÔNG thêm `recv` vào danh sách đối số.

### 5.5. Quy tắc Single-Form Dependency (`E2115`)

- Trong `include_expander.vri` và `import_expander.vri`:
  - Duy trì hai bảng theo dõi phụ thuộc của file gốc consumer:
    - `g_consumer_included_targets`: danh sách các canonical Module ID được `include`.
    - `g_consumer_imported_targets`: danh sách các canonical Module ID được `import`.
  - Nếu một target xuất hiện trong cả hai danh sách:
    - Báo lỗi sớm `E2115: conflicting dependency: cannot both include and import canonical module '<mod>'`.

### 5.6. Từ chối Include Alias (`E2101`)

- Trong `include_expander.vri:487`:
  - Đổi nhánh xử lý `as` thành: `g_inc_parsed_err = 2101; g_inc_parsed_err_msg = "include alias 'as' is not supported; include does not create a namespace"`.
  - Loại bỏ hoàn toàn fixture tương thích `test_multi_include_alias_compat_positive.vri` và thay bằng negative test.

## 6. Design Decisions

### Decision 1: Sử dụng cấu trúc `module M` ... `module root` để cách ly mã nguồn provider
- **Decision**: Khi mở rộng whole-module import, preprocessor tự động bao bọc mã nguồn provider bằng `module M` và kết thúc bằng `module root`.
- **Rationale**: Tận dụng triệt để hạ tầng đa module có sẵn của compiler mà không cần thay đổi định dạng token/AST parser hoặc tạo ra cơ chế biểu diễn AST thứ hai. Mọi hàm của provider tự động nhận canonical name `M.func`, biến mất khỏi unqualified scope, và có thể được liên kết an toàn ở backend.
- **Alternatives considered**: Thêm AST node `NamespaceBlock`. Bị loại bỏ vì đòi hỏi sửa đổi lớn trên toàn bộ 10 semantic passes và lowering pipeline.

### Decision 2: Lưu bảng ánh xạ Module Alias ở tầng semantic context
- **Decision**: Tạo bảng toàn cục `g_module_aliases` trong semantic context để ánh xạ tên alias cục bộ (ví dụ `provider`) về canonical module name (ví dụ `a`).
- **Rationale**: Cho phép `walk_method.vri` và lowering dễ dàng chuyển đổi `provider.foo()` thành `a.foo()` mà không làm mất thông tin định danh gốc hay can thiệp vào cách đặt tên symbol ở backend.

### Decision 3: Fail-closed export validation tại điểm gọi qualified access
- **Decision**: Khi consumer gọi `M.func()`, compiler kiểm tra xem `func` có nằm trong danh sách export của `M` hay không. Nếu không, từ chối với lỗi `E2113`.
- **Rationale**: Bảo đảm tính đóng gói (encapsulation) của module. Các hàm trợ giúp nội bộ của provider không thể bị consumer gọi lén lút.

## 7. Implementation Plan

### Phase 1 — Diagnostic & Boundary Errors (`E2101`, `E2115`, `E2004`)
- Cập nhật `compiler/src/diagnostic/error_codes.vri` và `msg_frontend.vri` cho mã lỗi `E2115`.
- Cập nhật `include_expander.vri` để từ chối dứt điểm `include ... as ...` bằng `E2101`.
- Thêm kiểm tra Single-Form Dependency trong `include_expander.vri` và `import_expander.vri` phát sinh `E2115`.
- Cập nhật `symbols/context.vri` (`pass2_register`) để phát hiện và báo lỗi `E2004` khi có hai định nghĩa hàm trùng tên trong cùng scope.

### Phase 2 — Whole-Module Import Preprocessing & Scoped Expansion
- Cập nhật `import_expander.vri` để khi `g_imp_sym_count == 0`:
  - Thu thập danh sách export của provider.
  - Bao bọc nội dung bằng `module <canonical_mod>` ... `module root`.
  - Đăng ký alias và exports vào bảng quản lý của compiler.

### Phase 3 — Semantic Resolution & Qualified Call Lowering
- Cập nhật `sem_pass1_modules.vri` để đăng ký `SymbolKind.Module` cho namespace và alias.
- Cập nhật `walk_method.vri` để hỗ trợ tra cứu module alias, kiểm tra export (`E2113`), và giải nghĩa `node.builtin_id = 203`.
- Cập nhật `ast_to_mir/calls.vri` để nhận diện module calls qua alias và hạ cấp chính xác.

### Phase 4 — Test Fixtures & Coverage
- Cập nhật/tạo các test cases trong `tests/modules/`:
  - `test_whole_module_import_positive.vri`: `import a; a.a_value()`.
  - `test_whole_module_import_alias_positive.vri`: `import a as provider; provider.a_value()`.
  - `test_whole_module_import_unqualified_rejected.vri`: gọi unqualified hàm bị từ chối với `E2002`.
  - `test_whole_module_import_private_rejected.vri`: gọi private member bị từ chối với `E2113`.
  - `test_whole_module_import_collision_positive.vri`: hai provider cùng tên hàm `calc`, gọi qua `m1.calc()` và `m2.calc()`.
  - `test_mixed_include_import_rejected.vri`: vừa include vừa import cùng target bị từ chối với `E2115`.
  - `test_include_duplicate_decl_rejected.vri`: hai include fragments trùng hàm bị từ chối với `E2004`.
  - Cập nhật `test_multi_include_alias_compat_positive.vri` thành rejection test `E2101`.

### Phase 5 — Bootstrap & Regression Verification
- Chạy `python3 tools/bump_virc_version.py --bump-internal VIRC-ISS-0065`.
- Biên dịch 3 thế hệ bootstrap `bin/virc.stage2` == `bin/virc.stage3` (`cmp` == 0).
- Chạy toàn bộ test suites `./run_tests.sh min` đạt 100% PASS.
- Viết báo cáo nghiệm thu `VIRC-RPT-0063`.

## 8. Compatibility

- **Source compatibility**: Các mã nguồn chuẩn tuân thủ `VIR-SPC-0021` sẽ hoạt động trơn tru. Bất kỳ mã nguồn nào từng dựa vào include alias hoặc gọi unqualified các hàm từ whole-module import sẽ nhận được lỗi chẩn đoán chính xác hướng dẫn sửa đổi.
- **Spec compatibility**: Đưa trình biên dịch đạt sự tuân thủ 100% với `VIR-SPC-0021` v1.0.0.

## 9. Migration

- Mã nguồn dùng `include m as a` phải đổi thành `import m as a` (nếu cần namespace) hoặc `include m` (nếu là fragment composition).
- Mã nguồn dùng `import m` rồi gọi hàm không định danh `f()` phải đổi thành `m.f()` hoặc chuyển sang selective import `import f from m`.

## 10. Validation Plan

- Kiểm thử đơn vị và tích hợp qua ma trận fixtures mới trong `tests/modules/`.
- Kiểm thử Group 3 (Module system) trong `run_tests.sh`.
- Kiểm thử CLI contract suite và Module Resolver suite.
- Kiểm thử full regression `./run_tests.sh min`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lệch toạ độ dòng (source marker) khi chèn `module <mod>` | Thấp | Thấp | Chèn `# @vir_source` ngay sau dòng `module <mod>` để thiết lập lại tọa độ chính xác của provider |
| Module lồng nhau (nested include/import) bên trong provider | Trung bình | Trung bình | Khôi phục `module <mod>` sau khi hoàn tất các include/import con |
| Xung đột với các test hiện có dựa vào include alias | Thấp | Thấp | Đã kiểm tra: chỉ có duy nhất 1 test compat trong repository, sẽ được chuyển đổi thành rejection test |

## 12. Rollback Strategy

Khôi phục các files đã sửa đổi từ git commit trước đó (`git checkout HEAD -- compiler/`).

## 13. Exit Criteria

- [x] `include M as A` bị từ chối với diagnostic `E2101`.
- [x] `include` và `import` cùng target trong một consumer bị từ chối với `E2115`.
- [x] Trùng lặp khai báo giữa các included fragments báo lỗi `E2004`.
- [x] `import M` và `import M as A` bind namespace tương ứng, không đưa exported names vào unqualified scope.
- [x] Gọi hàm qua qualified namespace (`M.func()` hoặc `A.func()`) thành công.
- [x] Gọi hàm private trong imported module bị từ chối với `E2113`.
- [x] Hai module cùng export một tên hàm ngắn hoạt động đồng thời qua namespace riêng mà không xung đột.
- [x] Self-hosting bootstrap đạt fixed point (`stage 2 == stage 3`).
- [x] Toàn bộ `./run_tests.sh min` đạt 100% PASS.
- [x] Hoàn thành báo cáo nghiệm thu `VIRC-RPT-0063`.

## 14. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0065_include_text_splicing_does_not_provide_uniform_collision_free_dot_style_module_n.md`
- `papers/VIR/specs/VIR-SPC-0021_include_and_whole_module_import_dependency_contract.md`
- `papers/VIRC/issues/VIRC-ISS-0044_multi_include_directives_fail_instead_of_loading_every_listed_module.md`
- `papers/VIRC/plans/VIRC-PLN-0044_support_multi_include_directives_in_source_preprocessor.md`
- `papers/VIRC/reports/VIRC-RPT-0061_support_multi_include_directives_in_source_preprocessor.md`

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created initial implementation plan for VIRC-ISS-0065 |
| 2026-10-11 | Linked VIRC-RPT-0063 |
| 2026-10-11 | Audit remediation completed: extended whole-module qualification and export enforcement to constants, enums, and entities, resolved parser E1001 for qualified entity construction, added comprehensive regression tests; marked COMPLETED |
