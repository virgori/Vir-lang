#!/usr/bin/env python3
"""
tools/migrate_huong3_phase2.py — Remove redundant `import ... from M` lines.

VIRC-PLN-0005 Phase 2: Safe import cleanup guided by bundle order.

A file F has a redundant import when:
  - F contains `include M` (M is physically loaded)
  - F also contains `import X from M` (redundant per single-declaration invariant)
  - AND M's first section in the bundle appears BEFORE F's first section

The third condition is the safety gate: sync_virc.py strips all `include` lines
when assembling the bundle. If M's content is physically inlined earlier in the
bundle than F's section, M's symbols are already in scope when F's section is
compiled — so the import is truly redundant and can be removed.

If M appears AFTER F in the bundle (or is not in the bundle at all, e.g. stdlib
preludes), the import must be kept because it is the only mechanism that makes
M's symbols visible in F's bundle section.

Usage:
    # dry-run
    python3 tools/migrate_huong3_phase2.py --verbose

    # apply
    python3 tools/migrate_huong3_phase2.py --apply

    # check specific files
    python3 tools/migrate_huong3_phase2.py --verbose compiler/src/backend/opt_backend.vri
"""

from __future__ import annotations
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILER_SRC = ROOT / "compiler/src"
BUNDLE_PATH = ROOT / "compiler/generated/virc.vri"
MODULE_LIST = ROOT / "compiler/module.list"

# Same alias map as phase 1 — maps dotted include names to flat module names.
# stdlib dotted names are absent by design.
ALIAS_MAP: dict[str, str] = {
    "compiler.ast_to_hir": "ast_to_hir",
    "compiler.ast_to_mir": "ast_to_mir",
    "compiler.cli_environment": "cli_environment",
    "compiler.cli_storage": "cli_storage",
    "compiler.cli_ui": "cli_ui",
    "compiler.codegen": "codegen",
    "compiler.codegen_x86": "codegen_x86",
    "compiler.context": "context",
    "compiler.ffi_imports": "ffi_imports",
    "compiler.hir": "hir",
    "compiler.hir_to_mir": "hir_to_mir",
    "compiler.ide_facts": "ide_facts",
    "compiler.ide_semantic": "ide_semantic",
    "compiler.lexer": "lexer",
    "compiler.lir": "lir",
    "compiler.lir_codegen": "lir_codegen",
    "compiler.lir_interference": "lir_interference",
    "compiler.lir_liveness": "lir_liveness",
    "compiler.lir_lower": "lir_lower",
    "compiler.lir_ra_arena": "lir_ra_arena",
    "compiler.lir_regalloc_color": "lir_regalloc_color",
    "compiler.lir_target_desc": "lir_target_desc",
    "compiler.lir_to_mc": "lir_to_mc",
    "compiler.lir_verifier": "lir_verifier",
    "compiler.main": "main",
    "compiler.mc": "mc",
    "compiler.mc_verify": "mc_verify",
    "compiler.mir": "mir",
    "compiler.mir_cfg": "mir_cfg",
    "compiler.mir_opt": "mir_opt",
    "compiler.mir_opt_pipeline": "mir_opt_pipeline",
    "compiler.mir_ssa": "mir_ssa",
    "compiler.opt_backend": "opt_backend",
    "compiler.opt_trace": "opt_trace",
    "compiler.parser": "parser",
    "compiler.pipeline": "pipeline",
    "compiler.scope_tree": "scope_tree",
    "compiler.scopes": "scope_tree",
    "compiler.symbol_table": "symbol_table",
    "compiler.symbols": "symbol_table",
    "compiler.target": "target",
    "compiler.target_spec": "target_spec",
    "compiler.tool_json": "tool_json",
    "compiler.type_table": "type_table",
    "compiler.sem.modules": "sem_pass1_modules",
    "compiler.sem.symbols": "sem_pass2_symbols",
    "compiler.sem.names": "sem_pass3_names",
    "compiler.sem.types": "sem_pass4_types",
    "compiler.sem.infer": "sem_pass5_infer",
    "compiler.sem.typecheck": "sem_pass6_typecheck",
    "compiler.sem.cfa": "sem_pass7_cfa",
    "compiler.sem.borrow": "sem_pass8_borrow",
    "compiler.sem.diagnostics": "sem_pass10_diagnostics",
    "compiler.sem_pass10_diagnostics": "sem_pass10_diagnostics",
    "compiler.sem_pass1_modules": "sem_pass1_modules",
    "compiler.sem_pass2_symbols": "sem_pass2_symbols",
    "compiler.sem_pass3_names": "sem_pass3_names",
    "compiler.sem_pass4_types": "sem_pass4_types",
    "compiler.sem_pass5_infer": "sem_pass5_infer",
    "compiler.sem_pass6_typecheck": "sem_pass6_typecheck",
    "compiler.sem_pass7_cfa": "sem_pass7_cfa",
    "compiler.sem_pass8_borrow": "sem_pass8_borrow",
    "compiler.sem_pass9_constfold": "sem_pass9_constfold",
    "compiler.sem_pass_ide": "sem_pass_ide",
    "virc.backend.opt_trace": "opt_trace",
    "virc.cli.cli_environment": "cli_environment",
    "virc.cli.cli_ui": "cli_ui",
    "virc.diagnostic.context": "context",
    "virc.frontend.source_manager": "source_manager",
    "virc.ide.ide_semantic": "ide_semantic",
    "virc.semantic.scope_tree": "scope_tree",
    "virc.semantic.symbol_table": "symbol_table",
    "virc.semantic.type_table": "type_table",
}

def normalize(mod: str) -> str:
    return ALIAS_MAP.get(mod, mod)


def parse_module_list(path: Path) -> dict[str, Path]:
    """
    Parse compiler/module.list.
    Returns flat_name -> absolute_path mapping.
    """
    mapping: dict[str, Path] = {}
    root_dir = path.parent
    src_dir = root_dir  # default; overridden by `virc = src` line
    virc_prefix = ""

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "root":
            root_dir = path.parent / val
            continue
        if key == "virc":
            virc_prefix = val
            src_dir = path.parent / val
            continue
        target = root_dir / val
        mapping[key] = target.resolve()

    return mapping


def build_bundle_order(bundle: Path) -> dict[str, int]:
    """
    Parse bundle markers to find the first occurrence index of each source file.
    Returns {absolute_path_str: first_marker_index} for non-bundle source files.
    Marker index is the sequential position (0-based) among all @vir_source markers
    (including virc.vri markers), so we can compare relative order.
    """
    order: dict[str, int] = {}
    idx = 0
    for line in bundle.read_text().splitlines():
        m = re.match(r"^#\s*@vir_source\s+(\S+)\s+\d+", line)
        if m:
            src = (ROOT / m.group(1)).resolve()
            src_str = str(src)
            if src_str not in order:
                order[src_str] = idx
            idx += 1
    return order


def process_file(
    file_path: Path,
    module_to_path: dict[str, Path],   # flat name -> abs path
    bundle_order: dict[str, int],       # abs path str -> bundle index
    apply: bool = False,
) -> tuple[int, int, list[str]]:
    """
    Remove redundant `import ... from M` lines where:
      1. `include M` already exists in this file, AND
      2. M's first bundle section precedes this file's first bundle section.

    Returns (removed_count, skipped_count, changes_summary).
    """
    if not file_path.is_file():
        return 0, 0, []
    if file_path.is_symlink() and not file_path.exists():
        return 0, 0, []

    file_abs = str(file_path.resolve())
    file_bundle_pos = bundle_order.get(file_abs, -1)

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # First pass: collect all `include M` names and their normalized forms
    # and determine which included modules appear BEFORE this file in the bundle.
    included_safe: set[str] = set()   # modules safe to drop imports for
    included_all: set[str] = set()    # all included modules (for reference)
    in_block_comment = False

    for raw in lines:
        s = raw.strip()
        if in_block_comment:
            if "##" in s:
                in_block_comment = False
            continue
        if s.startswith("##"):
            in_block_comment = True
            continue
        if s.startswith("#"):
            continue

        m_inc = re.match(r"^\s*include\s+([A-Za-z0-9_.\"\'-]+)", raw)
        if m_inc:
            mod_name = m_inc.group(1).strip("\"'")
            norm = normalize(mod_name)
            included_all.add(norm)

            # Determine bundle position of this included module
            mod_path = module_to_path.get(norm)
            if mod_path is not None:
                mod_abs = str(mod_path)
                mod_bundle_pos = bundle_order.get(mod_abs, -1)
                if mod_bundle_pos != -1 and file_bundle_pos != -1:
                    if mod_bundle_pos < file_bundle_pos:
                        included_safe.add(norm)
                    # else: M comes after F in bundle — keep import
                # If mod_path not in bundle_order at all but file is:
                # could be a helper file not directly in bundle; skip (keep import)

    if not included_safe:
        return 0, 0, []

    # Second pass: remove redundant imports for modules in included_safe
    new_lines: list[str] = []
    removed_count = 0
    skipped_count = 0
    changes: list[str] = []
    in_block_comment = False
    idx = 0
    n = len(lines)

    while idx < n:
        raw = lines[idx]
        s = raw.strip()

        if in_block_comment:
            if "##" in s:
                in_block_comment = False
            new_lines.append(raw)
            idx += 1
            continue

        if s.startswith("##"):
            in_block_comment = True
            new_lines.append(raw)
            idx += 1
            continue

        if s.startswith("#"):
            new_lines.append(raw)
            idx += 1
            continue

        # Check for import statement
        if re.match(r"^\s*import\b", raw):
            import_lines = [raw]
            mod_target: str | None = None

            # Find `from <module>` — may be on the same line or next lines
            m_single = re.search(r"\bfrom\s+([A-Za-z0-9_.\"\'-]+)\s*$", s)
            if m_single:
                mod_target = m_single.group(1).strip("\"'")
            else:
                look = idx + 1
                while look < n:
                    next_raw = lines[look]
                    import_lines.append(next_raw)
                    m_multi = re.search(
                        r"\bfrom\s+([A-Za-z0-9_.\"\'-]+)\s*$",
                        next_raw.strip()
                    )
                    if m_multi:
                        mod_target = m_multi.group(1).strip("\"'")
                        break
                    look += 1

            if mod_target is not None:
                norm_target = normalize(mod_target)
                if norm_target in included_safe:
                    # Safe to remove — M is included and precedes F in bundle
                    removed_count += 1
                    changes.append(f"Remove redundant import from {norm_target}")
                    idx += len(import_lines)
                    continue
                elif norm_target in included_all:
                    # Included but M comes AFTER F in bundle — must keep
                    skipped_count += 1
                    changes.append(f"[KEEP] import from {norm_target} (M after F in bundle)")

        new_lines.append(raw)
        idx += 1

    if apply and removed_count > 0:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return removed_count, skipped_count, changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--apply", action="store_true",
                        help="Apply removals to files (default: dry-run)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-file details")
    parser.add_argument("--show-kept", action="store_true",
                        help="Also show imports that are kept (M after F)")
    parser.add_argument("paths", nargs="*",
                        help="Limit to specific files/dirs (default: compiler/src)")
    args = parser.parse_args()

    if not BUNDLE_PATH.exists():
        print(f"Error: bundle not found: {BUNDLE_PATH}", file=sys.stderr)
        sys.exit(1)
    if not MODULE_LIST.exists():
        print(f"Error: module.list not found: {MODULE_LIST}", file=sys.stderr)
        sys.exit(1)

    module_to_path = parse_module_list(MODULE_LIST)
    bundle_order = build_bundle_order(BUNDLE_PATH)

    # Also index stdlib runtime modules by flat name
    # (they appear in the bundle header as compiler/src/misc/*.vri)
    stdlib_flat: dict[str, Path] = {
        "syscall": (ROOT / "compiler/src/misc/syscall.vri").resolve(),
        "alloc":   (ROOT / "compiler/src/misc/alloc.vri").resolve(),
        "string_rt": (ROOT / "compiler/src/misc/string_rt.vri").resolve(),
        "io":      (ROOT / "compiler/src/misc/io.vri").resolve(),
        "vec_rt":  (ROOT / "compiler/src/misc/vec_rt.vri").resolve(),
        "vec":     (ROOT / "compiler/src/misc/vec_rt.vri").resolve(),
        "result":  (ROOT / "compiler/src/bootstrap/prelude/result_prelude.vri").resolve(),
        "option":  (ROOT / "compiler/src/bootstrap/prelude/option_prelude.vri").resolve(),
    }
    for k, v in stdlib_flat.items():
        if k not in module_to_path:
            module_to_path[k] = v

    targets: list[Path] = []
    if args.paths:
        for p in args.paths:
            fp = Path(p)
            if fp.is_dir():
                targets.extend(sorted(fp.rglob("*.vri")))
            elif fp.is_file():
                targets.append(fp)
            else:
                print(f"Warning: not found: {p}", file=sys.stderr)
    else:
        targets = sorted(COMPILER_SRC.rglob("*.vri"))

    total_removed = 0
    total_kept = 0
    files_changed = 0

    for p in targets:
        if not p.is_file():
            continue
        if p.is_symlink() and not p.exists():
            continue
        removed, kept, changes = process_file(p, module_to_path, bundle_order, apply=args.apply)
        if removed > 0 or (kept > 0 and args.show_kept):
            if removed > 0:
                files_changed += 1
            total_removed += removed
            total_kept += kept
            if args.verbose:
                rel = p.relative_to(ROOT).as_posix()
                print(f"[{rel}]: {removed} removed, {kept} kept")
                for c in changes:
                    if c.startswith("[KEEP]") and not args.show_kept:
                        continue
                    print(f"   • {c}")
        elif kept > 0:
            total_kept += kept

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] Summary: {files_changed} files changed.")
    print(f"  • Redundant imports removed: {total_removed}")
    print(f"  • Imports kept (M after F in bundle): {total_kept}")


if __name__ == "__main__":
    main()
