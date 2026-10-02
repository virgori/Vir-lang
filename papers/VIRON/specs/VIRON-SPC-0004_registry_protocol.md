---
id: "VIRON-SPC-0004"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Vir Registry Protocol & Package Lifecycle"
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
  - "docs/viron/registry.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0004 — Viron v2.0 Architecture — Vir Registry Protocol & Package Lifecycle

Tài liệu này đặc tả giao thức Vir Registry chính thức, cấu trúc metadata sparse index, quy trình phân giải trước khi tải, chính sách bất biến của bản phát hành, cơ chế yank và hỗ trợ registry nội bộ/enterprise.

---

## 1. Điểm Truy Cập Mặc Định & Cấu Hình Mirror

Các điểm truy cập chính thức của hệ sinh thái Virgori:
```text
Registry metadata: https://pkg.virgori.com
Compiler/stdlib CDN: https://cdn.virgori.com
Bootstrap installer: https://get.virgori.com
```

### Cấu Hình Registry Linh Hoạt (`~/.vir/config.toml`)
Viron không bao giờ hardcode URL registry trong lõi mã nguồn. Người dùng và doanh nghiệp có thể cấu hình mirror hoặc private registry:

```toml
[registry]
default = "https://pkg.virgori.com"

# Cấu hình mirror tăng tốc độ tại các khu vực địa lý:
[registry.mirrors]
"https://pkg.virgori.com" = [
    "https://mirror.virgori.internal"
]

# Cấu hình private registry cho doanh nghiệp:
[registries.mycorp]
index = "https://vir.mycorp.internal/index"
token = "env:MYCORP_VIR_TOKEN"
```

> **Nguyên Tắc Độc Lập:**
> Vir Registry là một giao thức độc lập. **Tuyệt đối không đồng nhất `package == GitHub repository`**. GitHub chỉ có thể được dùng làm bản sao lưu trữ tải về, nhưng hệ thống metadata và chỉ mục bắt buộc nằm trong đặc tả của Vir Registry Protocol.

---

## 2. Siêu Dữ Liệu Chỉ Mục (Sparse Index & Metadata)

Để tối ưu hóa băng thông và cho phép phân giải đồ thị phụ thuộc cực nhanh mà **không cần tải về file nén mã nguồn**, Vir Registry cung cấp API metadata dạng JSON:

### Endpoint Metadata:
```text
GET /v1/packages/<package_name>
```

### Định Dạng Metadata JSON:
```json
{
  "name": "vir.json",
  "description": "High-performance native JSON parser and serializer for Vir",
  "repository": "https://github.com/virgori/Vir-lang",
  "versions": {
    "1.8.2": {
      "checksum": "sha256:4a6f23b7e8...",
      "archive_url": "https://cdn.virgori.com/packages/vir.json-1.8.2.tar.zst",
      "dependencies": {
        "vir.core": "^3.0"
      },
      "vir": ">=3.0,<4.0",
      "yanked": false
    },
    "1.8.3": {
      "checksum": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
      "archive_url": "https://cdn.virgori.com/packages/vir.json-1.8.3.tar.zst",
      "dependencies": {
        "vir.core": "^3.1"
      },
      "vir": ">=3.1,<4.0",
      "yanked": false
    }
  }
}
```

### Quy Trình Phân Giải Trước (Pre-download Resolution):
1. Resolver của Viron chỉ tải tệp JSON metadata nhỏ gọn của các gói liên quan.
2. Xây dựng đồ thị phụ thuộc và giải thuật toán SemVer trên bộ nhớ RAM.
3. Chỉ khi toàn bộ đồ thị phụ thuộc hợp lệ và không có xung đột, Viron mới tiến hành tải archive `.tar.zst` của các gói còn thiếu.

---

## 3. Tính Bất Biến Của Bản Phát Hành (Package Immutability)

- Một khi gói thư viện đã được xuất bản với cặp `(tên_gói, phiên_bản)` lên Vir Registry, **nội dung và checksum của phiên bản đó là bất biến vĩnh viễn**.
- Tác giả không thể ghi đè (re-publish) hoặc sửa đổi file nén đã phát hành.
- Nếu client phát hiện mã băm SHA-256 từ registry bị thay đổi so với giá trị đã lưu trong `vir.lock` hoặc cache địa phương, Viron sẽ lập tức kích hoạt cảnh báo toàn vẹn nghiêm trọng (`error[VIR4301]`) và từ chối nạp gói.

---

## 4. Cơ Chế Rút Gói (Registry Yank Semantics)

Khi phát hiện phiên bản thư viện có lỗ hổng bảo mật nghiêm trọng hoặc lỗi chí mạng, tác giả có thể thực hiện "yank":

```bash
viron yank vir.json --version 1.8.2
```

### Ý Nghĩa Ngữ Nghĩa Của Yank:
1. **Dự án cũ không bị phá vỡ:** Các dự án đã có phiên bản `1.8.2` trong tệp `vir.lock` vẫn được phép tiếp tục tải và build bình thường.
2. **Không chọn cho dự án mới:** Thuật toán phân giải phụ thuộc (Dependency Solver) của các dự án mới hoặc khi chạy `viron update` sẽ tự động bỏ qua phiên bản đã bị yank và chọn phiên bản an toàn khác.
3. **Không xóa vĩnh viễn:** Tệp archive vẫn được giữ trên storage để bảo đảm tính tái lập của các hệ thống đang chạy ổn định.

---

## 5. Quy Trình Xuất Bản Gói (Publishing Commands)

```bash
# Đăng nhập vào Registry:
viron login

# Đóng gói và phát hành lên Registry:
viron publish

# Rút một phiên bản lỗi:
viron yank <package> --version <version>

# Phục hồi phiên bản đã yank:
viron unyank <package> --version <version>

# Quản lý quyền sở hữu gói:
viron owner add <username> <package>
viron owner remove <username> <package>
```

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/registry.md` and assigned stable ID `VIRON-SPC-0004` |
