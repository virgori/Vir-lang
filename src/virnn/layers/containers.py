"""Container modules: Sequential and MLP."""

from __future__ import annotations

from src.virnn.tensor import Tensor
from src.virnn.module import Module
from src.virnn.layers.linear import Linear
from src.virnn.layers.activations import ReLU, GELU


class Sequential(Module):
    """Applies a list of modules in order."""

    def __init__(self, *modules: Module) -> None:
        self.layers = list(modules)

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x

    def __repr__(self) -> str:
        lines = ["Sequential("]
        for i, layer in enumerate(self.layers):
            lines.append(f"  ({i}): {layer}")
        lines.append(")")
        return "\n".join(lines)


class MLP(Module):
    """Multi-Layer Perceptron.

    Architecture: Linear → Act → Linear [→ Act → Linear …]
    """

    def __init__(
        self,
        dims: list[int],
        activation: str = "relu",
        output_activation: bool = False,
    ) -> None:
        if len(dims) < 2:
            raise ValueError("MLP requires at least 2 dims (input, output)")
        self.dims = dims
        layers: list[Module] = []
        act_cls: type[Module] = ReLU if activation == "relu" else GELU
        for i in range(len(dims) - 1):
            layers.append(Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2 or output_activation:
                layers.append(act_cls())
        self.net = Sequential(*layers)

    def forward(self, x: Tensor) -> Tensor:
        return self.net(x)

    def __repr__(self) -> str:
        return f"MLP(dims={self.dims})"
