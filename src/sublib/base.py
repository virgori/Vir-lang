"""
base.py – SubLib Base Adapter & Registry
==========================================
Defines the interface all language adapters must implement,
plus a global registry for discovering and loading adapters.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.lib.keywords import TokenKind


# ═══════════════════════════════════════════════════════════
# Phrase Entry (one native phrase → one TokenKind)
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PhraseEntry:
    """Maps one native-language phrase to a canonical TokenKind."""
    phrase: str           # Native text, e.g. "nếu", "もし", "如果"
    kind: TokenKind       # Canonical token, e.g. TokenKind.IF
    category: str = ""    # Optional grouping


# ═══════════════════════════════════════════════════════════
# Abstract Adapter
# ═══════════════════════════════════════════════════════════

class SubLibAdapter(ABC):
    """
    Base class for all language adapters.

    Each adapter provides:
      - language code (ISO 639-1)
      - language name
      - phrase→TokenKind mapping
      - stop words
      - N-gram lookup
    """

    def __init__(self) -> None:
        self._phrase_index: dict[str, PhraseEntry] = {}
        self._stop_words: set[str] = set()
        self._max_ngram: int = 1
        self._build_index()

    # ── Abstract methods (subclasses implement) ────────────
    @property
    @abstractmethod
    def lang_code(self) -> str:
        """ISO 639-1 code, e.g. 'vi', 'zh', 'ja', 'en'."""
        ...

    @property
    @abstractmethod
    def lang_name(self) -> str:
        """Human-readable name, e.g. 'Tiếng Việt', '中文'."""
        ...

    @abstractmethod
    def _define_phrases(self) -> list[PhraseEntry]:
        """Return all phrase→TokenKind mappings for this language."""
        ...

    @abstractmethod
    def _define_stop_words(self) -> list[str]:
        """Return stop words to ignore during tokenization."""
        ...

    # ── Build index ────────────────────────────────────────
    def _build_index(self) -> None:
        """Build the phrase index from _define_phrases()."""
        for entry in self._define_phrases():
            key = entry.phrase.lower().strip()
            self._phrase_index[key] = entry
            word_count = len(key.split())
            if word_count > self._max_ngram:
                self._max_ngram = word_count

        self._stop_words = {w.lower().strip() for w in self._define_stop_words()}

    # ── Public API ─────────────────────────────────────────
    def lookup(self, phrase: str) -> Optional[TokenKind]:
        """Look up a native phrase → TokenKind, or None."""
        entry = self._phrase_index.get(phrase.lower().strip())
        return entry.kind if entry else None

    def lookup_entry(self, phrase: str) -> Optional[PhraseEntry]:
        """Look up a native phrase → full PhraseEntry, or None."""
        return self._phrase_index.get(phrase.lower().strip())

    def is_stop_word(self, word: str) -> bool:
        return word.lower().strip() in self._stop_words

    @property
    def max_ngram(self) -> int:
        return self._max_ngram

    def all_phrases(self) -> list[str]:
        """All registered phrases, longest first."""
        return sorted(self._phrase_index.keys(), key=lambda p: -len(p.split()))

    def phrases_for_kind(self, kind: TokenKind) -> list[str]:
        """All phrases that map to a given TokenKind."""
        return [e.phrase for e in self._phrase_index.values() if e.kind == kind]

    def __repr__(self) -> str:
        return (f"<SubLibAdapter lang={self.lang_code} "
                f"phrases={len(self._phrase_index)} "
                f"max_ngram={self._max_ngram}>")


# ═══════════════════════════════════════════════════════════
# Global Registry
# ═══════════════════════════════════════════════════════════

class SubLibRegistry:
    """
    Discovers and manages language adapters.

    Usage:
        SubLibRegistry.register(VietnameseAdapter)
        adapter = SubLibRegistry.get("vi")
    """

    _adapters: dict[str, type[SubLibAdapter]] = {}
    _instances: dict[str, SubLibAdapter] = {}

    @classmethod
    def register(cls, adapter_cls: type[SubLibAdapter]) -> type[SubLibAdapter]:
        """Register an adapter class. Can be used as a decorator."""
        instance = adapter_cls()
        cls._adapters[instance.lang_code] = adapter_cls
        cls._instances[instance.lang_code] = instance
        return adapter_cls

    @classmethod
    def get(cls, lang_code: str) -> SubLibAdapter:
        """Get a language adapter by ISO 639-1 code. Raises KeyError."""
        code = lang_code.lower().strip()
        if code not in cls._instances:
            raise KeyError(
                f"No sublib adapter for '{code}'. "
                f"Available: {list(cls._instances.keys())}"
            )
        return cls._instances[code]

    @classmethod
    def available(cls) -> list[str]:
        """List available language codes."""
        return list(cls._instances.keys())

    @classmethod
    def all_adapters(cls) -> dict[str, SubLibAdapter]:
        """Return all registered adapters."""
        return dict(cls._instances)
