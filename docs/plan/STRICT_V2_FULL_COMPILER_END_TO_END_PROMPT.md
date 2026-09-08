# Prompt tổng nghiêm ngặt: hoàn thiện triệt để Vir v2.0 end-to-end

## 1. Vai trò và mục tiêu cuối cùng

Bạn là compiler, linker và runtime engineer của Vir. Hãy hoàn thiện **đồng thời
và triệt để** ba nhóm tính năng sau trên pipeline compiler đang active:

1. Toàn bộ AI/ML primitives theo Spec v2.0: `tensor<T>[S...]`, multi-index,
   matrix multiplication `**`, fused multiply-accumulate `><` (FMA, không phải
   “FWA”), `infer`, `train`/autodiff/`.backward()` và `quantize` INT8/INT4.
2. FFI `extern from`: import động thật, loader bind thật và gọi hàm ngoài thật.
3. String interpolation và toàn bộ literal values theo Spec v2.0.

Pipeline bắt buộc:

```text
source .vri
  -> lexer
  -> parser / AST
  -> semantic analysis
  -> AST-to-MIR / SSA
  -> LIR
  -> register allocation
  -> target codegen
  -> object/executable/module writer
  -> target loader/runtime
  -> observable result
```

Mục tiêu không phải là “compile được”, “có opcode”, “có section” hoặc “test
host pass”. Chỉ được tuyên bố hoàn thành khi **cả ba nhóm tính năng** vượt toàn
bộ checklist và cổng nghiệm thu cuối trên **mọi target công khai**.

Tài liệu này là prompt thực thi canonical duy nhất. Nó đã hợp nhất toàn bộ yêu
cầu của ba prompt cũ về tensor/matmul, FFI và interpolation/literal; không cần
đọc prompt khác để tìm điều kiện nghiệm thu. Ba prompt nguồn được lưu dưới
`docs/plan/done/` chỉ để truy vết lịch sử. Nếu tài liệu lịch sử khác prompt này,
áp dụng điều kiện **chặt hơn** trong prompt tổng này và Spec v2.0.

---

## 2. Nguồn sự thật

Theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md`, đặc biệt §4.3, §4.5 và §26.
2. `docs/vir_language_spec_v2.0_en.md` khi cần đối chiếu thuật ngữ.
3. `docs/ai-spec/vir-lang/references/syntax.md`.
4. `docs/ai-spec/vir-lang/references/types.md`.
5. `docs/ai-spec/vir-lang/references/functions.md`.
6. Pipeline active dưới `stdlib/vir/compiler/` và runtime liên quan.

Không sửa Spec để hợp thức hóa implementation. Không lấy hành vi legacy hoặc
khả năng parser hiện tại làm chuẩn nếu trái Spec v2.0.

### 2.1. Baseline, repro và dấu vết lịch sử bắt buộc

Trước khi sửa, chạy lại từng repro bằng compiler active và ghi raw command,
stdout, stderr, exit code, SHA-256 compiler. Không dùng claim trong report hoặc
commit cũ làm bằng chứng hiện tại.

#### Interpolation/literal baseline

Repro chuẩn tối thiểu:

```vir
func main:
    var name = "Vir"
    var count = 42
    print("Hello $name")
    print("count=$count")
end.
```

Rà soát `lex_string` và chứng minh `$name` không còn đi qua pipeline như một
token `Str` duy nhất. Parser phải thực sự tạo `InterpExpr`; AST-to-MIR phải
lower từng segment/value; codegen không được xử lý `MIR_INTR_INTERP` như literal
tĩnh. `tests/test_interp.vri`, `tests/test_interp2.vri` và
`tests/test_interp3.vri` là regression inputs, nhưng chỉ runtime exact output
mới là bằng chứng E2E.

Phải đọc diff các commit lịch sử sau để lấy test/ý tưởng nhưng không tin claim
hoàn thành hoặc copy code stage-1 khi chưa chứng minh ABI tương thích:

- `8950d6066d8a850991d0f752d425f621a639d15f` — claim `$var`, `$(expr)`, `$$`,
  escape và runtime helpers nhưng chủ yếu sửa `virc_stage1.vri`/binary/docs,
  không phải pipeline active dưới `stdlib/vir/compiler/`.
- `5b00db79` — claim AST-to-MIR `InterpExpr` complete.
- `70c6b407` — claim semantic `InterpExpr` complete.
- `c654498f`, `2d4a6a65` — claim compiler/spec/test pass rộng hơn.

Các commit trên là dấu vết điều tra, không thay thế test của artifact mới.

#### Tensor/matmul/FMA baseline

Repro lịch sử trong `tests/vri/test_tensor_ml_ops.vri` từng dừng ở
`c[1, 1]` với `expected ']' after index`. Luôn chạy lại fixture đó và các input
`tests/test_first_class_matmul_rect.vri`, `tests/test_first_class_tensor.vri`,
`tests/test_tensor_access.vri`, `tests/vri/test_tensor_matmul.vri`. Không đổi
multi-index thành flat-index và không đổi `**`/`><` thành wrapper thư viện.

#### FFI baseline

Repro macOS tối thiểu:

```vir
extern from os func getpid() -> int
extern from "/usr/lib/libSystem.B.dylib" func getuid() -> int

func main -> int:
    var pid = getpid()
    var uid = getuid()
    if pid <= 0 do out 21 end
    if uid < 0 do out 22 end
    print "PASS: ffi extern verified"
    out 0
end.
```

Chạy artifact do compiler đang sửa sinh trực tiếp; sau runtime mới dùng
`otool`/`nm`/`dyld_info` để kiểm `__stubs`, `__la_symbol_ptr`, undefined symbol,
dylib ordinal và bind mechanism. Metadata đúng nhưng call không chạy vẫn là
FAIL.

Cú pháp chuẩn phải được giữ nguyên, ví dụ:

```vir
func main:
    var name = "Vir"
    var count = 42
    print("Hello $name, count=$count")
    out 0
end.
```

```vir
func tensor_check -> int:
    var a: tensor<i32>[2, 2] = [1, 2, 3, 4]
    var b: tensor<i32>[2, 2] = [5, 6, 7, 8]
    var c = a ** b
    var fused = a >< b
    if c[0, 0] != 19 do out 11 end
    if fused[0, 0] != 19 do out 12 end
    out 0
end.
```

```vir
extern from os func getpid() -> int

func ffi_check -> int:
    var pid = getpid()
    if pid <= 0 do out 21 end
    out 0
end.
```

Không được thay `out` bằng `return`, không dùng `fn`, không thay `eif` bằng
`elif`, không dùng braces, không đổi `a ** b` thành wrapper thư viện và không
hạ `a >< b` thành phép nhân/cộng tách rời làm mất single-rounding của FMA.

---

## 3. Quy tắc làm việc bắt buộc

- Rà soát toàn bộ đường đi active trước khi sửa; không chỉ sửa
  `virc_stage1.vri`, bootstrap fixture, binary prebuilt hoặc tài liệu.
- Ghi lại root cause theo từng tầng pipeline cho từng nhóm tính năng.
- Chạy repro thật trên HEAD trước khi sửa và lưu command, stdout, stderr, exit
  code; không tin claim PASS/FAIL cũ.
- Giữ nguyên mọi thay đổi không thuộc task và mọi thay đổi của người dùng.
- Không reset, checkout, restore hoặc stage file ngoài phạm vi task.
- Không hạ syntax, test, target matrix hoặc assertion để né compiler defect.
- Không hard-code output PASS, expected tensor values, PID, chuỗi nội suy hoặc
  kết quả host import trong compiler/runtime.
- Không dùng interpreter fallback, local wrapper, syscall thay thế, C shim,
  `clang`/`ld` wrapper hoặc pre-generated binary để giả E2E.
- Toolchain ngoài chỉ được dùng như runner/assembler/linker khi prompt con cho
  phép rõ ràng. Riêng FFI, artifact chứng minh phải do `bin/virc` sinh trực
  tiếp với metadata loader/import hoàn chỉnh; không dùng linker ngoài để vá.
- Mỗi lỗi unsupported phải thành diagnostic rõ ràng và exit khác 0; không
  silently emit no-op, zero, empty function hoặc partial AST.
- Không đánh dấu `[x]` nếu chưa có bằng chứng runtime tương ứng.
- Nếu thiếu runner hoặc không chạy được một target, toàn nhiệm vụ là
  **blocked/incomplete**; không được ghi “100% ngoại trừ…”.

---

## 4. Khóa ma trận target công khai

Trước khi sửa, đối chiếu cả ba nguồn:

```sh
./bin/virc --help
```

- Parser option `--target` trong `stdlib/vir/compiler/virc.vri`.
- `stdlib/vir/compiler/target_triple.vri`.

Tối thiểu phải có đầy đủ:

- [ ] `macos-arm64`
- [ ] `linux-arm64`
- [ ] `linux-x86_64`
- [ ] `linux-riscv64`
- [ ] `wasm32-wasi-p1`

Nếu driver nhận thêm target, tự động thêm target đó vào mọi ma trận bên dưới.
Không được bỏ target khỏi CLI để làm cho checklist pass, trừ khi Spec/release
policy chính thức yêu cầu removal và người dùng phê duyệt rõ ràng.

Với mỗi target, ghi:

- target triple chính xác;
- artifact format;
- compiler SHA-256;
- runner/emulator/runtime và version;
- command build đầy đủ;
- command run đầy đủ;
- SHA-256 của artifact;
- stdout/stderr byte-exact;
- exit code;
- kết quả lượt 1 và lượt 2 từ hai output path sạch khác nhau.

---

## 5. Workstream A — String interpolation và literal values

### 5.1. Lexer, parser và AST

- [ ] Literal string không interpolation vẫn là literal tĩnh duy nhất.
- [ ] `$identifier` sinh đúng chuỗi segment literal/value xen kẽ.
- [ ] `$base.field` giữ đầy đủ member-access expression.
- [ ] Nhiều interpolation trong một chuỗi giữ đúng thứ tự trái sang phải.
- [ ] String và integer có thể xuất hiện trong **cùng một chuỗi**.
- [ ] Escape/dollar compatibility được tách khỏi syntax canonical của Spec.
- [ ] Chỉ coi `$(expr)` và `$$` là canonical nếu Spec hiện hành ghi nhận rõ;
      nếu giữ compatibility thì test và tài liệu phải gắn nhãn compatibility,
      không dùng chúng thay cho acceptance `$identifier`/`$base.field`.
- [ ] Mỗi segment/expression giữ source span chính xác.
- [ ] Malformed interpolation có diagnostic xác định, không partial AST.
- [ ] Không lưu toàn bộ source interpolation thành một literal duy nhất.

### 5.2. Semantic analysis

- [ ] Name resolution chạy trên mọi interpolation expression.
- [ ] Identifier không tồn tại có diagnostic đúng vị trí.
- [ ] Field không tồn tại có diagnostic đúng vị trí.
- [ ] Kiểu không có stringify contract bị từ chối rõ ràng.
- [ ] `true`/`false` có type `bool`, không bị đồng nhất với integer.
- [ ] `none` giữ null semantics riêng, không bị đồng nhất với integer zero.
- [ ] Float giữ chính xác IEEE-754 payload từ lexer đến codegen.
- [ ] Float lowering đọc đúng `float_val`/raw IEEE representation, tuyệt đối
      không đọc nhầm `int_val` hoặc biến mọi float thành `0.0`.
- [ ] List preserve toàn bộ phần tử và type-check nhất quán.
- [ ] Dict có AST/type `Dict`, preserve key/value expression và không giả dạng
      `EntityLiteral`.
- [ ] Dict hỗ trợ key string và key expression hợp lệ theo Spec; key/type sai
      có diagnostic.

### 5.3. MIR/LIR/runtime/backend

- [ ] Interpolation đánh giá value đúng thứ tự trái sang phải.
- [ ] Primitive formatting có semantic xác định, gồm ít nhất string, integer,
      bool, none và float nếu Spec yêu cầu.
- [ ] Kết quả interpolation là fat string hợp lệ `{ptr, len}`.
- [ ] Kết quả động immutable và cấp phát từ Arena đúng lifetime.
- [ ] Literal tĩnh không interpolation ở Static/read-only data, không gọi
      concat/format allocator.
- [ ] `MIR_INTR_INTERP` không alias thành string-pool literal.
- [ ] String-pool symbol/relocation đúng trên từng native backend.
- [ ] `str_cat`, integer/primitive formatting và print hoạt động thật trên mọi
      target, gồm WASI.
- [ ] Negative integer formatting đúng, gồm giá trị nhỏ nhất của integer có dấu.
- [ ] Unsupported interpolation/type phát diagnostic thay vì in pointer hoặc
      silently coerce.

### 5.4. Test bắt buộc

- [ ] Lexer/AST tests: literal-only, `$name`, `$this.name`, nhiều interpolation,
      malformed interpolation, source spans.
- [ ] Semantic negative tests: undeclared identifier, missing field,
      unsupported stringify type.
- [ ] E2E dùng ít nhất chuỗi `"Hello $name, count=$count"` và assert exact
      stdout, không tách thành hai print để né lỗi concat.
- [ ] E2E chứng minh evaluation order bằng expression có side effect quan sát được.
- [ ] E2E literal values bao phủ `42`, `3.14`, string, interpolation, `true`,
      `false`, `none`, list và dict.
- [ ] Regression chạy `tests/test_interp.vri`, `tests/test_interp2.vri` và
      `tests/test_interp3.vri`; compile-only hoặc pointer output không phải pass.
- [ ] Test float bao phủ `3.14`, `1e-300`, `5e-324`, `1e308` và ít nhất một
      phép arithmetic/comparison thật để bắt integer-payload lane giả.
- [ ] Test Static-vs-Arena chứng minh literal-only không cấp phát concat và
      interpolation có cấp phát động.
- [ ] Mọi test E2E chạy hai lần trên mọi target trong ma trận.

---

## 6. Workstream B — Toàn bộ AI/ML: tensor, `**`, `><`, `infer`, `train`, `quantize`

### 6.1. Parser và AST

- [ ] Parse read `a[i]`, `a[i, j]`, `a[i, j, k]`.
- [ ] Parse write `a[i, j] = value`.
- [ ] Parse index expression động như `a[row + 1, col]`.
- [ ] Parse `a >< b` thành `FmaOp` riêng, cùng precedence 22 và kết hợp trái như
      Spec §26.2; không alias sang `*`, `+`, `**` hoặc call thư viện.
- [ ] AST giữ `><` phân biệt với `**` và giữ đủ hai toán hạng theo đúng thứ tự.
- [ ] AST giữ danh sách index đầy đủ, đúng thứ tự và không flatten trong parser.
- [ ] Không hard-code rank 2 và không bỏ index sau phần tử đầu.
- [ ] Parser diagnostics xác định cho `a[i,]`, `a[,j]`, thiếu `]` và expression
      index lỗi.

### 6.2. Type system và semantic analysis

- [ ] `tensor<T>[S...]` là built-in tensor, độc lập với library `entity Tensor`.
- [ ] Shape/rank là metadata compile-time đầy đủ.
- [ ] Số index phải đúng rank.
- [ ] Mỗi index phải là integer hợp lệ.
- [ ] `tensor<T>[M,K] ** tensor<T>[K,N] -> tensor<T>[M,N]`.
- [ ] `tensor<T>[M,K] >< tensor<T>[K,N] -> tensor<T>[M,N]`; mỗi phần tử output
      là dot-product tích lũy bằng FMA single-rounding theo §26.2.
- [ ] Không dùng thanh ghi accumulator ngầm, giá trị cũ của destination hoặc
      tham số thứ ba không tồn tại trong AST; `a >< b` là biểu thức thuần,
      deterministic. Scalar `a >< b` phải bị từ chối cho tới khi Spec định
      nghĩa type rule scalar rõ ràng, không được đọc X2/RDX/stale stack làm `c`.
- [ ] Chỉ chấp nhận matmul rank 2 khi Spec yêu cầu rank 2.
- [ ] Element type hai toán hạng tương thích.
- [ ] Inner dimension `K` phải bằng nhau.
- [ ] FMA kiểm tra rank, element type và inner dimension chặt như matmul, với
      diagnostic nhận diện riêng đường `><` khi sai.
- [ ] Mọi lỗi rank/type/shape có diagnostic cụ thể, không chỉ thông báo chung
      “semantic pass failed”.

### 6.3. MIR/LIR/codegen

- [ ] MIR/LIR giữ shape, stride, rank và element type cần thiết.
- [ ] Multi-index address calculation đúng cho rank 1, 2, 3 và expression động.
- [ ] Read/write dùng cùng layout contract.
- [ ] Matmul implementation không hard-code 2×2.
- [ ] MIR và LIR có op FMA riêng, giữ shape/type metadata; không biến `><` thành
      `MUL` rồi `ADD`, không gọi stub ba tham số khi source chỉ có hai toán hạng.
- [ ] FMA implementation không hard-code 2×2 và không phụ thuộc giá trị thanh
      ghi/stack chưa khởi tạo.
- [ ] Rectangular 2×3 × 3×2 chạy đúng.
- [ ] Integer tensor arithmetic đúng overflow/width contract.
- [ ] Float tensor dùng instruction/representation float thật, không integer lane.
- [ ] Float FMA có một lần làm tròn trên target có primitive fused; target không
      có primitive tương đương phải dùng implementation software chứng minh
      cùng semantic hoặc báo unsupported khác 0 trong giai đoạn phát triển.
- [ ] ARM64 dùng FMADD/FMLA/primitive fused tương đương; x86_64 dùng FMA3/AVX
      tương đương; RISC-V dùng `fmadd.s`/`fmadd.d` khi feature contract cho phép;
      WASM phải giữ single-rounding bằng primitive/algorithm phù hợp, không giả
      `f32x4.mul` + `f32x4.add` là fused.
- [ ] Register allocation, stack spill và ABI không làm mất tensor metadata/value.
- [ ] Mọi backend public lower tensor/matmul thật; không emit no-op hoặc PASS giả.
- [ ] Library `stdlib/vir/math/tensor.vri` không bị đổi representation/API để
      che thiếu sót built-in tensor.
- [ ] `entity Tensor`/`TensorArena` của thư viện vẫn là API độc lập; chỉ đổi ABI
      của chúng khi có bằng chứng compiler built-in đang dùng trực tiếp và có
      migration/test rõ ràng.

### 6.4. Test bắt buộc

- [ ] Parse/AST positive cho rank 1, 2, 3; read, write và dynamic index.
- [ ] Parser negative đủ bốn nhóm lỗi index.
- [ ] Semantic negative: rank mismatch, non-integer index, element mismatch,
      inner-dimension mismatch.
- [ ] Parser/semantic positive và negative riêng cho `><`: precedence, AST op,
      scalar bị từ chối, rank khác 2, element type mismatch và K mismatch.
- [ ] E2E 2×2 assert lần lượt `19, 22, 43, 50`, mỗi lỗi có exit code riêng.
- [ ] E2E rectangular `tensor<i32>[2,3] ** tensor<i32>[3,2]` assert
      `58, 64, 139, 154`; không chỉ print các giá trị.
- [ ] E2E FMA `><` cho 2×2 và rectangular assert toàn bộ output tương ứng
      `19, 22, 43, 50` và `58, 64, 139, 154`, với exit code riêng từng ô.
- [ ] E2E FMA float có bộ dữ liệu adversarial nơi fused và `mul` rồi `add` cho
      bit pattern khác nhau; assert bit pattern fused để bắt lowering giả.
- [ ] Có fixture dùng index động để ngăn constant-fold/hard-code giả.
- [ ] Có mutation-sensitivity check: đổi một expected value phải làm test fail
      với exit khác 0, chứng minh assertion branch thực sự được codegen.
- [ ] Có mutation riêng cho `><`: đổi toán hạng, đổi expected và thay op bằng
      `**`/`*` phải làm ít nhất một oracle thất bại.
- [ ] `tests/vri/test_tensor_ml_ops.vri` không regress.
- [ ] Regression dùng cả `tests/test_first_class_matmul_rect.vri`,
      `tests/test_first_class_tensor.vri`, `tests/test_tensor_access.vri` và
      `tests/vri/test_tensor_matmul.vri`; fixture sai luật đóng `func` phải được
      chuẩn hóa thành `end.` chứ không hạ syntax tensor.
- [ ] Mọi E2E tensor chạy hai lần trên mọi target trong ma trận.

### 6.5. `infer` — forward-only, không gradient

- [ ] Parser tạo `InferBlock` chứa nguyên body và source spans; không hạ thành
      block thường hoặc marker no-op.
- [ ] Semantic context cấm `.backward()` trực tiếp lẫn gián tiếp trên mọi giá
      trị sinh trong `infer`; diagnostic chỉ đúng call-site.
- [ ] `infer` và `train` không thể lồng theo cả hai chiều; lỗi được bắt trước MIR.
- [ ] MIR/LIR mang mode forward-only qua toàn bộ body để tensor ops không tạo
      tape, gradient buffer hoặc lưu activation cho backward.
- [ ] Runtime chứng minh không cấp phát tape/gradient; không chỉ emit
      `MIR_INTR_INFER` rồi bỏ qua ở backend.
- [ ] Kết quả tensor/value thoát khỏi `infer` vẫn có lifetime và ownership hợp lệ,
      nhưng metadata “không gradient” được giữ để `.backward()` bên ngoài cũng
      bị từ chối như §26.3.

### 6.6. `train` — autodiff native và `.backward()`

- [ ] Parser/AST giữ `TrainBlock`, method call `.backward()` và toàn bộ graph
      expression; không rewrite thành library call không kiểm soát.
- [ ] Semantic context chỉ cho phép `.backward()` trên scalar loss/tensor có
      gradient được sinh trong `train`; cấm trên integer, string, quantized
      tensor và giá trị detached/infer.
- [ ] MIR/LIR có các op/tape events riêng cho watch, record operation, seed loss
      gradient, reverse traversal và gradient accumulation.
- [ ] Runtime cấp phát tape/activation/gradient từ lifetime riêng của `train`,
      không alias output tensor hoặc ghi đè forward values.
- [ ] Gradient rules native tối thiểu cho add, sub, mul, `**`, `><` và phép
      reduction tạo scalar loss; broadcasting/transpose phải đúng shape.
- [ ] `.backward()` thực sự duyệt graph theo thứ tự ngược và cộng gradient khi
      một tensor đi vào nhiều nhánh; không trả hằng, finite-difference trá hình
      hoặc gọi Python/library ngoài.
- [ ] Kết thúc `train` giải phóng tape/activation không còn sống nhưng giữ output
      và gradient được phép quan sát theo ownership contract.

### 6.7. `quantize` — compact INT8/INT4 và dequantize trong `infer`

- [ ] Cú pháp canonical `quantize(value, bits: N)` parse đầy đủ positional value
      và named argument `bits`; không chấp nhận dạng unary làm rơi `bits`.
- [ ] `bits` là hằng compile-time thuộc `{4, 8, 16, 32}`; thiếu/sai/động có
      diagnostic rõ ràng. Input chỉ là tensor `f32`/`f16` hợp lệ.
- [ ] Type/IR giữ storage type, logical element type, shape, scale, zero-point,
      packing order và bit width; quantized tensor là type state riêng.
- [ ] INT8 dùng đúng 1 byte/phần tử; INT4 đóng gói hai phần tử mỗi byte với thứ
      tự nibble xác định. Allocation thực tế phản ánh mức giảm RAM trong §26.5.
- [ ] Scale/zero-point được tính deterministic với quy tắc rounding, saturation,
      NaN/Inf và tensor toàn zero được định nghĩa/test rõ ràng.
- [ ] `bits: 16` lưu f16 thật và `bits: 32` giữ f32; không gắn nhãn mới lên cùng
      buffer 8-byte hiện tại.
- [ ] Khi dùng trong `infer`, backend sinh dequantize/vector dot phù hợp và kết
      quả nằm trong tolerance/bit contract; ngoài `infer`, hành vi unsupported
      phải báo lỗi thay vì silently dùng raw packed bytes như f32.
- [ ] INT4 target không có capability native phải dùng fallback đúng semantic
      hoặc diagnostic khác 0; không claim giảm RAM/tăng tốc nếu vẫn lưu i64/f32.

### 6.8. Test AI/ML bắt buộc ngoài tensor arithmetic

- [ ] AST/semantic positive và negative riêng cho `infer`, `train`, nested mode,
      `.backward()` và đủ bốn mức quantize.
- [ ] E2E infer kiểm output forward đúng và bộ đếm/allocation audit chứng minh
      tape/gradient bằng 0.
- [ ] E2E train dùng graph nhiều nhánh với gradient oracle giải tích, kiểm từng
      phần tử gradient và mutation expected phải fail.
- [ ] E2E quantize kiểm raw byte size/content INT8, raw nibble content INT4,
      scale/zero-point, saturation và dequantized inference result.
- [ ] Có adversarial test phân biệt buffer compact thật với tensor i64/f32 giả.
- [ ] Mọi test `infer`, `train`, `quantize` chạy hai lượt sạch trên mọi target
      public; capability thiếu phải làm toàn cổng incomplete, không được bỏ ô.

---

## 7. Workstream C — FFI `extern from` thật trên mọi target

### 7.1. Frontend và registry target-neutral

- [ ] Hỗ trợ `extern func symbol(...) -> T` như compatibility của
      `extern from os`.
- [ ] Hỗ trợ `extern from os func symbol(...) -> T`.
- [ ] Hỗ trợ source/library path rõ ràng theo target.
- [ ] Hỗ trợ absolute provider path như
      `extern from "/usr/lib/libSystem.B.dylib" func symbol() -> int` mà không
      làm mất provider khi lưu AST/registry.
- [ ] Parser giữ signature, ABI và source provider đầy đủ.
- [ ] AST-to-MIR không tạo empty local body cho extern.
- [ ] Import registry target-neutral và chỉ đánh dấu import thực sự được gọi.
- [ ] Unused extern không sinh stub/binding/import.
- [ ] Arity/type/ABI mismatch có diagnostic trước codegen khi có thể.

### 7.2. Mach-O ARM64

- [ ] Emit callable stub/thunk đúng ABI.
- [ ] Emit `__stubs`, `__la_symbol_ptr`, indirect symbols và undefined `nlist`.
- [ ] Emit cơ chế dyld bind nhất quán (`LC_DYLD_INFO_ONLY` hoặc chained fixups
      hợp lệ, không claim sai cơ chế).
- [ ] Emit đúng dylib ordinal và `LC_LOAD_DYLIB` cho mọi source distinct.
- [ ] Chọn đúng một bind mechanism nhất quán: `LC_DYLD_INFO_ONLY` với bind
      stream hợp lệ hoặc `LC_DYLD_CHAINED_FIXUPS` hoàn chỉnh; không ghi report
      “chained fixups” nếu artifact không phát command/format đó.
- [ ] Section offsets, VM addresses, entrypoint, code signing và return ABI đúng.
- [ ] Gọi thật ít nhất hai symbol, ví dụ `getpid()` và `getuid()`; không chỉ
      khai báo symbol thứ hai.

### 7.3. Linux ARM64, x86_64 và RISC-V 64

- [ ] ELF có dynamic symbol table thật.
- [ ] ELF có relocation và PLT/GOT hoặc cơ chế ABI tương đương đúng architecture.
- [ ] ELF có `DT_NEEDED`/dynamic loader metadata đúng provider.
- [ ] Call/return convention đúng cho từng architecture.
- [ ] Artifact do `bin/virc` sinh trực tiếp và loader target bind thành công.
- [ ] Không thay extern bằng raw syscall, local function hoặc constant.

### 7.4. WASI Preview 1

- [ ] Wasm import section chứa module/name/signature đúng.
- [ ] Call index và ABI/memory contract đúng.
- [ ] Dùng host import thật phù hợp WASI, ví dụ API clock/random/I/O có thể xác
      thực; không giả định `getpid` tồn tại trong WASI.
- [ ] Runtime WASI thật instantiate module, bind import và thực thi call.
- [ ] Không dùng local replacement có cùng tên để giả host import.

### 7.5. Test bắt buộc

- [ ] macOS ARM64: gọi thật `getpid()` và `getuid()`, kiểm cả hai kết quả.
- [ ] Mỗi Linux target: gọi ít nhất hai libc/OS imports thật, kiểm kết quả runtime.
- [ ] WASI: gọi ít nhất hai host imports hoặc hai đường import độc lập, kiểm
      result/memory side effect thật.
- [ ] Mỗi fixture trả exit khác 0 nếu extern result không hợp lệ.
- [ ] PASS marker chỉ được in sau mọi assertion.
- [ ] Test nhiều import bắt lỗi dylib ordinal/indirect-symbol/import-index.
- [ ] Test local call regression.
- [ ] Test unused extern không sinh import metadata.
- [ ] Inspection bằng `otool`, `nm`, `dyld_info`, `readelf`, `objdump` hoặc Wasm
      parser khớp implementation; inspection chỉ là bằng chứng phụ.
- [ ] Mọi E2E FFI chạy hai lần từ output path sạch trên mọi target.

---

## 8. Integration test bắt buộc giữa cả ba workstream

Sau khi từng workstream pass riêng, thêm fixture tích hợp để ngăn ba đường code
chỉ hoạt động cô lập.

Mỗi target phải có một fixture tương đương thực hiện theo thứ tự runtime:

1. Gọi extern/host import thật và xác thực kết quả.
2. Tính built-in tensor 2×2 bằng `**`, tính lại bằng `><`, đọc cả hai bằng
   multi-index và xác nhận hai đường IR/backend độc lập đều đúng.
3. Nội suy kết quả FFI đã chuẩn hóa thành `1` cùng kết quả matmul và FMA vào
   **cùng một string**.
4. Chạy một `infer` forward-only trên tensor quantized và xác nhận không có tape;
   chạy một `train` graph nhỏ, gọi `.backward()` và xác nhận gradient oracle.
5. In chính xác:

```text
PASS: ffi=1 matmul=19 fma=19
```

5. Trả exit `0`; mỗi failure point có exit code khác nhau.

Checklist:

- [ ] Integration fixture không hard-code trực tiếp `ffi=1` hoặc `matmul=19`
      trong chuỗi output.
- [ ] `ffi=1` được suy ra sau call extern thật.
- [ ] `matmul=19` được đọc từ tensor result thật.
- [ ] `fma=19` được đọc từ kết quả `><` thật, không reuse kết quả `**`.
- [ ] Cả ba được stringify qua interpolation thật.
- [ ] Có negative/mutation run chứng minh thay expected tensor hoặc vô hiệu hóa
      extern result làm artifact trả khác 0.
- [ ] Có mutation vô hiệu hóa/làm sai riêng đường `><` làm artifact trả khác 0.
- [ ] `quantize` trong integration dùng storage compact thật; `infer` consume
      kết quả dequantize thật và audit không tạo gradient/tape.
- [ ] `.backward()` trong integration sinh gradient thật từ graph của `train`,
      không reuse expected/hằng số fixture.
- [ ] Chạy hai lần trên mọi target public.

---

## 9. Harness và chống false-positive

Viết hoặc mở rộng test harness tự động để:

- [ ] Luôn build artifact mới vào temporary directory duy nhất cho từng lượt.
- [ ] Xóa hoặc đổi tên binary cũ trước build để không thể reuse cache.
- [ ] Fail nếu compiler exit 0 nhưng không tạo artifact mới.
- [ ] Ghi SHA-256 artifact và xác nhận hai lượt có source/compiler giống nhau.
- [ ] Capture stdout và stderr riêng dưới dạng bytes.
- [ ] So exact stdout, exact expected stderr và exact exit code.
- [ ] Fail khi timeout, signal, crash, output thiếu hoặc có output thừa.
- [ ] Ghi architecture/OS/runtime version thực tế, không chỉ target flag.
- [ ] Chạy native macOS, Linux runner/QEMU/container và WASI runtime thật.
- [ ] Không coi compile-success, AST/MIR dump, object inspection hoặc Wasm
      validation là runtime PASS.
- [ ] Có test tamper/mutation để chứng minh assertion branches không bị backend
      bỏ qua.
- [ ] Lưu raw command/result cho từng target, workstream và lượt chạy.

Ma trận tối thiểu cần **60 lượt E2E riêng** trước integration:

```text
(interpolation/literals + tensor/matmul/FMA + infer + train + quantize + FFI)
6 feature groups × 5 targets × 2 fresh runs = 60 runs
```

Sau đó thêm tối thiểu:

```text
1 integrated fixture × 5 targets × 2 fresh runs = 10 runs
```

Negative tests, mutation runs và regressions không được tính vào **60** lượt
standalone tối thiểu trên; mọi tham chiếu lịch sử tới 40 lượt đều đã bị
supersede.

---

## 10. Rebuild self-host và kiểm tra regression

- [ ] Rebuild bằng `bash tools/promote_virc.sh --install` thành công.
- [ ] `bin/virc` sau promote là compiler dùng cho toàn bộ E2E matrix.
- [ ] Smoke test của promotion pass.
- [ ] Nếu project yêu cầu fixed-point, build stage kế tiếp và xác minh theo
      policy hiện hành; mọi non-determinism phải được giải thích.
- [ ] `./run_tests.sh` pass hoặc mọi failure được chứng minh là pre-existing,
      không liên quan và được báo rõ.
- [ ] `git diff --check` pass.
- [ ] Không có debug print, placeholder, silent fallback hoặc temporary test
      hack trong code production.
- [ ] Không regress local calls, branches, spills, runtime string, ELF/Mach-O,
      WASI hoặc target routing.

---

## 11. Commit và báo cáo bàn giao

Tạo commit nguyên tử, chỉ chứa file thuộc phạm vi. Có thể tách theo dependency:

1. frontend/semantic chung;
2. string/literal backend và tests;
3. tensor/matmul/FMA backend và tests;
4. FFI loader/import backends và tests;
5. harness + final integration report.

Không commit artifact tạm, log chứa đường dẫn nhạy cảm hoặc thay đổi người dùng.

Ba prompt lịch sử đã được hợp nhất và lưu tại:

```text
docs/plan/done/STRICT_V2_STRING_INTERPOLATION_AND_LITERAL_VALUES_PROMPT.md
docs/plan/done/STRICT_V2_TENSOR_MULTI_INDEX_MATMUL_PROMPT.md
docs/plan/done/STRICT_FFI_EXTERN_IMPORT_END_TO_END_PROMPT.md
```

Không cập nhật riêng ba file lịch sử để thay đổi scope. Mọi yêu cầu mới cho ba
workstream phải được thêm trực tiếp vào prompt tổng này để tránh divergence.

Báo cáo cuối bắt buộc tạo tại:

```text
docs/report/STRICT_V2_FULL_COMPILER_E2E_REPORT.md
```

Báo cáo phải có:

- [ ] HEAD/commit hashes thực tế.
- [ ] Danh sách file sửa/thêm theo workstream.
- [ ] Root cause theo pipeline cho cả ba nhóm, gồm riêng `><` từ token tới
      single-rounding backend.
- [ ] Hành vi semantic/diagnostic mới.
- [ ] Ma trận target đầy đủ, hai lượt mỗi ô.
- [ ] Raw build/run commands, stdout, stderr, exit code, checksums và versions.
- [ ] Kết quả negative, mutation và regression tests.
- [ ] Kết quả integrated fixture trên mọi target.
- [ ] Mọi limitation còn lại.

Không được dùng từ “100%”, “complete”, “done”, “production-ready” hoặc dấu ✅
nếu còn **bất kỳ** checkbox nào chưa có bằng chứng.

---

## 12. Cổng nghiệm thu cuối — không ngoại lệ

Chỉ được kết luận **HOÀN THÀNH 100% END-TO-END** khi đồng thời thỏa tất cả:

- [ ] Workstream A pass toàn bộ checklist.
- [ ] Workstream B pass toàn bộ checklist, gồm multi-index, `**`, `><`, `infer`,
      `train`/`.backward()` và `quantize` INT8/INT4.
- [ ] Workstream C pass toàn bộ checklist.
- [ ] Mỗi workstream chạy hai lần trên mọi target public.
- [ ] Integrated fixture chạy hai lần trên mọi target public.
- [ ] Mọi artifact được sinh mới bởi compiler vừa sửa.
- [ ] Mọi runtime assertion thực sự được thực thi và đã qua mutation check.
- [ ] Exact stdout/stderr và exit code đúng.
- [ ] Negative tests có diagnostic xác định.
- [ ] Full regression suite không regress.
- [ ] Self-host promotion pass.
- [ ] `git diff --check` pass.
- [ ] Commits sạch, task-scoped và report có đủ bằng chứng tái lập.
- [ ] Không còn blocker, unsupported public target hoặc silent fallback.

Nếu chỉ một ô chưa đạt, kết luận bắt buộc là:

```text
INCOMPLETE / BLOCKED — chưa đạt cổng nghiệm thu tổng.
```

Nêu chính xác checkbox chưa đạt, root cause, output thật và bước kỹ thuật kế
tiếp. Không hạ scope, không làm tròn phần trăm và không xin phép dừng khi vẫn
còn hành động an toàn, đúng phạm vi để tiếp tục sửa và kiểm thử.
