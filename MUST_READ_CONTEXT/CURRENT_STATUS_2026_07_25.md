# Báo Cáo Tình Trạng Dự Án Vir v2.0
**Ngày:** 2026-07-25 05:05 (GMT+7)  
**Branch hiện tại:** `recovered_stash`

> **Đã có bản mới hơn:** `CURRENT_STATUS_2026_07_26.md`. Cả ba mục "Next" bên dưới
> đã xong; Stage-1 nay sinh được binary chạy thật.

---

## Self-host (honest)

| Commit | Description |
|--------|-------------|
| `431df9bc` | LIR multifn Call/SetArg/PrintStr |
| `ec4f5a17` | Flat MIR Constant Folding & DCE before LIR Emit |
| `300cef97` | Flat MIR Copy-Propagation & Dead-Load DCE (11/11 PASS) |
| `a18a9802` | Wire boot_stage1_compile CLI pipeline in dist/virc-stage1 |

| Stage | Status |
|-------|--------|
| Stage-0 bootstrap suite | **11/11 PASS** |
| Stage-1 thin stub `main` | **PASS** — Calls `boot_stage1_compile` |
| Real-lowered pipeline | **PASS** — compile → double → choose |
| Body-dump Jump/If | **PASS** — JumpIfNot / Jump / Label + patch |
| Output | `84` (double) rồi `7` (if/else else-branch) |

```bash
./core/build/vir run virc_boot.vri -- virc_boot.vri -o dist/virc-stage1
codesign -f -s - dist/virc-stage1
./dist/virc-stage1
# → ... / 84 / 7 / stage1 pipeline ok
```

---

## What landed (latest)

- **bd emit**: opc 29/30/31/32 (JumpIf / Jump / JumpIfNot / Label) + per-func label fixups (`boot_cg_patch_jumps`).
- **IfStmt / WhileStmt** push bd ops khi dump bật.
- **`boot_stage1_choose`**: `if 0 … else out 7` — chứng minh B.EQ nhảy đúng else.
- `QOp.JumpIf = 29` thêm vào enum (trước đây dùng nhưng thiếu).

---

## Next

1. Cmp* trong bd emit + `if a < b` với named locals.
2. Unskip dần tokenize/parse helpers vào Stage-1.
3. Stage-2: `virc-stage1` compiles tiny `.vri` → runnable binary.
