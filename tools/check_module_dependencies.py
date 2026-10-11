#!/usr/bin/env python3
"""
tools/check_module_dependencies.py — Enforces single-declaration invariant across compiler sources.
Delegates to pure-Vir native verifier bin/vir-pass-check (VIRC-ISS-0050 / VIRC-PLN-0029 Phase 5).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS_CHECK = ROOT / "bin" / "vir-pass-check"

if not PASS_CHECK.is_file():
    virc = ROOT / "bin" / "virc"
    subprocess.run([str(virc), str(ROOT / "tools/vir-pass-check/src/main.vri"), "-o", str(PASS_CHECK)], check=True)

sys.exit(subprocess.run([str(PASS_CHECK)], cwd=ROOT).returncode)
