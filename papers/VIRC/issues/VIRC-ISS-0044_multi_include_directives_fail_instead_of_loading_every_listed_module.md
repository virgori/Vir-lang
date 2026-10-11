---
id: "VIRC-ISS-0044"
type: "ISSUE"
domain: "VIRC"
title: "Multi-include directives fail instead of loading every listed module"
status: "CLOSED"
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
  - "parser"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIR-ISS-0017"
    - "VIRC-ISS-0045"
    - "VIRC-ISS-0065"
  plans:
    - "VIRC-PLN-0044"
  reports:
    - "VIRC-RPT-0061"
supersedes: null
superseded_by: null
tags:
  - "include"
  - "multi-include"
  - "module-system"
  - "spec-conformance"
---

# VIRC-ISS-0044 — Multi-include directives fail instead of loading every listed module

## 1. Summary

Native `virc` không compile directive chuẩn `include a, b`. Source preprocessor
chạy trước parser đọc `a,` như một module name duy nhất và phát E2102, dù parser
AST phía sau đã có logic lặp qua danh sách phân tách bằng dấu phẩy. Viết hai dòng
`include a` và `include b` cho cùng registry compile và chạy đúng.

## 2. Context

`VIR-SPC-0006` mục 5.3, `VIR-SPC-0014` và `VIR-SPC-0018` công bố multi-include
trên một dòng. Frontend pipeline lại expand include ở text level trước lexer và
parser, nên parser support không thể cứu directive mà preprocessor đã resolve
sai.

Audit dùng hai exact registry entries `a = a.vri` và `b = b.vri`; mỗi provider
export một function, còn consumer cộng hai kết quả thành 42.

## 3. Expected Behavior

- `include A, B` resolve, cycle-check, deduplicate và load từng canonical Module
  ID theo thứ tự source.
- Mỗi list element là một implementation fragment của cùng logical module và
  hỗ trợ cùng dependency-target spelling như một single-include directive.
- Multi-include tạo đúng cùng unqualified composition scope như các
  single-include tương đương; nó không tạo namespace hoặc export boundary.
- Alias-bearing include items tiếp tục được parser chấp nhận theo các parent SPEC
  đang `ACTIVE`. Việc loại bỏ include alias chỉ được thực thi sau khi
  `VIR-SPC-0021` trở thành `ACTIVE`; namespace behavior còn thiếu thuộc
  `VIRC-ISS-0065`.
- Whitespace, optional semicolon và line ending không thay đổi meaning.
- Failure ở một element chỉ đúng element, source line và module spelling thay
  vì báo toàn danh sách như một path.
- Các single-line và separate-line forms tạo cùng dependency graph, canonical
  dedup state và source provenance.

## 4. Actual Behavior

- `include a, b` exit 1 với E2102 `included source not found` tại line 1.
- `text_parse_include_name()` dừng ở whitespace nhưng không dừng/iterate tại
  comma, nên spelling gửi cho resolver là `a,` trong fixture có khoảng trắng.
- Control `include a` rồi `include b` compile thành công; executable exit 42.

## 5. Reproduction

```text
# module.list
root = .
a = a.vri
b = b.vri
```

```vir
# a.vri
func a_value -> int:
    out 40
end.

export a_value
```

```vir
# b.vri
func b_value -> int:
    out 2
end.

export b_value
```

```vir
# multi_include.vri
include a, b

func main:
    out a_value() + b_value()
end.
```

```sh
./bin/virc /private/tmp/vir_module_feature_audit/multi_include.vri \
  -o /private/tmp/vir_module_feature_audit/multi_include.out --color=never -q
```

Control: thay dòng đầu bằng hai dòng `include a` và `include b` rồi chạy lại.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0006:228-243` định nghĩa multi-include và ghi KNOWN GAP;
  `VIR-SPC-0018:448-453` minh họa cùng syntax.
- CONFIRMED: `compiler/src/frontend/parser/stmt_module.vri:225-265` đã parse
  nhiều include nodes qua comma.
- CONFIRMED: `compiler/src/main/include_expander.vri:252-302` chỉ đọc một name;
  `:1054-1086` resolve name đó trước khi parser chạy.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `db2a418c7952fffd66344ae9d29c28f5835ff25e08e634ea5915b911c00c7e69`:
  multi-include exit 1/E2102; control hai dòng compile 0 và executable exit 42.

## 7. Scope

### Affected

- text include scanner/parser và statement replacement;
- module resolution, include-once/cycle tracking và source markers cho list;
- classic/JSON diagnostics, IDE facts và module conformance tests.

### Not affected / Unknown

- Selective import nhiều symbol (`import A, B from M`) là grammar khác.
- Include-alias rejection và import namespace execution được theo dõi thống
  nhất bởi `VIRC-ISS-0065`; `VIRC-ISS-0045` chỉ còn là hồ sơ alias-only lịch sử.
- Registry mapping của từng `a`/`b` hoạt động trong control và không phải trigger.
- NOT_VERIFIED: behavior hiện tại khi comma không có whitespace hoặc list trộn
  quoted path và dotted name.

## 8. Impact

Một form được active SPEC công bố thất bại trước parser và có diagnostic gây hiểu
nhầm là registry/path bị thiếu. Workaround hai dòng đơn giản nhưng dependency
format, formatter và generated code không thể dựa vào grammar chuẩn đã mô tả.

Severity S2 vì mọi multi-include đều không build nhưng có workaround trực tiếp.
Priority P1 vì đây là gap nhỏ, rõ acceptance và nằm trên core module syntax.

## 9. Preliminary Analysis

- CONFIRMED: parser có list support nhưng active text preprocessor chỉ resolve
  một token-like name trước parser.
- CONFIRMED: provider files và registry entries hợp lệ qua separate-line control.
- HYPOTHESIS: include expander cần parse thành danh sách có provenance riêng cho
  từng element trước khi gọi existing single-module expansion path.
- NOT_VERIFIED: patch nhỏ nhất có giữ dedup/source-marker behavior cho mọi list
  shape hay cần shared directive parser.

## 10. Acceptance Criteria

- [x] Focused native fixture chứng minh `include a, b` load cả hai providers và
  executable cho kết quả 42.
- [x] Hai, ba và nhiều element; whitespace/semicolon; dotted registry name và
  quoted compatibility path có expected pass/fail rõ ràng.
- [x] Alias-bearing items trong multi-include được parse tương thích với các
  parent SPEC đang `ACTIVE`; compiler không áp dụng trước grammar của
  `VIR-SPC-0021` khi SPEC đó còn `REVIEW`.
- [x] Duplicate/repeated elements hội tụ theo canonical Module ID; real cycle
  vẫn báo chain hữu ích.
- [x] Collision giữa declarations của các fragment đã được audit độc lập; lỗi
  order-dependent còn tồn tại được ghi rõ và tiếp tục thuộc linked
  `VIRC-ISS-0065`, không còn bị report của ISSUE này tuyên bố là đã sửa.
- [x] Missing element diagnostic chỉ đúng spelling, registry/source line và
  không che những element đã/ chưa process.
- [x] Danh sách dài hơn 64 phần tử không bị truncate; target sau vị trí 64 vẫn
  được resolve hoặc phát diagnostic fail-closed.
- [x] Single-include, separate-line include, source markers, IDE facts và JSON
  diagnostics không regression.
- [x] Group 3 hoặc gate tương đương chạy fixture native, không chỉ parser AST.
- [x] Stage 2 == stage 3 bootstrap và supported-target module tests được ghi
  trong accepted REPORT trước khi đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit và remaining conformance
  matrix.
- `VIR-ISS-0017` — language decision record cho grammar và semantic boundary
  giữa include composition với whole-module import.
- `VIRC-ISS-0045` — hồ sơ alias-only lịch sử, đã bị supersede.
- `VIRC-ISS-0065` — owner cho include composition/collision boundary và
  executable whole-module import namespaces.

### Plans

- [VIRC-PLN-0044](../plans/VIRC-PLN-0044_support_multi_include_directives_in_source_preprocessor.md)

### Reports

- [VIRC-RPT-0061](../reports/VIRC-RPT-0061_support_multi_include_directives_in_source_preprocessor.md)

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from native multi-include failure and separate-line control |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Linked VIRC-ISS-0045 |
| 2026-10-09 | Linked VIRC-ISS-0065 as the consolidated namespace owner after VIRC-ISS-0045 supersession |
| 2026-10-10 | Aligned acceptance with VIR-SPC-0021: multi-include is same-module composition, include aliases are invalid, and duplicate declarations are order-independent errors |
| 2026-10-10 | Linked VIR-ISS-0017 |
| 2026-10-10 | Linked VIRC-PLN-0044 |
| 2026-10-10 | Linked VIRC-RPT-0061 |
| 2026-10-10 | Closed with verification report VIRC-RPT-0061 after fixed-point bootstrap and full test suite pass |
| 2026-10-10 | Reopened by corrective audit after the accepted report was disproved by >64-target truncation, order-dependent declaration collisions, and premature alias rejection |
| 2026-10-10 | Closed again after dynamic-list repair and native regression coverage; restored alias compatibility with ACTIVE specs and reassigned unresolved collision enforcement to VIRC-ISS-0065 |
