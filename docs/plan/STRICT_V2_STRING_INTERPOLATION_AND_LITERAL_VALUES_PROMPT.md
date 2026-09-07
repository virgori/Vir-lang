# Prompt nghiêm ngặt: Vir v2.0 string interpolation và literal values

## Vai trò và mục tiêu

Bạn là compiler engineer của Vir. Hãy đưa string interpolation và các literal
value của **Vir Spec v2.0** vào trạng thái chạy đúng end-to-end trên pipeline
compiler đang active:

```text
lexer -> parser/AST -> semantic -> AST-to-MIR/SSA -> LIR -> target codegen/runtime
```

Nguồn sự thật, theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md` §4.3 (literals), §4.5 (string memory),
   và ví dụ `$name`, `$this.name`, `$erx`.
2. `docs/ai-spec/vir-lang/references/syntax.md`, `types.md`, `functions.md`.
3. Mã active dưới `stdlib/vir/compiler/` và runtime liên quan.

Không hạ yêu cầu Spec để cho compiler cũ pass. Không đánh đồng “parse không
error” với “interpolation đã chạy”.

## Sự cố đã tái hiện trên HEAD

Source chuẩn:

```vir
func main:
    var name = "Vir"
    var count = 42
    print("Hello $name")
    print("count=$count")
end.
```

Hiện `lex_string` trong `stdlib/vir/compiler/lexer.vri` luôn trả một token
`Str`; không có nhánh nào phát `InterpStart` / `InterpEnd`. Vì vậy nhánh
`InterpExpr` của parser không thể tới từ source hợp lệ. Nếu tự tạo AST,
`ast_to_mir` chỉ intern `ast_node_name(expr)` mà không lower từng segment hoặc
giá trị; LIR codegen lại xử lý `MIR_INTR_INTERP` như string literal tĩnh.

Đây là false positive: `tests/test_interp.vri` có thể compile nhưng `$name`
không được nội suy. Không được coi đó là test pass.

## Dấu vết commit lịch sử bắt buộc phải rà soát

`8950d6066d8a850991d0f752d425f621a639d15f`
`feat(compiler): hoàn thiện 100% Trụ Cột 5 (Xử Lý Chuỗi & Ký Tự Nâng Cao)`
đã tuyên bố hỗ trợ `$var`, `$(expr)`, `$$`, escape và runtime helpers. Commit
này là ancestor của HEAD, nhưng diff của nó chỉ sửa `virc_stage1.vri`, binary,
docs và fixture bootstrap; nó **không** sửa pipeline active trong
`stdlib/vir/compiler/`. Hãy đọc diff commit này để tái sử dụng ý tưởng hay
test case, nhưng không copy mù hoặc tin claim hoàn thành thay cho kiểm chứng.

Các claim rộng hơn cần được coi là framework-coverage, không phải bằng chứng
runtime interpolation đã hoàn tất:

- `5b00db79` — ghi `InterpExpr` trong AST-to-MIR “complete”.
- `70c6b407` — ghi `InterpExpr` trong semantic “100% Coverage”.
- `c654498f` và `2d4a6a65` — tuyên bố compiler/spec/test pass 100%.

## Phạm vi bắt buộc

### 1. Interpolation

1. Lexer phải nhận dạng và preserve xen kẽ literal segment với interpolation
   được Spec ghi nhận, tối thiểu `$identifier` và `$base.field`.
2. Parser/AST phải giữ các segment theo đúng thứ tự, bao gồm expression/value
   được chèn và location chính xác. Không lưu cả source interpolation như một
   literal string duy nhất.
3. Name resolution/type-check phải chạy trên mọi expression interpolation,
   báo lỗi undeclared identifier, field không tồn tại, và biểu thức không thể
   stringify ở source location. Không được skip token hoặc tạo AST partial.
4. Lowering phải đánh giá các value theo thứ tự trái sang phải, format đúng
   kiểu, rồi nối segment thành fat string `{ptr, len}` mới. Chuỗi kết quả là
   immutable và cấp phát từ Arena; literal không có interpolation vẫn ở Static
   và không cấp phát runtime.
5. LIR/codegen của mọi target công khai phải có đường runtime thật cho
   formatting/nối string; `MIR_INTR_INTERP` không được alias sang string-pool
   literal. Giữ target-neutral design, không thêm ARM64-only workaround,
   target metadata-only hay interpreter fallback để giả execution.
6. Chỉ hỗ trợ `$(expr)` hoặc `$$` như syntax chuẩn nếu đọc được nguồn Spec
   chuẩn xác cho chúng. Nếu giữ compatibility syntax, tách test/documentation
   compatibility khỏi acceptance criteria Spec v2.0; không tuyên bố nó là
   canonical syntax chỉ vì commit `8950d606` có claim đó.

### 2. Literal values (§4.3)

Hoàn thiện và giữ phân biệt semantic cho:

```vir
42
3.14
"hello"
"Hello $name"
true
false
none
[1, 2, 3]
["a": 1, "b": 2]
```

Yêu cầu cụ thể:

- Float phải lower từ `float_val` hoặc representation float chính xác, không
  đọc nhầm `int_val`.
- `true`/`false` phải có type `bool`, không chỉ là `LiteralInt` 1/0; `none`
  phải giữ null semantics riêng thay vì bị đồng nhất với integer zero.
- Dict cần AST và type `Dict` đúng; không được giả dạng `EntityLiteral` hay
  mất key expression không phải string.
- List/dict phải preserve toàn bộ phần tử, type-check nhất quán và lower đúng
  representation runtime. Không nới lỏng type lỗi chỉ để test chạy.
- Formatting trong interpolation phải có semantic xác định cho các primitive
  mà Spec/examples yêu cầu. Với kiểu chưa được Spec định nghĩa stringify,
  phát diagnostic thay vì in địa chỉ hoặc silently coerce.

## Cấm tuyệt đối

- Không biến `$name` thành literal `"$name"` hoặc bỏ segment sau `$`.
- Không sửa test thành `str_concat`, `int_to_str`, hay print rời để né
  interpolation.
- Không coi chỉ compile thành công là pass; cần assert output/giá trị runtime.
- Không hạ `none` thành `0`, boolean thành `int`, hoặc dict thành entity.
- Không thêm parser recovery cho source hợp lệ rồi bypass semantic/codegen.
- Không sửa Spec để hợp thức hoá implementation cũ.
- Không reset, checkout, restore, stage, hoặc commit thay đổi không thuộc task;
  worktree đang có thay đổi của người dùng.
- Không coi cross-compile, object inspection, Wasm validation hay unit test
  runtime helper là E2E cho bất kỳ target nào.

## Ma trận target bắt buộc

Khóa từ `virc --help`, parser `--target` và `target_triple.vri` mọi target
công khai trước khi sửa. Với tree hiện tại, tối thiểu là `macos-arm64`,
`linux-arm64`, `linux-x86_64`, `linux-riscv64`, `wasm32-wasi-p1`; mọi target
mới driver nhận tự động vào ma trận. Mỗi target phải có lexer/AST/semantic/MIR
chung và **backend/runtime implementation thật** cho fat-string allocation,
format và concat, rồi chạy artifact mới sinh bằng native runner, container,
QEMU hoặc WASI runtime tương ứng. Không có runner/CI chạy được một target là
**blocked/incomplete cho toàn task**, không được đổi thành compile-only.

## Test và acceptance bắt buộc

1. Lexer/AST test kiểm tra segment order và source location cho literal-only,
   `$name`, `$this.name`, nhiều interpolation trong một string, và malformed
   interpolation.
2. Semantic negative test cho identifier/field không tồn tại và type không có
   stringify contract.
3. End-to-end bắt buộc trên **mỗi target trong ma trận**: compile và chạy
   artifact mới sinh bằng target flag/runner thật, capture stdout/stderr và
   exit code cho cả string lẫn integer interpolation. Ví dụ output chính xác
   `Hello Vir` và `count=42`, exit code `0`. Kiểm tra fat-string nội bộ chỉ là
   test phụ, không thay thế runtime output.
4. Literal regression test phải kiểm tra float không thành zero; type `bool`;
   null `none`; list; dict với key string và key expression phù hợp spec.
5. Test literal string không interpolation chứng minh vẫn là Static/không gọi
   runtime concat; test interpolation chứng minh có allocation/concat runtime.
6. Chạy test hai lần trên mọi target backend trong ma trận; lưu target triple,
   runner, raw command, stdout/stderr và exit code. Nếu cross target chưa chạy
   được, phải thêm runner/emulator/CI cần thiết rồi chạy; compile/link hoặc
   inspection không được thay thế execution.

## Cách làm và tiêu chí bàn giao

1. Trước khi sửa, viết ngắn gọn root cause cho từng điểm đứt lexer, AST,
   semantic, lowering và codegen; nêu khác biệt giữa `8950d606` stage-1 và
   pipeline active.
2. Sửa nhỏ nhất nhưng đầy đủ trên pipeline active. Chỉ port code stage-1 khi
   chứng minh được representation/ABI phù hợp.
3. Chạy `git diff --check`, test mới, regression interpolation/literal và
   compile/run E2E; báo lệnh cùng stdout/stderr và exit code thực tế.
4. Chỉ stage các file task, rồi tạo một commit nguyên tử, ví dụ:
   `implement spec string interpolation and literal values`.
5. Báo cáo cuối: file sửa/thêm, hành vi được hỗ trợ, syntax compatibility nào
   không thuộc Spec, kết quả test, và mọi blocker còn lại.

## Cổng nghiệm thu end-to-end — không ngoại lệ

Compile thành công, AST/MIR inspection, Wasm validation, hoặc unit test gọi
runtime helper trực tiếp không chứng minh interpolation. Agent phải chạy **hai
lần trên mọi target trong ma trận** artifact do compiler vừa sửa sinh ra, rồi
chứng minh output đã được nội suy bằng byte-exact stdout và exit code `0`. Ít
nhất một test phải chèn string và integer vào cùng một string; một test khác
phải chứng minh literal không nội suy không vô tình cấp phát/format. Không
hard-code marker PASS, không thay source interpolation bằng
`str_concat`/`int_to_str` ở test, và không dùng binary cũ hoặc stage-1 khác.
Nếu bất kỳ artifact target nào crash, bị kill, im lặng, không thể chạy, hoặc
chưa có runner, task là **incomplete/blocked** — không được thay bằng
compile-only hoặc tuyên bố pass có điều kiện.

Không tuyên bố hoàn thành nếu `$name` vẫn qua lexer như `Str` duy nhất, nếu
`MIR_INTR_INTERP` vẫn chỉ trỏ string static, nếu literal value làm mất
type/value theo các điều kiện trên, hoặc nếu không vượt cổng nghiệm thu này.
