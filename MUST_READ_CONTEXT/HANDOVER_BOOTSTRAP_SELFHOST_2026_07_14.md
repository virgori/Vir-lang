# Handover — Bootstrap Self-Host (`virc_boot.vri`)

**Date:** 2026-07-14  
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

## 2. Current status (verified)

| Stage | Self-host (`virc_boot.vri` as input) | Notes |
|-------|--------------------------------------|-------|
| Tokenize | ✅ | ~1s header + tens of seconds on full file |
| Parse | ✅ | **`virc: parse done`** (~115–200s for full file) |
| Lower | ❌ | Immediate crash after `lowering to Q-IR...` |
| Codegen / link | ❌ | Not reached |

**Regression sanity (must stay green):**

```bash
./core/build/vir run virc_boot.vri -- test_arithmetic.vri
# expect: parse done → done! wrote a.out; run ./a.out → 30 90 75 15 5
```

Small programs that exercise new parser features also work (`tmp/var_tuple2.vri`, `tmp/ent_vec.vri`, `tmp/export_many.vri`, `tmp/arr_param.vri`, `tmp/dot0.vri`).

---

## 3. Crash (next blocker)

```text
virc: parse done
virc: lowering to Q-IR...
# process exit -11 / EXC_BAD_ACCESS
```

LLDB (when captured):

- Stop: `EXC_BAD_ACCESS (code=1, address=0xfffffffffffffffa)`
- Frame: `vm_step` in `core/src/vm.c` (~LoadWord path: `ptr = base + idx`, then `*ptr`)
- Meaning: **while the C VM is interpreting bootstrap’s own lowering**, it executes a bad `LoadWord`/`ArrGet`-style memory op (base ≈ garbage / `-6`).

This is **not** a C-parser crash on `virc_boot.vri` (C still compiles/runs `virc_boot` as the host program). It is a bug in **bootstrap-emitted Q-IR** for the large AST (tuple / `.0` / entity / etc.).

### Likely suspects

1. **Numeric field access** `iv.0` / `iv.1` lowered as `LoadWord(base, index*8)` — must match real tuple return ABI (array vs packed pointer).
2. **Tuple destructuring** `var (a, _) = …` flagged `int_val |= 0x4000` (16384), lowered with `QOp.ArrGet` — layout mismatch with (1).
3. Edge cases in large functions (`compute_liveness`, `emit_fast_*`) that use both patterns heavily.

---

## 4. What was fixed in this push (parser-focused)

All live in **`virc_boot.vri`** only (do not expect matching C-core edits for this session’s parse work).

| Fix | Where / idea |
|-----|----------------|
| Soft names (`map`, keywords as names) | `is_name_tok` / `expect_name` |
| Generics / array types in annots | `skip_type_annot` — `Ident<…>`, `[T]`, trailing `[]` |
| Entity field `Vec<QInstr>` | `parse_entity_def` uses `skip_type_annot` |
| Param `instrs:[QInstr]` | same skip after `:` in `parse_func_def` `in(...)` |
| `var (a, b) = expr` / `var (a, _)` | `parse_var_decl` + flag `16384`; lower via `ArrGet` |
| `expr.0` / `expr.1` | postfix in unary: `Dot` + `Int` → `FieldAccess` name=`rt_itoa`; lower offset `str_to_i64(name)*8` |
| `export a, b, c;` | `Export` builds a `Block` of `ExportStmt`, comma loop + optional `;` |
| `extern func f(a: int; b: int) -> int;` | paren-depth-aware skip (`;` inside params OK) |
| Case parsing (earlier) | `parse_case_stmt` present; **CaseStmt lowering still incomplete** |
| Named call args / tuples / `end.` / bitops / multiline parens | earlier session work already in file |

**Recovery note:** there was an accidental `git checkout -- virc_boot.vri`; content was recovered by splicing `tmp/e_7989.vri` + git tail. Late-file integrity was re-validated via full-file **parse** success.

---

## 5. What NOT to commit / dirty tree traps

Working tree often contains **noise unrelated to bootstrap**:

| Path pattern | Issue | Action |
|--------------|-------|--------|
| `test_*.vri` (hundreds) | Accidental `end.` → `end` + missing final newline | **Do not commit.** Restore with `git checkout -- 'test_*.vri'` |
| `build/virc_merged.vri` | Truncated regen (~417 lines vs ~15k) | **Do not commit.** Restore or regenerate intentionally |
| `core/build/*`, `core/lib/*` | Built objects / `vir` binary | **Do not commit** unless explicitly releasing binaries |
| `tmp/**`, `*.log`, `a.out`, `*.bin` | Scratch / bisect artifacts | Ignore |

**This handover commit should only include:** `virc_boot.vri` + this document.

---

## 6. How to verify quickly

```bash
cd /Users/gengyang/Vir

# 1) Host binary present
ls -la ./core/build/vir

# 2) Tiny regression
./core/build/vir run virc_boot.vri -- test_arithmetic.vri

# 3) Feature smoke (optional)
./core/build/vir run virc_boot.vri -- tmp/var_tuple2.vri
./core/build/vir run virc_boot.vri -- tmp/export_many.vri
./core/build/vir run virc_boot.vri -- tmp/ent_vec.vri

# 4) Full self-host (expect parse OK, then crash in lower)
./core/build/vir run virc_boot.vri -- virc_boot.vri
# Watch for: "parse done" then "lowering..." then SIGSEGV

# 5) Debug crash
lldb -b -o run -o bt -o quit -- ./core/build/vir run virc_boot.vri -- virc_boot.vri
```

**Prefix bisect tip:** full-file parse is slow (~1–3 min). Prefer early-exit when you see `parse done` / `empty AST` instead of waiting for codegen; treat TIMEOUT ≠ EMPTY.

```bash
# Example: stream until parse outcome
python3 - <<'PY'
# (pattern used in session: Popen + kill after parse done / empty AST)
PY
```

---

## 7. Recommended next steps (in order)

### Step A — Stabilize lowering (P0)

1. Build a **minimal repro** that lowers successfully for `var (a,_) = f()` / `t.0` separately, then together, matching C ABI (`core/src/ir_lower.c` ~tuple `0x4000` + numeric field `atoi*8` LoadWord).
2. Confirm whether multi-value `out (x, y)` in bootstrap produces **array** (ArrGet) or **struct pointer** (LoadWord). Align FieldAccess `.N` and destructuring to the **same** representation.
3. Bisect **lower crash** (not parse) on growing prefixes of `virc_boot.vri`: last prefix that reaches `lower done` / `done! wrote a.out` vs first that SIGSEGV right after `lowering...`.
4. Fix bootstrap lower (and only if needed VM) until:

   ```bash
   ./core/build/vir run virc_boot.vri -- virc_boot.vri
   # gets past "lower done"
   ```

### Step B — Codegen / link of self-AST

5. After lower works, fix any empty/`code_size` / Mach-O issues already partially hardened on this branch (`emit_runtime_arm64` opcode hardcoding, etc.).
6. Produce `a.out` from compiling `virc_boot.vri`, then Stage-1: run that binary on a small test, then on itself.

### Step C — Remaining language gaps

7. **CaseStmt lowering** (parser exists; runtime still soft/wrong vs C-core Ok/Err/Some).
8. Re-check splice integrity only if odd late-file behavior appears after lower is fixed.
9. Do **not** “fix” hundreds of `test_*.vri` by stripping `end.` — restore them; `end.` is required for top-level defs.

### Step D — Hygiene before next PR

10. Keep commits to `virc_boot.vri` (+ docs). Exclude build products and corrupted merged/test trees.
11. Update this handover when lower/selfhost binary succeeds.

---

## 8. Key file map

| Path | Role |
|------|------|
| `virc_boot.vri` | Single-file bootstrap compiler (lex/parse/lower/codegen/link) |
| `./core/build/vir` | C host that runs `virc_boot.vri` |
| `core/src/parser.c` | Reference for tuple destructure / export lists / `[T]` params |
| `core/src/ir_lower.c` | Reference for `0x4000` tuples + numeric field offsets |
| `core/src/vm.c` | Crash site during bootstrap-interpreted LoadWord |
| `tmp/e_7989.vri` | Historical splice source used after accidental checkout wipe |
| `tmp/*` | Bisect/repro fragments (disposable) |

---

## 9. Commit message guidance (this checkpoint)

Focus of the checkpoint commit:

- Bootstrap **parses its own source** end-to-end.
- Parser gaps closed for types/exports/tuples/numeric fields.
- Known open: **VM crash in lowering** of the full self AST.

Do not bundle unrelated test/merged churn.
