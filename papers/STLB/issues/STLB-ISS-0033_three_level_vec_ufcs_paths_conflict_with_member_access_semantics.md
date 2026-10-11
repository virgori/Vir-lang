---
id: "STLB-ISS-0033"
type: "ISSUE"
domain: "STLB"
title: "Three-level Vec UFCS paths conflict with member-access semantics"
status: "CLOSED"
severity: "S1"
priority: "P0"
created: "2026-10-09"
updated: "2026-10-11"
owners:
  - "stdlib"
  - "language"
  - "compiler"
components:
  - "collections"
  - "vec"
  - "ufcs"
  - "member-resolution"
  - "public-api"
related:
  issues:
    - "STLB-ISS-0032"
  plans:
    - "STLB-PLN-0003"
  reports:
    - "STLB-RPT-0003"
supersedes: null
superseded_by: null
tags:
  - "stdlib"
  - "vec"
  - "three-level-ufcs"
  - "public-api"
  - "resolved-by-api-decision"
---

# STLB-ISS-0033 — Three-level Vec UFCS paths conflict with member-access semantics

## 1. Summary

Đã bỏ hai canonical path ba cấp `self.get.try` và `self.swap.remove`. Vec dùng
flat one-level UFCS:

```vir
values.try(index)
values.remove(index)
values.swapRemove(index)
```

Vì vậy Vir không cần method groups, overload, default arguments, typed
operation selectors, hoặc một ngoại lệ compiler cho Vec.

## 2. Context

Theo active member rules, `x.foo` không có parentheses là field access. Do đó
`v.get.try(i)` phải truy cập member `try` của field/value `v.get`, không thể tự
động mang nghĩa một callable name ba cấp. Tương tự với `v.swap.remove(i)`.

## 3. Resolution

- `vec.tryGet` đổi canonical spelling thành `self.try`.
- `vec.swapRemove` đổi canonical spelling thành method riêng
  `self.swapRemove(i)`.
- `self.remove(i)` luôn giữ thứ tự; `self.swapRemove(i)` luôn dùng thuật toán
  hoán đổi phần tử cuối và không giữ thứ tự.
- Không mở rộng member-access semantics và không thêm method group ba cấp.

## 4. Expected Behavior

Canonical Vec names phải có nghĩa duy nhất dưới member/UFCS rules hiện hành,
không cần compiler special-case. Safe lookup dùng `self.try`; unordered removal
dùng method riêng `self.swapRemove`.

## 5. Actual Behavior

- `v.get` và `v.swap` được resolve như field access ở giữa dotted expression.
- Vec không có field object tương ứng để cung cấp `try` hoặc `remove` member.
- Flat implementation symbols `vec_try_get` và `vec_swap_remove` đã cung cấp
  behavior nhưng không thể hợp thức hóa canonical spelling ba cấp.

## 6. Reproduction

Hai spelling cũ minh họa xung đột:

```vir
values.get.try(0)
values.swap.remove(0)
```

Theo `VIR-SPC-0017` section 11.4, `values.get` và `values.swap` ở đây là field
access. Canonical replacements không có intermediate field access:

```vir
values.try(0)
values.swapRemove(0)
```

## 7. Evidence

- CONFIRMED: `VIR-SPC-0017` section 11.4 quy định `x.foo` là field access và
  `x.foo(args)` mới đi vào method/callable-field/free-UFCS resolution.
- CONFIRMED: result chaining `x.foo().bar()` không định nghĩa hierarchical
  callable identity cho `x.foo.bar()`.
- CONFIRMED: `stdlib/registry/vec.md` hiện chỉ còn flat `self.try`,
  `self.remove`, và `self.swapRemove`.
- CONFIRMED: compatibility source symbols vẫn được giữ trong migration window.

## 8. Scope

### Resolved here

- canonical naming của Vec safe lookup và unordered removal;
- loại bỏ nhu cầu scoped method groups cho hai API này;
- compatibility mapping từ stable registry IDs cũ.

### Tracked elsewhere

- type-receiver constructors và generic UFCS: `STLB-ISS-0032`;
- implementation correctness của typed Vec: `STLB-ISS-0007`.

## 9. Impact

Canonical Vec API không còn dạy syntax xung đột với field access và không còn
phụ thuộc hai language features chỉ để biểu diễn hai thuật toán xóa khác nhau.

## 10. Preliminary Analysis

- Đây là naming conflict, không phải thiếu alias implementation.
- Flat operations giữ nguyên ordinary member-access semantics.
- Default arguments và typed selectors vẫn là language features độc lập trong
  `VIR-ISS-0015` và `VIR-ISS-0016`, nhưng Vec không còn là consumer của chúng.

## 11. Acceptance Criteria

- [x] Chọn one-level UFCS thay cho scoped method groups.
- [x] Đổi `self.get.try` thành `self.try` trong authoritative Vec registry.
- [x] Đổi `self.swap.remove` thành method riêng `self.swapRemove(i)`.
- [x] Giữ compatibility identities/symbols cho migration.
- [x] Không thay đổi ordinary field, callable-field, method, hoặc free-UFCS
  resolution.
- [x] External Vec consumer compile qua canonical spelling sau khi các compiler
  generic-UFCS gaps liên quan được giải quyết; tiêu chí này thuộc
  `STLB-ISS-0032` và không reopen quyết định naming ba cấp.

## 12. Related Papers

### Issues

- `STLB-ISS-0032` — Vec constructors and generic receiver UFCS.

### Plans

- None yet.

### Reports

- None yet.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-09 | Opened by splitting three-level UFCS/member semantics from STLB-ISS-0032 |
| 2026-10-09 | Resolved by selecting flat `try` and one selector-driven `remove` API |
| 2026-10-09 | Revised removal API to separate `remove` and `swapRemove`; withdrew Vec dependency on default arguments and typed selectors |
| 2026-10-11 | Linked STLB-PLN-0003 |
| 2026-10-11 | Linked STLB-RPT-0003 |
| 2026-10-11 | Closed after Vec source check, Group 3 external-consumer fixtures, Group 11 UFCS regressions and accepted STLB-RPT-0003 confirmed all criteria |
