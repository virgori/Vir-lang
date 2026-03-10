"""VirProf — Profiling and timer utilities for Vir runtime."""
from src.virprof.timer import Timer, profile_block
from src.virprof.startup_profile import StartupProfile

__all__ = ["Timer", "profile_block", "StartupProfile"]
