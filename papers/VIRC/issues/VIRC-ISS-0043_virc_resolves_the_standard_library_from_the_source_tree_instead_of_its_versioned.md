---
id: "VIRC-ISS-0043"
type: "ISSUE"
domain: "VIRC"
title: "virc resolves the standard library from the source tree instead of its versioned toolchain sysroot"
status: "VERIFYING"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-07"
owners:
  - "compiler"
  - "toolchain"
components:
  - "cli-driver"
  - "module-resolution"
  - "sysroot"
  - "stdlib-distribution"
  - "release-layout"
related:
  issues:
    - "VIRC-ISS-0047"
    - "VIRON-ISS-0001"
  plans:
    - "VIRC-PLN-0028"
  reports:
    - "VIRC-RPT-0045"
supersedes: null
superseded_by: null
tags:
  - "sysroot"
  - "stdlib"
  - "cwd-independence"
  - "toolchain-versioning"
  - "distribution"
---

# VIRC-ISS-0043 — virc resolves the standard library from the source tree instead of its versioned toolchain sysroot

## 1. Summary

`virc 4.2.1` không có compiler sysroot contract. Native resolver hiện tìm
`stdlib/stdlib.vri` bằng cách đi ngược từ source path rồi thử các path tương đối
với current working directory. Nó không suy ra installation prefix từ executable,
không đọc `VIR_SYSROOT`, không nhận `--sysroot`, và không có
`--print-sysroot`/`--print-stdlib`.

Do đó cùng một binary và source có thể compile khi process chạy từ repository
root nhưng thất bại E2120 khi chạy từ một thư mục khác, dù cây chứa executable
đã có đúng `stdlib/stdlib.vri`. Project bên ngoài checkout chỉ hoạt động nếu vô
tình chạy từ CWD phù hợp hoặc vendor/copy stdlib, làm mất tính portable và cho
phép compiler/stdlib lệch phiên bản.

Nguyên tắc kiến trúc của ISSUE này là:

> **The standard library belongs to the Vir toolchain, not to the consuming
> project. Project-local resolution must never require vendoring the Vir
> standard library.**

## 2. Context

Audit được thực hiện ngày 2026-10-06 tại Git HEAD
`e1fc2d54773b83a6be684ec6ab20f403faf0a215` trên dirty worktree được giữ nguyên.
Compiler được kiểm tra là `virc 4.2.1 (self-hosted)` tại
`/Users/gengyang/Vir-3.0/bin/virc`.

Checkout hiện đã có một compact distribution-shaped layout:

```text
/Users/gengyang/Vir-3.0/
├── bin/virc
└── stdlib/
    ├── stdlib.vri
    └── vir/...
```

Tuy nhiên resolver không dùng executable prefix. Thành công hiện phụ thuộc vào
source-tree/CWD discovery, không phụ thuộc quan hệ giữa `bin/virc` và stdlib đi
kèm.

`VIRON-ISS-0001` đã theo dõi lifecycle cài đặt/cập nhật standard library. ISSUE
này sở hữu phía compiler: CLI, sysroot selection, installed stdlib discovery,
registry handoff và CWD independence. `VIRON-SPC-0006` có thiết kế sysroot nhưng
đang `DRAFT`; nó là intended architecture, không phải bằng chứng implementation.

## 3. Expected Behavior

### 3.1. Toolchain ownership

- `virc`, compiler-coupled runtime và standard library tương thích phải được
  phân phối như một toolchain versioned.
- Project `module.list` chỉ quản lý module project; dependency/package module
  map quản lý dependency đã resolve; stdlib registry thuộc toolchain.
- Không project nào phải chứa hoặc copy Vir stdlib để compile.
- Resolver phải đọc `<stdlib-directory>/stdlib.vri` làm source of truth cho
  module-name → physical-path mapping. Nó không được suy tên module trực tiếp từ
  cây thư mục.
- Source spelling ví dụ `include json` phải resolve qua registry entry hiện hành.
  Namespace `std.json` do người dùng đề xuất là quyết định namespace riêng và
  không được coi là đã đăng ký chỉ vì sysroot tồn tại.

### 3.2. Sysroot selection

Sysroot phải được chọn tất định theo precedence:

1. `--sysroot <path>`;
2. `VIR_SYSROOT=<path>`;
3. installed sysroot/prefix suy ra từ canonical executable location;
4. development source-tree fallback chỉ trong development mode/build.

Một CLI hoặc environment override đã được cung cấp nhưng không hợp lệ phải fail
closed với diagnostic rõ ràng; compiler không được im lặng rơi xuống sysroot
khác. Release build không được search `./stdlib`, `../stdlib` hoặc
`../../stdlib` theo CWD.

Việc suy executable location phải xử lý ít nhất absolute invocation, PATH
lookup và symlink/shim handoff. Dùng raw `argv[0]` mà không canonicalize không đủ
làm installed-prefix contract.

### 3.3. Installed layout and observability

PLAN/SPEC triển khai phải chọn layout canonical rõ ràng, ví dụ compact profile:

```text
<prefix>/bin/virc
<prefix>/stdlib/stdlib.vri
<prefix>/stdlib/vir/...
```

Một FHS-style profile có thể đặt registry dưới
`<prefix>/lib/vir/stdlib/stdlib.vri`, nhưng profile phải đến từ release/toolchain
contract hoặc manifest, không phải filesystem probing không giới hạn.

Compiler phải công bố:

```text
virc --print-sysroot
virc --print-stdlib
```

Hai lệnh không cần input file, trả canonical absolute paths, dùng đúng selection
precedence như compilation và có exit code khác 0 nếu installation không hợp lệ.

### 3.4. Module resolution layers

Sau khi sysroot đã được chọn, namespace resolution phải phân lớp:

1. explicit project/local modules;
2. dependency/package modules đã được resolver/package manager cấp phép;
3. Vir sysroot stdlib modules;
4. compiler builtins nếu có contract riêng.

Collision/visibility policy giữa các layer phải được định nghĩa thay vì cho
project vô tình shadow hoặc thay thế stdlib. Dù policy cuối cùng là reject hay
qualified identity, project registry không được nhập/copy toàn bộ stdlib registry.

## 4. Actual Behavior

- `compiler/src/main/module_resolver.vri:23-37` chỉ ưu tiên
  `g_ideStdlibRegistry`, rồi `find_file_up(source_base, "stdlib/stdlib.vri")`,
  rồi ba relative-CWD candidates.
- `CompilerConfig` không có sysroot/stdlib fields.
- `parse_args()` không nhận `--sysroot`, `--print-sysroot` hoặc
  `--print-stdlib`; help cũng không công bố các option đó.
- `cliEnvironmentGet()` có thể đọc environment, nhưng không có caller nào đọc
  `VIR_SYSROOT`.
- `g_ideStdlibRegistry` là đường explicit cho IDE/LSP; normal `virc` CLI không
  có public option tương đương.
- `stdlib/stdlib.vri` đã có `root = vir` và explicit mappings. Khoảng trống nằm
  ở discovery/ownership, không phải thiếu registry format.

Kết quả audit:

- chạy compiler từ repository root: source ngoài repo compile thành công;
- chạy cùng absolute compiler path và source từ `/private/tmp`: thất bại E2120;
- đặt `VIR_SYSROOT=/Users/gengyang/Vir-3.0` vẫn thất bại E2120;
- `--print-sysroot` và `--print-stdlib` đều bị từ chối là unknown option.

## 5. Reproduction

Source `/private/tmp/vir_sysroot_audit/app.vri`:

```vir
include math

func main:
    out abs(0 - 7)
end.
```

Control case từ repository root:

```sh
cd /Users/gengyang/Vir-3.0
./bin/virc /private/tmp/vir_sysroot_audit/app.vri \
  -o /private/tmp/vir_sysroot_audit/from_repo.out --color=never -q
```

Kết quả: exit 0.

Foreign-CWD case:

```sh
cd /private/tmp
/Users/gengyang/Vir-3.0/bin/virc \
  /private/tmp/vir_sysroot_audit/app.vri \
  -o /private/tmp/vir_sysroot_audit/from_tmp.out --color=never -q
```

Kết quả: exit 1, E2120:

```text
failed to read stdlib registry: failed to locate stdlib/stdlib.vri
```

Environment override probe:

```sh
cd /private/tmp
VIR_SYSROOT=/Users/gengyang/Vir-3.0 \
  /Users/gengyang/Vir-3.0/bin/virc \
  /private/tmp/vir_sysroot_audit/app.vri \
  -o /private/tmp/vir_sysroot_audit/from_env.out --color=never -q
```

Kết quả: vẫn exit 1 với cùng E2120.

CLI observability probes:

```sh
./bin/virc --print-sysroot --color=never
./bin/virc --print-stdlib --color=never
```

Cả hai exit 1 với `unknown option`.

## 6. Evidence

- CONFIRMED: `module_resolver.vri:23-37` phụ thuộc source-tree/CWD search và
  không xét executable prefix.
- CONFIRMED: `module_resolver.vri:60-71,123-146` đọc `root` cùng mappings từ
  registry và resolve physical paths tương đối từ registry parent; cơ chế map
  đã có thể dùng với installed registry.
- CONFIRMED: `driver/config.vri:18-29` không lưu sysroot hoặc stdlib registry.
- CONFIRMED: `driver/args.vri:107-117,125-304` không parse các sysroot/print
  options; unknown option đi tới `vircArgumentError()` tại dòng 296-299.
- CONFIRMED: `cli_environment.vri:124-180` có environment adapter; repository
  search không tìm thấy `VIR_SYSROOT` trong compiler source.
- CONFIRMED: LSP có `--stdlib-registry PATH`, chứng minh explicit registry path
  đã tồn tại cho IDE surface nhưng chưa thống nhất với compiler CLI.
- OBSERVED: foreign-CWD và `VIR_SYSROOT` probes cùng fail E2120; repo-CWD control
  pass với cùng binary/source.
- OBSERVED: `--print-sysroot` và `--print-stdlib` cùng fail unknown option.
- HYPOTHESIS: source-tree probing được giữ từ bootstrap/development workflow và
  chưa được tách thành policy theo build/install mode.
- NOT_VERIFIED: installer/release artifact hiện tại, Windows executable-path
  behavior, symlink/shim contract, cross-target runtime layout và chính sách
  compatibility metadata compiler–stdlib.

## 7. Scope

### Affected

- `virc` CLI/configuration;
- standard-library registry discovery;
- executable-prefix/sysroot resolution;
- release and development layout separation;
- compiler–stdlib version compatibility;
- CWD-independent compilation and CI/multi-toolchain use;
- consistency với `vir-lsp` registry selection.

### Not affected / Unknown

- Nội dung và public APIs của từng stdlib module vẫn thuộc STLB.
- Viron network registry, download, signing, cache và update lifecycle thuộc
  `VIRON-ISS-0001`.
- ISSUE không quyết định package manifest/lockfile format.
- ISSUE không đổi module namespace `json` thành `std.json`; đây là quyết định
  language/package namespace riêng.
- ISSUE không yêu cầu hardcode path tuyệt đối của checkout hiện tại.

## 8. Impact

Không có toolchain sysroot, binary `virc` không portable ra ngoài source checkout
và project có động cơ vendor stdlib. Điều này làm duplicate source, tăng kích
thước repo, cho phép AI/tooling sửa nhầm stdlib như project code, gây phụ thuộc
CWD, và không bảo đảm cặp `virc X.Y ↔ stdlib X.Y`.

Trong CI, cross-compile và máy có nhiều Vir version, cùng một command có thể lấy
nhầm registry từ ancestor/CWD thay vì stdlib đi cùng compiler. Workaround hiện
tại là chạy từ checkout phù hợp hoặc copy stdlib; cả hai đều không thích hợp cho
release toolchain.

## 9. Preliminary Analysis

- CONFIRMED: lỗi là stdlib discovery/ownership, không phải module-to-file mapping;
  `stdlib.vri` đã là registry authority.
- CONFIRMED: current algorithm không phụ thuộc executable location, nên layout
  `bin/virc` + sibling `stdlib/` vẫn fail từ foreign CWD.
- CONFIRMED: environment adapter và IDE explicit-registry hook đã có một phần
  primitive cần thiết, nhưng không tạo thành compiler sysroot contract.
- HYPOTHESIS: cần một immutable resolved-toolchain context được tạo trước
  preprocessing và dùng chung bởi CLI, resolver, diagnostics và IDE handoff.
- HYPOTHESIS: release/dev behavior nên là explicit build/profile policy; giữ
  source-tree fallback không điều kiện sẽ tiếp tục cho phép version skew.
- NOT_VERIFIED: layout canonical cuối cùng là compact hay FHS-style; PLAN/SPEC
  phải chốt một profile và migration thay vì resolver đoán cả hai tùy CWD.

## 10. Acceptance Criteria

- [x] Một approved architecture/PLAN chốt toolchain prefix, sysroot, stdlib
  directory, registry path, runtime layout và compiler–stdlib compatibility
  metadata cho từng release profile.
- [x] `virc --sysroot <path>` chọn sysroot tường minh; path sai hoặc incompatible
  fail closed và không rơi xuống CWD/source-tree fallback.
- [x] `VIR_SYSROOT` hoạt động khi CLI không override; CLI có precedence cao hơn
  environment và invalid environment value cũng fail closed.
- [x] Khi không có override, release `virc` suy installed sysroot từ canonical
  executable location/manifest, gồm absolute path, PATH invocation và symlink or
  dispatcher handoff.
- [x] `virc --print-sysroot` và `virc --print-stdlib` chạy không cần input,
  in canonical absolute path đang thực sự được compiler dùng, và có machine-mode
  output/exit behavior được test.
- [x] Stdlib modules luôn được map qua `<stdlib-directory>/stdlib.vri`; resolver
  không biến filesystem layout thành module namespace hoặc hardcode checkout path.
- [ ] Project-local module, resolved dependency và sysroot stdlib layers có
  precedence/collision policy tất định; exact project/stdlib collision bị reject
  theo `VIR-ISS-0008`/`VIRC-ISS-0047` (đang theo dõi tại `VIRC-ISS-0047` OPEN); project không cần vendor/copy stdlib.
- [x] Release mode không tìm stdlib từ current working directory. Development
  source-tree fallback phải explicit, observable và không được thắng CLI/env hoặc
  installed sysroot.
- [ ] Compiler kiểm tra compatibility giữa binary, registry schema, stdlib và
  compiler-coupled runtime; mismatch có diagnostic ổn định (Round 5 & Round 6 audits phát hiện các fail-open defects: block comment #*#, string literal stripping, duplicate metadata rejection per VIR-SPC-0006:142, SemVer component arithmetic overflow checks, decoy prelude declarations type i64_alias / include vir.rt.alloc.fake / fake_vir_alloc, và malformed/empty directives schema = / garbage / = value; đã remediate bằng token-level matchers với identifier boundary enforcement và strict line grammar parsing; bộ test mở rộng lên 37/37 PASS; giữ mở [ ] chờ audit độc lập chấp nhận).
- [x] Integration tests compile một project ngoài checkout từ unrelated CWD và
  kiểm tra explicit override, missing sysroot, malformed registry, version
  mismatch, PATH/symlink invocation và hai toolchain versions song song (37/37 automated contract scenarios).
- [x] `vir-lsp` và `virc` dùng cùng resolved sysroot/stdlib identity hoặc có
  handoff contract rõ ràng; không tạo hai precedence algorithms khác nhau.
- [ ] Existing module resolver, compiler project-ingestion, strict diagnostics,
  CWD-independence và paper validation gates pass trước closure (gate `./run_tests.sh min` hiện ghi nhận 21 pre-existing failures chưa được cấp baseline exception).
- [ ] Một accepted REPORT ghi layout thực tế, before/after reproduction, tests
  đa platform khả dụng và các giới hạn chưa được hỗ trợ (`VIRC-RPT-0045` hiện ở `REVIEW` / `REQUIRES_FOLLOWUP`).

## 11. Related Papers

### Issues

- `VIRON-ISS-0001` — lifecycle cài đặt/cập nhật/verify stdlib và materialize
  sysroot; liên kết hai chiều với ISSUE này.
- `VIRON-ISS-0003` — umbrella gap cho end-to-end toolchain/package/registry
  lifecycle; đã ghi nhận compiler chưa có `--sysroot`/`--module-map`.
- `VIR-ISS-0006` — audit module/include specification và current registry
  behavior.
- `VIRC-ISS-0047` — exact project/active-stdlib collision diagnostics,
  provenance và native/tooling regression parity.

### Plans

- `VIRC-PLN-0028` — Toolchain sysroot discovery and CWD-independent standard library resolution plan
- `VIRON-PLN-0001` — intended Viron implementation plan; compiler-side changes
  vẫn cần PLAN/VIRC traceability phù hợp trước implementation.

### Reports

- `VIRC-RPT-0045` — Toolchain sysroot discovery and CWD-independent standard library resolution report

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from foreign-CWD, environment override, and CLI observability probes against `virc 4.2.1` |
| 2026-10-06 | Linked `VIRON-ISS-0001` and separated compiler sysroot discovery from Viron stdlib lifecycle ownership |
| 2026-10-06 | Linked VIRC-PLN-0028 |
| 2026-10-06 | Linked VIRC-ISS-0047 and delegated exact project/stdlib collision diagnostics and tests |
| 2026-10-06 | Linked VIRC-RPT-0045 |
| 2026-10-06 | Reopened: identified gaps in schema validation, relative path canonicalization, standalone compilation fallback leak, and vir-lsp parity |
| 2026-10-06 | Reopened per audit: missing real version/ABI compatibility check, standalone vir-lsp fail-closed gate, explicit registry validation, test false positive, missing PATH/version tests, and regression gate status |
| 2026-10-06 | Reopened per Round 3 audit: missing sysroot containment check, fail-open compatibility parser, superficial prelude size check, and SPEC metadata synchronization gap |
| 2026-10-06 | Closed: verified all 13 criteria across 28 contract tests, containment check, strict SemVer compatibility, structural prelude verification, VIR-SPC-0006 v3.2.0 synchronization, and zero regressions |
| 2026-10-07 | Reopened to VERIFYING per Round 4 audit remediation: exact key matching via virc_sub_matches (fixing abi_v prefix leak), comment-stripping parser-aware structural prelude validation (virc_strip_comments), expanded to 30 contract tests, keeping open criteria 7, 12, 13 pending VIRC-ISS-0047, regression gate baseline, and accepted report |
| 2026-10-07 | Round 5 audit remediation: canonical block comments (#*#), string literal stripping, duplicate metadata rejection per VIR-SPC-0006:142, SemVer component overflow checks, expanded to 34 contract tests, kept criterion 9 open pending audit acceptance |
| 2026-10-07 | Round 6 audit remediation: token-level declaration matching with identifier boundaries (rejecting type i64_alias, include vir.rt.alloc.fake, fake_vir_alloc), strict line parsing (rejecting schema =, garbage, = value), expanded to 37 contract tests, kept criterion 9 open pending audit acceptance |
