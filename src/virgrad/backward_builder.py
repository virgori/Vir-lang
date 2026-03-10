"""
Backward Builder — Constructs backward graph from forward trace.
================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.virgrad.grad_rules import GradRules


@dataclass
class TapeEntry:
    """One recorded forward operation."""
    op: str
    output_id: int
    input_ids: tuple[int, ...]
    saved_tensors: dict[str, object] = field(default_factory=dict)


class BackwardBuilder:
    """Build backward pass from forward tape.

    Usage:
        builder = BackwardBuilder()
        builder.record("matmul", output_id=5, input_ids=(1, 2),
                       saved={"a": a_data, "b": b_data, "m": m, "k": k, "n": n})
        grads = builder.backward(loss_grad={5: grad_loss})
    """

    def __init__(self) -> None:
        self._tape: list[TapeEntry] = []

    def record(self, op: str, output_id: int, input_ids: tuple[int, ...],
               saved: dict[str, object] | None = None) -> None:
        self._tape.append(TapeEntry(
            op=op, output_id=output_id, input_ids=input_ids,
            saved_tensors=saved or {},
        ))

    def backward(self, loss_grad: dict[int, list[float]]) -> dict[int, list[float]]:
        """Run backward pass. Returns accumulated gradients per tensor id."""
        grads: dict[int, list[float]] = dict(loss_grad)

        # Reverse traversal
        for entry in reversed(self._tape):
            if entry.output_id not in grads:
                continue
            grad_out = grads[entry.output_id]

            rule = GradRules.get(entry.op)
            if rule is None:
                continue

            # Prepare arguments: grad_out + saved tensors
            saved = entry.saved_tensors
            if entry.op == "matmul":
                input_grads = rule(
                    grad_out, saved["a"], saved["b"],
                    saved["m"], saved["k"], saved["n"],
                )
            elif entry.op in ("add", "sub", "mul", "div"):
                input_grads = rule(grad_out, saved["a"], saved["b"])
            else:
                # Unary: just x
                input_grads = rule(grad_out, saved.get("x", []))

            # Accumulate into input grads
            for inp_id, ig in zip(entry.input_ids, input_grads):
                if inp_id in grads:
                    grads[inp_id] = [a + b for a, b in zip(grads[inp_id], ig)]
                else:
                    grads[inp_id] = ig

        return grads

    def clear(self) -> None:
        self._tape.clear()
