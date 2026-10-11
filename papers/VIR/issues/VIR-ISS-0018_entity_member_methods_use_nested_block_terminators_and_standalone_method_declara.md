---
id: "VIR-ISS-0018"
type: "ISSUE"
domain: "VIR"
title: "Entity member methods use nested block terminators and standalone method declarations are invalid"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "language"
  - "compiler"
components:
  - "syntax"
  - "entity"
  - "parser"
  - "migration"
related:
  issues:
    - "VIRC-ISS-0068"
  plans:
    - "VIRC-PLN-0045"
  reports:
    - "VIRC-RPT-0062"
supersedes: null
superseded_by: null
tags:
  - "method"
  - "terminator"
  - "entity"
  - "ufcs"
---

# VIR-ISS-0018 — Entity member methods use nested block terminators and standalone method declarations are invalid

## 1. Summary

Active Vir specifications classify `method` as an entity member but also give
it the top-level definition terminator `end.`. That makes the nested member
look like an independently closed declaration, creates ambiguous textual
entity boundaries, and conflicts with the language's existing distinction
between nested statement blocks (`end`) and top-level declarations (`end.`).

## 2. Context

`VIR-SPC-0017` and `VIR-SPC-0018` define inherent methods only inside an
`entity`; method-like behavior outside an entity is provided by a free `func`
through UFCS. Nevertheless, the parser also contains a legacy top-level
`TokType.Method` branch, and `parse_func_def_mode()` accepts both `end` and
`end.` in every context. `VIRC-ISS-0068` exposed the practical consequence:
selective import cannot distinguish a nested method's `end.` from the entity's
outer `end.` without adding structure that the syntax should already express.

## 3. Expected Behavior

- A method declared inside an entity closes with `end`.
- The containing entity remains the declaration boundary and closes with
  `end.`.
- `method` is invalid at module/top level. Authors use `func` with an explicit
  first receiver parameter for UFCS behavior outside an entity.
- Interface signatures remain bodyless members owned by the interface block.
- The parser reports a focused migration diagnostic for legacy nested
  `end.` and top-level `method` spellings.

## 4. Actual Behavior

The following behavior is historical and applies to compiler `2026.1.16`:

- Normative specifications required `end.` for both methods and their
  containing entity.
- Compiler `2026.1.16` accepted a nested method closed by either `end` or `end.`.
- Compiler `2026.1.16` accepted `method orphan ... end.` at module scope and lowered it as
  an ordinary callable even though no entity owner exists.
- Selective import currently truncates an entity at the first nested `end.`.

## 5. Reproduction

Compile these two forms with `virc 2026.1.16`:

```vir
entity Counter:
    value: int
    method read() -> int:
        out this.value
    end
end.
```

```vir
method orphan() -> int:
    out 7
end.
```

Both are currently accepted. The first is the intended canonical nesting; the
second is outside the active language model and must be rejected.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0017` §7.2 and `VIR-SPC-0018` §7.2 define methods
  inside entities and direct external method-like calls through free-function
  UFCS.
- CONFIRMED: `compiler/src/frontend/parser/stmt_dispatch.vri:116-120`
  accepts `method` at general statement/module scope.
- CONFIRMED: `compiler/src/frontend/parser/stmt_decl/aggregate_def.vri:234-239`
  parses entity methods through the general function parser.
- CONFIRMED: `compiler/src/frontend/parser/stmt_decl/func_def.vri:483-492`
  consumes `end` with an optional dot in all function/member contexts.
- OBSERVED: on compiler `2026.1.16`, both the canonical nested `end` example
  and a top-level `method orphan ... end.` compile and execute successfully.
- CONFIRMED: `VIRC-ISS-0068` records an entity import truncated at a nested
  method's dotted terminator.

## 7. Scope

### Affected

- `method` grammar and terminator ownership;
- entity and packed-entity method parsing;
- diagnostics for legacy nested dotted terminators and top-level methods;
- active English, Vietnamese, and function specifications;
- repository source/test migration and selective-import regression coverage.

### Not affected / Unknown

- Entity privacy, opacity, inheritance, or class semantics.
- UFCS removal; free functions remain callable through dot syntax.
- Interface signature bodies and callable-field semantics.

## 8. Impact

The current grammar obscures ownership of the nested member boundary and
causes valid selective imports to fail. It also exposes an undocumented
top-level `method` form that behaves like a second spelling of `func` without
an entity owner. The correction is source-breaking for legacy `end.` method
bodies, but the migration is mechanical: remove the dot from the method's own
terminator; retain the entity's final dot.

## 9. Preliminary Analysis

- CONFIRMED: the active semantic model needs no standalone `method`; UFCS
  already covers external extension behavior with `func`.
- CONFIRMED: nested `end` already parses and runs today, so the target syntax
  does not require a lexer change.
- CONFIRMED: context-specific parser enforcement is needed because the shared
  function parser currently accepts an optional dot everywhere.
- HYPOTHESIS: making method/member termination structurally distinct removes
  the need for nested dotted-definition balancing in selective import.
- NOT_VERIFIED: whether every legacy stdlib method fixture is currently part of
  a production release gate; repository-wide migration will be validated.

## 10. Acceptance Criteria

- [x] Active English, Vietnamese, and function specifications state that an
  entity method closes with `end`, while the entity closes with `end.`.
- [x] The specifications state that `method` is not valid at module scope and
  direct users to free-function UFCS.
- [x] The parser accepts canonical nested methods and rejects their dotted
  legacy terminator with a focused diagnostic.
- [x] The parser rejects top-level `method` with a focused diagnostic.
- [x] Entity and packed-entity method sources in active stdlib/tests are
  migrated without changing behavior.
- [x] Selective import of an exported entity with multiple canonical methods
  succeeds for registered and direct-path modules.
- [x] Compiler self-check, relevant native suites, generated-source sync, and
  bootstrap fixed point pass.

## 11. Related Papers

### Issues

- `VIRC-ISS-0068` — selective-import truncation exposed by dotted nested
  method terminators.

### Plans

- `VIRC-PLN-0045` — compiler/spec migration and verification plan.

### Reports

- `VIRC-RPT-0062` — accepted implementation and verification evidence.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-10 | Opened and moved to implementation after compiler/spec audit |
| 2026-10-10 | Linked VIRC-RPT-0062 |
| 2026-10-10 | Closed after spec synchronization, parser enforcement, source migration, regressions, and fixed-point bootstrap |
