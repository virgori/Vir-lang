---
id: "VIR-PLN-0004"
type: "PLAN"
domain: "VIR"
title: "Resolved Vir module language corrections closure audit"
status: "COMPLETED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "VIR"
components:
  - "language-specification"
  - "module-system"
  - "module-registry"
related:
  issues:
    - "VIR-ISS-0005"
    - "VIR-ISS-0006"
    - "VIR-ISS-0007"
    - "VIR-ISS-0008"
  plans: []
  reports:
    - "VIR-RPT-0004"
supersedes: null
superseded_by: null
tags:
  - "closure-audit"
  - "specification"
  - "modules"
---

# VIR-PLN-0004 — Resolved Vir module language corrections closure audit

## 1. Objective

Thực hiện một đợt audit độc lập, có thể tái lập, để quyết định liệu bốn ISSUE
ngôn ngữ đã ở trạng thái `RESOLVED` có đủ bằng chứng VPS để chuyển sang
`CLOSED` hay không. PLAN này chỉ điều hành việc kiểm tra và lập hồ sơ đóng;
những thay đổi SPEC lịch sử đã có trước ngày 2026-10-11 không được hồi tố thành
kết quả triển khai của PLAN này.

## 2. Source Issues

- VIR-ISS-0005
- VIR-ISS-0006
- VIR-ISS-0007
- VIR-ISS-0008

Bốn ISSUE cùng thuộc một cụm thay đổi phá vỡ tương thích của Vir 3.0: loại bỏ
`has`/standalone `get`, loại mô tả kiến trúc compiler đã nghỉ, loại deferred
module forms và reserve exact stdlib Module IDs.

## 3. Scope

### In Scope

- đối chiếu acceptance criteria của bốn source ISSUE với các ACTIVE SPEC;
- kiểm tra version, trạng thái, revision history và liên kết hai chiều;
- kiểm tra derived Vir guidance không tái giới thiệu syntax đã loại;
- chạy VPS validation và các regression gate module hiện có;
- lập REPORT độc lập và chỉ đóng ISSUE nếu REPORT kết luận `READY_FOR_CLOSE`.

### Out of Scope

- sửa lại quyết định ngôn ngữ hoặc tạo syntax module mới;
- nhận công trạng cho các thay đổi SPEC đã hoàn thành trước PLAN;
- thay đổi compiler, LSP hoặc standard-library implementation;
- đóng các implementation ISSUE phụ thuộc nếu chúng chưa có hồ sơ riêng.

## 4. Current Architecture

`VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017` và `VIR-SPC-0018` đều đang
`ACTIVE`. Chúng mô tả module contract Vir 3.0 dựa trên registry, không còn
`has`, standalone `get` hoặc deferred/lazy module directive. `get` vẫn là tên
thông thường. Các stdlib Module ID đang active được reserve khỏi exact project
collision và validity được kiểm tra trước resolution.

Các compiler ISSUE liên quan tới selective export, multi-include, registry
collision và dot-style module resolution đã ở trạng thái terminal riêng. Vì
các source ISSUE ngôn ngữ chưa có PLAN/REPORT, VPS chưa cho phép đóng dù nội
dung acceptance đã được đánh dấu hoàn tất.

## 5. Proposed Architecture

Không thay đổi kiến trúc ngôn ngữ. Trạng thái mục tiêu là một trace chain
`REPORT ↔ PLAN ↔ ISSUE ↔ SPEC/gates` thể hiện rõ đây là closure audit, giữ
nguyên provenance của công việc lịch sử và cung cấp bằng chứng mới ngày
2026-10-11.

## 6. Design Decisions

### Decision 1 — Dùng một closure-audit chain chung

**Decision:** Một PLAN và một REPORT bao phủ cả bốn ISSUE.

**Rationale:** Bốn acceptance set cùng được hiện thực bởi một tập ACTIVE SPEC
và cùng gate module/spec; audit chung giảm trùng lặp nhưng vẫn giữ liên kết hai
chiều tới từng ISSUE.

**Alternatives considered:** Tạo bốn cặp PLAN/REPORT riêng.

**Trade-offs:** REPORT chung dài hơn, nhưng mỗi ISSUE vẫn phải được đánh giá
riêng và có kết luận rõ ràng.

### Decision 2 — Không hồi tố PLAN

**Decision:** PLAN chỉ bao phủ audit hiện tại; REPORT phải phân biệt nội dung
SPEC có sẵn với bằng chứng mới chạy trong audit.

**Rationale:** VPS cấm viết lại PLAN như thể nó đã điều hành implementation xảy
ra trước đó.

**Alternatives considered:** Gán các thay đổi lịch sử vào PLAN mới.

**Trade-offs:** Hồ sơ nêu rõ provenance thay vì tạo timeline đẹp nhưng sai.

## 7. Implementation Plan

### Phase 1 — Audit normative state

- files/modules: bốn ISSUE nguồn, bốn ACTIVE SPEC và derived Vir skills;
- changes: chỉ ghi nhận bằng chứng, không sửa normative language;
- dependencies: canonical paper registry và active spec metadata;
- expected result: mỗi criterion có một nguồn chứng minh cụ thể hoặc được đánh
  dấu chưa đạt.

### Phase 2 — Verify gates and traceability

- files/modules: native module regression groups, `papers/REGISTRY.yaml`;
- changes: tạo verification REPORT và liên kết reciprocal;
- dependencies: self-hosted native test stack và `./paper validate`;
- expected result: gate xanh, REPORT `ACCEPTED/READY_FOR_CLOSE`, sau đó mới
  chuyển source ISSUE sang `CLOSED`.

## 8. Compatibility

- Audit không tạo thay đổi source, ABI, parser, protocol hoặc stdlib mới.
- Các breaking changes Vir 3.0 đã được ghi trong revision history của ACTIVE
  SPEC và được đánh giá như historical state, không phải output của PLAN.

## 9. Migration

Không có migration mới. Hướng dẫn migration đã nằm trong `VIR-SPC-0006` và các
SPEC ngôn ngữ active.

## 10. Validation Plan

- kiểm tra trực tiếp metadata/version/revision của bốn ACTIVE SPEC;
- tìm kiếm normative text cho removed forms, ordinary `get`, cycle policy và
  exact cross-registry collision;
- chạy Group 3 và Group 11 của native verification stack;
- chạy toàn bộ LSP regression để phát hiện drift từ canonical language docs;
- chạy `./paper registry --check` và `./paper validate` sau khi hoàn thành
  traceability.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dấu checklist cũ không phản ánh SPEC hiện tại | Low | High | Đối chiếu từng criterion với ACTIVE SPEC và revision history |
| PLAN mới bị hiểu sai là plan triển khai lịch sử | Medium | Medium | Ghi rõ scope closure-only và deviations/provenance trong REPORT |
| Paper links làm registry mất nhất quán | Low | Medium | Dùng `paper new`/`paper link`, rồi chạy registry và VPS validation |

## 12. Rollback Strategy

Nếu audit thất bại, giữ ISSUE ở `RESOLVED` hoặc chuyển `REOPENED` theo VPS và
để REPORT ở `REVIEW`/`REJECTED`; không hoàn nguyên hay viết lại ACTIVE SPEC
trong PLAN này. Các thay đổi paper chưa nghiệm thu có thể được sửa riêng mà
không ảnh hưởng compiler artifacts.

## 13. Exit Criteria

- [x] từng acceptance criterion được audit với evidence hiện tại;
- [x] native module/LSP gates cần thiết pass;
- [x] reciprocal links và registry validation pass;
- [x] REPORT được tạo và kết luận `READY_FOR_CLOSE`;
- [x] chỉ các ISSUE được REPORT chấp thuận mới chuyển sang `CLOSED`.

## 14. Related Papers

- `VIR-ISS-0005` — removal of `has` and standalone `get`.
- `VIR-ISS-0006` — active module SPEC architecture correction.
- `VIR-ISS-0007` — removal of unimplemented lazy module directives.
- `VIR-ISS-0008` — reserved active stdlib Module IDs.
- `VIR-SPC-0006`, `VIR-SPC-0014`, `VIR-SPC-0017`, `VIR-SPC-0018` —
  authoritative normative evidence.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Created closure-audit plan for four resolved Vir module-language issues; explicitly excluded retroactive ownership of historical SPEC edits |
| 2026-10-11 | Completed after criterion mapping, native module/LSP regressions, reciprocal linking and preliminary VPS validation passed |
| 2026-10-11 | Linked VIR-RPT-0004 |
