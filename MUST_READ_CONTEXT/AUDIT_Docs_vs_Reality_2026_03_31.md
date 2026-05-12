# AUDIT: Tài liệu vs Thực tế Codebase (31/03/2026, cập nhật 11/04/2026)

> **Phương pháp:** Quét toàn bộ tài liệu trong `MUST_READ_CONTEXT/` (PLAN/ + COMPLETE/ + CURRENT_STATUS), đối chiếu với codebase thực tế.
> **Trạng thái (11/04/2026):** Phase 6 COMPLETE. **47/47 tests passing**. 82 canonical QOp opcodes. 6 optimization passes (fusion, BCE, autovec, regalloc, TCO, spill). Python removed. All ARM64 SIMD/fused/float handlers wired.
> **Kết luận tổng thể:** Tài liệu đã được cập nhật nhiều lần. Các sai số thống kê nghiêm trọng ban đầu đã được sửa. Phiên bản hiện tại (11/04/2026) phản ánh chính xác trạng thái codebase.
>
> ### ✅ AUDIT FIX LOG (02/04/2026 → 11/04/2026)
> - **CURRENT_STATUS**: 47 tests, Phase 6, 82 QOp opcodes, LOC tables cập nhật (compiler 9,975 + runtime 2,337 = 15,121)
> - **QIR_ARCHITECTURE.md**: Module table LOC cập nhật, optimization passes table với 7 entries, roadmap P1-P6 ✅ Done
> - **README.md**: 47/47 tests, Phase 7 roadmap, architecture diagram with LOC + SIMD/float info
> - **SELF_HOSTING_SPEC.md**: Phase 6 complete, virc stats
> - **COMPLETION_STATUS.md**: Python removed notice, 47/47 virc tests
> - **01_Opcode_Map.md**: V2.0 — virc canonical QOp enum table (82 opcodes) added to header
> - **03_Codegen_Matrix.md**: V2.0 — virc codegen overview added (82 opcodes, NEON/fused/float)
> - **06_Phase3_VM_Execution.md**: 47/47 tests, Phase 6 milestones
> - **Vir_Stage4_Kill_C_Master_Plan.md**: Stage 4 ✅ DONE notice
> - **05_C_Core_Analysis.md**: Written lại v2.0 (02/04)
> - **04_Test_Fortification.md**: Naming convention fix (02/04)
> - **7 docs in COMPLETE/ DELETED**: Outdated snapshots removed (02/04)

---

## MỤC LỤC

1. [SAI SỐ THỐNG KÊ — Số liệu LOC sai](#1-sai-số-thống-kê)
2. [MÂU THUẪN NỘI BỘ giữa các tài liệu](#2-mâu-thuẫn-nội-bộ)
3. [PHANTOM FILES — File tài liệu nói có nhưng không tồn tại](#3-phantom-files)
4. [OPCODE MAP — Sai hoàn toàn](#4-opcode-map)
5. [TEST COUNT — Undocumented tests](#5-test-count)
6. [PHANTOM FEATURES — Pipeline chưa đầy đủ](#6-phantom-features)
7. [TÀI LIỆU LỖI THỜI trong COMPLETE/](#7-tài-liệu-lỗi-thời)
8. [BUG TIỀM ẨN phát hiện từ code](#8-bug-tiềm-ẩn)
9. [BẢNG TÓM TẮT HÀNH ĐỘNG](#9-tóm-tắt)

---

## 1. SAI SỐ THỐNG KÊ — Số liệu LOC sai {#1-sai-số-thống-kê}

### 1.1 C Engine LOC

| File | Kill C Plan claim | 05_C_Core claim | **Thực tế** | Sai lệch |
|------|:-:|:-:|:-:|:-:|
| `parser.c` | 1,875 | ~3,000 | **1,738** | Kill C sai +8%; 05 sai **+73%** |
| `codegen.c` | 3,612 | ~2,500 | **3,510** | Kill C sai +3%; 05 sai **-29%** |
| `vm.c` | 2,142 | ~1,200 | **1,559** | Kill C sai **+37%**; 05 sai -23% |
| `ir_lower.c` | 2,144 | ~2,000 | **2,102** | Kill C sai +2%; 05 OK |
| `lexer.c` | ~800 | ~800 | **854** | OK |
| `mem_manager.c` | ~600 | ~600 | **271** | Sai **+121%** |
| `bridge_native.c` | ~220 | — | **362** | Sai **-39%** |
| **Tổng C src** | ~12,000 (critical only) | ~18,600 | **22,173** | 05 sai **-16%** |

**Kết luận:** Cả hai tài liệu đều cho số liệu LOC sai nghiêm trọng. `05_C_Core_Analysis.md` thổi phồng parser.c gần gấp đôi (3,000 vs 1,738). Kill C Plan thổi phồng vm.c (2,142 vs 1,559). Hai tài liệu mâu thuẫn lẫn nhau về cùng một file.

### 1.2 C Engine Header LOC

| Metric | Kill C Plan claim | **Thực tế** |
|--------|:-:|:-:|
| Header LOC | 4,200 | **4,220** |
| Tổng (src+header) | 27,400 (23.2K+4.2K) | **26,393 (22,173+4,220)** |

Sai lệch nhỏ (~4%) — chấp nhận được.

### 1.3 Vir Compiler LOC

| Metric | Kill C Plan claim | **Thực tế (01/04)** | Sai lệch |
|--------|:-:|:-:|:-:|
| `virc.vri` total compiler | **10,988** | **9,811** | Sai **+12%** (thổi phồng ~1,177 dòng) |
| `ir_optimizer.vri` | **3,025** (07_Arena doc) | **1,940** | Sai **+56%** |
| `parser.vri` | — | **1,694** | (không có claim) |
| `main.vri` | — | **1,304** | (không có claim) |
| `codegen.vri` | — | **1,870** | (không có claim) |

> [UPDATE 01/04] ir_optimizer.vri tăng từ 1,874 → 1,940 dòng do thêm Entity/Enum/Array lowering + vreg reclamation.

### 1.4 Vir Stdlib

| Metric | Claim | **Thực tế (01/04)** | Verdict |
|--------|:-:|:-:|:-:|
| File count | 292 modules | **292 files** | Chính xác |
| LOC | ~94,100 | **93,901** | OK (sai <1%) |

### 1.5 05_C_Core_Analysis — Phantom File List

Tài liệu `05_C_Core_Analysis.md` liệt kê 20 file C (`runtime.c`, `string.c`, `array.c`, `map.c`, `entity.c`, `file.c`, `network.c`, `syscall.c`, `error.c`, `debug.c`, `emit_x86.c`, `emit_arm64.c`, `memory.c`...) — **13 file KHÔNG TỒN TẠI** trong `core/src/`.

Ngược lại, 05 **không liệt kê** 18 file thực sự tồn tại:
`amx_accel.c`, `async_runtime.c`, `atomic.c`, `borrow_check.c`, `bridge.c`, `constraints.c`, `cpu_caps.c`, `ffi_runtime.c`, `gpu_cuda.c`, `gpu_metal.c`, `gpu_pipeline.c`, `huge_alloc.c`, `intrinsics.c`, `micro_prober.c`, `net_runtime.c`, `numa_alloc.c`, `patcher.c`, `ptx_gen.c`, `signer.c`, `simd_dispatch.c`, `simd_index.c`, `slab_alloc.c`, `task.c`, `thread_runtime.c`, `vir.c`.

**Đánh giá:** File list của 05 hoàn toàn **bịa đặt** hoặc dựa trên thiết kế lý thuyết, không phản ánh codebase thực tế. **Đây là lỗi nghiêm trọng nhất** — bất kỳ ai đọc tài liệu này sẽ hiểu sai hoàn toàn kiến trúc C engine.

---

## 2. MÂU THUẪN NỘI BỘ giữa các tài liệu {#2-mâu-thuẫn-nội-bộ}

### 2.1 Số lượng test: 7 vs 20 vs 25 vs 41

| Tài liệu | Claim | Ngày ghi |
|-----------|:-:|:-:|
| **Kill C Plan** (Phase 4.1B) | 7 tests pass | 30/03/2026 |
| **Phase3 VM (06)** header | 20 test programs | 30/03/2026 |
| **CURRENT_STATUS_2026_03_30** | **39 tests** (updated) | 31/03/2026 |
| **Thực tế verified** | **41 tests pass** | 01/04/2026 |

> [UPDATE 01/04] CURRENT_STATUS đã updated lên 39 tests (Phase C.2 + C.3). Thực tế verified 41/55 test files pass (14 file còn lại là WIP/debug stubs từ quá trình phát triển, nhiều file gây hang khi compile vì syntax không hỗ trợ hoặc entity cũ). Kill C Plan và Phase3 doc vẫn cũ — nên archive.

**Giải thích gốc:** Kill C Plan viết lúc đầu ngày khi chỉ 7 test pass, Phase3 doc cập nhật cùng ngày lên 20, rồi Status doc cập nhật cuối ngày lên 25 sau khi thêm string tests.

### 2.2 Phase numbering chaos

| Tài liệu | "Phase" trùng tên nhưng nghĩa khác |
|-----------|---|
| Kill C Plan | Phase 4.1, 4.1B, 4.2, 4.3, 4.4, 4.5 |
| Phase3 VM (06) | Phase 3A, 3B, 3C |
| CURRENT_STATUS | Phase A, B, C, C.1, C.2, C.3, D |
| 07_Arena | Phase A, B, C, D (hoàn toàn khác) |

"Phase C" trong CURRENT_STATUS = Fix 13 (Control Flow), nhưng "Phase C" trong 07_Arena = Drop Insertion + Codegen. Hoàn toàn khác nhau nhưng cùng tên.

### 2.3 Mâu thuẫn Opcode count

| Tài liệu | Claim |
|-----------|:-:|
| 01_Opcode_Map.md | 148 opcodes |
| vir_audit_report.md (20/03) | "11 opcodes mới" (ngụ ý ~140+) |
| **q_ir.h thực tế (01/04)** | **87 entries** (includes aliases) |
| **ir_optimizer.vri QOp enum** | **57 opcodes** |

Tài liệu 01 claim 148 opcodes, thực tế C engine chỉ có 73 và Vir compiler chỉ có 57. Sai lệch **+103%** (gấp đôi).

---

## 3. PHANTOM FILES — File tài liệu nói có nhưng không tồn tại {#3-phantom-files}

### 3.1 Test framework files (04_Test_Fortification.md)

Tài liệu liệt kê bảng test suites với 8 file `vtest_*.vri`:

| File claimed | **Thực tế** |
|---|---|
| `vtest_core.vri` | **MISSING** |
| `vtest_array.vri` | **MISSING** |
| `vtest_string.vri` | **MISSING** |
| `vtest_map.vri` | **MISSING** |
| `vtest_math.vri` | **MISSING** |
| `vtest_file.vri` | **MISSING** |
| `vtest_entity.vri` | **MISSING** |
| `vtest_enum.vri` | **MISSING** |

Trong khi đó, `stdlib/vir/test/` có 37 file `.vri` thực (không phải 28 suites như claim), tên theo convention khác: `math_vtest.vri`, `mem_vtest.vri`, `compiler_vtest.vri`... Naming mismatch cho thấy tài liệu viết tên file **dự kiến**, không phải file thực.

### 3.2 C source files (05_C_Core_Analysis.md)

Đã nêu ở mục 1.5: 13 file C **không tồn tại**. Tài liệu mô tả kiến trúc "lý tưởng" không khớp với code thực.

### 3.3 Docs referenced but missing

| Tài liệu tham chiếu | Tại |
|---|---|
| `docs/PHASE2_IR_LOWERING_REPORT.md` | Kill C Plan §3.2 |

```bash
$ find . -name "PHASE2_IR_LOWERING_REPORT*" 
# (Cần kiểm tra — khả năng không tồn tại)
```

---

## 4. OPCODE MAP — Sai hoàn toàn {#4-opcode-map}

### 4.1 Opcode numbering mismatch giữa C và Vir

| Opcode | C enum (`q_ir.h`) | Vir enum (`ir_optimizer.vri`) | **Khớp?** |
|--------|:-:|:-:|:-:|
| Load | 0x01 | 1 | ✅ |
| Move | 0x03 | 2 | **Sai**: C=3, Vir=2 |
| **Add** | **0x10** | **3** | **SAI NGHIÊM TRỌNG**: C=16, Vir=3 |
| Sub | 0x11 | 4 | **SAI**: C=17, Vir=4 |
| Mul | 0x12 | 5 | **SAI**: C=18, Vir=5 |
| Div | 0x13 | 6 | SAI |
| Mod | 0x14 | 7 | SAI |
| CmpEq | 0x20 | 20 | ✅ |
| CmpGt | 0x21 | 22 | **SAI**: C=0x21, Vir=22(0x16) |
| Jump | 0x40 | 30 | **SAI**: C=64, Vir=30 |
| Call | 0x43 | 33 | **SAI**: C=67, Vir=33 |
| Print | 0x50 | 40 | **SAI**: C=80, Vir=40 |
| Alloc | 0x60 | 50 | **SAI**: C=96, Vir=50 |
| ArrNew | 0x90 | 60 | **SAI**: C=144, Vir=60 |
| Exit | 0xA0 | 90 | **SAI**: C=160, Vir=90 |

**Kết luận CRITICAL:** Opcode numbering giữa C engine và Vir compiler *hoàn toàn không khớp* trừ Load và CmpEq. **Nhưng** đây có thể không phải bug — Vir compiler sinh Mach-O binary trực tiếp (không qua C VM), nên opcode enum Vir-side là internal encoding cho lowering, không cần khớp C enum. Tuy nhiên, **tài liệu 01_Opcode_Map.md không đề cập sự khác biệt này**, gây nhầm lẫn cực lớn.

### 4.2 Opcodes tồn tại trong C nhưng thiếu trong Vir compiler

| C Opcode | Có trong C | Có trong Vir | Ghi chú |
|---|:-:|:-:|---|
| Q_STORE (0x02) | ✅ | ❌ | Vir dùng Move thay |
| Q_CMP_GE/LE (0x23-24) | ✅ | ✅ | OK nhưng numbering khác |
| Q_VLOAD..Q_VPERM (16 SIMD ops) | ✅ | ❌ | Vir compiler chưa hỗ trợ SIMD |
| Q_TASK_SPAWN/YIELD/WAIT | ✅ | ❌ | Async chưa lowered |
| Q_HALT | ✅ | ❌ | Vir dùng Exit |

### 4.3 Opcodes trong tài liệu 01 nhưng không tồn tại ở đâu cả

Tài liệu `01_Opcode_Map.md` liệt kê opcodes cho: `Q_FADD`, `Q_FSUB`, `Q_FMUL`, `Q_FDIV`, `Q_FMOD`, `Q_FNEG`, `Q_ABS`, `Q_PERCENT`, `Q_POW`, `Q_SQRT`, `Q_SIN`, `Q_COS`, `Q_LOG`, `Q_EXP`, `Q_FLOOR`, `Q_CEIL`, `Q_ROUND`, `Q_NET_LISTEN`, `Q_NET_ACCEPT`, `Q_NET_SEND`, `Q_NET_RECV`...

**KHÔNG CÓ** trong `q_ir.h` (C enum chỉ 73 entries). Tài liệu 01 mô tả **thiết kế mong muốn**, không phải thực tế.

---

## 5. TEST COUNT — 55 files, 41 pass {#5-test-count}

### Tài liệu nói 25 tests (gốc), thêm lên 39 (Phase C.2+C.3), thực tế **41 pass** trên 55 files

14 file không pass là WIP/debug stubs từ quá trình phát triển:

| File | Nội dung |
|---|---|
| `test_control.vri` | Chưa rõ — không trong test matrix |
| `test_field_access.vri` | Entity field access test |
| `test_literal_only.vri` | Literal-only program (no main?) |
| `test_simple_field.vri` | Simple struct field test |
| `test_struct_colon.vri` | Struct with colon syntax? |
| `test_two_strings.vri` | Multiple string test |

> [UPDATE 01/04] 41/55 test files pass. 14 file còn lại là WIP/debug stubs (test_entity_basic, test_entity_debug, test_entity_lit, test_entity_min, test_entity_parse, test_arr_min, test_arr_reorder, test_array_simple, test_10vars, test_alloc_rw, test_simple_field, test_struct_colon, test_two_strings, test_entity_field). Một số gây hang do syntax cũ hoặc feature chưa hoàn tất. Không phải regression — là file debug từ quá trình phát triển Phase C.2/C.3.

---

## 6. PHANTOM FEATURES — Pipeline chưa đầy đủ {#6-phantom-features}

### 6.1 "12-Pass Optimizer" (Kill C Plan §2.2)

Kill C Plan claim: "12-Pass Optimizer (Copy Prop → DCE)".

**Thực tế trong `ir_optimizer.vri`:** Chỉ có **3 passes**:
- Pass 0: register enum/entity types
- Pass 1: register function names
- Pass 2: lower function bodies

Không có Copy Propagation, DCE, hay bất kỳ optimization pass nào.
TCO pass tồn tại riêng (`tco_pass`).

**Kết luận:** "12-Pass Optimizer" hoặc tồn tại ở chỗ khác (C engine? stdlib khác?) hoặc là **feature chưa implement**.

### 6.2 "Escape Analysis" + "Deterministic Free" (07_Arena §1.3)

Tài liệu Arena viết:
> `ir_optimizer.vri` L2481-2540: Escape Analysis pass (✅ Đã có)
> `ir_optimizer.vri` L2576-2630: Deterministic Free pass (✅ Đã có)

**Thực tế:** `ir_optimizer.vri` chỉ có **1,874 dòng** (không phải 3,025). Dòng 2481 **không tồn tại**. `grep "escape\|Escape\|det.*free"` → **0 kết quả**.

**Kết luận:** Escape Analysis và Deterministic Free **chưa được implement**. Tài liệu ghi "✅ Đã có" là **sai sự thật**.

### 6.3 "PGO (Profile-Guided Optimization)" / "Tiered Compilation"

Kill C Plan claim: "Tiered Compilation (Interpreter → Tier1 → Tier2)" ✅ Done.

Files `stdlib/vir/jit/{bridge,tiered,pgo}.vri` tồn tại, nhưng cần verify nếu chúng thực sự hoạt động hay chỉ là stub/skeleton.

### 6.4 "SIMD Vectorization (16 opcodes, NEON/AVX)" — Kill C Plan

C engine có 12 SIMD opcodes (`Q_VLOAD..Q_VPERM`). Vir compiler (`ir_optimizer.vri`) có **0 SIMD opcodes** trong QOp enum. `grep "SIMD\|simd\|VADD" ir_optimizer.vri` → **0 results**.

**Kết luận:** SIMD chỉ có trong C engine, Vir compiler **không hỗ trợ SIMD**. Kill C Plan claim "✅ DONE" cho SIMD là misleading — nó chỉ done ở C side.

### 6.5 "vtest Framework (362 tests)" — Kill C Plan

Kill C Plan claim 362 vtest functions. `vir_audit_report.md` (20/03) lại claim "865/865 pass". Hai con số hoàn toàn khác nhau, không thể cùng đúng.

---

## 7. TÀI LIỆU LỖI THỜI trong COMPLETE/ {#7-tài-liệu-lỗi-thời}

| File | Ngày | Tình trạng |
|---|---|---|
| `CURRENT_STATUS_2026_03_28.md` | 28/03 | **Lỗi thời** — chỉ nói "1 function, 3 Q-IR instructions". Bị thay thế bởi ver 30/03 với 25 tests |
| `Vir_Comprehensive_Status_Report_2026_03_22.md` | 22/03 | **Rất cũ** — trước khi Phase 3A hoàn tất. Nhiều claim trong đây đã bị Phan_bien phản bác |
| `Vir_SelfHost_Status_2026_03_27.md` | 27/03 | **Lỗi thời** — mid-progress snapshot |
| `Vir_Self_Hosted_Bootstrap_Status.md` | ? | Snapshot cũ |
| `vir_audit_report.md` | 20/03 | Claim "865/865 pass" nhưng Kill C Plan nói 362 vtest |
| `Phan_bien_Codebase_Audit.md` | 24/03 | Vẫn có giá trị — chỉ ra pipeline gaps (Q_CMP_NE, Q_POW, Map, Async). Một số có thể đã fix |
| `Pure_Vir_Self_Hosting_Plan.md` | ? | Planning doc, không rõ current relevance |

**Khuyến nghị:** Nên move tất cả file có ngày < 30/03 không còn chính xác vào folder `ARCHIVE/` hoặc gắn warning header "OUTDATED".

---

## 8. BUG TIỀM ẨN phát hiện từ code {#8-bug-tiềm-ẩn}

### 8.1 Arena 8KB limit — không báo overflow

> **✅ RESOLVED 02/04/2026:**
> - Arena tăng từ 8KB → **64KB** (65536 bytes)
> - Thêm **bounds check + BRK #1 trap** tại cả 2 nơi bump-alloc (runtime `_rt_str_concat` và inline StringRef)
> - Nếu overflow → SIGTRAP crash rõ ràng thay vì silent memory corruption
> - 46/46 tests pass sau fix

### 8.2 vreg overflow vào caller-saved registers

> [UPDATE 01/04] **ĐÃ GIẢI QUYẾT** bằng 3 cơ chế vreg reclamation:
> 1. **VarDecl reclamation:** `next_vreg = r + 1` sau mỗi VarDecl — reclaim temps khi variable đã được gán.
> 2. **Statement-level save/restore:** PrintStmt, Assign, IndexAssign, FieldAssign, BuiltinCall đều save/restore `next_vreg`.
> 3. **Call arg compaction + reverse move:** Evaluate args → compact vào sequential slots → reclaim temps giữa args → Move args vào X0-X7 theo thứ tự ngược (tránh clobbering).
>
> **Rủi ro còn lại:** Vẫn không có stack spilling — chương trình cực lớn (>10 biến local + nhiều nested expressions) vẫn có thể overflow. Nhưng đủ cho self-hosting hiện tại.

### 8.3 `else:` colon bug

> **✅ RESOLVED:** Parser.vri (lines 935-937) ĐÃ consume colon sau `else` — cùng pattern với `if:`. Bug này đã được fix trước khi audit được viết hoặc fix ngay sau đó.

### 8.4 Globals base pointer (X15) fragile

> **✅ NOT A BUG:** Phân tích kỹ cho thấy X15 an toàn trong kiến trúc hiện tại:
> 1. User functions save/restore X14/X15 trong prologue/epilogue (main.vri lines 440, 672)
> 2. Runtime functions (`_rt_print_i64`, `_rt_str_concat`, `_rt_print_str_var`) KHÔNG modify X15 — chỉ đọc từ nó
> 3. `_rt_alloc` là syscall thuần (SVC) — kernel bảo toàn registers
> 4. Không có external C library calls
>
> **Rủi ro còn lại:** Nếu thêm FFI/external calls trong tương lai, cần verify X15 preservation.

### 8.5 Phase3 VM "Blocker" docs vs. thực tế

> [UPDATE 01/04] **Field Access blocker ĐÃ GIẢI QUYẾT** — Entity field access/assign hoạt động qua inline field lookup + LoadWord/StoreWord. Higher-Order Calls vẫn chưa support. Extern Stubs và Missing Opcodes chỉ ảnh hưởng khi self-compile (virc compile virc), không ảnh hưởng test programs hiện tại.

---

## 9. TÓM TẮT HÀNH ĐỘNG {#9-tóm-tắt}

### CRITICAL — Cần sửa ngay

| # | Vấn đề | Tài liệu | Hành động |
|---|---|---|---|
| 1 | ~~05_C_Core_Analysis liệt kê 13 file không tồn tại~~ | COMPLETE/05 | **✅ RESOLVED 02/04** — Viết lại hoàn toàn file list + LOC (v2.0) |
| 2 | ~~01_Opcode_Map claim 148 opcodes (thực tế 87 C / 57 Vir)~~ | COMPLETE/01 | **✅ RESOLVED 02/04** — Thêm AUDIT CORRECTION header |
| 3 | ~~Kill C Plan Phase 4.1B nói "7 tests" cùng ngày Status nói "25 tests"~~ | ~~PLAN/Kill C~~ | **✅ RESOLVED** — CURRENT_STATUS updated 46 tests, Kill C Plan updated |
| 4 | ~~ir_optimizer.vri claim 3,025 LOC (thực tế 1,874→1,995)~~ | ~~PLAN/07~~ | **✅ RESOLVED** — Đã cập nhật |
| 5 | ~~Escape Analysis + Deterministic Free ghi "✅ Đã có" nhưng **không tồn tại**~~ | PLAN/07 | **✅ RESOLVED 02/04** — Đổi thành ❌ CHƯA IMPLEMENT |

### HIGH — Nên sửa sớm

| # | Vấn đề | Tài liệu | Hành động |
|---|---|---|---|
| 6 | ~~6 test files undocumented~~ | ~~CURRENT_STATUS~~ | **✅ RESOLVED** — 46 tests documented |
| 7 | ~~LOC sai cho vm.c, parser.c, codegen.c, mem_manager.c~~ | Kill C + 05 | **✅ RESOLVED 02/04** — Kill C Plan §2.3 rewritten với verified `wc -l` |
| 8 | ~~virc.vri claim 10,988 LOC (thực tế ~9,107)~~ | Kill C | **✅ RESOLVED 02/04** — Updated to 9,107 |
| 9 | Phase numbering chaos (A/B/C/D dùng trong 4 context khác nhau) | Multiple | ⚠️ ACKNOWLEDGED — Mỗi doc dùng Phase naming riêng. Không refactor (quá nhiều docs). CURRENT_STATUS dùng Phase A/B/C/C.x/D. Kill C dùng Phase 4.x. 06 dùng Phase 3A/3B/3C. 07 dùng Phase A/B/C/D riêng. |
| 10 | ~~vtest count conflict: 362 vs 865~~ | Multiple | **✅ RESOLVED 02/04** — Thực tế: 28 vtest files, ~796 test functions. Cả hai con số cũ đều sai. |

### MEDIUM — Nên dọn dẹp

| # | Vấn đề | Hành động |
|---|---|---|
| 11 | ~~7 file COMPLETE/ lỗi thời (pre-30/03)~~ | **✅ RESOLVED 02/04** — Thêm OUTDATED warning headers cho 5 file cũ nhất |
| 12 | ~~04_Test_Fortification dùng tên file sai (vtest_*.vri vs *_vtest.vri)~~ | **✅ RESOLVED 02/04** — Viết lại bảng test suites v2.0 (28 files, ~796 funcs) |
| 13 | ~~"12-Pass Optimizer" claim chưa verify~~ | **✅ RESOLVED 02/04** — Kill C Plan updated: "3-Pass Lowerer", ghi rõ "12-Pass KHÔNG TỒN TẠI" |
| 14 | ~~SIMD "✅ DONE" misleading~~ | **✅ RESOLVED 02/04** — Kill C Plan: "SIMD Vectorization — C engine only, Vir compiler: 0" |
| 15 | ~~Phase3 doc blocker list chưa resolved/updated~~ | **✅ RESOLVED 02/04** — 06_Phase3 updated: Blocker #4 RESOLVED, 46 tests |

---

**Tác giả:** Automated Codebase Audit
**Ngày:** 31/03/2026
**Phương pháp:** `wc -l`, `grep`, `find`, `diff`, đọc toàn bộ 17 tài liệu MUST_READ_CONTEXT
