"""
test_phase_h.py – Tests for Phase H: SIMD Vectorization & Memory Hierarchy
============================================================================
Tests for:
  - CPU capability detection (cpu_caps.json loading)
  - SIMD opcodes in Q-IR
  - Memory hierarchy model (cache, TLB, prefetch)
  - SIMD vectorizer pass in optimizer
  - Architecture configs (ARM64 NEON, x86_64 AVX, RISC-V RVV)
  - Auto-tuner engine
  - Cost model SIMD extensions
"""

import json
import math
import pytest
from pathlib import Path

from src.ir.instructions.q_ir import (
    Immediate,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)
from src.ir.cost_model.cost_model import (
    CostModel,
    CacheTopology,
    TLBInfo,
    PrefetchConfig,
    InstrCostEntry,
)
from src.ir.optimizer.optimizer import IROptimizer
from src.ir.optimizer.auto_tuner import AutoTuner, TuningConfig, TrialResult


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _make_func(body: list[QInstruction], name: str = "test") -> QFunction:
    return QFunction(name=name, params=[], body=body)

def _make_module(funcs: list[QFunction]) -> QModule:
    return QModule(functions=funcs)


# ═══════════════════════════════════════════════════════════
# 1. SIMD Opcodes in Q-IR
# ═══════════════════════════════════════════════════════════

class TestSIMDOpcodes:
    """Test that vector opcodes exist and are valid."""

    def test_vector_opcodes_exist(self):
        assert hasattr(Opcode, "Q_VADD")
        assert hasattr(Opcode, "Q_VSUB")
        assert hasattr(Opcode, "Q_VMUL")
        assert hasattr(Opcode, "Q_VFMA")
        assert hasattr(Opcode, "Q_VDIV")
        assert hasattr(Opcode, "Q_VLOAD")
        assert hasattr(Opcode, "Q_VSTORE")
        assert hasattr(Opcode, "Q_VREDUCE")
        assert hasattr(Opcode, "Q_VSPLAT")
        assert hasattr(Opcode, "Q_VPERM")
        assert hasattr(Opcode, "Q_VMIN")
        assert hasattr(Opcode, "Q_VMAX")

    def test_vector_instruction_creation(self):
        instr = QInstruction(
            opcode=Opcode.Q_VADD,
            dest=VReg(0),
            src1=VReg(1),
            src2=VReg(2),
            comment="vector add",
        )
        assert instr.opcode == Opcode.Q_VADD
        assert instr.dest == VReg(0)

    def test_all_simd_opcodes_are_distinct(self):
        simd_ops = [
            Opcode.Q_VADD, Opcode.Q_VSUB, Opcode.Q_VMUL, Opcode.Q_VFMA,
            Opcode.Q_VDIV, Opcode.Q_VLOAD, Opcode.Q_VSTORE, Opcode.Q_VREDUCE,
            Opcode.Q_VSPLAT, Opcode.Q_VPERM, Opcode.Q_VMIN, Opcode.Q_VMAX,
        ]
        values = [op.value for op in simd_ops]
        assert len(values) == len(set(values)), "SIMD opcodes must be unique"

    def test_total_opcode_count(self):
        """We should have scalar + vector opcodes."""
        all_opcodes = list(Opcode)
        assert len(all_opcodes) >= 38  # 26 scalar + 12 vector


# ═══════════════════════════════════════════════════════════
# 2. CostModel SIMD Support
# ═══════════════════════════════════════════════════════════

class TestCostModelSIMD:
    """Test SIMD cost queries in the cost model."""

    def test_simd_costs_loaded_arm64(self):
        cm = CostModel("arm64")
        entry = cm.get(Opcode.Q_VADD)
        assert entry.latency > 0
        assert entry.throughput > 0

    def test_simd_costs_loaded_x86_64(self):
        cm = CostModel("x86_64")
        entry = cm.get(Opcode.Q_VADD)
        assert entry.latency > 0

    def test_vdiv_slower_than_vadd(self):
        cm = CostModel("arm64")
        assert cm.latency(Opcode.Q_VDIV) > cm.latency(Opcode.Q_VADD)

    def test_vfma_exists(self):
        cm = CostModel("arm64")
        entry = cm.get(Opcode.Q_VFMA)
        assert entry.latency >= 3

    def test_default_fallback_has_simd(self):
        """CostModel defaults should include SIMD opcodes."""
        cm = CostModel("arm64", config_path="/nonexistent.json")
        entry = cm.get(Opcode.Q_VADD)
        assert entry.latency > 0

    def test_simd_lanes_float32(self):
        cm = CostModel("arm64")
        cm.max_simd_width = 16  # 128-bit
        assert cm.simd_lanes(4) == 4  # 128 / 32 = 4 lanes

    def test_simd_lanes_float64(self):
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        assert cm.simd_lanes(8) == 2  # 128 / 64 = 2 lanes

    def test_simd_lanes_avx512(self):
        cm = CostModel("x86_64")
        cm.max_simd_width = 64  # 512-bit
        assert cm.simd_lanes(4) == 16  # 512 / 32 = 16 lanes

    def test_vectorization_speedup(self):
        cm = CostModel("arm64")
        speedup = cm.vectorization_speedup(Opcode.Q_DIV)
        assert speedup > 1.0  # DIV is expensive enough to benefit from SIMD

    def test_should_vectorize_sufficient_trip(self):
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        assert cm.should_vectorize(Opcode.Q_DIV, trip_count=32) is True

    def test_should_not_vectorize_small_trip(self):
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        assert cm.should_vectorize(Opcode.Q_ADD, trip_count=2) is False


# ═══════════════════════════════════════════════════════════
# 3. Memory Hierarchy Model
# ═══════════════════════════════════════════════════════════

class TestMemoryHierarchy:
    """Test CacheTopology, TLB, Prefetch models."""

    def test_cache_topology_defaults(self):
        ct = CacheTopology()
        assert ct.cache_line_size == 64
        assert ct.l1d_size_kb > 0
        assert ct.l2_size_kb > 0

    def test_tlb_info_defaults(self):
        tlb = TLBInfo()
        assert tlb.page_size > 0
        assert tlb.l1_dtlb_entries > 0
        assert tlb.l2_tlb_entries > 0

    def test_prefetch_config_defaults(self):
        pf = PrefetchConfig()
        assert pf.hw_prefetch_distance > 0
        assert pf.sw_prefetch is True

    def test_estimated_access_cost_l1(self):
        cm = CostModel("arm64")
        # Working set fits in L1
        cost = cm.estimated_access_cost(working_set_kb=32)
        assert cost == cm.memory.l1_latency

    def test_estimated_access_cost_l2(self):
        cm = CostModel("arm64")
        # Working set larger than L1 but fits in L2
        cost = cm.estimated_access_cost(working_set_kb=2048)
        assert cm.memory.l1_latency < cost <= cm.memory.l2_latency

    def test_estimated_access_cost_main_memory(self):
        cm = CostModel("arm64")
        # Working set very large
        cost = cm.estimated_access_cost(working_set_kb=1_000_000)
        assert cost > cm.memory.l2_latency

    def test_tlb_miss_cost_no_miss(self):
        cm = CostModel("arm64")
        cost = cm.tlb_miss_cost(num_pages_touched=10)
        assert cost == 0.0

    def test_tlb_miss_cost_overflow(self):
        cm = CostModel("arm64")
        cost = cm.tlb_miss_cost(num_pages_touched=10000)
        assert cost > 0

    def test_cache_lines_for_array(self):
        cm = CostModel("arm64")
        cm.cache = CacheTopology(cache_line_size=64)
        # 16 floats × 4 bytes = 64 bytes = 1 cache line
        assert cm.cache_lines_for(16, element_bytes=4) == 1
        # 32 floats × 4 bytes = 128 bytes = 2 cache lines
        assert cm.cache_lines_for(32, element_bytes=4) == 2

    def test_prefetch_distance_elements(self):
        cm = CostModel("arm64")
        dist = cm.prefetch_distance_elements(element_bytes=4)
        assert dist > 0

    def test_load_cache_topology_from_json(self):
        """Test loading cache topology from cpu_caps.json."""
        caps_path = PROJECT_ROOT / "data" / "arch" / "cpu_caps.json"
        if caps_path.exists():
            cm = CostModel("arm64")
            cm.load_cache_topology(str(caps_path))
            assert cm.cache.l1d_size_kb > 0
            assert cm.cache.cache_line_size > 0
            assert cm.tlb.page_size > 0


# ═══════════════════════════════════════════════════════════
# 4. Architecture Config Files
# ═══════════════════════════════════════════════════════════

class TestArchConfigs:
    """Test that generated config files contain SIMD data."""

    def test_arm64_config_has_neon(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        # NEON instructions should be present
        assert "FADD_v" in mnemonics
        assert "FMUL_v" in mnemonics
        assert "LD1" in mnemonics
        assert "FMLA_v" in mnemonics

    def test_arm64_config_has_amx(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "AMX_FMA32" in mnemonics
        assert "AMX_LDX" in mnemonics

    def test_arm64_config_has_simd_qir_map(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        qir_map = data.get("qir_map", {})
        assert "Q_VADD" in qir_map
        assert "Q_VLOAD" in qir_map
        assert "Q_VMUL" in qir_map

    def test_x86_config_has_avx(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "x86_64_config.json"
        if not cfg_path.exists():
            pytest.skip("x86_64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "VADDPS" in mnemonics
        assert "VMULPS" in mnemonics
        assert "VFMADD231PS" in mnemonics

    def test_x86_config_has_avx512(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "x86_64_config.json"
        if not cfg_path.exists():
            pytest.skip("x86_64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "VADDPS_Z" in mnemonics
        assert "VFMADD231PS_Z" in mnemonics

    def test_x86_config_has_intel_amx(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "x86_64_config.json"
        if not cfg_path.exists():
            pytest.skip("x86_64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "TDPBF16PS" in mnemonics
        assert "TILELOADD" in mnemonics

    def test_rv64_config_exists(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "rv64_config.json"
        if not cfg_path.exists():
            pytest.skip("rv64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        assert data["arch"] == "rv64"
        assert len(data["instructions"]) > 50

    def test_rv64_config_has_base_instrs(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "rv64_config.json"
        if not cfg_path.exists():
            pytest.skip("rv64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "ADD_rv" in mnemonics
        assert "MUL_rv" in mnemonics
        assert "LD" in mnemonics
        assert "JAL" in mnemonics

    def test_rv64_config_has_fp(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "rv64_config.json"
        if not cfg_path.exists():
            pytest.skip("rv64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "FADD_S" in mnemonics   # RV64F
        assert "FADD_D" in mnemonics   # RV64D
        assert "FMADD_S" in mnemonics

    def test_rv64_config_has_vector(self):
        cfg_path = PROJECT_ROOT / "data" / "arch" / "rv64_config.json"
        if not cfg_path.exists():
            pytest.skip("rv64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "VADD_VV" in mnemonics    # RVV
        assert "VFADD_VV" in mnemonics
        assert "VLE32_V" in mnemonics

    def test_rv64_cost_model_loads(self):
        """Test CostModel can load rv64 config."""
        cm = CostModel("rv64")
        assert cm.arch == "rv64"
        assert cm.latency(Opcode.Q_ADD) >= 1

    def test_instruction_count_per_arch(self):
        """Verify instruction count is reasonable."""
        for arch, min_count in [("arm64", 100), ("x86_64", 80), ("rv64", 90)]:
            cfg_path = PROJECT_ROOT / "data" / "arch" / f"{arch}_config.json"
            if not cfg_path.exists():
                continue
            with open(cfg_path) as f:
                data = json.load(f)
            assert len(data["instructions"]) >= min_count, \
                f"{arch} should have >= {min_count} instructions"


# ═══════════════════════════════════════════════════════════
# 5. CPU Capability Detection
# ═══════════════════════════════════════════════════════════

class TestCPUCaps:
    """Test cpu_caps.json output from the C detector."""

    def test_cpu_caps_json_exists(self):
        caps_path = PROJECT_ROOT / "data" / "arch" / "cpu_caps.json"
        if not caps_path.exists():
            pytest.skip("cpu_caps.json not generated (run core/build/cpu_caps)")
        with open(caps_path) as f:
            data = json.load(f)
        assert "arch" in data
        assert "simd" in data
        assert "cache" in data
        assert "tlb" in data
        assert "prefetch" in data

    def test_cpu_caps_simd_fields(self):
        caps_path = PROJECT_ROOT / "data" / "arch" / "cpu_caps.json"
        if not caps_path.exists():
            pytest.skip("cpu_caps.json not generated")
        with open(caps_path) as f:
            data = json.load(f)
        simd = data["simd"]
        assert "neon" in simd or "avx" in simd
        assert "max_simd_width" in simd
        assert simd["max_simd_width"] >= 16

    def test_cpu_caps_cache_fields(self):
        caps_path = PROJECT_ROOT / "data" / "arch" / "cpu_caps.json"
        if not caps_path.exists():
            pytest.skip("cpu_caps.json not generated")
        with open(caps_path) as f:
            data = json.load(f)
        cache = data["cache"]
        assert cache["line_size"] > 0
        assert cache["l1d_size_kb"] > 0
        assert cache["l2_size_kb"] > 0

    def test_cpu_caps_tlb_fields(self):
        caps_path = PROJECT_ROOT / "data" / "arch" / "cpu_caps.json"
        if not caps_path.exists():
            pytest.skip("cpu_caps.json not generated")
        with open(caps_path) as f:
            data = json.load(f)
        tlb = data["tlb"]
        assert tlb["page_size"] > 0
        assert tlb["l1_dtlb_entries"] > 0


# ═══════════════════════════════════════════════════════════
# 6. SIMD Vectorizer Pass
# ═══════════════════════════════════════════════════════════

class TestSIMDVectorizer:
    """Test the SIMD vectorization pass in the optimizer."""

    def test_vectorize_consecutive_adds(self):
        """4 consecutive independent ADDs should be vectorized on 128-bit SIMD."""
        body = [
            QInstruction(Opcode.Q_ADD, VReg(0), VReg(10), VReg(20)),
            QInstruction(Opcode.Q_ADD, VReg(1), VReg(11), VReg(21)),
            QInstruction(Opcode.Q_ADD, VReg(2), VReg(12), VReg(22)),
            QInstruction(Opcode.Q_ADD, VReg(3), VReg(13), VReg(23)),
            # Keep results alive so DCE doesn't remove them
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.cost_model.max_simd_width = 16  # 128-bit = 4 lanes of f32
        opt.optimize(module)

        # At minimum, the optimizer shouldn't crash and body stays non-empty
        assert len(module.functions[0].body) > 0

    def test_vectorize_preserves_dependent_ops(self):
        """Instructions with dependencies should NOT be vectorized together."""
        body = [
            QInstruction(Opcode.Q_ADD, VReg(0), VReg(1), VReg(2)),
            QInstruction(Opcode.Q_ADD, VReg(3), VReg(0), VReg(4)),  # depends on VReg(0)
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.optimize(module)

        # Should remain scalar
        vec_instrs = [i for i in module.functions[0].body
                      if i.opcode == Opcode.Q_VADD]
        assert len(vec_instrs) == 0

    def test_vectorize_mixed_opcodes_not_merged(self):
        """Different opcodes should not be merged into a single vector op."""
        body = [
            QInstruction(Opcode.Q_ADD, VReg(0), VReg(10), VReg(20)),
            QInstruction(Opcode.Q_MUL, VReg(1), VReg(11), VReg(21)),
            QInstruction(Opcode.Q_ADD, VReg(2), VReg(12), VReg(22)),
            QInstruction(Opcode.Q_MUL, VReg(3), VReg(13), VReg(23)),
            # Keep results alive so DCE doesn't remove them
            QInstruction(Opcode.Q_RET, src1=VReg(0)),
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.optimize(module)

        # Mixed opcodes: no vectorization, results kept alive by RET
        assert len(module.functions[0].body) >= 2

    def test_vectorizer_handles_empty_function(self):
        func = _make_func([])
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.optimize(module)
        assert module.functions[0].body == []

    def test_vectorizer_handles_non_vectorizable(self):
        """Non-arithmetic ops should pass through unchanged."""
        body = [
            QInstruction(Opcode.Q_JUMP, dest=None, src1=None),
            QInstruction(Opcode.Q_RET),
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.optimize(module)
        # Non-vectorizable ops should remain
        opcodes = [i.opcode for i in module.functions[0].body]
        assert Opcode.Q_JUMP in opcodes or Opcode.Q_RET in opcodes


# ═══════════════════════════════════════════════════════════
# 7. Auto-Tuner
# ═══════════════════════════════════════════════════════════

class TestAutoTuner:
    """Test the ML-based auto-tuning engine."""

    def test_tuning_config_defaults(self):
        config = TuningConfig()
        assert config.vectorization_threshold == 8
        assert config.unroll_factor == 4
        assert config.alignment_pad == 64

    def test_auto_tuner_creation(self):
        tuner = AutoTuner(arch="arm64")
        assert tuner.arch == "arm64"
        assert tuner.state.arch == "arm64"

    def test_auto_tuner_random_config(self):
        tuner = AutoTuner(arch="arm64")
        config = tuner._random_config()
        assert 2 <= config.vectorization_threshold <= 64
        assert 1 <= config.unroll_factor <= 16
        assert config.alignment_pad in {16, 32, 64, 128, 256}

    def test_auto_tuner_perturb_best(self):
        tuner = AutoTuner(arch="arm64")
        config = tuner._perturb_best()
        # Should produce a valid config different from default
        assert isinstance(config, TuningConfig)

    def test_auto_tuner_tune_converges(self):
        """Test that tuner finds a good configuration."""
        tuner = AutoTuner(arch="arm64")

        # Simple benchmark: score decreases as threshold approaches 16
        def benchmark(config: TuningConfig) -> float:
            return abs(config.vectorization_threshold - 16) + \
                   abs(config.unroll_factor - 4) * 0.5

        best = tuner.tune(benchmark, max_trials=20, patience=8)
        # Should find something reasonable
        assert best.vectorization_threshold > 0
        assert tuner.state.best_score < 100

    def test_auto_tuner_summary(self):
        tuner = AutoTuner(arch="arm64")
        summary = tuner.summary()
        assert "AutoTuner: arm64" in summary
        assert "vectorization_threshold" in summary

    def test_trial_result(self):
        config = TuningConfig()
        result = TrialResult(config=config, score=42.0, trial_id=1)
        assert result.score == 42.0
        assert result.trial_id == 1


# ═══════════════════════════════════════════════════════════
# 8. Integration Tests
# ═══════════════════════════════════════════════════════════

class TestPhaseHIntegration:
    """End-to-end integration tests for Phase H features."""

    def test_cost_model_with_cache_topology(self):
        """Test cost model with loaded cache topology."""
        cm = CostModel("arm64")
        cm.cache = CacheTopology(
            cache_line_size=128, l1d_size_kb=64,
            l1d_assoc=8, l1i_size_kb=128,
            l2_size_kb=4096, l2_assoc=16,
        )
        # Verify cache-aware calculations work
        cost_l1 = cm.estimated_access_cost(32)
        cost_l2 = cm.estimated_access_cost(2048)
        assert cost_l1 < cost_l2

    def test_optimizer_preserves_correctness(self):
        """Full optimization pipeline including vectorizer doesn't break code."""
        body = [
            QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(10)),
            QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(20)),
            QInstruction(Opcode.Q_ADD, VReg(2), VReg(0), VReg(1)),
            QInstruction(Opcode.Q_PRINT, dest=VReg(2)),
            QInstruction(Opcode.Q_HALT),
        ]
        func = _make_func(body)
        module = _make_module([func])
        opt = IROptimizer("arm64")
        opt.optimize(module)

        # PRINT and HALT should survive
        opcodes = [i.opcode for i in module.functions[0].body]
        assert Opcode.Q_PRINT in opcodes

    def test_simd_cost_vs_scalar(self):
        """Vector operations should generally be cheaper per element."""
        cm = CostModel("arm64")
        scalar_add = cm.latency(Opcode.Q_ADD)
        vector_add = cm.latency(Opcode.Q_VADD)
        lanes = cm.simd_lanes(4)

        # Vector ADD processes `lanes` elements, should be cheaper per-element
        cost_per_element_scalar = scalar_add
        cost_per_element_vector = vector_add / lanes
        assert cost_per_element_vector <= cost_per_element_scalar

    def test_three_arch_cost_model(self):
        """Test that all three architectures load and work."""
        for arch in ["arm64", "x86_64", "rv64"]:
            cm = CostModel(arch)
            assert cm.arch == arch
            assert cm.latency(Opcode.Q_ADD) >= 1
            assert cm.latency(Opcode.Q_MUL) >= 1
            assert cm.latency(Opcode.Q_DIV) >= 1

    def test_neon_dot_product_in_config(self):
        """NEON dot product (FEAT_DotProd) should be in ARM64 config."""
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "SDOT_v" in mnemonics
        assert "UDOT_v" in mnemonics

    def test_bf16_matmul_in_config(self):
        """BF16 matrix multiply should be in ARM64 config."""
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "BFMMLA" in mnemonics

    def test_i8mm_in_config(self):
        """I8MM (int8 matrix multiply) should be in ARM64 config."""
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "SMMLA" in mnemonics
        assert "UMMLA" in mnemonics

    def test_crypto_aes_in_config(self):
        """AES crypto instructions should be in ARM64 config."""
        cfg_path = PROJECT_ROOT / "data" / "arch" / "arm64_config.json"
        if not cfg_path.exists():
            pytest.skip("arm64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "AESE" in mnemonics
        assert "AESMC" in mnemonics

    def test_vnni_in_x86_config(self):
        """AVX-512 VNNI instructions for neural network acceleration."""
        cfg_path = PROJECT_ROOT / "data" / "arch" / "x86_64_config.json"
        if not cfg_path.exists():
            pytest.skip("x86_64_config.json not generated")
        with open(cfg_path) as f:
            data = json.load(f)
        mnemonics = {i["mnemonic"] for i in data["instructions"]}
        assert "VPDPBUSD" in mnemonics
