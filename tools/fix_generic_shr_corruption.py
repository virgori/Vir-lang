#!/usr/bin/env python3
"""Fix replace_vri_shift_ops.py damage: generic `>>` closers turned into `TYPE shr (`.

Only rewrites `shr (` to `>>(` when the lhs looks like a generic type argument
(token immediately after `<` or `,` inside a type list).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "stdlib" / "vir"

# `, B shr (` or `<T shr (` — not `x shr (` (shift)
FIX_RE = re.compile(
    r"([,<])\s*([A-Za-z_][A-Za-z0-9_]*)\s+shr\s+\(",
)


def fix_line(line: str) -> str:
    if line.lstrip().startswith("#"):
        return line
    return FIX_RE.sub(r"\1\2>>(", line)


def main() -> int:
    changed_files = 0
    changed_lines = 0
    for path in sorted(TARGET.rglob("*.vri")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        n = 0
        for line in lines:
            fixed = fix_line(line)
            if fixed != line:
                n += 1
            out.append(fixed)
        if n:
            path.write_text("".join(out), encoding="utf-8")
            print(f"fixed {path}: {n} lines")
            changed_files += 1
            changed_lines += n
    # compiler/vec.vri mirrors collections/vec.vri but lives outside TARGET rglob?
    # It's under stdlib/vir/compiler/vec.vri — included in rglob.
    extra = [
        ROOT / "stdlib" / "vir" / "compiler" / "vec.vri",
        ROOT / "stdlib" / "vir" / "collections" / "vec.vri",
    ]
    print(f"\nDone: {changed_files} files, {changed_lines} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
