# Chỉ thị triển khai: AST → HIR → MIR (giữ MIR→LIR→Codegen)

**Ngày:** 2026-07-31  
**Đối tượng:** AI / người thực hiện tiếp — **không** đổi kiến trúc; chỉ wire HIR đúng Spec  
**Kiến trúc chính thức:** `AST → HIR → MIR → LIR → Optimizer → Codegen`  
**SoT IR:** `stdlib/vir/compiler/hir.vri`, `mir.vri`, `lir.vri`  
**Không đụng:** thin Stage-0/1 fixed-point (`virc_boot.vri`) trừ khi regression rõ  
**Không revive:** QIR-H/M/L / flat Q-IR làm spine

Đọc trước (bắt buộc):
- [`SOFT_PATH_DEBUG_HANDOFF_2026_07_30.md`](SOFT_PATH_DEBUG_HANDOFF_2026_07_30.md) — fat string, typed accessor, `vec_push_rt` write-back, `mod`
- [`PIPELINE_MAPPING_TABLES.md`](PIPELINE_MAPPING_TABLES.md)
- [`MIR_OPCODE_REGISTRY.md`](MIR_OPCODE_REGISTRY.md) — **không** đổi tên `MirOp` / `MIR_INTR_*`
- Spec §1.2 (`docs/vir_language_spec_v2.0_*.md`)

---

## 0. Mục tiêu / ngoài phạm vi

### Làm
1. **Hoàn thiện `hir.vri`** đủ mang ngữ nghĩa sau parse (SoT HIR).
2. **`ast_to_hir.vri`:** AST → HIR (program / func / expr / stmt).
3. **`hir_to_mir.vri`:** HIR → MIR (emit `MirInstr` / `MirFunc` như `ast_to_mir` đang làm).
4. **`pipeline.vri`:** `ast_lower_program` → thay bằng `ast→hir→mir`; **giữ nguyên** CFG/SSA/opt/LIR/RA/codegen.

### Không làm
- Không rewrite `lir_lower` / `lir_codegen` / RA (trừ bug do MIR shape đổi ngoài ý muốn).
- Không “fix” soft bằng cách bypass HIR sau khi đã wire.
- Không port nguyên xi Python QIR-H/M/L.
- Không `git add -A`; chỉ commit file liên quan khi user yêu cầu.
- Không phá smoke đang xanh: `cg_arith`, `cg_mul`, `cg_var`, `cg_assign`, `cg_call`, `cg_multiparam` (và các test soft đã PASS).

---

## 1. Audit hiện trạng (2026-07-31)

### 1.1 Pipeline soft thật

```text
virc.vri
  → semantic…
  → compile_pipeline(ast)          # pipeline.vri
       → ast_lower_program(ast)    # ast_to_mir.vri  ← AST→MIR thẳng
       → mir_cfg / mir_ssa / mir_opt
       → lir_lower_program
       → liveness + lir_regalloc_color
  → emit_lir_module_arm64          # lir_codegen.vri
```

**Không có** `ast_to_hir` / `hir_to_mir`. `hir.vri` **không** được import.

### 1.2 `hir.vri` — skeleton, chưa đủ SoT

| Có | Thiếu / yếu |
|----|-------------|
| `HirKind` 13 giá trị (IntrinsicCall…VarDecl) | C `hir.h` còn `HIR_PRINT`, `HIR_FIELD_LOAD` — soft chưa có |
| `HirNode` flat + `args`/`body` vec | Không có `HirFunc` / `HirModule` / tên callee / string pool |
| `hir_new`, `hir_add_arg`, `hir_add_stmt` | Không typed accessor; node refs là `i64` pointer mơ hồ |
| Port từ `hir.h` | **Không cover** ~95 `AstType` (parser) — chỉ vài stmt/expr lõi |

**Kết luận:** Phải **mở rộng `hir.vri` trước** khi lowerer. Copy tối thiểu từ C **không đủ** cho soft bootstrap suite.

### 1.3 `ast_to_mir.vri` — logic phải bảo toàn

- ~1500+ dòng; `lower_expr_impl` / `lower_stmt_impl` / `ast_lower_func` / `ast_lower_program`.
- Đã cover gần hết `AstType` + `MIR_INTR_PARAM` (ABI) — **bắt buộc giữ** khi qua HIR.
- String: fat string + `fat_str_eq` / intern pool — **không** `rt_streq` trên fat header.
- Checklist cũ: [`AST_TO_MIR_LOWERING_CHECKLIST.md`](AST_TO_MIR_LOWERING_CHECKLIST.md) — sau khi tách, ownership emit MIR chuyển sang `hir_to_mir.vri`.

### 1.4 Tham chiếu C (chỉ đọc, không SoT)

- `core/include/hir.h` — union node nhỏ.
- `core/src/mir_lower.c` — `lower_hir_node_to_mir` cho subset (const/load/store/binop/call/if/loop/print…).  
Dùng để hiểu intent; **output MIR soft phải khớp `mir.vri` / registry**, không khớp C struct layout.

### 1.5 Rủi ro lớn

| # | Rủi ro | Mitigation |
|---|--------|------------|
| 1 | Big-bang rewrite `ast_to_mir` → soft đỏ hàng loạt | Phased; feature flag / dual path; smoke mỗi phase |
| 2 | HIR quá mỏng → mất BuiltinCall/PARAM/string | Mở rộng `HirKind` + fields trước P1 |
| 3 | Field access qua `vec_get_rt` sai layout | Typed accessors mọi tầng |
| 4 | Fat string / name hash | Copy pattern từ `ast_to_mir` (`name_hash_bucket`, `fat_str_eq`) |
| 5 | Đụng thin bootstrap | Không đổi `virc_boot` / Stage-1 path |

---

## 2. Thiết kế HIR mục tiêu (mở rộng `hir.vri`)

### 2.1 Nguyên tắc

- HIR = **AST đã bỏ sugar parse**, còn tên/biểu thức/control gần nguồn; **chưa** SSA/vreg.
- MIR vẫn là chỗ tạo vreg, block, `SetArg`, `MIR_INTR_*`.
- Một node flat (như hiện tại) OK nếu có đủ field; thêm entity bao hàm:

```text
HirModule  { funcs: [HirFunc], … }
HirFunc    { name: string, params: [HirParam], body: HirNode, … }
HirParam   { name: string, is_ref: i64, … }
HirNode    { kind, type_id, … children/fields }
```

### 2.2 `HirKind` — hướng mở rộng tối thiểu (bắt buộc cho smoke)

Giữ kinds cũ; **thêm** ít nhất:

| Kind | Thay cho AstType (ví dụ) |
|------|---------------------------|
| `Print` | PrintStmt |
| `Assign` | Assign (khác Store thuần?) — hoặc Store + Load |
| `FieldLoad` / `FieldStore` | FieldAccess / FieldAssign |
| `IndexLoad` / `IndexStore` | Index* |
| `Compare` | Compare (hoặc BinOp + op) |
| `Unary` | UnaryMinus / UnaryNot / AddrOf |
| `Literal` | Int/Float/Str (discriminant trong field) |
| `Identifier` / `NameRef` | Identifier |
| `Func` / module-level đã có qua `HirFunc` | FuncDef |
| `BuiltinCall` | BuiltinCall (giữ `intrinsic_id` + name) |
| `When` / `For` / `Case` | hoặc hạ xuống If/Loop ở AST→HIR (chấp nhận) |
| `Param` | metadata trên `HirFunc.params` — **không** cần node nếu bind ở hir_to_mir |

**Sugar có thể hạ sớm ở AST→HIR** (giảm kinds):
- `WhenStmt` → chuỗi If
- `ForRange` / `LoopStmt` → Loop + counter
- `CaseExpr` → if-chain  
Document rõ trong comment kind nào còn / nào desugar.

**Không** nhồi mọi AstType 87–108 thành kind riêng nếu có thể → `IntrinsicCall` + `intrinsic_id` / `MIR_INTR_*` id ổn định + `args`.

### 2.3 Fields bắt buộc trên `HirNode` / `HirFunc`

- `name: string` (callee, var, field) — **fat string**
- `name2` hoặc flags (async / precomp / method) nếu cần parity `ast_lower_func`
- `op: i64` — map `OpType` cho BinOp/Compare
- `value: i64` — int lit; string lit → intern id **sau** ở MIR hoặc giữ string pointer trên HIR
- `args` / `body` vec — **luôn** `node.args = vec_push_rt(...)`
- Typed getters: `hir_node_kind(n)`, `hir_func_name(f)`, …

### 2.4 File mới

| File | Responsibility |
|------|----------------|
| `hir.vri` | Schema + constructors + accessors (**SoT**) |
| `ast_to_hir.vri` | `hir_lower_program(ast) -> HirModule` (hoặc vec HirFunc) |
| `hir_to_mir.vri` | `mir_lower_hir_program(hir) -> [MirFunc]` — **sole MIR emit owner** sau khi cắt |

`ast_to_mir.vri`: giữ tạm làm reference / fallback; sau parity đánh dấu deprecated hoặc thin wrapper gọi hir path.

---

## 3. Kế hoạch pha (bắt buộc theo thứ tự)

### Phase A — Schema HIR (không đổi pipeline)

1. Mở rộng `hir.vri` theo §2 (kinds, HirFunc/Module, name, accessors).
2. Export đầy đủ; không wire `pipeline` chưa.
3. **Done khi:** compile soft modules không lỗi; không regression (pipeline cũ vẫn AST→MIR).

### Phase B — AST→HIR (chưa thay pipeline)

1. Tạo `ast_to_hir.vri`.
2. Cover **P0 smoke** trước:
   - Program, FuncDef, params, Block
   - LiteralInt, Identifier, BinOp (+,-,*,/), Compare
   - VarDecl/ConstDecl, Assign, Return, Print
   - Call, BuiltinCall (alloc/print/… giữ name + builtin_id)
   - IfStmt, WhileStmt (When có thể desugar)
3. Unit-style: dump HirKind tree (print) cho `cg_arith.vri` / `cg_call.vri` nếu cần debug.
4. **Done khi:** HIR tree đúng cấu trúc cho các fixture P0 (manual/print OK).

### Phase C — HIR→MIR (song song, chưa cắt AST→MIR)

1. Tạo `hir_to_mir.vri`.
2. **Di chuyển** (không copy-paste mù) builder helpers từ `ast_to_mir`:
   - `builder_*`, `emit_*`, `get/set_var_vreg`, `MIR_INTR_PARAM` bind
3. Lower từng `HirKind` → đúng `MirOp` / `MIR_INTR_*` như registry.
4. API: `hir_lower_to_mir_program(HirModule) -> vec MirFunc` shape **giống** `ast_lower_program`.
5. So sánh: cùng input AST → path cũ vs `ast→hir→mir` — MIR dump hoặc chạy e2e.
6. **Done khi:** P0 fixtures qua path mới ra **cùng stdout/exit** với path cũ.

### Phase D — Wire `pipeline.vri`

```vir
# Trước:
let mir_funcs = ast_lower_program(ast)

# Sau:
let hir_mod = hir_lower_program(ast)       # ast_to_hir
let mir_funcs = mir_from_hir_program(hir_mod)  # hir_to_mir
# CFG / SSA / opt / lir_lower / RA — KHÔNG ĐỔI
```

1. `include`/`import` modules mới trong `pipeline.vri` (+ `virc.vri` nếu cần).
2. Xóa / comment verbose “AST to MIR” → “AST to HIR to MIR”.
3. Cập nhật header comment pipeline + MUST_READ tables.
4. **Done khi:** soft smoke P0 PASS; `cg_alloc_byte` không xấu hơn baseline hiện tại.

### Phase E — Mở rộng coverage

Map tiếp từ checklist AST→MIR (When/For/Case/Field/Index/async/…):
- Ưu tiên test `tests/bootstrap_codegen/manifest.json` đang FAIL vì lower, không phải RT stub.
- RT stubs (`alloc`, mem) là việc **lir_codegen** riêng — **không** block HIR wiring nếu MIR Call name đúng.

### Phase F — Dọn

- `ast_to_mir.vri`: deprecated wrapper hoặc chỉ re-export test helpers.
- Cập nhật `AST_TO_MIR_LOWERING_CHECKLIST.md` → `AST_HIR_MIR_LOWERING_CHECKLIST.md` (ownership mới).
- Không xóa C `hir.h` / `mir_lower.c` trong task này trừ khi user bảo.

---

## 4. Mapping gợi ý (P0)

### AST → HIR

| AstType | HirKind / structure |
|---------|---------------------|
| Program | HirModule.funcs |
| FuncDef | HirFunc + body Block |
| Identifier (param) | HirParam |
| Block | Block + body stmts |
| LiteralInt | Const (value=…) |
| Identifier (use) | Load / NameRef (var_id hoặc name) |
| BinOp / Compare | BinOp (op=OpType) |
| VarDecl / ConstDecl | VarDecl + init child |
| Assign | Store hoặc Assign |
| ReturnStmt | Return |
| PrintStmt | Print |
| Call | Call (name + args) |
| BuiltinCall | IntrinsicCall (intrinsic_id + name + args) |
| IfStmt | If (cond, then, else) |
| WhileStmt | Loop (cond ở đầu body hoặc field cond) |

### HIR → MIR (giữ semantics `ast_to_mir`)

| Hir | MIR |
|-----|-----|
| Const int | Move dst, Imm |
| NameRef/Load | Move từ vreg map |
| BinOp Add… | MirOp.Add… / Cmp* |
| VarDecl | new vreg + Move; set_var_vreg |
| Call | SetArg* + MirOp.Call + string pool id |
| IntrinsicCall / Builtin | MIR_INTR_BUILTIN marker + Call (như hiện tại) **hoặc** intrinsic riêng nếu đã có |
| Print | MIR_INTR_PRINT |
| If | blocks + JumpIf / Jump |
| Loop/While | loop_stack + JumpIfNot |
| Func params | **MIR_INTR_PARAM** dst, Imm(abi_index) — **bắt buộc** |

---

## 5. Quy tắc code soft (nhắc lại)

1. Fat string: `fat_str_eq` / `fat_str_new` — không `rt_streq` trên header.
2. `vec_get_rt` → typed accessor trước khi `.field`.
3. `x = vec_push_rt(x, …)` luôn gán lại.
4. Modulo: `mod`, không `%`.
5. Không đụng Stage-0/1 / `tools/bootstrap_fixed_point.sh` green path.
6. Đo soft: `tests/bootstrap_codegen/manifest.json` + `codesign -s - -f ./a.out`.
7. `codegen.vri` bitwise có thể đang dirty — **đừng** “fix” HIR bằng cách sửa encoder trừ khi block compile; hỏi user nếu cần.

---

## 6. Acceptance tests

### Mỗi phase A–D
```bash
# Host soft compiler
./core/build/vir run stdlib/vir/compiler/virc.vri -- tests/bootstrap_codegen/cg_arith.vri
codesign -s - -f ./a.out && ./a.out
# expect stdout khớp manifest
```

P0 list tối thiểu: `cg_arith`, `cg_mul`, `cg_var`, `cg_assign`, `cg_call`, `cg_multiparam`.

### Phase D xong
- Cùng lệnh trên; diff stdout vs trước khi wire (baseline).
- Không yêu cầu cố định toàn bộ 100+ manifest tests trong PR HIR đầu.

### Rollback
- Một commit/flag: `pipeline` gọi lại `ast_lower_program` nếu path HIR đỏ.
- Không force-push; không amend trừ user bảo.

---

## 7. Definition of Done (toàn bộ task)

- [ ] `hir.vri` đủ schema + export + accessors (SoT).
- [ ] `ast_to_hir.vri` + `hir_to_mir.vri` tồn tại và được `pipeline.vri` gọi.
- [ ] Soft P0 smoke PASS như trước khi tách.
- [ ] MIR→LIR→codegen **không** refactor lớn.
- [ ] Docs: pipeline header + `PIPELINE_MAPPING_TABLES.md` ghi soft đã AST→HIR→MIR (bỏ “gap wiring” nếu đã xong).
- [ ] Không còn phụ thuộc QIR-H/M/L.

---

## 8. Gợi ý thứ tự file edit

1. `stdlib/vir/compiler/hir.vri`  
2. `stdlib/vir/compiler/ast_to_hir.vri` *(new)*  
3. `stdlib/vir/compiler/hir_to_mir.vri` *(new)* — move emit từ `ast_to_mir`  
4. `stdlib/vir/compiler/pipeline.vri` — wire  
5. `stdlib/vir/compiler/virc.vri` — import nếu cần  
6. MUST_READ: pipeline tables + checklist rename/update  
7. `ast_to_mir.vri` — deprecate / thin wrapper  

---

## 9. Out of scope nhắc lại (để AI khác khỏi lạc)

- Fix `cg_alloc_byte` RT stubs / SIGSEGV alloc — **lir_codegen**, parallel track.
- Control-flow empty stdout (`cg_if`) — có thể lộ khi qua HIR; fix ở hir_to_mir hoặc giữ bug parity rồi fix riêng.
- `codegen.vri` bitwise syntax — user/track khác.
- Xóa `hir.vri` hoặc bỏ HIR — **cấm** (trái quyết định kiến trúc).

---

*Hết chỉ thị. Thực hiện theo Phase A→F; báo cáo mỗi phase: files touched, smoke results, residual gaps.*
