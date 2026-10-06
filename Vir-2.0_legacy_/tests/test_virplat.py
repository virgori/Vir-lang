"""Tests for VirPlat — CPU probe and capability profile."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virplat.cpu_probe import CPUProbe
from src.virplat.capability_profile import CapabilityProfile, VectorBackend


def test_cpu_probe():
    info = CPUProbe.probe()
    assert info.arch in ("arm64", "x86_64", "unknown")
    assert info.physical_cores >= 1


def test_capability_profile_detect():
    prof = CapabilityProfile.detect()
    assert prof.preferred_backend in VectorBackend.__members__.values()
    assert prof.tile_m > 0
    assert prof.tile_n > 0
    assert prof.tile_k > 0
    assert prof.cache_line >= 32


def test_capability_profile_vector_width():
    prof = CapabilityProfile.detect()
    # On arm64 with NEON: 4, x86 AVX2: 8, etc.
    assert prof.vector_width_f32 >= 1
