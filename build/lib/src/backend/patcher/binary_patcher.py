"""
binary_patcher.py – Giải thuật Vá mã (Binary Patching Logic)
==============================================================
Spec §3.2 – Jump Table Indirection & runtime code patching.

Quy trình:
1. Khởi tạo vùng nhớ RWX (PROT_READ | PROT_WRITE | PROT_EXEC / MAP_JIT).
2. Ghi Bản A (Safe) vào jump table ban đầu.
3. Khi CPU rảnh → ghi đè JMP target để trỏ sang Bản B (Fast).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
import struct
from dataclasses import dataclass, field
from typing import Optional

from src.backend.codegen.codegen import CodeVariant, MachineCode, TargetArch


# ── Cached library handles (loaded once) ──────────────────
_libc_handle = None
_libpthread_handle = None

def _get_libc():
    global _libc_handle
    if _libc_handle is None:
        _libc_handle = ctypes.CDLL(ctypes.util.find_library("c"))
    return _libc_handle

def _get_libpthread():
    global _libpthread_handle
    if _libpthread_handle is None:
        lib_name = ctypes.util.find_library("pthread")
        if lib_name:
            _libpthread_handle = ctypes.CDLL(lib_name)
    return _libpthread_handle


@dataclass
class JumpTableEntry:
    """Một entry trong Jump Table."""
    patch_id: str
    jmp_offset: int       # Offset trong vùng nhớ JIT nơi lệnh JMP nằm
    safe_target: int      # Absolute address → Bản A
    fast_target: int      # Absolute address → Bản B
    is_patched: bool = False  # True nếu đang trỏ sang Bản B


@dataclass
class JITRegion:
    """Vùng nhớ cấp phát cho JIT code."""
    base_address: int
    size: int
    _buffer: ctypes.Array | None = None  # ctypes buffer
    _is_macos_jit: bool = False  # True if allocated with MAP_JIT on macOS

    def write(self, offset: int, data: bytes, _protect: bool = True) -> None:
        if self._buffer is None:
            return
        end = offset + len(data)
        if end > self.size:
            raise ValueError(
                f"JITRegion write out of bounds: offset={offset}, len={len(data)}, size={self.size}"
            )
        if self._is_macos_jit and _protect:
            BinaryPatcher._macos_write_protect_off()
        # Use memmove for bulk write (avoids Bus Error on MAP_JIT pages)
        dst = ctypes.c_void_p(self.base_address + offset)
        src = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        ctypes.memmove(dst, src, len(data))
        if self._is_macos_jit and _protect:
            BinaryPatcher._macos_write_protect_on()
            BinaryPatcher._macos_icache_invalidate(
                self.base_address + offset, len(data)
            )

    def read(self, offset: int, length: int) -> bytes:
        if self._buffer is None:
            return b"\x00" * length
        end = offset + length
        if end > self.size:
            length = max(0, self.size - offset)
        return bytes(self._buffer[offset : offset + length])


class BinaryPatcher:
    """
    Bộ vá mã nhị phân runtime.

    Sử dụng Jump Table Indirection:
    - Mỗi patch point = 1 lệnh JMP trong code chính.
    - Ban đầu JMP trỏ tới Bản A (Stack/Safe).
    - Khi CPU rảnh → ghi đè JMP offset để trỏ sang Bản B (Register/Fast).
    """

    def __init__(self, arch: TargetArch = TargetArch.X86_64) -> None:
        self.arch = arch
        self.jump_table: list[JumpTableEntry] = []
        self._regions: list[JITRegion] = []
        self._system = platform.system()

    # ── JIT Memory Allocation ──────────────────────────────

    def allocate_jit_region(self, size: int = 4096) -> JITRegion:
        """
        Cấp phát vùng nhớ RWX cho JIT code.

        Spec §3.2.1:
        - macOS:  MAP_JIT + pthread_jit_write_protect_np
        - Linux:  mmap(MAP_ANONYMOUS | MAP_SHARED) + mprotect
        - Windows: VirtualAlloc(PAGE_EXECUTE_READWRITE)
        """
        region = self._alloc_platform(size)
        self._regions.append(region)
        return region

    def _alloc_platform(self, size: int) -> JITRegion:
        """Platform-specific JIT memory allocation."""
        system = self._system

        if system == "Darwin":
            return self._alloc_macos(size)
        elif system == "Linux":
            return self._alloc_linux(size)
        elif system == "Windows":
            return self._alloc_windows(size)
        else:
            # Fallback: dùng ctypes buffer thuần (không thể exec thật)
            return self._alloc_fallback(size)

    def _alloc_macos(self, size: int) -> JITRegion:
        """macOS: mmap với MAP_JIT."""
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c"))

            PROT_READ = 0x01
            PROT_WRITE = 0x02
            PROT_EXEC = 0x04
            MAP_PRIVATE = 0x0002
            MAP_ANONYMOUS = 0x1000
            MAP_JIT = 0x0800

            libc.mmap.restype = ctypes.c_void_p
            libc.mmap.argtypes = [
                ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_long,
            ]

            addr = libc.mmap(
                None, size,
                PROT_READ | PROT_WRITE | PROT_EXEC,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_JIT,
                -1, 0,
            )

            if addr == ctypes.c_void_p(-1).value or addr is None:
                return self._alloc_fallback(size)

            buf = (ctypes.c_ubyte * size).from_address(addr)
            region = JITRegion(base_address=addr, size=size, _buffer=buf,
                               _is_macos_jit=True)
            return region
        except Exception:
            return self._alloc_fallback(size)

    def _alloc_linux(self, size: int) -> JITRegion:
        """Linux: mmap + mprotect."""
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c"))

            PROT_READ = 0x1
            PROT_WRITE = 0x2
            PROT_EXEC = 0x4
            MAP_PRIVATE = 0x02
            MAP_ANONYMOUS = 0x20

            libc.mmap.restype = ctypes.c_void_p
            libc.mmap.argtypes = [
                ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_long,
            ]

            addr = libc.mmap(
                None, size,
                PROT_READ | PROT_WRITE | PROT_EXEC,
                MAP_PRIVATE | MAP_ANONYMOUS,
                -1, 0,
            )

            if addr == ctypes.c_void_p(-1).value or addr is None:
                return self._alloc_fallback(size)

            buf = (ctypes.c_ubyte * size).from_address(addr)
            return JITRegion(base_address=addr, size=size, _buffer=buf)
        except Exception:
            return self._alloc_fallback(size)

    def _alloc_windows(self, size: int) -> JITRegion:
        """Windows: VirtualAlloc."""
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            MEM_COMMIT = 0x1000
            MEM_RESERVE = 0x2000
            PAGE_EXECUTE_READWRITE = 0x40

            kernel32.VirtualAlloc.restype = ctypes.c_void_p
            addr = kernel32.VirtualAlloc(
                None, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE,
            )

            if not addr:
                return self._alloc_fallback(size)

            buf = (ctypes.c_ubyte * size).from_address(addr)
            return JITRegion(base_address=addr, size=size, _buffer=buf)
        except Exception:
            return self._alloc_fallback(size)

    @staticmethod
    def _alloc_fallback(size: int) -> JITRegion:
        """Fallback: buffer thuần Python (simulation mode)."""
        buf = (ctypes.c_ubyte * size)()
        addr = ctypes.addressof(buf)
        return JITRegion(base_address=addr, size=size, _buffer=buf)

    # ── Jump Table Construction ────────────────────────────

    def build_jump_table(
        self, variants: list[CodeVariant], region: JITRegion
    ) -> bytearray:
        """
        Xây dựng Jump Table + ghi tất cả code vào JIT region.

        Layout trong region:
        [JMP #1][JMP #2]…[JMP #N][Safe Code #1][Fast Code #1]…
        """
        self.jump_table.clear()

        # Tính kích cỡ
        jmp_size = 5 if self.arch == TargetArch.X86_64 else 4  # JMP rel32 = 5 bytes
        table_size = len(variants) * jmp_size
        code_offset = table_size

        # Bước 1: Ghi safe & fast code, ghi nhận address
        safe_addresses: dict[str, int] = {}
        fast_addresses: dict[str, int] = {}

        for variant in variants:
            # Safe code
            safe_addr = region.base_address + code_offset
            region.write(code_offset, variant.safe_code.bytes_)
            safe_addresses[variant.patch_id] = safe_addr
            code_offset += len(variant.safe_code.bytes_)

            # Fast code
            fast_addr = region.base_address + code_offset
            region.write(code_offset, variant.fast_code.bytes_)
            fast_addresses[variant.patch_id] = fast_addr
            code_offset += len(variant.fast_code.bytes_)

        # Bước 2: Ghi JMP entries (ban đầu trỏ về Safe)
        for i, variant in enumerate(variants):
            jmp_offset = i * jmp_size
            safe_addr = safe_addresses[variant.patch_id]
            fast_addr = fast_addresses[variant.patch_id]

            if self.arch == TargetArch.X86_64:
                # JMP rel32: E9 + offset (relative to next instruction)
                jmp_from = region.base_address + jmp_offset + jmp_size
                rel_offset = safe_addr - jmp_from
                jmp_bytes = b"\xE9" + struct.pack("<i", rel_offset)
                region.write(jmp_offset, jmp_bytes)
            else:
                # ARM64: B imm26
                jmp_from = region.base_address + jmp_offset
                imm26 = ((safe_addr - jmp_from) >> 2) & 0x03FFFFFF
                instr = 0x14000000 | imm26
                region.write(jmp_offset, struct.pack("<I", instr))

            entry = JumpTableEntry(
                patch_id=variant.patch_id,
                jmp_offset=jmp_offset,
                safe_target=safe_addr,
                fast_target=fast_addr,
                is_patched=False,
            )
            self.jump_table.append(entry)

        # Trả về raw bytes của jump table
        return bytearray(region.read(0, code_offset))

    # ── Runtime Patching ───────────────────────────────────

    def patch_to_fast(self, patch_id: str, region: JITRegion) -> bool:
        """
        Vá: chuyển JMP từ Bản A (Safe) → Bản B (Fast).
        Spec §3.2.3 – Ghi đè địa chỉ đích của lệnh JMP.
        """
        entry = self._find_entry(patch_id)
        if entry is None or entry.is_patched:
            return False

        jmp_size = 5 if self.arch == TargetArch.X86_64 else 4
        if self.arch == TargetArch.X86_64:
            jmp_from = region.base_address + entry.jmp_offset + jmp_size
            rel_offset = entry.fast_target - jmp_from
            region.write(entry.jmp_offset + 1, struct.pack("<i", rel_offset))
        else:
            jmp_from = region.base_address + entry.jmp_offset
            imm26 = ((entry.fast_target - jmp_from) >> 2) & 0x03FFFFFF
            instr = 0x14000000 | imm26
            region.write(entry.jmp_offset, struct.pack("<I", instr))

        entry.is_patched = True
        return True

    def patch_to_safe(self, patch_id: str, region: JITRegion) -> bool:
        """Rollback: chuyển lại về Bản A (Safe)."""
        entry = self._find_entry(patch_id)
        if entry is None or not entry.is_patched:
            return False

        jmp_size = 5 if self.arch == TargetArch.X86_64 else 4
        if self.arch == TargetArch.X86_64:
            jmp_from = region.base_address + entry.jmp_offset + jmp_size
            rel_offset = entry.safe_target - jmp_from
            region.write(entry.jmp_offset + 1, struct.pack("<i", rel_offset))
        else:
            jmp_from = region.base_address + entry.jmp_offset
            imm26 = ((entry.safe_target - jmp_from) >> 2) & 0x03FFFFFF
            instr = 0x14000000 | imm26
            region.write(entry.jmp_offset, struct.pack("<I", instr))

        entry.is_patched = False
        return True

    # ── macOS JIT Write Protection ─────────────────────────

    @staticmethod
    def _macos_write_protect_off() -> None:
        """pthread_jit_write_protect_np(0) – mở khóa ghi."""
        try:
            lib = _get_libpthread()
            if lib:
                lib.pthread_jit_write_protect_np(0)
        except Exception:
            pass

    @staticmethod
    def _macos_write_protect_on() -> None:
        """pthread_jit_write_protect_np(1) – khóa chạy."""
        try:
            lib = _get_libpthread()
            if lib:
                lib.pthread_jit_write_protect_np(1)
        except Exception:
            pass

    @staticmethod
    def _macos_icache_invalidate(addr: int, size: int) -> None:
        """sys_icache_invalidate – flush instruction cache after JIT write."""
        try:
            lib = _get_libc()
            if lib:
                lib.sys_icache_invalidate.argtypes = [
                    ctypes.c_void_p, ctypes.c_size_t
                ]
                lib.sys_icache_invalidate(ctypes.c_void_p(addr), size)
        except Exception:
            pass

    # ── Internal ───────────────────────────────────────────

    def _find_entry(self, patch_id: str) -> JumpTableEntry | None:
        for e in self.jump_table:
            if e.patch_id == patch_id:
                return e
        return None
