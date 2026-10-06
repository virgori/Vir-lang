---
id: "VIR-ISS-0007"
type: "ISSUE"
domain: "VIR"
title: "Unimplemented lazy module directives remain normative in active specifications"
status: "RESOLVED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "language"
components:
  - "module-system"
  - "language-specification"
  - "grammar"
  - "dependency-graph"
related:
  issues:
    - "VIR-ISS-0005"
    - "VIR-ISS-0006"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "lazy-include"
  - "lazy-import"
  - "language-simplification"
  - "breaking-change"
  - "spec-conformance"
---

# VIR-ISS-0007 — Unimplemented lazy module directives remain normative in active specifications

## 1. Summary

Các specification Vir đang công bố `lazy include` và `lazy import` như cơ chế
dependency chỉ nạp type, cho phép vòng phụ thuộc giữa `entity`/`enum`. Active
compiler không có semantics end-to-end tương ứng: `lazy include` không nạp
provider trước semantic analysis, còn `lazy import` bị parser từ chối.

Quyết định cho Vir 3.0 là loại hai directive `lazy` này khỏi normative module
contract thay vì duy trì một surface syntax không hoạt động. Việc loại standalone
`get X from module` đã được sở hữu trực tiếp bởi `VIR-ISS-0005`; ISSUE này không
tạo bản sao của phần việc đó.

## 2. Context

`VIR-SPC-0014` mục `lazy` và `VIR-SPC-0018` mục 3.8 mô tả một state machine
`ChuaNap -> DangParseLazy -> DaParseLazy`, type-only parsing, cycle permission và
upgrade sang full include. `VIR-SPC-0017` còn liệt kê `lazy include` trong quick
reference. `VIR-SPC-0006` v2.0.0 đã hạ cả `lazy include`/`lazy import` thành
KNOWN GAP nhưng vẫn giữ chúng trong danh sách contract cần xử lý.

Parser hiện có `LazyIncludeStmt` cho `lazy include`; nó không nhận `lazy import`.
Hai text preprocessor chạy trước parser chỉ scan directive bắt đầu trực tiếp bằng
`include `, `import ` hoặc `from `, nên không có đường load provider cho
`lazy include`.

## 3. Expected Behavior

- `lazy include` và `lazy import` không còn là syntax chuẩn, normative example,
  keyword/reference entry hoặc dependency-graph state trong active Vir 3.0
  specifications.
- Các specification tiếng Anh, tiếng Việt và focused module specification dùng
  cùng một contract: dependency runtime dùng `include` hoặc `import`; cycle vẫn
  bị từ chối theo canonical Module ID.
- Source dùng directive đã loại nhận syntax/migration diagnostic ổn định hoặc
  lỗi cú pháp chuẩn, không được parser chấp nhận rồi thất bại muộn ở semantic.
- Một cơ chế type-interface/cyclic-type dependency tương lai, nếu cần, phải có
  SPEC và implementation issue riêng thay vì ngầm phục hồi `lazy`.
- Standalone `get X from M` được loại theo `VIR-ISS-0005`; function/member tên
  `get` vẫn hợp lệ.

## 4. Actual Behavior

- `VIR-SPC-0014:84-93` và `VIR-SPC-0018:526-558` mô tả `lazy` như feature có
  semantics cụ thể dù compiler không thực hiện contract đó.
- `lazy include a` được parser nhận nhưng không load `a`; dùng symbol từ `a`
  thất bại E2002 ở semantic analysis.
- `lazy import a_value from a` thất bại E1001 tại `import` với thông báo chỉ
  chấp nhận `include` sau `lazy`.
- Không có focused positive executable test chứng minh type-only loading, cycle
  permission hoặc upgrade từ lazy sang full module.

## 5. Reproduction

Tạo project tối thiểu:

```text
# module.list
root = .
a = a.vri
```

```vir
# a.vri
func a_value -> int:
    out 40
end.

export a_value
```

Hai consumer:

```vir
lazy include a

func main:
    out a_value() + 2
end.
```

```vir
lazy import a_value from a

func main:
    out a_value() + 2
end.
```

Chạy:

```sh
./bin/virc /private/tmp/vir_module_feature_audit/lazy_include.vri \
  -o /private/tmp/vir_module_feature_audit/lazy_include.out --color=never -q
./bin/virc /private/tmp/vir_module_feature_audit/lazy_import.vri \
  -o /private/tmp/vir_module_feature_audit/lazy_import.out --color=never -q
```

## 6. Evidence

- CONFIRMED: `VIR-SPC-0014:84-93`, `VIR-SPC-0018:526-558` và quick-reference
  entries trong `VIR-SPC-0017`/`0018` công bố lazy dependency semantics.
- CONFIRMED: `compiler/src/frontend/parser/stmt_dispatch/modifiers.vri:209-243`
  chỉ parse `lazy include` và phát parser error cho token khác sau `lazy`.
- CONFIRMED: `compiler/src/main/include_expander.vri:227-250` chỉ phát hiện dòng
  bắt đầu `include `; `import_expander.vri:14-43` chỉ phát hiện `import ` hoặc
  `from `.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`: `lazy include` exit 1 với E2002
  `Undefined function or symbol: 'a_value'`; `lazy import` exit 1 với E1001
  `expected 'include' after 'lazy'`.
- CONFIRMED: `VIR-ISS-0005` đã yêu cầu loại standalone `get ... from ...` khỏi
  active English/Vietnamese và focused module specifications; tạo ISSUE `get`
  thứ hai sẽ trùng ownership.

## 7. Scope

### Affected

- `VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017`, `VIR-SPC-0018` và các
  generated/AI mirrors của module grammar;
- module dependency, cycle documentation và derived agent guidance.

### Not affected / Unknown

- `include`, selective/whole-module `import`, `export`, `share` và `port` không
  bị loại bởi ISSUE này.
- Standalone `get` removal thuộc `VIR-ISS-0005`.
- Namespace aliases, multi-include và umbrella import được theo dõi bởi các
  VIRC issue riêng; ISSUE này không hạ contract của chúng.
- Lexer/parser/AST/lowering/formatter/LSP changes, migration diagnostics and
  conformance tests are downstream compiler/tooling work and do not gate this
  language-document ISSUE.
- NOT_VERIFIED: số project ngoài repository đang dùng lazy directives.

## 8. Impact

Giữ syntax normative nhưng không hoạt động khiến người dùng thiết kế dependency
cycle dựa trên một state machine không tồn tại, và lỗi chỉ xuất hiện sau khi đã
viết type graph theo SPEC. Loại syntax làm contract Vir 3.0 nhỏ, kiểm chứng được
và tránh phải duy trì một loader type-only thứ hai khi chưa có use case/test.

Severity S2 vì đây là language-contract mismatch có thể làm project không build,
nhưng người dùng có thể tái cấu trúc cycle hoặc dùng dependency đầy đủ. Priority
P1 vì breaking grammar decision phải được chốt trước khi Vir 3.0 surface freeze.

## 9. Preliminary Analysis

- CONFIRMED: active frontend không có đường load provider cho line bắt đầu
  `lazy include`; parser support riêng lẻ không tạo executable semantics.
- CONFIRMED: `lazy import` được mô tả trong SPEC nhưng parser hiện từ chối.
- CONFIRMED: không cần ISSUE `get` mới vì `VIR-ISS-0005` đã có scope, migration
  mapping và acceptance criteria cho removal.
- HYPOTHESIS: xóa `LazyIncludeStmt` cùng `LazyKw` sau inventory sẽ đơn giản hơn
  giữ compatibility parser-only path.
- NOT_VERIFIED: có cần migration warning tạm thời hay Vir 3.0 có thể reject trực
  tiếp; quyết định này thuộc implementation PLAN.

## 10. Acceptance Criteria

- [x] `VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017` và `VIR-SPC-0018` loại
  `lazy include`/`lazy import` khỏi normative syntax, examples, dependency state
  machines, keyword tables và quick references.
- [x] Mỗi SPEC được tăng version phù hợp, cập nhật `updated` và Revision History;
  English/Vietnamese parity được kiểm tra.
- [x] Module contract còn lại mô tả cycle là lỗi và không ám chỉ type-only lazy
  resolution đang tồn tại.
- [x] `VIR-ISS-0005` hoàn thành removal của standalone `get` trong cùng tập SPEC,
  không tạo hai ownership hoặc hai migration contracts khác nhau.
- [x] Derived Vir agent guidance không còn chỉ dẫn dùng deferred type-only
  module directive.

Compiler removal, compatibility diagnostics, source migration, test coverage
và bootstrap state thuộc VIRC/tooling work độc lập, không phải acceptance
criteria của VIR documentation ISSUE này.

## 11. Related Papers

### Issues

- `VIR-ISS-0005` — loại `has` và standalone `get ... from ...`; giữ `get` như
  ordinary identifier/member.
- `VIR-ISS-0006` — audit umbrella cho module/include SPEC và convergence giữa
  các active specifications.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from specification/source audit and native lazy-directive probes |
| 2026-10-06 | Linked VIR-ISS-0005 |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Resolved the normative-document scope across the focused and bilingual active specifications; compiler conformance remains independent |
