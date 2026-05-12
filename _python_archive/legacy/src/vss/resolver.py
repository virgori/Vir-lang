"""
VSS Resolver — Theme variable resolution and mixin expansion.
================================================================
Transforms a parsed VSSStylesheet by:
  1. Resolving all VSSThemeRef values to concrete VSSLiteral values
  2. Expanding mixin applications into inline declarations
"""

from __future__ import annotations

from src.vss.ast import (
    VSSStylesheet, VSSStyleBlock, VSSTheme, VSSMixin,
    VSSDeclaration, VSSNestedRule, VSSKeyframes,
    VSSValue, VSSLiteral, VSSThemeRef, VSSFuncCall, VSSExpr, VSSValueList,
    VSSValueKind,
)


class VSSResolveError(Exception):
    """Raised when theme/mixin resolution fails."""


class VSSResolver:
    """Resolves themes and expands mixins in a VSSStylesheet."""

    def __init__(self, stylesheet: VSSStylesheet) -> None:
        self._sheet = stylesheet
        self._themes: dict[str, dict[str, VSSValue]] = {}
        self._mixins: dict[str, VSSMixin] = {}
        self._default_theme: str = ""

    def resolve(self) -> VSSStylesheet:
        """Resolve all theme refs and expand mixins. Returns new stylesheet."""
        # Index themes
        for theme in self._sheet.themes:
            self._themes[theme.name] = dict(theme.variables)
            if not self._default_theme:
                self._default_theme = theme.name

        # Index mixins
        for mixin in self._sheet.mixins:
            self._mixins[mixin.name] = mixin

        # Resolve style blocks
        resolved_styles = tuple(
            self._resolve_style(s) for s in self._sheet.styles
        )

        # Resolve keyframes
        resolved_keyframes = tuple(
            self._resolve_keyframes(kf) for kf in self._sheet.keyframes
        )

        return VSSStylesheet(
            themes=self._sheet.themes,
            styles=resolved_styles,
            mixins=self._sheet.mixins,
            keyframes=resolved_keyframes,
            imports=self._sheet.imports,
        )

    # ── Style block resolution ───────────────────────────────

    def _resolve_style(self, style: VSSStyleBlock) -> VSSStyleBlock:
        # Expand mixins first
        extra_decls: list[VSSDeclaration] = []
        for mixin_name in style.mixins_applied:
            mixin = self._mixins.get(mixin_name)
            if mixin is None:
                raise VSSResolveError(f"Unknown mixin: {mixin_name!r}")
            extra_decls.extend(mixin.declarations)

        # Resolve declarations
        all_decls = list(style.declarations) + extra_decls
        resolved_decls = tuple(self._resolve_decl(d) for d in all_decls)

        # Resolve nested rules
        resolved_nested = tuple(
            self._resolve_nested(n) for n in style.nested_rules
        )

        return VSSStyleBlock(
            name=style.name,
            declarations=resolved_decls,
            nested_rules=resolved_nested,
            mixins_applied=(),  # Already expanded
        )

    def _resolve_nested(self, rule: VSSNestedRule) -> VSSNestedRule:
        return VSSNestedRule(
            selector=rule.selector,
            condition=rule.condition,
            declarations=tuple(self._resolve_decl(d) for d in rule.declarations),
            nested_rules=tuple(self._resolve_nested(n) for n in rule.nested_rules),
        )

    def _resolve_decl(self, decl: VSSDeclaration) -> VSSDeclaration:
        if decl.value is None:
            return decl
        resolved_value = self._resolve_value(decl.value)
        return VSSDeclaration(
            property=decl.property,
            value=resolved_value,
            important=decl.important,
        )

    def _resolve_keyframes(self, kf: VSSKeyframes) -> VSSKeyframes:
        resolved_steps: list[tuple[str, tuple[VSSDeclaration, ...]]] = []
        for step_name, decls in kf.steps:
            resolved = tuple(self._resolve_decl(d) for d in decls)
            resolved_steps.append((step_name, resolved))
        return VSSKeyframes(name=kf.name, steps=tuple(resolved_steps))

    # ── Value resolution ─────────────────────────────────────

    def _resolve_value(self, value: VSSValue) -> VSSValue:
        if value.kind == VSSValueKind.THEME_REF:
            assert isinstance(value, VSSThemeRef)
            return self._resolve_theme_ref(value)

        if value.kind == VSSValueKind.FUNC_CALL:
            assert isinstance(value, VSSFuncCall)
            resolved_args = tuple(self._resolve_value(a) for a in value.args)
            return VSSFuncCall(func_name=value.func_name, args=resolved_args)

        if value.kind == VSSValueKind.EXPR:
            assert isinstance(value, VSSExpr)
            return VSSExpr(
                op=value.op,
                left=self._resolve_value(value.left) if value.left else None,
                right=self._resolve_value(value.right) if value.right else None,
            )

        if value.kind == VSSValueKind.LIST:
            assert isinstance(value, VSSValueList)
            return VSSValueList(
                items=tuple(self._resolve_value(v) for v in value.items)
            )

        return value  # VSSLiteral — no resolution needed

    def _resolve_theme_ref(self, ref: VSSThemeRef) -> VSSValue:
        theme_name = ref.theme_name or self._default_theme
        if not theme_name:
            raise VSSResolveError("No theme defined for theme reference")

        theme_vars = self._themes.get(theme_name)
        if theme_vars is None:
            # Try using theme_name as a variable in default theme
            if self._default_theme:
                theme_vars = self._themes.get(self._default_theme)
                if theme_vars and ref.theme_name and ref.theme_name in theme_vars:
                    raise VSSResolveError(f"Unknown theme: {theme_name!r}")
            if theme_vars is None:
                raise VSSResolveError(f"Unknown theme: {theme_name!r}")

        var_value = theme_vars.get(ref.var_name)
        if var_value is None:
            raise VSSResolveError(
                f"Unknown variable {ref.var_name!r} in theme {theme_name!r}"
            )

        # Recursively resolve (theme var may reference another theme var)
        return self._resolve_value(var_value)
