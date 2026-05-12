"""
VSS Parser — Recursive-descent parser for Vir Style Sheets.
==============================================================
Parses VSSToken stream into a VSSStylesheet AST.

Grammar (simplified BNF):
  stylesheet    = (import | theme | style | mixin | keyframes)*
  theme         = THEME IDENT COLON (declaration)* END
  style         = STYLE IDENT COLON (declaration | nested_rule)* END
  mixin         = MIXIN IDENT LPAREN params RPAREN COLON (declaration)* END
  keyframes     = KEYFRAMES IDENT COLON (step)* END
  declaration   = IDENT COLON value (IMPORTANT)?
  nested_rule   = (AMPERSAND selector | WHEN condition | GT selector) COLON body END
  value         = literal | theme_ref | func_call | expr
"""

from __future__ import annotations

from src.vss.ast import (
    VSSStylesheet, VSSStyleBlock, VSSTheme, VSSMixin, VSSKeyframes,
    VSSDeclaration, VSSNestedRule, VSSCondition,
    VSSValue, VSSLiteral, VSSThemeRef, VSSFuncCall, VSSExpr, VSSValueList,
)
from src.vss.tokenizer import VSSToken, VSSTokenKind


class VSSParseError(Exception):
    """Raised on syntax errors during VSS parsing."""
    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        self.line = line
        self.col = col
        super().__init__(f"VSS parse error at line {line}, col {col}: {message}")


class VSSParser:
    """Recursive-descent parser for VSS token streams."""

    def __init__(self, tokens: list[VSSToken]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ── Helpers ──────────────────────────────────────────────

    def _current(self) -> VSSToken:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return VSSToken(VSSTokenKind.EOF, "", 0, 0)

    def _peek(self, offset: int = 0) -> VSSToken:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return VSSToken(VSSTokenKind.EOF, "", 0, 0)

    def _advance(self) -> VSSToken:
        tok = self._current()
        self._pos += 1
        return tok

    def _expect(self, kind: VSSTokenKind) -> VSSToken:
        tok = self._current()
        if tok.kind != kind:
            raise VSSParseError(
                f"Expected {kind.name}, got {tok.kind.name} ({tok.value!r})",
                tok.line, tok.col,
            )
        return self._advance()

    def _match(self, kind: VSSTokenKind) -> VSSToken | None:
        if self._current().kind == kind:
            return self._advance()
        return None

    def _at(self, *kinds: VSSTokenKind) -> bool:
        return self._current().kind in kinds

    def _expect_block_open(self) -> None:
        """Accept either LBRACE or COLON to open a block."""
        if self._at(VSSTokenKind.LBRACE):
            self._advance()
        elif self._at(VSSTokenKind.COLON):
            self._advance()
        else:
            raise VSSParseError(
                f"Expected '{{' or ':', got {self._current().kind.name}",
                self._current().line, self._current().col,
            )

    def _expect_block_close(self) -> None:
        """Accept either RBRACE or END to close a block."""
        if self._at(VSSTokenKind.RBRACE):
            self._advance()
        elif self._at(VSSTokenKind.END):
            self._advance()
        else:
            raise VSSParseError(
                f"Expected '}}' or 'end', got {self._current().kind.name}",
                self._current().line, self._current().col,
            )

    def _at_block_end(self) -> bool:
        """Check if current token closes a block."""
        return self._at(VSSTokenKind.RBRACE, VSSTokenKind.END, VSSTokenKind.EOF)

    # ── Top-level ────────────────────────────────────────────

    def parse(self) -> VSSStylesheet:
        """Parse full stylesheet into AST."""
        themes: list[VSSTheme] = []
        styles: list[VSSStyleBlock] = []
        mixins: list[VSSMixin] = []
        keyframes_list: list[VSSKeyframes] = []
        imports: list[str] = []

        while not self._at(VSSTokenKind.EOF):
            tok = self._current()

            if tok.kind == VSSTokenKind.INCLUDE:
                imports.append(self._parse_import())
            elif tok.kind == VSSTokenKind.THEME:
                themes.append(self._parse_theme())
            elif tok.kind == VSSTokenKind.STYLE:
                styles.append(self._parse_style())
            elif tok.kind == VSSTokenKind.MIXIN:
                mixins.append(self._parse_mixin())
            elif tok.kind == VSSTokenKind.KEYFRAMES:
                keyframes_list.append(self._parse_keyframes())
            else:
                raise VSSParseError(
                    f"Unexpected token {tok.kind.name} ({tok.value!r})",
                    tok.line, tok.col,
                )

        return VSSStylesheet(
            themes=tuple(themes),
            styles=tuple(styles),
            mixins=tuple(mixins),
            keyframes=tuple(keyframes_list),
            imports=tuple(imports),
        )

    # ── Import ───────────────────────────────────────────────

    def _parse_import(self) -> str:
        self._expect(VSSTokenKind.INCLUDE)
        path_tok = self._expect(VSSTokenKind.STRING)
        self._match(VSSTokenKind.SEMICOLON)
        # Strip quotes
        return path_tok.value.strip("\"'")

    # ── Theme ────────────────────────────────────────────────

    def _parse_name(self) -> str:
        """Parse a block name — either a STRING (quoted) or IDENT."""
        if self._at(VSSTokenKind.STRING):
            return self._advance().value.strip("\"'")
        return self._expect(VSSTokenKind.IDENT).value

    def _parse_theme(self) -> VSSTheme:
        self._expect(VSSTokenKind.THEME)
        name = self._parse_name()
        self._expect_block_open()

        variables: list[tuple[str, VSSValue]] = []
        while not self._at_block_end():
            var_name = self._expect(VSSTokenKind.IDENT).value
            self._expect(VSSTokenKind.COLON)
            value = self._parse_value()
            self._match(VSSTokenKind.SEMICOLON)
            variables.append((var_name, value))

        self._expect_block_close()
        return VSSTheme(name=name, variables=tuple(variables))

    # ── Style block ──────────────────────────────────────────

    def _parse_style(self) -> VSSStyleBlock:
        self._expect(VSSTokenKind.STYLE)
        name = self._parse_name()
        self._expect_block_open()

        declarations: list[VSSDeclaration] = []
        nested_rules: list[VSSNestedRule] = []
        mixins_applied: list[str] = []

        while not self._at_block_end():
            if self._at(VSSTokenKind.AMPERSAND):
                nested_rules.append(self._parse_nested_rule())
            elif self._at(VSSTokenKind.WHEN):
                nested_rules.append(self._parse_when_block())
            elif self._at(VSSTokenKind.GT):
                nested_rules.append(self._parse_child_rule())
            elif self._at(VSSTokenKind.APPLY):
                self._advance()
                # Accept either IDENT or STRING for mixin name
                if self._at(VSSTokenKind.STRING):
                    mixin_name = self._advance().value.strip("\"'")
                else:
                    mixin_name = self._expect(VSSTokenKind.IDENT).value
                self._match(VSSTokenKind.SEMICOLON)
                mixins_applied.append(mixin_name)
            else:
                declarations.append(self._parse_declaration())

        self._expect_block_close()
        return VSSStyleBlock(
            name=name,
            declarations=tuple(declarations),
            nested_rules=tuple(nested_rules),
            mixins_applied=tuple(mixins_applied),
        )

    # ── Mixin ────────────────────────────────────────────────

    def _parse_mixin(self) -> VSSMixin:
        self._expect(VSSTokenKind.MIXIN)
        name = self._parse_name()
        params: list[tuple[str, VSSValue | None]] = []

        if self._match(VSSTokenKind.LPAREN):
            while not self._at(VSSTokenKind.RPAREN, VSSTokenKind.EOF):
                pname = self._expect(VSSTokenKind.IDENT).value
                default = None
                if self._match(VSSTokenKind.COLON):
                    default = self._parse_value()
                params.append((pname, default))
                self._match(VSSTokenKind.COMMA)
                self._match(VSSTokenKind.SEMICOLON)
            self._expect(VSSTokenKind.RPAREN)

        self._expect_block_open()

        declarations: list[VSSDeclaration] = []
        while not self._at_block_end():
            declarations.append(self._parse_declaration())

        self._expect_block_close()
        return VSSMixin(
            name=name,
            params=tuple(params),
            declarations=tuple(declarations),
        )

    # ── Keyframes ────────────────────────────────────────────

    def _parse_keyframes(self) -> VSSKeyframes:
        self._expect(VSSTokenKind.KEYFRAMES)
        name = self._parse_name()
        self._expect_block_open()

        steps: list[tuple[str, tuple[VSSDeclaration, ...]]] = []
        while not self._at_block_end():
            # Step selector: 0%, 50%, 100%, from, to
            step_tok = self._advance()
            step_name = step_tok.value
            # Handle "50%" as NUMBER + PERCENT or UNIT_VALUE
            if step_tok.kind == VSSTokenKind.NUMBER and self._at(VSSTokenKind.PERCENT):
                self._advance()
                step_name += "%"
            elif step_tok.kind == VSSTokenKind.UNIT_VALUE and step_tok.value.endswith("%"):
                step_name = step_tok.value

            self._expect_block_open()
            decls: list[VSSDeclaration] = []
            while not self._at_block_end():
                decls.append(self._parse_declaration())
            self._expect_block_close()
            steps.append((step_name, tuple(decls)))

        self._expect_block_close()
        return VSSKeyframes(name=name, steps=tuple(steps))

    # ── Declaration ──────────────────────────────────────────

    def _parse_declaration(self) -> VSSDeclaration:
        prop_tok = self._expect(VSSTokenKind.IDENT)
        self._expect(VSSTokenKind.COLON)
        value = self._parse_value()
        important = self._match(VSSTokenKind.IMPORTANT) is not None
        self._match(VSSTokenKind.SEMICOLON)
        return VSSDeclaration(
            property=prop_tok.value,
            value=value,
            important=important,
        )

    # ── Nested rules ─────────────────────────────────────────

    def _parse_nested_rule(self) -> VSSNestedRule:
        """Parse &:pseudo, &::pseudo-element."""
        self._expect(VSSTokenKind.AMPERSAND)
        # Collect selector text until COLON that starts the block
        selector_parts = ["&"]
        # Expect a colon for pseudo (: or ::)
        if self._at(VSSTokenKind.COLON):
            self._advance()
            selector_parts.append(":")
            if self._at(VSSTokenKind.COLON):
                self._advance()
                selector_parts.append(":")
            # Pseudo name
            if self._at(VSSTokenKind.IDENT):
                selector_parts.append(self._advance().value)

        # Now expect the block open
        self._expect_block_open()

        declarations, nested_rules = self._parse_rule_body()
        self._expect_block_close()

        return VSSNestedRule(
            selector="".join(selector_parts),
            declarations=tuple(declarations),
            nested_rules=tuple(nested_rules),
        )

    def _parse_when_block(self) -> VSSNestedRule:
        """Parse: when width > 768px: ... end."""
        self._expect(VSSTokenKind.WHEN)
        condition = self._parse_condition()
        self._expect_block_open()

        declarations, nested_rules = self._parse_rule_body()
        self._expect_block_close()

        return VSSNestedRule(
            selector="when",
            condition=condition,
            declarations=tuple(declarations),
            nested_rules=tuple(nested_rules),
        )

    def _parse_child_rule(self) -> VSSNestedRule:
        """Parse: > child_selector: ... end."""
        self._expect(VSSTokenKind.GT)
        selector_parts = ["> "]
        if self._at(VSSTokenKind.IDENT):
            selector_parts.append(self._advance().value)
        self._expect_block_open()

        declarations, nested_rules = self._parse_rule_body()
        self._expect_block_close()

        return VSSNestedRule(
            selector="".join(selector_parts),
            declarations=tuple(declarations),
            nested_rules=tuple(nested_rules),
        )

    def _parse_rule_body(self) -> tuple[list[VSSDeclaration], list[VSSNestedRule]]:
        """Parse declarations and nested rules inside a rule block."""
        declarations: list[VSSDeclaration] = []
        nested: list[VSSNestedRule] = []

        while not self._at_block_end():
            if self._at(VSSTokenKind.AMPERSAND):
                nested.append(self._parse_nested_rule())
            elif self._at(VSSTokenKind.WHEN):
                nested.append(self._parse_when_block())
            elif self._at(VSSTokenKind.GT):
                nested.append(self._parse_child_rule())
            else:
                declarations.append(self._parse_declaration())

        return declarations, nested

    # ── Condition ────────────────────────────────────────────

    def _parse_condition(self) -> VSSCondition:
        prop_tok = self._expect(VSSTokenKind.IDENT)
        op_tok = self._advance()
        op_map = {
            VSSTokenKind.GT: ">",
            VSSTokenKind.LT: "<",
            VSSTokenKind.GTE: ">=",
            VSSTokenKind.LTE: "<=",
            VSSTokenKind.EQ: "==",
        }
        op = op_map.get(op_tok.kind)
        if op is None:
            raise VSSParseError(
                f"Expected comparison operator, got {op_tok.kind.name}",
                op_tok.line, op_tok.col,
            )
        value = self._parse_single_value()
        return VSSCondition(property=prop_tok.value, operator=op, value=value)

    # ── Value parsing ────────────────────────────────────────

    def _parse_value(self) -> VSSValue:
        """Parse a full value (may be space-separated list)."""
        first = self._parse_single_value()

        # Check for space-separated values (e.g., "0 2px 8px rgba(0,0,0,0.1)")
        parts: list[VSSValue] = [first]
        while (
            not self._at(
                VSSTokenKind.SEMICOLON, VSSTokenKind.END, VSSTokenKind.EOF,
                VSSTokenKind.IMPORTANT, VSSTokenKind.NEWLINE,
                VSSTokenKind.RBRACE,
            )
            and self._current().kind in (
                VSSTokenKind.NUMBER, VSSTokenKind.UNIT_VALUE, VSSTokenKind.COLOR,
                VSSTokenKind.IDENT, VSSTokenKind.STRING, VSSTokenKind.MINUS,
            )
        ):
            # If next token is IDENT followed by COLON, it's a new declaration
            if (self._current().kind == VSSTokenKind.IDENT
                    and self._peek(1).kind == VSSTokenKind.COLON):
                break
            parts.append(self._parse_single_value())

        if len(parts) == 1:
            return parts[0]
        return VSSValueList(items=tuple(parts))

    def _parse_single_value(self) -> VSSValue:
        """Parse a single atomic value."""
        tok = self._current()

        # Theme reference: (IDENT|THEME) DOT IDENT (e.g., theme.primary)
        if (tok.kind in (VSSTokenKind.IDENT, VSSTokenKind.THEME)
                and self._peek(1).kind == VSSTokenKind.DOT):
            theme_name = self._advance().value
            self._advance()  # dot
            var_name = self._expect(VSSTokenKind.IDENT).value
            ref = VSSThemeRef(theme_name=theme_name, var_name=var_name)
            # Check for function call on theme ref
            return ref

        # Function call: IDENT LPAREN args RPAREN
        if tok.kind == VSSTokenKind.IDENT and self._peek(1).kind == VSSTokenKind.LPAREN:
            func_name = self._advance().value
            self._advance()  # lparen
            args: list[VSSValue] = []
            while not self._at(VSSTokenKind.RPAREN, VSSTokenKind.EOF):
                args.append(self._parse_value())
                self._match(VSSTokenKind.COMMA)
            self._expect(VSSTokenKind.RPAREN)
            return VSSFuncCall(func_name=func_name, args=tuple(args))

        # Literals
        if tok.kind == VSSTokenKind.COLOR:
            return VSSLiteral(raw=self._advance().value)
        if tok.kind == VSSTokenKind.NUMBER:
            return VSSLiteral(raw=self._advance().value)
        if tok.kind == VSSTokenKind.UNIT_VALUE:
            return VSSLiteral(raw=self._advance().value)
        if tok.kind == VSSTokenKind.STRING:
            return VSSLiteral(raw=self._advance().value)
        if tok.kind == VSSTokenKind.IDENT:
            return VSSLiteral(raw=self._advance().value)

        # Negative number: MINUS + NUMBER/UNIT_VALUE
        if tok.kind == VSSTokenKind.MINUS:
            self._advance()
            next_tok = self._current()
            if next_tok.kind in (VSSTokenKind.NUMBER, VSSTokenKind.UNIT_VALUE):
                return VSSLiteral(raw="-" + self._advance().value)
            return VSSLiteral(raw="-")

        raise VSSParseError(
            f"Expected value, got {tok.kind.name} ({tok.value!r})",
            tok.line, tok.col,
        )
