---
id: "VIRON-SPC-0006"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Toolchains & Sysroot Management"
status: "DRAFT"
version: "1.0.0"
language: "vi"
spec_class: "SPECIFICATION"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRON"
components: []
aliases:
  - "docs/viron/toolchains.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0006 — Viron v2.0 Architecture — Toolchains & Sysroot Management

Tài liệu này chi tiết hóa cách Viron quản lý đa phiên bản trình biên dịch, cấu trúc phân cấp `~/.vir/`, cơ chế dispatching qua shim, quy tắc sysroot và quy trình cài đặt bootstrap.

---

## 1. Bootstrap Installation

### Kịch bản cài đặt chính thức:
```bash
curl -fsSL https://get.virgori.com | sh
```

### Nguyên tắc thiết kế kịch bản `install.sh`:
- **Tối giản (Minimalist Loader):** Kịch bản shell chỉ đảm nhiệm vai trò cầu nối, tuyệt đối không chứa logic cài đặt phức tạp.
- **An toàn:** Chạy với `set -e`, trích dẫn toàn bộ biến, không sử dụng lệnh `sudo` (mặc định cài đặt vào thư mục người dùng `~/.vir/`).
- **Quy trình thực thi:**
  1. Nhận diện hệ điều hành (`darwin`, `linux`, `windows`) và kiến trúc phần cứng (`arm64`, `x86_64`, `riscv64`).
  2. Tải binary `viron-bootstrap` tương ứng từ CDN phân phối chính thức kèm mã băm kiểm tra.
  3. Xác thực mã băm SHA-256 của binary đã tải.
  4. Đặt binary vào `~/.vir/bin/viron` và gán quyền thực thi (`chmod +x`).
  5. Gọi lệnh khởi tạo nội bộ: `~/.vir/bin/viron setup`.

### Quy trình Viron Setup:
Khi chạy `viron setup`, Viron tự động:
1. Phân giải và tải toolchain phiên bản `stable` mới nhất.
2. Cài đặt các thư viện lõi và sysroot tương ứng.
3. Thiết lập biến môi trường PATH vào tệp cấu hình shell của người dùng (`.zshrc`, `.bashrc`, `.config/fish/config.fish`).
4. Kiểm tra và xác minh cài đặt thành công.

---

## 2. Bố Cục Thư Mục Gốc (`VIR_HOME`)

Mặc định tại `~/.vir/` (có thể ghi đè qua biến môi trường `VIR_HOME`):

```text
~/.vir/
├── bin/                       # Điểm duy nhất cần thêm vào PATH
│   ├── viron                  # Binary quản lý Viron chính
│   ├── virc                   # Dispatcher shim trỏ tới compiler hoạt động
│   └── vir-lsp                # Dispatcher shim trỏ tới language server
│
├── toolchains/                # Nơi chứa các phiên bản compiler độc lập
│   ├── 3.1.0/
│   │   ├── bin/
│   │   │   ├── virc           # Binary thực của virc 3.1.0
│   │   │   └── vir-lsp        # Binary thực của vir-lsp 3.1.0
│   │   ├── sysroot/           # Runtime nền tảng đi kèm compiler
│   │   │   ├── libvir_rt.a
│   │   │   ├── core/
│   │   │   └── intrinsics/
│   │   ├── runtime/
│   │   └── manifest.toml      # Thông số kỹ thuật của bản build
│   │
│   └── 3.2.0/
│
├── packages/                  # Kho lưu trữ các gói thư viện phiên bản cố định
│   ├── vir.json/
│   │   └── 1.8.3/
│   └── vir.crypto/
│       └── 2.2.1/
│
├── cache/
│   ├── downloads/             # Tệp tải tạm thời (.part)
│   ├── archives/              # Kho nén .tar.zst bất biến
│   └── objects/               # Content-Addressed Storage (CAS) theo SHA-256
│
├── registry/
│   ├── index/                 # Git/HTTP sparse index metadata
│   └── metadata/              # JSON metadata cache
│
├── state/                     # Trạng thái hệ thống nội bộ
│   ├── installed.toml         # Danh sách toolchains & packages đã cài
│   └── current-toolchain      # Tên/phiên bản toolchain mặc định toàn cục
│
├── config.toml                # Cấu hình người dùng (registry, mirrors, timeout)
└── logs/                      # Nhật ký hoạt động và debug
```

---

## 3. Quản Lý PATH & Dispatcher Shims

### Nguyên Tắc Bất Biến
**Không bao giờ chỉnh sửa (mutate) biến môi trường PATH mỗi khi người dùng thay đổi phiên bản compiler.**

Người dùng chỉ cần thêm một dòng duy nhất vào cấu hình shell:
```bash
export PATH="$HOME/.vir/bin:$PATH"
```

### Cơ Chế Dispatching Của Shim `~/.vir/bin/virc`
File `~/.vir/bin/virc` là một binary shim siêu nhẹ. Khi được gọi:
1. **Kiểm tra biến môi trường:** Đọc biến `VIR_TOOLCHAIN` (nếu người dùng muốn ép phiên bản tạm thời).
2. **Kiểm tra cấu hình dự án:** Quét ngược từ thư mục hiện tại lên các thư mục cha tìm `vir.toml`. Nếu có mục `[toolchain].vir = "3.1.0"`, chọn toolchain `3.1.0`.
3. **Fallback mặc định toàn cục:** Nếu không nằm trong dự án, đọc tệp `~/.vir/state/current-toolchain`.
4. **Chuyển tiếp thực thi:** Dùng lệnh hệ thống `execv` để kích hoạt trực tiếp `~/.vir/toolchains/<version>/bin/virc` kèm tham số `--sysroot ~/.vir/toolchains/<version>/sysroot`.

---

## 4. Quản Lý Đa Toolchain & Kênh Phát Hành (Channels)

Viron cho phép nhiều compiler cùng tồn tại song song mà không xung đột:

### Các Lệnh CLI
```bash
viron toolchain install 3.1.0        # Cài đặt phiên bản cụ thể
viron toolchain install 3.2.0        # Cài đặt thêm phiên bản mới
viron toolchain list                 # Hiển thị các toolchain đang có
viron toolchain default 3.2.0        # Chọn bản mặc định toàn hệ thống
viron toolchain uninstall 3.1.0      # Gỡ bỏ toolchain không dùng
```

### Kênh Phát Hành (Channels)
- `stable`: Phiên bản phát hành ổn định chính thức.
- `beta`: Phiên bản phát hành xem trước tính năng.
- `nightly`: Bản dựng tự động mới nhất mỗi ngày.

> **Quy tắc phân giải bất biến:** Kênh phát hành luôn được phân giải thành một phiên bản cố định bất biến (immutable version). Viron không bao giờ lưu trữ giá trị "stable" hay "nightly" vào tệp trạng thái cuối cùng, mà luôn lưu chuỗi phiên bản chính xác (ví dụ: `stable` → `3.2.4`, `nightly` → `3.3.0-nightly.20260918`).

---

## 5. Khái Niệm Sysroot & Loại Bỏ `./stdlib`

### Vấn Đề Lịch Sử
Trước đây, các trình biên dịch dạng prototype thường dựa vào giả định thư mục làm việc hiện tại chứa `./stdlib` hoặc `../stdlib`. Điều này khiến việc di chuyển binary sang môi trường khác hoặc chạy dự án ở thư mục bất kỳ bị gãy đổ.

### Giải Pháp Sysroot Chuẩn Hóa
- Toàn bộ runtime, định nghĩa hệ thống và thư viện gắn liền với trình biên dịch được đóng gói thành **`sysroot`** tại:
  ```text
  ~/.vir/toolchains/<version>/sysroot/
  ```
- Trình biên dịch `virc` nhận đường dẫn sysroot tường minh thông qua cờ `--sysroot <path>`.
- Compiler không tự ý suy đoán sysroot từ thư mục hiện tại.
- Người dùng có thể chạy `viron build` từ bất kỳ thư mục nào trên máy mà không cần quan tâm đến repository mã nguồn của Vir.

---

## 6. Phân Tách Bốn Lệnh Cập Nhật Độc Lập

Viron đảm bảo tính độc lập tuyệt đối giữa bốn đối tượng nâng cấp, **không có lệnh nào cập nhật ngầm cả bốn thành phần cùng lúc**:

| Lệnh | Phạm vi cập nhật | Đối tượng bị ảnh hưởng |
|---|---|---|
| `viron self update` | Chỉ nâng cấp binary `viron` | `~/.vir/bin/viron` |
| `viron toolchain update` | Chỉ nâng cấp trình biên dịch | `~/.vir/toolchains/<ver>` |
| `viron std update [pkg]` | Chỉ nâng cấp official libraries | Các gói `vir.*` trong cache |
| `viron update [pkg]` | Chỉ nâng cấp phụ thuộc của project | Cập nhật `vir.lock` của dự án |

---

## 7. Cơ Chế Rollback & Phục Hồi (Doctor)

### Rollback Toolchain
Nếu việc nâng cấp compiler gặp lỗi hoặc hồi quy:
```bash
viron toolchain rollback
```
Viron chỉ đơn giản đổi con trỏ trong `~/.vir/state/current-toolchain` về phiên bản trước đó mà không cần tải lại từ mạng nếu tệp nhị phân cũ vẫn còn lưu trữ.

### Viron Doctor
Khi gặp sự cố môi trường, lệnh `viron doctor` thực hiện kiểm tra toàn diện 10 tiêu chí:
1. Giá trị biến môi trường `VIR_HOME` và quyền ghi.
2. Cấu hình `PATH` trong shell hiện hành.
3. Tính toàn vẹn của binary `viron`.
4. Toolchain hiện hành và binary `virc`.
5. Tính hợp lệ của cấu trúc `sysroot`.
6. Khả năng kết nối đến Vir Registry.
7. Trạng thái phân quyền của kho cache.
8. Tính hợp lệ của manifest `vir.toml`.
9. Tính toàn vẹn của lockfile `vir.lock`.
10. Kiểm tra mã băm SHA-256 các gói đã cài.

```bash
viron doctor --repair
```
Tự động quét và khôi phục các chỉ mục metadata bị hỏng từ dữ liệu tệp tin thực tế mà không xóa dữ liệu người dùng.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/toolchains.md` and assigned stable ID `VIRON-SPC-0006` |
