# Handover — Bootstrap Self-Host (`virc_boot.vri`)

**Date:** 2026-07-14 (updated 2026-07-23)  
**Branch:** `recovered_stash`  
**Primary artifact:** `/Users/gengyang/Vir/virc_boot.vri`  
**Runner:** `./core/build/vir` (C-core Stage-0 / VM)

---

## 1. Goal

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri
# expect: parse done → lower #400 → lower done → codegen via body-dump → done! wrote a.out
```

---

## 2. Current status (verified 2026-07-23)

| Stage | Self-host | Notes |
|-------|-----------|-------|
| Tokenize / Parse | ✅ | `for … do` via `match_block_open` |
| Lower | ✅ | Cap **400** funcs when `nfuncs > 64`; name-skip huge bodies |
| Codegen / link | ✅ body-dump | `boot_codegen_emit_mod_min` when `g_bd_total > 0` (name-cell dump flag) |
| Call / print-local / add@scale | ✅ | `cg_call`→42; `cg_scale70`→10/41; Call+Add under dump→30 |
| Stage-1 `a.out` | ⚠️ | Links; bare run may SIGBUS (138); not yet a useful compiler |

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri   # ~45s, EXIT 0
./core/build/vir run virc_boot.vri -- tests/bootstrap_codegen/cg_call.vri  # → 42
./core/build/vir run virc_boot.vri -- tests/bootstrap_codegen/cg_scale70.vri  # → 10 / 41
```

### Syntax contract (do not “normalize” wrongly)

| Block | Open | Close |
|-------|------|-------|
| Definition (`func`/`entity`/…) | `:` | **`end.`** |
| `if` / `eif` | **`do`** | **`end`** |
| `when` | **`loop`** | **`end`** |
| `for` | **`do`** | **`end`** |

---

## 3. What landed recently

1. Syntax freeze across `virc_boot` / tests / stdlib + docs.
2. Boot `parse_for_range_stmt` accepts `do` (`TokType.Then`).
3. Self-host **body-dump codegen** without new Vir globals:
   - name-cell **72** = dump on, **80** = op cap
   - `boot_bd_dump_on()` = small_multi **or** dump flag
   - Larger `heap_alloc` bd buffers; `boot_do_lower` uses `mod_min` when `g_bd_total > 0`
4. **Do not** add new boot globals near the flag block — layout shift breaks Call smokes on C VM.
5. **Do not** dual-write `ir_emit` on the bd path (entity returns clobber mid-lower).
6. **`g_boot_func_tab`** sized **8192** (≥1024 funcs) — old 512B overflowed Call targets at scale.
7. **`boot_vmap_put`** also active when dump-on (not only small_multi) — fixes `print x` after Call at `nfuncs>64`.
8. Parse-time **blk lhs/rhs** Ident names for BinOp inits — fixes `let c = a + b` under dump (Ident.name clobber).
9. Binop emit scratch moved to name-cell **160..184** — must not reuse flag slots 72/80.

---

## 4. Still open

1. Raise / remove the 400-fn lower cap once remaining bodies are safe.
2. Grow opcode coverage in `boot_codegen_emit_mod_min` (branches, strings/`sys_write`, more locals).
3. True entity-walking `codegen_emit_module` under C VM (still unsafe).
4. Persist entity metadata in native cells so Vec headers cannot clobber mid-lower.
5. Prove Stage-1 `a.out` can compile a smoke (fixed-point path) — needs I/O + fuller main.

**Flat policy:** `main` only when AST kids `< 40` and dump off. **Small-multi:** `1 < nfuncs < 8`. **Self-host dump:** `nfuncs > 64`.

---

## 5. Key files

| Path | Role |
|------|------|
| `virc_boot.vri` | Bootstrap compiler |
| `core/src/vm.c` / `vm.h` | Interpreter Call + label cache |
| `tests/bootstrap_codegen/` | cg_* regression fixtures |
