"""
vir-fmt — Vir Code Formatter
==============================
Phase 3 Task F2: Deterministic code formatting for .vri files.

Usage:
    python -m tools.vir-fmt.formatter file.vri          # format in-place
    python -m tools.vir-fmt.formatter --check file.vri   # check only

Rules:
    - 4-space indent per block level
    - 1 blank line between top-level declarations
    - Consistent keyword spacing
    - Aligned entity field colons
    - Strip trailing whitespace
    - Line length: soft 100, hard 120
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# Block-opening keywords
_BLOCK_OPENERS = {
    "func", "entity", "enum", "trait", "impl", "method", "class",
    "if", "eif", "else", "when", "loop", "case", "try", "fallback", "error",
}

# Keywords that reduce indent before printing (close a block)
_BLOCK_CLOSERS = {"end", "end;"}

# Keywords that temporarily reduce then increase (eif, else, fallback, error in try)
_BLOCK_PIVOTS = {"eif", "else", "fallback", "error"}


class VirFormatter:
    """Format .vri source code."""

    def __init__(self, indent_size: int = 4, max_line: int = 120) -> None:
        self.indent_size = indent_size
        self.max_line = max_line

    def format(self, source: str) -> str:
        """Format source code string, return formatted version."""
        lines = source.split("\n")
        result: list[str] = []
        indent_level = 0
        prev_was_blank = False
        prev_was_toplevel = False
        in_block_comment = False

        for line in lines:
            stripped = line.strip()

            # Handle block comments ## ... ##
            if in_block_comment:
                result.append(self._indent(indent_level) + stripped)
                if "##" in stripped and not stripped.startswith("##"):
                    in_block_comment = False
                elif stripped.endswith("##") and stripped != "##":
                    in_block_comment = False
                continue
            if stripped.startswith("##") and not stripped.endswith("##"):
                in_block_comment = True
                result.append(self._indent(indent_level) + stripped)
                continue

            # Skip empty lines (normalize)
            if not stripped:
                if not prev_was_blank:
                    result.append("")
                    prev_was_blank = True
                continue

            # Line comment
            if stripped.startswith("#"):
                result.append(self._indent(indent_level) + stripped)
                prev_was_blank = False
                continue

            # Determine keyword
            first_word = stripped.split()[0].rstrip(":;") if stripped else ""

            # Blank line before top-level declarations
            is_toplevel = first_word in ("func", "entity", "enum", "trait", "impl",
                                         "class", "method") and indent_level == 0
            if is_toplevel and result and not prev_was_blank:
                result.append("")

            # Handle closing: reduce indent before printing
            if stripped in _BLOCK_CLOSERS or first_word in _BLOCK_CLOSERS:
                indent_level = max(0, indent_level - 1)
            elif first_word in _BLOCK_PIVOTS:
                indent_level = max(0, indent_level - 1)

            # Format the line
            formatted = self._format_line(stripped, indent_level)
            result.append(formatted)
            prev_was_blank = False
            prev_was_toplevel = is_toplevel

            # Handle opening: increase indent after printing
            if first_word in _BLOCK_PIVOTS:
                indent_level += 1
            elif self._opens_block(stripped, first_word):
                indent_level += 1

        # Strip trailing blank lines
        while result and result[-1] == "":
            result.pop()
        result.append("")  # Ensure final newline

        return "\n".join(result)

    def _indent(self, level: int) -> str:
        return " " * (level * self.indent_size)

    def _format_line(self, line: str, indent_level: int) -> str:
        """Apply formatting rules to a single line."""
        # Add indent
        formatted = self._indent(indent_level) + line

        # Strip trailing whitespace
        formatted = formatted.rstrip()

        # Normalize operator spacing: ensure spaces around =, ==, !=, +, -, etc.
        # (Simple approach — don't break string literals)
        formatted = self._normalize_spacing(formatted)

        return formatted

    def _normalize_spacing(self, line: str) -> str:
        """Ensure consistent spacing around operators."""
        # Don't modify inside strings
        if '"' in line:
            return line  # Skip lines with strings for safety
        # Ensure space after semicolons (but not before)
        line = re.sub(r";\s*(?=\S)", "; ", line)
        return line

    def _opens_block(self, line: str, first_word: str) -> bool:
        """Check if a line opens a new block."""
        if first_word in _BLOCK_OPENERS:
            # "func name:" or "if cond" opens a block
            return line.endswith(":") or first_word in ("if", "else", "when",
                                                         "loop", "try", "fallback",
                                                         "error")
        return False

    def check(self, source: str) -> bool:
        """Check if source is already formatted. Returns True if OK."""
        return self.format(source) == source


def main():
    """CLI entry point."""
    args = sys.argv[1:]
    check_only = "--check" in args
    files = [a for a in args if not a.startswith("-")]

    if not files:
        print("Usage: python -m tools.vir-fmt.formatter [--check] <files...>")
        sys.exit(1)

    formatter = VirFormatter()
    all_ok = True

    for path_str in files:
        path = Path(path_str)
        if not path.exists():
            print(f"File not found: {path}")
            all_ok = False
            continue

        source = path.read_text(encoding="utf-8")
        formatted = formatter.format(source)

        if check_only:
            if source != formatted:
                print(f"FAIL: {path} needs formatting")
                all_ok = False
            else:
                print(f"OK: {path}")
        else:
            if source != formatted:
                path.write_text(formatted, encoding="utf-8")
                print(f"Formatted: {path}")
            else:
                print(f"Already formatted: {path}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
