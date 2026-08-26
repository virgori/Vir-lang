# Báo Cáo Tình Trạng — Self-Host Thin Cone + Soft Path
**Ngày:** 2026-07-30  
**Branch:** `recovered_stash`

**IR (official, 2026-07-31):** `AST → HIR → MIR → LIR → Codegen` — Spec §1.2 / `ARCHITECTURE.md` §0. Soft session below may still say MIR/LIR only (HIR wiring gap).

---

## Done this session

### 1. Fixed-point tuyệt đối (thin Stage-1)

Lệch 1 byte stage2/stage3 trước đây là **codesign Identifier** (tên file), không phải codegen.

| Check | Result |
|-------|--------|
| Unsigned `cmp stage2 stage3` | **PASS** (bit-identical) |
| Signed với `codesign -i virc-bootstrap` | **PASS** |
| Script | [`tools/bootstrap_fixed_point.sh`](../tools/bootstrap_fixed_point.sh) |

```bash
./tools/bootstrap_fixed_point.sh
# → FIXED_POINT_PASS
```

### 2. Stage-1 `include "rel/path.vri";`

- Line-leading include, nested, include-once (cycle-safe).
- Path resolve relative to including file.
- Fast path: file không có `include` → slurp trực tiếp (giữ self-host `virc_stage1.vri`).
- Fixtures: `cg_include_basic`, `cg_include_nested`; smoke `bootstrap/thin_main.vri`.

### 3. Stage-0 threshold

`virc_boot.vri`: small_multi cho `8..256` funcs (trước `<64`); stub/MIR-lower mode chỉ khi `>256`. Cho phép Stage-1 lớn hơn sau khi thêm include helpers.

### 4. Soft `virc` end-to-end under C-VM (2026-07-30 tối)

Soft compiler (`stdlib/vir/compiler/virc.vri` qua `./core/build/vir run`) **chạy trọn** lex → parse → semantic → MIR/LIR → ARM64 → Mach-O cho `tests/bootstrap_codegen/cg_*.vri`.

| Milestone | Status |
|-----------|--------|
| Soft hang tại `parsing...` | **Fixed** — root cause là nested call-in-arg clobber ABI slots trong C-VM `mir_lower.c` (không phải soft parser) |
| Soft SEGV `emit_lir_module_arm64` | **Fixed** — C-VM: tuple destructure shadow, borrow `Q_FREE` on aliases, nested field assign parse/lower; soft: container type annotations on `LirFunc`/`MirFunc` |
| Soft semantic pass 2 SEGV | **Fixed** — `scope_tree.vri`: type `[ScopeNode]`/`[i64]` + capture `vec_push_rt` return |
| Soft binary không in gì | **Fixed** — ARM64 RT stub `MIR_INTR_PRINT` (itoa + `write`) |
| Soft `_start` gọi nhầm hàm đầu | **Fixed** — tìm `main` bằng fat-string name; typed accessor vì bare `vec_get_rt` mất record type |
| Soft `main` treo sau print | **Fixed** — fall-through epilogue khi không có `out` |
| Soft params / locals không khớp tên | **Fixed** — `name_hash_bucket` + `fat_str_eq` (hash nội dung, không pointer) |
| Soft RA (PARAM + X19..X26 + typed rewrite) | **Done** — see REGISTER_ALLOCATION_ARCHITECTURE.md |
| Soft `cg_arith` / `cg_mul` / `cg_var` / `cg_assign` | **PASS** |
| Soft `cg_call` / `cg_multiparam` | **PASS** → `42` |
| Soft `cg_if` / `cg_when` / `cg_let_call_arg` | **Still open** |

**Đo bằng** `tests/bootstrap_codegen/manifest.json` (+ `codesign -s - -f a.out`).  
`run_tests.sh` **không** phải nguồn sự thật (expected stdout lệch nội dung file, ví dụ `test_hello.vri` = `print 42`).

#### C-VM fixes (414-file corpus: không regression; vài test cải thiện 0→42)

| File | Fix |
|------|-----|
| `core/src/mir_lower.c` | Stage args vào fresh vreg trước khi nạp ABI slots 0..n |
| `core/src/ir_lower.c` | Nested field assign lower; array type inference; tuple destructure reuse vreg |
| `core/src/parser.c` | Nested `a.b.c = expr` → `AST_FIELD_ASSIGN` |
| `core/src/borrow_check.c` | Không gắn `is_alloc` cho alias MOVE khi src còn live |

#### Soft compiler / RA fixes

| File | Fix |
|------|-----|
| `lir_codegen.vri` | print stub; `_start`→`main`; `MIR_INTR_PARAM`; save **X19..X26** |
| `lir_regalloc_color.vri` | Typed rewrite; colors → **X19..X26** (callee-saved) |
| `lir_liveness.vri` / `lir_interference.vri` | Typed accessors; `[i64]` matrix |
| `ast_to_mir.vri` | `MIR_INTR_PARAM` DEF; fat-string name hash/eq |
| `virc.vri` | Một emitter theo arch |
| `scope_tree.vri` | Container types + `vec_push_rt` write-back |
| `mir.vri` | `MIR_INTR_PARAM = 100` |

#### Soft next blocker

Control flow (`cg_if` / `cg_when`) and `cg_let_call_arg`. Spill `StackMem` emit still missing.

**Handoff cho AI tiếp:** [`SOFT_PATH_DEBUG_HANDOFF_2026_07_30.md`](SOFT_PATH_DEBUG_HANDOFF_2026_07_30.md) — quy trình viết, test, rollback, playbook debug.

---

## Verify

```bash
# Thin fixed-point
./tools/bootstrap_fixed_point.sh
python3 tools/run_bootstrap_regressions.py \
  --compiler dist/virc-stage1 \
  --compiler dist/virc-stage2 \
  --compiler dist/virc-stage3

# Soft smoke (spot checks; full suite ~5s/test)
./core/build/vir run stdlib/vir/compiler/virc.vri tests/bootstrap_codegen/cg_arith.vri
codesign -s - -f ./a.out && ./a.out   # expect 30\n90
```

Regression thin so sánh **unsigned** outputs giữa các stage; ký bằng `-i virc-bootstrap`.

---

## Soft path / Stage-4 (chưa kill C)

| Item | Status |
|------|--------|
| C-VM `module A::B::C;` smoke | OK (simple) |
| Stdlib include style | **2026-07-30:** slash → **dot-path** (`math.tensor`, `vir.rt.alloc`, …) per spec §3.2 |
| Soft lex → parse → MIR/LIR | **OK** |
| Soft emit Mach-O under C-VM | **OK** (pipeline hoàn tất; print stub sống) |
| Soft correctness (params/arith via RA) | **OK** for straight-line + calls; control-flow next |
| Full MIR/LIR soft → thay `core/build/vir` | **Next** — broaden bootstrap_codegen pass rate |

### Include canonical (spec §3.2)

```vir
include math.tensor;          # → math/tensor.vri
import Tensor from math.tensor;
include vir.rt.alloc;         # → vir/rt/alloc.vri (via stdlib search)
```

Không dùng `include math/tensor;` hay `include "stdlib/vir/...vri"` trên surface thư viện.

### Next milestones

1. Soft `JmpCond` / `if` / `when` + `cg_let_call_arg`.
2. Spill `StackMem` load/store in soft emit; George–Appel coalesce.
3. Pass phần lớn `tests/bootstrap_codegen/manifest.json` qua soft `virc`.
4. Fixed-point **stdlib** stage2/stage3 → Stage-4 kill C.

---

## Key files

| Path | Role |
|------|------|
| `virc_stage1.vri` | Thin Stage-1 + include expander |
| `virc_boot.vri` | Stage-0; small_multi ≤256 |
| `stdlib/vir/compiler/virc.vri` | Soft driver (C-VM host) |
| `stdlib/vir/compiler/lir_codegen.vri` | Soft ARM64 + RT stubs + `_start` |
| `core/src/mir_lower.c` | Nested-call ABI staging (C-VM) |
| `tools/bootstrap_fixed_point.sh` | Unsigned + signed fixed-point gate |
| `tools/run_bootstrap_regressions.py` | Manifest suite (unsigned cmp) |
| `tests/bootstrap_codegen/manifest.json` | Soft/thin expected stdout |
| `tests/bootstrap_codegen/cg_include_*.vri` | Include regressions |
| `bootstrap/thin_main.vri` | Multi-file smoke |
