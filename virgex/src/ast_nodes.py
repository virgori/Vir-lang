"""VPS Abstract Syntax Tree node definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Base ──────────────────────────────────────────────

@dataclass
class Node:
    """Base AST node."""


# ── Top-level ─────────────────────────────────────────

@dataclass
class PatternNode(Node):
    """Root of a VPS pattern."""
    anchor_start: bool
    anchor_end: bool
    body: SequenceNode


# ── Sequence ──────────────────────────────────────────

@dataclass
class SequenceNode(Node):
    """Ordered sequence of expressions."""
    items: list[Node] = field(default_factory=list)


# ── Atoms ─────────────────────────────────────────────

@dataclass
class AtomNode(Node):
    """Character-class atom, e.g. @Az, @0, @06."""
    name: str  # "Az", "AZ", "az", "0", "06", "Az0", etc.


# ── Literals ──────────────────────────────────────────

@dataclass
class LiteralNode(Node):
    """One or more literal characters."""
    value: str


@dataclass
class EscapedCharNode(Node):
    """Single escaped character ($x)."""
    char: str


@dataclass
class EscapedBlockNode(Node):
    """Escaped block ($. ... .$)."""
    content: str


@dataclass
class SpaceTokenNode(Node):
    """Literal space token (-)."""


# ── Quantifier ────────────────────────────────────────

@dataclass
class QuantifiedNode(Node):
    """Expression with repetition."""
    expression: Node
    min: int
    max: int | None  # None = unbounded


# ── Optional ──────────────────────────────────────────

@dataclass
class OptionalNode(Node):
    """Optional expression (?expr)."""
    expression: Node


# ── Group / Alternation ──────────────────────────────

@dataclass
class GroupNode(Node):
    """Group with possible alternation: :( ... | ... :)"""
    alternatives: list[SequenceNode] = field(default_factory=list)
