"""
optimizer.py – Bộ tối ưu hóa Q-IR cơ bản
==========================================
Các bước tối ưu trên Q-IR trước khi hạ xuống Backend:
  1. Dead code elimination
  2. Constant folding
  3. Copy propagation
  4. Strength reduction (cost-model-driven)
  5. Bounds check elimination (range analysis)
  6. Escape analysis + stack promotion
  7. Deterministic free insertion
"""

from __future__ import annotations

import math
from dataclasses import replace as dc_replace
from typing import Optional

from src.ir.instructions.q_ir import (
    Immediate,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    Label,
    VReg,
)
from src.ir.cost_model.cost_model import CostModel
from src.ir.optimizer.bounds_check_elim import BoundsCheckEliminator
from src.ir.optimizer.escape_analysis import EscapeAnalyzer
from src.ir.optimizer.deterministic_free import DeterministicFree


# ═══════════════════════════════════════════════════════════
# Scalar → Vector Opcode Map
# ═══════════════════════════════════════════════════════════

_SCALAR_TO_VECTOR = {
    Opcode.Q_ADD: Opcode.Q_VADD,
    Opcode.Q_SUB: Opcode.Q_VSUB,
    Opcode.Q_MUL: Opcode.Q_VMUL,
    Opcode.Q_DIV: Opcode.Q_VDIV,
    Opcode.Q_LOAD: Opcode.Q_VLOAD,
    Opcode.Q_STORE: Opcode.Q_VSTORE,
}


class IROptimizer:
    """Tối ưu hóa QModule in-place, driven by CostModel."""

    def __init__(self, arch: str = "arm64", cost_model: Optional[CostModel] = None):
        self.cost_model = cost_model or CostModel(arch)
        self._bce = BoundsCheckEliminator()
        self._escape = EscapeAnalyzer()
        self._det_free = DeterministicFree()
        # Stats from last optimize() call
        self.bce_eliminated: int = 0
        self.stack_promoted: int = 0
        self.frees_inserted: int = 0

    def optimize(self, module: QModule) -> QModule:
        # Build function table for inlining
        func_table = {f.name: f for f in module.functions}
        self.bce_eliminated = 0
        self.stack_promoted = 0
        self.frees_inserted = 0

        for func in module.functions:
            self._copy_propagate(func)
            self._constant_fold(func)
            self._cse(func)
            self._inline_functions(func, func_table)
            self._strength_reduce(func)
            self._licm(func)
            # --- Phase 7: Memory Safety Optimizations ---
            self._bce.run(func)
            self._escape.run(func)
            self._det_free.run(func)
            self.bce_eliminated += self._bce.eliminated
            self.stack_promoted += self._escape.promoted
            self.frees_inserted += self._det_free.inserted
            # --- End Phase 7 ---
            self._loop_unroll(func)
            self._vectorize(func)
            self._dead_code_eliminate(func)
        return module

    # ── Copy Propagation ────────────────────────────────────
    def _copy_propagate(self, func: QFunction) -> None:
        """Replace uses of vY with vX when Q_MOVE vX → vY is seen."""
        # Control-flow instructions invalidate all copies
        _CFG_OPCODES = frozenset({
            Opcode.Q_LABEL, Opcode.Q_JUMP, Opcode.Q_JUMP_IF,
            Opcode.Q_JUMP_IF_NOT, Opcode.Q_CALL,
        })

        copies: dict[int, VReg] = {}  # dest_vreg_index → source VReg
        new_body: list[QInstruction] = []

        for instr in func.body:
            # At control-flow boundaries, invalidate all copies
            if instr.opcode in _CFG_OPCODES:
                copies.clear()
                new_body.append(instr)
                continue

            # Substitute operands using known copies
            new_src1 = self._subst(instr.src1, copies)
            new_src2 = self._subst(instr.src2, copies)
            if new_src1 is not instr.src1 or new_src2 is not instr.src2:
                instr = dc_replace(instr, src1=new_src1, src2=new_src2)

            # Track Q_MOVE as a copy: dest = src1
            if instr.opcode == Opcode.Q_MOVE \
                    and isinstance(instr.dest, VReg) \
                    and isinstance(instr.src1, VReg):
                copies[instr.dest.index] = instr.src1
            elif isinstance(instr.dest, VReg):
                # dest is redefined → kill any copy pointing to it
                copies.pop(instr.dest.index, None)
                # Also kill any copy whose source was just overwritten
                to_remove = [k for k, v in copies.items() if v.index == instr.dest.index]
                for k in to_remove:
                    del copies[k]

            new_body.append(instr)

        func.body = new_body

    @staticmethod
    def _subst(op, copies: dict[int, VReg]):
        """Resolve a VReg through the copy chain."""
        if isinstance(op, VReg) and op.index in copies:
            return copies[op.index]
        return op

    # ── Constant Folding ───────────────────────────────────
    def _constant_fold(self, func: QFunction) -> None:
        """Gập hằng: nếu src1 & src2 đều là Immediate → tính ngay."""
        _CFG_OPCODES = frozenset({
            Opcode.Q_LABEL, Opcode.Q_JUMP, Opcode.Q_JUMP_IF,
            Opcode.Q_JUMP_IF_NOT, Opcode.Q_CALL,
        })
        new_body: list[QInstruction] = []
        known: dict[int, float] = {}  # VReg.index → known immediate value

        for instr in func.body:
            # Invalidate at control-flow boundaries
            if instr.opcode in _CFG_OPCODES:
                known.clear()
                new_body.append(instr)
                continue

            # Track Q_LOAD of immediates
            if instr.opcode == Opcode.Q_LOAD and isinstance(instr.dest, VReg) \
                    and isinstance(instr.src1, Immediate):
                known[instr.dest.index] = instr.src1.value
                new_body.append(instr)
                continue

            # Try to fold arithmetic
            if instr.opcode in (Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL, Opcode.Q_DIV):
                val1 = self._resolve(instr.src1, known)
                val2 = self._resolve(instr.src2, known)
                if val1 is not None and val2 is not None:
                    result = self._compute(instr.opcode, val1, val2)
                    if result is not None and isinstance(instr.dest, VReg):
                        known[instr.dest.index] = result
                        new_body.append(QInstruction(
                            Opcode.Q_LOAD, dest=instr.dest, src1=Immediate(result),
                            comment=f"folded {instr.opcode.name}",
                        ))
                        continue

            new_body.append(instr)

        func.body = new_body

    @staticmethod
    def _resolve(op, known: dict[int, float]) -> float | None:
        if isinstance(op, Immediate):
            return op.value
        if isinstance(op, VReg) and op.index in known:
            return known[op.index]
        return None

    @staticmethod
    def _compute(opcode: Opcode, a: float, b: float) -> float | None:
        match opcode:
            case Opcode.Q_ADD:
                return a + b
            case Opcode.Q_SUB:
                return a - b
            case Opcode.Q_MUL:
                return a * b
            case Opcode.Q_DIV:
                return a / b if b != 0 else None
        return None

    # ── Dead Code Elimination ──────────────────────────────
    def _dead_code_eliminate(self, func: QFunction) -> None:
        """Loại bỏ instructions mà dest không được dùng sau đó."""
        # Collect used VRegs
        used: set[int] = set()
        for instr in func.body:
            for op in (instr.src1, instr.src2):
                if isinstance(op, VReg):
                    used.add(op.index)
            # Patch points, labels, jumps, ret, print, input → luôn giữ
            if instr.opcode in (
                Opcode.Q_PATCH_POINT, Opcode.Q_LABEL, Opcode.Q_JUMP,
                Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT, Opcode.Q_RET,
                Opcode.Q_PRINT, Opcode.Q_INPUT, Opcode.Q_CALL,
                Opcode.Q_FREE, Opcode.Q_BOUNDS_CHECK,
                Opcode.Q_STORE, Opcode.Q_VSTORE, Opcode.Q_FSTORE,
            ):
                if isinstance(instr.dest, VReg):
                    used.add(instr.dest.index)

        # Erasable opcodes: no side effects → safe to remove when unused
        _ERASABLE_FALLBACK = frozenset({
            Opcode.Q_LOAD, Opcode.Q_MOVE, Opcode.Q_ADD, Opcode.Q_SUB,
            Opcode.Q_MUL, Opcode.Q_DIV, Opcode.Q_CMP_EQ, Opcode.Q_CMP_GT,
            Opcode.Q_CMP_LT, Opcode.Q_CMP_NE, Opcode.Q_CMP_GE,
            Opcode.Q_CMP_LE,
            Opcode.Q_VADD, Opcode.Q_VSUB, Opcode.Q_VMUL, Opcode.Q_VDIV,
            Opcode.Q_VFMA, Opcode.Q_VMIN, Opcode.Q_VMAX,
            Opcode.Q_VREDUCE, Opcode.Q_VSPLAT, Opcode.Q_VPERM,
            Opcode.Q_VLOAD,
        })
        cm = self.cost_model
        _md_pure = cm.pure_opcodes()
        _ERASABLE = _ERASABLE_FALLBACK | _md_pure | frozenset(
            op for op in Opcode if cm.is_erasable(op)
        )

        new_body: list[QInstruction] = []
        for instr in func.body:
            if isinstance(instr.dest, VReg) and instr.dest.index not in used:
                # Side-effect free instructions with unused dest → remove
                if instr.opcode in _ERASABLE:
                    continue
            new_body.append(instr)

        func.body = new_body

    # ── Strength Reduction (Cost-Model Driven) ─────────────
    def _strength_reduce(self, func: QFunction) -> None:
        """Replace expensive operations with cheaper equivalents.

        Cost-model driven transformations:
          - MUL by power-of-2   → left shift (ADD chain or shift)
          - MUL by 0            → LOAD 0
          - MUL by 1            → MOVE
          - DIV by power-of-2   → right shift (treated as cheaper MUL+shift sequence)
          - MOD by power-of-2   → AND with (pow2 - 1)
        """
        if not self.cost_model.should_strength_reduce(Opcode.Q_MUL):
            return  # MUL is cheap enough, skip

        new_body: list[QInstruction] = []
        known: dict[int, float] = {}  # VReg.index → known imm value

        for instr in func.body:
            # Track immediates
            if instr.opcode == Opcode.Q_LOAD and isinstance(instr.dest, VReg) \
                    and isinstance(instr.src1, Immediate):
                known[instr.dest.index] = instr.src1.value

            # MUL strength reduction
            if instr.opcode == Opcode.Q_MUL and isinstance(instr.dest, VReg):
                val2 = self._resolve(instr.src2, known)
                if val2 is not None and val2 == int(val2) and val2 >= 0:
                    iv = int(val2)
                    if iv == 0:
                        new_body.append(QInstruction(
                            Opcode.Q_LOAD, dest=instr.dest, src1=Immediate(0),
                            comment="strength-reduce: MUL x,0 → 0",
                        ))
                        continue
                    if iv == 1:
                        new_body.append(QInstruction(
                            Opcode.Q_MOVE, dest=instr.dest, src1=instr.src1,
                            comment="strength-reduce: MUL x,1 → MOVE",
                        ))
                        continue
                    # Power-of-2: replace MUL with shift (represented as ADD chain)
                    if iv > 1 and (iv & (iv - 1)) == 0:
                        shift = int(math.log2(iv))
                        # Annotate for codegen to emit shift instead
                        new_body.append(dc_replace(
                            instr,
                            comment=f"strength-reduce: MUL x,{iv} → LSL x,{shift}",
                        ))
                        continue

            # DIV strength reduction: div by power-of-2 → shift right
            if instr.opcode == Opcode.Q_DIV and isinstance(instr.dest, VReg):
                val2 = self._resolve(instr.src2, known)
                if val2 is not None and val2 == int(val2) and val2 > 0:
                    iv = int(val2)
                    if iv == 1:
                        new_body.append(QInstruction(
                            Opcode.Q_MOVE, dest=instr.dest, src1=instr.src1,
                            comment="strength-reduce: DIV x,1 → MOVE",
                        ))
                        continue
                    if (iv & (iv - 1)) == 0:
                        shift = int(math.log2(iv))
                        new_body.append(dc_replace(
                            instr,
                            comment=f"strength-reduce: DIV x,{iv} → ASR x,{shift}",
                        ))
                        continue

            # MOD strength reduction: mod by power-of-2 → AND
            if instr.opcode == Opcode.Q_MOD and isinstance(instr.dest, VReg):
                val2 = self._resolve(instr.src2, known)
                if val2 is not None and val2 == int(val2) and val2 > 0:
                    iv = int(val2)
                    if (iv & (iv - 1)) == 0:
                        mask = iv - 1
                        new_body.append(dc_replace(
                            instr,
                            comment=f"strength-reduce: MOD x,{iv} → AND x,{mask}",
                        ))
                        continue

            new_body.append(instr)

        func.body = new_body

    # ── Common Subexpression Elimination (CSE) ─────────────
    def _cse(self, func: QFunction) -> None:
        """Eliminate duplicate computations using value numbering.

        For each arithmetic instruction (opcode, src1, src2), if we've
        already computed the same expression and the result vreg is still
        valid (not redefined), replace with a MOVE from the cached result.
        Invalidate at control-flow boundaries.
        """
        # Hash-based value numbering
        # Key: (opcode, canonical_src1, canonical_src2) → dest VReg
        # Use metadata-driven traits when available, hardcoded fallback otherwise
        _PURE_FALLBACK = frozenset({
            Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL, Opcode.Q_DIV,
            Opcode.Q_MOD, Opcode.Q_CMP_EQ, Opcode.Q_CMP_NE,
            Opcode.Q_CMP_GT, Opcode.Q_CMP_LT, Opcode.Q_CMP_GE,
            Opcode.Q_CMP_LE,
        })
        _COMM_FALLBACK = frozenset({Opcode.Q_ADD, Opcode.Q_MUL})
        cm = self.cost_model
        _PURE_OPS = _PURE_FALLBACK | cm.pure_opcodes()
        _COMMUTATIVE = _COMM_FALLBACK | cm.commutative_opcodes()

        _CFG_OPCODES = frozenset({
            Opcode.Q_LABEL, Opcode.Q_JUMP, Opcode.Q_JUMP_IF,
            Opcode.Q_JUMP_IF_NOT, Opcode.Q_CALL,
        })

        def _operand_key(op):
            if isinstance(op, VReg):
                return ("v", op.index)
            if isinstance(op, Immediate):
                return ("i", op.value)
            return ("n", None)

        expr_cache: dict[tuple, VReg] = {}
        new_body: list[QInstruction] = []

        for instr in func.body:
            if instr.opcode in _CFG_OPCODES:
                expr_cache.clear()
                new_body.append(instr)
                continue

            if (instr.opcode in _PURE_OPS
                    and isinstance(instr.dest, VReg)
                    and instr.src1 is not None):
                # Invalidate cached exprs whose result or source is this dest
                _inv_idx = instr.dest.index
                to_remove = [
                    k for k, v in expr_cache.items()
                    if v.index == _inv_idx
                    or any(part == ("v", _inv_idx) for part in k[1:])
                ]
                for k in to_remove:
                    del expr_cache[k]

                k1 = _operand_key(instr.src1)
                k2 = _operand_key(instr.src2)
                key = (instr.opcode, k1, k2)
                if instr.opcode in _COMMUTATIVE and k2 < k1:
                    key = (instr.opcode, k2, k1)

                if key in expr_cache:
                    cached = expr_cache[key]
                    # Replace with MOVE from cached result
                    new_body.append(QInstruction(
                        Opcode.Q_MOVE, dest=instr.dest, src1=cached,
                        comment=f"CSE: reuse {cached} for {instr.opcode.name}",
                    ))
                    continue
                else:
                    # First occurrence — cache it and emit normally
                    expr_cache[key] = instr.dest
                    new_body.append(instr)
                    continue

            # If dest is redefined, invalidate any cached expr that used it
            if isinstance(instr.dest, VReg):
                to_remove = [
                    k for k, v in expr_cache.items()
                    if v.index == instr.dest.index
                ]
                for k in to_remove:
                    del expr_cache[k]
                # Also invalidate exprs that reference the redefined vreg as source
                to_remove2 = [
                    k for k in expr_cache
                    if any(
                        part == ("v", instr.dest.index)
                        for part in k[1:]
                    )
                ]
                for k in to_remove2:
                    expr_cache.pop(k, None)

            new_body.append(instr)

        func.body = new_body

    # ── Function Inlining (IPO) ────────────────────────────
    _inline_counter: int = 0  # unique suffix to avoid vreg/label clashes

    def _inline_functions(
        self, func: QFunction, func_table: dict[str, QFunction],
    ) -> None:
        """Replace Q_CALL sites with the callee body when profitable.

        Inlining criteria:
          * Callee body <= MAX_INLINE_SIZE instructions
          * Non-recursive (callee != caller)

        VRegs in the inlined body are shifted by a per-site offset
        to avoid collisions.  Labels are similarly renamed.
        """
        MAX_INLINE_SIZE = 20

        new_body: list[QInstruction] = []

        # Find the highest vreg index already used in the caller
        max_vreg = 0
        for instr in func.body:
            for op in (instr.dest, instr.src1, instr.src2):
                if isinstance(op, VReg) and op.index > max_vreg:
                    max_vreg = op.index

        for instr in func.body:
            if instr.opcode != Opcode.Q_CALL:
                new_body.append(instr)
                continue

            # Extract callee name from the instruction
            callee_name: str | None = None
            if isinstance(instr.src1, Label):
                callee_name = instr.src1.name
            elif isinstance(instr.src1, Immediate) and instr.comment:
                # Some backends encode call target in comment
                callee_name = instr.comment.split()[-1] if instr.comment else None

            callee = func_table.get(callee_name) if callee_name else None

            # Inline only small, non-recursive callees
            if (callee is None
                    or callee.name == func.name
                    or len(callee.body) > MAX_INLINE_SIZE):
                new_body.append(instr)
                continue

            IROptimizer._inline_counter += 1
            tag = IROptimizer._inline_counter
            vreg_offset = max_vreg + 1
            max_vreg += self._max_vreg_in(callee) + 1

            def _remap(op):
                if isinstance(op, VReg):
                    return VReg(op.index + vreg_offset)
                if isinstance(op, Label):
                    return Label(f"{op.name}_inl{tag}")
                return op

            # Bind arguments: MOVE param_vreg(shifted) ← call arg vreg
            # Convention: args are in the caller's src2 and/or instr.dest
            # (Simplified: if callee has params, map first to src2, etc.)
            for pi, param in enumerate(callee.params):
                # Best-effort argument binding for the common 1-arg case
                arg = instr.src2 if pi == 0 and instr.src2 is not None else None
                if arg is not None:
                    new_body.append(QInstruction(
                        opcode=Opcode.Q_MOVE,
                        dest=VReg(param.index + vreg_offset),
                        src1=arg,
                        comment=f"inline-arg#{pi} {callee_name}",
                    ))

            # Copy callee body with remapped VRegs/Labels
            for c_instr in callee.body:
                if c_instr.opcode == Opcode.Q_RET:
                    # Map return value → caller's dest
                    if instr.dest is not None and c_instr.src1 is not None:
                        new_body.append(QInstruction(
                            opcode=Opcode.Q_MOVE,
                            dest=instr.dest,
                            src1=_remap(c_instr.src1),
                            comment=f"inline-ret {callee_name}",
                        ))
                    continue  # skip the Q_RET itself
                new_body.append(dc_replace(
                    c_instr,
                    dest=_remap(c_instr.dest),
                    src1=_remap(c_instr.src1),
                    src2=_remap(c_instr.src2),
                    patch_id=(f"{c_instr.patch_id}_inl{tag}"
                              if c_instr.patch_id else ""),
                    comment=c_instr.comment or f"inlined:{callee_name}",
                ))

        func.body = new_body

    @staticmethod
    def _max_vreg_in(func: QFunction) -> int:
        mx = 0
        for instr in func.body:
            for op in (instr.dest, instr.src1, instr.src2):
                if isinstance(op, VReg) and op.index > mx:
                    mx = op.index
        for p in func.params:
            if p.index > mx:
                mx = p.index
        return mx

    # ── LICM (Loop-Invariant Code Motion) ──────────────────
    def _licm(self, func: QFunction) -> None:
        """Hoist loop-invariant instructions to a preheader position.

        An instruction inside a loop is *invariant* if all its source
        operands are either constants (Immediate/Label) or defined
        outside the loop body.  We hoist such instructions before the
        loop label, reducing dynamic instruction count.
        """
        body = func.body
        new_body: list[QInstruction] = []
        i = 0

        _PURE_FALLBACK = frozenset({
            Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL, Opcode.Q_DIV,
            Opcode.Q_MOD, Opcode.Q_LOAD, Opcode.Q_MOVE,
            Opcode.Q_CMP_EQ, Opcode.Q_CMP_NE, Opcode.Q_CMP_GT,
            Opcode.Q_CMP_LT, Opcode.Q_CMP_GE, Opcode.Q_CMP_LE,
            Opcode.Q_FADD, Opcode.Q_FSUB, Opcode.Q_FMUL, Opcode.Q_FDIV,
        })
        _md_spec = self.cost_model.speculatable_opcodes()
        _PURE = _PURE_FALLBACK | _md_spec

        while i < len(body):
            instr = body[i]

            if instr.opcode == Opcode.Q_LABEL and instr.patch_id:
                loop_label = instr.patch_id
                loop_end = self._find_loop_back_edge(body, i + 1, loop_label)

                if loop_end is not None:
                    loop_body = body[i + 1 : loop_end]
                    back_edge = body[loop_end]

                    # Collect VRegs defined inside the loop
                    loop_defs: set[int] = set()
                    for lb in loop_body:
                        if isinstance(lb.dest, VReg):
                            loop_defs.add(lb.dest.index)

                    hoisted: list[QInstruction] = []
                    remaining: list[QInstruction] = []

                    for lb in loop_body:
                        if (lb.opcode in _PURE
                                and isinstance(lb.dest, VReg)
                                and self._operands_outside_loop(lb, loop_defs)):
                            hoisted.append(dc_replace(
                                lb, comment=lb.comment or "LICM-hoisted",
                            ))
                            # Remove from loop_defs — hoisted defs are now outside
                            loop_defs.discard(lb.dest.index)
                        else:
                            remaining.append(lb)

                    # Emit: hoisted → label → remaining body → back-edge
                    new_body.extend(hoisted)
                    new_body.append(instr)
                    new_body.extend(remaining)
                    new_body.append(back_edge)
                    i = loop_end + 1
                    continue

            new_body.append(instr)
            i += 1

        func.body = new_body

    @staticmethod
    def _operands_outside_loop(instr: QInstruction, loop_defs: set[int]) -> bool:
        """True if all source operands are defined outside the loop."""
        for op in (instr.src1, instr.src2):
            if isinstance(op, VReg) and op.index in loop_defs:
                return False
        return True

    # ── Loop Unrolling (with Epilogue) ─────────────────────
    _epilogue_counter: int = 0  # unique id for epilogue labels

    def _loop_unroll(self, func: QFunction) -> None:
        """Detect simple loops and unroll them by a configurable factor.

        Loop detection: find patterns of:
            Q_LABEL @loop_head
            ... body ...
            Q_JUMP_IF / Q_JUMP_IF_NOT → @loop_head (backward jump)
            or Q_JUMP → @loop_head (unconditional backward)

        Unroll strategy:
          1. Emit the main body duplicated *unroll_factor* times
             (handles ``N // factor`` groups of iterations).
          2. Emit an **epilogue loop** with one copy of the body and
             a backward conditional jump — this processes the
             ``N % factor`` remainder iterations correctly.

        Only unrolls small loops (body_size <= 32 instructions).
        """
        unroll_factor = getattr(self.cost_model, '_unroll_factor', 4)
        if unroll_factor <= 1:
            return

        MAX_LOOP_BODY = 32  # don't unroll large loops

        body = func.body
        new_body: list[QInstruction] = []
        i = 0

        while i < len(body):
            instr = body[i]

            # Detect loop head: Q_LABEL
            if instr.opcode == Opcode.Q_LABEL and instr.patch_id:
                loop_label = instr.patch_id
                # Scan forward for backward jump to this label
                loop_end = self._find_loop_back_edge(body, i + 1, loop_label)

                if loop_end is not None:
                    loop_body = body[i + 1 : loop_end]  # between label and back-edge
                    back_edge = body[loop_end]

                    if 1 <= len(loop_body) <= MAX_LOOP_BODY:
                        # ── Main unrolled body ──────────────
                        new_body.append(instr)  # Q_LABEL @loop_head
                        for _copy in range(unroll_factor):
                            for lb_instr in loop_body:
                                new_body.append(dc_replace(
                                    lb_instr,
                                    comment=lb_instr.comment or f"unroll#{_copy}",
                                ))
                        # Back-edge for the main unrolled loop
                        new_body.append(back_edge)

                        # ── Epilogue loop ───────────────────
                        # Handles remainder iterations (N % factor).
                        IROptimizer._epilogue_counter += 1
                        epi_label = f"_epi_{loop_label}_{IROptimizer._epilogue_counter}"
                        new_body.append(QInstruction(
                            opcode=Opcode.Q_LABEL,
                            patch_id=epi_label,
                            comment="epilogue loop head",
                        ))
                        for lb_instr in loop_body:
                            new_body.append(dc_replace(
                                lb_instr,
                                comment=lb_instr.comment or "epilogue",
                            ))
                        # Epilogue back-edge: same condition, jumps to epilogue label
                        epi_back = dc_replace(
                            back_edge,
                            src1=self._retarget_label(back_edge.src1, loop_label, epi_label),
                            src2=self._retarget_label(back_edge.src2, loop_label, epi_label),
                            comment="epilogue back-edge",
                        )
                        new_body.append(epi_back)

                        i = loop_end + 1
                        continue

            new_body.append(instr)
            i += 1

        func.body = new_body

    @staticmethod
    def _retarget_label(op, old_name: str, new_name: str):
        """Replace a Label operand's target if it matches *old_name*."""
        if isinstance(op, Label) and op.name == old_name:
            return Label(new_name)
        return op

    @staticmethod
    def _find_loop_back_edge(
        body: list[QInstruction], start: int, label_name: str
    ) -> int | None:
        """Find a backward jump to label_name within a reasonable distance."""
        for j in range(start, min(start + 40, len(body))):
            instr = body[j]
            if instr.opcode in (Opcode.Q_JUMP, Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT):
                # Check if jump target matches loop label
                for op in (instr.src1, instr.src2):
                    if isinstance(op, Label) and op.name == label_name:
                        return j
            # Another label means we left the loop scope
            if instr.opcode == Opcode.Q_LABEL and j > start:
                break
        return None

    # ── SIMD Vectorization Pass ────────────────────────────
    def _vectorize(self, func: QFunction) -> None:
        """Identify vectorizable sequences and convert to SIMD instructions.

        Strategy:
        1. Scan for consecutive independent same-opcode scalar operations
        2. Replace with vector equivalents if cost model says it's beneficial
        3. Emit scalar remainder for leftover iterations

        Requirements for vectorization:
        - Same opcode repeated consecutively on independent data
        - At least `lanes` consecutive operations
        - Cost model confirms speedup
        """
        lanes = self.cost_model.simd_lanes(4)  # float32 = 4 bytes
        if lanes < 2:
            return

        # Minimum count to justify pack/unpack overhead
        min_count = max(lanes, self.cost_model.min_vectorize_count)

        new_body: list[QInstruction] = []
        i = 0
        body = func.body

        while i < len(body):
            instr = body[i]

            # Only vectorize vectorizable ops
            if instr.opcode not in _SCALAR_TO_VECTOR:
                new_body.append(instr)
                i += 1
                continue

            # Try to collect a run of same-opcode instructions
            run: list[QInstruction] = [instr]
            j = i + 1
            while j < len(body) and j - i < lanes:
                next_instr = body[j]
                if next_instr.opcode != instr.opcode:
                    break
                # Check independence: dest of one shouldn't be src of another
                if self._has_dependency(run, next_instr):
                    break
                run.append(next_instr)
                j += 1

            # Need at least `lanes` instructions AND cost model must approve
            if len(run) >= lanes and len(run) >= min_count and self.cost_model.should_vectorize(
                instr.opcode, len(run), element_bytes=4
            ):
                vec_opcode = _SCALAR_TO_VECTOR[instr.opcode]
                vec_count = len(run) // lanes
                for vi in range(vec_count):
                    base = vi * lanes
                    first = run[base]
                    last = run[base + lanes - 1]

                    new_body.append(QInstruction(
                        opcode=vec_opcode,
                        dest=first.dest,
                        src1=first.src1,
                        src2=first.src2 if first.src2 is not None else last.dest,
                        comment=f"vectorized {lanes}× {instr.opcode.name}"
                                f" (v{base}..v{base + lanes - 1})",
                    ))

                # Remainder scalar instructions
                remainder_start = (len(run) // lanes) * lanes
                for ri in range(remainder_start, len(run)):
                    new_body.append(run[ri])

                i = j
            else:
                new_body.append(instr)
                i += 1

        func.body = new_body

    @staticmethod
    def _has_dependency(run: list[QInstruction], candidate: QInstruction) -> bool:
        """Check if candidate depends on any instruction in the run."""
        run_dests: set[int] = set()
        for r in run:
            if isinstance(r.dest, VReg):
                run_dests.add(r.dest.index)

        for op in (candidate.src1, candidate.src2):
            if isinstance(op, VReg) and op.index in run_dests:
                return True
        return False
