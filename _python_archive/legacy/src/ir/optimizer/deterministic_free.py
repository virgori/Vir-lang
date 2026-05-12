"""
Deterministic Free — Automatic Q_FREE insertion at scope exits
================================================================
For synchronous functions, automatically insert Q_FREE instructions
at all exit points for allocations whose lifetime ends within the scope.

Unlike GC/RC approaches:
  - Zero runtime overhead (no reference counting, no GC pause)
  - Deterministic timing (free happens at a known program point)
  - Composable with Escape Analysis (non-escaping + deterministic free = C-like perf)

Algorithm:
  1. Find all Q_ALLOC / Q_STACK_ALLOC in a function
  2. Compute liveness: last use of each allocation pointer
  3. For heap allocations (Q_ALLOC) not freed explicitly, insert Q_FREE
     at the earliest safe point after last use (or at scope exit)
  4. Skip Q_STACK_ALLOC (automatically freed on function return)
  5. Handle multiple return paths (insert Q_FREE before each Q_RET)
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class AllocLifetime:
    """Tracks lifetime of a heap allocation."""
    alloc_idx: int         # Index of Q_ALLOC in func.body
    dest_vreg: int         # VReg holding the pointer
    last_use: int          # Index of last instruction using this pointer
    has_explicit_free: bool = False  # Already freed by user code
    is_stack: bool = False  # Q_STACK_ALLOC — no free needed


class DeterministicFree:
    """Insert Q_FREE instructions at scope exits for unfree'd allocations."""

    def __init__(self) -> None:
        self.inserted: int = 0

    def run(self, func: QFunction) -> None:
        """Run deterministic free insertion on a single function."""
        self.inserted = 0

        # Phase 1: Find allocations and their lifetimes
        lifetimes = self._compute_lifetimes(func)
        if not lifetimes:
            return

        # Phase 2: Find all return points
        ret_indices = [
            i for i, instr in enumerate(func.body)
            if instr.opcode == Opcode.Q_RET
        ]

        # Phase 3: Insert Q_FREE before returns for heap allocations
        # that are not already freed
        needs_free = [
            lt for lt in lifetimes
            if not lt.has_explicit_free and not lt.is_stack
        ]

        if not needs_free:
            return

        # Build insertion list: (index, Q_FREE instruction)
        # Insert before each Q_RET, in reverse alloc order (LIFO — like stack unwinding)
        insertions: list[tuple[int, QInstruction]] = []

        for ret_idx in ret_indices:
            for lt in reversed(needs_free):
                # Only free if the allocation is live at this return point
                # (alloc happened before this return)
                if lt.alloc_idx < ret_idx:
                    free_instr = QInstruction(
                        opcode=Opcode.Q_FREE,
                        src1=VReg(lt.dest_vreg),
                        comment=f"det-free: R{lt.dest_vreg} (alloc@{lt.alloc_idx})",
                    )
                    insertions.append((ret_idx, free_instr))

        # Also insert Q_FREE at scope exit for allocations whose last use
        # is well before any return — place free right after last use
        for lt in needs_free:
            if not ret_indices:
                continue
            # If last_use is far from function end, insert early free
            earliest_ret = min(ret_indices) if ret_indices else len(func.body)
            if lt.last_use < earliest_ret - 3:
                early_free = QInstruction(
                    opcode=Opcode.Q_FREE,
                    src1=VReg(lt.dest_vreg),
                    comment=f"det-free-early: R{lt.dest_vreg} (last use@{lt.last_use})",
                )
                insertions.append((lt.last_use + 1, early_free))

        # Apply insertions (process in reverse order to maintain indices)
        insertions.sort(key=lambda x: x[0], reverse=True)
        # Deduplicate: don't insert both early-free and return-free for same alloc
        seen_frees: set[int] = set()
        for idx, free_instr in insertions:
            vreg_idx = free_instr.src1.index if isinstance(free_instr.src1, VReg) else -1
            if vreg_idx in seen_frees:
                continue
            seen_frees.add(vreg_idx)
            func.body.insert(idx, free_instr)
            self.inserted += 1

    def _compute_lifetimes(self, func: QFunction) -> list[AllocLifetime]:
        """Compute allocation lifetimes: find alloc sites and their last use."""
        lifetimes: list[AllocLifetime] = []
        alloc_vregs: dict[int, int] = {}  # vreg_index → index in lifetimes list

        # Build pointer alias map for tracking MOVEs
        aliases: dict[int, int] = {}  # vreg → original alloc vreg

        for i, instr in enumerate(func.body):
            # Track allocations
            if instr.opcode == Opcode.Q_ALLOC and isinstance(instr.dest, VReg):
                lt_idx = len(lifetimes)
                lifetimes.append(AllocLifetime(
                    alloc_idx=i,
                    dest_vreg=instr.dest.index,
                    last_use=i,
                ))
                alloc_vregs[instr.dest.index] = lt_idx

            elif instr.opcode == Opcode.Q_STACK_ALLOC and isinstance(instr.dest, VReg):
                lt_idx = len(lifetimes)
                lifetimes.append(AllocLifetime(
                    alloc_idx=i,
                    dest_vreg=instr.dest.index,
                    last_use=i,
                    is_stack=True,
                ))
                alloc_vregs[instr.dest.index] = lt_idx

            # Track explicit frees
            elif instr.opcode == Opcode.Q_FREE:
                if isinstance(instr.src1, VReg):
                    vreg = aliases.get(instr.src1.index, instr.src1.index)
                    if vreg in alloc_vregs:
                        lifetimes[alloc_vregs[vreg]].has_explicit_free = True

            # Track pointer aliases through MOVEs
            elif instr.opcode == Opcode.Q_MOVE:
                if isinstance(instr.src1, VReg) and isinstance(instr.dest, VReg):
                    src_orig = aliases.get(instr.src1.index, instr.src1.index)
                    if src_orig in alloc_vregs:
                        aliases[instr.dest.index] = src_orig

            # Update last use for any VReg referencing an alloc
            for op in (instr.src1, instr.src2):
                if isinstance(op, VReg):
                    vreg = aliases.get(op.index, op.index)
                    if vreg in alloc_vregs:
                        lifetimes[alloc_vregs[vreg]].last_use = i

        return lifetimes

    def run_module(self, module: QModule) -> int:
        """Run on all functions. Returns total Q_FREE inserted."""
        total = 0
        for func in module.functions:
            self.run(func)
            total += self.inserted
        return total
