#!/usr/bin/env python3
"""
Production test suite for LIR Tail-Call Optimization (TCO).
Governed by VIRC-ISS-0024 / VIRC-PLN-0014 / VIRC-RPT-0030 / VIRC-SPC-0008.

Verifies:
1. Direct self-tail-calls execute >= 1,000,000 iterations in O(1) stack space without stack overflow.
2. Argument permutation is handled correctly across recursive steps (e.g. Euclidean gcd).
3. More than 8 arguments (>8 args) update caller stack slots [FP + 16 + si*8] correctly before direct branch.
4. Negative non-tail calls (out func(n - 1) + 1) strictly preserve linked BL calls in isolated function body.
5. Negative calls with pending cleanup (ensure blocks) strictly preserve linked BL calls in isolated function body.
6. Backend Pass 11 (OptPassTCO) emits trace notes in --json output across -O1, -O2, and -O3, while disabled at -O0.
7. High register-pressure functions requiring spills maintain correct semantics and constant stack space under TCO.
8. Exceptions thrown from within tail-recursive iterations propagate correctly to caller try/revert handlers.
9. x86-64 target updates caller stack slots [rbp + 16 + si*8] in-place before jmp without stack-growing pushes.
"""

from __future__ import annotations
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", str(ROOT / "bin/virc_stage1" if (ROOT / "bin/virc_stage1").exists() else ROOT / "bin/virc")))


def run_cmd(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 < len(args):
            Path(args[idx + 1]).unlink(missing_ok=True)
    env = dict(os.environ, VIRC_UI="classic", NO_COLOR="1")
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


def codesign_bin(bin_path: Path) -> None:
    if bin_path.exists():
        subprocess.run(["codesign", "-s", "-", "-i", "virc", "-f", str(bin_path)], check=True, capture_output=True)


def get_function_assembly(src_path: Path, opt_level: str, target: str = "") -> str:
    """Emits assembly with -S and returns full assembly text."""
    out_s = src_path.with_suffix(".s")
    cmd = [str(VIRC), str(src_path), opt_level, "-S", "-o", str(out_s)]
    if target:
        cmd.extend(["--target", target])
    res = run_cmd(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate assembly ({opt_level} {target}): {res.stderr}")
    return out_s.read_text()


def extract_function_body(asm_text: str, func_name: str) -> str:
    """Extracts lines belonging strictly to func_name from emitted assembly."""
    lines = asm_text.splitlines()
    in_func = False
    func_lines = []
    target_labels = {f"_{func_name}:", f"{func_name}:"}
    for line in lines:
        stripped = line.strip()
        if stripped in target_labels:
            in_func = True
            func_lines.append(line)
            continue
        if in_func:
            if stripped.startswith(".globl ") or (
                stripped.endswith(":")
                and not stripped.startswith("LBB")
                and not stripped.startswith(".LBB")
                and not stripped.startswith(".L_")
            ):
                break
            func_lines.append(line)
    return "\n".join(func_lines)


class TailCallOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.scratch_dir = ROOT / "scratch"
        self.scratch_dir.mkdir(exist_ok=True)

    def write_stack_args_fixture(self) -> Path:
        src = self.scratch_dir / "test_tco_9args.vri"
        src.write_text(
            "func sum9:\n"
            "    in\n"
            "        n: int\n"
            "        a1: int\n"
            "        a2: int\n"
            "        a3: int\n"
            "        a4: int\n"
            "        a5: int\n"
            "        a6: int\n"
            "        a7: int\n"
            "        acc: int\n"
            "    if n <= 0 do\n"
            "        out acc\n"
            "    end\n"
            "    out sum9(n - 1, a1, a2, a3, a4, a5, a6, a7, acc + a1)\n"
            "end.\n"
            "func main:\n"
            "    let r = sum9(10000, 1, 1, 1, 1, 1, 1, 1, 0)\n"
            "    print r\n"
            "end.\n"
        )
        return src

    def test_01_direct_recursion_1m_stack_bounded(self):
        """1,000,000 recursive tail calls execute in O(1) stack space across -O1, -O2, -O3."""
        src = self.scratch_dir / "test_countdown_1m.vri"
        src.write_text(
            "func countdown:\n"
            "    in\n"
            "        n: int\n"
            "    if n <= 0 do\n"
            "        out 0\n"
            "    end\n"
            "    out countdown(n - 1)\n"
            "end.\n"
            "func main:\n"
            "    let r = countdown(1000000)\n"
            "    print r\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_tco_1m_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                # Execute binary: 1M depth would overflow default stack (8MB / 48B > 174k frames)
                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=30)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "0")

                # Verify isolated assembly of countdown: strictly zero bl calls inside countdown
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "countdown")
                self.assertTrue(len(body) > 0, "Failed to extract countdown function body")
                bl_count = len(re.findall(r"^\s*bl\s+", body, re.MULTILINE))
                self.assertEqual(bl_count, 0, f"Expected 0 'bl' inside countdown at {opt}, got:\n{body}")
                self.assertTrue(
                    re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE),
                    f"Expected direct branch 'b LBB_<fid>_0' inside countdown at {opt}, got:\n{body}"
                )

    def test_02_argument_permutation_gcd(self):
        """Argument permutation (a, b) -> (b, a mod b) correctly computes gcd across -O1, -O2, -O3."""
        src = self.scratch_dir / "test_tco_gcd.vri"
        src.write_text(
            "func gcd:\n"
            "    in\n"
            "        a: int\n"
            "        b: int\n"
            "    if b <= 0 do\n"
            "        out a\n"
            "    end\n"
            "    out gcd(b, a mod b)\n"
            "end.\n"
            "func main:\n"
            "    let r = gcd(1071, 462)\n"
            "    print r\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_tco_gcd_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "21")

                # Verify zero linked calls inside gcd
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "gcd")
                bl_count = len(re.findall(r"^\s*bl\s+", body, re.MULTILINE))
                self.assertEqual(bl_count, 0, f"Expected 0 'bl' inside gcd at {opt}")
                self.assertTrue(re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE))

    def test_03_stack_arguments_greater_than_8(self):
        """>8 arguments update stack slots [FP + 16 + si*8] correctly before direct branch."""
        src = self.write_stack_args_fixture()

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_tco_9args_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "10000")

                # Verify assembly contains caller stack store to [fp, #16] (9th argument)
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "sum9")
                self.assertTrue(
                    "str x" in body and "[fp, #16]" in body,
                    f"Expected stack store to [fp, #16] in sum9 body:\n{body}"
                )
                bl_count = len(re.findall(r"^\s*bl\s+", body, re.MULTILINE))
                self.assertEqual(bl_count, 0, f"Expected 0 'bl' inside sum9 at {opt}")

    def test_04_negative_non_tail_call_preserved(self):
        """Non-tail self-call (out countdown(n - 1) + 1) strictly preserved as linked BL call in isolated function body."""
        src = self.scratch_dir / "test_nontail.vri"
        src.write_text(
            "func countdown:\n"
            "    in\n"
            "        n: int\n"
            "    if n <= 0 do\n"
            "        out 0\n"
            "    end\n"
            "    out countdown(n - 1) + 1\n"
            "end.\n"
            "func main:\n"
            "    let r = countdown(10)\n"
            "    print r\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_nontail_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "10")

                # Isolate countdown body: must contain recursive linked 'bl _countdown', must NOT contain 'b LBB_<fid>_0'
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "countdown")
                bl_calls = re.findall(r"^\s*bl\s+_countdown\b", body, re.MULTILINE)
                self.assertGreaterEqual(len(bl_calls), 1, f"Expected linked 'bl _countdown' inside non-tail countdown at {opt}:\n{body}")
                self.assertFalse(
                    re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE),
                    f"Unexpected direct tail branch in non-tail countdown at {opt}:\n{body}"
                )

    def test_05_negative_pending_cleanup_preserved(self):
        """Self-call with pending ensure cleanup strictly preserved as linked BL call in isolated function body."""
        src = self.scratch_dir / "test_cleanup.vri"
        src.write_text(
            "func countdown_cleanup:\n"
            "    in\n"
            "        n: int\n"
            "    if n <= 0 do\n"
            "        out 0\n"
            "    end\n"
            "    out countdown_cleanup(n - 1)\n"
            "ensure\n"
            "    let x = 1\n"
            "end.\n"
            "func main:\n"
            "    let r = countdown_cleanup(5)\n"
            "    print r\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_cleanup_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "0")

                # Isolate countdown_cleanup body: must preserve linked 'bl _countdown_cleanup'
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "countdown_cleanup")
                bl_calls = re.findall(r"^\s*bl\s+_countdown_cleanup\b", body, re.MULTILINE)
                self.assertGreaterEqual(len(bl_calls), 1, f"Expected linked 'bl _countdown_cleanup' with ensure cleanup at {opt}:\n{body}")
                self.assertFalse(
                    re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE),
                    f"Unexpected direct tail branch in countdown_cleanup with ensure at {opt}:\n{body}"
                )

    def test_06_opt_trace_pass_11_json(self):
        """OptPassTCO (pass ID 11) is recorded in passInvocations under --json at -O1, -O2, -O3, and absent at -O0."""
        src = ROOT / "tests/test_adv_023_tailcall.vri"

        # Baseline -O0
        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "--json"])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        data_o0 = json.loads(res_o0.stdout)
        invs_o0 = data_o0.get("optimization", {}).get("passInvocations", [])
        has_tco_o0 = any(inv.get("id") == 11 for inv in invs_o0)
        self.assertFalse(has_tco_o0, "Pass 11 (TCO) should NOT run at -O0")

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                res = run_cmd([str(VIRC), str(src), opt, "--json"])
                self.assertEqual(res.returncode, 0, f"Failed at {opt}: {res.stderr}")
                data = json.loads(res.stdout)
                invs = data.get("optimization", {}).get("passInvocations", [])
                tco_inv = next((inv for inv in invs if inv.get("id") == 11), None)
                self.assertIsNotNone(tco_inv, f"Pass 11 (TCO) missing in passInvocations at {opt}")
                self.assertGreaterEqual(tco_inv.get("count", 0), 1, f"Pass 11 invocation count < 1 at {opt}")

    def test_07_register_spills_runtime(self):
        """Tail recursion with high register pressure (12+ live locals) executes in constant stack space."""
        src = self.scratch_dir / "test_tco_spills.vri"
        src.write_text(
            "func spill_tail:\n"
            "    in\n"
            "        n: int\n"
            "        acc: int\n"
            "    if n <= 0 do\n"
            "        out acc\n"
            "    end\n"
            "    let v1 = acc + 1\n"
            "    let v2 = v1 + 2\n"
            "    let v3 = v2 + 3\n"
            "    let v4 = v3 + 4\n"
            "    let v5 = v4 + 5\n"
            "    let v6 = v5 + 6\n"
            "    let v7 = v6 + 7\n"
            "    let v8 = v7 + 8\n"
            "    let v9 = v8 + 9\n"
            "    let v10 = v9 + 10\n"
            "    let v11 = v10 + 11\n"
            "    let v12 = v11 + 12\n"
            "    let next_acc = v1 + v2 + v3 + v4 + v5 + v6 + v7 + v8 + v9 + v10 + v11 + v12\n"
            "    out spill_tail(n - 1, next_acc mod 100000)\n"
            "end.\n"
            "func main:\n"
            "    let r = spill_tail(1000, 1)\n"
            "    print r\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_tco_spill_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "46876")

                # Verify 0 bl inside spill_tail
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "spill_tail")
                bl_count = len(re.findall(r"^\s*bl\s+", body, re.MULTILINE))
                self.assertEqual(bl_count, 0, f"Expected 0 'bl' inside spill_tail at {opt}")
                self.assertTrue(re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE))

    def test_08_error_propagation_runtime(self):
        """Errors thrown from within tail-recursive iterations propagate correctly to try/revert."""
        src = self.scratch_dir / "test_tco_error.vri"
        src.write_text(
            "func countdown_err:\n"
            "    in\n"
            "        n: int\n"
            "    if n == 5 do\n"
            "        throw 42\n"
            "    end\n"
            "    if n <= 0 do\n"
            "        out 0\n"
            "    end\n"
            "    out countdown_err(n - 1)\n"
            "end.\n"
            "func main:\n"
            "    try:\n"
            "        let r = countdown_err(10)\n"
            "        print 0\n"
            "    revert\n"
            "        let err = erx\n"
            "        print err\n"
            "    end\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_tco_err_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "42")

    def test_09_x86_64_stack_args_assembly(self):
        """linux-x86_64 target updates caller stack slots [rbp + 16 + si*8] in-place without push loop."""
        src = self.write_stack_args_fixture()
        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                asm_text = get_function_assembly(src, opt, target="linux-x86_64")
                body = extract_function_body(asm_text, "sum9")
                self.assertTrue(len(body) > 0, "Failed to extract sum9 body for x86-64")

                # Verify caller stack slots [rbp + 16], [rbp + 24], [rbp + 32] are written before jump
                self.assertIn("qword ptr [rbp + 16]", body)
                self.assertIn("qword ptr [rbp + 24]", body)
                self.assertIn("qword ptr [rbp + 32]", body)

                # Verify direct jump back to entry block .LBB_<fid>_0
                self.assertTrue(
                    re.search(r"^\s*jmp\s+\.LBB_\d+_0\b", body, re.MULTILINE),
                    f"Expected direct jmp .LBB_<fid>_0 in sum9 for x86-64:\n{body}"
                )

                # Verify NO call to sum9 inside sum9
                self.assertFalse(
                    re.search(r"^\s*call\s+sum9\b", body, re.MULTILINE),
                    f"Unexpected recursive call to sum9 in x86-64 assembly:\n{body}"
                )

    def test_10_arena_tco_stack_and_memory_bounded(self):
        """Tail recursion inside an arena block restores arena watermark and executes in O(1) stack & memory."""
        src = self.scratch_dir / "test_arena_tco.vri"
        src.write_text(
            "func arena_tail_step(n: int, acc: int) -> int:\n"
            "    if n <= 0 do\n"
            "        out acc\n"
            "    end\n"
            "    arena:\n"
            "        var tmp = [n, acc, (n + acc) mod 997]\n"
            "        var head = tmp[0]\n"
            "        var mid = tmp[1]\n"
            "        var tail = tmp[2]\n"
            "        out arena_tail_step(n - 1, (acc + tail) mod 1000000)\n"
            "    end\n"
            "end.\n"
            "func main:\n"
            "    let res = arena_tail_step(100000, 42)\n"
            "    print res\n"
            "end.\n"
        )

        for opt in ["-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_arena_tco_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                self.assertNotIn("W4001", res.stderr + res.stdout, f"Spurious W4001 warning emitted at {opt}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=10)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(exec_res.stdout.strip(), "860643")

                # Verify assembly: str ..., [x28] (watermark restore) before direct branch
                # Note: MIR_MEM_MARK generates ldr ..., [x28]; only the reset (str) must be asserted.
                asm_text = get_function_assembly(src, opt)
                body = extract_function_body(asm_text, "arena_tail_step")
                reset_store = re.search(r"(?m)^\s*str\s+\w+,\s*\[x28\]", body)
                self.assertIsNotNone(
                    reset_store,
                    f"Expected watermark restore 'str ..., [x28]' in arena_tail_step at {opt}:\n{body}"
                )
                bl_calls = re.findall(r"^\s*bl\s+_arena_tail_step\b", body, re.MULTILINE)
                self.assertEqual(len(bl_calls), 0, f"Expected 0 linked calls inside arena_tail_step at {opt}:\n{body}")
                backedge = re.search(r"^\s*b\s+LBB_\d+_0\b", body, re.MULTILINE)
                self.assertIsNotNone(
                    backedge,
                    f"Expected direct tail branch in arena_tail_step at {opt}:\n{body}"
                )
                self.assertLess(
                    reset_store.start(), backedge.start(),
                    f"Expected arena watermark restore before direct tail branch at {opt}:\n{body}"
                )

    def test_11_arena_tco_shadowed_callable_no_miscompile(self):
        """A local callable binding that shadows the current function name must NOT be treated
        as a self-tail call inside an arena block. Regression for the P1 name-based detection
        miscompile: without the fix, all O0-O3 returned 0 instead of 999."""
        # Helper that always returns 999
        helper_src = (
            "func other_fn(ignored: int) -> int:\n"
            "    out 999\n"
            "end.\n"
        )
        # Exact self-name shadowing case: a local variable named identically to the enclosing
        # function (`probe = other_fn`). Without checking local vreg binding, `fat_str_eq(callee, cur_fname)`
        # matched, causing wrong 0 (self-recursion) instead of 999 at all O0-O3.
        probe_src = (
            "func probe(x: int) -> int:\n"
            "    let probe = other_fn\n"
            "    arena:\n"
            "        out probe(x)\n"
            "    end\n"
            "end.\n"
            "func main:\n"
            "    let v = probe(42)\n"
            "    print v\n"
            "end.\n"
        )
        src = self.scratch_dir / "test_arena_shadow.vri"
        src.write_text(helper_src + probe_src)

        for opt in ["-O0", "-O1", "-O2", "-O3"]:
            with self.subTest(opt=opt):
                out_bin = self.scratch_dir / f"test_arena_shadow_{opt.lstrip('-')}"
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"Compilation failed with {opt}: {res.stderr}")
                codesign_bin(out_bin)

                exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True, timeout=5)
                self.assertEqual(exec_res.returncode, 0, f"Execution failed at {opt}: {exec_res.stderr}")
                self.assertEqual(
                    exec_res.stdout.strip(), "999",
                    f"At {opt}: expected 999 (call to other_fn via local binding) but got "
                    f"'{exec_res.stdout.strip()}' — arena self-tail detection incorrectly rewriting "
                    f"indirect call through local variable to self-recursion"
                )


if __name__ == "__main__":
    unittest.main()
