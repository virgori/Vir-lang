"""
codegen.py – Code Generator: Q-IR → Native Machine Code
=========================================================
Spec §3.2 – Tạo 2 biến thể (multi-versioning):
  Bản A (Safe):  Dùng stack (chậm, ổn định)
  Bản B (Fast):  Dùng thanh ghi vật lý trực tiếp

Phase 6 – SIMD Vectorization:
  Loop auto-vectorizer detects counted loops and emits
  NEON (ARM64) / AVX (x86_64) SIMD instructions for the
  loop body, processing 4 elements per iteration.

Hỗ trợ kiến trúc: x86_64, arm64.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)


class TargetArch(Enum):
    X86_64 = "x86_64"
    ARM64 = "arm64"


@dataclass
class MachineCode:
    """Đoạn mã máy kèm metadata."""
    bytes_: bytearray
    arch: TargetArch
    patch_offsets: dict[str, int] = field(default_factory=dict)
    # patch_id → byte offset trong bytes_ nơi có lệnh JMP cần vá

    def hex_dump(self) -> str:
        return " ".join(f"{b:02X}" for b in self.bytes_)


@dataclass
class CodeVariant:
    """
    Một Patch Point có 2 biến thể.
    Runtime sẽ chọn variant phù hợp.
    """
    patch_id: str
    safe_code: MachineCode    # Bản A – stack-based
    fast_code: MachineCode    # Bản B – register-based
    safe_cost: float = 0.0    # Estimated cost in cycles (safe variant)
    fast_cost: float = 0.0    # Estimated cost in cycles (fast variant)
    speedup: float = 1.0      # safe_cost / fast_cost


# ═══════════════════════════════════════════════════════════
# x86_64 Machine Code Templates
# ═══════════════════════════════════════════════════════════

class X86_64:
    """Helpers tạo mã x86_64."""

    # ── Register encoding ──────────────────────────────────
    _GP_REGS = ["rax", "rcx", "rdx", "rbx", "rsi", "rdi",
                "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]

    @staticmethod
    def add_rax_rbx() -> bytes:
        """ADD RAX, RBX → 48 01 D8"""
        return b"\x48\x01\xD8"

    @staticmethod
    def sub_rax_rbx() -> bytes:
        """SUB RAX, RBX → 48 29 D8"""
        return b"\x48\x29\xD8"

    @staticmethod
    def mul_rbx() -> bytes:
        """IMUL RAX, RBX → 48 0F AF C3"""
        return b"\x48\x0F\xAF\xC3"

    @staticmethod
    def cqo() -> bytes:
        """CQO → 48 99 (sign-extend RAX → RDX:RAX)"""
        return b"\x48\x99"

    @staticmethod
    def idiv_rbx() -> bytes:
        """IDIV RBX → 48 F7 FB"""
        return b"\x48\xF7\xFB"

    @staticmethod
    def cmp_rax_rbx() -> bytes:
        """CMP RAX, RBX → 48 39 D8"""
        return b"\x48\x39\xD8"

    @staticmethod
    def sete_al() -> bytes:
        """SETE AL → 0F 94 C0"""
        return b"\x0F\x94\xC0"

    @staticmethod
    def setg_al() -> bytes:
        """SETG AL → 0F 9F C0"""
        return b"\x0F\x9F\xC0"

    @staticmethod
    def setl_al() -> bytes:
        """SETL AL → 0F 9C C0"""
        return b"\x0F\x9C\xC0"

    @staticmethod
    def setne_al() -> bytes:
        """SETNE AL → 0F 95 C0"""
        return b"\x0F\x95\xC0"

    @staticmethod
    def setge_al() -> bytes:
        """SETGE AL → 0F 9D C0"""
        return b"\x0F\x9D\xC0"

    @staticmethod
    def setle_al() -> bytes:
        """SETLE AL → 0F 9E C0"""
        return b"\x0F\x9E\xC0"

    @staticmethod
    def movzx_rax_al() -> bytes:
        """MOVZX RAX, AL → 48 0F B6 C0"""
        return b"\x48\x0F\xB6\xC0"

    @staticmethod
    def xor_rax_rax() -> bytes:
        """XOR RAX, RAX → 48 31 C0"""
        return b"\x48\x31\xC0"

    @staticmethod
    def mov_rax_rbx() -> bytes:
        """MOV RAX, RBX → 48 89 D8"""
        return b"\x48\x89\xD8"

    @staticmethod
    def mov_rdx_rax() -> bytes:
        """MOV RDX, RAX (result = RDX after IDIV for MOD)"""
        return b"\x48\x89\xC2"

    @staticmethod
    def mov_rax_rdx() -> bytes:
        """MOV RAX, RDX → 48 89 D0"""
        return b"\x48\x89\xD0"

    @staticmethod
    def push_rax() -> bytes:
        return b"\x50"

    @staticmethod
    def pop_rax() -> bytes:
        return b"\x58"

    @staticmethod
    def push_rbx() -> bytes:
        return b"\x53"

    @staticmethod
    def pop_rbx() -> bytes:
        return b"\x5B"

    @staticmethod
    def push_rcx() -> bytes:
        return b"\x51"

    @staticmethod
    def pop_rcx() -> bytes:
        return b"\x59"

    @staticmethod
    def push_rdx() -> bytes:
        return b"\x52"

    @staticmethod
    def pop_rdx() -> bytes:
        return b"\x5A"

    @staticmethod
    def mov_rax_imm64(value: int) -> bytes:
        """MOV RAX, imm64 → 48 B8 [8 bytes]"""
        return b"\x48\xB8" + struct.pack("<q", value)

    @staticmethod
    def mov_rbx_imm64(value: int) -> bytes:
        """MOV RBX, imm64 → 48 BB [8 bytes]"""
        return b"\x48\xBB" + struct.pack("<q", value)

    @staticmethod
    def ret() -> bytes:
        return b"\xC3"

    @staticmethod
    def nop() -> bytes:
        return b"\x90"

    @staticmethod
    def jmp_rel32(offset: int = 0) -> bytes:
        """JMP rel32 → E9 [4 bytes offset]"""
        return b"\xE9" + struct.pack("<i", offset)

    @staticmethod
    def jne_rel32(offset: int = 0) -> bytes:
        """JNE rel32 → 0F 85 [4 bytes]"""
        return b"\x0F\x85" + struct.pack("<i", offset)

    @staticmethod
    def je_rel32(offset: int = 0) -> bytes:
        """JE rel32 → 0F 84 [4 bytes]"""
        return b"\x0F\x84" + struct.pack("<i", offset)

    @staticmethod
    def test_rax_rax() -> bytes:
        """TEST RAX, RAX → 48 85 C0"""
        return b"\x48\x85\xC0"

    @staticmethod
    def call_rel32(offset: int = 0) -> bytes:
        """CALL rel32 → E8 [4 bytes offset]"""
        return b"\xE8" + struct.pack("<i", offset)

    # ── AVX SIMD (VEX-encoded, 128-bit XMM) ───────────────

    @staticmethod
    def _vex2(vvvv: int, L: int, pp: int) -> bytes:
        """2-byte VEX prefix: C5 [R/vvvv/L/pp]"""
        byte2 = 0x80 | ((~vvvv & 0x0F) << 3) | ((L & 1) << 2) | (pp & 3)
        return bytes([0xC5, byte2])

    @staticmethod
    def avx_vmovaps_load_xmm0_rax() -> bytes:
        """VMOVAPS XMM0, [RAX] — C5 F8 28 00"""
        return bytes([0xC5, 0xF8, 0x28, 0x00])

    @staticmethod
    def avx_vmovaps_store_rax_xmm0() -> bytes:
        """VMOVAPS [RAX], XMM0 — C5 F8 29 00"""
        return bytes([0xC5, 0xF8, 0x29, 0x00])

    @staticmethod
    def avx_vaddps_xmm0_xmm1_xmm2() -> bytes:
        """VADDPS XMM0, XMM1, XMM2 — C5 F0 58 C2"""
        return bytes([0xC5, 0xF0, 0x58, 0xC2])

    @staticmethod
    def avx_vsubps_xmm0_xmm1_xmm2() -> bytes:
        """VSUBPS XMM0, XMM1, XMM2 — C5 F0 5C C2"""
        return bytes([0xC5, 0xF0, 0x5C, 0xC2])

    @staticmethod
    def avx_vmulps_xmm0_xmm1_xmm2() -> bytes:
        """VMULPS XMM0, XMM1, XMM2 — C5 F0 59 C2"""
        return bytes([0xC5, 0xF0, 0x59, 0xC2])

    @staticmethod
    def avx_vdivps_xmm0_xmm1_xmm2() -> bytes:
        """VDIVPS XMM0, XMM1, XMM2 — C5 F0 5E C2"""
        return bytes([0xC5, 0xF0, 0x5E, 0xC2])

    @staticmethod
    def avx_vminps_xmm0_xmm1_xmm2() -> bytes:
        """VMINPS XMM0, XMM1, XMM2 — C5 F0 5D C2"""
        return bytes([0xC5, 0xF0, 0x5D, 0xC2])

    @staticmethod
    def avx_vmaxps_xmm0_xmm1_xmm2() -> bytes:
        """VMAXPS XMM0, XMM1, XMM2 — C5 F0 5F C2"""
        return bytes([0xC5, 0xF0, 0x5F, 0xC2])

    # ── SSE2 Floating-Point Scalar (double-precision) ──────

    @staticmethod
    def addsd_xmm0_xmm1() -> bytes:
        """ADDSD XMM0, XMM1 — F2 0F 58 C1"""
        return bytes([0xF2, 0x0F, 0x58, 0xC1])

    @staticmethod
    def subsd_xmm0_xmm1() -> bytes:
        """SUBSD XMM0, XMM1 — F2 0F 5C C1"""
        return bytes([0xF2, 0x0F, 0x5C, 0xC1])

    @staticmethod
    def mulsd_xmm0_xmm1() -> bytes:
        """MULSD XMM0, XMM1 — F2 0F 59 C1"""
        return bytes([0xF2, 0x0F, 0x59, 0xC1])

    @staticmethod
    def divsd_xmm0_xmm1() -> bytes:
        """DIVSD XMM0, XMM1 — F2 0F 5E C1"""
        return bytes([0xF2, 0x0F, 0x5E, 0xC1])

    @staticmethod
    def ucomisd_xmm0_xmm1() -> bytes:
        """UCOMISD XMM0, XMM1 — 66 0F 2E C1"""
        return bytes([0x66, 0x0F, 0x2E, 0xC1])

    @staticmethod
    def cvtsi2sd_xmm0_rax() -> bytes:
        """CVTSI2SD XMM0, RAX — F2 48 0F 2A C0"""
        return bytes([0xF2, 0x48, 0x0F, 0x2A, 0xC0])

    @staticmethod
    def cvttsd2si_rax_xmm0() -> bytes:
        """CVTTSD2SI RAX, XMM0 — F2 48 0F 2C C0"""
        return bytes([0xF2, 0x48, 0x0F, 0x2C, 0xC0])

    @staticmethod
    def movsd_xmm0_xmm1() -> bytes:
        """MOVSD XMM0, XMM1 — F2 0F 10 C1"""
        return bytes([0xF2, 0x0F, 0x10, 0xC1])


# ═══════════════════════════════════════════════════════════
# arm64 Machine Code Templates (AArch64)
# ═══════════════════════════════════════════════════════════

class ARM64:
    """Helpers tạo mã ARM64."""

    @staticmethod
    def add_x0_x0_x1() -> bytes:
        """ADD X0, X0, X1"""
        return struct.pack("<I", 0x8B010000)

    @staticmethod
    def sub_x0_x0_x1() -> bytes:
        """SUB X0, X0, X1"""
        return struct.pack("<I", 0xCB010000)

    @staticmethod
    def mul_x0_x0_x1() -> bytes:
        """MUL X0, X0, X1 → 9B017C00"""
        return struct.pack("<I", 0x9B017C00)

    @staticmethod
    def sdiv_x0_x0_x1() -> bytes:
        """SDIV X0, X0, X1 → 9AC10C00"""
        return struct.pack("<I", 0x9AC10C00)

    @staticmethod
    def msub_x0_x2_x1_x0() -> bytes:
        """MSUB X0, X2, X1, X0 — for mod: X0 = X0 - (X0/X1)*X1"""
        return struct.pack("<I", 0x9B018040)

    @staticmethod
    def sdiv_x2_x0_x1() -> bytes:
        """SDIV X2, X0, X1 → 9AC10C02"""
        return struct.pack("<I", 0x9AC10C02)

    @staticmethod
    def cmp_x0_x1() -> bytes:
        """CMP X0, X1 → EB01001F"""
        return struct.pack("<I", 0xEB01001F)

    @staticmethod
    def cset_eq_x0() -> bytes:
        """CSET X0, EQ → 9A9F17E0"""
        return struct.pack("<I", 0x9A9F17E0)

    @staticmethod
    def cset_gt_x0() -> bytes:
        """CSET X0, GT → 9A9FC7E0 (actually CSET X0, GT = CSINC X0, XZR, XZR, LE)"""
        return struct.pack("<I", 0x9A9FC7E0)

    @staticmethod
    def cset_lt_x0() -> bytes:
        """CSET X0, LT → 9A9FA7E0 (CSINC X0, XZR, XZR, GE)"""
        return struct.pack("<I", 0x9A9FA7E0)

    @staticmethod
    def cset_ne_x0() -> bytes:
        """CSET X0, NE → 9A9F07E0 (CSINC X0, XZR, XZR, EQ)"""
        return struct.pack("<I", 0x9A9F07E0)

    @staticmethod
    def cset_ge_x0() -> bytes:
        """CSET X0, GE → 9A9FB7E0 (CSINC X0, XZR, XZR, LT)"""
        return struct.pack("<I", 0x9A9FB7E0)

    @staticmethod
    def cset_le_x0() -> bytes:
        """CSET X0, LE → 9A9FD7E0 (CSINC X0, XZR, XZR, GT)"""
        return struct.pack("<I", 0x9A9FD7E0)

    @staticmethod
    def mov_x0_x1() -> bytes:
        """MOV X0, X1 → AA0103E0"""
        return struct.pack("<I", 0xAA0103E0)

    @staticmethod
    def movz_x0_imm16(imm: int) -> bytes:
        """MOVZ X0, #imm16"""
        instr = 0xD2800000 | ((imm & 0xFFFF) << 5)
        return struct.pack("<I", instr)

    @staticmethod
    def ret() -> bytes:
        """RET → D65F03C0"""
        return struct.pack("<I", 0xD65F03C0)

    @staticmethod
    def nop() -> bytes:
        return struct.pack("<I", 0xD503201F)

    @staticmethod
    def b_imm26(offset: int = 0) -> bytes:
        """B (branch) → 14 | imm26"""
        instr = 0x14000000 | (offset & 0x03FFFFFF)
        return struct.pack("<I", instr)

    @staticmethod
    def bne_imm19(offset: int = 0) -> bytes:
        """B.NE → 54 | imm19<<5 | 1"""
        instr = 0x54000001 | ((offset & 0x7FFFF) << 5)
        return struct.pack("<I", instr)

    @staticmethod
    def beq_imm19(offset: int = 0) -> bytes:
        """B.EQ → 54 | imm19<<5 | 0"""
        instr = 0x54000000 | ((offset & 0x7FFFF) << 5)
        return struct.pack("<I", instr)

    @staticmethod
    def bl_imm26(offset: int = 0) -> bytes:
        """BL (branch-link) → 94 | imm26"""
        instr = 0x94000000 | (offset & 0x03FFFFFF)
        return struct.pack("<I", instr)

    @staticmethod
    def stp_pre_fp_lr() -> bytes:
        """STP X29, X30, [SP, #-16]!"""
        return struct.pack("<I", 0xA9BF7BFD)

    @staticmethod
    def ldp_post_fp_lr() -> bytes:
        """LDP X29, X30, [SP], #16"""
        return struct.pack("<I", 0xA8C17BFD)

    # ── NEON SIMD (128-bit, 4×i32/f32) ────────────────────

    @staticmethod
    def neon_ld1_v0_x0() -> bytes:
        """LD1 {V0.4S}, [X0]"""
        return struct.pack("<I", 0x4C40A800)

    @staticmethod
    def neon_st1_v0_x0() -> bytes:
        """ST1 {V0.4S}, [X0]"""
        return struct.pack("<I", 0x4C00A800)

    @staticmethod
    def neon_add_v0_v1_v2() -> bytes:
        """ADD V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x4EA28420)

    @staticmethod
    def neon_sub_v0_v1_v2() -> bytes:
        """SUB V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x6EA28420)

    @staticmethod
    def neon_mul_v0_v1_v2() -> bytes:
        """MUL V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x4EA29C20)

    @staticmethod
    def neon_fmla_v0_v1_v2() -> bytes:
        """FMLA V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x4E22CC20)

    @staticmethod
    def neon_fdiv_v0_v1_v2() -> bytes:
        """FDIV V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x6E22FC20)

    @staticmethod
    def neon_smin_v0_v1_v2() -> bytes:
        """SMIN V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x4EA26C20)

    @staticmethod
    def neon_smax_v0_v1_v2() -> bytes:
        """SMAX V0.4S, V1.4S, V2.4S"""
        return struct.pack("<I", 0x4EA26420)

    @staticmethod
    def neon_addv_s0_v1() -> bytes:
        """ADDV S0, V1.4S — horizontal sum"""
        return struct.pack("<I", 0x4EB1B820)

    @staticmethod
    def neon_dup_v0_w0() -> bytes:
        """DUP V0.4S, W0 — broadcast"""
        return struct.pack("<I", 0x4E040C00)

    # ── Floating-Point Scalar (double-precision, D-regs) ───

    @staticmethod
    def fadd_d0_d0_d1() -> bytes:
        """FADD D0, D0, D1"""
        return struct.pack("<I", 0x1E612800)

    @staticmethod
    def fsub_d0_d0_d1() -> bytes:
        """FSUB D0, D0, D1"""
        return struct.pack("<I", 0x1E613800)

    @staticmethod
    def fmul_d0_d0_d1() -> bytes:
        """FMUL D0, D0, D1"""
        return struct.pack("<I", 0x1E610800)

    @staticmethod
    def fdiv_d0_d0_d1() -> bytes:
        """FDIV D0, D0, D1"""
        return struct.pack("<I", 0x1E611800)

    @staticmethod
    def fcmp_d0_d1() -> bytes:
        """FCMP D0, D1"""
        return struct.pack("<I", 0x1E612000)

    @staticmethod
    def scvtf_d0_x0() -> bytes:
        """SCVTF D0, X0 — int64 → float64"""
        return struct.pack("<I", 0x9E620000)

    @staticmethod
    def fcvtzs_x0_d0() -> bytes:
        """FCVTZS X0, D0 — float64 → int64 (truncate)"""
        return struct.pack("<I", 0x9E780000)

    @staticmethod
    def fmov_d0_d1() -> bytes:
        """FMOV D0, D1"""
        return struct.pack("<I", 0x1E604020)


# ═══════════════════════════════════════════════════════════
# Loop Vectorizer — Phase 6 SIMD Auto-Vectorization
# ═══════════════════════════════════════════════════════════

@dataclass
class VectorizableLoop:
    """A detected counted loop suitable for SIMD vectorization."""
    start_idx: int          # index of first loop instruction
    end_idx: int            # index past last loop instruction
    induction_var: Optional[VReg] = None
    trip_count: Optional[int] = None
    body_opcodes: list[Opcode] = field(default_factory=list)
    stride: int = 1

    @property
    def vectorizable_body(self) -> bool:
        """Check if loop body contains only vectorizable ops."""
        _VECTORIZABLE = {
            Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL,
            Opcode.Q_LOAD, Opcode.Q_STORE, Opcode.Q_MOVE,
            Opcode.Q_FADD, Opcode.Q_FSUB, Opcode.Q_FMUL,
        }
        return all(op in _VECTORIZABLE for op in self.body_opcodes)


class LoopVectorizer:
    """
    Phase 6 loop auto-vectorizer.

    Detects counted loops (induction var + known trip count) and
    transforms them into vectorized loops using SIMD instructions:
      - ARM64: NEON 128-bit (4×i32 / 4×f32)
      - x86_64: AVX 128-bit (4×f32)

    The vectorized loop processes VECTOR_WIDTH elements per iteration
    with a scalar remainder loop for the tail.

    Minimum vectorization threshold: 16 iterations (avoids pack/unpack
    overhead for tiny loops).
    """

    VECTOR_WIDTH = 4          # 128-bit / 32-bit = 4 lanes
    MIN_TRIP_COUNT = 16       # don't vectorize short loops

    def __init__(self, arch: TargetArch) -> None:
        self.arch = arch

    def analyze(self, instrs: list[QInstruction]) -> list[VectorizableLoop]:
        """Scan instruction stream for vectorizable counted loops."""
        loops: list[VectorizableLoop] = []
        i = 0
        n = len(instrs)

        while i < n:
            # Pattern: LABEL → LOAD(induction) → CMP → JUMP_IF_NOT(exit)
            #          → body → ADD(induction, stride) → JUMP(label)
            if (
                i + 5 < n
                and instrs[i].opcode == Opcode.Q_LABEL
                and instrs[i + 1].opcode == Opcode.Q_LOAD
                and instrs[i + 2].opcode in (Opcode.Q_CMP_LT, Opcode.Q_CMP_LE)
                and instrs[i + 3].opcode == Opcode.Q_JUMP_IF_NOT
            ):
                # Find the back-edge JUMP that closes the loop
                loop_start = i
                j = i + 4
                body_ops = []
                while j < n and instrs[j].opcode != Opcode.Q_JUMP:
                    body_ops.append(instrs[j].opcode)
                    j += 1

                if j < n and instrs[j].opcode == Opcode.Q_JUMP:
                    # Extract trip count if the comparison is against an immediate
                    trip = None
                    cmp_instr = instrs[i + 2]
                    if isinstance(getattr(cmp_instr, 'src2', None), Immediate):
                        trip = int(cmp_instr.src2.value)
                    elif isinstance(getattr(cmp_instr, 'src1', None), Immediate):
                        trip = int(cmp_instr.src1.value)

                    loop = VectorizableLoop(
                        start_idx=loop_start,
                        end_idx=j + 1,
                        induction_var=getattr(instrs[i + 1], 'dest', None),
                        trip_count=trip,
                        body_opcodes=body_ops,
                    )
                    if (
                        loop.vectorizable_body
                        and trip is not None
                        and trip >= self.MIN_TRIP_COUNT
                    ):
                        loops.append(loop)
                    i = j + 1
                    continue
            i += 1

        return loops

    def emit_vectorized_loop(
        self, loop: VectorizableLoop, instrs: list[QInstruction],
    ) -> bytearray:
        """Emit SIMD-vectorized machine code for a detected loop.

        Strategy:
          1. Main SIMD loop: processes VECTOR_WIDTH elements per iteration
          2. Scalar remainder loop: handles trip_count % VECTOR_WIDTH tail

        Returns machine code bytes for the entire vectorized loop.
        """
        buf = bytearray()
        trip = loop.trip_count or 0
        vec_iters = trip // self.VECTOR_WIDTH
        remainder = trip % self.VECTOR_WIDTH

        if self.arch == TargetArch.ARM64:
            buf.extend(self._emit_neon_loop(loop, instrs, vec_iters, remainder))
        else:
            buf.extend(self._emit_avx_loop(loop, instrs, vec_iters, remainder))

        return buf

    def _emit_neon_loop(
        self, loop: VectorizableLoop, instrs: list[QInstruction],
        vec_iters: int, remainder: int,
    ) -> bytearray:
        """Emit ARM64 NEON vectorized loop.

        Register allocation for vectorized loop:
          x9  = loop counter (vector iterations)
          x10 = vector iteration limit
          x11 = base pointer / accumulator
          v0-v3 = SIMD data registers
          v4    = SIMD accumulator
        """
        buf = bytearray()

        # Initialize vector loop counter: x9 = 0, x10 = vec_iters
        buf.extend(struct.pack("<I", 0xD2800009))   # MOVZ X9, #0
        imm = vec_iters & 0xFFFF
        buf.extend(struct.pack("<I", 0xD280000A | (imm << 5)))  # MOVZ X10, #vec_iters

        # Zero the accumulator: MOVI V4.4S, #0
        buf.extend(struct.pack("<I", 0x4F000484))

        # ── Vector loop header (label) ──
        vec_loop_top = len(buf)

        # CMP X9, X10
        buf.extend(struct.pack("<I", 0xEB0A013F))
        # B.GE +skip  (forward branch, patched below)
        bge_patch = len(buf)
        buf.extend(struct.pack("<I", 0x5400000A))   # B.GE placeholder

        # ── Vector loop body: emit SIMD ops for body_opcodes ──
        for op in loop.body_opcodes:
            if op == Opcode.Q_ADD:
                buf.extend(ARM64.neon_add_v0_v1_v2())  # ADD V0.4S, V1.4S, V2.4S
            elif op == Opcode.Q_SUB:
                buf.extend(ARM64.neon_sub_v0_v1_v2())
            elif op == Opcode.Q_MUL:
                buf.extend(ARM64.neon_mul_v0_v1_v2())
            elif op == Opcode.Q_FADD:
                buf.extend(struct.pack("<I", 0x4E21D400))  # FADD V0.4S, V0.4S, V1.4S
            elif op == Opcode.Q_FSUB:
                buf.extend(struct.pack("<I", 0x4EA1D400))  # FSUB V0.4S, V0.4S, V1.4S
            elif op == Opcode.Q_FMUL:
                buf.extend(struct.pack("<I", 0x6E21DC00))  # FMUL V0.4S, V0.4S, V1.4S
            elif op in (Opcode.Q_LOAD, Opcode.Q_STORE, Opcode.Q_MOVE):
                pass  # data movement handled by surrounding context

        # Accumulate: ADD V4.4S, V4.4S, V0.4S
        buf.extend(struct.pack("<I", 0x4EA08484))

        # Increment: ADD X9, X9, #1
        buf.extend(struct.pack("<I", 0x91000529))
        # B vec_loop_top
        back_offset = (vec_loop_top - len(buf)) >> 2
        buf.extend(struct.pack("<I", 0x14000000 | (back_offset & 0x03FFFFFF)))

        # ── Patch forward branch ──
        skip_target = len(buf)
        fwd_offset = (skip_target - bge_patch) >> 2
        struct.pack_into("<I", buf, bge_patch,
                         0x5400000A | ((fwd_offset & 0x7FFFF) << 5))

        # ── Horizontal reduce: ADDV S0, V4.4S ──
        buf.extend(ARM64.neon_addv_s0_v1())  # uses v1 but intent is v4
        # Correct: ADDV S0, V4.4S
        buf[-4:] = struct.pack("<I", 0x4EB1B880)

        # ── Scalar remainder loop ──
        if remainder > 0:
            imm_rem = remainder & 0xFFFF
            buf.extend(struct.pack("<I", 0xD2800009))   # MOVZ X9, #0
            buf.extend(struct.pack("<I", 0xD280000A | (imm_rem << 5)))  # MOVZ X10, #rem

            rem_loop_top = len(buf)
            buf.extend(struct.pack("<I", 0xEB0A013F))   # CMP X9, X10
            bge_rem_patch = len(buf)
            buf.extend(struct.pack("<I", 0x5400000A))   # B.GE placeholder

            # Scalar body: single iteration ops
            for op in loop.body_opcodes:
                if op == Opcode.Q_ADD:
                    buf.extend(ARM64.add_x0_x0_x1())
                elif op == Opcode.Q_SUB:
                    buf.extend(ARM64.sub_x0_x0_x1())
                elif op == Opcode.Q_MUL:
                    buf.extend(ARM64.mul_x0_x0_x1())
                elif op in (Opcode.Q_LOAD, Opcode.Q_STORE, Opcode.Q_MOVE):
                    pass

            buf.extend(struct.pack("<I", 0x91000529))   # ADD X9, X9, #1
            back_rem = (rem_loop_top - len(buf)) >> 2
            buf.extend(struct.pack("<I", 0x14000000 | (back_rem & 0x03FFFFFF)))

            # Patch remainder branch
            skip_rem = len(buf)
            fwd_rem = (skip_rem - bge_rem_patch) >> 2
            struct.pack_into("<I", buf, bge_rem_patch,
                             0x5400000A | ((fwd_rem & 0x7FFFF) << 5))

        return buf

    def _emit_avx_loop(
        self, loop: VectorizableLoop, instrs: list[QInstruction],
        vec_iters: int, remainder: int,
    ) -> bytearray:
        """Emit x86_64 AVX vectorized loop.

        Register allocation:
          RCX = loop counter
          RDX = limit
          XMM0-XMM2 = SIMD data
          XMM3 = accumulator
        """
        buf = bytearray()

        # XOR RCX, RCX (counter = 0)
        buf.extend(b"\x48\x31\xC9")
        # MOV RDX, vec_iters
        buf.extend(b"\x48\xBA" + struct.pack("<q", vec_iters))

        # VXORPS XMM3, XMM3, XMM3 (zero accumulator)
        buf.extend(bytes([0xC5, 0xE0, 0x57, 0xDB]))

        # ── Vector loop ──
        vec_loop_top = len(buf)

        # CMP RCX, RDX
        buf.extend(b"\x48\x39\xD1")
        # JGE skip (patched)
        jge_patch = len(buf)
        buf.extend(b"\x0F\x8D\x00\x00\x00\x00")

        # Body
        for op in loop.body_opcodes:
            if op == Opcode.Q_ADD:
                buf.extend(X86_64.avx_vaddps_xmm0_xmm1_xmm2())
            elif op == Opcode.Q_SUB:
                buf.extend(X86_64.avx_vsubps_xmm0_xmm1_xmm2())
            elif op == Opcode.Q_MUL:
                buf.extend(X86_64.avx_vmulps_xmm0_xmm1_xmm2())
            elif op in (Opcode.Q_LOAD, Opcode.Q_STORE, Opcode.Q_MOVE):
                pass

        # Accumulate: VADDPS XMM3, XMM3, XMM0
        buf.extend(bytes([0xC5, 0xE0, 0x58, 0xD8]))

        # INC RCX
        buf.extend(b"\x48\xFF\xC1")
        # JMP vec_loop_top
        jmp_back = len(buf)
        rel = vec_loop_top - (jmp_back + 5)
        buf.extend(b"\xE9" + struct.pack("<i", rel))

        # Patch JGE
        skip_target = len(buf)
        struct.pack_into("<i", buf, jge_patch + 2, skip_target - (jge_patch + 6))

        # ── Scalar remainder ──
        if remainder > 0:
            buf.extend(b"\x48\x31\xC9")          # XOR RCX, RCX
            buf.extend(b"\x48\xBA" + struct.pack("<q", remainder))  # MOV RDX, rem

            rem_top = len(buf)
            buf.extend(b"\x48\x39\xD1")          # CMP RCX, RDX
            jge_rem_patch = len(buf)
            buf.extend(b"\x0F\x8D\x00\x00\x00\x00")  # JGE skip

            for op in loop.body_opcodes:
                if op == Opcode.Q_ADD:
                    buf.extend(X86_64.add_rax_rbx())
                elif op == Opcode.Q_SUB:
                    buf.extend(X86_64.sub_rax_rbx())
                elif op == Opcode.Q_MUL:
                    buf.extend(X86_64.mul_rbx())
                elif op in (Opcode.Q_LOAD, Opcode.Q_STORE, Opcode.Q_MOVE):
                    pass

            buf.extend(b"\x48\xFF\xC1")          # INC RCX
            jmp_rem = len(buf)
            rel_rem = rem_top - (jmp_rem + 5)
            buf.extend(b"\xE9" + struct.pack("<i", rel_rem))

            # Patch JGE
            skip_rem = len(buf)
            struct.pack_into("<i", buf, jge_rem_patch + 2,
                             skip_rem - (jge_rem_patch + 6))

        return buf


# ═══════════════════════════════════════════════════════════
# Intrinsic Function Registry — Grade S Performance Functions
# ═══════════════════════════════════════════════════════════

# These intrinsics bypass safe-mode bounds checking and map directly
# to SIMD machine instructions. They are the "muscle" of Vir.
GRADE_S_INTRINSICS: dict[str, dict] = {
    "simd_add": {
        "desc": "SIMD 4-wide add (NEON ADD.4S / AVX VADDPS)",
        "arm64": ARM64.neon_add_v0_v1_v2,
        "x86_64": X86_64.avx_vaddps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "simd_sub": {
        "desc": "SIMD 4-wide subtract",
        "arm64": ARM64.neon_sub_v0_v1_v2,
        "x86_64": X86_64.avx_vsubps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "simd_mul": {
        "desc": "SIMD 4-wide multiply",
        "arm64": ARM64.neon_mul_v0_v1_v2,
        "x86_64": X86_64.avx_vmulps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "simd_fma": {
        "desc": "SIMD fused multiply-add (V += A * B)",
        "arm64": ARM64.neon_fmla_v0_v1_v2,
        "x86_64": lambda: X86_64.avx_vmulps_xmm0_xmm1_xmm2()
                         + X86_64.avx_vaddps_xmm0_xmm1_xmm2(),
        "grade": "S",
    },
    "simd_div": {
        "desc": "SIMD 4-wide divide",
        "arm64": ARM64.neon_fdiv_v0_v1_v2,
        "x86_64": X86_64.avx_vdivps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "simd_load": {
        "desc": "SIMD aligned vector load (128-bit)",
        "arm64": ARM64.neon_ld1_v0_x0,
        "x86_64": X86_64.avx_vmovaps_load_xmm0_rax,
        "grade": "S",
    },
    "simd_store": {
        "desc": "SIMD aligned vector store (128-bit)",
        "arm64": ARM64.neon_st1_v0_x0,
        "x86_64": X86_64.avx_vmovaps_store_rax_xmm0,
        "grade": "S",
    },
    "simd_splat": {
        "desc": "SIMD broadcast scalar to all lanes",
        "arm64": ARM64.neon_dup_v0_w0,
        "x86_64": X86_64.nop,  # requires VBROADCASTSS
        "grade": "S",
    },
    "simd_reduce_sum": {
        "desc": "SIMD horizontal sum (reduce 4 lanes → scalar)",
        "arm64": ARM64.neon_addv_s0_v1,
        "x86_64": X86_64.nop,  # requires HADDPS chain
        "grade": "S",
    },
    "simd_min": {
        "desc": "SIMD 4-wide element-wise minimum",
        "arm64": ARM64.neon_smin_v0_v1_v2,
        "x86_64": X86_64.avx_vminps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "simd_max": {
        "desc": "SIMD 4-wide element-wise maximum",
        "arm64": ARM64.neon_smax_v0_v1_v2,
        "x86_64": X86_64.avx_vmaxps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
    "matmul": {
        "desc": "NEON-tiled matrix multiply (GEMM micro-kernel)",
        "arm64": ARM64.neon_fmla_v0_v1_v2,  # inner kernel uses FMLA
        "x86_64": X86_64.avx_vmulps_xmm0_xmm1_xmm2,
        "grade": "S",
    },
}


def emit_intrinsic(name: str, arch: TargetArch) -> bytes:
    """Emit machine code for a Grade S intrinsic function."""
    entry = GRADE_S_INTRINSICS.get(name)
    if entry is None:
        if arch == TargetArch.ARM64:
            return ARM64.nop()
        return X86_64.nop()
    key = "arm64" if arch == TargetArch.ARM64 else "x86_64"
    fn = entry[key]
    return fn()


# ═══════════════════════════════════════════════════════════
# Code Generator
# ═══════════════════════════════════════════════════════════

class CodeGenerator:
    """
    Dịch QModule thành mã máy đa biến thể (multi-version).

    Mỗi Q_PATCH_POINT tạo ra 1 CodeVariant gồm 2 bản:
    - safe_code: thực hiện qua stack
    - fast_code: thực hiện trực tiếp trên thanh ghi

    CostModel integration: estimates cycle cost per variant for
    runtime decision-making.
    """

    def __init__(self, arch: TargetArch = TargetArch.X86_64, cost_model=None) -> None:
        self.arch = arch
        self.variants: list[CodeVariant] = []
        self.reg_alloc_results: dict[str, "RegAllocResult"] = {}
        self.vectorizer = LoopVectorizer(arch)
        # Lazy import to avoid circular deps
        if cost_model is None:
            from src.ir.cost_model.cost_model import CostModel
            arch_str = "arm64" if arch == TargetArch.ARM64 else "x86_64"
            self.cost_model = CostModel(arch_str)
        else:
            self.cost_model = cost_model

    def generate(self, module: QModule) -> list[CodeVariant]:
        """Dịch toàn bộ QModule → danh sách CodeVariant."""
        from src.ir.registers.linear_scan import LinearScanAllocator

        self.variants.clear()
        self.reg_alloc_results.clear()

        arch_str = "arm64" if self.arch == TargetArch.ARM64 else "x86_64"
        allocator = LinearScanAllocator(arch=arch_str)

        for func in module.functions:
            # Run register allocation per function
            ra_result = allocator.allocate(func)
            self.reg_alloc_results[func.name] = ra_result
            # Insert spill/reload code if needed
            allocator.rewrite(func, ra_result)
            self._generate_function(func)

        return self.variants

    def _generate_function(self, func: QFunction) -> None:
        """Duyệt instructions, tạo variant cho mỗi PATCH_POINT."""
        # Phân nhóm instructions theo patch-point
        current_instrs: list[QInstruction] = []

        for instr in func.body:
            if instr.opcode == Opcode.Q_PATCH_POINT:
                # Tạo variant cho nhóm instructions hiện tại
                if current_instrs:
                    variant = self._build_variant(
                        patch_id=instr.patch_id or f"PATCH_{id(instr)}",
                        instrs=current_instrs,
                    )
                    self.variants.append(variant)
                current_instrs = []
            else:
                current_instrs.append(instr)

        # Nếu còn instructions sau patch-point cuối → tạo variant mặc định
        if current_instrs:
            variant = self._build_variant(
                patch_id=f"FUNC_{func.name}_TAIL",
                instrs=current_instrs,
            )
            self.variants.append(variant)

    def _build_variant(self, patch_id: str, instrs: list[QInstruction]) -> CodeVariant:
        """Tạo 2 bản mã cho 1 nhóm instructions, with cost estimates.

        The fast path attempts SIMD vectorization for detected loops.
        """
        safe = self._codegen_safe(instrs)

        # Phase 6: attempt SIMD vectorization for the fast path
        vec_loops = self.vectorizer.analyze(instrs)
        if vec_loops:
            fast_buf = bytearray()
            prev_end = 0
            for vloop in vec_loops:
                # Emit non-loop instructions before this loop (scalar)
                pre_instrs = instrs[prev_end:vloop.start_idx]
                if pre_instrs:
                    pre_code = self._codegen_fast(pre_instrs)
                    fast_buf.extend(pre_code.bytes_)
                # Emit vectorized loop
                fast_buf.extend(
                    self.vectorizer.emit_vectorized_loop(vloop, instrs)
                )
                prev_end = vloop.end_idx
            # Emit remaining instructions after last loop
            if prev_end < len(instrs):
                tail = self._codegen_fast(instrs[prev_end:])
                fast_buf.extend(tail.bytes_)
            fast = MachineCode(bytes_=fast_buf, arch=self.arch)
        else:
            fast = self._codegen_fast(instrs)

        # Estimate costs using the cost model
        safe_overhead = sum(
            self.cost_model.spill.total
            for i in instrs
            if i.opcode not in (Opcode.Q_LABEL, Opcode.Q_NOP, Opcode.Q_PATCH_POINT)
        )
        safe_cost = self.cost_model.block_cost(instrs) + safe_overhead
        fast_cost = self.cost_model.block_cost(instrs)
        # SIMD vectorization reduces fast cost by vector width factor
        if vec_loops:
            fast_cost /= LoopVectorizer.VECTOR_WIDTH
        speedup = safe_cost / fast_cost if fast_cost > 0 else 1.0

        return CodeVariant(
            patch_id=patch_id, safe_code=safe, fast_code=fast,
            safe_cost=safe_cost, fast_cost=fast_cost, speedup=speedup,
        )

    # ── Bản A: Safe (Stack-based) ──────────────────────────
    def _codegen_safe(self, instrs: list[QInstruction]) -> MachineCode:
        buf = bytearray()
        labels: dict[int, int] = {}      # label_id → byte offset
        fixups: list[tuple[int, int, bool]] = []  # (patch_offset, label_id, is_cond)

        if self.arch == TargetArch.X86_64:
            for instr in instrs:
                match instr.opcode:
                    case Opcode.Q_LOAD:
                        if isinstance(instr.src1, Immediate):
                            buf.extend(X86_64.mov_rax_imm64(int(instr.src1.value)))
                            buf.extend(X86_64.push_rax())
                    case Opcode.Q_STORE | Opcode.Q_MOVE:
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_ADD:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.add_rax_rbx())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_SUB:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.sub_rax_rbx())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_MUL:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.mul_rbx())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_DIV:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cqo())
                        buf.extend(X86_64.idiv_rbx())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_MOD:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cqo())
                        buf.extend(X86_64.idiv_rbx())
                        # remainder in RDX
                        buf.extend(X86_64.push_rdx())
                    case Opcode.Q_CMP_EQ:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.sete_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_CMP_GT:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setg_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_CMP_LT:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setl_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_CMP_NE:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setne_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_CMP_GE:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setge_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_CMP_LE:
                        buf.extend(X86_64.pop_rbx())
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setle_al())
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_INPUT:
                        buf.extend(X86_64.nop())  # handled by runtime
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_LOAD_STRING:
                        buf.extend(X86_64.nop())  # string ref handled by runtime
                        buf.extend(X86_64.push_rax())
                    case Opcode.Q_LABEL:
                        if instr.patch_id is not None:
                            labels[hash(instr.patch_id)] = len(buf)
                    case Opcode.Q_JUMP:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf) + 1, hash(instr.src1.name), False))
                        buf.extend(X86_64.jmp_rel32(0))
                    case Opcode.Q_JUMP_IF:
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.test_rax_rax())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf) + 2, hash(lbl.name), True))
                        buf.extend(X86_64.jne_rel32(0))
                    case Opcode.Q_JUMP_IF_NOT:
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.test_rax_rax())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf) + 2, hash(lbl.name), True))
                        buf.extend(X86_64.je_rel32(0))
                    case Opcode.Q_CALL:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf) + 1, hash(instr.src1.name), False))
                        buf.extend(X86_64.call_rel32(0))
                    case Opcode.Q_PRINT:
                        # No-op in safe code (handled by runtime)
                        buf.extend(X86_64.nop())
                    case Opcode.Q_RET:
                        buf.extend(X86_64.pop_rax())
                        buf.extend(X86_64.ret())
                    case Opcode.Q_HALT:
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.ret())
                    # SIMD / AVX opcodes
                    case Opcode.Q_VLOAD:
                        buf.extend(X86_64.avx_vmovaps_load_xmm0_rax())
                    case Opcode.Q_VSTORE:
                        buf.extend(X86_64.avx_vmovaps_store_rax_xmm0())
                    case Opcode.Q_VADD:
                        buf.extend(X86_64.avx_vaddps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VSUB:
                        buf.extend(X86_64.avx_vsubps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMUL:
                        buf.extend(X86_64.avx_vmulps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VFMA:
                        # No FMA3 in basic AVX, use MUL+ADD
                        buf.extend(X86_64.avx_vmulps_xmm0_xmm1_xmm2())
                        buf.extend(X86_64.avx_vaddps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VDIV:
                        buf.extend(X86_64.avx_vdivps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMIN:
                        buf.extend(X86_64.avx_vminps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMAX:
                        buf.extend(X86_64.avx_vmaxps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VREDUCE | Opcode.Q_VSPLAT | Opcode.Q_VPERM:
                        buf.extend(X86_64.nop())  # complex ops — NOP in safe path
                    # FP scalar opcodes (SSE2 double)
                    case Opcode.Q_FADD:
                        buf.extend(X86_64.addsd_xmm0_xmm1())
                    case Opcode.Q_FSUB:
                        buf.extend(X86_64.subsd_xmm0_xmm1())
                    case Opcode.Q_FMUL:
                        buf.extend(X86_64.mulsd_xmm0_xmm1())
                    case Opcode.Q_FDIV:
                        buf.extend(X86_64.divsd_xmm0_xmm1())
                    case Opcode.Q_FCMP_EQ | Opcode.Q_FCMP_LT | Opcode.Q_FCMP_GT:
                        buf.extend(X86_64.ucomisd_xmm0_xmm1())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.sete_al())
                    case Opcode.Q_FCVT_I2F:
                        buf.extend(X86_64.cvtsi2sd_xmm0_rax())
                    case Opcode.Q_FCVT_F2I:
                        buf.extend(X86_64.cvttsd2si_rax_xmm0())
                    case Opcode.Q_FLOAD:
                        buf.extend(X86_64.nop())  # FP load handled by runtime
                    case Opcode.Q_FSTORE:
                        buf.extend(X86_64.nop())  # FP store handled by runtime
                    case Opcode.Q_FMOVE:
                        buf.extend(X86_64.movsd_xmm0_xmm1())
                    case _:
                        buf.extend(X86_64.nop())
        else:
            for instr in instrs:
                match instr.opcode:
                    case Opcode.Q_LOAD:
                        if isinstance(instr.src1, Immediate):
                            buf.extend(ARM64.movz_x0_imm16(int(instr.src1.value) & 0xFFFF))
                            # STP X0, XZR, [SP, #-16]!  (push X0)
                            buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_ADD:
                        # pop b → X1, pop a → X0, add, push
                        buf.extend(struct.pack("<I", 0xA8C103E1))  # LDP X1, XZR, [SP], #16
                        buf.extend(struct.pack("<I", 0xA8C103E0))  # LDP X0, XZR, [SP], #16
                        buf.extend(ARM64.add_x0_x0_x1())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))  # push X0
                    case Opcode.Q_SUB:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.sub_x0_x0_x1())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_MUL:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.mul_x0_x0_x1())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_DIV:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.sdiv_x0_x0_x1())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_MOD:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.sdiv_x2_x0_x1())
                        buf.extend(ARM64.msub_x0_x2_x1_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_EQ:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_eq_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_GT:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_gt_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_LT:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_lt_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_NE:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_ne_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_GE:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_ge_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_CMP_LE:
                        buf.extend(struct.pack("<I", 0xA8C103E1))
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_le_x0())
                        buf.extend(struct.pack("<I", 0xA9BF03E0))
                    case Opcode.Q_INPUT:
                        buf.extend(ARM64.nop())  # handled by runtime
                        buf.extend(struct.pack("<I", 0xA9BF03E0))  # push X0
                    case Opcode.Q_LOAD_STRING:
                        buf.extend(ARM64.nop())  # string ref handled by runtime
                        buf.extend(struct.pack("<I", 0xA9BF03E0))  # push X0
                    case Opcode.Q_LABEL:
                        if instr.patch_id is not None:
                            labels[hash(instr.patch_id)] = len(buf)
                    case Opcode.Q_JUMP:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf), hash(instr.src1.name), False))
                        buf.extend(ARM64.b_imm26(0))
                    case Opcode.Q_RET:
                        # pop X0, ret
                        buf.extend(struct.pack("<I", 0xA8C103E0))
                        buf.extend(ARM64.ret())
                    case Opcode.Q_HALT:
                        buf.extend(ARM64.movz_x0_imm16(0))
                        buf.extend(ARM64.ret())
                    # SIMD / NEON opcodes
                    case Opcode.Q_VLOAD:
                        buf.extend(ARM64.neon_ld1_v0_x0())
                    case Opcode.Q_VSTORE:
                        buf.extend(ARM64.neon_st1_v0_x0())
                    case Opcode.Q_VADD:
                        buf.extend(ARM64.neon_add_v0_v1_v2())
                    case Opcode.Q_VSUB:
                        buf.extend(ARM64.neon_sub_v0_v1_v2())
                    case Opcode.Q_VMUL:
                        buf.extend(ARM64.neon_mul_v0_v1_v2())
                    case Opcode.Q_VFMA:
                        buf.extend(ARM64.neon_fmla_v0_v1_v2())
                    case Opcode.Q_VDIV:
                        buf.extend(ARM64.neon_fdiv_v0_v1_v2())
                    case Opcode.Q_VMIN:
                        buf.extend(ARM64.neon_smin_v0_v1_v2())
                    case Opcode.Q_VMAX:
                        buf.extend(ARM64.neon_smax_v0_v1_v2())
                    case Opcode.Q_VREDUCE:
                        buf.extend(ARM64.neon_addv_s0_v1())
                    case Opcode.Q_VSPLAT:
                        buf.extend(ARM64.neon_dup_v0_w0())
                    case Opcode.Q_VPERM:
                        buf.extend(ARM64.nop())  # complex permute — NOP in safe
                    # FP scalar opcodes (ARM64 double)
                    case Opcode.Q_FADD:
                        buf.extend(ARM64.fadd_d0_d0_d1())
                    case Opcode.Q_FSUB:
                        buf.extend(ARM64.fsub_d0_d0_d1())
                    case Opcode.Q_FMUL:
                        buf.extend(ARM64.fmul_d0_d0_d1())
                    case Opcode.Q_FDIV:
                        buf.extend(ARM64.fdiv_d0_d0_d1())
                    case Opcode.Q_FCMP_EQ | Opcode.Q_FCMP_LT | Opcode.Q_FCMP_GT:
                        buf.extend(ARM64.fcmp_d0_d1())
                        buf.extend(ARM64.cset_eq_x0())
                    case Opcode.Q_FCVT_I2F:
                        buf.extend(ARM64.scvtf_d0_x0())
                    case Opcode.Q_FCVT_F2I:
                        buf.extend(ARM64.fcvtzs_x0_d0())
                    case Opcode.Q_FLOAD:
                        buf.extend(ARM64.nop())  # FP load handled by runtime
                    case Opcode.Q_FSTORE:
                        buf.extend(ARM64.nop())  # FP store handled by runtime
                    case Opcode.Q_FMOVE:
                        buf.extend(ARM64.fmov_d0_d1())
                    case _:
                        buf.extend(ARM64.nop())

        # Back-patch branch offsets
        self._backpatch(buf, labels, fixups)

        return MachineCode(bytes_=buf, arch=self.arch)

    # ── Bản B: Fast (Register-direct) ─────────────────────
    def _codegen_fast(self, instrs: list[QInstruction]) -> MachineCode:
        buf = bytearray()
        labels: dict[int, int] = {}
        fixups: list[tuple[int, int, bool]] = []

        if self.arch == TargetArch.X86_64:
            for instr in instrs:
                match instr.opcode:
                    case Opcode.Q_LOAD:
                        if isinstance(instr.src1, Immediate):
                            buf.extend(X86_64.mov_rax_imm64(int(instr.src1.value)))
                    case Opcode.Q_STORE | Opcode.Q_MOVE:
                        buf.extend(X86_64.mov_rax_rbx())
                    case Opcode.Q_ADD:
                        buf.extend(X86_64.add_rax_rbx())
                    case Opcode.Q_SUB:
                        buf.extend(X86_64.sub_rax_rbx())
                    case Opcode.Q_MUL:
                        buf.extend(X86_64.mul_rbx())
                    case Opcode.Q_DIV:
                        buf.extend(X86_64.cqo())
                        buf.extend(X86_64.idiv_rbx())
                    case Opcode.Q_MOD:
                        buf.extend(X86_64.cqo())
                        buf.extend(X86_64.idiv_rbx())
                        buf.extend(X86_64.mov_rax_rdx())
                    case Opcode.Q_CMP_EQ:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.sete_al())
                    case Opcode.Q_CMP_GT:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setg_al())
                    case Opcode.Q_CMP_LT:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setl_al())
                    case Opcode.Q_CMP_NE:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setne_al())
                    case Opcode.Q_CMP_GE:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setge_al())
                    case Opcode.Q_CMP_LE:
                        buf.extend(X86_64.cmp_rax_rbx())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.setle_al())
                    case Opcode.Q_INPUT:
                        buf.extend(X86_64.nop())
                    case Opcode.Q_LOAD_STRING:
                        buf.extend(X86_64.nop())
                    case Opcode.Q_LABEL:
                        if instr.patch_id is not None:
                            labels[hash(instr.patch_id)] = len(buf)
                    case Opcode.Q_JUMP:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf) + 1, hash(instr.src1.name), False))
                        buf.extend(X86_64.jmp_rel32(0))
                    case Opcode.Q_JUMP_IF:
                        buf.extend(X86_64.test_rax_rax())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf) + 2, hash(lbl.name), True))
                        buf.extend(X86_64.jne_rel32(0))
                    case Opcode.Q_JUMP_IF_NOT:
                        buf.extend(X86_64.test_rax_rax())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf) + 2, hash(lbl.name), True))
                        buf.extend(X86_64.je_rel32(0))
                    case Opcode.Q_CALL:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf) + 1, hash(instr.src1.name), False))
                        buf.extend(X86_64.call_rel32(0))
                    case Opcode.Q_PRINT:
                        buf.extend(X86_64.nop())
                    case Opcode.Q_RET:
                        buf.extend(X86_64.ret())
                    case Opcode.Q_HALT:
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.ret())
                    # SIMD / AVX opcodes (fast path)
                    case Opcode.Q_VLOAD:
                        buf.extend(X86_64.avx_vmovaps_load_xmm0_rax())
                    case Opcode.Q_VSTORE:
                        buf.extend(X86_64.avx_vmovaps_store_rax_xmm0())
                    case Opcode.Q_VADD:
                        buf.extend(X86_64.avx_vaddps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VSUB:
                        buf.extend(X86_64.avx_vsubps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMUL:
                        buf.extend(X86_64.avx_vmulps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VFMA:
                        buf.extend(X86_64.avx_vmulps_xmm0_xmm1_xmm2())
                        buf.extend(X86_64.avx_vaddps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VDIV:
                        buf.extend(X86_64.avx_vdivps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMIN:
                        buf.extend(X86_64.avx_vminps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VMAX:
                        buf.extend(X86_64.avx_vmaxps_xmm0_xmm1_xmm2())
                    case Opcode.Q_VREDUCE | Opcode.Q_VSPLAT | Opcode.Q_VPERM:
                        buf.extend(X86_64.nop())
                    # FP scalar opcodes (fast path)
                    case Opcode.Q_FADD:
                        buf.extend(X86_64.addsd_xmm0_xmm1())
                    case Opcode.Q_FSUB:
                        buf.extend(X86_64.subsd_xmm0_xmm1())
                    case Opcode.Q_FMUL:
                        buf.extend(X86_64.mulsd_xmm0_xmm1())
                    case Opcode.Q_FDIV:
                        buf.extend(X86_64.divsd_xmm0_xmm1())
                    case Opcode.Q_FCMP_EQ | Opcode.Q_FCMP_LT | Opcode.Q_FCMP_GT:
                        buf.extend(X86_64.ucomisd_xmm0_xmm1())
                        buf.extend(X86_64.xor_rax_rax())
                        buf.extend(X86_64.sete_al())
                    case Opcode.Q_FCVT_I2F:
                        buf.extend(X86_64.cvtsi2sd_xmm0_rax())
                    case Opcode.Q_FCVT_F2I:
                        buf.extend(X86_64.cvttsd2si_rax_xmm0())
                    case Opcode.Q_FLOAD:
                        buf.extend(X86_64.nop())
                    case Opcode.Q_FSTORE:
                        buf.extend(X86_64.nop())
                    case Opcode.Q_FMOVE:
                        buf.extend(X86_64.movsd_xmm0_xmm1())
                    case _:
                        buf.extend(X86_64.nop())
        else:
            # ARM64 fast path (register-direct)
            for instr in instrs:
                match instr.opcode:
                    case Opcode.Q_LOAD:
                        if isinstance(instr.src1, Immediate):
                            buf.extend(ARM64.movz_x0_imm16(int(instr.src1.value) & 0xFFFF))
                    case Opcode.Q_STORE | Opcode.Q_MOVE:
                        buf.extend(ARM64.mov_x0_x1())
                    case Opcode.Q_ADD:
                        buf.extend(ARM64.add_x0_x0_x1())
                    case Opcode.Q_SUB:
                        buf.extend(ARM64.sub_x0_x0_x1())
                    case Opcode.Q_MUL:
                        buf.extend(ARM64.mul_x0_x0_x1())
                    case Opcode.Q_DIV:
                        buf.extend(ARM64.sdiv_x0_x0_x1())
                    case Opcode.Q_MOD:
                        buf.extend(ARM64.sdiv_x2_x0_x1())
                        buf.extend(ARM64.msub_x0_x2_x1_x0())
                    case Opcode.Q_CMP_EQ:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_eq_x0())
                    case Opcode.Q_CMP_GT:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_gt_x0())
                    case Opcode.Q_CMP_LT:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_lt_x0())
                    case Opcode.Q_CMP_NE:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_ne_x0())
                    case Opcode.Q_CMP_GE:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_ge_x0())
                    case Opcode.Q_CMP_LE:
                        buf.extend(ARM64.cmp_x0_x1())
                        buf.extend(ARM64.cset_le_x0())
                    case Opcode.Q_INPUT:
                        buf.extend(ARM64.nop())
                    case Opcode.Q_LOAD_STRING:
                        buf.extend(ARM64.nop())
                    case Opcode.Q_LABEL:
                        if instr.patch_id is not None:
                            labels[hash(instr.patch_id)] = len(buf)
                    case Opcode.Q_JUMP:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf), hash(instr.src1.name), False))
                        buf.extend(ARM64.b_imm26(0))
                    case Opcode.Q_JUMP_IF:
                        buf.extend(ARM64.cmp_x0_x1())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf), hash(lbl.name), True))
                        buf.extend(ARM64.bne_imm19(0))
                    case Opcode.Q_JUMP_IF_NOT:
                        buf.extend(ARM64.cmp_x0_x1())
                        lbl = instr.src2 if hasattr(instr, 'src2') and isinstance(instr.src2, Label) else None
                        if lbl:
                            fixups.append((len(buf), hash(lbl.name), True))
                        buf.extend(ARM64.beq_imm19(0))
                    case Opcode.Q_CALL:
                        if isinstance(instr.src1, Label):
                            fixups.append((len(buf), hash(instr.src1.name), False))
                        buf.extend(ARM64.bl_imm26(0))
                    case Opcode.Q_PRINT:
                        buf.extend(ARM64.nop())
                    case Opcode.Q_RET:
                        buf.extend(ARM64.ret())
                    case Opcode.Q_HALT:
                        buf.extend(ARM64.movz_x0_imm16(0))
                        buf.extend(ARM64.ret())
                    # SIMD / NEON opcodes (fast path)
                    case Opcode.Q_VLOAD:
                        buf.extend(ARM64.neon_ld1_v0_x0())
                    case Opcode.Q_VSTORE:
                        buf.extend(ARM64.neon_st1_v0_x0())
                    case Opcode.Q_VADD:
                        buf.extend(ARM64.neon_add_v0_v1_v2())
                    case Opcode.Q_VSUB:
                        buf.extend(ARM64.neon_sub_v0_v1_v2())
                    case Opcode.Q_VMUL:
                        buf.extend(ARM64.neon_mul_v0_v1_v2())
                    case Opcode.Q_VFMA:
                        buf.extend(ARM64.neon_fmla_v0_v1_v2())
                    case Opcode.Q_VDIV:
                        buf.extend(ARM64.neon_fdiv_v0_v1_v2())
                    case Opcode.Q_VMIN:
                        buf.extend(ARM64.neon_smin_v0_v1_v2())
                    case Opcode.Q_VMAX:
                        buf.extend(ARM64.neon_smax_v0_v1_v2())
                    case Opcode.Q_VREDUCE:
                        buf.extend(ARM64.neon_addv_s0_v1())
                    case Opcode.Q_VSPLAT:
                        buf.extend(ARM64.neon_dup_v0_w0())
                    case Opcode.Q_VPERM:
                        buf.extend(ARM64.nop())
                    # FP scalar opcodes (fast path)
                    case Opcode.Q_FADD:
                        buf.extend(ARM64.fadd_d0_d0_d1())
                    case Opcode.Q_FSUB:
                        buf.extend(ARM64.fsub_d0_d0_d1())
                    case Opcode.Q_FMUL:
                        buf.extend(ARM64.fmul_d0_d0_d1())
                    case Opcode.Q_FDIV:
                        buf.extend(ARM64.fdiv_d0_d0_d1())
                    case Opcode.Q_FCMP_EQ | Opcode.Q_FCMP_LT | Opcode.Q_FCMP_GT:
                        buf.extend(ARM64.fcmp_d0_d1())
                        buf.extend(ARM64.cset_eq_x0())
                    case Opcode.Q_FCVT_I2F:
                        buf.extend(ARM64.scvtf_d0_x0())
                    case Opcode.Q_FCVT_F2I:
                        buf.extend(ARM64.fcvtzs_x0_d0())
                    case Opcode.Q_FLOAD:
                        buf.extend(ARM64.nop())
                    case Opcode.Q_FSTORE:
                        buf.extend(ARM64.nop())
                    case Opcode.Q_FMOVE:
                        buf.extend(ARM64.fmov_d0_d1())
                    case _:
                        buf.extend(ARM64.nop())

        self._backpatch(buf, labels, fixups)
        return MachineCode(bytes_=buf, arch=self.arch)

    # ── SRI Emission ──────────────────────────────────────
    def emit_sri(self, module: QModule, entry: str = "main") -> "SRIBinary":
        """Generate code for a QModule and emit as an SRIBinary."""
        from src.backend.formats import (
            SRIBinary, SRISymbol, SRIReloc,
            ARCH_ARM64, ARCH_X86_64,
            SYM_FUNC, FLAG_PIC,
        )

        variants = self.generate(module)
        arch_code = ARCH_ARM64 if self.arch == TargetArch.ARM64 else ARCH_X86_64

        # Concatenate fast_code from all variants into a single code section
        code = bytearray()
        symbols: list[SRISymbol] = []
        entry_offset = 0

        for var in variants:
            offset = len(code)
            mc = var.fast_code
            symbols.append(SRISymbol(
                name=var.patch_id,
                address=offset,
                size=len(mc.bytes_),
                sym_type=SYM_FUNC,
            ))
            if var.patch_id == f"FUNC_{entry}_TAIL" or var.patch_id == entry:
                entry_offset = offset
            code.extend(mc.bytes_)

        return SRIBinary(
            arch=arch_code,
            flags=FLAG_PIC,
            entry_point=entry_offset,
            code=bytes(code),
            symbols=symbols,
        )

    # ── Back-patching ──────────────────────────────────────
    def _backpatch(
        self,
        buf: bytearray,
        labels: dict[int, int],
        fixups: list[tuple[int, int, bool]],
    ) -> None:
        """Resolve branch offsets in the emitted buffer."""
        for patch_offset, label_id, _is_cond in fixups:
            target = labels.get(label_id)
            if target is None:
                continue

            if self.arch == TargetArch.ARM64:
                byte_offset = target - patch_offset
                orig = struct.unpack_from("<I", buf, patch_offset)[0]
                if _is_cond:
                    imm19 = (byte_offset >> 2) & 0x7FFFF
                    orig = (orig & ~(0x7FFFF << 5)) | (imm19 << 5)
                else:
                    imm26 = (byte_offset >> 2) & 0x03FFFFFF
                    orig = (orig & ~0x03FFFFFF) | imm26
                struct.pack_into("<I", buf, patch_offset, orig)
            else:
                # x86_64: rel32 field at patch_offset, instruction end = patch_offset + 4
                instr_end = patch_offset + 4
                rel = target - instr_end
                struct.pack_into("<i", buf, patch_offset, rel)
