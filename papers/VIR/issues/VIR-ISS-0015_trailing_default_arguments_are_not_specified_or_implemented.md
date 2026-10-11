---
id: "VIR-ISS-0015"
type: "ISSUE"
domain: "VIR"
title: "Trailing default arguments are not specified or implemented"
status: "TRIAGED"
severity: "S2"
priority: "P1"
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "language"
  - "compiler"
components:
  - "functions"
  - "parser"
  - "type-checker"
  - "call-resolution"
  - "lowering"
related:
  issues:
    - "VIR-ISS-0016"
    - "VIRC-ISS-0062"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "default-arguments"
  - "functions"
  - "ufcs"
  - "language-gap"
---

# VIR-ISS-0015 — Trailing default arguments are not specified or implemented

## 1. Summary

Vir chưa có compiler support cho tham số cuối có default argument. Quyết định
ngôn ngữ được khóa trong ISSUE này: một parameter có default argument **nếu và
chỉ nếu** declaration của nó chứa explicit default expression `= expression`.
Compiler không được suy ra default argument từ type của parameter.

Ví dụ tổng quát:

```vir
func connect(host: string, port: int = 8080):
    # ...
end.

connect("localhost")
```

Đây là default argument, không phải default value của type và không phải
function overloading. Compiler phải điền đối số bị lược bỏ từ declaration đã
resolve trước khi hạ call.

## 2. Context

Compiler hiện lưu một function entry/parameter count theo tên và không có
grammar, typing hay lowering rule cho default value. Vec từng là motivating
consumer, nhưng canonical Vec API nay tách `remove` và `swapRemove`, nên không
còn phụ thuộc feature này.

Hai khái niệm độc lập:

- **Default argument:** expression do người lập trình ghi trong function
  declaration, ví dụ `port: int = 8080`.
- **Default value của type:** giá trị mà ngôn ngữ tự tạo khi thiếu initializer.

ISSUE này chỉ chấp nhận khái niệm thứ nhất. Nó không định nghĩa `int -> 0`,
`bool -> false`, `string -> ""`, pointer -> null/`none`, zero-filled entity,
hoặc bất kỳ implicit type default nào.

## 3. Expected Behavior

- Chỉ các tham số cuối liên tiếp mới được phép có default argument.
- Parameter không có explicit `= expression` luôn là bắt buộc, bất kể type.
- Một function vẫn có duy nhất một identity và một full parameter list.
- Compiler resolve declaration trước, đọc default expression đã lưu cùng
  parameter, kiểm tra expression tương thích với parameter type, rồi hạ call
  thiếu trailing arguments thành full call.
- Explicit argument tại call site luôn thay thế default expression tương ứng.
- Thiếu một required argument là compile-time error; compiler không được tổng
  hợp giá trị từ type để làm call hợp lệ.
- Ordinary calls và UFCS calls dùng cùng quy tắc; receiver không làm thay đổi vị
  trí các default parameter khai báo.
- Tính năng này không kích hoạt overload sets hoặc overload resolution.

Ví dụ lowering mục tiêu:

```vir
func example(a: int, b: int = 10):
    # ...
end.

example(5)      # equivalent full call: example(5, 10)
example(5, 20)  # explicit b overrides the declared default
example()       # error: required argument a is missing
```

## 4. Actual Behavior

- Active language specs không định nghĩa declaration syntax hoặc call semantics
  cho default arguments.
- Parser/type checker không ghi nhận default expression trên parameter.
- Arity checking yêu cầu số argument cố định của function đã resolve.
- Khai báo hai function cùng tên nhưng khác arity không cung cấp overload hợp
  lệ; một declaration che/lấn declaration còn lại trong current symbol model.

## 5. Reproduction

Target syntax (hiện chưa hợp lệ):

```vir
func connect(host: string, port: int = 8080):
    # ...
end.

connect("localhost")
```

## 6. Evidence

- CONFIRMED: không tìm thấy normative default-argument rule trong active Vir
  language specs.
- CONFIRMED: current compiler rejects the one-argument call when two same-name
  declarations with different arity are used as a substitute.
- CONFIRMED: Vec no longer depends on this feature; its canonical API has
  separate `remove` and `swapRemove` methods.
- DECIDED: no implicit default value is synthesized from a parameter type and
  no `Default` trait is introduced by this feature.
- NOT VERIFIED: default-expression lexical scope/evaluation details and final
  ABI representation in the implementation.

## 7. Scope

### Affected

- function/method parameter grammar and AST representation;
- declaration and call type checking;
- UFCS argument normalization;
- HIR/MIR lowering and diagnostics;
- ownership/effect rules for default expressions;
- function values and public ABI metadata where arity is observable.

### Not affected

- General function overloading;
- typed operation-selector lookup, tracked separately by `VIR-ISS-0016`;
- Vec removal API or algorithms.

## 8. Impact

Không có contract này, callers phải lặp lại các giá trị mặc định ở mọi call
site hoặc thư viện phải tạo wrapper riêng. Thêm overload để né vấn đề sẽ mở
rộng đáng kể ambiguity/type-resolution scope mà feature không yêu cầu.

## 9. Preliminary Analysis

- Restrict defaults to trailing parameters keeps arity normalization local and
  diagnostics deterministic.
- Default expressions need an explicit evaluation-time, name-resolution,
  ownership, side-effect, and error-flow contract in the normative SPEC. Những
  chi tiết đó không được dùng để mở lại quyết định “explicit expression only”.
- Lowering should produce a full call before backend ABI selection so omitted
  arguments do not create a second symbol.

## 10. Normative Decision (locked 2026-10-09)

```text
A parameter has a default argument if and only if its declaration contains an
explicit default expression.

The compiler must not synthesize default arguments from the parameter's type.
```

Hệ quả bắt buộc:

- `= expression` thuộc declaration và được lưu trên parameter AST/HIR.
- Expression phải type-check với declared parameter type.
- Omitted arguments được materialize từ resolved declaration.
- Không có `= expression` thì parameter là required.
- Không có implicit initialization policy cho primitive, pointer, string,
  entity, collection, hoặc generic type phát sinh từ feature này.
- Không yêu cầu hay ngầm tạo cơ chế `Default` trait.
- General function overloading nằm ngoài phạm vi.

Issue chuyển `OPEN -> TRIAGED`: semantic direction đã chốt; SPEC revision,
compiler implementation và verification vẫn là work chưa hoàn thành.

## 11. Acceptance Criteria

- [x] Chốt explicit declaration expression là nguồn duy nhất của default
  argument.
- [x] Loại trừ type-derived defaults, implicit zero/null initialization và
  `Default` trait khỏi feature này.
- [x] Chốt trailing-only parameters và một callable identity, không overload.
- [ ] Active English/Vietnamese specs define declaration grammar for trailing
  default parameters and reject a required parameter after a defaulted one.
- [ ] Specs define resolution scope, type checking, evaluation order/time,
  ownership, side effects, and error propagation for default expressions.
- [ ] Ordinary calls, entity methods, callable fields, and free-function UFCS
  share one deterministic omitted-argument rule.
- [ ] Function identity, function values, ABI arity, and diagnostics are defined
  without introducing general overload resolution.
- [ ] Parser, AST/HIR/MIR, self-hosted compiler, and bootstrap path implement the
  approved contract.
- [ ] Positive/negative tests cover zero, one, and multiple trailing defaults;
  illegal non-trailing defaults; type mismatch; ownership/effect failures; and
  UFCS receiver handling.

## 12. Related Papers

### Issues

- `VIR-ISS-0016` — contextual typed operation selectors.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Locked explicit-declaration-only defaults; rejected type-derived defaults and moved OPEN → TRIAGED |
| 2026-10-09 | Opened for Vec `remove(index, operation = preserve)` without overloads |
| 2026-10-09 | Vec dependency withdrawn after choosing separate `remove` and `swapRemove`; issue remains as an independent language feature |
