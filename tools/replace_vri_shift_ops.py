#!/usr/bin/env python3
"""Replace v1.2 shift tokens with v2.0 keywords in .vri sources.

  <<  -> shl   (spec §10.4 — not a lexer token in expressions)
  >>  -> shr   only when used as binary shift, NOT type cast closing `>>`

Skips comments and string literals. Does not process virc_stage1 by default.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_ROOTS = {
    ROOT / "virc_stage1.vri",
    ROOT / "vir-community",
    ROOT / "core",
    ROOT / "dist",
}

# << not part of <<< ; >> not part of >>> and not >>= 
SHL_RE = re.compile(r"(?<!<)<<(?!>)")
# Shift-right: `x >> n` where rhs looks numeric/paren — not `Type>>` generic close.
SHR_RE = re.compile(
    r">>(?=\s*[\d(])"
)


def transform_line(line: str) -> str:
    if line.lstrip().startswith("#"):
        return line
    return _transform_code(line)


def _transform_code(line: str) -> str:
    out: list[str] = []
    i = 0
    in_str = False
    quote = ""
    escape = False
    while i < len(line):
        c = line[i]
        if escape:
            out.append(c)
            escape = False
            i += 1
            continue
        if in_str:
            out.append(c)
            if c == "\\":
                escape = True
            elif c == quote:
                in_str = False
                quote = ""
            i += 1
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
            out.append(c)
            i += 1
            continue
        rest = line[i:]
        m = SHL_RE.match(rest)
        if m:
            out.append(" shl ")
            i += m.end()
            continue
        m = SHR_RE.match(rest)
        if m:
            out.append(" shr ")
            i += m.end()
            continue
        out.append(c)
        i += 1
    return "".join(out)


def should_skip(path: Path) -> bool:
    path = path.resolve()
    for root in SKIP_ROOTS:
        try:
            path.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    if path.suffix != ".vri":
        return True
    if ".bak" in path.name or path.name.endswith(".new"):
        return True
    return False


def process_file(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = 0
    new_lines: list[str] = []
    for line in lines:
        nl = transform_line(line)
        if nl != line:
            changed += 1
        new_lines.append(nl)
    if changed and not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", default=["stdlib/vir"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    roots = [(ROOT / p).resolve() if not Path(p).is_absolute() else Path(p) for p in args.paths]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        else:
            files.extend(sorted(root.rglob("*.vri")))

    total = 0
    touched = 0
    for path in files:
        if should_skip(path):
            continue
        n = process_file(path, args.dry_run)
        if n:
            touched += 1
            total += n
            print(f"{path.relative_to(ROOT)}: {n} line(s)")

    verb = "would change" if args.dry_run else "changed"
    print(f"\n{verb} {total} line(s) in {touched} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
