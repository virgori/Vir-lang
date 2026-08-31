#!/usr/bin/env python3
"""Replace v1.2 bitwise XOR `^` with v2.0 keyword `xor` in .vri sources.

Spec v2.0: `^` is exponentiation only; bitwise XOR is `xor`.

Skips comments, string literals, and block doc comments (##).
Does not touch `^=` (xor-assign token) or semver strings like "^1.2.0".
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
    ROOT / "stdlib_backup_pre_spec12",
}

DEFAULT_DIRS = (
    ROOT / "stdlib" / "vir",
    ROOT / "tests",
)


def transform_line(line: str) -> str:
    return _transform_code(line)


def _transform_code(line: str) -> str:
    out: list[str] = []
    i = 0
    in_str = False
    quote = ""
    escape = False
    in_line_comment = False

    while i < len(line):
        c = line[i]

        if in_line_comment:
            out.append(c)
            i += 1
            continue

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

        if c == "#":
            in_line_comment = True
            out.append(c)
            i += 1
            continue

        if c in ('"', "'"):
            in_str = True
            quote = c
            out.append(c)
            i += 1
            continue

        if c == "^":
            if i + 1 < len(line) and line[i + 1] == "=":
                out.append("^=")
                i += 2
                continue
            out.append(" xor ")
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def transform_file(path: Path) -> tuple[bool, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = 0
    new_lines: list[str] = []
    in_block_doc = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("##"):
            in_block_doc = not in_block_doc
            new_lines.append(line)
            continue
        if in_block_doc:
            new_lines.append(line)
            continue

        new_line = transform_line(line)
        if new_line != line:
            changed += 1
        new_lines.append(new_line)

    if changed:
        path.write_text("".join(new_lines), encoding="utf-8")
    return changed > 0, changed


def should_skip(path: Path) -> bool:
    for root in SKIP_ROOTS:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def iter_vri_files(dirs: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.vri")):
            if should_skip(p):
                continue
            files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("paths", nargs="*", type=Path)
    args = ap.parse_args()

    if args.paths:
        files = [p.resolve() for p in args.paths if p.suffix == ".vri" and not should_skip(p.resolve())]
    else:
        files = iter_vri_files(DEFAULT_DIRS)

    total_files = 0
    total_lines = 0
    for path in files:
        if args.dry_run:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            in_block_doc = False
            n = 0
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("##"):
                    in_block_doc = not in_block_doc
                    continue
                if in_block_doc:
                    continue
                if transform_line(line) != line:
                    n += 1
            if n:
                print(f"would change {path}: {n} lines")
                total_files += 1
                total_lines += n
        else:
            touched, n = transform_file(path)
            if touched:
                print(f"updated {path}: {n} lines")
                total_files += 1
                total_lines += n

    label = "would update" if args.dry_run else "updated"
    print(f"\n{label} {total_files} files ({total_lines} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
