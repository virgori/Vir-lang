"""
monomorph.py – Monomorphization Pass for Vir Generics
======================================================
Phase 3 Task E1: Instantiate generic functions and types
with concrete type arguments.

Strategy: Walk the call graph. For each call to a generic function
with concrete type args, generate a specialized copy with mangled name.

    vec_push<i64>(xs, 42)  →  call @vec_push__i64
    vec_push<f32>(ys, 3.14)  →  call @vec_push__f32

This avoids runtime overhead (no type erasure, no vtables for generics).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from src.ir.instructions.q_ir import (
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
    Immediate,
    Label,
)


@dataclass
class MonomorphKey:
    """Unique key for a monomorphized function instance."""
    base_name: str
    type_args: tuple[str, ...]

    @property
    def mangled_name(self) -> str:
        return f"{self.base_name}__{'_'.join(self.type_args)}"


@dataclass
class MonomorphStats:
    """Statistics from a monomorphization run."""
    generic_funcs: int = 0
    instantiations: int = 0
    call_sites_rewritten: int = 0


class MonomorphPass:
    """
    Monomorphization pass — converts generic functions into
    concrete specialized copies.

    Usage:
        mp = MonomorphPass()
        stats = mp.run(module)
    """

    def __init__(self) -> None:
        self._generic_funcs: dict[str, QFunction] = {}
        self._instantiated: dict[str, QFunction] = {}
        self._stats = MonomorphStats()

    def run(self, module: QModule) -> MonomorphStats:
        """Run monomorphization on a QModule."""
        self._stats = MonomorphStats()
        self._generic_funcs.clear()
        self._instantiated.clear()

        # Phase 1: Identify generic functions
        for func in module.functions:
            if func.generic_params:
                self._generic_funcs[func.name] = func
                self._stats.generic_funcs += 1

        # Phase 2: Scan call sites, collect instantiations needed
        needed: list[MonomorphKey] = []
        for func in module.functions:
            for instr in func.body:
                if instr.opcode == Opcode.Q_MONOMORPH:
                    # Q_MONOMORPH carries base func name + type args
                    base = instr.comment  # base function name
                    types = instr.string_value.split(",")  # type args
                    key = MonomorphKey(base, tuple(types))
                    if key.mangled_name not in self._instantiated:
                        needed.append(key)

        # Phase 3: Generate specialized copies
        for key in needed:
            if key.base_name in self._generic_funcs:
                specialized = self._instantiate(
                    self._generic_funcs[key.base_name], key
                )
                self._instantiated[key.mangled_name] = specialized
                module.add_function(specialized)
                self._stats.instantiations += 1

        # Phase 4: Rewrite call sites to use mangled names
        for func in module.functions:
            new_body: list[QInstruction] = []
            for instr in func.body:
                if instr.opcode == Opcode.Q_MONOMORPH:
                    base = instr.comment
                    types = instr.string_value.split(",")
                    mangled = MonomorphKey(base, tuple(types)).mangled_name
                    # Replace with Q_CALL to mangled name
                    new_body.append(QInstruction(
                        opcode=Opcode.Q_CALL,
                        dest=instr.dest,
                        src1=Label(mangled),
                        src2=instr.src2,
                        comment=f"monomorphized from {base}<{','.join(types)}>",
                    ))
                    self._stats.call_sites_rewritten += 1
                else:
                    new_body.append(instr)
            func.body = new_body

        return self._stats

    def _instantiate(self, generic: QFunction, key: MonomorphKey) -> QFunction:
        """Create a specialized copy of a generic function."""
        specialized = QFunction(
            name=key.mangled_name,
            params=list(generic.params),
            body=[],
        )

        # Build type substitution map: T → i64, U → str, etc.
        type_map = {}
        for i, param in enumerate(generic.generic_params):
            if i < len(key.type_args):
                type_map[param] = key.type_args[i]

        # Copy body, substituting type references
        for instr in generic.body:
            new_instr = QInstruction(
                opcode=instr.opcode,
                dest=instr.dest,
                src1=instr.src1,
                src2=instr.src2,
                comment=self._substitute_types(instr.comment, type_map),
                patch_id=instr.patch_id,
                string_value=self._substitute_types(instr.string_value, type_map),
            )
            specialized.body.append(new_instr)

        return specialized

    @staticmethod
    def _substitute_types(text: str, type_map: dict[str, str]) -> str:
        """Replace type parameters in a string."""
        result = text
        for param, concrete in type_map.items():
            result = result.replace(param, concrete)
        return result
