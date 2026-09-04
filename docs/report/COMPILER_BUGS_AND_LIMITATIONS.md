# Báo Cáo Kỹ Thuật: Lỗi Biên Dịch (Bugs) & Hạn Chế (Limitations) Của Compiler Vir v2.0
## Đúc kết thực tế trong quá trình phát triển InterVir Runtime (Phases 1 – 10)

**Tài liệu tham chiếu:** Quá trình xây dựng 88 file mã nguồn, 4,366 dòng mã Vir thuần (`.vri`) và 41 test suites cho [InterVir Runtime](../INTERVIR_ARCHITECTURE.md).  
**Môi trường:** Trình biên dịch tự lưu trữ `./bin/virc` trên macOS ARM64 (Apple Silicon).  
**Ngày lập báo cáo:** 04/09/2026.

---

## 1. Tóm Tắt Tổng Quan

Trong suốt quá trình triển khai 10 Phase đầu tiên của InterVir Runtime hoàn toàn bằng ngôn ngữ Vir (`.vri`), nhóm phát triển đã tương tác trực tiếp và sâu sát với backend sinh mã native ARM64 của compiler `virc`. 

Báo cáo này **không trích xuất từ các tài liệu lý thuyết cũ của Vir**, mà phản ánh **100% các lỗi nghiêm trọng (critical bugs), các hành vi sinh mã sai (codegen flaws), và các hạn chế ngôn ngữ/hạ tầng biên dịch** đã thực sự phát sinh và gây crash chương trình trong quá trình viết mã nguồn InterVir, kèm theo nguyên nhân gốc rễ (root cause) và giải pháp khắc phục (workaround) đã được áp dụng để đưa toàn bộ 41 test suite đạt trạng thái PASS 100%.

---

## 2. Các Lỗi Nghiêm Trọng Của Compiler (Critical Codegen & ABI Bugs)

### Bug 1: Xung Đột Tên Tham Số Hàm và Trường Của Entity (Symbol Collision gây Crash SIGBUS 138)
- **Mức độ:** **CRITICAL** (Gây crash nhị phân tức thì khi thực thi).
- **Ngữ cảnh phát hiện:** Phát sinh trong Phase 5 (`proxy/upstream.vri`), Phase 10 (`port_range/allocator.vri`, `port_range/sub_range.vri`, `port_range/manager.vri`).
- **Mô tả hành vi:**
  Khi một hàm khai báo tham số có tên **trùng khớp chính xác** với tên của một trường (field) trong bất kỳ `entity` nào tồn tại trong đồ thị AST biên dịch (ví dụ: tham số `port: int` trong khi đã có `entity PortLease { port: int }` hoặc `entity UpstreamTarget { port: int }`):
  ```vir
  // GÂY CRASH SIGBUS 138
  func contains_port(this, port: int) -> bool:
      if port >= this.start_port do
          out port <= this.end_port
      end
      out false
  end
  ```
- **Nguyên nhân gốc rễ trong compiler:**
  Trình phân giải tên biểu thức (Expression Name Resolver / Symbol Lookup) trong giai đoạn hạ mức IR của `virc` ưu tiên tra cứu bảng trường của struct trước hoặc nhầm lẫn offset của trường struct với vị trí thanh ghi/slot stack của tham số hàm. Thay vì phát sinh lệnh đọc thanh ghi tham số (`x1`/`w1`), `virc` phát sinh lệnh đọc bộ nhớ theo offset struct không hợp lệ, dẫn đến lỗi căn chỉnh địa chỉ bộ nhớ hoặc truy cập vùng cấm, gây ra lỗi **Bus Error: 138 (`SIGBUS`)**.
- **Giải pháp khắc phục trong InterVir:**
  Phải chủ động đổi tên toàn bộ các tham số này để không bao giờ trùng với tên trường của bất kỳ entity nào:
  ```vir
  // GIẢI PHÁP: Đổi 'port' thành 'p' hoặc 'target_port'
  func contains_port(this, p: int) -> bool:
      if p >= this.start_port do
          out p <= this.end_port
      end
      out false
  end
  ```

---

### Bug 2: Trả Về Struct Chứa Trường `string` Từ Hàm Gây Hỏng ABI & Rác Bộ Nhớ (Return ABI Corruption)
- **Mức độ:** **CRITICAL** (Gây hỏng dữ liệu chuỗi hoặc lỗi phân đoạn `SIGSEGV`).
- **Ngữ cảnh phát hiện:** Phát sinh trong Phase 6 (`app_runtime/descriptor.vri`), Phase 7 (`app_runtime/internal_req.vri`), Phase 10 (`port_range/manager.vri`).
- **Mô tả hành vi:**
  Khi viết một hàm tiện ích khởi tạo (factory function) trả về một cấu trúc có chứa các trường kiểu `string` (hoặc con trỏ động):
  ```vir
  // GÂY LỖI HỎNG CON TRỎ CHUỖI
  func create_target(host: string, port: int) -> UpstreamTarget:
      out UpstreamTarget(host: host, port: port, is_tls: false)
  end
  ```
  Khi caller nhận kết quả và truy cập `target.host`, chuỗi nhận được bị rỗng, trỏ tới vùng nhớ rác hoặc chương trình bị crash bộ nhớ.
- **Nguyên nhân gốc rễ trong compiler:**
  Trên kiến trúc ARM64 theo chuẩn AAPCS64, các cấu trúc dữ liệu tổng hợp (aggregates) có kích thước lớn hoặc chứa con trỏ cần được trả về qua con trỏ bộ đệm ẩn do caller cấp phát (thanh ghi `x8`). Backend của `virc` chưa xử lý hoàn chỉnh con trỏ đệm gián tiếp này cho các struct chứa chuỗi; vùng stack của hàm callee bị giải phóng (epilogue) trước khi dữ liệu chuỗi được bảo toàn, khiến con trỏ chuỗi trỏ vào stack frame đã chết (dangling pointer).
- **Giải pháp khắc phục trong InterVir:**
  Tuyệt đối không dùng hàm trả về struct chứa `string`. Thay vào đó:
  1. Khởi tạo trực tiếp (inline struct literal) tại nơi sử dụng:
     ```vir
     let target = UpstreamTarget(host: "127.0.0.1", port: 8080, is_tls: false)
     ```
  2. Hoặc khởi tạo trước rồi truyền theo con trỏ `this` vào hàm khởi tạo kiểu mutator:
     ```vir
     func init_target(this, h: string, p: int):
         this.host = h
         this.port = p
     end
     ```

---

### Bug 3: Lệch Bố Cục Bộ Nhớ Do Thứ Tự Khai Báo Trường (Struct Layout & Alignment Flaw)
- **Mức độ:** **HIGH** (Làm sai lệch giá trị các trường kế cận).
- **Ngữ cảnh phát hiện:** Xuất hiện trong `PortLease`, `ProcessHandle`, `AppDescriptor`.
- **Mô tả hành vi:**
  Nếu khai báo các trường `string` đứng TRƯỚC các trường kiểu số (`int`, `bool`, `enum`):
  ```vir
  // DỄ GÂY LỖI SAI LỆCH DỮ LIỆU
  entity BadLayout:
      app_id: string,
      instance_id: string,
      port: int,
      state: int
  end
  ```
  Khi gán giá trị cho `port` hoặc `state`, giá trị đọc ra bị sai, hoặc thao tác ghi làm hỏng metadata con trỏ của `app_id` / `instance_id`.
- **Nguyên nhân gốc rễ trong compiler:**
  Bộ tạo bố cục bộ nhớ (Struct Layout Generator) của `virc` tính toán offset theo cơ chế cộng dồn tuần tự thô sơ (naive accumulation), không thực hiện căn chỉnh tự nhiên (natural alignment padding 8-byte) chuẩn xác khi xen kẽ giữa kiểu động (`string`) và kiểu nguyên thủy (`int`/`bool`).
- **Giải pháp khắc phục trong InterVir:**
  Áp dụng quy tắc thiết kế nghiêm ngặt 100% cho mọi entity:
  **Luôn khai báo toàn bộ các trường số (`int`, `bool`, `enum`) ở ĐẦU, và các trường `string` ở CUỐI.**
  ```vir
  // ĐÚNG CHUẨN AN TOÀN TRÊN VIRC
  entity PortLease:
      port: int,
      state: int,
      expires_at_ms: int,
      app_id: string,
      instance_id: string,
      node_id: string
  end
  ```

---

## 3. Các Hạn Chế Ngôn Ngữ & Compiler Gây Trở Ngại Khi Thiết Kế Hệ Thống (Compiler Limitations)

### Hạn chế 1: Mập Mờ Ngữ Nghĩa Mutation Giữa Truyền Tham Chiếu và Sao Chép Giá Trị (Value-Copy vs Mutation Trap)
- **Mức độ ảnh hưởng:** **RẤT CAO** (Rủi ro trực tiếp đến tính đúng đắn của State Machine).
- **Thực tế trong InterVir:**
  Trong Phase 8 (Process Supervision) và Phase 9 (Scaling), các entity quản lý trạng thái (`HealthPolicy`, `ProcessHandle`, `ScalePolicy`) cần được cập nhật liên tục.
  Trong Vir, phương thức gọi theo cú pháp UFCS `entity.update()` truyền con trỏ ngầm định `this`, cho phép mutate tại chỗ. Tuy nhiên, nếu caller thực hiện gán:
  ```vir
  let proc = supervisor.processes[i] // THỰC HIỆN SHALLOW COPY RA STACK
  proc.record_success()              // CHỈ UPDATE BẢN SAO TRÊN STACK!
  ```
  Thì phần tử thực sự nằm trong mảng `supervisor.processes[i]` **hoàn toàn không được cập nhật**, khiến trạng thái của hệ thống bị đóng băng mà compiler không hề phát sinh bất kỳ cảnh báo nào.
- **Hạn chế của compiler:**
  Vir v2.0 chưa hỗ trợ cú pháp con trỏ/tham chiếu rõ ràng (`&mut T`, `ref T`), cũng như chưa có con trỏ trực tiếp đến phần tử của mảng (`&arr[i]`). Compiler cũng thiếu phân tích mượn (borrow analysis) để cảnh báo khi gọi phương thức mutating trên một biến r-value hoặc biến copy tạm thời.
- **Cách InterVir giải quyết:**
  Phải viết các hàm quản lý điều phối theo dạng index: `supervisor.record_process_success(proc_index)` để truy cập và biến đổi trực tiếp trên mảng dữ liệu gốc.

---

### Hạn chế 2: Không Có Cơ Chế Kiểm Soát Tràn Số Nguyên (Silent Integer Overflow)
- **Mức độ ảnh hưởng:** **HIGH** (Gây lỗi logic nghiêm trọng khi chạy dài hạn).
- **Thực tế trong InterVir:**
  Trong `supervisor/backoff.vri`, thuật toán Exponential Backoff tính toán:
  $$\text{delay} = \text{base\_delay} \times 2^{\text{consecutive\_crashes}}$$
  Nếu một tiến trình crash liên tục 60 lần, phép nhân `delay = delay * 2` sẽ tràn số nguyên 64-bit có dấu.
- **Hạn chế của compiler:**
  `virc` trên ARM64 phát sinh lệnh `MUL`/`LSL` thông thường, không kiểm tra cờ tràn số (Overflow Flag `V`) và không cung cấp các hàm nội tại bão hòa (saturating intrinsics). Khi tràn số, biến `delay` chuyển thành số âm hoặc giá trị gần 0, khiến supervisor kích hoạt **restart-storm** liên tục, làm sập toàn bộ hệ thống.
- **Cách InterVir giải quyết:**
  Phải lập trình phòng thủ thủ công trước từng phép toán số học:
  ```vir
  func next_backoff_delay(this) -> int:
      let cur = this.current_delay_ms
      if cur >= this.max_delay_ms / 2 do
          this.current_delay_ms = this.max_delay_ms
      else
          this.current_delay_ms = cur * 2
      end
      out this.current_delay_ms
  end
  ```

---

### Hạn chế 3: Thiếu Hệ Thống Generics & Monomorphization (Dẫn Đến Trùng Lặp Boilerplate)
- **Mức độ ảnh hưởng:** **MEDIUM - HIGH** (Tăng kích thước mã và độ phức tạp bảo trì).
- **Thực tế trong InterVir:**
  InterVir cần hàng loạt cấu trúc dữ liệu dạng bảng/danh sách: `ConnectionTable`, `BufferPool`, `AppRegistry`, `InstanceRegistry`, `AppExecutionDomain`, `PortAllocator`.
- **Hạn chế của compiler:**
  Do `virc` chưa hoàn thiện Generic Container (`List[T]`, `RingBuffer[T]`, `Map[K, V]`), toàn bộ các cấu trúc trên buộc phải cài đặt thủ công lặp đi lặp lại bằng mảng tĩnh có dung lượng cố định (`fixed-size array` kèm biến `count`).
- **Hệ quả:**
  - Phát sinh hàng trăm dòng mã boilerplate giống nhau cho các thao tác `add`, `find`, `remove`.
  - Phải đặt cứng giới hạn dung lượng (`MAX_APPS = 32`, `MAX_INSTANCES = 128`, `MAX_CONNS = 1024`, `PORT_MAX = 512`) và tự kiểm tra tràn dung lượng ở runtime.

---

### Hạn chế 4: Cơ Chế `include` Dạng Nối Tệp Phẳng (Thiếu Module Namespaces & Encapsulation)
- **Mức độ ảnh hưởng:** **MEDIUM**.
- **Thực tế trong InterVir:**
  Khi chia tách 88 file mã nguồn và các file kiểm thử trong `tests/unit/`.
- **Hạn chế của compiler:**
  Lệnh `include "file.vri"` hoạt động tương tự tiền xử lý văn bản thô, gộp toàn bộ ký hiệu vào một không gian tên phẳng duy nhất (global scope). 
- **Hệ quả:**
  - Không có tính bao đóng (encapsulation): không có từ khóa `private` hay `pub`.
  - Dễ bị xung đột tên hàm tiện ích chung giữa các module (ví dụ: hàm `min(a, b)`, `max(a, b)` hoặc `clamp(v, min, max)`). InterVir phải tự đặt tiền tố cho các hàm tiện ích theo từng module (ví dụ: `clamp_instances`).

---

### Hạn chế 5: Trình Biên Dịch Không Tự Động Ký Mã (Missing Ad-hoc Code-signing trên macOS ARM64)
- **Mức độ ảnh hưởng:** **MEDIUM** (Ảnh hưởng đến trải nghiệm phát triển và CI/CD).
- **Thực tế trong InterVir:**
  Mỗi khi biên dịch một file test bằng `./bin/virc test.vri -o test_bin`, binary Mach-O được sinh ra hợp lệ nhưng khi chạy sẽ bị hệ điều hành macOS gửi tín hiệu `SIGKILL (exit code 9)` ngay lập tức.
- **Hạn chế của compiler:**
  `virc` tạo file thực thi Mach-O nhưng không tự động ghi chữ ký hợp lệ (ad-hoc code signature) theo yêu cầu bắt buộc của Apple Silicon Security Subsystem.
- **Cách InterVir giải quyết:**
  Tất cả các lệnh build và test runner phải tự nối thêm bước ký:
  ```bash
  ./bin/virc "$f" -o "$b" && codesign -s - -f "$b" && "$b"
  ```

---

### Hạn chế 6: Thiếu Chuỗi Định Dạng (String Interpolation) & Buffer Builder
- **Mức độ ảnh hưởng:** **MEDIUM**.
- **Thực tế trong InterVir:**
  Trong Phase 3 (`protocol/http1_serializer.vri`), hệ thống cần tuần tự hóa các thông điệp HTTP (ví dụ: `HTTP/1.1 200 OK\r\nContent-Length: 42\r\n\r\n`).
- **Hạn chế của compiler:**
  Chưa có cú pháp nội suy chuỗi kiểu `$"{code} {reason}"` và chưa có kiểu dữ liệu `StringBuilder` chuẩn trong core runtime.
- **Cách InterVir giải quyết:**
  Phải tự xây dựng cơ chế ghi byte trực tiếp qua `BufferSlice` và mảng tĩnh để tránh phân mảnh bộ nhớ và vượt qua hạn chế nối chuỗi của compiler.

---

## 4. Bảng Đối Chiếu Tổng Kết: Vấn Đề vs Giải Pháp Trong InterVir

| STT | Vấn đề trong `virc` | Phân loại | Triệu chứng khi chạy | Giải pháp áp dụng trong InterVir |
|:---:|---|---|---|---|
| 1 | Trùng tên tham số hàm với tên trường của struct | **Codegen Bug** | Crash `SIGBUS 138` | Đổi tên tham số khác hoàn toàn với tên field (`p`, `target_port`) |
| 2 | Hàm trả về struct chứa trường `string` | **ABI Bug** | Chuỗi bị rác, crash `SIGSEGV` | Dùng inline literal struct hoặc pattern mutator với con trỏ `this` |
| 3 | Khai báo trường `string` đứng trước trường số | **Memory Layout** | Sai lệch offset, ghi đè trường cạnh | Quy chuẩn: trường số (`int`, `bool`, `enum`) đặt TRƯỚC, `string` đặt CUỐI |
| 4 | Gọi mutating method trên bản copy struct | **Language Limitation** | State update không có tác dụng | Truy xuất và update trực tiếp theo chỉ mục mảng `arr[idx]` |
| 5 | Tràn số nguyên 64-bit không có trap | **Codegen Limitation** | Delay biến thành số âm, storm restart | Tự viết điều kiện guard chặn trần trước khi nhân |
| 6 | Chưa có Generics (`List[T]`, `Map[K, V]`) | **Language Limitation** | Trùng lặp code boilerplate | Dùng mảng cố định kèm biến đếm và kiểm tra capacity thủ công |
| 7 | `include` gộp không gian tên phẳng | **Module Limitation** | Xung đột tên hàm tiện ích | Tiền tố hóa tên hàm theo module |
| 8 | Mach-O binary thiếu chữ ký trên Apple Silicon | **Tooling Limitation** | Bị kernel gửi `SIGKILL 9` | Bắt buộc chạy `codesign -s - -f` sau biên dịch |

---

## 5. Đề Xuất Ưu Tiên Sửa Lỗi Cho Compiler Team (`virc`)

Dựa trên thực tế xây dựng InterVir, nhóm kiến trúc khuyến nghị các ưu tiên sửa lỗi cho compiler `virc` theo thứ tự:

1. **Ưu tiên 1 (Khẩn cấp):** Sửa lỗi Symbol Lookup trong bộ sinh mã ARM64 để ưu tiên phạm vi biến cục bộ / tham số hàm trước khi tìm kiếm trường thực thể (giải quyết triệt để lỗi SIGBUS 138).
2. **Ưu tiên 2 (Khẩn cấp):** Chuẩn hóa việc trả về struct chứa con trỏ/string qua thanh ghi `x8` (Indirect Result Buffer) trên ARM64.
3. **Ưu tiên 3:** Tự động gọi hoặc nhúng chữ ký ad-hoc code signature khi phát sinh file nhị phân Mach-O trên nền tảng macOS ARM64.
4. **Ưu tiên 4:** Sửa thuật toán tính toán kích thước và padding của struct để hỗ trợ thứ tự khai báo trường tự do mà không gây lệch byte offset.
5. **Ưu tiên 5:** Bổ sung phân tích cảnh báo hoặc cú pháp tham chiếu tường minh (`&mut`) để loại bỏ rủi ro cập nhật nhầm trên bản sao tạm thời.
