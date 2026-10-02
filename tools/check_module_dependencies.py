#!/usr/bin/env python3
"""
tools/check_module_dependencies.py — Enforce single dependency declaration per module.

VIRC-ISS-0007 / VIRC-PLN-0005:
Verifies that no canonical compiler source file under `compiler/src/**/*.vri` declares
both `include M` and `import ... from M` for the same module M.

Usage:
    python3 tools/check_module_dependencies.py [--verbose] [--fix]
"""

from __future__ import annotations
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILER_SRC = ROOT / "compiler/src"

def extract_dependencies(file_path: Path) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """
    Returns (includes, imports) mapping module_name -> list of line numbers.
    """
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    includes: dict[str, list[int]] = {}
    imports: dict[str, list[int]] = {}

    in_block_comment = False
    for line_num, raw_line in enumerate(lines, start=1):
        s = raw_line.strip()
        if in_block_comment:
            if "##" in s:
                in_block_comment = False
            continue
        if s.startswith("##"):
            in_block_comment = True
            continue
        if s.startswith("#"):
            continue

        # Match include <mod>
        m_inc = re.match(r"^include\s+([A-Za-z0-9_./\"\-]+)", s)
        if m_inc:
            mod = m_inc.group(1).strip("\"'")
            includes.setdefault(mod, []).append(line_num)
            continue

        # Match import ... from <mod>
        m_imp = re.search(r"\bfrom\s+([A-Za-z0-9_./\"\-]+)\s*$", s)
        if m_imp:
            mod = m_imp.group(1).strip("\"'")
            imports.setdefault(mod, []).append(line_num)
            continue

    return includes, imports

def check_file(file_path: Path) -> list[str]:
    violations = []
    includes, imports = extract_dependencies(file_path)
    rel = file_path.relative_to(ROOT).as_posix()

    overlap = set(includes.keys()) & set(imports.keys())
    for mod in sorted(overlap):
        inc_lines = ",".join(str(l) for l in includes[mod])
        imp_lines = ",".join(str(l) for l in imports[mod])
        violations.append(
            f"{rel}: Redundant dependency on '{mod}' (include line {inc_lines}, import line {imp_lines})"
        )
    return violations

def check_all(verbose: bool = False) -> tuple[int, list[str]]:
    all_violations = []
    file_count = 0

    for file_path in sorted(COMPILER_SRC.rglob("*.vri")):
        if not file_path.is_file():
            continue
        file_count += 1
        violations = check_file(file_path)
        all_violations.extend(violations)
        if verbose and violations:
            for v in violations:
                print(f"  • {v}")

    return file_count, all_violations

def remove_redundant_includes(file_path: Path) -> int:
    """
    Removes `include M` lines when `import ... from M` exists in the same file.
    Returns the count of removed lines.
    """
    includes, imports = extract_dependencies(file_path)
    overlap = set(includes.keys()) & set(imports.keys())
    if not overlap:
        return 0

    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines = []
    removed_count = 0

    for line in lines:
        s = line.strip()
        m_inc = re.match(r"^include\s+([A-Za-z0-9_./\"\-]+)\s*$", s)
        if m_inc:
            mod = m_inc.group(1).strip("\"'")
            if mod in overlap:
                removed_count += 1
                continue
        new_lines.append(line)

    if removed_count > 0:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return removed_count

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true", help="Print all violations")
    parser.add_argument("--fix", action="store_true", help="Automatically remove redundant include statements")
    args = parser.parse_args()

    if args.fix:
        total_removed = 0
        fixed_files = 0
        for file_path in sorted(COMPILER_SRC.rglob("*.vri")):
            if not file_path.is_file():
                continue
            removed = remove_redundant_includes(file_path)
            if removed > 0:
                total_removed += removed
                fixed_files += 1
        print(f"Fix completed: removed {total_removed} redundant include statement(s) across {fixed_files} file(s).")

    file_count, violations = check_all(verbose=args.verbose)

    if violations:
        print(f"FAIL: {len(violations)} redundant include/import violation(s) found across {file_count} compiler source files.")
        if not args.verbose:
            print("Run with --verbose to view all violations, or --fix to remove redundant includes.")
        return 1

    print(f"PASS: All {file_count} compiler source files have disciplined, non-redundant dependencies.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
