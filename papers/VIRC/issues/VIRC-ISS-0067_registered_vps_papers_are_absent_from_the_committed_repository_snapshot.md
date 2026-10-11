---
id: "VIRC-ISS-0067"
type: "ISSUE"
domain: "VIRC"
title: "Registered VPS papers are absent from the committed repository snapshot"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
components:
  - "paper-tooling"
  - "repository-governance"
related:
  issues:
    - "VIRC-ISS-0004"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "vps"
  - "registry"
  - "clean-checkout"
  - "version-control"
---

# VIRC-ISS-0067 — Registered VPS papers are absent from the committed repository snapshot

## 1. Summary

The working-tree VPS registry validates, but the committed repository snapshot
does not contain every production paper named by that registry state. The
repository therefore cannot reproduce paper validation from a clean checkout
until the owning paper changes are reviewed and committed together.

## 2. Context

An independent closure audit of `VIRC-ISS-0004` extracted commit `40746bb5`
with `git archive` and ran the canonical paper validator. That clean snapshot
reported 86 path, registry, and reciprocal-link errors while the current
working tree passed. On 2026-10-10, the working tree contained 71 untracked
files below `papers/`, alongside many modified and newly registered papers from
multiple unrelated issue lifecycles.

## 3. Expected Behavior

- Every production entry in `papers/REGISTRY.yaml` is present in the committed
  repository tree.
- `./paper registry --check` and `./paper validate` pass after extracting the
  commit into a clean directory with no untracked-file overlay.
- Paper history from unrelated issues is reviewed and committed by its owner;
  one issue closure must not silently stage or commit all other working-tree
  changes.

## 4. Actual Behavior

The current working tree passes VPS validation with 261 production papers and
3 examples, but 71 files under `papers/` are untracked. Commit `40746bb5`
therefore cannot reproduce the working-tree registry and reciprocal-link
closure.

## 5. Reproduction

```sh
git status --porcelain --untracked-files=all papers
git archive HEAD | tar -x -C <empty-directory>
cd <empty-directory>
./paper registry --check
./paper validate
```

## 6. Evidence

- CONFIRMED: `./paper validate` passes in the working tree with 261 production
  papers and 3 examples.
- CONFIRMED: `./paper registry --check` reports the working-tree registry is
  synchronized.
- CONFIRMED: `git status --porcelain --untracked-files=all papers` reports 71
  untracked paper-tree files on 2026-10-10.
- CONFIRMED: the clean archive of `40746bb5` reports 86 VPS errors because
  referenced papers and reciprocal links are absent from that commit.

## 7. Scope

### Affected

- version-control completeness of production VPS papers;
- registry/filesystem parity in clean snapshots;
- reproducible paper validation for release and issue closure.

### Not affected / Unknown

- FFI semantics and backend behavior are not affected.
- Compiler `min` and `full` runtime/compile contracts are not affected.
- The correct ownership and commit grouping for unrelated paper changes is not
  decided by this issue.

## 8. Impact

Release and governance evidence cannot be reproduced from the current commit.
This blocks claims that rely specifically on clean-checkout VPS validation, but
does not invalidate focused compiler evidence produced from the current tree.

## 9. Preliminary Analysis

- CONFIRMED: the discrepancy is between Git-tracked snapshot contents and the
  validated working-tree paper set.
- OBSERVED: the missing files belong to many independent VIR, VIRC, and STLB
  lifecycles, so bulk-committing them as part of `VIRC-ISS-0004` would mix
  unrelated ownership and evidence.
- HYPOTHESIS: reviewing and committing the pending paper batches with the
  synchronized registry will make clean-snapshot validation pass.
- NOT_VERIFIED: which pending paper batches are ready for commit or should be
  split further.

## 10. Acceptance Criteria

- [ ] Every production paper referenced by the committed registry is tracked
  in the same commit.
- [ ] A clean archive or checkout of that commit passes
  `./paper registry --check` and `./paper validate` without overlays.
- [ ] Unrelated paper batches retain correct ownership, reciprocal links, and
  revision history during commit preparation.
- [ ] Evidence records the validated commit identifier and exact paper counts.

## 11. Related Papers

### Issues

- `VIRC-ISS-0004`

### Plans

- None.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Created from the clean-snapshot VPS failure found during the independent VIRC-ISS-0004 closure audit |
| 2026-10-10 | Linked VIRC-ISS-0004 |
