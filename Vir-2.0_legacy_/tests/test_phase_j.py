"""
test_phase_j.py – Tests for Phase J
=====================================
Tests for:
  1. Arena Allocator (stdlib source exists)
  2. Floating-Point opcodes & register allocation
  3. Separate Compilation (Mach-O object emitter)
  4. Live Range Splitting (next-use spill heuristic + cached reload)
  5. Epilogue Loop (loop unrolling remainder)
  6. Function Inlining (IPO)
  7. LICM (Loop Invariant Code Motion)
  8. Optional Static Typing (type checker)
"""

import os
import struct
import tempfile

import pytest

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)
from src.ir.optimizer.optimizer import IROptimizer
from src.ir.registers.linear_scan import (
    LinearScanAllocator,
    LiveInterval,
    RegAllocResult,
)
from src.frontend.parser.parser import (
    AssignNode,
    BinOpNode,
    CallNode,
    CompareNode,
    FuncDefNode,
    IdentifierRef,
    NumberLiteral,
    ProgramNode,
    ReturnNode,
    StringLiteral,
    VarDeclNode,
)
from src.frontend.type_check import TypeChecker
from src.backend.codegen.obj_emitter import MachOEmitter, Symbol


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_func(body: list[QInstruction], name: str = "test",
               params: list[VReg] | None = None) -> QFunction:
    return QFunction(name=name, params=params or [], body=body)


def _make_module(funcs: list[QFunction]) -> QModule:
    return QModule(functions=funcs)


def _opcodes(func: QFunction) -> list[Opcode]:
    return [i.opcode for i in func.body]


# ═══════════════════════════════════════════════════════════
# 1. Arena Allocator (source exists)
# ═══════════════════════════════════════════════════════════

class TestArenaAllocator:
    """Verify the arena.vri stdlib file is present and well-formed."""

    ARENA_PATH = os.path.join(
        os.path.dirname(__file__), "..", "core", "bootstrap", "stdlib", "arena.vri",
    )

    def test_arena_file_exists(self):
        assert os.path.isfile(self.ARENA_PATH), "arena.vri should exist"

    def test_arena_exports_expected_functions(self):
        text = open(self.ARENA_PATH).read()
        for fn in ("arena_create", "arena_alloc", "arena_reset",
                    "arena_destroy", "arena_used", "arena_free_space"):
            assert fn in text, f"arena.vri should export {fn}"


# ═══════════════════════════════════════════════════════════
# 2. Floating-Point Opcodes
# ═══════════════════════════════════════════════════════════

class TestFloatingPoint:
    """Verify FP opcodes are recognized, allocated correctly, and survive
    the optimizer pipeline without corruption."""

    def test_fp_opcodes_exist(self):
        """All 12 FP opcodes should be members of Opcode."""
        fp_names = [
            "Q_FLOAD", "Q_FSTORE", "Q_FMOVE", "Q_FADD", "Q_FSUB",
            "Q_FMUL", "Q_FDIV", "Q_FCMP_EQ", "Q_FCMP_LT", "Q_FCMP_GT",
            "Q_FCVT_I2F", "Q_FCVT_F2I",
        ]
        for name in fp_names:
            assert hasattr(Opcode, name), f"Opcode.{name} should exist"

    def test_fp_uses_vector_pool(self):
        """FP instructions should be allocated from the vector register pool."""
        body = [
            QInstruction(Opcode.Q_FLOAD, dest=VReg(0), src1=Immediate(3.14)),
            QInstruction(Opcode.Q_FLOAD, dest=VReg(1), src1=Immediate(2.72)),
            QInstruction(Opcode.Q_FADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        # All FP vregs should be assigned (not spilled) — only 3 needed
        for v in (0, 1, 2):
            assert not result.is_spilled(v), f"VReg {v} should not be spilled"
        # They should use vec pool (V0-V7 range)
        assert result.vec_regs_used > 0, "FP should use vector registers"

    def test_fp_arithmetic_survives_optimizer(self):
        """FP arithmetic passes through the optimizer intact."""
        body = [
            QInstruction(Opcode.Q_FLOAD, dest=VReg(0), src1=Immediate(1.5)),
            QInstruction(Opcode.Q_FLOAD, dest=VReg(1), src1=Immediate(2.5)),
            QInstruction(Opcode.Q_FADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_FMUL, dest=VReg(3), src1=VReg(2), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(3)),
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer()
        opt.optimize(module)
        opcodes = _opcodes(module.functions[0])
        # FP opcodes should survive (not be folded away since they're FP)
        assert Opcode.Q_FADD in opcodes or Opcode.Q_FMUL in opcodes

    def test_fp_compare_opcodes(self):
        """FP comparison opcodes should be valid instruction opcodes."""
        body = [
            QInstruction(Opcode.Q_FLOAD, dest=VReg(0), src1=Immediate(1.0)),
            QInstruction(Opcode.Q_FLOAD, dest=VReg(1), src1=Immediate(2.0)),
            QInstruction(Opcode.Q_FCMP_LT, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_FCMP_EQ, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_FCMP_GT, dest=VReg(4), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        assert result.vec_regs_used > 0

    def test_fp_conversion_opcodes(self):
        """Int↔Float conversion opcodes should allocate correctly."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_FCVT_I2F, dest=VReg(1), src1=VReg(0)),
            QInstruction(Opcode.Q_FCVT_F2I, dest=VReg(2), src1=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        assert not result.is_spilled(0)
        assert not result.is_spilled(1)


# ═══════════════════════════════════════════════════════════
# 3. Separate Compilation (Mach-O object emitter)
# ═══════════════════════════════════════════════════════════

class TestMachOEmitter:
    """Verify the Mach-O object emitter produces well-formed output."""

    def test_emitter_creates_file(self):
        emitter = MachOEmitter(arch="arm64")
        emitter.add_function("_main", b"\xc0\x03\x5f\xd6")  # RET
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
            path = f.name
        try:
            emitter.write(path)
            assert os.path.isfile(path)
            data = open(path, "rb").read()
            # Check Mach-O magic: MH_MAGIC_64 = 0xFEEDFACF
            magic = struct.unpack("<I", data[:4])[0]
            assert magic == 0xFEEDFACF, f"Expected MH_MAGIC_64, got {hex(magic)}"
        finally:
            os.unlink(path)

    def test_symbol_tracking(self):
        emitter = MachOEmitter(arch="arm64")
        emitter.add_function("_foo", b"\x00" * 8)
        emitter.add_function("_bar", b"\x00" * 16)
        assert len(emitter.symbols) == 2
        # MachO emitter may prepend underscore per Mach-O convention
        assert "foo" in emitter.symbols[0].name
        assert "bar" in emitter.symbols[1].name
        assert emitter.symbols[1].offset == 8

    def test_x86_64_arch(self):
        emitter = MachOEmitter(arch="x86_64")
        emitter.add_function("_start", b"\xc3")  # RET
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
            path = f.name
        try:
            emitter.write(path)
            data = open(path, "rb").read()
            # Check CPU type at offset 4: CPU_TYPE_X86_64 = 0x01000007
            cpu_type = struct.unpack("<I", data[4:8])[0]
            assert cpu_type == 0x01000007
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════
# 4. Live Range Splitting (next-use heuristic + cached reload)
# ═══════════════════════════════════════════════════════════

class TestLiveRangeSplitting:
    """Test the improved register allocator with next-use spill heuristic
    and cached-reload in rewrite()."""

    def test_use_positions_populated(self):
        """LiveInterval.use_positions should be filled during computation."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(2)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(0), src2=VReg(2)),
            QInstruction(Opcode.Q_RET, src1=VReg(3)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        intervals = alloc._compute_live_intervals(func)
        iv_map = {iv.vreg: iv for iv in intervals}
        # VReg(0) used at pos 0 (def), 2 (src), 3 (src)
        assert 0 in iv_map
        assert len(iv_map[0].use_positions) >= 2

    def test_next_use_after(self):
        iv = LiveInterval(vreg=0, start=0, end=10, use_positions=[0, 3, 7, 10])
        assert iv.next_use_after(0) == 3
        assert iv.next_use_after(3) == 7
        assert iv.next_use_after(10) == 11  # end + 1
        assert iv.next_use_after(8) == 10

    def test_cached_reload_reduces_spill_count(self):
        """When a spilled VReg is used twice consecutively, the second
        use should not re-emit a Q_LOAD (cached-reload optimization)."""
        # Create a function with high register pressure + repeated uses
        alloc = LinearScanAllocator("arm64")

        # Build a body that needs > 16 GP registers
        body = []
        for i in range(18):
            body.append(QInstruction(Opcode.Q_LOAD, dest=VReg(i), src1=Immediate(i)))
        # Use VReg(0) twice in a row after pressure is high
        body.append(QInstruction(Opcode.Q_ADD, dest=VReg(20), src1=VReg(0), src2=VReg(1)))
        body.append(QInstruction(Opcode.Q_ADD, dest=VReg(21), src1=VReg(0), src2=VReg(2)))
        body.append(QInstruction(Opcode.Q_RET, src1=VReg(21)))

        func = _make_func(body)
        result = alloc.allocate(func)
        func = alloc.rewrite(func, result)

        # Count spill-reload instructions for VReg(0)
        reloads_v0 = [
            i for i in func.body
            if i.opcode == Opcode.Q_LOAD and "spill-reload R0" in (i.comment or "")
        ]
        # With caching, max one reload for consecutive uses
        assert len(reloads_v0) <= 1, (
            f"Expected at most 1 reload for R0, got {len(reloads_v0)}"
        )

    def test_allocator_no_regression_simple(self):
        """Simple allocation should still work with the new heuristic."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        assert len(result.spilled) == 0
        assert result.gp_regs_used >= 1

    def test_x86_64_allocation(self):
        """Ensure x86_64 allocation still works."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(2)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("x86_64")
        result = alloc.allocate(func)
        assert len(result.spilled) == 0


# ═══════════════════════════════════════════════════════════
# 5. Epilogue Loop
# ═══════════════════════════════════════════════════════════

class TestEpilogueLoop:
    """Verify that loop unrolling now emits an epilogue loop for remainder."""

    def _build_simple_loop(self) -> QFunction:
        """A small loop: label → body → conditional back-edge."""
        return _make_func([
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="loop1"),
            QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(1), src1=VReg(0), src2=Immediate(10)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(1), src2=Label("loop1")),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ])

    def test_epilogue_label_emitted(self):
        """After unrolling, an epilogue label should appear."""
        func = self._build_simple_loop()
        opt = IROptimizer()
        opt._loop_unroll(func)
        labels = [i.patch_id for i in func.body if i.opcode == Opcode.Q_LABEL]
        epilogue_labels = [l for l in labels if l and "_epi_" in l]
        assert len(epilogue_labels) >= 1, "Epilogue label should be emitted"

    def test_epilogue_has_body_and_backedge(self):
        """The epilogue loop should contain one copy of the body + a back-edge."""
        func = self._build_simple_loop()
        opt = IROptimizer()
        opt._loop_unroll(func)

        body = func.body
        # Find epilogue label index
        epi_idx = None
        for idx, instr in enumerate(body):
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id and "_epi_" in instr.patch_id:
                epi_idx = idx
                break
        assert epi_idx is not None

        # After epilogue label, there should be body instructions and a back-edge
        after_epi = body[epi_idx + 1:]
        has_jump = any(
            i.opcode in (Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT, Opcode.Q_JUMP)
            for i in after_epi
        )
        assert has_jump, "Epilogue should have a back-edge jump"

    def test_unroll_factor_copies_in_main(self):
        """Main loop should have unroll_factor copies of the body."""
        func = self._build_simple_loop()
        opt = IROptimizer()
        opt._loop_unroll(func)
        # Count Q_ADD instructions before the epilogue
        adds_before_epi = 0
        for instr in func.body:
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id and "_epi_" in (instr.patch_id or ""):
                break
            if instr.opcode == Opcode.Q_ADD:
                adds_before_epi += 1
        # Default unroll factor is 4
        assert adds_before_epi == 4, f"Expected 4 unrolled ADDs, got {adds_before_epi}"


# ═══════════════════════════════════════════════════════════
# 6. Function Inlining
# ═══════════════════════════════════════════════════════════

class TestFunctionInlining:
    """Test inter-procedural function inlining."""

    def test_small_function_inlined(self):
        """A small callee should be inlined at the call site."""
        callee = _make_func([
            QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ], name="inc")

        caller_body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(5)),
            QInstruction(Opcode.Q_CALL, dest=VReg(1), src1=Label("inc"), src2=VReg(0)),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        caller = _make_func(caller_body, name="main")

        module = _make_module([callee, caller])
        opt = IROptimizer()
        func_table = {f.name: f for f in module.functions}
        opt._inline_functions(caller, func_table)

        # After inlining, Q_CALL should be replaced
        opcodes = _opcodes(caller)
        assert Opcode.Q_CALL not in opcodes, "Small function should be inlined"

    def test_large_function_not_inlined(self):
        """A large callee (>20 instructions) should NOT be inlined."""
        big_body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(i), src1=Immediate(i), src2=Immediate(1))
            for i in range(25)
        ] + [QInstruction(Opcode.Q_RET, src1=VReg(0))]
        callee = _make_func(big_body, name="big")

        caller_body = [
            QInstruction(Opcode.Q_CALL, dest=VReg(0), src1=Label("big")),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ]
        caller = _make_func(caller_body, name="main")

        module = _make_module([callee, caller])
        opt = IROptimizer()
        func_table = {f.name: f for f in module.functions}
        opt._inline_functions(caller, func_table)

        opcodes = _opcodes(caller)
        assert Opcode.Q_CALL in opcodes, "Large function should not be inlined"

    def test_recursive_not_inlined(self):
        """Recursive calls should not be inlined."""
        body = [
            QInstruction(Opcode.Q_CALL, dest=VReg(0), src1=Label("rec")),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ]
        func = _make_func(body, name="rec")
        module = _make_module([func])
        opt = IROptimizer()
        func_table = {f.name: f for f in module.functions}
        opt._inline_functions(func, func_table)
        opcodes = _opcodes(func)
        assert Opcode.Q_CALL in opcodes, "Recursive call should not be inlined"

    def test_inlined_vregs_remapped(self):
        """VRegs in inlined body should not clash with caller's VRegs."""
        callee = _make_func([
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(99)),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ], name="get99")

        caller_body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_CALL, dest=VReg(1), src1=Label("get99")),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        caller = _make_func(caller_body, name="main")

        opt = IROptimizer()
        func_table = {"get99": callee, "main": caller}
        opt._inline_functions(caller, func_table)

        # After inlining, VReg indices from callee should be shifted
        all_vregs = set()
        for instr in caller.body:
            for op in (instr.dest, instr.src1, instr.src2):
                if isinstance(op, VReg):
                    all_vregs.add(op.index)
        # Caller uses 0,1,2 — inlined code should use higher indices
        assert max(all_vregs) > 2, "Inlined VRegs should be remapped to higher indices"


# ═══════════════════════════════════════════════════════════
# 7. LICM (Loop-Invariant Code Motion)
# ═══════════════════════════════════════════════════════════

class TestLICM:
    """Test Loop-Invariant Code Motion."""

    def test_invariant_hoisted_before_loop(self):
        """An instruction whose operands are defined outside the loop
        should be hoisted to before the loop label."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="loop1"),
            # Invariant: MUL of VReg(0) × Immediate(2) — both defined outside loop
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=Immediate(2)),
            # Loop body: ADD counter
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(1), src2=VReg(2)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(3), src1=VReg(1), src2=Immediate(100)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(3), src2=Label("loop1")),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        func = _make_func(body)
        opt = IROptimizer()
        opt._licm(func)

        # Find the loop label position
        label_idx = next(
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id == "loop1"
        )
        # The MUL should now be BEFORE the loop label
        mul_indices = [
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_MUL
        ]
        assert len(mul_indices) == 1
        assert mul_indices[0] < label_idx, "Invariant MUL should be hoisted before loop"

    def test_non_invariant_stays_in_loop(self):
        """Instructions depending on loop variables should NOT be hoisted."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="loop2"),
            # NOT invariant: ADD uses VReg(0) which is modified in loop
            QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(1), src1=VReg(0), src2=Immediate(10)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(1), src2=Label("loop2")),
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ]
        func = _make_func(body)
        opt = IROptimizer()
        opt._licm(func)

        label_idx = next(
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id == "loop2"
        )
        add_indices = [
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_ADD
        ]
        for idx in add_indices:
            assert idx > label_idx, "Loop-variant ADD should stay inside loop"

    def test_licm_with_fp_opcodes(self):
        """LICM should also hoist FP invariant instructions."""
        body = [
            QInstruction(Opcode.Q_FLOAD, dest=VReg(0), src1=Immediate(3.14)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="floop"),
            # Invariant: FMUL of VReg(0) × constant
            QInstruction(Opcode.Q_FMUL, dest=VReg(2), src1=VReg(0), src2=Immediate(2.0)),
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(1), src2=Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(3), src1=VReg(1), src2=Immediate(10)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(3), src2=Label("floop")),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        func = _make_func(body)
        opt = IROptimizer()
        opt._licm(func)
        label_idx = next(
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id == "floop"
        )
        fmul_idx = next(
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_FMUL
        )
        assert fmul_idx < label_idx, "FP invariant FMUL should be hoisted"


# ═══════════════════════════════════════════════════════════
# 8. Optional Static Typing
# ═══════════════════════════════════════════════════════════

class TestStaticTyping:
    """Test the optional type checker."""

    def test_no_errors_on_untyped_program(self):
        prog = ProgramNode(statements=[
            VarDeclNode(name="x", value=NumberLiteral(value=42)),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []

    def test_int_assignment_ok(self):
        prog = ProgramNode(statements=[
            VarDeclNode(name="x", value=NumberLiteral(value=10), type_ann="int"),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []

    def test_type_mismatch_detected(self):
        prog = ProgramNode(statements=[
            VarDeclNode(name="x", value=StringLiteral(value="hello"), type_ann="int"),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert len(errors) == 1
        assert "mismatch" in errors[0].message.lower()

    def test_int_float_promotion(self):
        """int and float should be promotable (no error)."""
        prog = ProgramNode(statements=[
            VarDeclNode(name="x", value=NumberLiteral(value=3.14), type_ann="float"),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []

    def test_unknown_type_error(self):
        prog = ProgramNode(statements=[
            VarDeclNode(name="x", value=NumberLiteral(value=1), type_ann="foo_t"),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert len(errors) >= 1
        assert "foo_t" in errors[0].message

    def test_func_param_types(self):
        prog = ProgramNode(statements=[
            FuncDefNode(
                name="add",
                params=["a", "b"],
                param_types=["int", "int"],
                return_type="int",
                body=[
                    ReturnNode(expr=BinOpNode(
                        op="ADD",
                        left=IdentifierRef(name="a"),
                        right=IdentifierRef(name="b"),
                    )),
                ],
            ),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []

    def test_func_call_arg_mismatch(self):
        prog = ProgramNode(statements=[
            FuncDefNode(
                name="square",
                params=["n"],
                param_types=["int"],
                return_type="int",
                body=[
                    ReturnNode(expr=BinOpNode(
                        op="MUL",
                        left=IdentifierRef(name="n"),
                        right=IdentifierRef(name="n"),
                    )),
                ],
            ),
            VarDeclNode(
                name="result",
                value=CallNode(name="square", args=[StringLiteral(value="nope")]),
            ),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert len(errors) >= 1
        assert "expected int" in errors[0].message.lower() or "expected" in errors[0].message.lower()

    def test_comparison_yields_bool(self):
        prog = ProgramNode(statements=[
            VarDeclNode(
                name="flag",
                value=CompareNode(
                    op="GT",
                    left=NumberLiteral(value=5),
                    right=NumberLiteral(value=3),
                ),
                type_ann="bool",
            ),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []

    def test_string_concat_ok(self):
        prog = ProgramNode(statements=[
            VarDeclNode(
                name="msg",
                value=BinOpNode(
                    op="ADD",
                    left=StringLiteral(value="hello "),
                    right=StringLiteral(value="world"),
                ),
                type_ann="str",
            ),
        ])
        tc = TypeChecker()
        errors = tc.check(prog)
        assert errors == []


# ═══════════════════════════════════════════════════════════
# Integration: Full pipeline
# ═══════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """End-to-end tests: optimizer + allocator working together."""

    def test_full_pipeline_simple(self):
        """A simple module should survive optimize → allocate → rewrite."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        module = _make_module([_make_func(body, name="main")])
        opt = IROptimizer()
        opt.optimize(module)

        alloc = LinearScanAllocator("arm64")
        for func in module.functions:
            result = alloc.allocate(func)
            func = alloc.rewrite(func, result)
            assert len(func.body) >= 1

    def test_full_pipeline_with_loop(self):
        """A loop should survive optimize (with LICM, unroll, epilogue) + alloc."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(5)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="L"),
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(1), src2=VReg(0)),
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(1), src2=Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(2), src1=VReg(1), src2=Immediate(100)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(2), src2=Label("L")),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        module = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt.optimize(module)

        alloc = LinearScanAllocator("arm64")
        for func in module.functions:
            result = alloc.allocate(func)
            alloc.rewrite(func, result)
