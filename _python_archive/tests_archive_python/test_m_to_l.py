"""
Tests for M→L lowering pipeline.
==================================
Verifies that QIR-M nodes are correctly lowered to QIR-L form
with proper tile sizes, vector widths, and kernel families.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.qir.module import QIRGraph
from src.qir.schema import QIRMNode, QIRLNode, TensorType, DType
from src.qir.opcodes import QIRMOp, QIRLOp
from src.qir.lower.m_to_l import lower_m_to_l
from src.virplat.capability_profile import CapabilityProfile, VectorBackend
from src.virplat.cpu_probe import CPUInfo


def _make_profile(backend=VectorBackend.NEON, vw=4, tile=8):
    """Create a test capability profile."""
    cpu = CPUInfo(
        arch="arm64", model_name="test",
        physical_cores=4, logical_cores=8,
        l1d_bytes=32768, l2_bytes=262144,
        cache_line_bytes=64,
        has_neon=True,
    )
    return CapabilityProfile(
        cpu=cpu, preferred_backend=backend,
        vector_width_f32=vw, cache_line=64,
        tile_m=tile, tile_n=tile, tile_k=tile // 2,
    )


def _make_graph_with_matmul() -> QIRGraph:
    """Create a graph with a MATMUL node."""
    g = QIRGraph(name="test_matmul")
    tt_in = TensorType(DType.FLOAT32, (4, 8))
    tt_w = TensorType(DType.FLOAT32, (8, 16))
    tt_out = TensorType(DType.FLOAT32, (4, 16))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt_in,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt_w,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.MATMUL, input_ids=(1, 2),
                             tensor_type=tt_out, shape_inferred=True,
                             type_inferred=True,
                             attrs={"M": 4, "K": 8, "N": 16})
    return g


def test_matmul_lowering():
    """MATMUL should produce TILE_LOOP + MICRO_GEMM."""
    g = _make_graph_with_matmul()
    profile = _make_profile()
    lower_m_to_l(g, profile)

    assert len(g.l_nodes) >= 3  # 2 COPY passthroughs + tile + gemm
    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.TILE_LOOP in ops
    assert QIRLOp.MICRO_GEMM in ops

    # Check MICRO_GEMM has proper kernel family
    gemm_nodes = [n for n in g.l_nodes.values() if n.op == QIRLOp.MICRO_GEMM]
    assert len(gemm_nodes) == 1
    assert "gemm_neon" in gemm_nodes[0].kernel_family
    assert gemm_nodes[0].vector_width == 4


def test_elementwise_lowering():
    """Elementwise ops should produce VECTOR_LOOP + MICRO_EW."""
    g = QIRGraph(name="test_ew")
    tt = TensorType(DType.FLOAT32, (64,))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.ADD, input_ids=(1, 2),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True)

    profile = _make_profile()
    lower_m_to_l(g, profile)

    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.VECTOR_LOOP in ops
    assert QIRLOp.MICRO_EW in ops


def test_reduction_lowering():
    """Reduction ops should produce TILE_LOOP + MICRO_REDUCE."""
    g = QIRGraph(name="test_reduce")
    tt_in = TensorType(DType.FLOAT32, (256,))
    tt_out = TensorType(DType.FLOAT32, (1,))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt_in,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.REDUCE_SUM, input_ids=(1,),
                             tensor_type=tt_out, shape_inferred=True,
                             type_inferred=True)

    profile = _make_profile()
    lower_m_to_l(g, profile)

    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.TILE_LOOP in ops
    assert QIRLOp.MICRO_REDUCE in ops


def test_data_movement_lowering():
    """Data movement ops should produce KERNEL_CALL."""
    g = QIRGraph(name="test_dm")
    tt = TensorType(DType.FLOAT32, (4, 8))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.TRANSPOSE, input_ids=(1,),
                             tensor_type=TensorType(DType.FLOAT32, (8, 4)),
                             shape_inferred=True, type_inferred=True)

    profile = _make_profile()
    lower_m_to_l(g, profile)

    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.KERNEL_CALL in ops

    kcall = [n for n in g.l_nodes.values() if n.op == QIRLOp.KERNEL_CALL]
    assert kcall[0].kernel_family == "transpose"


def test_source_mid_id_tracking():
    """All L-nodes should track their source M-node."""
    g = _make_graph_with_matmul()
    profile = _make_profile()
    lower_m_to_l(g, profile)

    for lid, lnode in g.l_nodes.items():
        assert lnode.source_mid_id > 0 or lnode.attrs.get("pass_through")


def test_unary_ops_lowering():
    """All unary ops should lower to VECTOR_LOOP + MICRO_EW."""
    unary_ops = [QIRMOp.NEG, QIRMOp.ABS, QIRMOp.RELU,
                 QIRMOp.SIGMOID, QIRMOp.TANH, QIRMOp.EXP, QIRMOp.LOG]

    for m_op in unary_ops:
        g = QIRGraph(name=f"test_{m_op.name}")
        tt = TensorType(DType.FLOAT32, (32,))
        g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                                 shape_inferred=True, type_inferred=True)
        g.m_nodes[2] = QIRMNode(node_id=2, op=m_op, input_ids=(1,),
                                 tensor_type=tt, shape_inferred=True,
                                 type_inferred=True)
        lower_m_to_l(g, _make_profile())
        ops = [n.op for n in g.l_nodes.values()]
        assert QIRLOp.MICRO_EW in ops, f"{m_op.name} didn't produce MICRO_EW"


def test_prefetch_for_large_k():
    """Large K dimension should trigger PREFETCH node."""
    g = QIRGraph(name="test_prefetch")
    tt = TensorType(DType.FLOAT32, (8, 8))

    g.m_nodes[1] = QIRMNode(node_id=1, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[2] = QIRMNode(node_id=2, op=QIRMOp.COPY, tensor_type=tt,
                             shape_inferred=True, type_inferred=True)
    g.m_nodes[3] = QIRMNode(node_id=3, op=QIRMOp.MATMUL, input_ids=(1, 2),
                             tensor_type=tt, shape_inferred=True,
                             type_inferred=True,
                             attrs={"M": 8, "K": 128, "N": 8})

    profile = _make_profile(tile=8)
    lower_m_to_l(g, profile)

    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.PREFETCH in ops


def test_h_to_m_to_l_full_pipeline():
    """Test complete H→M→L pipeline."""
    from src.qir.opcodes import QIRHOp
    from src.qir.schema import QIRHNode
    from src.qir.lower.h_to_m import lower_h_to_m

    g = QIRGraph(name="pipeline_test")
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

    lower_h_to_m(g)
    assert len(g.m_nodes) > 0

    lower_m_to_l(g, _make_profile())
    assert len(g.l_nodes) > 0

    ops = [n.op for n in g.l_nodes.values()]
    assert QIRLOp.MICRO_GEMM in ops
    assert QIRLOp.MICRO_EW in ops
