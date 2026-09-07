# BÁO CÁO NGHIỆM THU HOÀN THÀNH VIRC 2.7.0 RELEASE HARDENING & STRICT REGISTER ALLOCATION

- **Mã phát hành:** `virc 2.7.0 (self-hosted)`
- **Thời gian hoàn tất:** 2026-09-07T14:06:30+07:00
- **Git Commit:** `release: v2.7.0 hardening and strict register allocation` (Branch: `recovered_stash`)
- **Vị trí đóng băng (Release Pin):** `frozen/release/v2.7.0/`
- **Tài liệu kế hoạch liên quan chuyển lưu trữ:**
  - `docs/plan/done/REGISTER_ALLOCATION_OPTIMIZATION_AND_BLOCK_ARENA_PLAN.md`
  - `docs/plan/done/REGISTER_ALLOCATION_STRICT_SPEC.md`
  - `docs/plan/done/V2_7_0_RELEASE_HARDENING_PLAN.md`

---

## 1. Tổng Quan & Mức Độ Hoàn Thành: 100%

Tất cả các tiêu chí trong 3 kế hoạch kiến trúc (`REGISTER_ALLOCATION_OPTIMIZATION_AND_BLOCK_ARENA_PLAN.md`, `REGISTER_ALLOCATION_STRICT_SPEC.md`, `V2_7_0_RELEASE_HARDENING_PLAN.md`) đã được triển khai, kiểm thử, tự chứng minh qua bootstrapping Stage-2 và nghiệm thu toàn diện:

| Hạng mục kế hoạch | Mục tiêu kỹ thuật | Mức độ | Trạng thái nghiệm thu |
|---|---|:---:|---|
| **Phase 1: SSA Correctness** | Khởi tạo Sentinel `-1`, Dead Phi Sweep, In-place Mutation, Def-Counts Arena | **100%** | **PASS** — Kiểm chứng qua byte-exact MIR & SSA test suite |
| **Phase 2: Borrow Checker & Arena** | Move-on-Call `[E5001]`, Arena Escape `[E5005]`, If-Move Join, Rebind Conflict `[E5002]` | **100%** | **PASS** — 4/4 compile-fail test cases pass chẩn đoán mã lỗi |
| **Phase 3: Strict Register Allocation** | Target Descriptors, Def-vs-Live-Out Interference, Block-Arena Scratch, Post-RA Verifier | **100%** | **PASS** — nested5, sieve, spill30 pass; zero clobber regression |
| **Phase 4: Dynamic Mach-O ARM64 FFI** | Mach-O LC_DYLD_INFO_ONLY & LC_LOAD_DYLIB, target-neutral extern import | **100%** | **PASS** — `test_extern_from_os.vri` nạp động `getpid` thành công |
| **Phase 5: Self-Hosting Bootstrap** | Tự biên dịch Stage-1 -> Stage-2 -> Promotion `bin/virc` | **100%** | **PASS** — Binary 1.87 MB chạy ổn định và ký mã hợp lệ |
| **Phase 6: Release Freeze v2.7.0** | Đóng băng cây phát hành chuẩn `tools/freeze_std_tree.sh` | **100%** | **PASS** — `frozen/release/v2.7.0/` (401 std, 90 compiler, readonly) |
| **Test Suite Toàn Diện** | `./run_tests.sh` duy trì tỷ lệ vượt qua tuyệt đối | **100%** | **187/187 tests PASS** (log: [`V2_7_0_TEST_SUITE_RUN.log`](./V2_7_0_TEST_SUITE_RUN.log)) |

---

## 2. Chi Tiết Từng Hạng Mục & Bằng Chứng Thực Nghiệm (Evidence & Proofs)

### 2.1. Phase 1 — SSA Correctness & Optimization Hardening
- **Task 1.1 — Sentinel Initialization trong `mir_rename_variables`:**
  - *Giải pháp:* Khởi tạo stack đổi tên biến với sentinel `-1` thay vì index virtual register ban đầu trong `stdlib/vir/compiler/mir_ssa.vri`. Loại bỏ hoàn toàn sự mập mờ giữa pre-SSA và post-SSA namespace.
  - *Bằng chứng:* Các phép gán và tính toán biến lồng nhau trong `tests/vri/test_register.vri`, `tests/vri/test_arithmetic.vri` biên dịch chính xác, giá trị không bị biến dạng qua các nhánh dominator.
- **Task 1.2 — Dead Phi Sweep Post-Simplification:**
  - *Giải pháp:* Bổ sung hàm `mir_opt_sweep_dead_phis` trong `stdlib/vir/compiler/mir_opt.vri`. Khi tối ưu hóa đơn giản hóa khối CFG khiến danh sách giá trị vào của Phi node trở về rỗng (`vec_len(incoming) == 0`), Phi node đó được loại bỏ hoàn toàn khỏi `block.phis`.
  - *Bằng chứng:* Không còn Phi node ma chiếm vreg trong đồ thị can nhiễu.
- **Task 1.3 — In-Place Instruction Mutation & Def-Counts Arena:**
  - *Giải pháp:* Chuyển đổi `mir_opt_copy_propagation` và `mir_opt_constant_propagation` sang ghi đè operand tại chỗ (`native_write_i64`), giải phóng mảng đếm `def_counts` ngay khi kết thúc pass.
  - *Bằng chứng:* Tiết kiệm bộ nhớ heap, loại bỏ áp lực phân mảnh bộ nhớ khi biên dịch các hàm lớn của trình biên dịch.

---

### 2.2. Phase 2 — Borrow Checker Correctness & Scope-Block Arena Semantics
Triển khai đúng mô hình ngữ nghĩa lexical block scope (`ScopeKind.Block`) cho `arena:` và siết chặt 4 quy tắc an toàn bộ nhớ trong `stdlib/vir/compiler/sem_pass8_borrow.vri`:
1. **Move-on-Call Enforcement (`tests/test_borrow_move_on_call.vri`):**
   - *Quy tắc:* Truyền giá trị kiểu Move vào tham số hàm sẽ đánh dấu biến đã bị move trong scope hiện tại.
   - *Bằng chứng:* Trình biên dịch chặn chính xác với mã lỗi: `[E5001] Use of moved value: arr` (PASS compile-fail).
2. **Arena Escape Prevention (`tests/test_borrow_arena_escape.vri`):**
   - *Quy tắc:* Trả về hoặc gán một identifier trỏ vào biến cấp phát trong block `arena:` ra ngoài scope cha bị phát hiện và chặn đứng.
   - *Bằng chứng:* Trình biên dịch chặn chính xác với mã lỗi: `[E5005] Cannot escape arena-allocated reference` (PASS compile-fail).
3. **Conservative Move Join on Conditional Branches (`tests/test_borrow_if_move.vri`):**
   - *Quy tắc:* Biến bị move trong nhánh `then` hoặc `else` của câu lệnh điều kiện được xem là đã move tại điểm hợp lưu (join point).
   - *Bằng chứng:* Trình biên dịch chặn chính xác với mã lỗi: `[E5001] Use of moved value: res` (PASS compile-fail).
4. **Rebind Conflict Detection Order (`tests/test_borrow_rebind_conflict.vri`):**
   - *Quy tắc:* Đánh giá biểu thức vế phải (RHS) trước khi hủy bỏ liên kết borrow cũ ở vế trái trong phép gán, ngăn chặn xung đột mượn khả biến/bất biến (`&x` và `&mut x`).
   - *Bằng chứng:* Trình biên dịch chặn chính xác với mã lỗi: `[E5002] Cannot mutably borrow while shared borrow is active` (PASS compile-fail).

---

### 2.3. Phase 3 — Strict Register Allocation Architecture & Block Arena
Thay thế hoàn toàn cơ chế gán thanh ghi heuristic bằng kiến trúc Strict RA theo đúng đặc tả `REGISTER_ALLOCATION_STRICT_SPEC.md`:
1. **Target Register Descriptors (`stdlib/vir/compiler/lir_target_desc.vri`):**
   - Định nghĩa đối tượng trừu tượng `TargetDesc` phân định rõ:
     - **ARM64:** $K=9$ callee-saved registers khả dụng (`X19..X27`), reserved (`SP`, `FP`, `X16..X18`, `X28`), caller-saved clobbers (`X0..X15`).
     - **x86-64:** $K=4$ callee-saved registers (`RBX`, `R12..R14`), reserved (`RSP`, `RBP`, `R15`), caller-saved clobbers (`RAX`, `RCX`, `RDX`, `RSI`, `RDI`, `R8..R11`).
   - Loại bỏ triệt để các hằng số ma thuật cứng (`19 + color`).
2. **Đồ Thị Giao Thoa Def-vs-Live-Out & Liveness Ngược (`lir_liveness.vri`, `lir_interference.vri`):**
   - Tính toán liveness điểm lặp lùi từ `live_out` của từng lệnh tới `live_in`.
   - Thiết lập cạnh giao thoa hai chiều đối xứng chính xác giữa biến được định nghĩa (`def`) và mọi biến còn sống (`live_out`).
   - Khắc phục triệt để lỗi mất cạnh can nhiễu trong `nested5.vri`, đảm bảo biến điều kiện so sánh `cmpv` không bao giờ nhận trùng thanh ghi với toán hạng vòng lặp.
   - *Bằng chứng:* `tests/test_adv_021_nested5.vri` (5 vòng lặp lồng sâu 32 tầng tính toán) chạy và trả về đúng **`32`**; `tests/vri/test_adv_054_sieve.vri` chạy và in đầy đủ 15 số nguyên tố.
3. **Block-Arena Scratch Allocator cho RA (`stdlib/vir/compiler/lir_ra_arena.vri`):**
   - Quản lý các cấu trúc dữ liệu tạm thời của quá trình tô màu đồ thị (bitset, danh sách kề, worklist) bằng các khối bộ nhớ bump 64KB có checkpoint và reset theo từng hàm.
   - Không để lọt bất kỳ con trỏ tạm nào vào cấu trúc `LirFunc` hay bộ phát sinh mã máy.
4. **Mandatory Post-RA Verifier (`stdlib/vir/compiler/lir_verifier.vri`):**
   - Chạy tự động trước khi phát sinh mã máy để xác thực các bất biến nghiêm ngặt:
     1. Không còn virtual register chưa được gán.
     2. Không có 2 biến kề nhau trên đồ thị giao thoa nhận cùng thanh ghi vật lý.
     3. Khung ngăn xếp (stack frame) tuân thủ căn chỉnh 16-byte chuẩn ABI.
     4. Không có thanh ghi reserved bị vi phạm.

---

### 2.4. Phase 4 — Dynamic OS FFI Imports (Mach-O ARM64)
- **Chuẩn hóa Dynamic Loader:**
  - Hoàn thiện bộ phát sinh Mach-O linker tự thân: hỗ trợ `LC_LOAD_DYLIB` (`/usr/lib/libSystem.B.dylib`), bảng biểu tượng nạp động dyld chained fixups, loại bỏ hoàn toàn hashing ad-hoc và lỗi `_native_sha256`.
  - Hoàn thiện bộ phát sinh Mach-O linker tự thân: hỗ trợ `LC_LOAD_DYLIB` (`/usr/lib/libSystem.B.dylib`), cơ chế nạp động ký hiệu qua `LC_DYLD_INFO_ONLY` (rebase & binding opcodes), loại bỏ hoàn toàn hashing ad-hoc và lỗi `_native_sha256`.
  - Hỗ trợ ký mã `codesign -s - -f` hợp lệ trên macOS ARM64.
- **Bằng chứng thực nghiệm:**
  - Chạy `tests/test_extern_from_os.vri` gọi trực tiếp `getpid()` của hệ điều hành:
    ```bash
    ./bin/virc tests/test_extern_from_os.vri -o bin/test_extern_from_os && ./bin/test_extern_from_os
    ```
  - Kết quả đầu ra: **`PASS: ffi extern getpid verified`** (Mã thoát: 0).

---

### 2.5. Phase 5 & 6 — Self-Hosting Bootstrapping & Release Freeze v2.7.0
- **Bootstrapping Stage-2:**
  - Trình biên dịch seed `bin/virc` đã tự biên dịch toàn bộ cây mã nguồn trình biên dịch (`stdlib/vir/compiler/virc.vri`) để tạo ra `dist/virc-2.7.0-stage2` (1,873,112 bytes).
  - Đã thực hiện promote `dist/virc-2.7.0-stage2` -> `dist/virc-2.7.0` và `bin/virc`.
- **Tỷ lệ kiểm thử đạt 100% trong `./run_tests.sh`:**
  - **187/187 tests PASS** (xem log thực nghiệm đính kèm tại [`docs/report/V2_7_0_TEST_SUITE_RUN.log`](./V2_7_0_TEST_SUITE_RUN.log)), bao gồm toàn bộ các nhóm kiểm thử cơ bản, 100 test case nâng cao (Adv 001 - Adv 100), các ca hồi quy (Category A - K), ML Tensor Engine (Category L), và Mach-O FFI (Category M).
- **Cây Đóng Băng Phát Hành (`frozen/release/v2.7.0/`):**
  - Thực thi lệnh:
    ```bash
    bash tools/freeze_std_tree.sh release v2.7.0 --with-bin --with-expanded --readonly
    ```
  - Kết quả xác thực:
    - `frozen/release/v2.7.0/bin/virc`: Binary độc lập 1,906,160 bytes, ký mã định danh bootstrap `-i virc-bootstrap`.
    - `frozen/release/v2.7.0/virc-expanded.vri`: 1.7 MB preprocessed snapshot.
    - 401 stdlib files, 90 compiler source files.
    - Checksum SHA256SUMS xác thực 100% OK.
    - Quyền truy cập: Đã khóa chỉ đọc (`chmod -R a-w`).

---

## 3. Kết Luận & Lưu Trữ Kế Hoạch

Phiên bản **virc 2.7.0** đã đạt trạng thái hoàn thiện vững chắc cao nhất, đảm bảo tính đúng đắn toán học của giải thuật phân bổ thanh ghi và giải quyết triệt để các lỗi clobber / rò rỉ vùng nhớ.

Theo yêu cầu, 3 tài liệu kế hoạch tương ứng được di chuyển chính thức vào thư mục lưu trữ hoàn thành:
1. `docs/plan/done/REGISTER_ALLOCATION_OPTIMIZATION_AND_BLOCK_ARENA_PLAN.md`
2. `docs/plan/done/REGISTER_ALLOCATION_STRICT_SPEC.md`
3. `docs/plan/done/V2_7_0_RELEASE_HARDENING_PLAN.md`
