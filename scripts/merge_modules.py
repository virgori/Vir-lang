#!/usr/bin/env python3
"""
merge_modules.py — Vir Module Merger (Preprocessor)
====================================================
Resolves all `include` directives in a .vri file, recursively reads
and merges the included files into a single output .vri file.

This is used for Stage 0 bootstrap: produce a single-file virc_merged.vri
that can be compiled by virc without needing include resolution.

Usage:
    python3 scripts/merge_modules.py stdlib/vir/compiler/virc.vri -o build/virc_merged.vri

Path resolution rules (matching C VM ir_lower.c):
  - `include vir::rt::syscall;`  →  stdlib/vir/rt/syscall.vri
  - `include types;`             →  search order: same dir, stdlib/vir/core/
  - `include lexer;`             →  same dir as including file
"""

import re
import os
import sys
from pathlib import Path

# Standard library search paths (relative to VIR_ROOT)
STDLIB_SEARCH = [
    "stdlib/vir/core",
    "stdlib/vir/collections",
    "stdlib/vir/str",
    "stdlib/vir/mem",
    "stdlib/vir/io",
    "stdlib/vir/codegen",
    "stdlib/vir/wasm",
    "stdlib/vir/error",
]

# Regex for include and import/export/module statements
RE_INCLUDE = re.compile(r"^include\s+(.+?)\s*;", re.MULTILINE)
RE_MODULE_DECL = re.compile(r"^(module|import|export)\s+", re.MULTILINE)


class ModuleMerger:
    def __init__(self, vir_root: str):
        self.vir_root = Path(vir_root)
        self.included: set[str] = set()  # normalized paths (include guards)
        self.output_lines: list[str] = []
        self.stats = {"files": 0, "lines": 0, "skipped_dupes": 0}

    def resolve_include_path(self, include_spec: str, current_dir: Path) -> Path | None:
        """Resolve an include spec to an actual file path."""
        spec = include_spec.strip().strip('"').strip("'")

        # Qualified path: vir::rt::syscall → stdlib/vir/rt/syscall.vri
        if "::" in spec:
            rel = spec.replace("::", "/") + ".vri"
            full = self.vir_root / "stdlib" / rel
            if full.exists():
                return full
            # Try without stdlib/
            full2 = self.vir_root / rel
            if full2.exists():
                return full2
            return None

        # Bare include: search relative to current file first
        bare = spec + ".vri" if not spec.endswith(".vri") else spec

        # 1. Same directory as current file
        candidate = current_dir / bare
        if candidate.exists():
            return candidate

        # 2. Search stdlib paths
        for search_dir in STDLIB_SEARCH:
            candidate = self.vir_root / search_dir / bare
            if candidate.exists():
                return candidate

        return None

    def process_file(self, filepath: Path, depth: int = 0) -> None:
        """Process a .vri file, resolving includes recursively."""
        normalized = str(filepath.resolve())
        if normalized in self.included:
            self.stats["skipped_dupes"] += 1
            return
        self.included.add(normalized)
        self.stats["files"] += 1

        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"  {'  ' * depth}[WARN] Cannot read {filepath}: {e}", file=sys.stderr)
            return

        current_dir = filepath.parent
        lines = content.split("\n")
        prefix = "  " * depth

        print(f"{prefix}[MERGE] {filepath.relative_to(self.vir_root)} ({len(lines)} lines)",
              file=sys.stderr)

        self.output_lines.append(f"# ═══ BEGIN: {filepath.relative_to(self.vir_root)} ═══")

        for line in lines:
            stripped = line.strip()

            # Handle include directives: process recursively
            m = RE_INCLUDE.match(stripped)
            if m:
                include_spec = m.group(1)
                resolved = self.resolve_include_path(include_spec, current_dir)
                if resolved:
                    self.output_lines.append(f"# [merged] {stripped}")
                    self.process_file(resolved, depth + 1)
                else:
                    # Can't resolve — keep as comment (might be compile-time only)
                    self.output_lines.append(f"# [unresolved] {stripped}")
                    print(f"{prefix}  [WARN] Cannot resolve: {include_spec}", file=sys.stderr)
                continue

            # Skip module/import/export declarations (already merged)
            if stripped.startswith("module ") and stripped.endswith(";"):
                self.output_lines.append(f"# [merged] {stripped}")
                continue
            if stripped.startswith("import ") and " from " in stripped and stripped.endswith(";"):
                self.output_lines.append(f"# [merged] {stripped}")
                continue
            if stripped.startswith("export ") and stripped.endswith(";"):
                self.output_lines.append(f"# [merged] {stripped}")
                continue

            # Regular line — keep as-is
            # But check if it's a continuation of a commented-out import/module line
            if (self.output_lines and
                self.output_lines[-1].startswith("# [merged") and
                line and line[0] in (' ', '\t') and
                not stripped.startswith("#")):
                self.output_lines.append(f"# [merged-cont] {stripped}")
                continue

            self.output_lines.append(line)
            self.stats["lines"] += 1

        self.output_lines.append(f"# ═══ END: {filepath.relative_to(self.vir_root)} ═══")
        self.output_lines.append("")

    def get_output(self) -> str:
        header = [
            "##",
            f" * virc_merged.vri — Auto-generated merged Vir compiler",
            f" * Generated by merge_modules.py on {__import__('datetime').datetime.now().isoformat()[:19]}",
            f" * Files: {self.stats['files']}, Lines: {self.stats['lines']}, Deduped: {self.stats['skipped_dupes']}",
            f" *",
            f" * DO NOT EDIT — regenerate with:",
            f" *   python3 scripts/merge_modules.py stdlib/vir/compiler/virc.vri -o build/virc_merged.vri",
            "##",
            "",
        ]
        return "\n".join(header + self.output_lines)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Merge Vir modules into single file")
    ap.add_argument("input", help="Root .vri file to process")
    ap.add_argument("-o", "--output", default="-", help="Output file (default: stdout)")
    ap.add_argument("--root", default=None, help="Vir project root (auto-detected)")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    # Auto-detect VIR_ROOT
    if args.root:
        vir_root = Path(args.root).resolve()
    else:
        # Walk up from input file to find stdlib/
        p = input_path.parent
        while p != p.parent:
            if (p / "stdlib").is_dir():
                vir_root = p
                break
            p = p.parent
        else:
            print("Error: Cannot find Vir root (no stdlib/ directory found)", file=sys.stderr)
            sys.exit(1)

    print(f"[merge_modules] Root: {vir_root}", file=sys.stderr)
    print(f"[merge_modules] Input: {input_path}", file=sys.stderr)

    merger = ModuleMerger(str(vir_root))
    merger.process_file(input_path)

    output = merger.get_output()

    if args.output == "-":
        sys.stdout.write(output)
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[merge_modules] Written: {out_path} ({len(output)} bytes)", file=sys.stderr)

    print(f"[merge_modules] Stats: {merger.stats}", file=sys.stderr)


if __name__ == "__main__":
    main()
