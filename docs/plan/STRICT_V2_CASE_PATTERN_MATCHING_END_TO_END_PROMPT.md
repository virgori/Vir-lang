# Prompt nghiêm ngặt: hoàn thiện `case` và pattern matching Vir v2.0 end-to-end

## 1. Vai trò và mục tiêu

Bạn là compiler, runtime và test engineer của Vir. Hãy đưa biểu thức `case`
theo Vir Spec v2.0 §8 và §21 vào trạng thái production-grade trên toàn pipeline
compiler đang active.

Contract cú pháp bắt buộc:

```text
case-expression :=
    "case" expression
    case-arm+
    ["else" statement-list]
    "end"

case-arm := pattern ":" statement-list
statement-list := statement (separator statement)*
separator := NEWLINE | ";"
```

Dạng chuẩn:

```vir
case value
    Option.Some(x): print(x)
    Option.None: print(0)
    else print(-1)
end
```

Không được coi lexer/parser nhận token, AST có `CaseExpr`, một happy path in
đúng output, hay backend sinh binary là bằng chứng hoàn thành. Phải chứng minh
đúng syntax, semantic, control flow, payload binding, diagnostics và runtime.

## 2. Nguồn sự thật

Theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md` §8.3–§8.6 và §21.
2. `docs/vir_language_spec_v2.0_en.md` các mục tương ứng.
3. `docs/ai-spec/vir-lang/references/control-flow.md`, `syntax.md`, `types.md`.
4. Pipeline active dưới `stdlib/vir/compiler/` và test runner `run_tests.sh`.

Nếu implementation hoặc fixture cũ mâu thuẫn spec, sửa implementation/fixture;
không sửa spec để hợp thức hóa cú pháp legacy. Cụ thể, các dạng sau sai:

```vir
case x:                 # sai: không có ':' sau expression
    case 1: foo()       # sai: không lặp keyword case trước arm
    2 foo()             # sai: thiếu ':' sau pattern
    else: bar()         # sai: else là continuation, không có ':'
end
```

`case` là control block và đóng bằng `end`, không dùng `end.`.

## 3. Baseline bắt buộc

Trước khi sửa:

1. Ghi HEAD và SHA-256 của compiler dùng để chạy baseline.
2. Chạy `./run_tests.sh 21` bằng `bin/virc` hiện tại.
3. Tạo repro riêng cho từng syntax sai ở §2; ghi command, stdout, stderr và
   exit code. Compile thành công đối với bất kỳ repro sai nào là bug.
4. Chạy các tagged-union tests ở `tests/strict_v2/` để phân biệt parser bug với
   semantic/lowering bug.
5. Không dùng kết quả hoặc report cũ thay cho bằng chứng trên HEAD.

## 4. Parser và grammar

### 4.1. Biên của expression và arm

- Sau `case`, parse đúng một expression và kết thúc nó tại separator hợp lệ.
- Không nhận `:` sau case expression.
- Phải có ít nhất một `case-arm`; `else` đứng một mình không thỏa grammar.
- Mỗi arm bắt buộc có `pattern :` và ít nhất một statement.
- Newline ngay sau `:` chỉ là formatting; parser phải tiếp tục tìm statement
  đầu tiên và reject nếu gặp arm kế, `else`, `end` hoặc EOF.
- `else` tối đa một lần, phải đứng sau mọi pattern arm, không có `:`, và body
  không rỗng.
- `end.` không được parser recovery thành `end` hợp lệ cho control block.

### 4.2. Ranh giới arm

Không dùng indentation. Arm mới chỉ bắt đầu ở đầu logical statement khi token
sequence khớp pattern grammar rồi đến `:`, hoặc gặp `else`.

Parser không được coi mọi arbitrary `expr:` là arm. Đặc biệt cần kiểm tra:

- call expression, assignment, typed construct/map/label tương lai trong body;
- dấu `:` nằm trong nested construct;
- literal hoặc identifier xuất hiện giữa body mà không có `:`;
- `;` phân tách statements trong cùng arm và phân tách hai arms cùng dòng.

Nếu parser chưa đủ symbol information để phân biệt unqualified variant với
identifier-shaped construct, AST phải giữ candidate rõ ràng và semantic phải
resolve dứt điểm; không được đoán theo indentation hoặc tên viết hoa.

### 4.3. Pattern hợp lệ

Tối thiểu hỗ trợ đúng contract §21.2:

- literal số, chuỗi và bool;
- qualified variant `Enum.Variant`;
- qualified payload variant `Enum.Variant(x)`;
- unqualified unique variant `Variant` / `Variant(x)`;
- wildcard `_` nếu được bật trong Spec v2.0.

Không mở rộng pattern thành arbitrary expression. Reject có diagnostic cho:

- operator expression như `1 + 1:`;
- call tùy ý như `foo():` nếu `foo` không resolve thành variant;
- malformed qualification hoặc payload delimiters;
- nested payload pattern chưa được spec hỗ trợ;
- binder expression thay vì binder identifier.

## 5. AST và source locations

- `CaseExpr` phải giữ target expression, ordered arms và optional default arm.
- Mỗi arm giữ pattern, binder list, body block và source span độc lập.
- Không mã hóa `else` thành wildcard giả; default arm phải phân biệt được để
  exhaustiveness/unreachable analysis chính xác.
- Không dùng magic `int_val` nếu representation typed/enum rõ ràng đã tồn tại;
  nếu chưa thể migration ngay, document invariant và thêm assertions.
- Source line/span của lỗi phải trỏ vào `case`, pattern, binder, `:`, hoặc
  `else` tương ứng, không trỏ vào EOF do recovery.
- Parser recovery không được tạo partial AST rồi cho semantic/codegen tiếp tục
  như chương trình hợp lệ.

## 6. Semantic pattern matching

### 6.1. Target và compatibility

- Resolve type target trước khi resolve patterns.
- Literal pattern phải tương thích type target; không silently cast string,
  bool, integer, float hoặc enum tag không hợp lệ.
- Qualified variant phải thuộc đúng enum của target.
- Unqualified variant chỉ hợp lệ khi duy nhất trong scope và tương thích target.
- Unknown enum/variant hoặc wrong enum qualifier phải fail compile.

### 6.2. Payload binders

- Arity binder phải đúng payload arity của variant.
- Binder type được suy diễn từ field payload tương ứng.
- Binder scope chỉ tồn tại trong body arm đó.
- Không rò binder sang arm kế, `else`, sau `end`, nested function hay module.
- Duplicate binder trong cùng pattern phải fail.
- Wildcard binder `_` không tạo symbol và có thể lặp nếu spec cho phép.
- Binding aggregate/string/entity phải giữ đúng ownership/borrow/lifetime.

### 6.3. Coverage diagnostics

- Phát hiện duplicate literal/variant arm.
- Phát hiện arm sau wildcard hoặc arm đã phủ toàn miền là unreachable.
- Tagged union không có default phải exhaustive.
- `else` làm coverage hoàn chỉnh nhưng không che duplicate/unreachable arms
  trước nó.
- Diagnostic codes §8.6 (`E3032`–`E3043`) phải ổn định, đúng source line và
  không phụ thuộc thứ tự khai báo.
- So sánh trực tiếp payload enum bằng `==`/`!=` vẫn bị từ chối theo `E3043`;
  không nới luật này để né pattern lowering.

## 7. Lowering, CFG và codegen

- Target expression được evaluate đúng một lần, trước mọi pattern test.
- Các arm được xét theo thứ tự source; chỉ body arm khớp được chạy.
- Binder payload chỉ được load sau khi tag match.
- Mỗi arm kết thúc phải branch đúng tới merge/return/break path; không fall
  through sang arm tiếp theo.
- `out`, `break`, `skip`, nested `case`, nested `if` và loop trong body phải giữ
  semantics control-flow hiện có.
- Phi/merge values phải đúng type; arm terminated không tạo predecessor giả.
- Không hard-code enum tag, binder offset, arm count hay literal test trong
  backend. Layout/tag metadata phải đến từ semantic/MIR.
- Mọi backend public phải nhận cùng MIR semantics; không vá riêng ARM64.

## 8. Test suite bắt buộc

### 8.1. Positive syntax/E2E

Ít nhất bao phủ:

1. integer, string và bool literal arms;
2. one-line arm;
3. newline ngay sau `:`;
4. nhiều statements trong một arm bằng newline;
5. nhiều statements bằng `;`;
6. nhiều arms cùng dòng với `;`;
7. default `else` không có colon;
8. nested `case` trong arm;
9. `out`, `break` và `skip` từ body ở context hợp lệ;
10. target expression có side effect và được evaluate đúng một lần.

Harness phải so stdout byte-exact và exit code; không chỉ kiểm tra compile.

### 8.2. Tagged-union E2E

- unit variant và explicit numeric tags;
- one-field và multi-field payload;
- qualified và unique-unqualified constructors/patterns;
- hai enum trùng variant name nhưng qualified đúng;
- binder type được dùng trong arithmetic/string/entity field access;
- nested case để mở payload enum lồng nhau theo từng tầng;
- default và exhaustive no-default paths;
- declaration-order independence.

Giữ regression cho các file `test_enum_*`, `test_option_result_enum_e2e.vri`,
`test_explicit_tags.vri` và toàn bộ negative enum diagnostics hiện có.

### 8.3. Negative grammar

Mỗi fixture phải có tên `_rejected.vri`, compiler exit non-zero, không sinh
artifact runnable:

- `else:`;
- thiếu `:` sau pattern;
- arm rỗng trước arm kế;
- arm rỗng trước `else` hoặc `end`;
- default body rỗng;
- không có pattern arm / chỉ có `else`;
- `case expression:`;
- lặp `case` trước từng arm;
- duplicate `else` hoặc arm sau `else`;
- thiếu `end`, dùng `end.`, EOF giữa payload pattern;
- arbitrary expression làm pattern;
- token `::` trong qualified variant pattern.

### 8.4. Negative semantic

- unknown variant và wrong enum qualifier;
- ambiguous unqualified variant;
- wrong/duplicate binder count;
- duplicate and unreachable arm;
- non-exhaustive enum;
- binder dùng ngoài scope;
- literal pattern sai type target;
- payload enum equality `E3043`.

### 8.5. Đăng ký test

- Thêm suite vào `run_group_21` của `run_tests.sh`.
- Core syntax positive và các rejection quan trọng phải chạy ở `min`.
- Toàn bộ edge cases chạy khi gọi `./run_tests.sh 21` và trong `full`.
- Không để fixture tồn tại nhưng không được runner gọi.
- Không sửa expected output để che codegen bug.

## 9. Bootstrap và ma trận xác minh

1. Build Stage 2 từ `bin/virc` bằng source đã sửa.
2. Dùng Stage 2 chạy `./run_tests.sh 21` và suite enum/tagged union.
3. Build Stage 3 bằng Stage 2 từ cùng source.
4. Ad-hoc sign Stage 2/3 với cùng identifier trước khi hash nếu Mach-O yêu cầu.
5. Chứng minh Stage 2 và Stage 3 byte-identical hoặc giải thích chính xác mọi
   nondeterminism; không tuyên bố fixed-point dựa trên source hash.
6. Chạy `./run_tests.sh min`, rồi `full` nếu không có blocker ngoài task.
7. Compile cho mọi target public trong `virc --help`; runtime E2E trên runner
   phù hợp, compile-only phải được ghi rõ là chưa đủ.
8. Chạy test ít nhất hai lần để bắt state leak/nondeterminism.

## 10. Cấm tuyệt đối

- Không giữ cú pháp legacy bằng hidden compatibility branch.
- Không nhận `else:` rồi silently bỏ colon.
- Không nhận arm thiếu colon bằng cách parse đúng một statement.
- Không dùng indentation để quyết định ranh giới arm.
- Không coi empty arm là no-op hợp lệ.
- Không biến `else` thành wildcard giả để né exhaustiveness.
- Không match payload trước khi kiểm tra tag.
- Không evaluate target expression nhiều lần.
- Không cho fallthrough giữa arms.
- Không hard-code fixture, enum name, variant name hoặc expected output.
- Không dùng binary cũ để test source parser mới.
- Không promote `bin/virc` khi Stage 2/3 chưa fixed-point và suite chưa pass.
- Không stage/commit thay đổi ngoài task; workspace có thể đang dirty.

## 11. Tiêu chí nghiệm thu

Chỉ tuyên bố hoàn thành khi tất cả điều sau đúng:

- grammar §21 được enforce, mọi syntax legacy/sai ở §8.3 fail compile;
- positive grammar và tagged-union E2E chạy đúng output;
- mọi negative fixture fail vì đúng diagnostic, không phải crash/link error;
- coverage, binder type/scope, duplicate/unreachable/exhaustiveness đều pass;
- target expression evaluate đúng một lần và CFG không fallthrough;
- `run_tests.sh 21` đạt 100%; min/full không có regression thuộc task;
- compiler tự host Stage 2 == Stage 3 theo quy trình ký/hash thống nhất;
- diff sạch theo `git diff --check`, chỉ stage file thuộc task;
- báo cáo ghi command, binary hash, stdout/stderr, exit code và blocker thật.

Nếu bất kỳ target public, diagnostic class, binder scope, CFG edge hoặc
fixed-point gate nào chưa được xác minh, báo **chưa hoàn thành** thay vì 100%.
