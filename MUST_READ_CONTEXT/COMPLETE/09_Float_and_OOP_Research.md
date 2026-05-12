# Research: Floating Point & OOP Support — Vir Compiler

> **Ngày:** 02/04/2026
> **Mục đích:** Đánh giá trạng thái hiện tại và roadmap cho Float + OOP trong Vir
> **Kết luận:** Cả hai đều CHƯA hoạt động. Float có infrastructure nhưng bug cascading. OOP chỉ có entity (C-style struct).

---

## PHẦN 1: FLOATING POINT

### 1.1 Trạng thái hiện tại: 🔴 HOÀN TOÀN KHÔNG HOẠT ĐỘNG

Float là "phantom feature" — infrastructure tồn tại nhưng cascade bugs ở mọi tầng khiến nó không dùng được.

| Stage | File | Status | Chi tiết |
|-------|------|--------|----------|
| **Lexer** | `lexer.vri` L420-500 | 🔴 BUG | Nhận diện float token nhưng chỉ tích lũy integer digits (`num = num * 10 + (c - 48)`), `tok_float_val` luôn = 0.0 |
| **Parser** | `parser.vri` L357-361 | 🟡 OK | Cấu trúc đúng nhưng nhận 0.0 từ lexer |
| **IR Lowering** | `ir_optimizer.vri` L475 | 🔴 BUG | Dùng `q_imm(expr.float_val >> int)` — bit-shift float thành garbage |
| **IR Opcodes** | QOp enum | 🔴 THIẾU | 0 float opcodes (không có FAdd, FSub, FMul, FDiv) |
| **ARM64 Codegen** | `main.vri` | 🔴 THIẾU | 0 scalar float instructions |
| **C VM** | `vm.c` | 🔴 THIẾU | Không handle float operations |
| **Tests** | — | 🔴 KHÔNG CÓ | 0 float test files |

### 1.2 Ví dụ Cascade Bug

```
Code: var x: float = 3.14

→ Lexer:  num = 314, tok_float_val = 0.0        [BUG: không compute decimal]
→ Parser: LiteralFloat { float_val = 0.0 }      [nhận garbage từ lexer]
→ IR:     Load r, q_imm(0.0 >> int)              [BUG: bit-shift = 0]
→ (không có Q_FADD opcode)                       [MISSING]
→ (không có ARM64 FADD D0,D1,D2)                 [MISSING]
→ Kết quả: x = 0 hoặc undefined                  [BROKEN]
```

### 1.3 Infrastructure Đã Có (C engine)

- `q_ir.h`: có field `double fimm` trong `QOperand`
- `q_ir.c`: có function `q_fimm()` — NHƯNG KHÔNG AI GỌI
- `codegen.vri`: có SIMD float ops (`neon_fadd_4s`, `neon_fmul_4s`) cho vectors — NHƯNG KHÔNG CÓ scalar float

### 1.4 Cần Thêm Để Float Hoạt Động

#### A. Lexer — Fix lex_number()

```
Hiện tại: num = num * 10 + (c - 48)  # integer arithmetic cho mọi digit
Cần:      tách integer_part và decimal_part, compute value = int_part + dec_part / 10^n
```

#### B. IR Opcodes — Thêm vào QOp enum

```
FAdd = 100    # float addition
FSub = 101    # float subtraction
FMul = 102    # float multiplication
FDiv = 103    # float division
FNeg = 104    # float negation
FCmpEq = 110  # float compare ==
FCmpLt = 111  # float compare <
FCmpGt = 112  # float compare >
FCvtI2F = 120 # int → float conversion
FCvtF2I = 121 # float → int conversion (truncate)
```

#### C. ARM64 Instructions — Scalar Float

```arm64
FADD  D0, D1, D2    # 0x1E602820 — double add
FSUB  D0, D1, D2    # 0x1E603820 — double sub
FMUL  D0, D1, D2    # 0x1E600820 — double mul
FDIV  D0, D1, D2    # 0x1E601820 — double div
SCVTF D0, X0        # 0x9E620000 — int64 → double
FCVTZS X0, D0       # 0x9E780000 — double → int64
FCMP  D0, D1        # 0x1E602000 — compare (set NZCV)
LDR   D0, [X1, #8]  # 0xFD400420 — load double from memory
STR   D0, [X1, #8]  # 0xFD000420 — store double to memory
```

#### D. Register Allocation

Float dùng **D-registers** (D0-D31), hoàn toàn tách biệt X-registers:
- D0-D7: caller-saved (args + return)
- D8-D15: callee-saved
- Mapping: float vreg 0-7 → D8-D15, float vreg 8-15 → D0-D7

#### E. Effort Estimate

| Phase | LOC | Thời gian ước lượng |
|-------|-----|---------------------|
| Fix lexer float parsing | ~100-150 | Ngắn |
| Thêm float opcodes | ~30 | Rất ngắn |
| Fix IR emission | ~50 | Ngắn |
| Float codegen (ARM64) | ~150-200 | Trung bình |
| VM float handlers | ~150-200 | Trung bình |
| Tests | ~200+ | Trung bình |
| **Tổng** | **~700-800** | |

---

## PHẦN 2: OOP (Object-Oriented Programming)

### 2.1 Trạng thái hiện tại: Entity = C-style Struct

Vir hiện tại có **entity** — tương đương C struct nhưng syntax đẹp hơn:

```vir
entity Point:
    x
    y
end

var p = Point{x: 10, y: 20}
p.x = 99          # FieldAssign — hoạt động
print p.y          # FieldAccess — hoạt động
```

#### Memory Layout
- Mỗi field = 8 bytes (64-bit word)
- Sequential layout: `[field0 (8B)] [field1 (8B)] ...`
- Allocation: Arena bump-alloc (virc compiler) hoặc malloc (bootstrap compiler)

### 2.2 Bảng So Sánh

| Feature | Vir Entities | C structs | Rust structs | Go structs |
|---------|---|---|---|---|
| Field definition | ✅ | ✅ | ✅ | ✅ |
| Field access/assign | ✅ | ✅ | ✅ | ✅ |
| Methods (impl) | ❌ | ❌ | ✅ | ✅ (receiver) |
| Inheritance | ❌ | ❌ | ❌ (composition) | ❌ (embedding) |
| Traits/Interfaces | ❌ | ❌ | ✅ | ✅ |
| Constructors | ❌ (literal only) | ❌ (literal) | ✅ (impl new) | ✅ (functions) |
| Destructors | ❌ | ❌ | ✅ (Drop) | ✅ (GC) |
| Access modifiers | ❌ | ❌ | ✅ (pub) | ✅ (uppercase) |
| Generics | ✅ syntax only | ❌ | ✅ | ❌ |

**Kết luận: Vir entity = C struct + Rust syntax, KHÔNG có methods**

### 2.3 Token Support Đã Có Nhưng Chưa Dùng

Trong lexer (bootstrap):
```
TK_METHOD = 38    # ❌ Defined nhưng KHÔNG ĐƯỢC LEX
TK_CLASS  = 39    # ❌ Defined nhưng KHÔNG ĐƯỢC LEX
TK_HAS    = 47    # ❌ Unused
```

Parser comment tại `compiler.vri` L1298: `"obj.method(args)"` — nhưng **KHÔNG IMPLEMENT**, fallback thành name mangling: `obj.method(a, b)` → `obj_method(a, b)` (không inject `self`).

### 2.4 OOP Features Cần Thêm

#### A. Methods (impl blocks) — Priority: HIGH

```vir
# Syntax đề xuất
impl Point:
    func distance() -> int:
        return sqrt(self.x * self.x + self.y * self.y)
    end

    func translate(dx, dy):
        self.x = self.x + dx
        self.y = self.y + dy
    end
end

# Sử dụng
var p = Point{x: 3, y: 4}
var d = p.distance()       # → inject self = p, gọi Point_distance(p)
```

**Cần thay đổi:**
1. Parser: parse `impl EntityName: ... end` blocks
2. IR: inject hidden `self` parameter (first arg)
3. Name mangling: `Point_distance`, `Point_translate`
4. Dispatch: simple static lookup (no vtable cần thiết)
5. LOC estimate: ~400-500

#### B. Constructors — Priority: MEDIUM

```vir
impl Point:
    func new(x, y) -> Point:
        return Point{x: x, y: y}
    end
end

var p = Point.new(3, 4)
```

**Cần:** Parser + entity method registry. LOC: ~200-300

#### C. Inheritance — Priority: LOW

```vir
entity Shape:
    color
end

entity Circle extends Shape:
    radius
end

# Memory: [color (8B)] [radius (8B)] — parent fields first
```

**Cần:** Parser extend syntax, field offset adjustment, type hierarchy. LOC: ~800-1000

#### D. Traits/Interfaces — Priority: LOW (cần type checker)

```vir
trait Drawable:
    func draw()
end

impl Drawable for Circle:
    func draw():
        # ...
    end
end
```

**Cần:** Type checker infrastructure, interface satisfaction checking. LOC: ~1200-1500

### 2.5 Đề Xuất Roadmap

| Priority | Feature | Complexity | Phụ thuộc |
|----------|---------|-----------|-----------|
| 1 | Methods (impl blocks) | Medium | Entity system (✅ đã có) |
| 2 | Constructors | Low-Medium | Methods |
| 3 | Float support | Medium | Lexer + codegen |
| 4 | Inheritance | High | Methods + type system |
| 5 | Traits | Very High | Type checker + methods |

**Khuyến nghị:** Implement Methods trước (impl blocks + self injection) — đây là foundation cho mọi OOP feature khác và effort chỉ ~400-500 LOC, tuơng đương với Phase C.2 (Arrays).

---

**Tác giả:** Research Session 02/04/2026
