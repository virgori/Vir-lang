---
id: "VIRC-RPT-0060"
type: "REPORT"
domain: "VIRC"
title: "Enforce fail-closed private by default module export contract report"
status: "ACCEPTED"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
  - "frontend"
  - "tooling"
components:
  - "module-resolution"
  - "import-expander"
  - "diagnostics"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0008"
  plans:
    - "VIRC-PLN-0043"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "import"
  - "export"
  - "visibility"
  - "fail-closed"
  - "e2113"
  - "private-by-default"
---

# VIRC-RPT-0060 — Enforce fail-closed private by default module export contract report

## 1. Executive Summary

`VIRC-ISS-0008` is resolved. Selective imports now treat a module without an
`export` declaration as having an empty public surface. A requested private or
missing declaration fails at the import site with `E2113`, including the
requested symbol and module identity in classic and JSON diagnostics.

The final implementation also closes the less obvious visibility leak created
when a selectively imported provider contains nested `include` or `import`
dependencies. The compiler may retain that provider's implementation closure
so an exported declaration can call private helpers, but semantic name
resolution uses physical source provenance and explicit import bindings to
prevent the consumer from calling those helpers directly.

Corrective verification found and fixed two compatibility cases before final
acceptance: canonical module identities coalesced between public includes and
selective imports, and aliases introduced by a second selective import of an
already-loaded provider.

## 2. Source Issues

- `VIRC-ISS-0008` — Selective imports accept symbols that are not exported.

## 3. Source Plans

- `VIRC-PLN-0043` — Enforce fail-closed private-by-default module export
  contract on selective import.

## 4. Implementation Summary

### 3.1 Fail-closed export validation

- `text_has_export` returns false when the provider has no exports.
- Every requested selective-import symbol is validated before any provider
  declaration or dependency is copied into the consumer.
- Private and missing symbols report `E2113` at the import statement.
- Direct-path spellings, registry aliases, preceding includes, repeated
  imports, and diamond dependency shapes use the same validation rule.

### 3.2 Nested dependency visibility

Providers with nested dependencies retain their implementation bodies so
exported declarations can continue to call private helpers. The compiler
records restricted provider paths, explicit local bindings, nested include
relationships, public include paths, and canonical `module` identities.

Pass 3 filters expression-level name resolution using source-manager spans.
Provider-internal references and explicit consumer bindings remain valid;
consumer access to unexported declarations resolves as undefined. If pass 2
coalesces duplicate declarations with the same canonical module identity, a
publicly included copy preserves the public include closure rather than being
mistaken for a private selective-import copy.

### 3.3 Repeated imports and aliases

When a provider is already loaded by an earlier selective import, a later
alias-only import now registers its additional binding without changing a
provider previously loaded through public `include`. This behavior is covered
by `test_import_repeated_alias_positive.vri` and the existing memory contract
that imports `Arena`, `arena_alloc`, and `arena_reserve` in separate statements.

### 3.4 Diagnostics and lifecycle

- `g_imp_failed_sym` is reset between compiler sessions.
- `E2113` carries `'<symbol>' from module '<module>'` in classic and JSON modes.
- Compiler and stdlib modules that intentionally expose APIs have explicit
  export declarations; the selective-import export-all fallback is removed.
- `compiler/generated/virc.vri` is synchronized with the modular sources.
- The internal compiler version is `2026.1.15`.

## 5. Changes by Component

### Import and include expansion

`compiler/src/main/import_expander.vri` performs fail-closed validation,
registers selective bindings including repeated aliases, and retains nested
implementation closures. `compiler/src/main/include_expander.vri` records
physical include relationships and canonical module identities.

### Semantic name resolution

`compiler/src/semantic/names/context.vri` owns the per-session visibility
metadata. `compiler/src/semantic/names/walk_expr.vri` applies the visibility
filter to identifiers, calls, enum receivers, entity literals, and enum access.
Driver and IDE session entry points reset the metadata between analyses.

### Runtime and generated source

The compiler and stdlib export migration is reflected in the synchronized
generated bundle. `stdlib/vir/thread/thread.vri` provides the native-backed
channel compatibility API required by the explicit export surface.

### Tests and fixtures

Coverage includes zero-export and partial-export providers; exported functions,
constants, entities, enums, and aliases; missing and private symbols; direct
paths and registry IDs; preceding and repeated imports; nested imported and
included private dependencies; and a positive nested dependency whose exported
API calls private helpers.

The focused fixtures are registered in `tests/modules/module.list` and executed
by group 3 in both minimum and full test modes.

## 6. Deviations from Plan

The plan expected declaration extraction to be sufficient. Corrective testing
showed that extracting only the requested declaration breaks valid exported
functions that depend on private helpers. The delivered design therefore keeps
the provider implementation closure and enforces its public boundary during
semantic name resolution using source provenance.

The initial report also treated a placeholder `Channel` shim as acceptable.
The final source wires `Channel`, `chan_new`, `send`, and `recv` to native
channel operations so export migration does not replace runtime semantics with
a stub.

## 7. Verification

- Modular compiler semantic check: PASS with zero diagnostics.
- Module/import group: `40/40 PASS`.
- Native module resolver and dependency DAG suite: `20/20 PASS`.
- Native CLI contract suite: `40 PASS / 0 FAIL`, including compiler fact-index
  growth and reset.
- Native memory contract suite: `149 PASS / 0 FAIL`; this includes
  `MEM-OVERFLOW-001`, which exercises separate repeated alias imports.
- Broad minimum suite before the repeated-alias correction: `516/517`; its only
  failure was `MEM-OVERFLOW-001`. After correction, the full native memory suite
  passed `149/149`, and the affected module suite passed `40/40`.
- Version policy, source/bundle synchronization, and version bump checks: PASS.
- Self-host fixed point: stage 2 and stage 3 are byte-identical after signing
  with the same identifier. Both stages and installed `bin/virc` have SHA-256
  `5ec84adf8521ec2b8b1fc3a88abbe8296b78d2b46eb29cb2898394291d3a628c`.

## 8. Acceptance Criteria

- [x] No-export providers reject selective imports with `E2113`.
- [x] Explicitly exported declarations import and execute successfully.
- [x] Existing private and missing declarations are rejected.
- [x] Include, path, registry, repetition, and dependency topology do not
  bypass export validation.
- [x] Classic and JSON diagnostics identify symbol and module at the import
  site.
- [x] Functions, constants, entities, enums, aliases, and nested dependencies
  have positive and negative coverage.
- [x] Intentional compiler and stdlib APIs use explicit exports; no blanket
  selective-import export-all fallback remains.
- [x] Modular and generated sources are synchronized and self-hosting reaches
  a byte-identical fixed point.

## 9. Known Limitations

Whole-module and umbrella import syntax remains governed by `VIRC-ISS-0046`.
This report does not redefine `include` as selective import; it only ensures
that combining the two mechanisms cannot bypass an explicit selective-import
export check.

## 10. Remaining Work

No remaining work is required within the scope of `VIRC-ISS-0008`.

## 11. Conclusion

`ACCEPTED — READY_FOR_CLOSE`

## 12. Related Papers

- [VIRC-ISS-0008](../issues/VIRC-ISS-0008_selective_imports_accept_symbols_that_are_not_exported.md)
- [VIRC-PLN-0043](../plans/VIRC-PLN-0043_enforce_fail_closed_private_by_default_module_export_contract_on_selective_impor.md)
- [VIR-SPC-0014](../../VIR/specs/VIR-SPC-0014_module_system.md)

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Initial implementation report created |
| 2026-10-10 | Corrected after origin-aware visibility, canonical module identity, repeated-alias, CLI, memory, and fixed-point verification |
