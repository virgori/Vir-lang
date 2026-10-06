---
id: "VIRC-RPT-0019"
type: "REPORT"
domain: "VIRC"
title: "Eliminate compiler legacy dead code and establish canonical runtime tree report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "compiler-source-layout"
  - "runtime-layer"
  - "dead-code-elimination"
  - "module-resolution"
  - "generated-compiler"
related:
  issues:
    - "VIRC-ISS-0010"
  plans:
    - "VIRC-PLN-0007"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "dead-code"
  - "runtime-tree"
  - "symlink-cleanup"
  - "misc-elimination"
  - "legacy-macho"
  - "self-hosting"
---

# VIRC-RPT-0019 — Eliminate compiler legacy dead code and establish canonical runtime tree report

## 1. Executive Summary

This report documents the implementation, verification, and closure of [VIRC-ISS-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0010_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md) under [VIRC-PLN-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0007_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md).

1. A compiler-owned runtime tree `compiler/src/rt/` (6 modules, 3,495 lines) now provides the runtime preludes spliced into the generated compiler, registered as `rt_*` in `compiler/module.list`.
2. All 9 runtime `# @vir_source` markers in `compiler/generated/virc.vri` now reference `compiler/src/rt/`.
3. `compiler/src/main/legacy_macho.vri` (901 lines, dead code) and the whole `compiler/src/misc/` directory (4,744 lines, including `ir_optimizer.vri`, `vm.vri`, `virc_min.vri` and 10 cross-tree symlinks) were deleted: 5,645 lines of dead code in total.
4. The compiler source set shrank from 260 to 253 modules; `compiler/src/` now holds zero symlinks.
5. The 3-stage self-host fixed point is bit-identical and the test baseline is unchanged (409/413).

## 2. Source Issues

- [VIRC-ISS-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0010_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md)

## 3. Source Plans

- [VIRC-PLN-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0007_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md)

## 4. Implementation Summary

- **Phase 1:** created `compiler/src/rt/{syscall,alloc,string_rt,io,vec_rt,start}.vri`, registered them in `module.list`, removed redundant includes so the dependency gate reports 0 violations, and retargeted the 9 bundle markers.
- **Phase 2:** removed `legacy_macho.vri`: its `include` and its three exports (`emit_macho_executable`, `emit_macho_with_entry`, `FuncLayout`) from `compiler/src/main.vri`, the matching import in `compiler/src/main/driver.vri`, its `module.list` entry, and its 901-line section from the bundle. Evidence for safety: the only remaining call of `emit_macho_executable` in `main.vri` sat inside the commented-out legacy `#*# … #*#` block; `driver.vri` made zero uses of the three symbols.
- **Phase 3:** deleted `compiler/src/misc/`. Beforehand: no bundle marker, `module.list` entry or non-`misc` source file referenced it.
- **Phase 4:** full verification (section 7). `python3 tools/sync_virc.py` regenerated the `main.vri` and `driver.vri` sections of the bundle.

## 5. Changes by Component

### `compiler/src/rt/`
- change: new canonical runtime modules (alloc, io, start, string_rt, syscall, vec_rt).
- reason: decouple the compiler from `stdlib/vir/rt/` and the `misc/` symlinks (VIRC-PLN-0004 principle).
- impact: none on generated code semantics; bundle content for these sections is unchanged.

### `compiler/src/main.vri`, `compiler/src/main/driver.vri`
- change: dropped legacy Mach-O include, exports and import.
- reason: dead code removal.
- impact: none; the symbols had no live callers.

### `compiler/src/main/legacy_macho.vri`, `compiler/src/misc/`
- change: deleted.
- reason: dead code, obsolete Q-IR pipeline, VM interpreter and symlinks.
- impact: bundle shrinks by the 901-line legacy section; no behaviour change.

### `compiler/module.list`, `compiler/generated/virc.vri`
- change: `rt_*` entries added, `main_legacy_macho` removed; bundle re-synchronized (now 81,005 lines).
- reason: keep the registry and bundle consistent with canonical sources.
- impact: `sync_virc.py --check` reports 0 drift.

## 6. Deviations from Plan

No material deviations from the approved plan. The legacy-section removal from the bundle was done by deleting its marker range directly and then running `sync_virc.py`, because the tool has no "remove module" mode; drift check confirms the result is canonical.

## 7. Verification

### Tests

| Test | Result | Evidence |
|---|---|---|
| `python3 tools/check_module_dependencies.py` | PASS | 253 compiler source files clean, 0 violations |
| `python3 tools/sync_virc.py --check` | PASS | 0 bundle drift |
| `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, stdlib boundary clean, 253 module dependencies clean |
| `python3 tests/cli_contract/runner.py` | PASS | 43/43 |
| `tests/modules/test_*.vri` fixtures | PASS | 5/5 compiled and executed with exit 0 |
| `./run_tests.sh min` | PASS (baseline) | 409/413; the same 4 known failures (§11, §26) |
| Symlink scan | PASS | `find compiler/src -type l` = 0 |
| `python3 tools/paper.py validate` | PASS | VPS validation passed |
| Self-host fixed point | PASS | `bin/virc` → stage2 → stage3 → stage4; `cmp bin/virc_stage3 bin/virc_stage4` identical (19,797,871 bytes each) |

### Regression

Zero regression against the historical baseline (409 passed, 4 known failures tracked by `VIRC-ISS-0003` and `VIRC-ISS-0005`).

### Conformance

No language or CLI behaviour changed; `stdlib/vir/` was not modified by this work.

## 8. Acceptance Criteria

Mapping 1:1 with VIRC-ISS-0010 section 10:

- [x] Canonical compiler runtime modules exist under `compiler/src/rt/`.
- [x] Runtime modules registered in `compiler/module.list` under `rt_*`.
- [x] All 9 runtime markers in `compiler/generated/virc.vri` reference `compiler/src/rt/`.
- [x] `legacy_macho.vri` removed from disk, `module.list` and `virc.vri`.
- [x] `compiler/src/misc/` removed entirely.
- [x] 0 bundle drift.
- [x] 0 dependency violations.
- [x] All quality gates pass including CLI contract 43/43 and the bit-identical self-host fixed point.
- [x] Linked PLAN completed and this REPORT accepted.

## 9. Known Limitations

- `tools/migrate_huong3_phase2.py` (one-off historical migration script) still mentions `compiler/src/misc/` paths; it is not part of any gate or build.
- The 4 known baseline test failures remain and are tracked elsewhere.

## 10. Remaining Work

None under `VIRC-ISS-0010` / `VIRC-PLN-0007`.

## 11. Conclusion

READY_FOR_CLOSE

## 12. Related Papers

- [VIRC-ISS-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0010_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md)
- [VIRC-PLN-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0007_eliminate_compiler_legacy_dead_code_and_establish_canonical_runtime_tree.md)
- `VIRC-ISS-0006`, `VIRC-PLN-0004`, `VIRC-RPT-0018`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0010 / VIRC-PLN-0007 completion and closure |
