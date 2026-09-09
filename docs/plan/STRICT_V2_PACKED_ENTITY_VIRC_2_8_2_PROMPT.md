# Prompt nghiêm ngặt: triển khai `packed entity` cho virc 2.8.2

## 1. Vai trò, phạm vi và kết quả bắt buộc

Bạn là compiler, ABI, runtime và test engineer của Vir. Hãy hoàn thiện
`packed entity` theo Vir Spec v2.0 §4.4 và §7.3 trên pipeline self-host phát
hành dưới tên **virc 2.8.2**.

Phạm vi duy nhất của task này là compiler Vir đang active:

```text
source .vri
  -> stdlib/vir/compiler/lexer.vri
  -> parser / AST
  -> semantic passes
  -> layout metadata
  -> AST-to-MIR / SSA
  -> LIR / register allocation
  -> target codegen / linker
  -> executable hoặc Wasm phát hành bởi bin/virc
```

`core/src/`, C-core, C parser, C lexer và C lowering là lịch sử, nằm ngoài
phạm vi. Không sửa chúng, không dùng chúng làm acceptance gate và không trì
hoãn implementation vì khác biệt với C-core.

Contract không được thương lượng:

```text
packed entity Wire:
    a: u8
    b: u16
    c: u32
end.

offset(a) = 0
offset(b) = 1
offset(c) = 3
sizeof(Wire) = 7
alignment(Wire) = 1
```

Không được coi việc lexer nhận `packed`, parser tạo `PackedDef`, field access
round-trip đúng, hoặc chương trình compile thành công là đã hoàn tất. Byte
layout observable phải đúng.

## 2. Nguồn sự thật

Theo thứ tự ưu tiên:

1. `docs/vir_language_spec_v2.0_vi.md` §4.4 và §7.3.
2. `docs/vir_language_spec_v2.0_en.md` các mục tương ứng.
3. `docs/ai-spec/vir-lang/references/types.md` và `syntax.md`.
4. Pipeline self-host active dưới `stdlib/vir/compiler/`.
5. Các test strict được liệt kê trong prompt này.

Spec yêu cầu:

- cú pháp canonical là `packed entity Name: ... end.`;
- mọi packed field phải có type annotation;
- field nằm liên tiếp, không padding;
- field access dùng byte offset;
- alignment của packed entity là 1;
- `sizeof(PackedType)` là hằng compile-time bằng tổng kích thước field;
- packed entity giữ move semantics của entity.

Không sửa Spec hoặc expected test để hợp thức hóa layout 8-byte-slot hiện tại.

## 3. Baseline lỗi phải tái hiện trên HEAD

Trước khi sửa, ghi commit/ref, `./bin/virc --help`, SHA-256 của `bin/virc`, raw
command, stdout, stderr và exit code cho các fixture mới dưới
`tests/strict_v2/packed_*`.

Baseline đã quan sát, nhưng phải chạy lại:

- lexer/parser self-host nhận `packed entity` và tạo `AstType.PackedDef`;
- semantic cho phép packed field không có annotation;
- aggregate allocation dùng `n * 8`;
- constructor ghi field tại `i * 8`;
- field read/write dùng `field_index * 8`;
- `u8, u16, u32` có byte offsets thực tế `0, 8, 16`, không phải `0, 1, 3`;
- test mang tên `tests/vri/test_packed.vri` chỉ dùng `entity`, nên không chứng
  minh packed layout;
- `sizeof(Type)` chưa hoạt động end-to-end.

Không dùng binary được build trước source change làm bằng chứng sau khi sửa.

## 4. Grammar và AST

### 4.1. Cú pháp canonical

Chỉ nhận declaration:

```vir
packed entity Name:
    field: FixedLayoutType
end.
```

- `packed Name:` là shorthand ngoài Spec và phải bị từ chối trong strict v2.
- `packed record Name:` không được tự thêm làm alias nếu Spec không định nghĩa.
- `packed` không được parser recovery thành identifier rồi bỏ qua modifier.
- AST declaration phải giữ `PackedDef` riêng; không rewrite sớm thành
  `EntityDef` làm mất layout kind.
- Source span của `packed`, entity name và từng field/type phải được giữ để
  diagnostic trỏ đúng vị trí.

### 4.2. Field và method

- Mọi non-method child là đúng một field có name và declared type.
- Method không phải field, không tăng field count, offset hay `sizeof`.
- Duplicate field name là compile error.
- Field order trong layout là declaration order, không phải constructor order.
- Constructor named initializer phải map bằng field identity; không ghi theo
  thứ tự argument source.
- Constructor phải có đúng một initializer cho mỗi field. Missing, duplicate
  và unknown initializer đều là compile error, không để byte chưa khởi tạo.

## 5. Layout contract của virc 2.8.2

Tạo một layout representation duy nhất dùng chung cho semantic, lowering,
`sizeof`, field access, mutation, optimizer và backend. Metadata tối thiểu:

```text
EntityLayout
  kind: normal | packed
  alignment
  total_size
  fields[]:
    name
    declared_type
    byte_offset
    byte_size
    signedness / load-extension rule
    nested layout identity nếu có
```

Không giữ hai phép tính offset độc lập giữa semantic và AST-to-MIR.

### 5.1. Kích thước primitive

Cho layout packed:

```text
i8/u8       1 byte
i16/u16     2 bytes
i32/u32     4 bytes
i64/u64     8 bytes
bool        1 byte, representation 0 hoặc 1
float       8 bytes theo Vir Spec v2.0
int/uint    target word size
ptr         target pointer size
```

Các alias compatibility như `f32`/`f64` chỉ được dùng nếu type system public
của virc 2.8.2 đã định nghĩa rõ kích thước; không đoán từ host compiler.

Offset packed được tính tuần tự:

```text
offset(field[0]) = 0
offset(field[i]) = offset(field[i-1]) + sizeof(field[i-1])
sizeof(T)        = sum(sizeof(field[i]))
alignment(T)     = 1
```

Không round offset hoặc total size lên 2, 4, 8, pointer size hay cache line.

### 5.2. Type hợp lệ

Packed field phải có compile-time fixed layout. Cho phép:

- các primitive có kích thước xác định ở trên;
- packed entity khác đã resolve đầy đủ;
- `ptr` như một scalar ABI field.

Từ chối trực tiếp:

- `string`, dynamic array/list, dict, tensor/deck hoặc type move/dynamic không
  có inline fixed-size contract;
- normal `entity` inline trong packed entity;
- unknown/unresolved type;
- direct hoặc indirect-by-value recursive packed layout;
- layout size overflow hoặc field count vượt giới hạn compiler.

Đệ quy qua `ptr` không phải inline recursion và được phép nếu các rule ownership
hiện hành cho phép.

### 5.3. Endianness

Packing không tự byte-swap. Scalar được lưu theo native target endianness.
Binary protocol yêu cầu network order phải dùng conversion explicit. Test raw
byte E2E chỉ chạy trên target little-endian tương ứng hoặc có expected riêng
cho target endian; không hard-code little-endian vào semantic layout engine.

## 6. Semantic và diagnostics

- `PackedDef` phải được thu thập, resolve và type-check như một named entity
  nhưng mang layout kind riêng tới backend.
- Thiếu field annotation phải dừng ở semantic trước MIR lowering.
- Tính nested layouts theo dependency graph; hỗ trợ forward declaration/order
  độc lập khi type tồn tại trong cùng module.
- Phát hiện cycle bằng trạng thái unvisited/visiting/done và diagnostic có
  đường cycle, không recursion vô hạn hoặc stack overflow.
- Kiểm tra integer literal khi gán/khởi tạo packed field: overflow, underflow
  và signedness mismatch phải là compile error, không truncate im lặng.
- Field read phải trả đúng declared type. Signed integer load phải sign-extend;
  unsigned load phải zero-extend.
- Field store phải kiểm tra type/range và chỉ thay đúng `byte_size` của field.
- Diagnostic phải chứa packed type, field, declared type và lý do. Không parser
  recovery thành partial type rồi tiếp tục codegen.

Không phát minh error code mới nếu repository có registry diagnostic tập trung;
dùng code family phù hợp và thêm test diagnostic tại tầng hiện có.

## 7. `sizeof`

Triển khai `sizeof(Type)` theo syntax Spec:

- operand là type identity, không evaluate như function call runtime;
- packed result là compile-time constant từ layout metadata;
- nested packed size cộng inline;
- method không ảnh hưởng size;
- normal entity giữ contract riêng hiện có, không bị đổi layout để phục vụ
  packed;
- invalid/incomplete/recursive packed layout không được có fallback size 0
  hoặc `field_count * 8`.

Constant folding, semantic và AST-to-MIR phải thống nhất cùng một value.

## 8. MIR, optimizer và codegen

### 8.1. Allocation và construction

- Cấp đúng `layout.total_size`, không `field_count * 8`.
- Named initializer được resolve sang field metadata rồi store tại
  `byte_offset` bằng đúng width.
- Không zero-fill để che việc constructor thiếu field; missing field là lỗi.
- Nếu allocator yêu cầu minimum allocation nội bộ, logical size/offset vẫn
  phải đúng và `sizeof` không được phản ánh allocator rounding.

### 8.2. Typed memory operations

- MIR/LIR phải giữ đủ type/width/signedness cho packed load/store.
- Không hạ mọi packed field thành generic 64-bit load/store.
- Unaligned `u16/u32/u64/float/ptr` tại offset bất kỳ phải chạy đúng trên mọi
  target public. Backend có thể dùng unaligned instruction hợp lệ hoặc chuỗi
  byte load/store an toàn theo target, nhưng không được dựa vào undefined
  alignment behavior.
- Signed load dùng sign extension; unsigned/bool dùng zero extension.
- Narrow store không được ghi đè byte của field kề bên.
- Copy/move/memcpy packed value dùng đúng `layout.total_size`.
- Optimizer không được widen narrow store thành 8-byte store nếu có thể clobber
  field bên cạnh.

### 8.3. Không gian field metadata

Loại bỏ packed path dựa trên bare global field name hoặc `field_index * 8`.
Mọi lookup phải dùng `(owner type, field name)` và trả metadata đầy đủ. Hai
packed type có field cùng tên nhưng offset/type khác nhau phải không xung đột.

Các biểu thức cần coverage:

- constructor;
- local và global packed value;
- field read và field assignment;
- chained nested access `outer.inner.field`;
- packed value qua parameter/return theo ABI hiện có;
- method access tới packed receiver;
- constant-folded `sizeof`.

## 9. Target matrix

Khóa target list từ `bin/virc --help` tại thời điểm thực hiện. Tối thiểu hiện
tại:

- macOS ARM64;
- Linux ARM64;
- Linux x86-64;
- Linux RISC-V 64;
- wasm32-wasi-p1.

Với mỗi target public:

1. rebuild compiler từ source task và ghi provenance/hash;
2. compile positive packed fixtures bằng target flag thật;
3. chạy artifact bằng native runner, QEMU hoặc WASI runtime phù hợp;
4. chạy ít nhất hai lần;
5. capture raw command, stdout, stderr và exit code.

Compile-only không thay thế runtime cho target có runner. Nếu môi trường thiếu
runner, báo blocker cụ thể; không tuyên bố toàn target matrix hoàn tất.

## 10. Bộ test acceptance bắt buộc

Các fixture sau là acceptance contract, không được làm yếu hoặc đổi expected
cho khớp implementation sai:

### Positive E2E

- `packed_layout_mixed_width_e2e.vri`: offsets 0/1/3, raw bytes và field value.
- `packed_named_initializer_order_e2e.vri`: constructor source order khác
  declaration order nhưng memory layout vẫn theo declaration.
- `packed_unaligned_mutation_e2e.vri`: narrow/unaligned store không clobber.
- `packed_signed_load_e2e.vri`: sign extension i8/i16/i32 và raw bytes.
- `packed_nested_layout_e2e.vri`: nested inline layout và chained field access.
- `packed_method_layout_e2e.vri`: packed method được link đúng và không chiếm
  byte trong layout.
- `packed_sizeof_e2e.vri`: `sizeof` là hằng compile-time, tổng byte chính xác
  và không tính method.

### Compile rejection

- missing field annotation;
- dynamic `string` field;
- normal entity inline field;
- recursive packed layout;
- shorthand `packed Name` ngoài grammar canonical;
- constructor missing, duplicate hoặc unknown field;
- `u8` overflow và underflow.

Bổ sung unit-level tests nếu test harness hỗ trợ:

- token/span của `packed entity`;
- AST kind giữ `PackedDef`;
- layout metadata exact offsets/sizes/alignment;
- cycle detection;
- MIR assertion không có 64-bit store cho narrow packed field;
- LIR/backend assertion cho signed/unsigned extension;
- two packed types có cùng field name nhưng offset khác nhau;
- global/parameter/return/copy-move paths.

## 11. Regression và static gates

Sau implementation:

```text
./run_tests.sh 7
./run_tests.sh min
git diff --check
```

Chạy thêm compiler semantic/unit/IR suites và target suites hiện có. Group §7
chỉ được gọi là packed coverage khi có fixture thực sự bắt đầu bằng
`packed entity` và quan sát byte layout/`sizeof`.

Static inventory phải phân loại mọi hit tương đương:

```text
PackedDef
PackedKw
field_index * 8
fid * 8
n * 8
g_scoped_field_indices
get_scoped_field_index
generic 64-bit field load/store
sizeof
```

`* 8` có thể hợp lệ cho normal entity, tuple hoặc IR table, nhưng packed path
không được đi qua phép tính slot đó. Ghi rõ từng exception còn lại.

## 12. Cấm tuyệt đối

- Không sửa hoặc mở rộng C-core để hoàn thành task.
- Không đổi packed entity thành alias của normal entity.
- Không dùng `field_index * 8` cho packed field.
- Không cấp `field_count * 8` rồi chỉ báo `sizeof` nhỏ hơn.
- Không ghi 8 byte cho `u8/u16/u32` rồi dựa vào field access cùng lỗi để pass.
- Không hard-code offsets theo tên fixture hoặc field.
- Không silently truncate integer ngoài range.
- Không cho thiếu annotation qua type inference.
- Không padding cuối struct.
- Không giả E2E bằng interpreter fallback, output hard-code hoặc binary cũ.
- Không đổi test raw-byte thành test chỉ đọc lại `value.field`.
- Không reset/restore/stage/commit thay đổi ngoài task; giữ nguyên worktree của
  người dùng.

## 13. Quy trình thực hiện

1. Capture baseline self-host và compiler provenance.
2. Lập inventory packed/field-layout/sizeof trong `stdlib/vir/compiler/`.
3. Thiết kế layout metadata duy nhất và dependency/cycle resolution.
4. Siết grammar và semantic diagnostics.
5. Triển khai typed packed construction/read/write/sizeof.
6. Carry width/signedness qua MIR, LIR, optimizer và từng backend.
7. Rebuild `bin/virc` thành version 2.8.2 từ source mới.
8. Chạy positive, negative, regression và target matrix hai lần.
9. Chạy static-clean inventory và `git diff --check`.
10. Chỉ commit file thuộc task nếu workflow yêu cầu.

## 14. Báo cáo bàn giao bắt buộc

Báo cáo cuối phải có:

- root cause theo parser, semantic, layout, MIR/LIR và backend;
- layout/type-size contract cuối cùng;
- danh sách file sửa/thêm;
- diagnostic cho từng negative class;
- raw command, compiler hash, target, runner, stdout/stderr/exit code;
- kết quả từng packed fixture và regression suite;
- inventory mọi `* 8`/generic field path còn lại và lý do hợp lệ;
- blocker target nếu có.

Không tuyên bố hoàn tất nếu còn một trong các điều sau:

- `u8/u16/u32` vẫn ở offsets `0/8/16`;
- packed constructor phụ thuộc argument order;
- missing annotation hoặc dynamic field vẫn compile;
- narrow store clobber field kề;
- signed narrow load không sign-extend;
- nested packed size/access sai hoặc cycle làm compiler treo;
- `sizeof` không phải compile-time tổng byte chính xác;
- method làm tăng size;
- một backend public vẫn dùng 64-bit generic packed access;
- group §7 chỉ pass nhờ `entity` thường.
