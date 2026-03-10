"""VPS Parser — converts a token stream into an AST."""

from __future__ import annotations

from .ast_nodes import (
    AtomNode,
    EscapedBlockNode,
    EscapedCharNode,
    GroupNode,
    LiteralNode,
    Node,
    OptionalNode,
    PatternNode,
    QuantifiedNode,
    SequenceNode,
    SpaceTokenNode,
)
from .errors import VPSParseError
from .tokens import Token, TokenType


class Parser:
    """Recursive-descent parser for VPS token streams."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ── public API ────────────────────────────────────

    def parse(self) -> PatternNode:
        anchor_start = self._check_anchor_start()
        body = self._parse_sequence()
        anchor_end = self._check_anchor_end()

        if not self._at_type(TokenType.EOF):
            tok = self._current()
            raise VPSParseError(
                f"Unexpected token {tok.type.value} ({tok.value!r})", tok.pos
            )

        return PatternNode(
            anchor_start=anchor_start,
            anchor_end=anchor_end,
            body=body,
        )

    # ── anchor detection ──────────────────────────────

    def _check_anchor_start(self) -> bool:
        """Consume leading | if it's at position 0 of the token stream."""
        if self._at_type(TokenType.PIPE):
            self._advance()
            return True
        return False

    def _check_anchor_end(self) -> bool:
        """Consume trailing | if the very next token is | and after that is EOF."""
        if (
            self._at_type(TokenType.PIPE)
            and self._peek_type(1) is TokenType.EOF
        ):
            self._advance()
            return True
        return False

    # ── sequence ──────────────────────────────────────

    def _parse_sequence(self) -> SequenceNode:
        items: list[Node] = []
        while not self._at_end() and not self._is_sequence_end():
            items.append(self._parse_expression())
        return SequenceNode(items=items)

    def _is_sequence_end(self) -> bool:
        tt = self._current().type
        return tt in (TokenType.GROUP_CLOSE, TokenType.PIPE, TokenType.EOF)

    # ── expression ────────────────────────────────────

    def _parse_expression(self) -> Node:
        # Optional prefix
        if self._at_type(TokenType.QUESTION):
            return self._parse_optional()

        node = self._parse_base()

        # Postfix quantifier
        if self._at_type(TokenType.QUANTIFIER):
            node = self._parse_quantifier(node)

        return node

    # ── optional (prefix ?) ───────────────────────────

    def _parse_optional(self) -> Node:
        self._expect(TokenType.QUESTION)
        inner = self._parse_expression()
        return OptionalNode(expression=inner)

    # ── quantifier (postfix !) ────────────────────────

    def _parse_quantifier(self, node: Node) -> Node:
        tok = self._expect(TokenType.QUANTIFIER)
        q = tok.quantifier
        assert q is not None
        return QuantifiedNode(expression=node, min=q.min, max=q.max)

    # ── base expressions ──────────────────────────────

    def _parse_base(self) -> Node:
        tok = self._current()

        if tok.type is TokenType.ATOM:
            self._advance()
            return AtomNode(name=tok.atom_name)

        if tok.type is TokenType.GROUP_OPEN:
            return self._parse_group()

        if tok.type is TokenType.SPACE_TOKEN:
            self._advance()
            return SpaceTokenNode()

        if tok.type is TokenType.ESCAPE_CHAR:
            self._advance()
            # value is "$x" → char is x
            return EscapedCharNode(char=tok.value[1])

        if tok.type is TokenType.ESCAPE_BLOCK:
            self._advance()
            # value is "$. content .$" → extract content
            content = tok.value[2:-2]  # strip $. and .$
            return EscapedBlockNode(content=content)

        if tok.type is TokenType.LITERAL:
            return self._parse_literal_run()

        raise VPSParseError(
            f"Unexpected token {tok.type.value} ({tok.value!r})", tok.pos
        )

    # ── literal run (merge consecutive literals) ──────

    def _parse_literal_run(self) -> LiteralNode:
        buf = ""
        while self._at_type(TokenType.LITERAL):
            buf += self._current().value
            self._advance()
        return LiteralNode(value=buf)

    # ── group ─────────────────────────────────────────

    def _parse_group(self) -> Node:
        self._expect(TokenType.GROUP_OPEN)
        alternatives: list[SequenceNode] = [self._parse_sequence()]

        while self._at_type(TokenType.PIPE):
            self._advance()  # consume |
            alternatives.append(self._parse_sequence())

        self._expect(TokenType.GROUP_CLOSE)

        node: Node = GroupNode(alternatives=alternatives)

        # Postfix quantifier on group
        if self._at_type(TokenType.QUANTIFIER):
            node = self._parse_quantifier(node)

        return node

    # ── token helpers ─────────────────────────────────

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    def _current(self) -> Token:
        if self._at_end():
            return Token(TokenType.EOF, "", -1)
        return self._tokens[self._pos]

    def _at_type(self, tt: TokenType) -> bool:
        return not self._at_end() and self._current().type is tt

    def _peek_type(self, offset: int) -> TokenType:
        idx = self._pos + offset
        if idx >= len(self._tokens):
            return TokenType.EOF
        return self._tokens[idx].type

    def _advance(self) -> Token:
        tok = self._current()
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        tok = self._current()
        if tok.type is not tt:
            raise VPSParseError(
                f"Expected {tt.value}, got {tok.type.value} ({tok.value!r})",
                tok.pos,
            )
        return self._advance()
