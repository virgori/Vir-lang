"""
test_tokenizer.py – Unit tests cho NGramTokenizer
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer, Token, NumberToken
from src.sublib.base import SubLibRegistry
import src.sublib.vi  # noqa: F401 – trigger adapter registration


@pytest.fixture
def tokenizer():
    adapter = SubLibRegistry.get("vi")
    return NGramTokenizer(adapter)


@pytest.fixture
def adapter():
    return SubLibRegistry.get("vi")


class TestTokenizer:
    def test_basic_func_def(self, tokenizer):
        tokens = tokenizer.tokenize("Ta có hàm cộng A B")
        ir_types = [t.ir_token for t in tokens]
        assert "func_def" in ir_types

    def test_if_condition(self, tokenizer):
        tokens = tokenizer.tokenize("Nếu mà X lớn hơn Y")
        ir_types = [t.ir_token for t in tokens]
        assert "if" in ir_types
        assert "cmp_gt" in ir_types

    def test_arithmetic(self, tokenizer):
        tokens = tokenizer.tokenize("Tính tổng A B")
        ir_types = [t.ir_token for t in tokens]
        assert "op_add" in ir_types

    def test_stop_words_removed(self, tokenizer):
        tokens = tokenizer.tokenize("thì là nhé giúp")
        assert len(tokens) == 0

    def test_number_token(self, tokenizer):
        tokens = tokenizer.tokenize("cho biến X 42")
        nums = [t for t in tokens if isinstance(t, NumberToken)]
        assert len(nums) == 1
        assert nums[0].value == 42.0

    def test_check_cpu(self, tokenizer):
        tokens = tokenizer.tokenize("Nếu máy rảnh tính tổng A B")
        ir_types = [t.ir_token for t in tokens]
        assert "check_cpu" in ir_types or "if" in ir_types

    def test_register_target(self, tokenizer):
        tokens = tokenizer.tokenize("bằng thanh ghi")
        ir_types = [t.ir_token for t in tokens]
        assert "target_register" in ir_types

    def test_mixed_vietnamese(self, tokenizer):
        tokens = tokenizer.tokenize(
            "Nếu máy rảnh, tính tổng A và B bằng thanh ghi."
        )
        # Should have at least: CHECK_CPU/IF, OP_ADD, identifiers, TARGET_REGISTER
        ir_types = [t.ir_token for t in tokens]
        assert any(t in ir_types for t in ["check_cpu", "if"])
        assert "op_add" in ir_types


class TestSubLibAdapter:
    def test_adapter_available(self):
        available = SubLibRegistry.available()
        assert "vi" in available

    def test_adapter_lookup(self, adapter):
        kind = adapter.lookup("ta có hàm")
        assert kind is not None
        assert kind.value == "func_def"

    def test_adapter_stop_word(self, adapter):
        assert adapter.is_stop_word("thì")
        assert adapter.is_stop_word("nhé")
        assert not adapter.is_stop_word("tính tổng")

    def test_adapter_all_phrases(self, adapter):
        phrases = adapter.all_phrases()
        assert len(phrases) > 0

    def test_adapter_max_ngram(self, adapter):
        assert adapter.max_ngram >= 1
