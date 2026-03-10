"""
Capability Profile — Map CPU features to kernel dispatch decisions.
====================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from src.virplat.cpu_probe import CPUInfo, CPUProbe


class VectorBackend(Enum):
    SCALAR = auto()
    NEON = auto()
    SSE2 = auto()
    AVX2 = auto()
    AVX512 = auto()


@dataclass
class CapabilityProfile:
    """Summarized platform capability for kernel dispatch."""
    cpu: CPUInfo
    preferred_backend: VectorBackend
    vector_width_f32: int
    cache_line: int
    tile_m: int = 8
    tile_n: int = 8
    tile_k: int = 4

    @staticmethod
    def detect() -> "CapabilityProfile":
        """Probe CPU and build capability profile."""
        cpu = CPUProbe.probe()

        if cpu.has_avx512:
            backend = VectorBackend.AVX512
        elif cpu.has_avx2:
            backend = VectorBackend.AVX2
        elif cpu.has_neon:
            backend = VectorBackend.NEON
        elif cpu.has_sse2:
            backend = VectorBackend.SSE2
        else:
            backend = VectorBackend.SCALAR

        vw = cpu.vector_width_f32

        # Heuristic tile sizes based on cache
        if cpu.l1d_bytes > 0:
            # Target ~50% of L1D for 3 tiles (A, B, C)
            tile_budget = cpu.l1d_bytes // 6  # bytes per tile
            tile_dim = 1
            while (tile_dim + 1) * (tile_dim + 1) * 4 <= tile_budget:
                tile_dim += 1
            tile_dim = max(4, min(tile_dim, 64))
        else:
            tile_dim = 8

        return CapabilityProfile(
            cpu=cpu,
            preferred_backend=backend,
            vector_width_f32=vw,
            cache_line=cpu.cache_line_bytes,
            tile_m=tile_dim,
            tile_n=tile_dim,
            tile_k=max(4, tile_dim // 2),
        )

    def summary(self) -> str:
        return (
            f"CapabilityProfile: {self.cpu.arch} {self.cpu.model_name}\n"
            f"  Backend: {self.preferred_backend.name}\n"
            f"  Vector width: {self.vector_width_f32} x f32\n"
            f"  Tile: {self.tile_m}x{self.tile_n}x{self.tile_k}\n"
            f"  Cache line: {self.cache_line} bytes\n"
            f"  L1D: {self.cpu.l1d_bytes // 1024} KB, "
            f"L2: {self.cpu.l2_bytes // 1024} KB"
        )
