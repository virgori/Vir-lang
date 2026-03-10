"""
VirPlat — Platform detection and capability profiling.
"""

from src.virplat.cpu_probe import CPUProbe, CPUInfo
from src.virplat.capability_profile import CapabilityProfile

__all__ = ["CPUProbe", "CPUInfo", "CapabilityProfile"]
