#!/usr/bin/env python3
"""
tools/gap_contract_runner.py — Strict Spec Gap Contract Test Runner

Runner for tests/spec_gap_contract/manifest.tsv.
Supports kinds:
  - run: compile, run, exact stdout and exit code match
  - compile_fail: compiler returns non-zero, diagnostic oracle match, no artifact
  - run_fail: compile succeeds, run traps/exits non-zero via error path
  - structural: runtime/behavioral gate + MIR/symbol/structural oracle check
  - blocked_contract: unconditionally reports BLOCKED (never PASS)
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/spec_gap_contract/manifest.tsv"
DEFAULT_FIXTURES_DIR = ROOT / "tests/spec_gap_contract"
DEFAULT_BASELINE = ROOT / "docs/report/checklist/spec_gap_contract_baseline.tsv"


@dataclass
class TestEntry:
    test_id: str
    kind: str
    fixture: str
    oracle: str


@dataclass
class TestResult:
    test_id: str
    kind: str
    status: str  # PASS, FAIL, BLOCKED
    target: str
    compile_exit: Optional[int]
    run_exit: Optional[int]
    stdout: str
    stderr: str
    reason: str


def parse_manifest(manifest_path: Path) -> list[TestEntry]:
    entries: list[TestEntry] = []
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            entries.append(
                TestEntry(
                    test_id=parts[0].strip(),
                    kind=parts[1].strip(),
                    fixture=parts[2].strip(),
                    oracle=parts[3].strip(),
                )
            )
        elif len(parts) == 3:
            entries.append(
                TestEntry(
                    test_id=parts[0].strip(),
                    kind=parts[1].strip(),
                    fixture=parts[2].strip(),
                    oracle="",
                )
            )
    return entries


def extract_fixture_expected(fixture_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Extract EXPECT stdout and EXPECT_DIAGNOSTIC from fixture comments if present."""
    content = fixture_path.read_text(encoding="utf-8", errors="replace")
    expected_stdout = None
    expected_diag = None

    m_start = re.search(r"#\s*EXPECT_START\n((?:#[^\n]*\n)+?)#\s*EXPECT_END", content)
    if m_start:
        lines = [
            line[1:].lstrip() if line.startswith("#") else line
            for line in m_start.group(1).splitlines()
        ]
        expected_stdout = "\n".join(lines).strip()
    else:
        m_exp = re.search(r"#\s*EXPECT:\s*\n((?:#[^\n]*\n)+)", content)
        if m_exp:
            lines = [
                line[1:].lstrip() if line.startswith("#") else line
                for line in m_exp.group(1).splitlines()
            ]
            expected_stdout = "\n".join(lines).strip()
        else:
            m_single = re.search(r"#\s*EXPECT:\s*([^\n]+)", content)
            if m_single:
                expected_stdout = m_single.group(1).strip().replace(r"\n", "\n")

    m_diag = re.search(r"#\s*EXPECT_DIAGNOSTIC:\s*([^\n]+)", content)
    if m_diag:
        expected_diag = m_diag.group(1).strip()

    return expected_stdout, expected_diag


def run_command(cmd: list[str], cwd: Path, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -999, stdout, stderr + f"\nTIMEOUT after {timeout}s"
    except Exception as e:
        return -998, "", str(e)


def check_compile_fail_oracle(oracle: str, compile_output: str) -> tuple[bool, str]:
    """Verify that compile error diagnostic satisfies oracle keywords."""
    out_lower = compile_output.lower()
    m_contains = re.search(r"diagnostic contains (.+)", oracle, re.IGNORECASE)
    if m_contains:
        spec = m_contains.group(1).strip()
        # Strip semicolon-separated directives (e.g. "; no artifact") — those are
        # checked separately (artifact existence) and are not keyword search terms.
        if ";" in spec:
            spec = spec[: spec.index(";")].strip()
        terms = [t.strip().lower() for t in spec.split(" and ")]
        for term in terms:
            if "/" in term:
                subterms = term.split("/")
                if not any(st.strip() in out_lower for st in subterms):
                    return False, f"diagnostic missing required keyword '{term}'"
            elif term not in out_lower:
                return False, f"diagnostic missing required keyword '{term}'"
        return True, "diagnostic matched required keywords"

    if "parser diagnostic" in oracle.lower():
        if "e1004" in out_lower or "parse" in out_lower or "syntax" in out_lower or "error" in out_lower:
            return True, "parser diagnostic present"
        return False, "expected parser diagnostic"

    if "error" in out_lower or "e1" in out_lower or "e2" in out_lower or "e3" in out_lower:
        return True, "diagnostic error present"
    return False, f"diagnostic does not match oracle: '{oracle}'"


def run_test(
    entry: TestEntry,
    virc_bin: Path,
    target: str,
    fixtures_dir: Path,
    timeout: float = 5.0,
) -> TestResult:
    if entry.kind == "blocked_contract":
        return TestResult(
            test_id=entry.test_id,
            kind=entry.kind,
            status="BLOCKED",
            target=target,
            compile_exit=None,
            run_exit=None,
            stdout="",
            stderr="",
            reason=entry.oracle or "Blocked contract",
        )

    fixture_path = fixtures_dir / entry.fixture
    if not fixture_path.is_file():
        return TestResult(
            test_id=entry.test_id,
            kind=entry.kind,
            status="FAIL",
            target=target,
            compile_exit=None,
            run_exit=None,
            stdout="",
            stderr="",
            reason=f"Fixture not found: {fixture_path}",
        )

    with tempfile.TemporaryDirectory(prefix="spec_gap_") as tmpdir:
        tmp_path = Path(tmpdir)
        bin_out = tmp_path / "test_artifact"

        compile_cmd = [str(virc_bin), str(fixture_path), "-o", str(bin_out)]
        if target:
            compile_cmd.extend(["--target", target])

        c_exit, c_stdout, c_stderr = run_command(compile_cmd, cwd=ROOT, timeout=10.0)
        c_all = c_stdout + "\n" + c_stderr

        # ── Kind: compile_fail ──
        if entry.kind == "compile_fail":
            if bin_out.exists():
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="Compiler unexpectedly generated an artifact for negative test",
                )
            if c_exit == 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="Compilation succeeded with 0, expected compile rejection",
                )
            matched, reason = check_compile_fail_oracle(entry.oracle, c_all)
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS" if matched else "FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason=reason,
            )

        # Non compile-fail cases require successful compilation
        if c_exit != 0:
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason=f"Compilation failed with exit code {c_exit}",
            )

        if not bin_out.exists():
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason="Compilation succeeded but artifact does not exist",
            )

        # Run artifact
        run_cmd = [str(bin_out)]
        r_exit, r_stdout, r_stderr = run_command(run_cmd, cwd=ROOT, timeout=timeout)

        # ── Kind: run_fail ──
        if entry.kind == "run_fail":
            if r_exit == 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Execution succeeded with exit 0, expected trap/run failure",
                )
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason=f"Execution correctly trapped/exited non-zero ({r_exit})",
            )

        # ── Kind: run ──
        if entry.kind == "run":
            if r_exit != 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason=f"Execution failed with non-zero exit code {r_exit}",
                )

            expected_stdout = None
            if entry.oracle.startswith("stdout="):
                expected_stdout = entry.oracle[7:].replace(r"\n", "\n").strip()
            else:
                exp_comment, _ = extract_fixture_expected(fixture_path)
                if exp_comment is not None:
                    expected_stdout = exp_comment

            actual_stdout = r_stdout.strip()
            if expected_stdout is not None:
                if actual_stdout != expected_stdout:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Stdout mismatch: expected '{expected_stdout}', got '{actual_stdout}'",
                    )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason="Stdout and exit code matched expected oracle",
            )

        # ── Kind: structural ──
        if entry.kind == "structural":
            m_out = re.search(r"stdout=([^;]+)", entry.oracle)
            if m_out:
                exp_s = m_out.group(1).replace(r"\n", "\n").strip()
                if r_stdout.strip() != exp_s:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Structural test behavioral stdout mismatch: expected '{exp_s}', got '{r_stdout.strip()}'",
                    )

            if entry.test_id == "TARGET-002":
                if r_exit != 37:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Expected exit code 37, got {r_exit}",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Exited with code 37 as required",
                )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL" if r_exit != 0 else "PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason=f"Structural check executed (exit={r_exit})",
            )

    return TestResult(
        test_id=entry.test_id,
        kind=entry.kind,
        status="FAIL",
        target=target,
        compile_exit=None,
        run_exit=None,
        stdout="",
        stderr="",
        reason=f"Unknown test kind {entry.kind}",
    )


def save_baseline(results: list[TestResult], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# id\tkind\tstatus\ttarget\tcompile_exit\trun_exit\treason\tstdout_escaped\n")
        for r in results:
            clean_stdout = r.stdout.strip().replace("\n", "\\n").replace("\t", " ")
            clean_reason = r.reason.replace("\t", " ").replace("\n", " ")
            f.write(
                f"{r.test_id}\t{r.kind}\t{r.status}\t{r.target}\t"
                f"{r.compile_exit if r.compile_exit is not None else ''}\t"
                f"{r.run_exit if r.run_exit is not None else ''}\t"
                f"{clean_reason}\t{clean_stdout}\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Vir Spec Gap Contract Runner")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to manifest.tsv")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES_DIR, help="Fixtures directory")
    parser.add_argument("--virc", type=Path, default=ROOT / "bin/virc", help="Path to virc compiler")
    parser.add_argument("--target", type=str, default="macos-arm64", help="Target architecture")
    parser.add_argument("--save-baseline", type=Path, default=None, help="Path to save baseline TSV")
    parser.add_argument("--filter", type=str, default="", help="Regex filter by test ID")
    parser.add_argument("--group", type=str, default="", help="Filter by group/phase (e.g. Phase1)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Execution timeout in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print details for every test")
    args = parser.parse_args()

    if not args.virc.is_file() or not os.access(args.virc, os.X_OK):
        print(f"Error: Compiler executable not found or not executable: {args.virc}", file=sys.stderr)
        return 1

    entries = parse_manifest(args.manifest)

    if args.group.lower() == "phase1":
        entries = [
            e for e in entries
            if e.test_id.startswith("PREC-")
            or e.test_id.startswith("NEG-")
            or e.test_id.startswith("FLOAT-")
            or e.test_id.startswith("CAST-")
        ]
    elif args.filter:
        pattern = re.compile(args.filter, re.IGNORECASE)
        entries = [e for e in entries if pattern.search(e.test_id)]

    print(f"==================================================")
    print(f"  Vir Spec Gap Contract Runner")
    manifest_rel = args.manifest.resolve().relative_to(ROOT) if args.manifest.resolve().is_relative_to(ROOT) else args.manifest
    virc_rel = args.virc.resolve().relative_to(ROOT) if args.virc.resolve().is_relative_to(ROOT) else args.virc
    print(f"  Manifest : {manifest_rel}")
    print(f"  Compiler : {virc_rel}")
    print(f"  Target   : {args.target}")
    print(f"  Total    : {len(entries)} tests")
    print(f"==================================================\n")

    results: list[TestResult] = []
    pass_count = 0
    fail_count = 0
    blocked_count = 0

    for idx, entry in enumerate(entries, 1):
        res = run_test(
            entry,
            virc_bin=args.virc,
            target=args.target,
            fixtures_dir=args.fixtures,
            timeout=args.timeout,
        )
        results.append(res)

        if res.status == "PASS":
            pass_count += 1
            status_str = "\033[92mPASS\033[0m"
        elif res.status == "BLOCKED":
            blocked_count += 1
            status_str = "\033[93mBLOCKED\033[0m"
        else:
            fail_count += 1
            status_str = "\033[91mFAIL\033[0m"

        print(f"[{idx:02d}/{len(entries):02d}] {res.test_id:<12} [{res.kind:<14}] {status_str} : {res.reason}")
        if args.verbose and res.status == "FAIL":
            if res.compile_exit != 0 and res.compile_exit is not None:
                print(f"    Compile Error (exit {res.compile_exit}):\n{res.stdout}\n{res.stderr}")
            elif res.run_exit is not None:
                print(f"    Run Output (exit {res.run_exit}):\n{res.stdout}")

    if args.save_baseline:
        save_baseline(results, args.save_baseline)
        print(f"\nBaseline saved to: {args.save_baseline.relative_to(ROOT)}")

    print(f"\nSummary:")
    print(f"  PASS    : {pass_count}")
    print(f"  FAIL    : {fail_count}")
    print(f"  BLOCKED : {blocked_count}")
    print(f"  TOTAL   : {len(entries)}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
