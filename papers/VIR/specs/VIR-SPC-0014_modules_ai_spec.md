---
id: "VIR-SPC-0014"
type: "SPEC"
domain: "VIR"
title: "Vir Modules (AI Spec)"
status: "ACTIVE"
version: "3.3.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-10"
owners:
  - "VIR"
  - "VIRC"
components: []
aliases:
  - "docs/ai-spec/vir-lang/references/modules.md"
related:
  issues:
    - "VIR-ISS-0005"
    - "VIR-ISS-0006"
    - "VIR-ISS-0007"
    - "VIR-ISS-0008"
    - "VIR-ISS-0017"
    - "VIRC-ISS-0046"
    - "VIRC-ISS-0065"
  plans:
    - "VIR-PLN-0003"
  reports:
    - "VIR-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIR-SPC-0014 — Vir Modules (AI Spec)

**Spec:** Vir v3.6

Canonical authority for registry and resolver semantics: `VIR-SPC-0006`.
Focused authority for the include/import boundary: `VIR-SPC-0021`.
Module IDs come from the active project, package, or toolchain stdlib registry;
directory layout alone does not publish a module.

The dot `.` is the only module-path separator. `A::B` is invalid Vir syntax.

## Dependency target forms

Prefer a registered dotted Module ID:

```vir
include app.net.http
import Client from app.net.http
```

Direct `.vri` paths remain supported compatibility targets for include and
selective import:

```vir
include "provider.vri"
include provider.vri
include "helpers/provider.vri"
import answer from "provider.vri"
```

A direct path does not publish a Module ID. Normalize it and converge to the
registered canonical identity when it names a registered file; otherwise use a
path-derived identity. Legacy unregistered dotted-to-path lookup may be accepted
for compatibility, but new projects should register the dotted ID.

## Declaration order (module level)

```text
include → import → const → var → entity → func → export → share
```

## include — implementation composition

Composes each target as an implementation fragment of the current logical
module. Included declarations enter unqualified module scope, retain provider
provenance, and do not become public without an explicit export. Include does
not establish a namespace and accepts no alias.

```vir
include math
include internal.logging
include math, io.file, internal.logging
```

Duplicate declarations across fragments or between a fragment and consumer are
compile-time errors independent of include order.

## import — exported symbols and namespaces

Does **not** require a prior `include`.

```vir
import add from math
import add, sub from math
import get from net.http as fetch
import net.http
import net.http as web
```

Selective import covers every exported declaration kind: functions, types,
constants, and variables. `from` is valid only after a non-empty selective
symbol list. `import module` binds the whole-module namespace, and `import
module as alias` binds it under an explicit local name; neither injects every
export as an unqualified name. `import from module` is invalid. `get` remains a
legal ordinary export name, as shown by `import get ...` above.

## export / share / port

```vir
export add, subtract
share counter, mode
port signals, commands
```

| | `share` / `ref` | `port` |
|---|---|---|
| Use | In-process shared data | Message coordination |
| Access | Memory | Send/recv queue |

## Registry invariants

- The directory containing `module.list` is its initial base; optional `root`
  changes that base for following mappings.
- The active stdlib registry belongs to the selected Vir toolchain, not to the
  project.
- Project Module IDs must be disjoint from active stdlib Module IDs. Exact
  equality is an eager configuration error; prefix-only relationships such as
  stdlib `http` and project `http.app` are valid.
- Cycles are compile-time errors. Vir 3.0 has no deferred type-only module form.

## Agent rules

1. Prefer `import X from mod` over inventing `use` / `require` / `package`.
2. Do not invent module paths; inspect the active `module.list` or toolchain
   `stdlib.vri` entry. Use a direct `.vri` path only when compatibility or a
   deliberately local source dependency requires it.
3. Do not treat compiler implementation status as language semantics; follow
   `VIR-SPC-0006`/`VIR-SPC-0021` and report conformance gaps separately.
4. Never emit `include M as A`. Use `include M` for composition, `import M as
   A` for an independent namespace, or `import X from M` for selected local
   bindings.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-10 | 3.3.0 | Aligned the AI module reference with active VIR-SPC-0021: include is same-module composition with no namespace or alias, while whole-module import owns qualified namespace consumption |
| 2026-10-10 | 3.2.0 | Made `import module` the canonical whole-module form, restricted `from` to non-empty selective imports, removed `import from module`, and recorded the decision under VIR-ISS-0017 |
| 2026-10-06 | 3.1.0 | Documented registered dotted IDs, direct-path compatibility, legacy dot-to-path lookup, and canonical identity convergence |
| 2026-10-06 | 3.0.0 | Aligned the AI module reference with the registry-based Vir 3.0 contract, unified named imports, removed deferred module forms, and reserved exact stdlib Module IDs |
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/modules.md` and assigned stable ID `VIR-SPC-0014` |
