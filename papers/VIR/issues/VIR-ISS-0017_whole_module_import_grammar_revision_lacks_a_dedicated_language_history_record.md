---
id: "VIR-ISS-0017"
type: "ISSUE"
domain: "VIR"
title: "Whole-module import grammar revision lacks a dedicated language history record"
status: "CLOSED"
severity: "S4"
priority: "P1"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
components:
  - "module-system"
  - "include"
  - "import"
  - "language-governance"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0046"
    - "VIRC-ISS-0065"
  plans:
    - "VIR-PLN-0003"
  reports:
    - "VIR-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "grammar-history"
  - "module-dependency"
  - "include"
  - "import"
---

# VIR-ISS-0017 — Whole-module import grammar revision lacks a dedicated language history record

## 1. Summary

Ngày 2026-10-10, active Vir specifications đổi whole-module grammar từ
`import from M` sang `import M`, đồng thời giữ `import X from M` cho named
selective import. Thay đổi đã được ghi trong revision history của các SPEC và
`VIRC-ISS-0046` đã bị reject, nhưng chưa có VIR ISSUE riêng giữ decision record,
lý do ngôn ngữ, migration surface và quan hệ giữa `import M` với `include M`.

Thiếu hồ sơ riêng làm lịch sử thay đổi bị phụ thuộc vào một compiler ISSUE đã
reject và để hai dependency forms tiếp tục có mô tả chồng lấn trong active
module specifications.

## 2. Context

Trước revision 2026-10-10, `VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017` và
`VIR-SPC-0018` công bố ba form: selective `import X from M`, umbrella
`import from M`, và whole-module namespace `import M [as A]`. Compiler không
nhận umbrella form theo nghĩa đó; nó đọc `from` như module name và báo E2112.

Quyết định ngôn ngữ chọn grammar nhỏ hơn:

- `import M [as A]` là whole-module import;
- `import X[, Y ...] from M` là named selective import;
- `import from M` không thuộc grammar.

Sau khi bỏ umbrella form, active documents vẫn mô tả cả `include M` và
`import M` như các whole-module operations nhưng chưa có một focused contract
giải thích khi nào dùng form nào, visibility khác nhau ra sao, và vì sao chúng
không phải aliases.

## 3. Expected Behavior

- Mọi normative grammar change phải có VIR-owned ISSUE ghi decision, nguồn gốc,
  compatibility và migration impact, thay vì chỉ tồn tại trong compiler issue.
- `import M`, `import X from M` và invalid `import from M` phải có một grammar
  contract duy nhất trong mọi active module/language SPEC.
- `include M` và `import M` phải có roles khác nhau, không phải hai spellings
  đồng nghĩa cho cùng một text-splice operation.
- Một focused VIR SPEC phải mô tả source composition, module consumption,
  namespace binding, export boundary, canonical identity, dedup/cycle behavior
  và migration giữa hai forms.
- Compiler conformance phải được theo dõi tách khỏi language decision; SPEC
  không được biến behavior hiện hành thành semantics chỉ vì fixture đang pass.

## 4. Actual Behavior

- Grammar revision đã có trong bốn active SPEC nhưng trước ISSUE này không có
  VIR-owned history record chuyên biệt.
- `VIRC-ISS-0046` giữ reproduction của compiler cho form cũ nhưng status
  `REJECTED`; nó không phải owner phù hợp cho lịch sử language design.
- `VIR-SPC-0006` hiện nói `include M` thiết lập namespace và `import M` cũng tạo
  whole-module namespace, nên ranh giới semantic giữa hai form chưa đủ rõ.
- Native compiler hiện preprocess cả include/import bằng source splicing;
  implementation behavior đó chưa chứng minh một language-level distinction.

## 5. Reproduction

Đối chiếu active contract và compiler evidence từ repository root:

```sh
rg -n "import from|Whole-module namespace import|include.*namespace" \
  papers/VIR/specs/VIR-SPC-0006_module_include_system.md \
  papers/VIR/specs/VIR-SPC-0014_modules_ai_spec.md \
  papers/VIR/specs/VIR-SPC-0017_language_specification_english.md \
  papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md

sed -n '1,120p' tests/modules/test_include_only.vri
sed -n '800,850p' compiler/src/main/import_expander.vri
```

`test_include_only.vri` sử dụng declarations của provider dưới tên unqualified.
`text_build_import_body()` trả raw provider body khi whole-module import có zero
selected symbols. Hai bằng chứng xác nhận current implementation flattening,
không tự xác lập semantics mong muốn cho language.

## 6. Evidence

- CONFIRMED: revision 2026-10-10 của `VIR-SPC-0006` v3.3.0,
  `VIR-SPC-0014` v3.2.0 và `VIR-SPC-0017`/`0018` v3.3.0 loại
  `import from M` và chọn `import M` làm whole-module form.
- CONFIRMED: `VIRC-ISS-0046` giữ reproduction E2112 cho form cũ và bị reject vì
  feature được loại khỏi grammar.
- CONFIRMED: `tests/modules/test_include_only.vri` dùng `Point`, `shared_calc`
  và `SHARED_MAGIC` unqualified sau `include mod.dep_shared`.
- CONFIRMED: `compiler/src/main/import_expander.vri` trả toàn bộ `mod_body` khi
  `g_imp_sym_count == 0`, nên whole-module import hiện vẫn là text flattening.
- OBSERVED: Group 3 module suite ngày 2026-10-10 pass 40/40 sau grammar revision;
  suite không có fixture chứng minh namespace-only behavior của `import M`.
- CONFIRMED: `VIR-SPC-0021` v1.0.0 ACTIVE quy định include không tạo namespace,
  nên `include M as A` là invalid syntax.
- CONFIRMED: audit không tìm thấy include alias hoặc whole-module import trong
  production `.vri` dưới `compiler/src`, `stdlib/vir` và `tools`; chỉ
  `tests/modules/test_multi_include_alias_compat_positive.vri` giữ include
  alias như compatibility evidence cho `VIRC-ISS-0065`.
- CONFIRMED: `VIR-SPC-0006` v3.4.0, `VIR-SPC-0014` v3.3.0 và
  `VIR-SPC-0017`/`0018` v3.6.0 đã đồng bộ với focused contract.

## 7. Scope

### Affected

- Vir module grammar và dependency semantics;
- history/traceability của `VIR-SPC-0006`, `0014`, `0017`, `0018`;
- compiler include/import preprocessing và namespace conformance;
- LSP completion/navigation cho module namespaces;
- migration của source đang dựa vào unqualified whole-module flattening.

### Not affected / Unknown

- ISSUE này không tự triển khai compiler hoặc LSP changes.
- Selective export enforcement đã được xử lý riêng bởi `VIRC-ISS-0008`.
- Registry lookup order và `module.list` format vẫn thuộc `VIR-SPC-0006`.
- Package acquisition/version solving không thuộc core dependency syntax.
- Compatibility lifetime của include alias đã chấm dứt ở language contract;
  compiler rejection/migration fixture thuộc `VIRC-ISS-0065`.

## 8. Impact

Không có decision record, contributor có thể khôi phục `import from M`, coi
`include M` và `import M` là aliases, hoặc tối ưu text splicing theo cách làm rò
private declarations qua module boundary. Tài liệu và tooling cũng không thể
đưa ra migration advice nhất quán.

Severity S4 vì đây chủ yếu là thiếu governance/specification record; compiler
gaps quan sát được tiếp tục có ISSUE riêng. Priority P1 vì contract phải được
chốt trước khi triển khai namespace semantics của `VIRC-ISS-0065`.

## 9. Preliminary Analysis

- CONFIRMED: grammar mới đã được ghi đồng nhất trong bốn active SPEC.
- CONFIRMED: include-only và whole-module import hiện cùng dựa nhiều vào source
  flattening, nên compiler chưa cung cấp semantic boundary đủ rõ.
- OBSERVED: `include` phù hợp với vai trò ghép implementation fragments của một
  module, còn `import` phù hợp với consumption của independent exported API.
- CONFIRMED: tách composition (`include`) khỏi namespace consumption (`import`)
  loại ambiguity mà không khôi phục umbrella import.
- CONFIRMED: không có production compiler/stdlib/tool source dùng include alias;
  current compiler acceptance của fixture alias là conformance gap, không phải
  migration blocker cho quyết định ngôn ngữ.

## 10. Acceptance Criteria

- [x] Một VIR ISSUE riêng ghi grammar revision ngày 2026-10-10 và evidence của
  thay đổi lịch sử.
- [x] Một focused SPEC ở REVIEW có stable ID mô tả khác biệt giữa `include M` và
  `import M`, gồm grammar, scope, visibility, identity và migration.
- [x] SPEC ghi rõ current implementation evidence không đồng nghĩa conformance.
- [x] SPEC quy định duplicate declarations giữa included fragments là lỗi
  compile-time, không có last-include-wins.
- [x] SPEC tách dependency multiplicity khỏi runtime initialization và để
  initialization ordering cho một normative SPEC riêng.
- [x] Compatibility usage của include alias được audit và có migration/rejection
  path phối hợp với `VIRC-ISS-0065`.
- [x] Focused SPEC qua REVIEW sau quyết định language-owner.
- [x] Các active parent SPEC được đồng bộ và focused SPEC chuyển ACTIVE trước
  khi contract mới được tuyên bố canonical.
- [x] Compiler/LSP conformance gaps phát hiện từ review được gắn ISSUE riêng,
  không đóng ngầm bằng documentation-only evidence.

## 11. Related Papers

### Issues

- `VIR-ISS-0006` — audit và rewrite module/include specification trước đây.
- `VIRC-ISS-0044` — compiler gap cho multi-include composition list.
- `VIRC-ISS-0046` — historical compiler issue cho umbrella form đã bị loại.
- `VIRC-ISS-0065` — compiler namespace behavior cần được đối chiếu contract mới.

### Plans

- `VIR-PLN-0003` — activation, parent-SPEC synchronization, compatibility audit
  and lifecycle closure plan.

### Reports

- `VIR-RPT-0003` — accepted language-contract activation report.

### Specifications

- `VIR-SPC-0021` v1.0.0 — ACTIVE focused contract cho include composition và
  whole-module import consumption.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Closed after VIR-SPC-0021 v1.0.0 activation, parent-SPEC synchronization, compatibility audit, accepted VIR-RPT-0003, and VPS validation |
| 2026-10-10 | Opened a dedicated language-history record for the whole-module import grammar revision and include/import semantic distinction |
| 2026-10-10 | Linked VIR-ISS-0006 |
| 2026-10-10 | Linked VIRC-ISS-0046 |
| 2026-10-10 | Linked VIRC-ISS-0065 |
| 2026-10-10 | Refined VIR-SPC-0021 to v0.2.0 with six core invariants, duplicate-include conflict semantics, and a separate module-initialization boundary |
| 2026-10-10 | Advanced VIR-SPC-0021 v0.3.0 to REVIEW with normative multi-include composition after language-owner decision; ACTIVE remains gated by migration, parent-SPEC, and compiler/LSP conformance work |
| 2026-10-10 | Linked VIRC-ISS-0044 |
| 2026-10-10 | Linked VIR-PLN-0003 |
| 2026-10-10 | Linked VIR-RPT-0003 |
