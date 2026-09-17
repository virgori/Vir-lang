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
- `virc-3.2.0-linux-arm64`: static Linux AArch64 compiler.
- `virc-3.2.0-linux-x86_64`: static Linux x86-64 compiler.
- `virc-3.2.0-linux-riscv64`: static Linux RISC-V 64 compiler.

The release workflow executes a two-level smoke gate for every Linux artifact:
each compiler must compile the arithmetic smoke program for its own target, and
the resulting program must execute with the expected output. Non-native Linux
architectures run under QEMU.

The compiler-sized `wasm32-wasi-p1` artifact is not shipped in 3.2.0. The Wasm
backend rejects control-flow used by the full compiler with
`E-WASM-UNSUPPORTED`; this release does not substitute a stub or an older
binary.

## Reproducibility

- macOS ARM64 SHA-256:
  `3e06dae92c9aabfa08a2389cfbf520919dd32fc1e86a401685c6984c95858109`
- Linux ARM64 SHA-256:
  `b63a97448e5045c79118b784c9e6038868c3b2ccd9ec1602f4346f6e18472473`
- Linux x86-64 SHA-256:
  `a7c0c1a8ba857fc07c51f0c2ce225299ace9cc7af07f11ce20b4e7202139e0f4`
- Linux RISC-V 64 SHA-256:
  `72bb5b044322a9eb1ec0cc51fcc205a0d3af3d04c412a469341f4e357b5f8363`

The macOS binary matches the signed Stage 2/Stage 3 fixed-point hash. The
read-only filesystem freeze contains its originating Git commit and per-file
checksums in `MANIFEST.json` and `SHA256SUMS`.
