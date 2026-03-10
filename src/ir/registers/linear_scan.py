"""
linear_scan.py – Linear Scan Register Allocator
=================================================
Maps virtual registers (infinite) to physical registers (finite)
using the classic Linear Scan algorithm (Poletto & Sarkar, 1999).

Pipeline:
  1. Compute live intervals for each VReg
  2. Sort intervals by start position
  3. Walk intervals left-to-right, assigning physical registers
  4. Spill the interval with the furthest endpoint when out of registers
  5. Emit spill/reload instructions for spilled VRegs

Supports both ARM64 (X0-X15, V0-V7) and x86_64 (RAX-R15, XMM0-XMM7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    VReg,
)


# ═══════════════════════════════════════════════════════════
# Live Interval
# ═══════════════════════════════════════════════════════════

@dataclass
class LiveInterval:
    """Live range of a virtual register: [start, end]."""
    vreg: int               # VReg.index
    start: int              # first definition (instruction index)
    end: int                # last use (instruction index)
    is_vector: bool = False # True for SIMD vregs
    use_positions: list[int] = field(default_factory=list)  # sorted def/use positions

    def next_use_after(self, pos: int) -> int:
        """Return the next use/def position strictly after *pos*, or end+1."""
        for p in self.use_positions:
            if p > pos:
                return p
        return self.end + 1

    def overlaps(self, other: LiveInterval) -> bool:
        return self.start < other.end and other.start < self.end


# ═══════════════════════════════════════════════════════════
# Physical Register Sets — AAPCS64 + Apple arm64
# ═══════════════════════════════════════════════════════════
#
# AAPCS64 conventions (with Apple arm64 amendments):
#
#   GPR caller-saved  : x0-x7 (args/result), x8 (indirect result),
#                        x9-x15 (temporaries)
#   GPR intra-proc    : x16 (IP0), x17 (IP1) — linker/veneer scratch,
#                        NOT freely allocatable by the register allocator
#   GPR platform-rsv  : x18 — reserved on Apple platforms (TBI / platform
#                        pointer), MUST NOT be allocated
#   GPR callee-saved  : x19-x28
#   GPR special       : x29 (FP), x30 (LR), SP
#
#   SIMD/FP caller-saved     : v0-v7 (args/result), v16-v31
#   SIMD/FP callee-saved     : v8-v15 (only low 64 bits guaranteed
#                               by AAPCS64; upper portion clobbered)
#
# The allocatable pools below intentionally exclude IP0/IP1, x18,
# FP, LR, and SP.  Callee-saved GPRs (x19-x28) are available in a
# separate pool so the codegen can emit save/restore prologue when
# they are used.

class PhysReg:
    """Physical register pools per ABI."""

    # ── ARM64 (AAPCS64 + Apple arm64) ──────────────────────

    # Caller-saved GPRs safe for free allocation (x0-x15)
    # x16/x17 (IP0/IP1) excluded — linker scratch
    # x18 excluded — Apple platform-reserved
    ARM64_GP = list(range(16))  # x0..x15

    # Callee-saved GPRs (x19-x28): allocator may use these when
    # caller-saved pool is exhausted; codegen must emit STP/LDP
    # prologue/epilogue when any of these is actually allocated.
    ARM64_GP_CALLEE_SAVED = list(range(19, 29))  # x19..x28

    # SIMD/FP caller-saved (v0-v7) — primary allocation pool
    ARM64_VEC = list(range(8))  # v0..v7

    # SIMD/FP callee-saved (v8-v15, low-64 only per AAPCS64).
    # Safe for scalar double (D-register) usage without clobbering
    # the upper 64 bits (which the caller doesn't rely on already).
    ARM64_VEC_CALLEE_SAVED = list(range(8, 16))  # v8..v15

    # ── x86_64 (System V AMD64 ABI) ────────────────────────

    # RAX(0) RCX(1) RDX(2) RBX(3) RSI(4) RDI(5) R8(6)..R15(13)
    # RSP/RBP excluded
    X86_GP = list(range(14))  # 14 GPRs

    # XMM0-XMM7  (XMM8-XMM15 available but rarely pressure-needed)
    X86_VEC = list(range(8))


# ═══════════════════════════════════════════════════════════
# Allocation Result
# ═══════════════════════════════════════════════════════════

@dataclass
class RegAllocResult:
    """Result of register allocation for one function."""
    # VReg.index → physical register index
    assignment: dict[int, int] = field(default_factory=dict)
    # VReg.index → stack slot index (for spilled regs)
    spilled: dict[int, int] = field(default_factory=dict)
    # Total stack slots needed for spills
    num_spill_slots: int = 0
    # Number of physical GPRs used
    gp_regs_used: int = 0
    # Number of physical vector regs used
    vec_regs_used: int = 0
    # Callee-saved GPRs actually allocated (codegen must save/restore)
    callee_saved_gprs: list[int] = field(default_factory=list)
    # Callee-saved VEC regs actually allocated
    callee_saved_vecs: list[int] = field(default_factory=list)

    def is_spilled(self, vreg_index: int) -> bool:
        return vreg_index in self.spilled

    def phys_reg(self, vreg_index: int) -> int | None:
        return self.assignment.get(vreg_index)


# ═══════════════════════════════════════════════════════════
# SIMD Opcode Set
# ═══════════════════════════════════════════════════════════

_VECTOR_OPCODES = frozenset({
    Opcode.Q_VLOAD, Opcode.Q_VSTORE, Opcode.Q_VADD, Opcode.Q_VSUB,
    Opcode.Q_VMUL, Opcode.Q_VFMA, Opcode.Q_VDIV, Opcode.Q_VMIN,
    Opcode.Q_VMAX, Opcode.Q_VREDUCE, Opcode.Q_VSPLAT, Opcode.Q_VPERM,
})

_FP_OPCODES = frozenset({
    Opcode.Q_FLOAD, Opcode.Q_FSTORE, Opcode.Q_FMOVE,
    Opcode.Q_FADD, Opcode.Q_FSUB, Opcode.Q_FMUL, Opcode.Q_FDIV,
    Opcode.Q_FCMP_EQ, Opcode.Q_FCMP_LT, Opcode.Q_FCMP_GT,
    Opcode.Q_FCVT_I2F, Opcode.Q_FCVT_F2I,
})


# ═══════════════════════════════════════════════════════════
# Linear Scan Register Allocator
# ═══════════════════════════════════════════════════════════

class LinearScanAllocator:
    """
    Linear Scan Register Allocator.

    Algorithm:
      1. Compute live intervals via single forward pass
      2. Sort by start position
      3. Walk left → right, maintain active list of currently-live intervals
      4. When no free register: spill interval ending furthest in the future
      5. Produce allocation map + spill set
    """

    def __init__(self, arch: str = "arm64") -> None:
        self.arch = arch
        if arch == "arm64":
            self.gp_pool = list(PhysReg.ARM64_GP)
            self.gp_callee_saved_pool = list(PhysReg.ARM64_GP_CALLEE_SAVED)
            self.vec_pool = list(PhysReg.ARM64_VEC)
            self.vec_callee_saved_pool = list(PhysReg.ARM64_VEC_CALLEE_SAVED)
        else:
            self.gp_pool = list(PhysReg.X86_GP)
            self.gp_callee_saved_pool = []  # x86_64: handled separately
            self.vec_pool = list(PhysReg.X86_VEC)
            self.vec_callee_saved_pool = []

    # ── Public API ─────────────────────────────────────────

    def allocate(self, func: QFunction) -> RegAllocResult:
        """Run linear scan on a function, return allocation result."""
        intervals = self._compute_live_intervals(func)
        if not intervals:
            return RegAllocResult()

        # Separate GP and vector intervals
        gp_intervals = [iv for iv in intervals if not iv.is_vector]
        vec_intervals = [iv for iv in intervals if iv.is_vector]

        result = RegAllocResult()

        # Allocate GP registers
        self._linear_scan(gp_intervals, self.gp_pool, result, is_vec=False)
        # Allocate vector registers
        self._linear_scan(vec_intervals, self.vec_pool, result, is_vec=True)

        return result

    def rewrite(self, func: QFunction, result: RegAllocResult) -> QFunction:
        """Insert spill/reload instructions with redundancy elimination.

        Tracks which spilled VRegs are currently 'cached' in register
        (i.e. were recently loaded and not invalidated), skipping
        redundant Q_LOAD instructions.  Control-flow boundaries
        conservatively flush the cache.
        """
        if not result.spilled:
            return func  # nothing to rewrite

        _CFG = frozenset({
            Opcode.Q_LABEL, Opcode.Q_JUMP, Opcode.Q_JUMP_IF,
            Opcode.Q_JUMP_IF_NOT, Opcode.Q_CALL,
        })

        new_body: list[QInstruction] = []
        cached: set[int] = set()  # spilled-vreg indices currently valid in register

        for instr in func.body:
            # Control-flow boundaries → flush reload cache
            if instr.opcode in _CFG:
                cached.clear()

            # Reload spilled sources — skip if already cached
            for attr in ("src1", "src2"):
                op = getattr(instr, attr)
                if isinstance(op, VReg) and result.is_spilled(op.index):
                    if op.index not in cached:
                        slot = result.spilled[op.index]
                        new_body.append(QInstruction(
                            opcode=Opcode.Q_LOAD,
                            dest=op,
                            src1=Immediate(slot),
                            comment=f"spill-reload R{op.index} from slot {slot}",
                        ))
                        cached.add(op.index)

            new_body.append(instr)

            # Store spilled dest after the instruction
            if isinstance(instr.dest, VReg) and result.is_spilled(instr.dest.index):
                slot = result.spilled[instr.dest.index]
                new_body.append(QInstruction(
                    opcode=Opcode.Q_STORE,
                    dest=Immediate(slot),
                    src1=instr.dest,
                    comment=f"spill-store R{instr.dest.index} to slot {slot}",
                ))
                cached.add(instr.dest.index)

        func.body = new_body
        return func

    # ── Live Interval Computation ──────────────────────────

    def _compute_live_intervals(
        self, func: QFunction
    ) -> list[LiveInterval]:
        """Single forward pass to compute live intervals."""
        intervals: dict[int, LiveInterval] = {}  # vreg_index → interval

        for pos, instr in enumerate(func.body):
            is_vec = instr.opcode in _VECTOR_OPCODES or instr.opcode in _FP_OPCODES

            # Process dest (definition)
            if isinstance(instr.dest, VReg):
                idx = instr.dest.index
                if idx not in intervals:
                    intervals[idx] = LiveInterval(
                        vreg=idx, start=pos, end=pos, is_vector=is_vec,
                    )
                else:
                    intervals[idx].end = pos
                intervals[idx].use_positions.append(pos)

            # Process sources (uses)
            for op in (instr.src1, instr.src2):
                if isinstance(op, VReg):
                    idx = op.index
                    if idx not in intervals:
                        # Use before def — parameter or cross-block
                        intervals[idx] = LiveInterval(
                            vreg=idx, start=0, end=pos, is_vector=is_vec,
                        )
                    else:
                        intervals[idx].end = max(intervals[idx].end, pos)
                    intervals[idx].use_positions.append(pos)

        return list(intervals.values())

    # ── Core Linear Scan ───────────────────────────────────

    def _linear_scan(
        self,
        intervals: list[LiveInterval],
        pool: list[int],
        result: RegAllocResult,
        is_vec: bool,
    ) -> None:
        """Linear scan with next-use-distance spill heuristic.

        Instead of always spilling the interval ending furthest,
        spill the one whose *next use* is furthest from the current
        position.  This achieves the main benefit of live-range
        splitting—frequently-used VRegs stay in registers while
        infrequently-used ones are spilled during their idle gaps.
        """
        if not intervals:
            return

        # Sort by start position
        intervals.sort(key=lambda iv: iv.start)

        free_regs: list[int] = list(pool)  # available physical regs
        active: list[tuple[LiveInterval, int]] = []  # (interval, phys_reg), sorted by end

        for iv in intervals:
            # Expire old intervals — free registers whose interval has ended
            active = [
                (a_iv, a_reg) for a_iv, a_reg in active
                if a_iv.end > iv.start
            ]
            free_regs = [r for r in pool if r not in {a_reg for _, a_reg in active}]

            if free_regs:
                # Allocate a physical register
                reg = free_regs[0]
                active.append((iv, reg))
                active.sort(key=lambda x: x[0].end)
                result.assignment[iv.vreg] = reg
                if is_vec:
                    result.vec_regs_used = max(
                        result.vec_regs_used, len(pool) - len(free_regs) + 1
                    )
                else:
                    result.gp_regs_used = max(
                        result.gp_regs_used, len(pool) - len(free_regs) + 1
                    )
            else:
                # ── Next-use spill heuristic ──────────────────
                # Pick the active interval whose next use after the
                # current position is furthest away.
                if active:
                    spill_idx = max(
                        range(len(active)),
                        key=lambda i: active[i][0].next_use_after(iv.start),
                    )
                    spill_iv, spill_reg = active[spill_idx]
                    spill_next = spill_iv.next_use_after(iv.start)
                    iv_next = iv.next_use_after(iv.start)

                    if spill_next > iv_next:
                        # Evict the one not needed soon
                        active.pop(spill_idx)
                        slot = result.num_spill_slots
                        result.num_spill_slots += 1
                        result.spilled[spill_iv.vreg] = slot
                        result.assignment.pop(spill_iv.vreg, None)
                        result.assignment[iv.vreg] = spill_reg
                        active.append((iv, spill_reg))
                        active.sort(key=lambda x: x[0].end)
                    else:
                        # Current interval's next use is furthest → spill it
                        slot = result.num_spill_slots
                        result.num_spill_slots += 1
                        result.spilled[iv.vreg] = slot
                else:
                    # No active intervals (shouldn't happen in practice)
                    slot = result.num_spill_slots
                    result.num_spill_slots += 1
                    result.spilled[iv.vreg] = slot
