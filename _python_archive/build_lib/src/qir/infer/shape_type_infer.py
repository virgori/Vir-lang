"""
QIR Shape & Type Inference — Propagates tensor types through the H-graph.
=========================================================================
"""

from __future__ import annotations

from src.qir.module import QIRGraph
from src.qir.schema import QIRHNode, TensorType, DType
from src.qir.opcodes import QIRHOp


# Ops that preserve shape from first input
_UNARY_PRESERVE = frozenset({
    QIRHOp.NEG, QIRHOp.ABS, QIRHOp.SQRT, QIRHOp.RSQRT, QIRHOp.EXP,
    QIRHOp.LOG, QIRHOp.TANH, QIRHOp.SIGMOID, QIRHOp.RELU, QIRHOp.GELU,
    QIRHOp.SILU,
})

# Binary elementwise ops: broadcast shapes
_BINARY_EW = frozenset({
    QIRHOp.ADD, QIRHOp.SUB, QIRHOp.MUL, QIRHOp.DIV,
    QIRHOp.POW, QIRHOp.MAXIMUM, QIRHOp.MINIMUM,
})


def _broadcast_shapes(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, ...] | None:
    """Compute broadcast shape, return None if incompatible."""
    rank = max(len(a), len(b))
    pa = (1,) * (rank - len(a)) + a
    pb = (1,) * (rank - len(b)) + b
    result: list[int] = []
    for da, db in zip(pa, pb):
        if da == db:
            result.append(da)
        elif da == 1:
            result.append(db)
        elif db == 1:
            result.append(da)
        else:
            return None  # incompatible
    return tuple(result)


def _infer_matmul_shape(
    a: tuple[int, ...], b: tuple[int, ...]
) -> tuple[int, ...] | None:
    """Infer matmul output shape. Supports 2D and batched."""
    if len(a) < 2 or len(b) < 2:
        return None
    if a[-1] != b[-2]:
        return None  # K dimension mismatch
    # Batch broadcast
    batch_a, batch_b = a[:-2], b[:-2]
    batch = _broadcast_shapes(batch_a, batch_b) if (batch_a or batch_b) else ()
    if batch is None:
        return None
    return batch + (a[-2], b[-1])


def _infer_reduce_shape(
    shape: tuple[int, ...], axis: int, keepdim: bool = False
) -> tuple[int, ...]:
    """Infer reduction output shape."""
    if axis < 0:
        axis = len(shape) + axis
    if axis < 0 or axis >= len(shape):
        return shape  # invalid axis, verifier will catch
    result = list(shape)
    if keepdim:
        result[axis] = 1
    else:
        result.pop(axis)
    return tuple(result) if result else (1,)


class ShapeTypeInfer:
    """Run shape and type inference on a QIR-H graph.

    Traverses nodes in topological order, computing output TensorType
    for each node based on its inputs and op semantics.
    """

    def __init__(self, graph: QIRGraph) -> None:
        self.graph = graph
        self.errors: list[str] = []
        self._resolved: dict[int, TensorType] = {}

    def run(self) -> bool:
        """Run inference. Returns True if all nodes resolved without errors."""
        self.errors.clear()
        self._resolved.clear()

        # Seed from nodes that already have tensor_type
        for nid, node in self.graph.h_nodes.items():
            if node.tensor_type is not None:
                self._resolved[nid] = node.tensor_type

        # Topo-order traversal
        for nid in self.graph.topo_order_h():
            node = self.graph.h_nodes.get(nid)
            if node is None:
                continue
            if nid in self._resolved:
                continue
            inferred = self._infer_node(node)
            if inferred is not None:
                self._resolved[nid] = inferred
                # Update node with inferred type
                updated = QIRHNode(
                    node_id=node.node_id, op=node.op,
                    input_ids=node.input_ids, output_ids=node.output_ids,
                    block_id=node.block_id, region_id=node.region_id,
                    name=node.name, tensor_type=inferred,
                    attrs=node.attrs,
                    requires_grad=node.requires_grad,
                    stop_gradient=node.stop_gradient,
                    saved_for_backward=node.saved_for_backward,
                    alias_group=node.alias_group, is_view=node.is_view,
                    mutable=node.mutable, inplace_safe=node.inplace_safe,
                    lifetime_region=node.lifetime_region,
                    buffer_hint=node.buffer_hint,
                )
                self.graph.h_nodes[nid] = updated

        return len(self.errors) == 0

    def get_type(self, nid: int) -> TensorType | None:
        return self._resolved.get(nid)

    def _input_type(self, nid: int) -> TensorType | None:
        return self._resolved.get(nid)

    def _infer_node(self, node: QIRHNode) -> TensorType | None:
        op = node.op

        # Unary ops: preserve input shape/dtype
        if op in _UNARY_PRESERVE:
            if not node.input_ids:
                self.errors.append(f"Node {node.node_id} ({op.name}): missing input")
                return None
            it = self._input_type(node.input_ids[0])
            if it is None:
                self.errors.append(
                    f"Node {node.node_id} ({op.name}): unresolved input {node.input_ids[0]}")
                return None
            return it

        # Binary elementwise: broadcast
        if op in _BINARY_EW:
            if len(node.input_ids) < 2:
                self.errors.append(f"Node {node.node_id} ({op.name}): need 2 inputs")
                return None
            ta = self._input_type(node.input_ids[0])
            tb = self._input_type(node.input_ids[1])
            if ta is None or tb is None:
                self.errors.append(f"Node {node.node_id} ({op.name}): unresolved input types")
                return None
            out_shape = _broadcast_shapes(ta.shape, tb.shape)
            if out_shape is None:
                self.errors.append(
                    f"Node {node.node_id} ({op.name}): "
                    f"incompatible shapes {ta.shape} vs {tb.shape}")
                return None
            return TensorType(dtype=ta.dtype, shape=out_shape)

        # Matmul
        if op == QIRHOp.MATMUL:
            if len(node.input_ids) < 2:
                self.errors.append(f"Node {node.node_id} (MATMUL): need 2 inputs")
                return None
            ta = self._input_type(node.input_ids[0])
            tb = self._input_type(node.input_ids[1])
            if ta is None or tb is None:
                self.errors.append(f"Node {node.node_id} (MATMUL): unresolved input types")
                return None
            out_shape = _infer_matmul_shape(ta.shape, tb.shape)
            if out_shape is None:
                self.errors.append(
                    f"Node {node.node_id} (MATMUL): shape mismatch {ta.shape} x {tb.shape}")
                return None
            return TensorType(dtype=ta.dtype, shape=out_shape)

        # Linear: out = x @ W^T + bias
        if op == QIRHOp.LINEAR:
            if len(node.input_ids) < 2:
                self.errors.append(f"Node {node.node_id} (LINEAR): need >= 2 inputs")
                return None
            ta = self._input_type(node.input_ids[0])  # x: (*, in)
            tw = self._input_type(node.input_ids[1])  # W: (out, in)
            if ta is None or tw is None:
                self.errors.append(f"Node {node.node_id} (LINEAR): unresolved input types")
                return None
            if ta.rank < 1 or tw.rank != 2:
                self.errors.append(
                    f"Node {node.node_id} (LINEAR): invalid ranks x={ta.rank}, W={tw.rank}")
                return None
            if ta.shape[-1] != tw.shape[1]:
                self.errors.append(
                    f"Node {node.node_id} (LINEAR): "
                    f"in_features mismatch {ta.shape[-1]} vs {tw.shape[1]}")
                return None
            out_shape = ta.shape[:-1] + (tw.shape[0],)
            return TensorType(dtype=ta.dtype, shape=out_shape)

        # Reduction
        if op in (QIRHOp.REDUCE_SUM, QIRHOp.REDUCE_MEAN, QIRHOp.REDUCE_MAX, QIRHOp.REDUCE_MIN):
            if not node.input_ids:
                self.errors.append(f"Node {node.node_id} ({op.name}): missing input")
                return None
            it = self._input_type(node.input_ids[0])
            if it is None:
                return None
            axis = node.attrs.get("axis", -1)
            if not isinstance(axis, int):
                axis = -1
            out_shape = _infer_reduce_shape(it.shape, axis)
            return TensorType(dtype=it.dtype, shape=out_shape)

        # Reshape
        if op == QIRHOp.RESHAPE:
            if not node.input_ids:
                return None
            it = self._input_type(node.input_ids[0])
            if it is None:
                return None
            new_shape = node.attrs.get("new_shape", ())
            if isinstance(new_shape, tuple) and new_shape:
                return it.with_shape(new_shape)
            return it

        # Transpose (2D swap)
        if op == QIRHOp.TRANSPOSE:
            if not node.input_ids:
                return None
            it = self._input_type(node.input_ids[0])
            if it is None:
                return None
            perm = node.attrs.get("perm", ())
            if isinstance(perm, tuple) and perm:
                new_shape = tuple(it.shape[p] for p in perm if p < len(it.shape))
                return it.with_shape(new_shape)
            if it.rank == 2:
                return it.with_shape((it.shape[1], it.shape[0]))
            return it

        # Cast
        if op == QIRHOp.CAST:
            if not node.input_ids:
                return None
            it = self._input_type(node.input_ids[0])
            if it is None:
                return None
            target_dtype = node.attrs.get("target_dtype", it.dtype)
            if isinstance(target_dtype, DType):
                return TensorType(dtype=target_dtype, shape=it.shape)
            return it

        # Softmax / LayerNorm / RMSNorm: preserve shape
        if op in (QIRHOp.SOFTMAX, QIRHOp.LAYER_NORM, QIRHOp.RMS_NORM):
            if not node.input_ids:
                return None
            it = self._input_type(node.input_ids[0])
            return it

        # Embedding: indices -> (*, embed_dim)
        if op == QIRHOp.EMBEDDING:
            if len(node.input_ids) < 2:
                return None
            t_idx = self._input_type(node.input_ids[0])
            t_weight = self._input_type(node.input_ids[1])
            if t_idx is None or t_weight is None:
                return None
            # weight: (vocab, embed_dim), indices: (*,) -> (*, embed_dim)
            out_shape = t_idx.shape + (t_weight.shape[-1],)
            return TensorType(dtype=t_weight.dtype, shape=out_shape)

        # Grad markers: transparent
        if op in (QIRHOp.GRAD_STOP, QIRHOp.SAVE_FOR_BACKWARD):
            if node.input_ids:
                return self._input_type(node.input_ids[0])
            return None

        return None
