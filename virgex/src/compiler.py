"""VPS Compiler — translates a VPS AST into a Python-compatible regex string."""

from __future__ import annotations

import re

from .ast_nodes import (
    AtomNode,
    EscapedBlockNode,
    EscapedCharNode,
    GroupNode,
    LiteralNode,
    Node,
    OptionalNode,
    PatternNode,
    QuantifiedNode,
    SequenceNode,
    SpaceTokenNode,
)
from .errors import VPSCompileError

# ── Atom → regex class mapping ────────────────────────

_ATOM_MAP: dict[str, str] = {
    "Az":  "[A-Za-z]",
    "AZ":  "[A-Z]",
    "az":  "[a-z]",
    "0":   "[0-9]",
    "Az0": "[A-Za-z0-9]",
}


def _atom_to_regex(name: str) -> str:
    """Convert an atom name to its regex character class."""
    if name in _ATOM_MAP:
        return _ATOM_MAP[name]

    # Numeric range: e.g. "06" → [0-6], "19" → [1-9]
    if len(name) == 2 and name[0].isdigit() and name[1].isdigit():
        lo, hi = name[0], name[1]
        if lo > hi:
            raise VPSCompileError(f"Invalid numeric atom range @{name}")
        if lo == "0" and hi == "9":
            return "[0-9]"
        return f"[{lo}-{hi}]"

    raise VPSCompileError(f"Unknown atom: @{name}")


# ── Quantifier → regex suffix ─────────────────────────

def _quantifier_suffix(qmin: int, qmax: int | None) -> str:
    if qmax is None:
        if qmin == 0:
            return "*"
        if qmin == 1:
            return "+"
        return f"{{{qmin},}}"
    if qmin == qmax:
        if qmin == 1:
            return ""
        return f"{{{qmin}}}"
    return f"{{{qmin},{qmax}}}"


# ── Compiler ──────────────────────────────────────────

class Compiler:
    """Compile a VPS AST into a regex pattern string."""

    def compile(self, tree: PatternNode) -> str:
        parts: list[str] = []
        if tree.anchor_start:
            parts.append("^")
        parts.append(self._emit_sequence(tree.body))
        if tree.anchor_end:
            parts.append("$")
        return "".join(parts)

    # ── dispatch ──────────────────────────────────────

    def _emit(self, node: Node) -> str:
        if isinstance(node, SequenceNode):
            return self._emit_sequence(node)
        if isinstance(node, AtomNode):
            return _atom_to_regex(node.name)
        if isinstance(node, LiteralNode):
            return re.escape(node.value)
        if isinstance(node, EscapedCharNode):
            return re.escape(node.char)
        if isinstance(node, EscapedBlockNode):
            return re.escape(node.content)
        if isinstance(node, SpaceTokenNode):
            return " "
        if isinstance(node, QuantifiedNode):
            return self._emit_quantified(node)
        if isinstance(node, OptionalNode):
            return self._emit_optional(node)
        if isinstance(node, GroupNode):
            return self._emit_group(node)
        raise VPSCompileError(f"Unknown AST node: {type(node).__name__}")

    # ── node emitters ─────────────────────────────────

    def _emit_sequence(self, node: SequenceNode) -> str:
        return "".join(self._emit(item) for item in node.items)

    def _emit_quantified(self, node: QuantifiedNode) -> str:
        inner = self._emit(node.expression)
        suffix = _quantifier_suffix(node.min, node.max)
        # Wrap multi-char inner in non-capturing group
        if len(inner) > 1 and not (inner.startswith("(?:") or inner.startswith("[")):
            inner = f"(?:{inner})"
        return f"{inner}{suffix}"

    def _emit_optional(self, node: OptionalNode) -> str:
        inner = self._emit(node.expression)
        # Safe to append ? directly: single char, char class [..], or already-wrapped (?:..)
        if (
            len(inner) == 1
            or (inner.startswith("["  ) and inner.endswith("]"))
            or (inner.startswith("(?:") and inner.endswith(")"))
        ):
            return f"{inner}?"
        return f"(?:{inner})?"

    def _emit_group(self, node: GroupNode) -> str:
        if len(node.alternatives) == 1:
            inner = self._emit_sequence(node.alternatives[0])
            return f"(?:{inner})"
        alts = "|".join(
            self._emit_sequence(alt) for alt in node.alternatives
        )
        return f"(?:{alts})"
