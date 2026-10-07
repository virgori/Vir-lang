# Viron — Modern Toolchain & Package Manager for Vir

Viron is the standalone, Vir-native package manager, toolchain lifecycle orchestrator, and build tool for the Vir programming language.

## Key Features

- **Project Scaffolding**: `viron new <name>` and `viron new --lib <name>` create standard projects with mandatory `module.list`, `vir.toml`, entrypoint, and test suite.
- **Deterministic Builds**: Resolves SemVer dependencies and guarantees bit-identical output via `vir.lock` and content-addressed cache.
- **Lifecycle Management**:
  - `viron toolchain`: Multi-toolchain install, list, default, rollback, repair under `VIR_HOME`.
  - `viron std`: Standard library install, update, verify, repair, rollback.
- **Diagnostics & Audit**: `viron doctor` checks system health, toolchains, caches, and repository integrity.
- **Reproducible Packaging**: `viron package` archives libraries securely without absolute paths or directory escapes.

## Building Viron

```sh
python3 tools/build_viron.py
./bin/viron --version
./bin/viron --help
```
