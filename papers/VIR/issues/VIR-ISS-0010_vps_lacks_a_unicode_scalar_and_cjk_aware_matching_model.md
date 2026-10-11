---
id: "VIR-ISS-0010"
type: "ISSUE"
domain: "VIR"
title: "VPS lacks a Unicode scalar and CJK-aware matching model"
status: "OPEN"
severity: "S4"
priority: "P2"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "virgex"
  - "vps"
  - "pattern-engine"
  - "unicode"
  - "cjk"
related:
  issues:
    - "STLB-ISS-0002"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "vps"
  - "utf-8"
  - "unicode"
  - "cjk"
  - "language-design"
---

# VIR-ISS-0010 — VPS lacks a Unicode scalar and CJK-aware matching model

## 1. Summary

VPS 2.1 normatively matches bytes and limits standard atoms to ASCII ranges.
It can match a literal CJK string only as its encoded byte sequence; it cannot
express one Unicode scalar, a Unicode property, or a CJK script/class as one
matching unit. A versioned language design and corresponding Pattern engine
capability are required before Virgex can claim UTF-8/CJK-aware matching.

## 2. Context

`VIR-SPC-0019` deliberately defines the current VPS grammar as byte-oriented.
Each atom consumes exactly one byte, non-ASCII literals are sequences of their
UTF-8 bytes, and there is no normalization or case-folding. The shared Pattern
IR and Thompson NFA preserve those byte semantics.

The standard-library Unicode registry identifies `unicode` as the single source
of truth for UTF-8 decoding and scalar validity, while script predicates such
as CJK, Hangul, Hiragana, and Katakana belong to `char`. Both registries remain
at the `pre-UCD` version pin, so no Unicode-version conformance claim is
currently available for a pattern extension.

## 3. Expected Behavior

- A future, versioned VPS contract can match valid UTF-8 by Unicode scalar
  without splitting one scalar into independent byte matches.
- The contract provides an explicit, readable way to match CJK and related
  scripts/properties with coverage tied to the repository's pinned Unicode
  Character Database version.
- Existing byte-oriented VPS 2.1 patterns retain defined compatibility; the
  migration or opt-in boundary between byte and scalar semantics is explicit.
- Malformed UTF-8, match offsets, quantifiers, negation, normalization, and
  case-folding have specified behavior rather than platform-dependent results.

## 4. Actual Behavior

Literal `|你|` matches `"你"` because the three UTF-8 bytes are compiled as a
three-literal sequence. By contrast, `| @-0 |` does not full-match `"你"`
because the atom consumes one byte, while `| @-0!3 |` does match it because the
same Unicode scalar occupies three bytes in UTF-8. Thus repetition and class
semantics observe encoding width rather than Unicode scalar identity.

## 5. Reproduction

Probe source:

```vir
include virgex

func main:
    var literal = virgex.compile("|你|")
    var one_byte = virgex.compile("| @-0 |")
    var three_bytes = virgex.compile("| @-0!3 |")
    if virgex.fullMatch(literal, "你") do print(1) else print(0) end
    if virgex.fullMatch(one_byte, "你") do print(1) else print(0) end
    if virgex.fullMatch(three_bytes, "你") do print(1) else print(0) end
end.
```

Commands executed from the repository root on 2026-10-08 with
`virc 2026.1.2`:

```sh
./bin/virc /private/tmp/virgex_cjk_probe.vri \
  -o /private/tmp/virgex_cjk_probe -q
/private/tmp/virgex_cjk_probe
```

Observed output:

```text
1
0
1
```

## 6. Evidence

- `CONFIRMED`: the reproduction proves literal CJK byte-sequence matching and
  byte-counted atom repetition on the current compiler.
- `CONFIRMED`: `VIR-SPC-0019` §5 states that VPS 2.1 atoms test exactly one byte,
  standard atoms are ASCII-only, and no Unicode normalization/case-folding is
  performed.
- `CONFIRMED`: the SPEC formal grammar admits only `Az0`, `Az`, `AZ`, `az`, `0`,
  and two-digit ASCII digit ranges as atom names.
- `CONFIRMED`: `stdlib/registry/pattern.md` declares byte-oriented UTF-8 match
  semantics for the shared Pattern engine.
- `CONFIRMED`: `stdlib/registry/unicode.md` owns UTF-8 decoding and currently
  uses the `pre-UCD` pin; `stdlib/registry/char.md` owns CJK/Hangul/Kana script
  predicates.
- `OBSERVED`: existing multilingual Virgex tests primarily exercise ASCII
  romanization rules and do not establish Unicode-property matching.

## 7. Scope

### Affected

- Normative VPS matching units and atom grammar in `VIR-SPC-0019`.
- Virgex lexer/parser and lowering.
- Shared Pattern IR/NFA matching units, captures, offsets, iteration, replace,
  split, and tokenize behavior.
- Unicode/character-property integration and CJK conformance tests.

### Not affected / Unknown

- Exact UTF-8 literal matching already works as byte-sequence matching and must
  not be misreported as absent.
- The traditional Regex frontend is not automatically changed by this ISSUE;
  any shared-engine semantic change must preserve or explicitly version its
  byte-oriented contract.
- Grapheme-cluster matching, canonical normalization, locale tailoring, and
  full Unicode case-folding are not implied by scalar-aware matching; their
  inclusion remains a design decision.
- `NOT_VERIFIED`: the final VPS spelling for Unicode properties or script atoms.

## 8. Impact

VPS cannot currently express robust validation or search rules such as “one CJK
character,” “three Han scalars,” or mixed ASCII/CJK classes independently of
UTF-8 encoding width. This limits multilingual rules and makes quantifier
meaning surprising for users who view a Vir `string` as text. The current
behavior is conforming to VPS 2.1 rather than a correctness regression, so the
issue is an S4 language-extension proposal with P2 scheduling intent.

## 9. Preliminary Analysis

- `CONFIRMED`: implementing UTF-8/CJK-aware atoms without revising
  `VIR-SPC-0019` would conflict with active normative byte semantics.
- `CONFIRMED`: the repository already assigns UTF-8 codec ownership to
  `unicode` and script-property ownership to `char`; Virgex should not invent
  independent ad-hoc Unicode tables.
- `HYPOTHESIS`: a versioned scalar-aware mode can preserve Thompson-NFA
  execution and byte offsets while decoding one scalar before each class
  transition, but the architecture and performance proof belong in a PLAN.
- `NOT_VERIFIED`: whether compatibility should use a new VPS version, an
  explicit mode, new atom names, or a separate frontend namespace.
- `NOT_VERIFIED`: the memory/performance cost of UCD-backed property transitions
  and supplementary-plane coverage.

## 10. Acceptance Criteria

- [ ] Revise `VIR-SPC-0019` through its versioned SPEC lifecycle to define the
      UTF-8 scalar matching model, grammar additions, and compatibility boundary
      with VPS 2.1 byte semantics.
- [ ] Pin and use one Unicode Character Database version through the existing
      `unicode`/`char` single-source-of-truth policy; do not claim conformance
      from partial hand-written ranges.
- [ ] Specify CJK-related property coverage precisely, including whether Han,
      Hangul, Hiragana, Katakana, compatibility ideographs, and supplementary
      planes are separate or combined match classes.
- [ ] Specify malformed UTF-8 handling, scalar quantifier behavior, negative
      classes, captures, match offsets, replacement boundaries, normalization,
      and case-folding scope.
- [ ] Implement scalar-aware Pattern IR/NFA matching without splitting valid
      multi-byte scalars and without introducing catastrophic backtracking.
- [ ] Add conformance tests for ASCII compatibility, mixed ASCII/CJK text,
      BMP and supplementary Han, Hangul, Hiragana, Katakana, repeated and
      negated classes, invalid UTF-8, extraction, replacement, and byte-offset
      reporting.
- [ ] Preserve the existing focused Virgex/Regex equivalence suite for the
      VPS 2.1 compatibility surface and add explicit migration tests for the
      selected Unicode mode/version.
- [ ] Update the Virgex, Pattern, Unicode, and Char registries, then run
      `./paper registry --check` and `./paper validate`.

## 11. Related Papers

### Issues

- `STLB-ISS-0002` — `virgex.toRegex` must define how future Unicode-aware VPS
  constructs map or fail when serialized to its target regex dialect.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened with executable UTF-8/CJK byte-semantics evidence and versioned language-extension criteria |
| 2026-10-08 | Linked STLB-ISS-0002 |
