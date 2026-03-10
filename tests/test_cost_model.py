"""
test_cost_model.py – Tests for the Vir Cost Model
===================================================
Tests cost model loading, query API, optimizer integration,
and codegen integration.
"""

import pytest

from src.ir.cost_model.cost_model import (
    CostModel,
    InstrCostEntry,
    BranchCostInfo,
    MemoryCostInfo,
    SpillCostInfo,
)
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
from src.backend.codegen.codegen import CodeGenerator, TargetArch


# ═══════════════════════════════════════════════════════════
# CostModel Loading & Query Tests
# ═══════════════════════════════════════════════════════════

class TestCostModelLoading:
    """Test that CostModel loads correctly from config or defaults."""

    def test_load_arm64(self):
        cm = CostModel("arm64")
        assert cm.arch == "arm64"
        assert cm.issue_width >= 4

    def test_load_x86_64(self):
        cm = CostModel("x86_64")
        assert cm.arch == "x86_64"

    def test_fallback_defaults(self):
        cm = CostModel("arm64", config_path="/nonexistent/path.json")
        # Should fall back to hardcoded defaults without crashing
        assert cm.latency(Opcode.Q_ADD) == 1
        assert cm.latency(Opcode.Q_MUL) == 3

    def test_all_opcodes_have_costs(self):
        cm = CostModel("arm64")
        for opcode in Opcode:
            entry = cm.get(opcode)
            assert isinstance(entry, InstrCostEntry)
            assert entry.latency >= 0
            assert entry.throughput >= 0


class TestCostModelQueries:
    """Test the per-instruction cost query API."""

    @pytest.fixture
    def cm(self):
        return CostModel("arm64")

    def test_latency_add(self, cm):
        assert cm.latency(Opcode.Q_ADD) == 1

    def test_latency_mul(self, cm):
        assert cm.latency(Opcode.Q_MUL) >= 3

    def test_latency_div_expensive(self, cm):
        assert cm.latency(Opcode.Q_DIV) >= 8

    def test_is_expensive_div(self, cm):
        assert cm.is_expensive(Opcode.Q_DIV)

    def test_not_expensive_add(self, cm):
        assert not cm.is_expensive(Opcode.Q_ADD)

    def test_should_strength_reduce_mul(self, cm):
        assert cm.should_strength_reduce(Opcode.Q_MUL)

    def test_should_strength_reduce_div(self, cm):
        assert cm.should_strength_reduce(Opcode.Q_DIV)

    def test_throughput_positive(self, cm):
        assert cm.throughput(Opcode.Q_ADD) > 0

    def test_reciprocal_throughput(self, cm):
        rt = cm.reciprocal_throughput(Opcode.Q_ADD)
        assert rt > 0
        assert rt <= 1.0  # ADD should be <= 1 cycle reciprocal throughput

    def test_branch_cost(self, cm):
        assert cm.branch.miss_penalty > 0
        assert cm.branch.predict_hit < cm.branch.predict_miss

    def test_memory_cost(self, cm):
        assert cm.memory.l1_latency < cm.memory.l2_latency
        assert cm.memory.l2_latency < cm.memory.mem_latency

    def test_spill_cost(self, cm):
        assert cm.spill.total == cm.spill.spill_store + cm.spill.spill_load
        assert cm.spill_cost_estimate(3) == 3 * cm.spill.total

    def test_div_worth_strength_reduce_constant(self, cm):
        assert cm.div_is_worth_strength_reduce(8)

    def test_div_not_worth_strength_reduce_none(self, cm):
        assert not cm.div_is_worth_strength_reduce(None)


# ═══════════════════════════════════════════════════════════
# Block & Function Cost Estimation Tests
# ═══════════════════════════════════════════════════════════

class TestBlockCost:
    """Test basic block and function cost estimation."""

    @pytest.fixture
    def cm(self):
        return CostModel("arm64")

    def _make_instrs(self, opcodes):
        return [
            QInstruction(op, dest=VReg(0), src1=VReg(1), src2=VReg(2))
            for op in opcodes
        ]

    def test_single_add_cost(self, cm):
        instrs = self._make_instrs([Opcode.Q_ADD])
        cost = cm.block_cost(instrs)
        assert cost >= 1.0

    def test_mul_more_expensive_than_add(self, cm):
        add_cost = cm.block_cost(self._make_instrs([Opcode.Q_ADD]))
        mul_cost = cm.block_cost(self._make_instrs([Opcode.Q_MUL]))
        assert mul_cost > add_cost

    def test_div_most_expensive(self, cm):
        add_cost = cm.block_cost(self._make_instrs([Opcode.Q_ADD]))
        div_cost = cm.block_cost(self._make_instrs([Opcode.Q_DIV]))
        assert div_cost > add_cost * 3

    def test_block_cost_additive(self, cm):
        one = cm.block_cost(self._make_instrs([Opcode.Q_ADD]))
        two = cm.block_cost(self._make_instrs([Opcode.Q_ADD, Opcode.Q_ADD]))
        assert abs(two - 2 * one) < 0.01

    def test_throughput_cost(self, cm):
        instrs = self._make_instrs([Opcode.Q_ADD, Opcode.Q_MUL, Opcode.Q_DIV])
        t_cost = cm.throughput_cost(instrs)
        assert t_cost > 0

    def test_empty_block(self, cm):
        assert cm.block_cost([]) == 0.0

    def test_function_cost(self, cm):
        func = QFunction(
            name="test",
            params=[],
            body=self._make_instrs([Opcode.Q_ADD, Opcode.Q_MUL, Opcode.Q_RET]),
        )
        cost = cm.function_cost(func)
        assert cost > 0

    def test_branch_adds_misprediction_cost(self, cm):
        # Conditional branch should include small misprediction overhead
        plain_add = cm.instr_cost(QInstruction(
            Opcode.Q_ADD, dest=VReg(0), src1=VReg(1), src2=VReg(2),
        ))
        branch = cm.instr_cost(QInstruction(
            Opcode.Q_JUMP_IF, dest=None, src1=VReg(0),
            src2=Label("target"),
        ))
        # Branch should have some misprediction cost baked in
        assert branch > plain_add


# ═══════════════════════════════════════════════════════════
# Optimizer Integration Tests
# ═══════════════════════════════════════════════════════════

class TestOptimizerCostIntegration:
    """Test that the optimizer uses cost model for strength reduction."""

    def test_optimizer_accepts_cost_model(self):
        cm = CostModel("arm64")
        opt = IROptimizer(cost_model=cm)
        assert opt.cost_model is cm

    def test_optimizer_default_cost_model(self):
        opt = IROptimizer()
        assert opt.cost_model is not None

    def test_strength_reduce_mul_by_zero(self):
        opt = IROptimizer()
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(5)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(0)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        opt.optimize(module)

        # MUL by 0 should become LOAD 0 (or MOVE from a register holding 0
        # if CSE deduplicates the constant load)
        mul_instrs = [i for i in func.body if i.opcode == Opcode.Q_MUL]
        assert len(mul_instrs) == 0
        # v2 must receive 0: either via Q_LOAD Imm(0) or Q_MOVE from v1 (which holds 0)
        v2_def = [i for i in func.body
                  if isinstance(i.dest, VReg) and i.dest.index == 2]
        assert len(v2_def) == 1
        defn = v2_def[0]
        if defn.opcode == Opcode.Q_LOAD:
            assert isinstance(defn.src1, Immediate) and defn.src1.value == 0
        else:
            assert defn.opcode == Opcode.Q_MOVE  # CSE coalesced with earlier LOAD 0

    def test_strength_reduce_mul_by_one(self):
        opt = IROptimizer()
        body = [
            # src1 comes from INPUT so constant fold can't resolve
            QInstruction(Opcode.Q_INPUT, dest=VReg(0)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(1)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        opt.optimize(module)

        # MUL by 1 should become MOVE
        move_instrs = [i for i in func.body if i.opcode == Opcode.Q_MOVE]
        assert len(move_instrs) >= 1

    def test_strength_reduce_mul_by_power_of_2(self):
        opt = IROptimizer()
        body = [
            # src1 comes from INPUT so constant fold can't resolve
            QInstruction(Opcode.Q_INPUT, dest=VReg(0)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(8)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        opt.optimize(module)

        # MUL by 8 should be annotated as LSL
        annotated = [i for i in func.body if "LSL" in (i.comment or "")]
        assert len(annotated) == 1

    def test_strength_reduce_div_by_one(self):
        opt = IROptimizer()
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(42)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(1)),
            QInstruction(Opcode.Q_DIV, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        opt.optimize(module)

        # DIV by 1 should become MOVE
        div_instrs = [i for i in func.body if i.opcode == Opcode.Q_DIV]
        assert len(div_instrs) == 0

    def test_strength_reduce_mod_by_power_of_2(self):
        opt = IROptimizer()
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(100)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(16)),
            QInstruction(Opcode.Q_MOD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        opt.optimize(module)

        # MOD by 16 should be annotated as AND with 15
        annotated = [i for i in func.body if "AND" in (i.comment or "")]
        assert len(annotated) == 1


# ═══════════════════════════════════════════════════════════
# Codegen Integration Tests
# ═══════════════════════════════════════════════════════════

class TestCodegenCostIntegration:
    """Test that CodeGenerator computes variant costs."""

    def test_codegen_has_cost_model(self):
        cg = CodeGenerator(TargetArch.X86_64)
        assert cg.cost_model is not None

    def test_codegen_accepts_cost_model(self):
        cm = CostModel("x86_64")
        cg = CodeGenerator(TargetArch.X86_64, cost_model=cm)
        assert cg.cost_model is cm

    def test_variant_has_cost(self):
        cg = CodeGenerator(TargetArch.X86_64)
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PATCH_POINT, patch_id="P1"),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        variants = cg.generate(module)

        assert len(variants) >= 1
        v = variants[0]
        assert v.safe_cost > 0
        assert v.fast_cost > 0
        assert v.speedup >= 1.0  # safe should be >= fast cost

    def test_safe_slower_than_fast(self):
        cg = CodeGenerator(TargetArch.X86_64)
        body = [
            QInstruction(Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(10)),
            QInstruction(Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(20)),
            QInstruction(Opcode.Q_MUL, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(Opcode.Q_PATCH_POINT, patch_id="P1"),
            QInstruction(Opcode.Q_RET, dest=None, src1=VReg(2)),
        ]
        func = QFunction(name="test", params=[], body=body)
        module = QModule(name="test", functions=[func])
        variants = cg.generate(module)

        v = variants[0]
        assert v.safe_cost > v.fast_cost


# ═══════════════════════════════════════════════════════════
# Summary Output Test
# ═══════════════════════════════════════════════════════════

class TestCostModelSummary:
    """Test the summary output format."""

    def test_summary_contains_arch(self):
        cm = CostModel("arm64")
        s = cm.summary()
        assert "arm64" in s

    def test_summary_contains_opcodes(self):
        cm = CostModel("arm64")
        s = cm.summary()
        assert "Q_ADD" in s
        assert "Q_MUL" in s
        assert "Q_DIV" in s
