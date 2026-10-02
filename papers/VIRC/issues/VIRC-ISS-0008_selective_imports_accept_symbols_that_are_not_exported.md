---
id: "VIRC-ISS-0008"
type: "ISSUE"
domain: "VIRC"
title: "Selective imports accept symbols that are not exported"
status: "OPEN"
severity: "S1"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRC"
components:
  - "module-resolution"
  - "symbol-visibility"
  - "diagnostics"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0007"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "import"
  - "export"
  - "visibility"
  - "diagnostics"
---

# VIRC-ISS-0008 — Selective imports accept symbols that are not exported

## 1. Summary

The active compiler accepts a selective import from a module that declares no
`export` statement. A private function can therefore cross the module boundary
and be called by another source unit without an error.

When the same provider contains an export list that omits the requested symbol,
the compiler correctly emits `E2113`. Export enforcement is consequently
dependent on whether any export declaration exists, rather than treating the
absence of exports as an empty public surface.

## 2. Context

`VIR-SPC-0014` defines selective import as bringing exported symbols into the
current scope. The compiler resolver contains explicit export validation and an
`E2113` diagnostic, but active behavior still accepts a selective import when
the target module has no export declarations.

This issue is separate from redundant include/import cleanup. An import-only
fixture reproduces the visibility failure, so removing preceding includes does
not resolve it.

## 3. Expected Behavior

- Module declarations are private by default unless explicitly listed by an
  `export` declaration.
- `import symbol from module` succeeds only when `symbol` exists and is
  explicitly exported by that resolved module.
- A module with no exports has an empty importable public surface.
- Missing or private symbols produce a stable module-resolution diagnostic at
  the import site, including the requested symbol and resolved module identity.
- A preceding include, alternate registry spelling, generated bundle, or
  compatibility path cannot bypass the export check.

## 4. Actual Behavior

- An import-only fixture requests `hiddenValue` from a module with no export
  declarations. `bin/virc --check --json` returns exit 0, `success: true`, and
  an empty diagnostic list.
- The same failure remains accepted when `include dep` precedes the selective
  import.
- Adding `export publicValue` to the provider while leaving `hiddenValue`
  private changes the result to exit 1 with `E2113: imported symbol not
  exported`.
- The compiler therefore distinguishes “export list exists but omits symbol”
  from “module exports nothing” and incorrectly treats the latter as importable.

## 5. Reproduction

Run from `/Users/gengyang/Vir-3.0` at revision
`e0082dfd4c087b17165c6346f678d787bf65c423`:

```text
# /private/tmp/vir3_module_issue/import_private/module.list
root = .
dep = dep.vri
```

```vir
# dep.vri — deliberately no export declaration
func hiddenValue -> int:
    out 9
end.
```

```vir
# main.vri
import hiddenValue from dep

func main:
    print hiddenValue()
    out 0
end.
```

```sh
./bin/virc /private/tmp/vir3_module_issue/import_private/main.vri \
  -o /private/tmp/vir3_module_issue/import_private/out \
  --check --json --color=never
```

Control case: add a different exported function to `dep.vri`:

```vir
func publicValue -> int:
    out 3
end.

func hiddenValue -> int:
    out 13
end.

export publicValue
```

Re-run the same import. The compiler exits 1 and emits `E2113`.

## 6. Evidence

- CONFIRMED: `bin/virc` SHA-256
  `39488949d2b94cb7ebb1518869fea5146c0666bbfe9cfedced37b36d47aa4748`
  accepts the no-export selective import with `success: true`, zero errors, and
  zero warnings.
- CONFIRMED: the explicit-export-list control rejects the private symbol with
  `E2113`, phase `ModuleResolver`, message `imported symbol not exported`.
- CONFIRMED: both modular `compiler/src/main.vri` and generated
  `compiler/generated/virc.vri` contain `text_validate_import_exports` and a
  compatibility branch labelled `No export list (stdlib modules)`.
- CONFIRMED: `VIR-SPC-0014` restricts selective import to exported symbols.
- OBSERVED: multiple compiler/runtime compatibility modules currently omit
  export declarations, so enforcing the contract may reveal a migration set
  rather than one isolated fixture.
- HYPOTHESIS: the no-export compatibility behavior or the parsed representation
  of an empty export set bypasses symbol validation in the active binary; the
  exact control-flow cause is not yet verified.

## 7. Scope

### Affected

- project and standard-library selective imports;
- modular and generated compiler preprocessors;
- module visibility and public API boundaries;
- JSON/classic diagnostics and IDE semantic facts;
- self-hosting modules that currently rely on implicit export-all behavior.

### Not affected / Unknown

- Include-only visibility semantics are tracked by `VIRC-ISS-0007` and are not
  redefined here.
- Whole-module import behavior and `get` visibility require dedicated fixtures
  before being classified.
- The number of current modules that intentionally rely on implicit export-all
  behavior is not yet verified.

## 8. Impact

The compiler violates module encapsulation and can expose implementation-only
functions as public dependencies. Refactors may silently break callers that
were never entitled to those symbols, and IDE/API tooling cannot trust export
metadata as the authoritative public surface.

Severity is S1 because this is a confirmed language-semantics and visibility
correctness failure in the core resolver. Priority is P1 because registry and
compiler-module migration should not stabilize around implicit export-all
behavior.

## 9. Preliminary Analysis

- CONFIRMED: the failure reproduces without any preceding include.
- CONFIRMED: the existing `E2113` path works when an explicit export list
  exists and omits the symbol.
- HYPOTHESIS: a compatibility exception for legacy stdlib modules is being
  applied too broadly or before the selective-symbol set is validated.
- HYPOTHESIS: making “no exports” an explicit empty export set will remove the
  ambiguity and simplify resolver behavior.
- NOT_VERIFIED: which canonical compiler and stdlib modules must add explicit
  exports before fail-closed enforcement can land.

## 10. Acceptance Criteria

- [ ] A selective import of any symbol from a module with no exports fails with
  `E2113` (or a more specific stable diagnostic) at the import site.
- [ ] A selective import of an explicitly exported symbol succeeds without a
  preceding include.
- [ ] A selective import of an existing but non-exported symbol fails whether
  or not the provider exports other symbols.
- [ ] A preceding include, registry alias, compatible path spelling, repeated
  import, or diamond dependency cannot bypass export enforcement.
- [ ] Diagnostics identify the requested symbol and canonical module identity
  in classic and JSON modes; IDE facts do not report the failed import as a
  valid public binding.
- [ ] Project and stdlib fixtures cover modules with zero exports, partial
  export lists, aliases, entities/enums/constants/functions, and missing
  symbols.
- [ ] Existing compiler/stdlib modules that intentionally expose APIs gain
  explicit export declarations; no blanket export-all fallback remains for
  selective imports.
- [ ] Modular and generated compiler sources are synchronized and stage 2 ==
  stage 3 under the repository self-host fixed-point contract.

## 11. Related Papers

### Issues

- `VIRC-ISS-0007` — redundant same-module include/import declarations can mask
  the intended dependency form but are not required to reproduce this issue.

### Plans

- `VIRC-PLN-0004` — compiler module migration context; section 6.3 defines
  private-by-default exports.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Opened from import-only and explicit-export-list control fixtures against the active self-hosted compiler |
| 2026-10-02 | Linked VIRC-ISS-0007 |
