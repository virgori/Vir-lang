"""
VSS AST — Node definitions for Vir Style Sheets.
===================================================
Immutable AST nodes representing parsed `.vss` files.

Design principles:
  - frozen dataclasses for immutability (matches QIR schema style)
  - Separate value types (literal, theme ref, function call, expression)
  - Recursive nesting for selectors and media queries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# =============================================================================
#  VSS Value Types
# =============================================================================

class VSSValueKind(Enum):
    """Discriminant for VSS value union."""
    LITERAL = auto()
    THEME_REF = auto()
    FUNC_CALL = auto()
    EXPR = auto()
    LIST = auto()


@dataclass(frozen=True)
class VSSValue:
    """Base value node in VSS."""
    kind: VSSValueKind = VSSValueKind.LITERAL


@dataclass(frozen=True)
class VSSLiteral(VSSValue):
    """Literal CSS value: '16px', '#ff0000', 'bold', '0 2px 8px rgba(0,0,0,0.1)'."""
    raw: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", VSSValueKind.LITERAL)


@dataclass(frozen=True)
class VSSThemeRef(VSSValue):
    """Reference to a theme variable: theme.primary, theme.radius."""
    theme_name: str | None = None     # None = current/default theme
    var_name: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", VSSValueKind.THEME_REF)


@dataclass(frozen=True)
class VSSFuncCall(VSSValue):
    """Function call: darken(theme.primary, 10%), rgba(0,0,0,0.5)."""
    func_name: str = ""
    args: tuple[VSSValue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", VSSValueKind.FUNC_CALL)


@dataclass(frozen=True)
class VSSExpr(VSSValue):
    """Arithmetic expression: base + 4px, width * 0.5."""
    op: str = "+"           # "+", "-", "*", "/"
    left: VSSValue | None = None
    right: VSSValue | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", VSSValueKind.EXPR)


@dataclass(frozen=True)
class VSSValueList(VSSValue):
    """Space-separated list of values: '0 2px 8px rgba(0,0,0,0.1)'."""
    items: tuple[VSSValue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", VSSValueKind.LIST)


# =============================================================================
#  VSS Condition — for `when` blocks (responsive/conditional)
# =============================================================================

@dataclass(frozen=True)
class VSSCondition:
    """Condition in a `when` block: width > 768px."""
    property: str = ""       # "width", "height", "prefers_dark"
    operator: str = ">"      # ">", "<", ">=", "<=", "=="
    value: VSSValue | None = None


# =============================================================================
#  VSS Declarations and Rules
# =============================================================================

@dataclass(frozen=True)
class VSSDeclaration:
    """Single property declaration: background: theme.primary."""
    property: str = ""       # Normalized CSS property name
    value: VSSValue | None = None
    important: bool = False


@dataclass(frozen=True)
class VSSNestedRule:
    """Nested rule: &:hover, > child, when width > 768px."""
    selector: str = ""                                  # "&:hover", "> .child"
    condition: VSSCondition | None = None                # For `when` blocks
    declarations: tuple[VSSDeclaration, ...] = ()
    nested_rules: tuple[VSSNestedRule, ...] = ()         # Recursive


# =============================================================================
#  Top-level VSS Constructs
# =============================================================================

@dataclass(frozen=True)
class VSSTheme:
    """Theme definition: theme Light: ... end."""
    name: str = ""
    variables: tuple[tuple[str, VSSValue], ...] = ()     # (name, value) pairs


@dataclass(frozen=True)
class VSSMixin:
    """Reusable style fragment: mixin rounded(radius): ... end."""
    name: str = ""
    params: tuple[tuple[str, VSSValue | None], ...] = ()  # (name, default)
    declarations: tuple[VSSDeclaration, ...] = ()


@dataclass(frozen=True)
class VSSKeyframes:
    """Keyframe animation: keyframes fade_in: 0%: ... end 100%: ... end end."""
    name: str = ""
    steps: tuple[tuple[str, tuple[VSSDeclaration, ...]], ...] = ()


@dataclass(frozen=True)
class VSSStyleBlock:
    """Named style block: style card: ... end."""
    name: str = ""
    declarations: tuple[VSSDeclaration, ...] = ()
    nested_rules: tuple[VSSNestedRule, ...] = ()
    mixins_applied: tuple[str, ...] = ()


# =============================================================================
#  VSS Stylesheet — Root AST Node
# =============================================================================

@dataclass(frozen=True)
class VSSStylesheet:
    """Root AST node for a parsed `.vss` file."""
    themes: tuple[VSSTheme, ...] = ()
    styles: tuple[VSSStyleBlock, ...] = ()
    mixins: tuple[VSSMixin, ...] = ()
    keyframes: tuple[VSSKeyframes, ...] = ()
    imports: tuple[str, ...] = ()
