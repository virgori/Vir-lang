"""Activation layers."""

from __future__ import annotations

import math

from src.virnn.tensor import Tensor
from src.virnn.module import Module
from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import VectorBackend


def _reg():
    return get_global_registry()


class ReLU(Module):
    def forward(self, x: Tensor) -> Tensor:
        kernel = _reg().get("relu", VectorBackend.SCALAR)
        out = kernel(x.data)
        return Tensor(data=out, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return "ReLU()"


class GELU(Module):
    def forward(self, x: Tensor) -> Tensor:
        kernel = _reg().get("gelu", VectorBackend.SCALAR)
        out = kernel(x.data)
        return Tensor(data=out, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return "GELU()"


class SiLU(Module):
    def forward(self, x: Tensor) -> Tensor:
        kernel = _reg().get("silu", VectorBackend.SCALAR)
        out = kernel(x.data)
        return Tensor(data=out, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return "SiLU()"


class Tanh(Module):
    def forward(self, x: Tensor) -> Tensor:
        kernel = _reg().get("tanh", VectorBackend.SCALAR)
        out = kernel(x.data)
        return Tensor(data=out, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return "Tanh()"


class Sigmoid(Module):
    def forward(self, x: Tensor) -> Tensor:
        kernel = _reg().get("sigmoid", VectorBackend.SCALAR)
        out = kernel(x.data)
        return Tensor(data=out, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return "Sigmoid()"
