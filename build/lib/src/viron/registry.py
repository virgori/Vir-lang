"""
Viron Command Registry — Đăng ký & tra cứu lệnh zero-cost.
============================================================
Registry dùng dict lookup O(1), không string matching runtime.
Alias chỉ thêm key mới trỏ cùng handler → zero overhead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandMeta:
    """Metadata cho một lệnh đã đăng ký."""
    name: str
    description: str
    usage: str
    handler: Callable[[Sequence[str]], int]
    category: str = "general"
    requires_maha: bool = False


class CommandRegistry:
    """
    Registry trung tâm cho tất cả lệnh Viron.
    
    Alias hoạt động zero-cost: mỗi alias là một key khác
    trong dict trỏ đến cùng CommandMeta object.
    Tra cứu luôn O(1) dict lookup, không regex/string transform.
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandMeta] = {}
        self._aliases: dict[str, str] = {}  # alias_name → canonical_name
        self._categories: dict[str, list[str]] = {}

    def register(self, meta: CommandMeta) -> None:
        """Đăng ký lệnh mới."""
        self._commands[meta.name] = meta
        cat = meta.category
        if cat not in self._categories:
            self._categories[cat] = []
        self._categories[cat].append(meta.name)

    def alias(self, alias_name: str, canonical_name: str) -> None:
        """
        Tạo alias zero-cost.
        alias_name sẽ trỏ trực tiếp đến handler của canonical_name.
        """
        if canonical_name not in self._commands:
            raise KeyError(f"Lệnh '{canonical_name}' chưa được đăng ký")
        self._aliases[alias_name] = canonical_name
        # Trỏ trực tiếp vào cùng CommandMeta → zero overhead khi resolve
        self._commands[alias_name] = self._commands[canonical_name]

    def resolve(self, name: str) -> CommandMeta | None:
        """Tra cứu lệnh O(1)."""
        return self._commands.get(name)

    def canonical_name(self, name: str) -> str | None:
        """Trả về tên gốc nếu đây là alias, hoặc chính nó."""
        if name in self._aliases:
            return self._aliases[name]
        if name in self._commands:
            return name
        return None

    def list_commands(self) -> list[CommandMeta]:
        """Liệt kê tất cả lệnh (không trùng alias)."""
        seen: set[str] = set()
        result: list[CommandMeta] = []
        for name, meta in self._commands.items():
            canon = self._aliases.get(name, name)
            if canon not in seen:
                seen.add(canon)
                result.append(meta)
        return result

    def list_by_category(self) -> dict[str, list[CommandMeta]]:
        """Liệt kê lệnh theo danh mục."""
        result: dict[str, list[CommandMeta]] = {}
        for cat, names in self._categories.items():
            result[cat] = [self._commands[n] for n in names]
        return result

    def is_alias(self, name: str) -> bool:
        return name in self._aliases

    def get_aliases(self, canonical_name: str) -> list[str]:
        """Lấy tất cả alias cho một lệnh."""
        return [a for a, c in self._aliases.items() if c == canonical_name]


# Singleton registry toàn cục
_global_registry = CommandRegistry()


def get_registry() -> CommandRegistry:
    return _global_registry


def register_command(
    name: str,
    description: str,
    usage: str,
    handler: Callable[[Sequence[str]], int],
    category: str = "general",
    requires_maha: bool = False,
) -> None:
    """Tiện ích đăng ký lệnh vào global registry."""
    meta = CommandMeta(
        name=name,
        description=description,
        usage=usage,
        handler=handler,
        category=category,
        requires_maha=requires_maha,
    )
    _global_registry.register(meta)


def register_alias(alias_name: str, canonical_name: str) -> None:
    """Tiện ích tạo alias vào global registry."""
    _global_registry.alias(alias_name, canonical_name)
