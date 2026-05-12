"""
Test suite for the VSS pipeline: tokenizer → parser → resolver → scoper → CSS emitter.
"""

import pytest

from src.vss.tokenizer import VSSTokenizer, VSSTokenKind
from src.vss.parser import VSSParser
from src.vss.resolver import VSSResolver, VSSResolveError
from src.vss.scoper import VSSScoper
from src.vss.emitter_css import VSSCSSEmitter
from src.vss.ast import VSSLiteral, VSSThemeRef, VSSValueKind


# =============================================================================
#  Tokenizer tests
# =============================================================================

class TestVSSTokenizer:
    def test_basic_tokens(self):
        src = 'theme "dark" { primary: #0066ff }'
        tokens = VSSTokenizer(src).tokenize()
        kinds = [t.kind for t in tokens]
        assert VSSTokenKind.THEME in kinds
        assert VSSTokenKind.STRING in kinds
        assert VSSTokenKind.LBRACE in kinds
        assert VSSTokenKind.COLOR in kinds
        assert VSSTokenKind.RBRACE in kinds

    def test_style_block(self):
        src = 'style "card" { padding: 16px }'
        tokens = VSSTokenizer(src).tokenize()
        kinds = [t.kind for t in tokens]
        assert VSSTokenKind.STYLE in kinds
        assert VSSTokenKind.UNIT_VALUE in kinds

    def test_color_hex(self):
        src = "color: #ff0033"
        tokens = VSSTokenizer(src).tokenize()
        colors = [t for t in tokens if t.kind == VSSTokenKind.COLOR]
        assert len(colors) == 1
        assert colors[0].value == "#ff0033"

    def test_number(self):
        src = "opacity: 0.5"
        tokens = VSSTokenizer(src).tokenize()
        nums = [t for t in tokens if t.kind == VSSTokenKind.NUMBER]
        assert len(nums) == 1
        assert nums[0].value == "0.5"

    def test_unit_values(self):
        src = "width: 100px margin: 2rem"
        tokens = VSSTokenizer(src).tokenize()
        units = [t for t in tokens if t.kind == VSSTokenKind.UNIT_VALUE]
        assert len(units) == 2

    def test_comments_stripped(self):
        src = """
        // this is a comment
        style "x" { color: red }
        /* block comment */
        """
        tokens = VSSTokenizer(src).tokenize()
        # No comment tokens should appear
        values = [t.value for t in tokens]
        assert "// this is a comment" not in values
        assert "/* block comment */" not in values

    def test_ampersand_token(self):
        src = "&:hover { color: blue }"
        tokens = VSSTokenizer(src).tokenize()
        assert any(t.kind == VSSTokenKind.AMPERSAND for t in tokens)

    def test_multilingual_keywords(self):
        vi_kw = {"chủ_đề": VSSTokenKind.THEME, "phong_cách": VSSTokenKind.STYLE}
        src = 'chủ_đề "dark" { }'
        tokens = VSSTokenizer(src, keyword_map=vi_kw).tokenize()
        assert tokens[0].kind == VSSTokenKind.THEME


# =============================================================================
#  Parser tests
# =============================================================================

class TestVSSParser:
    def test_parse_theme(self):
        src = 'theme "light" { primary: #0066ff secondary: #333333 }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.themes) == 1
        assert sheet.themes[0].name == "light"
        assert "primary" in dict(sheet.themes[0].variables)

    def test_parse_style(self):
        src = 'style "card" { padding: 16px border_radius: 8px }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.styles) == 1
        assert sheet.styles[0].name == "card"
        assert len(sheet.styles[0].declarations) == 2

    def test_parse_nested_rule(self):
        src = '''
        style "btn" {
            color: red
            &:hover {
                color: blue
            }
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.styles) == 1
        assert len(sheet.styles[0].nested_rules) == 1
        assert sheet.styles[0].nested_rules[0].selector == "&:hover"

    def test_parse_theme_ref(self):
        src = 'theme "main" { primary: #ff0000 } style "x" { color: theme.primary }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.styles) == 1
        decl = sheet.styles[0].declarations[0]
        assert decl.value.kind == VSSValueKind.THEME_REF

    def test_parse_mixin(self):
        src = 'mixin "flex_center" { display: flex align_items: center }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.mixins) == 1
        assert sheet.mixins[0].name == "flex_center"

    def test_parse_keyframes(self):
        src = '''
        keyframes "fade_in" {
            from { opacity: 0 }
            to { opacity: 1 }
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        assert len(sheet.keyframes) == 1
        assert sheet.keyframes[0].name == "fade_in"
        assert len(sheet.keyframes[0].steps) == 2


# =============================================================================
#  Resolver tests
# =============================================================================

class TestVSSResolver:
    def test_resolve_theme_ref(self):
        src = 'theme "main" { primary: #0066ff } style "x" { color: theme.primary }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        decl = resolved.styles[0].declarations[0]
        assert isinstance(decl.value, VSSLiteral)
        assert decl.value.raw == "#0066ff"

    def test_resolve_unknown_theme_var(self):
        src = 'theme "main" { primary: #0066ff } style "x" { color: theme.nonexistent }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        with pytest.raises(VSSResolveError, match="nonexistent"):
            VSSResolver(sheet).resolve()

    def test_mixin_expansion(self):
        src = '''
        mixin "shadow" { box_shadow: 0 2px 4px rgba(0,0,0,0.2) }
        style "card" {
            apply "shadow"
            padding: 16px
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        card = resolved.styles[0]
        props = [d.property for d in card.declarations]
        assert "padding" in props
        assert "box_shadow" in props


# =============================================================================
#  Scoper tests
# =============================================================================

class TestVSSScoper:
    def test_deterministic_hash(self):
        src = 'style "card" { padding: 16px }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        scoper = VSSScoper(scope_prefix="App")
        scope_map = scoper.scope_stylesheet(sheet)
        assert "card" in scope_map
        scoped = scope_map["card"]
        assert scoped.startswith("card_")
        assert len(scoped) == len("card_") + 4  # 4 hex chars

    def test_deterministic_same_input(self):
        """Same prefix + name → same hash."""
        scoper1 = VSSScoper(scope_prefix="X")
        scoper2 = VSSScoper(scope_prefix="X")
        src = 'style "btn" { color: red }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        map1 = scoper1.scope_stylesheet(sheet)
        map2 = scoper2.scope_stylesheet(sheet)
        assert map1["btn"] == map2["btn"]

    def test_different_prefix_different_hash(self):
        src = 'style "btn" { color: red }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        map1 = VSSScoper(scope_prefix="A").scope_stylesheet(sheet)
        map2 = VSSScoper(scope_prefix="B").scope_stylesheet(sheet)
        assert map1["btn"] != map2["btn"]


# =============================================================================
#  CSS Emitter tests
# =============================================================================

class TestVSSCSSEmitter:
    def test_basic_emission(self):
        src = 'style "card" { padding: 16px color: red }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        css = VSSCSSEmitter().emit(resolved)
        assert ".card" in css
        assert "padding: 16px" in css
        assert "color: red" in css

    def test_scoped_emission(self):
        src = 'style "card" { padding: 16px }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        scope_map = VSSScoper(scope_prefix="App").scope_stylesheet(resolved)
        css = VSSCSSEmitter(scope_map=scope_map).emit(resolved)
        scoped_name = scope_map["card"]
        assert f".{scoped_name}" in css

    def test_nested_pseudo(self):
        src = '''
        style "btn" {
            color: red
            &:hover {
                color: blue
            }
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        css = VSSCSSEmitter().emit(resolved)
        assert ".btn:hover" in css
        assert "color: blue" in css

    def test_property_normalization(self):
        src = 'style "x" { border_radius: 8px }'
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        css = VSSCSSEmitter().emit(resolved)
        assert "border-radius: 8px" in css

    def test_keyframes_emission(self):
        src = '''
        keyframes "fade" {
            from { opacity: 0 }
            to { opacity: 1 }
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        css = VSSCSSEmitter().emit(resolved)
        assert "@keyframes fade" in css
        assert "opacity: 0" in css
        assert "opacity: 1" in css

    def test_full_pipeline(self):
        """End-to-end: theme + style + nested + scoped → CSS."""
        src = '''
        theme "app" {
            bg: #ffffff
            text: #333333
        }
        style "page" {
            background: theme.bg
            color: theme.text
            &:hover {
                opacity: 0.8
            }
        }
        '''
        tokens = VSSTokenizer(src).tokenize()
        sheet = VSSParser(tokens).parse()
        resolved = VSSResolver(sheet).resolve()
        scope_map = VSSScoper(scope_prefix="App").scope_stylesheet(resolved)
        css = VSSCSSEmitter(scope_map=scope_map).emit(resolved)
        scoped = scope_map["page"]
        assert f".{scoped}" in css
        assert "#ffffff" in css
        assert "#333333" in css
        assert "opacity: 0.8" in css
