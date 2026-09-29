# Audit — Generic syntax → `of (...)`

**Date:** 2026-09-29  
**Decision:** Canonical Vir generics = `Name of (...)` (declarations + applications).  
**Compiler:** not updated in this wave — source/docs migrated first.

## Before → after

| Legacy | Canonical |
|---|---|
| `Vec<T>` / `Option<T>` / `Map<K,V>` | `Vec of (T)` / `Option of (T)` / `Map of (K, V)` |
| `entity Map<K, V>:` | `entity Map of (K, V):` |
| `func f<T>(...)` | `func f of (T)(...)` |
| `size_of<T>()` | `size_of of (T)()` |
| bare type app `Vec(string)` | `Vec of (string)` |
| nested `Option<Vec<T>>` | `Option of (Vec of (T))` |

Constructors with field init stay unchanged:

```text
Path(raw: s)     # not a generic application
IoError(kind: …)
```

## Scope applied

| Tree | Files touched (approx) | Notes |
|---|---|---|
| `stdlib/vir/**/*.vri` | ~250+ | angle + paren type apps |
| `stdlib/registry/**/*.md` | registry SSOT | `Result(T)` → `Result of (T)` |

Rough volume: ~4000+ angle replacements, ~400+ paren type apps, nested cleanup pass.

## Verification (static)

- `Ident<Ident` leftovers in `stdlib/vir`: **0**
- `of (` occurrences in vir: **~4200+**
- Prose/comments may still say “Option (…)” in English — not type syntax

## Not done / deferred to compiler wave

1. Parser/typechecker accept `of (...)` as sole generic form (drop `<>` preference).
2. Codegen / mangling for `of` specializations.
3. Re-promote `bin/virc` after compiler understands `of`.
4. False-friend review: ARM asm comments with `<<` (left alone).
5. Call sites that were already `vec_new of (T)()` — valid per spec once compiler lands.

## Status

**Library source + registry: migrated to `of (...)`.**  
**Runtime compile with current `bin/virc`: expected FAIL until compiler catches up.**  
Not production-certified.
