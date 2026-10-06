---
id: "VIRON-ISS-0002"
type: "ISSUE"
domain: "VIRON"
title: "Viron lacks an executable library development workflow"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRON"
components:
  - "cli"
  - "library-development"
  - "project-scaffolding"
  - "manifest-lockfile"
  - "package-resolution"
  - "module-map"
  - "testing"
  - "release-pipeline"
related:
  issues:
    - "VIRON-ISS-0001"
    - "VIRON-ISS-0003"
  plans:
    - "VIRON-PLN-0001"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "blocker"
  - "developer-workflow"
  - "package-manager"
  - "module-list"
  - "ci-cd"
  - "bootstrap"
---

# VIRON-ISS-0002 — Viron lacks an executable library development workflow

## 1. Summary

Viron chưa tồn tại như một công cụ thực thi end-to-end để tạo, kiểm tra, build,
test, đóng gói và chuẩn bị phát hành thư viện Vir. Repository có các mảnh CLI,
SemVer, manifest và package resolver, nhưng chúng chưa hợp thành một executable,
không qua được kiểm tra compiler hiện tại, và không có workflow phát triển thư
viện cục bộ có thể dùng hoặc kiểm thử.

Đây là blocker cho phát triển thư viện ở cấp hệ sinh thái: tác giả có thể sửa
source `.vri` trực tiếp trong monorepo và gọi `virc` thủ công, nhưng chưa thể
chứng minh một thư viện là một package Vir độc lập, resolve dependency theo cùng
contract với người dùng, chạy test qua toolchain đã chọn, tạo artifact bất biến,
hay đưa chính workflow đó vào CI/CD.

## 2. Context

Issue được audit tại revision `e65d6853073ba43d48932fd23a9ccd3fcac2613e`
ngày 2026-10-03. `VIRON-ISS-0001` đã ghi nhận riêng việc thiếu lifecycle manager
cho official standard libraries. Issue này rộng hơn ở development plane: trước
khi triển khai Registry/CDN production, Viron phải có một vòng lặp local-first
đủ dùng để chính các thư viện Vir được phát triển và kiểm chứng.

Các `VIRON-SPC-0001` đến `VIRON-SPC-0006` mô tả intended architecture cho
`vir.toml`, `vir.lock`, toolchain, module map, cache, registry và publish, nhưng
tất cả vẫn ở trạng thái DRAFT. Audit này dùng source và test hiện tại làm bằng
chứng implementation, không coi nội dung SPEC là chức năng đã tồn tại.

## 3. Expected Behavior

- Repository tạo được một executable `viron` từ canonical Vir source và project
  có `module.list` riêng, thay vì chỉ đăng ký `viron` như một module stdlib.
- Tác giả thư viện có workflow local tối thiểu và ổn định: tạo/scaffold library,
  validate manifest và `module.list`, check, build, test và package.
- Project scaffold bắt buộc có `vir.toml`, `module.list`, `src/lib.vri` và test
  layout; canonical module IDs không phụ thuộc đường dẫn checkout hay CWD.
- Local path dependencies hoạt động không cần network; registry dependencies
  được resolve vào exact versions/checksums và ghi `vir.lock` tất định.
- Viron tạo `module-map.json`, chọn toolchain/sysroot tương thích, rồi gọi
  compiler với input tường minh. Compiler không tự tải package.
- `package` tạo archive có manifest, module registry, license/provenance và
  checksum; `publish --dry-run` kiểm tra đầy đủ mà không mutation remote.
- CI/CD gọi đúng các command production giống developer local; pipeline không
  reimplement resolver/package logic bằng script riêng.
- Tests chạy vào implementation thật và phủ cả success lẫn negative paths;
  placeholder test không được tính là bằng chứng Viron hoạt động.

## 4. Actual Behavior

### 4.1 Không có executable hay project Viron độc lập

`bin/` chỉ có `virc` và `vir-lsp`; không có `viron`. Source Viron nằm tại
`stdlib/vir/viron/` gồm các module command rời, không có `main`, không có
`module.list`, và repository không có `vir.toml`/`vir.lock` mô tả Viron như một
project có thể build.

`stdlib/vir/viron/viron.vri` khai báo dispatcher nhưng repository search không
tìm thấy caller hoặc command-registration entrypoint. Help hiện tập trung vào
system-management commands (`maha`, `net`, `proc`, `fs`, `svc`, `pkg`, `user`,
`sys`), không có library workflow như `new`, `check`, `build`, `test`, `package`
hay `publish`.

### 4.2 Source Viron và package client không qua được compiler gate

Lệnh kiểm tra trực tiếp `stdlib/vir/viron/viron.vri` thất bại `E2113` tại import
`map`. Kiểm tra `stdlib/vir/test/tools_vtest.vri` cũng thất bại `E2113` từ
`stdlib/vir/pkg/pkg.vri`. Vì vậy chưa có baseline Vir-native build xanh để phát
triển tiếp trên chính Viron.

### 4.3 Resolver/fetch vẫn là stub và contract bị phân kỳ

`stdlib/vir/pkg/pkg.vri` gọi phần registry là `stub`: `pkg_search` luôn trả danh
sách rỗng, `pkg_fetch` luôn trả `not implemented`, còn `resolve` chỉ duyệt direct
dependencies và gán version placeholder `0.0.0`. URL mặc định trong code là
`https://pkg.vri-lang.org/v1`, khác với `https://pkg.virgori.com` trong các SPEC
VIRON hiện tại.

Module `stdlib/vir/viron/pkg_cmd.vri` không dùng package client này mà gọi
Homebrew. Hai bề mặt cùng mang tên package nhưng không tạo thành một Vir package
workflow thống nhất.

### 4.4 Test hiện tại không chứng minh Viron hoạt động

`stdlib/vir/test/tools_vtest.vri` có hai test Viron chỉ trả `vtest_pass()` vô
điều kiện và không include/call module Viron. File `tests/test_viron.py` tham
chiếu package Python `src.viron` không tồn tại; focused run kết thúc với 42 test
failed và 31 errors, tất cả do `ModuleNotFoundError: No module named 'src'`.

`tests/bootstrap_codegen/cg_viron_cli.vri` tự cài lại SemVer và topo-sort trong
fixture, không kiểm tra CLI, manifest, lockfile, module map, compiler dispatch,
package archive hoặc publish flow.

## 5. Reproduction

Từ repository root:

```sh
find bin -maxdepth 1 -type f -print
find stdlib/vir/viron -maxdepth 2 -type f -print | sort
find . -maxdepth 3 -type f \
  \( -name vir.toml -o -name vir.lock -o -name module.list \) -print

rg -n 'func main|viron_dispatch|pkg_dispatch|viron (new|check|build|test|package|publish)' \
  stdlib/vir/viron stdlib/vir/pkg tests --glob '*.vri'

./bin/virc stdlib/vir/viron/viron.vri --check --json -q
./bin/virc stdlib/vir/test/tools_vtest.vri --check --json -q
python3 -m pytest tests/test_viron.py -q
```

Kết quả audit:

- không có `bin/viron`, Viron entrypoint, Viron `module.list`, `vir.toml` hoặc
  `vir.lock`;
- hai compiler checks đều exit 1 với `E2113`;
- Python suite: `42 failed, 31 errors in 0.64s` do implementation được import
  không tồn tại.

## 6. Evidence

- CONFIRMED: `bin/virc` và `bin/vir-lsp` tồn tại; `bin/viron` không tồn tại.
- CONFIRMED: chỉ `tests/bootstrap_codegen/cg_viron_cli.vri` có `func main` trong
  phạm vi Viron được tìm kiếm; source production chỉ khai báo dispatcher.
- CONFIRMED: `./bin/virc stdlib/vir/viron/viron.vri --check --json -q` trả
  `E2113 imported symbol not exported` tại `viron.vri:16`.
- CONFIRMED: kiểm tra `tools_vtest.vri` trả `E2113` từ `pkg.vri:19` trước khi
  suite có thể chạy.
- CONFIRMED: `pkg.vri:113-155` đánh dấu registry là stub, không tải package và
  không resolve version ranges/transitive graph.
- CONFIRMED: `tools_vtest.vri:139-147` có hai Viron tests pass vô điều kiện.
- CONFIRMED: `python3 -m pytest tests/test_viron.py -q` cho 42 failed và 31
  errors vì toàn bộ suite import `src.viron` không có trong checkout.
- OBSERVED: không có `.github/` trong repository; chưa có release CI/CD cho
  Viron hoặc libraries ở checkout này.
- NOT_VERIFIED: trạng thái bất kỳ Registry/CDN/CI private nào nằm ngoài
  repository; không có client hoặc configuration trong checkout để kiểm chứng.

## 7. Scope

### Affected

- bootstrap và build của chính Viron;
- authoring, test và packaging của stdlib/official/third-party libraries;
- manifest, lockfile, path dependency và module-map behavior;
- reproducibility giữa local development và CI;
- publish readiness và supply-chain provenance;
- khả năng triển khai `VIRON-ISS-0001` trên một nền CLI/package engine thật.

### Not affected / Unknown

- Compiler vẫn có thể được gọi trực tiếp trên từng file `.vri`; đây là
  workaround cho compiler development, không phải package-development workflow.
- Issue không yêu cầu Registry/CDN production phải tồn tại trước local library
  workflow; mock registry và local path dependencies đủ cho milestone đầu.
- Issue không định nghĩa public API của từng library; ownership đó thuộc STLB
  hoặc package owner.
- Thiết kế chi tiết command names và storage schema thuộc PLAN/SPEC review,
  miễn acceptance workflow đo được vẫn được đáp ứng.

## 8. Impact

Không có Viron executable và workflow local-first, thư viện chỉ được phát triển
như file nội bộ của monorepo. Những invariant quan trọng nhất của package thực
tế—module identity, dependency resolution, lockfile, toolchain compatibility,
archive contents và consumer build—không được thực thi trong vòng lặp phát
triển. Khi đó CI/CD cũng không có command production đáng tin cậy để gọi.

Severity S1 phản ánh việc bề mặt phát triển package cốt lõi không thể chạy và
test công bố cho Viron đang hỏng hoặc pass giả. Priority P0 phản ánh dependency
ordering: xây thêm libraries hoặc Registry/CDN trước minimum Viron workflow sẽ
tạo quy trình ad-hoc và nợ migration. Không phân loại S0 vì chưa có bằng chứng
mất dữ liệu, compromise hoặc broad compiler failure.

## 9. Preliminary Analysis

- CONFIRMED: blocker đầu tiên là product boundary/buildability, không phải chỉ
  network registry. Viron cần project identity, entrypoint và testable service
  layers trước khi nối HTTP/CDN.
- CONFIRMED: ba implementation surfaces đang phân kỳ: system CLI dưới
  `stdlib/vir/viron`, package stub dưới `stdlib/vir/pkg`, và obsolete Python
  tests cho `src.viron` không tồn tại.
- OBSERVED: package/module helpers có thể tái sử dụng một phần, nhưng hiện chưa
  có green compiler gate hoặc exports đủ để coi là stable API.
- HYPOTHESIS: milestone đầu nên là vertical slice hoàn toàn local: scaffold một
  library fixture, resolve path dependency, sinh lock/module map, check/build,
  chạy test và tạo archive reproducible. Registry publish đến sau vertical slice.
- HYPOTHESIS: system-management commands kiểu `maha/net/proc/fs` không nên quyết
  định kiến trúc package tool; cần tách command adapters khỏi domain services.
- NOT_VERIFIED: command taxonomy cuối cùng, manifest schema canonical và
  compatibility policy giữa toolchain/core stdlib/official packages.

## 10. Acceptance Criteria

- [ ] Có PLAN liên kết `VIRON-ISS-0001` và issue này, xác định milestone
  vertical slice, ownership VIRON/STLB/VIRC, non-goals và migration khỏi các
  test/code surface cũ.
- [ ] Viron là project Vir độc lập có `module.list` bắt buộc, canonical source
  entrypoint và reproducible command tạo `bin/viron`.
- [ ] Toàn bộ source production của Viron/package engine qua `virc --check`;
  imports dùng explicit exports và không dựa vào fail-open behavior.
- [ ] `viron new --lib` hoặc command tương đương tạo project hợp lệ gồm
  `vir.toml`, `module.list`, `src/lib.vri` và test fixture.
- [ ] Một fixture library chạy được local `check`, `build` và `test` từ project
  root lẫn alternate CWD với cùng canonical module identities.
- [ ] Local path dependency được resolve, lock và đưa vào module map không cần
  network; missing/cyclic/duplicate modules có diagnostics xác định.
- [ ] Resolver xử lý exact version, version constraints và transitive graph;
  không ghi placeholder `0.0.0` vào resolved state.
- [ ] `package` tạo archive reproducible và kiểm tra đầy đủ manifest,
  `module.list`, source, license/provenance và checksum.
- [ ] `publish --dry-run` hoặc equivalent chạy toàn bộ validation mà không ghi
  remote; publish thật chỉ được mở sau khi Registry contract được chốt.
- [ ] Tests Python trỏ code không tồn tại được xóa/migrate có chủ đích; Viron
  tests gọi production implementation và không chứa unconditional pass.
- [ ] CI chạy chính các command Viron production cho fixture library; không có
  resolver/package implementation riêng trong workflow script.
- [ ] `./paper validate` và focused Viron/package/module tests đều pass trước
  khi issue chuyển VERIFYING.

## 11. Related Papers

### Issues

- `VIRON-ISS-0001` — thiếu standard-library lifecycle manager; phụ thuộc vào
  executable/package workflow được theo dõi ở issue này.
- `VIRON-ISS-0003` — umbrella issue theo dõi integration contract và closure
  end-to-end của project, toolchain, registry và stdlib lifecycles.

### Plans

- `VIRON-PLN-0001` — kế hoạch hợp nhất ba code/test surfaces, bắt đầu bằng
  standalone executable và local-first library vertical slice.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Opened and triaged the missing executable library-development workflow. |
| 2026-10-03 | Linked VIRON-ISS-0001 |
| 2026-10-03 | Linked VIRON-ISS-0003 |
| 2026-10-03 | Linked VIRON-PLN-0001 |
