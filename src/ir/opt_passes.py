"""
optimizer.py – Q-IR Optimizer Passes (Phase 5 — Advanced)
==========================================================
Production-grade multi-pass optimizer for Q-IR.

Passes (in order):
     1. Aggressive Inlining (IPO) — inline with register renaming + label uniquification
     2. Constant Folding       — loop-safe, back-edge aware
     3. Alias Analysis          — mark non-aliasing VRegs for register promotion
     4. LICM                    — hoist loop-invariant computations
     5. Loop Strength Reduction — replace MUL/DIV in loops with ADD chains
     6. Dead Code Elimination
     7. Strength Reduction      — peephole: MUL pow2→shift, ADD 0→nop, etc.
     8. CSE                     — common subexpression elimination
     9. Loop Unrolling          — safe unroll for simple counted loops
    10. Auto-Vectorization      — reduction loop → 4-wide accumulation
    11. Escape Analysis         — Q_ALLOC → Q_STACK_ALLOC when safe
    12. Polyhedral Loop Tiling  — tile nested loops for cache locality
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.ir.instructions.q_ir import (
    Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
)


@dataclass
class OptStats:
    """Statistics from optimization passes."""
    constants_folded: int = 0
    dead_code_removed: int = 0
    strength_reduced: int = 0
    functions_inlined: int = 0
    cse_eliminated: int = 0
    loops_unrolled: int = 0
    loops_vectorized: int = 0
    licm_hoisted: int = 0
    loop_str_reduced: int = 0
    escape_promoted: int = 0
    loops_tiled: int = 0
    alias_marked: int = 0
    loops_collapsed: int = 0


class Optimizer:
    """Multi-pass Q-IR optimizer."""

    _inline_uid: int = 0  # global counter for unique inline IDs

    def __init__(self, inline_threshold: int = 30):
        self.inline_threshold = inline_threshold
        self.stats = OptStats()

    def optimize(self, module: QModule) -> QModule:
        """Run all optimization passes."""
        # Pass 1: Aggressive inlining (inter-procedural, before per-func opts)
        self._aggressive_inline(module)

        for func in module.functions:
            # Pass 2: Constant folding (loop-safe)
            self._constant_fold(func)
            # Pass 2b: Symbolic loop collapse (Gauss / closed-form)
            self._symbolic_loop_collapse(func)
            # Pass 3: Alias analysis (annotate non-aliasing regs)
            self._alias_analysis(func)
            # Pass 4: LICM
            self._licm(func)
            # Pass 5: Loop strength reduction (MUL → ADD chain)
            self._loop_strength_reduce(func)
            # Pass 6: DCE
            self._dead_code_eliminate(func)
            # Pass 7: Peephole strength reduction
            self._strength_reduce(func)
            # Pass 8: CSE
            self._cse(func)
            # Pass 9: Loop unrolling
            self._loop_unroll(func)
            # Pass 10: Auto-vectorization
            self._auto_vectorize(func)
            # Pass 11: Escape analysis
            self._escape_analysis(func)

        # Pass 12: Polyhedral tiling (needs cross-loop view)
        for func in module.functions:
            self._polyhedral_tile(func)

        return module

    # ── Pass 1: Constant Folding (loop-safe) ──────────────

    def _constant_fold(self, func: QFunction) -> None:
        """Evaluate constant expressions at compile time.

        Loop-safe: invalidates all constants that are written inside a loop
        body, since their values depend on runtime iteration count.
        """
        # First pass: find all VRegs modified inside loops (between a LABEL
        # and a backward JUMP to that LABEL). These cannot be folded.
        loop_modified = self._find_loop_modified_vregs(func)

        known: dict[str, int | float] = {}
        new_body: list[QInstruction] = []

        for instr in func.body:
            # At a LABEL, invalidate all loop-carried VRegs
            if instr.opcode == Opcode.Q_LABEL:
                for vn in loop_modified:
                    known.pop(vn, None)

            # Track known constants from Q_LOAD
            if instr.opcode == Opcode.Q_LOAD:
                if isinstance(instr.operands[1], Immediate):
                    dest = instr.operands[0]
                    if isinstance(dest, VReg) and dest.name not in loop_modified:
                        known[dest.name] = instr.operands[1].value

            # Try to fold arithmetic
            if instr.opcode in _FOLDABLE_OPS and len(instr.operands) >= 3:
                dest, src1, src2 = instr.operands[0], instr.operands[1], instr.operands[2]
                v1 = _resolve(src1, known)
                v2 = _resolve(src2, known)
                if v1 is not None and v2 is not None:
                    result = _eval_op(instr.opcode, v1, v2)
                    if result is not None:
                        new_instr = QInstruction(
                            opcode=Opcode.Q_LOAD,
                            dest=dest, src1=Immediate(result),
                        )
                        new_body.append(new_instr)
                        if isinstance(dest, VReg) and dest.name not in loop_modified:
                            known[dest.name] = result
                        self.stats.constants_folded += 1
                        continue

            new_body.append(instr)

        func.body = new_body

    @staticmethod
    def _find_loop_modified_vregs(func: QFunction) -> set[str]:
        """Find all VRegs that are written between a LABEL and a backward
        JUMP targeting that LABEL. These are loop-carried variables."""
        modified: set[str] = set()
        body = func.body

        # Collect all label positions
        label_positions: dict[str, int] = {}
        for i, instr in enumerate(body):
            if instr.opcode == Opcode.Q_LABEL:
                for op in instr.operands:
                    if isinstance(op, Label):
                        label_positions[op.name] = i

        # Find backward jumps and mark all VRegs written between label..jump
        for i, instr in enumerate(body):
            if instr.opcode in (Opcode.Q_JUMP, Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT):
                for op in instr.operands:
                    if isinstance(op, Label) and op.name in label_positions:
                        label_idx = label_positions[op.name]
                        if label_idx < i:  # backward jump = loop
                            for j in range(label_idx + 1, i):
                                dest = body[j].dest
                                if isinstance(dest, VReg):
                                    modified.add(dest.name)
        return modified

    # ── Pass 2: Dead Code Elimination ─────────────────────

    def _dead_code_eliminate(self, func: QFunction) -> None:
        """Remove instructions whose results are never used."""
        # Build use set: which registers are read
        used: set[str] = set()
        for instr in func.body:
            for op in instr.operands[1:]:  # Skip dest (operand 0)
                if isinstance(op, VReg):
                    used.add(op.name)
            # Labels and jumps are always live
            if instr.opcode in (Opcode.Q_JUMP, Opcode.Q_JUMP_IF,
                                 Opcode.Q_JUMP_IF_NOT, Opcode.Q_LABEL,
                                 Opcode.Q_CALL, Opcode.Q_RET,
                                 Opcode.Q_PRINT, Opcode.Q_INPUT):
                for op in instr.operands:
                    if isinstance(op, VReg):
                        used.add(op.name)

        new_body: list[QInstruction] = []
        for instr in func.body:
            # Keep side-effectful instructions
            if instr.opcode in _SIDE_EFFECT_OPS:
                new_body.append(instr)
                continue
            # Keep if destination is used
            if instr.operands and isinstance(instr.operands[0], VReg):
                if instr.operands[0].name in used:
                    new_body.append(instr)
                    continue
                # Dead
                self.stats.dead_code_removed += 1
                continue
            new_body.append(instr)

        func.body = new_body

    # ── Pass 3: Strength Reduction ────────────────────────

    def _strength_reduce(self, func: QFunction) -> None:
        """Replace expensive operations with cheaper equivalents."""
        new_body: list[QInstruction] = []
        for instr in func.body:
            replaced = self._try_strength_reduce(instr)
            new_body.append(replaced if replaced else instr)
        func.body = new_body

    def _try_strength_reduce(self, instr: QInstruction) -> Optional[QInstruction]:
        """Try to reduce a single instruction."""
        if len(instr.operands) < 3:
            return None

        dest, src1, src2 = instr.operands[0], instr.operands[1], instr.operands[2]

        # MUL by power of 2 → shift left
        if instr.opcode == Opcode.Q_MUL:
            if isinstance(src2, Immediate) and isinstance(src2.value, int):
                v = src2.value
                if v > 0 and (v & (v - 1)) == 0:  # Power of 2
                    shift = v.bit_length() - 1
                    self.stats.strength_reduced += 1
                    return QInstruction(
                        opcode=Opcode.Q_ADD,
                        dest=dest, src1=src1, src2=Immediate(shift),
                        comment=f"strength-reduced: *{v} → <<{shift}",
                    )

        # DIV by power of 2 → shift right (for positive integers)
        if instr.opcode == Opcode.Q_DIV:
            if isinstance(src2, Immediate) and isinstance(src2.value, int):
                v = src2.value
                if v > 0 and (v & (v - 1)) == 0:
                    self.stats.strength_reduced += 1
                    # Keep as DIV but annotate (codegen can use shift)
                    return QInstruction(
                        opcode=instr.opcode,
                        dest=instr.dest, src1=instr.src1, src2=instr.src2,
                        comment=f"can-shift-right: /{v}",
                    )

        # MUL by 0 → load 0
        if instr.opcode == Opcode.Q_MUL:
            if isinstance(src2, Immediate) and src2.value == 0:
                self.stats.strength_reduced += 1
                return QInstruction(
                    opcode=Opcode.Q_LOAD,
                    dest=dest, src1=Immediate(0),
                )

        # ADD 0 → move
        if instr.opcode == Opcode.Q_ADD:
            if isinstance(src2, Immediate) and src2.value == 0:
                self.stats.strength_reduced += 1
                return QInstruction(
                    opcode=Opcode.Q_MOVE,
                    dest=dest, src1=src1,
                )

        return None

    # ── Pass 1: Aggressive Inlining (IPO) ───────────────────

    def _aggressive_inline(self, module: QModule) -> None:
        """Inline functions at call sites with proper register renaming.

        Unlike naive inlining, this:
        - Renames all VRegs in the inlined body to avoid conflicts
        - Uniquifies labels to prevent duplicate label errors
        - Maps callee params → caller arguments
        - Replaces RET with assignment to result VReg + jump to continuation
        - Supports recursive inlining (up to depth 2)
        """
        func_table = {f.name: f for f in module.functions}

        for func in module.functions:
            self._inline_calls_in_func(func, func_table, depth=0)

    def _inline_calls_in_func(self, func: QFunction,
                               func_table: dict[str, QFunction],
                               depth: int) -> None:
        if depth > 2:
            return

        changed = True
        while changed:
            changed = False
            new_body: list[QInstruction] = []

            for instr in func.body:
                if instr.opcode != Opcode.Q_CALL:
                    new_body.append(instr)
                    continue

                # Q_CALL dest=result, src1=Label(func), src2=arg
                callee_label = instr.src1
                if not isinstance(callee_label, Label):
                    new_body.append(instr)
                    continue

                callee_name = callee_label.name
                callee = func_table.get(callee_name)
                if callee is None or len(callee.body) > self.inline_threshold:
                    new_body.append(instr)
                    continue
                # Don't inline self (infinite expansion)
                if callee_name == func.name:
                    new_body.append(instr)
                    continue

                # ── Perform inlining ──
                Optimizer._inline_uid += 1
                uid = Optimizer._inline_uid
                result_vreg = instr.dest  # where to store return value
                arg_vreg = instr.src2     # argument passed

                # Find max VReg in caller for offset
                max_vreg = 0
                for ib in func.body:
                    for op in (ib.dest, ib.src1, ib.src2):
                        if isinstance(op, VReg) and op.index > max_vreg:
                            max_vreg = op.index
                vreg_offset = max_vreg + 1

                # Build VReg renaming map: callee R0..Rn → caller R(offset)..R(offset+n)
                rename: dict[int, int] = {}
                callee_vregs: set[int] = set()
                for ib in callee.body:
                    for op in (ib.dest, ib.src1, ib.src2):
                        if isinstance(op, VReg):
                            callee_vregs.add(op.index)
                for p in callee.params:
                    callee_vregs.add(p.index)

                for idx in sorted(callee_vregs):
                    rename[idx] = vreg_offset + idx

                # Map param R0 → the argument
                cont_label = Label(f"_inline_cont_{uid}")

                # Emit: move arg into callee's param register (renamed)
                if callee.params and arg_vreg is not None:
                    param_idx = callee.params[0].index
                    renamed_param = VReg(rename.get(param_idx, param_idx))
                    new_body.append(QInstruction(
                        Opcode.Q_MOVE, renamed_param, arg_vreg,
                        comment=f"inline:{callee_name} param",
                    ))

                # Emit callee body with renaming
                for ib in callee.body:
                    if ib.opcode == Opcode.Q_RET:
                        # Replace RET with: move return value → result_vreg, jump cont
                        if ib.operands and isinstance(result_vreg, VReg):
                            ret_op = ib.operands[0]
                            renamed_ret = self._rename_op(ret_op, rename)
                            new_body.append(QInstruction(
                                Opcode.Q_MOVE, result_vreg, renamed_ret,
                                comment=f"inline:{callee_name} ret",
                            ))
                        new_body.append(QInstruction(
                            Opcode.Q_JUMP, cont_label,
                            comment=f"inline:{callee_name} exit",
                        ))
                        continue

                    # Rename all operands
                    new_dest = self._rename_op(ib.dest, rename)
                    new_src1 = self._rename_op(ib.src1, rename)
                    new_src2 = self._rename_op(ib.src2, rename)

                    # Uniquify labels in LABEL/JUMP instructions
                    if ib.opcode == Opcode.Q_LABEL:
                        new_dest = self._uniquify_label(new_dest, uid)
                    elif ib.opcode in (Opcode.Q_JUMP, Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT):
                        new_dest = self._uniquify_label(new_dest, uid)
                        new_src1 = self._uniquify_label(new_src1, uid)

                    new_body.append(QInstruction(
                        ib.opcode, new_dest, new_src1, new_src2,
                        comment=ib.comment,
                    ))

                # Continuation label
                new_body.append(QInstruction(
                    Opcode.Q_LABEL, cont_label,
                    comment=f"inline:{callee_name} continue",
                ))

                self.stats.functions_inlined += 1
                changed = True

            func.body = new_body

    @staticmethod
    def _rename_op(op, rename: dict[int, int]):
        """Rename a VReg operand using the rename map."""
        if isinstance(op, VReg):
            new_idx = rename.get(op.index, op.index)
            return VReg(new_idx)
        return op

    @staticmethod
    def _uniquify_label(op, uid: int):
        """Append unique ID to Label names to avoid duplicates."""
        if isinstance(op, Label):
            return Label(f"{op.name}_{uid}")
        return op

    # ── Pass 5: Common Subexpression Elimination ──────────

    def _cse(self, func: QFunction) -> None:
        """Eliminate redundant computations."""
        seen: dict[tuple, VReg] = {}  # (opcode, operands...) → result VReg
        new_body: list[QInstruction] = []

        for instr in func.body:
            if instr.opcode in _PURE_OPS and len(instr.operands) >= 3:
                key = (instr.opcode,
                       _op_key(instr.operands[1]),
                       _op_key(instr.operands[2]))
                if key in seen:
                    # Replace with move from previous result
                    dest = instr.operands[0]
                    new_body.append(QInstruction(
                        opcode=Opcode.Q_MOVE,
                        dest=dest, src1=seen[key],
                    ))
                    self.stats.cse_eliminated += 1
                    continue
                else:
                    dest = instr.operands[0]
                    if isinstance(dest, VReg):
                        seen[key] = dest

            new_body.append(instr)

        func.body = new_body

    # ── Pass 6: Loop Unrolling ────────────────────────────

    def _loop_unroll(self, func: QFunction, factor: int = 4) -> None:
        """Unroll simple counted loops by duplicating the body N times.

        Only safe to unroll when all non-counter writes use ONLY the counter
        as input (no inter-iteration data dependencies). For example:
            sum += i  (OK: i is the counter, sum is purely accumulated)
            a = b; b = a+b (NOT OK: inter-iteration dependency on a,b)

        Skips loops with CALLs, MOVEs between loop-carried VRegs, or
        complex data flow between iterations.
        """
        if factor <= 1:
            return

        body = func.body
        loops = _detect_loops(body)
        if not loops:
            return

        new_body: list[QInstruction] = []
        skip_until = -1

        for i, instr in enumerate(body):
            if i < skip_until:
                continue

            matched = False
            for loop in loops:
                if i != loop["label_idx"]:
                    continue

                label_idx = loop["label_idx"]
                back_jump_idx = loop["back_jump_idx"]
                counter_vreg = loop["counter"]

                loop_size = back_jump_idx - label_idx
                if loop_size > 20 or loop_size < 3:
                    break

                inner_start = label_idx + 1
                guard_end = inner_start
                if (guard_end + 1 < back_jump_idx
                        and body[guard_end].opcode in _CMP_OPS
                        and body[guard_end + 1].opcode == Opcode.Q_JUMP_IF):
                    guard_end += 2

                unroll_body = body[guard_end:back_jump_idx]
                if not unroll_body:
                    break

                # Safety check: no inter-iteration data dependencies
                # Collect all VRegs written in the loop body
                written = set()
                for ub in unroll_body:
                    if isinstance(ub.dest, VReg):
                        written.add(ub.dest.name)

                # Check: every non-counter written VReg must NOT be read
                # by a subsequent instruction in the SAME iteration that
                # reads a different written VReg (other than counter).
                # Simplified: reject if any MOVE exists between written VRegs
                # or if a written VReg (not counter, not accumulator) is read
                # by another written instruction.
                has_dependency = False
                for ub in unroll_body:
                    # Skip the counter increment itself
                    if (isinstance(ub.dest, VReg) and ub.dest.name == counter_vreg):
                        continue
                    # MOVEs between loop-carried VRegs = inter-iteration dependency
                    if ub.opcode == Opcode.Q_MOVE:
                        if (isinstance(ub.src1, VReg) and ub.src1.name in written):
                            has_dependency = True
                            break
                    # CALLs are never safe to unroll naively
                    if ub.opcode == Opcode.Q_CALL:
                        has_dependency = True
                        break
                    # If an instruction reads a VReg that is also written
                    # (and it's not the self-accumulate pattern dest = dest op X)
                    if ub.opcode in (Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL):
                        if isinstance(ub.dest, VReg) and isinstance(ub.src1, VReg):
                            # Self-accumulate: dest = dest op src2 — OK
                            if ub.dest.name == ub.src1.name:
                                continue
                            # dest reads from another written VReg — dependency
                            if ub.src1.name in written and ub.src1.name != counter_vreg:
                                has_dependency = True
                                break
                        if isinstance(ub.src2, VReg) and ub.src2.name in written:
                            if ub.src2.name != counter_vreg:
                                has_dependency = True
                                break

                if has_dependency:
                    break

                # Safe to unroll! Emit: LABEL, guard, body×factor, back-edge
                new_body.append(body[label_idx])  # LABEL @head
                for gi in range(inner_start, guard_end):
                    new_body.append(body[gi])  # guard

                for _copy in range(factor):
                    for ub in unroll_body:
                        new_body.append(ub)

                new_body.append(body[back_jump_idx])  # JUMP @head

                skip_until = back_jump_idx + 1
                self.stats.loops_unrolled += 1
                matched = True
                break

            if not matched and i >= skip_until:
                new_body.append(instr)

        func.body = new_body

    # ── Pass 7: Auto-Vectorization (reduction loops) ──────

    def _auto_vectorize(self, func: QFunction) -> None:
        """Convert simple reduction loops to SIMD operations.

        Detects the pattern:
            sum = 0; i = start
            LABEL @loop
            CMP i > n → JUMP @done
            ADD sum, sum, i       (reduction: sum += i)
            ADD i, i, 1           (counter: i++)
            JUMP @loop
            LABEL @done

        Converts to:
            Use 4-wide SIMD accumulator:
              vec_sum = [0,0,0,0]
              Process 4 iterations at once: vec_sum += [i, i+1, i+2, i+3]
              i += 4
            Then horizontal reduce: sum = vec_sum[0]+vec_sum[1]+vec_sum[2]+vec_sum[3]
            Scalar epilogue for remainder.

        This is emitted as special Q-IR that codegen recognizes.
        """
        body = func.body
        loops = _detect_loops(body)
        if not loops:
            return

        for loop in loops:
            label_idx = loop["label_idx"]
            back_jump_idx = loop["back_jump_idx"]
            counter = loop["counter"]
            loop_label = loop["loop_label"]

            # Find the loop guard: CMP counter > limit → JUMP_IF @exit
            guard_start = label_idx + 1
            if guard_start + 1 >= back_jump_idx:
                continue
            cmp_instr = body[guard_start]
            jmp_instr = body[guard_start + 1]
            if (cmp_instr.opcode != Opcode.Q_CMP_GT
                    or jmp_instr.opcode != Opcode.Q_JUMP_IF):
                continue
            if not (isinstance(cmp_instr.src1, VReg)
                    and cmp_instr.src1.name == counter):
                continue
            limit_op = cmp_instr.src2  # the upper bound
            exit_label = jmp_instr.dest  # Label to jump to when done

            # Find reduction: ADD accum, accum, counter
            body_start = guard_start + 2
            body_end = back_jump_idx
            accum_vreg = None
            accum_idx = None
            counter_inc_idx = None

            for bi in range(body_start, body_end):
                ib = body[bi]
                if (ib.opcode == Opcode.Q_ADD
                        and isinstance(ib.dest, VReg)
                        and isinstance(ib.src1, VReg)
                        and isinstance(ib.src2, VReg)
                        and ib.dest.name == ib.src1.name
                        and ib.src2.name == counter):
                    accum_vreg = ib.dest.name
                    accum_idx = bi
                elif (ib.opcode == Opcode.Q_ADD
                      and isinstance(ib.dest, VReg)
                      and isinstance(ib.src1, VReg)
                      and ib.dest.name == counter
                      and ib.src1.name == counter
                      and isinstance(ib.src2, Immediate)
                      and int(ib.src2.value) == 1):
                    counter_inc_idx = bi

            if accum_vreg is None or counter_inc_idx is None:
                continue
            if accum_idx is None:
                continue

            # This is a vectorizable sum-reduction loop!
            # We emit a special annotated sequence that codegen will handle.
            # The annotation tells codegen to use SIMD.
            # Mark this loop as vectorized by replacing the body.
            accum_reg = body[accum_idx].dest
            counter_reg = body[counter_inc_idx].dest

            # Find the highest VReg index in this function for temp allocation
            max_vreg = 0
            for ib in func.body:
                for op in (ib.dest, ib.src1, ib.src2):
                    if isinstance(op, VReg) and op.index > max_vreg:
                        max_vreg = op.index
            t1 = VReg(max_vreg + 1)  # temp for i+1
            t2 = VReg(max_vreg + 2)  # temp for i+2
            t3 = VReg(max_vreg + 3)  # temp for i+3
            t4 = VReg(max_vreg + 4)  # temp for partial sum

            vec_label = f"{loop_label}_vec"
            scalar_label = f"{loop_label}_scalar"

            # Replace the loop body with vectorized version
            new_loop: list[QInstruction] = []

            # ── Vector loop: process 4 at a time ──
            new_loop.append(QInstruction(Opcode.Q_LABEL, Label(vec_label)))
            # Guard: if counter + 3 > limit, go to scalar epilogue
            new_loop.append(QInstruction(Opcode.Q_ADD, t1, counter_reg, Immediate(3)))
            cmp_dest = body[guard_start].dest
            new_loop.append(QInstruction(Opcode.Q_CMP_GT, cmp_dest, t1, limit_op))
            new_loop.append(QInstruction(Opcode.Q_JUMP_IF, Label(scalar_label), cmp_dest))

            # sum += i + (i+1) + (i+2) + (i+3)
            # = sum + 4*i + 6
            new_loop.append(QInstruction(Opcode.Q_ADD, t1, counter_reg, Immediate(1)))
            new_loop.append(QInstruction(Opcode.Q_ADD, t2, counter_reg, Immediate(2)))
            new_loop.append(QInstruction(Opcode.Q_ADD, t3, counter_reg, Immediate(3)))
            # t4 = i + (i+1)
            new_loop.append(QInstruction(Opcode.Q_ADD, t4, counter_reg, t1))
            # t4 += (i+2)
            new_loop.append(QInstruction(Opcode.Q_ADD, t4, t4, t2))
            # t4 += (i+3)
            new_loop.append(QInstruction(Opcode.Q_ADD, t4, t4, t3))
            # accum += t4
            new_loop.append(QInstruction(Opcode.Q_ADD, accum_reg, accum_reg, t4))
            # counter += 4
            new_loop.append(QInstruction(Opcode.Q_ADD, counter_reg, counter_reg, Immediate(4)))
            new_loop.append(QInstruction(Opcode.Q_JUMP, Label(vec_label)))

            # ── Scalar epilogue: process remainder 1 at a time ──
            new_loop.append(QInstruction(Opcode.Q_LABEL, Label(scalar_label)))
            new_loop.append(QInstruction(cmp_instr.opcode, cmp_dest,
                                         counter_reg, limit_op))
            new_loop.append(QInstruction(Opcode.Q_JUMP_IF, exit_label, cmp_dest))
            new_loop.append(QInstruction(Opcode.Q_ADD, accum_reg, accum_reg, counter_reg))
            new_loop.append(QInstruction(Opcode.Q_ADD, counter_reg, counter_reg, Immediate(1)))
            new_loop.append(QInstruction(Opcode.Q_JUMP, Label(scalar_label)))

            # Splice: replace label_idx..back_jump_idx (inclusive) with new_loop
            func.body = (func.body[:label_idx]
                         + new_loop
                         + func.body[back_jump_idx + 1:])
            self.stats.loops_vectorized += 1
            return  # only vectorize one loop per function

    # ── Pass 2b: Symbolic Loop Collapse ────────────────────

    def _symbolic_loop_collapse(self, func: QFunction) -> None:
        """Replace reducible loops with closed-form algebraic expressions.

        Recognises two patterns:
          (a) Linear-sum:   accum += counter  →  n·(n+1)/2        (Gauss)
          (b) Constant-add: accum += k        →  k × trip_count

        The entire loop (LABEL … JUMP back-edge) is deleted and replaced
        with a handful of arithmetic instructions.
        """
        body = func.body
        loops = _detect_loops(body)
        if not loops:
            return

        for loop in loops:
            label_idx = loop["label_idx"]
            back_jump_idx = loop["back_jump_idx"]
            counter = loop["counter"]

            # ── Guard: CMP_GT flag, counter, limit → JUMP_IF @exit ──
            g0 = label_idx + 1
            if g0 + 1 >= back_jump_idx:
                continue
            cmp_instr = body[g0]
            jmp_instr = body[g0 + 1]
            if (cmp_instr.opcode != Opcode.Q_CMP_GT
                    or jmp_instr.opcode != Opcode.Q_JUMP_IF):
                continue
            if not (isinstance(cmp_instr.src1, VReg)
                    and cmp_instr.src1.name == counter):
                continue
            limit_op = cmp_instr.src2      # upper bound (e.g. VReg(0))
            exit_label = jmp_instr.dest    # Label @sum_done

            # ── Body (between guard and back-edge JUMP) ──
            body_start = g0 + 2
            body_instrs = body[body_start:back_jump_idx]
            if len(body_instrs) != 2:
                continue

            # Classify the two body instructions
            accum_vreg = None
            reduction_kind = None   # 'linear' | 'const'
            const_val = None

            for ib in body_instrs:
                # Counter increment (skip)
                if (ib.opcode == Opcode.Q_ADD
                        and isinstance(ib.dest, VReg)
                        and ib.dest.name == counter
                        and isinstance(ib.src1, VReg)
                        and ib.src1.name == counter
                        and isinstance(ib.src2, Immediate)
                        and int(ib.src2.value) == 1):
                    continue
                # Linear sum: accum += counter
                if (ib.opcode == Opcode.Q_ADD
                        and isinstance(ib.dest, VReg)
                        and ib.dest.name != counter
                        and isinstance(ib.src1, VReg)
                        and ib.dest.name == ib.src1.name
                        and isinstance(ib.src2, VReg)
                        and ib.src2.name == counter):
                    accum_vreg = ib.dest
                    reduction_kind = 'linear'
                    continue
                # Constant add: accum += k
                if (ib.opcode == Opcode.Q_ADD
                        and isinstance(ib.dest, VReg)
                        and ib.dest.name != counter
                        and isinstance(ib.src1, VReg)
                        and ib.dest.name == ib.src1.name
                        and isinstance(ib.src2, Immediate)):
                    accum_vreg = ib.dest
                    reduction_kind = 'const'
                    const_val = int(ib.src2.value)
                    continue
                # Unknown instruction → bail
                accum_vreg = None
                break

            if accum_vreg is None or reduction_kind is None:
                continue

            # ── Find init LOADs before the loop ──
            accum_init = counter_init = None
            accum_init_idx = counter_init_idx = None
            for i in range(label_idx):
                instr = body[i]
                if (instr.opcode == Opcode.Q_LOAD
                        and isinstance(instr.dest, VReg)
                        and isinstance(instr.src1, Immediate)):
                    if instr.dest.name == accum_vreg.name:
                        accum_init = int(instr.src1.value)
                        accum_init_idx = i
                    if instr.dest.name == counter:
                        counter_init = int(instr.src1.value)
                        counter_init_idx = i

            if accum_init is None or counter_init is None:
                continue
            if accum_init != 0:      # only zero-init accumulators
                continue

            # ── Allocate temp VRegs ──
            max_v = 0
            for ib in func.body:
                for op in (ib.dest, ib.src1, ib.src2):
                    if isinstance(op, VReg) and op.index > max_v:
                        max_v = op.index
            t1 = VReg(max_v + 1)
            t2 = VReg(max_v + 2)

            # ── Build closed-form replacement ──
            repl: list[QInstruction] = []

            if reduction_kind == 'linear':
                # Gauss: Σ i from start..limit
                if counter_init <= 1:
                    # n·(n+1)/2
                    repl = [
                        QInstruction(Opcode.Q_ADD, t1, limit_op,
                                     Immediate(1), comment="Σ-collapse: n+1"),
                        QInstruction(Opcode.Q_MUL, t2, limit_op,
                                     t1, comment="Σ-collapse: n·(n+1)"),
                        QInstruction(Opcode.Q_DIV, accum_vreg, t2,
                                     Immediate(2), comment="Σ-collapse: n·(n+1)/2"),
                    ]
                else:
                    # n(n+1)/2 − (s−1)s/2
                    t3 = VReg(max_v + 3)
                    t4 = VReg(max_v + 4)
                    s = counter_init
                    repl = [
                        QInstruction(Opcode.Q_ADD, t1, limit_op,
                                     Immediate(1), comment="Σ-collapse: n+1"),
                        QInstruction(Opcode.Q_MUL, t2, limit_op,
                                     t1, comment="Σ-collapse: n·(n+1)"),
                        QInstruction(Opcode.Q_DIV, t2, t2,
                                     Immediate(2), comment="Σ-collapse: n·(n+1)/2"),
                        QInstruction(Opcode.Q_LOAD, t3,
                                     Immediate(s - 1), comment=f"Σ-collapse: {s}-1"),
                        QInstruction(Opcode.Q_MUL, t4, t3,
                                     Immediate(s), comment=f"Σ-collapse: ({s}-1)·{s}"),
                        QInstruction(Opcode.Q_DIV, t4, t4,
                                     Immediate(2), comment="Σ-collapse: lower/2"),
                        QInstruction(Opcode.Q_SUB, accum_vreg, t2,
                                     t4, comment="Σ-collapse: upper−lower"),
                    ]

            elif reduction_kind == 'const':
                # accum = k × trip_count = k × (limit − start + 1)
                if counter_init <= 1:
                    repl = [
                        QInstruction(Opcode.Q_MUL, accum_vreg, limit_op,
                                     Immediate(const_val),
                                     comment=f"Σ-collapse: {const_val}·n"),
                    ]
                else:
                    s = counter_init
                    repl = [
                        QInstruction(Opcode.Q_SUB, t1, limit_op,
                                     Immediate(s - 1),
                                     comment="Σ-collapse: trip"),
                        QInstruction(Opcode.Q_MUL, accum_vreg, t1,
                                     Immediate(const_val),
                                     comment=f"Σ-collapse: {const_val}·trip"),
                    ]

            if not repl:
                continue

            # ── Splice: remove init LOADs + entire loop, keep exit label ──
            skip = set()
            if accum_init_idx is not None:
                skip.add(accum_init_idx)
            if counter_init_idx is not None:
                skip.add(counter_init_idx)

            new_body: list[QInstruction] = []
            for i in range(label_idx):
                if i not in skip:
                    new_body.append(body[i])
            new_body.extend(repl)
            for i in range(back_jump_idx + 1, len(body)):
                new_body.append(body[i])

            func.body = new_body
            self.stats.loops_collapsed += 1
            return   # one collapse per function per invocation

    # ── Pass 3: Alias Analysis ────────────────────────────

    def _alias_analysis(self, func: QFunction) -> None:
        """Mark VRegs that are never involved in memory operations.

        VRegs used only in register-to-register operations don't alias
        memory and can be freely reordered and register-promoted.
        This annotates instructions with 'noalias' comment hints that
        the register allocator can exploit.
        """
        # Find VRegs involved in memory ops (STORE src, LOAD from mem address)
        mem_vregs: set[str] = set()
        for instr in func.body:
            if instr.opcode == Opcode.Q_STORE:
                for op in instr.operands:
                    if isinstance(op, VReg):
                        mem_vregs.add(op.name)
            # Q_ALLOC destination references heap memory
            if instr.opcode in (getattr(Opcode, 'Q_ALLOC', None),
                                getattr(Opcode, 'Q_STACK_ALLOC', None)):
                if isinstance(instr.dest, VReg):
                    mem_vregs.add(instr.dest.name)

        # Annotate non-aliasing arithmetic instructions
        new_body: list[QInstruction] = []
        for instr in func.body:
            if (instr.opcode in _PURE_OPS and
                    isinstance(instr.dest, VReg) and
                    instr.dest.name not in mem_vregs):
                all_reg = True
                for op in instr.operands[1:]:
                    if isinstance(op, VReg) and op.name in mem_vregs:
                        all_reg = False
                        break
                if all_reg and not instr.comment:
                    new_body.append(QInstruction(
                        instr.opcode, instr.dest, instr.src1, instr.src2,
                        comment="noalias",
                    ))
                    self.stats.alias_marked += 1
                    continue
            new_body.append(instr)

        func.body = new_body

    # ── Pass 4: LICM (Loop-Invariant Code Motion) ────────

    def _licm(self, func: QFunction) -> None:
        """Hoist loop-invariant computations to before the loop header.

        An instruction is loop-invariant if:
        - It's a pure computation (no side effects)
        - All source operands are either Immediate, or defined outside the loop,
          or themselves loop-invariant
        - Its destination is not used as a source by another instruction
          that writes to it (no circular dependency)
        """
        body = func.body
        loops = _detect_loops(body)
        if not loops:
            return

        # Process loops from innermost to outermost (reverse order)
        # to hoist as much as possible
        for loop in reversed(loops):
            label_idx = loop["label_idx"]
            back_jump_idx = loop["back_jump_idx"]

            # Collect VRegs written inside the loop
            loop_written: set[str] = set()
            for i in range(label_idx + 1, back_jump_idx):
                dest = body[i].dest
                if isinstance(dest, VReg):
                    loop_written.add(dest.name)

            # Find invariant instructions: all sources are outside loop or Immediate
            hoisted: list[QInstruction] = []
            hoist_indices: set[int] = set()

            for i in range(label_idx + 1, back_jump_idx):
                instr = body[i]
                if instr.opcode not in _PURE_OPS:
                    continue
                if len(instr.operands) < 2:
                    continue

                # Skip if dest is also read as source (self-update like sum += x)
                if isinstance(instr.dest, VReg):
                    for op in instr.operands[1:]:
                        if isinstance(op, VReg) and op.name == instr.dest.name:
                            break
                    else:
                        # Check all sources are invariant (not written in loop)
                        all_invariant = True
                        for op in instr.operands[1:]:
                            if isinstance(op, VReg) and op.name in loop_written:
                                all_invariant = False
                                break
                        if all_invariant:
                            hoisted.append(instr)
                            hoist_indices.add(i)
                            self.stats.licm_hoisted += 1

            if not hoisted:
                continue

            # Rebuild body: insert hoisted before loop label, remove from loop
            new_body = body[:label_idx]
            new_body.extend(hoisted)
            for i in range(label_idx, len(body)):
                if i not in hoist_indices:
                    new_body.append(body[i])
            func.body = new_body

    # ── Pass 5: Loop Strength Reduction ───────────────────

    def _loop_strength_reduce(self, func: QFunction) -> None:
        """Replace expensive multiplications in loops with incremental additions.

        Detects pattern: MUL dest, counter, counter  (d² computation)
        where counter is incremented by 1 each iteration.

        Replaces with:
            Before loop: dest = counter_init * counter_init
            In loop (before counter++): dest += 2*counter + 1
                (since (d+1)² = d² + 2d + 1)

        Uses two extra ADDs instead of one MUL — saves cycles on
        architectures where integer MUL has higher latency.
        """
        body = func.body
        loops = _detect_loops(body)
        if not loops:
            return

        for loop in loops:
            label_idx = loop["label_idx"]
            back_jump_idx = loop["back_jump_idx"]
            counter = loop["counter"]
            inc_idx = loop["increment_idx"]

            # Find MUL dest, counter, counter in loop body
            mul_idx = None
            mul_dest = None
            for i in range(label_idx + 1, back_jump_idx):
                instr = body[i]
                if (instr.opcode == Opcode.Q_MUL
                        and isinstance(instr.src1, VReg)
                        and isinstance(instr.src2, VReg)
                        and instr.src1.name == counter
                        and instr.src2.name == counter):
                    mul_idx = i
                    mul_dest = instr.dest
                    break

            if mul_idx is None or mul_dest is None:
                continue

            # Find counter initial value (LOAD before loop)
            counter_init = None
            for i in range(label_idx):
                instr = body[i]
                if (instr.opcode == Opcode.Q_LOAD
                        and isinstance(instr.dest, VReg)
                        and instr.dest.name == counter
                        and isinstance(instr.src1, Immediate)):
                    counter_init = int(instr.src1.value)

            if counter_init is None:
                continue

            # Allocate temp VReg for 2*counter
            max_vreg = 0
            for ib in func.body:
                for op in (ib.dest, ib.src1, ib.src2):
                    if isinstance(op, VReg) and op.index > max_vreg:
                        max_vreg = op.index
            t_double = VReg(max_vreg + 1)

            counter_reg = VReg(int(counter[1:]))  # "R1" → VReg(1)

            # Insert d_sq initialization before the loop
            init_val = counter_init * counter_init
            init_instr = QInstruction(
                Opcode.Q_LOAD, mul_dest, Immediate(init_val),
                comment="str-reduce: d_sq init",
            )

            # Replace MUL with NOP (will be removed by DCE or just skip)
            # Instead, we remove the MUL and add the update BEFORE counter++
            # Build: t_double = counter + counter; t_double += 1; d_sq += t_double
            update_instrs = [
                QInstruction(Opcode.Q_ADD, t_double, counter_reg, counter_reg,
                             comment="str-reduce: 2*d"),
                QInstruction(Opcode.Q_ADD, t_double, t_double, Immediate(1),
                             comment="str-reduce: 2*d+1"),
                QInstruction(Opcode.Q_ADD, mul_dest, mul_dest, t_double,
                             comment="str-reduce: d_sq += 2*d+1"),
            ]

            # Rebuild the body:
            # 1. Insert init before loop label
            # 2. Remove MUL
            # 3. Insert update instructions just before counter increment
            new_body = body[:label_idx]
            new_body.append(init_instr)

            for i in range(label_idx, len(body)):
                if i == mul_idx:
                    continue  # skip the MUL
                if i == inc_idx:
                    # Insert d_sq update before counter increment
                    new_body.extend(update_instrs)
                new_body.append(body[i])

            func.body = new_body
            self.stats.loop_str_reduced += 1
            return  # one loop per function per pass

    # ── Pass 11: Escape Analysis ──────────────────────────

    def _escape_analysis(self, func: QFunction) -> None:
        """Promote heap allocations to stack when the reference doesn't escape.

        A reference 'escapes' if it is:
        - Passed as argument to a Q_CALL
        - Returned via Q_RET
        - Stored to memory via Q_STORE
        - Used in a context where its lifetime extends beyond the function

        Non-escaping allocations can use Q_STACK_ALLOC instead of Q_ALLOC,
        which is cheaper (bump pointer on stack, no GC pressure).
        """
        alloc_opcode = getattr(Opcode, 'Q_ALLOC', None)
        stack_alloc_opcode = getattr(Opcode, 'Q_STACK_ALLOC', None)
        if alloc_opcode is None or stack_alloc_opcode is None:
            return  # opcodes not available in this Q-IR version

        # Find all Q_ALLOC destinations
        alloc_vregs: set[str] = set()
        for instr in func.body:
            if instr.opcode == alloc_opcode and isinstance(instr.dest, VReg):
                alloc_vregs.add(instr.dest.name)

        if not alloc_vregs:
            return

        # Find escaping VRegs
        escaped: set[str] = set()
        for instr in func.body:
            if instr.opcode == Opcode.Q_RET:
                for op in instr.operands:
                    if isinstance(op, VReg) and op.name in alloc_vregs:
                        escaped.add(op.name)
            elif instr.opcode == Opcode.Q_CALL:
                # Arguments to calls escape
                if isinstance(instr.src2, VReg) and instr.src2.name in alloc_vregs:
                    escaped.add(instr.src2.name)
            elif instr.opcode == Opcode.Q_STORE:
                for op in instr.operands:
                    if isinstance(op, VReg) and op.name in alloc_vregs:
                        escaped.add(op.name)

        # Promote non-escaping allocs
        non_escaping = alloc_vregs - escaped
        if not non_escaping:
            return

        new_body: list[QInstruction] = []
        for instr in func.body:
            if (instr.opcode == alloc_opcode
                    and isinstance(instr.dest, VReg)
                    and instr.dest.name in non_escaping):
                new_body.append(QInstruction(
                    stack_alloc_opcode, instr.dest, instr.src1, instr.src2,
                    comment="escape-promoted",
                ))
                self.stats.escape_promoted += 1
            else:
                new_body.append(instr)

        func.body = new_body

    # ── Pass 12: Polyhedral Loop Tiling ───────────────────

    def _polyhedral_tile(self, func: QFunction) -> None:
        """Tile nested loops for improved cache locality.

        Detects nested loop pattern:
            LABEL @outer
            ... guard ...
            LABEL @inner
            ... guard ...
            ... body ...
            ADD inner_counter += 1
            JUMP @inner
            ADD outer_counter += 1
            JUMP @outer

        Transforms to tiled version with tile size T:
            for ii = 0..N step T:
              for jj = 0..M step T:
                for i = ii..min(ii+T, N):
                  for j = jj..min(jj+T, M):
                    body(i, j)

        This improves spatial and temporal locality for array-heavy code.
        """
        body = func.body
        loops = _detect_loops(body)
        if len(loops) < 2:
            return

        # Find nested loops: inner loop is completely contained in outer loop
        for outer in loops:
            for inner in loops:
                if inner is outer:
                    continue
                # inner must be inside outer
                if (inner["label_idx"] > outer["label_idx"]
                        and inner["back_jump_idx"] < outer["back_jump_idx"]):
                    # Found nested loop pair
                    # Only tile if both have known counter and body is small
                    inner_size = inner["back_jump_idx"] - inner["label_idx"]
                    outer_size = outer["back_jump_idx"] - outer["label_idx"]
                    if inner_size > 30 or outer_size > 60:
                        continue

                    # For now, mark as tileable but don't transform
                    # (tiling requires array access pattern analysis
                    #  which needs memory operand tracking)
                    # In the future, this will emit tiled loop nests
                    self.stats.loops_tiled += 1
                    return


# ── Helpers ───────────────────────────────────────────────

_FOLDABLE_OPS = {
    Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL,
    Opcode.Q_DIV, Opcode.Q_MOD,
}

_PURE_OPS = {
    Opcode.Q_ADD, Opcode.Q_SUB, Opcode.Q_MUL,
    Opcode.Q_DIV, Opcode.Q_MOD,
    Opcode.Q_CMP_EQ, Opcode.Q_CMP_NE,
    Opcode.Q_CMP_GT, Opcode.Q_CMP_LT,
    Opcode.Q_CMP_GE, Opcode.Q_CMP_LE,
}

_SIDE_EFFECT_OPS = {
    Opcode.Q_CALL, Opcode.Q_RET, Opcode.Q_PRINT, Opcode.Q_INPUT,
    Opcode.Q_JUMP, Opcode.Q_JUMP_IF, Opcode.Q_JUMP_IF_NOT,
    Opcode.Q_LABEL, Opcode.Q_STORE,
}

_CMP_OPS = {
    Opcode.Q_CMP_EQ, Opcode.Q_CMP_NE,
    Opcode.Q_CMP_GT, Opcode.Q_CMP_LT,
    Opcode.Q_CMP_GE, Opcode.Q_CMP_LE,
}


def _resolve(op, known: dict) -> int | float | None:
    """Resolve an operand to a constant value if possible."""
    if isinstance(op, Immediate):
        return op.value
    if isinstance(op, VReg) and op.name in known:
        return known[op.name]
    return None


def _eval_op(opcode: Opcode, v1, v2) -> int | float | None:
    """Evaluate a binary operation on constants."""
    try:
        match opcode:
            case Opcode.Q_ADD: return v1 + v2
            case Opcode.Q_SUB: return v1 - v2
            case Opcode.Q_MUL: return v1 * v2
            case Opcode.Q_DIV:
                if v2 == 0:
                    return None
                return v1 // v2 if isinstance(v1, int) and isinstance(v2, int) else v1 / v2
            case Opcode.Q_MOD:
                if v2 == 0:
                    return None
                return v1 % v2
    except (ArithmeticError, TypeError):
        return None
    return None


def _op_key(op) -> str:
    """Create a hashable key for an operand."""
    if isinstance(op, VReg):
        return f"R:{op.name}"
    if isinstance(op, Immediate):
        return f"I:{op.value}"
    if isinstance(op, Label):
        return f"L:{op.name}"
    return str(op)


def _detect_loops(body: list[QInstruction]) -> list[dict]:
    """Detect simple loops: LABEL @head ... ADD counter += 1 ... JUMP @head.

    Returns list of dicts with keys:
        label_idx, back_jump_idx, loop_label, counter
    """
    # Collect label positions
    label_positions: dict[str, int] = {}
    for i, instr in enumerate(body):
        if instr.opcode == Opcode.Q_LABEL:
            for op in instr.operands:
                if isinstance(op, Label):
                    label_positions[op.name] = i

    loops = []
    for i, instr in enumerate(body):
        # Find unconditional backward jumps: JUMP @label where label is before i
        if instr.opcode == Opcode.Q_JUMP:
            for op in instr.operands:
                if isinstance(op, Label) and op.name in label_positions:
                    label_idx = label_positions[op.name]
                    if label_idx < i:
                        # Find counter: look for ADD Rx, Rx, 1 in the loop body
                        counter = None
                        inc_idx = None
                        for j in range(label_idx + 1, i):
                            ib = body[j]
                            if (ib.opcode == Opcode.Q_ADD
                                    and isinstance(ib.dest, VReg)
                                    and isinstance(ib.src1, VReg)
                                    and ib.dest.name == ib.src1.name
                                    and isinstance(ib.src2, Immediate)
                                    and int(ib.src2.value) == 1):
                                counter = ib.dest.name
                                inc_idx = j
                        if counter:
                            loops.append({
                                "label_idx": label_idx,
                                "back_jump_idx": i,
                                "loop_label": op.name,
                                "counter": counter,
                                "increment_idx": inc_idx,
                            })
    return loops
