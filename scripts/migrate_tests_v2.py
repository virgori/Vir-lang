#!/usr/bin/env python3
"""
migrate_tests_v2.py — Migrate .vri test files to Vir v2.0 syntax.

Changes:
  - func name(): with empty params → func name: (only when () is empty)
  - Definition block closing `end` → `end.`
  - Does NOT convert func name(a, b): — inline params are valid v2.0 (§6, §14.1)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEF_START = re.compile(
    r"^(\s*)(func|entity|enum|register|mold|packed entity)\s+([A-Za-z_][A-Za-z0-9_.]*)\s*(\([^)]*\))?\s*:\s*$"
)
DEF_START_PARENS = re.compile(
    r"^(\s*)(func|entity|enum|register|mold|packed entity)\s+([A-Za-z_][A-Za-z0-9_.]*)\s*\(\s*\)\s*:\s*$"
)
CONTROL_OPEN = re.compile(
    r"^(\s*)(if|eif|when|for|loop|while|try|arena|select|morph|infer|train|quantize)\b"
)
CONTROL_DO = re.compile(r"^(\s*)(if|eif|when)\b.+\bdo\s*$")
END_LINE = re.compile(r"^(\s*)end\s*\.?\s*$")
END_DOT_LINE = re.compile(r"^(\s*)end\.\s*$")


def migrate_source(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    def_depth = 0
    ctrl_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        m_empty = DEF_START_PARENS.match(line)
        if m_empty:
            indent, kind, name = m_empty.groups()
            out.append(f"{indent}{kind} {name}:")
            def_depth += 1
            i += 1
            continue

        m = DEF_START.match(line)
        if m:
            indent, kind, name, _params = m.groups()
            out.append(f"{indent}{kind} {name}:")
            def_depth += 1
            i += 1
            continue

        if CONTROL_OPEN.match(line) or CONTROL_DO.match(line):
            if stripped.endswith(":") or stripped.endswith("do"):
                ctrl_depth += 1

        em = END_LINE.match(line)
        if em:
            indent = em.group(1)
            if ctrl_depth > 0:
                out.append(f"{indent}end")
                ctrl_depth -= 1
            elif def_depth > 0:
                out.append(f"{indent}end.")
                def_depth -= 1
            else:
                out.append(f"{indent}end.")
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def migrate_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    migrated = migrate_source(original)
    if migrated != original:
        path.write_text(migrated, encoding="utf-8")
        return True
    return False


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    changed = 0
    for pattern in ("tests/**/*.vri", "hello.vri", "demo_*.vri"):
        for path in root.glob(pattern):
            if migrate_file(path):
                changed += 1
                print(f"migrated: {path.relative_to(root)}")
    print(f"done: {changed} files updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
