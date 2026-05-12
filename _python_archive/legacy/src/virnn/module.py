"""
Module — Base class for all VirNN neural network layers.
=========================================================
"""

from __future__ import annotations

from typing import Iterator

from src.virnn.tensor import Tensor
from src.virnn.parameter import Parameter


class Module:
    """Abstract base for all NN modules.

    Subclasses must override `forward()`.
    Provides automatic parameter collection and `train`/`eval` mode.
    """

    _training: bool = True

    def forward(self, *args: Tensor) -> Tensor:
        raise NotImplementedError

    def __call__(self, *args: Tensor) -> Tensor:
        return self.forward(*args)

    # ── Parameter collection ────────────────────────────────

    def parameters(self) -> list[Parameter]:
        params: list[Parameter] = []
        seen_ids: set[int] = set()
        for p in self._iter_params():
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                params.append(p)
        return params

    def _iter_params(self) -> Iterator[Parameter]:
        """Yield own parameters then child modules' parameters."""
        for val in self.__dict__.values():
            if isinstance(val, Parameter):
                yield val
            elif isinstance(val, Module):
                yield from val._iter_params()
            elif isinstance(val, (list, tuple)):
                for item in val:
                    if isinstance(item, Module):
                        yield from item._iter_params()

    def named_parameters(self) -> list[tuple[str, Parameter]]:
        result: list[tuple[str, Parameter]] = []
        seen_ids: set[int] = set()
        self._collect_named("", result, seen_ids)
        return result

    def _collect_named(
        self,
        prefix: str,
        result: list[tuple[str, Parameter]],
        seen: set[int],
    ) -> None:
        for name, val in self.__dict__.items():
            if isinstance(val, Parameter):
                if val.id not in seen:
                    seen.add(val.id)
                    full = f"{prefix}{name}" if prefix else name
                    result.append((full, val))
            elif isinstance(val, Module):
                child_prefix = f"{prefix}{name}." if prefix else f"{name}."
                val._collect_named(child_prefix, result, seen)
            elif isinstance(val, (list, tuple)):
                for i, item in enumerate(val):
                    if isinstance(item, Module):
                        child_prefix = f"{prefix}{name}.{i}."
                        item._collect_named(child_prefix, result, seen)

    def named_modules(self) -> list[tuple[str, Module]]:
        result: list[tuple[str, Module]] = [("", self)]
        for name, val in self.__dict__.items():
            if isinstance(val, Module):
                for sub_name, sub_mod in val.named_modules():
                    full = f"{name}.{sub_name}" if sub_name else name
                    result.append((full, sub_mod))
            elif isinstance(val, (list, tuple)):
                for i, item in enumerate(val):
                    if isinstance(item, Module):
                        for sub_name, sub_mod in item.named_modules():
                            full = f"{name}.{i}.{sub_name}" if sub_name else f"{name}.{i}"
                            result.append((full, sub_mod))
        return result

    # ── Train / eval mode ───────────────────────────────────

    def train(self, mode: bool = True) -> Module:
        self._training = mode
        for _, m in self.named_modules():
            m._training = mode
        return self

    def eval(self) -> Module:
        return self.train(False)

    @property
    def training(self) -> bool:
        return self._training

    # ── Gradient utilities ──────────────────────────────────

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.zero_grad()

    def __repr__(self) -> str:
        lines = [f"{self.__class__.__name__}("]
        for name, val in self.__dict__.items():
            if isinstance(val, (Module, Parameter)):
                lines.append(f"  ({name}): {val}")
        lines.append(")")
        return "\n".join(lines)
