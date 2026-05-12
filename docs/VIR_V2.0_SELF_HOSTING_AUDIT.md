# Báo cáo Rà soát: Tiến độ Self-Hosted Vir Compiler v2.0

Dựa trên việc đối chiếu Đặc tả Ngôn ngữ Vir v2.0 (`vir_language_spec_v2.0_vi.md`) và Kiến trúc hệ thống (`ARCHITECTURE.md`), dưới đây là kết quả rà soát codebase để xác định các bước còn thiếu nhằm hoàn thiện trình biên dịch self-hosted cho bản v2.0, cũng như các tệp tin đã bị mất.

## 1. Các bước còn thiếu để hoàn thiện Self-Hosted v2.0

Trái với dự đoán ban đầu, qua quá trình rà soát trực tiếp các file vừa khôi phục (đặc biệt là `stdlib/vir/compiler/parser.vri` và `core/src/parser.c`), **Frontend (Trình phân giải cú pháp) ĐÃ ĐƯỢC CẬP NHẬT** để đọc và hiểu gần như toàn bộ tính năng của Spec v2.0, bao gồm: `entity`, `enum`, `packed entity`, khối `arena`, `throw`, `ensure`, `revert`, `import`, và `include`.

Tuy nhiên, "nút thắt cổ chai" ngăn cản việc self-hosting phiên bản v2.0 nằm ở **Backend và IR Optimizer** của trình biên dịch viết bằng Vir (`ir_optimizer.vri` và `codegen.vri`). Cụ thể, các bước còn thiếu gồm:

### 1.1. Hạ cấp IR (IR Lowering) cho Xử lý lỗi
Dù Parser đã phân giải được các khối xử lý lỗi mới (`AstType::ThrowStmt`, `EnsureBlock`, `RevertBlock`), nhưng module `ir_optimizer.vri` hiện tại **bỏ qua hoàn toàn** các AST Node này. Cần bổ sung logic dịch các Node này sang mã Q-IR (thiết lập register lỗi, nhảy đến scope `revert` tương ứng).

### 1.2. Trình Kiểm tra Mượn biến (Borrow Checker - NLL)
C engine (`core/src/ir_lower.c`) sở hữu một Borrow Checker rất tinh vi dựa trên Non-Lexical Lifetimes (NLL) để quản lý `&` và `&mut`. Nhưng bản tự biên dịch `ir_optimizer.vri` **hoàn toàn thiếu vắng** logic này. Để v2.0 hoạt động, Vir compiler cần phải tự viết lại hệ thống kiểm soát quyền sở hữu bộ nhớ này bằng chính ngôn ngữ Vir.

### 1.3. Generics, Trait và Pattern Matching
*   **Generics & Traits:** Cơ chế Monomorphization (E1) và Trait Resolution (E2) hoàn toàn chưa có mặt trong `ir_optimizer.vri`.
*   **Pattern Matching:** Toán tử `:~` chưa được tích hợp engine Virgex vào quá trình sinh mã.

### 1.4. Code Generation (Backend)
Phần phát sinh mã máy (`codegen.vri`) cần được mở rộng để emit mã assembly chuẩn cho FFI (`@bind(c)`) và hỗ trợ tốt hơn các lệnh gọi hệ thống (syscall) phục vụ module `async/task`.

---

## 2. Các File Bị Thất Lạc (Đã Khôi Phục)

Sự cố lệnh `git stash drop` của Kiro đã xóa tạm thời hơn 9,600 file thay đổi (bao gồm toàn bộ công sức migrate code sang `.vri`). Tuy nhiên, **toàn bộ dữ liệu này hiện đã được khôi phục thành công** và đóng gói an toàn vào commit gắn tag `SAFE_RECOVERY` trên nhánh `recovered_stash`.

Một vài tệp thực sự vắng mặt so với kỳ vọng ban đầu:
1.  **File backup `lexer.vir`:** Trong thư mục `stdlib/vir/compiler/`, các file như `codegen`, `parser` đều có bản backup cũ đuôi `.vir` nằm cạnh file chính đuôi `.vri`. Tuy nhiên không tìm thấy `lexer.vir`.
2.  **File `test_transpile.py`:** Tệp script này đã bị xóa bỏ hoàn toàn khỏi Git tree.
3.  **Tệp tối ưu Bootstrap Compiler (Pillar H1):** Các file như `opt_fold.vri`, `opt_dce.vri`, `opt_inline.vri` có trong Roadmap nhưng chưa từng được tạo ra trong `core/bootstrap/`.
