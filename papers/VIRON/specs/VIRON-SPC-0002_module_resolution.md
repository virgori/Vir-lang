---
id: "VIRON-SPC-0002"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Canonical Module Resolution & Visibility"
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
  - "docs/viron/module-resolution.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0002 — Viron v2.0 Architecture — Canonical Module Resolution & Visibility

Tài liệu này đặc tả cơ chế định danh module chính quy, thuật toán phân giải tất định duy nhất (Canonical Resolver Pipeline), và quy tắc giới hạn tầm nhìn phụ thuộc nhằm ngăn chặn rò rỉ phụ thuộc ngầm (dependency leakage).

---

## 1. Phân Tách Tuyệt Đối Các Khái Niệm Định Danh

Trong kiến trúc Viron v2.0, bốn khái niệm sau được phân tách rạch ròi, **tuyệt đối không dùng tên file làm định danh module**:

| Khái niệm | Ví dụ | Ý nghĩa |
|---|---|---|
| **Package Identity** | `vir.crypto@2.2.1` | Tên gói và phiên bản phát hành cụ thể |
| **Module Namespace** | `crypto.hash.sha256` | Tên không gian module logic được mã nguồn gọi |
| **Canonical Module Identity** | `vir.crypto@2.2.1::crypto.hash.sha256` | Khóa duy nhất (primary key) đại diện cho module trong toàn bộ hệ thống |
| **Physical File Path** | `~/.vir/packages/vir.crypto/2.2.1/src/hash/sha256.vri` | Vị trí tệp tin thực tế trên ổ đĩa |

---

## 2. Ý Nghĩa Của Canonical Module Identity

Định danh `package@version::namespace.module` được sử dụng xuyên suốt toàn bộ hệ thống để phục vụ:
1. **Khử trùng lặp (Deduplication):** Đảm bảo cùng một module chỉ được parse và phân tích ngữ nghĩa một lần.
2. **Bộ nhớ đệm đa tầng (Multi-tier Caching):** Đánh khóa AST Cache, HIR Cache và MIR Cache.
3. **Phát hiện vòng lặp phụ thuộc (Cycle Detection):** Ngăn chặn import vòng tròn chính xác theo đồ thị logic.
4. **Chẩn đoán lỗi (Diagnostics):** Thông báo chính xác module lỗi thuộc gói nào, phiên bản nào.

---

## 3. Thứ Tự Phân Giải Duy Nhất (Canonical Resolver Pipeline)

Hệ thống chỉ duy trì **duy nhất một luồng phân giải tất định**, không có nhiều resolver chạy song song và không quét ngẫu nhiên filesystem:

```text
[1] Module tương đối (Relative import: ./utils, ../config)
        │ (nếu không khớp)
        ▼
[2] Module nội bộ thuộc package hiện tại
        │ (nếu không khớp)
        ▼
[3] Phụ thuộc trực tiếp khai báo trong vir.toml ([dependencies])
        │ (nếu không khớp)
        ▼
[4] Phụ thuộc bắc cầu được cấp phép hiển thị (Permitted transitive modules)
        │ (nếu không khớp)
        ▼
[5] Module thuộc Toolchain Sysroot (~/.vir/toolchains/<ver>/sysroot/)
        │ (nếu không khớp)
        ▼
[6] Compiler Builtins (native runtime intrinsics)
        │ (nếu không khớp)
        ▼
Báo lỗi phân giải có cấu trúc (VIR4201)
```

---

## 4. Quy Tắc Tầm Nhìn Phụ Thuộc (Dependency Visibility Rule)

### Vấn Đề Lịch Sử Của Các Trình Quản Lý Gói Khác
Trong các hệ thống như `node_modules` phẳng hay Go path cũ, nếu Project A dùng Package B, và Package B dùng Package C:
```text
Project A ──> Package B ──> Package C
```
Project A có thể vô tình `import C` thành công mà không khai báo C trong file cấu hình. Khi Package B gỡ bỏ C hoặc nâng cấp, Project A sẽ bị gãy vỡ âm thầm.

### Quy Tắc Của Viron
**Một dự án chỉ được phép import những thư viện được khai báo rõ ràng trong khối `[dependencies]` của `vir.toml`.**

- Nếu Project A không khai báo `vir.net`, mã nguồn của Project A **tuyệt đối không được import `vir.net`**, ngay cả khi `vir.net` đã nằm sẵn trong kho cache toàn cục do một thư viện khác tải về.
- Viron chặn rò rỉ phụ thuộc này ngay tại bước sinh `module-map.json` trước khi bàn giao cho trình biên dịch.

---

## 5. Ánh Xạ Bí Danh (Module Namespace Alias)

Để giữ code gọn gàng, các official packages có thể xuất ra namespace ngắn gọn thông qua khối `[modules]` trong manifest của package:

```toml
# vir.toml của gói vir.json
[package]
name = "vir.json"
version = "1.8.3"

[modules]
root = "json"
entry = "src/lib.vri"
```

Khi dự án người dùng khai báo `"vir.json" = "^1.8"`, người dùng có thể viết trực tiếp:
```vir
import decode, encode from json
```
thay vì phải gõ tên đầy đủ:
```vir
import decode, encode from vir.json
```
> Viron thực hiện chuyển đổi ánh xạ này trong `module-map.json`, trình biên dịch không cần hardcode bất kỳ danh sách alias nào.

---

## 6. Lệnh Kiểm Tra Phân Giải (`viron resolve`)

Lập trình viên có thể soi chiếu trực tiếp xem một import bất kỳ sẽ dẫn đến file nào:
```bash
viron resolve json
```
Kết quả hiển thị:
```text
Module:       json
Package:      vir.json
Version:      1.8.3
Source:       registry+https://pkg.virgori.com
Physical:     /Users/gengyang/.vir/packages/vir.json/1.8.3/src/lib.vri
Status:       OK (Direct Dependency)
```

Hoặc kiểm tra module con:
```bash
viron resolve crypto.hash.sha256
```
Kết quả:
```text
Module:       crypto.hash.sha256
Package:      vir.crypto
Version:      2.2.1
Source:       registry+https://pkg.virgori.com
Physical:     /Users/gengyang/.vir/packages/vir.crypto/2.2.1/src/hash/sha256.vri
Status:       OK (Direct Dependency)
```

---

## 7. Chẩn Đoán Phân Giải Module Có Cấu Trúc

Nếu xảy ra lỗi, Viron xuất thông báo chẩn đoán có cấu trúc rõ ràng, chỉ rõ nguyên nhân và giải pháp:

```text
error[VIR4201]: module could not be resolved

module:
    crypto.hash

dependency:
    vir.crypto@2.2.1

package root:
    ~/.vir/packages/vir.crypto/2.2.1

reason:
    exported module does not exist in manifest [modules] definition

help:
    check available modules by running: viron resolve vir.crypto
```

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/module-resolution.md` and assigned stable ID `VIRON-SPC-0002` |
