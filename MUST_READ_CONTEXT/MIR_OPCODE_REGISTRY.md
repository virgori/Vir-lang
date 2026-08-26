# MIR Opcode & Function Registry

**Source of truth for later `MIR_` / SSA / LIR / codegen.**  
Do **not** invent alternate names — import these constant/enum tags and call the listed functions.

| Artifact | Path |
|----------|------|
| Enums / consts / tags | `stdlib/vir/compiler/mir.vri` |
| AST → MIR emit | `stdlib/vir/compiler/ast_to_mir.vri` |
| Tag helpers | `mir_op_tag(op)`, `mir_intr_tag(kind)` |
| Checklist | [`AST_TO_MIR_LOWERING_CHECKLIST.md`](AST_TO_MIR_LOWERING_CHECKLIST.md) |
| Spec→IR gap / P0–P2 roadmap | [`SPEC_IR_SURFACE_ROADMAP.md`](SPEC_IR_SURFACE_ROADMAP.md) |

Updated: 2026-07-26

---

## Coverage

**Official IR spine:** AST → **HIR** → **MIR** → **LIR** → Codegen (Spec §1.2). Soft may still emit AST→MIR until HIR is wired.  
**Do not conflate:** Syntax (lex/parse) ≠ IR contract (`MirOp`/`MIR_INTR_*`) ≠ Lowering (`ast_to_mir`).  
Measurable gap vs Spec §29–§30: [`SPEC_IR_SURFACE_ROADMAP.md`](SPEC_IR_SURFACE_ROADMAP.md) (Spec→AST→HIR→MIR→LIR→Codegen→Runtime + P0/P1/P2).  
**Soft lexer:** Spec §29 keywords **75/75**.  
**Soft parser:** all keyword + op `TokType` → AST.  
**Soft ast_to_mir:** all **95 AstTypes** + **24 OpTypes** lowered (roadmap §1–2). `MIR_INTR_*` **1–60**.

What each layer is responsible for covering (green = done in soft pipeline files).

| Layer | Owns coverage of | Status |
|-------|------------------|--------|
| Parser `AstType` | All executable + decl nodes | **OK** (parse) |
| `ast_to_mir` | Every executable AstType → `MirOp` / `MIR_INTR_*` | **OK** |
| `ast_to_mir` decl markers | Enum/Entity/Import/… → `MIR_INTR_DECL` in `__mir_decls` | **OK** |
| `mir.vri` | Enum `MirOp`, consts `MIR_INTR_*`, `mir_op_tag` / `mir_intr_tag` | **OK** |
| `mir_cfg` / `mir_ssa` | CFG edges already from builder; Phi + rename | **OK** (soft) |
| `mir_opt` | Local CF / copy / DCE on MIR blocks | **OK** (soft) |
| `lir.vri` | `LirOp` 0–26, aux, `lir_op_tag`, `LIR_RT_*` | **OK** |
| `lir_lower` | MirOp → LirOp; copy `name`/`strings` | **OK** (all MirOp 0–30) |
| `lir_codegen` | LirOp → ARM64 module (`emit_lir_module_arm64`) | **OK** (ABI + BL patch) |
| Live `virc_boot` | Flat MIR → Mach-O (suite / Stage-1) | **OK** (separate path) |

### Coverage by MirOp family

| Family | Ops | AST→MIR | Soft LIR | Soft ARM64 |
|--------|-----|---------|----------|------------|
| Data move | Move, Load, Store | **OK** | **OK** | **OK** |
| Arith | Add, Sub, Mul, Div, Mod | **OK** | **OK** (Mod→Rem) | **OK** (+ Imm) |
| Bitwise | And, Or, Xor, Shl, Shr, Not | **OK** | **OK** | **OK** (+ Imm) |
| ML / pow | Pow, MatMul, Fma | **OK** | **OK** | **OK** (BL→`LIR_RT_POW`..FMA) |
| Compare | CmpEq..CmpLe | **OK** | **OK** (aux pred) | **OK** (+ Imm) |
| Control | Jump, JumpIf, JumpIfNot, Return | **OK** | **OK** | **OK** (fixup; Ret→X0) |
| Call ABI | SetArg, Call | **OK** | **OK** | **OK** (X0..X7 + BL patch) |
| Intrinsic | Intrinsic + `MIR_INTR_*` (1–60) | **OK** | **OK** (`aux`=kind) | **OK** (inline / RT stub) |

### Coverage by Intrinsic (`MIR_INTR_*`)

| Range | Tags | AST emit | Soft ARM64 |
|-------|------|----------|------------|
| 1–7 | STR_LIT…INTERP | **OK** | payload MOV / RT stub[kind] |
| 8–11 | BUILTIN…MATCH_PAT | **OK** | payload or RT stub |
| 12–17 | INPUT…QUIET | **OK** | QUIET→NOP; else RT |
| 18–23 | ARENA…STR_EQ | **OK** | RT stub[kind] |
| 24–28 | CHECK_CPU…NOP_MARKER | **OK** | markers→NOP |
| 29–45 | TASK…ATOMIC | **OK** | RT stub[kind] |
| 46–60 | EXIST…ATOMIC_VAR | **OK** | marker/payload/RT |

---

## Ownership

Who may **define**, **emit**, **mutate**, or **consume** each artifact. Later `MIR_` code must not steal ownership of emit or rename tags.

### Artifact ownership

| Artifact | Define (schema) | Emit (create) | Mutate (transform) | Consume (read) |
|----------|-----------------|---------------|--------------------|----------------|
| `MirOp` enum / numbers | `mir.vri` | — | **forbidden** (append-only) | all MIR_/LIR |
| `MIR_INTR_*` consts | `mir.vri` | — | **forbidden** (append-only) | `ast_to_mir`, LIR, rt |
| `mir_op_tag` / `mir_intr_tag` | `mir.vri` | — | keep 1:1 with enums | dumps / tests |
| `MirFunc` / `MirBlock` / `MirInstr` | `mir.vri` | `ast_to_mir` (`builder_*`, `emit_*`) | `mir_ssa`, `mir_opt` | `lir_lower` |
| `MirFunc.strings` | `mir.vri` field | `builder_intern` / `mir_intern_string` | only intern (append) | Call/Intrinsic resolve |
| CFG `successors`/`preds` | `MirBlock` | `builder_add_edge` | SSA may refine; no silent drop | CFG/SSA/LIR |
| Phi (`MirPhi`) | `mir.vri` | **`mir_ssa` only** | `mir_ssa` rename | `lir_lower` (→ Mov) |
| VarMap / vreg map | `ast_to_mir` | `set_var_vreg` | builder only (pre-SSA) | — (ends at lower) |
| `__mir_decls` func | name convention | `ast_lower_program` | none | linker / metadata |
| `LirOp` / `LirInstr.aux` / `lir_op_tag` | `lir.vri` | `lir_lower` | regalloc | `lir_codegen` |
| Live flat MIR (`g_bd_*`) | `virc_boot.vri` | boot lower | boot phase8 | boot codegen |

### Phase ownership (pipeline order)

```text
mir.vri          → schema owner (names + numbers)
ast_to_mir.vri   → emit owner (only place that creates MirInstr from AST)
mir_cfg.vri      → CFG analysis owner (read edges; may recompute)
mir_ssa.vri      → SSA owner (Phi insert + rename)  [DEFER from ast_to_mir]
mir_opt.vri      → opt owner (may Nop/Move rewrite; must keep MirOp tags)
lir_lower.vri    → MIR→LIR owner (must use MirOp.* / MIR_INTR_* consts)
lir_*.vri        → LIR owner
lir_codegen.vri  → soft machine owner
virc_boot.vri    → live bootstrap owner (parallel path; do not fork MirOp names)
```

### Ownership rules for MIR_ authors

1. **Do not** redefine `MirOp` / `MIR_INTR_*` in another file — `import` from `mir.vri`.  
2. **Do not** emit AST→MIR from SSA/opt — only transform existing `MirInstr`.  
3. **Phi** only in `mir_ssa.vri` (`mir_insert_phi_nodes`).  
4. New opcode/intrinsic: add to `mir.vri` + `mir_op_tag`/`mir_intr_tag` + this registry + checklist in one change.  
5. String ids always index `MirFunc.strings` owned by intern helpers — no side tables with different names.  
6. Live boot path owns its own tables (`g_bd_*`); soft MIR_ code owns `MirFunc`/`MirBlock`.

---

## 1. `MirOp` — exact enum names (`mir.vri`)

| # | Enum tag (`MirOp.X`) | String (`mir_op_tag`) | Emitted by (ast_to_mir) |
|---|----------------------|----------------------|-------------------------|
| 0 | `MirOp.Nop` | `Nop` | (opt / unused) |
| 1 | `MirOp.Move` | `Move` | `emit_move`, LiteralInt/Float, Assign, VarDecl, Loop induction |
| 2 | `MirOp.Load` | `Load` | `emit_load` |
| 3 | `MirOp.Store` | `Store` | `emit_store` |
| 4 | `MirOp.Add` | `Add` | BinOp `+`, For/Loop step |
| 5 | `MirOp.Sub` | `Sub` | BinOp `-`, UnaryMinus |
| 6 | `MirOp.Mul` | `Mul` | BinOp `*` |
| 7 | `MirOp.Div` | `Div` | BinOp `/` |
| 8 | `MirOp.Call` | `Call` | Call / BuiltinCall / MethodCall |
| 9 | `MirOp.Intrinsic` | `Intrinsic` | `emit_intrinsic` — kind in `src2.imm` |
| 10 | `MirOp.Jump` | `Jump` | `emit_jump` — `src1.imm` = block id |
| 11 | `MirOp.JumpIf` | `JumpIf` | `emit_jump_if` — `src1`=cond, `src2.imm`=then |
| 12 | `MirOp.Return` | `Return` | ReturnStmt |
| 13 | `MirOp.CmpEq` | `CmpEq` | Compare / Case |
| 14 | `MirOp.CmpNe` | `CmpNe` | Compare |
| 15 | `MirOp.CmpGt` | `CmpGt` | Compare |
| 16 | `MirOp.CmpLt` | `CmpLt` | Compare / For / Loop |
| 17 | `MirOp.CmpGe` | `CmpGe` | Compare |
| 18 | `MirOp.CmpLe` | `CmpLe` | Compare |
| 19 | `MirOp.Mod` | `Mod` | BinOp `%` / `mod` |
| 20 | `MirOp.SetArg` | `SetArg` | `emit_set_arg` — `src1.imm`=index, `src2`=value |
| 21 | `MirOp.JumpIfNot` | `JumpIfNot` | `emit_jump_if_not` — then if cond==0 |
| 22 | `MirOp.And` | `And` | `&` / `bit_and` |
| 23 | `MirOp.Or` | `Or` | `\|` / `\|\|` / `bit_or` |
| 24 | `MirOp.Xor` | `Xor` | `xor` |
| 25 | `MirOp.Shl` | `Shl` | `<<` / `shl` |
| 26 | `MirOp.Shr` | `Shr` | `>>` / `shr` |
| 27 | `MirOp.Not` | `Not` | unary `~` (`AstType.UnaryNot`) |
| 28 | `MirOp.Pow` | `Pow` | `^` |
| 29 | `MirOp.MatMul` | `MatMul` | `**` (§26.2) |
| 30 | `MirOp.Fma` | `Fma` | `><` (§26.2) |

`and` / `or` (words) → **CFG** (`Land`/`Lor`), not MirOp.

### Operand rules (later MIR_ must honor)

| Op | dst | src1 | src2 |
|----|-----|------|------|
| Move | vreg | imm \| vreg | — |
| Load | vreg | addr | — |
| Store | — | value | addr |
| Add..Fma / Cmp* / And..Shr | vreg | lhs | rhs |
| Not | vreg | src | — |
| Call | vreg (ret) | imm **nargs** | imm **callee pool id** |
| SetArg | — | imm **arg index** | value |
| Intrinsic | vreg \| — | payload | imm **`MIR_INTR_*` kind** |
| Jump | — | imm **block id** | — |
| JumpIf / JumpIfNot | — | cond | imm **then block id** |
| Return | — | value \| — | — |

String pool: `MirFunc.strings[id]` via `mir_intern_string` / `builder_intern`.

---

## 2. `MIR_INTR_*` — exact const names (`mir.vri`)

| # | Const name | Tag (`mir_intr_tag`) | Layout | Emit helper / site |
|---|------------|----------------------|--------|--------------------|
| 1 | `MIR_INTR_STR_LIT` | `STR_LIT` | src1=pool id | LiteralStr |
| 2 | `MIR_INTR_PRINT` | `PRINT` | src1=value | PrintStmt |
| 3 | `MIR_INTR_ARRAY` | `ARRAY` | SetArg 0..n-1 elems; src1=len | `lower_aggregate` |
| 4 | `MIR_INTR_TUPLE` | `TUPLE` | same | `lower_aggregate` |
| 5 | `MIR_INTR_ENTITY` | `ENTITY` | elems + SetArg(n)=type pool id; src1=len | `lower_aggregate` |
| 6 | `MIR_INTR_ADDR_OF` | `ADDR_OF` | src1=pointee | AddrOf |
| 7 | `MIR_INTR_INTERP` | `INTERP` | src1=pool id | InterpExpr |
| 8 | `MIR_INTR_BUILTIN` | `BUILTIN` | src1=builtin_id | before BuiltinCall `Call` |
| 9 | `MIR_INTR_INDEX` | `INDEX` | src1=base; SetArg0=idx | IndexAccess |
| 10 | `MIR_INTR_FIELD` | `FIELD` | src1=base; SetArg0=field pool id | FieldAccess |
| 11 | `MIR_INTR_MATCH_PAT` | `MATCH_PAT` | src1=scrutinee; SetArg0=pat pool id | CaseExpr tagged |
| 12 | `MIR_INTR_INPUT` | `INPUT` | — | InputExpr |
| 13 | `MIR_INTR_ENUM` | `ENUM` | SetArg0/1 = enum/variant pool ids | EnumAccess |
| 14 | `MIR_INTR_CAST` | `CAST` | + Move | CastExpr |
| 15 | `MIR_INTR_THROW` | `THROW` | src1=value? | ThrowStmt |
| 16 | `MIR_INTR_CANCEL` | `CANCEL` | src1=value? | CancelStmt |
| 17 | `MIR_INTR_QUIET` | `QUIET` | — | QuietStmt |
| 18 | `MIR_INTR_ARENA` | `ARENA` | src1=name pool id | ArenaBlock |
| 19 | `MIR_INTR_ENSURE` | `ENSURE` | marker | EnsureBlock |
| 20 | `MIR_INTR_REVERT` | `REVERT` | marker | RevertBlock |
| 21 | `MIR_INTR_INDEX_STORE` | `INDEX_STORE` | src1=base; SetArg0=idx, SetArg1=val | IndexAssign |
| 22 | `MIR_INTR_FIELD_STORE` | `FIELD_STORE` | src1=base; SetArg0=field id, SetArg1=val | FieldAssign |
| 23 | `MIR_INTR_STR_EQ` | `STR_EQ` | src1=scrutinee; SetArg0=str pool id | CaseExpr LiteralStr |
| 24 | `MIR_INTR_CHECK_CPU` | `CHECK_CPU` | — | CheckCpu |
| 25 | `MIR_INTR_PATCH_POINT` | `PATCH_POINT` | src1=name pool id | PatchPoint |
| 26 | `MIR_INTR_DECL` | `DECL` | src1=AstType#; SetArg0=name pool id | `lower_decl_marker` |
| 27 | `MIR_INTR_AWAIT` | `AWAIT` | src1=expr; dst=result | AwaitExpr |
| 28 | `MIR_INTR_NOP_MARKER` | `NOP_MARKER` | unknown OpType / debug | BinOp fallback |
| 29 | `MIR_INTR_TASK` | `TASK` | src1=expr | TaskExpr |
| 30 | `MIR_INTR_WAIT` | `WAIT` | src1=expr | WaitExpr |
| 31 | `MIR_INTR_SELECT` | `SELECT` | marker + body | SelectStmt |
| 32 | `MIR_INTR_SEND` | `SEND` | SetArg port,val | `send` |
| 33 | `MIR_INTR_RECV` | `RECV` | SetArg port | `recv` |
| 34 | `MIR_INTR_EMIT` | `EMIT` | src1=payload | EmitStmt |
| 35 | `MIR_INTR_ERX` | `ERX` | dst=error code | ErxExpr |
| 36 | `MIR_INTR_TRY` | `TRY` | marker + body | TryStmt |
| 37 | `MIR_INTR_RESUME` | `RESUME` | src1=name pool | ResumeStmt |
| 38 | `MIR_INTR_LOCK` | `LOCK` | SetArg target | `lock` |
| 39 | `MIR_INTR_SWIZZLE` | `SWIZZLE` | SetArg base,mask | SwizzleExpr |
| 40 | `MIR_INTR_INFER` | `INFER` | marker + body | InferBlock |
| 41 | `MIR_INTR_TRAIN` | `TRAIN` | marker + body | TrainBlock |
| 42 | `MIR_INTR_QUANTIZE` | `QUANTIZE` | src1=tensor | QuantizeExpr |
| 43 | `MIR_INTR_AWAIT_PASS` | `AWAIT_PASS` | — | `await pass` |
| 44 | `MIR_INTR_SAFE_ACCESS` | `SAFE_ACCESS` | SetArg base,field | `?.` |
| 45 | `MIR_INTR_ATOMIC` | `ATOMIC` | SetArg target | `!!` |
| 46 | `MIR_INTR_EXIST` | `EXIST` | src1=value | postfix `?` |
| 47 | `MIR_INTR_PATTERN` | `PATTERN` | SetArg lhs,rhs | `:~` / PatternExpr |
| 48 | `MIR_INTR_MAP` | `MAP` | SetArg args; src1=nargs | MapExpr |
| 49 | `MIR_INTR_ARR_COMPACT` | `ARR_COMPACT` | SetArg args | ArrCompactExpr |
| 50 | `MIR_INTR_BUNDLE` | `BUNDLE` | SetArg args | BundleExpr |
| 51 | `MIR_INTR_TIMEOUT` | `TIMEOUT` | src1=expr | TimeoutClause |
| 52 | `MIR_INTR_ISOLATE` | `ISOLATE` | + body | IsolateClause |
| 53 | `MIR_INTR_ERROR` | `ERROR` | dst | ErrorExpr |
| 54 | `MIR_INTR_PRECOMP` | `PRECOMP` | marker | PrecompBlock / FuncDef |
| 55 | `MIR_INTR_REACTIVE` | `REACTIVE` | name pool | ReactiveDecl |
| 56 | `MIR_INTR_MORPH` | `MORPH` | name pool | MorphDecl |
| 57 | `MIR_INTR_EXPOSE` | `EXPOSE` | + inner func | ExposeAttr |
| 58 | `MIR_INTR_PTR` | `PTR` | name pool | PtrTypeExpr |
| 59 | `MIR_INTR_ASYNC` | `ASYNC` | marker | FuncDef name2=async |
| 60 | `MIR_INTR_ATOMIC_VAR` | `ATOMIC_VAR` | + VarDecl | AtomicVarDecl |

**Const naming rule for MIR_ code:** always `MIR_INTR_<TAG>` matching column “Const name”. Never hardcode magic numbers without the const.

---

## 3. Emit / builder API — exact function names (`ast_to_mir.vri`)

| Function | Role |
|----------|------|
| `builder_new` | create `MirBuilder` + `MirFunc` + 64 var buckets |
| `builder_intern` | string → pool id |
| `builder_new_vreg` | allocate vreg |
| `builder_add_block` | new CFG block |
| `builder_add_instr` | push `MirInstr` to current block |
| `builder_edge_exists` | edge dedup query |
| `builder_add_edge` | successors/preds |
| `builder_push_loop` / `builder_pop_loop` / `builder_loop_top` | Break/Continue targets |
| `name_hash_bucket` | VarMap bucket 0..63 |
| `get_var_vreg` / `set_var_vreg` | hashed local map |
| `emit_jump` | `MirOp.Jump` |
| `emit_jump_if` | `MirOp.JumpIf` + `Jump` else |
| `emit_jump_if_not` | `MirOp.JumpIfNot` + `Jump` else |
| `emit_set_arg` | `MirOp.SetArg` |
| `emit_intrinsic` | `MirOp.Intrinsic` + kind |
| `emit_move` / `emit_load` / `emit_store` | Move / Load / Store |
| `lower_call_args` | SetArg loop for Call |
| `lower_aggregate` | SetArg elems + ARRAY/TUPLE/ENTITY |
| `lower_expr` / `lower_expr_impl` | expression lowering |
| `lower_stmt` / `lower_stmt_impl` | statement lowering |
| `lower_decl_marker` | `MIR_INTR_DECL` for top-level decls |
| `ast_lower_func` | one FuncDef/ExternFunc → `MirFunc` |
| `ast_lower_program` | program → `Vec<MirFunc>` (+ optional `__mir_decls`) |

### Downstream (do not rename)

| Phase | File | Key funcs |
|-------|------|-----------|
| CFG/dom | `mir_cfg.vri` | `mir_build_cfg`, `mir_compute_dominators` |
| SSA | `mir_ssa.vri` | `mir_insert_phi_nodes`, `mir_rename_variables` |
| Opt | `mir_opt.vri` | `mir_optimize_all` |
| MIR→LIR | `lir_lower.vri` | `lower_mir_instr`, `lir_lower_func`, `lir_lower_program` |
| Pipeline | `pipeline.vri` | `compile_pipeline` |

### LIR side (aux / ops) — avoid clash

| LIR | Meaning |
|-----|---------|
| `LirOp.Rem` | from `MirOp.Mod` |
| `LirOp.And`…`Not` / `Pow`/`MatMul`/`Fma` | 1:1 from matching `MirOp` |
| `LirOp.SetArg` | from `MirOp.SetArg` |
| `LirOp.Intrinsic` | from `MirOp.Intrinsic`; `LirInstr.aux` = `MIR_INTR_*` kind |
| `LirOp.Cmp` | from Cmp*; `aux` = `LIR_CMP_EQ`..`LIR_CMP_LE` |
| `LirOp.JmpCond` | JumpIf / JumpIfNot; `aux` = `LIR_JMP_IF` / `LIR_JMP_IFNOT` |
| Soft Intrinsic classes | marker→NOP; payload→MOV; else `BL` → `LIR_RT` stub[kind] (patched) |
| Soft Call | name via `LirFunc.strings[aux]` → func offs; else stub0; SetArg→X0..X7 |
| Soft ML | `BL` → stub 61/62/63 (`LIR_RT_POW`/`MATMUL`/`FMA`) |
| Module entry | `emit_lir_module_arm64` (wired from `virc` for ARM64) |

---

## 4. Synthetic / special names

| Name | Meaning |
|------|---------|
| `__mir_decls` | `MirFunc.name` for decl-marker init func from `ast_lower_program` |
| `MIR_VAR_BUCKETS` | `64` — VarMap hash buckets |

---

## 5. Checklist for MIR_ authors

1. Import `MirOp.X` / `MIR_INTR_Y` — never raw ints in new code.  
2. For Intrinsics, read **`src2.imm`** as kind; resolve strings via **`MirFunc.strings`**.  
3. For Call, **`src1.imm` = nargs**, **`src2.imm` = callee pool id**.  
4. CFG edges: use `successors` / `preds` on `MirBlock` (already filled by `builder_add_edge`).  
5. Jump targets are **imm block ids**, not `MirOperandType.Block` (ast_to_mir uses imm).  
6. Use `mir_op_tag` / `mir_intr_tag` in dumps/tests so names stay aligned.  
