---
id: <ID>
type: PLAN
domain: <VIR|VIRC|VLSP|STLB>
title: <TITLE>
status: DRAFT
created: YYYY-MM-DD
updated: YYYY-MM-DD
owners: []
components: []
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags: []
---

# <ID> — <Title>

## 1. Objective

Plan này giải quyết điều gì.

## 2. Source Issues

- <ISSUE-ID>

Không tạo PLAN không có lý do kỹ thuật rõ ràng.

## 3. Scope

### In Scope

- ...

### Out of Scope

- ...

## 4. Current Architecture

Mô tả trạng thái hiện tại dựa trên codebase thực tế. Không suy đoán nếu chưa
audit code.

## 5. Proposed Architecture

Kiến trúc mục tiêu.

## 6. Design Decisions

### Decision 1

**Decision:** ...

**Rationale:** ...

**Alternatives considered:** ...

**Trade-offs:** ...

## 7. Implementation Plan

### Phase 1 — ...

- files/modules:
- changes:
- dependencies:
- expected result:

## 8. Compatibility

- source compatibility;
- ABI nếu liên quan;
- parser compatibility;
- serialized formats;
- LSP protocol;
- public API;
- stdlib behavior.

## 9. Migration

No migration required.

## 10. Validation Plan

- unit tests;
- integration tests;
- regression tests;
- conformance tests;
- golden/manual verification nếu phù hợp.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ... | ... | ... | ... |

## 12. Rollback Strategy

Cách rollback an toàn.

## 13. Exit Criteria

- [ ] implementation completed;
- [ ] test suite passes;
- [ ] acceptance criteria satisfied;
- [ ] report generated;
- [ ] linked issues moved to VERIFYING/RESOLVED.

## 14. Related Papers

- ...

## 15. Revision History

| Date | Change |
|---|---|
| YYYY-MM-DD | Initial plan |
