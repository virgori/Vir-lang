"""
ngram_tokenizer.py – Universal N-Gram Tokenizer
==================================================
Tokenizes source text in ANY supported language via the lib/sublib system.

Pipeline:
  Source text (any language) → SubLibAdapter lookup → TokenKind → Token list

Supports:
  - Vietnamese (vi), Chinese (zh), Japanese (ja), Korean (ko), English (en)
  - Any future sublib adapter added to src/sublib/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.lib.keywords import TokenKind
from src.sublib.base import SubLibAdapter


@dataclass(frozen=True)
class Token:
    """A single token after N-gram resolution."""

    kind: TokenKind        # Canonical TokenKind from lib
    raw_text: str          # Original text from source
    position: int          # Character offset in source
    lang: str = ""         # Source language code (vi/zh/ja/ko/en)

    # Legacy compat: ir_token property for old parser
    @property
    def ir_token(self) -> str:
        return self.kind.value

    def __repr__(self) -> str:
        return f"<Token {self.kind.name} '{self.raw_text}' @{self.position}>"


@dataclass(frozen=True)
class IdentifierToken(Token):
    """Token for variable / function names."""
    pass


@dataclass(frozen=True)
class NumberToken(Token):
    """Token for numeric literals."""
    value: float = 0.0


@dataclass(frozen=True)
class StringToken(Token):
    """Token for string literals."""
    string_value: str = ""


# ── Regex patterns ─────────────────────────────────────────
_RE_NUMBER = re.compile(r"-?\d+(\.\d+)?")
_RE_IDENTIFIER = re.compile(r"[A-Za-zÀ-ỹ_\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]\w*", re.UNICODE)
_RE_WHITESPACE = re.compile(r"\s+")
_RE_STRING = re.compile(r'"[^"]*"|\'[^\']*\'')


class NGramTokenizer:
    """
    Universal N-Gram Tokenizer.

    Algorithm:
    1. Normalize input (lowercase, strip punctuation, compress whitespace).
    2. Scan left-to-right, try longest N-gram first (Greedy Longest-Match).
    3. If N-gram matches a sublib phrase → emit Token with canonical TokenKind.
    4. If no match → check number / identifier / string / stop-word.

    Works with ANY SubLibAdapter (Vietnamese, Chinese, Japanese, Korean, English).
    """

    def __init__(self, adapter: SubLibAdapter) -> None:
        self.adapter = adapter

    # ── Public API ─────────────────────────────────────────
    def tokenize(self, source: str) -> list[Token]:
        """Tokenize source text → list of Tokens using the loaded adapter."""
        source = self._strip_comments(source)
        normalized = self._normalize(source)
        words = normalized.split()
        tokens: list[Token] = []
        i = 0
        char_offset = 0

        while i < len(words):
            matched = False

            # Try N-gram from longest → shortest
            for n in range(min(self.adapter.max_ngram, len(words) - i), 0, -1):
                ngram = " ".join(words[i : i + n])
                kind = self.adapter.lookup(ngram)
                if kind is not None:
                    tokens.append(
                        Token(
                            kind=kind,
                            raw_text=ngram,
                            position=char_offset,
                            lang=self.adapter.lang_code,
                        )
                    )
                    char_offset += len(ngram) + 1
                    i += n
                    matched = True
                    break

            if matched:
                continue

            word = words[i]

            # Skip stop words
            if self.adapter.is_stop_word(word):
                char_offset += len(word) + 1
                i += 1
                continue

            # Number literal
            if _RE_NUMBER.fullmatch(word):
                tokens.append(
                    NumberToken(
                        kind=TokenKind.NUMBER,
                        raw_text=word,
                        position=char_offset,
                        lang=self.adapter.lang_code,
                        value=float(word),
                    )
                )
                char_offset += len(word) + 1
                i += 1
                continue

            # Identifier (variable / function name)
            if _RE_IDENTIFIER.fullmatch(word):
                tokens.append(
                    IdentifierToken(
                        kind=TokenKind.IDENTIFIER,
                        raw_text=word,
                        position=char_offset,
                        lang=self.adapter.lang_code,
                    )
                )
                char_offset += len(word) + 1
                i += 1
                continue

            # Unknown → skip
            char_offset += len(word) + 1
            i += 1

        return tokens

    # ── Internals ──────────────────────────────────────────
    @staticmethod
    def _strip_comments(text: str) -> str:
        """Strip block comments (## ... ##) and single-line comments (# ...)."""
        # Block comments: ## ... ## (may span multiple lines)
        text = re.sub(r'##.*?##', '', text, flags=re.DOTALL)
        # Single-line comments: # to end of line
        text = re.sub(r'#[^\n]*', '', text)
        return text

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize: lower, strip certain punctuation, compress whitespace.
        Dots and colons are preserved for floats, member access, and entities.
        """
        text = text.lower()
        # Preserving . and :. Removing , ; ! ? () " ' `
        text = re.sub(r"[,;!?()\"'`]", " ", text)
        text = _RE_WHITESPACE.sub(" ", text).strip()
        return text


# ═══════════════════════════════════════════════════════════
# Legacy compatibility – SublibMapping wrapper
# ═══════════════════════════════════════════════════════════

class LegacySublibBridge(SubLibAdapter):
    """
    Wraps the old SublibMapping (config/sublib_mapping.json) as a SubLibAdapter.
    Used for backward compatibility during migration.
    """

    def __init__(self) -> None:
        from src.frontend.sublib.sublib_loader import SublibMapping
        from src.lib.keywords import LEGACY_TOKEN_MAP
        self._legacy = SublibMapping.load()
        self._token_map = LEGACY_TOKEN_MAP
        super().__init__()

    @property
    def lang_code(self) -> str:
        return "vi-legacy"

    @property
    def lang_name(self) -> str:
        return "Tiếng Việt (Legacy JSON)"

    def _define_phrases(self) -> list[PhraseEntry]:
        from src.sublib.base import PhraseEntry
        entries = []
        for phrase, entry in self._legacy._phrase_index.items():
            kind = self._token_map.get(entry.ir_token)
            if kind:
                entries.append(PhraseEntry(phrase, kind, entry.category))
        return entries

    def _define_stop_words(self) -> list[str]:
        return list(self._legacy.stop_words)

