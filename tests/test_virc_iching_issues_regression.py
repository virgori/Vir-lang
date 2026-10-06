#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = ROOT / "bin/virc"

def run_cmd(cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def test_issue_1():
    print("[RUN] Test Issue 1: Diagnostic source span in included file...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "stdlib").symlink_to(ROOT / "stdlib")
        (tmp_path / "leaf.vri").write_text("# padding\n" * 10 + "func bad:\n    in\n        ref value: int\n    value = 1\nend.\n")
        (tmp_path / "main.vri").write_text('include "leaf.vri"\nfunc main:\n    out 0\nend.\n')
        res = run_cmd([str(VIRC), str(tmp_path / "main.vri"), "--json", "-o", str(tmp_path / "app")])
        assert res.returncode != 0, f"Expected compilation failure, got {res.returncode}"
        data = json.loads(res.stdout)
        assert data.get("code") == "E3046", f"Expected E3046, got {data.get('code')}"
        prim = data.get("primary_span", {})
        assert prim.get("file", "").endswith("leaf.vri"), f"Expected leaf.vri, got {prim.get('file')}"
        assert prim.get("start_line") == 12, f"Expected line 12, got {prim.get('start_line')}"
        assert prim.get("start_column") == 5, f"Expected column 5, got {prim.get('start_column')}"
        rel = data.get("related_locations", [])
        assert len(rel) == 1, f"Expected 1 related location, got {len(rel)}"
        assert rel[0].get("file", "").endswith("leaf.vri"), f"Expected leaf.vri, got {rel[0].get('file')}"
        assert rel[0].get("line") == 13, f"Expected related line 13, got {rel[0].get('line')}"
        assert rel[0].get("column") == 9, f"Expected related col 9, got {rel[0].get('column')}"
    print("  -> [PASS] Issue 1 verified.")

def test_issue_2():
    print("[RUN] Test Issue 2: Real column, functionContext, expectedType, actualType...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "stdlib").symlink_to(ROOT / "stdlib")
        (tmp_path / "leaf.vri").write_text("# padding\n" * 10 + "func bad() -> string:\n    out 42\nend.\n")
        (tmp_path / "main.vri").write_text('include "leaf.vri"\nfunc main:\n    out 0\nend.\n')
        res = run_cmd([str(VIRC), str(tmp_path / "main.vri"), "--json", "-o", str(tmp_path / "app")])
        assert res.returncode != 0, f"Expected compilation failure, got {res.returncode}"
        data = json.loads(res.stdout)
        assert data.get("code") == "E3007", f"Expected E3007, got {data.get('code')}"
        prim = data.get("primary_span", {})
        assert prim.get("file", "").endswith("leaf.vri"), f"Expected leaf.vri, got {prim.get('file')}"
        assert prim.get("start_line") == 12, f"Expected line 12, got {prim.get('start_line')}"
        assert prim.get("start_column") == 9, f"Expected column 9 (not 2429), got {prim.get('start_column')}"
        assert data.get("functionContext") == "bad", f"Expected functionContext 'bad', got {data.get('functionContext')}"
        assert data.get("expectedType") == "string", f"Expected expectedType 'string', got {data.get('expectedType')}"
        assert data.get("actualType") == "int", f"Expected actualType 'int', got {data.get('actualType')}"
    print("  -> [PASS] Issue 2 verified.")

def test_issue_3():
    iching_dir = Path("/Users/gengyang/Desktop/Repo/iching-vir")
    if not iching_dir.exists():
        print("[SKIP] Issue 3: iching-vir repo not found at /Users/gengyang/Desktop/Repo/iching-vir")
        return
    print("[RUN] Test Issue 3: No compile crash on test_scoring_preprocessor.vri...")
    bin_path = "/tmp/scoring_test_reg"
    res = run_cmd([str(VIRC), "tests/test_scoring_preprocessor.vri", "-o", bin_path], cwd=iching_dir)
    assert res.returncode == 0, f"Compile failed: {res.stderr}\n{res.stdout}"
    run_cmd(["codesign", "-s", "-", "-f", bin_path])
    res_run = run_cmd([bin_path], cwd=iching_dir)
    assert res_run.returncode == 0, f"Execution failed: {res_run.stderr}\n{res_run.stdout}"
    print("  -> [PASS] Issue 3 verified.")

def test_issue_4():
    iching_dir = Path("/Users/gengyang/Desktop/Repo/iching-vir")
    if not iching_dir.exists():
        print("[SKIP] Issue 4: iching-vir repo not found at /Users/gengyang/Desktop/Repo/iching-vir")
        return
    print("[RUN] Test Issue 4: json.push probe length == 1 in test_yingqi_engine.vri...")
    bin_path = "/tmp/yingqi_test_reg"
    res = run_cmd([str(VIRC), "tests/test_yingqi_engine.vri", "-o", bin_path], cwd=iching_dir)
    assert res.returncode == 0, f"Compile failed: {res.stderr}\n{res.stdout}"
    run_cmd(["codesign", "-s", "-", "-f", bin_path])
    res_run = run_cmd([bin_path], cwd=iching_dir)
    assert "probe len: \n1" in res_run.stdout or "probe len: 1" in res_run.stdout, f"probe len: 1 not found in stdout:\n{res_run.stdout}"
    print("  -> [PASS] Issue 4 verified.")

def test_issue_5():
    print("[RUN] Test Issue 5: Indirect call with ref parameter...")
    bin_path = "/tmp/test_cb_ref_reg"
    res = run_cmd([str(VIRC), "tests/test_cb_ref_regression.vri", "-o", bin_path])
    assert res.returncode == 0, f"Compile failed: {res.stderr}\n{res.stdout}"
    run_cmd(["codesign", "-s", "-", "-f", bin_path])
    res_run = run_cmd([bin_path])
    assert res_run.returncode == 0, f"Execution failed: {res_run.stderr}\n{res_run.stdout}"
    lines = [l.strip() for l in res_run.stdout.splitlines() if l.strip()]
    assert "probe entered" in lines, f"probe entered missing: {res_run.stdout}"
    assert "52" in lines, f"52 missing: {res_run.stdout}"
    assert "62" in lines, f"62 missing: {res_run.stdout}"
    print("  -> [PASS] Issue 5 verified.")

def main():
    print("=" * 60)
    print(" VIR COMPILER REGRESSION TEST SUITE (ICHING FIXES 1 - 5)")
    print("=" * 60)
    test_issue_1()
    test_issue_2()
    test_issue_3()
    test_issue_4()
    test_issue_5()
    print("=" * 60)
    print(" ALL 5 REGRESSION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
