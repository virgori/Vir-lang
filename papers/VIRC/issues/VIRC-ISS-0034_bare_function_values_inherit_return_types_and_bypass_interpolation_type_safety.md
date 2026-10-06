---
id: "VIRC-ISS-0034"
type: "ISSUE"
domain: "VIRC"
title: "Bare function values inherit return types and bypass interpolation type safety"
status: "REJECTED"
severity: "S1"
priority: "P1"
created: "2026-10-04"
updated: "2026-10-04"
owners:
  - "compiler"
  - "type-system"
components:
  - "semantic-typecheck"
  - "symbol-table"
  - "string-interpolation"
  - "ast-to-mir"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "function-value"
  - "type-safety"
  - "interpolation"
  - "regression"
---

# VIRC-ISS-0034 — Bare function values inherit return types and bypass interpolation type safety

## 1. Summary

Issue này bị từ chối vì được lập từ nội dung tạm thời đã ghi nhầm vào file
reproducer của người dùng. Nội dung đúng là ca tail recursion bên trong
`arena:` và được theo dõi độc lập tại `VIRC-ISS-0035`.

## 2. Context

VIR-SPC-0017 §6.6 định nghĩa function là first-class typed value:
`let f = double` giữ giá trị hàm, còn `f()` mới là lời gọi. §12 giới hạn string
interpolation ở string, integer, bool và none.

Tại thời điểm triage đầu tiên, `/Users/gengyang/Desktop/Test/TCO.vri` chứa một
benchmark tensor ngoài ý muốn. Người dùng sau đó xác nhận file đã bị sửa nhầm
và cung cấp lại source chuẩn. Vì provenance của reproducer ban đầu không hợp
lệ cho yêu cầu này, fixture `TYPE-PRINT-FUNC-001` đã được gỡ khỏi regression
manifest.

## 3. Expected Behavior

- `bench_tensor_mult` không có ngoặc phải có function-value type, không phải
  return type `int`.
- Nội suy function value phải phát diagnostic type error `E3001` và không sinh
  artifact.
- Nếu ý định là chạy benchmark, source phải viết `bench_tensor_mult()`; kết quả
  vòng đếm khi đó là `100000`.

## 4. Actual Behavior

`virc 4.2.1` chấp nhận source, sinh executable và khi chạy in một số nguyên phụ
thuộc địa chỉ runtime (một lần tái hiện in `4330930824`) thay vì `100000` hoặc
diagnostic. Điều này làm function pointer/code address bị xử lý như integer.

## 5. Reproduction

Fixture canonical:
`tests/type_safety_contract/function_value_interpolation_tensor_benchmark_negative.vri`.

```text
python3 tools/gap_contract_runner.py \
  --manifest tests/type_safety_contract/manifest.tsv \
  --fixtures tests/type_safety_contract \
  --virc ./bin/virc --target macos-arm64 \
  --filter '^TYPE-PRINT-FUNC-001$'
```

Current result: `FAIL — Compiler unexpectedly generated an artifact for
negative test`.

## 6. Evidence

- `./bin/virc /Users/gengyang/Desktop/Test/TCO.vri -o /private/tmp/tco_user_421.out`:
  compile PASS, no diagnostics.
- Executable output contains `Kết quả vòng lặp: 4330930824` rather than
  `100000`; the exact address-like integer is not a stable oracle.
- Focused contract result: 0 PASS / 1 FAIL because an artifact was generated.
- `TypeKind.Func = 8` already exists in
  `compiler/src/semantic/types/table.vri`.
- `pass6WalkInterpExpr` correctly rejects every type except String, Int, Bool
  and None, but `pass6_infer_interp_type` reaches the function symbol through
  the inferred variable as `Int`.

## 7. Scope

### Affected

- Function identifiers used as values.
- Inferred variables initialized from bare function identifiers.
- Print/string interpolation type checking and AST-to-MIR stringify selection.

### Not affected / Unknown

- Ordinary calls with parentheses are not the failing form.
- Tail-call optimization is not exercised by the reproducer.
- Tensor `*` versus matrix-multiply `**` is independent because the observed
  incorrect output is the bare function value bound in `main`.

## 8. Impact

Đây là lỗi type-safety lõi: compiler chấp nhận một representation không được
phép nội suy, làm return type che mất function-value identity và có thể làm lộ
địa chỉ code dưới dạng số. Source có lỗi gọi hàm cũng thất bại âm thầm thay vì
nhận diagnostic có thể hành động.

## 9. Preliminary Analysis

- **CONFIRMED:** bare function identifier là function value theo VIR-SPC-0017,
  không phải implicit zero-argument call.
- **CONFIRMED:** Pass 6 phân loại interpolation child thành loại được chấp nhận;
  nếu không, `pass6WalkInterpExpr` đã phát `E3001`.
- **CONFIRMED:** TypeKind có `Func`, nhưng focused regression hiện vẫn sinh
  artifact.
- **OBSERVED:** runtime in một số nguyên address-like thay vì `100000`.
- **HYPOTHESIS:** symbol registration hoặc identifier inference gắn return
  `TypeKind.Int` trực tiếp lên function symbol; cần audit exact write path trước
  khi sửa.
- **NOT_VERIFIED:** ảnh hưởng tới function values đi qua parameter, collection,
  entity field hoặc return value ngoài interpolation.

## 10. Acceptance Criteria

- [x] Gỡ fixture và manifest row sinh từ file bị sửa nhầm.
- [x] Tái hiện source TCO + arena đã được người dùng xác nhận.
- [x] Theo dõi lỗi đúng bằng ISSUE và regression test riêng.

## 11. Related Papers

### Issues

- VIRC-ISS-0035 — source đúng và lỗi thực tế được theo dõi tại đây.

### Plans

- None.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-04 | Tái hiện user fixture, phân loại type-safety defect, thêm TYPE-PRINT-FUNC-001 và chuyển TRIAGED |
| 2026-10-04 | REJECTED sau khi người dùng xác nhận file đã bị sửa nhầm; gỡ fixture sai và chuyển ca đúng sang VIRC-ISS-0035 |
