---
id: "VIRC-ISS-0065"
type: "ISSUE"
domain: "VIRC"
title: "Whole-module import namespaces and include composition boundaries are not enforced"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-09"
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
    - "VIR-ISS-0006"
    - "VIR-ISS-0017"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0046"
    - "VIRC-ISS-0064"
    - "VLSP-ISS-0002"
  plans:
    - "VIRC-PLN-0046"
  reports:
    - "VIRC-RPT-0063"
supersedes: "VIRC-ISS-0045"
superseded_by: null
tags:
  - "include"
  - "import"
  - "module-composition"
  - "module-namespace"
  - "namespace-alias"
  - "text-splicing"
  - "symbol-collision"
  - "export-boundary"
---

# VIRC-ISS-0065 — Whole-module import namespaces and include composition boundaries are not enforced

## 1. Summary

Compiler hiện source-splice cả `include M` và whole-module `import M`, làm mờ
hai boundary khác nhau mà `VIR-SPC-0021` v0.3.0 đang đưa qua REVIEW:

- `include M` phải compose implementation fragment vào cùng logical module,
  không tạo namespace; collision là duplicate declaration của cùng scope;
- `import M [as A]` phải giữ provider thành module độc lập, chỉ expose explicit
  exports qua namespace `M` hoặc `A`.

Include flattening hiện chứng minh một phần composition behavior, nhưng
whole-module import chưa có namespace/export isolation thực thi. Parser còn
chấp nhận `include M as A` dù form này không canonical theo review contract, và
duplicate/collision behavior của composed fragments chưa có conformance gate
đủ mạnh.

## 2. Context

Compiler mở rộng dependency trước lexer/parser. `include_expander.vri` splice
provider body cùng marker `@vir_mod_start` / `@vir_mod_end`; whole-module path
trong `import_expander.vri` cũng trả raw provider body khi không có selected
symbols. Internal source expansion không tự nó sai, nhưng các pass sau phải giữ
được language scope, visibility và module identity tương ứng từng directive.

Active parent specifications vẫn mô tả include namespace. `VIR-SPC-0021` đang
ở REVIEW để đảo contract đó theo quyết định language-owner: include là
same-module composition, còn import là independent namespace consumption. Vì
vậy implementation của ISSUE này chỉ được merge theo contract mới sau khi
focused SPEC chuyển ACTIVE và parent SPEC hết mâu thuẫn.

Issue này supersede alias-only `VIRC-ISS-0045` nhưng không còn yêu cầu include
namespace. Multi-include list parsing thuộc `VIRC-ISS-0044`; rejected umbrella
`import from M` thuộc `VIRC-ISS-0046`; selective export enforcement thuộc
`VIRC-ISS-0008`; generic receiver UFCS thuộc `VIRC-ISS-0064`.

## 3. Expected Behavior

- `include M` compose declarations vào unqualified scope của consumer như một
  fragment của cùng logical module; nó không bind namespace `M`.
- Included declarations giữ source provenance. Chúng chỉ trở thành public API
  khi composed module export tường minh; include tự thân không tạo export.
- Hai included fragments, hoặc fragment và consumer, khai báo cùng tên trong
  cùng scope phải báo duplicate declaration độc lập thứ tự; không last-wins.
- `include M as A` không thuộc canonical grammar và phải bị từ chối bằng stable
  syntax diagnostic, không được load provider rồi silently discard alias.
- `import M` compile/analyze provider như module độc lập, bind namespace `M`, chỉ
  expose explicit exports và không inject chúng thành unqualified locals.
- `import M as A` bind namespace local `A` tới cùng canonical Module ID; alias
  không tạo identity mới hoặc né export/cycle/dedup checks.
- Qualified lookup hỗ trợ mọi exported declaration kind, từ chối private hoặc
  missing members, và phân biệt module namespace với runtime receiver UFCS.
- Hai imported providers export cùng short name vẫn dùng đồng thời qua namespace
  riêng mà không duplicate/ambiguous global binding.
- Một consumer không được vừa include vừa import cùng canonical target.
- Repeated/diamond imports hội tụ một provider identity và không tự hàm ý chạy
  runtime initialization nhiều lần; exact initialization policy ngoài scope.

## 4. Actual Behavior

- `include result` đưa `isSuccess(...)` vào unqualified scope. Theo review
  contract mới, đây là expected composition control; việc `result.isSuccess`
  không tồn tại sau include không còn là defect mục tiêu.
- `import a as provider` load provider body nhưng không tạo executable namespace;
  `provider.a_value()` thất bại E2001 tại `provider`.
- Whole-module import body hiện bị flatten vào consumer, nên namespace-only
  access, unqualified non-injection và private export boundary chưa được chứng
  minh hoặc bảo vệ bởi representation riêng.
- Parser/preprocessor nhận `include a as provider`, load provider, rồi không tạo
  namespace dùng được. Theo review contract, form này phải bị reject sớm thay vì
  được hiểu như include alias.
- `include url` có thể gọi `url.parse(...)` chỉ vì provider tự khai báo runtime
  `UrlNamespace` facade và global `url`; đó không phải compiler module binding.
- Order-independent duplicate diagnostics giữa composed fragments hiện
  NOT_VERIFIED.

## 5. Reproduction

Historical include probe, nay là composition control:

```vir
# /private/tmp/vir_include_dot_result_probe.vri
include result

func makeResult -> Result of (int, int):
    out Result.Success(1)
end.

func main:
    if result.isSuccess(makeResult()) do
        out 0
    end
    out 1
end.
```

```sh
./bin/virc /private/tmp/vir_include_dot_result_probe.vri \
  --check --json --color=never
```

Đổi call thành unqualified form sau; form này phải tiếp tục pass khi include
composition được triển khai:

```vir
if isSuccess(makeResult()) do
```

Kiểm tra runtime facade control hiện có:

```sh
./bin/virc tests/strict_v2/ufcs_url_parse_positive_e2e.vri \
  --check --json --color=never
```

Cuối cùng đối chiếu facade:

```sh
rg -n '^entity UrlNamespace|^var url: UrlNamespace|method parse' \
  stdlib/vir/net/url.vri
```

Import namespace failure kế thừa từ `VIRC-ISS-0045`:

```vir
import a as provider

func main:
    out provider.a_value() + 2
end.
```

Form này hiện thất bại E2001, trong khi selective alias
`import a_value from a as provider_value` chạy thành công. Chạy riêng
`include a as provider` để xác nhận non-canonical form hiện được accept/load
thay vì nhận syntax diagnostic.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0021` v0.3.0 REVIEW tách include composition khỏi
  whole-module import namespace và loại include alias khỏi canonical grammar.
- CONFIRMED: active parent SPEC chưa đồng bộ, nên implementation contract mới
  chưa được tuyên bố ACTIVE.
- CONFIRMED: `compiler/src/main/include_expander.vri` expand include bằng text
  splice/marker; `compiler/src/main/import_expander.vri` trả raw provider body
  cho whole-module import không có selected symbols.
- CONFIRMED: `stdlib/stdlib.vri` đăng ký cả `result` và `url` là public Module
  IDs.
- CONFIRMED: `stdlib/vir/net/url.vri` khai báo `UrlNamespace` cùng global
  `url`, nên `url.parse` control không chứng minh include namespace hoạt động.
- OBSERVED ngày 2026-10-09 tại revision
  `b157da2f03b97ef6f700aff3e4a4d6ef38651982`, compiler SHA-256
  `a457dd41dbd8854624a847303e35472cd833f80415f730271f03e0ef1b16c4b7`:
  result dot-style probe exit 1/E2001, unqualified control exit 0, URL dot-style
  control exit 0 với một warning W4001 không liên quan.
- CONFIRMED: `VIRC-ISS-0007` và include-only fixtures chứng minh declarations
  hiện vào unqualified scope, phù hợp hướng composition nhưng chưa chứng minh
  collision/export conformance.
- CONFIRMED: evidence giữ lại từ `VIRC-ISS-0045` chứng minh parser nhận alias
  nhưng import expander không tạo executable namespace binding, gây E2001.
- NOT_VERIFIED: duplicate-declaration order independence, mixed-form rejection,
  private visibility isolation và repeated-import initialization behavior.

## 7. Scope

### Affected

- include composition scope, invalid include-alias diagnostic và duplicate
  declaration handling;
- whole-module import namespace symbols, export visibility và unqualified-name
  isolation;
- canonical dependency identity, mixed-form detection, dedup/cycle/provenance;
- module-qualified resolution/lowering và distinction với runtime UFCS;
- IDE completion, navigation, diagnostics và source provenance.

### Not affected / Unknown

- Selective import vẫn là cơ chế hợp lệ để chỉ đưa một tập symbol vào local
  scope; ISSUE này không loại bỏ `import A from M`.
- Selective symbol alias như `import f from M as local_f` vẫn là cơ chế local
  binding riêng và không bị chuyển thành module namespace.
- Generic receiver specialization thuộc `VIRC-ISS-0064`; module qualification
  không được dùng để che lỗi generic UFCS.
- Runtime module initialization timing/order/failure/cycle semantics cần SPEC
  riêng; ISSUE này chỉ cấm dependency multiplicity tự nhân initialization.
- Quyết định migration/xóa từng `*Namespace` facade của stdlib phải được audit
  theo module và không nằm trong ISSUE này.

## 8. Impact

Khi cả include và import đều bị flatten, compiler không thể bảo đảm module API
boundary: private names có nguy cơ rò, exported names có thể cạnh tranh trong
global scope, alias không dùng được, và collision có thể phụ thuộc expansion
order. Đồng thời việc chấp nhận include alias tạo source không portable theo
contract mới và làm migration khó chẩn đoán.

Severity S2 vì lỗi làm sai contract của core module system nhưng có workaround.
Priority P1 vì chuẩn naming mới và quá trình chuẩn hóa stdlib đang phụ thuộc
trực tiếp vào dot-style thống nhất.

## 9. Preliminary Analysis

- CONFIRMED: resolver đã có canonical Module ID, dedup và module provenance;
  gap nằm ở semantic participation sau resolution.
- CONFIRMED: compiler đã có `SymbolKind.Module` và module-qualified call paths,
  nhưng whole-module import chưa tạo binding/export table đúng contract.
- HYPOTHESIS: include có thể tiếp tục dùng source composition nội bộ nếu symbol
  registration xử lý nó như same-module declarations và giữ provenance.
- HYPOTHESIS: import cần first-class module binding tham chiếu export table;
  implementation không được merge provider scope dù có dùng source expansion.
- HYPOTHESIS: parse/cache provider theo canonical identity rồi liên kết symbol
  table sẽ giữ dedup và diagnostics ổn định hơn.
- NOT_VERIFIED: representation tối ưu cuối cùng ở AST, HIR hay semantic module
  graph; lựa chọn thuộc PLAN.

## 10. Acceptance Criteria

- [x] VIR-SPC-0021 chuyển ACTIVE và parent SPEC hết mâu thuẫn trước khi merge
  semantic implementation theo acceptance này.
- [x] `include M` đưa fragment declarations vào unqualified same-module scope,
  giữ provenance và không tạo namespace binding.
- [x] Included declarations chỉ public khi composed module export tường minh;
  include không tự export private declarations.
- [x] `include M as A` bị từ chối bằng stable classic/JSON syntax diagnostic,
  không load provider hoặc silently discard alias.
- [x] Hai fragments, hoặc fragment và consumer, khai báo cùng tên luôn báo
  duplicate declaration độc lập include order và không last-wins.
- [x] `import M` và `import M as A` bind namespace tương ứng, không inject
  exported names unqualified; alias giữ cùng canonical identity.
- [x] Module-qualified lookup hỗ trợ mọi exported declaration kind được SPEC
  cho phép và từ chối private/non-exported symbols với stable diagnostics.
- [x] Hai providers export cùng short name dùng được đồng thời qua namespace
  riêng mà không duplicate/ambiguous global binding.
- [x] Resolver phân biệt module namespace với runtime receiver UFCS bằng symbol
  kind; local shadowing và same-spelling collisions có test positive/negative.
- [x] Include và import cùng canonical target trong một consumer bị từ chối với
  diagnostic chỉ rõ cả hai dependency sites.
- [x] Repeated/diamond imports, compatible spelling, cycles và provenance hội tụ
  theo canonical Module ID; dependency multiplicity không nhân initialization.
- [x] IDE facts/completion/navigation phân biệt composed declaration với imported
  module member và trả đúng physical/provider provenance.
- [x] `./run_tests.sh 3`, relevant language/stdlib groups, supported target
  checks và stage 2 == stage 3 fixed point được ghi trong accepted REPORT.

## 11. Related Papers

### Issues

- `VIRC-ISS-0045` — historical alias-only issue, superseded by this issue and
  retained without a separate implementation.
- `VIRC-ISS-0044` — multi-include composition list parsing và per-element
  invalid-alias diagnostics.
- `VIRC-ISS-0046` — historical umbrella-import issue, rejected after the
  language selected `import M` as the sole whole-module form.
- `VIRC-ISS-0064` — generic receiver UFCS chưa resolve/specialize đầy đủ; không
  được trộn với module qualification.
- `VIRC-ISS-0007` — redundant include/import đã được loại, xác nhận include-only
  hiện đưa declarations vào unqualified scope.

### Plans

- [VIRC-PLN-0046](../plans/VIRC-PLN-0046_enforce_whole_module_import_namespaces_and_include_composition_boundaries.md)

### Reports

- [VIRC-RPT-0063](../reports/VIRC-RPT-0063_whole_module_import_namespaces_and_include_composition_boundaries_report.md)

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from result/url include namespace probes and active compiler inspection |
| 2026-10-09 | Linked VIRC-ISS-0045 |
| 2026-10-09 | Superseded VIRC-ISS-0045 and consolidated default plus aliased include/whole-module import namespaces under one implementation scope |
| 2026-10-09 | Linked VIRC-ISS-0064 |
| 2026-10-10 | Recorded rejection of the former `import from M` umbrella form; namespace scope remains `import M [as A]` |
| 2026-10-10 | Linked VIR-ISS-0017 and recorded the VIR-SPC-0021 draft distinction that must be resolved before include namespace implementation |
| 2026-10-10 | Recorded VIR-SPC-0021 v0.2.0 decision that include creates no namespace and duplicate fragment declarations must fail independent of include order |
| 2026-10-10 | Linked VIR-ISS-0017 |
| 2026-10-10 | Reframed the issue around VIR-SPC-0021 REVIEW: include composition/collisions, invalid include aliases, and independent whole-module import namespaces/export boundaries |
| 2026-10-10 | Linked VIRC-PLN-0046 |
| 2026-10-10 | Moved to IMPLEMENTING with implementation plan VIRC-PLN-0046 |
| 2026-10-11 | Linked VIRC-RPT-0063 |
| 2026-10-11 | All acceptance criteria satisfied; closed issue via accepted report VIRC-RPT-0063 |
| 2026-10-11 | Reopened after audit: qualified data/const/enum access bypasses E2113 export checks, qualified entity instantiation fails parser E1001, and missing whole-module regression coverage |
| 2026-10-11 | Audit remediation completed: fail-closed export boundary enforced across all declaration kinds (functions, constants, enums, entities), qualified entity literal parsing fixed, positive/negative whole-module regression fixtures added, shadowing verified, bit-identical fixed point bootstrap confirmed, 62/62 Group 3 tests passing; closed via accepted report VIRC-RPT-0063 |
| 2026-10-11 | Linked VLSP-ISS-0002 |
| 2026-10-11 | Closure audit replaced source-inspection-only IDE evidence with executable native LSP proof: complete compiler snapshot, export-only namespace completion, physical provider definition, and full 120/120 protocol suite pass |
