# Prompt nghiêm ngặt: hoàn thiện UFCS Vir v2.0 end-to-end

## 1. Vai trò và mục tiêu

Bạn là compiler, linker, runtime và test engineer của Vir. Hãy hoàn thiện
**UFCS — Uniform Function Call Syntax** theo Vir Spec v2.0 §11 trên toàn bộ
pipeline compiler đang active.

Mục tiêu không phải chỉ làm cho các happy path như `x.double()` compile. UFCS
chỉ hoàn thành khi compiler phân giải chính xác, độc lập với thứ tự khai báo và
kiểu receiver, theo thứ tự bắt buộc:

```text
x.foo(args)
  1. entity method foo của static receiver type
  2. callable field foo của receiver
  3. free function foo(x, args)
  4. nếu không có candidate hợp lệ: compile error
```

Các dạng phải giữ nghĩa riêng:

```text
x.foo          = field access, tuyệt đối không gọi hàm
x.foo()        = method/callable-field/free-UFCS resolution
x.foo(a, b)    = như trên, với kiểm tra đầy đủ arity và type
```

Pipeline bắt buộc:

```text
source .vri
  -> lexer
  -> parser / AST
  -> symbol collection / type resolution
  -> UFCS candidate resolution
  -> arity, type, borrow và ownership checking
  -> AST-to-HIR/MIR/SSA
  -> LIR / register allocation
  -> target codegen / linker fixups
  -> runtime execution
```

Không được coi parse thành công, có `MethodCall` AST, có `SetArg(0)`, compile
thành công hoặc một fixture in đúng output là bằng chứng UFCS đã hoàn tất.

## 2. Nguồn sự thật

Theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md` §7.2, §10.5 và toàn bộ §11.
2. `docs/vir_language_spec_v2.0_en.md` cùng các mục tương ứng.
3. `docs/ai-spec/vir-lang/references/functions.md`, `syntax.md`, `types.md`.
4. Operator/function contract của skill `vir-lang`.
5. Pipeline active dưới `stdlib/vir/compiler/`, C-core dưới `core/src/`, và
   runtime/backend thật được release compiler sử dụng.

Spec §11.1 cho phép free function gọi qua đối số đầu tiên bằng UFCS. §11.2 mô
tả tên `this` như quy ước thể hiện function được thiết kế cho UFCS; không được
biến quy ước này thành cớ từ chối các ví dụ §11.1 như `double(val)` hoặc
`add_n(val, n)`. Entity `method` luôn có receiver `this` ngầm.

Không sửa Spec để hợp thức hóa lookup theo tên trần hoặc behavior phụ thuộc
thứ tự source.

## 3. Baseline bắt buộc trên HEAD

Trước khi sửa:

1. Ghi commit/ref hiện tại, SHA-256 của C-core compiler và `bin/virc`.
2. Chạy từng repro bằng pipeline mặc định, classic/fallback nếu còn public, và
   self-host compiler.
3. Capture raw command, stdout, stderr và exit code.
4. Không dùng claim trong report cũ làm bằng chứng.

### 3.1. Happy path hiện có

Chạy lại `tests/bootstrap_codegen/cg_op_ufcs.vri` và xác nhận output hiện tại:

```text
20
15
27
200
```

Fixture này chỉ chứng minh free-function UFCS và chaining cơ bản. Đoạn
`total_cost(this)` dùng `alloc(16)` không thay thế test entity method/callable
field canonical. Không được dùng riêng fixture này để tuyên bố §11 pass.

Chạy thêm literal UFCS canonical:

```vir
func clamp(this: int, lo: int, hi: int) -> int:
    if this < lo do out lo end
    if this > hi do out hi end
    out this
end.

func main:
    if 15.clamp(0, 10) != 10 do out 11 end
    if 7.clamp(0, 10) != 7 do out 12 end
    out 0
end.
```

### 3.2. Lỗi đã quan sát phải tái hiện

Các kết quả sau từng được quan sát trên tree hiện tại. Phải chạy lại thay vì
tin số liệu này:

- Entity method khai báo trước free function cùng tên trả kết quả method;
  đảo thứ tự khai báo lại trả kết quả free function.
- Hai entity cùng có `score()` làm `B.score()` gọi nhầm implementation của A.
- Callable field không có free function trả `0` ở C-core default/self-host;
  classic path có thể trả đúng.
- Callable field trùng tên free function gọi free function, trái thứ tự §11.4.
- `1.no_such_method()` compile thành công và in `0` trên pipeline mặc định và
  self-host thay vì compile error.
- UFCS thiếu/thừa đối số vẫn compile; thiếu đối số có thể đọc register rác và
  sinh kết quả không ổn định.

## 4. Root cause bắt buộc phải xử lý

Không giới hạn điều tra ở danh sách này:

- C parser rewrite `receiver.fn(args)` thành call mang tên trần `fn` và chèn
  receiver làm child đầu tiên trước khi có receiver type.
- C-core đăng ký entity methods trong module function table bằng tên trần;
  `q_module_add_func` trả function đã tồn tại khi trùng tên.
- C lowering gọi `find_func_index(name)` trước callable-field lookup, đảo bước
  2 và bước 3 của §11.4.
- Self-host parser tạo `AstType.MethodCall`, nhưng semantic chưa gắn resolved
  callee kind/owner/signature vào node.
- Self-host name resolution cho phép mọi missing method name vì “có thể là
  callable field”, nhưng không có bước bắt buộc xác minh field sau đó.
- Self-host AST-to-MIR hạ mọi `MethodCall` thành direct call chỉ bằng method
  name và luôn chèn receiver, nên không thể thực hiện callable-field semantics.
- LIR codegen tìm function đầu tiên có cùng tên; không có entity owner hoặc
  resolved function identity.
- Arity/type checking hiện chỉ xử lý `Call`, bỏ qua `MethodCall` hoặc không
  tính receiver theo đúng callee kind.
- Default C HIR/MIR path có thể trả operand `none` cho unresolved call rồi tiếp
  tục codegen, biến lỗi compile thành giá trị `0`.

## 5. Thiết kế symbol và method identity

### 5.1. Không gian tên

- Entity method không được đăng ký chỉ bằng bare name trong global free-function
  namespace.
- Mỗi method phải có owner type và stable identity, ví dụ internal qualified
  key tương đương `Entity::method`; spelling nội bộ cụ thể tùy thiết kế nhưng
  không được lộ hoặc thay đổi syntax Vir.
- Hai entity được phép có method cùng tên và implementation khác nhau.
- Entity method và free function cùng tên phải cùng tồn tại mà không ghi đè,
  merge body hoặc phụ thuộc thứ tự đăng ký.
- Module/import visibility phải được tôn trọng. Không resolve method/private
  symbol từ module không visible chỉ vì bare-name table có entry.

### 5.2. Signature

Resolver phải biết tối thiểu:

- callee kind: entity method, callable field, free function hoặc builtin;
- owner entity/type nếu là method/field;
- full parameter list và return type;
- receiver passing mode: value, borrow, mutable borrow hoặc representation
  tương ứng contract hiện có;
- direct function identity hoặc field offset/indirect-call metadata;
- source span của receiver, member name và argument list.

Không để backend suy luận callee kind lại từ bare name.

## 6. Parser và AST

- Lexer phải giữ `15.clamp()` thành `INT`, `.`, identifier, call delimiters;
  không nuốt dấu chấm vào float literal.
- Parser phải giữ khác biệt rõ giữa `x.foo` và `x.foo()`.
- Parser có thể tạo một unresolved member-call AST, nhưng không được quyết định
  rằng mọi call dấu chấm là free function hoặc direct method chỉ từ syntax.
- Receiver phải xuất hiện đúng một lần trong AST và giữ source location.
- Chaining phải preserve kết quả call trước làm receiver call sau:
  `x.double().add_n(3).clamp(0, 100)`.
- Parentheses, literal receiver, index receiver, field receiver và expression
  receiver phải hoạt động mà không nhân bản evaluation.
- `?.` là safe access theo contract riêng; không tự phát minh safe method-call
  semantics nếu Spec chưa định nghĩa. Không rewrite `x?.foo` thành UFCS call.

## 7. Semantic UFCS resolver

Với mỗi `receiver.foo(args)`, semantic phải thực hiện đúng thứ tự:

### 7.1. Xác định receiver

1. Resolve và type-check receiver expression.
2. Xác định static entity/primitive/container type và ownership state.
3. Đánh giá receiver đúng một lần theo thứ tự trái sang phải.
4. Không dùng tên biến, field layout toàn cục hoặc method đầu tiên cùng tên để
   đoán type.

### 7.2. Entity method

- Tìm `foo` trong method set của receiver entity type.
- Chèn implicit `this` đúng ABI và đúng borrow/mutation contract.
- Không coi method của entity khác là candidate.
- Return type của method phải chảy sang call tiếp theo trong UFCS chain.

### 7.3. Callable field

- Chỉ chọn bước này nếu receiver type có field `foo` mang callable/function
  pointer type phù hợp.
- Load field đúng offset của receiver type và emit indirect call thật.
- Không truyền receiver như argument 0 trừ khi callable field signature tự khai
  báo tham số đó; ví dụ Spec `btn.on_click()` gọi `handle_click()` không có
  receiver argument.
- Arity/type phải được kiểm tra theo callable field signature, không theo một
  free function trùng tên.

### 7.4. Free-function UFCS

- Chỉ chạy sau khi không có entity method và callable field hợp lệ.
- Resolve `foo(receiver, args...)` theo visibility và signature.
- Receiver là argument đầu tiên; arguments explicit theo sau, đúng thứ tự.
- `this` là quy ước hữu ích nhưng các free function hợp lệ theo §11.1 như
  `double(val)` vẫn phải gọi được.
- Builtin/free functions được hỗ trợ qua UFCS, ví dụ array `a.len()`, phải đi
  qua candidate/resolution rõ ràng chứ không hard-code output.

### 7.5. Không có candidate

- Phát compile diagnostic tại member name/call span.
- Diagnostic phải nêu receiver type, requested member và candidate bị loại vì
  arity/type nếu có.
- Không tạo unresolved runtime stub, không trả `0`, không bỏ call, không parser
  recovery thành partial AST và không tiếp tục linking.

## 8. Arity, type, borrow và evaluation order

- Kiểm tra arity cho cả `Call` và member/UFCS call sau khi biết callee kind.
- Với method/free UFCS, tính implicit receiver đúng một lần trong effective
  argument list.
- Với callable field, không tự động tính receiver là argument.
- Thiếu hoặc thừa đối số phải là compile error; không đọc register cũ, mặc định
  `0`, bỏ argument hoặc để callee tự chịu.
- Kiểm tra type receiver so với first parameter của free UFCS và `this` type
  của method.
- Kiểm tra type từng explicit argument và return type.
- Tôn trọng `ref`, mutable access, move/borrow và lifetime contract hiện có.
- Receiver/arguments có side effect phải chạy đúng một lần, trái sang phải.
- Chaining phải dùng typed return value thật, không dùng fallback `int` hoặc
  pointer-sized default.

## 9. Lowering, LIR và codegen

- Semantic phải annotate call bằng resolved callee identity/kind/signature.
- Direct entity-method/free-function call phải dùng stable function ID hoặc
  qualified symbol, không lookup lại bare name trong backend.
- Callable field phải hạ thành field load + indirect call (`blr`, `call *reg`,
  `call_indirect` hoặc target-equivalent) với signature đúng.
- `SetArg(0)` chỉ được emit khi resolved callee contract yêu cầu receiver.
- Register allocation và call lowering phải bảo toàn receiver/argument values
  qua nested/chained calls; không phụ thuộc register state từ call trước.
- Linker/fixup phải fail hard với unresolved direct callee. Không được map sang
  `LIR_RT_UNRESOLVED`, NOP, zero stub hoặc địa chỉ mặc định rồi vẫn sinh binary.
- Giữ thiết kế target-neutral ở semantic/MIR; không vá riêng ARM64 để che lỗi
  resolver chung.

## 10. Test bắt buộc

### 10.1. Parser/AST

1. `x.foo` là field access.
2. `x.foo()` là unresolved/resolved member call, không phải field read.
3. Literal UFCS `15.clamp(0, 10)`.
4. Chaining ba bước.
5. Receiver là call result, index expression, field expression và parenthesized
   expression.
6. Source spans cho receiver, member và arguments.

### 10.2. Resolution order

Tạo positive E2E test có method và free function cùng tên, chạy với cả hai thứ
tự khai báo. Kết quả phải giống nhau và luôn chọn method:

```vir
func score(this, n: int) -> int:
    out 1000 + this.value + n
end.

entity Box:
    value: int

    method score(n: int) -> int:
        out this.value + n
    end.
end.

func main:
    var b = Box(value: 10)
    if b.score(5) != 15 do out 11 end
    out 0
end.
```

Tạo variant entity trước/free function sau và assert cùng kết quả.

### 10.3. Hai entity cùng method name

```vir
entity A:
    value: int
    method score() -> int:
        out this.value + 1
    end.
end.

entity B:
    value: int
    method score() -> int:
        out this.value + 2
    end.
end.

func main:
    var a = A(value: 10)
    var b = B(value: 20)
    if a.score() != 11 do out 11 end
    if b.score() != 22 do out 12 end
    out 0
end.
```

Test phải chứng minh hai body/direct-call target khác nhau ở IR/link fixup và
runtime, không chỉ AST có hai definitions.

### 10.4. Callable field và priority

```vir
entity Button:
    on_click: ptr
end.

func on_click(this) -> int:
    out 88
end.

func handler() -> int:
    out 77
end.

func main:
    var btn = Button(on_click: handler)
    if btn.on_click() != 77 do out 11 end
    out 0
end.
```

Test phải chứng minh callable field thắng free function trùng tên và artifact
thực hiện indirect call tới `handler`. Thêm variant không có free function.

### 10.5. Field và function không mơ hồ

```vir
entity User:
    name: int
end.

func name(this: User) -> int:
    out 999
end.

func main:
    var u = User(name: 42)
    if u.name != 42 do out 11 end
    if u.name() != 999 do out 12 end
    out 0
end.
```

### 10.6. Negative tests

Mỗi case phải fail compile với diagnostic và non-zero exit:

- `1.no_such_method()`;
- thiếu đối số: `10.add_n()` khi function cần `val, n`;
- thừa đối số: `10.add_n(1, 2)`;
- receiver sai type so với first parameter;
- explicit argument sai type;
- field tồn tại nhưng không callable: `obj.count()`;
- method của entity khác có cùng tên nhưng receiver type không sở hữu;
- method/private free function không visible từ module gọi.

Không coi runtime crash, output `0`, linker unresolved hay register garbage là
negative-test pass.

### 10.7. Evaluation và chaining

- Receiver có side effect tăng counter phải chạy đúng một lần.
- Mỗi explicit argument có marker/counter phải chạy trái sang phải một lần.
- Chained return type đổi qua ít nhất hai kiểu nếu type system cho phép.
- Nested call phải không làm mất receiver/args qua caller-saved registers.
- Chạy test lặp nhiều lần để bắt nondeterminism do register state.

### 10.8. Existing regression

Giữ và tăng cường:

- `tests/bootstrap_codegen/cg_op_ufcs.vri`;
- `tests/bootstrap_codegen/cg_array_len.vri`;
- mọi entity method, callable field, indirect-call và borrow test liên quan.

Không chỉ in expected value trong comment. Test phải assert value/exit code
hoặc harness phải so stdout byte-exact và non-zero khi lệch.

## 11. Ma trận target và E2E

Khóa target list từ `virc --help`, target parser và backend registry trước khi
sửa. Tối thiểu kiểm tra mọi target public hiện có:

- macOS ARM64;
- Linux ARM64;
- Linux x86_64;
- Linux RISC-V 64;
- Wasm32/WASI.

Với mỗi target:

1. Rebuild compiler từ source task và ghi SHA-256/provenance.
2. Compile toàn bộ positive fixtures bằng target flag thật.
3. Chạy artifact bằng native runner, QEMU hoặc WASI runtime phù hợp.
4. Chạy ít nhất hai lần.
5. Capture raw command, stdout, stderr và exit code.
6. Chạy negative fixtures và chứng minh compiler fail trước artifact execution.

Compile-only, AST/MIR inspection, object validation, disassembly hoặc unit test
resolver không thay thế runtime E2E. Không có runner cho target public là
blocker/incomplete, không phải lý do tự hạ acceptance.

## 12. Cổng static và architectural checks

Sau khi sửa, chứng minh:

- method table giữ owner type;
- hai entity method cùng bare name có function identity khác nhau;
- `MethodCall`/member call sau semantic mang resolved kind và callee identity;
- backend direct call không tìm method bằng bare name;
- callable field path emit indirect call;
- unresolved member call không tới LIR/linker;
- arity/type checker bao phủ mọi resolved callee kind;
- không có fallback trả zero cho unresolved call;
- declaration order không ảnh hưởng call target.

Dùng `rg`, AST/MIR/LIR dumps và targeted assertions để chứng minh, nhưng các
bằng chứng này chỉ bổ sung cho runtime E2E.

## 13. Cấm tuyệt đối

- Không mangle mọi method chỉ bằng bare name hoặc global declaration index.
- Không chọn function đầu tiên cùng tên.
- Không làm test pass bằng đổi thứ tự definitions.
- Không cấm hai entity có method cùng tên để né resolver.
- Không đổi callable field thành free function wrapper.
- Không truyền receiver ngầm vào callable field không yêu cầu receiver.
- Không bỏ qua missing method vì “có thể là callable field”.
- Không coi unresolved call là `0`, NOP hoặc runtime stub thành công.
- Không bỏ qua thiếu/thừa argument hoặc đọc register mặc định.
- Không hard-code `score`, `on_click`, `handler`, entity names hoặc expected
  values trong compiler/runtime.
- Không thay syntax UFCS bằng direct call trong positive tests.
- Không chỉ sửa C classic path và để default/self-host sai, hoặc ngược lại.
- Không dùng interpreter fallback, prebuilt binary hoặc host shim để giả E2E.
- Không sửa Spec để hợp thức hóa implementation hiện tại.
- Không reset, checkout, restore, stage hoặc commit thay đổi ngoài task; giữ
  nguyên mọi thay đổi sẵn có của người dùng.

## 14. Quy trình thực hiện

1. Chạy baseline, ghi compiler hashes và raw evidence.
2. Lập inventory parser AST, symbol tables, entity metadata, call lowering,
   indirect call, backend fixups và tests.
3. Viết root cause theo từng pipeline trước khi sửa.
4. Thiết kế method identity và resolved-call representation target-neutral.
5. Sửa symbol/type/semantic resolver trước khi sửa backend.
6. Sửa direct/indirect call lowering và hard-fail unresolved references.
7. Thêm toàn bộ positive/negative/ordering/collision/arity/type tests.
8. Rebuild compiler; không dùng binary cũ.
9. Chạy regression và E2E hai lần trên mọi target.
10. Chạy `git diff --check`; rà soát diff chỉ chứa file task.
11. Chỉ stage file task và tạo commit nguyên tử nếu workflow yêu cầu, ví dụ
    `implement strict v2 ufcs resolution`.

## 15. Báo cáo bàn giao bắt buộc

Báo cáo cuối phải có:

- root cause tại lexer/parser, symbols/types, semantic, HIR/MIR/LIR, backend và
  linker;
- thiết kế method identity/resolved-call representation cuối cùng;
- danh sách file sửa/thêm/xóa;
- behavior entity method, callable field và free UFCS;
- bằng chứng declaration-order independence;
- bằng chứng hai entity cùng method name;
- bằng chứng indirect callable-field call và đúng priority;
- kết quả arity/type/missing-method diagnostics;
- raw command, compiler hash, target, runner, stdout, stderr và exit code cho
  từng E2E run;
- kết quả regression suite;
- mọi blocker hoặc target chưa chạy được.

Không tuyên bố hoàn thành nếu một trong các điều sau còn đúng:

- đổi thứ tự khai báo làm đổi callee;
- `B.score()` gọi body của `A.score()`;
- callable field trả `0` hoặc thua free function trùng tên;
- missing method compile thành công;
- thiếu/thừa argument compile thành công;
- backend còn lookup method bằng bare name;
- unresolved call còn sinh binary;
- receiver/argument bị đánh giá nhiều lần hoặc đọc register rác;
- chỉ happy-path fixture pass;
- chưa chạy artifact mới sinh trên toàn target matrix.

