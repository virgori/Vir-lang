"""
QIR — Tensor Compiler IR for Vir AI
====================================
Three-level IR spine:
  QIR-H (High): Model-level ops with full tensor semantics
  QIR-M (Mid):  Canonical normalized tensor ops
  QIR-L (Low):  Tile/loop/vector scheduling metadata
"""

from src.qir.schema import (
    DType,
    TensorType,
    QIRHNode,
    QIRMNode,
    QIRLNode,
)
from src.qir.opcodes import QIRHOp, QIRMOp, QIRLOp
from src.qir.module import QIRGraph, QIRBlock, QIRRegion

__all__ = [
    "DType",
    "TensorType",
    "QIRHNode",
    "QIRMNode",
    "QIRLNode",
    "QIRHOp",
    "QIRMOp",
    "QIRLOp",
    "QIRGraph",
    "QIRBlock",
    "QIRRegion",
]
