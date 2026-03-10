"""
Dispatcher — Routes kernel execution to best available backend.
================================================================
Uses VirPlat's CapabilityProfile to select NEON/AVX2/SCALAR,
then looks up the kernel in VirMatrix's KernelRegistry.
"""

from __future__ import annotations

from typing import Any, Callable

from src.virplat.capability_profile import CapabilityProfile, VectorBackend
from src.virmatrix.registry import get_global_registry, KernelFn


class Dispatcher:
    """Dispatch kernel calls based on detected CPU capability."""

    def __init__(self, profile: CapabilityProfile | None = None) -> None:
        if profile is None:
            profile = CapabilityProfile.detect()
        self.profile = profile
        self._backend = profile.preferred_backend

    @property
    def backend(self) -> VectorBackend:
        return self._backend

    def dispatch(self, op: str, *args: Any, **kwargs: Any) -> Any:
        """Dispatch *op* to best available kernel backend.

        Falls back through: preferred_backend → SCALAR.
        """
        kernel = get_global_registry().get(op, self._backend)
        return kernel(*args, **kwargs)

    def get_kernel(self, op: str) -> KernelFn:
        """Return the best kernel function without calling it."""
        return get_global_registry().get(op, self._backend)

    def __repr__(self) -> str:
        return f"Dispatcher(backend={self._backend.name}, tile=({self.profile.tile_m},{self.profile.tile_n},{self.profile.tile_k}))"
