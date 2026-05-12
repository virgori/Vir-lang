"""
State Store — Optimizer state management.
"""

from __future__ import annotations


class StateStore:
    """Stores per-parameter optimizer state (momentum, variance, etc.)."""

    def __init__(self) -> None:
        self._state: dict[int, dict[str, list[float]]] = {}
        self._step: int = 0

    def get(self, param_id: int, key: str) -> list[float] | None:
        return self._state.get(param_id, {}).get(key)

    def set(self, param_id: int, key: str, value: list[float]) -> None:
        if param_id not in self._state:
            self._state[param_id] = {}
        self._state[param_id][key] = value

    def get_or_init(self, param_id: int, key: str, size: int) -> list[float]:
        """Get state buffer, initializing to zeros if not present."""
        existing = self.get(param_id, key)
        if existing is not None:
            return existing
        buf = [0.0] * size
        self.set(param_id, key, buf)
        return buf

    def increment_step(self) -> int:
        self._step += 1
        return self._step

    @property
    def step(self) -> int:
        return self._step

    def clear(self) -> None:
        self._state.clear()
        self._step = 0
