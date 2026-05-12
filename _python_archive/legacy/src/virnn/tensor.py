"""
Tensor — Core multi-dimensional array for VirNN.
==================================================
Flat float32 storage with shape/stride metadata.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence


_next_tensor_id = 0


def _alloc_tensor_id() -> int:
    global _next_tensor_id
    _next_tensor_id += 1
    return _next_tensor_id


def _compute_strides(shape: tuple[int, ...]) -> tuple[int, ...]:
    """Row-major strides."""
    if not shape:
        return ()
    strides = [1] * len(shape)
    for i in range(len(shape) - 2, -1, -1):
        strides[i] = strides[i + 1] * shape[i + 1]
    return tuple(strides)


class Tensor:
    """Multi-dimensional tensor with flat float32 storage.

    Designed for correctness-first execution via scalar kernels,
    with dispatch to NEON/AVX2 kernels via VirMatrix registry.
    """

    __slots__ = ("id", "data", "shape", "stride", "requires_grad", "grad", "_name")

    def __init__(
        self,
        data: list[float] | None = None,
        shape: tuple[int, ...] = (),
        requires_grad: bool = False,
        name: str = "",
    ) -> None:
        self.id = _alloc_tensor_id()
        self.shape = shape
        self.stride = _compute_strides(shape)
        self.requires_grad = requires_grad
        self._name = name
        self.grad: list[float] | None = None

        numel = 1
        for s in shape:
            numel *= s

        if data is not None:
            if len(data) != numel:
                raise ValueError(f"Data length {len(data)} != expected {numel} for shape {shape}")
            self.data = list(data)
        else:
            self.data = [0.0] * numel

    @property
    def numel(self) -> int:
        n = 1
        for s in self.shape:
            n *= s
        return n

    @property
    def rank(self) -> int:
        return len(self.shape)

    @property
    def name(self) -> str:
        return self._name

    # ── Factory methods ─────────────────────────────────────

    @staticmethod
    def zeros(shape: tuple[int, ...], requires_grad: bool = False) -> Tensor:
        return Tensor(shape=shape, requires_grad=requires_grad)

    @staticmethod
    def ones(shape: tuple[int, ...], requires_grad: bool = False) -> Tensor:
        n = 1
        for s in shape:
            n *= s
        return Tensor(data=[1.0] * n, shape=shape, requires_grad=requires_grad)

    @staticmethod
    def randn(shape: tuple[int, ...], requires_grad: bool = False,
              seed: int | None = None) -> Tensor:
        """Random normal (Box-Muller)."""
        if seed is not None:
            random.seed(seed)
        n = 1
        for s in shape:
            n *= s
        data: list[float] = []
        for _ in range(0, n, 2):
            u1 = max(1e-10, random.random())
            u2 = random.random()
            z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
            z1 = math.sqrt(-2.0 * math.log(u1)) * math.sin(2.0 * math.pi * u2)
            data.append(z0)
            if len(data) < n:
                data.append(z1)
        return Tensor(data=data[:n], shape=shape, requires_grad=requires_grad)

    @staticmethod
    def kaiming_uniform(shape: tuple[int, ...], fan_in: int,
                        requires_grad: bool = True) -> Tensor:
        """Kaiming uniform initialization."""
        bound = math.sqrt(6.0 / fan_in) if fan_in > 0 else 1.0
        n = 1
        for s in shape:
            n *= s
        data = [random.uniform(-bound, bound) for _ in range(n)]
        return Tensor(data=data, shape=shape, requires_grad=requires_grad)

    # ── Indexing ────────────────────────────────────────────

    def item(self) -> float:
        """Get scalar value from single-element tensor."""
        if self.numel != 1:
            raise ValueError(f"item() on tensor with {self.numel} elements")
        return self.data[0]

    def __getitem__(self, idx: int | tuple[int, ...]) -> float:
        if isinstance(idx, int):
            return self.data[idx]
        offset = 0
        for i, s in zip(idx, self.stride):
            offset += i * s
        return self.data[offset]

    def __setitem__(self, idx: int | tuple[int, ...], value: float) -> None:
        if isinstance(idx, int):
            self.data[idx] = value
        else:
            offset = 0
            for i, s in zip(idx, self.stride):
                offset += i * s
            self.data[offset] = value

    # ── Utilities ───────────────────────────────────────────

    def zero_grad(self) -> None:
        if self.grad is not None:
            for i in range(len(self.grad)):
                self.grad[i] = 0.0

    def accumulate_grad(self, grad: list[float]) -> None:
        if self.grad is None:
            self.grad = grad[:]
        else:
            for i in range(len(self.grad)):
                self.grad[i] += grad[i]

    def clone(self) -> Tensor:
        return Tensor(data=self.data[:], shape=self.shape,
                      requires_grad=self.requires_grad)

    def reshape(self, new_shape: tuple[int, ...]) -> Tensor:
        return Tensor(data=self.data[:], shape=new_shape,
                      requires_grad=self.requires_grad)

    def __repr__(self) -> str:
        prefix = f"Tensor(shape={self.shape}"
        if self._name:
            prefix += f", name='{self._name}'"
        if self.requires_grad:
            prefix += ", requires_grad=True"
        return prefix + ")"
