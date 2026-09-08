# Vir – Architecture Specification (Đặc tả Kiến trúc Vir v2.0)

> **Phiên bản:** 2.0 (Self-Hosted / Production)  
> **Cập nhật:** 2026-09  
> **Chuẩn ngôn ngữ:** Vir Language Specification v2.0 (§1.2, §26, §29, §30)  
> **Trạng thái:** Tự lưu trữ hoàn toàn (Self-Hosted Sovereign Compiler) — Zero Python, Zero C shims, Zero libc, Zero External Linker.  
> **Bản tiếng Anh (English Version):** [ARCHITECTURE.md](ARCHITECTURE.md) | [ARCHITECTURE_en.md](ARCHITECTURE_en.md)
> **Pipeline chuẩn tắc:** `Source (.vri) → Lexer / Parser → AST → Semantic Analysis (10 Passes) → HIR/MIR (CFG + SSA) → MIR Opts → LIR → RegAlloc (Chaitin-Briggs + George-Appel IRC) → Direct Codegen → Mach-O / ELF / WASM`

---

## 0. Tổng quan Kiến trúc & Nguyên tắc Cốt lõi

Vir là ngôn ngữ lập trình hệ thống và AI-native hiệu năng cao, được thiết kế để biên dịch trực tiếp thành mã máy nguyên thủy (bare-metal/native code) mà không phụ thuộc vào bất kỳ hạ tầng runtime hay bộ công cụ liên kết ngoài nào.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        KIẾN TRÚC TỔNG THỂ VIR v2.0                            │
└───────────────────────────────────────────────────────────────────────────────┘
                                       │
    Mã nguồn (.vri)                    │ [Cú pháp tiếng Anh chuẩn tắc, Spec v2.0]
    (UTF-8 Source)                     ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 1: FRONTEND                                                            │
 │   • Lexer thuần Vir (stdlib/vir/compiler/lexer.vri)                         │
 │   • Parser đệ quy giảm AST (stdlib/vir/compiler/parser.vri)                 │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    AST Cây cú pháp trừu tượng        │ [AstNode strongly typed]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 2: PHÂN TÍCH NGỮ NGHĨA — 10 PASSES (compiler/semantic.vri)             │
 │   • Module & Import   • Symbol Table    • Name Resolution   • Type Resolve  │
 │   • Type Inference    • Type Checking   • Control Flow CFA  • Borrow Check  │
 │   • Constant Folding  • Diagnostics Engine                                  │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    AST hợp lệ ngữ nghĩa               │ [ast_to_mir.vri / ast_to_hir.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 3: TRUNG GIAN TRUNG CẤP — MIR / SSA (compiler/mir*.vri)                 │
 │   • Control Flow Graph (CFG) & Dominator Trees (mir_cfg.vri)                │
 │   • Static Single Assignment (SSA) chèn Phi & Rename (mir_ssa.vri)          │
 │   • MIR Optimization Pipeline: Constant Fold, DCE, CSE, Inlining, Loop LICM │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    MIR SSA đã tối ưu                  │ [lir_lower.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 4: TRUNG GIAN HẠ TẦNG — LIR & REGALLOC (compiler/lir*.vri)             │
 │   • Lowering sang LIR virtual registers & stack slots                       │
 │   • Pre-RA Target Optimization Hook (opt_backend.vri)                       │
 │   • Liveness Analysis & Interference Graph (lir_liveness / interference)    │
 │   • Chaitin-Briggs Graph Coloring Allocator & Spill Manager                 │
 │   • George-Appel Iterated Register Coalescing (IRC triệt tiêu Mov)          │
 │   • Post-RA Target Optimization Hook                                        │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    LIR với thanh ghi vật lý           │ [lir_codegen*.vri / lir_to_mc.vri]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 5: SINH MÃ MÁY & LIÊN KẾT TRỰC TIẾP (compiler/codegen* / binary)        │
 │   • Backend Codegen: ARM64 (NEON), x86_64 (AVX), WebAssembly, RISC-V 64     │
 │   • Internal Linker: Direct Mach-O 64-bit, Direct ELF 64-bit, WASM module   │
 │   • Zero `ld64`, Zero `ld.lld`, Zero `gcc/clang` dependency                 │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       │
    Native Executable File             │ [Mach-O ARM64 / ELF x86_64 / WASM]
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 6: RUNTIME HỆ THỐNG THUẦN VIR (stdlib/vir/rt/)                          │
 │   • Syscall Layer (macOS BSD 0x2000000 / Linux POSIX) — Zero libc           │
 │   • Memory: Direct mmap page allocator, bump arena, free-list heap          │
 │   • String & Vector runtime, direct I/O                                     │
 └─────────────────────────────────────────────────────────────────────────────┘
```

### 0.1. Nguyên tắc thiết kế thực tế

1. **Chủ quyền Độc lập (Language Sovereignty):**
   - Trình biên dịch Vir (`stdlib/vir/compiler/virc.vri`) tự biên dịch chính nó (Self-Hosting 100%).
   - Hoàn toàn loại bỏ mã nguồn Python nguyên mẫu giai đoạn sơ khai (`src/*`), loại bỏ các C runtime shims (`core/*`) trong quá trình vận hành chính thức.
   - Nhắm đến mô hình liên kết trực tiếp: sinh trực tiếp nhị phân thực thi chuẩn Mach-O (macOS) và ELF (Linux) mà không cần linker ngoài.

2. **Loại bỏ hoàn toàn SubLib Adapter Ngôn ngữ Tự nhiên:**
   - **Thực tế:** Cú pháp của Vir được chuẩn hoá **duy nhất theo bộ từ khoá tiếng Anh** quy định tại Đặc tả Spec v2.0 §1.2 & §29 (`func`, `var`, `let`, `const`, `if`, `when`, `for`, `loop`, `case`, `out`, `do`, `end`, `end.`, v.v.).
   - Toàn bộ các adapter ngôn ngữ tự nhiên trước đây (`src/sublib/vi.py`, `zh.py`, `ja.py`, `ko.py`), các bộ tách từ N-Gram thử nghiệm (`ngram_tokenizer.py`), và bảng ánh xạ đa ngữ (`config/sublib_mapping.json`) **đã bị bãi bỏ hoàn toàn**.
   - Bộ Lexer của Vir là lexer đơn ngữ chuẩn, quét trực tiếp chuỗi ký tự UTF-8, không phân nhánh N-gram và không map từ khóa địa phương. Điều này bảo đảm tính nhất quán toán học, tốc độ phân tích siêu nhanh và loại bỏ hoàn toàn các nhập nhằng ngữ nghĩa.

3. **Cú pháp Khối Nghiêm ngặt (Block Structure Law):**
   - **Định nghĩa / Khai báo** (`func`, `entity`, `enum`, `register`, `mold`, `method`, v.v.) → bắt buộc đóng bằng **`end.`**
   - **Luồng điều khiển / Câu lệnh** (`if`, `when`, `for`, `loop`, `case`, `try`, `arena`, v.v.) → bắt buộc đóng bằng **`end`**
   - **Mở khối:**
     - Có biểu thức trước thân khối → sử dụng **`do`** hoặc **`loop`** (`if cond do`, `when cond loop`, `for i in 0..10 do`).
     - Không có biểu thức trước thân khối → sử dụng dấu hai chấm **`:`** (`func main:`, `try:`, `arena:`).
     - Mệnh đề tiếp nối (`else`, `eif`, `ensure`, `revert`) **không** dùng dấu `:`.

4. **Hệ thống AI / ML Tích hợp Cấp Ngôn ngữ (Spec v2.0 §26):**
   - Hạng tử `tensor<T>[Dimensions...]` là kiểu dữ liệu hạng nhất (first-class type).
   - Toán tử nhân ma trận MatMul `**` và FMA `><` được hỗ trợ ở cấp độ phần cứng thông qua SIMD NEON / AVX.
   - Hỗ trợ khối phân tách tính toán: `infer:` (tối ưu suy luận không gradient) và `train:` (tự động theo dõi đồ thị tính toán).
   - Tích hợp vi phân tự động (Tape Autodiff) với `backward()` và lượng tử hóa đa bit `quantize(t, bits)`.

---

## 1. Tầng Frontend (Lexer & Parser Thuần Vir)

Tầng Frontend đọc mã nguồn `.vri` (định dạng UTF-8) và chuyển đổi thành cây cú pháp trừu tượng AST có kiểu dữ liệu mạnh mẽ. Toàn bộ tầng này được viết bằng 100% mã nguồn Vir tự lưu trữ tại `stdlib/vir/compiler/`.

### 1.1. Lexer chuẩn tắc (`stdlib/vir/compiler/lexer.vri`)

Lexer thực hiện quét luồng byte UTF-8 theo thuật toán Greedy Longest-Match một chiều, không backtracking, không N-gram mapping.

- **Dữ liệu cấu trúc:**
  - `Token`: cấu trúc gồm `type` (`TokType`), `start` (vị trí bắt đầu), `length` (độ dài), `line` (dòng tương ứng trong mã nguồn).
  - `Lexer`: con trỏ duyệt, bộ đệm nguồn UTF-8, trạng thái theo dõi dòng/cột.
- **Tập Token Chuẩn (`TokType` - 90+ loại):**
  - **Keywords chính:** `func`, `var`, `let`, `const`, `if`, `eif`, `else`, `when`, `loop`, `for`, `in`, `case`, `out`, `skip`, `break`, `try`, `ensure`, `revert`, `arena`, `isolate`, `entity`, `enum`, `packed`, `register`, `mold`, `method`.
  - **AI/ML & Toán tử cấp cao:** `tensor`, `infer`, `train`, `quantize`, MatMul `**`, FMA `><`, Power `^`, Remainder `mod`.
  - **Logic & Bitwise chuẩn Vir v2.0:** Logic AND `&`, Logic OR `||`, Logic NOT `!`; Bitwise AND `and`, Bitwise OR `or`, Bitwise XOR `xor`, dịch bit `shl`, `shr`, `>>`.
  - **Toán tử so sánh & gán:** `==`, `!=`, `<`, `>`, `<=`, `>=`, Pattern Match `:~`, Exact Equal `?=`, gán `=`.
  - **Dấu phân cách & Literal:** Dấu hai chấm `:`, dấu chấm `.`, dấu phẩy `,`, dấu chấm phẩy `;`, ngoặc đơn `()`, ngoặc vuông `[]`, Integer, Float, String, Boolean (`true`, `false`), Null literal (`none`).

### 1.2. Parser đệ quy giảm (`stdlib/vir/compiler/parser.vri`)

Parser chuyển đổi danh sách các `Token` thành cây cú pháp trừu tượng `AstNode`.

- **Cấu trúc `AstNode`:**
  - `type`: Thuộc enum `AstType` (Program, FuncDef, VarDecl, If, When, For, Loop, Case, Try, Return/Out, BinOp, UnaryOp, TensorDecl, InferBlock, TrainBlock, v.v.).
  - `op`: Mã toán tử nếu là node biểu thức toán học / logic / AI.
  - `name`: Tên định danh (tên hàm, tên biến, tên kiểu, tên trường).
  - `value`: Giá trị tức thời (imm) cho literal nguyên, thực, chuỗi.
  - `children`: Vector các node con (`vec_rt`).
- **Leo bậc ưu tiên toán tử (Precedence Climbing):**
  Parser thực hiện phân tích biểu thức theo đúng thứ hạng toán tử nghiêm ngặt của Vir Spec v2.0 §30:
  1. Member Access (`.`), Safe Nav (`?.`), Swizzle (`~`), Atomic (`!!`).
  2. Prefix unary (`!`, `-`), Power (`^` kết hợp phải).
  3. Tensor MatMul (`**`), Tensor FMA (`><`), Nhân/Chia (`*`, `/`), Phép chia lấy dư (`mod`).
  4. Casts (`as`), Dịch bit (`shl`, `shr`, `>>`), Cộng/Trừ (`+`, `-`).
  5. So sánh tương đối (`<`, `>`, `<=`, `>=`), So sánh bằng (`==`, `!=`, `?=`), Pattern match (`:~`).
  6. Logic AND (`&`), Bitwise AND (`and`).
  7. Logic OR (`||`), Bitwise OR (`or`), Bitwise XOR (`xor`).
  8. Phép gán (`=`, kết hợp phải).

---

## 2. Tầng Phân tích Ngữ nghĩa (Semantic Analysis — 10 Passes)

Nằm tại `stdlib/vir/compiler/semantic.vri`, bộ điều phối `semantic_run` điều hành 10 pass phân tích độc lập theo kiến trúc đa tầng. Nếu phát hiện bất kỳ lỗi ngữ nghĩa nào (`error_count > 0`), pipeline sẽ dừng lại ngay lập tức và phát thông báo chuẩn đoán, ngăn chặn sinh mã sai lệch.

```
       AST từ Parser
             │
             ▼
    ┌──────────────────┐
    │  Pass 1: MODULES │ ─── Thu thập các module, nạp gói phụ thuộc, resolve `include` / `import`
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 2: SYMBOLS │ ─── Khởi tạo SymbolTable, đăng ký hàm, entity, enum, hằng số toàn cục
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 3: NAMES   │ ─── Phân giải tên biến trong ScopeTree, kiểm tra biến chưa khai báo
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 4: TYPES   │ ─── Nạp TypeTable, xây dựng chữ ký kiểu dữ liệu, entity fields
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 5: INFER   │ ─── Suy luận kiểu tự động cho `var` / `let` không gắn type annotation
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 6: CHK-TYP │ ─── Kiểm tra tương thích kiểu, ép kiểu tường minh, tensor dimension check
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 7: CFA     │ ─── Control Flow Analysis: kiểm tra đường trả về `out`, rẽ nhánh đầy đủ
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 8: BORROW  │ ─── Kiểm tra sở hữu, mượn bất biến `&` và khả biến `&mut`, kiểm tra alias
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 9: CONST   │ ─── Constant Folding: tính toán trước các biểu thức hằng số tại compile-time
    └────────┬─────────┘
             ▼
    ┌──────────────────┐
    │  Pass 10: DIAG   │ ─── Diagnostic Engine: phát hiện cảnh báo, tổng hợp lỗi có vị trí dòng/cột
    └────────┬─────────┘
             │
             ▼
       AST Hoàn chỉnh
```

| Pass | File nguồn | Mục đích & Trách nhiệm chính |
|------|------------|------------------------------|
| **Pass 1: Modules** | `sem_pass1_modules.vri` | Khám phá cây thư mục module, xử lý `include` và `import ... from`, kiểm tra chu trình DAG. |
| **Pass 2: Symbols** | `sem_pass2_symbols.vri` | Đăng ký các thực thể toàn cục vào `SymbolTable`: hàm (`func`), cấu trúc (`entity`), hằng số (`const`), kiểu dữ liệu người dùng. |
| **Pass 3: Names** | `sem_pass3_names.vri` | Phân giải không gian tên trong phạm vi cục bộ (`ScopeTree`), bắt lỗi sử dụng biến trước khi khai báo hoặc trùng tên biến. |
| **Pass 4: Types** | `sem_pass4_types.vri` | Kiểm tra tính hợp lệ của định nghĩa kiểu, tính toán kích thước struct / alignment, kiểm tra kiểu đệ quy không con trỏ. |
| **Pass 5: Infer** | `sem_pass5_infer.vri` | Suy luận kiểu cục bộ theo ngữ cảnh cho các biến không chỉ định kiểu cụ thể (`let x = 100`). |
| **Pass 6: Typecheck** | `sem_pass6_typecheck.vri` | Kiểm tra kiểu chặt chẽ (Strict Spec v2.0): kiểm tra tương thích toán tử, ràng buộc kích thước tensor, chữ ký tham số hàm. |
| **Pass 7: CFA** | `sem_pass7_cfa.vri` | Phân tích luồng điều khiển: đảm bảo mọi nhánh hàm có trả về `out`, phát hiện mã chết không thể chạm tới (unreachable code). |
| **Pass 8: Borrow** | `sem_pass8_borrow.vri` | Mô hình quyền sở hữu & vòng đời: đảm bảo chỉ có tối đa 1 tham chiếu khả biến `&mut` hoặc nhiều tham chiếu đọc `&`, chống rò rỉ dữ liệu. |
| **Pass 9: ConstFold** | `sem_pass9_constfold.vri` | Đánh giá và rút gọn các biểu thức hằng số lúc biên dịch (ví dụ `10 * 1024` → `10240`). |
| **Pass 10: Diagnostics** | `sem_pass10_diagnostics.vri` | Thu thập toàn bộ chẩn đoán, tô màu đầu ra, báo cáo vị trí dòng và cột chính xác từ mã nguồn. |

---

## 3. Tầng Trung gian: HIR & MIR (SSA & CFG Pipeline)

Kiến trúc chính thức của Vir chuyển đổi AST thành đồ thị điều khiển dòng lệnh SSA dạng **HIR → MIR → LIR** (Quy định tại Spec v2.0 §1.2).

### 3.1. High-Level Intermediate Representation (HIR)
- Nằm tại `stdlib/vir/compiler/hir.vri` và `ast_to_hir.vri`.
- Lưu giữ nguyên vẹn cấu trúc mức cao của ngôn ngữ: các khối điều khiển có cấu trúc, các biểu thức hướng đối tượng / entity, các khối xử lý tài nguyên `arena:` và các khối AI `infer:` / `train:`.

### 3.2. Mid-Level Intermediate Representation (MIR)
- Nằm tại `stdlib/vir/compiler/mir.vri`.
- **Đặc trưng:**
  - Mô hình đồ thị điều khiển dòng dữ liệu **Control Flow Graph (CFG)** gồm các `MirBlock` độc lập với danh sách tiền nhiệm (`preds`) và kế nhiệm (`successors`).
  - Dạng chuẩn **Static Single Assignment (SSA)**: Mỗi thanh ghi ảo chỉ được gán đúng một lần.
  - Chuyển đổi từ AST sang MIR qua `ast_to_mir.vri` hoặc từ HIR qua `hir_to_mir.vri`.

- **Tập lệnh MIR tiêu biểu (`MirOp`):**

| Nhóm lệnh | Opcodes |
|-----------|---------|
| **Điều khiển & Di chuyển** | `Nop`, `Move`, `Load`, `Store`, `Jump`, `JumpIf`, `JumpIfNot`, `Return` |
| **Số học & Logic** | `Add`, `Sub`, `Mul`, `Div`, `Mod`, `Pow`, `And`, `Or`, `Xor`, `Shl`, `Shr`, `Not` |
| **So sánh** | `CmpEq`, `CmpNe`, `CmpGt`, `CmpLt`, `CmpGe`, `CmpLe` |
| **Hàm & Thủ tục** | `SetArg`, `Call`, `Intrinsic` |
| **AI / Tensor Native** | `MatMul` (Toán tử `**`), `Fma` (Toán tử `><`) |

- **Intrinsic MIR chuẩn (`MIR_INTR_*`):**
  Xử lý các thao tác hệ thống và cấu trúc dữ liệu cấp cao:
  - `MIR_INTR_STR_LIT`, `MIR_INTR_PRINT`, `MIR_INTR_INPUT`: Chuỗi và I/O.
  - `MIR_INTR_ARRAY`, `MIR_INTR_TUPLE`, `MIR_INTR_ENTITY`: Khởi tạo đối tượng bộ nhớ.
  - `MIR_INTR_INDEX`, `MIR_INTR_INDEX_STORE`: Truy cập mảng và tensor đa chiều.
  - `MIR_INTR_ARENA`: Khởi tạo và giải phóng vùng nhớ cục bộ.
  - `MIR_INTR_THROW`, `MIR_INTR_ENSURE`, `MIR_INTR_REVERT`: Xử lý ngoại lệ không unwind.

### 3.3. SSA Construction & Dominator Analysis
- **CFG Dominators (`mir_cfg.vri`):**
  Tính toán Dominator Tree và Dominance Frontiers trên các khối basic block của từng hàm để xác định chính xác các điểm hội tụ dòng điều khiển.
- **$\phi$-Node Insertion (`mir_ssa.vri`):**
  Chèn các hàm $\phi$ (`mir_insert_phi_nodes`) tại các khối biên chi phối (dominance frontier) cho các biến bị sửa đổi trong nhiều nhánh rẽ.
- **SSA Variable Renaming (`mir_ssa.vri`):**
  Đổi tên toàn bộ biến thành các phiên bản SSA duy nhất ($v_0, v_1, v_2, \ldots$) đảm bảo tính chất Single Assignment.

### 3.4. MIR Optimization Pipeline (`mir_opt_pipeline.vri`, `mir_opt.vri`)
Pipeline tối ưu hoá cấp trung được cấu hình theo cấp độ tối ưu `-O0` đến `-O3`:
1. **Constant Folding & Constant Propagation:** Lan truyền hằng số qua các lệnh $\phi$ và rút gọn biểu thức tĩnh.
2. **Dead Code Elimination (DCE):** Quét đồ thị use-def loại bỏ các lệnh có đích không được dùng tới.
3. **Common Subexpression Elimination (CSE):** Nhận diện các biểu thức tương đương để tái sử dụng giá trị đã tính trong cùng một dominator scope.
4. **Function Inlining:** Nhúng các hàm nhỏ hoặc hàm đánh dấu `@inline` vào vị trí gọi để triệt tiêu chi phí gọi hàm.
5. **Loop Invariant Code Motion (LICM):** Đưa các biểu thức bất biến ra khỏi thân vòng lặp.
6. **Backend Target MIR Hook (`opt_backend_run_mir_post`):** Chạy các pass tối ưu hóa đặc thù cho kiến trúc phần cứng đích trước khi hạ xuống LIR.

---

## 4. Tầng Hạ tầng Máy: LIR & Phân bổ Thanh ghi (Register Allocation)

Nằm tại `stdlib/vir/compiler/lir*.vri`. Tầng LIR chuyển đổi MIR SSA sang dạng lệnh gần kề phần cứng, biểu diễn rõ ràng thanh ghi vật lý, thanh ghi ảo và vị trí trên ngăn xếp (stack frame slots).

### 4.1. Cấu trúc LIR (`lir.vri`)
- **Kiểu dữ liệu phần cứng (`LirType`):** `Int8`, `Int16`, `Int32`, `Int64`, `F32`, `F64`, `Ptr`, `Vector`.
- **Toán hạng LIR (`LirOperandType`):**
  - `PhysReg`: Thanh ghi vật lý cụ thể của CPU.
  - `VRegInt` / `VRegFloat`: Thanh ghi ảo nguyên / thực cần được phân bổ.
  - `StackMem`: Vị trí tương đối so với Frame Pointer `[FP + offset]`.
  - `Imm`: Giá trị tức thời 64-bit.
  - `Label`: Nhãn rẽ nhánh trong khối code.
- **Tập lệnh LIR (`LirOp`):**
  `Nop`, `Mov`, `Add`, `Sub`, `Mul`, `Div`, `Push`, `Pop`, `Call`, `Jmp`, `JmpCond`, `Cmp`, `Ret`, `Load`, `Store`, `Rem`, `SetArg`, `Intrinsic`, `And`, `Or`, `Xor`, `Shl`, `Shr`, `Not`, `Pow`, `MatMul`, `Fma`, `TailCall`.

### 4.2. LIR Lowering (`lir_lower.vri`)
- Chuyển đổi các khối lệnh MIR sang LIR instruction sequence.
- Khử dạng SSA (SSA deconstruction): loại bỏ các hàm $\phi$ bằng các lệnh sao chép `Mov` trên các cạnh vào tương ứng.
- Sinh các chuỗi lệnh nạp tham số gọi hàm tuân thủ ABI phần cứng.

### 4.3. Kiến trúc Phân bổ Thanh ghi Đồ thị Tô màu (Graph Coloring Register Allocation)

Vir áp dụng giải thuật phân bổ thanh ghi tiên tiến dựa trên nền tảng **Chaitin–Briggs Graph Coloring** kết hợp kỹ thuật **George–Appel Iterated Register Coalescing (IRC)** (`stdlib/vir/compiler/lir_regalloc_color.vri`):

```
       LIR với thanh ghi ảo
                │
                ▼
   ┌──────────────────────────┐
   │ 1. LIR Normalization     │ ─── Loại bỏ các lệnh Mov vô nghĩa, chuẩn hoá thứ tự toán hạng
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │ 2. Liveness Analysis     │ ─── Tính toán Live Intervals [start, end] cho từng thanh ghi ảo
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │ 3. Interference Graph    │ ─── Xây dựng đồ thị xung đột: Cạnh nối 2 biến sống đồng thời
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │ 4. Chaitin-Briggs        │ ─── Rút gọn đỉnh (Simplify), gán thanh ghi vật lý (Select)
   │    Coloring & Spill      │     Nếu thiếu thanh ghi: Ước lượng chi phí và Spill ra StackMem
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │ 5. George-Appel IRC      │ ─── Coalescing: Gộp các thanh ghi liên kết qua lệnh Mov Rd, Rs
   │    Coalescing Pass       │     Triệt tiêu hoàn toàn các lệnh copy thanh ghi không cần thiết
   └────────────┬─────────────┘
                ▼
       LIR với thanh ghi vật lý
```

1. **Liveness Analysis (`lir_liveness.vri`):**
   Xác định tập hợp các biến sống tại mỗi điểm chương trình (live-in, live-out) và khoảng sống tương ứng.
2. **Interference Graph (`lir_interference.vri`):**
   Tạo ma trận / danh sách kề giữa các thanh ghi ảo có khoảng sống giao nhau.
3. **Graph Coloring & Spilling:**
   - Chọn bậc đỉnh $K$ (số lượng thanh ghi vật lý có sẵn trên kiến trúc).
   - Đẩy các đỉnh có bậc $< K$ vào stack rút gọn.
   - Khi gặp bế tắc (mọi đỉnh có bậc $\ge K$), thuật toán tính toán trọng số tràn (spill weight) dựa trên mức độ lặp và tần suất sử dụng để chọn thanh ghi tràn ra ô nhớ ngăn xếp (`StackMem`).
4. **Iterated Register Coalescing:**
   Áp dụng chuẩn heuristic Briggs/George để hợp nhất các thanh ghi nguồn và đích của lệnh `Mov`, giúp mã máy sau cùng đạt mật độ thanh ghi tối ưu tương đương các compiler công nghiệp.

---

## 5. Tầng Sinh Mã Máy Trực tiếp & Định dạng Nhị phân

Toàn bộ quá trình sinh mã máy và liên kết nhị phân được thực hiện trực tiếp bởi trình biên dịch Vir mà **hoàn toàn không gọi công cụ ngoài** (như `as`, `ld`, `ld64`, `lld`, `gcc` hay `clang`).

### 5.1. Bộ phát mã máy trực tiếp (Direct Machine Codegen)

- **ARM64 / AArch64 (`stdlib/vir/compiler/lir_codegen.vri`):**
  - Tuân thủ chuẩn ABI **AAPCS64** (tham số trên $X_0-X_7$, giá trị trả về trên $X_0/X_1$, stack căn chỉnh 16-byte).
  - Trực tiếp mã hoá lệnh máy 32-bit vào bộ đệm `CodeBuf`:
    - ALU & Số học: `ADD`, `SUB`, `MUL`, `SDIV`, `UDIV`.
    - Di chuyển & Nạp giá trị tức thời: `MOVZ`, `MOVK`, `LDR`, `STR`, `STP`, `LDP`.
    - Điều khiển: `B`, `B.cond`, `BL`, `BLR`, `RET`.
    - Phép tính logic/bit: `AND`, `ORR`, `EOR`, `LSL`, `LSR`.
  - **Tăng tốc SIMD NEON:** Mã hoá trực tiếp các lệnh vector `LD1`, `ST1`, `FADD.4S`, `FMUL.4S`, `FMLA.4S` cho các thao tác tensor và mảng.

- **x86_64 (`stdlib/vir/compiler/lir_codegen_x86.vri`):**
  - Tuân thủ chuẩn ABI **System V AMD64** (tham số trên `RDI`, `RSI`, `RDX`, `RCX`, `R8`, `R9`, trả về trên `RAX`).
  - Mã hoá tiền tố REX (REX.W), byte ModR/M, byte SIB và offset tức thời:
    - ALU: `ADD`, `SUB`, `IMUL`, `IDIV`, `CQO`.
    - Điều khiển: `JMP rel32`, `Jcc rel32`, `CALL rel32`, `RET`.
    - Bộ nhớ: `MOV [rbp - off], reg`, `PUSH`, `POP`.
  - **Tăng tốc AVX/SSE:** Mã hoá tiền tố VEX cho các phép toán vector 128-bit / 256-bit: `vaddps`, `vmulps`, `vfmadd213ps`.

- **WebAssembly (`stdlib/vir/compiler/lir_codegen_wasm.vri`):**
  - Sinh trực tiếp mã nhị phân bytecode WASM (`.wasm`).
  - Mã hoá các section chuẩn WASM (Type, Function, Table, Memory, Global, Export, Element, Code).

- **RISC-V 64 (`stdlib/vir/compiler/lir_to_mc.vri`, `mc_printer.vri`):**
  - Hỗ trợ kiến trúc RV64GC chuẩn với calling convention LP64D.
  - Bộ phát Machine Code (MC) trung gian và bộ xuất assembly sạch.

### 5.2. Bộ liên kết nhị phân độc lập (Direct Binary Linker)

- **Mach-O 64-bit Builder (`stdlib/vir/compiler/macho.vri`):**
  - Tạo trực tiếp tập tin thực thi nhị phân cho nền tảng macOS (Apple Silicon ARM64 và Intel x86_64).
  - Tự động cấu hình cấu trúc Mach-O 64-bit:
    - `mach_header_64` (Magic `0xFEEDFACF`, cputype, cpusubtype, filetype `MH_EXECUTE`).
    - `LC_SEGMENT_64 (__PAGEZERO)`: Vùng bảo vệ chống null pointer dereference kích thước 4GB.
    - `LC_SEGMENT_64 (__TEXT)`: Chứa section `__text` (mã máy) và section `__cstring` (hằng chuỗi UTF-8).
    - `LC_MAIN`: Thiết lập entry point trực tiếp trỏ vào hàm `start` / `main`.
    - `LC_LOAD_DYLINKER`: Liên kết dylinker hệ thống (hoặc chạy bare-metal).

- **ELF 64-bit Builder (`stdlib/vir/compiler/binary.vri`, `stdlib/vir/rt/elf.vri`):**
  - Tạo trực tiếp tập tin thực thi nhị phân cho hệ điều hành Linux.
  - Tự động cấu hình cấu trúc ELF 64-bit:
    - `Elf64_Ehdr`: Định dạng e_ident (ELFCLASS64, ELFDATA2LSB), e_type (`ET_EXEC` hoặc `ET_DYN`), e_machine (`EM_AARCH64` hoặc `EM_X86_64`).
    - `Elf64_Phdr`: Các Program Header `PT_LOAD` với quyền Read-Exec (cho code) và Read-Write (cho data).
    - Section headers: `.text`, `.rodata`, `.data`, `.symtab`, `.strtab`.

---

## 6. Tầng Runtime Thuần Vir (`stdlib/vir/rt/`)

Để hiện thực hoá nguyên lý **Zero Libc & Zero External Runtime**, toàn bộ các tiện ích hệ thống cốt lõi được cài đặt trực tiếp tại `stdlib/vir/rt/` bằng mã nguồn Vir nguyên bản:

```
stdlib/vir/rt/
├── syscall.vri     # Giao tiếp kernel trực tiếp: macOS BSD 0x2000000 / Linux syscalls
├── alloc.vri       # Bộ cấp phát bộ nhớ mmap bump allocator & free-list heap
├── vec_rt.vri      # Dynamic buffer & byte vector runtime cho compiler & stdlib
├── string_rt.vri   # Chuỗi UTF-8 fat-pointer & StringBuilder
├── io.vri          # Đọc ghi tập tin và console I/O cấp thấp
├── start.vri       # Điểm nhập runtime `_start` / `start` phân tích argc, argv
├── macho.vri       # Cấu trúc dữ liệu runtime định dạng Mach-O
└── elf.vri         # Cấu trúc dữ liệu runtime định dạng ELF
```

### 6.1. Tầng Giao tiếp Kernel Trực tiếp (`syscall.vri`)
Vir không gọi qua các hàm `write()`, `mmap()`, `exit()` của thư viện chuẩn C `libc.so` hay `libSystem.dylib`. Thay vào đó, nó tương tác trực tiếp với nhân hệ điều hành qua lệnh ngắt hệ thống:
- **macOS (Darwin ARM64 / x86_64):**
  Sử dụng chuẩn syscall class 2 (offset `0x2000000`):
  - `sys_exit` = `0x2000001`
  - `sys_write` = `0x2000004`
  - `sys_open` = `0x2000005`
  - `sys_close` = `0x2000006`
  - `sys_mmap` = `0x20000c5` (197)
  - `sys_munmap` = `0x2000049` (73)
- **Linux (x86_64 / ARM64):**
  Sử dụng số hiệu syscall chuẩn của nhân Linux (ví dụ: `sys_write` = 1 trên x86_64, 64 trên AArch64).

### 6.2. Hệ thống Quản lý Bộ nhớ (`alloc.vri`)
- **Page Allocation:** Cấp phát các trang nhớ lớn trực tiếp qua syscall `mmap` (`PROT_READ | PROT_WRITE`, cờ `MAP_ANONYMOUS | MAP_PRIVATE`).
- **Arena Scopes (`arena:` blocks):**
  Bump-pointer allocation siêu tốc cho các biến tạm thời trong khối lệnh. Toàn bộ con trỏ phân bổ trong khối sẽ được giải phóng lập tức chỉ bằng một thao tác cuộn con trỏ (pointer rewind) khi rời khỏi khối `end`.
- **Heap Allocator (`vir_alloc`, `vir_free`, `vir_realloc`):**
  Bộ cấp phát free-list quản lý vùng nhớ heap cho các đối tượng sống lâu dài.

### 6.3. Runtime Vector & Chuỗi (`vec_rt.vri`, `string_rt.vri`)
- **`bvec` (Byte Vector):** Bộ đệm mảng byte mở rộng động, hỗ trợ nạp các giá trị số 8-bit, 16-bit, 32-bit, 64-bit định dạng Little-Endian (`bvec_push_u32_le`, `bvec_push_u64_le`). Được sử dụng làm nền tảng phát mã nhị phân trong `CodeBuf`.
- **`vec_rt` (Object Vector):** Mảng động chứa con trỏ/thực thể, hỗ trợ truy cập ngẫu nhiên $O(1)$.
- **Fat-Pointer Strings:** Chuỗi trong Vir được lưu trữ dưới dạng con trỏ dữ liệu và độ dài byte rõ ràng, ngăn ngừa triệt để lỗi tràn bộ đệm và tối ưu hoá thao tác cắt chuỗi (string slicing) không cần cấp phát lại.

---

## 7. Phân hệ AI / Học máy Bản địa (Native AI/ML Subsystem — Spec v2.0 §26)

Khác biệt với các ngôn ngữ lập trình truyền thống phải phụ thuộc vào thư viện bên ngoài (như PyTorch, TensorFlow hay NumPy), Vir tích hợp trực tiếp AI/ML vào ngữ pháp cốt lõi và hệ thống kiểu dữ liệu của trình biên dịch:

```
Mã nguồn Vir:
  var w: tensor<f32>[64, 128]
  var x: tensor<f32>[128, 32]
  train:
      var y = w ** x
      var loss = compute_loss(y)
      loss.backward()
  end
```

### 7.1. Kiểu dữ liệu Tensor Hạng nhất (`tensor<T>[Dims...]`)
- Cú pháp chuẩn tắc: `tensor<kiểu_dữ_liệu>[chiều_1, chiều_2, ...]`.
- Kích thước các chiều được kiểm tra tĩnh tại compile-time (trong Pass 6 của Semantic Analysis).
- Bộ nhớ được sắp xếp liên tục (contiguous memory layout) hoặc strided layout tối ưu cho truy cập SIMD cache line.

### 7.2. Toán tử Phần cứng AI Tích hợp
- **Nhân ma trận MatMul Infix Operator (`**`):**
  Toán tử `a ** b` thực hiện phép nhân ma trận giữa hai tensor tương thích chiều (ví dụ: $[M, K] ** [K, N] 
ightarrow [M, N]$).
  - Không phải là hàm thư viện gọi qua FFI.
  - Trực tiếp hạ xuống lệnh MIR `MirOp.MatMul` → LIR `LirOp.MatMul`.
  - Sinh mã máy sử dụng các khối nhân khối (tiled GEMM) và tập lệnh vector NEON / AVX.
- **Fused Multiply-Add Operator (`><`):**
  Toán tử `a >< b` thực hiện phép toán $(a 	imes b) + c$ tối ưu trực tiếp bằng một chu kỳ lệnh FMA trên phần cứng CPU/NPU, duy trì độ chính xác số học cao nhất mà không bị làm tròn trung gian.

### 7.3. Khối Ngữ cảnh Thực thi AI
- **Khối `infer:` (Suy luận tối ưu):**
  - Tắt hoàn toàn việc ghi vết đồ thị vi phân (zero autodiff overhead).
  - Sử dụng chiến lược tái sử dụng bộ nhớ đệm (activation buffer reuse) để giảm thiểu footprint RAM.
- **Khối `train:` (Huấn luyện có đạo hàm):**
  - Tự động kích hoạt cơ chế theo dõi đồ thị tính toán (Gradient Tape).
  - Mọi tensor tham số được tự động cấp phát trường `.grad` để tích luỹ gradient.

### 7.4. Động cơ Vi phân Tự động (Tape Autodiff & `backward()`)
- Hỗ trợ vi phân tự động chiều ngược (Reverse-mode Automatic Differentiation).
- Trong khối `train:`, mỗi thao tác toán học trên tensor sẽ ghi lại một nút toán tử và các tham chiếu đầu vào vào băng vi phân (computation tape).
- Khi gọi `loss.backward()`, động cơ duyệt ngược đồ thị tính toán từ đỉnh mục tiêu, áp dụng quy tắc dây chuyền (chain rule) để tính toán đạo hàm riêng cho từng tham số và lưu vào `.grad`.

### 7.5. Nguyên thuỷ Lượng tử hoá Đa bit (`quantize`)
- Hàm nguyên thuỷ `quantize(tensor, target_format)` hỗ trợ chuyển đổi tensor số thực chính xác cao sang các định dạng tiết kiệm tài nguyên:
  - `INT8` (Symmetric / Asymmetric quantization).
  - `INT4` (Hỗ trợ nén trọng số mô hình ngôn ngữ lớn LLM).
  - `FP16` / `BF16`.
- Tích hợp sẵn trong chuẩn thư viện `stdlib/vir/ai/quantize.vri`.

### 7.6. Thư viện Chuẩn AI Cấp cao (`stdlib/vir/ai/`)
Trình biên dịch và thư viện chuẩn cung cấp trọn gói các module AI cấp cao viết 100% bằng Vir:
- `stdlib/vir/ai/model.vri`: Khung kiến trúc xây dựng mạng nơ-ron (Linear, Conv2D, Attention, Transformer block).
- `stdlib/vir/ai/train.vri`: Vòng lặp huấn luyện, bộ tối ưu hoá (SGD, Adam, AdamW).
- `stdlib/vir/ai/infer.vri`: Engine thực thi suy luận batching và streaming.
- `stdlib/vir/ai/onnx.vri`: Trình phân tích và thực thi trực tiếp mô hình định dạng ONNX.
- `stdlib/vir/ai/vision.vri`: Xử lý tiền xử lý hình ảnh và thị giác máy tính.

---

## 8. Tầng JIT & Cơ chế Tự Vá Mã Động (Dynamic JIT & Self-Patching)

Nằm tại `stdlib/vir/jit/` (phiên bản thuần Vir) và `core/src/jit_bridge.c` (bộ JIT cấp thấp). Vir hỗ trợ chế độ thực thi JIT với cơ chế tự thích ứng phần cứng.

```
                    Mã nguồn / IR
                          │
                          ▼
            ┌───────────────────────────┐
            │ Dual-Emit Code Generator  │
            └─────────────┬─────────────┘
                          │
           ┌──────────────┴──────────────┐
           ▼                             ▼
    ┌─────────────┐               ┌─────────────┐
    │ Bản A: Safe │               │ Bản B: Fast │
    │ (Stack-safe)│               │ (Reg-direct)│
    └──────┬──────┘               └──────┬──────┘
           │                             │
           └──────────────┬──────────────┘
                          ▼
             ┌─────────────────────────┐
             │  Jump Table Indirection │ ── JMP trỏ ban đầu tới Bản A
             └────────────┬────────────┘
                          │
    Vòng lặp Runtime      │ (Thực thi & Quan trắc tải CPU)
    Evolution Loop        ▼
             ┌─────────────────────────┐
             │ Monitor: CPU Load < 80% │
             └────────────┬────────────┘
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      [Đạt điều kiện]           [Lỗi / Tràn thanh ghi]
             │                         │
             ▼                         ▼
    Ghi đè Jump Table offset    Gọi Rollback tự động
    chuyển sang Bản B!          quay về Bản A an toàn
```

1. **Dual-Emit Architecture:**
   Trình tạo mã sinh đồng thời hai biến thể mã máy cho các điểm nóng (hotspots):
   - **Bản A (Safe):** Dựa trên ngăn xếp (stack-based), an toàn tuyệt đối, không gây áp lực lên thanh ghi phần cứng.
   - **Bản B (Fast):** Dựa trên thanh ghi trực tiếp (register-direct), tốc độ tối đa.
2. **Jump Table Patching:**
   Thực thi thông qua bảng nhảy trung gian. Khi khởi động, bảng nhảy trỏ tới Bản A. Khi vòng lặp giám sát (Evolution Loop) phát hiện hệ thống còn nhiều thanh ghi rảnh rỗi ($N_{free} > 	ext{threshold}$), bộ patcher sẽ ghi đè 4 byte offset của lệnh `JMP` trong bảng nhảy để trỏ tức thì sang Bản B mà không cần dừng tiến trình.
3. **Rollback & Blacklist:**
   Nếu Bản B gặp lỗi hoặc gây suy giảm hiệu năng, hệ thống gọi `jit_bridge_rollback()` để hoàn nguyên bảng nhảy về Bản A. Nếu một khối mã bị rollback quá số lần định mức (ngưỡng mặc định: 3 lần), khối đó sẽ được đánh dấu `PERMANENT_SAFE` vĩnh viễn.
4. **Bảo mật Vùng nhớ Thực thi:**
   Trên macOS ARM64, vùng nhớ JIT được chuyển đổi trạng thái đọc/ghi thông qua `pthread_jit_write_protect_np(0)` (cho phép ghi) và `pthread_jit_write_protect_np(1)` (cho phép thực thi) kết hợp lệnh làm sạch cache lệnh `sys_icache_invalidate()`. Trên Linux, sử dụng `mprotect()`.

---

## 9. Quy trình Tự Lưu trữ (Self-Hosting Bootstrap)

Quá trình bootstrap của Vir đạt đến trạng thái tự chủ hoàn toàn (Fixed-Point Bootstrap):

```
┌──────────────┐     chạy bởi C-VM     ┌─────────────────┐
│ Stage 0      │ ─────────────────────→│ Binary virc-s0  │
│ (virc.vri)   │                       │ (Khởi động đầu) │
└──────────────┘                       └────────┬────────┘
                                                │
                                                ▼ tự biên dịch
┌──────────────┐     biên dịch bởi     ┌─────────────────┐
│ Stage 1      │ ─────────────────────→│ Binary virc-s1  │
│ (virc.vri)   │     virc-s0           │ (Tự lưu trữ)    │
└──────────────┘                       └────────┬────────┘
                                                │
                                                ▼ tự biên dịch lần nữa
┌──────────────┐     biên dịch bởi     ┌─────────────────┐
│ Stage 2      │ ─────────────────────→│ Binary virc-s2  │
│ (virc.vri)   │     virc-s1           │ (Hoàn tất)      │
└──────────────┘                       └─────────────────┘
                                                │
                          Kiểm tra: virc-s1 == virc-s2 (Bit-for-bit identical)
```

1. **Stage 0:** Trình biên dịch Vir (`stdlib/vir/compiler/virc.vri`) được khởi động thông qua máy ảo bootstrap C-VM để tạo ra tệp nhị phân đầu tiên `virc-s0`.
2. **Stage 1:** Tệp nhị phân `virc-s0` tự biên dịch mã nguồn của chính nó (`stdlib/vir/compiler/virc.vri`) thành `virc-s1` độc lập.
3. **Stage 2 (Fixed-Point Verification):** `virc-s1` tiếp tục biên dịch lại mã nguồn `virc.vri` để sinh ra `virc-s2`. Khi băm SHA-256 của `virc-s1` và `virc-s2` trùng khớp tuyệt đối 100%, trạng thái tự lưu trữ đạt đỉnh hoàn thiện (Fixed-point verification thành công).

---

## 10. Ví dụ Mã Nguồn Vir v2.0 Chuẩn tắc

Dưới đây là mã nguồn Vir v2.0 minh hoạ tính năng AI và cú pháp chuẩn tiếng Anh (không sử dụng sublib tự nhiên):

```vir
# File: demo_ai.vri
# Ngôn ngữ Vir v2.0 chuẩn tắc — Single English Keywords

module demo.ai

include vir.rt.io
import print_ln, print_int from vir.rt.io

func matrix_multiply_demo:
    # 1. Khai báo tensor 2 chiều kích thước 2x2
    var a: tensor<f32>[2, 2]
    var b: tensor<f32>[2, 2]

    # 2. Khởi tạo dữ liệu
    a[0, 0] = 1.0; a[0, 1] = 2.0
    a[1, 0] = 3.0; a[1, 1] = 4.0

    b[0, 0] = 5.0; b[0, 1] = 6.0
    b[1, 0] = 7.0; b[1, 1] = 8.0

    # 3. Khối suy luận tối ưu hoá không gradient
    infer:
        # Toán tử nhân ma trận cấp ngôn ngữ: a ** b
        var c = a ** b
        print_ln("Kết quả c[0, 0] = ")
        print_int(c[0, 0] as int)
    end
end.

func main:
    print_ln("Khởi động hệ thống Vir v2.0...")
    matrix_multiply_demo()
    out 0
end.
```

---

## 11. Bảng Đối Chiếu Thành Phần Hiện Tại vs Lịch Sử

Để bảo đảm tính rõ ràng cho các nhà phát triển và duy trì tính toàn vẹn của tài liệu, bảng sau đây liệt kê sự thay đổi giữa các thành phần nguyên mẫu lịch sử và kiến trúc thực tế hiện tại:

| Thành phần | Nguyên mẫu Lịch sử (Đã bãi bỏ) | Kiến trúc Thực tế Hiện tại (v2.0) | File nguồn hiện tại |
|------------|--------------------------------|----------------------------------|---------------------|
| **Cú pháp từ khoá** | Đa ngôn ngữ (`src/sublib/{vi,zh,ja,ko}.py`) | Đơn ngữ tiếng Anh chuẩn hóa Spec v2.0 | `stdlib/vir/compiler/lexer.vri` |
| **Tách từ (Lexer)** | N-Gram Greedy phrase match (`ngram_tokenizer.py`) | UTF-8 direct character stream lexer | `stdlib/vir/compiler/lexer.vri` |
| **Ánh xạ từ vựng** | Bảng JSON `config/sublib_mapping.json` | TokenKind / TokType enum định kiểu tĩnh | `stdlib/vir/compiler/lexer.vri` |
| **Phân tích ngữ pháp**| Python AST Parser (`src/frontend/parser/`) | Pure Vir Recursive Descent Parser | `stdlib/vir/compiler/parser.vri` |
| **Ngữ nghĩa (Semantics)**| Ghép nối lỏng lẻo trong compiler cũ | 10 Discrete Passes có chẩn đoán chi tiết | `stdlib/vir/compiler/semantic.vri` |
| **Mô hình IR** | Q-IR dạng flat opcode tuyến tính | Pipeline chính tắc: AST → HIR → MIR (SSA) → LIR | `mir.vri`, `mir_ssa.vri`, `lir.vri` |
| **Phân bổ thanh ghi**| Linear scan đơn giản không tối ưu | Chaitin–Briggs Graph Coloring + George–Appel IRC | `lir_regalloc_color.vri` |
| **Sinh mã máy** | Gọi Assembler / toolchain ngoài hoặc shim C | Trực tiếp phát byte mã máy ARM64 / x86_64 / WASM | `lir_codegen.vri`, `lir_codegen_x86.vri` |
| **Liên kết nhị phân** | Phụ thuộc `gcc`, `clang`, `ld64` | Tự sinh trực tiếp định dạng Mach-O và ELF | `macho.vri`, `binary.vri`, `rt/elf.vri` |
| **Thư viện hệ thống** | `libc.so`, `libSystem.dylib`, POSIX C headers | Direct OS Syscalls (macOS BSD 0x2000000 / Linux) | `stdlib/vir/rt/syscall.vri` |
| **Phân hệ AI/ML** | Thư viện wrapper ngoài hoặc mock test | First-class `tensor`, MatMul `**`, Autodiff `backward` | `mir.vri`, `lir_codegen.vri`, `stdlib/vir/ai/` |
