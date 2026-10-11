---
name: vir-lang
description: >-
  Mandatory router for every Vir, Virgori, virc, Viron, or .vri task. Use it
  before writing, reviewing, explaining, testing, or restructuring Vir code;
  it selects the syntax, clean-code, memory, module/stdlib, and native
  verification companion skills and requires claims to be verified against
  active Vir specifications and code.
---

# Vir language router

This is the entrypoint for every Vir task. Keep this file small: route to the
specialized skill that owns the decision instead of loading one monolithic
manual.

## Per-turn routing

Inventory `.agents/skills/vir-*/SKILL.md` and read this file plus every matched
companion in full before acting. Repeat the inventory each turn because skills
may change.

| Work in scope | Required companion |
|---|---|
| Any `.vri` creation, edit, refactor, or review | `vir-clean-code` and `vir-stdlib-modules` |
| Grammar, operators, types, blocks, control flow, errors, async, or unfamiliar Vir syntax | `vir-syntax` |
| Ownership, borrows, moves, lifetime, escape, allocation, `arena:`, cleanup, or memory-sensitive backend work | `vir-memory-management` |
| `include`, `import`, `export`, stdlib APIs, module identity, or file moves | `vir-stdlib-modules` |
| Creating, editing, auditing, or diagnosing `module.list` | `vir-module-list` and `vir-stdlib-modules` |
| Running Vir tests, contract manifests, LSP suites, module/pass checks, performance gates, or replacing Python verification harnesses | `vir-native-verification` |
| Compiler internals | All companions relevant to the changed semantics; also inspect `compiler/module.list` and canonical/generated provenance |

A task may require multiple companions. Do not suppress a companion merely
because another one also applies.

## Authority order

Use the narrowest current authoritative source:

1. Normative language: `papers/VIR/specs/VIR-SPC-0018_*` and
   `VIR-SPC-0017_*`, with focused specifications for the construct in scope.
   Entity/method work requires `VIR-SPC-0022`; member-call or UFCS work
   requires `VIR-SPC-0023`. Do not stop at the older `VIR-SPC-0010` through
   `VIR-SPC-0016` series when a newer focused paper exists.
2. Memory architecture: `papers/VIR/specs/VIR-SPC-0005_*` and allocator
   contracts under `papers/STLB/specs/`.
3. Modules and public APIs: active `module.list`, `stdlib/stdlib.vri`, actual
   `export` declarations, resolver source, and executed tests.
4. Compiler behavior: canonical `compiler/src/**`, generated-source provenance,
   and tests for the exact backend/optimization level.
5. Examples and old skills are patterns only. They cannot override active
   SPECs or implementation evidence.

When sources conflict, name the conflict and follow the source governing the
requested decision. Never silently combine incompatible rules.

## Mandatory evidence gate

Before emitting or changing Vir code:

1. Inspect Git status and preserve unrelated changes.
2. Locate the nearest applicable `module.list`; for stdlib names inspect
   `stdlib/stdlib.vri`. Follow `vir-stdlib-modules` even for a one-file edit.
3. Read the relevant focused SPEC section and a current positive test or nearby
   canonical source pattern.
4. Verify every module name, exported symbol, API, diagnostic, target claim,
   and command. These are closed-world identifiers; do not invent them.
5. Compile or run focused tests in proportion to the change. Compiler
   acceptance does not make legacy syntax normative.

## Base anti-hallucination rules

- Source files use `.vri`.
- Top-level definitions use `func`, `entity`, `enum`, and close with `end.`.
- `method` is never a top-level declaration: it is lexically owned by an
  `entity`, receives implicit `this`, and closes with `end`; the owning entity
  closes with `end.`. Standalone receiver operations use `func`, not `method`
  or an invented `extend` block.
- Statement/control blocks close with `end`.
- `if condition do`, `when condition loop`, `for item in values do`.
- Use `eif`, `skip`, and `out`; never substitute `elif`, `continue`, or
  `return`.
- Use `include` / `import module` / `import ... from module` / `export`; never invent
  Rust `use`, Go imports, or `A::B` paths. `get` is an ordinary identifier, not
  a standalone module directive.
- Prefer registered dotted Module IDs. Direct `.vri` paths are supported
  compatibility targets, not implicit public Module IDs.
- Boolean logic is `&`, `||`, `!`; bitwise operations use Vir word operators.
- Ordinary generics use `of (...)`; do not generate `Name<T>`.
- Do not invent a `saga` keyword. Compensation uses `try` / `revert`.
- Do not infer member-call resolution from spelling alone. For `x.foo(args)`,
  follow `VIR-SPC-0023`: entity method, then structural callable field, then
  eligible free-function UFCS. A selected method/callable field fails
  terminally on an invalid call; a non-callable field does not block free
  UFCS. Use `foo(x, args)` to explicitly select the free function.

## Compiler hard-limit prohibition

Compiler code MUST NOT impose an arbitrary hard-coded ceiling on otherwise
valid source programs, semantic graphs, runtime values, or tooling results.
Examples include fixed maxima for tokens, AST nodes, symbols, scopes, modules,
imports, exports, declarations, functions, fields, locals, diagnostics, IDE
facts, completion items, container entries, or generated output. An internal
buffer capacity MUST NOT become a language limit, cause silent truncation,
trigger an unclassified process exit, or reject a valid program merely because
the implementation reached that capacity.

Use growable storage, exact/two-pass sizing, checked allocation, streaming, or
a limit derived from an authoritative SPEC, target ABI, object format,
instruction encoding, hardware property, or explicit user configuration. A
true external limit is not arbitrary, but its source MUST be named in code and
overflow MUST fail with a stable, source-located diagnostic when possible.
Performance guards and denial-of-service budgets belong in explicit
configuration/policy; they MUST NOT be disguised as semantic constants.

When editing an affected path, audit nearby fixed-size allocations and bounded
loops. If an existing arbitrary ceiling is encountered, fix it within scope or
record it as a verified ISSUE; do not preserve it as precedent. Regression
coverage MUST exercise growth beyond the former/default capacity and prove no
truncation, overwrite, magic exit code, or capacity-dependent semantic change.

## Compiler version completion gate

When a `VIR-ISS` or `VIRC-ISS` that changes the compiler is completed, read
`compiler/VERSIONING.md` and bump the calendar version exactly once for that
issue before reporting completion. Verify canonical metadata, generated-source
sync, the rebuilt binary's `--version`, and the version-policy regression. An
issue is not compiler-complete while those checks are missing or stale.

When a `VLSP-ISS` changes the native language server, read
`tools/vir-lsp/VERSIONING.md` and bump the independent LSP Semantic Version
exactly once before reporting completion. Rebuild the server and verify both
CLI output and `initialize.serverInfo.version`; never derive the LSP version
from the compiler calendar version.

## Spec and generated-source guard

Do not edit canonical SPEC papers or `docs/ai-spec/vir-lang/**` unless the user
explicitly requests a language-spec change. Do not edit generated compiler
artifacts directly; identify and change their canonical sources, then use the
verified generation workflow.
