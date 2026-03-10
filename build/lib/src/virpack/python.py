"""
Python Thin Binding — Expose Vir kernels as Python-callable functions.
========================================================================
Thin wrappers around VirMatrix kernel registry for use from Python.
Provides a clean, numpy-like API surface.
"""

from __future__ import annotations

from typing import Any

from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import CapabilityProfile, VectorBackend


class VirKernels:
    """Python-callable kernel interface backed by VirMatrix registry.

    Automatically dispatches to the best available backend (NEON/AVX2/SCALAR).

    Usage:
        k = VirKernels()
        c = k.matmul(a, b, m=2, k=3, n=4)
        y = k.relu(x)
        s = k.reduce_sum(x)
    """

    def __init__(self, backend: VectorBackend | None = None) -> None:
        self._registry = get_global_registry()
        if backend is None:
            profile = CapabilityProfile.detect()
            self._backend = profile.preferred_backend
        else:
            self._backend = backend

    @property
    def backend(self) -> VectorBackend:
        return self._backend

    def _call(self, op: str, *args: Any) -> Any:
        fn = self._registry.get(op, self._backend)
        if fn is None:
            raise RuntimeError(f"No kernel registered for op '{op}' backend {self._backend.name}")
        return fn(*args)

    # ── GEMM ────────────────────────────────────────────────

    def matmul(self, a: list[float], b: list[float],
               m: int, k: int, n: int) -> list[float]:
        return self._call("matmul", a, b, m, k, n)

    # ── Binary elementwise ──────────────────────────────────

    def add(self, a: list[float], b: list[float]) -> list[float]:
        return self._call("add", a, b)

    def sub(self, a: list[float], b: list[float]) -> list[float]:
        return self._call("sub", a, b)

    def mul(self, a: list[float], b: list[float]) -> list[float]:
        return self._call("mul", a, b)

    def div(self, a: list[float], b: list[float]) -> list[float]:
        return self._call("div", a, b)

    # ── Unary ───────────────────────────────────────────────

    def neg(self, a: list[float]) -> list[float]:
        return self._call("neg", a)

    def abs(self, a: list[float]) -> list[float]:
        return self._call("abs", a)

    def sqrt(self, a: list[float]) -> list[float]:
        return self._call("sqrt", a)

    def exp(self, a: list[float]) -> list[float]:
        return self._call("exp", a)

    def log(self, a: list[float]) -> list[float]:
        return self._call("log", a)

    # ── Activations ─────────────────────────────────────────

    def relu(self, a: list[float]) -> list[float]:
        return self._call("relu", a)

    def sigmoid(self, a: list[float]) -> list[float]:
        return self._call("sigmoid", a)

    def tanh(self, a: list[float]) -> list[float]:
        return self._call("tanh", a)

    def gelu(self, a: list[float]) -> list[float]:
        return self._call("gelu", a)

    def silu(self, a: list[float]) -> list[float]:
        return self._call("silu", a)

    # ── Reductions ──────────────────────────────────────────

    def reduce_sum(self, a: list[float]) -> float:
        return self._call("reduce_sum", a)

    def reduce_mean(self, a: list[float]) -> float:
        return self._call("reduce_mean", a)

    def reduce_max(self, a: list[float]) -> float:
        return self._call("reduce_max", a)

    # ── Normalization ───────────────────────────────────────

    def softmax(self, a: list[float]) -> list[float]:
        return self._call("softmax", a)

    def layer_norm(self, x: list[float], gamma: list[float],
                   beta: list[float], eps: float = 1e-5) -> list[float]:
        return self._call("layer_norm", x, gamma, beta, eps)

    def rms_norm(self, x: list[float], gamma: list[float],
                 eps: float = 1e-5) -> list[float]:
        return self._call("rms_norm", x, gamma, eps)

    # ── Scale / Fill ────────────────────────────────────────

    def scale(self, a: list[float], s: float) -> list[float]:
        return self._call("scale", a, s)

    def fill(self, n: int, value: float) -> list[float]:
        return self._call("fill", n, value)
