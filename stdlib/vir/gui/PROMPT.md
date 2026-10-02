# Vir GUI Standard Library — Design Prompt

> Prompt gốc yêu cầu thiết kế thư viện GUI chuẩn cho Vir Programming Language.
> Lưu tại: `stdlib/vir/gui/PROMPT.md`
> Ngày: 2026-09-17

---

Hãy khởi tạo và triển khai một **thư viện GUI chuẩn cho Vir Programming Language**.

Mục tiêu là xây dựng nền tảng GUI chính thức của Vir theo hướng:

* native
* typed
* declarative
* gọn
* dễ đọc
* cú pháp có cảm giác quen thuộc như CSS
* không phụ thuộc HTML
* không phụ thuộc JavaScript
* không biến GUI thành feature hardcode của compiler
* có khả năng mở rộng thành framework GUI production-quality hoàn chỉnh

Đây không phải demo, MVP hay proof-of-concept.

Không được chỉ tạo vài widget mẫu rồi dừng.

Phải thiết kế architecture đủ sâu để sau này mở rộng toàn bộ desktop GUI mà không cần phá public API.

---

# 1. NGUYÊN TẮC QUAN TRỌNG NHẤT

GUI là **standard library**, không phải syntax đặc biệt hardcode trong compiler.

Toàn bộ implementation phải nằm trong thư mục thư viện chuẩn của Vir.

Ví dụ:

```text
stdlib/
    gui/
```

hoặc đúng đường dẫn stdlib hiện tại của repository.

Trước khi tạo file, hãy kiểm tra cấu trúc stdlib thực tế của Vir và đặt thư viện vào đúng convention hiện tại.

Không tự ý tạo một stdlib layout mới nếu repository đã có convention.

---

# 2. KHÔNG HARDCODE GUI VÀO COMPILER

Tuyệt đối không:

* thêm `button` vào parser
* thêm `window` vào parser
* thêm `text` vào parser
* thêm `width`, `height`, `padding`, `background` vào parser
* thêm danh sách CSS property vào compiler
* thêm AST node riêng cho từng GUI component
* thêm semantic pass riêng cho button/text/window
* thêm hardcoded widget registry vào compiler
* thêm GUI-specific lowering vào compiler
* khiến compiler phụ thuộc `std.gui`

Compiler không được biết:

```text
button
text
image
window
row
column
width
height
background
color
padding
margin
radius
```

là GUI.

Những khái niệm này thuộc thư viện.

---

# 3. SYNTAX GUI PHẢI ĐƯỢC ĐỊNH NGHĨA TỪ PHÍA THƯ VIỆN

Mục tiêu public syntax:

```vir
ui:
    .button("Save"):
        width: 120px; height: 40px
        background: #2563eb
        color: #fff
        radius: 8px

    .text("Ready"): size: 18px; weight: 600
end
```

Nhưng không được implement syntax trên bằng cách viết parser GUI riêng trong compiler.

Hãy nghiên cứu các khả năng cú pháp/DSL hiện có của Vir và xây dựng GUI DSL bằng primitive tổng quát hiện có của ngôn ngữ.

Nếu Vir hiện tại chưa thể biểu diễn chính xác cú pháp trên thì:

1. không được giả vờ syntax đã tồn tại
2. không được viết code Vir không compile
3. hãy xác định chính xác primitive tổng quát còn thiếu
4. tách compiler proposal đó khỏi implementation GUI
5. compiler proposal phải là feature tổng quát, không phải GUI-specific

Ví dụ:

Không đề xuất:

```text
add GUI style syntax to parser
```

Mà nếu thực sự cần, phải nghĩ theo hướng tổng quát như:

```text
declarative library block
custom literal
typed unit literal
library-defined property syntax
context member declaration
```

Feature compiler phải dùng được cho nhiều DSL khác, không riêng GUI.

---

# 4. THƯ VIỆN PHẢI CHỨA DSL IMPLEMENTATION

Syntax/domain mapping phải nằm trong thư viện.

Ví dụ concept:

```text
ui
.button
.text
.width
.background
```

phải resolve thông qua symbol/type/context của `std.gui`.

Không import GUI thì các symbol GUI phải không tồn tại.

Ví dụ:

```vir
import std.gui
```

mới cho phép sử dụng GUI API.

Không biến `ui` thành reserved keyword nếu không thật sự cần.

Ưu tiên `ui` là symbol/library construct được cung cấp bởi `std.gui`.

---

# 5. PUBLIC SYNTAX

Target syntax chính thức:

```vir
ui:
    .window("Vir"):
        width: 900px
        height: 600px
        background: #111

    .text("Hello Vir"):
        size: 28px
        weight: 700
        color: #fff

    .button("Continue"):
        width: 160px; height: 44px
        background: #2563eb
        color: #fff; radius: 8px
end
```

Chỉ `ui:` mở block lớn.

Chỉ `end` đóng `ui:`.

Style của element **không dùng `end` riêng**.

Style của element kết thúc khi:

* gặp element kế tiếp
* gặp kết thúc `ui`
* hoặc context parser/library xác định declaration đã kết thúc

---

# 6. ELEMENT SYNTAX

Element bắt đầu bằng dấu `.`.

Ví dụ:

```vir
.button("Save")
.text("Hello")
.image(source)
.row()
.column()
```

Dấu `.` phải tạo tín hiệu thị giác rõ rằng đây là element thuộc UI context.

Phân biệt với function call Vir thông thường:

```vir
save()
print("hello")

.button("Save")
.text("hello")
```

Không được biến `.button` thành keyword.

Nó phải resolve từ UI context/library.

---

# 7. STYLE SYNTAX

Style property dùng:

```vir
property: value
```

Ví dụ:

```vir
width: 160px
height: 44px
background: #111
color: #fff
radius: 8px
```

Không dùng:

```vir
width(160)
setWidth(160)
setBackgroundColor(...)
```

Style phải declarative.

---

# 8. CHO PHÉP MULTILINE, INLINE VÀ MIX

Ba dạng này đều phải hợp lệ:

```vir
.button():
    width: 16px
    height: 16px
```

```vir
.button(): width: 16px; height: 16px
```

```vir
.button():
    width: 16px; height: 16px
    background: #111; color: #fff
    radius: 8px
```

Cho phép mix tự do.

Rule mong muốn:

```text
newline = kết thúc declaration hiện tại
;       = phân cách nhiều declaration trên cùng dòng
```

Dấu `;` cuối dòng không bắt buộc.

---

# 9. NAMING STYLE

Tên API phải:

* ngắn
* dễ hiểu
* quen thuộc
* không dài kiểu Java
* tránh prefix `set`
* tránh prefix `get`
* không dùng snake_case
* không dùng tên dư thừa context

Tốt:

```text
width
height
size
weight
color
background
border
radius
padding
margin
gap
align
justify
wrap
grow
shrink
opacity
shadow
overflow
cursor
position
top
right
bottom
left
```

Không tốt:

```text
setElementWidth
setBackgroundColor
getCurrentFontWeight
setHorizontalAlignment
```

---

# 10. PROPERTY PHẢI CÓ TYPE

Style không được là dictionary string -> any.

Property phải typed.

Ví dụ concept:

```text
width      -> length
height     -> length
opacity    -> float
background -> paint
color      -> color
weight     -> font weight
align      -> alignment
```

Compiler/type checker phải có khả năng bắt lỗi type thông qua API/library bình thường.

---

# 11–64. [Xem toàn bộ prompt trong git history]

Các mục chi tiết về:
- Length system (px/percent/em/rem/auto)
- Color system (#rgb, #rrggbb, rgb(), hsl())
- Core architecture modules
- GUI tree / parent-child
- Layout engine (row/column/flex/grid)
- Box model
- Typography
- Text engine (UTF/shaping/bidi)
- Event system + propagation
- State (hover/focus/active/disabled)
- Widget catalog (20+ widgets)
- Container types
- Window system
- Application lifecycle
- Platform backends
- Renderer pipeline
- Graphics foundation
- GPU acceleration path
- Accessibility
- Input abstraction
- Clipboard/DnD/Cursor
- Image system
- Custom components
- Theme system
- Responsive design
- Animation
- Transform/Shadow/Border
- Spacing shorthand
- Style resolution pipeline
- Performance requirements
- Memory ownership
- Threading model
- Error handling
- Test requirements
- Compiler change policy

---

# DEFINITION OF DONE

```text
stdlib gui module
typed UI tree
typed style system
typed length
typed color
box model
row/column layout
window
text
button
event system
renderer abstraction
platform abstraction
native window backend
native input
working render loop
working click event
mixed inline/multiline style
tests
docs
example app
```
