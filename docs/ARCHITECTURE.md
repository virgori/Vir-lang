# Vir – Architecture Specification

> **Quizz-Core Engine v1.2** – English standard keywords • Self-hosting compiler • Self-patching JIT
>
> **Updated:** 9/3/2026 – Phase 4 "The Purest Build" complete

---

## 1. Tầng Giao diện Ngôn ngữ (The Multilingual Frontend)

### 1.0. lib – English Standard Keywords (`src/lib/keywords.py`)

**Single Source of Truth** cho toàn bộ ngôn ngữ:

- **`TokenKind`** enum: 60+ token types chuẩn (FUNC_DEF, VAR_DECL, IF, ELSE, ELIF, LOOP, WHILE, FOR, BREAK, CONTINUE, RETURN, OP_ADD/SUB/MUL/DIV/MOD/POW, CMP_EQ/NE/GT/LT/GE/LE, LOGIC_AND/OR/NOT, PRINT, INPUT, types, system tokens, delimiters, literals)
- **`Keyword`** dataclass: `kind`, `english`, `aliases`, `category`, `arity`, `precedence`, `description`
- **`KeywordRegistry`** class: `by_kind(TokenKind)`, `by_english(str)`, `all_keywords()`, `categories()`
- **`LEGACY_TOKEN_MAP`**: Bảng ánh xạ TOKEN_* strings → TokenKind cho backward compatibility

```python
from src.lib.keywords import TokenKind, KeywordRegistry

reg = KeywordRegistry()
kw = reg.by_kind(TokenKind.OP_ADD)  # → Keyword(english="add", precedence=10, ...)
```

### 1.0.1. sublib – Native Language Adapters (`src/sublib/`)

Mỗi ngôn ngữ tự nhiên là một **SubLibAdapter** kế thừa từ `SubLibAdapter` ABC:

| Adapter | File | Phrases | Ví dụ |
|---------|------|---------|-------|
| Vietnamese 🇻🇳 | `sublib/vi.py` | ~100+ | "nếu"→IF, "cộng"→OP_ADD, "in ra"→PRINT |
| Chinese 🇨🇳 | `sublib/zh.py` | ~90+ | "如果"→IF, "加"→OP_ADD, "打印"→PRINT |
| Japanese 🇯🇵 | `sublib/ja.py` | ~90+ | "もし"→IF, "足す"→OP_ADD, "表示する"→PRINT |
| Korean 🇰🇷 | `sublib/ko.py` | ~70+ | "만약"→IF, "더하기"→OP_ADD, "출력"→PRINT |
| English 🇬🇧 | `sublib/en.py` | auto | "if"→IF, "add"→OP_ADD, "print"→PRINT |

**SubLibRegistry** quản lý toàn bộ adapters:

```python
from src.sublib.base import SubLibRegistry

print(SubLibRegistry.available())  # ['vi', 'zh', 'ja', 'ko', 'en']
adapter = SubLibRegistry.get("vi")
adapter.lookup("nếu")             # → TokenKind.IF
adapter.is_stop_word("thì")       # → True
```

### 1.1. N-Gram Tokenizer (`src/frontend/tokenizer/ngram_tokenizer.py`)

**Thuật toán Greedy Longest-Match:**

```
Input:  "Nếu máy rảnh, tính tổng A và B bằng thanh ghi."
         ↓ normalize ↓
        "nếu máy rảnh tính tổng a và b bằng thanh ghi"
         ↓ N-gram scan (n=max_ngram → n=1) ↓
        [TokenKind.CHECK_CPU, TokenKind.OP_ADD, TokenKind.IDENTIFIER("a"),
         TokenKind.IDENTIFIER("b"), TokenKind.TARGET_REGISTER]
```

1. **Chuẩn hóa:** lowercase, xóa dấu câu, nén khoảng trắng.
2. **Quét N-gram:** Từ trái→phải, thử cụm dài nhất trước (max_ngram từ SubLibAdapter).
3. **Ánh xạ:** Nếu match → `SubLibAdapter.lookup(phrase)` → `TokenKind`.
4. **Lọc nhiễu:** Bỏ stop-words qua `SubLibAdapter.is_stop_word()`.
5. **Fallback:** Số → `NumberToken`, chuỗi → `StringToken`, identifier → Token(IDENTIFIER).
6. **CJK support:** Regex hỗ trợ ký tự CJK trong identifiers.

Token mới dùng `TokenKind` enum thay vì string `ir_token` (có backward-compat property).

### 1.2. [Legacy] Sublib Mapping (`config/sublib_mapping.json`)

> ⚠️ **Deprecated** – Dùng `src/sublib/*.py` adapters thay thế.  
> `LegacySublibBridge` trong tokenizer cho phép đọc JSON cũ qua adapter interface.

Cấu trúc cũ:
```json
{
  "SUB_DEFINITION": {
    "tokens": ["ta có hàm", "tạo hàm", "định nghĩa"],
    "ir_token": "TOKEN_FUNC_DEF",
    "category": "definition"
  },
  ...
  "stop_words": ["thì", "là", "nhé", ...]
}
```

20+ nhóm Sub đã định nghĩa, bao gồm:
- **definition:** hàm, biến
- **control_flow:** if/else, loop, while, return
- **arithmetic:** cộng, trừ, nhân, chia
- **comparison:** bằng, lớn hơn, nhỏ hơn
- **io:** in ra, nhập vào
- **system:** vá mã, kiểm tra CPU, thanh ghi

### 1.3. Parser (`src/frontend/parser/parser.py`)

Recursive-descent parser tạo AST với các node types:
- `ProgramNode` → `FuncDefNode`, `VarDeclNode`, `IfNode`, `LoopNode`
- `WhileNode`, `ReturnNode`, `PrintNode`, `InputNode`
- `BinOpNode` (ADD/SUB/MUL/DIV), `CompareNode` (EQ/GT/LT)
- `CheckCPUNode`, `PatchPointNode` (Spec §3 integration)

---

## 2. Tầng Máy trừu tượng (The Virtual Machine – Q-IR)

### 2.1. Tập lệnh Q-IR (`src/ir/instructions/q_ir.py`)

Mô hình SSA (Static Single Assignment) tối giản – 18 opcodes:

| Opcode | Dạng | Mô tả |
|--------|------|-------|
| `Q_LOAD` | `dest, src\|imm` | Nạp dữ liệu |
| `Q_STORE` | `addr, src` | Ghi vào bộ nhớ |
| `Q_MOVE` | `dest, src` | Sao chép thanh ghi |
| `Q_ADD` | `dest, src1, src2` | Cộng |
| `Q_SUB` | `dest, src1, src2` | Trừ |
| `Q_MUL` | `dest, src1, src2` | Nhân |
| `Q_DIV` | `dest, src1, src2` | Chia |
| `Q_CMP_EQ` | `dest, src1, src2` | So sánh bằng |
| `Q_CMP_GT` | `dest, src1, src2` | So sánh lớn hơn |
| `Q_CMP_LT` | `dest, src1, src2` | So sánh nhỏ hơn |
| `Q_JUMP` | `label` | Nhảy không điều kiện |
| `Q_JUMP_IF` | `cond, label` | Nhảy nếu cond ≠ 0 |
| `Q_JUMP_IF_NOT` | `cond, label` | Nhảy nếu cond = 0 |
| `Q_CALL` | `label` | Gọi hàm |
| `Q_RET` | `src` | Trả về |
| `Q_PRINT` | `src` | In giá trị |
| `Q_INPUT` | `dest` | Nhập giá trị |
| `Q_PATCH_POINT` | `id` | **"Lỗ hổng"** cho Backend tự vá mã |

### 2.2. Thanh ghi ảo (`src/ir/registers/virtual_registers.py`)

- Không giới hạn: $R_0, R_1, \ldots, R_n$
- Cấp phát tuần tự, hỗ trợ đặt tên (lookup by name)
- Backend chịu trách nhiệm mapping xuống thanh ghi vật lý

### 2.3. IR Optimizer (`src/ir/optimizer/optimizer.py`)

- **Constant Folding:** $R_0 = 10, R_1 = 20, R_2 = R_0 + R_1 \Rightarrow R_2 = 30$
- **Dead Code Elimination:** Loại bỏ instructions có dest không được sử dụng

### 2.4. IR Builder (`src/ir/instructions/ir_builder.py`)

AST → QModule lowering. Tự động tạo `__main__` function nếu không có func def.

---

## 3. Tầng Self-Patching Backend

### 3.1. Register Pressure Monitor (`src/backend/monitor/pressure_monitor.py`)

```
CPUState = probe() →
  arch:                "arm64"
  total_gp_registers:  31
  estimated_free:      22        ← N_free
  cpu_load_percent:    12.3%
  mode:                HIGH_PERFORMANCE_REG  (vì 22 > threshold=8)
```

**Công thức N_free:**
$$N_{free} = \max(0, \lfloor (N_{total} - N_{reserved}) \times (1 - \frac{CPU\%}{100}) \rfloor)$$

Trong đó $N_{reserved} = 4$ (RSP, RBP + 2 OS-reserved).

### 3.2. Code Generator (`src/backend/codegen/codegen.py`)

**Multi-versioning** – mỗi Q_PATCH_POINT → 2 biến thể:

| Biến thể | Mô tả | Ví dụ x86_64 |
|-----------|-------|---------------|
| **Bản A (Safe)** | Stack-based: PUSH/POP | `5B 58 48 01 D8 50` |
| **Bản B (Fast)** | Register-direct | `48 01 D8` |

Hỗ trợ: x86_64 + ARM64 (AArch64).

### 3.3. Binary Patcher (`src/backend/patcher/binary_patcher.py`)

**Jump Table Indirection:**

```
JIT Memory Layout:
┌──────────────────────────────────────────┐
│ [JMP rel32 → Safe#1] [JMP rel32 → Safe#2] ...  │  ← Jump Table
├──────────────────────────────────────────┤
│ [Safe Code #1] [Fast Code #1]            │  ← Code Variants
│ [Safe Code #2] [Fast Code #2]            │
│ ...                                      │
└──────────────────────────────────────────┘
```

**Patching = ghi đè 4 bytes offset trong lệnh JMP:**
- Trước patch: `E9 xx xx xx xx` → Safe code
- Sau patch:   `E9 yy yy yy yy` → Fast code

---

## 4. Bảo mật & Tương thích

### 4.1. Bridge API (`src/runtime/bridge/bridge_api.py`)

| OS | API | Cơ chế |
|----|-----|--------|
| Linux | `mprotect()` | PROT_READ \| PROT_WRITE \| PROT_EXEC |
| macOS | `pthread_jit_write_protect_np()` | Toggle write(0) / execute(1) |
| Windows | `VirtualProtect()` | PAGE_EXECUTE_READWRITE |

### 4.2. Internal Signer (`src/security/signer/internal_signer.py`)

- **Thuật toán:** HMAC-SHA256 với Quizz-Core Key (32 bytes random per session)
- **Message format:** `"{patch_id}:{sha256(code)}:{nonce}"`
- **Xác minh:** So sánh HMAC + code hash trước mỗi lần execute
- Nếu hash không khớp → **ngắt chương trình** (chống virus can thiệp)

---

## 5. Runtime Life-cycle

```
            ┌─────────────┐
            │  Source.vir  │  "Nếu máy rảnh, tính tổng A và B"
            └──────┬──────┘
                   ↓
         ┌─────────────────┐
Phase 1  │  NGramTokenizer  │  → [TokenKind.CHECK_CPU, TokenKind.OP_ADD, ...]
         │  + SubLibAdapter │     (vi / zh / ja / ko / en)
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
         │     Parser       │  → AST (CheckCPUNode → BinOpNode)
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
Phase 2  │   IR Builder     │  → QModule: Q_PATCH_POINT + Q_ADD R2,R0,R1
         │   + Optimizer    │
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
         │   CodeGenerator  │  → CodeVariant(safe=stack, fast=register)
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
Phase 3  │   JIT Engine     │  → mmap(MAP_JIT) + Build Jump Table
         │   + Bridge API   │
         └────────┬────────┘
                  ↓
         ┌─────────────────┐
Phase 4  │ Evolution Loop   │  ← Background thread
         │  ┌─────────────┐ │
         │  │ Monitor CPU │ │  probe() → N_free > 8?
         │  └──────┬──────┘ │
         │         ↓        │
         │  ┌─────────────┐ │
         │  │ Patch JMP   │ │  JMP → Bản B (48 01 D8)
         │  │ + Sign code │ │  HMAC-SHA256 verify
         │  └─────────────┘ │
         └─────────────────┘
```

---

## Ví dụ cụ thể

**Input:** `Nếu máy rảnh, tính tổng A và B bằng thanh ghi.`

**Phase 1 – Tokens (Vietnamese adapter):**
| # | TokenKind | raw_text |
|---|-----------|----------|
| 1 | CHECK_CPU | "máy rảnh" |
| 2 | OP_ADD | "tính tổng" |
| 3 | IDENTIFIER | "a" |
| 4 | IDENTIFIER | "b" |
| 5 | TARGET_REGISTER | "thanh ghi" |

**Cùng chương trình bằng 中文 (Chinese adapter):**
| # | TokenKind | raw_text |
|---|-----------|----------|
| 1 | CHECK_CPU | "机器空闲" |
| 2 | OP_ADD | "加" |
| 3 | IDENTIFIER | "a" |
| 4 | IDENTIFIER | "b" |
| 5 | TARGET_REGISTER | "寄存器" |

**Phase 2 – Q-IR:**
```
; module main
func @__main__():
  Q_PATCH_POINT    ; PATCH_1: CHECK_CPU → dynamic patch
  Q_ADD R2, R0, R1 ; tính tổng a, b
```

**Phase 3 – Machine Code:**

| Bản A (Safe – Stack) | Bản B (Fast – Register) |
|---------------------|------------------------|
| `5B 58 48 01 D8 50 90` | `48 01 D8 90` |
| POP RBX; POP RAX; ADD RAX,RBX; PUSH RAX; NOP | ADD RAX,RBX; NOP |

**Phase 4 – Runtime:**
- CPU load 12% → $N_{free} = 22 > 8$ → **Patch to Fast!**
- JMP offset được ghi đè → trỏ sang `48 01 D8` (ADD RAX,RBX)

---

## 6. Native Core – Lớp Giao tiếp Máy (C/ASM)

> Toàn bộ lớp này viết bằng C11 + Assembly (ARM64/x86_64).
> Không dùng Python – mapping bằng mã máy.

### 6.1. Constraints – Hệ thống Kiểu Máy (`core/include/constraints.h`, `core/src/constraints.c`)

**vir_type_t** – 7 kiểu dữ liệu cơ bản:

| Kiểu | Mã | Kích thước | Lớp |
|------|----|-----------|------|
| `VIR_TYPE_VOID` | 0x00 | 0B | — |
| `VIR_TYPE_I8` | 0x01 | 1B | integer |
| `VIR_TYPE_I32` | 0x02 | 4B | integer |
| `VIR_TYPE_I64` | 0x03 | 8B | integer (default) |
| `VIR_TYPE_F32` | 0x04 | 4B | float |
| `VIR_TYPE_F64` | 0x05 | 8B | float |
| `VIR_TYPE_PTR` | 0x06 | 8B | pointer |

**op_constraint_t** – Ràng buộc từng opcode:
- Mỗi Q-IR opcode có bảng: số operand, kiểu dest, kiểu src[0..2]
- `vir_op_constraint(opcode)` → tra bảng O(n) scan
- `vir_constraint_check(opcode, dest, src1, src2)` → 0 nếu hợp lệ

### 6.2. Intrinsics – Hàm Dựng sẵn (`core/include/intrinsics.h`, `core/src/intrinsics.c`)

9 intrinsics tự cài đặt bằng C, JIT code gọi trực tiếp qua ABI:

| ID | Tên | C Function | Signature |
|----|-----|-----------|-----------|
| 0 | PRINT | `vir_builtin_print_i64` | `i64 → i64` |
| 1 | PRINT_STR | `vir_builtin_print_str` | `ptr → i64` |
| 2 | INPUT | `vir_builtin_input_i64` | `() → i64` |
| 3 | INPUT_STR | `vir_builtin_input_str` | `() → ptr` |
| 4 | CPU_LOAD | `vir_builtin_cpu_load` | `() → i64` |
| 5 | SLEEP_MS | `vir_builtin_sleep_ms` | `i64 → void` |
| 6 | ALLOC | `vir_builtin_alloc` | `i64 → ptr` |
| 7 | FREE | `vir_builtin_free` | `ptr → void` |
| 8 | STRLEN | `vir_builtin_strlen` | `ptr → i64` |

**intrinsic_table_t** singleton – lazy init, `vir_intrinsic_addr(id)` trả địa chỉ thực cho codegen nhúng vào CALL.

### 6.3. Bridge API Mở rộng (`core/include/bridge.h`, `core/src/bridge.c`)

Bổ sung cho Bridge API gốc:

- **`bridge_flush_icache(addr, size)`** – macOS: `sys_icache_invalidate()`, Linux ARM64: `DC CVAU`/`IC IVAU`/`DSB ISH`/`ISB`, x86_64: `MFENCE`
- **`bridge_alloc_executable(size)`** – cấp phát page-aligned, dùng `bridge_jit_alloc` (MAP_JIT trên macOS)
- **`bridge_make_executable(addr, size)`** – macOS ARM64: `pthread_jit_write_protect_np(1)` + icache flush; Linux: `mprotect(RX)`
- **`bridge_make_writable(addr, size)`** – macOS ARM64: `pthread_jit_write_protect_np(0)`; Linux: `mprotect(RW)`

**abi_info_t** – Bảng ABI cho từng kiến trúc:

| ABI | Return | Arg0 | Arg1 | Arg2 | Arg3 | Arg4 | Arg5 |
|-----|--------|------|------|------|------|------|------|
| System V x86_64 | RAX | RDI | RSI | RDX | RCX | R8 | R9 |
| AAPCS64 (ARM64) | X0 | X0 | X1 | X2 | X3 | X4 | X5 |

### 6.4. JIT Bridge Singleton (`core/include/jit_bridge.h`, `core/src/jit_bridge.c`)

Bộ điều khiển trung tâm cho JIT:

```
jit_bridge_t (singleton, 1MB mmap region)
├── callbacks[64]        – registry native functions
├── callback_table[64]   – void* array cho indirect CALL
├── blocks[256]          – code blocks với HMAC-SHA256
├── patcher_t            – jump table patching
└── signer_t             – integrity verification
```

**Machine-Code Call Thunks:**

- **x86_64:** `48 B8 <8 bytes addr>; FF D0` = MOV RAX, imm64; CALL RAX (12 bytes)
- **ARM64:** `MOVZ X16, #low16; MOVK X16, #mid16, LSL#16; MOVK ...; BLR X16` (12–20 bytes)

**Lifecycle:** `jit_bridge_init()` → `register_intrinsics()` → `emit_code()` → `finalise()` → `get_entry()` → execute

### 6.5. IR Lowering + Register Allocation (`core/include/ir_lower.h`, `core/src/ir_lower.c`)

AST → Q-IR lowering hoàn toàn bằng C:

**ast_type_t** – 21 node types mirror Python parser:
`PROGRAM`, `FUNC_DEF`, `VAR_DECL`, `CONST_DECL`, `IF`, `LOOP`, `WHILE`, `RETURN`, `PRINT`, `INPUT`, `BINOP`, `COMPARE`, `LITERAL_INT/FLOAT/STR`, `IDENTIFIER`, `CALL`, `CHECK_CPU`, `PATCH_POINT`, `ASSIGN`, `BLOCK`

**Lowering Pipeline:**
1. `lower_init()` → khởi tạo module + vreg allocator + symbol table
2. `lower_program()` → duyệt AST_PROGRAM children
3. `lower_func_def()` → tạo q_function_t, đăng ký params, lower body
4. `lower_expr()` → recursive: LITERAL→Q_LOAD, IDENTIFIER→sym_lookup, BINOP→Q_ADD/SUB/MUL/DIV, COMPARE→Q_CMP_*
5. `lower_stmt()` → IF→Q_JUMP_IF_NOT, LOOP→counter+Q_CMP_LT+Q_JUMP, WHILE→Q_JUMP_IF_NOT, RETURN→Q_RET, PRINT→Q_PRINT

**Linear-Scan Register Allocation:**
1. `lower_compute_liveness()` → quét instructions tìm [start, end] cho mỗi vreg
2. `lower_regalloc_linear_scan(num_phys_regs)`:
   - Sort intervals by start
   - Maintain active set, expire finished intervals
   - Assign physical registers; spill khi hết regs
3. `lower_get_phys_reg(vreg)` → tra bảng kết quả

### 6.6. Redundancy Patching – Rollback (`jit_bridge.h/c`)

Cơ chế **Dual-Emit** cho phép lưu cả Safe (Bản A) và Fast (Bản B) code trong cùng một vùng JIT region, với khả năng chuyển đổi tức thì giữa hai phiên bản.

**Memory Layout:**
```
JIT Region:
  [safe_code ...]  [fast_code ...]
  ^                ^
  block.safe_offset  block.fast_offset
  block.offset → active variant
```

**jit_block_t** tracking fields:
- `safe_offset` / `safe_size` – vị trí Bản A (Safe code)
- `fast_offset` / `fast_size` – vị trí Bản B (Fast code)
- `is_fast` – 0 = safe, 1 = fast (biến trạng thái)
- `exec_count` – số lần block được thực thi
- `fast_fail_count` – số lỗi phát hiện khi chạy fast code

**API:**
1. `jit_bridge_emit_dual(jb, id, safe, safe_len, fast, fast_len)` – ghi cả hai biến thể, bắt đầu ở Safe, ký HMAC safe code
2. `jit_bridge_patch_to_fast(jb, id)` – chuyển `offset` → `fast_offset`, ký lại HMAC, flush icache
3. `jit_bridge_rollback(jb, id)` – chuyển `offset` → `safe_offset`, ký lại HMAC, flush icache. Nếu Fast code gây lỗi hoặc không cải thiện hiệu suất → gọi rollback ngay lập tức
4. `jit_bridge_report_fault(jb, id, max_faults)` – tăng `fast_fail_count`; nếu vượt `max_faults` → tự động rollback, return 1
5. `jit_bridge_is_fast(jb, id)` – truy vấn trạng thái hiện tại

**Flow trong Evolution Loop (Phase 4):**
```
emit_dual(safe, fast)  →  patch_to_fast()  →  chạy benchmark
                                               ├── perf tốt hơn → giữ fast
                                               └── perf xấu / lỗi → report_fault()
                                                                      └── vượt threshold → rollback() tự động
```

### 6.7. Tail-Call Optimization (`ir_lower.h/c`)

Pass **post-lowering** quét body hàm, tìm mẫu `Q_CALL + Q_RET` liền kề ở vị trí đuôi (tail position) và thay thế bằng `Q_JUMP + Q_NOP` — tiết kiệm stack frame, chuyển đệ quy thành vòng lặp.

**Pattern:**
```
TRƯỚC:   Q_CALL  @target          SAU:    Q_JUMP  @target
         Q_RET   [retval]                 Q_NOP
```

**API:** `lower_tco_pass(q_function_t *func)` → trả về số tail call đã tối ưu

**Quy tắc:**
- Chỉ tối ưu khi `Q_CALL` ngay trước `Q_RET` (tail position)
- `Q_RET` bị NOP-out để giữ nguyên chỉ số instruction (label references)
- Hỗ trợ nhiều tail call trong cùng 1 hàm (ví dụ: mỗi nhánh if/else kết thúc bằng tail call)

---

## 7. Native C Lexer (`lexer.h/c`)

Tokenizer thuần C xử lý mã nguồn UTF-8 (Tiếng Việt + English).

### 7.1. Token Types (`vir_tok_t`)

55 loại token: EOF, ERROR, INT, FLOAT, STRING, IDENT, FUNC, VAR, CONST, IF, ELSE, ELIF, LOOP, WHILE, FOR, BREAK, CONTINUE, RETURN, THEN, END, PRINT, INPUT, CHECK_CPU, PATCH, operators (+−×/%), comparisons (== != > < >= <=), logical (AND OR NOT), delimiters, TRUE/FALSE/NONE.

### 7.2. Vietnamese Keyword Support

| Loại | Số lượng | Ví dụ |
|------|----------|-------|
| Single-word VN | 20 | `hàm`→FUNC, `biến`→VAR, `nếu`→IF, `thì`→THEN, `hết`→END |
| Multi-word VN | 19 | `trả về`→RETURN, `in ra`→PRINT, `ngược lại`→ELSE |
| English | 24 | `func`, `var`, `if`, `then`, `end`, `print` |
| Stop words | 27 | `là`, `nhé`, `giúp`, `ơi` (filtered silently) |

**Thuật toán:** Greedy multi-word lookahead với save/restore vị trí. Đọc 1 word → thử match 2-3 word → fallback single → stop word → IDENT.

### 7.3. Block Delimiters

```
hàm chính() thì      ← THEN mở block
  biến x = 42
hết                   ← END đóng block
```

---

## 8. Native C Parser (`parser.h/c`)

Parser đệ quy giảm (recursive-descent) tạo `ast_node_t` tương thích với `ir_lower`.

### 8.1. Grammar

```
program    → (func_def | statement)* EOF
func_def   → FUNC IDENT '(' params ')' THEN block END
block      → statement*
statement  → var_decl | if_stmt | loop_stmt | while_stmt | return_stmt | print_stmt | assign_or_expr
if_stmt    → IF expr THEN block (ELIF expr THEN block)* (ELSE block)? END
while_stmt → WHILE expr THEN block END
loop_stmt  → LOOP expr THEN block END
expression → or_expr
or_expr    → and_expr ('or' and_expr)*
and_expr   → compare ('and' compare)*
compare    → addition (('==' | '!=' | '>' | '<' | '>=' | '<=') addition)?
addition   → mult (('+' | '-') mult)*
mult       → unary (('*' | '/' | '%') unary)*
unary      → ('-' | 'not') unary | primary
primary    → INT | FLOAT | STRING | TRUE | FALSE | NONE | IDENT ['(' args ')'] | '(' expr ')'
```

### 8.2. AST Output

Parser tạo cây `ast_node_t` (from `ir_lower.h`) với cùng cấu trúc mà `lower_program()` mong đợi:
- `AST_FUNC_DEF`: `name` = tên hàm, children = [IDENTIFIER params..., BLOCK body]
- `AST_IF`: children = [condition, then_block, else_block?]
- `AST_WHILE`: children = [condition, body_block]
- `AST_BINOP`: `op` = OP_ADD/SUB/..., children = [left, right]

---

## 9. Codegen Full (`codegen_emit_full`)

Mở rộng codegen để hỗ trợ **toàn bộ** Q-IR opcodes:

### 9.1. Opcodes mới

| Opcode | ARM64 | x86_64 |
|--------|-------|--------|
| Q_JUMP | B imm26 | JMP rel32 |
| Q_JUMP_IF | CMP+B.NE imm19 | TEST+JNE rel32 |
| Q_JUMP_IF_NOT | CMP+B.EQ imm19 | TEST+JE rel32 |
| Q_CMP_GE | CMP+CSET GE | CMP+SETGE |
| Q_CMP_LE | CMP+CSET LE | CMP+SETLE |
| Q_MOD | SDIV+MUL+SUB | CQO+IDIV (RDX) |
| Q_PRINT | Save regs + BLR X16 | Save regs + CALL RAX |
| Q_CALL | BL imm26 | CALL rel32 |

### 9.2. Label Back-Patching

Single-pass với fixup table:
1. Gặp Q_LABEL → ghi nhận `label_id → code_offset`
2. Gặp Q_JUMP* → emit placeholder, thêm fixup entry
3. Sau cùng: duyệt fixup → patch branch offset vào mã máy

### 9.3. Register Save/Restore

Quanh mỗi lời gọi hàm (PRINT, CALL), codegen phải save/restore caller-saved registers:
- ARM64: STP/LDP X0-X15 (8 cặp × 16 bytes = 128 bytes)
- x86_64: PUSH/POP RAX,RCX,RDX,RSI,RDI

Nếu hàm có CALL/PRINT → emit prologue (STP FP,LR / PUSH RBP) và epilogue (LDP FP,LR / POP RBP) + RET.

---

## 10. Blacklist – PERMANENT_SAFE (`jit_bridge`)

Cơ chế ngăn block bị rollback quá nhiều lần:

```
Threshold = 3 (configurable)
┌────────────────────────────────────────────────┐
│ patch_to_fast → rollback #1                    │
│ patch_to_fast → rollback #2                    │
│ patch_to_fast → rollback #3 → PERMANENT_SAFE   │
│ patch_to_fast → returns -2 (refused)            │
└────────────────────────────────────────────────┘
```

**API:**
- `jit_bridge_set_blacklist_threshold(jb, N)` — đặt ngưỡng (0 = tắt)
- `jit_bridge_is_blacklisted(jb, block_id)` — truy vấn trạng thái
- `jit_bridge_patch_to_fast()` → trả `-2` nếu blacklisted
- `jit_bridge_rollback()` → tự động set `permanent_safe = 1` khi đạt threshold

---

## 11. Vir-in-Vir Compiler (`stdlib/vir/compiler/`)

> Phase 4 — "The Purest Build" (9/3/2026)
> All 4 core C compiler modules translated to pure Vir.
> 7,183 LOC C → 5,335 LOC Vir.

### 11.1. Module Overview

| Module | Source | Lines | Translated From |
|--------|--------|-------|-----------------|
| `lexer.vir` | `stdlib/vir/compiler/lexer.vir` | 905 | `core/src/lexer.c` (807L) |
| `parser.vir` | `stdlib/vir/compiler/parser.vir` | 1,319 | `core/src/parser.c` (1,164L) |
| `ir_optimizer.vir` | `stdlib/vir/compiler/ir_optimizer.vir` | 1,448 | `core/src/ir_lower.c` (1,804L) |
| `codegen.vir` | `stdlib/vir/compiler/codegen.vir` | 1,663 | `core/src/codegen.c` (3,408L) |

### 11.2. Compiler Pipeline (Vir-native)

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│ .vir src │───→│ lexer.vir    │───→│ parser.vir   │───→│ir_optimizer.vir│───→│ codegen.vir  │
│ (UTF-8)  │    │ (tokenizer)  │    │ (AST builder)│    │ (Q-IR + alloc) │    │ (machine code)│
└──────────┘    └──────────────┘    └──────────────┘    └────────────────┘    └──────────────┘
  English         TokType enum       AstNode tree        QModule/QFunction     CodeBuf bytes
  keywords        (90+ types)        (50+ node types)    (95+ opcodes)         (x86_64 + ARM64)
```

### 11.3. lexer.vir — Tokenizer

- `TokType` enum: 90+ token types (keywords, operators, literals, delimiters)
- `Token` entity: `type`, `start`, `length`, `line`
- `Lexer` entity: source buffer, cursor, line tracking
- Greedy longest-match: numbers, strings, identifiers, multi-char operators
- Keyword lookup table: 30+ English keywords → `TokType`
- `tokenize(source) -> [Token]` entry point

### 11.4. parser.vir — Recursive Descent Parser

- `AstType` enum: 50+ node types (Program, FuncDef, VarDecl, If, Loop, While, For, Return, BinOp, Compare, Call, etc.)
- `OpType` enum: arithmetic, comparison, logical operators
- `AstNode` entity: type, op, children[], value, name
- Precedence climbing for expressions (6 levels: or → and → compare → add → mul → unary)
- `parse_program(tokens) -> AstNode` entry point

### 11.5. ir_optimizer.vir — AST→Q-IR Lowering + Register Allocation

- `QOp` enum: 95+ Q-IR opcodes (Load, Store, Move, Add, Sub, Mul, Div, Mod, CmpEq/Gt/Lt/Ge/Le/Ne, Jump/JumpIf/JumpIfNot, Call, Ret, Print, Input, And/Or/Xor/Shl/Shr/Not, FAdd/FSub/FMul/FDiv, VAdd/VSub/VMul/VDiv, Label, Nop, etc.)
- `QOperand` / `QInstr` / `QFunction` / `QModule` entities
- `SymTable` for variable/function symbol resolution
- `lower_expr()` / `lower_stmt()` / `lower_func_def()` / `lower_program()` — recursive lowering
- `compute_liveness()` → interval [start, end] per vreg
- `regalloc_linear_scan(num_phys)` — linear-scan register allocator with spill
- `tco_pass()` — tail-call optimization (Q_CALL+Q_RET → Q_JUMP+Q_NOP)

### 11.6. codegen.vir — Machine Code Emitter

- `TargetArch` enum: X86_64, ARM64 + `detect_arch()` for host auto-detection
- `CodeBuf` entity: growable byte buffer with `emit_byte()`, `emit32()`, `emit64()`, `patch32()`
- **x86_64 encoding:** REX.W prefix, ModRM byte, all ALU (add/sub/imul/idiv/cqo), cmp+setcc, branches (jmp/je/jne/call/ret), bitwise (and/or/xor/shl/sar), push/pop, syscall
- **AVX SIMD:** VEX-prefix encoding, vaddps/vsubps/vmulps/vdivps/vminps/vmaxps, vmovaps load/store, vbroadcastss, vhaddps
- **ARM64 encoding:** data-processing (add/sub/mul/sdiv), movz/movk immediate loading, cmp+cset, branches (b/beq/bne/bl), stp/ldp stack ops, ldr/str memory, bitwise, svc, blr
- **NEON SIMD:** ld1/st1 4s, add/sub/mul 4s, fadd/fmul/fdiv/fmla 4s, smin/smax 4s, addv/dup/tbl
- `PatchState` entity: label/fixup tracking, `backpatch_x86()` / `backpatch_arm64()`
- `emit_fast_x86(instrs, count)` / `emit_fast_arm64(instrs, count)` — full opcode dispatch
- `codegen_emit(instrs, count, arch)` / `codegen_emit_for_host(instrs, count)` — entry points

### 11.7. High-Level Codegen (`stdlib/vir/codegen/`)

Complementary assembly-text emitters with optimization grading:

| File | Lines | Purpose |
|------|-------|---------|
| `arm64.vir` | 510 | ARM64 assembly text generation (Grade S/A/B ranking) |
| `x86_64.vir` | 463 | x86_64 assembly text generation |
| `emitter.vir` | 262 | Generic emitter interface |
| `binary.vir` | 490 | ELF/Mach-O binary format output |
| `linker.vir` | 419 | Self-hosting linker |

---

## 12. CLI Driver (`main.c`)

Binary `vir` thuần C, **không cần Python runtime**.

### 12.1. Commands

| Command | Pipeline |
|---------|----------|
| `vir run <file>` | lex → parse → lower → TCO → VM interpret |
| `vir jit <file>` | lex → parse → lower → TCO → codegen → JIT execute |
| `vir dump <file>` | lex → parse → lower → Q-IR text |
| `vir tokens <file>` | lex → token stream |

### 12.2. Full Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ .vir src │───→│ C Lexer  │───→│ C Parser │───→│ir_lower │───→│ VM / JIT │
│ (UTF-8)  │    │ (lexer.c)│    │(parser.c)│    │(ir_low.c)│   │          │
└──────────┘    └──────────┘    └──────────┘    └─────────┘    └──────────┘
  Vietnamese      vir_token_t     ast_node_t      q_module_t     int64_t
  + English       (55 types)      (15 types)      (Q-IR ops)     result
```

### 12.3. Dual Language Example

```
# English                    # Vietnamese
func main() then             hàm chính() thì
  var x = 10                   biến x = 10
  var y = 20                   biến y = 20
  print x + y                  in ra x + y
  return x + y                 trả về x + y
end                           hết
```

Cả hai đều biên dịch → cùng Q-IR → cùng kết quả.
