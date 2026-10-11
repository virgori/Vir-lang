---
id: "VIRC-ISS-0058"
type: "ISSUE"
domain: "VIRC"
title: "Language surface reduction lacks a versioned deprecation and source migration contract"
status: "REJECTED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "tooling"
  - "language-governance"
components:
  - "diagnostics"
  - "migration-tooling"
  - "versioning"
  - "bootstrap"
  - "compatibility"
related:
  issues:
    - "VIR-ISS-0001"
    - "VIR-ISS-0003"
    - "VIR-ISS-0005"
    - "VIR-ISS-0007"
    - "VIR-ISS-0013"
    - "VIRC-ISS-0048"
    - "VIRC-ISS-0055"
    - "VIRC-ISS-0056"
    - "VIRC-ISS-0057"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "deprecation"
  - "migration"
  - "compatibility"
  - "language-simplification"
---

# VIRC-ISS-0058 — Language surface reduction lacks a versioned deprecation and source migration contract

## 1. Summary

**REJECTED:** deprecation và migration policy là hợp đồng tiến hóa ngôn ngữ,
không phải compiler implementation issue đầu tiên. `VIR-ISS-0013` phải được
giải quyết trước; VIRC issue chỉ được tạo sau đó cho diagnostics/tooling cụ thể.

Các đề xuất giảm keyword và chuyển feature sang stdlib có thể gây source break,
nhưng repository chưa có một contract chung quy định inventory, warning period,
diagnostic schema, automated rewrite, release boundary và removal proof. Các
migration trước được xử lý theo từng issue, nên cùng một loại thay đổi có thể
được reject ngay, giữ alias im lặng, hoặc chỉ sửa source nội bộ mà không có
external compatibility policy.

Cần một compiler-owned migration contract trước khi thực hiện các removal từ
`VIRC-ISS-0055`–`0057`; issue này không tự phê duyệt removal cụ thể.

## 2. Context

VPS yêu cầu normative syntax change đi qua versioned SPEC và evidence. Active
tree đã có các migration riêng cho generic `of`, saga/resume, has/get,
lazy module forms và non-SPEC aliases. Chúng cung cấp pattern hữu ích nhưng chưa
tạo một policy thống nhất áp dụng cho toàn language surface.

Compiler version dùng calendar release/internal patch channels; SPEC dùng
semantic version riêng. Migration contract phải liên kết hai hệ version mà
không giả định compiler patch tự động cho phép breaking syntax removal.

## 3. Expected Behavior

- Mỗi removal có owner, SPEC decision, first-warning version, last-supported
  version, removal boundary và replacement mapping.
- Deprecated source không được chấp nhận im lặng; classic và JSON diagnostics
  có stable code, span, canonical replacement và machine-readable metadata.
- Repository và downstream source có audit/rewrite workflow idempotent, có dry
  run và không sửa comments/strings/foreign embedded code sai ngữ cảnh.
- Compatibility window được quyết định theo release policy; breaking removal
  không xảy ra trong internal patch chỉ vì implementation đã sẵn sàng.
- Removal chỉ đóng khi active source, stdlib, examples, tests, LSP/formatter và
  fixed-point bootstrap cùng hội tụ.

## 4. Actual Behavior

- Một số alias như `return` được nhận im lặng mà không warning.
- Một số retired form như `while` rơi xuống semantic undefined-name diagnostic
  thay vì syntax migration diagnostic.
- `VIR-ISS-0005` và `VIR-ISS-0007` vẫn phải tự đặt câu hỏi deprecation duration.
- Generic and saga migrations có acceptance riêng nhưng chưa có reusable schema
  cho keyword-to-library transformation.
- Không tìm thấy registry paper hiện hành định nghĩa một removal lifecycle chung
  xuyên compiler, LSP, formatter, stdlib và external projects.

## 5. Reproduction

```sh
./paper show VIRC-ISS-0048
./paper show VIR-ISS-0001
./paper show VIR-ISS-0003
./paper show VIR-ISS-0005
./paper show VIR-ISS-0007
rg -n -i 'deprecat|migration|removal version|compatibility window' \
  papers/VIR papers/VIRC compiler/src tools tests
```

Đối chiếu các paper cho thấy acceptance criteria được định nghĩa cục bộ; chưa
có contract chung được đăng ký cho language-surface removal.

## 6. Evidence

- CONFIRMED: VPS yêu cầu SPEC versioning, traceability và accepted REPORT trước
  closure nhưng không định nghĩa language deprecation schedule.
- CONFIRMED: existing syntax-removal issues có migration gates khác nhau.
- CONFIRMED: `VIRC-ISS-0048` ghi nhận alias được compiler nhận không warning.
- OBSERVED: repository có migration tools/tests cho một số syntax cụ thể, không
  phải một engine/policy đã chứng minh cho mọi grammar transformation.
- HYPOTHESIS: một diagnostic/fix schema chung sẽ giảm chi phí cho nhiều removal
  mà không cần một universal AST rewriter ngay từ đầu.
- NOT_VERIFIED: số lượng và release cadence của external Vir projects.

## 7. Scope

### Affected

- syntax/keyword/operator deprecation;
- keyword-to-library/API migration;
- classic and JSON diagnostics;
- source audit/rewrite tooling;
- compiler/LSP/formatter/stdlib/test/bootstrap closure;
- compiler release and SPEC version coordination.

### Not affected / Unknown

- Không quyết định keyword/feature nào bị loại.
- Không bảo đảm source compatibility vĩnh viễn.
- Không sửa external repositories khi chưa có owner authorization.
- Binary/ABI compatibility cần contract riêng khi replacement thay public ABI.
- NOT_VERIFIED: package ecosystem telemetry có sẵn để chọn window theo usage.

## 8. Impact

Không có migration contract, simplification có thể phá source bất ngờ hoặc bị
trì hoãn vô hạn bởi alias im lặng. Cả hai đều làm suy yếu language contract.
Severity S2 vì rủi ro compatibility rộng nhưng chưa phải runtime data loss; P1
vì đây là prerequisite cho các surface-reduction issues.

## 9. Preliminary Analysis

- CONFIRMED: compiler acceptance và normative SPEC status đang không đủ để suy
  ra một removal schedule.
- CONFIRMED: source-internal migration alone không chứng minh downstream safety.
- HYPOTHESIS: default lifecycle nên là inventory → SPEC decision → warning +
  replacement tooling → repository/downstream audit → declared release-boundary
  removal → negative conformance + bootstrap report.
- NOT_VERIFIED: warning duration tối ưu; PLAN phải chọn bằng release policy và
  ecosystem evidence thay vì hard-code trong ISSUE.

## 10. Acceptance Criteria

- [ ] Phê duyệt lifecycle chung cho syntax/API surface removal, bao gồm owner,
  SPEC version, compiler version, warning/removal boundaries và rollback.
- [ ] Định nghĩa machine-readable deprecation diagnostic fields: stable code,
  old form, replacement, since-version, removal-version khi đã chốt, và source
  span/fix applicability.
- [ ] Định nghĩa audit/rewrite protocol có dry-run, idempotence, parse-aware
  exclusions và reviewable change manifest.
- [ ] Chứng minh protocol trên ít nhất một alias removal và một
  keyword-to-stdlib migration; text-only replacement không đủ.
- [ ] CI gate ngăn deprecated forms quay lại active compiler/stdlib/examples và
  positive tests, nhưng cho phép explicit negative fixtures.
- [ ] LSP/formatter/diagnostic parity được kiểm tra cùng compiler classic/JSON.
- [ ] Removal REPORT ghi internal/external migration evidence, bootstrap fixed
  point, known unsupported consumers và rollback result.
- [ ] `VIRC-ISS-0055`–`0057` không chuyển sang destructive implementation phase
  trước khi criteria phù hợp của contract này được đưa vào linked PLAN.

## 11. Related Papers

### Issues

- `VIRC-ISS-0048` — current non-SPEC alias cleanup.
- `VIRC-ISS-0055` — remaining keyword surface inventory.
- `VIRC-ISS-0056` — async/task/port boundary.
- `VIRC-ISS-0057` — UI/graphics/AI boundary.
- `VIR-ISS-0001` — generic syntax migration closure.
- `VIR-ISS-0003` — saga/resume migration.
- `VIR-ISS-0005` — has/get simplification.
- `VIR-ISS-0007` — lazy directive removal decision.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened as compatibility prerequisite for keyword and compiler-to-stdlib surface reduction |
| 2026-10-08 | Rejected because VIR-ISS-0013 must define the normative deprecation and migration policy first |
| 2026-10-08 | Linked VIRC-ISS-0055 |
| 2026-10-08 | Linked VIRC-ISS-0056 |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-08 | Linked VIRC-ISS-0048 |
| 2026-10-08 | Linked VIR-ISS-0001 |
| 2026-10-08 | Linked VIR-ISS-0003 |
| 2026-10-08 | Linked VIR-ISS-0005 |
| 2026-10-08 | Linked VIR-ISS-0007 |
| 2026-10-08 | Linked VIR-ISS-0013 |
