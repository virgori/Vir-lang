# Vir 3.0

Vir 3.0 is the active Vir language, compiler, standard library, and editor
tooling repository. The repository state that previously occupied `main` is
preserved intact under [`Vir-2.0_legacy_`](Vir-2.0_legacy_/).

## Repository layout

- `compiler/` — canonical compiler source and generated compiler bundle.
- `stdlib/` — standard library source and module registry.
- `bin/` — published macOS ARM64 `virc` and `vir-lsp` executables.
- `docs/` — guides and supporting documentation.
- `papers/` — VPS specifications, issues, plans, reports, and registry.
- `paper` — command-line entry point for VPS paper management.
- `vscode-tool/` — VS Code extension source, assets, and tests.
- `vir-lsp/` — native Vir language server source and documentation.
- `tests/` — compiler, language, standard-library, and tooling tests.
- `tools/` — build, validation, synchronization, and repository utilities.
- `Vir-2.0_legacy_/` — archived snapshot of the former repository root.

## Quick checks

```sh
./bin/virc --version
python3 tools/sync_virc.py --check
./paper registry --check
./paper validate
```

Build and test the language server from the repository root:

```sh
python3 tools/build_vir_lsp.py
python3 tests/run_lsp_tests.py
```

See [`papers/STANDARD.md`](papers/STANDARD.md) for the paper lifecycle and
[`compiler/README.md`](compiler/README.md) for compiler-specific guidance.
