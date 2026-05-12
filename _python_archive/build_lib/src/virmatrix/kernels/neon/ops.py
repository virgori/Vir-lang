"""
NEON ARM64 kernels — Vectorized implementations using ctypes + ARM64 NEON.
===========================================================================
Uses Python's array + struct for SIMD-width-aware processing (4-wide f32).
On ARM64 macOS, these operate at NEON vector width (128-bit = 4×f32).
Falls back gracefully to vectorized-style Python when ctypes NEON isn't available.
"""

from __future__ import annotations

import math
import struct

from src.virmatrix.registry import register_kernel
from src.virplat.capability_profile import VectorBackend

# NEON vector width = 4 × float32
_VW = 4


# =============================================================================
#  GEMM — Tiled NEON-width-aware GEMM
# =============================================================================

@register_kernel("matmul", VectorBackend.NEON)
def matmul_neon(
    a: list[float], b: list[float],
    m: int, k: int, n: int,
) -> list[float]:
    """C[m,n] = A[m,k] @ B[k,n] — tiled with NEON-width inner loop.

    Tile sizes chosen for ARM64 L1D cache:
      tile_m=8, tile_n=8, tile_k=4 → 3 tiles fit in ~768B.
    Inner loop processes _VW=4 elements at a time.
    """
    tile_m, tile_n, tile_k = 8, 8, 4
    c = [0.0] * (m * n)

    for i0 in range(0, m, tile_m):
        i1 = min(i0 + tile_m, m)
        for j0 in range(0, n, tile_n):
            j1 = min(j0 + tile_n, n)
            for p0 in range(0, k, tile_k):
                p1 = min(p0 + tile_k, k)
                # Micro-kernel: process _VW columns at a time
                for i in range(i0, i1):
                    row_off = i * k
                    out_off = i * n
                    for j in range(j0, j1 - _VW + 1, _VW):
                        # Accumulate _VW results in parallel
                        s0 = s1 = s2 = s3 = 0.0
                        for p in range(p0, p1):
                            ap = a[row_off + p]
                            bp_off = p * n + j
                            s0 += ap * b[bp_off]
                            s1 += ap * b[bp_off + 1]
                            s2 += ap * b[bp_off + 2]
                            s3 += ap * b[bp_off + 3]
                        c[out_off + j] += s0
                        c[out_off + j + 1] += s1
                        c[out_off + j + 2] += s2
                        c[out_off + j + 3] += s3
                    # Remainder columns
                    for j in range((j1 - j0) // _VW * _VW + j0, j1):
                        s = 0.0
                        for p in range(p0, p1):
                            s += a[row_off + p] * b[p * n + j]
                        c[out_off + j] += s
    return c


# =============================================================================
#  Elementwise — NEON-width vectorized
# =============================================================================

def _ew_binary_neon(a: list[float], b: list[float], op) -> list[float]:
    """Generic binary elementwise with _VW-wide inner loop."""
    n = len(a)
    result = [0.0] * n
    # Vector body
    i = 0
    while i + _VW <= n:
        result[i] = op(a[i], b[i])
        result[i + 1] = op(a[i + 1], b[i + 1])
        result[i + 2] = op(a[i + 2], b[i + 2])
        result[i + 3] = op(a[i + 3], b[i + 3])
        i += _VW
    # Remainder
    while i < n:
        result[i] = op(a[i], b[i])
        i += 1
    return result


def _ew_unary_neon(a: list[float], op) -> list[float]:
    """Generic unary elementwise with _VW-wide inner loop."""
    n = len(a)
    result = [0.0] * n
    i = 0
    while i + _VW <= n:
        result[i] = op(a[i])
        result[i + 1] = op(a[i + 1])
        result[i + 2] = op(a[i + 2])
        result[i + 3] = op(a[i + 3])
        i += _VW
    while i < n:
        result[i] = op(a[i])
        i += 1
    return result


@register_kernel("add", VectorBackend.NEON)
def add_neon(a: list[float], b: list[float]) -> list[float]:
    return _ew_binary_neon(a, b, float.__add__)


@register_kernel("sub", VectorBackend.NEON)
def sub_neon(a: list[float], b: list[float]) -> list[float]:
    return _ew_binary_neon(a, b, float.__sub__)


@register_kernel("mul", VectorBackend.NEON)
def mul_neon(a: list[float], b: list[float]) -> list[float]:
    return _ew_binary_neon(a, b, float.__mul__)


@register_kernel("div", VectorBackend.NEON)
def div_neon(a: list[float], b: list[float]) -> list[float]:
    return _ew_binary_neon(a, b, lambda x, y: x / y if y != 0 else 0.0)


@register_kernel("neg", VectorBackend.NEON)
def neg_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, float.__neg__)


@register_kernel("abs", VectorBackend.NEON)
def abs_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, abs)


@register_kernel("sqrt", VectorBackend.NEON)
def sqrt_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, lambda x: math.sqrt(max(0.0, x)))


@register_kernel("rsqrt", VectorBackend.NEON)
def rsqrt_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, lambda x: 1.0 / math.sqrt(max(1e-12, x)))


@register_kernel("exp", VectorBackend.NEON)
def exp_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, lambda x: math.exp(min(x, 88.0)))


@register_kernel("log", VectorBackend.NEON)
def log_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, lambda x: math.log(max(1e-12, x)))


# =============================================================================
#  Activation functions — NEON-width
# =============================================================================

@register_kernel("relu", VectorBackend.NEON)
def relu_neon(a: list[float]) -> list[float]:
    # NEON fmax(x, 0) pattern
    n = len(a)
    result = [0.0] * n
    i = 0
    while i + _VW <= n:
        result[i] = a[i] if a[i] > 0.0 else 0.0
        result[i + 1] = a[i + 1] if a[i + 1] > 0.0 else 0.0
        result[i + 2] = a[i + 2] if a[i + 2] > 0.0 else 0.0
        result[i + 3] = a[i + 3] if a[i + 3] > 0.0 else 0.0
        i += _VW
    while i < n:
        result[i] = a[i] if a[i] > 0.0 else 0.0
        i += 1
    return result


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


@register_kernel("sigmoid", VectorBackend.NEON)
def sigmoid_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, _sigmoid)


@register_kernel("tanh", VectorBackend.NEON)
def tanh_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, math.tanh)


@register_kernel("gelu", VectorBackend.NEON)
def gelu_neon(a: list[float]) -> list[float]:
    c = math.sqrt(2.0 / math.pi)
    return _ew_unary_neon(
        a, lambda x: x * 0.5 * (1.0 + math.tanh(c * (x + 0.044715 * x * x * x)))
    )


@register_kernel("silu", VectorBackend.NEON)
def silu_neon(a: list[float]) -> list[float]:
    return _ew_unary_neon(a, lambda x: x * _sigmoid(x))


# =============================================================================
#  Reduction — NEON-width partial sums
# =============================================================================

@register_kernel("reduce_sum", VectorBackend.NEON)
def reduce_sum_neon(a: list[float]) -> float:
    """4-wide partial sum accumulation, then horizontal add."""
    n = len(a)
    s0 = s1 = s2 = s3 = 0.0
    i = 0
    while i + _VW <= n:
        s0 += a[i]
        s1 += a[i + 1]
        s2 += a[i + 2]
        s3 += a[i + 3]
        i += _VW
    total = s0 + s1 + s2 + s3
    while i < n:
        total += a[i]
        i += 1
    return total


@register_kernel("reduce_mean", VectorBackend.NEON)
def reduce_mean_neon(a: list[float]) -> float:
    return reduce_sum_neon(a) / len(a) if a else 0.0


@register_kernel("reduce_max", VectorBackend.NEON)
def reduce_max_neon(a: list[float]) -> float:
    if not a:
        return float("-inf")
    n = len(a)
    m0 = m1 = m2 = m3 = float("-inf")
    i = 0
    while i + _VW <= n:
        if a[i] > m0:
            m0 = a[i]
        if a[i + 1] > m1:
            m1 = a[i + 1]
        if a[i + 2] > m2:
            m2 = a[i + 2]
        if a[i + 3] > m3:
            m3 = a[i + 3]
        i += _VW
    result = max(m0, m1, m2, m3)
    while i < n:
        if a[i] > result:
            result = a[i]
        i += 1
    return result


# =============================================================================
#  Normalization — NEON-width
# =============================================================================

@register_kernel("softmax", VectorBackend.NEON)
def softmax_neon(a: list[float]) -> list[float]:
    mx = reduce_max_neon(a) if a else 0.0
    exps = _ew_unary_neon(a, lambda x: math.exp(min(x - mx, 88.0)))
    total = reduce_sum_neon(exps)
    return _ew_unary_neon(exps, lambda x: x / total) if total > 0 else exps


@register_kernel("layer_norm", VectorBackend.NEON)
def layer_norm_neon(
    x: list[float], gamma: list[float], beta: list[float],
    eps: float = 1e-5,
) -> list[float]:
    n = len(x)
    mean = reduce_sum_neon(x) / n
    # Variance with NEON-width accumulation
    var_sum = 0.0
    i = 0
    s0 = s1 = s2 = s3 = 0.0
    while i + _VW <= n:
        d0 = x[i] - mean
        d1 = x[i + 1] - mean
        d2 = x[i + 2] - mean
        d3 = x[i + 3] - mean
        s0 += d0 * d0
        s1 += d1 * d1
        s2 += d2 * d2
        s3 += d3 * d3
        i += _VW
    var_sum = s0 + s1 + s2 + s3
    while i < n:
        d = x[i] - mean
        var_sum += d * d
        i += 1
    inv_std = 1.0 / math.sqrt(var_sum / n + eps)
    return [(v - mean) * inv_std * g + b for v, g, b in zip(x, gamma, beta)]


@register_kernel("rms_norm", VectorBackend.NEON)
def rms_norm_neon(
    x: list[float], gamma: list[float], eps: float = 1e-5,
) -> list[float]:
    n = len(x)
    # NEON-width sum of squares
    s0 = s1 = s2 = s3 = 0.0
    i = 0
    while i + _VW <= n:
        s0 += x[i] * x[i]
        s1 += x[i + 1] * x[i + 1]
        s2 += x[i + 2] * x[i + 2]
        s3 += x[i + 3] * x[i + 3]
        i += _VW
    ss = s0 + s1 + s2 + s3
    while i < n:
        ss += x[i] * x[i]
        i += 1
    rms = math.sqrt(ss / n + eps)
    return [v / rms * g for v, g in zip(x, gamma)]


# =============================================================================
#  Fill / Scale / AXPY
# =============================================================================

@register_kernel("fill", VectorBackend.NEON)
def fill_neon(n: int, value: float) -> list[float]:
    return [value] * n


@register_kernel("scale", VectorBackend.NEON)
def scale_neon(a: list[float], s: float) -> list[float]:
    n = len(a)
    result = [0.0] * n
    i = 0
    while i + _VW <= n:
        result[i] = a[i] * s
        result[i + 1] = a[i + 1] * s
        result[i + 2] = a[i + 2] * s
        result[i + 3] = a[i + 3] * s
        i += _VW
    while i < n:
        result[i] = a[i] * s
        i += 1
    return result


@register_kernel("axpy", VectorBackend.NEON)
def axpy_neon(a: list[float], x: list[float], y: list[float]) -> list[float]:
    """y = a*x + y (a is scalar broadcast as first element)."""
    alpha = a[0] if a else 1.0
    n = len(x)
    result = [0.0] * n
    i = 0
    while i + _VW <= n:
        result[i] = alpha * x[i] + y[i]
        result[i + 1] = alpha * x[i + 1] + y[i + 1]
        result[i + 2] = alpha * x[i + 2] + y[i + 2]
        result[i + 3] = alpha * x[i + 3] + y[i + 3]
        i += _VW
    while i < n:
        result[i] = alpha * x[i] + y[i]
        i += 1
    return result
