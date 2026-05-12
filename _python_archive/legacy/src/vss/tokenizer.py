"""
VSS Tokenizer — Lexer for Vir Style Sheets.
=============================================
Tokenizes `.vss` source into a stream of VSSToken objects.
Supports multilingual keywords via sublib adapters.

Token types mirror CSS concepts plus VSS extensions:
  THEME, STYLE, MIXIN, KEYFRAMES, WHEN, END,
  IDENT, NUMBER, STRING, COLOR, COLON, SEMICOLON,
  LBRACE (→ treated as colon in Vir syntax), etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import re


# =============================================================================
#  Token Types
# =============================================================================

class VSSTokenKind(Enum):
    """Token kinds for VSS lexer."""

    # Keywords
    THEME = auto()
    STYLE = auto()
    MIXIN = auto()
    KEYFRAMES = auto()
    END = auto()
    WHEN = auto()
    INCLUDE = auto()
    APPLY = auto()
    IMPORTANT = auto()

    # Literals
    IDENT = auto()           # property names, class names, theme refs
    NUMBER = auto()          # 16, 0.5, 768
    STRING = auto()          # "hello", 'world'
    COLOR = auto()           # #ff0000, #fff
    UNIT_VALUE = auto()      # 16px, 1.5em, 100%, 100vw

    # Delimiters
    COLON = auto()           # :
    SEMICOLON = auto()       # ;
    COMMA = auto()           # ,
    DOT = auto()             # .
    AMPERSAND = auto()       # &
    LPAREN = auto()          # (
    RPAREN = auto()          # )
    LBRACKET = auto()        # [
    RBRACKET = auto()        # ]
    LBRACE = auto()          # {
    RBRACE = auto()          # }

    # Operators
    PLUS = auto()            # +
    MINUS = auto()           # -
    STAR = auto()            # *
    SLASH = auto()           # /
    GT = auto()              # >
    LT = auto()              # <
    GTE = auto()             # >=
    LTE = auto()             # <=
    EQ = auto()              # ==
    PERCENT = auto()         # % (as operator, not unit)

    # Special
    NEWLINE = auto()
    EOF = auto()
    INVALID = auto()


# =============================================================================
#  Token
# =============================================================================

@dataclass(frozen=True)
class VSSToken:
    """Single token from VSS lexer."""
    kind: VSSTokenKind
    value: str
    line: int = 0
    col: int = 0


# =============================================================================
#  Tokenizer
# =============================================================================

# Regex for unit values: number + unit
_UNIT_RE = re.compile(
    r"^(\d+\.?\d*)(px|em|rem|vw|vh|vmin|vmax|ch|ex|cm|mm|in|pt|pc|%|fr|s|ms|deg|rad|turn)$"
)

# Regex for colors
_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3,8})$")

# Regex for numbers
_NUMBER_RE = re.compile(r"^\d+\.?\d*$")


class VSSTokenizer:
    """Lexer for `.vss` source files.

    Supports multilingual keywords via keyword_map parameter.
    Default: English keywords.
    """

    def __init__(self, source: str, keyword_map: dict[str, VSSTokenKind] | None = None) -> None:
        self._source = source
        # Default English keywords
        self._keywords: dict[str, VSSTokenKind] = {}
        if keyword_map is not None:
            self._keywords = dict(keyword_map)
        else:
            kw_map = {
                "theme": "THEME", "style": "STYLE", "mixin": "MIXIN",
                "keyframes": "KEYFRAMES", "end": "END", "when": "WHEN",
                "include": "INCLUDE", "apply": "APPLY", "important": "IMPORTANT",
            }
            for word, kind_name in kw_map.items():
                try:
                    self._keywords[word] = VSSTokenKind[kind_name]
                except KeyError:
                    pass

    def tokenize(self) -> list[VSSToken]:
        """Tokenize VSS source into a list of tokens."""
        tokens: list[VSSToken] = []
        source = self._source
        lines = source.split("\n")

        for line_no, line in enumerate(lines, start=1):
            col = 0
            text = line

            # Strip single-line comments (// ...)
            comment_idx = text.find("//")
            if comment_idx >= 0:
                text = text[:comment_idx]

            # Strip block comments (/* ... */)  — single-line only here
            while "/*" in text:
                start = text.find("/*")
                end = text.find("*/", start + 2)
                if end >= 0:
                    text = text[:start] + text[end + 2:]
                else:
                    text = text[:start]
                    break

            text = text.rstrip()
            if not text.strip():
                continue

            i = 0
            while i < len(text):
                ch = text[i]

                # Skip whitespace
                if ch in (" ", "\t"):
                    i += 1
                    continue

                # Single-char delimiters
                if ch == ":":
                    tokens.append(VSSToken(VSSTokenKind.COLON, ":", line_no, i))
                    i += 1
                    continue
                if ch == ";":
                    tokens.append(VSSToken(VSSTokenKind.SEMICOLON, ";", line_no, i))
                    i += 1
                    continue
                if ch == ",":
                    tokens.append(VSSToken(VSSTokenKind.COMMA, ",", line_no, i))
                    i += 1
                    continue
                if ch == ".":
                    tokens.append(VSSToken(VSSTokenKind.DOT, ".", line_no, i))
                    i += 1
                    continue
                if ch == "&":
                    tokens.append(VSSToken(VSSTokenKind.AMPERSAND, "&", line_no, i))
                    i += 1
                    continue
                if ch == "{":
                    tokens.append(VSSToken(VSSTokenKind.LBRACE, "{", line_no, i))
                    i += 1
                    continue
                if ch == "}":
                    tokens.append(VSSToken(VSSTokenKind.RBRACE, "}", line_no, i))
                    i += 1
                    continue
                if ch == "(":
                    tokens.append(VSSToken(VSSTokenKind.LPAREN, "(", line_no, i))
                    i += 1
                    continue
                if ch == ")":
                    tokens.append(VSSToken(VSSTokenKind.RPAREN, ")", line_no, i))
                    i += 1
                    continue
                if ch == "[":
                    tokens.append(VSSToken(VSSTokenKind.LBRACKET, "[", line_no, i))
                    i += 1
                    continue
                if ch == "]":
                    tokens.append(VSSToken(VSSTokenKind.RBRACKET, "]", line_no, i))
                    i += 1
                    continue
                if ch == "+":
                    tokens.append(VSSToken(VSSTokenKind.PLUS, "+", line_no, i))
                    i += 1
                    continue
                if ch == "*":
                    tokens.append(VSSToken(VSSTokenKind.STAR, "*", line_no, i))
                    i += 1
                    continue
                if ch == "/":
                    tokens.append(VSSToken(VSSTokenKind.SLASH, "/", line_no, i))
                    i += 1
                    continue

                # Multi-char operators
                if ch == ">" and i + 1 < len(text) and text[i + 1] == "=":
                    tokens.append(VSSToken(VSSTokenKind.GTE, ">=", line_no, i))
                    i += 2
                    continue
                if ch == "<" and i + 1 < len(text) and text[i + 1] == "=":
                    tokens.append(VSSToken(VSSTokenKind.LTE, "<=", line_no, i))
                    i += 2
                    continue
                if ch == "=" and i + 1 < len(text) and text[i + 1] == "=":
                    tokens.append(VSSToken(VSSTokenKind.EQ, "==", line_no, i))
                    i += 2
                    continue
                if ch == ">":
                    tokens.append(VSSToken(VSSTokenKind.GT, ">", line_no, i))
                    i += 1
                    continue
                if ch == "<":
                    tokens.append(VSSToken(VSSTokenKind.LT, "<", line_no, i))
                    i += 1
                    continue

                # String literals
                if ch in ('"', "'"):
                    quote = ch
                    j = i + 1
                    while j < len(text) and text[j] != quote:
                        if text[j] == "\\" and j + 1 < len(text):
                            j += 1
                        j += 1
                    j += 1  # past closing quote
                    raw = text[i:j]
                    tokens.append(VSSToken(VSSTokenKind.STRING, raw, line_no, i))
                    i = j
                    continue

                # Color literals (#hex)
                if ch == "#":
                    j = i + 1
                    while j < len(text) and (text[j].isalnum()):
                        j += 1
                    raw = text[i:j]
                    if _COLOR_RE.match(raw):
                        tokens.append(VSSToken(VSSTokenKind.COLOR, raw, line_no, i))
                    else:
                        tokens.append(VSSToken(VSSTokenKind.INVALID, raw, line_no, i))
                    i = j
                    continue

                # Negative numbers
                if ch == "-" and i + 1 < len(text) and text[i + 1].isdigit():
                    j = i + 1
                    while j < len(text) and (text[j].isdigit() or text[j] == "."):
                        j += 1
                    # Check for unit suffix
                    k = j
                    while k < len(text) and text[k].isalpha():
                        k += 1
                    raw = text[i:k]
                    if _UNIT_RE.match(raw.lstrip("-")):
                        tokens.append(VSSToken(VSSTokenKind.UNIT_VALUE, raw, line_no, i))
                    else:
                        tokens.append(VSSToken(VSSTokenKind.NUMBER, text[i:j], line_no, i))
                        if k > j:
                            # Unit was separate — re-scan
                            pass
                    i = k if _UNIT_RE.match(raw.lstrip("-")) else j
                    continue

                # Minus (standalone)
                if ch == "-":
                    tokens.append(VSSToken(VSSTokenKind.MINUS, "-", line_no, i))
                    i += 1
                    continue

                # Numbers and unit values (16px, 0.5em, 100%)
                if ch.isdigit():
                    j = i
                    while j < len(text) and (text[j].isdigit() or text[j] == "."):
                        j += 1
                    # Check for unit suffix
                    k = j
                    while k < len(text) and (text[k].isalpha() or text[k] == "%"):
                        k += 1
                    raw = text[i:k]
                    if _UNIT_RE.match(raw):
                        tokens.append(VSSToken(VSSTokenKind.UNIT_VALUE, raw, line_no, i))
                        i = k
                    elif _NUMBER_RE.match(text[i:j]):
                        if k > j and text[j] == "%":
                            tokens.append(VSSToken(VSSTokenKind.UNIT_VALUE, text[i:k], line_no, i))
                            i = k
                        else:
                            tokens.append(VSSToken(VSSTokenKind.NUMBER, text[i:j], line_no, i))
                            i = j
                    else:
                        tokens.append(VSSToken(VSSTokenKind.NUMBER, text[i:j], line_no, i))
                        i = j
                    continue

                # Identifiers and keywords (supports Unicode for multilingual)
                if ch.isalpha() or ch == "_" or ord(ch) > 127:
                    j = i
                    while j < len(text) and (text[j].isalnum() or text[j] == "_" or ord(text[j]) > 127):
                        j += 1
                    word = text[i:j]
                    kw = self._keywords.get(word)
                    if kw is not None:
                        tokens.append(VSSToken(kw, word, line_no, i))
                    else:
                        tokens.append(VSSToken(VSSTokenKind.IDENT, word, line_no, i))
                    i = j
                    continue

                # Unknown character
                tokens.append(VSSToken(VSSTokenKind.INVALID, ch, line_no, i))
                i += 1

        tokens.append(VSSToken(VSSTokenKind.EOF, "", len(lines), 0))
        return tokens
