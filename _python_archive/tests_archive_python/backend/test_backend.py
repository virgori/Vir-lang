"""
test_backend.py – Unit tests cho Backend (codegen, monitor, patcher)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backend.codegen.codegen import CodeGenerator, TargetArch, X86_64
from src.backend.monitor.pressure_monitor import (
    ExecutionMode, RegisterPressureMonitor,
)
from src.backend.patcher.binary_patcher import BinaryPatcher
from src.ir.instructions.q_ir import (
    Immediate, Opcode, QFunction, QInstruction, QModule, VReg,
)


class TestCodeGenerator:
    def test_x86_add_opcodes(self):
        assert X86_64.add_rax_rbx() == b"\x48\x01\xD8"
        assert X86_64.sub_rax_rbx() == b"\x48\x29\xD8"
        assert X86_64.ret() == b"\xC3"

    def test_generate_variants(self):
        mod = QModule()
        func = QFunction(name="test")
        func.append(QInstruction(Opcode.Q_PATCH_POINT, patch_id="P1"))
        func.append(QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)))
        func.append(QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(0), src2=VReg(0)))
        func.append(QInstruction(Opcode.Q_RET, src1=VReg(1)))
        mod.add_function(func)

        gen = CodeGenerator(TargetArch.X86_64)
        variants = gen.generate(mod)
        assert len(variants) >= 1
        for v in variants:
            assert len(v.safe_code.bytes_) > 0
            assert len(v.fast_code.bytes_) > 0


class TestPressureMonitor:
    def test_probe(self):
        monitor = RegisterPressureMonitor()
        state = monitor.probe()
        assert state.total_gp_registers > 0
        assert state.mode in (ExecutionMode.SAFE_STACK, ExecutionMode.HIGH_PERFORMANCE_REG)


class TestBinaryPatcher:
    def test_allocate_jit_region(self):
        patcher = BinaryPatcher()
        region = patcher.allocate_jit_region(4096)
        assert region.size == 4096
        assert region.base_address > 0

    def test_build_and_patch(self):
        # Build a simple variant
        from src.backend.codegen.codegen import CodeVariant, MachineCode

        safe = MachineCode(bytes_=bytearray(X86_64.add_rax_rbx() + X86_64.ret()),
                          arch=TargetArch.X86_64)
        fast = MachineCode(bytes_=bytearray(X86_64.add_rax_rbx()),
                          arch=TargetArch.X86_64)
        variant = CodeVariant(patch_id="TEST_P1", safe_code=safe, fast_code=fast)

        patcher = BinaryPatcher()
        region = patcher.allocate_jit_region(4096)
        patcher.build_jump_table([variant], region)

        assert len(patcher.jump_table) == 1
        assert not patcher.jump_table[0].is_patched

        # Patch to fast
        patcher.patch_to_fast("TEST_P1", region)
        assert patcher.jump_table[0].is_patched

        # Rollback
        patcher.patch_to_safe("TEST_P1", region)
        assert not patcher.jump_table[0].is_patched
