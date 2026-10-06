#!/usr/bin/env python3
"""
Production structural test suite for MIR PRE and Loop Transformations (Fusion, Tiling, Interchange).
Governed by VIRC-ISS-0001 / VIRC-PLN-0001 / VIRC-RPT-0025 / VIRC-SPC-0008.

Verifies:
1. PRE hoists partially redundant expressions, introduces SSA Phi, and preserves semantics.
2. PRE safely skips on operand redefinition and barriers.
3. PRE mutation controls fail the structural oracle (identity_pre) and CFG/SSA verifier (corrupt_pre_phi).
4. Loop fusion fuses adjacent counted loops with matching bounds/step, reducing loop count.
5. Loop fusion safely skips mismatched bounds and body barriers with precise skip reasons.
6. Loop tiling transforms its exact supported reduction and safely skips unsupported bodies and bounds.
7. Loop interchange swaps loop headers and safely skips (<, >) dependence directions.
8. Loop mutation mode (marker_loop_transforms) fails the structural oracle.
9. Cross-optimization level parity across O0, O1, O2, O3.
10. Existing bootstrap regression tests pass.
"""

from __future__ import annotations
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", str(ROOT / "bin/virc")))


def run_cmd(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 < len(args):
            Path(args[idx + 1]).unlink(missing_ok=True)
    env = dict(os.environ, VIRC_UI="classic", NO_COLOR="1")
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


def extract_transform(payload: dict, func_name: str, transform_name: str) -> dict | None:
    transforms = payload.get("optimization", {}).get("mirTransforms", [])
    for rec in transforms:
        if rec.get("function") == func_name and rec.get("transform") == transform_name:
            return rec
    return None


class PreAndLoopTransformsTest(unittest.TestCase):
    def setUp(self):
        self.scratch_dir = ROOT / "scratch"
        self.scratch_dir.mkdir(exist_ok=True)

    def test_01_pre_positive_structural_and_runtime(self):
        """PRE hoists redundant expression, creates SSA Phi, and maintains runtime parity."""
        src = ROOT / "tests/opt_structural/pre_positive.vri"
        out_bin = self.scratch_dir / "test_pre_pos"

        # 1. Baseline -O0
        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "95\n57")

        # 2. Structural assertion at -O2 --json
        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "compute_pre", "pre")
        self.assertIsNotNone(rec, "pre transform record must exist for compute_pre")
        self.assertEqual(rec["changed"], 1, f"PRE must report changed=1, got: {rec}")
        self.assertEqual(rec["reason"], "changed")
        self.assertEqual(rec["verified"], 1, "CFG/SSA verifier must pass")
        self.assertIn("before", rec)
        self.assertIn("after", rec)
        self.assertNotEqual(rec["before"], rec["after"])
        self.assertIn("phi=", rec["after"], "After snapshot must contain Phi node")

        # 3. Runtime parity at -O2
        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_02_pre_negative_redefinition_safety(self):
        """PRE must safely skip when operand is redefined on missing path."""
        src = ROOT / "tests/opt_structural/pre_redef_negative.vri"
        out_bin = self.scratch_dir / "test_pre_redef"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "compute_pre_redef", "pre")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"PRE must not hoist when redefined: {rec}")
        self.assertIn(rec["reason"], ["operand_redefined_in_join", "no_candidate"])
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_03_pre_negative_barrier_safety(self):
        """PRE must safely skip when call/memory barrier is present on path."""
        src = ROOT / "tests/opt_structural/pre_barrier_negative.vri"
        out_bin = self.scratch_dir / "test_pre_barrier"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_pre_barrier", "pre")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"PRE must not hoist across barrier: {rec}")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_04_pre_mutation_identity_fails_oracle(self):
        """Mutation mode --mutate-mir=identity_pre must cause positive structural oracle to fail."""
        src = ROOT / "tests/opt_structural/pre_positive.vri"
        out_bin = self.scratch_dir / "test_pre_mut_ident"

        res_mut = run_cmd([str(VIRC), str(src), "-O2", "--mutate-mir=identity_pre", "--json", "-o", str(out_bin)])
        self.assertEqual(res_mut.returncode, 0, res_mut.stderr)
        payload = json.loads(res_mut.stdout)
        rec = extract_transform(payload, "compute_pre", "pre")
        self.assertIsNotNone(rec)
        # Structural oracle expects changed == 1. Under identity_pre mutation, changed is 0!
        self.assertEqual(rec["changed"], 0, "Identity mutation must NOT perform real PRE")
        self.assertEqual(rec["reason"], "mutation_identity_pre")

    def test_05_pre_mutation_corrupt_phi_fails_verifier(self):
        """Mutation mode --mutate-mir=corrupt_pre_phi must trigger CFG/SSA verifier failure E6001."""
        src = ROOT / "tests/opt_structural/pre_positive.vri"
        out_bin = self.scratch_dir / "test_pre_mut_corrupt"

        res = run_cmd([str(VIRC), str(src), "-O2", "--mutate-mir=corrupt_pre_phi", "-o", str(out_bin)])
        self.assertNotEqual(res.returncode, 0, "Corrupt phi mutation MUST cause compile failure")
        self.assertEqual(res.returncode, 1)
        err_out = res.stdout + res.stderr
        self.assertIn("E6001", err_out)
        self.assertIn("MIR CFG/SSA verification failed", err_out)

    def test_06_loop_fusion_positive_structural_and_runtime(self):
        """Loop fusion merges two adjacent loops with identical bounds into a single loop."""
        src = ROOT / "tests/opt_structural/loop_fusion_positive.vri"
        out_bin = self.scratch_dir / "test_fusion_pos"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "255")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fusion", "loop_fusion")
        self.assertIsNotNone(rec, "loop_fusion transform record must exist")
        self.assertEqual(rec["changed"], 1, f"Loop fusion must report changed=1: {rec}")
        self.assertEqual(rec["reason"], "changed")
        self.assertEqual(rec["verified"], 1)
        self.assertIn("before", rec)
        self.assertIn("after", rec)
        self.assertNotEqual(rec["before"], rec["after"])

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_07_loop_fusion_negative_bounds(self):
        """Loop fusion must safely skip when loops have mismatched trip bounds."""
        src = ROOT / "tests/opt_structural/loop_fusion_negative_bounds.vri"
        out_bin = self.scratch_dir / "test_fusion_neg_bounds"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fusion_bounds", "loop_fusion")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, "Fusion must skip mismatched bounds")
        self.assertEqual(rec["reason"], "mismatched_bounds")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_08_loop_fusion_negative_barrier(self):
        """Loop fusion must safely skip when loop body has a call barrier."""
        src = ROOT / "tests/opt_structural/loop_fusion_negative_barrier.vri"
        out_bin = self.scratch_dir / "test_fusion_neg_bar"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fusion_barrier", "loop_fusion")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, "Fusion must skip when barrier present")
        self.assertEqual(rec["reason"], "barrier_in_body")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_09_loop_tiling_positive_and_negative(self):
        """Loop tiling transforms divisible 2D nests and skips non-divisible bounds."""
        pos_src = ROOT / "tests/opt_structural/loop_tiling_positive.vri"
        neg_src = ROOT / "tests/opt_structural/loop_tiling_negative_bounds.vri"
        out_bin = self.scratch_dir / "test_tiling"

        # Positive 32x32
        res_o0 = run_cmd([str(VIRC), str(pos_src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected_pos = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected_pos, "31744")

        res_o2 = run_cmd([str(VIRC), str(pos_src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec_pos = extract_transform(payload, "test_tiling", "loop_tiling")
        self.assertIsNotNone(rec_pos)
        self.assertEqual(rec_pos["changed"], 1, f"Tiling must report changed=1: {rec_pos}")
        self.assertEqual(rec_pos["reason"], "changed")
        self.assertEqual(rec_pos["verified"], 1)
        self.assertNotEqual(rec_pos["before"], rec_pos["after"])
        self.assertEqual(run_cmd([str(out_bin)]).stdout.strip(), expected_pos)

        # Negative 15x15
        res_neg = run_cmd([str(VIRC), str(neg_src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_neg.returncode, 0, res_neg.stderr)
        payload_neg = json.loads(res_neg.stdout)
        rec_neg = extract_transform(payload_neg, "test_tiling_bounds", "loop_tiling")
        self.assertIsNotNone(rec_neg)
        self.assertEqual(rec_neg["changed"], 0)
        self.assertEqual(rec_neg["reason"], "bounds_not_divisible_by_tile_size")

    def test_10_loop_interchange_positive_and_negative(self):
        """Loop interchange swaps safe 2D nests and skips (<, >) dependence directions."""
        pos_src = ROOT / "tests/opt_structural/loop_interchange_positive.vri"
        neg_src = ROOT / "tests/opt_structural/loop_interchange_negative.vri"
        out_bin = self.scratch_dir / "test_interchange"

        # Positive 8x8
        res_o0 = run_cmd([str(VIRC), str(pos_src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected_pos = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected_pos, "2016")

        res_o2 = run_cmd([str(VIRC), str(pos_src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec_pos = extract_transform(payload, "test_interchange", "loop_interchange")
        self.assertIsNotNone(rec_pos)
        self.assertEqual(rec_pos["changed"], 1, f"Interchange must report changed=1: {rec_pos}")
        self.assertEqual(rec_pos["reason"], "changed")
        self.assertEqual(rec_pos["verified"], 1)
        self.assertNotEqual(rec_pos["before"], rec_pos["after"])
        self.assertEqual(run_cmd([str(out_bin)]).stdout.strip(), expected_pos)

        # Negative (<, >) direction violation
        res_neg = run_cmd([str(VIRC), str(neg_src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_neg.returncode, 0, res_neg.stderr)
        payload_neg = json.loads(res_neg.stdout)
        rec_neg = extract_transform(payload_neg, "test_interchange_negative", "loop_interchange")
        self.assertIsNotNone(rec_neg)
        self.assertEqual(rec_neg["changed"], 0)
        self.assertEqual(rec_neg["reason"], "dependence_direction_violation")

    def test_11_loop_mutation_marker_fails_oracle(self):
        """Mutation mode --mutate-mir=marker_loop_transforms causes loop positive oracle to reject."""
        src = ROOT / "tests/opt_structural/loop_fusion_positive.vri"
        out_bin = self.scratch_dir / "test_loop_mut"

        res = run_cmd([str(VIRC), str(src), "-O2", "--mutate-mir=marker_loop_transforms", "--json", "-o", str(out_bin)])
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        rec = extract_transform(payload, "test_fusion", "loop_fusion")
        self.assertIsNotNone(rec)
        # Structural oracle requires changed == 1 with reason == "changed". Under marker mutation, reason is marker only!
        self.assertNotEqual(rec["reason"], "changed", "Marker mutation must NOT report changed status")
        self.assertIn(rec["reason"], ["mutation_marker_only", "mutation_bypassed"])

    def test_12_cross_optimization_level_parity(self):
        """All positive fixtures produce identical stdout across -O0, -O1, -O2, -O3."""
        fixtures = [
            ("tests/opt_structural/pre_positive.vri", "95\n57"),
            ("tests/opt_structural/loop_fusion_positive.vri", "255"),
            ("tests/opt_structural/loop_tiling_positive.vri", "31744"),
            ("tests/opt_structural/loop_interchange_positive.vri", "2016"),
        ]
        out_bin = self.scratch_dir / "test_parity"
        for rel_path, expected in fixtures:
            src = ROOT / rel_path
            for opt in ["-O0", "-O1", "-O2", "-O3"]:
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"{rel_path} {opt} compile failed: {res.stderr}")
                run = run_cmd([str(out_bin)])
                self.assertEqual(run.returncode, 0, f"{rel_path} {opt} run failed: {run.stderr}")
                self.assertEqual(run.stdout.strip(), expected, f"{rel_path} {opt} output mismatch")

    def test_13_bootstrap_tests_pass(self):
        """Existing bootstrap tests execute and pass with production passes active."""
        for test_file in [
            "tests/bootstrap_codegen/cg_optimizer_pre.vri",
            "tests/bootstrap_codegen/cg_optimizer_loop_tiling_fusion.vri",
        ]:
            src = ROOT / test_file
            out_bin = self.scratch_dir / "test_boot"
            for opt in ["-O0", "-O1", "-O2", "-O3"]:
                res = run_cmd([str(VIRC), str(src), opt, "-o", str(out_bin)])
                self.assertEqual(res.returncode, 0, f"{test_file} {opt} compile failed: {res.stderr}")
                run = run_cmd([str(out_bin)])
                self.assertEqual(run.returncode, 0, f"{test_file} {opt} execution failed: {run.stderr}")

    def test_14_loop_fusion_step_positive(self):
        """Loop fusion must not mistake accumulation using IV for the induction step."""
        src = ROOT / "tests/opt_structural/loop_fusion_step_positive.vri"
        out_bin = self.scratch_dir / "test_fusion_step"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "90")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fuse_step", "loop_fusion")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 1)
        self.assertEqual(rec["reason"], "changed")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_15_loop_fusion_negative_mismatched_init(self):
        """Loop fusion must reject loops with mismatched initial induction values."""
        src = ROOT / "tests/opt_structural/loop_fusion_negative_init.vri"
        out_bin = self.scratch_dir / "test_fusion_init"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "215")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fuse_init", "loop_fusion")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0)
        self.assertEqual(rec["reason"], "mismatched_bounds")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_16_loop_tiling_negative_nonzero_lower_bound(self):
        """Loop tiling must reject loops whose trip count is not divisible by tile size."""
        src = ROOT / "tests/opt_structural/loop_tiling_negative_lb.vri"
        out_bin = self.scratch_dir / "test_tiling_lb"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "31248")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_tiling_lb", "loop_tiling")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0)
        self.assertEqual(rec["reason"], "bounds_not_divisible_by_tile_size")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_17_loop_interchange_negative_dependent_bound(self):
        """Loop interchange must reject non-rectangular nests where inner bound depends on outer IV."""
        src = ROOT / "tests/opt_structural/loop_interchange_negative_dep.vri"
        out_bin = self.scratch_dir / "test_interchange_dep"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "1176")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_interchange_dep", "loop_interchange")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0)
        self.assertEqual(rec["reason"], "non_rectangular_domain")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_18_loop_fusion_negative_dependent_entry(self):
        """Loop fusion must reject when loop 2 entry value depends on loop 1 (cross-loop data dependency)."""
        src = ROOT / "tests/opt_structural/loop_fusion_negative_dep.vri"
        out_bin = self.scratch_dir / "test_fusion_dep"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "90")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_fusion_dep", "loop_fusion")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"Must skip fusion when loop 2 depends on loop 1: {rec}")
        self.assertEqual(rec["reason"], "barrier_in_body")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_19_loop_tiling_negative_dependent_bound(self):
        """Loop tiling must reject triangular nests where inner bound depends on outer IV."""
        src = ROOT / "tests/opt_structural/loop_tiling_negative_dep.vri"
        out_bin = self.scratch_dir / "test_tiling_dep"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "15376")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_tiling_dep", "loop_tiling")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"Must skip tiling on triangular nest: {rec}")
        self.assertEqual(rec["reason"], "non_rectangular_domain")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_20_loop_interchange_negative_mismatched_inits(self):
        """Loop interchange must reject rectangular nests with mismatched initial values."""
        src = ROOT / "tests/opt_structural/loop_interchange_negative_init.vri"
        out_bin = self.scratch_dir / "test_interchange_init"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "90")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_interchange_init", "loop_interchange")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"Must skip interchange on mismatched inits: {rec}")
        self.assertEqual(rec["reason"], "mismatched_bounds")
        self.assertEqual(rec["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)

    def test_21_loop_tiling_negative_expression_pattern(self):
        """Loop tiling must not rewrite a different Add/Add/Move reduction shape."""
        src = ROOT / "tests/opt_structural/loop_tiling_negative_pattern.vri"
        out_bin = self.scratch_dir / "test_tiling_pattern"

        res_o0 = run_cmd([str(VIRC), str(src), "-O0", "-o", str(out_bin)])
        self.assertEqual(res_o0.returncode, 0, res_o0.stderr)
        expected = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(expected, "23040\n67")

        res_o2 = run_cmd([str(VIRC), str(src), "-O2", "--json", "-o", str(out_bin)])
        self.assertEqual(res_o2.returncode, 0, res_o2.stderr)
        payload = json.loads(res_o2.stdout)
        rec = extract_transform(payload, "test_tiling_pattern", "loop_tiling")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["changed"], 0, f"Must skip tiling on an unsupported reduction: {rec}")
        self.assertEqual(rec["reason"], "unsupported_loop_body")
        self.assertEqual(rec["verified"], 1)

        rec_overwrite = extract_transform(payload, "test_tiling_overwrite", "loop_tiling")
        self.assertIsNotNone(rec_overwrite)
        self.assertEqual(rec_overwrite["changed"], 0, f"Must require a carried reduction Phi chain: {rec_overwrite}")
        self.assertEqual(rec_overwrite["reason"], "unsupported_loop_body")
        self.assertEqual(rec_overwrite["verified"], 1)

        actual = run_cmd([str(out_bin)]).stdout.strip()
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--virc", type=Path, default=VIRC)
    parsed_args, remaining = parser.parse_known_args()
    VIRC = parsed_args.virc.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
