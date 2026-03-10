#!/usr/bin/env python3
"""
demo.py – Demo end-to-end: Multilingual source → Q-IR → Machine Code

Demonstrates Vir's lib/sublib architecture:
  lib  = English standard keywords (TokenKind)
  sublib = native language adapters (vi, zh, ja, ko, en)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.lib.keywords import TokenKind, KeywordRegistry
from src.sublib.base import SubLibRegistry

# Ensure all adapters are loaded
import src.sublib.vi   # noqa: F401
import src.sublib.zh   # noqa: F401
import src.sublib.ja   # noqa: F401
import src.sublib.ko   # noqa: F401
import src.sublib.en   # noqa: F401

from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer


def demo_lib():
    """Show lib keyword registry."""
    print("=" * 60)
    print("  lib/keywords.py – English Standard (Single Source of Truth)")
    print("=" * 60)
    reg = KeywordRegistry()
    for cat in sorted(reg.categories()):
        kws = [kw for kw in reg.all_keywords() if kw.category == cat]
        names = ", ".join(kw.english for kw in kws[:6])
        more = f" (+{len(kws)-6} more)" if len(kws) > 6 else ""
        print(f"  {cat:15s}: {names}{more}")
    print()


def demo_sublib():
    """Show sublib adapters and multilingual lookups."""
    print("=" * 60)
    print("  sublib/ – Native Language Adapters")
    print("=" * 60)
    for lang in SubLibRegistry.available():
        adapter = SubLibRegistry.get(lang)
        phrases = adapter.all_phrases()
        print(f"  [{lang}] {adapter.lang_name:10s}  {len(phrases):3d} phrases  "
              f"max_ngram={adapter.max_ngram}")
    print()

    # Cross-language lookup: "if" in all languages
    print("  Cross-language lookup for TokenKind.IF:")
    for lang in SubLibRegistry.available():
        adapter = SubLibRegistry.get(lang)
        matches = adapter.phrases_for_kind(TokenKind.IF)
        print(f"    [{lang}] {', '.join(repr(p) for p in matches)}")
    print()


def demo_tokenize():
    """Tokenize the same program in multiple languages."""
    programs = {
        "vi": "nếu máy rảnh tính tổng A B bằng thanh ghi",
        "zh": "如果 机器空闲 加 A B 寄存器",
        "ja": "もし CPU空き 足す A B レジスタ",
        "ko": "만약 CPU여유 더하기 A B 레지스터",
        "en": "if check_cpu add A B register",
    }

    print("=" * 60)
    print("  Multilingual Tokenization – Same Program, 5 Languages")
    print("=" * 60)

    for lang, source in programs.items():
        adapter = SubLibRegistry.get(lang)
        tokenizer = NGramTokenizer(adapter)
        tokens = tokenizer.tokenize(source)
        kinds = [t.kind.name for t in tokens if t.kind != TokenKind.EOF]
        print(f"\n  [{lang}] {source}")
        print(f"       → {kinds}")

    print()


def demo_runtime():
    """Original runtime demo (if runtime is available)."""
    try:
        from src.runtime.lifecycle.lifecycle import VirRuntime

        runtime = VirRuntime(enable_jit=False)

        source = "Nếu máy rảnh, tính tổng A và B bằng thanh ghi."
        print("=" * 60)
        print(f"  Runtime Compile: {source}")
        print("=" * 60)

        result = runtime.compile(source)
        print(f"\n  ⏱  Compiled in {result.compile_time_ms:.2f}ms")

        print("\n  ── Tokens ──")
        print(runtime.dump_tokens(result))

        print("\n  ── Q-IR ──")
        print(runtime.dump_ir(result))

        print("\n  ── Machine Code (Hex) ──")
        print(runtime.dump_variants(result))
    except (ImportError, AttributeError) as e:
        print(f"  (Runtime compile skipped – {type(e).__name__}: {e})")
        print("  Note: lifecycle.py needs migration to SubLibAdapter.")
    print()


def main():
    demo_lib()
    demo_sublib()
    demo_tokenize()
    demo_runtime()

    print("=" * 60)
    print("  ✓ Demo complete. Vir supports:")
    print(f"    {len(SubLibRegistry.available())} languages: "
          f"{', '.join(SubLibRegistry.available())}")
    print(f"    {len(KeywordRegistry().all_keywords())} keywords in lib")
    print("=" * 60)


if __name__ == "__main__":
    main()
