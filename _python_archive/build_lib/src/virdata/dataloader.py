"""DataLoader — Batched iteration over datasets."""

from __future__ import annotations

import random
from typing import Iterator

from src.virnn.tensor import Tensor
from src.virdata.dataset import Dataset


class DataLoader:
    """Mini-batch data loader with optional shuffling.

    Yields (batch_x, batch_y) tuples where each is a Tensor
    with batch dimension prepended.
    """

    def __init__(
        self,
        dataset: Dataset,
        batch_size: int = 32,
        shuffle: bool = True,
        drop_last: bool = False,
    ) -> None:
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.drop_last = drop_last

    def __len__(self) -> int:
        n = len(self.dataset)
        if self.drop_last:
            return n // self.batch_size
        return (n + self.batch_size - 1) // self.batch_size

    def __iter__(self) -> Iterator[tuple[Tensor, Tensor]]:
        indices = list(range(len(self.dataset)))
        if self.shuffle:
            random.shuffle(indices)

        for start in range(0, len(indices), self.batch_size):
            batch_idx = indices[start : start + self.batch_size]
            if self.drop_last and len(batch_idx) < self.batch_size:
                break

            samples = [self.dataset[i] for i in batch_idx]
            xs, ys = zip(*samples)

            # Stack into batch tensors
            batch_x = self._stack(list(xs))
            batch_y = self._stack(list(ys))
            yield batch_x, batch_y

    @staticmethod
    def _stack(tensors: list[Tensor]) -> Tensor:
        """Stack 1-D tensors into a (batch, *shape) tensor."""
        if not tensors:
            return Tensor(shape=(0,))
        shape0 = tensors[0].shape
        data: list[float] = []
        for t in tensors:
            data.extend(t.data)
        return Tensor(data=data, shape=(len(tensors), *shape0))
