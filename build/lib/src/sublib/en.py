"""
en.py – English SubLib Adapter (Identity Mapping)
===================================================
Maps English keywords → lib TokenKind.
This is the identity / reference adapter.
"""

from __future__ import annotations

from src.lib.keywords import TokenKind, KeywordRegistry
from src.sublib.base import PhraseEntry, SubLibAdapter, SubLibRegistry


@SubLibRegistry.register
class EnglishAdapter(SubLibAdapter):
    """English → TokenKind (identity adapter – reference implementation)."""

    @property
    def lang_code(self) -> str:
        return "en"

    @property
    def lang_name(self) -> str:
        return "English"

    def _define_phrases(self) -> list[PhraseEntry]:
        """
        Auto-generate from KeywordRegistry:
        every english keyword + aliases → its TokenKind.
        """
        reg = KeywordRegistry()
        entries: list[PhraseEntry] = []
        for kw in reg.all_keywords():
            entries.append(PhraseEntry(kw.english, kw.kind, kw.category))
            for alias in kw.aliases:
                entries.append(PhraseEntry(alias, kw.kind, kw.category))
        return entries

    def _define_stop_words(self) -> list[str]:
        return [
            "the", "a", "an", "is", "are", "was", "were", "be",
            "to", "of", "that", "it", "with", "at",
            "this", "by", "on", "so", "do", "does",
            "please", "just", "also", "very", "really", "here",
        ]
