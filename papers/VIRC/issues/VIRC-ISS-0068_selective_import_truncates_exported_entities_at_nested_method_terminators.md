---
id: "VIRC-ISS-0068"
type: "ISSUE"
domain: "VIRC"
title: "Selective import truncates exported entities at nested method terminators"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "compiler"
components:
  - "source-preprocessing"
  - "selective-import"
  - "declaration-extraction"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0018"
  plans:
    - "VIRC-PLN-0045"
  reports:
    - "VIRC-RPT-0062"
supersedes: null
superseded_by: null
tags:
  - "import"
  - "entity"
  - "method"
  - "source-boundary"
---

# VIRC-ISS-0068 — Selective import truncates exported entities at nested method terminators

## 1. Summary

Selective import of an explicitly exported `entity` fails when the entity body
contains an inherent method. The import preprocessor extracts the declaration
only through the method's first nested `end.` instead of the entity's matching
outer `end.`, then passes an incomplete aggregate to the parser. Valid source is
therefore rejected with a misleading end-of-file parser diagnostic.

## 2. Context

Vir permits methods inside an entity and permits selective import of exported
types. `VIR-SPC-0018` sections 3.3 and 7.2 make these contracts independent:
`import Counter from model` selects the exported type, while the complete
entity definition includes its fields and inherent methods.

The native source preprocessor implements selective declaration import in
`compiler/src/main/import_expander.vri`. `text_extract_func()` handles
functions, entities, enums, constants, and variables through textual slicing;
the selective-import path calls it for every requested exported symbol.

This issue concerns declaration-boundary extraction only. It does not decide
whether Vir entities should gain private members, opaque exports, class-like
semantics, or any other visibility model.

## 3. Expected Behavior

- `import Counter from model` imports the complete exported entity declaration,
  including every field and inherent method through the entity's matching
  outer `end.`.
- The imported entity compiles and behaves consistently with the same provider
  reached through the valid `include model` control.
- Nested method bodies must not terminate aggregate extraction.
- Existing export enforcement remains fail-closed: an unexported or missing
  type is still rejected with the selective-import diagnostic.
- Source provenance and diagnostics continue to identify the provider and
  consumer locations accurately.

## 4. Actual Behavior

The following behavior is historical and applies to compiler `2026.1.16`:

- On compiler `2026.1.16`, the provider module parsed and type-checked successfully by itself.
- On compiler `2026.1.16`, the `include model` control parsed and type-checked successfully.
- On compiler `2026.1.16`, the equivalent `import Counter from model` consumer failed during parsing with
  `E1001: expected 'end' after entity (at end of file)` at the consumer EOF.
- Inspection of the historical expanded declaration path showed that the imported chunk
  ends at the nested method's `end.` and omits the entity's outer terminator.

## 5. Reproduction

Create `/private/tmp/virc_entity_import_method_repro/module.list`:

```text
root = .
model = model.vri
```

Create `model.vri`:

```vir
entity Counter:
    value: int

    method read() -> int:
        out this.value
    end
end.

export Counter
```

Create `main_import.vri`:

```vir
import Counter from model

func main:
    var counter = Counter(value: 42)
    print counter.read()
end.
```

Create the include control `main_include.vri` by replacing the first line with
`include model`, then run:

```sh
./bin/virc /private/tmp/virc_entity_import_method_repro/model.vri \
  --check --json --color=never
./bin/virc /private/tmp/virc_entity_import_method_repro/main_include.vri \
  --check --json --color=never
./bin/virc /private/tmp/virc_entity_import_method_repro/main_import.vri \
  --check --json --color=never
```

## 6. Evidence

- CONFIRMED: provider control exits 0 with no diagnostics.
- CONFIRMED: include control exits 0 with no diagnostics.
- CONFIRMED: selective-import reproduction exits 1 with `E1001`, parser phase,
  at `main_import.vri:7:1`.
- CONFIRMED: `compiler/src/main/import_expander.vri:378-384` scans forward to
  the first byte sequence `end.` followed by a statement boundary and returns
  that range without tracking nested definition depth.
- CONFIRMED: `compiler/src/main/import_expander.vri:885` uses this extractor for
  the requested exported symbol before parsing the combined consumer source.
- OBSERVED on 2026-10-10: compiler `2026.1.16`, binary SHA-256
  `61c6252b112ed60cf8bb6b5840ec6050ca746e4472e05f09d6c959c43b3692fb`,
  repository HEAD `40746bb560b52cba2f57ffa6adb1bc3d6d4471cd` with an existing dirty
  working tree.
- OBSERVED: a selectively imported exported entity with fields but no method
  compiles and executes, so the failure is triggered by the nested definition
  terminator rather than by entity-kind import support in general.

## 7. Scope

### Affected

- selective import of exported entities containing inherent methods;
- textual declaration-boundary extraction in the import preprocessor;
- parser diagnostics and source provenance after an incomplete imported chunk;
- generic or packed aggregate forms if they use the same extraction path.

### Not affected / Unknown

- Provider parsing and the include control are confirmed healthy for the
  reproduction.
- Plain exported entities without methods are confirmed importable.
- Entity visibility, privacy, opacity, and class-like semantics are explicitly
  outside this issue and remain undecided.
- Generic entities, packed entities, nested comment/string decoys, and
  multiple-method boundaries are covered by the accepted regression fixture.
- Interface and callable-field semantics are unchanged and outside this defect.
- NOT_VERIFIED: whole-module namespace import behavior tracked separately by
  `VIRC-ISS-0065`.

## 8. Impact

Libraries cannot selectively export and import a behavior-bearing entity as a
type. The failure is a valid-source rejection with a diagnostic pointing to
the consumer's end of file rather than the provider declaration that was
truncated. `include` is a temporary control/workaround, but it has different
module-composition semantics and is not an equivalent long-term replacement
for selective import.

## 9. Preliminary Analysis

- CONFIRMED: the imported chunk is produced by a textual first-`end.` scan that
  is not aware of nested definition boundaries.
- CONFIRMED: the nested method terminator satisfies that scan and causes the
  incomplete entity presented to the parser.
- OBSERVED: the resulting diagnostic is classified as a parser failure in the
  consumer rather than an import-expansion failure in the provider.
- HYPOTHESIS: a balanced definition-boundary scanner or structured declaration
  extraction can preserve the complete aggregate while retaining current
  export checks and source markers. The implementation choice requires a PLAN.
- NOT_VERIFIED: whether other nested-definition-capable declarations share the
  same truncation mode or require separate extraction rules.

## 10. Acceptance Criteria

- [x] A native checked-in fixture selectively imports an explicitly exported
  entity containing at least one method, constructs it, calls the method, and
  verifies the expected runtime result.
- [x] Extraction retains the entity's matching outer `end.` and every nested
  method body, independent of the number of methods.
- [x] A method containing nested statement blocks does not truncate or extend
  the imported declaration incorrectly.
- [x] Generic entity coverage establishes whether the same import contract is
  supported and rejects unsupported forms with a precise fail-closed error.
- [x] Missing and unexported entity imports remain rejected under the existing
  private-by-default module export contract.
- [x] Provider, include-control, direct-path compatibility, source-marker, and
  machine-JSON diagnostic regressions pass.
- [x] Group 3 module tests, compiler source self-check, generated-source sync,
  and fixed-point bootstrap pass on the corrected compiler.
- [x] No entity privacy, opacity, or class-semantics decision is introduced as
  part of this compiler defect fix.

## 11. Related Papers

### Issues

- `VIR-ISS-0018` — canonical member terminator and standalone-method decision.

### Plans

- `VIRC-PLN-0045` — implementation and verification plan.

### Reports

- `VIRC-RPT-0062` — accepted implementation and verification evidence.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Opened from a focused provider/include/selective-import control showing nested method terminator truncation |
| 2026-10-10 | Linked VIRC-PLN-0045 |
| 2026-10-10 | Linked VIR-ISS-0018 |
| 2026-10-10 | Linked VIRC-RPT-0062 |
| 2026-10-10 | Closed on compiler 2026.1.17 after native regressions and exact fixed-point bootstrap |
