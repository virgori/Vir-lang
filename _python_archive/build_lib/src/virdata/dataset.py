"""Dataset abstractions."""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from typing import Any

from src.virnn.tensor import Tensor


class Dataset(ABC):
    """Abstract dataset interface."""

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]: ...


class ListDataset(Dataset):
    """In-memory dataset from pre-built tensors."""

    def __init__(self, data: list[Tensor], targets: list[Tensor]) -> None:
        if len(data) != len(targets):
            raise ValueError("data and targets must have same length")
        self._data = data
        self._targets = targets

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        return self._data[index], self._targets[index]


class CSVDataset(Dataset):
    """Read rows from a CSV file.

    Each row becomes (features_tensor, target_tensor).
    `target_cols` specifies which column indices are targets (rest are features).
    """

    def __init__(self, path: str, target_cols: list[int] | None = None,
                 skip_header: bool = True) -> None:
        self._rows: list[tuple[list[float], list[float]]] = []
        target_cols = target_cols or [-1]

        with open(path, newline="") as f:
            reader = csv.reader(f)
            if skip_header:
                next(reader, None)
            for row in reader:
                vals = [float(v) for v in row]
                target_indices = {(c if c >= 0 else len(vals) + c) for c in target_cols}
                feats = [v for i, v in enumerate(vals) if i not in target_indices]
                tgts = [vals[i] for i in sorted(target_indices)]
                self._rows.append((feats, tgts))

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        feats, tgts = self._rows[index]
        return (
            Tensor(data=feats, shape=(len(feats),)),
            Tensor(data=tgts, shape=(len(tgts),)),
        )
