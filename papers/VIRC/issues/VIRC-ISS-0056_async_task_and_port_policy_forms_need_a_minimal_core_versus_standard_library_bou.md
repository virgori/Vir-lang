---
id: "VIRC-ISS-0056"
type: "ISSUE"
domain: "VIRC"
title: "Async task and port policy forms need a minimal core versus standard library boundary"
status: "REJECTED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "runtime"
  - "stdlib"
components:
  - "async"
  - "task"
  - "port"
  - "lexer"
  - "lowering"
  - "runtime-boundary"
related:
  issues:
    - "VIR-ISS-0012"
    - "VIRC-ISS-0055"
    - "VIRC-ISS-0058"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "async"
  - "port"
  - "stdlib-boundary"
  - "language-simplification"
---

# VIRC-ISS-0056 — Async task and port policy forms need a minimal core versus standard library boundary

## 1. Summary

**REJECTED:** issue này được mở trước quyết định ngôn ngữ. Ranh giới native
async semantics và library scheduling/port policy thuộc `VIR-ISS-0012`; chỉ sau
khi VIR issue và SPEC liên quan được giải quyết mới được tạo VIRC implementation
issue. Các acceptance criteria dưới đây không cho phép sửa compiler.

Vir có keyword riêng cho `async`, `await`, `task`, `wait`, `cancel`, `quiet`,
`port`, `send`, `recv`, `select`, `timeout` và `pass`, trong khi active runtime
separation SPEC quy định Task, executor, scheduler và mailbox là trách nhiệm
thư viện. Compiler hiện có token/AST/MIR marker cho phần lớn các form nhưng
không có state-machine/executor/port implementation đủ contract.

Surface này cần được rút về một async core tối thiểu, còn scheduling policy,
task lifecycle, channel/port và multiplexing chuyển sang stdlib trừ khi một
construct chứng minh được rằng nó là semantic primitive không thể biểu đạt an
toàn bằng library API.

## 2. Context

`VIR-SPC-0007` và `VIR-SPC-0018` §1.2 đặt hard boundary: language sở hữu cú
pháp/type/ownership; compiler hạ state machine/suspension; library sở hữu Task,
executor, scheduler, actor, work stealing và mailbox. Cùng lúc, §22–23 mô tả
nhiều policy operation như source keyword, tạo căng thẳng trong chính active
contract.

Stdlib registry đã có `async`, `async.tasks`, `thread`, `thread.select`,
`thread.pool`, `thread.waitgroup` và `thread.worksteal`, nên cần một ABI/protocol
chung thay vì thêm keyword theo từng policy.

## 3. Expected Behavior

- Core chỉ giữ semantic cần compiler participation, với ứng viên mặc định là
  `async func` và `await`/suspension.
- Spawn, join, cancellation, detach, timeout, channel/port và select được biểu
  đạt bằng typed stdlib APIs trên một executor protocol thay thế được.
- Nếu giữ `select` hoặc port syntax, SPEC phải chứng minh unique ownership,
  fairness, cancellation và suspension semantics không thể đạt qua API.
- Không dùng concurrency thì executor/mailbox code không xuất hiện trong binary.
- Nhiều executor/channel implementations cạnh tranh mà không đổi source grammar.

## 4. Actual Behavior

- Lexer đăng ký 12 spelling liên quan trực tiếp tới async/task/port policy.
- Parser `select` chỉ hạ generic block; chưa có đầy đủ typed arm semantics.
- `recv`, task/wait/cancel/quiet/select chủ yếu đi qua builtin/MIR markers.
- Backend phân loại một số intrinsic như marker/no-op thay vì executable state
  transition.
- `stdlib/vir/async/task_runtime.vri` cung cấp handle/state tối thiểu nhưng chưa
  chứng minh scheduler queue, suspension, cancellation và multi-wait contract.
- Group 22 pass bằng synchronous pass-through; group 23 chỉ có một fixture
  không sử dụng port. Hai contract executor-selection và quiet-observation vẫn
  BLOCKED trong spec-gap suite.

## 5. Reproduction

```sh
rg -n 'AwaitKw|CancelKw|QuietKw|Task|Wait|PortKw|SendKw|RecvKw|SelectKw|TimeoutKw' \
  compiler/src/frontend/lexer/tokens.vri
rg -n 'MIR_INTR_(AWAIT|TASK|WAIT|SELECT|SEND|RECV|CANCEL|QUIET)' compiler/src
./run_tests.sh 22
./run_tests.sh 23
python3 tools/gap_contract_runner.py --virc bin/virc --filter '^ASYNC-' --verbose
```

Observed ngày 2026-10-08: group 22 báo 13/13 nhưng fixtures thực thi đồng bộ;
group 23 báo 1/1 với fixture không chứa port; ASYNC-003 và ASYNC-009 BLOCKED.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0007` đặt Task, scheduler, executor và mailbox ở Library.
- CONFIRMED: `VIR-SPC-0018` §22 đồng thời dùng `task`, `wait`, `cancel`,
  `quiet`, `select` như keyword-level forms và §23 định nghĩa language port.
- CONFIRMED: lexer/parser/AST/MIR có scaffolding rộng hơn executable backend.
- CONFIRMED: stdlib registry đã có nhiều async/thread scheduling modules.
- OBSERVED: test groups hiện không chứng minh suspension, first-completed
  selection, loser cancellation, bounded port hoặc detached cleanup.
- HYPOTHESIS: một `Future`/`TaskHandle`/`Channel` protocol với methods/functions
  có thể thay phần lớn policy keywords mà vẫn giữ `async`/`await` zero-cost.

## 7. Scope

### Affected

- language/compiler boundary cho async suspension;
- task spawn/join/cancel/detach semantics;
- typed channel/port send/recv/select/timeout;
- executor selection/link protocol và zero-cost absence;
- stdlib module identities, exports và conformance tests.

### Not affected / Unknown

- Không chọn executor implementation cụ thể.
- Không loại `async`/`await` trước khi có semantic-equivalent replacement.
- Không thay đổi ownership/borrow-across-await rules trong issue kiến trúc này.
- OS thread primitives và shared-memory synchronization chỉ liên quan qua ABI.
- NOT_VERIFIED: external consumer count cho từng keyword.

## 8. Impact

Giữ mọi policy operation thành keyword khóa Vir vào surface lớn nhưng vẫn thiếu
runtime, mâu thuẫn với bản sắc replaceable execution layer và tạo false promise
cho người dùng. Severity S2 vì phần lớn feature chưa release-qualified; P1 vì
boundary cần chốt trước khi hoàn thiện async backend.

## 9. Preliminary Analysis

- CONFIRMED: suspension point cần compiler participation, nhưng queue policy,
  executor và mailbox không cần là keyword.
- CONFIRMED: active specs hiện chứa tension giữa hard boundary và §22–23.
- HYPOTHESIS: target surface nên giữ `async func` + `await`; chuyển `task`,
  `wait`, `cancel`, `quiet`, `port`, `send`, `recv`, timeout và phần lớn select
  thành API. `select` syntax chỉ giữ nếu review chứng minh API không bảo toàn
  typing/cancellation/fairness.
- NOT_VERIFIED: ABI tối thiểu giữa generated coroutine state machine và executor.

## 10. Acceptance Criteria

- [ ] Lập decision matrix cho từng async/port spelling: unique compiler
  semantic, library expressibility, ownership effect, zero-cost và migration.
- [ ] Định nghĩa minimal coroutine ABI giữa compiler-generated state machine và
  executor library mà không hard-code scheduler.
- [ ] Chọn và SPEC hóa source surface tối thiểu; mọi removal phải qua VIR SPEC
  revision và `VIRC-ISS-0058` migration gate.
- [ ] Cung cấp public, exported stdlib protocol cho spawn/join/cancel/detach,
  timeout và typed channel/select trước khi xóa syntax tương ứng.
- [ ] Positive tests quan sát suspension/resume, cancellation, first-completed,
  bounded backpressure, move/copy qua channel và detached cleanup.
- [ ] Negative tests kiểm tra use outside async, type mismatch, use-after-move,
  invalid capacity và unsupported executor configuration.
- [ ] Minimal binary không dùng async không chứa executor/mailbox symbols.
- [ ] Ít nhất serial executor và một evented/threaded implementation chạy cùng
  source contract mà compiler không đổi.
- [ ] Formatter/LSP/docs/bootstrap và gap manifest hội tụ trước closure.

## 11. Related Papers

### Issues

- `VIRC-ISS-0055` — keyword inventory and classification.
- `VIRC-ISS-0058` — deprecation and migration contract.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened from runtime-boundary audit, async/port lowering inspection and focused test review |
| 2026-10-08 | Rejected because VIR-ISS-0012 must resolve the language/library boundary first |
| 2026-10-08 | Linked VIRC-ISS-0055 |
| 2026-10-08 | Linked VIRC-ISS-0058 |
| 2026-10-08 | Linked VIR-ISS-0012 |
