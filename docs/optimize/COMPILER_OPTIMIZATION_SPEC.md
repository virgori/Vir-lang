# Đặc tả Kỹ thuật Tối ưu hóa Trình biên dịch Vir (virc)
**Tài liệu:** `docs/optimize/COMPILER_OPTIMIZATION_SPEC.md`  
**Phiên bản áp dụng:** Vir Compiler v2.6.5+  
**Phạm vi:** AST Lowering, MIR/SSA Pipeline, Backend Lowering, Memory Arena Lifecycle

---

## 1. Function Inlining (Nội suy hàm)

### 1.1. Mục tiêu
Loại bỏ chi phí gọi hàm (prologue, epilogue, lưu/phục hồi thanh ghi, rẽ nhánh `BL`/`RET`) cho các hàm nhỏ, thường gặp như getters, setters, hàm phụ trợ tính toán.

### 1.2. Điều kiện áp dụng an toàn
Một hàm callee chỉ được nội suy vào caller khi thỏa mãn tất cả các điều kiện:
1. **Hàm lá (Leaf function):** Thân hàm callee không chứa bất kỳ lời gọi hàm nào khác (`mir_blocks_contain_call(callee_blocks) == 0`).
2. **Đơn khối (Single Basic Block):** `vec_len_rt(callee_blocks) == 1`. Điều này đảm bảo không làm phân mảnh hoặc phá vỡ đồ thị luồng điều khiển (CFG) của caller khi chèn lệnh.
3. **Giới hạn kích thước (Instruction budget):** Tổng số lệnh của callee $\le 25$ lệnh (`MIR_INLINE_MAX_INSTRS`), tránh bùng nổ kích thước binary (code bloat).
4. **Không đệ quy:** Hàm không được tự gọi chính nó (`callee != caller`).

### 1.3. Cơ chế biến đổi
- **Ánh xạ tham số (Parameter Re-mapping):** Toàn bộ VReg tham số của callee (`param_vregs`) được thay thế trực tiếp bằng VReg đối số của caller (`arg_vals`).
- **Gán dải thanh ghi ảo mới:** Các VReg nội bộ của callee được dịch chuyển (rebase) dựa trên `vreg_base = mir_func_next_vreg(caller)`.
- **Chuyển giá trị trả về:** Lệnh `Return src` của callee được chuyển thành `Move call_dst, src` trong caller.

---

## 2. Tính độ dài chuỗi tĩnh (`str_len` Folding)

### 2.1. Mục tiêu
Loại bỏ hoàn toàn chi phí gọi hàm runtime hoặc quét chuỗi O(N) khi độ dài của chuỗi đã biết tại thời điểm biên dịch.

### 2.2. Cơ chế biến đổi
1. **Tầng AST $\to$ MIR (`ast_to_mir.vri`):**
   - Khi gặp `AstType.Call` hoặc `AstType.BuiltinCall` gọi tới `str_len` hoặc `fat_str_len`:
   - Nếu tham số đầu tiên là một `AstType.LiteralStr`:
     - Trực tiếp tính `len = fat_str_len(node.str_val)`.
     - Xuất ra ngay `mir_opnd_imm(len)`.
     - Không phát sinh bất kỳ lệnh nạp chuỗi hay gọi hàm nào.
2. **Tầng MIR Constant Folding (`mir_opt.vri`):**
   - Nếu `ins.op == MirOp.Intrinsic` với mã `MIR_INTR_BUILTIN` và `src2 == BuiltinId.StrLen (9)`:
   - Nếu đối số tương ứng trỏ tới một hằng số chuỗi tĩnh trong bảng chuỗi, chuyển đổi trực tiếp thành `MirOp.Move dst, imm(length)`.

---

## 3. Peephole Optimization & Copy Elimination

### 3.1. Peephole Algebraic Simplifications
Duyệt qua các lệnh số học và bitwise để thay thế bằng hằng số hoặc phép toán rẻ hơn:
- **Cộng / Trừ:**
  - `Add x, 0` $\to$ `x`
  - `Sub x, 0` $\to$ `x`
  - `Sub x, x` $\to$ `0`
- **Nhân / Chia:**
  - `Mul x, 1` $\to$ `x`
  - `Mul x, 0` $\to$ `0`
  - `Mul x, 2^k` $\to$ `Shl x, k` (Strength Reduction)
  - `Div x, 1` $\to$ `x`
- **Phép toán Bitwise:**
  - `And x, 0` $\to$ `0`
  - `And x, -1` $\to$ `x`
  - `And x, x` $\to$ `x`
  - `Or x, 0` $\to$ `x`
  - `Or x, x` $\to$ `x`
  - `Xor x, 0` $\to$ `x`
  - `Xor x, x` $\to$ `0`
  - `Not (Not x)` $\to$ `x`
- **Phép so sánh đồng nhất:**
  - `CmpEq x, x` $\to$ `1`, `CmpNe x, x` $\to$ `0`
  - `CmpLt x, x` $\to$ `0`, `CmpLe x, x` $\to$ `1`

### 3.2. Copy Elimination
- **Loại bỏ lệnh tự gán (Self-move):** `Move v0, v0` $\to$ `Nop`.
- **Rút ngắn chuỗi sao chép (Copy Chain Collapse):**  
  `v1 = Move v0` tiếp theo là `v2 = Move v1` $\to$ rút ngắn thành `v2 = Move v0`.
- **Xóa bản sao chết (Dead Copy Elimination):** Sau khi lan truyền bản sao (`copy_propagation`) thay thế hết các vị trí sử dụng, nếu số lần sử dụng của `dst` bằng 0 thì chuyển `Move dst, src` thành `Nop`.

---

## 4. Vectơ hóa SIMD (ARM64 NEON)

### 4.1. Mục tiêu
Tận dụng các thanh ghi vectơ 128-bit (`V0`..`V31`) của kiến trúc ARM64 để xử lý đồng thời 2 phần tử 64-bit (chế độ 2D) hoặc 4 phần tử 32-bit (chế độ 4S) trong một chu kỳ máy.

### 4.2. Cơ chế biến đổi (SLP Vectorization)
1. **Gộp nạp bộ nhớ liên kề (Pair Load):**
   - 2 lệnh `Load` từ cùng một con trỏ cơ sở với offset cách nhau đúng 8 bytes (`offset1 - offset0 == 8`):
   - Thay thế bằng lệnh nội tại 128-bit `MIR_INTR_SWIZZLE` tương ứng mã máy `LD1 {Vt.2D}, [Xn]`.
2. **Gộp lưu bộ nhớ liên kề (Pair Store):**
   - 2 lệnh `Store` liên tiếp vào cùng con trỏ cơ sở cách nhau 8 bytes:
   - Thay thế bằng lệnh ghi 128-bit `ST1 {Vt.2D}, [Xn]`.
3. **Phép toán số học song song:**
   - Cặp phép cộng `Add` / trừ `Sub` trên các thanh ghi liền kề được hạ cấp thành `ADD {Vd.2D}, {Vn.2D}, {Vm.2D}`.

---

## 5. Phân tích hằng số vòng lặp (Loop Constant & Invariant Analysis)

### 5.1. Nhận diện cấu trúc vòng lặp
- Xác định cung ngược (back-edge) từ khối thân lặp về khối header lặp.
- Định vị hoặc tạo lập khối preheader ngay trước header.

### 5.2. Định nghĩa toán hạng bất biến (Loop Invariant)
Toán hạng `opnd` được xem là bất biến đối với vòng lặp nếu:
1. `opnd` là hằng số tức thời (`MirOperandType.Imm`).
2. Hoặc `opnd` là VReg có duy nhất một định nghĩa nằm **bên ngoài** thân vòng lặp.

### 5.3. Kéo biểu thức ra ngoài vòng lặp (Loop Invariant Code Motion - LICM)
- Một lệnh `ins` thuần túy (`pure op`: Add, Sub, Mul, Bitwise, Load không có rủi ro alias) nằm trong vòng lặp có tất cả các toán hạng đầu vào đều là bất biến:
- Lệnh được di chuyển (hoist) lên khối preheader trước khi vòng lặp bắt đầu.
- Kết quả được lưu vào VReg bất biến và tái sử dụng qua tất cả các lần lặp.

---

## 6. Quản lý bộ nhớ tối ưu hóa bằng Arena (`arena: ... end`)

- Mọi pass tối ưu hóa duyệt qua blocks, vectors, bảng băm tạm (def_counts, use_tables, worklists) đều được bao bọc trong khối `arena: ... end`.
- Sau khi pass kết thúc, toàn bộ các cấu trúc dữ liệu tạm thời được giải phóng nguyên khối tại mốc phân bổ arena, loại bỏ tình trạng phân mảnh và rò rỉ heap trong quá trình self-hosting của compiler.
