"""
Tests for Phase 7: Core Performance Optimizations
====================================================
1. Bounds Check Elimination (BCE) via Range Analysis
2. Escape Analysis + Stack Promotion
3. Deterministic Free
4. BCE integration into M→L lowering
5. Deeper SIMD in M→L pipeline
"""

import pytest
from src.ir.instructions.q_ir import (
    Immediate, Label, Opcode, QFunction, QInstruction, QModule, VReg,
)
from src.ir.optimizer.bounds_check_elim import (
    BoundsCheckEliminator, Range, LoopInfo,
)
from src.ir.optimizer.escape_analysis import (
    EscapeAnalyzer, EscapeState,
)
from src.ir.optimizer.deterministic_free import DeterministicFree
from src.ir.optimizer.optimizer import IROptimizer


# ═════════════════════════════════════════════════════════════════════
#  Range Arithmetic Tests
# ═════════════════════════════════════════════════════════════════════

class TestRange:
    def test_bounded(self):
        r = Range(0, 10)
        assert r.is_bounded
        assert Range(None, 10).is_bounded is False
        assert Range(0, None).is_bounded is False

    def test_contains(self):
        outer = Range(0, 100)
        inner = Range(0, 50)
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_add_const(self):
        r = Range(0, 10)
        r2 = r.add_const(5)
        assert r2.lo == 5 and r2.hi == 15

    def test_sub_const(self):
        r = Range(5, 15)
        r2 = r.sub_const(3)
        assert r2.lo == 2 and r2.hi == 12

    def test_mul_const_positive(self):
        r = Range(2, 8)
        r2 = r.mul_const(3)
        assert r2.lo == 6 and r2.hi == 24

    def test_mul_const_negative(self):
        r = Range(2, 8)
        r2 = r.mul_const(-1)
        assert r2.lo == -8 and r2.hi == -2

    def test_intersect(self):
        a = Range(0, 10)
        b = Range(5, 15)
        c = a.intersect(b)
        assert c.lo == 5 and c.hi == 10

    def test_union(self):
        a = Range(0, 5)
        b = Range(3, 10)
        c = a.union(b)
        assert c.lo == 0 and c.hi == 10


# ═════════════════════════════════════════════════════════════════════
#  Bounds Check Elimination Tests
# ═════════════════════════════════════════════════════════════════════

def _make_loop_with_bounds_check(n: int = 100) -> QFunction:
    """Build a canonical loop:
        LOAD R0, #0           ; i = 0
        LOAD R5, #<n>         ; array length
        LABEL @loop
          BOUNDS_CHECK R0, R5 ; bounds check i < n
          LOAD R1, R0         ; body: use arr[i]
          ADD R0, R0, #1      ; i++
          CMP_LT R2, R0, R5  ; i < n
          JUMP_IF @loop, R2
    """
    func = QFunction(name="test_bce")
    func.body = [
        QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(0)),              # i = 0
        QInstruction(Opcode.Q_LOAD, VReg(5), Immediate(n)),              # len = n
        QInstruction(Opcode.Q_LABEL, patch_id="loop"),                   # @loop
        QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=VReg(5)), # bounds check
        QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),                   # body
        QInstruction(Opcode.Q_ADD, VReg(0), VReg(0), Immediate(1)),      # i++
        QInstruction(Opcode.Q_CMP_LT, VReg(2), VReg(0), VReg(5)),       # i < n
        QInstruction(Opcode.Q_JUMP_IF, src1=Label("loop"), src2=VReg(2)),# back-edge
    ]
    return func


class TestBoundsCheckElimination:
    def test_eliminates_in_canonical_loop(self):
        """BCE should eliminate bounds check when i ∈ [0, n) and check is i < n."""
        func = _make_loop_with_bounds_check(100)
        bce = BoundsCheckEliminator()
        bce.run(func)

        # The Q_BOUNDS_CHECK should be replaced with Q_NOP
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_BOUNDS_CHECK not in opcodes
        assert Opcode.Q_NOP in opcodes
        assert bce.eliminated == 1

    def test_preserves_check_without_loop(self):
        """Without a loop, bounds check should remain."""
        func = QFunction(name="no_loop")
        func.body = [
            QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(5)),
            QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=Immediate(10)),
            QInstruction(Opcode.Q_RET),
        ]
        bce = BoundsCheckEliminator()
        bce.run(func)
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_BOUNDS_CHECK in opcodes
        assert bce.eliminated == 0

    def test_immediate_bound(self):
        """BCE with immediate length constant."""
        func = QFunction(name="test_imm_bound")
        func.body = [
            QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(0)),
            QInstruction(Opcode.Q_LABEL, patch_id="L"),
            QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=Immediate(50)),
            QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
            QInstruction(Opcode.Q_ADD, VReg(0), VReg(0), Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, VReg(2), VReg(0), Immediate(50)),
            QInstruction(Opcode.Q_JUMP_IF, src1=Label("L"), src2=VReg(2)),
        ]
        bce = BoundsCheckEliminator()
        bce.run(func)
        assert bce.eliminated == 1

    def test_loop_detection(self):
        """Verify loop detection finds canonical counted loops."""
        func = _make_loop_with_bounds_check(42)
        bce = BoundsCheckEliminator()
        loops = bce._detect_loops(func)
        assert len(loops) == 1
        assert loops[0].iv_vreg == 0
        assert loops[0].step == 1

    def test_multiple_bounds_checks(self):
        """Two bounds checks in the same loop, both eliminated."""
        func = QFunction(name="dual_check")
        func.body = [
            QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(0)),
            QInstruction(Opcode.Q_LOAD, VReg(5), Immediate(100)),
            QInstruction(Opcode.Q_LABEL, patch_id="lp"),
            QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=VReg(5)),
            QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
            QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=VReg(5)),
            QInstruction(Opcode.Q_STORE, VReg(0), VReg(1)),
            QInstruction(Opcode.Q_ADD, VReg(0), VReg(0), Immediate(1)),
            QInstruction(Opcode.Q_CMP_LT, VReg(2), VReg(0), VReg(5)),
            QInstruction(Opcode.Q_JUMP_IF, src1=Label("lp"), src2=VReg(2)),
        ]
        bce = BoundsCheckEliminator()
        bce.run(func)
        assert bce.eliminated == 2


# ═════════════════════════════════════════════════════════════════════
#  Escape Analysis Tests
# ═════════════════════════════════════════════════════════════════════

def _make_non_escaping_alloc() -> QFunction:
    """Alloc used only locally — should be stack-promoted."""
    func = QFunction(name="local_alloc")
    func.body = [
        QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(64)),   # alloc 64 bytes
        QInstruction(Opcode.Q_STORE, VReg(0), Immediate(42)),   # store into it
        QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),          # read from it
        QInstruction(Opcode.Q_RET, src1=VReg(1)),               # return value, not pointer
    ]
    return func


def _make_escaping_alloc_via_return() -> QFunction:
    """Alloc returned from function — escapes globally."""
    func = QFunction(name="escape_ret")
    func.body = [
        QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(64)),
        QInstruction(Opcode.Q_STORE, VReg(0), Immediate(42)),
        QInstruction(Opcode.Q_RET, src1=VReg(0)),  # returning the pointer itself
    ]
    return func


def _make_escaping_alloc_via_call() -> QFunction:
    """Alloc passed to function call — arg escape."""
    func = QFunction(name="escape_call")
    func.body = [
        QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(128)),
        QInstruction(Opcode.Q_CALL, src1=Label("external_fn"), src2=VReg(0)),
        QInstruction(Opcode.Q_RET),
    ]
    return func


class TestEscapeAnalysis:
    def test_promotes_non_escaping(self):
        """Non-escaping alloc should be promoted to Q_STACK_ALLOC."""
        func = _make_non_escaping_alloc()
        ea = EscapeAnalyzer()
        ea.run(func)
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_STACK_ALLOC in opcodes
        assert Opcode.Q_ALLOC not in opcodes
        assert ea.promoted == 1

    def test_no_promote_when_returned(self):
        """Alloc that escapes via return should NOT be promoted."""
        func = _make_escaping_alloc_via_return()
        ea = EscapeAnalyzer()
        ea.run(func)
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_ALLOC in opcodes
        assert Opcode.Q_STACK_ALLOC not in opcodes
        assert ea.promoted == 0

    def test_no_promote_when_passed_to_call(self):
        """Alloc passed to external call should NOT be promoted."""
        func = _make_escaping_alloc_via_call()
        ea = EscapeAnalyzer()
        ea.run(func)
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_ALLOC in opcodes
        assert ea.promoted == 0

    def test_large_alloc_not_promoted(self):
        """Alloc larger than MAX_STACK_ALLOC (4096) should stay on heap."""
        func = QFunction(name="big_alloc")
        func.body = [
            QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(8192)),
            QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        ea = EscapeAnalyzer()
        ea.run(func)
        assert ea.promoted == 0

    def test_pointer_alias_tracking(self):
        """Pointer copied via MOVE and then returned — should escape."""
        func = QFunction(name="alias_escape")
        func.body = [
            QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(64)),
            QInstruction(Opcode.Q_MOVE, VReg(1), VReg(0)),     # alias
            QInstruction(Opcode.Q_STORE, VReg(1), Immediate(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),          # return alias → escapes
        ]
        ea = EscapeAnalyzer()
        ea.run(func)
        assert ea.promoted == 0

    def test_multiple_allocs_mixed(self):
        """One escaping, one non-escaping — only non-escaping is promoted."""
        func = QFunction(name="mixed")
        func.body = [
            QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(32)),   # local
            QInstruction(Opcode.Q_ALLOC, VReg(1), Immediate(64)),   # escapes
            QInstruction(Opcode.Q_LOAD, VReg(2), VReg(0)),          # use local
            QInstruction(Opcode.Q_RET, src1=VReg(1)),               # return heap ptr
        ]
        ea = EscapeAnalyzer()
        ea.run(func)
        assert ea.promoted == 1  # only VReg(0)
        assert func.body[0].opcode == Opcode.Q_STACK_ALLOC
        assert func.body[1].opcode == Opcode.Q_ALLOC

    def test_module_analysis(self):
        """analyze_module returns per-function stats."""
        module = QModule(name="test")
        module.add_function(_make_non_escaping_alloc())
        ea = EscapeAnalyzer()
        stats = ea.analyze_module(module)
        assert "local_alloc" in stats
        assert stats["local_alloc"]["promoted"] == 1


# ═════════════════════════════════════════════════════════════════════
#  Deterministic Free Tests
# ═════════════════════════════════════════════════════════════════════

def _make_alloc_no_free() -> QFunction:
    """Heap alloc without explicit free → deterministic free should insert one."""
    func = QFunction(name="needs_free")
    func.body = [
        QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(256)),
        QInstruction(Opcode.Q_STORE, VReg(0), Immediate(99)),
        QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
        QInstruction(Opcode.Q_RET, src1=VReg(1)),
    ]
    return func


def _make_alloc_explicit_free() -> QFunction:
    """Already has Q_FREE — no duplicate insertion."""
    func = QFunction(name="has_free")
    func.body = [
        QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(128)),
        QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
        QInstruction(Opcode.Q_FREE, src1=VReg(0)),
        QInstruction(Opcode.Q_RET, src1=VReg(1)),
    ]
    return func


class TestDeterministicFree:
    def test_inserts_free_before_ret(self):
        """Should insert Q_FREE for heap alloc without explicit free."""
        func = _make_alloc_no_free()
        df = DeterministicFree()
        df.run(func)

        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_FREE in opcodes
        assert df.inserted >= 1

        # Q_FREE should appear before Q_RET
        free_idx = opcodes.index(Opcode.Q_FREE)
        ret_idx = opcodes.index(Opcode.Q_RET)
        assert free_idx < ret_idx

    def test_no_duplicate_free(self):
        """Already-freed allocs should not get another Q_FREE."""
        func = _make_alloc_explicit_free()
        df = DeterministicFree()
        df.run(func)

        free_count = sum(1 for i in func.body if i.opcode == Opcode.Q_FREE)
        assert free_count == 1  # only the original

    def test_stack_alloc_no_free(self):
        """Q_STACK_ALLOC should NOT get a Q_FREE (stack is auto-deallocated)."""
        func = QFunction(name="stack")
        func.body = [
            QInstruction(Opcode.Q_STACK_ALLOC, VReg(0), Immediate(64)),
            QInstruction(Opcode.Q_LOAD, VReg(1), VReg(0)),
            QInstruction(Opcode.Q_RET, src1=VReg(1)),
        ]
        df = DeterministicFree()
        df.run(func)
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_FREE not in opcodes

    def test_multiple_allocs(self):
        """Multiple allocs: each gets its own Q_FREE (LIFO order)."""
        func = QFunction(name="multi")
        func.body = [
            QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(32)),
            QInstruction(Opcode.Q_ALLOC, VReg(1), Immediate(64)),
            QInstruction(Opcode.Q_LOAD, VReg(2), VReg(0)),
            QInstruction(Opcode.Q_LOAD, VReg(3), VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        df = DeterministicFree()
        df.run(func)

        frees = [i for i in func.body if i.opcode == Opcode.Q_FREE]
        assert len(frees) >= 2

    def test_module_run(self):
        """run_module returns total inserted count."""
        module = QModule(name="test")
        module.add_function(_make_alloc_no_free())
        df = DeterministicFree()
        total = df.run_module(module)
        assert total >= 1


# ═════════════════════════════════════════════════════════════════════
#  Integrated Optimizer Pipeline Tests
# ═════════════════════════════════════════════════════════════════════

class TestIntegratedOptimizer:
    def test_full_pipeline_with_bce(self):
        """Full optimizer pipeline processes bounds checks."""
        module = QModule(name="full")
        func = _make_loop_with_bounds_check(100)
        module.add_function(func)

        opt = IROptimizer(arch="arm64")
        opt.optimize(module)

        assert opt.bce_eliminated >= 1
        # Q_BOUNDS_CHECK should be replaced with NOP
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_BOUNDS_CHECK not in opcodes

    def test_full_pipeline_escape_and_free(self):
        """Full pipeline does escape analysis + deterministic free."""
        module = QModule(name="full2")
        func = _make_non_escaping_alloc()
        module.add_function(func)

        opt = IROptimizer(arch="arm64")
        opt.optimize(module)

        assert opt.stack_promoted >= 1
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_STACK_ALLOC in opcodes
        assert Opcode.Q_ALLOC not in opcodes

    def test_pipeline_preserves_correctness(self):
        """Optimizer doesn't break simple programs."""
        module = QModule(name="simple")
        func = QFunction(name="add")
        func.body = [
            QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(1)),
            QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(2)),
            QInstruction(Opcode.Q_ADD, VReg(2), VReg(0), VReg(1)),
            QInstruction(Opcode.Q_RET, src1=VReg(2)),
        ]
        module.add_function(func)

        opt = IROptimizer(arch="arm64")
        opt.optimize(module)

        # Should still have a return
        opcodes = [i.opcode for i in func.body]
        assert Opcode.Q_RET in opcodes

    def test_stats_tracking(self):
        """Optimizer reports BCE, promotion, and free stats."""
        module = QModule(name="stats")
        module.add_function(_make_loop_with_bounds_check(50))
        module.add_function(_make_non_escaping_alloc())

        opt = IROptimizer(arch="arm64")
        opt.optimize(module)

        assert isinstance(opt.bce_eliminated, int)
        assert isinstance(opt.stack_promoted, int)
        assert isinstance(opt.frees_inserted, int)


# ═════════════════════════════════════════════════════════════════════
#  QIR Opcode Tests (new opcodes)
# ═════════════════════════════════════════════════════════════════════

class TestNewOpcodes:
    def test_bounds_check_opcode_exists(self):
        assert Opcode.Q_BOUNDS_CHECK is not None

    def test_alloc_opcode_exists(self):
        assert Opcode.Q_ALLOC is not None

    def test_free_opcode_exists(self):
        assert Opcode.Q_FREE is not None

    def test_stack_alloc_opcode_exists(self):
        assert Opcode.Q_STACK_ALLOC is not None

    def test_qir_m_bounds_check(self):
        from src.qir.opcodes import QIRMOp
        assert QIRMOp.BOUNDS_CHECK is not None

    def test_qir_l_bounds_check(self):
        from src.qir.opcodes import QIRLOp
        assert QIRLOp.BOUNDS_CHECK is not None

    def test_qir_l_stack_alloc(self):
        from src.qir.opcodes import QIRLOp
        assert QIRLOp.STACK_ALLOC is not None

    def test_qir_l_det_free(self):
        from src.qir.opcodes import QIRLOp
        assert QIRLOp.DET_FREE is not None


# ═════════════════════════════════════════════════════════════════════
#  Edge Cases
# ═════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_bce_empty_function(self):
        func = QFunction(name="empty")
        func.body = []
        bce = BoundsCheckEliminator()
        bce.run(func)
        assert bce.eliminated == 0

    def test_escape_analysis_empty_function(self):
        func = QFunction(name="empty")
        func.body = []
        ea = EscapeAnalyzer()
        ea.run(func)
        assert ea.promoted == 0

    def test_det_free_empty_function(self):
        func = QFunction(name="empty")
        func.body = []
        df = DeterministicFree()
        df.run(func)
        assert df.inserted == 0

    def test_bce_non_counted_loop(self):
        """Infinite loop (no comparison) should not crash BCE."""
        func = QFunction(name="inf_loop")
        func.body = [
            QInstruction(Opcode.Q_LABEL, patch_id="inf"),
            QInstruction(Opcode.Q_BOUNDS_CHECK, src1=VReg(0), src2=Immediate(10)),
            QInstruction(Opcode.Q_JUMP, src1=Label("inf")),
        ]
        bce = BoundsCheckEliminator()
        bce.run(func)
        # Should not crash; check may or may not be eliminated

    def test_escaping_via_store_to_memory(self):
        """Store pointer to external memory → global escape."""
        func = QFunction(name="store_escape")
        func.body = [
            QInstruction(Opcode.Q_ALLOC, VReg(0), Immediate(64)),
            QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0)),  # some address
            QInstruction(Opcode.Q_STORE, VReg(1), VReg(0)),      # store ptr to memory
            QInstruction(Opcode.Q_RET),
        ]
        ea = EscapeAnalyzer()
        ea.run(func)
        assert ea.promoted == 0  # escaped via store
