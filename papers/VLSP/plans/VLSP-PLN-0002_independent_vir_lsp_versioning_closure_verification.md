---
id: "VLSP-PLN-0002"
type: "PLAN"
domain: "VLSP"
title: "Independent vir-lsp versioning closure verification"
status: "COMPLETED"
created: "2026-10-11"
updated: "2026-10-11"
owners:
  - "lsp"
components:
  - "versioning"
  - "release-process"
  - "protocol"
related:
  issues:
    - "VLSP-ISS-0001"
  plans: []
  reports:
    - "VLSP-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "closure-audit"
  - "semver"
  - "vir-lsp"
---

# VLSP-PLN-0002 — Independent vir-lsp versioning closure verification

## 1. Objective

Xác minh cơ chế SemVer độc lập của `vir-lsp`, version authority, idempotent bump
tool, fail-closed synchronization và native protocol regressions trước khi đóng
`VLSP-ISS-0001`. PLAN chỉ bao phủ audit ngày 2026-10-11, không hồi tố migration
từ 4.0.0 sang 1.3.0 đã hoàn thành trước đó.

## 2. Source Issues

- `VLSP-ISS-0001`.

## 3. Scope

### In Scope

- inspect canonical metadata, policy, source, binary and guidance;
- run synchronization check and native LSP regression;
- verify later issue bumps preserve the independent version lineage;
- create accepted closure evidence and reciprocal links.

### Out of Scope

- bump the version again solely for this paper-only audit;
- change protocol features, editor extension versioning or compiler versioning;
- attribute the historical 1.3.0 migration to this PLAN.

## 4. Current Architecture

`tools/vir-lsp/version.json` is the canonical record and currently reports
1.3.1 owned by the later closed `VLSP-ISS-0002`. Source, README and native
binary report the same version. `tools/vir-lsp/VERSIONING.md` and
`tools/bump_vir_lsp_version.py` define an independent SemVer lifecycle and an
idempotent issue-owned bump workflow. The source ISSUE remains OPEN despite all
acceptance boxes being checked and lacks PLAN/REPORT traceability.

## 5. Proposed Architecture

Không thay đổi release architecture. The target state is verified consistency
across metadata/source/binary/protocol plus a VPS-complete closure chain.

## 6. Design Decisions

### Decision 1 — Do not bump for paper-only closure

**Decision:** Run `--check` and regressions without changing 1.3.1.

**Rationale:** The policy requires a bump for a completed VLSP issue that
changes the shipped server/protocol/binary. This audit changes only papers;
another bump would falsely claim a product change.

**Alternatives considered:** Assign a new patch to VLSP-ISS-0001 retroactively.

**Trade-offs:** The closed issue records its original 1.3.0 migration while the
current product correctly remains at 1.3.1 after VLSP-ISS-0002.

## 7. Implementation Plan

### Phase 1 — Version authority audit

- files/modules: `version.json`, VERSIONING, bump tool, source, README, binary;
- changes: evidence only;
- dependencies: native `bin/vir-lsp`;
- expected result: all current surfaces agree and issue ownership is valid.

### Phase 2 — Regression and closure

- files/modules: native LSP tests and VPS papers;
- changes: create report, evaluate acceptance, close only after validation;
- dependencies: full LSP suite and paper validator;
- expected result: accepted `READY_FOR_CLOSE` report and reciprocal links.

## 8. Compatibility

- No product surface changes in this PLAN.
- Current 1.3.1 remains source/binary/protocol metadata authority.
- The historical 1.3.0 baseline remains recorded in the source ISSUE.

## 9. Migration

Không có migration mới.

## 10. Validation Plan

- `python3 tools/bump_vir_lsp_version.py --check`;
- `./bin/vir-lsp --version`;
- full native `./bin/vir-lsp-test` suite;
- inspect mandatory guidance in `.agents/skills/vir-lang/SKILL.md`;
- `./paper registry --check` and `./paper validate`.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Current 1.3.1 is mistaken for failure to preserve 1.3.0 | Medium | Medium | Verify 1.3.1 is the valid later bump owned by closed VLSP-ISS-0002 |
| Audit triggers a spurious version bump | Low | Medium | Explicitly classify paper-only work as no product change |

## 12. Rollback Strategy

If synchronization or protocol tests fail, keep the issue OPEN/REOPENED and do
not accept the report. The audit does not modify product artifacts, so no
binary rollback is needed.

## 13. Exit Criteria

- [x] metadata/source/binary synchronization check passes;
- [x] full native LSP regression passes;
- [x] every acceptance criterion is evaluated;
- [x] report concludes `READY_FOR_CLOSE`;
- [x] reciprocal links and VPS validation pass.

## 14. Related Papers

- `VLSP-ISS-0001`.
- `VLSP-ISS-0002` only as evidence for the legitimate later 1.3.1 bump.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-11 | Created closure-verification plan for independent vir-lsp SemVer, explicitly excluding a paper-only version bump |
| 2026-10-11 | Completed after version synchronization, 121 native protocol regressions, reciprocal linking and preliminary VPS validation passed |
| 2026-10-11 | Linked VLSP-RPT-0002 |
