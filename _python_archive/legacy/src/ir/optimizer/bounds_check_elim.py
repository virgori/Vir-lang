"""
Bounds Check Elimination (BCE) via Range Analysis
==================================================
Eliminates provably safe array bounds checks in loops by tracking
value ranges of induction variables and comparing against known
array lengths.

Algorithm:
  1. Identify loop induction variables (i = 0; i < N; i++)
  2. Build range intervals [lo, hi) for each VReg
  3. For Q_BOUNDS_CHECK(idx, len): if range(idx) ⊆ [0, len), eliminate
  4. Propagate ranges through arithmetic (ADD, SUB with constants)

This is the single biggest optimization for closing the array_traversal
gap between Vir and C (~248x → ~1x).
"""

from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
from typing import Optional

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    VReg,
)


@dataclass(frozen=True)
class Range:
    """Half-open interval [lo, hi). None means unbounded."""
    lo: int | None = None
    hi: int | None = None

    @property
    def is_bounded(self) -> bool:
        return self.lo is not None and self.hi is not None

    def contains(self, other: "Range") -> bool:
        """True if self fully contains other."""
        if not self.is_bounded or not other.is_bounded:
            return False
        return self.lo <= other.lo and other.hi <= self.hi

    def add_const(self, c: int) -> "Range":
        lo = self.lo + c if self.lo is not None else None
        hi = self.hi + c if self.hi is not None else None
        return Range(lo, hi)

    def sub_const(self, c: int) -> "Range":
        return self.add_const(-c)

    def mul_const(self, c: int) -> "Range":
        if self.lo is None or self.hi is None:
            return Range()
        if c >= 0:
            return Range(self.lo * c, self.hi * c)
        return Range(self.hi * c, self.lo * c)

    def intersect(self, other: "Range") -> "Range":
        lo = max(self.lo, other.lo) if self.lo is not None and other.lo is not None else (self.lo or other.lo)
        hi = min(self.hi, other.hi) if self.hi is not None and other.hi is not None else (self.hi or other.hi)
        return Range(lo, hi)

    def union(self, other: "Range") -> "Range":
        lo = min(self.lo, other.lo) if self.lo is not None and other.lo is not None else None
        hi = max(self.hi, other.hi) if self.hi is not None and other.hi is not None else None
        return Range(lo, hi)


@dataclass
class LoopInfo:
    """Detected canonical loop: for (iv = init; iv < bound; iv += step)."""
    label: str
    iv_vreg: int          # induction variable VReg index
    init_val: int         # initial value (typically 0)
    bound_vreg: int | None   # VReg holding the upper bound
    bound_imm: int | None    # or immediate upper bound
    step: int             # increment per iteration (typically 1)
    body_start: int       # index in body[] of first body instruction
    body_end: int         # index of back-edge instruction
    cmp_opcode: Opcode | None = None  # Q_CMP_LT, Q_CMP_LE, etc.


class BoundsCheckEliminator:
    """Eliminate redundant Q_BOUNDS_CHECK instructions using range analysis."""

    def __init__(self) -> None:
        self.eliminated: int = 0
        self.total_checks: int = 0

    def run(self, func: QFunction) -> None:
        """Run BCE on a single function. Modifies func.body in-place."""
        self.eliminated = 0
        self.total_checks = 0

        loops = self._detect_loops(func)
        if not loops:
            return

        # Process each loop
        for loop in loops:
            self._eliminate_in_loop(func, loop)

    def _detect_loops(self, func: QFunction) -> list[LoopInfo]:
        """Detect canonical counted loops."""
        loops: list[LoopInfo] = []
        body = func.body

        for i, instr in enumerate(body):
            if instr.opcode != Opcode.Q_LABEL:
                continue
            label_name = instr.patch_id or (instr.dest.name if isinstance(instr.dest, Label) else "")
            if not label_name:
                continue

            # Find back-edge: conditional or unconditional jump back to this label
            back_edge_idx = self._find_back_edge(body, i + 1, label_name)
            if back_edge_idx is None:
                continue

            # Analyze the loop to extract IV, bound, step
            loop_info = self._analyze_loop(body, i, back_edge_idx, label_name)
            if loop_info is not None:
                loops.append(loop_info)

        return loops

    def _find_back_edge(self, body: list[QInstruction], start: int, label: str) -> int | None:
        """Find backward jump to label within a reasonable window."""
        for j in range(start, min(start + 80, len(body))):
            instr = body[j]
            if instr.opcode in (Opcode.Q_JUMP, Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT):
                for op in (instr.src1, instr.src2, instr.dest):
                    if isinstance(op, Label) and op.name == label:
                        return j
            # Another label beyond start means we left scope
            if instr.opcode == Opcode.Q_LABEL and j > start + 2:
                break
        return None

    def _analyze_loop(
        self, body: list[QInstruction], label_idx: int, back_edge_idx: int, label: str
    ) -> LoopInfo | None:
        """Extract induction variable, bounds, and step from a counted loop.

        Pattern:
            ; before loop: Q_LOAD iv, #0  (init)
            Q_LABEL @loop
            ...
            Q_ADD iv, iv, #step
            Q_CMP_LT cond, iv, bound
            Q_JUMP_IF @loop, cond
        """
        loop_body = body[label_idx + 1 : back_edge_idx + 1]
        if len(loop_body) < 2:
            return None

        back_edge = body[back_edge_idx]

        # Find the comparison before the back-edge
        cmp_instr: QInstruction | None = None
        cmp_idx = back_edge_idx - 1
        while cmp_idx > label_idx:
            candidate = body[cmp_idx]
            if candidate.opcode in (
                Opcode.Q_CMP_LT, Opcode.Q_CMP_LE, Opcode.Q_CMP_GT,
                Opcode.Q_CMP_GE, Opcode.Q_CMP_NE,
            ):
                cmp_instr = candidate
                break
            cmp_idx -= 1

        if cmp_instr is None:
            return None

        # Extract IV from comparison: CMP cond, iv, bound
        iv_vreg_idx: int | None = None
        bound_vreg: int | None = None
        bound_imm: int | None = None

        if isinstance(cmp_instr.src1, VReg):
            iv_vreg_idx = cmp_instr.src1.index
        if isinstance(cmp_instr.src2, VReg):
            bound_vreg = cmp_instr.src2.index
        elif isinstance(cmp_instr.src2, Immediate):
            bound_imm = int(cmp_instr.src2.value)

        if iv_vreg_idx is None:
            return None

        # Find increment: Q_ADD iv, iv, #step
        step = 1
        for inst in body[label_idx + 1 : back_edge_idx]:
            if (inst.opcode == Opcode.Q_ADD
                    and isinstance(inst.dest, VReg)
                    and inst.dest.index == iv_vreg_idx
                    and isinstance(inst.src1, VReg)
                    and inst.src1.index == iv_vreg_idx
                    and isinstance(inst.src2, Immediate)):
                step = int(inst.src2.value)
                break

        # Find init value: Q_LOAD iv, #init before the loop label
        init_val = 0
        for k in range(label_idx - 1, max(label_idx - 10, -1), -1):
            pinstr = body[k]
            if (pinstr.opcode == Opcode.Q_LOAD
                    and isinstance(pinstr.dest, VReg)
                    and pinstr.dest.index == iv_vreg_idx
                    and isinstance(pinstr.src1, Immediate)):
                init_val = int(pinstr.src1.value)
                break

        return LoopInfo(
            label=label,
            iv_vreg=iv_vreg_idx,
            init_val=init_val,
            bound_vreg=bound_vreg,
            bound_imm=bound_imm,
            step=step,
            body_start=label_idx + 1,
            body_end=back_edge_idx,
            cmp_opcode=cmp_instr.opcode,
        )

    def _eliminate_in_loop(self, func: QFunction, loop: LoopInfo) -> None:
        """Eliminate Q_BOUNDS_CHECK instructions inside a detected loop."""
        body = func.body

        # Resolve bound_imm from VReg if needed (look up pre-loop loads)
        effective_bound: int | None = loop.bound_imm
        if effective_bound is None and loop.bound_vreg is not None:
            # Search for Q_LOAD bound_vreg, #imm before the loop
            for k in range(loop.body_start - 1, max(loop.body_start - 20, -1), -1):
                pinstr = body[k]
                if (pinstr.opcode == Opcode.Q_LOAD
                        and isinstance(pinstr.dest, VReg)
                        and pinstr.dest.index == loop.bound_vreg
                        and isinstance(pinstr.src1, Immediate)):
                    effective_bound = int(pinstr.src1.value)
                    break

        # Compute the range of the induction variable within this loop
        if loop.cmp_opcode == Opcode.Q_CMP_LT:
            # The comparison is on the POST-increment value: (iv + step) < bound
            # So the pre-increment iv ∈ [init, bound - step)
            # At the bounds check (before increment), iv ∈ [init, bound - 1]
            # since loop continues while (iv+1) < bound → iv ∈ [init, bound-1)
            iv_range = Range(loop.init_val,
                             effective_bound if effective_bound is not None else None)
        elif loop.cmp_opcode == Opcode.Q_CMP_LE:
            iv_range = Range(loop.init_val,
                             effective_bound + 1 if effective_bound is not None else None)
        elif loop.cmp_opcode == Opcode.Q_CMP_NE:
            iv_range = Range(loop.init_val,
                             effective_bound if effective_bound is not None else None)
        else:
            return

        # Build range map: VReg → Range derived from IV
        ranges: dict[int, Range] = {loop.iv_vreg: iv_range}

        # Also track VRegs loaded with constants before the loop
        for k in range(0, loop.body_start):
            pinstr = body[k]
            if (pinstr.opcode == Opcode.Q_LOAD
                    and isinstance(pinstr.dest, VReg)
                    and isinstance(pinstr.src1, Immediate)):
                val = int(pinstr.src1.value)
                ranges[pinstr.dest.index] = Range(val, val + 1)

        # Propagate ranges through arithmetic in the loop body
        for idx in range(loop.body_start, loop.body_end):
            instr = body[idx]
            if not isinstance(instr.dest, VReg):
                continue

            if instr.opcode == Opcode.Q_ADD:
                src_range = self._get_range(instr.src1, ranges)
                if src_range and isinstance(instr.src2, Immediate):
                    ranges[instr.dest.index] = src_range.add_const(int(instr.src2.value))
                elif isinstance(instr.src1, Immediate) and isinstance(instr.src2, VReg):
                    r2 = ranges.get(instr.src2.index)
                    if r2:
                        ranges[instr.dest.index] = r2.add_const(int(instr.src1.value))

            elif instr.opcode == Opcode.Q_SUB:
                src_range = self._get_range(instr.src1, ranges)
                if src_range and isinstance(instr.src2, Immediate):
                    ranges[instr.dest.index] = src_range.sub_const(int(instr.src2.value))

            elif instr.opcode == Opcode.Q_MUL:
                src_range = self._get_range(instr.src1, ranges)
                if src_range and isinstance(instr.src2, Immediate):
                    ranges[instr.dest.index] = src_range.mul_const(int(instr.src2.value))

            elif instr.opcode == Opcode.Q_LOAD and isinstance(instr.src1, Immediate):
                val = int(instr.src1.value)
                ranges[instr.dest.index] = Range(val, val + 1)

            elif instr.opcode == Opcode.Q_MOVE and isinstance(instr.src1, VReg):
                src_r = ranges.get(instr.src1.index)
                if src_r:
                    ranges[instr.dest.index] = src_r

        # Now eliminate bounds checks
        new_body = list(body)
        eliminated_indices: list[int] = []

        for idx in range(loop.body_start, loop.body_end):
            instr = body[idx]
            if instr.opcode != Opcode.Q_BOUNDS_CHECK:
                continue

            self.total_checks += 1

            # Q_BOUNDS_CHECK idx_reg, len_reg_or_imm
            idx_reg = instr.src1
            len_op = instr.src2

            idx_range = self._get_range(idx_reg, ranges)
            if idx_range is None or not idx_range.is_bounded:
                continue

            # Determine the valid range [0, len)
            safe_range: Range | None = None
            if isinstance(len_op, Immediate):
                safe_range = Range(0, int(len_op.value))
            elif isinstance(len_op, VReg):
                # Check if we know the value of this VReg
                len_range = ranges.get(len_op.index)
                if len_range and len_range.is_bounded:
                    # If it's a constant (lo == hi - 1), use it directly
                    if len_range.hi == len_range.lo + 1:
                        safe_range = Range(0, len_range.lo)
                    else:
                        # Conservative: use the minimum possible length
                        safe_range = Range(0, len_range.lo)
                # Also: if bound VReg matches loop bound and we know effective_bound
                if safe_range is None and len_op.index == loop.bound_vreg and effective_bound is not None:
                    safe_range = Range(0, effective_bound)

            if safe_range is None:
                continue

            # Check: idx_range ⊆ [0, safe_range.hi) ?
            if (idx_range.lo is not None and idx_range.lo >= 0
                    and idx_range.hi is not None
                    and safe_range.hi is not None
                    and idx_range.hi <= safe_range.hi):
                # Provably safe — eliminate the bounds check
                eliminated_indices.append(idx)
                self.eliminated += 1

        # Remove eliminated checks (replace with NOP for index stability, then compact)
        for idx in reversed(eliminated_indices):
            new_body[idx] = QInstruction(
                Opcode.Q_NOP,
                comment=f"BCE: bounds check eliminated (range [{iv_range.lo},{iv_range.hi}))",
            )

        func.body = new_body

    def _get_range(self, op, ranges: dict[int, Range]) -> Range | None:
        """Get the range for an operand."""
        if isinstance(op, VReg):
            return ranges.get(op.index)
        if isinstance(op, Immediate):
            val = int(op.value)
            return Range(val, val + 1)
        return None
