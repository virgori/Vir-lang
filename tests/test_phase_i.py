"""
test_phase_i.py – Tests for Phase I: Advanced Optimizations
=============================================================
Tests for:
  - Common Subexpression Elimination (CSE)
  - Loop Unrolling
  - Linear Scan Register Allocation
"""

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
from src.backend.codegen.codegen import CodeGenerator, TargetArch


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_func(body: list[QInstruction], name: str = "test") -> QFunction:
    return QFunction(name=name, params=[], body=body)


def _make_module(funcs: list[QFunction]) -> QModule:
    return QModule(functions=funcs)


def _opcodes(func: QFunction) -> list[Opcode]:
    return [i.opcode for i in func.body]


# ═══════════════════════════════════════════════════════════
# 1. Common Subexpression Elimination
# ═══════════════════════════════════════════════════════════

class TestCSE:
    """Test Common Subexpression Elimination pass (isolated)."""

    def _run_cse_only(self, body: list[QInstruction]) -> QFunction:
        """Run only the CSE pass, bypassing other optimizations."""
        func = _make_func(body)
        opt = IROptimizer()
        opt._cse(func)
        return func

    def test_duplicate_add_eliminated(self):
        """Two identical ADDs should produce a MOVE for the second."""
        body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        moves = [i for i in func.body if i.opcode == Opcode.Q_MOVE and "CSE" in i.comment]
        assert len(moves) >= 1, "CSE should replace duplicate ADD with MOVE"

    def test_different_operands_not_eliminated(self):
        """ADDs with different operands should not be CSE'd."""
        body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_ADD, dest=VReg(4), src1=VReg(0), src2=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(4)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        adds = [i for i in func.body if i.opcode == Opcode.Q_ADD]
        assert len(adds) == 2

    def test_cse_invalidated_by_redefinition(self):
        """CSE cache must invalidate when source vreg is redefined."""
        body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            # Redefine VReg(0) — invalidates the cached expression
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(99)),
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        adds = [i for i in func.body if i.opcode == Opcode.Q_ADD]
        assert len(adds) == 2, "CSE must not eliminate across redefinitions"

    def test_cse_invalidated_by_control_flow(self):
        """CSE cache clears at labels/jumps."""
        body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_LABEL, patch_id="lbl1"),
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        adds = [i for i in func.body if i.opcode == Opcode.Q_ADD]
        assert len(adds) == 2, "CSE must not eliminate across control flow"

    def test_commutative_cse(self):
        """ADD(a,b) and ADD(b,a) are the same for commutative ops."""
        body = [
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_ADD, dest=VReg(3), src1=VReg(1), src2=VReg(0)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        moves = [i for i in func.body if i.opcode == Opcode.Q_MOVE and "CSE" in i.comment]
        assert len(moves) >= 1, "Commutative CSE should detect ADD(a,b) == ADD(b,a)"

    def test_sub_not_commutative(self):
        """SUB(a,b) and SUB(b,a) differ — CSE should not merge them."""
        body = [
            QInstruction(Opcode.Q_SUB, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_SUB, dest=VReg(3), src1=VReg(1), src2=VReg(0)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        subs = [i for i in func.body if i.opcode == Opcode.Q_SUB]
        assert len(subs) == 2, "SUB is not commutative — both should remain"

    def test_duplicate_mul_eliminated(self):
        """MUL is commutative — same operands should be CSE'd."""
        body = [
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_MUL, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(3)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = self._run_cse_only(body)

        moves = [i for i in func.body if i.opcode == Opcode.Q_MOVE and "CSE" in i.comment]
        assert len(moves) >= 1


# ═══════════════════════════════════════════════════════════
# 2. Loop Unrolling
# ═══════════════════════════════════════════════════════════

class TestLoopUnrolling:
    """Test loop unrolling pass."""

    def test_simple_loop_unrolled(self):
        """A simple counted loop should be unrolled."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="loop_start"),
            QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, dest=VReg(1), src1=VReg(0), src2=Immediate(100)),
            QInstruction(Opcode.Q_JUMP_IF, src1=VReg(1), src2=Label("loop_start")),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        original_cmps = sum(1 for i in func.body if i.opcode == Opcode.Q_CMP_LT)

        # Run loop_unroll in isolation (full pipeline includes LICM which
        # may hoist invariants before the unroller sees the loop body).
        opt = IROptimizer()
        opt._loop_unroll(func)

        # After unrolling by 4, should have 4 CMP_LT in the unrolled body
        # plus 1 in the epilogue = 5 total
        result_cmps = sum(1 for i in func.body if i.opcode == Opcode.Q_CMP_LT)
        assert result_cmps >= original_cmps * 2, \
            f"Expected unrolled CMPs >= {original_cmps * 2}, got {result_cmps}"

    def test_no_loop_no_change(self):
        """Code without loops should be unchanged by unrolling."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(1)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        original_len = len(func.body)

        mod = _make_module([func])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        result_func = opt_mod.functions[0]

        # Length should not increase significantly (constant folding may change it)
        assert len(result_func.body) <= original_len + 2

    def test_large_loop_not_unrolled(self):
        """Loops with >32 instructions should NOT be unrolled."""
        # Create a loop body with 40 ADDs
        body = [QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(0))]
        body.append(QInstruction(Opcode.Q_LABEL, patch_id="big_loop"))
        for i in range(40):
            body.append(QInstruction(
                Opcode.Q_ADD, dest=VReg(i + 1),
                src1=VReg(i), src2=Immediate(1),
            ))
        body.append(QInstruction(
            Opcode.Q_CMP_LT, dest=VReg(50),
            src1=VReg(40), src2=Immediate(10),
        ))
        body.append(QInstruction(
            Opcode.Q_JUMP_IF, src1=VReg(50), src2=Label("big_loop"),
        ))
        body.append(QInstruction(Opcode.Q_HALT))

        func = _make_func(body)
        original_len = len(func.body)

        mod = _make_module([func])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        result_func = opt_mod.functions[0]

        # Large loops should not be unrolled (body count stays similar)
        # Allow some change from other passes (const fold, CSE, DCE)
        assert len(result_func.body) < original_len * 3

    def test_unroll_preserves_back_edge(self):
        """The backward jump should still exist after unrolling."""
        body = [
            QInstruction(Opcode.Q_LABEL, patch_id="lp"),
            QInstruction(Opcode.Q_ADD, dest=VReg(0), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_JUMP, src1=Label("lp")),
            QInstruction(Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        func = opt_mod.functions[0]

        jumps = [i for i in func.body if i.opcode == Opcode.Q_JUMP]
        assert len(jumps) >= 1, "Back-edge jump must be preserved"


# ═══════════════════════════════════════════════════════════
# 3. Linear Scan Register Allocation
# ═══════════════════════════════════════════════════════════

class TestLinearScanRegAlloc:
    """Test the linear scan register allocator."""

    def test_simple_allocation(self):
        """Simple program should allocate without spills."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)

        assert result.num_spill_slots == 0, "Simple program should not spill"
        assert 0 in result.assignment, "VReg(0) should be assigned"
        assert 1 in result.assignment, "VReg(1) should be assigned"
        assert 2 in result.assignment, "VReg(2) should be assigned"

    def test_all_vregs_get_unique_or_reused_phys(self):
        """Non-overlapping vregs may share physical registers."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(0)),
            # VReg(0) is dead here, VReg(1) can reuse same phys reg
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(1)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)

        assert result.num_spill_slots == 0

    def test_spill_when_exceeding_registers(self):
        """Using more VRegs than physical registers should cause spills."""
        # Create a function that needs all 16 ARM64 GP regs + 1 more
        body = []
        for i in range(18):
            body.append(QInstruction(Opcode.Q_LOAD, dest=VReg(i), src1=Immediate(i)))
        # Use all of them so they're all live simultaneously
        for i in range(18):
            body.append(QInstruction(Opcode.Q_PRINT, dest=VReg(i)))
        body.append(QInstruction(Opcode.Q_HALT))

        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)

        assert result.num_spill_slots >= 2, \
            f"18 simultaneously live VRegs should spill ≥2 (ARM64 has 16 GP), got {result.num_spill_slots}"

    def test_x86_allocation(self):
        """x86_64 allocation should work with 14 GP registers."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(2)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("x86_64")
        result = alloc.allocate(func)

        assert result.num_spill_slots == 0
        assert len(result.assignment) == 3

    def test_live_intervals_computed(self):
        """Live intervals should span from definition to last use."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),  # pos 0
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),  # pos 1
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),  # pos 2
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),  # pos 3
            QInstruction(Opcode.Q_HALT),  # pos 4
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        intervals = alloc._compute_live_intervals(func)

        iv_map = {iv.vreg: iv for iv in intervals}
        assert iv_map[0].start == 0
        assert iv_map[0].end == 2   # last used at pos 2 (src of ADD)
        assert iv_map[1].start == 1
        assert iv_map[1].end == 2   # last used at pos 2

    def test_vector_regs_allocated_separately(self):
        """SIMD instructions should use vector register pool."""
        body = [
            QInstruction(Opcode.Q_VLOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(Opcode.Q_VADD, dest=VReg(1), src1=VReg(0), src2=VReg(0)),
            QInstruction(Opcode.Q_VSTORE, dest=VReg(1), src1=Immediate(0)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        intervals = alloc._compute_live_intervals(func)

        # All intervals should be marked as vector
        for iv in intervals:
            if iv.vreg in (0, 1):
                assert iv.is_vector, f"VReg({iv.vreg}) in SIMD context should be vector"

    def test_rewrite_inserts_spill_code(self):
        """Rewrite should insert LOAD/STORE for spilled VRegs."""
        body = []
        for i in range(18):
            body.append(QInstruction(Opcode.Q_LOAD, dest=VReg(i), src1=Immediate(i)))
        for i in range(18):
            body.append(QInstruction(Opcode.Q_PRINT, dest=VReg(i)))
        body.append(QInstruction(Opcode.Q_HALT))

        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        alloc.rewrite(func, result)

        # Rewrite should have added spill-reload instructions
        spill_comments = [
            i for i in func.body
            if "spill" in i.comment
        ]
        assert len(spill_comments) > 0, "Spilled VRegs should have spill/reload code"

    def test_regalloc_result_api(self):
        """Test RegAllocResult helper methods."""
        result = RegAllocResult()
        result.assignment[0] = 5
        result.spilled[1] = 0

        assert result.phys_reg(0) == 5
        assert result.phys_reg(1) is None
        assert not result.is_spilled(0)
        assert result.is_spilled(1)


# ═══════════════════════════════════════════════════════════
# 4. Integration: Codegen with RegAlloc
# ═══════════════════════════════════════════════════════════

class TestCodegenRegAllocIntegration:
    """Test that codegen correctly invokes register allocation."""

    def test_codegen_produces_regalloc_results(self):
        """CodeGenerator.generate() should populate reg_alloc_results."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_ADD, dest=VReg(1), src1=VReg(0), src2=Immediate(1)),
            QInstruction(Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body, name="myfn")])
        gen = CodeGenerator(arch=TargetArch.ARM64)
        gen.generate(mod)

        assert "myfn" in gen.reg_alloc_results
        result = gen.reg_alloc_results["myfn"]
        assert isinstance(result, RegAllocResult)

    def test_codegen_still_produces_variants(self):
        """Code generation should still work end-to-end with regalloc."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body)])
        gen = CodeGenerator(arch=TargetArch.ARM64)
        variants = gen.generate(mod)

        assert len(variants) >= 1
        assert len(variants[0].safe_code.bytes_) > 0
        assert len(variants[0].fast_code.bytes_) > 0

    def test_optimizer_then_codegen_pipeline(self):
        """Full pipeline: optimize → codegen should not crash."""
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(5)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(7)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_MUL, dest=VReg(3), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_ADD, dest=VReg(4), src1=VReg(2), src2=VReg(3)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(4)),
            QInstruction(Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        gen = CodeGenerator(arch=TargetArch.ARM64)
        variants = gen.generate(opt_mod)

        assert len(variants) >= 1


# ═══════════════════════════════════════════════════════════
# 5. Live Interval Edge Cases
# ═══════════════════════════════════════════════════════════

class TestLiveIntervals:
    """Test live interval computation edge cases."""

    def test_empty_function(self):
        func = _make_func([QInstruction(Opcode.Q_HALT)])
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        assert result.num_spill_slots == 0

    def test_single_vreg(self):
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        alloc = LinearScanAllocator("arm64")
        result = alloc.allocate(func)
        assert 0 in result.assignment
        assert result.num_spill_slots == 0

    def test_interval_overlap_detection(self):
        iv1 = LiveInterval(vreg=0, start=0, end=5)
        iv2 = LiveInterval(vreg=1, start=3, end=8)
        iv3 = LiveInterval(vreg=2, start=6, end=10)

        assert iv1.overlaps(iv2)
        assert not iv1.overlaps(iv3)
        assert iv2.overlaps(iv3)
