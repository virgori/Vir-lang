---
id: "VIR-ISS-0013"
type: "ISSUE"
domain: "VIR"
title: "Language syntax deprecation and migration policy is not specified"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "compatibility"
  - "deprecation"
  - "versioning"
  - "migration"
related:
  issues:
    - "VIR-ISS-0011"
    - "VIR-ISS-0012"
    - "VIRC-ISS-0058"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "deprecation"
  - "migration"
  - "language-governance"
---

# VIR-ISS-0013 — Language syntax deprecation and migration policy is not specified

## 1. Summary

Vir chưa có normative policy chung cho việc loại keyword, đổi syntax hoặc
chuyển một language form sang library/tooling. VPS quy định lifecycle paper
nhưng không quy định warning window, release boundary, replacement metadata và
source migration obligations của language evolution.

## 2. Context

Các migration `of`, saga/resume, has/get, lazy directives và C/Rust aliases
đang dùng acceptance criteria riêng. Trước khi tinh gọn surface theo
`VIR-ISS-0011`/`0012`, language contract phải định nghĩa cách thay đổi mà không
phá source tùy tiện hoặc giữ alias vô thời hạn.

## 3. Expected Behavior

- Mỗi deprecation có SPEC version, replacement, warning/removal boundary và
  compatibility rationale.
- Breaking removal chỉ xảy ra tại release boundary được phê duyệt.
- Tooling có machine-readable diagnostic và migration path.
- Native first-class constructs không bị chuyển library chỉ vì muốn giảm số từ.
- VIRC issue chỉ mở sau khi VIR issue/SPEC quyết định hành vi normative.

## 4. Actual Behavior

- Alias có thể được chấp nhận im lặng hoặc bị reject không đồng nhất.
- Existing issues tự quyết định migration gates theo từng trường hợp.
- Không có policy chung nối SPEC semantic version với compiler release channel.
- Không có governance gate rõ buộc VIR resolution đi trước VIRC issue creation.

## 5. Reproduction

```sh
./paper show VIR-ISS-0001
./paper show VIR-ISS-0003
./paper show VIR-ISS-0005
./paper show VIR-ISS-0007
./paper show VIRC-ISS-0048
```

## 6. Evidence

- CONFIRMED: VPS không quy định language deprecation duration/schedule.
- CONFIRMED: current migration issues dùng các criteria cục bộ khác nhau.
- OBSERVED: compiler có alias được nhận không warning.
- NOT_VERIFIED: downstream ecosystem size và cadence phù hợp cho warning window.

## 7. Scope

### Affected

- syntax/operator/keyword evolution;
- language-form to library/tooling migration;
- SPEC/compiler version coordination;
- ordering giữa VIR và VIRC issue lifecycle.

### Not affected / Unknown

- Không quyết định form cụ thể nào bị loại.
- Không demote tensor/AI native constructs.
- Không thiết kế compiler migration tool trong language ISSUE.

## 8. Impact

Thiếu policy làm thay đổi source khó dự đoán hoặc khiến alias tồn tại vô hạn.
Severity S2, priority P1 vì policy là prerequisite cho surface simplification.

## 9. Preliminary Analysis

- CONFIRMED: normative decision phải thuộc VIR trước implementation VIRC.
- HYPOTHESIS: lifecycle phù hợp là inventory → VIR decision/SPEC → deprecation
  warning → migration evidence → declared release removal → VIRC verification.
- NOT_VERIFIED: warning duration cụ thể; PLAN phải dùng release/ecosystem data.

## 10. Acceptance Criteria

- [ ] SPEC hóa taxonomy cho compatibility alias, deprecated và removed forms.
- [ ] Định nghĩa required metadata: replacement, since-version, removal boundary
  khi được duyệt, diagnostic code và fix applicability.
- [ ] Định nghĩa rule liên kết SPEC semantic version với compiler release.
- [ ] Định nghĩa gate: VIR issue/SPEC phải resolved/approved trước khi tạo VIRC
  implementation issue cho cùng surface decision.
- [ ] Định nghĩa evidence tối thiểu cho source audit, migration, LSP/formatter,
  stdlib/tests và bootstrap trước removal.
- [ ] Chứng minh policy trên ít nhất một alias removal và một form chuyển sang
  library/tooling, không dùng tensor/AI native forms làm migration mẫu.

## 11. Related Papers

### Issues

- `VIR-ISS-0011` — native/core/library classification.
- `VIR-ISS-0012` — async/port/UI/graphics boundary.
- `VIRC-ISS-0048` — current alias evidence.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened to require language governance before compiler surface-removal issues |
| 2026-10-08 | Linked VIR-ISS-0011 |
| 2026-10-08 | Linked VIR-ISS-0012 |
| 2026-10-08 | Linked VIRC-ISS-0058 |
