"""Tests for QIR schema — DType, TensorType, QIRHNode."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.qir.schema import DType, TensorType, QIRHNode, QIRMNode, QIRLNode, Layout
from src.qir.opcodes import QIRHOp, QIRMOp, QIRLOp


def test_dtype_properties():
    assert DType.FLOAT32.itemsize == 4
    assert DType.FLOAT16.itemsize == 2
    assert DType.INT64.itemsize == 8
    assert DType.FLOAT32.is_float is True
    assert DType.INT32.is_float is False
    assert DType.INT32.is_int is True
    assert DType.BOOL.itemsize == 1


def test_tensor_type_basics():
    tt = TensorType(dtype=DType.FLOAT32, shape=(2, 3))
    assert tt.rank == 2
    assert tt.numel == 6
    assert tt.nbytes == 24  # 6 * 4
    assert tt.contiguous is True


def test_tensor_type_strides():
    tt = TensorType(dtype=DType.FLOAT32, shape=(4, 8), stride=(8, 1))
    assert tt.rank == 2
    assert tt.numel == 32


def test_tensor_type_with_shape():
    tt = TensorType(dtype=DType.FLOAT32, shape=(2, 3))
    tt2 = tt.with_shape((4, 5))
    assert tt2.shape == (4, 5)
    assert tt2.dtype == DType.FLOAT32


def test_qir_h_node_creation():
    node = QIRHNode(
        node_id=0,
        op=QIRHOp.RELU,
        input_ids=[1],
        output_ids=[2],
        tensor_type=TensorType(dtype=DType.FLOAT32, shape=(16,)),
    )
    assert node.op == QIRHOp.RELU
    assert node.node_id == 0


def test_qir_m_node_creation():
    node = QIRMNode(
        node_id=0,
        op=QIRMOp.ADD,
        input_ids=[1, 2],
        output_ids=[3],
    )
    assert node.op == QIRMOp.ADD


def test_qir_l_node_creation():
    node = QIRLNode(
        node_id=0,
        op=QIRLOp.MICRO_GEMM,
        input_ids=[1, 2],
        output_ids=[3],
        tile_sizes=(64, 64, 64),
        vector_width=8,
    )
    assert node.tile_sizes == (64, 64, 64)
    assert node.vector_width == 8


def test_opcodes_coverage():
    # Verify key ops exist
    assert QIRHOp.MATMUL is not None
    assert QIRHOp.LINEAR is not None
    assert QIRHOp.SOFTMAX is not None
    assert QIRHOp.LAYER_NORM is not None
    assert QIRHOp.ATTENTION is not None
    assert QIRMOp.FUSED_MUL_ADD is not None
    assert QIRMOp.FUSED_BIAS_RELU is not None
    assert QIRLOp.TILE_LOOP is not None
    assert QIRLOp.PARALLEL_FOR is not None
