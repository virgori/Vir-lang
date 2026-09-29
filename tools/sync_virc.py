#!/usr/bin/env python3
"""
tools/sync_virc.py — Synchronize stdlib/vir/compiler/virc.vri from modular sources.

This tool updates the bundled `stdlib/vir/compiler/virc.vri` file from the individual
module files in `stdlib/vir/compiler/`. It preserves all sections unique to `virc.vri`
(such as `CompilerConfig`, command-line argument parsing, and `main` entrypoint)
while safely refreshing any modified module content.

Usage:
    python3 tools/sync_virc.py [--check] [module_path ...]
"""

from __future__ import annotations
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC_PATH = ROOT / "stdlib/vir/compiler/virc.vri"

def get_module_content_for_bundle(module_path: Path, src_start_line: int, src_end_line: int | None) -> list[str]:
    """Read one source span, omitting includes expanded into separate sections."""
    lines = module_path.read_text().splitlines()
    if src_start_line < 1 or src_start_line > len(lines) + 1:
        raise ValueError(f"Invalid source marker {module_path}:{src_start_line}")
    slice_lines = lines[src_start_line - 1 : None if src_end_line is None else src_end_line - 1]
    result = []
    for line in slice_lines:
        if re.match(r"^\s*include\s+", line):
            continue
        result.append(line)
    return result

def sync_module_to_virc(target_modules: list[str] | None = None, check: bool = False) -> int:
    virc_text = VIRC_PATH.read_text()
    virc_lines = virc_text.splitlines()

    # Find all marker positions: (line_idx_in_virc, source_rel_path, source_start_line)
    markers: list[tuple[int, str, int]] = []
    for i, line in enumerate(virc_lines):
        m = re.match(r"^#\s*@vir_source\s+(\S+)\s+(\d+)", line)
        if m:
            markers.append((i, m.group(1), int(m.group(2))))

    if not markers:
        print("Error: No # @vir_source markers found in virc.vri")
        return 1

    # Map each section: (start_marker_idx, end_idx, source_path, source_line)
    sections = []
    for idx in range(len(markers)):
        start_virc_line, src_path, src_line = markers[idx]
        end_virc_line = markers[idx + 1][0] if idx + 1 < len(markers) else len(virc_lines)
        sections.append((start_virc_line, end_virc_line, src_path, src_line))

    # A module can resume after several included modules. Each marker owns only
    # the source span up to that module's next marker, never the whole suffix.
    next_source_line: dict[int, int | None] = {}
    for idx, (_, src_path, src_line) in enumerate(markers):
        next_source_line[idx] = None
        for _, later_path, later_line in markers[idx + 1 :]:
            if later_path == src_path and later_line > src_line:
                next_source_line[idx] = later_line
                break

    # Reconstruct virc_lines
    new_virc_lines = []
    modified_modules = set()

    for section_idx, (start_virc_line, end_virc_line, src_path, src_line) in enumerate(sections):
        marker_line = virc_lines[start_virc_line]
        new_virc_lines.append(marker_line)

        # Content lines currently in virc
        cur_content = virc_lines[start_virc_line + 1 : end_virc_line]

        # If this section belongs to virc.vri itself, preserve it exactly
        if src_path == "stdlib/vir/compiler/virc.vri":
            new_virc_lines.extend(cur_content)
            continue

        mod_file = ROOT / src_path
        if not mod_file.exists():
            # If source file does not exist, keep current content
            new_virc_lines.extend(cur_content)
            continue

        # If filtering by target modules, only update specified modules (exact basename or path)
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
    if new_text == virc_text:
        print("virc.vri is already identical to source modules. No changes needed.")
        return 0

    if check:
        print(f"virc.vri differs from source modules: {', '.join(sorted(modified_modules))}")
        return 1

    VIRC_PATH.write_text(new_text)
    print(f"Updated {VIRC_PATH} from modules: {', '.join(sorted(modified_modules))}")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("modules", nargs="*", help="module basename or repo-relative path")
    args = parser.parse_args()
    raise SystemExit(sync_module_to_virc(args.modules or None, args.check))
