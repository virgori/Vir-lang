---
id: "VIRC-RPT-0020"
type: "REPORT"
domain: "VIRC"
title: "Modularize compiler driver and add canonical bundle entry module report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "compiler-driver"
  - "generated-compiler"
  - "compiler-source-layout"
related:
  issues:
    - "VIRC-ISS-0011"
  plans:
    - "VIRC-PLN-0008"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "driver"
  - "entry-module"
  - "bundle-glue"
  - "modularization"
---

# VIRC-RPT-0020 — Modularize compiler driver and add canonical bundle entry module report

## 1. Executive Summary

1. `compiler/src/main/driver.vri` (1,432 lines) is now a thin orchestrator (includes, two imports, exports) over nine modules in `compiler/src/main/driver/`.
2. A canonical `compiler/src/entry.vri` owns the bundle header and `module vir.compiler.virc`.
3. `compiler/generated/virc.vri` has zero self-referential markers (was 35). 33 pinned `import` glue sections (41 lines) were proven dead and deleted.
4. `tools/sync_virc.py` now rejects any self-referential marker in `compiler/generated/virc.vri`.
5. The compiler built from the new sources is byte-identical to the previous compiler (19,797,871 bytes).

## 2. Source Issues

- VIRC-ISS-0011

## 3. Source Plans

- VIRC-PLN-0008

## 4. Implementation Summary

- **Phase 1:** created `compiler/src/entry.vri` from bundle lines 3-20, registered `bundle_entry` in `module.list`, deleted all other self-referential sections, hardened `sync_virc.py`. Prior experiment: a bundle with all glue imports removed compiled to a binary byte-identical to baseline stage3.
- **Phase 2:** sliced `driver.vri` into nine contiguous ranges (`config`, `cli_output`, `ui`, `defaults`, `locate`, `args`, `pipeline`, `banner`, `main_entry`), registered `driver_*` in `module.list`, and rewrote `driver.vri` as orchestrator. Bundle sections: `driver.vri` head, the nine modules in original order, `driver.vri` export tail.
- **Phase 3:** gates and fixed point (section 7).

## 5. Changes by Component

### `compiler/src/entry.vri`
- change: new canonical bundle header and module declaration.
- reason: remove hand-maintained text owned by the generated bundle.
- impact: none on generated code.

### `compiler/src/main/driver/*.vri`, `compiler/src/main/driver.vri`
- change: verbatim relocation of contiguous declarations; orchestrator keeps imports and exports.
- reason: cohesion, one responsibility per module.
- impact: bundle text differs from before only by new module doc comments and one trailing blank line.

### `tools/sync_virc.py`
- change: self-referential markers in `compiler/generated/` are an error.
- reason: bundle must be reproducible from `compiler/src/` alone.
- impact: negative test confirmed (exit 1, message names the line).

### `compiler/module.list`
- change: `bundle_entry`, `driver_config`, `driver_cli_output`, `driver_ui`, `driver_defaults`, `driver_locate`, `driver_args`, `driver_pipeline`, `driver_banner`, `driver_main_entry`.

## 6. Deviations from Plan

None material. The new `driver/` modules do not declare per-file imports of the many flat-bundle symbols they use, matching the previous single-file `driver.vri`, which relied on the same flat bundle; a finer dependency declaration is left as future work.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `python3 tools/check_module_dependencies.py` | PASS | 263 files, 0 violations |
| `python3 tools/sync_virc.py --check` | PASS | 0 drift |
| `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, 263 modules clean |
| `python3 tools/paper.py validate` | PASS | 80 production papers |
| Self-referential marker negative test | PASS | injected marker rejected, exit 1 |
| Self-host build | PASS | `bin/virc` on new bundle gives output `cmp`-identical to baseline stage3; stage3 from it also identical |
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 |
| `./run_tests.sh min` | PASS (baseline) | 409/413, the same 4 known failures |

### Regression
Zero regression: 409 passed, 4 known failures (VIRC-ISS-0003, VIRC-ISS-0005).

### Conformance
No language, CLI or `stdlib/vir/` change.

## 8. Acceptance Criteria

- [x] `compiler/src/main/driver/` holds nine extracted modules; `driver.vri` is a thin orchestrator keeping exports.
- [x] `compiler/src/entry.vri` owns the bundle header.
- [x] Zero self-referential markers in the bundle; `sync_virc.py` rejects them.
- [x] 0 drift, 0 dependency violations, pass-architecture passes.
- [x] 3-stage fixed point bit-identical.
- [x] CLI contract 43/43 and test baseline 409/413 preserved.
- [x] PLAN completed and this REPORT accepted.

## 9. Known Limitations

- `virc_compile` (~577 lines) is still one function inside `driver/pipeline.vri`; splitting it requires semantic refactoring and is out of scope.
- Driver submodules rely on the flat bundle namespace rather than explicit imports.

## 10. Remaining Work

None under VIRC-ISS-0011. Further function-level splitting of `virc_compile` can be a new issue.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- VIRC-ISS-0011, VIRC-PLN-0008, VIRC-ISS-0010, VIRC-PLN-0007, VIRC-RPT-0019

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0011 / VIRC-PLN-0008 |
