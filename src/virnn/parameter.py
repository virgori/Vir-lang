"""
Parameter — Trainable tensor wrapper for VirNN modules.
========================================================
"""

from __future__ import annotations

from src.virnn.tensor import Tensor


class Parameter(Tensor):
    """A Tensor that is registered as a trainable weight in a Module."""

    def __init__(
        self,
        data: list[float] | None = None,
        shape: tuple[int, ...] = (),
        name: str = "",
    ) -> None:
        super().__init__(data=data, shape=shape, requires_grad=True, name=name)

    @staticmethod
    def from_tensor(t: Tensor, name: str = "") -> Parameter:
        p = Parameter(data=t.data[:], shape=t.shape, name=name or t.name)
        return p

    def __repr__(self) -> str:
        return f"Parameter(shape={self.shape}, name='{self._name}')"
