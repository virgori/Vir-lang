# Hướng dẫn & Tài liệu API Thư viện Chuẩn: `vir.data.json` & `vir.env`

Tài liệu này hướng dẫn chi tiết cách sử dụng các hàm trong hai thư viện chuẩn nền tảng cho backend của ngôn ngữ Vir:
1. **`vir.data.json`** (và alias `vir.json`): Xử lý, bóc tách, chuyển đổi và tạo dữ liệu JSON native.
2. **`vir.env`**: Truy xuất, ép kiểu an toàn và quản lý biến môi trường hệ thống.

---

## I. Thư viện `vir.data.json`

### 1. Import module
```vir
include vir.data.json
# hoặc: include vir.json
```

---

### 2. Các hàm tạo giá trị JSON (`JsonValue`)

Dùng để khởi tạo các node JSON nguyên thủy hoặc container:

| Hàm | Kiểu trả về | Mô tả |
|---|---|---|
| `json.null()` | `JsonValue` | Tạo giá trị `null` |
| `json.bool(b: bool)` | `JsonValue` | Tạo giá trị boolean (`true` hoặc `false`) |
| `json.number(n: int)` | `JsonValue` | Tạo giá trị số nguyên 64-bit |
| `json.string(s: string)` | `JsonValue` | Tạo giá trị chuỗi |
| `json.array()` | `JsonValue` | Tạo một mảng rỗng `[]` |
| `json.object()` | `JsonValue` | Tạo một đối tượng rỗng `{}` |

#### Ví dụ:
```vir
let v_null = json.null()
let v_num  = json.number(8080)
let v_str  = json.string("vir-backend")
let v_bool = json.bool(true)
let obj    = json.object()
let arr    = json.array()
```

---

### 3. Cầu nối mảng nguyên thủy (`Array Bridges`)

Chuyển đổi trực tiếp mảng mộc native của Vir sang `JsonValue` dạng mảng chỉ trong **1 dòng code**, không cần vòng lặp thủ công:

| Hàm | Tham số | Mô tả |
|---|---|---|
| `json.fromInts(values)` | `values: [int]` | Chuyển `[int]` thành `JsonValue` mảng số |
| `json.fromStrings(values)` | `values: [string]` | Chuyển `[string]` thành `JsonValue` mảng chuỗi |
| `json.fromBools(values)` | `values: [bool]` | Chuyển `[bool]` thành `JsonValue` mảng boolean |

#### Ví dụ:
```vir
let ports = json.fromInts([80, 443, 8080])
let tags  = json.fromStrings(["api", "auth", "v2"])
let flags = json.fromBools([true, false, true])

# Gán trực tiếp vào đối tượng JSON
json.set(obj, "ports", ports)
json.set(obj, "tags", tags)
json.set(obj, "flags", flags)
```

---

### 4. Bóc tách kiểu an toàn với giá trị mặc định (`Typed Getters`)

Trích xuất trực tiếp kiểu dữ liệu nguyên thủy từ `JsonValue` đối tượng. Nếu trường không tồn tại hoặc sai kiểu dữ liệu, hàm tự động trả về giá trị mặc định (`default`) mà không gây crash hay panic:

| Hàm | Tham số | Kiểu trả về | Mô tả |
|---|---|---|---|
| `json.getInt(obj, key, default)` | `obj: JsonValue, key: string, default: int` | `int` | Lấy số nguyên; trả về `default` nếu thiếu/sai kiểu |
| `json.getStr(obj, key, default)` | `obj: JsonValue, key: string, default: string` | `string` | Lấy chuỗi ký tự; trả về `default` nếu thiếu/sai kiểu |
| `json.getBool(obj, key, default)` | `obj: JsonValue, key: string, default: bool` | `bool` | Lấy boolean; trả về `default` nếu thiếu/sai kiểu |

> **Hỗ trợ UFCS:** Bạn có thể gọi trực tiếp theo cú pháp đối tượng: `obj.getInt(...)`, `obj.getStr(...)`, `obj.getBool(...)`.

#### Ví dụ:
```vir
let port     = json.getInt(req_obj, "port", 3000)
let hostname = json.getStr(req_obj, "host", "localhost")
let debug    = json.getBool(req_obj, "debug", false)

# Cú pháp UFCS (Method-call syntax):
let timeout = req_obj.getInt("timeout", 60)
let env_tag = req_obj.getStr("env", "production")
```

---

### 5. Kiểm tra và Unpack giá trị (`Tag & Unboxing`)

Sử dụng khi cần kiểm tra kiểu hoặc bóc tách giá trị từ một `JsonValue` tự do:

| Hàm | Tham số | Kiểu trả về | Mô tả |
|---|---|---|---|
| `json.kind(v)` / `v.kind()` | `v: JsonValue` | `int` | Trả về tag enum: `JsonType.Null`, `JsonType.Bool`, `JsonType.Number`, `JsonType.Str`, `JsonType.Array`, `JsonType.Object` |
| `json.as_int(v)` / `v.as_int()` | `v: JsonValue` | `int` | Đọc giá trị số nguyên bên trong node Number |
| `json.as_string(v)` / `v.as_string()` | `v: JsonValue` | `string` | Đọc con trỏ chuỗi bên trong node Str |
| `json.as_bool(v)` / `v.as_bool()` | `v: JsonValue` | `bool` | Đọc giá trị boolean bên trong node Bool |
| `json.is_null(v)` / `v.is_null()` | `v: JsonValue` | `bool` | Kiểm tra node có phải `null` không |

#### Ví dụ:
```vir
if v.kind() == JsonType.Number do
    let n = v.as_int()
end

if v.kind() == JsonType.Str do
    let s = v.as_string()
end
```

---

### 6. Thao tác trên Container (Object & Array)

| Hàm | Tham số | Mô tả |
|---|---|---|
| `json.set(obj, key, val)` | `obj: JsonValue, key: string, val: JsonValue` | Thêm hoặc cập nhật một cặp key-value vào object |
| `json.get(obj, key)` | `obj: JsonValue, key: string` | Trả về `Option(JsonValue)` (`Some(val)` hoặc `None`) |
| `json.has(obj, key)` | `obj: JsonValue, key: string` | Kiểm tra xem key có tồn tại trong object không (`bool`) |
| `json.push(arr, item)` | `arr: JsonValue, item: JsonValue` | Thêm một phần tử vào cuối array |
| `json.at(arr, idx)` | `arr: JsonValue, idx: int` | Lấy phần tử tại vị trí `idx` của array |
| `json.len(val)` / `count` / `size` | `val: JsonValue` | Trả về số lượng phần tử của object hoặc array |
| `json.key(obj, idx)` | `obj: JsonValue, idx: int` | Lấy tên key tại vị trí `idx` của object |
| `json.value(obj, idx)` | `obj: JsonValue, idx: int` | Lấy `JsonValue` tại vị trí `idx` của object |

---

### 7. Phân tích cú pháp & Tuần tự hóa (`Parse & Stringify`)

| Hàm | Mô tả |
|---|---|
| `json.read(s: string)` | Parse chuỗi JSON thành `Result(JsonValue, JsonParseError)`. |
| `json.write(val: JsonValue) -> string` | Tuần tự hóa `JsonValue` thành chuỗi JSON dạng compact. |
| `json.pretty(val: JsonValue) -> string` | Tuần tự hóa `JsonValue` thành chuỗi JSON có thụt đầu dòng (indent 2 spaces). |

#### Ví dụ:
```vir
let parse_result = json.read("{\"name\": \"Vir\", \"version\": 2}")
case parse_result
    Ok(data):
        let name = json.getStr(data, "name", "")
        let ver  = json.getInt(data, "version", 1)
    Err(e):
        # e chứa: e.msg, e.pos, e.line, e.col
        print e.msg
end
```

---

## II. Thư viện `vir.env`

### 1. Import module
```vir
include vir.env
```

---

### 2. Các hàm đọc giá trị môi trường có ép kiểu (`Typed Readers`)

Đọc biến môi trường và tự động chuyển đổi sang kiểu dữ liệu mong muốn với giá trị fallback an toàn:

| Hàm | Tham số | Kiểu trả về | Mô tả |
|---|---|---|---|
| `env.int(key, default)` | `key: string, default: int` | `int` | Đọc biến môi trường và parse thành số nguyên 64-bit (hỗ trợ số âm). Trả về `default` nếu không có hoặc không hợp lệ. |
| `env.str(key, default)` | `key: string, default: string` | `string` | Đọc biến môi trường dưới dạng chuỗi; trả về `default` nếu thiếu. Có alias là `env.string(...)`. |
| `env.bool(key, default)` | `key: string, default: bool` | `bool` | Đọc boolean với so khớp linh hoạt, không phân biệt hoa thường (`true/1/yes/on` -> `true`, `false/0/no/off` -> `false`). |
| `env.require(key)` | `key: string` | `Result(string, string)` | Bắt buộc biến môi trường phải tồn tại. Trả về `Ok(val)` nếu có; trả về `Err("Missing required environment variable: KEY")` nếu thiếu. |

> **Hỗ trợ UFCS:** Các hàm trên cũng có thể gọi dưới dạng `key.int(default)`, `key.str(default)`, `key.bool(default)`, `key.require()`.

#### Ví dụ:
```vir
# Đọc với giá trị mặc định (Zero-Alloc):
let port    = env.int("SERVER_PORT", 8080)
let host    = env.str("SERVER_HOST", "0.0.0.0")
let debug   = env.bool("ENABLE_DEBUG", false)

# Bắt buộc phải có biến cấu hình quan trọng:
let db_conf = env.require("DATABASE_URL")
case db_conf
    Ok(url):
        # Kết nối database với url
    Err(msg):
        # In thông báo lỗi rõ ràng: "Missing required environment variable: DATABASE_URL"
        env.panic(msg)
end
```

---

### 3. Các hàm quản lý môi trường cơ bản

| Hàm | Tham số | Kiểu trả về | Mô tả |
|---|---|---|---|
| `env.get(key)` | `key: string` | `Option(string)` | Trả về `Some(val)` nếu biến tồn tại, ngược lại trả về `None` |
| `env.get_or(key, fallback)` | `key: string, fallback: string` | `string` | Lấy giá trị chuỗi hoặc trả về `fallback` nếu thiếu |
| `env.has(key)` | `key: string` | `bool` | Kiểm tra biến môi trường có tồn tại không |
| `env.set(key, val)` | `key: string, val: string` | `void` | Đặt hoặc ghi đè giá trị biến môi trường |
| `env.remove(key)` | `key: string` | `void` | Xóa biến môi trường |
| `env.keys()` | không | `[string]` | Danh sách tên tất cả các biến môi trường hiện có |
| `env.values()` | không | `[string]` | Danh sách giá trị tất cả các biến môi trường hiện có |
| `env.count()` | không | `int` | Số lượng biến môi trường hiện thời |
| `env.clear()` | không | `void` | Xóa toàn bộ bảng biến môi trường trong tiến trình |

---

### 4. Tiện ích Hệ thống & Tiến trình (`Process Utilities`)

Thư viện `vir.env` cũng tích hợp sẵn các tiện ích điều khiển tiến trình hệ thống:

| Hàm | Kiểu trả về | Mô tả |
|---|---|---|
| `env.args()` | `[string]` | Danh sách các đối số dòng lệnh (`argv`) truyền vào tiến trình |
| `env.program_name()` | `string` | Tên của file thực thi (`argv[0]`) |
| `env.cwd()` | `string` | Thư mục làm việc hiện tại |
| `env.home_dir()` | `string` | Thư mục người dùng (`$HOME`) |
| `env.temp_dir()` | `string` | Thư mục tạm thời (`$TMPDIR` hoặc `/tmp`) |
| `env.current_os()` | `int` | Mã định danh hệ điều hành (Darwin, Linux, Windows...) |
| `env.current_arch()` | `int` | Mã kiến trúc CPU (ARM64, x86_64, RISC-V...) |
| `env.os_name()` | `string` | Tên hệ điều hành dạng chuỗi (`"macos"`, `"linux"`...) |
| `env.arch_name()` | `string` | Tên kiến trúc CPU dạng chuỗi (`"arm64"`, `"x86_64"`...) |
| `env.exit(code: int)` | `void` | Thoát tiến trình ngay lập tức với mã thoát `code` |
| `env.abort()` | `void` | Hủy tiến trình bất thường (SIGABRT) |
| `env.panic(msg: string)` | `void` | In thông báo lỗi ra stderr và dừng tiến trình |

---

## III. Kịch bản Mẫu Thực Tế (Full Production Example)

Dưới đây là một ví dụ hoàn chỉnh về việc khởi động backend service: đọc cấu hình qua `vir.env`, xử lý payload qua `vir.data.json`, và sinh phản hồi:

```vir
include vir.env
include vir.data.json

func handle_request(raw_payload: string) -> string:
    # 1. Parse JSON đầu vào
    let parsed = json.read(raw_payload)
    case parsed
        Ok(req):
            # 2. Đọc an toàn các trường với default fallback (Zero-Alloc)
            let user_id  = json.getInt(req, "user_id", -1)
            let username = json.getStr(req, "username", "anonymous")
            let is_admin = json.getBool(req, "is_admin", false)

            # 3. Tạo phản hồi JSON
            let resp = json.object()
            json.set(resp, "status", json.string("success"))
            json.set(resp, "user_id", json.number(user_id))
            json.set(resp, "username", json.string(username))
            json.set(resp, "is_admin", json.bool(is_admin))

            # 4. Gán danh sách quyền và cổng bằng Array Bridge
            let roles = ["reader", "editor"]
            json.set(resp, "roles", json.fromStrings(roles))

            out json.write(resp)

        Err(err):
            let err_resp = json.object()
            json.set(err_resp, "status", json.string("error"))
            json.set(err_resp, "message", json.string(err.msg))
            out json.write(err_resp)
    end
end.

func main:
    # 1. Load cấu hình máy chủ từ biến môi trường
    let port    = env.int("SERVER_PORT", 8080)
    let host    = env.str("SERVER_HOST", "127.0.0.1")
    let debug   = env.bool("SERVER_DEBUG", false)
    let db_res  = env.require("DATABASE_URL")

    var db_url = ""
    case db_res
        Ok(url):
            db_url = url
        Err(msg):
            # Thiếu cấu hình bắt buộc -> Dừng khởi động
            env.panic(msg)
    end

    # 2. Thử nghiệm xử lý một request
    let test_body = "{\"user_id\": 101, \"username\": \"alice\", \"is_admin\": true}"
    let response_json = handle_request(test_body)
    
    # 3. Thoát bình thường
    out 0
end.
```

---

## IV. Lưu ý Kỹ thuật & Thực tiễn Tốt nhất (Best Practices)

1. **Tránh xung đột tên hàm tự do khi `include` đồng thời:**
   Cả `vir.env` và `vir.data.json` đều có phương thức `set` và `get`. Do Vir không có function overloading theo kiểu dữ liệu tham số, khi gọi các hàm này nên luôn gọi thông qua namespace đại diện:
   - Viết `json.set(obj, key, val)` thay vì gọi hàm tự do trần `set(...)`.
   - Viết `env.set(key, val)` thay vì gọi hàm tự do trần `set(...)`.
2. **Hiệu năng & Cấp phát bộ nhớ:**
   - Các hàm getter `json.getInt`, `json.getStr`, `json.getBool` và `env.int`, `env.str`, `env.bool` hoàn toàn **Zero-Allocation**. Chúng đọc trực tiếp dữ liệu từ thanh ghi hoặc buffer sẵn có, không tạo thêm rác hay cấp phát động.
   - Các hàm `json.fromInts`, `json.fromStrings`, `json.fromBools` tạo cấu trúc mảng trực tiếp từ mảng native mà không thông qua bước serialize/deserialize chuỗi trung gian.
3. **Quản lý bộ nhớ:**
   - Thư viện tuân thủ 100% mô hình native Vir: không garbage collector, không kéo thư viện ngoài (`libc`), an toàn trong môi trường multithreading và coroutines.
