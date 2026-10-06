---
id: "VIRC-ISS-0045"
type: "ISSUE"
domain: "VIRC"
title: "Include and whole-module import aliases do not create executable namespaces"
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
  - "symbol-resolution"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0046"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "namespace-alias"
  - "module-system"
  - "spec-conformance"
---

# VIRC-ISS-0045 — Include and whole-module import aliases do not create executable namespaces

## 1. Summary

Parser và text import parser nhận alias trong `include module as alias` và
`import module as alias`, nhưng source preprocessing chỉ splice provider body và
không tạo namespace binding. Cả hai forms compile tới semantic analysis rồi
thất bại E2001 khi consumer gọi `alias.symbol()`.

Selective symbol alias là cơ chế khác và đang hoạt động; ISSUE này chỉ sở hữu
whole-module namespace alias semantics.

## 2. Context

`VIR-SPC-0006` mục 5.3 yêu cầu include alias là namespace alias, còn mục 6.2 ghi
whole-module import alias là KNOWN GAP. `VIR-SPC-0014`, `VIR-SPC-0017` và
`VIR-SPC-0018` đều dùng include alias trong normative examples.

Frontend expand include/import ở text level trước lexer/parser. AST fields có
thể giữ alias nhưng directive đã bị loại khỏi source sau splice; vì thế alias
không trở thành một executable symbol/namespace trong semantic scope.

## 3. Expected Behavior

- `include module as alias` và `import module as alias` tạo namespace binding
  `alias` trỏ tới canonical module đã resolve.
- `alias.exported_symbol` resolve ổn định cho supported declaration kinds theo
  visibility contract của form tương ứng.
- Alias không tạo canonical Module ID mới, không splice module lần hai và không
  né cycle/dedup/export checks.
- Duplicate/conflicting alias có diagnostic tại directive; source provenance
  của symbol vẫn trỏ về provider.
- Selective symbol alias tiếp tục đổi local symbol name và không bị trộn với
  namespace alias.

## 4. Actual Behavior

- `include a as provider` load `a.vri`, nhưng `provider.a_value()` thất bại E2001
  `Undefined variable in current scope` tại `provider`.
- `import a as provider` cho cùng kết quả E2001.
- Control `import a` làm `a_value()` khả dụng trực tiếp và executable exit 42.
- Control selective alias `import a_value from a as provider_value` cũng compile
  và executable exit 42, xác nhận alias symbol path không phải lỗi này.

## 5. Reproduction

Dùng `module.list` và `a.vri` từ fixture của `VIRC-ISS-0044`, sau đó tạo:

```vir
# include_alias.vri
include a as provider

func main:
    out provider.a_value() + 2
end.
```

```vir
# import_alias.vri
import a as provider

func main:
    out provider.a_value() + 2
end.
```

```sh
./bin/virc /private/tmp/vir_module_feature_audit/include_alias.vri \
  -o /private/tmp/vir_module_feature_audit/include_alias.out --color=never -q
./bin/virc /private/tmp/vir_module_feature_audit/import_alias.vri \
  -o /private/tmp/vir_module_feature_audit/import_alias.out --color=never -q
```

## 6. Evidence

- CONFIRMED: `VIR-SPC-0006:228-243,280-300` tách namespace alias khỏi selective
  symbol alias và ghi failure hiện hành.
- CONFIRMED: `compiler/src/frontend/parser/stmt_module.vri:88-96,225-265` lưu
  whole-import/include aliases trong AST nodes.
- CONFIRMED: `compiler/src/main/include_expander.vri:252-302` không trả alias;
  `import_expander.vri:590-620` ghi `g_imp_alias` nhưng whole-body builder tại
  `:736-746` chỉ trả raw provider body.
- OBSERVED ngày 2026-10-06 tại HEAD `e1fc2d5`, binary SHA-256
  `db2a418c7952fffd66344ae9d29c28f5835ff25e08e634ea5915b911c00c7e69`:
  cả hai namespace alias probes exit 1/E2001 tại line 4 column 9.
- OBSERVED: unaliased whole import và selective alias controls compile 0, chạy
  exit 42.

## 7. Scope

### Affected

- include/import text preprocessing và parser/AST alias facts;
- namespace/symbol resolution, dedup/cycle identity và export visibility;
- diagnostics, source mapping, IDE module facts và module conformance fixtures.

### Not affected / Unknown

- Selective aliases như `import f from m as local_f` đang hoạt động và không
  được tái thiết kế trong ISSUE này.
- Multi-include list parsing thuộc `VIRC-ISS-0044`.
- Umbrella `import from module` thuộc `VIRC-ISS-0046`.
- NOT_VERIFIED: final visibility của unqualified names khi alias có mặt; PLAN
  phải theo normative SPEC decision thay vì suy ra từ raw-body compatibility.

## 8. Impact

Compiler chấp nhận phần directive khai báo alias nhưng không tạo binding, khiến
failure xuất hiện muộn và message nói alias là biến chưa khai báo. Điều này phá
API namespace được SPEC công bố và khiến module có tên symbol trùng nhau không
thể được qualify như thiết kế.

Severity S2 vì feature core không hoạt động nhưng có workaround dùng unaliased
whole load hoặc selective alias. Priority P1 vì namespace semantics ảnh hưởng
resolver, visibility, IDE và canonical module identity.

## 9. Preliminary Analysis

- CONFIRMED: alias được parse nhưng bị mất về mặt executable trong text-splice
  pipeline.
- CONFIRMED: provider/registry hợp lệ và selective symbol renaming hoạt động.
- HYPOTHESIS: namespace alias cần một first-class binding keyed by canonical
  Module ID thay vì textual rename toàn bộ provider declarations.
- NOT_VERIFIED: representation tối ưu ở AST, semantic module scope hay generated
  alias shim; lựa chọn thuộc PLAN sau khi visibility contract được chốt.

## 10. Acceptance Criteria

- [ ] Focused native fixtures cho `include m as a` và `import m as a` compile,
  execute và access provider qua `a.symbol`.
- [ ] Functions, constants, entities/enums và nested module dependencies có
  explicit namespace/visibility tests.
- [ ] Alias giữ canonical module identity, include/import-once behavior, cycle
  detection và source provenance; cùng provider qua hai compatible spellings
  không sinh duplicate definitions.
- [ ] Missing/private symbol, unknown module, duplicate alias và local-name
  collision có stable classic/JSON diagnostics tại source directive/use.
- [ ] Selective symbol alias behavior vẫn pass và không bị biến thành namespace.
- [ ] Multi-include per-element aliases interoperate với `VIRC-ISS-0044`.
- [ ] IDE facts/navigation/completion thấy namespace và provider origins đúng.
- [ ] Registered tests, supported targets và stage 2 == stage 3 bootstrap được
  ghi trong accepted REPORT trước khi đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — module/include specification audit và alias conformance gap.
- `VIRC-ISS-0044` — multi-include list và per-element alias parsing.
- `VIRC-ISS-0046` — canonical umbrella whole-export import spelling.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from include/import namespace-alias failures and passing controls |
| 2026-10-06 | Linked VIRC-ISS-0044 |
| 2026-10-06 | Linked VIR-ISS-0006 |
| 2026-10-06 | Linked VIRC-ISS-0046 |
