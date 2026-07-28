# Spec §29–§30 → IR Surface Roadmap

Updated: 2026-07-26  
**Phases:** Lexer ✅ → Parser ✅ → ast_to_mir ✅ → lir_lower ✅ → **lir_codegen ✅** → Runtime (stubs OK)

Sources: `lexer.vri` … `lir_codegen.vri`, `virc.vri`  
Related: [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md)

---

## 0. Layers

| Layer | Soft status |
|-------|-------------|
| Lexer | Spec §29 **75/75** keywords |
| Parser | All keyword + op `TokType` → AST |
| **ast_to_mir** | **All 95 AstTypes + 24 OpTypes referenced** |
| **lir_lower** | **All MirOp 0–30 → LirOp**; preserves `name`/`strings` |
| **lir_codegen** | **OK** — SetArg X0..X7, Call/Intrinsic/ML BL patched to func/RT table |

---

## 1. Operators → MIR (complete)

| OpType | Lowering |
|--------|----------|
| Add…Mod, Cmp*, And/Or/Xor/Shl/Shr, Pow/MatMul/Fma | `MirOp.*` |
| SafeEq/SafeNe | CmpEq/CmpNe |
| Land / Lor | CFG (`JumpIf` / `JumpIfNot`) |
| PatternOp (`:~`) | `MIR_INTR_PATTERN` |
| Unary `~` | `MirOp.Not` |
| `&` / `&mut` | `MIR_INTR_ADDR_OF` + SetArg mut flag |
| postfix `?` | `MIR_INTR_EXIST` |
| `?.` / `~mask` / `!!` | SAFE_ACCESS / SWIZZLE / ATOMIC |

**OpType gap: 0.**

---

## 2. Keywords / AstTypes → MIR (complete)

| AstType | MIR |
|---------|-----|
| Core control/expr (0–86 prior) | Jump*/Call/Intrinsic as before |
| TypeAlias, LazyInclude, Share/Has, Class, Dict/Tensor/Flux | `MIR_INTR_DECL` |
| PrecompBlock / FuncDef `precomp` | `MIR_INTR_PRECOMP` |
| FuncDef `async` | `MIR_INTR_ASYNC` |
| FuncDef `method` | DECL marker |
| AtomicVarDecl | `MIR_INTR_ATOMIC_VAR` + child VarDecl |
| ReactiveDecl / MorphDecl | REACTIVE / MORPH |
| BundleExpr / MapExpr / ArrCompactExpr | BUNDLE / MAP / ARR_COMPACT |
| ExposeAttr | EXPOSE + inner FuncDef |
| PtrTypeExpr / ErrorExpr / ExistExpr / PatternExpr | PTR / ERROR / EXIST / PATTERN |
| TimeoutClause / IsolateClause | TIMEOUT / ISOLATE |
| TryStmt | TRY + walk Timeout/Isolate/body/Revert |

**AstType gap: 0** (audit: every `AstType.X` appears in `ast_to_mir.vri`).

---

## 3. MIR_INTR_* range

| Range | Tags |
|-------|------|
| 1–28 | prior (STR_LIT…NOP_MARKER) |
| 29–45 | TASK…ATOMIC |
| **46–60** | **EXIST PATTERN MAP ARR_COMPACT BUNDLE TIMEOUT ISOLATE ERROR PRECOMP REACTIVE MORPH EXPOSE PTR ASYNC ATOMIC_VAR** |

---

## 4. Counts

| Metric | Value |
|--------|------:|
| Spec §29 keywords (lexer) | 75/75 |
| AstTypes | 95 |
| OpTypes | 24 |
| Soft MirOp | 31 (0–30) |
| Soft MIR_INTR_* | **60** |
| Open keyword/op → MIR gaps | **0** |

---

## 5. Soft LIR / codegen (2026-07-26) — ABI + BL resolve done

| Item | Status |
|------|--------|
| `LirOp` 0–26 + `lir_op_tag` + `LIR_RT_*` | **OK** |
| MirOp → LirOp map | **OK** |
| SetArg 0..7 → `MOV X0..X7` | **OK** |
| SetArg ≥8 → stack push; Call pops | **OK** |
| Call → `BL` patched to `LirFunc.name` match | **OK** |
| Unresolved Call → RT stub 0 (return 0) | **OK** |
| Intrinsic marker / payload inline | **OK** |
| Intrinsic runtime → RT stub[kind] (1..60) | **OK** |
| Pow / MatMul / Fma → stub 61/62/63 | **OK** |
| `virc` ARM64 → `emit_lir_module_arm64` | **OK** |

## 6. Remaining (runtime richness, not ABI gaps)

- RT stub bodies still thin (passthrough / 0); enrich PRINT/ARRAY/… when rt lib lands  
- Live `virc_boot` path still parallel (not soft SSA)
- Soft RA target: LIR clean → Chaitin–Briggs → George–Appel coalesce — [`REGISTER_ALLOCATION_ARCHITECTURE.md`](REGISTER_ALLOCATION_ARCHITECTURE.md) (`lir_clean` / `lir_coalesce_appel` still TODO)

Next: smoke tests soft LIR module, or thicken individual RT stubs.
