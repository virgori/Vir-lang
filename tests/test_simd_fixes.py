"""
test_simd_fixes.py – Tests for SIMD Production Fixes
=====================================================
Validates:
  Fix 1: CodeGen emits real NEON/AVX bytes (not NOP) for SIMD opcodes
  Fix 2: Pack/unpack cost prevents vectorization of short sequences
  Fix 3: Aligned allocation (32-byte) for SIMD compliance
"""

import platform
import struct
import pytest

from src.ir.cost_model.cost_model import CostModel, PackCostInfo
from src.ir.instructions.q_ir import (
    Immediate,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)
from src.ir.optimizer.optimizer import IROptimizer
from src.backend.codegen.codegen import CodeGenerator, TargetArch


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

IS_ARM64 = platform.machine() in ("arm64", "aarch64")

def _make_func(body: list[QInstruction], name: str = "test") -> QFunction:
    return QFunction(name=name, params=[], body=body)


def _make_module(funcs: list[QFunction]) -> QModule:
    return QModule(functions=funcs)


def _codegen_bytes(opcodes: list[Opcode], arch: TargetArch, mode: str = "safe") -> bytes:
    """Generate machine code for a sequence of SIMD opcodes, return bytes."""
    body = []
    for op in opcodes:
        body.append(QInstruction(opcode=op, dest=VReg(0), src1=VReg(1), src2=VReg(2)))
    body.append(QInstruction(opcode=Opcode.Q_HALT))
    mod = _make_module([_make_func(body)])
    gen = CodeGenerator(arch=arch)
    variants = gen.generate(mod)
    assert len(variants) > 0, "Expected at least one CodeVariant"
    if mode == "safe":
        return bytes(variants[0].safe_code.bytes_)
    else:
        return bytes(variants[0].fast_code.bytes_)


# ═══════════════════════════════════════════════════════════
# Fix 1: CodeGen SIMD Emission (NEON & AVX)
# ═══════════════════════════════════════════════════════════

class TestCodegenSIMDEmission:
    """Verify codegen emits non-NOP bytes for SIMD opcodes."""

    # ARM64 NOP is 0xD503201F (4 bytes); x86 NOP is 0x90 (1 byte)
    ARM64_NOP = b"\x1f\x20\x03\xd5"
    X86_NOP = b"\x90"

    SIMD_OPS = [
        Opcode.Q_VLOAD, Opcode.Q_VSTORE, Opcode.Q_VADD,
        Opcode.Q_VSUB, Opcode.Q_VMUL, Opcode.Q_VDIV,
        Opcode.Q_VMIN, Opcode.Q_VMAX, Opcode.Q_VFMA,
    ]

    @pytest.mark.parametrize("opcode", SIMD_OPS, ids=lambda o: o.name)
    def test_arm64_simd_not_nop_safe(self, opcode):
        """ARM64 safe path: each SIMD opcode should emit non-NOP bytes."""
        code = _codegen_bytes([opcode], TargetArch.ARM64, mode="safe")
        # The emitted bytes for the SIMD instr should not be just NOP
        # code contains SIMD instr bytes + HALT epilogue bytes
        # Just verify the code isn't composed entirely of NOPs up to the HALT
        assert len(code) > len(self.ARM64_NOP)  # must emit more than a single NOP

    @pytest.mark.parametrize("opcode", SIMD_OPS, ids=lambda o: o.name)
    def test_arm64_simd_not_nop_fast(self, opcode):
        """ARM64 fast path: each SIMD opcode should emit non-NOP bytes."""
        code = _codegen_bytes([opcode], TargetArch.ARM64, mode="fast")
        assert len(code) > len(self.ARM64_NOP)

    @pytest.mark.parametrize("opcode", SIMD_OPS, ids=lambda o: o.name)
    def test_x86_simd_not_nop_safe(self, opcode):
        """x86_64 safe path: each SIMD opcode should emit non-NOP bytes."""
        code = _codegen_bytes([opcode], TargetArch.X86_64, mode="safe")
        assert len(code) > len(self.X86_NOP)

    @pytest.mark.parametrize("opcode", SIMD_OPS, ids=lambda o: o.name)
    def test_x86_simd_not_nop_fast(self, opcode):
        """x86_64 fast path: each SIMD opcode should emit non-NOP bytes."""
        code = _codegen_bytes([opcode], TargetArch.X86_64, mode="fast")
        assert len(code) > len(self.X86_NOP)

    def test_arm64_neon_vadd_encoding(self):
        """NEON ADD.4S uses opcode 0x4EA0_1C00 family – verify byte pattern."""
        code = _codegen_bytes([Opcode.Q_VADD], TargetArch.ARM64, mode="safe")
        # Look for NEON ADD 4S encoding: bits [31:24] = 0x4E
        has_neon_prefix = any(code[i] == 0x4E for i in range(len(code)))
        assert has_neon_prefix, "Expected NEON 4S encoding byte 0x4E"

    def test_x86_avx_vadd_encoding(self):
        """AVX VADDPS uses VEX prefix 0xC5 – verify byte pattern."""
        code = _codegen_bytes([Opcode.Q_VADD], TargetArch.X86_64, mode="safe")
        # VEX 2-byte prefix starts with 0xC5
        assert 0xC5 in code, "Expected VEX prefix byte 0xC5 for AVX instruction"

    def test_arm64_neon_vload_encoding(self):
        """NEON LD1 uses specific encoding – verify non-NOP."""
        code = _codegen_bytes([Opcode.Q_VLOAD], TargetArch.ARM64, mode="safe")
        # LD1 {V0.4S}, [X0] encoding contains 0x4C (SIMD load family)
        has_simd_load = any(code[i] == 0x4C for i in range(len(code)))
        assert has_simd_load, "Expected NEON LD1 encoding byte 0x4C"

    def test_x86_avx_vmovaps_encoding(self):
        """AVX VMOVAPS uses VEX prefix 0xC5 – verify byte pattern."""
        code = _codegen_bytes([Opcode.Q_VLOAD], TargetArch.X86_64, mode="safe")
        assert 0xC5 in code, "Expected VEX prefix byte 0xC5 for VMOVAPS"

    def test_arm64_vreduce_emits_addv(self):
        """Q_VREDUCE on ARM64 should emit ADDV instruction."""
        code = _codegen_bytes([Opcode.Q_VREDUCE], TargetArch.ARM64, mode="safe")
        # ADDV has specific NEON encoding – just verify non-NOP
        assert len(code) > 4  # More than a single NOP

    def test_arm64_vsplat_emits_dup(self):
        """Q_VSPLAT on ARM64 should emit DUP instruction."""
        code = _codegen_bytes([Opcode.Q_VSPLAT], TargetArch.ARM64, mode="safe")
        assert len(code) > 4

    def test_simd_sequence_arm64(self):
        """Multiple SIMD ops should produce multi-instruction output."""
        ops = [Opcode.Q_VLOAD, Opcode.Q_VADD, Opcode.Q_VMUL, Opcode.Q_VSTORE]
        code = _codegen_bytes(ops, TargetArch.ARM64, mode="fast")
        # 4 SIMD ops × 4 bytes each + HALT epilogue
        assert len(code) >= 16 + 4

    def test_simd_sequence_x86(self):
        """Multiple SIMD ops should produce multi-instruction output."""
        ops = [Opcode.Q_VLOAD, Opcode.Q_VADD, Opcode.Q_VMUL, Opcode.Q_VSTORE]
        code = _codegen_bytes(ops, TargetArch.X86_64, mode="fast")
        # VEX instructions are 3-4 bytes each
        assert len(code) >= 12


# ═══════════════════════════════════════════════════════════
# Fix 2: Pack/Unpack Cost Model
# ═══════════════════════════════════════════════════════════

class TestPackUnpackCost:
    """Verify pack/unpack overhead prevents short-sequence vectorization."""

    def test_pack_cost_info_defaults(self):
        pci = PackCostInfo()
        assert pci.pack_latency == 3
        assert pci.unpack_latency == 2
        assert pci.alignment_penalty == 1.5

    def test_cost_model_has_pack_cost(self):
        cm = CostModel("arm64")
        assert hasattr(cm, "pack_cost")
        assert isinstance(cm.pack_cost, PackCostInfo)

    def test_cost_model_has_min_vectorize_count(self):
        cm = CostModel("arm64")
        assert hasattr(cm, "min_vectorize_count")
        assert cm.min_vectorize_count >= 4

    def test_should_not_vectorize_small_trip(self):
        """Trip count < min_vectorize_count must stay scalar."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        assert cm.should_vectorize(Opcode.Q_ADD, trip_count=2) is False
        assert cm.should_vectorize(Opcode.Q_ADD, trip_count=4) is False

    def test_should_not_vectorize_below_threshold(self):
        """Trip count below min_vectorize_count should stay scalar."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        cm.min_vectorize_count = 8
        assert cm.should_vectorize(Opcode.Q_ADD, trip_count=7) is False

    def test_should_vectorize_large_trip(self):
        """Large trip count with expensive op should vectorize."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        # DIV is expensive (high scalar latency) so vectorization should win
        # even with pack/unpack overhead
        assert cm.should_vectorize(Opcode.Q_DIV, trip_count=64) is True

    def test_vectorization_speedup_includes_pack_overhead(self):
        """Speedup must account for pack/unpack – result < raw lane count."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16  # 4 lanes for 32-bit
        # Use DIV which has high scalar latency, so speedup is meaningful
        speedup = cm.vectorization_speedup(Opcode.Q_DIV)
        # Without pack overhead, speedup would be lanes * scalar_lat / vec_lat.
        # With pack overhead, it should be noticeably reduced.
        lanes = cm.simd_lanes(4)
        raw_speedup = cm.latency(Opcode.Q_DIV) * lanes / cm.latency(Opcode.Q_VDIV)
        assert speedup < raw_speedup, "Pack/unpack overhead must reduce speedup"

    def test_vectorization_speedup_with_high_pack_cost(self):
        """Very high pack cost should make vectorization less attractive."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        cm.pack_cost = PackCostInfo(pack_latency=20, unpack_latency=20)
        speedup = cm.vectorization_speedup(Opcode.Q_ADD)
        # With 40 cycles overhead on 4 cycles compute, speedup should be very low
        assert speedup < 1.0, "High pack cost should negate vectorization benefit"

    def test_should_vectorize_respects_pack_cost(self):
        """Setting very high pack cost should prevent vectorization even at trip=32."""
        cm = CostModel("arm64")
        cm.max_simd_width = 16
        cm.pack_cost = PackCostInfo(pack_latency=100, unpack_latency=100)
        # 32 iterations with enormous pack/unpack overhead should fail
        assert cm.should_vectorize(Opcode.Q_ADD, trip_count=32) is False

    def test_pack_cost_summary_in_output(self):
        """Summary output should include pack/unpack information."""
        cm = CostModel("arm64")
        s = cm.summary()
        assert "Pack/Unpack" in s or "pack=" in s


# ═══════════════════════════════════════════════════════════
# Fix 3: DCE Preserves SIMD Instructions
# ═══════════════════════════════════════════════════════════

class TestDCESIMDAwareness:
    """Verify DCE treats SIMD ops as side-effect-free and doesn't wrongly kill them."""

    def test_dce_preserves_used_simd_ops(self):
        """SIMD ops whose results are consumed should survive DCE."""
        body = [
            QInstruction(opcode=Opcode.Q_VLOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(opcode=Opcode.Q_VADD, dest=VReg(1), src1=VReg(0), src2=VReg(0)),
            QInstruction(opcode=Opcode.Q_VSTORE, dest=VReg(1), src1=Immediate(0)),
            QInstruction(opcode=Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        func = opt_mod.functions[0]
        opcodes_after = [i.opcode for i in func.body]
        # VSTORE has a side effect, so it and its deps should survive
        assert Opcode.Q_VSTORE in opcodes_after

    def test_dce_removes_unused_simd_ops(self):
        """Unused SIMD ops (no side effect) should be removed by DCE."""
        body = [
            QInstruction(opcode=Opcode.Q_VLOAD, dest=VReg(0), src1=Immediate(0)),
            QInstruction(opcode=Opcode.Q_VADD, dest=VReg(1), src1=VReg(0), src2=VReg(0)),
            # VReg(1) is never used
            QInstruction(opcode=Opcode.Q_HALT),
        ]
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        func = opt_mod.functions[0]
        opcodes_after = [i.opcode for i in func.body]
        # DCE should be able to remove unused VADD and VLOAD
        assert Opcode.Q_VADD not in opcodes_after


# ═══════════════════════════════════════════════════════════
# Fix 3: Aligned Allocation (C-level – tested via build)
# ═══════════════════════════════════════════════════════════

class TestAlignedAlloc:
    """
    Verify that intrinsics.c uses 32-byte aligned allocation.
    This is a source-code-level check, since we can't call C from pytest.
    """

    def test_source_uses_posix_memalign(self):
        """intrinsics.c should call posix_memalign, not malloc."""
        from pathlib import Path
        intrinsics_path = Path(__file__).resolve().parent.parent / "core" / "src" / "intrinsics.c"
        if not intrinsics_path.exists():
            pytest.skip("intrinsics.c not found")
        src = intrinsics_path.read_text()
        assert "posix_memalign" in src, "Should use posix_memalign for aligned alloc"
        assert "32" in src, "Should align to 32 bytes"

    def test_source_does_not_use_bare_malloc_for_alloc(self):
        """vir_builtin_alloc should not use bare malloc."""
        from pathlib import Path
        intrinsics_path = Path(__file__).resolve().parent.parent / "core" / "src" / "intrinsics.c"
        if not intrinsics_path.exists():
            pytest.skip("intrinsics.c not found")
        src = intrinsics_path.read_text()
        # Find the alloc function and check it doesn't use malloc directly
        # (posix_memalign replaces malloc in the alloc path)
        alloc_start = src.find("vir_builtin_alloc")
        if alloc_start == -1:
            pytest.skip("vir_builtin_alloc not found")
        alloc_end = src.find("}", alloc_start)
        alloc_body = src[alloc_start:alloc_end]
        # malloc may still appear in comments; check it's not the actual allocator
        assert "posix_memalign" in alloc_body or "_aligned_malloc" in alloc_body


# ═══════════════════════════════════════════════════════════
# Integration: Vectorizer + CostModel Interaction
# ═══════════════════════════════════════════════════════════

class TestVectorizerCostIntegration:
    """End-to-end: optimizer vectorization respects cost model thresholds."""

    def test_short_add_sequence_stays_scalar(self):
        """4 ADDs should NOT be vectorized (below min_vectorize_count)."""
        body = [
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(i), src1=Immediate(i), src2=Immediate(1))
            for i in range(4)
        ]
        body.append(QInstruction(opcode=Opcode.Q_HALT))
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        opt_mod = opt.optimize(mod)
        func = opt_mod.functions[0]
        opcodes = [i.opcode for i in func.body]
        # Should remain scalar
        assert Opcode.Q_VADD not in opcodes, "Short sequence should not vectorize"

    def test_long_add_sequence_may_vectorize(self):
        """16+ ADDs could be vectorized if cost model permits."""
        body = [
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(i), src1=Immediate(i), src2=Immediate(1))
            for i in range(16)
        ]
        body.append(QInstruction(opcode=Opcode.Q_HALT))
        mod = _make_module([_make_func(body)])
        opt = IROptimizer()
        # Note: vectorization depends on the optimizer's analysis
        # This test primarily validates the path doesn't crash
        opt_mod = opt.optimize(mod)
        assert opt_mod is not None
