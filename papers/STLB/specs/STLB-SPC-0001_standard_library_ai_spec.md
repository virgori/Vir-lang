---
id: "STLB-SPC-0001"
type: "SPEC"
domain: "STLB"
title: "Vir Standard Library (AI Spec)"
status: "ACTIVE"
version: "2.0.0"
language: "en"
spec_class: "SPECIFICATION"
created: "2026-09-06"
updated: "2026-10-02"
owners:
  - "STLB"
components: []
aliases:
  - "docs/ai-spec/vir-lang/references/stdlib.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# STLB-SPC-0001 — Vir Standard Library (AI Spec)

**Rule:** Do **not** invent APIs. Prefer symbols that exist under `stdlib/vir/` or that appear in nearby project code. If unsure, say the API is unverified and search the tree.

## Layout

```text
stdlib/vir/
  prelude.vri      # auto-imported basics (types, option, result, string helpers, …)
  rt/              # runtime (alloc, string_rt, vec_rt, syscall, …)
  compiler/        # full compiler sources (.vri)
  io/, fs/, str/, math/, net/, http/, json/, …
```

Module path `vir.io.file` style maps to directories under `stdlib/vir/`.

## Safe defaults for toy programs

These appear widely in tests / bootstrap samples:

```vir
print(expr)
print("text $var")
out 0
```

Do not assume libc names (`printf`, `malloc`, `printf`-style format strings) unless a Vir binding is shown in-repo.

## Prelude (indicative)

`stdlib/vir/prelude.vri` pulls common pieces, for example:

- Types via `include types`
- `Option` / `Result` via `option`, `result`
- String helpers via `string` (`str_new`, `str_len`, `str_concat`, …)
- Checked arithmetic via `ops`

Exact export lists change — **read the file** before teaching an API.

## Common packages (existence, not full API)

| Path | Area |
|---|---|
| `stdlib/vir/io/file.vri` | File I/O |
| `stdlib/vir/fs/` | Filesystem |
| `stdlib/vir/str/` | Strings / unicode |
| `stdlib/vir/math/` | Math / tensors / NN |
| `stdlib/vir/http/` `net/` | Networking |
| `stdlib/vir/json/` `yaml/` `serde/` | Serialization |
| `stdlib/vir/collections/` | Collections |
| `stdlib/vir/rt/` | Runtime primitives |
| `stdlib/vir/compiler/` | Self-hosted compiler |

## How agents should resolve an API

1. Grep / open the module under `stdlib/vir/…`
2. Prefer `export`ed `func` / `entity` names from that file
3. Use Vir `include` / `import … from` (see `modules.md`)
4. If the symbol is only in C runtime (`core/`), treat as FFI / internal — do not expose casually in user samples

## Compiler toolchain (workflow, not inventable)

Production compile uses native `bin/virc` (see repo rules). Do not instruct agents to invent a C-VM compile path for full `virc.vri`.

## Agent rules

1. Inventing `std::…`, `fmt.Println`, `console.log`, `println!` is forbidden.
2. Document only APIs you verified in-tree for this answer.
3. For incomplete stdlib surfaces, state limitations explicitly.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 2.0.0 | Migrated from `docs/ai-spec/vir-lang/references/stdlib.md` and assigned stable ID `STLB-SPC-0001` |
