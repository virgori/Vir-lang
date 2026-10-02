---
id: "VIRC-ISS-0007"
type: "ISSUE"
domain: "VIRC"
title: "Compiler sources redundantly combine include with selective import"
status: "OPEN"
severity: "S3"
priority: "P1"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRC"
components:
  - "module-resolution"
  - "compiler-source-layout"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0006"
    - "VIRC-ISS-0008"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "dependency-cleanup"
  - "module-identity"
---

# VIRC-ISS-0007 — Compiler sources redundantly combine include with selective import

## 1. Summary

Compiler sources commonly declare both `include M` and a selective
`import ... from M` for the same canonical module. The active include
preprocessor already places the included module body in the compilation scope,
so the following selective import repeats the dependency and symbol inventory
without loading a distinct module.

At revision `e0082dfd4c087b17165c6346f678d787bf65c423`, 88 of 106 canonical
`compiler/src/**/*.vri` files contain at least one adjacent same-module
`include`/`import` pair.

## 2. Context

`VIR-SPC-0014` defines `include` as a physical module load and states that a
selective `import` does not require a preceding `include`. The active resolver
expands includes first, records the canonical Module ID, and treats a later
import of the same Module ID as alias-shim work because the declarations are
already in scope.

`VIRC-PLN-0004` section 6.6 already records the implementation policy that a
redundant `include` must not be added merely because an `import` exists. This
issue isolates the still-present source and enforcement defect from the broader
compiler-tree migration tracked by `VIRC-ISS-0006`.

## 3. Expected Behavior

- A caller that chooses `include M` can use the declarations made available by
  the include contract without enumerating the same functions in a subsequent
  selective import.
- A caller that needs only exported symbols uses `import A, B from M` without a
  preceding `include M`.
- One source unit expresses one dependency on a canonical Module ID. A second
  declaration is permitted only when it has independently specified semantics,
  such as a verified alias operation that cannot be represented directly.
- Compiler source checks reject accidental same-module `include` plus selective
  import pairs.

## 4. Actual Behavior

- 88 compiler source files contain an adjacent `include M` followed by
  `import ... from M`.
- An include-only fixture compiles successfully and resolves an unqualified
  function from the included module, proving that the matching selective import
  is not required by the active compiler behavior.
- The resolver explicitly comments that a module already pulled in through
  include/import has its exported names in scope and only alias shims remain.
- The duplicated declarations obscure the actual dependency model and make it
  difficult to distinguish required imports from compatibility residue.

## 5. Reproduction

Run from `/Users/gengyang/Vir-3.0` at revision
`e0082dfd4c087b17165c6346f678d787bf65c423`:

```sh
find compiler/src -type f -name '*.vri' | wc -l
rg --pcre2 -l -U \
  '^include ([A-Za-z0-9_.]+)\nimport [^\n]* from \1(?:\r)?$' \
  compiler/src --glob '*.vri' | wc -l
./bin/virc /private/tmp/vir3_module_issue/include_only/main.vri \
  -o /private/tmp/vir3_module_issue/include_only/out \
  --check --json --color=never
```

Fixture:

```text
# module.list
root = .
dep = dep.vri
```

```vir
# dep.vri
func exposedValue -> int:
    out 7
end.

export exposedValue
```

```vir
# main.vri
include dep

func main:
    print exposedValue()
    out 0
end.
```

## 6. Evidence

- CONFIRMED: the inventory commands report 106 source files and 88 files with
  at least one adjacent same-module include/import pair.
- CONFIRMED: `bin/virc` SHA-256
  `39488949d2b94cb7ebb1518869fea5146c0666bbfe9cfedced37b36d47aa4748`
  returns exit 0, `success: true`, and no diagnostics for the include-only
  fixture.
- CONFIRMED: `compiler/src/main.vri` expands includes before imports and its
  already-loaded branch states that names are already in scope.
- CONFIRMED: `VIR-SPC-0014` says selective import does not require a prior
  include.
- OBSERVED: redundant pairs occur across frontend, semantic, IR, lowering,
  backend, CLI, IDE, and bootstrap modules rather than one isolated component.
- NOT_VERIFIED: whether every non-adjacent include/import pair is redundant;
  migration needs canonical-ID analysis rather than a text-only rewrite.

## 7. Scope

### Affected

- canonical compiler modules under `compiler/src/`;
- generated compiler assembly and dependency graph construction;
- module-resolution tests and architecture checks;
- self-host fixed-point verification.

### Not affected / Unknown

- This issue does not change selective-import export visibility; that defect is
  tracked separately by `VIRC-ISS-0008`.
- Alias imports and namespace-qualified use require an explicit semantics audit
  before any automatic rewrite.
- Standard-library and downstream project migrations are outside scope unless
  the same compiler rule is deliberately applied to them.

## 8. Impact

The duplication creates noisy dependency declarations, increases generated
source work, and masks whether a caller depends on an entire module or only its
public surface. It also makes export enforcement harder to reason about because
an include may make a later selective import operationally unnecessary.

Severity is S3 because the confirmed behavior currently compiles, but the
pattern materially harms maintainability and can hide visibility defects.
Priority is P1 because the active compiler-tree migration is establishing the
final module graph now.

## 9. Preliminary Analysis

- CONFIRMED: include and import converge on the same canonical identity and
  dedup table in the active resolver.
- CONFIRMED: an include-only caller can resolve the fixture function.
- HYPOTHESIS: most adjacent pairs are migration residue from a period when
  physical inclusion and symbol visibility were implemented separately.
- HYPOTHESIS: removing redundant declarations after registry flattening will
  make the resolved graph smaller and diagnostics more deterministic.
- NOT_VERIFIED: the subset of pairs that exists solely to preserve an alias;
  those sites need symbol-level inspection.

## 10. Acceptance Criteria

- [ ] A deterministic checker resolves canonical Module IDs and reports every
  compiler source that both includes and selectively imports the same module,
  with narrow documented exceptions only for necessary alias semantics.
- [ ] Compiler canonical sources contain no redundant same-module pair.
- [ ] Include-only positive fixtures cover functions, entities/enums, constants,
  and nested dependencies supported by the include contract.
- [ ] Import-only positive fixtures prove selective imports require no prior
  include and load each canonical module once.
- [ ] Diamond dependencies and repeated includes still deduplicate to one
  Module ID and retain useful cycle diagnostics.
- [ ] Modular and generated compiler sources are synchronized through the
  authoritative generation workflow.
- [ ] Stage 1 -> stage 2 -> stage 3 self-hosting passes the repository fixed-point
  contract, with representative module tests run from repository root, a
  subdirectory, and an unrelated CWD.

## 11. Related Papers

### Issues

- `VIRC-ISS-0006` — broader compiler-tree separation and module-identity
  migration context.
- `VIRC-ISS-0008` — selective import currently accepts symbols from a module
  with no exports.

### Plans

- `VIRC-PLN-0004` — active design context; section 6.6 already prohibits
  redundant include/import declarations.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Opened from source inventory, active resolver inspection, and an include-only compiler fixture |
| 2026-10-02 | Linked VIRC-ISS-0008 |
| 2026-10-02 | Linked VIRC-ISS-0006 |
