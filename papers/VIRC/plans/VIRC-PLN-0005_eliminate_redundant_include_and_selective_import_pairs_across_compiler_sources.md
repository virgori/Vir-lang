---
id: "VIRC-PLN-0005"
type: "PLAN"
domain: "VIRC"
title: "Eliminate redundant include and selective import pairs across compiler sources"
status: "COMPLETED"
created: "2026-10-02"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "module-resolution"
  - "compiler-source-layout"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0007"
  plans: []
  reports:
    - "VIRC-RPT-0017"
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "dependency-cleanup"
  - "module-identity"
  - "architecture-check"
---

# VIRC-PLN-0005 — Eliminate redundant include and selective import pairs across compiler sources

## 1. Objective

Enforce a single, disciplined dependency declaration per canonical module across the entire compiler source tree (`compiler/src/**/*.vri`), resolving [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md).

Specifically:
- Establish that a caller requiring exported symbols uses solely `import ... from M` without an adjacent or preceding `include M`.
- Establish that a caller requiring whole-module loading uses solely `include M` without a following selective `import ... from M`.
- Provide an automated deterministic architecture checker to detect and reject any duplicate/redundant same-module `include`/`import` pairs.
- Cleanly eliminate redundant declarations across all affected files in `compiler/src/`, re-synchronize the canonical generated bundle, and verify 3-stage self-hosting fixed point.

## 2. Source Issues

- `VIRC-ISS-0007` — Compiler sources redundantly combine include with selective import.

## 3. Scope

### In Scope

- All canonical compiler source files under `compiler/src/**/*.vri`.
- Architecture check tooling (`tools/check_module_dependencies.py` or integrated check in `tools/check_pass_architecture.py`).
- Preprocessor behavior verification for include-only, import-only, and diamond dependency topologies.
- Synchronization of `compiler/generated/virc.vri` via `tools/sync_virc.py`.
- Full CLI contract test suite (`tests/cli_contract/runner.py`) and 3-stage self-host fixed-point verification.

### Out of Scope

- Standard library redesign (`stdlib/**`); standard library remains unchanged except where affected by compiler resolution contracts.
- Fixing empty-export fallback tracked by `VIRC-ISS-0008` (handled as an independent follow-up).
- Language syntax changes to `include` or `import` keywords.

## 4. Current Architecture

1. **Preprocessor Splice Model**:
   - `compiler/src/main.vri` runs `expand_includes_text` first, which finds `include M`, resolves `M` through `module.list` or stdlib, splices `M`'s body into the source text, and records `M` in `g_inc_has`.
   - Next, `expand_imports_text` finds `import ... from M`. If `M` is already present in `g_inc_has` (because `include M` ran), it enters the `alias_only=1` branch. For non-aliased symbols, it skips emission and splices an empty string.
2. **Current Defect**:
   - In 88 out of 106 canonical `.vri` files in `compiler/src/`, an `include M` is immediately followed by `import ... from M`.
   - The selective import is rendered operationally redundant by the preceding include.
   - Conversely, `expand_imports_text` is fully capable of resolving `M`, validating exports, and extracting `func`, `entity`, `enum`, `const`, `extern func`, `var`, and `let` declarations on its own without any preceding `include M`.
   - The dual declaration clutters pass modularization (such as ongoing work under `VIRC-PLN-0004`), creates ambiguous dependency graphs, and bypasses export visibility checks.

## 5. Proposed Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      compiler/module.list                              │
│         (Single source of truth for flat compiler module identities)   │
├────────────────────────────────────────────────────────────────────────┤
│  root = .                                                              │
│  typecheck_context      = src/semantic/typecheck/context.vri           │
│  typecheck_generics     = src/semantic/typecheck/generics.vri          │
│  typecheck_calls        = src/semantic/typecheck/calls.vri             │
│  sem_pass6_typecheck    = src/semantic/sem_pass6_typecheck.vri         │
│  ...                                                                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Flat Include Resolution
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
┌───────────────────────────────────┐   ┌──────────────────────────────────┐
│ Subsystem Hub (typecheck_context) │   │ Subsystem Orchestrator (pass 6)  │
├───────────────────────────────────┤   ├──────────────────────────────────┤
│ include types                     │   │ include typecheck_context        │
│ include vec_rt                    │   │ include typecheck_generics       │
│ include string_rt                 │   │ include typecheck_calls          │
│ include parser                    │   │ ...                              │
│ include type_table                │   │ (Zero redundant selective import)│
└─────────────────┬─────────────────┘   └──────────────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────┐
│ Subsystem Leaf (typecheck_calls)  │
├───────────────────────────────────┤
│ include typecheck_context         │
│ include typecheck_index           │
│ include typecheck_compatibility   │
│ (Zero directory paths, zero dupes)│
└───────────────────────────────────┘
```

1. **Flat Include Invariant**:
   - In `.vri` compiler code, no physical directory paths (`compiler/src/...` or `../../...`) or dotted directory structures are exposed.
   - All includes use flat identifiers registered in `compiler/module.list` or canonical stdlib names (`stdlib/stdlib.vri`).
2. **Subsystem Hub Architecture**:
   - Each compiler subsystem maintains a designated Hub module (e.g. `typecheck_context`) that pulls foundational types and runtime.
   - Sibling submodules include only the Hub and immediate sibling dependencies.
   - Subsystem orchestrators include the Hub and its submodules.
3. **Single-Declaration Invariant**:
   - No file may declare both `include M` and `import ... from M` for the same module.
   - When a module is loaded via `include`, all symbols are available in the unit; redundant `import ... from` is prohibited.
4. **Foundation for Dead Code Analysis**:
   - Flat registry mapping enables deterministic dependency graph construction to detect unreferenced modules (dead modules) and uncalled definitions (dead code).

## 6. Design Decisions

### Decision 1 — Centralized Hub and Flat Include via module.list (Approach 3)

**Decision:** Adopt centralized subsystem Hubs with flat module names registered in `compiler/module.list`. Eliminate redundant selective imports in favor of clean Hub includes.

**Rationale:**
- Keeps individual `.vri` files minimal, concise, and decoupled from physical directory layouts.
- Preprocessor's canonical ID registry (`project::...`) natively handles deduplication and cycle prevention.
- Eliminates fragile multi-line `import` lists and line-number drift in generated bundle tooling (`sync_virc.py`).
- Creates an organized, disciplined dependency tree that accelerates pass modularization under `VIRC-PLN-0004`.

**Alternatives considered:**
- *Approach 1 (Keep selective imports, eliminate includes):* Rejected due to extreme boilerplate (20-30 imported symbols per pass), bundle sync marker fragility, and lack of whole-subsystem cohesion.
- *Approach 2 (Bare includes with relative directory paths):* Rejected because leaking directory paths (`../../...`) creates tight coupling to filesystem layout and clutters refactoring.

### Decision 2 — Deterministic checker in repository CI

**Decision:** Create `tools/check_module_dependencies.py` and link it to `tools/check_pass_architecture.py`.

**Rationale:** Automated validation ensures no redundant include/import pairs are re-introduced and verifies all included modules are registered in `compiler/module.list`.

## 7. Implementation Plan

### Phase 1 — Architecture Checker & Test Fixtures

- Create `tools/check_module_dependencies.py`:
  - Scans all `.vri` files in `compiler/src/`.
  - Parses `include` targets and `import ... from` targets.
  - Normalizes module names to detect direct matches and alias equivalences.
  - Flags any file containing both `include M` and `import ... from M`.
- Create test fixtures in `tests/modules/`:
  - `test_include_only.vri`: verifies whole-module load (functions, entities, constants).
  - `test_import_only.vri`: verifies selective import without preceding include.
  - `test_diamond_dedup.vri`: verifies deduplication and cycle prevention.

### Phase 2 — Migrate Semantic & Typecheck Modules

- Update recently created typecheck leaf modules and orchestrators (`sem_pass6_typecheck.vri`, `typecheck/*.vri`):
  - Remove redundant `include` statements preceding `import` from stdlib runtime (`vec_rt`, `string_rt`) and compiler modules (`virc.semantic.*`).
- Verify each module compiles cleanly under the new rule.

### Phase 3 — Migrate All Remaining Compiler Sources

- Systematically audit and remove redundant `include` statements across all remaining files in `compiler/src/` (frontend, ir, lower, backend, cli, diagnostic, ide).
- Run `python3 tools/check_module_dependencies.py` to ensure zero redundant pairs remain.

### Phase 4 — Bundler Synchronization & Rebuild

- Update `tools/sync_virc.py` if necessary to ensure clean handling of pure-import modular sources.
- Synchronize `compiler/generated/virc.vri`.
- Recompile `bin/virc` using trusted bootstrap compiler.
- Run `tests/cli_contract/runner.py` (43/43 PASS).

### Phase 5 — Verification & Closure

- Perform 3-stage self-hosting test (Stage 1 -> Stage 2 -> Stage 3 fixed point).
- Produce VIRC-REP report and update VIRC-ISS-0007 status.

## 8. Compatibility

- Source compatibility: User Vir code is unaffected. The checker only targets `compiler/src/`.
- Compiler ABI & Codegen: Generated machine code is identical because `expand_imports_text` already produces the same AST whether preceded by include or not.
- Diagnostics: Error line locations remain accurate via `# @vir_source` markers.

## 9. Migration

- All 88 canonical compiler modules with redundant `include`/`import` pairs are mechanically migrated in Phase 2 and 3.
- No public user module or stdlib path is altered during this compiler-internal cleanup.

## 10. Validation Plan

1. `python3 tools/check_module_dependencies.py` returns 0 violations.
2. `tests/modules/` positive and negative fixtures pass.
3. Unit test fixtures in `tests/typecheck/` pass.
4. CLI contract test suite `python3 tests/cli_contract/runner.py` (43/43 PASS).
5. Self-host 3-stage build passes fixed point (`cmp bin/virc.s2 bin/virc.s3`).

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A module depends on unexported symbols that were silently imported via include | Low | Med | Audit symbol lists; add explicit exports or retain include if whole-module load is intentional |
| Preprocessor fails on diamond selective imports | Low | Med | Test with diamond dependency fixture before batch source cleanup |

## 12. Rollback Strategy

If any unresolvable preprocessor defect is discovered, git revert the cleanup commit and re-apply include statements; the modular sources remain intact and independently functional.

## 13. Exit Criteria

- [x] `tools/check_module_dependencies.py` implemented and passing with 0 violations.
- [x] No file in `compiler/src/` contains adjacent or redundant `include` + `import` for the same module.
- [x] `tests/cli_contract/runner.py` passes 43/43.
- [x] Self-hosting compiler rebuilds and passes fixed point.
- [x] VIRC-ISS-0007 acceptance criteria met.
- [x] Ready to resume VIRC-PLN-0004 with clean, disciplined import rules.

## 14. Related Papers

- `VIRC-ISS-0007` — Compiler sources redundantly combine include with selective import.
- `VIRC-ISS-0006` — Compiler sources are coupled to stdlib and oversized pass files.
- `VIRC-ISS-0008` — Selective imports accept symbols that are not exported.
- `VIRC-PLN-0004` — Separate compiler source tree and modularize compiler passes.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-02 | Initial plan drafted from VIRC-ISS-0007 context and preprocessor audit |
| 2026-10-03 | Linked VIRC-RPT-0017 |
| 2026-10-03 | Completed all phases; verified with bit-identical stage 2/stage 3 fixed point; linked VIRC-RPT-0017 |
