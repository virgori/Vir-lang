"""
QIR Schema — Node definitions for all three IR levels.
=======================================================
Immutable, SSA-style nodes with full tensor semantics.

Design principles:
  - frozen dataclasses for immutability (matches existing Q-IR style)
  - Integer-only shape metadata (no symbolic shapes yet)
  - Explicit gradient/memory/alias annotations per node
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from src.qir.opcodes import QIRHOp, QIRMOp, QIRLOp


# =============================================================================
#  Data Types
# =============================================================================

class DType(Enum):
    """Tensor element data types."""
    FLOAT32 = auto()
    FLOAT16 = auto()
    BFLOAT16 = auto()
    FLOAT64 = auto()
    INT32 = auto()
    INT64 = auto()
    INT8 = auto()
    UINT8 = auto()
    BOOL = auto()

    @property
    def itemsize(self) -> int:
        _sizes = {
            DType.FLOAT32: 4, DType.FLOAT16: 2, DType.BFLOAT16: 2,
            DType.FLOAT64: 8, DType.INT32: 4, DType.INT64: 8,
            DType.INT8: 1, DType.UINT8: 1, DType.BOOL: 1,
        }
        return _sizes[self]

    @property
    def is_float(self) -> bool:
        return self in (DType.FLOAT32, DType.FLOAT16, DType.BFLOAT16, DType.FLOAT64)

    @property
    def is_int(self) -> bool:
        return self in (DType.INT32, DType.INT64, DType.INT8, DType.UINT8)


# =============================================================================
#  Tensor Type — shape + dtype + layout metadata
# =============================================================================

class Layout(Enum):
    ROW_MAJOR = auto()     # C-contiguous
    COL_MAJOR = auto()     # Fortran-contiguous


@dataclass(frozen=True)
class TensorType:
    """Type descriptor for a tensor value in QIR."""
    dtype: DType = DType.FLOAT32
    shape: tuple[int, ...] = ()
    stride: tuple[int, ...] | None = None     # None = contiguous default
    layout: Layout = Layout.ROW_MAJOR
    contiguous: bool = True

    @property
    def rank(self) -> int:
        return len(self.shape)

    @property
    def numel(self) -> int:
        n = 1
        for s in self.shape:
            n *= s
        return n

    @property
    def nbytes(self) -> int:
        return self.numel * self.dtype.itemsize

    def with_shape(self, new_shape: tuple[int, ...]) -> TensorType:
        return TensorType(
            dtype=self.dtype, shape=new_shape, stride=None,
            layout=self.layout, contiguous=True,
        )


# =============================================================================
#  QIR-H Node — High-level model-semantic IR
# =============================================================================

@dataclass(frozen=True)
class QIRHNode:
    """High-level IR node preserving model semantics.

    Fields mirror the design plan §4.1.A:
      - Identity: node_id, op, input_ids, output_ids, block_id, region_id
      - Tensor: dtype, shape, rank, stride, layout, contiguous, broadcast
      - Training: requires_grad, stop_gradient, saved_for_backward
      - Memory: alias_group, is_view, mutable, inplace_safe, lifetime_region, buffer_hint
    """
    # Identity
    node_id: int
    op: QIRHOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()
    block_id: int = 0
    region_id: int = 0
    name: str = ""

    # Tensor semantics (output type)
    tensor_type: TensorType | None = None

    # Attributes (op-specific)
    attrs: dict[str, object] = field(default_factory=dict)

    # Training annotations
    requires_grad: bool = False
    stop_gradient: bool = False
    saved_for_backward: bool = False

    # Memory annotations
    alias_group: int = 0           # 0 = no aliasing
    is_view: bool = False
    mutable: bool = False
    inplace_safe: bool = False
    lifetime_region: int = 0       # 0 = default region
    buffer_hint: str = ""          # hint for memory planner


# =============================================================================
#  QIR-M Node — Mid-level canonical ops
# =============================================================================

@dataclass(frozen=True)
class QIRMNode:
    """Mid-level IR node with shape-resolved canonical ops."""
    node_id: int
    op: QIRMOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()

    # Resolved tensor type
    tensor_type: TensorType | None = None

    # Dataflow metadata
    shape_inferred: bool = False
    type_inferred: bool = False

    # Scheduling hints (carried from QIR-H)
    alias_group: int = 0
    inplace_safe: bool = False
    lifetime_region: int = 0

    # Attributes
    attrs: dict[str, object] = field(default_factory=dict)


# =============================================================================
#  QIR-L Node — Low-level tiled/scheduled ops
# =============================================================================

@dataclass(frozen=True)
class QIRLNode:
    """Low-level IR node with tile/vector/scheduling metadata."""
    node_id: int
    op: QIRLOp
    input_ids: tuple[int, ...] = ()
    output_ids: tuple[int, ...] = ()

    # Tile metadata
    tile_sizes: tuple[int, ...] = ()
    vector_width: int = 1
    parallel_dim: int = -1         # -1 = sequential

    # Kernel dispatch
    kernel_family: str = ""        # e.g. "gemm_neon_8x8"
    kernel_variant: str = ""       # e.g. "m8_n8_k4"

    # Memory scheduling
    prefetch_distance: int = 0
    buffer_id: int = 0

    # Parent reference for lowering trace
    source_mid_id: int = 0

    # Attributes
    attrs: dict[str, object] = field(default_factory=dict)
