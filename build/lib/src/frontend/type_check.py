"""
type_check.py – Optional Static Type Checker
=============================================
Walks the AST and verifies type consistency when annotations are
present.  All annotations are *optional* — un-annotated variables
and functions are silently accepted (gradual typing).

Supported base types: "int", "float", "str", "bool"
Promotion rule: int → float (implicit)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.frontend.parser.parser import (
    ASTNode,
    AssignNode,
    BinOpNode,
    CallNode,
    CompareNode,
    ForNode,
    FuncDefNode,
    IdentifierRef,
    IfNode,
    LoopNode,
    NumberLiteral,
    PrintNode,
    ProgramNode,
    ReturnNode,
    StringLiteral,
    VarDeclNode,
    WhileNode,
)

# ═══════════════════════════════════════════════════════════
# Type errors
# ═══════════════════════════════════════════════════════════

@dataclass
class TypeError:
    message: str
    node: Optional[ASTNode] = None

    def __repr__(self) -> str:
        return f"TypeError: {self.message}"


# ═══════════════════════════════════════════════════════════
# Type environment
# ═══════════════════════════════════════════════════════════

_VALID_TYPES = frozenset({"int", "float", "str", "bool"})

# Which type pairs allow implicit promotion
_PROMOTABLE = {("int", "float"): "float", ("float", "int"): "float"}


def _unify(t1: str | None, t2: str | None) -> str | None:
    """Return unified type, or None if unknown/compatible."""
    if t1 is None or t2 is None:
        return t1 or t2
    if t1 == t2:
        return t1
    return _PROMOTABLE.get((t1, t2))


# ═══════════════════════════════════════════════════════════
# Checker
# ═══════════════════════════════════════════════════════════

class TypeChecker:
    """Single-pass type checker over the AST.

    Usage::

        checker = TypeChecker()
        errors = checker.check(program_ast)
        # errors: list[TypeError]  — empty means OK
    """

    def __init__(self) -> None:
        self.errors: list[TypeError] = []
        # var_name → declared type (None = untyped)
        self._env: dict[str, str | None] = {}
        # func_name → (param_types, return_type)
        self._funcs: dict[str, tuple[list[str | None], str | None]] = {}

    def check(self, program: ProgramNode) -> list[TypeError]:
        """Type-check a full program, return any errors found."""
        self.errors.clear()
        self._env.clear()
        self._funcs.clear()
        for stmt in program.statements:
            self._check_stmt(stmt)
        return list(self.errors)

    # ── Statement visitors ─────────────────────────────────

    def _check_stmt(self, node: ASTNode) -> None:
        if isinstance(node, FuncDefNode):
            self._check_func_def(node)
        elif isinstance(node, VarDeclNode):
            self._check_var_decl(node)
        elif isinstance(node, AssignNode):
            self._check_assign(node)
        elif isinstance(node, IfNode):
            self._check_if(node)
        elif isinstance(node, (LoopNode, WhileNode)):
            self._check_loop(node)
        elif isinstance(node, ForNode):
            self._check_for(node)
        elif isinstance(node, ReturnNode):
            self._check_return(node)
        elif isinstance(node, PrintNode):
            if node.expr:
                self._infer(node.expr)

    def _check_func_def(self, node: FuncDefNode) -> None:
        ptypes = list(node.param_types) if node.param_types else [None] * len(node.params)
        # Pad ptypes if fewer than params
        while len(ptypes) < len(node.params):
            ptypes.append(None)
        self._funcs[node.name] = (ptypes, node.return_type)

        # Push params into env
        saved = dict(self._env)
        for pname, ptype in zip(node.params, ptypes):
            if ptype and ptype not in _VALID_TYPES:
                self.errors.append(TypeError(
                    f"Unknown type '{ptype}' for param '{pname}'", node,
                ))
            self._env[pname] = ptype

        for stmt in node.body:
            self._check_stmt(stmt)

        self._env = saved

    def _check_var_decl(self, node: VarDeclNode) -> None:
        ann = node.type_ann
        if ann and ann not in _VALID_TYPES:
            self.errors.append(TypeError(
                f"Unknown type annotation '{ann}' for '{node.name}'", node,
            ))
            ann = None

        inferred = self._infer(node.value) if node.value else None

        if ann and inferred and _unify(ann, inferred) is None:
            self.errors.append(TypeError(
                f"Type mismatch for '{node.name}': declared {ann}, got {inferred}",
                node,
            ))
        self._env[node.name] = ann or inferred

    def _check_assign(self, node: AssignNode) -> None:
        rhs = self._infer(node.value) if node.value else None
        declared = self._env.get(node.name)
        if declared and rhs and _unify(declared, rhs) is None:
            self.errors.append(TypeError(
                f"Cannot assign {rhs} to '{node.name}' (declared {declared})",
                node,
            ))
        if node.name not in self._env:
            self._env[node.name] = rhs

    def _check_if(self, node: IfNode) -> None:
        if node.condition:
            self._infer(node.condition)
        for s in node.then_body:
            self._check_stmt(s)
        for s in node.else_body:
            self._check_stmt(s)

    def _check_loop(self, node) -> None:
        if hasattr(node, "condition") and node.condition:
            self._infer(node.condition)
        if hasattr(node, "count") and node.count:
            self._infer(node.count)
        for s in node.body:
            self._check_stmt(s)

    def _check_for(self, node: ForNode) -> None:
        self._env[node.var_name] = "int"
        if node.start:
            self._infer(node.start)
        if node.end:
            self._infer(node.end)
        for s in node.body:
            self._check_stmt(s)

    def _check_return(self, node: ReturnNode) -> None:
        if node.expr:
            self._infer(node.expr)

    # ── Expression type inference ──────────────────────────

    def _infer(self, node: ASTNode | None) -> str | None:
        """Return the inferred type of an expression, or None."""
        if node is None:
            return None
        if isinstance(node, NumberLiteral):
            v = node.value
            if isinstance(v, float) and v != int(v):
                return "float"
            return "int"
        if isinstance(node, StringLiteral):
            return "str"
        if isinstance(node, IdentifierRef):
            return self._env.get(node.name)
        if isinstance(node, BinOpNode):
            lt = self._infer(node.left)
            rt = self._infer(node.right)
            if lt == "str" or rt == "str":
                if node.op == "ADD":
                    return "str"  # string concat
                self.errors.append(TypeError(
                    f"Cannot apply {node.op} to str operands", node,
                ))
                return None
            return _unify(lt, rt)
        if isinstance(node, CompareNode):
            self._infer(node.left)
            self._infer(node.right)
            return "bool"
        if isinstance(node, CallNode):
            info = self._funcs.get(node.name)
            if info:
                ptypes, rtype = info
                for i, arg in enumerate(node.args):
                    at = self._infer(arg)
                    if i < len(ptypes) and ptypes[i] and at:
                        if _unify(ptypes[i], at) is None:
                            self.errors.append(TypeError(
                                f"Arg {i} of '{node.name}': expected {ptypes[i]}, got {at}",
                                node,
                            ))
                return rtype
            return None
        return None
