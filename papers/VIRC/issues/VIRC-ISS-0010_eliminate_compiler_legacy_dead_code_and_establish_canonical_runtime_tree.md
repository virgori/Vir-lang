---
id: "VIRC-ISS-0010"
type: "ISSUE"
domain: "VIRC"
title: "Eliminate compiler legacy dead code and establish canonical runtime tree"
status: "CLOSED"
severity: "S2"
priority: "P1"
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
  issues: []
  plans:
    - "VIRC-PLN-0007"
  reports:
    - "VIRC-RPT-0019"
supersedes: null
superseded_by: null
tags:
  - "dead-code"
  - "runtime-tree"
  - "symlink-cleanup"
  - "misc-elimination"
  - "legacy-macho"
---

# VIRC-ISS-0010 — Eliminate compiler legacy dead code and establish canonical runtime tree

## 1. Summary

The canonical compiler tree under `compiler/src/` retains over 4,700 lines of dead, unmodularized, legacy code and 10 cross-tree symlinks under `compiler/src/misc/` and `compiler/src/main/legacy_macho.vri`.

Specifically:
1. `compiler/src/misc/ir_optimizer.vri` (3,111 lines) contains an obsolete AST-to-Q-IR lowering pass and linear scan register allocator from early bootstrap that is not registered in `compiler/module.list` and not referenced by the active pipeline.
2. `compiler/src/misc/vm.vri` (905 lines) and `compiler/src/misc/virc_min.vri` (35 lines) are dead bytecode VM and early driver prototypes.
3. `compiler/src/misc/string.vri` (392 lines), `result.vri` (165 lines), and `option.vri` (136 lines) are obsolete utility duplicates.
4. `compiler/src/main/legacy_macho.vri` (901 lines) is commented out (`#*# Legacy Q-IR code emitter`) but registered in `compiler/module.list` and spliced into `compiler/generated/virc.vri`.
5. 10 symlinks in `compiler/src/misc/` point across repository boundaries into `stdlib/vir/rt/` and `stdlib/vir/core/`, which `compiler/generated/virc.vri` relies upon via 9 `# @vir_source` markers. The compiler lacks an authoritative, self-contained `compiler/src/rt/` directory.

## 2. Context

During the resolution of `VIRC-ISS-0006` (`VIRC-PLN-0004`) and `VIRC-ISS-0009` (`VIRC-PLN-0006`), the compiler sources were moved to `compiler/src/` and decoupled from stdlib. However, the legacy bootstrap runtime symlinks and dead Q-IR/VM files were quarantined into `compiler/src/misc/` rather than canonicalized or removed.

Now that the driver and ELF writers are canonicalized and self-hosting is stable, this legacy dead code and cross-tree symlinks represent technical debt that bloats bundle size and confuses module discovery.

## 3. Expected Behavior

1. The compiler owns an authoritative, canonical runtime module tree under `compiler/src/rt/` (`syscall.vri`, `alloc.vri`, `string_rt.vri`, `io.vri`, `vec_rt.vri`, `start.vri`), registered cleanly in `compiler/module.list`.
2. All 9 `# @vir_source` markers in `compiler/generated/virc.vri` reference `compiler/src/rt/` directly.
3. The legacy directory `compiler/src/misc/` and all its dead contents (`ir_optimizer.vri`, `vm.vri`, `virc_min.vri`, `string.vri`, `result.vri`, `option.vri`, and all 10 symlinks) are completely deleted.
4. The dead file `compiler/src/main/legacy_macho.vri` is deleted, and its entry in `compiler/module.list` and `compiler/src/main.vri` is removed.
5. All 7 repository quality gates pass, including bit-identical self-hosting fixed point.

## 4. Actual Behavior

1. `compiler/src/misc/` exists with 4,744 lines of dead code and 10 cross-tree symlinks pointing to `stdlib/vir/`.
2. `compiler/src/main/legacy_macho.vri` exists with 901 lines of commented-out Q-IR emitter code embedded in `compiler/generated/virc.vri:76092`.
3. `compiler/generated/virc.vri` references `compiler/src/misc/` via 9 markers instead of a canonical compiler runtime directory.

## 5. Reproduction

```sh
# Inspect line counts of dead code
wc -l compiler/src/misc/ir_optimizer.vri compiler/src/misc/vm.vri compiler/src/main/legacy_macho.vri
# Verify symlinks
ls -la compiler/src/misc/
# Inspect references in generated compiler
grep -n "compiler/src/misc/" compiler/generated/virc.vri
grep -n "legacy_macho" compiler/module.list compiler/generated/virc.vri
```

## 6. Evidence

- CONFIRMED: `compiler/src/misc/ir_optimizer.vri` (3,111 lines) is not in `compiler/module.list` and only imported by `compiler/src/misc/vm.vri`.
- CONFIRMED: `compiler/src/main/legacy_macho.vri` (901 lines) contains dead commented code `#*# Legacy Q-IR code emitter. The full compiler uses emit_lir_module_arm64.` and is never invoked by the active compiler.
- CONFIRMED: 9 markers in `compiler/generated/virc.vri` point to `compiler/src/misc/` symlinks.
- CONFIRMED: `tools/check_module_dependencies.py` currently had to add special logic `not p.is_symlink()` because `compiler/src/misc/` symlinks re-introduced stdlib redundancy.

## 7. Scope

### Affected
- `compiler/src/misc/` (full deletion)
- `compiler/src/main/legacy_macho.vri` (deletion)
- `compiler/src/rt/` (creation of canonical compiler runtime files)
- `compiler/module.list` (registration of `rt_*` modules, removal of `main_legacy_macho`)
- `compiler/generated/virc.vri` (marker retargeting, removal of spliced legacy macho)

### Not affected / Unknown
- Language syntax and semantics
- Frontend lexer, parser, semantic passes
- MIR/LIR lowering and active backend emitters (`backend/macho.vri`, `backend/elf.vri`)

## 8. Impact

Severity: S2 (Technical debt, bloat, dangling symlinks across repository boundaries).
Priority: P1 (Clear prerequisites for pure self-contained compiler tree).

## 9. Preliminary Analysis

Extracting canonical `compiler/src/rt/` copies of the 6 pure-Vir runtime modules from `stdlib/vir/rt/` decouples the compiler runtime entirely from stdlib without symlinks. Deleting `legacy_macho.vri` and `misc/` reduces compiler codebase size by ~5,600 LOC of dead code with zero impact on compiler functionality.

## 10. Acceptance Criteria

- [x] Canonical compiler runtime modules exist under `compiler/src/rt/` (`syscall.vri`, `alloc.vri`, `string_rt.vri`, `io.vri`, `vec_rt.vri`, `start.vri`).
- [x] Runtime modules are registered in `compiler/module.list` under `rt_*` namespace.
- [x] All 9 `# @vir_source` markers in `compiler/generated/virc.vri` reference `compiler/src/rt/`.
- [x] `compiler/src/main/legacy_macho.vri` is removed from disk, `module.list`, and `virc.vri`.
- [x] Entire `compiler/src/misc/` directory (dead files and symlinks) is removed.
- [x] 0 bundle drift (`tools/sync_virc.py --check`).
- [x] 0 dependency violations (`tools/check_module_dependencies.py`).
- [x] All 7 quality gates pass, including CLI contract tests (43/43) and 3-stage bit-identical self-hosting fixed point.
- [x] Linked PLAN and accepted REPORT document verification and close the issue.

## 11. Related Papers

- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.
- `VIRC-ISS-0009` — Native codegen conflates architecture OS ABI and object format.
- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes.
- `VIRC-PLN-0006` — Decouple native codegen architecture OS ABI and object format.
- `VIRC-PLN-0007` — Eliminate compiler legacy dead code and establish canonical runtime tree.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged to eliminate legacy dead code, symlinks, and establish canonical compiler rt |
| 2026-10-03 | Linked VIRC-RPT-0019 |
| 2026-10-03 | Verified all acceptance criteria via VIRC-RPT-0019 under VIRC-PLN-0007; closed issue |
