---
id: "VIR-SPC-0023"
type: "SPEC"
domain: "VIR"
title: "Vir UFCS Resolution and Callable Shadowing Specification"
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
  - "ufcs"
  - "methods"
  - "callable-fields"
  - "name-resolution"
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
  - "ufcs"
  - "shadowing"
  - "callable-field"
  - "source-compatibility"
---

# VIR-SPC-0023 — Vir UFCS Resolution and Callable Shadowing Specification

## 1. Purpose

This specification defines the focused normative contract for Uniform Function
Call Syntax (UFCS), callable candidate priority, terminal shadowing, field/call
disambiguation, and source-compatibility consequences. It refines
`VIR-SPC-0017` §§11.1–11.5 and `VIR-SPC-0018` §§11.1–11.5.

The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are normative.

## 2. Direct Calls and UFCS Calls

For an eligible visible free function, UFCS rewrites the receiver into the
first argument position:

```vir
func scale(this: int, factor: int) -> int:
    out this * factor
end.

let direct = scale(7, 3)
let dotted = 7.scale(3)
```

Both forms target the same free function when no higher-priority callable
candidate shadows the dotted call. Naming the first parameter `this` is the
canonical convention for functions designed for UFCS; ordinary call
compatibility still determines whether a free function is eligible.

`receiver.member` without parentheses is field access. It MUST NOT invoke an
entity method, callable field, or free function. `receiver.member(args)` is a
call expression and uses the resolution contract below.

## 3. Resolution Order

For `receiver.member(args)`, resolution MUST proceed in this order:

1. An entity method with the matching name.
2. A callable field with the matching name and a structural function type.
3. An eligible visible free function through UFCS.
4. A compilation error if no callable candidate exists.

The order is independent of source declaration order.

### 3.1 Entity method

If the receiver type owns a method named `member`, that method is selected.
The receiver is passed as implicit `this`; written arguments correspond to the
method's explicit parameters.

Selection by name is terminal. If argument count, argument type, generic
inference, ownership, mutability, or another call requirement fails, the
compiler MUST report the failure and MUST NOT fall back to a callable field or
free function of the same name.

### 3.2 Callable field

If no entity method is selected and the receiver owns a field named `member`
whose declared type is structural `func(P...) -> R` or `func(P...)`, that field
is selected. Calling it passes only the arguments written inside parentheses;
the receiver is not injected as an implicit argument.

Selection of a callable field is terminal. Signature or type-checking failure
MUST produce a compilation error and MUST NOT fall back to a free function.
Raw `ptr` is not a callable field and has no implicit conversion to a
structural function type.

### 3.3 Non-callable field

A field whose declared type is not callable is not a call candidate and MUST
NOT prevent free-function UFCS resolution. This is intentional:

```vir
entity HasLabel:
    label: int
end.

func label(this: HasLabel) -> int:
    out this.label + 7
end.

let value = HasLabel(label: 40)
print value.label      # field access: 40
print value.label()    # free-function UFCS: 47
```

The two expressions occupy distinct semantic operations and are not
ambiguous. Vir does not apply strict shadowing merely because any member shares
the call name.

### 3.4 Free function UFCS

Free functions are considered only if no entity method or callable field was
selected. The receiver becomes argument zero and all written arguments follow
it. The candidate MUST be visible under the active module/import rules and its
signature MUST accept the normalized argument list. Multiple indistinguishable
visible candidates MUST be diagnosed as ambiguous rather than selected by
source order.

## 4. Direct Selection of a Free Function

Direct function-call syntax bypasses entity-method and callable-field priority:

```vir
entity Score:
    value: int

    method compute(delta: int) -> int:
        out this.value + delta
    end
end.

func compute(this: Score, delta: int) -> int:
    out 900 + this.value + delta
end.

let score = Score(value: 10)
print score.compute(5)    # entity method: 15
print compute(score, 5)  # free function: 915
```

Callers that require a stable free-function target SHOULD use direct syntax,
with module qualification when needed.

## 5. Callable Shadowing and API Evolution

Only members in the callable candidate space shadow free UFCS:

| Same-named component | `x.foo(args)` behavior | Shadows free UFCS |
|---|---|---|
| Entity method | Select method; call failure is terminal | Yes |
| Structural callable field | Select field; call failure is terminal | Yes |
| Non-callable field | Continue to free UFCS | No |
| Free function | Select only when not shadowed | — |

Adding an entity method or callable field MAY redirect an existing dot call
from a free function. Changing a field from a non-callable type to a structural
function type MAY likewise redirect an existing dot call. Library authors MUST
treat these as potentially source-breaking API changes even when the added or
changed member is otherwise source-compatible.

Adding or changing a non-callable field does not by itself shadow a free UFCS
call, though ordinary field-access compatibility still applies.

## 6. Diagnostics and Conformance

The reference compiler uses:

- `E3022` for wrong argument count after selecting a method or callable field;
- `E3001` for incompatible argument types;
- `E3021` when no method, callable field, or eligible free function resolves;
- `E3052` for ambiguous visible free-function UFCS candidates.

Conformance tests MUST distinguish targets by observable result and MUST place
a compatible lower-priority free function behind wrong-arity and wrong-type
method/callable-field candidates to prove terminal no-fallback behavior.

## 7. Non-Goals

This specification does not introduce:

- top-level `method`;
- `extend` or extension blocks;
- overload ranking across callable tiers;
- signature-based fallback after selecting a higher-priority name;
- strict shadowing by all same-named fields;
- implicit raw-pointer calls.

## 8. Compatibility

This paper consolidates behavior already normative in Vir 3.4 and implemented
by compiler `2026.1.17`; it introduces no ABI or source change. It makes API
evolution risk explicit and gives callers a stable direct-call spelling.

## 9. Related Specifications

- `VIR-SPC-0017` §§11.1–11.5 — English language specification.
- `VIR-SPC-0018` §§11.1–11.5 — Vietnamese language specification.
- `VIR-SPC-0013` — functions and structural callable fields.
- `VIR-SPC-0022` — entity and method declaration ownership.

## 10. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-10 | 1.0.0 | Established callable-tier priority, terminal no-fallback selection, non-callable-field fallthrough, direct-call pinning, and API compatibility rules under VIR-ISS-0019 |
