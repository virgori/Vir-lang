"""
bridge_api.py – Bridge API (Lách luật OS)
==========================================
Spec §4.1 – Tự động chọn "Cổng lách" tùy theo môi trường:
  - Linux:  sys_mprotect / mmap(MAP_ANONYMOUS | MAP_SHARED)
  - Windows: VirtualAlloc(PAGE_EXECUTE_READWRITE)
  - macOS:  pthread_jit_write_protect_np(0/1)
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol


class OSType(Enum):
    LINUX = "Linux"
    MACOS = "Darwin"
    WINDOWS = "Windows"
    UNKNOWN = "Unknown"


@dataclass
class MemoryPermission:
    """Quyền truy cập vùng nhớ."""
    read: bool = True
    write: bool = True
    execute: bool = True


class BridgeBackend(Protocol):
    """Interface cho mỗi OS backend."""

    def set_memory_writable(self, address: int, size: int) -> bool: ...
    def set_memory_executable(self, address: int, size: int) -> bool: ...
    def set_memory_rwx(self, address: int, size: int) -> bool: ...


# ═══════════════════════════════════════════════════════════
# Linux Bridge
# ═══════════════════════════════════════════════════════════

class LinuxBridge:
    """Linux: sys_mprotect."""

    def __init__(self) -> None:
        self._libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        self._libc.mprotect.restype = ctypes.c_int
        self._libc.mprotect.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int
        ]
        self._page_size = 4096

    def _align_page(self, addr: int) -> int:
        return addr & ~(self._page_size - 1)

    def set_memory_writable(self, address: int, size: int) -> bool:
        PROT_READ = 0x1
        PROT_WRITE = 0x2
        aligned = self._align_page(address)
        total = size + (address - aligned)
        return self._libc.mprotect(aligned, total, PROT_READ | PROT_WRITE) == 0

    def set_memory_executable(self, address: int, size: int) -> bool:
        PROT_READ = 0x1
        PROT_EXEC = 0x4
        aligned = self._align_page(address)
        total = size + (address - aligned)
        return self._libc.mprotect(aligned, total, PROT_READ | PROT_EXEC) == 0

    def set_memory_rwx(self, address: int, size: int) -> bool:
        PROT_READ = 0x1
        PROT_WRITE = 0x2
        PROT_EXEC = 0x4
        aligned = self._align_page(address)
        total = size + (address - aligned)
        return self._libc.mprotect(aligned, total, PROT_READ | PROT_WRITE | PROT_EXEC) == 0


# ═══════════════════════════════════════════════════════════
# macOS Bridge
# ═══════════════════════════════════════════════════════════

class MacOSBridge:
    """macOS: pthread_jit_write_protect_np + mprotect."""

    def __init__(self) -> None:
        self._libc = ctypes.CDLL(ctypes.util.find_library("c"))
        self._libpthread = ctypes.CDLL(ctypes.util.find_library("pthread"))
        self._page_size = 16384  # macOS ARM uses 16K pages

    def set_memory_writable(self, address: int, size: int) -> bool:
        """pthread_jit_write_protect_np(0) – mở khóa ghi."""
        try:
            self._libpthread.pthread_jit_write_protect_np(0)
            return True
        except Exception:
            return False

    def set_memory_executable(self, address: int, size: int) -> bool:
        """pthread_jit_write_protect_np(1) – khóa → chạy."""
        try:
            self._libpthread.pthread_jit_write_protect_np(1)
            return True
        except Exception:
            return False

    def set_memory_rwx(self, address: int, size: int) -> bool:
        """macOS MAP_JIT đã có RWX. Chỉ cần toggle write protect."""
        return self.set_memory_writable(address, size)


# ═══════════════════════════════════════════════════════════
# Windows Bridge
# ═══════════════════════════════════════════════════════════

class WindowsBridge:
    """Windows: VirtualProtect."""

    def __init__(self) -> None:
        try:
            self._kernel32 = ctypes.windll.kernel32  # type: ignore
        except AttributeError:
            self._kernel32 = None

    def _protect(self, address: int, size: int, new_protect: int) -> bool:
        if not self._kernel32:
            return False
        old = ctypes.c_ulong(0)
        return bool(
            self._kernel32.VirtualProtect(
                ctypes.c_void_p(address), size, new_protect, ctypes.byref(old)
            )
        )

    def set_memory_writable(self, address: int, size: int) -> bool:
        PAGE_READWRITE = 0x04
        return self._protect(address, size, PAGE_READWRITE)

    def set_memory_executable(self, address: int, size: int) -> bool:
        PAGE_EXECUTE_READ = 0x20
        return self._protect(address, size, PAGE_EXECUTE_READ)

    def set_memory_rwx(self, address: int, size: int) -> bool:
        PAGE_EXECUTE_READWRITE = 0x40
        return self._protect(address, size, PAGE_EXECUTE_READWRITE)


# ═══════════════════════════════════════════════════════════
# Bridge Factory
# ═══════════════════════════════════════════════════════════

class FallbackBridge:
    """Fallback cho OS không được hỗ trợ (simulation)."""

    def set_memory_writable(self, address: int, size: int) -> bool:
        return True

    def set_memory_executable(self, address: int, size: int) -> bool:
        return True

    def set_memory_rwx(self, address: int, size: int) -> bool:
        return True


def create_bridge() -> BridgeBackend:
    """Factory: tự động chọn Bridge phù hợp với OS hiện tại."""
    system = platform.system()
    match system:
        case "Linux":
            return LinuxBridge()  # type: ignore[return-value]
        case "Darwin":
            return MacOSBridge()  # type: ignore[return-value]
        case "Windows":
            return WindowsBridge()  # type: ignore[return-value]
        case _:
            return FallbackBridge()  # type: ignore[return-value]


def detect_os() -> OSType:
    """Phát hiện OS hiện tại."""
    system = platform.system()
    match system:
        case "Linux":
            return OSType.LINUX
        case "Darwin":
            return OSType.MACOS
        case "Windows":
            return OSType.WINDOWS
        case _:
            return OSType.UNKNOWN
