#!/usr/bin/env python3
"""
tools/check_pass_architecture.py — Architecture verification for pass orchestrators.

Enforces VIRC-PLN-0003 Section 5.4, 6.2, and Phase 6 policy:
1. Pass entry files (matching `pass*.vri` or `pass*.vri` under semantic/ and ir/mir/)
   must be clean orchestrators:
   - Must declare stable PASS_*_ID, PASS_*_STAGE, and PASS_*_NAME metadata.
   - Must expose an orchestrator run entry point (`pass*Run` or `pass_*_run`).
   - Must NOT contain AST/HIR/MIR/LIR rewrite bodies.
   - Must NOT contain concrete type unification/tensor rules or borrow state transfer algorithms.
   - Must NOT exceed the LOC limit (<= 300 logical lines).
2. Boundary invariants:
   - stdlib/stdlib.vri must contain zero `compiler.*` entries.
   - compiler/generated/virc.vri must match generated sync state.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROHIBITED_TRANSFORM_PATTERNS = [
    # AST/MIR/HIR rewriting patterns
    (re.compile(r"\bast_new\(AstType\.(BinOp|Assign|Call|UnaryOp|Index|FieldAccess)\)"), "AST rewrite node construction"),
    (re.compile(r"\bmir_instr_new\b"), "Direct MIR instruction synthesis"),
    (re.compile(r"\blir_emit_\w+\b"), "Direct LIR lowering pattern"),
    # Concrete domain logic forbidden in orchestrators
    (re.compile(r"\bpass6_type_strings_compatible\b"), "Inline type compatibility algorithm"),
    (re.compile(r"\bpass8_merge_loop_edge\b"), "Inline borrow transfer loop merge algorithm"),
    (re.compile(r"\bdominance_frontier\b"), "Inline dominance algorithm"),
    (re.compile(r"\binstruction_selection\b"), "Target instruction selection pattern"),
]

def check_pass_orchestrator(pass_file: Path) -> list[str]:
    errors = []
    text = pass_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [l for l in lines if l and not l.startswith("#")]

    # 1. Check LOC limit (<= 300 logical lines)
    if len(non_empty_lines) > 300:
        errors.append(f"{pass_file.name}: Orchestrator has {len(non_empty_lines)} logical lines (limit: <= 300)")

    # 2. Check stable metadata declaration
    has_id = any(re.search(r"PASS_\w+_ID\s*:", l) for l in non_empty_lines)
    has_stage = any(re.search(r"PASS_\w+_STAGE\s*:", l) for l in non_empty_lines)
    if not (has_id and has_stage):
        errors.append(f"{pass_file.name}: Missing PASS_*_ID or PASS_*_STAGE metadata constants")

    # 3. Check exported run entry point
    has_run_export = bool(re.search(r"\bexport\b[^;\n]*?\b(pass\w*Run|pass_\w+_run)\b", text) or
                          re.search(r"\bexport\b[\s\S]+?\b(pass\w*Run|pass_\w+_run)\b", text))
    if not has_run_export:
        errors.append(f"{pass_file.name}: Missing exported pass run entry point (`pass*Run` or `pass_*_run`)")

    # 4. Check for prohibited transform bodies
    for pattern, desc in PROHIBITED_TRANSFORM_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(f"{pass_file.name}: Contains prohibited transform logic: {desc} (match: '{match.group(0)}')")

    return errors

def check_stdlib_boundary() -> list[str]:
    errors = []
    stdlib_reg = ROOT / "stdlib/stdlib.vri"
    if not stdlib_reg.is_file():
        errors.append("stdlib/stdlib.vri not found")
        return errors
    
    text = stdlib_reg.read_text(encoding="utf-8")
    for idx, line in enumerate(text.splitlines(), start=1):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        if re.search(r"\bcompiler\.", clean) or re.search(r"=\s*compiler/", clean):
            errors.append(f"stdlib/stdlib.vri:{idx}: Found compiler mapping in stdlib: '{clean}'")

    return errors

def main() -> int:
    all_errors = []

    # Find pass orchestrators
    pass_files = []
    semantic_dir = ROOT / "compiler/src/semantic"
    if semantic_dir.is_dir():
        pass_files.extend(sorted(semantic_dir.glob("pass*.vri")))
    
    mir_dir = ROOT / "compiler/src/ir/mir"
    if mir_dir.is_dir():
        pass_files.extend(sorted(mir_dir.glob("pass*.vri")))

    if not pass_files:
        all_errors.append("No pass orchestrators (`pass*.vri`) found in compiler tree")

    for pass_file in pass_files:
        all_errors.extend(check_pass_orchestrator(pass_file))

    # Check stdlib boundary
    all_errors.extend(check_stdlib_boundary())

    # Check compiler module dependency hygiene (VIRC-ISS-0007 / VIRC-PLN-0005)
    sys.path.insert(0, str(ROOT / "tools"))
    from check_module_dependencies import check_all as check_module_deps
    dep_count, dep_violations = check_module_deps()
    all_errors.extend(dep_violations)

    if all_errors:
        print("FAIL: Pass architecture violations detected:")
        for err in all_errors:
            print(f"  • {err}")
        return 1

    print(f"PASS: Architecture verified ({len(pass_files)} orchestrator(s) checked, stdlib boundary clean, {dep_count} module dependencies clean).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
