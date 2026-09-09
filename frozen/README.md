# Vir Frozen Release Directory

Versioned filesystem tree snapshots for compiler and standard library releases.

- **Current Release Freeze**: `frozen/release/v2.8.5/`
  - `MANIFEST.json`
  - `SHA256SUMS`
  - `stdlib/`
  - `compiler_src/`
  - `bin/virc`
  - `virc-expanded.vri`

All freeze snapshots are verified via `tools/freeze_std_tree.sh verify`.
