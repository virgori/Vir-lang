"""
Vir SDK — Public Python API for the Vir Language Engine
========================================================

Provides a clean, documented interface to:
  - Compile and run Vir source code
  - Access the Q-IR intermediate representation
  - Load and call the native C core (JIT, codegen, SIMD)
  - GPU compute operations
  - Virgex pattern matching

Usage::

    from src.sdk import VirEngine

    engine = VirEngine()
    result = engine.run_file("hello.vir")

    # Or compile to IR
    ir = engine.compile("let x = 42; print(x);")
    print(ir.instructions)

    # GPU compute
    if engine.gpu_available():
        engine.gpu_vec_add(a, b, out, n)
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════
# Core Library Loader
# ═══════════════════════════════════════════════════════

_LIB_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "lib"
_BUILD_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "build"


def _find_core_lib() -> Path | None:
    """Locate libvir_core shared library."""
    system = platform.system()
    if system == "Darwin":
        names = ["libvir_core.dylib"]
    elif system == "Windows":
        names = ["vir_core.dll"]
    else:
        names = ["libvir_core.so"]

    for name in names:
        for d in [_LIB_DIR, _BUILD_DIR]:
            p = d / name
            if p.exists():
                return p
    return None


_core_lib: ctypes.CDLL | None = None


def _get_core() -> ctypes.CDLL | None:
    """Load the native core library (lazy, cached)."""
    global _core_lib
    if _core_lib is not None:
        return _core_lib
    path = _find_core_lib()
    if path is None:
        return None
    _core_lib = ctypes.CDLL(str(path))
    return _core_lib


# ═══════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════

@dataclass
class IRInstruction:
    """A single Q-IR instruction."""
    opcode: int
    opcode_name: str
    dest: int | str | None
    src1: int | str | None
    src2: int | str | None
    line: int = 0


@dataclass
class IRModule:
    """A compiled Q-IR module."""
    instructions: list[IRInstruction] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    string_table: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    """Result of running Vir code."""
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class DeviceInfo:
    """GPU device information."""
    ordinal: int
    name: str
    compute_major: int
    compute_minor: int
    total_mem: int
    sm_count: int


# ═══════════════════════════════════════════════════════
# VirEngine — Main SDK Entry Point
# ═══════════════════════════════════════════════════════

class VirEngine:
    """High-level API for the Vir language engine.

    Parameters
    ----------
    core_path : Path, optional
        Explicit path to libvir_core shared library.
    """

    def __init__(self, core_path: Path | None = None) -> None:
        if core_path:
            self._core = ctypes.CDLL(str(core_path))
        else:
            self._core = _get_core()
        self._gpu_inited = False

    @property
    def native_available(self) -> bool:
        """Check if the native C core is loaded."""
        return self._core is not None

    # ── Compilation ──────────────────────────────────

    def compile(self, source: str) -> IRModule:
        """Compile Vir source code to Q-IR.

        Uses the Python frontend (lexer → parser → IR lowering).
        """
        from src.frontend.lexer import Lexer
        from src.frontend.parser import Parser
        from src.ir.lowering import lower_ast

        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        ir = lower_ast(ast)

        module = IRModule()
        for instr in ir.instructions:
            module.instructions.append(IRInstruction(
                opcode=instr.opcode,
                opcode_name=instr.opcode_name if hasattr(instr, 'opcode_name') else str(instr.opcode),
                dest=getattr(instr, 'dest', None),
                src1=getattr(instr, 'src1', None),
                src2=getattr(instr, 'src2', None),
                line=getattr(instr, 'line', 0),
            ))
        return module

    def run_source(self, source: str) -> RunResult:
        """Compile and run Vir source code."""
        from src.runtime.lifecycle.lifecycle import run_source
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out = io.StringIO()
        err = io.StringIO()
        exit_code = 0
        try:
            with redirect_stdout(out), redirect_stderr(err):
                exit_code = run_source(source) or 0
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 1
        except Exception as e:
            err.write(str(e))
            exit_code = 1

        return RunResult(
            exit_code=exit_code,
            stdout=out.getvalue(),
            stderr=err.getvalue(),
        )

    def run_file(self, path: str | Path) -> RunResult:
        """Compile and run a .vir file."""
        source = Path(path).read_text(encoding="utf-8")
        return self.run_source(source)

    # ── CPU Capabilities ─────────────────────────────

    def cpu_arch(self) -> str:
        """Get the CPU architecture (x86_64, aarch64, etc.)."""
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            return "x86_64"
        if machine in ("aarch64", "arm64"):
            return "aarch64"
        return machine

    # ── GPU Operations ───────────────────────────────

    def gpu_available(self) -> bool:
        """Check if GPU compute is available."""
        if not self._core:
            return False
        try:
            rc = self._core.vir_gpu_cuda_init()
            self._gpu_inited = (rc == 0)
            return self._gpu_inited
        except (OSError, AttributeError):
            return False

    def gpu_device_count(self) -> int:
        if not self._gpu_inited:
            return 0
        return self._core.vir_gpu_cuda_device_count()

    def gpu_device_info(self, ordinal: int = 0) -> DeviceInfo | None:
        """Get GPU device information."""
        if not self._gpu_inited:
            return None

        class _CDeviceInfo(ctypes.Structure):
            _fields_ = [
                ("ordinal", ctypes.c_int),
                ("name", ctypes.c_char * 256),
                ("compute_major", ctypes.c_int),
                ("compute_minor", ctypes.c_int),
                ("total_mem", ctypes.c_int64),
                ("sm_count", ctypes.c_int),
                ("max_threads_per_block", ctypes.c_int),
                ("max_shared_mem_per_block", ctypes.c_int),
                ("warp_size", ctypes.c_int),
            ]

        info = _CDeviceInfo()
        rc = self._core.vir_gpu_cuda_device_info(ordinal, ctypes.byref(info))
        if rc != 0:
            return None

        return DeviceInfo(
            ordinal=info.ordinal,
            name=info.name.decode("utf-8", errors="replace").rstrip("\x00"),
            compute_major=info.compute_major,
            compute_minor=info.compute_minor,
            total_mem=info.total_mem,
            sm_count=info.sm_count,
        )

    # ── Virgex ───────────────────────────────────────

    @staticmethod
    def virgex_match(pattern: str, text: str, *, engine: str = "regex") -> bool:
        """Test if a VPS pattern matches text."""
        from virgex.src import Virgex
        v = Virgex(pattern, engine=engine)
        return v.fullmatch(text) is not None

    @staticmethod
    def virgex_search(pattern: str, text: str, *, engine: str = "regex") -> str | None:
        """Search for a VPS pattern in text, return matched substring."""
        from virgex.src import Virgex
        v = Virgex(pattern, engine=engine)
        m = v.search(text)
        return m.text if m else None

    @staticmethod
    def virgex_to_regex(pattern: str) -> str:
        """Translate a VPS pattern to Python regex."""
        from virgex.src import to_regex
        return to_regex(pattern)

    # ── Version Info ─────────────────────────────────

    @staticmethod
    def version() -> str:
        return "0.3.0"

    def __repr__(self) -> str:
        native = "native" if self.native_available else "python-only"
        return f"VirEngine(v{self.version()}, {self.cpu_arch()}, {native})"
