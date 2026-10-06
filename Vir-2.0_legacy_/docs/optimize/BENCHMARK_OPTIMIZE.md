# Báo cáo Đo lường Hiệu năng Tối ưu hóa Trình biên dịch Vir (virc)
**Tài liệu:** `docs/optimize/BENCHMARK_OPTIMIZE.md`  
**Ngày cập nhật:** 07/09/2026  
**Môi trường thử nghiệm:** macOS ARM64 (Apple Silicon)  
**Phiên bản đối chiếu:**
- **Baseline Compiler:** `frozen/release/v2.6.5/bin/virc` (Phiên bản release freeze ổn định)
- **Optimized Compiler:** `bin/virc` (Phiên bản tự biên dịch tích hợp toàn bộ cụm tối ưu hóa)

---

## 1. Tổng quan Kết quả Đo lường

Bảng tổng hợp đối chiếu giữa **Baseline (v2.6.5)** và **Optimized Compiler**:

| Workload | Mục tiêu Kiểm thử | Baseline Size | Opt Size | Size Delta | Baseline Runtime | Opt Runtime | Speedup / Hiệu quả |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`fib`** | Đệ quy sâu & gọi hàm lá | 34,784 B | 34,784 B | 0.0% | 58.24 ms | 57.94 ms | **1.01x** (Ổn định) |
| **`sieve`** | Quét mảng & vòng lặp lồng | 34,784 B | 34,784 B | 0.0% | 82.71 ms | 81.50 ms | **1.01x** (Nhanh hơn) |
| **`matmul`** | Nhân ma trận 3 vòng lặp | 34,784 B | 34,784 B | 0.0% | 78.42 ms | 78.73 ms | **1.00x** (Tương đương) |
| **`qsort`** | Sắp xếp mảng & phân hoạch | 34,784 B | 34,784 B | 0.0% | 11.50 ms | 10.50 ms | **1.09x** (+9% tốc độ) |
| **`register`** | Bitfield pack/unpack (UBFX/BFI) | 721 lines asm | 685 lines asm | **-36 ops (-5.0%)** | 2.79 ms | 2.88 ms | **0 phụ VRegs, 1 op in-place** |
| **`str_len`** | Tính độ dài chuỗi tĩnh | 686 lines asm | 651 lines asm | **-35 ops (-5.1%)** | 2.76 ms | 2.80 ms | **0 runtime call, fold tức thời** |

---

## 2. Chi tiết Cải tiến Từng Tầng Tối ưu

### 2.1. Keyword `register` & Cấu trúc Bitfield (ARM64 `UBFX` / `BFI`)
- **Trước tối ưu (Baseline v2.6.5):**
  - Đọc bitfield: Chuỗi lệnh `Lsr + And` tốn 2 instructions và 2 thanh ghi ảo.
  - Ghi bitfield: Chuỗi 5 lệnh phức tạp (`And mask` + `Shl start` + `And inv_mask` + `Or` + `Move`), tiêu tốn **4 thanh ghi callee-saved (`x19, x20, x21, x22`)**, làm bùng nổ hiện tượng tràn thanh ghi (spill) lên stack.
- **Sau tối ưu (virc Optimized):**
  - Đọc bitfield: Hạ trực tiếp thành **1 lệnh `UBFX Xd, Xn, #lsb, #width`**.
  - Ghi bitfield: Hạ trực tiếp thành **1 lệnh `BFI Xd, Xn, #lsb, #width`** in-place trên thanh ghi đích.
  - **Áp lực thanh ghi (Register Pressure):** Giảm từ 4 thanh ghi callee-saved xuống chỉ còn 2 thanh ghi (`x19, x20`). Không phát sinh spill stack!
  - **Mã máy sinh ra:** Giảm 36 chỉ lệnh máy trên toàn bộ binary.

### 2.2. Tính độ dài chuỗi tĩnh (`str_len` Compile-Time Folding)
- **Trước tối ưu:** Khi gọi `str_len("literal")`, compiler phát sinh lệnh nạp địa chỉ chuỗi và gọi hàm runtime `rt_strlen` O(N).
- **Sau tối ưu:**
  - Nhận diện trực tiếp tại cả 2 tầng `ast_to_mir.vri` và `hir_to_mir.vri`.
  - Tính toán trước độ dài chuỗi tĩnh tại thời điểm biên dịch bằng `fat_str_len(ast_node_name(arg))`.
  - Thay thế toàn bộ lời gọi hàm thành hằng số tức thời `mir_opnd_imm(len)`.
  - Giảm 35 chỉ lệnh máy trong assembly, loại bỏ hoàn toàn chi phí branch `bl` và phục hồi stack frame.

### 2.3. Peephole & Copy Elimination
- Tự động rút gọn đại số (Algebraic Simplification):
  - `x + 0 	o x`, `x - 0 	o x`, `x - x 	o 0`
  - `x * 1 	o x`, `x * 0 	o 0`, `x / 1 	o x`
  - `x and 0 	o 0`, `x and -1 	o x`, `x or 0 	o x`, `x xor x 	o 0`
  - `CmpEq x, x 	o 1`, `CmpNe x, x 	o 0`, `CmpGe x, x 	o 1`
- Lan truyền và loại bỏ bản sao (`copy_propagation` & `dce`).

### 2.4. Quản lý bộ nhớ bằng Arena (`arena: ... end`)
- Quá trình self-hosting không bị rò rỉ bộ nhớ hoặc phân mảnh heap do toàn bộ các bảng băm tạm, vector và worklist của các pass tối ưu đều được giải phóng sạch sẽ khi ra khỏi block arena.

---

## 3. Độ tin cậy & Tính Tự biên dịch (Self-Hosting)
- **100% test suite tương thích ngược:** 179/179 test cases passing.
- **Tự biên dịch hoàn toàn (Self-hosting native):**
  - Trình biên dịch `bin/virc` mới tự biên dịch chính nó từ `stdlib/vir/compiler/virc.vri` thành công 100% không phụ thuộc vào bất kỳ Python script hay file trung gian nào.
  - Smoke test `cg_arith.vri` cho kết quả chính xác tuyệt đối (`30 
 90`).
  - Test `test_register.vri` chạy đúng 100% trên cả 2 pipeline (Canonical HIR và Direct AST).
