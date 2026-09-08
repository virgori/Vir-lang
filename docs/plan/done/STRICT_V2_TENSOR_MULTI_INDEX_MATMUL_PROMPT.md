# Prompt nghiêm ngặt: hoàn thiện tensor v2.0 — multi-index và `**`

## Vai trò và mục tiêu

Bạn là compiler engineer của Vir. Hãy làm cho compiler thực thi đúng, end-to-end, phần Tensor trong **Vir Spec v2.0**. Không được hạ cú pháp test để né khiếm khuyết compiler.

Nguồn sự thật theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md`, §26.1–§26.2.
2. `docs/ai-spec/vir-lang/references/syntax.md` và `types.md`.
3. Mã compiler trong `stdlib/vir/compiler/`.

Yêu cầu cụ thể:

```vir
var a: tensor<i32>[2, 2] = [1, 2, 3, 4]
var b: tensor<i32>[2, 2] = [5, 6, 7, 8]
var c = a ** b

if c[0, 0] != 19 do out false end
```

Phải parse, type-check và codegen được. `tensor<T>[S...]` là tensor built-in; `**` là matrix multiplication. Truy cập tensor chuẩn là multi-index `value[i, j, ...]`, không phải chỉ indexing phẳng.

## Trạng thái lỗi đã tái hiện

`tests/vri/test_tensor_ml_ops.vri` đã có test v2.0 ở `test_native_matmul`. Chạy:

```sh
./bin/virc tests/vri/test_tensor_ml_ops.vri -o /private/tmp/test_tensor_ml_ops_v2
```

Hiện parser dừng với:

```text
expected ']' after index
```

ở `c[1, 1]`. Đây là compiler non-conformance: **không** sửa test thành `c[flat_index]`, không thay `**` bằng `tensor_matmul(a, b)`, và không biến tensor built-in thành `entity Tensor` của thư viện legacy.

## Phạm vi bắt buộc

1. Đọc toàn bộ logic lexer/parser cho indexing, AST expression, semantic tensor typing, MIR/LIR lowering và codegen của `MatMul` trước khi sửa.
2. Parser phải nhận một danh sách biểu thức phân tách bằng dấu phẩy trong `[...]` của expression indexing:
   - đọc: `a[i]`, `a[i, j]`, `a[i, j, k]`;
   - ghi: `a[i, j] = value`;
   - biểu thức chỉ số không hằng: `a[row + 1, col]`.
3. AST phải giữ **đủ danh sách index theo đúng thứ tự**. Không được bỏ index sau phần tử đầu, không mã hoá riêng rank-2, và không flatten trong parser.
4. Semantic analysis phải xác thực index trên tensor built-in:
   - số index bằng rank tensor;
   - từng index là integer hợp lệ;
   - shape tensor là dữ kiện kiểu compile-time;
   - index/shape sai phải có diagnostic rõ ràng, không panic hoặc sinh AST partial rồi tiếp tục codegen.
5. `a ** b` phải được giữ là `MatMulOp` với quy tắc kiểu spec:

   ```text
   tensor<T>[M, K] ** tensor<T>[K, N] -> tensor<T>[M, N]
   ```

   Kiểm tra rank là 2, element type tương thích và inner dimension bằng nhau. Sai shape là lỗi compile-time.
6. Lowering/codegen phải nhận đầy đủ metadata shape/stride cần thiết để multi-index và output của `**` hoạt động. Không thêm ABI đặc biệt chỉ cho matrix 2×2 và không thay `**` bằng gọi wrapper `stdlib/vir/math/tensor.vri`.
7. Giữ `entity Tensor`/`TensorArena` trong `stdlib/vir/math/tensor.vri` là API thư viện độc lập. Đừng đổi representation, ABI, hoặc public API này trong task này trừ khi có bằng chứng trực tiếp rằng compiler đang dùng nó cho built-in tensor.

## Ma trận target bắt buộc

`**`, multi-index, tensor storage/layout và codegen không được chỉ đúng trên
host. Chốt từ `virc --help`, parser `--target` và `target_triple.vri` mọi
target công khai trước khi sửa. Với tree hiện tại, tối thiểu phải triển khai
và kiểm chứng đầy đủ `macos-arm64`, `linux-arm64`, `linux-x86_64`,
`linux-riscv64` và `wasm32-wasi-p1`; target mới mà driver nhận cũng bắt buộc
vào ma trận.

Mỗi backend phải lower built-in `tensor<T>[M,K] ** tensor<T>[K,N]` thật, giữ
shape/stride/index metadata đúng, sinh artifact đúng format/ABI, và chạy test
runtime có assertion. Chạy macOS ARM64 native; Linux bằng native
runner/container hoặc QEMU theo architecture; Wasm bằng WASI runtime thật.
Cross-compile, object inspection, interpreter fallback, hoặc chỉ thêm target
metadata không chứng minh target support. Không có runner/CI runnable cho một
target nghĩa là task **blocked/incomplete**, không phải lý do để hạ scope về
host.

## Cấm tuyệt đối

- Không sửa spec, tài liệu spec, hoặc test để tránh multi-index / `**`.
- Không đổi `a[i, j]` thành `a[i]`, không tự flatten chỉ tại test, và không chỉ hỗ trợ literal index.
- Không chấp nhận `a[i, j]` rồi âm thầm bỏ `j`.
- Không để parser recovery sinh AST một phần rồi bỏ semantic analysis cho source hợp lệ.
- Không thêm fallback runtime panic cho shape sai mà spec yêu cầu lỗi kiểu lúc compile.
- Không dùng cú pháp Rust/C/Python để thay thế cú pháp Vir.
- Không reset, checkout, restore, hoặc commit các thay đổi không thuộc task. Worktree đang có thay đổi của người dùng.

## Test bắt buộc

Thêm hoặc cập nhật test tự động ở vị trí phù hợp, tối thiểu bao phủ:

1. Parse/AST: rank 1, 2 và 3; cả read lẫn write; AST lưu chính xác mọi index expression.
2. Parser negative: `a[i,]`, `a[,j]`, thiếu `]`, và dạng chỉ số lỗi phải có diagnostic xác định.
3. Semantic negative: sai số index, index không-integer, và `tensor<T>[M,K] ** tensor<T>[P,N]` với `K != P`.
4. End-to-end bắt buộc trên **mỗi target trong ma trận**: `tensor<i32>[2,2]`
   với `a ** b`, đọc `c[0,0]`, `c[0,1]`, `c[1,0]`, `c[1,1]`, và kiểm tra kết
   quả `19, 22, 43, 50`. Test phải biên dịch ra artifact target bằng target
   flag thật, **chạy artifact đó** qua native runner/QEMU/WASI runner, và xác
   nhận exact stdout PASS cùng exit code `0`; mỗi giá trị sai phải cho một exit
   code lỗi phân biệt. Không dùng AST dump, MIR dump, object inspection, hoặc
   compile-success để thay thế runtime assertion.
5. End-to-end rectangular trên mỗi target: `tensor<i32>[2,3] **
   tensor<i32>[3,2]`, assert `58, 64, 139, 154` (không chỉ print) và exit
   code `0`. Đây bắt lỗi implementation hard-code 2×2.
5. Regression: `tests/vri/test_tensor_ml_ops.vri` parse/type-check không còn báo `expected ']' after index`; các test tensor hiện có vẫn không regress.

Ưu tiên tái sử dụng fixture đã có như `tests/test_first_class_matmul_rect.vri`, `tests/test_first_class_tensor.vri`, `tests/test_tensor_access.vri`, và `tests/vri/test_tensor_matmul.vri`; chuẩn hoá các fixture đó nếu chúng dùng `end` thay vì `end.` cho `func`.

## Cách làm và tiêu chí hoàn thành

1. Trước khi sửa, ghi ngắn gọn luồng token → AST → semantic → MIR/LIR → codegen đang xử lý `[` `,` `]` và `**`.
2. Sửa nhỏ nhất nhưng hoàn chỉnh, giữ API/ABI ngoài phạm vi không đổi.
3. Chạy các test mới, test parser liên quan, và lệnh compile regression ở trên
   trên **mọi target trong ma trận**. Phải chạy artifact sinh trực tiếp bởi
   compiler đang sửa, capture stdout/stderr và exit code. Chỉ PASS khi stdout
   khớp marker test và exit code là `0`; artifact crash, bị kill, không in
   marker, chỉ compile thành công, hoặc không có runner là FAIL/blocked.
4. Dùng `git diff --check` và chỉ stage các file của task.
5. Commit nguyên tử với message rõ nghĩa, ví dụ: `support spec tensor multi-index and matmul`.
6. Kết quả cuối phải báo:
   - các file đã sửa/thêm;
   - các lệnh kiểm chứng và kết quả thực tế;
   - hành vi semantic và diagnostic mới;
   - mọi blocker còn lại, nếu có.

## Cổng nghiệm thu end-to-end — không ngoại lệ

Không được tuyên bố hoàn thành dựa trên parse, type-check, MIR/LIR dump,
`otool`/`readelf`, Wasm validation, hoặc executable được tạo ra. Bằng chứng
bắt buộc là **hai lần chạy reproducible trên mọi target** của artifact mới
sinh, có command đầy đủ, exact stdout/stderr và exit code `0`, trong đó mọi
assertion matrix thực sự được thực thi. Nếu bất kỳ môi trường target nào không
cho chạy artifact, ghi task là **blocked/incomplete**; không thay thế bằng
smoke compile, không bỏ assertion, và không hard-code output PASS.

Không tuyên bố hoàn thành nếu source hợp lệ ở trên vẫn tạo AST partial, bypass
semantic analysis, không codegen được, hoặc không vượt cổng nghiệm thu này.
