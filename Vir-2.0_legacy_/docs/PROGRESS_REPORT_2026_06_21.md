# Tiến Độ Phát Triển Vir - Báo Cáo Thực Trạng (21/06/2026)

> **Note:** Snapshot 21/06 — Phase 4 kickoff for **HIR + MIR**. That decision aligns with today’s official **HIR → MIR → LIR** spine (Spec §1.2). Numbers/status in this file are historical.

## 1. Các Tính Năng Đã Hoàn Thành (Phase 3 & Phase 9.1)

### 1.1. Intrinsic Registry (Phase 3)
- Đã hoàn thiện hệ thống `vir_intr_table` O(1) dispatch trong VM.
- Đã ánh xạ toàn bộ các lời gọi C-shim ngoại vi (`syscall`, `sys_read`, `memcpy`...) qua mã bytecode `Q_INTRINSIC`.
- Đã bổ sung bộ xử lý cho các phép toán **Intrinsic Mới**: `clz`, `ctz`, `popcnt`, `bswap` và các thao tác **Atomics** (`atomic_load`, `atomic_store`, `atomic_add`, `atomic_sub`) trong VM.
- Đã cập nhật C compiler core (`ir_lower.c`) và self-hosted compiler (`stdlib/vir/compiler/ir_optimizer.vri`) để có thể sinh bytecode `Q_INTRINSIC` từ các `AST_BUILTIN_CALL`. 
- Đã loại bỏ triệt để hàm shim cũ `vm_try_syscall_intrinsic`.

### 1.2. Multilingual Lexer Isolation (Phase 9.1)
- Từ khóa của các ngôn ngữ đã được bóc tách hoàn toàn khỏi core lexer (`lexer.c` và `lexer.vri`).
- Core lexer giờ đây tinh gọn, chỉ quản lý keyword chuẩn của Vir. Các từ khóa khác sẽ được tích hợp dạng plugin/sublib (như `lang_vi.c` hay `lang_zh.c`), hỗ trợ khả năng mapping sau này mà không làm core bị "phình to" hay gây xung đột ngôn ngữ.
- Core codebase đã được biên dịch thành công (`make -C core/`).

## 2. Bước Tiếp Theo: Phase 4 (HIR & MIR Implementation)

Bắt đầu tiến trình tái cấu trúc kiến trúc trình biên dịch theo chuẩn "Compiler / Runtime Engine", bao gồm việc xây dựng **High-level IR (HIR)** và **Mid-level IR (MIR)**.

### 2.1. Thiết kế HIR (`core/include/hir.h`)
HIR sẽ đại diện cho cấu trúc ngữ nghĩa sau quá trình AST (Abstract Syntax Tree) resolution, loại bỏ cú pháp (sugar syntax) không cần thiết và tiến hành kiểm tra kiểu (Type checking).
- Xây dựng `hir_node_t` độc lập.
- Thêm Type-Checking gắn liền với mỗi node HIR.

### 2.2. Thiết kế MIR (`core/include/mir.h`)
MIR sẽ đóng vai trò như một Control Flow Graph (CFG), phục vụ việc tối ưu hóa (Optimizer) và phân bổ thanh ghi (Register Allocation).
- Cấu trúc `mir_instr_t` cho dạng TAC (Three-Address Code).
- Quản lý Basic Block (`mir_block_t`).

## 3. Tình Trạng Lỗi Khác Cần Lưu Ý
- Vẫn còn tồn đọng lỗi môi trường Test (`tests/run_tests`) và lỗi `VM_HEAP_INITIAL_BLOCKS` (được nhắc đến trước đó). Ta có thể ưu tiên kiến trúc HIR/MIR trước rồi sửa lỗi này hoặc ngược lại tuỳ thuộc luồng công việc.
