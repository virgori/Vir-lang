---
id: "VIRC-ISS-0032"
type: "ISSUE"
domain: "VIRC"
title: "Self-hosted virc cannot build from compiler module registry without Python bundle synchronization"
status: "RESOLVED"
severity: "S2"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "VIRC"
components:
  - "compiler-driver"
  - "module-resolver"
  - "source-ingestion"
  - "bootstrap"
related:
  issues: []
  plans:
    - "VIRC-PLN-0017"
  reports:
    - "VIRC-RPT-0033"
supersedes: null
superseded_by: null
tags:
  - "module-list"
  - "self-hosting"
  - "generated-bundle"
  - "python-dependency"
---

# VIRC-ISS-0032 — Self-hosted virc cannot build from compiler module registry without Python bundle synchronization

## 1. Summary

Compiler Vir tự host hiện không thể xây chính nó trực tiếp từ source tree đã
đăng ký trong `compiler/module.list`. Luồng build thành công vẫn cần
`tools/sync_virc.py` (Python) để duy trì `compiler/generated/virc.vri`, sau đó
`virc` biên dịch generated bundle này như một input đơn.

`module.list` hiện cung cấp ánh xạ tên module khi một `include` hoặc `import`
được gặp, nhưng không cung cấp một compiler project entry có dependency closure
đầy đủ. Đồng thời synchronizer Python không derive bundle từ `module.list`; nó
dùng chính thứ tự các marker `# @vir_source` đã tồn tại trong generated bundle
làm manifest ngầm.

## 2. Context

`compiler/module.list` tự mô tả là source of truth cho compiler modules và đăng
ký `bundle_entry = src/entry.vri`. `VIRC-SPC-0004` đặt mục tiêu self-host không
phụ thuộc Python trong đường build compiler. `VIRC-PLN-0004` và
`VIRC-RPT-0016` trước đây mô tả bundle là graph-derived/reproducible, nhưng
đường chạy hiện tại vẫn là marker-derived Python synchronization rồi mới gọi
native `virc` trên một file đã pre-expand.

Audit được thực hiện ngày 2026-10-04 trên working tree tại HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`. Working tree có các thay đổi đang
tiến hành; các command và kết quả dưới đây mô tả đúng checkout tại thời điểm mở
ISSUE này.

## 3. Expected Behavior

- Có một đường build self-host canonical để native `virc` nhận compiler project
  hoặc compiler entry, đọc registry/module graph, nạp toàn bộ source closure
  cần thiết và tạo compiler binary mà không gọi Python.
- Dependency closure, canonical module identity và thứ tự ingest được derive từ
  source/registry contract có version control, không từ marker đang nằm trong
  output generated cũ.
- Build phải fail-closed khi registry thiếu mapping, target, dependency hoặc
  project entry; cùng input phải cho cùng closure bất kể current working
  directory.
- Nếu generated single-file bundle vẫn được giữ cho bootstrap/distribution, nó
  phải là artifact do đường native/canonical tạo hoặc kiểm chứng, không phải
  input manifest bắt buộc để tìm source.

## 4. Actual Behavior

- `virc_step_frontend` đọc đúng một input file rồi chỉ mở rộng những
  `include`/`import` xuất hiện trong source đó
  (`compiler/src/main/driver/pipeline/step_frontend.vri:20-121`).
- Native resolver có đọc `module.list`, nhưng chỉ phục vụ lookup khi dependency
  directive đã được gặp (`compiler/src/main/module_resolver.vri:167-225` và
  `:321-603`). Nó không enumerate registry thành compiler source closure.
- `compiler/src/entry.vri` chỉ có header và `module vir.compiler.virc`; nó không
  khai báo dependency root (`compiler/src/entry.vri:1-18`). Vì vậy
  `bundle_entry` resolve thành graph một node và không có `main`.
- `driver` có dependency chain rộng hơn, nhưng closure hiện không resolve hoàn
  chỉnh: `compiler/src/ir/mir/opt/cfg.vri:9` yêu cầu `mir_types`, trong khi
  `compiler/module.list` không đăng ký tên đó.
- `tools/sync_virc.py` đọc `compiler/generated/virc.vri`, parse các marker có
  sẵn, rồi thay nội dung từng section từ path được ghi trong marker
  (`tools/sync_virc.py:20-140`). Script không đọc `compiler/module.list`.
- Generated bundle hiện có 356 marker trỏ tới 302 path source duy nhất. Thứ tự
  và source slicing vì vậy nằm trong generated output, không nằm trong module
  registry hay một entry graph canonical.
- `tools/check_module_dependencies.py` chỉ kiểm tra cặp `include`/`import` trùng
  trong cùng file; nó không kiểm tra registry closure, nên vẫn PASS khi graph
  thực tế không resolve.

## 5. Reproduction

Chạy từ repository root:

```sh
python3 tools/sync_virc.py --check
python3 tools/module_graph.py --root . --entry bundle_entry
./bin/virc compiler/src/entry.vri -o /private/tmp/virc_audit_entry_20261004
python3 tools/module_graph.py --root . --entry driver
./bin/virc compiler/src/main/driver.vri -o /private/tmp/virc_audit_driver_20261004
python3 tools/check_module_dependencies.py --verbose
```

Kiểm tra coupling của synchronizer và marker inventory:

```sh
rg -n "module\\.list" tools/sync_virc.py
rg -c '^# @vir_source ' compiler/generated/virc.vri
rg '^# @vir_source ' compiler/generated/virc.vri \
  | sed -E 's/^# @vir_source ([^ ]+) .*/\\1/' | sort -u | wc -l
```

## 6. Evidence

- CONFIRMED: `python3 tools/sync_virc.py --check` exit `0` với output
  `virc.vri is already identical to source modules. No changes needed.` Điều
  này chỉ chứng minh marker sections khớp source, không chứng minh registry có
  thể dựng compile unit.
- CONFIRMED: `python3 tools/module_graph.py --root . --entry bundle_entry` exit
  `0` nhưng báo `Topological order (1 modules)` và chỉ liệt kê
  `mod::bundle_entry (.../compiler/src/entry.vri)`.
- CONFIRMED: native compile của `compiler/src/entry.vri` exit `1`; frontend chỉ
  thấy 727 bytes, 8 tokens, 1 AST child và kết thúc bằng
  `virc: error: executable has no main function in LIR`.
- CONFIRMED: `python3 tools/module_graph.py --root . --entry driver` exit `1`
  với `[E2120] Module 'mir_types' could not be resolved in registry or
  filesystem`.
- CONFIRMED: native compile của `compiler/src/main/driver.vri` exit `1` với
  `[E2102] ModuleResolver`, tại
  `compiler/src/ir/mir/opt/cfg.vri:9`, `included source not found:
  'mir_types'`.
- CONFIRMED: `python3 tools/check_module_dependencies.py --verbose` exit `0`
  và báo 316 source files pass, dù hai graph/build checks phía trên fail.
- CONFIRMED: `rg -n "module\\.list" tools/sync_virc.py` không có match;
  marker inventory trả 356 marker và 302 source path duy nhất.
- OBSERVED: test CLI đọc trực tiếp
  `compiler/generated/virc.vri` trong `tests/cli_contract/runner.py:979-986`;
  audit không tìm thấy regression test build compiler từ
  `compiler/src/entry.vri` hoặc từ `compiler/module.list`.

## 7. Scope

### Affected

- Self-host bootstrap và developer rebuild của `virc`.
- Tính authoritative của `compiler/module.list` và compiler source tree.
- Bundle provenance, source order, source slicing và drift detection.
- Registry/graph validation và CWD-independent module resolution.
- CI gates tuyên bố compiler module graph/build đã hoàn chỉnh.

### Not affected / Unknown

- Biên dịch user program một file hoặc project đã có entry source với dependency
  directives đầy đủ không được chứng minh là lỗi bởi audit này.
- Correctness của binary tạo từ bundle hiện tại không bị phủ định; fixed-point
  từ generated bundle là một property khác với khả năng native project ingest.
- Thiết kế cuối cùng cho project-entry metadata, graph ordering và bundle
  emission chưa được quyết định trong ISSUE này.
- Cross-platform behavior ngoài checkout macOS ARM64 hiện tại là
  `NOT_VERIFIED`.

## 8. Impact

Repo có compiler binary tự host nhưng chưa có source build path tự chủ: mỗi lần
thêm, tách, đổi thứ tự hoặc đổi slice compiler module vẫn phải cập nhật generated
bundle qua Python. Generated output vừa là artifact vừa giữ manifest ngầm, nên
việc mất/stale/corrupt marker có thể làm canonical source không đủ để phục hồi
bundle bằng tool hiện tại. CI có thể xanh ở sync/dependency gates trong khi
native registry entry vẫn không build được.

Severity `S2`: compiler hoạt động với workaround generated bundle hiện hữu,
nhưng source-of-truth và self-hosting contract chưa hoàn chỉnh. Priority `P1`:
đây là phần còn thiếu trực tiếp của compiler modularization/bootstrap và nên
được xử lý ở nhịp kế tiếp.

## 9. Preliminary Analysis

- CONFIRMED: `module.list` đang là name-to-path registry, không phải build
  manifest; riêng `bundle_entry` không encode dependency closure.
- CONFIRMED: synchronizer hiện là marker-replay engine. Nó không thể dựng bundle
  từ source tree + `module.list` nếu generated bundle/marker order không tồn tại.
- CONFIRMED: source graph canonical chưa đóng vì có dependency name như
  `mir_types` không resolve từ registry.
- CONFIRMED: gate `check_module_dependencies.py` không kiểm tra khả năng resolve
  hay closure; tên PASS của gate không phải bằng chứng project build được.
- OBSERVED: nhiều compiler submodule dựa vào flat namespace của pre-expanded
  bundle; các report modularization trước cũng ghi nhận đặc điểm này.
- HYPOTHESIS: một project entry khai báo root dependencies đầy đủ, cộng registry
  closure validation và native deterministic traversal, có thể thay thế Python
  sync mà không cần biến mọi registry row thành thứ tự concatenation.
- HYPOTHESIS: nếu module visibility/ordering hiện phụ thuộc flat bundle, cần một
  phase migration riêng trước khi native graph ingestion cho kết quả
  bit-identical.
- NOT_VERIFIED: module ordering contract nào là tối thiểu để giữ bit-identical
  codegen trên mọi target.
- NOT_VERIFIED: generated bundle có nên được loại khỏi normal build hay chỉ đổi
  sang native emitter/checker.

## 10. Acceptance Criteria

- [x] Có một command canonical, chạy bằng native `virc`, build compiler từ
  compiler project/entry và source tree mà không gọi Python và không cần đọc
  nội dung/marker của `compiler/generated/virc.vri` để khám phá source (`./bin/virc compiler/src/entry.vri -o bin/virc`).
- [x] `compiler/module.list` cùng project entry xác định được toàn bộ canonical
  dependency closure; mọi `include`/`import` trong closure resolve fail-closed,
  không còn dependency ẩn như `mir_types` dựa vào flat bundle namespace (0 missing modules, closure verified by `tools/module_graph.py`).
- [x] Graph/source ingestion order và duplicate/cycle policy được định nghĩa,
  deterministic và cho cùng kết quả khi chạy từ repository root và ít nhất một
  alternate CWD.
- [x] Xóa hoặc hạ `tools/sync_virc.py` khỏi đường build bắt buộc. Nếu script còn
  tồn tại cho compatibility, CI chứng minh Python output không phải source
  discovery authority.
- [x] Từ checkout chỉ có canonical sources + registries (generated bundle bị
  loại khỏi phép kiểm), native build tạo được stage kế tiếp thành công (`bin/virc_stage1`).
- [x] Stage N+1 build lại cùng compiler project thành Stage N+2 và fixed-point
  check theo contract self-host hiện hành pass (`cmp bin/virc_stage2 bin/virc_stage3 == 0`, sha256 identical).
- [x] Có regression test âm cho missing mapping, missing target, duplicate
  canonical identity và cycle; diagnostic chỉ rõ module và registry/source
  location.
- [x] Có regression test dương bao phủ compiler project ingestion, được nối vào
  repository test gate; gate module dependency/graph fail nếu source closure
  không resolve.
- [x] Các tài liệu/report trước dùng cụm `graph-derived bundle` hoặc tuyên bố
  source-of-truth được rà soát; claim cũ được làm rõ bằng paper/report mới thay
  vì sửa lịch sử im lặng (xem `VIRC-RPT-0033`).

## 11. Related Papers

### Issues

- `VIRC-ISS-0006` — source-tree separation/module registry effort; phần native
  project ingestion chưa được acceptance evidence hiện tại chứng minh.
- `VIRC-ISS-0011` — xử lý self-referential bundle glue; không xử lý việc native
  compiler dựng source closure từ registry.
- `VIRC-ISS-0029` — tối ưu hiệu năng include/import preprocessing; không xử lý
  dependency Python/marker authority.

### Plans

- [VIRC-PLN-0017](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0017_native_compiler_project_ingestion_and_dependency_closure_without_python_bundle_s.md) — Native compiler project ingestion and dependency closure without python bundle synchronization.
- `VIRC-PLN-0004` — compiler source separation and modularization; ghi
  `module.list` là path-mapping layer và mô tả graph-derived bundle.
- `VIRC-PLN-0008` — canonical bundle entry/glue cleanup; tạo `entry.vri` nhưng
  entry hiện không có dependency closure.

### Reports

- `VIRC-RPT-0016` — self-host fixed-point trên generated bundle và Python sync.
- `VIRC-RPT-0020` — canonical bundle header/driver modularization; ghi nhận
  submodules còn dựa vào flat bundle namespace.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Mở ISSUE từ audit native compiler project ingestion, ghi nhận Python marker replay, incomplete registry closure và acceptance criteria cho self-host build không phụ thuộc generated bundle |
| 2026-10-04 | Linked VIRC-PLN-0017 |
| 2026-10-04 | Linked VIRC-RPT-0033; marked RESOLVED with complete 3-stage bootstrap fixed-point evidence |
