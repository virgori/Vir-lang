# Q-IR: Kiến trúc IR Ba Cấp Độ của Vir

> **Status:** Historical design. **Superseded** by **HIR → MIR → LIR**  
> (Spec §1.2, [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §0). Do not treat QIR-H/M/L as the live compiler spine.

**Q-IR** (Quantum-IR) là hệ thống Intermediate Representation ba cấp độ của ngôn ngữ Vir, được thiết kế để tối ưu hóa các mô hình AI từ mức ngữ nghĩa cao xuống mã máy SIMD. Mỗi cấp độ phục vụ một mục đích khác nhau trong pipeline biên dịch, cho phép các pass tối ưu hóa hoạt động trên mức trừu tượng phù hợp nhất.

---

## 1. Tổng quan Pipeline

```
Source (.vri) → Parser → AST → QIR-H → [Passes] → QIR-M → [Fusion + Passes] → QIR-L → Codegen → Machine Code
```

### Ba cấp độ:

| Cấp độ | Tên | Vai trò | Số opcodes |
|--------|-----|---------|------------|
| **QIR-H** | High-Level | Ngữ nghĩa mô hình, AD tape, alias analysis | 36 ops |
| **QIR-M** | Mid-Level | Tensor canonical, fusion passes, BCE | 40 ops |
| **QIR-L** | Low-Level | Tiled loops, SIMD micro-kernels, scheduling | 15 ops |

---

## 2. QIR-H — High-Level (Model-Semantic IR)

QIR-H bảo toàn **ngữ nghĩa mô hình AI** — mỗi node đại diện cho một thao tác mà một ML engineer sẽ nhận ra (ATTENTION, LINEAR, LAYER_NORM). Đây là cấp độ nơi reverse-mode AD, alias analysis, và training annotations được thực hiện.

### 2.1 QIRHOp — 36 Operations

```
┌────────────────┬──────────────────────────────────────────────────────────┐
│ Category       │ Operations                                              │
├────────────────┼──────────────────────────────────────────────────────────┤
│ Data flow      │ CONSTANT, PARAMETER, INPUT                              │
│ Unary          │ NEG, ABS, SQRT, RSQRT, EXP, LOG, TANH, SIGMOID,        │
│                │ RELU, GELU, SILU                                        │
│ Binary         │ ADD, SUB, MUL, DIV, POW, MAXIMUM, MINIMUM              │
│ Reduction      │ REDUCE_SUM, REDUCE_MEAN, REDUCE_MAX                    │
│ Matrix         │ MATMUL, TRANSPOSE, RESHAPE, BROADCAST                  │
│ Data movement  │ GATHER, SCATTER, SLICE, CONCAT, CAST                   │
│ Composite      │ LINEAR, EMBEDDING, ATTENTION, MLP_BLOCK                │
│ Normalization  │ LAYER_NORM, RMS_NORM, SOFTMAX                          │
│ AD markers     │ GRAD_STOP, SAVE_FOR_BACKWARD                           │
│ Memory hints   │ ALIAS_BARRIER, BUFFER_HINT                             │
└────────────────┴──────────────────────────────────────────────────────────┘
```

### 2.2 QIRHNode Schema

```python
@dataclass
class QIRHNode:
    node_id: int
    op: QIRHOp
    input_ids: tuple[int, ...]
    output_ids: tuple[int, ...] = ()
    block_id: int = 0
    region_id: int = 0
    name: str = ""
    tensor_type: TensorType | None = None
    attrs: dict = field(default_factory=dict)

    # ── Training Annotations ──
    requires_grad: bool = False        # node tham gia backward pass
    stop_gradient: bool = False        # cắt gradient flow tại đây
    saved_for_backward: bool = False   # lưu activation cho backward

    # ── Memory Annotations ──
    alias_group: int = 0               # nhóm aliasing (cùng buffer)
    is_view: bool = False              # view (không copy data)
    mutable: bool = False              # có thể write in-place
    inplace_safe: bool = False         # optimizer có thể ghi đè a = a + b
    lifetime_region: int = 0           # vùng lifetime cho buffer planning
    buffer_hint: str = ""              # hints: "pin", "pool", "arena"
```

**Điểm đặc biệt:** QIR-H node mang cả thông tin training (cho AD) và memory hints (cho buffer planning), giúp compiler đưa ra quyết định tối ưu hóa cấp cao trước khi lowering.

### 2.3 Composite Op Semantics

Các composite ops bảo toàn ý nghĩa mô hình:

- **ATTENTION**: Toàn bộ self-attention (Q, K, V projection → scaled dot-product → output projection)
- **LINEAR**: `y = x @ W^T + bias`
- **MLP_BLOCK**: FFN hoàn chỉnh (Linear → Activation → Linear)
- **EMBEDDING**: Lookup table → gather

---

## 3. QIR-M — Mid-Level (Canonical Tensor IR)

QIR-M là cấp độ "trung tâm" — nơi tất cả composite ops đã được phân rã thành các thao tác tensor canonical. Đây là cấp độ lý tưởng cho **kernel fusion**, vì mỗi node là một phép tính nguyên tử có thể phân tích dependency một cách chính xác.

### 3.1 QIRMOp — 40 Operations

```
┌────────────────┬──────────────────────────────────────────────────────────┐
│ Category       │ Operations                                              │
├────────────────┼──────────────────────────────────────────────────────────┤
│ Elementwise    │ ADD, SUB, MUL, DIV, NEG, ABS, SQRT, RSQRT, EXP, LOG,  │
│                │ TANH, SIGMOID, RELU, GELU, SILU, POW, MAXIMUM, MINIMUM │
│ Reduction      │ REDUCE_SUM, REDUCE_MEAN, REDUCE_MAX                    │
│ Matrix         │ MATMUL, BATCH_MATMUL                                   │
│ Data movement  │ TRANSPOSE, RESHAPE, BROADCAST, GATHER, SCATTER,        │
│                │ SLICE, CONCAT, CAST, COPY                              │
│ Fused patterns │ FUSED_MUL_ADD, FUSED_BIAS_RELU, FUSED_BIAS_GELU       │
│ Memory         │ ALLOC_BUFFER, FREE_BUFFER                              │
│ Safety         │ BOUNDS_CHECK                                           │
└────────────────┴──────────────────────────────────────────────────────────┘
```

### 3.2 QIRMNode Schema

```python
@dataclass
class QIRMNode:
    node_id: int
    op: QIRMOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()
    tensor_type: TensorType | None = None
    shape_inferred: bool = False    # shape đã được giải
    type_inferred: bool = False     # dtype đã được giải
    alias_group: int = 0
    inplace_safe: bool = False
    lifetime_region: int = 0
    attrs: dict = field(default_factory=dict)
```

**Khác biệt chính so với H:** Không còn composite ops. Không còn AD markers. Mỗi node là một phép tính tensor đơn lẻ, shape đã được giải hoàn toàn.

---

## 4. QIR-L — Low-Level (Tiled/Scheduled IR)

QIR-L mô tả chương trình ở mức **micro-kernel** — mỗi node tương ứng với một tiled loop, một SIMD vector loop, hoặc một lệnh gọi micro-kernel cụ thể. Đây là cấp độ gần nhất với phần cứng.

### 4.1 QIRLOp — 15 Operations

```
┌─────────────────┬─────────────────────────────────────────────┐
│ Category        │ Operations                                  │
├─────────────────┼─────────────────────────────────────────────┤
│ Loop control    │ TILE_LOOP, VECTOR_LOOP, PARALLEL_FOR        │
│ Micro-kernels   │ MICRO_GEMM, MICRO_EW, MICRO_REDUCE         │
│ Dispatch        │ KERNEL_CALL                                 │
│ Memory          │ PREFETCH, CACHE_FLUSH, BARRIER              │
│ Safety          │ BOUNDS_CHECK                                │
│ Allocation      │ STACK_ALLOC, DET_FREE                       │
│ Scalar          │ SCALAR_OP                                   │
│ NOP             │ NOP                                         │
└─────────────────┴─────────────────────────────────────────────┘
```

### 4.2 QIRLNode Schema

```python
@dataclass
class QIRLNode:
    node_id: int
    op: QIRLOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()

    # ── Scheduling Metadata ──
    tile_sizes: tuple[int, ...] | None = None    # (tile_m, tile_n, tile_k)
    vector_width: int | None = None              # NEON=4, AVX2=8, AVX512=16
    parallel_dim: int | None = None              # dimension to parallelize

    # ── Kernel Dispatch ──
    kernel_family: str | None = None    # "gemm_neon_8x8", "add", "relu"
    kernel_variant: str | None = None   # "m8_n8_k4" (tile-specific)
    prefetch_distance: int | None = None

    # ── Provenance ──
    buffer_id: int | None = None       # allocated scratch buffer
    source_mid_id: int | None = None   # corresponding M-node
    attrs: dict = field(default_factory=dict)
```

**Đặc biệt:** Mỗi L-node mang đầy đủ thông tin scheduling — tile sizes cho cache reuse, vector width cho SIMD dispatch, kernel family cho micro-kernel selection.

---

## 5. Lowering Pipeline: H → M → L

### 5.1 H → M Lowering (Decomposition)

File: `src/qir/lower/h_to_m.py`

**Hai loại chuyển đổi:**

#### a) 1:1 Direct Mapping (30+ ops)
Các ops đơn giản truyền thẳng:
```
QIR-H ADD  → QIR-M ADD
QIR-H RELU → QIR-M RELU
QIR-H MATMUL → QIR-M MATMUL
```

#### b) Composite Decomposition
Các ops phức hợp được phân rã:

**LINEAR** (`y = x @ W^T + bias`):
```
H: LINEAR(x, W, bias)
         ↓ decompose
M: TRANSPOSE(W)       → W^T
   MATMUL(x, W^T)     → y_raw
   ADD(y_raw, bias)    → y
```

**ATTENTION** (`Softmax(Q·K^T / √d) · V`):
```
H: ATTENTION(Q, K, V)
         ↓ decompose
M: MATMUL(Q, K^T)            → scores
   REDUCE_MAX(scores, dim=-1) → max_s
   SUB(scores, max_s)         → shifted
   EXP(shifted)               → exp_s
   REDUCE_SUM(exp_s, dim=-1)  → sum_e
   DIV(exp_s, sum_e)          → attn_weights
   MATMUL(attn_weights, V)    → output
```

**AD Markers** — Gradient markers được loại bỏ (transparent):
```
H: GRAD_STOP(x) → M: passthrough (x)
H: SAVE_FOR_BACKWARD(x) → M: passthrough (x)
```

### 5.2 M → L Lowering (Tiling & Vectorization)

File: `src/qir/lower/m_to_l.py`

Sử dụng `CapabilityProfile` để quyết định tile sizes và vector widths dựa trên phần cứng:

#### a) MATMUL → TILE_LOOP + MICRO_GEMM
```
M: MATMUL(A[M×K], B[K×N]) → C[M×N]
         ↓ tile
L: TILE_LOOP(tile_m=8, tile_n=8, tile_k=4, parallel_dim=0)
   └─ MICRO_GEMM(kernel_family="gemm_neon_8x8", variant="m8_n8_k4")
      └─ PREFETCH(distance=2)   // if K > 4 × tile_k
```

#### b) Elementwise → VECTOR_LOOP + MICRO_EW
```
M: RELU(x[1024])
         ↓ vectorize
L: VECTOR_LOOP(vector_width=4)   // NEON = 4 × f32
   └─ MICRO_EW(kernel_family="relu", vector_width=4)
```

#### c) Reduction → TILE_LOOP + MICRO_REDUCE
```
M: REDUCE_SUM(x[10000], dim=0)
         ↓ tile
L: TILE_LOOP(tile_sizes=(32,))
   └─ MICRO_REDUCE(kernel_family="reduce_sum", vector_width=4)
```

#### d) Bounds Check Elimination (BCE)
```
M: BOUNDS_CHECK(idx, size, bce_safe=True)
         ↓ eliminate
L: SCALAR_OP(kernel_family="nop", bce_eliminated=True)   // zero-cost
```

---

## 6. AutoKernelFusionPass — Chi tiết thuật toán

File: `src/virpass/passes/auto_fusion.py`

AutoKernelFusionPass là pass tối ưu hóa quan trọng nhất ở QIR-M, thực hiện kernel fusion tự động bằng thuật toán "Greedy Chain Fusion with Register Pressure Analysis".

### 6.1 Tại sao cần Fusion?

Cách tiếp cận truyền thống (numpy/PyTorch) — mỗi phép tính tạo buffer trung gian:
```
tmp1 = a * b      →  STORE tmp1 (N bytes to RAM)
tmp2 = tmp1 + c   →  LOAD tmp1, STORE tmp2
out  = relu(tmp2) →  LOAD tmp2, STORE out
Memory traffic: 11N reads/writes
```

VirFusion — fuse toàn bộ chain vào một kernel:
```
for i in N:
  r0 = LOAD a[i]    // 1 load
  r1 = LOAD b[i]    // 1 load
  r2 = r0 * r1      // register only
  r3 = LOAD c[i]    // 1 load
  r4 = r2 + r3      // register only
  r5 = max(0, r4)   // register only
  STORE out[i] = r5  // 1 store
Memory traffic: 4N reads/writes → 2.75× speedup
```

### 6.2 Thuật toán ba pha

#### Phase 1: Build Consumer Map
```python
def _build_consumer_map(graph) -> dict[int, list[int]]:
    # Với mỗi node, tìm tất cả các node consume output của nó
    # consumers[node_A] = [node_B, node_C]
    # → node_A's output được sử dụng bởi B và C
```

#### Phase 2: Discover Chains (Greedy Forward Walk)

**Thuật toán:**
1. Duyệt tất cả M-nodes, tìm **chain heads** — fuseable nodes mà KHÔNG phải là single-consumer tiếp nối của một fuseable node khác
2. Từ mỗi head, **đi về phía trước** (greedy forward walk):
   - Node hiện tại phải là fuseable (thuộc 18 ops elementwise)
   - Node hiện tại phải có **đúng một** consumer
   - Register pressure + cost(node) ≤ MAX_CHAIN_REGISTERS (24)
   - Chain length ≤ MAX_CHAIN_LENGTH (16)
3. Khi dừng, nếu chain ≥ 2 nodes → lưu lại

**18 Fuseable Ops:**
```
ADD, SUB, MUL, DIV, NEG, ABS, SQRT, RSQRT,
EXP, LOG, TANH, SIGMOID, RELU, GELU, SILU,
MAXIMUM, MINIMUM, POW
```

**Register Pressure Model:**
```
Op          Registers
──────────  ─────────
ADD/SUB/MUL/DIV  1
NEG/ABS/SQRT/RSQRT  1
RELU/MAXIMUM/MINIMUM  1
SIGMOID/SILU        2  (multi-instruction expansion)
EXP/LOG             2  (transcendental approximation)
TANH/GELU/POW       3  (complex instruction sequences)
```

**Ví dụ — GELU activation:**
```
GELU(x) ≈ 0.5 * x * (1 + tanh(√(2/π) * (x + 0.044715 * x³)))
→ Cần 3 registers: temp cho x³, temp cho tanh input, result
```

#### Phase 3: Apply Fusions

1. Sắp xếp chains theo `memory_savings` (giảm dần) — ưu tiên chains tiết kiệm nhất
2. Với mỗi chain:
   - **Pattern matching**: kiểm tra known patterns
     - `MUL → ADD` → `FUSED_MUL_ADD` (FMA instruction)
     - `ADD → RELU` → `FUSED_BIAS_RELU`
     - `ADD → GELU` → `FUSED_BIAS_GELU`
     - `MUL → ADD → RELU` → `FUSED_BIAS_RELU`
   - **Generic fusion**: chuỗi ops bất kỳ → attrs chứa toàn bộ `op_sequence`
3. Thay thế chain bằng **một M-node duy nhất**:
   - Input: external inputs của chain (inputs đến từ bên ngoài)
   - Output: output của tail node
   - Attrs: `fused_chain`, `fused_chain_length`, `register_pressure`, `memory_ops_saved`
4. **Xóa** tất cả intermediate nodes (dead code elimination)

### 6.3 Kết quả trên Transformer 12 lớp

| Metric | Giá trị |
|--------|---------|
| Nodes trước | 288 |
| Nodes sau | 228 |
| **Giảm** | **20.8%** |
| Pass execution | 359 µs |
| Chains discovered | ~30 |
| Memory ops saved | ~60 load+store |

---

## 7. Ánh xạ QIR-L → SIMD (Apple Silicon ARM64)

### 7.1 Platform Detection

`CapabilityProfile.detect()` probe CPU features tại runtime:

```python
class VectorBackend(Enum):
    SCALAR  # Fallback — không có SIMD
    NEON    # ARM64 128-bit (4 x f32)
    SSE2    # x86 128-bit (4 x f32)
    AVX2    # x86 256-bit (8 x f32)
    AVX512  # x86 512-bit (16 x f32)
```

**Apple Silicon (M-series):**
- Backend: **NEON**
- Vector width: **4 × f32** (128-bit registers)
- 32 NEON registers (V0–V31)
- Tile sizing: dựa trên L1D cache (~50% utilization cho 3 tiles A, B, C)
- Typical: tile_m=8, tile_n=8, tile_k=4

### 7.2 MICRO_GEMM → NEON Instructions

QIR-L `MICRO_GEMM(kernel_family="gemm_neon_8x8", variant="m8_n8_k4")`:

```asm
// Micro-GEMM 8×8 tile with NEON FMA
// A tile: 8×4, B tile: 4×8, C accum: 8×8

// Load A column (4 elements)
LD1   {V0.4S}, [X0], #16     // A[0:4, k]
LD1   {V1.4S}, [X0], #16     // A[4:8, k]

// Load B row (8 elements = 2 NEON registers)
LD1   {V2.4S}, [X1], #16     // B[k, 0:4]
LD1   {V3.4S}, [X1], #16     // B[k, 4:8]

// FMA: C[i,j] += A[i,k] * B[k,j]
FMLA  V16.4S, V0.4S, V2.S[0]  // C[0:4, 0:4] += A[0:4,k] * B[k,0]
FMLA  V17.4S, V0.4S, V2.S[1]  // C[0:4, 0:4] += A[0:4,k] * B[k,1]
FMLA  V18.4S, V0.4S, V2.S[2]
FMLA  V19.4S, V0.4S, V2.S[3]
FMLA  V20.4S, V0.4S, V3.S[0]  // C[0:4, 4:8]
...
FMLA  V23.4S, V1.4S, V3.S[3]  // C[4:8, 4:8]

// Store C tile
ST1   {V16.4S}, [X2], #16
ST1   {V17.4S}, [X2], #16
...
```

**Register allocation:**
- V0–V1: A tile (2 regs)
- V2–V3: B tile (2 regs)
- V16–V31: C accumulator tile (16 regs, 8×8 / 4-wide = 16 vectors)
- Total: 20/32 registers used → well within budget

### 7.3 MICRO_EW → NEON Auto-Vectorized Loop

QIR-L `MICRO_EW(kernel_family="relu", vector_width=4)`:

```asm
// Vectorized ReLU: out[i] = max(0, x[i])
MOVI    V4.4S, #0              // zero vector

MOVZ    X9, #0                 // i = 0
MOVZ    X10, #vec_iters        // limit = N / 4

.Lvec_loop:
  CMP     X9, X10
  B.GE    .Lscalar_tail
  LD1     {V0.4S}, [X0], #16  // load x[i:i+4]
  SMAX    V1.4S, V0.4S, V4.4S // max(x, 0) = ReLU
  ST1     {V1.4S}, [X1], #16  // store out[i:i+4]
  ADD     X9, X9, #1
  B       .Lvec_loop

.Lscalar_tail:                 // Handle N % 4 remainder
  ...scalar loop...
```

### 7.4 Fused Kernel → NEON (Ví dụ: MUL+ADD+RELU chain)

Khi AutoKernelFusionPass fuse `MUL → ADD → RELU` thành FUSED_BIAS_RELU:

```asm
// Fused: out = relu(a * b + c)
// Một loop duy nhất, zero intermediate buffers

MOVI    V7.4S, #0              // zero for ReLU

.Lfused_loop:
  LD1     {V0.4S}, [X0], #16  // load a[i:i+4]
  LD1     {V1.4S}, [X1], #16  // load b[i:i+4]
  LD1     {V2.4S}, [X2], #16  // load c[i:i+4]
  FMUL    V3.4S, V0.4S, V1.4S // a * b (register only)
  FADD    V4.4S, V3.4S, V2.4S // + c   (register only)
  SMAX    V5.4S, V4.4S, V7.4S // relu  (register only)
  ST1     {V5.4S}, [X3], #16  // store out
  SUBS    X9, X9, #1
  B.NE    .Lfused_loop

// Memory traffic: 3 loads + 1 store per 4 elements
// vs unfused: 8 loads + 3 stores per 4 elements
// → 2.75× reduction in memory bandwidth
```

### 7.5 SIMD Intrinsics Registry

Vir cung cấp 11 Grade S intrinsics cho dual-architecture:

| Intrinsic | ARM64 NEON | x86_64 AVX |
|-----------|-----------|------------|
| `simd_add` | `FADD V.4S` | `VADDPS YMM` |
| `simd_sub` | `FSUB V.4S` | `VSUBPS YMM` |
| `simd_mul` | `FMUL V.4S` | `VMULPS YMM` |
| `simd_div` | `FDIV V.4S` | `VDIVPS YMM` |
| `simd_fma` | `FMLA V.4S` | `VFMADD132PS` |
| `simd_load` | `LD1 {V.4S}` | `VMOVUPS YMM` |
| `simd_store` | `ST1 {V.4S}` | `VMOVUPS [mem]` |
| `simd_splat` | `DUP V.4S, W` | `VBROADCASTSS` |
| `simd_reduce_sum` | `ADDV S, V.4S` | `VHADDPS` + shuffle |
| `simd_min` | `SMIN V.4S` | `VMINPS YMM` |
| `simd_max` | `SMAX V.4S` | `VMAXPS YMM` |

### 7.6 Codegen — Safe vs Fast Variants

Code generator tạo **hai variant** cho mỗi patch point:

| Variant | Cơ chế | Hiệu suất | Khi nào dùng |
|---------|--------|-----------|-------------|
| **Safe** | Stack-based, mỗi op push/pop | Baseline | Debug, verify |
| **Fast** | Register-direct, zero stack | 15–40% nhanh hơn | Production |

Cost model chọn variant tại runtime dựa trên workload characteristics.

---

## 8. Data Flow End-to-End: `y = relu(x @ W + b)`

### Bước 1: QIR-H
```
H1: PARAMETER(W)          → W [d_in × d_out]
H2: PARAMETER(b)          → b [d_out]
H3: INPUT(x)              → x [batch × d_in]
H4: LINEAR(H3, H1, H2)   → y [batch × d_out]    ← composite op
H5: RELU(H4)              → out [batch × d_out]
```

### Bước 2: H → M Lowering
```
M1: COPY(W)               → W
M2: COPY(b)               → b
M3: COPY(x)               → x
M4: TRANSPOSE(M1)         → W^T [d_out × d_in]   ← LINEAR decomposed
M5: MATMUL(M3, M4)        → xW [batch × d_out]
M6: ADD(M5, M2)           → xW+b [batch × d_out]
M7: RELU(M6)              → out [batch × d_out]
```

### Bước 3: AutoKernelFusionPass
```
Chain discovered: M6(ADD) → M7(RELU)
  - Single consumer: M6 output chỉ được M7 sử dụng
  - Register pressure: ADD(1) + RELU(1) = 2 ≤ 24 ✓
  - Pattern match: ADD → RELU = FUSED_BIAS_RELU
  - Memory saved: 2 ops (1 STORE + 1 LOAD eliminated)

After fusion:
M1: COPY(W)
M2: COPY(b)
M3: COPY(x)
M4: TRANSPOSE(M1)
M5: MATMUL(M3, M4)
M6: FUSED_BIAS_RELU(M5, M2)    ← M6+M7 merged
    attrs: {fused_chain: ["ADD", "RELU"], memory_ops_saved: 2}
```

### Bước 4: M → L Lowering (NEON, tile_m=8, tile_n=8)
```
L1: SCALAR_OP(copy W)
L2: SCALAR_OP(copy b)
L3: SCALAR_OP(copy x)
L4: KERNEL_CALL(transpose, W)
L5: TILE_LOOP(tile_sizes=(8,8,4), parallel_dim=0)
    └─ L6: MICRO_GEMM(kernel_family="gemm_neon_8x8", variant="m8_n8_k4")
       └─ L7: PREFETCH(distance=2)    // if K > 16
L8: MICRO_EW(kernel_family="fused_bias_relu", vector_width=4, fused=True)
```

### Bước 5: Codegen → ARM64 NEON

```asm
// L6: MICRO_GEMM (8×8 tile)
.Lgemm_tile:
  LD1   {V0.4S-V1.4S}, [X_A]     // load A 8×1 column
  LD1   {V2.4S-V3.4S}, [X_B]     // load B 1×8 row
  FMLA  V16.4S, V0.4S, V2.S[0]   // outer product accumulate
  ...                              // 8×2 = 16 FMLA instructions per k-step
  PRFM  PLDL1KEEP, [X_B, #128]   // L7: PREFETCH next B tile

// L8: FUSED_BIAS_RELU (vectorized)
.Lfused:
  LD1   {V4.4S}, [X_GEMM], #16   // load GEMM result
  LD1   {V5.4S}, [X_BIAS]        // load bias (reused)
  FADD  V6.4S, V4.4S, V5.4S      // + bias
  SMAX  V6.4S, V6.4S, V7.4S      // relu (V7 = zero)
  ST1   {V6.4S}, [X_OUT], #16    // store final
```

---

## 9. So sánh với các hệ thống IR khác

| Feature | XLA (TensorFlow) | TorchScript | MLIR | **Vir Q-IR** |
|---------|------------------|-------------|------|-------------|
| Cấp độ IR | 2 (HLO + LLO) | 1 | N (dialects) | **3 (H/M/L)** |
| Auto fusion | Pattern-based | Limited | Pass-based | **Greedy chain + register pressure** |
| Training support | ✓ | ✓ | ✓ | **✓ (AD tape ở H-level)** |
| SIMD target | GPU-focused | CPU limited | Flexible | **NEON + AVX + AVX512** |
| Register model | GPU warps | None | Backend-dep | **Explicit (24 NEON budget)** |
| CE analysis | No | No | Optional | **Bounds check elimination at M→L** |
| Binary size | >100 MB | >50 MB | Depends | **13.5 KB** |

---

## 10. Kết luận

Q-IR ba cấp độ cho phép Vir đạt được điều mà không framework ML nào khác làm được:

1. **QIR-H** bảo toàn ngữ nghĩa mô hình → AD analysis, training annotations, buffer planning
2. **QIR-M** chuẩn hóa thành canonical ops → AutoKernelFusionPass giảm 20.8% nodes, loại bỏ memory traffic dư thừa
3. **QIR-L** tiling + vectorization → MICRO_GEMM 8×8 tiles, MICRO_EW NEON vector loops, PREFETCH cho cache reuse

Kết quả: **13.5 KB binary** thực hiện inference với hiệu suất trong 24% của C++ hand-optimized, tại machine-epsilon accuracy (5.55e-16), trên 3,055 dòng code.

---

*Document generated from Vir source code: `src/qir/`, `src/virpass/`, `src/virplat/`, `src/backend/codegen/`*
