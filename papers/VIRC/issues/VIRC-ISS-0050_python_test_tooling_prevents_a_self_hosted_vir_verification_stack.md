---
id: "VIRC-ISS-0050"
type: "ISSUE"
domain: "VIRC"
title: "Python test tooling prevents a self-hosted Vir verification stack"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "compiler"
  - "tooling"
components:
  - "regression-suite"
  - "contract-runner"
  - "lsp-tests"
  - "performance-tests"
  - "ci"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "self-hosting"
  - "python-dependency"
  - "test-infrastructure"
  - "vir-migration"
  - "verification"
---

# VIRC-ISS-0050 — Python test tooling prevents a self-hosted Vir verification stack

## 1. Summary

Repository hiện dùng Python làm ngôn ngữ triển khai cho toàn bộ các lớp test
quan trọng: unit/contract tests, compiler subprocess harness, manifest runner,
LSP JSON-RPC client, performance/scaling checks, paper/tool tests và nhiều
validation helpers. Điều này khiến verification stack chưa self-hosted bằng
Vir và yêu cầu một Python runtime ngoài toolchain để chứng minh compiler hoạt
động đúng.

Issue này yêu cầu chuyển mọi công cụ và chương trình kiểm thử viết bằng Python
sang Vir. Khi đóng issue, test logic chuẩn của dự án phải chạy bằng executable
được viết bằng Vir; không còn Python test file, Python test runner hoặc Python
validation helper trong đường verification mặc định.

## 2. Context

Compiler đã có mục tiêu self-hosting, nhưng self-hosting binary không đồng nghĩa
verification self-hosting. `VIRC-ISS-0032` xử lý Python dependency trong đường
bundle/build compiler; nó không thay thế 64 Python files dưới `tests/` hay
`tools/gap_contract_runner.py` và các Python validation helpers.

Inventory ngày 2026-10-07 cho thấy:

- 64 file `tests/**/*.py`, tổng cộng 15,897 dòng; tất cả 64 chứa test framework,
  test function hoặc subprocess-based harness pattern;
- 13 file `tools/*.py`; trong đó contract runner, module graph/dependency/pass
  checks và sync/check paths được dùng làm verification gates;
- `run_tests.sh` có 10 vị trí gọi `python3`, Python module hoặc `.py` test/tool;
- riêng `tools/gap_contract_runner.py` dài 1,840 dòng và sở hữu manifest parsing,
  compile/run, diagnostics, timeout, baseline và result aggregation.

Migration phải bảo toàn observable test contract trước khi xóa Python. Đây là
ISSUE yêu cầu outcome; cấu trúc package/module và thứ tự chuyển đổi chi tiết
thuộc PLAN sau khi inventory được phê duyệt.

## 3. Expected Behavior

- Test suites và test runners chuẩn được viết bằng Vir (`.vri`) và build thành
  native test executables bằng một bootstrap/released `virc` được pin rõ ràng.
- Default verification path chạy mà không cần tìm hoặc gọi `python`, `python3`,
  `pytest` hay `unittest`.
- Vir harness hỗ trợ tối thiểu compile-pass, compile-fail, run, expected
  stdout/stderr, diagnostic matching, no-artifact assertions, timeout, target,
  optimization level, filters/groups, baseline comparison và machine-readable
  summary đang được Python runner cung cấp.
- LSP tests có Vir JSON-RPC/stdio harness hỗ trợ framing, concurrent requests,
  cancellation, UTF-16 positions, malformed/partial input, timeout và process
  cleanup.
- Performance tests giữ warmup, sample count, thresholds, raw measurement và
  deterministic failure reporting; migration không được biến performance gate
  thành smoke test.
- Test runner hoạt động độc lập với compiler-under-test đủ để phát hiện compiler
  crash/miscompile; bootstrap trust chain và version của runner được ghi nhận.
- Minimal shell orchestration MAY tiếp tục khởi chạy binaries, nhưng không được
  chứa test semantics thay thế cho Python đã xóa.

## 4. Actual Behavior

- `tests/` chứa Python tests dựa trên `pytest`, `unittest`, direct assertions và
  custom subprocess clients; nhiều suite không được biểu diễn bằng Vir source.
- `run_tests.sh` gọi trực tiếp `tools/gap_contract_runner.py`, module resolver
  tests, optimization/tail-call/source-map/narrow-cast/CLI tests bằng Python.
- Contract manifests được thực thi và tổng hợp bởi Python, nên các memory,
  type-safety và spec-gap gates không tự chạy chỉ với distributed Vir toolchain.
- LSP test launcher và nhiều protocol clients viết bằng Python; một số test còn
  spawn lại chính Python process để đo tài nguyên.
- Một phần Python files kiểm thử prototype/data/AI utilities trực tiếp trong
  Python thay vì kiểm thử public Vir modules và native artifacts.
- Không có canonical Vir test framework/runner được đăng ký làm replacement cho
  toàn bộ các capability trên.

## 5. Reproduction

Inventory có thể tái tạo từ repository root:

```sh
rg --files tests -g '*.py' | wc -l
rg --files tests -g '*.py' -0 | xargs -0 wc -l | tail -1
rg --files tools -g '*.py' | wc -l
rg -n 'python3?|\.py' run_tests.sh
rg -l 'unittest|pytest|def test_|subprocess\.Popen|subprocess\.run' tests -g '*.py' | wc -l
```

Observed result ngày 2026-10-07:

```text
tests Python files:       64
tests Python lines:       15897
tools Python files:       13
run_tests.sh call sites:  10
Python test harnesses:    64
```

Một máy có `bin/virc` nhưng không có Python hiện không thể chạy đầy đủ các lệnh
verification được gọi từ `run_tests.sh`, contract manifests và LSP/performance
suites.

## 6. Evidence

- CONFIRMED: `run_tests.sh:272,560,670-672,736,900,1300,1505,1594` gọi Python
  contract runner, compiler tests, module tools và CLI contract runner.
- CONFIRMED: `tools/gap_contract_runner.py` là Python executable 1,840 dòng,
  chứa manifest model, subprocess compile/run, timeouts, baseline và summary.
- CONFIRMED: `tests/run_lsp_tests.py` spawn một danh sách Python LSP clients rồi
  mới chạy JavaScript contract; các LSP Python files trực tiếp điều khiển
  `vir-lsp --stdio`.
- CONFIRMED: `tests/type_safety_contract/manifest.tsv` và
  `tests/memory_contract/manifest.tsv` phụ thuộc contract runner Python trong
  active verification workflow.
- CONFIRMED: repository inventory ở Reproduction trả đúng 64 Python test files,
  15,897 dòng và 13 Python tool files tại HEAD `d7dbdf1a`.
- OBSERVED: `./run_tests.sh 20`, focused type-safety contracts và memory
  contracts trong audit dict/map đều cần kết hợp shell với Python runner cho
  một phần evidence, dù compiler và fixtures chính là Vir.
- OBSERVED: không có `.vri` test-runner entrypoint hiện hành cung cấp feature
  parity với `gap_contract_runner.py` hoặc LSP Python clients.
- NOT_VERIFIED: mọi Python test hiện có đều đang được CI gọi. Inventory chứng
  minh source tồn tại, không chứng minh reachability của từng file từ mọi CI job.
- NOT_VERIFIED: Vir stdlib hiện đã có đầy đủ subprocess, monotonic clock,
  temporary-directory, JSON, filesystem và signal APIs cần cho migration hay
  chưa; PLAN phải gap-audit các API này trước implementation.

## 7. Scope

### Affected

- toàn bộ `tests/**/*.py`, gồm compiler, backend, optimizer, LSP, AI/tensor,
  toolchain, performance và governance/tool contracts;
- Python test/verification helpers dưới `tools/`, trước hết
  `gap_contract_runner.py`, module/dependency/pass checks và các `--check` path
  được dùng như release/verification gate;
- `run_tests.sh`, CI configuration, developer commands, manifests, expected
  output/baseline formats và test documentation;
- stdlib capabilities cần để Vir harness quản lý process, filesystem, timing,
  JSON/protocol framing và deterministic cleanup;
- bootstrap/release packaging của Vir test runner binaries.

### Not affected / Unknown

- Python utilities không tham gia test hoặc verification path, như one-time
  source migration helpers, không tự động thuộc issue này. Nếu một utility có
  cả production và validation role, phần validation phải chuyển sang Vir và
  phần còn lại phải được phân loại rõ trong PLAN.
- Issue không yêu cầu viết lại `run_tests.sh` bằng Vir nếu shell chỉ còn làm
  launcher/orchestrator và không giữ assertion/test semantics.
- Third-party tools có CLI độc lập MAY vẫn được gọi như system dependencies;
  không được nhúng Python script mới để né tiêu chí migration.
- JavaScript extension test trong `tools/vscode-vir` không phải Python và không
  nằm trong yêu cầu chuyển ngôn ngữ của issue này.
- NOT_VERIFIED: Python có còn là dependency của packaging/release/governance
  ngoài verification hay không; đó là phạm vi riêng.

## 8. Impact

Python test infrastructure tạo một trust/dependency boundary ngoài Vir
toolchain, làm release verification không thể chạy trên môi trường chỉ cài Vir,
chia logic assertions giữa nhiều frameworks và cản trở dogfooding các API
process/JSON/filesystem/timing của stdlib. Nó cũng cho phép compiler self-host
thành công trong khi test stack vẫn phụ thuộc một runtime và semantics khác.

Severity `S2` vì đây là architecture/verification gap, không phải bằng chứng
trực tiếp của data loss. Priority `P1` vì migration rộng, cần bắt đầu bằng
inventory/parity và chạy song song trước khi Python suites tiếp tục tăng thêm.

## 9. Preliminary Analysis

- CONFIRMED: migration không chỉ là đổi extension; Python harness hiện sở hữu
  process control, timeout, JSON, filesystem mutation, baseline và result
  aggregation semantics phải được đặc tả và giữ nguyên.
- CONFIRMED: xóa Python tests trước parity sẽ làm mất negative/mutation/
  performance/LSP coverage và không thỏa verification standard.
- HYPOTHESIS: một Vir test runtime nhỏ cộng với manifest-driven runners chuyên
  biệt có thể thay thế phần lớn custom scripts mà không tạo một monolith, nhưng
  module architecture phải được xác định trong PLAN.
- HYPOTHESIS: migration theo lớp capability — contract runner, compiler CLI,
  LSP, performance, Python-prototype tests — giảm bootstrap risk hơn chuyển theo
  tên thư mục.
- NOT_VERIFIED: API gaps nào bắt buộc compiler/stdlib changes và API nào đã có
  nhưng chưa được test; không được mở rộng compiler bằng API giả định.
- NOT_VERIFIED: cost và flakiness baseline của Vir replacement trên Linux
  x86-64/arm64 và macOS arm64.

## 10. Acceptance Criteria

- [ ] Publish a complete migration inventory mapping every current
  `tests/**/*.py` and every test/verification-role `tools/*.py` file to a Vir
  replacement, merged responsibility or explicit non-test classification.
- [ ] Establish a canonical registered Vir test framework/runner with documented
  module identities, ownership, CLI contract and machine-readable result format.
- [ ] Migrate all 64 current Python files under `tests/` to Vir tests or Vir
  fixtures; at closure `rg --files tests -g '*.py'` returns no files.
- [ ] Replace `tools/gap_contract_runner.py` with Vir implementation preserving
  manifest parsing, `compile_fail`/`run`, diagnostics, stdout/stderr, artifact,
  timeout, filter/group, target, optimization and baseline behavior.
- [ ] Migrate every Python module/dependency/pass/CLI validation helper used by
  the default test or release verification path to Vir equivalents.
- [ ] Remove all Python/pytest/unittest invocations from `run_tests.sh` and the
  default compiler verification CI; a clean environment without Python runs the
  documented suite successfully.
- [ ] Provide Vir LSP protocol test support for Content-Length framing,
  initialize/shutdown, request IDs, notifications, cancellation, concurrent and
  partial messages, UTF-16 ranges, timeouts and child-process cleanup.
- [ ] Preserve compiler negative-test guarantees: expected diagnostic code and
  source span, non-zero status, no output artifact and deterministic captured
  stdout/stderr.
- [ ] Preserve performance/scaling gates with recorded workloads, warmups,
  sample counts, thresholds, raw data and target metadata; no benchmark becomes
  output-only smoke coverage.
- [ ] Define and verify a bootstrap trust chain: the Vir test runner is built by
  a pinned released/bootstrap compiler and then tests the candidate compiler;
  candidate output alone is not its sole correctness oracle.
- [ ] Run Python and Vir implementations in parity mode before removal; an
  accepted REPORT accounts for every test count, expected failure, skip,
  timeout and result difference.
- [ ] Test runners are CWD-independent, network-independent by default, clean
  temporary artifacts and terminate spawned processes on success, failure,
  timeout and interruption.
- [ ] Vir test sources follow canonical syntax/module registries and pass module
  dependency checks; no direct generated-source editing is used for migration.
- [ ] Verification covers `-O0` and optimized runner builds on macOS arm64,
  Linux x86-64 and Linux arm64, or records a separately tracked unsupported
  target with explicit release impact.
- [ ] Developer/release documentation names the Vir-native commands and no
  longer presents Python commands as the canonical verification path.
- [ ] An accepted REPORT maps all criteria to reproducible evidence and lists
  any Python remaining outside test/verification scope with its classification.

## 11. Related Papers

### Issues

- None. `VIRC-ISS-0032` is adjacent self-host build dependency context, but it
  does not cover this migration and is not a formal lifecycle dependency.

### Plans

- None allocated.

### Reports

- None allocated.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Opened with repository-wide Python test inventory and measurable Vir-native verification acceptance criteria |
