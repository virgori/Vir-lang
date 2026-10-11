---
id: "STLB-ISS-0017"
type: "ISSUE"
domain: "STLB"
title: "The metrics module references an unavailable float conversion function"
status: "OPEN"
severity: "S2"
priority: "P2"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "observability"
  - "metrics"
  - "formatting"
  - "exports"
related:
  issues:
    - "STLB-ISS-0029"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "metrics"
  - "compile-failure"
  - "observability"
---

# STLB-ISS-0017 — The metrics module references an unavailable float conversion function

## 1. Summary

The registered `observability.metrics` standard-library module does not pass the active
compiler check. The first confirmed failure is `E2002` in
`stdlib/vir/observability/metrics.vri:197`, so the module is not a usable release-qualified
dependency.

## 2. Context

`stdlib/stdlib.vri:376` publishes the module identity and maps it to the active source.
This issue records implementation buildability only; API design or missing
canonical documentation is tracked separately where applicable.

## 3. Expected Behavior

- `observability.metrics` passes the active compiler's parser, name, type, and ownership
  checks through its registered identity.
- Exported behavior is callable from an external stdlib consumer.
- Focused positive and negative tests cover the repaired boundary.

## 4. Actual Behavior

The implementation references undefined `float_to_str` while rendering metric values.

## 5. Reproduction

```sh
rg -n '^observability\.metrics\\s*=' stdlib/stdlib.vri
./bin/virc stdlib/vir/observability/metrics.vri --check --json
```

Run from the repository root with the active `./bin/virc` on 2026-10-09.

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri:376` registers the affected module.
- CONFIRMED: the command exits nonzero with `E2002` and points to
  `stdlib/vir/observability/metrics.vri:197`.
- OBSERVED: the repository-wide module/resolver suite passes independently, so
  this reproduction is localized to the module or its direct dependencies.
- NOT_VERIFIED: downstream failures hidden by the first parser/name/type error
  and compatibility with unsupported targets.

## 7. Scope

### Affected

- `observability.metrics` source, exports, dependencies, and focused consumers;
- regression coverage for the reported diagnostic;
- registry accuracy if the module cannot remain public.

### Not affected / Unknown

- unrelated stdlib modules;
- new Vir language semantics;
- performance work before correctness and buildability are restored.

## 8. Impact

The registered metrics exporter cannot be compiled for application observability.

## 9. Preliminary Analysis

- CONFIRMED: the registered source fails the current compiler.
- CONFIRMED: the failure is reproducible without changing compiler or stdlib
  source.
- HYPOTHESIS: the immediate failure is migration debt against current syntax or
  exported dependency names, not a resolver defect.
- NOT_VERIFIED: the complete set of semantic and runtime defects after the
  first failure is repaired.

## 10. Acceptance Criteria

- [ ] The registered module passes `./bin/virc stdlib/vir/observability/metrics.vri --check --json`
  with zero diagnostics on a newly built active compiler.
- [ ] Public exports resolve from a consumer outside the module source
  directory through `stdlib/stdlib.vri`.
- [ ] A focused regression test fails before the repair and passes afterward,
  including the relevant error or ownership path.
- [ ] The repair uses current Vir syntax and explicitly exported dependency
  names; it does not rely on selective-import fail-open behavior.
- [ ] Existing module/resolver and relevant stdlib test groups remain green.
- [ ] Any API contract change is linked to the applicable API specification
  issue rather than being decided implicitly in this implementation issue.
- [ ] A VPS PLAN and verification REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- See front matter for linked API-contract work, when applicable.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from the registered-stdlib compile audit with a direct compiler reproduction |
| 2026-10-09 | Linked STLB-ISS-0029 |
