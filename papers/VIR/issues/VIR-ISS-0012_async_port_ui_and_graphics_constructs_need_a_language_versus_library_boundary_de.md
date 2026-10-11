---
id: "VIR-ISS-0012"
type: "ISSUE"
domain: "VIR"
title: "Async port UI and graphics constructs need a language versus library boundary decision"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "language"
components:
  - "async"
  - "port"
  - "ui"
  - "graphics"
  - "javascript-parity"
  - "runtime-separation"
related:
  issues:
    - "VIR-ISS-0011"
    - "VIR-ISS-0013"
    - "VIRC-ISS-0056"
    - "VIRC-ISS-0057"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "language-boundary"
  - "stdlib"
  - "async"
  - "ui"
  - "graphics"
  - "native-type"
  - "ecmascript-parity"
---

# VIR-ISS-0012 — Async port UI and graphics constructs need a language versus library boundary decision

## 1. Summary

Active SPEC chưa chốt nhất quán ranh giới giữa compiler-native semantics và
library/framework policy cho async/task/port, reactive/morph, bundle/expose và
GPU resource forms. §1.2 yêu cầu scheduler/executor/mailbox thuộc Library,
trong khi §22–25 đưa nhiều policy operation thành keyword.

Issue này phải giải quyết hợp đồng ngôn ngữ trước mọi VIRC cleanup. Tensor và
AI constructs không thuộc removal scope: `tensor`, `**`, `><`, `infer`,
`train`, `quantize` được giữ native theo `VIR-ISS-0011`.

Ba nguyên tắc phân định đã được chốt ở mức ISSUE: Native Type Guarantee,
Library Utility Principle và JavaScript Syntax and Capability Parity. “Native”
ở đây bao gồm compiler-recognized type, intrinsic operation và language
semantics; không bắt buộc mỗi capability phải có một keyword riêng.

## 2. Context

Language cần đủ primitive để compiler đảm bảo type, ownership, suspension và
native lowering, nhưng không nên cố định scheduler, channel implementation, UI
framework, GPU API hoặc endpoint protocol. Hiện các phần này vừa có keyword
vừa thiếu executable contract, gây nhầm giữa “first-class syntax” và “đã có
portable semantics”.

## 3. Expected Behavior

### 3.1 Native Type Guarantee

Mọi kiểu dữ liệu được Vir công nhận ở cấp ngôn ngữ phải có native support:

- compiler chịu trách nhiệm type checking, representation/layout, ownership và
  lowering khi phù hợp;
- không chuyển native type thành library wrapper chỉ nhằm giảm grammar;
- vector/SIMD, `flux`, tensor và các type được active SPEC công nhận phải được
  bảo toàn như native types;
- native support có thể dùng intrinsic/runtime helper, nhưng semantic owner vẫn
  là language/compiler và backend phải thấy đủ metadata để tối ưu;
- type thư viện như `HttpRequest` hay một backend-specific `GpuBuffer` không tự
  động trở thành native type nếu SPEC không công nhận nó.

### 3.2 Library Utility Principle

Utility function hoặc policy được phép chuyển sang thư viện khi việc chuyển đó:

- không làm mất language semantics, type/ownership guarantees hoặc native
  optimization capability;
- không buộc native value đi qua wrapper/boxing/dispatch layer không cần thiết;
- giữ observable behavior và zero-cost absence contract;
- có replacement API, compatibility decision và migration path rõ ràng.

Ứng viên gồm scheduling policy, executor selection, channel configuration, GPU
resource management và helper functions thao tác dữ liệu. Việc là “utility”
không đồng nghĩa implementation luôn thuần library: compiler intrinsic mỏng có
thể được dùng khi cần native lowering mà không mở rộng source keyword surface.

### 3.3 JavaScript Syntax and Capability Parity

Các construct/capability được Vir tuyên bố parity với **ECMAScript language
standard** phải được hỗ trợ native và không bị hạ thành opaque library wrapper.
Native parity có thể được biểu đạt bằng syntax, native type, compiler-recognized
intrinsic hoặc language semantics; không yêu cầu một keyword riêng cho mỗi API.

“JavaScript parity” mặc định không bao gồm toàn bộ browser/Node/framework
ecosystem. Web APIs như `AbortController` và `MessagePort`, hoặc framework forms
như React hooks, chỉ trở thành native Vir contract khi SPEC phê duyệt độc lập.

| Construct | Nguồn parity gần nhất | Định hướng VIR |
|---|---|---|
| `async` / `await` | ECMAScript syntax và suspension semantics | Native |
| Promise-equivalent / `task` | ECMAScript Promise/Job capability; không có `task` keyword tương ứng | Native capability nếu SPEC chốt; không mặc định bắt buộc keyword |
| `cancel` | `AbortController` là DOM Web API, không phải ECMAScript keyword | Native chỉ khi Vir định nghĩa cancellation thành language construct |
| `select` | Gần Promise combinators hơn là ECMAScript syntax | Native nếu SPEC chốt typed selection/suspension semantics; API vẫn là phương án hợp lệ |
| `reactive` | Không có ECMAScript native construct; React hooks là framework | Không được suy ra native chỉ từ JavaScript ecosystem parity |
| `port` | `MessagePort` là HTML Web API | Native type nếu Vir SPEC công nhận; Web API parity tự nó không đủ |
| `flux` / swizzle | Vir native SIMD type/operations | Native theo Native Type Guarantee, không phụ thuộc JS parity |
| `tensor`, `**`, `><`, `infer`, `train`, `quantize` | Vir native tensor/AI contract | Native, giữ nguyên theo `VIR-ISS-0011` |
| `bundle` / `expose` | Không có ECMAScript language construct tương đương trực tiếp | Đánh giá như build tooling, host integration hoặc approved language construct |

## 4. Actual Behavior

- §22 dùng keyword cho task/wait/cancel/quiet/select dù Task/executor thuộc Library.
- §23 định nghĩa port policy cụ thể MPSC, capacity và blocking behavior.
- §25 đưa reactive graph, morph UI mapping, bundle và expose endpoint vào core.
- §24 trộn native SIMD primitive với GPU buffer policy và hai atomic spellings.
- Các contract chưa chỉ ra tiêu chí nào bắt buộc syntax thay vì typed API.
- SPEC chưa định nghĩa “JavaScript parity” là ECMAScript, host Web API hay toàn
  ecosystem, nên cùng một lập luận có thể kéo framework/API tùy ý vào core.

## 5. Reproduction

```sh
sed -n '265,420p' papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md
sed -n '3026,3596p' papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md
sed -n '1,220p' papers/VIR/specs/VIR-SPC-0007_runtime_separation.md
```

## 6. Evidence

- CONFIRMED: `VIR-SPC-0007` giao Task, executor, scheduler và mailbox cho Library.
- CONFIRMED: `VIR-SPC-0018` §22–25 mô tả nhiều policy operation bằng keyword.
- CONFIRMED: §24 SIMD/native vector lowering là backend-sensitive và không đồng
  nhất với UI/GPU framework policy.
- CONFIRMED: ECMAScript specification định nghĩa Async Function, `await` và
  Promise semantics:
  <https://tc39.es/ecma262/multipage/ecmascript-language-functions-and-classes.html#sec-async-function-definitions>
  và <https://tc39.es/ecma262/multipage/control-abstraction-objects.html#sec-promise-objects>.
- CONFIRMED: `AbortController` thuộc DOM Standard, không phải ECMAScript:
  <https://dom.spec.whatwg.org/#interface-abortcontroller>.
- CONFIRMED: `MessagePort` thuộc HTML Standard Web Messaging:
  <https://html.spec.whatwg.org/multipage/web-messaging.html#message-ports>.
- OBSERVED: SPEC thiếu decision matrix giải thích vì sao từng form cần grammar.
- NOT_VERIFIED: replacement API cụ thể; đó là PLAN work sau language decision.

## 7. Scope

### Affected

- async/task/port semantics and runtime separation;
- SIMD primitive versus GPU resource policy;
- UI reactive/morph and build-time bundle/expose ownership;
- criteria for syntax, intrinsic, attribute/tooling or library API.
- normative meaning and boundary of JavaScript/ECMAScript capability parity.

### Not affected / Unknown

- `tensor`, `**`, `><`, `infer`, `train`, `quantize` không thuộc removal review.
- Không mở VIRC implementation/removal issue trước khi issue này được giải quyết.
- Không chọn scheduler, UI toolkit hoặc GPU backend cụ thể.
- Không sửa compiler trong language-contract phase.
- Không coi mọi Web API, Node API hoặc framework API là native Vir requirement.

## 8. Impact

Boundary không rõ làm grammar phình và compiler gánh framework policy, đồng
thời có nguy cơ chuyển nhầm native performance primitive sang wrapper library.
Severity S2, priority P1 để chốt contract trước implementation.

## 9. Preliminary Analysis

- CONFIRMED: coroutine suspension/borrow semantics cần compiler awareness;
  scheduler policy không cần compiler ownership.
- CONFIRMED: native type guarantee bảo toàn `flux`, vector/SIMD và tensor types;
  giảm keyword không được tạo library-wrapper abstraction quanh các type này.
- HYPOTHESIS: `wait`, `quiet`, channel configuration và executor policy có thể
  dùng typed APIs trên native async/await/task capability.
- HYPOTHESIS: `task`, `cancel`, `select` và `port` cần quyết định riêng theo
  language semantics; similarity với Promise/Web API không đủ tự động quyết
  định keyword status.
- HYPOTHESIS: reactive/morph là framework concern; bundle/expose là build/tooling
  concern; `deck` là GPU resource API trên native memory/intrinsic primitives.
- CONFIRMED: `flux`/swizzle là native theo Native Type Guarantee; atomic
  primitive tiếp tục được đánh giá như native memory semantics, không gom với
  framework removal.
- NOT_VERIFIED: API/intrinsic split cuối cùng và migration cost.

## 10. Acceptance Criteria

- [x] Chốt Native Type Guarantee: mọi SPEC-recognized type có compiler/native
  support; không demote thành library wrapper chỉ để giảm grammar.
- [x] Chốt Library Utility Principle: utility/policy có thể chuyển library nếu
  bảo toàn semantics, optimization capability, compatibility và migration.
- [x] Chốt JavaScript Syntax and Capability Parity: baseline là ECMAScript
  language standard; Web API/framework không tự động tạo native requirement;
  native capability không bắt buộc đồng nghĩa keyword riêng.
- [ ] Đưa ba nguyên tắc trên vào active English/Vietnamese SPECs bằng một
  approved normative revision.
- [ ] Duyệt decision matrix cho từng §22–25 construct theo ba nguyên tắc: safety
  semantics, backend knowledge, library expressibility, zero-cost và portability.
- [ ] Chốt minimal native async contract và library-owned executor/scheduling/
  channel policy, bao gồm task, cancellation, select và timeout ownership.
- [ ] Giữ `flux`/swizzle và SPEC-recognized SIMD/vector types native; chốt atomic
  source form và intrinsic/library boundary dựa trên memory/codegen evidence.
- [ ] Chốt reactive/morph/bundle/expose/deck ownership mà không phụ thuộc một
  framework/backend duy nhất.
- [ ] Ghi rõ `desk` không phải language feature nếu chưa có approved SPEC scope.
- [ ] Lập parity inventory phân biệt ECMAScript language, ECMAScript built-ins,
  Web/host APIs và framework capabilities; mỗi Vir native claim trỏ tới đúng lớp.
- [ ] Update focused contracts qua approved PLAN/REPORT trước khi mở VIRC
  implementation issues.
- [ ] Mọi removal dựa trên policy của `VIR-ISS-0013`.

## 11. Related Papers

### Issues

- `VIR-ISS-0011` — language surface classification and native tensor/AI rule.
- `VIR-ISS-0013` — syntax deprecation and migration policy.
- `VIR-SPC-0007` — runtime separation architecture.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened to resolve language/library ownership before compiler implementation issues |
| 2026-10-08 | Linked VIR-ISS-0011 |
| 2026-10-08 | Linked VIR-ISS-0013 |
| 2026-10-08 | Linked VIRC-ISS-0056 |
| 2026-10-08 | Linked VIRC-ISS-0057 |
| 2026-10-08 | Triaged with Native Type Guarantee, Library Utility Principle, and scoped ECMAScript parity; preserved native flux/tensor/AI semantics |
