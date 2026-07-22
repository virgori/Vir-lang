# Báo cáo Trạng thái Dự án: Vir Compiler 1.0 (Production Ready)

Đây là báo cáo chính thức về cột mốc quan trọng nhất của dự án Vir: **Trở thành công cụ sản xuất (Production Compiler)**.

## 1. Tình trạng Bootstrap (Stage Verification)

Quá trình "Compiler tự build chính nó" đang được diễn ra và đã vượt qua chướng ngại lớn nhất:
- **C-core Compiler đã parse và dump AST thành công 100% mã nguồn của `virc_boot.vri`.** Toàn bộ lỗi cú pháp (Syntax Error) và lỗi ngữ nghĩa (Semantic Error) đã được giải quyết.
- **Stage 1 Compilation:** Hiện tại, máy ảo Q-IR đang chạy `virc_boot.vri` (Self-hosting compiler) để biên dịch chính nó ra một file nhị phân nguyên bản (Mach-O). Quá trình này diễn ra hoàn toàn độc lập, không cần đến Python script cũ.
- **Tiến trình tiếp theo:** Ngay sau khi Stage 1 hoàn tất (tạo ra `virc_stage1`), hệ thống sẽ tiếp tục chạy `virc_stage1` để tạo ra `virc_stage2` và so sánh nhị phân (Fixed-point proof). Nếu hai file giống nhau, Bootstrap được chứng minh thành công rực rỡ.

## 2. Đóng băng Compiler (Compiler Freeze) & Đặc tả Vir 1.0

Để đảm bảo tính ổn định và tính tương thích ngược từ nay về sau, **ngữ pháp và cú pháp của Vir được chính thức đóng băng tại phiên bản 1.0**. Mọi quy tắc dưới đây là **hợp đồng vĩnh viễn** của trình biên dịch:

### 2.1. Cấu trúc Khối (Block Structure)
- **Khối định nghĩa** (`func`, `entity`, `enum`, `record`, …): mở bằng `:` và **đóng bằng `end.`** (có dấu chấm).
- **Khối điều khiển** (`if`/`eif`, `when`, `for`, …): mở bằng `do` / `loop` tương ứng và **đóng bằng `end`** (không dấu chấm).
  - `if cond do` … `end`
  - `when cond loop` … `end`
  - `for i in 0..n do` … `end`

### 2.2. Vòng lặp (Loops)
- Vòng lặp for được chuẩn hoá với từ khoá tiếng Anh `for` (Loại bỏ hoàn toàn biến thể `với mỗi`).
- Cú pháp chính thức: **`for i in 0..len do`** … `end` (luôn `do`; không dùng `:` / `loop` / `;` làm opener).
- `when cond loop` … `end` cho vòng while.
- Từ khoá để thoát vòng lặp là `break` (loại bỏ hoàn toàn biến thể `thoát`).

### 2.3. Khai báo Hàm (Functions) — Vir v2.0

Vir **hỗ trợ cả hai** cách khai báo tham số (spec §6, §14):

**Cách 1 — Inline sau tên hàm** (§6.1, §14.1), khi ít tham số:

```vir
func add(a, b):
    out a + b
end.

func increment(ref x: int):
    x = x + 1
end.
```

**Cách 2 — Nhóm trong thân hàm** (§14.2), khi nhiều tham số / nhiều nhóm `in`/`ref`/`out`:

```vir
func process_data:
    in  path: String;
        timeout: Int
    ref buffer: Array
    out status: Bool
    # logic...
end.
```

Hoặc dạng gọn `in(...)` ngay sau `:`:

```vir
func is_ok:
    in(r: Result)
    # ...
end.
```

Cả `func name(params):` lẫn `func name:` + `in(...)`/`ref`/`out` đều hợp lệ — **không loại trừ lẫn nhau**.

### 2.4. Hệ thống Kiểu và Tính an toàn (Type System & Safety)
- Không có thay đổi so với dự kiến. Bao gồm các nguyên thuỷ (`int`, `f32`), `Slice`, và kiểu `Result` cho xử lý lỗi.
- Hệ thống FFI (`@bind`), quản lý vòng đời (`ref`), và kiến trúc thanh ghi / bộ đệm (Register & Mold) vẫn được duy trì như đặc tả hiện có.

---

**Kết luận:** Vir Compiler đã có thể tự đọc hiểu chính nó mà không gặp bất kỳ lỗi nào. Hợp đồng ngôn ngữ (Language Contract) đã được củng cố. Việc nâng cấp từ một nguyên mẫu thành một công cụ sản xuất đã chính thức bắt đầu.
