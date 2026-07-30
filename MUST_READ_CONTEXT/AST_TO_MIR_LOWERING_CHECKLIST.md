# AST → MIR Lowering Checklist

**File:** `stdlib/vir/compiler/ast_to_mir.vri`  
**IR defs:** `stdlib/vir/compiler/mir.vri`  
**Opcode registry (MIR_ must follow):** [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md)  
**Pipeline tables:** [`PIPELINE_MAPPING_TABLES.md`](PIPELINE_MAPPING_TABLES.md)  
**Updated:** 2026-07-25 — TODOs closed + registry

Status:
- **OK** — lowering complete for this phase
- **DEFER** — Phi → `mir_ssa`; Intrinsic machine body → LIR/rt

---

## Conventions (short)

See [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md) for **exact** `MirOp.*` / `MIR_INTR_*` names and emit function names.

| Mục | API |
|-----|-----|
| String pool | `builder_intern` → `MirFunc.strings` |
| Call | `emit_set_arg`* + `MirOp.Call` (nargs, callee id) |
| Intrinsic | `emit_intrinsic(kind, …)` — kind = `MIR_INTR_*` |
| Locals | `get_var_vreg` / `set_var_vreg` — **64-bucket hash** (`name_hash_bucket`) |
| Loops | `emit_jump_if_not` (`MirOp.JumpIfNot`) for While/When/For/Loop exit |
| Decls | `lower_decl_marker` → `MIR_INTR_DECL` in `__mir_decls` |

---

## MirOp / Intrinsic

All opcodes and `MIR_INTR_1..28` listed in registry. Tags via `mir_op_tag` / `mir_intr_tag`.

---

## Builder helpers

| Hàm | Status |
|-----|--------|
| `builder_new` / `builder_intern` | **OK** |
| `builder_new_vreg` / `add_block` / `add_instr` | **OK** |
| `builder_edge_exists` / `add_edge` | **OK** |
| `builder_push_loop` / `pop` / `loop_top` | **OK** |
| `name_hash_bucket` / `get_var_vreg` / `set_var_vreg` | **OK** (hashed) |
| `emit_jump` / `emit_jump_if` / `emit_jump_if_not` | **OK** |
| `emit_set_arg` / `emit_intrinsic` / `emit_move` / `emit_load` / `emit_store` | **OK** |
| `lower_call_args` / `lower_aggregate` / `lower_decl_marker` | **OK** |

---

## Coverage

Chi tiết pipeline: [`MIR_OPCODE_REGISTRY.md` § Coverage](MIR_OPCODE_REGISTRY.md).

| Group | Status |
|-------|--------|
| Exprs (lit, binop, call, agg, index/field, enum, input, cast, await, named, check_cpu, patch) | **OK** |
| Stmts (assign, index/field assign, if/while/when/loop/for, case, print, break/continue, throw/cancel/quiet, arena/ensure/revert) | **OK** |
| Top-level FuncDef / ExternFunc / decl markers (`MIR_INTR_DECL`) | **OK** |
| MirOp 0–21 + MIR_INTR 1–28 emit | **OK** |
| Soft LIR map | **OK** |
| Soft ARM64 Intrinsic/Call bodies | **PARTIAL** (ngoài phase này) |

---

## Ownership

Chi tiết: [`MIR_OPCODE_REGISTRY.md` § Ownership](MIR_OPCODE_REGISTRY.md).

| Artifact | Owner file | Role |
|----------|------------|------|
| `MirOp` / `MIR_INTR_*` names | `mir.vri` | schema (append-only) |
| Emit `MirInstr` from AST | `ast_to_mir.vri` | sole emit owner |
| Phi | `mir_ssa.vri` | sole Phi owner |
| Opt rewrites | `mir_opt.vri` | may Nop/Move; keep tags |
| MIR→LIR | `lir_lower.vri` | consume MirOp tags |
| Live flat MIR | `virc_boot.vri` | parallel path |

---

## DEFER (not AST→MIR)

| Mục | Phase |
|-----|--------|
| Phi | `mir_insert_phi_nodes` (`mir_ssa.vri`) |
| Intrinsic → machine | `lir_codegen` / runtime |
| Callee pool id → address | linker / soft BL |
| Live Stage-0/1 | `virc_boot.vri` |

---

## Changelog

1. CFG + Call SetArg + Case/For + loop_stack  
2. String pool + callee/field ids  
3. Full AstType coverage + Intrinsics 12–23  
4. **TODOs:** hashed VarMap; JumpIfNot in loops; DECL/CHECK_CPU/PATCH_POINT/AWAIT; [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md)  
