# Vir Compiler 3.2.0

Vir 3.2.0 promotes the strict self-hosted compiler after the register, mold,
dictionary, numeric-cast, module-ordering, and backend-correctness work completed
since 2.9.0.

## Highlights

- **Self-hosting fixed point:** the promoted macOS ARM64 compiler reaches a
  bit-identical Stage 2/Stage 3 fixed point after deterministic signing.
- **Regression hardening:** the exhaustive release suite passes 628/628 tests,
  including higher-order calls, spill pressure, dictionaries, imports, casts,
  power expressions, packed molds, and register boundaries.
- **Backend correctness:** fixes preserve live values across calls and prevent
  dynamic-call result handling from corrupting aggregate compiler state.
- **Strict language behavior:** diagnostics and lowering are aligned for the
  strict module, numeric, mold, register, and operator contracts covered by the
  release suite.
- **Standard library:** environment, filesystem, data-format, URL/form, and
  runtime support are included in the frozen release tree.

## Release artifacts

- `virc-3.2.0-macos-arm64`: promoted, self-hosted Apple Silicon compiler.

Linux AArch64, x86-64, and RISC-V 64 compiler artifacts are not shipped in
3.2.0. Cross-compilation can produce ELF files for those targets, but the
Linux x86-64 compiler does not yet pass the required self-execution smoke gate.
Vir does not label cross-target compiler artifacts as supported until the
compiler and its generated program both execute with the expected output.

The compiler-sized `wasm32-wasi-p1` artifact is not shipped in 3.2.0. The Wasm
backend rejects control-flow used by the full compiler with
`E-WASM-UNSUPPORTED`; this release does not substitute a stub or an older
binary.

## Reproducibility

- macOS ARM64 SHA-256:
  `3e06dae92c9aabfa08a2389cfbf520919dd32fc1e86a401685c6984c95858109`
The macOS binary matches the signed Stage 2/Stage 3 fixed-point hash. The
read-only filesystem freeze contains its originating Git commit and per-file
checksums in `MANIFEST.json` and `SHA256SUMS`.
