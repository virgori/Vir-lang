---
id: "VIRC-ISS-0035"
type: "ISSUE"
domain: "VIRC"
title: "Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump"
status: "CLOSED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
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
  issues: []
  plans:
    - "VIRC-PLN-0022"
  reports:
    - "VIRC-RPT-0039"
supersedes: null
superseded_by: null
tags:
  - "tail-call"
  - "tail-recursion"
  - "arena"
  - "cleanup"
  - "stack-space"
  - "segfault"
  - "regression"
---

# VIRC-ISS-0035 — Tail recursion across an arena scope cannot perform teardown before a constant-stack tail jump

## 1. Summary

Một direct self-tail-call nằm trong explicit `arena:` không được hạ thành chuỗi
an toàn `evaluate arguments -> restore arena mark -> tail jump`. `virc 4.2.1`
giữ lại linked recursive call ở mọi mức tối ưu, làm reproducer 10.000.000 bước
chết với SIGSEGV do stack exhaustion. Cùng source còn nhận cảnh báo CFG sai
`W4001 Missing return statement on some code paths` dù mọi đường hợp lệ đều
`out`.

## 2. Context

VIR memory contract yêu cầu explicit sub-arena được reset trên mọi đường thoát,
bao gồm `out`. TCO contract yêu cầu direct self-tail recursion chạy với O(1)
stack. Khi hai contract gặp nhau, compiler phải tính và bảo toàn đối số mới,
reset watermark của arena hiện tại, cập nhật parameters rồi mới branch về entry
block.

`VIRC-RPT-0030` đã ghi nhận implementation TCO hiện tại dùng safety gate toàn
hàm: nếu có arena reset hoặc cleanup thì giữ linked call. Gate đó tránh bỏ qua
cleanup, nhưng không đáp ứng ca hợp lệ cần thực thi cleanup trước tail jump.

## 3. Expected Behavior

- CFG nhận diện `out` trong `arena:` là terminating path và không phát `W4001`.
- Các đối số `n - 1` và `(acc + tail) mod 1000000` được evaluate trước reset.
- Arena watermark được restore đúng một lần trước backedge.
- Direct self-call được thay bằng unlinked branch về entry block ở `-O1` đến
  `-O3`, giữ O(1) call stack.
- Fixture 10.000.000 bước hoàn thành và in kết quả `660305` mà không tăng stack
  hoặc giữ lại 10.000.000 arena allocations.

## 4. Actual Behavior

- Compiler tạo executable ở `-O0`, `-O1`, `-O2`, `-O3` và phát `W4001` tại
  declaration của `arena_tail_step`.
- Cả bốn executable in hai dòng đầu rồi thoát `139` trong khoảng 0,6–0,8 giây.
- ARM64 assembly tại `-O1`, `-O2`, `-O3` chứa `bl _arena_tail_step`; không có
  direct `b LBB_1_0` cho recursive backedge.
- TCO pass bỏ qua toàn bộ function ngay khi `lir_func_has_cleanup` thấy
  `MIR_MEM_MARK`, `MIR_MEM_RESET`, promotion hoặc cleanup liên quan.

## 5. Reproduction

Reproducer do người dùng xác nhận: `/Users/gengyang/Desktop/Test/TCO.vri`.

```text
./bin/virc -O1 /Users/gengyang/Desktop/Test/TCO.vri -o /tmp/tco_arena
codesign -s - -i virc -f /tmp/tco_arena
/tmp/tco_arena
```

## 6. Evidence

- `./bin/virc` tự báo version `4.2.1` trong bốn compile runs.
- Runtime exit: `-O0=139`, `-O1=139`, `-O2=139`, `-O3=139`; stdout dừng sau
  `Bắt đầu chạy N = 10000000...`.
- Isolated ARM64 bodies ở `-O1`, `-O2`, `-O3` đều chứa đúng một linked
  `bl _arena_tail_step`.
- `compiler/src/backend/opt_backend.vri` trả về sớm trong
  `opt_backend_run_tco` khi `lir_func_has_cleanup(lf) == 1`.
- `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri` hiện lower return
  expression trước rồi mới emit `MIR_MEM_RESET`; với tail call, thứ tự này đặt
  teardown sau khi recursive call đã quay về.
- Giá trị oracle `660305` được tính độc lập từ recurrence của source.

## 7. Scope

### Affected

- direct self-tail recursion bên trong explicit `arena:`;
- CFG termination analysis cho `out` trong arena block;
- AST-to-MIR ordering của argument evaluation, promotion và reset;
- LIR TCO cleanup gate và ARM64 code generation;
- stack-space và arena lifetime guarantees khi kết hợp.

### Not affected / Unknown

- Tail recursion không có cleanup vẫn PASS trong suite hiện tại.
- `ensure` cleanup vẫn phải giữ linked call trừ khi có transformation riêng bảo
  toàn semantics; issue này chỉ yêu cầu cleanup-aware TCO cho arena mark/reset.
- Chưa xác minh x86-64, RISC-V và Wasm cho ca kết hợp này.

## 8. Impact

Chương trình hợp lệ tuân theo cả TCO và arena contracts bị biến thành process
crash ở độ sâu lớn. Nếu chỉ bỏ safety gate để tail-jump mà không đặt reset đúng
thứ tự, compiler sẽ tránh stack overflow nhưng làm hỏng arena lifetime và có
thể tăng RAM không giới hạn. Vì vậy đây là lỗi S1/P1 cần một transformation có
ordering rõ ràng, không phải chỉ nới điều kiện optimizer.

## 9. Preliminary Analysis

Phân biệt rõ:

- **CONFIRMED:** cleanup gate toàn hàm là lý do Pass 11 không tạo TailCall.
- **CONFIRMED:** source chết exit 139 ở mọi optimization level được thử.
- **CONFIRMED:** CFG phát `W4001` sai trên function có `out` ở base case và
  `out` trong arena path.
- **OBSERVED:** generated assembly giữ linked call ở `-O1` đến `-O3`.
- **HYPOTHESIS:** lowering cần một arena-tail-return form hoặc canonical MIR
  sequence giữ staged arguments sống qua `MIR_MEM_RESET`, sau đó TCO mới rewrite
  call/return thành parameter moves + backedge.
- **NOT_VERIFIED:** mức RAM tối đa trước crash nếu tăng process stack để tránh
  stack exhaustion.
- **NOT_VERIFIED:** cross-target behavior ngoài macOS ARM64.

## 10. Acceptance Criteria

- [x] CFG không phát `W4001` cho terminating `out` bên trong arena block.
- [x] MIR thể hiện thứ tự evaluate/stage arguments, promote escape nếu cần,
  reset đúng arena mark, rồi cập nhật arguments và tail branch.
- [x] ARM64 assembly ở `-O1`, `-O2`, `-O3` không chứa linked recursive call,
  chứa arena watermark restore trước direct backedge về function entry.
- [x] Reproducer hoàn thành 10.000.000 bước, exit 0 và in kết quả `660305`
  trong O(1) stack.
- [x] Thêm regression fixture tương đương vào TCO suite; test phải PASS tại
  `-O1`, `-O2`, `-O3` và trở thành gate của group 6.
- [x] Existing no-cleanup TCO tests và negative `ensure` cleanup test không hồi
  quy.
- [x] Arena reset/promotion contract suite vẫn PASS; không có double reset hoặc
  use-after-reset.
- [x] Generated compiler bundle được đồng bộ và self-host fixed point được xác
  minh trước khi đóng issue.

## 11. Related Papers

### Issues

- VIRC-ISS-0024 — production direct self-tail-call optimization (closed).
- VIRC-ISS-0034 — rejected triage from accidentally overwritten reproducer.

### Plans

- VIRC-PLN-0022 — Teardown sub-arena scope before tail jump in tail recursion

### Reports

- VIRC-RPT-0030 — current TCO implementation and its conservative cleanup gate.
- VIRC-RPT-0039 — Teardown sub-arena scope before tail jump in tail recursion

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Reproduced on virc 4.2.1 at O0-O3, recorded runtime/assembly evidence, and triaged S1/P1 |
| 2026-10-05 | Linked VIRC-PLN-0022 and advanced to IMPLEMENTING |
| 2026-10-05 | Linked VIRC-RPT-0039 |
| 2026-10-05 | Acceptance criteria verified in VIRC-RPT-0039, issue closed |
| 2026-10-05 | Independent acceptance audit reproduced a P1 shadowed-callable miscompile and found the reset-order regression assertion incomplete; prior closure invalidated and issue returned through REOPENED to IMPLEMENTING |
| 2026-10-05 | Shadowed-callable resolution and ordered reset-before-backedge regression verified at O0-O3; TCO, Group 6, memory, fixed-point, bundle-sync, and VPS gates passed; issue advanced through VERIFYING and RESOLVED to CLOSED |
