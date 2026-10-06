"""
Tests for fusion and lowering passes.
========================================
Tests MatmulEpilogueFusionPass, HToMLoweringPass, MToLLoweringPass.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.qir.module import QIRGraph
from src.qir.schema import QIRHNode, QIRMNode, TensorType, DType
from src.qir.opcodes import QIRHOp, QIRMOp, QIRLOp
from src.virpass.passes.lowering import (
    MatmulEpilogueFusionPass,
    HToMLoweringPass,
    MToLLoweringPass,
)


def _make_matmul_bias_relu_graph() -> QIRGraph:
    """Create M-graph: MATMUL → ADD (bias) → RELU."""
    g = QIRGraph(name="matmul_bias_relu")
    tt = TensorType(DType.FLOAT32, (4, 8))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.MATMUL, input_ids=(1, 2),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True, attrs={"M": 4, "K": 8, "N": 8})
    # Bias node (separate input)
    g.m_nodes[4] = QIRMNode(node_id=4, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[5] = QIRMNode(node_id=5, op=QIRMOp.ADD, input_ids=(3, 4),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)
    g.m_nodes[6] = QIRMNode(node_id=6, op=QIRMOp.RELU, input_ids=(5,),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)
    return g


def _make_matmul_bias_graph() -> QIRGraph:
    """Create M-graph: MATMUL → ADD (bias) only."""
    g = QIRGraph(name="matmul_bias")
    tt = TensorType(DType.FLOAT32, (4, 8))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.MATMUL, input_ids=(1, 2),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True, attrs={"M": 4, "K": 8, "N": 8})
    g.m_nodes[4] = QIRMNode(node_id=4, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[5] = QIRMNode(node_id=5, op=QIRMOp.ADD, input_ids=(3, 4),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)
    return g


# =============================================================================
#  MatmulEpilogueFusionPass
# =============================================================================

def test_matmul_bias_relu_fusion():
    """MATMUL + ADD + RELU should fuse into FUSED_BIAS_RELU."""
    g = _make_matmul_bias_relu_graph()
    fusion = MatmulEpilogueFusionPass()
    result = fusion.run(g)
    assert result.changed
    assert result.stats.get("fused_matmul_epilogues", 0) >= 1

    # MATMUL and ADD should be removed
    ops = {n.op for n in g.m_nodes.values()}
    assert QIRMOp.MATMUL not in ops
    # FUSED_BIAS_RELU should be present
    assert QIRMOp.FUSED_BIAS_RELU in ops


def test_matmul_bias_only_fusion():
    """MATMUL + ADD should fuse into FUSED_MUL_ADD."""
    g = _make_matmul_bias_graph()
    fusion = MatmulEpilogueFusionPass()
    result = fusion.run(g)
    assert result.changed
    ops = {n.op for n in g.m_nodes.values()}
    assert QIRMOp.MATMUL not in ops
    assert QIRMOp.FUSED_MUL_ADD in ops


def test_no_fusion_when_multiple_consumers():
    """If MATMUL has multiple consumers, don't fuse."""
    g = QIRGraph(name="no_fuse")
    tt = TensorType(DType.FLOAT32, (4, 8))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.MATMUL, input_ids=(1, 2),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)
    # Two consumers of matmul
    g.m_nodes[4] = QIRMNode(node_id=4, op=QIRMOp.ADD, input_ids=(3, 1),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)
    g.m_nodes[5] = QIRMNode(node_id=5, op=QIRMOp.RELU, input_ids=(3,),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)

    fusion = MatmulEpilogueFusionPass()
    result = fusion.run(g)
    assert not result.changed


def test_empty_graph_fusion():
    g = QIRGraph(name="empty")
    fusion = MatmulEpilogueFusionPass()
    result = fusion.run(g)
    assert not result.changed


# =============================================================================
#  HToMLoweringPass
# =============================================================================

def test_h_to_m_pass():
    """HToMLoweringPass should create M-nodes from H-nodes."""
    g = QIRGraph(name="h_to_m_pass")
    tt = TensorType(DType.FLOAT32, (4, 8))

    g.h_nodes[1] = QIRHNode(node_id=1, op=QIRHOp.INPUT, tensor_type=tt)
    g.h_nodes[2] = QIRHNode(node_id=2, op=QIRHOp.RELU, input_ids=(1,),
                             tensor_type=tt)

    lowering = HToMLoweringPass()
    result = lowering.run(g)
    assert result.changed
    assert len(g.m_nodes) > 0


# =============================================================================
#  MToLLoweringPass
# =============================================================================

def test_m_to_l_pass():
    """MToLLoweringPass should create L-nodes from M-nodes."""
    g = QIRGraph(name="m_to_l_pass")
    tt = TensorType(DType.FLOAT32, (32,))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.RELU, input_ids=(1,),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)

    lowering = MToLLoweringPass()
    result = lowering.run(g)
    assert result.changed
    assert len(g.l_nodes) > 0
    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.MICRO_EW in ops


# =============================================================================
#  Full pipeline: H→M (fuse) → L
# =============================================================================

def test_full_lowering_pipeline():
    """Complete: H→M → Fusion → M→L."""
    g = QIRGraph(name="full_pipeline")
    tt_x = TensorType(DType.FLOAT32, (2, 4))
    tt_w = TensorType(DType.FLOAT32, (4, 8))
    tt_out = TensorType(DType.FLOAT32, (2, 8))

    g.h_nodes[1] = QIRHNode(node_id=1, op=QIRHOp.INPUT, tensor_type=tt_x)
    g.h_nodes[2] = QIRHNode(node_id=2, op=QIRHOp.PARAMETER, tensor_type=tt_w)
    g.h_nodes[3] = QIRHNode(node_id=3, op=QIRHOp.MATMUL,
                             input_ids=(1, 2), tensor_type=tt_out,
                             attrs={"M": 2, "K": 4, "N": 8})
    g.h_nodes[4] = QIRHNode(node_id=4, op=QIRHOp.RELU,
                             input_ids=(3,), tensor_type=tt_out)

    # H → M
    h2m = HToMLoweringPass()
    h2m.run(g)
    assert len(g.m_nodes) > 0

    # M → L
    m2l = MToLLoweringPass()
    m2l.run(g)
    assert len(g.l_nodes) > 0
