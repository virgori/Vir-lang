"""
VSS CSS Emitter — Compiles resolved VSSStylesheet to CSS text.
================================================================
Final stage of the VSS pipeline: VSSA → CSS string.

Handles:
  - Property normalization (underscore → hyphen)
  - Scoped class names (via VSSScoper mapping)
  - Nested rule flattening (&:hover → .card_a7f2:hover)
  - `when` condition → @media query translation
  - Keyframes emission
  - Value serialization (literals, function calls, value lists)
"""

from __future__ import annotations

from src.vss.ast import (
    VSSStylesheet, VSSStyleBlock, VSSKeyframes,
    VSSDeclaration, VSSNestedRule, VSSCondition,
    VSSValue, VSSLiteral, VSSFuncCall, VSSValueList,
    VSSValueKind,
)
from src.vss.sublib import normalize_property, SHORTHAND_TRANSFORMS, DISPLAY_ALIASES


class VSSCSSEmitter:
    """Emits optimized CSS from a resolved VSSStylesheet."""

    def __init__(self, scope_map: dict[str, str] | None = None) -> None:
        self._scope = scope_map or {}

    def emit(self, stylesheet: VSSStylesheet) -> str:
        """Emit full CSS string from stylesheet."""
        parts: list[str] = []

        # Keyframes first
        for kf in stylesheet.keyframes:
            parts.append(self._emit_keyframes(kf))

        # Style blocks
        for style in stylesheet.styles:
            parts.append(self._emit_style(style))

        return "\n".join(p for p in parts if p)

    # ── Style block ──────────────────────────────────────────

    def _emit_style(self, style: VSSStyleBlock) -> str:
        class_name = self._scope.get(style.name, style.name)
        selector = f".{class_name}"
        parts: list[str] = []

        # Main declarations
        decls = self._emit_declarations(style.declarations)
        if decls:
            parts.append(f"{selector} {{\n{decls}\n}}")

        # Nested rules
        for rule in style.nested_rules:
            parts.append(self._emit_nested_rule(selector, rule))

        return "\n".join(p for p in parts if p)

    def _emit_nested_rule(self, parent_selector: str, rule: VSSNestedRule) -> str:
        parts: list[str] = []

        if rule.condition is not None:
            # `when` block → @media query
            media_query = self._condition_to_media(rule.condition)
            decls = self._emit_declarations(rule.declarations)
            if decls:
                parts.append(f"@media ({media_query}) {{\n  {parent_selector} {{\n{self._indent(decls, 4)}\n  }}\n}}")
        elif rule.selector.startswith("&"):
            # Pseudo-class/element: &:hover → .card_a7f2:hover
            pseudo = rule.selector[1:]  # strip "&"
            full_selector = f"{parent_selector}{pseudo}"
            decls = self._emit_declarations(rule.declarations)
            if decls:
                parts.append(f"{full_selector} {{\n{decls}\n}}")
            # Recurse into deeper nesting
            for nested in rule.nested_rules:
                parts.append(self._emit_nested_rule(full_selector, nested))
        elif rule.selector.startswith(">"):
            # Child combinator
            child = rule.selector.lstrip("> ")
            full_selector = f"{parent_selector} > .{self._scope.get(child, child)}"
            decls = self._emit_declarations(rule.declarations)
            if decls:
                parts.append(f"{full_selector} {{\n{decls}\n}}")
        else:
            # Generic nested
            full_selector = f"{parent_selector} {rule.selector}"
            decls = self._emit_declarations(rule.declarations)
            if decls:
                parts.append(f"{full_selector} {{\n{decls}\n}}")

        return "\n".join(p for p in parts if p)

    # ── Declarations ─────────────────────────────────────────

    def _emit_declarations(self, declarations: tuple[VSSDeclaration, ...]) -> str:
        lines: list[str] = []
        for decl in declarations:
            css_prop = normalize_property(decl.property)
            css_value = self._emit_value(decl.value) if decl.value else ""

            # Handle shorthand transforms (scale, rotate, translate)
            template = SHORTHAND_TRANSFORMS.get(decl.property)
            if template:
                css_prop = "transform"
                css_value = template.format(value=css_value)

            # Handle display aliases
            if decl.property in ("display", "bố_cục", "hiển_thị"):
                alias = DISPLAY_ALIASES.get(css_value)
                if alias and ";" in alias:
                    # Multi-property expansion: "flex; flex-direction: row"
                    for sub in alias.split(";"):
                        sub = sub.strip()
                        if ":" in sub:
                            sp, sv = sub.split(":", 1)
                            lines.append(f"  {sp.strip()}: {sv.strip()};")
                        else:
                            lines.append(f"  display: {sub};")
                    continue
                elif alias:
                    css_value = alias

            important = " !important" if decl.important else ""
            lines.append(f"  {css_prop}: {css_value}{important};")

        return "\n".join(lines)

    # ── Value serialization ──────────────────────────────────

    def _emit_value(self, value: VSSValue | None) -> str:
        if value is None:
            return ""

        if value.kind == VSSValueKind.LITERAL:
            assert isinstance(value, VSSLiteral)
            return value.raw

        if value.kind == VSSValueKind.FUNC_CALL:
            assert isinstance(value, VSSFuncCall)
            args = ", ".join(self._emit_value(a) for a in value.args)
            return f"{value.func_name}({args})"

        if value.kind == VSSValueKind.LIST:
            assert isinstance(value, VSSValueList)
            return " ".join(self._emit_value(v) for v in value.items)

        # ThemeRef should have been resolved before emission
        return str(value)

    # ── Keyframes ────────────────────────────────────────────

    def _emit_keyframes(self, kf: VSSKeyframes) -> str:
        name = self._scope.get(kf.name, kf.name)
        lines = [f"@keyframes {name} {{"]
        for step_name, decls in kf.steps:
            decl_text = self._emit_declarations(decls)
            lines.append(f"  {step_name} {{")
            lines.append(self._indent(decl_text, 4))
            lines.append("  }")
        lines.append("}")
        return "\n".join(lines)

    # ── Media query ──────────────────────────────────────────

    def _condition_to_media(self, condition: VSSCondition) -> str:
        """Convert VSS condition to CSS media query."""
        prop = condition.property
        value = self._emit_value(condition.value) if condition.value else ""

        # Map common conditions
        prop_map = {
            "width": "width",
            "chiều_rộng": "width",
            "rộng": "width",
            "height": "height",
            "chiều_cao": "height",
            "cao": "height",
        }
        css_prop = prop_map.get(prop, prop)

        op = condition.operator
        if op == ">":
            return f"min-{css_prop}: {value}"
        if op == "<":
            return f"max-{css_prop}: {value}"
        if op == ">=":
            return f"min-{css_prop}: {value}"
        if op == "<=":
            return f"max-{css_prop}: {value}"
        if op == "==":
            return f"{css_prop}: {value}"

        return f"{css_prop}: {value}"

    # ── Util ─────────────────────────────────────────────────

    @staticmethod
    def _indent(text: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line if line.strip() else line for line in text.split("\n"))
