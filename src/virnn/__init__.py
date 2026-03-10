"""
VirNN — Neural network abstractions: Tensor, Parameter, Module, Layers.
"""

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter
from src.virnn.module import Module

__all__ = ["Tensor", "Parameter", "Module"]
