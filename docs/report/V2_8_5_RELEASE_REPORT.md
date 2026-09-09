# Vir Compiler v2.8.5 Release Report — AI/ML Hardening, Postfix Percent & Strict Packed Entity

- **Phiên bản phát hành**: `virc v2.8.5 (self-hosted)`
- **Ngày phát hành**: 2026-09-10
- **Trạng thái**: Production-Ready / General Availability (100% PASS)
- **Bản đóng băng**: `frozen/release/v2.8.5` (401 stdlib files, 90 compiler_src files, native signed binary, verified SHA-256)

---

## 1. Tổng quan Phát hành (Release Overview)

Phiên bản **Vir Compiler v2.8.5** đánh dấu bước hoàn thiện quan trọng về độ ổn định và tính tuân thủ nghiêm ngặt theo **Vir Language Specification v2.0**:
1. **Khắc phục triệt để Tensor Mutation & Coercion (Spec §26)**:
   - Sửa lỗi cấp phát rỗng và sai lệch kiểu phần tử khi gán giá trị nguyên vào `tensor<f32>`, bảo đảm slot ô nhớ tối thiểu 8 bytes.
   - Tự động chuẩn hoá kiểu (coercion) khi mutate mảng nhiều chiều để dispatch chính xác kernel nhân ma trận `**` (`LIR_RT_MATMUL` vs `LIR_RT_MATMUL_F64`).
2. **Toán tử Postfix Percent `%` (Spec §10 & §30)**:
   - Hỗ trợ toán tử hậu tố `%` biểu diễn tỷ lệ phần trăm (chia 100).
   - Tích hợp chuẩn xác vào thứ tự ưu tiên toán tử (precedence), kiểm tra kiểu chặt chẽ (từ chối string, boolean, tiền tố).
3. **Triển khai `packed entity` Nghiêm ngặt (Spec §4.4 & §7.3)**:
   - Bắt buộc cú pháp chuẩn `packed entity Name: ... end.`, loại bỏ cú pháp viết tắt `packed Name:`.
   - Layout byte tuần tự chính xác tuyệt đối (alignment 1 byte, không padding, không làm tròn 8 bytes, resolve đệ quy cho packed lồng nhau).
   - Toán tử compile-time `sizeof(Type)` trả về dung lượng byte thực tế.
   - Thao tác bộ nhớ định kiểu trên ARM64: `LDRB`/`LDRSB`, `LDRH`/`LDRSH`, `LDR W`/`LDRSW`, `LDR X` và `STRB`/`STRH`/`STR W`/`STR X`.
   - Toàn bộ chẩn đoán lỗi E3025..E3030 hoạt động chính xác.
4. **Đóng băng cây thư viện & trình biên dịch (`frozen/release/v2.8.5`)**:
   - Snapshot hoàn chỉnh có kiểm tra chữ ký số `SHA256SUMS` và nhị phân self-host được ký `codesign`.

---

## 2. Kết quả Kiểm thử (Test Suite Verification)

- **Nhóm 7 (Entity & Packed Entity)**:
  `55/55 PASS (100%)` — Bao gồm toàn bộ 17 bài test `tests/strict_v2/packed_*` mới.
- **Toàn bộ các chương kiểm thử (Min Conformance)**:
  `97/97 PASS (100%)` trên toàn bộ 31 nhóm phân loại Spec v2.0.
- **Self-Hosting Bootstrap**:
  Biên dịch hội tụ hoàn toàn không lỗi, vượt qua smoke test mã máy ARM64.
