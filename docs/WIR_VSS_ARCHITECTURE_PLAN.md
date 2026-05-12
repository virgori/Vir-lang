# W-IR + VSS — Kế Hoạch Kiến Trúc

> **Phiên bản**: Draft 1.0 — 17/03/2026  
> **Mục tiêu**: Thêm tầng IR song song (W-IR) cho WebAssembly target + hệ thống VSS (Vir Style Sheets)

---

## Mục lục

1. [Tổng quan & Động lực](#1-tổng-quan--động-lực)
2. [Kiến trúc tổng thể — Vị trí W-IR trong pipeline](#2-kiến-trúc-tổng-thể)
3. [W-IR: Web Intermediate Representation](#3-w-ir-web-intermediate-representation)
4. [VSS: Vir Style Sheets](#4-vss-vir-style-sheets)
5. [Pipeline biên dịch mới](#5-pipeline-biên-dịch-mới)
6. [Cấu trúc thư mục](#6-cấu-trúc-thư-mục)
7. [Kế hoạch triển khai theo giai đoạn](#7-kế-hoạch-triển-khai-theo-giai-đoạn)
8. [Chi tiết kỹ thuật — W-IR Opcodes](#8-chi-tiết-kỹ-thuật--w-ir-opcodes)
9. [Chi tiết kỹ thuật — VSS Syntax & Compilation](#9-chi-tiết-kỹ-thuật--vss-syntax--compilation)
10. [Tích hợp với hệ thống hiện tại](#10-tích-hợp-với-hệ-thống-hiện-tại)
11. [Stdlib mới cần thêm](#11-stdlib-mới-cần-thêm)
12. [So sánh VSS vs CSS](#12-so-sánh-vss-vs-css)

---

## 1. Tổng quan & Động lực

### Hiện trạng

Hiện tại, WASM output được tạo bằng cách **dịch trực tiếp Q-IR → WASM binary** trong `codegen_wasm.py`. Cách tiếp cận này:

- ✅ Hoạt động cho logic thuần (tính toán, control flow)
- ❌ Không có khái niệm DOM, layout, event, styling
- ❌ Không tối ưu cho web-specific patterns (virtual DOM diffing, CSS dead code elimination)
- ❌ Thiếu integration giữa logic (Vir) và presentation (CSS)

### Giải pháp

Thêm **2 hệ thống mới song song**:

| Hệ thống | Vai trò | Tương đương |
|---|---|---|
| **W-IR** (Web IR) | IR chuyên web: DOM ops, events, component lifecycle, layout | Giống QIR cho tensor — nhưng cho web |
| **VSS** (Vir Style Sheets) | Ngôn ngữ styling compiled, scoped, multilingual | CSS nhưng compiled, type-safe, scoped |

Cả hai hệ thống nằm **song song với Q-IR** (không thay thế), hoạt động cùng nhau khi target là WebAssembly.

---

## 2. Kiến trúc tổng thể

### Trước (hiện tại)

```
                    ┌─────────────┐
Source (.vri) ──→  │  Frontend    │──→ AST ──→ Q-IR ──→ Optimizer ──┬→ ARM64
                    └─────────────┘                                  ├→ x86_64
                                                                     ├→ WASM (trực tiếp)
                                                                     ├→ GPU
                                      AST ──→ QIR-H → QIR-M → QIR-L │ (tensor path)
                                                                     └→ Swift
```

### Sau (đề xuất)

```
                    ┌─────────────────┐
Source (.vri) ──→  │    Frontend      │──→ AST ──┬──→ Q-IR ──→ Optimizer ──┬→ ARM64
                    └─────────────────┘          │                          ├→ x86_64
                                                 │                          ├→ GPU
                    ┌─────────────────┐          │                          └→ Swift
Style  (.vss) ──→  │  VSS Frontend    │──→ VSSA  │
                    └─────────────────┘     │     │
                                            │     │
                                            ▼     ▼
                                     ┌────────────────┐
                                     │    W-IR Layer   │ ← Tầng mới (song song Q-IR)
                                     │                 │
                                     │ W-IR-H (High)   │  Component, Route, Event, Bind
                                     │ W-IR-M (Mid)    │  DOM ops, VDOM diff, VSS resolve
                                     │ W-IR-L (Low)    │  WASM calls, JS glue, CSS emit
                                     └────────┬───────┘
                                              │
                                    ┌─────────┼──────────┐
                                    ▼         ▼          ▼
                              ┌─────────┐ ┌────────┐ ┌────────┐
                              │  .wasm  │ │ .js    │ │ .css   │
                              │ (logic +│ │ (glue +│ │(compiled│
                              │  DOM    │ │ bridge)│ │  VSS)  │
                              │  ops)   │ │        │ │        │
                              └─────────┘ └────────┘ └────────┘
```

### Mối quan hệ 3 hệ thống IR

```
┌──────────────────────────────────────────────────────────────────┐
│                        AST (ProgramNode)                         │
└──────┬──────────────────────┬──────────────────────┬─────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Q-IR       │    │   W-IR           │    │   QIR (Tensor)   │
│              │    │                  │    │                  │
│ Logic thuần  │    │ Web semantics    │    │ Tensor ops       │
│ ALU, CMP,    │    │ DOM, Event,      │    │ MATMUL, SOFTMAX, │
│ CALL, RET    │    │ Component,       │    │ ATTENTION,       │
│ SIMD, Memory │    │ VSS binding      │    │ LAYER_NORM       │
│              │    │                  │    │                  │
│ 95+ opcodes  │    │ ~80 opcodes      │    │ ~60 opcodes      │
│ (SSA)        │    │ (3-level: H/M/L) │    │ (3-level: H/M/L) │
└──────┬───────┘    └────────┬─────────┘    └────────┬─────────┘
       │                     │                       │
       ▼                     ▼                       ▼
  ARM64/x86/GPU         WASM+JS+CSS              WASM+GPU
  (native)              (web bundle)             (compute)
```

**Nguyên tắc**: Khi compile cho web target:
- **Q-IR** xử lý logic thuần (tính toán, thuật toán) → WASM functions
- **W-IR** xử lý web semantics (DOM, events, lifecycle) → WASM + JS bridge
- **VSS AST (VSSA)** được W-IR-M resolve → CSS output hoặc inline styles

---

## 3. W-IR: Web Intermediate Representation

### 3.1 Thiết kế 3 tầng (giống QIR)

| Tầng | Tên | Mô tả | Tương đương QIR |
|---|---|---|---|
| **W-IR-H** | High-level | Component semantics, routes, events, bindings | QIR-H (model-semantic) |
| **W-IR-M** | Mid-level | Canonical DOM ops, VDOM diff, style resolution | QIR-M (canonical) |
| **W-IR-L** | Low-level | WASM imports, JS interop calls, CSS emission | QIR-L (scheduling) |

### 3.2 W-IR-H — Component Semantics

Opcodes mô tả ý nghĩa web ở mức cao:

```
# Component lifecycle
W_COMPONENT_DEF      name, props[], state[], children
W_COMPONENT_MOUNT    component_id
W_COMPONENT_UPDATE   component_id, changed_props[]
W_COMPONENT_UNMOUNT  component_id

# Routing
W_ROUTE_DEF          path_pattern, component_id, guards[]
W_ROUTE_NAVIGATE     path, params
W_ROUTE_PARAM        name → value

# Event binding
W_EVENT_BIND         element_id, event_type, handler_fn
W_EVENT_UNBIND       element_id, event_type
W_EVENT_EMIT         event_name, payload

# Reactive state
W_STATE_DEF          name, initial_value, type
W_STATE_GET          state_id → value
W_STATE_SET          state_id, new_value → triggers re-render
W_COMPUTED           deps[], compute_fn → cached value
W_EFFECT             deps[], effect_fn, cleanup_fn

# DOM declaration (high-level)
W_ELEMENT            tag, attrs{}, children[]
W_TEXT               content
W_FRAGMENT           children[]
W_CONDITIONAL        condition, then_tree, else_tree
W_LIST               items, key_fn, render_fn
W_SLOT               name, fallback

# Style binding
W_STYLE_BIND         element_id, vss_class_id
W_STYLE_DYNAMIC      element_id, prop, expr
W_STYLE_SCOPED       component_id, vss_module_id
```

### 3.3 W-IR-M — Canonical DOM Operations

Sau khi lowering W-IR-H, các composite ops được phân rã:

```
# DOM manipulation (canonical)
W_CREATE_ELEMENT     tag → element_id
W_CREATE_TEXT        content → text_id
W_SET_ATTR           element_id, attr_name, value
W_REMOVE_ATTR        element_id, attr_name
W_SET_PROP           element_id, prop_name, value
W_APPEND_CHILD       parent_id, child_id
W_INSERT_BEFORE      parent_id, child_id, ref_id
W_REMOVE_CHILD       parent_id, child_id
W_REPLACE_CHILD      parent_id, new_id, old_id
W_SET_TEXT            text_id, content
W_SET_INNER_HTML     element_id, html     # sanitized only

# VDOM diff
W_DIFF_START         old_tree_id, new_tree_id
W_DIFF_PATCH         patch_op[]           # minimal DOM mutations
W_DIFF_COMMIT        patches → apply to real DOM

# Style resolution
W_RESOLVE_CLASS      vss_class_id → css_class_name (mangled, scoped)
W_RESOLVE_DYNAMIC    expr → inline_style_value
W_APPLY_STYLE        element_id, resolved_styles{}

# Event (canonical)
W_ADD_LISTENER       element_id, event_type, handler_id, options
W_REMOVE_LISTENER    element_id, event_type, handler_id
W_DISPATCH_EVENT     element_id, event_type, detail

# State (canonical)
W_ALLOC_STATE        size, type → state_ptr
W_LOAD_STATE         state_ptr → value
W_STORE_STATE        state_ptr, value → notify_subscribers
W_SUBSCRIBE          state_ptr, callback_id
```

### 3.4 W-IR-L — WASM + JS Glue Emission

Tầng thấp nhất, map trực tiếp vào WASM imports và JS interop:

```
# WASM ↔ JS bridge calls
W_IMPORT_JS          module, func_name, signature
W_CALL_JS            import_id, args[]
W_EXPORT_WASM        func_name, wasm_func_id

# DOM API calls (via JS imports)
W_JS_CREATE_ELEMENT  tag → handle (i32)
W_JS_SET_ATTRIBUTE   handle, name_ptr, value_ptr
W_JS_APPEND_CHILD    parent_handle, child_handle
W_JS_ADD_EVENT       handle, event_ptr, callback_idx
W_JS_REMOVE_CHILD    parent_handle, child_handle
W_JS_SET_TEXT        handle, text_ptr
W_JS_SET_STYLE       handle, prop_ptr, value_ptr

# CSS emission
W_EMIT_CSS_RULE      selector, declarations[]
W_EMIT_CSS_MEDIA     query, rules[]
W_EMIT_CSS_KEYFRAME  name, steps[]
W_EMIT_CSS_VAR       name, value

# Memory (linear memory management for strings/data)
W_STRING_ALLOC       len → ptr
W_STRING_WRITE       ptr, data
W_STRING_FREE        ptr

# Scheduling
W_REQUEST_FRAME      callback_id            # requestAnimationFrame
W_SET_TIMEOUT        callback_id, ms
W_MICROTASK          callback_id            # queueMicrotask
```

---

## 4. VSS: Vir Style Sheets

### 4.1 Triết lý

| Nguyên tắc | CSS | VSS |
|---|---|---|
| **Scope** | Global mặc định, cần BEM/CSS Modules | **Scoped mặc định** — tự động mangle class names |
| **Typing** | Không có type safety | **Type-checked** — `width: 10` compile error nếu thiếu unit |
| **Dead code** | Cần PurgeCSS bên ngoài | **Compiled** — unused styles bị loại bỏ tại compile time |
| **Nesting** | Cần SCSS/PostCSS | **Native nesting** — `&` operator built-in |
| **Variables** | `--custom-property` | **Vir expressions** — dùng biến Vir, tính toán tại compile time |
| **Responsive** | `@media` queries | **`when` blocks** — cùng cú pháp với Vir (`when width > 768 ...`) |
| **Multilingual** | Chỉ tiếng Anh | **Đa ngôn ngữ** — viết style bằng tiếng Việt/Trung/Nhật/Hàn/Anh |
| **Theming** | CSS custom properties | **Theme entities** — typed, validated, auto-completed |

### 4.2 File format: `.vss`

```vss
# ── Tiếng Việt ──

chủ_đề Sáng:
    màu_nền:       #ffffff
    màu_chữ:       #1a1a2e
    màu_chính:     #0066ff
    bo_tròn:       8px
    bóng:          0 2px 8px rgba(0,0,0,0.1)
hết

phong_cách nút_chính:
    nền:           chủ_đề.màu_chính
    chữ:           #ffffff
    đệm:          12px 24px
    bo:            chủ_đề.bo_tròn
    chuyển_động:   nền 0.2s ease

    &:hover:
        nền:       darken(chủ_đề.màu_chính, 10%)
    hết

    &:active:
        scale:     0.98
    hết
hết

phong_cách thẻ:
    nền:           chủ_đề.màu_nền
    bo:            chủ_đề.bo_tròn
    bóng:          chủ_đề.bóng
    đệm:          16px

    khi chiều_rộng > 768px:
        đệm:      24px
        bố_cục:   hàng ngang
    hết
hết
```

```vss
# ── English ──

theme Light:
    bg_color:      #ffffff
    text_color:    #1a1a2e
    primary:       #0066ff
    radius:        8px
    shadow:        0 2px 8px rgba(0,0,0,0.1)
end

style primary_button:
    background:    theme.primary
    color:         #ffffff
    padding:       12px 24px
    border_radius: theme.radius
    transition:    background 0.2s ease

    &:hover:
        background: darken(theme.primary, 10%)
    end

    &:active:
        scale:      0.98
    end
end

style card:
    background:    theme.bg_color
    border_radius: theme.radius
    box_shadow:    theme.shadow
    padding:       16px

    when width > 768px:
        padding:    24px
        display:    row
    end
end
```

### 4.3 Cú pháp VSS — Spec tổng quan

```
# ── Khai báo ──

theme <name>:                          # Theme definition (typed variables)
    <prop>: <value>
end

style <name>:                          # Style block (scoped to component)
    <css-prop>: <value | expr>
    
    &:<pseudo>:                         # Pseudo-class nesting
        ...
    end
    
    &::<pseudo-element>:                # Pseudo-element
        ...
    end
    
    > <child-selector>:                # Child combinator
        ...
    end
    
    when <condition>:                   # Responsive/conditional
        ...
    end
end

mixin <name>(<params>):               # Reusable style fragment
    ...
end

keyframes <name>:                      # Animation
    0%:   ...  end
    100%: ...  end
end

# ── Sử dụng trong .vri ──

include "styles.vss";

func render:
    out element("div", style=thẻ):     # Bind VSS class
        element("button", style=nút_chính):
            text("Click me");
        end;
    end;
end
```

### 4.4 VSS Property Mapping

| VSS Property | CSS Property | Tiếng Việt | Ghi chú |
|---|---|---|---|
| `background` | `background` | `nền` | |
| `color` | `color` | `chữ` / `màu_chữ` | |
| `padding` | `padding` | `đệm` | |
| `margin` | `margin` | `lề` | |
| `border_radius` | `border-radius` | `bo` / `bo_tròn` | |
| `box_shadow` | `box-shadow` | `bóng` | |
| `display` | `display` | `bố_cục` | `row` = `flex; flex-direction: row` |
| `width` | `width` | `chiều_rộng` / `rộng` | |
| `height` | `height` | `chiều_cao` / `cao` | |
| `font_size` | `font-size` | `cỡ_chữ` | |
| `font_weight` | `font-weight` | `đậm` | |
| `transition` | `transition` | `chuyển_động` | |
| `transform` | `transform` | `biến_đổi` | |
| `opacity` | `opacity` | `độ_mờ` | |
| `gap` | `gap` | `khoảng_cách` | |
| `grid` | `display: grid` | `lưới` | |
| `flex` | `display: flex` | `dẻo` | |
| `position` | `position` | `vị_trí` | |
| `overflow` | `overflow` | `tràn` | |
| `cursor` | `cursor` | `con_trỏ` | |
| `z_index` | `z-index` | `tầng` | |
| `align` | `align-items` | `căn` | |
| `justify` | `justify-content` | `dàn` | |
| `scale` | `transform: scale()` | — | Shorthand |

---

## 5. Pipeline biên dịch mới

### 5.1 Luồng Web Target

```
hello.vri (logic)           hello.vss (style)
     │                           │
     ▼                           ▼
 Frontend (vi/en/zh...)     VSS Frontend
 NGramTokenizer              VSS Tokenizer
 Parser → AST                VSS Parser → VSSA (VSS AST)
     │                           │
     ├───→ Q-IR (logic)          │
     │     │                     │
     │     ▼                     │
     │   Q-IR Optimizer          │
     │     │                     │
     ▼     ▼                     ▼
┌──────────────────────────────────────┐
│           W-IR Builder               │
│                                      │
│  Input: AST + Q-IR (logic) + VSSA    │
│                                      │
│  1. Component analysis               │
│  2. Event/state dependency graph     │
│  3. DOM tree construction            │
│  4. VSS class resolution             │
│                                      │
│  Output: W-IR-H graph               │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         W-IR Optimizer               │
│                                      │
│  Pass 1: Dead style elimination      │
│  Pass 2: Component tree shaking      │
│  Pass 3: Event handler dedup         │
│  Pass 4: Static subtree hoisting     │
│  Pass 5: VDOM diff minimization      │
│  Pass 6: CSS property merging        │
│  Pass 7: Style scoping (mangle)      │
│  Pass 8: DCE                         │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         W-IR H → M Lowering          │
│                                      │
│  W_COMPONENT_DEF → DOM ops sequence  │
│  W_STATE_SET → notify + diff + patch │
│  W_STYLE_BIND → resolved CSS class   │
│  W_CONDITIONAL → DOM branching       │
│  W_LIST → keyed reconciliation       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         W-IR M → L Lowering          │
│                                      │
│  W_CREATE_ELEMENT → W_JS_CREATE_*    │
│  W_SET_ATTR → W_JS_SET_ATTRIBUTE     │
│  W_RESOLVE_CLASS → W_EMIT_CSS_RULE   │
│  W_ADD_LISTENER → W_JS_ADD_EVENT     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         Web Bundle Emitter           │
│                                      │
│  ┌──────────┐  ┌────────┐  ┌──────┐ │
│  │ .wasm    │  │ .js    │  │ .css │ │
│  │          │  │        │  │      │ │
│  │ Q-IR →   │  │ Bridge │  │ VSS  │ │
│  │ WASM bin │  │ code + │  │  →   │ │
│  │ + DOM    │  │ loader │  │ CSS  │ │
│  │ imports  │  │        │  │      │ │
│  └──────────┘  └────────┘  └──────┘ │
└──────────────────────────────────────┘
```

### 5.2 Output bundle

```
dist/
├── app.wasm           # Logic + DOM manipulation compiled
├── app.js             # JS bridge: WASM loader, DOM API imports, event dispatcher
├── app.css            # Compiled VSS → optimized CSS
└── index.html         # Entry point (auto-generated hoặc user template)
```

### 5.3 JS Bridge Architecture

```javascript
// app.js (auto-generated)
const imports = {
  env: {
    // DOM API — called from WASM
    js_create_element: (tag_ptr, tag_len) => { ... },
    js_set_attribute: (handle, name_ptr, name_len, val_ptr, val_len) => { ... },
    js_append_child: (parent_handle, child_handle) => { ... },
    js_remove_child: (parent_handle, child_handle) => { ... },
    js_add_event: (handle, event_ptr, event_len, callback_idx) => { ... },
    js_set_text: (handle, text_ptr, text_len) => { ... },
    js_set_style: (handle, prop_ptr, prop_len, val_ptr, val_len) => { ... },
    
    // Scheduling
    js_request_frame: (callback_idx) => requestAnimationFrame(() => wasm_call(callback_idx)),
    js_set_timeout: (callback_idx, ms) => setTimeout(() => wasm_call(callback_idx), ms),
    
    // Memory
    print: (val) => console.log(val),
    input: () => prompt("Input:"),
  }
};
```

---

## 6. Cấu trúc thư mục

### 6.1 Files mới trong compiler (`src/`)

```
src/
├── wir/                              # ★ MỚI — W-IR module (song song với ir/ và qir/)
│   ├── __init__.py                   #   Exports: WIRHOp, WIRMOp, WIRLOp, WIRGraph, ...
│   ├── opcodes.py                    #   3-level opcode enums
│   ├── schema.py                     #   WIRHNode, WIRMNode, WIRLNode, StyleType, EventType
│   ├── module.py                     #   WIRGraph, WIRBlock, WIRComponent
│   ├── builder/
│   │   ├── __init__.py
│   │   ├── component_builder.py      #   AST → W-IR-H (component analysis)
│   │   └── dom_builder.py            #   Element/text/fragment construction
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── optimizer.py              #   8-pass W-IR optimizer
│   │   ├── dead_style_elim.py        #   Remove unused VSS classes
│   │   ├── tree_shaking.py           #   Remove unreachable components
│   │   ├── static_hoist.py           #   Hoist static subtrees
│   │   └── vdom_minimize.py          #   Minimize diff patches
│   ├── lower/
│   │   ├── __init__.py
│   │   ├── h_to_m.py                 #   W-IR-H → W-IR-M (component → DOM ops)
│   │   └── m_to_l.py                 #   W-IR-M → W-IR-L (DOM ops → JS bridge calls)
│   ├── infer/
│   │   ├── __init__.py
│   │   └── dom_type_infer.py         #   Infer element types, prop types
│   └── verify/
│       ├── __init__.py
│       └── web_verify.py             #   Validate W-IR correctness
│
├── vss/                              # ★ MỚI — VSS compiler
│   ├── __init__.py
│   ├── tokenizer.py                  #   VSS tokenizer (reuse NGram for multilingual)
│   ├── parser.py                     #   VSS → VSSA (VSS AST)
│   ├── ast.py                        #   VSSA node types
│   ├── resolver.py                   #   Theme resolution, mixin expansion
│   ├── scoper.py                     #   Class name mangling (scope isolation)
│   ├── optimizer.py                  #   Property merging, shorthand collapsing
│   ├── emitter_css.py                #   VSSA → CSS output
│   ├── emitter_inline.py             #   VSSA → inline style strings (for SSR)
│   └── sublib/                       #   Multilingual property mappings
│       ├── vi.py                     #     nền → background, đệm → padding, ...
│       ├── en.py                     #     (identity mapping)
│       ├── zh.py                     #     背景 → background, 内边距 → padding, ...
│       ├── ja.py                     #     背景 → background, ...
│       └── ko.py                     #     배경 → background, ...
│
├── backend/
│   ├── codegen/
│   │   ├── codegen_wasm.py           # (existing) — Q-IR → WASM (logic only)
│   │   └── codegen_web.py            # ★ MỚI — W-IR-L → WASM+JS+CSS bundle
│   └── web/                          # ★ MỚI
│       ├── __init__.py
│       ├── bundle_emitter.py         #   Produces dist/ bundle
│       ├── js_bridge.py              #   Generates JS bridge code
│       ├── html_emitter.py           #   Generates index.html
│       └── sourcemap.py              #   Source map generation (.vri → .wasm)
```

### 6.2 Files mới trong stdlib

```
stdlib/vir/
├── dom/                              # ★ MỚI — DOM API
│   ├── dom.vri                       #   Element, TextNode, Document entities
│   ├── events.vri                    #   Event, MouseEvent, KeyEvent entities
│   └── query.vri                     #   querySelector equivalent
│
├── component/                        # ★ MỚI — Component system
│   ├── component.vri                 #   Component trait, lifecycle hooks
│   ├── state.vri                     #   Reactive state primitives
│   ├── effect.vri                    #   Side effects, cleanup
│   └── context.vri                   #   Shared context (like React Context)
│
├── vss/                              # ★ MỚI — VSS runtime support
│   ├── vss.vri                       #   Style, Theme, Mixin entities
│   ├── units.vri                     #   px, em, rem, %, vw, vh, ...
│   ├── colors.vri                    #   Color manipulation: darken, lighten, mix
│   └── media.vri                     #   Breakpoint definitions
│
├── router/                           # ★ MỚI — Client-side routing
│   ├── router.vri                    #   Route, Router entities
│   └── history.vri                   #   pushState/popState wrappers
│
├── wasm/
│   ├── wasm.vri                      #  (existing) — WASM types
│   ├── dom_imports.vri               # ★ MỚI — JS↔WASM DOM bridge declarations
│   └── memory.vri                    # ★ MỚI — Linear memory string/data helpers
```

### 6.3 Tests mới

```
tests/
├── wir/                              # ★ MỚI
│   ├── test_wir_opcodes.py
│   ├── test_wir_builder.py
│   ├── test_wir_optimizer.py
│   ├── test_wir_lower_h_to_m.py
│   ├── test_wir_lower_m_to_l.py
│   └── test_wir_integration.py
│
├── vss/                              # ★ MỚI
│   ├── test_vss_tokenizer.py
│   ├── test_vss_parser.py
│   ├── test_vss_resolver.py
│   ├── test_vss_scoper.py
│   ├── test_vss_emitter_css.py
│   ├── test_vss_multilingual.py
│   └── test_vss_integration.py
│
├── backend/
│   ├── test_codegen_web.py           # ★ MỚI
│   └── test_bundle_emitter.py        # ★ MỚI
```

---

## 7. Kế hoạch triển khai theo giai đoạn

### Phase 1: VSS Core (Foundation)
**Scope**: VSS tokenizer, parser, AST, CSS emitter

| Task | File(s) | Mô tả |
|---|---|---|
| 1.1 | `src/vss/ast.py` | Định nghĩa VSSA node types |
| 1.2 | `src/vss/sublib/en.py` | English property mapping (identity) |
| 1.3 | `src/vss/sublib/vi.py` | Vietnamese property mapping |
| 1.4 | `src/vss/tokenizer.py` | VSS tokenizer — reuse NGram framework |
| 1.5 | `src/vss/parser.py` | VSS parser → VSSA |
| 1.6 | `src/vss/resolver.py` | Theme variable resolution, mixin expansion |
| 1.7 | `src/vss/scoper.py` | Scoped class name mangling |
| 1.8 | `src/vss/emitter_css.py` | VSSA → CSS output |
| 1.9 | `tests/vss/` | Full test suite |

**Deliverable**: `vir style.vss --emit-css` → standalone CSS file

### Phase 2: W-IR Foundation
**Scope**: W-IR opcodes, schema, module, basic builder

| Task | File(s) | Mô tả |
|---|---|---|
| 2.1 | `src/wir/opcodes.py` | Define WIRHOp, WIRMOp, WIRLOp enums |
| 2.2 | `src/wir/schema.py` | WIRHNode, WIRMNode, WIRLNode dataclasses |
| 2.3 | `src/wir/module.py` | WIRGraph, WIRBlock, WIRComponent containers |
| 2.4 | `src/wir/builder/dom_builder.py` | Static DOM tree → W-IR-H |
| 2.5 | `src/wir/lower/h_to_m.py` | W-IR-H → W-IR-M |
| 2.6 | `src/wir/lower/m_to_l.py` | W-IR-M → W-IR-L |
| 2.7 | `tests/wir/` | Opcode + builder + lowering tests |

**Deliverable**: W-IR pipeline can represent static DOM trees

### Phase 3: DOM & Component Stdlib
**Scope**: DOM entities, component traits, state primitives

| Task | File(s) | Mô tả |
|---|---|---|
| 3.1 | `stdlib/vir/dom/dom.vri` | Element, TextNode, Document |
| 3.2 | `stdlib/vir/dom/events.vri` | Event hierarchy |
| 3.3 | `stdlib/vir/component/component.vri` | Component trait + lifecycle |
| 3.4 | `stdlib/vir/component/state.vri` | Reactive state |
| 3.5 | `stdlib/vir/vss/vss.vri` | VSS runtime types |
| 3.6 | `stdlib/vir/vss/units.vri` | CSS units |
| 3.7 | `stdlib/vir/vss/colors.vri` | Color functions |

**Deliverable**: Vir programs can declare components and styles

### Phase 4: Web Codegen
**Scope**: WASM + JS bridge + CSS bundle output

| Task | File(s) | Mô tả |
|---|---|---|
| 4.1 | `src/backend/web/js_bridge.py` | Generate JS bridge code |
| 4.2 | `src/backend/web/html_emitter.py` | Generate index.html |
| 4.3 | `src/backend/codegen/codegen_web.py` | W-IR-L → WASM binary (with DOM imports) |
| 4.4 | `src/backend/web/bundle_emitter.py` | Combine .wasm + .js + .css → dist/ |
| 4.5 | Integrate Q-IR WASM + W-IR WASM | Merge logic WASM + DOM WASM into single module |

**Deliverable**: `vir app.vri --target web` → dist/ bundle (chạy trong browser)

### Phase 5: W-IR Optimizer
**Scope**: Web-specific optimization passes

| Task | File(s) | Mô tả |
|---|---|---|
| 5.1 | `src/wir/optimizer/dead_style_elim.py` | Remove unused VSS classes |
| 5.2 | `src/wir/optimizer/tree_shaking.py` | Remove unreachable components |
| 5.3 | `src/wir/optimizer/static_hoist.py` | Hoist static DOM subtrees |
| 5.4 | `src/wir/optimizer/vdom_minimize.py` | Minimize virtual DOM diff patches |
| 5.5 | `src/vss/optimizer.py` | CSS property merging, shorthand collapse |

**Deliverable**: Optimized web bundle output

### Phase 6: Advanced Features
**Scope**: Router, SSR, multilingual VSS, dev tooling

| Task | File(s) | Mô tả |
|---|---|---|
| 6.1 | `stdlib/vir/router/` | Client-side routing |
| 6.2 | `src/vss/sublib/zh.py, ja.py, ko.py` | Chinese/Japanese/Korean VSS support |
| 6.3 | `src/backend/web/sourcemap.py` | Source maps (.vri → .wasm) |
| 6.4 | SSR (Server-side rendering) | Pre-render HTML + hydration |
| 6.5 | Hot reload | Dev server with file watching |
| 6.6 | VS Code extension updates | `.vss` syntax highlighting |

---

## 8. Chi tiết kỹ thuật — W-IR Opcodes

### 8.1 Enum definitions (Python)

```python
# src/wir/opcodes.py

from enum import Enum, auto

class WIRHOp(Enum):
    """W-IR High-level: Component semantics"""
    
    # Component lifecycle
    COMPONENT_DEF = auto()
    COMPONENT_MOUNT = auto()
    COMPONENT_UPDATE = auto()
    COMPONENT_UNMOUNT = auto()
    
    # Routing
    ROUTE_DEF = auto()
    ROUTE_NAVIGATE = auto()
    ROUTE_PARAM = auto()
    
    # Event binding
    EVENT_BIND = auto()
    EVENT_UNBIND = auto()
    EVENT_EMIT = auto()
    
    # Reactive state
    STATE_DEF = auto()
    STATE_GET = auto()
    STATE_SET = auto()
    COMPUTED = auto()
    EFFECT = auto()
    
    # DOM declaration (high-level / virtual)
    ELEMENT = auto()
    TEXT = auto()
    FRAGMENT = auto()
    CONDITIONAL = auto()
    LIST = auto()
    SLOT = auto()
    
    # Style binding
    STYLE_BIND = auto()
    STYLE_DYNAMIC = auto()
    STYLE_SCOPED = auto()


class WIRMOp(Enum):
    """W-IR Mid-level: Canonical DOM operations"""
    
    # DOM mutation
    CREATE_ELEMENT = auto()
    CREATE_TEXT = auto()
    SET_ATTR = auto()
    REMOVE_ATTR = auto()
    SET_PROP = auto()
    APPEND_CHILD = auto()
    INSERT_BEFORE = auto()
    REMOVE_CHILD = auto()
    REPLACE_CHILD = auto()
    SET_TEXT = auto()
    
    # VDOM diff
    DIFF_START = auto()
    DIFF_PATCH = auto()
    DIFF_COMMIT = auto()
    
    # Style resolution
    RESOLVE_CLASS = auto()
    RESOLVE_DYNAMIC = auto()
    APPLY_STYLE = auto()
    
    # Events (canonical)
    ADD_LISTENER = auto()
    REMOVE_LISTENER = auto()
    DISPATCH_EVENT = auto()
    
    # State (canonical)
    ALLOC_STATE = auto()
    LOAD_STATE = auto()
    STORE_STATE = auto()
    SUBSCRIBE = auto()


class WIRLOp(Enum):
    """W-IR Low-level: WASM + JS bridge emission"""
    
    # JS interop
    IMPORT_JS = auto()
    CALL_JS = auto()
    EXPORT_WASM = auto()
    
    # DOM API (via JS)
    JS_CREATE_ELEMENT = auto()
    JS_SET_ATTRIBUTE = auto()
    JS_APPEND_CHILD = auto()
    JS_REMOVE_CHILD = auto()
    JS_ADD_EVENT = auto()
    JS_SET_TEXT = auto()
    JS_SET_STYLE = auto()
    JS_INSERT_BEFORE = auto()
    JS_REPLACE_CHILD = auto()
    
    # CSS emission
    EMIT_CSS_RULE = auto()
    EMIT_CSS_MEDIA = auto()
    EMIT_CSS_KEYFRAME = auto()
    EMIT_CSS_VAR = auto()
    
    # Memory
    STRING_ALLOC = auto()
    STRING_WRITE = auto()
    STRING_FREE = auto()
    
    # Scheduling
    REQUEST_FRAME = auto()
    SET_TIMEOUT = auto()
    MICROTASK = auto()
```

### 8.2 Node schema

```python
# src/wir/schema.py

@dataclass(frozen=True)
class WIRHNode:
    """High-level W-IR node — component/DOM semantics"""
    node_id: int
    op: WIRHOp
    input_ids: tuple[int, ...]
    output_ids: tuple[int, ...]
    
    # Component metadata
    component_name: str | None = None
    props: dict[str, str] | None = None
    state_fields: list[tuple[str, str]] | None = None
    
    # DOM metadata
    tag: str | None = None
    attrs: dict[str, object] | None = None
    children_ids: tuple[int, ...] = ()
    
    # Style metadata
    vss_class_id: int | None = None
    dynamic_styles: dict[str, int] | None = None  # prop → expr_node_id
    
    # Event metadata
    event_type: str | None = None
    handler_fn: str | None = None
    
    # Source info
    name: str = ""
    source_line: int = 0


@dataclass(frozen=True)
class WIRMNode:
    """Mid-level W-IR node — canonical DOM ops"""
    node_id: int
    op: WIRMOp
    input_ids: tuple[int, ...]
    output_ids: tuple[int, ...]
    
    # DOM op details
    tag: str | None = None
    attr_name: str | None = None
    attr_value: object | None = None
    text_content: str | None = None
    
    # Style resolution
    css_class: str | None = None
    css_properties: dict[str, str] | None = None
    
    # Event details
    event_type: str | None = None
    handler_id: int | None = None
    
    # Source tracing
    source_h_id: int | None = None


@dataclass(frozen=True)
class WIRLNode:
    """Low-level W-IR node — WASM/JS bridge calls"""
    node_id: int
    op: WIRLOp
    input_ids: tuple[int, ...]
    output_ids: tuple[int, ...]
    
    # JS call metadata
    js_module: str | None = None
    js_func: str | None = None
    wasm_signature: tuple | None = None
    
    # CSS emission
    css_selector: str | None = None
    css_declarations: dict[str, str] | None = None
    css_media_query: str | None = None
    
    # Memory
    string_data: bytes | None = None
    alloc_size: int | None = None
    
    # Scheduling
    delay_ms: int | None = None
    callback_id: int | None = None
    
    # Source tracing
    source_mid_id: int | None = None
```

---

## 9. Chi tiết kỹ thuật — VSS Syntax & Compilation

### 9.1 VSSA (VSS AST) Node Types

```python
# src/vss/ast.py

@dataclass
class VSSStylesheet:
    """Root node"""
    themes: list[VSSTheme]
    styles: list[VSSStyleBlock]
    mixins: list[VSSMixin]
    keyframes: list[VSSKeyframes]
    imports: list[str]

@dataclass
class VSSTheme:
    name: str
    variables: dict[str, VSSValue]

@dataclass
class VSSStyleBlock:
    name: str                              # e.g., "primary_button"
    declarations: list[VSSDeclaration]
    nested_rules: list[VSSNestedRule]      # &:hover, > child, when ...
    mixins_applied: list[str]

@dataclass
class VSSDeclaration:
    property: str                          # CSS property name (normalized)
    value: VSSValue                        # Could be literal, theme ref, function call

@dataclass
class VSSNestedRule:
    selector: str                          # "&:hover", "> .child", "when ..."
    condition: VSSCondition | None         # For `when` blocks
    declarations: list[VSSDeclaration]
    nested_rules: list[VSSNestedRule]      # Recursive nesting

@dataclass
class VSSCondition:
    property: str                          # "width", "height", "prefers_dark"
    operator: str                          # ">", "<", ">=", "<=", "=="
    value: VSSValue

@dataclass
class VSSMixin:
    name: str
    params: list[tuple[str, VSSValue | None]]  # (name, default)
    declarations: list[VSSDeclaration]

@dataclass
class VSSKeyframes:
    name: str
    steps: list[tuple[str, list[VSSDeclaration]]]  # ("0%", decls), ("100%", decls)

# Values
@dataclass
class VSSValue:
    """Union type for VSS values"""
    pass

@dataclass
class VSSLiteral(VSSValue):
    raw: str                               # "16px", "#ff0000", "1.5"

@dataclass
class VSSThemeRef(VSSValue):
    theme_name: str | None                 # None = current theme
    var_name: str                           # "primary"

@dataclass
class VSSFuncCall(VSSValue):
    func_name: str                         # "darken", "lighten", "rgba", "calc"
    args: list[VSSValue]

@dataclass
class VSSExpr(VSSValue):
    """Arithmetic expression in VSS"""
    op: str                                # "+", "-", "*", "/"
    left: VSSValue
    right: VSSValue
```

### 9.2 VSS → CSS Compilation Example

**Input (VSS)**:
```vss
theme Light:
    primary: #0066ff
    radius:  8px
end

style card:
    background: #fff
    border_radius: theme.radius
    padding: 16px
    
    &:hover:
        box_shadow: 0 4px 12px rgba(0,0,0,0.15)
    end
    
    when width > 768px:
        padding: 24px
    end
end
```

**Output (CSS)** — with scoping:
```css
.card_x7f2a {
    background: #fff;
    border-radius: 8px;
    padding: 16px;
}
.card_x7f2a:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
@media (min-width: 768px) {
    .card_x7f2a {
        padding: 24px;
    }
}
```

**Compilation steps:**
1. **Tokenize**: `theme`, `Light`, `:`, `primary`, `:`, `#0066ff`, ...
2. **Parse → VSSA**: `VSSStylesheet(themes=[...], styles=[...])`
3. **Resolve themes**: Replace `theme.radius` → `8px`
4. **Expand mixins**: Inline mixin declarations
5. **Scope names**: `card` → `card_x7f2a` (hash of component + name)
6. **Normalize properties**: `border_radius` → `border-radius`
7. **Lower `when` blocks**: `when width > 768px` → `@media (min-width: 768px)`
8. **Emit CSS**: Output optimized CSS text

---

## 10. Tích hợp với hệ thống hiện tại

### 10.1 Thay đổi trong `src/lib/`

Thêm token kinds mới cho VSS:

```python
# Additions to TokenKind enum
TOKEN_STYLE = auto()       # "style" / "phong_cách"
TOKEN_THEME = auto()       # "theme" / "chủ_đề"  
TOKEN_MIXIN = auto()       # "mixin"
TOKEN_KEYFRAMES = auto()   # "keyframes"
TOKEN_WHEN = auto()        # Already exists (reuse từ "when <cond> loop")
TOKEN_AMPERSAND = auto()   # "&" (nested selector reference)
```

### 10.2 Thay đổi trong Frontend

Parser cần nhận diện web-specific constructs:

```python
# In parser.py — new AST nodes for .vri files with web content

class ElementExprNode:
    """element("div", style=card): ... end"""
    tag: str
    attrs: dict
    style_ref: str | None
    children: list[ASTNode]

class ComponentDefNode:
    """Extends FuncDefNode with state, props, lifecycle"""
    name: str
    props: list[tuple[str, str]]
    state: list[tuple[str, str, ASTNode]]  # (name, type, initial)
    render_fn: FuncDefNode
    mount_fn: FuncDefNode | None
    unmount_fn: FuncDefNode | None
```

### 10.3 Thay đổi trong Lifecycle

```python
# In lifecycle.py — add web target mode

class VirRuntime:
    def compile_web(self, source: str, vss_source: str | None) -> WebCompilationResult:
        """Compile for web target: .vri + .vss → WASM + JS + CSS"""
        # 1. Normal frontend: source → AST
        # 2. If vss_source: VSS frontend → VSSA
        # 3. Q-IR: AST → Q-IR → Optimize (for logic functions)
        # 4. W-IR: AST + VSSA → W-IR-H → optimize → W-IR-M → W-IR-L
        # 5. Emit: Q-IR → WASM (logic) + W-IR-L → WASM (DOM) + JS bridge + CSS
        pass
```

### 10.4 CLI mới

```bash
# Compile VSS only
vir style.vss --emit-css                  # → style.css

# Compile web app
vir app.vri --target web                  # → dist/app.{wasm,js,css,html}
vir app.vri --target web --vss style.vss  # Explicit VSS file
vir app.vri --target web --dev            # Dev mode (hot reload)
vir app.vri --target web --ssr            # Server-side rendering

# Debug/inspect
vir app.vri --target web --dump-wir       # Print W-IR
vir app.vri --target web --dump-vssa      # Print VSS AST
```

---

## 11. Stdlib mới cần thêm

### 11.1 `stdlib/vir/dom/dom.vri`

```vir
entity Element:
    tag: str
    handle: i32        # WASM linear memory handle
    children: Vec<Element>
    attrs: Map<str, str>
    style_class: str
end

entity TextNode:
    content: str
    handle: i32
end

entity Document:
    root: Element
end

# DOM API
func create_element:
    in(tag: str)
    out __wasm_import("js_create_element", tag);
end

func set_attr:
    in(el: Element; name: str; value: str)
    __wasm_import("js_set_attribute", el.handle, name, value);
end

func append_child:
    in(parent: Element; child: Element)
    __wasm_import("js_append_child", parent.handle, child.handle);
end
```

### 11.2 `stdlib/vir/component/component.vri`

```vir
trait Component<Props, State>:
    func render(self: Self; props: Props; state: State) -> Element;
    func mount(self: Self) -> void;
    func unmount(self: Self) -> void;
    func should_update(self: Self; new_props: Props; new_state: State) -> bool;
end

# Reactive state
func use_state<T>:
    in(initial: T)
    out (T, func(T) -> void);    # (value, setter)
end

func use_effect:
    in(deps: Vec<int>; effect_fn: func() -> func())
    # effect_fn returns cleanup function
end

func use_computed<T>:
    in(deps: Vec<int>; compute_fn: func() -> T)
    out T;
end
```

### 11.3 `stdlib/vir/vss/units.vri`

```vir
enum CSSUnit:
    Px(f64)
    Em(f64)
    Rem(f64)
    Percent(f64)
    Vw(f64)
    Vh(f64)
    Fr(f64)
    Auto
end

func px:
    in(val: f64)
    out CSSUnit.Px(val);
end

func em:
    in(val: f64)
    out CSSUnit.Em(val);
end

func to_css_string:
    in(unit: CSSUnit)
    case unit:
        case Px(v)      out format("{v}px")
        case Em(v)       out format("{v}em")
        case Rem(v)      out format("{v}rem")
        case Percent(v)  out format("{v}%")
        case Vw(v)       out format("{v}vw")
        case Vh(v)       out format("{v}vh")
        case Fr(v)       out format("{v}fr")
        case Auto        out "auto"
    end
end
```

---

## 12. So sánh VSS vs CSS

| Khía cạnh | CSS | VSS |
|---|---|---|
| **Scope** | Global (cascade) | Scoped mặc định (component-isolated) |
| **Variables** | `var(--name)` runtime | Compile-time resolved, zero-cost |
| **Nesting** | CSS Nesting (mới) | Native `&` operator, deeper nesting |
| **Type safety** | Không | Compile error nếu property/value sai |
| **Dead code** | Runtime (mọi rule parse) | Compile-time elimination |
| **Theming** | Custom properties | `theme` entities, typed, validated |
| **Mixins** | Không native | `mixin` + parameters |
| **Responsive** | `@media` | `when` conditions (Vir syntax) |
| **Functions** | `calc()`, limited | `darken()`, `lighten()`, Vir expressions |
| **Ngôn ngữ** | English only | 5 ngôn ngữ (vi/en/zh/ja/ko) |
| **File format** | `.css` | `.vss` → compiled `.css` |
| **Bundle** | Link manually | Auto-bundled with `--target web` |
| **Source map** | Có | `.vss` → `.css` source map |
| **Runtime cost** | Parse + cascade | Zero (pre-compiled + scoped) |

### Tương tác CSS ↔ VSS

VSS **không thay thế** CSS — nó **compiles to CSS**. Lập trình viên có thể:

1. Chỉ dùng VSS (khuyến khích)
2. Import CSS bên ngoài: `@import "external.css";` trong `.vss`
3. Mix CSS + VSS trong cùng project
4. Override VSS output bằng CSS (cascade vẫn hoạt động vì output là CSS)

---

## Tổng kết

### Quy mô ước tính

| Component | Files mới | LOC ước tính |
|---|---|---|
| W-IR (`src/wir/`) | ~15 files | ~3,000–4,000 |
| VSS (`src/vss/`) | ~12 files | ~2,500–3,500 |
| Web backend (`src/backend/web/`) | ~5 files | ~1,500–2,000 |
| Stdlib (`stdlib/vir/{dom,component,vss,router}/`) | ~12 files | ~3,000–4,000 |
| Tests (`tests/{wir,vss,backend}/`) | ~15 files | ~3,000–4,000 |
| **Tổng** | **~59 files** | **~13,000–17,500** |

### Dependency map

```
Phase 1 (VSS Core)           ← Không dependency, có thể bắt đầu ngay
Phase 2 (W-IR Foundation)    ← Không dependency, có thể song song Phase 1
Phase 3 (Stdlib DOM/Comp)    ← Cần Phase 2 (W-IR opcodes for binding)
Phase 4 (Web Codegen)        ← Cần Phase 1 + 2 + 3
Phase 5 (W-IR Optimizer)     ← Cần Phase 2 + 4
Phase 6 (Advanced)           ← Cần Phase 1–5
```

**Phase 1 và Phase 2 có thể triển khai song song** — đây là điểm khởi đầu tốt nhất.
