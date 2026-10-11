---
name: vir-syntax
description: >-
  Write and review canonical Vir syntax, blocks, control flow, operators,
  types, generics, errors, async forms, and other Vir-specific constructs.
  Use with vir-lang whenever syntax or semantics must be emitted or judged.
---

# Vir syntax and control flow

Use this skill only after `vir-lang` routes the task here.

## Required sources

Read the exact relevant section in `VIR-SPC-0017` or `VIR-SPC-0018`, then read
the focused SPEC for the construct and a current test or parser path when
implementation behavior matters. For entities or methods, `VIR-SPC-0022` is
mandatory. For dot calls, callable fields, or UFCS, `VIR-SPC-0023` is
mandatory. Read
[`references/core-syntax.md`](references/core-syntax.md) before writing or
reviewing nontrivial `.vri` syntax.

## Block law

- Top-level definitions/declarations (`func`, `async func`, `entity`, `enum`,
  `register`, `mold`, bind stubs) close with `end.`.
- Nested entity `method` declarations and statement/control blocks (`if`,
  `when`, `for`, `loop`, `case`, `try`, `arena`, `map`, `select`, `isolate`)
  close with `end`.
- Continuations (`eif`, `else`, `ensure`, `revert`) have no `:`.
- Expression before body: use `do` or `loop`. No leading expression: use `:`.

## Entity method gate

- Emit `method` only as a lexically nested member of `entity`; never emit a
  module-scope `method` or an `extend` block.
- A method receives implicit `this`. Do not write an explicit receiver
  parameter in its signature.
- Close the method with `end`, then close its owning entity with `end.`. Reject
  nested method `end.` even if legacy code or an old example contains it.
- For an operation declared outside the entity, emit `func` with an explicit
  first receiver parameter. It may be called directly or through UFCS.

## Member-call resolution gate

- `x.foo` is field access. `x.foo(args)` is callable resolution.
- Resolve calls in exactly this order: entity method, structural callable
  field, eligible visible free function through UFCS.
- Once a same-named method or callable field is selected, arity/type failure is
  an error. Never retry a lower-priority candidate based on signature.
- A same-named non-callable field is not a call candidate and does not block
  free-function UFCS. Never implement or describe strict shadowing by every
  field.
- When the free function must be selected despite a same-named callable
  member, use direct syntax `foo(x, args)`, qualified by module when needed.

## Review gate

Reject code copied from another language when it introduces braces, `fn`,
`while`, `elif`, `continue`, `return`, `&&`, `::`, `${...}`, or angle-bracket
generics. Check separator, opener, and closer as independent concerns.

Before accepting entity/UFCS code, explicitly check for module-scope `method`,
nested method `end.`, invented `extend`, strict shadowing by a data field, and
signature-based fallback. Any of these is a rejection unless a newer ACTIVE
SPEC explicitly supersedes `VIR-SPC-0022` or `VIR-SPC-0023`.

For an unfamiliar construct, do not extrapolate from this quick map. Search the
SPEC, lexer/parser, and positive tests; if they disagree, report both normative
and implemented behavior.

