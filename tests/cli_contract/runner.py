#!/usr/bin/env python3
"""Executed CLI contracts; --capture-baseline preserves raw classic output.

Run through run_tests.sh (group 18). Never inherits a developer's UI preference.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import errno
import fcntl
import pty
import select
import struct
from pathlib import Path
import re
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/cli_contract/success.vri"
VIRC = Path(os.environ.get("VIRC", ROOT / "bin/virc"))
BASELINE = ROOT / "tests/cli_contract/classic_baseline.json"
FAILURE = ROOT / "tests/cli_contract/failure.vri"
FAILURE_BASELINE = ROOT / "tests/cli_contract/classic_failure_baseline.json"
VIRC_VERSION = json.loads((ROOT / "compiler/version.json").read_text())["public_version"]


def invoke(args, *, env=None, cwd=ROOT):
    child_env = dict(os.environ, VIRC_UI="classic", NO_COLOR="1")
    if env:
        for name, value in env.items():
            if value is None:
                child_env.pop(name, None)
            else:
                child_env[name] = value
    return subprocess.run([str(VIRC), *map(str, args)], cwd=cwd, env=child_env,
                          capture_output=True, timeout=60)


def normalized(data):
    # Only clock values and caller-owned output paths are nondeterministic.
    data = re.sub(rb"Compile time: [0-9.]+ ms", b"Compile time: <duration> ms", data)
    return re.sub(
        rb"  v?[0-9]+\.[0-9]+(?:\.[0-9]+)? \xe2\x80\x94",
        b"  <version> \xe2\x80\x94",
        data,
    )


def invoke_pty(args, *, env=None, columns=80, executable=None):
    """Only stderr is a TTY: verifies detection isn't accidentally fd 1."""
    child_env = dict(os.environ, VIRC_UI="classic", TERM="xterm", NO_COLOR="1")
    child_env.pop("CI", None)
    for name, value in (env or {}).items():
        if value is None:
            child_env.pop(name, None)
        else:
            child_env[name] = value
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))
    # Disable the terminal driver's LF -> CRLF translation; inspect renderer bytes.
    attrs = termios.tcgetattr(slave)
    attrs[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    process = subprocess.Popen([str(executable or VIRC), *map(str, args)],
                               cwd=ROOT, env=child_env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=slave)
    os.close(slave)
    data = bytearray()
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if not ready:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            data.extend(chunk)
        else:
            process.kill()
            raise TimeoutError("PTY child did not complete")
        stdout = process.stdout.read()
        return subprocess.CompletedProcess(process.args, process.wait(timeout=5), stdout, bytes(data))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        os.close(master)


class CliContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vir-cli-contract-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "program"

    def compile(self, flags=(), *, env=None):
        # A new inode avoids Darwin's executable signature/page-cache reuse.
        self.output.unlink(missing_ok=True)
        return invoke([FIXTURE.relative_to(ROOT), *flags, "-o", self.output], env=env)

    def test_string_spans_preserve_decoded_empty_payload(self):
        with tempfile.TemporaryDirectory(prefix="vir-string-span-") as directory:
            source = Path(directory) / "strings.vri"
            output = Path(directory) / "strings"
            source.write_text('func main:\n    print 11\n    print ""\n    print "hello"\n    print 22\nend.\n')
            compiled = invoke([source, "-q", "-o", output])
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(output)], capture_output=True, timeout=5)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(executed.stdout, b"11\n\nhello\n22\n")

    def test_cfg_join_liveness_all_optimization_levels(self):
        source = ROOT / "tests/cli_contract/cfg_join_liveness.vri"
        for level in range(4):
            with self.subTest(optimization=level):
                output = Path(self.temp.name) / f"cfg-join-O{level}"
                compiled = invoke([source, "-q", f"-O{level}", "-o", output])
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                executed = subprocess.run([str(output)], capture_output=True, timeout=5)
                self.assertEqual(executed.returncode, 0, executed.stderr)
                self.assertEqual(executed.stdout, b"13\n17\n100\n109\n")

    def test_cfg_liveness_intervals_all_optimization_levels(self):
        source = ROOT / "tests/cli_contract/cfg_liveness_intervals.vri"
        for level in range(4):
            with self.subTest(optimization=level):
                output = Path(self.temp.name) / f"cfg-intervals-O{level}"
                compiled = invoke([source, "-q", f"-O{level}", "-o", output])
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                executed = subprocess.run([str(output)], capture_output=True, timeout=5)
                self.assertEqual(executed.returncode, 0, executed.stderr)
                self.assertEqual(executed.stdout, b"0\n5\n1\n" * 4)

    def test_compiler_fact_index_growth_update_and_reset(self):
        source = ROOT / "tests/cli_contract/ide_fact_index.vri"
        compiled = invoke([source, "-q", "-O1", "-o", self.output])
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        executed = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout, b"5000\n10000\n14999\n5000\n0\n1\n1\n7\n")

    def test_gvn_commutative_and_ordered_operand_comparisons(self):
        # Compile the actual helper bodies without pulling unrelated MIR passes
        # into this structural runtime test.
        helpers = []
        for name, candidate in (
            ("mir_gvn_expr_same", ROOT / "compiler/src/ir/mir/opt/gvn.vri"),
            ("mir_gvn_commutative", ROOT / "compiler/src/ir/mir/opt/gvn.vri"),
            ("mir_opnd_is_same", ROOT / "compiler/src/ir/mir/opt/rewrite.vri"),
        ):
            if not candidate.is_file():
                candidate = ROOT / "compiler/src/ir/mir/mir_opt.vri"
            if not candidate.is_file():
                candidate = ROOT / "stdlib/vir/compiler/mir_opt.vri"
            content = candidate.read_text()
            start = content.index("func " + name + "(")
            end = content.index("\nend.", start) + len("\nend.")
            helpers.append(content[start:end])
        mir_path = ROOT / "compiler/src/ir/mir/mir.vri"
        if not mir_path.is_file():
            mir_path = ROOT / "stdlib/vir/compiler/mir.vri"
        mir = mir_path.read_text()
        for declaration in ("enum MirOp:", "enum MirOperandType:", "entity MirOperand:", "entity MirInstr:"):
            start = mir.index(declaration)
            end = mir.index("\nend.", start) + len("\nend.")
            helpers.append(mir[start:end])
        for name in ("mir_opnd_new", "mir_instr_new", "mir_instr_op", "mir_instr_src1", "mir_instr_src2", "mir_opnd_type", "mir_opnd_vreg_id", "mir_opnd_imm_val", "mir_opnd_block_id", "mir_opnd_vreg", "mir_opnd_imm"):
            start = mir.index("func " + name + "(")
            end = mir.index("\nend.", start) + len("\nend.")
            helpers.append(mir[start:end])
        helpers.insert(0, "extern func native_read_i64(addr: int, offset: int) -> int\nextern func native_write_i64(addr: int, offset: int, value: int)")
        source = Path(self.temp.name) / "gvn-compare.vri"
        source.write_text("\n".join(helpers) + "\n" +
                          (ROOT / "tests/cli_contract/gvn_operand_comparison.vri").read_text())
        compiled = invoke([source, "-q", "-O1", "-o", self.output])
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        executed = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout, b"300000\n")

    def test_parser_structured_code_metadata(self):
        for name, source, code in [
            ("out_parameter", "func bad(out value: int):\nend.\n", "E3045"),
            ("missing_expression", "func main:\n    print -\nend.\n", "E1004"),
        ]:
            fixture = Path(self.temp.name) / (name + ".vri")
            fixture.write_text(source)
            result = invoke(["--json", fixture, "-o", self.output])
            self.assertNotEqual(result.returncode, 0)
            diagnostics = json.loads(result.stdout)["diagnostics"]
            self.assertEqual(diagnostics[0]["code"], code)
            self.assertNotIn("[E", diagnostics[0]["message"])

    def test_classic_raw_baseline(self):
        reference = json.loads(BASELINE.read_text())
        result = self.compile()
        self.assertEqual(result.returncode, reference["exitCode"])
        actual = result.stdout.replace(str(self.output).encode(), b"<artifact>")
        self.assertEqual(normalized(actual).decode(), normalized(reference["stdoutNormalized"].encode()).decode())
        self.assertEqual(normalized(result.stderr).decode(), normalized(reference["stderrNormalized"].encode()).decode())

    def test_classic_failure_baseline(self):
        reference = json.loads(FAILURE_BASELINE.read_text())
        result = invoke([FAILURE.relative_to(ROOT), "-o", self.output])
        self.assertEqual(result.returncode, reference["exitCode"])
        self.assertFalse(self.output.exists())
        self.assertEqual(normalized(result.stdout).decode(), normalized(reference["stdoutNormalized"].encode()).decode())
        self.assertEqual(normalized(result.stderr).decode(), normalized(reference["stderrNormalized"].encode()).decode())

    def test_machine_output_does_not_change_artifact(self):
        classic = self.compile(["-q"])
        self.assertEqual(classic.returncode, 0, classic.stdout + classic.stderr)
        artifact = self.output.read_bytes()
        machine = self.compile(["--json"])
        self.assertEqual(machine.returncode, 0, machine.stdout + machine.stderr)
        self.assertTrue(json.loads(machine.stdout)["success"])
        self.assertEqual(self.output.read_bytes(), artifact)

    def test_ui_selector_precedence(self):
        cases = (([], None, False), ([], "classic", False), ([], "modern", True),
                 (["--ui=classic"], "modern", False),
                 (["--ui=modern"], "classic", True),
                 (["--ui=modern", "--ui=classic"], "modern", False),
                 (["--ui=classic", "--ui=modern"], "classic", True),
                 (["--ui=classic"], "invalid-overridden", False))
        for flags, environment, modern in cases:
            with self.subTest(flags=flags, environment=environment):
                result = self.compile(flags, env={"VIRC_UI": environment})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if modern:
                    self.assertEqual(result.stdout, b"")
                    self.assertTrue(result.stderr.startswith("╭".encode("utf-8")), result.stderr)
                    self.assertNotIn(b"Compile time:", result.stderr)
                else:
                    self.assertEqual(result.stderr, b"")
                    self.assertIn(b"virc: tokenizing", result.stdout)

    def test_ui_invalid_values_fail_before_pipeline(self):
        for value in ("", "Modern", "MODERN", "invalid"):
            for flags, environment in (([f"--ui={value}"], "classic"), ([], value)):
                with self.subTest(flags=flags, environment=environment):
                    result = self.compile(flags, env={"VIRC_UI": environment})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.output.exists())
                    self.assertIn(b"requires classic or modern", result.stdout + result.stderr)
                    self.assertNotIn(b"tokenizing", result.stdout + result.stderr)
            result = self.compile([f"--ui={value}", "--json"])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["error_kind"], "argument")
            self.assertEqual(result.stderr, b"")

    def test_modern_artifact_and_json_equivalence(self):
        for level in range(4):
            classic = self.compile([f"-O{level}", "-q", "--ui=classic"])
            self.assertEqual(classic.returncode, 0)
            artifact = self.output.read_bytes()
            modern = self.compile([f"-O{level}", "--ui=modern"])
            self.assertEqual(modern.returncode, 0, modern.stdout + modern.stderr)
            self.assertEqual(self.output.read_bytes(), artifact)
            self.assertEqual(subprocess.check_output([self.output]).strip(), b"23")
        classic = self.compile(["--ui=classic", "--json"])
        modern = self.compile(["--ui=modern", "--json"], env={"VIRC_UI": "modern"})
        left, right = json.loads(classic.stdout), json.loads(modern.stdout)
        for payload in (left, right):
            payload.pop("compile_time_ms", None)
            if "session" in payload and isinstance(payload["session"], dict):
                payload["session"].pop("durationNs", None)
                for phase in payload["session"].get("phases", []):
                    if isinstance(phase, dict):
                        phase.pop("durationNs", None)
        self.assertEqual(left, right)
        self.assertEqual(modern.stderr, b"")

    def test_check_and_ide_modes_do_not_leak_classic_banner(self):
        for flag in ("--check", "--ide-semantic"):
            for ui in ("classic", "modern"):
                with self.subTest(flag=flag, ui=ui):
                    result = self.compile([flag, f"--ui={ui}", "--color=always"])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue(json.loads(result.stdout)["success"])
                    self.assertEqual(result.stderr, b"")
                    self.assertFalse(self.output.exists())

    def test_modern_phase_boundaries_are_plain_and_finalized_once(self):
        result = self.compile(["--ui=modern", "--color=never"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, b"")
        lines = result.stderr.decode().splitlines()
        # 1. No [OK]
        self.assertNotIn("[OK]", result.stderr.decode())
        # 2. No duplicate Reading stage (Reading only in banner intro)
        self.assertNotIn("✓ Reading", result.stderr.decode())
        self.assertEqual(sum(line.startswith("Reading ") for line in lines), 1)
        # 3. No pipe-separated stage output
        self.assertNotIn(" | ", result.stderr.decode())
        # 4. Correct · separators
        self.assertIn(" · ", result.stderr.decode())
        # 5. Correct stage names and ✓ markers
        for phase in ("Preprocess", "Lexer", "Parser", "Semantic",
                      "AST → MIR", "MIR optimize", "LIR lowering", "Regalloc", "Codegen", "Linking"):
            self.assertEqual(sum(line.startswith(f"✓ {phase}") for line in lines), 1, (phase, lines))
        # 6. Aligned metadata in banner
        self.assertEqual(sum("VIRC" in line for line in lines), 1)
        self.assertTrue(any(f"Version      {VIRC_VERSION}" in line for line in lines))
        self.assertTrue(any("What's New   Native LSP Daemon" in line for line in lines))
        # 7. Final build summary separated from stages with indented path
        self.assertEqual(sum(line.startswith("✓ Build succeeded · ") for line in lines), 1)
        self.assertIn(f"  {self.output}", lines)
        self.assertNotIn(b"\x1b", result.stderr)
        self.assertNotIn(b"\r", result.stderr)
        self.assertNotIn(b"pipeline", result.stderr)

    def test_modern_quiet_help_version_and_cross_target_banner(self):
        result = self.compile(["--ui=modern", "--quiet"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout + result.stderr, b"")
        for flag in ("--help", "--version"):
            result = invoke(["--ui=modern", flag], env={"VIRC_UI": "modern"})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            self.assertNotIn(b"The Virgori", result.stdout)
        result = invoke(["tests/cli_contract/dispatch.vri", "--ui=modern", "--target",
                         "linux-x86_64", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b"Host         macos-arm64", result.stderr)
        self.assertIn(b"Target       linux-x86_64", result.stderr)

    def test_modern_unique_error_code_grouping_preserves_occurrences(self):
        for fixture, detailed in (("repeated_code.vri", True), ("multiple_codes.vri", False)):
            with self.subTest(fixture=fixture):
                path = ROOT / "tests/cli_contract" / fixture
                result = invoke([path.relative_to(ROOT), "--ui=modern", "-q", "-o", self.output])
                machine = invoke([path.relative_to(ROOT), "--json"])
                diagnostics = json.loads(machine.stdout)["diagnostics"]
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                self.assertEqual(result.stdout, b"")
                text = result.stderr.decode()
                self.assertNotIn("Compile time:", text)
                self.assertNotIn("VIRC\n", text)
                self.assertEqual(text.count("✗ Build failed ·"), 1)
                if detailed:
                    self.assertEqual(len({d["code"] for d in diagnostics}), 1)
                    self.assertEqual(text.count("EXECUTION REPORT"), len(diagnostics))
                    self.assertNotIn("Summary:", text)
                    for record in diagnostics:
                        self.assertIn(f'Line        : {record["primary_span"]["start_line"]}', text)
                else:
                    self.assertNotIn("EXECUTION REPORT", text)
                    self.assertIn("Summary: [E2001] × 2 · [E3007] × 1", text)
                    occurrences = [line for line in text.splitlines() if line.startswith("[E")]
                    self.assertEqual(len(occurrences), len(diagnostics))
                    for record, line in zip(diagnostics, occurrences):
                        span = record["primary_span"]
                        self.assertIn(f'{span["file"]}:{span["start_line"]}:', line)
                        self.assertIn(f'[{record["code"]}]', line)
                        self.assertIn(record["message"], line)
                        self.assertIn(" · ", line)

    def test_modern_warning_does_not_change_error_grouping(self):
        fixture = Path(self.temp.name) / "warning_group.vri"
        fixture.write_text("""include virc.semantic.sem_pass10_diagnostics
include rt.io
import diagnostic_engine_new, report_error_loc, report_warning_loc from virc.diagnostic.context
import pass10_emit_diagnostics from virc.semantic.sem_pass10_diagnostics
import cliUiReset, cliUiPhaseBegin from virc.cli.cli_ui
func main:
    cliUiReset(1, 1)
    cliUiPhaseBegin(5)
    var diagnostics = diagnostic_engine_new()
    report_error_loc(diagnostics, 2001, 0, 2, 1, "first")
    report_warning_loc(diagnostics, 3007, 0, 3, 1, "warning")
    report_error_loc(diagnostics, 2001, 0, 4, 1, "last")
    pass10_emit_diagnostics(diagnostics)
end.
""")
        result = invoke([fixture, "-q", "--ui=classic", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rendered = subprocess.run([self.output], capture_output=True, timeout=10)
        self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
        self.assertEqual(rendered.stdout, b"")
        self.assertEqual(rendered.stderr.count(b"EXECUTION REPORT"), 2)
        self.assertIn(b"[W3007]", rendered.stderr)
        self.assertIn("2 errors · 1 warnings · 0 notes".encode("utf-8"), rendered.stderr)
        self.assertNotIn(b"Summary:", rendered.stderr)

    def test_modern_grouping_grows_without_losing_occurrences(self):
        fixture = Path(self.temp.name) / "large_groups.vri"
        fixture.write_text("""include virc.semantic.sem_pass10_diagnostics
include rt.io
import diagnostic_engine_new, report_error_loc from virc.diagnostic.context
import pass10_emit_diagnostics from virc.semantic.sem_pass10_diagnostics
import cliUiReset, cliUiPhaseBegin from virc.cli.cli_ui
func main:
    cliUiReset(1, 1)
    cliUiPhaseBegin(5)
    var diagnostics = diagnostic_engine_new()
    var index = 0
    when index < 40 loop
        report_error_loc(diagnostics, 2001 + (index mod 20), 0, index + 1, 1, "record")
        index = index + 1
    end
    pass10_emit_diagnostics(diagnostics)
end.
""")
        result = invoke([fixture, "-q", "--ui=classic", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rendered = subprocess.run([self.output], capture_output=True, timeout=10)
        self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
        self.assertEqual(rendered.stdout, b"")
        lines = rendered.stderr.decode().splitlines()
        summary = next(line for line in lines if line.startswith("Summary: "))
        self.assertEqual(summary, "Summary: " + " · ".join(
            f"[E{code}] × 2" for code in range(2001, 2021)))
        self.assertEqual(sum(line.startswith("[E") for line in lines), 40)
        self.assertIn("40 errors · 0 warnings · 0 notes", lines)
        self.assertEqual(sum(line.startswith("✗ Build failed · 40 errors · ") for line in lines), 1)

    def test_duration_rounding_precision_boundaries_and_overflow(self):
        fixture = ROOT / "tests/cli_contract/duration.vri"
        result = invoke([fixture, "-q", "--ui=classic", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rendered = subprocess.run([self.output], capture_output=True, timeout=10)
        self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
        self.assertEqual(rendered.stderr.splitlines(), [
            b"0.00ms", b"24.58ms", b"999.99ms", b"1.00s", b"12.45s",
            b"59.99s", b"1m 00.00s", b"1m 27.27s", b"59m 59.99s",
            b"1h 00m 00s", b"1h 02m 15s", b"2562047h 47m 17s",
            b"unavailable"])
        self.assertEqual(rendered.stdout.splitlines(), [b"1000", b"1000000041", b"-1", b"-1"])

    def test_native_clock_monotonic_or_explicitly_unavailable(self):
        fixture = ROOT / "tests/cli_contract/clock.vri"
        result = invoke([fixture, "-q", "--ui=classic", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rendered = subprocess.run([self.output], capture_output=True, timeout=10)
        self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
        lines = rendered.stdout.splitlines()
        if lines == [b"unavailable"]:
            # Sysctl can be denied by an OS sandbox. The full platform gate
            # additionally runs this probe outside that sandbox and on Linux.
            return
        self.assertEqual(lines[0], b"monotonic")
        self.assertGreater(int(lines[1]), 0)
        self.assertGreaterEqual(int(lines[2]), int(lines[1]))

    def test_modern_color_stream_and_plain_environment_policy(self):
        for flags, environment, color in (
            (["--color=auto"], {"NO_COLOR": None}, False),
            (["--color=always"], {}, True),
            (["--color=never"], {"NO_COLOR": None}, False),
            (["--color=auto"], {"NO_COLOR": None, "TERM": "dumb"}, False)):
            result = self.compile(["--ui=modern", *flags], env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(b"\x1b[32m\xe2\x9c\x93\x1b[0m" in result.stderr, color)
            self.assertNotIn(b"\r", result.stderr)
        machine = self.compile(["--ui=modern", "--color=always", "--json"])
        self.assertTrue(json.loads(machine.stdout)["success"])
        self.assertEqual(machine.stderr, b"")

    def test_modern_pty_finalization_and_failure_cleanup(self):
        result = invoke_pty([FIXTURE, "--ui=modern", "--color=auto", "-o", self.output],
                            env={"NO_COLOR": None})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"\x1b[32m\xe2\x9c\x93\x1b[0m", result.stderr)
        plain = re.sub(rb"\x1b\[[0-9;]*[mK]", b"", result.stderr)
        self.assertEqual(plain.count("✓ Build succeeded".encode("utf-8")), 1)
        for phase in ("Preprocess", "Lexer", "Parser", "Semantic",
                      "AST → MIR", "MIR optimize", "LIR lowering", "Regalloc",
                      "Codegen", "Linking"):
            self.assertEqual(plain.count(f"✓ {phase}".encode("utf-8")), 1)
        failed = invoke_pty([FAILURE, "--ui=modern", "--color=never", "-o", self.output])
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stderr.count("✗ Semantic".encode("utf-8")), 1)
        self.assertEqual(failed.stderr.count("✗ Build failed ·".encode("utf-8")), 1)
        report = failed.stderr.index(b"EXECUTION REPORT")
        self.assertNotIn(b"\r", failed.stderr[report:])

    def test_modern_pty_dumb_ci_no_color_and_quiet(self):
        for environment in ({"TERM": "dumb", "NO_COLOR": None},
                            {"CI": "1", "NO_COLOR": None}):
            result = invoke_pty([FIXTURE, "--ui=modern", "-o", self.output], env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(b"\x1b", result.stderr)
            self.assertNotIn(b"\r", result.stderr)
        result = invoke_pty([FIXTURE, "--ui=modern", "-o", self.output])
        self.assertNotIn(b"\x1b[32m", result.stderr)
        quiet = invoke_pty([FIXTURE, "--ui=modern", "-q", "-o", self.output], env={"NO_COLOR": None})
        self.assertEqual(quiet.returncode, 0)
        self.assertEqual(quiet.stdout + quiet.stderr, b"")

    def test_live_refresh_throttle_and_narrow_terminal(self):
        fixture = ROOT / "tests/cli_contract/live_events.vri"
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for width in (8, 28, 48, 80):
            result = invoke_pty([], executable=self.output, columns=width)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            if result.stdout == b"unavailable\n":
                continue  # Platform clock gate is separately mandatory.
            frames = result.stderr.split(b"\r\x1b[2K")[1:]
            updates = [frame for frame in frames if frame.startswith(b"  ")]
            self.assertGreaterEqual(len(updates), 1)
            self.assertLessEqual(len(updates), 6)  # 250 ms, immediate first event.
            self.assertEqual(result.stderr.count("✓ MIR optimize".encode("utf-8")), 1)
            for frame in updates:
                self.assertLess(len(frame), width, (width, frame))

    def storage_adapter(self):
        fixture = ROOT / "tests/cli_contract/storage_adapter.vri"
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.output

    def test_storage_atomic_collision_and_concurrent_build_ids(self):
        adapter = self.storage_adapter()
        project = Path(self.temp.name) / "project with space"
        project.mkdir()
        key = hashlib.sha256(b"entry/full/path.vri").hexdigest()

        def publish(build, payload):
            return subprocess.run([adapter, project, key, build, payload],
                                  capture_output=True, timeout=10)

        first_id = "0" * 32
        first = publish(first_id, '{"first":true}')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout, b"0\n")
        cache = project / ".vir/diagnostics/v1"
        self.assertEqual((cache / f"{key}.latest").read_text(), first_id)
        self.assertEqual(json.loads((cache / f"{first_id}.json").read_text()), {"first": True})
        duplicate = publish(first_id, '{"overwrite":true}')
        self.assertEqual(duplicate.stdout, b"-1\n")
        self.assertEqual((cache / f"{key}.latest").read_text(), first_id)
        self.assertEqual(json.loads((cache / f"{first_id}.json").read_text()), {"first": True})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
            results = list(workers.map(lambda index: publish("random", json.dumps({"index": index})), range(24)))
        ids = set()
        for index, result in enumerate(results):
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout, b"0\n")
            build = result.stderr.splitlines()[0].decode()
            self.assertRegex(build, r"^[0-9a-f]{32}$")
            self.assertNotIn(build, ids)
            ids.add(build)
            self.assertEqual(json.loads((cache / f"{build}.json").read_text()), {"index": index})
        self.assertIn((cache / f"{key}.latest").read_text(), ids)
        self.assertEqual(len(list(cache.glob("*.json"))), 25)
        self.assertEqual(list(cache.glob("*.tmp")), [])

    def test_storage_refuses_symlink_components_and_path_traversal(self):
        adapter = self.storage_adapter()
        project = Path(self.temp.name) / "project"
        outside = Path(self.temp.name) / "outside"
        project.mkdir()
        outside.mkdir()
        (outside / "keep").write_text("unchanged")
        (project / ".vir").symlink_to(outside, target_is_directory=True)
        key = "a" * 64
        build = "b" * 32

        def publish(entry=key, identity=build):
            return subprocess.run([adapter, project, entry, identity, "{}"],
                                  capture_output=True, timeout=10)

        denied = publish()
        self.assertNotEqual(denied.returncode, 0, denied.stdout + denied.stderr)
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ["keep"])
        (project / ".vir").unlink()
        (project / ".vir/diagnostics").mkdir(parents=True)
        (project / ".vir/diagnostics/v1").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(publish().returncode, 0)
        (project / ".vir/diagnostics/v1").unlink()
        cache = project / ".vir/diagnostics/v1"
        cache.mkdir()
        final = cache / f"{build}.json"
        final.symlink_to(outside / "keep")
        self.assertEqual(publish().stdout, b"-1\n")
        self.assertEqual((outside / "keep").read_text(), "unchanged")
        final.unlink()
        for entry, identity in (("../outside/keep", build), (key, "../keep"),
                                ("A" * 64, build), (key, "g" * 32)):
            result = publish(entry, identity)
            self.assertEqual(result.stdout, b"-1\n")
        self.assertEqual(list(cache.iterdir()), [])

    def test_virc_show_end_to_end_and_read_only(self):
        fail_fixture = ROOT / "tests/cli_contract/failure.vri"
        compile_res = invoke([fail_fixture, "-q", "-o", self.output])
        self.assertEqual(compile_res.returncode, 1)

        # Overview query
        show_res = invoke(["show", fail_fixture])
        self.assertEqual(show_res.returncode, 0, show_res.stdout + show_res.stderr)
        self.assertIn(b"Errors: 1", show_res.stdout)
        self.assertIn(b"[E2001]", show_res.stdout)
        self.assertNotIn(b"virc: reading", show_res.stdout)
        self.assertNotIn(b"virc: parsing", show_res.stdout)
        self.assertNotIn("virc — Vir Self-Hosting Compiler".encode(), show_res.stdout)

        # Code-specific query
        show_code = invoke(["show", fail_fixture, "E2001"])
        self.assertEqual(show_code.returncode, 0, show_code.stdout + show_code.stderr)
        self.assertIn(b"Analysis", show_code.stdout)
        self.assertIn(b"Undefined variable in current scope", show_code.stdout)
        self.assertIn(b"Possible Causes", show_code.stdout)
        self.assertIn(b"Action", show_code.stdout)

        # All codes query
        show_all = invoke(["show", fail_fixture, "all"])
        self.assertEqual(show_all.returncode, 0, show_all.stdout + show_all.stderr)
        self.assertIn(b"Analysis", show_all.stdout)
        self.assertIn(b"Action", show_all.stdout)

        # JSON output query
        show_json = invoke(["show", fail_fixture, "--json"])
        self.assertEqual(show_json.returncode, 0, show_json.stdout + show_json.stderr)
        data = json.loads(show_json.stdout.decode())
        self.assertEqual(data.get("status"), "fresh")
        self.assertEqual(data.get("schemaVersion"), 1)
        self.assertEqual(len(data.get("diagnostics", [])), 1)
        self.assertEqual(data["diagnostics"][0]["code"], "E2001")

        # Missing code returns exit 1
        show_bad_code = invoke(["show", fail_fixture, "E9999"])
        self.assertEqual(show_bad_code.returncode, 1)
        self.assertIn(b"no occurrence", show_bad_code.stdout + show_bad_code.stderr)

        # Missing entry returns exit 1
        show_no_file = invoke(["show", "nonexistent_file_xyz.vri"])
        self.assertEqual(show_no_file.returncode, 1)
        self.assertIn(b"no diagnostic snapshot", show_no_file.stdout + show_no_file.stderr)

    def test_ide_semantic_contract(self):
        fixture = Path(self.temp.name) / "ide_contract.vri"
        fixture.write_text("""func dead_func() -> int:
    out 42
end.

func live_worker(x: string) -> string:
    var copy_x = x
    out copy_x
end.

func main:
    var msg = "hello"
    var res = live_worker(msg)
    print(res)
end.
""")
        # 1. Normal --json compilation does not include ide block
        res_normal = invoke([fixture, "--json"])
        self.assertEqual(res_normal.returncode, 0, res_normal.stdout + res_normal.stderr)
        data_normal = json.loads(res_normal.stdout.decode())
        self.assertNotIn("ide", data_normal)

        # 2. --ide-semantic --json emits structured ide block
        res_ide = invoke([fixture, "--ide-semantic", "--json"])
        self.assertEqual(res_ide.returncode, 0, res_ide.stdout + res_ide.stderr)
        data_ide = json.loads(res_ide.stdout.decode())
        self.assertIn("ide", data_ide)
        ide = data_ide["ide"]
        self.assertIn("occurrences", ide)
        self.assertIn("modules", ide)
        self.assertIn("functions", ide)
        self.assertIn("shapeDimensions", ide)
        self.assertIn("symbols", ide)

        # Function reachability: dead_func is inactive, live_worker and main are active
        funcs = {f["name"]: f["state"] for f in ide["functions"]}
        self.assertEqual(funcs.get("dead_func"), "inactive")
        self.assertEqual(funcs.get("live_worker"), "active")
        self.assertEqual(funcs.get("main"), "active")

        # Symbols list matches kinds and states
        syms = {s["name"]: s for s in ide["symbols"]}
        self.assertEqual(syms["dead_func"]["kind"], "function")
        self.assertEqual(syms["dead_func"]["state"], "inactive")
        self.assertEqual(syms["live_worker"]["kind"], "function")
        self.assertEqual(syms["live_worker"]["state"], "active")

        # 3. Move state detection in occurrences
        move_fixture = Path(self.temp.name) / "ide_move.vri"
        move_fixture.write_text("""func consume(x: string) -> int:
    out 1
end.

func main:
    var s = "hello"
    var a = consume(s)
    var b = s
    print(a)
end.
""")
        res_move = invoke([move_fixture, "--ide-semantic", "--json"])
        self.assertEqual(res_move.returncode, 1)
        data_move = json.loads(res_move.stdout.decode())
        self.assertIn("ide", data_move)
        # Look for state 4 (IDE_STATE_MOVED) on line 8
        moved_occs = [o for o in data_move["ide"]["occurrences"] if o.get("state") == 4]
        self.assertTrue(len(moved_occs) >= 1)
        self.assertEqual(moved_occs[0]["line"], 8)


        # Missing argument returns exit 1
        show_no_args = invoke(["show"])
        self.assertEqual(show_no_args.returncode, 1)

    def test_tool_json_strict_bounded_document_parser(self):
        fixture = ROOT / "tests/cli_contract/tool_json.vri"
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        valid = ["null", "true", "false", "-0", "-1.25e+3", "1E-2", '"é😀"',
                 r'"\ud83d\ude00"', r'"\u0000"', r'"\b\f\n\r\t\\\/\""',
                 '{"a":[1,true,null,"text"]}', json.dumps([0] * 1000),
                 json.dumps({str(index): {"value": index} for index in range(1000)})]
        for data in valid:
            with self.subTest(data=data[:60]):
                rendered = subprocess.run([self.output, data], capture_output=True, timeout=10)
                self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
                self.assertEqual(rendered.stdout.splitlines()[0], b"valid", rendered.stdout)
                self.assertGreater(int(rendered.stdout.splitlines()[1]), 0)
        invalid = ["", "[", "{", "[1,]", '{"a":1,}', '{"a" 1}', "01", "1.",
                   "1e", "1e+", "+1", "--1", "NaN", "Infinity", "true false",
                   '"raw\nnewline"', r'"\x00"', r'"\ud800"', r'"\udc00"',
                   r'"\ud800\u0041"', r'"\uZZZZ"', '"unterminated',
                   "[" * 66 + "0" + "]" * 66,
                   b'"\xc0\xaf"', b'"\xed\xa0\x80"', b'"\xf4\x90\x80\x80"']
        for data in invalid:
            with self.subTest(data=data[:60]):
                rendered = subprocess.run([self.output, data], capture_output=True, timeout=10)
                self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
                self.assertEqual(rendered.stdout, b"invalid\n")

    def test_tool_json_growth_ownership_across_repeated_documents(self):
        fixture = ROOT / "tests/cli_contract/json_growth_ownership.vri"
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.dumps({"result": {"documentVersion": 7, "occurrences": [
            {"symbolId": "same-id", "range": {"start": {"line": n, "character": 0},
                                           "end": {"line": n, "character": 1}}}
            for n in range(1000)]}}, separators=(",", ":"))
        run = subprocess.run([self.output, payload], capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stdout.strip(), b"100 documents retained all 1000 occurrences")

    def test_tool_json_lossless_ids_unicode_and_version_validation(self):
        fixture = ROOT / "tests/cli_contract/tool_json.vri"
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cases = [('{"id":"9223372036854775807"}', "id", b"9223372036854775807", b"123"),
                 (r'{"id":"\ud83d\ude00é"}', "id", "😀é".encode(), b"123"),
                 ('{"version":9223372036854775807}', "version", b"", b"9223372036854775807"),
                 ('{"version":-9223372036854775808}', "version", b"", b"minimum"),
                 ('{"version":9223372036854775808}', "version", b"", b"123"),
                 ('{"version":-9223372036854775809}', "version", b"", b"123"),
                 ('{"version":1.0}', "version", b"", b"123"),
                 ('{"version":1e0}', "version", b"", b"123"),
                 (r'{"id":"\u0000hidden"}', "id", b"", b"123"),
                 ('{"version":1,"version":2}', "version", b"", b"123")]
        for payload, key, string, integer in cases:
            with self.subTest(payload=payload):
                rendered = subprocess.run([self.output, payload, key], capture_output=True, timeout=10)
                self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
                self.assertEqual(rendered.stdout.splitlines()[-1], integer)
                self.assertEqual(rendered.stderr.rstrip(b"\n"), string)
                if payload == '{"version":1,"version":2}':
                    self.assertEqual(rendered.stdout.splitlines()[2], b"0")

    def test_modern_display_sanitizes_control_characters(self):
        fixture = Path(self.temp.name) / "source\x1b\x07\r\nINJECTEDfile.vri"
        fixture.write_bytes(FIXTURE.read_bytes())
        result = invoke([fixture, "--ui=modern", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertTrue(self.output.exists())
        for byte in (b"\x1b", b"\x07", b"\r"):
            self.assertNotIn(byte, result.stderr)
        self.assertNotIn(b"\nINJECTED", result.stderr)
        fixture.write_bytes((ROOT / "tests/cli_contract/repeated_code.vri").read_bytes())
        result = invoke([fixture, "--ui=modern", "-q"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr.count(b"EXECUTION REPORT"), 3)
        self.assertNotIn(b"\nINJECTED", result.stderr)
        for byte in (b"\x1b", b"\x07", b"\r"):
            self.assertNotIn(byte, result.stderr)

    def test_environment_parser_is_bounded_and_preserves_empty_value(self):
        fixture = Path(self.temp.name) / "environment_bounds.vri"
        fixture.write_text("""include virc.cli.cli_environment
include string_rt
import cliFindEnvironment from virc.cli.cli_environment
import rt_strlen, rt_streq, native_read_u8 from string_rt
import vir_free from alloc
func main:
    let name = "VIRC_UI" as int
    let buffer = "VIRC_UI=modern" as int
    let size = rt_strlen(buffer) + 1
    let value = cliFindEnvironment(buffer, size, 0, name)
    if value > 0 do
        if rt_streq(value, "modern" as int) do print(1) else print(0) end
        vir_free(value)
    else
        print(0)
    end
    let empty = "VIRC_UI=" as int
    let emptySize = rt_strlen(empty) + 1
    let emptyValue = cliFindEnvironment(empty, emptySize, 0, name)
    if emptyValue > 0 do
        if native_read_u8(emptyValue, 0) == 0 do print(1) else print(0) end
        vir_free(emptyValue)
    else
        print(0)
    end
    print(cliFindEnvironment(buffer, size, size, name))
    print(cliFindEnvironment(buffer, size - 1, 0, name))
    print(cliFindEnvironment(buffer, size, 0 - 1, name))
end.
""")
        result = invoke([fixture, "--ui=classic", "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(subprocess.check_output([self.output]).split(), [b"1", b"1", b"0", b"-1", b"-1"])

    def test_help_and_version_without_pipeline(self):
        for option in ("--help", "--version"):
            with self.subTest(option=option):
                result = invoke([option])
                self.assertEqual(result.returncode, 0)
                self.assertNotIn(b"tokenizing", result.stdout + result.stderr)
                if option == "--help":
                    for expected in (b"-O0", b"-O3", b"default: O1", b"--mir-full"):
                        self.assertIn(expected, result.stdout)

    def test_invalid_options_fail_before_artifact(self):
        for option in ("-O4", "-Ofast", "-O", "--mir-ful", "--unknown", "-Z"):
            with self.subTest(option=option):
                result = self.compile([option])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                self.assertIn(b"unknown option", result.stdout + result.stderr)
                self.assertNotIn(b"tokenizing", result.stdout + result.stderr)

    def test_argument_errors_are_machine_json(self):
        for flags in (("-O4", "--json"), ("--json", "-O4"),
                      ("--bad\x1b\x07", "--json"),
                      ("--target", "invalid", "--json"),
                      ("--format", "invalid", "--json"),
                      ("--json", "-o", "-O3")):
            with self.subTest(flags=flags):
                result = self.compile(flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                payload = json.loads(result.stdout)
                self.assertFalse(payload["success"])
                self.assertEqual(payload["error_kind"], "argument")
                self.assertEqual(result.stderr, b"")
                self.assertNotIn(b"\x1b", result.stdout)
                if "\x1b" in flags[0]:
                    self.assertEqual(payload["argument"], flags[0])

    def test_missing_option_values(self):
        for option in ("-o", "--target", "--format"):
            for trailing in ([], ["-O3"]):
                with self.subTest(option=option, trailing=trailing):
                    result = invoke([FIXTURE, option, *trailing], cwd=Path(self.temp.name))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"requires an argument", result.stdout + result.stderr)

    def test_flags_before_input(self):
        result = invoke(["-O1", "-q", FIXTURE, "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(subprocess.check_output([self.output]).strip(), b"23")

    def test_last_optimization_selector_wins(self):
        hashes = {}
        for level in ("-O0", "-O1", "-O2", "-O3"):
            result = self.compile([level, "-q"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            hashes[level] = hashlib.sha256(self.output.read_bytes()).hexdigest()
            self.assertEqual(subprocess.check_output([self.output]).strip(), b"23")
        for selectors, expected in (([], "-O1"), (["--mir-full"], "-O3"),
                                    (["-O3", "-O0"], "-O0"),
                                    (["--mir-full", "-O1"], "-O1"),
                                    (["-O2", "-O1"], "-O1"),
                                    (["-O0", "-O3"], "-O3")):
            with self.subTest(selectors=selectors):
                result = self.compile([*selectors, "-q"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), hashes[expected])

    def test_actual_optimization_invocations(self):
        for selectors, level in (([], 1), (["-O0"], 0), (["-O2"], 2),
                                 (["-O3"], 3), (["--mir-full"], 3),
                                 (["--mir-full", "-O1"], 1), (["-O3", "-O0"], 0)):
            with self.subTest(selectors=selectors):
                result = self.compile([*selectors, "--json"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                observation = payload["optimization"]
                self.assertEqual(observation["resolvedLevel"], level)
                self.assertEqual(observation["requestedSelector"], selectors[-1] if selectors else "default")
                passes = {entry["id"] for entry in observation["passInvocations"]}
                self.assertTrue({5, 7, 8}.isdisjoint(passes), "disabled passes must not be invoked")
                if level >= 2:
                    self.assertIn(19, passes)
                if level < 3:
                    self.assertTrue({24, 25, 26}.isdisjoint(passes), "O3 passes must not run in O1/O2 cleanup")
                if level == 0:
                    self.assertEqual(passes, set())
                    self.assertEqual(observation["hookInvocations"], [])
                else:
                    self.assertTrue({1, 4}.issubset(passes))
                    self.assertIn("arm64.mir", [entry["name"] for entry in observation["hookInvocations"]])

    def test_cross_target_hook_dispatch(self):
        for target, prefix in (("macos-arm64", "arm64"), ("linux-x86_64", "x86"),
                               ("linux-riscv64", "riscv"), ("wasm32-wasi-p1", "wasm")):
            for level in (0, 1, 2, 3):
                with self.subTest(target=target, level=level):
                    self.output.unlink(missing_ok=True)
                    result = invoke(["tests/cli_contract/dispatch.vri", "--target", target,
                                     f"-O{level}", "--json", "-o", self.output])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    hooks = json.loads(result.stdout)["optimization"]["hookInvocations"]
                    if level == 0:
                        self.assertEqual(hooks, [])
                    for entry in hooks:
                        self.assertIn(entry["name"].split(".")[0], (prefix, "generic"))

    def test_same_process_optimizer_reset(self):
        pipeline_path = ROOT / "compiler/src/pipeline.vri"
        if not pipeline_path.is_file():
            pipeline_path = ROOT / "stdlib/vir/compiler/pipeline.vri"
        pipeline = pipeline_path.read_text()
        functions = []
        for name in ("set_pipeline_mir_full", "set_pipeline_opt_level", "get_pipeline_opt_level"):
            match = re.search(rf"^func {name}\b.*?^end\.", pipeline, re.M | re.S)
            self.assertIsNotNone(match)
            functions.append(match.group())
        source = """var g_mir_full_opt: int = 0
var g_mir_opt_level: int = 1
var actualLevel: int = 1
func set_mir_opt_level(level: int):
    actualLevel = level
end.
""" + "\n".join(functions) + """
func main:
    set_pipeline_mir_full(1)
    print(get_pipeline_opt_level())
    set_pipeline_opt_level(0)
    print(get_pipeline_opt_level())
    print(g_mir_full_opt)
    print(actualLevel)
    set_pipeline_opt_level(1)
    print(get_pipeline_opt_level())
    print(g_mir_full_opt)
    set_pipeline_opt_level(3)
    set_pipeline_mir_full(0)
    print(get_pipeline_opt_level())
end.
"""
        fixture = Path(self.temp.name) / "session_reset.vri"
        fixture.write_text(source)
        result = invoke([fixture, "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(subprocess.check_output([self.output]).split(), [b"3", b"0", b"0", b"0", b"1", b"0", b"1"])

    def test_driver_session_boundary_resets_state(self):
        driver_path = ROOT / "compiler/generated/virc.vri"
        if not driver_path.is_file():
            driver_path = ROOT / "stdlib/vir/compiler/virc.vri"
        driver = driver_path.read_text()
        reset = re.search(r"^func vircResetCompileSession\b.*?^end\.", driver, re.M | re.S).group()
        getter = re.search(r"^func cfgOptimizationLevel\b.*?^end\.", driver, re.M | re.S).group()
        self.assertRegex(driver, r"func virc_compile\(cfg: CompilerConfig\):\s+vircResetCompileSession\(cfg\)")
        globals_ = ["g_time_buf_start", "g_compile_timer_printed", "g_phase_read_us",
                    "g_phase_preprocess_us", "g_phase_lex_us", "g_phase_parse_us",
                    "g_phase_semantic_us", "g_phase_semantic_start_us", "g_phase_lower_us",
                    "g_phase_codegen_us", "g_phase_link_us"]
        source = "include alloc\n" + "\n".join(f"var {name}: int = 0" for name in globals_) + """
var g_diag_json: int = 1
var g_color_mode: int = 0
var resolved: int = 1
var observed: int = 1
var resets: int = 0
entity CompilerConfig:
    unused: int
end.
func set_pipeline_opt_level(level: int):
    resolved = level
end.
func optTraceReset(selector: int, level: int, enabled: int):
    observed = level
    resets = resets + 1
end.
func virc_timer_init():
    g_time_buf_start = vir_alloc(144)
end.
func cfg_get_verbose(cfg: &CompilerConfig):
    out 1
end.
func cliUiReset(mode: int, quiet: int):
    out
end.
func cliUiConfigure(color: int):
    out
end.
func pass10SessionReset():
    out
end.
""" + getter + "\n" + reset + """
func main:
    let cfg = vir_alloc(80) as CompilerConfig
    native_write_i64(cfg as int, 72, 0)
    native_write_i64(cfg as int, 64, 0)
    native_write_i64(cfg as int, 56, 3)
    vircResetCompileSession(cfg)
    print(resolved)
    g_compile_timer_printed = 1
    g_phase_codegen_us = 999
    native_write_i64(cfg as int, 56, 0)
    vircResetCompileSession(cfg)
    print(resolved)
    print(observed)
    print(g_compile_timer_printed)
    print(g_phase_codegen_us)
    native_write_i64(cfg as int, 56, 1)
    vircResetCompileSession(cfg)
    vircResetCompileSession(cfg)
    print(resolved)
    print(resets)
end.
"""
        fixture = Path(self.temp.name) / "driver_reset.vri"
        fixture.write_text(source)
        result = invoke([fixture, "-q", "-o", self.output])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(subprocess.check_output([self.output]).split(), [b"3", b"0", b"0", b"0", b"0", b"1", b"4"])


def main():
    global VIRC
    parser = argparse.ArgumentParser()
    parser.add_argument("--virc", type=Path, default=VIRC)
    parser.add_argument("--backend-only", action="store_true", help="Skip terminal UI tests for manual review")
    parser.add_argument("--capture-baseline", action="store_true")
    parser.add_argument("--capture-failure-baseline", action="store_true")
    args = parser.parse_args()
    VIRC = args.virc.resolve()
    if not VIRC.is_file() or not os.access(VIRC, os.X_OK):
        parser.error(f"compiler is not executable: {VIRC}")
    if args.capture_baseline or args.capture_failure_baseline:
        baseline_path = FAILURE_BASELINE if args.capture_failure_baseline else BASELINE
        fixture = FAILURE if args.capture_failure_baseline else FIXTURE
        if baseline_path.exists():
            parser.error("baseline already exists; refusing to overwrite")
        with tempfile.TemporaryDirectory(prefix="vir-cli-baseline-") as directory:
            output = Path(directory) / "program"
            result = invoke([fixture.relative_to(ROOT), "-o", output])
            baseline_path.write_text(json.dumps({
                "compilerSha256": hashlib.sha256(VIRC.read_bytes()).hexdigest(),
                "exitCode": result.returncode,
                "stdoutRaw": result.stdout.decode(), "stderrRaw": result.stderr.decode(),
                "stdoutNormalized": normalized(result.stdout.replace(str(output).encode(), b"<artifact>")).decode(),
                "stderrNormalized": normalized(result.stderr).decode(),
            }, indent=2, ensure_ascii=False) + "\n")
        return 0
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CliContract)
    if args.backend_only or os.environ.get("VIR_CLI_BACKEND_ONLY") == "1":
        skipped = ("test_classic_", "test_ui_", "test_modern_", "test_live_", "test_duration_", "test_check_and_ide_modes_do_not_leak_classic_banner", "test_help_and_version_without_pipeline")
        suite = unittest.TestSuite(test for test in suite if not test._testMethodName.startswith(skipped))
        print("Terminal UI verification is reserved for manual review.", flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
