# Prompt nghiêm ngặt: làm sạch `%` khỏi modulo và hoàn thiện percent operator Vir v2.0

## 1. Vai trò và mục tiêu

Bạn là compiler, runtime và test engineer của Vir. Hãy đưa toán tử phần trăm
`%` của **Vir Spec v2.0** vào trạng thái đúng end-to-end, đồng thời làm sạch
mọi khai báo, ánh xạ, lowering, constant-folding, comment và fixture đang coi
`%` là modulo hoặc remainder.

Contract không được thương lượng:

```text
10%   = 0.1
10.5% = 0.105
7 mod 3 = 1
```

`%` là toán tử **phần trăm**. `mod` là toán tử **phần dư**. Hai toán tử phải có
token, AST, semantic, IR và test độc lập; không được dùng chung opcode modulo
hoặc chỉ đổi tên ở frontend.

Pipeline bắt buộc phải kiểm tra và sửa:

```text
source .vri
  -> lexer
  -> parser / AST
  -> semantic / type inference / type checking
  -> constant folding
  -> AST-to-HIR/MIR/SSA
  -> LIR
  -> register allocation
  -> target codegen
  -> executable/module writer
  -> runtime execution
```

Không được coi “lexer có token `%`”, “parser không crash”, “có `PercentOp`”
hoặc “compile thành công” là đã triển khai xong.

## 2. Nguồn sự thật

Theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md` §10.1 và §30.
2. `docs/vir_language_spec_v2.0_en.md` §10.1 và §30 để đối chiếu thuật ngữ.
3. `docs/ai-spec/vir-lang/references/syntax.md` và operator contract của skill
   `vir-lang`.
4. Pipeline active dưới `stdlib/vir/compiler/`, C-core dưới `core/src/`, và
   runtime/backend thật được release compiler sử dụng.

Ví dụ chuẩn `10% = 0.1` là yêu cầu observable. Không sửa Spec thành cú pháp
nhị phân `a % b` để hợp thức hóa parser hiện tại. Nếu bảng precedence/associativity
còn mô tả chưa đủ rõ cho postfix `%`, ghi nhận và làm rõ tài liệu mà không đổi
nghĩa phần trăm; tuyệt đối không dùng sự mơ hồ đó để giữ `%` là remainder.

## 3. Baseline lỗi đã biết — bắt buộc tái hiện trên HEAD

Trước khi sửa, tạo fixture tạm hoặc test chính thức bằng cú pháp Vir v2.0:

```vir
func main:
    var p1 = 10%
    var p2 = 10.5%
    print(p1)
    print(p2)
    out 0
end.
```

Chạy bằng ít nhất C-core đang active và `bin/virc` self-host hiện tại; lưu raw
command, SHA-256 compiler, stdout, stderr và exit code. Baseline từng quan sát
thấy cả `10%` lẫn `10.5%` dừng ở parser với `expected expression`; phải chạy
lại, không dùng ghi nhận này thay bằng chứng mới.

Tái hiện thêm các false-positive hiện có:

```vir
func main:
    print(10 % 50)
    print(105 % 50)
    print(7 mod 3)
    out 0
end.
```

Ghi rõ parser nào nhận cú pháp nhị phân `a % b`, pipeline nào hạ nó thành
modulo, pipeline nào hạ thành `(a * b) / 100`, và vì sao cả hai đều không chứng
minh cú pháp chuẩn `10.5%` hoạt động.

## 4. Điều tra và làm sạch bắt buộc

### 4.1. Kiểm kê toàn repository

Dùng `rg` rà soát tối thiểu các pattern và biến thể tương đương:

```text
TOK_PERCENT -> OP_MOD
TokType.Percent -> OpType.ModOp
PercentOp -> MirOp.Mod
PercentOp -> LirOp.Rem
T_PERCENT -> Q_MOD
case Percent: Mod
case OP_PERCENT: remainder
`%` (modulo/remainder)
x % y trong fixture tính phần dư
```

Rà soát:

- `core/src/`, `core/include/`, `core/bootstrap/`;
- `stdlib/vir/compiler/`;
- mọi stage/freeze/compiler source có thể tái sinh `bin/virc`;
- `tests/`, `core/tests/`, `stdlib/vir/test/`, bootstrap-codegen fixtures;
- formatter, LSP/syntax highlighting và tài liệu compiler-facing.

Phân loại từng hit là active, bootstrap, legacy, generated, negative test,
chuỗi hiển thị `%`, hay lỗi semantic thật. Source legacy/bootstrap có thể được
dùng để tái sinh compiler phải được sửa hoặc loại bỏ an toàn; không để mapping
sai tồn tại rồi tuyên bố “pipeline active đã đúng”. Không sửa chuỗi `%` dùng để
hiển thị phần trăm, percent-encoding, CSS/VSS hoặc nội dung không phải toán tử.

### 4.2. Các điểm lỗi đã biết phải xử lý

Không giới hạn rà soát ở danh sách này:

- `core/src/parser.c` đang parse `%` trong layer infix cùng `mod` và đòi toán
  hạng bên phải.
- `stdlib/vir/compiler/parser.vri` đang đưa `TokType.Percent` vào Pratt infix
  binding-power table; test parser hiện dùng `x % 50`.
- `stdlib/vir/compiler/ast_to_mir.vri` đang gộp `OpType.PercentOp` với
  `OpType.ModOp` thành `MirOp.Mod`, kể cả đường `eval_const_expr`.
- Các nguồn parser/bootstrap cũ có thể map `TOK_PERCENT` hoặc `T_PERCENT` trực
  tiếp sang modulo/remainder.
- C-core có nhánh biến `a % b` thành `(a * b) / 100`; đây vẫn là grammar nhị
  phân không được ví dụ chuẩn `10%` xác nhận và không giải quyết `10.5%`.
- Float ở một số pipeline đang bị cast/truncate sang integer hoặc chở raw
  IEEE-754 bits qua phép toán nguyên. Phải sửa dependency này đủ để
  `10.5% = 0.105` chạy thật; không được hạ acceptance xuống integer-only.

## 5. Grammar, AST và semantic bắt buộc

### 5.1. Lexer

- Tokenize `10%` thành numeric literal `10` và token percent, không thành
  modulo và không đòi token toán hạng phải ở bên phải.
- Tokenize `10.5%` với literal float giữ nguyên giá trị `10.5` và source span
  chính xác.
- `mod` tiếp tục là keyword/token remainder riêng.
- Không gộp `%` vào numeric lexeme nếu việc đó làm mất source location hoặc
  gây sai formatter/LSP; nếu chọn percent-literal token chuyên biệt, phải chứng
  minh AST/diagnostic và tooling vẫn giữ đầy đủ thông tin.

### 5.2. Parser và AST

- Parse `%` theo dạng hậu tố được Spec minh họa: `expr%`.
- AST percent chỉ có một operand và có node/op riêng; không tạo `BinOp` giả với
  RHS `100`, không tạo RHS mặc định và không alias `ModOp`.
- `mod` vẫn là infix binary remainder với hai operand.
- Dạng `a % b` không được silently hiểu là modulo. Nếu không có định nghĩa
  binary-percent canonical trong Spec, phát diagnostic rõ ràng hướng người
  dùng tới `a%` cho phần trăm hoặc `a mod b` cho phần dư.
- Precedence phải có test AST rõ ràng dựa trên §30, gồm tương tác với unary
  minus, `^`, `*`, `/`, `+`, `-`, parentheses và `mod`. Không đổi precedence
  operator khác để vá cục bộ `%`.

### 5.3. Type system

- Operand của `%` phải là kiểu số được Spec cho phép; string, entity, pointer,
  tensor không có contract percent phải bị từ chối tại source location.
- `10%` phải biểu diễn được `0.1`; không được integer-divide thành `0`.
- `10.5%` phải cho giá trị float `0.105` trong sai số floating-point được test
  định nghĩa chặt chẽ.
- Giữ type/value float xuyên suốt semantic và IR. Không cast `float_val` sang
  `int64`, không áp `Div`, `Mul`, `Mod` integer lên raw IEEE bits.
- Constant-folded và runtime-computed percent phải cùng type, cùng rounding
  contract và cùng kết quả trong tolerance.

## 6. IR, optimizer và codegen bắt buộc

- Dùng percent node/op semantic riêng ít nhất cho tới tầng có đủ type
  information để hạ đúng. Không map `PercentOp` sang `Mod`, `Rem`, `SRem`,
  `URem`, `%` host-language hoặc helper modulo.
- Hạ percent thành phép chia/nhân floating-point đúng kiểu, hoặc opcode/helper
  percent chuyên biệt có semantics tương đương `value / 100`. Không dùng phép
  chia nguyên cho operand integer.
- Constant folder phải fold `10%` thành `0.1` và `10.5%` thành `0.105`, không
  đọc nhầm `int_val`, không modulo 100, không round/truncate về integer.
- Optimizer không được biến percent trở lại remainder hoặc làm mất signedness,
  float width hay source diagnostic.
- Mọi backend public phải nhận được representation hợp lệ: macOS ARM64,
  Linux ARM64, Linux x86_64, Linux RISC-V 64 và Wasm/WASI, cộng mọi target mới
  mà `virc --help`/target parser công khai tại thời điểm thực hiện.
- Không dùng interpreter fallback, host-only C shim, hard-coded constant/output
  hoặc prebuilt binary để giả E2E.

## 7. Dọn test và bổ sung coverage

### 7.1. Sửa fixture sai

- Tìm mọi test dùng `%` để tính remainder và đổi source Vir sang `mod`.
- Đổi tên test/comment/expected IR từ percent/modulo nhập nhằng thành tên đúng.
- Fixture đang chỉ parse `x % 50` không được giữ làm positive canonical percent
  test. Chuyển nó thành negative grammar test hoặc thay bằng `10%`, `10.5%` và
  AST postfix assertions.
- Test chuỗi hiển thị `"%"`, percent-encoding và VSS/CSS unit không phải modulo
  không được sửa chỉ để thỏa một lệnh search thô.

### 7.2. Test tối thiểu bắt buộc

1. Lexer token/span:
   - `10%`;
   - `10.5%`;
   - `value%`;
   - `7 mod 3`;
   - malformed prefix `%10` và binary `10 % 3`.
2. Parser/AST:
   - percent postfix có đúng một child;
   - `mod` binary có đúng hai child;
   - precedence/parentheses với unary minus, power, multiply/divide và add/sub;
   - source location của `%` và operand.
3. Semantic:
   - integer literal percent cho kết quả không bị integer truncation;
   - float literal và float variable percent;
   - negative/zero/large values;
   - từ chối operand không phải số;
   - diagnostic hướng dẫn dùng `mod` cho remainder.
4. Constant folding:
   - `10% == 0.1`;
   - `10.5%` xấp xỉ `0.105`;
   - folded value khớp runtime-computed value;
   - `7 mod 3 == 1` vẫn đúng và dùng remainder IR.
5. IR assertions:
   - percent path không chứa `Mod`, `Rem`, `SRem` hoặc `URem`;
   - `mod` path có remainder opcode/helper;
   - float percent dùng float operation/typed helper, không integer lane.
6. Negative regression:
   - `10 % 3` không trả `1` như modulo;
   - `%10` không được chấp nhận như cú pháp hợp lệ;
   - không parser recovery thành partial AST rồi tiếp tục codegen.

### 7.3. E2E value test canonical

Tạo một test `.vri` thực sự kiểm tra giá trị, không chỉ in marker PASS:

```vir
func main:
    var p1 = 10%
    var p2 = 10.5%

    var d1 = p1 - 0.1
    if d1 < 0.0 do d1 = 0.0 - d1 end
    if d1 > 0.0000001 do out 11 end

    var d2 = p2 - 0.105
    if d2 < 0.0 do d2 = 0.0 - d2 end
    if d2 > 0.0000001 do out 12 end

    if 7 mod 3 != 1 do out 13 end
    out 0
end.
```

Nếu type inference yêu cầu annotation theo Spec, thêm annotation chuẩn nhưng
không thay expression `%` bằng `/ 100`, helper thư viện hoặc expected constant.
Test phải compile và chạy artifact mới sinh; exit code `0` là bắt buộc.

## 8. Ma trận thực thi và bằng chứng

Khóa danh sách target từ driver hiện tại trước khi sửa. Với mỗi target public:

1. Build/rebuild compiler từ source task, ghi SHA-256 và provenance.
2. Compile fixture canonical bằng target flag thật.
3. Chạy artifact bằng native runner, QEMU hoặc WASI runtime phù hợp.
4. Capture raw command, stdout, stderr và exit code.
5. Chạy tối thiểu hai lần để phát hiện phụ thuộc register state hoặc binary cũ.

Compile-only, object inspection, disassembly, Wasm validation hoặc unit test
helper không thay thế execution. Target không có runner là blocker thật: phải
bổ sung runner/CI hoặc báo task incomplete, không được tự hạ target matrix.

## 9. Cổng static-clean bắt buộc

Sau khi sửa, chạy lại inventory và chứng minh không còn code path nào coi `%`
là modulo/remainder. Tối thiểu phải không còn các mapping tương đương:

```text
Percent -> Mod
Percent -> Rem
TOK_PERCENT -> OP_MOD
PercentOp -> MirOp.Mod
PercentOp -> LirOp.Rem
T_PERCENT -> Q_MOD
```

Các hit còn lại chỉ được phép là:

- negative test chứng minh mapping đó bị cấm;
- tài liệu giải thích `%` không phải modulo;
- chuỗi hiển thị ký tự `%` hoặc domain khác như percent-encoding/VSS;
- generated artifact được tái sinh từ source đã sạch và được kiểm chứng.

Liệt kê từng exception trong báo cáo cuối; không dùng allowlist rộng che lỗi.

## 10. Cấm tuyệt đối

- Không dùng `%` làm remainder ở bất kỳ source Vir mới nào; dùng `mod`.
- Không giữ alias `% -> mod` vì compatibility mà không có mode legacy tách
  biệt và test chứng minh strict v2.0 không thấy alias đó.
- Không sửa test expected từ `0.105` thành raw IEEE bits, `0`, `10` hoặc `5`.
- Không đổi test `10.5%` thành `10.5 / 100.0`.
- Không chỉ sửa lexer/parser rồi để MIR/LIR vẫn dùng remainder.
- Không chỉ sửa self-host mà bỏ C-core/bootstrap có thể tái sinh compiler sai,
  hoặc ngược lại.
- Không hard-code literal `10`, `10.5`, `0.1`, `0.105` trong compiler/runtime.
- Không dùng binary prebuilt cũ làm bằng chứng sau khi source đã thay đổi.
- Không sửa Spec để hợp thức hóa grammar/semantics hiện tại.
- Không reset, checkout, restore, stage hoặc commit thay đổi ngoài task; giữ
  nguyên mọi thay đổi sẵn có của người dùng.

## 11. Quy trình thực hiện

1. Ghi baseline và root cause theo từng tầng pipeline.
2. Lập inventory `%`/`mod`, phân loại từng hit trước khi sửa hàng loạt.
3. Sửa grammar/AST/type contract trước, sau đó lowering/optimizer/backend.
4. Dọn bootstrap/legacy sources và fixture có nguy cơ tái sinh mapping sai.
5. Thêm lexer, parser, semantic, IR, negative và E2E tests.
6. Rebuild compiler; không dùng binary cũ.
7. Chạy static-clean gate, regression suite và E2E hai lần trên mọi target.
8. Chạy `git diff --check`; rà soát diff chỉ chứa file thuộc task.
9. Chỉ stage file task và tạo một commit nguyên tử nếu workflow hiện tại yêu
   cầu commit, ví dụ `implement strict v2 percent operator`.

## 12. Báo cáo bàn giao bắt buộc

Báo cáo cuối phải có:

- root cause tại lexer/parser, AST/semantic, const-fold, MIR/LIR và codegen;
- danh sách file sửa/thêm/xóa;
- danh sách mọi mapping `% -> modulo` đã loại bỏ;
- danh sách hit `%` còn lại và lý do hợp lệ;
- grammar/type/rounding contract cuối cùng của percent;
- raw command, compiler hash, target, runner, stdout, stderr, exit code cho mỗi
  E2E run;
- kết quả test mới và regression suite;
- mọi blocker hoặc target chưa chạy được.

Không tuyên bố hoàn thành nếu một trong các điều sau còn đúng:

- `10%` hoặc `10.5%` vẫn lỗi parser;
- `10%` thành `0`, `10.5%` khác `0.105` ngoài tolerance;
- percent AST vẫn là binary modulo hoặc có RHS giả;
- bất kỳ active/bootstrap path nào còn `Percent -> Mod/Rem`;
- float vẫn bị truncate hoặc xử lý như raw integer bits;
- fixture vẫn dùng `%` để kiểm remainder;
- chỉ có compile/IR inspection mà chưa chạy artifact mới trên toàn target
  matrix;
- `7 mod 3` không còn bằng `1`.

