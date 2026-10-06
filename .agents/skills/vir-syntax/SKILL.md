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
a focused SPEC (`VIR-SPC-0010` through `VIR-SPC-0016`) and a current test or
parser path when implementation behavior matters. Read
[`references/core-syntax.md`](references/core-syntax.md) before writing or
reviewing nontrivial `.vri` syntax.

## Block law

- Definitions/declarations (`func`, `async func`, `method`, `entity`, `enum`,
  `register`, `mold`, bind stubs) close with `end.`.
- Statement/control blocks (`if`, `when`, `for`, `loop`, `case`, `try`,
  `arena`, `map`, `select`, `isolate`) close with `end`.
- Continuations (`eif`, `else`, `ensure`, `revert`) have no `:`.
- Expression before body: use `do` or `loop`. No leading expression: use `:`.

## Review gate

Reject code copied from another language when it introduces braces, `fn`,
`while`, `elif`, `continue`, `return`, `&&`, `::`, `${...}`, or angle-bracket
generics. Check separator, opener, and closer as independent concerns.

For an unfamiliar construct, do not extrapolate from this quick map. Search the
SPEC, lexer/parser, and positive tests; if they disagree, report both normative
and implemented behavior.

