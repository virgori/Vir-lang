"""VPS Matcher — high-level API for compiling and matching VPS patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .compiler import Compiler
from .lexer import Lexer
from .parser import Parser


@dataclass(frozen=True, slots=True)
class VPSMatch:
    """Result of a successful match."""
    start: int
    end: int
    text: str

    def group(self) -> str:
        return self.text


class Virgex:
    """Compiled VPS pattern — analogous to ``re.Pattern``."""

    def __init__(self, source: str) -> None:
        self.source = source
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        regex_str = Compiler().compile(ast)
        self._regex = re.compile(regex_str)
        self._regex_str = regex_str

    @property
    def regex(self) -> str:
        """Return the compiled regex string (for inspection/debugging)."""
        return self._regex_str

    def fullmatch(self, text: str) -> VPSMatch | None:
        m = self._regex.fullmatch(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def match(self, text: str) -> VPSMatch | None:
        m = self._regex.match(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def search(self, text: str) -> VPSMatch | None:
        m = self._regex.search(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def findall(self, text: str) -> list[str]:
        return self._regex.findall(text)

    def __repr__(self) -> str:
        return f"Virgex({self.source!r}) → /{self._regex_str}/"


# ── Module-level convenience functions ────────────────

def compile(pattern: str) -> Virgex:  # noqa: A001
    """Compile a VPS pattern string into a Virgex object."""
    return Virgex(pattern)


def fullmatch(pattern: str, text: str) -> VPSMatch | None:
    return Virgex(pattern).fullmatch(text)


def match(pattern: str, text: str) -> VPSMatch | None:
    return Virgex(pattern).match(text)


def search(pattern: str, text: str) -> VPSMatch | None:
    return Virgex(pattern).search(text)


def findall(pattern: str, text: str) -> list[str]:
    return Virgex(pattern).findall(text)


def to_regex(pattern: str) -> str:
    """Translate a VPS pattern to its equivalent Python regex string."""
    tokens = Lexer(pattern).tokenize()
    ast = Parser(tokens).parse()
    return Compiler().compile(ast)
