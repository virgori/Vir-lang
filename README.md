# The Vir Programming Language

[![Release](https://img.shields.io/github/v/release/virgori/Vir-lang)](https://github.com/virgori/Vir-lang/releases/latest)

Vir is a self-hosted systems programming language with deterministic ownership,
native ahead-of-time compilation, a modular standard library, and integrated
compiler/LSP tooling.

Current tool versions:

- Vir compiler: `2026.1` (`v2026.1.0` GitHub release)
- vir-lsp: `1.3.0`

## Version conventions

The compiler uses calendar release versions:

- `YYYY.R` is the public identity of an official compiler release. `2026.1` is
  the first official release in 2026.
- GitHub tags and release archives use `vYYYY.R.0` so release tooling receives a
  three-component version. Tag `v2026.1.0` therefore contains compiler
  `2026.1`.
- `YYYY.R.P`, where `P > 0`, identifies an internal patch build. Internal patch
  numbers are not official releases.
- `virc --version` and compiler banners never include the tag prefix `v`; an
  official build also omits the `.0` distribution suffix.

`vir-lsp` has an independent Semantic Version. Its MAJOR/MINOR/PATCH values are
not derived from the compiler's calendar version. See
[compiler/VERSIONING.md](compiler/VERSIONING.md) and
[tools/vir-lsp/VERSIONING.md](tools/vir-lsp/VERSIONING.md).

## Repository layout

- `compiler/src/` — canonical self-hosted compiler sources.
- `compiler/generated/virc.vri` — synchronized compiler bundle.
- `stdlib/` — standard library sources and registry.
- `tools/vir-lsp/` — native language server.
- `tools/vscode-vir/` — VS Code integration.
- `papers/` — specifications, issues, plans, reports, and the VPS registry.
- `tests/` — compiler, language, sysroot, CLI, and LSP contracts.

## Getting started

The local release binaries target macOS ARM64:

```sh
./bin/virc --version
./bin/vir-lsp --version
```

Compile a Vir source file:

```sh
./bin/virc main.vri -o main
./main
```

Build and verify the native language server:

```sh
python3 tools/build_vir_lsp.py
python3 tests/test_lsp_initialize.py
```

Core repository checks:

```sh
python3 tools/sync_virc.py --check
python3 tools/bump_virc_version.py --check
python3 tools/bump_vir_lsp_version.py --check
./paper registry --check
./paper validate
```

## Documentation

- [2026.1.0 release notes](docs/releases/2026.1.0.md)
- [English language specification](papers/VIR/specs/VIR-SPC-0017_language_specification_english.md)
- [Vietnamese language specification](papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md)
- [Compiler source guide](compiler/README.md)
- [Standard library](stdlib/README.md)
- [Vir language server](tools/vir-lsp/README.md)
- [VPS paper registry](papers/REGISTRY.yaml)
