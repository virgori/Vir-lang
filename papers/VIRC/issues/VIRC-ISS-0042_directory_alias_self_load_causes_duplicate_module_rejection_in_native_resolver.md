---
id: "VIRC-ISS-0042"
type: "ISSUE"
domain: "VIRC"
title: "Directory alias self-load causes duplicate module rejection in native resolver"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
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
    - "VIR-ISS-0006"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "regression"
  - "module-list"
  - "directory-alias"
  - "e2121"
  - "coverage-gap"
---

# VIRC-ISS-0042 — Directory alias self-load causes duplicate module rejection in native resolver

## 1. Summary

Native `virc 4.2.1` từ chối năm positive module fixtures trước tokenization với
E2121 `duplicate module ... 'flat_shared'`. Registry
`tests/modules/module.list` chỉ khai báo `flat_shared` một lần.

Hồi quy xuất hiện khi directory alias `mod = .` trỏ về chính thư mục chứa
registry. Loader hiện tự tìm `<alias-directory>/module.list`, đọc lại cùng file
như nested registry và chèn `flat_shared`; khi vòng đọc top-level tiến tới dòng
`flat_shared = dep_shared.vri`, nó coi entry hợp lệ ban đầu là duplicate.

## 2. Context

Audit được chạy ngày 2026-10-06 tại Git HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`, với dirty worktree được giữ nguyên.
`compiler/src/main/module_resolver.vri` đã bị sửa trước audit, nên ISSUE ghi nhận
trạng thái working tree hiện tại chứ không gán regression cho một commit.

Registry tái hiện:

```text
root = .
mod = .
flat_shared = dep_shared.vri
dep_left_inc = dep_left_inc.vri
dep_right_inc = dep_right_inc.vri
```

Directory alias `mod` cho phép các identity như `mod.dep_shared`; các exact file
entries đồng thời kiểm tra flat identities. Python resolver/graph tool xử lý hai
dạng này thành công, còn native resolver thất bại ngay khi load registry.

## 3. Expected Behavior

- Mỗi physical registry chỉ được parse một lần trong một load transaction, kể
  cả khi directory alias trỏ về thư mục chứa chính registry đó.
- `mod = .` không được biến top-level `module.list` thành nested registry của
  chính nó.
- Một duplicate key thực sự trong cùng logical registry vẫn phải bị từ chối
  bằng E2121 với vị trí hai declaration hữu ích.
- Directory alias và compatible spellings trỏ tới cùng source unit phải hội tụ
  vào dedup/cycle identity phù hợp hoặc bị từ chối bằng diagnostic có chủ đích;
  chúng không được sinh duplicate giả trong lúc load.
- Positive fixtures phải compile/run bằng native compiler, không chỉ resolve
  bằng Python graph helper.

## 4. Actual Behavior

Các lệnh sau đều exit 1 trước lexer/parser:

```sh
./bin/virc tests/modules/test_flat_include.vri -o /tmp/test_flat_include.out -q
./bin/virc tests/modules/test_include_only.vri -o /tmp/test_include_only.out -q
./bin/virc tests/modules/test_import_only.vri -o /tmp/test_import_only.out -q
./bin/virc tests/modules/test_diamond_dedup.vri -o /tmp/test_diamond_dedup.out -q
./bin/virc tests/modules/test_flat_diamond.vri -o /tmp/test_flat_diamond.out -q
```

Mỗi command báo cùng lỗi:

```text
[E2121] ModuleResolver
File: tests/modules/module.list
Line: 3
duplicate module in stdlib registry: 'flat_shared'
```

Trong khi đó các đường kiểm tra sau pass:

```sh
python3 -m unittest -v tests/module/test_module_resolver.py
python3 tools/module_graph.py --root tests/modules --entry flat_shared
python3 tools/module_graph.py --root tests/modules --entry mod.dep_shared
./run_tests.sh 3
```

## 5. Reproduction

Tối thiểu cần một thư mục có `dep_shared.vri`, một consumer và registry:

```text
root = .
mod = .
flat_shared = dep_shared.vri
```

Consumer có thể dùng `include flat_shared` hoặc `include mod.dep_shared`. Chạy
native compiler từ repository root. Failure xảy ra trong registry load trước
khi dependency directive của consumer được xử lý.

Để xác nhận coverage gap, chạy `./run_tests.sh 3`: suite pass dù năm command
native phía trên cùng fail.

## 6. Evidence

- CONFIRMED: `tests/modules/module.list:3` chỉ có một declaration cho
  `flat_shared`.
- CONFIRMED: `module_resolver.vri:251-307` đăng ký `mod = .` như directory alias.
- CONFIRMED: `module_resolver.vri:308-425` mở
  `<directory-alias>/module.list` và thêm các entry chưa có vào cùng registry.
- CONFIRMED: với `mod = .`, nested path chuẩn hóa về chính
  `tests/modules/module.list`; implementation không có same-file guard trước
  khi đọc lại.
- CONFIRMED: nested read thêm `flat_shared` khi top-level cursor vẫn đang ở dòng
  2; sau đó top-level duplicate check tại `:254-268` gặp lại key ở dòng 3 và
  phát E2121.
- OBSERVED: cả năm positive fixtures fail cùng E2121 tại dòng 3.
- OBSERVED: Python resolver unit suite và graph resolution cho `flat_shared`
  cùng `mod.dep_shared` đều pass.
- OBSERVED: Group 3 pass và không compile năm positive fixtures này bằng
  `./bin/virc`.
- HYPOTHESIS: regression bắt nguồn từ block nested-`module.list` mới ở
  `module_resolver.vri:308-425`; vì file đang có thay đổi chưa commit, audit
  không xác định commit đầu tiên gây lỗi.
- NOT_VERIFIED: directory alias trỏ tới một thư mục con có registry khác có xử
  lý root, duplicate provenance, prefix collisions và recursion nhiều cấp đúng.

## 7. Scope

### Affected

- native project-registry loading;
- directory aliases whose target contains a `module.list`;
- flat and dotted module fixtures under `tests/modules/`;
- dedup/cycle identity formation after project registry load;
- Group 3 module regression coverage.

### Not affected / Unknown

- `stdlib/stdlib.vri` exact mappings are not the trigger despite diagnostic text
  saying "stdlib registry".
- Python `tools/module_graph.py` does not reproduce the failure.
- Compiler project ingestion using `compiler/module.list` passed in this audit;
  its aliases do not establish safety for the self-referential fixture shape.
- Include/import scaling work resolved by `VIRC-ISS-0029` is not reopened by
  this correctness regression.

## 8. Impact

Valid projects can become uncompilable solely by adding a directory alias that
points at their registry directory. Because failure occurs during global
registry load, even a consumer that only requests an unrelated exact file
mapping fails. The green Group 3 result creates a false release signal: graph
behavior is tested, but native compiler behavior for the checked-in positive
fixtures is not.

## 9. Preliminary Analysis

- CONFIRMED: the duplicate is synthetic; no second top-level `flat_shared`
  declaration exists.
- CONFIRMED: the same physical registry is read as both top-level and nested
  registry when alias value is `.`.
- CONFIRMED: failure precedes source tokenization and is independent of whether
  the consumer uses include or import.
- HYPOTHESIS: tracking normalized registry realpaths in the active load stack,
  with a deliberate policy for self-reference, will prevent the false duplicate
  without weakening real duplicate checks.
- HYPOTHESIS: nested registry semantics need a single shared implementation with
  explicit namespace prefixing and root handling rather than an inline partial
  parser.
- NOT_VERIFIED: the smallest safe patch and behavior for mutually recursive
  registries.

## 10. Acceptance Criteria

- [ ] A focused native regression test reproduces `mod = .` plus an exact file
  entry and fails before the fix.
- [ ] Native resolver does not parse the same normalized `module.list` twice in
  one registry load or otherwise handles self-reference without a false E2121.
- [ ] All five positive fixtures compile and execute with exit code 0.
- [ ] `flat_shared` and `mod.dep_shared` resolve to the intended physical source
  and converge under the documented canonical/dedup policy.
- [ ] Genuine duplicate key, missing target, malformed entry and prefix-collision
  negative tests continue to emit their expected diagnostics.
- [ ] Nested registry tests cover a distinct child registry, self-reference,
  multi-level recursion and a real cross-file duplicate with source provenance.
- [ ] Group 3 invokes the native positive fixtures so this regression cannot be
  hidden by Python-only resolver tests.
- [ ] `python3 -m unittest -v tests/module/test_module_resolver.py`, relevant
  graph checks, dependency checks and compiler project ingestion remain green.
- [ ] A REPORT records before/after commands, versions, fixture exits and
  diagnostic evidence before closure.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit that exposed this gap.
- `VIRC-ISS-0029` — resolved preprocessing scalability work; related pipeline,
  separate outcome.
- `VIRC-ISS-0032` — resolved native compiler project-ingestion work; its gates
  do not cover this self-referential registry shape.

### Plans

- None.

### Reports

- `VIRC-RPT-0032` — accepted preprocessing/scaling verification.
- `VIRC-RPT-0033` — accepted compiler project-ingestion verification.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened after native reproduction on five positive module fixtures |
| 2026-10-06 | Linked `VIR-ISS-0006`, documented the self-registry load path, and added native-suite closure gates |
