# VIR — Current Status Snapshot (2026-03-30, updated 2026-04-11)

## 1) Self-Hosting Pipeline Status: ✅ PHASE 6 — 47/47 TESTS PASS — OPTIMIZATION PASSES COMPLETE

virc.vri (Vir self-hosting compiler) now successfully compiles **47 test programs** covering all major language features: integers, strings, arrays, entities, enums, globals, eif chains, combined patterns, stack spilling (20+ variables), and higher-order functions (function pointers + indirect calls).

**NEW (2026-04-11):** Phase 6 — Optimization passes complete. QOp opcode reconciliation done (82 canonical opcodes across all backends).
- **Optimization passes** (Phase 6): 3-pass optimization pipeline in `ir_optimizer.vri`:
  - `auto_kernel_fusion_pass` — Greedy chain fusion: Mul→Add → FusedMulAdd (ARM64 MADD/MSUB)
  - `bce_pass` — Bounds Check Elimination: ArrLen+CmpLt → safe ArrGet/ArrSet (patch_id=3022)
  - `autovec_pass` — Auto-vectorization: elementwise loops → VAdd/VSub/VMul/VDiv
- **QOp opcode reconciliation** (Phase 6): 82 canonical opcodes unified across ir_optimizer.vri, codegen.vri, codegen_wasm.vri, main.vri. 13 missing ARM64 handlers added (SIMD, Fused, Float). codegen.vri legacy enum replaced with canonical numbering + Store=200 alias.
- **Python removal** (Phase 5): All Python source (`src/`, `tests/`) removed. pyproject.toml cleaned. README rewritten for self-hosting workflow.
- **Stack spilling** (Phase 4.6): vreg >= 16 spills to stack via LDR/STR. X8 = primary spill register, X16 = secondary. Dynamic frame sizing: `frame_size = 160 + spill_extra`.
- **Function pointers** (Phase 4.6): `QOp::LoadFuncAddr` emits ADR instruction, back-patched to function code address. Indirect calls via `MOV X16, src; BLR X16`.
- **String runtime** (Phase 4.5): `_rt_strlen`, `_rt_strcat` stubs, StrCat/StrLenOp codegen, PrintStr for variable strings.
- **Global/string slot collision fix** (Phase 4.5): scan Q-IR for max LoadGlobal/StoreGlobal index to compute `str_globals_base`.

**Previous milestones:**
- Phase 4.2 (2026-04-08): First working ARM64 Mach-O binary (`print 42` → 34KB binary → correct output)
- Phase 4.3 (2026-04-08): Register allocation fixes, 8 tests passing
- Phase 4.4 (2026-04-09): Critical C VM workaround bugs fixed, 9 tests passing
- Phase 4.5 (2026-04-10): String runtime + global collision fix, 46 tests passing
- Phase 4.6 (2026-04-10): Stack spilling + function pointers, 47/47 tests passing
- Phase 5 (2026-04-10): Python removal, build hardening, heap-buffer-overflow fix
- Phase 6 (2026-04-11): Optimization passes (fusion, BCE, autovec) + QOp opcode reconciliation

### Pipeline
```
source.vri → lexer.vri → parser.vri → ir_optimizer.vri → [optimize_module] → codegen.vri → main.vri → Mach-O ARM64 binary
```

### Command
```bash
cd Vir && ./core/build/vir run stdlib/vir/compiler/virc.vri -- <test>.vri && ./a.out
```
(Auto-codesigning on macOS ARM64 — Fix 12)

---

## 2) Test Matrix — 47 Verified Passing ✅

| # | Test | Code | Expected Output | Status |
|---|------|------|----------------|--------|
| 1 | test_hello.vri | `print_str("hello world\n")` | hello world | ✅ |
| 2 | test_arithmetic.vri | 5 ops: +, *, -, /, % | 30, 90, 75, 15, 5 | ✅ |
| 3 | test_if_simple.vri | `if 1 > 0: print 42 end` | 42 | ✅ |
| 4 | test_if_false.vri | `if 0 > 1: print 99 end; print 0` | 0 | ✅ |
| 5 | test_if_else.vri | `var x=10; if x>5: print 1 else print 0 end` | 1 | ✅ |
| 6 | test_reassign.vri | `var x=5; x=x+1; print x` | 6 | ✅ |
| 7 | test_while.vri | `var i=0; when i<5 loop; print i; i=i+1; end` | 0,1,2,3,4 | ✅ |
| 8 | test_nested_if.vri | nested if/else (x=10, x>5 && x>8) | 2 | ✅ |
| 9 | test_for_range.vri | `for i in 0..5: print i end` | 0,1,2,3,4 | ✅ |
| 10 | test_break.vri | while + break at i==5 | 0,1,2,3,4,99 | ✅ |
| 11 | test_skip.vri | while + skip (continue) even numbers | 1,3,5,7,9 | ✅ |
| 12 | test_loop_n.vri | `loop 5: print 7 end` | 7,7,7,7,7 | ✅ |
| 13 | test_eif.vri | if/eif/else chain (x=15) | 2 | ✅ |
| 14 | test_for_accum.vri | for-range with accumulator | 103, 15 | ✅ |
| 15 | test_func_call.vri | `add(3, 7)` → 10 | 10 | ✅ |
| 16 | test_multi_func.vri | `add_squares(3,4)` = 3²+4² | 25 | ✅ |
| 17 | test_nested_while.vri | 3×3 nested while grid | 0,1,2,10,11,12,20,21,22 | ✅ |
| 18 | test_recursion.vri | `factorial(5)`, `factorial(10)` | 120, 3628800 | ✅ |
| 19 | test_fib.vri | `fib(0,1,5,10)` | 0, 1, 5, 55 | ✅ |
| 20 | test_mutual_recursion.vri | `is_even/is_odd` mutual recursion | 1, 1, 0, 0 | ✅ |
| 21 | test_str_var.vri | `var s="hello"; print_str(s)` | hello | ✅ |
| 22 | test_str_concat.vri | `str_cat("hello ", "world")` | hello world | ✅ |
| 23 | test_str_multi.vri | chained str_cat + str_len | Vir kills C!, 12, 4 | ✅ |
| 24 | test_str_func.vri | string concat across function calls | Hello, Vir!, 11 | ✅ |
| 25 | test_str_loop.vri | str_cat in while loop (Arena stress) | xxxxxx, 6 | ✅ |
| 26 | test_control.vri | simple if/else (x=10, x>5) | 1 | ✅ |
| 27 | test_array_basic.vri | arr_new, push, arr[i], len | 10, 20, 30, 3 | ✅ |
| 28 | test_array_set.vri | arr[1]=999 | 100, 999, 300 | ✅ |
| 29 | test_array_loop.vri | arrays in loops + functions | 10, 0, 9, 81, 285 | ✅ |
| 30 | test_array_literal.vri | `[10,20,30,40,50]` | 10, 30, 50, 5 | ✅ |
| 31 | test_entity_full.vri | entity create + field access + field assign | 10, 20, 99, 20 | ✅ |
| 32 | test_entity_advanced.vri | 2 entities, functions, computed assign | 3, 7, 10, 5, 50, 10 | ✅ |
| 33 | test_entity_rect.vri | 3-field entity | 10, 5, 0 | ✅ |
| 34 | test_entity_multi.vri | two entity types | 3, 7, 10, 5 | ✅ |
| 35 | test_enum_paren.vri | enum + parenthesized expr | 14, 3 | ✅ |
| 36 | test_arr_after_var.vri | array ops after variable decls | 2, 42, 99 | ✅ |
| 37 | test_dot_simple.vri | dot product with literal args | 110 | ✅ |
| 38 | test_dot_entity.vri | dot product with entity field args | 110 | ✅ |
| 39 | test_dot_entity2.vri | dot with pre-captured entity fields | 110 | ✅ |
| 40 | test_entity_enum_array.vri | entity+enum+array+functions combined | 3,4,10,20,13,110,255,128,0,64,2,3,3,110 | ✅ |
| 41 | test_global.vri | module-level globals + mutation across functions | 100, 42, 110, 200, 242 | ✅ |
| 42 | test_global2.vri | multiple globals + computed updates | 30, 45, 59, 2 | ✅ |
| 43 | test_eif_func.vri | eif chains inside non-main functions | 100, 25, 30 | ✅ |
| 44 | test_if_dot.vri | entity fields + eif chains in function | 110, 220, 30 | ✅ |
| 45 | test_virc_all.vri | entity+eif+globals+arrays+strings all combined | 15,25,12,32,100,200,2,hello,5 | ✅ |
| 46 | test_spill.vri | 20 local variables + chained additions (stack spilling) | 210 | ✅ |
| 47 | test_hof.vri | function pointers: `var f = double`, `f(5)`, `apply(double, 7)` | 10, 14 | ✅ |

### Feature Support Matrix

| Tính năng | Hỗ trợ | Ghi chú |
|-----------|--------|---------|
| `print <int>` | ✅ | syscall write |
| `print_str("...")` | ✅ | String literal in .data section |
| `var x = <int>` | ✅ | VarDecl with literal |
| `var x = a + b` | ✅ | BinOp in VarDecl |
| `x = x + n` (reassign) | ✅ | Inlined BinOp in Assign |
| `x = <int>` (reassign) | ✅ | LiteralInt fast path |
| `+`, `-`, `*`, `/`, `%` | ✅ | All 5 arithmetic ops |
| `>`, `<`, `>=`, `<=`, `==`, `!=` | ✅ | Compare → CMP + CSET |
| `if cond: ... end` | ✅ | Backpatch system |
| `if cond: ... else ... end` | ✅ | Backpatch with else branch |
| `when cond loop ... end` | ✅ | While loop with back-edge |
| Nested if/else | ✅ | Tested: nested + eif chains |
| For-range loops | ✅ | `for i in 0..N` with accumulator |
| Break/Continue | ✅ | `break` and `skip` (continue) |
| Loop N | ✅ | `loop 5: ... end` counter-based |
| Multi-function calls | ✅ | Functions calling functions |
| Recursion | ✅ | factorial, fibonacci, mutual recursion |
| String variables | ✅ | `var s = "hello"` — Arena-allocated header {len, data} |
| String concatenation | ✅ | `str_cat(s1, s2)` — Arena v2 bump-alloc, zero malloc |
| String length | ✅ | `str_len(s)` — reads len from header |
| `print_str(var)` | ✅ | Print string from variable (not just literal) |
| Array literal `[1,2,3]` | ✅ | Arena-allocated via ArrNew + ArrPush |
| Array indexing `arr[i]` | ✅ | ArrGet opcode |
| Array assign `arr[i] = v` | ✅ | ArrSet opcode |
| Array push/len | ✅ | `push(arr, val)`, `len(arr)` builtins |
| `arr_new(cap)` | ✅ | ArrNew with optional capacity (default 8) |
| Entity create | ✅ | `Vec2{x: 3, y: 4}` — Arena-allocated, fields via StoreWord |
| Entity field access | ✅ | `p.x` → LoadWord with element index |
| Entity field assign | ✅ | `p.x = 99` → StoreWord with element index |
| Entity in functions | ✅ | Entity field values as function args (with arg compaction) |
| Enum definition | ✅ | `enum Dir: North=0 East=1 end` |
| Enum dot access | ✅ | `Dir.South` → integer value |
| Parenthesized exprs | ✅ | `(a + b) * c` |
| Module-level globals | ✅ | top-level `var`/`const` lowered to `LoadGlobal`/`StoreGlobal` via `__vir_init__` |
| Stack spilling (20+ vars) | ✅ | vreg >= 16 spills to stack; X8 primary, X16 secondary spill register |
| Function pointers | ✅ | `var f = func_name` → LoadFuncAddr (ADR); `f(args)` → BLR X16 indirect call |
| Higher-order functions | ✅ | Pass functions as arguments, call through variables |

---

## 3) Bugs Fixed — Full History

### Phase A (Fixes 1-9): C VM Parser/Lowerer Compatibility
| Fix # | Description |
|-------|-------------|
| 1 | `IDENT::IDENT` enum access in C parser |
| 2 | Complex type annotations `Vec<T>` |
| 3 | Record literal field init syntax |
| 4 | `or;`/`and;` line continuation |
| 5a-5f | Keyword-as-identifier (6 sub-fixes) |
| 6 | `>>` shift vs cast disambiguation |
| 7 | CodeBuf array concat → bvec |
| 8a | `func` keyword variable clash |
| 8b | Long `eif` chain (40 branches) |
| 9 | `char_to_str()` missing → added as C VM built-in |

### Phase B (Fix 10): Runtime & Codegen Corrections
| Fix # | Description |
|-------|-------------|
| 10 | `print_ln` uses `print_str("\n")` in io.vri; field offset collision hardening (Token.line→tok_line, Lexer.line→lex_line, Token.int_val→tok_int_val); parser `else`/`when...loop` fixes; Assign handler `bin.op` write order |

### Phase B (Fixes 11-12): Parser & Build
| Fix # | Description |
|-------|-------------|
| 11 | Comma line continuation: `;`/newline skipping after commas in 3 call-arg sites in `core/src/parser.c` |
| 12 | Auto-codesigning: `core/src/main.c` runs `codesign -s - a.out` after VM execution on macOS ARM64 |

### Phase C (Fix 13): Control Flow / Backpatch System — MAJOR (5 sub-bugs)
| Sub-bug | Root Cause | Workaround |
|---------|------------|------------|
| 13a | Nested entity field access beyond position 1 returns 0 | Encode cond_vreg + label_id in single `patch_id` field: `(label+1)*1000 + vreg` |
| 13b | `entity.field = 0` treated as no-op by C VM | Offset all label IDs by +1 (never store 0 in patch_id) |
| 13c | `arr = arr + [value]` loses data (elements read back as 0) | Use `vec_new<int>()` + `vec_push<int>()` + `vec_get()` instead |
| 13d | `bvec_get(cb.data, offset)` returns 0 (can't read code buffer) | Construct final branch instructions directly (no read-modify-write) |
| 13e | Entity field assignment of nested fields corrupts parent fields | Only assign `patch_id` (int field); set all constructor args to `q_none()` |

### Phase C (Fix 14): Variable Reassignment in Loops
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 14 | `lower_expr` BinOp allocates fresh vregs → Assign needs Move → Move broken due to entity field bugs | Inline BinOp directly in Assign handler (writes to variable's vreg); also LiteralInt fast path for `x = 42` |

### Phase C (Fix 15): Cross-Function Call Convention
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 15a | `ins.src1.kind` wrong field name (QOperand has `op_type` not `kind`) → Call type detection fails | Separate `Call` vs `CallFunc` opcode handling; encode func_idx in `patch_id` |
| 15b | `ins.src1.func_idx` position 5 returns 0 (nested entity field bug) | Decode func_idx from `patch_id - 1` |
| 15c | `fixups = fixups + [...]` loses data (C VM array concat bug) | Use Vec: `global_fixup_offs_v`, `global_fixup_tgts_v` |
| 15d | Args passed via X19+ (callee-saved) overwrites params in recursive calls | New calling convention: args via X0-X7 (vreg 10+), function prologue moves X0→X19 etc. |

### Phase C (Fix 16): Register Pressure / Vreg Recycling
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 16 | Compare temps waste 2-3 vregs each; fib uses 11+ vregs → spills to caller-saved X0-X7 → clobbered by calls | Save/restore `next_vreg` around compare blocks in IfStmt and WhileStmt; recycle dead compare temps |

### Phase C.1 (Fix 17): String Operations — Arena v2
| Fix # | Feature | Implementation |
|-------|---------|---------------|
| 17a | String variables | `Load + StringRef` → embed string inline, bump-alloc header `{len, data}` in Arena, return ptr |
| 17b | String concatenation | `StrCat` opcode → `_rt_str_concat` runtime stub: bump-alloc in Arena, byte-copy both strings |
| 17c | String length | `StrLenOp` opcode → reads len from header `[ptr+0]` |
| 17d | `print_str(var)` | `PrintStrVar` opcode → `_rt_print_str_var` runtime stub: reads `{len, data}`, syscall write |
| 17e | Arena allocation | `_start` allocates 65536-byte Arena (64KB) via mmap; base at `[X15+0]`, offset at `[X15+8]`; zero malloc; bounds check with BRK#1 trap |

### Phase C.2 (Fix 18a): Array Operations
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 18a | Parser `expect()` returns 3-tuple → C VM crashes | Inline all `expect()` calls as `peek()` + `advance()` pattern (13 total eliminated) |

### Phase C.3 (Fixes 18b-18h): Entity/Enum Operations
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 18b | `parse_entity_def` didn't consume `:` after entity name | Add optional colon consumption |
| 18c | EntityLiteral alloc size: `vec_len(et.fields) >> int * 8` — operator precedence | Separate into `nfields = vec_len(et.fields) >> int; sz = nfields * 8` |
| 18d | FieldAccess/FieldAssign used `entity_field_offset` which returns byte offsets but LoadWord already applies LSL#3 | Inline entity field lookup, use element index (0,1,2) not byte offset (0,8,16) |
| 18e | FieldAccess used `expr.ast_name` after if-blocks (unreliable in C VM) | Use cached `expr_name` set at function entry |
| 18f | Register pressure: FieldAccess temps accumulate in Print/Assign/FieldAssign stmts | Save/restore `next_vreg` around statement handlers (PrintStmt, Assign, IndexAssign, FieldAssign, BuiltinCall) |
| 18g | Call arg clobbering: entity field temps push vregs into caller-saved range | Arg compaction: evaluate each arg → compact into sequential slots → reclaim temps between args |
| 18h | Call arg move clobbering: forward move order overwrites X0 before it's read as source | Reverse arg move order: move highest arg first (vreg13←slot[3]) before X0 is written |

### Phase C.4 (Fixes 19a-19n): Self-Compile Codegen/Linker — 14 Critical Bugs
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 19a | VIR `[]` + `+` array concat = integer addition (no Q_ARR_CONCAT) | Migrate layouts/fixups from `[]` arrays to `vec_new_rt()` + `vec_push_rt()` + `vec_get_rt()` |
| 19b | MSUB emitted twice (wrong first + cb.len -= 4 hack fails with bvec) | Remove wrong MSUB, emit only correct `0x9B008000 \| (rs2<<16) \| (rs1<<10) \| (17<<5) \| rd` |
| 19c | `arm64_mov_rr(cb, 29, 31)` encodes `ORR X29, XZR, XZR` = 0 (not MOV X29, SP) | New `arm64_mov_sp_to(cb, rd)` emits `ADD Xd, SP, #0` (`0x910003E0 \| rd`) |
| 19d | FuncLayout field name "offset" collides across entity types → wrong field index | Rename fields: `offset→code_off`, `size→fsize` (unique across all entities) |
| 19e | QOp enum values mismatch: codegen Print=27, ir_optimizer Print=40 | Align codegen QOp enum to match ir_optimizer values exactly |
| 19f | `ins.src1.label` / `ins.src1.func_idx` return 0 (QOperand is 3-field, not 6) | Use `.vreg` (field 1) which is where ir_optimizer stores label IDs and func indices |
| 19g | VIR `eif` chain >25 branches: later branches silently not executed | Extract Print/Exit/Halt handlers into independent `if` blocks before main chain |
| 19h | UDIV X24, X19, X3 — divides by X3 (caller's reg) instead of X23 (=10) | Fix encoding: `0x9AC30A78` → `0x9AD70A78` (Rm=23 not 3) |
| 19i | MSUB encoding: MADD (bit 15=0) + Ra=X3 instead of MSUB Ra=X19 | Fix encoding: `0x9B178F19` → `0x9B17CF19` (o0=1 for MSUB, Ra=19) |
| 19j | STRB W25, [X20, X1] — offset register X1 instead of X21 (position counter) | Fix all 5 STRB: `0x38216A99` → `0x38356A99` (Rm=21 not 1) |
| 19k | `SUB X24, X21, X0` (subtracts X0) + `CMP X24, X24` (always GE) | `SUB→MOV X24,X21`; `CMP` fix: `0xEB18031F` → `0xEB1802FF` (Rn=23 not 24) |
| 19l | `arm64_svc(cb)` missing imm argument → garbage SVC #0x4010 | Pass explicit: `arm64_svc(cb, 128)` → correct `SVC #0x80` |
| 19m | `MOV X0, X19` restore fails — X19=0 after digit loop zeroes it | Save original X0 in X27 (unused), restore from X27: `MOV X0, X27` |
| 19n | `_start` passes last-printed-value as exit code | Add `MOV X0, #0` before `BL _rt_exit` in `_start` |

### Phase 4.2 (Fixes 20a-20f): Full Mach-O Pipeline — 6 Critical Bugs
| Fix # | Root Cause | Solution |
|-------|------------|----------|
| 20a | `const NAME: VALUE;` — parser treated VALUE after `:` as type annotation, never set initializer | For AST_CONST_DECL, parse expression directly after `:` (not type annotation) |
| 20b | `codebuf_emit_byte`: `buf.data = buf.data + [byte]` — list `+` concat lowered as Q_ADD on VM array handles = garbage | Changed to `arr_push(buf.data, byte & 0xFF)` |
| 20c | `bvec_new`: `native_write_i64(base, 8, 0)` used byte offset 8 but VM uses word index | Changed to word index 1 |
| 20d | `codebuf_get_data` intrinsic: identity Q_MOVE returned entity handle not array data | Load field 0 (VM array) via Q_LOAD_WORD + Q_ARR_GET per index |
| 20e | Duplicate MachOBuilder entity: binary.vri and macho.vri both define it | Include reorder: macho.vri before binary.vri ("first compiled wins") |
| 20f | No intrinsic the write binary output to disk | Added Q_WRITE_FILE_BYTES (0xAD): fopen("wb")/fwrite/fclose/chmod(0755) |

---

## 4) Architecture Notes

### ARM64 Frame Layout (112 bytes)
```
[SP+0]   FP, LR (16 bytes)
[FP+16]  X14, X15 (16 bytes)
[FP+32]  X19-X28 (80 bytes, 10 callee-saved regs)
```

### Register Mapping
- vreg 0-9 → X19-X28 (callee-saved)
- vreg 10-17 → X0-X7 (caller-saved)
- vreg 18+ → X0 (overflow)
- X15 = Globals Base Pointer (mmap 4096 bytes in `_start`)

### Branch Encoding (Backpatch)
- B (Jump): `0x14000000 | imm26`
- B.EQ (JumpIfNot): `0x54000000 | (imm19 << 5)`
- B.NE (JumpIf): `0x54000001 | (imm19 << 5)`
- BL (Call): `0x94000000 | imm26`

### Label/Fixup Storage (Vec-based)
5 separate Vec objects replace arrays (C VM array bug workaround):
- `local_label_ids_v`, `local_label_offs_v` — label registry
- `local_fixup_offs_v`, `local_fixup_tgts_v`, `local_fixup_cond_v` — fixup registry

---

## 5) Files Modified

| File | LOC | Changes |
|------|-----|---------|
| `stdlib/vir/compiler/ir_optimizer.vri` | 2,281 | Q-IR lowering; QOp enum (82 canonical opcodes 0–135); optimization passes (fusion, BCE, autovec); all C VM workarounds; Assign handler inlines BinOp; patch_id encoding; EntityLiteral/FieldAccess/FieldAssign; vreg reclamation; arg compaction + reverse move in Call |
| `stdlib/vir/compiler/main.vri` | 1,953 | ARM64 codegen; Vec-based label storage; backpatch system; Mach-O emitter; print_int runtime; NEON SIMD dispatch (VLoad-VPerm); FusedBiasRelu/Gelu handlers; Float ops (FAdd-FCvtF2I); function pointer codegen; stack spilling |
| `stdlib/vir/compiler/codegen.vri` | 1,852 | ARM64+x86+NEON+AVX instruction emitters; QOp enum (82 canonical + Store=200 alias); codebuf_emit_byte → arr_push |
| `stdlib/vir/compiler/codegen_wasm.vri` | 869 | WASM backend; inherits canonical QOp from include chain |
| `stdlib/vir/compiler/parser.vri` | 1,623 | All 13 `expect()` 3-tuple calls inlined; entity/enum; FieldAccess/FieldAssign/EntityLiteral |
| `stdlib/vir/compiler/lexer.vri` | 955 | Tokenizer; field name collision fixes (tok_line, lex_line, tok_int_val) |
| `stdlib/vir/compiler/virc.vri` | 442 | Driver + CLI; include reorder; Step 4 calls optimize_module |
| `stdlib/vir/rt/*.vri` | 2,337 | Runtime modules (syscall, alloc, io, string_rt, vec_rt, macho, elf, start) |
| `core/src/parser.c` | 1,972 | Comma continuation; const decl parsing fix |
| `core/src/ir_lower.c` | 2,857 | codebuf_get_data intrinsic; Q_WRITE_FILE_BYTES; Q_REALLOC fix (2 sites) |
| `core/src/vm.c` | 1,069 | Q_WRITE_FILE_BYTES handler; Q_REALLOC handler |
| `core/src/main.c` | 532 | Auto-codesigning after VM execution |

### Totals

| Category | LOC |
|----------|-----|
| Self-hosting compiler (stdlib/vir/compiler/) | 9,975 |
| Runtime (stdlib/vir/rt/) | 2,337 |
| Compiler + Runtime | **15,121** |
| Full stdlib (stdlib/vir/**/*.vri) | **96,894** |
| C native core (core/src/*.c) | **22,757** |

---

## 6) Next Steps

### Immediate — Phase C Full Self-Hosting
- [x] Nested if/else, eif chains ✅
- [x] For-range loops ✅
- [x] Break/continue (skip) ✅
- [x] Loop N counter-based ✅
- [x] Multi-function calls ✅
- [x] Recursion (factorial, fibonacci, mutual) ✅

#### Phase C.1: String Operations (Arena v2) ✅ COMPLETE
- [x] String variables (`var s = "hello"`) — pointer+length in Arena header ✅
- [x] String concatenation (`str_cat(s1, s2)`) — Arena bump-alloc, zero malloc ✅
- [x] `print_str(variable)` — print string from Arena header ✅
- [x] `str_len(s)` — read len from header `[ptr+0]` ✅
- **Chiến lược:** Arena v2 bump allocator — cấp phát string mới ngay trong Arena hiện tại, nối chuỗi nhanh như chớp, không phân mảnh bộ nhớ. Không dùng malloc. ✅ ĐÃ TRIỂN KHAI

#### Phase C.2: Array/Vec ✅ COMPLETE
- [x] Array literal `[1, 2, 3]` — Arena-allocated via ArrNew + ArrPush ✅
- [x] Array indexing `arr[i]` — ArrGet opcode ✅
- [x] Array assign `arr[i] = v` — ArrSet opcode ✅
- [x] Vec push/len — `push(arr, val)`, `len(arr)` builtins ✅
- [x] `arr_new(cap)` — allocates with optional capacity (default 8) ✅

#### Phase C.3: Entity/Enum ✅ COMPLETE
- [x] Entity allocation and field access — Arena-allocated, LoadWord/StoreWord ✅
- [x] Entity field assignment — `p.x = 99` ✅
- [x] Entity fields as function arguments — arg compaction + reverse move ✅
- [x] Enum definition — `enum Dir: North=0 East=1 end` ✅
- [x] Enum dot access — `Dir.South` → integer value ✅
- [x] Multiple entity types in same program ✅
- [x] Complex entity+enum+array+function programs ✅
- [x] Globals / module-level variables ✅
- [ ] virc.vri compiles virc.vri (true bootstrap)

#### Phase C.4: Self-Compile Codegen/Linker ✅ ARITHMETIC VERIFIED
- [x] VIR array concat → vec_rt migration (layouts, fixups) ✅
- [x] MSUB double-emission fix ✅
- [x] Frame pointer encoding (ORR→ADD SP) with `arm64_mov_sp_to` ✅
- [x] FuncLayout field name collision (offset→code_off, size→fsize) ✅
- [x] QOp enum alignment (codegen ↔ ir_optimizer) ✅
- [x] QOperand field access (.label/.func_idx → .vreg) ✅
- [x] VIR eif depth limit workaround (extract handlers) ✅
- [x] print_int runtime: 10 encoding bugs fixed (UDIV, MSUB, STRB, CMP, SUB, SVC) ✅
- [x] Register clobbering: X0 preserved in X27 across print calls ✅
- [x] Exit code: `MOV X0, #0` in `_start` before `_rt_exit` ✅
- **Result:** `test_arithmetic.vri` → 380-byte ARM64 Mach-O → `30, 90, 75, 15, 5`, exit 0 ✅

#### Phase 4.2: Full Mach-O Pipeline ✅ WORKING BINARY (2026-04-08)
- [x] const decl parsing fix — all 409 module-level constants correctly initialized via `__vir_init__` ✅
- [x] codebuf_emit_byte — `arr_push` instead of broken list `+` concat ✅
- [x] bvec_new word index fix (8→1) ✅
- [x] codebuf_get_data intrinsic (Q_LOAD_WORD + Q_ARR_GET) ✅
- [x] Include reorder (macho.vri before binary.vri) for duplicate entity resolution ✅
- [x] write_file_bytes intrinsic (Q_WRITE_FILE_BYTES) ✅
- [x] Debug trace cleanup: ~40 traces removed from vm.c, ir_lower.c ✅
- **Result:** `print 42` → 34KB ARM64 Mach-O → `42`, exit 0 ✅
- **Binary:** Valid Mach-O structure (__PAGEZERO, __TEXT, __LINKEDIT, LC_MAIN, LC_LOAD_DYLIB, LC_CODE_SIGNATURE)
- **Known issue:** `print "string"` → outputs 1 (string literal codegen not yet implemented in virc.vri ARM64 backend)

### Long-term — Phase D Performance & Full Bootstrap
- [ ] virc.vri compiles virc.vri (true bootstrap — virc_boot.vri 10,800 LOC)
- [ ] **LTO (Link-Time Optimization):** Merge các file .vri thành một IR khổng lồ trước khi nhả ra Mach-O
- [ ] Peephole Optimizer v2
- [ ] PGO (Profile-Guided Optimization)
- [ ] Superoptimization templates
- [ ] x86_64 backend (active pipeline — currently only ARM64 in main.vri)
- [ ] ~~Port QIR-H/M/L 3-level pipeline from Python prototype to Vir~~ **Superseded** — official IR is HIR→MIR→LIR (`hir.vri`/`mir.vri`/`lir.vri`); QIR-H/M/L archived
- [ ] Full GELU approximation for FusedBiasGelu (currently bias-add only)

## 7) QOp Canonical Enum (82 opcodes, ir_optimizer.vri)

| Range | Category | Opcodes |
|-------|----------|---------|
| 0–12 | Arithmetic/Logic | Nop, Load, Move, Add, Sub, Mul, Div, Mod, And, Or, Xor, Shl, Shr |
| 20–25 | Comparison | CmpEq, CmpNe, CmpGt, CmpLt, CmpGe, CmpLe |
| 30–37 | Control Flow | Jump, JumpIfNot, Label, Call, CallFunc, Ret, JumpIf, Halt |
| 40–42 | I/O | Print, PrintStr, Input |
| 50–55 | Memory | Alloc, Free, LoadByte, StoreByte, LoadWord, StoreWord |
| 60–64 | Array | ArrNew, ArrPush, ArrGet, ArrSet, ArrLen |
| 70–75 | String | StrLenOp, StrGet, StrCat, StrEq, IToStr, StrToI |
| 80–84 | File I/O | FileOpen, FileRead, FileWrite, FileClose, FileWriteByte |
| 90–98 | System | Exit, PatchPoint, LoadGlobal, StoreGlobal, GetArg, ArgCount, SetArg, LoadFuncAddr, LoadString |
| 100–102 | Fused Ops | FusedMulAdd, FusedBiasRelu, FusedBiasGelu |
| 110–121 | SIMD Vector | VLoad, VStore, VAdd, VSub, VMul, VFma, VDiv, VMin, VMax, VReduce, VSplat, VPerm |
| 130–135 | Float Scalar | FAdd, FSub, FMul, FDiv, FCvtI2F, FCvtF2I |

**codegen.vri extra:** `Store = 200` (legacy alias for `emit_fast_x86`/`emit_fast_arm64`)
