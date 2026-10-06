---
name: vir-clean-code
description: >-
  Apply idiomatic Vir source structure, grouped var/let/const declarations,
  readable function signatures, and correct in/ref/out parameter blocks. Use
  for every Vir code creation, edit, refactor, or review.
---

# Clean Vir source

Use after `vir-lang`. Read
[`references/declarations-functions.md`](references/declarations-functions.md)
before changing declarations or function interfaces.

## Binding policy

- Prefer `let` when a binding is initialized once; use `var` only when it is
  reassigned. Use `const` for compile-time constants.
- Group two or more adjacent, related bindings with one `let`, `var`, or
  `const` keyword. Do not repeat the keyword on every line.
- Keep groups cohesive. Do not combine unrelated lifetimes or distant logic
  merely to reduce keyword count.
- Group members are ordered and become available from left to right; do not use
  a later member before its declaration.

## Function interface policy

- One or two short parameters: prefer the parenthesized signature.
- Three or more parameters, a long signature, or mixed ownership modes: prefer
  a block signature with `in`, `ref`, and `out` groups.
- In parentheses, pass-by-value is the default: do not write `in`. `ref name`
  is valid there. Caller-facing `out` slots use the block form.
- In block form write `func name:` with no parameter list, then declare each
  group once and indent its members. Separate parameters by newline or `;`.
- Use `ref` only for intentional mutation of caller-owned state. Use `out`
  parameters for multiple caller-facing outputs; require definite assignment
  on all successful paths. Prefer `out expression` for one natural return.
- Preserve ABI-required explicit types at FFI boundaries.

## Local structure

Keep dependency declarations at the top in canonical module order, then
declarations and exports. Keep early one-line exits only when they remain clear;
do not compress nested ownership or cleanup logic. Use `ensure` for external
resources because arena reset does not close files, sockets, locks, or handles.

## Verification

Compare the edited style with current canonical sources and strict fixtures,
especially `tests/strict_v2/decl_group_positive_e2e.vri` and parameter-group
tests. Compile focused fixtures; do not treat legacy syntax in bootstrap copies
as the preferred style.

