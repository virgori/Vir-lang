# PHASE D (Post-C): Hiệu năng cấp Compiler thông minh

> Ngày: 28/03/2026  
> Bối cảnh: Sau khi hoàn tất Phase C (core correctness + self-host stability), bước tiếp theo là tối ưu hiệu năng theo hướng compiler hiện đại.

---

## 1) Mục tiêu chiến lược

1. Đạt tăng tốc thực tế trên workload thật (không chỉ micro-benchmark tổng hợp).
2. Giảm overhead call/branch/cache-miss ở toàn pipeline Vir compiler + stdlib nóng.
3. Thiết lập kiến trúc tối ưu mở rộng dần: từ deterministic passes (LTO/Peephole) → profile-driven (PGO) → search/AI (Superopt/ML Scheduling).

---

## 2) Thứ tự ưu tiên thực thi (đề xuất chính thức)

### Ưu tiên P0 — **LTO + Peephole (bắt buộc làm trước)**
Lý do:
- ROI cao nhất/đơn vị effort.
- Ít rủi ro nhất so với ML scheduling.
- Tạo nền IR/machine pattern ổn định cho PGO và Superopt.

### Ưu tiên P0b — **RA soft: LIR clean → Briggs → George–Appel coalesce**
Song song / ngay sau self-host ổn định trên soft LIR:
- Không thay Linear Scan bootstrap bằng IRC đầy đủ một phát.
- Clean LIR trước; Chaitin–Briggs gán/spill; George–Appel chỉ coalescing còn lại.
- Spec: [`MUST_READ_CONTEXT/REGISTER_ALLOCATION_ARCHITECTURE.md`](../REGISTER_ALLOCATION_ARCHITECTURE.md).

### Ưu tiên P1 — **PGO (instrument + feedback compile)**
- Tập trung vào hot path thực tế của `virc.vri`, `ir_optimizer.vri`, `codegen.vri`, runtime string/vec/io.

### Ưu tiên P2 — **Superoptimization dạng template (peephole mở rộng)**
- Offline search + whitelist pattern đã chứng minh đúng nghĩa.

### Ưu tiên P3 — **ML-based Scheduling (thử nghiệm có kiểm soát)**
- Không đưa vào default pipeline trước khi có metric ổn định và reproducible.

---

## 3) Kế hoạch triển khai theo wave

## Wave D1 — LTO Infrastructure (2-3 tuần)

> **[AUDIT CONFIRM — 2026-04-02]** Audit P-06 false positive confirmed: `_licm` (optimizer.py:545) và `_cse` (optimizer.py:335) đã fully implemented, không phải stubs. Wave D1/D2 **unblocked** — không có blocker từ optimizer passes.

### Deliverables
- IR merger xuyên module (`QModule` hợp nhất toàn binary).
- Symbol/link graph cho function visibility.
- Pass inlining xuyên file (heuristic ban đầu):
  - inline tiny leaf function,
  - inline hot callsite từ profile sơ bộ,
  - giới hạn code size growth theo budget.
- Dead global/function elimination sau inline.

### Kỹ thuật
- **LTO chiến lược (không LLVM):** Vì Vir kiểm soát toàn bộ pipeline từ đầu đến cuối, LTO = Merge các file .vri thành một IR khổng lồ (single QModule) trước khi emit Mach-O. Đây là lợi thế cốt lõi so với ngôn ngữ phụ thuộc LLVM.
- Mở rộng `lower_program` và linker stage để giữ metadata callgraph.
- Thêm pass:
  - `build_call_graph`
  - `cross_module_inline`
  - `global_dce`
- Mặc định bật bằng cờ: `--lto=on` (có `off` để đối chiếu).

### Exit Criteria
- Build thành công toàn bộ vir compiler chain với LTO on/off.
- Số call BL/RET giảm đáng kể ở module nóng.
- Không regress correctness (snapshot output/binary behavior equivalence).

---

## Wave D2 — Peephole Optimizer v2 (2 tuần)

### Deliverables
- Rule engine cho machine-level peephole theo target (`arm64` trước).
- Rule set tối thiểu:
  - strength reduction (mul/div hằng số),
  - redundant mov/load-store elimination,
  - compare+branch canonicalization,
  - addressing mode fusion.
- Validation harness cho từng rule: SMT-like equivalence test hoặc exhaustive test miền nhỏ.

### Kỹ thuật
- Tách pipeline:
  1) pre-regalloc peephole (IR-level),
  2) post-regalloc peephole (machine-level).
- Rule format có version + feature flag (`--peephole=level1|level2`).

### Exit Criteria
- >10 rule hoạt động ổn định, có test cho từng rule.
- Giảm instruction count ở benchmark compiler workloads.

---

## Wave D3 — PGO đầy đủ (3 tuần)

### Deliverables
- Chế độ instrumentation build: `--pgo=gen`.
- Runtime profile collector (counter cho basic blocks + edge/hot callsites).
- Profile merge tool + optimize build: `--pgo=use profile.data`.
- Layout optimization:
  - hot-cold splitting,
  - function order for icache,
  - branch hinting.

### Kỹ thuật
- Thu profile từ 3 nhóm workload:
  1) self-host compile,
  2) stdlib compile,
  3) representative app compile.
- Cho phép stale-profile guard (nếu mismatch version/hash → fallback no-PGO).

### Exit Criteria
- Có vòng compile 2-pass hoàn chỉnh (gen/use).
- Cải thiện wall-time ổn định qua >= 20 runs, độ lệch chuẩn được báo cáo.

---

## Wave D4 — Superoptimization (template-driven) (2-4 tuần)

### Deliverables
- Offline superopt search cho block ngắn (2-6 instructions).
- Pattern DB theo kiến trúc (bản đầu: arm64).
- Verified replacement pipeline (chỉ apply template đã chứng minh).

### Kỹ thuật
- Không brute-force online trong compiler path.
- Sinh template offline + đóng gói DB immutable theo version.

### Exit Criteria
- Có ít nhất 20 template verified và pass regression.
- Không làm tăng compile-time quá ngưỡng cho phép.

---

## Wave D5 — ML Scheduling (experimental gate) (3-6 tuần, tùy kết quả)

### Deliverables
- Feature extraction cho instruction DAG.
- Inference model nhỏ (latency-sensitive) cho block scheduling đề xuất.
- A/B gate:
  - default: heuristic scheduler,
  - optional: ML scheduler (`--sched=ml`).

### Kỹ thuật
- Chỉ áp dụng lên hot blocks do PGO chỉ định.
- Có fallback deterministic 100% khi model confidence thấp.

### Exit Criteria
- Chỉ promote nếu thắng heuristic ở workload thực với sai số thấp và ổn định.

---

## 4) KPI kỹ thuật (đo bắt buộc)

- Build time self-host (`virc -> virc`): median/p95.
- Runtime binary throughput trên benchmark chuẩn.
- Instruction count / branch mispredict proxy / icache miss proxy.
- Code size delta (%).
- Compile-time overhead của mỗi pass.

Mục tiêu ban đầu (gợi ý):
- D1+D2: giảm 8-15% thời gian compile thực tế.
- D3 (PGO): thêm 5-12%.
- D4: thêm 2-8% (tùy workload).
- D5: chỉ giữ nếu thắng ổn định >3% trên hot workloads.

---

## 5) Rủi ro & kiểm soát

- **Code size bloat do LTO/inlining** → đặt budget + rollback heuristic.
- **Rule peephole sai ngữ nghĩa** → bắt buộc rule-level equivalence tests.
- **PGO overfit workload** → dùng tập profile đa dạng, có fallback guard.
- **ML không ổn định** → luôn có deterministic fallback, không default-on sớm.

---

## 6) Đề xuất ra quyết định ngay

1. Chốt roadmap ưu tiên: **D1 (LTO) + D2 (Peephole) trước**.
2. Đóng băng giao diện pass manager trước khi triển khai PGO.
3. Chuẩn hóa benchmark harness để mọi wave đo bằng cùng methodology.

---

## 7) Mapping theo yêu cầu mô tả

- PGO → Wave D3
- Superoptimization → Wave D4
- ML-based scheduling → Wave D5
- LTO → Wave D1
- Khuyến nghị “LTO + Peephole” → D1 + D2 là đường đi mặc định
