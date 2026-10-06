---
id: "VIRC-ISS-0014"
type: "ISSUE"
domain: "VIRC"
title: "Windows targets lack native ABI runtime and PE import support"
status: "TRIAGED"
severity: "S1"
priority: "P1"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "target-model"
  - "x86-64-codegen"
  - "arm64-codegen"
  - "windows-abi"
  - "windows-runtime"
  - "pe-coff"
related:
  issues:
    - "VIRC-ISS-0009"
    - "VIRC-ISS-0013"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "windows"
  - "win64"
  - "arm64"
  - "x86-64"
  - "pe-coff"
  - "kernel32"
  - "abi"
---

# VIRC-ISS-0014 — Windows targets lack native ABI runtime and PE import support

## 1. Summary

Compiler nhận diện `windows-x86_64` và `windows-arm64`, gán Windows calling ABI,
`WindowsKernel32` runtime provider và PE/COFF object format, nhưng chủ động từ
chối cả hai target trước lowering. PE writer hiện chỉ tạo DOS/PE headers và một
section `.text`; không có import directory/IAT để gọi Windows APIs. Nếu bỏ gate,
x86-64 backend vẫn hard-code Linux SysV còn ARM64 backend sẽ đi vào Darwin raw
syscall path.

Cần triển khai Windows native ABI end-to-end cho cả x86-64 và ARM64, gồm calling
convention, startup/runtime services qua Windows imports, PE relocation/import/
unwind metadata và native execution evidence. Một PE header hợp lệ hoặc fixture
tự mô phỏng thanh ghi không đủ để tuyên bố target được hỗ trợ.

## 2. Context

Audit thực hiện ngày 2026-10-03 trên working tree có HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215`; compiler tree đang có thay đổi
chưa commit. Evidence command ghi nhận behavior của working tree và `bin/virc`
tại thời điểm audit.

`VIRC-ISS-0009` đã sửa lỗi nguy hiểm trước đây—PE chứa Linux/Darwin runtime—bằng
fail-closed capability matrix. `VIRC-RPT-0018` kết luận Windows native runtime
còn unimplemented và nên có issue riêng khi được lên lịch. Issue này là follow-up
đó; nó không reopen correctness work đã đóng của ISS-0009.

## 3. Expected Behavior

- `windows-x86_64` lower calls, frames, stack arguments, returns, varargs và
  callee-save rules theo Microsoft x64 ABI, bao gồm shadow/home space và stack
  alignment.
- `windows-arm64` lower calls/frames theo Windows ARM64 ABI, gồm reserved/
  nonvolatile register policy, argument/return classification, stack layout và
  SIMD preservation theo contract được duyệt.
- Startup nhận process arguments/environment bằng Windows runtime contract,
  khởi tạo Vir arena/runtime và trả exit status qua supported Windows API.
- OS-facing services dùng `WindowsKernel32` hoặc provider được chuẩn hóa qua PE
  import table/IAT; compiler không phát Linux syscall hoặc Darwin `svc #0x80`.
- PE32+ writer tạo đúng machine type, sections, import directory, IAT/thunks,
  base relocations khi cần, exception/unwind metadata cho non-leaf functions và
  security flags nhất quán với artifact thực tế.
- External declarations resolve thành Windows imports với symbol/library mapping
  xác định; symbol không hỗ trợ fail closed.
- Binary được kiểm tra bằng parser/disassembler độc lập và chạy trên native
  Windows x64/Windows on ARM runner tương ứng.

## 4. Actual Behavior

### 4.1 Capability matrix từ chối mọi Windows target

`target_spec_is_supported()` trả 0 khi `TargetOS.Windows`. CLI vì thế phát
`target runtime is not supported` trước lowering và không tạo artifact cho cả
`windows-arm64` lẫn `windows-x86_64`.

### 4.2 ABI lowering chưa tồn tại trong production backend

`emit_lir_module_x86_64()` assert target OS phải là Linux và runtime/startup dùng
Linux mmap/syscall plus System V registers. ARM64 lowering chỉ phân biệt Linux
với non-Linux, nên Windows ARM64 sẽ dùng Darwin mmap/exit/runtime stubs nếu gate
bị bỏ mà không có provider-aware implementation.

### 4.3 PE writer chỉ có `.text`

`compiler/src/backend/pe.vri` ghi 16 data directories bằng zero, khai báo đúng
machine type nhưng chỉ emit một executable/read-only `.text` section. Không có
`.idata`, DLL/name tables, import lookup/address tables, `.reloc`, `.pdata` hoặc
`.xdata`; do đó không có đường production để gọi Kernel32 hay unwind non-leaf
frames.

### 4.4 Test hiện tại là structural/self-contained

`tests/bootstrap_codegen/cg_windows_abi.vri` tự định nghĩa helper cho register và
shadow-space calculation, không gọi production register allocator/lowering.
`cg_windows_pe.vri` tự tạo và kiểm tra PE bytes. Matrix runner hiện nhận compile
failure cho Windows; không có native execution evidence.

## 5. Reproduction

Từ repository root:

```sh
audit_dir=$(mktemp -d /tmp/vir-windows-audit.XXXXXX)

./bin/virc tests/vri/test_add.vri --target windows-arm64 \
  -q -o "$audit_dir/windows-arm64.exe"
./bin/virc tests/vri/test_add.vri --target windows-x86_64 \
  -q -o "$audit_dir/windows-x86_64.exe"

find "$audit_dir" -maxdepth 1 -type f -print

rg -n 'target_spec_is_supported|TargetOS.Windows|WindowsKernel32' \
  compiler/src/target compiler/src/main --glob '*.vri'
rg -n -i 'idata|import directory|kernel32|pdata|xdata|unwind|shadow' \
  compiler/src/backend/pe.vri compiler/src/lower --glob '*.vri'

python3 tests/matrix_runner.py tests/vri/test_add.vri \
  --target windows-arm64 --outdir "$audit_dir/matrix-arm64" --json
python3 tests/matrix_runner.py tests/vri/test_add.vri \
  --target windows-x86_64 --outdir "$audit_dir/matrix-x64" --json
```

Observed result tại thời điểm audit:

- hai direct compile command exit 1 với `target runtime is not supported`;
- không có `.exe` artifact;
- matrix runner ghi `FAIL` cho cả hai target tại compile stage;
- PE writer search không tìm thấy production import/unwind sections;
- x86 backend ghi rõ chỉ hỗ trợ Linux SysV ABI.

## 6. Evidence

- CONFIRMED: target factories đã khai báo `Windows_AMD64`, `Windows_ARM64`,
  `WindowsKernel32` và `PE_COFF`.
- CONFIRMED: capability matrix trả unsupported cho mọi Windows target và CLI
  fail closed trước code generation.
- CONFIRMED: x86-64 production backend từ chối non-Linux và phát Linux syscall
  startup/runtime; không có Win64 call/frame selection.
- CONFIRMED: ARM64 production backend không có Windows branch; non-Linux path là
  Darwin raw syscall.
- CONFIRMED: PE writer zero toàn bộ data directories và chỉ tạo `.text`; không
  có production IAT/import, relocation hoặc unwind tables.
- CONFIRMED: bootstrap Windows ABI/PE tests cài helper/writer riêng, không gọi
  production target pipeline.
- OBSERVED: `tests/matrix_runner.py` có branches dự kiến cho Windows runners,
  nhưng compiler fail trước khi artifact có thể được validate/run.
- HYPOTHESIS: shared runtime-service/import abstraction với ISS-0013 có thể dùng
  lại registry/thunk concepts, nhưng Windows ABI và PE metadata phải có owner/test
  riêng, không dùng Darwin implementation.
- NOT_VERIFIED: final minimum Windows version, CRT policy, SEH scope, DLL set,
  ARM64EC, dynamic linking strategy và cross-compilation SDK dependency.

## 7. Scope

### Affected

- Windows x86-64 and ARM64 target support claims;
- call lowering, register allocation constraints, prologue/epilogue and stack;
- runtime startup, allocator, I/O, process and error handling;
- PE32+ writer, imports/IAT, relocation and unwind/exception metadata;
- external function resolution and Windows DLL mapping;
- cross-compilation plus native Windows execution CI.

### Not affected / Unknown

- Windows x86 32-bit is not in scope.
- ARM64EC, UWP, kernel-mode drivers and MSVC object/library compatibility are not
  implied unless separately approved.
- Issue does not require raw Windows/NT syscalls; the declared provider is
  `WindowsKernel32` and any lower-level provider would need a separate contract.
- Wine may provide supplemental x86-64 smoke coverage but cannot replace native
  Windows x64 or Windows on ARM verification.
- PE/COFF relocatable object emission versus direct executable emission remains
  a PLAN decision; acceptance requires runnable supported artifacts either way.

## 8. Impact

Windows appears in CLI help and canonical target metadata but cannot compile any
program. Library/application authors cannot produce or verify Windows artifacts,
and existing bootstrap fixtures risk overstating readiness because they validate
copied ABI rules or headers rather than production lowering/runtime behavior.

Severity S1 reflects a complete missing platform backend for two advertised
targets, while fail-closed behavior prevents generation of silently corrupt
binaries. Priority P1 schedules this after the immediate macOS provider split;
it can move independently once ABI/PE contract and native runners are available.

## 9. Preliminary Analysis

- CONFIRMED: deleting the capability gate is unsafe; it would restore the exact
  foreign-runtime/container bug closed by `VIRC-ISS-0009`.
- CONFIRMED: PE writer work alone is insufficient; calling convention, startup,
  runtime services, imports and unwind metadata must land together behind tests.
- CONFIRMED: x86-64 and ARM64 share Windows service/import policy but need separate
  ABI lowering and verification matrices.
- HYPOTHESIS: target-neutral runtime operations can select a Windows import-backed
  provider, while per-architecture ABI modules own argument classification,
  registers, frames and unwind encoding.
- HYPOTHESIS: enable one Windows architecture only after its complete gate passes;
  target support does not need an all-or-nothing toggle for both architectures.
- NOT_VERIFIED: whether current register allocator can reserve all Windows ABI
  special/nonvolatile registers without design changes.

## 10. Acceptance Criteria

- [ ] A linked PLAN defines phased x86-64/ARM64 enablement, ownership, minimum OS,
  DLL/CRT policy, PE metadata, native runners, compatibility and rollback.
- [ ] Capability matrix remains fail closed per architecture until that exact
  target passes all production ABI/runtime/object-format gates.
- [ ] Windows x64 lowering implements Microsoft x64 argument/return rules,
  32-byte shadow space, alignment, callee-save and varargs behavior with tests.
- [ ] Windows ARM64 lowering implements reviewed argument/return/register/frame/
  SIMD rules, including reserved-register handling, with tests.
- [ ] Runtime startup, arena allocation, console/file I/O and process exit use
  the approved Windows API provider; output contains no Linux or Darwin syscall
  sequences.
- [ ] PE writer emits validated imports/IAT and necessary sections/directories;
  relocation, ASLR/NX flags and unwind/exception metadata match emitted code.
- [ ] Direct/extern calls and dynamic imports have deterministic DLL/symbol
  resolution and clear diagnostics for unsupported symbols/libraries.
- [ ] Production tests exercise compiler lowering/writer rather than copied ABI
  helpers; legacy bootstrap fixtures are migrated or explicitly scoped.
- [ ] Independent tooling validates machine type, sections, data directories,
  imports, relocations, unwind data and architecture-specific disassembly.
- [ ] Windows x64 artifacts run on a native Windows x64 runner; Windows ARM64
  artifacts run on Windows on ARM. Runner absence is BLOCKED, never PASS.
- [ ] Target matrix distinguishes unsupported, blocked-no-runner and failed
  compilation correctly and produces no false-success structural result.
- [ ] Generated bundle sync, self-host fixed point, Linux/macOS regression and a
  verified REPORT all pass before each Windows target is marked supported.

## 11. Related Papers

### Issues

- `VIRC-ISS-0009` — established typed target dimensions and fail-closed handling;
  this issue supplies the intentionally deferred Windows runtime.
- `VIRC-ISS-0013` — sibling runtime-provider work for macOS ARM64 LibSystem.

### Plans

- None; create a dedicated implementation PLAN after Windows ABI, PE and runner
  scope is reviewed.

### Reports

- `VIRC-RPT-0018` — accepted report confirming Windows targets currently fail
  closed and native Windows runtime remains follow-up work.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Opened and triaged native Windows x64/ARM64 ABI, runtime and PE import support. |
| 2026-10-03 | Linked VIRC-ISS-0009 and sibling VIRC-ISS-0013. |
