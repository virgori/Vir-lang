"""
virtual_registers.py – Bộ cấp phát thanh ghi ảo
==================================================
Spec §2.2 – Không giới hạn số lượng thanh ghi ảo (R0, R1, …, Rn).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.ir.instructions.q_ir import VReg


@dataclass
class VirtualRegisterAllocator:
    """
    Cấp phát thanh ghi ảo tuần tự.

    AI Agent có thể yêu cầu bao nhiêu thanh ghi tùy ý –
    Backend sẽ lo phần mapping xuống thanh ghi vật lý.
    """

    _next_index: int = 0
    _named: dict[str, VReg] = field(default_factory=dict)

    def alloc(self, name: str | None = None) -> VReg:
        """Cấp phát 1 thanh ghi ảo mới."""
        vreg = VReg(index=self._next_index)
        self._next_index += 1
        if name:
            self._named[name] = vreg
        return vreg

    def lookup(self, name: str) -> VReg | None:
        """Tra cứu thanh ghi ảo theo tên (nếu đã đặt tên)."""
        return self._named.get(name)

    def total_allocated(self) -> int:
        return self._next_index

    def reset(self) -> None:
        self._next_index = 0
        self._named.clear()
