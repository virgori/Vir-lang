---
id: "VIRC-ISS-0046"
type: "ISSUE"
domain: "VIRC"
title: "Canonical umbrella import from module is rejected by the source preprocessor"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "compiler"
  - "frontend"
components:
  - "source-preprocessing"
  - "module-resolution"
  - "symbol-visibility"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIRC-ISS-0008"
    - "VIRC-ISS-0045"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "import"
  - "umbrella-import"
  - "export"
  - "module-system"
  - "spec-conformance"
---

# VIRC-ISS-0046 — Canonical umbrella import from module is rejected by the source preprocessor

## 1. Summary

Canonical umbrella spelling `import from module`, được active module SPEC mô tả
là nhập toàn bộ exported symbols, bị native source preprocessor hiểu sai và
resolve module tên `from`. Minimal fixture thất bại E2112 dù provider được đăng
ký, tồn tại và `import module` compatibility control compile/run thành công.

## 2. Context

`VIR-SPC-0014:51-60` và `VIR-SPC-0018:459-470` dùng `import from net.http` như
Vir v2.0 form. `VIR-SPC-0006` ghi chưa có end-to-end evidence và không dùng nó
làm canonical example cho đến khi contract được thống nhất.

Active import expander hỗ trợ selective `import symbols from module`, legacy
`from module import symbols`, `import * from module` và compatibility
`import module`. Nó không có branch nhận token `from` ngay sau `import` như
umbrella marker.

## 3. Expected Behavior

- `import from M` resolve `M` qua canonical registry và đưa toàn bộ, chỉ những,
  declarations được `export` vào local scope.
- Provider không cần `include` trước; repeat/diamond imports load canonical
  module nhiều nhất một lần.
- Module có zero exports tạo empty public surface hoặc diagnostic được SPEC chốt,
  không fail-open private symbols; behavior phải hội tụ với `VIRC-ISS-0008`.
- Missing module, malformed directive và visibility failure có diagnostic tại
  `M`, không báo module tên `from`.
- Namespace alias là scope của `VIRC-ISS-0045`, không được ngầm trộn vào syntax
  umbrella cơ bản.

## 4. Actual Behavior

- `import from a` exit 1 với E2112 `imported module not found` tại line 1.
- Source preprocessor nhận `from` như first identifier của form `import mod` và
  cố resolve nó như module.
- Control `import a` splice provider body, compile thành công và executable exit
  42, nên registry/path/provider không phải nguyên nhân.

## 5. Reproduction

Dùng `module.list` và exported `a_value` provider từ `VIRC-ISS-0044`:

```vir
import from a

func main:
    out a_value() + 2
end.
```

```sh
./bin/virc /private/tmp/vir_module_feature_audit/umbrella_import.vri \
  -o /private/tmp/vir_module_feature_audit/umbrella_import.out --color=never -q
```

Control: thay directive bằng `import a` rồi compile/run cùng entry body.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0014:53-60` và `VIR-SPC-0018:461-470` công bố
  `import from module`; `VIR-SPC-0006:280-300` ghi active implementation gap.
- CONFIRMED: `compiler/src/main/import_expander.vri:559-620` đọc first identifier
  sau `import` như module hoặc selective symbol; không special-case umbrella
  `from`.
- CONFIRMED: whole-module builder tại `import_expander.vri:736-746` splice raw
  body khi symbol count bằng zero; export-only umbrella semantics chưa được tách.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `db2a418c7952fffd66344ae9d29c28f5835ff25e08e634ea5915b911c00c7e69`:
  umbrella fixture exit 1/E2112; `import a` control compile 0 và chạy exit 42.

## 7. Scope

### Affected

- import text parser/expander, module resolution và whole-export visibility;
- export enforcement, canonical dedup/cycle handling và source markers;
- diagnostics, IDE import facts và module conformance tests.

### Not affected / Unknown

- Selective `import X from M` và its symbol alias syntax không được đổi.
- Whole-module namespace aliases thuộc `VIRC-ISS-0045`.
- Legacy `from M import X`, `import * from M` và `import M` cần compatibility
  regression tests nhưng không phải canonical syntax do ISSUE này định nghĩa.
- NOT_VERIFIED: full declaration-kind set mà current export extractor có thể
  materialize; acceptance phải cover functions/types/constants/variables.

## 8. Impact

Một syntax được gọi là canonical trong active SPEC luôn resolve sai, khiến người
dùng buộc dùng compatibility whole-body forms có visibility semantics khác.
Điều đó làm export boundary không đáng tin và gây divergence giữa parser,
preprocessor, IDE và tài liệu.

Severity S2 vì canonical feature không hoạt động nhưng `import M`/
`import * from M` là workaround. Priority P1 vì fix phải phối hợp export
fail-closed và module surface trước Vir 3.0 freeze.

## 9. Preliminary Analysis

- CONFIRMED: active text parser không nhận grammar `import from M` và resolve
  literal `from` như module.
- CONFIRMED: provider registry và unaliased compatibility whole import hoạt động.
- CONFIRMED: `VIRC-ISS-0008` vẫn sở hữu no-export fail-open; umbrella import
  implementation không được đóng issue visibility đó nếu chưa pass criteria.
- HYPOTHESIS: một explicit whole-export mode có thể reuse canonical resolver và
  export inventory nhưng không được reuse raw-body `import M` semantics mù quáng.
- NOT_VERIFIED: representation và diagnostic codes cuối cùng; thuộc PLAN.

## 10. Acceptance Criteria

- [ ] `import from M` compile/run và đưa mọi explicitly exported supported
  declaration vào scope mà không cần preceding include.
- [ ] Private, missing và zero-export cases fail-closed theo contract thống nhất
  với `VIRC-ISS-0008`.
- [ ] Functions, constants, variables, entities/enums và aliases có positive/
  negative focused fixtures.
- [ ] Repeat, diamond và mixed compatible spellings hội tụ theo canonical Module
  ID; cycle diagnostics và source provenance giữ đúng.
- [ ] Unknown module/malformed umbrella syntax có stable classic/JSON diagnostic
  tại module spelling, không resolve literal `from`.
- [ ] Existing selective imports và documented compatibility forms không
  regression; namespace alias behavior được giữ tách ở `VIRC-ISS-0045`.
- [ ] IDE facts, navigation and completion reflect export-only imported symbols.
- [ ] Registered tests, supported targets và stage 2 == stage 3 bootstrap được
  ghi trong accepted REPORT trước khi đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit và umbrella import gap.
- `VIRC-ISS-0008` — selective imports fail-open khi provider không có export.
- `VIRC-ISS-0045` — include/whole-module namespace aliases.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from native umbrella-import failure and working whole-import control |
| 2026-10-06 | Linked VIRC-ISS-0045 |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Linked VIRC-ISS-0008 |
