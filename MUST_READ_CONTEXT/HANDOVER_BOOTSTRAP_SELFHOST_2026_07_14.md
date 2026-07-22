# Handover — Bootstrap Self-Host (`virc_boot.vri`)

**Date:** 2026-07-14 (updated 2026-07-17 night)  
**Branch:** `recovered_stash`  
**Primary artifact:** `/Users/gengyang/Vir/virc_boot.vri`  
**Runner:** `./core/build/vir` (C-core Stage-0 / VM)

---

## 1. Goal

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri
# expect: parse done → lower #400 → lower done → done! wrote a.out  (~50s)
```

---

## 2. Current status (verified 2026-07-17)

| Stage | Self-host | Notes |
|-------|-----------|-------|
| Tokenize / Parse | ✅ | |
| Lower | ✅ | Cap **400** funcs when `nfuncs > 64`; name-skip huge bodies |
| Codegen / link | ✅ stub | `boot_codegen_basic42` + Mach-O via **mmap** buffer |
| Call smokes | ✅ | `cg_arith`→30/90, `cg_call`/`cg_call0`/`cg_mod2`→42 |

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri   # ~50s, EXIT 0
./core/build/vir run tmp/cg_call.vri                  # → 42
```

---

## 3. What unblocked tonight

### Hang: `VarDecl` then `FieldAssign` (blocked at `arena_alloc`)

After any `let`, `ctx.ent_field_counts` can be clobbered on the C VM → FieldAssign’s nested loop spun forever (looked like a hang at `arena_alloc`).

**Fix in `virc_boot.vri`:**
1. Harden `ent_field_offset_flat` (clamp counts; linear name-scan fallback).
2. Rewrite `FieldAssign` to snapshot `name`/`name2`, use the flat helper + name-scan fallback.
3. EntityDef stores **byte** offsets (`i * 8`), matching C `ir_lower`.

### Prior (still in place)

1. **Label-map cache SIGBUS:** full `VM_MAX_LABELS` maps per cache entry.
2. **Call path:** memcpy save/restore with `VM_CALL_SAVE_MIN=1024`.
3. **Self-host cap / name-skips** for `lower_*`, `codegen_emit_*`, huge parse/emit helpers.
4. **Mach-O buffer:** `boot_macho_page_buf()` via `sys_mmap`; `bvec_reserve` length at byte offset **8**.

---

## 4. Still open

1. Raise / remove the 400-fn cap once remaining bodies are safe (or skip only by name).
2. Full `codegen_emit_module` under C VM (still stub → basic42).
3. Grow Call beyond smoke; optional faster dirty-reg Call window.
4. Persist entity metadata in native cells so Vec headers cannot clobber mid-lower.

**Flat policy:** `main` only when AST kids `< 40`. **Small-multi:** `1 < nfuncs < 8`.

---

## 5. Key files

| Path | Role |
|------|------|
| `virc_boot.vri` | Bootstrap compiler |
| `core/src/vm.c` / `vm.h` | Interpreter Call + label cache |
| `core/src/ir_lower.c` | Field-offset / type inference |
