"""End-to-end tests — VPS pattern → match against real strings."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.matcher import Virgex, fullmatch, search, findall


# ── Exactly 3 digits: | @0!3 | ───────────────────────

class TestExact3Digits:
    PAT = "| @0!3 |"

    def test_match(self):
        assert fullmatch(self.PAT, "123") is not None

    def test_reject_short(self):
        assert fullmatch(self.PAT, "12") is None

    def test_reject_long(self):
        assert fullmatch(self.PAT, "1234") is None

    def test_reject_alpha(self):
        assert fullmatch(self.PAT, "abc") is None


# ── ID code: | @AZ!2 $- @0!5 $? | ───────────────────

class TestIdCode:
    PAT = "| @AZ!2 $- @0!5 $? |"

    def test_match(self):
        assert fullmatch(self.PAT, "HN-12345?") is not None

    def test_reject_no_question(self):
        assert fullmatch(self.PAT, "HN-12345") is None

    def test_reject_lowercase(self):
        assert fullmatch(self.PAT, "hn-12345?") is None


# ── Optional suffix: | @AZ!2 ?:( $- @0!5 :) | ───────

class TestOptionalSuffix:
    PAT = "| @AZ!2 ?:( $- @0!5 :) |"

    def test_match_with_suffix(self):
        assert fullmatch(self.PAT, "HN-12345") is not None

    def test_match_without_suffix(self):
        assert fullmatch(self.PAT, "HN") is not None

    def test_reject_partial(self):
        assert fullmatch(self.PAT, "HN-123") is None


# ── A or B: | :( A | B :) | ──────────────────────────

class TestAorB:
    PAT = "| :( A | B :) |"

    def test_a(self):
        assert fullmatch(self.PAT, "A") is not None

    def test_b(self):
        assert fullmatch(self.PAT, "B") is not None

    def test_reject_c(self):
        assert fullmatch(self.PAT, "C") is None


# ── Username 3–12 alnum: | @Az0!3~12 | ──────────────

class TestUsername:
    PAT = "| @Az0!3~12 |"

    def test_min(self):
        assert fullmatch(self.PAT, "abc") is not None

    def test_max(self):
        assert fullmatch(self.PAT, "abcdefghijkl") is not None

    def test_reject_short(self):
        assert fullmatch(self.PAT, "ab") is None

    def test_reject_long(self):
        assert fullmatch(self.PAT, "abcdefghijklm") is None

    def test_reject_special(self):
        assert fullmatch(self.PAT, "abc@def") is None


# ── Space + quantifier: @AZ!2 - @0!5 ─────────────────

class TestSpacePattern:
    PAT = "| @AZ!2 - @0!5 |"

    def test_match(self):
        assert fullmatch(self.PAT, "HN 12345") is not None

    def test_reject_no_space(self):
        assert fullmatch(self.PAT, "HN12345") is None


# ── Repeated group: :( - @0 :)!3 ─────────────────────

class TestRepeatedGroup:
    PAT = "| :( - @0 :)!3 |"

    def test_match(self):
        assert fullmatch(self.PAT, " 1 2 3") is not None

    def test_reject(self):
        assert fullmatch(self.PAT, " 1 2") is None


# ── Search (no anchors) ──────────────────────────────

class TestSearch:
    def test_find_digits(self):
        m = search("@0!3", "abc123def")
        assert m is not None
        assert m.text == "123"

    def test_findall(self):
        results = findall("@0!3", "abc123def456ghi789")
        assert results == ["123", "456", "789"]


# ── Digit range atom ─────────────────────────────────

class TestDigitRange:
    def test_06_range(self):
        pat = "| @06 |"
        assert fullmatch(pat, "0") is not None
        assert fullmatch(pat, "6") is not None
        assert fullmatch(pat, "7") is None
        assert fullmatch(pat, "9") is None


# ── Escape block ─────────────────────────────────────

class TestEscapeBlock:
    def test_block(self):
        pat = "$.|@!~.$"
        m = search(pat, "hello |@!~ world")
        assert m is not None
        assert m.text == "|@!~"


# ── Nested groups ─────────────────────────────────────

class TestNestedGroups:
    def test_nested_or(self):
        pat = "| :( A | :( B | C :) :) |"
        assert fullmatch(pat, "A") is not None
        assert fullmatch(pat, "B") is not None
        assert fullmatch(pat, "C") is not None
        assert fullmatch(pat, "D") is None


# ── Virgex object ────────────────────────────────────

class TestVirgexObject:
    def test_regex_property(self):
        v = Virgex("| @0!3 |")
        assert v.regex == "^[0-9]{3}$"

    def test_repr(self):
        v = Virgex("| @0!3 |")
        assert "Virgex" in repr(v)

    def test_match_method(self):
        v = Virgex("@0!3")
        m = v.match("123abc")
        assert m is not None
        assert m.text == "123"


# ── Zero-or-more spaces ──────────────────────────────

class TestZeroOrMoreSpaces:
    PAT = "| @AZ!2 -!~ @0!3 |"

    def test_no_spaces(self):
        assert fullmatch(self.PAT, "HN123") is not None

    def test_one_space(self):
        assert fullmatch(self.PAT, "HN 123") is not None

    def test_many_spaces(self):
        assert fullmatch(self.PAT, "HN   123") is not None
