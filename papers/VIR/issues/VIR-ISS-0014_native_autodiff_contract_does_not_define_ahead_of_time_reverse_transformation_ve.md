---
id: "VIR-ISS-0014"
type: "ISSUE"
domain: "VIR"
title: "Native autodiff contract does not define ahead of time reverse transformation versus runtime graph tracing"
status: "CLOSED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "tensor"
  - "autodiff"
  - "train"
  - "hir"
  - "mir"
  - "memory-model"
  - "backend"
related:
  issues:
    - "VIR-ISS-0011"
    - "VIRC-ISS-0017"
    - "VIRC-ISS-0018"
  plans:
    - "VIR-PLN-0001"
    - "VIRC-PLN-0033"
  reports:
    - "VIR-RPT-0001"
    - "VIRC-RPT-0050"
supersedes: null
superseded_by: null
tags:
  - "autodiff"
  - "ahead-of-time"
  - "reverse-mode"
  - "native-tensor"
  - "language-contract"
---

# VIR-ISS-0014 — Native autodiff contract does not define ahead of time reverse transformation versus runtime graph tracing

## 1. Summary

Active SPEC xác định `train` và `.backward()` là native autodiff nhưng mô tả
“tracing toàn đồ thị” và RAM overhead 2–3×, không chốt compiler phải sinh
backward program ahead-of-time hay xây computation graph/tape lúc runtime.
Hai mô hình có observable memory, control-flow, lifetime và diagnostics khác
nhau; VIRC không thể triển khai toàn diện khi language contract còn mơ hồ.

Hướng quyết định được chọn cho SPEC revision là AOT-first reverse-mode autodiff,
không có implicit runtime tracing fallback: compiler phân tích typed program,
xây derivative IR lúc compile time và hạ thẳng forward/backward code cho từng
target. Runtime dynamic computation graph không thuộc execution model mặc định.
Đây không nhất thiết là “duyệt ngược raw AST”; transformation diễn ra sau khi
type, shape, control flow, effects và ownership đã được chuẩn hóa ở typed HIR/
MIR/SSA.

AOT-first không có nghĩa cấm dữ liệu hoặc control flow động và không có nghĩa
zero allocation. Derivative program do compiler sinh có thể cần runtime
activation/execution-state storage để ghi giá trị trung gian, số vòng lặp hoặc
nhánh thực sự đã chạy. Storage này không được biến thành runtime graph gồm node
toán tử, parent link và operator dispatch metadata.

## 2. Context

Native `tensor[T; S...]` mang static shape; `**`/`><` có compile-time shape
rules. Những metadata này cho phép specialization và symbolic differentiation
đối với graph tĩnh. Tuy nhiên §26.4 hiện dùng ngôn ngữ runtime tracing, còn
compiler hiện tại chỉ ghi một record matmul cố định vào arena runtime và gọi
hard-coded backward stub 2×2.

`VIRC-ISS-0018` theo dõi runtime graph gap theo contract hiện hành. Hướng AOT-
first đã được chọn trong ISSUE này nhưng chưa trở thành normative language
contract cho tới khi active English/Vietnamese SPECs được sửa đồng bộ và phê
duyệt. Vì vậy `VIRC-ISS-0018` chưa được re-scope trong bước này.

### 2.1 Decision direction pending SPEC adoption

| Thành phần | Hướng quyết định |
|---|---|
| `tensor[T; S...]` | Native type |
| `train` | Native language construct |
| `.backward()` | Native compiler-recognized operation |
| Reverse-mode autodiff | Compile-time typed-IR transformation |
| Static computation graph | Sinh forward/backward code AOT |
| Dynamic control flow | AOT-generated derivative CFG với execution-state storage khi cần |
| Dynamic computation graph | Không tạo ngầm tại runtime |
| Activation storage | Compiler-planned theo lifetime/ownership |
| Checkpointing | Compiler optimization; policy có thể bổ sung sau |
| Gradient buffers | Native storage, không yêu cầu graph objects |
| Custom gradients | Native contract, có thể triển khai theo giai đoạn |

Các quy tắc cần được đưa vào SPEC:

- **AOT-first:** mọi differentiable program hợp lệ được chuyển thành derivative
  IR khi compile.
- **No implicit dynamic graph:** compiler không được âm thầm fallback sang
  runtime graph tracing.
- **Dynamic control flow is not automatically unsupported:** branch và loop
  phụ thuộc dữ liệu có thể dùng reverse CFG cùng bounded hoặc dynamic execution-
  state storage.
- **Fail closed:** nếu không chứng minh được differentiability, ownership safety
  hoặc target support, compiler phải báo diagnostic trước artifact emission.
- **No fixed memory multiplier:** SPEC không áp đặt tỷ lệ RAM 2–3x hoặc mức tiết
  kiệm cố định nếu chưa nêu workload, điều kiện và benchmark tái lập được.
- **Native remains native:** `tensor`, `train`, `.backward()` và tensor operators
  không bị hạ cấp thành library wrappers.

## 3. Expected Behavior

- Static tensor shapes, dtype và differentiable operations được kiểm tra trước
  artifact emission.
- Với statically differentiable graph, compiler sinh forward/backward HIR/MIR/
  LIR và target code ahead-of-time; runtime không cần dynamic graph nodes,
  operator dispatch tape hoặc graph traversal.
- Với data-dependent branch/loop, compiler sinh derivative CFG ahead-of-time và
  chỉ lưu runtime execution state/activation cần thiết để replay đường thực thi;
  program không bị reject chỉ vì control flow động.
- Activation/value storage cần cho đạo hàm vẫn tuân ownership/lifetime và có
  compile-time lifetime/reuse plan; “không dynamic graph” không có nghĩa mọi
  activation có thể bị loại.
- Contract xác định rõ dynamic control flow, recursion, data-dependent shape,
  mutation, aliasing, side effects và unsupported/custom-gradient operations.
- Không có implicit hybrid/runtime-graph fallback. Một cơ chế runtime graph về
  sau, nếu được đề xuất, phải là contract opt-in riêng và không thay đổi nghĩa
  của execution model AOT mặc định.
- Backward kernels giữ native tensor/SIMD/FMA capability trên mọi supported
  target hoặc fail closed với stable capability diagnostic.

## 4. Actual Behavior

- §26.4 nói mọi tensor operation được “tracing tự động” và backward đi ngược
  toàn computation graph; bảng so sánh ghi `train` tốn khoảng 2–3× RAM.
- AST-to-MIR chỉ phát `MIR_INTR_TRAIN` khi vào block, không sinh derivative IR.
- `.backward()` hạ thành `MIR_INTR_BACKWARD` gọi runtime stub.
- ARM64 runtime tape giữ một W, một X, một output/count/type marker và backward
  stub cấp phát hai gradient tensor cố định 48 byte cho trường hợp 2×2.
- Không tìm thấy AOT reverse-mode transform trên AST/HIR/MIR/SSA.
- Focused autodiff fixture hiện compile nhưng chạy exit `10`, cho thấy cả stub
  hẹp hiện tại cũng không đạt oracle trên working tree được kiểm tra.

## 5. Reproduction

```sh
sed -n '3654,3692p' papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md
rg -n 'MIR_INTR_(TRAIN|BACKWARD)|backward|tape' compiler/src

./bin/virc tests/strict_v2/test_autodiff_e2e.vri \
  -O1 -q -o /tmp/vir_autodiff
/tmp/vir_autodiff
```

Observed ngày 2026-10-08: compilation thành công; executable exit `10`.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0018` §26.1 mang static shape trong native tensor type.
- CONFIRMED: §26.4 yêu cầu native autodiff nhưng mô tả runtime-style tracing và
  chưa định nghĩa AOT/hybrid/fallback boundary.
- CONFIRMED: current lowering phát train/backward intrinsics, không derivative
  program; current ARM64 backward stub hard-code một 2×2 matmul record.
- OBSERVED: `test_autodiff_e2e.vri` exit `10` trên current `bin/virc`.
- HYPOTHESIS: typed MIR/SSA là transformation boundary tốt hơn raw AST vì đã có
  resolved dtype/shape/CFG/ownership nhưng còn đủ operation structure.
- NOT_VERIFIED: tập differentiable operation cuối cùng, checkpointing policy,
  higher-order derivatives, dynamic-shape support và custom-gradient ABI.

## 7. Scope

### Affected

- native reverse-mode autodiff semantics for `train` and `.backward()`;
- compile-time derivative IR generation;
- static versus dynamic graph policy;
- activation ownership, lifetime, reuse and checkpointing;
- control-flow/effect restrictions and diagnostics;
- target-native backward lowering contract.

### Not affected / Unknown

- Static tensor shape checking implementation đã có contract riêng.
- Forward `**`/`><` SIMD/FMA implementation thuộc `VIRC-ISS-0017`.
- Không demote tensor, infer, train hoặc quantize xuống stdlib.
- Không mở VIRC AOT-autodiff implementation issue trước khi contract này được
  resolved bằng approved SPEC revision.
- Runtime execution-state storage phục vụ reverse CFG không bị phân loại nhầm
  thành dynamic computation graph tracing.

## 8. Impact

Nếu runtime tracing được triển khai trước khi chốt AOT contract, Vir có thể khóa
vào dynamic graph overhead trái với mục tiêu native/low-RAM. Nếu compiler loại
tape mà không định nghĩa control flow và activation lifetime, backward có thể
sai hoặc use-after-free. Severity S2 cho contract ambiguity, priority P1 vì nó
chặn implementation direction của S1/P0 `VIRC-ISS-0018`.

## 9. Preliminary Analysis

- CONFIRMED: static shape metadata cho phép reject mismatch trước codegen và là
  nền cho specialization.
- CONFIRMED: current implementation là fixed runtime record, không phải AOT AD.
- DECISION PENDING SPEC: AOT reverse transform là normative execution model;
  runtime dynamic computation graph không phải fallback mặc định.
- CONFIRMED: AOT không loại bỏ nhu cầu giữ activation và execution state mà
  derivative program cần ở runtime.
- HYPOTHESIS: typed MIR/SSA là boundary phù hợp nhất; PLAN/SPEC revision phải
  chọn boundary chính xác dựa trên IR invariants hiện hành.
- NOT_VERIFIED: representation tối ưu cho bounded/dynamic execution-state
  storage, checkpointing policy và giới hạn data-dependent workloads.

## 10. Acceptance Criteria

- [x] Chọn hướng normative execution model: AOT-first reverse-mode AD, không
  implicit runtime graph tracing fallback; AOT vẫn cho phép runtime activation/
  execution-state storage khi derivative program cần.
- [x] Nếu chọn AOT cho graph tĩnh, định nghĩa differentiation stage trên typed
  HIR/MIR/SSA, derivative IR invariants và forward/backward coupling.
- [x] Định nghĩa differentiability rules cho tensor ops, scalar ops, branches,
  loops, calls, mutation, aliases, effects, recursion và external functions.
- [x] Định nghĩa static-shape requirements, dynamic-shape behavior và stable
  diagnostics trước artifact emission.
- [x] Định nghĩa activation lifetime, ownership, checkpoint/recompute, reuse và
  arena cleanup trên normal/early/error exits.
- [x] Định nghĩa gradient accumulation dtype, shape, initialization, repeated
  backward, branching/fan-out và public gradient observation/update semantics.
- [x] Định nghĩa custom-gradient/stop-gradient contract hoặc explicit non-goal.
- [x] Định nghĩa target capability matrix cho forward/backward SIMD/FMA kernels
  và fail-closed behavior khi target không hỗ trợ.
- [x] Xóa các cam kết RAM cố định `~2–3x`/`~50%` khỏi normative text hoặc thay
  bằng điều kiện và benchmark tái lập được; phân biệt graph metadata với
  activation/execution-state memory.
- [x] Active English/Vietnamese SPECs được sửa đồng bộ bằng approved PLAN/REPORT.
- [x] Chỉ sau resolution mới mở hoặc re-scope VIRC implementation issue; không
  tạo umbrella issue trùng `VIRC-ISS-0017`/`0018` trước gate này.

## 11. Related Papers

### Issues

- `VIR-ISS-0011` — native tensor/AI classification.
- `VIRC-ISS-0018` — current runtime-mode and autodiff implementation gap.
- `VIRC-ISS-0017` — native SIMD/FMA tensor lowering.

### Plans

- `VIR-PLN-0001` — AOT-first native reverse-mode contract revision.

### Reports

- `VIR-RPT-0001` — accepted contract and closure report.

## 12. VIRC implementation sequence after the language gate

Không bắt buộc tách thành bốn ISSUE mới; PLAN của `VIRC-ISS-0018` có thể chia
thành các phase reviewable sau khi SPEC revision được approved:

1. Static differentiable subset: scalar arithmetic, tensor elementwise,
   matmul, chain rule, branching/fan-out và gradient accumulation.
2. Control flow: branches, loops, function calls và activation lifetime.
3. Memory optimization: buffer reuse/planning, checkpoint/recompute và cleanup.
4. Extended differentiation: custom-gradient contract, recursion và higher-
   order derivatives chỉ khi được SPEC duyệt.

Mỗi phase phải có numerical gradient checks, finite-difference comparison khi
phù hợp, ownership stress tests và inspection mã native đầu ra trên từng target
được tuyên bố hỗ trợ.

## 13. Resolution

VIR-SPC-0017/0018 v3.2.0 and VIR-SPC-0001/0002/0003 v2.1.0 now define the
AOT-first typed-IR reverse transformation, gradient/storage semantics, and
fail-closed capability policy. VIR-RPT-0001 is accepted with
`READY_FOR_CLOSE`; this issue is closed.

## 14. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Closed after approved v3.2.0/v2.1.0 SPEC revisions, VIR-PLN-0001, and accepted VIR-RPT-0001 |
| 2026-10-08 | Opened from SPEC/runtime-model conflict and current fixed-tape autodiff audit |
| 2026-10-08 | Linked VIR-ISS-0011 |
| 2026-10-08 | Linked VIRC-ISS-0018 |
| 2026-10-08 | Linked VIRC-ISS-0017 |
| 2026-10-08 | Recorded AOT-first decision direction, prohibited implicit runtime graph fallback, and added post-SPEC implementation phases |
