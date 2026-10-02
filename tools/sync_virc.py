#!/usr/bin/env python3
"""
tools/sync_virc.py — Synchronize compiler generated bundle from modular sources.

Supports both:
- Target layout: `compiler/src/**` -> `compiler/generated/virc.vri`
- Legacy layout: `stdlib/vir/compiler/**` -> `stdlib/vir/compiler/virc.vri`

Usage:
    python3 tools/sync_virc.py [--check] [module_path ...]
"""

from __future__ import annotations
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def get_virc_path() -> Path:
    target_bundle = ROOT / "compiler/generated/virc.vri"
    if target_bundle.is_file():
        return target_bundle
    return ROOT / "stdlib/vir/compiler/virc.vri"

def get_module_content_for_bundle(module_path: Path, src_start_line: int, src_end_line: int | None) -> list[str]:
    lines = module_path.read_text(encoding="utf-8").splitlines()
    if src_start_line < 1 or src_start_line > len(lines) + 1:
        raise ValueError(f"Invalid source marker {module_path}:{src_start_line}")
    slice_lines = lines[src_start_line - 1 : None if src_end_line is None else src_end_line - 1]
    result = []
    for line in slice_lines:
        if re.match(r"^\s*include\s+", line):
            continue
        result.append(line)
    return result

def sync_module_to_virc(target_modules: list[str] | None = None, check: bool = False,
                        add_modules: list[str] | None = None, before: str | None = None) -> int:
    virc_path = get_virc_path()
    if not virc_path.is_file():
        print(f"Error: Neither target nor legacy virc.vri found at {virc_path}")
        return 1

    virc_text = virc_path.read_text(encoding="utf-8")
    original_text = virc_text

    if add_modules:
        if not before:
            raise ValueError("--add-module requires --before with an existing source module")
        anchor = f"# @vir_source {before} 1\n"
        if anchor not in virc_text:
            raise ValueError(f"Missing insertion source marker: {before}")
        additions = []
        for module in add_modules:
            path = (ROOT / module).resolve()
            if not path.is_file():
                raise ValueError(f"Not a valid compiler module file: {module}")
            relative = path.relative_to(ROOT).as_posix()
            marker = f"# @vir_source {relative} 1\n"
            if marker not in virc_text:
                additions.append(marker + "\n".join(get_module_content_for_bundle(path, 1, None)) + "\n")
        virc_text = virc_text.replace(anchor, "".join(additions) + anchor, 1)

    virc_lines = virc_text.splitlines()

    markers: list[tuple[int, str, int]] = []
    for i, line in enumerate(virc_lines):
        m = re.match(r"^#\s*@vir_source\s+(\S+)\s+(\d+)", line)
        if m:
            markers.append((i, m.group(1), int(m.group(2))))

    if not markers:
        print("Error: No # @vir_source markers found in virc.vri")
        return 1

    sections = []
    for idx in range(len(markers)):
        start_virc_line, src_path, src_line = markers[idx]
        end_virc_line = markers[idx + 1][0] if idx + 1 < len(markers) else len(virc_lines)
        sections.append((start_virc_line, end_virc_line, src_path, src_line))

    next_source_line: dict[int, int | None] = {}
    for idx, (_, src_path, src_line) in enumerate(markers):
        next_source_line[idx] = None
        for _, later_path, later_line in markers[idx + 1 :]:
            if later_path == src_path and later_line > src_line:
                next_source_line[idx] = later_line
                break

    new_virc_lines = []
    modified_modules = set()

    for section_idx, (start_virc_line, end_virc_line, src_path, src_line) in enumerate(sections):
        marker_line = virc_lines[start_virc_line]
        new_virc_lines.append(marker_line)

        cur_content = virc_lines[start_virc_line + 1 : end_virc_line]

        if src_path.endswith("virc.vri"):
            new_virc_lines.extend(cur_content)
            continue

        mod_file = ROOT / src_path
        if not mod_file.exists():
            new_virc_lines.extend(cur_content)
            continue

        if target_modules:
            matched = any(target == Path(src_path).name or target == src_path for target in target_modules)
            if not matched:
                new_virc_lines.extend(cur_content)
                continue

        mod_lines = get_module_content_for_bundle(mod_file, src_line, next_source_line[section_idx])
        new_virc_lines.extend(mod_lines)
        if mod_lines != cur_content:
            modified_modules.add(src_path)

    new_text = "\n".join(new_virc_lines) + "\n"
    if new_text == original_text:
        print(f"{virc_path.name} is already identical to source modules. No changes needed.")
        return 0

    if check:
        print(f"{virc_path.name} differs from source modules: {', '.join(sorted(modified_modules))}")
        return 1

    virc_path.write_text(new_text, encoding="utf-8")
    print(f"Updated {virc_path} from modules: {', '.join(sorted(modified_modules))}")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("--add-module", action="append", default=[], help="register a new canonical source section")
    parser.add_argument("--before", help="existing module whose first source marker follows new sections")
    parser.add_argument("modules", nargs="*", help="module basename or repo-relative path")
    args = parser.parse_args()
    raise SystemExit(sync_module_to_virc(args.modules or None, args.check, args.add_module, args.before))
