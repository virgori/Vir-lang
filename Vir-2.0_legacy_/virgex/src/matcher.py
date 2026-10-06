"""VPS Matcher — high-level API for compiling and matching VPS patterns.

Supports two engines:
  - 'regex' (default): Compiles VPS → Python regex via re module
  - 'nfa': Thompson NFA simulation — guaranteed O(n*m), no backtracking
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .compiler import Compiler
from .lexer import Lexer
from .parser import Parser
from .nfa import compile_nfa, nfa_fullmatch, nfa_search, nfa_findall


@dataclass(frozen=True, slots=True)
class VPSMatch:
    """Result of a successful match."""
    start: int
    end: int
    text: str

    def group(self) -> str:
        return self.text


class Virgex:
    """Compiled VPS pattern — analogous to ``re.Pattern``.

    Parameters
    ----------
    source : str
        The VPS pattern string.
    engine : str
        'regex' (default) or 'nfa' (Thompson NFA, no backtracking).
    """

    def __init__(self, source: str, *, engine: str = "regex") -> None:
        self.source = source
        self._engine = engine
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        if engine == "nfa":
            self._nfa = compile_nfa(ast)
            self._regex = None
            self._regex_str = "(NFA engine)"
        else:
            regex_str = Compiler().compile(ast)
            self._regex = re.compile(regex_str)
            self._regex_str = regex_str
            self._nfa = None

    @property
    def regex(self) -> str:
        """Return the compiled regex string (for inspection/debugging)."""
        return self._regex_str

    def fullmatch(self, text: str) -> VPSMatch | None:
        if self._nfa is not None:
            if nfa_fullmatch(self._nfa, text):
                return VPSMatch(start=0, end=len(text), text=text)
            return None
        m = self._regex.fullmatch(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def match(self, text: str) -> VPSMatch | None:
        if self._nfa is not None:
            result = nfa_search(self._nfa, text)
            if result is not None and result[0] == 0:
                s, e = result
                return VPSMatch(start=s, end=e, text=text[s:e])
            return None
        m = self._regex.match(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def search(self, text: str) -> VPSMatch | None:
        if self._nfa is not None:
            result = nfa_search(self._nfa, text)
            if result is not None:
                s, e = result
                return VPSMatch(start=s, end=e, text=text[s:e])
            return None
        m = self._regex.search(text)
        if m is None:
            return None
        return VPSMatch(start=m.start(), end=m.end(), text=m.group())

    def findall(self, text: str) -> list[str]:
        if self._nfa is not None:
            spans = nfa_findall(self._nfa, text)
            return [text[s:e] for s, e in spans]
        return self._regex.findall(text)

    def __repr__(self) -> str:
        return f"Virgex({self.source!r}, engine={self._engine!r})"


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
