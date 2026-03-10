"""
lib – Vir Standard Library (English Core)
==========================================
Defines the canonical programming language keywords, operators,
and token types using standard English names.

Architecture:
  lib/   → English standard keywords & grammar rules
  sublib/ → Natural language adapters (Vietnamese, Chinese, Japanese, …)
"""

from src.lib.keywords import KeywordRegistry, TokenKind, Keyword

__all__ = ["KeywordRegistry", "TokenKind", "Keyword"]
