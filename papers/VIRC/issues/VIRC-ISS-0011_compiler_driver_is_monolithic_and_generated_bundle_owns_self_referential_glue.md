---
id: "VIRC-ISS-0011"
type: "ISSUE"
domain: "VIRC"
title: "Compiler driver is monolithic and generated bundle owns self-referential glue"
status: "CLOSED"
severity: "S3"
priority: "P2"
created: "2026-10-03"
updated: "2026-10-03"
owners: []
components:
  - "compiler-driver"
  - "generated-compiler"
  - "compiler-source-layout"
related:
  issues: []
  plans:
    - "VIRC-PLN-0008"
  reports:
    - "VIRC-RPT-0020"
supersedes: null
superseded_by: null
tags:
  - "driver"
  - "entry-module"
  - "bundle-glue"
  - "modularization"
---

# VIRC-ISS-0011 — Compiler driver is monolithic and generated bundle owns self-referential glue

## 1. Summary

After `VIRC-ISS-0009` and `VIRC-ISS-0010`, two modularization gaps remain in the compiler source tree:

1. `compiler/src/main/driver.vri` (1,432 lines) mixes configuration, CLI help/error output, UI resolution, defaults, source location, argument parsing, the compile pipeline, banner rendering and the program entry `main`.
2. `compiler/generated/virc.vri` still contains 35 self-referential markers (`# @vir_source compiler/generated/virc.vri N`) whose 77 lines (module header, comments and ~30 `import` statements) have no canonical source and are only preserved by `tools/sync_virc.py` pinning them in the generated file.

## 2. Context

`tools/sync_virc.py` treats any marker whose path ends with `virc.vri` and line < 97 as pinned content. The bundle therefore owns hand-maintained text, contradicting the rule that generated output is reproducible from `compiler/src/` alone.

## 3. Expected Behavior

1. The driver is split into cohesive modules under `compiler/src/main/driver/`, with `compiler/src/main/driver.vri` as a thin orchestrator that keeps its public exports.
2. A canonical source `compiler/src/entry.vri` owns the bundle header and `module vir.compiler.virc` declaration.
3. `compiler/generated/virc.vri` contains zero self-referential markers; `tools/sync_virc.py` rejects them fail-closed.
4. Compiler behavior and generated machine code are unchanged (self-host fixed point; stage output bit-identical to the pre-change compiler).

## 4. Actual Behavior

1. `driver.vri` is a single 1,432-line file containing nine unrelated responsibilities.
2. The bundle holds 35 self-referential markers (lines 1, 2, 907, 2286, ... 74699).

## 5. Reproduction

```sh
grep -c "@vir_source compiler/generated/virc.vri" compiler/generated/virc.vri
wc -l compiler/src/main/driver.vri
```

## 6. Evidence

- CONFIRMED: removing all 33 pinned `import` glue sections from the bundle (keeping the header) and recompiling with `bin/virc` yields a binary byte-identical to the baseline stage3 (`cmp` identical, 19,797,871 bytes). The glue imports are therefore dead in the bundle, because every referenced module is already physically spliced.
- CONFIRMED: the header (`module vir.compiler.virc`, usage comments) is the only non-import content.
- CONFIRMED: `tools/sync_virc.py` accepts self-referential markers with line < 97.
- OBSERVED: `driver.vri` function boundaries are contiguous (config 5-86, CLI output 88-146, UI 148-203, defaults 205-261, locate 262-325, args 327-562, pipeline 564-1164, banner 1165-1350, main 1351-1429).

## 7. Scope

### Affected
- `compiler/src/main/driver.vri` and new `compiler/src/main/driver/*.vri`
- new `compiler/src/entry.vri`
- `compiler/module.list`, `compiler/generated/virc.vri`
- `tools/sync_virc.py`

### Not affected / Unknown
- Language syntax and semantics, frontend, semantic passes, lowering, backends.
- `stdlib/vir/`.

## 8. Impact

Severity: S3 (maintainability; no functional defect). Priority: P2.

## 9. Preliminary Analysis

All driver ranges are contiguous top-level declarations, so moving them preserves bundle text order and thus generated code. Pure relocation needs no signature changes.

## 10. Acceptance Criteria

- [x] `compiler/src/main/driver/` holds the extracted modules and `driver.vri` is a thin orchestrator keeping its exports.
- [x] `compiler/src/entry.vri` exists and owns the bundle header.
- [x] `compiler/generated/virc.vri` has zero `@vir_source compiler/generated/virc.vri` markers and `sync_virc.py` rejects them.
- [x] 0 bundle drift, 0 dependency violations, pass-architecture gate passes.
- [x] CLI contract 43/43, module fixtures 5/5, `./run_tests.sh min` 409/413.
- [x] 3-stage self-host fixed point bit-identical.
- [x] Linked PLAN completed and accepted REPORT closes the issue.

## 11. Related Papers

- `VIRC-ISS-0006`, `VIRC-ISS-0009`, `VIRC-ISS-0010`
- `VIRC-PLN-0008`

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created from post-VIRC-ISS-0010 modularization audit |
| 2026-10-03 | Verified all acceptance criteria via VIRC-RPT-0020 under VIRC-PLN-0008; closed issue |
| 2026-10-03 | Linked VIRC-RPT-0020 |
