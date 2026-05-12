"""
QIR Graph Builder — Fluent API for constructing QIR-H graphs from model definitions.
=====================================================================================
"""

from __future__ import annotations

from src.qir.module import QIRGraph
from src.qir.schema import TensorType, DType
from src.qir.opcodes import QIRHOp


class QIRBuilder:
    """Fluent builder for constructing QIR-H model graphs.

    Usage:
        b = QIRBuilder("my_model")
        x = b.input("x", DType.FLOAT32, (batch, features))
        w1 = b.parameter("w1", DType.FLOAT32, (features, hidden))
        h = b.matmul(x, w1)
        h = b.relu(h)
        graph = b.build()
    """

    def __init__(self, name: str = "main") -> None:
        self.graph = QIRGraph(name=name)
        self.graph.add_block("entry")

    # ── Tensor creation ─────────────────────────────────────

    def input(self, name: str, dtype: DType, shape: tuple[int, ...]) -> int:
        return self.graph.add_input(name, TensorType(dtype=dtype, shape=shape))

    def parameter(self, name: str, dtype: DType, shape: tuple[int, ...]) -> int:
        return self.graph.add_parameter(name, TensorType(dtype=dtype, shape=shape))

    def constant(self, name: str, dtype: DType, shape: tuple[int, ...],
                 value: object = None) -> int:
        return self.graph.add_constant(name, TensorType(dtype=dtype, shape=shape), value)

    # ── Unary ops ───────────────────────────────────────────

    def relu(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.RELU, (x,), name=name)

    def gelu(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.GELU, (x,), name=name)

    def silu(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.SILU, (x,), name=name)

    def tanh(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.TANH, (x,), name=name)

    def sigmoid(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.SIGMOID, (x,), name=name)

    def neg(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.NEG, (x,), name=name)

    def sqrt(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.SQRT, (x,), name=name)

    def rsqrt(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.RSQRT, (x,), name=name)

    def exp(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.EXP, (x,), name=name)

    def log(self, x: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.LOG, (x,), name=name)

    # ── Binary ops ──────────────────────────────────────────

    def add(self, a: int, b: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.ADD, (a, b), name=name)

    def sub(self, a: int, b: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.SUB, (a, b), name=name)

    def mul(self, a: int, b: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.MUL, (a, b), name=name)

    def div(self, a: int, b: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.DIV, (a, b), name=name)

    # ── Matrix ops ──────────────────────────────────────────

    def matmul(self, a: int, b: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.MATMUL, (a, b), name=name)

    def transpose(self, x: int, name: str = "", perm: tuple[int, ...] = ()) -> int:
        return self.graph.add_op(QIRHOp.TRANSPOSE, (x,), name=name, perm=perm)

    def reshape(self, x: int, name: str = "", new_shape: tuple[int, ...] = ()) -> int:
        return self.graph.add_op(QIRHOp.RESHAPE, (x,), name=name, new_shape=new_shape)

    # ── Reduction ───────────────────────────────────────────

    def reduce_sum(self, x: int, name: str = "", axis: int = -1) -> int:
        return self.graph.add_op(QIRHOp.REDUCE_SUM, (x,), name=name, axis=axis)

    def reduce_mean(self, x: int, name: str = "", axis: int = -1) -> int:
        return self.graph.add_op(QIRHOp.REDUCE_MEAN, (x,), name=name, axis=axis)

    # ── Normalization ───────────────────────────────────────

    def layer_norm(self, x: int, weight: int, bias: int, name: str = "",
                   eps: float = 1e-5) -> int:
        return self.graph.add_op(QIRHOp.LAYER_NORM, (x, weight, bias), name=name, eps=eps)

    def rms_norm(self, x: int, weight: int, name: str = "", eps: float = 1e-5) -> int:
        return self.graph.add_op(QIRHOp.RMS_NORM, (x, weight), name=name, eps=eps)

    def softmax(self, x: int, name: str = "", axis: int = -1) -> int:
        return self.graph.add_op(QIRHOp.SOFTMAX, (x,), name=name, axis=axis)

    # ── Type ────────────────────────────────────────────────

    def cast(self, x: int, target_dtype: DType, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.CAST, (x,), name=name, target_dtype=target_dtype)

    # ── Composite (high-level) ──────────────────────────────

    def linear(self, x: int, weight: int, bias: int | None = None,
               name: str = "") -> int:
        """Linear layer: out = x @ weight.T + bias"""
        inputs = (x, weight, bias) if bias is not None else (x, weight)
        return self.graph.add_op(QIRHOp.LINEAR, inputs, name=name)

    def embedding(self, indices: int, weight: int, name: str = "") -> int:
        return self.graph.add_op(QIRHOp.EMBEDDING, (indices, weight), name=name)

    # ── Build ───────────────────────────────────────────────

    def build(self) -> QIRGraph:
        """Return the constructed graph."""
        return self.graph
