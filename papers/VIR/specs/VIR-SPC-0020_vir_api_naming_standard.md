---
id: "VIR-SPC-0020"
type: "SPEC"
domain: "VIR"
title: "VIR API Naming Standard"
status: "ACTIVE"
version: "1.1.0"
language: "vi"
spec_class: "SPECIFICATION"
aliases: []
created: "2026-10-09"
updated: "2026-10-09"
owners:
  - "VIR"
components:
  - "language"
  - "stdlib"
  - "official-libraries"
  - "public-api"
related:
  issues: []
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "api"
  - "naming"
  - "camel-case"
  - "pascal-case"
  - "ufcs"
---

# VIR-SPC-0020 — VIR API Naming Standard

## 1. Mục tiêu

Thiết lập quy chuẩn định danh thống nhất cho toàn bộ API công khai của Vir.

Các nguyên tắc cốt lõi:

1. Ưu tiên một từ tiếng Anh hoàn chỉnh, chính xác về ngữ nghĩa.
2. Sử dụng `camelCase` khi tên chứa từ hai từ trở lên.
3. Không viết tắt tùy tiện, không phát minh từ mới chỉ để rút ngắn tên.
4. Không sử dụng `snake_case` cho public API mới.
5. Không hy sinh ngữ nghĩa để đạt tính thẩm mỹ hoặc rút ngắn tên.
6. Các thao tác tương đương phải có cách đặt tên nhất quán giữa các kiểu.
7. Không mở rộng grammar chỉ để đáp ứng quy tắc đặt tên.
8. Hạn chế alias, wrapper và overload không cần thiết.

## 2. Quy chuẩn định danh

| Thành phần | Quy chuẩn | Ví dụ |
|---|---|---|
| Type | `PascalCase` | `Option`, `Result`, `Vec` |
| Enum variant | `PascalCase` | `Some`, `None`, `Success`, `Failure` |
| Function | `lowercase` / `camelCase` | `parse`, `readFile` |
| Method | `lowercase` / `camelCase` | `map`, `unwrapOr` |
| Predicate | `is` + tên trạng thái | `isEmpty`, `isSuccess` |
| Module | `lowercase` / `camelCase` | `json`, `fileSystem` |
| Constant | `lowercase` / `camelCase` | `pi`, `maxSize`, `defaultTimeout` |

Quy tắc tổng quát:

- Một từ: `lowercase`.
- Từ hai từ trở lên: `camelCase`.
- Type và enum variant: `PascalCase`.
- Không dùng `UPPER_SNAKE_CASE` cho constant mới.
- Quy tắc dành cho type và variant có ưu tiên riêng, không bị ép theo cách đặt tên của method.

## 3. Quy tắc lựa chọn tên

### 3.1. Một từ chính xác

Luôn ưu tiên một từ tiếng Anh đầy đủ nếu nó diễn đạt đúng chức năng.

```text
get
set
read
write
push
pop
insert
remove
clear
compact
copy
equal
map
filter
recover
```

### 3.2. camelCase

Nếu không tồn tại một từ đơn phù hợp, dùng tên ghép có ý nghĩa rõ ràng.

```text
isEmpty
isSuccess
unwrapOr
unwrapOrElse
mapFailure
flatMap
toOption
```

Không thay tên ghép chính xác bằng một từ đơn nhưng sai hoặc thiếu ngữ nghĩa.

### 3.3. Từ đầy đủ, acronym và dạng rút gọn

`camelCase` và `PascalCase` chỉ quy định cách nối và viết hoa các từ; chúng
không cho phép tự động rút gọn từng từ trong identifier.

```text
socketAddress
localAddress
remoteAddress
ipAddress
peerAddress
```

Các acronym và định danh kỹ thuật đã được công nhận rộng rãi được phép giữ ở
dạng chuẩn của chúng. Ví dụ: `ip`, `utf8`, `http`, `url`. Acronym phải được
viết nhất quán theo quy tắc casing của identifier chứa nó:

```text
ipAddress
isValidUtf8
parseHttpResponse
decodeUrl
```

Các dạng cắt ngắn từ thông thường như `addr`, `cfg`, `idx`, `len`, `str`
không mặc nhiên là acronym hoặc ngoại lệ. Public API phải dùng từ đầy đủ như
`address`, `config`, `index`, `length`, `string`, trừ khi một đặc tả tương
thích riêng ghi rõ lý do giữ tên cũ.

Thuật ngữ API lịch sử chỉ được giữ như ngoại lệ khi có lý do kỹ thuật hoặc
tương thích được ghi rõ. Việc một tên phổ biến trong ngôn ngữ hoặc thư viện
khác không tự động biến nó thành tên canonical của Vir.

### 3.4. Tên tham số public

Tên tham số thuộc public API phải tuân theo cùng quy tắc dùng từ đầy đủ và
`camelCase` như function và method. Ví dụ:

```text
config
headers
delimiter
index
message
precision
source
destination
pattern
replacement
extension
separator
```

Các ký hiệu ngắn có ý nghĩa kỹ thuật phổ quát như `i`, `x`, `y`, `n`, `id`,
`ms`, `ns` có thể được giữ khi ngữ cảnh làm cho ý nghĩa không mơ hồ. Ngoại lệ
này không áp dụng cho các dạng cắt ngắn tùy tiện.

### 3.5. Tham số điều khiển hành vi

Cho phép sử dụng tham số để lựa chọn hành vi khi:

- Tham số có kiểu và ý nghĩa xác định.
- Không làm mơ hồ chức năng chính.
- Không che giấu các thao tác khác biệt đáng kể.
- Không gây khó khăn cho mở rộng API.

Quyết định giữa `remove(index, swap)` và `swapRemove(index)` thuộc thiết kế API cụ thể, không được tự động quyết định chỉ bằng quy chuẩn naming.

## 4. Predicate

Các phương thức kiểm tra trạng thái ưu tiên tiền tố `is`.

```text
option.isSome
option.isNone

result.isSuccess
result.isFailure

vec.isEmpty
text.isDigit
text.isAlpha
```

Không sử dụng hậu tố `?` cho tên predicate.

Các phép kiểm tra quan hệ có tên tự nhiên như `contains`, `equal` được phép giữ nguyên mà không bắt buộc thêm `is`.

## 5. Type, Enum Variant và Constructor

Type và enum variant sử dụng `PascalCase`.

```text
Option.Some(value)
Option.None

Result.Success(value)
Result.Failure(error)
```

Constructor functions thông thường sử dụng `lowercase` hoặc `camelCase`.

Phải phân biệt:

- Enum variant: thành phần của hệ kiểu ngôn ngữ.
- Constructor function: hàm tạo giá trị.
- Factory method: phương thức cung cấp cơ chế khởi tạo.

Không tạo factory functions trùng lặp chỉ để thay đổi cách viết hoa.

Các constructor của collection hoặc builder có cùng contract "tạo giá trị
rỗng với dung lượng được dự trữ trước" phải ưu tiên tên `alloc`:

```text
Vec.alloc(capacity)
builder.alloc(capacity)
deque.alloc(capacity)
map.alloc(capacity)
set.alloc(capacity)
```

Không dùng `withCap` cho contract này. Khác biệt về thuật toán cấp phát hoặc
số bucket nội bộ không làm thay đổi tên public nếu contract quan sát được vẫn
là một giá trị rỗng với dung lượng dự trữ. API có ngữ nghĩa khác phải dùng tên
khác và ghi rõ ngoại lệ.

`none` là null literal dành riêng của Vir, vì vậy `Option.None` không được tự động chuyển thành `Option.none`.

`Result.Success` và `Result.Failure` là tên chuẩn. Mọi tài liệu, đặc tả hoặc call site còn dùng `Result.Ok` và `Result.Err` là migration debt và phải được cập nhật, kiểm thử riêng.

## 6. Constant

Constant áp dụng cùng quy tắc naming với các giá trị thông thường.

```text
pi
maxSize
defaultTimeout
appName
```

Không sử dụng:

```text
PI
MAX_SIZE
DEFAULT_TIMEOUT
```

chỉ vì một giá trị được khai báo bất biến.

Quy tắc này không quyết định:

- Cú pháp khai báo constant.
- Compile-time constant evaluation.
- Runtime immutable bindings.
- Mutability của dữ liệu được tham chiếu.

Những nội dung trên thuộc đặc tả ngữ nghĩa ngôn ngữ.

## 7. Uniform Function Call Syntax (UFCS)

Ưu tiên dạng:

```text
receiver.operation(arguments)
```

Ví dụ:

```text
vec.push(value)
vec.remove(index)
vec.compact()

option.map(transform)
result.map(transform)
```

Không sử dụng tên giả phân cấp hoặc chuỗi phân cấp phương thức không cần thiết chỉ để nhóm API.

Tên UFCS phải phản ánh chính xác chức năng, không phụ thuộc vào việc thao tác được khai báo như method hay function.

## 8. Tính đối xứng giữa các kiểu

Các phương thức có ngữ nghĩa tương đương nên có cùng tên.

```text
option.map(transform)
result.map(transform)

option.unwrapOr(default)
result.unwrapOr(default)
```

Khi biến đổi các nhánh khác nhau, tên phải thể hiện rõ sự khác biệt.

```text
result.map(transform)
result.mapFailure(transformError)
```

Không ép các thao tác khác ngữ nghĩa phải dùng chung một tên chỉ để đạt tính đồng bộ hình thức.

## 9. Quy tắc tương thích

Các thay đổi naming có thể ảnh hưởng đến:

- Source compatibility.
- Pattern matching.
- Symbol resolution.
- Compiler diagnostics.
- Autocomplete và LSP.
- Documentation và registry.
- Public library interfaces.

Mọi breaking change phải được kiểm tra phạm vi ảnh hưởng và có kế hoạch migration.

Không tự động tạo alias để duy trì tên cũ nếu chưa có quyết định về compatibility.

## 10. Quy trình kiểm tra API

Trước khi chấp nhận API công khai mới, phải kiểm tra:

1. Tên có đúng ngữ nghĩa không?
2. Có thể sử dụng một từ tiếng Anh đầy đủ không?
3. Nếu nhiều từ, đã sử dụng `camelCase` chưa?
4. Có viết tắt hoặc từ tự tạo không cần thiết không?
5. Có trùng chức năng với API hiện hành không?
6. Có nhất quán với các kiểu và module khác không?
7. Có xung đột grammar hoặc reserved keywords không?
8. Có tạo ra alias, wrapper hoặc overload không cần thiết không?
9. Hành vi lỗi, evaluation và mutability có được xác định rõ không?
10. Có ảnh hưởng đến compatibility hay ABI không?

## 11. Phạm vi áp dụng

Bắt buộc đối với:

- Vir Standard Library.
- Các official libraries của Virgori.
- Public API mới của các runtime và framework chính thức.
- Các API đang được chuẩn hóa trước khi phát hành ổn định.

Không tự động áp dụng đối với:

- Compiler internal symbols.
- External ABI.
- Foreign-function bindings.
- Tên do external protocols quy định.
- Các trường hợp có yêu cầu tương thích đặc biệt.

## 12. Nguyên tắc ưu tiên cuối cùng

**Semantic Correctness > Consistency > Brevity > Aesthetics**

Một API tốt phải:

- Dễ hiểu khi đọc.
- Dễ tìm khi viết.
- Dễ dự đoán khi mở rộng.
- Nhất quán giữa các module.
- Ổn định trong dài hạn.

Quy chuẩn này quản lý tên định danh, không thay thế các đặc tả riêng về cú pháp, hệ kiểu, hành vi runtime hoặc thiết kế thuật toán.

## 13. Revision History

| Date | Version | Change |
|---|---|---|
| 2026-10-09 | 1.1.0 | Chuẩn hóa từ đầy đủ và acronym; áp dụng naming cho public parameters; thống nhất constructor dự trữ dung lượng là `alloc` |
| 2026-10-09 | 1.0.0 | Ban hành quy chuẩn naming API công khai đầu tiên |
