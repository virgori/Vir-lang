"""
Adam — Adaptive Moment Estimation optimizer.
==============================================
"""

from __future__ import annotations

import math

from src.viroptim.state_store import StateStore


class Adam:
    """Adam optimizer (Kingma & Ba, 2014).

    m = beta1 * m + (1 - beta1) * grad
    v = beta2 * v + (1 - beta2) * grad^2
    m_hat = m / (1 - beta1^t)
    v_hat = v / (1 - beta2^t)
    param = param - lr * m_hat / (sqrt(v_hat) + eps)
    """

    def __init__(
        self,
        lr: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
        weight_decay: float = 0.0,
    ) -> None:
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.weight_decay = weight_decay
        self.state = StateStore()

    def step(self, params: dict[int, list[float]],
             grads: dict[int, list[float]]) -> None:
        """Update parameters in-place."""
        t = self.state.increment_step()

        bc1 = 1.0 - self.beta1 ** t
        bc2 = 1.0 - self.beta2 ** t

        for pid, param in params.items():
            grad = grads.get(pid)
            if grad is None:
                continue

            n = len(param)
            m = self.state.get_or_init(pid, "m", n)
            v = self.state.get_or_init(pid, "v", n)

            for i in range(n):
                g = grad[i]
                if self.weight_decay != 0:
                    g += self.weight_decay * param[i]

                m[i] = self.beta1 * m[i] + (1.0 - self.beta1) * g
                v[i] = self.beta2 * v[i] + (1.0 - self.beta2) * g * g

                m_hat = m[i] / bc1
                v_hat = v[i] / bc2

                param[i] -= self.lr * m_hat / (math.sqrt(v_hat) + self.eps)
