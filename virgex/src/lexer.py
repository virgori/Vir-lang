"""VPS Lexer — tokenises a VPS pattern string into a stream of Tokens."""

from __future__ import annotations

from .errors import VPSLexError
from .tokens import Quantifier, Token, TokenType

# Named atoms in longest-first order for greedy matching.
_NAMED_ATOMS = ("Az0", "Az", "AZ", "az")


class Lexer:
    """Stateful scanner that converts a VPS source string to tokens."""

    def __init__(self, source: str) -> None:
        self._src = source
        self._pos = 0
        self._tokens: list[Token] = []

    # ── public API ────────────────────────────────────

    def tokenize(self) -> list[Token]:
        """Return the full token list (cached after first call)."""
        if self._tokens:
            return self._tokens
        while True:
            tok = self._next_token()
            self._tokens.append(tok)
            if tok.type is TokenType.EOF:
                break
        return self._tokens

    # ── internal helpers ──────────────────────────────

    def _at_end(self) -> bool:
        return self._pos >= len(self._src)

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        return self._src[idx] if idx < len(self._src) else "\0"

    def _advance(self, n: int = 1) -> str:
        chunk = self._src[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def _skip_whitespace(self) -> None:
        while not self._at_end() and self._src[self._pos] in " \t\r\n":
            self._pos += 1

    # ── main dispatch ─────────────────────────────────

    def _next_token(self) -> Token:
        self._skip_whitespace()
        if self._at_end():
            return Token(TokenType.EOF, "", self._pos)

        start = self._pos
        ch = self._peek()

        # Two-character tokens: :( and :)
        if ch == ":" and self._peek(1) == "(":
            self._advance(2)
            return Token(TokenType.GROUP_OPEN, ":(", start)
        if ch == ":" and self._peek(1) == ")":
            self._advance(2)
            return Token(TokenType.GROUP_CLOSE, ":)", start)

        # Atom
        if ch == "@":
            return self._lex_atom(start)

        # Quantifier
        if ch == "!":
            return self._lex_quantifier(start)

        # Optional
        if ch == "?":
            self._advance()
            return Token(TokenType.QUESTION, "?", start)

        # Pipe (anchor or OR — parser decides)
        if ch == "|":
            self._advance()
            return Token(TokenType.PIPE, "|", start)

        # Escape
        if ch == "$":
            return self._lex_escape(start)

        # Space token
        if ch == "-":
            self._advance()
            return Token(TokenType.SPACE_TOKEN, "-", start)

        # Literal character
        self._advance()
        return Token(TokenType.LITERAL, ch, start)

    # ── atom ──────────────────────────────────────────

    def _lex_atom(self, start: int) -> Token:
        self._advance()  # consume @

        # Try named atoms (longest-first)
        for name in _NAMED_ATOMS:
            if self._src[self._pos : self._pos + len(name)] == name:
                self._advance(len(name))
                return Token(TokenType.ATOM, f"@{name}", start, atom_name=name)

        # Numeric atom: two digits → range, single '0' → all digits
        if not self._at_end() and self._peek().isdigit():
            d1 = self._advance()
            if not self._at_end() and self._peek().isdigit():
                d2 = self._advance()
                name = d1 + d2
                if int(d1) > int(d2):
                    raise VPSLexError(
                        f"Invalid numeric atom range @{name}: "
                        f"start ({d1}) > end ({d2})",
                        start,
                    )
                return Token(TokenType.ATOM, f"@{name}", start, atom_name=name)
            return Token(TokenType.ATOM, f"@{d1}", start, atom_name=d1)

        raise VPSLexError("Expected atom name after @", start)

    # ── quantifier ────────────────────────────────────

    def _lex_quantifier(self, start: int) -> Token:
        self._advance()  # consume !
        self._skip_whitespace()

        # !~ → 0..unbounded
        if not self._at_end() and self._peek() == "~":
            self._advance()
            raw = self._src[start : self._pos]
            return Token(
                TokenType.QUANTIFIER, raw, start,
                quantifier=Quantifier(0, None),
            )

        # !n ...
        n = self._read_int()
        if n is None:
            raise VPSLexError("Expected number or ~ after !", start)

        self._skip_whitespace()

        # !n~m or !n~
        if not self._at_end() and self._peek() == "~":
            self._advance()
            self._skip_whitespace()
            m = self._read_int()  # None → unbounded
            raw = self._src[start : self._pos]
            if m is not None and m < n:
                raise VPSLexError(
                    f"Quantifier range invalid: min ({n}) > max ({m})", start
                )
            return Token(
                TokenType.QUANTIFIER, raw, start,
                quantifier=Quantifier(n, m),
            )

        # !n → exact
        raw = self._src[start : self._pos]
        return Token(
            TokenType.QUANTIFIER, raw, start,
            quantifier=Quantifier(n, n),
        )

    def _read_int(self) -> int | None:
        if self._at_end() or not self._peek().isdigit():
            return None
        digits = ""
        while not self._at_end() and self._peek().isdigit():
            digits += self._advance()
        return int(digits)

    # ── escape ────────────────────────────────────────

    def _lex_escape(self, start: int) -> Token:
        self._advance()  # consume $

        if self._at_end():
            raise VPSLexError("Unexpected end after $", start)

        # Block escape: $. ... .$
        if self._peek() == ".":
            self._advance()  # consume .
            return self._lex_escape_block(start)

        # Single character escape
        ch = self._advance()
        return Token(TokenType.ESCAPE_CHAR, f"${ch}", start)

    def _lex_escape_block(self, start: int) -> Token:
        buf: list[str] = []
        while not self._at_end():
            if self._peek() == "." and self._peek(1) == "$":
                self._advance(2)  # consume .$
                content = "".join(buf)
                raw = self._src[start : self._pos]
                return Token(TokenType.ESCAPE_BLOCK, raw, start)
            buf.append(self._advance())
        raise VPSLexError("Unterminated escape block $. ... .$", start)
