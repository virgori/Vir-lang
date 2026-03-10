"""
sublib_loader.py – Bộ nạp Sublib Mapping
==========================================
Đọc file sublib_mapping.json và xây dựng cấu trúc dữ liệu cho N-Gram Tokenizer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "config" / "sublib_mapping.json"


@dataclass(frozen=True)
class SublibEntry:
    """Một mục trong Sublib Mapping."""

    sub_key: str           # e.g. "SUB_DEFINITION"
    ir_token: str          # e.g. "TOKEN_FUNC_DEF"
    category: str          # e.g. "definition"
    phrases: tuple[str, ...]  # ("ta có hàm", "tạo hàm", …)


@dataclass
class SublibMapping:
    """Bảng ánh xạ hoàn chỉnh – cung cấp tra cứu N-gram nhanh."""

    entries: list[SublibEntry] = field(default_factory=list)
    stop_words: set[str] = field(default_factory=set)

    # Bảng tra cứu: phrase (lowercase, stripped) → SublibEntry
    _phrase_index: dict[str, SublibEntry] = field(default_factory=dict, repr=False)

    # Longest phrase length (in words) – dùng cho N-gram window
    max_ngram: int = 1

    # ── Factory ────────────────────────────────────────────────
    @classmethod
    def load(cls, path: Path | str | None = None) -> "SublibMapping":
        """Nạp SublibMapping từ file JSON."""
        path = Path(path) if path else _DEFAULT_MAPPING_PATH
        with open(path, encoding="utf-8") as f:
            raw: dict = json.load(f)

        stop_words = set(raw.pop("stop_words", []))
        _ = raw.pop("version", None)
        _ = raw.pop("description", None)

        entries: list[SublibEntry] = []
        phrase_index: dict[str, SublibEntry] = {}
        max_ngram = 1

        for sub_key, value in raw.items():
            if not isinstance(value, dict):
                continue
            tokens_list: list[str] = value.get("tokens", [])
            ir_token: str = value.get("ir_token", "")
            category: str = value.get("category", "")

            phrases = tuple(p.lower().strip() for p in tokens_list)
            entry = SublibEntry(
                sub_key=sub_key,
                ir_token=ir_token,
                category=category,
                phrases=phrases,
            )
            entries.append(entry)

            for phrase in phrases:
                phrase_index[phrase] = entry
                word_count = len(phrase.split())
                if word_count > max_ngram:
                    max_ngram = word_count

        mapping = cls(
            entries=entries,
            stop_words=stop_words,
            _phrase_index=phrase_index,
            max_ngram=max_ngram,
        )
        return mapping

    # ── Tra cứu ───────────────────────────────────────────────
    def lookup(self, phrase: str) -> Optional[SublibEntry]:
        """Tra cứu chính xác 1 cụm từ → SublibEntry hoặc None."""
        return self._phrase_index.get(phrase.lower().strip())

    def is_stop_word(self, word: str) -> bool:
        return word.lower().strip() in self.stop_words

    def all_phrases(self) -> list[str]:
        """Trả về danh sách tất cả các cụm từ đã đăng ký, sắp theo độ dài giảm dần."""
        return sorted(self._phrase_index.keys(), key=lambda p: -len(p.split()))
