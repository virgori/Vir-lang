# Báo Cáo Kỹ Thuật: Phân Tích Khoảng Cách & Lộ Trình Hiện Thực Hóa Full Compiler Vir v2.0
## (Khắc Phục Hạn Chế Mini-Compiler, Đạt Chuẩn 100% Đặc Tả Ngôn Ngữ Vir v2.0)

**Tác giả:** Gemini Coding Assistant  
**Dự án:** Vir Programming Language (`virc`, `stdlib/vir`)  
**Ngày lập:** 27/08/2026  
**Tài liệu tham chiếu:** [vir_language_spec_v2.0_vi.md](vir_language_spec_v2.0_vi.md), [ARCHITECTURE.md](ARCHITECTURE.md), [STDLIB_ROADMAP.md](STDLIB_ROADMAP.md)

---

## 1. Tuyên Bố Mục Tiêu (Executive Summary)

Ngôn ngữ Vir được thiết kế như một **ngôn ngữ hệ thống độc lập, hiệu năng cao, zero-cost abstractions, an toàn bộ nhớ và định hướng AI/Native Systems**.

Compiler Stage-1 (`virc_stage1.vri`) đã hoàn thành sứ mệnh lịch sử quan trọng: **Đạt mốc Tự Biên Dịch (Self-Hosting Cycle 100% Native Vir Success với 102/102 test pass)**. Tuy nhiên, kiến trúc ban đầu của Stage-1 được tối giản thành một "bootstrap subset" để đạt mục tiêu self-host nhanh nhất.

> **NGUYÊN TẮC BẮT BUỘC:**  
> **Không chấp nhận mô hình "mini compiler" hay "toy subset".**  
> Toàn bộ compiler chính thức của Vir phải hiện thực hoá **100% đầy đủ, nghiêm ngặt và không lược bớt** tất cả các tính năng đã được chuẩn hóa trong [Đặc Tả Ngôn Ngữ Vir v2.0](vir_language_spec_v2.0_vi.md).

Báo cáo này cung cấp:
1. Bản đối soát chi tiết từng tính năng (Feature-by-Feature Gap Analysis) giữa Spec v2.0 và Stage-1 hiện tại.
2. Thiết kế kiến trúc chuỗi pipeline 4 tầng IR chuẩn mực (`AST` $\rightarrow$ `HIR` $\rightarrow$ `MIR` $\rightarrow$ `LIR` $\rightarrow$ `Codegen`).
3. Lộ trình triển khai cụ thể từng giai đoạn để nâng cấp compiler đạt mức công nghiệp (Production/Full-Grade Compiler).

---

## 2. Ma Trận Đối Soát Toàn Diện: Spec v2.0 vs Trạng Thái Compiler Hiện Tại

Dưới đây là phân tích chi tiết theo 10 trụ cột tính năng của ngôn ngữ Vir v2.0:

### 2.1. Hệ Thống Module & Không Gian Tên (§3)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§3.1, §3.2** | `include path;`<br>`include a, b as alias;` | Chỉ nạp nối chuỗi file phẳng qua bộ tiền xử lý thô | Xây dựng đồ thị phụ thuộc module (Module Dependency Graph - DAG), kiểm tra chống phụ thuộc vòng (Cycle Detection: `DangParse` $\rightarrow$ `DaParse`), hỗ trợ alias `as`. | **Cao** |
| **§3.3** | `import symbol1, symbol2 from module;` | Bị bỏ qua (skip token) | Bảng xuất nhập ký hiệu (Import/Export Symbol Table), liên kết symbol theo không gian tên cục bộ và toàn cục. | **Cao** |
| **§3.4** | `export func1, entity2;` | Bị bỏ qua (skip token) | Quản lý tầm nhìn Public / Private: chỉ các định danh được `export` mới được phép import ở module khác. | **Cao** |
| **§3.5** | `share counter, mode;` | Chưa có | Quản lý biến cấp module dùng chung trong cùng tiến trình (Module-Level Shared Memory). | **Trung bình** |
| **§3.8** | `lazy include module;` | Chưa có | Trì hoãn phân giải kiểu dữ liệu (Lazy Type Resolution), cho phép hai module phụ thuộc vòng về mặt cấu trúc kiểu (`entity`/`enum`). | **Trung bình** |

---

### 2.2. Hệ Thống Kiểu Dữ Liệu Tĩnh & Primitive Types (§5, §6, §7, §8, §9)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§5.1** | Integer Types:<br>`int`, `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, `u64` | Toàn bộ biến ngầm định là `i64` | Bộ kiểm tra kiểu (Type Checker), kiểm soát tràn số theo kiểu (Overflow Checking), sinh mã tải/lưu đúng độ rộng byte (`LDRB`, `LDRH`, `LDRSW`, `LDRX`). | **Rất Cao** |
| **§5.2** | Float Types:<br>`f32`, `f64` | Chưa có | Hỗ trợ thanh ghi số thực ARM64 (`S0..S31`, `D0..D31`), các phép toán `FADD`, `FSUB`, `FMUL`, `FDIV`, `FCMP`. | **Cao** |
| **§5.3** | `bool`, `char`, `ptr`, `void` | `bool` dùng số nguyên `0/1` | Định nghĩa kiểu rõ ràng trong Symbol Table, ép kiểu an toàn (Safe Type Casting). | **Cao** |
| **§5.4** | Native `string` Type | Chuỗi con trỏ null-terminated C-style | Cấu trúc String chuẩn: `{ data: ptr, byte_len: int, char_len: int }`, hỗ trợ slice `s[0..5]`, duyệt UTF-8 và nối chuỗi an toàn. | **Rất Cao** |
| **§5.5** | Type Alias:<br>`type Name = Target;` | Bị bỏ qua | Bảng tra cứu bí danh kiểu trong Symbol Table, phân giải kiểu đệ quy lúc biên dịch. | **Cao** |
| **§6** | Tagged Union `enum`:<br>`enum Option[T]: None, Some(T) end.` | Chưa có | Bộ bố trí bộ nhớ Enum: `Tag (u32) + Max Payload Alignment`, phân bổ bộ nhớ cho generic/tải trọng, làm nền tảng cho `Result` và `Option`. | **Rất Cao** |
| **§7** | `entity` với Methods & Packed Layout | Đã có: struct field read/write cơ bản | • Phương thức gắn liền với Entity (`method func(self): ... end`)<br>• `packed entity` (không padding, căn chỉnh byte chặt chẽ cho giao thức mạng). | **Rất Cao** |
| **§8** | `mold` (Interfaces / Layout Traits) | Chưa có | Bảng hàm ảo (vtable) hoặc kiểm tra tương thích bố cục tĩnh lúc biên dịch (Compile-time duck typing). | **Trung bình** |
| **§9** | `register` (MMIO Hardware Bitfields) | Chưa có | Thao tác `volatile` đọc/ghi thanh ghi phần cứng và tự động sinh mặt nạ bitfield (`BFXIL`, `UBFX`, `SBFX`). | **Trung bình** |

---

### 2.3. Quản Lý Bộ Nhớ, Quyền Sở Hữu & Borrow Checker (§4)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§4.1, §4.6** | Sub-Arena:<br>`arena: ... end` | Đã có (hạ mức thô qua bump watermark) | Khung Sub-Arena chuẩn hóa, kiểm tra tĩnh không cho con trỏ arena thoát ra ngoài phạm vi (Arena Escape Static Check). | **Cao** |
| **§4.2** | Move Semantics & Ownership | Chưa có (mọi giá trị copy tự do) | Bộ theo dõi trạng thái sở hữu (Ownership State: `Valid`, `Moved`), ngăn chặn sử dụng biến sau khi đã move (`Use-After-Move Error`). | **Rất Cao** |
| **§4.3** | Borrow Checker:<br>`&x` (shared), `&mut x` (mutable) | Chưa có | Bộ phân tích mượn tĩnh (Static Borrow Checker):<br>• Nhiều shared borrow HOẶC duy nhất một mutable borrow.<br>• Không được sửa biến khi đang có shared borrow. | **Rất Cao** |
| **§4.7** | `isolate(x, y): ... end` | Chưa có | Kiểm tra phạm vi cách ly: ngăn chặn truy cập bất kỳ biến ngoài nào không nằm trong danh sách isolate, đảm bảo không có race condition. | **Cao** |

---

### 2.4. Cấu Trúc Điều Khiển Mở Rộng & So Khớp Mẫu (§11, §12, §13)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§11.1** | `if cond do ... else ... end` | Đã hoàn chỉnh | Đã có | **Hoàn thành** |
| **§11.2** | `when cond loop ... end` | Đã hoàn chỉnh | Đã có | **Hoàn thành** |
| **§11.3** | Pattern Matching:<br>`case expr of pattern => ... end` | Chưa có | Cây quyết định so khớp (Decision Tree Pattern Matching) cho: hằng số số nguyên, hằng số chuỗi, biến thể `enum`, và tuple destructuring. | **Rất Cao** |
| **§11.4** | `break`, `skip` | Chưa có | Stack nhãn điều khiển vòng lặp để sinh lệnh nhảy `B exit_label` và `B continue_label`. | **Cao** |
| **§12** | `defer expr;` | Chưa có | Stack biểu thức cleanup: tự động chèn mã của `defer` theo thứ tự LIFO trước mọi câu lệnh `out`, `throw`, hoặc cuối khối hàm. | **Rất Cao** |
| **§13** | `saga: ... compensate: ... end` | Chưa có | Cơ chế ghi nhận hành động hoàn tác vào Compensation Rollback Stack khi có lỗi phát sinh trong giao dịch. | **Cao** |

---

### 2.5. Hàm, Biểu Thức, UFCS & Lambda (§14, §15, §16, §17)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§14.1** | Đa dạng cú pháp hàm:<br>`func f(a: int):`, block params | Đã có | Đã có | **Hoàn thành** |
| **§14.2** | Named Arguments:<br>`f(name: "A", age: 30)` | Đã hỗ trợ trong constructor entity | Mở rộng cho mọi hàm thông thường: tra cứu vị trí tham số theo tên lúc biên dịch. | **Cao** |
| **§14.3** | Multiple Return Values (Tuples):<br>`out a, b, c` | Chỉ trả về 1 giá trị (`X0`) | Hỗ trợ ABI trả về nhiều thanh ghi (`X0, X1, X2...`) hoặc thông qua con trỏ cấu trúc ẩn (Hidden Return Pointer). | **Cao** |
| **§15** | Closures / Lambda Expressions:<br>`\|x, y\| => expr` | Chưa có | Cấp phát Closure Environment Frame lưu các biến được bắt (captured variables), con trỏ hàm ẩn. | **Cao** |
| **§16** | UFCS (Uniform Function Call):<br>`x.func(y)` $\leftrightarrow$ `func(x, y)` | Chưa có (mới chỉ đọc/ghi field struct) | Bộ định tuyến UFCS: nếu `x.f` không phải field của struct, tự động chuyển đổi thành lời gọi `f(x, y)`. | **Rất Cao** |
| **§17** | `async func` & `await` | Chưa có | Biến đổi máy trạng thái (Coroutine State Machine Transform) và runtime task executor. | **Trung bình** |

---

### 2.6. Xử Lý Lỗi, Siêu Lập Trình & Đồng Thời (§18, §20, §23)

| Mục Spec | Cú pháp / Tính năng | Hiện trạng trong Stage-1 | Cần xây dựng để đạt Full Compiler | Mức độ ưu tiên |
|---|---|---|---|:---:|
| **§18** | `Result[T, E]`, `throw err;`, `revert;`, Nil-safe (`?.`, `?:`) | Hiện dùng `exit_prog(1)` | Hệ thống trả về `Result` tối ưu zero-cost trên thanh ghi (`X19`), toán tử điều hướng an toàn (`?.`). | **Rất Cao** |
| **§20** | `precomp` / `comptime` (CTFE) | Chưa có | Bộ thông dịch biểu thức lúc biên dịch (Compile-Time Function Evaluator), đưa kết quả trực tiếp thành hằng số mã máy. | **Cao** |
| **§23.1** | `port name: Type` (Actor Ports) | Chưa có | Khởi tạo hàng đợi MPSC (Multi-Producer Single-Consumer) không khóa trong bộ nhớ dùng chung. | **Cao** |
| **§23.2** | `spawn task(...)`, `atomic`, `spinlock` | Chưa có | Sinh lệnh khóa bộ nhớ ARM64: `LDAXR`, `STLXR`, `DMB ISHLD`. | **Cao** |

---

## 3. Kiến Trúc Compiler 4 Tầng IR Chuẩn Hóa

Để giải quyết triệt để toàn bộ khối lượng tính năng trên mà không làm phình to hoặc gây lỗi hồi quy trong mã nguồn compiler, hệ thống sẽ được tái cấu trúc thành **chuỗi 4 tầng trung gian (Compiler IR Pipeline)** theo đúng [ARCHITECTURE.md](ARCHITECTURE.md):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Frontend: Lexer & AST Parser (Cây Cú Pháp Trừu Tượng)                   │
│    - Phân tích cú pháp đầy đủ: entity, enum, mold, case, defer, saga, UFCS  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. HIR (High-Level Intermediate Representation)                             │
│    - Module Graph & Symbol Resolution (Xử lý include / import / export)     │
│    - Strict Static Type Checker (Kiểm tra kiểu dữ liệu toàn diện)           │
│    - Static Borrow Checker & Ownership State Tracker (Quản lý bộ nhớ)       │
│    - Desugaring: defer -> cleanup blocks, saga -> rollback, UFCS -> calls   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. MIR (Mid-Level Intermediate Representation)                              │
│    - SSA (Static Single Assignment) Form & Control Flow Graph (CFG)         │
│    - Tối ưu hóa: Dead Code Elimination, Constant Folding, Sub-Arena Reset   │
│    - Pattern Matching Decision Tree Lowering (Hạ mức khối case..of)         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. LIR & Backend (Low-Level IR & Emitter)                                   │
│    - Linear Scan Register Allocation (Thanh ghi X0..X28, D0..D31)           │
│    - Calling Convention AAPCS64 & Frame Layout (4KB stack frame)            │
│    - Mach-O 64-bit (macOS) & ELF 64-bit (Linux) Direct Object/Exec Emitter  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Lộ Trình Triển Khai Chi Tiết (Phased Execution Plan)

### Giai đoạn 1: Hệ Thống Kiểu Dữ Liệu Tĩnh & Enum / Tagged Union
- **Mục tiêu:** Xây dựng bộ Type Checker hoàn chỉnh cho Primitive types, String native struct, Enum tagged union và Type alias.
- **Nội dung thực hiện:**
  1. Mở rộng Symbol Table lưu thông tin kiểu (`TypeKind: INT, FLOAT, BOOL, STR, PTR, STRUCT, ENUM`).
  2. Bố cục bộ nhớ cho `enum` (`tag: u32` + `payload: T`), làm tiền đề cho `Option[T]` và `Result[T, E]`.
  3. Hiện thực `type Alias = Target;` và cấu trúc `String` native.
- **Tiêu chuẩn nghiệm thu:** Test suite cho kiểm tra kiểu, phát hiện lỗi gán sai kiểu lúc biên dịch.

### Giai đoạn 2: Cấu Trúc Điều Khiển Nâng Cao & Desugaring
- **Mục tiêu:** Hiện thực `case..of` (Pattern Matching), `defer`, `break`, `skip`, và UFCS.
- **Nội dung thực hiện:**
  1. Bộ phân tích và sinh mã cho `case expr of ... end` (nhảy bảng dispatch hoặc so sánh chuỗi/enum).
  2. Stack lưu trữ các biểu thức `defer` để chèn tự động trước mọi điểm thoát hàm.
  3. Bộ phân giải UFCS (`x.method(y)` $\rightarrow$ `method(x, y)`).
- **Tiêu chuẩn nghiệm thu:** Các bài test phức tạp về pattern matching và đảm bảo `defer` luôn giải phóng tài nguyên.

### Giai đoạn 3: Module Graph & Export / Import Liên Tệp
- **Mục tiêu:** Hệ thống module đa tệp độc lập, liên kết mã nguồn `stdlib/vir`.
- **Nội dung thực hiện:**
  1. Trình duyệt đồ thị phụ thuộc module (DAG), kiểm tra vòng lặp phụ thuộc.
  2. Bảng Export/Import Symbol Resolver.
  3. Biên dịch và liên kết nhiều module thành một file thực thi Mach-O duy nhất.
- **Tiêu chuẩn nghiệm thu:** Xây dựng và liên kết thành công các module của `stdlib/vir` mà không cần nối file vật lý.

### Giai đoạn 4: Borrow Checker & Các Tính Năng Nâng Cao
- **Mục tiêu:** Hoàn thiện mô hình an toàn bộ nhớ tĩnh và đồng thời.
- **Nội dung thực hiện:**
  1. Borrow Checker tĩnh (`&` và `&mut`).
  2. Khối cách ly `isolate` và giao dịch `saga..compensate`.
  3. Hỗ trợ kênh truyền thông điệp `port` và lệnh nguyên tử `atomic`.
- **Tiêu chuẩn nghiệm thu:** Vượt qua toàn bộ bộ kiểm thử an toàn mượn (`test_borrow_valid.vri`, `test_borrow_err_*.vri`) ở cấp độ native compiler.

---

## 5. Kết Luận

Báo cáo này xác lập ranh giới rõ ràng: **Giai đoạn bootstrap subset đã kết thúc, ngôn ngữ Vir bước vào giai đoạn hoàn thiện Full Compiler theo chuẩn v2.0.**

Toàn bộ quá trình phát triển tiếp theo sẽ tuân thủ nghiêm ngặt lộ trình trên, đảm bảo mỗi tính năng được tích hợp đều đạt chất lượng cao nhất, có kiểm thử hồi quy đầy đủ và bảo toàn khả năng tự nhân bản (Self-Hosting) 100%.
