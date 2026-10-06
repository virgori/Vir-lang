# Vir compiler versioning

`compiler/version.json` is the canonical compiler-version record. The public
version follows the release year rather than semantic-version compatibility:

- `YYYY.R` is an official release. For example, `2026.1` is the first official
  release in 2026.
- `YYYY.R.P` is an internal patch build based on that official release. `P`
  starts at `1`; `.0` is never displayed.
- GitHub tags and release archives use the SemVer-compatible form
  `vYYYY.R.0` for an official release. Thus tag `v2026.1.0` contains compiler
  identity `2026.1`; the CLI never prints the tag's `v` prefix or official
  `.0` suffix.
- The compiler's numeric compatibility tuple is `(year, release,
  internal_patch)`, even when the public official version omits `.0`.

Every completed `VIR-ISS` or `VIRC-ISS` that changes compiler behavior, code,
generated compiler source, or shipped compiler assets must bump the compiler
version exactly once before the issue is reported complete:

```sh
python3 tools/bump_virc_version.py --bump-internal VIRC-ISS-0000
```

The command is idempotent for the same issue ID. It updates the canonical
record, the compiler source metadata, and the generated compiler bundle. The
issue's verification evidence must include the new version, generated-source
sync, and a rebuilt `bin/virc --version` result.

An explicitly approved official release increments `R`, resets `P` to `0`, and
uses the two-component public form:

```sh
python3 tools/bump_virc_version.py --set-official 2026.2 --issue VIR-ISS-0000
```

Do not bump historical papers, external protocol versions, stdlib ABI versions,
or editor-extension versions merely because the compiler version changes.

Before completion, run:

```sh
python3 tools/bump_virc_version.py --check
python3 tools/sync_virc.py --check
python3 tests/test_virc_version_policy.py
```
