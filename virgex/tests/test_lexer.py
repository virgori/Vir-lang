"""Tests for VPS Lexer."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.lexer import Lexer
from src.tokens import TokenType, Quantifier
from src.errors import VPSLexError


def _types(source: str) -> list[TokenType]:
    return [t.type for t in Lexer(source).tokenize()]


def _values(source: str) -> list[str]:
    return [t.value for t in Lexer(source).tokenize()]


# ── Basic tokens ──────────────────────────────────────

class TestAtoms:
    def test_atom_az(self):
        toks = Lexer("@Az").tokenize()
        assert toks[0].type is TokenType.ATOM
        assert toks[0].atom_name == "Az"

    def test_atom_upper(self):
        toks = Lexer("@AZ").tokenize()
        assert toks[0].atom_name == "AZ"

    def test_atom_lower(self):
        toks = Lexer("@az").tokenize()
        assert toks[0].atom_name == "az"

    def test_atom_digit(self):
        toks = Lexer("@0").tokenize()
        assert toks[0].atom_name == "0"

    def test_atom_digit_range(self):
        toks = Lexer("@06").tokenize()
        assert toks[0].atom_name == "06"

    def test_atom_alnum(self):
        toks = Lexer("@Az0").tokenize()
        assert toks[0].atom_name == "Az0"

    def test_atom_invalid_range(self):
        with pytest.raises(VPSLexError):
            Lexer("@96").tokenize()

    def test_atom_no_name(self):
        with pytest.raises(VPSLexError):
            Lexer("@ ").tokenize()


# ── Quantifiers ───────────────────────────────────────

class TestQuantifiers:
    def test_exact(self):
        toks = Lexer("@0!3").tokenize()
        q = toks[1].quantifier
        assert q == Quantifier(3, 3)

    def test_range(self):
        toks = Lexer("@Az!1~5").tokenize()
        q = toks[1].quantifier
        assert q == Quantifier(1, 5)

    def test_at_least(self):
        toks = Lexer("@0!2~").tokenize()
        q = toks[1].quantifier
        assert q == Quantifier(2, None)

    def test_zero_or_more(self):
        toks = Lexer("-!~").tokenize()
        q = toks[1].quantifier
        assert q == Quantifier(0, None)

    def test_whitespace_in_quantifier(self):
        toks = Lexer("@0 !3").tokenize()
        assert toks[1].type is TokenType.QUANTIFIER
        assert toks[1].quantifier == Quantifier(3, 3)

    def test_invalid_range(self):
        with pytest.raises(VPSLexError):
            Lexer("@0!5~2").tokenize()


# ── Groups and pipes ──────────────────────────────────

class TestGroupsAndPipes:
    def test_group_open_close(self):
        types = _types(":( A :)")
        assert types == [
            TokenType.GROUP_OPEN,
            TokenType.LITERAL,
            TokenType.GROUP_CLOSE,
            TokenType.EOF,
        ]

    def test_pipe(self):
        types = _types(":( A | B :)")
        assert TokenType.PIPE in types

    def test_anchor_pipes(self):
        types = _types("| @0!3 |")
        assert types[0] is TokenType.PIPE
        assert types[-2] is TokenType.PIPE


# ── Escape ────────────────────────────────────────────

class TestEscape:
    def test_single_escape(self):
        toks = Lexer("$-").tokenize()
        assert toks[0].type is TokenType.ESCAPE_CHAR
        assert toks[0].value == "$-"

    def test_escape_pipe(self):
        toks = Lexer("$|").tokenize()
        assert toks[0].type is TokenType.ESCAPE_CHAR

    def test_escape_block(self):
        toks = Lexer("$. |@!~ .$").tokenize()
        assert toks[0].type is TokenType.ESCAPE_BLOCK
        assert " |@!~ " in toks[0].value

    def test_unterminated_block(self):
        with pytest.raises(VPSLexError):
            Lexer("$. hello").tokenize()


# ── Space token and literals ──────────────────────────

class TestSpaceAndLiterals:
    def test_space_token(self):
        toks = Lexer("-").tokenize()
        assert toks[0].type is TokenType.SPACE_TOKEN

    def test_literal_chars(self):
        toks = Lexer("ABC").tokenize()
        assert toks[0].type is TokenType.LITERAL
        assert toks[0].value == "A"
        assert toks[1].value == "B"
        assert toks[2].value == "C"

    def test_optional(self):
        toks = Lexer("?@0").tokenize()
        assert toks[0].type is TokenType.QUESTION

    def test_whitespace_ignored(self):
        t1 = _types("@0!3")
        t2 = _types("@0 !3")
        assert t1 == t2


# ── Full patterns ─────────────────────────────────────

class TestFullPatterns:
    def test_id_pattern(self):
        types = _types("| @AZ!2 $- @0!5 $? |")
        assert types[0] is TokenType.PIPE    # anchor start
        assert types[-2] is TokenType.PIPE   # anchor end
        assert TokenType.ATOM in types
        assert TokenType.QUANTIFIER in types
        assert TokenType.ESCAPE_CHAR in types
