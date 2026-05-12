"""
pressure_monitor.py – Register Pressure Monitor (Bộ giám sát áp suất)
=======================================================================
Spec §3.1 – Giám sát số lượng thanh ghi vật lý còn rảnh (N_free)
và quyết định chế độ thực thi.
"""

from __future__ import annotations

import os
import platform
import struct
import ctypes
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class ExecutionMode(Enum):
    """Chế độ thực thi."""
    SAFE_STACK = auto()            # Bản A – dùng stack (chậm, ổn định)
    HIGH_PERFORMANCE_REG = auto()  # Bản B – dùng thanh ghi vật lý trực tiếp


@dataclass
class CPUState:
    """Trạng thái CPU tại thời điểm kiểm tra."""
    arch: str                    # "x86_64", "arm64", …
    total_gp_registers: int      # Tổng số thanh ghi general-purpose
    estimated_free: int          # Ước tính số thanh ghi rảnh (N_free)
    cpu_load_percent: float      # % CPU usage hiện tại
    mode: ExecutionMode          # Chế độ được khuyến nghị


# ── Hằng số kiến trúc ────────────────────────────────────

_ARCH_GP_REGISTERS = {
    "x86_64": 16,   # RAX, RBX, RCX, RDX, RSI, RDI, R8-R15
    "AMD64": 16,
    "arm64": 31,     # X0-X30
    "aarch64": 31,
}

_DEFAULT_THRESHOLD = 8  # Ngưỡng N_free tối thiểu cho High Performance


class RegisterPressureMonitor:
    """
    Giám sát áp suất thanh ghi & tải CPU.

    Nếu N_free > threshold → kích hoạt Assembly High Performance.
    """

    def __init__(self, threshold: int = _DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        self._arch = platform.machine() or "x86_64"

    # ── Public API ─────────────────────────────────────────
    def probe(self) -> CPUState:
        """Lấy trạng thái CPU hiện tại."""
        total_gp = _ARCH_GP_REGISTERS.get(self._arch, 16)
        cpu_load = self._get_cpu_load()

        # Ước tính N_free dựa trên CPU load:
        #   - CPU 0% → gần như tất cả GP regs rảnh (trừ reserved ~4)
        #   - CPU 100% → chỉ còn ~2 regs rảnh
        reserved = 4  # RSP, RBP, + 2 OS-reserved
        available = total_gp - reserved
        estimated_free = max(0, int(available * (1.0 - cpu_load / 100.0)))

        mode = (
            ExecutionMode.HIGH_PERFORMANCE_REG
            if estimated_free > self.threshold
            else ExecutionMode.SAFE_STACK
        )

        return CPUState(
            arch=self._arch,
            total_gp_registers=total_gp,
            estimated_free=estimated_free,
            cpu_load_percent=cpu_load,
            mode=mode,
        )

    def should_use_registers(self) -> bool:
        """Trả về True nếu nên dùng thanh ghi (High Performance mode)."""
        return self.probe().mode == ExecutionMode.HIGH_PERFORMANCE_REG

    # ── CPU Load Measurement ───────────────────────────────
    def _get_cpu_load(self) -> float:
        """Đo CPU load (%). Fallback = 50% nếu không đo được."""
        system = platform.system()
        try:
            if system == "Darwin":
                return self._get_cpu_load_macos()
            elif system == "Linux":
                return self._get_cpu_load_linux()
            elif system == "Windows":
                return self._get_cpu_load_windows()
        except Exception:
            pass
        return 50.0  # fallback

    @staticmethod
    def _get_cpu_load_macos() -> float:
        """macOS: dùng sysctl / host_statistics."""
        import subprocess
        result = subprocess.run(
            ["sysctl", "-n", "vm.loadavg"],
            capture_output=True, text=True, timeout=2,
        )
        # Output: "{ 1.23 1.45 1.67 }"
        parts = result.stdout.strip().strip("{}").split()
        if parts:
            load_1min = float(parts[0])
            ncpu = os.cpu_count() or 1
            return min(100.0, (load_1min / ncpu) * 100.0)
        return 50.0

    @staticmethod
    def _get_cpu_load_linux() -> float:
        """Linux: đọc /proc/loadavg."""
        with open("/proc/loadavg") as f:
            load_1min = float(f.read().split()[0])
        ncpu = os.cpu_count() or 1
        return min(100.0, (load_1min / ncpu) * 100.0)

    @staticmethod
    def _get_cpu_load_windows() -> float:
        """Windows: dùng ctypes kernel32."""
        # Simplified – production would use WMI / PDH
        return 50.0
