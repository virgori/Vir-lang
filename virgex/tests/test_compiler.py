"""Tests for VPS Compiler (VPS → regex translation)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.matcher import to_regex


# ── Atoms ─────────────────────────────────────────────

class TestAtomCompilation:
    def test_az(self):
        assert to_regex("@Az") == "[A-Za-z]"

    def test_upper(self):
        assert to_regex("@AZ") == "[A-Z]"

    def test_lower(self):
        assert to_regex("@az") == "[a-z]"

    def test_digit(self):
        assert to_regex("@0") == "[0-9]"

    def test_digit_range(self):
        assert to_regex("@06") == "[0-6]"

    def test_alnum(self):
        assert to_regex("@Az0") == "[A-Za-z0-9]"


# ── Quantifiers ───────────────────────────────────────

class TestQuantifiers:
    def test_exact(self):
        assert to_regex("@0!3") == "[0-9]{3}"

    def test_range(self):
        assert to_regex("@Az!1~5") == "[A-Za-z]{1,5}"

    def test_at_least(self):
        assert to_regex("@0!2~") == "[0-9]{2,}"

    def test_zero_or_more(self):
        assert to_regex("@0!~") == "[0-9]*"

    def test_exact_one(self):
        # !1 should produce no quantifier suffix (already one)
        assert to_regex("@0!1") == "[0-9]"


# ── Anchors ───────────────────────────────────────────

class TestAnchors:
    def test_both(self):
        assert to_regex("| @0!3 |") == "^[0-9]{3}$"

    def test_start_only(self):
        assert to_regex("| @0!3") == "^[0-9]{3}"

    def test_end_only(self):
        assert to_regex("@0!3 |") == "[0-9]{3}$"


# ── Optional ──────────────────────────────────────────

class TestOptional:
    def test_optional_atom(self):
        assert to_regex("?@0") == "[0-9]?"

    def test_optional_quantified(self):
        assert to_regex("?@AZ!2") == "(?:[A-Z]{2})?"

    def test_optional_group(self):
        regex = to_regex("?:( $- @0!5 :)")
        assert regex == "(?:\\-[0-9]{5})?"


# ── Groups and OR ─────────────────────────────────────

class TestGroups:
    def test_simple_group(self):
        assert to_regex(":( - @0 :)") == "(?: [0-9])"

    def test_or(self):
        assert to_regex(":( A | B :)") == "(?:A|B)"

    def test_complex_or(self):
        assert to_regex(":( @AZ!2 | @0!3 :)") == "(?:[A-Z]{2}|[0-9]{3})"

    def test_group_quantified(self):
        assert to_regex(":( - @0 :)!3") == "(?: [0-9]){3}"


# ── Escape ────────────────────────────────────────────

class TestEscape:
    def test_escape_dash(self):
        assert to_regex("$-") == "\\-"

    def test_escape_pipe(self):
        assert to_regex("$|") == "\\|"

    def test_escape_question(self):
        assert to_regex("$?") == "\\?"

    def test_escape_block(self):
        regex = to_regex("$. |@!~ .$")
        # Should escape all special regex chars in the block
        assert "|" not in regex or "\\|" in regex


# ── Literals ──────────────────────────────────────────

class TestLiterals:
    def test_plain_literal(self):
        assert to_regex("ABC") == "ABC"

    def test_literal_hn(self):
        assert to_regex("HN") == "HN"


# ── Space token ───────────────────────────────────────

class TestSpace:
    def test_space_token(self):
        assert to_regex("@AZ!2 - @0!5") == "[A-Z]{2} [0-9]{5}"


# ── Full spec examples ────────────────────────────────

class TestSpecExamples:
    def test_exactly_3_digits(self):
        assert to_regex("| @0!3 |") == "^[0-9]{3}$"

    def test_id_code(self):
        regex = to_regex("| @AZ!2 $- @0!5 $? |")
        assert regex == "^[A-Z]{2}\\-[0-9]{5}\\?$"

    def test_optional_suffix(self):
        regex = to_regex("| @AZ!2 ?:( $- @0!5 :) |")
        assert regex == "^[A-Z]{2}(?:\\-[0-9]{5})?$"

    def test_a_or_b(self):
        assert to_regex("| :( A | B :) |") == "^(?:A|B)$"

    def test_username(self):
        assert to_regex("| @Az0!3~12 |") == "^[A-Za-z0-9]{3,12}$"
