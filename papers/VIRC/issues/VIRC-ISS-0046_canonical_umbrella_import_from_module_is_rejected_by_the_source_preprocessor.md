---
id: "VIRC-ISS-0046"
type: "ISSUE"
domain: "VIRC"
title: "Canonical umbrella import from module is rejected by the source preprocessor"
status: "REJECTED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-10"
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
    - "VIR-ISS-0017"
    - "VIRC-ISS-0008"
    - "VIRC-ISS-0045"
    - "VIRC-ISS-0065"
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

ISSUE này ghi nhận rằng canonical umbrella spelling cũ `import from module` bị
native source preprocessor hiểu sai và resolve module tên `from`. Ngày
2026-10-10, language contract được sửa để chọn `import module` làm whole-module
form duy nhất và dành `from` cho selective import có danh sách symbol không
rỗng. Vì form được báo lỗi đã bị loại khỏi grammar thay vì được triển khai,
ISSUE bị `REJECTED`; bằng chứng tái hiện bên dưới được giữ làm lịch sử.

## 2. Context

Các revision trước của `VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017` và
`VIR-SPC-0018` dùng `import from net.http` như một umbrella form. Revision
2026-10-10 của bốn SPEC đã loại form này và thống nhất hai grammar riêng:
`import module [as alias]` cho whole-module namespace, và
`import symbol[, symbol ...] from module` cho named selective import.

Active import expander hỗ trợ selective `import symbols from module`, legacy
`from module import symbols`, `import * from module` và compatibility
`import module`. Nó không có branch nhận token `from` ngay sau `import` như
umbrella marker.

## 3. Expected Behavior

- `import M` resolve `M` qua canonical registry và bind whole-module namespace;
  `import M as A` bind namespace đó bằng local alias `A`.
- `import X from M` và `import X as Y from M` selectively import named exports;
  `from` chỉ xuất hiện sau một danh sách import item không rỗng.
- `import from M` không thuộc grammar và phải bị từ chối; nó không phải alias
  của `import M` và không inject toàn bộ export surface vào local scope.
- Export visibility, canonical dedup/cycle behavior và namespace semantics vẫn
  thuộc các ISSUE triển khai tương ứng, gồm `VIRC-ISS-0008` và
  `VIRC-ISS-0065`.

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

### Historical non-goals

- Selective `import X from M` và its symbol alias syntax không được đổi bởi
  quyết định rejection này.
- Whole-module namespace aliases thuộc `VIRC-ISS-0065`; `VIRC-ISS-0045` chỉ
  còn giữ bằng chứng lịch sử đã được supersede.
- Legacy `from M import X` và `import * from M` không trở thành canonical syntax;
  `import M` hiện là whole-module syntax chuẩn.
- NOT_VERIFIED: full declaration-kind set mà current export extractor có thể
  materialize; acceptance phải cover functions/types/constants/variables.

## 8. Impact

Trước revision 2026-10-10, một syntax được gọi là canonical trong active SPEC
luôn resolve sai, tạo divergence giữa parser, preprocessor, IDE và tài liệu.
Sau revision, behavior từ chối không còn là conformance defect của umbrella
import vì umbrella form không còn tồn tại.

Severity/priority ban đầu được giữ trong metadata để phản ánh lúc ISSUE mở;
không còn compiler implementation work thuộc ISSUE này.

## 9. Preliminary Analysis

- CONFIRMED: active text parser không nhận grammar `import from M` và resolve
  literal `from` như module; rejection phù hợp với grammar mới, dù diagnostic
  chuyên biệt hơn có thể được theo dõi riêng nếu cần.
- CONFIRMED: provider registry và unaliased compatibility whole import hoạt động.
- CONFIRMED: `VIRC-ISS-0008` vẫn sở hữu no-export fail-open; umbrella import
  implementation không được đóng issue visibility đó nếu chưa pass criteria.
- CONFIRMED: language decision 2026-10-10 không định nghĩa explicit
  whole-export injection mode; whole-module access đi qua namespace.
- NOT_VERIFIED: một diagnostic chuyên biệt cho empty selective form; không phải
  acceptance gate của ISSUE bị reject này.

## 10. Acceptance Criteria

Because the reported feature was removed from the language, these are the
criteria for rejecting the ISSUE rather than implementation criteria.

- [x] Các active module SPEC thống nhất `import module [as alias]` là
  whole-module namespace form.
- [x] Các active module SPEC chỉ cho phép `from` sau non-empty selective symbol
  list và ghi rõ `import from module` là invalid.
- [x] Derived Vir agent guidance được đồng bộ với contract mới.
- [x] Bằng chứng compiler cũ được giữ lại, nhưng các implementation acceptance
  criteria cho umbrella import bị rút vì feature không còn thuộc language.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit; contract hiện đã loại
  umbrella form rỗng.
- `VIRC-ISS-0008` — selective imports fail-open khi provider không có export.
- `VIRC-ISS-0045` — hồ sơ alias-only lịch sử, đã bị supersede.
- `VIRC-ISS-0065` — owner hợp nhất cho include/whole-module namespace aliases.

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
| 2026-10-09 | Linked VIRC-ISS-0065 as the consolidated namespace owner after VIRC-ISS-0045 supersession |
| 2026-10-10 | Rejected after VIR-SPC-0006/0014/0017/0018 made `import module` canonical and removed `import from module` from the grammar |
| 2026-10-10 | Linked VIR-ISS-0017 |
