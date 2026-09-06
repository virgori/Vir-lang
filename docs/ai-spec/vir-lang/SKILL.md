# Vir Programming Language

Vir is a programming language developed by Virgori Labs.

## Spec binding

- Language: Vir **v2.0**
- Sources: `docs/vir_language_spec_v2.0_vi.md`, compiler under `stdlib/vir/`
- Extension: **`.vri`**

## Rules

When writing Vir code:

1. Follow Vir syntax exactly.
2. Do not infer syntax from Rust, Go, C, JavaScript, or Python.
3. Do not invent standard-library APIs.
4. Consult the supplied Vir references when uncertain.
5. Prefer documented Vir idioms over equivalents from other languages.
6. If a requested feature is unsupported by Vir, state that explicitly.

## References

- syntax.md — lexical and syntax rules
- types.md — Vir type system
- functions.md — function declarations and calls
- control-flow.md — conditions, loops and branching
- modules.md — imports and modules
- errors.md — throw / ensure / revert
- stdlib.md — standard library

## Examples

- examples/basics.vri
- examples/algorithms.vri
- examples/common-patterns.vri
