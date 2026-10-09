---
id: "STLB-ISS-0032"
type: "ISSUE"
domain: "STLB"
title: "Vec constructors and generic receiver UFCS are blocked by compiler dispatch"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "stdlib"
  - "compiler"
components:
  - "collections"
  - "vec"
  - "generics"
  - "ufcs"
  - "member-resolution"
  - "codegen"
related:
  issues:
    - "STLB-ISS-0007"
    - "STLB-ISS-0033"
    - "VIRC-ISS-0064"
    - "VIRC-ISS-0066"
  plans:
    - "STLB-PLN-0002"
    - "VIRC-PLN-0035"
  reports:
    - "STLB-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "ufcs"
  - "compiler-gate"
  - "public-api"
---

# STLB-ISS-0032 — Vec constructors and generic receiver UFCS are blocked by compiler dispatch

## 1. Summary

The approved Vec naming surface cannot yet be exposed as executable Vir:
type-receiver constructors such as `Vec.new` fail during lowering, while
receiver calls on `Vec of (T)` fail generic UFCS resolution.

The standard-library implementation therefore retains `vec_*` compatibility
symbols while `stdlib/registry/vec.md` records the canonical API.

## 2. Context

`stdlib/registry/vec.md` now records the approved constructors and UFCS names.
`stdlib/vir/collections/vec.vri` implements the collection algorithms and maps
renamed concepts to `vec_alloc`, `vec_create`, `vec_try`, `vec_copy`,
  `vec_equal`, and `vec_compact`, with the previous source symbols retained as
compatibility aliases. This issue covers type-receiver construction and generic
receiver dispatch only. Three-level dotted operations are isolated in
`STLB-ISS-0033`.

## 3. Expected Behavior

- `Vec.new`, `Vec.alloc`, and `Vec.create` lower as type-receiver constructors.
- A value of type `Vec of (T)` resolves calls such as `v.push(x)` and `v.len()`.
- The canonical calls work through the registered `collections.vec` module and
  focused external-consumer tests.

## 4. Actual Behavior

- A non-generic type-receiver method can pass semantic checking, but codegen
  fails while lowering the entity-name receiver as an unresolved identifier.
- A method or generic free function on a generic entity does not resolve through
  UFCS (`E3021`).

## 5. Reproduction

From the repository root, compile focused probes equivalent to:

```vir
entity Item:
    value: int
    method new(value: int) -> Item:
        out Item(value: value)
    end.
end.

func main:
    var item = Item.new(42)
    out 0
end.
```

and:

```vir
entity Box of (T):
    value: T
    method read() -> T:
        out this.value
    end.
end.

func main:
    var box = Box of (int)(value: 42)
    print(box.read())
    out 0
end.
```

The first passes `--check` but fails native lowering with
`lowering unresolved identifier`; the second fails semantic resolution with
`E3021`.

## 6. Evidence

- CONFIRMED: the non-generic `Item.new` probe passes `--check`, then native
  lowering fails with `lowering unresolved identifier: Item`.
- CONFIRMED: the generic `Box of (T)` method probe fails with `E3021` at
  `box.read()`.
- CONFIRMED: `collections.vec` still fails independently under
  `STLB-ISS-0007`; this issue does not claim that those 70 diagnostics are all
  dispatch failures.

## 7. Scope

### Affected

- compiler type-receiver call lowering;
- generic entity/free-function UFCS lookup and monomorphized identity;
- `collections.vec` canonical facade and focused tests.

### Not affected

- the element-width algorithms already implemented by `vec_*` functions;
- the compatibility symbols retained during migration;
- unrelated stdlib namespace renames.

## 8. Impact

The registry can name the intended API, but users cannot compile that spelling.
Removing `vec_*` compatibility symbols now would leave typed Vec with no usable
migration path, while pretending the canonical facade already ships would make
the API reference inaccurate.

## 9. Preliminary Analysis

- The constructor failure occurs after semantic checking, so it is a lowering
  gap rather than a parser rejection.
- The generic receiver failure occurs during semantic resolution and must be
  fixed before backend work can validate `Vec of (T)` calls.

## 10. Acceptance Criteria

- [x] Type-receiver constructors pass semantic checking and native lowering.
- [x] Generic Vec receiver calls resolve with the correct specialization and
  preserve `ref`/move semantics.
- [x] `Vec.new`, `Vec.alloc`, `Vec.create`, and all one-level receiver calls
  have focused positive and negative tests.
- [x] `collections.vec` exposes the canonical facade without removing the old
  compatibility symbols before a documented migration window.
- [x] `STLB-ISS-0007` is independently closed by making the typed module pass
  its complete semantic and ownership check.

## 11. Related Papers

### Issues

- `STLB-ISS-0007` — typed `collections.vec` buildability.
- `STLB-ISS-0033` — three-level Vec UFCS/member paths.
- `VIRC-ISS-0064` — generic receiver UFCS resolution and specialization.
- `VIRC-ISS-0066` — entity fields and methods share identifier.

### Plans

- `STLB-PLN-0002` — lower type receiver constructors and canonical Vec facade.
- `VIRC-PLN-0035` — resolve and specialize generic receiver UFCS.

### Reports

- `STLB-RPT-0002` — lower type receiver constructors and canonical Vec facade report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Split generic receiver UFCS implementation into VIRC-ISS-0064 |
| 2026-10-09 | Split three-level dotted operations into STLB-ISS-0033 |
| 2026-10-09 | Opened while implementing the approved Vec UFCS rename |
| 2026-10-09 | Linked VIRC-PLN-0035 |
| 2026-10-09 | Linked STLB-PLN-0002 |
| 2026-10-09 | Linked VIRC-ISS-0066 |
| 2026-10-09 | Verified all acceptance criteria and closed via STLB-RPT-0002 |
