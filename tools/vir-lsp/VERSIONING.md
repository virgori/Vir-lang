# vir-lsp versioning

`vir-lsp` uses Semantic Versioning independently from the Vir compiler. Its
canonical record is `tools/vir-lsp/version.json`; compiler calendar releases do
not implicitly change the LSP version.

- MAJOR: incompatible LSP protocol, custom extension, persistence, or client
  integration contract change.
- MINOR: backward-compatible capability or observable feature addition.
- PATCH: compatible fix, diagnostic correction, performance work, or internal
  refactor.

Every completed `VLSP-ISS` that changes the server, its protocol surface, or
shipped binary must bump the LSP version exactly once before completion:

```sh
python3 tools/bump_vir_lsp_version.py --patch VLSP-ISS-0000
```

Use `--minor` or `--major` only when the change matches the rules above. The
command is idempotent for the same issue ID and updates the canonical metadata
and source literals. After a bump, rebuild `bin/vir-lsp` and verify both the CLI
identity and initialize-response `serverInfo.version`.

Required checks:

```sh
python3 tools/bump_vir_lsp_version.py --check
python3 tools/build_vir_lsp.py
python3 tests/test_lsp_initialize.py
```
