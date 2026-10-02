---
id: "VIR-SPC-0010"
type: "SPEC"
domain: "VIR"
title: "Vir Programming Language"
status: "ACTIVE"
version: "2.0.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-02"
owners:
  - "VIR"
components: []
aliases:
  - "docs/ai-spec/vir-lang/SKILL.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0010 — Vir Programming Language

Vir is a programming language developed by Virgori Labs.

## Spec binding

- Language: Vir **v2.0**
- Sources: `VIR-SPC-0018`, `VIR-SPC-0017`, and compiler under `stdlib/vir/`
- Extension: **`.vri`**

## Spec freeze (critical)

**Do not create, edit, delete, or “improve” the Vir language specification** unless
the user **explicitly** asks to change the spec in that turn (e.g. “sửa spec”,
“update language spec”, “đổi AI spec”).

Frozen unless explicitly requested: canonical SPEC papers under
`papers/VIR/specs/` and `papers/STLB/specs/`, plus skill mirrors that define
language rules.

Allowed without a spec request: `stdlib/vir/`, tests, tools, compiler, non-spec
docs. If a feature is missing from the spec, **state the gap** — do not silently
amend the spec to match code.

## Rules

When writing Vir code:

1. Follow Vir syntax exactly.
2. Do not infer syntax from Rust, Go, C, JavaScript, or Python.
3. Do not invent standard-library APIs.
4. Consult the supplied Vir references when uncertain.
5. Prefer documented Vir idioms over equivalents from other languages.
6. If a requested feature is unsupported by Vir, state that explicitly.
7. Do not modify the language spec (paths above) unless the user explicitly
   requested a spec change.

## Scalar power

`^` is right-associative. For integer operands, a non-negative exponent
returns an integer; a negative exponent is valid and returns a binary64
`float` reciprocal (`2^-3 == 0.125`). Incomplete forms such as `2^` and `2^-`
are syntax errors.

## References

- `VIR-SPC-0015` — lexical and syntax rules
- `VIR-SPC-0016` — Vir type system
- `VIR-SPC-0013` — function declarations and calls
- `VIR-SPC-0011` — conditions, loops and branching
- `VIR-SPC-0014` — imports and modules
- `VIR-SPC-0012` — throw / ensure / revert
- `STLB-SPC-0001` — standard library

## Examples

- `docs/ai-spec/vir-lang/examples/basics.vri`
- `docs/ai-spec/vir-lang/examples/algorithms.vri`
- `docs/ai-spec/vir-lang/examples/common-patterns.vri`

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/SKILL.md` and assigned stable ID `VIR-SPC-0010` |
