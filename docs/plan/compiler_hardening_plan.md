# Vir Compiler Hardening Plan
## Phase 1: SSA Correctness · Phase 2: Borrow Checker Correctness

**Ngay lap:** 07/09/2026
**Trang thai:** DRAFT — cho phe duyet
**Pham vi:** stdlib/vir/compiler/
**Test baseline:** 179/179 PASSED — phai giu nguyen sau moi phase

---

## Quy Tac Chung

- **Strict claim:** Moi fix PHAI di kem mot claim co the kiem chung (test case cu the). Fix khong co claim khong duoc merge.
- **Arena block:** Moi ham opt/analysis ma allocate va discard hoan toan trong mot lan goi PHAI dung arena block.
- **Test suite:** run_tests.sh phai dat 100% sau moi task.
- **Bootstrap:** Sau khi hoan thanh moi phase, rebuild bin/virc va chay smoke test.
- **Arena semantics:** Arena block la scope-block. Borrow checker chi phan tich escape theo lexical scope, khong inter-procedural.

---

## Phase 1 — SSA Correctness

### Task 1.1 — Sentinel Init trong mir_rename_variables

**File:** stdlib/vir/compiler/mir_ssa.vri L436-440
**Van de:** Stack init voi vreg goc. Neu vreg chua def tren duong dominator, ssa_stack_top tra ve vreg goc (pre-SSA lan post-SSA namespace).

**Fix:**
  L438: thay  stk = vec_push_rt(stk, v)
        bang  stk = vec_push_rt(stk, 0 - 1)   # sentinel undefined
  Sua ssa_stack_top: neu top == -1, fallback ve slot index.

**Claim:** Compile tests/test_register.vri va tests/test_str_len_fold.vri — output byte-for-byte khong doi.

---

### Task 1.2 — Dead Phi Sweep sau mir_opt_phi_simplification

**File:** stdlib/vir/compiler/mir_opt.vri — them sau L1473
**Van de:** Phi voi incoming_values rong van nam trong block.phis, gây regalloc ton vreg slot thua.

**Fix:** Them mir_opt_sweep_dead_phis(blocks), goi sau mir_opt_phi_simplification trong spec pipeline.

**Claim:** Sau fix, khong co block nao co phi voi incoming_values.len == 0 trong MIR post-pipeline.

---

### Task 1.3 — Arena Block trong Callers cua mir_build_vreg_def_counts

**File:** stdlib/vir/compiler/mir_opt.vri L166-229
**Van de:** def_counts Vec duoc tao dung roi bo — phu hop de free som.

**Fix:** Trong mir_opt_copy_propagation va mir_opt_constant_propagation, wrap logic dung def_counts trong arena. blocks duoc modified in-place (khong co allocation moi escape).

**Claim:** run_tests.sh 179/179. def_counts Vec khong ton tai sau khi pass hoan thanh.

---

### Task 1.4 — Arena Block trong mir_rename_block

**File:** stdlib/vir/compiler/mir_ssa.vri L298-430
**Dieu kien:** Verify MirInstr va MirPhi la entity (value copy), khong phai pointer, truoc khi ap dung.

**Fix:** Neu la entity, wrap body vong lap phi rename trong arena.

**Claim:** run_tests.sh 179/179. Self-hosting bootstrap thanh cong.

---

### Phase 1 Checklist

| Task | File | Dong | Status |
|------|------|------|--------|
| 1.1 Sentinel init | mir_ssa.vri | L436-440 | [ ] |
| 1.2 Dead phi sweep | mir_opt.vri | sau L1473 | [ ] |
| 1.3 Arena def_counts | mir_opt.vri | L166-229 | [ ] |
| 1.4 Arena rename_block | mir_ssa.vri | L300-430 | [ ] |
| Bootstrap bin/virc | — | — | [ ] |
| run_tests.sh 179/179 | — | — | [ ] |

---

## Phase 2 — Borrow Checker Correctness

NOTE: Arena block la scope-block — borrow checker chi phan tich escape theo lexical scope cua arena, khong inter-procedural.

### Task 2.1 — Fix Move-on-Call [CRITICAL]

**File:** stdlib/vir/compiler/sem_pass8_borrow.vri L812-828
**Van de:** Truyen by-value vao ham khong mark moved. Double-move qua call khong bi phat hien.

**Fix:** Trong Call/MethodCall handler, sau pass8_walk(arg):
  neu arg la Identifier:
    neu da moved: report E5001
    neu chua moved va type_is_move: pass8_mark_moved

**Claim:**
  var arr = [1, 2, 3]
  consume(arr)   # move #1 ok
  consume(arr)   # E5001 PHAI duoc bao
**Test:** tests/test_borrow_move_on_call.vri

---

### Task 2.2 — Fix Arena Escape qua Bound Borrow [CRITICAL]

**File:** stdlib/vir/compiler/sem_pass8_borrow.vri L831-848
**Van de:** out r khi r la borrow binding cua arena-local khong bi phat hien (E5005).

**Fix:** Trong ReturnStmt, them lookup bound_borrows khi val la Identifier:
  neu bb = lookup(val.name) trong bound_borrows:
    tgt = borrow_binding_target(bb)
    neu in_arena va tgt in arena_locals: report E5005
    neu tgt in func_locals: report E5007

**Claim:**
  arena:
    var x = 42
    let r = &x
    result = r   # E5005 PHAI duoc bao
  end
**Test:** tests/test_borrow_arena_escape.vri

---

### Task 2.3 — Fix If-Branch Move Flow Join [CRITICAL]

**File:** stdlib/vir/compiler/sem_pass8_borrow.vri L946-973
**Van de:** IfStmt walk then/else tuan tu voi cung moved_vars. Khong co join tai merge point.

**Fix — Conservative union voi arena:**
  - Walk condition
  - arena block: walk then-branch -> snapshot moved_then; walk else-branch -> snapshot moved_else
  - Union: mark trong moved_vars neu ten xuat hien trong moved_then (conservative)
  - Temp buffers duoc free khi het arena
  - Truncate borrows ve watermark (khong thay doi)

**Claim:**
  Case 1 (phai E5001): if cond do consume(arr) end; print(arr)
  Case 2 (phai ok): var x = 42; if cond do x = 0 end; print(x)
**Test:** tests/test_borrow_if_move.vri

---

### Task 2.4 — Fix Borrow Conflict Order trong Assign [MEDIUM]

**File:** stdlib/vir/compiler/sem_pass8_borrow.vri L747
**Van de:** pass8_release_borrower truoc process_binding_rhs che khuat xung dot rebind.

**Fix — swap thu tu:**
  claimed = pass8_process_binding_rhs(...)    # walk RHS truoc
  pass8_release_borrower(...)                 # sau do release
  pass8_unmark_moved(...)

**Claim:**
  let r = &x
  r = &mut x    # E5003 PHAI duoc bao (x con shared borrow)
**Test:** tests/test_borrow_rebind_conflict.vri

---

### Task 2.5 — Arena Block trong FuncDef Handler [OPT]

**File:** stdlib/vir/compiler/sem_pass8_borrow.vri L876-907
**Van de:** 8 pass8_box_new() alloc per function, tich luy tuyen tinh.

**Fix:** Wrap toan bo function analysis trong arena:
  scope_push(scopes, ScopeKind.Func)
  arena:
    let func_moved = pass8_box_new()
    ... (8 boxes)
    # walk children
  end   # tat ca 8 box duoc free sau moi ham
  scope_pop(scopes)

**Claim:** File 500 ham: peak memory giam ro. run_tests.sh 179/179.

---

### Phase 2 Checklist

| Task | File | Dong | Priority | Status |
|------|------|------|----------|--------|
| 2.1 Move-on-call | sem_pass8_borrow.vri | L812-828 | CRITICAL | [ ] |
| 2.2 Arena escape via borrow | sem_pass8_borrow.vri | L831-848 | CRITICAL | [ ] |
| 2.3 If-branch flow join | sem_pass8_borrow.vri | L946-973 | CRITICAL | [ ] |
| 2.4 Borrow conflict order | sem_pass8_borrow.vri | L747 | MEDIUM | [ ] |
| 2.5 Arena FuncDef | sem_pass8_borrow.vri | L876-907 | OPT | [ ] |
| test_borrow_move_on_call.vri | tests/ | NEW | — | [ ] |
| test_borrow_if_move.vri | tests/ | NEW | — | [ ] |
| test_borrow_arena_escape.vri | tests/ | NEW | — | [ ] |
| test_borrow_rebind_conflict.vri | tests/ | NEW | — | [ ] |
| Bootstrap bin/virc | — | — | — | [ ] |
| run_tests.sh >= 183/183 | — | — | — | [ ] |

---

## Thu Tu Thuc Hien

Phase 1 (SSA):
  1.1 sentinel -> 1.2 dead phi sweep -> 1.3 arena def_counts -> 1.4 arena rename
  -> Bootstrap -> run_tests 179/179

Phase 2 (Borrow):
  2.1 move-on-call + test
  2.2 arena escape borrow + test
  2.3 if-branch join + test
  2.4 rebind conflict + test
  2.5 arena FuncDef (opt)
  -> Bootstrap -> run_tests >= 183/183

## Files Se Duoc Sua

| File | Phase | Tasks |
|------|-------|-------|
| stdlib/vir/compiler/mir_ssa.vri | 1 | 1.1, 1.4 |
| stdlib/vir/compiler/mir_opt.vri | 1 | 1.2, 1.3 |
| stdlib/vir/compiler/sem_pass8_borrow.vri | 2 | 2.1-2.5 |
| tests/test_borrow_move_on_call.vri | 2 | NEW |
| tests/test_borrow_if_move.vri | 2 | NEW |
| tests/test_borrow_arena_escape.vri | 2 | NEW |
| tests/test_borrow_rebind_conflict.vri | 2 | NEW |
