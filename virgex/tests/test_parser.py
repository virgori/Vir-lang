"""Tests for VPS Parser."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.lexer import Lexer
from src.parser import Parser
from src.ast_nodes import (
    AtomNode,
    EscapedCharNode,
    GroupNode,
    LiteralNode,
    OptionalNode,
    PatternNode,
    QuantifiedNode,
    SequenceNode,
    SpaceTokenNode,
)
from src.errors import VPSParseError


def _parse(source: str) -> PatternNode:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


# ── Anchors ───────────────────────────────────────────

class TestAnchors:
    def test_both_anchors(self):
        tree = _parse("| @0!3 |")
        assert tree.anchor_start is True
        assert tree.anchor_end is True

    def test_start_anchor_only(self):
        tree = _parse("| @0!3")
        assert tree.anchor_start is True
        assert tree.anchor_end is False

    def test_end_anchor_only(self):
        tree = _parse("@0!3 |")
        assert tree.anchor_start is False
        assert tree.anchor_end is True

    def test_no_anchors(self):
        tree = _parse("@0!3")
        assert tree.anchor_start is False
        assert tree.anchor_end is False


# ── Atoms ─────────────────────────────────────────────

class TestAtoms:
    def test_single_atom(self):
        tree = _parse("@AZ")
        items = tree.body.items
        assert len(items) == 1
        assert isinstance(items[0], AtomNode)
        assert items[0].name == "AZ"


# ── Quantified ────────────────────────────────────────

class TestQuantified:
    def test_atom_quantified(self):
        tree = _parse("@0!3")
        items = tree.body.items
        assert len(items) == 1
        node = items[0]
        assert isinstance(node, QuantifiedNode)
        assert isinstance(node.expression, AtomNode)
        assert node.min == 3
        assert node.max == 3

    def test_range_quantifier(self):
        tree = _parse("@Az!1~5")
        node = tree.body.items[0]
        assert isinstance(node, QuantifiedNode)
        assert node.min == 1
        assert node.max == 5

    def test_unbounded_quantifier(self):
        tree = _parse("@0!2~")
        node = tree.body.items[0]
        assert isinstance(node, QuantifiedNode)
        assert node.min == 2
        assert node.max is None


# ── Optional ──────────────────────────────────────────

class TestOptional:
    def test_optional_atom(self):
        tree = _parse("?@0")
        node = tree.body.items[0]
        assert isinstance(node, OptionalNode)
        assert isinstance(node.expression, AtomNode)

    def test_optional_quantified(self):
        tree = _parse("?@AZ!2")
        node = tree.body.items[0]
        assert isinstance(node, OptionalNode)
        inner = node.expression
        assert isinstance(inner, QuantifiedNode)
        assert inner.min == 2
        assert inner.max == 2

    def test_optional_group(self):
        tree = _parse("?:( $- @0!5 :)")
        node = tree.body.items[0]
        assert isinstance(node, OptionalNode)
        assert isinstance(node.expression, GroupNode)


# ── Group / Alternation ──────────────────────────────

class TestGroups:
    def test_simple_group(self):
        tree = _parse(":( - @0 :)")
        node = tree.body.items[0]
        assert isinstance(node, GroupNode)
        assert len(node.alternatives) == 1

    def test_alternation(self):
        tree = _parse(":( A | B :)")
        node = tree.body.items[0]
        assert isinstance(node, GroupNode)
        assert len(node.alternatives) == 2

    def test_multi_alternation(self):
        tree = _parse(":( A | B | C :)")
        node = tree.body.items[0]
        assert isinstance(node, GroupNode)
        assert len(node.alternatives) == 3

    def test_group_quantified(self):
        tree = _parse(":( - @0 :)!3")
        node = tree.body.items[0]
        assert isinstance(node, QuantifiedNode)
        assert isinstance(node.expression, GroupNode)
        assert node.min == 3

    def test_nested_group(self):
        tree = _parse(":( A | :( B | C :) :)")
        node = tree.body.items[0]
        assert isinstance(node, GroupNode)
        assert len(node.alternatives) == 2
        # Second alternative contains a nested group
        inner_seq = node.alternatives[1]
        assert isinstance(inner_seq.items[0], GroupNode)


# ── Literals ──────────────────────────────────────────

class TestLiterals:
    def test_literal_string(self):
        tree = _parse("ABC")
        node = tree.body.items[0]
        assert isinstance(node, LiteralNode)
        assert node.value == "ABC"

    def test_escaped_char(self):
        tree = _parse("$-")
        node = tree.body.items[0]
        assert isinstance(node, EscapedCharNode)
        assert node.char == "-"

    def test_space_token(self):
        tree = _parse("-")
        node = tree.body.items[0]
        assert isinstance(node, SpaceTokenNode)


# ── Complex patterns ─────────────────────────────────

class TestComplex:
    def test_id_pattern(self):
        tree = _parse("| @AZ!2 $- @0!5 $? |")
        assert tree.anchor_start
        assert tree.anchor_end
        items = tree.body.items
        assert len(items) == 4  # QAtom, EscChar, QAtom, EscChar

    def test_optional_suffix(self):
        tree = _parse("| @AZ!2 ?:( $- @0!5 :) |")
        items = tree.body.items
        assert isinstance(items[0], QuantifiedNode)  # @AZ!2
        assert isinstance(items[1], OptionalNode)     # ?:(...)
