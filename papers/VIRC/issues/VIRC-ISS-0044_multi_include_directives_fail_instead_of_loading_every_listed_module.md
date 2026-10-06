---
id: "VIRC-ISS-0044"
type: "ISSUE"
domain: "VIRC"
title: "Multi-include directives fail instead of loading every listed module"
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
  - "parser"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIRC-ISS-0045"
  plans: []
  reports: []
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
- Mỗi list element hỗ trợ cùng module spelling và alias grammar như một
  single-include directive.
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
- Namespace alias execution được theo dõi bởi `VIRC-ISS-0045`.
- Registry mapping của từng `a`/`b` hoạt động trong control và không phải trigger.
- NOT_VERIFIED: behavior hiện tại khi comma không có whitespace hoặc list trộn
  quoted path, dotted name và alias.

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
- NOT_VERIFIED: patch nhỏ nhất có giữ alias/dedup/source-marker behavior cho mọi
  list shape hay cần shared directive parser.

## 10. Acceptance Criteria

- [ ] Focused native fixture chứng minh `include a, b` load cả hai providers và
  executable cho kết quả 42.
- [ ] Hai, ba và nhiều element; whitespace/semicolon; dotted registry name và
  quoted compatibility path có expected pass/fail rõ ràng.
- [ ] Per-element `as alias` phối hợp với namespace-alias contract của
  `VIRC-ISS-0045` mà không silently discard alias.
- [ ] Duplicate/repeated elements hội tụ theo canonical Module ID; real cycle
  vẫn báo chain hữu ích.
- [ ] Missing element diagnostic chỉ đúng spelling, registry/source line và
  không che những element đã/ chưa process.
- [ ] Single-include, separate-line include, source markers, IDE facts và JSON
  diagnostics không regression.
- [ ] Group 3 hoặc gate tương đương chạy fixture native, không chỉ parser AST.
- [ ] Stage 2 == stage 3 bootstrap và supported-target module tests được ghi
  trong accepted REPORT trước khi đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit và remaining conformance
  matrix.
- `VIRC-ISS-0045` — executable namespace aliases cho include/import.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from native multi-include failure and separate-line control |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Linked VIRC-ISS-0045 |
