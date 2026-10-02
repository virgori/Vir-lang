---
id: "VIRON-SPC-0003"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Package Format, Manifest & Lockfile"
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
  - "docs/viron/package-format.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0003 — Viron v2.0 Architecture — Package Format, Manifest & Lockfile

Tài liệu này đặc tả quy chuẩn dự án Vir, định dạng manifest `vir.toml`, cấu trúc lockfile `vir.lock`, kho lưu trữ gói toàn cục (Global Immutable Cache) và định dạng lưu trữ archive `.tar.zst`.

---

## 1. Cấu Trúc Dự Án Tiêu Chuẩn

Mọi dự án Vir được quản lý bởi Viron đều tuân thủ bố cục phẳng, trực quan:

```text
my-project/
├── vir.toml               # Manifest khai báo metadata và phụ thuộc
├── vir.lock               # File khóa đồ thị phụ thuộc bất biến
├── src/
│   └── main.vri           # Điểm khởi đầu cho binary (hoặc lib.vri cho library)
└── target/                # Thư mục chứa artifact biên dịch (được gitignore)
    ├── debug/
    └── release/
```

> **Nguyên Tắc Bất Biến:**
> Viron **tuyệt đối không** tự động tạo các thư mục như `node_modules/`, `vendor/` hay `stdlib/` bên trong dự án. Toàn bộ các gói phụ thuộc được đọc trực tiếp từ kho cache toàn cục được chia sẻ của hệ thống.

---

## 2. Đặc Tả Manifest (`vir.toml`)

Manifest sử dụng cú pháp chuẩn TOML (được parse bằng parser TOML chuẩn của Vir, không dùng regex hay ad-hoc parser):

```toml
[package]
name = "vir-service"
version = "0.2.1"
authors = ["Vir Team <dev@virgori.org>"]
description = "High-performance microservice in pure native Vir"
license = "Apache-2.0"
repository = "https://github.com/virgori/vir-service"

[toolchain]
vir = "3.2"                # Pin phiên bản compiler tối thiểu

[modules]
root = "service"           # Tên namespace alias được xuất ra ngoài
entry = "src/lib.vri"      # Điểm nhập chính của module nếu là thư viện

[dependencies]
"vir.json" = "^1.8"        # Thư viện chính thức
"vir.crypto" = "~2.2.0"    # Thư viện chính thức với tilde range
"foo.http" = "0.9.4"       # Thư viện bên thứ ba phiên bản cố định

# Hỗ trợ phát triển local mà không cần sửa registry:
"my.util" = { path = "../shared/util" }

[dev-dependencies]
"vir.test" = "^1.0"        # Phụ thuộc chỉ dùng khi chạy `viron test`

[build-dependencies]
"vir.codegen" = "0.1.0"    # Phụ thuộc dùng trong build script

[compatibility]
vir = ">=3.1,<4.0"         # Ràng buộc tương thích trình biên dịch

[features]
default = ["logging"]
logging = ["vir.log"]
compression = ["vir.zstd"]

[target.'aarch64-apple-darwin'.dependencies]
"vir.darwin_sys" = "1.0.0" # Phụ thuộc riêng biệt theo nền tảng

[profile.dev]
opt_level = 0
debug_info = true

[profile.release]
opt_level = 3
debug_info = false
lto = true
```

---

## 3. Đặc Tả Lockfile (`vir.lock`)

`vir.lock` lưu trữ toàn bộ đồ thị phụ thuộc cụ thể đã được phân giải, đảm bảo việc biên dịch ở bất kỳ máy nào cũng tạo ra mã nhị phân có cùng phiên bản và cùng checksum 100%:

```toml
version = 1

[[package]]
name = "foo.http"
version = "0.9.4"
source = "registry+https://pkg.virgori.com"
checksum = "sha256:3b9acba72b534b4b3b64c126d90697f83b1657ff1fc53b92dc18148a1d65dfc"
dependencies = [
    "vir.net@1.5.2"
]

[[package]]
name = "vir.crypto"
version = "2.2.1"
source = "registry+https://pkg.virgori.com"
checksum = "sha256:1a84f509cba72b534b4b3b64c126d90697f83b1657ff1fc53b92dc18148a1d65"

[[package]]
name = "vir.json"
version = "1.8.3"
source = "registry+https://pkg.virgori.com"
checksum = "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"

[[package]]
name = "vir.net"
version = "1.5.2"
source = "registry+https://pkg.virgori.com"
checksum = "sha256:55e3ba72b534b4b3b64c126d90697f83b1657ff1fc53b92dc18148a1d65dfcd4"
```

---

## 4. Kho Lưu Trữ Gói Toàn Cục (Global Package Cache)

Mọi gói phụ thuộc được tải từ Registry chỉ lưu trữ **một bản duy nhất** trên toàn máy tại:

```text
~/.vir/packages/
├── vir.json/
│   └── 1.8.3/
├── vir.crypto/
│   └── 2.2.1/
└── foo.http/
    └── 0.9.4/
```

### Kiến Trúc Content-Addressed Storage (CAS)
Song song với thư mục `packages/`, Viron tổ chức `~/.vir/cache/objects/` theo mã băm SHA-256 của từng file. Nếu nhiều phiên bản của cùng một thư viện chia sẻ các tệp mã nguồn giống nhau, CAS sẽ lưu tệp đó một lần duy nhất và dùng hard-link/reflink để tiết kiệm tối đa dung lượng ổ cứng.

---

## 5. Định Dạng Archive Gói Phân Phối (`.tar.zst`)

Gói thư viện được đóng gói dưới định dạng nén siêu nhanh Zstandard:
```text
<package-name>-<version>.tar.zst
```

### Nội dung bắt buộc trong archive:
1. `vir.toml`: Manifest của gói thư viện.
2. `src/`: Thư mục chứa toàn bộ mã nguồn Vir (`.vri`).
3. `LICENSE`: Tệp giấy phép mã nguồn.
4. `README.md` (tùy chọn): Tài liệu hướng dẫn sử dụng.

---

## 6. Mô Hình Phân Giải Phiên Bản (SemVer)

Viron thiết kế mô hình phân giải dữ liệu chuẩn Semantic Versioning ngay từ kiến trúc nền tảng:

| Cú pháp | Ý nghĩa | Ví dụ phân giải |
|---|---|---|
| `=1.2.3` hoặc `1.2.3` | Phiên bản cố định chính xác | Chỉ chấp nhận đúng `1.2.3` |
| `^1.2.3` (Caret) | Tương thích không làm vỡ API (cùng major > 0) | `>= 1.2.3, < 2.0.0` |
| `^0.2.3` | Giữ nguyên minor khi major = 0 | `>= 0.2.3, < 0.3.0` |
| `~1.2.3` (Tilde) | Chỉ chấp nhận thay đổi patch | `>= 1.2.3, < 1.3.0` |
| `>=1.2, <2.0` | Khoảng giá trị tường minh | Bất kỳ phiên bản nào thỏa mãn cả hai |

---

## 7. Quản Lý Cache Bằng CLI

```bash
viron cache path           # Hiển thị đường dẫn thư mục cache (~/.vir/cache)
viron cache info           # Thống kê tổng dung lượng và số lượng gói đã lưu
viron cache clean          # Xóa các tệp tải tạm và download dở dang
viron cache prune          # Xóa các package không còn được dự án nào tham chiếu
```

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/package-format.md` and assigned stable ID `VIRON-SPC-0003` |
