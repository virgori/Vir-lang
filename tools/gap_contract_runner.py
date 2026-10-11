#!/usr/bin/env python3
"""
tools/gap_contract_runner.py — Strict Spec Gap Contract Test Runner
Delegates to pure-Vir native runner bin/vir-test (VIRC-ISS-0050 / VIRC-PLN-0029 Phase 2).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIR_TEST = ROOT / "bin" / "vir-test"

if not VIR_TEST.is_file():
    virc = ROOT / "bin" / "virc"
    subprocess.run([str(virc), str(ROOT / "tools/vir-test/src/main.vri"), "-o", str(VIR_TEST)], check=True)

sys.exit(subprocess.run([str(VIR_TEST)] + sys.argv[1:], cwd=ROOT).returncode)
