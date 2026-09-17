#!/usr/bin/env python3
"""Compile and execute UTF-8 probes with a native virc binary, byte-exact."""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCES = (
    "utf8_vietnamese_string.vri",
    "utf8_chinese_string.vri",
    "utf8_comment_and_string.vri",
    "utf8_escaped_quote.vri",
    "utf8_mixed_literals.vri",
    "utf8_edge_strings.vri",
    "utf8_identifier_comment.vri",
    "utf8_include/main.vri",
    "utf8_import/main.vri",
)


def expected_bytes(source: Path):
    text = source.read_text(encoding="utf-8")
    block = re.search(r"# EXPECT_START\n(.*?)# EXPECT_END", text, re.DOTALL)
    if block:
        lines = [line.removeprefix("# ") for line in block.group(1).splitlines()]
        return ("\n".join(lines) + "\n").encode("utf-8")
    single = re.search(r"^# EXPECT: (.*)$", text, re.MULTILINE)
    if not single:
        raise ValueError(f"No expectation in {source}")
    return (single.group(1) + "\n").encode("utf-8")


def run(argv):
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)


def main():
    if len(sys.argv) != 2:
        print("Usage: utf8_native_probe.py /path/to/virc", file=sys.stderr)
        return 2
    compiler = Path(sys.argv[1]).resolve()
    if not compiler.is_file():
        print(f"Compiler does not exist: {compiler}", file=sys.stderr)
        return 2
    failures = 0
    with tempfile.TemporaryDirectory(prefix="vir_utf8_native_", dir="/private/tmp") as temp:
        for index, name in enumerate(SOURCES):
            source = ROOT / name
            output = Path(temp) / f"probe_{index}"
            compiled = run([str(compiler), str(source), "-o", str(output)])
            if compiled.returncode != 0 or not output.is_file():
                print(f"FAIL {name}: compiler exit={compiled.returncode}")
                failures += 1
                continue
            executed = run([str(output)])
            expected = expected_bytes(source)
            ok = executed.returncode == 0 and executed.stdout == expected
            print(f"{'PASS' if ok else 'FAIL'} {name}: exit={executed.returncode} bytes={len(executed.stdout)} expected={len(expected)}")
            if not ok:
                print(f"  got={executed.stdout!r}")
                print(f"  want={expected!r}")
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
