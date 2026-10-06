#!/usr/bin/env python3
"""End-to-end source-origin, rendering, color, and timing regressions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests" / "source_origin_diagnostics"
ANSI = b"\x1b["


@dataclass(frozen=True)
class Check:
    name: str
    source: Path
    codes: tuple[str, ...] = ()
    locations: tuple[tuple[str, int], ...] = ()
    requested_location: tuple[str, int] | None = None
    summary: str = ""
    extra_args: tuple[str, ...] = ("-q",)
    env: dict[str, str] = field(default_factory=dict)
    expect_success: bool = False
    expect_artifact: bool = False
    compile_time_count: int | None = 1
    execution_reports: int | None = None
    compact_entries: int | None = None
    required: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    ansi: bool | None = None
    json_mode: bool = False
    json_diag_count: int | None = None


CHECKS = (
    Check("01 nested include keeps leaf origin", SUITE / "root_nested_e3021.vri",
          ("E3021",), (("tests/source_origin_diagnostics/fixtures/leaf_e3021.vri", 4),)),
    Check("02 parent origin restored after long include", SUITE / "root_after_include_e3021.vri",
          ("E3021",), (("tests/source_origin_diagnostics/root_after_include_e3021.vri", 5),)),
    Check("03 pre-expanded marker maps logical source", SUITE / "preexpanded_e3021.vri",
          ("E3021",), (("virtual/original_leaf.vri", 42),)),
    Check("04 parser error in included leaf", SUITE / "root_parser_error.vri",
          ("E1001",), (("tests/source_origin_diagnostics/fixtures/leaf_parser_error.vri", 1),)),
    Check("05 lexer error in included leaf", SUITE / "root_lexer_error.vri",
          ("E0001",), (("tests/source_origin_diagnostics/fixtures/leaf_lexer_error.vri", 2),)),
    Check("06 selective import alias keeps definition origin", SUITE / "root_import_alias_e3021.vri",
          ("E3021",), (("tests/source_origin_diagnostics/fixtures/import_origin.vri", 3),)),
    Check("07 diagnostics retain two distinct files", SUITE / "root_two_files_e3021.vri",
          ("E3021", "E3021"), (("tests/source_origin_diagnostics/fixtures/first_error.vri", 3),
                               ("tests/source_origin_diagnostics/fixtures/second_error.vri", 3)),
          execution_reports=2),
    Check("08 quoted UTF-8 and whitespace include path", SUITE / "root_utf8_space_include.vri",
          ("E3021",), (("tests/source_origin_diagnostics/fixtures/nguon utf8.vri", 3),)),
    Check("09 missing include points to parent directive", SUITE / "include_missing.vri",
          ("E2102",), requested_location=("tests/source_origin_diagnostics/include_missing.vri", 1)),
    Check("10 root source has stable location", SUITE / "root_plain_e3021.vri",
          ("E3021",), (("tests/source_origin_diagnostics/root_plain_e3021.vri", 3),)),
    Check("11 origin returns to root after selective import", SUITE / "root_after_import_e3021.vri",
          ("E3021", "E3021"), (("tests/source_origin_diagnostics/fixtures/import_origin.vri", 3),
                               ("tests/source_origin_diagnostics/root_after_import_e3021.vri", 5)),
          execution_reports=2),
    Check("12 compiler bundle marker resolves canonical module", SUITE / "compiler_bundle_probe.vri",
          ("E3021",), (("stdlib/vir/compiler/sem_pass6_typecheck.vri", 1736),),
          absent=("compiler_bundle_probe.vri:1736", "virc-expanded.vri")),
    Check("13 one diagnostic uses detailed mode once", SUITE / "root_plain_e3021.vri",
          ("E3021",), summary="virc: 1 error(s), 0 warning(s)", execution_reports=1,
          required=("Analysis", "Possible Causes", "Action")),
    Check("14 two diagnostics remain detailed", SUITE / "two_errors.vri",
          ("E3021", "E3021"), (("tests/source_origin_diagnostics/two_errors.vri", 3),
                               ("tests/source_origin_diagnostics/two_errors.vri", 5)),
          summary="virc: 2 error(s), 0 warning(s)", execution_reports=2),
    Check("15 three diagnostics switch to compact mode", SUITE / "multi_error.vri",
          ("E3021", "E3021", "E3021"), summary="virc: 3 error(s), 0 warning(s)",
          execution_reports=0, compact_entries=3, absent=("Possible Causes", "Action")),
    Check("16 compact mixed severity preserves counts", SUITE / "mixed_warning_errors.vri",
          ("E3021", "E3021", "W4001"), summary="virc: 2 error(s), 1 warning(s)",
          execution_reports=0, compact_entries=3),
    Check("17a color always emits ANSI", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("-q", "--color=always"), ansi=True),
    Check("17b color never emits clean text", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("-q", "--color=never"), ansi=False),
    Check("17c redirected auto output is clean", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("-q", "--color=auto"), ansi=False),
    Check("17d NO_COLOR disables auto color", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("-q", "--color=auto"), env={"NO_COLOR": "1"}, ansi=False),
    Check("18a successful compile emits one finite time", SUITE / "success.vri",
          expect_success=True, expect_artifact=True),
    Check("18b include failure emits one finite time", SUITE / "include_missing.vri", ("E2102",)),
    Check("18c lexer failure emits one finite time", SUITE / "root_lexer_error.vri", ("E0001",)),
    Check("18d parser failure emits one finite time", SUITE / "root_parser_error.vri", ("E1001",)),
    Check("18e semantic failure emits one finite time", SUITE / "root_plain_e3021.vri", ("E3021",)),
    Check("19 verbose phase timings preserve rendering", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("--timings", "--color=never"), required=("Phase timings",), execution_reports=1),
    Check("20 machine-readable output is clean and timed", SUITE / "root_plain_e3021.vri", ("E3021",),
          extra_args=("-q", "--json"), ansi=False, json_mode=True, compile_time_count=None),
    Check("21 success machine-readable output", SUITE / "success.vri",
          expect_success=True, expect_artifact=True, extra_args=("-q", "--json"),
          ansi=False, json_mode=True, compile_time_count=None),
    Check("22 multi-error machine-readable output", SUITE / "two_errors.vri", ("E3021",),
          extra_args=("-q", "--json"), ansi=False, json_mode=True, json_diag_count=2, compile_time_count=None),
    Check("23 parser error machine-readable output", SUITE / "root_parser_error.vri", ("E1001",),
          extra_args=("-q", "--json"), ansi=False, json_mode=True, compile_time_count=None),
    Check("24 lexer error machine-readable output", SUITE / "root_lexer_error.vri", ("E0001",),
          extra_args=("-q", "--json"), ansi=False, json_mode=True, compile_time_count=None),
)


def locations_from(output: str) -> list[tuple[str, int, int]]:
    found: list[tuple[str, int, int]] = []
    detailed = re.compile(
        r"^File\s*:\s*(.+?)\s*$\n^Line\s*:\s*(\d+)\s*$"
        r"(?:\n^Column\s*:\s*(\d+)\s*$)?", re.MULTILINE)
    for match in detailed.finditer(output):
        found.append((match.group(1).strip(), int(match.group(2)), int(match.group(3) or 0)))
    compact = re.compile(r"^\[(.+):(\d+):(\d+)\]\s+\[[EWI]\d{4}\]", re.MULTILINE)
    for match in compact.finditer(output):
        found.append((match.group(1).strip(), int(match.group(2)), int(match.group(3))))
    return found


def validate_json(output: str, check: Check) -> list[str]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON output: {exc}"]
    failures: list[str] = []
    if not isinstance(payload, dict):
        return ["machine-readable output must be one JSON object"]
    if check.expect_success:
        if payload.get("success") is not True:
            failures.append(f"expected success:true in JSON, got: {payload.get('success')!r}")
        if payload.get("diagnostics") != []:
            failures.append(f"expected empty diagnostics in JSON, got: {payload.get('diagnostics')!r}")
    else:
        if payload.get("code") not in check.codes:
            failures.append(f"JSON code mismatch: {payload.get('code')!r}")
        msg = payload.get("message")
        if not isinstance(msg, str) or not msg.strip():
            failures.append("JSON message missing or empty")
        span = payload.get("primary_span") or {}
        if not isinstance(span, dict) or not span.get("file"):
            failures.append("JSON primary_span.file missing")
        for key in ("start_line", "start_column", "end_line", "end_column"):
            if not isinstance(span.get(key), int) or span[key] <= 0:
                failures.append(f"JSON primary_span.{key} missing or non-positive")
        if isinstance(msg, str) and span.get("start_line"):
            line_match = re.search(r"\bline\s+(\d+)\b", msg, re.IGNORECASE)
            if line_match and int(line_match.group(1)) != span["start_line"]:
                failures.append(f"message line {line_match.group(1)} contradicts primary_span.start_line {span['start_line']}")
    if check.json_diag_count is not None:
        diags = payload.get("diagnostics") or []
        if len(diags) != check.json_diag_count:
            failures.append(f"expected {check.json_diag_count} items in diagnostics array, got {len(diags)}")
    elapsed = payload.get("compile_time_ms")
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        failures.append("JSON compile_time_ms missing, non-finite, or negative")
    return failures


def run_check(compiler: Path, check: Check, verbose: bool) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="vir-source-origin-") as temp_dir:
        artifact = Path(temp_dir) / "artifact"
        env = dict(os.environ)
        env.update(check.env)
        proc = subprocess.run(
            [str(compiler), str(check.source), "-o", str(artifact), *check.extra_args],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=90, check=False)
        raw = proc.stdout + proc.stderr
        output = raw.decode("utf-8", errors="replace")
        failures: list[str] = []

        if check.expect_success != (proc.returncode == 0):
            failures.append(f"unexpected exit code {proc.returncode}")
        if check.expect_artifact != artifact.exists():
            failures.append(f"artifact existence was {artifact.exists()}, expected {check.expect_artifact}")

        if check.json_mode:
            failures.extend(validate_json(output, check))
        else:
            plain_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
            for code in set(check.codes):
                actual = plain_output.count(f"[{code}]")
                expected = check.codes.count(code)
                if actual != expected:
                    failures.append(f"{code} count was {actual}, expected {expected}")

            actual_locations = locations_from(output)
            for suffix, line in check.locations:
                matches = [item for item in actual_locations
                           if item[0].replace("\\", "/").endswith(suffix)
                           and item[1] == line and item[2] > 0]
                if not matches:
                    failures.append(f"missing original location {suffix}:{line}:<positive-column>")
            if check.locations and ("<expanded>" in output or "virc-expanded.vri" in output):
                failures.append("expanded location leaked into primary diagnostic output")

            if check.requested_location:
                suffix, line = check.requested_location
                match = re.search(r"requested at\s+(.+?)\s*:\s*(\d+)", output, re.DOTALL)
                if not match:
                    failures.append("missing requested-at parent location")
                else:
                    path = match.group(1).strip().replace("\\", "/")
                    if not path.endswith(suffix) or int(match.group(2)) != line:
                        failures.append(f"requested-at location was {path}:{match.group(2)}")

            if check.summary and output.count(check.summary) != 1:
                failures.append(f"summary {check.summary!r} did not appear exactly once")
            report_count = output.count("EXECUTION REPORT")
            if check.execution_reports is not None and report_count != check.execution_reports:
                failures.append(f"EXECUTION REPORT count was {report_count}, expected {check.execution_reports}")
            if check.compact_entries is not None:
                count = len(re.findall(r"^\[.+:\d+:\d+\]\s+\[[EWI]\d{4}\]", output, re.MULTILINE))
                if count != check.compact_entries:
                    failures.append(f"compact entry count was {count}, expected {check.compact_entries}")
            for needle in check.required:
                if needle not in output:
                    failures.append(f"missing required text {needle!r}")
            for needle in check.absent:
                if needle in output:
                    failures.append(f"unexpected text {needle!r}")

            if check.compile_time_count is not None:
                times = re.findall(r"^Compile time:\s*([0-9]+(?:\.[0-9]+)?)\s*ms\s*$", output, re.MULTILINE)
                if len(times) != check.compile_time_count:
                    failures.append(f"Compile time count was {len(times)}, expected {check.compile_time_count}")
                elif any(not math.isfinite(float(value)) or float(value) < 0 for value in times):
                    failures.append("Compile time value was non-finite or negative")

        if check.ansi is True and ANSI not in raw:
            failures.append("ANSI color was required but absent")
        if check.ansi is False and ANSI in raw:
            failures.append("ANSI color was forbidden but present")
        if verbose or failures:
            print(f"--- {check.name}: raw compiler output ---")
            print(output.rstrip())
        return not failures, "; ".join(failures) if failures else "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default="./bin/virc")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    compiler = Path(args.compiler)
    if not compiler.is_absolute():
        compiler = (ROOT / compiler).resolve()
    if not compiler.is_file():
        parser.error(f"compiler not found: {compiler}")
    print(f"compiler: {compiler}")
    print(f"sha256:   {hashlib.sha256(compiler.read_bytes()).hexdigest()}")
    passed = 0
    for check in CHECKS:
        ok, reason = run_check(compiler, check, args.verbose)
        print(f"{'PASS' if ok else 'FAIL'}: {check.name}: {reason}")
        passed += int(ok)
    print(f"summary: {passed}/{len(CHECKS)} passed")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
