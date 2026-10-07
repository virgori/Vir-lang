# Viron Semantic Versioning Policy

Viron uses Semantic Versioning (`MAJOR.MINOR.PATCH`) independently from:
- the Vir self-hosting compiler's calendar versioning (`2026.x`);
- the `vir-lsp` native language server's Semantic Version (`1.3.x`).

## Canonical Metadata

- Canonical record: `tools/viron/version.json`.
- Schema: version `1` record with `schema`, `major`, `minor`, `patch`, `public_version`, and `last_completed_issue`.
- Bump tool: `tools/bump_viron_version.py`.
- Bump gate: Every completed `VIRON-ISS` that changes production Viron must bump this version exactly once before reporting completion.

## CLI & Output Parity

The following surfaces must match `public_version` exactly:
- `tools/viron/version.json`
- `tools/viron/src/main.vri` banner, `--version` and diagnostics
- `bin/viron --version`
- `bin/viron.build.json`

## Bump Command

```sh
python3 tools/bump_viron_version.py --check
python3 tools/bump_viron_version.py --patch VIRON-ISS-0004
python3 tools/bump_viron_version.py --minor VIRON-ISS-0005
python3 tools/bump_viron_version.py --major VIRON-ISS-0006
```
