#!/usr/bin/env python3
"""
tests/test_int64_min_boundary_contract.py — Regression and backend parity contract
for INT64_MIN (-9223372036854775808) formatting and string interpolation (VIRC-ISS-0051).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = ROOT / "bin" / "virc"


class TestInt64MinBoundaryContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(VIRC.is_file(), f"virc binary not found at {VIRC}")

    def test_01_native_execution_boundary_matrix(self):
        """Compile and execute tests/vri/test_int64_min_formatting.vri natively."""
        fixture = ROOT / "tests" / "vri" / "test_int64_min_formatting.vri"
        self.assertTrue(fixture.is_file(), f"Fixture {fixture} missing")

        with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
            out_bin = Path(tmpdir) / "test_int64_min_bin"
            comp_res = subprocess.run(
                [str(VIRC), str(fixture), "-o", str(out_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                comp_res.returncode,
                0,
                f"Compilation failed: {comp_res.stderr}\n{comp_res.stdout}",
            )
            self.assertTrue(out_bin.is_file())

            run_res = subprocess.run(
                [str(out_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                run_res.returncode,
                0,
                f"Binary execution failed: {run_res.stderr}\n{run_res.stdout}",
            )

            expected_snippets = [
                "0\ninterp=0\nitostr=0\nfmt_int=0",
                "1\ninterp=1\nitostr=1\nfmt_int=1",
                "-1\ninterp=-1\nitostr=-1\nfmt_int=-1",
                "9223372036854775807\ninterp=9223372036854775807\nitostr=9223372036854775807\nfmt_int=9223372036854775807",
                "-9223372036854775808\ninterp=-9223372036854775808\nitostr=-9223372036854775808\nfmt_int=-9223372036854775808",
                "hex_min=-0x8000000000000000",
                "bin_min=-0b1000000000000000000000000000000000000000000000000000000000000000",
                "oct_min=-0o1000000000000000000000",
            ]
            for snippet in expected_snippets:
                self.assertIn(
                    snippet,
                    run_res.stdout,
                    f"Expected snippet missing from stdout: {snippet}",
                )

    def test_02_arm64_disassembly_structural_check(self):
        """Verify direct machine-code emission uses udiv, not sdiv, in rt_int_to_str."""
        source_code = """
func main:
    let min = 9223372036854775807 + 1
    print "min=$min\\n"
end.
"""
        with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
            src_file = Path(tmpdir) / "test_disasm.vri"
            out_bin = Path(tmpdir) / "test_disasm_bin"
            src_file.write_text(source_code, encoding="utf-8")

            comp_res = subprocess.run(
                [str(VIRC), str(src_file), "-o", str(out_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(comp_res.returncode, 0)

            # Disassemble binary using otool on macOS
            disasm_res = subprocess.run(
                ["otool", "-tv", str(out_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            if disasm_res.returncode == 0:
                lines = disasm_res.stdout.splitlines()
                # Find loop: mov x15, #0xa followed by udiv x13, x9, x15 and msub x14, x13, x15, x9
                found_udiv_loop = False
                for i, line in enumerate(lines):
                    if "udiv" in line and "x13, x9, x15" in line:
                        found_udiv_loop = True
                        # Ensure preceding instruction was division by 10 setup
                        self.assertIn("0xa", lines[i - 1])
                        # Ensure following instruction is msub
                        self.assertIn("msub", lines[i + 1])
                        break
                self.assertTrue(
                    found_udiv_loop,
                    f"Did not find 'udiv x13, x9, x15' in rt_int_to_str stub disassembly:\n{disasm_res.stdout}",
                )

    def test_03_backend_assembly_parity(self):
        """Verify textual assembly stubs across ARM64, RISC-V, and x86-64 use unsigned division."""
        source_code = """
func main:
    let min = 9223372036854775807 + 1
    print "min=$min\\n"
end.
"""
        with tempfile.TemporaryDirectory(dir=ROOT) as tmpdir:
            src_file = Path(tmpdir) / "test_stubs.vri"
            src_file.write_text(source_code, encoding="utf-8")

            # 1. macOS ARM64 assembly
            s_arm64 = Path(tmpdir) / "arm64.s"
            res = subprocess.run(
                [str(VIRC), str(src_file), "-S", "--target", "macos-arm64", "-o", str(s_arm64)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            text_arm64 = s_arm64.read_text(encoding="utf-8")
            self.assertIn("udiv x13, x9, x15", text_arm64)

            # 2. Linux x86-64 assembly
            s_x86 = Path(tmpdir) / "x86.s"
            res = subprocess.run(
                [str(VIRC), str(src_file), "-S", "--target", "linux-x86_64", "-o", str(s_x86)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            text_x86 = s_x86.read_text(encoding="utf-8")
            # x86-64 uses unsigned div r10
            self.assertIn("div r10", text_x86)
            self.assertNotIn("idiv", text_x86)

            # 3. Linux RISC-V assembly
            s_rv = Path(tmpdir) / "rv.s"
            res = subprocess.run(
                [str(VIRC), str(src_file), "-S", "--target", "linux-riscv64", "-o", str(s_rv)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            text_rv = s_rv.read_text(encoding="utf-8")
            self.assertIn("remu a3, t4, t6", text_rv)
            self.assertIn("divu t4, t4, t6", text_rv)


if __name__ == "__main__":
    unittest.main()
