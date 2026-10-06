---
id: "VIRON-SPC-0005"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Security Baseline, Integrity & Concurrency"
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
  - "docs/viron/security.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0005 — Viron v2.0 Architecture — Security Baseline, Integrity & Concurrency

Tài liệu này đặc tả các ranh giới bảo mật cơ sở, cơ chế xác thực toàn vẹn mã hóa, kỹ thuật phòng chống tấn công hệ thống tệp tin, tính nguyên tử trong thao tác và khả năng vận hành an toàn trong môi trường đa tiến trình (concurrency).

---

## 1. Xác Minh Toàn Vẹn Mã Hóa (Cryptographic Integrity)

Mọi gói thư viện và bản phát hành compiler đều trải qua quy trình xác minh đa tầng:

```text
[1] Tải tệp tạm (.part) qua kết nối HTTPS bảo mật
                     │
                     ▼
[2] Tính toán mã băm SHA-256 từ luồng byte thực tế
                     │
                     ▼
[3] Đối chiếu với trường checksum trong vir.lock và registry metadata
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
     Trùng khớp            Không khớp
          │                     │
          ▼                     ▼
Tiến hành giải nén      Báo lỗi VIR4301, xóa ngay tệp tạm,
                        hủy bỏ toàn bộ quá trình cài đặt
```

### Thông Báo Lỗi Chẩn Đoán Khi Lệch Checksum:
```text
error[VIR4301]: package checksum mismatch

package:
    vir.json@1.8.3

expected:
    sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069

actual:
    sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

action:
    package was rejected and removed from download cache
```

---

## 2. Phòng Chống Tấn Công Duyệt Thư Mục (Path Traversal / Tar-Slip Protection)

Khi giải nén gói archive `.tar.zst`, Viron áp dụng bộ lọc đường dẫn nghiêm ngặt:
1. **Chặn đường dẫn tương đối vượt cấp:** Từ chối mọi tệp tin chứa `../` hoặc `..\\` nhằm ngăn chặn việc ghi đè các tệp hệ thống (ví dụ: `../../../etc/passwd` hoặc `~/.ssh/authorized_keys`).
2. **Chặn đường dẫn tuyệt đối:** Bất kỳ tệp nào bắt đầu bằng `/` (Unix) hoặc `C:\` (Windows) đều bị từ chối.
3. **Kiểm soát Symbolic Links:** Các liên kết tượng trưng (symlinks) chỉ được phép trỏ tới các tệp nội bộ nằm bên trong cùng thư mục gốc của package. Nếu symlink trỏ ra ngoài hoặc trỏ tới đường dẫn tuyệt đối, Viron sẽ hủy tiến trình cài đặt ngay lập tức.

---

## 3. Thao Tác Trạng Thái Nguyên Tử (Atomic State Changes)

Nhằm đảm bảo hệ thống không bao giờ bị rơi vào trạng thái hỏng một phần (partial corruption) khi tiến trình bị mất điện hoặc bị người dùng ngắt (`Ctrl+C`):

### Mô hình 4 bước:
```text
Tải về tệp tạm:     ~/.vir/cache/downloads/<id>.part
        │
        ▼
Giải nén thư mục tạm: ~/.vir/cache/downloads/<id>.extracting/
        │
        ▼
Xác nhận tính hợp lệ của manifest và tệp tin
        │
        ▼
Đổi tên nguyên tử (Atomic Rename qua POSIX rename()):
~/.vir/cache/downloads/<id>.extracting/  ──>  ~/.vir/packages/<name>/<version>/
```
> Vì lệnh `rename()` ở cấp độ kernel là nguyên tử (atomic) trên cùng hệ thống tệp, thư mục `packages/<name>/<version>` chỉ xuất hiện khi gói đã hoàn toàn hợp lệ 100%.

---

## 4. An Toàn Trong Môi Trường Đa Tiến Trình (Concurrency Safety)

Khi nhiều tiến trình chạy song song (ví dụ: hai terminal cùng gõ `viron build` trên hai project có chung dependency, hoặc các worker của hệ thống CI):

1. **Khóa Tệp Phân Cấp Cục Bộ (Fine-Grained File Locks):**
   Viron không dùng một khóa toàn cục (global mutex) khóa toàn bộ hệ sinh thái. Thay vào đó, Viron chỉ tạo file lock trên từng package cụ thể:
   ```text
   ~/.vir/cache/locks/<package_name>_<version>.lock
   ```
2. **Kho Lưu Trữ Gói Bất Biến (Immutable Storage):**
   Sau khi một package đã được cài vào `~/.vir/packages/<name>/<version>/`, thư mục này trở thành **Read-Only**. Mọi tiến trình build chỉ đọc dữ liệu từ đây mà không bao giờ chỉnh sửa hay ghi đè.

---

## 5. Chế Độ Vận Hành Bảo Mật Cho Doanh Nghiệp & CI/CD

### Chế độ Offline (`viron build --offline`)
- Ngắt tuyệt đối mọi kết nối mạng (Zero network requests).
- Không kiểm tra cập nhật toolchain, không truy vấn registry index.
- Nếu thiếu bất kỳ package nào trong kho cache, thông báo lỗi tường minh thay vì cố kết nối internet.

### Chế độ Frozen (`viron build --frozen`)
- Dùng cho môi trường production CI/CD.
- Yêu cầu `vir.lock` phải tồn tại và khớp chính xác tuyệt đối với `vir.toml`.
- Cấm Viron tự động giải lại đồ thị hoặc cập nhật lockfile.

---

## 6. Quyền Riêng Tư & An Toàn Bộ Cài Đặt (Privacy & Bootstrap Safety)

- **Không Telemetry Bắt Buộc:** Viron không tự ý thu thập thông tin người dùng, không gửi dữ liệu đo lường từ xa về máy chủ.
- **Không Chạy Daemon Thường Trú:** Viron chỉ chạy khi được người dùng gọi từ dòng lệnh, không có service chạy ngầm làm chậm hệ thống.
- **Kịch bản Bootstrap An Toàn:**
  - Không bao giờ yêu cầu quyền `sudo` hay quyền `root` khi cài đặt. Mọi thành phần đều nằm an toàn trong thư mục người dùng `~/.vir`.
  - Mọi biến trong shell script đều được bọc quote, chạy chế độ `set -e` và `set -u` để tránh lỗi vô tình xóa tệp tin.

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/security.md` and assigned stable ID `VIRON-SPC-0005` |
