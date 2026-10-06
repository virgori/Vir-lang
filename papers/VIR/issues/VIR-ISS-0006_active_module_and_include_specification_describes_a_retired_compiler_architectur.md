---
id: "VIR-ISS-0006"
type: "ISSUE"
domain: "VIR"
title: "Active module and include specification describes a retired compiler architecture"
status: "RESOLVED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "language"
components:
  - "module-system"
  - "include"
  - "import"
  - "module-registry"
  - "specification"
related:
  issues:
    - "VIR-ISS-0007"
    - "VIR-ISS-0008"
    - "VIRC-ISS-0008"
    - "VIRC-ISS-0042"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0045"
    - "VIRC-ISS-0046"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "spec-drift"
  - "module-list"
  - "stdlib-registry"
  - "source-preprocessing"
---

# VIR-ISS-0006 — Active module and include specification describes a retired compiler architecture

## 1. Summary

`VIR-SPC-0006` phiên bản 1.0.0 mang trạng thái `ACTIVE` nhưng mô tả compiler C
đã bị thay thế: include được lex/parse riêng rồi splice AST qua
`lower_resolve_includes()`, bảng alias nằm trong `lower_ctx_t`, giới hạn include
là 64 và bộ test kết thúc ở kết quả `89/89 pass`.

Compiler đang hoạt động là self-hosted `virc 4.2.1`. Nó nạp
`stdlib/stdlib.vri` cùng `module.list`, phân giải module thành canonical identity
và đường dẫn vật lý, sau đó mở rộng `include`/`import` ở mức văn bản trước
lexer/parser. Vì SPEC cũ vừa sai kiến trúc vừa bỏ qua registry, alias thực thi,
export visibility và các đường tương thích, nó không còn là nguồn hướng dẫn an
toàn cho compiler, tooling hay người viết Vir.

## 2. Context

Audit được thực hiện ngày 2026-10-06 tại Git HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`, trên dirty worktree được giữ nguyên.
`compiler/src/main/module_resolver.vri` đã có thay đổi chưa commit trước audit;
ISSUE này không quy các thay đổi đó cho bất kỳ commit nào.

Các nguồn được đối chiếu gồm:

- `VIR-SPC-0006` v1.0.0 và các module section trong `VIR-SPC-0018`;
- frontend pipeline, include/import expander và module resolver đang chạy;
- `stdlib/stdlib.vri`, `compiler/module.list`, `tests/modules/module.list`;
- parser/semantic passes cho `module`, `include`, `import`, `get`, `export`;
- positive, negative, scaling và project-ingestion tests hiện có.

## 3. Expected Behavior

- Một SPEC `ACTIVE` phải mô tả hợp đồng ngôn ngữ độc lập với chi tiết và trạng
  thái triển khai của một compiler cụ thể.
- Module identity phải đến từ registry; đường dẫn vật lý không tự động trở thành
  public module identity.
- SPEC phải mô tả riêng vai trò của `stdlib/stdlib.vri` và project
  `module.list`, kể cả root, file mapping, directory alias và canonical dedup.
- `include`, selective import, umbrella/whole-module import, `export` và từng
  loại alias phải có semantics chuẩn nhất quán.
- Conformance evidence và test status thuộc ISSUE/REPORT triển khai, không nằm
  trong normative language SPEC.

## 4. Actual Behavior

- SPEC v1.0.0 tham chiếu `main.c`, `ir_lower.c`, `ir_lower.h`,
  `lower_resolve_includes()`, `lower_process_imports()` và `lower_ctx_t`; các
  đường/API này không tồn tại trong compiler hiện hành.
- SPEC nói include splice AST sau parser. Pipeline thật gọi include expansion,
  import expansion rồi include expansion lần nữa trước tokenization.
- SPEC không nhắc `stdlib/stdlib.vri`, `module.list`, canonical identity, source
  markers, cycle detection hay resolver precedence.
- SPEC minh họa cú pháp cũ `func ... then`, `return` và `export func`; compiler
  hiện hành từ chối các dạng này.
- Sáu tên test và claim `89/89 pass` trong SPEC không tồn tại trong test tree
  hiện tại.
- Parser nhận whole-module/include alias, nhưng text preprocessor hiện loại bỏ
  directive sau khi splice source và không tạo namespace alias thực thi.
  Selective import alias lại hoạt động vì expander đổi tên chunk được nhập.
- `VIRC-ISS-0008` đã theo dõi trường hợp selective import cho phép symbol từ
  provider không khai báo export. `VIRC-ISS-0042` theo dõi hồi quy registry được
  phát hiện trong audit này.

## 5. Reproduction

Kiểm tra các tham chiếu đã biến mất và pipeline hiện tại:

```sh
test ! -e core/src/main.c
test ! -e core/src/ir_lower.c
test ! -e core/include/ir_lower.h
nl -ba compiler/src/main/driver/pipeline/step_frontend.vri | sed -n '55,115p'
nl -ba compiler/src/main/include_expander.vri | sed -n '1035,1165p'
nl -ba compiler/src/main/module_resolver.vri | sed -n '12,180p'
```

Chạy các gate còn hiệu lực:

```sh
./run_tests.sh 3
python3 -m unittest -v tests/module/test_module_resolver.py
python3 tools/module_graph.py --root . --entry driver
python3 tools/module_graph.py --root . --entry bundle_entry
python3 tools/check_module_dependencies.py --verbose
python3 tests/perf_contract/test_include_scaling.py --virc ./bin/virc --max-modules 128
```

Minimal alias probes dùng provider có `export add_one` cho kết quả:

- `import add_one from "provider.vri" as plus_one` compile và executable trả
  exit code 42;
- `include "provider.vri" as p` rồi gọi `p.add_one(41)` thất bại E2001 tại
  `p`;
- `import provider as p` qua exact file mapping rồi gọi `p.add_one(41)` cũng
  thất bại E2001 tại `p`.

## 6. Evidence

- CONFIRMED: `step_frontend.vri:55-104` thực hiện include → import → include
  expansion trước tokenization.
- CONFIRMED: `include_expander.vri:225` gọi cơ chế hiện hành là text-level
  include splice; `:1093-1159` dùng canonical key, dedup, cycle stack và source
  markers.
- CONFIRMED: `module_resolver.vri:12-180` nạp stdlib registry rồi tìm project
  `module.list`; `:454-810` thực hiện project, stdlib và compatibility fallbacks.
- CONFIRMED: `path_util.vri:21-25` đặt giới hạn hiện hành ở 4096 module/include
  entries và 8192 preprocessing operations, không phải 64.
- CONFIRMED: parser ghi nhận alias cho import/include, nhưng
  `text_parse_include_name()` chỉ trả module/path; alias không đi vào source
  chunk được splice.
- OBSERVED: selective import alias probe hoạt động; hai namespace alias probes
  thất bại E2001.
- OBSERVED: Group 3, resolver unit tests, hai module graphs, dependency checker
  và include-scaling test đều pass trong audit.
- OBSERVED: năm positive fixtures dưới `tests/modules/` thất bại E2121 vì hồi
  quy riêng được ghi ở `VIRC-ISS-0042`; Group 3 không chạy các fixture đó.
- NOT_VERIFIED: `lazy include`/`lazy import`, multi-include trên một dòng và
  canonical `import from module` có executable semantics đúng như mô tả trong
  umbrella language specification.

## 7. Scope

### Affected

- `VIR-SPC-0006` và phần module liên quan trong các SPEC ngôn ngữ;
- contract của module identity, registry và dependency resolution;
- semantics của include, import, export và alias;
- English/Vietnamese/focused-spec parity cùng derived agent guidance.

### Not affected / Unknown

- ISSUE này không sửa compiler implementation.
- Trạng thái conformance, test coverage, diagnostics và bootstrap thuộc các
  VIRC ISSUE/PLAN/REPORT độc lập và không gate resolution tài liệu này.
- Thuật toán resolver regression cụ thể thuộc `VIRC-ISS-0042`.
- Export fail-open của selective import thuộc `VIRC-ISS-0008`.
- `share`, `port` và lazy type-only dependency cần audit riêng trước khi được
  tuyên bố là implemented.

## 8. Impact

Một SPEC `ACTIVE` sai kiến trúc có thể khiến contributor sửa các file/API không
tồn tại, tạo test cho phase đã nghỉ hưu, hoặc giả định alias/export hoạt động
trong khi compiler không bảo đảm. Sự thiếu vắng registry contract còn làm cùng
một file bị gọi bằng nhiều identity, phá dedup, cycle detection và khả năng tái
lập dependency graph.

## 9. Preliminary Analysis

- CONFIRMED: `VIR-SPC-0006` v1.0.0 là tài liệu migrated nguyên trạng từ kiến
  trúc C cũ và đã lỗi thời toàn diện.
- CONFIRMED: implementation hiện hành là source-preprocessing dựa trên registry,
  không phải AST splice callback.
- CONFIRMED: selective symbol alias và whole-module namespace alias đi qua hai
  cơ chế khác nhau; chỉ loại đầu có executable probe pass.
- OBSERVED: resolver/tooling tích cực xử lý nhiều hơn SPEC cũ, nhưng các gate
  không có cùng coverage.
- HYPOTHESIS: SPEC drift tồn tại vì migration gắn stable ID/status nhưng không
  tái thẩm định nội dung với compiler self-hosted.
- NOT_VERIFIED: mọi syntax trong `VIR-SPC-0018` đã có end-to-end implementation.

## 10. Acceptance Criteria

- [x] `VIR-SPC-0006` được major-rewrite thành v3.0.0, loại bỏ retired compiler
  APIs, implementation status, capacity constants và stale test claims.
- [x] SPEC mô tả vai trò khác nhau của active toolchain `stdlib.vri` và project
  `module.list`, canonical identity, registry discovery/root và resolution
  layers mà không ràng buộc vào pipeline của một compiler cụ thể.
- [x] Multi-include, include/whole-module namespace alias, selective import và
  umbrella `import from module` có một normative contract duy nhất.
- [x] Các module section trùng lặp trong `VIR-SPC-0014`, `VIR-SPC-0017` và
  `VIR-SPC-0018` được đồng bộ hoặc dẫn chiếu một nguồn normative duy nhất.
- [x] Standalone `get` được loại theo `VIR-ISS-0005`; deferred type-only module
  forms được loại theo `VIR-ISS-0007`; `get` vẫn là ordinary identifier.
- [x] Standard-library canonical IDs được reserve khỏi exact project collision
  theo `VIR-ISS-0008`; prefix-only relationships vẫn hợp lệ.
- [x] Derived Vir module guidance được đồng bộ với contract Vir 3.0.

VIRC-ISS-0042 và VIRC-ISS-0044 đến VIRC-ISS-0047 tiếp tục theo dõi compiler
conformance độc lập. Trạng thái của chúng không phải acceptance gate của VIR
documentation ISSUE này.

## 11. Related Papers

### Issues

- `VIR-ISS-0007` — loại `lazy include`/`lazy import` khỏi active module specs.
- `VIR-ISS-0008` — reserve exact stdlib Module IDs khỏi project registry mà
  không cấm namespace prefix relationships.
- `VIRC-ISS-0008` — selective import fail-open khi provider không có export list.
- `VIRC-ISS-0042` — directory alias tự nạp lại cùng `module.list` và gây E2121.
- `VIRC-ISS-0044` — multi-include một dòng thất bại trước parser.
- `VIRC-ISS-0045` — include/import namespace aliases không tạo executable
  namespace.
- `VIRC-ISS-0046` — canonical umbrella `import from module` bị resolve sai.

### Plans

- None.

### Reports

- `VIRC-RPT-0032` — accepted report cho streaming source preprocessing.
- `VIRC-RPT-0033` — accepted report cho native compiler project ingestion.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from an implementation-backed audit of `VIR-SPC-0006` v1.0.0 |
| 2026-10-06 | Linked `VIRC-ISS-0042` and recorded v2.0.0 spec rewrite plus remaining convergence gates |
| 2026-10-06 | Linked VIR-ISS-0007 |
| 2026-10-06 | Linked VIRC-ISS-0044 |
| 2026-10-06 | Linked VIRC-ISS-0045 |
| 2026-10-06 | Linked VIRC-ISS-0046 |
| 2026-10-06 | Split remaining conformance ownership across VIR-ISS-0005/0007 and VIRC-ISS-0044 through 0046 |
| 2026-10-06 | Linked VIRC-ISS-0008 |
| 2026-10-06 | Linked VIR-ISS-0008 and delegated the stdlib/project exact-collision contract |
| 2026-10-06 | Resolved the documentation scope with compiler-independent VIR-SPC-0006 v3.0.0 and synchronized focused/bilingual specs; VIRC implementation status remains unchanged |
