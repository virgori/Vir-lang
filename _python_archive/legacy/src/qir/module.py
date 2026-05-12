"""
QIR Module — Graph, Block, Region containers for QIR nodes.
=============================================================
QIRGraph is the top-level container (equivalent to QModule for language-VM IR).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.qir.schema import QIRHNode, QIRMNode, QIRLNode, TensorType, DType
from src.qir.opcodes import QIRHOp


# =============================================================================
#  QIR Region — scoped lifetime / memory region
# =============================================================================

@dataclass
class QIRRegion:
    """Scoped region within a block (for lifetime / alias tracking)."""
    region_id: int
    parent_block_id: int = 0
    node_ids: list[int] = field(default_factory=list)


# =============================================================================
#  QIR Block — basic block of sequential nodes
# =============================================================================

@dataclass
class QIRBlock:
    """A basic block containing sequential QIR nodes."""
    block_id: int
    name: str = ""
    node_ids: list[int] = field(default_factory=list)
    regions: list[QIRRegion] = field(default_factory=list)


# =============================================================================
#  QIR Graph — top-level IR container
# =============================================================================

@dataclass
class QIRGraph:
    """Top-level IR graph holding all nodes, blocks, and metadata.

    Supports all three levels (H/M/L) — typically a graph progresses
    through H -> M -> L via lowering passes.
    """
    name: str = "main"

    # Node storage (keyed by node_id)
    h_nodes: dict[int, QIRHNode] = field(default_factory=dict)
    m_nodes: dict[int, QIRMNode] = field(default_factory=dict)
    l_nodes: dict[int, QIRLNode] = field(default_factory=dict)

    # Block/region structure
    blocks: list[QIRBlock] = field(default_factory=list)

    # Parameter metadata
    param_ids: list[int] = field(default_factory=list)
    input_ids: list[int] = field(default_factory=list)
    output_ids: list[int] = field(default_factory=list)

    # Auto-increment counter
    _next_id: int = field(default=1, repr=False)

    def _alloc_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    # ── QIR-H construction helpers ──────────────────────────

    def add_h_node(self, op: QIRHOp, **kwargs: object) -> int:
        """Create and add a QIR-H node, return its node_id."""
        nid = self._alloc_id()
        node = QIRHNode(node_id=nid, op=op, **kwargs)
        self.h_nodes[nid] = node
        if self.blocks:
            self.blocks[-1].node_ids.append(nid)
        return nid

    def add_parameter(self, name: str, ttype: TensorType) -> int:
        """Add a parameter node (trainable weight)."""
        nid = self.add_h_node(
            QIRHOp.PARAMETER,
            name=name,
            tensor_type=ttype,
            requires_grad=True,
        )
        self.param_ids.append(nid)
        return nid

    def add_input(self, name: str, ttype: TensorType) -> int:
        """Add an input (data) node."""
        nid = self.add_h_node(
            QIRHOp.INPUT,
            name=name,
            tensor_type=ttype,
        )
        self.input_ids.append(nid)
        return nid

    def add_constant(self, name: str, ttype: TensorType, value: object = None) -> int:
        """Add a constant node."""
        attrs = {"value": value} if value is not None else {}
        return self.add_h_node(
            QIRHOp.CONSTANT,
            name=name,
            tensor_type=ttype,
            attrs=attrs,
        )

    def add_op(
        self,
        op: QIRHOp,
        inputs: tuple[int, ...],
        name: str = "",
        tensor_type: TensorType | None = None,
        requires_grad: bool = False,
        **attrs: object,
    ) -> int:
        """Add a compute op node."""
        return self.add_h_node(
            op,
            input_ids=inputs,
            name=name,
            tensor_type=tensor_type,
            requires_grad=requires_grad,
            attrs=attrs if attrs else {},
        )

    def add_block(self, name: str = "") -> QIRBlock:
        """Add a new basic block."""
        blk = QIRBlock(block_id=len(self.blocks), name=name)
        self.blocks.append(blk)
        return blk

    def get_h_node(self, nid: int) -> QIRHNode | None:
        return self.h_nodes.get(nid)

    def get_m_node(self, nid: int) -> QIRMNode | None:
        return self.m_nodes.get(nid)

    @property
    def h_node_count(self) -> int:
        return len(self.h_nodes)

    @property
    def m_node_count(self) -> int:
        return len(self.m_nodes)

    def topo_order_h(self) -> list[int]:
        """Topological sort of H-nodes by dependency order."""
        visited: set[int] = set()
        order: list[int] = []

        def visit(nid: int) -> None:
            if nid in visited:
                return
            visited.add(nid)
            node = self.h_nodes.get(nid)
            if node:
                for inp in node.input_ids:
                    visit(inp)
            order.append(nid)

        for nid in self.h_nodes:
            visit(nid)
        return order
