"""Linear layer."""

from __future__ import annotations

import math

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter
from src.virnn.module import Module
from src.virmatrix.registry import get_global_registry
from src.virplat.capability_profile import VectorBackend


class Linear(Module):
    """y = x @ W^T + bias.

    Weight shape: (out_features, in_features)
    """

    def __init__(self, in_features: int, out_features: int,
                 bias: bool = True) -> None:
        self.in_features = in_features
        self.out_features = out_features

        # Kaiming uniform init
        self.weight = Parameter.from_tensor(
            Tensor.kaiming_uniform((out_features, in_features), fan_in=in_features),
            name="weight",
        )
        self.bias_param: Parameter | None = None
        if bias:
            bound = 1.0 / math.sqrt(in_features) if in_features > 0 else 1.0
            import random
            data = [random.uniform(-bound, bound) for _ in range(out_features)]
            self.bias_param = Parameter(data=data, shape=(out_features,), name="bias")

    def forward(self, x: Tensor) -> Tensor:
        # x: (batch, in_features) → out: (batch, out_features)
        batch = x.shape[0] if x.rank >= 2 else 1
        M, K, N = batch, self.in_features, self.out_features

        # Transpose weight: (out, in) → (in, out)
        wt_data = [0.0] * (K * N)
        for i in range(N):
            for j in range(K):
                wt_data[j * N + i] = self.weight.data[i * K + j]

        # matmul: (M,K) @ (K,N)
        reg = get_global_registry()
        matmul_kernel = reg.get("matmul", VectorBackend.SCALAR)
        out_data = matmul_kernel(x.data, wt_data, M, K, N)

        if self.bias_param is not None:
            add_kernel = reg.get("add", VectorBackend.SCALAR)
            # Broadcast bias to each row
            bias_expanded = self.bias_param.data * M
            out_data = add_kernel(out_data, bias_expanded)

        return Tensor(data=out_data, shape=(M, N), requires_grad=x.requires_grad)

    def __repr__(self) -> str:
        b = self.bias_param is not None
        return f"Linear(in_features={self.in_features}, out_features={self.out_features}, bias={b})"
