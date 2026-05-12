"""
VSS — Vir Style Sheets Compiler
=================================
Compiled, scoped, multilingual CSS alternative for Vir web targets.

Pipeline: .vss source → tokenize → parse (VSSA) → resolve → scope → emit CSS
"""

from src.vss.ast import (
    VSSStylesheet, VSSStyleBlock, VSSTheme, VSSMixin, VSSKeyframes,
    VSSDeclaration, VSSNestedRule, VSSCondition,
    VSSValue, VSSLiteral, VSSThemeRef, VSSFuncCall, VSSExpr, VSSValueList,
    VSSValueKind,
)
from src.vss.tokenizer import VSSTokenizer, VSSToken, VSSTokenKind
from src.vss.parser import VSSParser
from src.vss.resolver import VSSResolver, VSSResolveError
from src.vss.scoper import VSSScoper
from src.vss.emitter_css import VSSCSSEmitter

__all__ = [
    # AST
    "VSSStylesheet", "VSSStyleBlock", "VSSTheme", "VSSMixin", "VSSKeyframes",
    "VSSDeclaration", "VSSNestedRule", "VSSCondition",
    "VSSValue", "VSSLiteral", "VSSThemeRef", "VSSFuncCall", "VSSExpr",
    "VSSValueList", "VSSValueKind",
    # Pipeline
    "VSSTokenizer", "VSSToken", "VSSTokenKind",
    "VSSParser",
    "VSSResolver", "VSSResolveError",
    "VSSScoper",
    "VSSCSSEmitter",
]
