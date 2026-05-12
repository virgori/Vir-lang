"""Data transforms / preprocessing."""

from __future__ import annotations

from typing import Callable

from src.virnn.tensor import Tensor


class Compose:
    """Chain multiple transforms."""

    def __init__(self, transforms: list[Callable[[Tensor], Tensor]]) -> None:
        self.transforms = transforms

    def __call__(self, x: Tensor) -> Tensor:
        for t in self.transforms:
            x = t(x)
        return x


class Normalize:
    """Normalize to zero mean, unit variance (given pre-computed stats)."""

    def __init__(self, mean: list[float], std: list[float]) -> None:
        self.mean = mean
        self.std = std

    def __call__(self, x: Tensor) -> Tensor:
        out = x.clone()
        dim = len(self.mean)
        for i in range(x.numel):
            d = i % dim
            out.data[i] = (x.data[i] - self.mean[d]) / max(self.std[d], 1e-8)
        return out


class Tokenize:
    """Simple whitespace tokenizer that maps words → integer ids."""

    def __init__(self, vocab: dict[str, int] | None = None,
                 unk_id: int = 0) -> None:
        self.vocab: dict[str, int] = vocab or {}
        self.unk_id = unk_id
        self._next_id = max(self.vocab.values(), default=0) + 1

    def fit(self, texts: list[str]) -> Tokenize:
        for text in texts:
            for word in text.split():
                if word not in self.vocab:
                    self.vocab[word] = self._next_id
                    self._next_id += 1
        return self

    def encode(self, text: str, max_len: int | None = None) -> Tensor:
        ids = [float(self.vocab.get(w, self.unk_id)) for w in text.split()]
        if max_len is not None:
            ids = ids[:max_len]
            while len(ids) < max_len:
                ids.append(0.0)
        return Tensor(data=ids, shape=(len(ids),))
