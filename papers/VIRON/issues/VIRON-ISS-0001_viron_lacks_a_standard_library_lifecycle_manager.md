---
id: "VIRON-ISS-0001"
type: "ISSUE"
domain: "VIRON"
title: "Viron lacks a standard library lifecycle manager"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-03"
updated: "2026-10-06"
owners:
  - "VIRON"
components:
  - "cli"
  - "stdlib-lifecycle"
  - "toolchain"
  - "sysroot"
  - "package-cache"
  - "module-resolution"
related:
  issues:
    - "VIRC-ISS-0043"
    - "VIRON-ISS-0002"
    - "VIRON-ISS-0003"
  plans:
    - "VIRC-PLN-0028"
    - "VIRON-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "package-management"
  - "sysroot"
  - "module-map"
  - "integrity"
  - "reproducibility"
---

# VIRON-ISS-0001 — Viron lacks a standard library lifecycle manager

## 1. Summary

Viron chưa có trình quản lý vòng đời thư viện chuẩn dù ranh giới kiến trúc đã
giao trách nhiệm phân phối, cài đặt và cập nhật thư viện cho VIRON. Code đang
hoạt động chỉ có một CLI framework tổng quát và lệnh `pkg` ủy quyền trực tiếp
cho Homebrew; không có lệnh `viron std`, catalog official libraries, cơ chế
chọn phiên bản tương thích compiler, cache bất biến, cài đặt vào sysroot,
kiểm tra integrity, rollback hoặc sinh module map cho stdlib.

Do đó thư viện chuẩn hiện chỉ được nhìn thấy như cây source trong repository
và registry tĩnh `stdlib/stdlib.vri`. Người dùng chưa có một lifecycle do Viron
sở hữu để cài, liệt kê, cập nhật, xác minh hoặc phục hồi stdlib độc lập với
binary Viron, compiler toolchain và dependency của project.

## 2. Context

Issue được audit tại revision `e65d6853073ba43d48932fd23a9ccd3fcac2613e`
ngày 2026-10-03.

Các SPEC VIRON đang ở trạng thái DRAFT nhưng đã mô tả cùng một ranh giới dự
kiến:

- `VIRON-SPC-0001`: Viron sở hữu distribution/lifecycle, tải compiler và
  stdlib, quản lý immutable cache, tạo `module-map.json`, và truyền sysroot cho
  compiler; `virc` không được tự truy cập registry hoặc tự tải thư viện.
- `VIRON-SPC-0002`: Viron sở hữu canonical module resolution và module map.
- `VIRON-SPC-0003`: package manifest, lockfile và cache layout.
- `VIRON-SPC-0004`: registry protocol và package lifecycle.
- `VIRON-SPC-0005`: integrity, atomic install và security baseline.
- `VIRON-SPC-0006`: sysroot/toolchain layout và bốn namespace cập nhật độc
  lập, trong đó `viron std update [pkg]` chỉ cập nhật official libraries.

STLB vẫn sở hữu nội dung, public API và compatibility policy của thư viện
chuẩn. Việc phân phối, cài đặt, chọn phiên bản, cache và tích hợp toolchain là
trách nhiệm VIRON; issue này không chuyển ownership nội dung stdlib sang Viron.

## 3. Expected Behavior

- Viron có namespace `std` riêng, ít nhất hỗ trợ discover/list, install,
  update, remove khi an toàn, verify và repair/rollback cho official libraries.
- Phiên bản stdlib được chọn từ metadata phát hành có xác thực và được kiểm tra
  compatibility với compiler/toolchain, target và schema module registry.
- Nội dung tải về được xác minh checksum/signature trước khi publish nguyên tử
  vào immutable cache hoặc sysroot; thất bại không phá installation đang dùng.
- Trạng thái cài đặt ghi lại phiên bản chính xác và nguồn/provenance, không giữ
  channel trôi nổi làm kết quả cuối cùng.
- `viron std update` không tự cập nhật Viron, compiler toolchain hoặc dependency
  project; các lifecycle này giữ ranh giới command riêng.
- Viron materialize stdlib/sysroot và module map tất định để compiler chỉ đọc
  input cục bộ đã được phân giải.
- Offline/frozen mode dùng được khi artifact cần thiết đã có trong cache và
  báo lỗi rõ khi thiếu.
- CLI và lifecycle có integration tests cho success, incompatibility, corrupt
  download, interrupted install, rollback và concurrent invocation.

## 4. Actual Behavior

### 4.1 Không có stdlib lifecycle command

`stdlib/vir/viron/viron.vri` chỉ quảng bá các nhóm `maha`, `net`, `proc`, `fs`,
`svc`, `pkg`, `user` và `sys`. Không có category, command registration hay
dispatcher cho `std`, `toolchain`, `build`, `doctor` hoặc lifecycle được mô tả
trong các SPEC VIRON.

Toàn repository không có caller cho `viron_dispatch`, `registry_new` hoặc
`pkg_dispatch` ngoài chính nơi khai báo. Vì vậy ngay cả `pkg` hiện cũng chưa
được chứng minh là một command end-to-end có entrypoint/registration hoạt động.

### 4.2 `pkg` quản lý package hệ điều hành, không quản lý package Vir

`stdlib/vir/viron/pkg_cmd.vri` map `install`, `remove`, `update`, `upgrade`,
`search`, `list` và `info` trực tiếp sang executable `brew`. Module này không
đọc registry Vir, manifest/lockfile, metadata official library, checksum,
compatibility hay sysroot. Hành vi đó không thể thay thế `viron std` và không
portable sang host không có Homebrew.

### 4.3 Stdlib được resolve từ source-tree registry tĩnh

`stdlib/stdlib.vri` là registry module tĩnh với root tương đối `vir`. Compiler
hiện tự dò file này từ `stdlib/stdlib.vri`, `../stdlib/stdlib.vri` hoặc
`../../stdlib/stdlib.vri` khi không tìm được từ include base. Không có state do
Viron quản lý nối một stdlib release đã cài với toolchain đang chọn.

### 4.4 Test Viron không kiểm tra CLI hoặc stdlib lifecycle

`tests/bootstrap_codegen/cg_viron_cli.vri` tự định nghĩa parser SemVer, mô hình
package và topo-sort trong fixture. Test không include/call module Viron, không
dispatch command, không truy cập registry/cache/sysroot và không kiểm tra bất kỳ
thao tác stdlib nào. Tên test vì thế đang thể hiện coverage rộng hơn coverage
thực tế.

## 5. Reproduction

Từ repository root:

```sh
find stdlib/vir/viron -maxdepth 2 -type f -print | sort

rg -n 'std|toolchain|sysroot|module-map|vir\.lock|checksum|rollback' \
  stdlib/vir/viron --glob '*.vri'

rg -n 'pkg_dispatch|viron_dispatch|registry_new\(' . \
  --glob '!papers/**' --glob '!docs/**' --glob '!compiler/generated/**' \
  --glob '!target/**' --glob '!build/**'

rg -n 'command_new|brew' stdlib/vir/viron/pkg_cmd.vri

rg -n 'viron|pkg_dispatch|std|sysroot|module-map' \
  tests/bootstrap_codegen/cg_viron_cli.vri
```

Kết quả tại revision audit:

- thư mục Viron không có module `std` hoặc toolchain/sysroot manager;
- tìm kiếm lifecycle chỉ khớp các khai báo dispatcher hiện có, không có stdlib
  implementation;
- mọi thao tác trong `pkg_cmd.vri` gọi `brew`;
- test Viron không gọi implementation Viron và không đề cập lifecycle stdlib.

## 6. Evidence

- CONFIRMED: `stdlib/vir/viron/viron.vri:26-35` không có command category cho
  standard library; help tại dòng 159-167 không công bố `std`.
- CONFIRMED: `stdlib/vir/viron/pkg_cmd.vri:71-196` thực thi `brew install`,
  `brew uninstall`, `brew update`, `brew upgrade`, `brew search`, `brew list`
  và `brew info`; không có Vir registry/cache/sysroot path.
- CONFIRMED: repository search chỉ thấy `viron_dispatch` và `pkg_dispatch` tại
  declaration của chúng; không có active entrypoint đăng ký hoặc gọi hai hàm.
- CONFIRMED: `stdlib/stdlib.vri` đăng ký module stdlib bằng đường dẫn source
  tương đối và `compiler/src/main.vri:1438-1451` tự tìm registry trong cây thư
  mục làm việc.
- CONFIRMED: `tests/bootstrap_codegen/cg_viron_cli.vri:40-150` chứa SemVer/DAG
  implementation riêng của test và dòng 158-201 chỉ test các helper đó.
- OBSERVED: sáu VIRON SPEC hiện đều là DRAFT; chúng là intended architecture,
  không phải bằng chứng implementation đã hoàn thành.
- NOT_VERIFIED: registry/CDN production, release metadata hay artifact stdlib
  tồn tại ngoài repository; không có client code hoặc fixture trong scope đã
  audit để chứng minh contract đó.

## 7. Scope

### Affected

- cài đặt và cập nhật official standard libraries;
- compatibility compiler–stdlib và reproducibility của toolchain;
- sysroot/module-map provisioning cho compiler;
- integrity, atomicity, offline use, rollback và repair;
- CLI ownership giữa `std`, `toolchain`, project dependencies và host packages;
- test coverage của Viron distribution lifecycle.

### Not affected / Unknown

- Nội dung và public API của từng module stdlib vẫn thuộc STLB.
- Issue không yêu cầu compiler truy cập network hoặc tự làm package manager.
- Issue không quyết định mọi official library phải nằm trong sysroot; ranh giới
  compiler-coupled runtime so với independently versioned `vir.*` packages cần
  được chốt trong PLAN/SPEC trước triển khai.
- Correctness của từng implementation stdlib không được audit tại đây.
- Registry/CDN production và signing infrastructure ngoài repository là
  unknown.

## 8. Impact

Không có lifecycle này, một binary compiler được tách khỏi checkout chưa có
đường chuẩn để nhận đúng stdlib; build phụ thuộc layout source tree và trạng
thái thủ công. Người dùng không thể cập nhật hoặc phục hồi official libraries
độc lập, cũng không có bằng chứng phiên bản/tính toàn vẹn có thể audit.

Khoảng trống này chặn mục tiêu portable toolchain và khiến responsibility dễ
trôi ngược vào compiler hoặc script ad-hoc. Severity là S2 vì nó ảnh hưởng chức
năng phân phối cốt lõi, reproducibility và supply-chain boundary; chưa có bằng
chứng gây mất dữ liệu hay compromise đang xảy ra. Priority P1 vì module hóa và
tách compiler khỏi source-tree stdlib cần contract VIRON này sớm.

## 9. Preliminary Analysis

- CONFIRMED: gap không phải chỉ thiếu một subcommand. Nó bao gồm model release,
  compatibility contract, storage state, transaction boundary, module-map
  output và verification matrix.
- CONFIRMED: tái sử dụng `pkg_cmd.vri` hiện tại sẽ sai domain vì module đó quản
  lý Homebrew packages và không có primitive/package model của Vir ecosystem.
- OBSERVED: `VIRON-SPC-0001` đến `VIRON-SPC-0006` đã phân tán phần lớn desired
  behavior nhưng chưa hợp nhất thành một contract stdlib lifecycle có acceptance
  matrix rõ ràng.
- HYPOTHESIS: cần một subsystem riêng dưới Viron (`std` command + service/store
  layer) dùng chung registry/cache/integrity primitive với package manager,
  thay vì nhúng network/filesystem mutation trực tiếp vào CLI handler.
- HYPOTHESIS: compiler-coupled core/runtime nên phát hành cùng toolchain sysroot,
  còn official libraries version độc lập nên ở immutable package cache; module
  map hợp nhất cả hai. Quyết định này cần PLAN và cập nhật SPEC trước code.
- NOT_VERIFIED: format metadata/version compatibility chính thức và migration
  path từ `stdlib/stdlib.vri` sang installed registry/module map.

## 10. Acceptance Criteria

- [ ] Một PLAN liên kết issue này xác định rõ ownership VIRON/STLB/VIRC và phân
  loại stdlib nào compiler-coupled, stdlib nào independently versioned.
- [ ] Contract release/compatibility cho compiler, sysroot, registry schema và
  official libraries được chuẩn hóa, versioned và có diagnostics xác định.
- [ ] Viron có `std` command family hoạt động end-to-end; command registration,
  help, exit codes và structured diagnostics đều có test.
- [ ] Install/update/verify dùng authenticated metadata, checksum/signature,
  staging và atomic publish; corrupt hoặc interrupted operation giữ nguyên
  installation tốt gần nhất.
- [ ] Installed state ghi exact versions, provenance và compatibility; channel
  trôi nổi không được ghi làm resolved state.
- [ ] `std`, `self`, `toolchain` và project dependency update không gây side
  effect chéo ngoài contract công khai.
- [ ] Viron tạo sysroot/module map tất định từ resolved local state và compiler
  build được từ ngoài repository mà không dò `./stdlib` hoặc `../stdlib`.
- [ ] Offline/frozen, rollback/repair và concurrent invocation có integration
  tests, bao gồm negative cases thiếu cache, incompatible release và checksum
  mismatch.
- [ ] Test Viron sử dụng implementation production thay vì chép lại SemVer/DAG
  logic trong fixture; tên/coverage test phản ánh đúng behavior kiểm chứng.
- [ ] Tài liệu `module.list` của mọi project Vir liên quan được cập nhật khi
  thêm/move module, và source mới dùng stdlib qua canonical include/import.
- [ ] `./paper validate` và toàn bộ test suite liên quan đều pass trước closure.

## 11. Related Papers

### Issues

- `VIRON-ISS-0002` — executable library-development workflow required before
  the standard-library lifecycle can be implemented end-to-end.
- `VIRON-ISS-0003` — umbrella issue tracking integration across project,
  toolchain, package, registry and standard-library lifecycles.

### Plans

- `VIRON-PLN-0001` — end-to-end plan; Phase 0 chốt package split/compatibility
  contract và Phase 7 triển khai standard-library lifecycle.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Opened and triaged the missing Viron standard-library lifecycle manager. |
| 2026-10-03 | Linked VIRON-ISS-0002 |
| 2026-10-03 | Linked VIRON-ISS-0003 |
| 2026-10-03 | Linked VIRON-PLN-0001 |
| 2026-10-06 | Linked VIRC-ISS-0043 |
| 2026-10-06 | Linked VIRC-PLN-0028 |
