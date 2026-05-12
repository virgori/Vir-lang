"""Embedding layer."""

from __future__ import annotations

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter
from src.virnn.module import Module


class Embedding(Module):
    """Lookup-table embedding.

    Weight shape: (num_embeddings, embedding_dim).
    Forward input: integer indices as flat list in a Tensor.
    """

    def __init__(self, num_embeddings: int, embedding_dim: int) -> None:
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        self.weight = Parameter.from_tensor(
            Tensor.randn((num_embeddings, embedding_dim)),
            name="embedding_weight",
        )

    def forward(self, indices: Tensor) -> Tensor:
        # indices: flat (seq_len,) of integer token ids
        seq_len = indices.numel
        dim = self.embedding_dim
        out_data: list[float] = []
        for i in range(seq_len):
            idx = int(indices.data[i])
            if idx < 0 or idx >= self.num_embeddings:
                raise ValueError(f"Index {idx} out of range [0, {self.num_embeddings})")
            start = idx * dim
            out_data.extend(self.weight.data[start : start + dim])
        return Tensor(data=out_data, shape=(seq_len, dim), requires_grad=True)

    def __repr__(self) -> str:
        return f"Embedding({self.num_embeddings}, {self.embedding_dim})"
