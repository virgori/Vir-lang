---
id: "VIRON-ISS-0003"
type: "ISSUE"
domain: "VIRON"
title: "Viron has no end-to-end implementation across toolchain package and registry lifecycles"
status: "VERIFYING"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-07"
owners:
  - "VIRON"
components:
  - "architecture"
  - "cli"
  - "toolchain"
  - "package-manager"
  - "registry"
  - "stdlib-lifecycle"
  - "release-pipeline"
related:
  issues:
    - "VIRON-ISS-0001"
    - "VIRON-ISS-0002"
  plans:
    - "VIRON-PLN-0001"
  reports:
    - "VIRON-RPT-0001"
supersedes: null
superseded_by: null
tags:
  - "blocker"
  - "end-to-end"
  - "bootstrap"
  - "reproducibility"
  - "supply-chain"
---

# VIRON-ISS-0003 — Viron has no end-to-end implementation across toolchain package and registry lifecycles

## 1. Summary

Viron chưa tồn tại như một hệ thống end-to-end nối được vòng đời project,
package, toolchain, registry và standard library. Sáu VIRON SPEC đã mô tả kiến
trúc dự kiến nhưng đều còn DRAFT; source hiện tại là các command rời, package
stub và test fixture không gọi production implementation. Không có executable
`viron`, project registry `module.list`, lock/module-map pipeline, toolchain
provisioning, secure cache, registry client hoặc release workflow có thể chạy
từ đầu đến cuối.

Hai khoảng trống thành phần đã được ghi nhận riêng:

- `VIRON-ISS-0001`: thiếu standard-library lifecycle manager;
- `VIRON-ISS-0002`: thiếu executable library-development workflow.

Issue này theo dõi integration contract và thứ tự triển khai bắt buộc để hai
nhánh trên hợp thành một sản phẩm, thay vì tạo thêm các implementation song song
không tương thích.

## 2. Context

Audit được cập nhật tại revision `e8e33c5ddec354a0a0f91370a0629eab7cb1d846`
ngày 2026-10-03. Các `VIRON-SPC-0001` đến `VIRON-SPC-0006` mô tả intended
architecture cho responsibilities, module resolution, manifest/lockfile,
registry, security và toolchain/sysroot. Trạng thái DRAFT có nghĩa các paper này
chưa phải contract đã chuẩn hóa; implementation không được dùng sự tồn tại của
chúng làm bằng chứng conformance.

Repository hiện có ba surface phân kỳ:

1. system-management CLI dưới `stdlib/vir/viron/`, bao gồm `pkg` gọi Homebrew;
2. package client/resolver stub dưới `stdlib/vir/pkg/`;
3. Viron tests tự cài lại logic hoặc tham chiếu Python package không tồn tại.

Compiler hiện vẫn tự dò `stdlib/stdlib.vri` tương đối theo CWD và chưa có CLI
contract `--sysroot`/`--module-map` như VIRON SPEC dự kiến. Bất kỳ thay đổi nào
ở bề mặt compiler phải được VIRC quản lý bằng paper riêng và được link với PLAN
Viron, không được lén ghép vào package manager.

## 3. Expected Behavior

- Viron có project/executable độc lập, `module.list` bắt buộc và một entrypoint
  canonical có thể build lặp lại.
- Một vertical slice local-first tạo library, resolve path dependency, sinh
  exact lock/module map, check/build/test/package mà không cần network.
- Toolchain/sysroot được chọn rõ ràng; compiler chỉ nhận input local đã resolve
  và không tự dò source tree hoặc truy cập registry.
- Resolver, immutable cache, registry transport và publish dùng chung một model
  package/version/checksum/provenance thay vì nhiều implementation rời.
- Install/update dùng staging, integrity/authenticity verification và atomic
  publish; offline/frozen, concurrent invocation, repair và rollback có hành vi
  xác định.
- Standard library lifecycle phân biệt compiler-coupled runtime trong sysroot
  với independently versioned official packages trong cache.
- CI/CD chỉ gọi production Viron commands; GitHub Actions nếu được chọn chỉ là
  runner/release producer, không phải registry hoặc runtime dependency của
  Viron.
- SPEC chỉ được nâng lên REVIEW/ACTIVE khi có schema, compatibility rules và
  conformance tests tương ứng.

## 4. Actual Behavior

### 4.1 Product boundary chưa tồn tại

`bin/` không có `viron`. Source dưới `stdlib/vir/viron/` không có `main`,
`module.list`, `vir.toml` hoặc `vir.lock`. Repository search không tìm được caller
production cho `viron_dispatch`, nên help/dispatcher hiện tại chưa chứng minh
được một CLI runnable.

### 4.2 Package path không chạy và không thống nhất

`stdlib/vir/pkg/pkg.vri` có `pkg_search` trả danh sách rỗng, `pkg_fetch` trả
`not implemented`, resolver chỉ xử lý direct dependency rồi gán `0.0.0`.
Registry URL trong code là `https://pkg.vri-lang.org/v1`, khác
`https://pkg.virgori.com` trong DRAFT SPEC. Trong khi đó
`stdlib/vir/viron/pkg_cmd.vri` gọi `brew`, không dùng Vir package model.

### 4.3 Compiler handoff chưa có contract thực thi

Compiler chưa công bố `--sysroot` hoặc `--module-map`; code vẫn dò
`stdlib/stdlib.vri` tại các đường dẫn tương đối. Vì vậy module identity và stdlib
selection vẫn phụ thuộc checkout/CWD, trái với end-state dự kiến.

### 4.4 Kiểm thử không tạo bằng chứng end-to-end

`tests/test_viron.py` import `src.viron` không tồn tại và focused suite lỗi toàn
bộ. `tests/bootstrap_codegen/cg_viron_cli.vri` tự định nghĩa SemVer/DAG thay vì
gọi Viron. Hai Viron tests trong `stdlib/vir/test/tools_vtest.vri` pass vô điều
kiện. Repository không có `.github/` workflow để kiểm tra package/release flow.

## 5. Reproduction

Từ repository root:

```sh
find bin -maxdepth 1 -type f -print
find stdlib/vir/viron -maxdepth 2 -type f -print | sort
find . -maxdepth 3 -type f \
  \( -name vir.toml -o -name vir.lock -o -name module.list \) -print

rg -n -- '--sysroot|--module-map' compiler/src
rg -n 'pkg_search|pkg_fetch|0\.0\.0|pkg\.vri-lang\.org|brew' \
  stdlib/vir/pkg stdlib/vir/viron

./bin/virc stdlib/vir/viron/viron.vri --check --json -q
./bin/virc stdlib/vir/pkg/pkg.vri --check --json -q
python3 -m pytest tests/test_viron.py -q
```

Kết quả tại revision audit:

- không có `bin/viron` hoặc Viron project registry;
- không tìm thấy compiler flags dự kiến;
- hai `virc --check` đều lỗi `E2113` vì imported symbol không được export;
- Python suite kết thúc với `42 failed, 31 errors` do `src.viron` không tồn tại.

## 6. Evidence

- CONFIRMED: chỉ có `bin/virc` và `bin/vir-lsp`; không có `bin/viron`.
- CONFIRMED: project `module.list` chỉ được tìm thấy cho compiler và test
  fixture; không có registry cho Viron hoặc `tools/vir-lsp`.
- CONFIRMED: `stdlib/vir/pkg/pkg.vri` chứa registry/fetch stubs, placeholder
  version và endpoint phân kỳ với DRAFT SPEC.
- CONFIRMED: `stdlib/vir/viron/pkg_cmd.vri` quản lý Homebrew packages, không
  quản lý Vir packages.
- CONFIRMED: `compiler/src/main.vri` tự dò stdlib registry tương đối theo CWD;
  CLI source không có `--sysroot` hoặc `--module-map`.
- CONFIRMED: production Viron/package sources không qua compiler check hiện tại.
- CONFIRMED: focused Python tests lỗi vì implementation import không tồn tại;
  Vir-native fixtures không gọi production end-to-end path.
- OBSERVED: `semver`, `toml`, `archive`, `http`, `crypto.hash`, `fs`, `path` và
  `process` là các candidate để tái sử dụng, nhưng exports/compile contracts của
  một số module chưa xanh nên chưa thể coi là stable API.
- OBSERVED: archive helper hiện có tar và gzip/zlib, trong khi DRAFT package
  format nêu `.tar.zst`; compression format chưa được implementation chứng minh.
- NOT_VERIFIED: production Registry/CDN, signing service hoặc private CI ngoài
  checkout; không có client/configuration trong repository để kiểm chứng.

## 7. Scope

### Affected

- kiến trúc và bootstrap của Viron executable;
- project manifest, mandatory `module.list`, lockfile và module map;
- package resolution, cache, registry transport và publish lifecycle;
- compiler/toolchain/sysroot handoff;
- official standard-library distribution và update boundaries;
- secure installation, offline/frozen operation, concurrency và rollback;
- production tests, conformance tests, CI/CD và release provenance.

### Not affected / Unknown

- Nội dung/public API của từng stdlib module vẫn thuộc STLB.
- Parser/typechecker/codegen vẫn thuộc VIRC; issue chỉ yêu cầu interface rõ
  giữa Viron và compiler.
- Host OS package management (`brew`, `apt`, ...) không phải Vir package
  management và không nằm trong critical path này.
- Production hosting vendor, authentication provider và final registry domain
  chưa được quyết định bởi issue này.
- Không coi sáu DRAFT SPEC là paper chuẩn hóa cho đến khi lifecycle paper và
  conformance evidence đáp ứng `papers/STANDARD.md`.

## 8. Impact

Thiếu integration path khiến thư viện chỉ có thể phát triển như source nội bộ
của monorepo; toolchain ngoài checkout không có cách nhận đúng module registry,
dependency hoặc stdlib. Registry/CDN nếu triển khai trước sẽ không có package
producer/consumer canonical để phục vụ, còn CI/CD sẽ buộc phải reimplement logic
bằng script ad-hoc.

Severity S1 vì capability cốt lõi của ecosystem không runnable và test surface
hiện hỏng/pass giả. Priority P0 vì đây là dependency trước khi mở rộng thư viện,
registry hay release automation. Không dùng S0 vì chưa có bằng chứng mất dữ liệu,
supply-chain compromise hoặc broad compiler outage đang xảy ra.

## 9. Preliminary Analysis

- CONFIRMED: cần một PLAN tích hợp; xử lý riêng từng stub không tạo được lifecycle
  có chung state model và transaction boundary.
- CONFIRMED: minimum viable milestone phải local-first và network-free để bootstrap
  được chính package/toolchain contract trước Registry/CDN.
- CONFIRMED: compiler không được trở thành package manager; Viron materialize
  sysroot/module map rồi gọi compiler bằng input tường minh.
- OBSERVED: DRAFT SPEC thiếu hoặc chưa chốt mandatory project/archive
  `module.list`, CLI/schema versioning, authenticated metadata/signing,
  cross-platform atomicity và compatibility matrix.
- HYPOTHESIS: một standalone top-level `viron/` project với thin CLI adapters và
  testable domain services là boundary dễ bootstrap/migrate nhất.
- HYPOTHESIS: compiler-coupled core/runtime nên theo toolchain sysroot, còn
  independently versioned `vir.*` libraries nên ở immutable package cache;
  module map hợp nhất hai nguồn.
- NOT_VERIFIED: archive compression, registry wire protocol, trust root và exact
  command taxonomy cuối cùng; các quyết định này phải qua SPEC review.

## 10. Acceptance Criteria

- [x] `VIRON-PLN-0001` được review/approved và liên kết cả `VIRON-ISS-0001`, `VIRON-ISS-0002` cùng mọi VIRC/STLB paper phát sinh.
- [ ] `VIRON-SPC-0001` đến `VIRON-SPC-0006` được reconcile với implementation contract; chỉ chuyển REVIEW/ACTIVE sau conformance evidence.
- [x] Viron là project/executable độc lập có mandatory `module.list`, canonical entrypoint và reproducible build tạo `bin/viron`.
- [x] Local-first fixture hoàn thành `new --lib`, check, build, test và package với path dependency, exact lock và deterministic module map, không cần network.
- [x] Toolchain/sysroot contract hoạt động từ alternate CWD; compiler không tự dò stdlib source tree hoặc truy cập network.
- [x] Resolver hỗ trợ exact/range/transitive dependencies, cycle/conflict diagnostics và deterministic `vir.lock`, không dùng placeholder version.
- [x] Immutable cache/fetch path có staging, authenticated metadata, checksum/signature, archive traversal defense, concurrency lock, offline/frozen, repair và rollback tests.
- [x] Mock registry chứng minh search/fetch/package/`publish --dry-run`; publish thật chỉ bật sau khi protocol/trust contract được duyệt.
- [x] `viron std` chứng minh install/list/update/verify/repair/rollback và giữ tách biệt `self`, `toolchain`, project dependency và host-package lifecycle.
- [x] Legacy Homebrew naming, nonexistent Python implementation, duplicated fixture algorithms và unconditional-pass tests được migrate/xóa có chủ đích.
- [ ] CI chạy production Viron commands trên supported host/target matrix; release job tạo checksum/signature/provenance và kiểm tra consumer download.
- [x] Một VIRON REPORT ghi revision, command, log/artifact evidence, negative tests và traceability; linked issues chỉ RESOLVED khi report được VERIFIED (`VIRON-RPT-0001`).

## 11. Related Papers

### Issues

- `VIRON-ISS-0001` — standard-library lifecycle sub-issue.
- `VIRON-ISS-0002` — executable library-development workflow sub-issue.

### Plans

- `VIRON-PLN-0001` — phased implementation plan for the complete lifecycle.

### Reports

- `VIRON-RPT-0001` — verification report for standalone reimplementation.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Opened and triaged the missing end-to-end Viron integration path. |
| 2026-10-03 | Linked VIRON-PLN-0001. |
| 2026-10-03 | Linked VIRON-ISS-0001 and VIRON-ISS-0002. |
| 2026-10-07 | Linked VIRON-RPT-0001 |
| 2026-10-07 | Status transitioned TRIAGED -> VERIFYING following native standalone viron implementation and verification. |
