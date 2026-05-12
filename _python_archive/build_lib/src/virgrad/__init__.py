"""
VirGrad — Automatic differentiation engine.
"""

from src.virgrad.grad_rules import GradRules
from src.virgrad.backward_builder import BackwardBuilder
from src.virgrad.tape_runtime import GradTape

__all__ = ["GradRules", "BackwardBuilder", "GradTape"]
