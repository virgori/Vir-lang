"""
sublib – Natural Language Adapters for Vir
============================================
Each sublib maps a natural language's native phrases → lib's TokenKind.

Architecture:
  sublib/
    __init__.py      ← this file, adapter base + registry
    vi.py            ← Vietnamese  (Tiếng Việt)
    zh.py            ← Chinese     (中文)
    ja.py            ← Japanese    (日本語)
    ko.py            ← Korean      (한국어)
    en.py            ← English     (identity mapping)
    …

Usage:
    from src.sublib import SubLibRegistry
    adapter = SubLibRegistry.get("vi")
    kind = adapter.lookup("nếu")  # → TokenKind.IF
"""

from src.sublib.base import SubLibAdapter, SubLibRegistry

__all__ = ["SubLibAdapter", "SubLibRegistry"]
