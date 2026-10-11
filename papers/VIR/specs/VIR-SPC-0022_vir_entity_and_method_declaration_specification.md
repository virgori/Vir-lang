---
id: "VIR-SPC-0022"
type: "SPEC"
domain: "VIR"
title: "Vir Entity and Method Declaration Specification"
status: "ACTIVE"
version: "1.0.0"
language: "en"
spec_class: "SPECIFICATION"
aliases: []
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "VIR"
components:
  - "entity"
  - "methods"
  - "syntax"
related:
  issues:
    - "VIR-ISS-0019"
  plans:
    - "VIR-PLN-0002"
  reports:
    - "VIR-RPT-0002"
supersedes: null
superseded_by: null
tags:
  - "entity"
  - "method"
  - "this"
  - "declaration"
---

# VIR-SPC-0022 — Vir Entity and Method Declaration Specification

## 1. Purpose

This specification defines the focused normative contract for Vir `entity`
declarations and entity-owned `method` declarations. It refines
`VIR-SPC-0017` §7.2 and `VIR-SPC-0018` §7.2 without introducing class,
inheritance, access-control, extension-block, or top-level-method semantics.

The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are normative.

## 2. Declaration Ownership

An `entity` is a top-level type declaration. It owns its fields and inherent
methods. An entity declaration MUST close with `end.`.

A `method` is a nested member declaration owned by the lexically enclosing
entity. It MUST NOT appear at module scope. A method body MUST close with
`end`, without a dot; the entity's final `end.` remains the outer declaration
boundary.

Conceptually:

```text
module-declaration := func-declaration | entity-declaration | ...
entity-member      := field-declaration | method-declaration
```

`method` is deliberately absent from `module-declaration`. A bodyless method
signature MAY appear as an interface member under the interface contract; it
is still owned by that interface and is not a top-level declaration.

## 3. Canonical Forms

An entity with a no-argument method:

```vir
entity Counter:
    value: int

    method read() -> int:
        out this.value
    end
end.
```

A method with explicit arguments:

```vir
entity Counter:
    value: int

    method add(delta: int) -> int:
        this.value = this.value + delta
        out this.value
    end
end.
```

`packed entity` uses the same lexical ownership and method terminators. Packing
changes layout, not method scope or call resolution.

These forms are invalid:

```vir
# Invalid: a nested method does not own a dotted declaration boundary.
entity Counter:
    method read() -> int:
        out 0
    end.
end.
```

```vir
# Invalid: method has no entity owner at module scope.
method read(this: Counter) -> int:
    out this.value
end.
```

## 4. Receiver Semantics

An entity method receives its owning instance as implicit `this`. Field reads
and writes through `this` operate on that receiver subject to the ordinary
type, mutability, ownership, and borrow rules.

Method arguments written by the caller correspond only to the explicit method
parameters. In `counter.add(2)`, the receiver is implicit and `2` supplies the
declared `delta` parameter.

An operation declared outside the entity MUST use `func`, with the receiver as
its explicit first parameter when it is intended for UFCS:

```vir
func reset(this: Counter):
    this.value = 0
end.

counter.reset()       # UFCS spelling
reset(counter)        # direct free-function spelling
```

The identifier `this` is the canonical convention for an intended free UFCS
receiver; free-function eligibility and call checking are defined by
`VIR-SPC-0023`.

## 5. Member Names and Call Syntax

Fields and methods occupy distinct semantic roles. A field and a method MAY
share the same identifier:

```vir
entity Reading:
    value: int

    method value() -> int:
        out this.value + 1
    end
end.
```

`reading.value` is field access. `reading.value()` is callable resolution and
selects the entity method before lower-priority callable candidates. Duplicate
field declarations within one entity and duplicate method declarations within
one entity are invalid.

The complete priority, callable-field behavior, terminal signature checks, and
free-function fallback are specified by `VIR-SPC-0023`.

## 6. Non-Goals

This specification does not make `entity` a Java/C++ class and does not define:

- private/protected/public access modifiers;
- inheritance or virtual dispatch;
- module-scope `method`;
- `extend` or extension blocks;
- automatic invariant enforcement;
- wildcard method injection from imports.

Such features require independent language decisions.

## 7. Diagnostics and Conformance

An implementation MUST reject module-scope `method` and a dotted terminator on
an entity method. The reference compiler reports `E3091` and `E3092`,
respectively. Recovery MUST NOT reinterpret an invalid module-scope method as a
free `func` or silently detach a method from its entity owner.

Conformance coverage MUST include ordinary, generic, and packed entities and
must preserve entity ownership through include/import preprocessing.

## 8. Compatibility

This paper consolidates behavior already normative in Vir 3.4 and implemented
by compiler `2026.1.17`; it introduces no ABI or source change. Legacy nested
`end.` and module-scope `method` forms remain invalid. External operations use
free functions and may be invoked directly or through UFCS.

## 9. Related Specifications

- `VIR-SPC-0017` §7.2 — English language specification.
- `VIR-SPC-0018` §7.2 — Vietnamese language specification.
- `VIR-SPC-0013` — function and callable-field syntax.
- `VIR-SPC-0023` — UFCS resolution and callable shadowing.

## 10. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-10 | 1.0.0 | Established the focused entity ownership, method declaration, receiver, terminator, and module-scope rejection contract under VIR-ISS-0019 |
