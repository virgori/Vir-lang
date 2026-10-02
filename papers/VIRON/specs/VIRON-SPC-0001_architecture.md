---
id: "VIRON-SPC-0001"
type: "SPEC"
domain: "VIRON"
title: "Viron v2.0 Architecture — Core Architecture & Responsibilities"
status: "DRAFT"
version: "1.0.0"
language: "vi"
spec_class: "ARCHITECTURE"
created: "2026-10-02"
updated: "2026-10-02"
owners:
  - "VIRON"
components: []
aliases:
  - "docs/viron/architecture.md"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "migrated-from-docs"
---

# VIRON-SPC-0001 — Viron v2.0 Architecture — Core Architecture & Responsibilities

Tài liệu này xác định nguyên tắc kiến trúc cốt lõi, sự phân định trách nhiệm tuyệt đối giữa **Viron** và **virc**, luồng điều phối biên dịch và các quy tắc bất biến của hệ sinh thái Vir.

---

## 1. Phân Định Ranh Giới Giữa Viron và virc

Hệ sinh thái Vir phân tách nghiêm ngặt ranh giới giữa hai tầng:

```text
Language / Compiler (virc)
        ↓
Lifecycle & Toolchain Management (Viron)
        ↓
Standard / Third-party Libraries
        ↓
Operating System / Architecture
```

### Trách Nhiệm Của Viron
- Quản lý toàn bộ vòng đời phân phối (Distribution & Lifecycle).
- Cài đặt, chuyển đổi, gỡ bỏ và cập nhật đa toolchain.
- Quản lý metadata dự án (`vir.toml`) và khóa phụ thuộc (`vir.lock`).
- Giao tiếp mạng với Vir Registry (`https://pkg.virgori.com`), tải archive compiler/stdlib từ `https://cdn.virgori.com` và xác thực tính toàn vẹn.
- Giải quyết đồ thị phụ thuộc (Dependency Resolution) dựa trên SemVer.
- Quản lý kho lưu trữ gói toàn cục (Global Immutable Cache) dùng chung giữa các dự án.
- Thiết lập môi trường và dispatching compiler/LSP qua shim.
- Chuẩn bị bản đồ module (`module-map.json`) và bàn giao cho compiler.
- Chẩn đoán hệ thống (`viron doctor`), sao lưu, phục hồi và rollback.

### Trách Nhiệm Của virc (Compiler)
- Lexing và parsing mã nguồn `.vri`.
- Phân tích ngữ nghĩa qua 10 passes: symbol resolution, typecheck, CFA, borrow checker.
- Chuyển đổi trung gian HIR → MIR (SSA) → LIR.
- Tối ưu hóa đa tầng (26 optimization passes: TCO, DCE, GVN, SCCP, Inlining, RegAlloc...).
- Sinh mã máy AOT native (Mach-O ARM64, ELF ARM64/x86_64, WASM).

> **Bất Biến Compiler (Compiler Invariants):**
> `virc` **TUYỆT ĐỐI KHÔNG**:
> 1. Thực hiện bất kỳ network request nào.
> 2. Truy cập registry hoặc tải package từ internet.
> 3. Tự phân giải phiên bản gói phụ thuộc từ xa.
> 4. Tự động cập nhật chính nó hoặc tải thư viện ngoài sysroot.
> 5. Quét tìm thư viện ngẫu nhiên trong thư mục làm việc (`./stdlib`, `../stdlib`).

---

## 2. Luồng Điều Phối Biên Dịch (Build Orchestration Flow)

Khi lập trình viên thực hiện lệnh:
```bash
viron build
```

Viron thực hiện chuỗi 12 bước điều phối tất định (deterministic orchestration):

```text
  [1] Định vị thư mục gốc dự án (tìm vir.toml)
                        │
                        ▼
  [2] Phân tích cú pháp vir.toml
                        │
                        ▼
  [3] Xác định phiên bản toolchain yêu cầu ([toolchain].vir)
                        │
                        ▼
  [4] Đảm bảo toolchain yêu cầu đã được cài đặt trong ~/.vir/toolchains/
                        │
                        ▼
  [5] Nạp file khóa vir.lock (nếu chưa có hoặc vir.toml đổi, chạy solver)
                        │
                        ▼
  [6] Kiểm tra kho cache toàn cục ~/.vir/packages/
                        │
                        ▼
  [7] Tải các gói còn thiếu từ Registry về thư mục tạm
                        │
                        ▼
  [8] Xác minh mã băm SHA-256 và giải nén nguyên tử (atomic rename)
                        │
                        ▼
  [9] Khởi tạo tệp ánh xạ module .vir/build/module-map.json
                        │
                        ▼
  [10] Gọi binary virc tương ứng kèm --sysroot và --module-map
                        │
                        ▼
  [11] Compiler biên dịch mã nguồn thành file thực thi trong target/debug/
                        │
                        ▼
  [12] Lan truyền chẩn đoán lỗi có cấu trúc (structured diagnostics) về người dùng
```

---

## 3. Bản Đồ Module (`module-map.json`)

`virc` không cần biết registry hay vị trí cache toàn cục của Viron. Viron chịu trách nhiệm tổng hợp toàn bộ cây phụ thuộc đã phân giải thành một tệp bản đồ duy nhất:

```json
{
  "toolchain": {
    "version": "3.2.0",
    "sysroot": "/Users/gengyang/.vir/toolchains/3.2.0/sysroot"
  },
  "packages": {
    "vir.json": {
      "version": "1.8.3",
      "root": "/Users/gengyang/.vir/packages/vir.json/1.8.3"
    },
    "vir.crypto": {
      "version": "2.2.1",
      "root": "/Users/gengyang/.vir/packages/vir.crypto/2.2.1"
    }
  },
  "modules": {
    "json": {
      "package": "vir.json",
      "entry": "/Users/gengyang/.vir/packages/vir.json/1.8.3/src/lib.vri"
    },
    "crypto": {
      "package": "vir.crypto",
      "entry": "/Users/gengyang/.vir/packages/vir.crypto/2.2.1/src/lib.vri"
    }
  }
}
```

---

## 4. Chế Độ Standalone Của Compiler (`virc`)

Nhằm phục vụ quá trình phát triển nội bộ và kiểm thử compiler độc lập, `virc` vẫn hỗ trợ chạy trực tiếp không qua Viron:
```bash
# Chỉ định rõ ràng sysroot và module-map
virc src/main.vri \
    --sysroot ~/.vir/toolchains/3.2.0/sysroot \
    --module-map .vir/build/module-map.json \
    -o target/app

# Chỉ định đường dẫn include phát triển (chỉ dùng cho compiler hacking)
virc test.vri -I ../stdlib -o /tmp/test
```
*Cờ `-I` là tùy chọn phát triển cấp thấp, không được coi là hệ thống quản lý gói chính.*

---

## 5. Các Nguyên Tắc Kiến Trúc Bất Biến

1. **Viron sở hữu sự phân phối và vòng đời.**
2. **virc sở hữu sự biên dịch tất định.**
3. **Vir Registry sở hữu siêu dữ liệu gói đã phát hành.**
4. **`vir.lock` sở hữu sự lựa chọn phụ thuộc có thể tái lập 100%.**
5. **Sysroot sở hữu các thành phần runtime gắn liền với compiler.**
6. **Global Cache sở hữu nội dung gói bất biến theo nội dung.**
7. **Dự án sở hữu mã nguồn, manifest, lockfile và artifact đầu ra trong `target/`.**

## 99. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-02 | 1.0.0 | Migrated from `docs/viron/architecture.md` and assigned stable ID `VIRON-SPC-0001` |
