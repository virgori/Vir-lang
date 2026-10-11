---
id: "STLB-ISS-0003"
type: "ISSUE"
domain: "STLB"
title: "The public JSON module fails ownership checking"
status: "OPEN"
severity: "S1"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "json"
  - "serialization"
  - "ownership"
  - "public-api"
  - "tests"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "json"
  - "compile-failure"
  - "ownership"
  - "fanqie"
---

# STLB-ISS-0003 — The public JSON module fails ownership checking

## 1. Summary

The registered `json` standard-library module does not pass the active
compiler check. The first confirmed failure is `E5001` in
`stdlib/vir/data/json.vri:198`, so the module is not a usable release-qualified
dependency.

## 2. Context

`stdlib/stdlib.vri:58 and :332` publishes the module identity and maps it to the active source.
This issue records implementation buildability only; API design or missing
canonical documentation is tracked separately where applicable.

## 3. Expected Behavior

- `json` passes the active compiler's parser, name, type, and ownership
  checks through its registered identity.
- Exported behavior is callable from an external stdlib consumer.
- Focused positive and negative tests cover the repaired boundary.

## 4. Actual Behavior

The direct module check reports 64 ownership diagnostics; the first is a use of a moved value at line 198.

## 5. Reproduction

```sh
rg -n '^json\\s*=' stdlib/stdlib.vri
./bin/virc stdlib/vir/json.vri --check --json
```

Run from the repository root with the active `./bin/virc` on 2026-10-09.

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri:58 and :332` registers the affected module.
- CONFIRMED: the command exits nonzero with `E5001` and points to
  `stdlib/vir/data/json.vri:198`.
- OBSERVED: the repository-wide module/resolver suite passes independently, so
  this reproduction is localized to the module or its direct dependencies.
- NOT_VERIFIED: downstream failures hidden by the first parser/name/type error
  and compatibility with unsupported targets.

## 7. Scope

### Affected

- `json` source, exports, dependencies, and focused consumers;
- regression coverage for the reported diagnostic;
- registry accuracy if the module cannot remain public.

### Not affected / Unknown

- unrelated stdlib modules;
- new Vir language semantics;
- performance work before correctness and buildability are restored.

## 8. Impact

Fanqie and other consumers cannot use the documented stable JSON parser/stringifier through the canonical module.

## 9. Preliminary Analysis

- CONFIRMED: the registered source fails the current compiler.
- CONFIRMED: the failure is reproducible without changing compiler or stdlib
  source.
- HYPOTHESIS: the immediate failure is migration debt against current syntax or
  exported dependency names, not a resolver defect.
- NOT_VERIFIED: the complete set of semantic and runtime defects after the
  first failure is repaired.

## 10. Acceptance Criteria

- [ ] The registered module passes `./bin/virc stdlib/vir/json.vri --check --json`
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
