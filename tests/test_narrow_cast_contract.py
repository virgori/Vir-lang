#!/usr/bin/env python3
"""Regression contract for VIRC-ISS-0023 narrow integer casts."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", ROOT / "bin" / "virc"))
FLOW_FIXTURE = ROOT / "tests" / "test_narrow_cast_flow.vri"
WIDTH_FIXTURE = ROOT / "tests" / "test_narrow_casts.vri"
EXPECTED_FLOW = "\n".join(
    ["44", "-21682", "1", "43855", "2596069104", "-1698898192"]
)
EXPECTED_WIDTHS = "\n".join(
    ["44", "251", "-21682", "43854", "2596069104", "-1698898192", "-16", "240", "43854", "44"]
)
WASI_RUNNER = (
    'const fs=require("fs");'
    'const {WASI}=require("wasi");'
    'const wasi=new WASI({version:"preview1",args:[],env:{}});'
    'const module=new WebAssembly.Module(fs.readFileSync(process.argv[1]));'
    'const instance=new WebAssembly.Instance(module,{wasi_snapshot_preview1:wasi.wasiImport});'
    'wasi.start(instance);'
)


def run_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, VIRC_UI="classic", NO_COLOR="1")
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def extract_function(assembly: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:\n(.*?)(?=^\.size\s+{re.escape(name)},)",
        assembly,
    )
    if match is None:
        return ""
    return match.group(1)


class NarrowCastContractTest(unittest.TestCase):
    def test_flow_semantics_at_all_optimization_levels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vir-narrow-cast-") as temp_dir:
            temp_root = Path(temp_dir)
            for opt_level in range(4):
                with self.subTest(opt_level=opt_level):
                    output = temp_root / f"flow-o{opt_level}"
                    compiled = run_command(
                        [
                            str(VIRC),
                            str(FLOW_FIXTURE),
                            f"-O{opt_level}",
                            "-o",
                            str(output),
                            "-q",
                        ]
                    )
                    self.assertEqual(
                        compiled.returncode,
                        0,
                        f"compile failed at O{opt_level}:\n{compiled.stdout}\n{compiled.stderr}",
                    )
                    executed = run_command([str(output)])
                    self.assertEqual(
                        executed.returncode,
                        0,
                        f"execution failed at O{opt_level}:\n{executed.stderr}",
                    )
                    self.assertEqual(executed.stdout.strip(), EXPECTED_FLOW)

                    assembly_path = temp_root / f"flow-o{opt_level}.s"
                    emitted = run_command(
                        [
                            str(VIRC),
                            str(FLOW_FIXTURE),
                            f"-O{opt_level}",
                            "--target",
                            "linux-arm64",
                            "-S",
                            "-o",
                            str(assembly_path),
                            "-q",
                        ]
                    )
                    self.assertEqual(emitted.returncode, 0, emitted.stderr)
                    assembly = assembly_path.read_text(encoding="utf-8")
                    pressure_body = extract_function(assembly, "narrow_under_pressure")
                    main_body = extract_function(assembly, "main")
                    self.assertRegex(pressure_body, r"\buxth\b")
                    self.assertRegex(pressure_body, r"\b(?:ldr|str)\s+x\d+,\s*\[fp, #-\d+\]")
                    self.assertRegex(pressure_body, r"\bb\.(?:eq|ne)\b")
                    self.assertRegex(main_body, r"\bbl\s+narrow_u8\b")

    def test_mc_assembly_preserves_narrowing_at_all_optimization_levels(self) -> None:
        target_contracts = {
            "linux-arm64": [r"\buxtb\b", r"\buxth\b", r"\buxtw\b", r"\bsxtb\b", r"\bsxth\b", r"\bsxtw\b"],
            "linux-x86_64": [r"\bmovzx\b", r"\bmovsx\b", r"\bmovsxd\b", r"\bmov\s+(?:e[a-z]{2}|r\d+d),"],
            "linux-riscv64": [r"\bslli\b", r"\bsrli\b", r"\bsrai\b"],
        }
        with tempfile.TemporaryDirectory(prefix="vir-narrow-mc-") as temp_dir:
            temp_root = Path(temp_dir)
            for opt_level in range(4):
                for target, patterns in target_contracts.items():
                    with self.subTest(opt_level=opt_level, target=target):
                        assembly_path = temp_root / f"narrow-{target}-o{opt_level}.s"
                        compiled = run_command(
                            [
                                str(VIRC),
                                str(WIDTH_FIXTURE),
                                f"-O{opt_level}",
                                "--target",
                                target,
                                "-S",
                                "-o",
                                str(assembly_path),
                                "-q",
                            ]
                        )
                        self.assertEqual(
                            compiled.returncode,
                            0,
                            f"assembly emission failed for {target} O{opt_level}:\n"
                            f"{compiled.stdout}\n{compiled.stderr}",
                        )
                        assembly = assembly_path.read_text(encoding="utf-8")
                        for pattern in patterns:
                            self.assertRegex(
                                assembly,
                                re.compile(pattern, re.MULTILINE),
                                f"missing {pattern!r} for {target} O{opt_level}",
                            )

    def test_wasm_semantics_at_all_optimization_levels(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js WASI runtime is unavailable")
        with tempfile.TemporaryDirectory(prefix="vir-narrow-wasm-") as temp_dir:
            temp_root = Path(temp_dir)
            for opt_level in range(4):
                with self.subTest(opt_level=opt_level):
                    wasm_path = temp_root / f"narrow-o{opt_level}.wasm"
                    compiled = run_command(
                        [
                            str(VIRC),
                            str(WIDTH_FIXTURE),
                            f"-O{opt_level}",
                            "--target",
                            "wasm32-wasi",
                            "-o",
                            str(wasm_path),
                            "-q",
                        ]
                    )
                    self.assertEqual(
                        compiled.returncode,
                        0,
                        f"Wasm compile failed at O{opt_level}:\n{compiled.stdout}\n{compiled.stderr}",
                    )
                    executed = run_command(
                        [node, "--no-warnings", "-e", WASI_RUNNER, str(wasm_path)]
                    )
                    self.assertEqual(
                        executed.returncode,
                        0,
                        f"Wasm execution failed at O{opt_level}:\n{executed.stderr}",
                    )
                    self.assertEqual(executed.stdout.strip(), EXPECTED_WIDTHS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
