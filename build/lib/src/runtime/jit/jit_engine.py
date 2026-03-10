"""
jit_engine.py – JIT Engine
============================
Spec §5 Giai đoạn 3 & 4:
  - Giai đoạn 3: Xin quyền JIT từ OS.
  - Giai đoạn 4: Trong khi chạy, liên tục kiểm tra chip.
                 Nếu rảnh → vá Q-IR thành Assembly thuần túy.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.backend.codegen.codegen import CodeGenerator, CodeVariant, TargetArch
from src.backend.monitor.pressure_monitor import (
    ExecutionMode,
    RegisterPressureMonitor,
)
from src.backend.patcher.binary_patcher import BinaryPatcher, JITRegion
from src.runtime.bridge.bridge_api import BridgeBackend, create_bridge
from src.security.signer.internal_signer import InternalSigner


@dataclass
class PatchRecord:
    """Lịch sử patch."""
    patch_id: str
    timestamp: float
    mode: ExecutionMode
    success: bool


class JITEngine:
    """
    JIT Engine – điều phối vá mã runtime.

    Lifecycle:
    1. Nhận variants từ CodeGenerator.
    2. Cấp phát JIT memory qua Bridge API.
    3. Xây Jump Table (ban đầu trỏ Safe).
    4. Chạy background thread: giám sát CPU → vá khi rảnh.
    """

    def __init__(
        self,
        arch: TargetArch = TargetArch.X86_64,
        monitor_interval: float = 1.0,
    ) -> None:
        self.arch = arch
        self.monitor_interval = monitor_interval

        self._patcher = BinaryPatcher(arch=arch)
        self._monitor = RegisterPressureMonitor()
        self._signer = InternalSigner()
        self._bridge: BridgeBackend = create_bridge()

        self._region: JITRegion | None = None
        self._variants: list[CodeVariant] = []
        self._history: list[PatchRecord] = []

        self._running = False
        self._thread: threading.Thread | None = None

    # ── Phase 3: Initialize ────────────────────────────────

    def initialize(self, variants: list[CodeVariant]) -> None:
        """
        Giai đoạn 3: Chuẩn bị JIT region + Jump Table.
        """
        self._variants = variants

        # Tính kích thước cần cấp phát
        total_size = 0
        for v in variants:
            total_size += len(v.safe_code.bytes_) + len(v.fast_code.bytes_)
        total_size += len(variants) * 8  # jump table overhead
        total_size = max(total_size * 2, 4096)  # safety margin

        # Cấp phát vùng nhớ JIT
        self._region = self._patcher.allocate_jit_region(total_size)

        # Xây dựng Jump Table (ban đầu trỏ Safe)
        self._patcher.build_jump_table(variants, self._region)

        # Ký tất cả safe code
        for v in variants:
            self._signer.sign(v.patch_id, v.safe_code.bytes_)

    # ── Phase 4: Evolution Loop ────────────────────────────

    def start_evolution(self) -> None:
        """
        Giai đoạn 4: Bắt đầu background thread giám sát + vá mã.
        """
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._evolution_loop, daemon=True, name="vir-jit-evolution"
        )
        self._thread.start()

    def stop_evolution(self) -> None:
        """Dừng background evolution."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _evolution_loop(self) -> None:
        """Background loop: kiểm tra CPU → vá mã nếu rảnh."""
        while self._running:
            cpu_state = self._monitor.probe()

            if cpu_state.mode == ExecutionMode.HIGH_PERFORMANCE_REG:
                # CPU rảnh → vá sang Bản B (Fast)
                self._patch_all_to_fast()
            else:
                # CPU bận → rollback về Bản A (Safe)
                self._patch_all_to_safe()

            time.sleep(self.monitor_interval)

    def _patch_all_to_fast(self) -> None:
        """Vá tất cả patch points sang Fast mode."""
        if self._region is None:
            return
        for entry in self._patcher.jump_table:
            if not entry.is_patched:
                # Ký fast code trước khi vá
                variant = self._find_variant(entry.patch_id)
                if variant:
                    self._signer.sign(entry.patch_id, variant.fast_code.bytes_)

                success = self._patcher.patch_to_fast(entry.patch_id, self._region)
                self._history.append(PatchRecord(
                    patch_id=entry.patch_id,
                    timestamp=time.time(),
                    mode=ExecutionMode.HIGH_PERFORMANCE_REG,
                    success=success,
                ))

    def _patch_all_to_safe(self) -> None:
        """Rollback tất cả về Safe mode."""
        if self._region is None:
            return
        for entry in self._patcher.jump_table:
            if entry.is_patched:
                variant = self._find_variant(entry.patch_id)
                if variant:
                    self._signer.sign(entry.patch_id, variant.safe_code.bytes_)

                success = self._patcher.patch_to_safe(entry.patch_id, self._region)
                self._history.append(PatchRecord(
                    patch_id=entry.patch_id,
                    timestamp=time.time(),
                    mode=ExecutionMode.SAFE_STACK,
                    success=success,
                ))

    def _find_variant(self, patch_id: str) -> CodeVariant | None:
        for v in self._variants:
            if v.patch_id == patch_id:
                return v
        return None

    # ── Query ──────────────────────────────────────────────

    def get_history(self) -> list[PatchRecord]:
        return list(self._history)

    def get_current_modes(self) -> dict[str, str]:
        """Trả về trạng thái hiện tại của mỗi patch point."""
        return {
            e.patch_id: ("FAST" if e.is_patched else "SAFE")
            for e in self._patcher.jump_table
        }

    @property
    def is_running(self) -> bool:
        return self._running
