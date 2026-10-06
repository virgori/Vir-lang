"""
test_lib_sublib.py – Tests for the lib/sublib architecture
============================================================
Verifies:
  1. lib KeywordRegistry contains all expected tokens
  2. sublib adapters load and map phrases correctly
  3. NGramTokenizer works with each sublib
  4. Parser produces correct AST from multi-language input
"""

import pytest
from src.lib.keywords import KeywordRegistry, TokenKind, Keyword, LEGACY_TOKEN_MAP
from src.sublib.base import SubLibAdapter, SubLibRegistry

# Force all adapters to register
import src.sublib.vi
import src.sublib.zh
import src.sublib.ja
import src.sublib.ko
import src.sublib.en

from src.frontend.tokenizer.ngram_tokenizer import (
    NGramTokenizer,
    Token,
    NumberToken,
    IdentifierToken,
)
from src.frontend.parser.parser import (
    Parser,
    ProgramNode,
    FuncDefNode,
    VarDeclNode,
    ModuleStateNode,
    IfNode,
    BinOpNode,
    PrintNode,
    OutNode,
    ReturnNode,
)


# ═══════════════════════════════════════════════════════════
# 1. lib – KeywordRegistry
# ═══════════════════════════════════════════════════════════

class TestKeywordRegistry:
    def setup_method(self):
        self.reg = KeywordRegistry()

    def test_by_kind(self):
        kw = self.reg.by_kind(TokenKind.IF)
        assert kw is not None
        assert kw.english == "if"
        assert kw.kind == TokenKind.IF

    def test_by_english(self):
        kw = self.reg.by_english("function")
        assert kw is not None
        assert kw.kind == TokenKind.FUNC_DEF

    def test_alias_lookup(self):
        kw = self.reg.by_english("fn")
        assert kw is not None
        assert kw.kind == TokenKind.FUNC_DEF

    def test_operator_precedence(self):
        add = self.reg.by_kind(TokenKind.OP_ADD)
        mul = self.reg.by_kind(TokenKind.OP_MUL)
        assert add is not None and mul is not None
        assert mul.precedence > add.precedence

    def test_all_keywords_non_empty(self):
        assert len(self.reg.all_keywords()) > 30

    def test_categories(self):
        cats = self.reg.categories()
        assert "definition" in cats
        assert "control_flow" in cats
        assert "arithmetic" in cats

    def test_legacy_map(self):
        assert LEGACY_TOKEN_MAP["TOKEN_FUNC_DEF"] == TokenKind.FUNC_DEF
        assert LEGACY_TOKEN_MAP["TOKEN_IF_CONDITION"] == TokenKind.IF
        assert LEGACY_TOKEN_MAP["TOKEN_OP_ADD"] == TokenKind.OP_ADD
        assert LEGACY_TOKEN_MAP["TOKEN_RETURN"] == TokenKind.OUT
        assert LEGACY_TOKEN_MAP["TOKEN_CONTINUE"] == TokenKind.SKIP


# ═══════════════════════════════════════════════════════════
# 2. sublib – Adapter Registration
# ═══════════════════════════════════════════════════════════

class TestSubLibRegistry:
    def test_available_languages(self):
        available = SubLibRegistry.available()
        assert "vi" in available
        assert "zh" in available
        assert "ja" in available
        assert "ko" in available
        assert "en" in available

    def test_get_adapter(self):
        vi = SubLibRegistry.get("vi")
        assert vi.lang_code == "vi"
        assert vi.lang_name == "Tiếng Việt"

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            SubLibRegistry.get("xx")


# ═══════════════════════════════════════════════════════════
# 3. Vietnamese Adapter (vi)
# ═══════════════════════════════════════════════════════════

class TestVietnameseAdapter:
    def setup_method(self):
        self.vi = SubLibRegistry.get("vi")

    def test_if_lookup(self):
        assert self.vi.lookup("nếu") == TokenKind.IF
        assert self.vi.lookup("nếu mà") == TokenKind.IF

    def test_func_def_lookup(self):
        assert self.vi.lookup("ta có hàm") == TokenKind.FUNC_DEF
        assert self.vi.lookup("tạo hàm") == TokenKind.FUNC_DEF

    def test_arithmetic(self):
        assert self.vi.lookup("cộng") == TokenKind.OP_ADD
        assert self.vi.lookup("trừ") == TokenKind.OP_SUB
        assert self.vi.lookup("nhân") == TokenKind.OP_MUL
        assert self.vi.lookup("chia") == TokenKind.OP_DIV

    def test_comparison(self):
        assert self.vi.lookup("lớn hơn") == TokenKind.CMP_GT
        assert self.vi.lookup("nhỏ hơn") == TokenKind.CMP_LT

    def test_io(self):
        assert self.vi.lookup("in ra") == TokenKind.PRINT
        assert self.vi.lookup("nhập vào") == TokenKind.INPUT

    def test_system(self):
        assert self.vi.lookup("máy rảnh") == TokenKind.CHECK_CPU
        assert self.vi.lookup("vá mã") == TokenKind.PATCH

    def test_stop_words(self):
        assert self.vi.is_stop_word("thì")
        assert self.vi.is_stop_word("nhé")
        assert not self.vi.is_stop_word("cộng")

    def test_unknown_returns_none(self):
        assert self.vi.lookup("xyzabc") is None


# ═══════════════════════════════════════════════════════════
# 4. Chinese Adapter (zh)
# ═══════════════════════════════════════════════════════════

class TestChineseAdapter:
    def setup_method(self):
        self.zh = SubLibRegistry.get("zh")

    def test_if_lookup(self):
        assert self.zh.lookup("如果") == TokenKind.IF

    def test_func_def(self):
        assert self.zh.lookup("函数") == TokenKind.FUNC_DEF
        assert self.zh.lookup("定义函数") == TokenKind.FUNC_DEF

    def test_arithmetic(self):
        assert self.zh.lookup("加") == TokenKind.OP_ADD
        assert self.zh.lookup("减") == TokenKind.OP_SUB
        assert self.zh.lookup("乘") == TokenKind.OP_MUL
        assert self.zh.lookup("除") == TokenKind.OP_DIV

    def test_print(self):
        assert self.zh.lookup("打印") == TokenKind.PRINT


# ═══════════════════════════════════════════════════════════
# 5. Japanese Adapter (ja)
# ═══════════════════════════════════════════════════════════

class TestJapaneseAdapter:
    def setup_method(self):
        self.ja = SubLibRegistry.get("ja")

    def test_if_lookup(self):
        assert self.ja.lookup("もし") == TokenKind.IF

    def test_func_def(self):
        assert self.ja.lookup("関数") == TokenKind.FUNC_DEF

    def test_arithmetic(self):
        assert self.ja.lookup("足す") == TokenKind.OP_ADD
        assert self.ja.lookup("引く") == TokenKind.OP_SUB
        assert self.ja.lookup("掛ける") == TokenKind.OP_MUL
        assert self.ja.lookup("割る") == TokenKind.OP_DIV

    def test_return(self):
        assert self.ja.lookup("返す") == TokenKind.OUT


# ═══════════════════════════════════════════════════════════
# 6. Korean Adapter (ko)
# ═══════════════════════════════════════════════════════════

class TestKoreanAdapter:
    def setup_method(self):
        self.ko = SubLibRegistry.get("ko")

    def test_if_lookup(self):
        assert self.ko.lookup("만약") == TokenKind.IF

    def test_func_def(self):
        assert self.ko.lookup("함수") == TokenKind.FUNC_DEF

    def test_arithmetic(self):
        assert self.ko.lookup("더하기") == TokenKind.OP_ADD
        assert self.ko.lookup("빼기") == TokenKind.OP_SUB


# ═══════════════════════════════════════════════════════════
# 7. English Adapter (en) – identity mapping
# ═══════════════════════════════════════════════════════════

class TestEnglishAdapter:
    def setup_method(self):
        self.en = SubLibRegistry.get("en")

    def test_if_lookup(self):
        assert self.en.lookup("if") == TokenKind.IF
        assert self.en.lookup("when") == TokenKind.WHEN

    def test_func_def(self):
        assert self.en.lookup("function") == TokenKind.FUNC_DEF
        assert self.en.lookup("fn") == TokenKind.FUNC_DEF

    def test_operators(self):
        assert self.en.lookup("+") == TokenKind.OP_ADD
        assert self.en.lookup("add") == TokenKind.OP_ADD


# ═══════════════════════════════════════════════════════════
# 8. NGramTokenizer – multilingual
# ═══════════════════════════════════════════════════════════

class TestNGramTokenizer:
    def test_vietnamese_tokenize(self):
        vi = SubLibRegistry.get("vi")
        tok = NGramTokenizer(vi)
        tokens = tok.tokenize("Nếu mà X lớn hơn 10, in ra X")

        kinds = [t.kind for t in tokens]
        assert TokenKind.IF in kinds
        assert TokenKind.CMP_GT in kinds
        assert TokenKind.PRINT in kinds
        assert TokenKind.NUMBER in kinds

    def test_chinese_tokenize(self):
        zh = SubLibRegistry.get("zh")
        tok = NGramTokenizer(zh)
        tokens = tok.tokenize("如果 x 大于 10 打印 x")

        kinds = [t.kind for t in tokens]
        assert TokenKind.IF in kinds
        assert TokenKind.CMP_GT in kinds
        assert TokenKind.PRINT in kinds

    def test_japanese_tokenize(self):
        ja = SubLibRegistry.get("ja")
        tok = NGramTokenizer(ja)
        tokens = tok.tokenize("もし x 等しい 10 表示する x")

        kinds = [t.kind for t in tokens]
        assert TokenKind.IF in kinds
        assert TokenKind.CMP_EQ in kinds
        assert TokenKind.PRINT in kinds

    def test_english_tokenize(self):
        en = SubLibRegistry.get("en")
        tok = NGramTokenizer(en)
        tokens = tok.tokenize("function add x y out add x y")

        kinds = [t.kind for t in tokens]
        assert TokenKind.FUNC_DEF in kinds
        assert TokenKind.OUT in kinds
        assert TokenKind.OP_ADD in kinds

    def test_number_token(self):
        vi = SubLibRegistry.get("vi")
        tok = NGramTokenizer(vi)
        tokens = tok.tokenize("cho biến x 42")

        nums = [t for t in tokens if isinstance(t, NumberToken)]
        assert len(nums) == 1
        assert nums[0].value == 42.0

    def test_identifier_token(self):
        vi = SubLibRegistry.get("vi")
        tok = NGramTokenizer(vi)
        tokens = tok.tokenize("cho biến myVar 10")

        idents = [t for t in tokens if isinstance(t, IdentifierToken)]
        assert any(i.raw_text == "myvar" for i in idents)

    def test_stop_words_filtered(self):
        vi = SubLibRegistry.get("vi")
        tok = NGramTokenizer(vi)
        tokens = tok.tokenize("nếu thì nhé ơi cộng 1 2")

        raw_texts = [t.raw_text for t in tokens]
        assert "thì" not in raw_texts
        assert "nhé" not in raw_texts


# ═══════════════════════════════════════════════════════════
# 9. Parser with lib tokens
# ═══════════════════════════════════════════════════════════

class TestParserWithLibTokens:
    def _tokenize_vi(self, source: str) -> list[Token]:
        vi = SubLibRegistry.get("vi")
        return NGramTokenizer(vi).tokenize(source)

    def test_parse_func_def(self):
        tokens = self._tokenize_vi("ta có hàm hello")
        program = Parser(tokens).parse()
        assert len(program.statements) >= 1
        assert isinstance(program.statements[0], FuncDefNode)
        assert program.statements[0].name == "hello"

    def test_parse_var_decl(self):
        tokens = self._tokenize_vi("cho biến x 42")
        program = Parser(tokens).parse()
        assert len(program.statements) >= 1
        assert isinstance(program.statements[0], (VarDeclNode, ModuleStateNode))

    def test_parse_if(self):
        tokens = self._tokenize_vi("nếu x lớn hơn 10 in ra x")
        program = Parser(tokens).parse()
        found_if = False
        for stmt in program.statements:
            if isinstance(stmt, IfNode):
                found_if = True
                break
        assert found_if

    def test_parse_binop(self):
        tokens = self._tokenize_vi("cộng 3 5")
        program = Parser(tokens).parse()
        assert len(program.statements) >= 1
        assert isinstance(program.statements[0], BinOpNode)
        assert program.statements[0].op == "ADD"

    def test_parse_print(self):
        tokens = self._tokenize_vi("in ra 42")
        program = Parser(tokens).parse()
        assert len(program.statements) >= 1
        assert isinstance(program.statements[0], PrintNode)


# ═══════════════════════════════════════════════════════════
# 10. Cross-language parity
# ═══════════════════════════════════════════════════════════

class TestCrossLanguageParity:
    """Verify the same logical program produces same TokenKinds in all languages."""

    def _get_kinds(self, lang: str, source: str) -> list[TokenKind]:
        adapter = SubLibRegistry.get(lang)
        tokens = NGramTokenizer(adapter).tokenize(source)
        return [t.kind for t in tokens]

    def test_if_print_parity(self):
        """'if X > 10 print X' in all languages → same TokenKind sequence."""
        vi_kinds = self._get_kinds("vi", "nếu x lớn hơn 10 in ra x")
        zh_kinds = self._get_kinds("zh", "如果 x 大于 10 打印 x")
        ja_kinds = self._get_kinds("ja", "もし x より大きい 10 表示する x")
        ko_kinds = self._get_kinds("ko", "만약 x 크다 10 출력 x")

        for kinds in [vi_kinds, zh_kinds, ja_kinds, ko_kinds]:
            assert TokenKind.IF in kinds, f"IF missing in {kinds}"
            assert TokenKind.PRINT in kinds, f"PRINT missing in {kinds}"
            assert TokenKind.CMP_GT in kinds, f"CMP_GT missing in {kinds}"

    def test_add_parity(self):
        """'add 3 5' in all languages."""
        vi_kinds = self._get_kinds("vi", "cộng 3 5")
        zh_kinds = self._get_kinds("zh", "加 3 5")
        ja_kinds = self._get_kinds("ja", "足す 3 5")
        ko_kinds = self._get_kinds("ko", "더하기 3 5")

        for kinds in [vi_kinds, zh_kinds, ja_kinds, ko_kinds]:
            assert TokenKind.OP_ADD in kinds
            assert TokenKind.NUMBER in kinds
