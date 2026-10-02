# Vir GUI — Architecture Design
## `stdlib/vir/gui/`

> **Version:** 1.0
> **Spec target:** Vir v2.0
> **Date:** 2026-09-17
> **Prompt:** [`PROMPT.md`](PROMPT.md)

---

## 1. Triết lý thiết kế

`std.gui` là **thư viện chuẩn**, không phải syntax đặc biệt trong compiler.

Compiler Vir không biết `button`, `window`, `width`, `background`, hay bất kỳ
concept GUI nào. Tất cả đều là symbol và type thuộc `stdlib/vir/gui/`.

Nếu không `include gui`, không có symbol GUI nào tồn tại trong scope.

**Bốn nguyên tắc không vi phạm:**

```
1. Không hardcode GUI vào parser/compiler
2. Public API không expose backend platform (AppKit/Win32/Wayland)
3. Không wrap framework khác làm public model (không là GTK wrapper)
4. Không dùng WebView làm GUI core
```

---

## 2. Trạng thái hiện tại (Codebase Audit)

### Đã tồn tại (`stdlib/vir/gui/`):

| File | Nội dung | Đánh giá |
|------|---------|---------|
| `gui.vri` | Widget handle, extern bridge, Color, Rect, Font, Event, high-level API | Foundation tốt, cần tổ chức lại |
| `layout.vri` | Align, Insets, layout_distribute, layout_center | Skeleton, cần mở rộng |

### Gap analysis:

| Thiếu | Mức độ |
|-------|--------|
| Typed length (px/percent/em/auto) | Critical |
| Typed paint/gradient | Critical |
| UI tree / node model | Critical |
| Layout engine (flex/grid) | Critical |
| Style resolution pipeline | Critical |
| Box model (content/padding/border/margin) | Critical |
| Renderer abstraction | Critical |
| Platform abstraction layer | Critical |
| Declarative DSL syntax | Critical (language primitive gap) |
| Event propagation (bubble/capture) | High |
| State machine (hover/focus/active) | High |
| Animation system | Medium |
| Theme system | Medium |
| Accessibility layer | Medium |
| Custom component API | High |
| Text engine backend | High |

### Syntax gap (compiler primitive thiếu):

Target syntax mong muốn:
```vir
ui:
    .button("Save"):
        width: 120px
        background: #2563eb
end
```

**Hiện tại Vir không thể biểu diễn syntax này trực tiếp** vì:
- `120px` — không có typed unit literal (`px` không phải built-in)
- `#2563eb` — không có hex color literal
- `.button()` trước context — UFCS đòi hỏi receiver object rõ ràng

**API tương đương hoạt động với Vir v2.0 hiện tại:**
```vir
include gui

func main:
    app = gui.app("My App")
    win = gui.window(app, "Vir GUI", 640, 420)
    gui.windowBg(win, color.hex("#181818"))
    btn = gui.button(win, "Continue", rect(240, 180, 160, 44))
    gui.style(btn, style.create()
        .bg(color.hex("#2563eb"))
        .fg(color.hex("#ffffff"))
        .radius(8))
    gui.onClick(btn, func: print("clicked") end.)
    gui.run(app)
end.
```

**Compiler primitive proposals** (tổng quát, không GUI-specific):
- `TypedUnitLiteral` — `16px`, `10ms`, `90deg`, `5kb` (general unit literals)
- `HexLiteral` — `#2563eb` resolves to library type via `fromHex()` hook
- `ContextMemberSyntax` — `.button()` dispatches to current context object

---

## 3. Cây thư mục đích

```
stdlib/vir/gui/
│
│   PROMPT.md              — Prompt gốc
│   ARCHITECTURE.md        — Tài liệu này
│
├── gui.vri                — Entry point: include gui → mọi thứ
├── app.vri                — App lifecycle (App, run, quit)
├── window.vri             — Window (title, size, flags, events)
├── node.vri               — Node: base UI tree element
├── element.vri            — Element: typed wrapper around Node
│
├── style/
│   ├── style.vri          — Style: typed property bag
│   ├── length.vri         — Length: px | percent | em | rem | auto | fr
│   ├── color.vri          — Color: rgb/rgba/hsl/hsla/hex + named
│   ├── paint.vri          — Paint: solid | gradient | pattern
│   ├── spacing.vri        — EdgeInsets: top/right/bottom/left shorthand
│   ├── border.vri         — Border: width/color/style/radius (per-corner)
│   ├── shadow.vri         — Shadow: x/y/blur/spread/color, multi-shadow
│   ├── transform.vri      — Transform: translate/scale/rotate/origin
│   └── typography.vri     — Typography: font/size/weight/lineHeight/align
│
├── layout/
│   ├── layout.vri         — LayoutResult, LayoutConstraint, LayoutEngine
│   ├── box.vri            — BoxModel: content/padding/border/margin
│   ├── flex.vri           — Flex layout algorithm
│   ├── grid.vri           — Grid layout algorithm
│   └── stack.vri          — Stack (z-axis), absolute positioning
│
├── widget/
│   ├── text.vri           — Text: label, rich text
│   ├── button.vri         — Button: push, icon, toggle
│   ├── image.vri          — Image: load/decode/fit/crop
│   ├── input.vri          — TextInput: single line
│   ├── textarea.vri       — TextArea: multi line
│   ├── checkbox.vri       — Checkbox
│   ├── radio.vri          — RadioButton / RadioGroup
│   ├── switch.vri         — Switch (toggle)
│   ├── slider.vri         — Slider: horizontal/vertical
│   ├── progress.vri       — ProgressBar: determinate/indeterminate
│   ├── select.vri         — Dropdown / ComboBox
│   ├── list.vri           — ListView: virtual, recycled
│   ├── scroll.vri         — ScrollView: horizontal/vertical/both
│   ├── canvas.vri         — Canvas: immediate-mode drawing
│   ├── separator.vri      — Separator / Divider
│   └── spacer.vri         — Spacer: fills available space
│
├── container/
│   ├── row.vri            — Row: horizontal flex container
│   ├── column.vri         — Column: vertical flex container
│   ├── stack.vri          — ZStack: overlay container
│   ├── grid.vri           — Grid: 2D layout container
│   ├── scroll.vri         — ScrollContainer
│   └── panel.vri          — Panel: generic container with style
│
├── event/
│   ├── event.vri          — Event: base type, EventType enum
│   ├── mouse.vri          — MouseEvent: pos/button/delta/modifiers
│   ├── keyboard.vri       — KeyEvent: keyCode/char/modifiers
│   ├── focus.vri          — FocusEvent: focus/blur, tab order
│   ├── scroll.vri         — ScrollEvent: delta x/y
│   └── gesture.vri        — GestureEvent: tap/pinch/swipe (touch)
│
├── state/
│   ├── state.vri          — WidgetState: normal/hover/active/focus/disabled
│   └── signal.vri         — Signal<T>: reactive state primitive
│
├── render/
│   ├── renderer.vri       — Renderer interface (abstract)
│   ├── surface.vri        — Surface: draw target abstraction
│   ├── paint.vri          — Paint command types
│   ├── path.vri           — Path2D: moveTo/lineTo/arc/bezier
│   └── layer.vri          — Layer: compositing layer
│
├── graphics/
│   ├── point.vri          — Point: x, y (float)
│   ├── size.vri           — Size: width, height (float)
│   ├── rect.vri           — Rect: origin + size (float)
│   ├── color.vri          — (alias to style/color.vri)
│   ├── image.vri          — Image data + metadata
│   └── glyph.vri          — Glyph cache interface
│
├── text/
│   ├── engine.vri         — TextEngine interface (shaping backend)
│   ├── paragraph.vri      — Paragraph: shaped + laid out text
│   ├── span.vri           — Span: styled text run
│   └── measure.vri        — TextMeasure: width/height cache
│
├── animation/
│   ├── animation.vri      — Animation: duration/delay/easing/repeat
│   ├── easing.vri         — Easing functions: linear/ease/spring
│   └── timeline.vri       — Timeline: keyframe-based
│
├── theme/
│   ├── theme.vri          — Theme: token-based (light/dark/custom)
│   └── tokens.vri         — ColorToken, SpacingToken, RadiusToken
│
├── platform/
│   ├── platform.vri       — Platform interface (abstract)
│   ├── macos/
│   │   ├── backend.vri    — macOS AppKit/Cocoa backend
│   │   ├── window.vri     — NSWindow wrapper
│   │   ├── renderer.vri   — Core Graphics renderer
│   │   └── text.vri       — Core Text shaping backend
│   ├── linux/
│   │   └── backend.vri    — Wayland/X11 backend (planned)
│   └── windows/
│       └── backend.vri    — Win32/Direct2D backend (planned)
│
├── accessibility/
│   ├── a11y.vri           — Accessibility tree node
│   └── roles.vri          — ARIA-equivalent roles
│
└── tests/
    ├── style_test.vri
    ├── layout_test.vri
    ├── color_test.vri
    ├── length_test.vri
    ├── event_test.vri
    └── tree_test.vri
```

---

## 4. Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User Application                                               │
│  include gui  →  gui.app() · gui.window() · gui.button() ...   │
├─────────────────────────────────────────────────────────────────┤
│  Widget Layer                                                   │
│  text · button · image · input · checkbox · slider · canvas ... │
├───────────────┬─────────────────────────────────────────────────┤
│  Container    │  Style System                                   │
│  row · col    │  length · color · paint · spacing · typography  │
│  grid · stack │  border · shadow · transform                    │
├───────────────┴─────────────────────────────────────────────────┤
│  Core Systems                                                   │
│  UI Tree  │  Layout Engine  │  Event System  │  State Machine   │
│  (node)   │  (flex/grid/abs)│  (mouse/key)   │  (hover/focus)   │
├─────────────────────────────────────────────────────────────────┤
│  Render Pipeline                                                │
│  style resolution → layout → paint list → renderer → surface   │
├─────────────────────────────────────────────────────────────────┤
│  Platform Abstraction                                           │
│  Platform interface → [macOS | Linux | Windows]                │
├─────────────────────────────────────────────────────────────────┤
│  Vir Runtime                                                    │
│  rt/syscall · rt/ffi · math · mem · core/result                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Core Types

### 5.1 Node (UI Tree)

Mọi element trong UI là một `Node`. Node là đơn vị cơ bản của UI tree.

```
Entity Node
  id       : i64          (unique, monotonic)
  kind     : NodeKind     (enum: window/text/button/row/col/...)
  style    : Style        (computed style)
  children : [Node]       (child nodes, owned)
  state    : WidgetState  (normal/hover/active/focus/disabled)
  handlers : EventTable   (click/keyDown/... callbacks)
  layout   : LayoutResult (computed: x/y/width/height)
  data     : NodeData     (kind-specific payload: text content, image src, ...)
```

Không dùng `dict<string, any>` cho style hay event. Tất cả typed.

---

### 5.2 Style

`Style` là typed property bag. Không là `Map(String, Any)`.

```
Entity Style
  # Box model
  width       : Option(Length)
  height      : Option(Length)
  minWidth    : Option(Length)
  maxWidth    : Option(Length)
  minHeight   : Option(Length)
  maxHeight   : Option(Length)

  # Spacing
  padding     : EdgeInsets
  margin      : EdgeInsets

  # Background
  background  : Option(Paint)

  # Border
  border      : Option(Border)
  radius      : Option(CornerRadius)

  # Typography
  font        : Option(FontSpec)
  color       : Option(Color)
  size        : Option(Length)       (font size)
  weight      : Option(FontWeight)
  lineHeight  : Option(float)
  align       : Option(TextAlign)

  # Layout
  display     : Display      (block/flex/grid/none)
  direction   : Direction    (row/column)
  gap         : Option(Length)
  alignItems  : Option(Alignment)
  justifyContent: Option(Justify)
  grow        : float
  shrink      : float
  basis       : Option(Length)
  wrap        : bool

  # Position
  position    : Position     (static/relative/absolute/fixed)
  top         : Option(Length)
  right       : Option(Length)
  bottom      : Option(Length)
  left        : Option(Length)
  zIndex      : Option(i32)

  # Visual
  opacity     : float        (0.0..1.0)
  overflow    : Overflow     (visible/hidden/scroll/auto)
  cursor      : Cursor

  # Effects
  shadow      : [Shadow]     (multi-shadow)
  transform   : [Transform]

  # State overrides
  hoverStyle  : Option(Style)
  activeStyle : Option(Style)
  focusStyle  : Option(Style)
  disabledStyle: Option(Style)
```

---

### 5.3 Length

```
enum Length
  px(value: float)             # pixels
  percent(value: float)        # percentage of parent
  em(value: float)             # relative to font size
  rem(value: float)            # relative to root font size
  auto                         # auto-sized
  fr(value: float)             # fraction unit (grid)
  minContent                   # shrink to content
  maxContent                   # grow to content
  fitContent(max: Length)      # fit-content(max)
  calc(expr: CalcExpr)         # calculated (add/sub/min/max)
```

**API hiện tại (Vir v2.0 compatible, không cần unit literal):**

```vir
length.px(120)
length.pct(50)          # 50%
length.em(1.5)
length.auto
```

**API mục tiêu (cần TypedUnitLiteral compiler feature):**

```vir
120px
50pct
1.5em
```

Compiler proposal (tổng quát, không GUI-specific):
- `TypedUnitLiteral`: `<number><suffix>` → gọi `fromUnit(suffix, value)` hook
- Dùng được cho: `16px`, `10ms`, `90deg`, `5kb`, `100hz`

---

### 5.4 Color

```
Entity Color
  r : u8   (0..255)
  g : u8
  b : u8
  a : u8   (0=transparent, 255=opaque)
```

**Constructors:**

```vir
color.rgb(34, 197, 94)
color.rgba(34, 197, 94, 200)
color.hex("#2563eb")       # parses #rgb #rgba #rrggbb #rrggbbaa
color.hsl(210, 0.8, 0.5)
color.hsla(210, 0.8, 0.5, 1.0)
color.named("transparent")
color.named("white")
```

**Constants:**

```vir
color.black   color.white   color.transparent
color.red     color.green   color.blue
```

**Compiler proposal (tổng quát):**
- `HexLiteral`: `#rrggbb` → library type via `Color.fromHex()` hook
- Dùng được cho: color literals, SHA hashes, binary literals

---

### 5.5 Paint

```
enum Paint
  solid(color: Color)
  linearGradient(from: Point, to: Point, stops: [GradientStop])
  radialGradient(center: Point, radius: float, stops: [GradientStop])
  image(src: ImageRef, fit: ImageFit)
  none
```

---

### 5.6 CornerRadius

```
Entity CornerRadius
  topLeft     : Length
  topRight    : Length
  bottomRight : Length
  bottomLeft  : Length
```

**Constructors:**

```vir
radius.all(8)            # uniform
radius.top(8)            # top corners only
radius.bottom(8)
radius.left(8)
radius.right(8)
radius.corners(8, 0, 8, 0)  # topLeft, topRight, bottomRight, bottomLeft
```

---

### 5.7 EdgeInsets (Spacing)

```
Entity EdgeInsets
  top    : Length
  right  : Length
  bottom : Length
  left   : Length
```

**Shorthand constructors (CSS semantics):**

```vir
insets.all(16)            # 16 16 16 16
insets.xy(16, 8)          # top=8, right=16, bottom=8, left=16
insets.trbl(8, 16, 12, 16)  # top right bottom left
```

---

### 5.8 Typography

```
Entity FontSpec
  family    : string       ("Inter", "system-ui", ...)
  size      : Length       (font size, typically px)
  weight    : FontWeight   (100..900, w100..w900, thin/light/regular/bold/black)
  style     : FontStyle    (normal | italic | oblique)
  lineHeight: float        (multiplier, default 1.4)
  letterSpacing: Length
```

```
enum FontWeight
  w100 | w200 | w300 | w400 | w500 | w600 | w700 | w800 | w900
  thin | extraLight | light | regular | medium | semiBold | bold | extraBold | black
```

---

## 6. Layout System

### 6.1 Box Model

```
┌──────────────────────────────────────┐
│             margin                   │
│  ┌────────────────────────────────┐  │
│  │          border                │  │
│  │  ┌──────────────────────────┐  │  │
│  │  │        padding           │  │  │
│  │  │  ┌────────────────────┐  │  │  │
│  │  │  │      content       │  │  │  │
│  │  │  └────────────────────┘  │  │  │
│  │  └──────────────────────────┘  │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

`width`/`height` mặc định = content box (như `box-sizing: content-box`).  
Có thể chuyển sang `border-box` qua `style.boxSizing`.

### 6.2 Layout Algorithms

**Flex Layout** (dùng cho Row/Column):
```
1. Collect children và flex properties (grow/shrink/basis)
2. Compute base sizes từ content
3. Distribute free space theo grow/shrink
4. Apply alignment (alignItems/justifyContent)
5. Apply gap
6. Handle wrap nếu enabled
```

**Grid Layout** (dùng cho Grid):
```
1. Parse template (rows/columns, fr units)
2. Place items theo grid-area / auto-placement
3. Resolve fr units sau khi biết available space
4. Apply gap
5. Align items trong cells
```

**Absolute Positioning**:
```
Không tham gia flow
top/right/bottom/left tương đối với nearest positioned ancestor
```

### 6.3 Layout Properties

| Property | Kiểu | Mô tả |
|----------|------|-------|
| `display` | Display | block/flex/grid/none |
| `direction` | Direction | row/column |
| `gap` | Length | khoảng cách giữa children |
| `alignItems` | Alignment | stretch/start/center/end |
| `justifyContent` | Justify | start/center/end/spaceBetween/spaceAround/spaceEvenly |
| `grow` | float | flex grow factor |
| `shrink` | float | flex shrink factor |
| `basis` | Length | flex basis |
| `wrap` | bool | wrap khi overflow |
| `overflow` | Overflow | visible/hidden/scroll/auto |

---

## 7. Event System

### 7.1 Event Types

```
enum EventKind
  # Mouse
  click | doubleClick | press | release | move | enter | leave | scroll
  # Keyboard
  keyDown | keyUp | keyPress
  # Focus
  focus | blur
  # Value
  change | input | submit
  # Window
  resize | close | open | move
  # Drag
  dragStart | drag | dragEnd | dragEnter | dragLeave | dragOver | drop
  # Touch/Gesture (future)
  tap | doubleTap | pinch | swipe
```

### 7.2 Event Propagation

```
Capture phase (top → target)
    ↓
Target phase (at target)
    ↓
Bubble phase (target → top)
```

```
event.stop()    # stop propagation
event.prevent() # prevent default behavior
```

### 7.3 Event Handler API

```vir
# Handler registration
node.on(EventKind.click, func(e: MouseEvent):
    print("clicked at $e.x, $e.y")
end.)

# UFCS style
btn.onClick(handler)
input.onKeyDown(handler)
win.onClose(handler)
```

---

## 8. State Machine

```
enum WidgetState
  normal    # default
  hover     # cursor over element
  active    # being pressed/activated
  focus     # keyboard focused
  disabled  # interaction blocked
  checked   # toggle state (checkbox/switch)
  selected  # selection state (list item)
  error     # validation failed
```

**Style state override:**

```vir
style.create()
    .bg(color.hex("#2563eb"))
    .onHover(.bg(color.hex("#1d4ed8")))
    .onActive(.bg(color.hex("#1e40af")))
    .onDisabled(.opacity(0.5))
```

---

## 9. Render Pipeline

```
Node tree (mutable during update)
    │
    ▼
Style resolution
    (defaults → theme → component → state → inline)
    │
    ▼
Layout pass
    (constraints propagate down, sizes propagate up)
    │
    ▼
Paint list generation
    (sorted by z-index, clipping applied)
    │
    ▼
Renderer
    (PaintCommand list → draw calls)
    │
    ▼
Platform surface / GPU backend
```

**Optimization:**

- Dirty tracking: chỉ relayout node bị thay đổi và children của nó
- Paint cache: layer unchanged không repaint
- Glyph cache: rendered glyphs cached theo font+size+color
- Image cache: decoded images cached theo src+size

### 9.1 PaintCommand

```
enum PaintCommand
  fillRect(rect: Rect, paint: Paint, radius: CornerRadius)
  strokeRect(rect: Rect, stroke: Stroke)
  drawText(text: string, pos: Point, font: FontSpec, color: Color)
  drawImage(image: ImageRef, dest: Rect, fit: ImageFit)
  drawPath(path: Path2D, paint: Paint)
  pushClip(rect: Rect)
  popClip
  pushTransform(transform: Transform)
  popTransform
  pushLayer(opacity: float)
  popLayer
```

---

## 10. Platform Abstraction

```
Interface Platform
  createWindow(spec: WindowSpec)  → WindowHandle
  destroyWindow(handle)
  showWindow(handle)
  hideWindow(handle)
  setTitle(handle, title)
  setSize(handle, w, h)
  getSize(handle)               → Size
  runEventLoop(callback)
  stopEventLoop
  pollEvent                     → Option(RawEvent)
  createRenderer(window)        → Renderer
  systemFont                    → FontSpec
  systemScaleFactor             → float
  clipboard                     → Clipboard
  cursor                        → CursorManager
```

**Backends:**

| Platform | Backend | Status |
|----------|---------|--------|
| macOS ARM64 | AppKit/Cocoa via FFI | First target |
| macOS x86_64 | AppKit/Cocoa via FFI | Planned |
| Linux (Wayland) | libwayland + EGL | Planned |
| Linux (X11) | Xlib/XCB | Planned |
| Windows | Win32 + Direct2D | Planned |

Backend không được leak vào public API. User code không import `gui.platform.macos`.

---

## 11. Application Lifecycle

```
app.create(name)
    │
    ▼
app.onStart(handler)
    │
    ▼
window.create(app, spec)
    │
    ▼
gui.run(app)   ←─── platform event loop bắt đầu
    │
    ├── event arrives
    │       │
    │       ▼
    │   dispatch to UI tree
    │       │
    │       ▼
    │   update state
    │       │
    │       ▼
    │   relayout (dirty nodes)
    │       │
    │       ▼
    │   repaint (dirty regions)
    │       │
    │       ▼
    │   present to surface
    │
    └── window.onClose → app.quit
    │
    ▼
app.onStop(handler)
    │
    ▼
cleanup (resources freed)
```

---

## 12. DSL Syntax Analysis

### 12.1 Target syntax

```vir
ui:
    .window("Vir GUI"):
        width: 640px; height: 420px
        background: #181818

    .text("Hello Vir"):
        size: 28px; weight: 700
        color: #fff

    .button("Continue"):
        width: 160px; height: 44px
        background: #2563eb; color: #fff
        radius: 8px
end
```

### 12.2 Syntax feasibility với Vir v2.0

| Construct | Feasible? | Notes |
|-----------|-----------|-------|
| `ui:` block | YES | `ui` là library entity với method `:` opener |
| `.window()` | PARTIAL | `.` prefix UFCS trên context object — cần `ui` là receiver |
| `width: 640px` | NO | `px` suffix không phải built-in unit literal |
| `background: #181818` | NO | `#rrggbb` không phải built-in hex literal |
| `weight: 700` | YES | `700` là integer, cast sang FontWeight |
| multiline/inline mix | YES | `;` separator đã được Vir hỗ trợ |

### 12.3 Vir v2.0 compatible syntax (hiện tại)

```vir
include gui
import app, window, text, button, run from gui

func main:
    a = app.create("Vir GUI")
    w = window.create(a, "Vir GUI", 640, 420)
    w.bg(color.hex("#181818"))

    lbl = text.create(w, "Hello Vir")
    lbl.size(length.px(28))
    lbl.weight(fontWeight.bold)
    lbl.color(color.hex("#ffffff"))

    btn = button.create(w, "Continue")
    btn.width(length.px(160))
    btn.height(length.px(44))
    btn.bg(color.hex("#2563eb"))
    btn.fg(color.hex("#ffffff"))
    btn.radius(length.px(8))
    btn.onClick(func: print("Continue clicked") end.)

    run(a)
end.
```

### 12.4 Compiler Primitive Proposals

Các feature dưới đây là **tổng quát** (không GUI-specific):

**P1: TypedUnitLiteral**
```
Syntax:  <number><suffix>     (e.g. 16px, 10ms, 90deg, 5kb)
Resolve: calls suffix.from(value) or length.px(value)
Use cases: GUI lengths, duration, angles, file sizes, frequencies
```

**P2: CustomLiteralHook**
```
Syntax:  #rrggbb
Resolve: calls Color.fromHex(literal_string) if Color in scope
Use cases: colors, hex IDs, binary masks
```

**P3: ContextMemberSyntax**
```
Syntax:  .button()  (leading dot inside a block)
Resolve: dispatches to current context object
         ui.button() where ui is the implicit receiver
Use cases: DSL builders, query builders, config blocks
```

**P4: DeclarativeBlockSyntax (optional)**
```
Syntax:  property: value   (inside a designated block)
Resolve: calls style.set(property, value) via library hook
Use cases: CSS-like configs, TOML-like blocks, schema declarations
```

Mỗi proposal phải có issue riêng trong Vir compiler tracker,
không được implement GUI trước khi proposal được duyệt.

---

## 13. Widget API Reference

### 13.1 Window

```vir
window.create(app, title, width, height)    → Window
window.show(win)
window.hide(win)
window.close(win)
window.setTitle(win, title)
window.resize(win, w, h)
window.center(win)
window.bg(win, paint)
window.fullscreen(win, bool)
window.resizable(win, bool)
window.decorated(win, bool)

# Events
win.onOpen(handler)
win.onClose(handler)
win.onResize(handler: func(w, h))
win.onMove(handler: func(x, y))
win.onFocus(handler)
win.onBlur(handler)
```

### 13.2 Text

```vir
text.create(parent, content)    → TextNode
lbl.content(string)
lbl.size(length)
lbl.weight(weight)
lbl.color(color)
lbl.font(fontSpec)
lbl.align(textAlign)
lbl.lineHeight(float)
lbl.wrap(bool)
lbl.ellipsis(bool)
lbl.selectable(bool)
```

### 13.3 Button

```vir
button.create(parent, label)    → Button
btn.label(string)
btn.icon(image)
btn.width(length)
btn.height(length)
btn.bg(paint)
btn.fg(color)
btn.radius(cornerRadius)
btn.padding(insets)
btn.disabled(bool)

btn.onClick(handler)
btn.onDoubleClick(handler)
btn.onHover(enter, leave)
```

### 13.4 Input

```vir
input.create(parent, placeholder)  → Input
inp.value(string)                  # set value
inp.getValue()                     → string
inp.placeholder(string)
inp.width(length)
inp.type(inputType)                # text/password/number/email
inp.disabled(bool)
inp.readOnly(bool)
inp.maxLength(i32)

inp.onChange(handler: func(value))
inp.onSubmit(handler: func(value))
inp.onFocus(handler)
inp.onBlur(handler)
```

### 13.5 Row / Column

```vir
row.create(parent)   → Row
col.create(parent)   → Column

container.gap(length)
container.padding(insets)
container.align(alignment)
container.justify(justify)
container.wrap(bool)
container.add(child)
container.remove(child)
container.clear()
```

### 13.6 Image

```vir
image.create(parent, src)  → Image
img.src(string)
img.width(length)
img.height(length)
img.fit(imageFit)           # fill/contain/cover/none/scaleDown
img.alt(string)             # accessibility
img.onLoad(handler)
img.onError(handler)
```

### 13.7 Canvas

```vir
canvas.create(parent, w, h)   → Canvas
c.fillRect(rect, paint)
c.strokeRect(rect, stroke)
c.fillCircle(center, radius, paint)
c.drawLine(from, to, stroke)
c.drawPath(path, paint)
c.drawText(text, pos, font, color)
c.drawImage(img, dest)
c.clear()
c.flush()

c.onDraw(handler: func(ctx: CanvasContext))
```

---

## 14. Custom Component API

User có thể tạo component riêng không cần sửa stdlib:

```vir
# Custom Card component
entity CardProps:
    title:   string
    content: string
    accent:  Color
end.

func card(parent, props: CardProps):
    p = panel.create(parent)
    p.radius(radius.all(12))
    p.bg(paint.solid(color.hex("#1e1e2e")))
    p.padding(insets.all(16))

    header = row.create(p)
    t = text.create(header, props.title)
    t.weight(fontWeight.semiBold)
    t.color(props.accent)

    body = text.create(p, props.content)
    body.color(color.hex("#cdd6f4"))

    out p
end.

# Usage
card(win, CardProps(
    title: "Status",
    content: "All systems operational",
    accent: color.hex("#a6e3a1")
))
```

---

## 15. Theme System

```
Entity Theme
  # Color tokens
  primary    : Color
  secondary  : Color
  surface    : Color
  background : Color
  text       : Color
  textMuted  : Color
  border     : Color
  accent     : Color
  danger     : Color
  warning    : Color
  success    : Color

  # Spacing tokens
  spacing    : SpacingScale   (xs/sm/md/lg/xl)

  # Typography tokens
  fontFamily : string
  fontSize   : Length
  fontScale  : float

  # Radius tokens
  radius     : RadiusScale    (none/sm/md/lg/full)

  # Shadow tokens
  shadow     : ShadowScale    (none/sm/md/lg)
```

```vir
# Light/dark built-in
theme.set(theme.light)
theme.set(theme.dark)
theme.set(theme.system)      # follow OS preference

# Custom
myTheme = theme.create()
myTheme.primary = color.hex("#2563eb")
myTheme.background = color.hex("#0f172a")
theme.set(myTheme)
```

---

## 16. Error Model

```
enum GuiError
  windowCreationFailed(reason: string)
  rendererFailed(reason: string)
  fontLoadFailed(path: string)
  imageDecodeFailed(path: string, format: string)
  unsupportedBackend(platform: string)
  invalidLength(input: string)
  invalidColor(input: string)
  platformError(code: i32, msg: string)
  resourceNotFound(kind: string, id: string)
```

Dùng `Result(T, GuiError)`. Không dùng `none` cho lỗi nghiệp vụ.

---

## 17. Memory Model

| Resource | Ownership | Lifetime |
|----------|-----------|---------|
| App | Owned by `main` | Toàn bộ chương trình |
| Window | Owned by App | Đến khi `window.close()` |
| Node/Widget | Owned by parent Node | Lifetime của parent |
| Style | Value type (copy) | Per node |
| Image data | Reference counted / arena | Đến khi unreferenced |
| Font cache | Global cache | App lifetime |
| Glyph cache | Per-font, bounded LRU | App lifetime |
| Event callbacks | Owned by Node | Lifetime của Node |
| Renderer | Owned by Window | Window lifetime |
| Platform handle | Opaque int/ptr | Managed by platform layer |

**Arena-friendly design:**
- Style và LayoutResult là value types → stack allocation
- Node children là owned arrays → contiguous heap block
- Paint commands per frame → arena bump allocation, reset each frame
- String data → Vir string arena

---

## 18. Thread Model

```
Main Thread (UI Thread)
├── Event loop (platform)
├── Event dispatch to Node tree
├── State updates
├── Layout pass
├── Paint list generation
└── Present to surface

Render Thread (optional, future)
├── Receive paint list from UI thread
├── Execute GPU draw calls
└── Present to swap chain

Worker Threads
├── Image decode
├── Font loading
└── Network/IO (for async content)
```

**Quy tắc:**
- UI tree chỉ được mutate từ Main Thread
- Event handlers chạy trên Main Thread
- Worker threads giao tiếp với UI thread qua message queue

---

## 19. Accessibility

```
Entity A11yNode
  role        : A11yRole      (button/text/input/image/list/...)
  label       : string        (accessible name)
  description : string        (additional description)
  value       : string        (current value for inputs)
  state       : A11yState     (checked/selected/disabled/expanded)
  focusable   : bool
  tabIndex    : i32
```

Mỗi widget có default role:
- `button` → `A11yRole.button`
- `text` → `A11yRole.staticText`
- `input` → `A11yRole.textInput`
- `image` → `A11yRole.image`

Platform accessibility API (VoiceOver/NVDA/AT-SPI) được bridge qua `platform/` layer.

---

## 20. Graphics Foundation

### 20.1 Primitives

```
Entity Point  : x: float, y: float
Entity Size   : width: float, height: float
Entity Rect   : x: float, y: float, width: float, height: float
Entity Insets : top: float, right: float, bottom: float, left: float
```

### 20.2 Path2D

```
Entity Path2D
  commands : [PathCommand]

enum PathCommand
  moveTo(x, y)
  lineTo(x, y)
  cubicBezier(cp1x, cp1y, cp2x, cp2y, x, y)
  quadBezier(cpx, cpy, x, y)
  arc(cx, cy, radius, startAngle, endAngle, clockwise)
  close
```

### 20.3 Gradient

```
Entity GradientStop
  offset : float   (0.0..1.0)
  color  : Color

Entity LinearGradient
  from  : Point
  to    : Point
  stops : [GradientStop]

Entity RadialGradient
  center : Point
  radius : float
  stops  : [GradientStop]
```

---

## 21. Animation System

```
Entity Animation<T>
  from     : T
  to       : T
  duration : Duration       (from chrono)
  delay    : Duration
  easing   : EasingFn
  repeat   : RepeatMode     (none/loop/pingPong)
  onUpdate : func(value: T)
  onEnd    : func

enum EasingFn
  linear | easeIn | easeOut | easeInOut
  spring(stiffness, damping, mass)
  cubicBezier(p1x, p1y, p2x, p2y)

animation.play(anim)
animation.pause(anim)
animation.cancel(anim)
```

Animation system tách khỏi render loop — update được schedule qua `animationFrame` callback.

---

## 22. Naming Conventions

| Loại | Convention | Ví dụ |
|------|-----------|-------|
| Module | lowercase | `gui`, `widget`, `style` |
| Entity | PascalCase | `Node`, `Style`, `Color` |
| Enum | PascalCase | `Display`, `Overflow`, `EventKind` |
| Enum variant | camelCase | `flex`, `hidden`, `click` |
| Function | camelCase | `onClick`, `setTitle`, `fromHex` |
| Const | camelCase or ALL_CAPS | `color.white`, `PLATFORM_MACOS` |
| Private | `_` prefix | `_handle`, `_dispatch` |

Không dùng: `setWidth`, `getColor`, `calculateLayout`, `snake_case` trong public API.

---

## 23. Design Decisions Log

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | `gui/` ở `stdlib/vir/gui/` — extend existing, không tạo mới | Theo convention repository |
| D2 | Không hardcode GUI vào compiler | GUI là library; compiler chỉ cung cấp generic primitives |
| D3 | Style là typed entity, không Map(string, any) | Type safety; IDE support; performance |
| D4 | Color dùng `u8 rgba`, không float | Compact; matches platform APIs; common representation |
| D5 | Length là enum, không float | Hỗ trợ px/percent/em/auto/fr đều là typed |
| D6 | Node tree owned hierarchy | Vir ownership model; không GC needed |
| D7 | PaintCommand list (retained mode) | Decouples UI logic từ rendering; enables dirty tracking |
| D8 | Platform abstraction interface | Backend swap không phá public API |
| D9 | Không wrap GTK/Qt | Public architecture là của Vir; không lock vào third-party ABI |
| D10 | TypedUnitLiteral proposal tổng quát | `px` không phải GUI-only; `ms`/`deg`/`kb` cũng cần |
| D11 | HexLiteral proposal tổng quát | `#rrggbb` là common literal, không phải GUI-only |
| D12 | First target: macOS ARM64 | Matches Vir compiler primary platform |
| D13 | Animation system tách khỏi render loop | Reuse cho non-GUI animation; testable independently |
| D14 | A11y là first-class, không afterthought | Platform accessibility integration cần architecture support từ đầu |

---

## 24. Extension Points

| Area | Cơ chế |
|------|--------|
| Custom widget | Entity + func pattern; không cần stdlib modification |
| Custom renderer | Implement Renderer interface; inject via `app.setRenderer()` |
| Custom platform | Implement Platform interface; inject via `app.setPlatform()` |
| Custom theme | `Theme` entity; set via `theme.set()` |
| Custom layout | Implement LayoutEngine interface; attach to Node |
| Text engine | Implement TextEngine interface; platform-specific shaping |
| Image decoder | Plugin pattern: `image.registerDecoder(format, decoder)` |

---

## 25. First Milestone Checklist

Milestone 1 (Foundation) — target: working native app

```
[ ] app.create / app.run / app.quit
[ ] window.create / window.show / window.close
[ ] text.create với size/weight/color
[ ] button.create với width/height/bg/fg/radius
[ ] button.onClick event
[ ] color.hex() parser
[ ] length.px() / length.pct()
[ ] Basic style resolution
[ ] Box model (content+padding)
[ ] macOS AppKit backend (window + label + button)
[ ] Event loop integration
[ ] Resource cleanup on close
[ ] Basic tests (style, color, length)
[ ] Example app compiles and runs
```

---

## 26. Reference Sources

| Nguồn | Dùng cho |
|-------|---------|
| CSS Specifications (W3C) | Box model, flexbox, grid, typography concepts |
| Flutter Widget API | Declarative UI patterns, widget composition |
| SwiftUI (Apple) | Property-based style API, declarative DSL design |
| Jetpack Compose (Google) | Composable component patterns |
| AppKit/Cocoa (Apple) | macOS native backend |
| Direct2D / Core Graphics | 2D rendering API design |
| HarfBuzz | Text shaping reference |
| WAI-ARIA (W3C) | Accessibility roles and states |
| Vir Language Spec v2.0 | Vir syntax constraints and idioms |
