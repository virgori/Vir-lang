"""
vir_native.py – Python ctypes FFI Bindings for libvir_core
═══════════════════════════════════════════════════════════════
Provides Python access to the native C/ASM engine.

Usage:
    from src.native.vir_native import VirNativeEngine
    engine = VirNativeEngine()
    engine.load_library()

    # Use Q-IR
    mod = engine.create_module("hello")
    func = engine.create_function("main")
    ...
"""

import ctypes
import ctypes.util
import os
import platform
import sys
from pathlib import Path
from typing import Optional, Tuple, List


# ═══════════════════════════════════════════════════════
# C Structure Definitions (mirror core/include/*.h)
# ═══════════════════════════════════════════════════════

class QOperand(ctypes.Structure):
    """q_operand_t"""
    _fields_ = [
        ("type", ctypes.c_int),      # operand_type_t enum
        ("vreg", ctypes.c_uint32),
        ("imm",  ctypes.c_int64),
        ("label", ctypes.c_char * 64),
    ]

class QInstruction(ctypes.Structure):
    """q_instruction_t"""
    _fields_ = [
        ("opcode",   ctypes.c_int),   # q_opcode_t enum
        ("dest",     QOperand),
        ("src1",     QOperand),
        ("src2",     QOperand),
        ("patch_id", ctypes.c_uint32),
    ]

class QFunction(ctypes.Structure):
    """q_function_t"""
    _fields_ = [
        ("name",       ctypes.c_char * 128),
        ("body",       ctypes.POINTER(QInstruction)),
        ("body_count", ctypes.c_uint32),
        ("body_cap",   ctypes.c_uint32),
    ]

class QModule(ctypes.Structure):
    """q_module_t"""
    _fields_ = [
        ("name",       ctypes.c_char * 128),
        ("functions",  ctypes.POINTER(QFunction)),
        ("func_count", ctypes.c_uint32),
        ("func_cap",   ctypes.c_uint32),
    ]

class QVRegAlloc(ctypes.Structure):
    """q_vreg_alloc_t"""
    _fields_ = [
        ("next_reg", ctypes.c_uint32),
    ]

class VMState(ctypes.Structure):
    """vm_state_t (simplified – actual has 64K regs)"""
    _fields_ = [
        ("regs",       ctypes.c_int64 * 65536),
        ("labels",     ctypes.c_char * (256 * 64)),  # label_entry_t array placeholder
        ("label_count", ctypes.c_uint32),
        ("call_stack", ctypes.c_uint32 * 256),
        ("call_sp",    ctypes.c_uint32),
        ("halted",     ctypes.c_int),
        ("patch_handler",    ctypes.c_void_p),
        ("patch_handler_ctx", ctypes.c_void_p),
    ]

class CodeBuf(ctypes.Structure):
    """codebuf_t"""
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("len",  ctypes.c_size_t),
        ("cap",  ctypes.c_size_t),
        ("arch", ctypes.c_int),
    ]

class CPUState(ctypes.Structure):
    """cpu_state_t"""
    _fields_ = [
        ("os",           ctypes.c_int),
        ("core_count",   ctypes.c_uint32),
        ("load_percent", ctypes.c_double),
        ("n_free",       ctypes.c_uint32),
        ("mode",         ctypes.c_int),
    ]

class CodeSignature(ctypes.Structure):
    """code_signature_t"""
    _fields_ = [
        ("hmac",     ctypes.c_uint8 * 32),
        ("code_ptr", ctypes.c_void_p),
        ("code_len", ctypes.c_size_t),
        ("valid",    ctypes.c_int),
    ]

class Signer(ctypes.Structure):
    """signer_t"""
    _fields_ = [
        ("key",          ctypes.c_uint8 * 64),
        ("key_len",      ctypes.c_size_t),
        ("sign_count",   ctypes.c_uint32),
        ("verify_count", ctypes.c_uint32),
    ]


# ═══════════════════════════════════════════════════════
# Operand type constants
# ═══════════════════════════════════════════════════════
OPERAND_NONE  = 0
OPERAND_VREG  = 1
OPERAND_IMM   = 2
OPERAND_LABEL = 3

# Opcodes
Q_NOP   = 0x00
Q_LOAD  = 0x01
Q_STORE = 0x02
Q_MOVE  = 0x03
Q_ADD   = 0x10
Q_SUB   = 0x11
Q_MUL   = 0x12
Q_DIV   = 0x13
Q_MOD   = 0x14
Q_AND   = 0x15
Q_OR    = 0x16
Q_XOR   = 0x17
Q_SHL   = 0x18
Q_SHR   = 0x19
Q_CMP_EQ = 0x20
Q_CMP_GT = 0x21
Q_CMP_LT = 0x22
Q_JUMP      = 0x30
Q_JUMP_IF   = 0x31
Q_JUMP_IFNOT = 0x32
Q_CALL      = 0x33
Q_RET       = 0x34
Q_PRINT  = 0x40
Q_INPUT  = 0x41
Q_LABEL       = 0x50
Q_CHECK_CPU   = 0x51
Q_PATCH_POINT = 0x52
Q_HALT = 0xFF

# Architecture
ARCH_UNKNOWN = 0
ARCH_X86_64  = 1
ARCH_ARM64   = 2

# Exec mode
EXEC_MODE_SAFE = 0
EXEC_MODE_FAST = 1


# ═══════════════════════════════════════════════════════
# Native Engine Wrapper
# ═══════════════════════════════════════════════════════

class VirNativeEngine:
    """Python interface to libvir_core native library."""

    def __init__(self, lib_path: Optional[str] = None):
        self._lib = None
        self._lib_path = lib_path

    def load_library(self) -> bool:
        """Load the native shared library."""
        if self._lib is not None:
            return True

        search_paths = []
        if self._lib_path:
            search_paths.append(self._lib_path)

        # Determine library filename
        system = platform.system()
        if system == "Darwin":
            lib_name = "libvir_core.dylib"
        elif system == "Linux":
            lib_name = "libvir_core.so"
        elif system == "Windows":
            lib_name = "vir_core.dll"
        else:
            lib_name = "libvir_core.so"

        # Search paths relative to this file
        native_dir = Path(__file__).resolve().parent
        base = native_dir.parent.parent
        search_paths.extend([
            str(native_dir / "lib" / lib_name),   # bundled in wheel
            str(base / "core" / "lib" / lib_name),
            str(base / "core" / "build" / lib_name),
            str(base / lib_name),
        ])

        for path in search_paths:
            if os.path.exists(path):
                try:
                    self._lib = ctypes.cdll.LoadLibrary(path)
                    self._setup_prototypes()
                    return True
                except OSError as e:
                    print(f"[vir_native] Failed to load {path}: {e}")

        print(f"[vir_native] Library not found. Build with: cd core && make")
        return False

    def _setup_prototypes(self):
        """Configure C function signatures."""
        lib = self._lib

        # Q-IR
        lib.q_operand_none.restype = QOperand
        lib.q_operand_vreg.restype = QOperand
        lib.q_operand_vreg.argtypes = [ctypes.c_uint32]
        lib.q_operand_imm.restype = QOperand
        lib.q_operand_imm.argtypes = [ctypes.c_int64]

        lib.q_instr_create.restype = QInstruction
        lib.q_instr_create.argtypes = [
            ctypes.c_int, QOperand, QOperand, QOperand
        ]

        lib.q_function_init.argtypes = [
            ctypes.POINTER(QFunction), ctypes.c_char_p
        ]
        lib.q_function_emit.argtypes = [
            ctypes.POINTER(QFunction), ctypes.POINTER(QInstruction)
        ]
        lib.q_function_free.argtypes = [ctypes.POINTER(QFunction)]

        lib.q_module_init.argtypes = [
            ctypes.POINTER(QModule), ctypes.c_char_p
        ]
        lib.q_module_add_function.argtypes = [
            ctypes.POINTER(QModule), ctypes.POINTER(QFunction)
        ]
        lib.q_module_free.argtypes = [ctypes.POINTER(QModule)]

        lib.q_vreg_alloc_init.argtypes = [ctypes.POINTER(QVRegAlloc)]
        lib.q_vreg_alloc_next.restype = ctypes.c_uint32
        lib.q_vreg_alloc_next.argtypes = [ctypes.POINTER(QVRegAlloc)]

        # VM
        lib.vm_init.argtypes = [ctypes.POINTER(VMState)]
        lib.vm_exec_function.restype = ctypes.c_int64
        lib.vm_exec_function.argtypes = [
            ctypes.POINTER(VMState), ctypes.POINTER(QFunction)
        ]

        # Codegen
        lib.codegen_detect_arch.restype = ctypes.c_int
        lib.codebuf_init.argtypes = [
            ctypes.POINTER(CodeBuf), ctypes.c_int
        ]
        lib.codebuf_free.argtypes = [ctypes.POINTER(CodeBuf)]

        # Bridge
        lib.bridge_detect_os.restype = ctypes.c_int
        lib.bridge_cpu_probe.argtypes = [ctypes.POINTER(CPUState)]
        lib.bridge_cpu_probe.restype = ctypes.c_int

        # Signer
        lib.signer_init.argtypes = [ctypes.POINTER(Signer)]
        lib.signer_sign.argtypes = [
            ctypes.POINTER(Signer), ctypes.c_void_p, ctypes.c_size_t,
            ctypes.POINTER(CodeSignature)
        ]
        lib.signer_verify.restype = ctypes.c_int
        lib.signer_verify.argtypes = [
            ctypes.POINTER(Signer), ctypes.c_void_p, ctypes.c_size_t,
            ctypes.POINTER(CodeSignature)
        ]
        lib.sha256_hash.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_uint8 * 32
        ]

    # ── High-level Python API ──────────────────────────

    def detect_arch(self) -> str:
        arch = self._lib.codegen_detect_arch()
        return {ARCH_X86_64: "x86_64", ARCH_ARM64: "arm64"}.get(arch, "unknown")

    def detect_os(self) -> str:
        os_id = self._lib.bridge_detect_os()
        return {1: "macOS", 2: "Linux", 3: "Windows"}.get(os_id, "unknown")

    def cpu_probe(self) -> dict:
        state = CPUState()
        self._lib.bridge_cpu_probe(ctypes.byref(state))
        return {
            "cores": state.core_count,
            "load_percent": state.load_percent,
            "n_free": state.n_free,
            "mode": "fast" if state.mode == EXEC_MODE_FAST else "safe",
        }

    def sha256(self, data: bytes) -> bytes:
        digest = (ctypes.c_uint8 * 32)()
        buf = ctypes.create_string_buffer(data)
        self._lib.sha256_hash(buf, len(data), digest)
        return bytes(digest)

    def create_module(self, name: str) -> QModule:
        mod = QModule()
        self._lib.q_module_init(ctypes.byref(mod), name.encode())
        return mod

    def create_function(self, name: str) -> QFunction:
        func = QFunction()
        self._lib.q_function_init(ctypes.byref(func), name.encode())
        return func

    def alloc_vreg(self) -> Tuple['QVRegAlloc', int]:
        alloc = QVRegAlloc()
        self._lib.q_vreg_alloc_init(ctypes.byref(alloc))
        return alloc

    def emit_load(self, func: QFunction, dest_vreg: int, imm: int):
        instr = self._lib.q_instr_create(
            Q_LOAD,
            self._lib.q_operand_vreg(dest_vreg),
            self._lib.q_operand_imm(imm),
            self._lib.q_operand_none()
        )
        self._lib.q_function_emit(ctypes.byref(func), ctypes.byref(instr))

    def emit_add(self, func: QFunction, dest: int, src1: int, src2: int):
        instr = self._lib.q_instr_create(
            Q_ADD,
            self._lib.q_operand_vreg(dest),
            self._lib.q_operand_vreg(src1),
            self._lib.q_operand_vreg(src2),
        )
        self._lib.q_function_emit(ctypes.byref(func), ctypes.byref(instr))

    def emit_sub(self, func: QFunction, dest: int, src1: int, src2: int):
        instr = self._lib.q_instr_create(
            Q_SUB,
            self._lib.q_operand_vreg(dest),
            self._lib.q_operand_vreg(src1),
            self._lib.q_operand_vreg(src2),
        )
        self._lib.q_function_emit(ctypes.byref(func), ctypes.byref(instr))

    def emit_mul(self, func: QFunction, dest: int, src1: int, src2: int):
        instr = self._lib.q_instr_create(
            Q_MUL,
            self._lib.q_operand_vreg(dest),
            self._lib.q_operand_vreg(src1),
            self._lib.q_operand_vreg(src2),
        )
        self._lib.q_function_emit(ctypes.byref(func), ctypes.byref(instr))

    def emit_ret(self, func: QFunction, src_vreg: int):
        instr = self._lib.q_instr_create(
            Q_RET,
            self._lib.q_operand_none(),
            self._lib.q_operand_vreg(src_vreg),
            self._lib.q_operand_none()
        )
        self._lib.q_function_emit(ctypes.byref(func), ctypes.byref(instr))

    def vm_execute(self, func: QFunction) -> int:
        vm = VMState()
        self._lib.vm_init(ctypes.byref(vm))
        return self._lib.vm_exec_function(ctypes.byref(vm), ctypes.byref(func))

    def free_module(self, mod: QModule):
        self._lib.q_module_free(ctypes.byref(mod))

    def free_function(self, func: QFunction):
        self._lib.q_function_free(ctypes.byref(func))


# ═══════════════════════════════════════════════════════
# Quick Test
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = VirNativeEngine()
    if not engine.load_library():
        print("Build the native library first: cd core && make")
        sys.exit(1)

    print(f"Platform: {engine.detect_os()}")
    print(f"Arch: {engine.detect_arch()}")
    print(f"CPU: {engine.cpu_probe()}")

    # Test: 42 + 58 = 100
    func = engine.create_function("test_add")
    engine.emit_load(func, 0, 42)
    engine.emit_load(func, 1, 58)
    engine.emit_add(func, 2, 0, 1)
    engine.emit_ret(func, 2)

    result = engine.vm_execute(func)
    print(f"\n42 + 58 = {result}")
    assert result == 100, f"Expected 100, got {result}"
    print("✓ Native engine working!")

    engine.free_function(func)
