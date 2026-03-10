"""
Escape Analysis & Stack Promotion
===================================
Analyzes Q_ALLOC instructions to determine whether allocated objects
escape their defining scope. Non-escaping allocations are promoted to
Q_STACK_ALLOC (stack allocation) — eliminating heap allocation overhead.

An allocation "escapes" if:
  - It is stored to a global or heap location (Q_STORE to non-local address)
  - It is passed as an argument to a function call (Q_CALL)
  - It is returned from the function (Q_RET)
  - It is used in a Phi/merge across loop iterations with external consumers

Non-escaping allocations can be:
  1. Promoted to stack allocation (Q_STACK_ALLOC)
  2. Their corresponding Q_FREE automatically inserted at scope exit
  3. Potentially scalarized (each field as a separate VReg)

This is critical for alloc_free benchmark: target < 1ms (currently 379x slower than C).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)


class EscapeState(Enum):
    """Escape lattice: NO_ESCAPE < ARG_ESCAPE < GLOBAL_ESCAPE."""
    NO_ESCAPE = 0       # Object does not escape — safe for stack promotion
    ARG_ESCAPE = 1      # Escapes via function argument but not globally
    GLOBAL_ESCAPE = 2   # Escapes globally (stored to heap, returned, etc.)


@dataclass
class AllocSite:
    """Information about a single allocation site."""
    instr_idx: int            # Index in func.body
    dest_vreg: int            # VReg that holds the pointer
    size_op: object           # Size operand (Immediate or VReg)
    escape_state: EscapeState = EscapeState.NO_ESCAPE
    users: list[int] = field(default_factory=list)  # indices of instructions using this alloc


class EscapeAnalyzer:
    """Performs escape analysis on Q-IR functions."""

    def __init__(self) -> None:
        self.promoted: int = 0
        self.total_allocs: int = 0
        self._alloc_sites: list[AllocSite] = []

    def run(self, func: QFunction) -> None:
        """Run escape analysis and promote non-escaping allocs to stack."""
        self._alloc_sites.clear()
        self.promoted = 0
        self.total_allocs = 0

        # Phase 1: Find all Q_ALLOC sites
        self._find_alloc_sites(func)
        if not self._alloc_sites:
            return

        # Phase 2: Compute escape states via pointer tracking
        self._compute_escape(func)

        # Phase 3: Promote non-escaping allocations to stack
        self._promote_to_stack(func)

    def _find_alloc_sites(self, func: QFunction) -> None:
        """Identify all Q_ALLOC instructions."""
        for i, instr in enumerate(func.body):
            if instr.opcode == Opcode.Q_ALLOC and isinstance(instr.dest, VReg):
                self.total_allocs += 1
                self._alloc_sites.append(AllocSite(
                    instr_idx=i,
                    dest_vreg=instr.dest.index,
                    size_op=instr.src1,
                ))

    def _compute_escape(self, func: QFunction) -> None:
        """Determine escape state for each allocation site."""
        # Build pointer alias map: VReg → set of AllocSite indices
        # Tracks which alloc site(s) a VReg may point to
        ptr_to_alloc: dict[int, set[int]] = {}

        for ai, site in enumerate(self._alloc_sites):
            ptr_to_alloc.setdefault(site.dest_vreg, set()).add(ai)

        # Forward pass: propagate pointer aliases and detect escapes
        for i, instr in enumerate(func.body):
            # Q_MOVE copies pointer
            if instr.opcode == Opcode.Q_MOVE:
                if isinstance(instr.src1, VReg) and isinstance(instr.dest, VReg):
                    src_allocs = ptr_to_alloc.get(instr.src1.index)
                    if src_allocs:
                        ptr_to_alloc.setdefault(instr.dest.index, set()).update(src_allocs)

            # Q_STORE: if storing a pointer, it escapes globally
            elif instr.opcode == Opcode.Q_STORE:
                # The value being stored is in src2 (or src1 depending on convention)
                for op in (instr.src1, instr.src2):
                    if isinstance(op, VReg):
                        allocs = ptr_to_alloc.get(op.index)
                        if allocs:
                            for ai in allocs:
                                # Storing to a non-stack address = global escape
                                # Conservative: any store of a pointer escapes
                                self._alloc_sites[ai].escape_state = max(
                                    self._alloc_sites[ai].escape_state,
                                    EscapeState.GLOBAL_ESCAPE,
                                    key=lambda s: s.value,
                                )

            # Q_RET: returning a pointer escapes globally
            elif instr.opcode == Opcode.Q_RET:
                if isinstance(instr.src1, VReg):
                    allocs = ptr_to_alloc.get(instr.src1.index)
                    if allocs:
                        for ai in allocs:
                            self._alloc_sites[ai].escape_state = max(
                                self._alloc_sites[ai].escape_state,
                                EscapeState.GLOBAL_ESCAPE,
                                key=lambda s: s.value,
                            )

            # Q_CALL: passing pointer as argument = arg escape
            elif instr.opcode == Opcode.Q_CALL:
                for op in (instr.src2, instr.dest):
                    if isinstance(op, VReg):
                        allocs = ptr_to_alloc.get(op.index)
                        if allocs:
                            for ai in allocs:
                                self._alloc_sites[ai].escape_state = max(
                                    self._alloc_sites[ai].escape_state,
                                    EscapeState.ARG_ESCAPE,
                                    key=lambda s: s.value,
                                )

            # Track users for each alloc
            for op in (instr.src1, instr.src2):
                if isinstance(op, VReg):
                    allocs = ptr_to_alloc.get(op.index)
                    if allocs:
                        for ai in allocs:
                            self._alloc_sites[ai].users.append(i)

    def _promote_to_stack(self, func: QFunction) -> None:
        """Replace non-escaping Q_ALLOC with Q_STACK_ALLOC."""
        # Only promote allocations with known size that fit on stack
        MAX_STACK_ALLOC = 4096  # 4KB max stack allocation

        for site in self._alloc_sites:
            if site.escape_state != EscapeState.NO_ESCAPE:
                continue

            # Check size is known and reasonable
            size = None
            if isinstance(site.size_op, Immediate):
                size = int(site.size_op.value)
            if size is None or size > MAX_STACK_ALLOC or size <= 0:
                continue

            # Promote: Q_ALLOC → Q_STACK_ALLOC
            old_instr = func.body[site.instr_idx]
            func.body[site.instr_idx] = QInstruction(
                opcode=Opcode.Q_STACK_ALLOC,
                dest=old_instr.dest,
                src1=old_instr.src1,
                comment=f"stack-promoted (size={size}, no escape)",
            )
            self.promoted += 1

    def analyze_module(self, module: QModule) -> dict[str, dict]:
        """Run escape analysis on all functions, return per-function stats."""
        stats: dict[str, dict] = {}
        for func in module.functions:
            self.run(func)
            stats[func.name] = {
                "total_allocs": self.total_allocs,
                "promoted": self.promoted,
                "sites": [
                    {
                        "vreg": s.dest_vreg,
                        "escape": s.escape_state.name,
                        "users": len(s.users),
                    }
                    for s in self._alloc_sites
                ],
            }
        return stats
