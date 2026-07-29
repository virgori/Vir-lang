#!/usr/bin/env python3
"""Compile and execute the Stage-1 bootstrap regression manifest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests" / "bootstrap_codegen" / "manifest.json"


def run(
    command: list[str],
    *,
    timeout: float,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compiler",
        action="append",
        required=True,
        type=Path,
        help="compiler executable; repeat to compare multiple bootstrap stages",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    compilers = [path.resolve() for path in args.compiler]
    for compiler in compilers:
        if not compiler.is_file():
            print(f"missing compiler: {compiler}", file=sys.stderr)
            return 2

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    tests = data["tests"]
    failures: list[str] = []
    passed = 0

    with tempfile.TemporaryDirectory(prefix="vir-bootstrap-regression-") as tmp:
        tmpdir = Path(tmp)
        for test in tests:
            source = args.manifest.parent / test["file"]
            expected_stdout = test["stdout"].encode()
            expected_exit = test["exit"]
            unsigned_outputs: list[bytes] = []
            test_failed = False

            for stage, compiler in enumerate(compilers, 1):
                binary = tmpdir / f"case-{stage}"
                compiled = run(
                    [str(compiler), str(source), "-o", str(binary)],
                    timeout=args.timeout,
                )
                if compiled.returncode != 0 or not binary.is_file():
                    failures.append(
                        f"{test['file']}: compiler {stage} failed "
                        f"(rc={compiled.returncode}, stderr={compiled.stderr.decode(errors='replace')!r})"
                    )
                    test_failed = True
                    break

                unsigned_outputs.append(binary.read_bytes())
                os.chmod(binary, 0o755)
                signed = run(
                    ["codesign", "-s", "-", "-f", str(binary)],
                    timeout=args.timeout,
                )
                if signed.returncode != 0:
                    failures.append(
                        f"{test['file']}: codesign failed "
                        f"(stderr={signed.stderr.decode(errors='replace')!r})"
                    )
                    test_failed = True
                    break

                executed = run(
                    [str(binary), "fixture-argument"],
                    timeout=args.timeout,
                )
                if executed.returncode != expected_exit or executed.stdout != expected_stdout:
                    failures.append(
                        f"{test['file']}: stage {stage} expected "
                        f"rc={expected_exit}, stdout={expected_stdout!r}; got "
                        f"rc={executed.returncode}, stdout={executed.stdout!r}, "
                        f"stderr={executed.stderr!r}"
                    )
                    test_failed = True
                    break

            if not test_failed and any(
                output != unsigned_outputs[0] for output in unsigned_outputs[1:]
            ):
                failures.append(f"{test['file']}: compiler stages emitted different binaries")
                test_failed = True

            if not test_failed:
                passed += 1

    for failure in failures:
        print(f"FAIL {failure}")
    print(f"bootstrap regression: {passed}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
