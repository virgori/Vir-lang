"""
QIR Opcodes — Tensor operation codes for all three IR levels.
==============================================================
Namespace separate from the language-VM Q-IR opcodes in src/ir/instructions/q_ir.py.
These are tensor/training/memory-semantic operations for the AI compiler spine.
"""

from __future__ import annotations

from enum import Enum, auto


# =============================================================================
#  QIR-H Opcodes (High-level, model-semantic)
# =============================================================================

class QIRHOp(Enum):
    """High-level tensor ops preserving model semantics."""

    # ── Tensor creation ─────────────────────────────────────
    CONSTANT = auto()
    PARAMETER = auto()
    INPUT = auto()

    # ── Unary ───────────────────────────────────────────────
    NEG = auto()
    ABS = auto()
    SQRT = auto()
    RSQRT = auto()
    EXP = auto()
    LOG = auto()
    TANH = auto()
    SIGMOID = auto()
    RELU = auto()
    GELU = auto()
    SILU = auto()

    # ── Binary elementwise ──────────────────────────────────
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    POW = auto()
    MAXIMUM = auto()
    MINIMUM = auto()

    # ── Reduction ───────────────────────────────────────────
    REDUCE_SUM = auto()
    REDUCE_MEAN = auto()
    REDUCE_MAX = auto()
    REDUCE_MIN = auto()

    # ── Matrix ops ──────────────────────────────────────────
    MATMUL = auto()
    TRANSPOSE = auto()
    RESHAPE = auto()
    BROADCAST = auto()
    GATHER = auto()
    SCATTER = auto()
    SLICE = auto()
    CONCAT = auto()

    # ── Normalization ───────────────────────────────────────
    LAYER_NORM = auto()
    RMS_NORM = auto()
    SOFTMAX = auto()

    # ── Type ────────────────────────────────────────────────
    CAST = auto()

    # ── Composite (high-level, lowered by passes) ───────────
    LINEAR = auto()
    EMBEDDING = auto()
    ATTENTION = auto()
    MLP_BLOCK = auto()

    # ── Gradient markers ────────────────────────────────────
    GRAD_STOP = auto()
    SAVE_FOR_BACKWARD = auto()

    # ── Memory hints ────────────────────────────────────────
    ALIAS_BARRIER = auto()
    BUFFER_HINT = auto()


# =============================================================================
#  QIR-M Opcodes (Mid-level, canonical normalized tensor ops)
# =============================================================================

class QIRMOp(Enum):
    """Canonical tensor ops after shape inference and normalization."""

    # ── Elementwise (shape-resolved) ────────────────────────
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    NEG = auto()
    ABS = auto()
    SQRT = auto()
    RSQRT = auto()
    EXP = auto()
    LOG = auto()
    TANH = auto()
    SIGMOID = auto()
    RELU = auto()
    GELU = auto()
    SILU = auto()
    POW = auto()
    MAXIMUM = auto()
    MINIMUM = auto()

    # ── Reduction ───────────────────────────────────────────
    REDUCE_SUM = auto()
    REDUCE_MEAN = auto()
    REDUCE_MAX = auto()

    # ── Contraction ─────────────────────────────────────────
    MATMUL = auto()         # shape-verified: (M,K) x (K,N) -> (M,N)
    BATCH_MATMUL = auto()   # shape-verified: (B,M,K) x (B,K,N) -> (B,M,N)

    # ── Data movement ───────────────────────────────────────
    TRANSPOSE = auto()
    RESHAPE = auto()
    BROADCAST = auto()
    GATHER = auto()
    SCATTER = auto()
    SLICE = auto()
    CONCAT = auto()

    # ── Type ────────────────────────────────────────────────
    CAST = auto()

    # ── Fused patterns (post-fusion pass) ───────────────────
    FUSED_MUL_ADD = auto()  # a * b + c fused
    FUSED_BIAS_RELU = auto()
    FUSED_BIAS_GELU = auto()

    # ── Memory ──────────────────────────────────────────────
    ALLOC_BUFFER = auto()
    FREE_BUFFER = auto()
    COPY = auto()

    # ── Bounds checking ─────────────────────────────────────
    BOUNDS_CHECK = auto()   # runtime bounds check (may be eliminated by BCE)


# =============================================================================
#  QIR-L Opcodes (Low-level, scheduling/tiling/vector)
# =============================================================================

class QIRLOp(Enum):
    """Low-level tiled/vectorized ops with scheduling metadata."""

    # ── Tile structure ──────────────────────────────────────
    TILE_LOOP = auto()      # parameterized tile loop
    VECTOR_LOOP = auto()    # inner vector lane loop
    PARALLEL_FOR = auto()   # parallel split hint

    # ── Micro-kernel dispatch ───────────────────────────────
    KERNEL_CALL = auto()    # dispatch to registered kernel family
    MICRO_GEMM = auto()     # tiled GEMM micro-kernel
    MICRO_EW = auto()       # tiled elementwise micro-kernel
    MICRO_REDUCE = auto()   # tiled reduction micro-kernel

    # ── Memory scheduling ───────────────────────────────────
    PREFETCH = auto()
    CACHE_FLUSH = auto()
    BARRIER = auto()

    # ── Memory safety ───────────────────────────────────────
    BOUNDS_CHECK = auto()   # low-level bounds check (not eliminated by BCE)
    STACK_ALLOC = auto()    # stack-promoted allocation
    DET_FREE = auto()       # deterministic free at scope exit

    # ── Scalar fallback ─────────────────────────────────────
    SCALAR_OP = auto()      # fallback scalar operation
