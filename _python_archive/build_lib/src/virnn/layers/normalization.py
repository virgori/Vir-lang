"""Normalization layers."""

from __future__ import annotations

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter
from src.virnn.module import Module
from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import VectorBackend


class LayerNorm(Module):
    """Layer Normalization over the last dimension."""

    def __init__(self, normalized_shape: int, eps: float = 1e-5,
                 elementwise_affine: bool = True) -> None:
        self.normalized_shape = normalized_shape
        self.eps = eps
        if elementwise_affine:
            self.gamma = Parameter(data=[1.0] * normalized_shape,
                                   shape=(normalized_shape,), name="gamma")
            self.beta = Parameter(data=[0.0] * normalized_shape,
                                  shape=(normalized_shape,), name="beta")
        else:
            self.gamma = None  # type: ignore[assignment]
            self.beta = None  # type: ignore[assignment]

    def forward(self, x: Tensor) -> Tensor:
        kernel = get_global_registry().get("layer_norm", VectorBackend.SCALAR)
        gamma = self.gamma.data if self.gamma is not None else [1.0] * self.normalized_shape
        beta = self.beta.data if self.beta is not None else [0.0] * self.normalized_shape
        dim = self.normalized_shape
        n = x.numel
        # Apply layer norm per row (last dim)
        out_data: list[float] = []
        for start in range(0, n, dim):
            row = x.data[start:start + dim]
            normed = kernel(row, gamma, beta, self.eps)
            out_data.extend(normed)
        return Tensor(data=out_data, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return f"LayerNorm({self.normalized_shape}, eps={self.eps})"


class RMSNorm(Module):
    """Root Mean Square Layer Normalization."""

    def __init__(self, normalized_shape: int, eps: float = 1e-6) -> None:
        self.normalized_shape = normalized_shape
        self.eps = eps
        self.gamma = Parameter(data=[1.0] * normalized_shape,
                               shape=(normalized_shape,), name="gamma")

    def forward(self, x: Tensor) -> Tensor:
        kernel = get_global_registry().get("rms_norm", VectorBackend.SCALAR)
        dim = self.normalized_shape
        n = x.numel
        out_data: list[float] = []
        for start in range(0, n, dim):
            row = x.data[start:start + dim]
            normed = kernel(row, self.gamma.data, self.eps)
            out_data.extend(normed)
        return Tensor(data=out_data, shape=x.shape, requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        return f"RMSNorm({self.normalized_shape}, eps={self.eps})"
