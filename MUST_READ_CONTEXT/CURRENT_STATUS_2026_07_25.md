# Báo Cáo Tình Trạng Dự Án Vir v2.0
**Ngày:** 2026-07-25 02:55 (GMT+7)  
**Branch hiện tại:** `recovered_stash`

---

## Self-host (honest)

| Stage | Status |
|-------|--------|
| Stage-0 bootstrap suite | **11/11 PASS** (LIR emit + flat MIR opt) |
| Stage-1 parse self (`virc_boot.vri`) | **PASS** — fixed late `g_snap_ast_kids` decl |
| Stage-1 lower full compiler | **Partial** — ~400 funcs lowered; AST/`main` late miss |
| Stage-1 smoke binary | **PASS** — force stub main → `dist/virc-stage1` prints `virc stage1 ok` / `42` |
| Stage-1 real compiler binary | **Not yet** — need full lower of `main`+pipeline + large Mach-O emit |

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri -o dist/virc-stage1
codesign -f -s - dist/virc-stage1
./dist/virc-stage1   # → virc stage1 ok / 42
```

---

## Pipeline

Q staging → Phase-8 MIR/LIR + flat opt → LIR multifn/flat emit → Mach-O (basic42 or full emit).

**Recent fixes**
- `g_snap_ast_kids` declared next to `g_boot_prog_count` (C-VM late-`var` store miss → false empty AST)
- Self-host: `boot_force_bd_stub_main` when dump has no main; emit-only-main for 16KB linker
- Lower budget 400 → 2500; `-o` parsed in `main`; flush uses `g_output_path`

---

## Việc còn lại

1. Restore late FuncDefs / real `main` in self-host lower (not stub).
2. Harden `macho_emit` for large text (full Stage-1 compiler binary).
3. Stage-2: `virc-stage1` compiles `virc_boot.vri` → compare binaries.
