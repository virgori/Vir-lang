---
id: "VIRC-ISS-0057"
type: "ISSUE"
domain: "VIRC"
title: "UI graphics and AI domain constructs need reassignment from compiler syntax to libraries and build tooling"
status: "REJECTED"
severity: "S2"
priority: "P1"
created: "2026-10-08"
updated: "2026-10-08"
owners:
  - "compiler"
  - "stdlib"
  - "tooling"
components:
  - "ui"
  - "graphics"
  - "simd"
  - "tensor"
  - "build-tooling"
  - "runtime-boundary"
related:
  issues:
    - "STLB-ISS-0001"
    - "VIR-ISS-0011"
    - "VIR-ISS-0012"
    - "VIRC-ISS-0017"
    - "VIRC-ISS-0018"
    - "VIRC-ISS-0019"
    - "VIRC-ISS-0036"
    - "VIRC-ISS-0055"
    - "VIRC-ISS-0058"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "ui"
  - "graphics"
  - "ai"
  - "stdlib-boundary"
  - "language-simplification"
---

# VIRC-ISS-0057 — UI graphics and AI domain constructs need reassignment from compiler syntax to libraries and build tooling

## 1. Summary

**REJECTED:** issue này vừa được mở sai thứ tự governance vừa chứa premise sai
về tensor/AI. `tensor` là native first-class type; `**` và `><` là native
operators; `infer`, `train`, `quantize` là native constructs để backend tối ưu
trực tiếp và không phải ứng viên chuyển xuống stdlib. `VIR-ISS-0011` ghi nhận
nguyên tắc này; `VIR-ISS-0012` sở hữu review UI/graphics. Không mở VIRC follow-up
cho đến khi các VIR contract được giải quyết.

Compiler dành keyword, AST node và intrinsic cho nhiều domain feature:
`reactive`, `morph`, `bundle`, `embed`, `expose`, `deck`, `flux`, `infer`,
`train`, `quantize`, `tensor`, `lock` và `atomic`. Nhiều form mới là marker,
no-op hoặc backend-specific stub, nhưng việc đặt chúng vào grammar biến policy
UI, graphics, service generation và ML framework thành nghĩa vụ của language
core.

Cần review lại từng construct để giữ trong core chỉ type/memory/operation có
semantic hoặc ABI không thể biểu đạt bằng library. Framework behavior, resource
packaging, endpoint generation, reactive graph, GPU resource và AI training
policy nên chuyển sang stdlib/build tooling trên compiler intrinsics tối thiểu.

## 2. Context

`VIR-SPC-0018` §24–26 tuyên bố GPU/SIMD/UI/AI là first-class language features.
Audit implementation cho thấy mức hoàn thiện không đồng đều: explicit flux có
một phần lowering, tensor/FMA có một số native paths, còn reactive/morph/expose
chủ yếu là markers và GUI module là façade extern. `deck` parser chưa giữ đầy
đủ declaration contract; infer/train/autodiff/quantize còn các ISSUE correctness.

Stdlib registry đã có `gpu`, `gui`, `gui.layout`, `math.tensor`,
`math.tensor_q8_0` và `hw.simd`, tạo nền để chuyển policy ra ngoài grammar nếu
public exports và compiler intrinsic boundary được hoàn thiện.

## 3. Expected Behavior

- Core chỉ giữ primitive ảnh hưởng trực tiếp tới type safety, memory model,
  ownership hoặc portable code generation.
- UI component model, reactive propagation và morph mapping là library/framework
  contracts, không phải universal semantics của mọi Vir program.
- GPU buffers là typed resource APIs; backend chọn Vulkan/Metal/WebGPU mà không
  đổi grammar.
- Asset embedding và endpoint generation là build/attribute/tooling contracts
  với inputs/outputs reproducible, không cần declaration keyword riêng.
- Tensor/SIMD core, nếu giữ, chỉ định representation và primitive operations;
  train/infer/autodiff/quantization policy thuộc math/AI libraries.
- Atomic semantics có một canonical form; không duy trì đồng thời `lock`, `!!`
  và `atomic` nếu chúng trùng chức năng.

## 4. Actual Behavior

- `reactive`, `morph` và `expose` lower thành marker/no-op trên các đường chính.
- Morph parser chưa nhận đầy đủ grammar mapping entity-to-component trong SPEC.
- GUI stdlib khai báo nhiều extern nhưng chưa có verified exported backend.
- Không có `desk` construct/module trong active spec hoặc registry.
- `bundle` coverage không chứng minh file contents được nhúng reproducibly.
- `deck` chưa có CPU/GPU mapped resource runtime portable.
- `flux` lowering và auto-vectorization chỉ hỗ trợ một tập operation/target hẹp.
- `infer`/`train` chưa restore lexical mode; autodiff chưa graph-general;
  quantization chưa đạt storage/transparent-inference contract.
- `math.tensor` có open S1/P0 issue về semantic và ownership correctness.

## 5. Reproduction

```sh
rg -n 'ReactiveKw|MorphKw|BundleKw|EmbedKw|ExposeKw|FluxKw|DeckKw|TensorKw|InferKw|TrainKw|QuantizeKw|Lock|AtomicKw' \
  compiler/src/frontend/lexer/tokens.vri
rg -n 'MIR_INTR_(REACTIVE|MORPH|EXPOSE|INFER|TRAIN)' compiler/src
rg -n '^(gpu|gui|gui\.layout|math\.tensor|hw\.simd)' stdlib/stdlib.vri
./run_tests.sh 24
./run_tests.sh 25
./run_tests.sh 26
```

Observed ngày 2026-10-08: groups 24/25 pass nhưng thiếu feature-depth oracles;
group 26 đạt 28/37, còn 9 failures trong tensor/AI paths.

## 6. Evidence

- CONFIRMED: lexer và AST dành first-class forms cho danh sách ở §1.
- CONFIRMED: LIR/codegen phân loại reactive/morph/expose như markers trên các
  đường đã kiểm tra.
- CONFIRMED: `stdlib/stdlib.vri` đã đăng ký các module domain tương ứng.
- CONFIRMED: `VIRC-ISS-0017`, `VIRC-ISS-0018`, `VIRC-ISS-0019`,
  `VIRC-ISS-0036` và `STLB-ISS-0001` ghi nhận implementation gaps hiện hành.
- OBSERVED: test group headline không tương ứng với feature coverage thực tế.
- HYPOTHESIS: phần lớn UI/AI policy có thể là library APIs nếu Vir có generic,
  comptime/attribute và compiler intrinsic boundary đủ nhỏ, ổn định.

## 7. Scope

### Affected

- lexer/parser/AST/MIR surface cho UI, graphics, SIMD và AI;
- stdlib module IDs, exports và backend/provider contracts;
- build-time resource/ABI generation;
- target capability diagnostics và zero-cost dead stripping;
- language and stdlib conformance suites.

### Not affected / Unknown

- Không tự động loại `tensor` hoặc `flux`; representation/performance review có
  thể chứng minh chúng xứng đáng là core types.
- Không gộp correctness repair của existing tensor/SIMD issues vào issue này.
- Không thiết kế một UI framework hoặc GPU API cụ thể.
- `desk` là feature chưa có normative identity; cần SPEC/module proposal riêng
  nếu tiếp tục.
- NOT_VERIFIED: macro/attribute/plugin capability hiện tại có đủ thay mọi
  removed construct hay không.

## 8. Impact

Domain keywords làm tăng compiler core và compatibility surface trước khi các
backend ổn định, đồng thời ngăn nhiều framework cạnh tranh. Severity S2 vì có
workaround/library direction nhưng architecture debt lan nhiều subsystem; P1
vì cần chốt boundary trước khi đầu tư hoàn thiện các marker thành runtime riêng.

## 9. Preliminary Analysis

- CONFIRMED: reactive/morph/expose không hiện có executable semantics tương xứng
  với first-class language contract.
- CONFIRMED: tensor/SIMD có compiler-sensitive representation/performance nên
  không thể chuyển library bằng text-only rewrite.
- HYPOTHESIS (withdrawn for tensor/AI): proposal chuyển
  `infer`/`train`/`quantize` xuống stdlib là không phù hợp với quyết định native
  first-class. Chỉ UI/graphics/framework/tooling forms còn chờ VIR review.
- HYPOTHESIS: `lock` và `!!` nên hội tụ về typed atomic API hoặc một form core,
  không giữ hai cú pháp tương đương.
- NOT_VERIFIED: exact performance loss của library-defined tensor/flux trên từng
  target; cần IR/disassembly prototype trước quyết định normative.

## 10. Acceptance Criteria

- [ ] Lập matrix cho từng construct: required compiler knowledge, type/ownership
  effect, library expressibility, target dependency, test depth và migration.
- [ ] Giữ core chỉ khi prototype chứng minh library/attribute form không thể
  đạt safety, zero-cost hoặc target portability tương đương.
- [ ] REJECTED — không triển khai proposal chuyển native tensor/AI constructs
  xuống stdlib; UI/graphics boundary chuyển sang `VIR-ISS-0012`.
- [ ] Review riêng `tensor`, `flux`, swizzle và atomic để chọn core type,
  compiler intrinsic hoặc library abstraction; không quyết định theo keyword
  hiện có.
- [ ] Cung cấp replacement public APIs/tooling và representative callers trước
  khi deprecate source form.
- [ ] Chốt `desk`: tạo normative proposal/module identity hoặc loại khỏi roadmap
  language; không để tên mơ hồ trong acceptance claims.
- [ ] Mọi thay đổi normative có updated VIR SPEC, English/Vietnamese parity và
  `VIRC-ISS-0058` migration plan.
- [ ] Per-feature runtime, negative, multi-target và binary-absence contracts
  thay thế các compile-only/no-op fixtures.
- [ ] Accepted REPORT ghi rõ construct giữ lại, chuyển library, hoặc loại bỏ và
  lý do evidence-based cho từng mục.

## 11. Related Papers

### Issues

- `VIRC-ISS-0017` — dense tensor native SIMD lowering.
- `VIRC-ISS-0018` — infer/train/autodiff runtime semantics.
- `VIRC-ISS-0019` — quantization contract.
- `VIRC-ISS-0036` — general SIMD implementation gaps.
- `STLB-ISS-0001` — public `math.tensor` semantic/ownership failures.
- `VIRC-ISS-0055` — keyword inventory and classification.
- `VIRC-ISS-0058` — deprecation and migration contract.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-08 | Opened from UI/graphics/AI syntax, lowering, stdlib registry and focused conformance audit |
| 2026-10-08 | Rejected incorrect tensor/AI demotion premise and deferred UI/graphics contract to VIR-ISS-0011/0012 |
| 2026-10-08 | Linked VIRC-ISS-0055 |
| 2026-10-08 | Linked VIRC-ISS-0058 |
| 2026-10-08 | Linked VIRC-ISS-0017 |
| 2026-10-08 | Linked VIRC-ISS-0018 |
| 2026-10-08 | Linked VIRC-ISS-0019 |
| 2026-10-08 | Linked VIRC-ISS-0036 |
| 2026-10-08 | Linked STLB-ISS-0001 |
| 2026-10-08 | Linked VIR-ISS-0011 |
| 2026-10-08 | Linked VIR-ISS-0012 |
