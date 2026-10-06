---
id: "VIRC-ISS-0013"
type: "ISSUE"
domain: "VIRC"
title: "macOS ARM64 LibSystem runtime provider is not distinct from raw syscalls"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "target-model"
  - "arm64-codegen"
  - "darwin-runtime"
  - "mach-o"
  - "ffi"
related:
  issues:
    - "VIRC-ISS-0009"
    - "VIRC-ISS-0014"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "macos"
  - "arm64"
  - "libsystem"
  - "raw-syscall"
  - "runtime-provider"
  - "abi"
---

# VIRC-ISS-0013 — macOS ARM64 LibSystem runtime provider is not distinct from raw syscalls

## 1. Summary

Compiler quảng bá hai target macOS ARM64 song song:
`macos-arm64` dùng `DarwinRawSyscall` và `macos-arm64-libsystem` dùng
`DarwinLibSystem`. Tuy nhiên runtime provider hiện chỉ tồn tại trong target
metadata; ARM64 lowering phân nhánh Linux so với non-Linux và không đọc provider.
Vì vậy hai target tạo binary byte-identical, cùng chứa raw Darwin `svc #0x80`
và cùng load `libSystem.B.dylib` khi cùng source được compile.

Cần triển khai LibSystem như một runtime path thực sự song song với raw syscall,
không biến target mới thành alias và không làm mất raw path đang dùng cho
bootstrap/low-level workloads.

## 2. Context

Audit thực hiện ngày 2026-10-03 trên working tree có HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`; repository đang có các thay đổi
compiler chưa commit, nên evidence command bên dưới mô tả đúng working tree và
`bin/virc` tại thời điểm audit, không được gán ngược cho clean HEAD.

`VIRC-ISS-0009`/`VIRC-PLN-0006` đã tách target thành architecture, OS, ABI,
runtime provider và object format, đồng thời cố ý để target chưa có runtime fail
closed. Issue này là follow-up được phép bởi `VIRC-RPT-0018`: hoàn thiện một
provider đã có identity nhưng chưa có lowering/runtime semantics riêng.

Mach-O writer hiện có machinery cho `LC_LOAD_DYLIB`, symbol/bind tables và ARM64
foreign stubs. Đây là nền tảng có thể tái sử dụng, nhưng sự tồn tại của FFI
imports không chứng minh standard runtime đang gọi LibSystem.

## 3. Expected Behavior

- `macos-arm64` và `macos-arm64-libsystem` là hai target được hỗ trợ, có cùng
  ARM64/AAPCS64/Mach-O base nhưng runtime policy khác nhau rõ ràng.
- Raw target tiếp tục dùng Darwin raw-syscall stubs cho operations được contract
  cho phép; explicit user FFI vẫn có thể load dylib mà không đổi runtime provider.
- LibSystem target route các OS/runtime operations đã công bố qua symbol imports
  của `/usr/lib/libSystem.B.dylib`, dùng Darwin C ABI, Mach-O bind/import tables
  và error semantics được xác định.
- Runtime provider được truyền đến entry/startup, allocator, I/O, process,
  clock/network và generic `syscall*` boundary; operation chưa hỗ trợ phải fail
  closed bằng diagnostic thay vì âm thầm dùng provider khác.
- Target matrix phân biệt raw và LibSystem bằng structure/disassembly/imports,
  không chỉ kiểm tra Mach-O header hoặc stdout giống nhau.
- Hai path có native macOS ARM64 execution tests và giữ cùng language-level
  behavior cho các API nằm trong shared contract.

## 4. Actual Behavior

### 4.1 Runtime provider không được consume

`compiler/src/target/target_spec.vri` tạo hai `TargetSpec` khác nhau và export
`target_spec_provider`, nhưng repository search chỉ tìm thấy function này tại
nơi định nghĩa. Driver và lowering không query `DarwinRawSyscall` hoặc
`DarwinLibSystem`.

### 4.2 ARM64 lowering chỉ phân biệt Linux và non-Linux

`emit_lir_module_arm64` tính `is_linux` từ target OS. Mọi target non-Linux đi
vào cùng Darwin branch: arena `mmap`, print/runtime stubs, generic syscall stub
và exit đều phát raw BSD syscall qua X16 và `svc #0x80`.

### 4.3 Hai target tạo cùng artifact

Focused matrix và direct compile cho cùng source trả cùng SHA-256. Disassembly
của cả hai chứa `svc #0x80`; `otool -L` của cả hai liệt kê
`/usr/lib/libSystem.B.dylib`. LibSystem load hiện đến từ used FFI import machinery,
không phải runtime-provider dispatch, nên tên target không thay đổi core runtime.

### 4.4 Test matrix chưa kiểm tra isolation

`tests/matrix_runner.py` yêu cầu LibSystem target có load command, nhưng raw
target không bị fail nếu cũng có load command và runner không yêu cầu hai
artifacts khác nhau hay cấm raw syscall trong LibSystem runtime. Hai target vì
thế đều PASS dù binary byte-identical.

## 5. Reproduction

Từ repository root trên macOS ARM64:

```sh
audit_dir=$(mktemp -d /tmp/vir-target-audit.XXXXXX)

./bin/virc tests/vri/test_add.vri --target macos-arm64 \
  -q -o "$audit_dir/raw"
./bin/virc tests/vri/test_add.vri --target macos-arm64-libsystem \
  -q -o "$audit_dir/libsystem"

shasum -a 256 "$audit_dir/raw" "$audit_dir/libsystem"
cmp "$audit_dir/raw" "$audit_dir/libsystem"
otool -L "$audit_dir/raw"
otool -L "$audit_dir/libsystem"
otool -tvV "$audit_dir/raw" | rg 'svc'
otool -tvV "$audit_dir/libsystem" | rg 'svc'

rg -n 'target_spec_provider|DarwinRawSyscall|DarwinLibSystem' \
  compiler/src --glob '*.vri' --glob '!**/generated/**'
```

Observed result tại thời điểm audit:

- hai compile command exit 0 và chạy native đúng output;
- cả hai artifact có SHA-256
  `57b91e364bb4c37508e619d3dbb6a28da2068e2ce2adfc7dd14f7e833294520f`;
- `cmp` không báo khác biệt;
- cả hai load `libSystem.B.dylib` và đều chứa nhiều `svc #0x80`;
- provider identifiers chỉ được dùng trong target factory/enum, không dùng để
  chọn runtime lowering.

## 6. Evidence

- CONFIRMED: `make_target_macos_arm64()` chọn `DarwinRawSyscall` và
  `make_target_macos_arm64_libsystem()` chọn `DarwinLibSystem`.
- CONFIRMED: `target_spec_provider()` không có production caller ngoài nơi định
  nghĩa trong source được audit.
- CONFIRMED: `emit_lir_module_arm64()` và runtime stubs nhận `is_linux`, không
  nhận runtime provider; non-Linux branch phát Darwin `svc #0x80`.
- CONFIRMED: direct compile và target matrix tạo byte-identical outputs cho hai
  target trên cùng input; cả hai chạy native thành công.
- CONFIRMED: Mach-O writer đã có dylib/bind/foreign-stub primitives, nhưng chỉ
  kích hoạt theo used FFI imports.
- OBSERVED: minimal standard test transitively dùng FFI/import state khiến raw
  artifact cũng load LibSystem; exact source of every used import chưa được map
  thành một runtime-provider conformance fixture.
- HYPOTHESIS: tách runtime service interface khỏi ARM64 instruction encoder sẽ
  cho phép raw/LibSystem coexist mà không fork toàn bộ backend.
- NOT_VERIFIED: danh sách LibSystem symbols, errno mapping, cancellation
  semantics và deployment-target compatibility cuối cùng; chúng cần PLAN/SPEC
  review và authoritative Apple ABI references trước implementation.

## 7. Scope

### Affected

- target capability/identity for both macOS ARM64 modes;
- ARM64 startup, allocator and runtime-stub dispatch;
- Mach-O dynamic imports, bind data and FFI/runtime stub patching;
- standard I/O, memory, process and other OS-facing runtime services;
- target matrix, disassembly and native execution coverage;
- compiler self-host/bootstrap compatibility on macOS ARM64.

### Not affected / Unknown

- Linux ARM64 raw-syscall behavior is outside this issue except shared
  target-neutral interfaces.
- User-declared arbitrary dylib FFI is not the same as choosing LibSystem as the
  standard runtime provider.
- Issue does not remove raw syscalls or make LibSystem mandatory for all macOS
  binaries.
- macOS x86-64 remains unsupported and is not enabled by this work.
- Exact public Vir stdlib API and provider-selection UX require a linked PLAN or
  SPEC decision; this issue tracks the missing behavior, not final design.

## 8. Impact

Target name currently promises a runtime distinction that compiled output does
not implement. Users cannot request a LibSystem-backed standard runtime, while
tests can report both targets healthy without detecting that they are aliases.
This also prevents measuring compatibility, syscall coverage and deployment
behavior independently.

Severity S1 reflects incorrect target semantics in a supported core backend.
Priority P0 reflects the requested need to land LibSystem alongside—not instead
of—the raw path before expanding platform runtime APIs.

## 9. Preliminary Analysis

- CONFIRMED: target model separation exists; missing work is provider-aware
  lowering/runtime and conformance, not another target string.
- CONFIRMED: switching only the Mach-O load command is insufficient because
  startup and runtime stubs still emit raw syscalls.
- CONFIRMED: raw target must be regression-protected; explicit FFI imports must
  not silently reclassify its provider.
- HYPOTHESIS: define a runtime-service operation table selected from
  `TargetSpec.runtime_provider`, then lower each operation to raw stub or
  imported LibSystem thunk while sharing ARM64 instruction primitives.
- HYPOTHESIS: bootstrap may need a staged default-policy change only after
  LibSystem conformance is green; no default change is implied by this issue.
- NOT_VERIFIED: whether every current raw syscall has a direct LibSystem mapping
  suitable for the same semantic contract.

## 10. Acceptance Criteria

- [ ] A linked PLAN defines runtime-service boundaries, raw/LibSystem mapping,
  unsupported-operation diagnostics, migration and rollback.
- [ ] `TargetSpec.runtime_provider` is consumed by driver/lowering/runtime code;
  no Linux-vs-non-Linux boolean is the sole provider decision.
- [ ] `macos-arm64` retains a tested raw-syscall startup/runtime path and is not
  silently converted to LibSystem.
- [ ] `macos-arm64-libsystem` uses Mach-O imports/thunks for the agreed standard
  runtime services and does not emit raw `svc #0x80` for those migrated services.
- [ ] Explicit user FFI works on both targets without changing the selected
  standard runtime provider.
- [ ] Provider-specific error/errno, argument, return and ownership semantics
  are documented and covered by positive/negative tests.
- [ ] Mach-O structure tests verify dylib commands, symbols, bind/import data,
  stub patching, code signature validity and deployment-target behavior.
- [ ] Disassembly test proves the two target paths are not aliases and enforces
  allowed/forbidden raw trap policy for each fixture.
- [ ] Native macOS ARM64 tests cover process entry/exit, memory allocation,
  console/file I/O and at least one explicit external call for both providers.
- [ ] `tests/matrix_runner.py` fails if raw and LibSystem semantic/structural
  expectations collapse to byte-identical provider behavior.
- [ ] Generated compiler sync, self-host fixed point and full relevant regression
  gates pass; a REPORT records exact artifacts and commands before resolution.

## 11. Related Papers

### Issues

- `VIRC-ISS-0009` — established typed target dimensions and fail-closed policy;
  this issue is the focused Darwin provider follow-up.
- `VIRC-ISS-0014` — sibling work for Windows ABI/runtime-provider support.

### Plans

- None; create a dedicated implementation PLAN after provider service contract
  and macOS compatibility policy are reviewed.

### Reports

- `VIRC-RPT-0018` — verified decoupling and explicitly left native platform
  runtimes as follow-up work.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Opened and triaged the missing distinct LibSystem runtime path beside raw Darwin syscalls. |
| 2026-10-03 | Linked VIRC-ISS-0009 and sibling VIRC-ISS-0014. |
