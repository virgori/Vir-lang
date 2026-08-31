#!/usr/bin/env python3
"""Strip trailing statement semicolons from .vri sources (v2.0 style).

Only removes a semicolon at end-of-line (after optional whitespace).
Skips semicolons inside string literals. Does not touch mid-line separators.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SKIP = {
    ROOT / "virc_stage1.vri",
    ROOT / "vir-community",
    ROOT / "core",
    ROOT / "dist",
}


def ends_with_trailing_semicolon(line: str) -> bool:
    in_str = False
    quote = ""
    escape = False
    i = 0
    while i < len(line):
        c = line[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_str:
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
            i += 1
            continue
        i += 1

    stripped = line.rstrip()
    if not stripped.endswith(";"):
        return False
    # Semicolon must not be inside an unclosed string (bad source); ignore.
    return True


def strip_line(line: str) -> str:
    if not ends_with_trailing_semicolon(line):
        return line
    stripped = line.rstrip()
    assert stripped.endswith(";")
    suffix = line[len(stripped) :]
    return stripped[:-1] + suffix


def should_skip(path: Path, skip_roots: set[Path]) -> bool:
    try:
        path = path.resolve()
    except OSError:
        return True
    for root in skip_roots:
        try:
            path.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def process_file(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = 0
    out_lines: list[str] = []
    for line in lines:
        new_line = strip_line(line)
        if new_line != line:
            changed += 1
        out_lines.append(new_line)
    if changed and not dry_run:
        path.write_text("".join(out_lines), encoding="utf-8")
    return changed


def iter_vri_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".vri":
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(root.rglob("*.vri")))
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "paths",
        nargs="*",
        default=["stdlib/vir"],
        help="files or directories (default: stdlib/vir)",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only, do not write")
    ap.add_argument(
        "--include-stage1",
        action="store_true",
        help="also process virc_stage1.vri (normally skipped)",
    )
    args = ap.parse_args()

    skip_roots = set(DEFAULT_SKIP)
    if args.include_stage1:
        skip_roots.discard(ROOT / "virc_stage1.vri")

    roots = [(ROOT / p).resolve() if not Path(p).is_absolute() else Path(p) for p in args.paths]
    files = [p for p in iter_vri_files(roots) if not should_skip(p, skip_roots)]

    total_lines = 0
    touched_files = 0
    for path in files:
        n = process_file(path, args.dry_run)
        if n:
            touched_files += 1
            total_lines += n
            rel = path.relative_to(ROOT)
            print(f"{rel}: {n} line(s)")

    mode = "would change" if args.dry_run else "changed"
    print(f"\n{mode} {total_lines} line(s) in {touched_files} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
