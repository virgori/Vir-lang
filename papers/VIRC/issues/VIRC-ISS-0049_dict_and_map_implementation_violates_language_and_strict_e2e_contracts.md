---
id: "VIRC-ISS-0049"
type: "ISSUE"
domain: "VIRC"
title: "Dict and map implementation violates language and strict E2E contracts"
status: "OPEN"
severity: "S1"
priority: "P1"
created: "2026-10-07"
updated: "2026-10-07"
owners:
  - "compiler"
components:
  - "frontend"
  - "semantic-analysis"
  - "ast-to-mir"
  - "runtime-layout"
  - "regression-suite"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "dict"
  - "map"
  - "language-conformance"
  - "type-safety"
  - "codegen"
---

# VIRC-ISS-0049 — Dict and map implementation violates language and strict E2E contracts

## 1. Summary

`virc 2026.1` chỉ triển khai một tập con của hợp đồng `dict` và `map` trong
`VIR-SPC-0017`/`VIR-SPC-0018` §20. Typed empty dict bị nhận thành array,
`Hashable` và kiểu value của literal không được kiểm tra đầy đủ, các thao tác
existence/delete/iteration/keys/values thiếu hoặc cho kết quả sai, còn runtime
dict quét tuyến tính và dừng tiến trình khi vượt 256 phần tử. `map` không hỗ trợ
index binder hay range và có thể âm thầm bỏ statement hoặc nhánh `else`, tạo
kết quả native sai dù compilation thành công.

Issue này ghi nhận một lỗi conformance/correctness thống nhất thay vì tách từng
triệu chứng theo frontend, semantic và backend. Mục tiêu là khôi phục toàn bộ
hợp đồng §20 xuyên suốt lexer/parser, type system, ownership, MIR/LIR, runtime
layout và regression suite.

## 2. Context

Active language specifications quy định:

- literal `[key: value, ...]`, annotation `dict of (K, V)` và typed empty dict
  `var m: dict of (K, V) = []`;
- `K: Hashable`, hash `u64`, equality theo giá trị hoặc
  `equals`/`operator ==` cho entity;
- open addressing, linear probing, resize ở load factor 75% và bucket array
  cấp phát trong arena;
- set/get, `m ? key`, `del m[key]`, `len`, iteration cặp key/value,
  `keys(m)` và `values(m)`;
- `map` trên mọi iterable được liệt kê bởi §20, index binder `map i, v in`,
  filter bằng conditional `out` và nested map.

`VIRC-SPC-0007` §4 hiện gọi layout `[len, capacity, key/value pairs...]` là
implementation ABI, trong khi `VIR-SPC-0017`/`0018` §20.1.5 yêu cầu bucketed
open addressing. Đây là xung đột normative đã được CONFIRMED. Việc xử lý issue
phải quyết định và cập nhật hợp đồng compiler để không giữ hai mô hình runtime
mâu thuẫn; không được dùng layout cũ để hạ thấp semantics của language SPEC.

## 3. Expected Behavior

- Mọi `dict of (K, V)` chỉ hợp lệ khi `K: Hashable`; mọi key/value trong literal
  và mọi assignment phải tương thích với `K`/`V` đã suy luận hoặc khai báo.
- Typed empty dict được nhận diện và hoạt động như dict ở mọi pass.
- Lookup, update, insert, existence, delete, length và iteration giữ đúng
  semantics qua collision, resize, duplicate key, arena escape, move và mọi mức
  tối ưu hóa.
- Runtime không có giới hạn 256 phần tử tùy ý và không gọi `exit(70)` thay cho
  một grow hoặc diagnostic/runtime error đã được đặc tả.
- Hash/equality của primitive và entity tuân thủ §20.1.4; string so theo nội
  dung, không theo pointer identity.
- `map` hỗ trợ array, range và `keys`/`values` của dict, có binder một biến hoặc
  index/value, xử lý đầy đủ statement-list/control flow và suy luận nhất quán
  kiểu mảng kết quả.
- Source không được compile thành kết quả sai. Cấu trúc chưa được hỗ trợ phải
  bị từ chối bằng diagnostic trước code generation.

## 4. Actual Behavior

- Parser tạo `ArrayLiteral` cho `[]`; semantic index checker chỉ nhận type string
  đúng bằng `dict`, nên `dict of (string, int) = []` bị báo E3015 như một array
  hoặc tensor index.
- Dict literal walker chỉ so kiểu các key sau với key đầu. Literal value không
  đồng nhất và array key không `Hashable` vẫn compile.
- Dict lowering reserve đúng 256 entry, lookup/store quét tuần tự từ entry 0,
  không gọi hash, tăng logical capacity thẳng lên 256 rồi gọi process exit 70
  khi hết chỗ.
- `m ? "Alice"` được parse thành postfix existence chỉ chứa `m`; key không đi
  vào AST. `MIR_INTR_EXIST` bị LIR coi như no-op và kết quả quan sát là một số
  giống pointer thay vì `bool`.
- `del` có token được khai báo nhưng không có lexer/parser/semantic path hoạt
  động; source được chẩn đoán như identifier chưa định nghĩa. `keys` và `values`
  không có builtin/function resolution; `for k, v in dict` không parse được.
- Map parser chỉ đọc một binder. Source range dừng tại `..`. AST-to-MIR luôn
  giả định source có array layout, block chỉ xử lý child đầu tiên và `IfStmt`
  chỉ lower nhánh `then`.

## 5. Reproduction

Các probe tối thiểu đã được chạy với `./bin/virc -O0` và `-O3` tại revision ghi
trong Evidence.

Typed empty dict:

```vir
func main:
    var m: dict of (string, int) = []
    m["Alice"] = 30
    print m["Alice"]
end.
```

Observed: compilation thất bại với E3015 `Tensor index must be integer`.

Type soundness:

```vir
func main:
    var mixed = [1: 10, 2: "wrong"]
    var nonhashable = [[1, 2]: 10]
    print len(mixed)
    print len(nonhashable)
end.
```

Observed: compile/run thành công.

Capacity:

```vir
func main:
    var values = [0: 0]
    var i = 1
    when i < 260 loop
        values[i] = i
        i = i + 1
    end
    print len(values)
end.
```

Observed: compile thành công; executable dừng với exit code 70 ở cả `-O0` và
`-O3`, không in diagnostic.

Existence và map control flow:

```vir
func main:
    var m = ["Alice": 30]
    print m ? "Alice"

    var src = [1, 2, 3]
    var result = map x in src:
        var doubled = x * 2
        out doubled
    end
    print result.len
end.
```

Observed: existence in một integer pointer-like; `map` compile nhưng trả length
`0`. Một probe `if/else` khác chỉ emit nhánh `then`. `map i, value in src` và
`map x in 0..3` đều bị parser từ chối.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0017:2753-2936` và
  `VIR-SPC-0018:2728-2910` định nghĩa đầy đủ §20 Dict & Map, gồm Hashable,
  open addressing, resize 75%, typed empty dict, operations, iteration và map
  iterable/index/filter/nesting.
- CONFIRMED: `VIRC-SPC-0007:234-260` cố định contiguous pair layout như
  implementation ABI nhưng vẫn yêu cầu grow hoặc documented capacity error;
  process exit 70 hiện tại không thỏa yêu cầu đó.
- CONFIRMED: `compiler/src/frontend/parser/expr/primary.vri:198-243` chỉ nhận
  một map binder; `:625-659` chỉ phân biệt dict khi literal có dấu `:`.
- CONFIRMED: `compiler/src/frontend/parser/expr/unary.vri:255-262` biểu diễn
  `?` như postfix một operand; không có active `TokType.Del` consumer.
- CONFIRMED: `compiler/src/semantic/typecheck/walk_other.vri:248-265` chỉ kiểm
  tra key type của dict literal; `:456-473` không xác minh iterable hoặc result
  type của map.
- CONFIRMED: `compiler/src/semantic/typecheck/walk_index.vri:32-35,63-66` chỉ
  nhận tracked type string đúng bằng `dict`; key/value types được suy ra từ
  non-empty DictLiteral trong `compat_state.vri:348-390`.
- CONFIRMED: `compiler/src/lower/ast_to_mir/expr.vri:645-821` dùng equality +
  linear scan, reserve/cap 256 và exit 70; `:869-965` chỉ xử lý block child đầu,
  bỏ `else` và dùng array indexing cho source map.
- OBSERVED ngày 2026-10-07 tại HEAD `d7dbdf1a`, binary `virc 2026.1`, SHA-256
  `2b2d2d23b08dbfce765734f92ec886f69b70c72b62cb104bc68cd0cf7a431ad7`:
  các probe trên tái hiện giống nhau ở `-O0` và `-O3` trên macOS arm64.
- OBSERVED: `./run_tests.sh 20` báo 16/16 PASS, nhưng
  `tests/test_adv_093_map.vri` tự viết hàm `map_arr` và không dùng map expression.
  Focused `TYPE-DICT-001..003` pass nhưng không cover heterogeneous literal,
  non-Hashable key, typed empty dict hoặc capacity >256.
- OBSERVED: move-after-use contract trả E5001 đúng và arena dict escape in `42`
  ở `-O0/-O3`; chưa có bằng chứng lỗi trong borrow ownership cơ bản.
- NOT_VERIFIED: behavior của các probe lỗi trên Linux x86-64, Linux arm64,
  RISC-V và Wasm; source paths bị ảnh hưởng là shared nhưng native execution mới
  chỉ được chạy trên macOS arm64.

## 7. Scope

### Affected

- lexer/parser cho `del`, dict iteration và map grammar;
- type resolution/inference/checking của `dict of (K, V)`, `Hashable` và map;
- AST-to-MIR, MIR/LIR lowering, target codegen và runtime representation;
- arena allocation/promotion và move semantics khi representation thay đổi;
- group 20, type-safety, memory-contract, target/backend và bootstrap tests;
- `VIRC-SPC-0007` §4 implementation contract nếu layout hash-table được chuẩn hóa.

### Not affected / Unknown

- Array indexing và ordinary postfix optional/existence semantics ngoài dict
  không được phép thay đổi ngầm để vá `m ? key`.
- Existing correct use-after-move và owned arena escape behavior phải được giữ.
- Issue không thay đổi source-language §20; nếu implementation cho thấy SPEC
  cần đổi, việc đó cần một VIR SPEC revision riêng được phê duyệt.
- NOT_VERIFIED: ABI compatibility requirement cho serialized/FFI-exposed dict;
  không có bằng chứng hiện tại rằng internal dict layout là public stable ABI.

## 8. Impact

Đây là core correctness failure. Chương trình hợp lệ theo SPEC có thể không
compile, dừng tiến trình ở kích thước bình thường, nhận pointer thay vì boolean,
hoặc compile thành output sai mà không có warning. Việc bỏ kiểm tra `V` và
`Hashable` cũng phá type-safety boundary trước backend. Group 20 hiện pass nên
release gate không phát hiện các failure mode này.

Severity `S1` vì lỗi trải qua semantics và native execution, gồm silent
miscompile và process termination. Priority `P1` vì cần sửa trước khi quảng bá
§20 là hoàn chỉnh hoặc dùng dict/map cho compiler/runtime production workloads.

## 9. Preliminary Analysis

- CONFIRMED: frontend, semantic và lowering đang dùng ba cách nhận diện dict
  khác nhau: syntax có `:`, type string đúng bằng `dict`, và tracked variable
  side table. Typed empty dict rơi qua khe giữa ba cơ chế.
- CONFIRMED: current runtime storage là growable-looking contiguous vector với
  backing allocation cố định, không phải hash table được §20.1.5 mô tả.
- CONFIRMED: map parser/typechecker chấp nhận một AST rộng hơn phần lowering
  thực thi; thiếu fail-closed validation tạo silent miscompile.
- HYPOTHESIS: một canonical typed container descriptor dùng chung từ semantic
  tới MIR có thể loại bỏ string/side-table detection, nhưng thiết kế cụ thể
  thuộc PLAN chứ chưa phải kết luận của ISSUE.
- HYPOTHESIS: dict operations nên đi qua một runtime/container abstraction
  chung thay vì emit vòng linear scan trong AST lowering; cần benchmark và ABI
  analysis trước khi chọn representation.
- NOT_VERIFIED: migration cost cho existing generated bundle, external FFI và
  cross-target runtime stubs.

## 10. Acceptance Criteria

- [ ] Resolve the normative conflict between `VIR-SPC-0017`/`0018` §20.1.5 and
  `VIRC-SPC-0007` §4; approved paper changes leave exactly one canonical dict
  representation/behavior contract.
- [ ] Typed empty `dict of (K, V) = []` compiles, supports all dict operations
  and retains `K`/`V` through inference, assignment, function calls and imports.
- [ ] Semantic analysis rejects every non-`Hashable` key and heterogeneous or
  incompatible value at compile time with stable, source-located diagnostics.
- [ ] Primitive and entity hash/equality behavior conforms to §20.1.4,
  including collision tests proving equal hash alone does not imply equal key.
- [ ] Dict uses the approved arena-backed hash-table design with linear probing
  and 75% resize, or an explicitly revised active SPEC; there is no hard-coded
  256-entry termination path.
- [ ] Set/get/update/duplicate-key/len/existence/delete semantics pass for empty,
  singleton, collision-heavy, deleted-slot, resize and large dictionaries.
- [ ] `for k, v in dict`, `keys(dict)` and `values(dict)` compile and run with
  documented unordered iteration behavior.
- [ ] `map` supports one binder, index/value binders, array, range,
  `keys`/`values`, filter and nested map exactly as §20.2 specifies.
- [ ] Map lowering executes every permitted body statement and every reachable
  control-flow branch; unsupported bodies fail before MIR instead of silently
  emitting incomplete output.
- [ ] Result element type is inferred from all reachable `out` expressions and
  incompatible emissions produce a compile-time diagnostic.
- [ ] Ownership regressions cover move-after-use, borrow conflicts, arena
  escape/promotion, resize and deletion at `-O0` through `-O3`.
- [ ] Group 20 replaces false map coverage with direct language `map`
  expressions and adds negative contracts for every formerly accepted invalid
  case; `test_adv_093_map.vri` is not counted as map-expression coverage.
- [ ] Focused and full suites pass on every supported native target affected by
  shared lowering, with Linux x86-64 and Linux arm64 evidence recorded rather
  than inferred from macOS arm64.
- [ ] Generated compiler source is synchronized from canonical sources,
  self-host stage 2 equals stage 3, and module dependency validation passes.
- [ ] Completion follows `compiler/VERSIONING.md` and bumps the compiler
  calendar patch exactly once for this issue.
- [ ] An accepted REPORT maps every criterion to commands/results and records
  any unsupported backend or ABI limitation; no criterion is closed solely by
  compilation success.

## 11. Related Papers

### Issues

- None.

### Plans

- None allocated.

### Reports

- None allocated.

### Specifications

- `VIR-SPC-0017` §20 — Dict & Map (English).
- `VIR-SPC-0018` §20 — Dict & Map (Vietnamese canonical language specification).
- `VIRC-SPC-0007` §4 — Compiler Strict E2E Contract.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-07 | Opened from the virc dict/map audit with reproducible frontend, type-safety, lowering, capacity and regression-coverage evidence |
