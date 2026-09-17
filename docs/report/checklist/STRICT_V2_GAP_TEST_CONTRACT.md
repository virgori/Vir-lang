# Strict v2 gap test contract

## Mục tiêu

Bộ chuẩn nằm tại `tests/spec_gap_contract/`. Nó khóa hành vi cần đạt cho các
tính năng hiện chưa hoàn thiện/no-op, để implementation sau không tự hạ chuẩn
theo code đang có.

Manifest canonical:

```text
tests/spec_gap_contract/manifest.tsv
```

Hướng dẫn và quy tắc chống pass giả:

```text
tests/spec_gap_contract/README.md
```

## Gate bắt buộc cho mỗi feature

- Positive runtime test cho output/side effect observable.
- Compile-fail test cho semantic restriction.
- Structural oracle nếu runtime output có thể pass dù feature là no-op.
- Mutation test chứng minh bỏ semantics sẽ làm test fail.
- Chạy artifact thật trên từng target được công bố.

Numeric contract còn khóa riêng precedence/associativity, signed negative
semantics, IEEE-754 binary64 và cast `float ↔ int`, bao gồm runtime trap cho
NaN, infinity và out-of-range.

## Không được làm

- Không sửa expected output để giữ compiler hiện tại pass.
- Không thay runtime test bằng parser-only test.
- Không coi compile thành công là backend support.
- Không dùng raw internal layout làm language contract nếu spec không công khai
  layout đó.
- Không tự bịa executor API, gradient API hoặc `expose` build flag để đóng test
  đang được đánh dấu `blocked_contract`.

## Thứ tự bật gate

1. Precomp và generic.
2. FFI semantic negatives và bundle.
3. SIMD/swizzle.
4. Async/Port sau khi đóng executor selection contract.
5. Reactive/morph/expose sau khi có observation/backend contract.
6. Autodiff tổng quát sau khi có gradient observation contract.
7. Ma trận target và zero-overhead structural gates.

Suite này không thuộc release 3.2.0 và không liên quan JSON/XML.

Prompt giao việc implementation:

```text
docs/plan/STRICT_V2_GAP_FEATURES_IMPLEMENTATION_PROMPT.md
```
