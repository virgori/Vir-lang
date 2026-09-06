# Báo Cáo Kỹ Thuật: Phân Loại Lỗi Biên Dịch (Bugs), Lỗi Chẩn Đoán (Diagnostics) & Hạn Chế Thiết Kế (Limitations) Của Compiler Vir v2.0
## Đúc kết thực tế và thực chứng kỹ thuật trong quá trình phát triển InterVir Runtime

**Tài liệu tham chiếu:** Quá trình xây dựng 88 file mã nguồn, 4,366 dòng mã Vir thuần (`.vri`) và 41 test suites cho [InterVir Runtime](../../docs/INTERVIR_ARCHITECTURE.md).  
**Môi trường thử nghiệm:** Trình biên dịch tự lưu trữ `./bin/virc` (v2.2.0 HIR/MIR/LIR/MCInst pipeline) trên macOS ARM64 và Linux x86_64 / RISC-V 64.  
**Ngày cập nhật & chuẩn hóa:** 04/09/2026.

---

## 1. Tóm Tắt Định Hướng Lại Báo Cáo

Trong các bản báo cáo ban đầu, một số hành vi lỗi biên dịch, sự cố thực thi, hạn chế ngữ nghĩa và thiếu sót công cụ đóng gói đã bị gộp chung dưới danh nghĩa *"lỗi nghiêm trọng của compiler"*. 

Để phục vụ tốt nhất cho công tác bảo trì hệ thống và cung cấp phản hồi chuẩn xác cho nhóm phát triển compiler `virc`, tài liệu này tái cấu trúc toàn diện các vấn đề thành **3 nhóm độc lập về bản chất**:

1. **Bug thật của Compiler (Real Compiler & Codegen Bugs):** Mã nguồn hoàn toàn hợp lệ theo ngữ pháp và ngữ nghĩa, nhưng compiler sinh mã sai lệch, tính sai offset bộ nhớ hoặc phá vỡ quy ước ABI gây crash/hỏng dữ liệu ở runtime.
2. **Lỗi Chẩn Đoán & Kiểm Tra Cú Pháp (Parser / Diagnostic Validation Bugs):** Mã nguồn không hợp lệ (ví dụ: dùng từ khóa dành riêng làm định danh), nhưng lexer/parser không phát hiện và từ chối, lại thả cho AST không hợp lệ trôi xuống backend dẫn đến crash.
3. **Hạn Chế Thiết Kế Ngôn Ngữ, Ngữ Nghĩa & Thiếu Tiện Ích Hạ Tầng (Language Limitations, Semantic Gaps & Missing Features):** Ngôn ngữ hoạt động đúng theo đặc tả hiện hành nhưng còn thiếu tính năng, thiếu cảnh báo an toàn hoặc thiếu công cụ trong toolchain.

---

## 2. Nhóm I: Các Lỗi Thật Của Compiler (Real Compiler & Codegen Bugs)

Đây là những lỗi sinh mã (codegen) hoặc bố cục bộ nhớ (layout) sai hoàn toàn trên các source code Vir hợp lệ.

---

### Bug 1: Bảng Offset Trường Thực Thể Toàn Cục Không Phân Vùng Theo Kiểu (Global Struct Field Collision / Scoping Bug)
- **Phân loại:** **Symbol Resolution & Struct Lowering Bug (Rất nặng)**.
- **Mức độ:** **CRITICAL** (Gây silent data corruption hoặc đọc sai dữ liệu của struct khác).
- **Thực chứng bằng mã nguồn tối giản:**
  ```vir
  entity TraceContext:
      trace_id_hi: int # offset 0
      trace_id_lo: int # offset 8
      span_id: int     # offset 16
  end.

  entity LogEvent:
      level: int        # offset 0
      timestamp_ms: int # offset 8
      trace_id_hi: int  # offset 16 (trong LogEvent)
      trace_id_lo: int  # offset 24
      span_id: int      # offset 32
  end.

  func main():
      let ev = LogEvent(level: 1, timestamp_ms: 2, trace_id_hi: 333, trace_id_lo: 444, span_id: 555)
      # THỰC NGHIỆM: ev.trace_id_hi đọc ra giá trị 1 thay vì 333!
  end.
  ```
- **Bản chất nguyên nhân trong compiler:**
  Trình quản lý trường thực thể (Struct Field Table) của `virc` lưu trữ offset theo tên trường trong một bảng phẳng dùng chung trên toàn cục mà không gán kèm định danh kiểu (`TypeID -> FieldName -> Offset`). Khi `TraceContext` khai báo trường `trace_id_hi` ở byte offset 0, compiler chốt cứng offset 0 cho tên `trace_id_hi` trên toàn bộ chương trình. Đến khi `LogEvent` truy xuất `event.trace_id_hi` (vốn ở offset 16), backend phát sinh lệnh đọc offset 0, đọc nhầm trường `level`!
- **Giải pháp tạm thời trong InterVir:**
  Tiền tố hóa toàn bộ tên trường của các struct có nguy cơ trùng lặp (ví dụ: `log_trace_hi`, `log_span_id`, `engine_active_gen`, `snap_generation`) để mọi trường đều có tên độc nhất trên toàn AST.

---

### Bug 2: Trả Về Aggregate / Struct Chứa `string` Gây Hỏng ABI & Dữ Liệu Rác (Return ABI Corruption)
- **Phân loại:** **ABI Lowering & Calling Convention Bug**.
- **Mức độ:** **CRITICAL** (Chuỗi bị rỗng, trỏ tới dữ liệu rác hoặc crash `SIGSEGV`).
- **Triệu chứng:**
  Khi một hàm khởi tạo (factory) trả về struct chứa trường động (`string` hoặc con trỏ):
  ```vir
  func create_target(host: string, port_num: int) -> UpstreamTarget:
      out UpstreamTarget(host: host, port: port_num, is_tls: false)
  end.
  ```
  Khi caller nhận struct và truy cập `target.host`, chuỗi bị hỏng hoặc rỗng.
- **Phân tích kỹ thuật & Giả thuyết root cause:**
  - *Hiện tượng xác nhận:* Dữ liệu con trỏ chuỗi bên trong struct trả về bị sai lệch sau khi hàm callee kết thúc.
  - *Giả thuyết kỹ thuật cần kiểm chứng qua disassembly:* Trên ARM64 (AAPCS64), struct lớn hoặc chứa aggregate thường được trả về thông qua con trỏ đệm ẩn (indirect result buffer) do caller cấp phát và truyền qua thanh ghi `x8`. Rất có thể backend `virc` xử lý chưa đúng vùng đệm `x8`, hoặc con trỏ chuỗi trỏ vào vùng nhớ tạm thời trên stack frame của callee vốn đã bị hủy khi hàm trả về (dangling pointer).
- **Giải pháp tạm thời trong InterVir:**
  Tránh dùng hàm trả về struct chứa chuỗi. Sử dụng khởi tạo trực tiếp (inline literal) hoặc truyền `this` vào hàm khởi tạo kiểu in-place mutator:
  ```vir
  func init_target(this, h: string, p: int):
      this.host = h
      this.port = p
  end.
  ```

---

### Bug 3: Lệch Bố Cục Bộ Nhớ Do Thuật Toán Tính Căn Chỉnh / Padding (Struct Layout & Alignment Flaw)
- **Phân loại:** **Struct Layout Generator Bug**.
- **Mức độ:** **HIGH** (Làm sai lệch giá trị các trường kế cận tùy thuộc vào thứ tự khai báo).
- **Mô tả hành vi:**
  Nếu khai báo các trường `string` (con trỏ/fat pointer) đứng trước các trường nguyên thủy (`int`, `bool`, `enum`), compiler đôi khi tính toán sai offset kế cận, dẫn đến thao tác ghi trường này đè lên metadata của trường kia. Ngược lại, nếu đưa toàn bộ trường số lên đầu và chuỗi về cuối thì chương trình hoạt động bình thường.
- **Bản chất nguyên nhân trong compiler:**
  Cơ chế tính layout của `virc` áp dụng cơ chế cộng dồn kích thước tuần tự (naive accumulation) mà chưa tự động chèn các khoảng đệm căn chỉnh tự nhiên (natural alignment padding 8-byte) chuẩn xác cho mọi tổ hợp kiểu dữ liệu xen kẽ. Lập trình viên không nên phải thủ công sắp xếp trường để né lỗi tính offset của compiler.
- **Giải pháp tạm thời trong InterVir:**
  Áp dụng quy chuẩn thiết kế: **Toàn bộ trường số (`int`, `bool`, `enum`) đặt ở ĐẦU struct, toàn bộ trường `string` đặt ở CUỐI struct.**

---

## 3. Nhóm II: Lỗi Kiểm Tra Cú Pháp & Chẩn Đoán (Parser / Diagnostic Validation Bugs)

Nhóm này bao gồm các trường hợp mã nguồn sai quy chuẩn ngữ pháp nhưng compiler không từ chối, dẫn đến lỗi dây chuyền ở các tầng sau.

---

### Vấn Đề Từ Khóa `port`: Parser Không Chặn Reserved Keyword Làm Tham Số Hàm (Keyword Collision vs Symbol Shadowing)
- **Phân loại:** **Parser & Diagnostic Bug (Chẩn đoán lỗi thiếu sót)**.
- **Mức độ:** **HIGH** (Gây hiểu nhầm là lỗi codegen/shadowing).
- **Thực nghiệm làm rõ bản chất:**
  Trước đây, sự cố khi viết hàm:
  ```vir
  func contains_port(this, port: int) -> bool:
      if port >= this.start_port do
          out port <= this.end_port
      end
      out false
  end
  ```
  bị kết luận là *"Lỗi Symbol Shadowing giữa tham số hàm và trường của Entity"*.
  
  Tuy nhiên, **thực nghiệm kiểm tra chéo** đã chứng minh kết luận ban đầu là **chẩn đoán sai nguyên nhân gốc rễ**:
  1. **Thực nghiệm 1 (Định danh bình thường trùng tên trường):**
     ```vir
     entity Foo: value: int end.
     func test_param(value: int) -> int: out value end.
     # KẾT QUẢ: Chạy đúng 100%, trả về 42, KHÔNG hề có xung đột symbol!
     ```
  2. **Thực nghiệm 2 (Tham số `port` đứng độc lập, không có Entity nào):**
     ```vir
     func test_param(port: int) -> int: out port end.
     # KẾT QUẢ: Vẫn lỗi/sai giá trị ngay cả khi không hề có bất kỳ Entity nào trong mã nguồn!
     ```
- **Bản chất nguyên nhân gốc rễ:**
  Trong `stdlib/vir/compiler/lexer.vri` (dòng 377):
  ```vir
  table = vec_push(table, KeywordEntry ( word: fat_str_new("port"), tok: TokType.PortKw ))
  ```
  `port` là một **từ khóa dành riêng (reserved keyword)** của Vir (dùng cho actor/process messaging).  
  Theo ngữ pháp chuẩn của ngôn ngữ, tên tham số hàm bắt buộc phải là một `Identifier`. Tuy nhiên:
  - Lexer nhận diện đúng `port` là `TokType.PortKw`.
  - Parser lại **thiếu validation / error recovery**: chấp nhận một `TokType.PortKw` vào vị trí định danh tham số thay vì báo lỗi:
    ```text
    error: expected identifier, found reserved keyword `port`
    ```
  - AST mang nút token không hợp lệ này trôi xuống tầng Semantic và Codegen, nơi backend không liên kết được thanh ghi/slot stack của tham số, dẫn đến đọc rác hoặc sinh lệnh sai gây `SIGBUS`.
- **Đánh giá:**
  Đây là **Lỗi Parser / Chẩn đoán của Compiler** (cho phép invalid AST đi xuống backend), **hoàn toàn không phải lỗi Symbol Collision hay Shadowing giữa Parameter và Field**.

---

## 4. Nhóm III: Hạn Chế Thiết Kế Ngôn Ngữ, Ngữ Nghĩa & Thiếu Tiện Ích Hạ Tầng (Language Limitations, Semantic Gaps & Missing Features)

Các vấn đề dưới đây **không phải là lỗi biên dịch sinh mã sai**. Đây là các hành vi hoạt động đúng theo đặc tả hiện tại của Vir hoặc các tính năng chưa hoàn thiện trong hệ sinh thái.

---

### Hạn Chế 1: Ngữ Nghĩa Sao Chép Khi Index/Gán Struct (Value Copy vs In-place Mutation)
- **Phân loại:** **Language Design / Diagnostic Limitation**.
- **Mô tả hành vi:**
  ```vir
  let proc = supervisor.processes[i] # Thực hiện sao chép giá trị (value copy) ra stack
  proc.record_success()              # Chỉ biến đổi bản sao cục bộ trên stack!
  ```
  Phần tử gốc trong mảng `supervisor.processes[i]` không thay đổi.
- **Bản chất:**
  Nếu ngữ nghĩa của Vir quy định truy cập mảng và phép gán là sao chép giá trị (value copy semantics), thì việc `proc` không biến đổi phần tử gốc là **hành vi đúng ngữ nghĩa**. 
  Vấn đề là:
  - Ngôn ngữ chưa hỗ trợ kiểu tham chiếu/con trỏ rõ ràng (`&mut T`, `ref T`).
  - Compiler chưa có cơ chế kiểm tra (borrow analysis/warning) để cảnh báo khi lập trình viên gọi phương thức biến đổi trạng thái (mutator) trên một bản sao tạm thời (r-value copy).
- **Giải pháp trong InterVir:** Thiết kế API quản lý theo chỉ mục: `supervisor.record_process_success(i)`.

---

### Hạn Chế 2: Số Học Nguyên Bọc Vòng Mặc Định (Silent 2's Complement Wrapping Overflow)
- **Phân loại:** **Semantic / Runtime Limitation**.
- **Mô tả hành vi:**
  Khi tính toán Exponential Backoff `delay = delay * 2`, nếu vượt quá $2^{63}-1$, số bị biến thành số âm mà không kích hoạt ngoại lệ/trap.
- **Bản chất:**
  Trong hầu hết các ngôn ngữ lập trình hệ thống (C, C++, Go, Rust chế độ release), số nguyên có dấu bọc vòng theo chuẩn bù 2 (two's complement wrapping). Việc compiler phát lệnh `MUL`/`LSL` không kèm cờ kiểm tra tràn số chỉ chứng minh ngôn ngữ **không áp dụng checked arithmetic mặc định**, chứ không phải là compiler sai. Hành vi này chỉ bị coi là bug nếu đặc tả ngôn ngữ Vir (Spec) bắt buộc phải trap khi tràn số.
- **Giải pháp trong InterVir:** Chủ động lập trình phòng thủ với điều kiện chặn trần: `if cur >= max / 2 do ...`.

---

### Hạn Chế 3: Thiếu Hệ Thống Generics & Monomorphization
- **Phân loại:** **Missing Language Feature**.
- **Mô tả:** Chưa có container tổng quát (`List[T]`, `RingBuffer[T]`, `Map[K, V]`).
- **Hệ quả:** Phải viết lặp lại các mảng tĩnh dung lượng cố định (`fixed-size array` kèm biến đếm `count`) cho từng kiểu thực thể.

---

### Hạn Chế 4: Không Gian Tên `include` Dạng Văn Bản Phẳng
- **Phân loại:** **Module-System Limitation**.
- **Mô tả:** Lệnh `include "file.vri"` gộp mã nguồn vào một không gian tên phẳng toàn cục, chưa có tính bao đóng (`private`, `pub`) hay namespace module hoàn chỉnh.
- **Giải pháp:** Tiền tố hóa tên hàm theo module (ví dụ: `clamp_instances`).

---

### Hạn Chế 5: Toolchain Chưa Tự Động Codesign Mach-O Trên macOS ARM64
- **Phân loại:** **Toolchain / Packaging Deficiency**.
- **Mô tả:** Binary Mach-O sinh ra hợp lệ nhưng bị kernel Apple Silicon gửi `SIGKILL 9` do thiếu ad-hoc signature.
- **Đánh giá:** Đây là thiếu sót ở khâu hoàn thiện công cụ đóng gói (packaging), không phải lỗi tính đúng đắn của trình biên dịch.

---

### Hạn Chế 6: Thiếu Chuỗi Định Dạng (Interpolation) & Thư Viện StringBuilder
- **Phân loại:** **Language / Library Feature Gap**.
- **Mô tả:** Chưa có cú pháp `$"{code} {reason}"` và chưa có `StringBuilder` trong thư viện chuẩn, phải thao tác qua bộ đệm byte thủ công.

---

### Hạn Chế 7: Parser Chưa Hỗ Trợ Truy Xuất Thành Viên Đa Cấp (`a.b.c`)
- **Phân loại:** **Parser Grammar Limitation**.
- **Mô tả:** Biểu thức `this.store.active_generation` báo lỗi `expected expression [tok=90]`. Parser hiện tại mới chỉ xử lý toán tử truy xuất thành viên đơn cấp (`a.b`).

---

### Hạn Chế 8: Giới Hạn Biểu Diễn Số Nguyên Của Lexer
- **Phân loại:** **Lexer Limitation**.
- **Mô tả:** Lexer cắt bớt chữ số khi gặp literal số nguyên vượt quá phạm vi `INT64_MAX` (`0x7FFFFFFFFFFFFFFF`).

---

## 5. Bảng Đối Chiếu Phân Loại Chuẩn Hóa

| STT | Hiện Tượng / Vấn Đề | Phân Loại Cũ | **Phân Loại Chuẩn Hóa** | Đánh Giá Tính Đúng Đắn Của Compiler |
|:---:|---|---|---|---|
| 1 | `port` làm tham số hàm rồi crash `SIGBUS` | Codegen / Shadowing Bug | **Parser / Diagnostic Bug** | **Lỗi parser**: Không từ chối từ khóa dành riêng `port` ở vị trí identifier |
| 2 | Trùng tên trường giữa các struct khác nhau gây đọc sai offset | Codegen Bug | **Struct Lowering / Scoping Bug** | **Bug thật của compiler**: Bảng offset phẳng không phân vùng theo kiểu |
| 3 | Trả về struct chứa chuỗi gây hỏng dữ liệu | ABI Bug | **ABI / Aggregate Return Bug** | **Bug thật của compiler**: Quản lý bộ đệm trả về / con trỏ stack callee bị lỗi |
| 4 | Thứ tự trường làm lệch alignment/offset | Memory Layout Bug | **Struct Layout Generator Bug** | **Bug thật của compiler**: Thiếu tính toán padding tự nhiên tự động |
| 5 | Mutate bản copy struct không tác động phần tử gốc | Codegen Bug | **Semantic / Design Limitation** | **Đúng ngữ nghĩa copy**: Cần bổ sung `ref` hoặc diagnostic warning |
| 6 | Tràn số nguyên 64-bit im lặng | Codegen Limitation | **Semantic / Runtime Limitation** | **Đúng ngữ nghĩa 2's complement** (trừ khi spec yêu cầu checked trap) |
| 7 | Thiếu Generics (`List[T]`, `Map[K, V]`) | Compiler Limitation | **Missing Language Feature** | Chưa hỗ trợ tính năng |
| 8 | `include` gộp namespace phẳng | Compiler Limitation | **Module-System Limitation** | Chưa hoàn thiện module system |
| 9 | Mach-O binary thiếu chữ ký trên macOS | Compiler Bug | **Toolchain / Packaging Deficiency** | Binary đúng mã máy, thiếu bước signing trong toolchain |
| 10 | Thiếu String Interpolation / Buffer Builder | Compiler Limitation | **Language / Library Feature Gap** | Thiếu tiện ích cú pháp và thư viện chuẩn |
| 11 | Không hỗ trợ cú pháp `a.b.c` | Compiler Bug | **Parser Grammar Limitation** | Cú pháp đa cấp chưa được định nghĩa trong ngữ pháp |
| 12 | Cắt literal số nguyên > `INT64_MAX` | Compiler Bug | **Lexer Boundary Limitation** | Giới hạn miền giá trị biểu diễn số nguyên có dấu |

---

## 6. Lộ Trình & Đề Xuất Ưu Tiên Cho Nhóm Phát Triển Compiler

Việc phân loại rành mạch giúp phân bổ nguồn lực đội ngũ compiler chính xác:

### Nhóm Ưu Tiên 1: Sửa Lỗi Tính Đúng Đắn Của Mã Nguồn Hợp Lệ (Fix Compiler Bugs)
1. **Sửa bảng offset trường của Struct:** Gắn vùng offset theo `TypeID` (`TypeID -> FieldName -> Offset`) để loại bỏ hoàn toàn lỗi collision đọc sai offset giữa các struct (Bug 1).
2. **Sửa ABI Return Aggregate/Struct:** Chuẩn hóa con trỏ đệm gián tiếp (thanh ghi `x8` trên ARM64) và bảo toàn vòng đời vùng nhớ khi struct chứa chuỗi được trả về (Bug 2).
3. **Chuẩn hóa Padding/Alignment trong Struct Layout:** Đảm bảo tự động chèn padding 8-byte đúng chuẩn để lập trình viên tự do sắp xếp thứ tự trường (Bug 3).

### Nhóm Ưu Tiên 2: Nâng Cấp Bộ Phân Tích & Chẩn Đoán Lỗi (Parser & Diagnostics)
1. **Kiểm tra từ khóa tại vị trí định danh (Identifier Validation):** Ngăn chặn toàn bộ từ khóa dành riêng (`port`, `module`, `entity`, v.v.) được dùng làm tên tham số/biến; báo lỗi cú pháp sớm tại parser thay vì thả trôi xuống codegen.
2. **Hỗ trợ biểu thức truy xuất đa cấp (`a.b.c`):** Mở rộng ngữ pháp parser cho phép lồng ghép truy xuất thuộc tính liên tiếp.
3. **Cảnh báo Mutation trên R-Value / Bản sao:** Phân tích luồng dữ liệu để phát cảnh báo khi gọi phương thức mutating trên một biến vừa được sao chép từ mảng.

### Nhóm Ưu Tiên 3: Bổ Sung Tính Năng Ngôn Ngữ & Tiện Ích Toolchain (Features & Tooling)
1. **Hệ thống tham chiếu/mượn tường minh (`ref T`, `&mut T`):** Hỗ trợ thao tác trực tiếp lên phần tử của container mà không cần copy.
2. **Tự động ký mã Mach-O:** Tích hợp ad-hoc codesigning vào lệnh build của `virc` trên macOS ARM64.
3. **Generics & Thư viện đệm chuỗi:** Xây dựng các container cơ bản và `StringBuilder` trong thư viện chuẩn `stdlib`.
