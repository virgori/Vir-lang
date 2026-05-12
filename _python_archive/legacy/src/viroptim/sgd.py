"""
SGD — Stochastic Gradient Descent with optional momentum.
==========================================================
"""

from __future__ import annotations

from src.viroptim.state_store import StateStore


class SGD:
    """SGD optimizer with optional momentum.

    param = param - lr * (grad + weight_decay * param)
    If momentum > 0:
        v = momentum * v + grad
        param = param - lr * v
    """

    def __init__(self, lr: float = 0.01, momentum: float = 0.0,
                 weight_decay: float = 0.0) -> None:
        self.lr = lr
        self.momentum = momentum
        self.weight_decay = weight_decay
        self.state = StateStore()

    def step(self, params: dict[int, list[float]],
             grads: dict[int, list[float]]) -> None:
        """Update parameters in-place."""
        self.state.increment_step()

        for pid, param in params.items():
            grad = grads.get(pid)
            if grad is None:
                continue

            n = len(param)

            # Weight decay
            if self.weight_decay != 0:
                grad = [g + self.weight_decay * p for g, p in zip(grad, param)]

            if self.momentum != 0:
                v = self.state.get_or_init(pid, "velocity", n)
                for i in range(n):
                    v[i] = self.momentum * v[i] + grad[i]
                    param[i] -= self.lr * v[i]
            else:
                for i in range(n):
                    param[i] -= self.lr * grad[i]
