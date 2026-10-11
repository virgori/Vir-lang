---
id: "STLB-ISS-0022"
type: "ISSUE"
domain: "STLB"
title: "The test module lacks a canonical API specification"
status: "OPEN"
severity: "S4"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "test"
  - "test-runner"
  - "developer-tooling"
  - "api-registry"
related:
  issues:
    - "STLB-ISS-0009"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "test"
  - "missing-api-spec"
  - "fanqie"
---

# STLB-ISS-0022 — The test module lacks a canonical API specification

## 1. Summary

The registered `test` standard-library surface has no dedicated
canonical API contract in `stdlib/registry/`. Registration and source
existence therefore do not establish whether the module is public, stable,
experimental, deferred, or internal.

## 2. Context

The stdlib registry contract states that user-facing APIs use one flat
namespace document per public namespace and that the registry is the API
reference source of truth. `stdlib/stdlib.vri:50` registers the module, while
`stdlib/registry/test.md` is absent. `STLB-SPC-0001` requires callers to verify real
exports and forbids inventing APIs.

## 3. Expected Behavior

The module has one explicit, reviewable classification:

- if public, a schema-conforming API registry document defines canonical module
  identity, exports, signatures, ownership, errors, lifecycle, compatibility,
  and tests;
- if internal or deferred, the stdlib registry and supporting documentation say
  so unambiguously and user code is not directed to depend on it.

## 4. Actual Behavior

The source `stdlib/vir/test/test.vri` and module mapping exist, but no dedicated API
contract exists at `stdlib/registry/test.md`. Current source declarations are the only
surface available to a consumer and are not a substitute for a stable contract.

## 5. Reproduction

```sh
rg -n '^test\\s*=' stdlib/stdlib.vri
test -f stdlib/registry/test.md
rg -n 'test|test' stdlib/registry papers/STLB/specs
```

The file-existence check returns nonzero in the 2026-10-09 checkout.

## 6. Evidence

- CONFIRMED: `stdlib/stdlib.vri:50` registers the module identity.
- CONFIRMED: `stdlib/vir/test/test.vri` exists.
- CONFIRMED: `stdlib/registry/test.md` does not exist.
- CONFIRMED: `stdlib/registry/README.md` defines the flat public API registry
  as the API reference source of truth.
- OBSERVED: registration currently communicates more availability than the
  documented support status can justify.
- NOT_VERIFIED: whether the final decision should be public stabilization,
  experimental publication, deferral, or internal-only classification.

## 7. Scope

### Affected

- public/internal classification of `test`;
- canonical namespace and migration map;
- exported signatures, ownership, errors, platform limits, and test contract;
- alignment among source, `stdlib/stdlib.vri`, API registry, and STLB papers.

### Not affected / Unknown

- implementation repair tracked by a separate issue;
- addition of new language syntax;
- API implementation before the contract and support status are reviewed.

## 8. Impact

Projects cannot rely on a versioned assertion, failure, fixture, and runner contract for Vir-native tests.

## 9. Preliminary Analysis

- CONFIRMED: a registered source module exists without a matching namespace
  contract.
- CONFIRMED: this documentation gap is independent from whether the source
  currently compiles.
- HYPOTHESIS: the correct resolution may be to narrow or defer the surface
  instead of standardizing every current declaration.
- NOT_VERIFIED: which existing declarations are safe and compatible enough to
  become public API.

## 10. Acceptance Criteria

- [ ] Decide and record whether `test` is public stable, public
  experimental, deferred, or internal.
- [ ] If public, add a schema-conforming API document at the reviewed canonical
  namespace path and include a migration map from current module/source names.
- [ ] Define exported types and functions, parameter/return contracts,
  ownership and lifetime behavior, error model, resource cleanup, concurrency,
  determinism, and platform constraints where applicable.
- [ ] Align `stdlib/stdlib.vri`, source exports, registry documentation, and
  `STLB-SPC-0001`; remove or label misleading public aliases.
- [ ] Add at least one external consumer contract test plus negative tests for
  documented failures or invalid use.
- [ ] Keep implementation buildability work independently traceable and do not
  mark this issue complete merely because the source compiles.
- [ ] A VPS PLAN and verification REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- `STLB-ISS-0009` tracks the independently reproducible implementation failure.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened from the stdlib API-registry coverage audit |
| 2026-10-09 | Linked STLB-ISS-0009 |
