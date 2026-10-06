Hãy refactor và hoàn thiện toàn bộ JSON subsystem của Vir theo nguyên tắc:

> `stdlib/vir/data/json.vri` là **canonical JSON semantic implementation duy nhất** của hệ sinh thái Vir.

InterVir không được duy trì một parser/serializer JSON độc lập có semantic riêng.

## Repository

Vir / stdlib:

`/Users/gengyang/Vir-3.0`

InterVir:

`/Users/gengyang/Desktop/Repo/intervir`

Các file quan trọng đã xác định:

- `stdlib/vir/data/json.vri`
- `intervir/http/context.vri`
- `intervir/transport/tcp.vri`
- `intervir/protocol/json_slice.vri`

Trước khi sửa:

1. Đọc toàn bộ implementation JSON hiện tại.
2. Đọc toàn bộ call site trong repo sử dụng JSON.
3. Đọc `json_slice.vri` và xác định chính xác:
   - phần nào đang parse JSON;
   - phần nào đang serialize JSON;
   - phần nào thực sự cần zero-copy / slice scanning cho HTTP;
   - phần nào đang duplicate semantic của stdlib.
4. Chạy toàn bộ test JSON hiện tại để tạo baseline.
5. Commit baseline trước khi refactor để có thể rollback.

Không được suy đoán API hoặc architecture khi chưa đọc code.

---

# 1. Mục tiêu kiến trúc

Sau refactor phải có dependency model:

```text
Vir stdlib
└── vir.data.json
    ├── canonical JsonValue
    ├── canonical parser
    ├── canonical serializer
    ├── object/array operations
    ├── number semantics
    ├── error model
    └── conversion utilities

InterVir
├── HTTP JSON adapter
├── request/response integration
├── optional zero-copy JSON view/scanner
└── tuyệt đối không có JSON semantic implementation thứ hai
```

InterVir phải phụ thuộc vào stdlib JSON.

Không được copy parser, serializer hoặc number semantics từ stdlib sang InterVir.

---

# 2. Xử lý `intervir/protocol/json_slice.vri`

Đây là yêu cầu bắt buộc.

Hiện InterVir có JSON parser/writer riêng tại:

`intervir/protocol/json_slice.vri`

Phải audit toàn bộ module này.

Nếu functionality của nó trùng với parser/serializer của stdlib thì:

- xóa implementation duplicate;
- chuyển call site sang dùng `vir.data.json`;
- giữ compatibility adapter nếu cần để tránh phá API công khai.

Nếu một phần thực sự cần zero-copy vì HTTP performance thì chỉ được giữ dưới dạng:

- scanner;
- slice view;
- token/view abstraction;
- lightweight HTTP-oriented JSON view.

Phần đó:

- không được tự định nghĩa JSON semantics;
- không được có parser semantic thứ hai;
- không được có serializer JSON thứ hai;
- phải dùng canonical number/string/null/object/array rules từ stdlib;
- tên module phải phản ánh đúng bản chất là view/scanner chứ không giả vờ là JSON implementation độc lập.

Nếu functionality zero-copy có giá trị ngoài InterVir, cân nhắc chuyển phần generic về stdlib.

Không được để tồn tại hai implementation cùng xử lý cùng một JSON document theo hai rule khác nhau.

---

# 3. Sửa JSON number model

Đây là ưu tiên cao nhất sau khi hợp nhất implementation.

Hiện `JsonValue.num_val` dựa trên `int`, dẫn đến semantic sai.

Các lỗi phải sửa:

- `1.5` không được biến thành `1`.
- `1e3` không được accessor trả thành `1`.
- large integer không được overflow âm thầm.
- parse → stringify phải giữ đúng giá trị JSON.
- accessor không được silently truncate decimal hoặc exponent.

Thiết kế lại number representation để hỗ trợ đầy đủ JSON number grammar:

- integer;
- negative integer;
- fraction;
- exponent;
- negative exponent;
- large integer;
- các boundary của native integer.

Phải xác định rõ contract giữa:

- lexical JSON number;
- integer conversion;
- floating conversion;
- exact representation;
- overflow;
- invalid conversion.

Không được silently truncate.

Các conversion không chắc chắn phải trả `Option` hoặc `Result`.

Ví dụ về semantic mong muốn, không bắt buộc giữ đúng tên API:

```text
asInt()
asFloat()
asNumber()
```

phải phân biệt được:

- exact integer;
- fractional number;
- exponent;
- overflow;
- incompatible conversion.

Không được dùng floating point làm representation duy nhất nếu làm mất round-trip precision.

---

# 4. Hoàn thiện JSON object utilities

API hiện có một phần:

- get
- set
- has
- key/value access

Bổ sung các functionality còn thiếu:

- remove
- keys
- values
- entries
- len / size thống nhất
- clear nếu phù hợp
- object iteration
- safe lookup
- deep get
- deep set
- clone
- deep clone
- merge
- deep equality

Giữ naming ngắn, rõ nghĩa, nhất quán với style hiện tại của Vir.

Không tạo API dài dòng hoặc JavaScript-like không cần thiết.

Có thể thêm alias:

- `json.obj()` → `json.object()`
- `json.arr()` → `json.array()`

nhưng alias chỉ là ergonomic layer, không phải mục tiêu chính.

---

# 5. Hoàn thiện JSON array utilities

API hiện có:

- push
- at
- len

Bổ sung:

- pop
- insert
- remove
- contains
- clear nếu phù hợp
- array iteration
- clone / deep clone
- equality

Index error phải có contract rõ.

Không silent undefined behavior.

---

# 6. Safe primitive conversions

Bổ sung conversion an toàn từ một `JsonValue` bất kỳ sang primitive.

Bao gồm tối thiểu:

- string
- bool
- integer
- floating/number
- null inspection

Không được silently:

- truncate;
- coerce string thành number;
- coerce boolean thành number;
- convert invalid value thành default.

Sử dụng `Option` hoặc `Result` theo convention hiện tại của Vir.

Giữ các getter convenience hiện tại như:

- `getInt`
- `getStr`
- `getBool`

nhưng chuẩn hóa semantic của chúng với conversion canonical mới.

---

# 7. Missing và null

Giữ nguyên semantic đúng hiện tại:

- missing key → `Option.None`
- existing key có JSON null → `Option.Some(JsonValue Null)`

Không được làm mất phân biệt này trong API mới.

---

# 8. Iterator support

JSON object và array phải hỗ trợ iteration theo mechanism phù hợp với Vir hiện tại.

Nếu compiler/runtime đã có iterator protocol thì tích hợp đúng protocol đó.

Không tạo iterator framework riêng chỉ dành cho JSON.

Object iteration phải có khả năng lấy:

- key;
- value;
- hoặc entry.

Array iteration phải lấy value theo thứ tự.

Object phải tiếp tục giữ insertion order trừ khi explicitly yêu cầu sorted/canonical output.

---

# 9. Error model

Hiện `ParseError` có:

- offset;
- line;
- column;
- message.

Giữ compatibility nhưng bổ sung error contract đủ cho JSON.

Cần hỗ trợ:

- parse error;
- conversion error;
- encode error;
- decode error sau này;
- number overflow;
- invalid number conversion;
- nesting limit;
- document-size limit;
- duplicate-key condition nếu policy yêu cầu.

Bổ sung JSON path khi có thể:

```text
$.user.address.zip
```

Không cần ép mọi error vào một giant type nếu architecture hiện tại phù hợp hơn, nhưng error API phải nhất quán.

---

# 10. Duplicate key policy

Hiện parser dùng last-wins.

Phải:

- giữ backward compatibility mặc định nếu cần;
- document rõ behavior;
- thiết kế khả năng chọn policy nếu implementation phù hợp.

Các policy nên hỗ trợ hoặc chuẩn bị được:

- last wins;
- first wins;
- error.

Không cần over-engineer nếu API hiện tại chưa có parser options, nhưng semantic phải được xác định rõ và test.

---

# 11. Limits

Hiện nesting guard cố định là 128.

Giữ limit này hoặc refactor thành cấu hình nếu hợp lý.

Bổ sung document-size limit ở nơi phù hợp.

InterVir hiện có `MAX_BODY_BYTES` nhưng chưa enforce.

Phải enforce request body limit thực sự.

Phân biệt:

- stdlib JSON document limit;
- HTTP request body limit.

Không coupling stdlib vào HTTP.

---

# 12. Stringify

Hiện đã có:

- `json.stringify()`
- `json.pretty()`

Hoàn thiện:

- compact stringify thực sự;
- pretty stringify;
- configurable indentation nếu không phá API;
- Unicode escaping policy;
- deterministic output;
- optional sorted/canonical key ordering.

`json.stringify()` compact không được chèn whitespace thừa sau `:` hoặc `,`.

Không được làm mất insertion order mặc định.

Sorted/canonical ordering phải là opt-in.

---

# 13. Circular-reference handling

Nếu `JsonValue` architecture có khả năng tạo graph/cycle thì serializer phải detect cycle và trả error thay vì:

- infinite recursion;
- crash;
- stack overflow.

Nếu architecture hiện tại đảm bảo tree tuyệt đối thì hãy chứng minh điều đó bằng code và document lý do không cần cycle detection.

Không thêm code vô ích nếu type system đã loại trừ cycle.

---

# 14. Streaming

Đánh giá khả năng bổ sung:

- streaming parser;
- streaming serializer.

Chỉ triển khai nếu architecture hiện tại cho phép làm sạch.

Không phá canonical parser hiện tại.

Nếu scope quá lớn, tạo interface/foundation và ghi rõ phần còn lại trong report, nhưng không được giả implementation bằng wrapper đọc toàn bộ document rồi gọi đó là streaming.

---

# 15. Typed serde

Sau khi dynamic JSON layer ổn định mới triển khai typed serde.

Mục tiêu:

- `encode<T>`
- `decode<T>`

Hỗ trợ:

- primitive;
- struct;
- nested struct;
- enum;
- arrays/collections;
- optional field;
- default field;
- renamed field;
- ignored field;
- custom serializer;
- custom deserializer.

Không hard-code domain type.

Nếu Vir compiler hiện chưa có reflection/generic metadata đủ mạnh, không hack runtime bằng cách phụ thuộc tên field hard-coded.

Trong trường hợp compiler chưa hỗ trợ sạch:

- thiết kế serde API;
- xác định compiler/runtime hook còn thiếu;
- implement phần có thể thực hiện đúng;
- ghi rõ phần blocked.

Không dựng pseudo-reflection nguy hiểm chỉ để hoàn thành checkbox.

---

# 16. InterVir HTTP integration

InterVir hiện đã có:

- `ctx.json(...)`
- `ctx.json_val(status, JsonValue)`
- automatic `Content-Type: application/json; charset=utf-8`

Không viết lại những phần đã có.

Hoàn thiện phần còn thiếu:

- request body → canonical `JsonValue`;
- automatic invalid JSON handling;
- body-size enforcement;
- typed request binding khi serde đã sẵn sàng;
- typed response serialization;
- JSON middleware nếu thực sự cần;
- content negotiation nếu phù hợp với architecture hiện tại.

Response path phải dùng serializer canonical của stdlib.

Không được stringify bằng implementation khác trong `transport` hoặc `protocol`.

---

# 17. JSON Schema

Không ưu tiên trước parser/number/conformance.

Sau khi core ổn định, đánh giá:

- validation API;
- JSON Schema support;
- hoặc schema abstraction riêng.

Không nhét một JSON Schema engine lớn vào stdlib nếu không phù hợp.

Nếu triển khai, nên cân nhắc package/module độc lập sử dụng canonical `JsonValue`.

---

# 18. Testing bắt buộc

Test hiện tại quá nhỏ.

Phải bổ sung test theo nhóm.

## Parser

- object;
- array;
- nested document;
- empty object;
- empty array;
- string escape;
- Unicode;
- surrogate edge cases nếu applicable;
- whitespace;
- null;
- bool;
- integer;
- fraction;
- exponent;
- negative exponent;
- malformed JSON;
- trailing garbage;
- duplicate key;
- maximum depth.

## Number

Đặc biệt test:

```text
0
-0
1
-1
1.0
1.5
-1.5
1e3
1E3
1e+3
1e-3
12345678901234567890
```

Phải kiểm tra:

- parse;
- access;
- stringify;
- round trip;
- overflow.

## Object / array

Test toàn bộ operations mới.

## Round trip

Property:

```text
parse(stringify(value))
```

phải tương đương semantic với `value`.

## Error

Test:

- line;
- column;
- offset;
- message;
- path nếu có;
- overflow;
- invalid conversion.

## InterVir

Test:

- valid request JSON;
- malformed request JSON;
- oversized body;
- JSON response;
- content type;
- stdlib serializer được sử dụng;
- không có parser implementation độc lập.

---

# 19. RFC compatibility

Tạo test suite dựa trên official/community JSON conformance corpus phù hợp.

Không copy dependency khổng lồ không cần thiết vào repo.

Mục tiêu là chứng minh:

- accepted valid documents;
- rejected invalid documents;
- implementation-defined edge cases được document.

Viết compatibility report.

---

# 20. Fuzz testing

Bổ sung fuzz target cho parser.

Ưu tiên kiểm tra:

- crash;
- out-of-bounds;
- infinite loop;
- excessive recursion;
- malformed Unicode;
- malformed number;
- malformed nesting;
- random bytes.

Nếu project chưa có fuzz infrastructure, tạo target tối thiểu và document cách chạy.

---

# 21. Benchmark

Benchmark ít nhất:

- parse small JSON;
- parse medium JSON;
- parse large JSON;
- stringify;
- pretty stringify;
- object lookup;
- array traversal.

Nếu `json_slice` trước đây tồn tại vì performance, benchmark phải so sánh trước/sau refactor.

Không được giữ duplicate parser chỉ vì giả định rằng nó nhanh hơn.

Chỉ giữ zero-copy scanner/view khi benchmark chứng minh use case thực tế.

---

# 22. Performance và allocation

Trong quá trình refactor phải chú ý:

- unnecessary allocation;
- string copy;
- recursive allocation;
- object lookup complexity;
- array growth;
- repeated stringify buffer growth.

Nếu có thể, serializer nên sử dụng buffer growth strategy hợp lý thay vì concatenation O(n²).

Không đổi semantic để lấy benchmark đẹp.

Correctness trước, sau đó mới optimize.

---

# 23. Backward compatibility

Không phá các API đang được sử dụng nếu không cần thiết.

Nếu phải rename/deprecate:

- giữ compatibility wrapper;
- thêm deprecation note;
- migrate call site nội bộ;
- document migration.

Đặc biệt không xóa tùy tiện:

- `json.object()`
- `json.array()`
- `json.stringify()`
- `json.pretty()`
- existing getters
- `ctx.json(...)`
- `ctx.json_val(...)`

`json.obj()` và `json.arr()` nếu thêm chỉ là aliases.

---

# 24. Naming

Không dùng `snake_case` cho API mới nếu convention hiện tại của Vir không dùng kiểu đó.

Tên phải:

- ngắn;
- rõ nghĩa;
- không viết tắt khó hiểu;
- không copy naming style của Node/JavaScript một cách máy móc.

Nếu một concept cần namespace hai cấp thì ưu tiên dot-style theo convention hiện tại.

Không tạo tên dài chỉ để mô tả implementation detail.

---

# 25. Không thay đổi syntax ngôn ngữ

Task này không được thêm:

- `{}` JSON literal;
- object literal syntax mới;
- array literal syntax mới;
- compiler grammar mới chỉ để JSON trông giống JavaScript.

JSON first-class ở task này tập trung vào:

- semantic correctness;
- canonical representation;
- runtime API;
- safe conversion;
- serde;
- framework integration.

Syntax language-level là scope riêng.

---

# 26. Definition of Done

Chỉ xem task hoàn tất khi:

1. stdlib JSON là canonical semantic implementation duy nhất.
2. InterVir không còn parser/serializer JSON thứ hai.
3. `json_slice` đã được loại bỏ, chuyển thành adapter/view/scanner, hoặc chuyển generic functionality về stdlib.
4. Number model không còn truncate decimal/exponent.
5. Large integer không overflow âm thầm.
6. Parse/stringify round-trip giữ semantic JSON.
7. Object/array API còn thiếu đã được bổ sung.
8. Safe primitive conversions hoàn chỉnh.
9. Error contract rõ ràng.
10. Request body limit được enforce.
11. InterVir request JSON sử dụng stdlib canonical parser.
12. InterVir response JSON sử dụng stdlib canonical serializer.
13. Existing public API không bị phá tùy tiện.
14. Canonical tests pass.
15. RFC/conformance tests pass theo policy đã document.
16. Fuzz target tồn tại và chạy được.
17. Benchmark tồn tại và có before/after result.
18. Không còn duplicated JSON semantic logic khi grep/audit repository.

---

# 27. Deliverables

Sau khi code xong, tạo report Markdown gồm:

## JSON Architecture

- canonical modules;
- dependency flow;
- ownership của stdlib và InterVir;
- số phận cuối cùng của `json_slice`.

## Fixed Bugs

Liệt kê từng bug đã sửa, đặc biệt:

- decimal truncation;
- exponent handling;
- integer overflow;
- compact stringify;
- body-size enforcement.

## New APIs

Liệt kê API mới và compatibility aliases.

## Removed Duplication

Chứng minh những parser/serializer duplicate nào đã được loại bỏ.

## Tests

- unit;
- conformance;
- fuzz;
- round-trip;
- InterVir.

## Benchmarks

Before / after.

## Remaining Limitations

Chỉ ghi những phần thực sự bị compiler/runtime architecture block.

Không ghi TODO chung chung nếu có thể giải quyết ngay trong scope.

---

# 28. Quy tắc triển khai

- Audit trước, sửa sau.
- Không rewrite toàn bộ `json.vri` nếu không cần.
- Không duplicate implementation.
- Không mock.
- Không fake streaming.
- Không fake typed serde.
- Không đổi semantic chỉ để test pass.
- Không bỏ test lỗi hiện tại.
- Không sửa ngoài scope trừ khi dependency bắt buộc.
- Mỗi bước lớn phải compile và chạy test trước khi tiếp tục.
- Nếu refactor gây regression, tìm root cause thay vì patch call site bằng workaround.
- Ưu tiên correctness, compatibility, maintainability, sau đó mới performance.
- Kết thúc bằng `git diff`, test result, benchmark result và danh sách file đã thay đổi.

Mục tiêu cuối cùng không phải làm API trông giống Node.js.

Mục tiêu là biến JSON thành một subsystem chuẩn, an toàn, nhất quán và đủ mạnh của Vir, trong đó stdlib là single source of truth và InterVir chỉ cung cấp integration dành cho HTTP/framework.