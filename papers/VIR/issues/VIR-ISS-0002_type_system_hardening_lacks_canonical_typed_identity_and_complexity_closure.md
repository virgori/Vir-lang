---
id: "VIR-ISS-0002"
type: "ISSUE"
domain: "VIR"
title: "Type system hardening lacks canonical typed identity and complexity closure"
status: "TRIAGED"
severity: "S1"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-04"
owners:
  - "language"
  - "compiler"
components:
  - "type-system"
  - "semantic-analysis"
  - "binding-identity"
  - "mir-verifier"
  - "complexity"
  - "tests"
related:
  issues:
    - "VIR-ISS-0001"
    - "VIRC-ISS-0016"
    - "VIRC-ISS-0022"
    - "VIRC-ISS-0023"
    - "VIRC-ISS-0026"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "soundness"
  - "termination"
  - "type-identity"
  - "complexity"
  - "fail-closed"
---

# VIR-ISS-0002 — Type system hardening lacks canonical typed identity and complexity closure

## 1. Summary

The concrete crashes and unsound acceptances named in the type-system prompt
are covered and pass 105/105 in the canonical manifest. The broader architecture
is incomplete: inference retains `TypeKind.Int` fallbacks, compatibility paths
accept unknown declarations, variable type state is keyed by textual names and
searched linearly, generic types are reparsed from strings, and no registered
scaling or typed MIR-metadata mutation gate was found. This ISSUE tracks only
those remaining soundness, identity, termination, and complexity obligations.

## 2. Context

`docs/_legacy/plan/STRICT_TYPE_SYSTEM_SOUNDNESS_TERMINATION_AND_COMPLEXITY_PROMPT.md`
combined earlier work with six new reproducers and a typed-core redesign. The
named reproducers for inference cycles, flux width, composite-to-scalar,
call-return mismatch, unknown cast, and scope shadowing are now registered and
passing. They are regression gates, not unfinished implementation items.

## 3. Expected Behavior

- Every expression, binding, callable, projection, and aggregate resolves to a
  canonical typed identity or controlled poison.
- Unknown, void, unresolved, and poisoned values fail closed and cannot reach
  MIR as integer-like placeholders.
- Scope and cache state use binding/declaration identity, not textual names.
- Hot lookups and graph traversals meet documented O(N) expected or O(N log N)
  worst-case budgets with a reproducible scaling or operation-count gate.
- MIR verification rejects missing or forged type/layout/provenance metadata.

## 4. Actual Behavior

- The current type-safety manifest passes 105/105, including all six required
  reproducers and prior auto-deref/collection regressions.
- `pass5_infer_call_return` still returns `TypeKind.Int` when call return
  resolution fails; tuple/call inference contains other Int/Entity defaults.
- `pass6_ufcs_types_compatible` accepts `declared == 0`; low-level call
  compatibility is also driven by string prefixes and parameter names.
- `pass6_set_var_type` and `pass6_get_var_type` use textual names backed by a
  reverse linear scan of `g_pass6_scoped_var_names`.
- Function/global indices address some former hotspots, but field, scope-name,
  generic-string, and dependency paths remain mixed; no registered
  type-system scaling gate was found.
- No registered mutation gate was found proving rejection of forged typed
  projection, conversion, layout, or provenance metadata.

## 5. Reproduction

```sh
python3 tools/gap_contract_runner.py \
  --manifest tests/type_safety_contract/manifest.tsv \
  --fixtures tests/type_safety_contract \
  --virc ./bin/virc --target macos-arm64
sed -n '100,220p' stdlib/vir/compiler/sem_pass5_infer.vri
sed -n '1200,1470p' stdlib/vir/compiler/sem_pass6_typecheck.vri
sed -n '1890,1950p' stdlib/vir/compiler/sem_pass6_typecheck.vri
rg -n "complexity|scaling|operation.?count" tests tools \
  stdlib/vir/compiler --glob '!stdlib/vir/compiler/virc.vri'
```

The first command proves completed fixes remain green; source inspection exposes
the fallbacks/name cache; the final search shows the missing registered scaling
gate.

## 6. Evidence

- CONFIRMED: the 105-entry type-safety manifest passed 105/105 with 0 FAIL and
  0 BLOCKED on 2026-10-02.
- CONFIRMED: `TYPE-INFER-CYCLE-001`, `TYPE-FLUX-001`, `TYPE-RET-CALL-001`,
  `TYPE-CAST-UNKNOWN-001`, `TYPE-PRIM-WILDCARD-001/002`, and
  `TYPE-SCOPE-SHADOW-002` pass their oracles.
- CONFIRMED: `sem_pass5_infer.vri:120-147` falls back to `TypeKind.Int` for an
  unresolved call result.
- CONFIRMED: `sem_pass6_typecheck.vri:1260-1435` contains non-canonical
  compatibility exceptions, including `declared == 0` UFCS acceptance and
  string/name-based low-level exemptions.
- CONFIRMED: `sem_pass6_typecheck.vri:1898-1930` stores scoped type state as
  parallel name/type vectors and performs a reverse linear scan.
- CONFIRMED: function/global hash buckets exist; this issue does not claim that
  no complexity work has been done.
- CONFIRMED: generic helpers still scan serialized strings, separately tracked
  by VIR-ISS-0001.
- NOT_VERIFIED: asymptotic timing/RSS, multi-target semantic equivalence, typed
  MIR mutation coverage, and final self-host convergence for the full design.

## 7. Scope

### Affected

- canonical type/binding/callee/member identity and poison propagation;
- fail-closed inference, compatibility, conversion, and UFCS behavior;
- scope-keyed state and remaining lookup/traversal hotspots;
- typed MIR verification and complexity/mutation evidence;
- multi-target, O0-O3, and self-host closure for these changes.

### Not affected / Already complete

- all 105 currently passing type-safety contracts;
- the six explicit reproducers now registered in the manifest;
- completed auto-deref, reference return, print, nested-call, aggregate, and
  collection behavior represented by the passing manifest;
- language specification and frozen release trees.

## 8. Impact

Fallback types and name-keyed state are core soundness risks even with the
current reducer matrix green: an unresolved or shadowed value can be
misclassified at an uncovered boundary. Linear rescans also threaten self-host
compile time. Because these paths can admit serious semantic errors, the issue
is S1; no new broad failure is claimed.

## 9. Preliminary Analysis

- CONFIRMED: the prompt's enumerated regressions are fixed and must not be
  duplicated as open work.
- CONFIRMED: the semantic core mixes canonical symbol lookup with textual
  caches and permissive fallbacks.
- OBSERVED: targeted indexing reduced several obvious global scans.
- HYPOTHESIS: canonical descriptors and binding-keyed environments can be
  introduced incrementally with poison-aware adapters at old boundaries.
- NOT_VERIFIED: the exact remaining worst-case exponent and reachability of
  each fallback from user modules after prior passes.

## 10. Acceptance Criteria

- [ ] Unknown call, cast, field, index, projection, and generic types produce
  controlled poison, never `Int`, Entity, machine word, or type ID 0.
- [ ] Compatibility returns exact/conversion/incompatible/poisoned with typed
  conversion metadata; UFCS and low-level paths cannot bypass it by name.
- [ ] Type, inference, assignment, and borrow state use canonical binding IDs.
- [ ] Generic, callable, aggregate, reference, tensor, and flux identities keep
  structural metadata through semantic analysis and MIR.
- [ ] A typed MIR verifier and mutation suite reject forged metadata and
  artifact emission on error.
- [ ] A registered corpus at three or more sizes demonstrates the complexity
  budget with stable timing or operation counters.
- [ ] Existing 105/105 contracts remain green at supported optimization levels;
  semantic negatives are target-independent and produce no artifacts.
- [ ] Relevant memory, multi-target, sync, and self-host evidence is recorded
  in a REPORT.
- [ ] A VPS PLAN links this ISSUE before implementation is claimed complete.

## 11. Related Papers

### Issues

- VIR-ISS-0001 — overlapping canonical generic type identity debt.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Created and triaged after 105/105 verification; retained only architectural, verifier, complexity, and closure gaps |
| 2026-10-03 | Linked VIRC-ISS-0016 |
| 2026-10-04 | Linked VIRC-ISS-0022 |
| 2026-10-04 | Linked VIRC-ISS-0023 |
| 2026-10-04 | Linked VIRC-ISS-0026 |
