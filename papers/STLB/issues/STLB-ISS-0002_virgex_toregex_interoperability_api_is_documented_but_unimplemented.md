---
id: "STLB-ISS-0002"
type: "ISSUE"
domain: "STLB"
title: "Virgex toRegex interoperability API is documented but unimplemented"
status: "OPEN"
severity: "S3"
priority: "P2"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "stdlib"
components:
  - "virgex"
  - "regex"
  - "pattern-ir"
  - "interoperability"
related:
  issues:
    - "VIR-ISS-0010"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "virgex"
  - "vps"
  - "regex"
  - "interop"
  - "missing-api"
---

# STLB-ISS-0002 — Virgex toRegex interoperability API is documented but unimplemented

## 1. Summary

The standard-library registry documents `virgex.toRegex` as the public
interoperability operation for converting VPS source to traditional regex, but
the active `VirgexNamespace` exposes no such method and no implementation exists
in the current source tree. A valid public call therefore fails semantic
resolution instead of returning the documented `Result`.

## 2. Context

Virgex and Regex are separate syntax frontends that lower directly to the shared
Pattern IR and Thompson NFA. They intentionally do not translate through each
other during ordinary compilation. `virgex.toRegex` is a distinct
interoperability/debugging API and therefore needs an explicit target dialect,
escaping contract, failure policy, and semantic-equivalence tests.

`stdlib/registry/virgex.md` currently marks the operation incomplete and states
that a stub echoes its input. Direct source inspection found neither that stub
nor a `toRegex` namespace method, so the registry's description is stale in
addition to the missing implementation.

## 3. Expected Behavior

- `virgex.toRegex` is callable through the public `virgex` namespace with the
  signature and `Result`-based failure contract published by the registry.
- Every construct in the active VPS 2.1 grammar either translates to a regex
  expression with equivalent matching semantics or returns an explicit error.
- The target regex dialect and its byte/Unicode semantics are documented; the
  API must not silently emit syntax whose meaning depends on an unspecified
  external dialect.
- Invalid VPS and unsupported future constructs fail closed rather than being
  returned unchanged or partially translated.

## 4. Actual Behavior

`VirgexNamespace` ends after `tokenize` and has no `toRegex` method. A call to
`virgex.toRegex("@0!1")` fails with compiler diagnostic `E3021` for an unresolved
UFCS member. Repository search finds no `virgex_to_regex`, `toRegex`, or
`to_regex` implementation outside the registry documentation.

## 5. Reproduction

Probe source:

```vir
include virgex

func main:
    let result = virgex.toRegex("@0!1")
    print(result)
end.
```

Command executed from the repository root on 2026-10-08 with
`virc 2026.1.2`:

```sh
./bin/virc /private/tmp/virgex_toregex_probe.vri --check --json
```

Observed result:

```text
success: false
code: E3021
message: Unresolved UFCS member: no entity method, callable field, or free function
exit status: 1
```

## 6. Evidence

- `CONFIRMED`: the reproduction fails with `E3021` at the `toRegex` member.
- `CONFIRMED`: `stdlib/vir/virgex/virgex.vri:614-663` defines the complete
  active namespace surface and contains no `toRegex` method.
- `CONFIRMED`: `stdlib/registry/virgex.md:621-658` publishes the intended API,
  labels it incomplete, and warns callers not to rely on it.
- `CONFIRMED`: `stdlib/vir/pattern/ir.vri:2-8` states that Virgex and Regex lower
  directly to shared Pattern IR without cross-syntax string conversion.
- `OBSERVED`: no current test exercises VPS-to-regex translation or differential
  equivalence of translated output.

## 7. Scope

### Affected

- Public `virgex` namespace completeness and registry accuracy.
- VPS-to-regex interoperability and debugging workflows.
- VPS lexer/parser reuse needed to validate the complete input before
  translation.

### Not affected / Unknown

- Normal `virgex.compile` and `regex.compile` do not require string translation
  and are not blocked by this missing API.
- Unicode/CJK extensions beyond active VPS 2.1 are not part of the initial
  translation surface; their future mapping is tracked separately.
- `NOT_VERIFIED`: which external regex dialects, if any, should be targets in
  addition to Vir's own Regex frontend.

## 8. Impact

Users cannot obtain the documented regex representation for interoperability,
inspection, or migration. The stale registry also creates a false impression
that an identity-returning stub exists, while real code fails at compile time.
This is scoped standard-library incompleteness with a direct workaround—write
the regex manually—so severity is S3 and planned priority is P2.

## 9. Preliminary Analysis

- `CONFIRMED`: no callable API or implementation exists in the active source.
- `CONFIRMED`: active VPS 2.1 has a finite grammar covering anchors, atoms,
  quantifiers, optional expressions, groups/alternation, literals, spaces, and
  single/block escapes.
- `HYPOTHESIS`: translation can reuse the VPS token/parse representation and
  emit the subset accepted by the Vir Regex frontend, but the implementation
  architecture belongs in a PLAN after the target dialect is fixed.
- `NOT_VERIFIED`: whether atom extraction groups should become capturing or
  non-capturing regex groups in serialized output; this must be decided against
  the documented operation-level equivalence contract.

## 10. Acceptance Criteria

- [ ] Specify the target regex dialect, byte/Unicode model, escaping rules,
      anchor behavior, and capture policy for `virgex.toRegex`.
- [ ] Expose `virgex.toRegex` through the public namespace with the documented
      `Result`-based failure contract; the minimal reproduction compiles.
- [ ] Translate every construct in active VPS 2.1: literals, standard and
      negated atoms, digit-range atoms, all quantifier forms, prefix optional,
      groups and alternation, leading/trailing anchors, literal-space tokens,
      and single/block escapes.
- [ ] Reject malformed or untranslatable VPS without identity echo, partial
      output, panic, or silent token loss.
- [ ] Add differential tests that compile the emitted regex and compare
      full-match/search behavior with the source VPS over positive, negative,
      empty, escaped-symbol, and extraction-sensitive fixtures.
- [ ] Update `stdlib/registry/virgex.md` to describe the implemented behavior
      and remove stale stub claims.
- [ ] Run the focused Virgex/Regex equivalence and parser suites, then
      `./paper registry --check` and `./paper validate`.

## 11. Related Papers

### Issues

- `VIR-ISS-0010` — Future Unicode-scalar and CJK-aware VPS semantics require
  an explicit translation policy when that version becomes active.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened with compiler reproduction, source/registry mismatch evidence, and measurable VPS 2.1 translation criteria |
| 2026-10-08 | Linked VIR-ISS-0010 |
