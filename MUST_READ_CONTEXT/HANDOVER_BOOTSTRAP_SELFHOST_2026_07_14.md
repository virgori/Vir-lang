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
| Codegen / link | ⚠️ partial | Flat-IR path (`boot_codegen_flat_min`) emits real Print/Ret for small programs; full `codegen_emit_module` still too fragile on C VM |

**Codegen smoke (verified):**

```bash
./core/build/vir run virc_boot.vri -- tmp/cg_arith.vri
codesign -s - -f a.out && ./a.out
# expect: 30\n90\n (print immediates via flat staging → ARM64)
```

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

## 3b. Field-offset + first real codegen (2026-07-17 continued)

| Fix | Where | Idea |
|-----|-------|------|
| `Vec<T>` → `[T]` in parser | `core/src/parser.c` | Preserve element type so `vec_get_rt` can infer |
| Element-type for `vec_get_rt` | `core/src/ir_lower.c` | `copy_expr_type_name` returns `T` from container `[T]` |
| HIR var-decl type infer | `hir_lower.c` + `lower_infer_symbol_type` | Pipeline path previously never set `symbol.type_name` → field offsets fell back to scan-all (wrong) |
| Flat staging codegen | `virc_boot.vri` `boot_codegen_flat_min` | Walk `g_boot_q_*` with `g_emit_word` only (multi-arg helpers clobbered on C VM) |
| `boot_ir_*` staging | `virc_boot.vri` | Write flat arrays via `native_write_i64` / `boot_set_imm` cell — avoid 2-arg helpers |

**Root-cause note (entity fields):** the bug was **not** primarily `vm.c` LoadWord/StoreWord. It was **`ir_lower.c` field-offset fallback** picking the first record type that had a matching field name when the base expression had no inferred type. The HIR pipeline also skipped record-type inference on `let` bindings.

### Still open (next)

1. Wire `print x` (Identifier) end-to-end with correct vreg/const (last-vreg fallback prints wrong var; name lookup still flaky).
2. Grow `boot_codegen_flat_min` (Add/Sub/Mul + non-const) until it can replace the stub for self-host.
3. Eventually run full `codegen_emit_module` once multi-arg/entity issues shrink (or under a native stage-1 binary).
4. Fix/lower legacy `compile` / `virc_legacy_main` (or delete once unused).
5. CaseStmt / Ok-Err lowering gaps.

---

## 4. How to verify quickly

```bash
cd /Users/gengyang/Vir
./core/build/vir run virc_boot.vri -- tmp/cg_arith.vri && codesign -s - -f a.out && ./a.out
./core/build/vir run virc_boot.vri -- virc_boot.vri
# Watch for: parse done → lower done → done! wrote a.out
```

---

## 5. Key file map

| Path | Role |
|------|------|
| `virc_boot.vri` | Bootstrap compiler |
| `./core/build/vir` | C host VM |
| `core/src/vm.c` | Interpreter (LoadWord/StoreWord OK) |
| `core/src/ir_lower.c` | Field-offset + type inference (critical) |
| `core/src/hir_lower.c` | HIR var-decl must call `lower_infer_symbol_type` |
| `core/src/parser.c` | `Vec<T>` stored as `[T]` |
