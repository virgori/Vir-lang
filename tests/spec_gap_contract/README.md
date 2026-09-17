# Vir Spec Gap Contract Suite

Đây là bộ test chuẩn cho các tính năng Spec v2.0 đang thiếu, partial hoặc no-op.
Bộ test này cố ý chưa nối vào `run_tests.sh` của release 3.2.0.

## Quy tắc bất biến

1. Implementation phải sửa để pass test; không sửa expected output cho khớp code.
2. Không thay fixture positive thành compile-only nếu spec yêu cầu runtime semantics.
3. Không thay intrinsic thiếu bằng NOP/pass-through rồi công bố hoàn thành.
4. Không xóa negative test hoặc làm diagnostic trả exit code 0.
5. Mỗi feature phải có mutation proof: cố tình bỏ semantics thì test phải fail.
6. Không dùng JSON/XML làm điều kiện cho suite này.
7. Không nối suite vào release gate cho đến khi từng nhóm được owner bật rõ ràng.

## Manifest

`manifest.tsv` là danh mục canonical:

```text
id<TAB>kind<TAB>fixture<TAB>oracle
```

Các loại test:

- `run`: compile thành artifact, chạy, exit `0`, stdout phải khớp `EXPECT`.
- `compile_fail`: compiler phải trả non-zero và diagnostic chứa oracle.
- `run_fail`: compile phải thành công nhưng artifact phải trap/thoát non-zero ở
  runtime; compiler không được constant-fold thành giá trị bão hòa hoặc raw bits.
- `structural`: ngoài runtime output còn phải kiểm tra artifact/MIR theo oracle.
- `blocked_contract`: chưa được phép code vì spec/build interface chưa đủ để tạo
  black-box test không phụ thuộc implementation.

## Chống pass giả

- Async test đặt mutation sau `await pass`; synchronous pass-through sẽ trả mã
  lỗi thay vì output đúng.
- Bundle test yêu cầu output là nội dung file, không phải đường dẫn file.
- Precomp structural test yêu cầu call compile-time biến mất khỏi artifact.
- Port test dùng bounded queue và FIFO observable.
- Generic test gọi cùng một function với hai type khác nhau.
- SIMD test kiểm cả swizzle read lẫn write-mask giữ nguyên lane không bị ghi.
- AI test không chấp nhận hard-code shape 2x2.

## Blocked contracts

Các mục sau phải được đóng hợp đồng quan sát trước khi thêm fixture runtime:

- `reactive`/`morph`: cần UI test backend hoặc hook đếm invalidation chuẩn.
- `expose`: spec nói chọn endpoint bằng build flag nhưng chưa định nghĩa flag và
  artifact ABI để test.
- autodiff tổng quát: spec chưa định nghĩa API đọc gradient công khai; không dùng
  raw offset nội bộ làm chuẩn ngôn ngữ.
- lựa chọn async executor: test harness cần một cách chính thức để link executor
  tuần tự mà không tạo runtime mặc định cho mọi binary.
- `@bind(asm)`: cần output/IR inspection contract chứng minh optimizer không sửa
  thân hàm.

## Edge-case coverage

Manifest còn khóa các biên dễ bị implementation giả qua mặt:

- precomp base case, recursion, division-zero, allocation và throw;
- generic nhiều type parameter, specialization isolation, sai arity;
- local sống qua nhiều yield, completed await, cancellation cleanup, select;
- Port bounded wraparound, empty receive, move-after-send và single winner;
- repeated read swizzle, alias rgba, width/lane invalid;
- bundle thiếu file/UTF-8 và isolate capability violations;
- FFI thiếu type/body và Wasm import section;
- INT4 số phần tử lẻ, bits động/sai, rectangular tensor shape;
- optimizer equivalence giữa O0–O3;
- target exit-code propagation và zero-overhead artifact.
- precedence/associativity, signed minimum/wrapping, binary64 arithmetic,
  numeric float printing, nearest-even rounding, truncation-toward-zero và
  conversion traps cho NaN/infinity/out-of-range.

AI triển khai không được tự giải quyết các mục blocked bằng API tự đặt rồi gọi đó
là chuẩn. Phải bổ sung quyết định thiết kế riêng trước.
