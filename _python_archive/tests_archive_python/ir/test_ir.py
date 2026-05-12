"""
test_ir.py – Unit tests cho Q-IR & IR Builder
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ir.instructions.q_ir import (
    Immediate, Label, Opcode, QFunction, QInstruction, QModule, VReg,
)
from src.ir.registers.virtual_registers import VirtualRegisterAllocator
from src.ir.optimizer.optimizer import IROptimizer


class TestQIR:
    def test_instruction_repr(self):
        instr = QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(1), src2=VReg(2))
        assert "Q_ADD" in str(instr)
        assert "R0" in str(instr)

    def test_function(self):
        func = QFunction(name="test", params=[VReg(0)])
        func.append(QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(42)))
        func.append(QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)))
        func.append(QInstruction(Opcode.Q_RET, src1=VReg(2)))
        assert len(func.body) == 3

    def test_module_dump(self):
        mod = QModule(name="test_mod")
        func = QFunction(name="main")
        func.append(QInstruction(Opcode.Q_NOP))
        mod.add_function(func)
        dump = mod.dump()
        assert "module test_mod" in dump
        assert "func @main" in dump

    def test_patch_point(self):
        instr = QInstruction(Opcode.Q_PATCH_POINT, patch_id="POINT_TOTAL")
        assert instr.patch_id == "POINT_TOTAL"


class TestVirtualRegisters:
    def test_alloc(self):
        alloc = VirtualRegisterAllocator()
        r0 = alloc.alloc("x")
        r1 = alloc.alloc("y")
        assert r0.index == 0
        assert r1.index == 1

    def test_lookup(self):
        alloc = VirtualRegisterAllocator()
        alloc.alloc("x")
        assert alloc.lookup("x") is not None
        assert alloc.lookup("z") is None

    def test_total(self):
        alloc = VirtualRegisterAllocator()
        for _ in range(100):
            alloc.alloc()
        assert alloc.total_allocated() == 100


class TestOptimizer:
    def test_constant_fold(self):
        func = QFunction(name="test")
        func.append(QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)))
        func.append(QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)))
        func.append(QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)))
        func.append(QInstruction(Opcode.Q_RET, src1=VReg(2)))

        mod = QModule()
        mod.add_function(func)

        opt = IROptimizer()
        opt.optimize(mod)

        # The ADD should be folded into Q_LOAD R2, #30.0
        folded = [i for i in func.body if "folded" in i.comment]
        assert len(folded) == 1
