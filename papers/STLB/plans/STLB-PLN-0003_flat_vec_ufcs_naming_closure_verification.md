---
id: "STLB-PLN-0003"
type: "PLAN"
domain: "STLB"
title: "Flat Vec UFCS naming closure verification"
status: "COMPLETED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "stdlib"
components:
  - "collections"
  - "vec"
  - "ufcs"
related:
  issues:
    - "STLB-ISS-0033"
  plans: []
  reports:
    - "STLB-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "closure-audit"
  - "vec"
  - "ufcs"
---

# STLB-PLN-0003 — Flat Vec UFCS naming closure verification

## 1. Objective

Xác minh độc lập rằng quyết định one-level Vec UFCS trong `STLB-ISS-0033` đã
được phản ánh trong registry, compatibility surface và external-consumer
fixtures, sau đó tạo REPORT bắt buộc để đóng ISSUE. PLAN không hồi tố công việc
đã hoàn thành trước ngày 2026-10-11.

## 2. Source Issues

- `STLB-ISS-0033` — three-level Vec UFCS paths conflict with member-access
  semantics.

## 3. Scope

### In Scope

- audit canonical `self.try`, `self.remove`, `self.swapRemove` spellings;
- verify compatibility identities/symbols remain documented and compilable;
- compile the canonical Vec module and run external-consumer regressions;
- create reciprocal PLAN/REPORT links and close only after VPS validation.

### Out of Scope

- redesign UFCS/member resolution;
- implement generic Vec features outside the issue acceptance set;
- attribute historical registry/source edits to this closure-only PLAN.

## 4. Current Architecture

`stdlib/registry/vec.md` publishes flat receiver operations `self.try`,
`self.remove` and `self.swapRemove`; `stdlib/vir/collections/vec.vri` retains
`vec_*` compatibility symbols. `STLB-ISS-0032` is already CLOSED and its native
fixtures include canonical external Vec consumers. `STLB-ISS-0033` remains
RESOLVED because the consumer criterion and accepted REPORT are incomplete.

## 5. Proposed Architecture

Không đổi API architecture. Mục tiêu là chứng minh canonical flat UFCS surface
và compatibility layer bằng native tests, rồi hoàn tất VPS traceability.

## 6. Design Decisions

### Decision 1 — Closure-only verification

**Decision:** Dùng PLAN/REPORT riêng cho `STLB-ISS-0033`.

**Rationale:** `STLB-RPT-0002` nghiệm thu `STLB-ISS-0032` và chỉ ghi 0033 như
remaining work; không thể dùng nó làm accepted report hồi tố cho issue này.

**Alternatives considered:** Link trực tiếp report cũ hoặc đóng không report.

**Trade-offs:** Thêm hai paper nhỏ nhưng giữ đúng provenance và VPS lifecycle.

## 7. Implementation Plan

### Phase 1 — Audit and verify

- files/modules: Vec registry, Vec source, canonical consumer fixtures;
- changes: không sửa public API; thu thập evidence;
- dependencies: native compiler and Groups 3/11;
- expected result: flat naming and external consumers pass.

### Phase 2 — Close through VPS

- files/modules: source ISSUE, PLAN, REPORT and registry;
- changes: evaluate final criterion, accept REPORT, close ISSUE;
- dependencies: `./paper registry --check`, `./paper validate`;
- expected result: complete reciprocal trace chain.

## 8. Compatibility

- No new source or ABI change is introduced by this PLAN.
- Existing `vec_*` compatibility symbols remain in place.
- The audited canonical names remain `self.try`, `self.remove` and
  `self.swapRemove`.

## 9. Migration

Không có migration mới; compatibility mapping trong Vec registry là authority.

## 10. Validation Plan

- compile `stdlib/vir/collections/vec.vri` with native `virc`;
- verify `collections_vec_consumer_e2e.vri` and
  `canonical_vec_facade_e2e.vri` through Group 3;
- run Group 11 for UFCS/generic interaction regression;
- validate paper registry and VPS chain.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fixture passes only through compatibility spelling | Low | High | Inspect canonical registry spelling and fixture source alongside group result |
| Historical report is misattributed | Low | Medium | Create dedicated closure report and state historical boundary |

## 12. Rollback Strategy

Nếu external-consumer evidence fails, keep the ISSUE RESOLVED or REOPEN it and
leave the REPORT unaccepted. No stdlib source rollback is part of this PLAN.

## 13. Exit Criteria

- [x] canonical Vec module compiles;
- [x] external consumer and UFCS regression groups pass;
- [x] all source acceptance criteria are evaluated;
- [x] REPORT concludes `READY_FOR_CLOSE`;
- [x] reciprocal links, registry and VPS validation pass.

## 14. Related Papers

- `STLB-ISS-0033`.
- `STLB-ISS-0032`, `STLB-PLN-0002`, `STLB-RPT-0002` as predecessor context,
  not as the acceptance report for this PLAN.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Created dedicated closure-verification plan for flat Vec UFCS naming and external-consumer evidence |
| 2026-10-11 | Completed after Vec compilation, external-consumer/UFCS regressions, reciprocal linking and preliminary VPS validation passed |
| 2026-10-11 | Linked STLB-RPT-0003 |
