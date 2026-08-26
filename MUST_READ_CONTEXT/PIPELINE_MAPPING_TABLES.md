# Pipeline Mapping Tables

**Official architecture (Spec §1.2 / ARCHITECTURE §0):**  
`AST` → **HIR** → **MIR** → **LIR** → Optimizer → Codegen  

**Soft implementation (today):**  
`AST` → `ast_to_mir` → MIR → (`mir_ssa` / `mir_opt`) → `lir_lower` → **LIR clean** → (`lir_liveness` / `lir_regalloc_color` / **George–Appel coalesce**) → `lir_codegen` → ARM64  

HIR module exists (`hir.vri`); soft `virc` may still skip an explicit AST→HIR pass until wired — that is an implementation gap, not a second architecture.  
**Not official:** flat Q-IR; QIR-H/M/L (see `docs/archive/QIR_ARCHITECTURE.md`).

**Live Stage-0/1 path (today):** flat MIR in `virc_boot.vri` → Mach-O (không đi hết soft LIR codegen).  

**Register allocation policy:** LIR sạch trước → color/assign (Linear Scan *hoặc* Chaitin–Briggs) → George–Appel chỉ coalescing còn lại — xem [`REGISTER_ALLOCATION_ARCHITECTURE.md`](REGISTER_ALLOCATION_ARCHITECTURE.md).

**Exact MirOp / MIR_INTR_* / emit fn names:** [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md) — MIR_ phases must use those tags only.  
**Coverage + Ownership (who emits/mutates/consumes):** same file § Coverage / § Ownership.  
**AST→MIR status:** [`AST_TO_MIR_LOWERING_CHECKLIST.md`](AST_TO_MIR_LOWERING_CHECKLIST.md)  
**Spec §29–§30 surface gap (P0 ISA / P1 silent-wrong / P2 runtime):** [`SPEC_IR_SURFACE_ROADMAP.md`](SPEC_IR_SURFACE_ROADMAP.md)

**Status:** `OK` | `PARTIAL` | `TODO` | `—` (không áp dụng) | `LIVE` (chỉ boot flat emit)

Updated: 2026-07-31 (official IR = HIR→MIR→LIR; soft may still AST→MIR)

---

## 1. AST ↔ Lower Function

| AstType | # | Lower entry | Helper(s) | Notes |
|---------|---|-------------|-----------|-------|
| Program | 0 | `ast_lower_program` | — | chỉ walk `FuncDef` |
| FuncDef | 2 | `ast_lower_func` | `builder_new`, param bind | body = child cuối |
| Block | 1 | `lower_stmt_impl` | `lower_stmt` loop | |
| VarDecl | 3 | `lower_stmt_impl` | `lower_expr`, `set_var_vreg` | |
| ConstDecl | 4 | `lower_stmt_impl` | same | |
| Assign | 5 | `lower_stmt_impl` | new vreg + Move | SSA-ready map |
| IndexAssign | 6 | — | — | **TODO** |
| FieldAssign | 7 | — | — | **TODO** |
| IfStmt | 8 | `lower_stmt_impl` | `emit_jump_if`, `emit_jump` | |
| LoopStmt | 9 | `lower_stmt_impl` | counted 0..N + loop_stack | |
| WhileStmt | 10 | `lower_stmt_impl` | cond/body/end + loop_stack | |
| ForRange | 11 | `lower_stmt_impl` | induction + loop_stack | |
| ReturnStmt | 12 | `lower_stmt_impl` | — | |
| PrintStmt | 13 | `lower_stmt_impl` | `emit_intrinsic` | |
| BreakStmt | 14 | `lower_stmt_impl` | `builder_loop_top` | |
| ContinueStmt | 15 | `lower_stmt_impl` | `builder_loop_top` | |
| EnumDef..IncludeStmt | 16–21 | — | — | decl-only / **TODO** |
| LiteralInt | 30 | `lower_expr_impl` | — | |
| LiteralFloat | 31 | `lower_expr_impl` | — | bits qua int_val |
| LiteralStr | 32 | `lower_expr_impl` | `emit_intrinsic` | |
| Identifier | 33 | `lower_expr_impl` | `get_var_vreg` | |
| BinOp | 34 | `lower_expr_impl` | — | |
| Compare | 35 | `lower_expr_impl` | — | |
| Call | 36 | `lower_expr_impl` | `lower_call_args`, `emit_set_arg` | (+ expr-stmt path) |
| BuiltinCall | 37 | `lower_expr_impl` | same + BUILTIN intrinsic | |
| InputExpr | 38 | — | — | **TODO** |
| ArrayLiteral | 39 | `lower_expr_impl` | `emit_intrinsic` | |
| IndexAccess | 40 | `lower_expr_impl` | SetArg + INDEX | |
| FieldAccess | 41 | `lower_expr_impl` | FIELD intrinsic | |
| EnumAccess | 42 | — | — | **TODO** |
| EntityLiteral | 43 | `lower_expr_impl` | ENTITY intrinsic | |
| CheckCpu / PatchPoint | 50–51 | — | — | **TODO** |
| ExternFunc | 52 | — | — | **TODO** |
| WhenStmt | 53 | — | — | **TODO** |
| CastExpr | 54 | — | — | **TODO** |
| UnaryMinus | 55 | `lower_expr_impl` | Sub 0,x | |
| ExprIndex | 56 | `lower_expr_impl` | same IndexAccess | |
| TupleExpr | 57 | `lower_expr_impl` | TUPLE intrinsic | |
| ThrowStmt | 58 | — | — | **TODO** |
| EnsureBlock | 59 | `lower_stmt_impl` | lower body only | |
| RevertBlock | 60 | `lower_stmt_impl` | lower body only | |
| InterpExpr | 61 | `lower_expr_impl` | INTERP intrinsic | |
| MethodCall | 62 | `lower_expr_impl` | recv=SetArg0 | |
| PackedDef / RegisterDef / BindAttr | 63–65 | — | — | **TODO** |
| RefParam | 66 | `ast_lower_func` | param bind | không qua lower_expr |
| CaseExpr | 67 | `lower_stmt_impl` | CmpEq / wild / MATCH_PAT | |
| ArenaBlock | 68 | — | — | **TODO** |
| AwaitExpr | 69 | — | — | **TODO** |
| CancelStmt / QuietStmt | 70–71 | — | — | **TODO** |
| NamedArg | 72 | (via Call children) | `lower_expr` | **PARTIAL** |
| AddrOf | 73 | `lower_expr_impl` | ADDR_OF intrinsic | |

---

## 2. AST ↔ MIR Opcode

| AstType | Primary MirOp | Secondary / operands | Status |
|---------|---------------|----------------------|--------|
| LiteralInt | `Move` | dst=vreg, src1=imm | **OK** |
| LiteralFloat | `Move` | raw bits imm | **PARTIAL** |
| LiteralStr | `Intrinsic` | STR_LIT + pool id | **OK** |
| InterpExpr | `Intrinsic` | kind=`INTERP` | **PARTIAL** |
| Identifier | *(operand only)* | vreg từ var_map | **OK** |
| BinOp `+` | `Add` | | **OK** |
| BinOp `-` | `Sub` | | **OK** |
| BinOp `*` | `Mul` | | **OK** |
| BinOp `/` | `Div` | | **OK** |
| BinOp `%` | `Mod` | | **OK** |
| Compare `==` | `CmpEq` | | **OK** |
| Compare `!=` | `CmpNe` | | **OK** |
| Compare `>` | `CmpGt` | | **OK** |
| Compare `<` | `CmpLt` | | **OK** |
| Compare `>=` | `CmpGe` | | **OK** |
| Compare `<=` | `CmpLe` | | **OK** |
| Call | `SetArg`* + `Call` | nargs + callee pool id | **OK** |
| BuiltinCall | `Intrinsic(BUILTIN)` + `SetArg`* + `Call` | name pool id | **OK** |
| MethodCall | `SetArg`* + `Call` | recv @0; method pool id | **OK** |
| UnaryMinus | `Sub` | 0 − x | **OK** |
| AddrOf | `Intrinsic` | kind=`ADDR_OF` | **OK** |
| ArrayLiteral | `Intrinsic` | `ARRAY`, src1=len | **PARTIAL** |
| TupleExpr | `Intrinsic` | `TUPLE` | **PARTIAL** |
| EntityLiteral | `Intrinsic` | `ENTITY` | **PARTIAL** |
| IndexAccess / ExprIndex | `SetArg` + `Intrinsic` | `INDEX` | **PARTIAL** |
| FieldAccess | `SetArg` + `Intrinsic` | FIELD + field pool id | **OK** |
| VarDecl / ConstDecl / Assign | `Move` | + var_map | **OK** |
| IfStmt | `JumpIf`, `Jump` | then/else/end blocks | **OK** |
| WhileStmt | `Jump`, `JumpIf` | + loop_stack | **OK** |
| LoopStmt | `Move`, `CmpLt`, `Add`, `Jump*` | counted | **OK** |
| ForRange | `Move`, `CmpLt`, `Add`, `Jump*` | induction var | **OK** |
| ReturnStmt | `Return` | | **OK** |
| PrintStmt | `Intrinsic` | `PRINT` | **PARTIAL** |
| Break / Continue | `Jump` | loop targets | **OK** |
| CaseExpr (int/bool/wild) | `CmpEq`, `JumpIf`, `Jump` | | **OK** |
| CaseExpr (str/tagged) | `Intrinsic` | pool id + `MATCH_PAT` + JumpIf | **PARTIAL** (runtime) |
| Ensure / Revert | *(body ops)* | | **PARTIAL** |
| IndexAssign / FieldAssign / When / … | — | | **TODO** |

### Intrinsic kind quick ref

| Kind | # | AST |
|------|---|-----|
| STR_LIT | 1 | LiteralStr |
| PRINT | 2 | PrintStmt |
| ARRAY | 3 | ArrayLiteral |
| TUPLE | 4 | TupleExpr |
| ENTITY | 5 | EntityLiteral |
| ADDR_OF | 6 | AddrOf |
| INTERP | 7 | InterpExpr |
| BUILTIN | 8 | BuiltinCall |
| INDEX | 9 | IndexAccess |
| FIELD | 10 | FieldAccess |
| MATCH_PAT | 11 | CaseExpr non-int |

---

## 3. MIR Opcode ↔ LIR

Source: `lir_lower.vri` → `lower_mir_op`

| MirOp | # | LirOp | # | Status |
|-------|---|-------|---|--------|
| Nop | 0 | Nop | 0 | **OK** |
| Move | 1 | Mov | 1 | **OK** |
| Load | 2 | Load | 13 | **OK** map; AST chưa emit Load |
| Store | 3 | Store | 14 | **OK** map; AST chưa emit Store |
| Add | 4 | Add | 2 | **OK** |
| Sub | 5 | Sub | 3 | **OK** |
| Mul | 6 | Mul | 4 | **OK** |
| Div | 7 | Div | 5 | **OK** |
| Call | 8 | Call | 8 | **OK** map — `aux`=callee str_id; src1=nargs |
| Intrinsic | 9 | Intrinsic | 17 | **OK** — `aux`=kind |
| Jump | 10 | Jmp | 9 | **OK** — target → Label |
| JumpIf | 11 | JmpCond | 10 | **OK** — `aux`=LIR_JMP_IF |
| JumpIfNot | 21 | JmpCond | 10 | **OK** map — `aux`=LIR_JMP_IFNOT |
| Return | 12 | Ret | 12 | **OK** |
| CmpEq..CmpLe | 13–18 | Cmp | 11 | **OK** — `aux`=predicate |
| Mod | 19 | Rem | 15 | **OK** |
| SetArg | 20 | SetArg | 16 | **OK** — `aux`=index |
| And…Not | 22–27 | And…Not | 18–23 | **OK** |
| Pow / MatMul / Fma | 28–30 | Pow / MatMul / Fma | 24–26 | **OK** |
| *(unmapped)* | — | Pop | 7 | LIR có, MIR không emit |

**Phi:** không thành LirOp — `lir_lower` chèn `Mov` vào predecessor (SSA destroy).

---

## 4. LIR ↔ Machine Instruction (ARM64)

Soft emitter: `lir_codegen.vri` → helpers trong `codegen.vri`.  
Live emitter: `virc_boot.vri` `boot_cg_*` (bd/MIR flat) — ghi cột LIVE.

| LirOp | # | Soft `lir_codegen` ARM64 | Status | Live boot (tham chiếu) |
|-------|---|--------------------------|--------|------------------------|
| Nop | 0 | `arm64_nop` | **OK** | `NOP` |
| Mov | 1 | `arm64_mov_rr` / `arm64_movz_imm64` | **OK** | MOVZ/MOVK / ORR |
| Add | 2 | `arm64_add_rrr` | **OK** | ADD |
| Sub | 3 | `arm64_sub_rrr` | **OK** | SUB |
| Mul | 4 | `arm64_mul_rrr` | **OK** | MUL |
| Div | 5 | `arm64_sdiv_rrr` | **OK** | SDIV |
| Rem | 15 | `SDIV`+`MSUB` | **OK** | SDIV+MSUB |
| Push | 6 | `arm64_str_pre` SP | **OK** | STR |
| SetArg | 16 | `MOV X0..X7` (ai<8); else stack push | **OK** | MOV Xi |
| Pop | 7 | `arm64_ldr_post` SP | **OK** | LDR |
| Call | 8 | `BL` patched → func offs / RT#0; then `MOV rd,X0` | **OK** | `BL` / fixup |
| Intrinsic | 17 | marker/payload inline; else `BL`→RT[kind] | **OK** | `BL` / fixup |
| And…Not | 18–23 | bitwise (+ Imm) | **OK** | bitwise |
| Pow / MatMul / Fma | 24–26 | `BL`→RT 61/62/63 | **OK** | — |
| Jmp | 9 | `B` + fixup | **OK** | `B` |
| JmpCond | 10 | `SUBS #0` + `B.EQ`/`B.NE` + fixup | **OK** | `B.EQ` / `B.NE` |
| Cmp | 11 | `CMP` + `CSET` (+ Imm) | **OK** | `CMP` + `CSET` |
| Ret | 12 | src1→X0 + epilogue `LDP`+`RET` | **OK** | `RET` |
| Load | 13 | `LDR` [Xn] | **OK** | `LDR` |
| Store | 14 | `STR` [Xn] | **OK** | `STR` |

### Soft codegen helpers available but chưa wire từ LIR

| Helper (`codegen.vri`) | Dùng cho LirOp (kỳ vọng) |
|------------------------|---------------------------|
| `arm64_cmp_rr` / `arm64_cset_*` | Cmp |
| `arm64_b_imm26` / `arm64_beq_imm19` / `arm64_bne_imm19` | Jmp / JmpCond |
| `arm64_bl_imm26` / `arm64_blr_x16` | Call |
| `arm64_ldr_*` / `arm64_str_*` | Load / Store / Push / Pop |
| `arm64_add_imm` / `arm64_sub_imm` | Mov imm / stack |

---

## 5. Coverage Matrix

Hàng = AstType (nhóm). Cột = stage.

| AstType / nhóm | Lower fn | → MIR | → LIR | → ARM64 soft | → Live boot |
|----------------|----------|-------|-------|--------------|-------------|
| Program / FuncDef | **OK** | **OK** | **OK** | **PARTIAL** | **OK** (cap/keep) |
| Block | **OK** | **OK** | **OK** | **PARTIAL** | **OK** |
| VarDecl / Const / Assign | **OK** | **OK** | Mov | Mov | **OK** |
| IndexAssign / FieldAssign | **TODO** | — | — | — | **PARTIAL**/LIVE |
| IfStmt | **OK** | JumpIf/Jump | JmpCond/Jmp | **OK** | **OK** |
| WhileStmt | **OK** | Jump* | Jmp* | **OK** | **OK** |
| LoopStmt | **OK** | counted | Jmp*/Cmp | **TODO** | **PARTIAL** |
| ForRange | **OK** | induction | Jmp*/Cmp | **TODO** | **TODO**/LIVE |
| ReturnStmt | **OK** | Return | Ret | **PARTIAL** | **OK** |
| PrintStmt | **OK** | Intrinsic | Call | **TODO** | **OK** |
| Break / Continue | **OK** | Jump | Jmp | **TODO** | **PARTIAL** |
| CaseExpr int/wild | **OK** | Cmp+Jump | Cmp/Jmp | **OK** | **PARTIAL** |
| CaseExpr str/tag | **PARTIAL** | MATCH_PAT+pool | Intrinsic | **PARTIAL** BL#0 | **TODO** |
| LiteralInt | **OK** | Move | Mov | **OK** | **OK** |
| LiteralFloat | **PARTIAL** | Move | Mov | **PARTIAL** | **PARTIAL** |
| LiteralStr / Interp | **PARTIAL** | Intrinsic | Call | **TODO** | **OK** PrintStr |
| Identifier | **OK** | vreg | — | — | **OK** |
| BinOp arith | **OK** | Add..Mod | Add..Rem | **OK** | **OK** |
| Compare | **OK** | Cmp* | Cmp+aux | **OK** | **OK**/LIVE |
| Call / Method / Builtin | **OK** | SetArg+Call | SetArg+Call | **PARTIAL** BL#0 | **OK** Call |
| UnaryMinus | **OK** | Sub | Sub | **OK** | **OK** |
| AddrOf | **OK** | Intrinsic | Call | **TODO** | **TODO** |
| Array / Tuple / Entity lit | **PARTIAL** | Intrinsic | Call | **TODO** | **PARTIAL** |
| Index / Field access | **PARTIAL** | Intrinsic | Call | **TODO** | **PARTIAL** |
| Ensure / Revert | **PARTIAL** | body | body | — | **TODO** |
| When / Throw / Await / Arena / Cancel / Quiet | **TODO** | — | — | — | **TODO** |
| Enum/Entity/Module decls | **TODO** | — | — | — | parse-only |
| Cast / EnumAccess / Input / NamedArg | **TODO**/PARTIAL | — | — | — | **PARTIAL** |

### Pipeline bottleneck (đọc nhanh)

```text
AST→MIR          ██████████  full executable AstType coverage
MIR fidelity     █████████░  pool/SetArg/Intrinsics; runtime materialize ở LIR/rt
MIR→LIR map      █████████░  Rem/SetArg/Intrinsic/Cmp/JmpCond aux OK
LIR→ARM64 soft   ████████░░  Cmp/Jmp/Rem/Load/Store OK; Call=BL#0
Live boot emit   ████████░░  suite 11/11 + Stage-1 smoke
```

---

## Related

- Chi tiết AST→MIR status từng hàm: [`AST_TO_MIR_LOWERING_CHECKLIST.md`](AST_TO_MIR_LOWERING_CHECKLIST.md)
- Soft orchestrator: `stdlib/vir/compiler/pipeline.vri`
- Live: `virc_boot.vri` (`boot_do_lower` → phase8 → `boot_codegen_*`)
