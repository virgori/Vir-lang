# Lộ trình Chiến lược: Tái sinh Pure-Vir (Self-Hosting 100%)

**Mục tiêu tối thượng:** Loại bỏ hoàn toàn sự phụ thuộc vào Python (Frontend/Optimizer) và C (Runtime Core), đưa Vir thành một hệ sinh thái tự trị hoàn toàn.

---

## 1. Triết lý thực hiện: "Diệt Python trước, Diệt C sau"

Sau khi hoàn tất bước ngoặt v1.2 (`entity`, `map`, `float`), Vir đã có đủ công cụ ngôn ngữ để mô phỏng các cấu trúc dữ liệu phức tạp của một trình biên dịch hiện đại. 

### Bước đi chiến lược:
1.  Sử dụng VM (C) và Compiler (Python) hiện có làm "giàn giáo" để xây dựng các module Vir mới.
2.  Port lần lượt 12-pass Optimizer từ Python sang Vir (v1.2).
3.  Khi Optimizer chạy ổn định trên Vir, ta sẽ loại bỏ Python.
4.  Cuối cùng, viết lại `vm.vri` để loại bỏ C.

---

## 2. Lộ trình PORTING 12-PASS OPTIMIZER (Vir v1.2)

Tận dụng tính năng `entity` và `map` vừa nâng cấp để tái cấu trúc Optimizer.

### Phase 1: Vir-on-Vir Base Architecture
- **Entity: `Instruction`**: Đại diện cho một lệnh Q-IR.
  ```vir
  entity QInstr:
      opcode: int;
      dest: int;
      src1: int;
      src2: int;
      meta: map; # metadata (labels, type hints)
  end
  ```
- **Entity: `BasicBlock`**: Quản lý luồng điều khiển (CFG).
  ```vir
  entity BasicBlock:
      id: int;
      instrs: array; # Danh sách QInstr
      predecessors: array;
      successors: array;
  end
  ```

### Phase 2: Implementation mẫu (Constant Folding Pass)
Đây là Pass đầu tiên nên thực hiện để kiểm chứng sức mạnh v1.2.

**Logic porting từ Python sang Vir:**
1.  **Input:** Một danh sách `BasicBlock`.
2.  **State:** Một `map` dùng làm `ConstantTable` (lưu trữ giá trị hằng số của các thanh ghi).
3.  **Process:**
    - Duyệt qua từng `instr` trong block.
    - Nếu là `Q_ADD` và cả 2 toán cụ có trong `ConstantTable` → Thực hiện cộng → Thay bằng `Q_LOAD_CONST` → Cập nhật `ConstantTable`.
    - **Ưu điểm v1.2:** Sử dụng `map` để tra cứu hằng số cực nhanh và `entity` để truy cập thuộc tính lệnh một cách tường minh (`instr.src1`).

---

## 3. Hành trình Loại bỏ C Core (Tầng Thừa kế Cuối cùng)

Khi Python đã biến mất, ta sẽ xử lý "động cơ" C:

- **Module: `MemoryManager.vri`**: Tự viết trình quản lý Heap bằng Vir, sử dụng các mảng byte lớn (`array`) và tự tính toán offset để cấp phát cho `entity`.
- **Module: `VMSwitch.vri`**: Viết lại vòng lặp `while(1) { case opcode }` bằng Vir.
- **Module: `Syscall.vri`**: Sử dụng `Q_SYSCALL` (opcode mới) để trực tiếp yêu cầu Kernel cấp quyền JIT (`mprotect`) hoặc đọc ghi file, không qua thư viện chuẩn C (`libc`).

---

## 4. Bảng Kế hoạch Thực hiện (Ước tính)

| Giai đoạn | Tiêu điểm | Công nghệ Vir sử dụng |
| :--- | :--- | :--- |
| **Stage 1** | Porting `Constant Folding` & `DCE` | `entity Instruction`, `map Constants` |
| **Stage 2** | Xây dựng `DataFlowAnalyzer` | `map Graphs`, `try/catch` cho validation |
| **Stage 3** | Viết `Virgex` (Regex Engine) | `entity StateMachine`, `map Transitions` |
| **Stage 4** | Khởi tạo `vm.vri` (Core Interpreter) | Low-level memory access (v1.3 target) |

---

## 5. Đối soát & Phân tích lỗ hổng kỹ thuật (Vir v1.2 vs. C)

Để thực sự thay thế C Core, Vir cần lấp đầy các lỗ hổng hạ tầng mà phiên bản v1.2 hiện tại chưa nêu chi tiết:

- **Raw Memory Access (Truy cập Bộ nhớ Thô):** Vir cần khả năng nhìn bộ nhớ như một `array byte` khổng lồ và ép kiểu một đoạn bất kỳ thành `entity` (giống như `void*` và `struct pointer` của C).
- **Pointer Arithmetic (Tính toán Con trỏ):** Khả năng thực hiện `ptr + offset` trực tiếp trên vùng nhớ JIT để duyệt qua bytecode với độ trễ bằng 0.
- **FFI & Syscall Bridge:** Thay thế `bridge.c` bằng Opcode `Q_SYSCALL` để Vir có thể trực tiếp yêu cầu quyền thực thi (`mprotect`) từ Kernel mà không qua thư viện C.
- **Metaprogramming cho Cross-platform:** Cơ chế biên dịch có điều kiện (tương đương `#ifdef`) để một mã nguồn `compiler.vri` có thể tự thích ứng khi chạy trên ARM (Mac M1/M2) hoặc x86.

---

## 6. Bảng đối soát mức độ sẵn sàng của Opcode (Pure Vir Coverage)

Đây là thước đo khả năng tự trị của Vir trên 3 tầng thực thi:

| Nhóm Opcode | Opcode | C Core (VM) | Python FE | Vir (Self) | Ghi chú |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Số nguyên** | `Q_ADD`, `Q_SUB`, `Q_MUL` | ✅ | ✅ | ✅ | Đã ổn định 100% |
| | `Q_DIV`, `Q_MOD` | ✅ | ✅ | ✅ | |
| **Số thực** | `Q_FADD`, `Q_FSUB` | ✅ | ✅ | ⚠️ | Vir v1.2 mới bắt đầu dùng |
| | `Q_FMUL`, `Q_FDIV` | ✅ | ✅ | ⚠️ | Cần port logic chọn opcode float |
| **Thực thể** | `Q_ENTITY_NEW` | ✅ | ✅ | ✅ | Phục vụ Self-hosting Parser |
| | `Q_GET_FIELD`, `Q_SET_FIELD` | ✅ | ✅ | ✅ | |
| **Bản đồ** | `Q_MAP_NEW`, `Q_MAP_SET` | ✅ | ✅ | ✅ | Thay thế cho Symbol Table |
| | `Q_MAP_GET` | ✅ | ✅ | ✅ | |
| **Lỗi** | `Q_TRY_START`, `Q_TRY_END` | ✅ | ✅ | ❌ | Vir chưa dùng try/catch nội bộ |
| **Hệ thống** | `Q_PRINT`, `Q_INPUT` | ✅ | ✅ | ✅ | |
| | `Q_PATCH_POINT` | ✅ | ✅ | ❌ | Chỉ Python sinh ra được |
| **Hạ tầng 1.3**| `Q_SYSCALL` | ❌ | ❌ | ❌ | **Lỗ hổng để giết C** |
| | `Q_MEM_LOAD/STORE` | ❌ | ❌ | ❌ | **Lỗ hổng để giết C** |

---

## 7. Opcode Dự trữ Chiến lược (v1.5/v2.0 - Siêu hiệu năng)

Để Vir thực sự vượt qua giới hạn của C về mặt hiệu suất và tính năng, danh sách "dự trữ" sau đây cần được tích hợp vào lộ trình v1.5+:

- **Nhóm Vector/SIMD:** `Q_VEC_LOAD`, `Q_VADD`, `Q_VDOT` (Hỗ trợ NEON/AVX để xử lý dữ liệu song song cực nhanh như các thư viện xử lý ảnh/AI).
- **Nhóm Atomic & Đa luồng:** `Q_CMP_SWAP`, `Q_ATOMIC_ADD`, `Q_FENCE` (Xây dựng runtime đa luồng và các cấu trúc dữ liệu lock-free tự trị).
- **Nhóm Bitwise Nâng cao:** `Q_CLZ`, `Q_CTZ`, `Q_POPCNT` (Tối ưu hóa cực độ cho Memory Allocator và các thuật toán nén/mật mã).
- **Nhóm JIT Controller:** `Q_HOT_READ`, `Q_DEOPTIMIZE`, `Q_TAIL_CALL` (Giúp Vir tự tối ưu chính mình khi đang chạy, đạt hiệu năng tương đương JIT hiện đại nhất thế giới).

---

## 8. Siêu năng lực Kiến trúc (Architectural Superpowers - v2.0)

Đây là những tính năng độc bản của Vir mà ngay cả C hay Python cũng khó lòng thực hiện được một cách trơn tru:

- **Self-Patching (Tự sửa mã máy):** `Q_PATCH_FUNC`, `Q_REDIRECT` (Thay đổi logic của một hàm ngay trên RAM khi đang chạy mà không cần khởi động lại).
- **Hardware-Sovereign (Chủ quyền phần cứng):** `Q_REG_PIN` (Ghim các biến quan trọng vào thanh ghi vật lý vĩnh viễn), `Q_ISA_SWITCH` (Tự động chuyển đổi tập lệnh x86/ARM trong cùng một binary).
- **Security-First Execution:** `Q_SIGN_VSIB` (Ký số và xác thực module bộ nhớ), `Q_ISOLATE` (Tạo Sandbox phần cứng cho từng hàm).
- **Living Metadata:** `Q_REFLECT_IR` (Truy ngược mã Q-IR từ mã máy đang chạy để tự gỡ lỗi và tối ưu hóa).

> [!TIP]
> **Khởi động:** Bạn có muốn tôi phác thảo chi tiết cấu trúc dữ liệu và logic cho **Pass 1: Constant Folding** dựa trên cú pháp Vir v1.2 để bạn bắt đầu "port" không?

