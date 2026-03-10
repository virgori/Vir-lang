"""
GradTape — Lightweight tape-based autograd runtime.
=====================================================
Records ops during forward, replays backward.
"""

from __future__ import annotations

from src.virgrad.backward_builder import BackwardBuilder


class GradTape:
    """Context-manager style gradient tape.

    Usage:
        tape = GradTape()
        tape.watch(param_id)

        # Forward
        tape.record_op("matmul", out_id, (a_id, b_id), saved={...})

        # Backward
        grads = tape.gradient(loss_id, loss_grad)
    """

    def __init__(self) -> None:
        self._builder = BackwardBuilder()
        self._watched: set[int] = set()
        self._active = True

    def watch(self, tensor_id: int) -> None:
        """Mark a tensor as requiring gradient."""
        self._watched.add(tensor_id)

    def record_op(self, op: str, output_id: int,
                  input_ids: tuple[int, ...],
                  saved: dict[str, object] | None = None) -> None:
        if self._active:
            self._builder.record(op, output_id, input_ids, saved)

    def gradient(self, loss_id: int,
                 loss_grad: list[float]) -> dict[int, list[float]]:
        """Compute gradients. Returns dict of tensor_id -> gradient."""
        all_grads = self._builder.backward({loss_id: loss_grad})
        # Filter to only watched tensors
        return {tid: all_grads[tid] for tid in self._watched if tid in all_grads}

    def reset(self) -> None:
        self._builder.clear()
        self._watched.clear()

    @property
    def is_active(self) -> bool:
        return self._active

    def pause(self) -> None:
        self._active = False

    def resume(self) -> None:
        self._active = True
