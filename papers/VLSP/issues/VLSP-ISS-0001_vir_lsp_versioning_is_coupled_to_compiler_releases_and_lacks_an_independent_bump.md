---
id: "VLSP-ISS-0001"
type: "ISSUE"
domain: "VLSP"
title: "vir-lsp versioning is coupled to compiler releases and lacks an independent bump policy"
status: "OPEN"
severity: "S3"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "lsp"
components:
  - "versioning"
  - "release-process"
  - "protocol"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "semver"
  - "vir-lsp"
  - "release"
---

# VLSP-ISS-0001 — vir-lsp versioning is coupled to compiler releases and lacks an independent bump policy

## 1. Summary

`vir-lsp` đang báo `4.0.0`, trùng hệ version cũ của compiler dù LSP có lifecycle
và compatibility surface riêng. Server cần trở về `1.3.0`, dùng Semantic
Version độc lập và bắt buộc bump đúng một lần cho mỗi `VLSP-ISS` hoàn tất có
thay đổi server hoặc protocol.

## 2. Context

Version hiện hard-code tại header, banner, `--version` và
`initialize.serverInfo.version` trong `tools/vir-lsp/src/main.vri`. Regression
test cũng hard-code `4.0.0`; không có canonical record hoặc lệnh bump theo ISSUE.

## 3. Expected Behavior

- `vir-lsp` dùng SemVer riêng, bắt đầu tại `1.3.0`.
- MAJOR cho contract không tương thích; MINOR cho capability tương thích; PATCH
  cho fix/refactor tương thích.
- Compiler calendar version không làm thay đổi LSP version.
- Mỗi `VLSP-ISS` hoàn tất có thay đổi server/protocol/binary phải bump version
  đúng một lần và rebuild binary.
- CLI, banner và initialize response phải đồng bộ với canonical metadata.

## 4. Actual Behavior

- Source và binary báo `vir-lsp 4.0.0`.
- Test initialize kỳ vọng literal `4.0.0`.
- Không có policy tách version compiler và LSP.

## 5. Reproduction

```sh
./bin/vir-lsp --version
rg -n '4\.0\.0' tools/vir-lsp/src/main.vri tests/test_lsp_initialize.py
```

## 6. Evidence

- OBSERVED ngày 2026-10-07: binary trước migration báo `vir-lsp 4.0.0`.
- CONFIRMED: source chứa version tại bốn public surfaces và build script tạo
  native binary từ source đó.
- CONFIRMED: LSP 3.17 protocol version không phải product version của server.
- OBSERVED ngày 2026-10-07: `bin/vir-lsp --version` báo `1.3.0`, initialize
  response trả `serverInfo.version = 1.3.0`, protocol smoke tests pass và native
  binary SHA-256 là
  `ddd695a172be6100f0026a160712553fc0f2cebc7194e3b4fe221ec76a748fde`.

## 7. Scope

### Affected

- native vir-lsp source, CLI/banner và initialize response;
- LSP build/test workflow;
- agent completion guidance cho `VLSP-ISS`.

### Not affected / Unknown

- Compiler `2026.x` version không đổi theo LSP.
- LSP protocol specification vẫn là 3.17.
- VS Code extension version có lifecycle riêng và không bị bump tự động.

## 8. Impact

Coupled version làm người dùng hiểu sai rằng compiler và server có cùng
compatibility lifecycle. Thiếu bump gate cũng khiến binary, CLI và initialize
response có thể lệch nhau sau một issue.

## 9. Preliminary Analysis

- CONFIRMED: bốn version surface hiện cùng nằm trong một canonical source file.
- CONFIRMED: build script có thể fail closed bằng version-policy check trước
  khi compile.
- HYPOTHESIS: idempotent ISSUE ownership ngăn double bump khi retry workflow.
- NOT_VERIFIED: compatibility matrix của third-party LSP clients ngoài repo.

## 10. Acceptance Criteria

- [x] Canonical vir-lsp version là `1.3.0` và độc lập với compiler.
- [x] CLI, banner, initialize response và tests lấy cùng version contract.
- [x] Có lệnh bump idempotent cho PATCH/MINOR/MAJOR theo `VLSP-ISS`.
- [x] Build fail closed khi metadata/source drift.
- [x] Mandatory Vir guidance yêu cầu bump và rebuild trước khi hoàn tất issue.
- [x] Native `bin/vir-lsp` được rebuild và protocol regression pass.

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
| 2026-10-07 | Opened from the `4.0.0` source/binary audit and defined the independent `1.3.0` SemVer contract |
| 2026-10-07 | Recorded rebuilt `1.3.0` binary identity, initialize-response parity, protocol smoke tests, and binary hash |
