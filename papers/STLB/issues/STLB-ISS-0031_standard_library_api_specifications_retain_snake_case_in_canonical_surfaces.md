---
id: "STLB-ISS-0031"
type: "ISSUE"
domain: "STLB"
title: "Standard-library API specifications retain snake_case in canonical surfaces"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
components:
  - "api-registry"
  - "public-api"
  - "naming"
  - "documentation"
  - "validation"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "api-spec"
  - "snake-case"
  - "camel-case"
  - "governance"
---

# STLB-ISS-0031 — Standard-library API specifications retain snake_case in canonical surfaces

## 1. Summary

Existing standard-library API registry documents still publish `snake_case`
identifiers in canonical API rows, signatures, parameter names, and examples.
The drift contradicts the registry's established dot-style and `camelCase`
public naming direction and is not consistently distinguishable from permitted
legacy or internal names.

## 2. Context

`stdlib/registry/SCHEMA.md` defines the API registry as the user-facing API
reference source of truth. `VIR-SPC-0020` now defines the global naming
contract for public functions, methods, fields, parameters, types, and
constants. Individual registry documents state that new public APIs use
dot-style namespaces and that legacy `snake_case` functions belong only in
migration, `previous:`, or internal evidence.

The registry still lacks a machine-checkable validation gate for that contract.
This issue covers the specification-alignment and validation gap; it does not
require legacy implementation functions to be renamed merely because they are
recorded in migration maps.

## 3. Expected Behavior

- Canonical public module and API identities use dot-style namespaces.
- Multiword public functions, methods, fields, and parameter names use
  `camelCase`; public type names use `PascalCase`.
- `snake_case` may appear only where explicitly classified as legacy,
  previous, internal, native/FFI, source evidence, or migration input.
- API index rows, detailed signatures, parameter headings, and examples agree
  on the same canonical spelling.
- Validation rejects new canonical `snake_case` drift without flagging
  migration history.

## 4. Actual Behavior

The 2026-10-09 audit found these canonical occurrences:

- `stdlib/registry/net.md` previously used `net.socketAddr` as the target ID and
  published the stable symbol/signature `socket_addr`. The canonical registry
  target is now `net.socketAddress`; the source rename is still outstanding.
- `stdlib/registry/buffer.md:214,1142,1153`: `buffer.truncate` publishes
  parameter `new_len`.
- `stdlib/registry/fs.md:320,1060,1067,1071`: `fs.rename` publishes
  parameters `old_path` and `new_path`.
- `stdlib/registry/cli.md:236-241,365-373`: canonical API examples call
  `vec_new`, `vec_push`, `vec_get`, and `vec_len`.
- `stdlib/registry/cli.md:278-279`: required-behavior pseudocode calls
  `disable_echo` and `restore_echo` without marking them as internal or
  migration-only.

No top-level public `module:` value and no canonical detailed-entry `id:`
or `api:` metadata field contained `snake_case` in the same audit.

## 5. Reproduction

Run from the repository root:

```sh
rg -n '^module:\\s*[^#]*_' stdlib/registry/*.md
rg -n '^(api:|id:)\\s*[^[:space:]]*_[^[:space:]]*' stdlib/registry/*.md
rg -n '^#### `[^`]*_[^`]*:' stdlib/registry/*.md
rg -n 'socket_addr|new_len|old_path|new_path|vec_new|vec_push|vec_get|vec_len|disable_echo|restore_echo' \
  stdlib/registry/*.md
```

To classify results, inspect each occurrence in its API index, detailed entry,
parameter heading, example, or migration context. A raw repository-wide
underscore count is not sufficient because migration evidence is intentionally
retained.

## 6. Evidence

- CONFIRMED: active source still exports `socket_addr`; the registry now records
  the canonical target as `net.socketAddress` and classifies the old spelling
  as migration input.
- CONFIRMED: the buffer and filesystem underscore names occur in both API index
  signatures and their detailed parameter contracts.
- CONFIRMED: the CLI underscore calls occur inside examples or required
  behavior for canonical API entries, not in a migration-map column.
- CONFIRMED: `stdlib/registry/report/AUDIT.md` states that new public APIs use
  dot style and legacy snake functions are migration debt.
- CONFIRMED: `crypto.md`, `net.md`, `pattern.md`, and related registry
  documents independently state camel/dot-style public naming direction.
- CONFIRMED: `VIR-SPC-0020` defines the global public-identifier naming rule;
  `stdlib/registry/SCHEMA.md` does not yet enforce it mechanically.
- OBSERVED: migration tables contain many intentional `snake_case` source
  names and must not be treated as violations.
- NOT_VERIFIED: whether every narrative-only pseudocode identifier denotes a
  future public API rather than an internal implementation step.

## 7. Scope

### Affected

- canonical API rows, detailed signatures, parameter headings, and examples in
  `stdlib/registry/*.md`;
- the global STLB public naming contract;
- schema/check tooling needed to prevent recurrence;
- migration maps where canonical and legacy columns are currently ambiguous.

### Not affected / Unknown

- legacy source names recorded in `Current`, `Legacy`, `previous:`, or
  implementation-source fields;
- private helpers, native symbols, backend ABI names, and FFI symbols explicitly
  classified as internal;
- source-level API renames before compatibility and migration plans are
  approved;
- filenames and ordinary prose that are not public identifiers.

## 8. Impact

The registry can teach or generate conflicting spellings for the same API.
Consumers may copy noncanonical names, documentation generators cannot reliably
distinguish target APIs from migration debt, and future API reviews lack an
automatic gate preventing additional naming drift.

## 9. Preliminary Analysis

- CONFIRMED: at least four registry documents contain canonical or
  canonical-adjacent `snake_case` identifiers.
- CONFIRMED: the drift includes one stable symbol, three canonical parameter
  names, and multiple example/pseudocode calls.
- HYPOTHESIS: local naming rules without a global schema constraint allowed
  independently authored documents to diverge.
- NOT_VERIFIED: whether a source compatibility window is required for
  `net.socketAddress` and its former `socket_addr` / `socketAddr` spellings;
  that belongs in a PLAN after the actual exports and callers are inventoried.

## 10. Acceptance Criteria

- [x] Define a normative naming rule covering public modules, types, functions,
  methods, fields, parameters, constants, recognized technical acronyms, and
  explicitly allowed legacy/internal/native exceptions in `VIR-SPC-0020`.
- [ ] Align `net.socketAddress` ID, symbol, signature, detailed entry, source
  migration map, and external consumer test on the full-word canonical
  spelling; do not retain `socketAddr` as the target name.
- [ ] Rename canonical documentation parameters to `newLen`, `oldPath`, and
  `newPath` while preserving any source spellings only as migration evidence.
- [ ] Rewrite CLI examples to use canonical collection APIs and classify or
  replace `disable_echo` / `restore_echo` as public, internal, or
  migration-only names.
- [ ] Audit every top-level registry document so no unclassified
  `snake_case` remains in API IDs, symbols, signatures, parameter headings,
  public fields, or canonical examples.
- [ ] Preserve legacy names in explicit migration or `previous:` fields; do
  not erase compatibility provenance.
- [ ] Add a deterministic registry naming check that distinguishes canonical
  fields from allowed migration/internal evidence and fails on a seeded
  canonical `snake_case` fixture.
- [ ] Run the registry schema checks, documentation checks, external consumer
  tests for affected modules, `./paper registry --check`, and
  `./paper validate`.
- [ ] A VPS PLAN and verification REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- None yet.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Linked the active `VIR-SPC-0020` naming contract and corrected the `net.socketAddress` canonical target |
| 2026-10-09 | Opened from a field-aware audit of canonical API registry naming |
