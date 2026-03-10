"""
Kernel Registry — Maps (op, backend) to kernel implementations.
================================================================
"""

from __future__ import annotations

from typing import Callable, Protocol
from src.virplat.capability_profile import VectorBackend


class KernelFn(Protocol):
    """Protocol for kernel functions."""
    def __call__(self, *args: object) -> object: ...


class KernelRegistry:
    """Global registry of compute kernel implementations.

    Supports fallback chain: preferred_backend -> SCALAR.
    """

    def __init__(self) -> None:
        # (op_name, backend) -> kernel_fn
        self._kernels: dict[tuple[str, VectorBackend], KernelFn] = {}

    def register(self, op: str, backend: VectorBackend, fn: KernelFn) -> None:
        self._kernels[(op, backend)] = fn

    def get(self, op: str, backend: VectorBackend) -> KernelFn | None:
        """Look up kernel with fallback to SCALAR."""
        fn = self._kernels.get((op, backend))
        if fn is not None:
            return fn
        # Fallback
        return self._kernels.get((op, VectorBackend.SCALAR))

    def has(self, op: str, backend: VectorBackend) -> bool:
        return (op, backend) in self._kernels or (op, VectorBackend.SCALAR) in self._kernels

    def list_ops(self) -> list[str]:
        return sorted({op for op, _ in self._kernels})


# Global singleton
_GLOBAL_REGISTRY = KernelRegistry()


def get_global_registry() -> KernelRegistry:
    return _GLOBAL_REGISTRY


def register_kernel(op: str, backend: VectorBackend = VectorBackend.SCALAR) -> Callable:
    """Decorator to register a kernel function."""
    def decorator(fn: KernelFn) -> KernelFn:
        _GLOBAL_REGISTRY.register(op, backend, fn)
        return fn
    return decorator
