# Vir Compiler 2.9.0

Vir 2.9.0 consolidates the language and compiler around one strict, self-hosted toolchain.

## Highlights

- **Enums and tagged unions:** strict qualified variants use dot paths such as `Option.Some(value)` and `Option.None`; legacy `::` qualification is rejected. `case` supports variant payload binders and compiler diagnostics for invalid or non-exhaustive matching.
- **Canonical module paths:** module identities and imports now use one dot-qualified form, mapping deterministically to filesystem paths (for example, `foo.bar` maps to `foo/bar.vri`). Regex and Virgex modules follow the same rule.
- **AI/ML runtime:** the native tensor, autodiff, inference, training, and quantization pipeline is included in the unified standard library and compiler release.
- **Case expressions:** pattern arms use `pattern: statement-list`, default arms use `else` without a colon, empty arms are rejected, and arm boundaries are grammar-driven rather than indentation-driven.
- **Regex and Virgex:** Regex and Virgex now share the unified pattern IR and matching engine while retaining their respective regular-expression and VPS-facing semantics.
- **UFCS:** hardened semantic resolution and lowering across machine-code targets. Entity methods, callable fields, and free-function UFCS calls now follow a deterministic resolution order while preserving receiver and argument evaluation order; invalid visibility, arity, type, pointer, and optional-chaining cases receive strict diagnostics.
- **String interpolation:** hardened lexing, type checking, MIR/LIR lowering, and native/Wasm code generation end to end. Interpolation handles strings, integers (including negative and boundary values), booleans, and `none`, while malformed or unsupported interpolation forms are rejected consistently.
- **Self-hosting:** the promoted `virc` 2.9.0 compiler reached a bit-identical three-stage fixed point and passed post-promotion smoke and focused language tests.

## Release artifacts

- `virc-2.9.0-macos-arm64`: promoted native compiler for Apple Silicon macOS.
- `vir-2.9.0-freeze-macos-arm64.tar.gz`: read-only release freeze containing the standard library, compiler sources, expanded compiler source, manifest, checksums, and a smoke-tested native compiler.

The frozen tree contains its originating Git commit and per-file SHA-256 checksums in `MANIFEST.json` and `SHA256SUMS`.
