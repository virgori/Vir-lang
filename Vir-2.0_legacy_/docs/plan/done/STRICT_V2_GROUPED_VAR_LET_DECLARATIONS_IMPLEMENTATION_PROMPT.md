# Prompt nghiêm ngặt: hoàn thiện grouped `var` / `let` / `const` Vir v2.0

## Vai trò và kết quả bắt buộc

Bạn là compiler engineer chịu trách nhiệm sửa grouped declarations end-to-end
trong compiler Vir tự host. Đây là lỗi parser và semantic đã được tái hiện trên
`virc 3.6.1`, không phải lỗi formatting của project sử dụng Vir.

Kết quả cuối cùng bắt buộc:

1. grouped `var`, `let` và `const` dùng newline hoặc `;` được parse đúng theo
   Vir v2.0;
2. mọi member của grouped `let`/`const` giữ đúng immutable semantics;
3. mọi member của grouped `var` giữ đúng mutable semantics và type annotation;
4. declaration group không tạo lexical scope ẩn và bindings vẫn nhìn thấy ở
   phần còn lại của scope chứa nó;
5. dấu phẩy không được chấp nhận làm declaration separator;
6. ordinary assignment sau declaration không bị nuốt thành declaration mới;
7. implicit-local assignment hợp lệ hiện có không bị phá ngoài phạm vi group;
8. diagnostic lỗi có code, line và column ổn định;
9. modular compiler source, generated `virc.vri`, bootstrap compiler và test
   gates đều đồng bộ;
10. self-host fixed point và toàn bộ regression suite pass.

Không được giải quyết bằng cách bắt user lặp lại `var`/`let` trên từng dòng,
đổi source application, hard-code tên biến, hoặc chỉ làm fixture cụ thể compile
qua. Workaround lặp keyword chỉ là biện pháp tạm thời.

## Nguồn sự thật và phạm vi

Trước khi sửa, đọc và đối chiếu ít nhất:

- `docs/vir_language_spec_v2.0_en.md`, §1.0 và §5;
- `docs/vir_language_spec_v2.0_vi.md`, các mục tương ứng;
- `docs/ai-spec/vir-lang/references/syntax.md`;
- `.agents/skills/vir-lang/SKILL.md`;
- `.agents/skills/vir-clean-code/SKILL.md`;
- `stdlib/vir/compiler/lexer.vri`;
- `stdlib/vir/compiler/parser.vri`;
- `AstType`/`AstNode` active trong `stdlib/vir/compiler/parser.vri`;
- `stdlib/vir/compiler/sem_pass2_symbols.vri`;
- `stdlib/vir/compiler/sem_pass3_names.vri`;
- `stdlib/vir/compiler/sem_pass4_types.vri`;
- `stdlib/vir/compiler/sem_pass5_infer.vri`;
- `stdlib/vir/compiler/sem_pass6_typecheck.vri`;
- `stdlib/vir/compiler/sem_pass7_cfa.vri`;
- `stdlib/vir/compiler/sem_pass8_borrow.vri`;
- `stdlib/vir/compiler/sem_pass9_constfold.vri`;
- `stdlib/vir/compiler/ast_to_mir.vri`;
- `tests/test_grouped_var.vri`;
- `tests/vri/test_var_block.vri`;
- test manifests/runners active trên HEAD.

Không sửa language specification để hợp thức hóa behavior hiện tại. Source
canonical của compiler nằm trong các module dưới `stdlib/vir/compiler/`; không
sửa riêng bundle `stdlib/vir/compiler/virc.vri`. Sửa module canonical, sau đó
dùng workflow sync được repository xác nhận.

Đọc `git status` trước khi làm. Worktree có thể chứa thay đổi của owner; không
reset, restore, overwrite, stage hay commit file ngoài task. Không sửa các bản
`.new`, `.backup`, frozen hoặc generated cũ trừ khi workflow active chứng minh
chúng là input bắt buộc.

## Contract cú pháp không được thương lượng

Separator cho statement/declaration group là:

```text
separator := ";" | NEWLINE
```

Dấu phẩy chỉ dùng cho flat list như arguments và collection elements; dấu phẩy
không phải declaration separator.

Các dạng sau phải hợp lệ:

```vir
var
    width = 1920
    height: int = 1080
    visible = true

let
    area = width * height
    doubled = area * 2

const
    MIN_WIDTH = 320
    MAX_WIDTH = 7680
```

```vir
var x = 10; y: int = 20; z = 30
let first = 1; second = first + 1
const LOW = 10; HIGH = 100
```

Trailing `;` trước newline vẫn hợp lệ:

```vir
var
    x = 1;
    y = 2;
```

Dạng sau phải bị từ chối ở parser với diagnostic rõ ràng, không được rơi tới
undefined-variable errors ở semantic pass:

```vir
var x = 1, y = 2
let first = 1, second = 2
```

Không được biến comma form thành compatibility syntax chỉ vì parser hiện có
nhánh nhận `TokType.Comma`.

## Baseline đã xác nhận — bắt buộc tái hiện lại trên HEAD

Trước khi sửa, ghi lại:

- commit/ref;
- `bin/virc --version`;
- SHA-256 của compiler đang chạy;
- command, stdout, stderr và exit code của từng fixture;
- kết quả `python3 tools/sync_virc.py --check`.

Các lỗi dưới đây đã được quan sát nhưng phải chạy lại, không được dùng phần mô
tả này thay cho bằng chứng mới.

### 1. Grouped typed `var` theo newline bị parser từ chối

```vir
func main:
    var
        first: int = 1
        second: int = 2
    print(first + second)
    out 0
end.
```

Baseline: `E1004 expected expression` tại binding thứ hai.

### 2. Grouped `let` mất immutable semantics

```vir
func main:
    let
        first = 1
        second = 2
    second = 9
    print(first)
    print(second)
    out 0
end.
```

Baseline: compile thành công và in `1`, `9`. Sau fix, assignment `second = 9`
phải fail với diagnostic immutable-variable hiện hành, dự kiến `E3003` nếu code
đó vẫn là taxonomy active.

### 3. Same-line semicolon grouped `let` cũng mất immutable semantics

```vir
func main:
    let first = 1; second = 2
    second = 9
    out 0
end.
```

Baseline: compile thành công. Sau fix phải fail tại reassignment của `second`.

### 4. Control chứng minh standalone `let` đang đúng

```vir
func main:
    let first = 1
    let second = 2
    second = 9
    out 0
end.
```

Baseline: compiler đã reject assignment với immutable diagnostic. Không được
làm control này regression trong lúc sửa group.

### 5. Existing fixtures không bảo vệ suite

Chạy trực tiếp tối thiểu:

```text
bin/virc tests/test_grouped_var.vri -o <temp-output>
bin/virc tests/vri/test_var_block.vri -o <temp-output>
```

Xác nhận vì sao chúng đang fail nhưng full suite vẫn xanh: fixture không nằm
trong active manifest, runner bỏ qua, hay expectation không được assert. Sau
fix, test mới phải nằm trong gate thực sự được CI/full-suite chạy.

## Root cause phải được xác nhận trên source active

Không tin line number cố định; tìm lại symbol trên HEAD. Baseline hiện chỉ ra
ít nhất bốn lỗi liên kết với nhau.

### 1. Parser group không dùng unified separator

`parse_var_decl()` hiện chỉ thử `Comma` rồi `Semicolon` trong continuation
loop. Nó không coi `Newline` là separator dù repository đã có helper
`match_list_sep()` hỗ trợ newline.

Không chỉ thay một condition cho test xanh. Xác nhận behavior ở function body,
module scope, control-flow body và declaration có type annotation.

### 2. Single-declaration parser nuốt separator của group

`parse_var_decl_single()` hiện consume optional semicolon sau initializer trước
khi `parse_var_decl()` có thể quyết định đó là declaration-group separator hay
statement terminator. Vì vậy same-line `var x = 1; y = 2` thường không tạo hai
declaration nodes như spec yêu cầu.

Ownership của separator phải thuộc parser level có đủ context. Single-binding
parser không được âm thầm lấy token mà outer group parser cần.

### 3. Binding continuation rơi thành implicit mutable assignment

Khi newline/semicolon continuation không được group parser consume, dòng như
`second = 2` được parse thành ordinary `Assign`. `sem_pass3_names.vri` và
`sem_pass6_typecheck.vri` cho phép assignment chưa có declaration tạo implicit
mutable local. Behavior đó biến grouped `let` thành mutable mà không diagnostic.

Không được sửa bằng cách tắt toàn bộ implicit locals nếu language/runtime hiện
đang hỗ trợ chúng. Parser phải giữ đúng declaration identity để semantic pass
nhận `ConstDecl`/immutable symbol cho từng member.

### 4. Generic `AstType.Block` tạo scope sai

Khi parser hiện gom được nhiều member, nó bọc chúng trong `AstType.Block`.
Semantic passes coi `Block` là lexical scope mới và push/pop scope. Declaration
group không phải control-flow block và không tạo lifetime/scope mới.

Không được sửa newline parser rồi giữ nguyên scoping bug này. Chọn một
representation đúng, ví dụ:

- flatten declaration members vào statement list của scope chứa; hoặc
- declaration-group AST node chuyên biệt không tạo scope; hoặc
- một representation tương đương được mọi pass xử lý nhất quán.

Không thêm exception rời rạc ở chỉ một semantic pass. Name resolution, type
inference, type checking, CFA, borrow checking, constant folding và lowering
phải cùng nhìn thấy các declaration trong đúng enclosing scope.

## Invariant implementation bắt buộc

Sau parsing, mỗi binding trong group phải giữ đầy đủ:

- declaration kind: mutable `var` hay immutable `let`/`const`;
- source name và exact source span;
- optional type annotation;
- optional/required initializer theo contract active;
- initializer evaluation order từ trái sang phải;
- khả năng tham chiếu binding trước trong cùng group;
- enclosing lexical scope giống như các declaration viết keyword riêng;
- ownership/lifetime/drop behavior giống standalone declaration tương ứng.

Ví dụ sau phải in `6`:

```vir
func main:
    let
        first = 1
        second = first + 2
        third = second + 3
    print(third)
    out 0
end.
```

Group không được tạo scope mới, vì vậy ví dụ sau phải compile và in `3`:

```vir
func main:
    var
        first = 1
        second = 2
    print(first + second)
    out 0
end.
```

Các declaration sau group phải giữ đúng boundary. Ít nhất kiểm tra:

```vir
func main:
    var
        total = 1
        step = 2
    total = total + step
    print(total)
    out 0
end.
```

`total = total + step` là reassignment, không phải redeclaration member mới.
Nếu grammar cần source-column/indent information để phân biệt keyword-only
group với statement kế tiếp, dùng token span/column active và viết test rõ;
không suy đoán bằng tên biến hay expression shape. Nếu source spec và parser
architecture bộc lộ ambiguity thật sự, báo `BLOCKED` với minimal counterexample
thay vì tự sửa spec.

## Regression matrix bắt buộc

Thêm test tự động, thực sự được active gate chạy, cho ít nhất các nhóm sau.

### Positive parsing và runtime

1. newline grouped `var` với inferred types;
2. newline grouped `var` với explicit types;
3. newline grouped `let`;
4. newline grouped `const`;
5. same-line `;` grouped `var`;
6. same-line `;` grouped `let`;
7. trailing `;` trước newline;
8. member sau tham chiếu member trước trong cùng group;
9. sử dụng toàn bộ bindings sau group;
10. reassignment hợp lệ cho mọi grouped `var` member;
11. group tại function scope;
12. group trong nested control-flow scope;
13. module-level grouped state theo §5.3;
14. declaration không initializer nếu contract active cho phép;
15. type annotation gồm built-in, entity và generic/container type hiện được
    compiler hỗ trợ;
16. tuple destructuring và single declaration hiện có không regression.

### Negative semantics và diagnostics

1. reassign member đầu, giữa và cuối của grouped `let`;
2. reassign member của grouped `const`;
3. incompatible initializer với explicit type ở member đầu và member sau;
4. duplicate name trong cùng group;
5. duplicate/shadow behavior so với standalone declaration cùng scope;
6. use-before-declaration trong group;
7. comma-separated `var`, `let`, `const` bị parser reject;
8. malformed member thiếu name, type hoặc initializer;
9. diagnostic location trỏ đúng member lỗi, không chỉ trỏ keyword mở group;
10. group không che hoặc tạo lại implicit local ngoài group.

### AST/scope structural assertions

Test phải chứng minh, không chỉ suy luận từ compile success:

- mỗi member có đúng declaration node/kind;
- group không tạo lexical scope ngoài ý muốn;
- `let`/`const` symbols có `is_mutable = false`;
- `var` symbols có `is_mutable = true`;
- initializer order được giữ;
- lowering không nhận các continuation members như `Assign` implicit local.

Nếu test framework chưa có AST assertion trực tiếp, thêm structural oracle tối
thiểu hoặc diagnostic/runtime controls đủ để bắt chính xác regression này.

## Test integration bắt buộc

Không để test chỉ nằm rời trong `tests/` hoặc `tests/vri/`. Thêm chúng vào
manifest/runner active phù hợp hoặc mở rộng runner theo convention hiện hành.
Có thể tạo contract ID mới như `DECL-GROUP-001` nếu manifest yêu cầu ID, nhưng
phải kiểm tra uniqueness và naming convention trước khi dùng.

Mỗi test phải assert ít nhất:

- compiler exit code;
- expected diagnostic code/location cho negative case;
- không tạo artifact cho compile failure;
- exact stdout và runtime exit code cho positive case;
- không coi thiếu runner là PASS đối với target được yêu cầu chạy.

Không dùng một test compile-only để chứng minh immutable semantics. Phải có
negative reassignment test cho từng member position và positive runtime test.

## Generated source và bootstrap

Sau khi sửa canonical modules:

1. chạy workflow sync chính thức để cập nhật `stdlib/vir/compiler/virc.vri`;
2. chạy `python3 tools/sync_virc.py --check` và yêu cầu exit `0`;
3. rebuild self-host compiler bằng command active được repository xác nhận;
4. bootstrap ít nhất tới hai stage liên tiếp;
5. yêu cầu stage cuối và stage trước đó bit-for-bit identical;
6. ghi SHA-256 của các stage và `bin/virc` cuối;
7. chạy fixture bằng compiler bootstrap cuối, không chỉ compiler baseline cũ.

Không copy binary cũ để giả fixed point. Nếu code signing là bắt buộc trên
macOS, ghi rõ command và xác nhận hash trước/sau signing theo contract release
hiện hành.

## Completion gates

Chỉ kết luận hoàn tất khi tất cả gate sau xanh:

1. mọi baseline repro cho kết quả mới đúng;
2. canonical newline groups compile và chạy đúng;
3. canonical semicolon groups compile và chạy đúng;
4. grouped `let`/`const` reassignment bị reject ổn định;
5. grouped `var` reassignment được phép;
6. comma form bị parser reject đúng chỗ;
7. bindings còn visible sau group và không có hidden scope;
8. implicit-local standalone behavior không regression;
9. test mới nằm trong active automated gate;
10. parser/semantic/strict-v2 tests liên quan đều pass;
11. full repository suite pass, không giảm test count hoặc nới expectation;
12. `python3 tools/sync_virc.py --check` pass;
13. self-host stage N và N+1 bit-identical;
14. `git diff --check` pass;
15. diff cuối chỉ chứa file in-scope và không ghi đè owner changes.

Nếu một gate chưa chạy hoặc đang blocked, kết luận `INCOMPLETE` và ghi rõ
command, blocker, phần đã xác minh và phần chưa xác minh. Không đổi FAIL/BLOCKED
thành PASS, không bỏ test, không giảm assertion, không sửa expected output để
che lỗi.

## Báo cáo cuối bắt buộc

Báo cáo cuối phải gồm:

1. root cause chính xác ở parser, AST/scope và semantic;
2. danh sách file/symbol đã sửa;
3. declaration representation cuối cùng và lý do nó không tạo scope;
4. bảng baseline trước/sau cho newline `var`, newline `let`, semicolon `let`,
   comma negative và standalone `let` control;
5. test/contract IDs mới và bằng chứng chúng nằm trong active gate;
6. command cùng kết quả của targeted tests, full suite, sync và bootstrap;
7. SHA-256/fixed-point evidence;
8. mọi giới hạn hoặc blocker còn lại;
9. `git status --short` cuối.

Không tuyên bố “đã hỗ trợ grouped declarations” nếu chỉ parse được binding đầu,
nếu later members trở thành implicit assignments, nếu `let` vẫn mutable, nếu
bindings bị scope ẩn, hoặc nếu test mới không được CI/full suite chạy.
