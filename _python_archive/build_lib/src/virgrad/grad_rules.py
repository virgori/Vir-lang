"""
Gradient Rules — Per-op backward functions for autograd.
=========================================================
Each rule takes (grad_output, saved_tensors) and returns input gradients.
"""

from __future__ import annotations

import math
from typing import Callable


# Type: backward_fn(grad_out, *saved) -> tuple of grads for each input
GradFn = Callable[..., tuple[list[float], ...]]


class GradRules:
    """Registry of backward gradient rules per operation."""

    _rules: dict[str, GradFn] = {}

    @classmethod
    def register(cls, op: str) -> Callable[[GradFn], GradFn]:
        def decorator(fn: GradFn) -> GradFn:
            cls._rules[op] = fn
            return fn
        return decorator

    @classmethod
    def get(cls, op: str) -> GradFn | None:
        return cls._rules.get(op)

    @classmethod
    def has(cls, op: str) -> bool:
        return op in cls._rules


# =============================================================================
#  Backward rules
# =============================================================================

@GradRules.register("add")
def _grad_add(grad_out: list[float], a: list[float], b: list[float]
              ) -> tuple[list[float], list[float]]:
    return grad_out[:], grad_out[:]


@GradRules.register("sub")
def _grad_sub(grad_out: list[float], a: list[float], b: list[float]
              ) -> tuple[list[float], list[float]]:
    return grad_out[:], [-g for g in grad_out]


@GradRules.register("mul")
def _grad_mul(grad_out: list[float], a: list[float], b: list[float]
              ) -> tuple[list[float], list[float]]:
    # d(a*b)/da = b, d(a*b)/db = a
    return [g * bi for g, bi in zip(grad_out, b)], \
           [g * ai for g, ai in zip(grad_out, a)]


@GradRules.register("div")
def _grad_div(grad_out: list[float], a: list[float], b: list[float]
              ) -> tuple[list[float], list[float]]:
    # d(a/b)/da = 1/b, d(a/b)/db = -a/b^2
    ga = [g / bi if bi != 0 else 0.0 for g, bi in zip(grad_out, b)]
    gb = [-g * ai / (bi * bi) if bi != 0 else 0.0
          for g, ai, bi in zip(grad_out, a, b)]
    return ga, gb


@GradRules.register("relu")
def _grad_relu(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g if xi > 0 else 0.0 for g, xi in zip(grad_out, x)],)


@GradRules.register("sigmoid")
def _grad_sigmoid(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    def _sig(v: float) -> float:
        if v >= 0:
            return 1.0 / (1.0 + math.exp(-v))
        ex = math.exp(v)
        return ex / (1.0 + ex)
    return ([g * _sig(xi) * (1.0 - _sig(xi)) for g, xi in zip(grad_out, x)],)


@GradRules.register("tanh")
def _grad_tanh(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g * (1.0 - math.tanh(xi) ** 2) for g, xi in zip(grad_out, x)],)


@GradRules.register("exp")
def _grad_exp(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g * math.exp(min(xi, 88.0)) for g, xi in zip(grad_out, x)],)


@GradRules.register("log")
def _grad_log(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g / max(xi, 1e-12) for g, xi in zip(grad_out, x)],)


@GradRules.register("neg")
def _grad_neg(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([-g for g in grad_out],)


@GradRules.register("matmul")
def _grad_matmul(
    grad_out: list[float],
    a: list[float], b: list[float],
    m: int, k: int, n: int,
) -> tuple[list[float], list[float]]:
    """Backward for C = A @ B where A is (m,k), B is (k,n), C is (m,n)."""
    # dL/dA = dL/dC @ B^T  -> (m,n) @ (n,k) = (m,k)
    grad_a = [0.0] * (m * k)
    for i in range(m):
        for p in range(k):
            s = 0.0
            for j in range(n):
                s += grad_out[i * n + j] * b[p * n + j]
            grad_a[i * k + p] = s

    # dL/dB = A^T @ dL/dC  -> (k,m) @ (m,n) = (k,n)
    grad_b = [0.0] * (k * n)
    for p in range(k):
        for j in range(n):
            s = 0.0
            for i in range(m):
                s += a[i * k + p] * grad_out[i * n + j]
            grad_b[p * n + j] = s

    return grad_a, grad_b


@GradRules.register("reduce_mean")
def _grad_reduce_mean(grad_out: list[float], x: list[float]
                      ) -> tuple[list[float]]:
    """grad broadcast back to input shape, scaled by 1/n."""
    n = len(x)
    g = grad_out[0] if isinstance(grad_out, list) and len(grad_out) == 1 else sum(grad_out)
    return ([g / n] * n,)


@GradRules.register("reduce_sum")
def _grad_reduce_sum(grad_out: list[float], x: list[float]
                     ) -> tuple[list[float]]:
    g = grad_out[0] if isinstance(grad_out, list) and len(grad_out) == 1 else sum(grad_out)
    return ([g] * len(x),)


# =============================================================================
#  Additional backward rules (Phase 4 completion)
# =============================================================================

@GradRules.register("abs")
def _grad_abs(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g * (1.0 if xi > 0 else (-1.0 if xi < 0 else 0.0))
             for g, xi in zip(grad_out, x)],)


@GradRules.register("sqrt")
def _grad_sqrt(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    return ([g / (2.0 * math.sqrt(max(xi, 1e-12)))
             for g, xi in zip(grad_out, x)],)


@GradRules.register("rsqrt")
def _grad_rsqrt(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    # d(x^-0.5)/dx = -0.5 * x^-1.5
    return ([-0.5 * g / (max(xi, 1e-12) * math.sqrt(max(xi, 1e-12)))
             for g, xi in zip(grad_out, x)],)


@GradRules.register("gelu")
def _grad_gelu(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    """GELU gradient: d/dx[x * 0.5 * (1 + tanh(c*(x + 0.044715*x^3)))]."""
    c = math.sqrt(2.0 / math.pi)

    def _gelu_grad(g: float, xi: float) -> float:
        inner = c * (xi + 0.044715 * xi * xi * xi)
        tanh_inner = math.tanh(inner)
        dtanh = 1.0 - tanh_inner * tanh_inner
        dinner = c * (1.0 + 3.0 * 0.044715 * xi * xi)
        return g * (0.5 * (1.0 + tanh_inner) + 0.5 * xi * dtanh * dinner)

    return ([_gelu_grad(g, xi) for g, xi in zip(grad_out, x)],)


@GradRules.register("silu")
def _grad_silu(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    """SiLU/Swish gradient: d/dx[x * sigmoid(x)] = sigmoid(x) + x*sigmoid(x)*(1-sigmoid(x))."""
    def _sig(v: float) -> float:
        if v >= 0:
            return 1.0 / (1.0 + math.exp(-v))
        ex = math.exp(v)
        return ex / (1.0 + ex)

    def _silu_grad(g: float, xi: float) -> float:
        s = _sig(xi)
        return g * (s + xi * s * (1.0 - s))

    return ([_silu_grad(g, xi) for g, xi in zip(grad_out, x)],)


@GradRules.register("softmax")
def _grad_softmax(grad_out: list[float], x: list[float]) -> tuple[list[float]]:
    """Softmax gradient: dL/dx_i = s_i * (dL/ds_i - sum_j(dL/ds_j * s_j))."""
    # Recompute softmax
    mx = max(x) if x else 0.0
    exps = [math.exp(min(xi - mx, 88.0)) for xi in x]
    total = sum(exps)
    s = [e / total for e in exps] if total > 0 else exps
    # dot = sum(dL/ds_j * s_j)
    dot = sum(g * si for g, si in zip(grad_out, s))
    return ([si * (g - dot) for si, g in zip(s, grad_out)],)


@GradRules.register("layer_norm")
def _grad_layer_norm(
    grad_out: list[float], x: list[float],
    gamma: list[float], beta: list[float],
) -> tuple[list[float], list[float], list[float]]:
    """Layer norm backward.

    Forward: y = (x - mean) * inv_std * gamma + beta
    """
    n = len(x)
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / n
    inv_std = 1.0 / math.sqrt(var + 1e-5)

    x_hat = [(v - mean) * inv_std for v in x]

    # d_beta = grad_out
    d_beta = grad_out[:]

    # d_gamma = grad_out * x_hat
    d_gamma = [g * xh for g, xh in zip(grad_out, x_hat)]

    # d_x_hat = grad_out * gamma
    d_x_hat = [g * gi for g, gi in zip(grad_out, gamma)]

    # dx = inv_std * (d_x_hat - mean(d_x_hat) - x_hat * mean(d_x_hat * x_hat))
    mean_dxh = sum(d_x_hat) / n
    mean_dxh_xh = sum(dxh * xh for dxh, xh in zip(d_x_hat, x_hat)) / n
    d_x = [inv_std * (dxh - mean_dxh - xh * mean_dxh_xh)
            for dxh, xh in zip(d_x_hat, x_hat)]

    return d_x, d_gamma, d_beta


@GradRules.register("rms_norm")
def _grad_rms_norm(
    grad_out: list[float], x: list[float],
    gamma: list[float],
) -> tuple[list[float], list[float]]:
    """RMS norm backward."""
    n = len(x)
    ss = sum(v * v for v in x) / n
    rms = math.sqrt(ss + 1e-5)
    x_hat = [v / rms for v in x]

    # d_gamma = grad_out * x_hat
    d_gamma = [g * xh for g, xh in zip(grad_out, x_hat)]

    # dx
    d_x_hat = [g * gi for g, gi in zip(grad_out, gamma)]
    mean_dxh_xh = sum(dxh * xh for dxh, xh in zip(d_x_hat, x_hat)) / n
    d_x = [(dxh - xh * mean_dxh_xh) / rms for dxh, xh in zip(d_x_hat, x_hat)]

    return d_x, d_gamma


@GradRules.register("reduce_max")
def _grad_reduce_max(grad_out: list[float], x: list[float]
                     ) -> tuple[list[float]]:
    """Gradient flows only to the max element."""
    g = grad_out[0] if isinstance(grad_out, list) and len(grad_out) == 1 else sum(grad_out)
    mx = max(x) if x else 0.0
    return ([g if xi == mx else 0.0 for xi in x],)
