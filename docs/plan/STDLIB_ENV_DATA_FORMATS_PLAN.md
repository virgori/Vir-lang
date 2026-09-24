Bạn đang làm việc trên **Vir Programming Language**.

Nhiệm vụ: thiết kế và triển khai hai nhóm thư viện chuẩn production-grade:

1. **Environment Variables API**
2. **Data / File Format Standard Library**

Mục tiêu không phải proof-of-concept. Implementation phải strict, đầy đủ hai chiều đọc/ghi khi format hỗ trợ, có error model rõ ràng, UTF-safe, memory-safe theo mô hình của Vir, không phá API hiện có và không đưa logic không cần thiết vào compiler/runtime.

---

# STATUS DASHBOARD & COMPLETION PROGRESS

| Module | Location | Status | Dot-Style ABI | Test Suite |
| :--- | :--- | :--- | :--- | :--- |
| **`vir.data.csv`** | `stdlib/vir/data/csv.vri` | **COMPLETE** | `csv.read()`, `csv.write()`, `doc.count()`, `row.add()` | `tests/std_csv_test.vri` (12/12 PASS) |
| **`vir.data.ini`** | `stdlib/vir/data/ini.vri` | **COMPLETE** | `ini.read()`, `ini.write()`, `doc.get()`, `doc.set()` | `tests/std_ini_test.vri` (14/14 PASS) |
| **`vir.data.toml`**| `stdlib/vir/data/toml.vri`| **COMPLETE** | `toml.parse()`, `toml.table()`, `val.get()`, `val.set()`| `tests/std_toml_test.vri` (11/11 PASS) |
| **`vir.data.xml`** | `stdlib/vir/data/xml.vri` | **COMPLETE** | `xml.parse()`, `xml.element()`, `node.attr()`, `node.addChild()` | `tests/std_xml_yaml_test.vri` (13/13 PASS) |
| **`vir.data.yaml`**| `stdlib/vir/data/yaml.vri`| **NOT IMPLEMENTED** (Strict Security Err) | N/A | Tested in `std_xml_yaml_test` |

---

# PHẦN I — KIẾN TRÚC TỔNG THỂ

Phải giữ ranh giới:

```text
Language / Compiler
        ↓
Standard Library
        ↓
Runtime / Platform Abstraction
        ↓
Operating System
```

Compiler không được biết JSON, CSV, TOML hay environment variable là gì.

Compiler chỉ xử lý language semantics.

Runtime chỉ chứa primitive cần thiết để:

* allocation;
* process startup;
* OS interaction;
* syscall/platform API;
* low-level I/O;
* environment access primitive nếu cần.

Các API thân thiện với developer phải nằm trong standard library.

Ví dụ:

```text
std.env
std.fs

std.data.json
std.data.csv
std.data.toml
std.data.ini
std.data.xml

std.encoding.base64
std.encoding.hex
std.net.url
```

Không được đưa parser JSON/TOML/XML/CSV vào runtime.

---

# PHẦN II — ENVIRONMENT VARIABLES

Triển khai module:

```text
std.env
```

Environment variables thuộc process/OS environment.

Vir chỉ cung cấp abstraction thống nhất.

API mong muốn:

```vir
env.get("PATH")
env.get_or("PORT", "8080")

env.has("HOME")

env.set("APP_ENV", "production")
env.unset("APP_ENV")

env.all()
```

Có thể bổ sung:

```vir
env.keys()
env.values()
env.clear()
```

nhưng chỉ nếu phù hợp với platform semantics và không tạo API nguy hiểm hoặc khó đảm bảo portability.

## 1. env.get

Phải phân biệt:

```text
KEY không tồn tại
```

với:

```text
KEY tồn tại nhưng value = ""
```

Không được dùng empty string để biểu diễn cả hai trạng thái.

Nếu Vir có Option:

```vir
Option<string>
```

thì ưu tiên:

```vir
env.get(name) -> Option<string>
```

Nếu chưa có Option chuẩn thì sử dụng error/result/value model phù hợp hiện tại.

Không tạo sentinel magic.

---

## 2. env.get_or

Ví dụ:

```vir
let port = env.get_or("PORT", "8080")
```

Chỉ dùng fallback nếu variable không tồn tại.

Nếu variable tồn tại nhưng:

```text
PORT=""
```

thì phải trả empty string, không tự dùng fallback.

---

## 3. env.has

```vir
env.has("PATH")
```

phải kiểm tra existence thực sự.

Không implement bằng:

```text
env.get(name) != ""
```

vì empty value vẫn là một biến tồn tại.

---

## 4. env.set

```vir
env.set(name, value)
```

Phải có semantics rõ:

```text
existing key → overwrite
missing key  → create
```

Nếu API muốn hỗ trợ không overwrite:

```vir
env.set_if_absent(name, value)
```

hoặc:

```vir
env.set(name, value, overwrite: false)
```

Nhưng không làm API phức tạp nếu chưa cần.

---

## 5. env.unset

```vir
env.unset("DEBUG")
```

Phải có behavior deterministic.

Nếu variable không tồn tại, ưu tiên operation idempotent:

```text
unset(nonexistent) = success
```

trừ khi Vir stdlib conventions yêu cầu khác.

---

# PHẦN III — ENV INPUT VALIDATION

Environment variable name phải validate.

Reject:

```text
NUL
=
```

trong key nếu platform không cho phép.

Value phải reject NUL nếu underlying OS API dùng NUL-terminated strings.

Không silently truncate.

Ví dụ:

```text
"ABC\0DEF"
```

không được biến thành:

```text
"ABC"
```

mà phải trả lỗi.

---

# PHẦN IV — ENV MEMORY SAFETY

Không được trả raw pointer trực tiếp vào OS environment storage nếu lifetime không đảm bảo.

Ví dụ Unix:

```text
getenv()
```

có thể trả pointer thuộc environment storage.

Public Vir API nên trả:

```text
owned string
```

hoặc một representation có lifetime contract rõ ràng.

Không để:

```text
let x = env.get("PATH")
env.set(...)
use(x)
```

trở thành dangling pointer.

Nếu cần, copy dữ liệu ra region/arena thuộc caller.

---

# PHẦN V — ENV PLATFORM BACKENDS

Phải có abstraction platform-specific.

Ví dụ:

```text
std.env
    ↓
rt.env
    ↓
platform implementation
```

Unix-like:

```text
macOS
Linux
BSD nếu sau này hỗ trợ
```

Windows:

```text
Windows Environment API
```

Không expose platform-specific implementation ra public stdlib API.

Public behavior phải nhất quán tối đa giữa platforms.

---

# PHẦN VI — ENV ENUMERATION

Nếu cung cấp:

```vir
env.all()
```

thì phải trả snapshot.

Ví dụ semantic:

```text
Map<string, string>
```

hoặc:

```text
[]EnvEntry
```

với:

```text
EnvEntry {
    key
    value
}
```

Không trả trực tiếp mutable OS environment backing storage.

---

# PHẦN VII — ENV TESTS

Test ít nhất:

```text
get existing
get missing
get empty value
set new
overwrite existing
unset
unset missing
has existing
has missing
enumerate
Unicode key/value nếu platform hỗ trợ
very long value
empty value
invalid key
NUL rejection
repeated set/unset
```

Phải test:

```text
set → get
set → overwrite → get
set → unset → get
```

Không được phụ thuộc vào environment thực tế của máy test.

Tests phải tự tạo tên variable riêng.

---

# PHẦN VIII — FILE I/O FOUNDATION

Data format library không được tự đảm nhiệm low-level file I/O.

Phải có hoặc sử dụng:

```text
std.fs
```

Public API có thể gồm:

```vir
fs.read(path)
fs.read_bytes(path)

fs.write(path, text)
fs.write_bytes(path, bytes)

fs.append(path, data)

fs.exists(path)
fs.remove(path)

fs.rename(old, new)
fs.copy(src, dst)
```

Nếu API hiện tại khác, phải bảo toàn compatibility.

Data format usage phải theo flow:

```vir
let text = fs.read("config.json")
let config = json.parse(text)
```

và:

```vir
let text = json.stringify(config)
fs.write("config.json", text)
```

Không bắt `json.parse()` tự mở file.

Có thể cung cấp convenience API sau này:

```vir
json.read_file(path)
json.write_file(path, value)
```

nhưng implementation phải compose từ:

```text
fs + json
```

không duplicate file logic.

---

# PHẦN IX — DATA FORMAT MODULES

Triển khai theo kiến trúc:

```text
std.data.json
std.data.csv
std.data.toml
std.data.ini
```

Sau đó, nếu infrastructure đủ tốt:

```text
std.data.xml
```

YAML chỉ triển khai nếu có thể làm đúng grammar đáng tin cậy.

Không được làm YAML parser nửa vời rồi gọi là complete YAML.

Ưu tiên:

```text
1. JSON
2. CSV
3. TOML
4. INI
5. XML
6. YAML
```

Hoàn thiện từng module trước khi chuyển sang module tiếp theo.

---

# PHẦN X — COMMON FORMAT API

Các format cần cố gắng nhất quán:

```text
parse
stringify
```

Ví dụ:

```vir
json.parse(text)
json.stringify(value)

toml.parse(text)
toml.stringify(value)

csv.parse(text)
csv.stringify(rows)

ini.parse(text)
ini.stringify(value)
```

XML có thể dùng:

```vir
xml.parse(text)
xml.stringify(document)
```

Không dùng:

```text
read/write
```

cho parse/serialization nếu điều đó gây nhầm với filesystem.

Quy ước:

```text
parse:
text/bytes → structured data

stringify:
structured data → text/bytes
```

---

# PHẦN XI — JSON

Triển khai JSON strict theo standard JSON hiện hành.

API:

```vir
json.parse(text)
json.stringify(value)
```

Có representation kiểu:

```text
JsonValue
```

bao gồm:

```text
Null
Bool
Number
String
Array
Object
```

Không ép tất cả thành string.

---

## JSON primitives

Phải hỗ trợ:

```text
null
true
false
integer
negative integer
floating point
exponent
string
array
object
```

Ví dụ:

```json
null
true
123
-123
1.25
1e10
-1.25e-7
"hello"
[]
{}
```

---

## JSON nesting

Phải hỗ trợ nested structures:

```json
{
  "user": {
    "name": "Vir",
    "roles": [
      "compiler",
      "runtime"
    ]
  }
}
```

Không đặt giới hạn nesting nhỏ tùy tiện.

Nếu có depth limit để bảo vệ stack thì:

* phải configurable hoặc reasonable;
* phải document;
* vượt limit trả lỗi;
* không crash stack.

---

# PHẦN XII — JSON STRING

Phải xử lý:

```text
\"
\\
\/
\b
\f
\n
\r
\t
\uXXXX
```

Phải xử lý Unicode escape đúng.

Nếu có surrogate pair:

```text
\uD83D\uDE00
```

phải decode đúng thành code point tương ứng.

Reject:

```text
isolated high surrogate
isolated low surrogate
malformed escape
truncated unicode escape
```

---

# PHẦN XIII — JSON NUMBER

Không dùng parser số lỏng lẻo.

Phải reject:

```text
+1
01
1.
.5
1e
1e+
--
```

nếu JSON grammar không cho phép.

Phải hỗ trợ:

```text
0
-0
123
-123
0.5
-0.5
1e5
1E5
1e+5
1e-5
```

Phải có strategy rõ về:

```text
integer overflow
float overflow
precision
```

Không silently wrap integer.

---

# PHẦN XIV — JSON STRICT ERRORS

Reject:

```json
{"a":1,}
```

```json
[1,2,]
```

```json
{"a" 1}
```

```json
{"a":1 "b":2}
```

```json
true garbage
```

```json
"unterminated
```

Không auto-repair.

Không tự cho phép JSON5 features như:

```text
comments
single quote
unquoted keys
hex number
NaN
Infinity
```

trừ khi có module riêng.

---

# PHẦN XV — JSON SERIALIZER

Serializer phải:

* escape string;
* preserve nested values;
* serialize Unicode;
* xử lý empty array/object;
* không sinh trailing comma;
* không sinh invalid number;
* không output NaN/Infinity thành JSON invalid.

Có optional pretty printing:

```vir
json.stringify(value)
json.stringify_pretty(value)
```

hoặc:

```vir
json.stringify(value, indent: 2)
```

Nếu thêm option thì giữ API đơn giản.

---

# PHẦN XVI — JSON ROUND TRIP

Phải có invariant:

```text
parse(stringify(value)) == value
```

trong phạm vi semantic hỗ trợ.

Test nhiều cấp nesting.

---

# PHẦN XVII — CSV

CSV không được implement bằng:

```text
split(',')
```

Phải có state machine/parser thực sự.

API:

```vir
csv.parse(text)
csv.stringify(rows)
```

Representation cơ bản:

```text
[][]string
```

Có thể sau này thêm:

```text
CsvReader
CsvWriter
```

cho streaming.

---

# PHẦN XVIII — CSV FEATURES

Phải hỗ trợ:

```text
field bình thường
empty field
quoted field
comma trong quoted field
newline trong quoted field
quote escape
CRLF
LF
```

Ví dụ:

```csv
name,description
Vir,"compiler, runtime"
```

và:

```csv
name,text
Vir,"hello
world"
```

Phải hỗ trợ:

```text
""
"a""b"
```

đúng theo CSV escaping.

---

# PHẦN XIX — CSV CONFIG

Cho phép:

```text
delimiter
quote character nếu hợp lý
header mode
```

Ví dụ:

```vir
csv.parse(text, delimiter: ';')
```

Không hard-code comma nếu muốn dùng TSV/semi-colon formats.

Có thể thêm:

```text
std.data.tsv
```

như wrapper trên CSV engine:

```text
delimiter = '\t'
```

Không duplicate parser.

---

# PHẦN XX — CSV STREAMING

Nếu file rất lớn, toàn bộ parser không nên bắt buộc load tất cả rows vào memory.

Thiết kế architecture để có thể hỗ trợ:

```vir
let reader = csv.reader(stream)

when reader.next() as row loop
    ...
```

Không nhất thiết implement streaming ngay nếu Vir stream API chưa ổn định, nhưng parser architecture không được khóa đường phát triển này.

---

# PHẦN XXI — TOML

Triển khai TOML parser/stringifier theo version specification mà project chọn.

Version phải được ghi rõ.

Không nói:

```text
TOML compliant
```

nếu không support toàn bộ spec tương ứng.

API:

```vir
toml.parse(text)
toml.stringify(value)
```

---

# PHẦN XXII — TOML TYPES

Phải hỗ trợ khi specification yêu cầu:

```text
string
integer
float
boolean
date
time
datetime
array
table
inline table
array of tables
```

Ví dụ:

```toml
title = "Vir"

[compiler]
version = "3.0"

targets = ["arm64", "riscv64"]
```

Không flatten tables sai semantic.

---

# PHẦN XXIII — TOML KEYS

Hỗ trợ:

```text
bare key
quoted key
dotted key
```

Ví dụ:

```toml
compiler.target.arm64 = true
```

Duplicate key invalid phải reject.

Không silently overwrite nếu TOML spec cấm.

---

# PHẦN XXIV — TOML STRINGS

Hỗ trợ đúng theo spec:

```text
basic strings
literal strings
multiline basic strings
multiline literal strings
escapes
Unicode
```

Không dùng JSON string parser rồi giả định TOML giống JSON.

Có thể reuse common UTF utilities, nhưng grammar riêng.

---

# PHẦN XXV — INI

INI không có một standard duy nhất.

Do đó implementation phải định nghĩa dialect rõ.

API:

```vir
ini.parse(text)
ini.stringify(value)
```

Support tối thiểu:

```ini
name=Vir

[compiler]
target=arm64
opt=2
```

Phải quyết định và document:

```text
; comment
# comment
whitespace
duplicate key behavior
duplicate section behavior
quoted values
escaping
case sensitivity
```

Không tự suy diễn behavior khác nhau giữa parse và stringify.

---

# PHẦN XXVI — XML

Chỉ triển khai XML nếu có thể xây parser đúng.

API:

```vir
xml.parse(text)
xml.stringify(document)
```

Support:

```text
elements
attributes
text nodes
CDATA
comments
XML declaration
entity references
nested elements
self-closing tags
```

Phải validate:

```text
matching opening/closing tags
attribute syntax
quoted attributes
entities
```

---

# PHẦN XXVII — XML SECURITY

Không được vô tình đưa XXE vào stdlib.

External entity resolution phải:

```text
disabled by default
```

Không tự đọc:

```text
local files
network URLs
```

từ XML input.

Không resolve network resource trong parser mặc định.

Nếu DTD không hỗ trợ thì phải reject hoặc ignore theo contract rõ ràng.

Không có ambiguous behavior.

---

# PHẦN XXVIII — YAML

YAML chỉ được triển khai nếu implementation có thể tuân theo grammar đáng tin cậy.

Không implement kiểu:

```text
split(':')
indentation hack
```

rồi gọi là YAML.

Nếu chưa đủ nguồn lực:

```text
KHÔNG implement YAML trong stdlib giai đoạn này.
```

Thà không có còn hơn parser sai.

---

# PHẦN XXIX — BASE64

Triển khai:

```text
std.encoding.base64
```

API:

```vir
base64.encode(bytes)
base64.decode(text)
```

Có thể hỗ trợ:

```text
standard base64
URL-safe base64
padding
no-padding
```

Decode strict phải reject malformed input.

Không silently skip arbitrary invalid chars trừ khi mode cho phép.

---

# PHẦN XXX — HEX

Module:

```text
std.encoding.hex
```

API:

```vir
hex.encode(bytes)
hex.decode(text)
```

Support:

```text
upper
lower
```

Decode reject:

```text
odd digit count
invalid hex digit
```

---

# PHẦN XXXI — URL ENCODING

Module:

```text
std.net.url
```

hoặc:

```text
std.encoding.url
```

Tùy architecture hiện tại.

Support:

```vir
url.encode_component(...)
url.decode_component(...)
```

Nếu có URL parser:

```vir
url.parse(...)
```

phải phân biệt:

```text
scheme
host
port
path
query
fragment
userinfo
```

Không trộn percent encoding với form encoding.

---

# PHẦN XXXII — FORM URLENCODED

Nếu backend/web nằm trong scope stdlib:

```text
application/x-www-form-urlencoded
```

nên có module:

```text
std.net.form
```

hoặc utility tương ứng.

Support encode/decode key-value pairs.

Phải xử lý khác biệt:

```text
+
```

với:

```text
%20
```

đúng theo format.

---

# PHẦN XXXIII — COMMON ERROR MODEL

Các parser phải có error structure nhất quán.

Ví dụ:

```text
ParseError {
    kind
    offset
    line
    column
    message
}
```

Format-specific error có thể là:

```text
JsonError
CsvError
TomlError
IniError
XmlError
```

nhưng nên chia sẻ core metadata.

Không trả:

```text
-1
null
""
false
```

để biểu diễn mọi lỗi.

---

# PHẦN XXXIV — ERROR LOCATION

Parser text phải track:

```text
byte offset
line
column
```

Nếu column theo code point hay byte phải document.

Ưu tiên:

```text
offset = byte offset
line/column = human-readable source position
```

Không scan lại toàn input từ đầu mỗi lần error nếu tránh được.

---

# PHẦN XXXV — UTF-8

Text formats phải xử lý UTF-8 strict.

Support:

```text
ASCII
Vietnamese
Traditional Chinese
Simplified Chinese
Japanese
Korean
emoji
supplementary code points
```

Reject malformed sequences:

```text
invalid continuation byte
overlong encoding
truncated sequence
invalid scalar value
surrogate code point encoded directly
```

Không silently replace invalid UTF-8 trừ khi API explicit yêu cầu lossy mode.

---

# PHẦN XXXVI — BOM

Phải quyết định behavior với UTF-8 BOM.

Nếu format specification cho phép hoặc ecosystem thường gặp:

```text
EF BB BF
```

parser có thể accept ở đầu input.

Không accept BOM ở vị trí bất kỳ.

Behavior phải test.

---

# PHẦN XXXVII — MEMORY MODEL

Tất cả implementation phải tuân thủ memory model Vir.

Không:

```text
GC
hidden refcount
unsafe global allocator bypass
dangling borrowed reference
```

Phải xác định rõ lifetime:

```text
input
scratch
result
```

Ví dụ:

```text
Parser scratch memory
```

không được là backing storage cho returned value nếu scratch bị giải phóng khi parser return.

---

# PHẦN XXXVIII — OWNED VS BORROWED

Nếu parser muốn zero-copy string slices:

phải chứng minh lifetime input sống lâu hơn result.

Nếu chưa có lifetime representation đủ rõ:

ưu tiên correctness:

```text
copy strings vào owned result
```

sau đó mới tối ưu zero-copy.

Không tạo implicit dangling slice.

---

# PHẦN XXXIX — ARENA / REGION

Nếu stdlib sử dụng arena/region:

* dùng API memory chuẩn hiện tại của Vir;
* không tự viết allocator khác;
* parser scratch nên ở sub-region nếu phù hợp;
* result phải nằm ở region đúng lifetime.

Không promote memory tùy tiện để che lỗi lifetime.

---

# PHẦN XL — STREAMING ARCHITECTURE

Các format lớn nên có đường mở rộng streaming.

Sau parser DOM/value API:

```text
json.parse
csv.parse
xml.parse
```

architecture nên có khả năng thêm:

```text
JsonReader
CsvReader
XmlReader
```

hoặc token/event stream.

Không cần implement tất cả streaming ngay nếu infrastructure chưa có, nhưng không viết code khiến sau này phải rewrite toàn parser.

---

# PHẦN XLI — INTEGER SAFETY

Mọi index và length arithmetic phải kiểm tra overflow.

Ví dụ:

```text
index + 1
length + escape expansion
buffer capacity * 2
```

Không cho integer overflow dẫn đến out-of-bounds.

---

# PHẦN XLII — PARSER LOOP INVARIANT

Mỗi parsing loop phải đảm bảo:

```text
cursor tiến lên
```

hoặc:

```text
return
```

Không có loop có thể đứng yên vô hạn vì malformed input.

---

# PHẦN XLIII — BOUNDS SAFETY

Không được:

```text
input[cursor]
```

nếu chưa chứng minh:

```text
cursor < input.length
```

Lookahead:

```text
cursor + N
```

phải bounds-check trước.

Malformed/truncated input phải trả error.

Không crash.

---

# PHẦN XLIV — PERFORMANCE

Correctness trước.

Nhưng tránh design rõ ràng O(n²).

Không:

```text
append string bằng copy toàn buffer mỗi character
```

Không repeatedly scan lại input.

Không allocate object cho từng byte/token nếu không cần.

Target:

```text
O(n)
```

cho phần lớn parsing.

---

# PHẦN XLV — STRING BUILDER

Serializer nên dùng buffer/string builder.

Không:

```text
result = result + char
```

trong loop nếu mỗi lần gây copy toàn bộ string.

Nếu stdlib chưa có builder tốt, có thể xây primitive reusable:

```text
StringBuilder
ByteBuffer
```

nhưng không over-engineer.

---

# PHẦN XLVI — FILE SIZE

`fs.read()` phải xử lý:

```text
empty file
small file
large file
partial read
EINTR nếu platform có
short read
```

Không assume:

```text
read(fd, size) == size
```

Phải loop cho đến:

```text
EOF
```

hoặc đủ bytes theo contract.

---

# PHẦN XLVII — FILE WRITE

`fs.write()` phải xử lý short write.

Không assume một syscall write luôn ghi hết buffer.

Pseudo invariant:

```text
while total_written < length:
    write remaining
```

Handle error đúng.

---

# PHẦN XLVIII — ATOMIC WRITE

Nên cân nhắc API:

```vir
fs.write_atomic(path, data)
```

Implementation:

```text
write temp
flush nếu cần
rename
```

đặc biệt hữu ích cho config files.

Không bắt buộc nếu scope ban đầu chưa cần nhưng architecture không nên ngăn cản.

---

# PHẦN XLIX — FILE METADATA

Nếu đang hoàn thiện `std.fs`, cân nhắc:

```vir
fs.exists(path)
fs.is_file(path)
fs.is_dir(path)
fs.size(path)
fs.metadata(path)
```

Nhưng không để scope này làm chậm việc hoàn thiện parser formats.

---

# PHẦN L — DIRECTORY API

Có thể có:

```vir
fs.mkdir(path)
fs.mkdir_all(path)
fs.remove(path)
fs.remove_all(path)
fs.rename(...)
fs.copy(...)
fs.list_dir(...)
```

Nếu đã tồn tại thì giữ API.

Không rewrite subsystem unrelated chỉ để phục vụ data formats.

---

# PHẦN LI — PATH MODULE

Nếu path manipulation hiện đang scattered, cân nhắc module:

```text
std.path
```

Ví dụ:

```vir
path.join(...)
path.basename(...)
path.dirname(...)
path.extension(...)
path.normalize(...)
```

Nhưng path semantics phải platform-aware.

Không hard-code `/` ở public logic nếu Windows nằm trong target matrix.

---

# PHẦN LII — NO LIBC ASSUMPTION

Vir có định hướng runtime/system implementation độc lập.

Không tự thêm dependency libc chỉ vì implementation nhanh hơn nếu kiến trúc hiện tại tránh libc.

Nếu platform backend hiện sử dụng raw syscall/API thì tiếp tục đúng convention đó.

Không kéo dependency ngoài chỉ để parse JSON/TOML/CSV.

---

# PHẦN LIII — NO THIRD-PARTY PARSER

Không import external JSON/TOML/XML parser làm implementation chính.

Mục tiêu là Vir stdlib native.

Có thể đọc reference/spec để đảm bảo correctness nhưng implementation phải nằm trong codebase Vir.

---

# PHẦN LIV — COMPATIBILITY

Trước khi sửa:

1. scan module hiện có;
2. tìm public APIs;
3. tìm call sites;
4. tìm tests;
5. tìm runtime primitives liên quan;
6. xác định OS backend;
7. xác định memory conventions.

Sau đó mới implement.

Không rename API cũ tùy tiện.

Không xóa API vì cho rằng API mới đẹp hơn.

Nếu cần migrate:

```text
old API
    ↓
compatibility wrapper
    ↓
new implementation
```

---

# PHẦN LV — KHÔNG LÀM GIẢ

Nghiêm cấm:

```text
TODO
stub
placeholder
fake success
hardcoded fixture
special-case tests
```

Không được:

```text
if input == test_string:
    return expected
```

Không được bypass grammar chỉ để test pass.

---

# PHẦN LVI — TEST STRATEGY

Mỗi module cần:

```text
positive tests
negative tests
edge-case tests
round-trip tests
regression tests
stress tests
```

---

# PHẦN LVII — JSON TEST MATRIX

Test:

```text
null
bool
integer
negative
float
exponent
empty string
escaped string
Unicode
empty array
empty object
nested arrays
nested objects
mixed values
whitespace
surrogate pairs
```

Negative:

```text
unterminated string
unterminated array
unterminated object
invalid escape
invalid Unicode
trailing comma
missing colon
missing comma
leading zero
invalid exponent
trailing garbage
```

---

# PHẦN LVIII — CSV TEST MATRIX

Test:

```text
one row
many rows
empty field
empty row
quoted field
delimiter inside quote
quote escape
newline inside quote
CRLF
LF
trailing empty field
leading empty field
Unicode
large row
```

Malformed input behavior phải deterministic.

---

# PHẦN LIX — TOML TEST MATRIX

Test toàn bộ construct supported.

Bao gồm:

```text
keys
quoted keys
dotted keys
tables
nested tables
arrays
inline tables
array of tables
numbers
bool
string variants
datetime
Unicode
comments
```

Negative:

```text
duplicate keys
malformed number
invalid date
bad table syntax
invalid escape
```

---

# PHẦN LX — ENV TEST MATRIX

Test isolation.

Không sửa:

```text
PATH
HOME
USER
SHELL
```

trong tests.

Dùng key dạng:

```text
VIR_TEST_ENV_...
```

và cleanup sau test.

---

# PHẦN LXI — FUZZ MINDSET

Tất cả parser phải được viết với giả định:

```text
input hostile
```

Input có thể:

```text
empty
1 byte
random bytes
huge
deeply nested
truncated at every possible byte
```

Không:

```text
out-of-bounds
infinite loop
use-after-free
integer overflow
stack corruption
```

---

# PHẦN LXII — FUZZ TARGETS

Nếu repo có fuzz infrastructure, tạo targets cho:

```text
json.parse
csv.parse
toml.parse
ini.parse
xml.parse
base64.decode
url.decode
```

Invariant tối thiểu:

```text
never crash
never hang
never memory corrupt
```

---

# PHẦN LXIII — DIFFERENTIAL TESTING

Nếu có thể trong test/dev tooling, dùng reference implementations để kiểm tra fixtures.

Ví dụ:

```text
parse corpus với Vir
parse corpus với implementation chuẩn khác
compare semantic output
```

Không đưa reference dependency vào production stdlib.

---

# PHẦN LXIV — ROUND-TRIP

Mỗi serializer/parser cần:

```text
value
→ stringify
→ parse
→ equivalent value
```

Với formats canonicalization khác nhau, không yêu cầu text giống byte-for-byte.

Yêu cầu semantic equality.

---

# PHẦN LXV — CORPUS

Tạo corpus riêng:

```text
tests/data/json/
tests/data/csv/
tests/data/toml/
tests/data/ini/
tests/data/xml/
```

Bao gồm:

```text
valid/
invalid/
edge/
unicode/
regression/
```

Không nhồi tất cả test strings vào một file khổng lồ nếu khó maintain.

---

# PHẦN LXVI — DOCUMENTATION

Mỗi module phải document:

```text
Purpose
Public API
Supported standard/version
Encoding
Error behavior
Memory behavior
Examples
Known limitations
```

Không claim compliance quá mức.

Ví dụ:

```text
TOML 1.x support
```

chỉ được ghi nếu implementation thực sự support.

---

# PHẦN LXVII — NAMING CONSISTENCY

Ưu tiên naming:

```text
parse
stringify
encode
decode
```

Semantic:

```text
parse/stringify
```

dành cho structured textual formats.

```text
encode/decode
```

dành cho encoding transformations.

Ví dụ:

```vir
json.parse
json.stringify

base64.encode
base64.decode
```

---

# PHẦN LXVIII — OPTIONAL CONVENIENCE API

Sau khi core ổn định, có thể thêm:

```vir
json.read_file(path)
json.write_file(path, value)

toml.read_file(path)
toml.write_file(path, value)

csv.read_file(path)
csv.write_file(path, rows)
```

Nhưng phải implement bằng composition:

```text
fs.read + parser
serializer + fs.write
```

Không duplicate parser/file code.

---

# PHẦN LXIX — CONFIG WORKFLOW

Một workflow phải hoạt động sạch:

```vir
import env
import fs
import toml

let config_path = env.get_or("APP_CONFIG", "./config.toml")

let source = fs.read(config_path)
let config = toml.parse(source)
```

Và:

```vir
let output = toml.stringify(config)
fs.write(config_path, output)
```

---

# PHẦN LXX — JSON CONFIG WORKFLOW

```vir
import env
import fs
import json

let path = env.get_or("APP_CONFIG", "./config.json")

let content = fs.read(path)
let config = json.parse(content)

config["port"] = 8080

fs.write(path, json.stringify_pretty(config))
```

Các subsystem phải compose tự nhiên như vậy.

---

# PHẦN LXXI — SECURITY

Không để parser tự:

```text
open files
make network requests
execute commands
load plugins
resolve external entities
```

Parse phải là pure data operation ngoại trừ allocation.

I/O chỉ xảy ra khi caller gọi I/O API.

---

# PHẦN LXXII — RESOURCE LIMITS

Cân nhắc chống hostile input:

```text
maximum nesting
maximum token length
maximum resulting allocation
```

Nếu đặt limit:

* phải hợp lý;
* document;
* trả error;
* không panic.

Không đặt limit tùy tiện quá nhỏ.

---

# PHẦN LXXIII — ERROR RECOVERY

Core `parse()` strict có thể fail ngay khi gặp lỗi đầu tiên.

Không cần sophisticated recovery như compiler parser.

Mục tiêu:

```text
first deterministic useful error
```

Không cố sửa input.

---

# PHẦN LXXIV — THREAD SAFETY

Các parser phải tránh mutable global state.

`env` là ngoại lệ vì process environment bản chất global process state.

Document rõ:

```text
env.set / env.unset
```

thay đổi process-wide environment.

Nếu thread-safety platform khác nhau thì abstraction phải xử lý hoặc document.

---

# PHẦN LXXV — GLOBAL STATE

Không cache env variables mặc định.

Ví dụ:

```vir
env.get("PORT")
```

phải phản ánh environment hiện tại nếu trước đó có:

```vir
env.set("PORT", "9000")
```

Không snapshot toàn bộ env lúc startup rồi giữ mãi trừ khi API explicit nói đó là snapshot.

---

# PHẦN LXXVI — BUILD / MODULE ORGANIZATION

Không nhét tất cả vào một file.

Tách module hợp lý.

Ví dụ:

```text
stdlib/
    env/
        env.vri
        env_unix.vri
        env_windows.vri

    fs/
        fs.vri
        path.vri

    data/
        json/
            value.vri
            parser.vri
            writer.vri

        csv/
            parser.vri
            writer.vri

        toml/
            lexer.vri
            parser.vri
            writer.vri
            value.vri

        ini/
            parser.vri
            writer.vri

        xml/
            parser.vri
            writer.vri

    encoding/
        base64.vri
        hex.vri
```

Điều chỉnh theo module system hiện tại của Vir.

Không ép cấu trúc này nếu repo đã có convention khác.

---

# PHẦN LXXVII — SHARED INTERNAL UTILITIES

Có thể chia sẻ internal utility:

```text
UTF-8 decoder
line/column tracker
byte cursor
string builder
parse error location
```

Nhưng không tạo một abstraction quá generic gây khó debug.

Parser grammar-specific vẫn phải độc lập.

---

# PHẦN LXXVIII — KHÔNG COUPLE PARSERS

Không để TOML phụ thuộc JSON parser chỉ vì một số syntax giống nhau.

Không để XML parser phụ thuộc HTML behavior.

Không để CSV parser assume UTF text parsing giống JSON.

Reuse primitive thấp, không reuse grammar sai semantic.

---

# PHẦN LXXIX — DEFINITION OF DONE: ENV

`std.env` chỉ hoàn thành khi:

```text
get works
get_or works
has works
set works
unset works
empty vs missing distinguished
invalid key rejected
NUL safe
memory lifetime correct
tests pass
platform abstraction correct
```

---

# PHẦN LXXX — DEFINITION OF DONE: FORMAT

Một format chỉ hoàn thành khi:

```text
parser exists
serializer exists
positive tests pass
negative tests pass
Unicode tests pass
round-trip tests pass
malformed input does not crash
no TODO/stub
error location works
memory lifetime valid
documentation exists
```

---

# PHẦN LXXXI — IMPLEMENTATION ORDER

Làm tuần tự:

```text
Phase 1
- inspect existing stdlib/runtime architecture
- identify memory conventions
- identify OS abstraction conventions

Phase 2
- std.env

Phase 3
- std.fs primitives required by following work

Phase 4
- std.data.json

Phase 5
- std.data.csv

Phase 6
- std.data.toml

Phase 7
- std.data.ini

Phase 8
- std.encoding.base64
- std.encoding.hex
- URL percent encoding

Phase 9
- XML if architecture/resources permit

Phase 10
- YAML only if genuine compliant implementation is realistic
```

Không chuyển phase chỉ vì happy-path test pass.

---

# PHẦN LXXXII — KHÔNG PHÁ HỆ THỐNG HIỆN CÓ

Sau mỗi phase:

```text
build compiler
build stdlib
run existing test suite
run new tests
```

Nếu regression xuất hiện:

* tìm root cause;
* không xóa test;
* không weaken assertion;
* không disable feature;
* không bypass code path.

---

# PHẦN LXXXIII — REPORT CUỐI

Khi hoàn thành mỗi phase, báo cáo chính xác:

```text
Files added
Files changed
Public APIs
Internal APIs
Platform-specific code
Memory/lifetime design
Error model
UTF handling
Parser algorithm
Serializer algorithm
Tests added
Regression tests added
Performance considerations
Unsupported features
Known limitations
```

Nếu bất kỳ feature nào chưa hoàn thành, phải ghi:

```text
NOT IMPLEMENTED
```

Không được ghi:

```text
complete
production ready
fully compliant
```

nếu chưa đúng.

---

# PHẦN LXXXIV — NGUYÊN TẮC CUỐI CÙNG

Ưu tiên theo thứ tự:

```text
1. Correctness
2. Memory safety
3. Spec compliance
4. API stability
5. Portability
6. Performance
7. Convenience
```

Không đánh đổi correctness để code ngắn hơn.

Không đánh đổi memory safety để zero-copy.

Không đánh đổi portability để thuận tiện trên một OS.

Không làm implementation chỉ đủ chạy demo.

Mục tiêu cuối cùng là tạo một foundation standard library đủ chắc để các chương trình Vir thực tế có thể:

```text
đọc configuration
đọc/ghi structured data
giao tiếp API
xử lý dataset
đọc environment configuration
xây CLI
xây backend/server
xây system tools
```

mà không phải dựa vào libc hoặc third-party package cho các tác vụ nền tảng này.
