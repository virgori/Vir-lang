---
id: "VIR-ISS-0009"
type: "ISSUE"
domain: "VIR"
title: "Compiler versions need calendar-year release and internal patch channels"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "language"
  - "compiler"
components:
  - "compiler-version"
  - "release-process"
  - "binary-distribution"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "calendar-versioning"
  - "release"
  - "internal-patch"
---

# VIR-ISS-0009 — Compiler versions need calendar-year release and internal patch channels

## 1. Summary

Compiler đang công bố version `4.2.1`, không thể hiện năm phát hành và không có
quy ước phân biệt bản chính thức với bản vá nội bộ. Vir cần một contract thống
nhất: `YYYY.R` là bản chính thức, `YYYY.R.P` là bản vá nội bộ, và mỗi ISSUE làm
thay đổi compiler khi hoàn tất phải bump version đúng một lần.

## 2. Context

Version hiện được hard-code trong `compiler/src/main/driver/config.vri`, sau đó
được đồng bộ vào `compiler/generated/virc.vri` và bootstrap thành `bin/virc`.
Ba số hiện còn được dùng làm tuple so sánh với `compiler_min` trong sysroot.

Quy ước mới giữ tuple ba số cho compatibility nội bộ nhưng thay ý nghĩa thành
`(year, release, internal_patch)`. Bản chính thức ẩn patch `0` khỏi public
version; bản nội bộ hiển thị đầy đủ patch dương.

## 3. Expected Behavior

- Bản chính thức dùng `YYYY.R`; bản đầu tiên theo quy ước này là `2026.1`.
- Bản vá nội bộ dùng `YYYY.R.P`, với `P >= 1`.
- `YYYY` là năm phát hành; `R` tăng khi phát hành bản chính thức trong cùng năm.
- Khi phát hành chính thức, internal patch reset về `0` và không được hiển thị.
- GitHub tag dùng `vYYYY.R.0` để tương thích SemVer; CLI/banner chỉ hiển thị
  `YYYY.R`, không có tiền tố `v` hoặc suffix `.0`.
- Mỗi `VIR-ISS` hoặc `VIRC-ISS` hoàn tất có thay đổi compiler phải sở hữu đúng
  một version bump. Mặc định tăng internal patch; release được phê duyệt tăng
  `R` và reset patch.
- Canonical metadata, compiler source, generated bundle và binary phát hành phải
  báo cùng version.

## 4. Actual Behavior

- `bin/virc --version` báo `virc 4.2.1 (self-hosted)`.
- Source metadata dùng tuple `(4, 2, 1)` theo hình thức SemVer cũ.
- Không có canonical version record, lệnh bump idempotent theo ISSUE, hoặc gate
  bắt buộc agent bump trước khi báo hoàn tất.

## 5. Reproduction

```sh
./bin/virc --version
rg -n 'vircVersion(Number|Major|Minor|Patch)' compiler/src/main/driver/config.vri
```

Kết quả trước thay đổi là public version `4.2.1` và các component `4/2/1`.

## 6. Evidence

- OBSERVED ngày 2026-10-07: `./bin/virc --version` in `virc 4.2.1
  (self-hosted)`.
- CONFIRMED: `compiler/src/main/driver/config.vri` là canonical source cho bốn
  hàm version; `tools/sync_virc.py` sinh bundle từ source này.
- CONFIRMED: `compiler/src/main/driver/sysroot.vri` so sánh ba component của
  compiler với `compiler_min`.
- CONFIRMED: `bin/` bị Git ignore, nên release binary phải được rebuild và kiểm
  chứng riêng, không thể suy ra từ source diff.
- OBSERVED ngày 2026-10-07 sau migration: bootstrap Stage 2 và Stage 3
  byte-identical với SHA-256
  `2f914a403e1087d97f3bf15fc49ab07249629ba8c7386d4d78ddda7c5557ffaa`;
  `bin/virc --version` báo `virc 2026.1 (self-hosted)` và strict codesign verify
  thành công.
- OBSERVED ngày 2026-10-07: 43/43 CLI contracts, 42/42 sysroot contracts,
  version-policy regression, generated-source sync và VPS validation đều pass.
- OBSERVED ngày 2026-10-07 cho release build cuối: banner in `2026.1` không có
  `v`, Stage 2/3 byte-identical với SHA-256
  `2b2d2d23b08dbfce765734f92ec886f69b70c72b62cb104bc68cd0cf7a431ad7`.

## 7. Scope

### Affected

- compiler version metadata và CLI/banner;
- generated compiler bundle và bootstrap binary;
- workflow hoàn tất compiler ISSUE;
- regression/baseline có chứa public compiler version.

### Not affected / Unknown

- Version của VPS, SPEC paper, stdlib ABI/protocol và VS Code extension không tự
  đổi theo compiler version.
- Historical papers giữ nguyên version đã quan sát tại thời điểm lập paper.
- Quy ước không thay đổi Vir source-language syntax hoặc runtime ABI.

## 8. Impact

Không có contract, các binary cùng source có thể công bố version khác nhau và
một fix hoàn tất không tạo identity mới để truy vết. Calendar version cho biết
ngay năm/release, còn internal patch giữ khả năng phân biệt các build chưa phát
hành mà không giả vờ là một official release mới.

## 9. Preliminary Analysis

- CONFIRMED: tuple ba component hiện đủ để ánh xạ trực tiếp sang
  `(year, release, internal_patch)` mà không thay layout hay API sysroot.
- CONFIRMED: official form hai component vẫn có thể dùng patch số `0` bên trong
  cho comparison, trong khi CLI chỉ hiển thị `YYYY.R`.
- HYPOTHESIS: version bump idempotent theo ISSUE sẽ giảm double-bump khi một
  agent retry workflow hoặc tiếp tục một issue đang dở.
- NOT_VERIFIED: policy phát hành package ngoài compiler repo.

## 10. Acceptance Criteria

- [x] Canonical compiler version được chuyển sang official `2026.1` với tuple
  nội bộ `(2026, 1, 0)`.
- [x] Public CLI/banner dùng `YYYY.R` cho official và schema cho phép
  `YYYY.R.P` với internal patch dương.
- [x] Official GitHub tag `vYYYY.R.0` được ánh xạ rõ sang CLI `YYYY.R`, không
  in tiền tố `v`.
- [x] Có canonical machine-readable record và lệnh bump idempotent theo ISSUE.
- [x] Mandatory Vir agent guidance yêu cầu bump đúng một lần khi compiler ISSUE
  hoàn tất.
- [x] Generated bundle, regression policy và dynamic CLI expectation được đồng
  bộ với canonical version.
- [x] `bin/virc` được bootstrap lại, báo `2026.1`, và đạt fixed point của workflow
  release hiện hành.

## 11. Related Papers

### Issues

- None.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Opened the calendar-versioning contract and recorded the initial `2026.1` migration evidence |
| 2026-10-07 | Recorded the byte-identical Stage 2/3 bootstrap, `2026.1` binary output, and strict signature verification |
| 2026-10-07 | Added final CLI, sysroot, version-policy, generated-source, and VPS validation evidence |
| 2026-10-07 | Clarified the `vYYYY.R.0` release-tag mapping and required prefix-free `YYYY.R` CLI/banner output |
| 2026-10-07 | Verified the prefix-free `2026.1` release banner and final byte-identical bootstrap |
