# Đặc tả Ngôn ngữ Vir v2.0

*Phiên bản: 2.0 | Ngày: 11 tháng 4, 2026 | Trạng thái: Tài liệu sống*
*Thay thế: v1.2 (Tháng 3, 2026)*

---

## Mục lục

1. [Tổng quan](#1-tổng-quan) — gồm [§1.1 Phân tầng Language / Compiler / Library](#11-phân-tầng-language--compiler--library)
2. [Chú thích (Comments)](#2-chú-thích-comments)
3. [Hệ thống Module](#3-hệ-thống-module)
4. [Kiểu dữ liệu](#4-kiểu-dữ-liệu)
5. [Biến & Hằng số](#5-biến--hằng-số)
6. [Hàm (Functions)](#6-hàm-functions)
7. [Entity & Packed Entity](#7-entity--packed-entity)
8. [Enum](#8-enum)
9. [Luồng điều khiển](#9-luồng-điều-khiển)
10. [Toán tử](#10-toán-tử)
11. [UFCS — Cú pháp gọi hàm đồng nhất](#11-ufcs--cú-pháp-gọi-hàm-đồng-nhất)
12. [Nội suy chuỗi](#12-nội-suy-chuỗi)
13. [Xử lý lỗi — throw / ensure / revert](#13-xử-lý-lỗi--throw--ensure--revert)
14. [Tham số — in / ref / out](#14-tham-số--in--ref--out)
15. [FFI — @bind](#15-ffi--bind)
16. [Register & Mold — Cấu trúc bit](#16-register--mold--cấu-trúc-bit)
17. [Thực thi lúc biên dịch — precomp](#17-thực-thi-lúc-biên-dịch--precomp)
18. [Điểm nhập — @entry](#18-điểm-nhập--entry)
19. [Mảng (Arrays)](#19-mảng-arrays)
20. [Dict & Map](#20-dict--map)
21. [Biểu thức Case](#21-biểu-thức-case)
22. [Async / Task](#22-async--task)
23. [Port — Điều phối tín hiệu giữa các Worker](#23-port--điều-phối-tín-hiệu-giữa-các-worker)
24. [GPU, SIMD & Atomic Primitives](#24-gpu-simd--atomic-primitives)
25. [UI / Reactive](#25-ui--reactive)
26. [AI / Học máy](#26-ai--học-máy)
27. [Intrinsics hệ thống](#27-intrinsics-hệ-thống)
28. [Hỗ trợ đa ngôn ngữ](#28-hỗ-trợ-đa-ngôn-ngữ)
29. [Từ khoá tham chiếu](#29-từ-khoá-tham-chiếu)
30. [Bảng ưu tiên toán tử](#30-bảng-ưu-tiên-toán-tử)
31. [Thay đổi so với v1.2](#31-thay-đổi-so-với-v12)

---

## 1. Tổng quan

Vir là một ngôn ngữ lập trình hệ thống biên dịch trực tiếp, có cấu trúc khối (block-scoped). Nó biên dịch sang ARM64 (Mach-O), x86-64 (ELF) và WebAssembly — không phụ thuộc bất kỳ thư viện nào (không libc, không linker).

**Nguyên tắc cốt lõi:**
- Khối định nghĩa (`func`, `entity`, `method`, `enum`, `register`, `mold`) mở bằng `:` và đóng bằng `end.`
- Khối điều khiển (`if` / `eif`) mở bằng `do` và đóng bằng `end`
- Dấu hai chấm `:` cũng dùng cho khai báo kiểu và ánh xạ key-value (dict, case, map)
- Dấu chấm phẩy tuỳ chọn (xuống dòng cũng là kết thúc câu lệnh)
- `out` thay `return`, `eif` thay `elif`, `skip` thay `continue`
- `when ... loop` thay `while`

```vir
func main:
    var name = "Vir"
    print("Hello from $name!")
end.
```

### 1.1 Phân tầng Language / Compiler / Library

Vir **không** gắn ngôn ngữ vào một runtime thực thi duy nhất (khác Go, Erlang, …). Mục tiêu là thay được mô hình concurrency / allocator mà **không đổi ngôn ngữ**, và chương trình không dùng thì **không mang** chi phí đó trong binary.

**Ranh giới cứng:**

| Thành phần | Trách nhiệm |
|------------|-------------|
| **Language** | Cú pháp, type system, ownership, lifetime, memory model |
| **Compiler** | Phân tích, tối ưu, codegen |
| **Library** | Thread, async executor, scheduler, actor, work stealing, ArenaPool |

#### Nguyên tắc: Compiler không được biết scheduler tồn tại

Cấu trúc song song cấp ngôn ngữ (ví dụ `parallel for`, nếu có) chỉ hạ xuống IR trung gian hoặc intrinsic — **không** sinh sẵn Worker, Scheduler, hay ArenaPool.

```text
parallel_begin
parallel_chunk
parallel_end
```

Backend / thư viện được chọn mới quyết định ánh xạ:

| Backend / lib | `parallel_*` thành |
|---------------|-------------------|
| A | `pthread` |
| B | work-stealing |
| C | OpenMP |
| D | tuần tự (serial) — zero overhead khi không song song |

Cùng một chương trình nguồn có thể chạy trên các implementation khác nhau:

```text
vir/thread/pthread     # Linux / POSIX
vir/thread/win32       # Windows
vir/thread/spin        # kernel / bare-metal
vir/thread/none        # embedded — serial hoá mọi parallel
```

Người dùng chọn bằng `include`, ví dụ:

```vir
include std.thread.pthread
# hoặc
include std.thread.worksteal
```

Ngôn ngữ không đổi. Compiler không đổi. Chỉ thay implementation.

#### Arena vs ArenaPool

Compiler **chỉ** biết **Arena** (bump, watermark, `arena:`, vùng Static/Stack — §4.5–4.6).

**ArenaPool**, chiến lược `mmap` / `malloc` / custom allocator, và việc Worker cho task mượn arena rồi `reset` — thuộc **Library**. Compiler không giả định pool tồn tại.

#### Zero-cost = không dùng thì không tồn tại trong binary

Zero-cost không chỉ nghĩa là “không chậm”, mà còn:

> **Không dùng thì không có trong binary.**

```vir
@entry
func main:
    print("Hello")
end.
```

Binary hợp lệ gần như C thuần:

```text
_start → main → syscall
```

Nếu binary tối giản vẫn chứa thread scheduler, work stealing, async executor, hay mailbox — đó là **vi phạm** nguyên tắc này.

#### Bản sắc kiến trúc

- **Ngôn ngữ** không áp đặt mô hình thực thi.
- **Compiler** không phụ thuộc một runtime cố định.
- **Thư viện** cung cấp các mô hình concurrency **cạnh tranh** với nhau.

Khi xuất hiện scheduler tốt hơn (Rayon, Tokio, TBB, …), Vir chỉ cần thêm một thư viện mới — không sửa ngôn ngữ, không sửa compiler, không bắt mọi chương trình trả phí cho mô hình cũ. Đặc tả đầy đủ: [`VIR_EXECUTION_MODEL.md`](VIR_EXECUTION_MODEL.md). Tóm tắt EN: [`RUNTIME_SEPARATION.md`](RUNTIME_SEPARATION.md).

---

## 2. Chú thích (Comments)

```vir
# chú thích dòng đơn

##
  chú thích khối
  trải nhiều dòng
##
```

---

## 3. Hệ thống Module

Vir quản lý mã nguồn theo cơ chế **Ánh xạ Thư mục**. Compiler sử dụng dấu chấm `.` để duyệt cây thư mục và xây dựng Đồ thị Phụ thuộc (Dependency Graph) nhằm tránh nạp chồng.

### 3.1 Thứ tự khai báo

Module tuân thủ thứ tự nghiêm ngặt:

```
include → import/get → const → var → entity → func → export → share
```

### 3.2 Include — Nhúng toàn bộ file/lib

`include` là **nạp vật lý toàn bộ module** vào đồ thị biên dịch. Nó dùng khi muốn nhúng cả file/lib và cho phép truy cập qua namespace.

```vir
include math;                                   # nhúng math.vri
include net.http;                               # nhúng net/http.vri
include net.http as web;                        # nhúng net/http.vri, namespace cục bộ là web
include math, io.file as file, net.http as web; # nhúng nhiều module trên 1 dòng với alias
```

**Cơ chế ánh xạ:** `A.B.C` → tìm file `A/B/C.vri` từ gốc dự án.

### 3.3 Import — Nhập symbol đã export vào scope hiện tại

`import` **không yêu cầu phải include trước**. Nó chỉ lấy các symbol đã `export` từ file/module đích vào phạm vi hiện tại.

**Cú pháp chuẩn Vir v2.0:**

```vir
import add from math;               # nhập 1 hàm đã export
import add, sub from math;          # nhập nhiều hàm đã export
import from net.http;               # nhập toàn bộ symbol đã export
import get from net.http as fetch;  # alias tại scope hiện tại
```

> Dạng `from math import add` chỉ là tương thích cũ; **không phải cú pháp chuẩn ưu tiên** của Vir v2.0.

### 3.4 Get — Nhập biến/hằng vào phạm vi cục bộ

```vir
get MAX_RETRY from net.config;   # dùng MAX_RETRY trực tiếp
get PI from math as TAU;         # đổi tên
```

### 3.5 Export / Share / Port

```vir
export add, subtract;            # xuất hàm cho module khác
share counter, mode;             # chia sẻ biến module-level (dữ liệu thô, cùng tiến trình)
port signals, commands;          # kênh tín hiệu có tên (phối hợp giữa worker)
```

**`share`/`ref` so với `port`:**

| | `share` / `ref` | `port` |
|---|---|---|
| Mục đích | Truyền dữ liệu thô giữa module trong cùng tiến trình | Phối hợp tín hiệu giữa các worker / task |
| Mô hình truy cập | Đọc/ghi bộ nhớ trực tiếp | Gửi/nhận thông điệp (hàng đợi) |
| Sở hữu | Borrow (`&`) hoặc move | Copy thông điệp — bên gửi không giữ handle |
| Điển hình | Framebuffer, âm thanh, bảng tra cứu | Gateway ↔ Satellite node, producer ↔ consumer |
| Chặn | Không | `recv` chặn đến khi có tin (hoặc timeout) |

### 3.6 Import kết hợp

```vir
import add, subtract, get counter, mode from math;
```

### 3.7 Sử dụng

```vir
func main:
    var resp = http.get("/api")     # gọi có tiền tố namespace
    var resp2 = fetch("/api")       # gọi qua alias import
    print MAX_RETRY                 # hằng số đã import
end.
```

### 3.8 Đồ thị Phụ thuộc

Mỗi khi bắt gặp `include`, `import`, hoặc `get`, Compiler thực hiện các bước:

1. **Kiểm tra cache:** Module đường dẫn `A.B.C` đã có trong bộ nhớ chưa?
2. **Kiểm tra vòng:** Nếu module đang ở trạng thái `DangParse` → báo lỗi `"Phụ thuộc vòng: A.B.C"`
3. **Ánh xạ:** `A.B.C` → `A/B/C.vri`, nạp và parse file nguồn
4. **Đăng ký:** Thêm các định danh vào bảng ký hiệu (Symbol Table) của module hiện tại

Trạng thái module: `ChuaNap` → `DangParse` → `DaParse`

**Lazy Import — nới lỏng phụ thuộc vòng cho kiểu dữ liệu:**

Khi hai module phụ thuộc lẫn nhau về *kiểu* (không cần logic thực thi), dùng `lazy` để trì hoãn phân giải:

```vir
# gateway.vri
lazy include satellite;              # chỉ nhập kiểu, không parse toàn bộ

entity GatewayConfig:
    satellites: array[satellite.SatInfo]     # dùng kiểu từ satellite
end.
```

```vir
# satellite.vri
lazy include gateway;                # ngược lại cũng lazy

entity SatStatus:
    gw: gateway.GatewayConfig               # dùng kiểu từ gateway
end.
```

**Quy tắc `lazy`:**

| Thuộc tính | Hành vi |
|-----------|--------|
| Phân giải | Chỉ parse **khai báo kiểu** (`entity`, `enum`, `mold`, `register`) trong module đích |
| Hàm / logic | **Không** có sẵn — gọi hàm từ module `lazy` là lỗi biên dịch |
| Trạng thái | `ChuaNap` → `DangParseLazy` → `DaParseLazy`; chuyển `DaParse` đầy đủ khi có `include` không lazy |
| Vòng | Cho phép — hai module `lazy include` lẫn nhau là hợp lệ |
| Kích hoạt | `lazy include A;` hoặc `lazy import SomeType from A;` |

> **Hạn chế:** `lazy` chỉ phân giải kiểu — sử dụng hằng số (`const`), hàm, hoặc biến `share` từ module lazy yêu cầu nâng cấp thành `include` đầy đủ.

---

## 4. Kiểu dữ liệu

### 4.1 Kiểu nguyên thuỷ

| Nhóm | Kiểu | Kích thước | Mô tả |
|------|------|-----------|--------|
| **Số nguyên có dấu** | `i8`, `i16`, `i32`, `i64` | 1, 2, 4, 8 byte | Bù hai (2's complement) |
| **Số nguyên không dấu** | `u8`, `u16`, `u32`, `u64` | 1, 2, 4, 8 byte | Thanh ghi, bộ đếm, dữ liệu thô |
| **Số nguyên linh hoạt** | `int`, `uint` | Theo CPU | 8 byte trên hệ 64-bit |
| **Số thực** | `float` | 8 byte | Chấm động IEEE 754 |
| **Logic** | `bool` | 1 byte | `true` hoặc `false` |
| **Chuỗi** | `string` | Con trỏ + độ dài | Bất biến, Arena-allocated |
| **Con trỏ** | `ptr` | Theo CPU | Con trỏ thô, tương thích FFI |

### 4.2 Kiểu phức hợp

| Kiểu | Mô tả | Ngữ nghĩa |
|------|--------|----------|
| `entity` | Bản ghi có tên (struct) | **Move** |
| `packed entity` | Bố trí liên tiếp, không padding (FFI/mmap) | **Move** |
| `enum` | Hằng số nguyên có tên | **Copy** |
| `register` | Ánh xạ bit thanh ghi phần cứng | **Copy** |
| `mold` | Bit-field đa dụng (đóng gói dữ liệu) | **Copy** |
| `array` | Mảng động co giãn | **Move** |
| `dict` | Từ điển khoá-giá trị | **Move** |
| `map` | Biểu thức biến đổi (transformation) | biểu thức |
| `flux<T,N>` | Vector SIMD kích thước cố định — N phần tử kiểu T | **Copy** |
| `deck` | Buffer chia sẻ CPU-GPU (có kiểu, cố định) | **Move** (handle) |

### 4.3 Giá trị trực tiếp (Literals)

```vir
42                        # int
3.14                      # float
"hello"                   # chuỗi
"Hello $name"             # chuỗi nội suy
true / false              # boolean
none                      # null
[1, 2, 3]                 # mảng (list)
["a": 1, "b": 2]          # dict (có : là dict)
```

**Quy tắc phân biệt List và Dict:** Cùng dùng `[]`. Nếu phần tử có `:` thì là Dict, không có thì là List.

### 4.4 Chú thích kiểu (Type Annotations)

Chú thích kiểu là tuỳ chọn cho biến cục bộ (tự suy luận), nhưng **bắt buộc** cho FFI và field của packed entity.

```vir
var x = 42               # suy luận là int
var y: i32 = 42           # chỉ định i32
func add(a: i32, b: i32) -> i32:
    out a + b
end.
```

### 4.5 Kiến trúc bộ nhớ

Vir sử dụng ba vùng nhớ, không có garbage collector:

| Vùng | Cấp phát | Thu hồi | Dùng cho |
|------|----------|---------|----------|
| **Stack** | Tự động (push/pop) | Khi hàm kết thúc | Biến cục bộ, tham số, giá trị tạm |
| **Arena** | Bump allocator | Toàn bộ arena khi scope kết thúc | Entity, string động, array, dict |
| **Static** | Compile-time | Không bao giờ | `const`, string literal, `precomp` |

**Arena allocator:**
- Cấp phát bằng bump pointer — O(1), không phân mảnh
- Không giải phóng từng đối tượng — giải phóng toàn bộ arena cùng lúc
- Mỗi hàm `main` (hoặc scope lớn) tạo một arena mặc định
- Không cần GC, không cần reference counting
- **ArenaPool / chiến lược cấp phát nền (mmap, malloc, …)** thuộc thư viện — compiler chỉ thấy Arena (§1.1)

**String:**
- Immutable — mọi thao tác nối/nội suy tạo string mới
- Nội bộ: `{ ptr: *u8, len: u64 }`
- String literal → vùng Static (zero-cost, không cấp phát runtime)
- Nội suy / nối chuỗi → cấp phát trong Arena

**Không có ownership/borrow:**
Vir không có hệ thống ownership/borrow như Rust. Arena đảm bảo mọi đối tượng sống đến cuối scope. Cho FFI hoặc bare-metal cần quản lý thủ công, dùng `ptr` + `malloc`/`free` qua `@bind(c)`.

### 4.6 Khối Sub-arena — `arena:`

Vòng lặp chạy dài (server, event loop, xử lý stream) sẽ cạn kiệt arena mặc định vì bump pointer không bao giờ tua lại. Khối `arena:` tạo **sub-arena tạm thời** tự huỷ sau mỗi lần lặp hoặc khi thoát khối.

```vir
func serve_forever:
    loop
        var conn = accept()

        arena:
            # Mọi cấp phát ở đây (string, entity, array)
            # sống trong sub-arena mới
            var req = parse_request(conn)
            var resp = build_response(req)
            send(conn, resp)
        end
        # Sub-arena giải phóng ở đây — thu hồi toàn bộ bộ nhớ request
    end
end.
```

**Ngữ nghĩa:**

| Thuộc tính | Hành vi |
|----------|----------|
| Phạm vi | Block-scoped — giải phóng khi gặp `end` |
| Lồng nhau | `arena:` có thể lồng; mỗi khối có bump pointer riêng |
| Dung lượng mặc định | Compiler chọn (vd. 64KB); tuỳ chỉnh qua `arena(capacity: 256KB):` |
| Tương tác với `try` | `arena:` trong `try:` được giải phóng trước khi `revert` cục bộ chạy |
| Biến stack | Không ảnh hưởng — chỉ đối tượng heap (entity, string, array, dict) dùng sub-arena |

**Với dung lượng tường minh:**

```vir
arena(capacity: 1MB):
    var big_buf = arr_new(100000)
    process(big_buf)
end
```

**Quy tắc:** Đối tượng cấp phát trong `arena:` không được thoát ra ngoài khối. Compiler phát cảnh báo nếu tham chiếu đến đối tượng arena-local được lưu vào biến có thời gian sống vượt quá khối.

### 4.7 Allocator API

```vir
# Arena mặc định — tự động tạo bởi compiler cho `main`
var buf = arena_alloc(1024)           # cấp phát 1024 byte từ arena hiện tại
arena_reset()                          # giải phóng toàn bộ cấp phát arena cùng lúc

# Arena tuỳ chỉnh cho các hệ thống con
var scratch = arena_new(64 * 1024)     # arena 64KB
var ptr = arena_alloc_from(scratch, 512)
arena_free(scratch)                    # giải phóng toàn bộ
```

### 4.8 Ownership, Borrow Checker và Move Semantics

Vir có một **borrow checker thời biên dịch** đảm bảo an toàn bộ nhớ mà không cần garbage collector hay reference counting. Borrow checker chạy như một compiler pass sau IR lowering, trước codegen.

#### Quy tắc Ownership

```
Quy tắc 1:  Mỗi value có ĐÚNG MỘT owner tại mọi thời điểm.
Quy tắc 2:  Khi owner thoát khỏi scope → value bị DROP tự động.
Quy tắc 3:  Value có thể được BORROW:
                &     = shared borrow    (chỉ đọc, nhiều đồng thời)
                &mut  = exclusive borrow (đọc-ghi, một tại một thời điểm)
Quy tắc 4:  Shared borrow (&) và mutable borrow (&mut) KHÔNG đồng thời tồn tại.
Quy tắc 5:  Borrow KHÔNG sống lâu hơn owner.
Quy tắc 6:  MOVE chuyển ownership — owner cũ trở nên không hợp lệ.
```

**Phân loại kiểu:**

| Loại | Kiểu | Ngữ nghĩa |
|------|------|-----------|
| **Copy** | `int`, `i8`–`i64`, `u8`–`u64`, `float`, `bool` | Copy ngầm — không cần borrow |
| **Static** | String literal | Lifetime tĩnh — không cần borrow/move |
| **Move** | `string`, `array`, `entity`, `dict` | Move khi gán; borrow bằng `&`/`&mut` |

#### Cú pháp Ownership

```vir
# Tham số owned — caller move value vào
func process(data: [i32]) -> [i32]:
    out data                        # ownership chuyển cho caller
end.

# Shared borrow — chỉ đọc, không tiêu thụ
func tong_tat_ca(data: &[i32]) -> int:
    var total = 0
    for x in data do
        total = total + x
    end
    out total
end.

# Mutable borrow — quyền ghi độc quyền
func xoa_phan_tu_dau(data: &mut [i32]):
    data[0] = 0
end.
```

#### Move semantics

```vir
# Kiểu Copy — gán là copy, bản gốc vẫn hợp lệ
let x = 10
let y = x           # COPY — x vẫn hợp lệ
print(x + y)        # OK

# Kiểu Move — gán chuyển ownership
let arr = [1, 2, 3]
let arr2 = arr      # MOVE — arr không còn hợp lệ
# print(arr[0])     # LỖI BIÊN DỊCH: dùng giá trị đã move 'arr'

# Để giữ bản gốc, dùng borrow
let s = tong_tat_ca(&arr2)   # shared borrow — arr2 vẫn hợp lệ sau đó
```

#### Xung đột borrow

```vir
let arr = [1, 2, 3]

# OK — nhiều shared borrow
let s1 = tong_tat_ca(&arr)
let s2 = tong_tat_ca(&arr)   # &arr + &arr → OK

# LỖI — shared + mutable borrow chồng chéo
let r = &arr                    # shared borrow bắt đầu
xoa_phan_tu_dau(&mut arr)       # LỖI BIÊN DỊCH: không thể borrow &mut
                                # trong khi shared borrow còn sống
print(r[0])                     # r vẫn trong scope → xung đột
```

#### Auto-drop và phạm vi arena

Đối tượng cấp phát trong arena (`array`, `entity`, `string`, `dict`) được drop tự động khi owner thoát khỏi scope. Borrow checker chèn lệnh drop `Q_FREE` tại đúng vị trí — không cần gọi `free()`.

```vir
func vi_du:
    let arr = [1, 2, 3]     # cấp phát trong function arena
    if dieu_kien do
        let tmp = [4, 5]    # cấp phát trong scope arena (watermark)
        xu_ly(tmp)
    end                      # tmp bị drop ở đây (watermark restore)
    print(arr[0])            # arr vẫn còn sống
end.                          # arr bị drop ở đây (function arena reset)
```

Đối tượng **thoát** ra caller (qua `out` hoặc move-return) được escape analysis đưa lên heap — caller sở hữu chúng và chúng bị drop khi scope caller kết thúc.

#### Vị trí borrow checker trong pipeline

```
AST → ir_lower → Q-IR → TCO pass → ★ Borrow Check ★ → Optimizer → Codegen
                                          │
                                          ├── Suy luận ownership
                                          ├── Kiểm tra xung đột borrow
                                          ├── Phân tích lifetime
                                          └── Chèn điểm drop (Q_FREE)
```

**Chi phí biên dịch:** +5–10% thời gian biên dịch cho borrow check pass. Không có runtime overhead — tất cả kiểm tra được giải quyết tại thời điểm biên dịch.

---

## 5. Biến & Hằng số

### 5.1 Khai báo biến

```vir
var counter = 0           # có thể thay đổi, kiểu tự suy luận
var name: string = "Vir"  # có thể thay đổi, kiểu tường minh
let result = compute()    # không thể thay đổi sau khi gán
```

- `var` — biến có thể thay đổi (mutable)
- `let` — ràng buộc bất biến (immutable)

### 5.2 Hằng số

```vir
const PI = 3.14159
const MAX_SIZE = 1024
const BANNER = "Hello Vir"
```

Hằng số dùng `=` để gán giá trị (giống biến). Được tính tại thời điểm biên dịch, không thể gán lại.

### 5.3 Biến cấp module

```vir
var
    counter: int;
    mode: string
```

Biến cấp module có thể truy cập từ mọi hàm trong module. Dùng `share` để mở cho module khác.

**Quy tắc nhóm bằng dấu chấm phẩy:** Khi dòng kết thúc bằng `;`, dòng tiếp theo vẫn thuộc cùng nhóm `var` (không cần lặp lại từ khoá `var`). Khi dòng **không có** `;`, nhóm kết thúc.

```vir
var
    x: int;         # có ';' → dòng sau vẫn thuộc nhóm var
    y: int;         # có ';'
    z: int          # không ';' → kết thúc nhóm var
```

### 5.4 Gán lại

```vir
var x = 5
x = x + 1         # gán lại
x = compute(x)    # gán lại từ kết quả hàm
```

---

## 6. Hàm (Functions)

### 6.1 Hàm cơ bản

```vir
func add(a, b):
    out a + b
end.
```

- `func <tên>(<tham số>):` — định nghĩa hàm
- `out <biểu thức>` — trả về giá trị (thay thế `return`)
- `end` — đóng thân hàm

### 6.2 Tham số có kiểu

```vir
func add(a: int, b: int) -> int:
    out a + b
end.
```

### 6.3 Nhiều tham số

```vir
func clamp(value, lo, hi):
    if value < lo do
        out lo
    end
    if value > hi do
        out hi
    end
    out value
end.
```

### 6.4 Đối số có tên

```vir
sum(a=5; b=10);     # gọi hàm với đối số có tên, ngăn cách bằng ;
```

### 6.5 Khai báo trước

```vir
has processData;     # khai báo trước khi định nghĩa
```

### 6.6 Hàm bậc cao (Higher-Order Functions)

Hàm có thể được truyền như giá trị:

```vir
func double(x):
    out x * 2
end.

func apply(f, value):
    out f(value)
end.

func main:
    var f = double        # con trỏ hàm
    print f(5)            # → 10
    print apply(double, 7) # → 14
end.
```

### 6.7 Đệ quy

```vir
func factorial(n):
    if n <= 1 do
        out 1
    end
    out n * factorial(n - 1)
end.
```

### 6.8 Bảo vệ phạm vi (ensure / revert)

Xem [§13 Xử lý lỗi](#13-xử-lý-lỗi--throw--ensure--revert).

---

## 7. Entity & Packed Entity

### 7.1 Entity (cấu trúc)

```vir
entity User:
    name: string
    age: int
end.
```

**Tạo thực thể:**

```vir
var u = User(name: "Alice", age: 30)
print(u.name)          # truy cập field
u.age = 31             # gán field
```

**Bố trí nội bộ:** Arena-allocated, field được đánh địa chỉ theo chỉ mục slot.

### 7.2 Phương thức (Method)

Vir hỗ trợ phương thức được khai báo trực tiếp bên trong `entity`. Phương thức tự động nhận `this` là tham số ngầm định.

```vir
entity Account:
    balance: int

    method deposit(amount: int):
        this.balance = this.balance + amount
    end.

    method withdraw(amount: int):
        if amount > this.balance do
            throw 1
        end
        this.balance = this.balance - amount
    end.

    method get_balance: int
        out this.balance
    end.
end.

func main:
    var acc = Account(balance: 1000)
    acc.deposit(500)
    acc.withdraw(200)
    print(acc.get_balance())     # → 1300
end.
```

Ngoài ra, UFCS vẫn hoạt động — bất kỳ hàm nào có tham số đầu tiên tên `this` đều gọi được bằng cú pháp dấu chấm:

```vir
func display(this: User):
    print("User: $this.name, tuổi: $this.age")
end.

var u = User(name: "Alice", age: 30)
u.display()              # tương đương display(u)
```

Xem [§11 UFCS](#11-ufcs--cú-pháp-gọi-hàm-đồng-nhất) để biết chi tiết.

### 7.3 Packed Entity (cấu trúc gọn)

`packed entity` đảm bảo bố trí bộ nhớ liên tiếp, không padding — phục vụ FFI, memory-mapped I/O và giao thức nhị phân.

```vir
packed entity Vec2:
    x: int
    y: int
end.

packed entity TCPHeader:
    src_port: u16
    dst_port: u16
    seq_num: u32
    ack_num: u32
    flags: u16
end.
```

| Thuộc tính | `entity` | `packed entity` |
|-----------|----------|-----------------|
| Bố trí bộ nhớ | Arena slots | Liên tiếp, không padding |
| Truy cập field | Chỉ mục slot | Offset byte |
| Canh chỉnh | Phụ thuộc nền tảng | Canh 1 byte |
| Dùng cho | Mục đích chung | FFI, mmap, phần cứng |
| `sizeof` | Runtime | Compile-time (`Σ kích_thước_field`) |

**Sử dụng giống entity thường:**

```vir
var v = Vec2(x: 3, y: 4)
print(v.x)                 # → 3
```

---

## 8. Enum

```vir
enum Color:
    Red
    Green
    Blue
end.

enum Priority:
    Low
    Medium
    High
end.
```

**Truy cập:**

```vir
var c = Color.Red
if c == Color.Green do
    print("Đi!")
end
```

Giá trị enum là hằng số nguyên bắt đầu từ 0.

---

## 9. Luồng điều khiển

### 9.1 If / Eif / Else

```vir
if x > 10 do
    print(x)
eif x > 5 do
    print("trung bình")
else
    print("nhỏ")
end
```

- `eif` thay thế `elif`/`else if`
- `else` không có dấu hai chấm
- `end` đóng toàn bộ khối

### 9.2 Vòng When (while)

```vir
when x > 0 loop
    x = x - 1
end
```

### 9.3 Vòng For phạm vi

```vir
for i in 0..10 do
    print i         # in từ 0 đến 9
end
```

### 9.4 Vòng Loop (vô hạn)

```vir
loop
    if done do
        break
    end
end
```

### 9.5 Loop N (đếm)

```vir
loop 5:
    print 7         # in 7 năm lần
end
```

### 9.6 Break / Skip

```vir
break        # thoát vòng lặp gần nhất
skip         # nhảy sang vòng tiếp theo (thay thế 'continue')
```

---

## 10. Toán tử

### 10.1 Số học

| Toán tử | Mô tả | Ưu tiên |
|---------|-------|---------|
| `^` | Luỹ thừa | 30 |
| `*` | Nhân | 20 |
| `/` | Chia | 20 |
| `%` | Phần trăm | 18 |
| `mod` | Phần dư (modulo) | 18 |
| `+` | Cộng | 10 |
| `-` | Trừ | 10 |

### 10.2 So sánh

| Toán tử | Mô tả | Ưu tiên |
|---------|-------|---------|
| `==` | Bằng | 5 |
| `!=` | Khác | 5 |
| `?=` | Bằng an toàn (nil-safe) | 5 |
| `?=/=` | Khác an toàn | 5 |
| `>` | Lớn hơn | 6 |
| `<` | Nhỏ hơn | 6 |
| `>=` | Lớn hơn hoặc bằng | 6 |
| `<=` | Nhỏ hơn hoặc bằng | 6 |

### 10.3 Logic

| Toán tử | Mô tả | Ưu tiên |
|---------|-------|---------|
| `&` | AND logic | 3 |
| `\|\|` | OR logic | 2 |
| `!` | NOT logic (unary) | 28 |

### 10.4 Thao tác bit

| Từ khoá | Mô tả | Ưu tiên |
|---------|-------|---------|
| `and` | AND bit | 3 |
| `or` | OR bit | 2 |
| `xor` | XOR bit | 2 |
| `shl` | Dịch trái | 12 |
| `shr` | Dịch phải | 12 |

### 10.5 Đặc biệt

| Toán tử | Mô tả | Ưu tiên |
|---------|-------|---------|
| `.` | Truy cập thành viên / gọi UFCS | 40 |
| `?.` | Truy cập thành viên an toàn | 40 |
| `?` | Kiểm tra tồn tại | — |
| `:~` | So khớp mẫu | 8 |
| `>>` | Ép kiểu | 12 |
| `as` | Chuyển đổi kiểu | 12 |

### 10.6 Phép gán

```vir
x = 10               # gán đơn giản
x = x + 1            # phép gán rõ ràng (không có += — tường minh tốt hơn)
```

---

## 11. UFCS — Cú pháp gọi hàm đồng nhất

Bất kỳ hàm nào cũng có thể gọi bằng cú pháp dấu chấm trên đối số đầu tiên. Điều này cho phép gọi như phương thức mà không cần hệ thống class.

### 11.1 UFCS cơ bản

```vir
func double(val):
    out val * 2
end.

func add_n(val, n):
    out val + n
end.

var x = 10
var a = x.double()           # → double(10) → 20
var b = x.add_n(5)           # → add_n(10, 5) → 15
```

### 11.2 Từ khoá `this`

Khi tham số đầu tiên của hàm được đặt tên `this`, nó báo hiệu hàm được thiết kế cho UFCS:

```vir
func scale(this, n):
    out this * n
end.

func clamp(this, lo, hi):
    if this < lo do out lo end
    if this > hi do out hi end
    out this
end.

var x = 7
print x.scale(3)             # → 21
print x.clamp(0, 10)         # → 7
print 15.clamp(0, 10)        # → 10 (hoạt động trên literal)
```

### 11.3 Chuỗi UFCS (Chaining)

```vir
var result = x.double().add_n(3).clamp(0, 100)
# tương đương: clamp(add_n(double(x), 3), 0, 100)
```

### 11.4 UFCS trên Entity

```vir
entity User:
    name: string
    age: int
end.

func display(this: User):
    print("User: $this.name, tuổi: $this.age")
end.

var u = User(name: "Alice", age: 30)
u.display()                  # → display(u)
```

**Quy tắc giải quyết:**

| Cú pháp | Ý nghĩa |
|---------|---------|
| `x.foo` | Luôn là **truy cập field** — không bao giờ gọi hàm |
| `x.foo()` | Gọi hàm — xét theo thứ tự bên dưới |
| `x.foo(a, b)` | Gọi hàm có đối số — giải quyết như trên |

Khi compiler gặp `x.foo(args)`:
1. Nếu `foo` là `method` của entity type → gọi method (implicit `this`)
2. Nếu `foo` là **callable field** (field kiểu con trỏ hàm) → gọi gián tiếp qua giá trị field
3. Nếu tồn tại hàm `foo(x, args)` → gọi UFCS
4. Nếu không → lỗi biên dịch

Bước 2 cho phép pattern hướng sự kiện (event-driven) — entity field lưu callback:

```vir
entity Button:
    label: string
    on_click: ptr           # field con trỏ hàm
end.

func handle_click:
    print("đã nhấn!")
end.

var btn = Button(label: "OK", on_click: handle_click)
btn.on_click()              # bước 2 → gọi gián tiếp qua giá trị field
```

> **Lưu ý:** `btn.on_click` (không có ngoặc) vẫn là truy cập field — đọc con trỏ hàm. `btn.on_click()` (có ngoặc) **gọi** con trỏ hàm vì bước 2 nhận biết field chứa kiểu callable.

### 11.5 Field và Hàm — Không mờ hồ

Dấu ngoặc tròn là **ký hiệu phân biệt duy nhất** giữa truy cập field và gọi hàm:

```vir
entity User:
    name: string
end.

func name(this: User) -> string:
    out "hiển thị: $this.name"
end.

var u = User(name: "Alice")
print u.name               # → "Alice"              (truy cập field — không có ngoặc)
print u.name()             # → "hiển thị: Alice"    (gọi UFCS — có ngoặc)
```

Field và hàm có thể dùng cùng tên mà không xung đột. Compiler **không bao giờ đoán** — `x.foo` luôn là field, `x.foo()` luôn là gọi hàm.

---

## 12. Nội suy chuỗi

Vir hỗ trợ nội suy chuỗi bằng tiền tố `$` bên trong chuỗi ngoặc kép.

### 12.1 Nội suy biến

```vir
var name = "World"
print("Hello $name")         # → Hello World
```

### 12.2 Nội suy thuộc tính

```vir
var user = User(name: "Alice", age: 30)
print("Tên: $user.name")     # → Tên: Alice
```

### 12.3 Nội suy biểu thức

```vir
var price = 100
print("VAT: $(price * 10 / 100)")   # → VAT: 10
```

### 12.4 Thoát ký hiệu Dollar

```vir
print("Giá: $$100")          # → Giá: $100
```

### 12.5 Tóm tắt

| Loại | Cú pháp | Ví dụ | Kết quả |
|------|---------|-------|---------|
| Biến đơn | `$var` | `"Hello $name"` | `Hello World` |
| Thuộc tính | `$obj.prop` | `"User: $user.id"` | `User: 42` |
| Biểu thức | `$(expr)` | `"Tổng: $(a + b)"` | `Tổng: 15` |
| Thoát | `$$` | `"Giá: $$100"` | `Giá: $100` |

**Cơ chế nội bộ:** Lexer tách chuỗi nội suy thành token `InterpStart`/`InterpEnd` bao quanh token biến/biểu thức. IR hạ thành chuỗi `StrCat`, tự động wrap giá trị int bằng `i_to_str()`.

### 12.6 Quy tắc biên lexer

Nội suy `$` **không phải greedy**. Lexer chỉ tiêu thụ những gì ngữ pháp định nghĩa:

| Mẫu | Lexer tiêu thụ | Ví dụ | Kết quả |
|-----|--------------|-------|--------|
| `$ident` | Một định danh (chữ, số, `_`) | `"giá: $x"` | Giá trị `x` |
| `$ident.ident` | Định danh + `.` + định danh (một chuỗi dot) | `"tên: $user.name"` | Truy cập field |
| `$ident.ident.ident` | Tối đa N chuỗi dot | `"$a.b.c"` | Field lồng nhau |
| `$(expr)` | Mọi thứ trong `()` như một biểu thức | `"$(list[0])"` | Truy cập phần tử |
| `$ident[...]` | **Không tiêu thụ** — `[` dừng lexer | `"giá: $list[0]"` | ❌ in giá trị list + `"[0]"` literal |

**Quy tắc:** Dạng rút gọn `$` dừng tại **ký tự đầu tiên không phải định danh, không phải dấu chấm**. Dấu ngoặc vuông `[`, toán tử và khoảng trắng **không** được tiêu thụ. Với truy cập mảng/dict hoặc biểu thức phức tạp, dùng dạng `$(...)` :

```vir
var list = [10, 20, 30]
print("Sai:  $list[0]")          # → in giá trị list + literal "[0]"
print("Đúng: $(list[0])")        # → in "10"

var m = ["a": 1]
print("Sai:  $m[a]")             # → in giá trị m + literal "[a]"
print("Đúng: $(m[\"a\"])")        # → in "1"
```

**Tóm tắt:** `$ident` và `$ident.prop` là phím tắt tiện lợi. Với **mọi thứ phức tạp hơn** (truy cập chỉ mục, số học, gọi method), dùng `$(expr)`.

---

## 13. Xử lý lỗi — throw / ensure / revert

Vir sử dụng mô hình lỗi cục bộ hàm với ba từ khoá:

| Từ khoá | Vai trò | Tương đương |
|---------|---------|------------|
| `throw` | Ném lỗi, dừng luồng bình thường | `throw` (Java), `panic!` (Rust) |
| `ensure` | Code **luôn** chạy khi thoát hàm | `defer` (Go), `scope(exit)` (D) |
| `revert` | Code chạy **chỉ khi** có `throw` | `catch` (Java), `scope(failure)` (D) |

### 13.1 throw

```vir
func safe_div(a, b):
    if b == 0 do
        throw 1               # mã lỗi 1 = chia cho 0
    end
    out a / b
end.
```

Nếu hàm không có `revert`/`ensure`, `throw` sẽ dừng chương trình (emit ARM64 `BRK #1`).

### 13.2 ensure — Luôn thực thi khi thoát

`ensure` là từ khoá định hướng — không có dấu hai chấm, không tạo hàm mới. Nó đánh dấu phần code luôn chạy khi thoát hàm.

```vir
func process_file(path):
    var fd = open(path)
    # ... làm việc với file ...
    print(42)
ensure
    close(fd)                  # luôn chạy, kể cả khi throw
end.
```

**Output:** `42` rồi `close(fd)` thực thi.

`ensure` là khối cuối trước `end`. Nó chạy ở cả thoát bình thường lẫn khi lỗi.

### 13.3 revert — Thực thi chỉ khi có lỗi

`revert` cũng là từ khoá định hướng, không có dấu hai chấm.

```vir
func transfer(from, to, amount):
    withdraw(from, amount)
    deposit(to, amount)
ensure
    log("giao dịch hoàn tất hoặc đã rollback")
revert
    refund(from, amount)       # chỉ chạy nếu throw xảy ra
end.
```

### 13.4 Luồng kết hợp

```vir
func example:
    # code thân hàm chạy ở đây
    if bad_condition do
        throw 42
    end
    print("thành công")
ensure
    print("dọn dẹp")           # luôn chạy
revert
    print("xử lý lỗi")        # chỉ chạy khi throw
end.
```

**Thứ tự thực thi:**

| Kịch bản | Luồng |
|----------|-------|
| Thoát bình thường (không throw) | thân hàm → ensure → return |
| Thoát do throw | thân hàm → throw → revert → ensure → return |

### 13.5 Giá trị lỗi — `erx`

Giá trị được throw lưu trong thanh ghi lỗi `erx`. Khối `revert` có thể đọc nó:

```vir
func compute(x):
    if x < 0 do
        throw 1        # đầu vào âm
    end
    if x > 1000 do
        throw 2        # tràn
    end
    out x * x
revert
    # erx chứa 1 hoặc 2
    print("Đã xảy ra lỗi: $erx")
end.
```

### 13.6 Kiểu lỗi

Giá trị `throw` là số nguyên (`int`). Vir không có exception object — lỗi được biểu diễn bằng mã số:

| Dải mã | Ý nghĩa (quy ước) |
|--------|-------------------|
| 0 | Không lỗi |
| 1–99 | Lỗi logic ứng dụng |
| 100–199 | Lỗi I/O |
| 200–255 | Lỗi hệ thống |

Để mang thêm ngữ cảnh, kết hợp entity với mã lỗi:

```vir
entity Error:
    code: int
    message: string
end.

var last_error: Error

func safe_div(a, b):
    if b == 0 do
        last_error = Error(code: 1, message: "chia cho 0")
        throw 1
    end
    out a / b
end.
```

**Tại sao chỉ `int`?** — Giữ `throw`/`revert` đơn giản, zero-cost trên bare-metal. Mã lỗi lưu trong một thanh ghi duy nhất (ARM64: X19, x86-64: r12). Thông tin bổ sung truyền qua biến module-level hoặc `out` parameter.

### 13.7 try / revert — Xử lý lỗi cục bộ với bồi hoàn

`try:` tạo **ranh giới bắt lỗi cục bộ** bên trong thân hàm. Mỗi khối `try` có phần `revert` riêng để bồi hoàn cục bộ. Tính năng bổ sung: **timeout**, **isolate**, **resume retry**, **resume revert**, và **emit** cho ghi sự kiện có cấu trúc.

**Cấu trúc cơ bản:**

```vir
try:
    # thao tác rủi ro
revert
    # bồi hoàn / phục hồi cục bộ
end
```

**Có `timeout` — tự động huỷ sau thời hạn:**

```vir
try(timeout: 5s):
    download_large_file()
revert
    emit LOG_ERROR("Tải xuống hết hạn hoặc lỗi: $erx")
    resume revert
end
```

Tham số `timeout` là tuỳ chọn. Nếu thao tác vượt thời gian quy định, khối try bị huỷ và `revert` cục bộ chạy với mã lỗi timeout trong `erx`.

**`resume retry` — khởi động lại khối try hiện tại:**

Nếu `revert` cục bộ xác định lỗi có thể phục hồi, `resume retry` khởi động lại khối `try` từ đầu. Dùng biến đếm để tránh vòng lặp vô hạn.

**⚠ Cảnh báo trạng thái bẩn:** Vir không có transactional memory. Biến bị sửa đổi trước khi `throw` bên trong `try:` **giữ nguyên giá trị đã bị sửa** khi `resume retry` khởi động lại khối. Developer **phải** reset mọi trạng thái bẩn bên trong `revert` cục bộ trước khi gọi `resume retry`. Nếu không, retry chạy trên dữ liệu rác/hỏng.

```vir
var retry_limit = 3

try(timeout: 5s):
    connect_to_server()
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry           # khởi động lại khối try này
    end
    resume revert              # bỏ cuộc — lan truyền đến revert hàm
end
```

**Thực hành tốt — dọn dẹp trước retry:**

```vir
var retry_limit = 3;
    partial_result = 0

try:
    partial_result = buoc_mot()   # sửa partial_result
    buoc_hai(partial_result)      # có thể throw
revert
    partial_result = 0            # ← BẮT BUỘC reset trạng thái bẩn trước retry
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry
    end
    resume revert
end
```

Compiler phát **cảnh báo** nếu `resume retry` được dùng mà khối `revert` không gán lại bất kỳ biến nào đã bị sửa trong thân `try`. Đây là heuristic nỗ lực tốt nhất — luồng điều khiển phức tạp có thể cần kiểm tra thủ công.

**`isolate` — snapshot & khôi phục tự động:**

`isolate` là tham số của `try` cho phép khai báo tường minh danh sách biến bên ngoài mà Compiler tự động **snapshot lên Stack** khi vào `try` và **khôi phục** trước mỗi `resume retry`. Điều này loại bỏ nhu cầu reset thủ công trạng thái bẩn trong `revert`.

```vir
try(isolate: [retry_limit, partial_result]):
    partial_result = buoc_mot()
    buoc_hai(partial_result)
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry       # partial_result tự động khôi phục về giá trị trước try
    end
    resume revert
end
```

Có thể kết hợp với `timeout`:

```vir
try(timeout: 5s, isolate: [retry_limit]):
    ket_noi_may_chu()
revert
    retry_limit -= 1
    if retry_limit > 0 do
        resume retry
    end
    resume revert
end
```

**Ngữ nghĩa:**
- **Khi vào `try`:** giá trị snapshot của các biến trong danh sách `isolate` được đẩy lên stack frame bao ngoài (copy semantics; với Move type chỉ copy header/con trỏ — nội dung heap *không* được hoàn tác).
- **Khi `resume retry`:** các biến được **khôi phục** từ snapshot trước khi thân `try` khởi lại. Snapshot được giữ cho các lần retry tiếp theo.
- **Khi thoát bình thường hoặc `resume revert`:** snapshot bị huỷ.
- Biến **không** nằm trong danh sách `isolate` không bị ảnh hưởng — mutation của chúng vẫn còn hiệu lực.

**Phát hiện trạng thái bẩn lúc biên dịch (W302):**

Nếu Compiler phát hiện một biến:
1. Được khai báo **bên ngoài** khối `try`
2. Bị **đột biến** bên trong thân `try` (gán, `+=`, `-=`, v.v.)
3. Trong khối có dùng `resume retry`
4. **Không** được liệt kê trong `isolate`
5. Và **không** được gán lại trong khối `revert`

→ Compiler phát **cảnh báo W302**:

```
Warning W302: Biến 'retry_limit' bị thay đổi trước khi retry.
  Trạng thái có thể bị bẩn. Dùng isolate: [retry_limit] hoặc reset thủ công trong revert.
```

**Biến `atomic` — cho phép mutation xuyên retry mà không khôi phục:**

Trong một số trường hợp, biến bên ngoài `isolate` *cần* giữ giá trị mới qua các lần retry — ví dụ bộ đếm tổng số lần thử, accumulator log. Khai báo chúng với bổ ngữ `atomic` để tắt W302:

```vir
atomic var total_attempts: i32 = 0

try(isolate: [connection]):
    total_attempts += 1           # OK — atomic, không W302, không khôi phục
    connection = open_link()
revert
    if total_attempts < 5 do
        resume retry
    end
    resume revert
end
```

**Quy tắc `atomic`:**

| Thuộc tính | Hành vi |
|------------|--------|
| W302 | Tắt — không cảnh báo khi mutate bên trong `try` có `resume retry` |
| Snapshot | Không — biến `atomic` **không** bị khôi phục khi retry |
| Phạm vi | Cấp hàm hoặc cấp module; không cho phép trong `isolate` list |
| Kiểu | Chỉ kiểu Copy (`i8`–`i64`, `u8`–`u64`, `int`, `bool`, `float`) |
| Ngữ nghĩa | Mutation vẫn tuân thủ borrow checker; `atomic` chỉ ảnh hưởng đến heuristic W302 |

> **Lưu ý:** `atomic` ở đây là thuộc tính biến cho retry logic, không phải atomic bộ nhớ (`lock`/`!!`). Hai cơ chế hoàn toàn độc lập.

**`resume revert` — lan truyền đến revert cấp hàm:**

`resume revert` bên trong khối `revert` cục bộ đẩy lỗi lên `revert` cấp hàm. Đây là **mẫu bồi hoàn Saga** — mỗi cấp dọn dẹp cục bộ, rồi lan truyền lên trên.

**`emit` — ghi sự kiện có cấu trúc:**

`emit` gửi một sự kiện/log có cấu trúc. Đối số là hàm tạo sự kiện với chuỗi thông điệp. Sự kiện được kiểm tra kiểu lúc biên dịch; runtime quyết định định tuyến (console, file, telemetry).

```vir
emit LOG_INFO("thông điệp")
emit LOG_ERROR("lỗi: $erx")
emit LOG_CRITICAL("sự cố hệ thống")
```

**Ví dụ toàn diện — khối try phân cấp (mẫu Saga):**

```vir
func sync_satellite_data:
    var retry_limit = 3;
        connection = none;
        data_buffer = none

    # Cấp 1: Kết nối
    try(timeout: 5s):
        emit LOG_INFO("Đang kết nối vệ tinh...")
        connection = open_satellite_link()
    revert
        emit LOG_ERROR("Kết nối thất bại (lỗi $erx)")
        retry_limit -= 1
        if retry_limit > 0 do
            resume retry
        end
        resume revert
    end

    # Cấp 2: Lấy dữ liệu
    try(timeout: 10s):
        emit LOG_INFO("Đang lấy dữ liệu telemetry...")
        data_buffer = fetch_telemetry(connection)
    revert
        emit LOG_ERROR("Lấy dữ liệu thất bại (lỗi $erx)")
        close_satellite_link(connection)
        resume revert
    end

    # Cấp 3: Ghi vào bộ nhớ
    try:
        emit LOG_INFO("Đang ghi dữ liệu vào bộ nhớ...")
        write_storage(data_buffer)
    revert
        emit LOG_ERROR("Ghi thất bại (lỗi $erx)")
        resume revert
    end

    emit LOG_INFO("Đồng bộ hoàn tất.")

revert
    emit LOG_CRITICAL("sync_satellite_data thất bại, đang hoàn tác...")
    rollback_all_changes()

ensure
    if connection != none do
        close_satellite_link(connection)
    end
    if data_buffer != none do
        free_buffer(data_buffer)
    end
    emit LOG_INFO("Tài nguyên đã giải phóng.")
end.
```

**`erx` — Thanh ghi lỗi:**

Từ khoá `erx` đọc mã lỗi hiện tại (giá trị truyền cho `throw`). Có sẵn bên trong `revert` và `ensure` (cả cục bộ và cấp hàm).

**Tóm tắt ngữ nghĩa:**

| Cấu trúc | Vị trí | Hành vi |
|-----------|--------|---------|
| `try: ... revert ... end` | Trong thân hàm | Ranh giới lỗi với bồi hoàn cục bộ |
| `try(timeout: T): ...` | Trong thân hàm | Ranh giới lỗi với hết hạn tự động |
| `try(isolate: [x, y]): ...` | Trong thân hàm | Snapshot biến khi vào; khôi phục khi `resume retry` |
| `resume retry` | Trong `revert` cục bộ | Khởi động lại khối try hiện tại |
| `resume revert` | Trong `revert` cục bộ | Lan truyền lỗi đến revert cấp hàm |
| `revert` | Cuối hàm | Chạy khi lỗi lan truyền qua `resume revert` hoặc `throw` |
| `ensure` | Cuối hàm | Luôn chạy khi thoát hàm |
| `emit` | Bất kỳ đâu | Ghi sự kiện/log có cấu trúc |
| `erx` | revert / ensure | Đọc mã lỗi đã throw |

**Luồng thực thi:**

| Kịch bản | Luồng |
|----------|-------|
| try thành công | thân try → code sau try end → ensure → return |
| try throw + resume retry | thân try → throw → revert cục bộ → resume retry → thân try (khởi lại) |
| try throw + resume retry (isolate) | thân try → throw → revert cục bộ → resume retry → **khôi phục snapshot** → thân try (khởi lại) |
| try throw + resume revert | thân try → throw → revert cục bộ → resume revert → revert hàm → ensure → return |
| try hết hạn | timeout kích hoạt → revert cục bộ (erx = mã timeout) |
| throw ngoài try | thân hàm → throw → revert hàm → ensure → return |

---

## 14. Tham số — in / ref / out

Vir sử dụng ba từ khoá nhóm tham số: `in` (đầu vào), `ref` (tham chiếu), `out` (đầu ra). Mặc định mọi tham số đều **truyền theo giá trị**. Dùng `ref` để truyền theo tham chiếu.

### 14.1 Cú pháp đơn giản (inline)

Khi số tham số ít, khai báo trực tiếp trong ngoặc:

```vir
func increment(ref x: int):
    x = x + 1
end.

func swap(ref a: int, ref b: int):
    var tmp = a
    a = b
    b = tmp
end.
```

### 14.2 Cú pháp nhóm (multi-line)

Khi hàm có nhiều tham số thuộc các nhóm khác nhau, sử dụng cú pháp nhóm. Dấu chấm phẩy `;` cuối dòng nghĩa là "dòng tiếp vẫn thuộc nhóm này". Không có `;` → nhóm kết thúc.

```vir
func process_data:
    in  path: String;
        timeout: Int;
        retry: Bool         # Không có ';' → kết thúc nhóm 'in'
    ref buffer: Array       # Không có ';' → chỉ có 1 biến nhóm 'ref'
    out status: Bool;
        error: String       # Kết thúc nhóm 'out'

    # --- Logic ---
    var fd = open(path)
end.
```

**An toàn compiler — phát hiện lệch nhóm:** Vì ký tự `;` mang trọng lượng ngữ nghĩa (xác định tư cách nhóm), thêm hoặc xoá nhầm có thể lệch nhóm tham số mà không có cảnh báo. Compiler áp dụng các kiểm tra sau để phát hiện lỗi:

| Kiểm tra | Điều kiện | Thông báo |
|---------|-----------|----------|
| **Tham số mồ côi** | Dòng định danh đơn tiếp sau dòng kết thúc nhóm (không `;`) nhưng không có từ khoá `in`/`ref`/`out` | **Lỗi:** "tham số `X` không có nhóm — quên `;` ở dòng trước?" |
| **Nhóm rỗng** | Từ khoá `in`/`ref`/`out` không có tham số trước từ khoá nhóm tiếp theo hoặc thân hàm | **Lỗi:** "nhóm tham số `ref` rỗng" |
| **Gợi ý không khớp kiểu** | Tham số được dùng kiểu `ref` (lấy địa chỉ) nhưng khai báo trong `in` | **Cảnh báo:** "tham số `X` truyền theo giá trị nhưng bị sửa — cân nhắc dùng `ref`" |
| **Hướng dẫn thụt lề** | Dòng tiếp nối (sau `;`) phải thụt lề sâu hơn từ khoá nhóm | **Cảnh báo:** "dòng tiếp nối nên thụt lề dưới từ khoá nhóm của nó" |

Quy tắc `;` cũng áp dụng cho `var` — không cần lặp lại từ khoá:

```vir
var
    x: int;
    y: int;
    z: int
```

### 14.3 Sử dụng

```vir
func main:
    var n = 10
    increment(n)
    print(n)              # → 11 (bản gốc đã bị sửa)

    var x = 1
    var y = 2
    swap(x, y)
    print(x)              # → 2
    print(y)              # → 1
end.
```

### 14.4 Ngữ nghĩa

| Nhóm | Bên gọi truyền | Bên nhận thấy | Ghi lại ảnh hưởng gốc? |
|------|----------------|--------------|----------------------|
| `in` (mặc định) | Bản sao giá trị | Bản sao cục bộ | Không |
| `ref` | Địa chỉ biến | Bản gốc (deref) | **Có** |
| `out` | Slot chưa khởi tạo | Bên nhận gán giá trị | **Có** (sau khi hàm trả về) |

**Nội bộ:** Tham số `ref` emit `LoadAddr` (địa chỉ stack slot) ở vị trí gọi, `DerefLoad`/`DerefStore` ở hàm nhận.

---

## 15. FFI — @bind

Thuộc tính `@bind(target)` cho phép Vir giao tiếp với mã ngoại qua FFI (Foreign Function Interface). Hỗ trợ ba mục tiêu: `c`, `asm`, `wasm`.

### 15.1 @bind(c) — Hàm C ngoại

Khai báo hàm C ngoại để liên kết động.

```vir
@bind(c)
func puts(s: ptr) -> int
end.

@bind(c)
func malloc(size: u64) -> ptr
end.

@bind(c)
func free(p: ptr)
end.
```

- Hàm `@bind(c)` **không có thân** — là ký hiệu ngoại
- Chú thích kiểu **bắt buộc** (ABI của C cần biết kích thước tham số)
- Kiểu trả về dùng `-> type` sau danh sách tham số
- Kết thúc bằng `end`

**Sử dụng:**

```vir
func main:
    var msg = "Hello from Vir via FFI!\n"
    puts(msg)

    var buf = malloc(1024)
    # ... dùng buf ...
    free(buf)
end.
```

### 15.2 @bind(asm) — Hàm hợp ngữ nội tuyến

Khai báo hàm chứa mã hợp ngữ (assembly) theo kiến trúc đích.

```vir
@bind(asm)
func halt:
    # thân hàm chứa chỉ dẫn hợp ngữ hoặc logic Vir
    # biên dịch trực tiếp thành mã máy
    print 0
end.
```

- Hàm `@bind(asm)` **có thân** — chứa logic sẽ biên dịch thành mã máy
- Dùng cho hot path, trap handler, hoặc lệnh CPU đặc thù
- Trình biên dịch **không** tối ưu hoá thân hàm `@bind(asm)` — emit nguyên trạng

### 15.3 @bind(wasm) — Hàm WebAssembly ngoại

Khai báo hàm nhập từ môi trường WebAssembly host.

```vir
@bind(wasm)
func console_log(msg: ptr)
end.

@bind(wasm)
func wasm_alloc(size: u32) -> ptr
end.
```

- Hàm `@bind(wasm)` **không có thân** — là ký hiệu nhập từ host
- Tương tự `@bind(c)` nhưng liên kết qua bảng import WASM
- Kiểu tham số ánh xạ sang WASM value types (`i32`, `i64`, `f32`, `f64`)

### 15.4 Quy ước gọi hàm

| Kiến trúc | Thanh ghi tham số | Thanh ghi trả về |
|-----------|------------------|-----------------|
| ARM64 (AAPCS64) | X0–X7 | X0 |
| x86-64 (SysV) | rdi, rsi, rdx, rcx, r8, r9 | rax |
| WASM | Stack machine (không có thanh ghi) | Stack top |

### 15.5 Liên kết

- **Mach-O (macOS):** Tạo `__stubs` + `__la_symbol_ptr`, liên kết `/usr/lib/libSystem.B.dylib`
- **ELF (Linux):** Tạo `.plt` + `.got`, liên kết qua `DT_NEEDED`
- **WASM:** Tạo bảng `import` section, host cung cấp hàm lúc khởi tạo
- `@bind(c)` và `@bind(wasm)` kích hoạt chế độ liên kết động; chương trình Vir thuần vẫn hoàn toàn static
- `@bind(asm)` không thay đổi chế độ liên kết — mã được nhúng trực tiếp

---

## 16. Register — Cấu trúc bit phần cứng

Từ khoá `register` định nghĩa cấu trúc ánh xạ bit thanh ghi phần cứng, phục vụ lập trình hệ thống và nhúng.

### 16.1 Field đơn bit

```vir
register UART_SR: u32
    PE:     0          # bit 0 — Parity Error
    FE:     1          # bit 1 — Framing Error
    NF:     2          # bit 2 — Noise Flag
    ORE:    3          # bit 3 — Overrun Error
    IDLE:   4          # bit 4 — IDLE line detected
    RXNE:   5          # bit 5 — Read Data Register Not Empty
    TC:     6          # bit 6 — Transmission Complete
    TXE:    7          # bit 7 — Transmit Data Register Empty
end.
```

### 16.2 Field nhiều bit

```vir
register GPIO_MODER: u32
    MODE0:  0..1       # bit 0-1 (2 bit)
    MODE1:  2..3       # bit 2-3
    MODE2:  4..5       # bit 4-5
end.
```

### 16.3 Sử dụng

```vir
func uart_init:
    var sr = volatile_read(0x40011000) as UART_SR

    if sr.RXNE do # đọc bit 5
        var data = volatile_read(0x40011004)
    end

    sr.TXE = 1                            # đặt bit 7
    volatile_write(0x40011000, sr as u32)  # ghi lại
end.
```

### 16.4 Cơ chế nội bộ

| Thao tác | Code sinh ra |
|----------|-------------|
| **Đọc 1 bit** `reg.FIELD` | `(value >> bit_pos) & 1` |
| **Ghi 1 bit** `reg.FIELD = v` | `(value & ~(1 << bit_pos)) \| (v << bit_pos)` |
| **Đọc nhiều bit** `reg.FIELD` | `(value >> lo) & ((1 << (hi-lo+1)) - 1)` |
| **Ghi nhiều bit** `reg.FIELD = v` | `(value & ~(mask << lo)) \| ((v & mask) << lo)` |

Trên ARM64, compiler emit lệnh `UBFX` (trích) và `BFI` (chèn) native.

### 16.5 Volatile Intrinsics

```vir
volatile_read(addr: ptr): int    # đọc với memory barrier
volatile_write(addr: ptr, val)   # ghi với memory barrier
```

Ngăn compiler sắp xếp lại hoặc bỏ qua truy cập memory đến thanh ghi phần cứng.

### 16.6 Mold — Bit-field đa dụng

Trong khi `register` dùng cho ánh xạ thanh ghi phần cứng (volatile, memory-mapped I/O), `mold` định nghĩa **bit-field đa dụng** để đóng gói dữ liệu — format pixel, header giao thức, cờ compact, v.v.

```vir
mold Pixel: u16
    r: 5, g: 6, b: 5
end.

mold TCPFlags: u8
    FIN: 1, SYN: 1, RST: 1, PSH: 1, ACK: 1, URG: 1
end.
```

**Cú pháp:** `mold Tên: <kiểu_nền>` theo sau bởi các cặp `field: độ_rộng` phân cách bằng dấu phẩy, đóng bằng `end`.

**Sử dụng:**

```vir
var p = Pixel(r: 31, g: 0, b: 0)    # đỏ thuần
print p.r                             # 31
p.g = 63                              # đặt xanh lá tối đa
var raw = p as u16                    # đóng gói thành u16
```

**Khác biệt với `register`:**

| Khía cạnh | `register` | `mold` |
|-----------|-----------|--------|
| Mục đích | I/O thanh ghi phần cứng | Đóng gói dữ liệu / giao thức bit |
| Truy cập | Qua `volatile_read`/`volatile_write` | Biến bình thường |
| Volatile | Có — compiler giữ mọi truy cập | Không — compiler có thể tối ưu |
| Trường hợp | UART, GPIO, DMA | Pixel, network header, cờ |
| Ngữ nghĩa | **Copy** | **Copy** |

**Cơ chế nội bộ:** Cùng cơ chế trích/chèn bit như `register` (§16.4) — `UBFX`/`BFI` trên ARM64, shift-and-mask trên kiến trúc khác.

---

## 17. Thực thi lúc biên dịch — precomp

Từ khoá `precomp` (và bí danh `comptime`) là một **bổ ngữ (modifier)** đặt trực tiếp trước biểu thức/khai báo cần được tính toán lúc biên dịch. Không dùng khối `{ }`. Kết quả được inline vào binary dưới dạng hằng số.

**Quy tắc ưu tiên:** `precomp`/`comptime` có độ ưu tiên **thấp nhất** — chúng "nuốt" toàn bộ biểu thức đứng sau cho đến khi gặp kết thúc dòng, dấu ngăn cách, hoặc từ khoá kế tiếp. Dùng ngoặc đơn `( ... )` để gom nhóm biểu thức phức hợp.

### 17.1 Hằng compile-time (bổ ngữ prefix)

```vir
const TABLE_SIZE = precomp 1 shl 16            # → 65536
const MASK       = precomp 0xFF and 0x0F       # → 0x0F
var   a          = precomp 2 + 3 * 5           # → precomp(2 + 3*5) = 17
var   b          = comptime (get_cfg() or 1)   # dùng ngoặc để gom gọi hàm
```

### 17.2 Hàm compile-time

```vir
precomp func factorial(n):
    if n <= 1 do
        out 1
    end
    out n * factorial(n - 1)
end.

const FACT_10 = precomp factorial(10)          # → 3628800

func main:
    print(FACT_10)             # in 3628800 (đã tính lúc biên dịch)
end.
```

### 17.3 Kiểm tra compile-time

```vir
precomp if TABLE_SIZE > 1000000 do
    throw "TABLE_SIZE quá lớn!"                # lỗi biên dịch, không phải runtime
end
```

### 17.4 Giới hạn

| Hỗ trợ trong precomp | Không hỗ trợ |
|-----------------------|-------------|
| Số học số nguyên | I/O (`print`) |
| `if`/`eif`/`else` | Mảng, entity |
| Gọi hàm, đệ quy | Thao tác chuỗi |
| `throw` (thành lỗi biên dịch) | System calls |
| Toán tử so sánh | Cấp phát bộ nhớ |

---

## 18. Điểm nhập — @entry

Mặc định, compiler tìm `func main` làm điểm nhập. Trong môi trường bare-metal/kernel, dùng `@entry` để chỉ định tuỳ chọn.

```vir
@entry
func kmain:
    # Khởi tạo kernel — không libc, không allocator
    # Chỉ truy cập phần cứng trực tiếp
end.
```

Hàm `@entry` được export thành `_start` (hoặc tên tuỳ chỉnh qua linker script).

---

## 19. Mảng (Arrays)

### 19.1 Mảng literal

```vir
var nums = [10, 20, 30, 40, 50]
print nums[0]            # → 10
print len(nums)          # → 5
```

### 19.2 Mảng động

```vir
var list = arr_new(64)   # tạo với dung lượng ban đầu
push(list, 42)           # thêm phần tử
push(list, 99)
print list[0]            # → 42
print len(list)          # → 2
list[0] = 100            # gán theo chỉ mục
```

### 19.3 Mảng trong vòng lặp

```vir
var sum = 0
for i in 0..len(nums) do
    sum = sum + nums[i]
end
print sum                # → 150
```

### 19.4 Resize và Dead Space Arena

Khi mảng động vượt dung lượng, nó cấp phát một khối mới lớn hơn (tăng gấp 2) và copy dữ liệu sang. Vì Vir dùng bump allocator, **khối cũ trở thành dead space không thể thu hồi** cho đến khi toàn bộ arena được giải phóng.

**Tác động:** Mảng resize nhiều lần (ví dụ: trong vòng lặp push hàng triệu phần tử) có thể tiêu tốn bộ nhớ arena nhanh hơn nhiều so với kích thước dữ liệu thực tế.

**Chiến lược giảm thiểu:**

| Chiến lược | Khi nào dùng |
|-----------|-------------|
| Khai báo trước với `arr_new(N)` | Khi biết hoặc ước tính được kích thước tối đa |
| Dùng khối `arena:` (§4.6) | Khi mảng thuộc phạm vi vòng lặp — dead space được thu hồi mỗi lần lặp |
| Dùng `arr_compact(list)` | Thu hồi dead space tường minh bằng cách cấp phát lại vừa khít |

```vir
# Khai báo trước để tránh resize
var data = arr_new(10000)

# Hoặc compact sau khi push số lượng lớn
for i in 0..10000 do
    push(data, tinh_toan(i))
end
arr_compact(data)          # cấp phát lại vừa khít, khối cũ thành dead space (một lần)
```

| Hàm | Mô tả |
|-----|-------|
| `arr_new(capacity)` | Tạo mảng với dung lượng đặt trước |
| `arr_compact(arr)` | Cấp phát lại vừa khít (giảm lãng phí arena) |
| `len(arr)` | Số phần tử hiện tại |
| `cap(arr)` | Dung lượng đã cấp phát hiện tại |

---

## 20. Dict & Map

### 20.1 Dict — Dữ liệu khoá-giá trị

Dict là cấu trúc khoá-giá trị (hash table). Dùng cùng cú pháp `[]` như mảng — nếu phần tử có `:` thì là dict.

#### 20.1.1 Khai báo

```vir
var ages = ["Alice": 30, "Bob": 25]
```

Khai báo với kiểu tường minh:

```vir
var ages: dict[string, int] = ["Alice": 30, "Bob": 25]
```

- `[key: value, ...]` — dict literal, compiler suy luận kiểu từ phần tử đầu tiên
- Chú thích kiểu `dict[K, V]` tuỳ chọn
- Kiểu khoá nguyên thuỷ: `int`, `string`, `bool`, `ptr`
- Khoá entity cần phương thức `hash` (xem §20.1.4)

#### 20.1.2 Thao tác

```vir
var m: dict[string, int] = []      # dict rỗng (chú thích kiểu bắt buộc cho dict rỗng)

m["Alice"] = 30                    # gán
print m["Alice"]                   # đọc → 30

var exists = m ? "Alice"           # kiểm tra tồn tại → true
del m["Bob"]                       # xoá
print len(m)                       # số phần tử
```

#### 20.1.3 Duyệt (Iteration)

```vir
for k, v in ages do
    print("$k: $v")
end

for k in keys(ages) do
    print k
end

for v in values(ages) do
    print v
end
```

Thứ tự duyệt **không đảm bảo** (hash table không giữ thứ tự chèn).

#### 20.1.4 Hash Function

Vir dùng hash nội bộ cho các kiểu nguyên thuỷ. Khoá entity cần định nghĩa phương thức `hash`:

| Kiểu khoá | Hash |
|-----------|------|
| `int`, `i32`, `u64`, ... | Identity hash (mod bucket count) |
| `string` | FNV-1a |
| `bool` | 0 hoặc 1 |
| Entity với `method hash -> int` | Do người dùng định nghĩa |

```vir
entity Point:
    x: int
    y: int

    method hash -> int
        out this.x * 31 + this.y
    end.
end.

var grid: dict[Point, string] = [Point(x: 0, y: 0): "origin"]
```

#### 20.1.5 Nội bộ

| Thuộc tính | Chi tiết |
|----------|--------|
| **Va chạm** | Open addressing, linear probing |
| **Load factor** | Resize khi 75% |
| **Cấp phát** | Bucket array trong Arena |
| **So sánh** | Nguyên thuỷ: so giá trị. Entity: so từng trường |

### 20.2 Map — Biểu thức biến đổi

`map` biến đổi từng phần tử của một iterable, tạo ra mảng mới.

```vir
var doubled = map x in numbers:
    out x * 2
end

var names = map u in users:
    out u.name
end
```

**Cú pháp:**

```
map <biến> in <iterable>:
    out <biểu_thức>
end
```

- `<biến>` — biến lặp gắn với từng phần tử
- `<iterable>` — bất kỳ iterable nào (array, range, keys/values của dict)
- `out <biểu_thức>` — giá trị đã biến đổi cho mảng kết quả
- Kiểu kết quả là `array`, kiểu phần tử suy luận từ `<biểu_thức>`

**Với chỉ số (index):**

```vir
var labeled = map i, v in items:
    out "$i: $v"
end
```

**Kết hợp với lọc (filter):**

```vir
var evens = map x in numbers:
    if x % 2 == 0
        out x
    end
end
```

**Map lồng nhau:**

```vir
var flat = map row in matrix:
    out map col in row:
        out col * 2
    end
end
```

---

## 21. Biểu thức Case

Mỗi nhánh của `case` là một arm độc lập.

- **Kết thúc nhánh** dùng dấu chấm phẩy `;`
- **Nhiều statement trong cùng một nhánh** dùng dấu phẩy `,`
- **Nhánh cuối cùng** có thể bỏ dấu `;`
- Nếu thiếu `,` hoặc `;` đúng vị trí thì đó là **lỗi cú pháp**
- Dấu phẩy bên trong lời gọi hàm như `f(x, y)` hoặc bên trong biểu thức lồng nhau **không** tách statement

```vir
case color
    "red": log("stop", 1), out 1;
    "green": log("go", 2), out 2;
    "yellow": log("wait", 3), out 3;
    else: log("unknown", 0), out 0
end
```

---

## 22. Async / Task

Vir hỗ trợ lập trình bất đồng bộ qua mô hình **stackless coroutine** — mỗi hàm `async` được compiler biến đổi thành state machine.

### 22.1 Hàm async

```vir
async func fetch_data(url: string):
    var conn = await connect(url)
    var data = await read(conn)
    out data
end.
```

- `async func` khai báo hàm bất đồng bộ
- `await` tạm dừng hàm, nhường quyền cho scheduler
- Compiler sinh state machine — mỗi `await` là một điểm tạm dừng (suspension point)

### 22.2 Task — Tạo tác vụ

```vir
var t = task fetch_data("https://api.example.com")
# t là handle, fetch_data chưa chạy xong
```

`task` tạo một tác vụ async và đưa vào hàng đợi scheduler. Trả về task handle.

### 22.3 Wait — Chờ kết quả

```vir
var result = wait t               # block cho đến khi t hoàn thành
```

### 22.4 Nhiều task

```vir
var t1 = task fetch_data("/api/a")
var t2 = task fetch_data("/api/b")

var r1 = wait t1
var r2 = wait t2
```

Task chạy đồng thời (concurrent) — không song song (parallel) trừ khi chương trình `include` một thư viện thread pool / work-stealing (xem §1.1).

### 22.5 Mô hình Scheduler

| Thuộc tính | Giá trị |
|-----------|---------|
| Loại | Cooperative (stackless coroutine) — semantics ngôn ngữ |
| Chuyển ngữ cảnh | Tại mỗi `await` hoặc `await pass` |
| Event loop | Do **thư viện** cung cấp khi được include — không nhúng sẵn vào mọi binary |
| Thread pool / work-steal | Tuỳ chọn qua `include` (POSIX, win32, spin, none, …) |
| Overhead khi không dùng | **Không** — binary tối giản không chứa scheduler (§1.1) |

Compiler hạ `async`/`await`/`task` xuống state machine và điểm tạm dừng. **Compiler không biết** Scheduler / Worker / ArenaPool tồn tại — ai chạy các điểm đó do thư viện quyết định (polling đơn luồng, thread pool, work-stealing, hoặc serial trên embedded). Xem [`VIR_EXECUTION_MODEL.md`](VIR_EXECUTION_MODEL.md) §7.

### 22.6 Nhường quyền chủ động — `await pass`

Trong mô hình đa nhiệm hợp tác, vòng lặp đồng bộ chạy lâu bên trong `async func` sẽ chặn scheduler. `await pass` chèn một **điểm nhường quyền tường minh** — tác vụ hiện tại tạm dừng một nhịp scheduler, cho phép các tác vụ sẵn sàng khác chạy.

```vir
async func xu_ly_danh_sach_lon(items: array):
    var i = 0
    loop:
        if i >= items.len do
            stop
        end
        xu_ly_nang(items[i])
        i += 1
        if i mod 100 == 0 do
            await pass           # nhường quyền mỗi 100 lần lặp
        end
    end
end.
```

- `await pass` chỉ hợp lệ bên trong `async func`
- Chi phí: một vòng scheduler (không I/O, chỉ nhường rồi xếp lại hàng đợi)
- Dùng trong vòng lặp tốn CPU để ngăn chặn tình trạng đói tác vụ (task starvation)

### 22.7 Huỷ tác vụ — `cancel`

`cancel` yêu cầu kết thúc nhẹ nhàng một tác vụ đang chạy. Tại `await` tiếp theo (bao gồm `await pass`), tác vụ bị huỷ nhận lỗi nội bộ được chuyển đến khối `revert`.

```vir
var t = task cong_viec_dai()

# ... sau đó, nếu điều kiện thay đổi:
cancel t

# khối revert của tác vụ (nếu có) chạy để dọn dẹp
```

**Ngữ nghĩa:**

| Khía cạnh | Hành vi |
|-----------|---------|
| Tức thì? | Không — huỷ là **hợp tác**. Được gửi tại `await` tiếp theo |
| Tác vụ đang `await` | Được đánh thức ngay với mã lỗi cancel |
| Tác vụ đang chạy (không await) | Cờ cancel được đặt; gửi tại `await` hoặc `await pass` tiếp theo |
| `revert` của tác vụ bị huỷ | Chạy bình thường — `erx` chứa mã lỗi cancel |
| Cancel tác vụ đã xong | Không có tác dụng |
| Cancel từ hàm không async | Cho phép — `cancel` không yêu cầu `async func` |

### 22.8 Đa nhiệm hoá sự kiện — `select`

`select` chờ **nhiều task handle** đồng thời và trả về khi **tác vụ đầu tiên** hoàn thành. Kết quả cho biết tác vụ nào đã hoàn thành.

```vir
async func chay_dua_fetch:
    var t1 = task fetch_data("/api/primary")
    var t2 = task fetch_data("/api/mirror")

    select:
        on t1 as ket_qua:
            print "Primary phản hồi: $ket_qua"
        end
        on t2 as ket_qua:
            print "Mirror phản hồi: $ket_qua"
            cancel t1
        end
    end
end.
```

**Có timeout:**

```vir
select(timeout: 10s):
    on t1 as ket_qua:
        xu_ly(ket_qua)
    end
    on timeout:
        cancel t1
        emit LOG_ERROR("Tất cả tác vụ hết hạn")
    end
end
```

**Quy tắc:**
- `select` chỉ hợp lệ bên trong `async func`
- Mỗi nhánh `on <handle> as <binding>:` chạy khi tác vụ đó hoàn thành trước
- Chỉ **một** nhánh được thực thi — tác vụ hoàn thành đầu tiên thắng
- Các tác vụ còn lại **không** tự động bị huỷ — dùng `cancel` tường minh nếu cần
- `on timeout:` là nhánh dự phòng nếu không tác vụ nào hoàn thành trong thời hạn
- Cho phép `select` lồng nhau

### 22.9 Tác vụ ly khai — `quiet`

`quiet` tạo tác vụ **bắn-và-quên** (fire-and-forget), ly khai khỏi hàm gọi. Hàm gọi không nhận handle — tác vụ chạy độc lập đến khi hoàn thành hoặc lỗi. Khối `revert`/`ensure` của nó chạy bình thường; lỗi được ghi qua `emit` nhưng không lan truyền.

```vir
quiet gui_analytics(event_data)
quiet xoa_cache()
```

**Ngữ nghĩa:**

| Khía cạnh | Hành vi |
|-----------|---------|
| Giá trị trả về | Không — `quiet` bỏ kết quả |
| Handle | Không — không thể `wait`, `cancel`, hay `select` tác vụ quiet |
| Xử lý lỗi | `revert`/`ensure` của tác vụ chạy; lỗi ghi qua `emit`, không lan truyền |
| Thời gian sống | Đến khi tác vụ hoàn thành hoặc scheduler tắt |
| Trường hợp sử dụng | Telemetry, logging, làm nóng cache, dọn nền |

**⚠ Cảnh báo:** Vì tác vụ `quiet` ly khai, rò rỉ tài nguyên là có thể nếu tác vụ mở tài nguyên mà không có `ensure`. Luôn dùng `ensure` để dọn dẹp trong tác vụ quiet.

### 22.10 Giới hạn

- `await` / `await pass` / `select` chỉ hợp lệ bên trong `async func`
- `cancel` là hợp tác — tác vụ đang kẹt trong C FFI không thể bị huỷ cho đến khi quyền điều khiển trả về Vir
- Để chia sẻ buffer dữ liệu thô giữa module mà không cần thông điệp, dùng `share` hoặc `ref` parameter thay vì `port`

### 22.11 Port — Điều phối tín hiệu giữa Worker

Xem **§23 Port** để biết đặc tả đầy đủ.

---

## 23. Port — Điều phối tín hiệu giữa các Worker

`port` là nguyên bản của Vir dành cho **phối hợp dựa trên thông điệp giữa các worker async**. Khác với `share`/`ref` cấp quyền truy cập trực tiếp vào bộ nhớ dữ liệu thô (ví dụ Framebuffer), `port` mang **tín hiệu có kiểu** qua hàng đợi nội bộ; bên gửi không bị chặn, bên nhận chờ tín hiệu tiếp theo.

**Khi nào dùng `port` vs `share`/`ref`:**

| Tình huống | Dùng |
|----------|---------|
| Framebuffer, buffer âm thanh, bảng tra cứu | `share` hoặc `deck` — bộ nhớ trực tiếp, không sao chép |
| Gateway nhận telemetry từ các Satellite node | `port` — tín hiệu có kiểu, hàng đợi an toàn qua task |
| Truyền mảng lớn vào hàm để xử lý in-place | `ref` parameter |
| Gửi lệnh hoặc sự kiện từ producer đến consumer | `port` |

### 23.1 Khai báo

```vir
port signals: SatSignal          # port tín hiệu có kiểu (MPSC — nhiều producer, một consumer)
port commands: GatewayCmd        # một port khác trên cùng module
```

Port được khai báo cấp module với `port tên: KiểuThôngĐiệp`. Module khai báo **sở hữu** port (phía consumer). Mọi module import port có thể gửi vào đó.

### 23.2 Gửi tín hiệu

```vir
send signals <- SatSignal(id: 7, lat: 21.03, lon: 105.8)
send commands <- GatewayCmd.Ping
```

`send <port> <- <giá_trị>` đưa thông điệp vào hàng đợi. Điều này **không chặn** — bên gửi tiếp tục ngay.

### 23.3 Nhận tín hiệu

```vir
async func gateway_loop:
    loop:
        var msg = recv signals        # tạm dừng cho đến khi có thông điệp
        xu_ly(msg)
    end
end.
```

`recv <port>` tạm dừng `async func` hiện tại cho đến khi có thông điệp, rồi trả về giá trị. Đây là điểm tạm dừng (như `await`).

**Có timeout:**

```vir
async func gateway_loop:
    loop:
        var msg = recv(signals, timeout: 500ms)
        case msg:
            SatSignal as s: xu_ly_tin_hieu(s)
            timeout:        emit LOG_WARN("Không có tín hiệu trong 500 ms")
        end
    end
end.
```

### 23.4 Port với `select`

Nhiều port có thể đa hóa bằng `select`:

```vir
async func gateway_loop:
    loop:
        select:
            on recv(signals) as s:
                xu_ly_tin_hieu(s)
            end
            on recv(commands) as cmd:
                xu_ly_lenh(cmd)
            end
            on timeout(1s):
                emit LOG_WARN("Không tín hiệu trong 1s")
            end
        end
    end
end.
```

### 23.5 Xuất Port

Module công khai port bằng khai báo `port` ở cấp module:

```vir
# gateway.vri
port signals: SatSignal          # sở hữu phía consumer
port commands: GatewayCmd
```

Module satellite gửi vào đó:

```vir
# satellite.vri
include gateway;

func bao_cao_vi_tri(lat: f32, lon: f32):
    send gateway.signals <- SatSignal(id: NODE_ID, lat: lat, lon: lon)
end.
```

### 23.6 Ngữ nghĩa

| Thuộc tính | Hành vi |
|----------|-----------|
| Mô hình hàng đợi | MPSC — nhiều producer, một consumer |
| Sở hữu thông điệp | **Copy** khi gửi (kiểu Move bị move vào hàng đợi; rlàng buộc cũ vô hiệu) |
| Chặn | `send` không bao giờ chặn; `recv` tạm dừng đến khi có tin hoặc timeout |
| Dung lượng hàng đợi | Không giới hạn mặc định; giới hạn: `port(cap: N) ten: T` |
| Hàng đợi đầy (có giới hạn) | Bên gửi chặn đến khi có chỗ (cooperative yield) |
| An toàn kiểu | Thời biên dịch — sử dụng sai kiểu là lỗi kiểu |
| An toàn luồng | An toàn qua các async task; không an toàn qua OS thread nếu không có `lock` |

### 23.7 So sánh với `share` và `deck`

```vir
# Đường dữ liệu thô — không sao chép, trực tiếp bộ nhớ
share framebuf: Pixel[SCREEN_W * SCREEN_H]   # các module đọc/ghi trực tiếp

# Buffer chia sẻ GPU — vùng mapped
deck render_target: Pixel[1920 * 1080]        # CPU-GPU mapped, lock để ghi nguyên tử

# Phối hợp tín hiệu — hàng đợi có kiểu
port frame_done: FrameEvent                  # renderer thông báo compositor
port user_input: InputEvent                  # module input thông báo UI
```

---

## 24. GPU, SIMD & Atomic Primitives

Vir cung cấp từ khoá hạng nhất cho vector SIMD, buffer chia sẻ GPU, thao tác swizzle, và truy cập bộ nhớ nguyên tử — cho phép đồ hoạ và tính toán hiệu năng cao mà không cần thư viện ngoài.

### 24.1 Vector SIMD — `flux`

`flux<T, N>` khai báo vector SIMD có độ rộng cố định gồm `N` phần tử kiểu `T`. Compiler ánh xạ các phép toán sang lệnh SIMD native (ARM NEON, x86 SSE/AVX, WASM SIMD).

```vir
var pos: flux<f32, 4> = flux(1.0, 2.0, 3.0, 1.0)
var vel: flux<f32, 4> = flux(0.1, 0.0, -0.5, 0.0)

var next_pos = pos + vel          # cộng từng phần tử — một lệnh SIMD
```

**Kiểu phần tử hỗ trợ:** `f32`, `f64`, `i8`–`i64`, `u8`–`u64`
**Độ rộng phổ biến:** 2, 4, 8, 16 (phải là luỹ thừa 2)

| Thao tác | Cú pháp | Sinh ra |
|----------|---------|---------|
| Số học từng phần tử | `a + b`, `a * b`, `a - b` | SIMD `FADD`/`FMUL`/`FSUB` |
| Broadcast scalar | `flux(s, s, s, s)` hoặc `flux.splat(s)` | `DUP` / broadcast |
| Tích vô hướng | `flux.dot(a, b)` | chuỗi fused multiply-add |
| Độ dài / chuẩn hoá | `flux.len(v)`, `flux.norm(v)` | `SQRT` + nghịch đảo |
| Nạp từ bộ nhớ | `flux.load(ptr)` | SIMD load căn chỉnh |
| Lưu vào bộ nhớ | `flux.store(ptr, v)` | SIMD store căn chỉnh |

**Ngữ nghĩa:** `flux` là kiểu **Copy** (kích thước cố định, vừa thanh ghi). Không cấp phát heap.

### 24.2 Swizzle — `~`

Toán tử swizzle `~` xáo trộn hoặc nhân bản các kênh vector theo tên. Tên kênh theo quy ước `xyzw` (vị trí) hoặc `rgba` (màu sắc).

```vir
var v: flux<f32, 4> = flux(1.0, 2.0, 3.0, 4.0)

var xyz  = v~xyz              # flux<f32, 3> — bỏ w
var zyx  = v~zyx              # flux<f32, 3> — đảo xyz
var xxxx = v~xxxx             # flux<f32, 4> — broadcast x
var rg   = v~rg               # flux<f32, 2> — đồng nghĩa với xy
```

**Quy tắc:**
- Ký tự kênh: `x`=0, `y`=1, `z`=2, `w`=3 (tương đương `r`, `g`, `b`, `a`)
- Độ rộng kết quả = số ký tự: `v~xy` → `flux<T, 2>`
- Kênh có thể lặp: `v~xxyy` → `flux<T, 4>`
- Swizzle là compile-time — không chi phí runtime (ánh xạ sang lệnh shuffle hoặc được gập)

**Write-masking — ghi chọn lọc qua swizzle:**

Swizzle bên **vế trái** phép gán giới hạn kênh được ghi, các kênh không nêu giữ nguyên giá trị cũ:

```vir
var v: flux<f32, 4> = flux(1.0, 2.0, 3.0, 4.0)

v~xy = flux(10.0, 20.0)          # v = flux(10.0, 20.0, 3.0, 4.0) — z, w giữ nguyên
v~z  = flux(99.0)                 # v = flux(10.0, 20.0, 99.0, 4.0) — chỉ ghi z
v~rb = flux(0.5, 0.8)            # viết qua tên màu — r=x, b=z
```

**Quy tắc write-mask:**
- Tên kênh ở vế trái **không được lặp**: `v~xx = ...` là lỗi biên dịch
- Số kênh vế trái phải bằng độ rộng vế phải: `v~xyz = flux(1.0, 2.0)` → lỗi
- Kênh không nêu giữ nguyên — compiler sinh lệnh `INS` / blend mask (ARM NEON) hoặc `BLENDPS` (x86 SSE)
- Write-mask kết hợp với pipeline: `v~xy = src~zw` (copy z→x, w→y)

**Tích hợp pipeline:**

```vir
v~xyz |> project |> draw      # swizzle, rồi pipe qua các hàm
```

### 24.3 Buffer chia sẻ — `deck`

`deck` khai báo **buffer dữ liệu chia sẻ** cho giao tiếp CPU-GPU hoặc pipeline render nhiều giai đoạn. Deck là vùng nhớ có kiểu, kích thước cố định, có thể được ánh xạ đọc/ghi bởi cả CPU và GPU.

```vir
deck screen: Pixel[1920 * 1080]

func clear_screen:
    for i in 0..screen.len do
        screen[i] = Pixel(r: 0, g: 0, b: 0)
    end
end.
```

**Khai báo:** `deck tên: Kiểu[kích_thước]`

| Thuộc tính | Mô tả |
|-----------|--------|
| Kiểu | Bất kỳ kiểu Copy (`mold`, số nguyên có kích thước, `flux`) |
| Truy cập | Đánh chỉ mục như mảng: `deck[i]` |
| Bộ nhớ | Cấp phát trong vùng shared/mapped (tuỳ platform) |
| Thời gian sống | Cấp module — sống suốt chương trình |
| Ngữ nghĩa | **Move** (handle buffer); phần tử là **Copy** |
| Trường hợp | Framebuffer, vertex buffer, vùng staging compute |

**Ghi nguyên tử vào deck — xem §24.4.**

### 24.4 Nguyên tử — `lock` / `!!`

`lock` cung cấp truy cập **đọc-sửa-ghi nguyên tử** đến một vị trí bộ nhớ. Ngăn chặn data race khi nhiều tác vụ hoặc đơn vị phần cứng truy cập cùng địa chỉ.

**Dạng tiền tố — `lock`:**

```vir
lock screen[coord] = p           # ghi nguyên tử
lock counter += 1                 # tăng nguyên tử
var val = lock shared_flag        # đọc nguyên tử
```

**Dạng hậu tố — `!!`:**

```vir
screen[coord]!! = p              # ghi nguyên tử
counter!! += 1                    # tăng nguyên tử
var val = shared_flag!!           # đọc nguyên tử
```

Hai dạng tương đương. `lock` đọc trái-sang-phải ("khoá cái này, rồi thao tác"). `!!` đọc phải-sang-trái như hậu tố cảnh báo ("đây là vùng nhạy cảm!").

**Ngữ nghĩa:**

| Thao tác | Dạng `lock` | Dạng `!!` | Sinh ra |
|----------|------------|-----------|---------|
| Ghi nguyên tử | `lock x = v` | `x!! = v` | `STLR` (ARM64) / `XCHG` (x86) |
| Đọc nguyên tử | `var v = lock x` | `var v = x!!` | `LDAR` (ARM64) / `MOV` + fence (x86) |
| RMW nguyên tử | `lock x += 1` | `x!! += 1` | `LDAXR`/`STLXR` loop (ARM64) / `LOCK ADD` (x86) |
| Compare-and-swap | `lock.cas(x, old, new)` | — | `CAS` / `CMPXCHG` |

**Thứ tự bộ nhớ:** Mọi thao tác `lock`/`!!` dùng **sequentially consistent** mặc định. Cho relaxed ordering trong đường dẫn hiệu năng, dùng intrinsics `__atomic_load_relaxed` / `__atomic_store_relaxed`.

**⚠ Cảnh báo:** `lock`/`!!` bảo vệ **một thao tác đơn**. Cho critical section nhiều bước, kết hợp với `try`/`revert` hoặc giao thức mutex.

### 24.5 Ví dụ tổng hợp

```vir
mold Pixel: u16
    r: 5, g: 6, b: 5
end.

deck screen: Pixel[1920 * 1080]

func render:
    var p = Pixel(r: 31, g: 0, b: 0)
    var v: flux<f32, 4> = get_pos()

    # Swizzle + pipeline
    v~xyz |> project |> draw

    # Ghi nguyên tử vào buffer chia sẻ
    lock screen[coord] = p
end.
```

---

## 25. UI / Reactive

Vir cung cấp các nguyên bản cấp ngôn ngữ cho lập trình UI phản ứng và đóng gói tài nguyên — không phụ thuộc runtime framework ngoài.

### 25.1 Biến trạng thái — `reactive`

```vir
reactive var count: i32 = 0
reactive var username: string = ""
```

`reactive` khai báo biến trạng thái. Khi giá trị thay đổi, compiler tự động phát sinh lệnh cập nhật mọi view/component phụ thuộc — không cần gọi refresh thủ công, không cần observable wrapper.

**Quy tắc:**
- `reactive` chỉ hợp lệ ở cấp module hoặc cấp `entity`
- Gán thông thường (`count = count + 1`) kích hoạt propagation
- Đọc `reactive` từ `infer`/`train` block không kích hoạt propagation

### 25.2 Ánh xạ Struct sang UI — `morph`

```vir
entity UserCard:
    name: string
    score: i32
end.

morph UserCard -> Panel:
    Label(text: name)
    ProgressBar(value: score, max: 100)
end
```

`morph` khai báo ánh xạ tĩnh từ entity/struct sang component UI. Compiler sinh binding tại thời biên dịch — không runtime reflection, không heap allocation ẩn. Khi trường entity thay đổi, chỉ component tương ứng re-render.

**Ngữ nghĩa:**

| Thuộc tính | Mô tả |
|-----------|--------|
| Thời điểm | Compile-time binding generation |
| Cập nhật | Granular — chỉ component bị ảnh hưởng bởi field thay đổi |
| DOM/layout | Tuỳ platform backend (native widget, WebAssembly DOM, GPU canvas) |

### 25.3 Nhúng tài nguyên — `bundle`

```vir
bundle icon_png:   u8[]   = embed "assets/icon.png"
bundle shader_src: string = embed "shaders/main.vert"
bundle config:     u8[]   = embed "config/default.toml"
```

`bundle` nhúng file tài nguyên vào binary lúc biên dịch. Kết quả là hằng số slice (`u8[]` hoặc `string`) — truy cập zero-overhead, không I/O runtime, không cần file system.

**Quy tắc:**
- Đường dẫn tương đối so với file `.vri` chứa khai báo
- Kiểu `u8[]` cho dữ liệu nhị phân; `string` cho UTF-8 text
- Kích thước file được kiểm tra tại biên dịch

### 25.4 Xuất API — `expose`

```vir
expose func get_user(id: u64) -> UserInfo:
    out db.lookup(id)
end.

expose func update_score(id: u64, delta: i32):
    db.users[id].score += delta
end.
```

`expose` chú thích hàm để compiler sinh glue code cho ABI endpoint. Target endpoint xác định qua build flag: REST (HTTP handler), gRPC (stub), IPC (message handler), hoặc WASM export.

**Ràng buộc kiểu:**
- Tham số và kiểu trả về phải là serializable: entity, số nguyên có kích thước, `string`, `bool`
- Không cho phép: `ptr`, `&mut`, raw `deck`, `flux` (non-serializable)
- `expose async func` phát sinh async endpoint (streaming / SSE)

### 25.5 Sandbox bảo mật — `isolate` (block)

```vir
isolate:
    var result = untrusted_plugin.run(input)
    out result
end
```

`isolate` (dạng block độc lập) chạy code trong sandbox với tập quyền hạn chế: không truy cập bộ nhớ ngoài block trừ tham số được truyền vào, không I/O trực tiếp, không gọi hàm trừ khi được `expose` vào sandbox.

**Phân biệt hai dạng `isolate`:**

| Dạng | Cú pháp | Mục đích |
|------|---------|---------|
| Variable snapshot | `try(isolate: [x, y]):` | Snapshot biến để retry an toàn (§13.7) |
| Security sandbox | `isolate: ... end` | Block sandbox — giới hạn quyền truy cập bộ nhớ/I/O |

---

## 26. AI / Học máy

Vir tích hợp các nguyên bản AI/ML cấp ngôn ngữ: tensor aligned, matmul native, autodiff, và quantization — không phụ thuộc thư viện ngoài.

### 26.1 Kiểu Tensor — `tensor<T>[S...]`

```vir
var weights: tensor<f32>[784, 128]
var input:   tensor<f32>[1, 784]
var output:  tensor<f32>[1, 128]
```

`tensor<T>[S...]` khai báo mảng N chiều với alignment phù hợp cho NPU/GPU. Bộ nhớ tự động căn chỉnh (aligned allocation), layout row-major. Compiler sinh lệnh load/store SIMD aligned.

**Kiểu phần tử T hỗ trợ:** `f32`, `f16`, `i8`, `u8` (quantized), `i32` (accumulator)
**Chiều:** Bất kỳ số chiều D ≥ 1; kích thước kiểm tra tại biên dịch

| Thuộc tính | Mô tả |
|-----------|--------|
| Bộ nhớ | Heap-allocated, aligned 64-byte (cache line) |
| Ngữ nghĩa | Move (handle tensor); phần tử là Copy |
| Thời gian sống | Quản lý qua ownership — không GC |
| Truy cập | `weights[i, j]` (multi-index) |

### 26.2 Nhân ma trận — `**` và `><`

```vir
var output = weights ** input          # matmul chuẩn: [M,K] ** [K,N] → [M,N]
var fused  = a >< b                    # fused multiply-accumulate (FMA)
```

`**` ánh xạ sang lệnh Tensor-core/SIMD native tương ứng platform: **ARM NEON FMMLA**, **x86 AVX-512 DPBF16**, **WASM simd128 dot product**.

`><` là toán tử **fused multiply-accumulate** — nhân rồi cộng tích lũy trong một lệnh hardware, tránh round-off trung gian, dùng trong dot product loop tối ưu.

**Kiểm tra kiểu matmul:**

```
tensor<T>[M, K]  **  tensor<T>[K, N]  →  tensor<T>[M, N]
```

Kích thước không khớp là **lỗi kiểu tại biên dịch** — không runtime panic.

**Ưu tiên toán tử:** `**` và `><` ở mức 22 (cao hơn `*`/`/` ở mức 20).

### 26.3 Inference không gradient — `infer`

```vir
infer:
    var pred = model.forward(input)
    out pred
end
```

`infer` block **tắt toàn bộ gradient tracking**: không cấp phát buffer autodiff, không lưu activation cho backward pass. Giảm RAM ~50% so với `train` mode. Dùng cho deployment / production serving.

**Ngữ nghĩa:**
- Mọi phép toán `tensor` / `**` bên trong đều được tối ưu hoá cho forward-only
- Không thể gọi `.backward()` bên trong hoặc trên giá trị sinh từ `infer` block
- `infer` và `train` không thể lồng nhau

### 26.4 Training với Autodiff native — `train`

```vir
train:
    var pred = model.forward(input)
    var loss = cross_entropy(pred, label)
    loss.backward()
    optimizer.step(model)
end
```

`train` block kích hoạt **autodiff native**: mọi phép toán tensor đều được tracing tự động; `.backward()` tính gradient ngược toàn đồ thị tính toán. Không cần thư viện ngoài.

**So sánh `infer` vs `train`:**

| | `infer` | `train` |
|---|---|---|
| Gradient tracking | Tắt | Bật |
| RAM overhead | Thấp nhất | ~2–3× so với infer |
| Tốc độ | Nhanh nhất | Chậm hơn do tracing |
| `.backward()` | Không cho phép | Có |
| Mục đích | Deployment / serving | Huấn luyện mô hình |

### 26.5 Nén độ chính xác — `quantize`

```vir
var model_q8 = quantize(model, bits: 8)    # INT8 — 75% giảm RAM
var model_q4 = quantize(model, bits: 4)    # INT4 — 87.5% giảm RAM (yêu cầu NPU native)
```

`quantize` chuyển đổi tensor `f32`/`f16` sang dạng compact để tăng tốc inference và giảm RAM. Compiler sinh lệnh dequantize tại điểm `infer` tương ứng — trong suốt với code logic.

| Mức | Kiểu lưu trữ | Giảm RAM | Ghi chú |
|-----|-------------|---------|---------|
| `bits: 32` | `f32` | 0% | Chuẩn — độ chính xác đầy đủ |
| `bits: 16` | `f16` | 50% | Mất mát nhỏ — phù hợp hầu hết mô hình |
| `bits: 8`  | `i8`  | 75% | Đủ cho inference production |
| `bits: 4`  | INT4  | 87.5% | Yêu cầu NPU với hỗ trợ INT4 native |

---

## 27. Intrinsics hệ thống

Vir cung cấp các hàm nội tại cấp thấp cho lập trình hệ thống (không cần `@bind(c)`):

| Intrinsic | Mô tả |
|-----------|--------|
| `__syscall(num, a0, a1, a2)` | Gọi hệ thống thô |
| `__memcpy(dst, src, n)` | Sao chép bộ nhớ |
| `__memset(dst, val, n)` | Điền bộ nhớ |
| `__clz(x)` | Đếm bit 0 đầu (leading zeros) |
| `__ctz(x)` | Đếm bit 0 cuối (trailing zeros) |
| `__popcnt(x)` | Đếm bit 1 (population count) |
| `__bswap(x)` | Đảo byte |
| `__neg(x)` | Phủ định |
| `__not(x)` | NOT bit |
| `__fence()` | Hàng rào bộ nhớ (memory barrier) |
| `__trap()` | Kích hoạt hardware trap |
| `volatile_read(addr)` | Đọc volatile + barrier |
| `volatile_write(addr, val)` | Ghi volatile + barrier |

---

## 28. Hỗ trợ đa ngôn ngữ

Vir hỗ trợ lập trình bằng nhiều ngôn ngữ tự nhiên thông qua hệ thống SubLib adapter:

| Ngôn ngữ | `if` | `func` | `out` | `eif` |
|----------|------|--------|-------|-------|
| English | `if` | `func` | `out` | `eif` |
| Tiếng Việt | `nếu` | `hàm` | `trả về` | `còn nếu` |
| 中文 | `若` | `函数` | `歸` | `又若` |
| 日本語 | `もし` | `関数` | `返す` | `それ以外もし` |
| 한국어 | `만약` | `함수` | `반환` | `아니면 만약` |

Mọi cụm từ ngôn ngữ tự nhiên đều được ánh xạ qua KeywordRegistry sang giá trị token chuẩn.

---

## 29. Từ khoá tham chiếu

### Lõi

| Từ khoá | Mục đích |
|---------|---------|
| `func` | Định nghĩa hàm |
| `end` | Đóng bất kỳ khối nào |
| `out` | Trả về giá trị từ hàm |
| `var` | Khai báo biến có thể thay đổi |
| `let` | Ràng buộc biến bất biến |
| `const` | Hằng số biên dịch |

### Luồng điều khiển

| Từ khoá | Mục đích |
|---------|---------|
| `if` | Nhánh điều kiện |
| `eif` | Nhánh else-if |
| `else` | Nhánh mặc định |
| `when ... loop` | Vòng while |
| `for ... in` | Vòng for phạm vi |
| `loop` | Vòng vô hạn hoặc đếm |
| `break` | Thoát vòng lặp |
| `skip` | Nhảy vòng tiếp |
| `case` | Biểu thức switch/match |

### Kiểu dữ liệu

| Từ khoá | Mục đích |
|---------|---------|
| `entity` | Định nghĩa kiểu struct |
| `packed` | Bổ sung cho entity — bố trí liên tiếp |
| `enum` | Định nghĩa hằng số nguyên có tên |
| `register` | Định nghĩa ánh xạ bit thanh ghi phần cứng |
| `mold` | Định nghĩa bit-field đa dụng (đóng gói dữ liệu) |
| `method` | Định nghĩa hàm gắn với entity |
| `dict` | Kiểu từ điển key-value; literal dùng `[k: v, ...]` |
| `map` | Biểu thức biến đổi (functional map) |

### Phần cứng & SIMD

| Từ khoá / Toán tử | Mục đích |
|-------------------|--------|
| `mold` | Khai báo bit-field đa dụng — đóng gói dữ liệu, không phải hardware-volatile (§16.6) |
| `flux<T, N>` | Kiểu vector SIMD — N phần tử kiểu T; ánh xạ sang ARM NEON / x86 SSE-AVX / WASM SIMD (§23.1) |
| `deck` | Buffer chia sẻ — vùng nhớ có kiểu, cố định cho CPU-GPU hoặc pipeline nhiều giai đoạn (§23.3) |
| `~` | Hậu tố swizzle — xáo trộn/nhân bản kênh `flux`: `v~xyz`, `v~rgba`; hỗ trợ write-masking: `v~xy = flux(a, b)` (§24.2) |
| `lock` | Tiền tố nguyên tử — đọc-sửa-ghi sequentially consistent (§23.4) |
| `!!` | Hậu tố nguyên tử — tương đương `lock`; đánh dấu vị trí nhạy cảm (§23.4) |

### Hệ thống Module

| Từ khoá | Mục đích |
|---------|---------|
| `include` | Nạp file và tạo namespace |
| `lazy include` | Import trì hoãn chỉ kiểu — cho phép phụ thuộc vòng giữa module về kiểu dữ liệu (§3.8) |
| `import` | Đưa hàm vào phạm vi cục bộ |
| `get` | Đưa biến/hằng vào phạm vi cục bộ |
| `from` | Chỉ định module nguồn |
| `as` | Đổi tên namespace, import, hoặc ép kiểu |
| `export` | Xuất hàm cho module khác |
| `share` | Chia sẻ biến cấp module |

### Ownership & Borrow

| Từ khoá / Cú pháp | Mục đích |
|---------|----------|
| `&expr` | Shared borrow — tham chiếu chỉ đọc, không tiêu thụ |
| `&mut expr` | Mutable borrow — tham chiếu ghi độc quyền |
| `let` | Ràng buộc bất biến; move semantics cho kiểu non-copy |
| `var` | Ràng buộc có thể thay đổi; move semantics cho kiểu non-copy |

> Kiểu Copy (`int`, `float`, `bool`, số nguyên có kích thước) được copy ngầm khi gán. Kiểu Move (`string`, `array`, `entity`, `dict`) chuyển ownership — dùng `&` để borrow thay vì move.

### Xử lý lỗi

| Từ khoá | Mục đích |
|---------|---------|
| `throw` | Ném lỗi (dừng luồng bình thường) |
| `ensure` | Bảo vệ phạm vi — luôn chạy khi thoát hàm |
| `revert` | Bảo vệ phạm vi — chỉ chạy khi lỗi/throw (cấp hàm và cấp try cục bộ) |
| `try` | Mở khối ranh giới bắt lỗi cục bộ |
| `erx` | Đọc mã lỗi đã throw (thanh ghi lỗi) |
| `emit` | Ghi sự kiện/log có cấu trúc |
| `timeout` | Tham số cho `try` — tự động huỷ sau thời hạn |
| `isolate` | Tham số cho `try` — khai báo biến cần snapshot & khôi phục tự động khi retry |
| `atomic` (var) | Bổ ngữ biến — cho phép mutation xuyên retry mà không khôi phục, tắt W302 (§13.7) |
| `resume retry` | Trong `revert` cục bộ — khởi lại khối try hiện tại |
| `resume revert` | Trong `revert` cục bộ — lan truyền đến revert cấp hàm |

### Tham số

| Từ khoá | Mục đích |
|---------|---------|
| `in` | Nhóm tham số đầu vào (chỉ đọc, mặc định) |
| `ref` | Nhóm tham số tham chiếu (đọc-ghi, ảnh hưởng bên gọi) |
| `out` | Nhóm tham số đầu ra (hàm nhận ghi, bên gọi nhận) |
| `this` | Tham số ngầm trong method; quy ước tham số đầu cho UFCS |

### FFI & Hệ thống

| Từ khoá | Mục đích |
|---------|---------|
| `@bind(c)` | Khai báo hàm C ngoại |
| `@bind(asm)` | Hàm hợp ngữ nội tuyến |
| `@bind(wasm)` | Khai báo hàm WASM ngoại |
| `@entry` | Đánh dấu điểm nhập kernel/bare-metal |
| `ptr` | Kiểu con trỏ thô |
| `precomp` | Khối/hàm thực thi thời gian biên dịch |
| `arena` | Khối sub-arena — vùng nhớ có phạm vi (§4.6) |
| `arr_compact` | Thu hồi dead space resize mảng (§19.4) |

### Bất đồng bộ

| Từ khoá | Mục đích |
|---------|---------|
| `async` | Khai báo hàm bất đồng bộ |
| `await` | Tạm dừng hàm và chờ thao tác async hoàn thành |
| `await pass` | Nhường quyền tường minh — tạm dừng một nhịp scheduler, chống chiếm CPU (§22.6) |
| `task` | Tạo tác vụ async; trả về task handle |
| `wait` | Chờ tác vụ hoàn thành — block bên gọi đến khi xong |
| `cancel` | Yêu cầu huỷ hợp tác tác vụ đang chạy (§22.7) |
| `select` | Đa nhiệm hoá sự kiện — chờ tác vụ đầu tiên hoàn thành trong nhiều task (§22.8) |
| `quiet` | Tạo tác vụ ly khai bắn-và-quên — không handle, không lan truyền lỗi (§22.9) |
| `port` | Khai báo cổng tín hiệu cấp module có kiểu — MPSC, hàng đợi, an toàn qua task (§23) |
| `send` | Đưa thông điệp vào port: `send port <- giá_trị` — không bao giờ chặn (§23.2) |
| `recv` | Nhận thông điệp từ port: `recv port` — điểm tạm dừng async (§23.3) |

### UI / Reactive

| Từ khoá | Mục đích |
|---------|----------|
| `reactive` | Biến trạng thái tự động cập nhật UI khi thay đổi — không cần gọi refresh thủ công (§25.1) |
| `morph` | Ánh xạ tĩnh từ entity/struct sang component UI tại thời biên dịch (§25.2) |
| `bundle` | Nhúng file tài nguyên vào binary lúc biên dịch; trả về slice hằng — không I/O runtime (§25.3) |
| `expose` | Chú thích hàm để compiler sinh API endpoint (REST, IPC, WASM export) (§25.4) |
| `isolate` (block) | Block sandbox bảo mật — giới hạn quyền truy cập bộ nhớ/I/O; phân biệt với `try(isolate:)` (§14.7) (§25.5) |

### AI / Học máy

| Từ khoá / Toán tử | Mục đích |
|---------|----------|
| `tensor<T>[S...]` | Mảng N chiều NPU/GPU-aligned — layout row-major, aligned 64-byte (§26.1) |
| `**` | Matmul — ánh xạ sang SIMD/Tensor-core (NEON FMMLA, AVX-512, WASM simd128) (§26.2) |
| `><` | Fused multiply-accumulate (FMA) — nhân + cộng tích lũy một lệnh, không round-off trung gian (§26.2) |
| `infer` | Block inference không gradient — tắt autodiff, thấp RAM (§26.3) |
| `train` | Block training với autodiff native — `.backward()` tính gradient tự động (§26.4) |
| `quantize` | Nén độ chính xác tensor (INT8/INT4) để tăng tốc inference, giảm RAM (§26.5) |

### Khác

| Từ khoá | Mục đích |
|---------|---------|
| `has` | Khai báo trước |
| `none` | Giá trị null |
| `true` / `false` | Giá trị boolean |
| `mod` | Toán tử modulo |
| `xor` / `shl` / `shr` | Toán tử bit |
| `and` / `or` | AND / OR bit |

---

## 30. Bảng ưu tiên toán tử

Từ cao đến thấp:

| Ưu tiên | Toán tử | Kết hợp |
|---------|---------|---------|
| 40 | `.` `?.` | Trái |
| 39 | `~` (postfix swizzle) | Trái |
| 38 | `!!` (postfix nguyên tử) | Trái |
| 28 | `!` `-` (unary) | Phải |
| 30 | `^` | Phải |
| 22 | `**` `><` | Trái |
| 20 | `*` `/` | Trái |
| 18 | `%` `mod` | Trái |
| 12 | `>>` `shl` `shr` `as` | Trái |
| 10 | `+` `-` | Trái |
| 8 | `:~` | Trái |
| 6 | `>` `<` `>=` `<=` | Trái |
| 5 | `==` `!=` `?=` `?=/=` | Trái |
| 3 | `&` `and` | Trái |
| 2 | `\|\|` `or` `xor` | Trái |
| 1 | `=` | Phải |

---

## 31. Thay đổi so với v1.2

| Tính năng | v1.2 | v2.0 |
|-----------|------|------|
| UFCS | — | `x.func()` ≡ `func(x)` với từ khoá `this` |
| Entity method | — | Từ khoá `method` bên trong entity cho hàm gắn kết |
| Packed entity | — | `packed entity` bố trí liên tiếp |
| Nội suy chuỗi | — | `"Hello $name"`, `"$(expr)"`, `"$$"` |
| throw | — | `throw <expr>` với mã lỗi |
| ensure | — | `ensure` bảo vệ phạm vi (luôn chạy) |
| revert | — | `revert` bảo vệ phạm vi (chỉ khi lỗi) |
| ref params | — | Khối tham số `in`/`ref`/`out` theo nhóm |
| FFI | — | `@bind(c)` giao tiếp C, `@bind(asm)` hợp ngữ, `@bind(wasm)` WASM |
| Register | — | `register Name: u32 ... end` ánh xạ bit |
| precomp | — | `precomp` bổ ngữ từ khoá cho tính toán thời biên dịch |
| @entry | — | Điểm nhập bare-metal tuỳ chọn |
| try / revert | — | `try: ... revert ... end` ranh giới lỗi cục bộ với bồi hoàn Saga |
| emit | — | `emit LOG_INFO(...)` ghi sự kiện/log có cấu trúc |
| timeout | — | `try(timeout: 5s):` tự động huỷ sau thời hạn |
| resume | — | `resume retry` / `resume revert` — điều khiển luồng trong revert cục bộ |
| isolate | — | `try(isolate: [x, y]):` snapshot & khôi phục tự động khi retry; cảnh báo W302 cho mutation chưa bảo vệ (§13.7) |
| resume retry an toàn | — | Compiler phát W302 nếu biến bị đột biến trong try, khối có `resume retry`, và biến không trong `isolate` hoặc chưa reset trong `revert` (§13.7) |
| `await pass` | — | Điểm nhường quyền tường minh — chống chiếm CPU trong vòng lặp async hợp tác (§22.6) |
| `cancel` | — | Huỷ tác vụ hợp tác — gửi tại `await` tiếp theo (§22.7) |
| `select` | — | Đa nhiệm hoá sự kiện — `select: on t1 as r: ... end` chạy đua nhiều tác vụ (§22.8) |
| `quiet` | — | Tác vụ ly khai bắn-và-quên — không handle, lỗi ghi log không lan truyền (§22.9) |
| `port` | — | Cổng tín hiệu cấp module có kiểu — MPSC, hàng đợi, an toàn qua async task (§23) |
| `send` / `recv` | — | Gửi/nhận thông điệp port — `send` không chặn, `recv` là điểm tạm dừng (§23.2–23.3) |
| `mold` | `register` (dùng đóng gói) | `mold Tên: u16 r:5, g:6, b:5 end` — bit-field đa dụng (§16.6) |
| `flux` | — | `flux<T, N>` — kiểu vector SIMD, ánh xạ sang NEON/SSE-AVX/WASM SIMD (§24.1) |
| Swizzle `~` | — | `v~xyz` — hậu tố xáo trộn/nhân bản kênh `flux`; write-masking: `v~xy = flux(a, b)` (§24.2) |
| `deck` | — | `deck tên: Kiểu[kích_thước]` — buffer chia sẻ CPU-GPU (§24.3) |
| `lock` / `!!` | — | Đọc-sửa-ghi nguyên tử: `lock x += 1` hoặc `x!! += 1` (§24.4) |
| `atomic` (var) | — | Bổ ngữ biến cho retry logic — cho phép mutation xuyên `resume retry` mà không bị khôi phục, tắt W302 (§13.7) |
| `lazy include` | — | Import trì hoãn chỉ kiểu — cho phép phụ thuộc vòng giữa module về `entity`/`enum` (§3.8) |
| Swizzle write-mask | — | `v~xy = flux(a, b)` — ghi chọn lọc kênh, kênh không nêu giữ nguyên; sinh `INS`/`BLENDPS` (§24.2) |
| `reactive` | — | Biến trạng thái tự động cập nhật UI — propagation tại biên dịch, không runtime refresh (§25.1) |
| `morph` | — | Ánh xạ tĩnh entity/struct → component UI — binding sinh tại biên dịch, không reflection (§25.2) |
| `bundle` | — | Nhúng tài nguyên vào binary lúc biên dịch — slice hằng, zero-overhead, không I/O (§25.3) |
| `expose` | — | Chú thích hàm thành API endpoint — compiler sinh REST/IPC/WASM glue code (§25.4) |
| `isolate` (block) | `try(isolate:)` (snapshot) | Block sandbox bảo mật — giới hạn quyền truy cập bộ nhớ/I/O; phân biệt với §13.7 (§25.5) |
| `tensor<T>[S...]` | — | Mảng N chiều NPU/GPU-aligned — row-major, aligned 64-byte, kiểm tra kích thước tại biên dịch (§26.1) |
| `**` | — | Matmul — `[M,K]**[K,N]→[M,N]`; ánh xạ NEON FMMLA / AVX-512 / WASM simd128 (§26.2) |
| `><` | — | Fused multiply-accumulate (FMA) — nhân + cộng tích lũy một lệnh, tránh round-off (§26.2) |
| `infer` | — | Block inference không gradient — tắt autodiff, ~50% RAM ít hơn train (§26.3) |
| `train` | — | Block training autodiff native — `.backward()` tính gradient ngược tự động (§26.4) |
| `quantize` | — | Nén độ chính xác tensor INT8/INT4 — tăng tốc inference, giảm RAM (§26.5) |
| erx | — | Thanh ghi lỗi — đọc mã lỗi đã throw |
| Borrow checker | — | An toàn ownership/borrow/move thời biên dịch — không runtime overhead (§4.8) |
| `&` / `&mut` | — | Cú pháp shared / mutable borrow — kiểm tra bởi borrow checker (§4.8) |
| Move semantics | — | Kiểu non-copy move khi gán; ràng buộc cũ bị vô hiệu hoá (§4.8) |
| arena block | — | `arena: ... end` sub-arena có phạm vi cho thu hồi bộ nhớ vòng lặp (§4.6) |
| Phân tầng runtime | — | Language / Compiler / Library tách cứng; compiler không biết scheduler; zero-cost = không dùng thì không có trong binary (§1.1, `VIR_EXECUTION_MODEL.md`) |
| callable field | — | Bước UFCS 2: `x.callback()` gọi field con trỏ hàm (§11) |
| Quy tắc biên lexer nội suy | — | `$ident` dừng tại `[`, toán tử; dùng `$(expr)` cho biểu thức phức tạp (§12.6) |
| arr_compact | — | `arr_compact(arr)` — thu hồi dead space resize mảng (§19.4) |
| Kiểu mũi tên trả về | `func f(): int` | `func f() -> int:` |
| dict (thay map) | `map[K,V]` | Kiểu `dict[K,V]` + literal `[key: value, ...]` — cùng cú pháp `[]`, có `:` là dict |
| Map biểu thức | — | `map x in list: out expr end` — biến đổi |
| Kiểu có kích thước | `int`, `float`, `string`, `bool` | + `i8`–`i64`, `u8`–`u64`, `ptr` |
| Include đường dẫn | `include math;` | + `include net.http;` (ánh xạ thư mục) |
| Include alias | — | `include net.http as web;` |
| Import alias | — | `import get from net.http as fetch;` |
| Get | — | `get PI from math;` (nhập biến/hằng) |

---

*Đặc tả Ngôn ngữ Vir v2.0 — Ngôn ngữ lập trình hệ thống biên dịch native không phụ thuộc.*
*Mục tiêu: ARM64 (Mach-O), x86-64 (ELF), WebAssembly.*
*Trình biên dịch tự lưu trữ: virc.vri (viết hoàn toàn bằng Vir).*
