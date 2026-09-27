# Stdlib API Registry — Format Spec

This file is the **closed schema** for every document under `stdlib/registry/`.
Parsers (docs generators, AI tooling, curriculum linkers) may rely only on
rules defined here. Prefer adding optional fields over inventing new layouts.

> **Note:** Named `SCHEMA.md` (not `FORMAT.md`) so it can coexist with the
> public namespace file `format.md` on case-insensitive filesystems (APFS default).

## Goals

| Goal | Rule |
|---|---|
| Flat tree | One public namespace → one Markdown file at `stdlib/registry/<namespace>.md` |
| Machine-readable enough | Front matter + fixed heading / table shapes |
| Human-readable | Narrative prose under each API; no metadata dump |
| Stable identity | Every API has an `id` that survives renames |
| SSOT | Registry is the source of truth for **API Reference**; curriculum is downstream |
| No invention | Document only symbols verified in `stdlib/vir/` (or mark `proposed` / `planned`) |
| Public ≠ impl layout | Users never need `rt/io`, `stdio.vri`, etc. |

## Scope

**In scope:** user-facing libraries (collections, I/O, net, crypto, …).

**Out of scope for this tree:**

- `compiler.*`, `test.*`, `codegen.*`, `vss.*`, `wir.*`
- Runtime internals (`rt.*`) unless a symbol is part of a public user API
- Lesson prose / textbooks (live under a separate curriculum tree)

Physical module registration remains in `stdlib/stdlib.vri`.
This registry describes the **public API surface** and may use a cleaner
namespace than today's include name (see `source` in front matter).

## File naming

```text
stdlib/registry/<namespace>.md
```

- `<namespace>` is the public name users and docs use (`fs`, `io`, `json`, …).
- Must match front matter `module:`.
- Use lowercase ASCII; prefer flat names (`fs`, not `io.file`).
- Do not create empty placeholder files.

## Front matter (required)

```yaml
---
module: fs
title: Fs
summary: Filesystem path convenience and File handles.
source:
  - name: fs
    path: vir/fs.vri
status: draft          # draft | stable | deprecated
---
```

| Field | Required | Meaning |
|---|---|---|
| `module` | yes | Public namespace; equals filename stem |
| `title` | yes | Short display title |
| `summary` | yes | One sentence |
| `source` | yes | Implementing modules (`stdlib.vri` name + path under `stdlib/`) |
| `status` | yes | Maturity of the **namespace doc** as a whole |

Optional: `aliases`, `previous`, `notes`.

## Document body shape

Exact order:

1. Front matter
2. `# <Title>`
3. One short intro paragraph
4. Optional `## Boundary`
5. Optional `## Migration map` — **required** while under rearchitecture
6. `## API` — index table of every documented public entry
7. One `---` then one section per API entry
8. Optional `## Open questions` / `## Notes`

### Migration map (rearchitecture)

```markdown
## Migration map

| Current symbol | Proposed public | Signature (target) | Implementation source | Action |
|---|---|---|---|---|
| `print` | `io.print` | `io.print(value) -> void` | `vir/io/stdio.vri` | rename |
```

| Column | Rule |
|---|---|
| Current symbol | Name in source today (or `—` if new) |
| Proposed public | Target user-facing name |
| Signature (target) | Intended Vir signature |
| Implementation source | Path under `stdlib/` |
| Action | `keep` \| `rename` \| `move` \| `internal` \| `remove alias` \| `merge` \| `split` \| `planned` \| `incomplete` |

**Do not rename `.vri` sources until the migration map for that cluster is closed.**

### API index table

```markdown
## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `io.print` | `io.print` | `io.print(value) -> void` | proposed |
```

| Column | Rule |
|---|---|
| ID | Stable identity (`<module>.<name>`) |
| Symbol | Proposed public callable (during redesign) or shipped name |
| Signature | One-line Vir signature |
| Status | Per-entry status |

Every row must have a matching detailed section later in the file.

## Per-entry status

| Status | Meaning |
|---|---|
| `stable` | Shipped under this public name; safe to teach |
| `draft` | Shipped (possibly under an old name); docs settling |
| `proposed` | Target public API agreed; source not yet aligned |
| `planned` | Wanted; design or impl still open |
| `incomplete` | Named or partially present; behavior not correct/safe |
| `deprecated` | Still present; prefer replacement |
| `experimental` | Shipped but may break |

## Stable API identity

```markdown
<a id="fs.exists"></a>
## `fs.exists`

<!--
id: fs.exists
api: fs.exists
previous: exists
-->
```

- HTML anchor `id="<stable_id>"` required.
- HTML comment with `id:` required; `api:` is current public symbol; `previous:` on rename.
- Do not treat heading text alone as identity.

## Required fields per API entry

In order:

1. Anchor + `## \`<symbol>\``
2. Metadata HTML comment (`id`, `api`, optional `previous` / `since`)
3. Signature fence (```vir)
4. Semantics prose
5. `### Parameters` — `#### \`name: type\`` with meaning (units, origin, empty/negative)
6. `### Returns` — type + meaning of the value
7. `### Errors` — always present; use `None.` if not observable
8. `### Example` — minimal valid Vir snippet

Optional after Example: `### See also`, `### Notes`, `### Version`.

### Quality bar

Insufficient: `offset: int` / `-> int` alone.  
Required: what it measures, origin, whether negative/zero/empty is allowed.

Examples use real Vir syntax. Prefer symbols matching the entry status.

## Types in signatures

Use Vir types: `string`, `int`, `bool`, `float`, …

**Generics use parentheses `()`, never Rust/C++/TS `<>`:**

```text
Result(T)           # default error type Error
Result(T, E)        # explicit error type
Option(T)
Vec(T) · Map(K, V) · Set(T) · Deque(T)
```

Do not write bare `Result` / `Option` in signatures when the payload type is
known. Void-success `Result` (no payload) may stay as `Result` until a unit
type form is audited — mark that intentionally.
Do not invent foreign names (`str`, `bytes`) unless that type exists in Vir.

## Relationship to `stdlib.vri`

| Layer | Role |
|---|---|
| `stdlib/stdlib.vri` | Module name → physical `.vri` path |
| `stdlib/registry/*.md` | Public API contract + docs SSOT |
| Curriculum / API Reference | Downstream; link by stable `id` |

## Validation checklist

- [ ] Filename stem == `module`
- [ ] Every API table row has a detailed section with the same `id`
- [ ] Every entry has Signature, Semantics, Parameters, Returns, Errors, Example
- [ ] Parameters/Returns explain meaning, not only types
- [ ] `stable` / `draft` match `stdlib/vir/`; futures marked `proposed` / `planned` / `incomplete`
- [ ] Migration map closed before source renames
- [ ] No compiler/test modules documented here

## Non-goals

- Not a second copy of implementation comments
- Not chapter-length tutorials
- Not a package manager store (Viron)
- Not a substitute for `export` in `.vri` sources
