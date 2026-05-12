"""
CPU Probe — Detect ISA, cache topology, vector width at runtime.
=================================================================
Supports macOS arm64 (NEON/AMX) and x86_64 (SSE2/AVX2/AVX-512).
"""

from __future__ import annotations

import os
import platform
import struct
import subprocess
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CPUInfo:
    """Detected CPU capabilities."""
    arch: str                  # "arm64" or "x86_64"
    vendor: str = ""           # "Apple", "AMD", "Intel"
    model_name: str = ""
    physical_cores: int = 1
    logical_cores: int = 1
    cache_line_bytes: int = 64
    l1d_bytes: int = 0
    l2_bytes: int = 0
    l3_bytes: int = 0
    page_size: int = 4096

    # Vector ISA flags
    has_neon: bool = False
    has_amx: bool = False      # Apple AMX
    has_sse2: bool = False
    has_avx2: bool = False
    has_avx512: bool = False
    has_f16c: bool = False
    has_fma: bool = False

    @property
    def vector_width_bytes(self) -> int:
        """Widest usable SIMD register in bytes."""
        if self.has_avx512:
            return 64
        if self.has_avx2:
            return 32
        if self.has_neon or self.has_sse2:
            return 16
        return 0

    @property
    def vector_width_f32(self) -> int:
        """Number of float32 lanes in widest vector."""
        return self.vector_width_bytes // 4


class CPUProbe:
    """Probe current CPU capabilities."""

    @staticmethod
    def probe() -> CPUInfo:
        arch = platform.machine()
        system = platform.system()

        if arch == "arm64" and system == "Darwin":
            return CPUProbe._probe_macos_arm64()
        if arch == "x86_64":
            if system == "Darwin":
                return CPUProbe._probe_macos_x86()
            return CPUProbe._probe_linux_x86()
        # Fallback
        return CPUInfo(arch=arch, physical_cores=os.cpu_count() or 1,
                       logical_cores=os.cpu_count() or 1)

    @staticmethod
    def _probe_macos_arm64() -> CPUInfo:
        def sysctl_int(key: str) -> int:
            try:
                out = subprocess.check_output(
                    ["sysctl", "-n", key], text=True, timeout=2
                ).strip()
                return int(out)
            except (subprocess.SubprocessError, ValueError):
                return 0

        def sysctl_str(key: str) -> str:
            try:
                return subprocess.check_output(
                    ["sysctl", "-n", key], text=True, timeout=2
                ).strip()
            except subprocess.SubprocessError:
                return ""

        model = sysctl_str("machdep.cpu.brand_string")
        pcores = sysctl_int("hw.perflevel0.physicalcpu") or sysctl_int("hw.physicalcpu")
        lcores = sysctl_int("hw.logicalcpu")
        l1d = sysctl_int("hw.perflevel0.l1dcachesize")
        l2 = sysctl_int("hw.perflevel0.l2cachesize")
        page = sysctl_int("hw.pagesize") or 16384  # macOS arm64 default

        return CPUInfo(
            arch="arm64", vendor="Apple", model_name=model,
            physical_cores=pcores or 1, logical_cores=lcores or 1,
            cache_line_bytes=128,  # Apple Silicon
            l1d_bytes=l1d, l2_bytes=l2,
            page_size=page,
            has_neon=True,
            has_amx=True,  # All Apple Silicon has AMX
        )

    @staticmethod
    def _probe_macos_x86() -> CPUInfo:
        def sysctl_int(key: str) -> int:
            try:
                out = subprocess.check_output(
                    ["sysctl", "-n", key], text=True, timeout=2
                ).strip()
                return int(out)
            except (subprocess.SubprocessError, ValueError):
                return 0

        def sysctl_str(key: str) -> str:
            try:
                return subprocess.check_output(
                    ["sysctl", "-n", key], text=True, timeout=2
                ).strip()
            except subprocess.SubprocessError:
                return ""

        model = sysctl_str("machdep.cpu.brand_string")
        vendor = sysctl_str("machdep.cpu.vendor")
        features = sysctl_str("machdep.cpu.features").upper()
        leaf7 = sysctl_str("machdep.cpu.leaf7_features").upper()
        pcores = sysctl_int("hw.physicalcpu")
        lcores = sysctl_int("hw.logicalcpu")
        l1d = sysctl_int("hw.l1dcachesize")
        l2 = sysctl_int("hw.l2cachesize")
        l3 = sysctl_int("hw.l3cachesize")

        return CPUInfo(
            arch="x86_64", vendor=vendor, model_name=model,
            physical_cores=pcores or 1, logical_cores=lcores or 1,
            cache_line_bytes=64, l1d_bytes=l1d, l2_bytes=l2, l3_bytes=l3,
            page_size=4096,
            has_sse2="SSE2" in features,
            has_avx2="AVX2" in leaf7,
            has_avx512="AVX512" in features or "AVX512F" in leaf7,
            has_f16c="F16C" in features,
            has_fma="FMA" in features,
        )

    @staticmethod
    def _probe_linux_x86() -> CPUInfo:
        flags_str = ""
        model = ""
        vendor = ""
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                    elif line.startswith("vendor_id"):
                        vendor = line.split(":", 1)[1].strip()
                    elif line.startswith("flags"):
                        flags_str = line.split(":", 1)[1].upper()
                        break
        except OSError:
            pass

        cores = os.cpu_count() or 1
        page = os.sysconf("SC_PAGESIZE") if hasattr(os, "sysconf") else 4096

        return CPUInfo(
            arch="x86_64", vendor=vendor, model_name=model,
            physical_cores=cores, logical_cores=cores,
            cache_line_bytes=64, page_size=page,
            has_sse2="SSE2" in flags_str,
            has_avx2="AVX2" in flags_str,
            has_avx512="AVX512F" in flags_str,
            has_f16c="F16C" in flags_str,
            has_fma="FMA" in flags_str,
        )
