"""
tests/test_virgex_integration.py — VPS Pattern Integration Tests
================================================================
Kiểm tra tích hợp Virgex (VPS) vào stdlib:
  1. VPS compilation → regex correctness
  2. Extended atom types (Vn, Cj, Hi, Ka, Ko)
  3. Phonetic rule pattern matching cho 5 ngôn ngữ
  4. End-to-end: VPS pattern → NFA match trên text thật
"""

import sys
import os
import re
import pytest

# Đảm bảo import được virgex engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'virgex'))

from virgex.src.matcher import Virgex, compile as vps_compile
from virgex.src.compiler import Compiler
from virgex.src.lexer import Lexer
from virgex.src.parser import Parser


# ═══════════════════════════════════════════════════════
# 1. Core VPS → Regex Compilation
# ═══════════════════════════════════════════════════════

class TestVPSCoreCompilation:
    """Basic VPS patterns compile to correct regex."""

    def test_exact_digits(self):
        v = Virgex("| @0!3 |")
        assert v.fullmatch("123")
        assert not v.fullmatch("12")
        assert not v.fullmatch("1234")
        assert not v.fullmatch("abc")

    def test_uppercase_dash_digits(self):
        v = Virgex("| @AZ!2 $- @0!5 |")
        assert v.fullmatch("HN-12345")
        assert not v.fullmatch("hn-12345")
        assert not v.fullmatch("H-12345")

    def test_optional_group(self):
        v = Virgex("| @AZ!2 ?:( $- @0!5 :) |")
        assert v.fullmatch("HN")
        assert v.fullmatch("HN-12345")
        assert not v.fullmatch("HN-")

    def test_alternation(self):
        v = Virgex("| :( A | B | C :) |")
        assert v.fullmatch("A")
        assert v.fullmatch("B")
        assert v.fullmatch("C")
        assert not v.fullmatch("D")

    def test_alphanumeric_range(self):
        v = Virgex("| @Az0!3~12 |")
        assert v.fullmatch("abc")
        assert v.fullmatch("abc123def456")
        assert not v.fullmatch("ab")          # too short
        assert not v.fullmatch("a" * 13)      # too long

    def test_space_token(self):
        v = Virgex("| @AZ!2 - @0!5 |")
        assert v.fullmatch("HN 12345")
        assert not v.fullmatch("HN12345")

    def test_digit_range_atom(self):
        v = Virgex("| @06 |")
        for d in range(7):
            assert v.fullmatch(str(d)), f"Should match {d}"
        for d in range(7, 10):
            assert not v.fullmatch(str(d)), f"Should not match {d}"

    def test_search_no_anchor(self):
        v = Virgex("@0!3")
        result = v.search("abc123def")
        assert result is not None
        assert result.text == "123"

    def test_escape_block(self):
        v = Virgex("| $.hello world.$ |")
        assert v.fullmatch("hello world")
        assert not v.fullmatch("hello world!")

    def test_repeated_group(self):
        v = Virgex("| :( - @0 :)!3 |")
        assert v.fullmatch(" 1 2 3")
        assert not v.fullmatch(" 1 2")

    def test_zero_or_more(self):
        v = Virgex("| @Az!~ |")
        assert v.fullmatch("")
        assert v.fullmatch("abc")
        assert v.fullmatch("ABCDEFG")

    def test_one_or_more(self):
        v = Virgex("| @0!1~ |")
        assert not v.fullmatch("")
        assert v.fullmatch("1")
        assert v.fullmatch("12345")


# ═══════════════════════════════════════════════════════
# 2. Extended Atom Types (multilingual)
# ═══════════════════════════════════════════════════════

class TestExtendedAtoms:
    """Extended VPS atoms for multilingual phonetic processing."""

    def test_to_regex_basic_atoms(self):
        """Verify basic atom → regex translation."""
        cases = [
            ("@Az",  "[A-Za-z]"),
            ("@AZ",  "[A-Z]"),
            ("@az",  "[a-z]"),
            ("@0",   "[0-9]"),
            ("@Az0", "[A-Za-z0-9]"),
        ]
        for vps, expected_regex in cases:
            result = Virgex(f"| {vps} |").regex
            assert expected_regex in result, f"{vps} should contain {expected_regex}, got {result}"

    def test_findall(self):
        """VPS findall extracts all matches."""
        v = Virgex("@0!2~4")
        results = v.findall("abc12def3456ghi78")
        assert "12" in results
        assert "3456" in results
        assert "78" in results


# ═══════════════════════════════════════════════════════
# 3. Vietnamese Phonetic Patterns
# ═══════════════════════════════════════════════════════

class TestVietnamesePhonetics:
    """Vietnamese phonetic rules using VPS patterns."""

    def test_consonant_cluster_ng(self):
        """ng/ngh + vowel pattern."""
        # Simplified: match words starting with ng/ngh
        v = Virgex(":( ng | ngh :) @az!1~")
        assert v.search("nghe") is not None
        assert v.search("ngu") is not None
        assert v.search("nghĩ") is not None   # UTF-8 'ĩ' may not match @az

    def test_consonant_nh(self):
        v = Virgex("nh @az!1~")
        assert v.search("nha") is not None
        assert v.search("nhe") is not None

    def test_consonant_kh(self):
        v = Virgex("kh @az!1~")
        assert v.search("khong") is not None
        assert v.search("khoe") is not None

    def test_consonant_ph(self):
        v = Virgex("ph @az!1~")
        assert v.search("pho") is not None

    def test_consonant_th(self):
        v = Virgex("th @az!1~")
        assert v.search("the") is not None
        assert v.search("them") is not None

    def test_consonant_gi(self):
        v = Virgex("gi ?@az")
        assert v.search("gia") is not None
        assert v.search("gi") is not None

    def test_consonant_tr(self):
        v = Virgex("tr @az!1~")
        assert v.search("trong") is not None

    def test_consonant_ch(self):
        v = Virgex("ch @az!1~")
        assert v.search("cho") is not None

    def test_diphthong_patterns(self):
        """Vietnamese diphthong detection."""
        v = Virgex(":( uo | ua :)")
        assert v.search("mua") is not None
        assert v.search("muoi") is not None

    def test_syllable_structure(self):
        """Vietnamese syllable: (C)(w)V(C/w) tone."""
        # Match basic CV syllable
        v = Virgex("| @az!1~3 @az!1~3 |")
        assert v.fullmatch("ba")       # b + a
        assert v.fullmatch("chi")      # ch + i (approximate)
        assert v.fullmatch("trong")    # tr + ong


# ═══════════════════════════════════════════════════════
# 4. Chinese (Pinyin) Phonetic Patterns
# ═══════════════════════════════════════════════════════

class TestChinesePhonetics:
    """Chinese Pinyin phonetic patterns."""

    def test_initials_zh_ch_sh(self):
        v = Virgex(":( zh | ch | sh :) @az!1~")
        assert v.search("zhang") is not None
        assert v.search("chang") is not None
        assert v.search("shang") is not None

    def test_initials_j_q_x(self):
        v = Virgex(":( j | q | x :) :( i | u :)")
        assert v.search("ji") is not None
        assert v.search("qi") is not None
        assert v.search("xi") is not None

    def test_finals_ang_eng_ong(self):
        v = Virgex("@az!1~ :( ang | eng | ong :)")
        assert v.search("zhang") is not None
        assert v.search("sheng") is not None
        assert v.search("zhong") is not None

    def test_pinyin_syllable(self):
        """Basic Pinyin syllable structure: Initial + Final."""
        v = Virgex("| @az!1~6 |")
        assert v.fullmatch("ma")
        assert v.fullmatch("zhuan")
        assert v.fullmatch("shuang")


# ═══════════════════════════════════════════════════════
# 5. Japanese Phonetic Patterns
# ═══════════════════════════════════════════════════════

class TestJapanesePhonetics:
    """Japanese phonetic patterns (Romaji-based)."""

    def test_special_syllables(self):
        v = Virgex(":( shi | chi | tsu | fu :)")
        assert v.search("sushi") is not None      # su-shi
        assert v.search("matchi") is not None      # match-chi (approximate)
        assert v.search("fuji") is not None        # fu-ji
        assert v.search("tsuki") is not None       # tsu-ki

    def test_long_vowels(self):
        v = Virgex(":( aa | ii | uu | ee | oo :)")
        assert v.search("obaasan") is not None     # o-baa-san
        assert v.search("suugaku") is not None     # suu-gaku
        assert v.search("oniisan") is not None     # oni-isan? (ii)

    def test_romaji_syllable(self):
        """Basic Japanese CV syllable in romaji."""
        v = Virgex("| :( @az!1~2 @az :)!1~ |")
        assert v.fullmatch("ka")
        assert v.fullmatch("shi")
        assert v.fullmatch("tsu")


# ═══════════════════════════════════════════════════════
# 6. Korean Phonetic Patterns
# ═══════════════════════════════════════════════════════

class TestKoreanPhonetics:
    """Korean phonetic patterns (Romanization-based)."""

    def test_aspirated_consonants(self):
        v = Virgex(":( kh | th | ph | ch :) @az!1~")
        assert v.search("khada") is not None
        assert v.search("thada") is not None

    def test_double_consonants(self):
        v = Virgex(":( kk | tt | pp | ss | jj :)")
        assert v.search("kka") is not None
        assert v.search("tta") is not None
        assert v.search("ssa") is not None


# ═══════════════════════════════════════════════════════
# 7. English Phonetic Patterns
# ═══════════════════════════════════════════════════════

class TestEnglishPhonetics:
    """English phonetic patterns."""

    def test_digraphs(self):
        """Common English digraphs."""
        v = Virgex(":( th | sh | ch | ph | wh :)")
        assert v.search("the") is not None
        assert v.search("ship") is not None
        assert v.search("church") is not None
        assert v.search("phone") is not None
        assert v.search("what") is not None

    def test_silent_initial_k(self):
        v = Virgex("| kn @az!1~ |")
        assert v.fullmatch("know")
        assert v.fullmatch("knife")
        assert v.fullmatch("knight")

    def test_silent_initial_w(self):
        v = Virgex("| wr @az!1~ |")
        assert v.fullmatch("write")
        assert v.fullmatch("wrong")
        assert v.fullmatch("wrap")

    def test_vowel_digraphs(self):
        v = Virgex(":( ee | oo | ea | ai | oa :)")
        assert v.search("see") is not None
        assert v.search("moon") is not None
        assert v.search("rain") is not None

    def test_diphthongs(self):
        v = Virgex(":( ou | ow | oi | oy :)")
        assert v.search("house") is not None
        assert v.search("cow") is not None
        assert v.search("oil") is not None
        assert v.search("boy") is not None

    def test_ng_final(self):
        v = Virgex("@az!1~ ng")
        assert v.search("sing") is not None
        assert v.search("ring") is not None
        assert v.search("long") is not None


# ═══════════════════════════════════════════════════════
# 8. Complex Cross-language Pattern Tests
# ═══════════════════════════════════════════════════════

class TestCrossLanguagePatterns:
    """Patterns that work across languages."""

    def test_id_code_format(self):
        """Universal ID code: 2 upper + dash + 5 digits."""
        v = Virgex("| @AZ!2 $- @0!5 |")
        assert v.fullmatch("HN-12345")    # Vietnam
        assert v.fullmatch("BJ-67890")    # Beijing code
        assert v.fullmatch("TK-00001")    # Tokyo code
        assert not v.fullmatch("hn-12345")

    def test_phone_pattern(self):
        """Phone number: optional +, 1-3 digits, dash, 3 digits, dash, 4 digits."""
        v = Virgex("| ?:( $+ @0!1~3 :) @0!3 $- @0!4 |")
        assert v.fullmatch("123-4567")
        assert v.fullmatch("+84123-4567")
        assert v.fullmatch("+1123-4567")

    def test_email_username(self):
        """Email username: alphanumeric, 3-20 chars."""
        v = Virgex("| @Az0!3~20 |")
        assert v.fullmatch("user123")
        assert v.fullmatch("JohnDoe42")
        assert not v.fullmatch("ab")

    def test_hex_color(self):
        """Hex color: # + 6 hex digits (uppercase)."""
        v = Virgex("| $# @Az0!6 |")
        assert v.fullmatch("#FF00AA")
        assert v.fullmatch("#abc123")

    def test_date_format(self):
        """Date: DD/MM/YYYY."""
        v = Virgex("| @0!2 $/ @0!2 $/ @0!4 |")
        assert v.fullmatch("25/12/2024")
        assert v.fullmatch("01/01/2000")
        assert not v.fullmatch("1/1/2000")


# ═══════════════════════════════════════════════════════
# 9. VPS Error Handling
# ═══════════════════════════════════════════════════════

class TestVPSErrorHandling:
    """VPS should produce clear errors for invalid patterns."""

    def test_unterminated_group(self):
        with pytest.raises(Exception):
            Virgex(":( abc")

    def test_invalid_quantifier_range(self):
        with pytest.raises(Exception):
            Virgex("@0!5~3")  # max < min

    def test_unterminated_escape_block(self):
        with pytest.raises(Exception):
            Virgex("$.abc")  # no closing .$


# ═══════════════════════════════════════════════════════
# 10. VPS to Regex Translation Verification
# ═══════════════════════════════════════════════════════

class TestVPSToRegex:
    """Verify VPS → regex string translation is correct."""

    def test_simple_patterns(self):
        cases = [
            ("| @0!3 |",              r"^[0-9]{3}$"),
            ("| @AZ!2 |",            r"^[A-Z]{2}$"),
            ("| @az!1~5 |",          r"^[a-z]{1,5}$"),
            ("@0!1~",                r"[0-9]+"),
        ]
        for vps_pattern, expected_regex in cases:
            v = Virgex(vps_pattern)
            actual = v.regex
            assert actual == expected_regex, f"VPS '{vps_pattern}' → '{actual}' (expected '{expected_regex}')"

    def test_group_alternation_regex(self):
        v = Virgex(":( cat | dog :)")
        regex = v.regex
        assert "cat" in regex
        assert "dog" in regex
        assert "|" in regex

    def test_optional_regex(self):
        v = Virgex("?@0")
        regex = v.regex
        assert "?" in regex
        assert "[0-9]" in regex


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
