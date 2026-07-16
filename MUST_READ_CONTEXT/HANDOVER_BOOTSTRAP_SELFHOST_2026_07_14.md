# Handover — Bootstrap Self-Host (`virc_boot.vri`)

**Date:** 2026-07-14 (updated 2026-07-17)  
**Branch:** `recovered_stash`  
**Primary artifact:** `/Users/gengyang/Vir/virc_boot.vri` (~15k lines)  
**Runner:** `./core/build/vir` (C-core Stage-0 / VM)

---

## 1. Goal

Make the Vir bootstrap compiler self-host:

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri
```

Pipeline expected: tokenize → parse → lower → codegen → Mach-O → `a.out`.

---

## 2. Current status (verified 2026-07-17)

| Stage | Self-host (`virc_boot.vri` as input) | Notes |
|-------|--------------------------------------|-------|
| Tokenize | ✅ | |
| Parse | ✅ | `virc: parse done` |
| Lower | ✅ | `virc: lower done` (~2 min after parse) |
| Codegen / link | ⚠️ stub | Still uses `boot_codegen_basic42` / basic Mach-O path, not real self-AST codegen |

**Regression sanity (must stay green):**

```bash
./core/build/vir run virc_boot.vri -- test_arithmetic.vri
# expect: parse done → lower done → done! wrote a.out
```

---

## 3. What was fixed to get past lower (2026-07-17)

Root theme: **C-core VM entity return/assign + stale parse scratch are unreliable** under deep bootstrap call frames. Prefer in-place mutation + flat globals.

| Fix | Idea |
|-----|------|
| `ir_emit` / `fresh_vreg` / `fresh_label` / `lower_error` | Do **not** return `LowerCtx`; mutate heap entity in place |
| `lower_expr` / `lower_stmt` / `lower_program` | Return vreg/`0` only; never `ctx = lower_*(...)` |
| `lower_stmt` default | Was `ctx = lower_expr(...)` (int→entity) — immediate corruption |
| Block lowering | Stopped using stale `g_boot_blk_*` from last parsed block |
| `native_read/write_u8/i64` | Lower directly to Load/Store Byte/Word (inline externs missing from func table) |
| String literals | Seed/use `g_mod_strings_acc` in `q_module_new`; avoid nested `ctx.mod_obj.strings` |
| Skip during self-lower | `compile`, `virc_legacy_main` (old `print "..."` / Result / concat) still SIGSEGV the lowerer |

### Still open (next)

1. **Real codegen** of lowered self-AST (replace `boot_codegen_basic42`).
2. Fix/lower legacy `compile` / `virc_legacy_main` (or delete once unused).
3. CaseStmt / Ok-Err lowering gaps.
4. Optional: harden C VM entity return so workarounds can shrink.

---

## 4. How to verify quickly

```bash
cd /Users/gengyang/Vir
./core/build/vir run virc_boot.vri -- test_arithmetic.vri
./core/build/vir run virc_boot.vri -- virc_boot.vri
# Watch for: parse done → lower done → done! wrote a.out
```

---

## 5. Key file map

| Path | Role |
|------|------|
| `virc_boot.vri` | Bootstrap compiler |
| `./core/build/vir` | C host VM |
| `core/src/vm.c` | Entity/call-frame issues |
| `core/src/ir_lower.c` | Reference lowering |
