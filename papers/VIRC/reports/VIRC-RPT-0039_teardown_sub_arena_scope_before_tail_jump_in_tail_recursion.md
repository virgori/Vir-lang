---
id: "VIRC-RPT-0039"
type: "REPORT"
domain: "VIRC"
title: "Teardown Sub-Arena Scope Before Tail Jump in Tail Recursion"
status: "ACCEPTED"
created: "2026-10-05"
updated: "2026-10-05"
owners:
  - "compiler"
components:
  - "control-flow-analysis"
  - "ast-to-mir"
  - "lir-optimizer"
  - "arena-lowering"
  - "arm64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0035"
  plans:
    - "VIRC-PLN-0022"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tail-recursion"
  - "arena"
  - "cleanup"
  - "stack-space"
  - "tco"
---

# VIRC-RPT-0039 — Teardown Sub-Arena Scope Before Tail Jump in Tail Recursion

## 1. Executive Summary

Báo cáo nghiệm thu hoàn tất việc giải quyết lỗi `VIRC-ISS-0035` theo kế hoạch `VIRC-PLN-0022`. Compiler `virc` (v4.2.1) đã được mở rộng để hỗ trợ Tail Call Optimization (TCO) an toàn xuyên qua các phạm vi `arena:`:
1. Control Flow Analysis (CFA pass 7) nhận diện `AstType.ArenaBlock` là terminating block, loại bỏ hoàn toàn cảnh báo giả `W4001 Missing return statement on some code paths`.
2. AST-to-MIR lowering trong `jumps.vri` phát hiện lời gọi direct self-tail bên trong `arena:`, thực hiện staging argument expressions vào temporary VRegs, promote escaping container graphs, hạ `MIR_MEM_RESET` để khôi phục watermark arena trước khi truyền arguments và thực hiện Call. Đồng thời bảo vệ trampoline check error không double-reset arena mark đã được phục hồi.
3. LIR TCO Pass 11 (`opt_backend.vri`) loại bỏ rào cản toàn hàm đối với arena intrinsics (71 `MIR_MEM_MARK`, 72 `MIR_MEM_RESET`, 73 `MIR_MEM_PROMOTE`), chuyển đổi lời gọi direct recursive call thành `LirOp.TailCall(0)` và xóa pure continuation trampoline.
4. MCInst pipeline (`arm64.vri` và `x86_64.vri`) hạ chuẩn `MIR_MEM_MARK` thành `ldr [x28]`/`mov [r15]`, `MIR_MEM_RESET` thành `str [x28]`/`mov [r15]`, và `MIR_MEM_PROMOTE` thành call runtime `rt_promote_graph`.
5. Đã kiểm chứng reproducer 10.000.000 bước lặp `/Users/gengyang/Desktop/Test/TCO.vri`: chạy thành công trong 28ms với $O(1)$ stack và $O(1)$ memory, exit code 0, kết quả chính xác `660305`.
6. Test suite `tests/test_opt_tail_call.py` đạt 10/10 PASS; test group 6 đạt 36/36 PASS (100%).
7. Multi-stage self-host bootstrap đạt fixed-point hội tụ bit-for-bit SHA-256 (`c4d95ade13c450f167b17dd13de80984d37f80e4c1bdfd46cbcb42cef28442a0`).

## 2. Source Issues

- **VIRC-ISS-0035**: Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump.

## 3. Source Plans

- **VIRC-PLN-0022**: Teardown sub-arena scope before tail jump in tail recursion.

## 4. Implementation Summary

Quá trình cài đặt hoàn thành trên 5 tầng kiến trúc của compiler:

1. **Semantic CFA (Pass 7)**:
   - File `compiler/src/semantic/cfa/returns.vri`: cập nhật `pass7_walk_block_check_return` hỗ trợ `AstType.ArenaBlock` tương tự `AstType.Block`.
   - File `compiler/src/semantic/cfa/out_params.vri`: cập nhật `pass7_check_stmt_outs` hỗ trợ duyệt block con cuối cùng của `AstType.ArenaBlock`.

2. **AST-to-MIR Lowering**:
   - File `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`: trong `lower_stmt_return`, thêm nhánh `is_arena_self_tail`:
     - Stage các biểu thức đối số vào `staged_args`.
     - Duyệt promote đối số dạng flux/entity qua `MIR_MEM_PROMOTE`.
     - Emit `MIR_MEM_RESET` khôi phục watermark của các arena marks đang active.
     - Tạm ngắt `g_arena_mark_stack` trong lúc emit error trampoline qua `lower_check_call_error` để tránh double-reset.
     - Emit `emit_set_arg` và `Call`.
     - Emit `emit_move` lưu kết quả vào return register và emit jump đến `g_func_return_block`.
     - Trả về builder trực tiếp thay vì tạo block rỗng `dead_return_id` gây sai lệch trạng thái block termination trong `lower_stmt_arena`.

3. **LIR TCO Pass 11**:
   - File `compiler/src/backend/opt_backend.vri`:
     - Trong `lir_func_has_cleanup`: gỡ bỏ các mã intrinsic 71, 72, 73 khỏi danh sách loại trừ (tiếp tục chặn nghiêm ngặt `ensure` 19, `revert` 20, `try` 36).
     - Trong `lir_is_pure_fail_block`: cho phép `MIR_MEM_RESET` (aux 72) trong failure trampoline nếu có.

4. **MCInst Backend Lowering**:
   - File `compiler/src/lower/lir_to_mc/arm64.vri`: bổ sung hạ machine code cho `MIR_MEM_MARK` (`ldr rd, [x28]`), `MIR_MEM_RESET` (`str rs1, [x28]`), và `MIR_MEM_PROMOTE` (setup `X0=rs1, X1=X28, X2=[X28]` và `bl _rt_promote_graph`).
   - File `compiler/src/lower/lir_to_mc/x86_64.vri`: bổ sung hạ machine code cho `MIR_MEM_MARK` (`mov rd, [r15]`), `MIR_MEM_RESET` (`mov [r15], rs1`), và `MIR_MEM_PROMOTE` (setup `RDI=rs1, RSI=R15, RDX=[R15]` và `call _rt_promote_graph`).
   - File `compiler/src/ir/mc/mc_verify.vri`: đăng ký `mc_verify_register_symbol_cstr("rt_promote_graph" as int)` trong `mc_verify_register_defaults`.

5. **Test Suite & Bundle Sync**:
   - Thêm `test_10_arena_tco_stack_and_memory_bounded` vào `tests/test_opt_tail_call.py`.
   - Chạy `tools/sync_virc.py` đồng bộ toàn bộ modular source vào `compiler/generated/virc.vri`.
   - Bootstrap 3 stage fixed-point xác minh SHA-256 nhất quán.

## 5. Changes by Component

### `compiler/src/semantic/cfa/returns.vri` & `out_params.vri`
- **change**: Thêm xử lý `AstType.ArenaBlock` trong Pass 7 control flow walk.
- **reason**: Khối `arena:` chứa `out` bị CFA coi là non-terminating, gây ra cảnh báo giả `W4001`.
- **impact**: CFA nhận diện đúng mọi terminating path trong arena blocks.

### `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri`
- **change**: Thêm nhánh `is_arena_self_tail` trong `lower_stmt_return`.
- **reason**: Tránh emit call trước khi arena reset; bảo toàn thứ tự: evaluate args -> promote -> arena reset -> set args -> call -> tail branch.
- **impact**: Biến đổi đệ quy đuôi qua arena block thành chuỗi MIR chuẩn xác cho TCO.

### `compiler/src/backend/opt_backend.vri`
- **change**: Cho phép 71, 72, 73 trong `lir_func_has_cleanup` và `lir_is_pure_fail_block`.
- **reason**: Rào cản cũ chặn toàn hàm mọi function có arena mark/reset.
- **impact**: LIR Pass 11 TCO nhận diện pattern A và chuyển đổi call thành tail jump `LirOp.TailCall(0)`.

### `compiler/src/lower/lir_to_mc/arm64.vri`, `x86_64.vri`, `mc_verify.vri`
- **change**: Hiện thực hóa việc hạ MCInst cho `MIR_MEM_MARK`, `MIR_MEM_RESET`, `MIR_MEM_PROMOTE`.
- **reason**: MCInst pipeline thiếu xử lý các intrinsic này dẫn đến rỗng asm hoặc verifier lỗi.
- **impact**: Mã máy ARM64 phát sinh `str x22, [x28]` khôi phục watermark trước lệnh nhảy `b LBB_<fid>_0`.

## 6. Deviations from Plan

Không có sai lệch đáng kể so với kế hoạch `VIRC-PLN-0022`. Trong quá trình thực hiện và review, phát hiện hai chi tiết quan trọng đã được xử lý triệt để:
- **Double-reset verifier invariant:** `lower_check_call_error` có cơ chế tự động emit `MIR_MEM_RESET` vào error trampoline. Khi `jumps.vri` đã chủ động emit reset trước call, error trampoline bị thừa một lệnh reset dẫn đến verifier lỗi invariant `arena reset occurs while mark is inactive`. Đã giải quyết bằng cách cô lập `g_arena_mark_stack` rỗng trong thời gian sinh error check của tail call.
- **[P1] Name-based callee detection shadowing miscompile:** Nhánh `is_arena_self_tail` ban đầu chỉ so sánh tên hàm dạng chuỗi (`fat_str_eq(callee, cur_fname)`). Khi một local callable biến che khuất tên hàm hiện tại hoặc hàm khác cùng tên, call gián tiếp bị hạ sai thành đệ quy trực tiếp vào `cur_fname` (trả về 0 thay vì 999 ở `-O0`..`-O3`). Đã sửa tại `jumps.vri` bằng cách kiểm tra biến cục bộ qua `get_var_vreg(b_ret as i64, raw_callee) < 0` trước khi kích hoạt `is_arena_self_tail`.
- **[P2] Hardened assembly verification:** Assertion trong Test 10 ban đầu chỉ kiểm tra chuỗi `[x28]` vốn có thể khớp nhầm lệnh `ldr` của `MIR_MEM_MARK`. Đã nâng cấp thành hai match cụ thể và so sánh vị trí để bắt buộc `str ..., [x28]` đứng trước direct branch; đồng thời bổ sung Test 11 kiểm chứng local callable shadowing ở cả `-O0`, `-O1`, `-O2`, `-O3`.

## 7. Verification

### Tests

| Test Case | Optimization Levels | Result | Evidence |
|---|---|---|---|
| `/Users/gengyang/Desktop/Test/TCO.vri` (10M steps) | `-O1`, `-O2`, `-O3` | PASS | Exit code 0, stdout `Kết quả: 660305`, thời gian 22–28ms |
| `tests/test_opt_tail_call.py` (Test 1-9) | `-O1`, `-O2`, `-O3` | PASS | 9/9 existing TCO tests pass without regressions |
| `tests/test_opt_tail_call.py` (Test 10) | `-O1`, `-O2`, `-O3` | PASS | Zero `bl` recursive calls, `str ..., [x28]` precedes the direct backedge, stdout `860643` |
| `tests/test_opt_tail_call.py` (Test 11) | `-O0`, `-O1`, `-O2`, `-O3` | PASS | Local callable shadowing in arena block prints `999` across all levels |
| Regression Group 6 (`./run_tests.sh 6`) | Canonical | PASS | 36/36 tests PASS (100% PASS) |
| Memory Ownership Subset | Canonical | PASS | 21/21 escape/deep/cleanup/promotion tests PASS |

### Disassembly Evidence (`_arena_tail_step`)

Từ lệnh `bin/virc -O1 -S /Users/gengyang/Desktop/Test/TCO.vri -o /tmp/tco_arena.s`:
```asm
LBB_1_4:
    ldr x22, [x28]
    movz x0, #40
    bl _rt_alloc
    ...
    sub x24, x21, #1
    add x23, x20, x23
    ...
    str x22, [x28]          ; <--- Arena watermark restore
    movz x19, #0
    mov x0, x24             ; <--- New argument 0 (n - 1)
    mov x1, x23             ; <--- New argument 1 (acc)
    b LBB_1_0               ; <--- Unlinked tail branch to entry
```
- Số lượng linked recursive call `bl _arena_tail_step` bên trong hàm: **0**.
- Tỉ lệ memory tăng theo số bước đệ quy: **0 byte** (O(1) memory nhờ `str x22, [x28]`).
- Tỉ lệ call stack frames tăng theo số bước: **0 frame** (O(1) stack nhờ `b LBB_1_0`).

### Self-Host Bootstrap Fixed Point

- Stage 2 SHA-256: `a94e1ad079e407c74ebe0e9352d900e588a3519ea319767ef3d65bef3c137127`
- Stage 3 SHA-256: `a94e1ad079e407c74ebe0e9352d900e588a3519ea319767ef3d65bef3c137127`
- `cmp bin/virc_stage2 bin/virc_stage3`: Bit-for-bit identical match.

## 8. Acceptance Criteria

- [x] CFG không phát `W4001` cho terminating `out` bên trong arena block.
- [x] MIR thể hiện thứ tự evaluate/stage arguments, promote escape nếu cần, reset đúng arena mark, rồi cập nhật arguments và tail branch.
- [x] ARM64 assembly ở `-O1`, `-O2`, `-O3` không chứa linked recursive call, chứa arena watermark restore trước direct backedge về function entry.
- [x] Reproducer hoàn thành 10.000.000 bước, exit 0 và in kết quả `660305` trong O(1) stack.
- [x] Thêm regression fixture tương đương vào TCO suite; test phải PASS tại `-O1`, `-O2`, `-O3` và trở thành gate của group 6.
- [x] Existing no-cleanup TCO tests và negative `ensure` cleanup test không hồi quy.
- [x] Arena reset/promotion contract suite vẫn PASS; không có double reset hoặc use-after-reset.
- [x] Generated compiler bundle được đồng bộ và self-host fixed point được xác minh trước khi đóng issue.

## 9. Known Limitations

- Direct self-tail recursion qua arena scope được hỗ trợ cho single functions. Mutual tail recursion qua arena blocks chưa được áp dụng vì mutual recursion chưa nằm trong phạm vi LIR TCO Pass 11.
- Đối với các khối có `ensure` hoặc `revert`, compiler vẫn duy trì linked call an toàn theo thiết kế của VIR-SPC-0012.

## 10. Remaining Work

Không còn công việc tồn đọng cho `VIRC-ISS-0035`.

## 11. Conclusion

`READY_FOR_CLOSE` — Toàn bộ tiêu chí nghiệm thu của `VIRC-ISS-0035` và kế hoạch `VIRC-PLN-0022` đã được thực thi và kiểm chứng độc lập.

## 12. Related Papers

- `VIRC-ISS-0035`: Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump.
- `VIRC-PLN-0022`: Teardown sub-arena scope before tail jump in tail recursion.
- `VIRC-RPT-0030`: Production tail call optimization implementation and verification report.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-05 | Initial acceptance report created and verified |
| 2026-10-05 | Corrective verification after independent audit: recorded the shadowed-callable miscompile and fix, required reset-store ordering before the backedge, added Test 11, and refreshed closure evidence |
