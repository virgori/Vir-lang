#!/usr/bin/env python3
"""Regression checks for the Vir compiler calendar-version contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.run(
        [sys.executable, "tools/bump_virc_version.py", "--check"],
        cwd=ROOT,
        check=True,
    )
    record = json.loads((ROOT / "compiler/version.json").read_text(encoding="utf-8"))
    public = record["public_version"]
    if record["channel"] == "official":
        assert re.fullmatch(r"[0-9]{4}\.[1-9][0-9]*", public)
        assert record["internal_patch"] == 0
    else:
        assert re.fullmatch(r"[0-9]{4}\.[1-9][0-9]*\.[1-9][0-9]*", public)
        assert record["internal_patch"] >= 1

    binary = ROOT / "bin/virc"
    if binary.is_file():
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert lines[-1] == f"virc {public} (self-hosted)"
        assert f"v{public}" not in result.stdout
        assert f"{public} —" in result.stdout
    print(f"PASS: Vir compiler version policy ({public}, {record['channel']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
