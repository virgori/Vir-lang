"""
Scalar reference kernels — Correct-by-construction baseline.
=============================================================
Every vector/SIMD kernel must match these results within tolerance.
These operate on flat lists (poor locality) for correctness verification.
"""

from __future__ import annotations

import math

from src.virmatrix.registry import register_kernel
from src.virplat.capability_profile import VectorBackend


# =============================================================================
#  GEMM (General Matrix Multiply)
# =============================================================================

@register_kernel("matmul", VectorBackend.SCALAR)
def matmul_scalar(
    a: list[float], b: list[float],
    m: int, k: int, n: int,
) -> list[float]:
    """C[m,n] = A[m,k] @ B[k,n]  —  naive triple loop."""
    c = [0.0] * (m * n)
    for i in range(m):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += a[i * k + p] * b[p * n + j]
            c[i * n + j] = s
    return c


@register_kernel("matmul_tiled", VectorBackend.SCALAR)
def matmul_tiled_scalar(
    a: list[float], b: list[float],
    m: int, k: int, n: int,
    tile: int = 8,
) -> list[float]:
    """Tiled GEMM for better cache reuse."""
    c = [0.0] * (m * n)
    for i0 in range(0, m, tile):
        for j0 in range(0, n, tile):
            for p0 in range(0, k, tile):
                for i in range(i0, min(i0 + tile, m)):
                    for j in range(j0, min(j0 + tile, n)):
                        s = 0.0
                        for p in range(p0, min(p0 + tile, k)):
                            s += a[i * k + p] * b[p * n + j]
                        c[i * n + j] += s
    return c


# =============================================================================
#  Elementwise ops
# =============================================================================

@register_kernel("add", VectorBackend.SCALAR)
def add_scalar(a: list[float], b: list[float]) -> list[float]:
    return [x + y for x, y in zip(a, b)]


@register_kernel("sub", VectorBackend.SCALAR)
def sub_scalar(a: list[float], b: list[float]) -> list[float]:
    return [x - y for x, y in zip(a, b)]


@register_kernel("mul", VectorBackend.SCALAR)
def mul_scalar(a: list[float], b: list[float]) -> list[float]:
    return [x * y for x, y in zip(a, b)]


@register_kernel("div", VectorBackend.SCALAR)
def div_scalar(a: list[float], b: list[float]) -> list[float]:
    return [x / y if y != 0 else 0.0 for x, y in zip(a, b)]


@register_kernel("neg", VectorBackend.SCALAR)
def neg_scalar(a: list[float]) -> list[float]:
    return [-x for x in a]


@register_kernel("abs", VectorBackend.SCALAR)
def abs_scalar(a: list[float]) -> list[float]:
    return [abs(x) for x in a]


@register_kernel("sqrt", VectorBackend.SCALAR)
def sqrt_scalar(a: list[float]) -> list[float]:
    return [math.sqrt(max(0.0, x)) for x in a]


@register_kernel("rsqrt", VectorBackend.SCALAR)
def rsqrt_scalar(a: list[float]) -> list[float]:
    return [1.0 / math.sqrt(max(1e-12, x)) for x in a]


@register_kernel("exp", VectorBackend.SCALAR)
def exp_scalar(a: list[float]) -> list[float]:
    return [math.exp(min(x, 88.0)) for x in a]  # clamp to avoid overflow


@register_kernel("log", VectorBackend.SCALAR)
def log_scalar(a: list[float]) -> list[float]:
    return [math.log(max(1e-12, x)) for x in a]


# =============================================================================
#  Activation functions
# =============================================================================

@register_kernel("relu", VectorBackend.SCALAR)
def relu_scalar(a: list[float]) -> list[float]:
    return [max(0.0, x) for x in a]


@register_kernel("sigmoid", VectorBackend.SCALAR)
def sigmoid_scalar(a: list[float]) -> list[float]:
    def _sig(x: float) -> float:
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        ex = math.exp(x)
        return ex / (1.0 + ex)
    return [_sig(x) for x in a]


@register_kernel("tanh", VectorBackend.SCALAR)
def tanh_scalar(a: list[float]) -> list[float]:
    return [math.tanh(x) for x in a]


@register_kernel("gelu", VectorBackend.SCALAR)
def gelu_scalar(a: list[float]) -> list[float]:
    """GELU approximation: x * 0.5 * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))"""
    c = math.sqrt(2.0 / math.pi)
    return [x * 0.5 * (1.0 + math.tanh(c * (x + 0.044715 * x * x * x))) for x in a]


@register_kernel("silu", VectorBackend.SCALAR)
def silu_scalar(a: list[float]) -> list[float]:
    """SiLU / Swish: x * sigmoid(x)"""
    def _sig(x: float) -> float:
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        ex = math.exp(x)
        return ex / (1.0 + ex)
    return [x * _sig(x) for x in a]


# =============================================================================
#  Reduction
# =============================================================================

@register_kernel("reduce_sum", VectorBackend.SCALAR)
def reduce_sum_scalar(a: list[float]) -> float:
    return sum(a)


@register_kernel("reduce_mean", VectorBackend.SCALAR)
def reduce_mean_scalar(a: list[float]) -> float:
    return sum(a) / len(a) if a else 0.0


@register_kernel("reduce_max", VectorBackend.SCALAR)
def reduce_max_scalar(a: list[float]) -> float:
    return max(a) if a else float("-inf")


# =============================================================================
#  Normalization
# =============================================================================

@register_kernel("softmax", VectorBackend.SCALAR)
def softmax_scalar(a: list[float]) -> list[float]:
    mx = max(a) if a else 0.0
    exps = [math.exp(min(x - mx, 88.0)) for x in a]
    total = sum(exps)
    return [e / total for e in exps] if total > 0 else exps


@register_kernel("layer_norm", VectorBackend.SCALAR)
def layer_norm_scalar(
    x: list[float], gamma: list[float], beta: list[float],
    eps: float = 1e-5,
) -> list[float]:
    """Layer normalization over last dimension."""
    n = len(x)
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / n
    inv_std = 1.0 / math.sqrt(var + eps)
    return [(v - mean) * inv_std * g + b for v, g, b in zip(x, gamma, beta)]


@register_kernel("rms_norm", VectorBackend.SCALAR)
def rms_norm_scalar(
    x: list[float], gamma: list[float], eps: float = 1e-5,
) -> list[float]:
    """RMS normalization."""
    n = len(x)
    rms = math.sqrt(sum(v * v for v in x) / n + eps)
    return [v / rms * g for v, g in zip(x, gamma)]


# =============================================================================
#  Fill / scale
# =============================================================================

@register_kernel("fill", VectorBackend.SCALAR)
def fill_scalar(n: int, value: float) -> list[float]:
    return [value] * n


@register_kernel("scale", VectorBackend.SCALAR)
def scale_scalar(a: list[float], s: float) -> list[float]:
    return [x * s for x in a]


@register_kernel("axpy", VectorBackend.SCALAR)
def axpy_scalar(a: list[float], x: list[float], y: list[float]) -> list[float]:
    """y = a*x + y (scalar a broadcast)"""
    alpha = a[0] if isinstance(a, list) else a  # type: ignore[assignment]
    return [alpha * xi + yi for xi, yi in zip(x, y)]
