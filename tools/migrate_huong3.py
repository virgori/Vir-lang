#!/usr/bin/env python3
"""
tools/migrate_huong3.py — Implement Hướng 3: Flat include names via module.list.

VIRC-ISS-0007 / VIRC-PLN-0005 — Phase 1 (safe, bundle-order-independent):

  Normalizes dotted include names to flat registered module names.
    compiler.X  →  X
    virc.X.Y    →  Y
  using the ALIAS_MAP derived from compiler/module.list.

What this script intentionally does NOT do:
  - Does NOT remove `import ... from M` statements.
    Removing imports is unsafe when the bundle order places M after the
    current file, because sync_virc.py strips all `include` lines and
    the import is the only mechanism that makes M's symbols available
    in the current file's bundle section. Import cleanup is deferred
    until the bundle is reordered so every dependency precedes its user.
  - Does NOT convert standalone `import ... from M` to `include M`.
  - Does NOT touch stdlib dotted names (rt.*, jit.*, wasm.*).
    Those are registered in stdlib/stdlib.vri, not compiler/module.list.

Run dry-run (default):
    python3 tools/migrate_huong3.py --verbose

Apply:
    python3 tools/migrate_huong3.py --apply
"""

from __future__ import annotations
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILER_SRC = ROOT / "compiler/src"

# Map dotted compiler module names to flat registered names in compiler/module.list.
# stdlib dotted names (rt.*, jit.*, wasm.*) are intentionally absent —
# they live in stdlib/stdlib.vri and must remain as dotted references.
ALIAS_MAP: dict[str, str] = {
    # compiler.* prefixes
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
    # virc.* prefixes
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


def normalize_include_name(mod: str) -> str:
    """Return the flat registered name for a dotted compiler module name.
    Returns the original name unchanged if no alias is defined
    (including stdlib dotted names like rt.alloc, jit.bridge, wasm.wasm)."""
    return ALIAS_MAP.get(mod, mod)


def process_file(file_path: Path, apply: bool = False) -> tuple[int, list[str]]:
    """
    Process a single .vri source file:
      - Flatten dotted `include compiler.X` / `include virc.X.Y` names.
      - Leave all `import ... from M` lines UNCHANGED.

    Returns (num_flattened, changes_summary).
    """
    if not file_path.is_file():
        return 0, []
    if file_path.is_symlink() and not file_path.exists():
        return 0, []

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    new_lines: list[str] = []
    flattened_count = 0
    changes: list[str] = []

    in_block_comment = False

    for raw in lines:
        s = raw.strip()

        # Block comment tracking (## ... ##)
        if in_block_comment:
            if "##" in s:
                in_block_comment = False
            new_lines.append(raw)
            continue

        if s.startswith("##"):
            in_block_comment = True
            new_lines.append(raw)
            continue

        # Line comment — keep as-is
        if s.startswith("#"):
            new_lines.append(raw)
            continue

        # ── Handle `include` statements only ─────────────────────────────────
        m_inc = re.match(r"^(\s*include\s+)([A-Za-z0-9_.\"\'-]+)(.*)", raw)
        if m_inc:
            prefix, mod_name, suffix = m_inc.groups()
            cleaned = mod_name.strip("\"'")
            norm = normalize_include_name(cleaned)
            if norm != cleaned:
                raw = f"{prefix}{norm}{suffix}"
                flattened_count += 1
                changes.append(f"Flatten include: {cleaned} -> {norm}")

        new_lines.append(raw)

    if apply and flattened_count > 0:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return flattened_count, changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--apply", action="store_true",
                        help="Apply migrations to files (default: dry-run)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-file change details")
    parser.add_argument("paths", nargs="*",
                        help="Limit to specific files or directories (default: compiler/src)")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.paths:
        for p in args.paths:
            fp = Path(p)
            if fp.is_dir():
                targets.extend(sorted(fp.rglob("*.vri")))
            elif fp.is_file():
                targets.append(fp)
            else:
                print(f"Warning: path not found: {p}", file=sys.stderr)
    else:
        targets = sorted(COMPILER_SRC.rglob("*.vri"))

    total_flattened = 0
    files_changed = 0

    for p in targets:
        if not p.is_file():
            continue
        if p.is_symlink() and not p.exists():
            continue
        fl_count, changes = process_file(p, apply=args.apply)
        if fl_count > 0:
            files_changed += 1
            total_flattened += fl_count
            if args.verbose:
                rel = p.relative_to(ROOT).as_posix()
                print(f"[{rel}]: {fl_count} includes flattened")
                for c in changes[:8]:
                    print(f"   • {c}")
                if len(changes) > 8:
                    print(f"   • ... and {len(changes) - 8} more")

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] Summary: {files_changed} files affected.")
    print(f"  • Include names flattened: {total_flattened}")
    if not args.apply:
        print("\nNote: imports are untouched (safe; import cleanup requires bundle reorder first).")


if __name__ == "__main__":
    main()
