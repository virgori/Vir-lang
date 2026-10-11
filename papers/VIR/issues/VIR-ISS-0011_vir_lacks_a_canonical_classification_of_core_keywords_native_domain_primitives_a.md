---
id: "VIR-ISS-0011"
type: "ISSUE"
domain: "VIR"
title: "Vir lacks a canonical classification of core keywords native domain primitives and library policy forms"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "syntax"
  - "type-system"
  - "native-primitives"
  - "stdlib-boundary"
  - "language-governance"
related:
  issues:
    - "VIR-ISS-0012"
    - "VIR-ISS-0013"
    - "VIR-ISS-0014"
    - "VIRC-ISS-0048"
    - "VIRC-ISS-0055"
    - "VIRC-ISS-0057"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "keywords"
  - "native-first-class"
  - "language-surface"
  - "simplification"
---

# VIR-ISS-0011 — Vir lacks a canonical classification of core keywords native domain primitives and library policy forms

## 1. Summary

Active Vir SPEC liệt kê nhiều nhóm source form nhưng chưa phân loại normative
rõ thành: core structural keyword, native domain primitive, contextual form,
library policy form, compatibility alias hay retired spelling. Vì thiếu taxonomy
này, việc “giảm keyword” dễ đánh đồng native compiler semantics với framework
abstraction và có thể loại nhầm các primitive cần backend hiểu trực tiếp.

Issue này chốt nguyên tắc: `tensor` là kiểu dữ liệu native first-class;
`**` và `><` là native operators; `infer`, `train` và `quantize` là native
language/backend constructs. Chúng không phải ứng viên chuyển xuống stdlib chỉ
để giảm số keyword. Mục tiêu tinh gọn là bỏ alias và policy layer dư thừa trong
khi giữ đường lowering trực tiếp, ít abstraction cho tensor/AI.

## 2. Context

`VIR-SPC-0018` §24–26 đang trộn primitive vector/tensor, compiler optimization,
UI framework behavior, resource packaging và ML execution modes trong cùng
language surface. Lexer hiện đăng ký 108 spelling cho 98 token type, gồm nhiều
alias không tăng expressive power. Cần language decision trước khi compiler có
thể mở implementation/removal issue.

## 3. Expected Behavior

- SPEC phân loại từng source form theo owner và lý do phải tồn tại.
- Native type/operator/mode có lowering trực tiếp qua semantic IR/backend và
  không bắt buộc đi qua wrapper object/framework layer.
- `tensor[T; S...]`, `**`, `><`, `infer`, `train`, `quantize` giữ first-class
  status và có target capability contract rõ.
- Alias trùng nghĩa và framework policy không tự động trở thành core keyword.
- Compiler issue chỉ được mở sau khi language contract tương ứng được giải quyết
  hoặc có approved SPEC revision làm nguồn yêu cầu.

## 4. Actual Behavior

- SPEC chưa có taxonomy chung cho keyword/native primitive/library policy.
- Alias như `struct`/`record`, `continue`, `then`, `comptime`, `bit_*` cùng tồn
  tại với spelling canonical trong lexer.
- Một số construct có backend-sensitive representation (`tensor`, `flux`) bị
  đặt cạnh các framework form (`morph`, `expose`) mà không có tiêu chí phân lớp.
- Không có gate bắt buộc VIR decision hoàn tất trước VIRC implementation issue.

## 5. Reproduction

```sh
sed -n '1,240p' compiler/src/frontend/lexer/tokens.vri
sed -n '3026,3710p' papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md
./paper list --domain VIR --type ISSUE
./paper list --domain VIRC --type ISSUE
```

Lexer inventory ngày 2026-10-08: 108 spelling, 98 token type.

## 6. Evidence

- CONFIRMED: §26 định nghĩa tensor type và native operators `**`, `><`.
- CONFIRMED: §26 định nghĩa `infer`, `train`, `quantize` với backend/runtime
  behavior, không chỉ là convenience APIs.
- CONFIRMED: lexer có nhiều spelling ánh xạ cùng token.
- OBSERVED: implementation depth giữa native primitives và framework constructs
  rất khác nhau nhưng SPEC không có classification gate.
- NOT_VERIFIED: keyword target count tối ưu; issue không đặt quota tùy ý.

## 7. Scope

### Affected

- keyword and source-form taxonomy;
- native tensor/AI/SIMD primitive ownership;
- language/compiler/library boundary criteria;
- ordering giữa VIR contract issue và VIRC implementation issue.

### Not affected / Unknown

- Không demote `tensor`, `**`, `><`, `infer`, `train`, `quantize` xuống stdlib.
- Không quyết định backend implementation chi tiết.
- Không sửa SPEC trực tiếp trong ISSUE; normative result cần SPEC revision.
- Existing correctness/performance VIRC issues vẫn giữ scope đã có.

## 8. Impact

Phân loại sai có thể thêm abstraction layer vào hot path tensor/AI, làm mất
backend optimization opportunity và phá identity native-first-class. Ngược
lại, không phân loại khiến alias/framework keyword tiếp tục phình grammar.
Severity S2, priority P1 trước language surface freeze.

## 9. Preliminary Analysis

- CONFIRMED: native tensor type và operators cần compiler type/shape/lowering.
- CONFIRMED: infer/train/quantize cần backend-visible semantics để tối ưu mode,
  graph và representation mà không qua nhiều wrapper layer.
- HYPOTHESIS: surface nhỏ hơn đạt được bằng cách loại alias và chuyển policy
  framework, không phải bằng cách loại native computational primitives.
- NOT_VERIFIED: classification cuối cùng của `flux`, `deck`, reactive/morph và
  async policy; `VIR-ISS-0012` sở hữu boundary review đó.

## 10. Acceptance Criteria

- [ ] Định nghĩa taxonomy normative cho core keyword, native primitive,
  contextual form, library policy, compatibility alias và retired spelling.
- [ ] Ghi rõ `tensor` là native first-class type; `**` và `><` là native
  operators với direct semantic/IR/backend contract.
- [ ] Ghi rõ `infer`, `train`, `quantize` là native constructs và không yêu cầu
  stdlib wrapper làm semantic owner.
- [ ] Phân loại toàn bộ keyword/spelling hiện hành bằng taxonomy đã duyệt.
- [ ] Mỗi alias giữ lại phải có compatibility rationale và lifecycle; alias
  không tăng expressive power mặc định là ứng viên loại bỏ.
- [ ] Đặt governance gate: không mở VIRC issue triển khai/removal mới cho quyết
  định surface khi VIR issue/SPEC còn chưa giải quyết.
- [ ] English/Vietnamese SPEC parity và revision history được cập nhật qua một
  approved VIR PLAN/REPORT trước khi issue đóng.

## 11. Related Papers

### Issues

- `VIR-ISS-0012` — async/port/UI/graphics boundary decision.
- `VIR-ISS-0013` — deprecation and migration policy.
- `VIRC-ISS-0048` — existing non-SPEC alias evidence.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened to classify language surface while preserving tensor and AI constructs as native first-class semantics |
| 2026-10-08 | Linked VIR-ISS-0012 |
| 2026-10-08 | Linked VIR-ISS-0013 |
| 2026-10-08 | Linked VIRC-ISS-0048 |
| 2026-10-08 | Linked VIRC-ISS-0055 |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-08 | Linked VIR-ISS-0014 |
