# Register Allocation Architecture (Vir)

Updated: 2026-07-30

**Language spec** (`vir_language_spec` §16 `register`) chỉ mô tả ánh xạ bit phần cứng — **không** quy định thuật toán RA. Tài liệu này là **spec compiler** cho allocation / coalescing.

Related: [`PIPELINE_MAPPING_TABLES.md`](PIPELINE_MAPPING_TABLES.md), [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md), soft `lir_regalloc*.vri`, boot `regalloc_linear_scan`.

---

## 1. Nguyên tắc

**LIR được làm sạch trước; George–Appel chỉ xử lý coalescing còn lại.**

Không để một thuật toán gánh toàn bộ: clean-up + color + coalesce + spill heuristics trong một pass khổng lồ. Tách trách nhiệm:

| Giai đoạn | Việc | Thuật toán / cơ chế |
|-----------|------|---------------------|
| **A. Làm sạch LIR** | SSA destroy / copy-elim thô, phi→move gọn, dead move, canonical operand | Pass trước RA (MIR opt + `lir_lower` hygiene) |
| **B. Gán thanh ghi** | Live intervals → phys / spill | **Linear Scan** (bootstrap / JIT-ish) **hoặc** **Chaitin–Briggs** (soft LIR quality) |
| **C. Coalescing còn lại** | Gộp copy `mov v_i, v_j` / affinity còn sót sau B | **George–Appel** (iterated register coalescing) trên interference còn lại |
| **D. Rewrite** | Insert spill/reload, rewrite operands | Post-RA rewrite |

George–Appel **không** thay bước B; nó chạy **sau** khi LIR đã sạch và (tuỳ đường) đã có coloring / assignment sơ bộ, chỉ trên phần copy còn lại.

---

## 2. Vì sao tách như vậy

- **Linear Scan / Chaitin–Briggs** mạnh ở *assignment + spill*: quyết định ai vào phys, ai ra stack.
- **George–Appel** mạnh ở *coalescing an toàn*: gộp move mà không phá colorability một cách mù quáng (conservative / iterated).
- LIR bẩn (phi thừa, move chuỗi, operand không chuẩn) làm interference phình → mọi RA đều trông như “chậm / spill nhiều”. Clean trước = đồ thị nhỏ hơn, coalescing dễ chứng minh đúng.

---

## 3. Mapping đường pipeline

| Đường | Hôm nay (live) | Mục tiêu kiến trúc |
|-------|----------------|--------------------|
| Stage-0/1 bootstrap (`virc_boot` Q-IR / body-dump) | Linear Scan (Poletto & Sarkar) hoặc slot cố định (Stage-1) | Giữ Linear Scan cho tốc độ self-host; không bắt buộc GA trên đường này |
| Soft MIR→LIR (`pipeline.vri`) | `lir_liveness` + **Chaitin–Briggs** (`lir_regalloc_color`) | **A → Briggs color → George–Appel coalesce → rewrite** |
| Stage-1 thin (`virc_stage1.vri`) | **Experiment (2026-07-28):** Linear Scan locals → x19–x22 + mini `let a=b;` mov; rest fp | Giữ experiment; nâng Stage-2 trước full GA |

**Không** ghi George–Appel vào language spec. Chỉ soft/compiler docs + module `lir_*`.

### Soft path gap (2026-07-30)

`compile_pipeline` chạy Chaitin–Briggs và nhận `(lf2, phys_map, stack_map)`, nhưng `emit_lir_module_arm64` hiện gọi `emit_lir_arm64_into(..., assigned_phys: -1, ...)` — tức **identity** vreg→phys. Hệ quả quan sát được: nhiều vreg bị emit như `x0` (`add x0, x0, x0` thay vì `add x0, x0, #1`), làm sai `cg_call`/`cg_var` dù live intervals trông hợp lý.

**Next:** rewrite operand sang PhysReg trước emit, hoặc truyền `phys_map` vào emitter và tôn trọng nó trong `resolve_reg`.

---

## 4. Hợp đồng pass (soft LIR)

```
lir_lower
  → lir_clean          # (mục tiêu) dead-move, fold trivial copy, normalize
  → lir_compute_liveness
  → lir_allocate_registers_color   # Chaitin–Briggs simplify/spill/select (đã có)
  → lir_coalesce_appel             # (mục tiêu) George–Appel IRC trên copy edges còn lại
  → lir_rewrite_operands           # spill slots + phys ids
  → lir_codegen
```

**Invariant**

1. Sau `lir_clean`: không còn phi MIR; move thừa đã DCE tối đa *trước* đồ thị.
2. Briggs chỉ tô màu / spill — **không** cố coalesce aggressive trong cùng vòng (tránh trộn heuristic).
3. George–Appel chỉ coalesce khi an toàn (conservative) hoặc theo vòng IRC chuẩn; fail → giữ move.
4. Bootstrap Q-IR được phép **bỏ qua** bước 3 (GA) cho đến khi soft path e2e xanh.

---

## 5. Tham chiếu thuật toán

| Tên | Vai trò trong Vir |
|-----|-------------------|
| Poletto & Sarkar 1999 (Linear Scan) | Spec lịch sử + boot / nhanh |
| Chaitin / Briggs (graph coloring) | Soft LIR assignment (`lir_regalloc_color`) |
| George & Appel (iterated register coalescing) | **Mục tiêu** bước coalescing sau clean + color |
| Stage-1 fp slots / Linear Scan experiment | **✅** thin path: first 4 locals → x19–x22; `let a=b;` → mov; `_rt_print` preserves x19–x22; suite 25/25 |
| Soft e2e dùng full A→B→C→D | **TODO** (sau self-host ổn) |

---

## 6. Trạng thái triển khai

| Hạng mục | Status |
|----------|--------|
| Spec kiến trúc (doc này) | **✅** 2026-07-28 |
| Linear Scan (boot / `lir_regalloc.vri`) | Có |
| Chaitin–Briggs (`lir_regalloc_color.vri`) | Có (soft) |
| `lir_clean` tách rõ | **TODO** (logic rải trong mir_opt / lower) |
| `lir_coalesce_appel` | **TODO** |
| Stage-1 Linear Scan experiment (`virc_stage1`) | **✅** x19–x22 + mini `let a=b;` mov; `_rt_print` saves x19–x22; suite 25/25 |
| Soft e2e dùng full A→B→C→D | **TODO** (sau self-host ổn) |

---

## 7. Anti-goals

- Không thay Linear Scan bootstrap bằng full IRC trước khi self-host ổn.
- Không “George–Appel only” từ LIR bẩn.
- Không coalescing trong cùng pass với simplify Briggs nếu làm đục invariant test.
- Không nhầm keyword ngôn ngữ `register` (§16) với register allocation.
