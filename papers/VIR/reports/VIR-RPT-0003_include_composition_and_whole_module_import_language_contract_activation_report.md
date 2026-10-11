---
id: "VIR-RPT-0003"
type: "REPORT"
domain: "VIR"
title: "Include composition and whole-module import language contract activation report"
status: "ACCEPTED"
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
    - "VIR-ISS-0017"
  plans:
    - "VIR-PLN-0003"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "module-composition"
  - "module-namespace"
  - "spec-activation"
---

# VIR-RPT-0003 — Include composition and whole-module import language contract activation report

## 1. Executive Summary

The language decision in VIR-ISS-0017 is complete. `VIR-SPC-0021` v1.0.0 is
ACTIVE and distinguishes alias-free same-module composition through
`include M` from export-limited namespace consumption through `import M [as
A]`. All four active parent specifications are synchronized. Compatibility
audit found no production `.vri` use of include aliases or whole-module imports;
one explicit compatibility fixture remains as evidence for the separate
compiler conformance issue `VIRC-ISS-0065`.

## 2. Source Issues

- VIR-ISS-0017

## 3. Source Plans

- VIR-PLN-0003

## 4. Implementation Summary

- Activated `VIR-SPC-0021` v1.0.0 as the focused dependency-boundary contract.
- Revised `VIR-SPC-0006` to v3.4.0 and `VIR-SPC-0014` to v3.3.0.
- Revised paired language specs `VIR-SPC-0017`/`0018` to v3.6.0 with
  English/Vietnamese normative parity.
- Removed include aliases and include-created namespaces from canonical grammar.
- Defined duplicate fragment declarations as order-independent errors and
  preserved explicit-export-only publication for the composed module.
- Separated language activation from compiler/LSP conformance and retained
  `VIRC-ISS-0065` as the durable implementation owner.
- Updated the module skill so agents do not generate `include M as A` or infer
  namespaces from current source-splicing behavior.

## 5. Changes by Component

### `papers/VIR/specs/VIR-SPC-0021_*`

- change: promoted REVIEW v0.3.0 to ACTIVE v1.0.0 and recorded the completed
  compatibility audit;
- reason: establish a focused canonical contract independent of implementation;
- impact: language semantics are now stable and discoverable.

### Parent language specifications

- change: synchronized `VIR-SPC-0006`, `0014`, `0017`, and `0018`;
- reason: remove the prior contradiction that both include and import created
  module namespaces;
- impact: one grammar and semantic model across all ACTIVE papers.

### `.agents/skills/vir-stdlib-modules/SKILL.md`

- change: made include composition and the `VIRC-ISS-0065` caveat explicit;
- reason: prevent agents from treating compatibility behavior as language law;
- impact: future code generation selects include/import by semantic role.

## 6. Deviations from Plan

No material deviations from the approved plan.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| Production include-alias audit | PASS | zero matches under `compiler/src`, `stdlib/vir`, and `tools` |
| Fixture include-alias audit | PASS | exactly one compatibility fixture under `tests/modules` |
| Production whole-module-import audit | PASS | zero matches under `compiler/src`, `stdlib/vir`, and `tools` |
| Parent-SPEC contradiction search | PASS | no positive include-namespace/alias rule remains |
| `./paper registry --check` | PASS | production registry synchronized |
| `./paper validate` | PASS | 284 production papers and 3 examples after report registration |

### Regression

No compiler regression claim is made. The accepted language decision
deliberately leaves current include-alias acceptance and whole-import source
flattening as known nonconformance evidence for `VIRC-ISS-0065`.

### Conformance

The ACTIVE focused and parent specifications agree on three dependency forms:
`include M`, `import M [as A]`, and `import X from M`. They reject `include M
as A` and `import from M`, and distinguish implementation composition from
independent exported API consumption.

## 8. Acceptance Criteria

- [x] Dedicated VIR history record exists for the 2026-10-10 grammar revision.
- [x] Stable focused SPEC defines grammar, scope, visibility, identity, and
  migration.
- [x] SPEC separates current implementation evidence from language semantics.
- [x] Duplicate included declarations are order-independent compile errors.
- [x] Dependency multiplicity is separated from module initialization policy.
- [x] Include-alias compatibility usage was audited with a migration/rejection
  path linked to `VIRC-ISS-0065`.
- [x] Focused SPEC passed REVIEW and is now ACTIVE.
- [x] All active parent specs are synchronized.
- [x] Compiler/LSP conformance remains explicitly owned by `VIRC-ISS-0065`.

## 9. Known Limitations

- Compiler and LSP conformance is not implemented or verified by this report.
- `tests/modules/test_multi_include_alias_compat_positive.vri` remains accepted
  by the current compiler although its syntax is now noncanonical; it must be
  migrated or inverted into a rejection fixture under `VIRC-ISS-0065`.
- Module initialization timing, ordering, failure, and cycle semantics remain
  intentionally unspecified pending a separate language decision.

## 10. Remaining Work

Implementation and tooling work remains in `VIRC-ISS-0065`; no additional VIR
language issue is required for this decision.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- `VIR-ISS-0017` — source language decision record.
- `VIR-PLN-0003` — activation and synchronization plan.
- `VIR-SPC-0006`, `0014`, `0017`, `0018` — synchronized parent specs.
- `VIR-SPC-0021` — ACTIVE focused contract.
- `VIRC-ISS-0065` — separate compiler/LSP conformance owner.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Accepted after compatibility audit, parent-SPEC synchronization, focused SPEC activation, registry synchronization, and VPS validation |
