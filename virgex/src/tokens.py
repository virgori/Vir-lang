"""VPS token definitions."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class TokenType(enum.Enum):
    # Structural
    ATOM = "ATOM"                   # @Az, @AZ, @az, @0, @06, @Az0
    QUANTIFIER = "QUANTIFIER"       # !n, !n~m, !n~, !~
    QUESTION = "QUESTION"           # ?
    GROUP_OPEN = "GROUP_OPEN"       # :(
    GROUP_CLOSE = "GROUP_CLOSE"     # :)
    PIPE = "PIPE"                   # |
    SPACE_TOKEN = "SPACE_TOKEN"     # -

    # Escape
    ESCAPE_CHAR = "ESCAPE_CHAR"     # $x  → single escaped character
    ESCAPE_BLOCK = "ESCAPE_BLOCK"   # $. ... .$  → literal block

    # Data
    LITERAL = "LITERAL"             # any literal character

    # Control
    EOF = "EOF"


@dataclass(frozen=True, slots=True)
class Quantifier:
    """Parsed quantifier values."""
    min: int
    max: int | None  # None = unbounded

    def __repr__(self) -> str:
        if self.max is None:
            return f"!{self.min}~"
        if self.min == self.max:
            return f"!{self.min}"
        return f"!{self.min}~{self.max}"


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: str          # raw text consumed from source
    pos: int            # starting position in source

    # --- extra payload ---
    atom_name: str = ""                # for ATOM tokens
    quantifier: Quantifier | None = None  # for QUANTIFIER tokens

    def __repr__(self) -> str:
        extra = ""
        if self.atom_name:
            extra = f" atom={self.atom_name}"
        if self.quantifier is not None:
            extra = f" q={self.quantifier}"
        return f"Token({self.type.value}, {self.value!r}{extra}, @{self.pos})"
