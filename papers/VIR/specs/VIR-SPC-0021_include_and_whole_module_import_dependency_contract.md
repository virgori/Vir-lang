---
id: "VIR-SPC-0021"
type: "SPEC"
domain: "VIR"
title: "Include and whole-module import dependency contract"
status: "ACTIVE"
version: "1.0.0"
language: "en"
spec_class: "CONTRACT"
aliases: []
created: "2026-10-10"
updated: "2026-10-10"
owners:
  - "VIR"
  - "VIRC"
components:
  - "module-system"
  - "dependency-semantics"
  - "include"
  - "import"
  - "export"
related:
  issues:
    - "VIR-ISS-0006"
    - "VIR-ISS-0017"
    - "VIRC-ISS-0044"
    - "VIRC-ISS-0046"
    - "VIRC-ISS-0065"
  plans:
    - "VIR-PLN-0003"
  reports:
    - "VIR-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "module-composition"
  - "module-namespace"
  - "dependency-contract"
  - "visibility"
---

# VIR-SPC-0021 — Include and whole-module import dependency contract

## 1. Purpose

This specification defines distinct language roles for `include M` and whole-module
`import M`. It prevents the two directives from being treated as interchangeable
spellings merely because the current compiler expands both through source text.

The intended distinction is:

- `include M` composes an implementation fragment into the current logical
  module;
- `import M` consumes an independent module through a qualified namespace and
  its declared export boundary.

This SPEC refines the dependency semantics in `VIR-SPC-0006` and the grammar in
`VIR-SPC-0014`, `VIR-SPC-0017`, and `VIR-SPC-0018`. Those parent
specifications are synchronized with this ACTIVE focused contract.

## 2. Specification

### 2.1 Grammar

The relevant canonical forms are:

```text
include_dependency     := "include" dependency_target ("," dependency_target)*
whole_module_import    := "import" dependency_target ("as" IDENT)?
selective_import       := "import" import_item ("," import_item)* "from" dependency_target
import_item            := IDENT ("as" IDENT)?
```

`import from M` is invalid because `from` may appear only after a non-empty
selective import list. `import * from M` and `from M import X` are not canonical
forms under this contract.

Because include does not create a namespace, `include M as A` is invalid syntax
and MUST be rejected. Existing compiler acceptance and source usage of include
aliases are compatibility evidence to audit and migrate, not semantics to
preserve implicitly.

`include A, B` is shorthand for composition of the same target sequence as
separate `include A` and `include B` directives. Each list element is an
independent dependency target with its own resolution provenance; no element
accepts a namespace alias.

### 2.2 Core invariants

The following invariants define the separation:

1. `include` does not create a new module, namespace, or independent export
   boundary.
2. `import M` does not copy the provider implementation into the consumer's
   logical module. The provider is compiled and analyzed as an independent
   module unit even if an implementation internally uses source expansion.
3. `import X from M` resolves `X` only when `X` belongs to the explicit export
   set of `M`.
4. `import from M` is a syntax error and MUST NOT be inferred as a wildcard or
   umbrella import.
5. Including a fragment does not automatically make any of its declarations
   public. Only explicit exports of the composed module define its public API.
6. Multiple imports of one canonical module do not imply multiple runtime
   initializations. Exact initialization timing, ordering, failure, and cycle
   behavior require a separate module-initialization specification.

### 2.3 Shared dependency resolution rules

Both directives MUST resolve their target through the same active registry and
canonical-identity machinery defined by `VIR-SPC-0006`. They MUST share:

- canonical Module ID and physical-path normalization;
- deterministic deduplication and cycle detection;
- source provenance for diagnostics and tooling;
- fail-closed handling of missing, invalid, or conflicting registry entries.

The common resolver does not make the directives semantically equivalent.
Resolution answers which source unit is referenced; the directive determines
how that unit participates in the consumer.

### 2.4 `include M` — implementation composition

`include M` is a composition dependency. Its target is an implementation
fragment of the consumer's current logical module rather than an independently
consumed public API.

The included fragment:

- contributes declarations to the consumer's unqualified lexical/module scope;
- may be used to split one implementation across physical files;
- participates in the consumer's type checking, ownership analysis, lowering,
  initialization ordering, and diagnostics as part of that logical module;
- retains its physical source provenance and canonical dependency identity for
  deduplication and cycle diagnostics;
- does not create an independent consumer-visible namespace merely by being
  included;
- does not bypass package or registry validation.

Private declarations in an included fragment are visible to the composed
module because the fragment is part of that module. An `export` declaration in
the fragment contributes to the export surface of the composed module; no
declaration becomes exported merely because it was included.

If two included fragments, or an included fragment and its consumer, declare
the same name in the same scope, the compiler MUST report a duplicate
declaration. Resolution is order-independent: later includes MUST NOT overwrite,
replace, or silently shadow earlier declarations.

Repeated spellings in one include list or across include directives converge
on canonical Module ID deduplication. Deduplication does not suppress a real
declaration collision between distinct fragments.

An included source that declares a logical `module` name MUST either match the
consumer's logical module or be rejected as an invalid cross-module include.
Consuming an independent module through include is non-canonical; use an import.

### 2.5 `import M` — module consumption

`import M` is a module dependency. It preserves the provider's independent
canonical Module ID and binds a local namespace. Without an explicit alias, the
namespace is the provider's canonical local module name; `import M as A` binds
the same provider under local name `A` without creating a new identity.

Whole-module import:

- compiles and analyzes the provider as an independent logical module unit;
- exposes only declarations explicitly listed by the provider's `export`
  contract;
- requires qualified access such as `M.symbol` or `A.symbol`;
- MUST NOT inject the provider's exports into the consumer as unqualified local
  names;
- MUST NOT expose private declarations, even when the implementation uses text
  expansion internally;
- loads and analyzes a canonical provider at most once for the dependency graph.

Compiler optimization may inline code, merge artifacts, or use a shared parser
pipeline, but those transformations do not merge the language scopes or export
boundaries of provider and consumer.

An empty export surface produces an empty namespace; it never falls back to
private declarations.

### 2.6 Selective import

`import X, Y from M` is the explicit unqualified alternative to whole-module
namespace import. It loads the provider without a preceding include and binds
only the named exported declarations. Symbol aliases change local bindings but
not provider identity or export names.

Selective import applies to every supported named declaration kind, including
functions, types, constants, and variables. A missing or private symbol is a
compile-time error.

### 2.7 Single-form dependency rule

A consumer MUST choose one dependency form for a canonical target:

- use `include M` when `M` is an implementation fragment of the same logical
  module;
- use `import M` for qualified access to an independent module API;
- use `import X from M` for selected unqualified public names.

Combining include and import for the same canonical target in one consumer is
invalid unless a later SPEC defines a narrowly scoped migration exception.

### 2.8 Name collisions and re-export

Because include composes declarations into the consumer's unqualified scope,
duplicate declarations are ordinary same-module conflicts. Import namespaces
prevent collisions between equal short export names from different providers.
Duplicate include declarations are compile-time errors regardless of include
order; Vir defines no last-include-wins behavior.

Importing a module does not re-export it. A consumer that wants to publish a
provider declaration must declare its own supported forwarding API or use a
future explicit re-export mechanism; no implicit re-export is defined here.

### 2.9 Module initialization boundary

Import count and initialization count are distinct. Repeated and diamond
imports of one canonical Module ID MUST converge on one provider identity and
MUST NOT multiply runtime initialization merely because multiple dependency
edges exist.

This contract does not define whether a module has an initializer, when it
runs, how initialization order is computed, or how initialization failure and
cycles behave. Those rules require a separate normative SPEC. Until that SPEC
exists, compiler behavior MUST NOT be presented as a portable language promise.

### 2.10 Example

The following schematic Vir source exercises all three valid mechanisms:

```vir
include internal
import math
import sqrt from math
```

`internal` is implementation belonging to the current logical module. The
independent `math` module is accessed through qualified names such as
`math.sqrt(...)`. The selective import also creates the local binding
`sqrt(...)`. The include creates neither an `internal` namespace nor a public
export by itself.

### 2.11 Diagnostics and tooling

Diagnostics MUST identify the directive kind, dependency spelling, canonical
Module ID when available, physical source provenance, and the violated boundary.
LSP completion/navigation MUST distinguish composed declarations from imported
namespace members and retain provider provenance.

An implementation MAY use text preprocessing, AST/HIR composition, or another
internal representation, but implementation strategy MUST NOT change the scope,
visibility, or namespace behavior defined above.

## 3. Compatibility

### 3.1 Grammar migration

- Replace former umbrella `import from M` with `import M`, then qualify uses.
- Replace unqualified whole-module consumption with either `import X from M`
  for selected names or `import M` plus qualified access.
- Do not add `include M` merely to make an import resolve; every import form
  resolves and loads its provider directly.

### 3.2 Include migration

Code that uses `include M` to consume an independently named module relies on a
flattening behavior outside this contract. It SHOULD migrate to a whole or
selective import. Code that uses include to assemble same-module implementation
fragments remains the intended use.

The activation audit identified:

- no include aliases or whole-module imports in production `.vri` sources under
  `compiler/src`, `stdlib/vir`, or `tools`;
- one non-canonical include-alias compatibility fixture,
  `tests/modules/test_multi_include_alias_compat_positive.vri`;
- compiler namespace, mixed-form, collision, visibility, provenance, and IDE
  conformance gaps already owned by `VIRC-ISS-0065`.

The compatibility fixture is implementation evidence, not canonical syntax.
It MUST migrate to alias-free composition or become a negative rejection test
when the compiler issue is implemented.

### 3.3 Current implementation status

The self-hosted compiler currently expands include and import directives before
lexing. The include-only fixture demonstrates unqualified composition, while
the whole-module import builder returns the provider body when no symbols are
selected. That implementation evidence is not proof of namespace-only import
conformance. `VIRC-ISS-0065` tracks the relevant compiler namespace gap.

No compiler, LSP, standard-library, or source migration is claimed by this
language-contract activation.

### 3.4 Language activation and implementation conformance

This SPEC is ACTIVE by language-owner decision after grammar, compatibility,
and parent-SPEC review. Language activation does not certify a compiler or LSP
implementation. In particular, current acceptance of include aliases and
source flattening of whole-module imports are known nonconformities tracked by
`VIRC-ISS-0065`.

An implementation may claim conformance only after executable positive and
negative fixtures cover scope, visibility, qualification, collisions, cycles,
provenance, mixed-form rejection, and include-alias rejection. Those gates
belong to the implementation report for `VIRC-ISS-0065`, not to this language
paper's ACTIVE lifecycle.

## 4. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-10 | 1.0.0 | Activated the language contract after repository compatibility audit and parent-SPEC synchronization; separated normative activation from compiler/LSP conformance owned by VIRC-ISS-0065 |
| 2026-10-10 | 0.3.0 | Advanced to REVIEW and made multi-target include composition normative; every list element has independent provenance, include aliases remain invalid, and canonical-target dedup does not hide cross-fragment declaration collisions |
| 2026-10-10 | 0.2.0 | Added the six core invariants, independent compilation boundary for imports, order-independent duplicate declaration errors for includes, module-initialization separation, and canonical three-form example |
| 2026-10-10 | 0.1.0 | Initial draft separating same-module implementation composition through `include M` from independent namespace consumption through `import M` |
