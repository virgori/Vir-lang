"""Virgex — Vir Pattern Syntax (VPS) engine.

Usage::

    import virgex

    # Compile & match
    pat = virgex.compile("| @AZ!2 $- @0!5 |")
    assert pat.fullmatch("HN-12345")

    # One-shot
    assert virgex.fullmatch("| @0!3 |", "456")

    # Translate to regex
    print(virgex.to_regex("| @Az0!3~12 |"))  # ^[A-Za-z0-9]{3,12}$
"""

from .matcher import (  # noqa: F401
    Virgex,
    VPSMatch,
    compile,
    findall,
    fullmatch,
    match,
    search,
    to_regex,
)
from .errors import VPSError, VPSLexError, VPSParseError, VPSCompileError  # noqa: F401

__all__ = [
    "Virgex",
    "VPSMatch",
    "VPSError",
    "VPSLexError",
    "VPSParseError",
    "VPSCompileError",
    "compile",
    "fullmatch",
    "match",
    "search",
    "findall",
    "to_regex",
]
