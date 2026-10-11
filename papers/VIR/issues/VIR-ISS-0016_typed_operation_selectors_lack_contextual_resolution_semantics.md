---
id: "VIR-ISS-0016"
type: "ISSUE"
domain: "VIR"
title: "Typed operation selectors lack contextual resolution semantics"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "language"
  - "compiler"
components:
  - "type-system"
  - "name-resolution"
  - "call-resolution"
  - "modules"
  - "diagnostics"
related:
  issues:
    - "VIR-ISS-0015"
    - "VIRC-ISS-0063"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "typed-selectors"
  - "contextual-resolution"
  - "name-resolution"
  - "language-gap"
---

# VIR-ISS-0016 — Typed operation selectors lack contextual resolution semantics

## 1. Summary

Vir chưa implement typed operation selector. Quyết định ngôn ngữ được khóa
trong ISSUE này: một giá trị ngắn như `swap` được resolve từ expected parameter
type tại call site; nó không trở thành keyword toàn cục, implicit global
constant, hoặc overload discriminator.

Ví dụ một API có thể dùng typed selector:

```vir
image.resize(width, height, nearest)
```

Issue này độc lập với trailing default arguments (`VIR-ISS-0015`).
Vec từng là motivating consumer, nhưng canonical Vec API nay dùng method riêng
`swapRemove` và không còn phụ thuộc typed selectors.

## 2. Context

Tên `swap` đã có nghĩa bình thường trong chương trình (ví dụ method đổi hai
phần tử). Biến nó thành keyword toàn cục sẽ tạo collision và mở rộng grammar
không cần thiết. Selector phải có type identity, declaration rules, visibility,
và contextual lookup rõ ràng để cùng một spelling có thể tồn tại an toàn trong
các selector types khác nhau.

Selector value phải được khai báo tường minh trong một typed selector domain.
Compiler không được tự tạo selector chỉ vì gặp một bare identifier ở argument
position.

## 3. Expected Behavior

- `swap` trong vị trí argument được xét như selector candidate khi expected
  parameter type cho phép selector đó.
- `swap` không trở thành reserved/global keyword.
- Callee/function declaration phải được resolve trước để cung cấp expected type
  của parameter; resolver không suy type chỉ từ spelling `swap`.
- Selector có typed identity; spelling giống nhau ở các selector type không tự
  tạo ambiguity khi expected type là duy nhất.
- Ordinary lexical binding cùng spelling giữ ordinary identifier semantics và
  shadow contextual selector lookup; selector lookup chỉ là fallback khi không
  có ordinary binding phù hợp trong lexical scope.
- Khi không có expected type, không có matching selector, hoặc có nhiều type
  hợp lệ, compiler báo diagnostic ổn định thay vì đoán.
- Module visibility/import rules ngăn selector bị rò vào global namespace.
- Sau resolution, selector là typed value/constant bình thường trong IR; backend
  không nhận một magic identifier hoặc Vec-specific flag.

## 4. Actual Behavior

- Active specs chỉ có ordinary identifier/name lookup; không có contextual
  selector lookup từ expected parameter type.
- Compiler chưa có selector declaration/type representation.
- Bare `swap` hiện phải resolve như ordinary name hoặc fail unresolved.
- Không có collision, qualification, import, or ambiguity policy cho selector.

## 5. Reproduction

Target call (hiện chưa có contract):

```vir
image.resize(640, 480, nearest)
```

Compiler phải biết expected operation-selector type từ parameter của `resize`
trước khi resolve `nearest`; ordinary global identifier lookup là không đủ.

## 6. Evidence

- CONFIRMED: `swap` không phải Vir keyword trong active language/compiler keyword
  sets được audit.
- CONFIRMED: không tìm thấy typed/contextual operation-selector mechanism trong
  active specs hoặc current resolver.
- CONFIRMED: ordinary identifiers can share spellings with selector candidates,
  so global-keyword treatment would break normal namespaces.
- DECIDED: selector membership is explicit and typed; no selector is synthesized
  from an identifier spelling.
- NOT VERIFIED: final selector declaration/qualification syntax and physical
  representation.

## 7. Scope

### Affected

- selector declaration and typed identity;
- expected-type-directed name resolution;
- imports, visibility, qualification, and collision rules;
- type checker, HIR/MIR representation, diagnostics, and tooling;
- use in ordinary and default arguments.

### Not affected

- Creating a global `swap` keyword;
- general function overloading;
- default-argument omission/lowering, tracked by `VIR-ISS-0015`;
- the Vec removal API or algorithms.

## 8. Impact

Nếu thiếu typed selectors, APIs muốn dùng selector phải dùng qualified enum
variants, boolean/magic integer, hoặc method names riêng. Nếu selector spelling
bị reserve toàn cục, thay đổi còn ảnh hưởng mọi module và các API/biến hợp lệ
đang dùng spelling đó.

## 9. Preliminary Analysis

- Expected-type lookup keeps selector names local to their operation domain and
  avoids global keyword growth.
- Resolver must not use result-type guessing or silently select among multiple
  selector types.
- A qualified escape form is required for explicit disambiguation or when
  ordinary lexical shadowing applies; exact syntax requires a SPEC decision.
- Selector representation must state equality, storage/ABI, pattern matching,
  serialization, and FFI boundaries—or explicitly exclude them.

## 10. Normative Decision (locked 2026-10-09)

Typed operation selectors follow this resolution contract:

1. Resolve the callee and its parameter list.
2. Obtain the expected selector type for the argument position.
3. Perform ordinary lexical identifier lookup first. An ordinary binding keeps
   its normal meaning and must type-check normally.
4. If no ordinary binding resolves the bare identifier, look for an explicitly
   declared selector member with that spelling in the expected selector type.
5. Succeed only when exactly one visible member matches; otherwise emit an
   unresolved/ambiguous selector diagnostic.
6. Lower the result as a typed value. The spelling is not carried as backend
   magic and does not create a second function identity.

Locked exclusions:

- `swap`, `preserve`, and future selectors are not reserved words.
- A selector is not an automatically imported global constant.
- Compiler does not synthesize selector members from parameter/function names.
- Selector resolution does not add function overloading.
- No library receives a special-case resolver rule.

Issue chuyển `OPEN -> TRIAGED`: semantic direction đã chốt; declaration and
qualification syntax, SPEC revision, compiler implementation, and verification
remain pending work.

## 11. Acceptance Criteria

- [x] Chốt expected-parameter-type-directed resolution.
- [x] Chốt selector members phải được khai báo tường minh và có typed identity.
- [x] Loại trừ global keywords, implicit globals, overload resolution và
  Vec-specific compiler handling.
- [x] Chốt ordinary lexical bindings giữ nghĩa bình thường và shadow selector
  fallback lookup.
- [ ] Active English/Vietnamese specs define selector declaration, typed
  identity, values, and contextual lookup from an expected type.
- [ ] Specs explicitly state selectors are not global keywords and define how
  ordinary identifiers named `swap`/`preserve` continue to resolve.
- [ ] Visibility, import, qualification, same-spelling collisions, shadowing,
  and ambiguity diagnostics are deterministic.
- [ ] Behavior without an expected type and behavior across generic/type-variable
  parameters are specified.
- [ ] Runtime/ABI representation and permitted uses outside call arguments are
  defined or explicitly deferred.
- [ ] Compiler and self-host path implement positive/negative resolution tests,
  including collisions with fields, methods, locals, and imported names.

## 12. Related Papers

### Issues

- `VIR-ISS-0015` — trailing default arguments.
- `VIR-ISS-0011` — classification of keywords and language/library forms.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Locked contextual typed-selector resolution and moved OPEN → TRIAGED |
| 2026-10-09 | Opened for contextual `preserve`/`swap` operation selection in Vec |
| 2026-10-09 | Vec dependency withdrawn after choosing separate `remove` and `swapRemove`; issue remains an independent language feature |
